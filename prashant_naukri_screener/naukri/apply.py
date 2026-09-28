"""Push approved rewrites back into Naukri's edit dialogs.

Reads changes.yaml, opens each field's edit dialog, replaces the text and
saves. Runs headed by default so you can watch it and take over if Naukri
throws something unexpected mid-edit.

Nothing is written without either --dry-run being off or an explicit --yes,
because these edits land on a live profile that recruiters are reading.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from . import selectors as S
from .session import DEFAULT_STATE, open_profile

log = logging.getLogger("naukri.apply")

ROOT = Path(__file__).resolve().parent.parent
CHANGES_FILE = ROOT / "changes.yaml"


def load_changes(path: Path = CHANGES_FILE) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"No {path.name} found. Copy changes.example.yaml to changes.yaml and edit it."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    unknown = set(data) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(
            f"changes.yaml has fields with no editor defined: {sorted(unknown)}. "
            f"Editable fields: {sorted(EDITABLE_FIELDS)}"
        )
    _validate(data)
    return data


# Plain-text fields go through S.EDITORS; the rest have their own handler and
# their own dialog shape.
STRUCTURED_FIELDS = ("it_skills", "certifications", "designation")
EDITABLE_FIELDS = set(S.EDITORS) | set(STRUCTURED_FIELDS)


def _validate(data: dict) -> None:
    """Reject a malformed changes.yaml before a browser is ever opened.

    Every one of these would otherwise surface as a selector timeout halfway
    through editing a live profile, which is the worst place to discover a typo.
    """
    for row in data.get("it_skills") or []:
        if not isinstance(row, dict) or not row.get("skill"):
            raise ValueError(f"it_skills entries need a 'skill': {row!r}")
        if row.get("last_used") in (None, ""):
            raise ValueError(f"it_skills[{row.get('skill')!r}] needs 'last_used' (a year)")
        for key in ("years", "months"):
            if key in row and not isinstance(row[key], int):
                raise ValueError(
                    f"it_skills[{row.get('skill')!r}].{key} must be a whole number"
                )

    certs = data.get("certifications")
    if certs is not None:
        if not isinstance(certs, list) or not certs:
            raise ValueError("certifications must be a non-empty list")
        for cert in certs:
            if not isinstance(cert, dict) or not cert.get("name"):
                raise ValueError(f"certifications entries need a 'name': {cert!r}")

    desig = data.get("designation")
    if desig is not None:
        if not isinstance(desig, dict) or not desig.get("expect") or not desig.get("value"):
            raise ValueError(
                "designation needs both 'expect' (the title currently on the "
                "profile, as a safety check) and 'value' (the new title)"
            )


def _editor_for(field: str, value) -> dict:
    """The trigger/input/save triple for a field, whatever its dialog shape.

    `input[0]` doubles as the proof that the intended dialog opened and, after
    saving, the proof that it closed - so it must be an element unique to this
    field's dialog.
    """
    if field in S.EDITORS:
        return S.EDITORS[field]
    if field == "it_skills":
        return {"trigger": S.IT_SKILLS["trigger"],
                "input": S.IT_SKILLS["name"],
                "save": S.IT_SKILLS["save"]}
    if field == "certifications":
        return {"trigger": S.CERTIFICATIONS["trigger"],
                "input": S.CERTIFICATIONS["name"],
                "save": S.CERTIFICATIONS["save"]}
    if field == "designation":
        return {"trigger": S.designation_trigger(str(value["expect"]).strip()),
                "input": S.DESIGNATION["input"],
                "save": S.DESIGNATION["save"]}
    raise KeyError(field)


def _click_first(page, candidates: list[str], what: str) -> None:
    """Click the first candidate selector that is actually clickable.

    Each candidate gets three escalating attempts before the next is tried: a
    normal click, then a forced one, then a dispatched DOM event. The ordinary
    click is the only one that respects overlays and disabled states, so it has
    to come first - but a Save button sitting under Naukri's sticky footer is
    genuinely unclickable while still being the right element, and failing the
    whole edit over that leaves a dirty dialog open on a live profile.
    """
    for selector in candidates:
        try:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            locator.scroll_into_view_if_needed(timeout=3000)
        except Exception as exc:
            log.debug("locate %s failed: %s", selector, exc)
            continue

        for attempt, how in enumerate(("click", "force", "dispatch")):
            try:
                if how == "click":
                    locator.click(timeout=5000)
                elif how == "force":
                    locator.click(timeout=4000, force=True)
                else:
                    locator.dispatch_event("click")
                if attempt:
                    log.info("%s needed a %s click (%s)", what, how, selector)
                return
            except Exception as exc:
                log.debug("%s click %s failed: %s", how, selector, exc)

    raise RuntimeError(f"Could not find {what}. Selectors tried: {candidates}")


def _save_and_confirm(page, editor: dict, field: str) -> None:
    """Click Save, then prove the dialog actually closed.

    Waiting a fixed 2.5s and declaring success is how a rejected save - over a
    character limit, a required field left blank - gets logged as "ok" and the
    old text stays live for another week. The dialog's own input disappearing is
    the cheapest available proof that Naukri accepted the edit.
    """
    _click_first(page, editor["save"], f"{field} save button")

    probe = editor["input"][0]
    try:
        page.wait_for_selector(probe, state="hidden", timeout=12000)
    except Exception:
        still_open = False
        try:
            still_open = page.locator(probe).first.is_visible(timeout=2000)
        except Exception:
            pass
        if still_open:
            raise RuntimeError(
                f"{field}: Save was clicked but the dialog is still open - "
                f"Naukri rejected the edit (check length limits and required fields)"
            )
    page.wait_for_timeout(1200)


def _fill_first(page, candidates: list[str], value: str, what: str) -> None:
    """Set a field's value and read it back to confirm it landed.

    Uses fill() rather than type(). type() streams keystrokes, and a stream
    still flushing when the next field starts typing interleaves the two
    character by character - which is exactly how a profile summary once ended
    up shredded across the key-skill chips. fill() sets value in one shot.
    """
    for selector in candidates:
        try:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            locator.click(timeout=5000)
            locator.fill("", timeout=5000)
            page.wait_for_timeout(200)
            locator.fill(value, timeout=5000)
            page.wait_for_timeout(300)

            wrote = (locator.input_value(timeout=3000) or "").strip()
            if wrote != value.strip():
                raise RuntimeError(
                    f"{what} readback mismatch - wrote {len(value)} chars, "
                    f"field holds {len(wrote)}"
                )
            return
        except Exception as exc:
            log.debug("fill %s failed: %s", selector, exc)
    raise RuntimeError(f"Could not find {what}. Selectors tried: {candidates}")


def _open_editor(page, editor: dict, field: str) -> None:
    """Open a field's dialog and confirm the right one opened.

    Clicking a trigger is not proof the intended dialog appeared - a mis-matched
    selector opens someone else's dialog just as happily. Waiting for this
    field's own input means a wrong dialog raises before any key is pressed,
    rather than after the text has been typed into the wrong box.
    """
    _click_first(page, editor["trigger"], f"{field} edit button")
    page.wait_for_timeout(1200)

    expected = editor["input"][0]
    try:
        page.wait_for_selector(expected, state="visible", timeout=12000)
    except Exception:
        raise RuntimeError(f"{field} dialog did not open (no {expected})")


def _close_editor(page) -> None:
    """Dismiss any open dialog so the next field starts from a clean page."""
    for _ in range(3):
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(700)
        except Exception:
            break


CHIP = ".chipsContainer .chip"


def _current_chips(page) -> list[str]:
    """Skill names currently on the chip list, in display order."""
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('.chipsContainer .chip'))
             .map(c => (c.querySelector('.tagTxt')?.textContent || '').trim())
             .filter(Boolean)"""
    )


def _remove_key_skills(page, unwanted: list[str]) -> list[str]:
    """Click the close icon on each unwanted chip. Returns what was removed."""
    removed = []
    for name in unwanted:
        # Re-query each time - removing a chip reindexes the list.
        chips = page.locator(CHIP)
        for i in range(chips.count()):
            chip = chips.nth(i)
            try:
                label = (chip.locator(".tagTxt").inner_text(timeout=1500) or "").strip()
            except Exception:
                continue
            if label.lower() != name.lower():
                continue
            try:
                chip.locator(".material-icons.close").click(timeout=3000)
                page.wait_for_timeout(500)
                removed.append(label)
            except Exception as exc:
                log.warning("Could not remove chip %s: %s", label, exc)
            break
    return removed


def _apply_key_skills(page, editor: dict, spec) -> list[str]:
    """Sync the key-skill chips. Returns the skills Naukri would not accept.

    `spec` is either a plain list (skills to add) or a mapping with `remove`
    and `add` keys. Removal runs first so freed slots are available to the
    additions - Naukri caps how many skills a profile may carry.
    """
    if isinstance(spec, dict):
        to_remove = spec.get("remove") or []
        to_add = spec.get("add") or []
    else:
        to_remove, to_add = [], list(spec)

    if to_remove:
        removed = _remove_key_skills(page, to_remove)
        print(f"    removed: {', '.join(removed) if removed else 'none'}")

    existing = {s.lower() for s in _current_chips(page)}

    for selector in editor["input"]:
        box = page.locator(selector).first
        if box.count() == 0:
            continue

        skipped = []
        for skill in to_add:
            if skill.lower() in existing:
                continue
            if not _add_one_skill(page, box, skill):
                skipped.append(skill)
                continue

            # Clicking the right suggestion is not proof a chip appeared. Naukri
            # caps how many key skills a profile may carry and, at the cap, it
            # accepts the click and silently adds nothing - which is how
            # "Regression Testing" and "Functional Testing" were reported as
            # added on 2026-09-12 while never reaching the profile. Confirm
            # against the live chip list instead of trusting the click.
            chips = {c.lower() for c in _current_chips(page)}
            if skill.lower() in chips:
                existing = chips
            else:
                log.warning("%r was accepted but no chip appeared - most likely "
                            "Naukri's key-skill cap (%d chips) is reached",
                            skill, len(chips))
                skipped.append(f"{skill} (cap reached at {len(chips)} skills)")

        # Anything still in the box would be committed as a junk chip on save.
        box.fill("")
        page.wait_for_timeout(300)

        final = _current_chips(page)
        print(f"    final {len(final)} skills: {', '.join(final)}")

        if skipped:
            # This used to print and do nothing else, which is how two of the
            # highest-value keywords on this profile - SDET and REST API - were
            # dropped by Naukri's suggester and stayed missing for weeks: the
            # only record was one console line inside a scheduled run's output.
            # A dropped keyword is a silent, permanent loss of search
            # visibility, so it goes to the log file and is handed back to the
            # caller. It is deliberately NOT raised: the chips that did land are
            # still unsaved at this point, and throwing here would discard them
            # along with the bad news.
            log.warning("%d key skill(s) had no exact suggestion and were NOT added: %s",
                        len(skipped), ", ".join(skipped))
            print(f"    [WARN] no exact Naukri suggestion, NOT added: {', '.join(skipped)}")
        return skipped

    raise RuntimeError("Could not find the key-skills input.")


def _add_one_skill(page, box, skill: str) -> bool:
    """Type a skill and click its suggestion. True if a chip was created.

    Never raises: one unavailable keyword must not abandon the rest of the list,
    or the chips already added go unsaved along with it.
    """
    try:
        _pick_suggestion(page, box, skill, S.SKILL_SUGGESTIONS)
        return True
    except NoExactSuggestion as exc:
        # Record what Naukri actually offered. "SDET" was rejected for weeks with
        # no clue why; the nearest accepted spelling is usually sitting in this
        # list, so logging it turns a dead end into a one-line config fix.
        log.warning("%s", exc)
        return False
    except Exception as exc:
        log.warning("key skill %r failed: %s", skill, exc)
        return False


def _pick_suggestion(page, box, wanted: str, suggestions: str) -> list[str]:
    """Type `wanted` into a suggester and click its exact suggestion.

    Returns the labels Naukri offered; an empty return means no dropdown ever
    appeared. Raises if none of them matched exactly.

    Only an exact (case-insensitive) match is accepted. Taking the first
    suggestion instead would quietly claim a skill that was never asked for -
    typing "Git" surfaces "Github" at the top.

    The click targets the suggestion by its text, not by index. Reading every
    label and then clicking `nth(i)` is what made the key-skills run fail on
    2026-09-12: the list re-rendered between the read and the click, so the
    index pointed at a row that no longer existed.
    """
    box.click(timeout=5000)
    box.fill("")
    box.type(wanted, delay=40)

    try:
        page.wait_for_selector(suggestions, timeout=6000)
    except Exception:
        box.fill("")
        return []

    page.wait_for_timeout(400)
    options = page.locator(suggestions)
    offered: list[str] = []
    for i in range(min(options.count(), 12)):
        try:
            offered.append((options.nth(i).inner_text(timeout=1500) or "").strip())
        except Exception:
            continue

    pattern = re.compile(rf"^\s*{re.escape(wanted)}\s*$", re.I)
    for attempt in range(2):
        try:
            target = page.locator(suggestions).filter(has_text=pattern).first
            if target.count() == 0:
                break
            target.click(timeout=5000)
            page.wait_for_timeout(700)
            return offered
        except Exception as exc:
            log.debug("suggestion click for %r attempt %d failed: %s", wanted, attempt, exc)
            page.wait_for_timeout(600)

    box.fill("")
    raise NoExactSuggestion(wanted, offered)


class NoExactSuggestion(RuntimeError):
    """Naukri's suggester offered nothing matching the requested wording."""

    def __init__(self, wanted: str, offered: list[str]):
        self.wanted = wanted
        self.offered = offered
        detail = f"; Naukri offered: {', '.join(offered[:6])}" if offered else \
                 "; no suggestion dropdown appeared"
        super().__init__(f"no exact suggestion for {wanted!r}{detail}")


def _pick_droope(page, base: str, value, label: str | None = None) -> None:
    """Choose a value in one of Naukri's droope dropdowns.

    Opens the control, then clicks the option by its stable `data-id`. Falls
    back to the visible label only if that misses, because the year droopes list
    every year back to 1940 and a loose text match lands in the wrong decade.
    """
    box = page.locator(S.droope_input(base)).first
    if box.count() == 0:
        raise RuntimeError(f"droope {base} not present in this dialog")
    box.scroll_into_view_if_needed(timeout=3000)
    box.click(timeout=5000)
    page.wait_for_timeout(900)

    for selector in (S.droope_option(base, value),
                     S.droope_option_by_text(base, label) if label else None):
        if not selector:
            continue
        try:
            option = page.locator(selector).first
            if option.count() == 0:
                continue
            option.click(timeout=5000)
            page.wait_for_timeout(700)
            wrote = (box.input_value(timeout=3000) or "").strip()
            if not wrote:
                raise RuntimeError("option clicked but the control is still empty")
            return
        except Exception as exc:
            log.debug("droope %s via %s failed: %s", base, selector, exc)

    raise RuntimeError(f"Could not set droope {base} to {value!r}")


def _existing_it_skills(page) -> dict[str, str]:
    """Skill name -> the experience text currently shown, for rows on the page."""
    return page.evaluate(
        """() => {
             const out = {};
             document.querySelectorAll('#lazyITSkills li.collection').forEach(li => {
               const cols = li.querySelectorAll('span.col');
               if (cols.length < 4) return;
               const name = (cols[0].textContent || '').trim();
               if (!name || name === 'Skills') return;
               out[name] = (cols[3].textContent || '').trim();
             });
             return out;
           }"""
    )


def _fill_it_skill_row(page, row: dict, name_is_prefilled: bool) -> None:
    """Fill the open IT-skills dialog for one skill."""
    if not name_is_prefilled:
        box = page.locator(S.IT_SKILLS["name"][0]).first
        # Must be the IT-skills dropdown, not the key-skills one.
        _pick_suggestion(page, box, str(row["skill"]).strip(), S.IT_SKILLS["suggestions"])

    if row.get("version"):
        ver = page.locator(S.IT_SKILLS["version"][0]).first
        if ver.count():
            ver.fill(str(row["version"]))
            page.wait_for_timeout(300)

    _pick_droope(page, S.IT_SKILLS["last_used"], row["last_used"], str(row["last_used"]))
    years = int(row.get("years") or 0)
    months = int(row.get("months") or 0)
    _pick_droope(page, S.IT_SKILLS["years"], years, S.DROOPE_YEAR_LABEL(years))
    _pick_droope(page, S.IT_SKILLS["months"], months, S.DROOPE_MONTH_LABEL(months))


def _apply_it_skills(page, spec: list[dict]) -> list[str]:
    """Add or update IT-skill rows, one dialog cycle per skill.

    This field owns its own dialog lifecycle rather than using the shared
    open/fill/save path, because Naukri's IT-skills dialog holds exactly one
    skill: six skills means six open-fill-save rounds, and a skill already on
    the profile has to be opened through its own row pencil or it gets added a
    second time instead of updated.

    Returns a list of human-readable failures; rows that succeeded stay saved.
    """
    failed: list[str] = []
    existing = _existing_it_skills(page)
    log.info("IT skills already on the profile: %s", existing or "none")

    for row in spec:
        name = str(row["skill"]).strip()
        update = name in existing
        mode = "update" if update else "add"
        try:
            trigger = ([S.it_skill_row_edit(name)] if update
                       else list(S.IT_SKILLS["trigger"]))
            _click_first(page, trigger, f"IT skills {mode} trigger for {name}")
            page.wait_for_selector(S.IT_SKILLS["name"][0], state="visible", timeout=12000)
            page.wait_for_timeout(1000)

            _fill_it_skill_row(page, row, name_is_prefilled=update)

            years = int(row.get("years") or 0)
            months = int(row.get("months") or 0)
            _save_and_confirm(page, {"input": S.IT_SKILLS["name"],
                                     "save": S.IT_SKILLS["save"]}, f"it_skills[{name}]")
            was = f" (was {existing[name]})" if update else ""
            print(f"    [{mode}] {name:<22} {years}y {months}m, last used {row['last_used']}{was}")
            log.info("IT skill %s %sd: %dy %dm", name, mode, years, months)
        except Exception as exc:
            failed.append(f"{name} ({exc})")
            log.warning("IT skill %s (%s) failed: %s", name, mode, exc)
            print(f"    [WARN] {name}: {exc}")
            _close_editor(page)

        # The section re-renders after each save, so the next row's pencil only
        # exists once the new markup has settled.
        page.wait_for_timeout(1200)

    return failed


def _apply_certifications(page, spec: list[dict]) -> list[str]:
    """Add certification rows. Returns the ones that could not be filled.

    Naukri's dialog exposes one row (index 0) at a time, so this fills the first
    entry and reports any others as needing another pass - better than silently
    writing one of three certifications and reporting success.
    """
    failed: list[str] = []
    if len(spec) > 1:
        extra = ", ".join(str(c.get("name")) for c in spec[1:])
        failed.append(f"only the first row is supported per run; not added: {extra}")

    cert = spec[0]
    name = str(cert["name"]).strip()
    try:
        _fill_first(page, S.CERTIFICATIONS["name"], name, "certification name")

        for key, field in (("cert_id", "cert_id"), ("url", "url")):
            if cert.get(key):
                box = page.locator(S.CERTIFICATIONS[field][0]).first
                if box.count():
                    box.fill(str(cert[key]))
                    page.wait_for_timeout(300)

        if cert.get("never_expires"):
            cb = page.locator(S.CERTIFICATIONS["never_expires"][0]).first
            if cb.count() and not cb.is_checked():
                cb.click(timeout=4000)
                page.wait_for_timeout(500)

        if cert.get("from_month") and cert.get("from_year"):
            _pick_droope(page, S.CERTIFICATIONS["from_month"], cert["from_month"],
                         str(cert["from_month"]))
            _pick_droope(page, S.CERTIFICATIONS["from_year"], cert["from_year"],
                         str(cert["from_year"]))
        print(f"    certification: {name}")
    except Exception as exc:
        failed.append(f"{name} ({exc})")
        log.warning("certification %s failed: %s", name, exc)

    return failed


def _apply_designation(page, spec: dict) -> list[str]:
    """Rewrite the current job title, guarded against editing the wrong card.

    `expect` must match what the dialog already holds. Without that check a
    drifted selector silently rewrites a previous employer's designation, or
    fills the blank "Add employment" form and creates a duplicate job entry -
    both of which are far worse than the edit simply refusing to run.
    """
    expect = str(spec["expect"]).strip()
    value = str(spec["value"]).strip()

    box = page.locator(S.DESIGNATION["input"][0]).first
    if box.count() == 0:
        raise RuntimeError("employment dialog has no #designationSugg")

    current = (box.input_value(timeout=5000) or "").strip()
    if current != expect:
        raise RuntimeError(
            f"dialog holds designation {current!r} but changes.yaml expects "
            f"{expect!r} - refusing to edit, this may be the wrong employment "
            f"card or a blank Add form"
        )

    box.click(timeout=5000)
    box.fill("")
    page.wait_for_timeout(300)
    box.fill(value)
    page.wait_for_timeout(600)

    wrote = (box.input_value(timeout=3000) or "").strip()
    if wrote != value:
        raise RuntimeError(f"designation readback mismatch: field holds {wrote!r}")
    print(f"    designation: {current!r} -> {value!r}")
    return []


def _preview(field: str, value) -> list[str]:
    """Render one pending change for the dry run.

    The dry run is the only review step before an edit lands on a live profile,
    so a structured field has to read as what it will actually write - a bare
    str(dict) is not something anyone can check a claimed year count against.
    """
    if field == "it_skills":
        return [f"{r['skill']:<22} {int(r.get('years') or 0)}y {int(r.get('months') or 0)}m"
                f"   last used {r['last_used']}"
                + (f"   v{r['version']}" if r.get("version") else "")
                for r in value]
    if field == "certifications":
        return [f"{c['name']}"
                + (f"   {c.get('from_month')}/{c.get('from_year')}"
                   if c.get("from_year") else "")
                + ("   (does not expire)" if c.get("never_expires") else "")
                for c in value]
    if field == "designation":
        return [f"{value['expect']!r}  ->  {value['value']!r}"]
    if field == "key_skills" and isinstance(value, dict):
        lines = []
        if value.get("remove"):
            lines.append(f"remove: {', '.join(value['remove'])}")
        if value.get("add"):
            lines.append(f"add:    {', '.join(value['add'])}")
        return lines
    if isinstance(value, list):
        return [", ".join(str(v) for v in value)]

    text = str(value).strip()
    limit = S.MAX_LENGTHS.get(field)
    head = [f"({len(text)} chars" + (f" of {limit} allowed)" if limit else ")")]
    # Naukri truncates the summary behind a "Read More" at ~285 characters, and
    # that prefix is the whole of what a recruiter sees in a search result. Show
    # where the cut falls so a rewrite can be judged on the visible part.
    if field == "profile_summary" and len(text) > 285:
        head.append(f"VISIBLE: {text[:285]}")
        head.append(f"hidden : {text[285:]}")
    else:
        head.append(text)
    return head


def apply(
    changes: dict,
    state_path: Path = DEFAULT_STATE,
    headless: bool = False,
    dry_run: bool = True,
) -> dict:
    """Apply each field in `changes`. Returns {field: 'ok' | error message}."""
    from playwright.sync_api import sync_playwright

    if dry_run:
        print("\n  DRY RUN - nothing will be saved.\n")
        for field, value in changes.items():
            print(f"  {field}:")
            for line in _preview(field, value):
                print(f"    {line}")
            print()
        return {field: "dry-run" for field in changes}

    results: dict[str, str] = {}
    with sync_playwright() as p:
        browser, _context, page = open_profile(p, state_path, headless=headless)
        try:
            # Sections below the fold are lazy-rendered. Without this pass their
            # edit buttons genuinely do not exist yet and every trigger lookup
            # for a lower section fails.
            for _ in range(8):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(400)
            page.mouse.wheel(0, -30000)
            page.wait_for_timeout(1200)

            for field, value in changes.items():
                # it_skills drives its own open/save cycle per row - see
                # _apply_it_skills - so it bypasses the single-dialog path.
                if field == "it_skills":
                    try:
                        skipped = _apply_it_skills(page, value) or []
                        if skipped:
                            results[field] = "partial: " + "; ".join(skipped)
                            print(f"  [PARTIAL] {field} - {len(skipped)} row(s) failed")
                        else:
                            results[field] = "ok"
                            print(f"  [ok] {field}")
                    except Exception as exc:
                        results[field] = str(exc)
                        log.warning("Failed to update %s: %s", field, exc)
                        print(f"  [FAILED] {field}: {exc}")
                        _close_editor(page)
                    continue

                editor = _editor_for(field, value)
                try:
                    _open_editor(page, editor, field)

                    skipped: list[str] = []
                    if field == "key_skills":
                        skipped = _apply_key_skills(page, editor, value) or []
                    elif field == "certifications":
                        skipped = _apply_certifications(page, value) or []
                    elif field == "designation":
                        skipped = _apply_designation(page, value) or []
                    else:
                        limit = S.MAX_LENGTHS.get(field)
                        text = str(value).strip()
                        if limit and len(text) > limit:
                            raise ValueError(
                                f"{field} is {len(text)} chars, over Naukri's {limit} limit"
                            )
                        _fill_first(page, editor["input"], text, f"{field} input")

                    page.wait_for_timeout(500)
                    _save_and_confirm(page, editor, field)

                    # Saved, but not wholly as asked - the caller needs to see
                    # the difference so a half-applied change is not read as a
                    # clean one.
                    if skipped:
                        results[field] = "partial: Naukri rejected " + ", ".join(skipped)
                        log.warning("Updated %s, but %d skill(s) rejected: %s",
                                    field, len(skipped), ", ".join(skipped))
                        print(f"  [PARTIAL] {field} - rejected: {', '.join(skipped)}")
                    else:
                        results[field] = "ok"
                        log.info("Updated %s", field)
                        print(f"  [ok] {field}")
                except Exception as exc:
                    results[field] = str(exc)
                    log.warning("Failed to update %s: %s", field, exc)
                    print(f"  [FAILED] {field}: {exc}")
                finally:
                    # Always, not just on failure: a dialog left open is what
                    # lets one field's text bleed into the next field's input.
                    _close_editor(page)
        finally:
            browser.close()

    return results
