"""WhatsApp, honestly: a link Sagar clicks, and no automated first message ever.

The temptation this module refuses is the WhatsApp Business Cloud API. It exists, it is free at
low volume, and using it for cold outreach would be a policy violation on the first message:
Meta's Business Messaging Policy requires prior opt-in for a business-initiated conversation,
and a template sent to somebody who never opted in is what gets a number quality-rated down and
then blocked. There is no version of that trade that is worth a WABA number, so this build
transmits nothing on WhatsApp at all.

What it does instead is build a `wa.me` click-to-chat deep link with the message pre-filled.
Sagar opens it, reads it one more time, and presses send on his own phone with his own thumb.
The system then records what he says he sent. That is a weaker automation story and a much
stronger compliance story, and the recorded row is identical either way: same draft, same
policy check, same approval, same audit trail.

`send()` therefore never contacts anybody. It returns the link and marks the message as
transmitted-by-hand, and the caller writes a MANUAL_RECORDED event beside it so that six months
later the history says a human sent this one, not the machine.
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar
from urllib.parse import quote

from radar.channels.types import OutboundWhatsApp, TransportResult

log = logging.getLogger("radar.channels.whatsapp")

# wa.me refuses anything but digits: no plus, no spaces, no dashes.
_DIGITS = re.compile(r"\D")

# WhatsApp truncates very long pre-filled text in some clients. The message engine's own
# length budget (rule R6) is stricter; this is the transport-side floor.
MAX_TEXT_CHARS = 1000


def wa_link(phone_e164: str, text: str) -> str:
    """https://wa.me/<digits>?text=<percent-encoded>

    Raises ValueError on a number that is not dialable, because a link that opens WhatsApp on
    an empty chat is worse than no link: Sagar would paste the message into whatever thread was
    last open.
    """
    digits = _DIGITS.sub("", phone_e164 or "")
    if len(digits) < 10:
        raise ValueError(f"{phone_e164!r} is not a dialable number for a wa.me link")
    return f"https://wa.me/{digits}?text={quote(text or '', safe='')}"


class WhatsAppLinkTransport:
    """MANUAL_LINK mode. No credentials, no Cloud API, no network call of any kind."""

    name: ClassVar[str] = "wa_me"
    is_live: ClassVar[bool] = False       # nothing leaves this process
    supports_delivery_receipts: ClassVar[bool] = False

    def __init__(self, *, name_override: str | None = None) -> None:
        # PHONE and MANUAL reuse this transport: all three record rather than transmit.
        self._name = name_override or self.name

    def send(self, msg: OutboundWhatsApp, *, idempotency_key: str) -> TransportResult:
        """Produce the link. Transmits nothing; the human is the transport."""
        try:
            link = msg.link or wa_link(msg.to_e164, msg.text)
        except ValueError as exc:
            return TransportResult(
                outcome="FAILED", provider=self._name, provider_message_id=None,
                failure_code="INVALID_RECIPIENT", failure_detail=str(exc)[:500],
            )
        if len(msg.text) > MAX_TEXT_CHARS:
            log.warning("whatsapp text for %s is %d chars; clients may truncate it",
                        msg.message_id, len(msg.text))
        log.info("whatsapp link ready for %s (%s)", msg.message_id, _mask(msg.to_e164))
        return TransportResult(
            outcome="ACCEPTED", provider=self._name,
            provider_message_id=f"{self._name}:{msg.message_id}", status_code=200,
            raw={"link": link, "manual": True, "idempotency_key": idempotency_key},
        )

    def preflight(self) -> list[str]:
        return []


def build_outbound(message_id: str, phone_e164: str, text: str) -> OutboundWhatsApp:
    return OutboundWhatsApp(message_id=message_id, to_e164=phone_e164, text=text,
                            link=wa_link(phone_e164, text))


def _mask(number: str) -> str:
    digits = _DIGITS.sub("", number or "")
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"
