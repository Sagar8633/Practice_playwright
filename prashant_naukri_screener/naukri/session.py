"""Log in once by hand, reuse that session forever after.

The password never touches this codebase. `login()` opens a real browser,
parks on Naukri's login page and waits for *you* to sign in - which means
OTP, captcha and device-verification all just work, because a human is
there for them. The resulting cookies are written to data/state.json and
every later run loads that file instead of logging in again.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from . import selectors as S

log = logging.getLogger("naukri.session")

DEFAULT_STATE = Path(__file__).resolve().parent.parent / "data" / "state.json"


class NotLoggedIn(RuntimeError):
    """Raised when no usable saved session exists."""


def is_logged_in(page) -> bool:
    """Best-effort check that the current page belongs to a signed-in user."""
    url = page.url or ""

    # Naukri sits behind Akamai, which serves an "Access Denied" body while
    # leaving the requested URL in the address bar. Without this check the URL
    # marker below matches and we report a healthy session for a blocked page.
    try:
        if "Access Denied" in page.locator("body").inner_text(timeout=3000)[:400]:
            log.warning("Blocked by Akamai bot protection - run with a visible browser")
            return False
    except Exception:
        pass

    if any(marker in url for marker in S.LOGGED_IN_URL_MARKERS):
        return True
    if "nlogin/login" in url:
        return False
    for selector in S.LOGGED_IN_MARKERS:
        try:
            if page.locator(selector).first.is_visible(timeout=1500):
                return True
        except Exception:
            continue
    return False


def login(state_path: Path = DEFAULT_STATE, timeout_sec: int = 300) -> bool:
    """Open a browser, wait for a manual login, save the session.

    Returns True once cookies are captured, False on timeout.
    """
    from playwright.sync_api import sync_playwright

    state_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Headed on purpose - a human is completing this flow.
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(S.LOGIN_URL, wait_until="domcontentloaded")

        print("\n  A browser window is open. Sign in to Naukri there.")
        print("  Complete any OTP or captcha as normal - just finish the login.")
        print(f"  Waiting up to {timeout_sec // 60} minutes...\n")

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if is_logged_in(page):
                # Let the post-login redirects settle before snapshotting cookies.
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


def open_profile(p, state_path: Path = DEFAULT_STATE, headless: bool = True):
    """Return (browser, context, page) sitting on the profile page.

    Raises NotLoggedIn if the saved session is missing or has expired, so
    callers can tell the user to re-run `--login` instead of failing on a
    confusing selector timeout further down.
    """
    if not state_path.exists():
        raise NotLoggedIn(f"No saved session at {state_path}. Run: python main.py --login")

    try:
        json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise NotLoggedIn(f"Session file at {state_path} is unreadable ({exc}). Re-run --login.")

    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(
        storage_state=str(state_path),
        viewport={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.goto(S.PROFILE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)  # profile widgets lazy-load after first paint

    if not is_logged_in(page):
        browser.close()
        raise NotLoggedIn("Saved session has expired. Run: python main.py --login")

    _resave(context, state_path)
    return browser, context, page


def _resave(context, state_path: Path) -> None:
    """Write the session back, so a working login stops decaying on disk.

    Naukri issues a short-lived access cookie alongside the long-lived ones and
    reissues it during each visit, but the file was only ever written once at
    login - so the saved state drifts further out of date every day it is used.
    On 2026-09-12 the stored nauk_at had been expired for three weeks while runs
    kept working purely off the long-lived cookies; that is a login living on
    borrowed time, and it fails on whichever morning Naukri stops accepting it.

    Best-effort and atomic: a half-written state.json is worse than a stale one,
    because it locks every later run out until --login is run by hand.
    """
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    try:
        context.storage_state(path=str(tmp))
        tmp.replace(state_path)
        log.debug("Session refreshed on disk")
    except Exception as exc:
        log.debug("Could not re-save session (harmless): %s", exc)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
