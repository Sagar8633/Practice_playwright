#!/usr/bin/env python
"""Global Remote Job Finder - Naukri (India) + global remote boards.

    python -m global_remote_finder.main --naukri-login   sign in to Naukri once
    python -m global_remote_finder.main --search         all boards, remote-only
    python -m global_remote_finder.main --search --naukri-only
    python -m global_remote_finder.main --search --global-only
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from global_remote_finder import session, report, boards, naukri
import yaml

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"
LOG_DIR = ROOT / "data" / "logs"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _setup_logging(verbose: bool) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "global_finder.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _filter(jobs: list[dict], config: dict) -> list[dict]:
    excludes_t = [t.lower() for t in config.get("exclude_titles", [])]
    excludes_c = [c.lower() for c in config.get("exclude_companies", [])]
    kept = []
    for job in jobs:
        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()
        if any(t in title for t in excludes_t):
            continue
        if any(c in company for c in excludes_c):
            continue
        # Board-level keyword relevance for global boards (boards already
        # filtered, but keep only relevant ones by title word match)
        kept.append(job)
    return kept


def cmd_naukri_login() -> int:
    return 0 if session.naukri_login() else 1


def cmd_search(args, config: dict) -> int:
    all_jobs: dict[str, dict] = {}
    keywords = [k for k in config.get("keywords", []) if k]

    if not args.global_only:
        # --- Naukri (India) ---
        if config.get("naukri", {}).get("enabled", True):
            try:
                pw, browser, page = session.open_naukri(headless=args.headless)
            except session.NotLoggedIn as exc:
                print(f"\n  {exc}\n")
                return 2
            try:
                jobs = naukri.gather(page, config, experience=config.get("experience_years"))
                for j in jobs:
                    all_jobs[j["job_id"]] = j
            finally:
                session.close(pw, browser)

    if not args.naukri_only:
        # --- Global boards (public, headless for speed, each with a timeout) ---
        gcfg = config.get("global", {})
        if gcfg.get("enabled", True):
            board_kw = config.get("board_keywords", {})
            if gcfg.get("remoteok", True):
                bj = boards.run_board(boards.remoteok,
                                      board_kw.get("remoteok", keywords),
                                      headless=True, timeout_sec=90)
                for j in bj:
                    all_jobs[j["job_id"]] = j
            if gcfg.get("weworkremotely", True):
                bj = boards.run_board(boards.weworkremotely,
                                      board_kw.get("weworkremotely", keywords),
                                      headless=True, timeout_sec=90)
                for j in bj:
                    all_jobs[j["job_id"]] = j
            if gcfg.get("remotive", True):
                bj = boards.remotive(board_kw.get("remotive", keywords))
                for j in bj:
                    all_jobs[j["job_id"]] = j

    all_jobs = _filter(list(all_jobs.values()), config)

    # Order: source group, then as found
    order = {"Naukri": 0, "RemoteOK": 1, "WeWorkRemotely": 2, "Remote.co": 3}
    jobs = sorted(all_jobs, key=lambda j: order.get(j.get("source"), 9))

    html_path = report.unified(jobs, subtitle="Across India + Global | Remote-only | No cap")
    json_path = report.save_json(jobs)

    board_counts = {}
    for j in jobs:
        src = j.get("source", "?")
        board_counts[src] = board_counts.get(src, 0) + 1

    print(f"\n  Global Remote Job Search Complete!")
    print(f"  {'=' * 55}")
    print(f"  Total remote jobs (no cap): {len(jobs)}")
    for src, cnt in board_counts.items():
        print(f"    {src:12}: {cnt}")
    companies = len(set(j.get("company", "") for j in jobs if j.get("company")))
    print(f"\n  Unique companies: {companies}")
    print(f"\n  Report: {html_path}")
    print(f"  Data:   {json_path}")

    comp = {}
    for j in jobs:
        if j.get("company"):
            comp[j["company"]] = comp.get(j["company"], 0) + 1
    if comp:
        print(f"\n  Companies Hiring Remotely:")
        sources_by_company = {}
        for j in jobs:
            if j.get("company"):
                sources_by_company.setdefault(j["company"], set()).add(j.get("source", "?"))
        for c, n in sorted(comp.items(), key=lambda x: -x[1])[:25]:
            srcs = "/".join(sorted(sources_by_company[c]))
            print(f"    {n:3}x  {c} [{srcs}]")
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--naukri-login", action="store_true", dest="naukri_login",
                        help="Sign in to Naukri once")
    action.add_argument("--search", action="store_true",
                        help="Search all boards, remote-only")

    parser.add_argument("--keywords", help="Comma-separated keywords (overrides config)")
    parser.add_argument("--naukri-only", action="store_true", dest="naukri_only",
                        help="Skip global boards (Naukri only)")
    parser.add_argument("--global-only", action="store_true", dest="global_only",
                        help="Skip Naukri (global boards only)")
    parser.add_argument("--pages", type=int, default=None,
                        help="Naukri pages per keyword (unlimited results)")
    parser.add_argument("--headless", action="store_true",
                        help="Headless (may be blocked by Naukri's Akamai)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    args = parser.parse_args()
    _setup_logging(args.verbose)
    config = load_config()

    if args.keywords:
        config["keywords"] = [k.strip() for k in args.keywords.split(",") if k.strip()]

    if args.naukri_login:
        return cmd_naukri_login()
    if args.search:
        if args.pages:
            config["naukri"]["pages_per_keyword"] = args.pages
        return cmd_search(args, config)

    return 0


if __name__ == "__main__":
    sys.exit(main())
