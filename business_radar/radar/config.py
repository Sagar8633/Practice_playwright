"""Configuration, assembled from config.yaml and config/.env, and the startup checks that stop
the system running against credentials nobody filled in.

Two shapes of failure this file exists to catch before anything else happens.

The first is running with the example values still in place. `config.example.yaml` ships a
User-Agent that says `contact: you@example.com`. Nominatim's usage policy makes an
unidentifiable User-Agent a violation that gets the IP blocked, and a placeholder contact
address is worse than none: it names somebody else. So a placeholder that would reach the
network is a refusal, not a warning.

The second is the difference between "broken" and "not configured yet", which is not the same
question for every credential. A missing GEMINI_API_KEY is broken - nothing in this system
works without a model - and the error names the file to edit. A missing Gmail app password is
not broken: it means the email channel is unconfigured, which is a completely supported state.
Discovery, research, verification, drafting and approval all work; only the send and poll
steps report the channel as off. Conflating the two would either block a first run on a
credential the operator does not need yet, or let a send path silently no-op.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG_PATH, ENV_PATH, LOGS_DIR, ROOT, ensure

log = logging.getLogger("radar.config")

# Substrings that mean "this value came from the example file and nobody edited it".
_PLACEHOLDERS = (
    "you@example.com",
    "example.github.io",
    "SAMPLE",
    "changeme",
    "your-key-here",
    "xxxx",
)


class ConfigError(RuntimeError):
    """Configuration exists but cannot be used. The message names the file to edit."""


# ---------------------------------------------------------------------------
# .env parsing
# ---------------------------------------------------------------------------

def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    """Parse config/.env into a dict. Absent file is not an error.

    Deliberately not python-dotenv: this is fifteen lines, the format is KEY=value, and one
    fewer dependency in requirements.txt is one fewer thing to install on a laptop that is
    about to run this for the first time. Values already in os.environ win, so a shell export
    can override a file for one run without editing it.
    """
    values: dict[str, str] = {}
    if path.exists():
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, sep, value = line.partition("=")
            if not sep:
                log.warning("%s line %d: no '=', ignoring", path, lineno)
                continue
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value

    # The environment is the final word: a shell export beats the file.
    for key in list(values) + [
        "GEMINI_API_KEY", "OUTREACH_GMAIL_ADDRESS", "OUTREACH_GMAIL_APP_PASSWORD",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    ]:
        env_value = os.environ.get(key)
        if env_value:
            values[key] = env_value

    return values


# ---------------------------------------------------------------------------
# Config sections
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class City:
    """One target city. `slug` is the identity used in every join; `name` is the label."""
    slug: str
    name: str
    state_region: str = "Maharashtra"
    nominatim_query: str = ""
    osm_relation_id: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> City:
        slug = str(data.get("slug") or "").strip().lower()
        name = str(data.get("name") or slug.title()).strip()
        if not slug:
            raise ConfigError("a cities entry has no slug")
        relation = data.get("osm_relation_id")
        return cls(
            slug=slug,
            name=name,
            state_region=str(data.get("state_region") or "Maharashtra"),
            nominatim_query=str(
                data.get("nominatim_query") or f"{name}, {data.get('state_region', 'Maharashtra')}, India"
            ),
            osm_relation_id=int(relation) if relation is not None else None,
        )


@dataclass(frozen=True)
class DiscoveryConfig:
    """Overpass and Nominatim access. Every number here is a fair-use obligation, not a tuning
    knob: exceeding them is how a volunteer-run service blocks the IP."""
    user_agent: str
    overpass_endpoints: tuple[str, ...]
    overpass_max_concurrent: int = 1
    overpass_min_interval_seconds: float = 6.0
    overpass_timeout_seconds: int = 180
    overpass_element_cap: int = 2000
    overpass_cache_days: int = 30
    nominatim_endpoint: str = "https://nominatim.openstreetmap.org/search"
    nominatim_min_interval_seconds: float = 1.0
    nominatim_timeout_seconds: int = 30
    website_min_interval_seconds: float = 2.0
    website_respect_robots: bool = True


@dataclass(frozen=True)
class ResearchConfig:
    depth: str = "STANDARD"
    min_opportunity_score: int = 0
    max_businesses_per_campaign: int = 200
    max_sources_per_business: int = 8
    page_fetch_timeout_seconds: int = 20
    max_page_bytes: int = 2_000_000
    snapshot_dir: Path = field(default_factory=lambda: ROOT / "data" / "capture")


@dataclass(frozen=True)
class LLMConfig:
    """Google Gemini free tier. The model id and prompt versions are pinned into every row that
    stores model output, so an audit can reproduce why a message came out the way it did."""
    api_key: str
    model: str = "gemini-2.5-flash"
    research_prompt_version: str = "research-v1"
    message_prompt_version: str = "msg-email-v1"
    classify_prompt_version: str = "classify-v1"
    temperature: float = 0.2
    max_output_tokens: int = 4096
    timeout_seconds: int = 120
    daily_request_cap: int = 180
    requests_per_minute: int = 8

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class EmailConfig:
    """The outreach mailbox. `configured` is False when the credentials are absent, which is a
    supported state and not an error: everything up to APPROVED still works."""
    address: str
    app_password: str
    from_name: str = "Sagar"
    reply_to: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_use_ssl: bool = False
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_folder: str = "INBOX"
    poll_interval_minutes: int = 20
    unsubscribe_subject: str = "unsubscribe"
    identity_page_url: str = ""
    daily_send_cap: int = 25
    send_min_gap_seconds: int = 45
    ramp_schedule: tuple[int, ...] = (5, 5, 10, 10, 15, 15, 20, 20, 25)
    bounce_rate_max_pct: float = 5.0
    complaint_rate_max_pct: float = 0.1
    bounce_rate_min_sample: int = 20

    @property
    def configured(self) -> bool:
        """True when both the address and the app password are present.

        One without the other is a half-configured channel, which is worse than none: it looks
        ready in the UI and fails at the SMTP handshake, after Sagar has approved a message.
        """
        return bool(self.address and self.app_password)

    @property
    def unsubscribe_mailto(self) -> str:
        """The List-Unsubscribe header value. mailto: only.

        There is no public hostname on this deploy, so RFC 8058 one-click unsubscribe cannot
        be offered. RFC 2369 mailto: is what remains, and the inbox poller is what makes it
        real. Empty when the channel is unconfigured, and nothing may send without it.
        """
        if not self.address:
            return ""
        return f"<mailto:{self.address}?subject={self.unsubscribe_subject}>"


@dataclass(frozen=True)
class ContactPolicyDefaults:
    """What a fresh database's GLOBAL contact_policy row is seeded with. Once the row exists,
    the row is authoritative and this is only what /settings shows as the baseline."""
    automation_mode: str = "HUMAN_APPROVAL"
    min_days_between_outreach: int = 21
    max_attempts: int = 3
    max_followups: int = 2
    stop_after_rejection: bool = True
    stop_after_opt_out: bool = True
    recent_campaign_days: int = 90
    same_domain_days: int = 30
    same_domain_max: int = 1
    verification_valid_days: int = 30
    approval_ttl_minutes: int = 60


@dataclass(frozen=True)
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8770
    threads: int = 4


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


@dataclass(frozen=True)
class Config:
    """Everything the application was told, in one immutable object."""
    cities: tuple[City, ...]
    industries: tuple[str, ...]
    categories: tuple[str, ...]
    research: ResearchConfig
    discovery: DiscoveryConfig
    llm: LLMConfig
    email: EmailConfig
    contact_policy: ContactPolicyDefaults
    web: WebConfig
    telegram: TelegramConfig
    config_path: Path
    env_path: Path
    log_level: str = "INFO"
    log_file: Path | None = None

    # --- lookups -----------------------------------------------------------
    def city(self, slug: str) -> City:
        """The city with this slug. Raises ConfigError naming the configured slugs."""
        wanted = slug.strip().lower()
        for entry in self.cities:
            if entry.slug == wanted:
                return entry
        known = ", ".join(c.slug for c in self.cities) or "(none)"
        raise ConfigError(f"unknown city {slug!r}; config.yaml has: {known}")

    @property
    def city_slugs(self) -> tuple[str, ...]:
        return tuple(c.slug for c in self.cities)

    @property
    def channels_ready(self) -> tuple[str, ...]:
        """Which outreach channels have working credentials right now.

        MANUAL is always ready: it is Sagar doing it himself and recording that he did.
        """
        ready = ["MANUAL"]
        if self.email.configured:
            ready.insert(0, "EMAIL")
        return tuple(ready)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker.lower() in lowered for marker in _PLACEHOLDERS)


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name)
    return value if isinstance(value, dict) else {}


def load_config(
    path: Path = CONFIG_PATH,
    env_path: Path = ENV_PATH,
    *,
    strict: bool = True,
) -> Config:
    """Read config.yaml and config/.env into a Config.

    `strict=True` (the default) runs the startup checks: an absent or placeholder
    GEMINI_API_KEY is a refusal, and a placeholder User-Agent is a refusal because sending it
    to Nominatim is a usage-policy violation. `strict=False` skips them, for tests and for the
    `radar config check` command that wants to report every problem rather than the first.
    """
    ensure()

    if not path.exists():
        raise ConfigError(
            f"no configuration at {path}. Copy config.example.yaml to config.yaml and edit "
            f"it, then copy config/.env.example to config/.env and fill in GEMINI_API_KEY."
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")

    env = load_env(env_path)

    # --- cities ------------------------------------------------------------
    city_entries = raw.get("cities") or []
    if not isinstance(city_entries, list):
        raise ConfigError(f"{path}: 'cities' must be a list")
    cities = tuple(City.from_dict(entry) for entry in city_entries if isinstance(entry, dict))
    seen: set[str] = set()
    for entry in cities:
        if entry.slug in seen:
            raise ConfigError(f"{path}: city slug {entry.slug!r} appears twice")
        seen.add(entry.slug)

    # --- discovery ---------------------------------------------------------
    disc = _section(raw, "discovery")
    osm = _section(disc, "overpass") or _section(disc, "osm")
    nom = _section(disc, "nominatim")
    site = _section(disc, "website")
    user_agent = str(disc.get("user_agent") or "").strip()
    endpoints = osm.get("endpoints") or ["https://overpass-api.de/api/interpreter"]
    discovery = DiscoveryConfig(
        user_agent=user_agent,
        overpass_endpoints=tuple(str(e) for e in endpoints),
        overpass_max_concurrent=int(osm.get("max_concurrent", 1)),
        overpass_min_interval_seconds=float(osm.get("min_interval_seconds", 6.0)),
        overpass_timeout_seconds=int(osm.get("timeout_seconds", 180)),
        overpass_element_cap=int(osm.get("element_cap", 2000)),
        overpass_cache_days=int(osm.get("cache_days", 30)),
        nominatim_endpoint=str(
            nom.get("endpoint", "https://nominatim.openstreetmap.org/search")
        ),
        nominatim_min_interval_seconds=float(nom.get("min_interval_seconds", 1.0)),
        nominatim_timeout_seconds=int(nom.get("timeout_seconds", 30)),
        website_min_interval_seconds=float(site.get("min_interval_seconds", 2.0)),
        website_respect_robots=bool(site.get("respect_robots", True)),
    )

    # --- research ----------------------------------------------------------
    res = _section(raw, "research")
    snapshot = res.get("snapshot_dir")
    research = ResearchConfig(
        depth=str(res.get("depth", "STANDARD")).upper(),
        min_opportunity_score=int(res.get("min_opportunity_score", 0)),
        max_businesses_per_campaign=int(res.get("max_businesses_per_campaign", 200)),
        max_sources_per_business=int(res.get("max_sources_per_business", 8)),
        page_fetch_timeout_seconds=int(res.get("page_fetch_timeout_seconds", 20)),
        max_page_bytes=int(res.get("max_page_bytes", 2_000_000)),
        snapshot_dir=(ROOT / str(snapshot)) if snapshot else (ROOT / "data" / "capture"),
    )
    if research.depth not in {"STANDARD", "DEEP"}:
        raise ConfigError(f"{path}: research.depth must be STANDARD or DEEP")
    if not 0 <= research.min_opportunity_score <= 100:
        raise ConfigError(f"{path}: research.min_opportunity_score must be 0-100")

    # --- llm ---------------------------------------------------------------
    llm_raw = _section(raw, "llm")
    llm = LLMConfig(
        api_key=env.get("GEMINI_API_KEY", "").strip(),
        model=str(llm_raw.get("model", "gemini-2.5-flash")),
        research_prompt_version=str(llm_raw.get("research_prompt_version", "research-v1")),
        message_prompt_version=str(llm_raw.get("message_prompt_version", "msg-email-v1")),
        classify_prompt_version=str(llm_raw.get("classify_prompt_version", "classify-v1")),
        temperature=float(llm_raw.get("temperature", 0.2)),
        max_output_tokens=int(llm_raw.get("max_output_tokens", 4096)),
        timeout_seconds=int(llm_raw.get("timeout_seconds", 120)),
        daily_request_cap=int(llm_raw.get("daily_request_cap", 180)),
        requests_per_minute=int(llm_raw.get("requests_per_minute", 8)),
    )

    # --- email -------------------------------------------------------------
    mail = _section(raw, "email")
    ramp = mail.get("ramp_schedule") or [5, 5, 10, 10, 15, 15, 20, 20, 25]
    email = EmailConfig(
        address=env.get("OUTREACH_GMAIL_ADDRESS", "").strip(),
        app_password=env.get("OUTREACH_GMAIL_APP_PASSWORD", "").replace(" ", "").strip(),
        from_name=str(mail.get("from_name", "Sagar")),
        reply_to=(str(mail["reply_to"]) if mail.get("reply_to") else None),
        smtp_host=str(mail.get("smtp_host", "smtp.gmail.com")),
        smtp_port=int(mail.get("smtp_port", 587)),
        smtp_use_ssl=bool(mail.get("smtp_use_ssl", False)),
        imap_host=str(mail.get("imap_host", "imap.gmail.com")),
        imap_port=int(mail.get("imap_port", 993)),
        imap_folder=str(mail.get("imap_folder", "INBOX")),
        poll_interval_minutes=int(mail.get("poll_interval_minutes", 20)),
        unsubscribe_subject=str(mail.get("unsubscribe_subject", "unsubscribe")),
        identity_page_url=str(mail.get("identity_page_url", "")),
        daily_send_cap=int(mail.get("daily_send_cap", 25)),
        send_min_gap_seconds=int(mail.get("send_min_gap_seconds", 45)),
        ramp_schedule=tuple(int(n) for n in ramp),
        bounce_rate_max_pct=float(mail.get("bounce_rate_max_pct", 5.0)),
        complaint_rate_max_pct=float(mail.get("complaint_rate_max_pct", 0.1)),
        bounce_rate_min_sample=int(mail.get("bounce_rate_min_sample", 20)),
    )

    # --- contact policy defaults -------------------------------------------
    cp = _section(raw, "contact_policy")
    policy = ContactPolicyDefaults(
        automation_mode=str(cp.get("automation_mode", "HUMAN_APPROVAL")).upper(),
        min_days_between_outreach=int(cp.get("min_days_between_outreach", 21)),
        max_attempts=int(cp.get("max_attempts", 3)),
        max_followups=int(cp.get("max_followups", 2)),
        stop_after_rejection=bool(cp.get("stop_after_rejection", True)),
        stop_after_opt_out=bool(cp.get("stop_after_opt_out", True)),
        recent_campaign_days=int(cp.get("recent_campaign_days", 90)),
        same_domain_days=int(cp.get("same_domain_days", 30)),
        same_domain_max=int(cp.get("same_domain_max", 1)),
        verification_valid_days=int(cp.get("verification_valid_days", 30)),
        approval_ttl_minutes=int(cp.get("approval_ttl_minutes", 60)),
    )
    if policy.automation_mode != "HUMAN_APPROVAL":
        raise ConfigError(
            f"{path}: contact_policy.automation_mode is {policy.automation_mode!r}. "
            f"HUMAN_APPROVAL is the only mode this build implements, and the database "
            f"rejects the others outright. Change it back."
        )

    # --- web, telegram, logging --------------------------------------------
    web_raw = _section(raw, "web")
    web = WebConfig(
        host=str(web_raw.get("host", "127.0.0.1")),
        port=int(web_raw.get("port", 8770)),
        threads=int(web_raw.get("threads", 4)),
    )
    telegram = TelegramConfig(
        bot_token=env.get("TELEGRAM_BOT_TOKEN", "").strip(),
        chat_id=env.get("TELEGRAM_CHAT_ID", "").strip(),
    )

    log_raw = _section(raw, "logging")
    log_file_value = log_raw.get("file", "logs/radar.log")
    log_file = (ROOT / str(log_file_value)) if log_file_value else None

    config = Config(
        cities=cities,
        industries=tuple(str(v).upper() for v in (raw.get("industries") or [])),
        categories=tuple(str(v).upper() for v in (raw.get("categories") or [])),
        research=research,
        discovery=discovery,
        llm=llm,
        email=email,
        contact_policy=policy,
        web=web,
        telegram=telegram,
        config_path=path,
        env_path=env_path,
        log_level=str(log_raw.get("level", "INFO")).upper(),
        log_file=log_file,
    )

    if strict:
        problems = check_config(config)
        if problems:
            raise ConfigError("\n".join(problems))

    _report_channel_state(config)
    return config


def check_config(config: Config) -> list[str]:
    """Every startup problem, as a list of messages naming the file to edit.

    Returned rather than raised so `radar config check` can print all of them at once. A
    missing email credential is deliberately not in here: it is a state, not a fault.
    """
    problems: list[str] = []

    if not config.cities:
        problems.append(
            f"{config.config_path}: no cities configured. Add at least one entry under "
            f"'cities' with a slug, a name and a nominatim_query."
        )

    if not config.llm.api_key:
        problems.append(
            f"GEMINI_API_KEY is empty. Edit {config.env_path} and paste a free-tier key from "
            f"https://aistudio.google.com/apikey. Nothing in this system - research, message "
            f"drafting or response classification - runs without it."
        )
    elif _looks_like_placeholder(config.llm.api_key):
        problems.append(
            f"GEMINI_API_KEY in {config.env_path} still looks like a placeholder. "
            f"Paste the real key."
        )

    ua = config.discovery.user_agent
    if not ua:
        problems.append(
            f"{config.config_path}: discovery.user_agent is empty. Nominatim requires an "
            f"identifiable User-Agent carrying a contact address; a default one is a usage "
            f"policy violation that gets the IP blocked."
        )
    elif _looks_like_placeholder(ua):
        problems.append(
            f"{config.config_path}: discovery.user_agent still contains an example value "
            f"({ua!r}). Put a real contact address in it before touching Overpass or "
            f"Nominatim - that address is what a volunteer sysadmin uses to reach you "
            f"instead of blocking you."
        )

    if config.discovery.nominatim_min_interval_seconds < 1.0:
        problems.append(
            f"{config.config_path}: discovery.nominatim.min_interval_seconds is "
            f"{config.discovery.nominatim_min_interval_seconds}. The policy limit is an "
            f"absolute 1 request per second. Anything below 1.0 is a violation."
        )

    if config.email.address and not config.email.app_password:
        problems.append(
            f"OUTREACH_GMAIL_ADDRESS is set but OUTREACH_GMAIL_APP_PASSWORD is empty in "
            f"{config.env_path}. A half-configured channel looks ready and fails at the SMTP "
            f"handshake, after a message has been approved. Fill it in or clear both."
        )
    if config.email.app_password and not config.email.address:
        problems.append(
            f"OUTREACH_GMAIL_APP_PASSWORD is set but OUTREACH_GMAIL_ADDRESS is empty in "
            f"{config.env_path}. Fill it in or clear both."
        )

    return problems


def _report_channel_state(config: Config) -> None:
    """Say plainly, once, which channels can actually send. Not a warning - a statement."""
    if config.email.configured:
        log.info("email channel configured: %s, cap %d/day",
                 config.email.address, config.email.daily_send_cap)
    else:
        log.info(
            "email channel is not configured (OUTREACH_GMAIL_ADDRESS / "
            "OUTREACH_GMAIL_APP_PASSWORD absent from %s). Research, verification, drafting "
            "and approval all work; nothing can be sent.",
            config.env_path,
        )
    if not config.telegram.configured:
        log.debug("telegram alerts are off; handoffs are still created and shown at /handoffs")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(
    level: str | int = "INFO",
    *,
    log_file: Path | None = None,
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
    quiet_console: bool = False,
) -> None:
    """Configure the 'radar' logger tree: console plus a rotating file.

    Idempotent - calling it twice does not double every line, which matters because both the
    CLI and the web app call it and the web app imports the CLI.
    """
    ensure()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger("radar")
    root.setLevel(level)
    root.propagate = False

    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)-22s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(logging.WARNING if quiet_console else level)
    root.addHandler(console)

    target = log_file or (LOGS_DIR / "radar.log")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        rotating = logging.handlers.RotatingFileHandler(
            target, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        rotating.setFormatter(fmt)
        rotating.setLevel(level)
        root.addHandler(rotating)
    except OSError as exc:
        # A read-only or full disk must not stop the run; it must be visible that it happened.
        console.handle(
            logging.LogRecord(
                "radar.config", logging.ERROR, __file__, 0,
                "cannot write the log file at %s (%s); console logging only",
                (target, exc), None,
            )
        )

    # These libraries are chatty at DEBUG and none of it is ours.
    for noisy in ("urllib3", "requests", "google", "google_genai", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
