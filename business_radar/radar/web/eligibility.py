"""The eight gates a business must clear before a message may be transmitted to it.

Without this module the confirm dialog is a screenshot. Every gate here was true at some point
in the past - when the business was verified, when it was selected, when the draft was written -
and the whole risk of an outreach tool is the gap between then and now. An opt-out arrives at
06:10; the tab has been open since 09:40 the previous evening; the button still looks live. So
this runs inside the send request, against the database as it is in that request, and its answer
is stored on the message row as the snapshot of what was true at the moment of transmission.

The gates are 05-outreach-workflow.md section 5.9's A-H. The refusal sentences are
15-ui-wireframe.md section 15.18.3's map, imported from radar/policy.py when that module exists
so the report, the grid, the workspace and this screen cannot drift apart, and defined here when
it does not.

SIMPLIFIED: doc 05 section 5.9.12 evaluates forty sub-clauses across the eight gates and records
per-clause evidence ids. This evaluates the clause of each gate that can actually block a send on
this build - the ones with rows behind them in 001_schema.sql - and names the row it read.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from radar.models import ContactPolicy, utc_now

log = logging.getLogger("radar.web.eligibility")

# The eleven sentences 15-ui-wireframe.md section 15.18.3 fixes, plus the five this build's
# gates B, C and H need. One map, one register: name the missing precondition and where to fix
# it, never a generic refusal.
_LOCAL_BLOCK_REASON: dict[str, str] = {
    "A_SUPPRESSED":           "Do not contact: an opt-out or suppression is recorded.",
    "B_CHANNEL_OFF":          "This channel is switched off in contact policy.",
    "B_CHANNEL_UNCONFIGURED": "This channel has no working credentials yet - see Settings, Channels.",
    "C_RESEARCH_INCOMPLETE":  "Research has not finished for this business.",
    "C_NO_OBSERVED_FINDING":  "Nothing observed about this business can be cited, so nothing may be claimed.",
    "D_HUMAN_OWNED":          "This is a live lead - the machine stops here and you take it.",
    "D_VERIFICATION_REVOKED": "You rejected or skipped this business.",
    "D_NOT_VERIFIED":         "This business still needs your verification.",
    "D_VERIFICATION_STALE":   "The verification has expired - re-verify before selecting.",
    "E_CONTACT_MISSING":      "Verified, but no confirmed contact yet.",
    "F_IN_FLIGHT":            "A message for this business is already awaiting approval.",
    "G_STOP_AFTER_REJECTION": "This business replied that it is not interested.",
    "G_MAX_ATTEMPTS":         "The maximum number of outreach attempts has been reached.",
    "G_MAX_FOLLOWUPS":        "The maximum number of follow-ups has been reached.",
    "G_MIN_DAYS":             "Contacted too recently - the minimum gap has not elapsed.",
    "H_DAILY_CAP":            "Today's send cap has been reached. This resumes tomorrow.",
    "H_MIN_GAP":              "The last send was less than the minimum gap ago.",
}

try:  # pragma: no cover - depends on which sibling modules have landed
    from radar.policy import BLOCK_REASON as _POLICY_BLOCK_REASON  # type: ignore

    BLOCK_REASON: dict[str, str] = {**_LOCAL_BLOCK_REASON, **dict(_POLICY_BLOCK_REASON)}
except Exception:  # ImportError, or a policy module still being written
    BLOCK_REASON = dict(_LOCAL_BLOCK_REASON)

PASS = "PASS"
WARN = "WARN"
BLOCK = "BLOCK"
NA = "N/A"

GATE_TITLES: dict[str, str] = {
    "A": "no suppression on the business, address, number or domain",
    "B": "channel enabled and its transport resolved",
    "C": "research complete, with observed findings to cite",
    "D": "a live human verification",
    "E": "a human-confirmed contact",
    "F": "no message already in flight for this business",
    "G": "contact frequency policy",
    "H": "sending-account protection",
}


@dataclass(frozen=True, slots=True)
class Gate:
    """One gate's verdict, with the sentence that goes next to the control it disables."""

    letter: str
    verdict: str                       # PASS | WARN | BLOCK | N/A
    sentence: str
    code: str | None = None            # a BLOCK_REASON key when not PASS
    evidence: tuple[str, ...] = ()     # row ids read to reach this verdict

    @property
    def blocks(self) -> bool:
        return self.verdict == BLOCK

    @property
    def tone(self) -> str:
        return {PASS: "ok", WARN: "warn", BLOCK: "bad"}.get(self.verdict, "mute")


@dataclass(frozen=True, slots=True)
class Eligibility:
    """The whole A-H verdict for one (business, contact, channel) at one instant."""

    gates: tuple[Gate, ...]
    checked_at: str = field(default_factory=utc_now)

    @property
    def blockers(self) -> tuple[Gate, ...]:
        return tuple(g for g in self.gates if g.blocks)

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def business_blockers(self) -> tuple[Gate, ...]:
        """Everything except gate B, which is about the transport rather than the business.

        Selecting, drafting, policy-checking and approving all remain legitimate on a laptop
        with no Gmail credentials - 17-channel-configuration.md section 17.4.1 is explicit
        that work done while unconfigured is kept and labelled, not refused. Only the
        transmission step reads gate B.
        """
        return tuple(g for g in self.blockers if g.letter != "B")

    @property
    def business_blocked(self) -> bool:
        return bool(self.business_blockers)

    @property
    def warnings(self) -> tuple[Gate, ...]:
        return tuple(g for g in self.gates if g.verdict == WARN)

    @property
    def first_block_sentence(self) -> str:
        blockers = self.blockers
        return blockers[0].sentence if blockers else ""

    def to_dict(self) -> dict[str, Any]:
        """The JSON written to selections.eligibility_snapshot and to a message row."""
        return {
            "checked_at": self.checked_at,
            "blocked": self.blocked,
            "gates": [
                {"gate": g.letter, "verdict": g.verdict, "code": g.code,
                 "sentence": g.sentence, "evidence": list(g.evidence)}
                for g in self.gates
            ],
        }


def check_send_eligibility(
    conn: sqlite3.Connection,
    *,
    business_id: str,
    channel: str,
    policy: ContactPolicy,
    contact_id: str | None = None,
    channel_configured: bool = True,
    channel_switch_on: bool = True,
    exclude_message_id: str | None = None,
) -> Eligibility:
    """Evaluate gates A-H now, against the database as it is in this transaction."""
    now = utc_now()
    gates: list[Gate] = [
        _gate_a(conn, business_id),
        _gate_b(channel, channel_configured, channel_switch_on),
        _gate_c(conn, business_id),
        _gate_d(conn, business_id, policy, now),
        _gate_e(conn, business_id, channel, contact_id),
        _gate_f(conn, business_id, exclude_message_id),
        _gate_g(conn, business_id, policy, now),
        _gate_h(conn, policy, now),
    ]
    return Eligibility(gates=tuple(gates), checked_at=now)


# ---------------------------------------------------------------------------
# A - suppression. Invariant 3: one opt-out blocks every channel, permanently.
# ---------------------------------------------------------------------------

_SUPPRESSION_SQL = """
SELECT s.id, s.scope, s.reason, s.created_at
  FROM suppressions s
  LEFT JOIN business_contacts c
         ON c.business_id = ?
        AND (   (s.scope = 'EMAIL'    AND c.kind = 'EMAIL'    AND c.value_norm = s.value_norm)
             OR (s.scope = 'PHONE'    AND c.kind = 'PHONE'    AND c.value_norm = s.value_norm)
             OR (s.scope = 'WHATSAPP' AND c.kind = 'WHATSAPP' AND c.value_norm = s.value_norm)
             OR (s.scope = 'DOMAIN'   AND c.domain IS NOT NULL AND c.domain = s.value_norm))
 WHERE s.released_at IS NULL
   AND (   (s.scope = 'BUSINESS' AND s.value_norm = ?)
        OR (s.business_id = ?)
        OR c.id IS NOT NULL)
 ORDER BY s.created_at
 LIMIT 1
"""


def _gate_a(conn: sqlite3.Connection, business_id: str) -> Gate:
    row = conn.execute(_SUPPRESSION_SQL, (business_id, business_id, business_id)).fetchone()
    if row is None:
        return Gate("A", PASS, "No opt-out on file for this business, this address, this "
                               "number or this domain.")
    return Gate(
        "A", BLOCK, BLOCK_REASON["A_SUPPRESSED"], "A_SUPPRESSED",
        evidence=(str(row["id"]),),
    )


# ---------------------------------------------------------------------------
# B - the channel itself
# ---------------------------------------------------------------------------

def _gate_b(channel: str, configured: bool, switch_on: bool) -> Gate:
    if not switch_on:
        return Gate("B", BLOCK, BLOCK_REASON["B_CHANNEL_OFF"], "B_CHANNEL_OFF")
    if not configured:
        return Gate("B", BLOCK, BLOCK_REASON["B_CHANNEL_UNCONFIGURED"],
                    "B_CHANNEL_UNCONFIGURED")
    return Gate("B", PASS, "Channel %s enabled, transport resolved." % channel)


# ---------------------------------------------------------------------------
# C - research. Invariant 4 begins here: no citable fact, no claim, no message.
# ---------------------------------------------------------------------------

def _gate_c(conn: sqlite3.Connection, business_id: str) -> Gate:
    complete = conn.execute(
        "SELECT COUNT(*) AS n FROM research_runs "
        " WHERE business_id = ? AND status = 'COMPLETE'", (business_id,),
    ).fetchone()["n"]
    if not complete:
        return Gate("C", BLOCK, BLOCK_REASON["C_RESEARCH_INCOMPLETE"], "C_RESEARCH_INCOMPLETE")

    row = conn.execute(
        "SELECT COUNT(DISTINCT f.id) AS n FROM research_findings f "
        "  JOIN finding_sources fs ON fs.finding_id = f.id "
        " WHERE f.business_id = ? AND f.kind = 'OBSERVED' AND f.is_current = 1",
        (business_id,),
    ).fetchone()
    n = int(row["n"])
    if n == 0:
        return Gate("C", BLOCK, BLOCK_REASON["C_NO_OBSERVED_FINDING"], "C_NO_OBSERVED_FINDING")
    return Gate("C", PASS, "Research complete, %d observed finding%s cited."
                % (n, "" if n == 1 else "s"))


# ---------------------------------------------------------------------------
# D - the verification gate. Spec 45's whole point.
# ---------------------------------------------------------------------------

def _gate_d(conn: sqlite3.Connection, business_id: str, policy: ContactPolicy,
            now: str) -> Gate:
    biz = conn.execute(
        "SELECT status, status_verification_id FROM businesses WHERE id = ?", (business_id,),
    ).fetchone()
    if biz is None:
        return Gate("D", BLOCK, BLOCK_REASON["D_NOT_VERIFIED"], "D_NOT_VERIFIED")

    status = biz["status"]
    if status == "HUMAN_HANDOFF":
        return Gate("D", BLOCK, BLOCK_REASON["D_HUMAN_OWNED"], "D_HUMAN_OWNED")
    if status in ("REJECTED", "SKIPPED"):
        return Gate("D", BLOCK, BLOCK_REASON["D_VERIFICATION_REVOKED"],
                    "D_VERIFICATION_REVOKED")

    ver = conn.execute(
        "SELECT id, verified_at, "
        "       CAST(julianday(?) - julianday(verified_at) AS INTEGER) AS age_days "
        "  FROM verifications "
        " WHERE business_id = ? AND state = 'SUBMITTED' AND verdict = 'VERIFIED' "
        "   AND superseded_at IS NULL "
        " ORDER BY verified_at DESC LIMIT 1",
        (now, business_id),
    ).fetchone()
    if ver is None:
        return Gate("D", BLOCK, BLOCK_REASON["D_NOT_VERIFIED"], "D_NOT_VERIFIED")

    age = int(ver["age_days"] or 0)
    valid = int(policy.verification_valid_days)
    if age > valid:
        return Gate(
            "D", BLOCK,
            "The verification is %d days old and expires after %d - re-verify before sending."
            % (age, valid),
            "D_VERIFICATION_STALE", evidence=(str(ver["id"]),),
        )
    return Gate(
        "D", PASS,
        "Verified %s, %d day%s old, valid for %d."
        % (str(ver["verified_at"])[:10], age, "" if age == 1 else "s", valid),
        evidence=(str(ver["id"]),),
    )


# ---------------------------------------------------------------------------
# E - the contact. A human confirmed this address, or there is no send.
# ---------------------------------------------------------------------------

def _gate_e(conn: sqlite3.Connection, business_id: str, channel: str,
            contact_id: str | None) -> Gate:
    kind = "EMAIL" if channel == "EMAIL" else ("WHATSAPP" if channel == "WHATSAPP" else "PHONE")
    if channel == "MANUAL":
        return Gate("E", NA, "Manual outreach records what you sent yourself; no stored "
                             "contact is used.")
    if contact_id:
        row = conn.execute(
            "SELECT id, human_verified, is_active, valid FROM business_contacts WHERE id = ?",
            (contact_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, human_verified, is_active, valid FROM business_contacts "
            " WHERE business_id = ? AND kind = ? AND is_active = 1 AND valid = 1 "
            "   AND human_verified = 1 "
            " ORDER BY is_primary DESC, captured_at LIMIT 1",
            (business_id, kind),
        ).fetchone()

    if row is None:
        return Gate("E", BLOCK, BLOCK_REASON["E_CONTACT_MISSING"], "E_CONTACT_MISSING")
    if not (row["is_active"] and row["valid"] and row["human_verified"]):
        return Gate("E", BLOCK, BLOCK_REASON["E_CONTACT_MISSING"], "E_CONTACT_MISSING",
                    evidence=(str(row["id"]),))
    return Gate("E", PASS, "Contact confirmed by a human.", evidence=(str(row["id"]),))


# ---------------------------------------------------------------------------
# F - one conversation at a time
# ---------------------------------------------------------------------------

def _gate_f(conn: sqlite3.Connection, business_id: str,
            exclude_message_id: str | None) -> Gate:
    row = conn.execute(
        "SELECT id, status FROM outreach_messages "
        " WHERE business_id = ? AND status IN ('PENDING_APPROVAL','APPROVED','QUEUED') "
        "   AND id <> COALESCE(?, '') "
        " ORDER BY created_at LIMIT 1",
        (business_id, exclude_message_id),
    ).fetchone()
    if row is None:
        return Gate("F", PASS, "No message in flight for this business.")
    return Gate("F", BLOCK, BLOCK_REASON["F_IN_FLIGHT"], "F_IN_FLIGHT",
                evidence=(str(row["id"]),))


# ---------------------------------------------------------------------------
# G - contact frequency, spec 31
# ---------------------------------------------------------------------------

def _gate_g(conn: sqlite3.Connection, business_id: str, policy: ContactPolicy,
            now: str) -> Gate:
    if policy.stop_after_rejection or policy.stop_after_opt_out:
        stopper = conn.execute(
            "SELECT id, COALESCE(human_classification, classification) AS cls "
            "  FROM responses "
            " WHERE business_id = ? "
            "   AND COALESCE(human_classification, classification) IN "
            "       ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE','OPT_OUT','COMPLAINT') "
            " ORDER BY received_at DESC LIMIT 1",
            (business_id,),
        ).fetchone()
        if stopper is not None:
            return Gate("G", BLOCK, BLOCK_REASON["G_STOP_AFTER_REJECTION"],
                        "G_STOP_AFTER_REJECTION", evidence=(str(stopper["id"]),))

    counts = conn.execute(
        "SELECT COUNT(*) AS attempts, MAX(sent_at) AS last_sent, "
        "       CAST(julianday(?) - julianday(MAX(sent_at)) AS INTEGER) AS days_since "
        "  FROM outreach_messages "
        " WHERE business_id = ? AND status IN ('SENT','DELIVERED','BOUNCED')",
        (now, business_id),
    ).fetchone()
    attempts = int(counts["attempts"] or 0)

    if attempts >= int(policy.max_attempts):
        return Gate("G", BLOCK,
                    "%d of %d outreach attempts have already been made."
                    % (attempts, policy.max_attempts),
                    "G_MAX_ATTEMPTS")
    if attempts == 0:
        return Gate("G", PASS, "Never contacted; the %d-day minimum gap does not apply."
                    % policy.min_days_between_outreach)

    if attempts - 1 >= int(policy.max_followups):
        return Gate("G", BLOCK,
                    "%d follow-up%s already sent; the maximum is %d."
                    % (attempts - 1, "" if attempts - 1 == 1 else "s", policy.max_followups),
                    "G_MAX_FOLLOWUPS")

    days = int(counts["days_since"] or 0)
    gap = int(policy.min_days_between_outreach)
    if days < gap:
        return Gate("G", BLOCK,
                    "Contacted %d day%s ago; the minimum gap is %d days."
                    % (days, "" if days == 1 else "s", gap),
                    "G_MIN_DAYS")
    return Gate("G", PASS, "Last contacted %d days ago; the minimum gap is %d." % (days, gap))


# ---------------------------------------------------------------------------
# H - protecting one free Gmail account
# ---------------------------------------------------------------------------

def _gate_h(conn: sqlite3.Connection, policy: ContactPolicy, now: str) -> Gate:
    today = now[:10]
    row = conn.execute(
        "SELECT COUNT(*) AS n, MAX(sent_at) AS last_sent "
        "  FROM outreach_messages "
        " WHERE status IN ('SENT','DELIVERED','BOUNCED') AND substr(sent_at, 1, 10) = ?",
        (today,),
    ).fetchone()
    sent_today = int(row["n"] or 0)
    cap = int(policy.daily_send_cap)

    if sent_today >= cap:
        return Gate("H", BLOCK,
                    "Today's sends are %d of %d. The cap has been reached." % (sent_today, cap),
                    "H_DAILY_CAP")

    last = row["last_sent"]
    if last:
        elapsed = conn.execute(
            "SELECT CAST((julianday(?) - julianday(?)) * 86400 AS INTEGER) AS secs",
            (now, last),
        ).fetchone()["secs"]
        gap = int(policy.send_min_gap_seconds)
        if elapsed is not None and int(elapsed) < gap:
            return Gate("H", BLOCK,
                        "The last send was %ds ago; the minimum gap is %ds."
                        % (int(elapsed), gap),
                        "H_MIN_GAP")

    verdict = WARN if sent_today >= max(cap - 3, 1) else PASS
    return Gate("H", verdict, "Today's sends %d of %d." % (sent_today, cap))
