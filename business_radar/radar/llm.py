"""The only module in this package that is allowed to talk to Google.

Three things would go wrong without it, and the third is the one that cannot be undone.

The first is provenance. `_CONTEXT.md` section 2 says never call a model without recording the
model id, the prompt version and the token counts beside the output. Scattered across three
call sites that becomes a convention somebody forgets on a Friday, and the row that says "the
AI decided this business needs a system" stops being reproducible. Here it is mechanical: every
call goes through `complete_json`, and `complete_json` cannot return without having written a
`llm_quota_ledger` row.

The second is the quota. The free tier is not a bill, it is a wall - ten requests a minute and
a few hundred a day, after which the API returns 429 and stays that way until midnight in
California. A wall handled badly looks like a campaign that failed; handled properly it is a
campaign that pauses and resumes after lunch. `QuotaExhausted` is deliberately not an error:
it is a deferral, and nothing in this module treats it as a failure.

The third is PII. Free-tier content may be used by Google to improve their products. A
proprietor's mobile number in a research prompt is a contact detail collected for one purpose
and handed to a third party for another, which under the DPDP Act is a purpose-limitation
failure that no disclaimer repairs - and unlike a bad score it cannot be corrected afterwards,
because the data has left the laptop. So `scrub_pii` redacts and `assert_no_pii` refuses: the
redactor is a transformation that can miss a format, the assertion can only pass or fail, and
the job dies rather than the number travelling. Redacting inside the assertion would hide the
extractor bug that produced it, and the next bug would leak something this module has never
heard of.

Nothing else under `radar/` may import `google.genai`. The import here is deliberately lazy so
the package stays importable - and testable - on a machine with no SDK and no API key.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from .config import LLMConfig
from .ids import new_id
from .paths import CAPTURE_DIR

log = logging.getLogger("radar.llm")

# The alias we ask for. What gets recorded is resp.model_version, the build it resolved to.
DEFAULT_MODEL = "gemini-2.5-flash"

# Purposes the ledger's CHECK accepts. RESEARCH, ASSESS, GATHER and REPAIR are this pipeline's;
# MESSAGE and CLASSIFY belong to the drafting and reply paths and are listed so their share of
# the day is visible in the same table.
RESEARCH_PURPOSES: frozenset[str] = frozenset({"RESEARCH", "ASSESS", "GATHER", "REPAIR"})
PURPOSES: frozenset[str] = RESEARCH_PURPOSES | {"MESSAGE", "CLASSIFY", "OTHER"}

# Research's share of the day's requests. The remaining quarter is reserved for drafting and
# classification, which Sagar waits on: a campaign that eats the whole day's quota leaves him
# unable to draft a reply to the one business that answered.
# SIMPLIFIED: doc 02 section 2.16 gives research its own `research.quota.daily_request_cap`
# (150 of 200). ResearchConfig carries no quota block, so the share is a fraction of
# llm.daily_request_cap instead of a second configured number.
RESEARCH_SHARE = 0.75


# ===========================================================================
# Errors
# ===========================================================================

class LLMError(RuntimeError):
    """The model call could not be made or its answer could not be used."""


class LLMNotConfigured(LLMError):
    """No GEMINI_API_KEY, or the SDK is not installed. A supported state, not a crash."""


class LLMResponseInvalid(LLMError):
    """The model answered, but not with the JSON object the schema asked for."""


class QuotaExhausted(LLMError):
    """The free-tier ceiling was reached. Defer, do not fail.

    `scope` says which wall was hit and therefore how long to wait: RPM and TPM are minutes,
    RPD is the next Pacific midnight. `retry_after_seconds` is what the caller should sleep or
    schedule against; `resume_at` is the same thing as a timestamp.
    """

    def __init__(self, message: str, *, scope: str = "RPD",
                 retry_after_seconds: float | None = None,
                 resume_at: datetime | None = None) -> None:
        super().__init__(message)
        self.scope = scope
        self.retry_after_seconds = retry_after_seconds
        self.resume_at = resume_at


class PiiLeak(RuntimeError):
    """A contact detail was found in a payload that was about to leave the laptop.

    Not a warning and not a redaction. The job fails, loudly, and the fixture that reproduces
    it goes into the test suite.
    """

    def __init__(self, kinds: Sequence[str], *, where: str) -> None:
        super().__init__(
            f"{where}: refusing to send a payload containing "
            f"{', '.join(sorted(set(kinds))) or 'personal data'} to a free-tier LLM"
        )
        self.kinds = list(kinds)
        self.where = where


# ===========================================================================
# The PII boundary (doc 02 section 2.10.0)
# ===========================================================================
# Everything in the first group is replaced by a typed placeholder. Everything in the second
# is deliberately kept: a GSTIN is a registration number printed on the invoice footer of
# every shop in India, not a way to reach a person, and it is both a REGULATORY finding and a
# size signal. A postal address is where the business is, which is the LOCATION dimension.

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_MAILTO_RE = re.compile(r"mailto:\s*[^\s\"'<>)]+", re.IGNORECASE)

# Indian mobile: ten digits starting 6-9, optionally +91 / 0091 / 0 prefixed, with spaces or
# hyphens anywhere inside. Landline: an STD code of 2-5 digits then 6-8 digits.
_MOBILE_RE = re.compile(
    r"(?<![0-9A-Za-z])(?:\+?91[\s\-]?|0(?![0-9]{11}))?[6-9][0-9](?:[\s\-]?[0-9]){8}"
    r"(?![0-9])"
)
_LANDLINE_RE = re.compile(
    r"(?<![0-9A-Za-z])(?:\+?91[\s\-]?)?0?\d{2,5}[\s\-]\d{6,8}(?![0-9])"
)
_TEL_RE = re.compile(r"tel:\s*\+?[0-9][0-9\s\-]{6,}", re.IGNORECASE)
_WA_RE = re.compile(
    r"(?:https?://)?(?:wa\.me/|api\.whatsapp\.com/send\?phone=)\+?[0-9]{8,15}",
    re.IGNORECASE,
)

_HONORIFICS = ("Dr", "Shri", "Smt", "Mr", "Mrs", "Ms", "Adv", "CA", "CS", "Prof")
_PERSON_RE = re.compile(
    r"\b(?:" + "|".join(_HONORIFICS) + r")\.?\s+"
    r"(?:[A-Z][a-zA-Z]*\.?\s*){1,3}"
)
_DESIGNATIONS = ("Managing Director", "Proprietor", "Director", "Founder", "Owner",
                 "Principal", "Chairman", "Trustee", "Dean", "Partner")
_DESIGNATION_RE = re.compile(
    # Separators are spaces, tabs, commas and dashes - never a newline. A rule that crosses
    # lines joins the end of one paragraph to the start of the next and redacts both.
    r"\b(?:[A-Z][a-zA-Z]+(?:[ \t]+|,[ \t]*|[ \t]*-[ \t]*)){1,3}"
    r"(?=(?:the[ \t]+)?(?:" + "|".join(_DESIGNATIONS) + r")\b)"
)

_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_AADHAAR_RE = re.compile(r"(?<![0-9])[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}(?![0-9])")

# Kept, never redacted. Listed so a future edit does not "tidy" them into the group above.
GSTIN_RE = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
CIN_RE = re.compile(r"\b[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\b")

PLACEHOLDERS: dict[str, str] = {
    "EMAIL": "[email]",
    "PHONE": "[phone]",
    "PERSON": "[person]",
    "ID": "[id]",
}


@dataclass(slots=True, frozen=True)
class PiiHit:
    """One span the redactor found, with enough to explain itself in a log line."""
    kind: str            # EMAIL | PHONE | PERSON | ID
    start: int
    end: int
    value: str

    @property
    def placeholder(self) -> str:
        return PLACEHOLDERS[self.kind]


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", _MAILTO_RE),
    ("EMAIL", _EMAIL_RE),
    ("PHONE", _WA_RE),
    ("PHONE", _TEL_RE),
    ("PHONE", _MOBILE_RE),
    ("PHONE", _LANDLINE_RE),
    ("ID", _PAN_RE),
    ("ID", _AADHAAR_RE),
    ("PERSON", _PERSON_RE),
    ("PERSON", _DESIGNATION_RE),
)


def _protected_spans(text: str, protect: Iterable[str]) -> list[tuple[int, int]]:
    """Character ranges the redactor must leave alone.

    A hospital called "Dr. Patil Hospital" would otherwise have its own name redacted by the
    honorific rule, and the model would then be unable to confirm the identity it was asked
    about. Business names, `name_norm` and OSM operator/brand tags go in here.
    """
    spans: list[tuple[int, int]] = []
    lowered = text.lower()
    for phrase in protect:
        phrase = (phrase or "").strip()
        if len(phrase) < 3:
            continue
        needle = phrase.lower()
        start = lowered.find(needle)
        while start != -1:
            spans.append((start, start + len(needle)))
            start = lowered.find(needle, start + 1)
    # Keep GSTIN and CIN out of the ID rule's way: they are registration numbers, not contacts.
    for pattern in (GSTIN_RE, CIN_RE):
        for match in pattern.finditer(text):
            spans.append(match.span())
    return spans


def _overlaps(span: tuple[int, int], spans: Sequence[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in spans)


def find_pii(text: str, *, protect: Iterable[str] = ()) -> list[PiiHit]:
    """Every contact-shaped span in `text`, longest first, non-overlapping.

    Ordering matters: `mailto:someone@x.in` must be found as one span before the bare address
    inside it is, or the redaction leaves `mailto:[email]` next to a half-eaten href.
    """
    if not text:
        return []
    protected = _protected_spans(text, protect)
    hits: list[PiiHit] = []
    taken: list[tuple[int, int]] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if span[1] - span[0] < 3:
                continue
            if _overlaps(span, protected) or _overlaps(span, taken):
                continue
            taken.append(span)
            hits.append(PiiHit(kind=kind, start=span[0], end=span[1], value=match.group(0)))
    hits.sort(key=lambda h: h.start)
    return hits


def scrub_pii(text: str, *, protect: Iterable[str] = ()) -> str:
    """Replace every contact value in `text` with its typed placeholder.

    The placeholder is typed and empty on purpose: `[email]` tells the model that an address
    was published on this page - which is a real DIGITAL_PRESENCE fact and a real CONTACT one -
    without telling it what the address is.
    """
    return redact(text, protect=protect)[0]


def redact(text: str, *, protect: Iterable[str] = ()) -> tuple[str, list[PiiHit]]:
    """scrub_pii, plus the list of what was removed, for `sources.redaction_count`."""
    hits = find_pii(text, protect=protect)
    if not hits:
        return text, []
    out: list[str] = []
    cursor = 0
    for hit in hits:
        out.append(text[cursor:hit.start])
        out.append(hit.placeholder)
        # The person rules swallow the separator that follows the name so the span stays
        # contiguous. Putting it back keeps "[person], Director" readable rather than
        # "[person]Director", which reads as a defect in the page rather than as our redaction.
        trailing = hit.value[len(hit.value.rstrip()):]
        if trailing:
            out.append(trailing)
        cursor = hit.end
    out.append(text[cursor:])
    return "".join(out), hits


def assert_no_pii(payload: str, *, where: str, protect: Iterable[str] = ()) -> None:
    """Raise `PiiLeak` if a payload about to be sent carries an email, phone, person or id.

    This is the assertion half of the boundary and it runs on the assembled bytes, not on a
    helper's return value, because the thing that must be true is a property of what leaves
    the process.
    """
    hits = find_pii(payload, protect=protect)
    if hits:
        sample = ", ".join(f"{h.kind}@{h.start}" for h in hits[:5])
        log.error("%s: %d PII spans in an outbound payload (%s)", where, len(hits), sample)
        raise PiiLeak([h.kind for h in hits], where=where)


# ===========================================================================
# Prompt-injection defence (doc 02 section 2.9)
# ===========================================================================

DOCUMENT_OPEN = "<document"
UNTRUSTED_OPEN = "<untrusted_content>"
UNTRUSTED_CLOSE = "</untrusted_content>"

_DELIMITERS = (UNTRUSTED_OPEN, UNTRUSTED_CLOSE, DOCUMENT_OPEN, "</document>")

INJECTION_MARKERS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in (
        r"ignore (all |any |the )?(previous|prior|above) instructions",
        r"disregard (the |all )?(previous|prior|above)",
        r"you are (now|actually) ",
        r"system prompt",
        r"</?(system|assistant|human)>",
        r"<\|im_(start|end)\|>",
        r"\bassistant\s*:",
        r"\bAI\s+instructions?\b",
        r"do not (mention|record|report) ",
        r"(record|write|say) that (this|the) business",
    )
)


def neutralise_delimiters(text: str) -> str:
    """Escape every literal envelope token so a page cannot close our own tag.

    Without this a fetched page can print `</untrusted_content>` and everything after it reads
    as an instruction from us rather than as data from them. It is the one step in the
    sanitiser that an attacker cannot work around by writing better prose.
    """
    for token in _DELIMITERS:
        text = text.replace(token, token.replace("<", "&lt;").replace(">", "&gt;"))
    return text


def scan_for_injection(text: str) -> list[str]:
    """The deterministic pre-scan. Returns the markers that matched, empty when clean."""
    return [m.pattern for m in INJECTION_MARKERS if m.search(text)]


def wrap_untrusted(text: str, *, doc_id: str, source_type: str, url: str,
                   checked_at: str, sha256: str) -> str:
    """Put one fetched document into its envelope, delimiters already neutralised.

    The envelope is the whole of layer 2 in the defence table: the content stays inside a
    block the system prompt has labelled as data, and it cannot end that block early.
    """
    body = neutralise_delimiters(text)
    return (
        f'{DOCUMENT_OPEN} id="{doc_id}" source_type="{source_type}" url="{url}"\n'
        f'          checked_at="{checked_at}" sha256="{sha256[:8]}">\n'
        f"{UNTRUSTED_OPEN}\n{body}\n{UNTRUSTED_CLOSE}\n</document>"
    )


# ===========================================================================
# Quota: the day, and what has been spent of it
# ===========================================================================

def _zone(name: str, fallback_hours: float) -> Any:
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # no tzdata on this machine
        return timezone(timedelta(hours=fallback_hours))


_QUOTA_TZ = _zone("America/Los_Angeles", -8)     # Google AI Studio resets on Pacific time
_REPORT_TZ = _zone("Asia/Kolkata", 5.5)          # every number Sagar reads is IST


def quota_day(now: datetime | None = None) -> str:
    """The Pacific date the free-tier daily allowance is counted against."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(_QUOTA_TZ).date().isoformat()


def report_day(now: datetime | None = None) -> str:
    """The IST date every human-facing daily number is grouped by."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(_REPORT_TZ).date().isoformat()


def next_quota_reset(now: datetime | None = None) -> datetime:
    """When the daily request allowance rolls over, in UTC.

    Midnight America/Los_Angeles, not midnight IST. In IST that is early afternoon, so a
    campaign that exhausts its quota at 11:00 resumes the same day after lunch rather than
    tomorrow - which is worth knowing before you conclude the machine is stuck.
    """
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(_QUOTA_TZ)
    tomorrow = date.fromisoformat(local.date().isoformat()) + timedelta(days=1)
    midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=_QUOTA_TZ)
    return midnight.astimezone(timezone.utc)


def requests_today(conn: sqlite3.Connection, *, purposes: Iterable[str] | None = None,
                   now: datetime | None = None) -> int:
    """Requests recorded against today's Pacific quota day, optionally by purpose."""
    day = quota_day(now)
    if purposes is None:
        row = conn.execute(
            "SELECT COALESCE(SUM(requests), 0) AS n FROM llm_quota_ledger WHERE quota_day = ?",
            (day,),
        ).fetchone()
        return int(row["n"])
    names = sorted(set(purposes))
    marks = ",".join("?" for _ in names)
    row = conn.execute(
        f"SELECT COALESCE(SUM(requests), 0) AS n FROM llm_quota_ledger "
        f"WHERE quota_day = ? AND purpose IN ({marks})",
        (day, *names),
    ).fetchone()
    return int(row["n"])


def quota_summary(conn: sqlite3.Connection, *, cfg: LLMConfig,
                  now: datetime | None = None) -> dict[str, Any]:
    """What is left of today, for the settings page and for a log line before a campaign."""
    used = requests_today(conn, now=now)
    research_used = requests_today(conn, purposes=RESEARCH_PURPOSES, now=now)
    research_cap = max(1, int(cfg.daily_request_cap * RESEARCH_SHARE))
    return {
        "quota_day": quota_day(now),
        "report_day": report_day(now),
        "requests_used": used,
        "requests_cap": cfg.daily_request_cap,
        "requests_left": max(0, cfg.daily_request_cap - used),
        "research_used": research_used,
        "research_cap": research_cap,
        "research_left": max(0, research_cap - research_used),
        "resets_at": next_quota_reset(now).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ===========================================================================
# One call, and what is recorded about it
# ===========================================================================

@dataclass(slots=True)
class LLMResponse:
    """One model answer, with everything an audit three years from now needs.

    `model_id` is `resp.model_version` - the build the alias actually resolved to - and not the
    alias we asked for, because "gemini-2.5-flash" in a row from last March does not identify
    what produced it.
    """
    data: dict[str, Any]
    raw_text: str
    model_id: str
    prompt_version: str
    purpose: str
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: int = 0
    finish_reason: str | None = None
    capture_path: str | None = None
    capture_sha256: str | None = None
    ledger_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
            "purpose": self.purpose,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "cached_tokens": self.cached_tokens,
            "latency_ms": self.latency_ms,
            "capture_sha256": self.capture_sha256,
        }


class _RateBucket:
    """A minimum gap between requests, held in this process.

    The published RPM is ten. Ten evenly spaced requests are fine; ten in the same second is a
    429 and a wasted minute, and on a free tier a wasted minute is wasted throughput for the
    whole day.
    """

    def __init__(self, per_minute: int) -> None:
        self._gap = 60.0 / max(1, per_minute)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            sleep_for = self._gap - (now - self._last)
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last = time.monotonic()


# JSON Schema keywords the Gemini `response_schema` field rejects outright with a bare
# 400 INVALID_ARGUMENT that names none of them. Our schemas use them because they are correct
# JSON Schema and because the post-response validators read them; they simply cannot travel in
# the request. Stripping them costs nothing real - every one of these bounds is re-checked
# against the parsed response by the caller's validator, which is where a violation has to be
# caught anyway, since a model will happily ignore a bound it was told about.
_SCHEMA_UNSUPPORTED = frozenset({
    "minItems", "maxItems", "minLength", "maxLength", "minProperties", "maxProperties",
    "pattern", "patternProperties", "additionalProperties", "default", "examples", "$schema",
    "$id", "$ref", "definitions", "$defs", "const", "not", "if", "then", "else",
    "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "uniqueItems", "title",
})


def gemini_schema(schema: Any) -> Any:
    """A copy of `schema` carrying only what Gemini's structured-output mode accepts.

    Recurses through dicts and lists so nested object and array schemas are cleaned too.
    Everything meaningful survives: type, properties, required, items, enum, description,
    nullable and format.
    """
    if isinstance(schema, dict):
        return {
            k: gemini_schema(v)
            for k, v in schema.items()
            if k not in _SCHEMA_UNSUPPORTED
        }
    if isinstance(schema, list):
        return [gemini_schema(v) for v in schema]
    return schema


class GeminiClient:
    """The Gemini free tier, with the quota ledger and the PII assertion wired in.

    Construct one per process. It is safe to construct without an API key: `configured` is
    False, and every call raises `LLMNotConfigured` rather than the module failing to import.
    """

    def __init__(self, cfg: LLMConfig, conn: sqlite3.Connection | None = None, *,
                 capture_dir: Path = CAPTURE_DIR, enforce_quota: bool = True) -> None:
        self.cfg = cfg
        self.conn = conn
        self.capture_dir = Path(capture_dir) / "llm"
        self.enforce_quota = enforce_quota
        self._bucket = _RateBucket(cfg.requests_per_minute)
        self._sdk: Any = None

    # --- readiness ---------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.cfg.api_key)

    def _client(self) -> Any:
        """Build the SDK client on first use. The import is lazy on purpose.

        `radar/` must stay importable on a machine with no `google-genai` installed, because
        that is what lets the whole test suite run with no network and no key.
        """
        if self._sdk is not None:
            return self._sdk
        if not self.configured:
            raise LLMNotConfigured(
                "GEMINI_API_KEY is not set. Put it in config/.env; research cannot run "
                "without it, and nothing else in the pipeline needs it."
            )
        try:
            from google import genai                     # noqa: PLC0415 - deliberate
            from google.genai import types               # noqa: PLC0415
        except ImportError as exc:                       # pragma: no cover - env dependent
            raise LLMNotConfigured(
                "google-genai is not installed. pip install -r requirements.txt"
            ) from exc

        http_options: Any = None
        try:
            # Retries are disabled here on purpose: retries belong to the job runtime, which
            # owns the lease and the quota ledger. An SDK-internal retry spends a request that
            # nothing recorded.
            http_options = types.HttpOptions(timeout=self.cfg.timeout_seconds * 1000)
        except Exception:                                # pragma: no cover - SDK version drift
            http_options = None

        self._sdk = (genai.Client(api_key=self.cfg.api_key, http_options=http_options)
                     if http_options is not None
                     else genai.Client(api_key=self.cfg.api_key))
        return self._sdk

    # --- the quota gate ----------------------------------------------------

    def check_quota(self, purpose: str, *, now: datetime | None = None) -> None:
        """Raise `QuotaExhausted` before spending a request we do not have.

        The research share is checked before the global cap, so a campaign cannot quietly
        consume the requests reserved for the reply Sagar is waiting to answer.
        """
        if not (self.enforce_quota and self.conn is not None):
            return
        if purpose in RESEARCH_PURPOSES:
            cap = max(1, int(self.cfg.daily_request_cap * RESEARCH_SHARE))
            used = requests_today(self.conn, purposes=RESEARCH_PURPOSES, now=now)
            if used >= cap:
                raise QuotaExhausted(
                    f"research has used {used} of its {cap} requests for the quota day "
                    f"{quota_day(now)}; resuming at the next reset",
                    scope="RPD", resume_at=next_quota_reset(now),
                )
        used_all = requests_today(self.conn, now=now)
        if used_all >= self.cfg.daily_request_cap:
            raise QuotaExhausted(
                f"the daily request cap of {self.cfg.daily_request_cap} is spent for the "
                f"quota day {quota_day(now)}; resuming at the next reset",
                scope="RPD", resume_at=next_quota_reset(now),
            )

    # --- the call ----------------------------------------------------------

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        purpose: str,
        prompt_version: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int = 0,
        business_id: str | None = None,
        campaign_id: str | None = None,
        entity_table: str | None = None,
        entity_id: str | None = None,
        protect: Iterable[str] = (),
        capture_name: str | None = None,
    ) -> LLMResponse:
        """One structured-output call. Returns the parsed object, records everything.

        The order of the first three steps is the safety property: PII assertion, then quota
        gate, then request. Asserting after the request would mean the value had already left.
        """
        if purpose not in PURPOSES:
            raise ValueError(f"unknown purpose {purpose!r}; one of {sorted(PURPOSES)}")

        # 1. Nothing with a contact value in it goes out, whatever produced it.
        assert_no_pii(system, where=f"{purpose}/system", protect=protect)
        assert_no_pii(user, where=f"{purpose}/user", protect=protect)

        # 2. Nothing goes out that we do not have quota for.
        self.check_quota(purpose)

        client = self._client()
        from google.genai import types                   # noqa: PLC0415 - after _client()

        config_kwargs: dict[str, Any] = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_schema": gemini_schema(schema),
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "candidate_count": 1,
            "max_output_tokens": max_output_tokens or self.cfg.max_output_tokens,
        }
        try:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=thinking_budget)
        except Exception:                                # pragma: no cover - SDK version drift
            pass

        # No `tools` key, anywhere. The call that reads attacker-controlled text has no tools,
        # and the API enforces the same thing by refusing tools alongside a response schema.
        self._bucket.wait()
        started = time.monotonic()
        try:
            response = client.models.generate_content(
                model=self.cfg.model or DEFAULT_MODEL,
                contents=user,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            quota = _as_quota_error(exc)
            if quota is not None:
                self._record(purpose=purpose, model_id=self.cfg.model,
                             prompt_version=prompt_version, outcome="QUOTA",
                             latency_ms=latency_ms, error_code="429",
                             business_id=business_id, campaign_id=campaign_id,
                             entity_table=entity_table, entity_id=entity_id, requests=1)
                raise quota from exc
            self._record(purpose=purpose, model_id=self.cfg.model,
                         prompt_version=prompt_version, outcome="ERROR",
                         latency_ms=latency_ms, error_code=type(exc).__name__,
                         business_id=business_id, campaign_id=campaign_id,
                         entity_table=entity_table, entity_id=entity_id, requests=1)
            raise LLMError(f"{purpose} call failed: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        thinking_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)
        cached_tokens = int(getattr(usage, "cached_content_token_count", 0) or 0)
        model_id = str(getattr(response, "model_version", "") or self.cfg.model)
        raw_text = getattr(response, "text", "") or ""

        capture_path, capture_sha = self._capture(
            name=capture_name or f"{purpose.lower()}-{prompt_version}",
            payload={
                "purpose": purpose,
                "prompt_version": prompt_version,
                "model_asked": self.cfg.model,
                "model_id": model_id,
                "system": system,
                "user": user,
                "response_text": raw_text,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "thinking_tokens": thinking_tokens,
                    "cached_tokens": cached_tokens,
                },
            },
        )

        try:
            data = json.loads(raw_text)
        except (TypeError, ValueError) as exc:
            self._record(purpose=purpose, model_id=model_id, prompt_version=prompt_version,
                         outcome="INVALID", latency_ms=latency_ms,
                         input_tokens=input_tokens, output_tokens=output_tokens,
                         thinking_tokens=thinking_tokens, cached_tokens=cached_tokens,
                         business_id=business_id, campaign_id=campaign_id,
                         entity_table=entity_table, entity_id=entity_id, requests=1)
            raise LLMResponseInvalid(
                f"{purpose} returned {len(raw_text)} characters that are not JSON; "
                f"the exchange is captured at {capture_path}"
            ) from exc
        if not isinstance(data, dict):
            raise LLMResponseInvalid(f"{purpose} returned a {type(data).__name__}, not an object")

        ledger_id = self._record(
            purpose=purpose, model_id=model_id, prompt_version=prompt_version, outcome="OK",
            latency_ms=latency_ms, input_tokens=input_tokens, output_tokens=output_tokens,
            thinking_tokens=thinking_tokens, cached_tokens=cached_tokens,
            business_id=business_id, campaign_id=campaign_id,
            entity_table=entity_table, entity_id=entity_id, requests=1)

        finish = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish = str(getattr(candidates[0], "finish_reason", "") or "") or None

        return LLMResponse(
            data=data, raw_text=raw_text, model_id=model_id, prompt_version=prompt_version,
            purpose=purpose, input_tokens=input_tokens, output_tokens=output_tokens,
            thinking_tokens=thinking_tokens, cached_tokens=cached_tokens,
            latency_ms=latency_ms, finish_reason=finish,
            capture_path=str(capture_path) if capture_path else None,
            capture_sha256=capture_sha, ledger_id=ledger_id,
        )

    # --- recording ---------------------------------------------------------

    def _record(self, *, purpose: str, model_id: str, prompt_version: str, outcome: str,
                latency_ms: int, requests: int = 1, input_tokens: int = 0,
                output_tokens: int = 0, thinking_tokens: int = 0, cached_tokens: int = 0,
                error_code: str | None = None, business_id: str | None = None,
                campaign_id: str | None = None, entity_table: str | None = None,
                entity_id: str | None = None) -> str | None:
        """Write the ledger row. A call that happened and was not counted is a lie."""
        if self.conn is None:
            return None
        ledger_id = new_id("run")
        try:
            self.conn.execute(
                """
                INSERT INTO llm_quota_ledger
                    (id, quota_day, report_day, purpose, model_id, prompt_version,
                     business_id, campaign_id, entity_table, entity_id,
                     requests, input_tokens, output_tokens, thinking_tokens, cached_tokens,
                     outcome, latency_ms, error_code)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (ledger_id, quota_day(), report_day(), purpose, model_id or "unknown",
                 prompt_version, business_id, campaign_id, entity_table, entity_id,
                 requests, input_tokens, output_tokens, thinking_tokens, cached_tokens,
                 outcome, latency_ms, error_code),
            )
        except sqlite3.Error:
            # The call is more important than the bookkeeping, but a silent miss is how a
            # quota ceiling stops working, so this is an ERROR and not a debug line.
            log.error("could not record the %s call in llm_quota_ledger", purpose,
                      exc_info=True)
            return None
        return ledger_id

    def _capture(self, *, name: str, payload: dict[str, Any]) -> tuple[Path | None, str | None]:
        """Gzip the exact exchange to disk. Atomic: .tmp, then replace.

        This file is what makes "why did the AI say that" answerable three years later, and it
        is written before the response is parsed so an unparseable answer is still on disk.
        """
        try:
            day = report_day()
            directory = self.capture_dir / day
            directory.mkdir(parents=True, exist_ok=True)
            blob = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
            digest = hashlib.sha256(blob).hexdigest()
            path = directory / f"{name}-{digest[:12]}.json.gz"
            tmp = path.with_suffix(path.suffix + ".tmp")
            with gzip.open(tmp, "wb") as handle:
                handle.write(blob)
            tmp.replace(path)
            return path, digest
        except OSError:
            log.error("could not write the LLM capture for %s", name, exc_info=True)
            return None, None


def _as_quota_error(exc: Exception) -> QuotaExhausted | None:
    """Turn a provider 429 into the deferral the job runtime understands.

    A 429 is not a failure: it consumes no attempt, writes no FAILED row and never marks a
    business SKIPPED. Which wall was hit decides how long to wait - a per-minute wall is
    thirty seconds, a per-day wall is the next Pacific midnight.
    """
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc)
    is_429 = code == 429 or "429" in text or "RESOURCE_EXHAUSTED" in text
    if not is_429:
        return None

    retry_after: float | None = None
    match = re.search(r"retryDelay[\"']?\s*[:=]\s*[\"']?(\d+(?:\.\d+)?)s", text)
    if match:
        retry_after = float(match.group(1))

    # A retry delay measured in hours is the daily wall wearing a per-minute error code.
    if retry_after is not None and retry_after < 900:
        return QuotaExhausted(f"rate limited, retry in {retry_after:.0f}s",
                              scope="RPM", retry_after_seconds=retry_after)
    if "PerDay" in text or "per day" in text.lower():
        return QuotaExhausted("the free-tier daily request allowance is spent",
                              scope="RPD", resume_at=next_quota_reset())
    return QuotaExhausted("rate limited by the provider", scope="RPM",
                          retry_after_seconds=retry_after or 30.0)


__all__ = [
    "DEFAULT_MODEL", "GeminiClient", "INJECTION_MARKERS", "LLMError", "LLMNotConfigured",
    "LLMResponse", "LLMResponseInvalid", "PLACEHOLDERS", "PiiHit", "PiiLeak", "QuotaExhausted",
    "RESEARCH_PURPOSES", "assert_no_pii", "find_pii", "neutralise_delimiters",
    "next_quota_reset", "quota_day", "quota_summary", "redact", "report_day", "requests_today",
    "scan_for_injection", "scrub_pii", "wrap_untrusted",
]
