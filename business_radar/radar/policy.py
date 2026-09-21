"""Refuse to show Sagar a message that claims something the research did not establish.

The failure this prevents is specific and it is not hypothetical: a business receives a cold
email asserting a fact about its internal operations that the sender cannot possibly know,
replies "how do you know that?", and there is no answer. That single exchange costs the
prospect, the sending account's reputation, and any claim the system had to being a research
tool rather than a spam cannon.

So every draft - generated, rewritten or hand-edited - is segmented into sentences, every
sentence that asserts something about the recipient is matched to a research_findings row, and
the kind of that row decides what the sentence is allowed to sound like: OBSERVED may be
stated, INFERRED must be hedged, UNKNOWN must not appear at all. The result is stored, not just
returned, so six months later the record still says which rule passed and which rule fired.
BLOCK means the approve path will not accept the draft, and the database agrees: there is no
POLICY_BLOCKED -> SENT edge in outreach_status_transitions.

The module's second half answers a different question with the same seriousness: may we contact
this business, this way, right now? check_send_eligibility() is the one place that knows, and
it runs again inside the send transaction, because a suppression written while Sagar was
reading the preview has to win.

Deterministic, pure Python, no LLM call, no network. The engine's failure mode is refusing a
safe message; it is never passing an unsafe one.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Iterable, Mapping, Sequence

from radar.config import Config, ConfigError, load_config
from radar.channels.identity import Identity, load_identity, placeholder_identity
from radar.models import Draft, Finding, parse_ts, utc_now

log = logging.getLogger("radar.policy")

POLICY_VERSION = "policy@v1.0+rules@2026-08-27"

# Thresholds. Named, so that a change to one is a diff a human can read.
MAX_FINDING_AGE_DAYS = 180
UNKNOWN_OVERLAP_THRESHOLD = 0.55
WARN_ESCALATION_COUNT = 3
EMAIL_WORDS_WARN = 320
EMAIL_WORDS_BLOCK = 500
WHATSAPP_CHARS_WARN = 700
WHATSAPP_CHARS_BLOCK = 1000
SUBJECT_MIN = 25
SUBJECT_MAX = 78
NEAR_DUPLICATE_WARN = 0.60
NEAR_DUPLICATE_BLOCK = 0.85
SIMILARITY_CORPUS_LIMIT = 200

CLAIM_TYPES: frozenset[str] = frozenset({
    "FACTUAL", "PROCESS", "SELF", "SELF_CAPABILITY", "OFFER",
    "GREETING", "CTA", "IDENTITY", "COMPLIANCE", "SUBJECT",
})

# A FACTUAL segment is the only kind that must carry a binding. Everything else is a statement
# about us, our offer, or the envelope.
BINDING_REQUIRED = frozenset({"FACTUAL"})


# ===========================================================================
# Segmentation
# ===========================================================================

_ABBREV = {"dr", "mr", "mrs", "ms", "pvt", "ltd", "co", "no", "e.g", "i.e", "sr", "jr", "st"}
_SENTENCE_END = re.compile(r"([.!?])\s+(?=[A-Z0-9])")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_WS = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Segment:
    idx: int
    text: str
    block: int
    kind: str = "FACTUAL"
    slot: str | None = None
    finding_ids: tuple[str, ...] = ()
    bound_by: str | None = None


def normalise(text: str) -> str:
    """casefold, collapse whitespace, strip terminal punctuation. Map matching only."""
    return _WS.sub(" ", text or "").strip().strip(".!?,;:").casefold()


def segment(subject: str | None, body: str) -> list[Segment]:
    """Deterministic segmentation. Segment 0 is the subject when the channel has one.

    Rules, in order: split the body on blank lines into blocks; a bullet line is its own
    segment; inside a block split after [.!?] + whitespace + an uppercase letter or digit,
    unless the token before the punctuation is an abbreviation or a single initial; collapse
    internal whitespace; merge a segment shorter than three characters into the previous one.
    """
    out: list[Segment] = []
    idx = 0
    if subject is not None and subject.strip():
        out.append(Segment(idx=0, text=_WS.sub(" ", subject).strip(), block=-1, slot="subject"))
        idx = 1

    for block_no, block in enumerate(re.split(r"\n\s*\n", body or "")):
        if not block.strip():
            continue
        for line in block.splitlines():
            if not line.strip():
                continue
            pieces = [line] if _BULLET.match(line) else _split_sentences(line)
            for piece in pieces:
                text = _WS.sub(" ", piece).strip()
                if not text:
                    continue
                if len(text) < 3 and out:
                    prev = out[-1]
                    out[-1] = Segment(idx=prev.idx, text=f"{prev.text} {text}".strip(),
                                      block=prev.block, slot=prev.slot)
                    continue
                out.append(Segment(idx=idx, text=text, block=block_no))
                idx += 1
    return out


def sentences(text: str) -> list[str]:
    """The checker's own sentence split, exported so a generator can label what the checker
    will read. A claim map indexed on a different split describes text that is not there."""
    return [seg.text for seg in segment(None, text)]


def _split_sentences(line: str) -> list[str]:
    parts: list[str] = []
    start = 0
    for match in _SENTENCE_END.finditer(line):
        head = line[start:match.end(1)]
        token = re.split(r"[\s(]", head.rstrip()[:-1])[-1].lower() if len(head) > 1 else ""
        if token in _ABBREV or (len(token) == 1 and token.isalpha()):
            continue
        parts.append(head)
        start = match.end()
    parts.append(line[start:])
    return [p for p in parts if p.strip()]


# ===========================================================================
# Similarity helpers
# ===========================================================================

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall((text or "").casefold())


def skeleton(text: str) -> str:
    """Content words only, in order. Used for overlap comparisons, never for display."""
    stop = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "on", "at", "is", "are",
            "was", "were", "be", "been", "it", "its", "this", "that", "with", "as", "by",
            "we", "you", "your", "our", "their", "they", "there", "has", "have", "had"}
    return " ".join(t for t in _tokens(text) if t not in stop)


def _trigrams(text: str) -> set[str]:
    toks = _tokens(text)
    return {" ".join(toks[i:i + 3]) for i in range(max(0, len(toks) - 2))}


def token_set_ratio(a: str, b: str) -> float:
    """Jaccard over token sets. Cheap, order-insensitive, good enough for both callers."""
    sa, sb = set(_tokens(a)), set(_tokens(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def trigram_jaccard(a: str, b: str) -> float:
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ===========================================================================
# Rule tables. Every regex here traces to a bad example in spec section 23.
# ===========================================================================

HEDGE_RE = re.compile(r"""\b(
      may | might | could | can\s+potentially | would\s+typically | typically | often | usually
    | we\s+believe | we\s+think | it\s+is\s+possible\s+that | it\s+may\s+be
    | appears?\s+to | seems?\s+to | suggests?\s+that
    | based\s+on\s+the\s+nature\s+of | based\s+on\s+the\s+scale
    | in\s+businesses\s+of\s+this\s+type | for\s+a\s+business\s+of\s+this\s+size
    | if\s+that\s+is\s+the\s+case | where\s+relevant | potentially
)\b""", re.I | re.X)

FORBIDDEN_ASSERTIVE: list[tuple[str, str]] = [
    (r"\bwe\s+(noticed|observed|saw|found|spotted|see)\b", "A1"),
    (r"\bwe\s+know\b", "A1"),
    (r"\bwe\s+understand\s+that\s+(you|your)\b", "A1"),
    (r"\bwe\s+can\s+see\s+that\s+(you|your)\b", "A1"),
    (r"\byou\s+are\s+(currently\s+)?(using|running|managing|handling|relying\s+on|"
     r"struggling|losing|wasting)\b", "A1"),
    (r"\byou\s+(still\s+)?(use|run|manage|handle|rely\s+on)\b", "A1"),
    (r"\byour\s+(problem|issue|pain\s*point|bottleneck|challenge)\s+is\b", "A1"),
    (r"\byour\s+(company|business|organisation|organization|team)\s+has\s+"
     r"(a\s+|an\s+|serious\s+|major\s+)?(problem|issues?|difficult)", "A1"),
    (r"\byou\s+(have|face|suffer\s+from)\s+(a\s+|an\s+)?(problem|issues?)\b", "A1"),
    (r"\b(clearly|obviously|evidently|no\s+doubt)\b", "A1"),
    (r"\byour\s+current\s+(system|software|process)\s+(is|does|cannot|can't)", "A1"),
]

FAKE_URGENCY: list[tuple[str, str]] = [
    (r"\b(limited\s+time|offer\s+expires?|expires\s+(today|tomorrow|soon))\b", "A2"),
    (r"\b(act\s+now|last\s+chance|final\s+(call|reminder)|don'?t\s+miss)\b", "A2"),
    (r"\b(only\s+(a\s+)?few|few\s+slots?|limited\s+slots?|closing\s+soon)\b", "A2"),
    (r"\b(this\s+week\s+only|today\s+only|hurry|urgent(ly)?\s+reply)\b", "A2"),
]

UNBOUND_STATISTIC: list[tuple[str, str]] = [
    (r"\b\d{1,3}(\.\d+)?\s?%", "A3"),
    (r"\b\d+\s?x\b", "A3"),
    (r"\b(hundreds|thousands|dozens)\s+of\s+(businesses|clients|customers)\b", "A3"),
    (r"\b(most|many|nine\s+out\s+of\s+ten)\s+(hospitals|schools|colleges|"
     r"manufacturers|dealers|businesses|companies)\b", "A3"),
    (r"\b(save|reduce|cut|increase|improve)\s+[^.]{0,20}\bby\s+\d", "A3"),
]

FABRICATED_RELATIONSHIP: list[tuple[str, str]] = [
    (r"\bas\s+(discussed|promised|agreed|per\s+our\s+(call|conversation|meeting))\b", "A5"),
    (r"\b(following\s+up\s+on|further\s+to)\s+(our|my|the)\s+"
     r"(call|conversation|meeting|email|message)\b", "A5"),
    (r"\b(referred\s+by|on\s+the\s+recommendation\s+of|introduced\s+(to\s+you\s+)?by)\b", "A5"),
    (r"\b(your|a)\s+(colleague|friend|associate|contact)\s+(suggested|mentioned|told)\b", "A5"),
    (r"\bwe\s+(met|spoke)\s+(at|during|last)\b", "A5"),
    (r"\b(mutual|common)\s+(contact|connection|friend)\b", "A5"),
]

GUARANTEE: list[tuple[str, str]] = [
    (r"\bguarantee[ds]?\b", "A6"),
    (r"\b100\s?%\b", "A6"),
    (r"\b(will|shall)\s+(definitely\s+)?(reduce|increase|save|eliminate|fix|solve)\b", "A6"),
    (r"\brisk[- ]free\b", "A6"),
]

SUPERLATIVE: list[tuple[str, str]] = [
    (r"\b(best|leading|number\s*one|#\s*1|world[- ]class|cutting[- ]edge|"
     r"state[- ]of[- ]the[- ]art|revolutionary|game[- ]chang)\w*\b", "A7"),
]

PRESSURE_CTA: list[tuple[str, str]] = [
    (r"\b(call|reply|respond|confirm)\s+(me\s+)?(back\s+)?(today|now|immediately|"
     r"right\s+away|within\s+\d+\s+hours?)\b", "A8"),
    (r"\bwhen\s+(can|shall)\s+we\s+(meet|talk)\s+(today|tomorrow)\b", "A8"),
]

PERSONAL_IDENTIFIER: list[tuple[str, str]] = [
    (r"\b[A-Z]{5}\d{4}[A-Z]\b", "P2"),                       # PAN
    (r"\b\d{4}\s?\d{4}\s?\d{4}\b", "P2"),                    # Aadhaar-shaped
    (r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]Z[A-Z\d]\b", "P2"),  # GSTIN
    (r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b", "P2"),               # a mobile number
    (r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "P2"),                  # an email address
    (r"\b(date\s+of\s+birth|d\.?o\.?b\.?)\b", "P2"),
]

SENSITIVE_INFERENCE: list[tuple[str, str]] = [
    (r"\b(financial(ly)?\s+(trouble|distress|difficulty)|cash\s?flow\s+problem|"
     r"losing\s+money|near\s+bankrupt|debt)\b", "P4"),
    (r"\b(illness|health\s+condition|caste|religion|political)\b", "P4"),
]

PRICE_CLAIM: list[tuple[str, str]] = [
    (r"[₹$]\s?\d", "M3"),
    (r"\b(rs\.?|inr|usd)\s?\d", "M3"),
    (r"\b(price|pricing|cost\s+per|quote|quotation|discount)\b", "M3"),
]

HONORIFIC_NAME = re.compile(
    r"\b(?:Dr|Mr|Mrs|Ms|Shri|Smt|Prof)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)")
URL_RE = re.compile(r"https?://([^\s/<>\"')]+)", re.I)
EMAIL_IN_BODY = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
MARKUP_RE = re.compile(r"(<[a-zA-Z/][^>]*>)|(\{\{)|(\{%)|(<<[A-Z_]+>>)|(<[A-Z_]{3,}>)")
HEX32 = re.compile(r"\b[0-9a-f]{32}\b")
PROPER_RUN = re.compile(r"\b([A-Z][A-Za-z&'.-]*(?:\s+[A-Z][A-Za-z&'.-]*)+)")

_MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december", "monday", "tuesday",
           "wednesday", "thursday", "friday", "saturday", "sunday"}

# The full rule catalogue, so that a rule that did not run is still visible as SKIPPED.
RULES: tuple[tuple[str, str, str], ...] = (
    ("F1", "UNBOUND_ASSERTION", "BLOCK"),
    ("F2", "BINDING_NOT_FOUND", "BLOCK"),
    ("F3", "PROCESS_CLAIM_UNSUPPORTED", "BLOCK"),
    ("F4", "SOURCELESS_FINDING", "BLOCK"),
    ("F5", "STALE_RESEARCH", "WARN"),
    ("K1", "INFERRED_UNHEDGED", "BLOCK"),
    ("K2", "UNKNOWN_CITED", "BLOCK"),
    ("K3", "UNKNOWN_LEAKED", "BLOCK"),
    ("K4", "LOW_CONFIDENCE_STATED", "WARN"),
    ("A1", "FORBIDDEN_ASSERTIVE", "BLOCK"),
    ("A2", "FAKE_URGENCY", "BLOCK"),
    ("A3", "UNBOUND_STATISTIC", "BLOCK"),
    ("A4", "INVENTED_CLIENT", "BLOCK"),
    ("A5", "FABRICATED_RELATIONSHIP", "BLOCK"),
    ("A6", "GUARANTEE", "BLOCK"),
    ("A7", "SUPERLATIVE", "WARN"),
    ("A8", "PRESSURE_CTA", "WARN"),
    ("P1", "UNAUTHORISED_NAME", "BLOCK"),
    ("P2", "PERSONAL_IDENTIFIER", "BLOCK"),
    ("P4", "SENSITIVE_INFERENCE", "BLOCK"),
    ("R1", "MISSING_UNSUBSCRIBE", "BLOCK"),
    ("R2", "MISSING_IDENTITY", "BLOCK"),
    ("R3", "SUBJECT_MISLEADING", "BLOCK"),
    ("R4", "SUBJECT_LENGTH", "WARN"),
    ("R5", "MISSING_PURPOSE", "WARN"),
    ("R6", "LENGTH_BUDGET", "BLOCK"),
    ("R7", "LINK_POLICY", "BLOCK"),
    ("R8", "MARKUP_IN_BODY", "BLOCK"),
    ("M1", "MODULE_NOT_IN_MAP", "BLOCK"),
    ("M2", "CAPABILITY_NOT_DECLARED", "BLOCK"),
    ("M3", "PRICE_CLAIM", "BLOCK"),
    ("T1", "TEMPLATE_BUNDLE_UNPINNED", "BLOCK"),
    ("T2", "CLAIM_MAP_MALFORMED", "BLOCK"),
    ("T3", "SEGMENT_UNMATCHED", "BLOCK"),
    ("V1", "NEAR_DUPLICATE", "WARN"),
    ("V2", "TEMPLATE_UNRENDERED", "BLOCK"),
)

RULE_NAME = {rid: name for rid, name, _ in RULES}
RULE_SEVERITY = {rid: sev for rid, _, sev in RULES}

# SIMPLIFIED: 06-message-engine.md section 6.9.6 rule P3 (third-party individual) and section
# 6.9.9 rule T1's bundle-hash check need a name lexicon and an on-disk template bundle that this
# build does not ship. P1 covers the honorific case, T1 covers the unpinned case.


# ===========================================================================
# Result types
# ===========================================================================

@dataclass(frozen=True, slots=True)
class RuleOutcome:
    rule_id: str
    name: str
    severity: str            # BLOCK | WARN
    status: str              # PASS | FIRED | SKIPPED
    segments: tuple[int, ...] = ()
    detail: str | None = None
    evidence: dict[str, Any] | None = None
    remedy: str | None = None

    @property
    def fired(self) -> bool:
        return self.status == "FIRED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id, "name": self.name, "severity": self.severity,
            "status": self.status, "segments": list(self.segments), "detail": self.detail,
            "evidence": self.evidence, "remedy": self.remedy,
        }


@dataclass(frozen=True, slots=True)
class SimilarityResult:
    max_j3: float = 0.0
    max_tsr: float = 0.0
    peer_message_id: str | None = None
    corpus_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"max_j3": round(self.max_j3, 4), "max_tsr": round(self.max_tsr, 4),
                "peer_message_id": self.peer_message_id, "corpus_size": self.corpus_size}


@dataclass(frozen=True, slots=True)
class PolicyResult:
    verdict: str                       # PASS | WARN | BLOCK
    rules: tuple[RuleOutcome, ...]
    similarity: SimilarityResult
    policy_version: str
    body_hash: str
    checked_at: str
    channel: str = "EMAIL"
    draft_id: str | None = None
    segments: tuple[Segment, ...] = ()
    claim_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.verdict == "BLOCK"

    @property
    def fired(self) -> tuple[RuleOutcome, ...]:
        return tuple(o for o in self.rules if o.fired)

    @property
    def blocking_rules(self) -> tuple[RuleOutcome, ...]:
        return tuple(o for o in self.fired if o.severity == "BLOCK")

    def sentence(self) -> str:
        """One line a human can act on. Empty string when the draft passed cleanly."""
        if self.verdict == "PASS":
            return ""
        first = self.blocking_rules or self.fired
        if not first:
            return ""
        head = first[0]
        return f"{head.rule_id} {head.name}: {head.detail or head.remedy or ''}".strip()

    def to_dict(self) -> dict[str, Any]:
        counts = {
            "block": sum(1 for o in self.rules if o.fired and o.severity == "BLOCK"),
            "warn": sum(1 for o in self.rules if o.fired and o.severity == "WARN"),
            "pass": sum(1 for o in self.rules if o.status == "PASS"),
            "skipped": sum(1 for o in self.rules if o.status == "SKIPPED"),
        }
        return {
            "schema": "policy_result/v1",
            "policy_version": self.policy_version,
            "checked_at": self.checked_at,
            "draft_id": self.draft_id,
            "channel": self.channel,
            "verdict": self.verdict,
            "counts": counts,
            "body_hash": self.body_hash,
            "segments": len(self.segments),
            "rules": [o.to_dict() for o in self.rules],
            "similarity": self.similarity.to_dict(),
            "claim_summary": self.claim_summary,
        }

    def to_row(self) -> dict[str, Any]:
        """The three columns store_policy_result() writes, plus the hash the approve path
        compares against."""
        return {
            "policy_result": self.verdict,
            "policy_detail": json.dumps(self.to_dict(), ensure_ascii=False),
            "policy_version": self.policy_version,
            "policy_checked_at": self.checked_at,
            "policy_checked_body_hash": self.body_hash,
        }


@dataclass(frozen=True, slots=True)
class FindingRef:
    """A finding as the checker needs it: kind, statement, and how well sourced it is."""
    id: str
    kind: str
    statement: str
    confidence: str
    business_id: str
    research_run_id: str
    n_sources: int = 0
    latest_checked_at: str | None = None

    @classmethod
    def from_finding(cls, finding: Finding, *, latest_checked_at: str | None = None) -> FindingRef:
        return cls(
            id=finding.id, kind=finding.kind, statement=finding.statement,
            confidence=finding.confidence, business_id=finding.business_id,
            research_run_id=finding.research_run_id,
            n_sources=len(finding.source_ids or ()),
            latest_checked_at=latest_checked_at,
        )


def body_hash(subject: str | None, body: str) -> str:
    """sha256 over subject + RS + body. The same bytes the approval row commits to."""
    payload = f"{subject or ''}\x1e{body or ''}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ===========================================================================
# check_policy
# ===========================================================================

@dataclass(frozen=True, slots=True)
class _Ctx:
    identity: Identity
    channel: str
    business_name: str
    city: str
    solution_name: str
    allowed_labels: tuple[str, ...]
    all_labels: tuple[str, ...]
    demo_labels: tuple[str, ...]
    contact_person: str | None
    unsubscribe_address: str
    unsubscribe_token: str | None
    has_completed_research: bool
    thread_has_sent: bool
    # The frozen spans: signature and opt-out lines, normalised. A segment that IS one of these
    # is that thing, byte for byte, rather than a sentence the classifier has to reason about.
    identity_lines: tuple[str, ...] = ()


def check_policy(
    draft: Draft,
    findings: Sequence[Finding | FindingRef],
    *,
    identity: Identity | None = None,
    claim_map: Sequence[Mapping[str, Any]] | None = None,
    business_name: str = "",
    city: str = "",
    solution_name: str = "",
    allowed_labels: Sequence[str] = (),
    all_labels: Sequence[str] = (),
    demo_labels: Sequence[str] = (),
    contact_person: str | None = None,
    unsubscribe_address: str = "",
    unsubscribe_token: str | None = None,
    template_version: str | None = None,
    has_completed_research: bool = True,
    thread_has_sent: bool = False,
    similarity_corpus: Sequence[tuple[str, str]] = (),
    now: str | None = None,
) -> PolicyResult:
    """Run every rule against a draft and return the verdict, per rule.

    `draft` supplies the text (final_body: the edited body when there is one, so an edit cannot
    inherit the generated body's PASS) and `findings` supplies the research it is allowed to
    lean on. Everything else is context the rules need in order to be decidable: a rule that
    cannot see the identity block cannot tell a real signature from a missing one.

    No writes, no LLM, no network. Deterministic for a fixed input.
    """
    checked_at = now or utc_now()
    ident = identity or _default_identity()
    channel = (draft.channel or "EMAIL").upper()
    subject = draft.subject if channel == "EMAIL" else None
    body = draft.final_body or ""
    unsub = unsubscribe_address or _derive_unsub_address(ident, unsubscribe_token)

    ctx = _Ctx(
        identity=ident, channel=channel, business_name=business_name, city=city,
        solution_name=solution_name,
        allowed_labels=tuple(l.lower() for l in allowed_labels),
        all_labels=tuple(l.lower() for l in all_labels),
        demo_labels=tuple(l.lower() for l in demo_labels),
        contact_person=contact_person, unsubscribe_address=unsub,
        unsubscribe_token=unsubscribe_token,
        has_completed_research=has_completed_research, thread_has_sent=thread_has_sent,
        identity_lines=tuple(normalise(line) for line in ident.signature_lines()),
    )

    refs: dict[str, FindingRef] = {}
    for f in findings:
        ref = f if isinstance(f, FindingRef) else FindingRef.from_finding(f)
        refs[ref.id] = ref

    segments = segment(subject, body)
    outcomes: list[RuleOutcome] = []
    entries, unmatched = _bind_claims(segments, claim_map)
    segments = _classify(segments, entries, ctx)

    outcomes.extend(_rules_provenance(segments, claim_map, unmatched, template_version, body))
    outcomes.extend(_rules_binding(segments, refs, draft, ctx, checked_at))
    outcomes.extend(_rules_kind(segments, refs, ctx))
    outcomes.extend(_rules_language(segments, refs, ctx))
    outcomes.extend(_rules_pii(segments, body, ctx))
    outcomes.extend(_rules_required(segments, subject, body, ctx))
    outcomes.extend(_rules_modules(segments, body, ctx))
    similarity, v1 = _rule_similarity(body, similarity_corpus)
    outcomes.append(v1)

    verdict = _verdict(outcomes)
    summary = _claim_summary(segments, refs)
    return PolicyResult(
        verdict=verdict, rules=tuple(outcomes), similarity=similarity,
        policy_version=POLICY_VERSION, body_hash=body_hash(subject, body),
        checked_at=checked_at, channel=channel, draft_id=draft.id,
        segments=tuple(segments), claim_summary=summary,
    )


def _default_identity() -> Identity:
    try:
        return load_identity(load_config(strict=False))
    except (ConfigError, OSError) as exc:
        log.warning("policy: no identity available (%s); using the rehearsal placeholder", exc)
        return placeholder_identity()


def _derive_unsub_address(identity: Identity, token: str | None) -> str:
    if not token:
        return ""
    local, _, domain = identity.from_address.partition("@")
    return f"{local}+unsub-{token}@{domain}" if domain else ""


def _verdict(outcomes: Sequence[RuleOutcome]) -> str:
    if any(o.fired and o.severity == "BLOCK" for o in outcomes):
        return "BLOCK"
    warns = {o.rule_id for o in outcomes if o.fired and o.severity == "WARN"}
    if len(warns) >= WARN_ESCALATION_COUNT:
        # A message with three things slightly wrong with it is one worth regenerating.
        return "BLOCK"
    return "WARN" if warns else "PASS"


def _claim_summary(segments: Sequence[Segment], refs: Mapping[str, FindingRef]) -> dict[str, Any]:
    observed, inferred, unknown, unbound = [], [], [], []
    factual = 0
    for seg in segments:
        if seg.kind == "FACTUAL":
            factual += 1
            if not seg.finding_ids:
                unbound.append(seg.idx)
        for fid in seg.finding_ids:
            ref = refs.get(fid)
            if ref is None:
                continue
            {"OBSERVED": observed, "INFERRED": inferred, "UNKNOWN": unknown}[ref.kind].append(fid)
    return {
        "factual_segments": factual,
        "observed_ids": sorted(set(observed)),
        "inferred_ids": sorted(set(inferred)),
        "unknown_ids_present": sorted(set(unknown)),
        "unbound_segments": unbound,
    }


# --- claim map binding -----------------------------------------------------

def _bind_claims(
    segments: Sequence[Segment],
    claim_map: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    """Attach each claim entry to exactly one segment. Never the other way round.

    A segment the model did not describe is unbound, not safe.
    """
    if not claim_map:
        return {}, []
    by_norm = {normalise(s.text): s.idx for s in segments}
    bound: dict[int, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    for raw in claim_map:
        if not isinstance(raw, Mapping) or "text" not in raw or "type" not in raw:
            unmatched.append({"text": str(raw)[:120], "reason": "malformed entry"})
            continue
        entry = {
            "text": str(raw.get("text") or ""),
            "type": str(raw.get("type") or "FACTUAL").upper(),
            "finding_ids": tuple(str(i) for i in (raw.get("finding_ids") or [])),
        }
        key = normalise(entry["text"])
        idx = by_norm.get(key)
        if idx is None:
            best_idx, best_score = None, 0.0
            for seg in segments:
                score = token_set_ratio(entry["text"], seg.text)
                if score > best_score:
                    best_idx, best_score = seg.idx, score
            idx = best_idx if best_score >= 0.95 else None
        if idx is None:
            unmatched.append({"text": entry["text"][:120], "reason": "no matching segment"})
            continue
        existing = bound.get(idx)
        if existing:
            existing["finding_ids"] = tuple(set(existing["finding_ids"]) | set(entry["finding_ids"]))
        else:
            bound[idx] = entry
    return bound, unmatched


def _classify(
    segments: Sequence[Segment],
    entries: Mapping[int, Mapping[str, Any]],
    ctx: _Ctx,
) -> list[Segment]:
    out: list[Segment] = []
    for seg in segments:
        entry = entries.get(seg.idx)
        kind = _classify_segment(seg, ctx)
        if entry is not None and entry["type"] in CLAIM_TYPES:
            declared = entry["type"]
            # The model may only make a segment *more* restricted, never less. A segment the
            # checker reads as FACTUAL stays FACTUAL however the model labelled it.
            kind = kind if kind == "FACTUAL" else declared
        finding_ids = tuple(entry["finding_ids"]) if entry else ()
        out.append(Segment(idx=seg.idx, text=seg.text, block=seg.block, kind=kind,
                           slot=seg.slot, finding_ids=finding_ids,
                           bound_by="MODEL" if entry else None))
    return out


def _classify_segment(seg: Segment, ctx: _Ctx) -> str:
    """Conservative lexical classifier. When unsure, FACTUAL - and FACTUAL must bind."""
    text = seg.text
    low = text.casefold()
    ident = ctx.identity

    if seg.slot == "subject":
        return "SUBJECT"
    if normalise(text) in ctx.identity_lines:
        return "IDENTITY"
    if ctx.unsubscribe_address and ctx.unsubscribe_address.casefold() in low:
        return "COMPLIANCE"
    if re.search(r"\breply\s+(with\s+the\s+word\s+)?stop\b", low):
        return "COMPLIANCE"
    if low.startswith("hello") or low.startswith("dear") or low.startswith("hi "):
        return "GREETING"
    if any(bit and bit.casefold() in low for bit in
           (ident.from_address, ident.reply_to, ident.site_url)) or low.startswith("regards"):
        return "IDENTITY"
    if ident.company_name and ident.company_name.casefold() in low and "we" not in low.split():
        return "IDENTITY"

    second_person = bool(re.search(r"\byour\b|\byou\b", low))
    first_person = bool(re.search(r"\b(we|i|our|my)\b", low))

    if first_person and re.search(
            r"\b(researching|research|reviewed|came\s+across|looked\s+at|read)\b", low):
        return "PROCESS"
    if first_person and not second_person and re.search(
            r"\b(demonstration|demo|show\s+you|building|build)\b", low):
        return "SELF_CAPABILITY"
    if ctx.solution_name and ctx.solution_name.casefold() in low:
        return "OFFER"
    if first_person and not second_person and re.search(
            r"\b(we\s+build|we\s+work\s+on|we\s+are|what\s+we\s+build|a\s+system\s+that\s+would)\b",
            low):
        return "SELF"
    if re.search(r"\b(happy\s+to|would\s+be\s+glad|if\s+this\s+is\s+relevant|"
                 r"let\s+me\s+know|worth\s+a\s+short)\b", low) and not _asserts_about_recipient(low):
        return "CTA"
    return "FACTUAL"


def _asserts_about_recipient(low: str) -> bool:
    return bool(re.search(r"\byour\s+\w+\s+(is|are|has|have|was|were)\b", low))


# --- rule groups -----------------------------------------------------------

def _outcome(rule_id: str, status: str, *, segments: Iterable[int] = (),
             detail: str | None = None, evidence: dict[str, Any] | None = None,
             remedy: str | None = None) -> RuleOutcome:
    return RuleOutcome(rule_id=rule_id, name=RULE_NAME[rule_id],
                       severity=RULE_SEVERITY[rule_id], status=status,
                       segments=tuple(segments), detail=detail, evidence=evidence,
                       remedy=remedy)


def _rules_provenance(segments, claim_map, unmatched, template_version, body) -> list[RuleOutcome]:
    out: list[RuleOutcome] = []

    if not template_version:
        out.append(_outcome("T1", "FIRED",
                            detail="The draft records no template_version.",
                            remedy="Regenerate the draft; a message with no pinned template "
                                   "cannot be reproduced later."))
    else:
        out.append(_outcome("T1", "PASS"))

    if not claim_map:
        out.append(_outcome("T2", "FIRED",
                            detail="The draft carries no claim map, so nothing binds its "
                                   "sentences to research.",
                            remedy="Regenerate the draft."))
    elif any(not isinstance(e, Mapping) or "text" not in e or "type" not in e
             or str(e.get("type", "")).upper() not in CLAIM_TYPES for e in claim_map):
        out.append(_outcome("T2", "FIRED",
                            detail="A claim map entry is missing text/type or uses an unknown "
                                   "claim type.",
                            remedy="Regenerate the draft."))
    else:
        out.append(_outcome("T2", "PASS"))

    if unmatched:
        out.append(_outcome("T3", "FIRED",
                            detail=f"{len(unmatched)} claim entries describe text that is not "
                                   f"in the body.",
                            evidence={"unmatched": unmatched[:5]},
                            remedy="Regenerate the draft; the map and the body disagree."))
    else:
        out.append(_outcome("T3", "PASS" if claim_map else "SKIPPED"))

    hits = [s.idx for s in segments if re.search(r"\bNone\b|\[\]", s.text)]
    out.append(_outcome("V2", "FIRED" if hits else "PASS", segments=hits,
                        detail="A slot rendered as the literal 'None' or '[]'." if hits else None,
                        remedy="Regenerate the draft." if hits else None))
    return out


def _rules_binding(segments, refs, draft, ctx, checked_at) -> list[RuleOutcome]:
    out: list[RuleOutcome] = []
    cited = {fid for s in segments for fid in s.finding_ids}

    unbound = [s.idx for s in segments
               if s.kind in BINDING_REQUIRED and s.slot != "subject" and not s.finding_ids]
    out.append(_outcome(
        "F1", "FIRED" if unbound else "PASS", segments=unbound,
        detail=(f"Sentences {unbound} assert something about the business with no research "
                f"behind them.") if unbound else None,
        remedy="Cite a finding, hedge it, or delete the sentence." if unbound else None))

    bad = []
    for fid in sorted(cited):
        ref = refs.get(fid)
        if ref is None:
            bad.append({"finding_id": fid, "why": "not found in this business's findings"})
        elif ref.business_id and draft.business_id and ref.business_id != draft.business_id:
            bad.append({"finding_id": fid, "why": "belongs to another business"})
    out.append(_outcome(
        "F2", "FIRED" if bad else "PASS", evidence={"bindings": bad} if bad else None,
        detail="A sentence cites research that is not this business's current research."
        if bad else None,
        remedy="Regenerate the draft." if bad else None))

    process = [s.idx for s in segments if s.kind == "PROCESS"]
    if not process:
        out.append(_outcome("F3", "SKIPPED"))
    elif ctx.has_completed_research:
        out.append(_outcome("F3", "PASS", segments=process))
    else:
        out.append(_outcome(
            "F3", "FIRED", segments=process,
            detail="The message says we reviewed public information. There is no completed "
                   "research run with sources to back that.",
            remedy="Run research for this business before writing to it."))

    sourceless = sorted(fid for fid in cited
                        if fid in refs and refs[fid].n_sources == 0)
    out.append(_outcome(
        "F4", "FIRED" if sourceless else "PASS",
        evidence={"finding_ids": sourceless} if sourceless else None,
        detail="A cited finding has no source. Findings without sources are not citable."
        if sourceless else None,
        remedy="Re-run research, or remove the sentence." if sourceless else None))

    stale: list[dict[str, Any]] = []
    checked_dt = parse_ts(checked_at)
    for fid in sorted(cited):
        ref = refs.get(fid)
        if ref is None or not ref.latest_checked_at or checked_dt is None:
            continue
        seen = parse_ts(ref.latest_checked_at)
        if seen is None:
            continue
        age = (checked_dt - seen) // timedelta(days=1)
        if age > MAX_FINDING_AGE_DAYS:
            stale.append({"finding_id": fid, "age_days": int(age),
                          "threshold_days": MAX_FINDING_AGE_DAYS})
    if not any(refs[f].latest_checked_at for f in cited if f in refs):
        out.append(_outcome("F5", "SKIPPED"))
    else:
        out.append(_outcome(
            "F5", "FIRED" if stale else "PASS", evidence={"stale": stale} if stale else None,
            detail="A sentence rests on information checked more than "
                   f"{MAX_FINDING_AGE_DAYS} days ago." if stale else None,
            remedy="Re-research this business, or soften the sentence." if stale else None))
    return out


def _rules_kind(segments, refs, ctx) -> list[RuleOutcome]:
    out: list[RuleOutcome] = []
    unhedged, unknown_cited, low_stated = [], [], []
    for seg in segments:
        kinds = {refs[f].kind for f in seg.finding_ids if f in refs}
        if "INFERRED" in kinds and not HEDGE_RE.search(seg.text):
            unhedged.append(seg.idx)
        if "UNKNOWN" in kinds:
            unknown_cited.append(seg.idx)
        if kinds == {"OBSERVED"} and not HEDGE_RE.search(seg.text):
            if all(refs[f].confidence == "LOW" for f in seg.finding_ids if f in refs):
                low_stated.append(seg.idx)

    out.append(_outcome(
        "K1", "FIRED" if unhedged else "PASS", segments=unhedged,
        detail="A sentence states an inference as fact. INFERRED findings must be hedged in "
               "the same sentence." if unhedged else None,
        remedy="Add 'may', 'could', 'we believe' or 'based on the nature of' to that sentence."
        if unhedged else None))
    out.append(_outcome(
        "K2", "FIRED" if unknown_cited else "PASS", segments=unknown_cited,
        detail="A sentence cites a finding we recorded as UNKNOWN." if unknown_cited else None,
        remedy="Delete the sentence. An UNKNOWN finding may not appear in a message."
        if unknown_cited else None))

    leaks: list[dict[str, Any]] = []
    unknowns = [r for r in refs.values() if r.kind == "UNKNOWN"]
    for seg in segments:
        if seg.kind != "FACTUAL":
            continue
        for ref in unknowns:
            score = token_set_ratio(skeleton(seg.text), skeleton(ref.statement))
            if score >= UNKNOWN_OVERLAP_THRESHOLD:
                leaks.append({"segment": seg.idx, "finding_id": ref.id,
                              "overlap": round(score, 3), "statement": ref.statement})
    if not unknowns:
        out.append(_outcome("K3", "SKIPPED"))
    else:
        out.append(_outcome(
            "K3", "FIRED" if leaks else "PASS",
            segments=[l["segment"] for l in leaks], evidence={"leaks": leaks[:5]} if leaks else None,
            detail="A sentence says something we recorded as UNKNOWN, without citing it."
            if leaks else None,
            remedy="Delete the sentence; rewording it past the threshold is not the fix."
            if leaks else None))
    out.append(_outcome(
        "K4", "FIRED" if low_stated else "PASS", segments=low_stated,
        detail="A sentence states a LOW-confidence observation flatly." if low_stated else None,
        remedy="Hedge it, or cite a better-sourced finding." if low_stated else None))
    return out


def _rules_language(segments, refs, ctx) -> list[RuleOutcome]:
    out: list[RuleOutcome] = []
    tables = [
        ("A1", FORBIDDEN_ASSERTIVE), ("A2", FAKE_URGENCY), ("A5", FABRICATED_RELATIONSHIP),
        ("A6", GUARANTEE), ("A7", SUPERLATIVE), ("A8", PRESSURE_CTA),
    ]
    for rule_id, table in tables:
        hits: list[dict[str, Any]] = []
        for seg in segments:
            for pattern, _ in table:
                match = re.search(pattern, seg.text, re.I)
                if match:
                    hits.append({"segment": seg.idx, "phrase": match.group(0)})
        if rule_id == "A5" and hits and ctx.thread_has_sent:
            # A follow-up on a thread we really did send is not a fabricated relationship.
            out.append(_outcome("A5", "PASS", evidence={"downgraded": hits[:5]}))
            continue
        out.append(_outcome(
            rule_id, "FIRED" if hits else "PASS",
            segments=[h["segment"] for h in hits], evidence={"hits": hits[:5]} if hits else None,
            detail=(f"Banned phrasing: {hits[0]['phrase']!r}.") if hits else None,
            remedy="Rewrite that sentence so it does not assert what we cannot know."
            if hits else None))

    allowed_numbers = {t for r in refs.values() for t in _tokens(r.statement) if t.isdigit()}
    stat_hits: list[dict[str, Any]] = []
    for seg in segments:
        if seg.kind not in {"FACTUAL", "OFFER", "SELF_CAPABILITY", "SELF", "SUBJECT"}:
            continue
        for pattern, _ in UNBOUND_STATISTIC:
            match = re.search(pattern, seg.text, re.I)
            if match and match.group(0).strip().strip("%x ") not in allowed_numbers:
                stat_hits.append({"segment": seg.idx, "phrase": match.group(0)})
    out.append(_outcome(
        "A3", "FIRED" if stat_hits else "PASS",
        segments=[h["segment"] for h in stat_hits],
        evidence={"hits": stat_hits[:5]} if stat_hits else None,
        detail=f"A number appears that no cited finding supports: "
               f"{stat_hits[0]['phrase']!r}." if stat_hits else None,
        remedy="Delete the number or cite the finding it came from." if stat_hits else None))

    out.append(_rule_invented_client(segments, refs, ctx))
    return out


def _rule_invented_client(segments, refs, ctx) -> RuleOutcome:
    """A capitalised multi-word proper noun that is nobody we are allowed to name.

    Catches 'we did this for XYZ Hospital'. Words that appear in a cited finding are allowed:
    a proper noun the research actually recorded is not an invention.
    """
    allow: set[str] = set(_MONTHS)
    for source in (ctx.business_name, ctx.city, ctx.solution_name, ctx.identity.company_name,
                   ctx.identity.sender_name, ctx.identity.role, ctx.contact_person or "",
                   " ".join(ctx.all_labels)):
        allow.update(_tokens(source))
    for ref in refs.values():
        allow.update(_tokens(ref.statement))

    hits: list[dict[str, Any]] = []
    for seg in segments:
        for match in PROPER_RUN.finditer(seg.text):
            run = match.group(1)
            words = run.split()
            if match.start() == 0 and len(words) > 1:
                words = words[1:]          # sentence-initial capital is not a proper noun
            if len(words) < 2:
                continue
            if all(w.casefold().strip(".,&'") in allow for w in words):
                continue
            hits.append({"segment": seg.idx, "phrase": " ".join(words)})
    return _outcome(
        "A4", "FIRED" if hits else "PASS", segments=[h["segment"] for h in hits],
        evidence={"hits": hits[:5]} if hits else None,
        detail=f"The body names {hits[0]['phrase']!r}, which is not this business, this city, "
               f"our company or a cited finding." if hits else None,
        remedy="Remove the name. We do not cite clients or third parties in a first message."
        if hits else None)


def _rules_pii(segments, body, ctx) -> list[RuleOutcome]:
    out: list[RuleOutcome] = []
    ident = ctx.identity
    exempt = {v.casefold() for v in (ident.from_address, ident.reply_to,
                                     ctx.unsubscribe_address, ident.phone_display) if v}

    hits: list[dict[str, Any]] = []
    for seg in segments:
        for pattern, _ in PERSONAL_IDENTIFIER:
            for match in re.finditer(pattern, seg.text):
                value = match.group(0)
                if value.casefold() in exempt:
                    continue
                if re.sub(r"[\s\-]", "", value).casefold() in {
                        re.sub(r"[\s\-]", "", e) for e in exempt}:
                    continue
                hits.append({"segment": seg.idx, "value": value})
    out.append(_outcome(
        "P2", "FIRED" if hits else "PASS", segments=[h["segment"] for h in hits],
        evidence={"count": len(hits)} if hits else None,
        detail="The body carries a personal identifier that is not one of our own contact "
               "details." if hits else None,
        remedy="Remove it. Contact details of the recipient never belong in the body."
        if hits else None))

    named: list[dict[str, Any]] = []
    allowed = (ctx.contact_person or "").casefold()
    for seg in segments:
        for match in HONORIFIC_NAME.finditer(seg.text):
            name = match.group(1)
            if allowed and name.casefold() in allowed:
                continue
            if name.casefold() in ctx.identity.sender_name.casefold():
                continue
            named.append({"segment": seg.idx, "name": name})
    out.append(_outcome(
        "P1", "FIRED" if named else "PASS", segments=[n["segment"] for n in named],
        evidence={"names": named[:5]} if named else None,
        detail=f"The body names {named[0]['name']!r}, who is not the verified contact for this "
               f"business." if named else None,
        remedy="Address the business, or the one contact you verified." if named else None))

    sensitive: list[dict[str, Any]] = []
    for seg in segments:
        for pattern, _ in SENSITIVE_INFERENCE:
            match = re.search(pattern, seg.text, re.I)
            if match:
                sensitive.append({"segment": seg.idx, "phrase": match.group(0)})
    out.append(_outcome(
        "P4", "FIRED" if sensitive else "PASS", segments=[s["segment"] for s in sensitive],
        evidence={"hits": sensitive[:5]} if sensitive else None,
        detail="The body infers a special-category attribute about the business or its people."
        if sensitive else None,
        remedy="Delete the sentence." if sensitive else None))
    return out


def _rules_required(segments, subject, body, ctx) -> list[RuleOutcome]:
    out: list[RuleOutcome] = []
    ident = ctx.identity
    low = body.casefold()

    # R1 - the entire opt-out surface on this stack.
    if ctx.channel == "EMAIL":
        problems = []
        if not ctx.unsubscribe_address or ctx.unsubscribe_address.casefold() not in low:
            problems.append("the unsubscribe address is not in the body")
        if not ctx.unsubscribe_token or ctx.unsubscribe_token not in body:
            problems.append("the 32-character unsubscribe token is missing")
        if not re.search(r"\breply\s+(with\s+the\s+word\s+)?stop\b", low):
            problems.append("there is no 'reply STOP' instruction")
        out.append(_outcome(
            "R1", "FIRED" if problems else "PASS",
            evidence={"problems": problems} if problems else None,
            detail="; ".join(problems) if problems else None,
            remedy="Regenerate the draft. mailto: unsubscribe and reply STOP are the only two "
                   "opt-out mechanisms this build has." if problems else None))
    elif ctx.channel == "WHATSAPP":
        ok = bool(re.search(r"\breply\s+(with\s+the\s+word\s+)?stop\b", low))
        out.append(_outcome("R1", "PASS" if ok else "FIRED",
                            detail=None if ok else "No 'reply STOP' instruction.",
                            remedy=None if ok else "Regenerate the draft."))
    else:
        out.append(_outcome("R1", "SKIPPED"))

    # R2 - identity.
    missing = []
    if ident.sender_name and ident.sender_name not in body:
        missing.append("sender name")
    if ident.company_name and ident.company_name not in body:
        missing.append("company name")
    if ctx.channel == "EMAIL" and ident.reply_to and ident.reply_to not in body:
        missing.append("reply address")
    out.append(_outcome(
        "R2", "FIRED" if missing else "PASS",
        evidence={"missing": missing} if missing else None,
        detail=f"The signature is missing: {', '.join(missing)}." if missing else None,
        remedy="Regenerate the draft; an unsigned cold message is not defensible."
        if missing else None))

    # R3 / R4 - subject.
    if ctx.channel != "EMAIL":
        out.append(_outcome("R3", "SKIPPED"))
        out.append(_outcome("R4", "SKIPPED"))
    else:
        subj = (subject or "").strip()
        reasons = []
        if not subj:
            reasons.append("the subject is empty")
        if re.match(r"^\s*(re|fwd|fw)\s*:", subj, re.I) and not ctx.thread_has_sent:
            reasons.append("it claims to be a reply to a message we never sent")
        if subj.count("!") > 1:
            reasons.append("it uses more than one exclamation mark")
        shouty = [t for t in subj.split() if len(t) > 3 and t.isupper()]
        if shouty:
            reasons.append("it shouts")
        if subj and not (set(_tokens(subj)) & set(_tokens(body))):
            reasons.append("it shares no word with the message")
        for table in (FORBIDDEN_ASSERTIVE, FAKE_URGENCY, GUARANTEE):
            for pattern, _ in table:
                if re.search(pattern, subj, re.I):
                    reasons.append(f"it contains banned phrasing")
                    break
        out.append(_outcome(
            "R3", "FIRED" if reasons else "PASS",
            evidence={"reasons": reasons} if reasons else None,
            detail="; ".join(reasons) if reasons else None,
            remedy="Rewrite the subject to describe the message." if reasons else None))
        bad_len = bool(subj) and not (SUBJECT_MIN <= len(subj) <= SUBJECT_MAX)
        out.append(_outcome(
            "R4", "FIRED" if bad_len else "PASS",
            evidence={"length": len(subj)} if bad_len else None,
            detail=f"The subject is {len(subj)} characters; aim for {SUBJECT_MIN}-{SUBJECT_MAX}."
            if bad_len else None))

    # R5 - purpose.
    has_self = any(s.kind in {"SELF", "SELF_CAPABILITY", "PROCESS"} for s in segments)
    out.append(_outcome(
        "R5", "PASS" if has_self else "FIRED",
        detail=None if has_self else "The message never says who we are or why we are writing.",
        remedy=None if has_self else "Add the one-line introduction."))

    # R6 - length.
    words = len(_tokens(body))
    chars = len(body)
    if ctx.channel == "WHATSAPP":
        fired = chars > WHATSAPP_CHARS_WARN
        severity_block = chars > WHATSAPP_CHARS_BLOCK
        out.append(RuleOutcome(
            "R6", RULE_NAME["R6"], "BLOCK" if severity_block else "WARN",
            "FIRED" if fired else "PASS", (),
            f"The WhatsApp message is {chars} characters." if fired else None,
            {"chars": chars}, "Shorten it." if fired else None))
    else:
        fired = words > EMAIL_WORDS_WARN
        severity_block = words > EMAIL_WORDS_BLOCK
        out.append(RuleOutcome(
            "R6", RULE_NAME["R6"], "BLOCK" if severity_block else "WARN",
            "FIRED" if fired else "PASS", (),
            f"The email is {words} words." if fired else None,
            {"words": words}, "Shorten it." if fired else None))

    # R7 - links and addresses.
    problems = []
    hosts = [h.lower().rstrip(".,)") for h in URL_RE.findall(body)]
    site_host = ident.site_host
    if ctx.channel == "WHATSAPP" and hosts:
        problems.append("a WhatsApp message may carry no URL at all")
    else:
        foreign = [h for h in hosts if not site_host or not h.startswith(site_host)]
        if foreign:
            problems.append(f"links to {', '.join(sorted(set(foreign))[:3])}")
        if len(hosts) > 1:
            problems.append("more than one link")
    allowed_addrs = {a.casefold() for a in (ident.reply_to, ident.from_address,
                                            ctx.unsubscribe_address) if a}
    stray = [a for a in EMAIL_IN_BODY.findall(body) if a.casefold() not in allowed_addrs]
    if stray:
        problems.append(f"an address that is not ours: {stray[0]}")
    out.append(_outcome(
        "R7", "FIRED" if problems else "PASS",
        evidence={"problems": problems} if problems else None,
        detail="; ".join(problems) if problems else None,
        remedy="Remove it. One link, to the identity page, and no address but ours."
        if problems else None))

    # R8 - markup and un-hydrated placeholders.
    markup = MARKUP_RE.search(body)
    out.append(_outcome(
        "R8", "FIRED" if markup else "PASS",
        evidence={"match": markup.group(0)} if markup else None,
        detail=f"The body still contains {markup.group(0)!r}." if markup else None,
        remedy="Regenerate the draft. A placeholder that survived into the body means the "
               "contact substitution failed." if markup else None))
    return out


def _rules_modules(segments, body, ctx) -> list[RuleOutcome]:
    out: list[RuleOutcome] = []
    low = body.casefold()

    if not ctx.all_labels:
        out.append(_outcome("M1", "SKIPPED"))
    else:
        present = [l for l in ctx.all_labels if l and l in low]
        wrong = sorted({l for l in present if l not in ctx.allowed_labels})
        out.append(_outcome(
            "M1", "FIRED" if wrong else "PASS", evidence={"labels": wrong} if wrong else None,
            detail=f"The message offers {', '.join(wrong)}, which is not in this business's "
                   f"module map." if wrong else None,
            remedy="Regenerate the draft; that module belongs to another category."
            if wrong else None))

    demo = set(ctx.demo_labels)
    offered: list[str] = []
    for seg in segments:
        if seg.kind != "SELF_CAPABILITY":
            continue
        for label in ctx.allowed_labels:
            if label and label in seg.text.casefold() and label not in demo:
                offered.append(label)
    offered = sorted(set(offered))
    if not any(s.kind == "SELF_CAPABILITY" for s in segments):
        out.append(_outcome("M2", "SKIPPED"))
    else:
        # The comparison is on labels, not module keys: the label form is what the body
        # contains, and "patient records" and PATIENTS are the same module.
        out.append(_outcome(
            "M2", "FIRED" if offered else "PASS",
            evidence={"undeclared": offered} if offered else None,
            detail=f"The message offers a demonstration of {', '.join(offered)}, which is not "
                   f"in identity.demo_modules." if offered else None,
            remedy="Do not offer to demonstrate what does not exist yet." if offered else None))

    price_hits: list[dict[str, Any]] = []
    for seg in segments:
        for pattern, _ in PRICE_CLAIM:
            match = re.search(pattern, seg.text, re.I)
            if match:
                price_hits.append({"segment": seg.idx, "phrase": match.group(0)})
    out.append(_outcome(
        "M3", "FIRED" if price_hits else "PASS",
        segments=[p["segment"] for p in price_hits],
        evidence={"hits": price_hits[:5]} if price_hits else None,
        detail="The message talks about price. Pricing is a human conversation."
        if price_hits else None,
        remedy="Remove it and let the reply start that conversation." if price_hits else None))
    return out


def _rule_similarity(body: str, corpus: Sequence[tuple[str, str]]) -> tuple[SimilarityResult, RuleOutcome]:
    if not corpus:
        return SimilarityResult(), _outcome("V1", "SKIPPED")
    best = SimilarityResult(corpus_size=len(corpus))
    for message_id, prior in corpus:
        j3 = trigram_jaccard(body, prior)
        tsr = token_set_ratio(body, prior)
        if j3 > best.max_j3:
            best = SimilarityResult(max_j3=j3, max_tsr=max(tsr, best.max_tsr),
                                    peer_message_id=message_id, corpus_size=len(corpus))
    if best.max_j3 >= NEAR_DUPLICATE_BLOCK:
        outcome = RuleOutcome("V1", RULE_NAME["V1"], "BLOCK", "FIRED", (),
                              f"This message is {best.max_j3:.0%} identical to one already sent.",
                              best.to_dict(), "Regenerate it.")
    elif best.max_j3 >= NEAR_DUPLICATE_WARN:
        outcome = _outcome("V1", "FIRED", evidence=best.to_dict(),
                           detail=f"This message is {best.max_j3:.0%} similar to "
                                  f"{best.peer_message_id}.",
                           remedy="Consider regenerating it.")
    else:
        outcome = _outcome("V1", "PASS", evidence=best.to_dict())
    return best, outcome


# ===========================================================================
# The database-backed wrappers
# ===========================================================================

_BINDING_SQL = """
SELECT f.id, f.kind, f.statement, f.confidence, f.business_id, f.research_run_id,
       COUNT(fs.source_id) AS n_sources,
       MAX(s.checked_at)   AS latest_checked_at
  FROM research_findings f
  LEFT JOIN finding_sources fs ON fs.finding_id = f.id
  LEFT JOIN sources         s  ON s.id = fs.source_id
 WHERE f.business_id = ? AND f.is_current = 1
 GROUP BY f.id
"""


def load_finding_refs(conn: sqlite3.Connection, business_id: str) -> list[FindingRef]:
    """Every current finding for a business, with its source count and freshness."""
    rows = conn.execute(_BINDING_SQL, (business_id,)).fetchall()
    return [FindingRef(id=r["id"], kind=r["kind"], statement=r["statement"],
                       confidence=r["confidence"], business_id=r["business_id"],
                       research_run_id=r["research_run_id"], n_sources=int(r["n_sources"] or 0),
                       latest_checked_at=r["latest_checked_at"]) for r in rows]


def check_draft(
    conn: sqlite3.Connection,
    draft_id: str,
    *,
    config: Config | None = None,
    identity: Identity | None = None,
    now: str | None = None,
) -> PolicyResult:
    """Re-read the draft from the database and check it. The one entry point the web layer
    and the CLI both use, so an edit cannot reach approval without passing through here."""
    from radar.messages import resolve_modules          # local: messages imports this module

    row = conn.execute(
        """
        SELECT d.*, b.name AS business_name, b.city, b.industry, b.category,
               o.potential_solution
          FROM outreach_drafts d
          JOIN businesses b ON b.id = d.business_id
          LEFT JOIN opportunities o ON o.business_id = b.id AND o.is_current = 1
         WHERE d.id = ?
        """,
        (draft_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no outreach_drafts row {draft_id!r}")

    draft = Draft.from_row(row)
    ident = identity or (load_identity(config) if config else _default_identity())
    profile = resolve_modules(row["category"], row["industry"])

    claim_map = _json_list(row["claim_map"] if "claim_map" in row.keys() else None)
    token = row["unsubscribe_token"] if "unsubscribe_token" in row.keys() else None
    template_version = row["template_version"] if "template_version" in row.keys() else None

    contact_person = None
    if draft.contact_id:
        crow = conn.execute(
            "SELECT person_name FROM business_contacts WHERE id = ?", (draft.contact_id,)
        ).fetchone()
        contact_person = crow["person_name"] if crow else None

    has_research = bool(conn.execute(
        """
        SELECT 1 FROM research_runs r
         WHERE r.business_id = ? AND r.status = 'COMPLETE'
           AND EXISTS (SELECT 1 FROM sources s WHERE s.business_id = r.business_id)
         LIMIT 1
        """,
        (draft.business_id,),
    ).fetchone())

    thread_has_sent = bool(conn.execute(
        """
        SELECT 1 FROM outreach_messages
         WHERE business_id = ? AND status IN ('SENT','DELIVERED','BOUNCED') LIMIT 1
        """,
        (draft.business_id,),
    ).fetchone())

    corpus = [
        (r["id"], r["body_final"] or "")
        for r in conn.execute(
            """
            SELECT id, body_final FROM outreach_messages
             WHERE status IN ('SENT','DELIVERED','BOUNCED') AND business_id <> ?
               AND body_final IS NOT NULL
             ORDER BY sent_at DESC LIMIT ?
            """,
            (draft.business_id, SIMILARITY_CORPUS_LIMIT),
        ).fetchall()
    ]

    return check_policy(
        draft,
        load_finding_refs(conn, draft.business_id),
        identity=ident,
        claim_map=claim_map,
        business_name=row["business_name"],
        city=row["city"],
        solution_name=row["potential_solution"] or profile.solution_name,
        allowed_labels=profile.labels,
        all_labels=all_module_labels(),
        demo_labels=tuple(profile.label_for(k) for k in ident.demo_modules
                          if k in profile.module_keys),
        contact_person=contact_person,
        unsubscribe_token=token,
        template_version=template_version,
        has_completed_research=has_research,
        thread_has_sent=thread_has_sent,
        similarity_corpus=corpus,
        now=now,
    )


def all_module_labels() -> tuple[str, ...]:
    from radar.messages import MODULE_LABELS
    return tuple(MODULE_LABELS.values())


def _json_list(raw: Any) -> list[dict[str, Any]] | None:
    if not raw:
        return None
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def store_policy_result(
    conn: sqlite3.Connection,
    draft_id: str,
    result: PolicyResult,
    *,
    actor: str = "policy",
) -> None:
    """Write the verdict onto the draft, event the message, and move its status.

    policy_checked_body_hash is the column the approve path compares against; without it an
    edit that skipped the checker would inherit the previous PASS.
    """
    from radar.audit import audit
    from radar.db import transaction
    from radar.ids import new_id_for

    row = result.to_row()
    with transaction(conn):
        conn.execute(
            """
            UPDATE outreach_drafts
               SET policy_result = ?, policy_detail = ?, policy_version = ?,
                   policy_checked_at = ?, policy_checked_body_hash = ?
             WHERE id = ?
            """,
            (row["policy_result"], row["policy_detail"], row["policy_version"],
             row["policy_checked_at"], row["policy_checked_body_hash"], draft_id),
        )
        message = conn.execute(
            "SELECT id, status, business_id, campaign_id FROM outreach_messages WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
        if message is not None:
            target = "POLICY_BLOCKED" if result.blocked else "PENDING_APPROVAL"
            if message["status"] == "DRAFT":
                conn.execute("UPDATE outreach_messages SET status = ? WHERE id = ?",
                             (target, message["id"]))
            conn.execute(
                """
                INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, detail)
                VALUES (?, ?, ?, 'SYSTEM', ?, ?)
                """,
                (new_id_for("outreach_events"), message["id"],
                 "POLICY_BLOCK" if result.blocked else "POLICY_PASS", actor,
                 json.dumps({"verdict": result.verdict,
                             "fired": [o.rule_id for o in result.fired]})),
            )
        audit(
            conn, actor,
            "POLICY_CHECK_BLOCKED" if result.blocked else "POLICY_CHECK_PASSED",
            "outreach_drafts", draft_id,
            after={"policy_result": result.verdict},
            detail={"fired": [o.rule_id for o in result.fired],
                    "policy_version": result.policy_version},
            business_id=message["business_id"] if message is not None else None,
            campaign_id=message["campaign_id"] if message is not None else None,
            message_id=message["id"] if message is not None else None,
        )


# ===========================================================================
# Send eligibility - "may we contact them, this way, right now?"
# ===========================================================================
# It lives in radar/eligibility.py, which owns the forty gates, the contact-point
# normalisation and the stored snapshot format. It is re-exported here because
# 05-outreach-workflow.md section 5.13 names `radar/policy.py :: check_send_eligibility()` as
# its address, and because the two questions belong together at the call site: may we say this,
# and may we say it to them. Two implementations of the second question is exactly the drift
# that ends with a message going to somebody who asked us to stop, so there is only one.

from radar.eligibility import (  # noqa: E402  - re-export, after the rules above
    CHANNEL_CONTACT_KINDS,
    ContactPoint,
    Eligibility,
    EligibilityError,
    GATE_ORDER,
    GateResult,
    check_send_eligibility,
    effective_policy,
    live_suppressions,
    normalise_contact,
    registrable_domain,
)

__all__ = [
    # the claim policy
    "POLICY_VERSION", "PolicyResult", "RuleOutcome", "Segment", "SimilarityResult",
    "FindingRef", "RULES", "RULE_NAME", "RULE_SEVERITY", "HEDGE_RE",
    "body_hash", "check_draft", "check_policy", "load_finding_refs", "normalise",
    "segment", "sentences", "skeleton", "store_policy_result", "token_set_ratio",
    "trigram_jaccard", "all_module_labels",
    # the send gates, re-exported from radar/eligibility.py
    "CHANNEL_CONTACT_KINDS", "ContactPoint", "Eligibility", "EligibilityError",
    "GATE_ORDER", "GateResult", "check_send_eligibility", "effective_policy",
    "live_suppressions", "normalise_contact", "registrable_domain",
]
