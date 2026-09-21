"""Build the exact bytes that go on the wire, in one place, for both transports.

Without this module each transport assembles its own headers, and the two drift: the null
transport writes a .eml that Sagar reads and approves of, and the live one sends something
subtly different - a missing List-Unsubscribe, a Date in UTC, a Content-Type without a charset.
The whole value of rehearsing with .eml files is that the file is the message, so the file has
to be produced by the same code that produces the transmission.

Every header this system is capable of emitting is named below. There is no mechanism to add
another, because OutboundEmail has no headers dict: no X-Mailer to fingerprint us, no
Precedence: bulk to suppress the bounces we depend on, no Auto-Submitted claiming a human did
not write this when a human approved every word.
"""

from __future__ import annotations

import logging
from email import policy as email_policy
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime, parsedate_to_datetime
from datetime import datetime, timedelta, timezone

from radar.channels.types import OutboundEmail

log = logging.getLogger("radar.channels.mime")

# A business email from India timestamped +0000 is a small tell. Send the real offset.
IST = timezone(timedelta(hours=5, minutes=30))
WRAP_COLUMNS = 78

# The line limit is the RFC 5322 hard maximum rather than the 78-column recommendation, and
# that is deliberate. At 78 the header refolder cannot fold a List-Unsubscribe - it is one long
# token with no fold point - so it RFC 2047 q-encodes it instead, and a q-encoded
# List-Unsubscribe is a header no mail client honours: the only opt-out mechanism this build
# has, silently not working. Our headers are all far inside 998, and the body is hard-wrapped
# to 78 columns by wrap_body() before it ever reaches the encoder.
MIME_POLICY = email_policy.SMTP.clone(max_line_length=998)


def rfc5322_date(when: datetime | None = None) -> str:
    return format_datetime((when or datetime.now(IST)).astimezone(IST))


def wrap_body(text: str, columns: int = WRAP_COLUMNS) -> str:
    """Hard-wrap at 78 columns, preserving blank lines and never breaking a long token.

    Long lines get folded in transit, which changes the body and looks wrong in narrow
    clients. Folding here means the body Sagar approved is the body that arrives.
    """
    out: list[str] = []
    for line in (text or "").splitlines():
        if len(line) <= columns:
            out.append(line)
            continue
        current = ""
        for word in line.split(" "):
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= columns:
                current = f"{current} {word}"
            else:
                out.append(current)
                current = word
        if current:
            out.append(current)
    return "\n".join(out)


def build_mime(msg: OutboundEmail) -> EmailMessage:
    """One recipient, plain text, utf-8, with a working List-Unsubscribe."""
    mime = EmailMessage(policy=MIME_POLICY)
    mime["From"] = _address(msg.from_name, msg.from_addr)
    mime["To"] = msg.to_addr
    if msg.reply_to:
        mime["Reply-To"] = _address(msg.from_name, msg.reply_to)
    mime["Subject"] = msg.subject
    mime["Date"] = msg.date or rfc5322_date()
    mime["Message-ID"] = msg.rfc_message_id
    if msg.in_reply_to:
        mime["In-Reply-To"] = msg.in_reply_to
    if msg.references:
        mime["References"] = " ".join(msg.references)
    if msg.unsubscribe_mailto:
        # RFC 2369. One URI, and it is a mailto: - there is no HTTPS endpoint to host the other
        # half, and List-Unsubscribe-Post without one renders a button that POSTs nowhere.
        mime["List-Unsubscribe"] = f"<{msg.unsubscribe_mailto}>"
    mime.set_content(wrap_body(msg.text), subtype="plain", charset="utf-8", cte="quoted-printable")
    return mime


def _address(display_name: str, addr: str) -> str:
    local, _, domain = addr.partition("@")
    if not domain:
        return addr
    try:
        return str(Address(display_name or "", local, domain))
    except (ValueError, UnicodeEncodeError):
        log.warning("could not format display name for %s; sending the bare address", addr)
        return addr


def parse_date(raw: str) -> datetime | None:
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
