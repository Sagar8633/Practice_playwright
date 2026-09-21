"""Sortable, prefixed, greppable primary keys.

Without the prefix, a log line reading "not found: 01JB2K..." does not say which table was
searched, and a foreign key typed into the wrong column is invisible until it produces a
silently empty join. In a system whose whole job is deciding whether a business may be
contacted, a silently empty join is the failure that sends a message to the wrong company.
The prefix turns both into an immediate assertion failure at the point of the mistake.

ULID ordering is the side benefit: ids sort by creation time, so `ORDER BY id` is a usable
tiebreak when two rows share a timestamp truncated to the second, which every timestamp in
this schema is.
"""
from __future__ import annotations

import os
import secrets
import time

# Crockford base32: no I, L, O or U, so an id read aloud or typed from a screenshot does not
# turn into a different id.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_TIME_CHARS = 10        # 48 bits of milliseconds - good until the year 10889
_RANDOM_CHARS = 16      # 80 bits of randomness per millisecond
_ID_CHARS = _TIME_CHARS + _RANDOM_CHARS   # 26, the ULID length

# Every registered prefix. An unregistered one is a typo or a table nobody agreed on, and both
# are worth failing over. Canonical ruling: 01-data-model.md section 1.1.3.
PREFIXES: frozenset[str] = frozenset({
    # core loop
    "cmp",   # campaigns
    "cbz",   # campaign_businesses
    "biz",   # businesses
    "cnt",   # business_contacts
    "res",   # research_runs
    "fnd",   # research_findings
    "src",   # sources
    "opp",   # opportunities, and opportunity_modules (child rows share the parent's prefix)
    "ver",   # verifications
    "chk",   # verification_checks
    "sel",   # selections
    "out",   # outreach_drafts   - canonical
    "drf",   # outreach_drafts   - accepted alias
    "msg",   # outreach_messages
    "apr",   # outreach_approvals
    "evt",   # outreach_events
    "rsp",   # responses
    "hnd",   # handoffs
    "sup",   # suppressions
    "aud",   # audit_log
    "usr",   # users
    "job",   # jobs
    "run",   # job_runs
    "rex",   # report_exports    - canonical
    "rpt",   # report_exports    - accepted alias
    # correlation ids, not table rows
    "bat",   # jobs.batch_id, groups a fan-out
    "trc",   # jobs.trace_id, survives re-enqueue
    "req",   # audit_log.request_id, echoed as X-Request-Id
    # reserved for tables the core loop does not create yet
    "inb", "opt", "wat", "waw", "wev", "sch", "spn", "ses", "tok", "mgc", "mrg",
})

# The prefix each canonical table's ids carry. Use new_id_for() rather than remembering these.
TABLE_PREFIX: dict[str, str] = {
    "campaigns": "cmp",
    "campaign_businesses": "cbz",
    "businesses": "biz",
    "business_contacts": "cnt",
    "research_runs": "res",
    "research_findings": "fnd",
    "sources": "src",
    "opportunities": "opp",
    "opportunity_modules": "opp",
    "verifications": "ver",
    "verification_checks": "chk",
    "selections": "sel",
    "outreach_drafts": "out",
    "outreach_messages": "msg",
    "outreach_approvals": "apr",
    "outreach_events": "evt",
    "responses": "rsp",
    "handoffs": "hnd",
    "suppressions": "sup",
    "audit_log": "aud",
    "users": "usr",
    "jobs": "job",
    "job_runs": "run",
    "report_exports": "rex",
}

# Monotonicity guard. Two ids minted inside the same millisecond would otherwise sort
# arbitrarily against each other, which defeats the one reason to use ULIDs at all.
_last_ms: int = 0
_last_random: int = 0


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def _ulid() -> str:
    """A 26-character Crockford base32 ULID: 48 bits of time, 80 bits of randomness."""
    global _last_ms, _last_random

    now_ms = int(time.time() * 1000)
    if now_ms == _last_ms:
        # Same millisecond: increment the random part instead of drawing a fresh one, so the
        # two ids still sort in creation order.
        _last_random += 1
        if _last_random >= (1 << 80):        # overflow, vanishingly unlikely
            _last_ms += 1
            _last_random = secrets.randbits(80)
    else:
        _last_ms = max(now_ms, _last_ms)     # never go backwards over an NTP correction
        _last_random = secrets.randbits(80)

    return _encode(_last_ms, _TIME_CHARS) + _encode(_last_random, _RANDOM_CHARS)


def new_id(prefix: str) -> str:
    """Mint a new prefixed id, e.g. new_id("cmp") -> 'cmp_01JB2K7Q9XZ4M8T3VC0RNGHDEW'.

    Raises ValueError on an unregistered prefix: register it in PREFIXES here and in
    01-data-model.md section 1.1.3 rather than passing it through.
    """
    if prefix not in PREFIXES:
        raise ValueError(
            f"unregistered id prefix {prefix!r}; add it to radar/ids.py PREFIXES "
            f"and to 01-data-model.md section 1.1.3"
        )
    return f"{prefix}_{_ulid()}"


def new_id_for(table: str) -> str:
    """Mint an id for a canonical table name, so callers do not memorise prefixes."""
    try:
        prefix = TABLE_PREFIX[table]
    except KeyError:
        raise ValueError(
            f"no id prefix registered for table {table!r}; "
            f"add it to radar/ids.py TABLE_PREFIX"
        ) from None
    return new_id(prefix)


def prefix_of(identifier: str) -> str:
    """The prefix part of an id, or '' if it does not look like one of ours."""
    head, sep, _ = identifier.partition("_")
    return head if sep and head in PREFIXES else ""


def is_id(identifier: object, prefix: str | None = None) -> bool:
    """True if this looks like one of our ids, optionally of a specific prefix.

    Used at the top of functions that take an id, so passing a business row where a business
    id was expected fails on the line that made the mistake instead of six joins later.
    """
    if not isinstance(identifier, str):
        return False
    head, sep, body = identifier.partition("_")
    if not sep or head not in PREFIXES or len(body) != _ID_CHARS:
        return False
    if prefix is not None and head != prefix:
        return False
    return all(ch in _ALPHABET for ch in body)


def require_id(identifier: object, prefix: str, *, field: str = "id") -> str:
    """Assert an id has the expected prefix and return it. Raises ValueError otherwise."""
    if not is_id(identifier, prefix):
        raise ValueError(f"{field}: expected a {prefix}_ id, got {identifier!r}")
    return str(identifier)


def timestamp_ms(identifier: str) -> int:
    """The creation time embedded in an id, in milliseconds since the epoch.

    Useful in a maintenance session when a row's created_at has been lost or is suspect: the
    id carries its own timestamp and cannot be edited without changing the primary key.
    """
    _, sep, body = identifier.partition("_")
    if not sep or len(body) != _ID_CHARS:
        raise ValueError(f"not a radar id: {identifier!r}")
    value = 0
    for ch in body[:_TIME_CHARS]:
        idx = _ALPHABET.find(ch)
        if idx < 0:
            raise ValueError(f"not a radar id: {identifier!r}")
        value = (value << 5) | idx
    return value


def worker_id() -> str:
    """A stable-per-process label for jobs.lease_owner and job_runs.worker_id.

    Not an id in the PREFIXES sense - it names a process, not a row - but it belongs beside
    them, because a lease held by an unidentifiable owner cannot be reaped safely.
    """
    return f"{os.getpid()}-{_encode(secrets.randbits(25), 5)}"
