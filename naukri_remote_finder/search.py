"""Naukri job search - remote-only, posted in the last 24 hours, across India.

Reuses the same architecture as naukri_profile: read Naukri's OWN signed JSON
endpoints (/jobapi/v3/search) as the page fetches them, rather than scraping
rendered cards. These endpoints are signed and only answer to the page's own
fetch, so each result costs one real navigation through a logged-in browser.

Remote-only is enforced in two ways:
  1. The keyword is suffixed with "remote" where useful, and
  2. Every result's location placeholder is checked against remote markers -
     a listing is only kept if it states Remote / Work From Home / WFH.
"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from urllib.parse import urlencode

log = logging.getLogger("naukri_remote_finder.search")

BASE = "https://www.naukri.com"
SEARCH_API = "jobapi/v3/search"
API_WAIT_SEC = 25


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def search_url(keyword: str, location: str | None = None,
               experience: float | None = None, page_no: int = 1,
               job_age: int | None = None) -> str:
    """Build the same URL the site's own search box would produce.

    `job_age` is Naukri's own Freshness facet, in days - the same filter as
    clicking "Last 1 day" in the sidebar. Moving the filter to where the
    ranking happens matters: a query returns ~20 results ranked by relevance,
    not by date, so filtering a stale page afterwards would leave nothing.
    """
    path = f"{_slug(keyword)}-jobs"
    if location:
        path += f"-in-{_slug(location)}"
    if page_no > 1:
        path += f"-{page_no}"

    params: dict[str, str] = {"k": keyword}
    if location:
        params["l"] = location
    if experience is not None:
        params["experience"] = str(int(experience))
    if job_age:
        params["jobAge"] = str(int(job_age))
    if page_no > 1:
        params["pageNo"] = str(page_no)
    return f"{BASE}/{path}?{urlencode(params)}"


def _capture(page, url: str, marker: str) -> list[dict]:
    """Navigate and return the jobDetails from the page's own API call."""
    payloads: list[dict] = []

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

    records: list[dict] = []
    for payload in payloads:
        records.extend(payload.get("jobDetails") or [])
    return records


def _pause() -> None:
    time.sleep(random.uniform(2.5, 6.0))


@dataclass
class Job:
    job_id: str
    title: str
    company: str
    url: str
    skills: list = field(default_factory=list)
    location: str | None = None
    experience_label: str | None = None
    salary_label: str | None = None
    experience: float | None = None
    description: str = ""
    posted_label: str | None = None
    created_ms: int | None = None
    company_apply: bool = False
    has_questionnaire: bool = False
    source: str = ""

    @property
    def age_days(self) -> float | None:
        """How long ago the job was posted, in days."""
        if not self.created_ms:
            return None
        try:
            posted = datetime.fromtimestamp(self.created_ms / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
        return (datetime.now(tz=timezone.utc) - posted).total_seconds() / 86400

    @property
    def is_remote(self) -> bool:
        text = (self.location or "").lower()
        for marker in ("remote", "work from home", "wfh", "anywhere in india"):
            if marker in text:
                return True
        return False

    @property
    def auto_applicable(self) -> bool:
        return not self.company_apply and not self.has_questionnaire

    def to_dict(self) -> dict:
        return asdict(self)


def _placeholder(record: dict, kind: str) -> str | None:
    for item in record.get("placeholders") or []:
        if item.get("type") == kind:
            label = (item.get("label") or "").strip()
            return label or None
    return None


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"&amp;?", "&", text)
    return re.sub(r"\s+", " ", text).strip()


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _from_api(record: dict, source: str = "") -> Job:
    jd_url = record.get("jdURL") or record.get("staticUrl") or ""
    if jd_url and not jd_url.startswith("http"):
        jd_url = BASE + jd_url
    raw_skills = record.get("tagsAndSkills") or ""
    skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
    return Job(
        job_id=str(record.get("jobId") or ""),
        title=(record.get("title") or "").strip(),
        company=(record.get("companyName") or "").strip(),
        url=jd_url,
        skills=skills,
        location=_placeholder(record, "location"),
        experience_label=_placeholder(record, "experience"),
        salary_label=_placeholder(record, "salary"),
        experience=_as_float(record.get("minimumExperience")),
        description=_strip_html(record.get("jobDescription")),
        posted_label=record.get("footerPlaceholderLabel"),
        created_ms=record.get("createdDate"),
        company_apply=bool(record.get("companyApplyJob")),
        has_questionnaire=bool(record.get("questionnaireIdPresent")),
        source=source,
    )


def str_search_url(keyword: str, remote_marker: str = "remote",
                   experience: float | None = None,
                   job_age: int | None = None) -> str:
    """Build a URL where the keyword itself carries the remote term.

    Using "remote" in the keyword is a strong signal to Naukri's ranking. The
    location is left blank so the search spans all of India.
    """
    kw = keyword
    if remote_marker and remote_marker.lower() not in kw.lower():
        kw = f"{keyword} {remote_marker}"
    return search_url(kw, None, experience, 1, job_age)


def gather(page, keywords: list[str], experience: float | None = None,
           job_age: int | None = None, pages: int = 1,
           remote_marker: str = "remote") -> list[Job]:
    """Run every keyword search; dedupe by jobId. Returns all jobs (any location)."""
    found: dict[str, Job] = {}
    for keyword in keywords:
        for page_no in range(1, pages + 1):
            url = str_search_url(keyword, remote_marker, experience, job_age)
            if page_no > 1:
                url = url.replace(f"pageNo={page_no - 1}", f"pageNo={page_no}") if "pageNo" in url \
                    else url + (("&" if "?" in url else "?") + f"pageNo={page_no}")
            label = f"{keyword} remote" + (f" p{page_no}" if page_no > 1 else "")
            records = _capture(page, url, SEARCH_API)
            added = 0
            for record in records:
                job = _from_api(record, source=f"search:{label}")
                if not job.job_id or not job.url:
                    continue
                if job.job_id not in found:
                    found[job.job_id] = job
                    added += 1
            log.info("  %s: +%d new (%d total)", label, added, len(found))
            _pause()
    log.info("Collected %d distinct jobs", len(found))
    return list(found.values())


def filter_remote_only(jobs: list[Job], config: dict) -> list[Job]:
    """Keep only listings that state a remote/work-from-home location."""
    markers = [m.lower() for m in config.get("remote_location_markers",
              ["remote", "work from home", "wfh", "anywhere in india"])]
    exclude_titles = [t.lower() for t in config.get("exclude_titles", [])]
    exclude_companies = [c.lower() for c in config.get("exclude_companies", [])]
    posted_days = config.get("posted_days")

    kept = []
    skipped_not_remote = 0
    for job in jobs:
        title = (job.title or "").lower()
        company = (job.company or "").lower()
        location_text = (job.location or "").lower()

        # Remote-only gate: must state a remote location
        if not any(m in location_text for m in markers):
            skipped_not_remote += 1
            continue
        if any(ex in title for ex in exclude_titles):
            continue
        if any(ex in company for ex in exclude_companies):
            continue
        # Freshness gate (posted within N days)
        if posted_days:
            age = job.age_days
            if age is None or age > posted_days:
                continue
        kept.append(job)

    log.info("Kept %d remote jobs (%d excluded as not-remote)",
             len(kept), skipped_not_remote)
    return kept
