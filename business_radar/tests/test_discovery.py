"""Discovery tests: the identity key holds, the SSRF guard holds, and coverage tells the truth.

The three things worth testing here are the three things whose failure is silent.

A broken normaliser does not crash - it creates a second row for a hospital already in the
database, and the first symptom is a second cold email to a business that ignored the first one.
A broken SSRF guard does not crash either; it quietly turns this tool into a proxy into its own
home network. And a coverage band computed against nothing does not crash at all: it prints a
number that reads as reassurance, and Sagar stops working the most under-served town in the
campaign.

No network. The Overpass payloads are seeded into the cache, which is also a test that the cache
works: if it did not, these tests would try to reach the internet and fail.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import db, discover, fetch, identity
from radar.config import (
    City,
    Config,
    ContactPolicyDefaults,
    DiscoveryConfig,
    EmailConfig,
    LLMConfig,
    ResearchConfig,
    TelegramConfig,
    WebConfig,
)
from radar.ids import new_id_for
from radar.paths import CONFIG_PATH, ENV_PATH

OWNER = "usr_00000000000000000000000000"
SHIRPUR = City(slug="shirpur", name="Shirpur", nominatim_query="Shirpur, Maharashtra, India")


@pytest.fixture()
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(discover, "OVERPASS_CACHE_DIR", tmp_path / "cache" / "overpass")
    connection = db.connect(tmp_path / "radar.db")
    db.migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def cfg() -> Config:
    return Config(
        cities=(SHIRPUR,),
        industries=(),
        categories=("HOSPITAL", "BAKERY"),
        research=ResearchConfig(),
        discovery=DiscoveryConfig(
            user_agent="business-radar/1.0 (+https://example.test/about; contact: a@b.test)",
            overpass_endpoints=("https://overpass-api.de/api/interpreter",),
        ),
        llm=LLMConfig(api_key=""),
        email=EmailConfig(address="", app_password=""),
        contact_policy=ContactPolicyDefaults(),
        web=WebConfig(),
        telegram=TelegramConfig(bot_token="", chat_id=""),
        config_path=CONFIG_PATH,
        env_path=ENV_PATH,
        log_level="INFO",
        log_file=None,
    )


def make_campaign(connection: sqlite3.Connection) -> str:
    campaign_id = new_id_for("campaigns")
    with db.transaction(connection):
        connection.execute(
            "INSERT INTO campaigns (id, name, slug, created_by, status) "
            "VALUES (?,?,?,?,'DISCOVERING')",
            (campaign_id, "Shirpur test", "shirpur-test", OWNER),
        )
    return campaign_id


BOUND = discover.CityBound(
    slug="shirpur", name="Shirpur", kind="RADIUS",
    lat=21.3486, lon=74.8805, radius_m=7000, source="NOMINATIM_RADIUS",
)


def seed(connection: sqlite3.Connection, cfg: Config, categories, elements) -> None:
    """Put an Overpass answer in the cache, so discover_city needs no network."""
    query = discover.build_query(
        BOUND, categories,
        timeout_seconds=cfg.discovery.overpass_timeout_seconds,
        element_cap=cfg.discovery.overpass_element_cap,
    )
    discover._store_cache_row(
        connection, provider="OSM_OVERPASS", key=discover.query_hash(query),
        query_text=query, payload={"elements": elements},
        element_count=len(elements), truncated=False, ttl_days=30,
    )


# --------------------------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name, city, website, phone, phone_type, expected_norm, expected_key",
    [
        ("A.B.C. Hospital", "Dhule", None, None, None, "abc hospital", "n:abc hospital@dhule"),
        ("ABC Hospital, Dhule", "Dhule", None, None, None, "abc hospital", "n:abc hospital@dhule"),
        ("ABC HOSPITAL PVT LTD", "Dhule", None, None, None, "abc hospital", "n:abc hospital@dhule"),
        ("M/s A B C Hospital & Sons", "Dhule", None, None, None, "abc hospital",
         "n:abc hospital@dhule"),
        ("ABC Hospital", "Dhule", "https://WWW.ABC-Hospital.IN/", None, None, "abc hospital",
         "d:abc-hospital.in"),
        ("ABC Multispeciality Hospital", "Dhule", "http://abc-hospital.in/about", None, None,
         "abc multispeciality hospital", "d:abc-hospital.in"),
        ("श्री ABC रुग्णालय",
         "Dhule", None, None, None, "shree abc hospital", "n:shree abc hospital@dhule"),
        ("Shri ABC Hospital", "Dhule", None, None, None, "shree abc hospital",
         "n:shree abc hospital@dhule"),
        ("Sri A.B.C. Hospital", "Dhule", None, None, None, "shree abc hospital",
         "n:shree abc hospital@dhule"),
        ("Krishna Motors", "Nashik", None, "+919812345678", "MOBILE", "krishna motors",
         "p:+919812345678"),
        ("Krishna Auto", "Nashik", None, "+919812345678", "MOBILE", "krishna auto",
         "p:+919812345678"),
        ("Krishna Motors", "Nashik", None, "+912532345678", "FIXED_LINE", "krishna motors",
         "n:krishna motors@nashik"),
        ("Nashik Motors", "Dhule", None, None, None, "nashik motors", "n:nashik motors@dhule"),
        ("Laxmi Industries Pvt. Ltd.", "Jalgaon", None, None, None, "lakshmi industries",
         "n:lakshmi industries@jalgaon"),
        ("Lakshmi Inds", "Jalgaon", None, None, None, "lakshmi industries",
         "n:lakshmi industries@jalgaon"),
        ("Shree Bakery", "Shirpur", None, None, None, "shree bakery", "n:shree bakery@shirpur"),
        ("Shree Bakery", "Dhule", None, None, None, "shree bakery", "n:shree bakery@dhule"),
    ],
)
def test_business_key_normalisation(name, city, website, phone, phone_type,
                                    expected_norm, expected_key):
    """The SAMPLE table of 01-data-model.md section 1.12.3, row by row."""
    assert identity.normalise_name(name, city=city) == expected_norm
    assert identity.business_key(
        name=name, city=city, website=website,
        phone_norm=phone, phone_number_type=phone_type,
    ) == expected_key


def test_a_landline_never_takes_the_phone_branch():
    """A reception number shared by two clinics in one building must not merge them."""
    key = identity.business_key(
        name="Krishna Motors", city="Nashik",
        phone_norm="+912532345678", phone_number_type="FIXED_LINE",
    )
    assert key.startswith("n:")


def test_business_key_refuses_to_be_empty():
    with pytest.raises(ValueError):
        identity.business_key(name="...", city="Dhule")


def test_similarity_never_merges_across_cities():
    is_candidate, _ = identity.merge_candidates(
        "shree bakery", "shree bakery", same_city=False, same_category=True,
    )
    assert is_candidate is False


def test_phone_and_email_normalisation():
    mobile = identity.normalise_phone("+91 98123 45678")
    assert (mobile.e164, mobile.number_type, mobile.is_mobile) == ("+919812345678", "MOBILE", True)

    landline = identity.normalise_phone("02562-123456")
    assert (landline.e164, landline.number_type) == ("+912562123456", "FIXED_LINE")

    assert identity.normalise_phone("12345").valid is False

    gmail = identity.normalise_email("Owner.Name+leads@GMail.com")
    assert gmail.value_norm == "owner.name+leads@gmail.com"
    assert gmail.value_dedupe == "ownername@gmail.com"
    assert gmail.is_role_address is False

    role = identity.normalise_email("info@abchospital.in")
    assert role.is_role_address is True


# --------------------------------------------------------------------------------------------
# The fetcher's guards
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://192.168.1.1/",
    "http://10.0.0.5/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "file:///etc/passwd",
    "ftp://example.com/x",
    "javascript:alert(1)",
    "https://www.justdial.com/listing",
])
def test_the_fetcher_refuses_what_it_must(url):
    """The laptop's own network is behind this check, and so is the loopback the app binds to."""
    with pytest.raises(fetch.FetchError):
        fetch.check_url(url)


def test_html_becomes_readable_text():
    html = (
        "<html><head><title>ABC Hospital</title></head><body>"
        "<script>var secret = 1</script>"
        "<h1>ABC Hospital</h1><p>Call 02562-123456 or write to info@abc-hospital.in</p>"
        "<a href='/about'>About us</a></body></html>"
    )
    text, title, links = fetch.extract_text(html)
    assert title == "ABC Hospital"
    assert "secret" not in text
    assert "ABC Hospital" in text
    assert links == ["/about"]
    assert fetch.extract_emails(text) == ["info@abc-hospital.in"]
    assert "02562-123456" in fetch.extract_phones(text)


# --------------------------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------------------------

def test_an_area_query_is_bounded_by_the_relation():
    bound = discover.CityBound(slug="dhule", name="Dhule", kind="AREA", area_id=3607400592)
    query = discover.build_query(bound, ["HOSPITAL"])
    assert "area(3607400592)->.city;" in query
    assert '(area.city);' in query
    assert query.rstrip().endswith("out tags center 2000;")
    assert "out body" not in query


def test_a_radius_query_says_so():
    query = discover.build_query(BOUND, ["BAKERY"])
    assert "(around:7000,21.3486,74.8805)" in query
    assert "area(" not in query


def test_every_category_has_a_tag_map():
    """A category with no selectors would silently return nothing and look like a small town."""
    from radar.models import CATEGORIES

    for category in CATEGORIES:
        assert discover.CATEGORY_SELECTORS.get(category), category
        assert discover.INDUSTRY_OF_CATEGORY.get(category), category

    covered = {c for cats in discover.TAG_GROUPS.values() for c in cats}
    assert covered == set(CATEGORIES)


def test_the_query_hash_changes_when_a_selector_changes():
    """The cache key is the exact QL, so a stale answer can never serve a new question."""
    a = discover.build_query(BOUND, ["BAKERY"])
    b = discover.build_query(BOUND, ["BAKERY", "HOTEL"])
    assert discover.query_hash(a) != discover.query_hash(b)


# --------------------------------------------------------------------------------------------
# Classification and parsing
# --------------------------------------------------------------------------------------------

def test_a_nursing_home_is_promoted_to_hospital():
    industry, category = discover.classify_element(
        {"amenity": "clinic", "name": "Krishna Nursing Home", "beds": "20"}
    )
    assert (industry, category) == ("HEALTHCARE", "HOSPITAL")


def test_a_plain_clinic_is_healthcare_but_not_a_hospital():
    """Real prospects, but no _CONTEXT category fits. Forcing them into HOSPITAL is worse."""
    assert discover.classify_element({"amenity": "doctors"}) == ("HEALTHCARE", "OTHER")


def test_an_unnamed_element_is_not_a_business():
    records = discover.parse_elements(
        {"elements": [{"type": "node", "id": 1, "lat": 21.0, "lon": 74.0,
                       "tags": {"amenity": "hospital"}}]},
        city_name="Shirpur", city_slug="shirpur",
    )
    assert records[0].is_business is False


def test_a_social_link_never_becomes_the_website():
    records = discover.parse_elements(
        {"elements": [{"type": "node", "id": 2, "lat": 21.0, "lon": 74.0, "tags": {
            "shop": "bakery", "name": "Shree Bakery",
            "website": "https://facebook.com/shreebakery"}}]},
        city_name="Shirpur", city_slug="shirpur",
    )
    assert records[0].website is None
    assert records[0].website_domain is None


# --------------------------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------------------------

def test_no_denominator_means_unknown_not_good():
    """There is no such thing as good coverage measured against nothing."""
    assessment = discover.coverage_confidence(
        City(slug="malegaon", name="Malegaon"), "HOSPITAL", 9, kept=7, tag_rich_pct=40,
    )
    assert assessment.band == "UNKNOWN"
    assert assessment.coverage_pct is None
    assert assessment.denominator_kind == "NONE"
    assert "unknown" in assessment.note.lower()


def test_a_truncated_query_cannot_produce_a_coverage_number():
    assessment = discover.coverage_confidence(
        SHIRPUR, "RETAIL_STORE", 2000, kept=1800, tag_rich_pct=50, truncated=True,
    )
    assert assessment.band == "UNKNOWN"
    assert assessment.coverage_pct is None


def test_name_only_nodes_never_score_high():
    """A mapped area in name only is not a mapped area."""
    band, pct = discover.coverage_band(90, 100, tag_rich_pct=10)
    assert band == "MEDIUM"
    assert pct == 90


def test_a_thin_result_is_low_however_good_the_ratio():
    band, _ = discover.coverage_band(3, 4, tag_rich_pct=100)
    assert band == "LOW"


def test_the_database_refuses_a_dishonest_coverage_row(conn):
    campaign_id = make_campaign(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO discovery_coverage (campaign_id, city, category, denominator_kind,"
            "                                band, coverage_pct, note) "
            "VALUES (?,'shirpur','RETAIL_STORE','NONE','HIGH',90,'a number with no basis')",
            (campaign_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO discovery_coverage (campaign_id, city, category, denominator_kind,"
            "                                band, coverage_pct, note) "
            "VALUES (?,'shirpur','RETAIL_STORE','POPULATION_MODEL','UNKNOWN',40,'unknown, 40%')",
            (campaign_id,),
        )


# --------------------------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------------------------

HEALTH_ELEMENTS = [
    {"type": "way", "id": 111, "center": {"lat": 21.35, "lon": 74.88}, "tags": {
        "amenity": "hospital", "name": "A.B.C. Hospital", "addr:street": "Station Road",
        "addr:postcode": "425405", "phone": "+91 98123 45678",
        "website": "http://www.abc-hospital.in/"}},
    # The same hospital, mapped again as a node with a different spelling. One row, not two.
    {"type": "node", "id": 112, "lat": 21.35, "lon": 74.88, "tags": {
        "amenity": "hospital", "name": "ABC Hospital, Shirpur",
        "website": "https://abc-hospital.in"}},
    # No name: counted as found, never kept, never inserted.
    {"type": "node", "id": 113, "lat": 21.34, "lon": 74.87, "tags": {"amenity": "hospital"}},
    # Permanently closed.
    {"type": "node", "id": 114, "lat": 21.34, "lon": 74.87, "tags": {
        "amenity": "hospital", "name": "Old Civil Hospital", "disused:amenity": "hospital"}},
    # Already opted out, by domain.
    {"type": "node", "id": 115, "lat": 21.34, "lon": 74.87, "tags": {
        "amenity": "hospital", "name": "Said No Hospital", "website": "https://saidno.in"}},
]

BAKERY_ELEMENTS = [
    {"type": "node", "id": 201, "lat": 21.35, "lon": 74.88,
     "tags": {"shop": "bakery", "name": "Shree Bakery"}},
    # An industrial estate polygon: a geographic hint, never a prospect.
    {"type": "way", "id": 202, "center": {"lat": 21.36, "lon": 74.89},
     "tags": {"landuse": "industrial", "name": "Shirpur MIDC Phase II"}},
]


def run_discovery(conn: sqlite3.Connection, cfg: Config, campaign_id: str):
    seed(conn, cfg, ["HOSPITAL"], HEALTH_ELEMENTS)
    seed(conn, cfg, ["BAKERY"], BAKERY_ELEMENTS)
    return discover.discover_city(
        conn, campaign_id, SHIRPUR, ["HOSPITAL", "BAKERY"], cfg=cfg, bound=BOUND,
    )


def test_discovery_writes_businesses_and_dedupes_on_the_key(conn, cfg):
    campaign_id = make_campaign(conn)
    report = run_discovery(conn, cfg, campaign_id)

    names = [r["name"] for r in conn.execute("SELECT name FROM businesses ORDER BY name")]
    assert "A.B.C. Hospital" in names

    # The node remapping of the same hospital shares the domain key: one row, not two, and the
    # row keeps the name it was first discovered under.
    assert conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE business_key = 'd:abc-hospital.in'"
    ).fetchone()[0] == 1
    assert "ABC Hospital, Shirpur" not in names

    # Both elements were recorded as sources against that single business.
    assert conn.execute(
        "SELECT COUNT(*) FROM sources s JOIN businesses b ON b.id = s.business_id "
        " WHERE b.business_key = 'd:abc-hospital.in'"
    ).fetchone()[0] == 2

    assert report.businesses_new == 4          # ABC, Old Civil, Said No, Shree Bakery
    assert report.businesses_rediscovered == 1  # the second ABC element

    # The unnamed node was seen and not kept. That difference is what coverage rests on.
    hospital = conn.execute(
        "SELECT elements_found, elements_kept FROM discovery_coverage WHERE category='HOSPITAL'"
    ).fetchone()
    assert hospital["elements_found"] == 5
    assert hospital["elements_kept"] == 4


def test_a_landuse_polygon_never_becomes_a_prospect(conn, cfg):
    campaign_id = make_campaign(conn)
    run_discovery(conn, cfg, campaign_id)
    assert conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE name LIKE '%MIDC%'"
    ).fetchone()[0] == 0


def test_a_closed_business_is_skipped_not_researched(conn, cfg):
    campaign_id = make_campaign(conn)
    run_discovery(conn, cfg, campaign_id)
    row = conn.execute(
        "SELECT status, skip_reason, research_status FROM businesses WHERE name = ?",
        ("Old Civil Hospital",),
    ).fetchone()
    assert row["status"] == "SKIPPED"
    assert row["research_status"] != "PENDING"


def test_an_opt_out_blocks_a_business_at_discovery(conn, cfg):
    """Invariant 3: an opt-out is absolute, permanent and cross-channel.

    A business that unsubscribed in June must not walk back into a campaign in September just
    because a different query found it.
    """
    campaign_id = make_campaign(conn)
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO suppressions (id, scope, value_norm, reason, source) "
            "VALUES (?,'DOMAIN','saidno.in','REPLY_OPT_OUT','inbox poller')",
            (new_id_for("suppressions"),),
        )
    run_discovery(conn, cfg, campaign_id)

    row = conn.execute(
        "SELECT b.status, cb.state, cb.exclusion_reason "
        "  FROM businesses b JOIN campaign_businesses cb ON cb.business_id = b.id "
        " WHERE b.name = 'Said No Hospital'"
    ).fetchone()
    assert row["status"] == "SKIPPED"
    assert row["state"] == "EXCLUDED"
    assert row["exclusion_reason"] == "LIVE_SUPPRESSION"


def test_contacts_are_written_as_rows_with_their_provenance(conn, cfg):
    campaign_id = make_campaign(conn)
    run_discovery(conn, cfg, campaign_id)
    row = conn.execute(
        "SELECT kind, phone_e164, phone_number_type, human_verified, source_url "
        "  FROM business_contacts WHERE kind = 'PHONE'"
    ).fetchone()
    assert row["phone_e164"] == "+919812345678"
    assert row["phone_number_type"] == "MOBILE"
    assert row["human_verified"] == 0          # nothing from a map is verified
    assert "openstreetmap.org" in row["source_url"]


def test_rerunning_a_city_creates_nothing_and_asks_nobody(conn, cfg):
    """The re-run must be free: no new rows, and - because the cache is seeded - no network."""
    campaign_id = make_campaign(conn)
    first = run_discovery(conn, cfg, campaign_id)
    before = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]

    second = discover.discover_city(
        conn, campaign_id, SHIRPUR, ["HOSPITAL", "BAKERY"], cfg=cfg, bound=BOUND,
    )
    after = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]

    assert first.businesses_new > 0
    assert second.businesses_new == 0
    assert before == after
    assert sorted(second.groups_cached) == ["G1_HEALTH", "G6_RETAIL"]
    assert conn.execute(
        "SELECT COUNT(*) FROM campaign_businesses"
    ).fetchone()[0] == before


def test_discovery_leaves_an_intact_audit_trail(conn, cfg):
    from radar import audit as audit_mod

    campaign_id = make_campaign(conn)
    run_discovery(conn, cfg, campaign_id)

    assert audit_mod.verify_chain(conn) == []
    actions = {
        row["action"] for row in conn.execute(
            "SELECT DISTINCT action FROM audit_log WHERE campaign_id = ?", (campaign_id,)
        )
    }
    assert "BUSINESS_DISCOVERED" in actions
    assert "BUSINESS_REDISCOVERED" in actions


def test_the_campaign_counter_matches_the_rows(conn, cfg):
    """Report numbers come from real rows. n_discovered must not drift from the table."""
    campaign_id = make_campaign(conn)
    report = run_discovery(conn, cfg, campaign_id)
    counter = conn.execute(
        "SELECT n_discovered FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE first_seen_campaign_id = ?", (campaign_id,)
    ).fetchone()[0]
    assert counter == rows == report.businesses_new
