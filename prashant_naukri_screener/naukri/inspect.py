"""Dump a profile section's edit dialog so selectors can be written from fact.

Naukri reships this markup often, and a selector written from a guess fails at
the worst possible moment - halfway through an edit, with a dialog open on a
live profile. This opens a section's dialog, records every form control and
button inside it, screenshots it, and closes it again without typing anything.

    python main.py --inspect "IT skills"
    python main.py --inspect "IT skills,Certification,Employment"

Output lands in data/inspect/<slug>.json and <slug>.png. Nothing is saved to
the profile: the dialog is dismissed with Escape, never with its save button.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from . import selectors as S
from .session import DEFAULT_STATE, open_profile

log = logging.getLogger("naukri.inspect")

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "inspect"

# Everything inside the open dialog worth knowing about, collected in one pass
# in the page so a re-rendering dialog cannot change shape between queries.
_DUMP_JS = """
(rootSel) => {
  const root = document.querySelector(rootSel) || document.body;
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const describe = (el) => ({
    tag: el.tagName.toLowerCase(),
    type: el.getAttribute('type') || null,
    id: el.id || null,
    name: el.getAttribute('name') || null,
    cls: el.getAttribute('class') || null,
    placeholder: el.getAttribute('placeholder') || null,
    label: (el.getAttribute('aria-label') || '').trim() || null,
    text: (el.textContent || '').trim().slice(0, 60) || null,
    value: ('value' in el ? String(el.value || '') : '').slice(0, 80),
    visible: vis(el),
    options: el.tagName.toLowerCase() === 'select'
      ? Array.from(el.options).slice(0, 12).map(o => o.textContent.trim())
      : undefined,
  });
  const pick = (sel) => Array.from(root.querySelectorAll(sel)).filter(vis).map(describe);
  return {
    rootSelector: rootSel,
    rootClass: root.getAttribute('class') || null,
    rootId: root.id || null,
    inputs: pick('input, textarea, select'),
    buttons: pick("button, a[role='button'], .btn, [class*='btn']"),
    chips: Array.from(root.querySelectorAll("[class*='chip'], [class*='tag']"))
             .filter(vis).map(e => (e.textContent || '').trim()).filter(Boolean).slice(0, 40),
    headings: Array.from(root.querySelectorAll('h1,h2,h3,h4,label,legend'))
             .filter(vis).map(e => (e.textContent || '').trim()).filter(Boolean).slice(0, 40),
  };
}
"""

# Candidate roots for "the dialog that just opened", most specific first.
DIALOG_ROOTS = [
    ".Drawer",
    "[class*='Drawer']",
    "[class*='drawer']",
    "[role='dialog']",
    ".modal",
    "[class*='modal']",
    "body",
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _triggers(heading: str) -> list[str]:
    """Both ways into a section: its edit pencil, and its Add affordance.

    A section the profile has never filled in has no edit icon at all - only
    an "Add" link - which is exactly the case for the sections this tool
    exists to discover.
    """
    h = heading
    return [
        S._edit_trigger(h),
        f"xpath=//*[normalize-space(text())='{h}']/following-sibling::span[contains(@class,'add')][1]",
        f"xpath=//*[normalize-space(text())='{h}']/following-sibling::a[contains(@class,'add')][1]",
        # Scoped to the heading's own parent. Accomplishment sub-blocks
        # ("Certification", "Patent") are a label div plus an `a.add` inside one
        # unclassed container, so the parent is the only thing that bounds them.
        f"xpath=//*[normalize-space(text())='{h}']/parent::*//a[contains(@class,'add')]",
        f"xpath=//*[normalize-space(text())='{h}']/following-sibling::*[self::a or self::span][1]",
        f"xpath=//*[normalize-space(text())='{h}']/ancestor::*[contains(@class,'widgetHead')][1]"
        f"//*[contains(@class,'edit') or contains(@class,'add')]",
        # Last resort, and the reason it is last: `following::` walks document
        # order out of the section entirely. Asking for "Certification" this way
        # opened the Career-profile dialog, because the next "Add" link after the
        # last accomplishment block belongs to the next card down the page.
        f"xpath=//*[contains(normalize-space(text()),'{h}')]/following::a[contains(.,'Add')][1]",
    ]


def _open(page, heading: str) -> str:
    """Click something that opens `heading`'s dialog. Returns what worked."""
    for selector in _triggers(heading):
        try:
            loc = page.locator(selector).first
            if loc.count() == 0:
                continue
            loc.scroll_into_view_if_needed(timeout=3000)
            loc.click(timeout=5000)
            page.wait_for_timeout(1800)
            return selector
        except Exception as exc:
            log.debug("trigger %s failed: %s", selector, exc)
    raise RuntimeError(f"No trigger opened the {heading!r} dialog")


def _dialog_root(page) -> str:
    """The narrowest container that actually holds a text input right now."""
    for root in DIALOG_ROOTS:
        try:
            loc = page.locator(root).first
            if loc.count() == 0:
                continue
            if loc.locator("input, textarea, select").count() > 0:
                return root
        except Exception:
            continue
    return "body"


def inspect(headings: list[str], state_path: Path = DEFAULT_STATE,
            headless: bool = False) -> dict:
    """Dump each heading's dialog. Returns {heading: dump-or-error}."""
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}

    with sync_playwright() as p:
        browser, _context, page = open_profile(p, state_path, headless=headless)
        try:
            # Sections below the fold do not exist until they have been scrolled
            # past, so their triggers cannot be found without this pass.
            for _ in range(10):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(350)
            page.mouse.wheel(0, -40000)
            page.wait_for_timeout(1200)

            for heading in headings:
                slug = _slug(heading)
                try:
                    trigger = _open(page, heading)
                    root = _dialog_root(page)
                    dump = page.evaluate(_DUMP_JS, root)
                    dump["heading"] = heading
                    dump["trigger"] = trigger
                    page.screenshot(path=str(OUT_DIR / f"{slug}.png"), full_page=False)
                    (OUT_DIR / f"{slug}.json").write_text(
                        json.dumps(dump, indent=2), encoding="utf-8")
                    out[heading] = dump
                    log.info("%s: %d input(s), %d button(s) via %s",
                             heading, len(dump["inputs"]), len(dump["buttons"]), root)
                except Exception as exc:
                    out[heading] = {"error": str(exc)}
                    log.warning("%s: %s", heading, exc)
                finally:
                    # Escape, never Save. Nothing this tool does is a write.
                    for _ in range(3):
                        try:
                            page.keyboard.press("Escape")
                            page.wait_for_timeout(600)
                        except Exception:
                            break
                    page.wait_for_timeout(600)
        finally:
            browser.close()
    return out


def summarise(dumps: dict) -> str:
    lines = ["", "  Dialog inspection", "  " + "-" * 60]
    for heading, d in dumps.items():
        if "error" in d:
            lines.append(f"  {heading}: FAILED - {d['error']}")
            continue
        lines.append(f"  {heading}   (root {d['rootSelector']}, via {d['trigger'][:50]}...)")
        for i in d["inputs"]:
            ident = i["id"] or i["name"] or i["cls"] or "?"
            extra = f" placeholder={i['placeholder']!r}" if i["placeholder"] else ""
            opts = f" options={i['options'][:6]}" if i.get("options") else ""
            lines.append(f"      {i['tag']}[{i['type'] or '-'}]  {ident}{extra}{opts}")
        for b in d["buttons"]:
            if not b["text"]:
                continue
            ident = b["id"] or b["cls"] or "?"
            lines.append(f"      BUTTON {b['text']!r}  id/cls={ident}")
        if d["chips"]:
            lines.append(f"      chips: {d['chips'][:12]}")
        lines.append("")
    lines.append(f"  Full dumps in {OUT_DIR}")
    return "\n".join(lines) + "\n"
