"""Tests for the parts of the apply path that need no browser.

The value here is catching a bad changes.yaml before a run opens a dialog on a
live profile - by the time a selector times out, the edit is half typed.
"""
from __future__ import annotations

import pytest

from naukri import apply as apply_mod
from naukri import selectors as S
from naukri.resume_file import _same


# ----------------------------------------------------------- changes.yaml
@pytest.mark.parametrize("data, fragment", [
    ({"it_skills": [{"version": "3"}]}, "need a 'skill'"),
    ({"it_skills": [{"skill": "Python"}]}, "last_used"),
    ({"it_skills": [{"skill": "Python", "last_used": 2026, "years": "four"}]}, "whole number"),
    ({"it_skills": [{"skill": "Python", "last_used": 2026, "months": 1.5}]}, "whole number"),
    ({"certifications": []}, "non-empty list"),
    ({"certifications": [{"from_year": 2023}]}, "need a 'name'"),
    ({"designation": {"value": "X"}}, "expect"),
    ({"designation": {"expect": "X"}}, "value"),
])
def test_validate_rejects_bad_config(data, fragment):
    with pytest.raises(ValueError) as err:
        apply_mod._validate(data)
    assert fragment in str(err.value)


def test_validate_accepts_a_complete_config():
    apply_mod._validate({
        "it_skills": [{"skill": "Python", "version": "3.12",
                       "last_used": 2026, "years": 4, "months": 0}],
        "certifications": [{"name": "ISTQB Foundation Level", "never_expires": True}],
        "designation": {"expect": "Software Test Engineer",
                        "value": "Software Test Engineer (SDET)"},
    })


def test_editable_fields_covers_every_handler():
    assert apply_mod.EDITABLE_FIELDS >= set(S.EDITORS)
    for field in apply_mod.STRUCTURED_FIELDS:
        assert field in apply_mod.EDITABLE_FIELDS


@pytest.mark.parametrize("field, value", [
    ("resume_headline", "x"),
    ("profile_summary", "y"),
    ("key_skills", {"add": ["SDET"]}),
    ("it_skills", [{"skill": "Python", "last_used": 2026}]),
    ("certifications", [{"name": "ISTQB"}]),
    ("designation", {"expect": "A", "value": "B"}),
])
def test_every_editable_field_resolves_to_an_editor(field, value):
    editor = apply_mod._editor_for(field, value)
    assert editor["trigger"] and editor["input"] and editor["save"]


def test_designation_trigger_is_anchored_to_the_current_title():
    """It must never resolve to "Add employment", which creates a duplicate job."""
    editor = apply_mod._editor_for("designation", {"expect": "Software Test Engineer",
                                                  "value": "X"})
    assert all("Software Test Engineer" in t for t in editor["trigger"])
    assert not any("add" in t.lower() for t in editor["trigger"])


# ----------------------------------------------------------- dry-run preview
def test_preview_shows_the_summary_truncation_point():
    text = "A" * 400
    lines = apply_mod._preview("profile_summary", text)
    assert any("VISIBLE" in ln for ln in lines)
    assert any("hidden" in ln for ln in lines)
    visible = next(ln for ln in lines if ln.startswith("VISIBLE"))
    assert len(visible.replace("VISIBLE: ", "")) == 285


def test_preview_renders_structured_fields_without_crashing():
    # str(dict) here is what made the old preview useless for checking a claim.
    assert apply_mod._preview(
        "it_skills", [{"skill": "Python", "last_used": 2026, "years": 4, "months": 0}]
    ) == ["Python                 4y 0m   last used 2026"]
    assert apply_mod._preview(
        "designation", {"expect": "A", "value": "B"}) == ["'A'  ->  'B'"]
    assert apply_mod._preview("key_skills", {"remove": ["Grafana"], "add": ["SDET"]}) == [
        "remove: Grafana", "add:    SDET"]


# ----------------------------------------------------------------- selectors
def test_droope_option_targets_the_stable_data_id():
    """Year lists run back to 1940, so a text match can hit the wrong decade."""
    assert S.droope_option("expYearDroope", 4) == \
        "#ul_expYearDroope a[data-id='expYearDroope_4']"
    assert S.droope_input("expYearDroope") == "#expYearDroopeFor"


@pytest.mark.parametrize("n, expected", [(1, "1 Year"), (0, "0 Years"), (4, "4 Years")])
def test_droope_year_labels_match_naukris_singular_plural(n, expected):
    assert S.DROOPE_YEAR_LABEL(n) == expected


def test_suggestions_are_scoped_to_their_own_input():
    """Reusing the key-skills dropdown id is what broke every IT-skill add."""
    assert S.suggestions_for("itSkillSugg") == "#sugDrp_itSkillSugg li.sugTouple"
    assert S.IT_SKILLS["suggestions"] != S.SKILL_SUGGESTIONS


def test_every_editor_carries_the_generic_save_fallbacks():
    for field, editor in S.EDITORS.items():
        assert set(S.GENERIC_SAVE) <= set(editor["save"]), field
    for spec in (S.IT_SKILLS, S.CERTIFICATIONS, S.DESIGNATION):
        assert set(S.GENERIC_SAVE) <= set(spec["save"])


def test_it_skill_row_edit_is_scoped_to_the_it_skills_widget():
    sel = S.it_skill_row_edit("Python")
    assert "lazyITSkills" in sel and "Python" in sel


# --------------------------------------------------- resume upload diffing
@pytest.mark.parametrize("was, now, same", [
    ("abc def ...", "abc def ghi", True),      # collapsed "Read More" snapshot
    ("Senior SDET and QA ...", "Senior SDET and QA automation", True),
    ("abc", "abc", True),
    (None, None, True),
    (["a", "b"], ["a", "b"], True),
    ("totally different", "something else", False),
    (["a"], ["b"], False),
])
def test_same_ignores_truncated_snapshots_but_not_real_changes(was, now, same):
    assert _same(was, now) is same
