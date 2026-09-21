# 5. Outreach workflow and eligibility gates

This document settles everything that happens between the moment Sagar ticks the last box on a
verification screen and the moment a message physically leaves the machine. It defines the nine-step
pipeline (SELECT -> PREPARE OUTREACH -> DRAFT -> POLICY CHECK -> PREVIEW -> APPROVE -> QUEUE -> SEND
-> RECORD), the DDL and state machine for `selections`, `outreach_drafts`, `outreach_messages`,
`outreach_approvals`, `outreach_events`, `suppressions` and `contact_policy`, and — the part
everything else hangs off — a single eligibility engine, `check_send_eligibility()`, that answers
"may we contact this business, on this channel, through this contact, right now?" with a structured
per-gate pass/block. It covers spec §18, §19, §20, §21, §27, §28, §29, §30, §31, §32, §40, §45, §46.

**Cross-references.** `01-data-model.md` carries the canonical schema file; where this document
prints DDL for a table it owns, that DDL is the definition and `01-data-model.md` must match it
byte-for-byte. Tables owned elsewhere (`businesses`, `business_contacts`, `verifications`,
`verification_checks`, `research_findings`, `sources`, `opportunities`, `responses`, `handoffs`,
`jobs`, `audit_log`) appear here only as a "columns this document depends on" contract. Message
generation (§22–§26) belongs to the message-template document; response classification (§33) and
human handoff (§34–§35) belong to the response document; the report itself (§5–§14, §36–§44) belongs
to the report document. Those are referenced by spec section rather than filename because the pack
numbering beyond `01-data-model.md` is not fixed in `_CONTEXT.md`.

---

## 5.1 The rule this document exists to enforce

Spec §45, restated as an implementable invariant:

> There is exactly one code path that causes a message to be transmitted. It is
> `radar.outreach.send_message(conn, message_id, approval_id, *, worker_id)`. It will not run
> without an `approval_id` that resolves to a live row in `outreach_approvals`, and the database
> refuses to record `outreach_messages.status = 'SENT'` unless that row exists, is unrevoked, and
> its `approved_body_hash` equals the bytes about to be sent.

Everything in this document is either a step that produces that row, or a gate that stops the step
from producing it.

Three consequences, stated once here and enforced throughout:

| Consequence | Enforced by |
|---|---|
| §19 — no SEND control exists on raw research output | There is no endpoint that accepts a `business_id` and transmits. The only transmit endpoints take a `message_id` that already carries an approval. The exported HTML report contains no forms and no fetch calls (see §5.19) |
| §3 invariant 1 — no send without a human approval **row** | `outreach_messages.approval_id` FK + `trg_om_send_needs_approval` trigger + `ApprovalId` NewType whose only constructor reads `outreach_approvals` |
| §3 invariant 2 — `SENT` only from `APPROVED` | `outreach_status_transitions` table + `trg_om_transition` trigger; there is no `('QUEUED','SENT')`... there is, but no `('DRAFT','SENT')`, `('PENDING_APPROVAL','SENT')` or `('POLICY_BLOCKED','SENT')` |

---

## 5.2 The pipeline

```
                                     ┌───────────────────────────────────────────┐
                                     │  businesses.status = CONTACT_READY        │
                                     │  (VERIFIED + a human-verified contact)    │
                                     └────────────────────┬──────────────────────┘
                                                          │
   1. SELECT ............................................ │ ...... selections row (SELECTED)
      /campaigns/<id> grid, checkbox per row              │        eligibility snapshot @SELECT
                                                          ▼
   2. PREPARE OUTREACH .................................. selections.state = PREPARED
      POST /api/v1/outreach/prepare                       jobs row: type='draft_outreach'
                                                          ▼
   3. DRAFT ............................................. outreach_drafts row (out_...)
      radar/messages.py, gemini-2.5-flash                 outreach_messages row: DRAFT
                                                          ▼
   4. POLICY CHECK ...................................... outreach_drafts.policy_result
      radar/policy.py claim check (§12 / §23)             status: PENDING_APPROVAL | POLICY_BLOCKED
                                                          ▼
   5. PREVIEW ........................................... outreach_events: PREVIEWED
      GET /outreach/<draft_id>, nine panels (§27)         preview_token issued (10 min TTL)
      check_send_eligibility(stage=PREVIEW)               eligibility rendered as a panel
                                                          ▼
   6. APPROVE ........................................... outreach_approvals row (apr_...)
      "CONFIRM & SEND" (§28)                              status: APPROVED
      human web session only                              audit_log row
                                                          ▼
   7. QUEUE ............................................. status: QUEUED
      jobs row: type='send_email'                         outreach_events: QUEUED
                                                          ▼
   8. SEND .............................................. BEGIN IMMEDIATE
      radar/channels/<channel>.py                         check_send_eligibility(stage=SEND)  ← the race closer
                                                          outreach_events: SEND_ATTEMPT
                                                          provider call (outside the write txn)
                                                          status: SENT | FAILED
                                                          ▼
   9. RECORD ............................................ businesses.status = CONTACTED
                                                          outreach_events: SENT
                                                          audit_log row (§48)
                                                          selections.state = DISPATCHED
                                                          campaign counters recomputed
```

### 5.2.1 Step table

| # | Step | Actor | UI route | API | Rows written | `outreach_messages.status` after | `businesses.status` after |
|---|---|---|---|---|---|---|---|
| 1 | SELECT | Human | `/campaigns/<id>` | `POST /api/v1/selections` | `selections`, `audit_log` | — (no message row yet) | unchanged (`CONTACT_READY`) |
| 2 | PREPARE OUTREACH | Human starts, system runs | `/outreach` | `POST /api/v1/outreach/prepare` | `jobs`, `selections` (state) | — | unchanged |
| 3 | DRAFT | System (LLM) | `/outreach` | (job) | `outreach_drafts`, `outreach_messages`, `outreach_events(DRAFTED)` | `DRAFT` | unchanged |
| 4 | POLICY CHECK | System | — | (job) | `outreach_drafts` (policy cols), `outreach_events(POLICY_PASS\|POLICY_BLOCK)` | `PENDING_APPROVAL` or `POLICY_BLOCKED` | unchanged |
| 5 | PREVIEW | Human | `/outreach/<draft_id>` | `GET .../preview` | `outreach_events(PREVIEWED)` | unchanged | unchanged |
| 6 | APPROVE | Human | `/outreach/<draft_id>` | `POST .../approve` | `outreach_approvals`, `outreach_events(APPROVED)`, `audit_log` | `APPROVED` | unchanged |
| 7 | QUEUE | System | — | (same request) | `jobs`, `outreach_events(QUEUED)` | `QUEUED` | unchanged |
| 8 | SEND | System worker | — | (job) | `outreach_messages` (provider cols), `outreach_events(SEND_ATTEMPT, SENT\|PROVIDER_ERROR)` | `SENT` or stays `QUEUED` (retry) or `FAILED` | — |
| 9 | RECORD | System | — | (same job) | `businesses`, `selections`, `audit_log`, `campaigns` counters | `SENT` | `CONTACTED` |
| 10 | (later) inbound poll | System worker | — | (job `poll_inbox`) | `outreach_events`, `outreach_messages`, sometimes `suppressions` | `BOUNCED` on a parsed DSN; otherwise unchanged | unchanged |

There is no step 10 webhook. `_CONTEXT.md` §2 puts this process on `127.0.0.1`, so nothing on the
public internet can POST to it: the only inbound path is `poll_inbox` reading the Gmail mailbox over
IMAP (`07-email-integration.md` §7.8, §7.9; `14-background-jobs.md` §14.8.13). SMTP acceptance is not
delivery and no `DELIVERED` event exists on this stack — an accepted, un-bounced email stays `SENT`
(`14` §14.8.14). `DELIVERED` remains a legal `outreach_messages.status` value because `_CONTEXT.md`
§6 fixes the enum and the WhatsApp Cloud API path (`08-whatsapp-integration.md`) can still reach it.

Steps 6 and 7 happen inside one HTTP request and one DB transaction: approving *is* queueing. There
is no "approved but not queued" resting state a background process could pick up on its own, and no
"queued but never approved" state at all.

### 5.2.2 Where each channel diverges

| Channel | Steps 1–7 | Step 8 | Step 9 |
|---|---|---|---|
| `EMAIL` | identical | system submits over SMTP to `smtp.gmail.com:587` (`07-email-integration.md` §7.3.5) | as above |
| `WHATSAPP` (no opt-in) | identical | system renders a `wa.me` link and marks the message awaiting manual dispatch | Sagar clicks the link, sends in WhatsApp, then confirms — `POST .../record-manual` writes `SENT` |
| `WHATSAPP` (recorded opt-in, Cloud API enabled) | identical | system calls the WhatsApp Cloud API with an approved template | as email |
| `PHONE` | identical, but the "message" is a call script | system never dials; the message parks awaiting a logged call | `POST .../record-manual` with call outcome writes `SENT` |
| `MANUAL` | steps 1–2 only; draft optional | none | `POST .../record-manual` creates the message already `APPROVED` -> `SENT` in one transaction, with an approval row Sagar signs |

See §5.6 for why each channel is shaped this way.

---

## 5.3 The outreach schema

Full DDL for the tables this document owns. `PRAGMA foreign_keys = ON` and
`PRAGMA journal_mode = WAL` are set by `radar/db.py` on every connection. All timestamps are UTC
ISO-8601 `YYYY-MM-DDTHH:MM:SSZ`.

### 5.3.1 `contact_policy` (§31, §46)

```sql
-- radar/migrations/010_contact_policy.sql
CREATE TABLE contact_policy (
    id                        TEXT PRIMARY KEY,            -- 'GLOBAL' or a cmp_... id
    scope                     TEXT NOT NULL
                                CHECK (scope IN ('GLOBAL','CAMPAIGN')),
    campaign_id               TEXT REFERENCES campaigns(id) ON DELETE CASCADE,

    -- §46 automation mode
    automation_mode           TEXT NOT NULL DEFAULT 'HUMAN_APPROVAL'
                                CHECK (automation_mode IN
                                       ('MANUAL','HUMAN_APPROVAL','SEMI_AUTOMATED','FULLY_AUTOMATED')),

    -- §31 contact frequency
    min_days_between_outreach INTEGER NOT NULL DEFAULT 21
                                CHECK (min_days_between_outreach >= 0),
    max_attempts              INTEGER NOT NULL DEFAULT 3   CHECK (max_attempts >= 1),
    max_followups             INTEGER NOT NULL DEFAULT 2   CHECK (max_followups >= 0),
    stop_after_rejection      INTEGER NOT NULL DEFAULT 1   CHECK (stop_after_rejection IN (0,1)),
    stop_after_opt_out        INTEGER NOT NULL DEFAULT 1   CHECK (stop_after_opt_out IN (0,1)),

    -- §29 duplicate windows
    recent_campaign_days      INTEGER NOT NULL DEFAULT 90  CHECK (recent_campaign_days >= 0),
    same_domain_days          INTEGER NOT NULL DEFAULT 30  CHECK (same_domain_days >= 0),
    same_domain_max           INTEGER NOT NULL DEFAULT 1   CHECK (same_domain_max >= 1),

    -- verification freshness
    verification_valid_days   INTEGER NOT NULL DEFAULT 30
                                CHECK (verification_valid_days >= 1),

    -- approval and pacing
    approval_ttl_minutes      INTEGER NOT NULL DEFAULT 60
                                CHECK (approval_ttl_minutes >= 1),
    send_min_gap_seconds      INTEGER NOT NULL DEFAULT 45
                                CHECK (send_min_gap_seconds >= 0),

    -- sending-account protection (_CONTEXT §4: one free Gmail account, no custom domain)
    daily_send_cap            INTEGER NOT NULL DEFAULT 25  CHECK (daily_send_cap >= 0),
    warmup_started_on         TEXT,                        -- date the sending account first sent
    warmup_schedule           TEXT NOT NULL DEFAULT '[5,5,10,10,15,15,20,20,25]',  -- JSON, per day
    bounce_rate_window_days   INTEGER NOT NULL DEFAULT 30,
    bounce_rate_max_pct       REAL    NOT NULL DEFAULT 5.0,
    complaint_rate_max_pct    REAL    NOT NULL DEFAULT 0.1,
    bounce_rate_min_sample    INTEGER NOT NULL DEFAULT 20,

    -- channel switches
    email_enabled             INTEGER NOT NULL DEFAULT 1 CHECK (email_enabled IN (0,1)),
    email_sending_domain      TEXT,                        -- 'gmail.com'; see the note below
    whatsapp_enabled          INTEGER NOT NULL DEFAULT 1 CHECK (whatsapp_enabled IN (0,1)),
    whatsapp_api_enabled      INTEGER NOT NULL DEFAULT 0 CHECK (whatsapp_api_enabled IN (0,1)),
    phone_enabled             INTEGER NOT NULL DEFAULT 1 CHECK (phone_enabled IN (0,1)),
    manual_enabled            INTEGER NOT NULL DEFAULT 1 CHECK (manual_enabled IN (0,1)),

    policy_version            TEXT NOT NULL DEFAULT 'cp-1',
    updated_at                TEXT NOT NULL
                                DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_by                TEXT REFERENCES users(id),

    CHECK ((scope = 'GLOBAL'   AND campaign_id IS NULL)
        OR (scope = 'CAMPAIGN' AND campaign_id IS NOT NULL))
);

CREATE UNIQUE INDEX ux_contact_policy_campaign
    ON contact_policy(campaign_id) WHERE campaign_id IS NOT NULL;

INSERT INTO contact_policy (id, scope) VALUES ('GLOBAL', 'GLOBAL');

-- v1 refuses to store an automation mode it cannot honour. Dropped by the migration that
-- actually implements a non-human approval source; see §5.20.
CREATE TRIGGER trg_contact_policy_v1_mode
BEFORE INSERT ON contact_policy
WHEN NEW.automation_mode IN ('SEMI_AUTOMATED','FULLY_AUTOMATED')
BEGIN
    SELECT RAISE(ABORT, 'automation_mode SEMI_AUTOMATED/FULLY_AUTOMATED is not implemented in v1');
END;

CREATE TRIGGER trg_contact_policy_v1_mode_upd
BEFORE UPDATE OF automation_mode ON contact_policy
WHEN NEW.automation_mode IN ('SEMI_AUTOMATED','FULLY_AUTOMATED')
BEGIN
    SELECT RAISE(ABORT, 'automation_mode SEMI_AUTOMATED/FULLY_AUTOMATED is not implemented in v1');
END;
```

**`email_sending_domain` on the free stack.** The column keeps its name — `01-data-model.md` §1.14.2
references it and a rename costs a migration for one row — but its meaning changed with
`_CONTEXT.md` §4. There is no custom domain: the from-address is a dedicated free Gmail account, so
the value is always `gmail.com` and the real configuration is `identity.from_address` in
`config/.env` (`07-email-integration.md` §7.3.8). The column survives as the deliberate on-switch
that gate H5 (§5.9.10) reads — a freshly migrated database has it `NULL` and cannot mail anybody by
accident. It is not a reputation asset. gmail.com's reputation is Google's, inherited rather than
earned, and the only thing this system can damage is the one account, which is exactly why
`_CONTEXT.md` §4 puts outreach on an account Sagar can abandon.

Resolution order: a `CAMPAIGN`-scoped row overrides the `GLOBAL` row **field by field only where the
campaign row is stricter**. A campaign may never loosen a global limit.

```python
def effective_policy(conn: sqlite3.Connection, campaign_id: str | None) -> ContactPolicy:
    """GLOBAL merged with the campaign override, taking the stricter value per field.

    A campaign that wants to email every 7 days when GLOBAL says 21 does not get to.
    Stricter means: larger for min_days_between_outreach / recent_campaign_days /
    same_domain_days / verification_valid_days-inverse; smaller for max_attempts /
    max_followups / daily_send_cap / same_domain_max; 1 for the stop_after_* flags;
    0 for the *_enabled flags.
    """
```

### 5.3.2 `suppressions` (§30)

```sql
-- radar/migrations/011_suppressions.sql
CREATE TABLE suppressions (
    id                TEXT PRIMARY KEY,                   -- sup_...
    scope             TEXT NOT NULL
                        CHECK (scope IN ('BUSINESS','EMAIL','PHONE','WHATSAPP','DOMAIN')),
    value_norm        TEXT NOT NULL,                      -- DISPLAY ONLY; see §5.3.2.1
    business_id       TEXT REFERENCES businesses(id),     -- nullable: a domain block spans businesses
    reason            TEXT NOT NULL
                        CHECK (reason IN ('UNSUBSCRIBE_LINK','REPLY_OPT_OUT','COMPLAINT',
                                          'BOUNCE_HARD','MANUAL','DNC_LIST','LEGAL_REQUEST')),
    source            TEXT NOT NULL,                      -- human-readable provenance
    source_ref        TEXT,                               -- rsp_/msg_/aud_ id where applicable
    detail            TEXT,                               -- JSON: verbatim evidence
    created_at        TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_by        TEXT REFERENCES users(id),          -- NULL when written by the inbox poller

    released_at       TEXT,                               -- NULL forever, in the application
    released_by       TEXT REFERENCES users(id),
    released_audit_id TEXT REFERENCES audit_log(id)
);

CREATE UNIQUE INDEX ux_suppressions_scope_value ON suppressions(scope, value_norm);
CREATE INDEX ix_suppressions_business        ON suppressions(business_id);
CREATE INDEX ix_suppressions_live            ON suppressions(scope, value_norm) WHERE released_at IS NULL;

-- Invariant 3: opt-out is permanent and the app cannot clear it. Releasing requires a manual
-- DB session AND a matching audit row, which the app has no code to create.
CREATE TRIGGER trg_suppressions_release_needs_audit
BEFORE UPDATE OF released_at ON suppressions
WHEN NEW.released_at IS NOT NULL
 AND (NEW.released_audit_id IS NULL
      OR NOT EXISTS (SELECT 1 FROM audit_log a
                     WHERE a.id = NEW.released_audit_id
                       AND a.action = 'SUPPRESSION_RELEASED'
                       AND a.entity_id = NEW.id))
BEGIN
    SELECT RAISE(ABORT, 'releasing a suppression requires an audit_log SUPPRESSION_RELEASED row');
END;

CREATE TRIGGER trg_suppressions_no_delete
BEFORE DELETE ON suppressions
BEGIN
    SELECT RAISE(ABORT, 'suppressions are append-only');
END;
```

### 5.3.2.1 `value_hmac` is the identity; `value_norm` is a label

`11-audit-architecture.md` §11.12.3 adds two columns to this table by additive migration, and they
change what "look up a suppression" means everywhere in this document. Reproduced here because every
query below depends on it — `11` owns the migration and its text wins:

```sql
-- radar/migrations/039_suppression_hmac.sql   (owned by 11-audit-architecture.md §11.12.3)
ALTER TABLE suppressions ADD COLUMN value_hmac TEXT;   -- 64 hex, HMAC-SHA256(pepper, value_norm)
ALTER TABLE suppressions ADD COLUMN erased_at  TEXT;

CREATE UNIQUE INDEX ux_suppressions_scope_hmac
    ON suppressions(scope, value_hmac) WHERE value_hmac IS NOT NULL;
CREATE INDEX ix_suppressions_hmac_live
    ON suppressions(scope, value_hmac) WHERE released_at IS NULL;

CREATE TRIGGER trg_suppressions_hmac_required
BEFORE INSERT ON suppressions
WHEN NEW.value_hmac IS NULL OR length(NEW.value_hmac) <> 64
BEGIN
    SELECT RAISE(ABORT, 'suppressions.value_hmac is required');
END;
```

**Why this document cares.** A DPDP erasure (`11` §11.12.5) overwrites `value_norm` with
`'#erased:' || substr(value_hmac,1,32)` and leaves the row otherwise intact. Every gate in this
document that matched on `value_norm` stops matching at that moment. The failure is not abstract:

| Step | What happens | Under a `value_norm` join |
|---|---|---|
| 1 | A recipient unsubscribes | `suppressions(scope='EMAIL', value_norm='owner@example-sample.in')` |
| 2 | The same person asks for erasure — the request an angry unsubscriber is most likely to make next | `value_norm` becomes `'#erased:9f13...'` |
| 3 | A later campaign rediscovers the business and writes a fresh `business_contacts` row with the real address | — |
| 4 | Gate A runs | **returns nothing. We send a second cold email to the one person guaranteed to forward it to a lawyer, with an audit trail showing we held their opt-out and mailed them anyway** |

The `scope='BUSINESS'` fan-out row does not save it. An unattributable unsubscribe carries
`business_id IS NULL` (`07-email-integration.md` §7.7.9 case 6), so the `EMAIL`-scope row is the only
block that exists.

Therefore, in this document and everywhere downstream of it:

| Rule | |
|---|---|
| The join key is `value_hmac` | `value_norm` is display only, and after an erasure it is not even that |
| `suppression_hmac()` is computed in **Python**, never in SQL | SQLite has no HMAC function. Every query below receives pre-computed 64-hex point hashes as bound parameters |
| `is_suppressed()` (`11` §11.12.3) is the single lookup implementation | Both documents call it. This document does not carry a second one |
| The pepper is `SUPPRESSION_HMAC_PEPPER` in `config/.env` | Rotating it silently unblocks everybody, so it is the one secret with no rotation procedure: `12-security-model.md` §12.5 |

`radar/policy.py` contains exactly one write against this table:

```python
def suppress(conn, *, scope: str, value_norm: str, business_id: str | None,
             reason: str, source: str, source_ref: str | None,
             detail: dict[str, Any] | None = None) -> str:
    """Record an opt-out. Idempotent: an existing live row for (scope, value_hmac) wins.

    Computes value_hmac = suppression_hmac(value_norm) and writes BOTH columns. It is not
    optional: trg_suppressions_hmac_required ABORTs an insert without a 64-char hash, so a
    suppress() that forgot it would raise on every automatic opt-out - unsubscribe mail,
    STOP reply, hard bounce, classifier OPT_OUT - which is the one failure mode where an
    exception and a silent no-op look identical from the outside.

    There is no `unsuppress`. There never will be one in this file. Clearing an opt-out is a
    psql/sqlite3 session, a written reason, and an audit row - which is the point: the code
    cannot be talked into it by a UI bug or a stray API call.
    """
```

Rows are written automatically by: the inbox poller when it recognises an unsubscribe mail
(`UNSUBSCRIBE_LINK`, `07-email-integration.md` §7.7.5), the response classifier when
`responses.classification = 'OPT_OUT'` or `'COMPLAINT'` (`REPLY_OPT_OUT` / `COMPLAINT`), and the
inbox poller again when it parses a hard-bounce DSN (`BOUNCE_HARD`, `07` §7.9.6). Sagar can add one
by hand from `/business/<id>` (`MANUAL`). All four paths go through `suppress()`, so all four write
`value_hmac`.

### 5.3.3 `selections` (§18)

```sql
-- radar/migrations/012_selections.sql
CREATE TABLE selections (
    id                   TEXT PRIMARY KEY,                -- sel_...
    campaign_id          TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    business_id          TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    city                 TEXT NOT NULL,                   -- copied from businesses.city at select time
    industry             TEXT NOT NULL,                   -- copied, so the counts survive a re-classify
    state                TEXT NOT NULL DEFAULT 'SELECTED'
                           CHECK (state IN ('SELECTED','PREPARED','DISPATCHED','BLOCKED','REMOVED')),
    intent_channel       TEXT
                           CHECK (intent_channel IS NULL OR
                                  intent_channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),
    sequence_no          INTEGER NOT NULL DEFAULT 1 CHECK (sequence_no >= 1),
    parent_message_id    TEXT REFERENCES outreach_messages(id),
    eligibility_snapshot TEXT NOT NULL,                   -- JSON Eligibility at SELECT stage
    eligible_at_select   INTEGER NOT NULL CHECK (eligible_at_select IN (0,1)),
    blocking_gate        TEXT,
    note                 TEXT,
    selected_by          TEXT NOT NULL REFERENCES users(id),
    selected_at          TEXT NOT NULL
                           DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    removed_by           TEXT REFERENCES users(id),
    removed_at           TEXT,
    updated_at           TEXT NOT NULL
                           DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- One live selection per business per campaign. A removed selection is kept for the audit trail.
CREATE UNIQUE INDEX ux_selections_live
    ON selections(campaign_id, business_id) WHERE state <> 'REMOVED';
CREATE INDEX ix_selections_campaign_city ON selections(campaign_id, city, state);
CREATE INDEX ix_selections_business      ON selections(business_id);
```

### 5.3.4 `outreach_drafts`

The message-template document owns the content columns (`subject`, `body`, personalisation inputs,
`facts_used`). This document owns the lifecycle columns and prints the whole table so the FK graph is
readable in one place.

```sql
-- radar/migrations/013_outreach_drafts.sql
CREATE TABLE outreach_drafts (
    id                TEXT PRIMARY KEY,                   -- out_...
    business_id       TEXT NOT NULL REFERENCES businesses(id),
    campaign_id       TEXT NOT NULL REFERENCES campaigns(id),
    selection_id      TEXT REFERENCES selections(id),
    contact_id        TEXT REFERENCES business_contacts(id),
    channel           TEXT NOT NULL
                        CHECK (channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),
    sequence_no       INTEGER NOT NULL DEFAULT 1 CHECK (sequence_no >= 1),
    parent_message_id TEXT REFERENCES outreach_messages(id),

    subject           TEXT,                               -- NULL for WHATSAPP/PHONE
    body              TEXT NOT NULL,                      -- as generated
    body_edited       TEXT,                               -- as edited by Sagar, NULL if untouched
    edited_by         TEXT REFERENCES users(id),
    edited_at         TEXT,
    edit_count        INTEGER NOT NULL DEFAULT 0,

    -- §49 AI message audit
    model_id          TEXT NOT NULL,                      -- e.g. 'gemini-2.5-flash'
    prompt_version    TEXT NOT NULL,                      -- e.g. 'msg-email-v3'
    input_tokens      INTEGER,
    output_tokens     INTEGER,
    facts_used        TEXT NOT NULL,                      -- JSON array of research_findings ids (OBSERVED)
    inferences_used   TEXT NOT NULL,                      -- JSON array of research_findings ids (INFERRED)
    ai_confidence     TEXT CHECK (ai_confidence IN ('HIGH','MEDIUM','LOW')),
    ai_confidence_pct INTEGER CHECK (ai_confidence_pct BETWEEN 0 AND 100),

    -- step 4
    policy_result     TEXT CHECK (policy_result IN ('PASS','WARN','BLOCK')),
    policy_detail     TEXT,                               -- JSON: violations, each with finding id
    policy_version    TEXT,
    policy_checked_at TEXT,

    created_at        TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_by        TEXT REFERENCES users(id),          -- who pressed PREPARE OUTREACH
    superseded_by     TEXT REFERENCES outreach_drafts(id) -- set when regenerated
);

CREATE INDEX ix_drafts_business  ON outreach_drafts(business_id, channel, sequence_no);
CREATE INDEX ix_drafts_campaign  ON outreach_drafts(campaign_id, created_at);
```

`final_body` is always `COALESCE(body_edited, body)`. Nothing else may compute it.

### 5.3.5 `outreach_messages`

```sql
-- radar/migrations/014_outreach_messages.sql
CREATE TABLE outreach_messages (
    id                   TEXT PRIMARY KEY,                -- msg_...
    draft_id             TEXT NOT NULL REFERENCES outreach_drafts(id),
    business_id          TEXT NOT NULL REFERENCES businesses(id),
    campaign_id          TEXT NOT NULL REFERENCES campaigns(id),
    contact_id           TEXT REFERENCES business_contacts(id),
    channel              TEXT NOT NULL
                           CHECK (channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),
    status               TEXT NOT NULL DEFAULT 'DRAFT'
                           CHECK (status IN ('DRAFT','POLICY_BLOCKED','PENDING_APPROVAL','APPROVED',
                                             'QUEUED','SENT','DELIVERED','BOUNCED','FAILED','CANCELLED')),
    approval_id          TEXT REFERENCES outreach_approvals(id),

    sequence_no          INTEGER NOT NULL DEFAULT 1 CHECK (sequence_no >= 1),
    parent_message_id    TEXT REFERENCES outreach_messages(id),
    thread_key           TEXT NOT NULL,                   -- business_id||':'||channel||':'||to_address_norm

    to_address_norm      TEXT,                            -- lowercase email / E.164 / wa_id
    to_address_dedupe    TEXT,                            -- looser key used by gate F2; see 5.9.2
    to_address_display   TEXT,                            -- what Sagar was shown
    recipient_domain     TEXT,                            -- eTLD+1 for EMAIL, NULL otherwise
    subject_final        TEXT,
    body_final           TEXT,
    body_hash            TEXT,                            -- sha256 hex of subject_final||'\x1e'||body_final

    idempotency_key      TEXT NOT NULL,
    provider             TEXT,                            -- 'gmail' | 'null' | 'wa_cloud' | 'manual_wa' | 'manual'
    provider_message_id  TEXT,                            -- EMAIL: our own derive_message_id(); 07 §7.10.2
    provider_status_code INTEGER,                         -- EMAIL: the SMTP reply code
    provider_response    TEXT,                            -- JSON, truncated to 4 KB
    provider_send_started_at TEXT,                        -- written before the transport call; see 5.10.2

    queued_at            TEXT,
    sent_at              TEXT,
    delivered_at         TEXT,
    failed_at            TEXT,
    cancelled_at         TEXT,
    failure_code         TEXT,
    failure_detail       TEXT,
    attempt_count        INTEGER NOT NULL DEFAULT 0,
    next_retry_at        TEXT,

    eligibility_snapshot TEXT,                            -- JSON Eligibility at SEND stage
    policy_override      INTEGER NOT NULL DEFAULT 0
                           CHECK (policy_override IN (0,1)),   -- record-manual acknowledgement, 5.6.3
    sent_by              TEXT REFERENCES users(id),       -- §32 "Sender": the approving human
    worker_id            TEXT,                            -- which worker performed the transmit

    created_at           TEXT NOT NULL
                           DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at           TEXT NOT NULL
                           DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- A message that has reached or passed APPROVED must carry its approval.
    CHECK (status NOT IN ('APPROVED','QUEUED','SENT','DELIVERED','BOUNCED')
           OR approval_id IS NOT NULL),
    CHECK (status <> 'SENT'   OR sent_at   IS NOT NULL),
    CHECK (status <> 'FAILED' OR failure_code IS NOT NULL),
    CHECK (channel <> 'EMAIL' OR status IN ('DRAFT','POLICY_BLOCKED','CANCELLED')
           OR subject_final IS NOT NULL)
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
```

### 5.3.6 `outreach_approvals`

```sql
-- radar/migrations/015_outreach_approvals.sql
CREATE TABLE outreach_approvals (
    id                   TEXT PRIMARY KEY,                -- apr_...
    message_id           TEXT NOT NULL REFERENCES outreach_messages(id) ON DELETE CASCADE,
    draft_id             TEXT NOT NULL REFERENCES outreach_drafts(id),
    business_id          TEXT NOT NULL REFERENCES businesses(id),
    contact_id           TEXT REFERENCES business_contacts(id),
    channel              TEXT NOT NULL
                           CHECK (channel IN ('EMAIL','WHATSAPP','PHONE','MANUAL')),

    approved_by          TEXT NOT NULL REFERENCES users(id),
    approved_at          TEXT NOT NULL
                           DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- proof that a human browser session, not a machine token, created this row
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
    confirmation_text    TEXT NOT NULL,                   -- the §28 sentence, stored verbatim
    displayed            TEXT NOT NULL,                   -- JSON: the seven §28 items as rendered
    eligibility_snapshot TEXT NOT NULL,                   -- JSON Eligibility at APPROVE stage
    preview_token        TEXT NOT NULL,
    idempotency_key      TEXT NOT NULL,                   -- the confirm nonce from the preview form

    revoked_at           TEXT,
    revoked_by           TEXT REFERENCES users(id),
    revoke_reason        TEXT
);

CREATE UNIQUE INDEX ux_approvals_live_message
    ON outreach_approvals(message_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX ux_approvals_idem ON outreach_approvals(idempotency_key);
CREATE INDEX ix_approvals_business    ON outreach_approvals(business_id, approved_at);
```

`session_auth_method` is the type-level barrier. The API-token authenticator used by the job worker
and the CLI cannot mint a session, so it cannot supply a legal value for this column; the approve
endpoint is registered only on the session-authenticated Flask blueprint. See §5.20.

### 5.3.7 `outreach_events`

```sql
-- radar/migrations/016_outreach_events.sql
CREATE TABLE outreach_events (
    id                TEXT PRIMARY KEY,                   -- evt_...
    message_id        TEXT NOT NULL REFERENCES outreach_messages(id) ON DELETE CASCADE,
    event             TEXT NOT NULL CHECK (event IN (
                          'DRAFTED','EDITED','POLICY_PASS','POLICY_BLOCK','PREVIEWED',
                          'ELIGIBILITY_BLOCK','APPROVED','APPROVAL_REVOKED','QUEUED',
                          'SEND_ATTEMPT','SENT','PROVIDER_ERROR','RATE_LIMITED','INDETERMINATE',
                          'DELIVERED','BOUNCED','COMPLAINED','OPENED','CLICKED','UNSUBSCRIBED',
                          'FAILED','CANCELLED','MANUAL_RECORDED','CALL_LOGGED')),
    at                TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    actor_type        TEXT NOT NULL CHECK (actor_type IN ('HUMAN','SYSTEM','PROVIDER')),
    actor_id          TEXT,                               -- users.id, worker id, or provider name
    detail            TEXT,                               -- JSON
    provider_event_id TEXT                                -- provider's own event id, for dedupe
);

CREATE INDEX ix_events_message ON outreach_events(message_id, at);
CREATE UNIQUE INDEX ux_events_provider_event
    ON outreach_events(provider_event_id) WHERE provider_event_id IS NOT NULL;
```

`provider_event_id` is the inbound dedupe key. There are no webhooks on this stack (`_CONTEXT.md`
§2), so the writer is `poll_inbox`: it sets `provider_event_id` to the inbound mail's own
`Message-ID`, and re-reading the same DSN or unsubscribe mail after a crash produces one row and one
status change. The column keeps its name because the WhatsApp Cloud API path (`08-whatsapp-integration.md`),
if it is ever enabled, does have provider event ids and needs the same index.

### 5.3.8 The state machine

```sql
-- radar/migrations/017_outreach_status_transitions.sql
CREATE TABLE outreach_status_transitions (
    from_status TEXT NOT NULL,
    to_status   TEXT NOT NULL,
    note        TEXT NOT NULL,
    PRIMARY KEY (from_status, to_status)
);

INSERT INTO outreach_status_transitions (from_status, to_status, note) VALUES
    ('DRAFT',            'PENDING_APPROVAL', 'claim policy check passed'),
    ('DRAFT',            'POLICY_BLOCKED',   'claim policy check failed'),
    ('DRAFT',            'CANCELLED',        'Sagar discarded the draft'),
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
    ('SENT',             'DELIVERED',        'WhatsApp Cloud API delivery receipt; unreachable on EMAIL'),
    ('SENT',             'BOUNCED',          'poll_inbox parsed a hard-bounce DSN'),
    ('SENT',             'FAILED',           'async rejection after acceptance'),
    ('DELIVERED',        'BOUNCED',          'late hard bounce after a delivery event');

CREATE TRIGGER trg_om_transition
BEFORE UPDATE OF status ON outreach_messages
WHEN NEW.status <> OLD.status
 AND NOT EXISTS (SELECT 1 FROM outreach_status_transitions t
                 WHERE t.from_status = OLD.status AND t.to_status = NEW.status)
BEGIN
    SELECT RAISE(ABORT, 'illegal outreach_messages.status transition');
END;

-- Invariant 1 and invariant 4, in the database.
CREATE TRIGGER trg_om_send_needs_approval
BEFORE UPDATE OF status ON outreach_messages
WHEN NEW.status = 'SENT'
 AND (NEW.approval_id IS NULL
      OR NOT EXISTS (SELECT 1 FROM outreach_approvals a
                     WHERE a.id = NEW.approval_id
                       AND a.message_id = NEW.id
                       AND a.revoked_at IS NULL
                       AND a.approved_body_hash = NEW.body_hash
                       AND a.approved_to_address = NEW.to_address_norm))
BEGIN
    SELECT RAISE(ABORT,
      'SENT requires a live approval whose body hash and address match what is being sent');
END;

CREATE TRIGGER trg_om_touch
AFTER UPDATE ON outreach_messages
BEGIN
    UPDATE outreach_messages
       SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.id;
END;
```

Reading the transition table: there is no path from `DRAFT`, `POLICY_BLOCKED` or
`PENDING_APPROVAL` to `SENT`, and no path out of `SENT`/`DELIVERED`/`BOUNCED`/`FAILED`/`CANCELLED`
back into the drafting states. A retry is a **new** message row with `sequence_no` unchanged and a
new `idempotency_key`, not a resurrection.

`('SENT','DELIVERED')` stays in the table but is **dead on the email channel**. SMTP acceptance is not
delivery and no DSN says "delivered", so an accepted, un-bounced email stays `SENT` for good
(`14-background-jobs.md` §14.8.14, `07-email-integration.md` §7.9.5). The row survives because
`_CONTEXT.md` §6 fixes `DELIVERED` in the status enum and the WhatsApp Cloud API path can still reach
it. Anywhere a delivery state is rendered for an email, `03-html-report.md` shows `—` rather than
"unknown" — invariant 5 applied to a column that will never be populated.

### 5.3.9 Id prefixes used here

| Table | Prefix | Source |
|---|---|---|
| `outreach_drafts` | `out_` | `_CONTEXT.md` §2 |
| `outreach_messages` | `msg_` | `_CONTEXT.md` §2 |
| `audit_log` | `aud_` | `_CONTEXT.md` §2 |
| `responses` | `rsp_` | `_CONTEXT.md` §2 |
| `selections` | `sel_` | extension, see Open questions |
| `outreach_approvals` | `apr_` | extension |
| `outreach_events` | `evt_` | extension |
| `suppressions` | `sup_` | extension |
| `business_contacts` | `cnt_` | extension |

---

## 5.4 Step 1 — SELECT (§18, §19)

### 5.4.1 The selectability predicate

§18 says "Only businesses with VERIFIED and CONTACT_READY can be selected". `businesses.status` is
one column and cannot hold both values at once, so the two words describe a sequence, not a
conjunction:

```
AI_RESEARCHED -> NEEDS_VERIFICATION -> VERIFIED -> CONTACT_READY -> CONTACTED -> ...
                                          │
                                          └─ promoted automatically the moment the business
                                             has at least one business_contacts row with
                                             human_verified = 1 and is_active = 1
```

`CONTACT_READY` is therefore *strictly stronger* than `VERIFIED`: it is reachable only from
`VERIFIED`, and it means "verified, and there is a human-confirmed contact to write to". The
selectable set is:

| `businesses.status` | Selectable for first touch | Selectable for follow-up | Reason shown when greyed |
|---|---|---|---|
| `AI_RESEARCHED` | no | no | "Research has not been reviewed yet." |
| `NEEDS_VERIFICATION` | no | no | "This business still needs your verification." |
| `VERIFIED` | no | no | "Verified, but no confirmed contact yet — add or confirm a contact." |
| `CONTACT_READY` | **yes** | n/a | — |
| `REJECTED` | no | no | "You rejected this business on {date}." |
| `SKIPPED` | no | no | "You skipped this business on {date}." |
| `CONTACTED` | no | yes, if frequency gates pass | frequency gate reason |
| `RESPONDED` | no | yes, if the reply was not a rejection | response gate reason |
| `INTERESTED` | no | **no** | "This is a live lead — the machine stops here and you take it." |
| `HUMAN_HANDOFF` | no | **no** | "This lead is with you, not the system." |

`INTERESTED` and `HUMAN_HANDOFF` being unselectable is spec §55 in one line: once a business is
genuinely interested, automated preparation stops and Sagar handles it personally.

The promotion `VERIFIED -> CONTACT_READY` is performed by:

```python
def promote_contact_ready(conn: sqlite3.Connection, business_id: str) -> bool:
    """Move a VERIFIED business to CONTACT_READY once a human has confirmed a contact.

    Called from the verification save path and from the contact editor. Returns True if the
    status changed. Never demotes: a contact deleted later is caught by gate E1 at send time.
    """
```

### 5.4.2 The grid query

`GET /api/v1/campaigns/<campaign_id>/selectable` drives the checkbox column of the report table
(§9). It returns one row per business with `selectable`, `blocking_gate` and `block_reason`, so the
UI greys out with a real reason rather than a generic tooltip.

**Before the query runs**, `radar/outreach.py` fills a temp table of contact-point hashes, because
suppression is matched on `value_hmac` (§5.3.2.1) and SQLite has no HMAC function:

```python
# radar/outreach.py :: build_point_hmacs()
conn.execute("""CREATE TEMP TABLE IF NOT EXISTS point_hmac (
                    business_id TEXT NOT NULL,
                    scope       TEXT NOT NULL,
                    value_hmac  TEXT NOT NULL)""")
conn.execute("DELETE FROM point_hmac")
rows = conn.execute(POINTS_FOR_CAMPAIGN_SQL, {"campaign_id": campaign_id}).fetchall()
conn.executemany(
    "INSERT INTO point_hmac (business_id, scope, value_hmac) VALUES (?,?,?)",
    [(r["business_id"], r["scope"], policy.suppression_hmac(r["value_norm"])) for r in rows],
)
```

`POINTS_FOR_CAMPAIGN_SQL` emits one row per point per business in the campaign: the `BUSINESS` point
(`scope='BUSINESS'`, `value_norm = b.id`), one `EMAIL` / `PHONE` / `WHATSAPP` point per
`business_contacts` row, and one `DOMAIN` point per distinct non-null `business_contacts.domain`. The
hashing is a few hundred `hmac.new()` calls per grid load, which is nothing; doing it in SQL is not
an option and doing it per-row in a correlated subquery would be.

```sql
-- radar/outreach.py :: SELECTABLE_GRID_SQL
-- Bulk, one pass, for a whole campaign. Parameters:
--   :campaign_id, :now, :recent_cutoff, :min_days_cutoff, :verif_cutoff,
--   :max_attempts, :max_followups, :domain_cutoff, :same_domain_max
-- Precondition: temp.point_hmac has been filled for :campaign_id by build_point_hmacs().
WITH live_contact AS (
    SELECT c.business_id,
           MAX(CASE WHEN c.kind='EMAIL'    THEN 1 ELSE 0 END) AS has_email,
           MAX(CASE WHEN c.kind='PHONE'    THEN 1 ELSE 0 END) AS has_phone,
           MAX(CASE WHEN c.kind='WHATSAPP' THEN 1 ELSE 0 END) AS has_whatsapp,
           COUNT(*)                                            AS n_contacts
      FROM business_contacts c
     WHERE c.human_verified = 1 AND c.is_active = 1
     GROUP BY c.business_id
),
suppressed AS (
    -- Joined on value_hmac, never on value_norm: after a DPDP erasure value_norm reads
    -- '#erased:<hash-prefix>' and a plaintext join silently stops matching. §5.3.2.1.
    SELECT DISTINCT p.business_id
      FROM point_hmac p
      JOIN suppressions s
        ON s.scope = p.scope
       AND s.value_hmac = p.value_hmac
       AND s.released_at IS NULL
),
verif AS (
    SELECT v.business_id, MAX(v.verified_at) AS verified_at
      FROM verifications v
     WHERE v.verdict = 'VERIFIED' AND v.superseded_at IS NULL
     GROUP BY v.business_id
),
sent AS (
    SELECT m.business_id,
           COUNT(*)                                              AS attempts,
           SUM(CASE WHEN m.sequence_no > 1 THEN 1 ELSE 0 END)     AS followups,
           MAX(m.sent_at)                                         AS last_sent_at
      FROM outreach_messages m
     WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
     GROUP BY m.business_id
),
stopper AS (
    SELECT r.business_id, MIN(r.received_at) AS at, r.classification
      FROM responses r
     WHERE r.classification IN ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE',
                                'WRONG_CONTACT','OPT_OUT','COMPLAINT')
     GROUP BY r.business_id
),
inflight AS (
    SELECT m.business_id, COUNT(*) AS n
      FROM outreach_messages m
     WHERE m.status IN ('PENDING_APPROVAL','APPROVED','QUEUED')
     GROUP BY m.business_id
)
SELECT b.id                AS business_id,
       b.name, b.city, b.industry, b.category, b.size_band, b.status,
       o.score             AS opportunity_score,
       o.confidence        AS research_confidence,
       COALESCE(lc.n_contacts, 0) AS n_contacts,
       COALESCE(lc.has_email, 0)  AS has_email,
       COALESCE(lc.has_phone, 0)  AS has_phone,
       COALESCE(lc.has_whatsapp, 0) AS has_whatsapp,
       sel.id              AS selection_id,
       CASE
         WHEN sup.business_id IS NOT NULL                       THEN 'A_SUPPRESSED'
         WHEN b.status IN ('INTERESTED','HUMAN_HANDOFF')        THEN 'D_HUMAN_OWNED'
         WHEN b.status IN ('REJECTED','SKIPPED')                THEN 'D_VERIFICATION_REVOKED'
         WHEN b.status NOT IN ('CONTACT_READY','CONTACTED','RESPONDED')
                                                                THEN 'D_NOT_VERIFIED'
         WHEN v.verified_at IS NULL                             THEN 'D_NOT_VERIFIED'
         WHEN v.verified_at < :verif_cutoff                     THEN 'D_VERIFICATION_STALE'
         WHEN COALESCE(lc.n_contacts,0) = 0                     THEN 'E_CONTACT_MISSING'
         WHEN st.business_id IS NOT NULL                        THEN 'G_STOP_AFTER_REJECTION'
         WHEN COALESCE(s.attempts,0)  >= :max_attempts          THEN 'G_MAX_ATTEMPTS'
         WHEN COALESCE(s.followups,0) >= :max_followups
              AND COALESCE(s.attempts,0) > 0                    THEN 'G_MAX_FOLLOWUPS'
         WHEN s.last_sent_at IS NOT NULL
              AND s.last_sent_at > :min_days_cutoff             THEN 'G_MIN_DAYS'
         WHEN COALESCE(inf.n,0) > 0                             THEN 'F_IN_FLIGHT'
         ELSE NULL
       END                 AS blocking_gate,
       s.last_sent_at, s.attempts, s.followups,
       st.classification   AS stop_classification, st.at AS stop_at
  FROM campaign_businesses cb
  JOIN businesses          b   ON b.id = cb.business_id
  LEFT JOIN opportunities  o   ON o.business_id  = b.id AND o.is_current = 1
  LEFT JOIN live_contact   lc  ON lc.business_id = b.id
  LEFT JOIN suppressed     sup ON sup.business_id = b.id
  LEFT JOIN verif          v   ON v.business_id  = b.id
  LEFT JOIN sent           s   ON s.business_id  = b.id
  LEFT JOIN stopper        st  ON st.business_id = b.id
  LEFT JOIN inflight       inf ON inf.business_id = b.id
  LEFT JOIN selections     sel ON sel.business_id = b.id
                              AND sel.campaign_id = :campaign_id
                              AND sel.state <> 'REMOVED'
 WHERE cb.campaign_id = :campaign_id
   AND cb.state = 'INCLUDED'
 ORDER BY b.city, b.industry, o.score DESC;
```

`businesses` has no `campaign_id` column. `01-data-model.md` §1.2.2 makes `businesses` one row per
real business and `campaign_businesses` the many-to-many link, and the join above is that document's
worked rewrite of this query. Nothing else in §5.9 changes: every gate keys on `business_id`, and
gate F1 ("recent campaign") gets *stronger*, because a prior campaign's messages now hang off the
same `business_id` instead of a second row.

The grid query is a **fast approximation** of `check_send_eligibility()`. It deliberately omits the
per-contact, per-channel gates (E3, F2–F5, H*, I*) because they need a chosen contact and channel,
which the grid does not have. It never says "selectable" where the full engine would say "blocked"
for the gates it does evaluate; a business the grid allows can still be blocked at preview or send
time, and that is expected. See §5.10.

### 5.4.3 Selecting

```http
POST /api/v1/selections
Content-Type: application/json

{
  "campaign_id": "cmp_01JB2X8P0000000000000001",
  "business_ids": ["biz_01JB...A1", "biz_01JB...A2", "biz_01JB...A3"],
  "intent_channel": "EMAIL"
}
```

Response (SAMPLE):

```json
{
  "campaign_id": "cmp_01JB2X8P0000000000000001",
  "created": [
    {"selection_id": "sel_01JB...S1", "business_id": "biz_01JB...A1", "city": "DHULE"},
    {"selection_id": "sel_01JB...S2", "business_id": "biz_01JB...A2", "city": "NASHIK"}
  ],
  "rejected": [
    {"business_id": "biz_01JB...A3",
     "blocking_gate": "A_SUPPRESSED_EMAIL",
     "reason": "The email address contact@example-sample.in opted out on 2026-06-14, so no email can be sent to it."}
  ],
  "counts": {"DHULE": 5, "NASHIK": 7, "JALGAON": 3, "_total": 15}
}
```

Rules:

1. Selection is per `(campaign_id, business_id)`, enforced by `ux_selections_live`. Re-selecting an
   already-selected business is a no-op returning the existing `selection_id`, not an error.
2. Every selection runs `check_send_eligibility(stage=SELECT)` and stores the whole `Eligibility`
   JSON in `selections.eligibility_snapshot`. A business that fails a **hard** gate is not inserted
   at all; it comes back in `rejected` with the one-sentence reason.
3. A business that only fails a **soft/WARN** gate is inserted with `eligible_at_select = 0` and
   `blocking_gate` set, so the workspace can show it in an "attention" band rather than silently
   dropping it.
4. `city` and `industry` are copied into the row. If a later re-classification moves a business from
   `RETAIL` to `DISTRIBUTION`, the per-city counts Sagar saw when he selected do not silently change
   under him.
5. Deselect is `DELETE /api/v1/selections/<selection_id>`: it sets `state='REMOVED'`,
   `removed_at`, `removed_by`. Rows are never deleted — §48 wants the trail of what was considered.

### 5.4.4 Per-city selection counts (§18)

The header chip on `/campaigns/<id>` and `/outreach` reads "Dhule 5 · Nashik 7 · Jalgaon 3 = 15
selected" (SAMPLE). It comes from one aggregate, never from a Python counter:

```sql
-- radar/outreach.py :: SELECTION_COUNTS_SQL
SELECT s.city,
       COUNT(*)                                                        AS selected,
       SUM(CASE WHEN s.state = 'PREPARED'   THEN 1 ELSE 0 END)         AS prepared,
       SUM(CASE WHEN s.state = 'DISPATCHED' THEN 1 ELSE 0 END)         AS dispatched,
       SUM(CASE WHEN s.eligible_at_select = 0 THEN 1 ELSE 0 END)       AS needs_attention
  FROM selections s
 WHERE s.campaign_id = :campaign_id
   AND s.state <> 'REMOVED'
 GROUP BY s.city
 ORDER BY s.city;
```

Per `_CONTEXT.md` invariant 5: a city with no selections renders `—`, not `0`, in the summary strip;
`0` is reserved for "we counted and the answer is zero", which is what the aggregate returns for a
city that has businesses but none selected.

### 5.4.5 §19 in the code

| Surface | What exists | What does not exist |
|---|---|---|
| `/campaigns/<id>` research grid | `VIEW`, `RESEARCH`, `VERIFY`, `REJECT`, `SELECT`, `HISTORY` | any control that transmits |
| Exported HTML report | the same actions as deep links back into the live app | `<form>`, `fetch()`, any POST target |
| `/outreach` workspace | `PREPARE OUTREACH`, channel picker, draft list | a send control |
| `/outreach/<draft_id>` | `CONFIRM & SEND`, enabled only per §5.13 | — |
| API | `POST /api/v1/outreach/drafts/<draft_id>/approve` | no endpoint accepting `business_id` that transmits |

The endpoint audit is a test:

```python
def test_no_endpoint_sends_from_a_business_id(app):
    """A route that takes business_id must not be able to reach the transmit path.

    Walks the Flask url_map, and for every rule whose arguments include 'business_id',
    asserts that radar.outreach.send_message is not reachable from its view function's
    call graph. This test is the machine-readable form of spec §19.
    """
```

---

## 5.5 Step 2 — PREPARE OUTREACH, and the workspace screen (§20)

### 5.5.1 The action

```http
POST /api/v1/outreach/prepare
{
  "campaign_id": "cmp_01JB...01",
  "selection_ids": ["sel_01JB...S1", "sel_01JB...S2"],
  "channel": "EMAIL",
  "depth": "STANDARD"
}
-> 202 {"batch_id": "job_01JB...B7", "queued": 2, "skipped": 0}
```

This enqueues one `jobs` row per selection (`kind = 'draft_outreach'`), grouped under a `batch_id`.
Selections move to `state = 'PREPARED'`. Drafting is asynchronous because it is an LLM call per
business; the workspace polls `GET /api/v1/outreach/batches/<batch_id>`.

Before enqueueing, `check_send_eligibility(stage=SELECT)` runs once more per selection. A business
that has become ineligible since selection (an opt-out arrived overnight) is skipped, its selection
moves to `state='BLOCKED'` with `blocking_gate` set, and it appears in the workspace's "blocked since
you selected them" band. This is deliberately not silent: a disappearing row is how a person stops
trusting the tool.

### 5.5.2 The workspace screen `/outreach`

Left rail: the selection list grouped by city, with the per-city counts from §5.4.4. Main area: one
business at a time, seven panels, in this order.

| # | Panel | Data source | Empty state |
|---|---|---|---|
| 1 | Selected Business | `businesses` + `campaign_cities` | never empty |
| 2 | Research Summary | `research_runs` + `research_findings` grouped by `kind` | "Research produced no findings" (blocks gate C2) |
| 3 | **Why was this selected** | see §5.5.3 | never empty — if it would be, the business is not selectable |
| 4 | Potential software opportunity | `opportunities` | "No opportunity scored" (blocks gate C3) |
| 5 | Recommended solution | `opportunities.potential_solution`, `expected_benefit` | `—` |
| 6 | Recommended modules | `opportunity_modules` | `—` |
| 7 | Available contact channels | `business_contacts` + per-channel eligibility | "No confirmed contact" (blocks gate E1) |

### 5.5.3 "Why was this selected" — the rule

This panel is the one place where the system is most tempted to lie, so it has a hard rule:

> **Every sentence in this panel is a column value or a count from a SQL query. No LLM call runs at
> render time. No text is paraphrased, re-summarised or re-worded. If a string on this screen is not
> traceable to a row id printed next to it, that is a bug.**

The panel renders four blocks, each with the row ids visible (in a monospace muted style, so the
provenance is on screen without shouting):

**(a) What Sagar himself ticked.** Verbatim from `verification_checks`, including the free-text note.

```sql
SELECT vc.check_key, vc.passed, vc.note,
       v.id AS verification_id, v.verified_at, u.display_name AS verified_by
  FROM verifications v
  JOIN verification_checks vc ON vc.verification_id = v.id
  JOIN users u ON u.id = v.verified_by
 WHERE v.business_id = :business_id
   AND v.verdict = 'VERIFIED'
   AND v.superseded_at IS NULL
 ORDER BY vc.ordinal;
```

**(b) The findings the score was built from.** Verbatim `research_findings.statement`, grouped by
`kind`, each with its sources.

```sql
SELECT f.id            AS finding_id,
       f.kind,                       -- OBSERVED | INFERRED | UNKNOWN
       f.statement,                  -- rendered verbatim, never re-worded
       f.confidence,                 -- HIGH | MEDIUM | LOW
       f.confidence_pct,
       f.dimension,                  -- e.g. DIGITAL_MATURITY, OPERATIONAL_COMPLEXITY
       s.id            AS source_id,
       s.name          AS source_name,
       s.url           AS source_url,
       s.source_type,
       s.checked_at
  FROM research_findings f
  LEFT JOIN finding_sources fs ON fs.finding_id = f.id
  LEFT JOIN sources         s  ON s.id = fs.source_id
 WHERE f.business_id = :business_id
   AND f.research_run_id = (SELECT r.id FROM research_runs r
                             WHERE r.business_id = :business_id
                               AND r.status = 'COMPLETE'
                             ORDER BY r.finished_at DESC LIMIT 1)
 ORDER BY CASE f.kind WHEN 'OBSERVED' THEN 0 WHEN 'INFERRED' THEN 1 ELSE 2 END,
          f.confidence_pct DESC;
```

Rendering rules for this block, which the message policy engine also depends on:

| `kind` | Rendered as | May be cited in a message |
|---|---|---|
| `OBSERVED` | plain statement + source links | yes, as a statement of fact |
| `INFERRED` | statement prefixed "Inferred:" + the sources it was inferred from | only hedged ("may", "could", "we believe") |
| `UNKNOWN` | statement, greyed, marked "Not verified" | **never** |

A finding with no `finding_sources` row renders with a "no source" badge and is excluded from the
citable set regardless of `kind`. `_CONTEXT.md` invariant 4 depends on this.

**(c) The score, decomposed.** From the stored breakdown, not recomputed:

```sql
SELECT o.id, o.score, o.band, o.confidence, o.confidence_pct,
       o.digital_maturity, o.operational_complexity,
       o.potential_problem, o.potential_solution, o.expected_benefit,
       o.score_breakdown,        -- JSON: [{"component":"...","points":..,"of":..,"because_finding_id":"..."}]
       o.model_id, o.prompt_version, o.computed_at
  FROM opportunities o
 WHERE o.business_id = :business_id AND o.is_current = 1;
```

Each component of `score_breakdown` carries `because_finding_id`, so the panel can render
"Operational complexity 22/25 — because finding `res_...` (OBSERVED): *four departments listed on
the About page*". If a component has no `because_finding_id`, it renders with the component name and
points and no justification line; it does not invent one.

**(d) The selection filters that let it through.** From `campaigns` (min score, size band, industry
filter) and `selections`:

```sql
SELECT c.name, c.min_opportunity_score, c.size_filter, c.industries, c.research_depth,
       s.selected_at, s.eligible_at_select, s.blocking_gate,
       u.display_name AS selected_by
  FROM selections s
  JOIN campaigns c ON c.id = s.campaign_id
  JOIN users u     ON u.id = s.selected_by
 WHERE s.id = :selection_id;
```

**SAMPLE render** of the panel (labelled SAMPLE; no part of this is a real business):

```
WHY WAS THIS SELECTED                                        SAMPLE

You verified it on 2026-08-24 09:12 UTC (ver_01JB...V4), ticking all nine checks.
Your note: "Website lists four departments and a 40-bed capacity."

Findings the score used
  OBSERVED  res_01JB...F1  conf 90  "The website lists four clinical departments."
                                     source: Practice website (site) checked 2026-08-23
  OBSERVED  res_01JB...F2  conf 85  "No online appointment booking is present on the site."
                                     source: Practice website (site) checked 2026-08-23
  INFERRED  res_01JB...F3  conf 60  "Appointment scheduling is likely handled by phone."
                                     inferred from: res_01JB...F2
  UNKNOWN   res_01JB...F4  conf 30  "Current billing software is unknown."   [not verified]

Opportunity 86 (HIGH), confidence MEDIUM 64
  Digital maturity 62 · Operational complexity 78
  Departments breadth        22/25   because res_01JB...F1
  Booking gap                20/25   because res_01JB...F2
  Size band (MEDIUM)         18/20   —
  Public contact present     16/20   because cnt_01JB...C1
  Website quality            10/10   because res_01JB...F1

Campaign filter: min score 70, size MEDIUM+LARGE, industries ALL.
Selected by Sagar on 2026-08-26 07:41 UTC.
```

`GET /api/v1/outreach/workspace/<business_id>?campaign_id=...&channel=EMAIL` returns exactly this
data as JSON; the Jinja template and the JSON share one query module so the screen and the API can
never drift.

---

## 5.6 Step 2c — Channel selection (§21)

§21 says: Email, WhatsApp, Phone, Manual; focus on email and *official* business messaging; do not
implement unofficial WhatsApp automation. That sentence, turned into four concrete channel
definitions, is the whole of this section. The rule that generates all four rows is:

> The channel column records **who physically transmitted the message**, and the system may only
> claim `SENT` for a transmission it actually performed, or one that a human explicitly told it
> happened.

| Channel | Who transmits in v1 | Artefact produced | `SENT` is written when | Why it is shaped this way |
|---|---|---|---|---|
| `EMAIL` | the system, over SMTP to `smtp.gmail.com:587` with an App Password | subject + body + `mailto:` unsubscribe footer | Gmail's SMTP `DATA` returns `250` | The only channel that can be transmitted at all on this stack. `_CONTEXT.md` §4's AUP argument is what permits it — one recipient per message, a per-business rendered body, per-message human approval, 15–25 a day, a working unsubscribe, permanent suppression on any complaint — which is a person writing business letters. Bulk it or automate the approval and it becomes the thing that gets the account closed. Authentication is Google's: there is no custom domain and SPF/DKIM/DMARC are not ours to configure. There is **no** delivery receipt (`07-email-integration.md` §7.9.5); gate H2 is sourced from bounces, complaint replies and reply rate over IMAP instead (§5.9.10) |
| `WHATSAPP` (default path) | **Sagar, by hand** | a short body + a `wa.me` link | Sagar returns and calls `record-manual` | Meta's Business Messaging Policy requires prior opt-in and a pre-approved template for business-initiated conversations. A cold template send to a business that never opted in is a policy violation whose price is the WABA number's quality rating and eventually the number itself. A `wa.me` click-to-chat link is not a business-initiated API conversation — it is Sagar opening a chat window himself. The system prepares; the human sends |
| `WHATSAPP` (Cloud API path) | the system, via WhatsApp Cloud API | an approved template + variables | the Cloud API returns a message id | Built, but dark. Gate H1 refuses it unless `contact_policy.whatsapp_api_enabled = 1` **and** the contact carries a recorded opt-in (`business_contacts.whatsapp_optin_at`). No code path sets `whatsapp_optin_at` from research output — only from a recorded human action (a reply, a form submission, a signed note) |
| `PHONE` | **nobody, ever, automatically** | a call script: talking points, not a monologue | Sagar logs the call outcome | TRAI/DND applies to voice and SMS, an auto-dialler is a different regulatory object entirely, and a call is not a message: there is no artefact to preview, no delivery receipt, and no unsubscribe link. What the system can usefully do is prepare research-grounded talking points and then record what happened, so gates F and G can see the attempt |
| `MANUAL` | Sagar, through some channel outside the system (LinkedIn, a contact form, an in-person meeting, a referral) | optional draft | Sagar calls `record-manual` | Without this row the history is incomplete, and an incomplete history makes every frequency gate lie. `MANUAL` exists so that "I already emailed them from my personal account in June" becomes a row gate G can read, instead of a fact that lives only in Sagar's head |

### 5.6.1 Which contact a channel may use

```python
CHANNEL_CONTACT_KIND: dict[str, tuple[str, ...]] = {
    "EMAIL":    ("EMAIL",),
    "WHATSAPP": ("WHATSAPP", "PHONE"),   # a PHONE contact with whatsapp_capable = 1
    "PHONE":    ("PHONE",),
    "MANUAL":   ("EMAIL", "PHONE", "WHATSAPP", "OTHER"),   # or contact_id = NULL
}
```

`MANUAL` is the only channel that accepts `contact_id IS NULL` — "I met the owner at a trade fair"
has no contact point. Every other channel requires a `business_contacts` row (gate E1).

### 5.6.2 The `wa.me` link

```python
def wa_me_link(phone_e164: str, body: str) -> str:
    """Click-to-chat URL. Opens WhatsApp with the text pre-filled; it does not send.

    phone_e164 is '+919999900000'; wa.me wants it without the '+'.
    """
    return "https://wa.me/" + phone_e164.lstrip("+") + "?text=" + urllib.parse.quote(body, safe="")
```

The preview for a `WHATSAPP` draft on the default path shows the body, the link, a copy button, and
one control labelled **"I sent this"** — not "Send". The message sits in `APPROVED` until Sagar
presses it; §5.17 covers what happens when he never does.

### 5.6.3 `record-manual`

```http
POST /api/v1/outreach/drafts/<draft_id>/record-manual
{
  "channel": "WHATSAPP",
  "contact_id": "cnt_01JB...C2",
  "sent_at": "2026-08-27T06:15:00Z",
  "outcome": "SENT",
  "body_as_sent": "Hello ... Regards, Sagar",
  "note": "Sent from my phone",
  "idempotency_key": "cnf_01JB...N4"
}
```

`outcome` is one of `SENT`, `NO_ANSWER`, `WRONG_NUMBER`, `REFUSED`. `record-manual` is a **send
path**, so it obeys every rule a send path obeys:

1. It runs the full gate set at `stage='SEND'` inside `BEGIN IMMEDIATE`.
2. It writes an `outreach_approvals` row first — Sagar is approving the record of his own action,
   and §48 wants a named human against every transmission — then moves the message
   `PENDING_APPROVAL -> APPROVED -> QUEUED -> SENT` in the same transaction.
3. `provider` is `'manual'`, `provider_message_id` is NULL, `sent_by` is Sagar.
4. `body_as_sent` overwrites `body_final` and recomputes `body_hash` **before** the approval row is
   written, so the trigger's hash equality still holds. If Sagar retyped the message on his phone,
   what is stored is what he actually sent, not what the model drafted.
5. `outcome <> 'SENT'` writes the message as `FAILED` with `failure_code = 'MANUAL_' + outcome`, and
   `WRONG_NUMBER` additionally deactivates the contact (`is_active = 0`).

One deliberate exception, and it is the only place in this document where a gate can be acknowledged
rather than obeyed:

| Situation | Behaviour |
|---|---|
| `record-manual` on `MANUAL`/`PHONE`/`WHATSAPP` default path, gate A blocks | `409` with the gate sentence and `{"acknowledgeable": true}`. Re-posting with `"acknowledge_block": "A_SUPPRESSED_EMAIL"` records the message with `policy_override = 1`, writes an `audit_log` row with `action = 'OUTREACH_POLICY_OVERRIDE'` carrying the gate result verbatim, and fires a Telegram alert |
| Any system-transmit path (`EMAIL`, WhatsApp Cloud API), gate A blocks | `409`, not acknowledgeable. The `acknowledge_block` parameter does not exist in that endpoint's schema |

The reasoning: recording is not sending. If Sagar phoned a business that had opted out, the honest
system state is "this happened, and it should not have" — not a database that pretends it did not.
The override records history; it can never cause a transmission. Invariant 3 is a statement about
what the machine does, and the machine still refuses.

---

## 5.7 Steps 3 and 4 — DRAFT and POLICY CHECK (the boundary with the message document)

The message-template document owns *what the model is asked* and *what the claim policy engine
inspects* (§22–§26, §23's supported-claim rule, §49's audit columns). This document owns the row
lifecycle around it. The contract between them is two function signatures and one status column.

```python
# radar/messages.py — owned by the message-template document
def generate_draft(conn: sqlite3.Connection, *, business_id: str, campaign_id: str,
                   selection_id: str, contact_id: str | None, channel: str,
                   sequence_no: int, parent_message_id: str | None,
                   created_by: str) -> str:
    """Returns a new outreach_drafts.id. Writes the draft and its §49 audit columns."""

# radar/policy.py — called from step 4
def check_message_claims(conn: sqlite3.Connection, draft_id: str) -> ClaimPolicyResult:
    """PASS | WARN | BLOCK plus a per-violation list, each naming the finding it offends."""
```

The `draft_outreach` job body:

```python
def run_draft_outreach(conn: sqlite3.Connection, job: Job) -> None:
    sel = load_selection(conn, job.payload["selection_id"])

    elig = check_send_eligibility(conn, sel.business_id, job.payload.get("contact_id"),
                                  job.payload["channel"], stage="SELECT",
                                  campaign_id=sel.campaign_id)
    if not elig.allowed:
        mark_selection_blocked(conn, sel.id, elig)      # state='BLOCKED', snapshot stored
        return

    draft_id = messages.generate_draft(conn, ...)

    with db.transaction(conn):
        msg_id = insert_outreach_message(conn, draft_id, status="DRAFT")
        emit_event(conn, msg_id, "DRAFTED", actor_type="SYSTEM", actor_id=job.worker_id)

    result = policy.check_message_claims(conn, draft_id)
    with db.transaction(conn):
        store_policy_result(conn, draft_id, result)     # policy_result/detail/version/checked_at
        if result.verdict == "BLOCK":
            set_status(conn, msg_id, "POLICY_BLOCKED")
            emit_event(conn, msg_id, "POLICY_BLOCK", detail=result.as_json())
        else:
            set_status(conn, msg_id, "PENDING_APPROVAL")
            emit_event(conn, msg_id, "POLICY_PASS", detail=result.as_json())
```

Two design points worth stating because they are easy to get wrong:

- **The `outreach_messages` row is created at DRAFT time, not at approval time.** One row, one status
  column, one place to look for "where is this message in the pipeline". A draft that is never
  approved becomes a `CANCELLED` message, not a dangling draft with no lifecycle.
- **A `POLICY_BLOCKED` message is not a failure to hide.** It appears in the workspace with the
  offending claim highlighted against the finding it contradicts, because §23's whole purpose is to
  make an unsupported claim visible rather than to quietly delete it.

### 5.7.1 Editing and regeneration

| From | Action | Result |
|---|---|---|
| `DRAFT` / `POLICY_BLOCKED` / `PENDING_APPROVAL` | `PUT /api/v1/outreach/drafts/<id>/body` | `body_edited` set, `edit_count += 1`, `EDITED` event, status forced back to `DRAFT`, claim policy re-run, any outstanding preview token invalidated |
| `DRAFT` / `POLICY_BLOCKED` / `PENDING_APPROVAL` | `POST /api/v1/outreach/drafts/<id>/regenerate` | old draft gets `superseded_by`, old message `CANCELLED`, a new `out_`/`msg_` pair created |
| `APPROVED` / `QUEUED` | edit | **refused, 409.** The transition table has no `APPROVED -> PENDING_APPROVAL` edge. The UI offers "Revoke approval", which is `APPROVED -> CANCELLED` plus `outreach_approvals.revoked_at`, then a fresh draft |
| `SENT` and beyond | edit | refused. Nothing rewrites a message that left the building |

Editing after approval is impossible by construction rather than by validation, because the
alternative — an approval row whose `approved_body_hash` no longer matches the body — is exactly the
hole invariant 1 exists to close.

---

## 5.8 The eligibility engine

Everything above and below funnels into one function. It is the only thing in the system allowed to
answer "may we contact this business, on this channel, through this contact, right now?", and every
screen that appears to answer that question is rendering its output.

```python
# radar/policy.py

Stage = Literal["SELECT", "PREVIEW", "SEND"]
Outcome = Literal["PASS", "WARN", "BLOCK", "SKIP"]


@dataclass(frozen=True)
class GateResult:
    gate: str                       # 'A1', 'F5', 'H2' - stable, greppable
    code: str                       # 'A_SUPPRESSED_EMAIL' - stable, shown in the API
    outcome: Outcome
    sentence: str                   # ONE sentence, addressed to Sagar, no jargon
    detail: dict[str, Any]          # the numbers behind the sentence
    evidence_ids: tuple[str, ...]   # sup_/msg_/rsp_/ver_/res_ ids backing it


@dataclass(frozen=True)
class Eligibility:
    business_id: str
    contact_id: str | None
    channel: str | None
    stage: Stage
    evaluated_at: str               # ISO-8601 UTC
    policy_version: str             # contact_policy.policy_version in force
    allowed: bool
    blocking_code: str | None       # first BLOCK in precedence order
    blocking_sentence: str | None
    gates: tuple[GateResult, ...]   # ALL gates, in precedence order, always
    warnings: tuple[GateResult, ...]
    fingerprint: str                # sha256 over the (gate, outcome) pairs

    def to_json(self) -> str: ...
    @classmethod
    def from_json(cls, raw: str) -> Eligibility: ...


def check_send_eligibility(
    conn: sqlite3.Connection,
    business_id: str,
    contact_id: str | None = None,
    channel: str | None = None,
    *,
    stage: Stage = "SEND",
    campaign_id: str | None = None,
    message_id: str | None = None,
    now: str | None = None,
) -> Eligibility:
    """Answer 'may we contact this business, this way, right now?' with a reason per gate.

    Without this function the answer lives in nine different screens and four different WHERE
    clauses, and the day one of them drifts is the day a message goes to somebody who asked
    never to hear from us again. Every gate is evaluated on every call - no short circuit -
    because the operator deserves the whole picture, not the first objection.

    Read-only. It never writes. Callers persist the snapshot; the engine has no opinion about
    where they put it.
    """
```

### 5.8.1 Contract

| Property | Rule | Why |
|---|---|---|
| Purity | Never writes. Never calls an LLM. Never makes a network call | It runs inside a write transaction at SEND stage; a network call there would hold SQLite's writer lock open across the internet |
| Completeness | Evaluates every gate on every call. `blocking_code` is the first `BLOCK` in precedence order, but `gates` carries all of them | A screen that reveals one objection at a time turns fixing a business into whack-a-mole |
| Determinism | Given the same database state and the same `now`, the output including `fingerprint` is byte-identical | This is what makes §5.10's change detection possible and what makes the engine testable from fixtures |
| Cost | 9 queries, all indexed; no query touches more than one business's rows except H2/H3, which are two aggregates over an indexed date range | It runs once per row of a 200-row grid (as a batched variant) and once per send |
| Transaction | At `stage='SEND'` the caller must already be inside `BEGIN IMMEDIATE`; `radar/policy.py` asserts `conn.in_transaction` | A read outside the write transaction is exactly the race §5.10 describes |

### 5.8.2 What the stage argument changes

| Stage | Called from | `contact_id` / `channel` | Per-contact gates when they are `None` | Effect of a `BLOCK` | Effect of a `WARN` |
|---|---|---|---|---|---|
| `SELECT` | `POST /api/v1/selections`, `POST /api/v1/outreach/prepare`, the grid (batched) | may be `None` | return `SKIP` | row not inserted, or the selection moves to `BLOCKED`; the reason is returned in `rejected[]` | inserted with `eligible_at_select = 0`, shown in the attention band |
| `PREVIEW` | `GET /api/v1/outreach/drafts/<id>/preview` | always both | n/a | `CONFIRM & SEND` renders disabled; panel 8 carries the sentence | amber note in panel 8; the button stays enabled |
| `SEND` | inside `send_message()`'s transaction | always both | n/a | message `-> CANCELLED`, `ELIGIBILITY_BLOCK` event, Telegram alert, batch row marked blocked | recorded in `eligibility_snapshot`; the send proceeds |

`SKIP` is not `PASS`. A `SKIP` at SELECT stage means "this gate could not be evaluated without a
chosen contact and channel", and the workspace renders those gates as "checked at preview" rather
than as green ticks. Pretending an unevaluated gate passed is how a grid ends up promising something
the send path will refuse.

---

## 5.9 The gates

### 5.9.1 Catalogue and precedence

Precedence runs A -> I, numeric order within a letter. The first `BLOCK` in this order becomes
`blocking_code`. The order is chosen for usefulness to a human: permanent legal facts first, then
configuration, then data completeness, then per-contact facts, then timing, then channel mechanics,
then paperwork.

| Gate | Code | Question | Hard | Stages | One sentence to Sagar (template) |
|---|---|---|---|---|---|
| A1 | `A_SUPPRESSED_BUSINESS` | business-level opt-out? | yes | all | "{name} opted out on {date} ({reason}) — no channel may be used." |
| A2 | `A_SUPPRESSED_EMAIL` | this email opted out? | yes | all | "The address {email} opted out on {date} via {source}, so no email can be sent to it." |
| A3 | `A_SUPPRESSED_PHONE` | this number opted out or is on DNC? | yes | all | "The number {phone} has been on your do-not-contact list since {date} ({source})." |
| A4 | `A_SUPPRESSED_WHATSAPP` | this WhatsApp id opted out? | yes | all | "{wa_id} asked to stop receiving WhatsApp messages on {date}." |
| A5 | `A_SUPPRESSED_DOMAIN` | the whole domain opted out? | yes | all | "Everyone at {domain} is suppressed since {date} ({reason}), and that includes {name}." |
| B1 | `B_MODE_NOT_HUMAN_APPROVAL` | is `automation_mode` supported? | yes | all | "Automation mode is {mode}; v1 only transmits under HUMAN_APPROVAL." |
| B2 | `B_CHANNEL_DISABLED` | is the channel switched on? | yes | PREVIEW, SEND | "The {channel} channel is switched off in Settings." |
| C1 | `C_RESEARCH_INCOMPLETE` | is there a `COMPLETE` research run? | yes | all | "Research for {name} has not finished — there is nothing to write a message from." |
| C2 | `C_NO_SOURCED_FINDINGS` | at least one sourced `OBSERVED` finding? | yes | all | "No observed, sourced fact exists for {name}, so any message would be guesswork." |
| C3 | `C_NO_OPPORTUNITY` | is there a current `opportunities` row? | yes | all | "No opportunity has been scored for {name}." |
| D1 | `D_NOT_VERIFIED` | status in the verified family? | yes | all | "{name} is {status} — verify it before preparing outreach." |
| D2 | `D_VERIFICATION_REVOKED` | rejected or skipped? | yes | all | "You marked {name} {status} on {date}." |
| D3 | `D_VERIFICATION_STALE` | verified within `verification_valid_days`? | yes | all | "Your verification of {name} is {age} days old (limit {limit}) — re-verify it." |
| D4 | `D_CHECKLIST_INCOMPLETE` | all nine §16 checks ticked? | yes | all | "{n} of the nine verification checks were not ticked for {name}." |
| D5 | `D_HUMAN_OWNED` | `INTERESTED` or `HUMAN_HANDOFF`? | yes | all | "{name} is a live lead you are handling personally — the system stops here." |
| D6 | `D_UNREVIEWED_DUPLICATE` | an OPEN HIGH-priority `merge_candidates` row on this business? | yes | all (first touch only) | "This may be the same business as {other}. Review the duplicate before contacting, or you may send two first emails to one company." |
| E1 | `E_CONTACT_MISSING` | any usable contact at all? | yes | all | "{name} has no confirmed contact to write to." |
| E2 | `E_CONTACT_NOT_VERIFIED` | `human_verified = 1` and active? | yes | PREVIEW, SEND | "You have not confirmed that {display} is a legitimate business contact for {name}." |
| E3 | `E_CONTACT_CHANNEL_MISMATCH` | kind fits the channel and parses? | yes | PREVIEW, SEND | "{display} cannot be used for {channel}." |
| E4 | `E_CONTACT_NO_PROVENANCE` | is `source_ref` recorded? | yes at SEND, WARN at SELECT | all | "There is no record of where {display} came from, and we need one before writing to a named person." |
| F1 | `F_IN_FLIGHT` | another message mid-pipeline? | yes | all | "Another message to {name} is already waiting to go out." |
| F2 | `F_DUPLICATE_EMAIL` | same email contacted inside the window? | yes | all | "{email} was already emailed on {date}, inside your {days}-day window." |
| F3 | `F_DUPLICATE_PHONE` | same E.164 contacted inside the window? | yes | all | "{phone} was already contacted on {date}." |
| F4 | `F_DUPLICATE_WHATSAPP` | same wa id contacted inside the window? | yes | all | "{wa_id} was already messaged on {date}." |
| F5 | `F_DUPLICATE_DOMAIN` | too many addresses at one domain? | yes | PREVIEW, SEND | "{n} people at {domain} have already been contacted since {date} (your limit is {max})." |
| F6 | `F_RECENT_CAMPAIGN` | contacted from another campaign recently? | yes | all | "{name} was contacted on {date} in campaign '{campaign}', inside your {days}-day window." |
| F7 | `F_PRIOR_RESPONSE` | any prior reply on file? | no (WARN) | all | "{name} has replied before ({classification} on {date}) — read the thread before sending again." |
| G1 | `G_MIN_DAYS` | has `min_days_between_outreach` elapsed? | yes | all | "It has been {n} days since the last message to {name}; your minimum is {limit}." |
| G1b | `G_SNOOZED` | is a `LATER` snooze still running? | yes | all | "{name} asked you to come back after {date}." |
| G2 | `G_MAX_ATTEMPTS` | attempts under `max_attempts`? | yes | all | "{name} has already had {n} messages; your maximum is {limit}." |
| G3 | `G_MAX_FOLLOWUPS` | follow-ups under `max_followups`? | yes | all | "{name} has had {n} follow-ups; your maximum is {limit}." |
| G4 | `G_STOP_AFTER_REJECTION` | a rejecting reply on file? | yes | all | "{name} replied {classification} on {date}, and your policy stops outreach after a rejection." |
| G5 | `G_STOP_AFTER_OPT_OUT` | an OPT_OUT or COMPLAINT reply on file? | yes | all | "{name} asked to be removed on {date}." |
| G6 | `G_WRONG_CONTACT` | was this contact flagged wrong? | yes | PREVIEW, SEND | "Someone at {name} told us on {date} that {display} is the wrong contact." |
| H1 | `H_WHATSAPP_NO_OPTIN` | opt-in on file for an API send? | yes for API, WARN for `wa.me` | PREVIEW, SEND | "{name} never opted in to WhatsApp, so this one has to go from your own phone." |
| H2 | `H_EMAIL_REPUTATION` | bounce and complaint rates under limits? | yes | PREVIEW, SEND | "Email sending is paused: {rate}% of the last {n} messages bounced (limit {limit}%)." |
| H3 | `H_DAILY_CAP` | today's send count under the cap? | yes | PREVIEW, SEND | "You have sent {n} of today's {cap} emails — this one goes out tomorrow." |
| H4 | `H_PHONE_NOT_TRANSMITTABLE` | phone is script-only | no (WARN) | PREVIEW, SEND | "This is a call script — the system will never dial; log the call once you have made it." |
| H5 | `H_NO_UNSUBSCRIBE` | is an unsubscribe mailbox configured? | yes | PREVIEW, SEND | "No unsubscribe address is configured for {from_address}, and no email goes out without one." |
| I1 | `I_MESSAGE_STATUS` | message in the right status? | yes | SEND | "This message is {status}, not approved and queued." |
| I2 | `I_NO_APPROVAL` | live approval matching hash and address? | yes | SEND | "No live approval matches this message's text and recipient." |
| I3 | `I_APPROVAL_STALE` | approval within its TTL? | yes | SEND | "You approved this {age} ago and approvals expire after {ttl} — review and approve it again." |
| I4 | `I_POLICY_BLOCKED_MESSAGE` | claim policy verdict not `BLOCK`? | yes | PREVIEW, SEND | "The message makes a claim the research does not support; edit it or regenerate." |

The grid query in §5.4.2 evaluates a subset and orders its `CASE` slightly differently: it puts
`F_IN_FLIGHT` last. That is a display decision, not a precedence disagreement — an in-flight message
is the most transient reason there is, and "you already have one going out" is less useful to a
person scanning 200 rows than "you rejected this business in June". The engine's precedence is
authoritative wherever a decision is made; the grid's `CASE` order only decides which greyed-out
tooltip a human reads. The grid also emits the family code `A_SUPPRESSED` rather than
`A_SUPPRESSED_EMAIL`/`_PHONE`/`_DOMAIN`, because it evaluates suppression across all of a business's
contact points at once and does not yet know which one Sagar will pick. `POST /api/v1/selections`,
which does resolve a contact, returns the specific code.

### 5.9.2 Contact-point normalisation

Every gate that compares contact points compares **normalised** values. Normalisation happens once,
at contact capture; the result is stored in `business_contacts.value_norm` and
`business_contacts.domain`, and `suppressions.value_norm` and `outreach_messages.to_address_norm`
use exactly the same function. There is no ad-hoc `LOWER()` anywhere in a query.

Gate A goes one step further: it hashes the normalised value with `suppression_hmac()` and compares
`value_hmac`, because a suppression has to survive the erasure of the address it names (§5.3.2.1).
Normalisation is still the input to that hash, so everything below applies unchanged — get the
normalisation wrong and the hashes differ, which is the same failure as before with less to look at.

```python
# radar/policy.py

@dataclass(frozen=True)
class ContactPoint:
    kind: str            # EMAIL | PHONE | WHATSAPP | DOMAIN | OTHER
    value_norm: str      # identity: what suppressions and to_address_norm store
    value_dedupe: str    # looser: what gate F2 compares
    domain: str | None   # registrable domain where the kind has one
    display: str         # what the human typed, preserved for the screen
    valid: bool
    error: str | None


def normalise_contact(kind: str, raw: str, *, default_region: str = "IN") -> ContactPoint:
    """Canonical form of a contact point, plus its registrable domain where one exists.

    Two failure modes fight here. Under-normalising means an opt-out on 'Sales@ABC.IN' fails to
    block 'sales@abc.in' and we mail somebody who told us to stop. Over-normalising means one
    person's opt-out silently blocks a colleague who never asked for anything. When they
    conflict, blocking wins: this function may be over-inclusive and must never be
    under-inclusive.
    """
```

| Kind | Rule | SAMPLE input | SAMPLE `value_norm` | SAMPLE `domain` |
|---|---|---|---|---|
| `EMAIL` | NFKC, strip whitespace, lowercase the whole address including the local part (RFC says the local part is case-sensitive; no mail server Sagar will meet treats it that way, and blocking wins) | `  Sales@ABC-Hospital.IN ` | `sales@abc-hospital.in` | `abc-hospital.in` |
| `EMAIL` (`value_dedupe`) | additionally strip `+tag`; for `gmail.com`/`googlemail.com` also drop dots in the local part and fold the domain to `gmail.com` | `S.Agar+leads@googlemail.com` | `s.agar+leads@googlemail.com` | `googlemail.com` (dedupe: `sagar@gmail.com`) |
| `PHONE` | `phonenumbers.parse(raw, 'IN')`, require `is_valid_number`, format `E164` | `098765 43210` | `+919876543210` | — |
| `WHATSAPP` | E.164 without the leading `+` (Meta's `wa_id` form) | `+91 98765 43210` | `919876543210` | — |
| `DOMAIN` | registrable domain (eTLD+1) from the public suffix list, lowercase, strip `www.`, strip the trailing dot, IDNA-encode | `https://WWW.ABC-Hospital.co.in/contact` | `abc-hospital.co.in` | itself |
| `OTHER` | NFKC, trim, lowercase | `LinkedIn: /company/x` | `linkedin: /company/x` | — |

Two consequences worth writing down:

- `value_norm` is what is stored and compared for **identity**; `value_dedupe` is what gate F2 uses
  for **duplicate** detection. An opt-out on `sales+x@abc.in` suppresses that exact address (A2)
  and, because the dedupe keys also match, additionally trips F2 against `sales@abc.in`. The
  stricter of the two always wins.
- A `PHONE` value that fails `is_valid_number` is stored with `valid = 0`, `is_active = 0` and the
  capture error. It can never satisfy gate E3, so a malformed number cannot become a send.

### 5.9.3 Gate A — suppression and opt-out (§30)

The absolute one. `_CONTEXT.md` invariant 3: an opt-out on **any** contact point blocks **every**
channel for that business, permanently.

The points are collected in SQL and hashed in **Python**, then compared on `value_hmac` (§5.3.2.1).
SQLite has no HMAC function, and that limitation is a gift: it forces the hash to be computed in the
one place that holds the pepper, so no query can accidentally fall back to a plaintext comparison.

```sql
-- radar/policy.py :: GATE_A_POINTS_SQL      params: :business_id
-- Step 1. What are this business's contact points, right now?
SELECT 'BUSINESS' AS scope, :business_id AS value_norm
UNION ALL
SELECT c.kind, c.value_norm
  FROM business_contacts c
 WHERE c.business_id = :business_id
   AND c.kind IN ('EMAIL','PHONE','WHATSAPP')
UNION ALL
SELECT 'DOMAIN', c.domain
  FROM business_contacts c
 WHERE c.business_id = :business_id
   AND c.domain IS NOT NULL
UNION ALL
SELECT 'DOMAIN', b.website_domain
  FROM businesses b
 WHERE b.id = :business_id
   AND b.website_domain IS NOT NULL;
```

```python
# radar/policy.py :: gate_a()
points = conn.execute(GATE_A_POINTS_SQL, {"business_id": business_id}).fetchall()
pairs  = [(p["scope"], suppression_hmac(p["value_norm"])) for p in points]
```

```sql
-- radar/policy.py :: GATE_A_SQL
-- Step 2. Does any of them carry a live suppression? Joined on value_hmac, NEVER on
-- value_norm: after a DPDP erasure (11 §11.12.5) value_norm reads '#erased:<prefix>' while
-- value_hmac is untouched, and a plaintext join would return nothing for exactly the person
-- who asked hardest not to be contacted. §5.3.2.1.
-- The (scope, hmac) pairs are expanded into the VALUES list as bound parameters; there are
-- at most a handful per business and the query is prepared per call.
WITH points(scope, value_hmac) AS (VALUES (?, ?), (?, ?), ...)
SELECT s.id, s.scope, s.value_norm, s.reason, s.source, s.source_ref,
       s.created_at, s.erased_at, s.detail
  FROM suppressions s
  JOIN points p
    ON p.scope = s.scope
   AND p.value_hmac = s.value_hmac
 WHERE s.released_at IS NULL
 ORDER BY CASE s.scope WHEN 'BUSINESS' THEN 0 WHEN 'DOMAIN' THEN 1 ELSE 2 END,
          s.created_at
 LIMIT 5;
```

`radar/policy.py :: is_suppressed()` (`11-audit-architecture.md` §11.12.3) is the single-point form of
the same lookup, and it is the one every other document calls. There are not two implementations:
`gate_a()` is `is_suppressed()` run over a business's whole point set in one round trip, and a test
asserts the two agree on every point (§5.23 case 4b).

Note what the query does **not** do: it does not filter by the channel being requested. A phone
opt-out blocks email. That is the invariant, expressed as a missing WHERE clause.

`s.erased_at` is selected so the banner can say "this contact's details were erased on request; the
block survives" instead of rendering `#erased:9f13...` at a human. The block is what matters and the
address is gone on purpose.

Every row returned becomes its own `GateResult` (A1–A5, by scope), and the UI renders §30's banner:

```
DO NOT CONTACT                                                    SAMPLE
Reason  : Replied "please remove us from your list" (REPLY_OPT_OUT)
Date    : 2026-06-14T11:20:00Z
Source  : Inbound reply rsp_01JB...R7 to msg_01JB...M3
Scope   : EMAIL  contact@example-sample.in
This block covers every channel for this business and cannot be cleared from the app.
```

The last line is not decoration. It is there so Sagar does not spend ten minutes hunting for the
button that would clear it, and so that anyone reading over his shoulder understands the block is
structural rather than a setting.

### 5.9.4 Gate B — mode and switches (§46)

```sql
-- radar/policy.py :: GATE_B_SQL      params: :campaign_id
SELECT id, scope, automation_mode, policy_version,
       email_enabled, whatsapp_enabled, whatsapp_api_enabled,
       phone_enabled, manual_enabled
  FROM contact_policy
 WHERE id = 'GLOBAL'
    OR (scope = 'CAMPAIGN' AND campaign_id = :campaign_id)
 ORDER BY CASE scope WHEN 'GLOBAL' THEN 0 ELSE 1 END;
```

Merged by `effective_policy()` (§5.3.1, stricter wins). B1 passes only for `HUMAN_APPROVAL`; see
§5.20. B2 checks the switch for the requested channel. Gate B is the only gate whose failure is
**campaign-wide rather than per-row**, which is why §5.4.2's grid carries no `B_` code: when B
fails, `GET /api/v1/campaigns/<id>/selectable` returns every row with `selectable = false` plus a
page-level `policy_banner` object, instead of 200 identical tooltips.

### 5.9.5 Gate C — research complete (§40's first precondition)

```sql
-- radar/policy.py :: GATE_C_SQL      params: :business_id
SELECT
  (SELECT r.id FROM research_runs r
    WHERE r.business_id = :business_id AND r.status = 'COMPLETE'
    ORDER BY r.finished_at DESC LIMIT 1)                              AS run_id,
  (SELECT r.finished_at FROM research_runs r
    WHERE r.business_id = :business_id AND r.status = 'COMPLETE'
    ORDER BY r.finished_at DESC LIMIT 1)                              AS run_finished_at,
  (SELECT COUNT(*) FROM research_findings f
     JOIN finding_sources fs ON fs.finding_id = f.id
    WHERE f.business_id = :business_id AND f.kind = 'OBSERVED')       AS observed_sourced,
  (SELECT COUNT(*) FROM research_findings f
    WHERE f.business_id = :business_id)                               AS findings_total,
  (SELECT o.id FROM opportunities o
    WHERE o.business_id = :business_id AND o.is_current = 1)          AS opportunity_id,
  (SELECT o.score FROM opportunities o
    WHERE o.business_id = :business_id AND o.is_current = 1)          AS opportunity_score,
  (SELECT o.confidence FROM opportunities o
    WHERE o.business_id = :business_id AND o.is_current = 1)          AS opportunity_confidence;
```

| Gate | Blocks when |
|---|---|
| C1 | `run_id IS NULL` |
| C2 | `observed_sourced = 0` — a message built only on `INFERRED` findings is entirely hedged speculation, which is §23's bad column |
| C3 | `opportunity_id IS NULL` |

C2 is the gate that makes invariant 4 achievable rather than aspirational: if there is no sourced
observation, there is nothing the message is permitted to state, so there is no message.

### 5.9.6 Gate D — verification current (§15, §16, §17)

```sql
-- radar/policy.py :: GATE_D_SQL      params: :business_id
SELECT b.status                                                       AS business_status,
       b.rejected_at, b.skipped_at,
       v.id                                                           AS verification_id,
       v.verified_at, v.verified_by, v.verdict,
       (SELECT COUNT(*) FROM verification_checks vc
         WHERE vc.verification_id = v.id)                             AS checks_total,
       (SELECT COUNT(*) FROM verification_checks vc
         WHERE vc.verification_id = v.id AND vc.passed = 1)           AS checks_passed
  FROM businesses b
  LEFT JOIN verifications v
         ON v.business_id = b.id
        AND v.verdict = 'VERIFIED'
        AND v.superseded_at IS NULL
 WHERE b.id = :business_id;

-- D6 branch: an unreviewed high-confidence duplicate blocks a FIRST touch.
-- 01-data-model.md §1.12.6. Follow-ups are unaffected: the thread already exists and stopping
-- it mid-conversation is worse than the duplicate it would prevent. Evaluated only when the
-- draft's sequence_no = 1; skipped entirely otherwise.
--   params: :business_id
SELECT c.id, c.rule, c.signal, c.score,
       CASE WHEN c.business_a_id = :business_id THEN c.business_b_id
            ELSE c.business_a_id END                                  AS other_business_id
  FROM merge_candidates c
 WHERE c.state = 'OPEN' AND c.priority = 'HIGH'
   AND (c.business_a_id = :business_id OR c.business_b_id = :business_id);
```

| Gate | Blocks when | Note |
|---|---|---|
| D2 | `business_status IN ('REJECTED','SKIPPED')` | Evaluated before D1 so the sentence names the decision Sagar actually made |
| D1 | `business_status NOT IN ('CONTACT_READY','CONTACTED','RESPONDED')` | The `VERIFIED -> CONTACT_READY` promotion is §5.4.1 |
| D3 | `verification_id IS NULL` or `verified_at < now - verification_valid_days` | Default 30 days. A verification is a statement about a business as it was on one day; a month later "appears operational" is a guess again |
| D4 | `checks_passed < checks_total` or `checks_total < 9` | §16 lists nine checks, including "No do-not-contact record exists". A partial checklist is not a verification |
| D5 | `business_status IN ('INTERESTED','HUMAN_HANDOFF')` | §55: the machine stops at a live lead |
| D6 | the D6 branch returns a row **and** `sequence_no = 1` | `01-data-model.md` §1.12.6. The fuzzy matcher found two rows that may be one company and the deterministic key did not merge them; without this gate both rows get a first email, which is the exact failure `merge_candidates` was built to prevent |

**D6 is numbered D6, not D4.** `01-data-model.md` §1.12.6 calls it "gate D4"; D4 has been
`D_CHECKLIST_INCOMPLETE` in this document since it was written, and gate codes are read by humans out
of stored `eligibility_snapshot` JSON, so renumbering an existing code to make room would silently
change the meaning of every snapshot already on disk. `01` §1.12.6 and `01` §1.14's Open question 2
need the one-word correction; the SQL, the predicate and the blocking sentence are `01`'s, verbatim.

`merge_candidates` is owned by `01-data-model.md` §1.12.6 — the columns this gate depends on are
`state`, `priority`, `business_a_id`, `business_b_id`, `rule`, `signal` and `score`. The block clears
by reviewing the pair at `/settings/duplicates`: merging sets `state = 'MERGED'`, "these are two
different businesses" sets `state = 'REJECTED'`, and either way the gate stops firing. Review is one
click from the block sentence, like re-verification below.

Re-verification is one click from every D block sentence:
`/verify/<business_id>?return=/outreach/<draft_id>`. A new `verifications` row supersedes the old
one (`superseded_at` set on the previous), and the message becomes eligible again without losing any
of its drafting work.

### 5.9.7 Gate E — contact present and human-verified

```sql
-- radar/policy.py :: GATE_E_SQL      params: :contact_id, :business_id
SELECT c.id, c.business_id, c.kind, c.value_norm, c.value_display, c.domain,
       c.human_verified, c.is_active, c.is_role_address, c.person_name,
       c.source_ref, c.source_url, c.captured_at,
       c.whatsapp_capable, c.whatsapp_optin_at, c.whatsapp_optin_source,
       (SELECT COUNT(*) FROM business_contacts x
         WHERE x.business_id = :business_id
           AND x.human_verified = 1 AND x.is_active = 1)              AS usable_contacts
  FROM business_contacts c
 WHERE c.id = :contact_id;
```

| Gate | Blocks when | The block offers |
|---|---|---|
| E1 | `usable_contacts = 0`, or `contact_id IS NULL` on a channel that requires one | "Add a contact" |
| E2 | `human_verified = 0` or `is_active = 0` | the contact confirmation dialog |
| E3 | `kind NOT IN CHANNEL_CONTACT_KIND[channel]`, or `c.business_id <> :business_id`, or `value_norm` empty/invalid, or (`channel='WHATSAPP'` and `kind='PHONE'` and `whatsapp_capable = 0`) | the channel picker |
| E4 | `source_ref IS NULL AND source_url IS NULL` **and** `is_role_address = 0` | the contact provenance field |

`c.business_id <> :business_id` inside E3 is not paranoia — it is the check that stops a stale
`contact_id` in a resubmitted form from addressing one business's message to another's inbox.

E4 is DPDP purpose limitation made mechanical: a named individual's address with no recorded
provenance has no defensible purpose record. A role address (`info@`, `contact@`, `admin@`) with no
provenance is a `WARN`, not a block, because a role address published on a business's own website is
business contact data rather than personal data.

### 5.9.8 Gate F — duplicate contact protection (§29)

§29 enumerates: same business, same email, same phone, same WhatsApp identifier, recent campaign,
previous response, opt-out. Opt-out is gate A. The other six are one query.

```sql
-- radar/policy.py :: GATE_F_SQL
-- params: :business_id, :campaign_id, :message_id, :contact_norm, :contact_dedupe,
--         :contact_domain, :dup_cutoff, :domain_cutoff, :recent_campaign_cutoff
SELECT 'F1_IN_FLIGHT'        AS probe,
       COUNT(*)              AS hits,
       MAX(m.updated_at)     AS last_at,
       MAX(m.id)             AS sample_id,
       NULL                  AS extra
  FROM outreach_messages m
 WHERE m.business_id = :business_id
   AND m.status IN ('PENDING_APPROVAL','APPROVED','QUEUED')
   AND (:message_id IS NULL OR m.id <> :message_id)

UNION ALL
SELECT 'F2_SAME_EMAIL', COUNT(*), MAX(m.sent_at), MAX(m.id), NULL
  FROM outreach_messages m
 WHERE m.channel = 'EMAIL'
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :dup_cutoff
   AND (m.to_address_norm = :contact_norm OR m.to_address_dedupe = :contact_dedupe)

UNION ALL
SELECT 'F3_SAME_PHONE', COUNT(*), MAX(m.sent_at), MAX(m.id), NULL
  FROM outreach_messages m
 WHERE m.channel IN ('PHONE','MANUAL')
   AND m.status IN ('SENT','DELIVERED')
   AND m.sent_at >= :dup_cutoff
   AND m.to_address_norm = :contact_norm

UNION ALL
SELECT 'F4_SAME_WHATSAPP', COUNT(*), MAX(m.sent_at), MAX(m.id), NULL
  FROM outreach_messages m
 WHERE m.channel = 'WHATSAPP'
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :dup_cutoff
   AND m.to_address_norm = :contact_norm

UNION ALL
SELECT 'F5_SAME_DOMAIN',
       COUNT(DISTINCT m.to_address_norm), MAX(m.sent_at), MAX(m.id),
       GROUP_CONCAT(DISTINCT m.business_id)
  FROM outreach_messages m
 WHERE m.recipient_domain IS NOT NULL
   AND m.recipient_domain = :contact_domain
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :domain_cutoff
   AND m.to_address_norm <> :contact_norm

UNION ALL
SELECT 'F6_RECENT_CAMPAIGN', COUNT(*), MAX(m.sent_at), MAX(m.campaign_id), NULL
  FROM outreach_messages m
 WHERE m.business_id = :business_id
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :recent_campaign_cutoff
   AND (:campaign_id IS NULL OR m.campaign_id <> :campaign_id)

UNION ALL
SELECT 'F7_PRIOR_RESPONSE', COUNT(*), MAX(r.received_at), MAX(r.id),
       MAX(r.classification)
  FROM responses r
 WHERE r.business_id = :business_id;
```

| Probe | Blocks when | Window parameter |
|---|---|---|
| F1 | `hits > 0` | none — always |
| F2 / F3 / F4 | `hits > 0` | `:dup_cutoff = now - min_days_between_outreach days` |
| F5 | `hits >= same_domain_max` | `:domain_cutoff = now - same_domain_days days` |
| F6 | `hits > 0` | `:recent_campaign_cutoff = now - recent_campaign_days days` |
| F7 | never blocks — `WARN` only | none |

`to_address_dedupe` is an additional column on `outreach_messages` holding the §5.9.2 dedupe key,
indexed alongside `to_address_norm`. F5 excludes the address itself so it counts *colleagues* rather
than the recipient, and it deliberately spans businesses: a hospital and its diagnostic arm sharing
`@example-group.in` are two `businesses` rows and one inbox culture.

When any of F1–F6 blocks, the banner headline is §29's exact required string —
**"Contact already exists / recent outreach detected."** — with the specific gate sentence beneath
it. The generic line is what §29 asks for; the specific line is what makes it actionable.

The follow-up interaction, which is easy to get backwards: a **follow-up** (`sequence_no > 1`) with
a `parent_message_id` set exempts F2/F3/F4/F6 from the `min_days` window and hands the timing
decision entirely to gate G1 — otherwise no second message could ever be sent to the same address,
and §31's `max_followups` would be unreachable. F1 and F5 still apply to follow-ups.

### 5.9.9 Gate G — contact frequency policy (§31)

```sql
-- radar/policy.py :: GATE_G_SQL      params: :business_id, :contact_id
SELECT
  (SELECT COUNT(*) FROM outreach_messages m
    WHERE m.business_id = :business_id
      AND m.status IN ('SENT','DELIVERED','BOUNCED'))                     AS attempts,
  (SELECT COUNT(*) FROM outreach_messages m
    WHERE m.business_id = :business_id
      AND m.status IN ('SENT','DELIVERED','BOUNCED')
      AND m.sequence_no > 1)                                              AS followups,
  (SELECT MAX(m.sent_at) FROM outreach_messages m
    WHERE m.business_id = :business_id
      AND m.status IN ('SENT','DELIVERED','BOUNCED'))                     AS last_sent_at,
  (SELECT r.classification FROM responses r
    WHERE r.business_id = :business_id
      AND r.classification IN ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE')
    ORDER BY r.received_at LIMIT 1)                                       AS reject_class,
  (SELECT r.received_at FROM responses r
    WHERE r.business_id = :business_id
      AND r.classification IN ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE')
    ORDER BY r.received_at LIMIT 1)                                       AS reject_at,
  (SELECT r.received_at FROM responses r
    WHERE r.business_id = :business_id
      AND r.classification IN ('OPT_OUT','COMPLAINT')
    ORDER BY r.received_at LIMIT 1)                                       AS optout_at,
  (SELECT COUNT(*) FROM responses r
    WHERE r.business_id = :business_id
      AND r.classification = 'WRONG_CONTACT'
      AND r.contact_id = :contact_id)                                     AS wrong_contact_hits,
  (SELECT r.snooze_until FROM responses r
    WHERE r.business_id = :business_id AND r.classification = 'LATER'
    ORDER BY r.received_at DESC LIMIT 1)                                  AS snooze_until;
```

| Gate | Policy field | Blocks when |
|---|---|---|
| G1 | `min_days_between_outreach` | `last_sent_at > now - min_days` |
| G1b | (from the response) | `snooze_until > now` — a `LATER` reply overrides the ordinary window with the date the business itself named |
| G2 | `max_attempts` | `attempts >= max_attempts` |
| G3 | `max_followups` | `followups >= max_followups AND attempts > 0` |
| G4 | `stop_after_rejection` | flag is 1 and `reject_class IS NOT NULL` |
| G5 | `stop_after_opt_out` | flag is 1 and `optout_at IS NOT NULL` |
| G6 | (not configurable) | `wrong_contact_hits > 0` — blocks *this contact*, not the business |

G5 looks redundant against gate A, and it is, deliberately. Gate A reads `suppressions`; G5 reads
`responses`. If the classifier writes an `OPT_OUT` response row and the suppression write fails —
disk full, a worker killed between two statements — gate A goes quiet and G5 is the second lock on
the same door. The reconciliation job in §5.17 repairs the missing suppression, but G5 blocks the
send in the meantime rather than afterwards.

`WRONG_CONTACT` blocking only the contact is the difference between "you have the wrong person" and
"go away". Sagar can add the right contact and proceed; the business is not burned.

### 5.9.10 Gate H — channel-specific policy

**H1 — WhatsApp opt-in.**

```sql
-- params: :contact_id
SELECT c.whatsapp_optin_at, c.whatsapp_optin_source, c.whatsapp_optin_evidence,
       p.whatsapp_api_enabled
  FROM business_contacts c
  CROSS JOIN (SELECT whatsapp_api_enabled FROM contact_policy WHERE id = 'GLOBAL') p
 WHERE c.id = :contact_id;
```

| `whatsapp_api_enabled` | `whatsapp_optin_at` | Result |
|---|---|---|
| 0 | anything | `WARN` — default `wa.me` path; the preview says the send is by hand |
| 1 | `NULL` | `WARN` on the `wa.me` path, `BLOCK` if the request asked for `transport = 'CLOUD_API'` |
| 1 | set | `PASS` — Cloud API with an approved template is permitted |

The transport is chosen by the engine, not by the caller: `Eligibility.detail['whatsapp_transport']`
is `'WA_ME'` or `'CLOUD_API'`, and `radar/channels/whatsapp.py` reads it rather than deciding for
itself. A channel module that *could* decide to use the API is a channel module that one day will,
by accident.

**H2 — email sending health.** The gate reads `v_email_health` (`07-email-integration.md` §7.6.7),
which is the single definition of these rates:

```sql
-- params: none; the view fixes its own 30-day window
SELECT n_sent, n_bounced, n_complained, n_replied, n_today,
       bounce_pct, complaint_pct, reply_pct
  FROM v_email_health;
```

Blocks when `bounce_pct >= bounce_rate_max_pct` (default 5.0) or
`complaint_pct >= complaint_rate_max_pct` (default 0.1). Both are `NULL` below
`bounce_rate_min_sample` (20), and a `NULL` never blocks: the gate passes with a `WARN` carrying the
raw counts, because two bounces out of three sends is noise, not a reputation problem — and per
invariant 5 the panel renders `—` for the rate rather than a meaningless percentage.

**Where these numbers come from on this stack, since there is no webhook.** `_CONTEXT.md` §2 puts
the app on `127.0.0.1`, so nothing POSTs delivery outcomes to us. Each input has one source and it is
worth being exact about which, because the earlier revision of this gate assumed all three arrived by
callback:

| Input | Source | Honest limitation |
|---|---|---|
| `n_bounced` | `poll_inbox` parses the DSN out of the mailbox and sets `status = 'BOUNCED'` (`07` §7.9.6, `14` §14.8.13) | Delayed by up to one poll interval. Soft bounces are not counted as hard ones |
| `n_complained` | An inbound reply the classifier types `COMPLAINT`, which writes a `COMPLAINED` event (`09-response-classification.md`) | **There is no feedback loop.** Gmail does not expose a complaint stream without a domain, so this counts complaints that were *written to us*, and misses every "mark as spam" that was not. `07` §7.9.4 says so plainly |
| `n_replied` | `responses` rows joined to their message | On this stack the reply rate is the only positive delivery signal that exists |
| Delivery confirmation | **Nothing.** There is no `DELIVERED` event | SMTP acceptance is not delivery; an accepted, un-bounced message stays `SENT` forever (`14` §14.8.14) |

Because complaints are under-counted rather than over-counted, `reply_pct` earns its place next to
them: a reply rate that ran at 8% for six weeks and is 0% for the last two is the closest thing to a
delivery alarm this build can construct, and `07` §7.9.4 makes it one. The gate does not block on it —
a rate that only falls when things are already bad is a warning, not a lock.

Unblocking is manual and deliberate. Sagar cleans the contact list, then clears the pause from
`/settings`, which writes a `contact_policy` update and an `audit_log` row. There is no automatic
"try again tomorrow" for reputation, because what recovers a sending account is fixing the list, not
waiting — and on a free Gmail account the thing at stake is the account itself.

**H3 — daily cap and warm-up.**

```sql
-- params: :utc_day_start
SELECT COUNT(*) AS sent_today
  FROM outreach_messages m
 WHERE m.channel = 'EMAIL'
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :utc_day_start;
```

```python
def effective_daily_cap(policy: ContactPolicy, today: date) -> int:
    """Warm-up schedule wins while it is running, then the flat cap applies.

    A brand-new sending domain that emits two hundred messages on day one is a domain that gets
    filtered forever. The schedule is a list of per-day caps counted from warmup_started_on.
    """
    if not policy.warmup_started_on:
        return policy.daily_send_cap
    day_index = (today - date.fromisoformat(policy.warmup_started_on)).days
    schedule = json.loads(policy.warmup_schedule)
    if 0 <= day_index < len(schedule):
        return min(schedule[day_index], policy.daily_send_cap)
    return policy.daily_send_cap
```

H3 blocks at `sent_today >= effective_daily_cap(...)` and warns from 90% of it. A message blocked by
H3 **alone** is not cancelled — it is the one gate whose block means "later", not "no"; see §5.17.

**H4 — phone.** Always `WARN`, never a silent `PASS`, never a `BLOCK` on its own. Its entire job is
to put "the system will never dial" on screen so the operator's expectation matches the code. A
number on a do-not-call list is gate A3, not H4.

**H5 — unsubscribe.** Blocks `EMAIL` when `contact_policy.email_sending_domain IS NULL`, or when
`identity.from_address` is unset, or when the `+unsub-` mailbox derived from it exceeds 64 characters
(`07-email-integration.md` §7.3.8 refuses to construct a live transport in that case). `_CONTEXT.md`
§4 requires a working unsubscribe on every outbound email; a message that cannot carry one does not
go out.

**There is no unsubscribe URL and no `/u/<message_id>/<token>` endpoint.** The earlier revision of
this section specified a signed HTTPS link and RFC 8058 one-click. Both are impossible here:
`_CONTEXT.md` §2 binds this process to `127.0.0.1`, and a recipient's mail provider cannot POST to a
laptop. `07-email-integration.md` §7.7.1 settles the mechanism and `07` §7.6.4's transport check
**`T8` blocks any message that carries `List-Unsubscribe-Post`** — so specifying that header here
would not merely be stale, it would fail every message with `TRANSPORT_CHECK` before it reached the
socket.

The mechanism, owned by `07` §7.7:

| Element | Value |
|---|---|
| Header | `List-Unsubscribe: <mailto:<base>+unsub-<token>@gmail.com?subject=unsubscribe>` — one URI, `mailto:`, RFC 2369 (`07` §7.7.3) |
| `List-Unsubscribe-Post` | **Absent.** Asserted absent by transport check `T8` (`07` §7.6.4) |
| Visible in the body | The same address as plain text plus a `reply STOP` instruction — the primary path, because `List-Unsubscribe` renders in fewer clients with no HTTPS half (`07` §7.7.4, `06-message-engine.md` rule `R1`) |
| Token | `outreach_drafts.unsubscribe_token`, 32 hex, checked by `T5` against the header |
| Who writes the suppression | `poll_inbox`. It is the **only** automatic suppression writer for unsubscribes (`07` §7.7.5, §7.7.7) |

The poller recognises an unsubscribe by the `+unsub-<token>` tag, resolves the token to the message
and business, and calls
`policy.suppress(scope='EMAIL', reason='UNSUBSCRIBE_LINK', source_ref=message_id)`, which writes both
`value_norm` and `value_hmac` (§5.3.2.1). It writes an `UNSUBSCRIBED` event, and — because §30 is
business-wide — the next gate A evaluation blocks every channel for that business. An unsubscribe
that arrives with no resolvable token still suppresses, on the `From` address, with reason
`REPLY_OPT_OUT` and `business_id IS NULL` (`07` §7.7.6, §7.7.9 case 6). That fallback is why gate A
must join on the contact point and not only on `business_id`.

One consequence of the poll: **suppression is not instantaneous.** An unsubscribe sits in the mailbox
until the next `poll_inbox` tick, and the machine may have been off. `07` §7.10.1 step 0 closes the
window that matters — `send_email` defers for fifteen seconds unless a `poll_inbox` has completed
successfully since the worker started, so the mailbox is always read before the session's first
transmission.

### 5.9.11 Gate I — approval and mode at the send boundary

```sql
-- radar/policy.py :: GATE_I_SQL      params: :message_id
SELECT m.id, m.status, m.body_hash, m.to_address_norm, m.approval_id,
       d.policy_result,
       a.id                AS live_approval_id,
       a.approved_at, a.revoked_at,
       a.approved_body_hash, a.approved_to_address,
       a.session_auth_method
  FROM outreach_messages m
  JOIN outreach_drafts d ON d.id = m.draft_id
  LEFT JOIN outreach_approvals a
         ON a.id = m.approval_id
        AND a.message_id = m.id
        AND a.revoked_at IS NULL
 WHERE m.id = :message_id;
```

| Gate | Blocks when |
|---|---|
| I1 | `status <> 'QUEUED'` at SEND stage |
| I2 | `live_approval_id IS NULL`, or `approved_body_hash <> body_hash`, or `approved_to_address <> to_address_norm` |
| I3 | `approved_at < now - approval_ttl_minutes` (default 60; a queued batch a crashed worker left sitting for three days must be looked at again, not fired blind) |
| I4 | `d.policy_result = 'BLOCK'` |

Gate I is the application-level twin of `trg_om_send_needs_approval`. The trigger is the part that
cannot be bypassed; gate I exists so the refusal reaches Sagar as a sentence he can read rather than
as a `sqlite3.IntegrityError` in a log file.

### 5.9.12 The `Eligibility` payload

`GET /api/v1/outreach/eligibility?business_id=...&contact_id=...&channel=EMAIL&stage=PREVIEW`
returns exactly the JSON that is stored in `selections.eligibility_snapshot`,
`outreach_approvals.eligibility_snapshot` and `outreach_messages.eligibility_snapshot`:

```json
{
  "business_id": "biz_01JB...A1",
  "contact_id": "cnt_01JB...C1",
  "channel": "EMAIL",
  "stage": "PREVIEW",
  "evaluated_at": "2026-08-27T05:41:12Z",
  "policy_version": "cp-1",
  "allowed": false,
  "blocking_code": "G_MIN_DAYS",
  "blocking_sentence": "It has been 9 days since the last message to ABC Hospital (SAMPLE); your minimum is 21.",
  "fingerprint": "9f2c...e41a",
  "warnings": [
    {"gate": "F7", "code": "F_PRIOR_RESPONSE", "outcome": "WARN",
     "sentence": "ABC Hospital (SAMPLE) has replied before (LATER on 2026-08-18) - read the thread before sending again.",
     "detail": {"classification": "LATER", "received_at": "2026-08-18T10:02:00Z"},
     "evidence_ids": ["rsp_01JB...R2"]}
  ],
  "gates": [
    {"gate": "A1", "code": "A_SUPPRESSED_BUSINESS", "outcome": "PASS", "sentence": "No opt-out on file for this business.", "detail": {}, "evidence_ids": []},
    {"gate": "G1", "code": "G_MIN_DAYS", "outcome": "BLOCK",
     "sentence": "It has been 9 days since the last message to ABC Hospital (SAMPLE); your minimum is 21.",
     "detail": {"days_since": 9, "min_days": 21, "last_sent_at": "2026-08-18T09:00:00Z"},
     "evidence_ids": ["msg_01JB...M8"]}
  ]
}
```

`gates` is elided above for length; in the real payload it carries all 39 gate results in precedence
order. SAMPLE data throughout.

---

## 5.10 Where the eligibility check runs, and the race it closes

The same function runs three times, at three moments, for three different reasons.

| Stage | When | Purpose | On block |
|---|---|---|---|
| SELECT | as the grid is rendered and again as a selection is created or prepared | **grey out** — do not let Sagar spend attention on a business he cannot contact | the checkbox is disabled with the gate sentence as its tooltip; a selection attempt returns the row in `rejected[]` |
| PREVIEW | on every render of `/outreach/<draft_id>` | **warn** — show the whole picture before he commits, with `CONFIRM & SEND` disabled if anything hard is blocking | panel 8 renders the block; the button is disabled and the server will refuse the POST too |
| SEND | inside the send transaction, immediately before the provider call | **block** — the last word, on current data, under a write lock | message `-> CANCELLED`, `ELIGIBILITY_BLOCK` event, `audit_log` row, Telegram alert, batch row marked blocked |

### 5.10.1 The race

The first two checks are advisory. Both read the database at a moment that is not the moment of
sending, and between those moments the world moves:

```
T0  09:00:10  Sagar previews msg_...M12 to contact@example-sample.in   -> eligibility allowed
T1  09:00:14  Sagar approves 15 messages, one after another; M12 is #12
T2  09:03:02  the recipient presses "unsubscribe" in a message from June; their client mails
              sagar.radar.mail+unsub-<token>@gmail.com
T2' 09:04:00  poll_inbox reads it and writes suppressions(scope='EMAIL', value_hmac=HMAC(...))
T3  09:07:41  the send worker reaches M12 in the queue
```

Without a check at T3, M12 goes to somebody who opted out four minutes ago, and the system violates
its own first invariant while every screen it drew was truthful at the time it drew it.

The `T2'` line is new with the free stack and it is not cosmetic. On a webhook the suppression landed
the instant the recipient acted; here it lands at the next `poll_inbox` tick, so the gap between
"they opted out" and "the database knows" is real and bounded by the poll interval (two minutes) plus
however long the laptop was closed. `07-email-integration.md` §7.10.1 step 0 closes the dangerous end
of it: `send_email` defers until a `poll_inbox` has completed successfully in this worker's lifetime,
so the mailbox is always read before the first transmission of a session.

The same window admits four other events, all of which are ordinary rather than exotic:

| Event between approval and send | Which gate catches it at T3 |
|---|---|
| An unsubscribe mail, an inbound `OPT_OUT` reply, or a reply the classifier types `COMPLAINT` — all three arrive through `poll_inbox` | A2/A5, G5 |
| A hard bounce on an earlier message to the same domain pushes the bounce rate over the limit | H2 |
| Another campaign, or Sagar himself, contacts the same business by hand | F6, G1 |
| Sagar edits `contact_policy` from `/settings` — tightens `min_days`, drops the daily cap, switches a channel off | B2, G1, H3 |
| Sagar re-verifies, rejects, or deletes the contact from another tab | D2, D3, E2 |
| The response classifier writes an `INTERESTED` row and the handoff job flips the business to `HUMAN_HANDOFF` | D5 |

### 5.10.2 The transaction that closes it

```python
# radar/outreach.py

def send_message(conn: sqlite3.Connection, message_id: str,
                 approval_id: ApprovalId, *, worker_id: str) -> SendResult:
    """The only function in this system that causes a message to be transmitted.

    Everything a screen told Sagar was true when the screen was drawn. This function is where
    it has to be true right now, under a write lock, on the current rows - because between his
    click and this line somebody may have clicked unsubscribe.
    """
    with db.transaction(conn, immediate=True):          # BEGIN IMMEDIATE: writer lock now
        m = conn.execute(
            "SELECT * FROM outreach_messages WHERE id = ? AND status = 'QUEUED'",
            (message_id,)).fetchone()
        if m is None:
            return SendResult.already_handled(message_id)   # another worker won; not an error

        elig = policy.check_send_eligibility(
            conn, m["business_id"], m["contact_id"], m["channel"],
            stage="SEND", campaign_id=m["campaign_id"], message_id=message_id)

        conn.execute(
            "UPDATE outreach_messages SET eligibility_snapshot = ? WHERE id = ?",
            (elig.to_json(), message_id))

        if not elig.allowed:
            _cancel_blocked(conn, m, elig, worker_id)   # -> CANCELLED + ELIGIBILITY_BLOCK + audit
            return SendResult.blocked(message_id, elig)

        conn.execute(
            """UPDATE outreach_messages
                  SET attempt_count = attempt_count + 1,
                      worker_id = ?,
                      provider = ?,
                      provider_send_started_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
                WHERE id = ? AND status = 'QUEUED'""",
            (worker_id, channels.provider_name(m["channel"]), message_id))
        # EMAIL: the reconciliation key is ours and is recorded BEFORE the socket opens.
        if m["channel"] == "EMAIL":
            conn.execute("UPDATE outreach_messages SET provider_message_id = ? WHERE id = ?",
                         (email.derive_message_id(message_id), message_id))
        emit_event(conn, message_id, "SEND_ATTEMPT", actor_type="SYSTEM", actor_id=worker_id,
                   detail={"attempt": m["attempt_count"] + 1,
                           "eligibility_fingerprint": elig.fingerprint})
    # ---- transaction closed. The writer lock is released before any network I/O. ----

    outcome = channels.CHANNELS[m["channel"]].dispatch(
        conn, message_id, approval_id, worker_id=worker_id, cfg=cfg)

    with db.transaction(conn, immediate=True):
        return _record_outcome(conn, message_id, outcome, worker_id)
```

Four things this shape buys:

1. **`BEGIN IMMEDIATE` before the read.** SQLite in WAL mode allows one writer. Taking the write
   lock before reading the message row means no other worker, no poller and no web request can
   commit a change between the eligibility read and the `SEND_ATTEMPT` write. A deferred transaction
   that upgraded later could see a snapshot from before the unsubscribe.
2. **`AND status = 'QUEUED'` on both the SELECT and the UPDATE.** Two workers that somehow claim the
   same message produce one winner; the loser gets `rowcount = 0` and returns `already_handled`.
3. **The transport call is outside the transaction.** An SMTP conversation with Gmail — connect,
   STARTTLS, AUTH, MAIL FROM, RCPT TO, DATA — can take thirty seconds on a bad day. Holding SQLite's
   single writer lock for thirty seconds stalls every other job, the web app and the inbox poller.
   This is the standard outbox shape: decide under the lock, transmit outside it, record under the
   lock again.
4. **`provider_send_started_at` and `provider_message_id` are both written before the call.** They are
   the markers that make the crash window in §5.17 recoverable. SMTP assigns nothing we can query, so
   the reconciliation key has to be one we generate: `derive_message_id(outreach_messages.id)`,
   deterministic from the row (`07-email-integration.md` §7.10.2). A message with
   `provider_send_started_at` set, no `sent_at`, and a worker whose lease has expired is
   `INDETERMINATE` — it is reconciled by searching `[Gmail]/Sent Mail` for that `Message-ID` (`07`
   §7.10.4), and if that is inconclusive a human decides. It is never blindly resent.

### 5.10.3 Fingerprint drift

`Eligibility.fingerprint` is a sha256 over the ordered `(gate, outcome)` pairs. The approval row
stores the PREVIEW-stage snapshot; the message row stores the SEND-stage one. When they differ and
the send still went ahead — a `WARN` appeared or disappeared, a `PASS` became a different `PASS` —
the history panel (§5.18) shows a "conditions changed between approval and send" line with the
per-gate diff. It is not a failure; it is the audit trail admitting that the world moved, which is
exactly what §48 and §49 are asking the system to be honest about.

---

## 5.11 Step 5 — the preview screen (§27)

`GET /outreach/<draft_id>`. Nine panels, in the order §27 lists them, because that order is an
argument: who, how, to whom, on what evidence, for what reason, saying what, how sure, allowed by
whom, and what has passed between us before.

| # | Panel (§27) | Source | Contents | Empty state | Disables CONFIRM? |
|---|---|---|---|---|---|
| 1 | BUSINESS | `businesses`, `campaigns` | name, city, industry, category, size band, website link, campaign name, `businesses.status` badge, opportunity score badge | never empty | — |
| 2 | CHANNEL | request + `contact_policy` + `identity` | channel, transport (`SMTP` / `WA_ME` / `CLOUD_API` / `MANUAL` / `SCRIPT`), the real From address, "who transmits this" in words | never empty | gate B2 |
| 3 | CONTACT | `business_contacts` | display value, kind, `human_verified` badge, provenance (`source_url` + `captured_at`), role-address flag, "not the one you want?" contact switcher | "No confirmed contact" | gates E1–E4 |
| 4 | RESEARCH BASIS | `research_findings` + `finding_sources` + `sources` | the same verbatim finding list as §5.5.3(b), filtered to the findings the draft actually cites (`outreach_drafts.facts_used` and `inferences_used`), each with its source link and `checked_at` | "No sourced findings" | gates C1, C2 |
| 5 | OPPORTUNITY | `opportunities`, `opportunity_modules` | score, band, confidence, potential problem, potential solution, recommended modules, expected benefit | `—` per field | gate C3 |
| 6 | GENERATED MESSAGE | `outreach_drafts` | subject (email only), `final_body` rendered exactly as it will be transmitted — including the signature and, for email, the unsubscribe footer — plus an inline editor and an edit-count badge | never empty | — |
| 7 | AI CONFIDENCE | `outreach_drafts` | `ai_confidence` + `ai_confidence_pct`, `model_id`, `prompt_version`, input/output tokens, and per-claim confidence pulled from the cited findings | `—` | — |
| 8 | POLICY CHECK | `outreach_drafts.policy_result` + `Eligibility` at PREVIEW stage | two blocks: the **claim check** (§23 violations, each naming the finding it offends) and the **eligibility check** (every gate, grouped PASS / WARN / BLOCK, each with its sentence and evidence ids) | never empty | any hard gate; `policy_result = 'BLOCK'` |
| 9 | CONTACT HISTORY | `outreach_messages`, `outreach_events`, `responses` | the §32 history table for this business, newest first, with the current draft shown as a pending row at the top | "No previous contact" — which is itself information | — |

Panel 4 is not a summary. It is the same rows, rendered the same way, as the "why was this selected"
panel in §5.5.3, filtered to what the draft cites. If a claim in panel 6 has no corresponding row in
panel 4, the claim policy engine has already turned `policy_result` to `BLOCK` and panel 8 says so.
The two panels sitting next to each other is the design: an operator can read the message and the
evidence in one eye movement.

```http
GET /api/v1/outreach/drafts/<draft_id>/preview
```

```json
{
  "draft_id": "out_01JB...D1",
  "message_id": "msg_01JB...M1",
  "status": "PENDING_APPROVAL",
  "business": {"id": "biz_01JB...A1", "name": "ABC Hospital (SAMPLE)", "city": "DHULE",
               "industry": "HEALTHCARE", "category": "HOSPITAL", "size_band": "MEDIUM",
               "website": "https://example-sample.in", "status": "CONTACT_READY"},
  "channel": {"channel": "EMAIL", "transport": "SMTP", "provider": "gmail",
              "from_address": "sagar.radar.mail@gmail.com", "transmitted_by": "system",
              "is_live": true},
  "contact": {"id": "cnt_01JB...C1", "kind": "EMAIL",
              "display": "contact@example-sample.in", "human_verified": true,
              "is_role_address": true, "source_url": "https://example-sample.in/contact",
              "captured_at": "2026-08-23T04:10:00Z"},
  "research_basis": {"facts_used": ["res_01JB...F1", "res_01JB...F2"],
                     "inferences_used": ["res_01JB...F3"],
                     "findings": [
                       {"id": "res_01JB...F1", "kind": "OBSERVED", "confidence": "HIGH",
                        "confidence_pct": 90,
                        "statement": "The website lists four clinical departments.",
                        "sources": [{"id": "src_01JB...S1", "name": "Practice website",
                                     "url": "https://example-sample.in/about",
                                     "source_type": "SITE", "checked_at": "2026-08-23T04:02:00Z"}]}
                     ]},
  "opportunity": {"id": "opp_01JB...O1", "score": 86, "band": "HIGH",
                  "confidence": "MEDIUM", "confidence_pct": 64,
                  "potential_solution": "Hospital Operations Platform",
                  "modules": ["Appointments", "Billing", "Inventory", "Reports"]},
  "message": {"subject": "A possible digital operations solution for ABC Hospital (SAMPLE)",
              "body": "Hello ABC Hospital team, ...",
              "body_hash": "3d1f...9ac2", "edit_count": 1, "edited_by": "usr_sagar"},
  "ai_confidence": {"level": "MEDIUM", "pct": 64, "model_id": "gemini-2.5-flash",
                    "prompt_version": "msg-email-v3",
                    "input_tokens": 4120, "output_tokens": 318},
  "policy_check": {"claims": {"verdict": "PASS", "violations": [], "policy_version": "claim-2"},
                   "eligibility": { "...": "the §5.9.12 Eligibility object" }},
  "contact_history": [],
  "preview_token": "pvt_01JB...T9.1d0a...c7",
  "preview_expires_at": "2026-08-27T05:51:12Z",
  "confirm_enabled": true,
  "confirm_blockers": []
}
```

An `outreach_events` row with `event = 'PREVIEWED'` is written on each render, carrying the
eligibility fingerprint. That is what lets the audit answer "did he actually look at it before he
approved it, and what did it say when he did".

Panel 2's `provider`, `transport` and `from_address` are read from the **live transport object**
(`07-email-integration.md` §7.3.3's `name` and `is_live`), never from a constant in this document.
That is `07` §7.10.6's rule and `15-ui-wireframe.md` §15.10 builds the confirm dialog on it: the
dialog names the transport and the From address that will actually be used, so a live send is never
mistaken for a dry run. A preview that printed a provider the build does not have would defeat the
one check that catches a misconfigured environment before it mails a stranger. When
`NullEmailTransport` is active the panel says so — `"provider": "null"`, `"is_live": false` — and the
confirm button reads **CONFIRM & WRITE .EML**.

## 5.12 The preview token and staleness

The preview token binds an approval to a specific rendered screen. Without it, a POST to
`/approve` is a claim about a screen nobody can prove was ever drawn.

```python
def issue_preview_token(draft_id: str, body_hash: str, elig_fingerprint: str,
                        session_id: str, secret: str, now: str) -> str:
    """HMAC over exactly what was on screen. Ten minutes, one session, one body, one verdict."""
    nonce = ids.new("pvt")
    payload = f"{nonce}|{draft_id}|{body_hash}|{elig_fingerprint}|{session_id}|{now}"
    return nonce + "." + hmac.new(secret.encode(), payload.encode(), "sha256").hexdigest()[:32]
```

| Event | Token still valid? | Why |
|---|---|---|
| 10 minutes elapse | no | `preview_expires_at`; a stale screen is a screen whose facts may have moved |
| Body edited (`body_hash` changes) | no | the operator would be approving text he did not read |
| Recipient changed | no | same reason, worse consequence |
| Eligibility fingerprint changes | no | a gate flipped between render and confirm |
| Different browser session | no | `session_id` is inside the HMAC |
| Page reloaded | new token issued, old one is simply forgotten | the tokens are stateless; only the current render's token is accepted, because the confirm handler re-derives it |

A rejected token returns `409` with `{"error": "preview_stale", "reload": true}` and the UI reloads
the preview rather than showing a dead end. This is deliberately not a silent retry: if the reason
the token died is that a gate flipped, Sagar needs to see the new panel 8.

---

## 5.13 Step 6 — the confirmation screen and CONFIRM & SEND (§28)

### 5.13.1 The wording

The button reads exactly **`CONFIRM & SEND`**. Not "Auto Send", not "Send All", not "Go". The
confirmation block above it opens with §28's sentence, stored verbatim in
`outreach_approvals.confirmation_text` so that an audit two years later can read what the operator
was actually told:

```
You are about to contact this business using the selected business contact.
```

`radar/web/app.py` holds this string in one constant, `CONFIRMATION_TEXT`, and a test asserts that
the constant, the rendered template, and the value written to `confirmation_text` are the same
string. If the wording is ever changed, `contact_policy.policy_version` is bumped and old approvals
keep the words that were actually shown to the person who clicked.

Forbidden labels are enforced, not merely discouraged:

```python
FORBIDDEN_BUTTON_TEXT = ("auto send", "send all", "send now to all", "blast", "auto-send")

def test_no_forbidden_send_labels(app):
    """§19 and §28 in one assertion: no template anywhere offers a bulk or automatic send."""
```

### 5.13.2 The seven items §28 requires on screen

All seven must render with real values before the button enables. The server re-checks
completeness — a client that draws six of them and enables the button gets a `409`.

| # | §28 item | Rendered as | Server assertion |
|---|---|---|---|
| 1 | Business | name, city, category, `businesses.status`, opportunity score | `business_id` resolves and is not `REJECTED`/`SKIPPED` |
| 2 | Contact | the exact address that will be used, its kind, its `human_verified` badge and provenance | `to_address_norm` non-null and equal to the contact's `value_norm` |
| 3 | Channel | channel + transport + who transmits | channel enabled, transport resolved by gate H1 |
| 4 | Message | the full final text, not a truncated preview — subject, body, signature, unsubscribe footer | `body_hash` in the POST equals the server's hash of `final_body` |
| 5 | Previous contact history | the §32 table, or the words "No previous contact" | history query executed; the panel may be empty but must have run |
| 6 | Opt-out status | "No opt-out on file for this business, this address, this number or this domain" — or the §30 DO NOT CONTACT banner | gate A evaluated in this request, not read from a cache |
| 7 | Approval status | who is approving (the logged-in user), when, and that this creates a permanent record | session resolves to a `users` row with an interactive auth method |

Item 6's positive form matters. "No opt-out" is a claim the system is making, and it is made from a
gate A evaluation performed inside the same request that renders the screen — not from a flag on the
business row that something might have failed to update.

### 5.13.3 What must be true before the button enables

```python
def confirm_blockers(preview: PreviewPayload) -> list[str]:
    """Everything that keeps CONFIRM & SEND disabled. Empty list means enabled.

    The client uses this to grey the button. The server calls the same function again in the
    approve handler and refuses on any non-empty result, because a disabled button is a
    suggestion and a 409 is a rule.
    """
    blockers: list[str] = []
    if preview.status not in ("PENDING_APPROVAL",):          blockers.append("MESSAGE_STATUS")
    if preview.claims.verdict == "BLOCK":                    blockers.append("CLAIM_POLICY")
    if not preview.eligibility.allowed:                      blockers.append(preview.eligibility.blocking_code)
    if preview.token_expired:                                blockers.append("PREVIEW_STALE")
    if preview.body_hash != preview.rendered_body_hash:      blockers.append("BODY_CHANGED")
    if preview.contact is None and preview.channel != "MANUAL": blockers.append("NO_CONTACT")
    if not preview.displayed_all_seven:                      blockers.append("PANELS_INCOMPLETE")
    if preview.session.auth_method not in ("PASSWORD", "PASSWORD_TOTP"):
                                                             blockers.append("NOT_A_HUMAN_SESSION")
    return blockers
```

### 5.13.4 The request

```http
POST /api/v1/outreach/drafts/<draft_id>/approve
Content-Type: application/json

{
  "message_id": "msg_01JB...M1",
  "preview_token": "pvt_01JB...T9.1d0a...c7",
  "idempotency_key": "cnf_01JB...N4",
  "body_hash": "3d1f...9ac2",
  "to_address_norm": "contact@example-sample.in",
  "eligibility_fingerprint": "9f2c...e41a",
  "displayed": {
    "business": true, "contact": true, "channel": true, "message": true,
    "history": true, "opt_out": true, "approval": true
  },
  "confirmation_text": "You are about to contact this business using the selected business contact."
}
```

Every one of those fields is re-derived server-side and compared. The client is not trusted to tell
the truth about what it drew; it is required to *echo* what the server issued, which is a different
and much weaker claim to have to believe.

Response, on success (SAMPLE):

```json
{
  "approval_id": "apr_01JB...P3",
  "message_id": "msg_01JB...M1",
  "status": "QUEUED",
  "queued_at": "2026-08-27T05:44:03Z",
  "job_id": "job_01JB...J8",
  "duplicate": false
}
```

Failure bodies:

| Condition | Status | Body |
|---|---|---|
| Preview token stale/expired/wrong session | 409 | `{"error":"preview_stale","reload":true}` |
| Body hash mismatch | 409 | `{"error":"body_changed","reload":true}` |
| Hard eligibility gate | 409 | `{"error":"blocked","code":"A_SUPPRESSED_EMAIL","sentence":"..."}` |
| Claim policy `BLOCK` | 409 | `{"error":"claim_policy","violations":[...]}` |
| Message not `PENDING_APPROVAL` | 409 | `{"error":"bad_status","status":"APPROVED"}` |
| Same `idempotency_key` seen already | 200 | the original response with `"duplicate": true` |
| Non-session auth (API token) | 403 | `{"error":"human_session_required"}` |

### 5.13.5 The transaction

Approval and queueing are one transaction. There is no moment at which a message is approved but not
queued, and none at which it is queued but not approved.

```python
def approve_and_queue(conn, *, message_id, draft_id, req, session, user_id) -> ApprovalResult:
    with db.transaction(conn, immediate=True):
        m = load_message_for_update(conn, message_id)          # must be PENDING_APPROVAL
        blockers = confirm_blockers(build_preview(conn, draft_id, session))
        if blockers:
            raise Blocked(blockers)

        elig = policy.check_send_eligibility(conn, m.business_id, m.contact_id, m.channel,
                                             stage="PREVIEW", campaign_id=m.campaign_id,
                                             message_id=message_id)
        if not elig.allowed:
            raise Blocked([elig.blocking_code])

        approval_id = ids.new("apr")
        conn.execute("""
            INSERT INTO outreach_approvals
                (id, message_id, draft_id, business_id, contact_id, channel,
                 approved_by, session_id, session_auth_method, client_ip, user_agent,
                 approved_subject, approved_body, approved_body_hash, approved_to_address,
                 confirmation_text, displayed, eligibility_snapshot,
                 preview_token, idempotency_key)
            VALUES (?,?,?,?,?,?, ?,?,?,?,?, ?,?,?,?, ?,?,?, ?,?)""",
            (approval_id, message_id, draft_id, m.business_id, m.contact_id, m.channel,
             user_id, session.id, session.auth_method, request.remote_addr,
             request.user_agent.string[:255],
             m.subject_final, m.body_final, m.body_hash, m.to_address_norm,
             CONFIRMATION_TEXT, json.dumps(req["displayed"]), elig.to_json(),
             req["preview_token"], req["idempotency_key"]))

        conn.execute("UPDATE outreach_messages SET approval_id = ?, status = 'APPROVED' "
                     "WHERE id = ? AND status = 'PENDING_APPROVAL'", (approval_id, message_id))
        emit_event(conn, message_id, "APPROVED", actor_type="HUMAN", actor_id=user_id,
                   detail={"approval_id": approval_id, "fingerprint": elig.fingerprint})

        job_type = SEND_JOB_TYPE[m.channel]                # 'send_email' | 'send_whatsapp'
        job_id = jobs.enqueue(conn, type=job_type,
                              dedupe_key=f"{job_type}:{message_id}",
                              payload={"message_id": message_id, "approval_id": approval_id,
                                       "business_id": m.business_id,
                                       "campaign_id": m.campaign_id,
                                       "contact_id": m.contact_id})
        conn.execute("UPDATE outreach_messages SET status = 'QUEUED', "
                     "queued_at = strftime('%Y-%m-%dT%H:%M:%SZ','now'), sent_by = ? "
                     "WHERE id = ? AND status = 'APPROVED'", (user_id, message_id))
        emit_event(conn, message_id, "QUEUED", actor_type="SYSTEM", actor_id="web",
                   detail={"job_id": job_id})
        audit.write(conn, action="OUTREACH_APPROVED", entity="outreach_messages",
                    entity_id=message_id, actor_id=user_id,
                    detail={"approval_id": approval_id, "channel": m.channel,
                            "to": m.to_address_norm, "body_hash": m.body_hash,
                            "campaign_id": m.campaign_id, "draft_id": draft_id})
    return ApprovalResult(approval_id=approval_id, job_id=job_id, duplicate=False)
```

**`SEND_JOB_TYPE`, and why there is no `send_message` job.** An earlier revision of this document
enqueued a single job type called `send_message`. `14-background-jobs.md` §14.8's registry has no
such key, and an unregistered type is rejected by the worker at claim time — every message would have
sat in `QUEUED` forever. The transmit job is selected on `outreach_messages.channel`, exactly as
`13-api-endpoints.md` §13.11.4 does it:

```python
# radar/outreach.py
SEND_JOB_TYPE: dict[str, str] = {
    "EMAIL":    "send_email",       # 14 §14.8.12
    "WHATSAPP": "send_whatsapp",    # 14 §14.8: registered ONLY when the Cloud API is enabled
}
```

`MANUAL` and `PHONE` are absent from the map on purpose: nothing transmits them, so nothing is
enqueued and `KeyError` is the correct outcome for a caller that tried. `WHATSAPP` reaches
`send_whatsapp` only on the Cloud API path — on the default `wa.me` path gate H1 has already routed
the message to manual dispatch and `record-manual` writes `SENT` (§5.6). `14` §14.8 is explicit that
`send_whatsapp` is **not** registered in v1, so enqueueing it before the Cloud API is switched on is
a boot-time registry failure rather than a silent stall. `jobs.enqueue()` takes `type=`, not `kind=`:
`14` §14.3.1 names the column `type` and the registry is its reader.

The dedupe key is `{job_type}:{message_id}` — `send_email:msg_01JB...M1` — and it is **permanent,
never pruned** (`07-email-integration.md` §7.10.2). That is one of the four things that make
at-most-once real; §5.14 lists the rest.

### 5.13.6 One at a time

Sagar selected fifteen businesses. He does not get one button that approves fifteen messages.

The review queue at `/outreach?batch=<batch_id>` walks him through them one at a time — full preview
each, `j`/`k` to move, `Enter` to open, an explicit `CONFIRM & SEND` per message, an explicit "skip"
that leaves the message `PENDING_APPROVAL`. Fifteen approvals means fifteen `outreach_approvals`
rows, fifteen previews, fifteen decisions. A progress strip reads "7 of 15 reviewed · 5 approved ·
2 skipped" (SAMPLE).

This is not an ergonomic preference. §45's whole content is that a human decision stands between
research and contact, and one click that produces fifteen approval rows is one decision wearing
fifteen costumes. The keyboard queue makes the honest version fast instead of making the dishonest
version available.

---

## 5.14 Idempotency: a double-clicked CONFIRM must not send twice

Four independent layers, each of which alone would prevent the duplicate, because the cost of a
duplicate here is a second cold email to a stranger.

### Layer 1 — the confirm nonce and a unique index

`idempotency_key` (`cnf_...`) is generated **server-side** when the preview is rendered and embedded
in the confirm form. Both POSTs of a double click carry the same value.

```sql
CREATE UNIQUE INDEX ux_approvals_idem ON outreach_approvals(idempotency_key);
```

```python
try:
    return approve_and_queue(conn, ...)
except sqlite3.IntegrityError as exc:
    if "ux_approvals_idem" not in str(exc):
        raise
    existing = conn.execute(
        "SELECT id, message_id FROM outreach_approvals WHERE idempotency_key = ?",
        (req["idempotency_key"],)).fetchone()
    return ApprovalResult.from_existing(existing, duplicate=True)   # HTTP 200, not 409
```

The second click gets `200` and lands on the same "queued" screen as the first. A double click
should feel like a single click, not like an error.

### Layer 2 — the status guard

`UPDATE ... WHERE id = ? AND status = 'PENDING_APPROVAL'` returns `rowcount = 0` for the second
attempt even if the unique index were somehow absent, and `approve_and_queue` treats `rowcount = 0`
as "already approved". The transition table backs it up: `APPROVED -> APPROVED` is not an edge, so
`trg_om_transition` aborts.

### Layer 3 — the job dedupe key

```sql
CREATE UNIQUE INDEX ux_jobs_dedupe_live ON jobs(type, dedupe_key)
    WHERE state IN ('QUEUED','RUNNING');
```

The column is `type`, not `kind` — `14-background-jobs.md` §14.3.1 owns the `jobs` DDL and names it
`type`. This index is printed here for readability; `14` is the definition, and the version of this
line that said `kind` would have failed at migration time with `no such column: kind`.

`dedupe_key = 'send_email:' || message_id` for email. Two enqueue attempts produce one job, and the
key is permanent rather than pruned (`07-email-integration.md` §7.10.2), so it also blocks a re-send
long after the job row has been archived. A worker that crashes does **not** simply get the job back:
`send_email` is registered with `max_attempts = 1` and `on_lease_expiry = 'RECONCILE'`, so an expired
lease routes to the reconciliation path in §5.17 rather than to a second transmit. Re-queueing after a
failure is an operator action, which appends `regen_no` to the dedupe key.

### Layer 4 — the transmit guard

```sql
CREATE UNIQUE INDEX ux_om_idempotency ON outreach_messages(idempotency_key);
```

```python
message_idempotency_key = sha256(
    f"{business_id}|{channel}|{to_address_norm}|{sequence_no}|{draft_id}".encode()
).hexdigest()
```

This one is about a different duplicate: the same draft producing two message rows to the same
address at the same sequence position. Combined with `send_message()`'s
`UPDATE ... WHERE status = 'QUEUED'` guard, two workers cannot both transmit.

**Nothing goes on the wire as an idempotency key.** SMTP has no such concept, and
`07-email-integration.md` §7.3.3 deleted the `supports_idempotency_key` flag precisely because a flag
that is always false invites somebody to write the branch for it. There is no provider to ask "did
you already accept this one?" either — Gmail's `250` carries an internal queue token that is neither
documented as stable nor queryable. What replaces it is a key we generate ourselves:
`derive_message_id(outreach_messages.id)` goes into the `Message-ID` header and into
`provider_message_id` **before the socket opens**, so the reconciliation path in §5.17 can search
`[Gmail]/Sent Mail` for our own message instead of guessing (`07` §7.10.2, §7.10.4). When that search
is inconclusive, a human decides — which is the honest answer, and the reason this system is
at-most-once rather than exactly-once.

### The double-click timeline

| T | Request A | Request B | Database |
|---|---|---|---|
| 0 | POST /approve | — | — |
| 1 | `BEGIN IMMEDIATE`, gates pass | POST /approve arrives, blocks on the write lock | — |
| 2 | INSERT approval `apr_...P3`; message `PENDING_APPROVAL -> APPROVED -> QUEUED`; job enqueued | still blocked | one approval, one job |
| 3 | COMMIT, returns 200 `duplicate: false` | acquires the lock | — |
| 4 | — | INSERT approval with the same `idempotency_key` -> `IntegrityError` on `ux_approvals_idem` | unchanged |
| 5 | — | rollback, look up the existing approval, return 200 `duplicate: true` | unchanged |

If the two requests hit two processes on two connections, the outcome is identical: SQLite's single
writer serialises them, and the loser hits the same unique index.

The one case that is not a duplicate: Sagar approves, then revokes, then approves again. That is a
deliberate second decision. The revoke sets `revoked_at` (so `ux_approvals_live_message` no longer
matches), a fresh preview issues a fresh `idempotency_key`, and the new approval is a new row —
which is correct, because it *is* a new decision, and §48 wants both of them on the record.

---

## 5.15 Steps 7 and 8 — QUEUE and SEND

### 5.15.1 The job row

The job contract is `14-background-jobs.md` §14.8.12's, restated by `07-email-integration.md`
§7.10.1. `14` is the job registry and its contract wins over anything this document used to say:

| Property | Value |
|---|---|
| Type | `send_email` (io lane, priority 700) |
| Payload | `{"message_id","approval_id","business_id","campaign_id","contact_id"}` — no body, no subject, no address |
| Dedupe key | `send_email:{message_id}` — permanent, never pruned |
| `max_attempts` | **1** |
| Lease expiry | `RECONCILE` |

```json
{
  "id": "job_01JB...J8",
  "type": "send_email",
  "lane": "io",
  "dedupe_key": "send_email:msg_01JB...M1",
  "payload": {"message_id": "msg_01JB...M1", "approval_id": "apr_01JB...P3",
              "business_id": "biz_01JB...A1", "campaign_id": "cmp_01JB...01",
              "contact_id": "cnt_01JB...C1", "batch_id": "job_01JB...B7"},
  "state": "QUEUED",
  "run_after": "2026-08-27T05:44:03Z",
  "lease_expires_at": null,
  "attempts": 0,
  "max_attempts": 1,
  "priority": 700
}
```

The payload carries ids and nothing else. The subject, body and recipient address are read from
`outreach_messages` inside the send transaction, so a `jobs` row is never a second copy of a message
that could drift from the approved one — and `_CONTEXT.md` §2's rule that no `business_contacts`
value reaches a place it does not need to be applies to the job table as much as to an LLM payload.

Claim-by-UPDATE with a lease, per `_CONTEXT.md` §2:

```sql
UPDATE jobs
   SET state = 'RUNNING',
       lease_expires_at = strftime('%Y-%m-%dT%H:%M:%SZ','now','+120 seconds'),
       lease_owner = :worker_id,
       attempts = attempts + 1
 WHERE id = (SELECT id FROM jobs
              WHERE type = 'send_email'
                AND state = 'QUEUED'
                AND run_after <= strftime('%Y-%m-%dT%H:%M:%SZ','now')
              ORDER BY priority, run_after
              LIMIT 1)
RETURNING id, payload;
```

`send_email` jobs run on a pool of **one** thread. Concurrency buys nothing here — the daily cap
is measured in tens of messages — and a single sender makes the per-minute pacing, the daily cap
check and the SQLite writer lock all trivially correct.

Pacing: a minimum gap of `send_min_gap_seconds` (default 45) between two email transmissions,
jittered by ±30% (`07-email-integration.md` §7.6.5 owns the function). Twenty-five identical-looking
messages leaving one account within four seconds is a pattern every spam filter is built to notice,
and on a free Gmail account the filter that notices is the one that closes the account.

The order the worker evaluates before it opens a socket is `07` §7.10.1's, and the distinction that
matters is `Defer` versus `Retry`:

| Step | Condition | On failure |
|---|---|---|
| 0 | has `poll_inbox` completed successfully since this worker started? | `Defer(now + 15s)` — the mailbox may hold an opt-out from whenever the laptop was last closed |
| 1 | message is `QUEUED`, approval live and unrevoked | `Fail` |
| 2 | `check_send_eligibility(stage='SEND')` | `Fail(ELIGIBILITY_BLOCK)`, nothing transmitted |
| 3 | send window open (`14` §14.9.3) | `Defer(next open)` |
| 4 | pacing gap elapsed | `Defer(now + delay)` |
| 5 | rate-bucket token available | `Defer(eta)` + `RATE_LIMITED` event |
| 6 | `body_hash == approval.approved_body_hash` | `Fail` permanently, page immediately |
| 7 | transport checks `T1`–`T9` (`07` §7.6.4) | `Fail('TRANSPORT_CHECK')`, page |
| 8 | commit the intent, then transmit | this is the only step that consumes the one attempt |

Steps 0, 3, 4 and 5 are `Defer`, not `Retry`: they do not consume the attempt. By the time step 8
runs, every gate has passed.

### 5.15.2 The `ApprovalId` type

```python
class ApprovalId(str):
    """A message id that has been proven to carry a live, matching human approval.

    The constructor is the proof. send_message() takes one of these and nothing else, so
    'send without approval' is not a mistake a caller can make - there is no value of the
    right type to pass.
    """
    __slots__ = ()

    @classmethod
    def load(cls, conn: sqlite3.Connection, message_id: str, approval_id: str) -> ApprovalId:
        row = conn.execute(
            """SELECT a.id FROM outreach_approvals a
                JOIN outreach_messages m ON m.id = a.message_id
               WHERE a.id = ? AND a.message_id = ?
                 AND a.revoked_at IS NULL
                 AND a.approved_body_hash = m.body_hash
                 AND a.approved_to_address = m.to_address_norm""",
            (approval_id, message_id)).fetchone()
        if row is None:
            raise NoLiveApproval(message_id, approval_id)
        return cls(row["id"])
```

`_CONTEXT.md` invariant 1 asks for a null `approval_id` to be rejected "at the type level". This is
that: the only way to obtain an `ApprovalId` is a query that already checked the approval is live
and matches the exact bytes about to be sent.

### 5.15.3 Transport dispatch

`08-whatsapp-integration.md` §8.4.1 owns `radar/channels/base.py`, so the result type is its
`DispatchResult` — four outcomes plus a `retryable` flag, not the six-valued `DispatchOutcome` an
earlier revision of this document declared. `07-email-integration.md` §7.10.3 gives the mapping from
the email transport's own `TransportResult` through it.

```python
# radar/channels/base.py   (owned by 08-whatsapp-integration.md §8.4.1 — reproduced, not redefined)
@dataclass(slots=True, frozen=True)
class DispatchResult:
    outcome: str                    # ACCEPTED | AWAITING_MANUAL | FAILED | INDETERMINATE
    provider: str                   # 'gmail' | 'null' | 'wa_cloud' | 'manual_wa' | 'manual'
    provider_message_id: str | None # EMAIL: our own Message-ID, generated before the send
    provider_status_code: int | None
    provider_response: dict[str, Any]
    delivery_state: str | None      # channel-local, e.g. 'AWAITING_MANUAL_DISPATCH'
    artifact: dict[str, Any] | None # e.g. {'wa_link': 'https://wa.me/...'}
    failure_code: str | None
    failure_detail: str | None
    retryable: bool = False


class Channel(Protocol):
    def dispatch(self, conn, message_id: str, approval_id: str, *,
                 worker_id: str, cfg) -> DispatchResult: ...
```

`dispatch()` takes `approval_id` positionally and is only ever called from `send_message()`, which
will not run without one (`08` §8.4.1 — invariant 1, expressed in a signature). It never raises for
a transport-side problem: an exception escaping it would leave a message with
`provider_send_started_at` set and no record of what happened, which is the one state that costs a
human ten minutes in a mail client, because there is no provider dashboard to look it up in.

| Channel | Module | Behaviour |
|---|---|---|
| `EMAIL` | `radar/channels/email.py` -> `radar/email/transport.py` | SMTP submission to `smtp.gmail.com:587`, STARTTLS, App Password auth (`07` §7.3.5). One recipient. `List-Unsubscribe` is a single `mailto:` URI and `List-Unsubscribe-Post` is asserted **absent** by check `T8`. `Reply-To` is a `+msg_...` plus-tagged address on the same account, which is how a reply is attributed (`07` §7.8.3). **No idempotency key goes on the wire** — SMTP has no such header and `07` §7.3.3 removed the flag |
| `EMAIL`, transport `null` | `radar/email/transport.py` | The default. Writes a `.eml` file to disk and returns `ACCEPTED`; no recipient receives anything. `is_live = False` and the confirm button says so |
| `WHATSAPP`, transport `WA_ME` | `radar/channels/whatsapp.py` | returns `AWAITING_MANUAL` immediately; makes no API call |
| `WHATSAPP`, transport `CLOUD_API` | `radar/channels/whatsapp.py` | Cloud API template send; refuses at module level if `Eligibility.detail['whatsapp_transport'] != 'CLOUD_API'` |
| `PHONE` | none | returns `AWAITING_MANUAL` with `failure_code = None`; there is no dialler and there is no code that could become one |
| `MANUAL` | none | never dispatched; `record-manual` writes the outcome directly |

**There is no provider-assigned id on the email path.** SMTP submission assigns nothing we can query,
so `provider_message_id` holds `derive_message_id(outreach_messages.id)` —
`<msg_01JB...@gmail.com>` — generated and written **before** the socket opens, and used as the
reconciliation key against `[Gmail]/Sent Mail` (`07` §7.10.2). Gmail may rewrite the header in
transit; the recorded value is still the key, because §7.10.4's search falls back to the plus-tagged
`Reply-To`, which Gmail does not rewrite.

### 5.15.4 Retry and backoff

`14-background-jobs.md` §14.8.12 registers `send_email` with `max_attempts = 1` and
`on_lease_expiry = 'RECONCILE'`. That is the contract; an earlier revision of this section gave email
five attempts on a 2 min → 6 h ladder, which would send a cold business letter up to five times to a
stranger who has never heard of us. The retry policy is **one attempt at the transmit boundary**,
with `Defer` for everything before it (§5.15.1's step table).

| `DispatchResult` | `retryable` | Message status | Job | What happens next |
|---|---|---|---|---|
| `ACCEPTED` | false | `SENT` | `SUCCEEDED` | — |
| `FAILED`, `INVALID_RECIPIENT` | false | `FAILED` | `FAILED` | Terminal. The fix is a different address, which is a different decision |
| `FAILED`, `AUTH_FAILED` | false | stays `QUEUED` | `FAILED` + banner + Telegram | The message is fine, the App Password is not. Failing fifteen good messages would cost fifteen new drafts and fifteen new approvals |
| `FAILED`, `SMTP_ERROR` permanent 5xx | false | `FAILED` | `FAILED` | Terminal |
| `FAILED`, `421`/`4.7.0` from Gmail | **true** | stays `QUEUED` | `Defer` to the next send window | Gmail's own daily ceiling. Drain the `email.day` bucket, `RATE_LIMITED` event, `HIGH` alert — if we hit Google's limit at a policy cap of 25, the policy cap is wrong |
| `FAILED`, other 4xx / `NETWORK` | true | stays `QUEUED`, `next_retry_at` set | `FAILED` | Surfaces as a row Sagar re-queues with one click, which writes a fresh job with `regen_no` on the dedupe key |
| `INDETERMINATE`, `CONNECTION_LOST` | false | stays `QUEUED`, `INDETERMINATE` event | `DEAD` | §5.17's reconciliation: search the Sent folder; if inconclusive, ask Sagar |
| `AWAITING_MANUAL` | false | stays `APPROVED` | `SUCCEEDED` | A nag job checks after 48 h |

A `retryable` failure does **not** automatically re-enqueue. `max_attempts = 1` and the dedupe key is
permanent, so re-queueing is an operator action. That friction is deliberate: an automatic retry loop
against a mail server that is refusing us is how a rate limit becomes a block.

A `FAILED` message is terminal. Retrying it is a new draft and a new approval — because if the
address was invalid, the fix is a different address, and a different address is a different decision.

---

## 5.16 Step 9 — RECORD (§48)

`_record_outcome()` runs in its own `BEGIN IMMEDIATE` transaction and writes, in order:

```python
def _record_outcome(conn, message_id, outcome: DispatchResult, worker_id: str) -> SendResult:
    m = load_message_for_update(conn, message_id)

    if outcome.outcome == "ACCEPTED":
        conn.execute("""
            UPDATE outreach_messages
               SET status = 'SENT',
                   sent_at = strftime('%Y-%m-%dT%H:%M:%SZ','now'),
                   provider = ?,
                   provider_message_id = COALESCE(?, provider_message_id),
                   provider_status_code = ?,
                   provider_response = ?, failure_code = NULL, next_retry_at = NULL
             WHERE id = ? AND status = 'QUEUED'""",
            (outcome.provider, outcome.provider_message_id, outcome.provider_status_code,
             json.dumps(outcome.provider_response)[:4096], message_id))
        emit_event(conn, message_id, "SENT", actor_type="SYSTEM", actor_id=worker_id,
                   detail={"provider_message_id": outcome.provider_message_id})

        # businesses.status: only CONTACT_READY advances. RESPONDED and beyond stay put.
        conn.execute("""
            UPDATE businesses
               SET status = 'CONTACTED',
                   first_contacted_at = COALESCE(first_contacted_at,
                                                 strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                   last_contacted_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
             WHERE id = ? AND status = 'CONTACT_READY'""", (m.business_id,))

        conn.execute("""
            UPDATE selections SET state = 'DISPATCHED',
                   updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
             WHERE id = (SELECT selection_id FROM outreach_drafts WHERE id = ?)""",
            (m.draft_id,))

        audit.write(conn, action="OUTREACH_SENT", entity="outreach_messages",
                    entity_id=message_id, actor_id=m.sent_by, detail=_audit_payload(conn, m, outcome))
        campaigns.recount(conn, m.campaign_id)
    ...
```

The §48 audit payload — "Business, Contact, Channel, Message, Research ID, Campaign ID, User
approval, Timestamp, Provider response, Delivery status":

```json
{
  "business_id": "biz_01JB...A1",
  "business_name": "ABC Hospital (SAMPLE)",
  "contact_id": "cnt_01JB...C1",
  "to_address_norm": "contact@example-sample.in",
  "channel": "EMAIL",
  "message_id": "msg_01JB...M1",
  "draft_id": "out_01JB...D1",
  "body_hash": "3d1f...9ac2",
  "subject": "A possible digital operations solution for ABC Hospital (SAMPLE)",
  "research_run_id": "res_01JB...R1",
  "opportunity_id": "opp_01JB...O1",
  "campaign_id": "cmp_01JB...01",
  "approval_id": "apr_01JB...P3",
  "approved_by": "usr_sagar",
  "approved_at": "2026-08-27T05:44:03Z",
  "sent_at": "2026-08-27T05:44:41Z",
  "provider": "gmail",
  "transport": "SMTP",
  "provider_message_id": "<msg_01JB...M1@gmail.com>",
  "provider_status_code": 250,
  "delivery_status": "SENT",
  "eligibility_fingerprint_preview": "9f2c...e41a",
  "eligibility_fingerprint_send": "9f2c...e41a",
  "model_id": "gemini-2.5-flash",
  "prompt_version": "msg-email-v3",
  "policy_version": "cp-1"
}
```

`delivery_status` is `'SENT'`, and on the email channel it stays `'SENT'`. `provider_status_code` is
the SMTP reply code (`250` on acceptance), not an HTTP status. `provider_message_id` is the
`Message-ID` we generated ourselves before opening the socket — SMTP hands back nothing we can query
(`07-email-integration.md` §7.10.2).

The body itself is not copied into `audit_log`; `body_hash` plus `outreach_approvals.approved_body`
already pin the exact text, and duplicating a message body into a third table is three places for it
to drift.

**Outcomes that arrive later come in by poll, not by callback.** `_CONTEXT.md` §2 puts this process
on `127.0.0.1`: there is no `POST /api/v1/webhooks/<provider>` and there never will be on this stack.
The `poll_inbox` job (`14-background-jobs.md` §14.8.13, every 2 minutes) reads the Gmail mailbox over
IMAP and is the sole inbound path:

| What arrives | How it is recognised | What it writes |
|---|---|---|
| A hard-bounce DSN | `multipart/report; report-type=delivery-status`, permanent `5.x.x` status, `Original-Message-ID` matching one of ours (`07` §7.9.6) | `outreach_events(BOUNCED)`, `SENT -> BOUNCED`, and `policy.suppress(scope='EMAIL', reason='BOUNCE_HARD')` |
| A soft-bounce DSN | transient `4.x.x` | `BOUNCED` event with `soft=true`; **no** status change and **no** suppression |
| An unsubscribe mail | `+unsub-<token>` tag on the delivery address (`07` §7.7.5) | `UNSUBSCRIBED` event, `policy.suppress(reason='UNSUBSCRIBE_LINK')` |
| A reply the classifier types `COMPLAINT` | `09-response-classification.md` | `COMPLAINED` event, `policy.suppress(reason='COMPLAINT')` |
| A delivery confirmation | — | **Nothing. It does not exist.** SMTP acceptance is not delivery and no DSN says "delivered"; an accepted, un-bounced email stays `SENT` (`14` §14.8.14) |

Every one of these is keyed on `outreach_events.provider_event_id` — the inbound mail's own
`Message-ID` — so re-reading the same mail after a crash produces one row and one status transition.
The WhatsApp Cloud API, if it is ever enabled, is the only channel on this stack with a real callback,
and `08-whatsapp-integration.md` owns it.

---

## 5.17 The failure paths, and what Sagar sees

| Failure | Detected by | `outreach_messages.status` | `businesses.status` | `selections.state` | What Sagar sees | Recovery |
|---|---|---|---|---|---|---|
| SMTP 4xx / network / timeout | dispatch | stays `QUEUED`, `next_retry_at` set | unchanged | `PREPARED` | batch row: "Not sent — connection to Gmail failed. Re-queue when you are ready" | operator re-queues with one click; `max_attempts = 1` means nothing retries on its own |
| SMTP 5xx, invalid recipient | dispatch | `FAILED`, `failure_code='INVALID_RECIPIENT'` | unchanged | `PREPARED` | red row: "The address was rejected as invalid — fix the contact and prepare a new message" | new contact, new draft, new approval |
| `535` auth failure (App Password revoked, 2SV off, IMAP/SMTP disabled) | dispatch | stays `QUEUED` | unchanged | `PREPARED` | banner across `/outreach` naming the three likely causes in order (`07` §7.3.5) + Telegram | fix `config/.env`, restart; queue drains |
| `421` / `4.7.0` from Gmail — the account's own daily ceiling | dispatch | stays `QUEUED` | unchanged | `PREPARED` | "Gmail asked us to stop for today; resuming in tomorrow's window" + `HIGH` alert | automatic tomorrow; also means the policy cap is wrong, because 25/day should never reach Google's limit |
| Daily cap reached (H3) at send | gate H3 inside the txn | stays `QUEUED`, `next_retry_at` = tomorrow's window | unchanged | `PREPARED` | amber: "3 messages held until tomorrow's window (cap 25/day)" | automatic |
| Any other hard gate at send | gate engine inside the txn | `CANCELLED` | unchanged | `BLOCKED` | red row with the gate sentence and the evidence link, plus a Telegram alert if the gate is in the A or G family | the block sentence carries the fix |
| Transport check `T1`–`T9` blocked the built MIME | `07` §7.6.4, before the socket | `FAILED`, `failure_code='TRANSPORT_CHECK'` | unchanged | `PREPARED` | red row naming the failed check | a build bug; page immediately. `T8` firing means somebody re-added `List-Unsubscribe-Post` |
| Hard bounce (DSN read by `poll_inbox`) | `poll_inbox` | `SENT -> BOUNCED` | unchanged | `DISPATCHED` | history row turns red; a `suppressions` row appears; the business shows DO NOT CONTACT | none — this is the system working |
| Soft bounce (transient DSN) | `poll_inbox` | stays `SENT`, `BOUNCED` event with `soft=true` | unchanged | `DISPATCHED` | history note | none |
| Spam complaint, as a reply the classifier typed `COMPLAINT` | `poll_inbox` + classifier | stays `SENT`, `COMPLAINED` event | unchanged | `DISPATCHED` | red banner on the business, suppression row, Telegram alert | investigate the message; H2 may pause sending |
| Worker crash mid-send | expired lease + `provider_send_started_at IS NOT NULL AND sent_at IS NULL` | stays `QUEUED`, `INDETERMINATE` event | unchanged | `PREPARED` | amber: "We are not sure whether this one went out — we searched your Sent folder and could not tell" with two buttons | §5.17.2: search `[Gmail]/Sent Mail` for our `Message-ID`; if inconclusive, **Sagar decides**, and either button writes an audit row naming him |
| Never sent by hand (`AWAITING_MANUAL` for 48 h) | nag job | stays `APPROVED` | unchanged | `PREPARED` | Telegram: "3 WhatsApp messages approved on 25 Aug are still waiting for you to send them" | send and record, or cancel |
| WhatsApp template rejected by Meta | dispatch | `FAILED`, `failure_code='TEMPLATE_REJECTED'` | unchanged | `PREPARED` | red row naming the template | fix the template in the WABA console; regenerate |
| `poll_inbox` has not run since the worker started | `07` §7.10.1 step 0 | stays `QUEUED` | unchanged | `PREPARED` | nothing — it clears in fifteen seconds | automatic. It exists because the machine is not on 24/7 and the mailbox may hold Saturday's opt-out |

There is no "webhook signature invalid" row, because there is no webhook. The equivalent failure on
this stack is an inbound mail the poller cannot attribute, and `07` §7.7.6 and `09` handle it by
suppressing on the `From` address rather than by discarding it.

### 5.17.1 Partial batch failure

Fifteen approved messages do not succeed or fail as a unit. The batch view
`GET /api/v1/outreach/batches/<batch_id>` returns per-message rows plus a rollup:

```json
{
  "batch_id": "job_01JB...B7",
  "created_at": "2026-08-27T05:44:03Z",
  "totals": {"approved": 15, "sent": 12, "queued": 1, "blocked": 1, "failed": 1},
  "messages": [
    {"message_id": "msg_01JB...M1", "business": "ABC Hospital (SAMPLE)", "city": "DHULE",
     "status": "SENT", "sent_at": "2026-08-27T05:44:41Z"},
    {"message_id": "msg_01JB...M12", "business": "XYZ Traders (SAMPLE)", "city": "NASHIK",
     "status": "CANCELLED", "blocking_code": "A_SUPPRESSED_EMAIL",
     "sentence": "The address ops@example-sample.in opted out on 2026-08-27 via the unsubscribe link, so no email can be sent to it."},
    {"message_id": "msg_01JB...M14", "business": "PQR Motors (SAMPLE)", "city": "JALGAON",
     "status": "QUEUED", "note": "Provider asked us to slow down; next attempt 06:12"},
    {"message_id": "msg_01JB...M15", "business": "LMN Bakery (SAMPLE)", "city": "DHULE",
     "status": "FAILED", "failure_code": "INVALID_RECIPIENT"}
  ]
}
```

Rules for the batch screen:

1. **No batch-level retry button.** "Retry the failed one" opens a fresh preview for a fresh draft,
   which needs a fresh approval. There is no control that re-fires four messages at once.
2. Counts come from one `GROUP BY status` aggregate over the batch, never from a counter maintained
   in Python (invariant 5).
3. A blocked message shows the gate sentence in full, not a code. The code is in a tooltip for when
   Sagar wants to search the logs.
4. The batch card persists; §42 wants campaigns reopenable, and "what happened when I sent those
   fifteen" is part of the campaign.

### 5.17.2 The reconciliation job

Run at worker startup (`14-background-jobs.md` §14.5.1 step 6) over every `DEAD` `send_email` job and
every message with a `SEND_ATTEMPT` and no terminal event.

```python
def run_reconcile_indeterminate(conn, job) -> None:
    """Decide what happened to messages whose worker died between the socket and the commit.

    Resending is the tempting default and the wrong one: a duplicate cold email is worse than a
    message that never went out. There is no provider API to ask - SMTP submission assigns
    nothing queryable - so the evidence is Gmail's own Sent folder, read over the same IMAP
    connection the inbox poller uses. When that is inconclusive, the answer is a person, not a
    default.
    """
```

Selection query:

```sql
SELECT m.id, m.provider, m.provider_message_id, m.to_address_norm, m.provider_send_started_at
  FROM outreach_messages m
 WHERE m.status = 'QUEUED'
   AND m.provider_send_started_at IS NOT NULL
   AND m.sent_at IS NULL
   AND m.provider_send_started_at < strftime('%Y-%m-%dT%H:%M:%SZ','now','-5 minutes');
```

`provider_message_id` is populated for every row this query returns, because §5.10.2 writes it inside
the same transaction as `SEND_ATTEMPT`, before the socket opens. That is what makes the row
reconcilable at all.

| Transport | Can it answer "did this send?" | How |
|---|---|---|
| `null` | Yes, definitively | The `.eml` file exists or it does not |
| `gmail` | Usually | `find_sent_copy()` searches `[Gmail]/Sent Mail` over IMAP for our `Message-ID`, falling back to the plus-tagged `Reply-To` if Gmail rewrote the header (`07-email-integration.md` §7.10.4) |

| Search result | Action |
|---|---|
| A Sent copy exists | `SENT`, with the delivered id recorded in the reconciliation event and an `INDETERMINATE` -> `SENT` event pair. **No resend** |
| No Sent copy, and the mailbox answered | `NOT_SENT`. The message returns to `QUEUED` and can be re-queued by Sagar with one click |
| IMAP unreachable, or the search is ambiguous | The message stays `QUEUED` with the `INDETERMINATE` event on screen and a Telegram alert. The row is the only one on `/outreach` with buttons — "it went out" / "it did not" — and **either** writes an audit row naming Sagar |

An honest "we do not know, and here is what we already tried" beats a guess in either direction. This
is the one place where at-most-once needs a human tiebreak, and `07` §7.10.2 explains why that is the
correct trade on a transport that reports nothing back.

---

## 5.18 Outreach history and follow-up sequencing (§32)

### 5.18.1 The history query

§32 asks for, per organisation: Date, Channel, Message, Sender, Delivery status, Response, AI
classification, Next action. One query, rendered on `/business/<id>`, in preview panel 9, and in the
handoff packet.

```sql
-- radar/outreach.py :: OUTREACH_HISTORY_SQL      params: :business_id
SELECT m.id                        AS message_id,
       COALESCE(m.sent_at, m.queued_at, m.created_at)   AS at,
       m.channel,
       m.sequence_no,
       m.parent_message_id,
       m.subject_final,
       m.body_final,
       m.status                    AS delivery_status,
       m.failure_code,
       m.to_address_display,
       u.display_name              AS sender,
       a.approved_at,
       a.approved_by,
       r.id                        AS response_id,
       r.received_at               AS response_at,
       r.body_excerpt              AS response_excerpt,
       r.classification            AS ai_classification,
       r.confidence                AS classification_confidence,
       r.classifier_model_id       AS classifier_model_id,
       r.snooze_until              AS snooze_until,
       h.id                        AS handoff_id,
       h.state                     AS handoff_state,
       (SELECT COUNT(*) FROM outreach_events e
         WHERE e.message_id = m.id AND e.event = 'OPENED')   AS opens
  FROM outreach_messages m
  LEFT JOIN users u                ON u.id = m.sent_by
  LEFT JOIN outreach_approvals a   ON a.id = m.approval_id
  LEFT JOIN responses r            ON r.message_id = m.id
  LEFT JOIN handoffs h             ON h.response_id = r.id
 WHERE m.business_id = :business_id
   AND m.status <> 'DRAFT'
 ORDER BY at DESC;
```

"Next action" is derived, deterministically, in SQL-shaped Python — never by asking a model:

```python
def next_action(row: sqlite3.Row, elig: Eligibility) -> str:
    """One short imperative per history row. No LLM: this is a table, not a judgement."""
    if row["handoff_state"] in ("OPEN", "IN_PROGRESS"):
        return "You are handling this lead - open the handoff"
    if row["ai_classification"] in ("INTERESTED", "VERY_INTERESTED", "DEMO_REQUESTED",
                                    "MEETING_REQUESTED", "PRICE_REQUESTED"):
        return "Contact this business personally"
    if row["ai_classification"] in ("OPT_OUT", "COMPLAINT"):
        return "Do not contact - opt-out recorded"
    if row["ai_classification"] in ("NOT_INTERESTED", "ALREADY_HAVE_SOFTWARE"):
        return "Closed - no further outreach"
    if row["ai_classification"] == "WRONG_CONTACT":
        return "Find the right contact, then start a new sequence"
    if row["ai_classification"] == "LATER":
        return f"Follow up after {row['snooze_until'][:10]}"
    if row["ai_classification"] == "MORE_INFORMATION":
        return "Send the material personally"
    if row["delivery_status"] == "BOUNCED":
        return "Address is dead - suppressed automatically"
    if row["delivery_status"] == "FAILED":
        return "Send failed - prepare a new message if still relevant"
    if row["response_id"] is None and elig.allowed:
        return f"Follow-up {row['sequence_no'] + 1} available"
    if row["response_id"] is None:
        return elig.blocking_sentence or "No action available"
    return "Read the reply"
```

SAMPLE render:

```
OUTREACH HISTORY - ABC Hospital (SAMPLE), Dhule                              SAMPLE

Date        Ch     Seq  Message                       Sender  Delivery   Response            Class      Next action
2026-08-27  EMAIL  1    "A possible digital ope..."   Sagar   SENT       "Please send det..."  INTERESTED Contact this business personally
                                                                          (2026-08-28, HIGH 88)
2026-06-02  MANUAL 1    "(recorded) LinkedIn note"    Sagar   SENT       -                     -          Closed - superseded by campaign cmp_...01
```

The email row reads `SENT` and not `DELIVERED` because on this stack `DELIVERED` is unreachable for
email (§5.3.8). The `opens` count is likewise always zero on the email channel — there is no tracking
pixel and no open tracking of any kind (`07-email-integration.md` §7.6.1) — so the column renders `—`
for `EMAIL` rows rather than `0`, per invariant 5. It is populated on the WhatsApp Cloud API path,
which is why the query still selects it.

### 5.18.2 Follow-up sequencing

A follow-up is a **new** `outreach_drafts` + `outreach_messages` pair with `sequence_no = parent + 1`
and `parent_message_id` set. It is never a re-send of an existing row.

```
seq 1  first touch     day 0
seq 2  follow-up A     day 0 + min_days_between_outreach          (default day 21)
seq 3  follow-up B     day of seq 2 + min_days_between_outreach   (default day 42)
stop   max_followups = 2 -> gate G3 blocks seq 4
```

Preconditions for creating a follow-up, all enforced by the same eligibility engine plus three
sequencing rules that live in `radar/outreach.py`:

| Rule | Check |
|---|---|
| The parent actually went out | `parent.status IN ('SENT','DELIVERED')`. A `BOUNCED` parent means the address is dead; a `FAILED` parent means nothing was received |
| Nothing is in flight | gate F1 |
| No reply of any class has arrived | if `responses` has a row for the parent, the ladder stops and the next action comes from §5.18.1's table — including for `MORE_INFORMATION`, which is a human's job, not a template's |
| The window has elapsed | gate G1, or `snooze_until` for a `LATER` reply |
| Under the follow-up ceiling | gate G3 |
| Same thread | `thread_key` must match the parent's, so a follow-up cannot silently switch to a different address; changing the recipient starts a new sequence at `seq 1` |

The follow-up draft is generated with the parent's `final_body` in the prompt context and one extra
instruction, owned by the message document: **do not repeat the observation used in the parent**. A
follow-up that recites the same sentence about four clinical departments reads as a mailing loop,
which is precisely the impression §54 says not to optimise for.

Auto-scheduling is deliberately absent. A follow-up becomes *available* on its due date and appears
in `/outreach` under "Follow-ups due today"; it is not drafted, not approved and not sent until
Sagar acts. §45 does not have an exemption for second messages.

---

## 5.19 Report row actions and the export boundary (§40)

§40: per row — VIEW, RESEARCH, VERIFY, REJECT, SELECT, PREPARE OUTREACH, VIEW MESSAGE, SEND,
HISTORY. And: "SEND only available after research complete, verified, contact eligible, no opt-out,
no duplicate block, message approved."

| Action | Lives on | Route | Precondition | Gate that enforces it |
|---|---|---|---|---|
| VIEW | grid + export | `GET /business/<id>` | none | — |
| RESEARCH | grid + export | `GET /business/<id>#research` | none | — |
| VERIFY | grid + export | `GET /verify/<id>` | `status IN ('AI_RESEARCHED','NEEDS_VERIFICATION','VERIFIED','CONTACT_READY')` | — |
| REJECT | grid only | `POST /api/v1/businesses/<id>/reject` | not already `CONTACTED`+ | — |
| SELECT | grid only | `POST /api/v1/selections` | §5.4.1 predicate | A, C, D, E, F, G at SELECT stage |
| PREPARE OUTREACH | grid + `/outreach` | `POST /api/v1/outreach/prepare` | a live selection | full gate set at SELECT stage |
| VIEW MESSAGE | grid + `/outreach` | `GET /outreach/<draft_id>` | a draft exists | — |
| SEND | **`/outreach/<draft_id>` only** | `POST /api/v1/outreach/drafts/<id>/approve` | the six §40 conditions below | all of them |
| HISTORY | grid + export | `GET /business/<id>#history` | none | — |

§40's six conditions, mapped:

| §40 condition | Gate | Where it is enforced |
|---|---|---|
| research complete | C1, C2, C3 | SELECT, PREVIEW, SEND |
| verified | D1, D3, D4 | SELECT, PREVIEW, SEND |
| contact eligible | E1, E2, E3, E4 | PREVIEW, SEND |
| no opt-out | A1–A5, G5 | SELECT, PREVIEW, SEND |
| no duplicate block | F1–F6 | SELECT, PREVIEW, SEND |
| message approved | I1, I2, I3 + `trg_om_send_needs_approval` | SEND, and the database |

### 5.19.1 The exported HTML report

The exported file (§5, §41) is a **read-only artefact**. It contains no `<form>`, no `fetch()`, no
`XMLHttpRequest`, no `<button>` that does anything but toggle a local filter or expand a panel. Its
row actions are plain anchors back into the live app:

```html
<td class="actions">
  <a href="https://radar.example-host.in/business/biz_01JB...A1">VIEW</a>
  <a href="https://radar.example-host.in/verify/biz_01JB...A1">VERIFY</a>
  <a href="https://radar.example-host.in/business/biz_01JB...A1#history">HISTORY</a>
</td>
```

No SELECT, no PREPARE OUTREACH, no SEND — those need a session, a CSRF token and a live eligibility
evaluation, none of which a file sitting in a Downloads folder has. A report emailed to somebody
else must be inert in their hands.

```python
def test_exported_report_is_inert(tmp_path):
    """§19 and §5: the file Sagar can email to anyone must not be able to contact anyone.

    Parses the generated HTML and asserts: zero <form> elements, zero occurrences of 'fetch(',
    'XMLHttpRequest', 'navigator.sendBeacon', and every <a href> is either an in-document
    fragment or an absolute https URL under the app host with a GET-safe path.
    """
```

---

## 5.20 Automation modes (§46)

### 5.20.1 What the four modes would mean

| Mode | Meaning | v1 |
|---|---|---|
| `MANUAL` | The system researches, scores and drafts. It transmits nothing at all; every message is recorded through `record-manual` | Storable. Gate B1 restricts the channel to `MANUAL` and no SMTP or Cloud API call is possible. Strictly weaker than `HUMAN_APPROVAL`, so it is safe |
| `HUMAN_APPROVAL` | Every message is previewed and approved by a named human before transmission | **The default and the only mode under which the system transmits.** Everything in this document describes it |
| `SEMI_AUTOMATED` | The system sends within a pre-approved envelope — an approved template, a whitelisted segment, a human spot-checking a sample | Refused by a database trigger |
| `FULLY_AUTOMATED` | The system decides and sends | Refused by a database trigger |

### 5.20.2 How the mode is stored, and why the refusal is structural

```sql
-- from §5.3.1
automation_mode TEXT NOT NULL DEFAULT 'HUMAN_APPROVAL'
    CHECK (automation_mode IN ('MANUAL','HUMAN_APPROVAL','SEMI_AUTOMATED','FULLY_AUTOMATED'))
```

The `CHECK` keeps the column honest about the enum; the two triggers `trg_contact_policy_v1_mode`
and `trg_contact_policy_v1_mode_upd` refuse to store the two automated values at all. A config flag
would be a line in a YAML file that a tired person could flip at 1 a.m.; a trigger is a migration.

But the trigger is only the outermost layer, and it is the least important one. The real reason v1
cannot send without a human is that **the send path requires a row that only a human session can
create**:

```
send_message(conn, message_id, approval_id: ApprovalId, *, worker_id)
      │
      ├─ ApprovalId.load() → SELECT ... FROM outreach_approvals
      │     WHERE revoked_at IS NULL
      │       AND approved_body_hash = m.body_hash
      │       AND approved_to_address = m.to_address_norm
      │
      └─ UPDATE outreach_messages SET status='SENT'
            └─ trg_om_send_needs_approval → RAISE(ABORT) unless that same row exists
```

and `outreach_approvals` can only be written from one place:

| Barrier | Mechanism |
|---|---|
| Column | `session_auth_method` is `NOT NULL CHECK (session_auth_method IN ('PASSWORD','PASSWORD_TOTP'))`. The API-token authenticator used by the worker and the CLI cannot produce either value; there is no `'API_TOKEN'` in the CHECK, so a machine-authored approval fails the constraint |
| Blueprint | The approve handler is registered on `bp_session`, the Flask blueprint whose `before_request` requires a signed session cookie and a CSRF token. The worker process does not run a Flask app at all |
| Import graph | `radar/jobs.py` and every module under `radar/channels/` are forbidden to import `radar.web.*`. Enforced by a test |
| Write audit | Exactly one function, `radar.web.outreach_views.approve_and_queue`, contains an `INSERT INTO outreach_approvals`. Enforced by a test |
| Hash binding | Even a hypothetical machine-written approval would have to carry the exact body hash and recipient of the message about to go out, so a stockpiled generic approval cannot be reused |

```python
def test_only_the_web_approve_handler_writes_approvals():
    """grep, as a test. If a second INSERT INTO outreach_approvals appears anywhere in radar/,
    this fails and somebody has to explain themselves in a code review."""

def test_worker_cannot_import_web():
    """radar.jobs and radar.channels.* must not reach radar.web.*; the send path must not be
    able to construct the object that authorises it."""
```

Gate B1 then makes the refusal legible rather than merely effective: if `automation_mode` were
somehow `FULLY_AUTOMATED`, every eligibility check would block with
"Automation mode is FULLY_AUTOMATED; v1 only transmits under HUMAN_APPROVAL" rather than failing
somewhere deep with a constraint error.

### 5.20.3 What would have to be true to enable more

Not a config change. A migration, and these preconditions, each of which is checkable:

| # | Precondition | Evidence required |
|---|---|---|
| 1 | Recorded opt-in per contact, not per business | `business_contacts.optin_at` + `optin_evidence` populated from a human action, and a gate that requires it |
| 2 | A sending arrangement whose AUP explicitly permits the volume and the nature of the sending | the AUP clause, quoted, stored in `docs/` with a date. `_CONTEXT.md` §4's argument for free Gmail is conditional on per-message human approval, so raising the automation mode is exactly what voids it |
| 3 | DPDP notice and purpose record for every stored personal contact | a rendered notice, an erasure endpoint that works, retention limits enforced by a job |
| 4 | A measured sending history under the bounce and complaint thresholds | at least 500 messages with bounce < 2% and complaints < 0.05%, from the H2 aggregate |
| 5 | An approval source with equivalent audit weight to a human session | a new `outreach_approvals.approval_source` column and a new value in the `session_auth_method` CHECK — that is, a schema migration and a code review, not a setting |
| 6 | A sampling gate: a human still reviews a random n% of every batch, and a failed sample halts the batch | implemented and tested |
| 7 | A kill switch that stops in-flight batches within one job cycle | implemented and tested |
| 8 | Sagar's explicit written decision, recorded as an `audit_log` row | `action = 'AUTOMATION_MODE_CHANGED'` with the reasoning |

Item 5 is the load-bearing one. Enabling `SEMI_AUTOMATED` is not flipping a value; it is adding a
second legal way to authorise a send. That change should look like a change, in a diff, with a
migration number.

---

## 5.21 Endpoint index

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/campaigns/<id>` | session | Research grid with the selection checkboxes |
| GET | `/outreach` | session | Workspace: selections, batches, follow-ups due |
| GET | `/outreach/<draft_id>` | session | The nine-panel preview |
| GET | `/business/<id>` | session | Business detail incl. §32 history |
| GET | `/verify/<id>` | session | Verification screen |
| GET | `/settings` | session | `contact_policy` editor |
| GET | `/api/v1/campaigns/<id>/selectable` | session | Grid rows + `selectable` + `blocking_gate` |
| POST | `/api/v1/selections` | session | Bulk select (§18) |
| DELETE | `/api/v1/selections/<selection_id>` | session | Deselect (soft) |
| GET | `/api/v1/campaigns/<id>/selection-counts` | session | Per-city counts |
| POST | `/api/v1/outreach/prepare` | session | Enqueue drafting for selections |
| GET | `/api/v1/outreach/batches/<batch_id>` | session | Batch progress and outcomes |
| GET | `/api/v1/outreach/workspace/<business_id>` | session | The §20 workspace payload |
| GET | `/api/v1/outreach/drafts/<draft_id>/preview` | session | The §27 payload + preview token |
| PUT | `/api/v1/outreach/drafts/<draft_id>/body` | session | Edit; forces re-check |
| POST | `/api/v1/outreach/drafts/<draft_id>/regenerate` | session | New draft, supersede old |
| POST | `/api/v1/outreach/drafts/<draft_id>/approve` | **session only** | §28 CONFIRM & SEND |
| POST | `/api/v1/outreach/messages/<message_id>/revoke` | session | `APPROVED -> CANCELLED` |
| POST | `/api/v1/outreach/drafts/<draft_id>/record-manual` | session | Record a hand-sent message or a logged call |
| GET | `/api/v1/outreach/eligibility` | session | The `Eligibility` object for a triple |
| GET | `/api/v1/businesses/<id>/history` | session | §32 history rows |
| POST | `/api/v1/suppressions` | session | Manual do-not-contact entry |

Two rows that used to be here are gone, and their absence is a design decision rather than an
oversight:

| Removed | Why | What replaces it |
|---|---|---|
| `GET`/`POST /u/<message_id>/<token>` | No public HTTPS host, so no recipient's browser can reach it (`_CONTEXT.md` §2) | `mailto:` unsubscribe read by `poll_inbox` (`07-email-integration.md` §7.7) |
| `POST /api/v1/webhooks/<provider>` | Nothing on the public internet can reach `127.0.0.1` | `poll_inbox` over IMAP (`14-background-jobs.md` §14.8.13, §14.8.14) |

Every route in this table is `session`-authenticated. There is no unauthenticated endpoint in this
document at all, which is a smaller attack surface than the earlier design had and one fewer thing to
sign.

There is no endpoint anywhere in this table that accepts a `business_id` and transmits. That absence
is §19.

---

## 5.22 Module map

| Module | Responsibility | Docstring opens with |
|---|---|---|
| `radar/outreach.py` | The pipeline: selections, prepare, approve, `send_message()`, batches, history | "Without this module the pipeline lives in the Flask views, and the day a second caller needs to send a message it grows a second, subtly different send path." |
| `radar/policy.py` | `check_send_eligibility()`, the gates, `normalise_contact()`, `suppress()`, `check_message_claims()` | "Without this module the answer to 'may we contact them?' lives in nine screens and four WHERE clauses, and the day one of them drifts is the day we mail somebody who asked us to stop." |
| `radar/channels/email.py` | SMTP submission to Gmail, the `mailto:` unsubscribe header, DSN parsing | "Without this module every send is a hand-rolled smtplib call, and the one that forgets the unsubscribe header is the one that gets the account closed — which on a free Gmail account is not a reputation problem, it is the end of the channel." |
| `radar/channels/whatsapp.py` | `wa.me` link building, Cloud API template send behind gate H1 | "Without this module WhatsApp becomes an unofficial automation hack, which is how a business number gets permanently banned." |
| `radar/messages.py` | Draft generation (§22–§26) | owned by the message-template document |
| `radar/jobs.py` | Claim-by-lease worker, retries, reconciliation | owned by the background-jobs document |
| `radar/audit.py` | `audit.write()` | owned by the audit document |

`radar/outreach.py` is an addition to the module list in `_CONTEXT.md` §6; see Open questions.

---

## 5.23 Test matrix

The tests that must exist for this document to be considered implemented. All offline, fixtures over
mocks, per house style.

| # | Test | Asserts |
|---|---|---|
| 1 | `test_send_requires_live_approval` | `UPDATE ... SET status='SENT'` with `approval_id = NULL` raises; with a revoked approval raises; with a mismatched `body_hash` raises |
| 2 | `test_illegal_transitions_abort` | Every pair not in `outreach_status_transitions` raises, including `DRAFT -> SENT` and `PENDING_APPROVAL -> SENT` |
| 3 | `test_suppression_blocks_every_channel` | An `EMAIL`-scope suppression blocks `WHATSAPP`, `PHONE` and `MANUAL` for that business |
| 4 | `test_suppression_cannot_be_released_by_app` | No code path sets `released_at`; the trigger rejects a release without a matching audit row; DELETE raises |
| 5 | `test_gate_precedence_stable` | With every gate failing at once, `blocking_code` is `A_SUPPRESSED_BUSINESS` |
| 6 | `test_every_gate_has_a_sentence` | Every gate code in the catalogue renders a non-empty, single-sentence message with all placeholders filled |
| 7 | `test_eligibility_is_read_only` | The engine executes no statement outside `SELECT`/`WITH` (connection trace) |
| 8 | `test_send_stage_requires_transaction` | Calling with `stage='SEND'` outside a transaction raises |
| 9 | `test_race_opt_out_between_approve_and_send` | Approve, insert a suppression, then send: message becomes `CANCELLED` with `A_SUPPRESSED_EMAIL`, provider never called |
| 10 | `test_double_click_confirm_sends_once` | Two concurrent POSTs with one `idempotency_key`: one approval row, one job, one transmit, both HTTP 200 |
| 11 | `test_two_workers_one_message` | Two workers claiming the same `QUEUED` message: one `SENT`, one `already_handled` |
| 12 | `test_no_endpoint_sends_from_a_business_id` | The §5.4.5 url_map walk |
| 13 | `test_exported_report_is_inert` | The §5.19.1 parse |
| 14 | `test_no_forbidden_send_labels` | No template contains a bulk or automatic send label |
| 15 | `test_only_the_web_approve_handler_writes_approvals` | One `INSERT INTO outreach_approvals` in the codebase |
| 16 | `test_worker_cannot_import_web` | Import graph |
| 17 | `test_automation_mode_refuses_automated_values` | Both triggers |
| 18 | `test_normalise_contact_table` | Every row of the §5.9.2 table, plus invalid inputs producing `valid = False` |
| 19 | `test_frequency_gates_against_fixtures` | A fixture business at each of G1–G6 blocks with the right code |
| 20 | `test_followup_sequencing` | `seq 2` allowed at day 21, refused at day 20, refused after a reply, refused at `seq 4` |
| 21 | `test_manual_record_writes_approval` | `record-manual` produces an approval row, a `SENT` message and an audit row |
| 22 | `test_hard_bounce_dsn_creates_suppression` | A fixture DSN through `poll_inbox` -> `BOUNCED` + `suppressions` row (with `value_hmac` set) + gate A blocks afterwards |
| 23 | `test_reread_of_the_same_inbound_mail_is_idempotent` | The same inbound `Message-ID` five times: one `outreach_events` row, one status change |
| 24 | `test_preview_token_invalidation` | Each row of the §5.12 table |
| 25 | `test_selection_counts_match_rows` | Per-city counts equal a `COUNT(*)` over `selections`; an empty city renders `—` |
| 26 | `test_suppression_survives_erasure_and_rediscovery` | The whole cycle, and the reason §5.3.2.1 exists: `suppress(scope='EMAIL', ...)` → `erase_subject()` (`11` §11.12.5) rewrites `value_norm` to `'#erased:...'` → a **new** campaign rediscovers the business and writes a fresh `business_contacts` row with the real normalised address → gate A **still BLOCKS** with `A_SUPPRESSED_EMAIL`. A plaintext join passes every other test in this table and fails this one |
| 27 | `test_suppress_always_writes_value_hmac` | Each of the four automatic writers — unsubscribe mail, `STOP` reply, hard bounce, classifier `OPT_OUT` — inserts successfully against the migrated schema. Without `value_hmac`, `trg_suppressions_hmac_required` ABORTs and every automatic opt-out raises instead of suppressing |
| 28 | `test_gate_a_agrees_with_is_suppressed` | For a business with all five point kinds, `gate_a()`'s result set equals the union of `is_suppressed()` over the same points. Two implementations of one lookup is how they drift |
| 29 | `test_unreviewed_duplicate_blocks_first_touch_only` | An `OPEN`/`HIGH` `merge_candidates` row blocks `sequence_no = 1` with `D_UNREVIEWED_DUPLICATE`; the same fixture at `sequence_no = 2` passes; `state = 'REJECTED'` clears it; `priority = 'NORMAL'` never blocks |
| 30 | `test_no_message_carries_list_unsubscribe_post` | The built MIME for every fixture message has exactly one `List-Unsubscribe`, it is a `mailto:`, and `List-Unsubscribe-Post` is absent — the assertion `07` §7.6.4's `T8` makes at build time, repeated here because §5.9.10 used to specify the opposite |
| 31 | `test_send_job_type_is_registered` | For every value of `SEND_JOB_TYPE`, `radar.jobs` has a registration. An unregistered type means a message that queues and never transmits, which looks like nothing at all |
| 32 | `test_email_send_has_one_attempt` | The `send_email` registration has `max_attempts = 1` and `on_lease_expiry = 'RECONCILE'`; a transport failure does not re-enqueue |

---

## 5.24 Worked example (§52), end to end

Every step below names the row that gets written. SAMPLE data throughout.

| Step | Sagar does | System writes |
|---|---|---|
| 1 | Opens `/campaigns/cmp_...01`, Dhule > Healthcare | nothing |
| 2 | Opens ABC Hospital (SAMPLE), reads the research | nothing |
| 3 | Clicks VERIFY, ticks all nine checks, adds a note, approves | `verifications` (`ver_...V4`), 9 × `verification_checks`, `businesses.status = 'VERIFIED'`, then `'CONTACT_READY'` via `promote_contact_ready()`, `audit_log` |
| 4 | Ticks the row's checkbox in the grid | `selections` (`sel_...S1`, `SELECTED`) with the SELECT-stage `Eligibility` snapshot |
| 5 | Clicks PREPARE OUTREACH, channel EMAIL | `jobs` (`draft_outreach`), `selections.state = 'PREPARED'` |
| 6 | waits ~15 s | `outreach_drafts` (`out_...D1`), `outreach_messages` (`msg_...M1`, `DRAFT`), `DRAFTED` event; claim check `PASS`; status `PENDING_APPROVAL`, `POLICY_PASS` event |
| 7 | Opens `/outreach/out_...D1`, reads nine panels | `PREVIEWED` event, preview token issued |
| 8 | Edits one sentence | `body_edited`, `EDITED` event, status back to `DRAFT`, claim re-check, `PENDING_APPROVAL`, new preview token |
| 9 | Clicks CONFIRM & SEND | `outreach_approvals` (`apr_...P3`), `APPROVED` event, status `APPROVED -> QUEUED`, `jobs` (`send_email`, dedupe `send_email:msg_...M1`), `QUEUED` event, `audit_log` `OUTREACH_APPROVED` |
| 10 | waits | worker: step 0 confirms `poll_inbox` has run this session, `BEGIN IMMEDIATE`, SEND-stage eligibility passes, `provider_message_id` written, `SEND_ATTEMPT` event, SMTP submission to `smtp.gmail.com:587` returns `250`, `status = 'SENT'`, `SENT` event, `businesses.status = 'CONTACTED'`, `selections.state = 'DISPATCHED'`, `audit_log` `OUTREACH_SENT`, campaign counters recomputed |
| 11 | — | **Nothing.** There is no delivery event on this stack; the message stays `SENT`. If it had bounced, the next `poll_inbox` would have parsed the DSN into `BOUNCED` + a `suppressions` row |
| 12 | — | `poll_inbox` reads the reply; `responses` (`rsp_...R2`, `INTERESTED`, `gemini-2.5-flash`); `businesses.status = 'RESPONDED'` then `'INTERESTED'`; `handoffs` row; Telegram "HUMAN ACTION REQUIRED" |
| 13 | Opens `/handoffs`, phones the hospital himself | handoff state, `audit_log`. Gate D5 now blocks any further automated outreach to this business — which is the correct end of the pipeline |

---

## Open questions

1. **`radar/outreach.py` is not in `_CONTEXT.md` §6's module list.** The pipeline needs a home that
   is neither `radar/policy.py` (gates) nor `radar/web/app.py` (views). Alternative: fold it into
   `radar/messages.py`, which would then own both drafting and dispatch. Recommendation: keep the
   split; add `radar/outreach.py` to the canonical list. The same applies to
   `outreach_status_transitions` (5.3.8), a static lookup table not in `_CONTEXT.md` section 6's
   table list; it exists so the state machine is enforced by data rather than by a Python
   constant.
2. **Id prefixes `sel_`, `apr_`, `evt_`, `sup_`, `cnt_`** are extensions to `_CONTEXT.md` §2's list.
   §2 supplies `out_` for `outreach_drafts` and `msg_` for `outreach_messages` but nothing for
   selections, approvals, events, suppressions or contacts. Needs a one-line ruling so
   `01-data-model.md` and this file agree.
3. **`automation_mode = 'MANUAL'` remains storable** in the DDL in §5.3.1, while `_CONTEXT.md` §6
   says `HUMAN_APPROVAL` is the "only supported value in v1". This document reads that as "the only
   mode under which the system transmits", and treats `MANUAL` as a strictly weaker draft-only mode
   that the `MANUAL` channel already provides per message. If the intent was that the column must
   physically refuse `MANUAL` too, the trigger in §5.3.1 needs one more value and gate B1 needs one
   fewer branch.
4. **Columns this document assumes on tables it does not own**, needed by `01-data-model.md`:
   `businesses.website_domain`, `businesses.first_contacted_at`, `businesses.last_contacted_at`;
   `campaign_businesses.{campaign_id, business_id, state}` (§5.4.2's grid join, per `01` §1.2.2 —
   `businesses.campaign_id` no longer exists and nothing here reads it);
   `business_contacts.{kind, value_norm, value_dedupe, value_display, domain, human_verified,
   is_active, is_role_address, person_name, whatsapp_capable, whatsapp_optin_at,
   whatsapp_optin_source, whatsapp_optin_evidence, source_ref, source_url, captured_at}`;
   `responses.{contact_id, snooze_until, body_excerpt, classifier_model_id}`;
   `merge_candidates.{state, priority, business_a_id, business_b_id, rule, signal, score}` (gate D6);
   `suppressions.{value_hmac, erased_at}` — additive, owned by `11` §11.12.3, and the join key for
   gate A;
   `opportunities.{is_current, score_breakdown, band, digital_maturity, operational_complexity}`;
   `verifications.superseded_at`;
   `verification_checks.{check_key, passed, note, ordinal}`; `research_runs.{status, finished_at}`;
   `jobs.{type, dedupe_key, run_after, lease_expires_at, lease_owner, priority}` — `type`, not
   `kind`, per `14` §14.3.1.
5. **`verification_valid_days = 30`** is a guess at the right staleness window. Too short and Sagar
   re-verifies constantly; too long and "appears operational" becomes stale. It is configurable, so
   the only real question is the default.
6. **Settled — the transport is not an open question any more.** This slot used to ask which ESP to
   pick. `_CONTEXT.md` §4 and `07-email-integration.md` §7.2.4 answer it: a dedicated free Gmail
   account over `smtp.gmail.com:587` with an App Password, no custom domain, no webhooks, no
   idempotency key on the wire, `mailto:` unsubscribe, and `derive_message_id()` as the
   reconciliation key. `07` §7.2.3 disqualifies Postmark by name — its terms require explicit
   consent per contact and do not permit prospecting — which is why every `postmark` sample in this
   document has been replaced with `gmail`. Nothing here needs a late binding: §5.15.3's transport
   table and §5.17.2's reconciliation are written against the arrangement that exists.

8. **Two renumberings this document is waiting on, both one word long.**
   `01-data-model.md` §1.12.6 and its §1.14 Open question 2 call the merge-candidate block
   "gate D4". In this document D4 has always been `D_CHECKLIST_INCOMPLETE`, and gate codes are
   stored verbatim in `eligibility_snapshot` JSON, so renumbering an existing code would rewrite the
   meaning of every snapshot on disk. The gate is added here as **D6** / `D_UNREVIEWED_DUPLICATE`
   (§5.9.1, §5.9.6) with `01`'s predicate and sentence unchanged; `01` needs the label corrected.
7. **Whether a blocked message inside an approved batch should page Sagar immediately or wait for
   the batch summary.** This document sends a Telegram alert for gate A and gate G family blocks
   only, on the grounds that those mean "somebody asked us to stop" and the others mean "not yet".
   If that is the wrong split, it is one dictionary in `radar/outreach.py`.
