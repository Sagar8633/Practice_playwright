"""The research report: the document Sagar actually reads before he contacts anybody.

Everything upstream of this module - discovery, research, scoring, verification - produces rows
in SQLite that nobody can look at. This module turns those rows into one self-contained HTML
file he can open on a plane, mail to himself, or keep in a folder for a year and still have it
render. Without it the pipeline is a database nobody reviews, and the human verification gate
that the whole system exists to enforce becomes a screen he never visits.

Two properties matter more than anything else here.

The first is that **every number comes from a SQL aggregate over real rows**. There is no
placeholder, no default, no average deal size applied to an unpriced business. Where a metric
has nothing behind it the report renders an em dash, never a zero, because "we checked and the
answer is none" and "we never checked" lead Sagar to opposite actions and a report that draws
them identically is worse than no report at all.

The second is that **the exported file carries no capability**. It has no form, no token, no
credential, no contact address and no code path that can transmit anything. Every
state-changing control in it is an ordinary link to a GET route on the live app, which will
demand a session and re-check every gate before it changes a thing. If this file gets forwarded
to a stranger, the worst they can do with it is read it.

Design of record: docs/03-html-report.md. Where this implementation deliberately does less than
the design, the line is marked SIMPLIFIED and names the section that carries the full version.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import logging
import os
import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from . import db
from .audit import audit
from .ids import new_id_for
from .paths import REPORTS_DIR, ensure

log = logging.getLogger("radar.report")

# Bumped whenever the rendered structure changes in a way an archived report should be
# distinguishable by. Both land in report_exports so an old file can be explained.
GENERATOR_VERSION = "report-1.0.0"
TEMPLATE_VERSION = "report.html.j2-1.0.0"

TEMPLATE_DIR: Path = Path(__file__).resolve().parent / "templates"

# India Standard Time. Sagar's "26 Aug" is IST, not UTC, and a report dated a day early
# because the campaign started at 02:00 UTC is a report he cannot find again.
IST = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# Display vocabulary. The report never shows a raw enum.
# ---------------------------------------------------------------------------
INDUSTRY_ORDER: tuple[str, ...] = (
    "HEALTHCARE", "EDUCATION", "AUTOMOBILE", "MANUFACTURING", "RETAIL",
    "HOSPITALITY", "DISTRIBUTION", "REAL_ESTATE", "PROFESSIONAL_SERVICES", "OTHER",
)

INDUSTRY_LABEL: dict[str, str] = {
    "HEALTHCARE": "Healthcare", "EDUCATION": "Education", "AUTOMOBILE": "Automobile",
    "MANUFACTURING": "Manufacturing", "RETAIL": "Retail", "HOSPITALITY": "Hospitality",
    "DISTRIBUTION": "Distribution", "REAL_ESTATE": "Real estate",
    "PROFESSIONAL_SERVICES": "Professional services", "OTHER": "Other",
}

# Plural, for a group heading over many rows.
CATEGORY_LABEL: dict[str, str] = {
    "HOSPITAL": "Hospitals", "DIAGNOSTIC_CENTER": "Diagnostic centres", "SCHOOL": "Schools",
    "COLLEGE": "Colleges", "MANUFACTURER": "Manufacturers", "DISTRIBUTOR": "Distributors",
    "VEHICLE_DEALER": "Vehicle dealers", "GARAGE": "Garages", "HOTEL": "Hotels",
    "RESTAURANT": "Restaurants", "BAKERY": "Bakeries", "RETAIL_STORE": "Retail stores",
    "REAL_ESTATE_AGENCY": "Real estate agencies", "OTHER": "Other",
}

# Singular, for one row's own cell.
CATEGORY_ONE: dict[str, str] = {
    "HOSPITAL": "Hospital", "DIAGNOSTIC_CENTER": "Diagnostic centre", "SCHOOL": "School",
    "COLLEGE": "College", "MANUFACTURER": "Manufacturer", "DISTRIBUTOR": "Distributor",
    "VEHICLE_DEALER": "Vehicle dealer", "GARAGE": "Garage", "HOTEL": "Hotel",
    "RESTAURANT": "Restaurant", "BAKERY": "Bakery", "RETAIL_STORE": "Retail store",
    "REAL_ESTATE_AGENCY": "Real estate agency", "OTHER": "Other",
}

MODULE_LABEL: dict[str, str] = {
    "DASHBOARD": "Dashboard", "WORKFLOW": "Workflow", "FINANCE": "Finance tracking",
    "INVENTORY": "Inventory", "REPORTS": "Reports", "ROLE_MANAGEMENT": "Role management",
    "AUDIT_LOGS": "Audit logs", "PATIENTS": "Patients", "APPOINTMENTS": "Appointments",
    "DEPARTMENTS": "Departments", "BILLING": "Billing", "STUDENTS": "Students",
    "FEES": "Fees", "ATTENDANCE": "Attendance", "STAFF": "Staff", "TRANSPORT": "Transport",
    "ADMISSIONS": "Admissions", "EXAMINATIONS": "Examinations", "PRODUCTION": "Production",
    "PURCHASING": "Purchasing", "SALES": "Sales", "QUALITY": "Quality", "ORDERS": "Orders",
    "CUSTOMERS": "Customers", "RECEIVABLES": "Receivables", "DELIVERY": "Delivery",
    "PAYMENTS": "Payments", "VARIANTS": "Variants", "PROFITABILITY": "Profitability",
    "EXPENSES": "Expenses", "PROFIT": "Profit",
}

# One sentence per gate, so the report, the live grid and the outreach workspace all say the
# same thing about the same row. The tooltip names the missing precondition; "not eligible"
# would make Sagar go and find out for himself.
BLOCK_REASON: dict[str, str] = {
    "A_SUPPRESSED": "Do not contact: an opt-out or suppression is recorded.",
    "D_HUMAN_OWNED": "This is a live lead - the machine stops here and you take it.",
    "D_VERIFICATION_REVOKED": "You rejected or skipped this business.",
    "D_NOT_VERIFIED": "This business still needs your verification.",
    "D_VERIFICATION_STALE": "The verification has expired - re-verify before selecting.",
    "E_CONTACT_MISSING": "Verified, but no confirmed contact yet.",
    "F_IN_FLIGHT": "A message for this business is already awaiting approval.",
    "G_STOP_AFTER_REJECTION": "This business replied that it is not interested.",
    "G_MAX_ATTEMPTS": "The maximum number of outreach attempts has been reached.",
    "G_MAX_FOLLOWUPS": "The maximum number of follow-ups has been reached.",
    "G_MIN_DAYS": "Contacted too recently - the minimum gap has not elapsed.",
}

# Ordinal scales for the badge columns. They are computed here and written into data-*
# attributes as plain numbers, so the client-side comparator is one numeric compare and there
# is no shared lookup table in which MEDIUM-the-size and MEDIUM-the-confidence can collide.
SIZE_ORD: dict[str, int] = {"UNKNOWN": 0, "MICRO": 1, "SMALL": 2, "MEDIUM": 3, "LARGE": 4}
CONF_ORD: dict[str, int] = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
VERIF_ORD: dict[str, int] = {
    "SKIPPED": 0, "REJECTED": 0, "AI_RESEARCHED": 1, "NEEDS_VERIFICATION": 2,
    "VERIFIED": 3, "CONTACT_READY": 4,
}
OUTREACH_ORD: dict[str, int] = {
    "BLOCKED": 0, "NOT_CONTACTED": 0, "QUEUED": 1, "BOUNCED": 1, "FAILED": 1,
    "SENT": 2, "DELIVERED": 3, "RESPONDED": 4, "INTERESTED": 5,
}

CONTACT_CHIP: dict[str, tuple[str, str]] = {
    "EMAIL": ("E", "Business email available"),
    "PHONE": ("P", "Business phone available"),
    "WHATSAPP": ("W", "WhatsApp number available"),
}


# ===========================================================================
# The twelve queries. One report load is twelve statements regardless of how
# many businesses it contains; per-row data is fetched in bulk and grouped in
# Python. docs/03-html-report.md section 3.3.3.
# ===========================================================================

Q_CAMPAIGN = """
SELECT
    c.id                                   AS campaign_id,
    c.name,
    c.created_at,
    c.status                               AS campaign_status,
    c.research_depth,
    c.size_filter,
    c.industries,
    c.min_opportunity_score,
    c.research_model_id,
    c.research_prompt_version,
    u.display_name                         AS created_by_name,
    (SELECT group_concat(cc.city, ', ')
       FROM (SELECT city FROM campaign_cities
              WHERE campaign_id = c.id ORDER BY ordinal) cc)   AS cities_display,

    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id)                              AS h_found,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.research_complete = 1)  AS h_researched,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.is_qualified = 1)       AS h_qualified,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id
        AND r.status IN ('SKIPPED','REJECTED'))                AS h_skipped,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.status = 'SKIPPED')     AS h_skipped_pipeline,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.status = 'REJECTED')    AS h_rejected,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id
        AND r.status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')) AS h_needs_verification,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.status = 'CONTACT_READY') AS h_ready,

    -- drift detection only; never rendered as a fact
    c.n_discovered, c.n_researched, c.n_qualified,
    c.n_skipped, c.n_verified, c.n_contacted
FROM campaigns c
LEFT JOIN users u ON u.id = c.created_by
WHERE c.id = :campaign_id
"""

Q_KPIS = """
SELECT
  COUNT(*)                                                                AS k_total,
  SUM(CASE WHEN is_qualified = 1                    THEN 1 ELSE 0 END)    AS k_qualified,
  SUM(CASE WHEN opportunity_score >= 80             THEN 1 ELSE 0 END)    AS k_high,
  SUM(CASE WHEN opportunity_score BETWEEN 60 AND 79 THEN 1 ELSE 0 END)    AS k_medium,
  SUM(CASE WHEN opportunity_score < 60              THEN 1 ELSE 0 END)    AS k_low,
  SUM(CASE WHEN opportunity_score IS NULL           THEN 1 ELSE 0 END)    AS k_unscored,
  SUM(CASE WHEN website_status = 'PRESENT'          THEN 1 ELSE 0 END)    AS k_web_yes,
  SUM(CASE WHEN website_status = 'ABSENT'           THEN 1 ELSE 0 END)    AS k_web_no,
  SUM(CASE WHEN website_status = 'UNKNOWN'          THEN 1 ELSE 0 END)    AS k_web_unknown,
  SUM(CASE WHEN potential_solution IS NOT NULL
             AND n_modules > 0                      THEN 1 ELSE 0 END)    AS k_software_opp,
  SUM(CASE WHEN status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')
                                                    THEN 1 ELSE 0 END)    AS k_need_verif,
  SUM(CASE WHEN is_verified = 1                     THEN 1 ELSE 0 END)    AS k_verified,
  SUM(CASE WHEN n_sent > 0                          THEN 1 ELSE 0 END)    AS k_contacted,
  SUM(CASE WHEN is_interested = 1                   THEN 1 ELSE 0 END)    AS k_interested,
  SUM(CASE WHEN opportunity_score IS NOT NULL       THEN 1 ELSE 0 END)    AS k_scored,
  SUM(CASE WHEN research_complete = 1               THEN 1 ELSE 0 END)    AS k_researched
FROM v_report_business
WHERE campaign_id = :campaign_id
"""

# LEFT JOIN from campaign_cities so a targeted city that returned nothing still gets a card. A
# missing card reads as "we did not search Shirpur"; a card of zeros reads as "we searched
# Shirpur and found nothing", which is the true statement.
# The join is on city_slug rather than the display form: the slug is the identity column and a
# display-form join breaks the first time a city is stored as "Nashik " with a trailing space.
Q_CITY_SUMMARY = """
SELECT
    cc.city,
    cc.city_slug,
    cc.ordinal,
    COUNT(r.business_id)                                                    AS c_found,
    SUM(CASE WHEN r.is_qualified = 1          THEN 1 ELSE 0 END)            AS c_qualified,
    SUM(CASE WHEN r.opportunity_score >= 80   THEN 1 ELSE 0 END)            AS c_high,
    SUM(CASE WHEN r.is_verified = 1           THEN 1 ELSE 0 END)            AS c_verified,
    SUM(CASE WHEN r.is_ready_for_outreach = 1 THEN 1 ELSE 0 END)            AS c_ready,
    SUM(CASE WHEN r.opportunity_score IS NOT NULL THEN 1 ELSE 0 END)        AS c_scored,
    SUM(CASE WHEN r.research_complete = 1     THEN 1 ELSE 0 END)            AS c_researched
FROM campaign_cities cc
LEFT JOIN v_report_business r
       ON r.campaign_id = cc.campaign_id
      AND r.city_slug = cc.city_slug
WHERE cc.campaign_id = :campaign_id
GROUP BY cc.city, cc.city_slug, cc.ordinal
ORDER BY cc.ordinal
"""

# The report renders selectability; it never computes it. blocking_gate is the grid
# approximation from 05-outreach-workflow.md section 5.4.2 - optimistic in a way that costs a
# click, never in a way that costs a send.
Q_ROWS = """
SELECT
    r.*,
    sel.state                                   AS selection_state,
    d.id                                        AS draft_id,
    d.policy_result                             AS draft_policy_result,
    CASE
      WHEN r.is_suppressed = 1                                       THEN 'A_SUPPRESSED'
      WHEN r.status IN ('INTERESTED','HUMAN_HANDOFF')                THEN 'D_HUMAN_OWNED'
      WHEN r.status IN ('REJECTED','SKIPPED')                        THEN 'D_VERIFICATION_REVOKED'
      WHEN r.status NOT IN ('CONTACT_READY','CONTACTED','RESPONDED') THEN 'D_NOT_VERIFIED'
      WHEN r.verified_at IS NULL                                     THEN 'D_NOT_VERIFIED'
      WHEN r.n_contacts = 0                                          THEN 'E_CONTACT_MISSING'
      ELSE NULL
    END                                         AS blocking_gate
FROM v_report_business r
LEFT JOIN selections sel
       ON sel.campaign_id = r.campaign_id
      AND sel.business_id = r.business_id
      AND sel.state <> 'REMOVED'
LEFT JOIN outreach_drafts d
       ON d.business_id = r.business_id
      AND d.campaign_id = r.campaign_id
      AND d.superseded_by IS NULL
WHERE r.campaign_id = :campaign_id
ORDER BY r.city,
         r.industry,
         r.category,
         CASE WHEN r.opportunity_score IS NULL THEN 1 ELSE 0 END,
         r.opportunity_score DESC,
         r.name,
         r.business_id
"""

# The join fans out one row per (finding, source); _load_findings collapses it into
# Finding(sources=[...]). This is why the query set stays at twelve regardless of row count.
Q_FINDINGS = """
SELECT
    f.business_id,
    f.id            AS finding_id,
    f.kind,
    f.dimension,
    f.label,
    f.statement,
    f.confidence,
    f.confidence_pct,
    f.weight,
    f.unknown_reason,
    f.inference_note,
    s.id            AS source_id,
    s.name          AS source_name,
    s.url           AS source_url,
    s.source_type,
    COALESCE(fs.checked_at, s.checked_at) AS checked_at,
    fs.excerpt      AS information_obtained
FROM research_findings f
JOIN v_report_business r ON r.business_id = f.business_id
LEFT JOIN finding_sources fs ON fs.finding_id = f.id
LEFT JOIN sources         s  ON s.id = fs.source_id
WHERE r.campaign_id = :campaign_id
  AND f.research_run_id = (SELECT rr.id FROM research_runs rr
                            WHERE rr.business_id = f.business_id
                              AND rr.status = 'COMPLETE'
                            ORDER BY rr.finished_at DESC
                            LIMIT 1)
ORDER BY f.business_id,
         CASE f.kind WHEN 'OBSERVED' THEN 0 WHEN 'INFERRED' THEN 1 ELSE 2 END,
         f.confidence_pct DESC,
         f.weight DESC,
         f.id
"""

Q_OPPORTUNITY = """
SELECT o.business_id, o.score, o.band, o.confidence, o.confidence_pct,
       o.digital_maturity, o.operational_complexity,
       o.potential_problem, o.potential_solution, o.expected_benefit,
       o.est_value_inr, o.est_value_basis, o.score_breakdown,
       o.model_id, o.prompt_version, o.computed_at
FROM opportunities o
JOIN v_report_business r ON r.business_id = o.business_id
WHERE r.campaign_id = :campaign_id AND o.is_current = 1
ORDER BY o.business_id
"""

Q_MODULES = """
SELECT om.business_id, om.module, om.ordinal, om.rationale
FROM opportunity_modules om
JOIN v_report_business r ON r.business_id = om.business_id
WHERE r.campaign_id = :campaign_id AND om.is_current = 1
ORDER BY om.business_id, om.ordinal, om.module
"""

# Kinds and counts only. No contact VALUE ever reaches the exported file: a report that gets
# forwarded must not be a mailing list. 03-html-report.md section 3.4.5.2.
Q_CONTACTS = """
SELECT c.business_id,
       c.kind,
       COUNT(*)                                                 AS n_total,
       SUM(CASE WHEN c.human_verified = 1 THEN 1 ELSE 0 END)    AS n_confirmed
FROM business_contacts c
JOIN v_report_business r ON r.business_id = c.business_id
WHERE r.campaign_id = :campaign_id
  AND c.is_active = 1
GROUP BY c.business_id, c.kind
ORDER BY c.business_id, c.kind
"""

# The message BODY is deliberately not selected. A file that gets emailed around should not
# carry the full text of every message Sagar has ever sent to every prospect in four cities.
Q_HISTORY = """
SELECT
    m.business_id,
    m.id                AS message_id,
    m.channel,
    m.status            AS delivery_status,
    m.sequence_no,
    m.subject_final,
    m.sent_at,
    m.delivered_at,
    u.display_name      AS sender,
    COALESCE(resp.human_classification, resp.classification) AS response_classification,
    resp.confidence     AS response_confidence,
    resp.received_at    AS response_at,
    h.state             AS handoff_state,
    h.outcome           AS handoff_outcome
FROM outreach_messages m
JOIN v_report_business r        ON r.business_id = m.business_id
LEFT JOIN outreach_approvals ap ON ap.id = m.approval_id
LEFT JOIN users u               ON u.id = ap.approved_by
LEFT JOIN responses resp        ON resp.message_id = m.id
LEFT JOIN handoffs h            ON h.business_id = m.business_id
WHERE r.campaign_id = :campaign_id
  AND m.status IN ('SENT','DELIVERED','BOUNCED','FAILED')
ORDER BY m.business_id, m.sent_at, m.id
"""

Q_CMP_CITY = """
SELECT
    cc.city,
    cc.city_slug,
    cc.ordinal,
    COUNT(r.business_id)                                              AS n_businesses,
    SUM(CASE WHEN r.is_qualified = 1        THEN 1 ELSE 0 END)        AS n_qualified,
    SUM(CASE WHEN r.opportunity_score >= 80 THEN 1 ELSE 0 END)        AS n_high,
    SUM(CASE WHEN r.is_verified = 1         THEN 1 ELSE 0 END)        AS n_verified,
    SUM(CASE WHEN r.n_sent > 0              THEN 1 ELSE 0 END)        AS n_contacted,
    SUM(CASE WHEN r.n_responses > 0         THEN 1 ELSE 0 END)        AS n_responded,
    SUM(CASE WHEN r.is_interested = 1       THEN 1 ELSE 0 END)        AS n_interested,
    -- 0/0 is undefined, so the SQL returns NULL and the cell renders an em dash. A 0% here
    -- would tell Sagar that Jalgaon does not respond, when Jalgaon has never been contacted.
    CASE WHEN SUM(CASE WHEN r.n_sent > 0 THEN 1 ELSE 0 END) > 0
         THEN ROUND(100.0 * SUM(CASE WHEN r.is_interested = 1 THEN 1 ELSE 0 END)
                          / SUM(CASE WHEN r.n_sent > 0 THEN 1 ELSE 0 END), 1)
    END                                                               AS conversion_pct,
    SUM(CASE WHEN r.is_qualified = 1 THEN r.est_value_inr END)        AS potential_inr,
    SUM(CASE WHEN r.is_qualified = 1 AND r.est_value_inr IS NOT NULL
             THEN 1 ELSE 0 END)                                       AS n_priced,
    SUM(CASE WHEN r.opportunity_score IS NOT NULL THEN 1 ELSE 0 END)  AS n_scored,
    SUM(CASE WHEN r.research_complete = 1 THEN 1 ELSE 0 END)          AS n_researched
FROM campaign_cities cc
LEFT JOIN v_report_business r
       ON r.campaign_id = cc.campaign_id AND r.city_slug = cc.city_slug
WHERE cc.campaign_id = :campaign_id
GROUP BY cc.city, cc.city_slug, cc.ordinal
ORDER BY cc.ordinal
"""

Q_CMP_INDUSTRY = """
SELECT
    r.industry,
    COUNT(*)                                                          AS n_businesses,
    ROUND(AVG(r.opportunity_score), 1)                                AS avg_score,
    SUM(CASE WHEN r.opportunity_score IS NOT NULL THEN 1 ELSE 0 END)  AS n_scored,
    SUM(CASE WHEN r.is_verified = 1   THEN 1 ELSE 0 END)              AS n_verified,
    SUM(CASE WHEN r.n_sent > 0        THEN 1 ELSE 0 END)              AS n_contacted,
    SUM(CASE WHEN r.n_responses > 0   THEN 1 ELSE 0 END)              AS n_responded,
    SUM(CASE WHEN r.is_interested = 1 THEN 1 ELSE 0 END)              AS n_interested,
    COUNT(DISTINCT CASE WHEN h.demo_held_at IS NOT NULL
                        THEN h.business_id END)                       AS n_demos,
    COUNT(DISTINCT CASE WHEN h.outcome = 'WON'
                        THEN h.business_id END)                       AS n_won,
    SUM(CASE WHEN h.outcome = 'WON' THEN h.won_value_inr END)         AS revenue_inr,
    SUM(CASE WHEN h.outcome = 'WON' AND h.won_value_inr IS NOT NULL
             THEN 1 ELSE 0 END)                                       AS n_revenue_rows
FROM v_report_business r
LEFT JOIN handoffs h ON h.business_id = r.business_id
WHERE r.campaign_id = :campaign_id
GROUP BY r.industry
ORDER BY CASE r.industry
           WHEN 'HEALTHCARE' THEN 0 WHEN 'EDUCATION' THEN 1 WHEN 'AUTOMOBILE' THEN 2
           WHEN 'MANUFACTURING' THEN 3 WHEN 'RETAIL' THEN 4 WHEN 'HOSPITALITY' THEN 5
           WHEN 'DISTRIBUTION' THEN 6 WHEN 'REAL_ESTATE' THEN 7
           WHEN 'PROFESSIONAL_SERVICES' THEN 8 ELSE 9 END
"""

Q_TOP20 = """
SELECT
    r.business_id,
    r.name,
    r.city,
    r.city_slug,
    r.industry,
    r.opportunity_score,
    r.opportunity_band,
    r.potential_solution           AS potential_system,
    r.research_confidence,
    r.research_confidence_pct,
    r.status,
    r.is_verified,
    r.verified_at,
    o.score_breakdown,
    (SELECT f.statement
       FROM research_findings f
      WHERE f.business_id = r.business_id
        AND f.kind = 'OBSERVED'
      ORDER BY f.weight DESC, f.confidence_pct DESC, f.id
      LIMIT 1)                     AS top_observed_statement
FROM v_report_business r
LEFT JOIN opportunities o ON o.business_id = r.business_id AND o.is_current = 1
WHERE r.campaign_id = :campaign_id
  AND r.opportunity_score IS NOT NULL
ORDER BY r.opportunity_score DESC, r.name, r.business_id
LIMIT :limit
"""

ALL_QUERIES: tuple[tuple[str, str], ...] = (
    ("Q_CAMPAIGN", Q_CAMPAIGN), ("Q_KPIS", Q_KPIS), ("Q_CITY_SUMMARY", Q_CITY_SUMMARY),
    ("Q_ROWS", Q_ROWS), ("Q_FINDINGS", Q_FINDINGS), ("Q_OPPORTUNITY", Q_OPPORTUNITY),
    ("Q_MODULES", Q_MODULES), ("Q_CONTACTS", Q_CONTACTS), ("Q_HISTORY", Q_HISTORY),
    ("Q_CMP_CITY", Q_CMP_CITY), ("Q_CMP_INDUSTRY", Q_CMP_INDUSTRY), ("Q_TOP20", Q_TOP20),
)


def query_fingerprint() -> str:
    """A hash over the SQL that produced a report.

    Stored on the report_exports row so that "the numbers changed" can be told apart from "the
    query changed". Without it, a fixed aggregate looks exactly like a data drift.
    """
    digest = hashlib.sha256()
    for name, sql in ALL_QUERIES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(" ".join(sql.split()).encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


# ===========================================================================
# Records. from_row() never coalesces a nullable metric to zero: once a None
# has become a 0 in Python, no template downstream can tell "we looked and
# found none" from "we never measured this".
# ===========================================================================

def _get(row: sqlite3.Row | dict[str, Any], key: str, default: Any = None) -> Any:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return default if value is None else value


def _opt(row: sqlite3.Row | dict[str, Any], key: str) -> Any:
    """The nullable read. Returns None rather than a default, on purpose."""
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


def _flag(row: sqlite3.Row | dict[str, Any], key: str) -> bool:
    return bool(_get(row, key, 0))


@dataclass(slots=True)
class HeaderFacts:
    """Section 6's nine facts. Live aggregates, never the campaigns.n_* counter columns."""

    found: int
    researched: int
    qualified: int
    skipped: int
    skipped_pipeline: int
    rejected: int
    needs_verification: int
    ready: int

    @property
    def skipped_title(self) -> str:
        return (f"{self.skipped_pipeline} skipped by the pipeline, "
                f"{self.rejected} rejected by you")


@dataclass(slots=True)
class Kpis:
    """Section 7's twelve cards, from one query so the row is internally consistent."""

    total: int
    qualified: int
    high: int
    medium: int
    low: int
    unscored: int
    web_yes: int
    web_no: int
    web_unknown: int
    software_opp: int
    need_verif: int
    verified: int
    contacted: int
    interested: int
    scored: int
    researched: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Kpis":
        return cls(
            total=_get(row, "k_total", 0), qualified=_get(row, "k_qualified", 0),
            high=_get(row, "k_high", 0), medium=_get(row, "k_medium", 0),
            low=_get(row, "k_low", 0), unscored=_get(row, "k_unscored", 0),
            web_yes=_get(row, "k_web_yes", 0), web_no=_get(row, "k_web_no", 0),
            web_unknown=_get(row, "k_web_unknown", 0),
            software_opp=_get(row, "k_software_opp", 0),
            need_verif=_get(row, "k_need_verif", 0), verified=_get(row, "k_verified", 0),
            contacted=_get(row, "k_contacted", 0), interested=_get(row, "k_interested", 0),
            scored=_get(row, "k_scored", 0), researched=_get(row, "k_researched", 0),
        )

    # The em-dash decisions from section 3.4.2, made once, in Python, where they can be read.
    @property
    def qualified_or_none(self) -> int | None:
        return self.qualified if self.researched else None

    @property
    def high_or_none(self) -> int | None:
        return self.high if self.scored else None

    @property
    def medium_or_none(self) -> int | None:
        return self.medium if self.scored else None

    @property
    def low_or_none(self) -> int | None:
        return self.low if self.scored else None

    @property
    def software_opp_or_none(self) -> int | None:
        return self.software_opp if self.researched else None

    @property
    def total_or_none(self) -> int | None:
        return self.total or None


@dataclass(slots=True)
class CitySummary:
    city: str
    city_slug: str
    ordinal: int
    found: int
    qualified: int | None
    high: int | None
    verified: int
    ready: int
    scored: int
    researched: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CitySummary":
        researched = _get(row, "c_researched", 0)
        scored = _get(row, "c_scored", 0)
        return cls(
            city=row["city"],
            city_slug=row["city_slug"],
            ordinal=_get(row, "ordinal", 0),
            found=_get(row, "c_found", 0),
            qualified=_get(row, "c_qualified", 0) if researched else None,
            high=_get(row, "c_high", 0) if scored else None,
            verified=_get(row, "c_verified", 0),
            ready=_get(row, "c_ready", 0),
            scored=scored,
            researched=researched,
        )


@dataclass(slots=True)
class SourceRef:
    source_id: str
    name: str
    url: str | None
    source_type: str
    checked_at: str | None
    excerpt: str | None
    number: int = 0          # per-business citation number, assigned in first-citation order


@dataclass(slots=True)
class FindingView:
    business_id: str
    finding_id: str
    kind: str
    dimension: str
    label: str | None
    statement: str
    confidence: str | None
    confidence_pct: int | None
    weight: float
    unknown_reason: str | None
    inference_note: str | None
    sources: list[SourceRef] = field(default_factory=list)

    @property
    def has_source(self) -> bool:
        return bool(self.sources)


@dataclass(slots=True)
class ModuleView:
    module: str
    ordinal: int
    rationale: str | None

    @property
    def label(self) -> str:
        return MODULE_LABEL.get(self.module, self.module.replace("_", " ").title())


@dataclass(slots=True)
class OpportunityView:
    business_id: str
    score: int | None
    band: str | None
    confidence: str | None
    confidence_pct: int | None
    digital_maturity: int | None
    operational_complexity: int | None
    potential_problem: str | None
    potential_solution: str | None
    expected_benefit: str | None
    est_value_inr: int | None
    est_value_basis: str | None
    breakdown: list[dict[str, Any]]
    model_id: str | None
    prompt_version: str | None
    computed_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "OpportunityView":
        return cls(
            business_id=row["business_id"],
            score=_opt(row, "score"), band=_opt(row, "band"),
            confidence=_opt(row, "confidence"), confidence_pct=_opt(row, "confidence_pct"),
            digital_maturity=_opt(row, "digital_maturity"),
            operational_complexity=_opt(row, "operational_complexity"),
            potential_problem=_opt(row, "potential_problem"),
            potential_solution=_opt(row, "potential_solution"),
            expected_benefit=_opt(row, "expected_benefit"),
            est_value_inr=_opt(row, "est_value_inr"),
            est_value_basis=_opt(row, "est_value_basis"),
            breakdown=parse_breakdown(_opt(row, "score_breakdown")),
            model_id=_opt(row, "model_id"), prompt_version=_opt(row, "prompt_version"),
            computed_at=_opt(row, "computed_at"),
        )


@dataclass(slots=True)
class ContactSummary:
    """What channels exist, and how many are confirmed. Never a value."""

    kind: str
    n_total: int
    n_confirmed: int


@dataclass(slots=True)
class HistoryEvent:
    business_id: str
    message_id: str
    channel: str
    delivery_status: str
    sequence_no: int
    subject_final: str | None
    sent_at: str | None
    delivered_at: str | None
    sender: str | None
    response_classification: str | None
    response_confidence: str | None
    response_at: str | None
    handoff_state: str | None
    handoff_outcome: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "HistoryEvent":
        return cls(
            business_id=row["business_id"], message_id=row["message_id"],
            channel=row["channel"], delivery_status=row["delivery_status"],
            sequence_no=_get(row, "sequence_no", 1),
            subject_final=_opt(row, "subject_final"), sent_at=_opt(row, "sent_at"),
            delivered_at=_opt(row, "delivered_at"), sender=_opt(row, "sender"),
            response_classification=_opt(row, "response_classification"),
            response_confidence=_opt(row, "response_confidence"),
            response_at=_opt(row, "response_at"),
            handoff_state=_opt(row, "handoff_state"),
            handoff_outcome=_opt(row, "handoff_outcome"),
        )

    @property
    def next_action(self) -> tuple[str, str]:
        """(tone class, sentence). Derived at render time; nothing stores it."""
        stoppers = {"NOT_INTERESTED", "ALREADY_HAVE_SOFTWARE", "WRONG_CONTACT"}
        interest = {"INTERESTED", "VERY_INTERESTED", "DEMO_REQUESTED",
                    "MEETING_REQUESTED", "PRICE_REQUESTED"}
        cls_ = self.response_classification
        if self.handoff_state and self.handoff_state != "CLOSED":
            return ("ok", "With you - see /handoffs")
        if cls_ in ("OPT_OUT", "COMPLAINT"):
            return ("bad", "Do not contact")
        if cls_ in interest:
            return ("ok", "Human action required")
        if cls_ in stoppers:
            return ("mute", "Stop - no further outreach")
        if cls_ == "LATER":
            return ("warn", "Revisit after the frequency window")
        if self.delivery_status in ("BOUNCED", "FAILED"):
            return ("bad", "Delivery failed - check the contact")
        if self.delivery_status in ("SENT", "DELIVERED"):
            return ("warn", "Follow-up available")
        return ("mute", "No further outreach")


@dataclass(slots=True)
class BusinessRow:
    """One line of section 9's table, plus everything its research panel needs."""

    business_id: str
    name: str
    city: str
    city_slug: str
    industry: str
    category: str
    size_band: str
    status: str
    website: str | None
    website_domain: str | None
    website_status: str
    listing_url: str | None
    membership_state: str
    discovered_at: str | None
    discovered_on: str | None
    opportunity_score: int | None
    opportunity_band: str | None
    research_confidence: str | None
    research_confidence_pct: int | None
    digital_maturity: int | None
    operational_complexity: int | None
    potential_problem: str | None
    potential_solution: str | None
    expected_benefit: str | None
    est_value_inr: int | None
    n_modules: int
    research_complete: bool
    researched_at: str | None
    research_depth: str | None
    n_contacts: int
    n_contacts_any: int
    has_email: bool
    has_phone: bool
    has_whatsapp: bool
    verified_at: str | None
    is_verified: bool
    n_sent: int
    last_sent_at: str | None
    last_message_status: str | None
    last_channel: str | None
    n_responses: int
    last_response_at: str | None
    is_interested: bool
    is_suppressed: bool
    is_qualified: bool
    is_ready_for_outreach: bool
    selection_state: str | None
    draft_id: str | None
    draft_policy_result: str | None
    blocking_gate: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "BusinessRow":
        return cls(
            business_id=row["business_id"], name=row["name"], city=row["city"],
            city_slug=row["city_slug"], industry=row["industry"], category=row["category"],
            size_band=_get(row, "size_band", "UNKNOWN"), status=row["status"],
            website=_opt(row, "website"), website_domain=_opt(row, "website_domain"),
            website_status=_get(row, "website_status", "UNKNOWN"),
            listing_url=_opt(row, "listing_url"),
            membership_state=_get(row, "membership_state", "INCLUDED"),
            discovered_at=_opt(row, "discovered_at"), discovered_on=_opt(row, "discovered_on"),
            # These five may be None and are never coalesced. Section 3.5.
            opportunity_score=_opt(row, "opportunity_score"),
            opportunity_band=_opt(row, "opportunity_band"),
            research_confidence=_opt(row, "research_confidence"),
            research_confidence_pct=_opt(row, "research_confidence_pct"),
            digital_maturity=_opt(row, "digital_maturity"),
            operational_complexity=_opt(row, "operational_complexity"),
            potential_problem=_opt(row, "potential_problem"),
            potential_solution=_opt(row, "potential_solution"),
            expected_benefit=_opt(row, "expected_benefit"),
            est_value_inr=_opt(row, "est_value_inr"),
            n_modules=_get(row, "n_modules", 0),
            research_complete=_flag(row, "research_complete"),
            researched_at=_opt(row, "researched_at"),
            research_depth=_opt(row, "research_depth"),
            n_contacts=_get(row, "n_contacts", 0),
            n_contacts_any=_get(row, "n_contacts_any", 0),
            has_email=_flag(row, "has_email"), has_phone=_flag(row, "has_phone"),
            has_whatsapp=_flag(row, "has_whatsapp"),
            verified_at=_opt(row, "verified_at"), is_verified=_flag(row, "is_verified"),
            n_sent=_get(row, "n_sent", 0), last_sent_at=_opt(row, "last_sent_at"),
            last_message_status=_opt(row, "last_message_status"),
            last_channel=_opt(row, "last_channel"),
            n_responses=_get(row, "n_responses", 0),
            last_response_at=_opt(row, "last_response_at"),
            is_interested=_flag(row, "is_interested"),
            is_suppressed=_flag(row, "is_suppressed"),
            is_qualified=_flag(row, "is_qualified"),
            is_ready_for_outreach=_flag(row, "is_ready_for_outreach"),
            selection_state=_opt(row, "selection_state"), draft_id=_opt(row, "draft_id"),
            draft_policy_result=_opt(row, "draft_policy_result"),
            blocking_gate=_opt(row, "blocking_gate"),
        )

    # --- derived, rendered into data-* attributes ---------------------------
    @property
    def verif_state(self) -> str:
        """Independent of outreach state: a CONTACTED business is still VERIFIED for filter 8."""
        if self.status in ("REJECTED", "SKIPPED"):
            return self.status
        if self.status == "CONTACT_READY":
            return "CONTACT_READY"
        if self.is_verified:
            return "VERIFIED"
        return self.status

    @property
    def verification_badge(self) -> tuple[str, str]:
        state = self.verif_state
        return {
            "CONTACT_READY": ("ok", "READY"),
            "VERIFIED": ("ok", "VERIFIED"),
            "NEEDS_VERIFICATION": ("warn", "NOT VERIFIED"),
            "AI_RESEARCHED": ("warn", "AI RESEARCHED"),
            "REJECTED": ("bad", "REJECTED"),
            "SKIPPED": ("mute", "SKIPPED"),
        }.get(state, ("warn", state.replace("_", " ")))

    @property
    def outreach_badge(self) -> tuple[str, str]:
        """(css class, label). Ordered by severity, not recency.

        A business that opted out after a delivered message must read DO NOT CONTACT, not
        DELIVERED: the newest fact is not the one that governs the next action.
        """
        if self.is_suppressed:
            return ("bad", "DO NOT CONTACT")
        if self.is_interested:
            return ("ok", "INTERESTED")
        if self.n_responses > 0:
            return ("info", "RESPONDED")
        if self.last_message_status in ("BOUNCED", "FAILED", "POLICY_BLOCKED"):
            return ("bad", self.last_message_status.replace("_", " "))
        if self.last_message_status == "DELIVERED":
            return ("ok", "DELIVERED")
        if self.last_message_status == "SENT":
            return ("info", "SENT")
        if self.last_message_status == "QUEUED":
            return ("info", "QUEUED")
        if self.n_sent > 0:
            return ("info", "SENT")
        return ("mute", "NOT CONTACTED")

    @property
    def outreach_attr(self) -> str:
        """The filter-10 token. Coarser than the badge, one value per row."""
        if self.is_suppressed:
            return "BLOCKED"
        if self.is_interested:
            return "INTERESTED"
        if self.n_responses > 0:
            return "RESPONDED"
        if self.last_message_status in ("QUEUED", "SENT", "DELIVERED", "BOUNCED", "FAILED"):
            return self.last_message_status
        if self.n_sent > 0:
            return "SENT"
        return "NOT_CONTACTED"

    @property
    def contact_attr(self) -> str:
        """Space-separated channels, or UNVERIFIED, or NONE.

        UNVERIFIED exists because "we found an email but nobody has confirmed it is a business
        address" and "there is no contact" are different states with different next actions.
        """
        kinds = [k for k, present in (("EMAIL", self.has_email), ("PHONE", self.has_phone),
                                      ("WHATSAPP", self.has_whatsapp)) if present]
        if kinds:
            return " ".join(kinds)
        if self.n_contacts_any > 0:
            return "UNVERIFIED"
        return "NONE"

    @property
    def contact_rank(self) -> int:
        """Ordinal for sorting column 10 - more confirmed channels sorts higher."""
        attr = self.contact_attr
        if attr == "NONE":
            return 0
        if attr == "UNVERIFIED":
            return 1
        return 1 + len(attr.split(" "))

    @property
    def selectable(self) -> bool:
        """Only CONTACT_READY gets an enabled checkbox, and only with no blocking gate."""
        return self.blocking_gate is None and self.status == "CONTACT_READY"

    @property
    def block_reason(self) -> str:
        if self.selectable:
            return ""
        if self.blocking_gate:
            return BLOCK_REASON.get(self.blocking_gate, "Not eligible for outreach.")
        if self.status == "CONTACTED":
            return "Already contacted - open the business to check the follow-up window."
        if self.status == "RESPONDED":
            return "This business has replied - read the response before contacting again."
        return "Not eligible for outreach."

    @property
    def size_ord(self) -> int:
        return SIZE_ORD.get(self.size_band, 0)

    @property
    def conf_ord(self) -> int:
        return CONF_ORD.get(self.research_confidence or "", 0)

    @property
    def verif_ord(self) -> int:
        return VERIF_ORD.get(self.verif_state, 0)

    @property
    def outreach_ord(self) -> int:
        return OUTREACH_ORD.get(self.outreach_attr, 0)

    @property
    def short(self) -> str:
        """A short DOM-safe suffix for panel ids."""
        return self.business_id[-10:]

    @property
    def search_blob(self) -> str:
        """data-q. Built once, lowercased once, so search is one indexOf per row.

        The business id is in here on purpose: Sagar can paste an id out of a log line straight
        into the search box.
        """
        parts = [
            self.name, self.city,
            CATEGORY_ONE.get(self.category, self.category),
            INDUSTRY_LABEL.get(self.industry, self.industry),
            self.potential_solution or "",
            self.website_domain or "",
            self.business_id,
        ]
        return " ".join(p for p in parts if p).casefold()


@dataclass(slots=True)
class CityCompareRow:
    city: str
    city_slug: str
    n_businesses: int
    n_qualified: int | None
    n_high: int | None
    n_verified: int
    n_contacted: int
    n_responded: int | None
    n_interested: int | None
    conversion_pct: float | None
    potential_inr: int | None
    n_priced: int
    n_scored: int
    n_researched: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CityCompareRow":
        contacted = _get(row, "n_contacted", 0)
        researched = _get(row, "n_researched", 0)
        scored = _get(row, "n_scored", 0)
        priced = _get(row, "n_priced", 0)
        return cls(
            city=row["city"], city_slug=row["city_slug"],
            n_businesses=_get(row, "n_businesses", 0),
            n_qualified=_get(row, "n_qualified", 0) if researched else None,
            n_high=_get(row, "n_high", 0) if scored else None,
            n_verified=_get(row, "n_verified", 0),
            n_contacted=contacted,
            n_responded=_get(row, "n_responded", 0) if contacted else None,
            n_interested=_get(row, "n_interested", 0) if contacted else None,
            conversion_pct=_opt(row, "conversion_pct"),
            potential_inr=_opt(row, "potential_inr") if priced else None,
            n_priced=priced, n_scored=scored, n_researched=researched,
        )


@dataclass(slots=True)
class IndustryCompareRow:
    industry: str
    n_businesses: int
    avg_score: float | None
    n_scored: int
    n_verified: int
    n_contacted: int
    n_responded: int | None
    n_interested: int | None
    n_demos: int | None
    n_won: int | None
    revenue_inr: int | None
    n_revenue_rows: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "IndustryCompareRow":
        contacted = _get(row, "n_contacted", 0)
        rev_rows = _get(row, "n_revenue_rows", 0)
        return cls(
            industry=row["industry"], n_businesses=_get(row, "n_businesses", 0),
            avg_score=_opt(row, "avg_score"), n_scored=_get(row, "n_scored", 0),
            n_verified=_get(row, "n_verified", 0), n_contacted=contacted,
            n_responded=_get(row, "n_responded", 0) if contacted else None,
            n_interested=_get(row, "n_interested", 0) if contacted else None,
            n_demos=_get(row, "n_demos", 0) if contacted else None,
            n_won=_get(row, "n_won", 0) if contacted else None,
            revenue_inr=_opt(row, "revenue_inr") if rev_rows else None,
            n_revenue_rows=rev_rows,
        )

    @property
    def small_sample(self) -> bool:
        """Under ten contacted, a 100% conversion on one business is not a trend."""
        return 0 < self.n_contacted < 10


@dataclass(slots=True)
class TopOpportunity:
    rank: int
    business_id: str
    name: str
    city: str
    industry: str
    opportunity_score: int
    opportunity_band: str | None
    potential_system: str | None
    research_confidence: str | None
    research_confidence_pct: int | None
    verif_state: str
    verification_badge: tuple[str, str]
    reason: str | None
    short: str


@dataclass(slots=True)
class CategoryGroup:
    category: str
    rows: list[BusinessRow]


@dataclass(slots=True)
class ReportData:
    campaign_id: str
    campaign_name: str
    created_at: str | None
    campaign_status: str
    research_depth: str
    min_opportunity_score: int
    size_filter: str
    industries_filter: str
    cities_display: str
    created_by_name: str | None
    research_model_id: str | None
    research_prompt_version: str | None
    header: HeaderFacts
    kpis: Kpis
    city_cards: list[CitySummary]
    rows: list[BusinessRow]
    groups: list[CategoryGroup]
    city_tabs: list[tuple[str, str, int]]          # (slug, label, count)
    industry_tabs: list[tuple[str, str, int]]      # (enum, label, count)
    findings: dict[str, list[FindingView]]
    sources: dict[str, list[SourceRef]]
    opportunities: dict[str, OpportunityView]
    modules: dict[str, list[ModuleView]]
    contacts: dict[str, list[ContactSummary]]
    history: dict[str, list[HistoryEvent]]
    cmp_city: list[CityCompareRow]
    cmp_industry: list[IndustryCompareRow]
    top20: list[TopOpportunity]
    warnings: list[str]
    generated_at: str
    generated_at_ist: str
    generated_by: str | None
    mode: str = "EXPORT"

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class ReportBuild:
    export_id: str
    path: Path
    bytes_written: int
    content_sha256: str
    data_sha256: str
    data_rel_path: str
    row_count: int
    generated_at: str
    duration_ms: int


# ===========================================================================
# Small helpers
# ===========================================================================

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SAFE_SCHEMES = ("http://", "https://")


def slug_city(city: str) -> str:
    text = unicodedata.normalize("NFKD", city or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return _SLUG_RE.sub("_", text.casefold()).strip("_")


def report_filename(
    cities: Sequence[str],
    on_date: date,
    *,
    scope: str = "CAMPAIGN",
    ext: str = "html",
    existing: Callable[[str], bool] | None = None,
) -> str:
    """Build the report's filename.

    The city list is in the file name on purpose. Sagar's reports live in a folder for months
    and "report_3.html" tells him nothing; "business_research_dhule_shirpur_2026-08-26.html"
    tells him whether he needs to open it.
    """
    if scope == "DAILY":
        stem = f"business_research_daily_{on_date.isoformat()}"
    else:
        slugs: list[str] = []
        seen: set[str] = set()
        for city in cities:
            s = slug_city(city)
            if s and s not in seen:
                seen.add(s)
                slugs.append(s)
        if len(slugs) > 4:
            slugs = slugs[:3] + [f"plus{len(slugs) - 3}more"]
        joined = "_".join(slugs) or "unspecified"
        stem = f"business_research_{joined}_{on_date.isoformat()}"
    if len(stem) > 120:
        stem = stem[:120].rsplit("_", 1)[0]
    name, n = f"{stem}.{ext}", 1
    while existing and existing(name):
        n += 1
        name = f"{stem}_v{n}.{ext}"
    return name


def inr(value: int | None) -> str:
    """Format rupees the way an Indian reader expects, or an em dash for no data."""
    if value is None:
        return "—"
    s = str(int(value))
    if len(s) <= 3:
        return f"₹ {s}"
    head, tail = s[:-3], s[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return f"₹ {','.join(parts)},{tail}"


def safe_url(value: str | None) -> str | None:
    """Absolute http(s) only.

    The export is opened from file://, where a relative URL resolves against the local disk and
    404s. Anything else - javascript:, data:, a bare fragment - is not a link this document is
    willing to render.
    """
    if not value:
        return None
    candidate = value.strip()
    if not candidate.lower().startswith(_SAFE_SCHEMES):
        return None
    if any(ch in candidate for ch in ("\n", "\r", "\t", " ", '"', "<", ">")):
        return None
    return candidate


def score_class(score: int | None) -> str:
    if score is None:
        return "mute"
    if score >= 80:
        return "ok"
    if score >= 60:
        return "warn"
    return "mute"


def score_band(score: int | None) -> str | None:
    if score is None:
        return None
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"


def confidence_class(confidence: str | None) -> str:
    return {"HIGH": "ok", "MEDIUM": "warn", "LOW": "mute"}.get(confidence or "", "mute")


def parse_breakdown(raw: str | None) -> list[dict[str, Any]]:
    """opportunities.score_breakdown, defensively.

    The score is never recomputed here. A report that disagrees with the stored score is a
    report Sagar cannot audit, so a breakdown we cannot parse renders as nothing at all rather
    than as a reconstruction.
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        log.warning("unparseable score_breakdown, rendering the opportunity without it")
        return []
    out: list[dict[str, Any]] = []
    if isinstance(parsed, dict):
        parsed = [{"component": k, "points": v} for k, v in parsed.items()]
    if not isinstance(parsed, list):
        return []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        out.append({
            "component": str(item.get("component") or item.get("name") or "component"),
            "points": item.get("points"),
            "of": item.get("of"),
            "because_finding_id": item.get("because_finding_id") or item.get("finding_id"),
        })
    return out


def top_reason(
    breakdown: list[dict[str, Any]],
    findings: list[FindingView],
    fallback: str | None,
) -> str | None:
    """One line explaining why this business is near the top.

    Prefers the score component that carries a finding id, because that is the only reason in
    the system that is traceable back to a source. Never composes a reason out of the score
    itself - "scored 86" explains nothing.
    """
    by_id = {f.finding_id: f for f in findings}
    cited = [c for c in breakdown if c.get("because_finding_id") in by_id]

    def points(component: dict[str, Any]) -> float:
        value = component.get("points")
        return float(value) if isinstance(value, (int, float)) else -1.0

    if cited:
        best = max(cited, key=points)
        finding = by_id[str(best["because_finding_id"])]
        head = best["component"]
        if best.get("points") is not None and best.get("of") is not None:
            head = f"{head} {best['points']}/{best['of']}"
        return f"{head} - {finding.statement}"
    return fallback or None


def fmt_date(value: str | None) -> str:
    """ISO-8601 UTC to '23 Aug 2026'. Anything unparseable renders verbatim."""
    if not value:
        return "—"
    try:
        parsed = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return value
    return parsed.strftime("%d %b %Y").lstrip("0")


def fmt_ist(value: str | None) -> str:
    """ISO-8601 UTC to '26 Aug 2026, 07:12 IST'. Sagar reads dates in IST."""
    if not value:
        return "—"
    try:
        parsed = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return value
    local = parsed.replace(tzinfo=timezone.utc).astimezone(IST)
    return local.strftime("%d %b %Y, %H:%M IST").lstrip("0")


def ist_date(value: str | None) -> date:
    """The IST calendar date of a UTC timestamp; today's if there is none."""
    if not value:
        return datetime.now(timezone.utc).astimezone(IST).date()
    try:
        parsed = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.now(timezone.utc).astimezone(IST).date()
    return parsed.replace(tzinfo=timezone.utc).astimezone(IST).date()


_NA = ('<span class="na" title="{title}" aria-label="no data">&mdash;</span>')


def dash(value: Any, *, unit: str = "", why: str = "No data") -> Markup:
    """Render a metric, or an em dash if there is nothing behind it.

    Every number in this report goes through here. The em dash is not decoration: a KPI that
    shows 0 is asserting that we looked and the answer was none, and a KPI that shows an em dash
    is admitting we do not know. Sagar acts on those two differently - one is a finding, the
    other is a job that has not run - and a report that renders them identically is worse than
    one that renders neither.
    """
    if value is None or value == "":
        return Markup(_NA.format(title=escape(why)))
    if isinstance(value, float):
        return Markup(f"{value:,.1f}{escape(unit)}")
    return Markup(f"{escape(value)}{escape(unit)}")


def canonical_json(payload: Any) -> str:
    """Sorted keys, no whitespace. The input to data_sha256."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


# ===========================================================================
# Loading
# ===========================================================================

def load_report_data(
    conn: sqlite3.Connection,
    campaign_id: str,
    *,
    mode: str = "EXPORT",
    top_limit: int = 20,
) -> ReportData:
    """Twelve queries, one pass, no per-row SQL.

    Grouping happens here rather than in the templates so a template can never accidentally
    trigger a lazy query while rendering row 3,000 of a table.
    """
    conn.row_factory = sqlite3.Row
    params = {"campaign_id": campaign_id}

    campaign = conn.execute(Q_CAMPAIGN, params).fetchone()
    if campaign is None:
        raise ValueError(f"no campaign with id {campaign_id!r}")

    kpis = Kpis.from_row(conn.execute(Q_KPIS, params).fetchone())
    city_cards = [CitySummary.from_row(r) for r in conn.execute(Q_CITY_SUMMARY, params)]
    rows = [BusinessRow.from_row(r) for r in conn.execute(Q_ROWS, params)]

    findings, sources = _load_findings(conn, params)
    opportunities = {r["business_id"]: OpportunityView.from_row(r)
                     for r in conn.execute(Q_OPPORTUNITY, params)}
    modules: dict[str, list[ModuleView]] = {}
    for row in conn.execute(Q_MODULES, params):
        modules.setdefault(row["business_id"], []).append(
            ModuleView(module=row["module"], ordinal=_get(row, "ordinal", 0),
                       rationale=_opt(row, "rationale")))
    contacts: dict[str, list[ContactSummary]] = {}
    for row in conn.execute(Q_CONTACTS, params):
        contacts.setdefault(row["business_id"], []).append(
            ContactSummary(kind=row["kind"], n_total=_get(row, "n_total", 0),
                           n_confirmed=_get(row, "n_confirmed", 0)))
    history: dict[str, list[HistoryEvent]] = {}
    for row in conn.execute(Q_HISTORY, params):
        history.setdefault(row["business_id"], []).append(HistoryEvent.from_row(row))

    cmp_city = [CityCompareRow.from_row(r) for r in conn.execute(Q_CMP_CITY, params)]
    cmp_industry = [IndustryCompareRow.from_row(r)
                    for r in conn.execute(Q_CMP_INDUSTRY, params)]

    top20: list[TopOpportunity] = []
    top_params = {"campaign_id": campaign_id, "limit": top_limit}
    for rank, row in enumerate(conn.execute(Q_TOP20, top_params), start=1):
        biz_id = row["business_id"]
        breakdown = parse_breakdown(_opt(row, "score_breakdown"))
        state = _verif_state_for(row["status"], _flag(row, "is_verified"))
        top20.append(TopOpportunity(
            rank=rank, business_id=biz_id, name=row["name"], city=row["city"],
            industry=row["industry"], opportunity_score=row["opportunity_score"],
            opportunity_band=_opt(row, "opportunity_band"),
            potential_system=_opt(row, "potential_system"),
            research_confidence=_opt(row, "research_confidence"),
            research_confidence_pct=_opt(row, "research_confidence_pct"),
            verif_state=state,
            verification_badge=_verification_badge(state),
            reason=top_reason(breakdown, findings.get(biz_id, []),
                              _opt(row, "top_observed_statement")),
            short=biz_id[-10:],
        ))

    header = HeaderFacts(
        found=_get(campaign, "h_found", 0),
        researched=_get(campaign, "h_researched", 0),
        qualified=_get(campaign, "h_qualified", 0),
        skipped=_get(campaign, "h_skipped", 0),
        skipped_pipeline=_get(campaign, "h_skipped_pipeline", 0),
        rejected=_get(campaign, "h_rejected", 0),
        needs_verification=_get(campaign, "h_needs_verification", 0),
        ready=_get(campaign, "h_ready", 0),
    )

    warnings = _counter_drift(campaign, header, kpis)
    unscored = kpis.total - kpis.scored
    if unscored:
        warnings.append(
            f"{unscored} business(es) carry no opportunity score. They are excluded from "
            f"every score band and from the top-opportunities table."
        )

    groups = _build_groups(rows)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return ReportData(
        campaign_id=campaign_id,
        campaign_name=campaign["name"],
        created_at=_opt(campaign, "created_at"),
        campaign_status=_get(campaign, "campaign_status", "DRAFT"),
        research_depth=_get(campaign, "research_depth", "STANDARD"),
        min_opportunity_score=_get(campaign, "min_opportunity_score", 0),
        size_filter=_render_json_filter(_opt(campaign, "size_filter"), "all sizes"),
        industries_filter=_render_json_filter(_opt(campaign, "industries"), "all industries"),
        cities_display=_get(campaign, "cities_display", "—"),
        created_by_name=_opt(campaign, "created_by_name"),
        research_model_id=_opt(campaign, "research_model_id"),
        research_prompt_version=_opt(campaign, "research_prompt_version"),
        header=header, kpis=kpis, city_cards=city_cards, rows=rows, groups=groups,
        city_tabs=_city_tabs(city_cards, rows),
        industry_tabs=_industry_tabs(rows),
        findings=findings, sources=sources, opportunities=opportunities, modules=modules,
        contacts=contacts, history=history,
        cmp_city=cmp_city, cmp_industry=cmp_industry, top20=top20,
        warnings=warnings,
        generated_at=generated_at,
        generated_at_ist=fmt_ist(generated_at),
        generated_by=_opt(campaign, "created_by_name"),
        mode=mode,
    )


def _verif_state_for(status: str, is_verified: bool) -> str:
    if status in ("REJECTED", "SKIPPED"):
        return status
    if status == "CONTACT_READY":
        return "CONTACT_READY"
    if is_verified:
        return "VERIFIED"
    return status


def _verification_badge(state: str) -> tuple[str, str]:
    return {
        "CONTACT_READY": ("ok", "READY"),
        "VERIFIED": ("ok", "VERIFIED"),
        "NEEDS_VERIFICATION": ("warn", "NOT VERIFIED"),
        "AI_RESEARCHED": ("warn", "AI RESEARCHED"),
        "REJECTED": ("bad", "REJECTED"),
        "SKIPPED": ("mute", "SKIPPED"),
    }.get(state, ("warn", state.replace("_", " ")))


def _load_findings(
    conn: sqlite3.Connection, params: dict[str, Any]
) -> tuple[dict[str, list[FindingView]], dict[str, list[SourceRef]]]:
    """Collapse the (finding x source) fan-out and number sources per business.

    Numbering is first-citation order, so the [1] beside a statement and the [1] in the source
    list are the same source in a printed page as well as on screen.
    """
    findings: dict[str, list[FindingView]] = {}
    sources: dict[str, list[SourceRef]] = {}
    seen: dict[str, dict[str, SourceRef]] = {}
    current: dict[str, FindingView] = {}

    for row in conn.execute(Q_FINDINGS, params):
        biz = row["business_id"]
        fid = row["finding_id"]
        view = current.get(fid)
        if view is None:
            view = FindingView(
                business_id=biz, finding_id=fid, kind=row["kind"],
                dimension=_get(row, "dimension", "OTHER"), label=_opt(row, "label"),
                statement=row["statement"], confidence=_opt(row, "confidence"),
                confidence_pct=_opt(row, "confidence_pct"),
                weight=float(_get(row, "weight", 1.0)),
                unknown_reason=_opt(row, "unknown_reason"),
                inference_note=_opt(row, "inference_note"),
            )
            current[fid] = view
            findings.setdefault(biz, []).append(view)

        source_id = _opt(row, "source_id")
        if not source_id:
            continue
        per_biz = seen.setdefault(biz, {})
        ref = per_biz.get(source_id)
        if ref is None:
            ref = SourceRef(
                source_id=source_id, name=_get(row, "source_name", "Source"),
                url=safe_url(_opt(row, "source_url")),
                source_type=_get(row, "source_type", "OTHER"),
                checked_at=_opt(row, "checked_at"),
                excerpt=_opt(row, "information_obtained"),
                number=len(per_biz) + 1,
            )
            per_biz[source_id] = ref
            sources.setdefault(biz, []).append(ref)
        elif ref.excerpt is None:
            ref.excerpt = _opt(row, "information_obtained")
        view.sources.append(ref)

    return findings, sources


def _render_json_filter(raw: str | None, empty_label: str) -> str:
    if not raw:
        return empty_label
    try:
        values = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if not values:
        return empty_label
    return ", ".join(str(v) for v in values)


def _counter_drift(campaign: sqlite3.Row, header: HeaderFacts, kpis: Kpis) -> list[str]:
    """Compare campaigns.n_* to the live aggregate and say so, loudly, in the footer.

    The report renders the aggregate and never repairs the counter: repairing a counter from a
    read path is how a reporting bug becomes a data bug.
    """
    out: list[str] = []
    checks = (
        ("n_discovered", header.found), ("n_researched", header.researched),
        ("n_qualified", header.qualified), ("n_skipped", header.skipped),
        ("n_verified", kpis.verified), ("n_contacted", kpis.contacted),
    )
    for column, live in checks:
        stored = _opt(campaign, column)
        if stored is not None and int(stored) != int(live):
            out.append(f"campaigns.{column} says {stored}, live count is {live}. "
                       f"The report shows {live}.")
    return out


def _build_groups(rows: Sequence[BusinessRow]) -> list[CategoryGroup]:
    """Category groups, biggest first, OTHER last.

    The biggest group is the one worth reading first; OTHER is a bucket, not a subject, so it
    sorts to the bottom whatever its size.
    """
    buckets: dict[str, list[BusinessRow]] = {}
    for row in rows:
        buckets.setdefault(row.category, []).append(row)

    def key(item: tuple[str, list[BusinessRow]]) -> tuple[int, int, str]:
        category, members = item
        return (1 if category == "OTHER" else 0, -len(members),
                CATEGORY_LABEL.get(category, category))

    return [CategoryGroup(category=c, rows=m) for c, m in sorted(buckets.items(), key=key)]


def _city_tabs(cards: Sequence[CitySummary], rows: Sequence[BusinessRow]) -> list[tuple[str, str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.city_slug] = counts.get(row.city_slug, 0) + 1
    tabs: list[tuple[str, str, int]] = [("ALL", "All", len(rows))]
    seen = set()
    for card in cards:
        seen.add(card.city_slug)
        tabs.append((card.city_slug, card.city, counts.get(card.city_slug, 0)))
    # A business whose city is not in campaign_cities still needs a tab, or it becomes
    # invisible in every pane but ALL.
    for row in rows:
        if row.city_slug not in seen:
            seen.add(row.city_slug)
            tabs.append((row.city_slug, row.city, counts.get(row.city_slug, 0)))
    return tabs


def _industry_tabs(rows: Sequence[BusinessRow]) -> list[tuple[str, str, int]]:
    """Enum order, not count order, so tab positions stay put between days."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.industry] = counts.get(row.industry, 0) + 1
    tabs: list[tuple[str, str, int]] = [("ALL", "All", len(rows))]
    for industry in INDUSTRY_ORDER:
        if counts.get(industry):
            tabs.append((industry, INDUSTRY_LABEL[industry], counts[industry]))
    for industry, count in sorted(counts.items()):
        if industry not in INDUSTRY_ORDER:
            tabs.append((industry, industry.replace("_", " ").title(), count))
    return tabs


# ===========================================================================
# Rendering
# ===========================================================================

def _environment() -> Environment:
    """Autoescape on, StrictUndefined on.

    Autoescape is the load-bearing one: business names are scraped off the public web and a
    name containing markup must render as text in a file Sagar may forward to somebody else.
    StrictUndefined turns a metric the loader forgot to pass into a build failure rather than
    an empty cell that looks like a measured zero.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["dash"] = dash
    env.filters["inr"] = inr
    env.filters["fmt_date"] = fmt_date
    env.filters["fmt_ist"] = fmt_ist
    env.filters["safe_url"] = safe_url
    env.globals.update(
        INDUSTRY_LABEL=INDUSTRY_LABEL,
        CATEGORY_LABEL=CATEGORY_LABEL,
        CATEGORY_ONE=CATEGORY_ONE,
        CONTACT_CHIP=CONTACT_CHIP,
        BLOCK_REASON=BLOCK_REASON,
        score_class=score_class,
        score_band=score_band,
        confidence_class=confidence_class,
        generator_version=GENERATOR_VERSION,
    )
    return env


def render_report(data: ReportData, *, mode: str = "EXPORT",
                  app_base_url: str | None = None) -> str:
    """ReportData to one self-contained HTML string. No file I/O, no database."""
    env = _environment()
    template = env.get_template("report.html.j2")
    return template.render(d=data, mode=mode, app_base=safe_url(app_base_url) or "")


# ===========================================================================
# Building: write the file, then record it
# ===========================================================================

def _atomic_write_text(path: Path, text: str) -> int:
    """Write .tmp, then replace. Never leave a half-written report where a whole one was."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = text.encode("utf-8")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return len(data)


def _atomic_write_bytes(path: Path, blob: bytes) -> int:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, path)
    return len(blob)


def _data_payload(data: ReportData) -> dict[str, Any]:
    """The numbers, with the volatile generation metadata stripped.

    data_sha256 over this answers "are these the numbers the database produced on 26 Aug",
    which is the only thing that stays checkable after the file has been emailed to somebody.
    Regenerating an unchanged campaign gives a new content_sha256 and an identical data_sha256.
    """
    payload = asdict(data)
    for volatile in ("generated_at", "generated_at_ist", "generated_by", "mode"):
        payload.pop(volatile, None)
    return payload


def _existing_rel_paths(conn: sqlite3.Connection, campaign_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT rel_path FROM report_exports WHERE campaign_id = :campaign_id",
        {"campaign_id": campaign_id},
    ).fetchall()
    return {row["rel_path"] for row in rows}


def _record_export(
    conn: sqlite3.Connection,
    *,
    campaign_id: str,
    fmt: str,
    scope: str,
    title: str,
    filename: str,
    rel_path: str,
    size_bytes: int,
    content_sha256: str,
    data_sha256: str,
    data_rel_path: str | None,
    row_count: int,
    contains_pii: bool,
    user_id: str | None,
) -> str:
    """One INSERT plus its audit row, in one transaction.

    SIMPLIFIED: docs/03-html-report.md section 3.2.7 brackets the write with a two-phase
    PENDING -> READY row so a crashed build leaves a FAILED row rather than nothing. The
    report_exports table in 001_schema.sql has no status and no error column and makes both
    hashes NOT NULL, so a PENDING row cannot be expressed. The row is therefore written after
    os.replace(), which means a crash mid-build leaves a file with no row rather than a row
    with no file - the safer of the two, since the retention sweep keys off rows.
    """
    export_id = new_id_for("report_exports")
    with db.transaction(conn) as tx:
        tx.execute(
            """
            INSERT INTO report_exports
                (id, campaign_id, fmt, scope, scope_key, title, filename, rel_path,
                 bytes, content_sha256, data_sha256, data_rel_path, row_count,
                 filters_json, columns_json, contains_pii,
                 template_version, generator_version, db_schema_version, query_fingerprint,
                 generated_by, retention_class)
            VALUES
                (:id, :campaign_id, :fmt, :scope, NULL, :title, :filename, :rel_path,
                 :bytes, :content_sha256, :data_sha256, :data_rel_path, :row_count,
                 '{}', NULL, :contains_pii,
                 :template_version, :generator_version, :db_schema_version, :query_fingerprint,
                 :generated_by, 'P2Y')
            """,
            {
                "id": export_id, "campaign_id": campaign_id, "fmt": fmt, "scope": scope,
                "title": title, "filename": filename, "rel_path": rel_path,
                "bytes": size_bytes, "content_sha256": content_sha256,
                "data_sha256": data_sha256, "data_rel_path": data_rel_path,
                "row_count": row_count, "contains_pii": 1 if contains_pii else 0,
                "template_version": TEMPLATE_VERSION,
                "generator_version": GENERATOR_VERSION,
                "db_schema_version": db.schema_version(tx),
                "query_fingerprint": query_fingerprint(),
                "generated_by": user_id,
            },
        )
        audit(
            tx, user_id, "REPORT_GENERATED", "report_exports", export_id,
            after={"fmt": fmt, "rel_path": rel_path, "row_count": row_count},
            campaign_id=campaign_id,
            detail={"content_sha256": content_sha256, "data_sha256": data_sha256,
                    "bytes": size_bytes, "generator_version": GENERATOR_VERSION},
        )
    return export_id


def build_report(
    conn: sqlite3.Connection,
    campaign_id: str,
    *,
    mode: str = "EXPORT",
    app_base_url: str | None = None,
    out_dir: Path | None = None,
    user_id: str | None = None,
    data: ReportData | None = None,
) -> ReportBuild:
    """Load, render, write atomically, and record a report_exports row."""
    started = datetime.now(timezone.utc)
    ensure()
    if data is None:
        data = load_report_data(conn, campaign_id, mode=mode)

    directory = Path(out_dir) if out_dir else (REPORTS_DIR / campaign_id)
    directory.mkdir(parents=True, exist_ok=True)

    cities = [card.city for card in data.city_cards] or [data.cities_display]
    taken = _existing_rel_paths(conn, campaign_id)
    filename = report_filename(
        cities, ist_date(data.created_at), ext="html",
        existing=lambda name: (directory / name).exists()
        or f"{campaign_id}/{name}" in taken,
    )
    path = directory / filename
    rel_path = f"{campaign_id}/{filename}"

    html = render_report(data, mode=mode, app_base_url=app_base_url)
    size_bytes = _atomic_write_text(path, html)
    content_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()

    blob = canonical_json(_data_payload(data)).encode("utf-8")
    data_sha256 = hashlib.sha256(blob).hexdigest()
    data_name = f"{filename}.data.json.gz"
    _atomic_write_bytes(directory / data_name, gzip.compress(blob, mtime=0))
    data_rel_path = f"{campaign_id}/{data_name}"

    export_id = _record_export(
        conn, campaign_id=campaign_id, fmt="HTML", scope="CAMPAIGN",
        title=data.campaign_name, filename=filename, rel_path=rel_path,
        size_bytes=size_bytes, content_sha256=content_sha256, data_sha256=data_sha256,
        data_rel_path=data_rel_path, row_count=data.row_count,
        contains_pii=False, user_id=user_id,
    )

    duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    log.info("wrote %s (%d row(s), %d bytes, %d ms, %s)",
             path, data.row_count, size_bytes, duration_ms, export_id)
    return ReportBuild(
        export_id=export_id, path=path, bytes_written=size_bytes,
        content_sha256=content_sha256, data_sha256=data_sha256,
        data_rel_path=data_rel_path, row_count=data.row_count,
        generated_at=data.generated_at, duration_ms=duration_ms,
    )


def generate_report(
    conn: sqlite3.Connection,
    campaign_id: str,
    *,
    mode: str = "EXPORT",
    app_base_url: str | None = None,
    out_dir: Path | None = None,
    user_id: str | None = None,
) -> Path:
    """Render the campaign report to a self-contained HTML file and return its path."""
    return build_report(conn, campaign_id, mode=mode, app_base_url=app_base_url,
                        out_dir=out_dir, user_id=user_id).path


# ===========================================================================
# CSV
# ===========================================================================

CSV_HEADERS: tuple[str, ...] = (
    "business_id", "business", "city", "industry", "category", "size",
    "website", "website_status", "digital_maturity", "operational_complexity",
    "opportunity_score", "opportunity_band", "potential_problem", "potential_solution",
    "recommended_modules", "expected_benefit", "research_status", "research_confidence",
    "n_observed", "n_inferred", "n_unknown", "sources",
    "verification_status", "verified_on", "contact_available", "outreach_status",
    "discovered_on", "last_sent_on", "n_sent", "n_responses", "response_classification",
    "do_not_contact", "blocking_reason", "campaign",
)

_FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> Any:
    """Neutralise spreadsheet formula injection.

    Business names come off the public web. A business literally named "=cmd|'/c calc'!A1" is
    unlikely, but a research statement that starts with a hyphen is not, and Excel will happily
    evaluate either. Prefixing an apostrophe costs one character of display and removes the
    whole class of problem.
    """
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIX):
        return "'" + value
    return value


def flat_rows(data: ReportData) -> list[list[Any]]:
    """One flat list per business, in the report's own row order.

    Empty cells are empty, not 0 and not an em dash. In a spreadsheet an em dash is a text
    value that poisons a whole numeric column; a blank is what AVERAGE() and a pivot table
    expect, and the research_status column beside it carries the distinction the em dash
    carried in the HTML.
    """
    out: list[list[Any]] = []
    for row in data.rows:
        findings = data.findings.get(row.business_id, [])
        kinds = {"OBSERVED": 0, "INFERRED": 0, "UNKNOWN": 0}
        for finding in findings:
            kinds[finding.kind] = kinds.get(finding.kind, 0) + 1
        modules = data.modules.get(row.business_id, [])
        history = data.history.get(row.business_id, [])
        classification = next(
            (h.response_classification for h in reversed(history)
             if h.response_classification), None)
        research_status = "COMPLETE" if row.research_complete else (
            "PENDING" if row.researched_at else "NONE")
        out.append([
            row.business_id,
            row.name,
            row.city,
            INDUSTRY_LABEL.get(row.industry, row.industry),
            CATEGORY_ONE.get(row.category, row.category),
            row.size_band,
            row.website if row.website_status == "PRESENT" else "",
            row.website_status,
            row.digital_maturity if row.digital_maturity is not None else "",
            row.operational_complexity if row.operational_complexity is not None else "",
            row.opportunity_score if row.opportunity_score is not None else "",
            row.opportunity_band or "",
            row.potential_problem or "",
            row.potential_solution or "",
            " · ".join(m.label for m in modules),
            row.expected_benefit or "",
            research_status,
            row.research_confidence or "",
            kinds["OBSERVED"], kinds["INFERRED"], kinds["UNKNOWN"],
            len(data.sources.get(row.business_id, [])),
            row.verif_state,
            (row.verified_at or "")[:10],
            row.contact_attr,
            row.outreach_badge[1],
            row.discovered_on or "",
            (row.last_sent_at or "")[:10],
            row.n_sent,
            row.n_responses,
            classification or "",
            "YES" if row.is_suppressed else "NO",
            row.block_reason,
            data.campaign_name,
        ])
    return out


def export_csv(
    conn: sqlite3.Connection,
    campaign_id: str,
    *,
    out_dir: Path | None = None,
    user_id: str | None = None,
    data: ReportData | None = None,
) -> Path:
    """Write the flat business table as CSV and record a report_exports row.

    Written with a UTF-8 BOM because the machine that opens this is running Excel on Windows,
    and Excel without a BOM renders every business name with a Devanagari or accented character
    as mojibake. The BOM is ugly and it is the difference between a usable file and an evening
    spent working out why the names are broken.

    Contact VALUES are not in this file. docs/03-html-report.md section 3.11.1 offers an
    --include-contacts flag; it is deliberately not implemented here, because a CSV of business
    contact addresses circulating by email is the exact artefact the DPDP purpose-limitation
    design in _CONTEXT.md section 4 exists to keep from proliferating.
    """
    ensure()
    if data is None:
        data = load_report_data(conn, campaign_id)

    directory = Path(out_dir) if out_dir else (REPORTS_DIR / campaign_id)
    directory.mkdir(parents=True, exist_ok=True)

    cities = [card.city for card in data.city_cards] or [data.cities_display]
    taken = _existing_rel_paths(conn, campaign_id)
    filename = report_filename(
        cities, ist_date(data.created_at), ext="csv",
        existing=lambda name: (directory / name).exists()
        or f"{campaign_id}/{name}" in taken,
    )
    path = directory / filename
    rows = flat_rows(data)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        writer.writerow(CSV_HEADERS)
        for row in rows:
            writer.writerow([csv_safe(value) for value in row])
    os.replace(tmp, path)

    blob = path.read_bytes()
    content_sha256 = hashlib.sha256(blob).hexdigest()
    data_sha256 = hashlib.sha256(
        canonical_json(_data_payload(data)).encode("utf-8")).hexdigest()

    _record_export(
        conn, campaign_id=campaign_id, fmt="CSV", scope="CAMPAIGN",
        title=data.campaign_name, filename=filename,
        rel_path=f"{campaign_id}/{filename}", size_bytes=len(blob),
        content_sha256=content_sha256, data_sha256=data_sha256, data_rel_path=None,
        row_count=len(rows), contains_pii=False, user_id=user_id,
    )
    log.info("wrote %d business row(s) to %s", len(rows), path)
    return path
