"""The report tests: the file renders, and the two properties that make it safe hold.

There are only two things about this report that can hurt somebody, and both are tested here
rather than left to review.

The first is that a number with nothing behind it must not render as a zero. A KPI showing 0 is
a claim that we looked and the answer was none; an em dash admits we do not know. Sagar works
down the "no website" list first, so an unassessed business rendered as 0 puts a business
nobody has researched at the top of the list he acts on.

The second is that the exported file must carry no capability: no form, no token, no contact
address, no send control. It is a document people forward by email, and the worst thing anybody
should be able to do with a forwarded copy is read it.

No network, no API key, one temporary database.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import db, report
from radar.ids import new_id

OWNER = "usr_00000000000000000000000000"
CAMPAIGN = "cmp_01TEST0000000000000000001"
READY = "biz_01TEST00000000000000READY"
RAW = "biz_01TEST000000000000000RAW"


@pytest.fixture()
def conn(tmp_path: Path):
    connection = db.open_migrated(tmp_path / "radar.db")
    _seed(connection)
    yield connection
    connection.close()


def _seed(conn: sqlite3.Connection) -> None:
    """One campaign, two cities, two businesses: one complete, one untouched.

    The untouched business is the point of the fixture. It has no research run, no score and no
    website check, so every metric on its row is unknown, and that is what the em-dash tests
    read.
    """
    with db.transaction(conn) as tx:
        tx.execute(
            """INSERT INTO campaigns (id, name, slug, created_by, created_at,
                min_opportunity_score, research_depth, status)
               VALUES (?,?,?,?,?,?,?,?)""",
            (CAMPAIGN, "Dhule - test", "dhule-test", OWNER, "2026-08-26T07:12:00Z", 60,
             "STANDARD", "COMPLETE"),
        )
        for ordinal, (city, slug) in enumerate((("Dhule", "dhule"), ("Shirpur", "shirpur"))):
            tx.execute(
                """INSERT INTO campaign_cities (campaign_id, city, city_slug, ordinal, status)
                   VALUES (?,?,?,?, 'COMPLETE')""",
                (CAMPAIGN, city, slug, ordinal),
            )

        rows = (
            (READY, "ABC Hospital", "HOSPITAL", "MEDIUM", "https://abc-hospital.example",
             "PRESENT", 62, 86, "HIGH", "MEDIUM", 64, "CONTACT_READY", "COMPLETE"),
            (RAW, "Patil Auto Garage", "GARAGE", "UNKNOWN", None, "UNKNOWN", None, None, None,
             None, None, "AI_RESEARCHED", "PENDING"),
        )
        for (bid, name, category, size, site, wstat, dm, score, band, conf, cpct, status,
             rstatus) in rows:
            tx.execute(
                """INSERT INTO businesses (id, business_key, name, name_norm, city, city_slug,
                    industry, category, size_band, website, website_domain, website_status,
                    digital_maturity, opportunity_score, opportunity_band, research_confidence,
                    research_confidence_pct, status, research_status, first_seen_campaign_id)
                   VALUES (?,?,?,?, 'Dhule','dhule', 'HEALTHCARE', ?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (bid, f"dhule|{name}", name, name.lower(), category, size, site,
                 site.split("//")[1] if site else None, wstat, dm, score, band, conf, cpct,
                 status, rstatus, CAMPAIGN),
            )
            tx.execute(
                """INSERT INTO campaign_businesses (id, campaign_id, business_id, state,
                    first_seen_at, city_at_discovery, industry_at_discovery,
                    category_at_discovery)
                   VALUES (?,?,?, 'INCLUDED', '2026-08-26T07:12:00Z', 'Dhule', 'HEALTHCARE', ?)""",
                (new_id("cbz"), CAMPAIGN, bid, category),
            )

        run = new_id("res")
        tx.execute(
            """INSERT INTO research_runs (id, business_id, campaign_id, status, model_id,
                prompt_version, started_at, finished_at, n_findings, n_sources)
               VALUES (?,?,?, 'COMPLETE', 'gemini-2.5-flash', 'research-v4',
                       '2026-08-23T07:39:00Z', '2026-08-23T07:41:00Z', 3, 1)""",
            (run, READY, CAMPAIGN),
        )
        src = new_id("src")
        tx.execute(
            """INSERT INTO sources (id, business_id, name, url, source_type,
                information_obtained, url_norm, domain, research_run_id, checked_at)
               VALUES (?,?, 'Practice website', 'https://abc-hospital.example/about', 'SITE',
                       'departments', 'https://abc-hospital.example/about',
                       'abc-hospital.example', ?, '2026-08-23T07:40:00Z')""",
            (src, READY, run),
        )
        observed = new_id("fnd")
        tx.execute(
            """INSERT INTO research_findings (id, business_id, research_run_id, kind, dimension,
                label, statement, confidence, confidence_pct, weight)
               VALUES (?,?,?, 'OBSERVED', 'OPERATIONS', 'Departments listed',
                 'The website lists four clinical departments and their timings.', 'HIGH', 88, 2.0)""",
            (observed, READY, run),
        )
        tx.execute("INSERT INTO finding_sources (finding_id, source_id) VALUES (?,?)",
                   (observed, src))
        tx.execute(
            """INSERT INTO research_findings (id, business_id, research_run_id, kind, dimension,
                label, statement, confidence, derived_from, inference_note)
               VALUES (?,?,?, 'INFERRED', 'SYSTEMS', 'Records likely departmental',
                 'Patient records are likely handled department by department.', 'MEDIUM', ?,
                 'Four departments, no shared portal.')""",
            (new_id("fnd"), READY, run, f'["{observed}"]'),
        )
        tx.execute(
            """INSERT INTO research_findings (id, business_id, research_run_id, kind, dimension,
                label, statement, confidence, unknown_reason)
               VALUES (?,?,?, 'UNKNOWN', 'SYSTEMS', 'Billing software',
                 'Whether any billing software is in use could not be established.', 'LOW',
                 'NOT_PUBLISHED')""",
            (new_id("fnd"), READY, run),
        )
        opp = new_id("opp")
        tx.execute(
            """INSERT INTO opportunities (id, business_id, research_run_id, campaign_id,
                potential_problem, potential_solution, expected_benefit, score, band,
                confidence, confidence_pct, digital_maturity, score_breakdown, est_value_inr,
                model_id, prompt_version)
               VALUES (?,?,?,?, 'Records kept per department.', 'Hospital Operations Platform',
                 'One view of admissions and billing.', 86, 'HIGH', 'MEDIUM', 64, 62, ?, 240000,
                 'gemini-2.5-flash', 'score-v3')""",
            (opp, READY, run, CAMPAIGN,
             '[{"component":"Operational complexity","points":22,"of":25,'
             f'"because_finding_id":"{observed}"}}]'),
        )
        tx.execute(
            """INSERT INTO opportunity_modules (id, opportunity_id, business_id, module,
                ordinal) VALUES (?,?,?, 'DASHBOARD', 0)""",
            (new_id("opp"), opp, READY),
        )
        tx.execute(
            """INSERT INTO verifications (id, business_id, campaign_id, state, verdict,
                checks_passed, checks_failed, why_note, dwell_ms, verified_by, verified_at)
               VALUES (?,?,?, 'SUBMITTED', 'VERIFIED', 9, 0,
                 'Checked the site and the listing by hand.', 41000, ?, '2026-08-24T10:00:00Z')""",
            (new_id("ver"), READY, CAMPAIGN, OWNER),
        )
        tx.execute(
            """INSERT INTO business_contacts (id, business_id, kind, value_raw, value_norm,
                value_dedupe, value_display, domain, human_verified, human_verified_at,
                human_verified_by) VALUES (?,?, 'EMAIL', ?,?,?,?, 'abc-hospital.example', 1,
                '2026-08-24T10:00:00Z', ?)""",
            (new_id("cnt"), READY, "info@abc-hospital.example", "info@abc-hospital.example",
             "info@abc-hospital.example", "info@abc-hospital.example", OWNER),
        )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def test_report_queries_execute_against_the_real_schema(conn):
    """Every query runs. A column name that only exists in prose fails here, not in a report."""
    data = report.load_report_data(conn, CAMPAIGN)
    assert data.row_count == 2
    assert [c.city for c in data.city_cards] == ["Dhule", "Shirpur"]


def test_header_facts_are_live_aggregates(conn):
    data = report.load_report_data(conn, CAMPAIGN)
    assert data.header.found == 2
    assert data.header.researched == 1
    assert data.header.qualified == 1
    assert data.header.needs_verification == 1
    assert data.header.ready == 1


def test_from_row_never_coalesces_a_missing_metric_to_zero(conn):
    data = report.load_report_data(conn, CAMPAIGN)
    raw = next(r for r in data.rows if r.business_id == RAW)
    assert raw.opportunity_score is None
    assert raw.digital_maturity is None
    assert raw.research_confidence is None
    assert raw.website_status == "UNKNOWN"


def test_a_city_that_found_nothing_still_gets_a_card(conn):
    """A missing card reads as 'we did not search Shirpur'. Zeros read as the truth."""
    data = report.load_report_data(conn, CAMPAIGN)
    shirpur = next(c for c in data.city_cards if c.city == "Shirpur")
    assert shirpur.found == 0          # discovery ran and found nothing
    assert shirpur.qualified is None   # nothing researched, so there is no rate to give


def test_conversion_is_none_not_zero_when_nothing_was_contacted(conn):
    data = report.load_report_data(conn, CAMPAIGN)
    for row in data.cmp_city:
        assert row.conversion_pct is None
        assert row.n_responded is None


def test_unscored_businesses_never_reach_the_top_opportunities_table(conn):
    data = report.load_report_data(conn, CAMPAIGN)
    assert [t.business_id for t in data.top20] == [READY]


def test_only_contact_ready_gets_an_enabled_checkbox(conn):
    data = report.load_report_data(conn, CAMPAIGN)
    ready = next(r for r in data.rows if r.business_id == READY)
    raw = next(r for r in data.rows if r.business_id == RAW)
    assert ready.selectable is True
    assert raw.selectable is False
    # The tooltip names the missing precondition, never a generic "not eligible".
    assert "verification" in raw.block_reason.lower()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

@pytest.fixture()
def html(conn, tmp_path: Path) -> str:
    path = report.generate_report(conn, CAMPAIGN, out_dir=tmp_path / "out",
                                  app_base_url="http://127.0.0.1:8770", user_id=OWNER)
    return path.read_text(encoding="utf-8")


def test_export_has_no_form_no_post_and_no_send_control(html):
    lowered = html.lower()
    assert "<form" not in lowered
    assert " method=" not in lowered
    assert "xmlhttprequest" not in lowered
    assert "javascript:" not in lowered
    assert "onclick=" not in lowered
    # Exactly one network call: the optional health probe.
    assert html.count("fetch(") == 1
    assert 'form-action \'none\'' in html


def test_export_carries_no_contact_value(html):
    """Channel availability is a fact about a business. An address is a mailing list."""
    assert "info@abc-hospital.example" not in html


def test_export_loads_no_external_resource(html):
    import re
    for url in re.findall(r'src="([^"]+)"', html):
        assert not url.startswith("http"), url
    assert "@import" not in html
    assert '<link rel="stylesheet"' not in html


def test_zero_and_no_data_render_differently(html):
    assert 'class="na"' in html
    assert 'title="Not scored yet"' in html
    assert 'title="Not assessed"' in html
    assert 'title="Website not checked"' in html


def test_the_three_finding_kinds_are_always_rendered(html):
    for legend in ("Observed - supported by sources",
                   "Inferred - reasonable conclusion, not verified",
                   "Unknown - could not be verified"):
        assert legend in html


def test_a_scraped_name_containing_markup_is_escaped(conn, tmp_path: Path):
    with db.transaction(conn) as tx:
        tx.execute("UPDATE businesses SET name = ? WHERE id = ?",
                   ("<script>alert(1)</script> Clinic", RAW))
    path = report.generate_report(conn, CAMPAIGN, out_dir=tmp_path / "out2")
    body = path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


def test_no_action_links_at_all_without_an_app_base_url(conn, tmp_path: Path):
    """A report mailed to somebody must not carry links that resolve to their machine."""
    path = report.generate_report(conn, CAMPAIGN, out_dir=tmp_path / "out3")
    body = path.read_text(encoding="utf-8")
    assert 'data-deep="1"' not in body
    assert 'aria-disabled="true"' in body


# ---------------------------------------------------------------------------
# The export record
# ---------------------------------------------------------------------------

def test_build_writes_a_report_exports_row_with_both_hashes(conn, tmp_path: Path):
    build = report.build_report(conn, CAMPAIGN, out_dir=tmp_path / "out", user_id=OWNER)
    row = conn.execute("SELECT * FROM report_exports WHERE id = ?", (build.export_id,)).fetchone()
    assert row["fmt"] == "HTML"
    assert row["row_count"] == 2
    assert len(row["content_sha256"]) == 64
    assert len(row["data_sha256"]) == 64
    assert row["contains_pii"] == 0
    assert build.path.exists()


def test_data_sha256_is_stable_while_content_sha256_moves(conn, tmp_path: Path):
    """The asymmetry is the point: same numbers, new file, and both are provable."""
    first = report.build_report(conn, CAMPAIGN, out_dir=tmp_path / "out")
    second = report.build_report(conn, CAMPAIGN, out_dir=tmp_path / "out")
    assert first.data_sha256 == second.data_sha256
    assert first.path != second.path


def test_generation_is_audited(conn, tmp_path: Path):
    from radar.audit import verify_chain
    build = report.build_report(conn, CAMPAIGN, out_dir=tmp_path / "out", user_id=OWNER)
    row = conn.execute(
        "SELECT action, entity_id FROM audit_log WHERE entity_id = ?", (build.export_id,)
    ).fetchone()
    assert row["action"] == "REPORT_GENERATED"
    assert verify_chain(conn) == []


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def test_csv_leaves_unknown_cells_blank_rather_than_zero(conn, tmp_path: Path):
    import csv as csv_mod
    path = report.export_csv(conn, CAMPAIGN, out_dir=tmp_path / "out", user_id=OWNER)
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv_mod.DictReader(handle))
    raw = next(r for r in rows if r["business_id"] == RAW)
    assert raw["digital_maturity"] == ""
    assert raw["opportunity_score"] == ""
    assert raw["research_status"] == "NONE"
    ready = next(r for r in rows if r["business_id"] == READY)
    assert ready["opportunity_score"] == "86"
    assert ready["n_observed"] == "1"


def test_csv_neutralises_a_formula(conn, tmp_path: Path):
    with db.transaction(conn) as tx:
        tx.execute("UPDATE businesses SET name = ? WHERE id = ?", ("=cmd|calc", RAW))
    path = report.export_csv(conn, CAMPAIGN, out_dir=tmp_path / "out")
    assert "'=cmd|calc" in path.read_text(encoding="utf-8-sig")


def test_csv_carries_no_contact_value(conn, tmp_path: Path):
    path = report.export_csv(conn, CAMPAIGN, out_dir=tmp_path / "out")
    assert "info@abc-hospital.example" not in path.read_text(encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# Small helpers with sharp edges
# ---------------------------------------------------------------------------

def test_report_filename_matches_the_spec_example():
    from datetime import date
    name = report.report_filename(["Dhule", "Shirpur", "Nashik", "Jalgaon"], date(2026, 8, 26))
    assert name == "business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.html"


def test_report_filename_collapses_a_long_city_list():
    from datetime import date
    name = report.report_filename(
        ["Nashik", "Jalgaon", "Dhule", "Shirpur", "Malegaon", "Chalisgaon"], date(2026, 8, 26))
    assert name == "business_research_nashik_jalgaon_dhule_plus3more_2026-08-26.html"


def test_inr_uses_indian_digit_grouping():
    assert report.inr(2400000) == "₹ 24,00,000"
    assert report.inr(None) == "—"


def test_safe_url_refuses_anything_that_is_not_absolute_http():
    assert report.safe_url("https://example.com/a") == "https://example.com/a"
    assert report.safe_url("javascript:alert(1)") is None
    assert report.safe_url("/business/biz_1") is None
    assert report.safe_url(None) is None
