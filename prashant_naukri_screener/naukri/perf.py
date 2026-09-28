"""Record how the profile is actually performing, so edits can be judged.

Naukri publishes two numbers on the My Naukri homepage:

    Search appearances   how often the profile turned up in a recruiter search
    Recruiter actions    how often a recruiter then did something about it

Everything else in this toolkit is a guess until these are tracked. The daily
nudge ran three times a day for weeks with no way to tell whether it helped,
which is exactly the position this file exists to end: append one row per run,
and a month later the effect of a headline rewrite is a number, not an opinion.

The ratio is the interesting part. Appearances going up with a flat action rate
means the profile is being found on weaker matches; the action rate going up is
the only thing that means the content got better.

    python main.py --perf
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from .session import DEFAULT_STATE, open_profile

log = logging.getLogger("naukri.perf")

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "data" / "performance.json"
HOMEPAGE = "https://www.naukri.com/mnjuser/homepage"

# Confirmed against the live page on 2026-09-12: the widget renders as
# <div class="profile-perf-content">
#   <div class="searchAppWrapper">Search appearances<span>1234</span></div>
#   <div class="recActionsWrapper">Recruiter actions<span>56</span></div>
#
# Scraped by wrapper class and then by label text, because the number itself
# carries no class of its own and its position inside the wrapper has moved
# before.
_SCRAPE_JS = r"""
() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const num = (el) => {
    if (!el) return null;
    const m = norm(el.textContent).match(/(\d[\d,]*)/);
    return m ? parseInt(m[1].replace(/,/g, ''), 10) : null;
  };
  const byClass = (cls) => num(document.querySelector(cls));
  const byLabel = (re) => {
    const hit = Array.from(document.querySelectorAll('div, span, p'))
      .filter(e => e.children.length <= 3)
      .find(e => re.test(norm(e.textContent)) && /\d/.test(norm(e.textContent)));
    return num(hit);
  };
  return {
    search_appearances: byClass('.searchAppWrapper') ?? byLabel(/search appearances/i),
    recruiter_actions:  byClass('.recActionsWrapper') ?? byLabel(/recruiter actions/i),
  };
}
"""


def capture(state_path: Path = DEFAULT_STATE, headless: bool = False,
            note: str | None = None) -> dict:
    """Scrape the two numbers and append them to data/performance.json."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, _context, page = open_profile(p, state_path, headless=headless)
        try:
            page.goto(HOMEPAGE, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            # The widget is below the fold and lazy-rendered.
            for _ in range(5):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(400)

            data = page.evaluate(_SCRAPE_JS)
        finally:
            browser.close()

    if data.get("search_appearances") is None and data.get("recruiter_actions") is None:
        raise RuntimeError(
            "Could not read either number from the homepage - Naukri has most "
            "likely reshipped the Profile performance widget. Re-check with: "
            "python main.py --inspect \"Profile performance\""
        )

    entry = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "search_appearances": data.get("search_appearances"),
        "recruiter_actions": data.get("recruiter_actions"),
    }
    appearances, actions = entry["search_appearances"], entry["recruiter_actions"]
    if appearances and actions is not None:
        entry["action_rate_pct"] = round(actions / appearances * 100, 2)
    if note:
        entry["note"] = note

    _record(entry)
    log.info("Performance: %s appearances, %s recruiter actions", appearances, actions)
    return entry


def _record(entry: dict) -> None:
    entries = []
    if LOG_FILE.exists():
        try:
            entries = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            entries = []
    entries.append(entry)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def history() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def summarise(entry: dict) -> str:
    """Show the new reading against the previous one."""
    rows = history()
    prev = rows[-2] if len(rows) >= 2 else None

    def delta(key: str) -> str:
        if not prev or prev.get(key) is None or entry.get(key) is None:
            return ""
        diff = entry[key] - prev[key]
        # The counts are ints, the action rate is a float - one format cannot
        # carry both, and {:+d} on the rate raises.
        shown = f"{diff:+d}" if isinstance(diff, int) else f"{diff:+.2f}"
        return f"   ({shown} since {prev['at'][:10]})"

    lines = [
        "",
        "  Profile performance",
        "  " + "-" * 52,
        f"  Search appearances   {entry.get('search_appearances')}{delta('search_appearances')}",
        f"  Recruiter actions    {entry.get('recruiter_actions')}{delta('recruiter_actions')}",
    ]
    if entry.get("action_rate_pct") is not None:
        lines.append(f"  Action rate          {entry['action_rate_pct']}%"
                     + delta("action_rate_pct"))
    if entry.get("note"):
        lines.append(f"  Note                 {entry['note']}")
    lines += [
        "",
        f"  {len(rows)} reading(s) in data/performance.json",
        "  Appearances rising on a flat action rate means more weak matches,",
        "  not a better profile. The action rate is the number to watch.",
        "",
    ]
    return "\n".join(lines)
