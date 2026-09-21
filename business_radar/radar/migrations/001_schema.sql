-- business_radar: consolidated core-loop schema.
--
-- SIMPLIFIED: the design pack (01-data-model.md section 1.13.2) specifies 57 numbered
-- migrations. This is one file carrying the tables the working core loop needs. Tables
-- deliberately not created here, each with its owning doc section: discovery_cache and
-- discovery_coverage (02 sections 2.3.5, 2.3.6), business_merges and merge_candidates
-- (01 sections 1.12.5, 1.12.6), draft_findings (11 section 11.15), inbound_emails
-- (07 section 7.1.4), whatsapp_* (08), job_schedules, rate_buckets, spend_ledger
-- (14 sections 14.3.4-14.3.6), sessions and api_tokens (12 section 12.4),
-- verification_check_defs and verification_sources (04 sections 4.4.3, 4.4.4), industry_ref
-- and category_ref (01 section 1.14.1). Adding them later is additive: nothing here changes.
--
-- Conventions, from _CONTEXT.md section 2:
--   * TEXT ISO-8601 UTC timestamps, strftime('%Y-%m-%dT%H:%M:%SZ','now').
--   * CHECK (col IN (...)) on every enum column. The state machine lives in the database.
--   * TEXT primary keys with a type prefix, from radar/ids.py.
-- Forward-only. Never edit an applied migration; radar/db.py hashes the file and will say so.

-- ===========================================================================
-- 0. schema_version
-- ===========================================================================
-- One row per applied migration, not a single mutable integer. The difference matters the
-- first time a database is restored from a backup and somebody asks which migrations it had.
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    filename    TEXT NOT NULL,
    sha256      TEXT NOT NULL CHECK (length(sha256) = 64),
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    duration_ms INTEGER,
    applied_by  TEXT NOT NULL DEFAULT 'migrate'
);

-- ===========================================================================
-- 1. users
-- ===========================================================================
-- One operator today. The table exists anyway, because invariant 1 requires a send path that
-- takes an approval id, an approval needs a signer, and "Sagar" as a string constant is not a
-- signer.
CREATE TABLE users (
    id                   TEXT PRIMARY KEY,               -- usr_...
    email                TEXT NOT NULL,
    email_norm           TEXT NOT NULL,
    display_name         TEXT NOT NULL,

    password_hash        TEXT NOT NULL,                  -- argon2id PHC string
    password_algo        TEXT NOT NULL DEFAULT 'argon2id'
                           CHECK (password_algo IN ('argon2id','bcrypt')),
    password_set_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0,1)),

    role                 TEXT NOT NULL DEFAULT 'VIEWER'
                           CHECK (role IN ('OWNER','OPERATOR','VIEWER')),

    totp_secret          TEXT,
    totp_enrolled_at     TEXT,
    totp_last_used_step  INTEGER,

    failed_logins        INTEGER NOT NULL DEFAULT 0 CHECK (failed_logins >= 0),
    locked_until         TEXT,
    last_login_at        TEXT,
    last_login_ip        TEXT,

    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_by           TEXT REFERENCES users(id),
    disabled_at          TEXT,
    disabled_by          TEXT REFERENCES users(id),
    disabled_reason      TEXT,

    CHECK ((totp_secret IS NULL) = (totp_enrolled_at IS NULL)),
    CHECK ((disabled_at IS NULL) = (disabled_by IS NULL)),
    CHECK (email_norm = lower(email_norm))
);

CREATE UNIQUE INDEX ux_users_email ON users(email_norm);
CREATE INDEX ix_users_role ON users(role) WHERE disabled_at IS NULL;

-- ===========================================================================
-- 2. audit_actions + audit_log
-- ===========================================================================
-- The catalogue is a table, not a set of string literals at call sites: audit.audit() with an
-- unknown action fails on the foreign key rather than writing a row nobody can interpret.
CREATE TABLE audit_actions (
    action       TEXT PRIMARY KEY,
    domain       TEXT NOT NULL CHECK (domain IN (
                     'RESEARCH','VERIFICATION','SELECTION','MESSAGE','POLICY','APPROVAL',
                     'SEND','DELIVERY','RESPONSE','HANDOFF','SUPPRESSION','CONFIG',
                     'ACCESS','EXPORT','DATA','SYSTEM')),
    severity     TEXT NOT NULL CHECK (severity IN ('INFO','NOTICE','CRITICAL')),
    user_visible INTEGER NOT NULL DEFAULT 1 CHECK (user_visible IN (0,1)),
    pii_class    TEXT NOT NULL DEFAULT 'NONE'
                   CHECK (pii_class IN ('NONE','REFERENCE','HASHED','MASKED')),
    best_effort  INTEGER NOT NULL DEFAULT 0 CHECK (best_effort IN (0,1)),
    description  TEXT NOT NULL
);

CREATE TABLE audit_log (
    id            TEXT PRIMARY KEY,                      -- aud_...
    seq           INTEGER NOT NULL,                      -- 1-based, gapless, in-transaction
    at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    actor_kind    TEXT NOT NULL
                    CHECK (actor_kind IN ('HUMAN','SYSTEM','PROVIDER','ANONYMOUS')),
    actor_user_id TEXT REFERENCES users(id),
    actor_label   TEXT NOT NULL,             -- a row with no actor looks like evidence

    action        TEXT NOT NULL REFERENCES audit_actions(action),
    entity_table  TEXT NOT NULL,
    entity_id     TEXT,

    business_id   TEXT REFERENCES businesses(id),
    campaign_id   TEXT REFERENCES campaigns(id),
    message_id    TEXT REFERENCES outreach_messages(id),

    before_json   TEXT,
    after_json    TEXT,
    detail_json   TEXT NOT NULL DEFAULT '{}',

    request_id    TEXT,
    session_id    TEXT,
    route         TEXT,
    http_method   TEXT CHECK (http_method IS NULL OR
                    http_method IN ('GET','POST','PUT','PATCH','DELETE')),
    client_ip     TEXT,
    user_agent    TEXT,
    job_id        TEXT,
    job_run_id    TEXT,

    prev_hash     TEXT NOT NULL,
    row_hash      TEXT NOT NULL,
    hash_version  INTEGER NOT NULL DEFAULT 1,

    CHECK (seq >= 1),
    CHECK (length(prev_hash) = 64 AND length(row_hash) = 64),
    CHECK (lower(prev_hash) = prev_hash AND lower(row_hash) = row_hash),
    CHECK (actor_kind <> 'HUMAN' OR actor_user_id IS NOT NULL),
    CHECK (json_valid(detail_json)),
    CHECK (before_json IS NULL OR json_valid(before_json)),
    CHECK (after_json  IS NULL OR json_valid(after_json)),
    CHECK (at LIKE '____-__-__T__:__:__Z')
);

CREATE UNIQUE INDEX ux_audit_seq      ON audit_log(seq);
CREATE UNIQUE INDEX ux_audit_row_hash ON audit_log(row_hash);
CREATE INDEX ix_audit_at          ON audit_log(at);
CREATE INDEX ix_audit_action_at   ON audit_log(action, at);
CREATE INDEX ix_audit_entity      ON audit_log(entity_table, entity_id, at);
CREATE INDEX ix_audit_business_at ON audit_log(business_id, at) WHERE business_id IS NOT NULL;
CREATE INDEX ix_audit_campaign_at ON audit_log(campaign_id, at) WHERE campaign_id IS NOT NULL;
CREATE INDEX ix_audit_message_at  ON audit_log(message_id, at)  WHERE message_id IS NOT NULL;
CREATE INDEX ix_audit_actor_at    ON audit_log(actor_user_id, at);
CREATE INDEX ix_audit_request     ON audit_log(request_id) WHERE request_id IS NOT NULL;

-- ===========================================================================
-- 3. campaigns
-- ===========================================================================
CREATE TABLE campaigns (
    id                      TEXT PRIMARY KEY,            -- cmp_...
    name                    TEXT NOT NULL,
    slug                    TEXT NOT NULL,

    created_by              TEXT NOT NULL REFERENCES users(id),
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    industries              TEXT NOT NULL DEFAULT '[]',  -- JSON array; [] means no filter
    categories              TEXT NOT NULL DEFAULT '[]',
    size_filter             TEXT NOT NULL DEFAULT '[]',
    min_opportunity_score   INTEGER NOT NULL DEFAULT 0
                              CHECK (min_opportunity_score BETWEEN 0 AND 100),
    research_depth          TEXT NOT NULL DEFAULT 'STANDARD'
                              CHECK (research_depth IN ('STANDARD','DEEP')),
    max_businesses          INTEGER CHECK (max_businesses IS NULL OR max_businesses > 0),

    status                  TEXT NOT NULL DEFAULT 'DRAFT'
                              CHECK (status IN ('DRAFT','QUEUED','DISCOVERING','RESEARCHING',
                                                'REPORTING','COMPLETE','PAUSED','FAILED',
                                                'CANCELLED')),
    paused_reason           TEXT CHECK (paused_reason IS NULL OR paused_reason IN
                              ('QUOTA_CEILING','MANUAL','PROVIDER_ERROR','RATE_LIMIT')),
    started_at              TEXT,
    finished_at             TEXT,
    cancel_requested        INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),

    n_discovered            INTEGER NOT NULL DEFAULT 0 CHECK (n_discovered >= 0),
    n_researched            INTEGER NOT NULL DEFAULT 0 CHECK (n_researched >= 0),
    n_qualified             INTEGER NOT NULL DEFAULT 0 CHECK (n_qualified  >= 0),
    n_skipped               INTEGER NOT NULL DEFAULT 0 CHECK (n_skipped    >= 0),
    n_verified              INTEGER NOT NULL DEFAULT 0 CHECK (n_verified   >= 0),
    n_contacted             INTEGER NOT NULL DEFAULT 0 CHECK (n_contacted  >= 0),
    counters_reconciled_at  TEXT,

    discovery_provider      TEXT,
    research_model_id       TEXT,        -- pinned at start; two campaigns run against
    research_prompt_version TEXT,        -- different models are not comparable
    notes                   TEXT,

    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (json_valid(industries) AND json_valid(categories) AND json_valid(size_filter)),
    CHECK (status <> 'PAUSED' OR paused_reason IS NOT NULL),
    CHECK (finished_at IS NULL OR started_at IS NOT NULL),
    CHECK (created_at LIKE '____-__-__T__:__:__Z')
);

CREATE UNIQUE INDEX ux_campaigns_slug ON campaigns(slug);
CREATE INDEX ix_campaigns_status  ON campaigns(status, created_at DESC);
CREATE INDEX ix_campaigns_created ON campaigns(created_at DESC);
CREATE INDEX ix_campaigns_live    ON campaigns(id)
    WHERE status IN ('QUEUED','DISCOVERING','RESEARCHING','REPORTING','PAUSED');

CREATE TABLE campaign_cities (
    campaign_id  TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    city         TEXT NOT NULL,                          -- display form: 'Dhule'
    city_slug    TEXT NOT NULL,                          -- identity form: 'dhule'
    state_region TEXT NOT NULL DEFAULT 'Maharashtra',
    ordinal      INTEGER NOT NULL CHECK (ordinal >= 0),
    status       TEXT NOT NULL DEFAULT 'PENDING'
                   CHECK (status IN ('PENDING','DISCOVERING','COMPLETE','FAILED','SKIPPED')),
    n_discovered INTEGER NOT NULL DEFAULT 0 CHECK (n_discovered >= 0),
    error        TEXT,
    started_at   TEXT,
    finished_at  TEXT,
    PRIMARY KEY (campaign_id, city_slug)
);

CREATE INDEX ix_campaign_cities_order ON campaign_cities(campaign_id, ordinal);

-- ===========================================================================
-- 4. businesses
-- ===========================================================================
CREATE TABLE businesses (
    id                      TEXT PRIMARY KEY,            -- biz_...

    -- identity
    business_key            TEXT NOT NULL,
    name                    TEXT NOT NULL,
    name_norm               TEXT NOT NULL,
    legal_name              TEXT,
    aliases                 TEXT NOT NULL DEFAULT '[]',

    -- place
    city                    TEXT NOT NULL,
    city_slug               TEXT NOT NULL,
    state_region            TEXT NOT NULL DEFAULT 'Maharashtra',
    address                 TEXT,
    pincode                 TEXT CHECK (pincode IS NULL
                              OR pincode GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'),
    latitude                REAL CHECK (latitude  IS NULL OR latitude  BETWEEN -90  AND 90),
    longitude               REAL CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),

    -- classification
    industry                TEXT NOT NULL DEFAULT 'OTHER'
                              CHECK (industry IN ('HEALTHCARE','EDUCATION','AUTOMOBILE',
                                     'MANUFACTURING','RETAIL','HOSPITALITY','DISTRIBUTION',
                                     'REAL_ESTATE','PROFESSIONAL_SERVICES','OTHER')),
    category                TEXT NOT NULL DEFAULT 'OTHER'
                              CHECK (category IN ('HOSPITAL','DIAGNOSTIC_CENTER','SCHOOL',
                                     'COLLEGE','MANUFACTURER','DISTRIBUTOR','VEHICLE_DEALER',
                                     'GARAGE','HOTEL','RESTAURANT','BAKERY','RETAIL_STORE',
                                     'REAL_ESTATE_AGENCY','OTHER')),
    size_band               TEXT NOT NULL DEFAULT 'UNKNOWN'
                              CHECK (size_band IN ('MICRO','SMALL','MEDIUM','LARGE','UNKNOWN')),
    size_evidence           TEXT,

    -- web presence
    website                 TEXT,
    website_domain          TEXT,
    website_status          TEXT NOT NULL DEFAULT 'UNKNOWN'
                              CHECK (website_status IN ('PRESENT','ABSENT','UNKNOWN')),
    website_hash            TEXT,
    website_checked_at      TEXT,
    listing_url             TEXT,

    -- assessment: denormalised from the current opportunities row so the grid sorts and filters
    -- without a join. opportunities is the record; these are the copy.
    digital_maturity        INTEGER CHECK (digital_maturity IS NULL
                              OR digital_maturity BETWEEN 0 AND 100),
    operational_complexity  INTEGER CHECK (operational_complexity IS NULL
                              OR operational_complexity BETWEEN 0 AND 100),
    opportunity_score       INTEGER CHECK (opportunity_score IS NULL
                              OR opportunity_score BETWEEN 0 AND 100),
    opportunity_band        TEXT CHECK (opportunity_band IS NULL
                              OR opportunity_band IN ('HIGH','MEDIUM','LOW')),
    research_confidence     TEXT CHECK (research_confidence IS NULL
                              OR research_confidence IN ('HIGH','MEDIUM','LOW')),
    research_confidence_pct INTEGER CHECK (research_confidence_pct IS NULL
                              OR research_confidence_pct BETWEEN 0 AND 100),

    -- lifecycle, spec section 17
    status                  TEXT NOT NULL DEFAULT 'AI_RESEARCHED'
                              CHECK (status IN ('AI_RESEARCHED','NEEDS_VERIFICATION','VERIFIED',
                                     'REJECTED','SKIPPED','CONTACT_READY','CONTACTED',
                                     'RESPONDED','INTERESTED','HUMAN_HANDOFF')),
    status_actor_kind       TEXT NOT NULL DEFAULT 'SYSTEM'
                              CHECK (status_actor_kind IN ('HUMAN','SYSTEM')),
    status_actor_user_id    TEXT REFERENCES users(id),
    status_changed_at       TEXT,
    status_verification_id  TEXT REFERENCES verifications(id),
    contact_ready_at        TEXT,
    skip_reason             TEXT CHECK (skip_reason IS NULL OR skip_reason IN
                              ('BELOW_MIN_SCORE','SIZE_FILTER','CITY_FILTER','INDUSTRY_FILTER',
                               'RESEARCH_FAILED','MANUAL','PRIOR_PERMANENT_REJECTION')),

    -- research progress. Not the lifecycle.
    research_status         TEXT NOT NULL DEFAULT 'PENDING'
                              CHECK (research_status IN ('PENDING','RUNNING','COMPLETE','FAILED')),
    last_researched_at      TEXT,
    research_fingerprint    TEXT,
    contact_fingerprint     TEXT,

    -- outreach summary, denormalised for the frequency gates
    first_contacted_at      TEXT,
    last_contacted_at       TEXT,

    first_seen_campaign_id  TEXT NOT NULL REFERENCES campaigns(id),
    first_discovered_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- merge tombstone. The losing row is never deleted.
    merged_into_id          TEXT REFERENCES businesses(id),
    merged_at               TEXT,

    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (json_valid(aliases)),
    CHECK (size_evidence IS NULL OR json_valid(size_evidence)),
    CHECK (website_status <> 'PRESENT' OR website IS NOT NULL),
    CHECK (opportunity_band IS NULL OR opportunity_score IS NOT NULL),
    CHECK ((merged_into_id IS NULL) = (merged_at IS NULL)),
    CHECK (merged_into_id IS NULL OR merged_into_id <> id),
    CHECK (first_discovered_at LIKE '____-__-__T__:__:__Z')
);

CREATE UNIQUE INDEX ux_businesses_key ON businesses(business_key) WHERE merged_into_id IS NULL;
CREATE INDEX ix_businesses_status     ON businesses(status);
CREATE INDEX ix_businesses_geo        ON businesses(city_slug, industry, category);
CREATE INDEX ix_businesses_score      ON businesses(opportunity_score DESC)
    WHERE merged_into_id IS NULL;
CREATE INDEX ix_businesses_domain     ON businesses(website_domain)
    WHERE website_domain IS NOT NULL;
CREATE INDEX ix_businesses_name_norm  ON businesses(city_slug, name_norm);
CREATE INDEX ix_businesses_research   ON businesses(research_status, last_researched_at);
CREATE INDEX ix_businesses_merged     ON businesses(merged_into_id)
    WHERE merged_into_id IS NOT NULL;
CREATE INDEX ix_businesses_first_seen ON businesses(first_seen_campaign_id);

-- ===========================================================================
-- 5. campaign_businesses - the membership join
-- ===========================================================================
-- A business belongs to many campaigns. Excluded rows are kept, not skipped: an EXCLUDED row
-- costs one row and buys the report the sentence "excluded: you rejected this in June", which
-- is the difference between a report Sagar trusts and one where businesses vanish unexplained.
CREATE TABLE campaign_businesses (
    id                    TEXT PRIMARY KEY,              -- cbz_...
    campaign_id           TEXT NOT NULL REFERENCES campaigns(id)  ON DELETE CASCADE,
    business_id           TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,

    state                 TEXT NOT NULL DEFAULT 'INCLUDED'
                            CHECK (state IN ('INCLUDED','EXCLUDED')),
    exclusion_reason      TEXT CHECK (exclusion_reason IS NULL OR exclusion_reason IN
                            ('BELOW_MIN_SCORE','SIZE_FILTER','CITY_FILTER','INDUSTRY_FILTER',
                             'CATEGORY_FILTER','RESEARCH_FAILED','PRIOR_PERMANENT_REJECTION',
                             'PRIOR_REJECTION_COOLING_OFF','LIVE_SUPPRESSION','CAMPAIGN_CAP',
                             'MANUAL')),
    exclusion_detail      TEXT,

    first_seen_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    is_rediscovery        INTEGER NOT NULL DEFAULT 0 CHECK (is_rediscovery IN (0,1)),
    discovery_source      TEXT,
    discovery_source_id   TEXT REFERENCES sources(id),
    discovery_rank        INTEGER,

    -- what THIS campaign's report said, pinned so an archived report stays reproducible
    city_at_discovery     TEXT NOT NULL,
    industry_at_discovery TEXT NOT NULL,
    category_at_discovery TEXT NOT NULL,
    score_at_close        INTEGER CHECK (score_at_close IS NULL
                            OR score_at_close BETWEEN 0 AND 100),
    status_at_close       TEXT,
    closed_at             TEXT,

    research_run_id       TEXT REFERENCES research_runs(id),

    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (state <> 'EXCLUDED' OR exclusion_reason IS NOT NULL),
    CHECK (state <> 'INCLUDED' OR exclusion_reason IS NULL),
    CHECK (exclusion_detail IS NULL OR json_valid(exclusion_detail))
);

CREATE UNIQUE INDEX ux_cb_pair    ON campaign_businesses(campaign_id, business_id);
CREATE INDEX ix_cb_campaign_state ON campaign_businesses(campaign_id, state);
CREATE INDEX ix_cb_business       ON campaign_businesses(business_id, first_seen_at);
CREATE INDEX ix_cb_queue          ON campaign_businesses(campaign_id, business_id)
    WHERE state = 'INCLUDED';
CREATE INDEX ix_cb_campaign_city  ON campaign_businesses(campaign_id, city_at_discovery,
                                                         industry_at_discovery);

-- ===========================================================================
-- 6. research: runs, findings, sources, finding_sources
-- ===========================================================================
CREATE TABLE research_runs (
    id                  TEXT PRIMARY KEY,                -- res_...
    business_id         TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    campaign_id         TEXT REFERENCES campaigns(id),

    depth               TEXT NOT NULL DEFAULT 'STANDARD' CHECK (depth IN ('STANDARD','DEEP')),
    status              TEXT NOT NULL DEFAULT 'PENDING'
                          CHECK (status IN ('PENDING','RUNNING','COMPLETE','FAILED','CANCELLED')),
    reason              TEXT NOT NULL DEFAULT 'CAMPAIGN'
                          CHECK (reason IN ('CAMPAIGN','STALE','MANUAL','RECHECK')),

    -- LLM provenance. Never call a model without recording these.
    model_id            TEXT,
    prompt_version      TEXT,
    input_tokens        INTEGER CHECK (input_tokens  IS NULL OR input_tokens  >= 0),
    output_tokens       INTEGER CHECK (output_tokens IS NULL OR output_tokens >= 0),
    -- Requests, not rupees. On the free tier the scarce resource is the call.
    quota_requests      INTEGER NOT NULL DEFAULT 0 CHECK (quota_requests >= 0),

    n_findings          INTEGER NOT NULL DEFAULT 0 CHECK (n_findings          >= 0),
    n_findings_observed INTEGER NOT NULL DEFAULT 0 CHECK (n_findings_observed >= 0),
    n_findings_inferred INTEGER NOT NULL DEFAULT 0 CHECK (n_findings_inferred >= 0),
    n_findings_unknown  INTEGER NOT NULL DEFAULT 0 CHECK (n_findings_unknown  >= 0),
    n_sources           INTEGER NOT NULL DEFAULT 0 CHECK (n_sources           >= 0),

    capture_path        TEXT,
    capture_sha256      TEXT CHECK (capture_sha256 IS NULL OR length(capture_sha256) = 64),

    fingerprint         TEXT,
    error               TEXT,
    job_run_id          TEXT,

    started_at          TEXT,
    finished_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (status <> 'COMPLETE' OR (finished_at IS NOT NULL AND model_id IS NOT NULL
                                    AND prompt_version IS NOT NULL)),
    CHECK (status <> 'FAILED'   OR error IS NOT NULL),
    CHECK (finished_at IS NULL OR started_at IS NOT NULL)
);

CREATE INDEX ix_research_runs_business ON research_runs(business_id, status, finished_at);
CREATE INDEX ix_research_runs_current  ON research_runs(business_id, finished_at DESC)
    WHERE status = 'COMPLETE';
CREATE INDEX ix_research_runs_campaign ON research_runs(campaign_id, status);
CREATE INDEX ix_research_runs_quota    ON research_runs(finished_at) WHERE quota_requests > 0;

-- Invariant 4, schema half. OBSERVED may be stated, INFERRED must be hedged, UNKNOWN must
-- never appear in a message. The kind CHECK is what makes the policy engine's job decidable.
CREATE TABLE research_findings (
    id              TEXT PRIMARY KEY,                    -- fnd_...
    business_id     TEXT NOT NULL REFERENCES businesses(id)    ON DELETE CASCADE,
    research_run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,

    kind            TEXT NOT NULL CHECK (kind IN ('OBSERVED','INFERRED','UNKNOWN')),

    dimension       TEXT NOT NULL
                      CHECK (dimension IN ('IDENTITY','SCALE','OPERATIONS','DIGITAL_PRESENCE',
                                           'SYSTEMS','STAFFING','CUSTOMERS','FINANCE',
                                           'COMPLIANCE','OTHER')),
    label           TEXT NOT NULL CHECK (length(label) BETWEEN 3 AND 80),
    statement       TEXT NOT NULL CHECK (length(statement) BETWEEN 10 AND 600),
    detail          TEXT,

    confidence      TEXT NOT NULL DEFAULT 'MEDIUM'
                      CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct  INTEGER CHECK (confidence_pct IS NULL OR confidence_pct BETWEEN 0 AND 100),
    weight          REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0),

    derived_from    TEXT NOT NULL DEFAULT '[]',          -- JSON array of research_findings.id
    inference_note  TEXT,

    unknown_reason  TEXT CHECK (unknown_reason IS NULL OR unknown_reason IN
                      ('NOT_PUBLISHED','SOURCE_UNREACHABLE','AMBIGUOUS','OUT_OF_SCOPE',
                       'CONFLICTING_SOURCES')),

    is_current      INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
    ordinal         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (json_valid(derived_from)),
    -- An INFERRED finding that names no antecedent is an assertion wearing a hedge.
    CHECK (kind <> 'INFERRED' OR (json_array_length(derived_from) >= 1
                                  AND inference_note IS NOT NULL)),
    -- An UNKNOWN finding must say why it is unknown, or the third category is a shrug.
    CHECK (kind <> 'UNKNOWN'  OR unknown_reason IS NOT NULL),
    -- An UNKNOWN finding may never carry a confidence above LOW: we do not know it.
    CHECK (kind <> 'UNKNOWN'  OR confidence = 'LOW')
);

CREATE INDEX ix_findings_business_run ON research_findings(business_id, research_run_id, kind);
CREATE INDEX ix_findings_run_kind     ON research_findings(research_run_id, kind, ordinal);
CREATE INDEX ix_findings_current      ON research_findings(business_id, kind)
    WHERE is_current = 1;

CREATE TABLE sources (
    id                   TEXT PRIMARY KEY,               -- src_...
    business_id          TEXT REFERENCES businesses(id) ON DELETE CASCADE,

    name                 TEXT NOT NULL,
    url                  TEXT NOT NULL,
    source_type          TEXT NOT NULL
                           CHECK (source_type IN ('SITE','LISTING','DIRECTORY','NEWS','SOCIAL',
                                                  'REGISTRY','MAP','REVIEW','DOCUMENT','OTHER')),
    checked_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    information_obtained TEXT NOT NULL,
    confidence           TEXT NOT NULL DEFAULT 'MEDIUM'
                           CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct       INTEGER CHECK (confidence_pct IS NULL
                           OR confidence_pct BETWEEN 0 AND 100),

    url_norm             TEXT NOT NULL,
    domain               TEXT,
    http_status          INTEGER CHECK (http_status IS NULL OR http_status BETWEEN 100 AND 599),
    content_sha256       TEXT CHECK (content_sha256 IS NULL OR length(content_sha256) = 64),
    snapshot_path        TEXT,
    robots_allowed       INTEGER CHECK (robots_allowed IS NULL OR robots_allowed IN (0,1)),
    title                TEXT,
    publisher            TEXT,
    published_at         TEXT,

    research_run_id      TEXT REFERENCES research_runs(id),
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (url LIKE 'http://%' OR url LIKE 'https://%'),
    CHECK (checked_at LIKE '____-__-__T__:__:__Z')
);

CREATE UNIQUE INDEX ux_sources_business_url ON sources(business_id, url_norm);
CREATE INDEX ix_sources_business ON sources(business_id, checked_at DESC);
CREATE INDEX ix_sources_run      ON sources(research_run_id);
CREATE INDEX ix_sources_domain   ON sources(domain);
CREATE INDEX ix_sources_stale    ON sources(checked_at);

-- ON DELETE RESTRICT on source_id is deliberate. Deleting a source that a finding cites would
-- leave a finding a message may quote with nothing behind it; the delete must fail loudly.
CREATE TABLE finding_sources (
    finding_id TEXT NOT NULL REFERENCES research_findings(id) ON DELETE CASCADE,
    source_id  TEXT NOT NULL REFERENCES sources(id)           ON DELETE RESTRICT,
    excerpt    TEXT,                          -- the sentence on the page that supports it
    locator    TEXT,
    checked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (finding_id, source_id)
);

CREATE INDEX ix_finding_sources_source ON finding_sources(source_id);

-- ===========================================================================
-- 7. business_contacts
-- ===========================================================================
-- No value in this table is ever sent to the LLM (_CONTEXT.md section 2, consequence 1). The
-- address is substituted into a rendered message locally, after generation.
CREATE TABLE business_contacts (
    id                         TEXT PRIMARY KEY,         -- cnt_...
    business_id                TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,

    kind                       TEXT NOT NULL
                                 CHECK (kind IN ('EMAIL','PHONE','WHATSAPP','WEB_FORM',
                                                 'ADDRESS','OTHER')),

    value_raw                  TEXT NOT NULL,
    value_norm                 TEXT NOT NULL,            -- identity
    value_dedupe               TEXT NOT NULL,            -- looser comparison for gate F2
    value_display              TEXT NOT NULL,
    domain                     TEXT,
    valid                      INTEGER NOT NULL DEFAULT 1 CHECK (valid IN (0,1)),
    invalid_reason             TEXT,

    phone_e164                 TEXT,
    phone_number_type          TEXT CHECK (phone_number_type IS NULL OR phone_number_type IN
                                 ('MOBILE','FIXED_LINE','FIXED_LINE_OR_MOBILE','TOLL_FREE',
                                  'PREMIUM_RATE','VOIP','UNKNOWN','INVALID')),
    phone_norm_version         TEXT,
    wa_capability              TEXT NOT NULL DEFAULT 'UNKNOWN'
                                 CHECK (wa_capability IN ('CONFIRMED','LIKELY','UNKNOWN',
                                                          'UNLIKELY','NOT_ON_WHATSAPP')),
    wa_capability_source       TEXT CHECK (wa_capability_source IS NULL
                                 OR wa_capability_source IN ('NUMBER_TYPE','INBOUND_MESSAGE',
                                    'API_ERROR_131026','OPERATOR','LISTING_WA_BUTTON')),
    wa_id                      TEXT,
    whatsapp_capable           INTEGER NOT NULL DEFAULT 0 CHECK (whatsapp_capable IN (0,1)),

    -- Consent is never written from research output, only from a human action.
    whatsapp_optin_at          TEXT,
    whatsapp_optin_source      TEXT CHECK (whatsapp_optin_source IS NULL
                                 OR whatsapp_optin_source IN ('INBOUND_MESSAGE','WEB_FORM',
                                    'WRITTEN_NOTE','OPERATOR_ATTESTED')),
    whatsapp_optin_evidence    TEXT,

    -- DPDP: is_named_individual is the flag that turns a business record into personal data.
    is_public_business_contact INTEGER NOT NULL DEFAULT 1
                                 CHECK (is_public_business_contact IN (0,1)),
    is_named_individual        INTEGER NOT NULL DEFAULT 0
                                 CHECK (is_named_individual IN (0,1)),
    person_name                TEXT,
    person_role                TEXT,
    is_role_address            INTEGER NOT NULL DEFAULT 0 CHECK (is_role_address IN (0,1)),

    source_id                  TEXT REFERENCES sources(id),
    source_ref                 TEXT,
    source_url                 TEXT,
    source_note                TEXT,
    discovered_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    captured_at                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    confidence                 TEXT NOT NULL DEFAULT 'MEDIUM'
                                 CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct             INTEGER CHECK (confidence_pct IS NULL
                                 OR confidence_pct BETWEEN 0 AND 100),
    human_verified             INTEGER NOT NULL DEFAULT 0 CHECK (human_verified IN (0,1)),
    human_verified_at          TEXT,
    human_verified_by          TEXT REFERENCES users(id),

    is_active                  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    deactivated_at             TEXT,
    deactivated_reason         TEXT CHECK (deactivated_reason IS NULL OR deactivated_reason IN
                                 ('BOUNCED','SUPERSEDED','OPERATOR','INVALID','ERASURE','MERGED')),
    is_primary                 INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),

    retention_class            TEXT NOT NULL DEFAULT 'P2Y'
                                 CHECK (retention_class IN ('P180D','P2Y','P7Y')),
    erased_at                  TEXT,

    created_at                 TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at                 TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (whatsapp_optin_evidence IS NULL OR json_valid(whatsapp_optin_evidence)),
    CHECK (kind <> 'EMAIL' OR domain IS NOT NULL),
    CHECK (kind NOT IN ('PHONE','WHATSAPP') OR phone_e164 IS NOT NULL OR valid = 0),
    CHECK (is_named_individual = 0 OR person_name IS NOT NULL),
    CHECK (human_verified = 0 OR (human_verified_at IS NOT NULL
                                  AND human_verified_by IS NOT NULL)),
    CHECK (is_active = 1 OR deactivated_at IS NOT NULL),
    CHECK ((whatsapp_optin_at IS NULL) = (whatsapp_optin_source IS NULL)),
    CHECK (valid = 1 OR is_active = 0)
);

CREATE UNIQUE INDEX ux_contacts_business_value
    ON business_contacts(business_id, kind, value_norm);
-- The hottest contact query in the system: it decides CONTACT_READY.
CREATE INDEX ix_contacts_business_live ON business_contacts(business_id, kind)
    WHERE is_active = 1 AND human_verified = 1;
CREATE INDEX ix_contacts_business_any  ON business_contacts(business_id, kind)
    WHERE is_active = 1;
CREATE INDEX ix_contacts_value_norm    ON business_contacts(kind, value_norm);
CREATE INDEX ix_contacts_value_dedupe  ON business_contacts(kind, value_dedupe);
CREATE INDEX ix_contacts_domain        ON business_contacts(domain) WHERE domain IS NOT NULL;
CREATE INDEX ix_contacts_phone         ON business_contacts(phone_e164)
    WHERE phone_e164 IS NOT NULL;
CREATE INDEX ix_contacts_person        ON business_contacts(business_id)
    WHERE is_named_individual = 1;

-- ===========================================================================
-- 8. opportunities
-- ===========================================================================
CREATE TABLE opportunities (
    id                     TEXT PRIMARY KEY,             -- opp_...
    business_id            TEXT NOT NULL REFERENCES businesses(id)    ON DELETE CASCADE,
    research_run_id        TEXT REFERENCES research_runs(id),
    campaign_id            TEXT REFERENCES campaigns(id),

    potential_problem      TEXT NOT NULL,
    potential_solution     TEXT NOT NULL,
    expected_benefit       TEXT NOT NULL,
    score                  INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    band                   TEXT NOT NULL CHECK (band IN ('HIGH','MEDIUM','LOW')),
    confidence             TEXT NOT NULL DEFAULT 'MEDIUM'
                             CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct         INTEGER CHECK (confidence_pct IS NULL
                             OR confidence_pct BETWEEN 0 AND 100),

    digital_maturity       INTEGER CHECK (digital_maturity IS NULL
                             OR digital_maturity BETWEEN 0 AND 100),
    operational_complexity INTEGER CHECK (operational_complexity IS NULL
                             OR operational_complexity BETWEEN 0 AND 100),

    score_breakdown        TEXT NOT NULL DEFAULT '{}',
    -- Nullable on purpose: the comparison sums only priced rows and renders an em dash when
    -- nothing is priced. Invariant 5 - no placeholder numbers.
    est_value_inr          INTEGER CHECK (est_value_inr IS NULL OR est_value_inr >= 0),
    est_value_basis        TEXT,

    model_id               TEXT,
    prompt_version         TEXT,
    computed_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    is_current             INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
    superseded_by          TEXT REFERENCES opportunities(id),

    CHECK (json_valid(score_breakdown)),
    -- The score bands, enforced rather than trusted to the scorer. "HIGH" next to 62 in a
    -- report Sagar shows somebody is worth three lines of CHECK.
    CHECK ((band = 'HIGH'   AND score >= 80)
        OR (band = 'MEDIUM' AND score BETWEEN 60 AND 79)
        OR (band = 'LOW'    AND score < 60))
);

-- At most one current opportunity per business. A second would make every KPI double-count.
CREATE UNIQUE INDEX ux_opportunities_current ON opportunities(business_id) WHERE is_current = 1;
CREATE INDEX ix_opportunities_current  ON opportunities(business_id) WHERE is_current = 1;
CREATE INDEX ix_opportunities_score    ON opportunities(score DESC)  WHERE is_current = 1;
CREATE INDEX ix_opportunities_history  ON opportunities(business_id, computed_at DESC);
CREATE INDEX ix_opportunities_campaign ON opportunities(campaign_id, is_current);

CREATE TABLE opportunity_modules (
    id             TEXT PRIMARY KEY,                     -- opp_... like its parent
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    business_id    TEXT NOT NULL REFERENCES businesses(id)    ON DELETE CASCADE,
    module         TEXT NOT NULL
                     CHECK (module IN ('DASHBOARD','WORKFLOW','FINANCE','INVENTORY','REPORTS',
                                       'ROLE_MANAGEMENT','AUDIT_LOGS','PATIENTS','APPOINTMENTS',
                                       'DEPARTMENTS','BILLING','STUDENTS','FEES','ATTENDANCE',
                                       'STAFF','TRANSPORT','ADMISSIONS','EXAMINATIONS',
                                       'PRODUCTION','PURCHASING','SALES','QUALITY','ORDERS',
                                       'CUSTOMERS','RECEIVABLES','DELIVERY','PAYMENTS',
                                       'VARIANTS','PROFITABILITY','EXPENSES','PROFIT')),
    ordinal        INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    rationale      TEXT,
    is_current     INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),

    UNIQUE (opportunity_id, module)   -- stops "Inventory" appearing twice in one recommendation
);

CREATE INDEX ix_modules_business ON opportunity_modules(business_id, ordinal)
    WHERE is_current = 1;
CREATE INDEX ix_modules_module   ON opportunity_modules(module);

-- ===========================================================================
-- 9. verification
-- ===========================================================================
CREATE TABLE verification_reason_codes (
    code               TEXT PRIMARY KEY,
    label              TEXT NOT NULL,
    guidance           TEXT NOT NULL,
    is_permanent       INTEGER NOT NULL CHECK (is_permanent IN (0,1)),
    cool_off_days      INTEGER NOT NULL CHECK (cool_off_days >= 0),
    writes_suppression INTEGER NOT NULL CHECK (writes_suppression IN (0,1)),
    suppression_reason TEXT CHECK (suppression_reason IS NULL OR suppression_reason IN
                         ('UNSUBSCRIBE_LINK','REPLY_OPT_OUT','COMPLAINT','BOUNCE_HARD',
                          'MANUAL','DNC_LIST','LEGAL_REQUEST')),
    bulk_ok            INTEGER NOT NULL CHECK (bulk_ok IN (0,1)),
    requires_note      INTEGER NOT NULL DEFAULT 0 CHECK (requires_note IN (0,1)),
    ordinal            INTEGER NOT NULL,

    -- A permanent rejection always writes the suppression that makes it permanent. Without
    -- this the two halves of "permanent" drift apart and permanent becomes a label.
    CHECK (is_permanent = 0 OR writes_suppression = 1),
    CHECK (writes_suppression = 0 OR suppression_reason IS NOT NULL),
    -- Nothing that writes a suppression may be applied in bulk. This one CHECK is the whole of
    -- the "never bulk-appliable" rule, enforced where it cannot be forgotten.
    CHECK (bulk_ok = 0 OR writes_suppression = 0),
    CHECK (is_permanent = 0 OR cool_off_days = 0)   -- permanent has no cool-off; it has no exit
);

CREATE INDEX ix_reason_codes_bulk ON verification_reason_codes(bulk_ok, ordinal);

CREATE TABLE verifications (
    id                    TEXT PRIMARY KEY,              -- ver_...
    business_id           TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    campaign_id           TEXT REFERENCES campaigns(id),

    state                 TEXT NOT NULL DEFAULT 'DRAFT'
                            CHECK (state IN ('DRAFT','SUBMITTED','ABANDONED')),
    mode                  TEXT NOT NULL DEFAULT 'FULL'
                            CHECK (mode IN ('FULL','QUICK_REJECT','RECHECK')),
    verdict               TEXT CHECK (verdict IS NULL
                            OR verdict IN ('VERIFIED','REJECTED','SKIPPED')),

    checks_total          INTEGER NOT NULL DEFAULT 9 CHECK (checks_total = 9),
    checks_passed         INTEGER NOT NULL DEFAULT 0 CHECK (checks_passed BETWEEN 0 AND 9),
    checks_failed         INTEGER NOT NULL DEFAULT 0 CHECK (checks_failed BETWEEN 0 AND 9),

    reason_code           TEXT REFERENCES verification_reason_codes(code),
    reason_note           TEXT,

    -- anti-rubber-stamp evidence
    why_note              TEXT,
    dwell_ms              INTEGER CHECK (dwell_ms IS NULL OR dwell_ms >= 0),
    dwell_required_ms     INTEGER NOT NULL DEFAULT 20000,
    sources_visited       TEXT NOT NULL DEFAULT '[]',    -- JSON array of sources.id opened
    sources_waived        TEXT NOT NULL DEFAULT '[]',

    trigger_reason        TEXT CHECK (trigger_reason IS NULL OR trigger_reason IN
                            ('INITIAL','STALE','WEBSITE_CHANGED','CONTACT_CHANGED',
                             'RESEARCH_CHANGED','MANUAL','REOPENED')),
    recheck_scope         TEXT,
    prior_verification_id TEXT REFERENCES verifications(id),

    superseded_at         TEXT,
    superseded_by         TEXT REFERENCES verifications(id),
    superseded_reason     TEXT CHECK (superseded_reason IS NULL OR superseded_reason IN
                            ('REVERIFY','MANUAL','PARKED','REOPENED','REJECTED','STALE')),

    research_run_id       TEXT REFERENCES research_runs(id),
    research_fingerprint  TEXT,
    contact_fingerprint   TEXT,

    verified_by           TEXT REFERENCES users(id),
    verified_at           TEXT,
    note                  TEXT,
    session_id            TEXT,
    started_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (json_valid(sources_visited) AND json_valid(sources_waived)),
    CHECK (recheck_scope IS NULL OR json_valid(recheck_scope)),
    CHECK (state <> 'SUBMITTED' OR (verdict IS NOT NULL AND verified_by IS NOT NULL
                                    AND verified_at IS NOT NULL)),
    -- Invariant V1 at the row level: a VERIFIED verdict needs all nine checks, a signature, a
    -- dwell time and a note. No system actor can produce one, because verified_by is a user.
    -- Two layers, deliberately: the trigger below stops the status being written, this CHECK
    -- stops the evidence being fabricated.
    CHECK (verdict <> 'VERIFIED' OR (checks_passed = 9 AND checks_failed = 0
                                     AND why_note IS NOT NULL AND length(why_note) >= 15
                                     AND dwell_ms IS NOT NULL AND dwell_ms >= dwell_required_ms)),
    CHECK (verdict <> 'REJECTED' OR reason_code IS NOT NULL),
    CHECK (checks_passed + checks_failed <= checks_total),
    CHECK ((superseded_at IS NULL) = (superseded_reason IS NULL))
);

-- At most one live submitted verification per business. Two would make "is this business
-- verified" ambiguous at the exact moment it decides whether a message may be sent.
CREATE UNIQUE INDEX ux_verifications_live ON verifications(business_id)
    WHERE state = 'SUBMITTED' AND superseded_at IS NULL;
CREATE UNIQUE INDEX ux_verifications_draft ON verifications(business_id) WHERE state = 'DRAFT';
CREATE INDEX ix_verifications_business ON verifications(business_id, created_at DESC);
CREATE INDEX ix_verifications_verdict  ON verifications(verdict, verified_at)
    WHERE superseded_at IS NULL;
CREATE INDEX ix_verifications_user     ON verifications(verified_by, verified_at);
CREATE INDEX ix_verifications_stale    ON verifications(verified_at)
    WHERE verdict = 'VERIFIED' AND superseded_at IS NULL;

CREATE TABLE verification_checks (
    id              TEXT PRIMARY KEY,                    -- chk_...
    verification_id TEXT NOT NULL REFERENCES verifications(id) ON DELETE CASCADE,
    business_id     TEXT NOT NULL REFERENCES businesses(id)    ON DELETE CASCADE,

    check_key       TEXT NOT NULL
                      CHECK (check_key IN ('IDENTITY_CORRECT','IN_TARGET_CITY','CATEGORY_CORRECT',
                                           'APPEARS_OPERATIONAL','CONTACT_LEGITIMATE',
                                           'RESEARCH_RELEVANT','OPPORTUNITY_REASONABLE',
                                           'OUTREACH_APPROPRIATE','NO_DNC_RECORD')),
    ordinal         INTEGER NOT NULL CHECK (ordinal BETWEEN 1 AND 9),
    passed          INTEGER CHECK (passed IS NULL OR passed IN (0,1)),  -- NULL = not yet answered
    note            TEXT,
    evidence_ref    TEXT,                                -- sources.id or a URL the operator opened
    answered_at     TEXT,
    answered_by     TEXT REFERENCES users(id),

    UNIQUE (verification_id, check_key),
    CHECK ((passed IS NULL) = (answered_at IS NULL)),
    CHECK (passed IS NULL OR answered_by IS NOT NULL),
    -- A failed check must say why. "No" without a reason is the same as no answer.
    CHECK (passed <> 0 OR (note IS NOT NULL AND length(note) >= 10))
);

CREATE INDEX ix_checks_verification ON verification_checks(verification_id, ordinal);
CREATE INDEX ix_checks_business     ON verification_checks(business_id, check_key, answered_at);
CREATE INDEX ix_checks_failed       ON verification_checks(check_key) WHERE passed = 0;

-- ===========================================================================
-- 10. contact_policy
-- ===========================================================================
CREATE TABLE contact_policy (
    id                        TEXT PRIMARY KEY,          -- 'GLOBAL' or a cmp_... id
    scope                     TEXT NOT NULL CHECK (scope IN ('GLOBAL','CAMPAIGN')),
    campaign_id               TEXT REFERENCES campaigns(id) ON DELETE CASCADE,

    automation_mode           TEXT NOT NULL DEFAULT 'HUMAN_APPROVAL'
                                CHECK (automation_mode IN ('MANUAL','HUMAN_APPROVAL',
                                                           'SEMI_AUTOMATED','FULLY_AUTOMATED')),

    min_days_between_outreach INTEGER NOT NULL DEFAULT 21
                                CHECK (min_days_between_outreach >= 0),
    max_attempts              INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
    max_followups             INTEGER NOT NULL DEFAULT 2 CHECK (max_followups >= 0),
    stop_after_rejection      INTEGER NOT NULL DEFAULT 1 CHECK (stop_after_rejection IN (0,1)),
    stop_after_opt_out        INTEGER NOT NULL DEFAULT 1 CHECK (stop_after_opt_out IN (0,1)),

    recent_campaign_days      INTEGER NOT NULL DEFAULT 90 CHECK (recent_campaign_days >= 0),
    same_domain_days          INTEGER NOT NULL DEFAULT 30 CHECK (same_domain_days >= 0),
    same_domain_max           INTEGER NOT NULL DEFAULT 1  CHECK (same_domain_max >= 1),

    verification_valid_days   INTEGER NOT NULL DEFAULT 30 CHECK (verification_valid_days >= 1),

    approval_ttl_minutes      INTEGER NOT NULL DEFAULT 60 CHECK (approval_ttl_minutes >= 1),
    send_min_gap_seconds      INTEGER NOT NULL DEFAULT 45 CHECK (send_min_gap_seconds >= 0),

    -- Sending-account protection. One free Gmail account, no custom domain.
    daily_send_cap            INTEGER NOT NULL DEFAULT 25 CHECK (daily_send_cap >= 0),
    warmup_started_on         TEXT,
    warmup_schedule           TEXT NOT NULL DEFAULT '[5,5,10,10,15,15,20,20,25]',
    bounce_rate_window_days   INTEGER NOT NULL DEFAULT 30,
    bounce_rate_max_pct       REAL    NOT NULL DEFAULT 5.0,
    complaint_rate_max_pct    REAL    NOT NULL DEFAULT 0.1,
    bounce_rate_min_sample    INTEGER NOT NULL DEFAULT 20,

    email_enabled             INTEGER NOT NULL DEFAULT 1 CHECK (email_enabled IN (0,1)),
    -- NULL on a fresh database: the deliberate on-switch, so a freshly migrated install cannot
    -- mail anybody by accident. Set it to 'gmail.com' when the account is configured.
    email_sending_domain      TEXT,
    whatsapp_enabled          INTEGER NOT NULL DEFAULT 1 CHECK (whatsapp_enabled IN (0,1)),
    whatsapp_api_enabled      INTEGER NOT NULL DEFAULT 0 CHECK (whatsapp_api_enabled IN (0,1)),
    phone_enabled             INTEGER NOT NULL DEFAULT 1 CHECK (phone_enabled IN (0,1)),
    manual_enabled            INTEGER NOT NULL DEFAULT 1 CHECK (manual_enabled IN (0,1)),

    policy_version            TEXT NOT NULL DEFAULT 'cp-1',
    updated_at                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_by                TEXT REFERENCES users(id),

    CHECK (json_valid(warmup_schedule)),
    CHECK ((scope = 'GLOBAL'   AND campaign_id IS NULL)
        OR (scope = 'CAMPAIGN' AND campaign_id IS NOT NULL))
);

CREATE UNIQUE INDEX ux_contact_policy_campaign
    ON contact_policy(campaign_id) WHERE campaign_id IS NOT NULL;

-- ===========================================================================
-- 11. suppressions
-- ===========================================================================
-- Invariant 3. An opt-out on any contact point blocks every channel for that business, forever,
-- and the application has no code that can clear it.
CREATE TABLE suppressions (
    id                TEXT PRIMARY KEY,                  -- sup_...
    scope             TEXT NOT NULL
                        CHECK (scope IN ('BUSINESS','EMAIL','PHONE','WHATSAPP','DOMAIN')),
    value_norm        TEXT NOT NULL,
    -- SIMPLIFIED: 11-audit-architecture.md section 11.12.3 makes value_hmac the identity and
    -- value_norm a label, so a DPDP erasure that blanks value_norm cannot resurrect a
    -- suppressed address. The column and its unique index are here; the NOT NULL trigger and
    -- the pepper management that go with it are not, because they need a key-storage decision
    -- this foundation does not own. Until then value_norm is the lookup key.
    value_hmac        TEXT,
    business_id       TEXT REFERENCES businesses(id),    -- NULL: a domain block spans businesses
    reason            TEXT NOT NULL
                        CHECK (reason IN ('UNSUBSCRIBE_LINK','REPLY_OPT_OUT','COMPLAINT',
                                          'BOUNCE_HARD','MANUAL','DNC_LIST','LEGAL_REQUEST')),
    source            TEXT NOT NULL,                     -- human-readable provenance
    source_ref        TEXT,                              -- rsp_/msg_/aud_ id where applicable
    detail            TEXT,                              -- JSON: verbatim evidence
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_by        TEXT REFERENCES users(id),         -- NULL when the inbox poller wrote it

    released_at       TEXT,                              -- NULL forever, in the application
    released_by       TEXT REFERENCES users(id),
    released_audit_id TEXT REFERENCES audit_log(id),
    erased_at         TEXT,

    CHECK (detail IS NULL OR json_valid(detail))
);

CREATE UNIQUE INDEX ux_suppressions_scope_value ON suppressions(scope, value_norm);
CREATE INDEX ix_suppressions_business ON suppressions(business_id);
CREATE INDEX ix_suppressions_live     ON suppressions(scope, value_norm)
    WHERE released_at IS NULL;
CREATE UNIQUE INDEX ux_suppressions_scope_hmac
    ON suppressions(scope, value_hmac) WHERE value_hmac IS NOT NULL;

-- ===========================================================================
-- 12. selections
-- ===========================================================================
CREATE TABLE selections (
    id                   TEXT PRIMARY KEY,               -- sel_...
    campaign_id          TEXT NOT NULL REFERENCES campaigns(id)  ON DELETE CASCADE,
    business_id          TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    city                 TEXT NOT NULL,                  -- copied at select time
    industry             TEXT NOT NULL,                  -- copied, so counts survive a reclassify
    state                TEXT NOT NULL DEFAULT 'SELECTED'
                           CHECK (state IN ('SELECTED','PREPARED','DISPATCHED','BLOCKED',
                                            'REMOVED')),
    intent_channel       TEXT CHECK (intent_channel IS NULL
                           OR intent_channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),
    sequence_no          INTEGER NOT NULL DEFAULT 1 CHECK (sequence_no >= 1),
    parent_message_id    TEXT REFERENCES outreach_messages(id),
    eligibility_snapshot TEXT NOT NULL DEFAULT '{}',     -- JSON Eligibility at SELECT stage
    eligible_at_select   INTEGER NOT NULL CHECK (eligible_at_select IN (0,1)),
    blocking_gate        TEXT,
    note                 TEXT,
    selected_by          TEXT NOT NULL REFERENCES users(id),
    selected_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    removed_by           TEXT REFERENCES users(id),
    removed_at           TEXT,
    updated_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (json_valid(eligibility_snapshot))
);

-- One live selection per business per campaign. A removed selection is kept for the audit trail.
CREATE UNIQUE INDEX ux_selections_live
    ON selections(campaign_id, business_id) WHERE state <> 'REMOVED';
CREATE INDEX ix_selections_campaign_city ON selections(campaign_id, city, state);
CREATE INDEX ix_selections_business      ON selections(business_id);

-- ===========================================================================
-- 13. outreach: drafts, messages, approvals, events
-- ===========================================================================
CREATE TABLE outreach_drafts (
    id                TEXT PRIMARY KEY,                  -- out_...
    business_id       TEXT NOT NULL REFERENCES businesses(id),
    campaign_id       TEXT NOT NULL REFERENCES campaigns(id),
    selection_id      TEXT REFERENCES selections(id),
    contact_id        TEXT REFERENCES business_contacts(id),
    channel           TEXT NOT NULL
                        CHECK (channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),
    sequence_no       INTEGER NOT NULL DEFAULT 1 CHECK (sequence_no >= 1),
    parent_message_id TEXT REFERENCES outreach_messages(id),

    subject           TEXT,                              -- NULL for WHATSAPP/PHONE
    body              TEXT NOT NULL,                     -- as generated
    body_edited       TEXT,                              -- as edited by Sagar, NULL if untouched
    edited_by         TEXT REFERENCES users(id),
    edited_at         TEXT,
    edit_count        INTEGER NOT NULL DEFAULT 0,

    -- AI message audit. Never call a model without recording these.
    model_id          TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    input_tokens      INTEGER,
    output_tokens     INTEGER,
    facts_used        TEXT NOT NULL DEFAULT '[]',        -- JSON array of OBSERVED finding ids
    inferences_used   TEXT NOT NULL DEFAULT '[]',        -- JSON array of INFERRED finding ids
    ai_confidence     TEXT CHECK (ai_confidence IS NULL
                        OR ai_confidence IN ('HIGH','MEDIUM','LOW')),
    ai_confidence_pct INTEGER CHECK (ai_confidence_pct IS NULL
                        OR ai_confidence_pct BETWEEN 0 AND 100),

    policy_result     TEXT CHECK (policy_result IS NULL
                        OR policy_result IN ('PASS','WARN','BLOCK')),
    policy_detail     TEXT,                              -- JSON: violations, each with a finding id
    policy_version    TEXT,
    policy_checked_at TEXT,

    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_by        TEXT REFERENCES users(id),
    superseded_by     TEXT REFERENCES outreach_drafts(id),

    CHECK (json_valid(facts_used) AND json_valid(inferences_used)),
    CHECK (policy_detail IS NULL OR json_valid(policy_detail))
);

CREATE INDEX ix_drafts_business ON outreach_drafts(business_id, channel, sequence_no);
CREATE INDEX ix_drafts_campaign ON outreach_drafts(campaign_id, created_at);

CREATE TABLE outreach_messages (
    id                       TEXT PRIMARY KEY,           -- msg_...
    draft_id                 TEXT NOT NULL REFERENCES outreach_drafts(id),
    business_id              TEXT NOT NULL REFERENCES businesses(id),
    campaign_id              TEXT NOT NULL REFERENCES campaigns(id),
    contact_id               TEXT REFERENCES business_contacts(id),
    channel                  TEXT NOT NULL
                               CHECK (channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),
    status                   TEXT NOT NULL DEFAULT 'DRAFT'
                               CHECK (status IN ('DRAFT','POLICY_BLOCKED','PENDING_APPROVAL',
                                                 'APPROVED','QUEUED','SENT','DELIVERED',
                                                 'BOUNCED','FAILED','CANCELLED')),
    approval_id              TEXT REFERENCES outreach_approvals(id),

    sequence_no              INTEGER NOT NULL DEFAULT 1 CHECK (sequence_no >= 1),
    parent_message_id        TEXT REFERENCES outreach_messages(id),
    thread_key               TEXT NOT NULL,

    to_address_norm          TEXT,                       -- lowercase email / E.164 / wa_id
    to_address_dedupe        TEXT,
    to_address_display       TEXT,                       -- what Sagar was shown
    recipient_domain         TEXT,
    subject_final            TEXT,
    body_final               TEXT,
    body_hash                TEXT,                       -- sha256 of subject + RS + body

    idempotency_key          TEXT NOT NULL,
    provider                 TEXT,
    provider_message_id      TEXT,
    provider_status_code     INTEGER,
    provider_response        TEXT,
    provider_send_started_at TEXT,                       -- written before the transport call

    queued_at                TEXT,
    sent_at                  TEXT,
    delivered_at             TEXT,
    failed_at                TEXT,
    cancelled_at             TEXT,
    failure_code             TEXT,
    failure_detail           TEXT,
    attempt_count            INTEGER NOT NULL DEFAULT 0,
    next_retry_at            TEXT,

    eligibility_snapshot     TEXT,                       -- JSON Eligibility at SEND stage
    policy_override          INTEGER NOT NULL DEFAULT 0 CHECK (policy_override IN (0,1)),
    sent_by                  TEXT REFERENCES users(id),  -- the approving human
    worker_id                TEXT,

    created_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- Invariant 1, as a row constraint: a message at or past APPROVED carries its approval.
    -- The triggers below close the update path; this closes the insert path.
    CHECK (status NOT IN ('APPROVED','QUEUED','SENT','DELIVERED','BOUNCED')
           OR approval_id IS NOT NULL),
    CHECK (status <> 'SENT'   OR sent_at IS NOT NULL),
    CHECK (status <> 'FAILED' OR failure_code IS NOT NULL),
    CHECK (channel <> 'EMAIL' OR status IN ('DRAFT','POLICY_BLOCKED','CANCELLED')
           OR subject_final IS NOT NULL),
    CHECK (eligibility_snapshot IS NULL OR json_valid(eligibility_snapshot))
);

CREATE UNIQUE INDEX ux_om_idempotency ON outreach_messages(idempotency_key);
CREATE UNIQUE INDEX ux_om_provider_id ON outreach_messages(provider, provider_message_id)
    WHERE provider_message_id IS NOT NULL;
CREATE INDEX ix_om_business_status ON outreach_messages(business_id, status);
CREATE INDEX ix_om_addr_sent       ON outreach_messages(to_address_norm, sent_at);
CREATE INDEX ix_om_addr_dedupe     ON outreach_messages(to_address_dedupe, sent_at);
CREATE INDEX ix_om_domain_sent     ON outreach_messages(recipient_domain, sent_at);
CREATE INDEX ix_om_sent_at         ON outreach_messages(sent_at);
CREATE INDEX ix_om_queue           ON outreach_messages(status, next_retry_at);
CREATE INDEX ix_om_thread          ON outreach_messages(thread_key, sequence_no);
CREATE INDEX ix_om_campaign        ON outreach_messages(campaign_id, status);

CREATE TABLE outreach_approvals (
    id                   TEXT PRIMARY KEY,               -- apr_...
    message_id           TEXT NOT NULL REFERENCES outreach_messages(id) ON DELETE CASCADE,
    draft_id             TEXT NOT NULL REFERENCES outreach_drafts(id),
    business_id          TEXT NOT NULL REFERENCES businesses(id),
    contact_id           TEXT REFERENCES business_contacts(id),
    channel              TEXT NOT NULL
                           CHECK (channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),

    approved_by          TEXT NOT NULL REFERENCES users(id),
    approved_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- Proof that a human browser session, not a machine token, created this row. The API-token
    -- authenticator used by the worker and the CLI cannot mint a session, so it cannot supply a
    -- legal value for session_auth_method. That is the type-level barrier behind invariant 1.
    session_id           TEXT NOT NULL,
    session_auth_method  TEXT NOT NULL
                           CHECK (session_auth_method IN ('PASSWORD','PASSWORD_TOTP')),
    client_ip            TEXT,
    user_agent           TEXT,

    -- exactly what was on screen
    approved_subject     TEXT,
    approved_body        TEXT NOT NULL,
    approved_body_hash   TEXT NOT NULL,
    approved_to_address  TEXT NOT NULL,
    confirmation_text    TEXT NOT NULL,                  -- the confirm sentence, stored verbatim
    displayed            TEXT NOT NULL DEFAULT '{}',     -- JSON: the preview items as rendered
    eligibility_snapshot TEXT NOT NULL DEFAULT '{}',
    preview_token        TEXT NOT NULL,
    idempotency_key      TEXT NOT NULL,

    revoked_at           TEXT,
    revoked_by           TEXT REFERENCES users(id),
    revoke_reason        TEXT,

    CHECK (json_valid(displayed) AND json_valid(eligibility_snapshot))
);

CREATE UNIQUE INDEX ux_approvals_live_message
    ON outreach_approvals(message_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX ux_approvals_idem ON outreach_approvals(idempotency_key);
CREATE INDEX ix_approvals_business    ON outreach_approvals(business_id, approved_at);

CREATE TABLE outreach_events (
    id                TEXT PRIMARY KEY,                  -- evt_...
    message_id        TEXT NOT NULL REFERENCES outreach_messages(id) ON DELETE CASCADE,
    event             TEXT NOT NULL CHECK (event IN (
                          'DRAFTED','EDITED','POLICY_PASS','POLICY_BLOCK','PREVIEWED',
                          'ELIGIBILITY_BLOCK','APPROVED','APPROVAL_REVOKED','QUEUED',
                          'SEND_ATTEMPT','SENT','PROVIDER_ERROR','RATE_LIMITED','INDETERMINATE',
                          'DELIVERED','BOUNCED','COMPLAINED','OPENED','CLICKED','UNSUBSCRIBED',
                          'FAILED','CANCELLED','MANUAL_RECORDED','CALL_LOGGED')),
    at                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    actor_type        TEXT NOT NULL CHECK (actor_type IN ('HUMAN','SYSTEM','PROVIDER')),
    actor_id          TEXT,
    detail            TEXT,
    -- The inbound dedupe key. There are no webhooks on this stack; poll_inbox sets it to the
    -- inbound mail's own Message-ID, so re-reading the same DSN produces one row.
    provider_event_id TEXT,

    CHECK (detail IS NULL OR json_valid(detail))
);

CREATE INDEX ix_events_message ON outreach_events(message_id, at);
CREATE UNIQUE INDEX ux_events_provider_event
    ON outreach_events(provider_event_id) WHERE provider_event_id IS NOT NULL;

-- ===========================================================================
-- 14. responses
-- ===========================================================================
CREATE TABLE responses (
    id                        TEXT PRIMARY KEY,          -- rsp_...
    business_id               TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,

    -- message_id is nullable on purpose: a reply can arrive from an address we mailed months
    -- ago or from a colleague who was forwarded the mail. Refusing to store those would lose
    -- exactly the replies that matter most, so attribution carries its own confidence instead.
    message_id                TEXT REFERENCES outreach_messages(id),
    campaign_id               TEXT REFERENCES campaigns(id),
    contact_id                TEXT REFERENCES business_contacts(id),
    channel                   TEXT NOT NULL
                                CHECK (channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),
    attribution               TEXT NOT NULL DEFAULT 'UNATTRIBUTED'
                                CHECK (attribution IN ('THREAD_HEADER','PROVIDER_ID',
                                                       'ADDRESS_MATCH','OPERATOR',
                                                       'UNATTRIBUTED')),
    attribution_confidence    TEXT NOT NULL DEFAULT 'MEDIUM'
                                CHECK (attribution_confidence IN ('HIGH','MEDIUM','LOW')),

    direction                 TEXT NOT NULL DEFAULT 'INBOUND'
                                CHECK (direction IN ('INBOUND','OUTBOUND_MANUAL')),
    from_address_norm         TEXT,
    from_address_hmac         TEXT,
    from_display              TEXT,
    subject                   TEXT,
    body_text                 TEXT NOT NULL,
    body_excerpt              TEXT NOT NULL,             -- first 280 chars, for lists and alerts
    body_html_path            TEXT,
    provider_message_id       TEXT,
    in_reply_to               TEXT,
    thread_key                TEXT,
    received_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- The AI classifies. It never replies.
    classification            TEXT CHECK (classification IS NULL OR classification IN
                                ('INTERESTED','VERY_INTERESTED','DEMO_REQUESTED',
                                 'MEETING_REQUESTED','PRICE_REQUESTED','MORE_INFORMATION',
                                 'LATER','NOT_INTERESTED','ALREADY_HAVE_SOFTWARE',
                                 'WRONG_CONTACT','OPT_OUT','COMPLAINT','UNKNOWN')),
    confidence                TEXT CHECK (confidence IS NULL
                                OR confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct            INTEGER CHECK (confidence_pct IS NULL
                                OR confidence_pct BETWEEN 0 AND 100),
    interpretation            TEXT,
    recommended_action        TEXT,
    classifier_model_id       TEXT,
    classifier_prompt_version TEXT,
    classified_at             TEXT,
    classification_state      TEXT NOT NULL DEFAULT 'PENDING'
                                CHECK (classification_state IN ('PENDING','CLASSIFIED','FAILED',
                                                                'HUMAN_CORRECTED')),
    classification_error      TEXT,

    human_classification      TEXT CHECK (human_classification IS NULL
                                OR human_classification IN
                                ('INTERESTED','VERY_INTERESTED','DEMO_REQUESTED',
                                 'MEETING_REQUESTED','PRICE_REQUESTED','MORE_INFORMATION',
                                 'LATER','NOT_INTERESTED','ALREADY_HAVE_SOFTWARE',
                                 'WRONG_CONTACT','OPT_OUT','COMPLAINT','UNKNOWN')),
    human_classified_by       TEXT REFERENCES users(id),
    human_classified_at       TEXT,
    human_note                TEXT,

    -- Pre-LLM safety scan: legal language must be seen before anything reaches a model.
    legal_flag                INTEGER NOT NULL DEFAULT 0 CHECK (legal_flag IN (0,1)),
    legal_flag_pattern        TEXT,
    legal_flag_excerpt        TEXT,

    handoff_id                TEXT REFERENCES handoffs(id),
    snooze_until              TEXT,
    is_stopper                INTEGER NOT NULL DEFAULT 0 CHECK (is_stopper IN (0,1)),

    created_at                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (classification_state <> 'CLASSIFIED' OR (classification IS NOT NULL
           AND classifier_model_id IS NOT NULL AND classifier_prompt_version IS NOT NULL
           AND classified_at IS NOT NULL)),
    CHECK (classification_state <> 'FAILED' OR classification_error IS NOT NULL),
    CHECK ((human_classification IS NULL) = (human_classified_at IS NULL)),
    CHECK (human_classification IS NULL OR human_classified_by IS NOT NULL),
    CHECK (legal_flag = 0 OR legal_flag_pattern IS NOT NULL),
    CHECK (length(body_excerpt) <= 280)
);

-- Inbox-poll idempotency. poll_inbox re-delivers on every slot, and a duplicate reply would
-- create a duplicate handoff and a duplicate alert at 02:00.
CREATE UNIQUE INDEX ux_responses_provider ON responses(channel, provider_message_id)
    WHERE provider_message_id IS NOT NULL;
CREATE INDEX ix_responses_business   ON responses(business_id, received_at);
CREATE INDEX ix_responses_message    ON responses(message_id, received_at);
CREATE INDEX ix_responses_pending    ON responses(received_at)
    WHERE classification_state = 'PENDING';
CREATE INDEX ix_responses_class      ON responses(classification, received_at);
CREATE INDEX ix_responses_campaign   ON responses(campaign_id, classification);
CREATE INDEX ix_responses_legal      ON responses(received_at) WHERE legal_flag = 1;
CREATE INDEX ix_responses_correction ON responses(human_classified_at)
    WHERE human_classification IS NOT NULL;

-- ===========================================================================
-- 15. handoffs
-- ===========================================================================
-- An interested lead stops the machine and pages Sagar. brief_json is a snapshot, not a cache:
-- it is what was true when the trigger fired, and it must not silently rewrite itself when the
-- research changes afterwards.
CREATE TABLE handoffs (
    id                     TEXT PRIMARY KEY,             -- hnd_...
    business_id            TEXT NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    campaign_id            TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
    response_id            TEXT NOT NULL REFERENCES responses(id) ON DELETE RESTRICT,
    outreach_message_id    TEXT REFERENCES outreach_messages(id) ON DELETE SET NULL,
    previous_handoff_id    TEXT REFERENCES handoffs(id) ON DELETE SET NULL,
    owner_user_id          TEXT REFERENCES users(id) ON DELETE SET NULL,

    trigger_rule           TEXT NOT NULL CHECK (trigger_rule IN (
                               'CLASSIFICATION','COMPLAINT','LOW_CONFIDENCE',
                               'LEGAL_LANGUAGE','MANUAL')),
    trigger_classification TEXT CHECK (trigger_classification IS NULL
                               OR trigger_classification IN (
                               'INTERESTED','VERY_INTERESTED','DEMO_REQUESTED',
                               'MEETING_REQUESTED','PRICE_REQUESTED','MORE_INFORMATION','LATER',
                               'NOT_INTERESTED','ALREADY_HAVE_SOFTWARE','WRONG_CONTACT',
                               'OPT_OUT','COMPLAINT','UNKNOWN')),
    trigger_detail         TEXT NOT NULL DEFAULT '',
    confidence             TEXT NOT NULL CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct         INTEGER CHECK (confidence_pct IS NULL
                               OR confidence_pct BETWEEN 0 AND 100),

    priority               TEXT NOT NULL DEFAULT 'NORMAL'
                               CHECK (priority IN ('URGENT','HIGH','NORMAL')),
    state                  TEXT NOT NULL DEFAULT 'OPEN'
                               CHECK (state IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','CLOSED')),
    outcome                TEXT CHECK (outcome IS NULL OR outcome IN (
                               'DEMO_SCHEDULED','PROPOSAL_SENT','WON','LOST','NO_RESPONSE')),
    lost_reason            TEXT CHECK (lost_reason IS NULL OR lost_reason IN (
                               'PRICE','ALREADY_HAVE_SOFTWARE','NO_BUDGET','NO_DECISION_MAKER',
                               'WRONG_FIT','WENT_QUIET','OTHER')),

    brief_json             TEXT NOT NULL DEFAULT '{}',
    brief_version          INTEGER NOT NULL DEFAULT 1,
    response_count         INTEGER NOT NULL DEFAULT 1,

    -- Text only, never executable. Nothing in this system replies on its own.
    recommended_action     TEXT NOT NULL,
    recommended_channel    TEXT CHECK (recommended_channel IS NULL OR recommended_channel IN (
                               'EMAIL','WHATSAPP','PHONE','MANUAL')),
    recommended_by_when    TEXT,
    action_rule_id         TEXT NOT NULL DEFAULT 'default',
    action_model_id        TEXT,
    action_prompt_version  TEXT,

    notify_count           INTEGER NOT NULL DEFAULT 0,
    first_notified_at      TEXT,
    last_notified_at       TEXT,
    last_notify_channel    TEXT CHECK (last_notify_channel IS NULL OR last_notify_channel IN (
                               'TELEGRAM','EMAIL','DIGEST','NONE')),
    telegram_chat_id       TEXT,
    telegram_message_id    INTEGER,
    snoozed_until          TEXT,

    sla_ack_due_at         TEXT NOT NULL,
    sla_progress_due_at    TEXT NOT NULL,
    sla_close_due_at       TEXT NOT NULL,
    sla_breach_count       INTEGER NOT NULL DEFAULT 0,
    sla_last_breach_at     TEXT,

    -- Money is INTEGER rupees, not float. One operator selling in INR.
    demo_scheduled_at      TEXT,
    demo_held_at           TEXT,
    proposal_sent_at       TEXT,
    proposal_value_inr     INTEGER CHECK (proposal_value_inr IS NULL OR proposal_value_inr >= 0),
    won_value_inr          INTEGER CHECK (won_value_inr IS NULL OR won_value_inr >= 0),

    created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    acknowledged_at        TEXT,
    started_at             TEXT,
    closed_at              TEXT,
    updated_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (json_valid(brief_json)),
    CHECK (state <> 'CLOSED' OR outcome IS NOT NULL),
    CHECK (state <> 'CLOSED' OR closed_at IS NOT NULL),
    CHECK (outcome IS NULL OR state = 'CLOSED'),
    CHECK (state = 'OPEN' OR acknowledged_at IS NOT NULL),
    CHECK (state <> 'IN_PROGRESS' OR started_at IS NOT NULL),
    CHECK (outcome <> 'WON' OR won_value_inr IS NOT NULL),
    CHECK (outcome <> 'LOST' OR lost_reason IS NOT NULL),
    CHECK (outcome <> 'DEMO_SCHEDULED' OR demo_scheduled_at IS NOT NULL),
    CHECK (outcome <> 'PROPOSAL_SENT' OR proposal_sent_at IS NOT NULL)
);

-- One live handoff per business. This partial unique index IS the de-duplication guarantee;
-- everything in Python is a courtesy on top of it.
CREATE UNIQUE INDEX ux_handoffs_open_business ON handoffs(business_id) WHERE state <> 'CLOSED';
CREATE UNIQUE INDEX ux_handoffs_open_response ON handoffs(response_id) WHERE state <> 'CLOSED';
CREATE INDEX ix_handoffs_queue    ON handoffs(state, priority, created_at);
CREATE INDEX ix_handoffs_sla      ON handoffs(state, sla_ack_due_at);
CREATE INDEX ix_handoffs_campaign ON handoffs(campaign_id, created_at);
CREATE INDEX ix_handoffs_outcome  ON handoffs(outcome, closed_at);
CREATE INDEX ix_handoffs_business ON handoffs(business_id, created_at);

-- ===========================================================================
-- 16. jobs
-- ===========================================================================
-- No Celery, no Redis. One in-process worker pool claiming rows by UPDATE with a lease, because
-- the deploy target is one laptop. A crash mid-job is recoverable: leases expire.
CREATE TABLE jobs (
    id               TEXT PRIMARY KEY,                   -- job_...
    type             TEXT NOT NULL,
    lane             TEXT NOT NULL DEFAULT 'io'
                       CHECK (lane IN ('llm','io','export','notify','maint')),
    payload          TEXT NOT NULL DEFAULT '{}'
                       CHECK (json_valid(payload) AND json_type(payload) = 'object'),

    state            TEXT NOT NULL DEFAULT 'QUEUED'
                       CHECK (state IN ('QUEUED','LEASED','RUNNING','SUCCEEDED','FAILED',
                                        'DEAD','CANCELLED')),
    priority         INTEGER NOT NULL DEFAULT 100 CHECK (priority BETWEEN 0 AND 1000),
    run_after        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    attempts         INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts     INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),

    lease_owner      TEXT,
    lease_expires_at TEXT,
    heartbeat_at     TEXT,

    last_error       TEXT,
    last_error_class TEXT,
    dedupe_key       TEXT,

    campaign_id      TEXT REFERENCES campaigns(id),
    business_id      TEXT REFERENCES businesses(id),
    parent_job_id    TEXT REFERENCES jobs(id),
    batch_id         TEXT,                               -- bat_..., groups a fan-out
    trace_id         TEXT NOT NULL,                      -- trc_..., survives re-enqueue

    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),

    progress_done    INTEGER NOT NULL DEFAULT 0,
    progress_total   INTEGER,
    progress_note    TEXT,

    timeout_seconds  INTEGER NOT NULL DEFAULT 300 CHECK (timeout_seconds > 0),
    result           TEXT CHECK (result IS NULL OR json_valid(result)),

    created_by       TEXT REFERENCES users(id),          -- NULL = system
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    started_at       TEXT,
    finished_at      TEXT,

    CHECK (state NOT IN ('LEASED','RUNNING')
           OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CHECK (state NOT IN ('SUCCEEDED','FAILED','DEAD','CANCELLED') OR finished_at IS NOT NULL),
    CHECK (state NOT IN ('SUCCEEDED','FAILED','DEAD','CANCELLED')
           OR (lease_owner IS NULL AND lease_expires_at IS NULL)),
    CHECK (attempts <= max_attempts),
    CHECK (state <> 'FAILED' OR last_error IS NOT NULL),
    CHECK (progress_total IS NULL OR progress_done <= progress_total)
);

CREATE INDEX ix_jobs_claim ON jobs(lane, priority DESC, run_after) WHERE state = 'QUEUED';
CREATE INDEX ix_jobs_lease ON jobs(lease_expires_at) WHERE state IN ('LEASED','RUNNING');
CREATE UNIQUE INDEX ux_jobs_dedupe ON jobs(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX ix_jobs_campaign ON jobs(campaign_id, state) WHERE campaign_id IS NOT NULL;

CREATE TABLE job_runs (
    id                  TEXT PRIMARY KEY,                -- run_...
    job_id              TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    attempt_no          INTEGER NOT NULL CHECK (attempt_no >= 1),
    type                TEXT NOT NULL,                   -- denormalised on purpose
    lane                TEXT NOT NULL,
    worker_id           TEXT NOT NULL,

    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    duration_ms         INTEGER,

    -- LEASE_EXPIRED is written by the reaper, not by the dead worker. The dead worker cannot
    -- write anything, which is the point.
    outcome             TEXT CHECK (outcome IS NULL OR outcome IN
                          ('SUCCEEDED','RETRY','DEFERRED','FAILED','DEAD','CANCELLED',
                           'TIMEOUT','LEASE_EXPIRED')),
    error_class         TEXT,
    error_message       TEXT,
    error_detail        TEXT CHECK (error_detail IS NULL OR json_valid(error_detail)),

    model_id            TEXT,
    prompt_version      TEXT,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    thinking_tokens     INTEGER,
    cached_tokens       INTEGER,
    quota_units         INTEGER,          -- requests charged to the day, not rupees
    provider            TEXT,
    provider_request_id TEXT,             -- google-genai response_id, or the SMTP accepted id

    UNIQUE (job_id, attempt_no)
);

CREATE INDEX ix_job_runs_job    ON job_runs(job_id, attempt_no);
CREATE INDEX ix_job_runs_recent ON job_runs(type, started_at);
CREATE INDEX ix_job_runs_failed ON job_runs(type, finished_at)
    WHERE outcome IN ('FAILED','TIMEOUT','LEASE_EXPIRED');
CREATE INDEX ix_job_runs_quota  ON job_runs(started_at) WHERE quota_units IS NOT NULL;

-- ===========================================================================
-- 17. report_exports
-- ===========================================================================
CREATE TABLE report_exports (
    id                TEXT PRIMARY KEY,                  -- rex_...
    campaign_id       TEXT REFERENCES campaigns(id),
    fmt               TEXT NOT NULL CHECK (fmt IN ('HTML','CSV','XLSX','PDF','JSON')),
    scope             TEXT NOT NULL
                        CHECK (scope IN ('CAMPAIGN','DAILY','CITY','INDUSTRY',
                                         'TOP_OPPORTUNITIES','SUBJECT_ACCESS','AUDIT')),
    scope_key         TEXT,
    title             TEXT NOT NULL,
    filename          TEXT NOT NULL,
    rel_path          TEXT NOT NULL,                     -- relative to REPORTS_DIR

    bytes             INTEGER NOT NULL CHECK (bytes >= 0),
    content_sha256    TEXT NOT NULL CHECK (length(content_sha256) = 64),
    data_sha256       TEXT NOT NULL CHECK (length(data_sha256) = 64),
    data_rel_path     TEXT,
    row_count         INTEGER NOT NULL CHECK (row_count >= 0),

    filters_json      TEXT NOT NULL DEFAULT '{}',
    columns_json      TEXT,
    contains_pii      INTEGER NOT NULL DEFAULT 0 CHECK (contains_pii IN (0,1)),

    template_version  TEXT NOT NULL,
    generator_version TEXT NOT NULL,
    db_schema_version INTEGER NOT NULL,
    query_fingerprint TEXT NOT NULL,

    generated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    generated_by      TEXT REFERENCES users(id),
    job_run_id        TEXT REFERENCES job_runs(id),

    retention_class   TEXT NOT NULL DEFAULT 'P2Y'
                        CHECK (retention_class IN ('PERMANENT','P2Y','P180D')),
    expires_at        TEXT,
    deleted_at        TEXT,
    deleted_reason    TEXT CHECK (deleted_reason IS NULL OR
                        deleted_reason IN ('RETENTION','ERASURE','MANUAL','SUPERSEDED')),
    superseded_by     TEXT REFERENCES report_exports(id),

    CHECK (json_valid(filters_json)),
    CHECK (deleted_at IS NULL OR deleted_reason IS NOT NULL),
    -- DPDP purpose limitation as a constraint: a file with contact columns in it may not be
    -- kept forever.
    CHECK (contains_pii = 0 OR retention_class <> 'PERMANENT')
);

CREATE UNIQUE INDEX ux_report_exports_path ON report_exports(rel_path);
CREATE INDEX ix_report_exports_campaign ON report_exports(campaign_id, generated_at);
CREATE INDEX ix_report_exports_scope    ON report_exports(scope, scope_key, generated_at);
CREATE INDEX ix_report_exports_live     ON report_exports(generated_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_report_exports_expiry   ON report_exports(expires_at)   WHERE deleted_at IS NULL;

-- ===========================================================================
-- 18. state machine tables
-- ===========================================================================
CREATE TABLE business_status_transitions (
    from_status TEXT NOT NULL,
    to_status   TEXT NOT NULL,
    actor_kind  TEXT NOT NULL CHECK (actor_kind IN ('HUMAN','SYSTEM')),
    ref         TEXT NOT NULL,
    note        TEXT NOT NULL,
    PRIMARY KEY (from_status, to_status, actor_kind)
);

INSERT INTO business_status_transitions (from_status, to_status, actor_kind, ref, note) VALUES
    ('AI_RESEARCHED',      'NEEDS_VERIFICATION', 'SYSTEM', 'T01', 'research complete and qualified'),
    ('AI_RESEARCHED',      'SKIPPED',            'SYSTEM', 'T02', 'below campaign bar or research failed'),
    ('AI_RESEARCHED',      'SKIPPED',            'HUMAN',  'T04', 'skipped from the grid'),
    ('AI_RESEARCHED',      'REJECTED',           'HUMAN',  'T05', 'rejected from the grid'),
    ('NEEDS_VERIFICATION', 'VERIFIED',           'HUMAN',  'T06', 'nine checks passed'),
    ('NEEDS_VERIFICATION', 'REJECTED',           'HUMAN',  'T07', 'a check failed, reason recorded'),
    ('NEEDS_VERIFICATION', 'SKIPPED',            'HUMAN',  'T08', 'decide later'),
    ('VERIFIED',           'CONTACT_READY',      'SYSTEM', 'T09', 'contact-ready predicate holds'),
    ('VERIFIED',           'NEEDS_VERIFICATION', 'SYSTEM', 'T10', 're-verification trigger fired'),
    ('VERIFIED',           'NEEDS_VERIFICATION', 'HUMAN',  'T11', 'verification revoked'),
    ('VERIFIED',           'REJECTED',           'HUMAN',  'T12', 'rejected after verifying'),
    ('VERIFIED',           'SKIPPED',            'HUMAN',  'T13', 'parked'),
    ('CONTACT_READY',      'VERIFIED',           'SYSTEM', 'T14', 'non-verification clause broke'),
    ('CONTACT_READY',      'NEEDS_VERIFICATION', 'SYSTEM', 'T15', 'verification went stale'),
    ('CONTACT_READY',      'NEEDS_VERIFICATION', 'HUMAN',  'T16', 'verification revoked'),
    ('CONTACT_READY',      'REJECTED',           'HUMAN',  'T17', 'rejected after promotion'),
    ('CONTACT_READY',      'SKIPPED',            'HUMAN',  'T18', 'parked'),
    ('CONTACT_READY',      'CONTACTED',          'SYSTEM', 'T19', 'a message reached SENT'),
    ('CONTACTED',          'RESPONDED',          'SYSTEM', 'T20', 'inbound response classified'),
    ('RESPONDED',          'INTERESTED',         'SYSTEM', 'T21', 'classification in the interested set'),
    ('SKIPPED',            'AI_RESEARCHED',      'SYSTEM', 'T22', 're-research queued'),
    ('SKIPPED',            'NEEDS_VERIFICATION', 'HUMAN',  'T23', 'unskipped'),
    ('HUMAN_HANDOFF',      'CONTACT_READY',      'HUMAN',  'T26', 'returned to the automated pool'),
    ('HUMAN_HANDOFF',      'VERIFIED',           'HUMAN',  'T27', 'returned, predicate not satisfied'),
    ('HUMAN_HANDOFF',      'NEEDS_VERIFICATION', 'HUMAN',  'T28', 'returned, verification stale'),
    ('REJECTED',           'NEEDS_VERIFICATION', 'HUMAN',  'T29', 'reopened, non-permanent reason');

-- T24 / T25: the handoff door. Reachable from every other state, by either actor kind. A legal
-- complaint, a threat, or a misrouted reply must never be blocked by a state machine.
INSERT INTO business_status_transitions (from_status, to_status, actor_kind, ref, note)
SELECT s.v, 'HUMAN_HANDOFF', a.v, 'T24/T25', 'the handoff door is never locked'
  FROM (SELECT 'AI_RESEARCHED' AS v UNION ALL SELECT 'NEEDS_VERIFICATION'
        UNION ALL SELECT 'VERIFIED'  UNION ALL SELECT 'REJECTED'
        UNION ALL SELECT 'SKIPPED'   UNION ALL SELECT 'CONTACT_READY'
        UNION ALL SELECT 'CONTACTED' UNION ALL SELECT 'RESPONDED'
        UNION ALL SELECT 'INTERESTED') s
 CROSS JOIN (SELECT 'HUMAN' AS v UNION ALL SELECT 'SYSTEM') a;

-- There is no path from DRAFT, POLICY_BLOCKED or PENDING_APPROVAL to SENT, and no path out of a
-- terminal state back into the drafting states. A retry is a NEW message row with a new
-- idempotency_key, not a resurrection.
CREATE TABLE outreach_status_transitions (
    from_status TEXT NOT NULL,
    to_status   TEXT NOT NULL,
    note        TEXT NOT NULL,
    PRIMARY KEY (from_status, to_status)
);

INSERT INTO outreach_status_transitions (from_status, to_status, note) VALUES
    ('DRAFT',            'PENDING_APPROVAL', 'claim policy check passed'),
    ('DRAFT',            'POLICY_BLOCKED',   'claim policy check failed'),
    ('DRAFT',            'CANCELLED',        'the draft was discarded'),
    ('POLICY_BLOCKED',   'DRAFT',            'regenerated or edited, re-check pending'),
    ('POLICY_BLOCKED',   'CANCELLED',        'abandoned'),
    ('PENDING_APPROVAL', 'DRAFT',            'edited after policy pass, re-check required'),
    ('PENDING_APPROVAL', 'APPROVED',         'human approval row written'),
    ('PENDING_APPROVAL', 'CANCELLED',        'abandoned or blocked by an eligibility gate'),
    ('APPROVED',         'QUEUED',           'send job enqueued'),
    ('APPROVED',         'CANCELLED',        'approval revoked before queueing'),
    ('QUEUED',           'SENT',             'transport accepted the message'),
    ('QUEUED',           'FAILED',           'permanent transport error'),
    ('QUEUED',           'CANCELLED',        'pulled from the queue before transmit'),
    ('SENT',             'DELIVERED',        'WhatsApp delivery receipt; unreachable on EMAIL'),
    ('SENT',             'BOUNCED',          'poll_inbox parsed a hard-bounce DSN'),
    ('SENT',             'FAILED',           'async rejection after acceptance'),
    ('DELIVERED',        'BOUNCED',          'late hard bounce after a delivery event');

-- ===========================================================================
-- 19. THE SAFETY TRIGGERS
-- ===========================================================================
-- Everything above is bookkeeping. This section is the reason the system exists.

-- --- businesses.status moves only along the declared transitions --------------------------
CREATE TRIGGER trg_biz_status_transition
BEFORE UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status <> OLD.status
 AND NOT EXISTS (SELECT 1 FROM business_status_transitions t
                  WHERE t.from_status = OLD.status
                    AND t.to_status   = NEW.status
                    AND t.actor_kind  = NEW.status_actor_kind)
BEGIN
    SELECT RAISE(ABORT, 'illegal businesses.status transition for this actor kind');
END;

-- VERIFIED is a human signature backed by a real, complete, live checklist. No system actor
-- can produce one.
CREATE TRIGGER trg_biz_verified_needs_human_checklist
BEFORE UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status = 'VERIFIED' AND OLD.status <> 'VERIFIED'
 AND (NEW.status_actor_kind <> 'HUMAN'
      OR NEW.status_actor_user_id IS NULL
      OR NEW.status_verification_id IS NULL
      OR NOT EXISTS (SELECT 1 FROM verifications v
                      WHERE v.id            = NEW.status_verification_id
                        AND v.business_id   = NEW.id
                        AND v.state         = 'SUBMITTED'
                        AND v.verdict       = 'VERIFIED'
                        AND v.superseded_at IS NULL
                        AND v.checks_passed = 9
                        AND v.checks_failed = 0))
BEGIN
    SELECT RAISE(ABORT,
      'VERIFIED requires a live human verification with all nine checks passed');
END;

-- Belt to the transition table's braces: this holds even if someone inserts a
-- ('VERIFIED','CONTACTED') row into business_status_transitions.
CREATE TRIGGER trg_biz_contacted_only_from_ready
BEFORE UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status = 'CONTACTED' AND OLD.status <> 'CONTACT_READY'
BEGIN
    SELECT RAISE(ABORT, 'CONTACTED is reachable only from CONTACT_READY (spec 19, 45)');
END;

CREATE TRIGGER trg_biz_status_touch
AFTER UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status <> OLD.status
BEGIN
    UPDATE businesses
       SET status_changed_at = strftime('%Y-%m-%dT%H:%M:%SZ','now'),
           updated_at        = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.id;
END;

-- --- Invariants 1 and 2: nothing is sent without a human approval row ----------------------
CREATE TRIGGER trg_om_transition
BEFORE UPDATE OF status ON outreach_messages
FOR EACH ROW
WHEN NEW.status <> OLD.status
 AND NOT EXISTS (SELECT 1 FROM outreach_status_transitions t
                 WHERE t.from_status = OLD.status AND t.to_status = NEW.status)
BEGIN
    SELECT RAISE(ABORT, 'illegal outreach_messages.status transition');
END;

-- Invariant 1, stated as bluntly as SQLite allows.
CREATE TRIGGER trg_om_send_needs_approval
BEFORE UPDATE OF status ON outreach_messages
FOR EACH ROW
WHEN NEW.status = 'SENT' AND NEW.approval_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'SENT requires an approval_id: there is no send path without a human');
END;

-- Invariant 2. SENT is reachable only from APPROVED or QUEUED, and QUEUED is reachable only
-- from APPROVED, so every SENT message passed through APPROVED.
CREATE TRIGGER trg_om_send_only_from_approved
BEFORE UPDATE OF status ON outreach_messages
FOR EACH ROW
WHEN NEW.status = 'SENT' AND OLD.status NOT IN ('APPROVED','QUEUED')
BEGIN
    SELECT RAISE(ABORT, 'SENT is reachable only from APPROVED or QUEUED (spec 45)');
END;

-- The approval must be live and must match what is actually being sent. Approving one body
-- does not authorise sending a different one, or sending it to a different address.
CREATE TRIGGER trg_om_send_approval_matches
BEFORE UPDATE OF status ON outreach_messages
FOR EACH ROW
WHEN NEW.status = 'SENT'
 AND NOT EXISTS (SELECT 1 FROM outreach_approvals a
                 WHERE a.id                  = NEW.approval_id
                   AND a.message_id          = NEW.id
                   AND a.revoked_at          IS NULL
                   AND a.approved_body_hash  = NEW.body_hash
                   AND a.approved_to_address = NEW.to_address_norm)
BEGIN
    SELECT RAISE(ABORT,
      'SENT requires a live approval whose body hash and address match what is being sent');
END;

-- The insert path, closed too. A row cannot be born sent.
CREATE TRIGGER trg_om_insert_not_sent
BEFORE INSERT ON outreach_messages
FOR EACH ROW
WHEN NEW.status IN ('SENT','DELIVERED','BOUNCED')
BEGIN
    SELECT RAISE(ABORT, 'an outreach_messages row may not be inserted in a sent state');
END;

CREATE TRIGGER trg_om_touch
AFTER UPDATE ON outreach_messages
FOR EACH ROW
BEGIN
    UPDATE outreach_messages
       SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.id;
END;

-- --- The verification gate, one level down ------------------------------------------------
-- Spec 19 says the Send button must not exist on a raw research result. This is the same rule
-- applied to storage: the object the button would need cannot be stored.
CREATE TRIGGER trg_no_selection_before_contact_ready
BEFORE INSERT ON selections
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM businesses b
                  WHERE b.id = NEW.business_id
                    AND b.status IN ('CONTACT_READY','CONTACTED','RESPONDED'))
BEGIN
    SELECT RAISE(ABORT, 'only CONTACT_READY businesses may be selected (spec 18)');
END;

CREATE TRIGGER trg_no_draft_before_contact_ready
BEFORE INSERT ON outreach_drafts
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM businesses b
                  WHERE b.id = NEW.business_id
                    AND b.status IN ('CONTACT_READY','CONTACTED','RESPONDED'))
BEGIN
    SELECT RAISE(ABORT,
      'no outreach draft may exist for a business that has not passed verification (spec 19, 45)');
END;

CREATE TRIGGER trg_no_message_before_contact_ready
BEFORE INSERT ON outreach_messages
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM businesses b
                  WHERE b.id = NEW.business_id
                    AND b.status IN ('CONTACT_READY','CONTACTED','RESPONDED'))
BEGIN
    SELECT RAISE(ABORT,
      'no outreach message may exist for a business that has not passed verification (spec 19, 45)');
END;

-- --- Invariant 3: opt-out is permanent ----------------------------------------------------
CREATE TRIGGER trg_suppressions_no_delete
BEFORE DELETE ON suppressions
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'suppressions are append-only: an opt-out is permanent');
END;

-- Releasing requires a manual DB session AND a matching audit row, which the application has no
-- code to create.
CREATE TRIGGER trg_suppressions_release_needs_audit
BEFORE UPDATE OF released_at ON suppressions
FOR EACH ROW
WHEN NEW.released_at IS NOT NULL
 AND (NEW.released_audit_id IS NULL
      OR NOT EXISTS (SELECT 1 FROM audit_log a
                     WHERE a.id = NEW.released_audit_id
                       AND a.action = 'SUPPRESSION_RELEASED'
                       AND a.entity_id = NEW.id))
BEGIN
    SELECT RAISE(ABORT, 'releasing a suppression requires an audit_log SUPPRESSION_RELEASED row');
END;

-- --- Invariant 4: an OBSERVED finding keeps its sources -------------------------------------
-- SQLite cannot express "at least one child row" as a CHECK, because the child does not exist
-- when the parent is inserted. radar/research.py holds the insert case in one transaction;
-- these two triggers hold the delete and the promote.
CREATE TRIGGER trg_finding_sources_no_orphan_observed
BEFORE DELETE ON finding_sources
FOR EACH ROW
WHEN (SELECT kind FROM research_findings WHERE id = OLD.finding_id) = 'OBSERVED'
 AND (SELECT COUNT(*) FROM finding_sources WHERE finding_id = OLD.finding_id) <= 1
BEGIN
    SELECT RAISE(ABORT,
      'an OBSERVED finding must keep at least one source (spec 12); re-type it INFERRED first');
END;

CREATE TRIGGER trg_finding_promote_needs_source
BEFORE UPDATE OF kind ON research_findings
FOR EACH ROW
WHEN NEW.kind = 'OBSERVED' AND OLD.kind <> 'OBSERVED'
 AND NOT EXISTS (SELECT 1 FROM finding_sources WHERE finding_id = NEW.id)
BEGIN
    SELECT RAISE(ABORT, 'cannot promote a finding to OBSERVED with no source (spec 12)');
END;

-- --- The audit log is append-only ----------------------------------------------------------
-- SQLite has no append-only table. This is the closest thing: any UPDATE or DELETE aborts the
-- statement and its transaction. It stops application bugs and it stops a hurried interactive
-- session. It does not stop someone who first drops the trigger; that is what the hash chain
-- and an off-box export are for.
CREATE TRIGGER trg_audit_log_no_update
BEFORE UPDATE ON audit_log
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: UPDATE is not permitted');
END;

CREATE TRIGGER trg_audit_log_no_delete
BEFORE DELETE ON audit_log
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: DELETE is not permitted');
END;

-- The chain is built at the head and nowhere else: seq is exactly one past the current maximum
-- and prev_hash is exactly the row_hash before it. Genesis links to 64 zeroes.
CREATE TRIGGER trg_audit_log_chain
BEFORE INSERT ON audit_log
FOR EACH ROW
WHEN NEW.seq <> 1 + (SELECT COALESCE(MAX(seq), 0) FROM audit_log)
   OR NEW.prev_hash <> COALESCE(
        (SELECT row_hash FROM audit_log WHERE seq = NEW.seq - 1),
        '0000000000000000000000000000000000000000000000000000000000000000')
BEGIN
    SELECT RAISE(ABORT, 'audit_log chain break: seq/prev_hash do not follow the current head');
END;

-- No raw contact address in an audit payload. The masked and hashed forms are
-- address_masked and address_sha256.
CREATE TRIGGER trg_audit_log_no_raw_address
BEFORE INSERT ON audit_log
FOR EACH ROW
WHEN json_extract(NEW.detail_json, '$.address') IS NOT NULL
   OR json_extract(NEW.detail_json, '$.to') IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
      'audit_log detail_json must use address_masked / address_sha256, never a raw address');
END;

-- --- v1 automation mode --------------------------------------------------------------------
-- HUMAN_APPROVAL is the only mode this build can honour, because it is the only mode with an
-- implemented approval source. The column keeps all four enum values so a later migration can
-- drop these two triggers rather than rewrite the column.
CREATE TRIGGER trg_contact_policy_v1_mode_ins
BEFORE INSERT ON contact_policy
FOR EACH ROW
WHEN NEW.automation_mode <> 'HUMAN_APPROVAL'
BEGIN
    SELECT RAISE(ABORT, 'automation_mode must be HUMAN_APPROVAL in v1');
END;

CREATE TRIGGER trg_contact_policy_v1_mode_upd
BEFORE UPDATE OF automation_mode ON contact_policy
FOR EACH ROW
WHEN NEW.automation_mode <> 'HUMAN_APPROVAL'
BEGIN
    SELECT RAISE(ABORT, 'automation_mode must be HUMAN_APPROVAL in v1');
END;

-- --- report_exports identity is immutable ---------------------------------------------------
CREATE TRIGGER trg_report_exports_identity_immutable
BEFORE UPDATE ON report_exports
FOR EACH ROW
WHEN NEW.content_sha256    <> OLD.content_sha256
  OR NEW.data_sha256       <> OLD.data_sha256
  OR NEW.rel_path          <> OLD.rel_path
  OR NEW.generated_at      <> OLD.generated_at
  OR NEW.row_count         <> OLD.row_count
  OR NEW.query_fingerprint <> OLD.query_fingerprint
BEGIN
    SELECT RAISE(ABORT, 'report_exports content identity is immutable');
END;

-- Files get deleted; rows get tombstoned. Deleting the row would lose the proof that the
-- report existed.
CREATE TRIGGER trg_report_exports_no_delete
BEFORE DELETE ON report_exports
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'report_exports rows are tombstoned (deleted_at), never deleted');
END;

-- --- handoffs ------------------------------------------------------------------------------
CREATE TRIGGER trg_handoffs_state_transition
BEFORE UPDATE OF state ON handoffs
FOR EACH ROW
WHEN OLD.state <> NEW.state
 AND (OLD.state || '>' || NEW.state) NOT IN (
     'OPEN>ACKNOWLEDGED', 'OPEN>CLOSED', 'ACKNOWLEDGED>IN_PROGRESS',
     'ACKNOWLEDGED>CLOSED', 'IN_PROGRESS>CLOSED')
BEGIN
    SELECT RAISE(ABORT, 'illegal handoff state transition');
END;

CREATE TRIGGER trg_handoffs_touch
AFTER UPDATE ON handoffs
FOR EACH ROW
BEGIN
    UPDATE handoffs SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = NEW.id;
END;

-- Opening a handoff moves the business into HUMAN_HANDOFF. The handoff door is never locked,
-- so this transition is legal from every state.
CREATE TRIGGER trg_handoffs_business_status
AFTER INSERT ON handoffs
FOR EACH ROW
BEGIN
    UPDATE businesses
       SET status = 'HUMAN_HANDOFF',
           status_actor_kind = 'SYSTEM',
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.business_id
       AND status <> 'HUMAN_HANDOFF';
END;

-- ===========================================================================
-- 20. Seed data
-- ===========================================================================

-- The bootstrap operator. Every verifications.verified_by, outreach_approvals.approved_by and
-- audit_log.actor_user_id has to resolve to a row, so one exists from migration time. The
-- password hash is deliberately not a valid argon2id PHC string: nothing can log in as this
-- user until a real credential is set. It is an anchor for foreign keys, not an account.
INSERT INTO users (id, email, email_norm, display_name, password_hash, password_algo,
                   must_change_password, role)
VALUES ('usr_00000000000000000000000000', 'owner@localhost', 'owner@localhost', 'Owner',
        '!locked-no-login', 'argon2id', 1, 'OWNER');

-- The default contact policy. HUMAN_APPROVAL, 21 days between touches, 3 attempts,
-- 2 follow-ups. email_sending_domain stays NULL: a freshly migrated database cannot mail
-- anybody by accident.
INSERT INTO contact_policy (id, scope, automation_mode, min_days_between_outreach,
                            max_attempts, max_followups)
VALUES ('GLOBAL', 'GLOBAL', 'HUMAN_APPROVAL', 21, 3, 2);

-- Rejection reason codes. bulk_ok = 0 wherever a suppression is written.
INSERT INTO verification_reason_codes
    (code, label, guidance, is_permanent, cool_off_days, writes_suppression, suppression_reason,
     bulk_ok, requires_note, ordinal) VALUES
    ('NOT_A_REAL_BUSINESS',  'Not a real business',
     'The listing does not correspond to a trading entity at all.',
     1, 0, 1, 'MANUAL', 0, 1, 1),
    ('CLOSED',               'Permanently closed',
     'It existed but has shut down. Reopen manually if that turns out to be wrong.',
     1, 0, 1, 'MANUAL', 0, 1, 2),
    ('WRONG_CITY',           'Outside the target city',
     'Real business, wrong place. No suppression: the city filter was wrong, not the business.',
     0, 0, 0, NULL, 1, 0, 3),
    ('WRONG_CATEGORY',       'Wrong category',
     'Real business in the right city, but not the kind of operation this campaign targets.',
     0, 90, 0, NULL, 1, 0, 4),
    ('TOO_SMALL',            'Too small to need this',
     'A one-person operation that a management system would burden rather than help.',
     0, 180, 0, NULL, 1, 0, 5),
    ('ALREADY_HAS_SOFTWARE', 'Already runs a system',
     'Visible evidence of an existing platform already doing the job.',
     0, 365, 0, NULL, 1, 1, 6),
    ('CONTACT_NOT_LEGITIMATE', 'Contact is not theirs',
     'The address or number belongs to a directory, an aggregator, or someone else entirely.',
     0, 30, 0, NULL, 0, 1, 7),
    ('RESEARCH_UNRELIABLE',  'Research does not hold up',
     'The findings do not survive opening the sources. Re-research rather than contact.',
     0, 30, 0, NULL, 1, 1, 8),
    ('DO_NOT_CONTACT',       'Do not contact',
     'A standing instruction, a prior request, or a DNC record. Permanent, and it suppresses.',
     1, 0, 1, 'DNC_LIST', 0, 1, 9),
    ('OTHER',                'Other',
     'Anything the eight above do not cover. The note is mandatory and is what makes it usable.',
     0, 90, 0, NULL, 0, 1, 10);

-- The audit action catalogue. audit.audit() with an action absent from this table fails on the
-- foreign key, which is the point: an action is a migration, not a string literal at a call site.
INSERT INTO audit_actions (action, domain, severity, user_visible, pii_class, description) VALUES
    ('CAMPAIGN_CREATED',       'SYSTEM',       'NOTICE',   1, 'NONE',      'A campaign was created'),
    ('CAMPAIGN_STARTED',       'SYSTEM',       'NOTICE',   1, 'NONE',      'A campaign began discovery'),
    ('CAMPAIGN_PAUSED',        'SYSTEM',       'NOTICE',   1, 'NONE',      'A campaign was paused'),
    ('CAMPAIGN_RESUMED',       'SYSTEM',       'NOTICE',   1, 'NONE',      'A paused campaign resumed'),
    ('CAMPAIGN_COMPLETED',     'SYSTEM',       'NOTICE',   1, 'NONE',      'A campaign finished'),
    ('CAMPAIGN_CANCELLED',     'SYSTEM',       'NOTICE',   1, 'NONE',      'A campaign was cancelled'),
    ('BUSINESS_DISCOVERED',    'RESEARCH',     'INFO',     1, 'NONE',      'A business row was created'),
    ('BUSINESS_REDISCOVERED',  'RESEARCH',     'INFO',     1, 'NONE',      'A known business reappeared'),
    ('BUSINESS_UPDATED',       'DATA',         'INFO',     1, 'REFERENCE', 'A business field changed'),
    ('BUSINESS_STATUS_CHANGED','VERIFICATION', 'NOTICE',   1, 'NONE',      'businesses.status moved'),
    ('BUSINESS_MERGED',        'DATA',         'CRITICAL', 1, 'NONE',      'Two business rows were merged'),
    ('CONTACT_CAPTURED',       'DATA',         'INFO',     1, 'MASKED',    'A contact point was stored'),
    ('CONTACT_VERIFIED',       'DATA',         'NOTICE',   1, 'MASKED',    'A human confirmed a contact'),
    ('CONTACT_DEACTIVATED',    'DATA',         'NOTICE',   1, 'MASKED',    'A contact was retired'),
    ('RESEARCH_STARTED',       'RESEARCH',     'INFO',     1, 'NONE',      'A research run began'),
    ('RESEARCH_COMPLETED',     'RESEARCH',     'NOTICE',   1, 'NONE',      'A research run finished'),
    ('RESEARCH_FAILED',        'RESEARCH',     'NOTICE',   1, 'NONE',      'A research run failed'),
    ('FINDING_STORED',         'RESEARCH',     'INFO',     0, 'NONE',      'A finding was written'),
    ('SOURCE_CAPTURED',        'RESEARCH',     'INFO',     0, 'NONE',      'A source was fetched and stored'),
    ('OPPORTUNITY_SCORED',     'RESEARCH',     'NOTICE',   1, 'NONE',      'An opportunity score was computed'),
    ('VERIFICATION_STARTED',   'VERIFICATION', 'INFO',     1, 'NONE',      'A checklist was opened'),
    ('VERIFICATION_SUBMITTED', 'VERIFICATION', 'CRITICAL', 1, 'NONE',      'A human signed a verification'),
    ('VERIFICATION_SUPERSEDED','VERIFICATION', 'NOTICE',   1, 'NONE',      'A verification was superseded'),
    ('SELECTION_CREATED',      'SELECTION',    'NOTICE',   1, 'NONE',      'A business was selected for outreach'),
    ('SELECTION_REMOVED',      'SELECTION',    'NOTICE',   1, 'NONE',      'A selection was withdrawn'),
    ('DRAFT_GENERATED',        'MESSAGE',      'NOTICE',   1, 'NONE',      'A message draft was generated'),
    ('DRAFT_EDITED',           'MESSAGE',      'NOTICE',   1, 'NONE',      'A draft was edited by a human'),
    ('POLICY_CHECK_PASSED',    'POLICY',       'INFO',     1, 'NONE',      'Claim policy check passed'),
    ('POLICY_CHECK_BLOCKED',   'POLICY',       'CRITICAL', 1, 'NONE',      'Claim policy check blocked a draft'),
    ('MESSAGE_PREVIEWED',      'APPROVAL',     'INFO',     1, 'MASKED',    'A preview was rendered'),
    ('MESSAGE_APPROVED',       'APPROVAL',     'CRITICAL', 1, 'MASKED',    'A human approved a message'),
    ('APPROVAL_REVOKED',       'APPROVAL',     'CRITICAL', 1, 'NONE',      'An approval was revoked'),
    ('MESSAGE_QUEUED',         'SEND',         'INFO',     1, 'NONE',      'A send job was enqueued'),
    ('MESSAGE_SENT',           'SEND',         'CRITICAL', 1, 'MASKED',    'A message was transmitted'),
    ('MESSAGE_FAILED',         'SEND',         'NOTICE',   1, 'NONE',      'A send failed permanently'),
    ('MESSAGE_CANCELLED',      'SEND',         'NOTICE',   1, 'NONE',      'A message was cancelled'),
    ('MESSAGE_BOUNCED',        'DELIVERY',     'NOTICE',   1, 'MASKED',    'A hard bounce was parsed'),
    ('RESPONSE_RECEIVED',      'RESPONSE',     'NOTICE',   1, 'MASKED',    'An inbound reply was stored'),
    ('RESPONSE_CLASSIFIED',    'RESPONSE',     'NOTICE',   1, 'NONE',      'A reply was classified'),
    ('RESPONSE_RECLASSIFIED',  'RESPONSE',     'NOTICE',   1, 'NONE',      'A human corrected a classification'),
    ('HANDOFF_CREATED',        'HANDOFF',      'CRITICAL', 1, 'NONE',      'A lead was handed to a human'),
    ('HANDOFF_ACKNOWLEDGED',   'HANDOFF',      'NOTICE',   1, 'NONE',      'A handoff was acknowledged'),
    ('HANDOFF_CLOSED',         'HANDOFF',      'NOTICE',   1, 'NONE',      'A handoff was closed'),
    ('SUPPRESSION_CREATED',    'SUPPRESSION',  'CRITICAL', 1, 'MASKED',    'An opt-out was recorded'),
    ('SUPPRESSION_RELEASED',   'SUPPRESSION',  'CRITICAL', 1, 'MASKED',    'A suppression was released manually'),
    ('POLICY_CHANGED',         'CONFIG',       'CRITICAL', 1, 'NONE',      'contact_policy was changed'),
    ('CONFIG_CHANGED',         'CONFIG',       'NOTICE',   1, 'NONE',      'A configuration value changed'),
    ('USER_CREATED',           'ACCESS',       'CRITICAL', 1, 'REFERENCE', 'A user account was created'),
    ('USER_LOGIN',             'ACCESS',       'INFO',     0, 'REFERENCE', 'A user logged in'),
    ('USER_LOGIN_FAILED',      'ACCESS',       'NOTICE',   0, 'REFERENCE', 'A login attempt failed'),
    ('REPORT_GENERATED',       'EXPORT',       'NOTICE',   1, 'NONE',      'A report was exported'),
    ('REPORT_DOWNLOADED',      'EXPORT',       'INFO',     0, 'NONE',      'A report file was downloaded'),
    ('DATA_ERASED',            'DATA',         'CRITICAL', 1, 'HASHED',    'A DPDP erasure was applied'),
    ('MIGRATION_APPLIED',      'SYSTEM',       'NOTICE',   0, 'NONE',      'A schema migration was applied'),
    ('SYSTEM_STARTED',         'SYSTEM',       'INFO',     0, 'NONE',      'The application started');
