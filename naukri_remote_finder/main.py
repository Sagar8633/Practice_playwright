#!/usr/bin/env python
"""Naukri Remote Job Finder.

    python -m naukri_remote_finder.main --login       sign in once, save the session
    python -m naukri_remote_finder.main --search      search remote jobs (24h, all India)
    python -m naukri_remote_finder.main --search --keywords "DevOps,Cloud" --pages 5
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naukri_remote_finder import session, search, report
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
            logging.FileHandler(LOG_DIR / "naukri_finder.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def cmd_login() -> int:
    ok = session.login()
    return 0 if ok else 1


def cmd_search(args, config: dict) -> int:
    # Keywords
    keywords = config.get("keywords", ["SDET", "QA Automation"])
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    location = config.get("location")
    posted_days = args.posted_days if args.posted_days is not None else config.get("posted_days", 1)
    pages = args.pages if args.pages is not None else config.get("pages_per_keyword", 3)
    experience = config.get("experience_years")
    remote_marker = args.remote_marker or "remote"

    log = logging.getLogger("naukri_remote_finder.main")
    log.info("Starting Naukri search: %d keywords, posted in last %d day(s)",
             len(keywords), posted_days)

    # Open Naukri session (headed always - Akamai blocks headless)
    try:
        pw, browser, ctx, page = session.open_session(headless=args.headless)
    except session.NotLoggedIn as exc:
        print(f"\n  {exc}\n")
        return 2

    try:
        # Gather ALL jobs (any location) - no cap
        jobs = search.gather(
            page, keywords, experience=experience,
            job_age=posted_days if posted_days else None,
            pages=pages, remote_marker=remote_marker
        )
        log.info("Raw results (all locations): %d jobs", len(jobs))

        # Keep ONLY remote jobs, posted within window - no cap
        jobs = search.filter_remote_only(jobs, config)
        log.info("After remote-only+posting filter: %d jobs", len(jobs))

        # Generate report - NOT capped
        html_path = report.generate_report(jobs)
        json_path = report.save_json(jobs)

        # Summary
        print(f"\n  Naukri Remote Job Search Complete!")
        print(f"  {'=' * 55}")
        print(f"  Keywords: {', '.join(keywords)}")
        print(f"  Posted in last: {posted_days} day(s)")
        print(f"  Total remote jobs: {len(jobs)}")
        print(f"  1-Click Apply: {sum(1 for j in jobs if j.auto_applicable)}")
        print(f"  With Questionnaire: {sum(1 for j in jobs if j.has_questionnaire)}")
        print(f"  Companies: {len(set(j.company for j in jobs if j.company))}")
        print(f"\n  Report: {html_path}")
        print(f"  Data:   {json_path}")

        companies = {}
        for job in jobs:
            if job.company:
                companies[job.company] = companies.get(job.company, 0) + 1
        if companies:
            print(f"\n  Companies Hiring Remotely:")
            for co, count in sorted(companies.items(), key=lambda x: -x[1])[:25]:
                print(f"    {count:3}x  {co}")
        print()
        return 0

    except Exception as exc:
        logging.getLogger("naukri_remote_finder").exception("Search failed")
        print(f"\n  Error: {exc}\n")
        return 1

    finally:
        session.close_session(pw, browser)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--login", action="store_true",
                        help="Sign in manually and save the session")
    action.add_argument("--search", action="store_true",
                        help="Search remote jobs (24h, all India) and generate report")

    parser.add_argument("--keywords", help="Comma-separated keywords (overrides config)")
    parser.add_argument("--posted-days", type=float, default=None, dest="posted_days",
                        help="Only show jobs posted in the last N days (default from config)")
    parser.add_argument("--pages", type=int, default=None,
                        help="Pages to scrape per keyword - unlimited results, no cap")
    parser.add_argument("--remote-marker", default=None, dest="remote_marker",
                        help="Word appended to keyword to signal remote (default 'remote')")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode (may be blocked by Akamai)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    args = parser.parse_args()
    _setup_logging(args.verbose)

    config = load_config()

    if args.login:
        return cmd_login()
    if args.search:
        return cmd_search(args, config)

    return 0


if __name__ == "__main__":
    sys.exit(main())
