"""The foundation tests: the happy path runs end to end, and each safety invariant bites.

The happy-path test is here because every later builder will write the same INSERT sequence and
should be able to copy a working one. The invariant tests are here because a trigger that does
not fire is worse than no trigger: it reads like protection and provides none.

No network, no API key, no fixtures beyond a temporary database.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import audit as audit_mod
from radar import db
from radar.ids import new_id, new_id_for
from radar.models import (
    BusinessStatus,
    FindingKind,
    MessageStatus,
    band_for_score,
    utc_now,
)

OWNER = "usr_00000000000000000000000000"


@pytest.fixture()
def conn(tmp_path: Path):
    connection = db.connect(tmp_path / "radar.db")
    db.migrate(connection)
    yield connection
    connection.close()


# ---------------------------------------------------------------------------
# Builders: the minimum row at each stage, in pipeline order.
# ---------------------------------------------------------------------------

def make_campaign(conn: sqlite3.Connection) -> str:
    cid = new_id("cmp")
    conn.execute(
        "INSERT INTO campaigns (id, name, slug, created_by) VALUES (?,?,?,?)",
        (cid, "Dhule test", f"dhule-{cid[-6:]}", OWNER),
    )
    return cid


def make_business(conn: sqlite3.Connection, campaign_id: str) -> str:
    bid = new_id("biz")
    conn.execute(
        """
        INSERT INTO businesses (id, business_key, name, name_norm, city, city_slug,
                                industry, category, first_seen_campaign_id)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (bid, f"dhule|hospital|{bid[-8:]}", "Sample Hospital", "sample hospital",
         "Dhule", "dhule", "HEALTHCARE", "HOSPITAL", campaign_id),
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
    return rid


def make_source(conn: sqlite3.Connection, business_id: str, run_id: str) -> str:
    sid = new_id("src")
    conn.execute(
        """
        INSERT INTO sources (id, business_id, name, url, url_norm, source_type,
                             information_obtained, research_run_id)
        VALUES (?,?,?,?,?,'SITE',?,?)
        """,
        (sid, business_id, "Official site", "https://example.invalid/about",
         "https://example.invalid/about", "departments listed on the about page", run_id),
    )
    return sid


def make_finding(conn, business_id, run_id, kind=FindingKind.OBSERVED, source_id=None,
                 derived_from=None) -> str:
    fid = new_id("fnd")
    conn.execute(
        """
        INSERT INTO research_findings (id, business_id, research_run_id, kind, dimension,
                                       label, statement, confidence, derived_from,
                                       inference_note, unknown_reason)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            fid, business_id, run_id, str(kind), "OPERATIONS",
            "Six departments",
            "The about page lists six clinical departments across two floors.",
            "LOW" if kind == FindingKind.UNKNOWN else "HIGH",
            derived_from or "[]",
            "listed departments imply shift scheduling" if kind == FindingKind.INFERRED else None,
            "NOT_PUBLISHED" if kind == FindingKind.UNKNOWN else None,
        ),
    )
    if source_id:
        conn.execute(
            "INSERT INTO finding_sources (finding_id, source_id, excerpt) VALUES (?,?,?)",
            (fid, source_id, "Departments: Medicine, Surgery, Paediatrics..."),
        )
    return fid


def make_contact(conn: sqlite3.Connection, business_id: str, verified: bool = True) -> str:
    cid = new_id("cnt")
    conn.execute(
        """
        INSERT INTO business_contacts (id, business_id, kind, value_raw, value_norm,
                                       value_dedupe, value_display, domain,
                                       human_verified, human_verified_at, human_verified_by)
        VALUES (?,?,'EMAIL',?,?,?,?,?,?,?,?)
        """,
        (cid, business_id, "Info@Example.invalid", "info@example.invalid",
         "info@example.invalid", "info@example.invalid", "example.invalid",
         1 if verified else 0, utc_now() if verified else None, OWNER if verified else None),
    )
    return cid


def verify_business(conn: sqlite3.Connection, business_id: str, campaign_id: str) -> str:
    """The full nine-check human verification, then the status move it unlocks."""
    vid = new_id("ver")
    conn.execute(
        """
        INSERT INTO verifications (id, business_id, campaign_id, state, verdict,
                                   checks_passed, checks_failed, why_note, dwell_ms,
                                   verified_by, verified_at, session_id)
        VALUES (?,?,?,'SUBMITTED','VERIFIED',9,0,?,?,?,?,?)
        """,
        (vid, business_id, campaign_id,
         "Opened the site and the listing; the address and phone match.",
         25000, OWNER, utc_now(), "ses-test"),
    )
    from radar.models import VERIFICATION_CHECK_KEYS
    for ordinal, key in enumerate(VERIFICATION_CHECK_KEYS, start=1):
        conn.execute(
            """
            INSERT INTO verification_checks (id, verification_id, business_id, check_key,
                                             ordinal, passed, answered_at, answered_by)
            VALUES (?,?,?,?,?,1,?,?)
            """,
            (new_id("chk"), vid, business_id, key, ordinal, utc_now(), OWNER),
        )

    conn.execute(
        "UPDATE businesses SET status='NEEDS_VERIFICATION', status_actor_kind='SYSTEM' "
        "WHERE id=?", (business_id,))
    conn.execute(
        """
        UPDATE businesses
           SET status='VERIFIED', status_actor_kind='HUMAN',
               status_actor_user_id=?, status_verification_id=?
         WHERE id=?
        """,
        (OWNER, vid, business_id),
    )
    conn.execute(
        "UPDATE businesses SET status='CONTACT_READY', status_actor_kind='SYSTEM', "
        "contact_ready_at=? WHERE id=?", (utc_now(), business_id))
    return vid


def make_draft(conn, business_id, campaign_id, contact_id, fact_ids) -> str:
    import json
    did = new_id("out")
    conn.execute(
        """
        INSERT INTO outreach_drafts (id, business_id, campaign_id, contact_id, channel,
                                     subject, body, model_id, prompt_version, facts_used,
                                     policy_result, policy_version, policy_checked_at,
                                     created_by)
        VALUES (?,?,?,?,'EMAIL',?,?,'gemini-2.5-flash','msg-email-v1',?,'PASS','pol-1',?,?)
        """,
        (did, business_id, campaign_id, contact_id,
         "A question about your department scheduling",
         "I noticed your about page lists six departments.",
         json.dumps(fact_ids), utc_now(), OWNER),
    )
    return did


def make_message(conn, draft_id, business_id, campaign_id, contact_id) -> tuple[str, str]:
    """A DRAFT message, returned with the body hash the approval will have to match."""
    import hashlib
    mid = new_id("msg")
    subject = "A question about your department scheduling"
    body = "I noticed your about page lists six departments."
    body_hash = hashlib.sha256(f"{subject}\x1e{body}".encode()).hexdigest()
    conn.execute(
        """
        INSERT INTO outreach_messages (id, draft_id, business_id, campaign_id, contact_id,
                                       channel, status, thread_key, to_address_norm,
                                       to_address_display, recipient_domain, subject_final,
                                       body_final, body_hash, idempotency_key, provider)
        VALUES (?,?,?,?,?,'EMAIL','DRAFT',?,?,?,?,?,?,?,?,'gmail')
        """,
        (mid, draft_id, business_id, campaign_id, contact_id,
         f"{business_id}:EMAIL:info@example.invalid", "info@example.invalid",
         "info@example.invalid", "example.invalid", subject, body, body_hash, mid),
    )
    return mid, body_hash


def approve(conn, message_id, draft_id, business_id, body_hash) -> str:
    aid = new_id("apr")
    conn.execute(
        """
        INSERT INTO outreach_approvals (id, message_id, draft_id, business_id, channel,
                                        approved_by, session_id, session_auth_method,
                                        approved_subject, approved_body, approved_body_hash,
                                        approved_to_address, confirmation_text,
                                        preview_token, idempotency_key)
        VALUES (?,?,?,?,'EMAIL',?,?,'PASSWORD',?,?,?,?,?,?,?)
        """,
        (aid, message_id, draft_id, business_id, OWNER, "ses-test",
         "A question about your department scheduling",
         "I noticed your about page lists six departments.", body_hash,
         "info@example.invalid",
         "Send this message to info@example.invalid", "tok-test", aid),
    )
    return aid


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------

def test_full_pipeline_reaches_sent(conn):
    """RESEARCH -> REPORT -> VERIFY -> SELECT -> PERSONALIZE -> PREVIEW -> CONFIRM -> SEND."""
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        conn.execute(
            "INSERT INTO campaign_businesses (id, campaign_id, business_id, "
            "city_at_discovery, industry_at_discovery, category_at_discovery) "
            "VALUES (?,?,?,?,?,?)",
            (new_id_for("campaign_businesses"), campaign, business,
             "Dhule", "HEALTHCARE", "HOSPITAL"),
        )

        run = make_research(conn, business, campaign)
        source = make_source(conn, business, run)
        fact = make_finding(conn, business, run, FindingKind.OBSERVED, source_id=source)

        opp = new_id("opp")
        conn.execute(
            """
            INSERT INTO opportunities (id, business_id, research_run_id, campaign_id,
                                       potential_problem, potential_solution,
                                       expected_benefit, score, band)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (opp, business, run, campaign, "Scheduling is on paper",
             "Hospital Operations Platform", "Fewer clashes", 84, band_for_score(84)),
        )
        conn.execute(
            "UPDATE businesses SET opportunity_score=84, opportunity_band='HIGH', "
            "research_status='COMPLETE' WHERE id=?", (business,))

        contact = make_contact(conn, business)
        verify_business(conn, business, campaign)

    row = conn.execute("SELECT status FROM businesses WHERE id=?", (business,)).fetchone()
    assert row["status"] == BusinessStatus.CONTACT_READY

    with db.transaction(conn):
        conn.execute(
            "INSERT INTO selections (id, campaign_id, business_id, city, industry, "
            "eligible_at_select, selected_by) VALUES (?,?,?,?,?,1,?)",
            (new_id("sel"), campaign, business, "Dhule", "HEALTHCARE", OWNER),
        )
        draft = make_draft(conn, business, campaign, contact, [fact])
        message, body_hash = make_message(conn, draft, business, campaign, contact)

        conn.execute("UPDATE outreach_messages SET status='PENDING_APPROVAL' WHERE id=?",
                     (message,))
        approval = approve(conn, message, draft, business, body_hash)
        conn.execute(
            "UPDATE outreach_messages SET status='APPROVED', approval_id=? WHERE id=?",
            (approval, message))
        conn.execute("UPDATE outreach_messages SET status='QUEUED', queued_at=? WHERE id=?",
                     (utc_now(), message))
        conn.execute(
            "UPDATE outreach_messages SET status='SENT', sent_at=?, sent_by=? WHERE id=?",
            (utc_now(), OWNER, message))
        conn.execute(
            "UPDATE businesses SET status='CONTACTED', status_actor_kind='SYSTEM', "
            "first_contacted_at=?, last_contacted_at=? WHERE id=?",
            (utc_now(), utc_now(), business))

        audit_mod.audit(conn, OWNER, "MESSAGE_SENT", "outreach_messages", message,
                        before={"status": "QUEUED"}, after={"status": "SENT"},
                        business_id=business, campaign_id=campaign, message_id=message,
                        detail={"address_masked": "in***@example.invalid"})

    msg = conn.execute("SELECT status, approval_id FROM outreach_messages WHERE id=?",
                       (message,)).fetchone()
    assert msg["status"] == MessageStatus.SENT
    assert msg["approval_id"] == approval
    biz = conn.execute("SELECT status FROM businesses WHERE id=?", (business,)).fetchone()
    assert biz["status"] == BusinessStatus.CONTACTED
    assert audit_mod.verify_chain(conn) == []


# ---------------------------------------------------------------------------
# Invariant 1: no send without a human approval row
# ---------------------------------------------------------------------------

def _queued_message(conn) -> tuple[str, str, str, str]:
    """A message sitting at QUEUED with a live approval. Returns the ids the tests poke at."""
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        run = make_research(conn, business, campaign)
        source = make_source(conn, business, run)
        fact = make_finding(conn, business, run, FindingKind.OBSERVED, source_id=source)
        contact = make_contact(conn, business)
        verify_business(conn, business, campaign)
        draft = make_draft(conn, business, campaign, contact, [fact])
        message, body_hash = make_message(conn, draft, business, campaign, contact)
        conn.execute("UPDATE outreach_messages SET status='PENDING_APPROVAL' WHERE id=?",
                     (message,))
        approval = approve(conn, message, draft, business, body_hash)
        conn.execute(
            "UPDATE outreach_messages SET status='APPROVED', approval_id=? WHERE id=?",
            (approval, message))
        conn.execute("UPDATE outreach_messages SET status='QUEUED' WHERE id=?", (message,))
    return campaign, business, message, approval


def test_the_approval_cannot_be_detached_from_a_queued_message(conn):
    """Layer one: the CHECK constraint. A queued message must carry its approval."""
    campaign, business, message, approval = _queued_message(conn)
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute("UPDATE outreach_messages SET approval_id=NULL WHERE id=?", (message,))
    assert "approval_id" in str(exc.value)


def test_sent_without_approval_is_refused_by_the_trigger_too(conn):
    """Layer two: the trigger, tested with the CHECK layer switched off.

    ignore_check_constraints disables CHECK but not triggers, which is exactly the shape of a
    maintenance session that has decided the constraints are in its way. The trigger is what is
    left, and it has to hold on its own.
    """
    campaign, business, message, approval = _queued_message(conn)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    try:
        conn.execute("UPDATE outreach_messages SET approval_id=NULL WHERE id=?", (message,))
        with pytest.raises(sqlite3.IntegrityError) as exc:
            conn.execute("UPDATE outreach_messages SET status='SENT', sent_at=? WHERE id=?",
                         (utc_now(), message))
        assert "approval" in str(exc.value).lower()
    finally:
        conn.execute("PRAGMA ignore_check_constraints = OFF")


def test_sent_with_a_revoked_approval_is_refused(conn):
    campaign, business, message, approval = _queued_message(conn)
    conn.execute("UPDATE outreach_approvals SET revoked_at=? WHERE id=?",
                 (utc_now(), approval))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE outreach_messages SET status='SENT', sent_at=? WHERE id=?",
                     (utc_now(), message))


def test_sent_with_a_different_body_than_was_approved_is_refused(conn):
    """Approving one body does not authorise sending another."""
    campaign, business, message, approval = _queued_message(conn)
    conn.execute("UPDATE outreach_messages SET body_final=?, body_hash=? WHERE id=?",
                 ("Something else entirely.", "f" * 64, message))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE outreach_messages SET status='SENT', sent_at=? WHERE id=?",
                     (utc_now(), message))


def test_sent_to_a_different_address_than_was_approved_is_refused(conn):
    campaign, business, message, approval = _queued_message(conn)
    conn.execute("UPDATE outreach_messages SET to_address_norm=? WHERE id=?",
                 ("someone.else@example.invalid", message))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE outreach_messages SET status='SENT', sent_at=? WHERE id=?",
                     (utc_now(), message))


# ---------------------------------------------------------------------------
# Invariant 2: SENT only from APPROVED
# ---------------------------------------------------------------------------

def test_draft_cannot_jump_to_sent(conn):
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        run = make_research(conn, business, campaign)
        source = make_source(conn, business, run)
        fact = make_finding(conn, business, run, FindingKind.OBSERVED, source_id=source)
        contact = make_contact(conn, business)
        verify_business(conn, business, campaign)
        draft = make_draft(conn, business, campaign, contact, [fact])
        message, _ = make_message(conn, draft, business, campaign, contact)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE outreach_messages SET status='SENT', sent_at=? WHERE id=?",
                     (utc_now(), message))


def test_a_message_cannot_be_born_sent(conn):
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        run = make_research(conn, business, campaign)
        source = make_source(conn, business, run)
        fact = make_finding(conn, business, run, FindingKind.OBSERVED, source_id=source)
        contact = make_contact(conn, business)
        verify_business(conn, business, campaign)
        draft = make_draft(conn, business, campaign, contact, [fact])

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO outreach_messages (id, draft_id, business_id, campaign_id, channel,
                                           status, thread_key, idempotency_key, subject_final,
                                           sent_at)
            VALUES (?,?,?,?,'EMAIL','SENT','t','k','s',?)
            """,
            (new_id("msg"), draft, business, campaign, utc_now()),
        )


def test_contacted_only_from_contact_ready(conn):
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE businesses SET status='CONTACTED', status_actor_kind='SYSTEM' "
                     "WHERE id=?", (business,))


def test_verified_needs_a_real_human_checklist(conn):
    """A SYSTEM actor cannot promote a business to VERIFIED, with or without a verification."""
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        conn.execute("UPDATE businesses SET status='NEEDS_VERIFICATION' WHERE id=?",
                     (business,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE businesses SET status='VERIFIED', status_actor_kind='SYSTEM' "
                     "WHERE id=?", (business,))


def test_no_draft_before_the_verification_gate(conn):
    """Spec 19: the object the Send button would need cannot exist yet."""
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)      # still AI_RESEARCHED
        contact = make_contact(conn, business)
    with pytest.raises(sqlite3.IntegrityError) as exc:
        make_draft(conn, business, campaign, contact, [])
    assert "verification" in str(exc.value).lower()


def test_no_selection_before_the_verification_gate(conn):
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO selections (id, campaign_id, business_id, city, industry, "
            "eligible_at_select, selected_by) VALUES (?,?,?,?,?,1,?)",
            (new_id("sel"), campaign, business, "Dhule", "HEALTHCARE", OWNER),
        )


# ---------------------------------------------------------------------------
# Invariant 3: opt-out is permanent
# ---------------------------------------------------------------------------

def test_a_suppression_cannot_be_deleted(conn):
    sup = new_id("sup")
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO suppressions (id, scope, value_norm, reason, source) "
            "VALUES (?,'EMAIL',?,'REPLY_OPT_OUT','inbox poll')",
            (sup, "info@example.invalid"),
        )
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute("DELETE FROM suppressions WHERE id=?", (sup,))
    assert "permanent" in str(exc.value).lower()


def test_a_suppression_cannot_be_released_without_an_audit_row(conn):
    sup = new_id("sup")
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO suppressions (id, scope, value_norm, reason, source) "
            "VALUES (?,'EMAIL',?,'COMPLAINT','inbox poll')",
            (sup, "angry@example.invalid"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE suppressions SET released_at=? WHERE id=?", (utc_now(), sup))


# ---------------------------------------------------------------------------
# Invariant 4: every claim traces to a stored finding
# ---------------------------------------------------------------------------

def test_a_finding_cannot_be_promoted_to_observed_without_a_source(conn):
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        run = make_research(conn, business, campaign)
        source = make_source(conn, business, run)
        base = make_finding(conn, business, run, FindingKind.OBSERVED, source_id=source)
        import json
        guess = make_finding(conn, business, run, FindingKind.INFERRED,
                             derived_from=json.dumps([base]))
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute("UPDATE research_findings SET kind='OBSERVED' WHERE id=?", (guess,))
    assert "source" in str(exc.value).lower()


def test_an_observed_finding_cannot_lose_its_last_source(conn):
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        run = make_research(conn, business, campaign)
        source = make_source(conn, business, run)
        fact = make_finding(conn, business, run, FindingKind.OBSERVED, source_id=source)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM finding_sources WHERE finding_id=?", (fact,))


def test_an_inferred_finding_must_name_its_antecedents(conn):
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        run = make_research(conn, business, campaign)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO research_findings (id, business_id, research_run_id, kind, "
            "dimension, label, statement) VALUES (?,?,?,'INFERRED','OPERATIONS',?,?)",
            (new_id("fnd"), business, run, "A hunch", "They probably use paper records."),
        )


def test_an_unknown_finding_must_say_why_and_may_not_be_confident(conn):
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
        run = make_research(conn, business, campaign)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO research_findings (id, business_id, research_run_id, kind, "
            "dimension, label, statement, confidence) "
            "VALUES (?,?,?,'UNKNOWN','FINANCE',?,?,'HIGH')",
            (new_id("fnd"), business, run, "Revenue", "Annual revenue is not published."),
        )


# ---------------------------------------------------------------------------
# The audit log
# ---------------------------------------------------------------------------

def test_audit_log_is_append_only(conn):
    with db.transaction(conn):
        aid = audit_mod.audit(conn, None, "SYSTEM_STARTED", "-", None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE audit_log SET actor_label='someone else' WHERE id=?", (aid,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_log WHERE id=?", (aid,))


def test_audit_chain_verifies_and_detects_a_forged_row(conn):
    with db.transaction(conn):
        for _ in range(5):
            audit_mod.audit(conn, OWNER, "USER_LOGIN", "users", OWNER)
    assert audit_mod.verify_chain(conn) == []

    # Forge a row past the immutability trigger, the way a maintenance session would.
    conn.execute("PRAGMA writable_schema = ON")
    conn.executescript("DROP TRIGGER trg_audit_log_no_update;")
    conn.execute("UPDATE audit_log SET actor_label='mallory' WHERE seq=3")
    problems = audit_mod.verify_chain(conn)
    assert problems and "seq 3" in problems[0]


def test_an_undeclared_audit_action_is_refused(conn):
    with pytest.raises(audit_mod.UnknownAuditAction):
        with db.transaction(conn):
            audit_mod.audit(conn, OWNER, "DEFINITELY_NOT_AN_ACTION", "businesses", "biz_x")


def test_a_raw_address_cannot_reach_the_audit_log(conn):
    with pytest.raises(audit_mod.AuditError):
        with db.transaction(conn):
            audit_mod.audit(conn, OWNER, "MESSAGE_SENT", "outreach_messages", "msg_x",
                            detail={"to": "owner@example.invalid"})


# ---------------------------------------------------------------------------
# Policy and configuration
# ---------------------------------------------------------------------------

def test_automation_mode_cannot_leave_human_approval(conn):
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute("UPDATE contact_policy SET automation_mode='FULLY_AUTOMATED' "
                     "WHERE id='GLOBAL'")
    assert "HUMAN_APPROVAL" in str(exc.value)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO contact_policy (id, scope, automation_mode) "
            "VALUES ('other','GLOBAL','SEMI_AUTOMATED')")


def test_the_default_policy_row_is_seeded(conn):
    row = conn.execute("SELECT * FROM contact_policy WHERE id='GLOBAL'").fetchone()
    assert row["automation_mode"] == "HUMAN_APPROVAL"
    assert row["min_days_between_outreach"] == 21
    assert row["max_attempts"] == 3
    assert row["max_followups"] == 2
    # The deliberate on-switch: a fresh database cannot mail anybody.
    assert row["email_sending_domain"] is None


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------

def test_foreign_keys_are_actually_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO campaigns (id, name, slug, created_by) VALUES (?,?,?,?)",
            (new_id("cmp"), "orphan", "orphan", "usr_does_not_exist"),
        )


def test_migration_is_idempotent_and_tamper_evident(conn, tmp_path):
    assert db.migrate(conn) == []
    conn.execute("UPDATE schema_version SET sha256 = ? WHERE version = 1", ("0" * 64,))
    with pytest.raises(db.MigrationError) as exc:
        db.migrate(conn)
    assert "forward-only" in str(exc.value)


def test_transaction_rolls_back_on_error(conn):
    campaign = None
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            campaign = make_campaign(conn)
            raise RuntimeError("something went wrong halfway")
    assert conn.execute("SELECT COUNT(*) c FROM campaigns").fetchone()["c"] == 0


def test_ids_are_prefixed_ordered_and_validated(conn):
    from radar import ids
    first = ids.new_id("biz")
    second = ids.new_id("biz")
    assert first < second                      # ULID ordering
    assert ids.is_id(first, "biz")
    assert not ids.is_id(first, "cmp")
    assert ids.prefix_of(first) == "biz"
    with pytest.raises(ValueError):
        ids.new_id("nope")
    with pytest.raises(ValueError):
        ids.require_id(first, "cmp")


def test_score_bands_match_the_check_constraint(conn):
    assert band_for_score(80) == "HIGH"
    assert band_for_score(79) == "MEDIUM"
    assert band_for_score(60) == "MEDIUM"
    assert band_for_score(59) == "LOW"
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO opportunities (id, business_id, potential_problem, "
            "potential_solution, expected_benefit, score, band) VALUES (?,?,?,?,?,62,'HIGH')",
            (new_id("opp"), business, "p", "s", "b"),
        )


def test_models_round_trip_from_partial_rows(conn):
    from radar.models import Business, Campaign
    with db.transaction(conn):
        campaign = make_campaign(conn)
        business = make_business(conn, campaign)

    full = Business.from_row(
        conn.execute("SELECT * FROM businesses WHERE id=?", (business,)).fetchone())
    assert full.name == "Sample Hospital"
    assert full.status == BusinessStatus.AI_RESEARCHED
    assert full.may_receive_outreach is False

    partial = Business.from_row(
        conn.execute("SELECT id, name FROM businesses WHERE id=?", (business,)).fetchone())
    assert partial.name == "Sample Hospital"
    assert partial.city == ""          # dataclass default, not a crash

    camp = Campaign.from_row(
        conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign,)).fetchone())
    assert camp.industries == []
    assert camp.is_live is False
