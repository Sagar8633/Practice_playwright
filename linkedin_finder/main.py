#!/usr/bin/env python
"""LinkedIn Remote Job Finder.

    python -m linkedin_finder.main --login       sign in once, save the session
    python -m linkedin_finder.main --search      search remote jobs, generate report
    python -m linkedin_finder.main --search --keywords "DevOps,Cloud"
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ensure parent directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from linkedin_finder import session, search, report
import yaml

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"
LOG_DIR = ROOT / "data" / "logs"

# Windows console encoding fix
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
            logging.FileHandler(LOG_DIR / "linkedin_finder.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config() -> dict:
    """Load search configuration from config.yaml."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def cmd_login() -> int:
    """Handle --login: manual sign-in and session save."""
    ok = session.login()
    return 0 if ok else 1


def cmd_search(args, config: dict) -> int:
    """Handle --search: search remote jobs and generate report."""
    # Override config with CLI args
    keywords = config.get("keywords", ["SDET", "QA Automation"])
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    location = config.get("location")
    posted_days = args.posted_days or config.get("posted_days", 30)
    pages = args.pages or config.get("pages_per_keyword", 2)
    max_results = args.max_results or config.get("max_results", 100)

    log = logging.getLogger("linkedin_finder.main")
    log.info("Starting LinkedIn search: %d keywords, posted in last %d days",
             len(keywords), posted_days)

    # Open LinkedIn session
    try:
        pw, browser, ctx, page = session.open_session(headless=args.headless)
    except session.NotLoggedIn as exc:
        print(f"\n  {exc}\n")
        return 2

    try:
        # Search all keywords
        cards = search.search_all(
            page, keywords, location, posted_days, pages, remote_only=True
        )
        log.info("Raw results: %d unique jobs", len(cards))

        # Apply filters
        cards = search.filter_cards(cards, config)
        log.info("After filtering: %d jobs", len(cards))

        # Limit results
        cards = cards[:max_results]

        # Generate report
        html_path = report.generate_report(cards)
        json_path = report.save_json(cards)

        # Print summary
        print(f"\n  LinkedIn Remote Job Search Complete!")
        print(f"  {'=' * 50}")
        print(f"  Keywords searched: {', '.join(keywords)}")
        print(f"  Total jobs found: {len(cards)}")
        print(f"  Remote jobs: {sum(1 for c in cards if c.get('_remote'))}")
        print(f"  Easy Apply: {sum(1 for c in cards if c.get('easy_apply'))}")
        print(f"  Companies: {len(set(c.get('company', '') for c in cards if c.get('company')))}")
        print(f"\n  Report: {html_path}")
        print(f"  Data:   {json_path}")

        # Print top companies
        companies = {}
        for card in cards:
            co = card.get("company", "")
            if co:
                companies[co] = companies.get(co, 0) + 1
        if companies:
            print(f"\n  Top Companies Hiring:")
            for co, count in sorted(companies.items(), key=lambda x: -x[1])[:15]:
                print(f"    {count:3}x  {co}")
        print()

        return 0

    except Exception as exc:
        logging.getLogger("linkedin_finder").exception("Search failed")
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
                        help="Search remote jobs and generate report")

    parser.add_argument("--keywords", help="Comma-separated search keywords (overrides config)")
    parser.add_argument("--posted-days", type=int, default=None, dest="posted_days",
                        help="Only show jobs posted in the last N days")
    parser.add_argument("--pages", type=int, default=None,
                        help="Pages to scrape per keyword (25 results each)")
    parser.add_argument("--max-results", type=int, default=None, dest="max_results",
                        help="Maximum jobs in report")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode (may be blocked by LinkedIn)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Debug logging")

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
