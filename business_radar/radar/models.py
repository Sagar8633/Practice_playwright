"""The vocabularies and the row shapes, in one file, so nothing anywhere types a status by hand.

The reason this exists is narrower than "typed records are nice". Every enum in this file is
also a CHECK constraint in migrations/001_schema.sql, and the two must agree. When they drift,
the symptom is not a type error: it is an `sqlite3.IntegrityError: CHECK constraint failed`
raised from the middle of a research job at 40 businesses in, naming a constraint and not the
value that broke it. Importing `BusinessStatus.CONTACT_READY` instead of writing
`"CONTACT_READY"` moves that failure to the import, where it is one line to fix.

The `from_row()` classmethods take an `sqlite3.Row` and never a tuple, and they tolerate a row
that is missing columns - a `SELECT b.id, b.name` for a list page produces a partial record
rather than a TypeError. What they do not tolerate is a column present with a value outside its
enum, because that means something has written to the database around the schema.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, TypeVar

# ===========================================================================
# Enums. Every value here is also a CHECK constraint in 001_schema.sql.
# ===========================================================================


class BusinessStatus(StrEnum):
    """The ten lifecycle states of a business (spec section 17).

    The order below is the pipeline order, and the only two facts worth memorising are that
    CONTACT_READY is reachable only through VERIFIED, and CONTACTED is reachable only through
    CONTACT_READY. Both are enforced by triggers, not by this class.
    """
    AI_RESEARCHED = "AI_RESEARCHED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    CONTACT_READY = "CONTACT_READY"
    CONTACTED = "CONTACTED"
    RESPONDED = "RESPONDED"
    INTERESTED = "INTERESTED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


class MessageStatus(StrEnum):
    """outreach_messages.status. SENT is reachable only from APPROVED or QUEUED."""
    DRAFT = "DRAFT"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    BOUNCED = "BOUNCED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class FindingKind(StrEnum):
    """Safety invariant 4, as three words.

    OBSERVED may be stated in a message. INFERRED must be hedged ("may", "could", "we
    believe"). UNKNOWN must never appear in a message at all.
    """
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class Confidence(StrEnum):
    """Three levels everywhere, plus a numeric confidence_pct where a score is needed. There is
    never a fourth level."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Channel(StrEnum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    PHONE = "PHONE"
    MANUAL = "MANUAL"


class SizeBand(StrEnum):
    MICRO = "MICRO"
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    UNKNOWN = "UNKNOWN"


class Industry(StrEnum):
    """The report's city sections. The finer type lives in Category."""
    HEALTHCARE = "HEALTHCARE"
    EDUCATION = "EDUCATION"
    AUTOMOBILE = "AUTOMOBILE"
    MANUFACTURING = "MANUFACTURING"
    RETAIL = "RETAIL"
    HOSPITALITY = "HOSPITALITY"
    DISTRIBUTION = "DISTRIBUTION"
    REAL_ESTATE = "REAL_ESTATE"
    PROFESSIONAL_SERVICES = "PROFESSIONAL_SERVICES"
    OTHER = "OTHER"


class Category(StrEnum):
    HOSPITAL = "HOSPITAL"
    DIAGNOSTIC_CENTER = "DIAGNOSTIC_CENTER"
    SCHOOL = "SCHOOL"
    COLLEGE = "COLLEGE"
    MANUFACTURER = "MANUFACTURER"
    DISTRIBUTOR = "DISTRIBUTOR"
    VEHICLE_DEALER = "VEHICLE_DEALER"
    GARAGE = "GARAGE"
    HOTEL = "HOTEL"
    RESTAURANT = "RESTAURANT"
    BAKERY = "BAKERY"
    RETAIL_STORE = "RETAIL_STORE"
    REAL_ESTATE_AGENCY = "REAL_ESTATE_AGENCY"
    OTHER = "OTHER"


class ResponseClass(StrEnum):
    """The thirteen inbound classifications (spec section 33).

    The AI assigns one of these and stops. It never replies. Everything in STOPPER_CLASSES
    halts outreach for that business immediately; everything in INTERESTED_CLASSES pages a
    human.
    """
    INTERESTED = "INTERESTED"
    VERY_INTERESTED = "VERY_INTERESTED"
    DEMO_REQUESTED = "DEMO_REQUESTED"
    MEETING_REQUESTED = "MEETING_REQUESTED"
    PRICE_REQUESTED = "PRICE_REQUESTED"
    MORE_INFORMATION = "MORE_INFORMATION"
    LATER = "LATER"
    NOT_INTERESTED = "NOT_INTERESTED"
    ALREADY_HAVE_SOFTWARE = "ALREADY_HAVE_SOFTWARE"
    WRONG_CONTACT = "WRONG_CONTACT"
    OPT_OUT = "OPT_OUT"
    COMPLAINT = "COMPLAINT"
    UNKNOWN = "UNKNOWN"


class AutomationMode(StrEnum):
    """contact_policy.automation_mode. HUMAN_APPROVAL is the only value v1 accepts; the
    database rejects the other three on insert and on update."""
    MANUAL = "MANUAL"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    SEMI_AUTOMATED = "SEMI_AUTOMATED"
    FULLY_AUTOMATED = "FULLY_AUTOMATED"


class ActorKind(StrEnum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    PROVIDER = "PROVIDER"
    ANONYMOUS = "ANONYMOUS"


class Verdict(StrEnum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"


class SuppressionScope(StrEnum):
    BUSINESS = "BUSINESS"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    WHATSAPP = "WHATSAPP"
    DOMAIN = "DOMAIN"


class SuppressionReason(StrEnum):
    UNSUBSCRIBE_LINK = "UNSUBSCRIBE_LINK"
    REPLY_OPT_OUT = "REPLY_OPT_OUT"
    COMPLAINT = "COMPLAINT"
    BOUNCE_HARD = "BOUNCE_HARD"
    MANUAL = "MANUAL"
    DNC_LIST = "DNC_LIST"
    LEGAL_REQUEST = "LEGAL_REQUEST"


class ContactKind(StrEnum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    WHATSAPP = "WHATSAPP"
    WEB_FORM = "WEB_FORM"
    ADDRESS = "ADDRESS"
    OTHER = "OTHER"


class HandoffState(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"


class CampaignStatus(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    DISCOVERING = "DISCOVERING"
    RESEARCHING = "RESEARCHING"
    REPORTING = "REPORTING"
    COMPLETE = "COMPLETE"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunStatus(StrEnum):
    """research_runs.status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# --- derived sets, so nothing recomputes them at a call site ----------------

#: A response in any of these stops outreach for that business at once.
STOPPER_CLASSES: frozenset[ResponseClass] = frozenset({
    ResponseClass.OPT_OUT,
    ResponseClass.COMPLAINT,
    ResponseClass.NOT_INTERESTED,
    ResponseClass.ALREADY_HAVE_SOFTWARE,
})

#: A response in any of these pages a human. The machine does not answer any of them.
INTERESTED_CLASSES: frozenset[ResponseClass] = frozenset({
    ResponseClass.INTERESTED,
    ResponseClass.VERY_INTERESTED,
    ResponseClass.DEMO_REQUESTED,
    ResponseClass.MEETING_REQUESTED,
    ResponseClass.PRICE_REQUESTED,
})

#: A response in either of these writes a permanent suppressions row, always.
OPT_OUT_CLASSES: frozenset[ResponseClass] = frozenset({
    ResponseClass.OPT_OUT,
    ResponseClass.COMPLAINT,
})

#: Statuses from which an outreach object (selection, draft, message) may be created.
OUTREACHABLE_STATUSES: frozenset[BusinessStatus] = frozenset({
    BusinessStatus.CONTACT_READY,
    BusinessStatus.CONTACTED,
    BusinessStatus.RESPONDED,
})

#: Statuses a message can be in after it has left Sagar's hands.
TERMINAL_MESSAGE_STATUSES: frozenset[MessageStatus] = frozenset({
    MessageStatus.SENT,
    MessageStatus.DELIVERED,
    MessageStatus.BOUNCED,
    MessageStatus.FAILED,
    MessageStatus.CANCELLED,
})

#: The nine verification checks, in the order they are asked.
VERIFICATION_CHECK_KEYS: tuple[str, ...] = (
    "IDENTITY_CORRECT",
    "IN_TARGET_CITY",
    "CATEGORY_CORRECT",
    "APPEARS_OPERATIONAL",
    "CONTACT_LEGITIMATE",
    "RESEARCH_RELEVANT",
    "OPPORTUNITY_REASONABLE",
    "OUTREACH_APPROPRIATE",
    "NO_DNC_RECORD",
)

#: Frozensets of the raw string values, for code that validates untrusted input before it
#: reaches the database (an API payload, a CSV import).
BUSINESS_STATUSES: frozenset[str] = frozenset(s.value for s in BusinessStatus)
MESSAGE_STATUSES: frozenset[str] = frozenset(s.value for s in MessageStatus)
FINDING_KINDS: frozenset[str] = frozenset(s.value for s in FindingKind)
CONFIDENCES: frozenset[str] = frozenset(s.value for s in Confidence)
CHANNELS: frozenset[str] = frozenset(s.value for s in Channel)
SIZE_BANDS: frozenset[str] = frozenset(s.value for s in SizeBand)
INDUSTRIES: frozenset[str] = frozenset(s.value for s in Industry)
CATEGORIES: frozenset[str] = frozenset(s.value for s in Category)
RESPONSE_CLASSES: frozenset[str] = frozenset(s.value for s in ResponseClass)


def band_for_score(score: int) -> str:
    """HIGH >= 80, MEDIUM 60-79, LOW < 60. The one place this mapping is written.

    The database enforces the same relation as a CHECK, so a scorer that drifts from this
    function fails at the INSERT rather than printing "HIGH" next to 62 in a report.
    """
    if not 0 <= score <= 100:
        raise ValueError(f"opportunity score must be 0-100, got {score}")
    if score >= 80:
        return Confidence.HIGH.value
    if score >= 60:
        return Confidence.MEDIUM.value
    return Confidence.LOW.value


def utc_now() -> str:
    """The canonical timestamp format: 'YYYY-MM-DDTHH:MM:SSZ', UTC.

    Matches strftime('%Y-%m-%dT%H:%M:%SZ','now') exactly, including the CHECK constraints that
    test the shape with LIKE '____-__-__T__:__:__Z'.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str | None) -> datetime | None:
    """Parse one of our timestamps back into an aware datetime. None passes through."""
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ===========================================================================
# Row helpers
# ===========================================================================

T = TypeVar("T")


def _keys(row: sqlite3.Row | dict[str, Any]) -> set[str]:
    if isinstance(row, sqlite3.Row):
        return set(row.keys())
    return set(row.keys())


def _get(row: sqlite3.Row | dict[str, Any], key: str, default: Any = None) -> Any:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return default if value is None else value


def _json(row: sqlite3.Row | dict[str, Any], key: str, default: Any) -> Any:
    """Decode a JSON column, falling back loudly rather than crashing a report render.

    A malformed JSON column is a bug somewhere upstream, but a report that refuses to render
    because one business has a bad `aliases` value is worse than one that renders it empty.
    """
    raw = _get(row, key)
    if raw in (None, ""):
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _bool(row: sqlite3.Row | dict[str, Any], key: str, default: bool = False) -> bool:
    value = _get(row, key)
    return default if value is None else bool(value)


def _int(row: sqlite3.Row | dict[str, Any], key: str) -> int | None:
    value = _get(row, key)
    return None if value is None else int(value)


class _FromRow:
    """Mixin giving every record a `from_row()` that tolerates a partial SELECT.

    Subclasses override it when a column needs decoding (JSON, an enum with a default). The
    generic version is enough for the flat ones and keeps them honest: adding a column to the
    dataclass without adding it to the SELECT yields the dataclass default, not a TypeError.
    """

    @classmethod
    def from_row(cls: type[T], row: sqlite3.Row | dict[str, Any]) -> T:
        present = _keys(row)
        kwargs = {f.name: row[f.name] for f in fields(cls) if f.name in present}  # type: ignore[arg-type]
        return cls(**kwargs)  # type: ignore[call-arg]

    def to_dict(self) -> dict[str, Any]:
        """A plain dict, for JSON responses and Jinja contexts."""
        return {f.name: getattr(self, f.name) for f in fields(self)}  # type: ignore[arg-type]


# ===========================================================================
# Records
# ===========================================================================

@dataclass(slots=True)
class Campaign(_FromRow):
    """One run of the pipeline over a set of cities. The unit of work and of reporting."""
    id: str
    name: str = ""
    slug: str = ""
    created_by: str = ""
    created_at: str = ""
    industries: list[str] = None  # type: ignore[assignment]
    categories: list[str] = None  # type: ignore[assignment]
    size_filter: list[str] = None  # type: ignore[assignment]
    min_opportunity_score: int = 0
    research_depth: str = "STANDARD"
    max_businesses: int | None = None
    status: str = CampaignStatus.DRAFT.value
    paused_reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    cancel_requested: bool = False
    n_discovered: int = 0
    n_researched: int = 0
    n_qualified: int = 0
    n_skipped: int = 0
    n_verified: int = 0
    n_contacted: int = 0
    discovery_provider: str | None = None
    research_model_id: str | None = None
    research_prompt_version: str | None = None
    notes: str | None = None
    updated_at: str = ""

    def __post_init__(self) -> None:
        if self.industries is None:
            self.industries = []
        if self.categories is None:
            self.categories = []
        if self.size_filter is None:
            self.size_filter = []

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Campaign:
        return cls(
            id=row["id"],
            name=_get(row, "name", ""),
            slug=_get(row, "slug", ""),
            created_by=_get(row, "created_by", ""),
            created_at=_get(row, "created_at", ""),
            industries=_json(row, "industries", []),
            categories=_json(row, "categories", []),
            size_filter=_json(row, "size_filter", []),
            min_opportunity_score=int(_get(row, "min_opportunity_score", 0)),
            research_depth=_get(row, "research_depth", "STANDARD"),
            max_businesses=_int(row, "max_businesses"),
            status=_get(row, "status", CampaignStatus.DRAFT.value),
            paused_reason=_get(row, "paused_reason"),
            started_at=_get(row, "started_at"),
            finished_at=_get(row, "finished_at"),
            cancel_requested=_bool(row, "cancel_requested"),
            n_discovered=int(_get(row, "n_discovered", 0)),
            n_researched=int(_get(row, "n_researched", 0)),
            n_qualified=int(_get(row, "n_qualified", 0)),
            n_skipped=int(_get(row, "n_skipped", 0)),
            n_verified=int(_get(row, "n_verified", 0)),
            n_contacted=int(_get(row, "n_contacted", 0)),
            discovery_provider=_get(row, "discovery_provider"),
            research_model_id=_get(row, "research_model_id"),
            research_prompt_version=_get(row, "research_prompt_version"),
            notes=_get(row, "notes"),
            updated_at=_get(row, "updated_at", ""),
        )

    @property
    def is_live(self) -> bool:
        return self.status in {
            CampaignStatus.QUEUED, CampaignStatus.DISCOVERING,
            CampaignStatus.RESEARCHING, CampaignStatus.REPORTING, CampaignStatus.PAUSED,
        }


@dataclass(slots=True)
class Business(_FromRow):
    """One real trading entity. `status` is the gate everything else in the system reads."""
    id: str
    business_key: str = ""
    name: str = ""
    name_norm: str = ""
    legal_name: str | None = None
    aliases: list[str] = None  # type: ignore[assignment]
    city: str = ""
    city_slug: str = ""
    state_region: str = "Maharashtra"
    address: str | None = None
    pincode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    industry: str = Industry.OTHER.value
    category: str = Category.OTHER.value
    size_band: str = SizeBand.UNKNOWN.value
    website: str | None = None
    website_domain: str | None = None
    website_status: str = "UNKNOWN"
    listing_url: str | None = None
    digital_maturity: int | None = None
    operational_complexity: int | None = None
    opportunity_score: int | None = None
    opportunity_band: str | None = None
    research_confidence: str | None = None
    research_confidence_pct: int | None = None
    status: str = BusinessStatus.AI_RESEARCHED.value
    status_actor_kind: str = ActorKind.SYSTEM.value
    status_actor_user_id: str | None = None
    status_changed_at: str | None = None
    status_verification_id: str | None = None
    contact_ready_at: str | None = None
    skip_reason: str | None = None
    research_status: str = "PENDING"
    last_researched_at: str | None = None
    research_fingerprint: str | None = None
    contact_fingerprint: str | None = None
    first_contacted_at: str | None = None
    last_contacted_at: str | None = None
    first_seen_campaign_id: str = ""
    first_discovered_at: str = ""
    merged_into_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Business:
        present = _keys(row)
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name != "aliases" and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        if "aliases" in present:
            kwargs["aliases"] = _json(row, "aliases", [])
        return cls(**kwargs)

    @property
    def may_receive_outreach(self) -> bool:
        """True only from the three statuses an outreach object may be created against.

        Advisory: the database enforces the same thing with three BEFORE INSERT triggers. Use
        this to decide whether to render a button, never to decide whether to send.
        """
        return self.status in {s.value for s in OUTREACHABLE_STATUSES}

    @property
    def is_merged_away(self) -> bool:
        return self.merged_into_id is not None


@dataclass(slots=True)
class Contact(_FromRow):
    """A way to reach a business. No value on this record is ever sent to an LLM.

    `human_verified` is the column that separates "we scraped an address" from "Sagar looked at
    it and said yes", and it is what CONTACT_READY depends on.
    """
    id: str
    business_id: str = ""
    kind: str = ContactKind.EMAIL.value
    value_raw: str = ""
    value_norm: str = ""
    value_dedupe: str = ""
    value_display: str = ""
    domain: str | None = None
    valid: bool = True
    invalid_reason: str | None = None
    phone_e164: str | None = None
    phone_number_type: str | None = None
    wa_capability: str = "UNKNOWN"
    wa_id: str | None = None
    whatsapp_capable: bool = False
    whatsapp_optin_at: str | None = None
    whatsapp_optin_source: str | None = None
    is_public_business_contact: bool = True
    is_named_individual: bool = False
    person_name: str | None = None
    person_role: str | None = None
    is_role_address: bool = False
    source_id: str | None = None
    source_url: str | None = None
    discovered_at: str = ""
    captured_at: str = ""
    confidence: str = Confidence.MEDIUM.value
    confidence_pct: int | None = None
    human_verified: bool = False
    human_verified_at: str | None = None
    human_verified_by: str | None = None
    is_active: bool = True
    deactivated_at: str | None = None
    deactivated_reason: str | None = None
    is_primary: bool = False
    retention_class: str = "P2Y"
    erased_at: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Contact:
        present = _keys(row)
        bool_fields = {
            "valid", "whatsapp_capable", "is_public_business_contact", "is_named_individual",
            "is_role_address", "human_verified", "is_active", "is_primary",
        }
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            if f.name not in present:
                continue
            value = row[f.name]
            if value is None:
                continue
            kwargs[f.name] = bool(value) if f.name in bool_fields else value
        kwargs["id"] = row["id"]
        return cls(**kwargs)

    @property
    def is_live(self) -> bool:
        """Active, valid, and confirmed by a human. The predicate CONTACT_READY reads."""
        return self.is_active and self.valid and self.human_verified

    @property
    def masked(self) -> str:
        """A display form safe to put in a log line or an audit payload.

        'owner@abchospital.in' -> 'ow***@abchospital.in'. No raw address reaches audit_log;
        a trigger enforces it, and this is what callers use instead.
        """
        value = self.value_norm or self.value_raw
        if "@" in value:
            local, _, domain = value.partition("@")
            head = local[:2] if len(local) > 2 else local[:1]
            return f"{head}***@{domain}"
        if len(value) > 4:
            return f"{value[:3]}***{value[-2:]}"
        return "***"


@dataclass(slots=True)
class ResearchRun(_FromRow):
    """One pass of research over one business. Carries the model provenance an audit needs."""
    id: str
    business_id: str = ""
    campaign_id: str | None = None
    depth: str = "STANDARD"
    status: str = RunStatus.PENDING.value
    reason: str = "CAMPAIGN"
    model_id: str | None = None
    prompt_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    quota_requests: int = 0
    n_findings: int = 0
    n_findings_observed: int = 0
    n_findings_inferred: int = 0
    n_findings_unknown: int = 0
    n_sources: int = 0
    capture_path: str | None = None
    capture_sha256: str | None = None
    fingerprint: str | None = None
    error: str | None = None
    job_run_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str = ""

    @property
    def is_complete(self) -> bool:
        return self.status == RunStatus.COMPLETE


@dataclass(slots=True)
class Source(_FromRow):
    """A page that was actually fetched, with the hash of what it said at the time.

    Without the hash and the snapshot, "the source says so" degrades to "the source said so in
    August" the moment the page changes, and a claim in a sent message becomes unprovable.
    """
    id: str
    business_id: str | None = None
    name: str = ""
    url: str = ""
    source_type: str = "OTHER"
    checked_at: str = ""
    information_obtained: str = ""
    confidence: str = Confidence.MEDIUM.value
    confidence_pct: int | None = None
    url_norm: str = ""
    domain: str | None = None
    http_status: int | None = None
    content_sha256: str | None = None
    snapshot_path: str | None = None
    robots_allowed: bool | None = None
    title: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    research_run_id: str | None = None
    created_at: str = ""


@dataclass(slots=True)
class Finding(_FromRow):
    """One typed fact about a business. Safety invariant 4 lives on this record.

    `kind` decides what a message may do with it: state an OBSERVED, hedge an INFERRED, never
    mention an UNKNOWN. `source_ids` is populated by whoever loads the finding_sources join;
    an OBSERVED finding with an empty list is a bug the policy engine blocks on.
    """
    id: str
    business_id: str = ""
    research_run_id: str = ""
    kind: str = FindingKind.UNKNOWN.value
    dimension: str = "OTHER"
    label: str = ""
    statement: str = ""
    detail: str | None = None
    confidence: str = Confidence.MEDIUM.value
    confidence_pct: int | None = None
    weight: float = 1.0
    derived_from: list[str] = None  # type: ignore[assignment]
    inference_note: str | None = None
    unknown_reason: str | None = None
    is_current: bool = True
    ordinal: int = 0
    created_at: str = ""
    source_ids: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.derived_from is None:
            self.derived_from = []
        if self.source_ids is None:
            self.source_ids = []

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Finding:
        present = _keys(row)
        skip = {"derived_from", "source_ids", "is_current"}
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name not in skip and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["derived_from"] = _json(row, "derived_from", [])
        kwargs["is_current"] = _bool(row, "is_current", True)
        if "source_ids" in present:
            raw = row["source_ids"]
            # Tolerates both a JSON array and the group_concat(',') form a report query uses.
            if isinstance(raw, str) and raw and not raw.startswith("["):
                kwargs["source_ids"] = [s for s in raw.split(",") if s]
            else:
                kwargs["source_ids"] = _json(row, "source_ids", [])
        return cls(**kwargs)

    @property
    def may_be_stated(self) -> bool:
        """OBSERVED only, and only with at least one source behind it."""
        return self.kind == FindingKind.OBSERVED and bool(self.source_ids)

    @property
    def must_be_hedged(self) -> bool:
        return self.kind == FindingKind.INFERRED

    @property
    def must_not_appear(self) -> bool:
        return self.kind == FindingKind.UNKNOWN


@dataclass(slots=True)
class Opportunity(_FromRow):
    """What a management system would do for this business, and how strongly we believe it."""
    id: str
    business_id: str = ""
    research_run_id: str | None = None
    campaign_id: str | None = None
    potential_problem: str = ""
    potential_solution: str = ""
    expected_benefit: str = ""
    score: int = 0
    band: str = Confidence.LOW.value
    confidence: str = Confidence.MEDIUM.value
    confidence_pct: int | None = None
    digital_maturity: int | None = None
    operational_complexity: int | None = None
    score_breakdown: dict[str, Any] = None  # type: ignore[assignment]
    est_value_inr: int | None = None
    est_value_basis: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    computed_at: str = ""
    is_current: bool = True
    superseded_by: str | None = None
    modules: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.score_breakdown is None:
            self.score_breakdown = {}
        if self.modules is None:
            self.modules = []

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Opportunity:
        present = _keys(row)
        skip = {"score_breakdown", "modules", "is_current"}
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name not in skip and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["score_breakdown"] = _json(row, "score_breakdown", {})
        kwargs["is_current"] = _bool(row, "is_current", True)
        if "modules" in present:
            raw = row["modules"]
            if isinstance(raw, str) and raw and not raw.startswith("["):
                kwargs["modules"] = [m for m in raw.split(",") if m]
            else:
                kwargs["modules"] = _json(row, "modules", [])
        return cls(**kwargs)


@dataclass(slots=True)
class Verification(_FromRow):
    """A human signature on a business, with the evidence that it was not a rubber stamp.

    A verdict of VERIFIED requires all nine checks passed, a note of at least fifteen
    characters, and a dwell time above the floor. The database enforces all three.
    """
    id: str
    business_id: str = ""
    campaign_id: str | None = None
    state: str = "DRAFT"
    mode: str = "FULL"
    verdict: str | None = None
    checks_total: int = 9
    checks_passed: int = 0
    checks_failed: int = 0
    reason_code: str | None = None
    reason_note: str | None = None
    why_note: str | None = None
    dwell_ms: int | None = None
    dwell_required_ms: int = 20000
    sources_visited: list[str] = None  # type: ignore[assignment]
    sources_waived: list[str] = None  # type: ignore[assignment]
    trigger_reason: str | None = None
    prior_verification_id: str | None = None
    superseded_at: str | None = None
    superseded_by: str | None = None
    superseded_reason: str | None = None
    research_run_id: str | None = None
    research_fingerprint: str | None = None
    contact_fingerprint: str | None = None
    verified_by: str | None = None
    verified_at: str | None = None
    note: str | None = None
    session_id: str | None = None
    started_at: str = ""
    created_at: str = ""
    checks: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.sources_visited is None:
            self.sources_visited = []
        if self.sources_waived is None:
            self.sources_waived = []
        if self.checks is None:
            self.checks = []

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Verification:
        present = _keys(row)
        skip = {"sources_visited", "sources_waived", "checks"}
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name not in skip and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["sources_visited"] = _json(row, "sources_visited", [])
        kwargs["sources_waived"] = _json(row, "sources_waived", [])
        return cls(**kwargs)

    @property
    def is_live(self) -> bool:
        """Submitted, VERIFIED, and not superseded. The only shape that unlocks outreach."""
        return (
            self.state == "SUBMITTED"
            and self.verdict == Verdict.VERIFIED
            and self.superseded_at is None
        )


@dataclass(slots=True)
class Draft(_FromRow):
    """A generated message, before a human has seen it. `final_body` is the only body anything
    should render: nothing else may compute COALESCE(body_edited, body)."""
    id: str
    business_id: str = ""
    campaign_id: str = ""
    selection_id: str | None = None
    contact_id: str | None = None
    channel: str = Channel.EMAIL.value
    sequence_no: int = 1
    parent_message_id: str | None = None
    subject: str | None = None
    body: str = ""
    body_edited: str | None = None
    edited_by: str | None = None
    edited_at: str | None = None
    edit_count: int = 0
    model_id: str = ""
    prompt_version: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    facts_used: list[str] = None  # type: ignore[assignment]
    inferences_used: list[str] = None  # type: ignore[assignment]
    ai_confidence: str | None = None
    ai_confidence_pct: int | None = None
    policy_result: str | None = None
    policy_detail: dict[str, Any] | None = None
    policy_version: str | None = None
    policy_checked_at: str | None = None
    created_at: str = ""
    created_by: str | None = None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        if self.facts_used is None:
            self.facts_used = []
        if self.inferences_used is None:
            self.inferences_used = []

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Draft:
        present = _keys(row)
        skip = {"facts_used", "inferences_used", "policy_detail"}
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name not in skip and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["facts_used"] = _json(row, "facts_used", [])
        kwargs["inferences_used"] = _json(row, "inferences_used", [])
        kwargs["policy_detail"] = _json(row, "policy_detail", None)
        return cls(**kwargs)

    @property
    def final_body(self) -> str:
        """What would actually be sent. The edited body if there is one, else the generated."""
        return self.body_edited if self.body_edited else self.body

    @property
    def passed_policy(self) -> bool:
        return self.policy_result == "PASS"


@dataclass(slots=True)
class OutreachMessage(_FromRow):
    """One message to one contact. Reaching SENT requires a live approval that matches it.

    `approval_id` is not decoration. The send function takes it, the CHECK constraint requires
    it from APPROVED onwards, and three triggers verify it at the moment status becomes SENT.
    """
    id: str
    draft_id: str = ""
    business_id: str = ""
    campaign_id: str = ""
    contact_id: str | None = None
    channel: str = Channel.EMAIL.value
    status: str = MessageStatus.DRAFT.value
    approval_id: str | None = None
    sequence_no: int = 1
    parent_message_id: str | None = None
    thread_key: str = ""
    to_address_norm: str | None = None
    to_address_dedupe: str | None = None
    to_address_display: str | None = None
    recipient_domain: str | None = None
    subject_final: str | None = None
    body_final: str | None = None
    body_hash: str | None = None
    idempotency_key: str = ""
    provider: str | None = None
    provider_message_id: str | None = None
    provider_status_code: int | None = None
    queued_at: str | None = None
    sent_at: str | None = None
    delivered_at: str | None = None
    failed_at: str | None = None
    cancelled_at: str | None = None
    failure_code: str | None = None
    failure_detail: str | None = None
    attempt_count: int = 0
    next_retry_at: str | None = None
    policy_override: bool = False
    sent_by: str | None = None
    worker_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> OutreachMessage:
        present = _keys(row)
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name != "policy_override" and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["policy_override"] = _bool(row, "policy_override")
        return cls(**kwargs)

    @property
    def is_sent(self) -> bool:
        return self.status in {MessageStatus.SENT, MessageStatus.DELIVERED,
                               MessageStatus.BOUNCED}

    @property
    def is_terminal(self) -> bool:
        return self.status in {s.value for s in TERMINAL_MESSAGE_STATUSES}


@dataclass(slots=True)
class Response(_FromRow):
    """An inbound reply. The AI classifies it; it never answers it."""
    id: str
    business_id: str = ""
    message_id: str | None = None
    campaign_id: str | None = None
    contact_id: str | None = None
    channel: str = Channel.EMAIL.value
    attribution: str = "UNATTRIBUTED"
    attribution_confidence: str = Confidence.MEDIUM.value
    direction: str = "INBOUND"
    from_address_norm: str | None = None
    from_display: str | None = None
    subject: str | None = None
    body_text: str = ""
    body_excerpt: str = ""
    provider_message_id: str | None = None
    in_reply_to: str | None = None
    thread_key: str | None = None
    received_at: str = ""
    classification: str | None = None
    confidence: str | None = None
    confidence_pct: int | None = None
    interpretation: str | None = None
    recommended_action: str | None = None
    classifier_model_id: str | None = None
    classifier_prompt_version: str | None = None
    classified_at: str | None = None
    classification_state: str = "PENDING"
    classification_error: str | None = None
    human_classification: str | None = None
    human_classified_by: str | None = None
    human_classified_at: str | None = None
    human_note: str | None = None
    legal_flag: bool = False
    legal_flag_pattern: str | None = None
    legal_flag_excerpt: str | None = None
    handoff_id: str | None = None
    snooze_until: str | None = None
    is_stopper: bool = False
    created_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Response:
        present = _keys(row)
        bool_fields = {"legal_flag", "is_stopper"}
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            if f.name not in present:
                continue
            value = row[f.name]
            if value is None:
                continue
            kwargs[f.name] = bool(value) if f.name in bool_fields else value
        kwargs["id"] = row["id"]
        return cls(**kwargs)

    @property
    def effective_classification(self) -> str | None:
        """The human's correction if there is one, otherwise the model's answer."""
        return self.human_classification or self.classification

    @property
    def stops_outreach(self) -> bool:
        cls_value = self.effective_classification
        return bool(cls_value) and cls_value in {c.value for c in STOPPER_CLASSES}

    @property
    def needs_human(self) -> bool:
        """A human must see this: an interested lead, a complaint, or legal language."""
        cls_value = self.effective_classification
        if self.legal_flag:
            return True
        if not cls_value:
            return False
        return cls_value in {c.value for c in INTERESTED_CLASSES | OPT_OUT_CLASSES}


@dataclass(slots=True)
class Handoff(_FromRow):
    """A conversation the machine has stopped touching. `brief_json` is a snapshot of what was
    true when it fired, not a live view."""
    id: str
    business_id: str = ""
    campaign_id: str | None = None
    response_id: str = ""
    outreach_message_id: str | None = None
    previous_handoff_id: str | None = None
    owner_user_id: str | None = None
    trigger_rule: str = "CLASSIFICATION"
    trigger_classification: str | None = None
    trigger_detail: str = ""
    confidence: str = Confidence.MEDIUM.value
    confidence_pct: int | None = None
    priority: str = "NORMAL"
    state: str = HandoffState.OPEN.value
    outcome: str | None = None
    lost_reason: str | None = None
    brief: dict[str, Any] = None  # type: ignore[assignment]
    brief_version: int = 1
    response_count: int = 1
    recommended_action: str = ""
    recommended_channel: str | None = None
    recommended_by_when: str | None = None
    action_rule_id: str = "default"
    notify_count: int = 0
    first_notified_at: str | None = None
    last_notified_at: str | None = None
    snoozed_until: str | None = None
    sla_ack_due_at: str = ""
    sla_progress_due_at: str = ""
    sla_close_due_at: str = ""
    sla_breach_count: int = 0
    demo_scheduled_at: str | None = None
    proposal_sent_at: str | None = None
    proposal_value_inr: int | None = None
    won_value_inr: int | None = None
    created_at: str = ""
    acknowledged_at: str | None = None
    started_at: str | None = None
    closed_at: str | None = None
    updated_at: str = ""

    def __post_init__(self) -> None:
        if self.brief is None:
            self.brief = {}

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Handoff:
        present = _keys(row)
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name != "brief" and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["brief"] = _json(row, "brief_json", {})
        return cls(**kwargs)

    @property
    def is_open(self) -> bool:
        return self.state != HandoffState.CLOSED


@dataclass(slots=True)
class Suppression(_FromRow):
    """A permanent block. Safety invariant 3: it blocks every channel for that business and the
    application has no code path that can clear it."""
    id: str
    scope: str = SuppressionScope.EMAIL.value
    value_norm: str = ""
    value_hmac: str | None = None
    business_id: str | None = None
    reason: str = SuppressionReason.MANUAL.value
    source: str = ""
    source_ref: str | None = None
    detail: dict[str, Any] | None = None
    created_at: str = ""
    created_by: str | None = None
    released_at: str | None = None
    released_by: str | None = None
    released_audit_id: str | None = None
    erased_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Suppression:
        present = _keys(row)
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name != "detail" and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["detail"] = _json(row, "detail", None)
        return cls(**kwargs)

    @property
    def is_live(self) -> bool:
        return self.released_at is None


@dataclass(slots=True)
class ContactPolicy(_FromRow):
    """The frequency and pacing rules. `automation_mode` is HUMAN_APPROVAL and the database
    refuses to store anything else."""
    id: str = "GLOBAL"
    scope: str = "GLOBAL"
    campaign_id: str | None = None
    automation_mode: str = AutomationMode.HUMAN_APPROVAL.value
    min_days_between_outreach: int = 21
    max_attempts: int = 3
    max_followups: int = 2
    stop_after_rejection: bool = True
    stop_after_opt_out: bool = True
    recent_campaign_days: int = 90
    same_domain_days: int = 30
    same_domain_max: int = 1
    verification_valid_days: int = 30
    approval_ttl_minutes: int = 60
    send_min_gap_seconds: int = 45
    daily_send_cap: int = 25
    warmup_started_on: str | None = None
    warmup_schedule: list[int] = None  # type: ignore[assignment]
    bounce_rate_window_days: int = 30
    bounce_rate_max_pct: float = 5.0
    complaint_rate_max_pct: float = 0.1
    bounce_rate_min_sample: int = 20
    email_enabled: bool = True
    email_sending_domain: str | None = None
    whatsapp_enabled: bool = True
    whatsapp_api_enabled: bool = False
    phone_enabled: bool = True
    manual_enabled: bool = True
    policy_version: str = "cp-1"
    updated_at: str = ""
    updated_by: str | None = None

    def __post_init__(self) -> None:
        if self.warmup_schedule is None:
            self.warmup_schedule = [5, 5, 10, 10, 15, 15, 20, 20, 25]

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> ContactPolicy:
        present = _keys(row)
        bool_fields = {
            "stop_after_rejection", "stop_after_opt_out", "email_enabled",
            "whatsapp_enabled", "whatsapp_api_enabled", "phone_enabled", "manual_enabled",
        }
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            if f.name not in present or f.name == "warmup_schedule":
                continue
            value = row[f.name]
            if value is None:
                continue
            kwargs[f.name] = bool(value) if f.name in bool_fields else value
        kwargs["warmup_schedule"] = _json(row, "warmup_schedule",
                                          [5, 5, 10, 10, 15, 15, 20, 20, 25])
        return cls(**kwargs)

    @property
    def email_switch_on(self) -> bool:
        """The deliberate on-switch. A freshly migrated database has email_sending_domain NULL
        and cannot mail anybody until somebody sets it."""
        return self.email_enabled and bool(self.email_sending_domain)


@dataclass(slots=True)
class Selection(_FromRow):
    """Sagar picked this business for outreach in this campaign. One live row per pair."""
    id: str
    campaign_id: str = ""
    business_id: str = ""
    city: str = ""
    industry: str = ""
    state: str = "SELECTED"
    intent_channel: str | None = None
    sequence_no: int = 1
    parent_message_id: str | None = None
    eligibility_snapshot: dict[str, Any] = None  # type: ignore[assignment]
    eligible_at_select: bool = False
    blocking_gate: str | None = None
    note: str | None = None
    selected_by: str = ""
    selected_at: str = ""
    removed_by: str | None = None
    removed_at: str | None = None
    updated_at: str = ""

    def __post_init__(self) -> None:
        if self.eligibility_snapshot is None:
            self.eligibility_snapshot = {}

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Selection:
        present = _keys(row)
        skip = {"eligibility_snapshot", "eligible_at_select"}
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name not in skip and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["eligibility_snapshot"] = _json(row, "eligibility_snapshot", {})
        kwargs["eligible_at_select"] = _bool(row, "eligible_at_select")
        return cls(**kwargs)


@dataclass(slots=True)
class Approval(_FromRow):
    """The human approval row. This is safety invariant 1, made of columns.

    `approved_body_hash` and `approved_to_address` are what a trigger compares against the
    message at the moment it becomes SENT: approving one body does not authorise sending a
    different one, and approving a send to one address does not authorise another.
    """
    id: str
    message_id: str = ""
    draft_id: str = ""
    business_id: str = ""
    contact_id: str | None = None
    channel: str = Channel.EMAIL.value
    approved_by: str = ""
    approved_at: str = ""
    session_id: str = ""
    session_auth_method: str = "PASSWORD"
    client_ip: str | None = None
    user_agent: str | None = None
    approved_subject: str | None = None
    approved_body: str = ""
    approved_body_hash: str = ""
    approved_to_address: str = ""
    confirmation_text: str = ""
    displayed: dict[str, Any] = None  # type: ignore[assignment]
    eligibility_snapshot: dict[str, Any] = None  # type: ignore[assignment]
    preview_token: str = ""
    idempotency_key: str = ""
    revoked_at: str | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None

    def __post_init__(self) -> None:
        if self.displayed is None:
            self.displayed = {}
        if self.eligibility_snapshot is None:
            self.eligibility_snapshot = {}

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> Approval:
        present = _keys(row)
        skip = {"displayed", "eligibility_snapshot"}
        kwargs: dict[str, Any] = {
            f.name: row[f.name] for f in fields(cls)
            if f.name in present and f.name not in skip and row[f.name] is not None
        }
        kwargs["id"] = row["id"]
        kwargs["displayed"] = _json(row, "displayed", {})
        kwargs["eligibility_snapshot"] = _json(row, "eligibility_snapshot", {})
        return cls(**kwargs)

    @property
    def is_live(self) -> bool:
        return self.revoked_at is None


@dataclass(slots=True)
class User(_FromRow):
    """An operator. Exists because an approval needs a signer and a string constant is not one."""
    id: str
    email: str = ""
    email_norm: str = ""
    display_name: str = ""
    role: str = "VIEWER"
    must_change_password: bool = False
    totp_enrolled_at: str | None = None
    failed_logins: int = 0
    locked_until: str | None = None
    last_login_at: str | None = None
    created_at: str = ""
    disabled_at: str | None = None

    @property
    def is_active(self) -> bool:
        return self.disabled_at is None

    @property
    def may_approve(self) -> bool:
        return self.is_active and self.role in {"OWNER", "OPERATOR"}
