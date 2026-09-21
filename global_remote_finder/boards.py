"""Global remote job board sources.

These boards are PUBLIC pages - no login required - and are scraped HEADLESS
for speed. Each board runs in its own browser context wrapped in a hard
timeout, so one slow/blocking board never hangs the whole run.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from urllib.parse import quote_plus

log = logging.getLogger("global_remote_finder.boards")

REMOTEOK = "https://remoteok.com/remote-{slug}-jobs"
WEWORKREMOTELY = "https://weworkremotely.com/remote-jobs/search?term={term}"
REMOTIVE_API = "https://remotive.com/api/remote-jobs?limit=50&search={term}"


def _norm(s):
    return " ".join((s or "").split()).strip()


def _run_with_timeout(fn, *args, timeout_sec: int = 90):
    """Run fn in a thread; kill-abandon after timeout_sec."""
    result: dict = {}

    def worker():
        try:
            result["value"] = fn(*args)
        except Exception as exc:
            result["error"] = exc

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        log.warning("Board scrape exceeded %ds timeout - abandoning", timeout_sec)
        return []
    if "error" in result:
        log.warning("Board scrape error: %s", result["error"][:160])
        return []
    return result.get("value", [])


def _make_page(headless: bool = True):
    """Launch a fresh browser context for a public board."""
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(
        viewport={"width": 1440, "height": 2000},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"),
    )
    page = context.new_page()
    return p, browser, page


def _remoteok_slug(word: str) -> str | None:
    w = word.lower()
    mapping = {
        "qa": "qa", "test": "qa", "testing": "qa", "sdet": "qa",
        "automation": "qa", "quality": "qa",
        "python": "python", "devops": "devops", "backend": "backend",
        "frontend": "frontend", "fullstack": "fullstack",
    }
    for key, slug in mapping.items():
        if key in w:
            return slug
    return None


def remoteok(keywords, headless: bool = True) -> list[dict]:
    """Scrape RemoteOK headless. Returns job dicts."""
    p = b = pg = None
    try:
        p, b, pg = _make_page(headless)
        out: dict[str, dict] = {}
        slugs = set()
        for word in keywords:
            s = _remoteok_slug(word)
            if s:
                slugs.add(s)
        if not slugs:
            slugs = {"qa", "automation"}
        for slug in slugs:
            url = REMOTEOK.format(slug=slug)
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(2500)
                cards = pg.locator("tr.job")
                count = cards.count()
                for i in range(count):
                    try:
                        card = cards.nth(i)
                        jid = card.evaluate("el => el.getAttribute('data-id') || ''") or str(i)
                        # The job title link is the anchor whose href ends with the
                        # job id and points at /remote-jobs/remote-* (not the /l/ apply
                        # link, not the +category tag links).
                        title_link = None
                        title = ""
                        for a in card.locator("a").all():
                            href = a.get_attribute("href") or ""
                            if href.endswith(jid) and "/remote-jobs/remote-" in href:
                                t = _norm(a.inner_text())
                                if t:
                                    title_link, title = href, t
                                    break
                        if not title_link:
                            continue
                        full = title_link if title_link.startswith("http") else "https://remoteok.com" + title_link
                        comp = card.locator("h3").first
                        loc = card.locator(".location").first
                        out.setdefault(f"remoteok:{slug}:{jid}", {
                            "job_id": f"remoteok:{slug}:{jid}",
                            "title": title,
                            "company": _norm(comp.inner_text()) if comp.count() else "",
                            "location": _norm(loc.inner_text()) if loc.count() else "Remote",
                            "url": full,
                            "posted": "",
                            "source": "RemoteOK",
                        })
                    except Exception:
                        continue
                log.info("  RemoteOK [%s]: %d cards", slug, count)
            except Exception as exc:
                log.warning("RemoteOK [%s] failed: %s", slug, str(exc)[:120])
            time.sleep(random.uniform(1.5, 3.0))
        return list(out.values())
    finally:
        _close(p, b)


def weworkremotely(keywords, headless: bool = True) -> list[dict]:
    p = b = None
    try:
        p, b, pg = _make_page(headless)
        out: dict[str, dict] = {}
        terms = set(w for w in keywords if w and len(w.replace(" ", "")) > 2)
        if not terms:
            terms = {"qa", "software"}
        for term in terms:
            url = WEWORKREMOTELY.format(term=quote_plus(term))
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(2500)
                links = pg.locator("a[href*='/remote-jobs/']")
                count = links.count()
                for i in range(count):
                    try:
                        link = links.nth(i)
                        href = link.get_attribute("href") or ""
                        # skip nav/CTA links
                        if any(s in href for s in ("utm", "find-your-plan")):
                            continue
                        title_el = link.locator(".new-listing__header__title__text").first
                        comp_el = link.locator(".new-listing__company-name").first
                        hq_el = link.locator(".new-listing__company-headquarters").first
                        cat_el = link.locator(".new-listing__categories__category").first
                        date_el = link.locator(".new-listing__header__icons__date").first
                        txt = _norm(title_el.inner_text()) if title_el.count() else ""
                        if not txt:
                            continue
                        full = href if href.startswith("http") else "https://weworkremotely.com" + href
                        loc = _norm(hq_el.inner_text()) if hq_el.count() else ""
                        cat = _norm(cat_el.inner_text()) if cat_el.count() else ""
                        if loc and cat:
                            loc = f"{cat} | {loc}".strip()
                        elif cat:
                            loc = cat
                        out.setdefault(f"wwr:{term}:{full}", {
                            "job_id": f"wwr:{term}:{full}",
                            "title": txt,
                            "company": _norm(comp_el.inner_text()) if comp_el.count() else "",
                            "location": loc or "Remote",
                            "url": full,
                            "posted": _norm(date_el.inner_text()) if date_el.count() else "",
                            "source": "WeWorkRemotely",
                        })
                    except Exception:
                        continue
                log.info("  WeWorkRemotely [%s]: %d links", term, count)
            except Exception as exc:
                log.warning("WeWorkRemotely [%s] failed: %s", term, str(exc)[:120])
            time.sleep(random.uniform(1.5, 3.0))
        return list(out.values())
    finally:
        _close(p, b)


def remoteco(keywords, headless: bool = True) -> list[dict]:
    p = b = None
    try:
        p, b, pg = _make_page(headless)
        out: dict[str, dict] = {}
        try:
            pg.goto(REMOTECO, wait_until="domcontentloaded", timeout=30000)
            pg.wait_for_timeout(2500)
            # Remote.co lists jobs as divs with class job-listing or similar
            rows = pg.locator('[class*="job-listing"], [class*="job-listing__"], .job h3 a')
            count = rows.count()
            for i in range(count):
                try:
                    el = rows.nth(i)
                    # find the anchor
                    a = el.locator("a[href*='/job/']").first
                    if not a.count():
                        a = el if el.evaluate("e => e.tagName==='A'") else None
                        if a is None:
                            continue
                    txt = _norm(a.inner_text()) if a.count() else ""
                    if not txt:
                        continue
                    href = a.get_attribute("href") or ""
                    full = href if href.startswith("http") else "https://remote.co" + href
                    out.setdefault(f"remoteco:{i}:{full}", {
                        "job_id": f"remoteco:{i}:{full}",
                        "title": txt,
                        "company": "",
                        "location": "Remote",
                        "url": full,
                        "posted": "",
                        "source": "Remote.co",
                    })
                except Exception:
                    continue
            log.info("  Remote.co: %d rows", count)
        except Exception as exc:
            log.warning("Remote.co failed: %s", str(exc)[:120])
        return list(out.values())
    finally:
        _close(p, b)


def _close(playwright, browser) -> None:
    try:
        browser.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass


def run_board(board_fn, keywords, headless: bool = True, timeout_sec: int = 120):
    """Run one board with a hard timeout."""
    return _run_with_timeout(
        lambda: board_fn(keywords, headless=headless),
        timeout_sec=timeout_sec,
    )


def remotive(keywords, headless: bool = True) -> list[dict]:
    """Remotive - public JSON API, no browser required. Reliable + structured.

    Returns QA/tech/test relevant remote jobs. `headless` is ignored here.
    """
    import json
    import urllib.request

    terms = set()
    relevance = {
        "qa": 0, "test": 0, "sdet": 0, "automation": 0, "quality": 0,
        "python": 1, "devops": 1, "backend": 1, "software": 1,
    }
    for w in keywords:
        wl = w.lower()
        for k in relevance:
            if k in wl:
                terms.add(k)
    if not terms:
        terms = {"qa", "software"}

    out: dict[str, dict] = {}
    for term in terms:
        url = REMOTIVE_API.format(term=quote_plus(term))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.load(r)
            for j in data.get("jobs", []):
                jid = f"remotive:{j.get('id')}"
                tags = " ".join((j.get("tags") or []) + [j.get("category") or ""])
                out.setdefault(jid, {
                    "job_id": jid,
                    "title": (j.get("title") or "").strip(),
                    "company": (j.get("company_name") or "").strip(),
                    "location": (j.get("candidate_required_location") or "Remote").strip(),
                    "url": j.get("url") or j.get("application_url") or "",
                    "posted": j.get("publication_date") or "",
                    "salary": (j.get("salary") or "").strip(),
                    "skills": [t for t in (j.get("tags") or [])],
                    "source": "Remotive",
                    "age_days": _remotive_age_days(j.get("publication_date")),
                })
            log.info("  Remotive [%s]: %d jobs", term, len(data.get("jobs", [])))
        except Exception as exc:
            log.warning("Remotive [%s] failed: %s", term, str(exc)[:120])
        time.sleep(1.0)
    return list(out.values())


def _remotive_age_days(iso: str):
    if not iso:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        return None
