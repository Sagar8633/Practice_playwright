-- ===========================================================================
-- 020_research.sql
-- Owner: radar/llm.py, radar/research.py, radar/score.py
-- Doc:   02-research-pipeline.md sections 2.3.1 - 2.3.4, 2.8, 2.10, 2.11 - 2.14, 2.16
-- ===========================================================================
-- 001_schema.sql created the six research tables. This migration applies the amendment
-- requests section 2.3 collects against them, and adds the one table the free-tier LLM
-- layer needs and nobody else owns.
--
-- Four of these are load-bearing rather than cosmetic:
--
--   sources.authority_tier   research_confidence (2.14.1) has no input without it, so every
--                            run would score the same confidence whether it read a
--                            government register or an aggregator page.
--   sources.redacted_sha256  nothing otherwise records what was actually put in front of the
--                            model, as opposed to what was fetched. The PII boundary of
--                            2.10.0 becomes unauditable.
--   finding_sources.excerpt_verified
--                            a 0 is a citation the model asserted and nothing confirmed.
--                            Without the column every citation looks verified.
--   opportunities.score nullable
--                            a NOT NULL score forces a fabricated 0 into the row that feeds
--                            the report when no signal was measurable, which is exactly the
--                            placeholder number _CONTEXT.md invariant 5 forbids.
--
-- Three tables are rebuilt rather than altered, because SQLite cannot widen a CHECK in
-- place: research_findings (the dimension vocabulary), opportunities (nullable score and
-- narrative) and opportunity_modules (the module vocabulary MODULE_MAP actually uses, plus
-- because_finding_id). All three are copied row by row, so this migration is correct on a
-- populated database as well as an empty one.

-- ---------------------------------------------------------------------------
-- 1. sources: provenance, redaction accounting and the injection quarantine
-- ---------------------------------------------------------------------------
ALTER TABLE sources ADD COLUMN authority_tier  TEXT NOT NULL DEFAULT 'C'
    CHECK (authority_tier IN ('A','B','C','D'));
ALTER TABLE sources ADD COLUMN redacted_sha256 TEXT;
ALTER TABLE sources ADD COLUMN redaction_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sources ADD COLUMN content_chars   INTEGER;
ALTER TABLE sources ADD COLUMN truncated       INTEGER NOT NULL DEFAULT 0
    CHECK (truncated IN (0,1));
ALTER TABLE sources ADD COLUMN trust           TEXT NOT NULL DEFAULT 'OK'
    CHECK (trust IN ('OK','SUSPECT','QUARANTINED'));
ALTER TABLE sources ADD COLUMN trust_reason    TEXT;

CREATE INDEX ix_sources_trust ON sources(trust) WHERE trust <> 'OK';
CREATE INDEX ix_sources_tier  ON sources(business_id, authority_tier);

-- ---------------------------------------------------------------------------
-- 2. finding_sources: was this citation checked, and in what order does it render
-- ---------------------------------------------------------------------------
ALTER TABLE finding_sources ADD COLUMN excerpt_verified INTEGER NOT NULL DEFAULT 0
    CHECK (excerpt_verified IN (0,1));
ALTER TABLE finding_sources ADD COLUMN ordinal INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------------------
-- 3. research_runs: what the validator threw away, and the second call's provenance
-- ---------------------------------------------------------------------------
ALTER TABLE research_runs ADD COLUMN sufficiency TEXT
    CHECK (sufficiency IS NULL OR sufficiency IN ('SUFFICIENT','THIN','INSUFFICIENT'));
ALTER TABLE research_runs ADD COLUMN integrity TEXT NOT NULL DEFAULT 'OK'
    CHECK (integrity IN ('OK','DEGRADED','QUARANTINED'));
ALTER TABLE research_runs ADD COLUMN rejection_detail      TEXT;
ALTER TABLE research_runs ADD COLUMN repair_attempts       INTEGER NOT NULL DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN n_findings_rejected   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN thinking_tokens       INTEGER;
ALTER TABLE research_runs ADD COLUMN cached_tokens         INTEGER;
ALTER TABLE research_runs ADD COLUMN web_searches          INTEGER NOT NULL DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN pages_fetched         INTEGER NOT NULL DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN pages_blocked         INTEGER NOT NULL DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN error_code            TEXT;
ALTER TABLE research_runs ADD COLUMN gather_model_id       TEXT;
ALTER TABLE research_runs ADD COLUMN gather_prompt_version TEXT;

-- One live run per business, enforced by the database rather than by a job dedupe key. It
-- spans PENDING because the duplicate this prevents is created at enqueue time.
CREATE UNIQUE INDEX ux_research_runs_live ON research_runs(business_id)
    WHERE status IN ('PENDING','RUNNING');

-- ---------------------------------------------------------------------------
-- 4. research_findings: signals, and the dimension union of 2.3.3
-- ---------------------------------------------------------------------------
-- The scorer reads every measured signal out of this table by key. Without signal_key it
-- would have to pattern-match on label, which is prose written by a model.
--
-- The dimension vocabulary is the union 2.3.3 asks 01-data-model.md to adopt: 001's ten
-- values are all kept, and LOCATION, CONTACT, REGULATORY, COMMERCIAL and INTEGRITY are
-- added. DIGITAL_PRESENCE stays the canonical spelling; radar/research.py maps the model's
-- DIGITAL_FOOTPRINT onto it on write, so nothing that already queries DIGITAL_PRESENCE
-- changes. INTEGRITY cannot be folded into OTHER without losing 2.9.5's alarm.
CREATE TABLE research_findings_v2 (
    id              TEXT PRIMARY KEY,
    business_id     TEXT NOT NULL REFERENCES businesses(id)    ON DELETE CASCADE,
    research_run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,

    kind            TEXT NOT NULL CHECK (kind IN ('OBSERVED','INFERRED','UNKNOWN')),

    dimension       TEXT NOT NULL
                      CHECK (dimension IN ('IDENTITY','LOCATION','SCALE','OPERATIONS',
                                           'DIGITAL_PRESENCE','SYSTEMS','STAFFING',
                                           'CUSTOMERS','FINANCE','COMPLIANCE','CONTACT',
                                           'REGULATORY','COMMERCIAL','INTEGRITY','OTHER')),
    label           TEXT NOT NULL CHECK (length(label) BETWEEN 3 AND 80),
    statement       TEXT NOT NULL CHECK (length(statement) BETWEEN 10 AND 600),
    detail          TEXT,

    confidence      TEXT NOT NULL DEFAULT 'MEDIUM'
                      CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct  INTEGER CHECK (confidence_pct IS NULL OR confidence_pct BETWEEN 0 AND 100),
    weight          REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0),

    derived_from    TEXT NOT NULL DEFAULT '[]',
    inference_note  TEXT,

    unknown_reason  TEXT CHECK (unknown_reason IS NULL OR unknown_reason IN
                      ('NOT_PUBLISHED','SOURCE_UNREACHABLE','AMBIGUOUS','OUT_OF_SCOPE',
                       'CONFLICTING_SOURCES')),

    -- New in 020. NULL when the finding is not a scored signal.
    signal_key      TEXT,
    signal_value    TEXT,

    is_current      INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
    ordinal         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (json_valid(derived_from)),
    CHECK (kind <> 'INFERRED' OR (json_array_length(derived_from) >= 1
                                  AND inference_note IS NOT NULL)),
    CHECK (kind <> 'UNKNOWN'  OR unknown_reason IS NOT NULL),
    CHECK (kind <> 'UNKNOWN'  OR confidence = 'LOW')
);

INSERT INTO research_findings_v2
    (id, business_id, research_run_id, kind, dimension, label, statement, detail,
     confidence, confidence_pct, weight, derived_from, inference_note, unknown_reason,
     is_current, ordinal, created_at)
SELECT
     id, business_id, research_run_id, kind, dimension, label, statement, detail,
     confidence, confidence_pct, weight, derived_from, inference_note, unknown_reason,
     is_current, ordinal, created_at
FROM research_findings;

-- 001's trigger on finding_sources names research_findings in its body, and SQLite reparses
-- every trigger when a table is dropped or renamed. It has to come off first and go back on
-- afterwards, unchanged.
DROP TRIGGER trg_finding_sources_no_orphan_observed;

DROP TABLE research_findings;
ALTER TABLE research_findings_v2 RENAME TO research_findings;

CREATE TRIGGER trg_finding_sources_no_orphan_observed
BEFORE DELETE ON finding_sources
FOR EACH ROW
WHEN (SELECT kind FROM research_findings WHERE id = OLD.finding_id) = 'OBSERVED'
 AND (SELECT COUNT(*) FROM finding_sources WHERE finding_id = OLD.finding_id) <= 1
BEGIN
    SELECT RAISE(ABORT,
      'an OBSERVED finding must keep at least one source (spec 12); re-type it INFERRED first');
END;

CREATE INDEX ix_findings_business_run ON research_findings(business_id, research_run_id, kind);
CREATE INDEX ix_findings_run_kind     ON research_findings(research_run_id, kind, ordinal);
CREATE INDEX ix_findings_current      ON research_findings(business_id, kind)
    WHERE is_current = 1;
CREATE INDEX ix_findings_signal       ON research_findings(business_id, signal_key)
    WHERE signal_key IS NOT NULL;

-- Recreated: it was attached to the table 001 declared and went with it.
CREATE TRIGGER trg_finding_promote_needs_source
BEFORE UPDATE OF kind ON research_findings
FOR EACH ROW
WHEN NEW.kind = 'OBSERVED' AND OLD.kind <> 'OBSERVED'
 AND NOT EXISTS (SELECT 1 FROM finding_sources WHERE finding_id = NEW.id)
BEGIN
    SELECT RAISE(ABORT, 'cannot promote a finding to OBSERVED with no source (spec 12)');
END;

-- 2.3.3's two additions. The first is safety invariant 4 at the moment a run completes.
CREATE TRIGGER trg_research_run_complete_sourced
BEFORE UPDATE OF status ON research_runs
FOR EACH ROW
WHEN NEW.status = 'COMPLETE'
 AND EXISTS (
     SELECT 1 FROM research_findings f
      WHERE f.research_run_id = NEW.id
        AND f.kind = 'OBSERVED'
        AND NOT EXISTS (SELECT 1 FROM finding_sources fs WHERE fs.finding_id = f.id))
BEGIN
    SELECT RAISE(ABORT, 'OBSERVED finding without a source in a completing research run');
END;

CREATE TRIGGER trg_unknown_finding_has_no_source
BEFORE INSERT ON finding_sources
FOR EACH ROW
WHEN (SELECT kind FROM research_findings WHERE id = NEW.finding_id) = 'UNKNOWN'
BEGIN
    SELECT RAISE(ABORT, 'UNKNOWN findings do not carry sources');
END;

-- ---------------------------------------------------------------------------
-- 5. opportunities: nullable score, coverage, signals, the assess call's provenance
-- ---------------------------------------------------------------------------
CREATE TABLE opportunities_v2 (
    id                     TEXT PRIMARY KEY,
    business_id            TEXT NOT NULL REFERENCES businesses(id)    ON DELETE CASCADE,
    research_run_id        TEXT REFERENCES research_runs(id),
    campaign_id            TEXT REFERENCES campaigns(id),

    -- Nullable since 020. NULL means "we could not measure enough to say this", which the
    -- report renders as an em dash. A placeholder sentence reaches a real hospital.
    potential_problem      TEXT,
    potential_solution     TEXT,
    expected_benefit       TEXT,
    refusal_reason         TEXT,

    score                  INTEGER CHECK (score IS NULL OR score BETWEEN 0 AND 100),
    band                   TEXT CHECK (band IS NULL OR band IN ('HIGH','MEDIUM','LOW')),
    confidence             TEXT NOT NULL DEFAULT 'MEDIUM'
                             CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct         INTEGER CHECK (confidence_pct IS NULL
                             OR confidence_pct BETWEEN 0 AND 100),

    digital_maturity       INTEGER CHECK (digital_maturity IS NULL
                             OR digital_maturity BETWEEN 0 AND 100),
    operational_complexity INTEGER CHECK (operational_complexity IS NULL
                             OR operational_complexity BETWEEN 0 AND 100),

    digital_coverage_pct     INTEGER CHECK (digital_coverage_pct IS NULL
                               OR digital_coverage_pct BETWEEN 0 AND 100),
    operational_coverage_pct INTEGER CHECK (operational_coverage_pct IS NULL
                               OR operational_coverage_pct BETWEEN 0 AND 100),
    score_coverage_pct       INTEGER CHECK (score_coverage_pct IS NULL
                               OR score_coverage_pct BETWEEN 0 AND 100),

    score_breakdown        TEXT NOT NULL DEFAULT '{}',
    signals_json           TEXT NOT NULL DEFAULT '[]',
    weights_version        TEXT NOT NULL DEFAULT 'sw-1',

    est_value_inr          INTEGER CHECK (est_value_inr IS NULL OR est_value_inr >= 0),
    est_value_basis        TEXT,

    model_id               TEXT,
    prompt_version         TEXT,
    input_tokens           INTEGER,
    output_tokens          INTEGER,
    quota_requests         INTEGER NOT NULL DEFAULT 0,
    assessed_at            TEXT,

    computed_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    is_current             INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
    superseded_by          TEXT REFERENCES opportunities_v2(id),

    CHECK (json_valid(score_breakdown)),
    CHECK (json_valid(signals_json)),
    -- The bands, enforced rather than trusted to the scorer.
    CHECK (score IS NULL OR (band IS NOT NULL AND (
              (band = 'HIGH'   AND score >= 80)
           OR (band = 'MEDIUM' AND score BETWEEN 60 AND 79)
           OR (band = 'LOW'    AND score < 60)))),
    CHECK (band IS NULL OR score IS NOT NULL),
    -- A narrative half exists only when a model call produced it, and that call's provenance
    -- is recorded beside it. potential_problem and expected_benefit stay nullable even then:
    -- 2.10.5 requires the model to null them and give a refusal_reason rather than invent one.
    CHECK (assessed_at IS NULL OR (model_id IS NOT NULL AND prompt_version IS NOT NULL
                                   AND potential_solution IS NOT NULL))
);

INSERT INTO opportunities_v2
    (id, business_id, research_run_id, campaign_id, potential_problem, potential_solution,
     expected_benefit, score, band, confidence, confidence_pct, digital_maturity,
     operational_complexity, score_breakdown, est_value_inr, est_value_basis, model_id,
     prompt_version, computed_at, is_current, superseded_by)
SELECT
     id, business_id, research_run_id, campaign_id, potential_problem, potential_solution,
     expected_benefit, score, band, confidence, confidence_pct, digital_maturity,
     operational_complexity, score_breakdown, est_value_inr, est_value_basis, model_id,
     prompt_version, computed_at, is_current, superseded_by
FROM opportunities;

CREATE TABLE opportunity_modules_v2 (
    id             TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities_v2(id) ON DELETE CASCADE,
    business_id    TEXT NOT NULL REFERENCES businesses(id)       ON DELETE CASCADE,
    -- 001's 31 keys, plus the 20 MODULE_MAP (06-message-engine.md 6.8.1) uses for the five
    -- categories spec 26 does not enumerate. A module key outside this list is a bug in the
    -- map rather than a new module.
    module         TEXT NOT NULL
                     CHECK (module IN ('DASHBOARD','WORKFLOW','FINANCE','INVENTORY','REPORTS',
                                       'ROLE_MANAGEMENT','AUDIT_LOGS','PATIENTS','APPOINTMENTS',
                                       'DEPARTMENTS','BILLING','STUDENTS','FEES','ATTENDANCE',
                                       'STAFF','TRANSPORT','ADMISSIONS','EXAMINATIONS',
                                       'PRODUCTION','PURCHASING','SALES','QUALITY','ORDERS',
                                       'CUSTOMERS','RECEIVABLES','DELIVERY','PAYMENTS',
                                       'VARIANTS','PROFITABILITY','EXPENSES','PROFIT',
                                       'ROLES','AUDIT','PURCHASES','TEST_ORDERS','SAMPLES',
                                       'JOB_CARDS','SPARES','LABOUR','ROOMS','BOOKINGS',
                                       'GUESTS','HOUSEKEEPING','TABLES','MENU','LISTINGS',
                                       'ENQUIRIES','SITE_VISITS','CLIENTS','ENGAGEMENTS',
                                       'DOCUMENTS')),
    ordinal        INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    rationale      TEXT,
    -- A module recommended for no recorded reason is the unsourced claim invariant 4 stops.
    because_finding_id TEXT REFERENCES research_findings(id) ON DELETE SET NULL,
    is_current     INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),

    UNIQUE (opportunity_id, module)
);

INSERT INTO opportunity_modules_v2
    (id, opportunity_id, business_id, module, ordinal, rationale, is_current)
SELECT id, opportunity_id, business_id, module, ordinal, rationale, is_current
FROM opportunity_modules;

-- The child goes first: dropping the parent while the child still holds rows pointing at it
-- would fail the foreign key check.
DROP TABLE opportunity_modules;
DROP TABLE opportunities;

ALTER TABLE opportunities_v2       RENAME TO opportunities;
ALTER TABLE opportunity_modules_v2 RENAME TO opportunity_modules;

CREATE UNIQUE INDEX ux_opportunities_current ON opportunities(business_id) WHERE is_current = 1;
CREATE INDEX ix_opportunities_current  ON opportunities(business_id) WHERE is_current = 1;
CREATE INDEX ix_opportunities_score    ON opportunities(score DESC)  WHERE is_current = 1;
CREATE INDEX ix_opportunities_history  ON opportunities(business_id, computed_at DESC);
CREATE INDEX ix_opportunities_campaign ON opportunities(campaign_id, is_current);

CREATE INDEX ix_modules_business ON opportunity_modules(business_id, ordinal)
    WHERE is_current = 1;
CREATE INDEX ix_modules_module   ON opportunity_modules(module);

-- ---------------------------------------------------------------------------
-- 6. llm_quota_ledger - requests, not rupees (2.16)
-- ---------------------------------------------------------------------------
-- On the free tier the scarce resource is the request. This is the row that decides whether
-- the next research job runs today or waits for the quota window to roll over, and it is
-- written in the same transaction that records the model's output, so a call that happened
-- and a call that was counted cannot come apart.
--
-- quota_day is the PACIFIC date, because Google AI Studio's daily allowance resets at
-- midnight America/Los_Angeles. report_day is the IST date, because every number Sagar reads
-- is IST. Both are stored: they are different days on purpose, and conflating them is how a
-- campaign appears to have quota it does not have.
CREATE TABLE llm_quota_ledger (
    id             TEXT PRIMARY KEY,                    -- run_...
    at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    quota_day      TEXT NOT NULL,                       -- YYYY-MM-DD, America/Los_Angeles
    report_day     TEXT NOT NULL,                       -- YYYY-MM-DD, Asia/Kolkata

    purpose        TEXT NOT NULL
                     CHECK (purpose IN ('RESEARCH','ASSESS','GATHER','MESSAGE','CLASSIFY',
                                        'REPAIR','OTHER')),
    model_id       TEXT NOT NULL,
    prompt_version TEXT NOT NULL,

    business_id    TEXT REFERENCES businesses(id),
    campaign_id    TEXT REFERENCES campaigns(id),
    entity_table   TEXT,
    entity_id      TEXT,

    requests        INTEGER NOT NULL DEFAULT 1 CHECK (requests        >= 0),
    input_tokens    INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens    >= 0),
    output_tokens   INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens   >= 0),
    thinking_tokens INTEGER NOT NULL DEFAULT 0 CHECK (thinking_tokens >= 0),
    cached_tokens   INTEGER NOT NULL DEFAULT 0 CHECK (cached_tokens   >= 0),

    outcome        TEXT NOT NULL DEFAULT 'OK'
                     CHECK (outcome IN ('OK','QUOTA','ERROR','INVALID')),
    latency_ms     INTEGER,
    error_code     TEXT,

    CHECK (at LIKE '____-__-__T__:__:__Z'),
    CHECK (quota_day  LIKE '____-__-__'),
    CHECK (report_day LIKE '____-__-__')
);

CREATE INDEX ix_quota_day      ON llm_quota_ledger(quota_day, purpose);
CREATE INDEX ix_quota_report   ON llm_quota_ledger(report_day);
CREATE INDEX ix_quota_business ON llm_quota_ledger(business_id, at);

-- ---------------------------------------------------------------------------
-- 7. audit actions this pipeline raises
-- ---------------------------------------------------------------------------
INSERT INTO audit_actions (action, domain, severity, user_visible, pii_class, description)
VALUES
    ('SOURCE_INJECTION_SUSPECTED', 'RESEARCH', 'CRITICAL', 1, 'NONE',
     'A fetched page carried instruction-like content and was quarantined'),
    ('RESEARCH_DEGRADED',          'RESEARCH', 'CRITICAL', 1, 'NONE',
     'A research run failed validation badly enough to be marked DEGRADED'),
    ('LLM_QUOTA_EXHAUSTED',        'SYSTEM',   'NOTICE',   1, 'NONE',
     'The daily free-tier request ceiling was reached and work was deferred');
