"""The screens Sagar actually clicks, and the one place a decision becomes a row.

Without this module business_radar is a research pipeline with no gate: it would discover,
score and draft, and then either do nothing or - much worse - send. Spec section 45's sequence
is RESEARCH -> REPORT -> VERIFY -> SELECT -> PERSONALIZE -> PREVIEW -> CONFIRM -> SEND, and
five of those eight steps are a person reading a screen. These are the screens.

Three rules hold across every route here and are worth stating before the code:

  * The send control exists in exactly one template, templates/outreach/confirm_dialog.html.
    Not disabled elsewhere - absent. A greyed-out control that becomes live under some
    condition is a permanent invitation, and the day the condition is met by accident is the
    day something goes out that nobody decided to send.
  * Every gate is re-evaluated inside the request that acts, never trusted from the request
    that drew the page. A tab can be open for fourteen hours; an opt-out can arrive in hour
    thirteen.
  * A metric with no rows behind it renders as an em dash, never as zero. "Won: 0" invites
    "we tried and lost"; "Won: -" says "this has not got that far".

SIMPLIFIED: 13-api-endpoints.md specifies a JSON API under /api/v1 with SSE progress streams,
and 15-ui-wireframe.md adds /suppressions, /compare and /reports/daily. This is the server-
rendered core loop: campaigns, business detail, verification, selection, preview, confirm, send,
handoffs and channel settings. Adding the API later is additive - the queries it would serve are
already in radar/web/queries.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import (Flask, abort, flash, g, redirect, render_template, request, session,
                   url_for)

from radar import audit as audit_mod
from radar import db as db_mod
from radar import ids
from radar import locations
from radar.audit import hash_address, mask_address
from radar.config import Config, load_config, setup_logging
from radar.db import transaction
from radar.models import (CATEGORIES, INDUSTRIES, SIZE_BANDS, VERIFICATION_CHECK_KEYS,
                          ContactPolicy, band_for_score, parse_ts, utc_now)
from radar.paths import DB_PATH, DATA_DIR, ensure
from radar.web import channels as channels_mod
from radar.web import compose, eligibility, queries, security, transmit

log = logging.getLogger("radar.web.app")

#: Rendered verbatim in the confirm dialog and written verbatim to
#: outreach_approvals.confirmation_text, so an audit two years from now reads exactly what the
#: operator was shown. Spec section 28 fixes the wording; nothing may paraphrase it.
CONFIRMATION_TEXT = (
    "You are about to contact this business using the selected business contact."
)

#: Labels that must never appear on a control anywhere in this app. A tool whose button says
#: "Send all" is a different tool from the one this design describes.
FORBIDDEN_BUTTON_TEXT: tuple[str, ...] = (
    "auto send", "send all", "send now to all", "blast", "auto-send",
)

#: The nine checks, in ask order, with the prompt each one asks. The keys come from
#: radar/models.py so that this list cannot drift from the CHECK constraint.
CHECKLIST: tuple[tuple[str, str, str], ...] = (
    ("IDENTITY_CORRECT", "Business identity appears correct",
     "Name, address and website belong to one real business."),
    ("IN_TARGET_CITY", "Business is located in the target city",
     "The address is in the city this campaign is searching."),
    ("CATEGORY_CORRECT", "Business category is correct",
     "The category above matches what the business actually does."),
    ("APPEARS_OPERATIONAL", "Business appears operational",
     "Recent evidence that it is trading, not closed or dormant."),
    ("CONTACT_LEGITIMATE", "Contact information appears to be a legitimate business contact",
     "A published business address, not a personal one scraped from somewhere."),
    ("RESEARCH_RELEVANT", "Research is relevant",
     "The findings are about this business and are worth acting on."),
    ("OPPORTUNITY_REASONABLE", "Software opportunity appears reasonable",
     "The problem named is one this business plausibly has."),
    ("OUTREACH_APPROPRIATE", "Outreach is appropriate",
     "Approaching this business about software is a reasonable thing to do."),
    ("NO_DNC_RECORD", "No do-not-contact record exists",
     "Nothing on the suppression list, and no prior refusal."),
)

if tuple(k for k, _p, _h in CHECKLIST) != VERIFICATION_CHECK_KEYS:  # pragma: no cover
    raise RuntimeError(
        "the checklist on screen has drifted from radar/models.py VERIFICATION_CHECK_KEYS, "
        "which is the same list the verification_checks CHECK constraint enforces"
    )

_SLUG_RE = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# the app factory
# ---------------------------------------------------------------------------

def create_app(config: Config | None = None, db_path: Path | None = None) -> Flask:
    """Build the Flask app. One process, one SQLite file, one operator."""
    ensure()
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["RADAR_CONFIG"] = config
    app.config["RADAR_DB_PATH"] = Path(db_path) if db_path else DB_PATH
    app.secret_key = _secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_NAME="radar_session",
        PERMANENT_SESSION_LIFETIME=security.SESSION_MAX_AGE_SECONDS,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        TEMPLATES_AUTO_RELOAD=False,
    )
    app.jinja_env.autoescape = True
    _register_filters(app)
    _register_hooks(app)
    _register_routes(app)
    # The simple one-page flow. Registered last so it cannot shadow an existing route.
    from radar.web.simple import bp as simple_bp
    app.register_blueprint(simple_bp)
    return app


def _secret_key() -> bytes:
    """A stable cookie-signing key, minted on first run and kept beside the database.

    Regenerating it on every start would log Sagar out every restart, which teaches him to
    treat the login screen as noise. It never leaves the machine, so a file next to the
    database is the right place for it.
    """
    import os

    from_env = os.environ.get("RADAR_SECRET_KEY")
    if from_env:
        return from_env.encode("utf-8")
    path = DATA_DIR / ".web_secret"
    if path.exists():
        return path.read_bytes().strip()
    key = secrets.token_bytes(48)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(key)
    tmp.replace(path)
    log.info("minted a new web session key at %s", path)
    return key


def _config(app: Flask) -> Config:
    cfg = app.config.get("RADAR_CONFIG")
    if cfg is None:
        cfg = load_config(strict=False)
        app.config["RADAR_CONFIG"] = cfg
    return cfg


# ---------------------------------------------------------------------------
# per-request plumbing
# ---------------------------------------------------------------------------

def _register_hooks(app: Flask) -> None:

    @app.before_request
    def _open_db() -> Any:
        g.conn = db_mod.connect(app.config["RADAR_DB_PATH"])
        g.config = _config(app)
        g.policy = ContactPolicy.from_row(queries.contact_policy_row(g.conn))
        g.channels = channels_mod.evaluate(g.config, g.policy)
        g.session_obj = _current_session(g.conn)

        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not security.csrf_ok(session.get("csrf"), request.form.get("csrf_token")):
                log.warning("CSRF token mismatch on %s", request.path)
                abort(400, "This form expired. Reload the page and try again.")
        return None

    @app.teardown_request
    def _close_db(_exc: BaseException | None) -> None:
        conn: sqlite3.Connection | None = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.context_processor
    def _globals() -> dict[str, Any]:
        conn = getattr(g, "conn", None)
        counts = {"handoffs": 0, "verify": 0, "tray": 0}
        if conn is not None:
            counts = {
                "handoffs": conn.execute(
                    "SELECT COUNT(*) AS n FROM handoffs WHERE state <> 'CLOSED'"
                ).fetchone()["n"],
                "verify": conn.execute(
                    "SELECT COUNT(*) AS n FROM businesses "
                    " WHERE status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')"
                ).fetchone()["n"],
                "tray": conn.execute(
                    "SELECT COUNT(*) AS n FROM selections WHERE state <> 'REMOVED'"
                ).fetchone()["n"],
            }
        return {
            "csrf_token": _csrf_token(),
            "nav_counts": counts,
            "me": getattr(g, "session_obj", None),
            "channel_status": getattr(g, "channels", {}),
            "policy": getattr(g, "policy", None),
            "CONFIRMATION_TEXT": CONFIRMATION_TEXT,
        }

    @app.errorhandler(404)
    def _not_found(_exc: Any) -> Any:
        return render_template("error.html", code=404,
                               sentence="There is no such page."), 404

    @app.errorhandler(400)
    def _bad_request(exc: Any) -> Any:
        return render_template("error.html", code=400,
                               sentence=getattr(exc, "description",
                                                "That request could not be read.")), 400


def _csrf_token() -> str:
    token = session.get("csrf")
    if not token:
        token = security.new_csrf_token()
        session["csrf"] = token
    return token


def _current_session(conn: sqlite3.Connection) -> security.Session | None:
    user_id = session.get("uid")
    if not user_id:
        return None
    user = security.load_user(conn, user_id)
    if user is None or not user.is_active:
        session.clear()
        return None
    sid = session.get("sid") or security.new_session_id()
    session["sid"] = sid
    return security.Session(user=user, session_id=sid)


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if g.session_obj is None:
            if not security.has_usable_password(g.conn):
                return redirect(url_for("setup"))
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# template filters
# ---------------------------------------------------------------------------

def _register_filters(app: Flask) -> None:

    @app.template_filter("dash")
    def _dash(value: Any) -> str:
        """03 section 3.5: no data is not zero. A missing metric is an em dash."""
        if value is None or value == "":
            return "—"
        return str(value)

    @app.template_filter("day")
    def _day(value: Any) -> str:
        moment = parse_ts(str(value)) if value else None
        return moment.strftime("%d %b %Y") if moment else "—"

    @app.template_filter("stamp")
    def _stamp(value: Any) -> str:
        moment = parse_ts(str(value)) if value else None
        return moment.strftime("%d %b %Y %H:%M UTC") if moment else "—"

    @app.template_filter("score_tone")
    def _score_tone(score: Any) -> str:
        if score is None:
            return "mute"
        return {"HIGH": "ok", "MEDIUM": "warn", "LOW": "mute"}[band_for_score(int(score))]

    @app.template_filter("status_tone")
    def _status_tone(status: str) -> str:
        return {
            "CONTACT_READY": "ok", "VERIFIED": "ok", "INTERESTED": "ok", "DELIVERED": "ok",
            "SENT": "info", "QUEUED": "info", "APPROVED": "info", "RESPONDED": "info",
            "CONTACTED": "info", "PENDING_APPROVAL": "warn", "NEEDS_VERIFICATION": "warn",
            "AI_RESEARCHED": "warn", "PAUSED": "warn", "DRAFT": "mute", "SKIPPED": "mute",
            "REJECTED": "bad", "POLICY_BLOCKED": "bad", "BOUNCED": "bad", "FAILED": "bad",
            "HUMAN_HANDOFF": "bad", "CANCELLED": "mute",
        }.get(str(status), "mute")

    @app.template_filter("safe_url")
    def _safe_url(value: Any) -> str:
        """03 section 3.2.6: only absolute http(s) URLs become links. Everything else is text."""
        text = str(value or "")
        return text if text.startswith(("http://", "https://")) else ""

    @app.template_filter("pretty")
    def _pretty(value: Any) -> str:
        return str(value or "").replace("_", " ").title()


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------

def _register_routes(app: Flask) -> None:  # noqa: C901 - one function, one route table

    # --- first run and sign-in ---------------------------------------------

    @app.route("/setup", methods=["GET", "POST"])
    def setup() -> Any:
        """The first visit to a freshly migrated database, which has no usable password.

        001_schema.sql seeds one OWNER row whose password hash is deliberately unusable: it is
        a foreign-key anchor for approvals and audit rows, not an account. This turns it into
        one.
        """
        if security.has_usable_password(g.conn):
            return redirect(url_for("login"))
        error = ""
        if request.method == "POST":
            email = (request.form.get("email") or "").strip()
            name = (request.form.get("display_name") or "").strip() or "Sagar"
            password = request.form.get("password") or ""
            confirm = request.form.get("confirm") or ""
            if "@" not in email:
                error = "That does not look like an email address."
            elif len(password) < 8:
                error = "Use at least 8 characters."
            elif password != confirm:
                error = "The two passwords do not match."
            else:
                uid = security.owner_id(g.conn)
                if uid is None:
                    abort(500, "No OWNER row exists. The database is not migrated.")
                security.set_owner_email(g.conn, uid, email, name)
                security.set_password(g.conn, uid, password, actor=uid)
                flash("Account created. Sign in with it.", "ok")
                return redirect(url_for("login"))
        return render_template("setup.html", error=error)

    @app.route("/login", methods=["GET", "POST"])
    def login() -> Any:
        if not security.has_usable_password(g.conn):
            return redirect(url_for("setup"))
        error = ""
        if request.method == "POST":
            try:
                user = security.authenticate(
                    g.conn, request.form.get("email") or "",
                    request.form.get("password") or "",
                    client_ip=request.remote_addr,
                )
            except security.AuthError as exc:
                error = str(exc)
            else:
                session.clear()
                session.permanent = True
                session["uid"] = user.id
                session["sid"] = security.new_session_id()
                session["csrf"] = security.new_csrf_token()
                target = request.args.get("next") or url_for("index")
                return redirect(target if target.startswith("/") else url_for("index"))
        return render_template("login.html", error=error)

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout() -> Any:
        with transaction(g.conn):
            audit_mod.audit(g.conn, g.session_obj.id, "USER_LOGOUT", "users", g.session_obj.id)
        session.clear()
        return redirect(url_for("login"))

    # --- campaigns ---------------------------------------------------------

    @app.route("/")
    @app.route("/campaigns")
    @login_required
    def index() -> Any:
        status_filter = request.args.get("filter", "all")
        return render_template(
            "campaigns.html",
            campaigns=queries.campaigns(g.conn, status_filter),
            status_filter=status_filter,
            industries=sorted(INDUSTRIES),
            categories=sorted(CATEGORIES),
            size_bands=sorted(SIZE_BANDS),
            default_cities=", ".join(c.name for c in g.config.cities),
        )

    @app.route("/campaigns", methods=["POST"])
    @login_required
    def create_campaign() -> Any:
        form = request.form
        cities = [c.strip() for c in (form.get("cities") or "").split(",") if c.strip()]
        if not cities:
            flash("A campaign needs at least one city.", "bad")
            return redirect(url_for("index"))

        name = (form.get("name") or "").strip() or (
            "-".join(cities) + " - " + utc_now()[:10]
        )
        campaign_id = ids.new_id("cmp")
        slug = _slugify(name) or campaign_id
        depth = "DEEP" if form.get("research_depth") == "DEEP" else "STANDARD"
        try:
            min_score = max(0, min(100, int(form.get("min_opportunity_score") or 0)))
        except ValueError:
            min_score = 0
        cap_raw = (form.get("max_businesses") or "").strip()
        cap = int(cap_raw) if cap_raw.isdigit() and int(cap_raw) > 0 else None

        industries = [v for v in form.getlist("industries") if v in INDUSTRIES]
        categories = [v for v in form.getlist("categories") if v in CATEGORIES]
        sizes = [v for v in form.getlist("size_filter") if v in SIZE_BANDS]

        with transaction(g.conn):
            g.conn.execute(
                "INSERT INTO campaigns (id, name, slug, created_by, industries, categories, "
                "                       size_filter, min_opportunity_score, research_depth, "
                "                       max_businesses, status, notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?, 'DRAFT', ?)",
                (campaign_id, name, slug, g.session_obj.id, json.dumps(industries),
                 json.dumps(categories), json.dumps(sizes), min_score, depth, cap,
                 (form.get("notes") or "").strip() or None),
            )
            for ordinal, city in enumerate(cities):
                # Resolve what was typed against OpenStreetMap rather than just slugifying it.
                # A slug is a label; discovery needs a *bound* - an OSM area or a point and a
                # radius - and without one it has nothing to query and silently finds nothing.
                # Anything on earth is fair game here, not only the cities in config.yaml.
                try:
                    place, bound = locations.resolve_to_bound(city, cfg=g.config, conn=g.conn)
                    city_name, city_slug, region = place.name, bound.slug, (
                        place.state or place.country or "")
                except locations.LocationError as exc:
                    # Keep the row so the campaign is still coherent, but say plainly that this
                    # one will find nothing until it is resolved.
                    log.warning("could not resolve %r: %s", city, exc)
                    flash(f"{city}: {exc}", "warn")
                    city_name, city_slug, region = city, _slugify(city), ""
                g.conn.execute(
                    "INSERT INTO campaign_cities (campaign_id, city, city_slug, state_region,"
                    " ordinal) VALUES (?,?,?,?,?)",
                    (campaign_id, city_name, city_slug, region or None, ordinal),
                )
            audit_mod.audit(g.conn, g.session_obj.id, "CAMPAIGN_CREATED", "campaigns",
                            campaign_id, after={"name": name, "cities": cities},
                            campaign_id=campaign_id, route=request.path, http_method="POST")
        flash("Campaign created. Run discovery from the command line to fill it.", "ok")
        return redirect(url_for("campaign", campaign_id=campaign_id))

    @app.route("/campaigns/<campaign_id>")
    @login_required
    def campaign(campaign_id: str) -> Any:
        row = queries.campaign(g.conn, campaign_id)
        if row is None:
            abort(404)
        return render_template(
            "campaign.html",
            campaign=row,
            cities=queries.campaign_cities(g.conn, campaign_id),
            funnel=queries.campaign_funnel(g.conn, campaign_id),
            businesses=queries.campaign_businesses(g.conn, campaign_id),
        )

    # --- one business ------------------------------------------------------

    @app.route("/business/<business_id>")
    @login_required
    def business(business_id: str) -> Any:
        row = queries.business(g.conn, business_id)
        if row is None:
            abort(404)
        return render_template(
            "business.html",
            business=row,
            contacts=queries.contacts(g.conn, business_id),
            findings=queries.findings_by_kind(g.conn, business_id),
            sources=queries.sources(g.conn, business_id),
            opportunity=queries.opportunity(g.conn, business_id),
            modules=queries.modules(g.conn, business_id),
            run=queries.latest_run(g.conn, business_id),
            verification=queries.live_verification(g.conn, business_id),
            suppressions=queries.live_suppressions(g.conn, business_id),
            history=queries.outreach_history(g.conn, business_id),
        )

    @app.route("/business/<business_id>/contact/<contact_id>/confirm", methods=["POST"])
    @login_required
    def confirm_contact(business_id: str, contact_id: str) -> Any:
        """A human says this address is a real, published business contact.

        Gate E reads this column and nothing else. Research can capture an address; only a
        person can confirm one, which is the difference between a scrape and a decision.
        """
        with transaction(g.conn):
            row = g.conn.execute(
                "SELECT value_norm FROM business_contacts WHERE id = ? AND business_id = ?",
                (contact_id, business_id),
            ).fetchone()
            if row is None:
                abort(404)
            g.conn.execute(
                "UPDATE business_contacts SET human_verified = 1, human_verified_at = ?, "
                "       human_verified_by = ?, updated_at = ? WHERE id = ?",
                (utc_now(), g.session_obj.id, utc_now(), contact_id),
            )
            audit_mod.audit(
                g.conn, g.session_obj.id, "CONTACT_VERIFIED", "business_contacts", contact_id,
                business_id=business_id, route=request.path, http_method="POST",
                detail={"address_masked": mask_address(row["value_norm"]),
                        "address_sha256": hash_address(row["value_norm"])},
            )
        _refresh_contact_ready(g.conn, business_id)
        flash("Contact confirmed.", "ok")
        return redirect(url_for("business", business_id=business_id))

    @app.route("/business/<business_id>/suppress", methods=["POST"])
    @login_required
    def suppress(business_id: str) -> Any:
        """Invariant 3, from the UI side. Typed confirmation, and no code path clears it."""
        if (request.form.get("confirm_word") or "") != "SUPPRESS":
            flash("Type SUPPRESS to confirm. Nothing was changed.", "warn")
            return redirect(url_for("business", business_id=business_id))
        note = (request.form.get("note") or "").strip()
        with transaction(g.conn):
            g.conn.execute(
                "INSERT OR IGNORE INTO suppressions (id, scope, value_norm, business_id, "
                "                                    reason, source, source_ref, created_by) "
                "VALUES (?, 'BUSINESS', ?, ?, 'MANUAL', ?, ?, ?)",
                (ids.new_id("sup"), business_id, business_id,
                 "operator, /business/" + business_id, note or None, g.session_obj.id),
            )
            audit_mod.audit(g.conn, g.session_obj.id, "SUPPRESSION_CREATED", "suppressions",
                            business_id, business_id=business_id, detail={"note": note},
                            route=request.path, http_method="POST")
        flash("Suppressed permanently. The application has no code that clears this.", "ok")
        return redirect(url_for("business", business_id=business_id))

    # --- verification ------------------------------------------------------

    @app.route("/verify/<business_id>", methods=["GET"])
    @login_required
    def verify(business_id: str) -> Any:
        """The nine-item checklist.

        Opening the screen creates the DRAFT verifications row, because the dwell floor is
        measured from it server-side: a timer the browser owns is a timer the browser can lie
        about. The unique index on (business_id) WHERE state = 'DRAFT' makes reopening idempotent.
        """
        row = queries.business(g.conn, business_id)
        if row is None:
            abort(404)

        draft_row = queries.open_verification(g.conn, business_id)
        if draft_row is None:
            verification_id = ids.new_id("ver")
            with transaction(g.conn):
                g.conn.execute(
                    "INSERT INTO verifications (id, business_id, campaign_id, state, mode, "
                    "                           trigger_reason, session_id) "
                    "VALUES (?,?,?, 'DRAFT', 'FULL', 'INITIAL', ?)",
                    (verification_id, business_id, row["first_seen_campaign_id"],
                     g.session_obj.session_id),
                )
                audit_mod.audit(g.conn, g.session_obj.id, "VERIFICATION_STARTED",
                                "verifications", verification_id, business_id=business_id,
                                route=request.path, http_method="GET")
            draft_row = queries.open_verification(g.conn, business_id)

        started = parse_ts(draft_row["started_at"])
        now = parse_ts(utc_now())
        elapsed_ms = int((now - started).total_seconds() * 1000) if started and now else 0

        return render_template(
            "verify.html",
            business=row,
            verification=draft_row,
            checklist=CHECKLIST,
            answers=queries.verification_checks(g.conn, draft_row["id"]),
            findings=queries.findings_by_kind(g.conn, business_id),
            sources=queries.sources(g.conn, business_id),
            contacts=queries.contacts(g.conn, business_id),
            opportunity=queries.opportunity(g.conn, business_id),
            modules=queries.modules(g.conn, business_id),
            run=queries.latest_run(g.conn, business_id),
            suppressions=queries.live_suppressions(g.conn, business_id),
            history=queries.outreach_history(g.conn, business_id),
            reason_codes=queries.reason_codes(g.conn),
            elapsed_ms=elapsed_ms,
            queue=queries.verification_queue(g.conn, 25),
        )

    @app.route("/verify/<business_id>", methods=["POST"])
    @login_required
    def verify_submit(business_id: str) -> Any:
        """Approve, reject or skip. Every predicate the button showed is re-checked here.

        A disabled button is a suggestion; this ladder is the rule. A client that enables the
        control early lands on the same page with the sentence naming the step it skipped.
        """
        row = queries.business(g.conn, business_id)
        draft_row = queries.open_verification(g.conn, business_id)
        if row is None or draft_row is None:
            abort(404)

        action = request.form.get("action", "approve")
        why_note = (request.form.get("why_note") or "").strip()

        # A failed check must say why: the CHECK constraint refuses passed = 0 with a note
        # shorter than ten characters, so an unticked box with no explanation is recorded as
        # unanswered rather than as a considered "no". The counters follow what is stored.
        answers: dict[str, tuple[int | None, str | None]] = {}
        for key, _prompt, _helper in CHECKLIST:
            ticked = request.form.get("check_" + key) == "on"
            note = (request.form.get("note_" + key) or "").strip()
            if ticked:
                answers[key] = (1, note or None)
            elif len(note) >= 10:
                answers[key] = (0, note)
            else:
                answers[key] = (None, note or None)

        passed = sum(1 for v, _ in answers.values() if v == 1)
        failed = sum(1 for v, _ in answers.values() if v == 0)
        unanswered = len(answers) - passed - failed
        started = parse_ts(draft_row["started_at"])
        now_dt = parse_ts(utc_now())
        dwell_ms = int((now_dt - started).total_seconds() * 1000) if started and now_dt else 0
        required = int(draft_row["dwell_required_ms"])

        if action == "approve":
            problems: list[str] = []
            if unanswered or failed:
                short = unanswered + failed
                problems.append("%d check%s not ticked" % (short, "" if short == 1 else "s"))
            if len(why_note) < 15:
                problems.append("the why-note needs %d more characters"
                                % (15 - len(why_note)))
            if dwell_ms < required:
                problems.append("%ds of dwell remaining"
                                % max(1, (required - dwell_ms) // 1000))
            if queries.live_suppressions(g.conn, business_id):
                problems.append("a suppression is recorded for this business")
            if problems:
                flash(", ".join(problems).capitalize() + ".", "warn")
                return redirect(url_for("verify", business_id=business_id))

        reason_code = (request.form.get("reason_code") or "").strip() or None
        if action == "reject" and not reason_code:
            flash("Rejecting needs a reason and nothing else. Pick one.", "warn")
            return redirect(url_for("verify", business_id=business_id))

        verdict = {"approve": "VERIFIED", "reject": "REJECTED", "skip": "SKIPPED"}[action]
        stamp = utc_now()

        with transaction(g.conn):
            for ordinal, (key, _prompt, _helper) in enumerate(CHECKLIST, start=1):
                value, note = answers[key]
                answered = stamp if value is not None else None
                g.conn.execute(
                    "INSERT INTO verification_checks (id, verification_id, business_id, "
                    "        check_key, ordinal, passed, note, answered_at, answered_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(verification_id, check_key) DO UPDATE SET "
                    "        passed = excluded.passed, note = excluded.note, "
                    "        answered_at = excluded.answered_at, "
                    "        answered_by = excluded.answered_by",
                    (ids.new_id("chk"), draft_row["id"], business_id, key, ordinal,
                     value, note, answered,
                     g.session_obj.id if answered is not None else None),
                )

            # At most one live verification per business: an earlier one is superseded, not
            # left alongside, or "is this business verified" becomes ambiguous at the exact
            # moment it decides whether a message may go out.
            g.conn.execute(
                "UPDATE verifications SET superseded_at = ?, superseded_by = ?, "
                "       superseded_reason = 'REVERIFY' "
                " WHERE business_id = ? AND state = 'SUBMITTED' AND superseded_at IS NULL "
                "   AND id <> ?",
                (stamp, draft_row["id"], business_id, draft_row["id"]),
            )

            g.conn.execute(
                "UPDATE verifications SET state = 'SUBMITTED', verdict = ?, "
                "       checks_passed = ?, checks_failed = ?, why_note = ?, dwell_ms = ?, "
                "       reason_code = ?, reason_note = ?, verified_by = ?, verified_at = ?, "
                "       session_id = ? "
                " WHERE id = ?",
                (verdict, passed, failed,
                 why_note or None, dwell_ms, reason_code,
                 (request.form.get("reason_note") or "").strip() or None,
                 g.session_obj.id, stamp, g.session_obj.session_id, draft_row["id"]),
            )

            _set_status(g.conn, business_id, "NEEDS_VERIFICATION", actor_kind="SYSTEM",
                        only_from=("AI_RESEARCHED",))

            if verdict == "VERIFIED":
                g.conn.execute(
                    "UPDATE businesses SET status = 'VERIFIED', status_actor_kind = 'HUMAN', "
                    "       status_actor_user_id = ?, status_verification_id = ? "
                    " WHERE id = ? AND status = 'NEEDS_VERIFICATION'",
                    (g.session_obj.id, draft_row["id"], business_id),
                )
            elif verdict == "REJECTED":
                _set_status(g.conn, business_id, "REJECTED", actor_kind="HUMAN",
                            user_id=g.session_obj.id,
                            only_from=("AI_RESEARCHED", "NEEDS_VERIFICATION", "VERIFIED",
                                       "CONTACT_READY"))
                code = g.conn.execute(
                    "SELECT writes_suppression, suppression_reason "
                    "  FROM verification_reason_codes WHERE code = ?", (reason_code,),
                ).fetchone()
                if code is not None and code["writes_suppression"]:
                    g.conn.execute(
                        "INSERT OR IGNORE INTO suppressions (id, scope, value_norm, "
                        "        business_id, reason, source, source_ref, created_by) "
                        "VALUES (?, 'BUSINESS', ?, ?, ?, ?, ?, ?)",
                        (ids.new_id("sup"), business_id, business_id,
                         code["suppression_reason"] or "MANUAL",
                         "verification " + str(draft_row["id"]), reason_code,
                         g.session_obj.id),
                    )
                    audit_mod.audit(g.conn, g.session_obj.id, "SUPPRESSION_CREATED",
                                    "suppressions", business_id, business_id=business_id,
                                    detail={"reason_code": reason_code})
            else:
                g.conn.execute(
                    "UPDATE businesses SET status = 'SKIPPED', status_actor_kind = 'HUMAN', "
                    "       status_actor_user_id = ?, skip_reason = 'MANUAL' "
                    " WHERE id = ? AND status = 'NEEDS_VERIFICATION'",
                    (g.session_obj.id, business_id),
                )

            audit_mod.audit(
                g.conn, g.session_obj.id, "VERIFICATION_SUBMITTED", "verifications",
                draft_row["id"], business_id=business_id, route=request.path,
                http_method="POST", session_id=g.session_obj.session_id,
                client_ip=request.remote_addr,
                after={"verdict": verdict, "checks_passed": passed, "dwell_ms": dwell_ms},
            )

        if verdict == "VERIFIED":
            _refresh_contact_ready(g.conn, business_id)
            flash("Verified. " + _readiness_sentence(g.conn, business_id), "ok")
        elif verdict == "REJECTED":
            flash("Rejected, reason recorded.", "ok")
        else:
            flash("Parked. It stays in the list and can be picked up later.", "ok")
        return redirect(url_for("business", business_id=business_id))

    # --- outreach workspace ------------------------------------------------

    @app.route("/outreach")
    @login_required
    def outreach() -> Any:
        rows = queries.tray(g.conn)
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(row["city"], []).append(row)
        checks = {}
        for row in rows:
            checks[row["id"]] = eligibility.check_send_eligibility(
                g.conn, business_id=row["business_id"],
                channel=row["intent_channel"] or "EMAIL", policy=g.policy,
                channel_configured=_configured(row["intent_channel"] or "EMAIL"),
                channel_switch_on=_switch_on(row["intent_channel"] or "EMAIL"),
            )
        return render_template(
            "outreach/workspace.html",
            grouped=grouped,
            tray=rows,
            checks=checks,
            available=queries.contact_ready(g.conn),
            sent_today=queries.sent_today(g.conn),
        )

    @app.route("/outreach/select", methods=["POST"])
    @login_required
    def outreach_select() -> Any:
        """Add a CONTACT_READY business to the tray. The database refuses anything else.

        trg_no_selection_before_contact_ready is the belt to this braces: a selection row for
        an unverified business cannot be stored at all.
        """
        business_id = request.form.get("business_id") or ""
        row = queries.business(g.conn, business_id)
        if row is None:
            abort(404)
        campaign_id = row["first_seen_campaign_id"]
        if row["status"] not in ("CONTACT_READY", "CONTACTED", "RESPONDED"):
            # trg_no_selection_before_contact_ready would refuse the row anyway; catching it
            # here is the difference between a sentence and a stack trace.
            flash(_readiness_sentence(g.conn, business_id)
                  or "Only a contact-ready business may be selected.", "warn")
            return redirect(url_for("outreach"))
        check = eligibility.check_send_eligibility(
            g.conn, business_id=business_id, channel="EMAIL", policy=g.policy,
            channel_configured=_configured("EMAIL"), channel_switch_on=_switch_on("EMAIL"),
        )
        hard = check.business_blockers
        with transaction(g.conn):
            g.conn.execute(
                "INSERT INTO selections (id, campaign_id, business_id, city, industry, state, "
                "        intent_channel, eligibility_snapshot, eligible_at_select, "
                "        blocking_gate, selected_by) "
                "VALUES (?,?,?,?,?, ?, 'EMAIL', ?, ?, ?, ?)",
                (ids.new_id("sel"), campaign_id, business_id, row["city"], row["industry"],
                 "BLOCKED" if hard else "SELECTED",
                 json.dumps(check.to_dict()), 0 if hard else 1,
                 hard[0].code if hard else None, g.session_obj.id),
            )
            audit_mod.audit(g.conn, g.session_obj.id, "SELECTION_CREATED", "selections",
                            business_id, business_id=business_id, campaign_id=campaign_id,
                            route=request.path, http_method="POST")
        flash("Added to the tray." if not hard
              else "Added, but blocked: " + hard[0].sentence, "warn" if hard else "ok")
        return redirect(url_for("outreach"))

    @app.route("/outreach/<selection_id>/remove", methods=["POST"])
    @login_required
    def outreach_remove(selection_id: str) -> Any:
        with transaction(g.conn):
            row = g.conn.execute(
                "SELECT business_id, state FROM selections WHERE id = ?", (selection_id,)
            ).fetchone()
            if row is None:
                abort(404)
            if row["state"] == "DISPATCHED":
                flash("A message has already gone out for this selection.", "warn")
                return redirect(url_for("outreach"))
            g.conn.execute(
                "UPDATE selections SET state = 'REMOVED', removed_by = ?, removed_at = ?, "
                "       updated_at = ? WHERE id = ?",
                (g.session_obj.id, utc_now(), utc_now(), selection_id),
            )
            audit_mod.audit(g.conn, g.session_obj.id, "SELECTION_REMOVED", "selections",
                            selection_id, business_id=row["business_id"],
                            route=request.path, http_method="POST")
        return redirect(url_for("outreach"))

    @app.route("/outreach/prepare", methods=["POST"])
    @login_required
    def outreach_prepare() -> Any:
        """Draft a message for every selection that is still eligible.

        Nothing is sent, nothing is queued and nothing is approved. What comes out is a draft
        and a message row in PENDING_APPROVAL or POLICY_BLOCKED, which is as far as the machine
        is allowed to take it.
        """
        selection_ids = request.form.getlist("selection_id")
        rows = [r for r in queries.tray(g.conn)
                if (not selection_ids or r["id"] in selection_ids)
                and r["state"] in ("SELECTED", "PREPARED")]
        prepared, blocked = 0, 0
        for row in rows:
            try:
                _, message_status = _prepare_one(row)
            except _PrepareRefused as exc:
                blocked += 1
                flash("%s: %s" % (row["name"], exc), "warn")
                continue
            prepared += 1
            if message_status == "POLICY_BLOCKED":
                blocked += 1
        flash("Prepared %d draft%s%s." % (prepared, "" if prepared == 1 else "s",
                                          "" if not blocked else
                                          ", %d needing attention" % blocked), "ok")
        return redirect(url_for("outreach"))

    def _prepare_one(selection: sqlite3.Row) -> tuple[str, str]:
        business_id = selection["business_id"]
        channel = selection["intent_channel"] or "EMAIL"
        check = eligibility.check_send_eligibility(
            g.conn, business_id=business_id, channel=channel, policy=g.policy,
            channel_configured=_configured(channel), channel_switch_on=_switch_on(channel),
        )
        # B is about the transport, not about this business: a draft is still worth writing on
        # a laptop with no Gmail account, and doc 17 section 17.4.1 says so explicitly.
        hard = check.business_blockers
        if hard:
            raise _PrepareRefused(hard[0].sentence)

        contact = g.conn.execute(
            "SELECT * FROM business_contacts "
            " WHERE business_id = ? AND kind = ? AND is_active = 1 AND valid = 1 "
            "   AND human_verified = 1 ORDER BY is_primary DESC, captured_at LIMIT 1",
            (business_id, "EMAIL" if channel == "EMAIL" else channel),
        ).fetchone()
        if contact is None and channel != "MANUAL":
            raise _PrepareRefused(eligibility.BLOCK_REASON["E_CONTACT_MISSING"])

        biz = queries.business(g.conn, business_id)
        unsubscribe_line = _unsubscribe_line()
        composed = compose.generate(
            g.conn, business=biz, channel=channel,
            sender_name=g.config.email.from_name or "Sagar",
            sender_company="", unsubscribe_line=unsubscribe_line,
        )
        claim = compose.check_claims(
            g.conn, business_id=business_id, subject=composed.subject, body=composed.body,
            unsubscribe_marker=_unsubscribe_marker(),
            sender_name=g.config.email.from_name or "Sagar",
        )

        draft_id = ids.new_id_for("outreach_drafts")
        message_id = ids.new_id("msg")
        body_hash = _body_hash(composed.subject, composed.body)
        status = "POLICY_BLOCKED" if claim.blocked else "PENDING_APPROVAL"

        with transaction(g.conn):
            g.conn.execute(
                "INSERT INTO outreach_drafts (id, business_id, campaign_id, selection_id, "
                "        contact_id, channel, sequence_no, subject, body, model_id, "
                "        prompt_version, facts_used, inferences_used, ai_confidence, "
                "        ai_confidence_pct, policy_result, policy_detail, policy_version, "
                "        policy_checked_at, created_by) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (draft_id, business_id, selection["campaign_id"], selection["id"],
                 contact["id"] if contact else None, channel, selection["sequence_no"],
                 composed.subject or None, composed.body, composed.model_id,
                 composed.prompt_version, json.dumps(list(composed.facts_used)),
                 json.dumps(list(composed.inferences_used)), composed.confidence,
                 composed.confidence_pct, claim.result, claim.detail_json(), claim.version,
                 utc_now(), g.session_obj.id),
            )
            g.conn.execute(
                "INSERT INTO outreach_messages (id, draft_id, business_id, campaign_id, "
                "        contact_id, channel, status, sequence_no, thread_key, "
                "        to_address_norm, to_address_dedupe, to_address_display, "
                "        recipient_domain, subject_final, body_final, body_hash, "
                "        idempotency_key, eligibility_snapshot) "
                "VALUES (?,?,?,?,?,?, 'DRAFT', ?,?,?,?,?,?,?,?,?,?,?)",
                (message_id, draft_id, business_id, selection["campaign_id"],
                 contact["id"] if contact else None, channel, selection["sequence_no"],
                 business_id + ":" + channel,
                 contact["value_norm"] if contact else None,
                 contact["value_dedupe"] if contact else None,
                 contact["value_display"] if contact else None,
                 contact["domain"] if contact else None,
                 composed.subject or None, composed.body, body_hash,
                 draft_id + ":" + (contact["value_norm"] if contact else "manual"),
                 json.dumps(check.to_dict())),
            )
            g.conn.execute("UPDATE outreach_messages SET status = ? WHERE id = ?",
                           (status, message_id))
            g.conn.execute(
                "UPDATE selections SET state = 'PREPARED', updated_at = ? WHERE id = ?",
                (utc_now(), selection["id"]),
            )
            audit_mod.audit(g.conn, g.session_obj.id, "DRAFT_GENERATED", "outreach_drafts",
                            draft_id, business_id=business_id, message_id=message_id,
                            campaign_id=selection["campaign_id"],
                            detail={"model_id": composed.model_id,
                                    "prompt_version": composed.prompt_version,
                                    "facts_used": list(composed.facts_used)})
            audit_mod.audit(
                g.conn, g.session_obj.id,
                "POLICY_CHECK_BLOCKED" if claim.blocked else "POLICY_CHECK_PASSED",
                "outreach_drafts", draft_id, business_id=business_id, message_id=message_id,
                detail={"result": claim.result, "violations": list(claim.findings)},
            )
        return draft_id, status

    # --- the preview -------------------------------------------------------

    @app.route("/outreach/<draft_id>")
    @login_required
    def preview(draft_id: str) -> Any:
        """Nine panels in spec section 27's order, and the only route that renders the dialog."""
        row = queries.draft(g.conn, draft_id)
        if row is None:
            abort(404)
        business_id = row["business_id"]
        channel = row["channel"]
        check = eligibility.check_send_eligibility(
            g.conn, business_id=business_id, channel=channel, policy=g.policy,
            contact_id=row["contact_id"], channel_configured=_configured(channel),
            channel_switch_on=_switch_on(channel),
            exclude_message_id=row["message_id"],
        )
        claim_detail = json.loads(row["policy_detail"] or "{}")
        preview_token = security.new_preview_token()
        session["preview_token"] = preview_token

        # Gate B is deliberately not a blocker here. Approving is legitimate on a laptop with
        # no Gmail credentials: the approval is recorded, the message is written to
        # data/outbox/ and it is not transmitted. The dialog says so in item 3.
        blockers = list(check.business_blockers)
        if row["policy_result"] == "BLOCK":
            blockers.insert(0, eligibility.Gate(
                "K", eligibility.BLOCK,
                "The claim policy check has not passed. Read panel 8.", "K_POLICY_BLOCK",
            ))
        if row["message_status"] not in ("PENDING_APPROVAL", "APPROVED"):
            blockers.append(eligibility.Gate(
                "S", eligibility.BLOCK,
                "This message is %s." % row["message_status"], "S_WRONG_STATE",
            ))

        with transaction(g.conn):
            audit_mod.audit(g.conn, g.session_obj.id, "MESSAGE_PREVIEWED", "outreach_drafts",
                            draft_id, business_id=business_id, message_id=row["message_id"],
                            route=request.path, http_method="GET",
                            session_id=g.session_obj.session_id)

        return render_template(
            "outreach/preview.html",
            draft=row,
            findings=queries.findings_by_kind(g.conn, business_id),
            modules=queries.modules(g.conn, business_id),
            eligibility=check,
            claim_detail=claim_detail,
            blockers=blockers,
            history=queries.outreach_history(g.conn, business_id),
            preview_token=preview_token,
            unsubscribe_line=_unsubscribe_line(),
            already_approved=row["message_status"] == "APPROVED",
        )

    @app.route("/outreach/<draft_id>/edit", methods=["POST"])
    @login_required
    def preview_edit(draft_id: str) -> Any:
        """An edit re-runs the claim check. The operator cannot edit his way past a block."""
        row = queries.draft(g.conn, draft_id)
        if row is None:
            abort(404)
        if row["message_status"] not in ("DRAFT", "PENDING_APPROVAL", "POLICY_BLOCKED"):
            flash("This message has already been approved.", "warn")
            return redirect(url_for("preview", draft_id=draft_id))

        body = (request.form.get("body") or "").strip()
        subject = (request.form.get("subject") or "").strip()
        claim = compose.check_claims(
            g.conn, business_id=row["business_id"], subject=subject, body=body,
            unsubscribe_marker=_unsubscribe_marker(),
            sender_name=g.config.email.from_name or "Sagar",
        )
        body_hash = _body_hash(subject, body)
        with transaction(g.conn):
            g.conn.execute(
                "UPDATE outreach_drafts SET body_edited = ?, subject = ?, edited_by = ?, "
                "       edited_at = ?, edit_count = edit_count + 1, policy_result = ?, "
                "       policy_detail = ?, policy_checked_at = ? WHERE id = ?",
                (body, subject or None, g.session_obj.id, utc_now(), claim.result,
                 claim.detail_json(), utc_now(), draft_id),
            )
            # PENDING_APPROVAL -> DRAFT is the declared "edited, re-check required" transition.
            if row["message_status"] == "PENDING_APPROVAL":
                g.conn.execute("UPDATE outreach_messages SET status = 'DRAFT' WHERE id = ?",
                               (row["message_id"],))
            g.conn.execute(
                "UPDATE outreach_messages SET subject_final = ?, body_final = ?, "
                "       body_hash = ? WHERE id = ?",
                (subject or None, body, body_hash, row["message_id"]),
            )
            g.conn.execute(
                "UPDATE outreach_messages SET status = ? WHERE id = ?",
                ("POLICY_BLOCKED" if claim.blocked else "PENDING_APPROVAL",
                 row["message_id"]),
            )
            audit_mod.audit(g.conn, g.session_obj.id, "DRAFT_EDITED", "outreach_drafts",
                            draft_id, business_id=row["business_id"],
                            message_id=row["message_id"],
                            detail={"result": claim.result, "edit": True})
        flash("Re-checked: " + claim.result + ".", "ok" if not claim.blocked else "bad")
        return redirect(url_for("preview", draft_id=draft_id))

    # --- approve, then send -------------------------------------------------

    @app.route("/outreach/<draft_id>/approve", methods=["POST"])
    @login_required
    def approve(draft_id: str) -> Any:
        """Write the approval row. This is the only writer of outreach_approvals.

        Everything the dialog displayed is re-derived here rather than read from the form: the
        body hash, the address, the eligibility verdict and the confirmation sentence. A form
        field is a claim about what was on screen; these are the facts.
        """
        row = queries.draft(g.conn, draft_id)
        if row is None:
            abort(404)
        if not g.session_obj.may_approve:
            abort(403)
        if row["message_status"] != "PENDING_APPROVAL":
            flash("This message is %s and cannot be approved." % row["message_status"], "warn")
            return redirect(url_for("preview", draft_id=draft_id))
        if row["policy_result"] == "BLOCK":
            flash("The claim policy check blocks this message. Fix panel 8 first.", "bad")
            return redirect(url_for("preview", draft_id=draft_id))

        check = eligibility.check_send_eligibility(
            g.conn, business_id=row["business_id"], channel=row["channel"], policy=g.policy,
            contact_id=row["contact_id"], channel_configured=_configured(row["channel"]),
            channel_switch_on=_switch_on(row["channel"]),
            exclude_message_id=row["message_id"],
        )
        hard = check.business_blockers
        if hard:
            flash(hard[0].sentence, "bad")
            return redirect(url_for("preview", draft_id=draft_id))

        body = row["final_body"]
        subject = row["subject"]
        body_hash = _body_hash(subject, body)
        approval_id = ids.new_id("apr")
        displayed = {
            "business": True, "contact": True, "channel": True, "message": True,
            "previous_contact": True, "opt_out_status": True, "approval_status": True,
        }

        with transaction(g.conn):
            g.conn.execute(
                "UPDATE outreach_messages SET subject_final = ?, body_final = ?, "
                "       body_hash = ?, eligibility_snapshot = ? WHERE id = ?",
                (subject, body, body_hash, json.dumps(check.to_dict()), row["message_id"]),
            )
            g.conn.execute(
                "INSERT INTO outreach_approvals (id, message_id, draft_id, business_id, "
                "        contact_id, channel, approved_by, approved_at, session_id, "
                "        session_auth_method, client_ip, user_agent, approved_subject, "
                "        approved_body, approved_body_hash, approved_to_address, "
                "        confirmation_text, displayed, eligibility_snapshot, preview_token, "
                "        idempotency_key) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (approval_id, row["message_id"], draft_id, row["business_id"],
                 row["contact_id"], row["channel"], g.session_obj.id, utc_now(),
                 g.session_obj.session_id, g.session_obj.auth_method, request.remote_addr,
                 (request.user_agent.string or "")[:300], subject, body, body_hash,
                 row["to_address_norm"] or "", CONFIRMATION_TEXT, json.dumps(displayed),
                 json.dumps(check.to_dict()),
                 request.form.get("preview_token") or session.get("preview_token") or "",
                 approval_id),
            )
            g.conn.execute(
                "UPDATE outreach_messages SET status = 'APPROVED', approval_id = ? "
                " WHERE id = ? AND status = 'PENDING_APPROVAL'",
                (approval_id, row["message_id"]),
            )
            audit_mod.audit(
                g.conn, g.session_obj.id, "MESSAGE_APPROVED", "outreach_approvals",
                approval_id, business_id=row["business_id"], message_id=row["message_id"],
                campaign_id=row["campaign_id"], route=request.path, http_method="POST",
                session_id=g.session_obj.session_id, client_ip=request.remote_addr,
                detail={"body_hash": body_hash, "confirmation_text": CONFIRMATION_TEXT,
                        "address_masked": mask_address(row["to_address_norm"]),
                        "address_sha256": hash_address(row["to_address_norm"])},
            )

        if request.form.get("then") == "send":
            return _do_send(row["message_id"], approval_id, draft_id)

        flash("Approved. apr_ record written.", "ok")
        return redirect(url_for("preview", draft_id=draft_id))

    @app.route("/outreach/<message_id>/send", methods=["POST"])
    @login_required
    def send(message_id: str) -> Any:
        """Re-validate everything, then hand the message to the transport.

        This is reachable on its own for a message approved earlier and held because the email
        channel had no credentials at the time. Its control still lives only in the confirm
        dialog.
        """
        message = queries.message(g.conn, message_id)
        if message is None:
            abort(404)
        if not message["approval_id"]:
            abort(400, "There is no send path without a human approval row.")
        return _do_send(message_id, message["approval_id"], None)

    def _do_send(message_id: str, approval_id: str, draft_id: str | None) -> Any:
        message = queries.message(g.conn, message_id)
        if message is None:
            abort(404)
        draft_id = draft_id or message["draft_id"]

        check = eligibility.check_send_eligibility(
            g.conn, business_id=message["business_id"], channel=message["channel"],
            policy=g.policy, contact_id=message["contact_id"],
            channel_configured=_configured(message["channel"]),
            channel_switch_on=_switch_on(message["channel"]),
            exclude_message_id=message_id,
        )
        hard = check.business_blockers
        if hard:
            with transaction(g.conn):
                g.conn.execute(
                    "UPDATE outreach_messages SET status = 'CANCELLED', cancelled_at = ? "
                    " WHERE id = ? AND status = 'APPROVED'", (utc_now(), message_id),
                )
                audit_mod.audit(g.conn, g.session_obj.id, "MESSAGE_CANCELLED",
                                "outreach_messages", message_id, message_id=message_id,
                                business_id=message["business_id"],
                                detail={"gate": hard[0].code})
            flash("Not sent. " + hard[0].sentence + " The message was cancelled.", "bad")
            return redirect(url_for("preview", draft_id=draft_id))

        try:
            result = transmit.send(
                g.conn, g.config, message_id=message_id, approval_id=approval_id,
                actor=g.session_obj.id,
                channel_configured=_configured(message["channel"]),
            )
        except transmit.SendRefused as exc:
            flash(str(exc), "bad")
            return redirect(url_for("preview", draft_id=draft_id))

        flash(result.sentence, "ok" if result.sent else "warn")
        return redirect(url_for("business", business_id=message["business_id"]))

    # --- handoffs ----------------------------------------------------------

    @app.route("/handoffs")
    @login_required
    def handoffs() -> Any:
        state = request.args.get("state", "open")
        return render_template("handoffs.html",
                               handoffs=queries.handoffs(g.conn, state), state=state)

    @app.route("/handoffs/<handoff_id>/ack", methods=["POST"])
    @login_required
    def handoff_ack(handoff_id: str) -> Any:
        with transaction(g.conn):
            row = g.conn.execute(
                "SELECT business_id, state FROM handoffs WHERE id = ?", (handoff_id,)
            ).fetchone()
            if row is None:
                abort(404)
            g.conn.execute(
                "UPDATE handoffs SET state = 'ACKNOWLEDGED', acknowledged_at = ?, "
                "       owner_user_id = ? WHERE id = ? AND state = 'OPEN'",
                (utc_now(), g.session_obj.id, handoff_id),
            )
            audit_mod.audit(g.conn, g.session_obj.id, "HANDOFF_ACKNOWLEDGED", "handoffs",
                            handoff_id, business_id=row["business_id"],
                            route=request.path, http_method="POST")
        return redirect(url_for("handoffs"))

    # --- settings ----------------------------------------------------------

    @app.route("/settings/channels")
    @login_required
    def settings_channels() -> Any:
        return render_template(
            "settings_channels.html",
            statuses=g.channels,
            config=g.config,
            sent_today=queries.sent_today(g.conn),
            unsubscribe_line=_unsubscribe_line(),
        )

    # --- small helpers bound to the request ---------------------------------

    def _configured(channel: str) -> bool:
        status = g.channels.get(channel)
        return bool(status and status.configured)

    def _switch_on(channel: str) -> bool:
        status = g.channels.get(channel)
        return bool(status and status.switch_on)

    def _unsubscribe_line() -> str:
        address = g.config.email.address or "the address this mail came from"
        return ("To stop receiving these, reply with UNSUBSCRIBE or write to %s."
                % _unsub_address(address))

    def _unsubscribe_marker() -> str:
        return "UNSUBSCRIBE"


class _PrepareRefused(RuntimeError):
    """One selection could not be drafted. The message is the sentence shown next to it."""


# ---------------------------------------------------------------------------
# module-level helpers
# ---------------------------------------------------------------------------

def _unsub_address(address: str) -> str:
    if "@" in address:
        local, _, domain = address.partition("@")
        return "%s+unsub@%s" % (local, domain)
    return address


def _body_hash(subject: str | None, body: str) -> str:
    """sha256 of subject + RS + body. The approval covers both or it covers neither."""
    payload = (subject or "") + "\x1e" + (body or "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _slugify(value: str) -> str:
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-")


def _set_status(conn: sqlite3.Connection, business_id: str, status: str, *,
                actor_kind: str, user_id: str | None = None,
                only_from: tuple[str, ...] | None = None) -> None:
    """Move businesses.status, letting the transition table refuse an illegal move.

    `only_from` makes the update a no-op rather than an error when the row has already moved -
    two tabs open on the same business is a normal thing, not an exception.
    """
    sql = ("UPDATE businesses SET status = ?, status_actor_kind = ?, status_actor_user_id = ? "
           " WHERE id = ?")
    params: list[Any] = [status, actor_kind, user_id, business_id]
    if only_from:
        sql += " AND status IN (%s)" % ",".join("?" * len(only_from))
        params.extend(only_from)
    conn.execute(sql, params)


def _refresh_contact_ready(conn: sqlite3.Connection, business_id: str) -> None:
    """Promote a VERIFIED business to CONTACT_READY when the predicate holds, or explain why not.

    CONTACT_READY is a materialised answer, not an opinion: it means there is a live human-
    confirmed contact and no suppression. 010_verify_eligibility.sql added the two columns that
    let the grid render "verified, and here is what is holding it back" without re-running this.
    """
    row = conn.execute("SELECT status FROM businesses WHERE id = ?", (business_id,)).fetchone()
    if row is None:
        return
    suppressed = bool(conn.execute(
        "SELECT 1 FROM suppressions WHERE released_at IS NULL "
        "   AND ((scope = 'BUSINESS' AND value_norm = ?) OR business_id = ?) LIMIT 1",
        (business_id, business_id),
    ).fetchone())
    contact = conn.execute(
        "SELECT 1 FROM business_contacts WHERE business_id = ? AND is_active = 1 "
        "   AND valid = 1 AND human_verified = 1 LIMIT 1", (business_id,),
    ).fetchone()

    block_code = None
    if suppressed:
        block_code = "A_SUPPRESSED"
    elif contact is None:
        block_code = "E_CONTACT_MISSING"

    with transaction(conn):
        conn.execute(
            "UPDATE businesses SET contact_ready_block_code = ?, contact_ready_checked_at = ? "
            " WHERE id = ?", (block_code, utc_now(), business_id),
        )
        if block_code is None and row["status"] == "VERIFIED":
            conn.execute(
                "UPDATE businesses SET status = 'CONTACT_READY', status_actor_kind = 'SYSTEM', "
                "       status_actor_user_id = NULL, contact_ready_at = ? "
                " WHERE id = ? AND status = 'VERIFIED'", (utc_now(), business_id),
            )
            audit_mod.audit(conn, None, "CONTACT_READY_GRANTED", "businesses", business_id,
                            business_id=business_id)


def _readiness_sentence(conn: sqlite3.Connection, business_id: str) -> str:
    row = conn.execute(
        "SELECT status, contact_ready_block_code FROM businesses WHERE id = ?", (business_id,)
    ).fetchone()
    if row is None:
        return ""
    if row["status"] == "CONTACT_READY":
        return "It is now contact-ready and appears in the outreach tray."
    code = row["contact_ready_block_code"]
    return eligibility.BLOCK_REASON.get(code, "It is verified but not yet contact-ready.")


# ---------------------------------------------------------------------------
# serving
# ---------------------------------------------------------------------------

def serve(config: Config | None = None, db_path: Path | None = None) -> None:
    """Run the app under waitress on 127.0.0.1. Never the Flask dev server.

    The bind address is not configurable to anything routable on purpose: docs/_CONTEXT.md
    section 2 puts this on a laptop with no public hostname, and a tool that can be started on
    0.0.0.0 by editing one line is a tool that eventually is.
    """
    from waitress import serve as waitress_serve

    cfg = config or load_config(strict=False)
    setup_logging(cfg.log_level, log_file=cfg.log_file)
    app = create_app(cfg, db_path)

    conn = db_mod.open_migrated(db_path or DB_PATH)
    try:
        with transaction(conn):
            audit_mod.audit(conn, "web", "SYSTEM_STARTED", "system", None,
                            detail={"host": cfg.web.host, "port": cfg.web.port})
        first_run = not security.has_usable_password(conn)
    finally:
        conn.close()

    url = "http://%s:%d/" % (cfg.web.host, cfg.web.port)
    log.info("business_radar is at %s", url)
    print("business_radar: " + url)
    if first_run:
        print("First run: open " + url + "setup to create the operator account.")
    waitress_serve(app, host=cfg.web.host, port=cfg.web.port, threads=cfg.web.threads)
