#!/usr/bin/env python3
"""business_radar - city-wise business research with a mandatory human verification gate.

The AI researches, scores and explains. It never contacts anybody. Every message that leaves this
machine passed through a human approval row first, and there is no code path that skips it.

Requires Python 3.11 or newer (enum.StrEnum, dataclass slots).

Examples
--------
  python main.py doctor                        # what is ready, what is missing
  python main.py migrate                       # create/upgrade the database

  python main.py places "Pune"                 # search anywhere on earth
  python main.py places "Shirpur, Maharashtra"

  python main.py campaign new --name "Pune healthcare" --locations "Pune, India" \
      --categories HOSPITAL,DIAGNOSTIC_CENTER --min-score 70
  python main.py campaign list
  python main.py campaign show cmp_01M1...

  python main.py discover cmp_01M1...          # OpenStreetMap, free, no key
  python main.py research  cmp_01M1...         # Gemini free tier: findings + scores
  python main.py report    cmp_01M1...         # self-contained HTML

  python main.py draft biz_01M1...             # generate + policy-check a message
  python main.py check-channels                # is email configured yet?
  python main.py web                           # the UI on http://127.0.0.1:8770

Nothing sends until you configure Gmail. Until then drafts are written to data/outbox/ as .eml
files you can open and read - which is the intended way to use this for the first few weeks.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(
        "business_radar needs Python 3.11 or newer (you have "
        f"{sys.version_info.major}.{sys.version_info.minor}).\n"
        "On this machine the right interpreter is usually:\n"
        r"  C:\Users\samja\AppData\Local\Programs\Python\Python311\python.exe" "\n"
        "or the project venv: .venv311\\Scripts\\python.exe"
    )

sys.path.insert(0, str(Path(__file__).resolve().parent))

from radar import paths                                              # noqa: E402
from radar.config import ConfigError, check_config, load_config, setup_logging   # noqa: E402
from radar.db import connect, migrate, open_migrated, schema_version  # noqa: E402

log = logging.getLogger("radar.main")

OK, BAD, WARN = "  [ok]  ", "  [--]  ", "  [!!]  "


# --------------------------------------------------------------------------- helpers

def _cfg(strict: bool = False):
    try:
        return load_config(strict=strict)
    except ConfigError as exc:
        sys.exit(f"Configuration problem:\n  {exc}\n\nRun:  python main.py setup")


def _conn():
    paths.ensure()
    return open_migrated()


# --------------------------------------------------------------------------- commands

def cmd_setup(args) -> int:
    """Copy the example config and env into place, then report what still needs filling in."""
    paths.ensure()
    made = []
    if not paths.CONFIG_PATH.exists() and paths.CONFIG_EXAMPLE_PATH.exists():
        shutil.copy(paths.CONFIG_EXAMPLE_PATH, paths.CONFIG_PATH)
        made.append(paths.CONFIG_PATH)
    if not paths.ENV_PATH.exists() and paths.ENV_EXAMPLE_PATH.exists():
        paths.ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(paths.ENV_EXAMPLE_PATH, paths.ENV_PATH)
        made.append(paths.ENV_PATH)

    for p in made:
        print(f"  created  {p}")
    if not made:
        print("  config already present, nothing copied")
    print()
    return cmd_doctor(args)


def cmd_doctor(args) -> int:
    """Say plainly what works right now and what is still missing."""
    print("business_radar - readiness\n")
    print(f"{OK}Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    if not paths.CONFIG_PATH.exists():
        print(f"{BAD}config.yaml missing - run: python main.py setup")
        return 1
    print(f"{OK}config.yaml at {paths.CONFIG_PATH}")

    cfg = _cfg(strict=False)
    problems = check_config(cfg)

    # The database
    try:
        conn = _conn()
        v = schema_version(conn)
        n = conn.execute("SELECT count(*) c FROM campaigns").fetchone()["c"]
        print(f"{OK}database at {paths.DB_PATH} (schema v{v}, {n} campaign(s))")
        conn.close()
    except Exception as exc:                                    # noqa: BLE001
        print(f"{BAD}database: {exc}")
        problems.append(str(exc))

    # The LLM - the only thing genuinely required to start
    if cfg.llm.configured:
        print(f"{OK}Gemini key present, model {cfg.llm.model}")
    else:
        print(f"{BAD}GEMINI_API_KEY not set in config/.env  <- research cannot run without this")

    # Channels are optional by design
    if cfg.email.configured:
        print(f"{OK}email configured: {cfg.email.address}")
    else:
        print(f"{WARN}email not configured - drafts will be written to data/outbox/ as .eml files")
        print("         this is a supported state, not an error. See docs/17-channel-configuration.md")
    print(f"{OK}WhatsApp: manual wa.me links (never needs credentials)")

    print()
    if problems:
        print("Still to do:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("Ready. Try:  python main.py places \"Pune\"")
    return 0


def cmd_migrate(args) -> int:
    paths.ensure()
    conn = connect()
    applied = migrate(conn)
    print(f"  applied {len(applied)} migration(s); schema is now v{schema_version(conn)}")
    conn.close()
    return 0


def cmd_places(args) -> int:
    """Search for a place anywhere in the world."""
    from radar.locations import LocationError, describe, search

    cfg = _cfg()
    conn = _conn()
    try:
        found = search(" ".join(args.query), cfg=cfg, conn=conn, limit=args.limit)
    except LocationError as exc:
        print(f"  {exc}")
        return 1
    if not found:
        print("  Nothing found. Try adding a region or country.")
        return 1
    print(f"\n  {len(found)} match(es) for {' '.join(args.query)!r}:\n")
    print(describe(found))
    print("\n  Use the full label with:  python main.py campaign new --locations \"...\"\n")
    conn.close()
    return 0


def cmd_campaign(args) -> int:
    from radar.ids import new_id
    from radar.locations import LocationError, LocationTooBroad, resolve_to_bound
    from radar.models import utc_now

    conn = _conn()

    if args.action == "new":
        cfg = _cfg()
        locations = [s.strip() for s in args.locations.split(",,") if s.strip()] \
            if ",," in args.locations else [s.strip() for s in args.locations.split(",") if s.strip()]
        # A single "Pune, India" is one place, not two. Only treat commas as separators when the
        # user gave an explicit ",," - otherwise resolve the whole string as one query.
        if len(locations) > 1 and ",," not in args.locations:
            locations = [args.locations.strip()]

        resolved = []
        for q in locations:
            try:
                place, bound = resolve_to_bound(q, cfg=cfg, conn=conn)
            except LocationTooBroad as exc:
                print(f"  {exc}")
                return 1
            except LocationError as exc:
                print(f"  {exc}")
                return 1
            resolved.append((place, bound))
            kind = "boundary" if bound.is_exact else f"{bound.radius_m // 1000} km radius"
            print(f"  resolved  {place.label}  [{kind}]")

        owner = conn.execute(
            "SELECT id FROM users ORDER BY created_at LIMIT 1"
        ).fetchone()
        if owner is None:
            print("  no user exists yet - run: python main.py migrate")
            return 1

        cid = new_id("cmp")
        slug = "".join(c if c.isalnum() else "-" for c in args.name.lower()).strip("-")
        slug = "-".join(p for p in slug.split("-") if p)[:48] or "campaign"
        slug = f"{slug}-{cid[-6:].lower()}"
        cats = json.dumps(
            [c.strip().upper() for c in (args.categories or "").split(",") if c.strip()]
        )
        with conn:
            conn.execute(
                "INSERT INTO campaigns (id, name, slug, created_by, created_at, status,"
                " min_opportunity_score, research_depth, categories)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, args.name, slug, owner["id"], utc_now(), "DRAFT",
                 args.min_score, args.depth, cats),
            )
            for ordinal, (place, bound) in enumerate(resolved, start=1):
                # The bound itself lives in `locations` (written by remember() during resolution);
                # campaign_cities records which place this campaign targets and how far it got.
                conn.execute(
                    "INSERT INTO campaign_cities (campaign_id, city, city_slug, state_region,"
                    " ordinal) VALUES (?,?,?,?,?)",
                    (cid, place.name, bound.slug, place.state or place.country, ordinal),
                )
        print(f"\n  created campaign {cid}")
        print(f"  next:  python main.py discover {cid}")
        return 0

    if args.action == "list":
        rows = conn.execute(
            "SELECT c.id, c.name, c.status, c.created_at,"
            " (SELECT count(*) FROM campaign_cities cc WHERE cc.campaign_id = c.id) cities"
            " FROM campaigns c ORDER BY c.created_at DESC"
        ).fetchall()
        if not rows:
            print("  no campaigns yet - python main.py campaign new --help")
            return 0
        print()
        for r in rows:
            print(f"  {r['id']}  {r['status']:<10} {r['cities']} location(s)  {r['name']}")
        print()
        return 0

    if args.action == "show":
        c = conn.execute("SELECT * FROM campaigns WHERE id = ?", (args.campaign_id,)).fetchone()
        if not c:
            print(f"  no campaign {args.campaign_id}")
            return 1
        print(f"\n  {c['name']}  [{c['status']}]  created {c['created_at']}")
        for cc in conn.execute(
            "SELECT * FROM campaign_cities WHERE campaign_id = ? ORDER BY ordinal",
            (args.campaign_id,),
        ):
            how = "boundary" if cc["bound_kind"] == "AREA" else f"{(cc['radius_m'] or 0)//1000} km radius"
            print(f"    - {cc['city_name']}  [{how}, {cc['bound_source']}]")
        n = conn.execute(
            "SELECT count(*) c FROM campaign_businesses WHERE campaign_id = ?",
            (args.campaign_id,),
        ).fetchone()["c"]
        print(f"    {n} business(es) discovered\n")
        return 0

    return 1


def cmd_check_channels(args) -> int:
    cfg = _cfg(strict=False)
    print()
    print(f"  EMAIL     {'configured: ' + cfg.email.address if cfg.email.configured else 'not configured'}")
    if not cfg.email.configured:
        print("            drafts go to data/outbox/ as .eml files. Nothing is sent.")
        print("            to enable: set OUTREACH_GMAIL_ADDRESS and OUTREACH_GMAIL_APP_PASSWORD")
        print("            in config/.env (2-Step Verification must be on, IMAP enabled)")
    print("  WHATSAPP  manual wa.me links - no credentials required, ever")
    print("  PHONE     manual only, never dialled by this system")
    print()
    return 0


def cmd_web(args) -> int:
    cfg = _cfg()
    paths.ensure()
    open_migrated().close()
    from waitress import serve
    from radar.web.app import create_app

    app = create_app(cfg)
    host, port = args.host or cfg.web.host, args.port or cfg.web.port
    print(f"\n  business_radar running at http://{host}:{port}")
    print("  press Ctrl+C to stop\n")
    serve(app, host=host, port=port, threads=cfg.web.threads)
    return 0


def _stage(name):
    """The campaign-level loops.

    radar/research.py deliberately exposes only `research_and_score(business_id)` - one business,
    one transaction, resumable. The loop over a campaign lives here so that a crash mid-campaign
    leaves every business already researched exactly as it was, and re-running simply picks up
    the ones still in AI_RESEARCHED.
    """
    def run(args) -> int:
        cfg = _cfg()
        conn = _conn()

        if name == "discover":
            from radar.discover import discover_campaign
            results = discover_campaign(conn, args.campaign_id, cfg=cfg)
            total = 0
            for r in results:
                n = getattr(r, "kept", None)
                n = len(n) if isinstance(n, list) else getattr(r, "n_discovered", 0)
                total += n or 0
                print(f"  {getattr(r, 'city_name', '?'):<20} {n or 0} business(es)")
                for err in getattr(r, "errors", []) or []:
                    print(f"      error: {err}")
            print(f"\n  {total} discovered")
            print(f"  next:  python main.py research {args.campaign_id}")

        elif name == "research":
            from radar.llm import GeminiClient, QuotaExhausted
            from radar.research import research_and_score

            client = GeminiClient(cfg.llm, conn)
            if not client.configured:
                print("  GEMINI_API_KEY is not set in config/.env - research needs it.")
                return 1

            rows = conn.execute(
                "SELECT b.id, b.name FROM businesses b"
                "  JOIN campaign_businesses cb ON cb.business_id = b.id"
                " WHERE cb.campaign_id = ? AND b.status = 'AI_RESEARCHED'"
                " ORDER BY b.created_at",
                (args.campaign_id,),
            ).fetchall()
            if args.limit:
                rows = rows[: args.limit]
            if not rows:
                print("  nothing left to research in this campaign")
                return 0

            print(f"  researching {len(rows)} business(es)\n")
            done = failed = 0
            for i, r in enumerate(rows, 1):
                label = (r["name"] or r["id"])[:44]
                try:
                    out = research_and_score(
                        conn, r["id"], client=client, cfg=cfg,
                        campaign_id=args.campaign_id, depth=args.depth, actor="cli",
                    )
                    score, band = out.get("score"), out.get("band")
                    shown = f"{score:>3} {band}" if score is not None else "  - unscored"
                    print(f"  {i:>3}/{len(rows)}  {shown:<14} {label}")
                    done += 1
                except QuotaExhausted:
                    print(f"\n  daily Gemini quota reached after {done}. Nothing is lost -")
                    print(f"  re-run tomorrow and it resumes where it stopped.")
                    break
                except Exception as exc:                        # noqa: BLE001
                    print(f"  {i:>3}/{len(rows)}  FAILED         {label}: {exc}")
                    failed += 1
            print(f"\n  researched {done}, failed {failed}")
            print(f"  next:  python main.py report {args.campaign_id}")

        elif name == "report":
            from radar.report import generate_report
            path = generate_report(conn, args.campaign_id)
            print(f"  wrote {path}")
            print("  open it in a browser - it is self-contained")

        conn.close()
        return 0
    return run


def cmd_draft(args) -> int:
    cfg = _cfg()
    conn = _conn()
    from radar.messages import generate_draft
    from radar.policy import check_policy

    draft = generate_draft(conn, args.business_id, channel=args.channel, cfg=cfg)
    result = check_policy(conn, draft)
    print(f"\n  subject: {getattr(draft, 'subject', '(none)')}\n")
    print(getattr(draft, "body", ""))
    print(f"\n  policy: {getattr(result, 'verdict', '?')}")
    for d in getattr(result, "details", []) or []:
        print(f"    - {d}")
    print("\n  Nothing has been sent. Approve in the web UI to proceed.\n")
    conn.close()
    return 0


# --------------------------------------------------------------------------- wiring

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="create config from the examples, then check").set_defaults(fn=cmd_setup)
    sub.add_parser("doctor", help="what is ready and what is missing").set_defaults(fn=cmd_doctor)
    sub.add_parser("migrate", help="create or upgrade the database").set_defaults(fn=cmd_migrate)
    sub.add_parser("check-channels", help="is email configured yet").set_defaults(fn=cmd_check_channels)

    pl = sub.add_parser("places", help="search for a place anywhere in the world")
    pl.add_argument("query", nargs="+")
    pl.add_argument("--limit", type=int, default=8)
    pl.set_defaults(fn=cmd_places)

    c = sub.add_parser("campaign", help="create and inspect campaigns")
    csub = c.add_subparsers(dest="action", required=True)
    cn = csub.add_parser("new")
    cn.add_argument("--name", required=True)
    cn.add_argument("--locations", required=True,
                    help='place to search, e.g. "Pune, India". Separate several with ",,"')
    cn.add_argument("--categories", default="")
    cn.add_argument("--min-score", type=int, default=70, dest="min_score")
    cn.add_argument("--depth", default="STANDARD", choices=["STANDARD", "DEEP"])
    cn.add_argument("--created-by", default="sagar", dest="created_by")
    csub.add_parser("list")
    cs = csub.add_parser("show")
    cs.add_argument("campaign_id")
    c.set_defaults(fn=cmd_campaign)

    for name, helptext in [
        ("discover", "find businesses via OpenStreetMap"),
        ("research", "research and score discovered businesses"),
        ("report", "generate the self-contained HTML report"),
    ]:
        s = sub.add_parser(name, help=helptext)
        s.add_argument("campaign_id")
        if name == "research":
            s.add_argument("--limit", type=int, default=None)
            s.add_argument("--depth", default=None, choices=["STANDARD", "DEEP"])
        s.set_defaults(fn=_stage(name))

    d = sub.add_parser("draft", help="generate and policy-check a message (sends nothing)")
    d.add_argument("business_id")
    d.add_argument("--channel", default="EMAIL", choices=["EMAIL", "WHATSAPP"])
    d.set_defaults(fn=cmd_draft)

    w = sub.add_parser("web", help="run the local web UI")
    w.add_argument("--host", default=None)
    w.add_argument("--port", type=int, default=None)
    w.set_defaults(fn=cmd_web)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        print("\n  interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
