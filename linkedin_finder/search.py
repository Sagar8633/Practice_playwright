"""LinkedIn job search with multi-keyword support and scroll-to-load.

Searches LinkedIn's public job listings using the f_WT=2 remote filter.
Only reads data - never applies, messages, or touches anything else.
"""
from __future__ import annotations

import logging
import math
import random
import re
import time
from urllib.parse import urlencode

log = logging.getLogger("linkedin_finder.search")

JOBS_URL = "https://www.linkedin.com/jobs/search/"

RETRYABLE_ERRORS = (
    "ERR_NETWORK_CHANGED",
    "ERR_INTERNET_DISCONNECTED",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_CONNECTION",
    "Timeout",
)

# JavaScript to extract job cards from the page.
# Uses stable design-system class names, not per-build hashed classes.
_EXTRACT_JS = r"""
() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const pick = (root, sel) => {
    const el = root.querySelector(sel);
    return el ? norm(el.innerText) : null;
  };
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href*="/jobs/view/"]').forEach(anchor => {
    const card = anchor.closest('li') || anchor.closest('[data-job-id]');
    if (!card) return;
    const href = anchor.getAttribute('href') || '';
    const match = href.match(/\/jobs\/view\/(\d+)/);
    if (!match) return;
    const jobId = match[1];
    if (seen.has(jobId)) return;
    seen.add(jobId);

    const title = pick(card, '.artdeco-entity-lockup__title strong')
               || pick(card, '.artdeco-entity-lockup__title')
               || norm(anchor.getAttribute('aria-label') || anchor.innerText);

    const meta = Array.from(card.querySelectorAll('.job-card-container__metadata-wrapper li'))
      .map(li => norm(li.innerText)).filter(Boolean);
    const footer = Array.from(card.querySelectorAll('.job-card-container__footer-item'))
      .map(li => norm(li.innerText)).filter(Boolean);
    const text = norm(card.innerText);

    out.push({
      job_id: jobId,
      url: 'https://www.linkedin.com/jobs/view/' + jobId + '/',
      title: title,
      company: pick(card, '.artdeco-entity-lockup__subtitle'),
      location: pick(card, '.artdeco-entity-lockup__caption'),
      metadata: meta,
      footer: footer,
      insight: pick(card, '.job-card-container__job-insight-text'),
      easy_apply: /easy apply/i.test(text),
      promoted: /promoted/i.test(text),
      viewed: /\bviewed\b/i.test(text),
    });
  });
  return out;
}
"""


def search_url(keyword: str, location: str | None = None,
               posted_days: int | None = 30, start: int = 0,
               remote_only: bool = True) -> str:
    """Build a LinkedIn job-search URL."""
    params: dict[str, str] = {"keywords": keyword}
    params["location"] = location or "Worldwide"
    if posted_days:
        params["f_TPR"] = f"r{posted_days * 86400}"
    if remote_only:
        params["f_WT"] = "2"
    if start:
        params["start"] = str(start)
    return f"{JOBS_URL}?{urlencode(params)}"


def pause() -> None:
    """Human-paced spacing between navigations."""
    time.sleep(random.uniform(3.5, 8.0))


def _load_all_cards(page, want: int = 25, rounds: int = 14) -> int:
    """Scroll results into view until the card count stops growing.

    LinkedIn renders about nine cards and lazy-loads the rest as they are
    scrolled to. The results list is its own scroll container, so walking
    the last card into view triggers the lazy load.
    """
    previous = 0
    stable = 0
    for _ in range(rounds):
        count = page.evaluate(
            """() => {
                const links = document.querySelectorAll('a[href*="/jobs/view/"]');
                if (!links.length) return 0;
                const last = links[links.length - 1].closest('li') || links[links.length - 1];
                let el = last.parentElement;
                while (el && el !== document.body) {
                  const style = getComputedStyle(el);
                  if (/(auto|scroll)/.test(style.overflowY)
                      && el.scrollHeight > el.clientHeight + 40) {
                    el.scrollTop = Math.min(el.scrollTop + el.clientHeight * 0.9,
                                            el.scrollHeight);
                    return links.length;
                  }
                  el = el.parentElement;
                }
                last.scrollIntoView({block: 'end'});
                window.scrollBy(0, 700);
                return links.length;
            }"""
        )
        if count >= want:
            break
        stable = stable + 1 if count == previous else 0
        if stable >= 2:
            break
        previous = count
        page.wait_for_timeout(2000)
    page.wait_for_timeout(800)
    return page.evaluate(
        "() => document.querySelectorAll('a[href*=\\\"/jobs/view/\\\"]').length"
    )


def search_one(page, keyword: str, location: str | None = None,
               posted_days: float | None = 30, pages: int = 1,
               remote_only: bool = True) -> list[dict]:
    """Return raw card dicts for one keyword/location, across `pages` pages."""
    found: dict[str, dict] = {}
    for index in range(pages):
        url = search_url(keyword, location,
                         max(1, math.ceil(posted_days)) if posted_days else None,
                         index * 25, remote_only)
        cards = None
        for attempt in (1, 2):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
                loaded = _load_all_cards(page)
                cards = page.evaluate(_EXTRACT_JS)
                break
            except Exception as exc:
                detail = str(exc)
                if attempt == 1 and any(e in detail for e in RETRYABLE_ERRORS):
                    log.warning("Transport error for %s: %s - retrying once",
                                keyword, detail[:160])
                    time.sleep(random.uniform(25, 45))
                    continue
                log.warning("Search failed for %s: %s", keyword, detail[:160])
                break
        if cards is None:
            continue
        added = 0
        for card in cards:
            if card["job_id"] not in found:
                card["source"] = (f"linkedin:{keyword}"
                                  + (" remote" if remote_only else "")
                                  + (f" in {location}" if location else " worldwide"))
                card["remote_filtered"] = remote_only
                found[card["job_id"]] = card
                added += 1
        log.info("  %s%s p%d: %d loaded, +%d new",
                 keyword, f" in {location}" if location else "", index + 1, loaded, added)
        if not added:
            break
        pause()
    return list(found.values())


def search_all(page, keywords: list[str], location: str | None = None,
               posted_days: float | None = 30, pages_per_keyword: int = 1,
               remote_only: bool = True) -> list[dict]:
    """Search multiple keywords and merge results."""
    all_cards: dict[str, dict] = {}
    for keyword in keywords:
        log.info("Searching: %s", keyword)
        cards = search_one(page, keyword, location, posted_days,
                           pages_per_keyword, remote_only)
        for card in cards:
            all_cards[card["job_id"]] = card
        pause()
    return list(all_cards.values())


def filter_cards(cards: list[dict], config: dict) -> list[dict]:
    """Filter cards based on config rules (exclusions, location preferences)."""
    exclude_titles = [t.lower() for t in config.get("exclude_titles", [])]
    exclude_companies = [c.lower() for c in config.get("exclude_companies", [])]
    preferred = [l.lower() for l in config.get("preferred_locations", ["remote"])]

    kept = []
    for card in cards:
        title = (card.get("title") or "").lower()
        company = (card.get("company") or "").lower()

        # Exclude by title
        if any(ex in title for ex in exclude_titles):
            continue
        # Exclude by company
        if any(ex in company for ex in exclude_companies):
            continue

        # Score location preference (lower = better)
        location_text = (card.get("location") or "").lower()
        pref_score = len(preferred)  # default: worst
        for i, pref in enumerate(preferred):
            if pref in location_text:
                pref_score = i
                break
        card["_pref_score"] = pref_score
        card["_remote"] = bool(card.get("remote_filtered")) or "remote" in location_text

        kept.append(card)

    # Remote first, then by preference, then by job_id (newest first on LinkedIn)
    kept.sort(key=lambda c: (not c["_remote"], c["_pref_score"], -int(c.get("job_id", 0))))
    return kept
