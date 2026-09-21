"""The number Sagar sorts four hundred businesses by, and the arithmetic behind it in writing.

Without this module the report is a list in discovery order, and he reads the first twenty of
four hundred instead of the best twenty. That is the obvious half.

The half that matters more is what happens to a signal nobody could measure. The opportunity
score rewards a *low* digital maturity - the business that already has a system does not need
one - so scoring an unmeasured signal as zero manufactures a digital gap out of our own
ignorance and floats the businesses we know least about straight to the top of the list he
works down first. Every metric here therefore excludes what it could not measure from both the
numerator and the denominator, records why each one is missing, and returns None rather than a
number when too little was measured to mean anything. An em dash in the report is the honest
answer; a 0 is a claim.

Everything is deterministic and inspectable. Same findings in, same number out, which is what
lets a score be recomputed after a crash and lets two campaigns three months apart be compared
at all. Every component carries the finding id that produced it, so "why 86" is answered from
stored rows rather than by running the model again - and `top_reason` assembles its sentence
from a component label, a number and the stored text of a validated finding, because a
generated one-liner next to a business name in the top-20 table is an unsourced claim in the
one table that is read before deciding who to contact.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Mapping, Sequence

from .config import Config
from .ids import new_id_for
from .models import Confidence, band_for_score, utc_now

log = logging.getLogger("radar.score")

# A weights bump forces a recompute and a note in the report. Turning one of the two
# permanently-None review signals on later is exactly that event, which is why they stay in the
# table at their weights rather than being deleted and the other twelve renormalised.
WEIGHTS_VERSION = "sw-1"

MIN_DIGITAL_COVERAGE = 60.0        # of 100 signal weight
MIN_OPERATIONAL_COVERAGE = 50.0
MIN_SCORE_COVERAGE = 50.0


def round_half_up(x: float) -> int:
    """Half-up via Decimal, never Python's round().

    round(40.5) is 40 and round(41.5) is 42 under banker's rounding, so two businesses whose
    raw scores differ by a point can display the same score and the Top 20 ordering stops
    being explicable to the person reading it.
    """
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ===========================================================================
# The signal registry
# ===========================================================================

@dataclass(slots=True, frozen=True)
class SignalSpec:
    """One measurable input, its weight, and who is allowed to produce it.

    `basis` is PROBE for a deterministic measurement of our own, READ for something a model
    reported with a citation, OSM for a map tag, NONE for a signal with no free source in v1.
    """
    key: str
    weight: float
    basis: str
    value_type: str = "bool"          # bool | int | float | str
    why_null: str | None = None       # fixed when the signal can never be measured in v1


# Fourteen digital signals, weights summing to 100 (doc 02 section 2.11.1).
DIGITAL_SIGNALS: dict[str, SignalSpec] = {
    s.key: s for s in (
        SignalSpec("has_website", 12, "PROBE", "bool"),
        SignalSpec("https_valid", 6, "PROBE", "bool"),
        SignalSpec("mobile_responsive", 8, "PROBE", "bool"),
        SignalSpec("page_weight", 6, "PROBE", "int"),
        SignalSpec("load_speed", 6, "PROBE", "int"),
        SignalSpec("content_freshness", 10, "PROBE", "int"),
        SignalSpec("online_booking", 12, "PROBE", "bool"),
        SignalSpec("payment_integration", 10, "PROBE", "bool"),
        SignalSpec("social_presence", 6, "PROBE", "bool"),
        SignalSpec("social_recency", 6, "READ", "int", "SOCIAL_NOT_FETCHED"),
        # No free source publishes review counts. Kept at weight, always None, excluded from
        # both sides of the average. Deleting them would renormalise the other twelve and make
        # every score computed before that point incomparable with every score after it.
        SignalSpec("review_volume", 6, "NONE", "int", "NO_FREE_SOURCE_IN_V1"),
        SignalSpec("review_recency", 4, "NONE", "int", "NO_FREE_SOURCE_IN_V1"),
        SignalSpec("job_postings_software", 4, "READ", "bool",
                   "NOT_MEASURED_AT_STANDARD_DEPTH"),
        SignalSpec("customer_portal", 4, "PROBE", "bool"),
    )
}

# Six operational signals, weights summing to 100 (doc 02 section 2.12).
OPERATIONAL_SIGNALS: dict[str, SignalSpec] = {
    s.key: s for s in (
        SignalSpec("staff_count", 25, "READ", "int"),
        SignalSpec("location_count", 15, "READ", "int"),
        SignalSpec("breadth", 20, "READ", "int"),
        SignalSpec("department_count", 15, "READ", "int"),
        SignalSpec("shift_pattern", 10, "READ", "str"),
        SignalSpec("regulatory_load", 15, "CATEGORY_PRIOR", "int"),
    )
}

# The keys a model may attach to a finding. `breadth` is measured through one of these two.
_BREADTH_KEYS = ("service_count", "sku_count")

SIGNAL_TYPES: dict[str, str] = {
    **{k: s.value_type for k, s in DIGITAL_SIGNALS.items()},
    **{k: s.value_type for k, s in OPERATIONAL_SIGNALS.items()},
    "service_count": "int",
    "sku_count": "int",
    "regulatory_registration": "bool",
}

# What a model is invited to attach, per doc 02 section 2.10.4. Anything else is dropped with
# UNKNOWN_SIGNAL_KEY rather than silently stored, because a signal key the scorer has never
# heard of is a measurement nothing will ever read.
MODEL_SIGNAL_KEYS: frozenset[str] = frozenset({
    "department_count", "location_count", "staff_count", "service_count", "sku_count",
    "shift_pattern", "online_booking", "payment_integration", "customer_portal",
    "social_presence", "regulatory_registration", "job_postings_software",
})


def coerce_signal(key: str, value: Any) -> Any | None:
    """Turn the string the schema forces onto every signal value into its declared type.

    Gemini's schema dialect cannot express `string | number | boolean`, so `signal_value`
    arrives as "4" or "false". A registry that knows `department_count` is an integer is a
    place that coercion can be tested, and "the model returned 4 as a float" stops being a
    class of bug. Returns None when the value cannot be coerced; the caller keeps the finding
    and drops the signal.
    """
    declared = SIGNAL_TYPES.get(key)
    if declared is None or value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if declared == "bool":
            if text.lower() in {"true", "yes", "1", "present", "found"}:
                return True
            if text.lower() in {"false", "no", "0", "absent", "none", "not found"}:
                return False
            return None
        if declared == "int":
            return int(float(text))
        if declared == "float":
            return float(text)
        return text
    except (TypeError, ValueError):
        return None


# ===========================================================================
# Rubrics
# ===========================================================================

def _bucket(value: float, table: Sequence[tuple[float, float]], *, above: float) -> float:
    """First threshold the value is at or below wins; `above` is the fall-through."""
    for threshold, score in table:
        if value <= threshold:
            return score
    return above


_PAGE_WEIGHT = ((500_000, 1.0), (1_500_000, 0.8), (3_000_000, 0.5), (6_000_000, 0.25))
_LOAD_SPEED = ((1_500, 1.0), (3_000, 0.75), (6_000, 0.4), (12_000, 0.15))
_FRESHNESS = ((90, 1.0), (365, 0.7), (730, 0.3))
_SOCIAL_RECENCY = ((90, 1.0), (365, 0.6))
_STAFF = ((5, 0.10), (20, 0.25), (50, 0.55), (150, 0.80), (500, 0.95))
_LOCATIONS = ((1, 0.20), (2, 0.45), (5, 0.70), (15, 0.90))
_DEPARTMENTS = ((1, 0.10), (3, 0.35), (6, 0.60), (12, 0.85))
_SERVICE_BREADTH = ((3, 0.15), (8, 0.35), (15, 0.55), (30, 0.80))
_SKU_BREADTH = ((15, 0.15), (60, 0.35), (200, 0.55), (1000, 0.80))

_SHIFT_PATTERN = {
    "SINGLE": 0.30, "EXTENDED": 0.50, "TWO_SHIFT": 0.60, "SEVEN_DAY": 0.75, "24X7": 1.00,
}

# Categories that sell stock rather than services. A hospital with 28 specialities and a
# distributor with 28 SKUs are not comparable, and one bucket table would score the
# distributor as though it were the hospital.
_SKU_CATEGORIES = frozenset({"MANUFACTURER", "DISTRIBUTOR", "RETAIL_STORE", "BAKERY",
                             "VEHICLE_DEALER", "RESTAURANT"})

REGULATORY_PRIOR: dict[str, float] = {
    "HOSPITAL": 0.85, "DIAGNOSTIC_CENTER": 0.75, "COLLEGE": 0.70, "MANUFACTURER": 0.70,
    "SCHOOL": 0.65, "VEHICLE_DEALER": 0.50, "HOTEL": 0.45, "DISTRIBUTOR": 0.45,
    "RESTAURANT": 0.35, "REAL_ESTATE_AGENCY": 0.35, "GARAGE": 0.30, "BAKERY": 0.25,
    "RETAIL_STORE": 0.25, "OTHER": 0.30,
}

SIZE_SUBSCORE: dict[str, float | None] = {
    "LARGE": 100.0, "MEDIUM": 80.0, "SMALL": 35.0, "MICRO": 10.0, "UNKNOWN": None,
}

# A fact about Sagar, not about the business: which categories he has a module map and a demo
# path for today. It can never become a finding or a message sentence.
INDUSTRY_FIT_CATEGORY: dict[str, float] = {
    "HOSPITAL": 95, "COLLEGE": 92, "SCHOOL": 90, "MANUFACTURER": 88, "DISTRIBUTOR": 88,
    "DIAGNOSTIC_CENTER": 85, "VEHICLE_DEALER": 80, "BAKERY": 60, "RETAIL_STORE": 60,
    "GARAGE": 55, "HOTEL": 55, "REAL_ESTATE_AGENCY": 50, "RESTAURANT": 45, "OTHER": 30,
}
INDUSTRY_FIT_INDUSTRY: dict[str, float] = {
    "HEALTHCARE": 85, "EDUCATION": 85, "MANUFACTURING": 80, "DISTRIBUTION": 80,
    "AUTOMOBILE": 70, "RETAIL": 60, "HOSPITALITY": 50, "REAL_ESTATE": 45,
    "PROFESSIONAL_SERVICES": 40, "OTHER": 30,
}

CONFIDENCE_MULTIPLIER: dict[str, float] = {"HIGH": 1.00, "MEDIUM": 0.90, "LOW": 0.75}

OPPORTUNITY_WEIGHTS: dict[str, float] = {
    "size_band": 20, "operational_complexity": 25, "digital_gap": 25,
    "contactability": 15, "industry_fit": 15,
}

COMPONENT_LABEL: dict[str, str] = {
    "operational_complexity": "Operational complexity",
    "digital_gap": "Digital gap",
    "size_band": "Size band",
    "contactability": "Contactability",
    "industry_fit": "Industry fit",
}


# ===========================================================================
# The coverage rule
# ===========================================================================

def weighted_coverage(components: Mapping[str, tuple[float | None, float]], *,
                      min_coverage: float) -> tuple[int | None, int]:
    """Weighted mean over the components that have a value, plus the coverage that produced it.

    Returns (None, coverage) when too little was measured to mean anything. That None is the
    whole point: the report renders it as an em dash, and an em dash is the honest answer. A
    zero here would be a claim that the business has no digital footprint, and because the
    opportunity score rewards a low digital maturity, that claim would push an unexamined
    business to the top of the exact list Sagar works down first.
    """
    measured = {k: (v, w) for k, (v, w) in components.items() if v is not None}
    measured_weight = sum(w for _, w in measured.values())
    total_weight = sum(w for _, w in components.values())
    coverage = round_half_up(100.0 * measured_weight / total_weight) if total_weight else 0
    if measured_weight < min_coverage or measured_weight <= 0:
        return None, coverage
    return round_half_up(
        100.0 * sum(v * w for v, w in measured.values()) / measured_weight
    ), coverage


# ===========================================================================
# digital_maturity and operational_complexity
# ===========================================================================

@dataclass(slots=True)
class SignalReading:
    """One signal as it will be stored in `opportunities.signals_json`.

    `why_null` is the difference between "we checked and there is no booking flow" and "we
    never looked", and the report's em dash tooltip is rendered from it.
    """
    key: str
    value: float | None
    weight: float
    basis: str
    raw: Any = None
    finding_id: str | None = None
    why_null: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out = {"key": self.key, "value": self.value, "weight": self.weight,
               "basis": self.basis, "raw": self.raw, "finding_id": self.finding_id}
        if self.value is None and self.why_null:
            out["why_null"] = self.why_null
        return out


def normalise_digital(key: str, raw: Any) -> float | None:
    """Map one raw digital measurement onto [0.0, 1.0], or None for not measured."""
    if raw is None:
        return None
    spec = DIGITAL_SIGNALS.get(key)
    if spec is None:
        return None
    if spec.value_type == "bool":
        return 1.0 if bool(raw) else 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if key == "page_weight":
        return _bucket(value, _PAGE_WEIGHT, above=0.0)
    if key == "load_speed":
        return _bucket(value, _LOAD_SPEED, above=0.0)
    if key == "content_freshness":
        # Days since the newest dated signal. No dated signal at all is None, not 0: a
        # brochure site with no dates is not a stale site, it is a site whose staleness we
        # cannot measure, and scoring it 0 rewards it with a larger digital gap.
        return _bucket(value, _FRESHNESS, above=0.0)
    if key == "social_recency":
        return _bucket(value, _SOCIAL_RECENCY, above=0.2)
    if key == "review_volume":
        for threshold, score in ((200, 1.0), (75, 0.8), (25, 0.55), (5, 0.3), (1, 0.1)):
            if value >= threshold:
                return score
        return 0.0
    if key == "review_recency":
        return _bucket(value, _SOCIAL_RECENCY, above=0.2)
    return None


def normalise_operational(key: str, raw: Any, *, category: str) -> float | None:
    """Map one raw operational measurement onto [0.0, 1.0], or None for not measured."""
    if raw is None:
        return None
    if key == "shift_pattern":
        return _SHIFT_PATTERN.get(str(raw).upper())
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if key == "staff_count":
        return _bucket(value, _STAFF, above=1.0)
    if key == "location_count":
        return _bucket(value, _LOCATIONS, above=1.0)
    if key == "department_count":
        return _bucket(value, _DEPARTMENTS, above=1.0)
    if key == "breadth":
        table = _SKU_BREADTH if category in _SKU_CATEGORIES else _SERVICE_BREADTH
        return _bucket(value, table, above=1.0)
    if key == "regulatory_load":
        return min(1.0, value)
    return None


def digital_maturity(signals: Mapping[str, Any],
                     *, finding_ids: Mapping[str, str] | None = None,
                     why_null: Mapping[str, str] | None = None,
                     ) -> tuple[int | None, int, list[SignalReading]]:
    """0-100 over the fourteen weighted digital signals, plus coverage and the readings.

    `signals` maps a signal key to its raw measurement, or to None where the pipeline looked
    and could not measure it. A key that is absent entirely is treated the same as None and
    carries its registry `why_null`.
    """
    finding_ids = finding_ids or {}
    why_null = why_null or {}
    readings: list[SignalReading] = []
    components: dict[str, tuple[float | None, float]] = {}
    for key, spec in DIGITAL_SIGNALS.items():
        raw = signals.get(key)
        value = normalise_digital(key, raw)
        components[key] = (value, spec.weight)
        readings.append(SignalReading(
            key=key, value=value, weight=spec.weight, basis=spec.basis, raw=raw,
            finding_id=finding_ids.get(key),
            why_null=None if value is not None else (why_null.get(key) or spec.why_null
                                                     or "NOT_MEASURED_AT_STANDARD_DEPTH"),
        ))
    value, coverage = weighted_coverage(components, min_coverage=MIN_DIGITAL_COVERAGE)
    return value, coverage, readings


def operational_complexity(signals: Mapping[str, Any], *, category: str,
                           finding_ids: Mapping[str, str] | None = None,
                           why_null: Mapping[str, str] | None = None,
                           ) -> tuple[int | None, int, list[SignalReading]]:
    """0-100 over the six weighted operational signals, plus coverage and the readings.

    `regulatory_load` is the one component that is always measurable, because the category
    prior always exists. It is marked CATEGORY_PRIOR in the breakdown and, per doc 02 section
    2.1.3, can never be written into research_findings and can never become a message
    sentence: it is a fact about hospitals, not about this hospital.
    """
    finding_ids = finding_ids or {}
    why_null = why_null or {}
    signals = dict(signals)

    if signals.get("breadth") is None:
        for key in _BREADTH_KEYS:
            if signals.get(key) is not None:
                signals["breadth"] = signals[key]
                if key in finding_ids:
                    finding_ids = {**finding_ids, "breadth": finding_ids[key]}
                break

    if signals.get("regulatory_load") is None:
        prior = REGULATORY_PRIOR.get(category, REGULATORY_PRIOR["OTHER"])
        observed = signals.get("regulatory_registration_count") or 0
        signals["regulatory_load"] = min(1.0, prior + 0.05 * float(observed))

    readings: list[SignalReading] = []
    components: dict[str, tuple[float | None, float]] = {}
    for key, spec in OPERATIONAL_SIGNALS.items():
        raw = signals.get(key)
        value = normalise_operational(key, raw, category=category)
        components[key] = (value, spec.weight)
        readings.append(SignalReading(
            key=key, value=value, weight=spec.weight, basis=spec.basis, raw=raw,
            finding_id=finding_ids.get(key),
            why_null=None if value is not None else (why_null.get(key) or spec.why_null
                                                     or "NOT_MEASURED_AT_STANDARD_DEPTH"),
        ))
    value, coverage = weighted_coverage(components, min_coverage=MIN_OPERATIONAL_COVERAGE)
    return value, coverage, readings


# ===========================================================================
# research_confidence
# ===========================================================================

SOURCE_TIER_POINTS = {"A": 3.0, "B": 2.0, "C": 1.0, "D": 0.5}
REQUIRED_DIMENSIONS = ("IDENTITY", "LOCATION", "SCALE", "OPERATIONS",
                       "DIGITAL_PRESENCE", "CONTACT")


def research_confidence(conn: sqlite3.Connection, business_id: str,
                        research_run_id: str) -> tuple[str, int, dict[str, Any]]:
    """HIGH / MEDIUM / LOW plus a percentage, from source count, authority and coverage.

    A dimension covered only by an UNKNOWN finding does not count towards coverage. That is
    the distinction the third finding kind exists to preserve - measured-and-missing is not
    the same as never-looked-at - and it is why coverage carries the largest of the three
    weights. Four sources that all say the same thing about identity are worth less than two
    that between them establish scale and operations.
    """
    rows = conn.execute(
        """
        SELECT f.dimension AS dimension, s.id AS source_id, s.authority_tier AS tier
          FROM research_findings f
          JOIN finding_sources fs ON fs.finding_id = f.id
          JOIN sources s          ON s.id = fs.source_id
         WHERE f.research_run_id = ? AND f.kind = 'OBSERVED'
        """,
        (research_run_id,),
    ).fetchall()

    source_ids = {r["source_id"] for r in rows}
    tiers = {r["tier"] for r in rows if r["tier"]}
    covered = {r["dimension"] for r in rows if r["dimension"] in REQUIRED_DIMENSIONS}

    source_score = min(1.0, len(source_ids) / 4.0)
    authority_score = min(1.0, sum(SOURCE_TIER_POINTS.get(t, 0.5) for t in tiers) / 5.0)
    coverage_score = len(covered) / len(REQUIRED_DIMENSIONS)
    pct = round_half_up(100 * (0.30 * source_score + 0.30 * authority_score
                               + 0.40 * coverage_score))

    run = conn.execute(
        "SELECT integrity, sufficiency FROM research_runs WHERE id = ?",
        (research_run_id,),
    ).fetchone()
    integrity = (run["integrity"] if run else "OK") or "OK"
    sufficiency = (run["sufficiency"] if run else None)

    # Four hard floors, each of which forces LOW regardless of the arithmetic.
    floors: list[str] = []
    if not rows:
        floors.append("NO_SOURCED_OBSERVATION")
    if tiers and tiers <= {"D"}:
        floors.append("ALL_SOURCES_TIER_D")
    if integrity == "DEGRADED":
        floors.append("INTEGRITY_DEGRADED")
    if sufficiency == "INSUFFICIENT":
        floors.append("SUFFICIENCY_INSUFFICIENT")

    if floors:
        band = "LOW"
    elif (pct >= 75 and len(source_ids) >= 3 and bool(tiers & {"A", "B"})
            and len(covered) >= 5):
        band = "HIGH"
    elif pct >= 50 and len(source_ids) >= 2 and len(covered) >= 3:
        band = "MEDIUM"
    else:
        band = "LOW"

    detail = {
        "distinct_sources": len(source_ids),
        "tiers": sorted(tiers),
        "covered_dimensions": sorted(covered),
        "missing_dimensions": [d for d in REQUIRED_DIMENSIONS if d not in covered],
        "source_score": round(source_score, 3),
        "authority_score": round(authority_score, 3),
        "coverage_score": round(coverage_score, 3),
        "floors": floors,
    }
    return band, pct, detail


# ===========================================================================
# opportunity_score
# ===========================================================================

@dataclass(slots=True)
class ScoreComponent:
    """What one component contributed, and the stored row that justifies it."""
    component: str
    label: str
    points: float
    of: float
    subscore: float | None
    basis: str                       # OBSERVED | DERIVED | CATEGORY_PRIOR | OPERATOR_CONFIG
    because_finding_id: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OpportunityScore:
    """The stored result of one scoring pass. Nothing here is recomputed at render time."""
    business_id: str
    research_run_id: str
    score: int | None
    band: str | None
    confidence: str
    confidence_pct: int
    digital_maturity: int | None
    digital_coverage_pct: int
    operational_complexity: int | None
    operational_coverage_pct: int
    score_coverage_pct: int
    breakdown: list[ScoreComponent] = field(default_factory=list)
    signals: list[SignalReading] = field(default_factory=list)
    opportunity_id: str | None = None

    @property
    def breakdown_json(self) -> str:
        return json.dumps([c.to_dict() for c in self.breakdown], ensure_ascii=False)

    @property
    def signals_json(self) -> str:
        return json.dumps([s.to_dict() for s in self.signals], ensure_ascii=False)


def contactability(conn: sqlite3.Connection, business_id: str, *,
                   website_domain: str | None) -> tuple[float | None, str | None, str | None]:
    """0-100 from the best contact evidence on record, or None if discovery never ran.

    Read before verification, so `human_verified` is not yet meaningful and `is_active = 1` is
    the filter. An unreachable prospect is worth nothing regardless of fit, which is why this
    is a component of the score rather than a filter applied after it.
    """
    rows = conn.execute(
        """
        SELECT c.id, c.kind, c.domain, c.source_id, c.confidence, s.source_type, s.authority_tier
          FROM business_contacts c
          LEFT JOIN sources s ON s.id = c.source_id
         WHERE c.business_id = ? AND c.is_active = 1 AND c.valid = 1
        """,
        (business_id,),
    ).fetchall()
    if not rows:
        # Nothing usable is 0; contact discovery never having run is None. The two must not
        # collapse: one is a measurement, the other is our own failure to measure.
        probed = conn.execute(
            "SELECT 1 FROM sources WHERE business_id = ? LIMIT 1", (business_id,)
        ).fetchone()
        return (0.0, "No usable contact point found", None) if probed else (None, None, None)

    emails = [r for r in rows if r["kind"] == "EMAIL"]
    phones = [r for r in rows if r["kind"] in ("PHONE", "WHATSAPP")]
    free_providers = {"gmail.com", "yahoo.com", "yahoo.in", "outlook.com", "hotmail.com",
                      "rediffmail.com", "live.com"}

    for row in emails:
        domain = (row["domain"] or "").lower()
        if website_domain and domain and domain.endswith(website_domain.lower()):
            return 100.0, "Email on the business's own domain", row["id"]
    for row in emails:
        if (row["authority_tier"] or "") in ("A", "C") and \
                (row["source_type"] or "") in ("REGISTRY", "DIRECTORY", "LISTING"):
            return 85.0, "Email published on a registry or association listing", row["id"]
    if emails:
        row = emails[0]
        domain = (row["domain"] or "").lower()
        if domain in free_providers:
            return 70.0, "Free-provider email published by the business", row["id"]
        return 85.0, "Email published by the business", row["id"]
    if phones:
        sources = {r["source_id"] for r in phones if r["source_id"]}
        if len(sources) >= 2:
            return 40.0, "Phone corroborated by two or more sources", phones[0]["id"]
        return 25.0, "Phone from a single source", phones[0]["id"]
    return 0.0, "No usable contact point found", None


def industry_fit(category: str, industry: str) -> tuple[float, str]:
    """Category first, industry as the fallback when the category is OTHER."""
    if category and category != "OTHER" and category in INDUSTRY_FIT_CATEGORY:
        return INDUSTRY_FIT_CATEGORY[category], f"Industry fit ({category})"
    value = INDUSTRY_FIT_INDUSTRY.get(industry, INDUSTRY_FIT_INDUSTRY["OTHER"])
    return value, f"Industry fit ({industry})"


def opportunity_score(components: Mapping[str, tuple[float | None, float]], *,
                      multiplier: float) -> tuple[int | None, str | None, int, float | None]:
    """Renormalised weighted mean, times the confidence multiplier, clamped and banded.

    The multiplier applies to the whole score rather than to individual components, because
    thin evidence weakens every component at once. Its practical effect is that a LOW-
    confidence business needs a raw 107 to reach HIGH, which it cannot - so no LOW-confidence
    business ever renders a green HIGH badge on the report.
    """
    # weighted_coverage takes fractions and returns an integer; here the raw total must stay a
    # float, because rounding before the multiplier and again after it moves a 74.5 into a
    # different band than the formula says it belongs in. Coverage still comes from the shared
    # function, so the three metrics degrade identically under missing data.
    fractions = {k: (None if v is None else v / 100.0, w)
                 for k, (v, w) in components.items()}
    _, coverage = weighted_coverage(fractions, min_coverage=MIN_SCORE_COVERAGE)

    measured = {k: (v, w) for k, (v, w) in components.items() if v is not None}
    measured_weight = sum(w for _, w in measured.values())
    if measured_weight < MIN_SCORE_COVERAGE:
        return None, None, coverage, None
    raw = sum(v * w for v, w in measured.values()) / measured_weight
    score = max(0, min(100, round_half_up(raw * multiplier)))
    return score, band_for_score(score), coverage, float(raw)


# ===========================================================================
# Reading the signals back out of the findings
# ===========================================================================

def signals_from_findings(conn: sqlite3.Connection, research_run_id: str
                          ) -> tuple[dict[str, Any], dict[str, str]]:
    """Every stored signal for a run, as {key: value} plus {key: finding_id}.

    The scorer reads signals by key rather than by pattern-matching a label, because a label
    is prose written by a model and a key is a contract.
    """
    values: dict[str, Any] = {}
    ids: dict[str, str] = {}
    registrations = 0
    for row in conn.execute(
        "SELECT id, signal_key, signal_value FROM research_findings "
        "WHERE research_run_id = ? AND signal_key IS NOT NULL AND kind <> 'UNKNOWN' "
        "ORDER BY ordinal",
        (research_run_id,),
    ):
        key = row["signal_key"]
        value = coerce_signal(key, row["signal_value"])
        if value is None:
            continue
        if key == "regulatory_registration":
            registrations += 1 if value else 0
            continue
        values.setdefault(key, value)
        ids.setdefault(key, row["id"])
    if registrations:
        values["regulatory_registration_count"] = registrations
    return values, ids


def score_business(conn: sqlite3.Connection, business_id: str, research_run_id: str, *,
                   cfg: Config | None = None, campaign_id: str | None = None,
                   actor: str | None = None) -> OpportunityScore:
    """Turn one completed research run into the number Sagar sorts by, and store it.

    Writes one `opportunities` row, marks the previous one superseded, copies the four
    denormalised columns onto `businesses` so the grid sorts without a join, and returns the
    score with its full breakdown. The narrative half of the row is written later by
    `assess_opportunity`; a quota pause between the two loses no scoring work.
    """
    business = conn.execute(
        "SELECT id, name, category, industry, size_band, website_domain, website_status "
        "FROM businesses WHERE id = ?", (business_id,)
    ).fetchone()
    if business is None:
        raise ValueError(f"no such business: {business_id}")

    category = business["category"] or "OTHER"
    industry = business["industry"] or "OTHER"

    raw_signals, finding_ids = signals_from_findings(conn, research_run_id)
    why_null: dict[str, str] = {}

    # A definite "no website" is nine real zeros; an unreachable one is nine Nones. The
    # difference is whether a check ran and returned a negative or never returned at all.
    site_dependent = ("has_website", "https_valid", "mobile_responsive", "page_weight",
                      "load_speed", "content_freshness", "online_booking",
                      "payment_integration", "customer_portal")
    if business["website_status"] == "ABSENT":
        for key in site_dependent:
            raw_signals.setdefault(key, False if DIGITAL_SIGNALS[key].value_type == "bool"
                                   else 0)
        raw_signals["has_website"] = False
    elif business["website_status"] == "UNKNOWN":
        for key in site_dependent:
            if key not in raw_signals:
                why_null[key] = "SITE_UNREACHABLE"

    dm, dm_cov, dm_readings = digital_maturity(raw_signals, finding_ids=finding_ids,
                                               why_null=why_null)
    oc, oc_cov, oc_readings = operational_complexity(raw_signals, category=category,
                                                     finding_ids=finding_ids,
                                                     why_null=why_null)
    confidence, confidence_pct, confidence_detail = research_confidence(
        conn, business_id, research_run_id)

    components: dict[str, tuple[float | None, float]] = {}
    breakdown: list[ScoreComponent] = []

    size_sub = SIZE_SUBSCORE.get(business["size_band"] or "UNKNOWN")
    components["size_band"] = (size_sub, OPPORTUNITY_WEIGHTS["size_band"])

    components["operational_complexity"] = (
        None if oc is None else float(oc), OPPORTUNITY_WEIGHTS["operational_complexity"])

    digital_gap = None if dm is None else float(100 - dm)
    components["digital_gap"] = (digital_gap, OPPORTUNITY_WEIGHTS["digital_gap"])

    contact_sub, contact_detail, contact_id = contactability(
        conn, business_id, website_domain=business["website_domain"])
    components["contactability"] = (contact_sub, OPPORTUNITY_WEIGHTS["contactability"])

    fit_sub, fit_label = industry_fit(category, industry)
    components["industry_fit"] = (fit_sub, OPPORTUNITY_WEIGHTS["industry_fit"])

    multiplier = CONFIDENCE_MULTIPLIER.get(confidence, 0.75)
    score, band, score_cov, raw_score = opportunity_score(components, multiplier=multiplier)

    measured_weight = sum(w for v, w in components.values() if v is not None) or 1.0

    def _points(key: str) -> float:
        """What this component put on the board, out of its own weight.

        Not renormalised: the breakdown shows points out of the component's own weight and
        the multiplier row carries the raw total, so `sum(points) / sum(measured weights)`
        reproduces the raw score by hand. A renormalised points column would not add up to
        anything a reader could check.
        """
        value, weight = components[key]
        if value is None:
            return 0.0
        return round((value / 100.0) * weight, 2)

    breakdown.append(ScoreComponent(
        "size_band", f"Size band ({business['size_band']})", _points("size_band"),
        OPPORTUNITY_WEIGHTS["size_band"], size_sub,
        "OBSERVED" if size_sub is not None else "DERIVED",
        finding_ids.get("staff_count"),
        None if size_sub is not None else "Size band unknown; component excluded"))
    breakdown.append(ScoreComponent(
        "operational_complexity", COMPONENT_LABEL["operational_complexity"],
        _points("operational_complexity"), OPPORTUNITY_WEIGHTS["operational_complexity"],
        None if oc is None else float(oc), "OBSERVED",
        finding_ids.get("department_count") or finding_ids.get("staff_count"),
        f"operational complexity {oc} of 100, coverage {oc_cov}%" if oc is not None
        else f"coverage {oc_cov}% is below the floor of {MIN_OPERATIONAL_COVERAGE:g}"))
    breakdown.append(ScoreComponent(
        "digital_gap", COMPONENT_LABEL["digital_gap"], _points("digital_gap"),
        OPPORTUNITY_WEIGHTS["digital_gap"], digital_gap, "DERIVED",
        finding_ids.get("online_booking") or finding_ids.get("has_website"),
        f"digital maturity {dm} of 100, coverage {dm_cov}%" if dm is not None
        else f"coverage {dm_cov}% is below the floor of {MIN_DIGITAL_COVERAGE:g}"))
    breakdown.append(ScoreComponent(
        "contactability", COMPONENT_LABEL["contactability"], _points("contactability"),
        OPPORTUNITY_WEIGHTS["contactability"], contact_sub,
        "OBSERVED" if contact_sub is not None else "DERIVED", contact_id, contact_detail))
    breakdown.append(ScoreComponent(
        "industry_fit", fit_label, _points("industry_fit"),
        OPPORTUNITY_WEIGHTS["industry_fit"], fit_sub, "OPERATOR_CONFIG", None,
        "Module map and demo exist for this category"))
    breakdown.append(ScoreComponent(
        "_multiplier", f"Research confidence {confidence}", 0.0, 0.0, None, "DERIVED", None,
        f"x{multiplier:.2f} applied to a raw {raw_score:.1f}" if raw_score is not None
        else f"score not computed: coverage {score_cov}% is below the floor "
             f"of {MIN_SCORE_COVERAGE:g}"))

    result = OpportunityScore(
        business_id=business_id, research_run_id=research_run_id, score=score, band=band,
        confidence=confidence, confidence_pct=confidence_pct,
        digital_maturity=dm, digital_coverage_pct=dm_cov,
        operational_complexity=oc, operational_coverage_pct=oc_cov,
        score_coverage_pct=score_cov, breakdown=breakdown,
        signals=dm_readings + oc_readings,
    )

    opportunity_id = new_id_for("opportunities")
    conn.execute(
        "UPDATE opportunities SET is_current = 0, superseded_by = ? "
        "WHERE business_id = ? AND is_current = 1",
        (opportunity_id, business_id),
    )
    conn.execute(
        """
        INSERT INTO opportunities
            (id, business_id, research_run_id, campaign_id, score, band, confidence,
             confidence_pct, digital_maturity, operational_complexity, digital_coverage_pct,
             operational_coverage_pct, score_coverage_pct, score_breakdown, signals_json,
             weights_version, computed_at, is_current)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
        """,
        (opportunity_id, business_id, research_run_id, campaign_id, score, band, confidence,
         confidence_pct, dm, oc, dm_cov, oc_cov, score_cov, result.breakdown_json,
         result.signals_json, WEIGHTS_VERSION, utc_now()),
    )
    conn.execute(
        "UPDATE businesses SET digital_maturity = ?, operational_complexity = ?, "
        "opportunity_score = ?, opportunity_band = ?, research_confidence = ?, "
        "research_confidence_pct = ?, updated_at = ? WHERE id = ?",
        (dm, oc, score, band, confidence, confidence_pct, utc_now(), business_id),
    )
    result.opportunity_id = opportunity_id

    log.info("scored %s: score=%s band=%s dm=%s(%d%%) oc=%s(%d%%) confidence=%s(%d%%)",
             business["name"], score, band, dm, dm_cov, oc, oc_cov, confidence,
             confidence_pct)

    from . import audit as audit_mod                     # local: audit imports models only
    audit_mod.audit(
        conn, actor, "OPPORTUNITY_SCORED", "opportunities", opportunity_id,
        after={"score": score, "band": band, "confidence": confidence},
        business_id=business_id, campaign_id=campaign_id,
        detail={"digital_maturity": dm, "digital_coverage_pct": dm_cov,
                "operational_complexity": oc, "operational_coverage_pct": oc_cov,
                "score_coverage_pct": score_cov, "weights_version": WEIGHTS_VERSION,
                "confidence": confidence_detail},
    )
    return result


# ===========================================================================
# The reason string (doc 02 section 2.17.2)
# ===========================================================================

def first_clause(statement: str, *, limit: int = 90) -> str:
    """The first clause of a stored statement. Splits, never rewrites a word."""
    for sep in (". ", "; ", ", "):
        index = statement.find(sep)
        if 0 < index <= limit:
            return statement[:index]
    return statement[:limit].rstrip()


def top_reason(conn: sqlite3.Connection, business_id: str) -> tuple[str | None, str | None]:
    """One line explaining why this business is near the top, and the finding behind it.

    Every character returned is either a literal from COMPONENT_LABEL, a number out of
    score_breakdown, or the stored text of a finding that was validated against a source at
    research time. No model runs here. Asking the model for a one-line reason at report time
    would put an unsourced sentence next to a business name in the one table Sagar reads
    before deciding who to contact.
    """
    row = conn.execute(
        "SELECT score_breakdown FROM opportunities WHERE business_id = ? AND is_current = 1",
        (business_id,),
    ).fetchone()
    if row is None:
        return None, None
    try:
        breakdown = json.loads(row["score_breakdown"])
    except (TypeError, ValueError):
        return None, None
    if not isinstance(breakdown, list):
        return None, None

    findings = {
        r["id"]: r for r in conn.execute(
            "SELECT f.id, f.label, f.statement, f.weight, f.kind, "
            "       (SELECT COUNT(*) FROM finding_sources fs WHERE fs.finding_id = f.id) AS n "
            "  FROM research_findings f "
            " WHERE f.business_id = ? AND f.is_current = 1", (business_id,))
    }

    candidates = [c for c in breakdown
                  if c.get("component") != "_multiplier"
                  and c.get("basis") not in ("CATEGORY_PRIOR", "OPERATOR_CONFIG")
                  and (c.get("of") or 0) > 0]
    candidates.sort(key=lambda c: (c.get("points") or 0) / (c.get("of") or 1), reverse=True)

    for component in candidates:
        finding_id = component.get("because_finding_id")
        finding = findings.get(finding_id) if finding_id else None
        if finding is None or finding["kind"] != "OBSERVED" or not finding["n"]:
            continue
        text = finding["label"] or first_clause(finding["statement"])
        label = COMPONENT_LABEL.get(component["component"], component.get("label", ""))
        return (f"{label} {component['points']:g}/{component['of']:g} - {text}", finding_id)

    sourced = [f for f in findings.values() if f["kind"] == "OBSERVED" and f["n"]]
    if sourced:
        best = max(sourced, key=lambda f: f["weight"] or 0)
        return (best["label"] or first_clause(best["statement"])), best["id"]
    return None, None


# ===========================================================================
# MODULE_MAP (06-message-engine.md section 6.8) and the assessment call
# ===========================================================================

@dataclass(slots=True, frozen=True)
class ModuleProfile:
    """The fixed solution name and module list for one category. Not a model's choice."""
    solution_name: str
    module_keys: tuple[str, ...]
    relevant_area: str


MODULE_MAP: dict[str, ModuleProfile] = {
    "HOSPITAL": ModuleProfile(
        "Hospital Operations Platform",
        ("PATIENTS", "APPOINTMENTS", "DEPARTMENTS", "BILLING", "INVENTORY", "REPORTS"),
        "patient records, appointments and billing"),
    "SCHOOL": ModuleProfile(
        "School Management System",
        ("STUDENTS", "FEES", "ATTENDANCE", "STAFF", "TRANSPORT", "REPORTS"),
        "student records, fees and attendance"),
    "COLLEGE": ModuleProfile(
        "College Management System",
        ("ADMISSIONS", "STUDENTS", "DEPARTMENTS", "FEES", "EXAMINATIONS", "REPORTS"),
        "admissions, fees and examination records"),
    "MANUFACTURER": ModuleProfile(
        "Manufacturing Management Platform",
        ("INVENTORY", "PRODUCTION", "PURCHASING", "SALES", "QUALITY", "REPORTS"),
        "inventory, production and purchase tracking"),
    "DISTRIBUTOR": ModuleProfile(
        "Distribution Management System",
        ("INVENTORY", "ORDERS", "CUSTOMERS", "RECEIVABLES", "SALES", "REPORTS"),
        "inventory, orders and receivables"),
    "BAKERY": ModuleProfile(
        "Bakery Operations System",
        ("ORDERS", "PRODUCTION", "INVENTORY", "DELIVERY", "CUSTOMERS", "PAYMENTS"),
        "orders, production and delivery"),
    "RETAIL_STORE": ModuleProfile(
        "Retail Inventory and Sales System",
        ("INVENTORY", "VARIANTS", "PURCHASING", "SALES", "CUSTOMERS", "PROFITABILITY"),
        "stock, variants and sales"),
    "VEHICLE_DEALER": ModuleProfile(
        "Dealership Management System",
        ("INVENTORY", "PURCHASES", "EXPENSES", "SALES", "PROFIT", "CUSTOMERS"),
        "vehicle stock, purchases and sales"),
    "DIAGNOSTIC_CENTER": ModuleProfile(
        "Diagnostic Centre Operations Platform",
        ("PATIENTS", "TEST_ORDERS", "SAMPLES", "REPORTS", "BILLING", "INVENTORY"),
        "test orders, reports and billing"),
    "GARAGE": ModuleProfile(
        "Service Workshop Management System",
        ("JOB_CARDS", "SPARES", "LABOUR", "BILLING", "CUSTOMERS", "REPORTS"),
        "job cards, spare parts and billing"),
    "HOTEL": ModuleProfile(
        "Hotel Operations Platform",
        ("ROOMS", "BOOKINGS", "GUESTS", "HOUSEKEEPING", "BILLING", "REPORTS"),
        "bookings, room status and billing"),
    "RESTAURANT": ModuleProfile(
        "Restaurant Operations System",
        ("ORDERS", "TABLES", "MENU", "INVENTORY", "BILLING", "REPORTS"),
        "orders, inventory and billing"),
    "REAL_ESTATE_AGENCY": ModuleProfile(
        "Property Sales Management System",
        ("LISTINGS", "ENQUIRIES", "SITE_VISITS", "BOOKINGS", "PAYMENTS", "REPORTS"),
        "listings, enquiries and bookings"),
    "OTHER": ModuleProfile(
        "Custom Business Management System",
        ("DASHBOARD", "WORKFLOW", "FINANCE", "INVENTORY", "REPORTS", "ROLES", "AUDIT"),
        "day-to-day operations and reporting"),
}

MODULE_MAP_BY_INDUSTRY: dict[str, ModuleProfile] = {
    "HEALTHCARE": ModuleProfile(
        "Healthcare Operations Platform",
        ("PATIENTS", "APPOINTMENTS", "BILLING", "INVENTORY", "REPORTS"),
        "patient records and billing"),
    "EDUCATION": ModuleProfile(
        "Education Management System",
        ("STUDENTS", "FEES", "ATTENDANCE", "STAFF", "REPORTS"),
        "student records and fees"),
    "AUTOMOBILE": ModuleProfile(
        "Automotive Business Management System",
        ("INVENTORY", "PURCHASES", "SALES", "CUSTOMERS", "REPORTS"),
        "stock, sales and customers"),
    "MANUFACTURING": ModuleProfile(
        "Manufacturing Management Platform",
        ("INVENTORY", "PRODUCTION", "PURCHASING", "SALES", "REPORTS"),
        "inventory and production"),
    "RETAIL": ModuleProfile(
        "Retail Management System",
        ("INVENTORY", "SALES", "PURCHASING", "CUSTOMERS", "REPORTS"),
        "stock and sales"),
    "HOSPITALITY": ModuleProfile(
        "Hospitality Operations System",
        ("BOOKINGS", "ORDERS", "INVENTORY", "BILLING", "REPORTS"),
        "bookings and billing"),
    "DISTRIBUTION": ModuleProfile(
        "Distribution Management System",
        ("INVENTORY", "ORDERS", "RECEIVABLES", "CUSTOMERS", "REPORTS"),
        "orders and receivables"),
    "REAL_ESTATE": ModuleProfile(
        "Property Business Management System",
        ("LISTINGS", "ENQUIRIES", "PAYMENTS", "CUSTOMERS", "REPORTS"),
        "listings and enquiries"),
    "PROFESSIONAL_SERVICES": ModuleProfile(
        "Practice Management System",
        ("CLIENTS", "ENGAGEMENTS", "DOCUMENTS", "BILLING", "REPORTS"),
        "client records and billing"),
    "OTHER": MODULE_MAP["OTHER"],
}


def module_profile(category: str, industry: str) -> ModuleProfile:
    """Category first, industry fallback only when the category is OTHER."""
    if category and category != "OTHER" and category in MODULE_MAP:
        return MODULE_MAP[category]
    return MODULE_MAP_BY_INDUSTRY.get(industry, MODULE_MAP["OTHER"])


ASSESS_PROMPT_VERSION = "assess-v1"

ASSESS_SYSTEM = """\
You write the four narrative fields of a software opportunity assessment for one business,
from findings that have already been verified against their sources.

You are given the business, its findings by kind, its computed scores, and the fixed solution
name and module list for its category. You do not choose the solution name and you do not
choose which modules exist. Both are supplied.

FIELDS
  potential_problem  What operational difficulty the findings suggest. One or two sentences,
                     conditional or observational, never diagnostic. Write "coordination
                     across four departments with separate records" - not "your records are a
                     mess" and not "you are using Excel".
  potential_solution Copy the supplied solution_name exactly. Do not reword it.
  expected_benefit   What would change if the modules were in place. One or two sentences,
                     concrete, no numbers, no percentages, no promises.
  modules            Rank the supplied module_keys for this business, most relevant first.
                     Return every one of them, reordered. Do not add or drop any. Give each a
                     rationale of at most twenty words and, where one exists, the finding id
                     that justifies its rank.

RULES
- Every sentence in potential_problem and expected_benefit must be supported by a supplied
  OBSERVED or INFERRED finding, and you must return the finding ids you used.
- Never use an UNKNOWN finding. Never write a sentence a reader would take as a claim about
  something listed as UNKNOWN.
- Never state a number, percentage, currency amount, timescale or guarantee.
- Never name a person, an email address or a phone number.
- Never mention another business, a client, a case study or a competitor.
- Never mention price.
- If the findings do not support a problem statement, set potential_problem to null and set
  refusal_reason. A null renders as an em dash in the report, which is correct. An invented
  problem statement reaches a real hospital administrator.

OUTPUT
JSON only, matching the supplied schema.
"""

ASSESS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "required": ["potential_problem", "potential_solution", "expected_benefit",
                 "modules", "finding_ids_used", "refusal_reason"],
    "propertyOrdering": ["potential_problem", "potential_solution", "expected_benefit",
                         "modules", "finding_ids_used", "refusal_reason"],
    "properties": {
        "potential_problem": {"type": "STRING", "nullable": True, "maxLength": 400},
        "potential_solution": {"type": "STRING", "maxLength": 120},
        "expected_benefit": {"type": "STRING", "nullable": True, "maxLength": 400},
        "modules": {
            "type": "ARRAY", "minItems": 1, "maxItems": 8,
            "items": {
                "type": "OBJECT",
                "required": ["module", "rationale", "because_finding_id"],
                "propertyOrdering": ["module", "rationale", "because_finding_id"],
                "properties": {
                    "module": {"type": "STRING", "maxLength": 40},
                    "rationale": {"type": "STRING", "nullable": True, "maxLength": 240},
                    "because_finding_id": {"type": "STRING", "nullable": True,
                                           "maxLength": 40},
                },
            },
        },
        "finding_ids_used": {"type": "ARRAY", "items": {"type": "STRING"}},
        "refusal_reason": {"type": "STRING", "nullable": True, "maxLength": 200},
    },
}

_DIGIT = re.compile(r"\d")


def build_assess_user_prompt(conn: sqlite3.Connection, business: sqlite3.Row,
                             score: OpportunityScore, profile: ModuleProfile) -> str:
    """The user turn. Findings only - this call never sees raw page text.

    The injection surface of section 2.9 does not exist here and neither does the PII surface:
    every input is a finding statement the validator already checked against a redacted
    document.
    """
    rows = conn.execute(
        "SELECT id, kind, dimension, label, statement, confidence, confidence_pct "
        "  FROM research_findings WHERE research_run_id = ? AND is_current = 1 "
        " ORDER BY kind, ordinal", (score.research_run_id,),
    ).fetchall()
    by_kind: dict[str, list[sqlite3.Row]] = {"OBSERVED": [], "INFERRED": [], "UNKNOWN": []}
    for row in rows:
        by_kind.setdefault(row["kind"], []).append(row)

    lines = [
        f"BUSINESS   {business['name']}, {business['city']}, "
        f"{business['category']} / {business['industry']}, size {business['size_band']}",
        f"SCORES     opportunity {score.score if score.score is not None else '-'} "
        f"({score.band or '-'}) - digital maturity "
        f"{score.digital_maturity if score.digital_maturity is not None else '-'} - "
        f"operational complexity "
        f"{score.operational_complexity if score.operational_complexity is not None else '-'}",
        f"           research confidence {score.confidence} ({score.confidence_pct})",
        "",
        "OBSERVED FINDINGS - you may rely on these plainly",
    ]
    for row in by_kind["OBSERVED"]:
        lines.append(f"  [{row['id']}] ({row['confidence']}, {row['confidence_pct']}) "
                     f"{row['dimension']}")
        lines.append(f"      {row['statement']}")
    lines += ["", "INFERRED FINDINGS - you may rely on these with hedged wording"]
    for row in by_kind["INFERRED"]:
        lines.append(f"  [{row['id']}] ({row['confidence']}, {row['confidence_pct']}) "
                     f"{row['dimension']}")
        lines.append(f"      {row['statement']}")
    lines += ["", "UNKNOWN - DO NOT MENTION, DO NOT ALLUDE TO"]
    for row in by_kind["UNKNOWN"]:
        lines.append(f"  [{row['id']}] {row['statement']}")
    lines += [
        "",
        "FIXED FOR THIS CATEGORY - copy, do not invent",
        f'  solution_name: "{profile.solution_name}"',
        f"  module_keys:   {', '.join(profile.module_keys)}",
        "",
        "Return the JSON now.",
    ]
    return "\n".join(lines)


def assess_opportunity(conn: sqlite3.Connection, business_id: str, score: OpportunityScore, *,
                       client: Any, cfg: Config | None = None,
                       campaign_id: str | None = None,
                       actor: str | None = None) -> dict[str, Any]:
    """Write the narrative half of the opportunity row and its ranked modules.

    Everything the model returns is checked against stored rows before it is kept: the
    solution name must equal the map's, the module set must be a permutation of the map's, a
    cited finding must exist and must not be UNKNOWN, and a narrative field containing a
    digit, an email, a phone or a person's name is nulled rather than repaired. A null
    renders as an em dash. A repaired sentence reaches a real business.
    """
    from . import audit as audit_mod
    from .llm import assert_no_pii

    business = conn.execute(
        "SELECT id, name, city, category, industry, size_band FROM businesses WHERE id = ?",
        (business_id,),
    ).fetchone()
    if business is None:
        raise ValueError(f"no such business: {business_id}")
    profile = module_profile(business["category"] or "OTHER", business["industry"] or "OTHER")

    user = build_assess_user_prompt(conn, business, score, profile)
    assert_no_pii(user, where="ASSESS/user", protect=[business["name"]])

    response = client.complete_json(
        system=ASSESS_SYSTEM, user=user, schema=ASSESS_SCHEMA, purpose="ASSESS",
        prompt_version=ASSESS_PROMPT_VERSION, temperature=0.3, max_output_tokens=8192,
        thinking_budget=-1, business_id=business_id, campaign_id=campaign_id,
        entity_table="opportunities", entity_id=score.opportunity_id,
        protect=[business["name"]],
    )
    payload = response.data
    drift: dict[str, int] = {}

    # 1. The solution name is the map's, always.
    if (payload.get("potential_solution") or "").strip() != profile.solution_name:
        drift["solution_name_drift"] = 1
    solution = profile.solution_name

    # 2. The module set is a permutation of the map's: unknown keys dropped, missing keys
    #    appended in map order.
    allowed = list(profile.module_keys)
    returned = [m for m in (payload.get("modules") or []) if isinstance(m, dict)]
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in returned:
        key = str(entry.get("module") or "").strip().upper()
        if key in allowed and key not in seen:
            seen.add(key)
            ordered.append({"module": key, "rationale": entry.get("rationale"),
                            "because_finding_id": entry.get("because_finding_id")})
    if len(ordered) != len(returned):
        drift["module_set_drift"] = len(returned) - len(ordered)
    for key in allowed:
        if key not in seen:
            ordered.append({"module": key, "rationale": None, "because_finding_id": None})
            drift["module_set_drift"] = drift.get("module_set_drift", 0) + 1

    # 3. Cited findings must exist in this run and must not be UNKNOWN.
    usable = {
        row["id"] for row in conn.execute(
            "SELECT id FROM research_findings WHERE research_run_id = ? AND kind <> 'UNKNOWN'",
            (score.research_run_id,))
    }
    used = [fid for fid in (payload.get("finding_ids_used") or []) if fid in usable]
    if len(used) != len(payload.get("finding_ids_used") or []):
        drift["unknown_finding_cited"] = 1

    problem = (payload.get("potential_problem") or None)
    benefit = (payload.get("expected_benefit") or None)
    refusal = (payload.get("refusal_reason") or None)

    def _clean(text: str | None, name: str) -> str | None:
        if text is None:
            return None
        if _DIGIT.search(text):
            drift[f"numeric_claim_{name}"] = 1
            return None
        from .llm import find_pii
        if find_pii(text, protect=[business["name"]]):
            log.error("assess-v1 put personal data in %s for %s", name, business_id)
            drift[f"pii_in_narrative_{name}"] = 1
            return None
        return text.strip()

    problem = _clean(problem, "potential_problem")
    benefit = _clean(benefit, "expected_benefit")

    # 4. An unsourced claim is not a claim. A null renders an em dash; nothing manufactures a
    #    sentence to fill it.
    if problem is not None and not used:
        drift["unsourced_claims"] = 1
        problem = None
        refusal = refusal or "No finding id was returned to support the problem statement"

    conn.execute(
        "UPDATE opportunities SET potential_problem = ?, potential_solution = ?, "
        "expected_benefit = ?, refusal_reason = ?, model_id = ?, prompt_version = ?, "
        "input_tokens = ?, output_tokens = ?, quota_requests = quota_requests + 1, "
        "assessed_at = ? WHERE id = ?",
        (problem, solution, benefit, refusal, response.model_id, response.prompt_version,
         response.input_tokens, response.output_tokens, utc_now(), score.opportunity_id),
    )
    conn.execute("UPDATE opportunity_modules SET is_current = 0 WHERE business_id = ?",
                 (business_id,))
    for ordinal, entry in enumerate(ordered):
        because = entry.get("because_finding_id")
        conn.execute(
            "INSERT INTO opportunity_modules "
            "  (id, opportunity_id, business_id, module, ordinal, rationale, "
            "   because_finding_id, is_current) VALUES (?,?,?,?,?,?,?,1)",
            (new_id_for("opportunity_modules"), score.opportunity_id, business_id,
             entry["module"], ordinal, entry.get("rationale"),
             because if because in usable else None),
        )

    audit_mod.audit(
        conn, actor, "OPPORTUNITY_SCORED", "opportunities", score.opportunity_id,
        after={"potential_solution": solution, "modules": [e["module"] for e in ordered]},
        business_id=business_id, campaign_id=campaign_id,
        detail={"model_id": response.model_id, "prompt_version": response.prompt_version,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens, "drift": drift,
                "refusal_reason": refusal},
    )
    log.info("assessed %s: %s, %d modules%s", business["name"], solution, len(ordered),
             f", drift {drift}" if drift else "")
    return {"potential_problem": problem, "potential_solution": solution,
            "expected_benefit": benefit, "modules": ordered, "drift": drift,
            "refusal_reason": refusal}


__all__ = [
    "ASSESS_PROMPT_VERSION", "ASSESS_SCHEMA", "ASSESS_SYSTEM", "CONFIDENCE_MULTIPLIER",
    "DIGITAL_SIGNALS", "MODEL_SIGNAL_KEYS", "MODULE_MAP", "MODULE_MAP_BY_INDUSTRY",
    "MIN_DIGITAL_COVERAGE", "OPERATIONAL_SIGNALS", "OPPORTUNITY_WEIGHTS", "OpportunityScore",
    "REGULATORY_PRIOR", "SIGNAL_TYPES", "ScoreComponent", "SignalReading", "SignalSpec",
    "WEIGHTS_VERSION", "assess_opportunity", "coerce_signal", "contactability",
    "digital_maturity", "first_clause", "industry_fit", "module_profile",
    "operational_complexity", "opportunity_score", "research_confidence", "round_half_up",
    "score_business", "signals_from_findings", "top_reason", "weighted_coverage",
]
