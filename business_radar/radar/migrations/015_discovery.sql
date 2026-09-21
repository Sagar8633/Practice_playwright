-- 010_discovery.sql
--
-- What breaks without this migration: discovery has nowhere to remember that it already asked
-- Overpass a question, and nowhere to record how much of a town it actually saw.
--
-- The first gap costs a volunteer-run service a repeated query every time a campaign is re-run
-- over Dhule, which is how this project's IP gets blocked and how it becomes the thing
-- 02-research-pipeline.md section 2.2.3 refuses to be. The second is worse for Sagar: a Shirpur
-- retail query returns six elements, the report renders six businesses, and he concludes there
-- is no retail opportunity in Shirpur. What actually happened is that nobody has mapped
-- Shirpur's main market street. discovery_coverage is the row that lets the report say so.
--
-- Design source: 02-research-pipeline.md sections 2.3.5 (discovery_cache) and 2.3.6
-- (discovery_coverage), where this is migration 058_discovery.sql.

-- --- OSM provenance on the business row ----------------------------------------------------
-- osm_ref is 'node/123456', 'way/98765' or 'relation/4321': the element this row came from.
-- osm_tags_json is every tag, verbatim, so a changed tag map can be re-applied to a city
-- without asking Overpass the same question again.
ALTER TABLE businesses ADD COLUMN osm_ref TEXT;
ALTER TABLE businesses ADD COLUMN osm_tags_json TEXT;

CREATE INDEX ix_businesses_osm_ref ON businesses(osm_ref) WHERE osm_ref IS NOT NULL;


-- --- discovery_cache -----------------------------------------------------------------------
-- expires_at is a freshness TTL, not a licence term: the date after which we are willing to
-- ask Overpass the same question again. A row is never deleted on expiry.
CREATE TABLE discovery_cache (
    provider        TEXT NOT NULL CHECK (provider IN
                       ('OSM_OVERPASS','NOMINATIM','WIKIDATA','REGISTRY','MANUAL')),
    provider_key    TEXT NOT NULL,        -- query sha256, 'node/123456', or 'dhule|boundary'
    business_id     TEXT REFERENCES businesses(id) ON DELETE CASCADE,

    query_text      TEXT,                 -- the exact Overpass QL or request URL, so a run is
                                          -- reproducible from the row alone
    payload_json    TEXT,                 -- small payloads inline; NULL when payload_path is set
    payload_path    TEXT,                 -- data/cache/overpass/<sha>.json.gz
    payload_sha256  TEXT,
    element_count   INTEGER,
    truncated       INTEGER NOT NULL DEFAULT 0 CHECK (truncated IN (0,1)),

    retention_class TEXT NOT NULL DEFAULT 'DURABLE'
                       CHECK (retention_class IN ('DURABLE','EXPIRING')),
    fetched_at      TEXT NOT NULL,
    expires_at      TEXT,
    purged_at       TEXT,

    PRIMARY KEY (provider, provider_key),
    CHECK (payload_json IS NOT NULL OR payload_path IS NOT NULL OR purged_at IS NOT NULL)
);

CREATE INDEX ix_discovery_cache_expiry   ON discovery_cache(expires_at)
    WHERE expires_at IS NOT NULL AND purged_at IS NULL;
CREATE INDEX ix_discovery_cache_business ON discovery_cache(business_id);


-- --- discovery_coverage --------------------------------------------------------------------
-- One row per (campaign, city, category, provider); rewritten whole each time discovery for
-- that pair completes.
--
-- SIMPLIFIED: 02-research-pipeline.md section 2.3.6 gives this table a 'cov_' primary key, but
-- 'cov' is not a registered prefix in radar/ids.py and adding one there is a change to a shared
-- foundation module. The natural key was already UNIQUE in that design, so it is the primary
-- key here instead. Nothing joins to a coverage row by id.
CREATE TABLE discovery_coverage (
    campaign_id      TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    city             TEXT NOT NULL,       -- city_slug
    category         TEXT NOT NULL,       -- a category, or '*' for the city total
    provider         TEXT NOT NULL DEFAULT 'OSM'
                       CHECK (provider IN ('OSM','REGISTRY','COMBINED')),

    elements_found   INTEGER NOT NULL DEFAULT 0 CHECK (elements_found >= 0),
    elements_kept    INTEGER NOT NULL DEFAULT 0 CHECK (elements_kept  >= 0),
    businesses_new   INTEGER NOT NULL DEFAULT 0 CHECK (businesses_new >= 0),
    tag_rich_pct     INTEGER CHECK (tag_rich_pct IS NULL OR tag_rich_pct BETWEEN 0 AND 100),

    denominator      INTEGER CHECK (denominator IS NULL OR denominator >= 0),
    denominator_kind TEXT NOT NULL
                       CHECK (denominator_kind IN ('REGISTRY','POPULATION_MODEL','NONE')),
    population_used  INTEGER,
    coverage_pct     INTEGER CHECK (coverage_pct IS NULL OR coverage_pct BETWEEN 0 AND 100),
    band             TEXT NOT NULL CHECK (band IN ('HIGH','MEDIUM','LOW','UNKNOWN')),
    truncated        INTEGER NOT NULL DEFAULT 0 CHECK (truncated IN (0,1)),
    note             TEXT NOT NULL,
    computed_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    PRIMARY KEY (campaign_id, city, category, provider),

    -- The two honesty constraints. A band of UNKNOWN may not carry a percentage, because a
    -- number printed next to the word "unknown" gets read as the number. And a missing
    -- denominator may not produce anything except UNKNOWN: there is no such thing as good
    -- coverage measured against nothing.
    CHECK (elements_kept <= elements_found),
    CHECK (band <> 'UNKNOWN' OR coverage_pct IS NULL),
    CHECK (denominator_kind <> 'NONE' OR band = 'UNKNOWN')
);

CREATE INDEX ix_discovery_coverage_campaign ON discovery_coverage(campaign_id, band);
