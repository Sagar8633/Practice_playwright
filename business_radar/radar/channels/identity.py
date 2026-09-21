"""Who an outbound message says it is from, and where a recipient can check that.

Without this module every message is anonymous. A cold email whose signature does not name a
real person, a real company, a reply address that reaches somebody, and a way to stop the mail
is not a business letter - it is the thing spam filters were built for, and it is also the thing
that makes a recipient who did not want it feel they have no recourse. Two of the policy
engine's BLOCK rules (R1 unsubscribe, R2 identity) exist purely to refuse a draft that lost one
of these strings on the way through, so the strings need one owner rather than five callers each
assembling their own.

The second job is quieter. On a laptop with an empty config/.env there is no Gmail account and
therefore no from-address, and a message engine that raised in that state would make the first
hour with this system unusable. So an unconfigured install gets a reserved placeholder identity
on `localhost.invalid` (RFC 2606 - it never resolves anywhere), which is enough for drafting,
policy checking, approval and an .eml written to data/outbox/, and which a live transport
refuses to construct itself with. The placeholder is a rehearsal identity, never a mailbox.

Note: this is the *sender* identity. `radar/identity.py` is a different thing entirely - the
normalisation of a business's own name so that one hospital is not two rows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from radar.config import Config

log = logging.getLogger("radar.channels.identity")

# RFC 2606 reserves .invalid; nothing resolves there, so a message built with this identity
# cannot be delivered even if somebody drags the .eml into a mail client.
PLACEHOLDER_ADDRESS = "radar-rehearsal@localhost.invalid"

# What we are willing to say we can demonstrate. Rule M2 refuses a message offering a demo of
# anything outside this set: we do not offer to show software that does not exist.
DEFAULT_DEMO_MODULES: tuple[str, ...] = (
    "DASHBOARD", "WORKFLOW", "REPORTS", "INVENTORY", "BILLING", "CUSTOMERS",
    "PATIENTS", "APPOINTMENTS", "DEPARTMENTS", "STUDENTS", "FEES", "ATTENDANCE",
    "STAFF", "ORDERS", "SALES", "PURCHASING", "PRODUCTION", "PAYMENTS",
)


@dataclass(frozen=True, slots=True)
class Identity:
    """The sender block, frozen because several callers read it and none may edit it."""

    sender_name: str
    company_name: str
    role: str
    from_address: str
    reply_to: str
    phone_display: str
    site_url: str
    unsubscribe_subject: str
    demo_modules: tuple[str, ...]

    @property
    def is_placeholder(self) -> bool:
        """True when no real mailbox is configured. A live transport may not use this."""
        return self.from_address.endswith(".invalid")

    @property
    def site_host(self) -> str:
        """The one host rule R7 permits in a message body. Empty when no page is configured."""
        if not self.site_url:
            return ""
        return self.site_url.split("://", 1)[-1].split("/", 1)[0].lower()

    def signature_lines(self) -> tuple[str, ...]:
        """The signature block, in order.

        An empty field is an omitted line, never a placeholder: `+91 XXXXXXXXXX` in a real
        message is the most embarrassing failure available here, and rule A3 allowlists
        signature digits, so nothing else would catch it.
        """
        contact_bits = [b for b in (self.from_address, self.phone_display) if b]
        lines = ["Regards,", self.sender_name]
        if self.role and self.company_name:
            lines.append(f"{self.role}, {self.company_name}")
        elif self.company_name:
            lines.append(self.company_name)
        if contact_bits:
            lines.append(" | ".join(contact_bits))
        if self.site_url:
            lines.append(self.site_url)
        return tuple(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender_name": self.sender_name, "company_name": self.company_name,
            "role": self.role, "from_address": self.from_address, "reply_to": self.reply_to,
            "phone_display": self.phone_display, "site_url": self.site_url,
            "is_placeholder": self.is_placeholder,
        }


def placeholder_identity(sender_name: str = "Sagar", company_name: str = "") -> Identity:
    """The identity an install with no Gmail account drafts with."""
    return Identity(
        sender_name=sender_name or "Sagar",
        company_name=company_name,
        role="Founder",
        from_address=PLACEHOLDER_ADDRESS,
        reply_to=PLACEHOLDER_ADDRESS,
        phone_display="",
        site_url="",
        unsubscribe_subject="unsubscribe",
        demo_modules=DEFAULT_DEMO_MODULES,
    )


def load_identity(config: Config) -> Identity:
    """Build the sender block from config.yaml plus the credentials in config/.env.

    SIMPLIFIED: 17-channel-configuration.md section 17.3.4 gives `identity.*` its own block in
    Config. radar/config.py does not carry one yet, so the optional `identity:` mapping is read
    straight from the same config.yaml here and everything it omits falls back to the `email:`
    block. Never raises: an unreadable YAML file is a reason to draft in rehearsal, not a reason
    to crash at import.
    """
    block = _read_identity_block(config.config_path)
    email = config.email

    sender_name = str(block.get("sender_name") or email.from_name or "Sagar")
    company_name = str(block.get("company_name") or "")
    role = str(block.get("role") or "Founder")
    site_url = str(block.get("site_url") or email.identity_page_url or "")
    from_address = str(block.get("from_address") or email.address or "").strip()

    if not from_address:
        return replace(
            placeholder_identity(sender_name, company_name),
            role=role, site_url=site_url,
            unsubscribe_subject=email.unsubscribe_subject,
            demo_modules=_demo_modules(block),
        )

    return Identity(
        sender_name=sender_name,
        company_name=company_name,
        role=role,
        from_address=from_address,
        reply_to=str(block.get("reply_to") or email.reply_to or from_address),
        phone_display=str(block.get("phone_display") or ""),
        site_url=site_url,
        unsubscribe_subject=email.unsubscribe_subject,
        demo_modules=_demo_modules(block),
    )


def _demo_modules(block: dict[str, Any]) -> tuple[str, ...]:
    raw = block.get("demo_modules")
    if not isinstance(raw, list) or not raw:
        return DEFAULT_DEMO_MODULES
    return tuple(str(m).strip().upper() for m in raw if str(m).strip())


def _read_identity_block(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning("could not read the identity block from %s: %s", path, exc)
        return {}
    block = raw.get("identity") if isinstance(raw, dict) else None
    return block if isinstance(block, dict) else {}
