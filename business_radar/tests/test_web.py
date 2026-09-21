"""Walks the whole core loop through the HTTP layer, on a throwaway database.

These are the tests that would catch the failures worth catching: a send control that appears
somewhere it must not, an approval written without a session, a message that reaches SENT
without an approval row, a policy check that lets an UNKNOWN finding into a body. Every one of
them is a rule the design states in prose; here they are as assertions.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("RADAR_HOME", "")

from radar import db as db_mod           # noqa: E402
from radar import ids                    # noqa: E402
from radar.config import (City, Config, ContactPolicyDefaults, DiscoveryConfig,  # noqa: E402
                          EmailConfig, LLMConfig, ResearchConfig, TelegramConfig, WebConfig)
from radar.models import utc_now         # noqa: E402
from radar.web import compose, security  # noqa: E402
from radar.web.app import (CONFIRMATION_TEXT, FORBIDDEN_BUTTON_TEXT,  # noqa: E402
                           create_app, _body_hash)

TEMPLATES = Path(__file__).resolve().parents[1] / "radar" / "web" / "templates"
PASSWORD = "a-good-enough-password"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _config(tmp_path: Path) -> Config:
    return Config(
        cities=(City(slug="dhule", name="Dhule", state_region="Maharashtra",
                     nominatim_query="Dhule, Maharashtra, India", osm_relation_id=None),),
        industries=("HEALTHCARE",),
        categories=("DIAGNOSTIC_CENTER",),
        research=ResearchConfig(),
        discovery=DiscoveryConfig(user_agent="business_radar/test",
                                  overpass_endpoints=("https://overpass-api.de/api/interpreter",)),
        llm=LLMConfig(api_key="", model="gemini-2.5-flash"),
        email=EmailConfig(address="", app_password="", from_name="Sagar"),
        contact_policy=ContactPolicyDefaults(),
        web=WebConfig(),
        telegram=TelegramConfig(),
        config_path=tmp_path / "config.yaml",
        env_path=tmp_path / ".env",
    )


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_SECRET_KEY", "test-key-not-a-real-one")
    db_path = tmp_path / "radar.db"
    conn = db_mod.open_migrated(db_path)
    _seed(conn)
    conn.close()
    application = create_app(_config(tmp_path), db_path)
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    with app.test_client() as test_client:
        test_client.post("/setup", data={"email": "sagar@example.com",
                                         "display_name": "Sagar",
                                         "password": PASSWORD, "confirm": PASSWORD,
                                         "csrf_token": _csrf(test_client, "/setup")})
        test_client.post("/login", data={"email": "sagar@example.com", "password": PASSWORD,
                                         "csrf_token": _csrf(test_client, "/login")})
        yield test_client


def _csrf(test_client, path: str) -> str:
    page = test_client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page)
    return match.group(1) if match else ""


CAMPAIGN = "cmp_00000000000000000000000001"
BUSINESS = "biz_00000000000000000000000001"
OWNER = "usr_00000000000000000000000000"


def _seed(conn) -> None:
    """One campaign, one researched business, three findings, a contact, an opportunity."""
    with db_mod.transaction(conn):
        conn.execute(
            "INSERT INTO campaigns (id, name, slug, created_by, status, min_opportunity_score) "
            "VALUES (?, 'Dhule sweep', 'dhule-sweep', ?, 'RESEARCHING', 50)",
            (CAMPAIGN, OWNER),
        )
        conn.execute(
            "INSERT INTO campaign_cities (campaign_id, city, city_slug, ordinal) "
            "VALUES (?, 'Dhule', 'dhule', 0)", (CAMPAIGN,),
        )
        conn.execute(
            "INSERT INTO businesses (id, business_key, name, name_norm, city, city_slug, "
            "        industry, category, size_band, website, website_domain, website_status, "
            "        status, research_status, first_seen_campaign_id) "
            "VALUES (?, 'dhule|sample-diagnostics', 'SAMPLE Diagnostics Centre', "
            "        'sample diagnostics centre', 'Dhule', 'dhule', 'HEALTHCARE', "
            "        'DIAGNOSTIC_CENTER', 'SMALL', 'https://sample.example.in', "
            "        'sample.example.in', 'PRESENT', 'AI_RESEARCHED', 'COMPLETE', ?)",
            (BUSINESS, CAMPAIGN),
        )
        conn.execute(
            "INSERT INTO campaign_businesses (id, campaign_id, business_id, city_at_discovery, "
            "        industry_at_discovery, category_at_discovery) "
            "VALUES (?,?,?, 'Dhule', 'HEALTHCARE', 'DIAGNOSTIC_CENTER')",
            (ids.new_id("cbz"), CAMPAIGN, BUSINESS),
        )

        run_id = ids.new_id("res")
        conn.execute(
            "INSERT INTO research_runs (id, business_id, campaign_id, status, model_id, "
            "        prompt_version, started_at, finished_at) "
            "VALUES (?,?,?, 'COMPLETE', 'gemini-2.5-flash', 'research-v1', ?, ?)",
            (run_id, BUSINESS, CAMPAIGN, utc_now(), utc_now()),
        )
        source_id = ids.new_id("src")
        conn.execute(
            "INSERT INTO sources (id, business_id, name, url, source_type, "
            "        information_obtained, url_norm, domain, research_run_id) "
            "VALUES (?,?, 'Practice website', 'https://sample.example.in/services', 'SITE', "
            "        'services list, no patient portal', 'sample.example.in/services', "
            "        'sample.example.in', ?)",
            (source_id, BUSINESS, run_id),
        )

        observed = ids.new_id("fnd")
        conn.execute(
            "INSERT INTO research_findings (id, business_id, research_run_id, kind, dimension, "
            "        label, statement, confidence, confidence_pct, ordinal) "
            "VALUES (?,?,?, 'OBSERVED', 'DIGITAL_PRESENCE', 'No patient portal', "
            "        'The website lists four services and offers no patient login or online "
            "report download.', 'HIGH', 88, 1)",
            (observed, BUSINESS, run_id),
        )
        conn.execute("INSERT INTO finding_sources (finding_id, source_id) VALUES (?,?)",
                     (observed, source_id))

        inferred = ids.new_id("fnd")
        conn.execute(
            "INSERT INTO research_findings (id, business_id, research_run_id, kind, dimension, "
            "        label, statement, confidence, confidence_pct, derived_from, "
            "        inference_note, ordinal) "
            "VALUES (?,?,?, 'INFERRED', 'OPERATIONS', 'Manual report delivery', "
            "        'Report delivery is handled at the counter rather than online.', "
            "        'MEDIUM', 64, ?, 'A four-service lab with no portal usually hands "
            "reports over at the counter.', 2)",
            (inferred, BUSINESS, run_id, json.dumps([observed])),
        )
        conn.execute(
            "INSERT INTO research_findings (id, business_id, research_run_id, kind, dimension, "
            "        label, statement, confidence, unknown_reason, ordinal) "
            "VALUES (?,?,?, 'UNKNOWN', 'SCALE', 'Daily patient volume', "
            "        'How many patients pass through in a day is not published anywhere.', "
            "        'LOW', 'NOT_PUBLISHED', 3)",
            (ids.new_id("fnd"), BUSINESS, run_id),
        )

        opportunity_id = ids.new_id("opp")
        conn.execute(
            "INSERT INTO opportunities (id, business_id, research_run_id, campaign_id, "
            "        potential_problem, potential_solution, expected_benefit, score, band, "
            "        confidence, confidence_pct, model_id, prompt_version) "
            "VALUES (?,?,?,?, 'Reports and billing are tracked on paper across four services.', "
            "        'A diagnostic centre operations platform', "
            "        'One record per visit, and report turnaround becomes measurable.', "
            "        72, 'MEDIUM', 'MEDIUM', 64, 'gemini-2.5-flash', 'score-v1')",
            (opportunity_id, BUSINESS, run_id, CAMPAIGN),
        )
        for ordinal, module in enumerate(("PATIENTS", "BILLING", "REPORTS")):
            conn.execute(
                "INSERT INTO opportunity_modules (id, opportunity_id, business_id, module, "
                "        ordinal) VALUES (?,?,?,?,?)",
                (ids.new_id("opp"), opportunity_id, BUSINESS, module, ordinal),
            )

        conn.execute(
            "INSERT INTO business_contacts (id, business_id, kind, value_raw, value_norm, "
            "        value_dedupe, value_display, domain, is_role_address, is_primary, "
            "        source_url) "
            "VALUES (?,?, 'EMAIL', 'info@sample.example.in', 'info@sample.example.in', "
            "        'info@sample.example.in', 'info@sample.example.in', 'sample.example.in', "
            "        1, 1, 'https://sample.example.in/contact')",
            (ids.new_id("cnt"), BUSINESS),
        )


# ---------------------------------------------------------------------------
# the rules the templates make impossible
# ---------------------------------------------------------------------------

def test_send_control_is_local():
    """No send / transmit / dispatch control in any template but the confirm dialog."""
    allowed = TEMPLATES / "outreach" / "confirm_dialog.html"
    pattern = re.compile(r"<(button|a)\b([^>]*)>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
    verb = re.compile(r"\b(send|transmit|dispatch)\b", re.IGNORECASE)
    offenders = []
    for path in TEMPLATES.rglob("*.html"):
        if path == allowed:
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            attrs, label = match.group(2), match.group(3)
            if not verb.search(label):
                continue
            # "Confirm & send..." carries an ellipsis because it opens the dialog; the
            # control that transmits lives inside the dialog and nowhere else.
            if "&hellip;" in label or "..." in label:
                continue
            offenders.append((path.name, attrs.strip(), " ".join(label.split())))
    assert offenders == []


def test_no_forbidden_send_labels():
    for path in TEMPLATES.rglob("*.html"):
        body = path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_BUTTON_TEXT:
            assert phrase not in body, f"{path.name} contains {phrase!r}"


def test_no_bulk_verify_control():
    for path in TEMPLATES.rglob("*.html"):
        body = path.read_text(encoding="utf-8").lower()
        for phrase in ("verify-all", "approve-all", "approve_selected", "verify_selected"):
            assert phrase not in body


def test_confirmation_text_is_one_constant():
    dialog = (TEMPLATES / "outreach" / "confirm_dialog.html").read_text(encoding="utf-8")
    assert "{{ CONFIRMATION_TEXT }}" in dialog
    assert CONFIRMATION_TEXT == (
        "You are about to contact this business using the selected business contact."
    )


def test_findings_render_three_fieldsets(client):
    page = client.get(f"/business/{BUSINESS}").get_data(as_text=True)
    assert page.count("<fieldset") == 3
    assert "Do not assert these" in page


# ---------------------------------------------------------------------------
# auth and CSRF
# ---------------------------------------------------------------------------

def test_anonymous_is_redirected(app):
    with app.test_client() as anon:
        assert anon.get("/").status_code == 302
        assert anon.get(f"/business/{BUSINESS}").status_code == 302


def test_post_without_csrf_is_refused(client):
    response = client.post("/outreach/select", data={"business_id": BUSINESS})
    assert response.status_code == 400


def test_password_round_trip():
    stored = security.hash_password(PASSWORD)
    assert security.verify_password(stored, PASSWORD)
    assert not security.verify_password(stored, PASSWORD + "x")
    assert not security.verify_password("!locked-no-login", PASSWORD)


# ---------------------------------------------------------------------------
# the loop
# ---------------------------------------------------------------------------

def _verify_business(client, app):
    client.get(f"/verify/{BUSINESS}")
    # The dwell floor is real: backdate started_at rather than sleeping twenty seconds.
    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    with db_mod.transaction(conn):
        conn.execute(
            "UPDATE verifications SET started_at = datetime('now','-120 seconds') "
            " WHERE business_id = ? AND state = 'DRAFT'", (BUSINESS,),
        )
        conn.execute(
            "UPDATE verifications SET started_at = "
            "  strftime('%Y-%m-%dT%H:%M:%SZ','now','-120 seconds') "
            " WHERE business_id = ? AND state = 'DRAFT'", (BUSINESS,),
        )
    conn.close()

    data = {"csrf_token": _csrf(client, f"/verify/{BUSINESS}"), "action": "approve",
            "why_note": "Site lists four services and no patient portal; counter collection "
                        "is plausible."}
    for key, _p, _h in __import__("radar.web.app", fromlist=["CHECKLIST"]).CHECKLIST:
        data["check_" + key] = "on"
    return client.post(f"/verify/{BUSINESS}", data=data, follow_redirects=True)


def test_verification_ladder_refuses_an_incomplete_checklist(client):
    client.get(f"/verify/{BUSINESS}")
    response = client.post(
        f"/verify/{BUSINESS}",
        data={"csrf_token": _csrf(client, f"/verify/{BUSINESS}"), "action": "approve",
              "why_note": "too short"},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert "not ticked" in page
    assert "dwell" in page.lower()


def test_full_loop_verify_select_prepare_approve_and_hold(client, app):
    response = _verify_business(client, app)
    page = response.get_data(as_text=True)
    assert "Verified." in page
    # No confirmed contact yet, so it stops at VERIFIED rather than CONTACT_READY.
    assert "no confirmed contact" in page.lower()

    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    contact_id = conn.execute(
        "SELECT id FROM business_contacts WHERE business_id = ?", (BUSINESS,)
    ).fetchone()["id"]
    conn.close()

    client.post(f"/business/{BUSINESS}/contact/{contact_id}/confirm",
                data={"csrf_token": _csrf(client, f"/business/{BUSINESS}")},
                follow_redirects=True)

    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    status = conn.execute("SELECT status FROM businesses WHERE id = ?",
                          (BUSINESS,)).fetchone()["status"]
    conn.close()
    assert status == "CONTACT_READY"

    client.post("/outreach/select", data={"csrf_token": _csrf(client, "/outreach"),
                                          "business_id": BUSINESS}, follow_redirects=True)
    client.post("/outreach/prepare", data={"csrf_token": _csrf(client, "/outreach")},
                follow_redirects=True)

    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    draft = conn.execute("SELECT * FROM outreach_drafts").fetchone()
    message = conn.execute("SELECT * FROM outreach_messages").fetchone()
    conn.close()
    assert draft is not None
    assert draft["id"].startswith("out_")
    assert draft["model_id"] and draft["prompt_version"]
    assert message["status"] == "PENDING_APPROVAL"

    preview = client.get(f"/outreach/{draft['id']}").get_data(as_text=True)
    assert "Research basis" in preview
    assert "Daily patient volume" in preview          # UNKNOWN is shown to Sagar...
    assert "Daily patient volume" not in draft["body"]  # ...and never to the recipient.
    assert CONFIRMATION_TEXT in preview

    # Approve and attempt the send. The email channel has no credentials, so the message is
    # held on disk and stays APPROVED - doc 17 section 17.4.1.
    client.post(f"/outreach/{draft['id']}/approve",
                data={"csrf_token": _csrf(client, f"/outreach/{draft['id']}"),
                      "then": "send", "confirm_word": "SEND"},
                follow_redirects=True)

    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    message = conn.execute("SELECT * FROM outreach_messages").fetchone()
    approval = conn.execute("SELECT * FROM outreach_approvals").fetchone()
    conn.close()

    assert approval is not None
    assert approval["confirmation_text"] == CONFIRMATION_TEXT
    assert approval["approved_by"] != ""
    assert approval["session_auth_method"] == "PASSWORD"
    assert message["status"] == "APPROVED"
    assert message["approval_id"] == approval["id"]
    assert approval["approved_body_hash"] == message["body_hash"]


def test_database_refuses_sent_without_an_approval(client, app):
    """Invariant 2, at the layer that cannot be argued with."""
    import sqlite3

    _verify_business(client, app)
    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    contact_id = conn.execute("SELECT id FROM business_contacts").fetchone()["id"]
    conn.close()
    client.post(f"/business/{BUSINESS}/contact/{contact_id}/confirm",
                data={"csrf_token": _csrf(client, f"/business/{BUSINESS}")},
                follow_redirects=True)
    client.post("/outreach/select", data={"csrf_token": _csrf(client, "/outreach"),
                                          "business_id": BUSINESS}, follow_redirects=True)
    client.post("/outreach/prepare", data={"csrf_token": _csrf(client, "/outreach")},
                follow_redirects=True)

    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    message_id = conn.execute("SELECT id FROM outreach_messages").fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        with db_mod.transaction(conn):
            conn.execute("UPDATE outreach_messages SET status = 'SENT', sent_at = ? WHERE id = ?",
                         (utc_now(), message_id))
    conn.close()


def test_send_refuses_a_blank_approval_id(app):
    from radar.web import transmit

    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    with pytest.raises(transmit.SendRefused):
        transmit.send(conn, app.config["RADAR_CONFIG"], message_id="msg_x", approval_id="",
                      actor="usr_x", channel_configured=False)
    conn.close()


def test_suppression_blocks_selection(client, app):
    _verify_business(client, app)
    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    contact_id = conn.execute("SELECT id FROM business_contacts").fetchone()["id"]
    conn.close()
    client.post(f"/business/{BUSINESS}/contact/{contact_id}/confirm",
                data={"csrf_token": _csrf(client, f"/business/{BUSINESS}")},
                follow_redirects=True)

    client.post(f"/business/{BUSINESS}/suppress",
                data={"csrf_token": _csrf(client, f"/business/{BUSINESS}"),
                      "confirm_word": "SUPPRESS", "note": "asked us to stop"},
                follow_redirects=True)
    page = client.get(f"/business/{BUSINESS}").get_data(as_text=True)
    assert "DO NOT CONTACT" in page

    client.post("/outreach/select", data={"csrf_token": _csrf(client, "/outreach"),
                                          "business_id": BUSINESS}, follow_redirects=True)
    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    selection = conn.execute("SELECT state, blocking_gate FROM selections").fetchone()
    conn.close()
    assert selection["state"] == "BLOCKED"
    assert selection["blocking_gate"] == "A_SUPPRESSED"


# ---------------------------------------------------------------------------
# invariant 4: the claim policy engine
# ---------------------------------------------------------------------------

def test_claim_check_blocks_an_unknown_claim(app):
    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    verdict = compose.check_claims(
        conn, business_id=BUSINESS, subject="x",
        body=("Hello team,\nYour daily patient volume must be a strain.\nRegards,\nSagar\n"
              "--\nTo stop receiving these, reply with UNSUBSCRIBE."),
        unsubscribe_marker="UNSUBSCRIBE", sender_name="Sagar",
    )
    conn.close()
    assert verdict.result == "BLOCK"
    assert any(v["rule"] == "K3" for v in verdict.findings)


def test_claim_check_blocks_an_unhedged_inference(app):
    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    verdict = compose.check_claims(
        conn, business_id=BUSINESS, subject="x",
        body=("Hello team,\nYour report delivery is handled at the counter.\n"
              "Regards,\nSagar\n--\nTo stop receiving these, reply with UNSUBSCRIBE."),
        unsubscribe_marker="UNSUBSCRIBE", sender_name="Sagar",
    )
    conn.close()
    assert verdict.result == "BLOCK"
    assert any(v["rule"] == "K1" for v in verdict.findings)


def test_claim_check_blocks_a_missing_unsubscribe(app):
    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    verdict = compose.check_claims(
        conn, business_id=BUSINESS, subject="x",
        body="Hello team,\nRegards,\nSagar",
        unsubscribe_marker="UNSUBSCRIBE", sender_name="Sagar",
    )
    conn.close()
    assert verdict.result == "BLOCK"
    assert any(v["rule"] == "R1" for v in verdict.findings)


def test_local_composer_passes_its_own_check(app):
    conn = db_mod.connect(app.config["RADAR_DB_PATH"])
    business = conn.execute("SELECT * FROM businesses WHERE id = ?", (BUSINESS,)).fetchone()
    composed = compose.compose_locally(
        conn, business=business, channel="EMAIL", sender_name="Sagar", sender_company="",
        unsubscribe_line="To stop receiving these, reply with UNSUBSCRIBE.",
    )
    verdict = compose.check_claims(
        conn, business_id=BUSINESS, subject=composed.subject, body=composed.body,
        unsubscribe_marker="UNSUBSCRIBE", sender_name="Sagar",
    )
    conn.close()
    assert verdict.result in ("PASS", "WARN")
    assert composed.facts_used
    assert "Daily patient volume" not in composed.body


def test_body_hash_covers_the_subject():
    assert _body_hash("a", "b") != _body_hash("ab", "")


# ---------------------------------------------------------------------------
# every screen renders
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/", "/campaigns", f"/campaigns/{CAMPAIGN}",
                                  f"/business/{BUSINESS}", "/outreach", "/handoffs",
                                  "/settings/channels"])
def test_pages_render(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "Traceback" not in response.get_data(as_text=True)
