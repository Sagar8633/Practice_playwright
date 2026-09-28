"""The daily nudge: keep the profile at the top of recruiter searches.

Naukri's recruiter search ranks heavily on when a profile was last modified,
so a profile that is never touched sinks below identical ones edited today.
This makes the smallest possible edit - toggling a trailing full stop on the
resume headline - which bumps the modified timestamp without changing what a
human reads.

Run it once a day. Running it more often gains nothing and only makes the
traffic look automated.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from . import selectors as S
from .session import DEFAULT_STATE, open_profile
from .apply import _click_first, _fill_first, _save_and_confirm

log = logging.getLogger("naukri.refresh")

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "data" / "refresh_log.json"


def _toggle_trailing_period(text: str) -> str:
    """Flip a trailing '.' on or off - a real change, invisible in practice."""
    text = text.rstrip()
    return text[:-1] if text.endswith(".") else text + "."


def already_refreshed_today() -> bool:
    """Whether a refresh has already succeeded today."""
    today = datetime.now().date().isoformat()
    for entry in reversed(_entries()):
        if not entry.get("at", "").startswith(today):
            break
        if entry.get("ok"):
            return True
    return False


def refresh(state_path: Path = DEFAULT_STATE, headless: bool = True,
            force: bool = False) -> bool:
    """Bump the profile's last-modified timestamp. Returns True on success.

    Skips if today's bump has already landed. The timestamp only records a date,
    so the second and third runs of a day change nothing a recruiter search can
    see - they just add browser sessions and edit requests against a live
    profile, which is the opposite of what this is for. This module has always
    said "run it once a day"; jobs_scan_and_prep.bat calls it three times, so the
    limit belongs here where it cannot be bypassed by a scheduler entry.

    Pass force=True to bump anyway.
    """
    from playwright.sync_api import sync_playwright

    if not force and already_refreshed_today():
        log.info("Already refreshed today - skipping (use force=True to override)")
        print("  Profile was already refreshed today; nothing to do.")
        return True

    editor = S.EDITORS["resume_headline"]

    with sync_playwright() as p:
        browser, _context, page = open_profile(p, state_path, headless=headless)
        try:
            _click_first(page, editor["trigger"], "resume headline edit button")
            page.wait_for_timeout(1500)

            current = None
            for selector in editor["input"]:
                locator = page.locator(selector).first
                if locator.count():
                    current = locator.input_value(timeout=5000)
                    break
            if not current:
                raise RuntimeError("Could not read the current resume headline.")

            new_text = _toggle_trailing_period(current)
            _fill_first(page, editor["input"], new_text, "resume headline input")
            page.wait_for_timeout(500)
            # Shares apply()'s save path so the longer fallback list and the
            # dialog-closed check cover the nudge too. Before that, this ran on
            # three save selectors and failed outright on 2026-09-06, 09-07 and
            # 09-12 - leaving the headline dirty and the timestamp un-bumped.
            _save_and_confirm(page, editor, "resume_headline")

            _record(True, new_text)
            log.info("Profile refreshed")
            return True
        except Exception as exc:
            log.warning("Refresh failed: %s", exc)
            _record(False, str(exc))
            return False
        finally:
            browser.close()


def _entries() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _record(ok: bool, detail: str) -> None:
    """Append the outcome so a silently-broken scheduled job is visible."""
    entries = _entries()
    entries.append({"at": datetime.now().isoformat(timespec="seconds"), "ok": ok, "detail": detail})
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(entries[-90:], indent=2), encoding="utf-8")
