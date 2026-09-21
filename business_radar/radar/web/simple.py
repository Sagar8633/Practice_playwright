"""One page that does the whole research half, so nobody has to open a terminal.

Without this the product is two tools pretending to be one: a web app for verifying and approving,
and a command line for finding and researching. Sagar has to know that `discover` comes before
`research`, that both take a campaign id he has to copy from somewhere, and that neither reports
progress anywhere he can see it. That is a fine shape for a cron job and a bad one for the thing
he opens on a Tuesday evening.

This module collapses it to: type a place, tick what kind of business, press Find. Everything
after that - resolving the place against OpenStreetMap, discovering, researching, scoring,
generating the report - happens in one background thread that writes its progress somewhere the
page can poll.

It adds no capability. Every route here calls the same functions the CLI calls, and the safety
model is untouched: this page can research and it can report, and it cannot verify, draft, approve
or send. Those stay where they were, one deliberate click at a time.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for

from radar import ids, locations
from radar.db import connect, transaction
from radar.models import utc_now

log = logging.getLogger("radar.web.simple")

bp = Blueprint("simple", __name__)

# What most people actually want to search for, in the order they think of them. The full
# category list lives in radar/models.py; this is the short menu, and "Everything" falls back to
# the campaign's configured set.
QUICK_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("HOSPITAL", "Hospitals & clinics"),
    ("DIAGNOSTIC_CENTER", "Diagnostic centres"),
    ("SCHOOL", "Schools"),
    ("COLLEGE", "Colleges"),
    ("MANUFACTURER", "Manufacturers"),
    ("DISTRIBUTOR", "Distributors"),
    ("VEHICLE_DEALER", "Vehicle dealers"),
    ("GARAGE", "Garages"),
    ("HOTEL", "Hotels"),
    ("RESTAURANT", "Restaurants"),
    ("BAKERY", "Bakeries"),
    ("RETAIL_STORE", "Shops & retail"),
    ("REAL_ESTATE_AGENCY", "Estate agents"),
)


@dataclass
class Progress:
    """What a run is doing, in words a person can read while waiting."""
    campaign_id: str = ""
    place: str = ""
    stage: str = "idle"           # resolving | discovering | researching | reporting | done | error
    message: str = ""
    found: int = 0
    researched: int = 0
    failed: int = 0
    total: int = 0
    report_path: str = ""
    error: str = ""
    started_at: float = field(default_factory=time.monotonic)

    @property
    def percent(self) -> int:
        if self.stage == "done":
            return 100
        if self.stage in ("idle", "resolving"):
            return 2
        if self.stage == "discovering":
            return 12
        if self.stage == "reporting":
            return 95
        if self.total:
            return min(94, 15 + int(78 * (self.researched + self.failed) / self.total))
        return 15

    @property
    def running(self) -> bool:
        return self.stage not in ("idle", "done", "error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id, "place": self.place, "stage": self.stage,
            "message": self.message, "found": self.found, "researched": self.researched,
            "failed": self.failed, "total": self.total, "percent": self.percent,
            "running": self.running, "report_path": self.report_path, "error": self.error,
            "elapsed": int(time.monotonic() - self.started_at),
        }


#: One run at a time, deliberately. Two concurrent runs would race the same Overpass and Gemini
#: allowances and neither would finish sooner.
_state: dict[str, Progress] = {"current": Progress()}
_lock = threading.Lock()


def current() -> Progress:
    with _lock:
        return _state["current"]


def _run(cfg, db_path, campaign_id: str, place_query: str, categories: list[str],
         limit: int, user_id: str) -> None:
    """The whole research half, in one thread, reporting as it goes."""
    from radar.discover import discover_campaign
    from radar.llm import GeminiClient, QuotaExhausted
    from radar.report import generate_report
    from radar.research import research_and_score

    p = current()
    conn = connect(db_path)
    try:
        p.stage, p.message = "discovering", f"Searching OpenStreetMap around {p.place}"
        results = discover_campaign(conn, campaign_id, cfg=cfg)
        found = 0
        for r in results:
            kept = getattr(r, "kept", None)
            found += len(kept) if isinstance(kept, list) else (getattr(r, "n_discovered", 0) or 0)
        p.found = found
        log.info("simple run: discovered %d", found)

        rows = conn.execute(
            "SELECT b.id, b.name FROM businesses b"
            "  JOIN campaign_businesses cb ON cb.business_id = b.id"
            " WHERE cb.campaign_id = ? AND b.status = 'AI_RESEARCHED'"
            " ORDER BY b.created_at",
            (campaign_id,),
        ).fetchall()
        if limit:
            rows = rows[:limit]
        p.total = len(rows)

        if rows:
            client = GeminiClient(cfg.llm, conn)
            p.stage = "researching"
            for i, row in enumerate(rows, 1):
                name = row["name"] or row["id"]
                p.message = f"Researching {name}  ({i} of {len(rows)})"
                try:
                    research_and_score(conn, row["id"], client=client, cfg=cfg,
                                       campaign_id=campaign_id, actor=user_id)
                    p.researched += 1
                except QuotaExhausted:
                    p.message = (f"Daily free allowance used up after {p.researched}. "
                                 "Nothing is lost - continue tomorrow.")
                    log.warning("simple run: quota exhausted after %d", p.researched)
                    break
                except Exception as exc:                                # noqa: BLE001
                    p.failed += 1
                    log.warning("simple run: %s failed: %s", name, exc)

        p.stage, p.message = "reporting", "Building your report"
        path = generate_report(conn, campaign_id, user_id=user_id)
        p.report_path = str(path)
        p.stage = "done"
        p.message = (f"Done. {p.found} found, {p.researched} researched"
                     + (f", {p.failed} could not be researched" if p.failed else "") + ".")
        log.info("simple run finished: %s", p.message)
    except Exception as exc:                                            # noqa: BLE001
        p.stage, p.error = "error", str(exc)
        p.message = "Something went wrong."
        log.exception("simple run failed")
    finally:
        conn.close()


@bp.before_request
def _require_login() -> Any:
    """Guard every route in this blueprint.

    A before_request on the blueprint rather than app.py's `login_required` decorator, because
    app.py imports this module to register it - importing back the other way would be circular.
    The check is the same one: no live session, no access.
    """
    if getattr(g, "session_obj", None) is None:
        return redirect(url_for("login", next=request.path))
    return None


#: Offered in the dropdown. Nominatim searches the whole planet regardless - this is a
#: convenience so the common cases need no typing, not a restriction.
COUNTRIES: tuple[str, ...] = (
    "India", "United Kingdom", "United States", "United Arab Emirates", "Australia",
    "Canada", "Germany", "Ireland", "Kenya", "Malaysia", "Netherlands", "New Zealand",
    "Nigeria", "Philippines", "Singapore", "South Africa", "Sri Lanka", "Bangladesh",
    "Nepal", "Other",
)


@bp.route("/start", methods=["GET"])
def start() -> Any:
    return render_template("simple_start.html",
                           countries=COUNTRIES,
                           categories=QUICK_CATEGORIES,
                           progress=current().to_dict())


@bp.route("/start", methods=["POST"])
def start_run() -> Any:
    p = current()
    if p.running:
        return redirect(url_for("simple.start"))

    # Country + city, joined into one query. Nominatim reads "Nashik, India" perfectly well,
    # and the dropdown exists only so the common case needs no typing.
    city = (request.form.get("city") or request.form.get("place") or "").strip()
    country = (request.form.get("country") or "").strip()
    if country and country != "Other" and country.lower() not in city.lower():
        place_query = f"{city}, {country}"
    else:
        place_query = city

    # No category picker and no limit box any more: search everything, research a sensible
    # first batch. Someone who wants to narrow it can still do so from the campaign page.
    categories = [key for key, _label in QUICK_CATEGORIES]
    limit = 25

    if not city:
        fresh = Progress(stage="error", error="Type a town or city first.",
                         message="Type a town or city first.")
        with _lock:
            _state["current"] = fresh
        return redirect(url_for("simple.start"))

    fresh = Progress(place=place_query, stage="resolving",
                     message=f"Looking up {place_query}")
    with _lock:
        _state["current"] = fresh

    try:
        place, bound = locations.resolve_to_bound(place_query, cfg=g.config, conn=g.conn)
    except locations.LocationError as exc:
        fresh.stage, fresh.error, fresh.message = "error", str(exc), str(exc)
        return redirect(url_for("simple.start"))

    fresh.place = place.label
    campaign_id = ids.new_id("cmp")
    name = f"{place.name} - {utc_now()[:10]}"
    import json as _json
    with transaction(g.conn):
        g.conn.execute(
            "INSERT INTO campaigns (id, name, slug, created_by, created_at, status,"
            " categories, industries, size_filter, min_opportunity_score, research_depth)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (campaign_id, name, f"{bound.slug}-{campaign_id[-6:].lower()}",
             g.session_obj.id, utc_now(), "DRAFT",
             _json.dumps(categories), _json.dumps([]), _json.dumps([]), 0, "STANDARD"),
        )
        g.conn.execute(
            "INSERT INTO campaign_cities (campaign_id, city, city_slug, state_region, ordinal)"
            " VALUES (?,?,?,?,?)",
            (campaign_id, place.name, bound.slug,
             place.state or place.country or None, 1),
        )
    fresh.campaign_id = campaign_id

    # The thread needs its own connection, so it gets the path rather than this request's
    # connection - a sqlite3 handle must not cross threads.
    from radar.paths import DB_PATH
    t = threading.Thread(
        target=_run,
        args=(g.config, DB_PATH, campaign_id, place_query, categories, limit, g.session_obj.id),
        daemon=True, name="radar-simple-run",
    )
    t.start()
    return redirect(url_for("simple.start"))


@bp.route("/start/progress")
def progress() -> Any:
    return jsonify(current().to_dict())


@bp.route("/start/places")
def places() -> Any:
    """Live place suggestions for the search box."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 3:
        return jsonify([])
    try:
        found = locations.search(q, cfg=g.config, conn=g.conn, limit=6)
    except locations.LocationError as exc:
        return jsonify({"error": str(exc)}), 200
    return jsonify([{"label": p.label, "query": p.display_name,
                     "type": p.place_type} for p in found])
