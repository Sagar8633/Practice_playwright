"""Free-text place search, so a campaign is not limited to the cities someone pinned in a config file.

Without this module a campaign can only run against the handful of cities in `config.yaml`, each
one needing a human to look up an OSM relation id and paste it in. That was tolerable while the
target was four towns in Maharashtra. It stops being tolerable the moment the question becomes
"what about Pune, or Surat, or Leeds" - because the answer would be "edit a YAML file, find a
relation id on openstreetmap.org, restart".

Nominatim already searches the whole planet and Overpass already holds the whole planet's business
data. The only thing missing was a way to turn what somebody typed into a bound Overpass can use.
That is all this module does: search, disambiguate, cache, and hand back a `CityBound` that the
existing discovery path accepts without knowing anything changed.

Two things it deliberately does NOT do. It does not bulk-geocode - Nominatim's usage policy is one
request per second with an identifying User-Agent, and a tool that ignores that gets the whole
project's IP blocked for everybody. And it does not silently pick the first match: "Springfield"
is a real question, not a typo, so ambiguity is returned to the caller rather than guessed at.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Any, Iterable

import requests

from .config import Config
from .discover import AREA_ID_BASE, DEFAULT_RADIUS_M, CityBound
from .ids import new_id
from .models import utc_now

log = logging.getLogger("radar.locations")

# Nominatim's usage policy. Not a suggestion - exceeding it gets the IP blocked.
_MIN_INTERVAL_S = 1.0
_last_call: float = 0.0

# Place types worth searching for businesses in. A country or a continent is a valid Nominatim
# result and a catastrophic Overpass query, so they are refused with an explanation rather than
# accepted and left to time out after ninety seconds.
_TOO_BIG = {"country", "continent"}
_USABLE_CLASSES = {"boundary", "place"}


class LocationError(RuntimeError):
    """A place could not be resolved into something Overpass can be pointed at."""


class LocationTooBroad(LocationError):
    """The place is real but too large to search in one pass."""


@dataclass(slots=True)
class Place:
    """One candidate answer to what somebody typed.

    `display_name` is Nominatim's full comma-separated path ("Pune, Pune District, Maharashtra,
    India"), which is what makes disambiguation possible: two places called Shirpur are
    distinguishable by their parents, not by their names.
    """
    query: str
    display_name: str
    name: str
    osm_type: str                   # node | way | relation
    osm_id: int
    place_class: str                # boundary | place | ...
    place_type: str                 # city | town | village | administrative | suburb | ...
    lat: float
    lon: float
    country: str | None = None
    country_code: str | None = None
    state: str | None = None
    importance: float = 0.0
    bbox: tuple[float, float, float, float] | None = None

    @property
    def slug(self) -> str:
        """A stable, filesystem- and URL-safe key for this exact place.

        Built from the OSM type and id rather than the name, because two different Shirpurs must
        not collide in the cache, in a filename, or in a campaign_cities row.
        """
        base = "".join(c if c.isalnum() else "-" for c in self.name.lower()).strip("-")
        base = "-".join(p for p in base.split("-") if p)
        return f"{base or 'place'}-{self.osm_type[0]}{self.osm_id}"

    @property
    def is_area(self) -> bool:
        """True when this place has a real boundary Overpass can use as an area."""
        return self.osm_type == "relation" and self.place_class in _USABLE_CLASSES

    @property
    def label(self) -> str:
        """What to show in a picker: the name, then enough of the path to disambiguate it."""
        parts = [p.strip() for p in self.display_name.split(",")]
        tail = [p for p in parts[1:] if p][-2:]
        return self.name + (" — " + ", ".join(tail) if tail else "")

    @property
    def approx_km(self) -> float | None:
        """Rough width of the bounding box in km, for the too-big check and for the UI."""
        if not self.bbox:
            return None
        south, north, west, east = self.bbox
        return max(abs(north - south), abs(east - west)) * 111.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["slug"] = self.slug
        d["label"] = self.label
        d["is_area"] = self.is_area
        d["approx_km"] = self.approx_km
        return d

    @classmethod
    def from_nominatim(cls, query: str, row: dict[str, Any]) -> "Place":
        addr = row.get("address") or {}
        bbox = None
        raw = row.get("boundingbox")
        if raw and len(raw) == 4:
            try:
                bbox = (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
            except (TypeError, ValueError):
                bbox = None
        return cls(
            query=query,
            display_name=row.get("display_name", ""),
            name=row.get("name") or (row.get("display_name", "").split(",")[0].strip()),
            osm_type=row.get("osm_type", ""),
            osm_id=int(row.get("osm_id") or 0),
            place_class=row.get("class", ""),
            place_type=row.get("type", ""),
            lat=float(row.get("lat", 0.0)),
            lon=float(row.get("lon", 0.0)),
            country=addr.get("country"),
            country_code=(addr.get("country_code") or "").upper() or None,
            state=addr.get("state") or addr.get("region"),
            importance=float(row.get("importance") or 0.0),
            bbox=bbox,
        )


def _throttle() -> None:
    """Hold the caller to Nominatim's one-request-per-second policy."""
    global _last_call
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the location cache if it is not there yet.

    Done here rather than in a migration because this table is a cache: it can be dropped and
    rebuilt from the network at any time, and nothing references it by foreign key.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS locations (
            id            TEXT PRIMARY KEY,
            slug          TEXT NOT NULL UNIQUE,
            query         TEXT NOT NULL,
            display_name  TEXT NOT NULL,
            name          TEXT NOT NULL,
            osm_type      TEXT NOT NULL,
            osm_id        INTEGER NOT NULL,
            place_class   TEXT NOT NULL,
            place_type    TEXT NOT NULL,
            lat           REAL NOT NULL,
            lon           REAL NOT NULL,
            country       TEXT,
            country_code  TEXT,
            state         TEXT,
            bbox_json     TEXT,
            resolved_at   TEXT NOT NULL,
            UNIQUE (osm_type, osm_id)
        );
        CREATE INDEX IF NOT EXISTS ix_locations_query ON locations(query);
        CREATE TABLE IF NOT EXISTS location_searches (
            query       TEXT PRIMARY KEY,
            results     TEXT NOT NULL,
            searched_at TEXT NOT NULL
        );
        """
    )


def search(
    query: str,
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
    limit: int = 8,
    session: requests.Session | None = None,
    use_cache: bool = True,
) -> list[Place]:
    """Search the planet for a place name and return the candidates, best first.

    Returns a list rather than one answer on purpose. "Shirpur" matches a town in Dhule district
    and a village in Rajasthan; picking one silently is how a campaign ends up researching
    businesses 900 km from where its owner meant.
    """
    q = " ".join(query.split()).strip()
    if len(q) < 2:
        raise LocationError("Enter at least two characters to search for a place.")

    if conn is not None and use_cache:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT results FROM location_searches WHERE query = ?", (q.lower(),)
        ).fetchone()
        if row:
            log.debug("Location search %r served from cache", q)
            return [Place(**{k: (tuple(v) if k == "bbox" and v else v)
                             for k, v in r.items() if k in Place.__slots__})
                    for r in json.loads(row["results"])]

    sess = session or requests.Session()
    _throttle()
    endpoint = getattr(cfg.discovery, "nominatim_endpoint", "https://nominatim.openstreetmap.org/search")
    if not endpoint.rstrip("/").endswith("/search"):
        endpoint = endpoint.rstrip("/") + "/search"

    try:
        resp = sess.get(
            endpoint,
            params={
                "q": q,
                "format": "jsonv2",
                "limit": str(max(1, min(limit, 20))),
                "addressdetails": "1",
                "accept-language": "en",
            },
            headers={"User-Agent": cfg.discovery.user_agent},
            timeout=getattr(cfg.discovery, "nominatim_timeout_seconds", 20),
        )
        resp.raise_for_status()
        rows = resp.json()
    except requests.RequestException as exc:
        raise LocationError(f"Could not reach the place search service: {exc}") from exc
    except ValueError as exc:
        raise LocationError("The place search service returned something unreadable.") from exc

    places = [Place.from_nominatim(q, r) for r in rows if r.get("osm_id")]
    # Keep things a business search makes sense in. A river or a mountain is a real Nominatim
    # result and a meaningless place to look for hospitals.
    places = [p for p in places if p.place_class in _USABLE_CLASSES or p.place_type in {
        "city", "town", "village", "suburb", "municipality", "administrative", "county",
        "state_district", "district", "region", "hamlet", "neighbourhood", "borough",
    }]

    if conn is not None and use_cache and places:
        payload = json.dumps([p.to_dict() for p in places], ensure_ascii=False)
        with conn:
            conn.execute(
                "INSERT INTO location_searches (query, results, searched_at) VALUES (?,?,?) "
                "ON CONFLICT(query) DO UPDATE SET results=excluded.results, searched_at=excluded.searched_at",
                (q.lower(), payload, utc_now()),
            )
    log.info("Location search %r -> %d candidate(s)", q, len(places))
    return places


def resolve_one(
    query: str,
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
    session: requests.Session | None = None,
) -> Place:
    """Search, and return a single place - raising if the answer is genuinely ambiguous.

    Used by the CLI, where there is no picker. The rule is deliberately strict: accept the top
    match only when it is clearly ahead of the runner-up, otherwise make the human choose.
    """
    places = search(query, cfg=cfg, conn=conn, session=session, limit=8)
    if not places:
        raise LocationError(
            f"No place found matching {query!r}. Try adding a region or country, "
            f"for example 'Nashik, Maharashtra, India'."
        )
    if len(places) > 1:
        top, second = places[0], places[1]
        # Nominatim's importance is a reasonable tiebreak, but only when the gap is real.
        if top.importance - second.importance < 0.05:
            options = "\n".join(f"    - {p.label}" for p in places[:5])
            raise LocationError(
                f"{query!r} is ambiguous. Be more specific - one of:\n{options}"
            )
    return places[0]


def remember(conn: sqlite3.Connection, place: Place) -> str:
    """Store a chosen place so a campaign can reference it, and return its id."""
    ensure_schema(conn)
    existing = conn.execute(
        "SELECT id FROM locations WHERE osm_type = ? AND osm_id = ?",
        (place.osm_type, place.osm_id),
    ).fetchone()
    if existing:
        return existing["id"]
    # "loc" is not in ids.PREFIXES - this table is a cache created outside the migration
    # sequence, so it borrows the ULID body from a registered prefix rather than widening the
    # registry for something no foreign key points at.
    loc_id = "loc_" + new_id("cmp").split("_", 1)[1]
    with conn:
        conn.execute(
            "INSERT INTO locations (id, slug, query, display_name, name, osm_type, osm_id,"
            " place_class, place_type, lat, lon, country, country_code, state, bbox_json, resolved_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                loc_id, place.slug, place.query, place.display_name, place.name,
                place.osm_type, place.osm_id, place.place_class, place.place_type,
                place.lat, place.lon, place.country, place.country_code, place.state,
                json.dumps(place.bbox) if place.bbox else None, utc_now(),
            ),
        )
    log.info("Remembered location %s (%s)", place.label, loc_id)
    return loc_id


def bound_for(place: Place, *, radius_m: int = DEFAULT_RADIUS_M, max_km: float = 120.0) -> CityBound:
    """Turn a chosen place into the bound the existing discovery path already understands.

    A relation becomes an Overpass area, which is exact. Anything else becomes a radius around
    the point, which is a judgement call - and `CityBound.source` records which of the two
    happened so a coverage figure is never read as more precise than it is.
    """
    width = place.approx_km
    if place.place_type in _TOO_BIG or (width is not None and width > max_km * 8):
        raise LocationTooBroad(
            f"{place.label} is too large to search in one pass "
            f"({'a ' + place.place_type if place.place_type else 'about ' + str(int(width or 0)) + ' km across'}). "
            f"Search a city or district inside it instead."
        )

    if place.is_area:
        return CityBound(
            slug=place.slug,
            name=place.name,
            kind="AREA",
            area_id=AREA_ID_BASE + int(place.osm_id),
            source="NOMINATIM_AREA",
            display_name=place.display_name,
        )

    # No boundary relation: fall back to a circle, sized from the bounding box where there is one
    # so a large town is not searched with a small-village radius.
    r = radius_m
    if width:
        r = int(max(radius_m, min(width * 1000 / 2, max_km * 1000)))
    return CityBound(
        slug=place.slug,
        name=place.name,
        kind="RADIUS",
        lat=place.lat,
        lon=place.lon,
        radius_m=r,
        source="NOMINATIM_RADIUS",
        display_name=place.display_name,
    )


def resolve_to_bound(
    query: str,
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
    session: requests.Session | None = None,
) -> tuple[Place, CityBound]:
    """The one call the CLI and the web app both want: text in, searchable bound out."""
    place = resolve_one(query, cfg=cfg, conn=conn, session=session)
    bound = bound_for(place)
    if conn is not None:
        remember(conn, place)
    return place, bound


def describe(places: Iterable[Place]) -> str:
    """Render candidates for a terminal picker."""
    lines = []
    for i, p in enumerate(places, 1):
        kind = "boundary" if p.is_area else "point"
        width = p.approx_km
        extent = f", ~{width:.0f} km across" if width else ""
        lines.append(f"  {i:>2}. {p.label}  [{p.place_type}, {kind}{extent}]")
    return "\n".join(lines)
