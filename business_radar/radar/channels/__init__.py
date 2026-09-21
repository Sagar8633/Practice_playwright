"""Answer "is this channel set up, and what would it use?" in one place.

The failure this package prevents is the one that greets a new install: a KeyError from deep
inside a transport because config/.env has never existed, surfacing as a 500 on the one screen
Sagar was trying to learn the system from. A missing credential is a fact about the laptop, not
an exception, and this is where that fact lives. Every surface that could offer a send - the
eligibility engine, the settings page, the CLI - reads its answer from here and from nowhere
else, so an unconfigured channel is a supported state with a sentence attached rather than a
crash.

The second thing that lives here is the default. `NullEmailTransport` is what runs unless a
human said otherwise: it is the default in config.example.yaml, the default when the config key
is missing, the default when the key is misspelled, and the default in every test. Every other
safety mechanism in this system is a check that can in principle be passed. That one is the
absence of a socket.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import threading
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, ClassVar, Mapping, Protocol, runtime_checkable

from radar.channels.identity import Identity, load_identity, placeholder_identity
from radar.channels.types import OutboundEmail, OutboundWhatsApp, TransportResult
from radar.config import Config, load_env
from radar.models import utc_now
from radar.paths import CONFIG_DIR, ENV_PATH, OUTBOX_DIR

log = logging.getLogger("radar.channels")

CHANNELS: tuple[str, ...] = ("EMAIL", "WHATSAPP", "PHONE", "MANUAL")

# Lock 4: credentials, keyed by (channel, live mode).
_REQUIRED_ENV: dict[tuple[str, str], tuple[str, ...]] = {
    ("EMAIL", "gmail"): ("OUTREACH_GMAIL_USER", "OUTREACH_GMAIL_APP_PASSWORD",
                         "UNSUBSCRIBE_SIGNING_SECRET"),
    ("WHATSAPP", "cloud_api"): ("WA_ACCESS_TOKEN", "WA_PHONE_NUMBER_ID", "WA_APP_SECRET"),
}

# Lock 3: an environment variable only the production launcher sets.
_LIVE_ENV: dict[str, str] = {"EMAIL": "RADAR_EMAIL_LIVE", "WHATSAPP": "RADAR_WHATSAPP_LIVE"}

STATE_PATH = CONFIG_DIR / "state" / "channels.json"

_cache: dict[str, "ChannelStatus"] = {}
_cache_lock = threading.Lock()


# ===========================================================================
# The Protocol
# ===========================================================================

@runtime_checkable
class Transport(Protocol):
    """What every channel transport must be able to do, and nothing more."""

    name: ClassVar[str]                          # goes into outreach_messages.provider
    is_live: ClassVar[bool]                      # True means real recipients receive real mail
    supports_delivery_receipts: ClassVar[bool]   # False for every transport in this build

    def send(self, msg: Any, *, idempotency_key: str) -> TransportResult:
        """Transmit one message. Never raises for a transport-side problem.

        An exception escaping send() leaves a message row with provider_send_started_at set and
        no record of what happened. Every network error becomes a TransportResult with an
        outcome; only a programming error propagates.
        """
        ...

    def preflight(self) -> list[str]:
        """Check credentials and configuration without sending. [] means ready."""
        ...


# ===========================================================================
# ChannelStatus
# ===========================================================================

@dataclass(frozen=True, slots=True)
class ChannelStatus:
    """What one channel can do right now, and what is missing if it cannot.

    Frozen, and `missing` is a tuple rather than a list, because this object is cached and
    handed to several callers. A cached value a caller can append to is a cache that lies.
    """
    channel: str
    configured: bool
    mode: str                       # UNCONFIGURED | REHEARSAL | GMAIL_LIVE | MANUAL_LINK
                                    # CLOUD_API | SCRIPT_ONLY | CLIPBOARD
    missing: tuple[str, ...] = ()
    last_verified_at: str | None = None
    last_error: str | None = None

    @property
    def unconfigured(self) -> bool:
        return not self.configured

    def sentence(self) -> str:
        """The one sentence every surface renders: name the missing precondition and where to
        fix it, never a generic refusal."""
        if self.configured:
            base = f"{self.channel} is ready ({self.mode.lower().replace('_', ' ')})."
            return f"{base} Last error: {self.last_error}" if self.last_error else base
        if self.missing:
            return (f"{self.channel} is not configured yet: {', '.join(self.missing)}. "
                    f"Everything up to approval still works; nothing can be transmitted.")
        return (f"{self.channel} is not configured yet. Everything up to approval still works; "
                f"nothing can be transmitted.")

    def to_json(self) -> dict[str, Any]:
        return {
            "channel": self.channel, "configured": self.configured, "mode": self.mode,
            "missing": list(self.missing), "last_verified_at": self.last_verified_at,
            "last_error": self.last_error, "sentence": self.sentence(),
        }


def evaluate(config: Config, env: Mapping[str, str] | None = None) -> dict[str, ChannelStatus]:
    """Read the locks for every channel. No network, no database write, no exception.

    Nothing here raises. A channel this function cannot understand is reported as UNCONFIGURED
    with the reason in `missing`, because the alternative is a startup crash on a laptop whose
    only problem is a typo in a YAML file.
    """
    environ = _environment(env)
    state = _read_state()
    out: dict[str, ChannelStatus] = {}

    for channel in CHANNELS:
        try:
            status = _evaluate_one(channel, config, environ)
        except Exception as exc:                     # noqa: BLE001 - never raise from here
            log.warning("could not evaluate channel %s: %s", channel, exc)
            status = ChannelStatus(channel, False, "UNCONFIGURED",
                                   missing=(f"configuration error: {exc}",))
        saved = state.get(channel, {})
        out[channel] = ChannelStatus(
            channel=status.channel, configured=status.configured, mode=status.mode,
            missing=status.missing,
            last_verified_at=saved.get("last_verified_at"),
            last_error=saved.get("last_error"),
        )
        log.info("channel %s configured=%s mode=%s missing=%s", channel,
                 out[channel].configured, out[channel].mode, ",".join(out[channel].missing))
    with _cache_lock:
        _cache.clear()
        _cache.update(out)
    return out


def _evaluate_one(channel: str, config: Config, env: Mapping[str, str]) -> ChannelStatus:
    if channel == "PHONE":
        # Never unconfigured, because it never transmits. It produces a call script.
        return ChannelStatus("PHONE", True, "SCRIPT_ONLY")
    if channel == "MANUAL":
        return ChannelStatus("MANUAL", True, "CLIPBOARD")
    if channel == "WHATSAPP":
        missing = [v for v in _REQUIRED_ENV[("WHATSAPP", "cloud_api")] if not env.get(v)]
        if env.get(_LIVE_ENV["WHATSAPP"], "").lower() in {"yes", "1", "true"} and not missing:
            return ChannelStatus("WHATSAPP", True, "CLOUD_API")
        # The default, and the only mode this build actually supports: a wa.me link Sagar
        # clicks himself. Zero credentials, and cold outreach through the Cloud API without a
        # recorded opt-in is a Meta policy violation regardless of credentials.
        return ChannelStatus("WHATSAPP", True, "MANUAL_LINK")

    # EMAIL: the only channel where deferred configuration is a real state.
    identity = load_identity(config)
    missing: list[str] = []
    for var in _REQUIRED_ENV[("EMAIL", "gmail")]:
        if not env.get(var):
            missing.append(var)
    if not config.email.address:
        missing.append("email address (config/.env OUTREACH_GMAIL_USER)")
    if identity.is_placeholder:
        missing.append("a real from-address (identity.from_address in config.yaml)")
    live = env.get(_LIVE_ENV["EMAIL"], "").lower() in {"yes", "1", "true"}
    if not live:
        missing.append("RADAR_EMAIL_LIVE=yes")

    if not missing:
        return ChannelStatus("EMAIL", True, "GMAIL_LIVE")
    # A rehearsal writes a file; it does not contact anybody; reporting it as configured would
    # claim a capability the system does not have. Drills are labelled.
    mode = "REHEARSAL" if config.email.configured else "UNCONFIGURED"
    return ChannelStatus("EMAIL", False, mode, missing=tuple(dict.fromkeys(missing)))


def channel_status(config: Config, channel: str = "EMAIL") -> ChannelStatus:
    """The cached answer for one channel. Evaluates on first use."""
    key = channel.upper()
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached
    return evaluate(config).get(key, ChannelStatus(key, False, "UNCONFIGURED",
                                                   missing=("unknown channel",)))


def all_channel_status(config: Config) -> dict[str, ChannelStatus]:
    with _cache_lock:
        if _cache:
            return dict(_cache)
    return evaluate(config)


def refresh(config: Config, *, reason: str = "manual") -> dict[str, ChannelStatus]:
    log.info("refreshing channel status (%s)", reason)
    return evaluate(config)


def record_test_result(channel: str, *, ok: bool, error: str | None,
                       now: str | None = None) -> None:
    """Remember what the last connection test said. Not a secret, and safe to screenshot."""
    state = _read_state()
    entry = state.setdefault(channel.upper(), {})
    entry["last_verified_at"] = (now or utc_now()) if ok else entry.get("last_verified_at")
    entry["last_error"] = None if ok else (error or "connection test failed")
    _write_state(state)
    with _cache_lock:
        _cache.clear()


def _read_state() -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


def _write_state(state: Mapping[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, **state}
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def _environment(env: Mapping[str, str] | None) -> dict[str, str]:
    if env is not None:
        return dict(env)
    merged = dict(load_env())
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


# ===========================================================================
# Unsubscribe: the token, the address, the header
# ===========================================================================

def signing_secret(env: Mapping[str, str] | None = None) -> str:
    """The HMAC key behind every unsubscribe token, minted on first use if absent.

    Nobody issues this one - it is 32 random bytes, and treating it as something Sagar has to go
    and get would put a credential-shaped obstacle in front of a value the machine can produce
    in a microsecond. It is never regenerated: rotating it invalidates every outstanding
    unsubscribe token, which is the one thing this build cannot afford to break.
    """
    environ = _environment(env)
    existing = environ.get("UNSUBSCRIBE_SIGNING_SECRET")
    if existing:
        return existing
    minted = secrets.token_hex(32)
    _append_env("UNSUBSCRIBE_SIGNING_SECRET", minted)
    os.environ["UNSUBSCRIBE_SIGNING_SECRET"] = minted
    log.warning("minted UNSUBSCRIBE_SIGNING_SECRET (fp %s) into %s; back this up with the "
                "database", sha256(minted.encode()).hexdigest()[:8], ENV_PATH)
    return minted


def _append_env(key: str, value: str) -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    tmp = ENV_PATH.with_suffix(".env.tmp")
    tmp.write_text(f"{existing}{key}={value}\n", encoding="utf-8")
    os.replace(tmp, ENV_PATH)


def unsubscribe_token(message_id: str, contact_norm: str,
                      secret: str | None = None) -> str:
    """The 32-hex token that appears in the unsubscribe address and in the body.

    Derived rather than random so that it can be recomputed and verified, and stored so that
    verification is an indexed lookup rather than a table scan. Recomputation catches a token
    minted under a different secret; the stored column turns an inbound unsubscribe into one
    primary-key hop.
    """
    key = (secret or signing_secret()).encode()
    return hmac.new(key, f"{message_id}|{contact_norm}".encode(), "sha256").hexdigest()[:32]


def unsub_address(from_address: str, token: str) -> str:
    """sagar.example+unsub-<token>@gmail.com

    The token lives in the LOCAL PART, not in the subject and not only in the body, because the
    local part is the only place a mail client cannot drop. Clients routinely strip the
    ?subject= parameter of a mailto: URI - but every one of them sends to the address.
    """
    local, _, domain = (from_address or "").partition("@")
    if not domain:
        return ""
    address = f"{local}+unsub-{token}@{domain}"
    if len(address.split("@")[0]) > 64:
        raise ValueError(f"unsubscribe local part is {len(address)} chars; Gmail caps at 64")
    return address


def unsubscribe_mailto(from_address: str, token: str, subject: str = "unsubscribe") -> str:
    address = unsub_address(from_address, token)
    return f"mailto:{address}?subject={subject}" if address else ""


def verify_unsubscribe_token(token: str, message_id: str, contact_norm: str,
                             secret: str | None = None) -> bool:
    return hmac.compare_digest(token, unsubscribe_token(message_id, contact_norm, secret))


# ===========================================================================
# Transport selection
# ===========================================================================

def get_email_transport(config: Config, *, force_null: bool = False) -> Transport:
    """The four locks, read as a factory guard rather than as a detector.

    Anything short of all four open returns the null transport. There is no configuration
    mistake whose consequence is an unintended live send.
    """
    from radar.channels.gmail import GmailTransport
    from radar.channels.null_email import NullEmailTransport

    status = channel_status(config, "EMAIL")
    if force_null or not status.configured:
        if not force_null:
            log.info("email is %s; using the null transport (%s)", status.mode,
                     ", ".join(status.missing) or "no reason given")
        return NullEmailTransport(OUTBOX_DIR)

    identity = load_identity(config)
    if identity.is_placeholder:
        # Belt to the detector's braces: a live transport may never be constructed with a
        # .invalid from-address.
        log.error("refusing a live transport with the rehearsal from-address")
        return NullEmailTransport(OUTBOX_DIR)

    return GmailTransport(
        host=config.email.smtp_host, port=config.email.smtp_port,
        user=config.email.address, app_password=config.email.app_password,
    )


def get_transport(config: Config, channel: str = "EMAIL", *, force_null: bool = False) -> Transport:
    channel = channel.upper()
    if channel == "EMAIL":
        return get_email_transport(config, force_null=force_null)
    if channel == "WHATSAPP":
        from radar.channels.whatsapp import WhatsAppLinkTransport
        return WhatsAppLinkTransport()
    if channel in {"PHONE", "MANUAL"}:
        from radar.channels.whatsapp import WhatsAppLinkTransport
        # PHONE and MANUAL never transmit; the link transport's record-only behaviour is the
        # honest stand-in until radar/channels/manual.py exists (05-outreach-workflow 5.7).
        return WhatsAppLinkTransport(name_override=channel.lower())
    raise ValueError(f"unknown channel {channel!r}")


__all__ = [
    "CHANNELS", "ChannelStatus", "Identity", "OutboundEmail", "OutboundWhatsApp",
    "Transport", "TransportResult", "all_channel_status", "channel_status", "evaluate",
    "get_email_transport", "get_transport", "load_identity", "placeholder_identity",
    "record_test_result", "refresh", "signing_secret", "unsub_address",
    "unsubscribe_mailto", "unsubscribe_token", "verify_unsubscribe_token",
]
