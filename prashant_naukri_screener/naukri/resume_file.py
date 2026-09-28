"""Replace the resume attached to the profile.

Worth knowing before using this: Naukri re-runs its resume parser on upload, and
the parser can overwrite fields that were set by hand - headline, summary, key
skills. This module therefore snapshots the fields it could clobber, uploads,
re-reads them, and reports anything that changed, so a silent rollback of a
careful edit shows up as output rather than as a mystery three weeks later.

Resdex full-text searches the attached resume, so the file is worth keeping
current - but upload deliberately, check the diff, and re-apply changes.yaml if
the parser has undone something.

    python main.py --upload-resume
    python main.py --upload-resume --file path/to/other.pdf
"""
from __future__ import annotations

import logging
from pathlib import Path

from . import extract as extract_mod
from . import selectors as S
from .session import DEFAULT_STATE, open_profile

log = logging.getLogger("naukri.resume")

ROOT = Path(__file__).resolve().parent.parent
RESUME_DIR = ROOT / "resume"

# Fields Naukri's parser is known to rewrite on upload.
AT_RISK = ("resume_headline", "profile_summary", "key_skills", "it_skills",
           "current_designation")


def default_resume() -> Path:
    """The newest resume file the builder produced, preferring PDF."""
    candidates = [p for ext in ("*.pdf", "*.docx") for p in RESUME_DIR.glob(ext)
                  if not p.name.endswith(".bak")]
    if not candidates:
        raise FileNotFoundError(
            f"No .pdf or .docx in {RESUME_DIR}. Run: python resume/build_resume.py")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def upload(path: Path | None = None, state_path: Path = DEFAULT_STATE,
           headless: bool = False) -> dict:
    """Attach `path` as the profile's resume. Returns a before/after report."""
    from playwright.sync_api import sync_playwright

    resume = Path(path) if path else default_resume()
    if not resume.exists():
        raise FileNotFoundError(resume)
    if resume.stat().st_size > 2 * 1024 * 1024:
        raise ValueError(
            f"{resume.name} is {resume.stat().st_size / 1e6:.1f} MB - Naukri's limit is 2 MB")

    before = extract_mod.load_saved() or {}

    with sync_playwright() as p:
        browser, _context, page = open_profile(p, state_path, headless=headless)
        try:
            shown_before = _attached_name(page)
            log.info("Currently attached: %s", shown_before)

            upload_input = page.locator(S.RESUME_UPLOAD[0]).first
            for selector in S.RESUME_UPLOAD:
                candidate = page.locator(selector).first
                if candidate.count():
                    upload_input = candidate
                    break
            if upload_input.count() == 0:
                raise RuntimeError(
                    f"No resume upload input found. Tried: {S.RESUME_UPLOAD}")

            upload_input.set_input_files(str(resume))
            log.info("Uploading %s (%.0f KB)", resume.name, resume.stat().st_size / 1024)

            # The card re-renders with the new filename once Naukri has taken it.
            for _ in range(30):
                page.wait_for_timeout(1000)
                now = _attached_name(page)
                if now and now != shown_before and resume.stem[:12] in now:
                    break
            page.wait_for_timeout(3000)
            shown_after = _attached_name(page)
        finally:
            browser.close()

    after = extract_mod.extract(state_path=state_path, headless=headless)

    changed = {}
    for field in AT_RISK:
        was, now = before.get(field), after.get(field)
        if not _same(was, now):
            changed[field] = {"before": was, "after": now}

    return {
        "file": str(resume),
        "attached_before": shown_before,
        "attached_after": shown_after,
        "clobbered": changed,
    }


def _same(was, now) -> bool:
    """Whether two snapshots of a field really differ.

    A long section is sometimes captured while still collapsed behind Naukri's
    "Read More", so one side is a truncated prefix ending in " ...". Comparing
    those raw reports the profile summary as rewritten on every upload, which
    buries a genuine parser overwrite in noise. One side being a prefix of the
    other is a scrape artefact, not a change.
    """
    if was == now:
        return True
    if isinstance(was, str) and isinstance(now, str):
        a = was.rstrip().removesuffix("...").rstrip()
        b = now.rstrip().removesuffix("...").rstrip()
        if a and b and (a.startswith(b) or b.startswith(a)):
            return True
    return False


def _attached_name(page) -> str:
    for selector in S.RESUME_ATTACHED:
        try:
            loc = page.locator(selector).first
            if loc.count():
                text = (loc.inner_text(timeout=3000) or "").strip()
                if text:
                    return " ".join(text.split())
        except Exception:
            continue
    return ""


def summarise(report: dict) -> str:
    lines = [
        "",
        "  Resume upload",
        "  " + "-" * 58,
        f"  File       {Path(report['file']).name}",
        f"  Was        {report['attached_before'] or '(unknown)'}",
        f"  Now        {report['attached_after'] or '(unknown)'}",
        "",
    ]
    if report["clobbered"]:
        lines.append("  NAUKRI'S PARSER CHANGED THESE FIELDS:")
        for field, diff in report["clobbered"].items():
            lines.append(f"    {field}")
            lines.append(f"      before: {str(diff['before'])[:110]}")
            lines.append(f"      after : {str(diff['after'])[:110]}")
        lines += [
            "",
            "  Re-apply the affected fields from changes.yaml if the parser has",
            "  undone an edit: uncomment them and run `main.py --apply --yes`.",
        ]
    else:
        lines.append("  No parser damage: every at-risk field is unchanged.")
    lines.append("")
    return "\n".join(lines)
