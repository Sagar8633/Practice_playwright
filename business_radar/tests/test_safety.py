"""The tests that prove the safety model is structural rather than aspirational.

Every other test in this suite checks that a feature works. These check that a feature *cannot*
work - that the database itself refuses the things the design says must never happen, even when
the application layer is wrong, absent, or deliberately bypassed.

They are written against raw SQL on purpose. Going through radar/outreach.py would test that the
Python guard works; going straight at the table tests that the guard is not the only thing
standing between a bug and a stranger's inbox.

If any test in this file fails, stop and fix it before writing another line of anything else.
"""
from __future__ import annotations

import sqlite3

import pytest

from radar.db import connect, migrate
from radar.ids import new_id
from radar.models import utc_now


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "safety.db")
    migrate(c)
    yield c
    c.close()


def _raises(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> str:
    """Run a statement that must be refused, and return the refusal message."""
    with pytest.raises(sqlite3.Error) as exc:
        conn.execute(sql, params)
    return str(exc.value)


# --------------------------------------------------------------------- invariant 1 & 2: sending

def test_send_requires_an_approval(conn):
    """No message reaches SENT without an approval row. This is the whole system in one test."""
    mid = _seed_message(conn)
    msg = _raises(
        conn,
        "UPDATE outreach_messages SET status='SENT', sent_at=? WHERE id=?",
        (utc_now(), mid),
    )
    assert "approval" in msg.lower(), msg


def test_sent_only_from_approved(conn):
    """SENT is reachable only from APPROVED or QUEUED - never straight from DRAFT."""
    mid = _seed_message(conn)
    apr = _seed_approval(conn, mid)
    # Still DRAFT: even with an approval attached, the transition itself is illegal.
    msg = _raises(
        conn,
        "UPDATE outreach_messages SET status='SENT', approval_id=?, sent_at=? WHERE id=?",
        (apr, utc_now(), mid),
    )
    assert msg, "a DRAFT -> SENT transition must be refused"


def test_insert_cannot_start_at_sent(conn):
    """A row cannot be born SENT, which would sidestep every transition check."""
    biz, camp, contact, _ = _fixtures(conn)
    _promote_to_contact_ready(conn, biz)
    draft = _seed_draft(conn, biz, camp)
    mid = new_id("msg")
    msg = _raises(
        conn,
        "INSERT INTO outreach_messages (id, draft_id, business_id, campaign_id, contact_id,"
        " channel, status, thread_key, idempotency_key, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (mid, draft, biz, camp, contact, "EMAIL", "SENT", "t-"+mid[-6:], mid, utc_now()),
    )
    assert msg


# --------------------------------------------------------------------- invariant 3: opt-out

def test_a_suppression_cannot_be_deleted(conn):
    """An opt-out is permanent. Deleting one is how you email somebody who told you to stop."""
    sid = new_id("sup")
    conn.execute(
        "INSERT INTO suppressions (id, scope, value_norm, reason, source, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (sid, "EMAIL", "someone@example.invalid", "REPLY_OPT_OUT", "REPLY", utc_now()),
    )
    msg = _raises(conn, "DELETE FROM suppressions WHERE id=?", (sid,))
    assert msg


# --------------------------------------------------------------------- invariant: audit

def test_audit_log_is_append_only(conn):
    """An audit trail you can edit is not an audit trail."""
    from radar.audit import audit

    audit(conn, "sagar", "CAMPAIGN_CREATED", "campaigns", new_id("cmp"), None, {"n": 1})
    row = conn.execute("SELECT id FROM audit_log LIMIT 1").fetchone()
    assert row is not None, "audit() wrote nothing"
    assert _raises(conn, "UPDATE audit_log SET action='X' WHERE id=?", (row["id"],))
    assert _raises(conn, "DELETE FROM audit_log WHERE id=?", (row["id"],))


# --------------------------------------------------------------------- invariant: no automation

def test_automation_mode_cannot_be_raised(conn):
    """v1 supports HUMAN_APPROVAL only. The other modes exist in the enum and nowhere else."""
    assert _raises(
        conn, "UPDATE contact_policy SET automation_mode='FULLY_AUTOMATED' WHERE scope='GLOBAL'"
    )
    assert _raises(
        conn, "UPDATE contact_policy SET automation_mode='SEMI_AUTOMATED' WHERE scope='GLOBAL'"
    )


def test_default_policy_is_human_approval(conn):
    row = conn.execute(
        "SELECT automation_mode FROM contact_policy WHERE scope='GLOBAL'"
    ).fetchone()
    assert row is not None, "the global contact_policy row must be seeded"
    assert row["automation_mode"] == "HUMAN_APPROVAL"


# --------------------------------------------------------------------- invariant: status machine

def test_illegal_status_transition_is_refused(conn):
    """A business cannot jump the queue from researched straight to contacted."""
    biz, _, _, _ = _fixtures(conn)
    assert _raises(
        conn, "UPDATE businesses SET status='CONTACTED' WHERE id=?", (biz,)
    )


# --------------------------------------------------------------------- unconfigured is supported

def test_unconfigured_email_is_a_supported_state():
    """A fresh install with no Gmail credentials must load, not crash."""
    from radar.config import load_config

    cfg = load_config(strict=False)
    assert cfg.llm is not None
    # Whether or not email happens to be configured on this machine, asking must never raise.
    assert isinstance(cfg.email.configured, bool)
    assert "MANUAL" in cfg.channels_ready


# --------------------------------------------------------------------- fixtures

def _fixtures(conn) -> tuple[str, str, str, str]:
    """The minimum rows needed to hang an outreach message off, all in AI_RESEARCHED state."""
    camp, biz = new_id("cmp"), new_id("biz")
    contact, draft = new_id("cnt"), new_id("out")
    now = utc_now()
    conn.execute(
        "INSERT INTO campaigns (id, name, slug, created_by, created_at, status)"
        " VALUES (?,?,?,?,?,?)",
        (camp, "safety test", "safety-test-" + camp[-6:], "usr_00000000000000000000000000", now, "DRAFT"),
    )
    conn.execute(
        "INSERT INTO businesses (id, business_key, name, name_norm, city, city_slug,"
        " industry, category, status, first_seen_campaign_id, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (biz, "safety-test-key", "Safety Test Ltd", "safety test", "Dhule", "dhule",
         "HEALTHCARE", "HOSPITAL", "AI_RESEARCHED", camp, now, now),
    )
    conn.execute(
        "INSERT INTO campaign_businesses (campaign_id, business_id, first_seen_at, state,"
        " city_at_discovery, industry_at_discovery, category_at_discovery)"
        " VALUES (?,?,?,?,?,?,?)",
        (camp, biz, now, "INCLUDED", "Dhule", "HEALTHCARE", "HOSPITAL"),
    )
    conn.execute(
        "INSERT INTO business_contacts (id, business_id, kind, value_raw, value_norm,"
        " value_dedupe, value_display, domain, discovered_at, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (contact, biz, "EMAIL", "x@example.invalid", "x@example.invalid",
         "x@example.invalid", "x@example.invalid", "example.invalid", now, now),
    )
    return biz, camp, contact, draft


def _promote_to_contact_ready(conn, biz: str) -> None:
    """Walk a business up the ladder the way the application must: no shortcuts.

    Every step here is a transition the `business_status_transitions` table permits. That the
    fixture has to do this at all is the point - a draft cannot exist for a business that has not
    been verified by a human, and the database enforces that, not a code review.
    """
    from radar.models import VERIFICATION_CHECK_KEYS

    now = utc_now()
    conn.execute(
        "UPDATE businesses SET status='NEEDS_VERIFICATION', status_actor_kind='SYSTEM'"
        " WHERE id=?", (biz,),
    )

    ver = new_id("ver")
    conn.execute(
        "INSERT INTO verifications (id, business_id, state, verdict, checks_total,"
        " checks_passed, checks_failed, why_note, dwell_ms, dwell_required_ms,"
        " verified_by, verified_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ver, biz, "SUBMITTED", "VERIFIED", 9, 9, 0,
         "Fixture verification for the safety test suite.", 60_000, 0,
         "usr_00000000000000000000000000", now, now),
    )
    for i, key in enumerate(VERIFICATION_CHECK_KEYS, start=1):
        conn.execute(
            "INSERT INTO verification_checks (id, verification_id, business_id, check_key,"
            " ordinal, passed, answered_at, answered_by) VALUES (?,?,?,?,?,?,?,?)",
            (new_id("chk"), ver, biz, key, i, 1, now, "usr_00000000000000000000000000"),
        )
    # The transition must record WHICH verification and WHICH human authorised it - the trigger
    # will not accept a status change that cannot name its evidence.
    conn.execute(
        "UPDATE businesses SET status='VERIFIED', status_verification_id=?,"
        " status_actor_kind='HUMAN', status_actor_user_id=? WHERE id=?",
        (ver, "usr_00000000000000000000000000", biz),
    )
    conn.execute(
        "UPDATE businesses SET status='CONTACT_READY', status_actor_kind='SYSTEM',"
        " status_actor_user_id=NULL WHERE id=?",
        (biz,),
    )


def _seed_draft(conn, biz: str, camp: str) -> str:
    draft = new_id("out")
    conn.execute(
        "INSERT INTO outreach_drafts (id, business_id, campaign_id, channel, body,"
        " model_id, prompt_version, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (draft, biz, camp, "EMAIL", "hello", "gemini-2.5-flash", "test-v1", utc_now()),
    )
    return draft


def _seed_message(conn, status: str = "DRAFT") -> str:
    biz, camp, contact, _ = _fixtures(conn)
    _promote_to_contact_ready(conn, biz)
    draft = _seed_draft(conn, biz, camp)
    mid = new_id("msg")
    conn.execute(
        "INSERT INTO outreach_messages (id, draft_id, business_id, campaign_id, contact_id,"
        " channel, status, thread_key, idempotency_key, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (mid, draft, biz, camp, contact, "EMAIL", status, "thread-" + mid[-6:], mid, utc_now()),
    )
    return mid


def _seed_approval(conn, message_id: str) -> str:
    """An approval row the schema will actually accept.

    Note how much evidence it demands: which session, how that session authenticated, the exact
    body approved and its hash, the address, and the confirmation text typed. That is deliberate -
    an approval is meant to be hard to forge accidentally.
    """
    aid = new_id("apr")
    row = conn.execute(
        "SELECT business_id, draft_id, channel FROM outreach_messages WHERE id=?", (message_id,)
    ).fetchone()
    body = "hello"
    conn.execute(
        "INSERT INTO outreach_approvals (id, message_id, draft_id, business_id, channel,"
        " approved_by, session_id, session_auth_method, approved_body, approved_body_hash,"
        " approved_to_address, confirmation_text, preview_token, idempotency_key, approved_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (aid, message_id, row["draft_id"], row["business_id"], row["channel"],
         "usr_00000000000000000000000000", "sess-test", "PASSWORD", body,
         __import__("hashlib").sha256(body.encode()).hexdigest(),
         "x@example.invalid", "CONFIRM & SEND", "tok-" + aid[-6:], aid, utc_now()),
    )
    return aid
