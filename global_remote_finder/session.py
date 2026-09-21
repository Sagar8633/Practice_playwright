"""Session management.

Naukri needs a manual login (Akamai + auth). Global boards (RemoteOK, We Work
Remotely, Remote.co) are public pages that do NOT need a session - they just
need a real browser context.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

log = logging.getLogger("global_remote_finder.session")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
NAUKRI_STATE = DATA_DIR / "naukri_state.json"

NAUKRI_LOGIN_URL = "https://www.naukri.com/nlogin/login"
NAUKRI_LOGGED_IN_MARKERS = ("mnjuser/profile", "mnjuser/homepage", "mnjuser/recommendedjobs")


class NotLoggedIn(RuntimeError):
    """No usable saved Naukri session."""


def _naukri_is_logged_in(page) -> bool:
    url = page.url or ""
    try:
        if "Access Denied" in page.locator("body").inner_text(timeout=3000)[:400]:
            log.warning("Blocked by Akamai bot protection")
            return False
    except Exception:
        pass
    if any(m in url for m in NAUKRI_LOGGED_IN_MARKERS):
        return True
    if "nlogin/login" in url:
        return False
    return False


def naukri_login(state_path=NAUKRI_STATE, timeout_sec: int = 300) -> bool:
    """Sign in to Naukri by hand once, save cookies."""
    from playwright.sync_api import sync_playwright

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(NAUKRI_LOGIN_URL, wait_until="domcontentloaded")

        print("\n  A browser window is open. Sign in to Naukri there.")
        print("  Complete any OTP or captcha as normal - just finish the login.")
        print(f"  Waiting up to {timeout_sec // 60} minutes...\n")

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if _naukri_is_logged_in(page):
                page.wait_for_timeout(3000)
                context.storage_state(path=str(state_path))
                print(f"  Naukri login captured. Session saved to {state_path}")
                browser.close()
                return True
            page.wait_for_timeout(1000)
        print("  Timed out waiting for Naukri login.")
        browser.close()
        return False


def open_naukri(state_path=NAUKRI_STATE, headless: bool = True):
    """Return (playwright, browser, page) on a signed-in Naukri."""
    from playwright.sync_api import sync_playwright

    if not state_path.exists():
        raise NotLoggedIn(
            f"No saved Naukri session at {state_path}. "
            "Run: python -m global_remote_finder.main --naukri-login"
        )
    try:
        json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise NotLoggedIn(f"Session file unreadable ({exc}). Re-run --naukri-login.")

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(
        storage_state=str(state_path),
        viewport={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    if not _naukri_is_logged_in(page):
        browser.close()
        p.stop()
        raise NotLoggedIn("Naukri session expired. Run: python -m global_remote_finder.main --naukri-login")
    return p, browser, page


def open_public() -> tuple:
    """Open a plain browser context for public (non-login) boards."""
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    return p, browser, page


def close(playwright, browser) -> None:
    try:
        browser.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass
