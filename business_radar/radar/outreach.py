"""The only door out of this system, and the human standing in it.

Invariant 1 says there is no send path that does not pass through a human approval record - not
a config flag, a row. This module is where that stops being a sentence in a design document and
becomes a function signature: send() takes an approval_id and refuses a null one before it
touches the database, the database refuses a SENT status whose approval does not match the body
hash and the recipient address, and the two refusals are independent.

The ordering here is the other half of the point. The eligibility gates run again inside the
write transaction, immediately before the message is committed to being sent, because Sagar can
read a preview for four minutes and an unsubscribe can arrive in the third. A check made outside
the transaction is a check somebody can race. The transport call is then made outside the
transaction, because holding SQLite's writer lock open across the internet blocks every other
worker on the machine for as long as Gmail feels like taking.

Sending exactly once is not achievable over SMTP submission and this module does not pretend
otherwise. What it does instead: the status moves APPROVED -> QUEUED under the write lock, so a
double click finds QUEUED and returns rather than sending twice; a dropped connection after DATA
records INDETERMINATE and asks a human, because the wrong guess is either a lost message or the
same cold email twice.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from radar.audit import audit, mask_address
from radar.channels import (Transport, get_transport, unsub_address, unsubscribe_mailto)
from radar.channels.gmail import reply_to_address, rfc_message_id
from radar.channels.identity import load_identity
from radar.channels.mime import rfc5322_date
from radar.channels.types import OutboundEmail, OutboundWhatsApp, TransportResult
from radar.channels.whatsapp import wa_link
from radar.config import Config, load_config
from radar.db import transaction
from radar.ids import new_id_for, worker_id
from radar.models import utc_now
from radar.eligibility import Eligibility, check_send_eligibility
from radar.policy import body_hash

log = logging.getLogger("radar.outreach")


class SendRefused(RuntimeError):
    """The send path refused before any transport was contacted."""


class ApprovalRefused(RuntimeError):
    """A draft could not be approved. The reason is in the message."""


@dataclass(slots=True)
class SendOutcome:
    message_id: str
    status: str                      # SENT | FAILED | CANCELLED | INDETERMINATE | ALREADY_SENT
    provider: str | None = None
    provider_message_id: str | None = None
    detail: str | None = None
    eligibility: Eligibility | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def sent(self) -> bool:
        return self.status in {"SENT", "ALREADY_SENT"}


# ===========================================================================
# approve
# ===========================================================================

def approve(
    conn: sqlite3.Connection,
    draft_id: str,
    user_id: str,
    *,
    session_id: str,
    session_auth_method: str = "PASSWORD",
    confirmation_text: str = "I have read this message and I am sending it.",
    client_ip: str | None = None,
    user_agent: str | None = None,
    config: Config | None = None,
) -> str:
    """Write the approval row a send cannot happen without. Returns its apr_ id.

    Three refusals, in order, all before the row is written:
      * the policy verdict is BLOCK - a claim the research does not support is not approvable;
      * the checked body hash does not match the body as it stands now - which is what an edit
        after a PASS looks like, and it must go back through the checker;
      * an eligibility gate blocks - there is no point approving a message to somebody who
        opted out.

    The approval stores what was on screen, not a reference to it: the subject, the body, the
    address and the hash. Approving one body does not authorise sending a different one.
    """
    cfg = config or load_config(strict=False)

    with transaction(conn):
        row = conn.execute(
            """
            SELECT d.*, m.id AS message_id, m.status AS message_status,
                   m.to_address_norm, m.to_address_display, m.subject_final, m.body_final,
                   m.body_hash, m.approval_id, m.campaign_id AS message_campaign_id
              FROM outreach_drafts d
              JOIN outreach_messages m ON m.draft_id = d.id
             WHERE d.id = ?
            """,
            (draft_id,),
        ).fetchone()
        if row is None:
            raise ApprovalRefused(f"no draft {draft_id!r}, or it has no message row")

        if row["message_status"] in {"SENT", "DELIVERED", "BOUNCED", "FAILED", "CANCELLED"}:
            # Approving something already transmitted is not idempotence, it is a second
            # authorisation for a message that has left the building.
            raise ApprovalRefused(f"this message is already {row['message_status']}")

        # Idempotent: a double click on CONFIRM finds the approval it already made. Checked
        # after the terminal states above and before nothing else, because an approval that
        # already exists means these checks already passed once.
        if row["approval_id"] and row["message_status"] == "APPROVED":
            existing = conn.execute(
                "SELECT id FROM outreach_approvals WHERE id = ? AND revoked_at IS NULL",
                (row["approval_id"],)).fetchone()
            if existing is not None:
                return existing["id"]

        if row["policy_result"] == "BLOCK":
            raise ApprovalRefused(
                "the claim policy blocked this message; edit it or regenerate it")
        if row["policy_result"] is None:
            raise ApprovalRefused("this draft has not been policy-checked yet")

        final_body = row["body_edited"] or row["body"]
        current = body_hash(row["subject"], final_body)
        if row["policy_checked_body_hash"] != current:
            raise ApprovalRefused(
                "this draft changed after its policy check; re-check it before approving")
        if row["body_hash"] != current:
            raise ApprovalRefused(
                "the message body and the draft body disagree; re-check the draft")
        if row["message_status"] != "PENDING_APPROVAL":
            raise ApprovalRefused(
                f"this message is {row['message_status']}, not awaiting approval")
        if session_auth_method not in {"PASSWORD", "PASSWORD_TOTP"}:
            # The machine authenticator cannot mint a session, and therefore cannot supply a
            # legal value here. That is the type-level barrier behind invariant 1.
            raise ApprovalRefused("an approval requires a human browser session")

        eligibility = check_send_eligibility(
            conn, row["business_id"], row["contact_id"], row["channel"],
            stage="PREVIEW", campaign_id=row["message_campaign_id"],
            message_id=row["message_id"],
        )
        if not eligibility.allowed:
            raise ApprovalRefused(
                eligibility.blocking_sentence or "an eligibility gate blocks this send")

        approval_id = new_id_for("outreach_approvals")
        conn.execute(
            """
            INSERT INTO outreach_approvals
                (id, message_id, draft_id, business_id, contact_id, channel, approved_by,
                 session_id, session_auth_method, client_ip, user_agent, approved_subject,
                 approved_body, approved_body_hash, approved_to_address, confirmation_text,
                 displayed, eligibility_snapshot, preview_token, idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (approval_id, row["message_id"], draft_id, row["business_id"], row["contact_id"],
             row["channel"], user_id, session_id, session_auth_method, client_ip, user_agent,
             row["subject_final"], final_body, current, row["to_address_norm"] or "",
             confirmation_text,
             json.dumps({"to": row["to_address_display"], "subject": row["subject_final"],
                         "policy_result": row["policy_result"]}, ensure_ascii=False),
             eligibility.to_json(), new_id_for("outreach_approvals"),
             f"{row['message_id']}:{current[:16]}"),
        )
        conn.execute(
            "UPDATE outreach_messages SET approval_id = ?, status = 'APPROVED', sent_by = ? "
            "WHERE id = ?",
            (approval_id, user_id, row["message_id"]),
        )
        conn.execute(
            "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, detail) "
            "VALUES (?, ?, 'APPROVED', 'HUMAN', ?, ?)",
            (new_id_for("outreach_events"), row["message_id"], user_id,
             json.dumps({"approval_id": approval_id})),
        )
        audit(conn, user_id, "MESSAGE_APPROVED", "outreach_approvals", approval_id,
              after={"message_id": row["message_id"], "channel": row["channel"]},
              detail={"address_masked": mask_address(row["to_address_norm"]),
                      "policy_result": row["policy_result"]},
              business_id=row["business_id"], campaign_id=row["message_campaign_id"],
              message_id=row["message_id"], session_id=session_id, client_ip=client_ip,
              user_agent=user_agent)

    log.info("approval %s written for message %s by %s", approval_id, row["message_id"], user_id)
    return approval_id


def revoke_approval(conn: sqlite3.Connection, approval_id: str, user_id: str,
                    reason: str = "withdrawn") -> None:
    """Take the approval back. The message goes to CANCELLED; it cannot go back to draft."""
    with transaction(conn):
        row = conn.execute("SELECT * FROM outreach_approvals WHERE id = ?",
                           (approval_id,)).fetchone()
        if row is None:
            raise ValueError(f"no approval {approval_id!r}")
        conn.execute(
            "UPDATE outreach_approvals SET revoked_at = ?, revoked_by = ?, revoke_reason = ? "
            "WHERE id = ?", (utc_now(), user_id, reason, approval_id))
        conn.execute(
            "UPDATE outreach_messages SET status = 'CANCELLED', cancelled_at = ? "
            "WHERE id = ? AND status IN ('APPROVED','QUEUED')", (utc_now(), row["message_id"]))
        conn.execute(
            "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, detail) "
            "VALUES (?, ?, 'APPROVAL_REVOKED', 'HUMAN', ?, ?)",
            (new_id_for("outreach_events"), row["message_id"], user_id,
             json.dumps({"reason": reason})))
        audit(conn, user_id, "APPROVAL_REVOKED", "outreach_approvals", approval_id,
              detail={"reason": reason}, business_id=row["business_id"],
              message_id=row["message_id"])


# ===========================================================================
# send
# ===========================================================================

def send(
    conn: sqlite3.Connection,
    message_id: str,
    approval_id: str | None,
    *,
    config: Config | None = None,
    transport: Transport | None = None,
    actor: str | None = None,
) -> SendOutcome:
    """Transmit one approved message, or say precisely why it was not transmitted.

    Refuses a null approval_id at the top, before any query: invariant 1 is a type-level rule
    and the type-level check belongs where a caller cannot skip it.
    """
    if not approval_id:
        raise SendRefused("send() requires an approval_id; there is no send path without a human")

    cfg = config or load_config(strict=False)
    who = actor or worker_id()

    # --- phase 1: claim the message under the write lock ------------------
    with transaction(conn):
        message = conn.execute(
            "SELECT * FROM outreach_messages WHERE id = ?", (message_id,)).fetchone()
        if message is None:
            raise SendRefused(f"no outreach_messages row {message_id!r}")

        if message["status"] in {"SENT", "DELIVERED", "BOUNCED"}:
            # A double click, or a retry after a successful send. Do it once.
            log.info("message %s is already %s; not sending again", message_id,
                     message["status"])
            return SendOutcome(message_id, "ALREADY_SENT", message["provider"],
                               message["provider_message_id"], "already transmitted")
        if message["status"] == "QUEUED":
            return SendOutcome(message_id, "CANCELLED", detail="already in flight")
        if message["status"] != "APPROVED":
            raise SendRefused(f"message {message_id} is {message['status']}, not APPROVED")
        if message["approval_id"] != approval_id:
            raise SendRefused("the approval id does not match this message's approval")

        approval = conn.execute(
            "SELECT * FROM outreach_approvals WHERE id = ? AND message_id = ? "
            "AND revoked_at IS NULL", (approval_id, message_id)).fetchone()
        if approval is None:
            raise SendRefused("no live approval for this message")
        if approval["approved_body_hash"] != message["body_hash"]:
            raise SendRefused("the approved body is not the body about to be sent")
        if approval["approved_to_address"] != (message["to_address_norm"] or ""):
            raise SendRefused("the approved recipient is not the recipient about to be used")

        eligibility = check_send_eligibility(
            conn, message["business_id"], message["contact_id"], message["channel"],
            stage="SEND", campaign_id=message["campaign_id"], message_id=message_id)
        if not eligibility.allowed:
            _block(conn, message, eligibility, who)
            return SendOutcome(message_id, "CANCELLED", detail=eligibility.blocking_sentence,
                               eligibility=eligibility)

        conn.execute(
            """
            UPDATE outreach_messages
               SET status = 'QUEUED', queued_at = ?, provider_send_started_at = ?,
                   attempt_count = attempt_count + 1, worker_id = ?,
                   eligibility_snapshot = ?
             WHERE id = ?
            """,
            (utc_now(), utc_now(), who, eligibility.to_json(), message_id),
        )
        conn.execute(
            "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id) "
            "VALUES (?, ?, 'QUEUED', 'SYSTEM', ?)",
            (new_id_for("outreach_events"), message_id, who))
        audit(conn, who, "MESSAGE_QUEUED", "outreach_messages", message_id,
              after={"status": "QUEUED"}, business_id=message["business_id"],
              campaign_id=message["campaign_id"], message_id=message_id)

        contact = conn.execute(
            "SELECT * FROM business_contacts WHERE id = ?", (message["contact_id"],)
        ).fetchone() if message["contact_id"] else None
        draft = conn.execute(
            "SELECT unsubscribe_token FROM outreach_drafts WHERE id = ?",
            (message["draft_id"],)).fetchone()

    # --- phase 2: the transport, outside the transaction ------------------
    channel = message["channel"]
    picked = transport or get_transport(cfg, channel)
    identity = load_identity(cfg)
    token = draft["unsubscribe_token"] if draft is not None else ""

    try:
        if channel == "EMAIL":
            outbound = _build_email(message, identity, token)
            result = picked.send(outbound, idempotency_key=message["idempotency_key"])
        else:
            number = (contact["phone_e164"] if contact is not None else "") or ""
            outbound_wa = OutboundWhatsApp(
                message_id=message_id, to_e164=number, text=message["body_final"] or "",
                link=wa_link(number, message["body_final"] or "") if number else "")
            result = picked.send(outbound_wa, idempotency_key=message["idempotency_key"])
    except Exception as exc:                              # noqa: BLE001 - a transport bug
        log.exception("transport raised for %s", message_id)
        result = TransportResult(outcome="FAILED", provider=getattr(picked, "name", "unknown"),
                                 provider_message_id=None, failure_code="TRANSPORT_EXCEPTION",
                                 failure_detail=str(exc)[:500])

    # --- phase 3: record what happened ------------------------------------
    return _record(conn, message, result, who=who, channel=channel)


def _build_email(message: sqlite3.Row, identity, token: str | None) -> OutboundEmail:
    address = identity.from_address
    unsub = unsub_address(address, token) if token else ""
    return OutboundEmail(
        message_id=message["id"],
        rfc_message_id=rfc_message_id(message["id"], address),
        from_addr=address,
        from_name=identity.sender_name,
        to_addr=message["to_address_norm"] or "",
        reply_to=reply_to_address(address, message["id"]),
        subject=message["subject_final"] or "",
        text=message["body_final"] or "",
        unsubscribe_mailto=unsubscribe_mailto(address, token,
                                              identity.unsubscribe_subject) if token else "",
        unsubscribe_addr=unsub,
        date=rfc5322_date(),
    )


def _block(conn: sqlite3.Connection, message: sqlite3.Row, eligibility: Eligibility,
           who: str) -> None:
    conn.execute(
        "UPDATE outreach_messages SET status = 'CANCELLED', cancelled_at = ? WHERE id = ?",
        (utc_now(), message["id"]))
    conn.execute(
        "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, detail) "
        "VALUES (?, ?, 'ELIGIBILITY_BLOCK', 'SYSTEM', ?, ?)",
        (new_id_for("outreach_events"), message["id"], who,
         json.dumps({"blocking_code": eligibility.blocking_code,
                     "sentence": eligibility.blocking_sentence})))
    audit(conn, who, "MESSAGE_CANCELLED", "outreach_messages", message["id"],
          after={"status": "CANCELLED"},
          detail={"blocking_code": eligibility.blocking_code},
          business_id=message["business_id"], campaign_id=message["campaign_id"],
          message_id=message["id"])
    log.warning("send blocked for %s: %s", message["id"], eligibility.blocking_sentence)


def _record(conn: sqlite3.Connection, message: sqlite3.Row, result: TransportResult, *,
            who: str, channel: str) -> SendOutcome:
    message_id = message["id"]
    now = utc_now()

    with transaction(conn):
        current = conn.execute(
            "SELECT status FROM outreach_messages WHERE id = ?", (message_id,)).fetchone()
        if current is not None and current["status"] in {"SENT", "DELIVERED", "BOUNCED"}:
            return SendOutcome(message_id, "ALREADY_SENT", result.provider,
                               result.provider_message_id)

        if result.outcome == "ACCEPTED":
            conn.execute(
                """
                UPDATE outreach_messages
                   SET status = 'SENT', sent_at = ?, provider = ?, provider_message_id = ?,
                       provider_status_code = ?, provider_response = ?
                 WHERE id = ?
                """,
                (now, result.provider, result.provider_message_id, result.status_code,
                 result.truncated_raw(), message_id),
            )
            conn.execute(
                "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, "
                "detail) VALUES (?, ?, 'SENT', 'SYSTEM', ?, ?)",
                (new_id_for("outreach_events"), message_id, who,
                 json.dumps({"provider": result.provider})))
            if channel != "EMAIL":
                # The human was the transport. Say so, in the history.
                conn.execute(
                    "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, "
                    "detail) VALUES (?, ?, 'MANUAL_RECORDED', 'HUMAN', ?, ?)",
                    (new_id_for("outreach_events"), message_id, who,
                     json.dumps({"link": result.raw.get("link")})))
            _mark_contacted(conn, message, now, who)
            audit(conn, who, "MESSAGE_SENT", "outreach_messages", message_id,
                  after={"status": "SENT", "provider": result.provider},
                  detail={"address_masked": mask_address(message["to_address_norm"]),
                          "provider": result.provider,
                          "live": result.provider not in {"null", "wa_me"}},
                  business_id=message["business_id"], campaign_id=message["campaign_id"],
                  message_id=message_id)
            log.info("message %s sent via %s", message_id, result.provider)
            return SendOutcome(message_id, "SENT", result.provider,
                               result.provider_message_id, extra=dict(result.raw))

        if result.outcome == "INDETERMINATE":
            # Neither SENT nor FAILED is honest. Leave it QUEUED, record the event, and let a
            # human check the Sent folder: a resend here may be the second copy.
            conn.execute(
                "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, "
                "detail) VALUES (?, ?, 'INDETERMINATE', 'SYSTEM', ?, ?)",
                (new_id_for("outreach_events"), message_id, who,
                 json.dumps({"failure_code": result.failure_code,
                             "detail": result.failure_detail})))
            log.error("message %s is INDETERMINATE (%s): check the Sent folder before retrying",
                      message_id, result.failure_code)
            return SendOutcome(message_id, "INDETERMINATE", result.provider, None,
                               result.failure_detail)

        conn.execute(
            """
            UPDATE outreach_messages
               SET status = 'FAILED', failed_at = ?, failure_code = ?, failure_detail = ?,
                   provider = ?, provider_status_code = ?, provider_response = ?
             WHERE id = ?
            """,
            (now, result.failure_code or "UNKNOWN", result.failure_detail, result.provider,
             result.status_code, result.truncated_raw(), message_id),
        )
        conn.execute(
            "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, detail) "
            "VALUES (?, ?, 'PROVIDER_ERROR', 'PROVIDER', ?, ?)",
            (new_id_for("outreach_events"), message_id, result.provider,
             json.dumps({"failure_code": result.failure_code,
                         "retryable": result.retryable})))
        audit(conn, who, "MESSAGE_FAILED", "outreach_messages", message_id,
              after={"status": "FAILED"},
              detail={"failure_code": result.failure_code, "provider": result.provider},
              business_id=message["business_id"], campaign_id=message["campaign_id"],
              message_id=message_id)
        log.error("message %s failed: %s %s", message_id, result.failure_code,
                  result.failure_detail)
        return SendOutcome(message_id, "FAILED", result.provider, None, result.failure_detail)


def _mark_contacted(conn: sqlite3.Connection, message: sqlite3.Row, now: str,
                    who: str) -> None:
    """CONTACT_READY -> CONTACTED, the counters, and the frequency clock.

    businesses.last_contacted_at is what gate G1 reads, so it has to move in the same
    transaction as the send. A counter updated by a later job is a counter that is wrong for as
    long as the job takes.
    """
    business = conn.execute(
        "SELECT id, status, first_contacted_at FROM businesses WHERE id = ?",
        (message["business_id"],)).fetchone()
    if business is None:
        return
    conn.execute(
        "UPDATE businesses SET last_contacted_at = ?, first_contacted_at = COALESCE(?, ?) "
        "WHERE id = ?",
        (now, business["first_contacted_at"], now, business["id"]))
    if business["status"] == "CONTACT_READY":
        conn.execute(
            "UPDATE businesses SET status = 'CONTACTED', status_actor_kind = 'SYSTEM' "
            "WHERE id = ?", (business["id"],))
        audit(conn, who, "BUSINESS_STATUS_CHANGED", "businesses", business["id"],
              before={"status": "CONTACT_READY"}, after={"status": "CONTACTED"},
              business_id=business["id"], message_id=message["id"])
    conn.execute(
        "UPDATE campaigns SET n_contacted = n_contacted + 1 WHERE id = ?",
        (message["campaign_id"],))


# ===========================================================================
# The manual channels
# ===========================================================================

def whatsapp_link(conn: sqlite3.Connection, message_id: str) -> str:
    """The wa.me link for an approved WhatsApp message, for Sagar to click.

    Nothing is recorded by building the link: opening WhatsApp is not sending, and a message
    marked sent because a link was generated is a lie in the outreach history.
    """
    row = conn.execute(
        """
        SELECT m.body_final, c.phone_e164
          FROM outreach_messages m
          LEFT JOIN business_contacts c ON c.id = m.contact_id
         WHERE m.id = ?
        """, (message_id,)).fetchone()
    if row is None:
        raise ValueError(f"no outreach_messages row {message_id!r}")
    if not row["phone_e164"]:
        raise ValueError("that message has no phone number to open a chat with")
    return wa_link(row["phone_e164"], row["body_final"] or "")


def record_manual_send(conn: sqlite3.Connection, message_id: str, approval_id: str, *,
                       user_id: str, config: Config | None = None) -> SendOutcome:
    """Sagar says he sent it from his own phone; record it as sent, by him.

    This is the WhatsApp and MANUAL path in full. It runs through send() rather than beside it,
    so the eligibility gates, the approval match, the status transitions, the audit row and the
    business status change are the same code that the email path uses. The only difference is
    which transport is asked, and that one records rather than transmits.
    """
    return send(conn, message_id, approval_id, config=config, actor=user_id)
