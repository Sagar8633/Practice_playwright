"""Answers "is this channel set up?" in one place, so that no screen has to guess.

The failure this module prevents is the one that greets a new install: a KeyError from deep
inside a transport because config/.env has never existed, surfacing as a 500 on the one screen
Sagar was trying to learn the system from. A missing credential is a fact about the laptop, not
an exception, and this is where that fact lives. Every surface that could offer a send - the
eligibility engine, /settings/channels, the outreach workspace, the preview - reads its answer
from here and from nowhere else.

17-channel-configuration.md section 17.3.1 defines four independent locks per channel, and the
point of having four is that going live means touching four different kinds of thing in four
different places. A "go live" button would collapse three of them into one click, which is
exactly the failure the locks exist to prevent, so nothing in this module writes anything.

SIMPLIFIED: doc 17 section 17.3.3 caches ChannelStatus with explicit invalidation, and section
17.6 runs an eleven-step SMTP/IMAP connection test whose result feeds last_verified_at and
last_error. Neither is here: evaluation is four dictionary lookups, so it runs per request, and
last_verified_at reads whatever the sender recorded rather than probing Gmail from a page load.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Mapping

from radar.config import Config
from radar.models import ContactPolicy

log = logging.getLogger("radar.web.channels")

CHANNELS: tuple[str, ...] = ("EMAIL", "WHATSAPP", "PHONE", "MANUAL")

# Lock 4: credentials that must be present in config/.env. Names follow config/.env.example,
# which is the authority on this build - doc 17 quotes OUTREACH_GMAIL_USER, radar/config.py
# reads OUTREACH_GMAIL_ADDRESS, and the file on disk wins.
_REQUIRED_ENV: dict[str, tuple[str, ...]] = {
    "EMAIL": ("OUTREACH_GMAIL_ADDRESS", "OUTREACH_GMAIL_APP_PASSWORD"),
}

# Lock 3: an environment variable set only by the launcher that starts the service. Nothing in
# the app can set it, which is the whole point.
_LIVE_ENV: dict[str, str] = {"EMAIL": "RADAR_EMAIL_LIVE"}

_HUMAN_NAMES: dict[str, str] = {
    "OUTREACH_GMAIL_ADDRESS": "the dedicated Gmail account address",
    "OUTREACH_GMAIL_APP_PASSWORD": "an App Password for Mail on that account",
    "RADAR_EMAIL_LIVE": "RADAR_EMAIL_LIVE=yes in the environment that starts the app",
}


@dataclass(frozen=True, slots=True)
class ChannelStatus:
    """What one channel can do right now, and what is missing if it cannot.

    Frozen, and `missing` is a tuple rather than a list, because this object is handed to five
    callers. A shared value a caller can append to is a value that lies to the next caller.
    """

    channel: str                     # EMAIL | WHATSAPP | PHONE | MANUAL
    configured: bool                 # can this channel complete its own transmission step?
    mode: str                        # UNCONFIGURED | GMAIL_LIVE | MANUAL_LINK | SCRIPT_ONLY |
                                     # CLIPBOARD
    missing: tuple[str, ...] = ()    # ordered, human-readable, most-blocking first
    locks: tuple[tuple[str, bool, str], ...] = ()   # (label, open, detail) for the settings tab
    switch_on: bool = True           # contact_policy.<channel>_enabled
    last_verified_at: str | None = None
    last_error: str | None = None
    note: str = ""

    @property
    def unconfigured(self) -> bool:
        return not self.configured

    def sentence(self) -> str:
        """The one sentence every surface renders.

        15-ui-wireframe.md section 15.18.3's register: name the missing precondition and where
        to fix it, never a generic refusal.
        """
        if self.configured and self.switch_on:
            return ""
        if not self.switch_on:
            return ("The %s channel is switched off in contact policy."
                    % self.channel.lower())
        if self.missing:
            return ("%s is not configured yet. Still needed: %s."
                    % (self.channel.title(), self.missing[0]))
        return "%s is not configured yet." % self.channel.title()

    def to_dict(self) -> dict[str, object]:
        return {
            "channel": self.channel,
            "configured": self.configured,
            "mode": self.mode,
            "missing": list(self.missing),
            "switch_on": self.switch_on,
            "last_verified_at": self.last_verified_at,
            "last_error": self.last_error,
        }


def evaluate(config: Config, policy: ContactPolicy,
             env: Mapping[str, str] | None = None) -> dict[str, ChannelStatus]:
    """Every channel's status, keyed by channel name. Reads; never writes."""
    env = os.environ if env is None else env
    return {
        "EMAIL": _email(config, policy, env),
        "WHATSAPP": _whatsapp(policy),
        "PHONE": _phone(policy),
        "MANUAL": _manual(policy),
    }


def _email(config: Config, policy: ContactPolicy, env: Mapping[str, str]) -> ChannelStatus:
    address = (config.email.address or env.get("OUTREACH_GMAIL_ADDRESS") or "").strip()
    password = (config.email.app_password or env.get("OUTREACH_GMAIL_APP_PASSWORD") or "").strip()
    live_env = (env.get(_LIVE_ENV["EMAIL"], "") or "").strip().lower() in ("yes", "1", "true")

    lock1 = bool(config.email.smtp_host)
    lock2 = bool(policy.email_enabled) and policy.email_sending_domain is not None
    lock3 = live_env
    lock4 = bool(address) and bool(password)

    missing: list[str] = []
    if not lock4:
        for name in _REQUIRED_ENV["EMAIL"]:
            if not (env.get(name) or "").strip() and not (
                name == "OUTREACH_GMAIL_ADDRESS" and address
            ) and not (name == "OUTREACH_GMAIL_APP_PASSWORD" and password):
                missing.append(_HUMAN_NAMES[name] + " in config/.env")
    if not lock2:
        missing.append(
            "contact_policy.email_sending_domain, the deliberate on-switch a fresh database "
            "leaves NULL so it cannot mail anybody by accident"
        )
    if not lock3:
        missing.append(_HUMAN_NAMES["RADAR_EMAIL_LIVE"])
    if not lock1:
        missing.append("an smtp_host in config.yaml")

    configured = lock1 and lock2 and lock3 and lock4
    return ChannelStatus(
        channel="EMAIL",
        configured=configured,
        mode="GMAIL_LIVE" if configured else "UNCONFIGURED",
        missing=tuple(missing),
        locks=(
            ("1  transport named in config.yaml", lock1,
             config.email.smtp_host or "not set"),
            ("2  channel switch in contact_policy", lock2,
             policy.email_sending_domain or "email_sending_domain is NULL"),
            ("3  RADAR_EMAIL_LIVE in the launcher environment", lock3,
             "yes" if lock3 else "not set"),
            ("4  credentials in config/.env", lock4,
             "present" if lock4 else "%d missing" % (2 - int(bool(address)) - int(bool(password)))),
        ),
        switch_on=bool(policy.email_enabled),
        note=(
            "There is no custom domain. The from-address is an @gmail.com address, SPF, DKIM "
            "and DMARC are Google's and cannot be configured, and a spam complaint costs the "
            "account rather than a domain."
        ),
    )


def _whatsapp(policy: ContactPolicy) -> ChannelStatus:
    # Lock 1 is satisfied by the shipped manual_link default and lock 2 by whatsapp_enabled;
    # manual_link needs no credentials because nothing is transmitted by this machine.
    return ChannelStatus(
        channel="WHATSAPP",
        configured=True,
        mode="MANUAL_LINK",
        switch_on=bool(policy.whatsapp_enabled),
        locks=(("Cloud API", bool(policy.whatsapp_api_enabled),
                "whatsapp_api_enabled = %d" % int(bool(policy.whatsapp_api_enabled))),),
        note=(
            "Business-initiated WhatsApp needs a pre-approved template and a recorded opt-in. "
            "v1 produces a wa.me link you open yourself, and needs no credentials."
        ),
    )


def _phone(policy: ContactPolicy) -> ChannelStatus:
    return ChannelStatus(
        channel="PHONE",
        configured=True,
        mode="SCRIPT_ONLY",
        switch_on=bool(policy.phone_enabled),
        note="The system never dials. It produces a call script; you log the call afterwards.",
    )


def _manual(policy: ContactPolicy) -> ChannelStatus:
    return ChannelStatus(
        channel="MANUAL",
        configured=True,
        mode="CLIPBOARD",
        switch_on=bool(policy.manual_enabled),
        note="Copy the approved body and send it yourself, then record that you did.",
    )
