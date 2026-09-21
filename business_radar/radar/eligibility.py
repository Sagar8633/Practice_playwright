"""The one function allowed to answer "may we contact this business, this way, right now?".

Without this module that answer lives in nine different screens and four different WHERE
clauses, and the day one of them drifts is the day a message goes to somebody who asked never
to hear from us again. The grid greys a row out; the preview enables the button; the send job
does its own quick check. Three near-copies of the same rule, each written on a different
afternoon, and the one that disagrees is the one holding the socket.

So there is exactly one evaluator. Every screen that appears to decide is rendering its output,
and the send path calls it a third time inside the write transaction, because between the
preview Sagar read at 11:04 and the send at 11:06 an unsubscribe can land in the mailbox. A
check performed outside that lock is a check performed against a database that is allowed to
change underneath it.

Two properties are load-bearing and neither is an optimisation:

It never writes and never makes a network call. At SEND stage it runs while SQLite's writer
lock is held, and a network call there would hold that lock open across the internet.

It evaluates every gate on every call, even after the first block. An operator who is told one
objection at a time turns fixing a business into whack-a-mole: fix the contact, resubmit, learn
about the frequency window, wait, resubmit, learn about the suppression that was there all
along. `blocking_code` is the first BLOCK in precedence order; `gates` carries all of them.

Precedence runs A to I, and the order is chosen for usefulness to a human rather than for
cheapness: permanent legal facts first, then configuration, then data completeness, then the
per-contact facts, then timing, then channel mechanics, then paperwork.

See 05-outreach-workflow.md sections 5.8 and 5.9 for the catalogue this implements.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal, Sequence

from .models import (
    AutomationMode,
    Channel,
    ContactPolicy,
    parse_ts,
    utc_now,
)

log = logging.getLogger("radar.eligibility")

Stage = Literal["SELECT", "PREVIEW", "SEND"]
Outcome = Literal["PASS", "WARN", "BLOCK", "SKIP"]

STAGES: tuple[str, ...] = ("SELECT", "PREVIEW", "SEND")

#: Which contact kinds a channel is able to carry. Gate E3 is this table, and nothing else.
CHANNEL_CONTACT_KINDS: dict[str, tuple[str, ...]] = {
    "EMAIL": ("EMAIL",),
    "WHATSAPP": ("WHATSAPP", "PHONE"),
    "PHONE": ("PHONE",),
    "MANUAL": ("EMAIL", "PHONE", "WHATSAPP", "WEB_FORM", "OTHER"),
}

#: Message statuses that count as "this address has already been written to".
DELIVERED_FAMILY: tuple[str, ...] = ("SENT", "DELIVERED", "BOUNCED")

#: Statuses that mean another message to this business is already mid-pipeline.
IN_FLIGHT_STATUSES: tuple[str, ...] = ("PENDING_APPROVAL", "APPROVED", "QUEUED")

#: Replies that stop outreach on their own, read from `responses` rather than `suppressions`,
#: so that a failed suppression write is not a silent green light. See gate G5.
REJECTING_CLASSES: tuple[str, ...] = ("NOT_INTERESTED", "ALREADY_HAVE_SOFTWARE")
OPTING_OUT_CLASSES: tuple[str, ...] = ("OPT_OUT", "COMPLAINT")

#: Confidence ranks, for the C4 floor comparison. Never a fourth level.
CONFIDENCE_RANK: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# SIMPLIFIED: gate C4 / C_CONFIDENCE_LOW is requested by 04-verification-workflow.md section
# 4.11.1 and has no config key in radar/config.py. The floor defaults to LOW/0, which passes
# everything; the design's intent is a stricter default once `verify.min_research_confidence`
# exists. Both thresholds are function arguments so a caller can tighten them today.
DEFAULT_MIN_RESEARCH_CONFIDENCE = "LOW"
DEFAULT_MIN_RESEARCH_CONFIDENCE_PCT = 0

# SIMPLIFIED: 05-outreach-workflow.md section 5.9.1 also defines gate D6
# (D_UNREVIEWED_DUPLICATE), which blocks a first touch while an OPEN HIGH-priority
# merge_candidates row names this business. merge_candidates is owned by 01-data-model.md
# section 1.12.6 and is not in 001_schema.sql, so D6 is not evaluated. Adding it is one query
# and one entry in GATE_ORDER once that table lands.
GATE_ORDER: tuple[tuple[str, str], ...] = (
    ("A1", "A_SUPPRESSED_BUSINESS"),
    ("A2", "A_SUPPRESSED_EMAIL"),
    ("A3", "A_SUPPRESSED_PHONE"),
    ("A4", "A_SUPPRESSED_WHATSAPP"),
    ("A5", "A_SUPPRESSED_DOMAIN"),
    ("B1", "B_MODE_NOT_HUMAN_APPROVAL"),
    ("B2", "B_CHANNEL_DISABLED"),
    ("C1", "C_RESEARCH_INCOMPLETE"),
    ("C2", "C_NO_SOURCED_FINDINGS"),
    ("C3", "C_NO_OPPORTUNITY"),
    ("C4", "C_CONFIDENCE_LOW"),
    # D2 is emitted before D1 on purpose: both fire for a REJECTED business, and the sentence
    # Sagar needs is "you rejected this on the 4th", not "this is not verified".
    ("D2", "D_VERIFICATION_REVOKED"),
    ("D1", "D_NOT_VERIFIED"),
    ("D3", "D_VERIFICATION_STALE"),
    ("D4", "D_CHECKLIST_INCOMPLETE"),
    ("D5", "D_HUMAN_OWNED"),
    ("E1", "E_CONTACT_MISSING"),
    ("E2", "E_CONTACT_NOT_VERIFIED"),
    ("E3", "E_CONTACT_CHANNEL_MISMATCH"),
    ("E4", "E_CONTACT_NO_PROVENANCE"),
    ("F1", "F_IN_FLIGHT"),
    ("F2", "F_DUPLICATE_EMAIL"),
    ("F3", "F_DUPLICATE_PHONE"),
    ("F4", "F_DUPLICATE_WHATSAPP"),
    ("F5", "F_DUPLICATE_DOMAIN"),
    ("F6", "F_RECENT_CAMPAIGN"),
    ("F7", "F_PRIOR_RESPONSE"),
    ("G1", "G_MIN_DAYS"),
    ("G1b", "G_SNOOZED"),
    ("G2", "G_MAX_ATTEMPTS"),
    ("G3", "G_MAX_FOLLOWUPS"),
    ("G4", "G_STOP_AFTER_REJECTION"),
    ("G5", "G_STOP_AFTER_OPT_OUT"),
    ("G6", "G_WRONG_CONTACT"),
    ("H1", "H_WHATSAPP_NO_OPTIN"),
    ("H2", "H_EMAIL_REPUTATION"),
    ("H3", "H_DAILY_CAP"),
    ("H4", "H_PHONE_NOT_TRANSMITTABLE"),
    ("H5", "H_NO_UNSUBSCRIBE"),
    ("I1", "I_MESSAGE_STATUS"),
    ("I2", "I_NO_APPROVAL"),
    ("I3", "I_APPROVAL_STALE"),
    ("I4", "I_POLICY_BLOCKED_MESSAGE"),
)

GATE_CODES: dict[str, str] = {gate: code for gate, code in GATE_ORDER}
GATE_INDEX: dict[str, int] = {gate: i for i, (gate, _c) in enumerate(GATE_ORDER)}


class EligibilityError(RuntimeError):
    """The engine was asked something it must refuse rather than guess at."""


# ===========================================================================
# Results
# ===========================================================================


@dataclass(frozen=True)
class GateResult:
    """One gate's answer, and the sentence a human reads when it is the blocking one."""

    gate: str
    code: str
    outcome: str
    sentence: str
    detail: dict[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()

    @property
    def blocks(self) -> bool:
        return self.outcome == "BLOCK"

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "code": self.code,
            "outcome": self.outcome,
            "sentence": self.sentence,
            "detail": self.detail,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GateResult:
        return cls(
            gate=raw["gate"],
            code=raw["code"],
            outcome=raw["outcome"],
            sentence=raw.get("sentence", ""),
            detail=raw.get("detail") or {},
            evidence_ids=tuple(raw.get("evidence_ids") or ()),
        )


@dataclass(frozen=True)
class Eligibility:
    """The whole picture, in precedence order, exactly as it is stored in the snapshots.

    This object is written verbatim into selections.eligibility_snapshot,
    outreach_approvals.eligibility_snapshot and outreach_messages.eligibility_snapshot, so its
    JSON shape is a compatibility surface: gate codes get read by a human out of a stored
    snapshot months later, and renaming one silently changes the meaning of every snapshot
    already on disk.
    """

    business_id: str
    contact_id: str | None
    channel: str | None
    stage: str
    evaluated_at: str
    policy_version: str
    allowed: bool
    blocking_code: str | None
    blocking_sentence: str | None
    gates: tuple[GateResult, ...]
    warnings: tuple[GateResult, ...] = ()
    fingerprint: str = ""

    def gate(self, gate_or_code: str) -> GateResult | None:
        """Look one gate up by its id ('G1') or by its code ('G_MIN_DAYS')."""
        for result in self.gates:
            if result.gate == gate_or_code or result.code == gate_or_code:
                return result
        return None

    def blocked_by(self, gate_or_code: str) -> bool:
        result = self.gate(gate_or_code)
        return result is not None and result.blocks

    @property
    def blocking_gates(self) -> tuple[GateResult, ...]:
        return tuple(g for g in self.gates if g.blocks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "contact_id": self.contact_id,
            "channel": self.channel,
            "stage": self.stage,
            "evaluated_at": self.evaluated_at,
            "policy_version": self.policy_version,
            "allowed": self.allowed,
            "blocking_code": self.blocking_code,
            "blocking_sentence": self.blocking_sentence,
            "fingerprint": self.fingerprint,
            "warnings": [w.to_dict() for w in self.warnings],
            "gates": [g.to_dict() for g in self.gates],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> Eligibility:
        data = json.loads(raw)
        return cls(
            business_id=data["business_id"],
            contact_id=data.get("contact_id"),
            channel=data.get("channel"),
            stage=data.get("stage", "SELECT"),
            evaluated_at=data.get("evaluated_at", ""),
            policy_version=data.get("policy_version", ""),
            allowed=bool(data.get("allowed")),
            blocking_code=data.get("blocking_code"),
            blocking_sentence=data.get("blocking_sentence"),
            gates=tuple(GateResult.from_dict(g) for g in data.get("gates", ())),
            warnings=tuple(GateResult.from_dict(w) for w in data.get("warnings", ())),
            fingerprint=data.get("fingerprint", ""),
        )


def eligibility_fingerprint(gates: Sequence[GateResult]) -> str:
    """sha256 over the (gate, outcome) pairs, in precedence order.

    Two evaluations of the same database state produce the same fingerprint, which is what lets
    the send path notice that the world changed between the preview Sagar approved and the row
    it is about to transmit. It deliberately excludes the sentences and the numbers inside them:
    "9 days since the last message" becoming "10 days" is not a change of decision.
    """
    payload = "\n".join(f"{g.gate}={g.outcome}" for g in gates)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ===========================================================================
# Contact-point normalisation
# ===========================================================================


@dataclass(frozen=True)
class ContactPoint:
    """A contact point in the form every comparison in the system uses."""

    kind: str
    value_norm: str
    value_dedupe: str
    domain: str | None
    display: str
    valid: bool
    error: str | None = None


_WS_RE = re.compile(r"\s+")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DIGITS_RE = re.compile(r"\d+")

# SIMPLIFIED: 05-outreach-workflow.md section 5.9.2 normalises phone numbers with the
# `phonenumbers` library and domains against the public suffix list. Neither is in
# requirements.txt. Phones are normalised for India below; domains keep the last two labels, or
# three when the second-to-last is a known two-part suffix. Both are deliberately
# over-inclusive rather than under-inclusive: when normalisation is ambiguous, blocking wins.
TWO_PART_SUFFIXES: frozenset[str] = frozenset({
    "co.in", "net.in", "org.in", "gen.in", "firm.in", "ind.in", "ac.in", "edu.in", "res.in",
    "gov.in", "nic.in", "mil.in", "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "co.nz",
    "com.sg", "co.za", "com.br",
})


def _nfkc(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip()


def registrable_domain(value: str | None) -> str | None:
    """The eTLD+1 of a URL, a host or an email address. Lowercase, no `www.`, no trailing dot."""
    if not value:
        return None
    text = _nfkc(value).lower()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in text:
        text = text.rsplit("@", 1)[1]
    text = text.split(":", 1)[0].strip(".")
    if text.startswith("www."):
        text = text[4:]
    if not text:
        return None
    if "." not in text:
        return text
    labels = text.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in TWO_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _normalise_phone(raw: str, region_cc: str = "91") -> tuple[str, bool, str | None]:
    """E.164 for an Indian number, plus whether it parsed. Returns (value, valid, error)."""
    text = _nfkc(raw)
    stripped = text.lstrip()
    has_cc = stripped.startswith("+") or stripped.startswith("00")
    digits = "".join(_DIGITS_RE.findall(text))
    if stripped.startswith("00"):
        digits = digits[2:]
    if not digits:
        return ("", False, "there are no digits in this number")
    if not has_cc:
        digits = digits.lstrip("0")
        if len(digits) == 10:
            digits = region_cc + digits
        elif not (len(digits) == 12 and digits.startswith(region_cc)):
            return ("+" + digits, False,
                    f"{len(digits)} digits and no country code; an Indian number has 10")
    if not 8 <= len(digits) <= 15:
        return ("+" + digits, False, f"{len(digits)} digits is not a valid E.164 number")
    if len(digits) == 12 and digits.startswith(region_cc) and digits[2] not in "6789":
        return ("+" + digits, False, "an Indian mobile number starts 6, 7, 8 or 9")
    return ("+" + digits, True, None)


def normalise_contact(kind: str, raw: str, *, region_cc: str = "91") -> ContactPoint:
    """Canonical form of a contact point, plus its registrable domain where one exists.

    Two failure modes fight here. Under-normalising means an opt-out on 'Sales@ABC.IN' fails to
    block 'sales@abc.in' and we mail somebody who told us to stop. Over-normalising means one
    person's opt-out silently blocks a colleague who never asked for anything. When they
    conflict, blocking wins: this function may be over-inclusive and must never be
    under-inclusive.

    `value_norm` is identity - what `suppressions` and `outreach_messages.to_address_norm`
    store. `value_dedupe` is the looser key gate F2 compares, so `sales+leads@abc.in` and
    `sales@abc.in` read as one inbox for duplicate detection while staying two distinct
    addresses for suppression.
    """
    kind = (kind or "").upper()
    display = _nfkc(raw)

    if kind == "EMAIL":
        norm = display.lower()
        if not _EMAIL_RE.match(norm):
            return ContactPoint(kind, norm, norm, registrable_domain(norm), display, False,
                                "this is not a well-formed email address")
        local, _, host = norm.rpartition("@")
        dedupe_local = local.split("+", 1)[0]
        dedupe_host = host
        if host in ("gmail.com", "googlemail.com"):
            dedupe_local = dedupe_local.replace(".", "")
            dedupe_host = "gmail.com"
        return ContactPoint(kind, norm, f"{dedupe_local}@{dedupe_host}",
                            registrable_domain(host), display, True, None)

    if kind in ("PHONE", "WHATSAPP"):
        e164, valid, error = _normalise_phone(display, region_cc)
        norm = e164.lstrip("+") if kind == "WHATSAPP" else e164
        return ContactPoint(kind, norm, norm, None, display, valid, error)

    if kind == "DOMAIN":
        domain = registrable_domain(display)
        if not domain:
            return ContactPoint(kind, "", "", None, display, False, "there is no host in this value")
        return ContactPoint(kind, domain, domain, domain, display, True, None)

    norm = _WS_RE.sub(" ", display).lower()
    return ContactPoint(kind, norm, norm, None, display, bool(norm),
                        None if norm else "this value is empty")


def _keys(row: sqlite3.Row | dict[str, Any] | None) -> set[str]:
    if row is None:
        return set()
    if isinstance(row, dict):
        return set(row)
    return set(row.keys())


def _get(row: sqlite3.Row | dict[str, Any] | None, key: str, default: Any = None) -> Any:
    if row is None or key not in _keys(row):
        return default
    value = row[key]
    return default if value is None else value


def point_from_contact_row(row: sqlite3.Row | dict[str, Any]) -> ContactPoint:
    """The stored normalisation, trusted, not recomputed.

    Normalisation happens once, at capture, and the stored columns are what suppressions and
    sent messages were compared against. Re-normalising here would mean a later change to the
    function silently re-scopes every historical opt-out.
    """
    norm = _get(row, "value_norm", "")
    return ContactPoint(
        kind=_get(row, "kind", "OTHER"),
        value_norm=norm,
        value_dedupe=_get(row, "value_dedupe", norm),
        domain=_get(row, "domain"),
        display=_get(row, "value_display", norm),
        valid=bool(_get(row, "valid", 1)),
        error=_get(row, "invalid_reason"),
    )


# ===========================================================================
# Policy resolution
# ===========================================================================


def effective_policy(conn: sqlite3.Connection, campaign_id: str | None = None) -> ContactPolicy:
    """The GLOBAL policy, tightened by the campaign's row where one exists.

    Stricter always wins. A campaign row that raised the daily cap above the global one would
    make the global setting a suggestion, and the global setting is the thing protecting the
    single Gmail account this system has.
    """
    rows = conn.execute(
        """
        SELECT * FROM contact_policy
         WHERE id = 'GLOBAL'
            OR (scope = 'CAMPAIGN' AND campaign_id = :campaign_id)
         ORDER BY CASE scope WHEN 'GLOBAL' THEN 0 ELSE 1 END
        """,
        {"campaign_id": campaign_id},
    ).fetchall()
    if not rows:
        raise EligibilityError(
            "no contact_policy row: the GLOBAL row is seeded by 001_schema.sql, so an empty "
            "table means this database was never migrated"
        )
    policy = ContactPolicy.from_row(rows[0])
    for row in rows[1:]:
        policy = _tighten(policy, ContactPolicy.from_row(row))
    return policy


def _tighten(base: ContactPolicy, override: ContactPolicy) -> ContactPolicy:
    """Merge a campaign policy onto the global one, taking the stricter value of each field."""
    return ContactPolicy(
        id=override.id,
        scope=override.scope,
        campaign_id=override.campaign_id,
        automation_mode=override.automation_mode,
        min_days_between_outreach=max(base.min_days_between_outreach,
                                      override.min_days_between_outreach),
        max_attempts=min(base.max_attempts, override.max_attempts),
        max_followups=min(base.max_followups, override.max_followups),
        stop_after_rejection=base.stop_after_rejection or override.stop_after_rejection,
        stop_after_opt_out=base.stop_after_opt_out or override.stop_after_opt_out,
        recent_campaign_days=max(base.recent_campaign_days, override.recent_campaign_days),
        same_domain_days=max(base.same_domain_days, override.same_domain_days),
        same_domain_max=min(base.same_domain_max, override.same_domain_max),
        verification_valid_days=min(base.verification_valid_days,
                                    override.verification_valid_days),
        approval_ttl_minutes=min(base.approval_ttl_minutes, override.approval_ttl_minutes),
        send_min_gap_seconds=max(base.send_min_gap_seconds, override.send_min_gap_seconds),
        daily_send_cap=min(base.daily_send_cap, override.daily_send_cap),
        warmup_started_on=override.warmup_started_on or base.warmup_started_on,
        warmup_schedule=override.warmup_schedule or base.warmup_schedule,
        bounce_rate_window_days=max(base.bounce_rate_window_days,
                                    override.bounce_rate_window_days),
        bounce_rate_max_pct=min(base.bounce_rate_max_pct, override.bounce_rate_max_pct),
        complaint_rate_max_pct=min(base.complaint_rate_max_pct,
                                   override.complaint_rate_max_pct),
        bounce_rate_min_sample=min(base.bounce_rate_min_sample,
                                   override.bounce_rate_min_sample),
        email_enabled=base.email_enabled and override.email_enabled,
        email_sending_domain=override.email_sending_domain or base.email_sending_domain,
        whatsapp_enabled=base.whatsapp_enabled and override.whatsapp_enabled,
        whatsapp_api_enabled=base.whatsapp_api_enabled and override.whatsapp_api_enabled,
        phone_enabled=base.phone_enabled and override.phone_enabled,
        manual_enabled=base.manual_enabled and override.manual_enabled,
        policy_version=f"{base.policy_version}+{override.policy_version}",
        updated_at=override.updated_at,
        updated_by=override.updated_by,
    )


def channel_enabled(policy: ContactPolicy, channel: str) -> bool:
    """Is this channel switched on? EMAIL additionally needs its deliberate on-switch."""
    if channel == Channel.EMAIL:
        return policy.email_switch_on
    if channel == Channel.WHATSAPP:
        return policy.whatsapp_enabled
    if channel == Channel.PHONE:
        return policy.phone_enabled
    if channel == Channel.MANUAL:
        return policy.manual_enabled
    return False


def effective_daily_cap(policy: ContactPolicy, today: date) -> int:
    """The warm-up schedule wins while it is running, then the flat cap applies.

    A brand new sending account that emits two hundred messages on day one is an account that
    gets filtered forever. The schedule is a list of per-day caps counted from
    warmup_started_on.
    """
    if not policy.warmup_started_on:
        return policy.daily_send_cap
    try:
        started = date.fromisoformat(str(policy.warmup_started_on)[:10])
    except ValueError:
        log.warning("contact_policy.warmup_started_on is not a date: %r",
                    policy.warmup_started_on)
        return policy.daily_send_cap
    day_index = (today - started).days
    schedule = list(policy.warmup_schedule or ())
    if 0 <= day_index < len(schedule):
        return min(int(schedule[day_index]), policy.daily_send_cap)
    return policy.daily_send_cap


# ===========================================================================
# Time helpers
# ===========================================================================


def _now(now: str | None) -> str:
    return now or utc_now()


def _shift(now_iso: str, *, days: int = 0, minutes: int = 0) -> str:
    moment = parse_ts(now_iso)
    if moment is None:
        raise EligibilityError(f"not one of our timestamps: {now_iso!r}")
    return (moment + timedelta(days=days, minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day_start(now_iso: str) -> str:
    return now_iso[:10] + "T00:00:00Z"


def _age_days(then: str | None, now_iso: str) -> int | None:
    start, end = parse_ts(then), parse_ts(now_iso)
    if start is None or end is None:
        return None
    return (end - start).days


def _age_minutes(then: str | None, now_iso: str) -> int | None:
    start, end = parse_ts(then), parse_ts(now_iso)
    if start is None or end is None:
        return None
    return int((end - start).total_seconds() // 60)


def _on(value: str | None) -> str:
    """A date a human can read, or an honest admission that we did not record one."""
    return (value or "")[:10] or "an unrecorded date"


# ===========================================================================
# The evaluation context
# ===========================================================================


@dataclass
class _Ctx:
    """Everything the gates share, read once."""

    conn: sqlite3.Connection
    business_id: str
    business: sqlite3.Row
    name: str
    contact_id: str | None
    contact: sqlite3.Row | None
    point: ContactPoint | None
    channel: str | None
    stage: str
    campaign_id: str | None
    message_id: str | None
    message: sqlite3.Row | None
    sequence_no: int
    is_followup: bool
    policy: ContactPolicy
    now: str
    min_confidence: str
    min_confidence_pct: int


def _pass(gate: str, sentence: str, detail: dict[str, Any] | None = None) -> GateResult:
    return GateResult(gate, GATE_CODES[gate], "PASS", sentence, detail or {})


def _block(gate: str, sentence: str, detail: dict[str, Any] | None = None,
           evidence: tuple[str, ...] = ()) -> GateResult:
    return GateResult(gate, GATE_CODES[gate], "BLOCK", sentence, detail or {}, evidence)


def _warn(gate: str, sentence: str, detail: dict[str, Any] | None = None,
          evidence: tuple[str, ...] = ()) -> GateResult:
    return GateResult(gate, GATE_CODES[gate], "WARN", sentence, detail or {}, evidence)


def _skip(gate: str, sentence: str) -> GateResult:
    return GateResult(gate, GATE_CODES[gate], "SKIP", sentence, {})


# ===========================================================================
# Gate A - suppression and opt-out (spec section 30)
# ===========================================================================


def contact_points_of(conn: sqlite3.Connection, business_id: str) -> list[dict[str, Any]]:
    """Every point an opt-out could name for this business, active or not.

    Inactive rows are included on purpose: deactivating a contact must not un-say an opt-out.
    The `is_active` flag rides along because the BOUNCE_HARD tier reads it (see gate A).
    """
    points: list[dict[str, Any]] = [
        {"scope": "BUSINESS", "value_norm": business_id, "is_active": True, "display": "this business"}
    ]
    rows = conn.execute(
        """
        SELECT kind, value_norm, value_display, domain, is_active
          FROM business_contacts
         WHERE business_id = ?
        """,
        (business_id,),
    ).fetchall()
    for row in rows:
        if row["kind"] in ("EMAIL", "PHONE", "WHATSAPP") and row["value_norm"]:
            points.append({
                "scope": row["kind"],
                "value_norm": row["value_norm"],
                "is_active": bool(row["is_active"]),
                "display": row["value_display"] or row["value_norm"],
            })
        if row["domain"]:
            points.append({
                "scope": "DOMAIN",
                "value_norm": row["domain"],
                "is_active": bool(row["is_active"]),
                "display": row["domain"],
            })
    website_domain = conn.execute(
        "SELECT website_domain FROM businesses WHERE id = ?", (business_id,)
    ).fetchone()
    if website_domain and website_domain["website_domain"]:
        points.append({
            "scope": "DOMAIN",
            "value_norm": website_domain["website_domain"],
            "is_active": True,
            "display": website_domain["website_domain"],
        })
    return points


def live_suppressions(conn: sqlite3.Connection, business_id: str) -> list[dict[str, Any]]:
    """Every live suppression that touches this business, with the point it matched.

    Note what this does NOT do: it does not filter by the channel being requested. A phone
    opt-out blocks email. That is safety invariant 3, expressed as a missing WHERE clause.
    """
    # SIMPLIFIED: 05-outreach-workflow.md section 5.3.2.1 makes suppressions.value_hmac the
    # identity so an erasure that blanks value_norm cannot resurrect a suppressed address.
    # 001_schema.sql leaves value_hmac nullable and says value_norm is the lookup key until a
    # pepper-storage decision is made, so this joins on value_norm.
    points = contact_points_of(conn, business_id)
    if not points:
        return []
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for point in points:
        key = (point["scope"], point["value_norm"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(point)

    clauses = " OR ".join("(s.scope = ? AND s.value_norm = ?)" for _ in unique)
    params: list[str] = []
    for point in unique:
        params.extend([point["scope"], point["value_norm"]])
    rows = conn.execute(
        f"""
        SELECT s.id, s.scope, s.value_norm, s.reason, s.source, s.source_ref,
               s.created_at, s.erased_at, s.business_id
          FROM suppressions s
         WHERE s.released_at IS NULL AND ({clauses})
         ORDER BY CASE s.scope WHEN 'BUSINESS' THEN 0 WHEN 'DOMAIN' THEN 1 ELSE 2 END,
                  s.created_at
        """,
        params,
    ).fetchall()

    by_key = {(p["scope"], p["value_norm"]): p for p in unique}
    hits: list[dict[str, Any]] = []
    for row in rows:
        point = by_key.get((row["scope"], row["value_norm"]))
        if point is None:
            continue
        # The two-tier rule, 04-verification-workflow.md section 4.3.2. A person who said stop
        # is blocked forever whatever happens to the contact row. A mailbox that bounced is a
        # deliverability fact: it blocks the business only while that dead address is still one
        # of its live contact points, so replacing it restores the business without ever
        # clearing the suppression.
        if row["reason"] == "BOUNCE_HARD" and row["scope"] != "BUSINESS" and not point["is_active"]:
            continue
        hits.append({
            "id": row["id"],
            "scope": row["scope"],
            "value_norm": row["value_norm"],
            "display": point["display"],
            "reason": row["reason"],
            "source": row["source"],
            "source_ref": row["source_ref"],
            "created_at": row["created_at"],
            "erased_at": row["erased_at"],
        })
    return hits


_A_GATE_FOR_SCOPE: dict[str, str] = {
    "BUSINESS": "A1", "EMAIL": "A2", "PHONE": "A3", "WHATSAPP": "A4", "DOMAIN": "A5",
}


def _gate_a(ctx: _Ctx) -> list[GateResult]:
    hits = live_suppressions(ctx.conn, ctx.business_id)
    by_gate: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        by_gate.setdefault(_A_GATE_FOR_SCOPE[hit["scope"]], []).append(hit)

    results: list[GateResult] = []
    for gate in ("A1", "A2", "A3", "A4", "A5"):
        found = by_gate.get(gate)
        if not found:
            results.append(_pass(gate, _A_CLEAR_SENTENCE[gate].format(name=ctx.name)))
            continue
        hit = found[0]
        sentence = _A_BLOCK_SENTENCE[gate].format(
            name=ctx.name,
            value=hit["display"] if not hit["erased_at"] else "a contact since erased on request",
            date=_on(hit["created_at"]),
            reason=hit["reason"],
            source=hit["source"],
        )
        results.append(_block(gate, sentence, {
            "reason": hit["reason"],
            "scope": hit["scope"],
            "created_at": hit["created_at"],
            "source": hit["source"],
            "erased": bool(hit["erased_at"]),
            "matches": len(found),
        }, tuple(h["id"] for h in found)))
    return results


_A_CLEAR_SENTENCE: dict[str, str] = {
    "A1": "No opt-out is on file for {name}.",
    "A2": "No email address at {name} has opted out.",
    "A3": "No number at {name} is on your do-not-contact list.",
    "A4": "No WhatsApp identity at {name} has opted out.",
    "A5": "No domain belonging to {name} is suppressed.",
}

_A_BLOCK_SENTENCE: dict[str, str] = {
    "A1": "{name} opted out on {date} ({reason}) - no channel may be used.",
    "A2": "The address {value} opted out on {date} via {source}, so no email can be sent to it.",
    "A3": "The number {value} has been on your do-not-contact list since {date} ({source}).",
    "A4": "{value} asked to stop receiving WhatsApp messages on {date}.",
    "A5": "Everyone at {value} is suppressed since {date} ({reason}), and that includes {name}.",
}


# ===========================================================================
# Gate B - mode and switches (spec section 46)
# ===========================================================================


def _gate_b(ctx: _Ctx) -> list[GateResult]:
    results: list[GateResult] = []
    mode = ctx.policy.automation_mode
    if mode == AutomationMode.HUMAN_APPROVAL:
        results.append(_pass("B1", "Automation mode is HUMAN_APPROVAL, the only mode v1 transmits under.",
                             {"automation_mode": mode}))
    else:
        results.append(_block("B1",
                              f"Automation mode is {mode}; v1 only transmits under HUMAN_APPROVAL.",
                              {"automation_mode": mode}))

    if ctx.channel is None:
        results.append(_skip("B2", "Which channel is used has not been chosen yet."))
    elif ctx.stage == "SELECT":
        results.append(_skip("B2", "The channel switch is checked at preview."))
    elif channel_enabled(ctx.policy, ctx.channel):
        results.append(_pass("B2", f"The {ctx.channel} channel is switched on.",
                             {"channel": ctx.channel}))
    else:
        detail = {"channel": ctx.channel}
        if ctx.channel == Channel.EMAIL and not ctx.policy.email_sending_domain:
            sentence = ("No sending account is configured, so the EMAIL channel is off until "
                        "somebody sets it in Settings.")
            detail["email_sending_domain"] = None
        else:
            sentence = f"The {ctx.channel} channel is switched off in Settings."
        results.append(_block("B2", sentence, detail))
    return results


# ===========================================================================
# Gate C - research complete, and confidence adequate
# ===========================================================================

GATE_C_SQL = """
SELECT
  (SELECT r.id FROM research_runs r
    WHERE r.business_id = :business_id AND r.status = 'COMPLETE'
    ORDER BY r.finished_at DESC LIMIT 1)                              AS run_id,
  (SELECT r.finished_at FROM research_runs r
    WHERE r.business_id = :business_id AND r.status = 'COMPLETE'
    ORDER BY r.finished_at DESC LIMIT 1)                              AS run_finished_at,
  (SELECT COUNT(*) FROM research_findings f
     JOIN finding_sources fs ON fs.finding_id = f.id
    WHERE f.business_id = :business_id AND f.kind = 'OBSERVED')       AS observed_sourced,
  (SELECT COUNT(*) FROM research_findings f
    WHERE f.business_id = :business_id)                               AS findings_total,
  (SELECT o.id FROM opportunities o
    WHERE o.business_id = :business_id AND o.is_current = 1)          AS opportunity_id,
  (SELECT o.score FROM opportunities o
    WHERE o.business_id = :business_id AND o.is_current = 1)          AS opportunity_score,
  (SELECT o.confidence FROM opportunities o
    WHERE o.business_id = :business_id AND o.is_current = 1)          AS opportunity_confidence,
  (SELECT o.confidence_pct FROM opportunities o
    WHERE o.business_id = :business_id AND o.is_current = 1)          AS opportunity_confidence_pct
"""


def _gate_c(ctx: _Ctx) -> list[GateResult]:
    row = ctx.conn.execute(GATE_C_SQL, {"business_id": ctx.business_id}).fetchone()
    results: list[GateResult] = []

    if row["run_id"]:
        results.append(_pass("C1", f"Research for {ctx.name} finished on {_on(row['run_finished_at'])}.",
                             {"research_run_id": row["run_id"]},))
    else:
        results.append(_block("C1",
                              f"Research for {ctx.name} has not finished - there is nothing to "
                              f"write a message from.",
                              {"findings_total": row["findings_total"]}))

    # C2 is what makes safety invariant 4 achievable rather than aspirational: with no sourced
    # observation there is nothing the message is permitted to state, so there is no message.
    if row["observed_sourced"]:
        results.append(_pass("C2",
                             f"{row['observed_sourced']} observed, sourced facts are on file for {ctx.name}.",
                             {"observed_sourced": row["observed_sourced"]}))
    else:
        results.append(_block("C2",
                              f"No observed, sourced fact exists for {ctx.name}, so any message "
                              f"would be guesswork.",
                              {"observed_sourced": 0, "findings_total": row["findings_total"]}))

    if row["opportunity_id"]:
        results.append(_pass("C3",
                             f"{ctx.name} scores {row['opportunity_score']} out of 100.",
                             {"opportunity_id": row["opportunity_id"],
                              "score": row["opportunity_score"]}))
    else:
        results.append(_block("C3", f"No opportunity has been scored for {ctx.name}.", {}))

    confidence = row["opportunity_confidence"]
    confidence_pct = row["opportunity_confidence_pct"]
    floor = CONFIDENCE_RANK.get(ctx.min_confidence, 0)
    detail = {
        "confidence": confidence,
        "confidence_pct": confidence_pct,
        "min_confidence": ctx.min_confidence,
        "min_confidence_pct": ctx.min_confidence_pct,
    }
    if confidence is None:
        results.append(_skip("C4", "There is no scored opportunity to read a confidence from."))
    elif (CONFIDENCE_RANK.get(confidence, 0) >= floor
          and (confidence_pct is None or confidence_pct >= ctx.min_confidence_pct)):
        results.append(_pass("C4", f"Research confidence for {ctx.name} is {confidence}.", detail))
    else:
        results.append(_block("C4",
                              f"Research confidence for {ctx.name} is {confidence}, below your "
                              f"{ctx.min_confidence} floor.",
                              detail))
    return results


# ===========================================================================
# Gate D - verification current (spec sections 15, 16, 17)
# ===========================================================================

GATE_D_SQL = """
SELECT b.status                                                       AS business_status,
       b.status_changed_at,
       b.contact_ready_block_code,
       v.id                                                           AS verification_id,
       v.verified_at, v.verified_by, v.verdict,
       v.checks_passed, v.checks_failed, v.checks_total
  FROM businesses b
  LEFT JOIN verifications v
         ON v.business_id   = b.id
        AND v.state         = 'SUBMITTED'
        AND v.verdict       = 'VERIFIED'
        AND v.superseded_at IS NULL
 WHERE b.id = :business_id
"""


def _gate_d(ctx: _Ctx) -> list[GateResult]:
    row = ctx.conn.execute(GATE_D_SQL, {"business_id": ctx.business_id}).fetchone()
    if row is None:
        raise EligibilityError(f"no businesses row for {ctx.business_id!r}")
    status = row["business_status"]
    changed = row["status_changed_at"]
    limit = ctx.policy.verification_valid_days
    results: list[GateResult] = []

    if status in ("REJECTED", "SKIPPED"):
        results.append(_block("D2", f"You marked {ctx.name} {status} on {_on(changed)}.",
                              {"status": status, "at": changed}))
    else:
        results.append(_pass("D2", f"{ctx.name} has not been rejected or parked.",
                             {"status": status}))

    if status in ("CONTACT_READY", "CONTACTED", "RESPONDED"):
        results.append(_pass("D1", f"{ctx.name} is {status}.", {"status": status}))
    elif status == "VERIFIED" and row["contact_ready_block_code"]:
        # 04 section 4.3.6: a business held back by a non-verification clause stays VERIFIED,
        # and saying "not verified" here would be the one wrong sentence on an accurate screen.
        results.append(_block("D1",
                              f"{ctx.name} is verified but held out of the outreach pool "
                              f"({row['contact_ready_block_code']}).",
                              {"status": status,
                               "contact_ready_block_code": row["contact_ready_block_code"]}))
    else:
        results.append(_block("D1", f"{ctx.name} is {status} - verify it before preparing outreach.",
                              {"status": status}))

    verification_id = row["verification_id"]
    age = _age_days(row["verified_at"], ctx.now)
    if verification_id is None:
        results.append(_block("D3", f"There is no live verification on file for {ctx.name}.",
                              {"verification_valid_days": limit}))
        results.append(_block("D4", f"The nine verification checks have not been completed for {ctx.name}.",
                              {"checks_passed": 0, "checks_total": 9}))
    else:
        evidence = (verification_id,)
        if age is not None and age > limit:
            results.append(_block("D3",
                                  f"Your verification of {ctx.name} is {age} days old "
                                  f"(limit {limit}) - re-verify it.",
                                  {"age_days": age, "verification_valid_days": limit,
                                   "verified_at": row["verified_at"]}, evidence))
        else:
            results.append(_pass("D3",
                                 f"You verified {ctx.name} on {_on(row['verified_at'])}, "
                                 f"{age} days ago.",
                                 {"age_days": age, "verification_valid_days": limit}))
        passed = row["checks_passed"] or 0
        total = row["checks_total"] or 9
        if passed < 9 or (row["checks_failed"] or 0) > 0:
            results.append(_block("D4",
                                  f"{9 - passed} of the nine verification checks were not "
                                  f"ticked for {ctx.name}.",
                                  {"checks_passed": passed, "checks_total": total}, evidence))
        else:
            results.append(_pass("D4", "All nine verification checks were ticked.",
                                 {"checks_passed": passed, "checks_total": total}))

    if status in ("INTERESTED", "HUMAN_HANDOFF"):
        results.append(_block("D5",
                              f"{ctx.name} is a live lead you are handling personally - "
                              f"the system stops here.",
                              {"status": status}))
    else:
        results.append(_pass("D5", f"{ctx.name} is not a live lead under personal handling.",
                             {"status": status}))
    return results


# ===========================================================================
# Gate E - contact present and human-verified
# ===========================================================================


def _gate_e(ctx: _Ctx) -> list[GateResult]:
    usable = ctx.conn.execute(
        """
        SELECT COUNT(*) AS n FROM business_contacts
         WHERE business_id = ? AND human_verified = 1 AND is_active = 1
           AND valid = 1 AND value_norm IS NOT NULL AND value_norm <> ''
        """,
        (ctx.business_id,),
    ).fetchone()["n"]

    results: list[GateResult] = []
    if usable:
        results.append(_pass("E1", f"{ctx.name} has {usable} confirmed contact(s) to write to.",
                             {"usable_contacts": usable}))
    else:
        results.append(_block("E1", f"{ctx.name} has no confirmed contact to write to.",
                              {"usable_contacts": 0}))

    contact = ctx.contact
    if contact is None:
        reason = ("No contact has been chosen yet; this is checked at preview."
                  if ctx.stage == "SELECT" else
                  "No contact was supplied with this request.")
        for gate in ("E2", "E3", "E4"):
            results.append(_skip(gate, reason) if ctx.stage == "SELECT"
                           else _block(gate, reason, {"contact_id": None}))
        return results

    display = contact["value_display"] or contact["value_norm"]
    evidence = (contact["id"],)

    if contact["human_verified"] and contact["is_active"]:
        results.append(_pass("E2", f"You confirmed {display} as a contact for {ctx.name}.",
                             {"human_verified": True}, ))
    else:
        results.append(_block("E2",
                              f"You have not confirmed that {display} is a legitimate business "
                              f"contact for {ctx.name}.",
                              {"human_verified": bool(contact["human_verified"]),
                               "is_active": bool(contact["is_active"])}, evidence))

    e3 = _gate_e3(ctx, contact, display)
    results.append(e3)

    role_address = bool(contact["is_role_address"])
    has_provenance = bool(contact["source_ref"] or contact["source_url"] or contact["source_id"])
    if has_provenance:
        results.append(_pass("E4", f"We recorded where {display} came from.",
                             {"is_role_address": role_address}))
    elif role_address:
        # A role address published on a business's own site is business contact data rather
        # than personal data, so its missing provenance is a warning, not a block.
        results.append(_warn("E4",
                             f"There is no record of where {display} came from, though it is a "
                             f"role address rather than a named person.",
                             {"is_role_address": True}, evidence))
    elif ctx.stage == "SELECT":
        results.append(_warn("E4",
                             f"There is no record of where {display} came from, and we need one "
                             f"before writing to a named person.",
                             {"is_role_address": False}, evidence))
    else:
        results.append(_block("E4",
                              f"There is no record of where {display} came from, and we need one "
                              f"before writing to a named person.",
                              {"is_role_address": False}, evidence))
    return results


def _gate_e3(ctx: _Ctx, contact: sqlite3.Row, display: str) -> GateResult:
    evidence = (contact["id"],)
    # Not paranoia: this is the check that stops a stale contact_id in a resubmitted form from
    # addressing one business's message to another business's inbox.
    if contact["business_id"] != ctx.business_id:
        return _block("E3", f"{display} belongs to a different business.",
                      {"contact_business_id": contact["business_id"]}, evidence)
    if ctx.channel is None:
        return _skip("E3", "No channel has been chosen yet.")
    allowed_kinds = CHANNEL_CONTACT_KINDS.get(ctx.channel, ())
    if contact["kind"] not in allowed_kinds:
        return _block("E3", f"{display} cannot be used for {ctx.channel}.",
                      {"kind": contact["kind"], "channel": ctx.channel,
                       "allowed_kinds": list(allowed_kinds)}, evidence)
    if not contact["valid"] or not (contact["value_norm"] or "").strip():
        return _block("E3", f"{display} did not parse as a usable {contact['kind']}.",
                      {"invalid_reason": contact["invalid_reason"]}, evidence)
    if (ctx.channel == Channel.WHATSAPP and contact["kind"] == "PHONE"
            and not contact["whatsapp_capable"]):
        return _block("E3", f"{display} is not known to be on WhatsApp.",
                      {"whatsapp_capability": contact["wa_capability"]}, evidence)
    return _pass("E3", f"{display} is a usable {ctx.channel} contact.",
                 {"kind": contact["kind"], "channel": ctx.channel})


# ===========================================================================
# Gate F - duplicate contact protection (spec section 29)
# ===========================================================================

GATE_F_SQL = """
SELECT 'F1' AS probe, COUNT(*) AS hits, MAX(m.updated_at) AS last_at,
       MAX(m.id) AS sample_id, NULL AS extra
  FROM outreach_messages m
 WHERE m.business_id = :business_id
   AND m.status IN ('PENDING_APPROVAL','APPROVED','QUEUED')
   AND (:message_id IS NULL OR m.id <> :message_id)
UNION ALL
SELECT 'F2', COUNT(*), MAX(m.sent_at), MAX(m.id), NULL
  FROM outreach_messages m
 WHERE m.channel = 'EMAIL'
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :dup_cutoff
   AND :contact_norm IS NOT NULL
   AND (m.to_address_norm = :contact_norm OR m.to_address_dedupe = :contact_dedupe)
UNION ALL
SELECT 'F3', COUNT(*), MAX(m.sent_at), MAX(m.id), NULL
  FROM outreach_messages m
 WHERE m.channel IN ('PHONE','MANUAL')
   AND m.status IN ('SENT','DELIVERED')
   AND m.sent_at >= :dup_cutoff
   AND :contact_norm IS NOT NULL
   AND m.to_address_norm = :contact_norm
UNION ALL
SELECT 'F4', COUNT(*), MAX(m.sent_at), MAX(m.id), NULL
  FROM outreach_messages m
 WHERE m.channel = 'WHATSAPP'
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :dup_cutoff
   AND :contact_norm IS NOT NULL
   AND m.to_address_norm = :contact_norm
UNION ALL
SELECT 'F5', COUNT(DISTINCT m.to_address_norm), MAX(m.sent_at), MAX(m.id),
       GROUP_CONCAT(DISTINCT m.business_id)
  FROM outreach_messages m
 WHERE :contact_domain IS NOT NULL
   AND m.recipient_domain = :contact_domain
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :domain_cutoff
   AND (m.to_address_norm IS NULL OR m.to_address_norm <> :contact_norm)
UNION ALL
SELECT 'F6', COUNT(*), MAX(m.sent_at), MAX(m.campaign_id), NULL
  FROM outreach_messages m
 WHERE m.business_id = :business_id
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :recent_campaign_cutoff
   AND (:campaign_id IS NULL OR m.campaign_id <> :campaign_id)
UNION ALL
SELECT 'F7', COUNT(*), MAX(r.received_at), MAX(r.id),
       (SELECT r2.classification FROM responses r2
         WHERE r2.business_id = :business_id
         ORDER BY r2.received_at DESC LIMIT 1)
  FROM responses r
 WHERE r.business_id = :business_id
"""


def _gate_f(ctx: _Ctx) -> list[GateResult]:
    policy = ctx.policy
    params = {
        "business_id": ctx.business_id,
        "campaign_id": ctx.campaign_id,
        "message_id": ctx.message_id,
        "contact_norm": ctx.point.value_norm if ctx.point else None,
        "contact_dedupe": ctx.point.value_dedupe if ctx.point else None,
        "contact_domain": ctx.point.domain if ctx.point else None,
        "dup_cutoff": _shift(ctx.now, days=-policy.min_days_between_outreach),
        "domain_cutoff": _shift(ctx.now, days=-policy.same_domain_days),
        "recent_campaign_cutoff": _shift(ctx.now, days=-policy.recent_campaign_days),
    }
    probes = {r["probe"]: r for r in ctx.conn.execute(GATE_F_SQL, params).fetchall()}
    results: list[GateResult] = []

    f1 = probes["F1"]
    if f1["hits"]:
        results.append(_block("F1", f"Another message to {ctx.name} is already waiting to go out.",
                              {"in_flight": f1["hits"]}, (f1["sample_id"],)))
    else:
        results.append(_pass("F1", f"No other message to {ctx.name} is in flight.", {"in_flight": 0}))

    # A follow-up with a parent message is exempt from the address-level windows and hands the
    # timing decision to gate G1. Without this exemption no second message could ever reach the
    # same address and max_followups would be unreachable.
    exempt = ctx.is_followup
    per_contact = (("F2", "EMAIL"), ("F3", "PHONE"), ("F4", "WHATSAPP"))
    for gate, label in per_contact:
        row = probes[gate]
        if ctx.point is None:
            results.append(_skip(gate, "No contact has been chosen yet."))
            continue
        if exempt:
            results.append(_pass(gate,
                                 f"This is follow-up {ctx.sequence_no}; the duplicate window "
                                 f"does not apply and gate G1 sets the timing.",
                                 {"sequence_no": ctx.sequence_no, "exempt": True}))
            continue
        if row["hits"]:
            results.append(_block(gate,
                                  f"{ctx.point.display} was already contacted on "
                                  f"{_on(row['last_at'])}, inside your "
                                  f"{policy.min_days_between_outreach}-day window.",
                                  {"hits": row["hits"], "last_at": row["last_at"],
                                   "window_days": policy.min_days_between_outreach},
                                  (row["sample_id"],)))
        else:
            results.append(_pass(gate,
                                 f"{ctx.point.display} has not been contacted inside your "
                                 f"{policy.min_days_between_outreach}-day window.",
                                 {"hits": 0, "channel_family": label}))

    f5 = probes["F5"]
    if ctx.point is None or not ctx.point.domain:
        results.append(_skip("F5", "There is no domain on this contact to count colleagues at."))
    elif ctx.stage == "SELECT":
        results.append(_skip("F5", "The per-domain count is checked at preview."))
    elif f5["hits"] >= policy.same_domain_max:
        # Deliberately spans businesses: a hospital and its diagnostic arm sharing one domain
        # are two businesses rows and one inbox culture.
        results.append(_block("F5",
                              f"{f5['hits']} people at {ctx.point.domain} have already been "
                              f"contacted since {_on(params['domain_cutoff'])} "
                              f"(your limit is {policy.same_domain_max}).",
                              {"hits": f5["hits"], "max": policy.same_domain_max,
                               "since": params["domain_cutoff"],
                               "businesses": (f5["extra"] or "").split(",") if f5["extra"] else []},
                              (f5["sample_id"],) if f5["sample_id"] else ()))
    else:
        results.append(_pass("F5",
                             f"{f5['hits']} of your limit of {policy.same_domain_max} addresses "
                             f"at {ctx.point.domain} have been contacted recently.",
                             {"hits": f5["hits"], "max": policy.same_domain_max}))

    f6 = probes["F6"]
    if exempt:
        results.append(_pass("F6", "This is a follow-up in an existing thread.",
                             {"exempt": True}))
    elif f6["hits"]:
        results.append(_block("F6",
                              f"{ctx.name} was contacted on {_on(f6['last_at'])} in another "
                              f"campaign, inside your {policy.recent_campaign_days}-day window.",
                              {"hits": f6["hits"], "last_at": f6["last_at"],
                               "other_campaign_id": f6["sample_id"],
                               "window_days": policy.recent_campaign_days}))
    else:
        results.append(_pass("F6", f"No other campaign has written to {ctx.name} recently.",
                             {"hits": 0}))

    f7 = probes["F7"]
    if f7["hits"]:
        results.append(_warn("F7",
                             f"{ctx.name} has replied before ({f7['extra']} on "
                             f"{_on(f7['last_at'])}) - read the thread before sending again.",
                             {"responses": f7["hits"], "classification": f7["extra"],
                              "received_at": f7["last_at"]},
                             (f7["sample_id"],) if f7["sample_id"] else ()))
    else:
        results.append(_pass("F7", f"{ctx.name} has never replied.", {"responses": 0}))
    return results


# ===========================================================================
# Gate G - contact frequency policy (spec section 31)
# ===========================================================================

GATE_G_SQL = """
SELECT
  (SELECT COUNT(*) FROM outreach_messages m
    WHERE m.business_id = :business_id
      AND m.status IN ('SENT','DELIVERED','BOUNCED'))                     AS attempts,
  (SELECT COUNT(*) FROM outreach_messages m
    WHERE m.business_id = :business_id
      AND m.status IN ('SENT','DELIVERED','BOUNCED')
      AND m.sequence_no > 1)                                              AS followups,
  (SELECT MAX(m.sent_at) FROM outreach_messages m
    WHERE m.business_id = :business_id
      AND m.status IN ('SENT','DELIVERED','BOUNCED'))                     AS last_sent_at,
  (SELECT m.id FROM outreach_messages m
    WHERE m.business_id = :business_id
      AND m.status IN ('SENT','DELIVERED','BOUNCED')
    ORDER BY m.sent_at DESC LIMIT 1)                                      AS last_message_id,
  (SELECT COALESCE(r.human_classification, r.classification) FROM responses r
    WHERE r.business_id = :business_id
      AND COALESCE(r.human_classification, r.classification)
          IN ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE')
    ORDER BY r.received_at LIMIT 1)                                       AS reject_class,
  (SELECT r.received_at FROM responses r
    WHERE r.business_id = :business_id
      AND COALESCE(r.human_classification, r.classification)
          IN ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE')
    ORDER BY r.received_at LIMIT 1)                                       AS reject_at,
  (SELECT r.id FROM responses r
    WHERE r.business_id = :business_id
      AND COALESCE(r.human_classification, r.classification)
          IN ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE')
    ORDER BY r.received_at LIMIT 1)                                       AS reject_id,
  (SELECT r.received_at FROM responses r
    WHERE r.business_id = :business_id
      AND COALESCE(r.human_classification, r.classification) IN ('OPT_OUT','COMPLAINT')
    ORDER BY r.received_at LIMIT 1)                                       AS optout_at,
  (SELECT r.id FROM responses r
    WHERE r.business_id = :business_id
      AND COALESCE(r.human_classification, r.classification) IN ('OPT_OUT','COMPLAINT')
    ORDER BY r.received_at LIMIT 1)                                       AS optout_id,
  (SELECT COUNT(*) FROM responses r
    WHERE r.business_id = :business_id
      AND COALESCE(r.human_classification, r.classification) = 'WRONG_CONTACT'
      AND :contact_id IS NOT NULL AND r.contact_id = :contact_id)         AS wrong_contact_hits,
  (SELECT r.received_at FROM responses r
    WHERE r.business_id = :business_id
      AND COALESCE(r.human_classification, r.classification) = 'WRONG_CONTACT'
      AND :contact_id IS NOT NULL AND r.contact_id = :contact_id
    ORDER BY r.received_at DESC LIMIT 1)                                  AS wrong_contact_at,
  (SELECT r.snooze_until FROM responses r
    WHERE r.business_id = :business_id AND r.snooze_until IS NOT NULL
    ORDER BY r.received_at DESC LIMIT 1)                                  AS snooze_until
"""


def _gate_g(ctx: _Ctx) -> list[GateResult]:
    policy = ctx.policy
    row = ctx.conn.execute(
        GATE_G_SQL, {"business_id": ctx.business_id, "contact_id": ctx.contact_id}
    ).fetchone()
    results: list[GateResult] = []

    days_since = _age_days(row["last_sent_at"], ctx.now)
    if row["last_sent_at"] is None:
        results.append(_pass("G1", f"{ctx.name} has never been contacted.", {"last_sent_at": None}))
    elif days_since is not None and days_since < policy.min_days_between_outreach:
        results.append(_block("G1",
                              f"It has been {days_since} days since the last message to "
                              f"{ctx.name}; your minimum is "
                              f"{policy.min_days_between_outreach}.",
                              {"days_since": days_since,
                               "min_days": policy.min_days_between_outreach,
                               "last_sent_at": row["last_sent_at"]},
                              (row["last_message_id"],) if row["last_message_id"] else ()))
    else:
        results.append(_pass("G1",
                             f"The last message to {ctx.name} went out {days_since} days ago.",
                             {"days_since": days_since,
                              "min_days": policy.min_days_between_outreach}))

    snooze = row["snooze_until"]
    if snooze and snooze > ctx.now:
        results.append(_block("G1b", f"{ctx.name} asked you to come back after {_on(snooze)}.",
                              {"snooze_until": snooze}))
    else:
        results.append(_pass("G1b", f"{ctx.name} has not asked you to come back later.",
                             {"snooze_until": snooze}))

    attempts = row["attempts"] or 0
    if attempts >= policy.max_attempts:
        results.append(_block("G2",
                              f"{ctx.name} has already had {attempts} messages; your maximum "
                              f"is {policy.max_attempts}.",
                              {"attempts": attempts, "max_attempts": policy.max_attempts}))
    else:
        results.append(_pass("G2",
                             f"{ctx.name} has had {attempts} of a maximum "
                             f"{policy.max_attempts} messages.",
                             {"attempts": attempts, "max_attempts": policy.max_attempts}))

    followups = row["followups"] or 0
    if followups >= policy.max_followups and attempts > 0:
        results.append(_block("G3",
                              f"{ctx.name} has had {followups} follow-ups; your maximum is "
                              f"{policy.max_followups}.",
                              {"followups": followups, "max_followups": policy.max_followups}))
    else:
        results.append(_pass("G3",
                             f"{ctx.name} has had {followups} of a maximum "
                             f"{policy.max_followups} follow-ups.",
                             {"followups": followups, "max_followups": policy.max_followups}))

    if policy.stop_after_rejection and row["reject_class"]:
        results.append(_block("G4",
                              f"{ctx.name} replied {row['reject_class']} on "
                              f"{_on(row['reject_at'])}, and your policy stops outreach after "
                              f"a rejection.",
                              {"classification": row["reject_class"],
                               "received_at": row["reject_at"]},
                              (row["reject_id"],) if row["reject_id"] else ()))
    else:
        results.append(_pass("G4", f"{ctx.name} has not turned you down.",
                             {"stop_after_rejection": policy.stop_after_rejection}))

    # Deliberately redundant against gate A. Gate A reads suppressions; G5 reads responses. If
    # the classifier wrote an OPT_OUT row and the suppression write failed - disk full, a worker
    # killed between two statements - gate A goes quiet and G5 is the second lock on that door.
    if policy.stop_after_opt_out and row["optout_at"]:
        results.append(_block("G5", f"{ctx.name} asked to be removed on {_on(row['optout_at'])}.",
                              {"received_at": row["optout_at"]},
                              (row["optout_id"],) if row["optout_id"] else ()))
    else:
        results.append(_pass("G5", f"{ctx.name} has not asked to be removed.",
                             {"stop_after_opt_out": policy.stop_after_opt_out}))

    if ctx.contact_id is None:
        results.append(_skip("G6", "No contact has been chosen yet."))
    elif row["wrong_contact_hits"]:
        display = ctx.point.display if ctx.point else ctx.contact_id
        results.append(_block("G6",
                              f"Someone at {ctx.name} told us on "
                              f"{_on(row['wrong_contact_at'])} that {display} is the wrong "
                              f"contact.",
                              {"hits": row["wrong_contact_hits"],
                               "received_at": row["wrong_contact_at"]}))
    else:
        results.append(_pass("G6", "Nobody has told us this is the wrong contact.", {"hits": 0}))
    return results


# ===========================================================================
# Gate H - channel-specific policy
# ===========================================================================

GATE_H_REPUTATION_SQL = """
SELECT
  (SELECT COUNT(*) FROM outreach_messages m
    WHERE m.channel = 'EMAIL' AND m.status IN ('SENT','DELIVERED','BOUNCED')
      AND m.sent_at >= :window_start)                                     AS n_sent,
  (SELECT COUNT(*) FROM outreach_messages m
    WHERE m.channel = 'EMAIL' AND m.status = 'BOUNCED'
      AND m.sent_at >= :window_start)                                     AS n_bounced,
  (SELECT COUNT(*) FROM responses r
    WHERE COALESCE(r.human_classification, r.classification) = 'COMPLAINT'
      AND r.received_at >= :window_start)                                 AS n_complained,
  (SELECT COUNT(*) FROM outreach_messages m
    WHERE m.channel = 'EMAIL' AND m.status IN ('SENT','DELIVERED','BOUNCED')
      AND m.sent_at >= :day_start)                                        AS sent_today
"""


def _gate_h(ctx: _Ctx) -> list[GateResult]:
    policy = ctx.policy
    results: list[GateResult] = []
    channel = ctx.channel

    if channel is None or ctx.stage == "SELECT":
        why = ("No channel has been chosen yet." if channel is None
               else "Channel mechanics are checked at preview.")
        return [_skip(gate, why) for gate in ("H1", "H2", "H3", "H4", "H5")]

    # H1 - WhatsApp opt-in. Business-initiated WhatsApp needs a recorded opt-in; without one
    # the honest path is a wa.me link Sagar sends from his own phone.
    if channel != Channel.WHATSAPP:
        results.append(_skip("H1", "This is not a WhatsApp message."))
    else:
        optin = _get(ctx.contact, "whatsapp_optin_at")
        if optin:
            results.append(_pass("H1", f"{ctx.name} opted in to WhatsApp on {_on(optin)}.",
                                 {"whatsapp_optin_at": optin}))
        elif policy.whatsapp_api_enabled:
            results.append(_block("H1",
                                  f"{ctx.name} never opted in to WhatsApp, so the Cloud API "
                                  f"may not be used - send this one from your own phone.",
                                  {"whatsapp_api_enabled": True}))
        else:
            results.append(_warn("H1",
                                 f"{ctx.name} never opted in to WhatsApp, so this one has to "
                                 f"go from your own phone.",
                                 {"whatsapp_api_enabled": False}))

    if channel != Channel.EMAIL:
        results.append(_skip("H2", "Sending reputation only applies to email."))
        results.append(_skip("H3", "The daily cap only applies to email."))
    else:
        rep = ctx.conn.execute(GATE_H_REPUTATION_SQL, {
            "window_start": _shift(ctx.now, days=-policy.bounce_rate_window_days),
            "day_start": _day_start(ctx.now),
        }).fetchone()
        n_sent = rep["n_sent"] or 0
        bounce_pct = (100.0 * (rep["n_bounced"] or 0) / n_sent) if n_sent else 0.0
        complaint_pct = (100.0 * (rep["n_complained"] or 0) / n_sent) if n_sent else 0.0
        detail = {
            "n_sent": n_sent,
            "n_bounced": rep["n_bounced"] or 0,
            "n_complained": rep["n_complained"] or 0,
            "bounce_pct": round(bounce_pct, 2),
            "complaint_pct": round(complaint_pct, 2),
            "bounce_rate_max_pct": policy.bounce_rate_max_pct,
            "complaint_rate_max_pct": policy.complaint_rate_max_pct,
            "min_sample": policy.bounce_rate_min_sample,
            "window_days": policy.bounce_rate_window_days,
        }
        # Under the minimum sample one bad address in three is 33% and means nothing.
        if n_sent < policy.bounce_rate_min_sample:
            results.append(_pass("H2",
                                 f"Only {n_sent} emails in the last "
                                 f"{policy.bounce_rate_window_days} days - too few to judge "
                                 f"deliverability by.",
                                 detail))
        elif bounce_pct > policy.bounce_rate_max_pct:
            results.append(_block("H2",
                                  f"Email sending is paused: {bounce_pct:.1f}% of the last "
                                  f"{n_sent} messages bounced (limit "
                                  f"{policy.bounce_rate_max_pct}%).",
                                  detail))
        elif complaint_pct > policy.complaint_rate_max_pct:
            results.append(_block("H2",
                                  f"Email sending is paused: {complaint_pct:.2f}% of the last "
                                  f"{n_sent} messages drew a complaint (limit "
                                  f"{policy.complaint_rate_max_pct}%).",
                                  detail))
        else:
            results.append(_pass("H2",
                                 f"{bounce_pct:.1f}% of the last {n_sent} emails bounced, "
                                 f"under your {policy.bounce_rate_max_pct}% limit.",
                                 detail))

        sent_today = rep["sent_today"] or 0
        cap = effective_daily_cap(policy, date.fromisoformat(ctx.now[:10]))
        cap_detail = {"sent_today": sent_today, "cap": cap,
                      "daily_send_cap": policy.daily_send_cap,
                      "warmup_started_on": policy.warmup_started_on}
        # H3 is the one gate whose block means "later", not "no": a message stopped here is
        # held, not cancelled.
        if sent_today >= cap:
            results.append(_block("H3",
                                  f"You have sent {sent_today} of today's {cap} emails - this "
                                  f"one goes out tomorrow.",
                                  cap_detail))
        elif cap and sent_today >= 0.9 * cap:
            results.append(_warn("H3",
                                 f"You have sent {sent_today} of today's {cap} emails.",
                                 cap_detail))
        else:
            results.append(_pass("H3",
                                 f"You have sent {sent_today} of today's {cap} emails.",
                                 cap_detail))

    if channel == Channel.PHONE:
        # Always a warning, never a silent pass: its whole job is to put "the system will never
        # dial" on screen so the operator's expectation matches the code.
        results.append(_warn("H4",
                             "This is a call script - the system will never dial; log the call "
                             "once you have made it.",
                             {"channel": channel}))
    else:
        results.append(_skip("H4", "This is not a phone script."))

    if channel != Channel.EMAIL:
        results.append(_skip("H5", "Unsubscribe headers only apply to email."))
    elif policy.email_sending_domain:
        results.append(_pass("H5",
                             f"Outbound mail carries a working mailto: unsubscribe on "
                             f"{policy.email_sending_domain}.",
                             {"email_sending_domain": policy.email_sending_domain}))
    else:
        # SIMPLIFIED: 07-email-integration.md section 7.3.8 additionally refuses when the
        # derived +unsub- mailbox exceeds 64 characters. That check belongs to the transport,
        # which owns the from-address; here H5 reads the one column the database has.
        results.append(_block("H5",
                              "No unsubscribe address is configured, and no email goes out "
                              "without one.",
                              {"email_sending_domain": None}))
    return results


# ===========================================================================
# Gate I - approval and mode at the send boundary
# ===========================================================================

GATE_I_SQL = """
SELECT m.id, m.status, m.body_hash, m.to_address_norm, m.approval_id,
       d.policy_result,
       a.id                AS live_approval_id,
       a.approved_at, a.revoked_at,
       a.approved_body_hash, a.approved_to_address,
       a.session_auth_method
  FROM outreach_messages m
  JOIN outreach_drafts d ON d.id = m.draft_id
  LEFT JOIN outreach_approvals a
         ON a.id = m.approval_id
        AND a.message_id = m.id
        AND a.revoked_at IS NULL
 WHERE m.id = :message_id
"""


def _gate_i(ctx: _Ctx) -> list[GateResult]:
    if ctx.message_id is None:
        why = "There is no message row yet."
        return [_skip(gate, why) for gate in ("I1", "I2", "I3", "I4")]

    row = ctx.conn.execute(GATE_I_SQL, {"message_id": ctx.message_id}).fetchone()
    if row is None:
        raise EligibilityError(f"no outreach_messages row for {ctx.message_id!r}")
    results: list[GateResult] = []
    evidence = (ctx.message_id,)

    if ctx.stage != "SEND":
        results.append(_skip("I1", "The message status is checked at send."))
    elif row["status"] == "QUEUED":
        results.append(_pass("I1", "This message is approved and queued.",
                             {"status": row["status"]}))
    else:
        results.append(_block("I1",
                              f"This message is {row['status']}, not approved and queued.",
                              {"status": row["status"]}, evidence))

    # The application-level twin of trg_om_send_needs_approval. The trigger is the part that
    # cannot be bypassed; gate I exists so the refusal reaches Sagar as a sentence rather than
    # as a sqlite3.IntegrityError in a log file.
    approval_id = row["live_approval_id"]
    if approval_id is None:
        results.append(_block("I2", "No live approval matches this message's text and recipient.",
                              {"approval_id": row["approval_id"]}, evidence))
        results.append(_skip("I3", "There is no live approval to age."))
    elif row["approved_body_hash"] != row["body_hash"]:
        results.append(_block("I2",
                              "The approved text is not the text about to be sent - approve it "
                              "again.",
                              {"approval_id": approval_id, "body_hash_matches": False},
                              (approval_id,)))
        results.append(_skip("I3", "The approval does not match this message."))
    elif row["approved_to_address"] != row["to_address_norm"]:
        results.append(_block("I2",
                              "The approved recipient is not the recipient about to be written "
                              "to - approve it again.",
                              {"approval_id": approval_id, "address_matches": False},
                              (approval_id,)))
        results.append(_skip("I3", "The approval does not match this message."))
    else:
        results.append(_pass("I2", "A live approval matches this message's text and recipient.",
                             {"approval_id": approval_id,
                              "session_auth_method": row["session_auth_method"]},))
        ttl = ctx.policy.approval_ttl_minutes
        age = _age_minutes(row["approved_at"], ctx.now)
        if age is not None and age > ttl:
            results.append(_block("I3",
                                  f"You approved this {age} minutes ago and approvals expire "
                                  f"after {ttl} - review and approve it again.",
                                  {"age_minutes": age, "approval_ttl_minutes": ttl},
                                  (approval_id,)))
        else:
            results.append(_pass("I3",
                                 f"This approval is {age} minutes old, inside its {ttl}-minute "
                                 f"window.",
                                 {"age_minutes": age, "approval_ttl_minutes": ttl}))

    if row["policy_result"] == "BLOCK":
        results.append(_block("I4",
                              "The message makes a claim the research does not support; edit "
                              "it or regenerate.",
                              {"policy_result": row["policy_result"]}, evidence))
    else:
        results.append(_pass("I4", "The claim policy check passed.",
                             {"policy_result": row["policy_result"]}))
    return results


# ===========================================================================
# The entry point
# ===========================================================================


def check_send_eligibility(
    conn: sqlite3.Connection,
    business_id: str,
    contact_id: str | None = None,
    channel: str | None = None,
    *,
    stage: str = "SEND",
    campaign_id: str | None = None,
    message_id: str | None = None,
    now: str | None = None,
    min_research_confidence: str = DEFAULT_MIN_RESEARCH_CONFIDENCE,
    min_research_confidence_pct: int = DEFAULT_MIN_RESEARCH_CONFIDENCE_PCT,
    require_transaction: bool = True,
) -> Eligibility:
    """Answer "may we contact this business, this way, right now?" with a reason per gate.

    Read-only. It never writes, never calls an LLM and never opens a socket: at SEND stage it
    runs while SQLite's writer lock is held, and a network call there would hold that lock open
    across the internet.

    Every gate is evaluated on every call - no short circuit - because the operator deserves
    the whole picture rather than the first objection. `blocking_code` is the first BLOCK in
    precedence order; `gates` carries all of them, and `warnings` repeats the WARN results so a
    screen can render an amber band without filtering.

    At `stage='SEND'` the caller must already be inside `db.transaction(conn)`. A check done
    outside that lock is a check done against a database that is free to change between the
    answer and the socket, which is the exact race the send path exists to close.
    """
    if stage not in STAGES:
        raise EligibilityError(f"stage must be one of {STAGES}, got {stage!r}")
    if stage == "SEND" and require_transaction and not conn.in_transaction:
        raise EligibilityError(
            "check_send_eligibility(stage='SEND') must run inside db.transaction(conn): a "
            "decision taken outside the write lock can be stale before the message leaves"
        )
    if channel is not None and channel not in CHANNEL_CONTACT_KINDS:
        raise EligibilityError(f"unknown channel {channel!r}")

    now_iso = _now(now)
    business = conn.execute(
        "SELECT * FROM businesses WHERE id = ?", (business_id,)
    ).fetchone()
    if business is None:
        raise EligibilityError(f"no businesses row for {business_id!r}")

    contact = None
    point = None
    if contact_id is not None:
        contact = conn.execute(
            "SELECT * FROM business_contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if contact is None:
            raise EligibilityError(f"no business_contacts row for {contact_id!r}")
        point = point_from_contact_row(contact)

    message = None
    sequence_no = 1
    parent_message_id = None
    if message_id is not None:
        message = conn.execute(
            "SELECT * FROM outreach_messages WHERE id = ?", (message_id,)
        ).fetchone()
        if message is None:
            raise EligibilityError(f"no outreach_messages row for {message_id!r}")
        sequence_no = message["sequence_no"] or 1
        parent_message_id = message["parent_message_id"]
        campaign_id = campaign_id or message["campaign_id"]

    ctx = _Ctx(
        conn=conn,
        business_id=business_id,
        business=business,
        name=business["name"] or business_id,
        contact_id=contact_id,
        contact=contact,
        point=point,
        channel=channel,
        stage=stage,
        campaign_id=campaign_id,
        message_id=message_id,
        message=message,
        sequence_no=sequence_no,
        is_followup=sequence_no > 1 and parent_message_id is not None,
        policy=effective_policy(conn, campaign_id),
        now=now_iso,
        min_confidence=min_research_confidence,
        min_confidence_pct=min_research_confidence_pct,
    )

    collected: list[GateResult] = []
    for evaluate in (_gate_a, _gate_b, _gate_c, _gate_d, _gate_e, _gate_f, _gate_g,
                     _gate_h, _gate_i):
        collected.extend(evaluate(ctx))

    gates = tuple(sorted(collected, key=lambda g: GATE_INDEX[g.gate]))
    blocking = next((g for g in gates if g.blocks), None)
    warnings = tuple(g for g in gates if g.outcome == "WARN")

    result = Eligibility(
        business_id=business_id,
        contact_id=contact_id,
        channel=channel,
        stage=stage,
        evaluated_at=now_iso,
        policy_version=ctx.policy.policy_version,
        allowed=blocking is None,
        blocking_code=blocking.code if blocking else None,
        blocking_sentence=blocking.sentence if blocking else None,
        gates=gates,
        warnings=warnings,
        fingerprint=eligibility_fingerprint(gates),
    )
    log.debug("eligibility %s stage=%s allowed=%s blocking=%s",
              business_id, stage, result.allowed, result.blocking_code)
    return result


__all__ = [
    "CHANNEL_CONTACT_KINDS",
    "ContactPoint",
    "Eligibility",
    "EligibilityError",
    "GATE_CODES",
    "GATE_ORDER",
    "GateResult",
    "Outcome",
    "Stage",
    "channel_enabled",
    "check_send_eligibility",
    "contact_points_of",
    "effective_daily_cap",
    "effective_policy",
    "eligibility_fingerprint",
    "live_suppressions",
    "normalise_contact",
    "point_from_contact_row",
    "registrable_domain",
]
