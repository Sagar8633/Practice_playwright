"""LinkedIn session management - manual login with persistent cookies.

Same approach as naukri_profile: you sign in by hand in a real browser,
so 2FA, captcha and device verification all work because a human is there.
The password never enters this codebase. Cookies land in data/session.json.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

log = logging.getLogger("linkedin_finder.session")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "session.json"

LOGIN_URL = "https://www.linkedin.com/login"
JOBS_URL = "https://www.linkedin.com/jobs/search/"

LOGGED_IN_URL_MARKERS = ("/feed", "/jobs", "/mynetwork", "/in/")
LOGGED_IN_MARKERS = [
    "img.global-nav__me-photo",
    ".global-nav__me",
    "[data-test-global-nav]",
    "#global-nav",
]


class NotLoggedIn(RuntimeError):
    """No usable saved LinkedIn session."""


def is_logged_in(page, strict: bool = False) -> bool:
    """Is this page a signed-in LinkedIn?"""
    url = page.url or ""
    if "/login" in url or "/checkpoint" in url or "/authwall" in url:
        return False
    markers = LOGGED_IN_URL_MARKERS
    if strict:
        try:
            if page.locator('a[href*="/authwall"]').first.is_visible(timeout=1500):
                return False
        except Exception:
            pass
        markers = tuple(m for m in markers if m != "/jobs")
    if any(marker in url for marker in markers):
        return True
    for selector in LOGGED_IN_MARKERS:
        try:
            if page.locator(selector).first.is_visible(timeout=1500):
                return True
        except Exception:
            continue
    return strict


def login(state_path: Path = STATE_PATH, timeout_sec: int = 420) -> bool:
    """Open a browser, wait for a manual sign-in, save the session."""
    from playwright.sync_api import sync_playwright

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("\n  A browser window is open. Sign in to LinkedIn there.")
        print("  Complete any 2FA or captcha as normal - just finish the login.")
        print(f"  Waiting up to {timeout_sec // 60} minutes...\n")

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if is_logged_in(page):
                page.wait_for_timeout(3000)
                context.storage_state(path=str(state_path))
                log.info("LinkedIn session saved to %s", state_path)
                print(f"  Login captured. Session saved to {state_path}")
                browser.close()
                return True
            page.wait_for_timeout(1000)

        print("  Timed out waiting for login.")
        browser.close()
        return False


def open_session(state_path: Path = STATE_PATH, headless: bool = False):
    """Return (browser, context, page) on a signed-in LinkedIn."""
    from playwright.sync_api import sync_playwright

    if not state_path.exists():
        raise NotLoggedIn(
            f"No saved LinkedIn session at {state_path}. "
            "Run: python -m linkedin_finder.main --login"
        )

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(
        storage_state=str(state_path),
        viewport={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.goto(JOBS_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)

    if not is_logged_in(page, strict=True):
        browser.close()
        p.stop()
        raise NotLoggedIn(
            "Saved LinkedIn session has expired. Run: python -m linkedin_finder.main --login"
        )
    return p, browser, context, page


def close_session(playwright, browser) -> None:
    """Clean up browser and playwright instance."""
    try:
        browser.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass
