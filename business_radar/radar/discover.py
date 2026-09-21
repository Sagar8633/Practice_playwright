"""Finds businesses in towns nobody has finished mapping, and refuses to find the same one twice.

Without the identity key in here, the second campaign over Dhule creates fresh rows for every
clinic Sagar already rejected in June, and the system emails a business he personally said no
to. That is the failure this module exists to prevent, and it is why every insert goes through
radar.identity.business_key rather than through a name comparison.

The second thing it holds is the coverage arithmetic, and that one is subtler. OpenStreetMap in
Nashik is decent; in Dhule and Shirpur it is thin. A retail query over Shirpur returns six
elements, the report renders six businesses, and nothing on that page is false - but it reads as
"the retail sector of Shirpur", Sagar works down the list, and he concludes there is no retail
opportunity in a town he has not actually looked at. A short list is indistinguishable from a
small town, and only one of those two is a finding. discovery_coverage is where the difference
gets written down.

The third thing is manners. Overpass and Nominatim are volunteer-run, there is no account and no
bill, and the fair-use limits are obligations rather than tuning knobs. Every query is cached on
disk by the hash of its exact text, so re-running a city inside the TTL costs the volunteers
nothing; every request waits its turn behind a throttle; and every one of them carries an
identifiable User-Agent with a contact address on it. Get this wrong and the IP is blocked, at
which point there is no discovery at all.

Design source: 02-research-pipeline.md sections 2.2.4, 2.2.5, 2.2.9, 2.3.5, 2.3.6 and 2.4.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import random
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import requests

from radar import db
from radar.audit import audit
from radar.config import City, Config
from radar.fetch import HostThrottle, is_denied_host
from radar.identity import (
    business_key,
    city_slug as slugify_city,
    host_of,
    normalise_email,
    normalise_name,
    normalise_phone,
    normalise_source_url,
    normalise_url,
    registrable_domain,
)
from radar.ids import new_id_for
from radar.models import utc_now
from radar.paths import DATA_DIR

log = logging.getLogger("radar.discover")

OVERPASS_CACHE_DIR: Path = DATA_DIR / "cache" / "overpass"

# An OSM relation with id R becomes Overpass area id 3600000000 + R. We use relations only.
AREA_ID_BASE = 3_600_000_000

OVERPASS_MAXSIZE_BYTES = 268_435_456
NOMINATIM_TTL_DAYS = 365
DEFAULT_RADIUS_M = 9000

DISCOVERY_ACTOR = "discover"


class DiscoveryError(RuntimeError):
    """Discovery could not proceed. The campaign stops here rather than reporting a short list."""


class DiscoveryTruncated(DiscoveryError):
    """Overpass returned exactly the element cap, so the answer is silently incomplete.

    Overpass has no cursor and no pagination: a truncated result looks exactly like a complete
    one unless somebody compares the count with the cap. Raised so the caller can split the
    group; caught by discover_city, which marks the coverage row UNKNOWN rather than publishing
    a number computed on a truncated set.
    """


# --------------------------------------------------------------------------------------------
# The category-to-tag map
#
# Every _CONTEXT.md section 6 category, mapped to the OSM tags that actually carry it in India.
# `nwr` means node, way and relation: a hospital is frequently a building way rather than a
# point, and querying nodes only is the commonest way to lose half of a city.
# --------------------------------------------------------------------------------------------

CATEGORY_SELECTORS: dict[str, tuple[str, ...]] = {
    "HOSPITAL": (
        '["amenity"="hospital"]',
        '["healthcare"="hospital"]',
    ),
    "DIAGNOSTIC_CENTER": (
        '["healthcare"~"^(laboratory|diagnostics|radiology)$"]',
    ),
    "SCHOOL": (
        '["amenity"="school"]',
        '["amenity"="kindergarten"]',
    ),
    "COLLEGE": (
        '["amenity"~"^(college|university)$"]',
        '["office"="educational_institution"]',
    ),
    "VEHICLE_DEALER": (
        '["shop"~"^(car|motorcycle|truck|agrarian|trailer)$"]',
    ),
    "GARAGE": (
        '["shop"~"^(car_repair|motorcycle_repair|tyres|car_parts)$"]',
        '["amenity"="car_wash"]',
    ),
    "MANUFACTURER": (
        '["man_made"="works"]',
        '["industrial"="factory"]',
        '["craft"]',
        '["office"="company"]',
        # Queried as a geographic hint only. See _LANDUSE_IS_NOT_A_BUSINESS below: nothing
        # derived from a landuse element is ever inserted as a business.
        '["landuse"="industrial"]',
    ),
    "DISTRIBUTOR": (
        '["shop"~"^(wholesale|trade)$"]',
        '["industrial"="warehouse"]',
        '["office"="logistics"]',
        '["office"="company"]',
    ),
    "HOTEL": (
        '["tourism"~"^(hotel|guest_house|motel|hostel|apartment)$"]',
    ),
    "RESTAURANT": (
        '["amenity"~"^(restaurant|fast_food|cafe|ice_cream|food_court|banquet_hall|events_venue)$"]',
    ),
    "BAKERY": (
        '["shop"~"^(bakery|pastry|confectionery)$"]',
        '["craft"="bakery"]',
    ),
    # SIMPLIFIED: the build brief writes this as shop=*, which would drag in car_repair,
    # wholesale and estate_agent and double-count them against three other categories.
    # 02-research-pipeline.md section 2.2.4 gives the real allowlist, and it is used here.
    "RETAIL_STORE": (
        '["shop"~"^(supermarket|department_store|clothes|shoes|electronics|mobile_phone|'
        'furniture|hardware|doityourself|jewelry|optician|chemist|variety_store|general|'
        'convenience|sports|books|toys|paint|farm)$"]',
        '["amenity"="pharmacy"]',
    ),
    "REAL_ESTATE_AGENCY": (
        '["office"="estate_agent"]',
        '["shop"="estate_agent"]',
    ),
    # Clinics, doctors, dentists and professional offices are real prospects for which no
    # _CONTEXT.md category fits. They classify as category OTHER with the right industry.
    # Government, NGO, political and diplomatic offices are excluded by allowlist: they are not
    # prospects and they pollute the density denominator.
    "OTHER": (
        '["amenity"~"^(clinic|doctors|dentist)$"]',
        '["healthcare"~"^(centre|clinic|dentist)$"]',
        '["office"~"^(accountant|lawyer|it|insurance|financial|consulting|engineer|architect|'
        'advertising_agency|employment_agency|travel_agent)$"]',
        '["amenity"="bank"]',
    ),
}

# One query per tag group, not one per category: eight queries per city, each small enough to
# finish inside the timeout and large enough to be worth a slot.
TAG_GROUPS: dict[str, tuple[str, ...]] = {
    "G1_HEALTH": ("HOSPITAL", "DIAGNOSTIC_CENTER"),
    "G2_EDUCATION": ("SCHOOL", "COLLEGE"),
    "G3_AUTOMOBILE": ("VEHICLE_DEALER", "GARAGE"),
    "G4_INDUSTRY": ("MANUFACTURER",),
    "G5_DISTRIBUTION": ("DISTRIBUTOR",),
    "G6_RETAIL": ("RETAIL_STORE", "BAKERY"),
    "G7_HOSPITALITY": ("HOTEL", "RESTAURANT"),
    "G8_PROFESSIONAL": ("REAL_ESTATE_AGENCY", "OTHER"),
}

INDUSTRY_OF_CATEGORY: dict[str, str] = {
    "HOSPITAL": "HEALTHCARE",
    "DIAGNOSTIC_CENTER": "HEALTHCARE",
    "SCHOOL": "EDUCATION",
    "COLLEGE": "EDUCATION",
    "VEHICLE_DEALER": "AUTOMOBILE",
    "GARAGE": "AUTOMOBILE",
    "MANUFACTURER": "MANUFACTURING",
    "DISTRIBUTOR": "DISTRIBUTION",
    "HOTEL": "HOSPITALITY",
    "RESTAURANT": "HOSPITALITY",
    "BAKERY": "RETAIL",
    "RETAIL_STORE": "RETAIL",
    "REAL_ESTATE_AGENCY": "REAL_ESTATE",
    "OTHER": "OTHER",
}

# An industrial landuse polygon is a MIDC estate or an industrial area. It is not a business, it
# has nobody to contact, and inserting one produces a prospect called "Dhule MIDC Phase II".
_LANDUSE_IS_NOT_A_BUSINESS = True

# The free stack's replacement for businessStatus=CLOSED_PERMANENTLY.
_LIFECYCLE_PREFIXES = ("disused:", "abandoned:", "was:", "demolished:", "construction:", "razed:")

# A tag-rich element carries at least one of these: a proxy for how actively the area is mapped,
# not just whether it is.
_TAG_RICH_KEYS = ("website", "contact:website", "url", "phone", "contact:phone", "mobile",
                  "addr:street", "opening_hours", "email", "contact:email")

_NAME_KEYS = ("name", "name:en", "official_name", "operator", "brand")


# --------------------------------------------------------------------------------------------
# Coverage priors
#
# SIMPLIFIED: 02-research-pipeline.md section 2.2.9 puts all of these under a
# `discovery.coverage:` block in config.yaml so they can be tuned without a code change. They are
# module constants here because radar/config.py's Config has no coverage section to read them
# from, and adding one is a change to a shared foundation module. Moving them later is a
# mechanical change: nothing outside this block reads them.
# --------------------------------------------------------------------------------------------

# SAMPLE priors. These are Sagar's calibration knobs, not data. Revise each the first time a
# city is counted by hand.
EXPECTED_PER_100K: dict[str, int] = {
    "HOSPITAL": 8, "DIAGNOSTIC_CENTER": 12, "SCHOOL": 40, "COLLEGE": 4,
    "MANUFACTURER": 25, "DISTRIBUTOR": 20, "VEHICLE_DEALER": 10, "GARAGE": 40,
    "HOTEL": 15, "RESTAURANT": 60, "BAKERY": 15, "RETAIL_STORE": 250,
    "REAL_ESTATE_AGENCY": 12, "OTHER": 40,
}

# SAMPLE, Census 2011. Fifteen years stale, which is what GROWTH_FACTOR is for: without it the
# denominator is too small and coverage flatters itself.
CITY_POPULATION: dict[str, int] = {
    "dhule": 376_093,
    "shirpur": 118_786,
    "nashik": 1_486_053,
    "jalgaon": 460_468,
}

GROWTH_FACTOR = 1.30
MIN_ABSOLUTE = 5
LOW_BELOW_PCT = 35
HIGH_AT_OR_ABOVE_PCT = 75
TAG_RICH_FLOOR_PCT = 25


# --------------------------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CityBound:
    """How one city's queries are bounded, and how we came to bound them that way.

    `source` is not decoration. A campaign that quietly searched a 9 km circle when Sagar
    believed it searched a municipality produces a coverage number that means nothing, so the
    fallback is recorded on the row and printed in the coverage note.
    """
    slug: str
    name: str
    kind: str                       # AREA | RADIUS
    area_id: int | None = None
    lat: float | None = None
    lon: float | None = None
    radius_m: int = DEFAULT_RADIUS_M
    source: str = "CONFIG"          # CONFIG | NOMINATIM_AREA | NOMINATIM_RADIUS
    display_name: str = ""

    @property
    def clause(self) -> str:
        """The Overpass filter appended to every statement in the query."""
        if self.kind == "AREA":
            return "(area.city)"
        return "(around:" + str(int(self.radius_m)) + "," + str(self.lat) + "," + str(self.lon) + ")"

    @property
    def preamble(self) -> str:
        if self.kind == "AREA":
            return "area(" + str(self.area_id) + ")->.city;\n"
        return ""

    @property
    def is_exact(self) -> bool:
        """True when the bound is a real municipal boundary rather than a judgement call."""
        return self.kind == "AREA"


@dataclass(slots=True)
class OverpassResult:
    """One tag-group query and what came back, whether or not the network was touched."""
    query: str
    query_sha256: str
    elements: list[dict[str, Any]]
    element_count: int
    truncated: bool
    from_cache: bool
    endpoint: str
    fetched_at: str


@dataclass(slots=True)
class DiscoveredBusiness:
    """One OSM element, parsed. Not yet a businesses row - the filters run first."""
    osm_ref: str
    name: str
    tags: dict[str, str]
    city: str
    city_slug: str
    industry: str = "OTHER"
    category: str = "OTHER"
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    pincode: str | None = None
    website: str | None = None
    website_domain: str | None = None
    phone_raw: str | None = None
    email_raw: str | None = None
    is_landuse: bool = False
    is_closed: bool = False
    tag_rich: bool = False

    @property
    def is_business(self) -> bool:
        """An element with no name and no landuse exemption is not a business.

        It is counted in elements_found and not in elements_kept, which is the whole reason
        those two numbers are separate: a Shirpur retail query that returns 40 elements of which
        34 are unnamed nodes has not found 40 businesses.
        """
        return bool(self.name) and not self.is_landuse

    @property
    def osm_url(self) -> str:
        return "https://www.openstreetmap.org/" + self.osm_ref


@dataclass(slots=True)
class CoverageAssessment:
    """How much of one city and category we actually saw, and how sure we are of that."""
    city_slug: str
    category: str
    elements_found: int
    elements_kept: int
    businesses_new: int
    tag_rich_pct: int | None
    denominator: int | None
    denominator_kind: str           # REGISTRY | POPULATION_MODEL | NONE
    population_used: int | None
    coverage_pct: int | None
    band: str                       # HIGH | MEDIUM | LOW | UNKNOWN
    truncated: bool
    note: str
    provider: str = "OSM"


@dataclass(slots=True)
class CityDiscovery:
    """Everything one discover_city() call did, for the CLI and the report to print."""
    campaign_id: str
    city_slug: str
    city_name: str
    bound: CityBound
    groups_run: list[str] = field(default_factory=list)
    groups_cached: list[str] = field(default_factory=list)
    groups_truncated: list[str] = field(default_factory=list)
    elements_found: int = 0
    elements_kept: int = 0
    businesses_new: int = 0
    businesses_rediscovered: int = 0
    businesses_skipped: int = 0
    contacts_added: int = 0
    coverage: list[CoverageAssessment] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            self.city_name + ": " + str(self.businesses_new) + " new",
            str(self.businesses_rediscovered) + " already known",
            str(self.elements_kept) + " of " + str(self.elements_found) + " elements kept",
        ]
        if self.groups_cached:
            parts.append(str(len(self.groups_cached)) + " groups served from cache")
        if self.groups_truncated:
            parts.append("TRUNCATED: " + ", ".join(self.groups_truncated))
        return "; ".join(parts)


# --------------------------------------------------------------------------------------------
# Throttles. Module level, because the fair-use limit is per IP, not per object.
# --------------------------------------------------------------------------------------------

_overpass_throttle = HostThrottle(6.0)
_nominatim_throttle = HostThrottle(1.0)


# --------------------------------------------------------------------------------------------
# Query building
# --------------------------------------------------------------------------------------------

def selectors_for(categories: Iterable[str]) -> list[str]:
    """The OSM selector fragments for a set of categories, deduplicated, in a stable order."""
    seen: dict[str, None] = {}
    for category in categories:
        for selector in CATEGORY_SELECTORS.get(category.upper(), ()):
            seen.setdefault(selector, None)
    return list(seen)


def build_query(
    bound: CityBound,
    categories: Sequence[str],
    *,
    timeout_seconds: int = 180,
    element_cap: int = 2000,
    maxsize_bytes: int = OVERPASS_MAXSIZE_BYTES,
) -> str:
    """Overpass QL for one tag group over one city.

    Three details that are not optional:

    `out tags center` returns tags plus one representative coordinate for ways and relations.
    `out body` would return every node of every building outline: megabytes of geometry we never
    use, and a download budget spent on nothing.

    The trailing element cap guards against a mis-bounded query. It is not a page size - Overpass
    has no cursor and no pagination, so a result that comes back at exactly the cap is silent
    data loss unless somebody looks for it. overpass() looks for it.

    `[timeout:...]` is the server-side execution budget and `[maxsize:...]` the memory budget.
    Exceeding either returns an error whose only correct response is a smaller query, never a
    retry of the identical one.
    """
    selectors = selectors_for(categories)
    if not selectors:
        raise DiscoveryError("no OSM selectors for categories " + repr(list(categories)))

    lines = [
        "[out:json][timeout:" + str(int(timeout_seconds)) + "][maxsize:" + str(int(maxsize_bytes)) + "];",
    ]
    if bound.preamble:
        lines.append(bound.preamble.rstrip("\n"))
    lines.append("(")
    for selector in selectors:
        lines.append("  nwr" + selector + bound.clause + ";")
    lines.append(");")
    lines.append("out tags center " + str(int(element_cap)) + ";")
    return "\n".join(lines) + "\n"


def query_hash(query: str) -> str:
    """The cache key: sha256 of the exact QL text.

    Exact, so that changing one selector changes the key and a stale answer can never be served
    for a new question.
    """
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------------
# The cache
# --------------------------------------------------------------------------------------------

def _iso_plus_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def cached_payload(
    conn: sqlite3.Connection,
    provider: str,
    key: str,
    *,
    now: str | None = None,
) -> dict[str, Any] | None:
    """The cached provider payload, or None when it is missing, purged or past its TTL.

    Returning None means "ask again", which for Overpass costs a slot and six seconds. This is
    the only function permitted to read discovery_cache.payload_*, so there is exactly one place
    where the freshness rule can be got wrong, and one place to fix it.
    """
    now = now or utc_now()
    row = conn.execute(
        "SELECT payload_json, payload_path, expires_at, purged_at, element_count, truncated "
        "  FROM discovery_cache WHERE provider = ? AND provider_key = ?",
        (provider, key),
    ).fetchone()
    if row is None:
        return None
    if row["purged_at"]:
        return None
    if row["expires_at"] and row["expires_at"] <= now:
        log.debug("cache entry %s/%s expired at %s", provider, key, row["expires_at"])
        return None

    if row["payload_json"]:
        try:
            return json.loads(row["payload_json"])
        except json.JSONDecodeError:
            log.error("discovery_cache %s/%s holds unparseable JSON; treating as a miss",
                      provider, key)
            return None

    path = Path(row["payload_path"]) if row["payload_path"] else None
    if path is None or not path.exists():
        log.warning("discovery_cache %s/%s points at a missing file %s; treating as a miss",
                    provider, key, path)
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        # Loudly, and move the bad file aside rather than silently pretending it was never there.
        broken = path.with_suffix(path.suffix + ".corrupt")
        log.error("cannot read cached payload %s (%s); moving it to %s", path, exc, broken)
        try:
            path.replace(broken)
        except OSError:
            pass
        return None


def _write_payload(sha: str, payload: dict[str, Any]) -> Path:
    """Write a raw response to disk atomically, before a single element is parsed.

    Parsing is then a pure function of a file on disk, which is what makes the tag map testable
    against real data with no network in the test suite.
    """
    OVERPASS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = OVERPASS_CACHE_DIR / (sha + ".json.gz")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)
    tmp.replace(path)
    return path


def _store_cache_row(
    conn: sqlite3.Connection,
    *,
    provider: str,
    key: str,
    query_text: str,
    payload: dict[str, Any],
    element_count: int,
    truncated: bool,
    ttl_days: int,
    inline: bool = False,
) -> None:
    payload_json = json.dumps(payload) if inline else None
    payload_path = None if inline else str(_write_payload(key, payload))
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO discovery_cache "
            "  (provider, provider_key, query_text, payload_json, payload_path, payload_sha256,"
            "   element_count, truncated, retention_class, fetched_at, expires_at) "
            "VALUES (?,?,?,?,?,?,?,?,'DURABLE',?,?) "
            "ON CONFLICT (provider, provider_key) DO UPDATE SET "
            "  query_text=excluded.query_text, payload_json=excluded.payload_json,"
            "  payload_path=excluded.payload_path, payload_sha256=excluded.payload_sha256,"
            "  element_count=excluded.element_count, truncated=excluded.truncated,"
            "  fetched_at=excluded.fetched_at, expires_at=excluded.expires_at, purged_at=NULL",
            (
                provider, key, query_text, payload_json, payload_path,
                hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest(),
                element_count, 1 if truncated else 0, utc_now(), _iso_plus_days(ttl_days),
            ),
        )


# --------------------------------------------------------------------------------------------
# The Overpass client
# --------------------------------------------------------------------------------------------

def _request_overpass(
    query: str,
    *,
    cfg: Config,
    session: requests.Session,
    max_attempts: int = 3,
    backoff_initial_seconds: float = 60.0,
) -> tuple[dict[str, Any], str]:
    """POST the query, rotating endpoints and backing off. Returns (payload, endpoint).

    HTTP 429 means no slot: it is a defer, not a failure, and it is not held against the
    attempt budget the way a real error is. HTTP 504 with "Query timed out" and the
    out-of-memory runtime error both mean the query was too big; retrying the identical query is
    pointless and rude, so they raise immediately and the caller splits the group.
    """
    endpoints = list(cfg.discovery.overpass_endpoints) or [
        "https://overpass-api.de/api/interpreter"
    ]
    headers = {
        "User-Agent": cfg.discovery.user_agent,
        "Accept": "application/json",
        "Content-Type": "text/plain; charset=utf-8",
    }
    last_error = "no attempt was made"

    for attempt in range(1, max_attempts + 1):
        endpoint = endpoints[(attempt - 1) % len(endpoints)]
        host = host_of(endpoint) or endpoint
        _overpass_throttle.wait(host)

        log.info("overpass attempt %d/%d via %s", attempt, max_attempts, endpoint)
        try:
            response = session.post(
                endpoint,
                data=query.encode("utf-8"),
                headers=headers,
                timeout=cfg.discovery.overpass_timeout_seconds + 30,
            )
        except requests.RequestException as exc:
            last_error = type(exc).__name__ + ": " + str(exc)
            log.warning("overpass request failed (%s)", last_error)
        else:
            body = response.text or ""
            if response.status_code == 200:
                try:
                    return json.loads(body), endpoint
                except json.JSONDecodeError as exc:
                    last_error = "overpass returned 200 with unparseable JSON: " + str(exc)
                    log.warning("%s", last_error)
            elif response.status_code in (429, 503):
                # Slot exhaustion. Wait for what the server suggests, or the backoff.
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if (retry_after or "").isdigit() else (
                    backoff_initial_seconds * (2 ** (attempt - 1))
                )
                delay = min(delay, 3600.0) + random.uniform(0, 3)
                last_error = "HTTP " + str(response.status_code) + " (no slot)"
                log.warning("overpass has no slot; waiting %.0fs", delay)
                if attempt < max_attempts and delay > 0:
                    time.sleep(delay)
                continue
            elif "Query timed out" in body or "run out of memory" in body:
                raise DiscoveryError(
                    "overpass refused this query as too large (" + str(response.status_code) +
                    "). Split the tag group or shrink the radius; retrying it unchanged will "
                    "fail the same way and waste a slot."
                )
            else:
                last_error = "HTTP " + str(response.status_code) + ": " + body[:200]
                log.warning("overpass error: %s", last_error)

        if attempt < max_attempts:
            delay = min(backoff_initial_seconds * (2 ** (attempt - 1)), 3600.0)
            if delay > 0:
                time.sleep(delay)

    raise DiscoveryError("overpass failed after " + str(max_attempts) + " attempts: " + last_error)


def overpass(
    conn: sqlite3.Connection,
    *,
    query: str,
    cfg: Config,
    force: bool = False,
    session: requests.Session | None = None,
    backoff_initial_seconds: float = 60.0,
) -> OverpassResult:
    """Run one tag-group query, or return the cached response without touching the network.

    A hit costs nothing and takes no slot; a miss waits its turn behind the throttle and writes
    the raw response to disk before parsing a single element.

    Without this, developing the tag map means hammering a volunteer's server with the same query
    forty times in an afternoon, which is how an IP gets blocked and how this project becomes the
    thing it refuses to be.
    """
    sha = query_hash(query)
    cap = cfg.discovery.overpass_element_cap

    if not force:
        payload = cached_payload(conn, "OSM_OVERPASS", sha)
        if payload is not None:
            elements = list(payload.get("elements") or [])
            log.info("overpass cache hit for %s (%d elements)", sha[:12], len(elements))
            return OverpassResult(
                query=query, query_sha256=sha, elements=elements,
                element_count=len(elements), truncated=len(elements) >= cap,
                from_cache=True, endpoint="cache", fetched_at=utc_now(),
            )

    owns_session = session is None
    http = session or requests.Session()
    try:
        payload, endpoint = _request_overpass(
            query, cfg=cfg, session=http,
            backoff_initial_seconds=backoff_initial_seconds,
        )
    finally:
        if owns_session:
            http.close()

    elements = list(payload.get("elements") or [])
    truncated = len(elements) >= cap

    _store_cache_row(
        conn,
        provider="OSM_OVERPASS", key=sha, query_text=query, payload=payload,
        element_count=len(elements), truncated=truncated,
        ttl_days=cfg.discovery.overpass_cache_days,
    )

    if truncated:
        log.error("overpass returned exactly the element cap (%d): the answer is incomplete", cap)

    return OverpassResult(
        query=query, query_sha256=sha, elements=elements, element_count=len(elements),
        truncated=truncated, from_cache=False, endpoint=endpoint, fetched_at=utc_now(),
    )


# --------------------------------------------------------------------------------------------
# Nominatim
# --------------------------------------------------------------------------------------------

def resolve_city(
    city: City,
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
    session: requests.Session | None = None,
    radius_m: int = DEFAULT_RADIUS_M,
) -> CityBound:
    """The Overpass bound for a city: its admin relation where one exists, a radius where not.

    The configured relation id is used without a network call, which is the point of pasting it
    into config.yaml: a campaign should not depend on a live geocoder. Only an unresolved city
    reaches Nominatim, at one request per second with an identifiable User-Agent, and the answer
    is cached for a year because municipal boundaries barely move.

    SIMPLIFIED: 02-research-pipeline.md section 2.2.4 makes an explicit `bound: AREA` with a null
    relation id a startup failure rather than a silent downgrade to a radius. radar/config.py's
    City has no `bound` field to declare that intent with, so there is nothing to contradict.
    The downgrade is instead recorded on CityBound.source and printed in every coverage note for
    the city, so a radius never gets read as a municipal boundary.
    """
    if city.osm_relation_id:
        return CityBound(
            slug=city.slug, name=city.name, kind="AREA",
            area_id=AREA_ID_BASE + int(city.osm_relation_id),
            source="CONFIG", display_name=city.name,
        )

    cache_key = city.slug + "|boundary"
    payload: dict[str, Any] | None = None
    if conn is not None:
        payload = cached_payload(conn, "NOMINATIM", cache_key)

    if payload is None:
        endpoint = cfg.discovery.nominatim_endpoint
        params = {
            "q": city.nominatim_query or (city.name + ", " + city.state_region + ", India"),
            "format": "jsonv2",
            "limit": "1",
            "addressdetails": "0",
        }
        headers = {"User-Agent": cfg.discovery.user_agent, "Accept": "application/json"}

        _nominatim_throttle.wait(host_of(endpoint) or "nominatim")

        owns_session = session is None
        http = session or requests.Session()
        try:
            response = http.get(
                endpoint, params=params, headers=headers,
                timeout=cfg.discovery.nominatim_timeout_seconds,
            )
            response.raise_for_status()
            results = response.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            raise DiscoveryError(
                "cannot resolve " + city.name + " through Nominatim: " + str(exc)
            ) from exc
        finally:
            if owns_session:
                http.close()

        if not results:
            raise DiscoveryError(
                "Nominatim found nothing for " + repr(params["q"]) + ". Fix the "
                "nominatim_query in config.yaml, or paste an osm_relation_id for this city."
            )
        payload = {"result": results[0]}
        if conn is not None:
            _store_cache_row(
                conn, provider="NOMINATIM", key=cache_key,
                query_text=endpoint + "?q=" + str(params["q"]),
                payload=payload, element_count=1, truncated=False,
                ttl_days=NOMINATIM_TTL_DAYS, inline=True,
            )

    result = payload.get("result") or {}
    lat = float(result["lat"]) if result.get("lat") else None
    lon = float(result["lon"]) if result.get("lon") else None
    display = str(result.get("display_name") or city.name)

    if result.get("osm_type") == "relation" and result.get("osm_id"):
        log.info("resolved %s to OSM relation %s; paste osm_relation_id: %s into config.yaml "
                 "so the next campaign needs no geocoder", city.name, result["osm_id"],
                 result["osm_id"])
        return CityBound(
            slug=city.slug, name=city.name, kind="AREA",
            area_id=AREA_ID_BASE + int(result["osm_id"]),
            lat=lat, lon=lon, source="NOMINATIM_AREA", display_name=display,
        )

    if lat is None or lon is None:
        raise DiscoveryError("Nominatim returned no usable geometry for " + city.name)

    log.warning(
        "%s has no admin relation in OSM; falling back to a %d m radius around %.4f,%.4f. "
        "This is a judgement, not a boundary, and every coverage note for the city says so.",
        city.name, radius_m, lat, lon,
    )
    return CityBound(
        slug=city.slug, name=city.name, kind="RADIUS", lat=lat, lon=lon,
        radius_m=radius_m, source="NOMINATIM_RADIUS", display_name=display,
    )


# --------------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------------

def classify_element(tags: dict[str, str]) -> tuple[str, str]:
    """(industry, category) for one element's tags, first match wins.

    The order matters: an element tagged both amenity=clinic and healthcare=laboratory is a
    diagnostic centre, and a shop=bakery inside a supermarket building is a bakery.
    """
    amenity = tags.get("amenity", "")
    shop = tags.get("shop", "")
    healthcare = tags.get("healthcare", "")
    office = tags.get("office", "")
    tourism = tags.get("tourism", "")

    category = "OTHER"

    if healthcare in {"laboratory", "diagnostics", "radiology"}:
        category = "DIAGNOSTIC_CENTER"
    elif amenity == "hospital" or healthcare == "hospital":
        category = "HOSPITAL"
    elif amenity == "clinic" and tags.get("healthcare:speciality", "") in {"pathology", "radiology"}:
        category = "DIAGNOSTIC_CENTER"
    elif amenity == "clinic" and _looks_like_hospital(tags):
        # A "nursing home" is usually tagged amenity=clinic. Promote it when the name says so,
        # or when beds or an emergency department are recorded.
        category = "HOSPITAL"
    elif amenity in {"clinic", "doctors", "dentist"} or healthcare in {"centre", "clinic", "dentist"}:
        return "HEALTHCARE", "OTHER"
    elif amenity in {"school", "kindergarten"}:
        category = "SCHOOL"
    elif amenity in {"college", "university"} or office == "educational_institution":
        category = "COLLEGE"
    elif shop in {"car", "motorcycle", "truck", "agrarian", "trailer"}:
        category = "VEHICLE_DEALER"
    elif shop in {"car_repair", "motorcycle_repair", "tyres", "car_parts"} or amenity == "car_wash":
        category = "GARAGE"
    elif tourism in {"hotel", "guest_house", "motel", "hostel", "apartment"}:
        category = "HOTEL"
    elif amenity in {"restaurant", "fast_food", "cafe", "ice_cream", "food_court",
                     "banquet_hall", "events_venue"}:
        category = "RESTAURANT"
    elif shop in {"bakery", "pastry", "confectionery"} or tags.get("craft") == "bakery":
        category = "BAKERY"
    elif shop in {"wholesale", "trade"} or tags.get("industrial") == "warehouse" \
            or office == "logistics":
        category = "DISTRIBUTOR"
    elif tags.get("man_made") == "works" or tags.get("industrial") == "factory" \
            or (office == "company" and tags.get("industrial")) or tags.get("craft"):
        category = "MANUFACTURER"
    elif office == "estate_agent" or shop == "estate_agent":
        category = "REAL_ESTATE_AGENCY"
    elif shop or amenity == "pharmacy":
        category = "RETAIL_STORE"
    elif office == "company":
        category = "DISTRIBUTOR"
    elif office in {"accountant", "lawyer", "it", "insurance", "financial", "consulting",
                    "engineer", "architect", "advertising_agency", "employment_agency",
                    "travel_agent"} or amenity == "bank":
        return "PROFESSIONAL_SERVICES", "OTHER"

    return INDUSTRY_OF_CATEGORY.get(category, "OTHER"), category


def _looks_like_hospital(tags: dict[str, str]) -> bool:
    name = " ".join(tags.get(key, "") for key in _NAME_KEYS).lower()
    if "hospital" in name or "nursing home" in name:
        return True
    return bool(tags.get("beds")) or tags.get("emergency") == "yes"


def _element_name(tags: dict[str, str]) -> str:
    for key in _NAME_KEYS:
        value = (tags.get(key) or "").strip()
        if value:
            return value
    return ""


def _element_address(tags: dict[str, str]) -> str | None:
    parts = [
        tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb"),
        tags.get("addr:city"), tags.get("addr:postcode"),
    ]
    joined = ", ".join(part.strip() for part in parts if part and part.strip())
    return joined or None


def _first_tag(tags: dict[str, str], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = (tags.get(key) or "").strip()
        if value:
            return value
    return None


def parse_elements(
    payload_or_elements: dict[str, Any] | Sequence[dict[str, Any]],
    *,
    city_name: str,
    city_slug: str,
) -> list[DiscoveredBusiness]:
    """Turn an Overpass response into candidate business records.

    A pure function of a payload, which is what makes the tag map testable against real captured
    data with no network in the test suite. Filtering happens in discover_city, not here: the
    unnamed nodes and the landuse polygons come back too, because elements_found has to count
    them before elements_kept drops them.
    """
    if isinstance(payload_or_elements, dict):
        elements = list(payload_or_elements.get("elements") or [])
    else:
        elements = list(payload_or_elements)

    out: list[DiscoveredBusiness] = []
    for element in elements:
        tags = {str(k): str(v) for k, v in (element.get("tags") or {}).items()}
        osm_type = str(element.get("type") or "node")
        osm_id = element.get("id")
        if osm_id is None:
            continue
        osm_ref = osm_type + "/" + str(osm_id)

        centre = element.get("center") or {}
        latitude = element.get("lat", centre.get("lat"))
        longitude = element.get("lon", centre.get("lon"))

        website_raw = _first_tag(tags, ("website", "contact:website", "url"))
        website = normalise_url(website_raw)
        if website and is_denied_host(host_of(website)):
            # A facebook.com page is a social presence, not a website. It becomes a SOCIAL
            # source elsewhere; it must never become businesses.website_domain.
            website = None

        pincode = (tags.get("addr:postcode") or "").strip() or None
        if pincode and not (len(pincode) == 6 and pincode.isdigit()):
            pincode = None

        industry, category = classify_element(tags)
        is_landuse = "landuse" in tags and not any(
            key in tags for key in ("man_made", "industrial", "office", "craft", "shop", "amenity")
        )

        out.append(DiscoveredBusiness(
            osm_ref=osm_ref,
            name=_element_name(tags),
            tags=tags,
            city=(tags.get("addr:city") or city_name).strip() or city_name,
            city_slug=city_slug,
            industry=industry,
            category=category,
            latitude=float(latitude) if latitude is not None else None,
            longitude=float(longitude) if longitude is not None else None,
            address=_element_address(tags),
            pincode=pincode,
            website=website,
            website_domain=registrable_domain(website),
            phone_raw=_first_tag(tags, ("phone", "contact:phone", "mobile")),
            email_raw=_first_tag(tags, ("email", "contact:email")),
            is_landuse=is_landuse,
            is_closed=_is_closed(tags),
            tag_rich=any(key in tags for key in _TAG_RICH_KEYS),
        ))
    return out


def _is_closed(tags: dict[str, str]) -> bool:
    if tags.get("opening_hours", "").strip().lower() == "closed":
        return True
    return any(key.startswith(_LIFECYCLE_PREFIXES) for key in tags)


# --------------------------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------------------------

def _round_half_up(value: float) -> int:
    return int(value + 0.5) if value >= 0 else -int(-value + 0.5)


def coverage_band(
    kept: int,
    denominator: int | None,
    tag_rich_pct: int | None,
    *,
    truncated: bool = False,
) -> tuple[str, int | None]:
    """How much of this city and category did we actually see? Returns (band, coverage_pct).

    UNKNOWN when there is nothing honest to compare against; LOW when the answer is "not much";
    and never HIGH on a set of name-only nodes, however many of them there are.

    This function exists because a short list is indistinguishable from a small town, and only
    one of those two is a finding. Without it the report quietly asserts that Shirpur has six
    shops, Sagar believes it, and the most under-served city in the campaign is the one he stops
    working.
    """
    if truncated or denominator is None or denominator <= 0:
        return "UNKNOWN", None
    pct = min(100, _round_half_up(100.0 * kept / denominator))
    if kept < MIN_ABSOLUTE:
        return "LOW", pct
    if pct < LOW_BELOW_PCT:
        return "LOW", pct
    band = "HIGH" if pct >= HIGH_AT_OR_ABOVE_PCT else "MEDIUM"
    if band == "HIGH" and (tag_rich_pct or 0) < TAG_RICH_FLOOR_PCT:
        # Name-only nodes are a mapped area in name only.
        return "MEDIUM", pct
    return band, pct


def expected_count(city_slug: str, category: str) -> tuple[int | None, str, int | None]:
    """The denominator for a (city, category) pair: (denominator, kind, population_used).

    SIMPLIFIED: 02-research-pipeline.md section 2.2.9 puts a REGISTRY denominator first - UDISE+
    schools, AICTE colleges, PM-JAY hospitals - because a measured denominator deserves more
    trust than a modelled one. Those registry importers are not built yet, so only the
    POPULATION_MODEL branch and the honest NONE branch exist here. The kind is stored on the row
    either way, so the report can label a modelled number as modelled, and adding the registry
    branch later changes nothing else.
    """
    population = CITY_POPULATION.get(city_slug)
    per_100k = EXPECTED_PER_100K.get(category.upper())
    if not population or not per_100k:
        return None, "NONE", population
    denominator = int(round(population * GROWTH_FACTOR / 100_000 * per_100k))
    return max(denominator, 1), "POPULATION_MODEL", population


def coverage_confidence(
    city: City | str,
    category: str,
    n_found: int,
    *,
    kept: int | None = None,
    businesses_new: int = 0,
    tag_rich_pct: int | None = None,
    truncated: bool = False,
    bound: CityBound | None = None,
) -> CoverageAssessment:
    """The full coverage assessment for one (city, category) pair, note included.

    `n_found` is what the query returned; `kept` is what survived the name and lifecycle checks
    and defaults to it. The note is the sentence the report prints, and it is written here rather
    than in the template so that the number and the sentence explaining it can never disagree.
    """
    slug = city.slug if isinstance(city, City) else slugify_city(city)
    label = city.name if isinstance(city, City) else str(city)
    kept_count = n_found if kept is None else kept

    denominator, kind, population = expected_count(slug, category)
    band, pct = coverage_band(kept_count, denominator, tag_rich_pct, truncated=truncated)

    note = _coverage_note(
        label=label, category=category, kept=kept_count, found=n_found, band=band, pct=pct,
        denominator=denominator, kind=kind, tag_rich_pct=tag_rich_pct, truncated=truncated,
        bound=bound,
    )

    return CoverageAssessment(
        city_slug=slug, category=category.upper(), elements_found=n_found,
        elements_kept=kept_count, businesses_new=businesses_new, tag_rich_pct=tag_rich_pct,
        denominator=denominator, denominator_kind=kind, population_used=population,
        coverage_pct=pct, band=band, truncated=truncated, note=note,
    )


def _coverage_note(
    *,
    label: str,
    category: str,
    kept: int,
    found: int,
    band: str,
    pct: int | None,
    denominator: int | None,
    kind: str,
    tag_rich_pct: int | None,
    truncated: bool,
    bound: CityBound | None,
) -> str:
    head = label + " / " + category.upper() + " - coverage " + band + "."

    if truncated:
        return (
            head + " The Overpass query came back at the element cap, so this is a truncated "
            "answer and no coverage figure can be computed from it. Re-run the group with a "
            "narrower bound before reading anything into the list."
        )

    if kind == "NONE" or denominator is None:
        return (
            head + " " + str(kept) + " of " + str(found) + " OpenStreetMap elements were kept, "
            "and there is no denominator to compare that against, so how much of " + label +
            " this represents is genuinely unknown. Do not read the list as the sector."
        )

    basis = ("the state registry" if kind == "REGISTRY"
             else "a population model (Census 2011 uplifted by " + str(GROWTH_FACTOR) + ")")
    sentence = (
        head + " " + str(kept) + " kept against an expected " + str(denominator) +
        " from " + basis + ", which is " + str(pct) + " percent."
    )
    if tag_rich_pct is not None:
        sentence += (" " + str(tag_rich_pct) + " percent of the kept elements carry a website, "
                     "phone, street or opening hours.")
    if band == "LOW":
        sentence += (" OpenStreetMap coverage of this category in " + label + " is sparse: treat "
                     "the list as a sample, not as the sector.")
    if bound is not None and not bound.is_exact:
        sentence += (" The city was bounded by a " + str(bound.radius_m) + " m radius rather "
                     "than a municipal boundary, which is a judgement and not a limit.")
    return sentence


# --------------------------------------------------------------------------------------------
# Writing it down
# --------------------------------------------------------------------------------------------

def _live_suppression(conn: sqlite3.Connection, record: DiscoveredBusiness) -> str | None:
    """The scope of a live suppression matching this business, or None.

    An opt-out is absolute, permanent and cross-channel. A business that unsubscribed in June
    must not come back into a campaign in September just because a different query found it, so
    the check happens at discovery, before the row is even eligible for research.
    """
    checks: list[tuple[str, str]] = []
    if record.website_domain:
        checks.append(("DOMAIN", record.website_domain))
    email = normalise_email(record.email_raw)
    if email.valid and email.value_norm:
        checks.append(("EMAIL", email.value_norm))
        if email.domain:
            checks.append(("DOMAIN", email.domain))
    phone = normalise_phone(record.phone_raw)
    if phone.valid and phone.e164:
        checks.append(("PHONE", phone.e164))
        checks.append(("WHATSAPP", phone.e164))

    for scope, value in checks:
        row = conn.execute(
            "SELECT id FROM suppressions "
            " WHERE scope = ? AND value_norm = ? AND released_at IS NULL AND erased_at IS NULL "
            " LIMIT 1",
            (scope, value),
        ).fetchone()
        if row is not None:
            return scope
    return None


def _insert_source(
    conn: sqlite3.Connection,
    *,
    business_id: str,
    record: DiscoveredBusiness,
) -> str | None:
    """Record the OSM element as the source it is. Returns the src_ id, or None if already there."""
    url = record.osm_url
    url_norm = normalise_source_url(url)
    existing = conn.execute(
        "SELECT id FROM sources WHERE business_id = ? AND url_norm = ?",
        (business_id, url_norm),
    ).fetchone()
    if existing is not None:
        return existing["id"]

    obtained = ", ".join(sorted(
        key for key in record.tags
        if key in {"name", "website", "phone", "email", "addr:street", "addr:postcode",
                   "opening_hours", "operator", "brand"}
    )) or "name and category tags"

    source_id = new_id_for("sources")
    conn.execute(
        "INSERT INTO sources (id, business_id, name, url, source_type, information_obtained,"
        "                     confidence, url_norm, domain, checked_at) "
        "VALUES (?,?,?,?,'MAP',?,'MEDIUM',?,?,?)",
        (source_id, business_id, "OpenStreetMap " + record.osm_ref, url,
         "OSM tags: " + obtained, url_norm, "openstreetmap.org", utc_now()),
    )
    return source_id


def _insert_contacts(
    conn: sqlite3.Connection,
    *,
    business_id: str,
    record: DiscoveredBusiness,
    source_id: str | None,
) -> int:
    """Write the phone and email OSM published, as unverified contact rows.

    No value written here is ever sent to a language model. Contacts are rows, not columns, and
    the research prompt receives neither: the address is substituted into a rendered message
    locally, after generation.
    """
    added = 0

    email = normalise_email(record.email_raw)
    if email.valid and email.value_norm and email.domain:
        exists = conn.execute(
            "SELECT 1 FROM business_contacts "
            " WHERE business_id = ? AND kind = 'EMAIL' AND value_norm = ?",
            (business_id, email.value_norm),
        ).fetchone()
        if exists is None:
            conn.execute(
                "INSERT INTO business_contacts "
                "  (id, business_id, kind, value_raw, value_norm, value_dedupe, value_display,"
                "   domain, is_role_address, source_id, source_url, source_note, confidence) "
                "VALUES (?,?,'EMAIL',?,?,?,?,?,?,?,?,?,'MEDIUM')",
                (new_id_for("business_contacts"), business_id, email.raw, email.value_norm,
                 email.value_dedupe, email.display, email.domain,
                 1 if email.is_role_address else 0, source_id, record.osm_url,
                 "published in the OpenStreetMap element " + record.osm_ref),
            )
            added += 1

    phone = normalise_phone(record.phone_raw)
    if phone.valid and phone.e164:
        exists = conn.execute(
            "SELECT 1 FROM business_contacts "
            " WHERE business_id = ? AND kind = 'PHONE' AND value_norm = ?",
            (business_id, phone.e164),
        ).fetchone()
        if exists is None:
            conn.execute(
                "INSERT INTO business_contacts "
                "  (id, business_id, kind, value_raw, value_norm, value_dedupe, value_display,"
                "   phone_e164, phone_number_type, phone_norm_version, source_id, source_url,"
                "   source_note, confidence) "
                "VALUES (?,?,'PHONE',?,?,?,?,?,?,?,?,?,?,'MEDIUM')",
                (new_id_for("business_contacts"), business_id, phone.raw, phone.e164,
                 phone.e164, phone.display, phone.e164, phone.number_type, phone.version,
                 source_id, record.osm_url,
                 "published in the OpenStreetMap element " + record.osm_ref),
            )
            added += 1

    return added


def _write_coverage(
    conn: sqlite3.Connection,
    campaign_id: str,
    assessment: CoverageAssessment,
) -> None:
    conn.execute(
        "INSERT INTO discovery_coverage "
        "  (campaign_id, city, category, provider, elements_found, elements_kept,"
        "   businesses_new, tag_rich_pct, denominator, denominator_kind, population_used,"
        "   coverage_pct, band, truncated, note, computed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT (campaign_id, city, category, provider) DO UPDATE SET "
        "  elements_found=excluded.elements_found, elements_kept=excluded.elements_kept,"
        "  businesses_new=excluded.businesses_new, tag_rich_pct=excluded.tag_rich_pct,"
        "  denominator=excluded.denominator, denominator_kind=excluded.denominator_kind,"
        "  population_used=excluded.population_used, coverage_pct=excluded.coverage_pct,"
        "  band=excluded.band, truncated=excluded.truncated, note=excluded.note,"
        "  computed_at=excluded.computed_at",
        (campaign_id, assessment.city_slug, assessment.category, assessment.provider,
         assessment.elements_found, assessment.elements_kept, assessment.businesses_new,
         assessment.tag_rich_pct, assessment.denominator, assessment.denominator_kind,
         assessment.population_used, assessment.coverage_pct, assessment.band,
         1 if assessment.truncated else 0, assessment.note, utc_now()),
    )


def _upsert_business(
    conn: sqlite3.Connection,
    *,
    campaign_id: str,
    record: DiscoveredBusiness,
    requested_categories: frozenset[str],
    requested_industries: frozenset[str],
    actor: str,
) -> tuple[str, bool, int]:
    """Insert or recognise one business. Returns (business_id, is_new, contacts_added).

    The dedupe decision is business_key and nothing else. A name that merely looks similar is
    never merged here: that goes to a human, because a false split costs one verification and a
    false merge silently applies one company's rejection to another.
    """
    phone = normalise_phone(record.phone_raw)
    key = business_key(
        name=record.name, city=record.city,
        website=record.website,
        phone_norm=phone.e164 if phone.valid else None,
        phone_number_type=phone.number_type if phone.valid else None,
    )

    existing = conn.execute(
        "SELECT id, status FROM businesses "
        " WHERE business_key = ? AND merged_into_id IS NULL LIMIT 1",
        (key,),
    ).fetchone()

    suppression_scope = _live_suppression(conn, record)

    if existing is not None:
        business_id = str(existing["id"])
        source_id = _insert_source(conn, business_id=business_id, record=record)
        added = _insert_contacts(conn, business_id=business_id, record=record,
                                 source_id=source_id)
        _link_campaign(
            conn, campaign_id=campaign_id, business_id=business_id, record=record,
            is_rediscovery=True, requested_categories=requested_categories,
            requested_industries=requested_industries, suppression_scope=suppression_scope,
            source_id=source_id, is_closed=record.is_closed,
        )
        audit(conn, actor, "BUSINESS_REDISCOVERED", "businesses", business_id,
              business_id=business_id, campaign_id=campaign_id,
              detail={"osm_ref": record.osm_ref, "business_key": key,
                      "city_slug": record.city_slug})
        return business_id, False, added

    if record.is_closed:
        status, skip_reason = "SKIPPED", "MANUAL"
    elif suppression_scope:
        status, skip_reason = "SKIPPED", "MANUAL"
    else:
        status, skip_reason = "AI_RESEARCHED", None

    business_id = new_id_for("businesses")
    conn.execute(
        "INSERT INTO businesses "
        "  (id, business_key, name, name_norm, city, city_slug, state_region, address, pincode,"
        "   latitude, longitude, industry, category, website, website_domain, website_status,"
        "   listing_url, status, status_actor_kind, status_changed_at, skip_reason,"
        "   research_status, first_seen_campaign_id, first_discovered_at, osm_ref,"
        "   osm_tags_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'SYSTEM',?,?,?,?,?,?,?) "
        "ON CONFLICT (business_key) WHERE merged_into_id IS NULL DO NOTHING",
        (
            business_id, key, record.name, normalise_name(record.name, city=record.city),
            record.city, record.city_slug, "Maharashtra", record.address, record.pincode,
            record.latitude, record.longitude, record.industry, record.category,
            record.website, record.website_domain,
            "PRESENT" if record.website else "UNKNOWN",
            record.osm_url, status, utc_now(), skip_reason,
            "PENDING" if status == "AI_RESEARCHED" else "COMPLETE",
            campaign_id, utc_now(), record.osm_ref,
            json.dumps(record.tags, ensure_ascii=False, sort_keys=True),
        ),
    )

    row = conn.execute(
        "SELECT id FROM businesses WHERE business_key = ? AND merged_into_id IS NULL",
        (key,),
    ).fetchone()
    if row is None:
        raise DiscoveryError("business " + key + " vanished between insert and read")
    is_new = str(row["id"]) == business_id
    business_id = str(row["id"])

    source_id = _insert_source(conn, business_id=business_id, record=record)
    added = _insert_contacts(conn, business_id=business_id, record=record, source_id=source_id)
    _link_campaign(
        conn, campaign_id=campaign_id, business_id=business_id, record=record,
        is_rediscovery=not is_new, requested_categories=requested_categories,
        requested_industries=requested_industries, suppression_scope=suppression_scope,
        source_id=source_id, is_closed=record.is_closed,
    )

    audit(conn, actor, "BUSINESS_DISCOVERED" if is_new else "BUSINESS_REDISCOVERED",
          "businesses", business_id, business_id=business_id, campaign_id=campaign_id,
          after={"name": record.name, "category": record.category, "status": status},
          detail={"osm_ref": record.osm_ref, "business_key": key,
                  "city_slug": record.city_slug,
                  "suppressed": suppression_scope or ""})
    return business_id, is_new, added


def _link_campaign(
    conn: sqlite3.Connection,
    *,
    campaign_id: str,
    business_id: str,
    record: DiscoveredBusiness,
    is_rediscovery: bool,
    requested_categories: frozenset[str],
    requested_industries: frozenset[str],
    suppression_scope: str | None,
    source_id: str | None,
    is_closed: bool = False,
) -> None:
    """Membership of this campaign, with the reason if it is excluded from it.

    Exclusion lives on the membership row rather than on the business, because "not in this
    campaign" and "never contact this business" are different facts and conflating them is how a
    business excluded from a retail campaign in March never gets looked at again.
    """
    existing = conn.execute(
        "SELECT id FROM campaign_businesses WHERE campaign_id = ? AND business_id = ?",
        (campaign_id, business_id),
    ).fetchone()
    if existing is not None:
        return

    state, reason, detail = "INCLUDED", None, None
    if suppression_scope:
        state, reason = "EXCLUDED", "LIVE_SUPPRESSION"
        detail = json.dumps({"scope": suppression_scope})
    elif is_closed:
        # There is no CLOSED value in the exclusion_reason enum. MANUAL plus a detail is the
        # honest encoding: this business is out of the campaign for a stated reason, and the
        # reason is not that it failed a filter.
        state, reason = "EXCLUDED", "MANUAL"
        detail = json.dumps({"closed": True, "evidence": "OSM lifecycle prefix or opening_hours=closed"})
    elif requested_categories and record.category not in requested_categories:
        state, reason = "EXCLUDED", "CATEGORY_FILTER"
        detail = json.dumps({"category": record.category})
    elif requested_industries and record.industry not in requested_industries:
        state, reason = "EXCLUDED", "INDUSTRY_FILTER"
        detail = json.dumps({"industry": record.industry})

    conn.execute(
        "INSERT INTO campaign_businesses "
        "  (id, campaign_id, business_id, state, exclusion_reason, exclusion_detail,"
        "   is_rediscovery, discovery_source, discovery_source_id, city_at_discovery,"
        "   industry_at_discovery, category_at_discovery, first_seen_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (new_id_for("campaign_businesses"), campaign_id, business_id, state, reason, detail,
         1 if is_rediscovery else 0, "OSM_OVERPASS", source_id, record.city_slug,
         record.industry, record.category, utc_now()),
    )


# --------------------------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------------------------

def discover_city(
    conn: sqlite3.Connection,
    campaign_id: str,
    city: City,
    categories: Sequence[str],
    *,
    cfg: Config,
    force: bool = False,
    session: requests.Session | None = None,
    bound: CityBound | None = None,
    backoff_initial_seconds: float = 60.0,
) -> CityDiscovery:
    """Discover one city for one campaign: query, parse, dedupe, insert, and score the coverage.

    Each tag group is one query and one transaction. A crash before the commit loses the group
    and the retry redoes it, and because the retry hits the cache it costs Overpass nothing. A
    crash after the commit means the group is done. There is no window in which a business row
    exists without its campaign membership and its source, because all three are written by the
    same commit.
    """
    wanted = frozenset(c.upper() for c in categories if c)
    unknown = wanted - set(CATEGORY_SELECTORS)
    if unknown:
        raise DiscoveryError("no OSM tag map for categories " + repr(sorted(unknown)))
    if not wanted:
        raise DiscoveryError("discover_city needs at least one category")

    requested_industries = frozenset(
        INDUSTRY_OF_CATEGORY.get(c, "OTHER") for c in wanted
    ) | ({"HEALTHCARE", "PROFESSIONAL_SERVICES"} if "OTHER" in wanted else set())

    city_bound = bound or resolve_city(city, cfg=cfg, conn=conn, session=session)
    report = CityDiscovery(
        campaign_id=campaign_id, city_slug=city.slug, city_name=city.name, bound=city_bound,
    )

    log.info("discovering %s (%s bound, source %s) for %d categories",
             city.name, city_bound.kind, city_bound.source, len(wanted))

    # Per-category tallies, so coverage is computed on what we saw rather than on what we hoped.
    found: dict[str, int] = {c: 0 for c in wanted}
    kept: dict[str, int] = {c: 0 for c in wanted}
    tag_rich: dict[str, int] = {c: 0 for c in wanted}
    fresh: dict[str, int] = {c: 0 for c in wanted}
    truncated_categories: set[str] = set()

    for group, group_categories in TAG_GROUPS.items():
        selected = [c for c in group_categories if c in wanted]
        if not selected:
            continue

        query = build_query(
            city_bound, selected,
            timeout_seconds=cfg.discovery.overpass_timeout_seconds,
            element_cap=cfg.discovery.overpass_element_cap,
        )

        try:
            result = overpass(conn, query=query, cfg=cfg, force=force, session=session,
                              backoff_initial_seconds=backoff_initial_seconds)
        except DiscoveryError as exc:
            log.error("%s / %s failed: %s", city.name, group, exc)
            report.errors.append(group + ": " + str(exc))
            truncated_categories.update(selected)
            continue

        report.groups_run.append(group)
        if result.from_cache:
            report.groups_cached.append(group)
        if result.truncated:
            report.groups_truncated.append(group)
            truncated_categories.update(selected)
            log.error("%s / %s hit the element cap: coverage for %s is UNKNOWN until it is "
                      "re-run with a narrower bound", city.name, group, ", ".join(selected))

        records = parse_elements(
            result.elements, city_name=city.name, city_slug=city.slug,
        )

        with db.transaction(conn):
            for record in records:
                if record.is_landuse and _LANDUSE_IS_NOT_A_BUSINESS:
                    # An industrial landuse polygon is an estate, not a business. It is a
                    # geographic hint and nothing else: not counted, never inserted.
                    continue

                # A landuse polygon is neither found nor kept: it is a geographic hint and
                # counting it would deflate the coverage percentage with something that was
                # never a business.
                report.elements_found += 1

                # A group query also returns neighbours of the categories we asked for - a
                # clinic inside G1_HEALTH, a bank inside G8. Those are real rows, but they are
                # not part of any requested category's coverage arithmetic.
                bucket = record.category if record.category in found else None
                if bucket is not None:
                    found[bucket] += 1

                if not record.is_business:
                    continue

                if bucket is not None:
                    kept[bucket] += 1
                    if record.tag_rich:
                        tag_rich[bucket] += 1

                report.elements_kept += 1
                try:
                    _, is_new, contacts = _upsert_business(
                        conn, campaign_id=campaign_id, record=record,
                        requested_categories=wanted,
                        requested_industries=requested_industries,
                        actor=DISCOVERY_ACTOR,
                    )
                except ValueError as exc:
                    # business_key refused it: no name, no domain, no mobile. Not a business.
                    log.debug("skipping %s: %s", record.osm_ref, exc)
                    report.elements_kept -= 1
                    if bucket is not None:
                        kept[bucket] -= 1
                        if record.tag_rich:
                            tag_rich[bucket] -= 1
                    continue

                report.contacts_added += contacts
                if is_new:
                    report.businesses_new += 1
                    if bucket is not None:
                        fresh[bucket] += 1
                else:
                    report.businesses_rediscovered += 1

    with db.transaction(conn):
        for category in sorted(wanted):
            kept_count = kept[category]
            rich_pct = (
                _round_half_up(100.0 * tag_rich[category] / kept_count) if kept_count else None
            )
            assessment = coverage_confidence(
                city, category, found[category],
                kept=kept_count, businesses_new=fresh[category], tag_rich_pct=rich_pct,
                truncated=category in truncated_categories, bound=city_bound,
            )
            report.coverage.append(assessment)
            _write_coverage(conn, campaign_id, assessment)
            log.info("%s", assessment.note)

        if report.businesses_new:
            conn.execute(
                "UPDATE campaigns SET n_discovered = n_discovered + ?,"
                "       updated_at = ? WHERE id = ?",
                (report.businesses_new, utc_now(), campaign_id),
            )

        audit(conn, DISCOVERY_ACTOR, "CAMPAIGN_STARTED", "campaigns", campaign_id,
              campaign_id=campaign_id,
              detail={
                  "stage": "DISCOVER",
                  "city_slug": city.slug,
                  "bound": city_bound.kind,
                  "bound_source": city_bound.source,
                  "groups_run": report.groups_run,
                  "groups_cached": report.groups_cached,
                  "groups_truncated": report.groups_truncated,
                  "elements_found": report.elements_found,
                  "elements_kept": report.elements_kept,
                  "businesses_new": report.businesses_new,
              })

    log.info("%s", report.summary())
    return report


def _campaign_targets(conn: sqlite3.Connection, campaign_id: str, cfg: Config) -> list[City]:
    """The places this campaign actually named, as City records discovery already understands.

    Joins campaign_cities to the locations cache so a place resolved once at campaign-creation
    time does not need a second trip to Nominatim: a stored OSM relation id goes straight into
    City.osm_relation_id, which resolve_city() then uses without any network call at all.
    """
    try:
        rows = conn.execute(
            "SELECT cc.city, cc.city_slug, cc.state_region,"
            "       l.osm_type, l.osm_id, l.display_name"
            "  FROM campaign_cities cc"
            "  LEFT JOIN locations l ON l.slug = cc.city_slug"
            " WHERE cc.campaign_id = ?"
            " ORDER BY cc.ordinal",
            (campaign_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        # The locations cache is created on demand by radar/locations.py; a database that has
        # never seen a place search simply has no such table yet.
        rows = conn.execute(
            "SELECT city, city_slug, state_region, NULL osm_type, NULL osm_id, NULL display_name"
            "  FROM campaign_cities WHERE campaign_id = ? ORDER BY ordinal",
            (campaign_id,),
        ).fetchall()

    out: list[City] = []
    for r in rows:
        out.append(City(
            slug=r["city_slug"],
            name=r["city"],
            state_region=r["state_region"] or "",
            nominatim_query=r["display_name"] or r["city"],
            osm_relation_id=int(r["osm_id"]) if r["osm_type"] == "relation" and r["osm_id"] else None,
        ))
    if out:
        return out
    log.info("campaign %s named no locations; falling back to config.yaml cities", campaign_id)
    return list(cfg.cities)


def _campaign_categories(conn: sqlite3.Connection, campaign_id: str, cfg: Config) -> list[str]:
    """The categories the campaign asked for, or everything configured if it asked for none."""
    row = conn.execute(
        "SELECT categories FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if row and row["categories"]:
        try:
            wanted = [c for c in json.loads(row["categories"]) if c]
            if wanted:
                return wanted
        except (ValueError, TypeError):
            log.warning("campaign %s has unreadable categories; using the configured list",
                        campaign_id)
    return list(cfg.categories)


def discover_campaign(
    conn: sqlite3.Connection,
    campaign_id: str,
    *,
    cfg: Config,
    cities: Sequence[City] | None = None,
    categories: Sequence[str] | None = None,
    force: bool = False,
) -> list[CityDiscovery]:
    """Run discovery over the campaign's own locations. One session, reusing connections politely.

    The campaign's `campaign_cities` rows win over `cfg.cities`. That ordering is the whole point
    of the free-text location search: a campaign created for Pune must search Pune, not whatever
    four towns happen to be pinned in config.yaml. Falling back to the configured list only when a
    campaign named no locations of its own keeps the older config-driven path working.
    """
    targets = list(cities) if cities is not None else _campaign_targets(conn, campaign_id, cfg)
    wanted = list(categories if categories is not None else _campaign_categories(conn, campaign_id, cfg))
    if not targets:
        raise DiscoveryError(
            "this campaign has no locations, and no cities: list is configured. "
            "Create it with:  main.py campaign new --locations \"<place>\""
        )

    out: list[CityDiscovery] = []
    with requests.Session() as session:
        for city in targets:
            try:
                out.append(discover_city(
                    conn, campaign_id, city, wanted, cfg=cfg, force=force, session=session,
                ))
            except DiscoveryError as exc:
                log.error("discovery failed for %s: %s", city.name, exc)
                out.append(CityDiscovery(
                    campaign_id=campaign_id, city_slug=city.slug, city_name=city.name,
                    bound=CityBound(slug=city.slug, name=city.name, kind="RADIUS",
                                    source="UNRESOLVED"),
                    errors=[str(exc)],
                ))
    return out
