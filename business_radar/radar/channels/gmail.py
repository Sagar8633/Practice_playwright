"""Authenticated SMTP submission to Gmail, with the four quiet failures closed.

The failures this module prevents are the ones that do not look like failures. smtplib will
connect without TLS if asked nicely; it will accept an unverified certificate if no context is
supplied; it reports partial success for a multi-recipient message rather than raising; and
Gmail answers a revoked App Password with a bare 535 that reads like a typo. All four are closed
here, once, so that no caller has to remember them and no future transport re-opens them.

The fifth failure has no fix, only an honest name. If the connection dies after DATA, SMTP
submission offers no lookup that can settle whether the message was delivered. That returns
INDETERMINATE rather than a guess, because the wrong guess in either direction is either a
silently lost message or the same cold email sent twice.

What this transport will not do: no tracking pixel, no click wrapping, no HTML alternative, no
attachments, no bcc, and no second recipient. One message, one person, plain text, with a
List-Unsubscribe that works and a "reply STOP" line in the body. That is the whole argument for
sending business mail from a free Gmail account at all, and the moment any of it is relaxed the
argument stops being true.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from typing import ClassVar

from radar.channels.mime import build_mime
from radar.channels.types import OutboundEmail, TransportResult

log = logging.getLogger("radar.channels.gmail")

# 421/450/452 are Gmail's rate and daily-limit answers: retryable tomorrow, not in ninety
# seconds. Everything in this set is permanent and must not be retried at all.
_PERMANENT = {501, 502, 503, 504, 521, 541, 550, 551, 552, 553, 554}


def rfc_message_id(message_id: str, from_address: str) -> str:
    """Our own Message-ID, derived from the row id so the thread key is recomputable.

    Gmail may replace a client-supplied Message-ID on submission. We generate and record it
    regardless: it is the only provider id SMTP submission gives us, and a recorded id that the
    provider later overrode is still better than no id at all.
    """
    domain = from_address.partition("@")[2] or "localhost.invalid"
    prefix, _, body = message_id.partition("_")
    return f"<{prefix.lower()}_{body.upper()}@{domain}>" if body else f"<{message_id}@{domain}>"


def reply_to_address(from_address: str, message_id: str) -> str:
    """A plus-addressed Reply-To, so an inbound reply names the message it answers.

    There are no webhooks on this deploy and no way to ask Gmail which message a reply belongs
    to. The plus tag is the attribution mechanism, and it survives every mail client that
    quotes the address it is replying to.
    """
    local, _, domain = (from_address or "").partition("@")
    if not domain:
        return from_address
    return f"{local}+{message_id.lower()}@{domain}"


class GmailTransport:
    name: ClassVar[str] = "gmail"
    is_live: ClassVar[bool] = True
    supports_delivery_receipts: ClassVar[bool] = False

    def __init__(self, *, host: str, port: int, user: str, app_password: str,
                 timeout_s: int = 30) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = app_password
        self._timeout = timeout_s

    def send(self, msg: OutboundEmail, *, idempotency_key: str) -> TransportResult:
        try:
            mime = build_mime(msg)
        except Exception as exc:                     # noqa: BLE001
            log.exception("could not build the MIME message for %s", msg.message_id)
            return self._fail("MIME_BUILD_FAILED", None, exc, retryable=False)

        context = ssl.create_default_context()       # verifies chain and hostname; never relax
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self._user, self._password)
                refused = server.send_message(
                    mime,
                    from_addr=msg.from_addr,
                    to_addrs=[msg.to_addr],          # exactly one recipient, always
                )
        except smtplib.SMTPAuthenticationError as exc:
            # A 535 here is almost always one of three things, in this order of likelihood: a
            # revoked App Password, 2-Step Verification switched off, or the account's own
            # password pasted in instead of the App Password.
            log.error("Gmail refused the App Password for %s (%s). Check that 2-Step "
                      "Verification is on and the App Password has not been revoked.",
                      self._user, exc.smtp_code)
            return self._fail("AUTH_FAILED", exc.smtp_code, exc, retryable=False)
        except smtplib.SMTPRecipientsRefused as exc:
            code = next(iter(exc.recipients.values()))[0] if exc.recipients else None
            return self._fail("INVALID_RECIPIENT", code, exc, retryable=False)
        except smtplib.SMTPResponseException as exc:
            return self._fail("SMTP_ERROR", exc.smtp_code, exc,
                              retryable=exc.smtp_code not in _PERMANENT,
                              retry_after_s=3600 if exc.smtp_code in {421, 450, 452} else None)
        except (smtplib.SMTPServerDisconnected, TimeoutError) as exc:
            # The connection died. We do not know whether DATA completed. Never guess.
            log.error("connection to %s lost while sending %s; outcome unknown",
                      self._host, msg.message_id)
            return TransportResult(
                outcome="INDETERMINATE", provider=self.name, provider_message_id=None,
                failure_code="CONNECTION_LOST", failure_detail=str(exc)[:500],
                retryable=False,
            )
        except OSError as exc:
            return self._fail("NETWORK", None, exc, retryable=True, retry_after_s=120)

        if refused:      # unreachable with one recipient; asserted rather than assumed
            return self._fail("INVALID_RECIPIENT", None, refused, retryable=False)

        log.info("sent %s to %s via %s", msg.message_id, _mask(msg.to_addr), self._host)
        return TransportResult(
            outcome="ACCEPTED", provider=self.name,
            provider_message_id=msg.rfc_message_id.strip("<>"),
            status_code=250,
            raw={"host": self._host, "envelope_from": msg.from_addr,
                 "idempotency_key": idempotency_key},
        )

    def preflight(self) -> list[str]:
        """EHLO, STARTTLS, AUTH, QUIT. Sends nothing.

        The only cheap way to tell "the App Password is wrong" from "the network is down"
        before a queue of approved messages discovers it one at a time.
        """
        problems: list[str] = []
        if not self._user:
            problems.append("no Gmail address configured (OUTREACH_GMAIL_USER)")
        if not self._password:
            problems.append("no App Password configured (OUTREACH_GMAIL_APP_PASSWORD)")
        if problems:
            return problems
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self._user, self._password)
        except smtplib.SMTPAuthenticationError:
            return ["Gmail rejected the App Password. Check 2-Step Verification is on and the "
                    "App Password has not been revoked."]
        except (OSError, smtplib.SMTPException) as exc:
            return [f"could not reach {self._host}:{self._port}: {exc}"]
        return []

    def _fail(self, code: str, status: int | None, exc: object, *,
              retryable: bool, retry_after_s: int | None = None) -> TransportResult:
        return TransportResult(
            outcome="FAILED", provider=self.name, provider_message_id=None,
            status_code=status, failure_code=code, failure_detail=str(exc)[:500],
            retryable=retryable, retry_after_s=retry_after_s,
            raw={"host": self._host},
        )


def _mask(address: str) -> str:
    local, _, domain = (address or "").partition("@")
    return f"{local[:2]}***@{domain}" if domain else "***"
