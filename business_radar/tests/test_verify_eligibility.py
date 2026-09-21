"""The verification gate and the eligibility engine, exercised against a real database.

Two things are being proved here. The happy path runs end to end - a researched business is
opened, nine-checked, signed, and promoted to CONTACT_READY without anybody touching SQL - and
each safety rule bites when it should. The second half matters more: a gate that does not fire
reads like protection and provides none.

No network, no API key, nothing but a temporary SQLite file.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import db, verify
from radar.eligibility import (
    check_send_eligibility,
    effective_daily_cap,
    effective_policy,
    normalise_contact,
    registrable_domain,
)
from radar.ids import new_id
from radar.models import BusinessStatus, utc_now

OWNER = "usr_00000000000000000000000000"


#: The migrations these two modules depend on: the base schema, and the two cached columns on
#: businesses that refresh_contact_readiness() writes. Migrating only these keeps the suite
#: green while other modules' migrations are still being written next door, and it documents
#: exactly what verify.py and eligibility.py need from the schema.
REQUIRED_MIGRATIONS = ("001_schema.sql", "010_verify_eligibility.sql")


@pytest.fixture()
def conn(tmp_path: Path):
    import shutil

    from radar.paths import MIGRATIONS_DIR

    staged = tmp_path / "migrations"
    staged.mkdir()
    for name in REQUIRED_MIGRATIONS:
        shutil.copy(MIGRATIONS_DIR / name, staged / name)

    connection = db.connect(tmp_path / "radar.db")
    db.migrate(connection, directory=staged)
    yield connection
    connection.close()


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def make_campaign(conn: sqlite3.Connection) -> str:
    cid = new_id("cmp")
    conn.execute(
        "INSERT INTO campaigns (id, name, slug, created_by) VALUES (?,?,?,?)",
        (cid, "Dhule test", f"dhule-{cid[-6:]}", OWNER),
    )
    return cid


def make_business(conn: sqlite3.Connection, campaign_id: str,
                  name: str = "Sample Hospital") -> str:
    bid = new_id("biz")
    conn.execute(
        """
        INSERT INTO businesses (id, business_key, name, name_norm, city, city_slug,
                                industry, category, website_domain, first_seen_campaign_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (bid, f"dhule|hospital|{bid[-8:]}", name, name.lower(), "Dhule", "dhule",
         "HEALTHCARE", "HOSPITAL", "example.invalid", campaign_id),
    )
    return bid


def make_research(conn: sqlite3.Connection, business_id: str, campaign_id: str) -> str:
    rid = new_id("res")
    conn.execute(
        """
        INSERT INTO research_runs (id, business_id, campaign_id, status, model_id,
                                   prompt_version, started_at, finished_at, quota_requests)
        VALUES (?,?,?,'COMPLETE','gemini-2.5-flash','research-v1',?,?,1)
        """,
        (rid, business_id, campaign_id, utc_now(), utc_now()),
    )
    src = new_id("src")
    conn.execute(
        """
        INSERT INTO sources (id, business_id, name, url, url_norm, source_type,
                             information_obtained, research_run_id)
        VALUES (?,?,?,?,?,'SITE',?,?)
        """,
        (src, business_id, "Official site", "https://example.invalid/about",
         "https://example.invalid/about", "departments listed on the about page", rid),
    )
    fnd = new_id("fnd")
    conn.execute(
        """
        INSERT INTO research_findings (id, business_id, research_run_id, kind, dimension,
                                       label, statement, confidence)
        VALUES (?,?,?,'OBSERVED','OPERATIONS',?,?,'HIGH')
        """,
        (fnd, business_id, rid, "Six departments",
         "The about page lists six clinical departments across two floors."),
    )
    conn.execute(
        "INSERT INTO finding_sources (finding_id, source_id, excerpt) VALUES (?,?,?)",
        (fnd, src, "Departments: Medicine, Surgery, Paediatrics"),
    )
    opp = new_id("opp")
    conn.execute(
        """
        INSERT INTO opportunities (id, business_id, research_run_id, campaign_id,
                                   potential_problem, potential_solution, expected_benefit,
                                   score, band, confidence, confidence_pct, is_current)
        VALUES (?,?,?,?,?,?,?,?,?,'HIGH',85,1)
        """,
        (opp, business_id, rid, campaign_id,
         "Six departments scheduled on paper", "A shared scheduling module",
         "Fewer clashes and one visible rota", 84, "HIGH"),
    )
    conn.execute(
        "UPDATE businesses SET research_status='COMPLETE', opportunity_score=84,"
        " opportunity_band='HIGH', research_confidence='HIGH' WHERE id=?",
        (business_id,),
    )
    return rid


def make_contact(conn: sqlite3.Connection, business_id: str,
                 value: str = "info@example.invalid", verified: bool = False) -> str:
    cid = new_id("cnt")
    point = normalise_contact("EMAIL", value)
    conn.execute(
        """
        INSERT INTO business_contacts (id, business_id, kind, value_raw, value_norm,
                                       value_dedupe, value_display, domain, is_role_address,
                                       source_url, human_verified, human_verified_at,
                                       human_verified_by)
        VALUES (?,?,'EMAIL',?,?,?,?,?,1,?,?,?,?)
        """,
        (cid, business_id, value, point.value_norm, point.value_dedupe, point.display,
         point.domain, "https://example.invalid/contact",
         1 if verified else 0, utc_now() if verified else None, OWNER if verified else None),
    )
    return cid


def ready_business(conn: sqlite3.Connection) -> tuple[str, str, str]:
    """A researched business with one contact, ready for the checklist."""
    campaign_id = make_campaign(conn)
    business_id = make_business(conn, campaign_id)
    make_research(conn, business_id, campaign_id)
    contact_id = make_contact(conn, business_id)
    return campaign_id, business_id, contact_id


ALL_PASS = {key: True for key in verify.CHECK_BY_KEY}
WHY = "Opened the site and the listing; six departments and the address both check out."


def sign(conn: sqlite3.Connection, business_id: str, campaign_id: str,
         checks=None, **kwargs) -> verify.SubmitResult:
    ver_id = verify.open_verification(conn, business_id, OWNER, campaign_id=campaign_id,
                                      dwell_required_ms=0)
    return verify.submit_verification(
        conn, business_id, OWNER, checks or ALL_PASS, kwargs.pop("note", WHY),
        verification_id=ver_id, campaign_id=campaign_id, **kwargs
    )


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


def test_nine_checks_promote_a_business_to_contact_ready(conn):
    campaign_id, business_id, contact_id = ready_business(conn)

    result = sign(conn, business_id, campaign_id)

    assert result.verdict == "VERIFIED"
    assert result.business_status == BusinessStatus.CONTACT_READY
    assert result.readiness is not None and result.readiness.ok

    row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    assert row["status"] == "CONTACT_READY"
    assert row["contact_ready_at"] is not None
    assert row["contact_ready_block_code"] is None
    assert row["status_verification_id"] == result.verification_id

    # The checklist is stored answer by answer, not as a rollup.
    checks = conn.execute(
        "SELECT check_key, passed FROM verification_checks WHERE verification_id=?"
        " ORDER BY ordinal",
        (result.verification_id,),
    ).fetchall()
    assert [c["check_key"] for c in checks] == list(verify.CHECK_BY_KEY)
    assert all(c["passed"] == 1 for c in checks)

    # Check 5 confirmed the contact, which is what CONTACT_READY depends on.
    assert conn.execute(
        "SELECT human_verified FROM business_contacts WHERE id=?", (contact_id,)
    ).fetchone()["human_verified"] == 1


def test_a_contact_ready_business_passes_every_gate(conn):
    campaign_id, business_id, contact_id = ready_business(conn)
    sign(conn, business_id, campaign_id)
    conn.execute("UPDATE contact_policy SET email_sending_domain='gmail.com' WHERE id='GLOBAL'")

    elig = check_send_eligibility(conn, business_id, contact_id, "EMAIL", stage="PREVIEW",
                                  campaign_id=campaign_id)

    assert elig.allowed, elig.blocking_sentence
    assert elig.blocking_code is None
    # Every gate reports, always, so a stored snapshot is a complete record rather than a note
    # about whichever objection happened to come first.
    from radar.eligibility import GATE_ORDER

    assert len(elig.gates) == len(GATE_ORDER)
    assert [g.gate for g in elig.gates] == [gate for gate, _code in GATE_ORDER]
    assert elig.fingerprint


# ---------------------------------------------------------------------------
# Safety invariant 3: an opt-out blocks every channel, permanently
# ---------------------------------------------------------------------------


def test_a_phone_opt_out_blocks_email(conn):
    campaign_id, business_id, contact_id = ready_business(conn)
    sign(conn, business_id, campaign_id)
    conn.execute("UPDATE contact_policy SET email_sending_domain='gmail.com' WHERE id='GLOBAL'")
    phone = normalise_contact("PHONE", "098765 43210")
    conn.execute(
        """
        INSERT INTO business_contacts (id, business_id, kind, value_raw, value_norm,
                                       value_dedupe, value_display, phone_e164, is_role_address)
        VALUES (?,?,'PHONE',?,?,?,?,?,1)
        """,
        (new_id("cnt"), business_id, "098765 43210", phone.value_norm, phone.value_dedupe,
         phone.display, phone.value_norm),
    )
    conn.execute(
        """
        INSERT INTO suppressions (id, scope, value_norm, business_id, reason, source)
        VALUES (?,'PHONE',?,?,'REPLY_OPT_OUT','a reply saying stop calling')
        """,
        (new_id("sup"), phone.value_norm, business_id),
    )

    elig = check_send_eligibility(conn, business_id, contact_id, "EMAIL", stage="PREVIEW",
                                  campaign_id=campaign_id)

    assert not elig.allowed
    assert elig.blocking_code == "A_SUPPRESSED_PHONE"
    assert elig.blocked_by("A3")


def test_a_suppression_demotes_contact_ready_but_keeps_the_signature(conn):
    campaign_id, business_id, contact_id = ready_business(conn)
    result = sign(conn, business_id, campaign_id)
    conn.execute(
        """
        INSERT INTO suppressions (id, scope, value_norm, business_id, reason, source)
        VALUES (?,'BUSINESS',?,?,'REPLY_OPT_OUT','a reply asking to be removed')
        """,
        (new_id("sup"), business_id, business_id),
    )

    readiness = verify.refresh_contact_readiness(conn, business_id, campaign_id=campaign_id)

    assert not readiness.ok
    assert readiness.failing_clause == "C4_NO_SUPPRESSION"
    assert readiness.demote_to == "VERIFIED"
    row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    assert row["status"] == "VERIFIED"
    assert row["contact_ready_block_code"] == "A_SUPPRESSED_BUSINESS"
    # The point of two states: the human's signature is untouched.
    ver = conn.execute("SELECT * FROM verifications WHERE id=?",
                       (result.verification_id,)).fetchone()
    assert ver["superseded_at"] is None
    assert ver["verdict"] == "VERIFIED"


# ---------------------------------------------------------------------------
# The checklist rules
# ---------------------------------------------------------------------------


def test_one_no_rejects_and_needs_a_reason_and_a_note(conn):
    campaign_id, business_id, _ = ready_business(conn)
    checks = dict(ALL_PASS)
    checks["APPEARS_OPERATIONAL"] = {
        "passed": False,
        "note": "The site says permanently closed as of March.",
    }

    result = sign(conn, business_id, campaign_id, checks=checks)

    assert result.verdict == "REJECTED"
    assert result.business_status == "REJECTED"
    assert result.reason_code == "CLOSED"
    # CLOSED is permanent, so it wrote the suppression that makes "permanent" mean something.
    assert result.suppression_id is not None
    sup = conn.execute("SELECT * FROM suppressions WHERE id=?",
                       (result.suppression_id,)).fetchone()
    assert sup["scope"] == "BUSINESS" and sup["released_at"] is None


def test_a_failed_check_without_a_note_is_refused(conn):
    campaign_id, business_id, _ = ready_business(conn)
    checks = dict(ALL_PASS)
    checks["IN_TARGET_CITY"] = {"passed": False, "note": "nope"}

    with pytest.raises(verify.ChecklistError, match="at least 10 characters"):
        sign(conn, business_id, campaign_id, checks=checks)


def test_eight_of_nine_is_not_a_verification(conn):
    campaign_id, business_id, _ = ready_business(conn)
    checks = {k: v for k, v in ALL_PASS.items() if k != "NO_DNC_RECORD"}

    with pytest.raises(verify.ChecklistError, match="all nine items"):
        sign(conn, business_id, campaign_id, checks=checks)


def test_a_verified_verdict_needs_a_real_why_note(conn):
    campaign_id, business_id, _ = ready_business(conn)

    with pytest.raises(verify.ChecklistError, match="15 characters"):
        sign(conn, business_id, campaign_id, note="looks ok")


def test_the_dwell_floor_stops_a_rubber_stamp(conn):
    campaign_id, business_id, _ = ready_business(conn)
    ver_id = verify.open_verification(conn, business_id, OWNER, campaign_id=campaign_id,
                                      dwell_required_ms=20_000)

    with pytest.raises(verify.ChecklistError, match="read the sources"):
        verify.submit_verification(conn, business_id, OWNER, ALL_PASS, WHY,
                                   verification_id=ver_id, campaign_id=campaign_id)


def test_item_nine_is_shown_but_never_ticked_for_you(conn):
    _campaign_id, business_id, _ = ready_business(conn)
    conn.execute(
        """
        INSERT INTO suppressions (id, scope, value_norm, business_id, reason, source)
        VALUES (?,'BUSINESS',?,?,'DNC_LIST','a standing instruction')
        """,
        (new_id("sup"), business_id, business_id),
    )

    items = {i.definition.key: i for i in verify.checklist_for(conn, business_id)}

    assert items["NO_DNC_RECORD"].machine_answer is False
    assert "DNC_LIST" in items["NO_DNC_RECORD"].machine_note
    # Every other item is the human's to answer, with nothing pre-filled.
    assert all(i.machine_answer is None for k, i in items.items() if k != "NO_DNC_RECORD")


# ---------------------------------------------------------------------------
# set_status
# ---------------------------------------------------------------------------


def test_set_status_refuses_an_undeclared_transition_with_a_readable_message(conn):
    campaign_id, business_id, _ = ready_business(conn)

    with pytest.raises(verify.TransitionError) as excinfo:
        verify.set_status(conn, business_id, "CONTACTED", "a_worker", "trying it on")

    assert "AI_RESEARCHED" in str(excinfo.value)
    assert "may reach" in str(excinfo.value)


def test_a_system_actor_cannot_verify(conn):
    campaign_id, business_id, _ = ready_business(conn)
    verify.set_status(conn, business_id, "NEEDS_VERIFICATION", "system", "queued")

    with pytest.raises(verify.TransitionError):
        verify.set_status(conn, business_id, "VERIFIED", "the_worker", "no human involved")


def test_set_status_is_idempotent(conn):
    campaign_id, business_id, _ = ready_business(conn)
    assert verify.set_status(conn, business_id, "NEEDS_VERIFICATION", "sys", "queued") is True
    assert verify.set_status(conn, business_id, "NEEDS_VERIFICATION", "sys", "again") is False


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------


def test_a_stale_verification_demotes_to_the_queue_not_to_a_warning(conn):
    campaign_id, business_id, _ = ready_business(conn)
    result = sign(conn, business_id, campaign_id)
    conn.execute("UPDATE verifications SET verified_at='2020-01-01T00:00:00Z' WHERE id=?",
                 (result.verification_id,))

    readiness = verify.refresh_contact_readiness(conn, business_id, campaign_id=campaign_id)

    assert readiness.failing_clause == "C1_VERIFIED_FRESH"
    assert readiness.demote_to == "NEEDS_VERIFICATION"
    row = conn.execute("SELECT status FROM businesses WHERE id=?", (business_id,)).fetchone()
    assert row["status"] == "NEEDS_VERIFICATION"
    ver = conn.execute("SELECT superseded_at, superseded_reason FROM verifications WHERE id=?",
                       (result.verification_id,)).fetchone()
    assert ver["superseded_at"] is not None
    assert ver["superseded_reason"] == "STALE"


def test_the_sweep_promotes_and_demotes_in_one_pass(conn):
    campaign_id, stale_id, _ = ready_business(conn)
    stale = sign(conn, stale_id, campaign_id)
    conn.execute("UPDATE verifications SET verified_at='2020-01-01T00:00:00Z' WHERE id=?",
                 (stale.verification_id,))

    # A second business held back at signing time by a missing contact, then fixed.
    held_id = make_business(conn, campaign_id, "Second Sample Hospital")
    make_research(conn, held_id, campaign_id)
    sign(conn, held_id, campaign_id)
    assert conn.execute("SELECT status FROM businesses WHERE id=?",
                        (held_id,)).fetchone()["status"] == "VERIFIED"
    contact_id = make_contact(conn, held_id, "reception@example-two.invalid", verified=True)
    assert contact_id

    outcome = verify.sweep_verification_staleness(conn)

    assert outcome.scanned >= 2
    assert outcome.promoted == 1
    assert outcome.reverify_queued == 1
    assert conn.execute("SELECT status FROM businesses WHERE id=?",
                        (held_id,)).fetchone()["status"] == "CONTACT_READY"
    assert conn.execute("SELECT status FROM businesses WHERE id=?",
                        (stale_id,)).fetchone()["status"] == "NEEDS_VERIFICATION"


# ---------------------------------------------------------------------------
# The engine's own contract
# ---------------------------------------------------------------------------


def test_every_gate_is_evaluated_even_after_the_first_block(conn):
    campaign_id, business_id, contact_id = ready_business(conn)

    elig = check_send_eligibility(conn, business_id, contact_id, "EMAIL", stage="PREVIEW",
                                  campaign_id=campaign_id)

    assert not elig.allowed
    # An unverified business fails D and E; the operator sees both, not one per refresh.
    assert len(elig.blocking_gates) >= 2
    assert elig.blocked_by("D_NOT_VERIFIED")
    assert elig.blocked_by("E_CONTACT_NOT_VERIFIED")


def test_the_send_stage_refuses_to_answer_outside_the_write_lock(conn):
    campaign_id, business_id, contact_id = ready_business(conn)

    with pytest.raises(Exception, match="db.transaction"):
        check_send_eligibility(conn, business_id, contact_id, "EMAIL", stage="SEND")


def test_the_snapshot_round_trips(conn):
    campaign_id, business_id, contact_id = ready_business(conn)
    elig = check_send_eligibility(conn, business_id, contact_id, "EMAIL", stage="SELECT",
                                  campaign_id=campaign_id)

    from radar.eligibility import Eligibility

    again = Eligibility.from_json(elig.to_json())

    assert again.fingerprint == elig.fingerprint
    assert again.blocking_code == elig.blocking_code
    assert len(again.gates) == len(elig.gates)
    assert json.loads(elig.to_json())["gates"][0]["gate"] == "A1"


def test_email_is_off_until_somebody_sets_the_sending_account(conn):
    campaign_id, business_id, contact_id = ready_business(conn)
    sign(conn, business_id, campaign_id)

    elig = check_send_eligibility(conn, business_id, contact_id, "EMAIL", stage="PREVIEW",
                                  campaign_id=campaign_id)

    assert elig.blocked_by("B_CHANNEL_DISABLED")
    assert elig.blocked_by("H_NO_UNSUBSCRIBE")


def test_the_frequency_window_blocks_a_second_message(conn):
    campaign_id, business_id, contact_id = ready_business(conn)
    sign(conn, business_id, campaign_id)
    conn.execute("UPDATE contact_policy SET email_sending_domain='gmail.com' WHERE id='GLOBAL'")
    _record_sent_message(conn, business_id, campaign_id, contact_id)

    elig = check_send_eligibility(conn, business_id, contact_id, "EMAIL", stage="PREVIEW",
                                  campaign_id=campaign_id)

    assert not elig.allowed
    assert elig.blocked_by("G_MIN_DAYS")
    assert elig.blocked_by("F_DUPLICATE_EMAIL")


def _record_sent_message(conn: sqlite3.Connection, business_id: str, campaign_id: str,
                         contact_id: str) -> str:
    """A previously sent message, written the only way the triggers allow: through APPROVED."""
    draft_id = new_id("out")
    conn.execute(
        """
        INSERT INTO outreach_drafts (id, business_id, campaign_id, contact_id, channel,
                                     subject, body, model_id, prompt_version, policy_result,
                                     created_by)
        VALUES (?,?,?,?,'EMAIL',?,?,'gemini-2.5-flash','msg-email-v1','PASS',?)
        """,
        (draft_id, business_id, campaign_id, contact_id, "A question about scheduling",
         "Your about page lists six departments.", OWNER),
    )
    contact = conn.execute("SELECT value_norm, value_dedupe, domain FROM business_contacts"
                           " WHERE id=?", (contact_id,)).fetchone()
    msg_id = new_id("msg")
    body_hash = "a" * 64
    conn.execute(
        """
        INSERT INTO outreach_messages (id, draft_id, business_id, campaign_id, contact_id,
                                       channel, status, thread_key, to_address_norm,
                                       to_address_dedupe, recipient_domain, subject_final,
                                       body_final, body_hash, idempotency_key)
        VALUES (?,?,?,?,?,'EMAIL','PENDING_APPROVAL',?,?,?,?,?,?,?,?)
        """,
        (msg_id, draft_id, business_id, campaign_id, contact_id, f"thread-{msg_id}",
         contact["value_norm"], contact["value_dedupe"], contact["domain"],
         "A question about scheduling", "Your about page lists six departments.",
         body_hash, f"idem-{msg_id}"),
    )
    apr_id = new_id("apr")
    conn.execute(
        """
        INSERT INTO outreach_approvals (id, message_id, draft_id, business_id, contact_id,
                                        channel, approved_by, session_id, session_auth_method,
                                        approved_subject, approved_body, approved_body_hash,
                                        approved_to_address, confirmation_text, preview_token,
                                        idempotency_key)
        VALUES (?,?,?,?,?,'EMAIL',?,?,'PASSWORD',?,?,?,?,?,?,?)
        """,
        (apr_id, msg_id, draft_id, business_id, contact_id, OWNER, "ses-test",
         "A question about scheduling", "Your about page lists six departments.",
         body_hash, contact["value_norm"], "Send this message now",
         f"tok-{apr_id}", f"idem-{apr_id}"),
    )
    conn.execute("UPDATE outreach_messages SET status='APPROVED', approval_id=? WHERE id=?",
                 (apr_id, msg_id))
    conn.execute("UPDATE outreach_messages SET status='QUEUED', queued_at=? WHERE id=?",
                 (utc_now(), msg_id))
    conn.execute("UPDATE outreach_messages SET status='SENT', sent_at=?, sent_by=? WHERE id=?",
                 (utc_now(), OWNER, msg_id))
    verify.set_status(conn, business_id, "CONTACTED", "record_send", "a message reached SENT")
    return msg_id


# ---------------------------------------------------------------------------
# Normalisation, where blocking has to win
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("  Sales@ABC-Hospital.IN ", "sales@abc-hospital.in"),
    ("INFO@Example.co.in", "info@example.co.in"),
])
def test_email_normalisation_is_case_folding(raw, expected):
    assert normalise_contact("EMAIL", raw).value_norm == expected


def test_plus_tags_and_gmail_dots_collapse_only_in_the_dedupe_key():
    point = normalise_contact("EMAIL", "S.Agar+leads@googlemail.com")
    assert point.value_norm == "s.agar+leads@googlemail.com"
    assert point.value_dedupe == "sagar@gmail.com"


@pytest.mark.parametrize("raw", ["098765 43210", "+91 98765 43210", "0091-9876543210"])
def test_indian_numbers_reach_one_e164_form(raw):
    assert normalise_contact("PHONE", raw).value_norm == "+919876543210"


def test_a_malformed_number_is_marked_invalid_rather_than_guessed_at():
    point = normalise_contact("PHONE", "12345")
    assert not point.valid and point.error


@pytest.mark.parametrize("raw,expected", [
    ("https://WWW.ABC-Hospital.co.in/contact", "abc-hospital.co.in"),
    ("mail@sub.example.com", "example.com"),
])
def test_registrable_domain(raw, expected):
    assert registrable_domain(raw) == expected


def test_the_warmup_schedule_wins_while_it_is_running(conn):
    from datetime import date

    policy = effective_policy(conn)
    assert effective_daily_cap(policy, date(2026, 8, 27)) == policy.daily_send_cap

    conn.execute("UPDATE contact_policy SET warmup_started_on='2026-08-25' WHERE id='GLOBAL'")
    policy = effective_policy(conn)
    assert effective_daily_cap(policy, date(2026, 8, 25)) == 5
    assert effective_daily_cap(policy, date(2026, 8, 27)) == 10
    assert effective_daily_cap(policy, date(2027, 1, 1)) == policy.daily_send_cap
