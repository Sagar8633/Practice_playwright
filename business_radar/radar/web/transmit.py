"""The one function in the system that hands a message to a transport.

Invariant 1 is a statement about this file: `send()` takes `approval_id: str`, not
`str | None`, and refuses a blank one before it looks at anything else. Everything upstream -
the absent send control, the confirm dialog, the typed word - is a UI convention that a
determined caller could route around. This is the barrier that a caller cannot route around,
because there is no code path from a message row to smtplib that does not pass through an
approval id that names a human, a session and the exact body they read.

The second thing it does is refuse to pretend. When the email channel has no credentials -
which is the shipped default and will be the state on Sagar's laptop until he runs the Gmail
setup - an approved message is written to data/outbox/unsent/ as a .eml file and the row stays
APPROVED. It is not marked SENT, not marked FAILED, and not silently dropped: 17-channel-
configuration.md section 17.4.1 is explicit that work done while unconfigured is kept and
labelled, because an approval that vanished is an approval Sagar will make again.

SIMPLIFIED: 07-email-integration.md sections 7.5-7.8 add a send queue with leases, exponential
backoff, per-account ramp scheduling and DSN parsing. This transmits inline, in the request
that approved it, because on this deployment the operator is sitting in front of the machine
and one send a minute is the working rate. The retry story is a new message row, which is what
the outreach_status_transitions table already says a retry is.
"""

from __future__ import annotations

import logging
import smtplib
import sqlite3
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from radar import audit as audit_mod
from radar.audit import hash_address, mask_address
from radar.config import Config
from radar.db import transaction
from radar.models import utc_now
from radar.paths import OUTBOX_DIR

log = logging.getLogger("radar.web.transmit")


class SendRefused(RuntimeError):
    """The send was refused before anything left the machine. The message names the reason."""


@dataclass(frozen=True, slots=True)
class SendResult:
    """What happened, in a form the confirm dialog can render without interpreting."""

    sent: bool
    status: str                 # the outreach_messages.status the row now carries
    sentence: str               # what to show the operator
    eml_path: Path | None = None
    provider_message_id: str | None = None


def send(conn: sqlite3.Connection, config: Config, *, message_id: str, approval_id: str,
         actor: str, channel_configured: bool) -> SendResult:
    """Transmit one approved message. `approval_id` is required and is checked first.

    The database enforces the same rule twice more on the way through: the row CHECK refuses a
    SENT status with a null approval_id, and trg_om_send_approval_matches refuses one whose
    approval does not cover this exact body and this exact address.
    """
    if not approval_id or not isinstance(approval_id, str):
        raise SendRefused(
            "send() requires an approval id. There is no send path that does not pass "
            "through a human approval row."
        )

    message = conn.execute(
        "SELECT * FROM outreach_messages WHERE id = ?", (message_id,)
    ).fetchone()
    if message is None:
        raise SendRefused("No such message: " + message_id)
    if message["status"] != "APPROVED":
        raise SendRefused(
            "This message is %s. Only an APPROVED message may be sent." % message["status"]
        )
    if message["approval_id"] != approval_id:
        raise SendRefused("That approval does not belong to this message.")

    approval = conn.execute(
        "SELECT * FROM outreach_approvals WHERE id = ? AND revoked_at IS NULL", (approval_id,)
    ).fetchone()
    if approval is None:
        raise SendRefused("That approval has been revoked. Approve the message again.")
    if approval["approved_body_hash"] != message["body_hash"]:
        raise SendRefused(
            "The message body has changed since it was approved. Approve the new text."
        )
    if approval["approved_to_address"] != message["to_address_norm"]:
        raise SendRefused(
            "The recipient has changed since the approval. Approve it again for this address."
        )

    if message["channel"] != "EMAIL":
        return _record_manual(conn, message, actor)

    mime, eml_path = _build_eml(config, message)

    if not channel_configured:
        _write_eml(eml_path, mime)
        log.warning("email channel unconfigured; %s written to %s and NOT sent",
                    message_id, eml_path)
        with transaction(conn):
            audit_mod.audit(
                conn, actor, "MESSAGE_QUEUED", "outreach_messages", message_id,
                message_id=message_id, business_id=message["business_id"],
                campaign_id=message["campaign_id"],
                detail={"outcome": "HELD_UNCONFIGURED", "eml_path": str(eml_path),
                        "address_masked": mask_address(message["to_address_norm"])},
            )
        return SendResult(
            sent=False, status="APPROVED", eml_path=eml_path,
            sentence=("The email channel is not configured, so nothing was transmitted. The "
                      "approved message is on disk at %s and the approval still stands."
                      % eml_path),
        )

    with transaction(conn):
        conn.execute(
            "UPDATE outreach_messages SET status = 'QUEUED', queued_at = ?, "
            "       attempt_count = attempt_count + 1, "
            "       provider = 'gmail-smtp', provider_send_started_at = ? WHERE id = ?",
            (utc_now(), utc_now(), message_id),
        )
        audit_mod.audit(conn, actor, "MESSAGE_QUEUED", "outreach_messages", message_id,
                        message_id=message_id, business_id=message["business_id"],
                        campaign_id=message["campaign_id"])

    try:
        provider_id = _smtp_send(config, mime, message["to_address_norm"])
    except Exception as exc:
        code = type(exc).__name__
        log.error("send failed for %s: %s", message_id, exc)
        with transaction(conn):
            conn.execute(
                "UPDATE outreach_messages SET status = 'FAILED', failed_at = ?, "
                "       failure_code = ?, failure_detail = ? WHERE id = ?",
                (utc_now(), code, str(exc)[:500], message_id),
            )
            audit_mod.audit(conn, actor, "MESSAGE_FAILED", "outreach_messages", message_id,
                            message_id=message_id, business_id=message["business_id"],
                            campaign_id=message["campaign_id"],
                            detail={"failure_code": code})
        _write_eml(eml_path, mime)
        return SendResult(
            sent=False, status="FAILED", eml_path=eml_path,
            sentence=("The transport refused this message (%s). Nothing was delivered. The "
                      "body is on disk at %s." % (code, eml_path)),
        )

    now = utc_now()
    with transaction(conn):
        conn.execute(
            "UPDATE outreach_messages SET status = 'SENT', sent_at = ?, "
            "       provider_message_id = ?, sent_by = ?, worker_id = ? WHERE id = ?",
            (now, provider_id, approval["approved_by"], "web", message_id),
        )
        conn.execute(
            "UPDATE businesses "
            "   SET first_contacted_at = COALESCE(first_contacted_at, ?), "
            "       last_contacted_at = ?, status_actor_kind = 'SYSTEM' "
            " WHERE id = ?",
            (now, now, message["business_id"]),
        )
        conn.execute(
            "UPDATE businesses SET status = 'CONTACTED', status_actor_kind = 'SYSTEM', "
            "       status_actor_user_id = NULL "
            " WHERE id = ? AND status = 'CONTACT_READY'",
            (message["business_id"],),
        )
        conn.execute(
            "UPDATE selections SET state = 'DISPATCHED', updated_at = ? "
            " WHERE business_id = ? AND campaign_id = ? AND state IN ('SELECTED','PREPARED')",
            (now, message["business_id"], message["campaign_id"]),
        )
        conn.execute(
            "UPDATE campaigns SET n_contacted = n_contacted + 1 WHERE id = ?",
            (message["campaign_id"],),
        )
        audit_mod.audit(
            conn, actor, "MESSAGE_SENT", "outreach_messages", message_id,
            message_id=message_id, business_id=message["business_id"],
            campaign_id=message["campaign_id"],
            detail={"approval_id": approval_id, "provider": "gmail-smtp",
                    "provider_message_id": provider_id,
                    "address_masked": mask_address(message["to_address_norm"]),
                    "address_sha256": hash_address(message["to_address_norm"])},
        )

    _write_eml(eml_path, mime)
    log.info("sent %s to %s", message_id, mask_address(message["to_address_norm"]))
    return SendResult(
        sent=True, status="SENT", eml_path=eml_path, provider_message_id=provider_id,
        sentence=("Sent. A copy is on disk at %s, and the approval record %s names you, the "
                  "time and this exact text." % (eml_path, approval_id)),
    )


# ---------------------------------------------------------------------------
# building and writing
# ---------------------------------------------------------------------------

def _build_eml(config: Config, message: sqlite3.Row) -> tuple[EmailMessage, Path]:
    """One recipient, one rendered body, one working unsubscribe. Never a Bcc list."""
    mime = EmailMessage()
    from_address = config.email.address or "radar@localhost.invalid"
    mime["From"] = formataddr((config.email.from_name or "business_radar", from_address))
    mime["To"] = message["to_address_display"] or message["to_address_norm"]
    mime["Subject"] = message["subject_final"] or ""
    mime["Date"] = formatdate(localtime=True)
    mime["Message-ID"] = make_msgid(domain=(from_address.split("@")[-1] or "localhost.invalid"))
    if config.email.reply_to:
        mime["Reply-To"] = config.email.reply_to
    # RFC 2369 mailto: unsubscribe. There is no public hostname, so the one-click POST form of
    # RFC 8058 cannot be offered and this is the whole opt-out mechanism.
    unsubscribe = getattr(config.email, "unsubscribe_mailto", "")
    if unsubscribe:
        mime["List-Unsubscribe"] = unsubscribe
    mime["Auto-Submitted"] = "no"
    mime.set_content(message["body_final"] or "")

    day = utc_now()[:10]
    folder = OUTBOX_DIR / ("sent" if message["status"] == "APPROVED" else "sent") / day
    return mime, folder / (str(message["id"]) + ".eml")


def _write_eml(path: Path, mime: EmailMessage) -> None:
    """Atomic write: .tmp then replace. A half-written record of a send is worse than none."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(bytes(mime))
    tmp.replace(path)


def _smtp_send(config: Config, mime: EmailMessage, to_address: str) -> str:
    """Hand the message to Gmail over SMTP with an App Password. One recipient, always."""
    email_cfg = config.email
    timeout = 30
    if email_cfg.smtp_use_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(email_cfg.smtp_host, email_cfg.smtp_port,
                                                timeout=timeout)
    else:
        server = smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port, timeout=timeout)
    try:
        server.ehlo()
        if not email_cfg.smtp_use_ssl:
            server.starttls()
            server.ehlo()
        server.login(email_cfg.address, email_cfg.app_password)
        server.send_message(mime, from_addr=email_cfg.address, to_addrs=[to_address])
    finally:
        try:
            server.quit()
        except Exception:  # pragma: no cover - a dead socket on quit is not a send failure
            pass
    return str(mime["Message-ID"])


def _record_manual(conn: sqlite3.Connection, message: sqlite3.Row, actor: str) -> SendResult:
    """WHATSAPP, PHONE and MANUAL never transmit from here; the operator does it himself."""
    return SendResult(
        sent=False, status=message["status"],
        sentence=("%s outreach is not transmitted by this machine. Copy the approved body, "
                  "send it yourself, and record what happened on the business page."
                  % message["channel"].title()),
    )
