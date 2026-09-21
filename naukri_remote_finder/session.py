"""Naukri session management - manual login with persistent cookies.

Same pattern as naukri_profile: you sign in by hand in a real browser,
so OTP, captcha and device-verification all work. The password never
enters this codebase. Cookies land in data/state.json.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

log = logging.getLogger("naukri_remote_finder.session")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "state.json"

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
HOME_URL = "https://www.naukri.com/"

LOGGED_IN_URL_MARKERS = ("mnjuser/profile", "mnjuser/homepage", "mnjuser/recommendedjobs")
LOGGED_IN_MARKERS = [
    ".view-profile-wrapper",
    ".nI-gNb-drawer__bars",
    "[data-ga-track*='My Naukri']",
    ".mn-hdr",
]


class NotLoggedIn(RuntimeError):
    """No usable saved Naukri session."""


def is_logged_in(page) -> bool:
    """Best-effort check that the current page belongs to a signed-in user."""
    url = page.url or ""
    try:
        if "Access Denied" in page.locator("body").inner_text(timeout=3000)[:400]:
            log.warning("Blocked by Akamai bot protection - run with a visible browser")
            return False
    except Exception:
        pass
    if any(marker in url for marker in LOGGED_IN_URL_MARKERS):
        return True
    if "nlogin/login" in url:
        return False
    for selector in LOGGED_IN_MARKERS:
        try:
            if page.locator(selector).first.is_visible(timeout=1500):
                return True
        except Exception:
            continue
    return False


def login(state_path: Path = STATE_PATH, timeout_sec: int = 300) -> bool:
    """Open a browser, wait for a manual login, save the session."""
    from playwright.sync_api import sync_playwright

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("\n  A browser window is open. Sign in to Naukri there.")
        print("  Complete any OTP or captcha as normal - just finish the login.")
        print(f"  Waiting up to {timeout_sec // 60} minutes...\n")

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if is_logged_in(page):
                page.wait_for_timeout(3000)
                context.storage_state(path=str(state_path))
                log.info("Session saved to %s", state_path)
                print(f"  Login captured. Session saved to {state_path}")
                browser.close()
                return True
            page.wait_for_timeout(1000)

        print("  Timed out waiting for login.")
        browser.close()
        return False


def open_session(state_path: Path = STATE_PATH, headless: bool = True):
    """Return (playwright, browser, context, page) on a signed-in Naukri."""
    from playwright.sync_api import sync_playwright

    if not state_path.exists():
        raise NotLoggedIn(
            f"No saved session at {state_path}. "
            "Run: python -m naukri_remote_finder.main --login"
        )
    try:
        json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise NotLoggedIn(f"Session file at {state_path} is unreadable ({exc}). Re-run --login.")

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(
        storage_state=str(state_path),
        viewport={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.goto(PROFILE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    if not is_logged_in(page):
        browser.close()
        p.stop()
        raise NotLoggedIn(
            "Saved session has expired. Run: python -m naukri_remote_finder.main --login"
        )
    return p, browser, context, page


def close_session(playwright, browser) -> None:
    try:
        browser.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass
