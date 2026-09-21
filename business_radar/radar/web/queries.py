"""Every SELECT the screens run, in one file, so that two screens cannot disagree.

The failure this module prevents is the one docs/_CONTEXT.md invariant 5 is about. A dashboard
that counts "verified" with its own CASE expression and a report that counts it with another
will, on some Tuesday, print 21 in one place and 19 in the other, and from that moment nobody
believes either number. So "qualified", "verified", "ready" and "sent" are defined once - mostly
by the v_report_business view that 030_report_views.sql owns - and every counter on every screen
aggregates over the same definition.

The second reason this file exists is that a metric with no rows behind it must render as an em
dash rather than a zero. That distinction only survives if the query returns None instead of 0,
which means the SQL and the template have to be designed together. Counting functions here
return None where 03 section 3.5 says the figure is not applicable yet.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

log = logging.getLogger("radar.web.queries")


# ---------------------------------------------------------------------------
# campaigns
# ---------------------------------------------------------------------------

def campaigns(conn: sqlite3.Connection, status_filter: str = "all") -> list[sqlite3.Row]:
    """The campaign list, newest first, with the two numbers the cards show."""
    clause = ""
    params: list[Any] = []
    if status_filter == "active":
        clause = " WHERE c.status IN ('QUEUED','DISCOVERING','RESEARCHING','REPORTING','PAUSED')"
    elif status_filter == "complete":
        clause = " WHERE c.status = 'COMPLETE'"
    elif status_filter == "draft":
        clause = " WHERE c.status = 'DRAFT'"
    return conn.execute(
        "SELECT c.*, "
        "       (SELECT COUNT(*) FROM campaign_businesses cb WHERE cb.campaign_id = c.id) "
        "           AS n_members, "
        "       (SELECT COUNT(*) FROM campaign_cities cc WHERE cc.campaign_id = c.id) "
        "           AS n_cities, "
        "       (SELECT group_concat(cc.city, ', ') FROM campaign_cities cc "
        "         WHERE cc.campaign_id = c.id) AS city_list, "
        "       u.display_name AS created_by_name "
        "  FROM campaigns c LEFT JOIN users u ON u.id = c.created_by"
        + clause +
        " ORDER BY c.created_at DESC",
        params,
    ).fetchall()


def campaign(conn: sqlite3.Connection, campaign_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT c.*, u.display_name AS created_by_name "
        "  FROM campaigns c LEFT JOIN users u ON u.id = c.created_by WHERE c.id = ?",
        (campaign_id,),
    ).fetchone()


def campaign_cities(conn: sqlite3.Connection, campaign_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM campaign_cities WHERE campaign_id = ? ORDER BY ordinal, city",
        (campaign_id,),
    ).fetchall()


def campaign_funnel(conn: sqlite3.Connection, campaign_id: str) -> dict[str, int | None]:
    """15-ui-wireframe.md section 15.3.2's thirteen figures, every one an aggregate.

    Figures 11-13 return None rather than 0 in a campaign that never produced a handoff:
    "Won: 0" invites the reading "we tried and lost", "Won: -" says "this has not got that far".
    """
    row = conn.execute(
        "SELECT COUNT(*) AS found, "
        "       SUM(research_complete)     AS researched, "
        "       SUM(is_qualified)          AS qualified, "
        "       SUM(is_verified)           AS verified, "
        "       SUM(is_ready_for_outreach) AS ready, "
        "       SUM(CASE WHEN n_sent > 0 THEN 1 ELSE 0 END) AS sent, "
        "       SUM(n_responses)           AS responses, "
        "       SUM(is_interested)         AS interested "
        "  FROM v_report_business WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()

    counts = conn.execute(
        "SELECT (SELECT COUNT(*) FROM selections s "
        "         WHERE s.campaign_id = ? AND s.state <> 'REMOVED')              AS selected, "
        "       (SELECT COUNT(*) FROM outreach_drafts d "
        "         WHERE d.campaign_id = ? AND d.superseded_by IS NULL)           AS prepared, "
        "       (SELECT COUNT(*) FROM outreach_approvals a "
        "          JOIN outreach_messages m ON m.id = a.message_id "
        "         WHERE m.campaign_id = ? AND a.revoked_at IS NULL)              AS approved",
        (campaign_id, campaign_id, campaign_id),
    ).fetchone()

    handoffs = conn.execute(
        "SELECT COUNT(*) AS n, "
        "       SUM(CASE WHEN demo_held_at    IS NOT NULL THEN 1 ELSE 0 END) AS demos, "
        "       SUM(CASE WHEN proposal_sent_at IS NOT NULL THEN 1 ELSE 0 END) AS proposals, "
        "       SUM(CASE WHEN outcome = 'WON' THEN 1 ELSE 0 END)              AS won "
        "  FROM handoffs WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()

    found = int(row["found"] or 0)
    researched = int(row["researched"] or 0)
    sent = int(row["sent"] or 0)
    any_handoff = int(handoffs["n"] or 0) > 0

    return {
        "found": found,
        "researched": researched,
        "qualified": int(row["qualified"] or 0) if researched else None,
        "verified": int(row["verified"] or 0),
        "selected": int(counts["selected"] or 0),
        "prepared": int(counts["prepared"] or 0),
        "approved": int(counts["approved"] or 0),
        "sent": sent,
        "responses": int(row["responses"] or 0) if sent else None,
        "interested": int(row["interested"] or 0) if sent else None,
        "demos": int(handoffs["demos"] or 0) if any_handoff else None,
        "proposals": int(handoffs["proposals"] or 0) if any_handoff else None,
        "won": int(handoffs["won"] or 0) if any_handoff else None,
    }


def campaign_businesses(conn: sqlite3.Connection, campaign_id: str,
                        limit: int = 300) -> list[sqlite3.Row]:
    """The grid. Ordered by score, with unscored rows sinking to the bottom."""
    return conn.execute(
        "SELECT v.*, b.contact_ready_block_code, b.skip_reason "
        "  FROM v_report_business v JOIN businesses b ON b.id = v.business_id "
        " WHERE v.campaign_id = ? "
        " ORDER BY (v.opportunity_score IS NULL), v.opportunity_score DESC, v.name "
        " LIMIT ?",
        (campaign_id, limit),
    ).fetchall()


# ---------------------------------------------------------------------------
# one business
# ---------------------------------------------------------------------------

def business(conn: sqlite3.Connection, business_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()


def contacts(conn: sqlite3.Connection, business_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT c.*, u.display_name AS verified_by_name "
        "  FROM business_contacts c LEFT JOIN users u ON u.id = c.human_verified_by "
        " WHERE c.business_id = ? AND c.is_active = 1 "
        " ORDER BY c.is_primary DESC, c.kind, c.captured_at",
        (business_id,),
    ).fetchall()


def latest_run(conn: sqlite3.Connection, business_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM research_runs WHERE business_id = ? "
        " ORDER BY (status = 'COMPLETE') DESC, COALESCE(finished_at, created_at) DESC LIMIT 1",
        (business_id,),
    ).fetchone()


def findings_by_kind(conn: sqlite3.Connection, business_id: str) -> dict[str, list[dict]]:
    """The three groups, always all three keys, always in ask order.

    An empty group is returned as an empty list rather than omitted: a missing OBSERVED
    fieldset on the page would read as "we did not look", which is a different claim.
    """
    rows = conn.execute(
        "SELECT f.*, COUNT(fs.source_id) AS n_sources "
        "  FROM research_findings f "
        "  LEFT JOIN finding_sources fs ON fs.finding_id = f.id "
        " WHERE f.business_id = ? AND f.is_current = 1 "
        " GROUP BY f.id ORDER BY f.ordinal, f.created_at",
        (business_id,),
    ).fetchall()

    by_id = {r["id"]: r for r in rows}
    grouped: dict[str, list[dict]] = {"OBSERVED": [], "INFERRED": [], "UNKNOWN": []}
    for row in rows:
        item = dict(row)
        item["sources"] = _sources_for_finding(conn, row["id"])
        item["antecedents"] = []
        if row["kind"] == "INFERRED":
            try:
                for fid in json.loads(row["derived_from"] or "[]"):
                    parent = by_id.get(fid)
                    if parent is not None:
                        item["antecedents"].append(parent["label"])
            except (ValueError, TypeError):
                log.warning("finding %s has unreadable derived_from", row["id"])
        grouped.setdefault(row["kind"], []).append(item)
    return grouped


def _sources_for_finding(conn: sqlite3.Connection, finding_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT s.id, s.name, s.url, s.source_type, s.checked_at, s.snapshot_path, "
        "       fs.excerpt "
        "  FROM finding_sources fs JOIN sources s ON s.id = fs.source_id "
        " WHERE fs.finding_id = ? ORDER BY s.checked_at",
        (finding_id,),
    ).fetchall()


def sources(conn: sqlite3.Connection, business_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sources WHERE business_id = ? ORDER BY checked_at DESC", (business_id,),
    ).fetchall()


def opportunity(conn: sqlite3.Connection, business_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM opportunities WHERE business_id = ? AND is_current = 1", (business_id,),
    ).fetchone()


def modules(conn: sqlite3.Connection, business_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM opportunity_modules WHERE business_id = ? AND is_current = 1 "
        " ORDER BY ordinal, module",
        (business_id,),
    ).fetchall()


def live_suppressions(conn: sqlite3.Connection, business_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT DISTINCT s.* FROM suppressions s "
        "  LEFT JOIN business_contacts c ON c.business_id = ? "
        " WHERE s.released_at IS NULL "
        "   AND (   (s.scope = 'BUSINESS' AND s.value_norm = ?) "
        "        OR s.business_id = ? "
        "        OR (s.scope = 'EMAIL'    AND c.kind = 'EMAIL'    AND c.value_norm = s.value_norm) "
        "        OR (s.scope = 'PHONE'    AND c.kind = 'PHONE'    AND c.value_norm = s.value_norm) "
        "        OR (s.scope = 'WHATSAPP' AND c.kind = 'WHATSAPP' AND c.value_norm = s.value_norm) "
        "        OR (s.scope = 'DOMAIN'   AND c.domain = s.value_norm)) "
        " ORDER BY s.created_at",
        (business_id, business_id, business_id),
    ).fetchall()


#: 05 section 5.18.1's OUTREACH_HISTORY_SQL. One query, three renderings - the business page,
#: preview panel 9 and the confirm dialog - so the three cannot disagree about what was sent.
OUTREACH_HISTORY_SQL = """
SELECT m.id, m.channel, m.status, m.sequence_no, m.subject_final,
       m.to_address_display, m.sent_at, m.delivered_at, m.failed_at, m.failure_code,
       m.created_at, a.approved_at, u.display_name AS approved_by_name,
       (SELECT COUNT(*) FROM responses r WHERE r.message_id = m.id) AS n_responses,
       (SELECT COALESCE(r.human_classification, r.classification) FROM responses r
         WHERE r.message_id = m.id ORDER BY r.received_at DESC LIMIT 1) AS last_classification
  FROM outreach_messages m
  LEFT JOIN outreach_approvals a ON a.id = m.approval_id
  LEFT JOIN users u ON u.id = a.approved_by
 WHERE m.business_id = ?
 ORDER BY COALESCE(m.sent_at, m.created_at) DESC
"""


def outreach_history(conn: sqlite3.Connection, business_id: str) -> list[sqlite3.Row]:
    return conn.execute(OUTREACH_HISTORY_SQL, (business_id,)).fetchall()


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------

def open_verification(conn: sqlite3.Connection, business_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM verifications WHERE business_id = ? AND state = 'DRAFT'", (business_id,),
    ).fetchone()


def live_verification(conn: sqlite3.Connection, business_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT v.*, u.display_name AS verified_by_name FROM verifications v "
        "  LEFT JOIN users u ON u.id = v.verified_by "
        " WHERE v.business_id = ? AND v.state = 'SUBMITTED' AND v.superseded_at IS NULL "
        " ORDER BY v.verified_at DESC LIMIT 1",
        (business_id,),
    ).fetchone()


def verification_checks(conn: sqlite3.Connection, verification_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM verification_checks WHERE verification_id = ? ORDER BY ordinal",
        (verification_id,),
    ).fetchall()
    return {r["check_key"]: r for r in rows}


def reason_codes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM verification_reason_codes ORDER BY ordinal, code"
    ).fetchall()


def verification_queue(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    """Businesses waiting on Sagar, highest opportunity first."""
    return conn.execute(
        "SELECT b.id, b.name, b.city, b.industry, b.category, b.status, "
        "       o.score AS opportunity_score, o.band AS opportunity_band "
        "  FROM businesses b LEFT JOIN opportunities o "
        "         ON o.business_id = b.id AND o.is_current = 1 "
        " WHERE b.status IN ('AI_RESEARCHED','NEEDS_VERIFICATION') AND b.merged_into_id IS NULL "
        " ORDER BY (o.score IS NULL), o.score DESC, b.name LIMIT ?",
        (limit,),
    ).fetchall()


# ---------------------------------------------------------------------------
# outreach
# ---------------------------------------------------------------------------

def contact_ready(conn: sqlite3.Connection, limit: int = 200) -> list[sqlite3.Row]:
    """CONTACT_READY businesses that are not already in the tray."""
    return conn.execute(
        "SELECT b.id, b.name, b.city, b.industry, b.category, b.status, "
        "       o.score AS opportunity_score, o.band AS opportunity_band, "
        "       b.first_seen_campaign_id AS campaign_id "
        "  FROM businesses b LEFT JOIN opportunities o "
        "         ON o.business_id = b.id AND o.is_current = 1 "
        " WHERE b.status = 'CONTACT_READY' AND b.merged_into_id IS NULL "
        "   AND NOT EXISTS (SELECT 1 FROM selections s "
        "                    WHERE s.business_id = b.id AND s.state <> 'REMOVED') "
        " ORDER BY (o.score IS NULL), o.score DESC, b.name LIMIT ?",
        (limit,),
    ).fetchall()


def tray(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Everything currently selected, in the order the left rail groups it."""
    return conn.execute(
        "SELECT s.*, b.name, b.category, b.size_band, b.status AS business_status, "
        "       o.score AS opportunity_score, o.band AS opportunity_band, "
        "       o.potential_solution, "
        "       (SELECT d.id FROM outreach_drafts d "
        "         WHERE d.selection_id = s.id AND d.superseded_by IS NULL "
        "         ORDER BY d.created_at DESC LIMIT 1) AS draft_id "
        "  FROM selections s "
        "  JOIN businesses b ON b.id = s.business_id "
        "  LEFT JOIN opportunities o ON o.business_id = b.id AND o.is_current = 1 "
        " WHERE s.state <> 'REMOVED' "
        " ORDER BY s.city, (o.score IS NULL), o.score DESC, b.name",
    ).fetchall()


def draft(conn: sqlite3.Connection, draft_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT d.*, COALESCE(d.body_edited, d.body) AS final_body, "
        "       b.name AS business_name, b.city, b.industry, b.category, b.size_band, "
        "       b.status AS business_status, "
        "       c.value_display AS contact_display, c.value_norm AS contact_norm, "
        "       c.kind AS contact_kind, c.is_role_address, c.human_verified, "
        "       c.human_verified_at, c.source_url AS contact_source_url, "
        "       c.captured_at AS contact_captured_at, "
        "       cu.display_name AS contact_verified_by_name, "
        "       m.id AS message_id, m.status AS message_status, m.body_hash, "
        "       m.to_address_norm, m.approval_id, "
        "       o.score AS opportunity_score, o.band AS opportunity_band, "
        "       o.confidence AS opportunity_confidence, o.confidence_pct, "
        "       o.potential_problem, o.potential_solution, o.expected_benefit "
        "  FROM outreach_drafts d "
        "  JOIN businesses b ON b.id = d.business_id "
        "  LEFT JOIN business_contacts c ON c.id = d.contact_id "
        "  LEFT JOIN users cu ON cu.id = c.human_verified_by "
        "  LEFT JOIN outreach_messages m ON m.draft_id = d.id "
        "  LEFT JOIN opportunities o ON o.business_id = b.id AND o.is_current = 1 "
        " WHERE d.id = ? ORDER BY m.created_at DESC LIMIT 1",
        (draft_id,),
    ).fetchone()


def message(conn: sqlite3.Connection, message_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM outreach_messages WHERE id = ?", (message_id,),
    ).fetchone()


def approval(conn: sqlite3.Connection, approval_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM outreach_approvals WHERE id = ?", (approval_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# handoffs
# ---------------------------------------------------------------------------

def handoffs(conn: sqlite3.Connection, state: str = "open") -> list[sqlite3.Row]:
    """URGENT first, then most overdue, then oldest. Not sortable, on purpose.

    A queue that can be sorted by "newest" is a queue that hides the thing you are avoiding.
    """
    clause = " WHERE h.state IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS')"
    if state == "all":
        clause = ""
    elif state == "closed":
        clause = " WHERE h.state = 'CLOSED'"
    return conn.execute(
        "SELECT h.*, b.name AS business_name, b.city, "
        "       r.body_excerpt, r.received_at, "
        "       COALESCE(r.human_classification, r.classification) AS classification "
        "  FROM handoffs h "
        "  JOIN businesses b ON b.id = h.business_id "
        "  LEFT JOIN responses r ON r.id = h.response_id"
        + clause +
        " ORDER BY CASE h.priority WHEN 'URGENT' THEN 0 WHEN 'HIGH' THEN 1 ELSE 2 END, "
        "          h.sla_ack_due_at, h.created_at",
    ).fetchall()


# ---------------------------------------------------------------------------
# policy
# ---------------------------------------------------------------------------

def contact_policy_row(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM contact_policy WHERE id = 'GLOBAL'").fetchone()
    if row is None:  # pragma: no cover - 001_schema.sql seeds it
        raise RuntimeError("contact_policy 'GLOBAL' is missing; the database is not migrated")
    return row


def sent_today(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) AS n FROM outreach_messages "
        " WHERE status IN ('SENT','DELIVERED','BOUNCED') "
        "   AND substr(sent_at, 1, 10) = strftime('%Y-%m-%d','now')"
    ).fetchone()["n"])
