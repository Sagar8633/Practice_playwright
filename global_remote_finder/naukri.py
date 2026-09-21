"""Naukri search - remote-only, last 24h, across India.

Reads Naukri's own signed /jobapi/v3/search endpoint as the page fetches it.
"""
from __future__ import annotations

import logging
import random
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

log = logging.getLogger("global_remote_finder.naukri")

BASE = "https://www.naukri.com"
SEARCH_API = "jobapi/v3/search"
API_WAIT_SEC = 25


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def search_url(keyword: str, location=None, experience=None,
               page_no=1, job_age=None) -> str:
    path = f"{_slug(keyword)}-jobs"
    if location:
        path += f"-in-{_slug(location)}"
    if page_no > 1:
        path += f"-{page_no}"
    params = {"k": keyword}
    if location:
        params["l"] = location
    if experience is not None:
        params["experience"] = str(int(experience))
    if job_age:
        params["jobAge"] = str(int(job_age))
    if page_no > 1:
        params["pageNo"] = str(page_no)
    return f"{BASE}/{path}?{urlencode(params)}"


def str_search_url(keyword: str, experience=None, job_age=None) -> str:
    return search_url(f"{keyword} remote", None, experience, 1, job_age)


def _capture(page, url, marker) -> list[dict]:
    payloads = []

    def handler(response):
        if marker not in response.url:
            return
        try:
            if "json" not in (response.headers.get("content-type") or ""):
                return
            data = response.json()
        except Exception:
            return
        if isinstance(data, dict) and data.get("jobDetails"):
            payloads.append(data)

    page.on("response", handler)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        deadline = time.time() + API_WAIT_SEC
        while time.time() < deadline and not payloads:
            page.wait_for_timeout(500)
        if not payloads:
            page.mouse.wheel(0, 1600)
            page.wait_for_timeout(3000)
    except Exception as exc:
        log.warning("Navigation failed for %s: %s", url, str(exc)[:160])
    finally:
        page.remove_listener("response", handler)

    records = []
    for payload in payloads:
        records.extend(payload.get("jobDetails") or [])
    return records


def _placeholder(record, kind):
    for item in record.get("placeholders") or []:
        if item.get("type") == kind:
            return (item.get("label") or "").strip() or None
    return None


def _normalize(record, source) -> dict:
    jd_url = record.get("jdURL") or record.get("staticUrl") or ""
    if jd_url and not jd_url.startswith("http"):
        jd_url = BASE + jd_url
    skills = [s.strip() for s in (record.get("tagsAndSkills") or "").split(",") if s.strip()]
    location = _placeholder(record, "location") or ""
    created_ms = record.get("createdDate")
    age_days = None
    if created_ms:
        try:
            posted = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            age_days = (datetime.now(tz=timezone.utc) - posted).total_seconds() / 86400
        except Exception:
            pass
    return {
        "job_id": f"naukri:{record.get('jobId')}",
        "title": (record.get("title") or "").strip(),
        "company": (record.get("companyName") or "").strip(),
        "location": location,
        "url": jd_url or "",
        "posted": record.get("footerPlaceholderLabel") or "",
        "source": "Naukri",
        "experience": _placeholder(record, "experience"),
        "salary": _placeholder(record, "salary"),
        "skills": skills,
        "age_days": age_days,
        "company_apply": bool(record.get("companyApplyJob")),
        "has_questionnaire": bool(record.get("questionnaireIdPresent")),
        "_naukri": True,
    }


def remote_marker_match(location_text: str, markers) -> bool:
    lt = (location_text or "").lower()
    return any(m in lt for m in markers)


def gather(page, config, experience=None) -> list[dict]:
    """Search all configured keywords; return normalized remote jobs."""
    found: dict[str, dict] = {}
    keywords = [k for k in config.get("keywords", []) if k]
    markers = [m.lower() for m in config.get("naukri", {}).get("remote_location_markers",
              ["remote", "work from home", "wfh", "anywhere in india"])]
    pages = max(1, int(config.get("naukri", {}).get("pages_per_keyword", 2)))

    for keyword in keywords:
        for page_no in range(1, pages + 1):
            url = str_search_url(keyword, experience, job_age=1)
            if page_no > 1:
                url = search_url(f"{keyword} remote", None, experience, page_no, job_age=1)
            label = f"{keyword} remote" + (f" p{page_no}" if page_no > 1 else "")
            records = _capture(page, url, SEARCH_API)
            added = 0
            for record in records:
                job = _normalize(record, source=label)
                if not job["job_id"] or not job["url"]:
                    continue
                # Remote-only gate
                if not remote_marker_match(job["location"], markers):
                    continue
                if job["job_id"] not in found:
                    found[job["job_id"]] = job
                    added += 1
            log.info("  Naukri %s: +%d new (%d total)", label, added, len(found))
            time.sleep(random.uniform(2.5, 6.0))
    log.info("Naukri collected %d remote jobs", len(found))
    return list(found.values())
