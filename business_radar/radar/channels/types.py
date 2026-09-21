"""The message-shaped values the transports move, kept apart from the policy layer.

Without this module a transport grows its own notion of what an outbound message is, and the
version of it that forgets List-Unsubscribe is the version that gets the account closed.
OutboundEmail is deliberately closed: it has no attachments field, no arbitrary headers dict,
no bcc, and no html field that can be set without also setting text - so the four mistakes that
would actually matter cannot be expressed in the type at all.

TransportResult exists for the opposite reason. A transport that raises leaves an
outreach_messages row with provider_send_started_at set and no record of what happened, which
is the one state that costs a human ten minutes in a mail client. Every network outcome,
including "we do not know", is a value here rather than an exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Outcome = Literal["ACCEPTED", "FAILED", "INDETERMINATE"]


@dataclass(frozen=True, slots=True)
class OutboundEmail:
    message_id: str                 # msg_..., the outreach_messages row
    rfc_message_id: str             # '<msg_01JB...@gmail.com>', recorded before the send
    from_addr: str
    from_name: str
    to_addr: str                    # exactly one recipient, always
    reply_to: str                   # plus-addressed for attribution, see radar/channels/gmail.py
    subject: str
    text: str                       # outreach_messages.body_final, verbatim
    unsubscribe_mailto: str         # 'mailto:...+unsub-<token>@gmail.com?subject=unsubscribe'
    unsubscribe_addr: str           # the same address, printed in the body
    in_reply_to: str | None = None  # follow-ups only
    references: tuple[str, ...] = ()
    date: str = ""                  # RFC 5322 date, filled at build time

    # There is no `attachments` field.   Nothing this system sends has one.
    # There is no `headers: dict`.       Every header emitted is named in radar/channels/mime.py.
    # There is no `cc` / `bcc`.          One recipient per message is the whole AUP argument.
    # There is no `unsubscribe_url`.     There is no public HTTPS endpoint on this deploy.
    # There is no `html`.                Plain text only; a tracking pixel cannot be expressed.


@dataclass(frozen=True, slots=True)
class OutboundWhatsApp:
    """A WhatsApp message in the only mode this build supports: a link Sagar clicks himself."""
    message_id: str
    to_e164: str                    # '+919812345678'
    text: str
    link: str                       # https://wa.me/<digits>?text=<percent-encoded>


@dataclass(frozen=True, slots=True)
class TransportResult:
    outcome: Outcome
    provider: str                   # 'null' | 'gmail' | 'wa_me'
    provider_message_id: str | None
    status_code: int | None = None
    failure_code: str | None = None  # 'INVALID_RECIPIENT', 'AUTH_FAILED', 'NETWORK', ...
    failure_detail: str | None = None
    retryable: bool = False
    retry_after_s: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.outcome == "ACCEPTED"

    def truncated_raw(self, limit: int = 4096) -> str:
        import json
        blob = json.dumps(self.raw, ensure_ascii=False, default=str)
        return blob[:limit]
