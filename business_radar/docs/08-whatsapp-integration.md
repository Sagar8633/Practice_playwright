# 8. WhatsApp official API integration architecture

This document settles how `business_radar` uses WhatsApp, and — more importantly — how it refuses
to. It states the platform constraint that shapes every other decision here (business-initiated
WhatsApp requires a pre-approved template **and** prior opt-in), specifies the v1 answer
(`MANUAL_LINK`: the system drafts, checks and previews the §25 message, then hands Sagar a
`wa.me` click-to-chat link he sends himself), specifies the v2 answer built behind a hard gate
(`CLOUD_API`: WhatsApp Cloud API with an approved MARKETING template and a recorded opt-in row),
and defines the opt-in ledger, the Indian E.164 normalisation rules, the duplicate-identity
matching §29 requires, the STOP path into `suppressions`, the channel interface that makes
`radar/channels/whatsapp.py` interchangeable with `radar/channels/email.py` from the eligibility
engine's point of view, and the list of things we deliberately do not build. It covers spec §21 and
§25.

**Cross-references.** `05-outreach-workflow.md` owns `outreach_messages`, `outreach_approvals`,
`outreach_events`, `selections`, `suppressions` and `contact_policy`, and owns
`check_send_eligibility()`; this document adds columns and gates to those and never redefines them.
`06-message-engine.md` owns message generation (§22–§26) and the industry vocabulary this
document consumes. `07-email-integration.md` is the sibling channel and shares the interface in
§8.4. `09-response-classification.md` owns `responses`. `10-human-handoff.md` owns `handoffs` and
the Telegram notifier. `01-data-model.md` carries the canonical schema file; where this document
prints DDL for a table it owns, that DDL is the definition.

---

## 8.1 The constraint, stated first

Everything below follows from four facts about Meta's platform. They are not negotiable by
engineering effort, and a design that pretends otherwise ends with a banned number.

| # | Constraint | Consequence for this system |
|---|---|---|
| 1 | A **business-initiated** conversation on the WhatsApp Business Platform may only be started with a **template message that Meta has pre-approved**. Free-form text is allowed only inside an open 24-hour customer service window, and only a message *from the user* opens that window. | We cannot send the fully-personalised §25 prose through the API. We can send a fixed skeleton with three variable slots. See §8.8.5 — this is the single biggest functional difference between the two modes. |
| 2 | Meta's **Business Messaging Policy requires prior opt-in** from the recipient before a business sends them template messages. Meta does not technically verify the opt-in at send time; it enforces it after the fact, through recipient blocks and reports. | Cold-messaging a business that never opted in is a policy violation whether or not the API accepts the call. The API accepting a message is not permission. |
| 3 | The enforcement mechanism is **quality rating and messaging tier**, per phone number, driven by blocks and reports. A number that collects blocks drops to RED, gets its tier cut, then gets restricted, then the WABA is disabled. Appeals exist and mostly fail. | The failure mode is not "some messages bounce". It is "the number and the WhatsApp Business Account are gone", after which re-registering the same business under a new number is itself a policy violation. |
| 4 | Spec §21: *"Do not implement unofficial WhatsApp automation."* `whatsapp-web.js`, Baileys, venom-bot, WPPConnect, Selenium driving `web.whatsapp.com`, Android accessibility-service bots, and every "WhatsApp panel" reseller built on them are out. | There is no code path in `radar/` that drives a WhatsApp client. §8.12 lists what we refuse and what each refusal costs us. |

### 8.1.1 What this means in one sentence

> For a business that has **not** opted in — which is almost every business the research pipeline
> discovers — the only compliant WhatsApp path is a **human typing into his own WhatsApp**, and the
> system's job is to prepare that message perfectly and then get out of the way.

### 8.1.2 The honest risk position

`MANUAL_LINK` is *lower* risk than the API, not *zero* risk, and this document will not pretend
otherwise:

- `wa.me` is Meta's own documented click-to-chat product. Opening it does not send anything; it
  opens a chat window with text pre-filled in the compose box. The human presses send.
- The send is performed by a natural person, from an account the recipient can block and report, in
  the ordinary UI. No API impersonates a business identity; no unofficial client touches the wire.
- **But** WhatsApp's consumer Terms of Service prohibit sending bulk, automated, or unsolicited
  messages. A human sending forty cold introductions a day from one number is still doing the thing
  the ban heuristics look for. Volume discipline (§8.6.7) is part of the design, not a nicety.
- And it is still **cold contact**, so it obeys `suppressions` and `contact_policy` exactly like
  email. There is no "it's just WhatsApp, it's informal" exemption anywhere in this codebase.

---

## 8.2 Two modes, one channel

`outreach_messages.channel = 'WHATSAPP'` in both modes. The mode is a property of the dispatch, not
of the channel, and it lives in `outreach_whatsapp.dispatch_mode`.

| | `MANUAL_LINK` (v1, default) | `CLOUD_API` (v2, gated off) |
|---|---|---|
| Who transmits | Sagar, from his own WhatsApp | The system, via `graph.facebook.com` |
| Message content | Fully personalised §25 prose, generated per business | A pre-approved MARKETING template with 3 variables |
| Requires opt-in row | No (but obeys suppressions and frequency) | **Yes — enforced by a DB trigger** |
| Requires template approval | No | Yes, `whatsapp_templates.status = 'APPROVED'` |
| Delivery receipts | None. Sagar confirms he sent it | `sent` / `delivered` / `read` / `failed` webhooks |
| Inbound replies captured | No. Pasted in by hand (§8.6.8) | Yes, `messages` webhook |
| Cost | Zero | Per delivered template message, India MARKETING rate (§8.8.10) |
| Throughput | Sagar's hands. Cap 15/day (§8.6.7) | Messaging tier: 250 → 1K → 10K → 100K per rolling 24 h |
| Blast radius of a mistake | One WhatsApp account | The WABA, the number, and the business verification |
| Config switch | `contact_policy.whatsapp_enabled = 1` | `contact_policy.whatsapp_api_enabled = 1` (default `0`) |

Both modes go through the identical steps 1–7 of the `05-outreach-workflow.md` pipeline: SELECT,
PREPARE, DRAFT, POLICY CHECK, PREVIEW, APPROVE, QUEUE. They diverge only at step 8, SEND. That is
deliberate — the human approval record, the policy engine and the eligibility gates are the same
objects for both, so there is no cheaper path to a person's phone than there is to their inbox.

### 8.2.1 `SENT_MANUAL` and the canonical status enum

Manual mode needs to record "a human sent this by hand, and confirmed it". The canonical
`outreach_messages.status` enum in `_CONTEXT.md` §6 has no such value and is not being extended.
The reconciliation:

| Concept | Where it lives | Value |
|---|---|---|
| Lifecycle status (canonical, shared by all channels) | `outreach_messages.status` | `SENT` |
| How it was transmitted | `outreach_whatsapp.dispatch_mode` | `MANUAL_LINK` |
| Channel-specific delivery state | `outreach_whatsapp.delivery_state` | `SENT_MANUAL` |
| Provider label for the audit row | `outreach_messages.provider` | `manual_wa` |

So a manually-dispatched WhatsApp message is `status = 'SENT'`, `delivery_state = 'SENT_MANUAL'`,
and it never reaches `DELIVERED`, because nothing can honestly tell us that it was. The mapping is
exhaustive and trigger-enforced in §8.3.8; `05-outreach-workflow.md`'s transition table is untouched.

---

## 8.3 Schema

All DDL below is owned by this document. `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`
are set by `radar/db.py`. Timestamps are UTC ISO-8601 `YYYY-MM-DDTHH:MM:SSZ`. Migrations are
forward-only and numbered; this document occupies `030`–`037`.

### 8.3.1 `whatsapp_optins` — the opt-in ledger

The table that makes §8.1 constraint 2 real. Without a live row here, `CLOUD_API` dispatch is not
merely discouraged; it is rejected by the database.

```sql
-- radar/migrations/030_whatsapp_optins.sql
CREATE TABLE whatsapp_optins (
    id                 TEXT PRIMARY KEY,                 -- opt_...
    business_id        TEXT NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    contact_id         TEXT REFERENCES business_contacts(id),
    wa_e164            TEXT NOT NULL,                    -- '+919876543210', normalised by §8.5

    method             TEXT NOT NULL
                         CHECK (method IN ('EMAIL_REPLY','WEB_FORM','VERBAL',
                                           'INBOUND_WHATSAPP','WRITTEN_DOCUMENT')),
    consent_text       TEXT NOT NULL,                    -- the verbatim words relied on
    evidence_kind      TEXT NOT NULL
                         CHECK (evidence_kind IN ('RESPONSE_ROW','FORM_SUBMISSION',
                                                  'OPERATOR_ATTESTATION','WEBHOOK_EVENT','FILE')),
    evidence_ref       TEXT,                             -- rsp_... | wev_... | msg_... | file path
    evidence_json      TEXT NOT NULL,                    -- JSON, per-method shape in §8.7.2

    captured_at        TEXT NOT NULL,                    -- when consent was actually given
    recorded_at        TEXT NOT NULL
                         DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    recorded_by        TEXT NOT NULL REFERENCES users(id),
    expires_at         TEXT NOT NULL,                    -- captured_at + optin_valid_days

    revoked_at         TEXT,
    revoked_reason     TEXT
                         CHECK (revoked_reason IS NULL OR revoked_reason IN
                                ('STOP_REPLY','STOP_BUTTON','SUPPRESSION','OPERATOR',
                                 'EXPIRED_CLEANUP')),
    revoked_source_ref TEXT,                             -- rsp_/wev_/sup_ id that caused it

    audit_id           TEXT NOT NULL REFERENCES audit_log(id),

    CHECK (captured_at <= recorded_at),
    CHECK (expires_at > captured_at)
);

-- One live opt-in per (business, number). A revoked one stays for the audit trail.
CREATE UNIQUE INDEX ux_wa_optin_live
    ON whatsapp_optins(business_id, wa_e164) WHERE revoked_at IS NULL;
CREATE INDEX ix_wa_optin_number   ON whatsapp_optins(wa_e164, revoked_at);
CREATE INDEX ix_wa_optin_business ON whatsapp_optins(business_id);

-- Consent evidence is append-only. It is the only defence if a recipient complains.
CREATE TRIGGER trg_wa_optin_no_delete
BEFORE DELETE ON whatsapp_optins
BEGIN
    SELECT RAISE(ABORT, 'whatsapp_optins is append-only');
END;

CREATE TRIGGER trg_wa_optin_immutable
BEFORE UPDATE ON whatsapp_optins
WHEN NEW.business_id   <> OLD.business_id
  OR NEW.wa_e164       <> OLD.wa_e164
  OR NEW.method        <> OLD.method
  OR NEW.consent_text  <> OLD.consent_text
  OR NEW.evidence_json <> OLD.evidence_json
  OR NEW.captured_at   <> OLD.captured_at
  OR NEW.recorded_by   <> OLD.recorded_by
  OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'only the revoke columns of whatsapp_optins may be updated, and only once');
END;
```

`expires_at` exists because stale consent is not consent. `contact_policy.whatsapp_optin_valid_days`
defaults to 365 (§8.3.6). An expired row is never deleted — it stays in place, fails the liveness
predicate, and renders on `/business/<id>` as "opt-in expired on {date}".

### 8.3.2 `whatsapp_templates` — the local mirror of Meta's registry

```sql
-- radar/migrations/031_whatsapp_templates.sql
CREATE TABLE whatsapp_templates (
    id                TEXT PRIMARY KEY,                  -- wat_...
    waba_id           TEXT NOT NULL,
    name              TEXT NOT NULL,                     -- lowercase snake_case, Meta's rule
    language          TEXT NOT NULL,                     -- 'en', 'hi', 'mr'
    category          TEXT NOT NULL
                        CHECK (category IN ('MARKETING','UTILITY','AUTHENTICATION')),

    status            TEXT NOT NULL DEFAULT 'LOCAL_DRAFT'
                        CHECK (status IN ('LOCAL_DRAFT','PENDING','APPROVED','REJECTED',
                                          'PAUSED','DISABLED','IN_APPEAL','PENDING_DELETION',
                                          'DELETED')),
    meta_template_id  TEXT,                              -- Meta's numeric id, once submitted
    components_json   TEXT NOT NULL,                     -- exactly what was POSTed to Meta
    body_text         TEXT NOT NULL,                     -- the BODY component, {{n}} intact
    param_names       TEXT NOT NULL,                     -- JSON array, positional order
    param_vocab       TEXT,                              -- JSON: closed vocabulary per param, §8.8.5

    quality_score     TEXT
                        CHECK (quality_score IS NULL OR
                               quality_score IN ('GREEN','YELLOW','RED','UNKNOWN')),
    rejected_reason   TEXT,                              -- Meta's reason string, verbatim
    paused_until      TEXT,
    disabled_at       TEXT,

    submitted_at      TEXT,
    approved_at       TEXT,
    last_synced_at    TEXT,
    created_at        TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at        TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (status <> 'APPROVED' OR meta_template_id IS NOT NULL)
);

CREATE UNIQUE INDEX ux_wa_template_name ON whatsapp_templates(waba_id, name, language);
CREATE INDEX ix_wa_template_status      ON whatsapp_templates(status);
```

`components_json` is stored verbatim rather than reconstructed on demand, because when Meta rejects
a template the only useful debugging artefact is the exact bytes that were submitted.

### 8.3.3 `outreach_whatsapp` — per-message channel state

One row per `outreach_messages` row with `channel = 'WHATSAPP'`. It carries everything that is true
of a WhatsApp message and false of an email, so `outreach_messages` stays channel-neutral.

```sql
-- radar/migrations/032_outreach_whatsapp.sql
CREATE TABLE outreach_whatsapp (
    id                     TEXT PRIMARY KEY,             -- waw_...
    message_id             TEXT NOT NULL UNIQUE
                             REFERENCES outreach_messages(id) ON DELETE CASCADE,
    business_id            TEXT NOT NULL REFERENCES businesses(id),
    contact_id             TEXT REFERENCES business_contacts(id),

    dispatch_mode          TEXT NOT NULL
                             CHECK (dispatch_mode IN ('MANUAL_LINK','CLOUD_API')),
    delivery_state         TEXT NOT NULL DEFAULT 'PENDING'
                             CHECK (delivery_state IN (
                               'PENDING','LINK_ISSUED','AWAITING_MANUAL_DISPATCH','SENT_MANUAL',
                               'MANUAL_ABANDONED','API_ACCEPTED','API_SENT','API_DELIVERED',
                               'API_READ','API_FAILED','API_UNDELIVERED')),

    to_e164                TEXT NOT NULL,                -- '+919876543210'
    wa_id                  TEXT,                         -- Meta's id, '919876543210' for IN
    optin_id               TEXT REFERENCES whatsapp_optins(id),

    template_id            TEXT REFERENCES whatsapp_templates(id),
    template_name          TEXT,
    template_language      TEXT,
    template_params        TEXT,                         -- JSON array, exactly as sent

    rendered_body          TEXT NOT NULL,                -- what a human will read
    rendered_body_hash     TEXT NOT NULL,                -- sha256 hex; must equal the approval's

    -- MANUAL_LINK columns
    wa_link                TEXT,
    wa_link_hash           TEXT,
    link_issued_at         TEXT,
    link_issued_by         TEXT REFERENCES users(id),
    link_view_count        INTEGER NOT NULL DEFAULT 0,
    manual_confirmed_at    TEXT,
    manual_confirmed_by    TEXT REFERENCES users(id),
    manual_edited          INTEGER NOT NULL DEFAULT 0 CHECK (manual_edited IN (0,1)),
    manual_final_body      TEXT,                         -- pasted back when manual_edited = 1
    manual_final_body_hash TEXT,
    manual_note            TEXT,

    -- CLOUD_API columns
    wamid                  TEXT,                         -- 'wamid.HBgM...'
    conversation_id        TEXT,
    conversation_origin    TEXT,                         -- marketing | utility | service | ...
    pricing_billable       INTEGER CHECK (pricing_billable IS NULL OR pricing_billable IN (0,1)),
    pricing_model          TEXT,                         -- 'PMP' | 'CBP' | future values
    pricing_category       TEXT,
    cost_inr_micros        INTEGER,                      -- integer micro-rupees, never a float

    accepted_at            TEXT,
    sent_at                TEXT,
    delivered_at           TEXT,
    read_at                TEXT,
    failed_at              TEXT,
    error_code             INTEGER,
    error_title            TEXT,
    error_detail           TEXT,                         -- JSON, truncated to 4 KB

    created_at             TEXT NOT NULL
                             DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at             TEXT NOT NULL
                             DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- The two hard rules of §8.1, as column constraints.
    CHECK (dispatch_mode <> 'CLOUD_API' OR optin_id    IS NOT NULL),
    CHECK (dispatch_mode <> 'CLOUD_API' OR template_id IS NOT NULL),

    CHECK (delivery_state <> 'SENT_MANUAL'
           OR (manual_confirmed_at IS NOT NULL AND manual_confirmed_by IS NOT NULL)),
    CHECK (manual_edited = 0 OR manual_final_body IS NOT NULL),
    CHECK (delivery_state NOT IN ('API_ACCEPTED','API_SENT','API_DELIVERED','API_READ')
           OR wamid IS NOT NULL),
    CHECK (delivery_state <> 'API_FAILED' OR error_code IS NOT NULL),
    CHECK (dispatch_mode <> 'MANUAL_LINK' OR delivery_state IN
           ('PENDING','LINK_ISSUED','AWAITING_MANUAL_DISPATCH','SENT_MANUAL','MANUAL_ABANDONED'))
);

CREATE UNIQUE INDEX ux_waw_wamid   ON outreach_whatsapp(wamid) WHERE wamid IS NOT NULL;
CREATE INDEX ix_waw_number         ON outreach_whatsapp(to_e164, created_at);
CREATE INDEX ix_waw_state          ON outreach_whatsapp(delivery_state, updated_at);
CREATE INDEX ix_waw_business       ON outreach_whatsapp(business_id, created_at);
CREATE INDEX ix_waw_awaiting       ON outreach_whatsapp(link_issued_at)
                                   WHERE delivery_state = 'AWAITING_MANUAL_DISPATCH';
```

### 8.3.4 `whatsapp_webhook_events` — raw, append-only, replayable

```sql
-- radar/migrations/033_whatsapp_webhook_events.sql
CREATE TABLE whatsapp_webhook_events (
    id                TEXT PRIMARY KEY,                  -- wev_...
    received_at       TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    signature_ok      INTEGER NOT NULL CHECK (signature_ok IN (0,1)),
    field             TEXT NOT NULL,                     -- 'messages', 'account_update', ...
    waba_id           TEXT,
    phone_number_id   TEXT,
    event_key         TEXT NOT NULL,                     -- dedupe key, §8.9.4
    payload           TEXT NOT NULL,                     -- raw request body, verbatim
    payload_purged_at TEXT,                              -- DPDP retention, §8.13.5
    processed_at      TEXT,
    process_result    TEXT
                        CHECK (process_result IS NULL OR process_result IN
                               ('APPLIED','IGNORED_UNKNOWN_FIELD','IGNORED_DUPLICATE',
                                'IGNORED_UNMATCHED','ERROR')),
    process_error     TEXT
);

CREATE UNIQUE INDEX ux_wa_webhook_key ON whatsapp_webhook_events(event_key);
CREATE INDEX ix_wa_webhook_unproc     ON whatsapp_webhook_events(received_at)
                                      WHERE processed_at IS NULL;

CREATE TRIGGER trg_wa_webhook_no_delete
BEFORE DELETE ON whatsapp_webhook_events
BEGIN
    SELECT RAISE(ABORT, 'whatsapp_webhook_events is append-only; purge the payload, keep the row');
END;
```

The handler writes this row and returns `200` **before** interpreting anything. Meta retries
aggressively and treats a slow response as a failure; interpretation happens in a job (§8.13.4).

### 8.3.5 Columns contributed to `business_contacts` (owned by `01-data-model.md`)

| Column | Type / constraint | Purpose |
|---|---|---|
| `phone_e164` | `TEXT` | Normalised form of a `PHONE`/`WHATSAPP` contact; `NULL` when the raw value would not parse. |
| `phone_number_type` | `TEXT CHECK (phone_number_type IS NULL OR phone_number_type IN ('MOBILE','FIXED_LINE','FIXED_LINE_OR_MOBILE','TOLL_FREE','PREMIUM_RATE','VOIP','UNKNOWN','INVALID'))` | libphonenumber's classification. Drives §8.5.4. |
| `wa_capability` | `TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (wa_capability IN ('CONFIRMED','LIKELY','UNKNOWN','UNLIKELY','NOT_ON_WHATSAPP'))` | What we actually know about whether this number receives WhatsApp. `LIKELY` is a guess and is labelled as one in the UI. |
| `wa_capability_source` | `TEXT` | `NUMBER_TYPE` \| `INBOUND_MESSAGE` \| `API_ERROR_131026` \| `OPERATOR` \| `LISTING_WA_BUTTON` |
| `wa_id` | `TEXT` | Meta's identifier, learned from an inbound webhook. Never assumed; see §8.5.5. |
| `phone_norm_version` | `TEXT` | Version of the normalisation ruleset that produced `phone_e164`, so a rule fix can re-run selectively. |

`business_contacts.value_norm` for a `WHATSAPP` or `PHONE` contact **is** the E.164 string, so the
`suppressions.value_norm` comparisons in `05-outreach-workflow.md`'s queries work unchanged.

### 8.3.6 Columns contributed to `contact_policy` (owned by `05-outreach-workflow.md`)

| Column | Type / constraint | Purpose |
|---|---|---|
| `whatsapp_daily_manual_cap` | `INTEGER NOT NULL DEFAULT 15 CHECK (whatsapp_daily_manual_cap >= 0)` | Cold introductions Sagar may send by hand per day. §8.6.7. |
| `whatsapp_daily_api_cap` | `INTEGER NOT NULL DEFAULT 0 CHECK (whatsapp_daily_api_cap >= 0)` | Cloud API cap, independent of Meta's tier. Starts at 0 so enabling the API is two deliberate settings changes, not one. |
| `whatsapp_min_days_between_outreach` | `INTEGER NOT NULL DEFAULT 30 CHECK (whatsapp_min_days_between_outreach >= 0)` | Stricter than the email default of 21. A repeat WhatsApp message is more intrusive than a repeat email. |
| `whatsapp_max_attempts` | `INTEGER NOT NULL DEFAULT 1 CHECK (whatsapp_max_attempts >= 1)` | One cold WhatsApp per business, ever, unless they reply. |
| `whatsapp_optin_valid_days` | `INTEGER NOT NULL DEFAULT 365 CHECK (whatsapp_optin_valid_days >= 1)` | Consent expiry, §8.3.1. |
| `whatsapp_same_number_max` | `INTEGER NOT NULL DEFAULT 1 CHECK (whatsapp_same_number_max >= 1)` | How many businesses sharing one E.164 may be messaged. §8.5.6. |
| `whatsapp_same_number_days` | `INTEGER NOT NULL DEFAULT 180 CHECK (whatsapp_same_number_days >= 0)` | Window for the above. |
| `whatsapp_quality_floor` | `TEXT NOT NULL DEFAULT 'YELLOW' CHECK (whatsapp_quality_floor IN ('GREEN','YELLOW','RED'))` | API sending stops when the number's quality rating falls below this. §8.8.11. |
| `whatsapp_manual_reminder_hours` | `INTEGER NOT NULL DEFAULT 6 CHECK (whatsapp_manual_reminder_hours >= 1)` | How long a link may sit `AWAITING_MANUAL_DISPATCH` before Telegram nags. |

`whatsapp_enabled` and `whatsapp_api_enabled` already exist in `05-outreach-workflow.md` §5.3.1.
`whatsapp_api_enabled` defaults to `0` and there is no UI control that sets it to `1`; see §8.8.12.

### 8.3.7 Id prefixes used here

| Table | Prefix | Source |
|---|---|---|
| `outreach_messages` | `msg_` | `_CONTEXT.md` §2 |
| `responses` | `rsp_` | `_CONTEXT.md` §2 |
| `audit_log` | `aud_` | `_CONTEXT.md` §2 |
| `suppressions` | `sup_` | `05-outreach-workflow.md` §5.3.9 |
| `business_contacts` | `cnt_` | `05-outreach-workflow.md` §5.3.9 |
| `whatsapp_optins` | `opt_` | extension, see Open questions |
| `whatsapp_templates` | `wat_` | extension |
| `outreach_whatsapp` | `waw_` | extension |
| `whatsapp_webhook_events` | `wev_` | extension |

### 8.3.8 `delivery_state` to `outreach_messages.status`

The two are kept in lockstep by one function, and the pairing is trigger-enforced so a future code
path cannot invent a combination.

| `dispatch_mode` | `delivery_state` | `outreach_messages.status` | `businesses.status` effect |
|---|---|---|---|
| either | `PENDING` | `PENDING_APPROVAL` or `APPROVED` | none |
| `MANUAL_LINK` | `LINK_ISSUED` | `QUEUED` | none |
| `MANUAL_LINK` | `AWAITING_MANUAL_DISPATCH` | `QUEUED` | none |
| `MANUAL_LINK` | `SENT_MANUAL` | `SENT` | `CONTACTED` |
| `MANUAL_LINK` | `MANUAL_ABANDONED` | `CANCELLED` | none |
| `CLOUD_API` | `API_ACCEPTED` | `QUEUED` | none |
| `CLOUD_API` | `API_SENT` | `SENT` | `CONTACTED` |
| `CLOUD_API` | `API_DELIVERED` | `DELIVERED` | none |
| `CLOUD_API` | `API_READ` | `DELIVERED` | none |
| `CLOUD_API` | `API_FAILED` | `FAILED` | none |
| `CLOUD_API` | `API_UNDELIVERED` | `FAILED` | none |

`API_READ` maps to `DELIVERED` because the canonical enum has no `READ`, and a read receipt is not a
lifecycle event — it is an engagement signal, recorded in `outreach_whatsapp.read_at` and in an
`outreach_events` row with `event = 'OPENED'`.

```sql
-- radar/migrations/034_whatsapp_state_map.sql
CREATE TABLE whatsapp_delivery_state_map (
    dispatch_mode  TEXT NOT NULL,
    delivery_state TEXT NOT NULL,
    message_status TEXT NOT NULL,
    PRIMARY KEY (dispatch_mode, delivery_state, message_status)
);

INSERT INTO whatsapp_delivery_state_map VALUES
    ('MANUAL_LINK','PENDING','PENDING_APPROVAL'),
    ('MANUAL_LINK','PENDING','APPROVED'),
    ('MANUAL_LINK','LINK_ISSUED','QUEUED'),
    ('MANUAL_LINK','AWAITING_MANUAL_DISPATCH','QUEUED'),
    ('MANUAL_LINK','SENT_MANUAL','SENT'),
    ('MANUAL_LINK','MANUAL_ABANDONED','CANCELLED'),
    ('CLOUD_API','PENDING','PENDING_APPROVAL'),
    ('CLOUD_API','PENDING','APPROVED'),
    ('CLOUD_API','API_ACCEPTED','QUEUED'),
    ('CLOUD_API','API_SENT','SENT'),
    ('CLOUD_API','API_DELIVERED','DELIVERED'),
    ('CLOUD_API','API_READ','DELIVERED'),
    ('CLOUD_API','API_FAILED','FAILED'),
    ('CLOUD_API','API_UNDELIVERED','FAILED');

CREATE TRIGGER trg_waw_state_pairing
AFTER UPDATE OF delivery_state ON outreach_whatsapp
WHEN NOT EXISTS (
        SELECT 1 FROM whatsapp_delivery_state_map m
          JOIN outreach_messages om ON om.id = NEW.message_id
         WHERE m.dispatch_mode  = NEW.dispatch_mode
           AND m.delivery_state = NEW.delivery_state
           AND m.message_status = om.status)
BEGIN
    SELECT RAISE(ABORT, 'outreach_whatsapp.delivery_state does not match outreach_messages.status');
END;
```

Because the trigger is `AFTER UPDATE`, both rows must be written inside one transaction, in either
order. `radar/channels/whatsapp.py` never writes one without the other.

### 8.3.9 The triggers that make un-consented API sending impossible

This is the enforcement point for §8.1 constraint 2. Application code cannot route around it; a
`sqlite3` session opened by hand cannot route around it either, short of dropping the trigger.

```sql
-- radar/migrations/035_whatsapp_optin_enforcement.sql

-- 1. A CLOUD_API row may not exist without a live, unexpired, matching opt-in.
CREATE TRIGGER trg_waw_cloud_needs_optin_ins
BEFORE INSERT ON outreach_whatsapp
WHEN NEW.dispatch_mode = 'CLOUD_API'
 AND NOT EXISTS (SELECT 1 FROM whatsapp_optins o
                  WHERE o.id          = NEW.optin_id
                    AND o.business_id = NEW.business_id
                    AND o.wa_e164     = NEW.to_e164
                    AND o.revoked_at IS NULL
                    AND o.expires_at  > strftime('%Y-%m-%dT%H:%M:%SZ','now'))
BEGIN
    SELECT RAISE(ABORT,
      'CLOUD_API dispatch requires a live unexpired opt-in for this business and number');
END;

-- 2. Re-check at the moment of transmit, not only at draft time. Consent can be revoked in
--    the minutes between approval and send.
CREATE TRIGGER trg_waw_cloud_needs_optin_send
BEFORE UPDATE OF delivery_state ON outreach_whatsapp
WHEN NEW.dispatch_mode = 'CLOUD_API'
 AND NEW.delivery_state IN ('API_ACCEPTED','API_SENT')
 AND NOT EXISTS (SELECT 1 FROM whatsapp_optins o
                  WHERE o.id          = NEW.optin_id
                    AND o.business_id = NEW.business_id
                    AND o.wa_e164     = NEW.to_e164
                    AND o.revoked_at IS NULL
                    AND o.expires_at  > strftime('%Y-%m-%dT%H:%M:%SZ','now'))
BEGIN
    SELECT RAISE(ABORT, 'opt-in is no longer live; CLOUD_API transmit refused');
END;

-- 3. The kill switch is a database fact, not a Python `if`.
CREATE TRIGGER trg_waw_cloud_needs_switch
BEFORE INSERT ON outreach_whatsapp
WHEN NEW.dispatch_mode = 'CLOUD_API'
 AND COALESCE((SELECT whatsapp_api_enabled FROM contact_policy WHERE id = 'GLOBAL'), 0) = 0
BEGIN
    SELECT RAISE(ABORT, 'contact_policy.whatsapp_api_enabled = 0; CLOUD_API dispatch is off');
END;

-- 4. The template must be APPROVED at insert time.
CREATE TRIGGER trg_waw_cloud_needs_approved_template
BEFORE INSERT ON outreach_whatsapp
WHEN NEW.dispatch_mode = 'CLOUD_API'
 AND NOT EXISTS (SELECT 1 FROM whatsapp_templates t
                  WHERE t.id = NEW.template_id AND t.status = 'APPROVED')
BEGIN
    SELECT RAISE(ABORT, 'CLOUD_API dispatch requires an APPROVED template');
END;

-- 5. A live suppression on the number or the business blocks the row outright, in either
--    mode. This duplicates gate H_WA_SUPPRESSED on purpose: gates advise the UI, triggers
--    are the law.
CREATE TRIGGER trg_waw_suppression_block
BEFORE INSERT ON outreach_whatsapp
WHEN EXISTS (SELECT 1 FROM suppressions s
              WHERE s.released_at IS NULL
                AND ( (s.scope = 'BUSINESS' AND s.value_norm = NEW.business_id)
                   OR (s.scope = 'WHATSAPP' AND s.value_norm = NEW.to_e164)
                   OR (s.scope = 'PHONE'    AND s.value_norm = NEW.to_e164) ))
BEGIN
    SELECT RAISE(ABORT, 'a live suppression covers this business or number');
END;
```

Note trigger 5's scope list: a `PHONE` suppression blocks WhatsApp and a `WHATSAPP` suppression
blocks phone, because they are the same person holding the same handset. `_CONTEXT.md` §3 invariant
3 says an opt-out on any contact point blocks every channel; §8.10.4 shows the full fan-out.

---

## 8.4 The channel interface (§21)

§21 lists four channels: `EMAIL`, `WHATSAPP`, `PHONE`, `MANUAL`. The eligibility engine, the policy
engine, the approval flow and the audit trail must treat all four identically, or the invariants in
`_CONTEXT.md` §3 have to be re-proved once per channel. They are made identical by one Protocol.

### 8.4.1 `radar/channels/base.py`

```python
"""The shape every outbound channel must fit into, so the safety machinery is written once.

Without this file, each channel grows its own idea of what "already contacted" and
"opted out" mean, and the day WhatsApp gets a shortcut past the approval row is the day
the whole human-verification design is decorative. The Protocol is deliberately narrow:
a channel normalises an address, says whether it is usable, renders a body, validates it,
transmits it, and translates provider callbacks. It does not decide whether it is allowed
to send. That decision belongs to check_send_eligibility() and to an approval row, and it
is made before dispatch() is ever called.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, runtime_checkable


@dataclass(slots=True, frozen=True)
class NormalisedAddress:
    """The channel-canonical form of a contact point, plus what we know about it."""
    ok: bool
    value_norm: str | None          # goes into business_contacts.value_norm and suppressions
    display: str                    # what a human is shown, e.g. '+91 98765 43210'
    kind: str                       # 'EMAIL' | 'PHONE' | 'WHATSAPP'
    reason: str | None = None       # why ok is False, e.g. 'NOT_MOBILE'
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ChannelAvailability:
    """Can this channel reach this business at all, ignoring policy and frequency?"""
    available: bool
    mode: str | None                # channel-specific: 'SMTP' | 'MANUAL_LINK' | 'CLOUD_API'
    contact_id: str | None
    address: NormalisedAddress | None
    blocking_gate: str | None       # 'H_WA_NOT_MOBILE', 'H_EMAIL_NO_ADDRESS', ...
    reason: str | None              # one sentence, rendered verbatim in the UI
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RenderedMessage:
    subject: str | None             # None for WHATSAPP
    body: str
    body_hash: str                  # sha256 hex of (subject or '') + '\x1e' + body
    char_count: int
    render_meta: dict[str, Any]     # template name, params, model id, prompt_version


@dataclass(slots=True, frozen=True)
class DispatchResult:
    outcome: str                    # ACCEPTED | AWAITING_MANUAL | FAILED | INDETERMINATE
    provider: str                   # 'gmail' | 'null' | 'wa_cloud' | 'manual_wa' | 'manual'
    provider_message_id: str | None
    provider_status_code: int | None
    provider_response: dict[str, Any]
    delivery_state: str | None      # channel-local state, e.g. 'AWAITING_MANUAL_DISPATCH'
    artifact: dict[str, Any] | None # e.g. {'wa_link': 'https://wa.me/...', 'qr_png': b'...'}
    failure_code: str | None
    failure_detail: str | None
    retryable: bool = False


@dataclass(slots=True, frozen=True)
class ChannelEvent:
    """One provider callback, translated into the vocabulary of outreach_events."""
    provider_event_id: str
    message_id: str | None          # msg_..., resolved by the channel from its own keys
    event: str                      # an outreach_events.event value
    at: str                         # ISO-8601 UTC
    detail: dict[str, Any]
    suppression: tuple[str, str, str] | None = None   # (scope, value_norm, reason)
    inbound: dict[str, Any] | None = None             # becomes a `responses` row


@runtime_checkable
class Channel(Protocol):
    name: ClassVar[str]             # 'EMAIL' | 'WHATSAPP' | 'PHONE' | 'MANUAL'
    contact_kinds: ClassVar[tuple[str, ...]]
    suppression_scopes: ClassVar[tuple[str, ...]]
    supports_delivery_receipts: ClassVar[bool]
    supports_inbound_capture: ClassVar[bool]

    def normalise(self, raw: str, *, region: str = "IN") -> NormalisedAddress: ...

    def availability(self, conn, business_id: str, *,
                     cfg, policy) -> ChannelAvailability: ...

    def render(self, conn, draft_id: str, *, cfg) -> RenderedMessage: ...

    def validate(self, rendered: RenderedMessage, *,
                 policy) -> list[str]: ...      # channel-local violations, [] means fine

    def dispatch(self, conn, message_id: str, approval_id: str, *,
                 worker_id: str, cfg) -> DispatchResult: ...

    def parse_callback(self, payload: dict[str, Any], *,
                       headers: dict[str, str], cfg) -> list[ChannelEvent]: ...
```

### 8.4.2 The registry, and why it is a dict and not an `if`

```python
# radar/channels/__init__.py
from .email import EmailChannel
from .whatsapp import WhatsAppChannel
from .phone import PhoneChannel
from .manual import ManualChannel

CHANNELS: dict[str, Channel] = {
    "EMAIL":    EmailChannel(),
    "WHATSAPP": WhatsAppChannel(),
    "PHONE":    PhoneChannel(),
    "MANUAL":   ManualChannel(),
}

def get_channel(name: str) -> Channel:
    """Raise on an unknown channel rather than defaulting to anything.

    A KeyError here is a bug. A default here would be a message sent through the wrong
    channel to the wrong address, which is the one class of bug this project exists to
    make impossible.
    """
    return CHANNELS[name]
```

`radar/outreach.py` calls `get_channel(message.channel).dispatch(...)` and knows nothing else about
WhatsApp. Consequences worth stating:

| Property | How the interface guarantees it for WhatsApp |
|---|---|
| §29 duplicate protection | `check_send_eligibility()` reads `outreach_messages.to_address_norm`, which the channel filled with the E.164. No WhatsApp-specific dedupe code exists. |
| §30 opt-out | `suppression_scopes = ('BUSINESS','WHATSAPP','PHONE')`; the engine's existing suppression join covers it. |
| §31 frequency | `contact_policy` columns in §8.3.6 are read by the same `effective_policy()` merge. |
| §3 invariant 1 | `dispatch()` takes `approval_id` positionally and is only ever called from `send_message()`, which will not run without one. |
| §48 audit | The audit row is written by `radar/outreach.py` from `DispatchResult`, identically for all channels. |

### 8.4.3 Gates this document contributes to `check_send_eligibility()`

`05-outreach-workflow.md` reserves the `H_*` and `I_*` namespaces for per-contact, per-channel
gates. The split used here: **`H_*` blocks the channel**, **`I_*` blocks `CLOUD_API` only and
downgrades the mode to `MANUAL_LINK`** rather than blocking the send.

| Gate | Fires when | Effect |
|---|---|---|
| `H_WA_CHANNEL_DISABLED` | `contact_policy.whatsapp_enabled = 0` | BLOCK |
| `H_WA_NO_NUMBER` | No active, human-verified contact of kind `WHATSAPP` or `PHONE` | BLOCK |
| `H_WA_NOT_E164` | `phone_e164 IS NULL` — the listed number would not parse | BLOCK |
| `H_WA_NOT_MOBILE` | `phone_number_type` in `FIXED_LINE`, `TOLL_FREE`, `PREMIUM_RATE` | BLOCK |
| `H_WA_NOT_ON_WHATSAPP` | `wa_capability = 'NOT_ON_WHATSAPP'` | BLOCK |
| `H_WA_SUPPRESSED` | Live `suppressions` row, scope `BUSINESS`/`WHATSAPP`/`PHONE` | BLOCK |
| `H_WA_SHARED_NUMBER` | The E.164 is listed for more than `whatsapp_same_number_max` businesses messaged inside `whatsapp_same_number_days` (§8.5.6) | BLOCK |
| `H_WA_MIN_DAYS` | Last WhatsApp to this number inside `whatsapp_min_days_between_outreach` | BLOCK |
| `H_WA_MAX_ATTEMPTS` | WhatsApp attempts to this business `>= whatsapp_max_attempts` | BLOCK |
| `H_WA_DAILY_CAP` | Today's `SENT_MANUAL` count `>= whatsapp_daily_manual_cap` (or the API cap in API mode) | BLOCK |
| `H_WA_MANUAL_IN_FLIGHT` | A row is already `AWAITING_MANUAL_DISPATCH` for this business | BLOCK |
| `I_WA_API_DISABLED` | `whatsapp_api_enabled = 0` | DOWNGRADE to `MANUAL_LINK` |
| `I_WA_NO_OPTIN` | No live unexpired `whatsapp_optins` row | DOWNGRADE |
| `I_WA_TEMPLATE_UNAVAILABLE` | No `APPROVED` template for the required language | DOWNGRADE |
| `I_WA_TIER_EXHAUSTED` | Unique recipients in the rolling 24 h `>=` the messaging tier | DOWNGRADE |
| `I_WA_QUALITY_BELOW_FLOOR` | Number quality rating below `whatsapp_quality_floor` | DOWNGRADE |
| `I_WA_ACCOUNT_RESTRICTED` | A live restriction from an `account_update` webhook | DOWNGRADE |

A DOWNGRADE is never silent. It is rendered in the preview's POLICY CHECK panel as, for example,
"Cloud API not available for this business: no recorded opt-in. This message will be sent by you,
by hand." Sagar always knows which mode he is approving.

### 8.4.4 `PHONE` and `MANUAL`, for completeness (§21)

| Channel | v1 behaviour | Why |
|---|---|---|
| `PHONE` | `render()` produces a **call script**, not a message. `dispatch()` never dials; it returns `outcome = 'AWAITING_MANUAL'` and the message parks until `POST /api/v1/outreach/<message_id>/record-manual` logs the call outcome. | TRAI's DND/UCC framework governs commercial calls and SMS to Indian numbers, registration as a telemarketer is required for automated commercial calling, and none of that is worth building for a one-operator tool. A human dialling a published business number is ordinary business conduct. |
| `MANUAL` | Record-only. Used when Sagar met someone at an event or was introduced. `dispatch()` is never called; `POST .../record-manual` creates the message already `APPROVED` then `SENT` in one transaction, with an approval row Sagar signs. | It exists so that §32's outreach history is complete. A contact the system does not know about is a contact the frequency and duplicate gates cannot protect. |

Neither channel is allowed to skip the approval row, and neither is allowed to skip suppression
checks. "Manual" describes the transport, not the permission.

---

## 8.5 Phone numbers: normalisation, capability, identity

The listings the research pipeline reads (business websites, Google Business profiles, IndiaMART,
JustDial, association directories) contain Indian phone numbers written every possible way. Before
any of the §29 duplicate logic can work, they have to become one canonical string.

### 8.5.1 The rules for India (+91)

| Rule | Detail |
|---|---|
| Country code | `+91`. National significant number (NSN) is **10 digits** for both mobile and landline. |
| Trunk prefix | A leading `0` is the national trunk prefix and is stripped: `09876543210` → `+919876543210`. |
| Mobile ranges | NSN starts with `6`, `7`, `8` or `9`. Ten digits. This is the only class we treat as plausibly WhatsApp-capable. |
| Landline | NSN = STD code (without its leading `0`) + subscriber number, totalling 10 digits. Relevant STD codes: Nashik `253`, Jalgaon `257`, Dhule `2562`, Shirpur `2563`, Malegaon `2554`, Pune `20`, Mumbai `22`. |
| Toll-free / service | `1800`, `1860`, `1600` prefixes, and short codes (`1091`, `112`). Never E.164-valid as a mobile, never WhatsApp. |
| Common listing junk | `+91-98765 43210`, `91 9876543210`, `(0253) 2345678`, `98765-43210`, `+91 0 9876543210`, `9876543210 / 9876543211`, `Ph: 0257 2223344 Mob: 9822012345`. |
| Multiple numbers in one field | Split on `/`, `,`, `;`, `and`, `Mob`, `Ph`, `Tel`, newlines — then normalise each independently and store each as its own `business_contacts` row. Never keep a compound string. |
| Extensions | `2345678 Ext 21` — the extension is dropped from `phone_e164` and preserved in `business_contacts.value_raw`. |

### 8.5.2 The implementation

Use `phonenumbers` (the Python port of Google's libphonenumber). Do not hand-roll the ranges; the
Indian numbering plan changes and libphonenumber tracks it.

```python
# radar/channels/whatsapp.py

PHONE_NORM_VERSION = "in-e164-1"

_SPLIT_RE = re.compile(r"[/,;\n]|\band\b|\bmob(?:ile)?\.?\b|\bph(?:one)?\.?\b|\btel\.?\b",
                       re.IGNORECASE)
_EXT_RE = re.compile(r"\b(?:ext|extn|extension)\.?\s*\d+\s*$", re.IGNORECASE)


def split_phone_field(raw: str) -> list[str]:
    """One listing field, many numbers. Returns the candidate substrings, uncleaned.

    Directory listings routinely pack a landline and two mobiles into one cell. Storing
    that string as a contact means the duplicate gate compares '0257 2223344 / 9822012345'
    against itself forever and never matches anything real.
    """


def normalise_in_phone(raw: str, *, region: str = "IN") -> NormalisedAddress:
    """Parse one Indian phone string into E.164, or say precisely why it could not be.

    Returns ok=False with a machine-readable `reason` rather than raising, because the
    research pipeline finds hundreds of unparseable strings a week and every one of them
    needs to survive into the report as 'contact present but unusable', not vanish.

    reason values: EMPTY | TOO_SHORT | NOT_A_NUMBER | INVALID_FOR_REGION | TOLL_FREE |
                   SHORT_CODE | PREMIUM_RATE | NOT_MOBILE
    """
    text = _EXT_RE.sub("", raw or "").strip()
    if not text:
        return NormalisedAddress(False, None, raw, "PHONE", reason="EMPTY")
    try:
        num = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException as exc:
        return NormalisedAddress(False, None, raw, "PHONE",
                                 reason=_PARSE_REASON.get(exc.error_type, "NOT_A_NUMBER"))
    if not phonenumbers.is_valid_number(num):
        return NormalisedAddress(False, None, raw, "PHONE", reason="INVALID_FOR_REGION")

    e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    display = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    ntype = _TYPE_NAMES[phonenumbers.number_type(num)]
    return NormalisedAddress(True, e164, display, "PHONE",
                             meta={"number_type": ntype,
                                   "region": phonenumbers.region_code_for_number(num),
                                   "norm_version": PHONE_NORM_VERSION})
```

`_TYPE_NAMES` maps libphonenumber's `PhoneNumberType` enum onto the `phone_number_type` CHECK
values in §8.3.5. `FIXED_LINE_OR_MOBILE` is kept as its own value rather than collapsed — collapsing
it to `MOBILE` would be inventing a fact.

### 8.5.3 Worked examples (SAMPLE)

All rows below are SAMPLE data. The numbers are illustrative and are not real subscribers.

| Raw listing string (SAMPLE) | `phone_e164` | `phone_number_type` | `wa_capability` | Note |
|---|---|---|---|---|
| `+91 98765 43210` | `+919876543210` | `MOBILE` | `LIKELY` | The common good case. |
| `09876543210` | `+919876543210` | `MOBILE` | `LIKELY` | Trunk prefix stripped. |
| `919876543210` | `+919876543210` | `MOBILE` | `LIKELY` | Country code without `+`. |
| `9876543210` | `+919876543210` | `MOBILE` | `LIKELY` | Bare NSN, region `IN` supplies `+91`. |
| `+91 0 98765 43210` | `+919876543210` | `MOBILE` | `LIKELY` | Trunk prefix after the country code. |
| `0253-2345678` | `+912532345678` | `FIXED_LINE` | `UNLIKELY` | Nashik landline. Blocked by `H_WA_NOT_MOBILE`. |
| `02562 234567` | `+912562234567` | `FIXED_LINE` | `UNLIKELY` | Dhule landline. |
| `1800 123 4567` | `+911800123456` (invalid) | `TOLL_FREE` | `UNLIKELY` | `ok=False`, reason `TOLL_FREE`. |
| `0257 2223344 / 9822012345` | two rows | `FIXED_LINE`, `MOBILE` | `UNLIKELY`, `LIKELY` | Split first, then normalise. |
| `+91 98765 4321` | — | — | — | `ok=False`, reason `INVALID_FOR_REGION` (9 digits). |
| `Contact us` | — | — | — | `ok=False`, reason `NOT_A_NUMBER`. |

### 8.5.4 What we can and cannot know about WhatsApp capability

This is where honesty matters more than cleverness. **There is no legitimate way to ask "is this
number on WhatsApp?" without messaging it.** The old On-Premises `/contacts` endpoint that answered
that question is gone, the Cloud API has no replacement, and every third-party "WhatsApp number
checker" is either scraping `wa.me` (rate-limited, against the terms) or running an unofficial
client (§8.12). So `wa_capability` records evidence, never a lookup:

| `wa_capability` | Set by | Meaning |
|---|---|---|
| `CONFIRMED` | An inbound message arrived from this number, or a `delivered` status came back | We have seen WhatsApp work on this number. |
| `LIKELY` | `phone_number_type = 'MOBILE'` | An Indian mobile. Most are on WhatsApp. This is a prior, not a fact, and the UI says "likely". |
| `UNKNOWN` | `FIXED_LINE_OR_MOBILE`, or a mobile we have never touched and Sagar has not looked at | Default. |
| `UNLIKELY` | `FIXED_LINE`, `TOLL_FREE`, `PREMIUM_RATE` | A landline *can* be registered on the WhatsApp Business app via the voice-call verification path, so this is "unlikely", not "impossible". It still fails gate `H_WA_NOT_MOBILE`, because guessing wrong means messaging a switchboard. |
| `NOT_ON_WHATSAPP` | Cloud API error `131026`, or Sagar clicked the link and WhatsApp said the number is not registered | Terminal for this channel. The contact stays active for `EMAIL`/`PHONE`. |

One more legitimate evidence source: if the business's own website or Google Business profile
carries a "Chat on WhatsApp" button, the discovery pipeline records
`wa_capability_source = 'LISTING_WA_BUTTON'` and `wa_capability = 'CONFIRMED'`, with the source URL
stored in `sources` like any other finding. A business advertising a WhatsApp number is the closest
thing to an invitation that exists short of a real opt-in — but note carefully: **it is still not
an opt-in** for §8.7 purposes. It tells us the number works; it does not tell us they want to hear
from us.

### 8.5.5 `wa_id` is not the E.164

Meta's `wa_id` is usually the E.164 without the `+`, but not always — some countries insert or drop
a digit (Argentina's `9`, Mexico's historical `1`). India has no such quirk today, so
`wa_id == e164.lstrip('+')` holds for every number this system will touch. The code still does not
assume it:

```python
def wa_id_for(e164: str) -> str:
    """Best-effort wa_id from an E.164. Correct for +91; a guess everywhere else.

    Stored as a guess and overwritten the first time a webhook tells us the real one. The
    duplicate-identity check in §8.5.6 matches on E.164 first and wa_id second, so a wrong
    guess costs nothing.
    """
    return e164.lstrip("+")
```

`outreach_whatsapp.wa_id` and `business_contacts.wa_id` are only ever *trusted* when
`wa_capability_source = 'INBOUND_MESSAGE'`.

### 8.5.6 Duplicate-identity matching (§29)

§29 requires a pre-send check on: same business, same email, same phone, **same WhatsApp identifier
where supported**, recent campaign, previous response, opt-out. The WhatsApp-specific parts:

```sql
-- radar/channels/whatsapp.py :: WA_DUPLICATE_SQL
-- Parameters: :business_id, :e164, :wa_id, :same_number_cutoff, :min_days_cutoff
WITH by_number AS (
    SELECT w.business_id,
           MAX(om.sent_at)  AS last_sent_at,
           COUNT(*)         AS n_sent
      FROM outreach_whatsapp w
      JOIN outreach_messages om ON om.id = w.message_id
     WHERE om.status IN ('SENT','DELIVERED')
       AND (w.to_e164 = :e164 OR (w.wa_id IS NOT NULL AND w.wa_id = :wa_id))
       AND om.sent_at > :same_number_cutoff
     GROUP BY w.business_id
),
shared AS (                       -- the same handset listed against other businesses
    SELECT COUNT(DISTINCT c.business_id) AS n_businesses
      FROM business_contacts c
     WHERE c.phone_e164 = :e164
       AND c.is_active = 1
)
SELECT (SELECT n_businesses FROM shared)                                    AS n_businesses_sharing,
       (SELECT COUNT(*)  FROM by_number)                                    AS n_businesses_messaged,
       (SELECT SUM(n_sent) FROM by_number)                                  AS n_messages,
       (SELECT MAX(last_sent_at) FROM by_number)                            AS last_sent_at_any,
       (SELECT last_sent_at FROM by_number WHERE business_id = :business_id) AS last_sent_at_this;
```

Interpretation, in `check_send_eligibility()`:

| Condition | Gate | Rationale |
|---|---|---|
| `last_sent_at_this > :min_days_cutoff` | `H_WA_MIN_DAYS` | We already messaged *this* business on WhatsApp recently. |
| `n_businesses_messaged >= whatsapp_same_number_max` and this business is not among them | `H_WA_SHARED_NUMBER` | Three clinics in one building share a reception number. Messaging the third one is the same person's phone buzzing for the third time. |
| `n_businesses_sharing > 1` | not a block, a **warning panel** in the preview | Sagar sees "This number is also listed for 2 other businesses in this campaign" before he approves. |
| A live `suppressions` row on the E.164 | `H_WA_SUPPRESSED` | Opt-out is per-number, and therefore automatically covers every business that lists it. |

The last row is the important one, and it is the reason suppression scope `WHATSAPP` stores the
E.164 rather than a business id: one person saying "stop" stops all of it.

### 8.5.7 Where normalisation runs

| Point | Action |
|---|---|
| Discovery / research (`radar/discover.py`, `radar/research.py`) | Every scraped phone string is split and normalised before a `business_contacts` row is written. The raw string is preserved in `value_raw`. |
| Human verification (`/verify/<id>`, §16 checklist item "Contact information appears to be a legitimate business contact") | The verification screen shows raw and normalised side by side. Sagar ticking the box sets `human_verified = 1`. |
| Contact editor on `/business/<id>` | Re-normalises on save, bumps `phone_norm_version`. |
| A `phone_norm_version` bump | Job `wa_renormalise_contacts` re-runs the parser over rows with an older version and writes an `audit_log` row for every value that changed. Numbers never change silently. |

---

## 8.6 `MANUAL_LINK` — the v1 answer

### 8.6.1 The flow

```
  steps 1-7 of 05-outreach-workflow.md, unchanged
  SELECT -> PREPARE -> DRAFT -> POLICY CHECK -> PREVIEW -> APPROVE -> QUEUE
                                                                       │
                                       outreach_messages.status = QUEUED│
                                       outreach_whatsapp.delivery_state │
                                                        = 'PENDING'     │
                                                                        ▼
  8a. LINK ISSUE ....... POST /api/v1/outreach/<message_id>/whatsapp-link
      session auth only   builds wa.me URL from the APPROVED body, verifies the hash
                          delivery_state = LINK_ISSUED -> AWAITING_MANUAL_DISPATCH
                          outreach_events: SEND_ATTEMPT (actor_type = HUMAN)
                                                                        ▼
  8b. HUMAN SENDS ...... Sagar clicks. WhatsApp Desktop/Web/phone opens the chat with
                         the text pre-filled. He reads it once more and presses send.
                         The system observes nothing here. This is the point.
                                                                        ▼
  9.  CONFIRM .......... POST /api/v1/outreach/<message_id>/record-manual
                         {"sent": true, "edited": false}
                         delivery_state = SENT_MANUAL, status = SENT
                         businesses.status = CONTACTED
                         outreach_events: MANUAL_RECORDED, SENT
                         audit_log row (§48)
```

If Sagar never confirms, the message stays `QUEUED` / `AWAITING_MANUAL_DISPATCH` forever until he
either confirms or abandons it. Nothing times it out into `SENT`. A message the system is not sure
was sent is never recorded as sent — §29's duplicate protection depends on that number being true.

### 8.6.2 Building the link

```python
# radar/channels/whatsapp.py

WA_LINK_BASE = "https://wa.me/"
WA_MAX_BODY_CHARS = 1024          # parity with the Cloud API template body limit
WA_MAX_ENCODED_BYTES = 1800       # keeps the URL under the practical OS/browser handoff limit


def build_wa_link(e164: str, body: str) -> str:
    """The wa.me click-to-chat URL for one message.

    wa.me wants the number with no '+', no spaces, no dashes and no leading zeros, and
    the text percent-encoded with nothing left safe - a literal '&' or '#' in the body
    truncates the message in the recipient's compose box, which is the sort of bug that
    only ever shows up on the one message that mattered.
    """
    digits = e164.lstrip("+")
    if not digits.isdigit():
        raise ValueError(f"not an E.164 number: {e164!r}")
    if len(body) > WA_MAX_BODY_CHARS:
        raise ValueError(f"body is {len(body)} chars, limit {WA_MAX_BODY_CHARS}")
    encoded = urllib.parse.quote(body, safe="")
    if len(encoded.encode("utf-8")) > WA_MAX_ENCODED_BYTES:
        raise ValueError("encoded body exceeds the safe URL length")
    return f"{WA_LINK_BASE}{digits}?text={encoded}"
```

Encoding facts that matter in practice:

| Character | Encodes to | Why it matters |
|---|---|---|
| newline | `%0A` | The §25 message has paragraph breaks; they survive. |
| space | `%20` | `+` is not decoded as a space by the WhatsApp handler; never use `quote_plus`. |
| `&` | `%26` | Un-encoded, everything after it is lost. |
| `#` | `%23` | Un-encoded, everything after it is dropped by the browser before the request. |
| `₹` | `%E2%82%B9` | UTF-8 percent-encoding, three bytes. Counts against `WA_MAX_ENCODED_BYTES`. |

A `SAMPLE` link, wrapped for readability — in the UI it is one unbroken string:

```
https://wa.me/919876543210?text=Hello%20ABC%20Hospital%20team%2C%20I%20work%20on%20
customised%20business-management%20software%20for%20established%20businesses.%0A%0AI%20
came%20across%20your%20organisation%20while%20researching%20businesses%20in%20Dhule...
```

The link is also rendered as a QR code so Sagar can send from the phone that holds the account
without retyping anything:

```python
def build_wa_qr(link: str) -> bytes:
    """PNG of the wa.me link, generated offline with `segno`.

    Offline matters: the exported report and the preview page are self-contained per
    _CONTEXT.md §2, and a QR image fetched from an external chart API would leak every
    prospect's phone number to a third party on page render.
    """
```

### 8.6.3 The §25 message

§25 gives the skeleton. `06-message-engine.md` owns generation; this document owns the
channel-local constraints the generator must satisfy:

| Constraint | Value | Reason |
|---|---|---|
| Max body | 1024 characters | Parity with the Cloud API template body limit, so a message drafted in manual mode can be re-expressed as template parameters later without a rewrite. |
| Target body | 400–700 characters | Longer reads as a broadcast. WhatsApp shows roughly the first 3 lines before "Read more". |
| Paragraphs | 3–4, blank line separated | The first paragraph must stand alone, because it is all most recipients see in the notification. |
| No subject | — | `RenderedMessage.subject is None` for `WHATSAPP`; the `outreach_messages` CHECK only requires `subject_final` for `EMAIL`. |
| No links in the first message | enforced by `validate()` | A cold WhatsApp with a link is the exact shape of a phishing message and gets reported. The demo link goes in the reply, after they answer. |
| No attachments, no images | enforced by `validate()` | Same reason, and `wa.me` cannot carry them anyway. |
| Opt-out line | mandatory, last line before the sign-off | See §8.10.2. |
| Greeting | Business name, never a personal name, unless `business_contacts.person_name` is `human_verified` | Guessing a proprietor's name from a listing and getting it wrong is worse than not using one. |

Rendered SAMPLE for a SAMPLE business (ABC Hospital, Dhule, `HEALTHCARE`/`HOSPITAL`, opportunity 86):

```text
Hello ABC Hospital team, I work on customised business-management software for
established businesses.

I came across your organisation while researching healthcare providers in Dhule.
Based on the nature of your operations, I believe a centralised system for patient
records, appointments and billing could improve day-to-day visibility and reporting.

We have a working demonstration built for this type of organisation. If it is
relevant, I can share a short demo and explain how it could be shaped around your
existing workflow.

Reply STOP and I will not message you again.

Regards, Sagar
```

Note what the message does **not** say. It does not claim to know how they currently manage
appointments; §23's bad example ("We noticed that you are managing your hospital through Excel") is
exactly the claim the policy engine rejects. "Based on the nature of your operations" is the hedge
that `radar/policy.py` requires around an `INFERRED` finding, and "patient records, appointments and
billing" comes from §26's `HOSPITAL` vocabulary, which is an attribute of the category rather than a
claim about this business.

### 8.6.4 The policy engine runs identically

Manual mode has no template pre-approval, so `radar/policy.py` is the **only** content gate between
an LLM and a stranger's phone. It therefore runs with exactly the same strictness as for email, plus
the channel-local `validate()` checks:

```python
def validate(self, rendered: RenderedMessage, *, policy) -> list[str]:
    """WhatsApp-local content rules, on top of the shared claim check in radar/policy.py.

    Returns violation codes, empty list means clean. These are the rules that are about
    the medium rather than about truth: a claim check cannot tell you that a URL in a
    cold WhatsApp gets you reported, but ten years of people reporting cold WhatsApps can.
    """
    # WA_TOO_LONG            len(body) > 1024
    # WA_NO_OPTOUT_LINE      the opt-out sentence is missing
    # WA_CONTAINS_URL        any http:// https:// wa.me www. or bare domain
    # WA_CONTAINS_PHONE      a phone number in the body (invites a callback loop)
    # WA_ALL_CAPS_RUN        6+ consecutive uppercase words
    # WA_EMOJI               any emoji; the house style has none
    # WA_PRICE_CLAIM         a currency figure in a first-touch message
    # WA_URGENCY             'limited time', 'act now', 'offer expires', 'last chance'
    # WA_GREETING_MISMATCH   greeting name not equal to businesses.name or a verified person_name
```

A `POLICY_BLOCKED` message cannot have a link issued: `POST .../whatsapp-link` re-reads
`outreach_messages.status` and refuses anything that is not `QUEUED`.

### 8.6.5 The preview panel (§27)

§27's nine panels are rendered by `05-outreach-workflow.md`'s preview screen. WhatsApp adds a tenth,
between GENERATED MESSAGE and POLICY CHECK:

```
┌─ HOW THIS WILL BE SENT ───────────────────────────────────────────────────────┐
│  Mode        MANUAL — you will send this yourself                             │
│  Why         No opt-in on record for this business, so the WhatsApp Business   │
│              API cannot be used. (I_WA_NO_OPTIN)                              │
│  To          +91 98765 43210   (SAMPLE)                                       │
│              Listed on: abchospital-sample.in/contact, checked 2026-08-23      │
│              Type: MOBILE · WhatsApp: LIKELY (not confirmed)                   │
│  Shared      This number is also listed for 1 other business in this campaign  │
│  From        Your WhatsApp Business number ending 4417                         │
│  Today       6 of 15 manual WhatsApp messages used                             │
│                                                                               │
│  On CONFIRM & SEND this system will NOT send anything. It will give you a      │
│  link. Opening the link puts this exact text in a WhatsApp chat window. You    │
│  press send. Then come back and confirm.                                      │
└───────────────────────────────────────────────────────────────────────────────┘
```

The last paragraph is not decoration. The §28 confirmation sentence for WhatsApp manual mode is
stored verbatim in `outreach_approvals.confirmation_text` and reads:

> You are about to contact this business using the selected business contact. This system will not
> send the message — it will give you a WhatsApp link and you will send it yourself from your own
> account.

### 8.6.6 Endpoints and payloads

```http
POST /api/v1/outreach/msg_01JB2X8P00000000000000M1/whatsapp-link
Cookie: session=...                       # session auth only; no API token may call this
Content-Type: application/json

{ "confirm_token": "b4d1f0a2c8e94a6f", "reissue": false }
```

```json
{
  "message_id": "msg_01JB2X8P00000000000000M1",
  "delivery_state": "AWAITING_MANUAL_DISPATCH",
  "to_display": "+91 98765 43210",
  "wa_link": "https://wa.me/919876543210?text=Hello%20ABC%20Hospital%20team%2C...",
  "wa_link_hash": "3f9a2c...",
  "qr_png_data_uri": "data:image/png;base64,iVBORw0KGgo...",
  "body_preview": "Hello ABC Hospital team, I work on customised business-management...",
  "body_hash": "9c1e77...",
  "expires_at": null,
  "issued_at": "2026-08-27T06:41:12Z",
  "view_count": 1,
  "reminder_at": "2026-08-27T12:41:12Z"
}
```

Rules for this endpoint:

1. It re-runs `check_send_eligibility(stage=SEND)` first. An approval that was valid ten minutes ago
   is not a licence — a suppression may have landed in between.
2. It verifies `sha256(rendered_body) == outreach_approvals.approved_body_hash`. If the body has
   changed by one character since approval, it refuses with `409 BODY_CHANGED_SINCE_APPROVAL`.
3. `reissue: true` is allowed (Sagar closed the tab, the QR did not scan) and increments
   `link_view_count`, writing an `outreach_events` row each time. A link issued six times without a
   confirmation is visible in the audit and worth Sagar's attention.
4. The link is **never** placed in the exported HTML report, in an email, or in a Telegram message.
   It exists only inside an authenticated page. §19's "no send control on the raw research result"
   would be defeated by a report that carried click-to-send links.

```http
POST /api/v1/outreach/msg_01JB2X8P00000000000000M1/record-manual
Content-Type: application/json

{
  "sent": true,
  "sent_at": "2026-08-27T06:44:03Z",
  "edited": true,
  "final_body": "Hello ABC Hospital team, I work on customised business-management software...",
  "note": "Removed the last line, felt long in the chat window.",
  "confirm_token": "b4d1f0a2c8e94a6f"
}
```

```json
{
  "message_id": "msg_01JB2X8P00000000000000M1",
  "status": "SENT",
  "delivery_state": "SENT_MANUAL",
  "manual_edited": true,
  "manual_final_body_hash": "7ab30d...",
  "business_status": "CONTACTED",
  "audit_id": "aud_01JB2X8P0000000000000A7",
  "events": ["MANUAL_RECORDED", "SENT"]
}
```

The `edited` flag is the honest part. Sagar can and will tweak the text in the WhatsApp compose box
before pressing send. If he says he did, the system asks for the final text, hashes it, and stores
it as `manual_final_body`. §49's message audit then shows the drafted text, the approved text, and
the text a human actually sent, which are three different things and all three matter.

`{"sent": false, "reason": "NOT_ON_WHATSAPP"}` sets `delivery_state = 'MANUAL_ABANDONED'`,
`status = 'CANCELLED'`, and — for `NOT_ON_WHATSAPP` — writes
`business_contacts.wa_capability = 'NOT_ON_WHATSAPP'` with source `OPERATOR`. Other reasons:
`CHANGED_MY_MIND`, `WRONG_NUMBER`, `BUSINESS_CLOSED`, `LOOKS_PERSONAL`.

### 8.6.7 Volume discipline

The design constrains Sagar, on purpose, because the ban heuristics do not care that a human pressed
the button:

| Control | Default | Enforcement |
|---|---|---|
| Manual WhatsApp per day | 15 | Gate `H_WA_DAILY_CAP`, counted over `SENT_MANUAL` in the last 24 h |
| One `AWAITING_MANUAL_DISPATCH` at a time per business | — | Gate `H_WA_MANUAL_IN_FLIGHT` |
| Cold WhatsApp attempts per business | 1 | `whatsapp_max_attempts = 1` |
| Days between WhatsApp touches | 30 | `whatsapp_min_days_between_outreach` |
| Which number Sagar uses | A dedicated business number, **not** his primary personal number, running the free WhatsApp Business app | Not enforceable in code. Documented in `16-mvp-plan.md`'s setup checklist and repeated in `/settings`. |
| Broadcast lists | Never | Not enforceable in code. Stated here so it is on the record: a broadcast list is bulk messaging, is a ban trigger, and defeats the per-business personalisation that is the entire point. |

Two facts behind the "dedicated number" rule. First, a WhatsApp ban takes the account, not just the
outreach — years of personal chats disappear with it. Second, the number used for manual mode
**must not be the number later registered on the Cloud API**: registering a number for Cloud API
requires deleting it from the WhatsApp Business app first, which is irreversible and destroys that
history too. Plan for two numbers from day one.

### 8.6.8 What manual mode does not give us

Stated plainly, because every one of these is a real capability loss and pretending otherwise leads
to a report full of blanks nobody can explain:

| Missing | Consequence | Mitigation |
|---|---|---|
| Delivery receipts | `outreach_messages.status` stops at `SENT`. The §36 dashboard's "Delivered" figure is `—` for WhatsApp, never `0` (`_CONTEXT.md` §3 invariant 5). | None available. The report labels the column "Delivered (email only)". |
| Read receipts | No open-rate equivalent. | None. |
| Automatic reply capture | A reply lands in Sagar's WhatsApp and nowhere else. Without action it never becomes a `responses` row, so §33 classification and §34 handoff never fire — the most valuable event in the system evaporates. | `POST /api/v1/responses/manual` (§8.10.5), reachable in two clicks from `/business/<id>`, plus a daily Telegram nudge listing WhatsApp messages sent 1–7 days ago with no recorded response. |
| Proof of what was sent | Sagar may have edited the text. | The `edited` + `final_body` capture in §8.6.6. |
| Scale | 15/day is 15/day. A 200-business campaign is two weeks of WhatsApp, or an email campaign plus WhatsApp for the top 30 by opportunity score. | This is a feature, given §54: optimise for qualified conversations, not messages sent. |
| Bounce/invalid-number signal | If the number is not on WhatsApp, only Sagar sees the error. | The `NOT_ON_WHATSAPP` abandon reason feeds `wa_capability` so the number is not offered again. |

### 8.6.9 Why this is compliant, in the terms the platform actually uses

| Meta rule | How manual mode sits with it |
|---|---|
| Business-initiated conversations require an approved template | Not engaged. No WhatsApp Business Account is involved; this is a person messaging from a normal account. |
| Business Messaging Policy opt-in requirement | The Business Messaging Policy governs the WhatsApp Business Platform. Manual mode does not use it. The *spirit* of the rule still binds this system: suppressions, frequency caps and one-attempt-per-business apply. |
| Terms of Service: no automated or bulk messaging | The system automates drafting, not sending. No code sends a WhatsApp message, no code drives a WhatsApp client, and the volume caps keep the human below anything that looks like bulk. |
| Terms of Service: no unsolicited messaging | **Not fully satisfied, and we say so.** This is cold outreach. The mitigation is that it is low-volume, individually personalised, from a blockable identity, with a working opt-out, honoured permanently. |
| No impersonation | The message says who Sagar is in the first sentence and is sent from his own account. |

The honest summary: manual mode moves the risk from "platform enforcement against a business
account" to "an individual being blocked or reported like any other cold contact". That is a
category of risk a solo consultant already carries when he cold-calls, and it is bounded.

---

## 8.7 The opt-in ledger

The gate between v1 and v2. Everything in §8.8 is unreachable for a business without a row here.

### 8.7.1 What counts as an opt-in

| `method` | What it is | Minimum evidence | Strength |
|---|---|---|---|
| `INBOUND_WHATSAPP` | The business messaged our WABA number first (including via a "Chat on WhatsApp" button on our site, or a click-to-WhatsApp entry point) | The `wev_` webhook event id and the inbound message body | Strongest. It also opens the 24-hour service window, so the first reply need not be a template at all. |
| `EMAIL_REPLY` | A reply to Sagar's outreach email that affirmatively asks for WhatsApp | The `rsp_` id, the verbatim sentence, the sender address, `received_at` | Strong, and the realistic path for this system: email first, WhatsApp only for the people who answered. |
| `WEB_FORM` | A form on Sagar's site with an un-pre-ticked checkbox that names WhatsApp and names his business | Full form payload, submission timestamp, source IP, the exact checkbox label as rendered | Strong if the label is right. See §8.7.3. |
| `WRITTEN_DOCUMENT` | A signed engagement letter, an email thread, a WhatsApp message from them saying "send it here" | Scanned file or message id, stored under `data/optin_evidence/` | Strong. |
| `VERBAL` | Sagar spoke to them and they said yes | Sagar's attestation: who said it, their role, when, the words used, the number they gave | **Weakest.** Accepted, flagged, and shown as "verbal, recorded by Sagar" everywhere it appears. |

What does **not** count, and the system must never let any of these create a row:

- The number being published on their website, a directory or a signboard.
- A "Chat on WhatsApp" button on *their* site. That is an invitation to their customers, not to a
  software vendor.
- Their having replied to a previous message with something other than consent. "Who is this?" is
  not opt-in.
- An unrelated business relationship, a shared acquaintance, or an industry association membership.
- Inferring consent from a `research_findings` row of any `kind`. Consent is not a finding.

### 8.7.2 Evidence shapes

`evidence_json` is validated against a per-method JSON schema at write time. Rejected writes fail
loudly; an opt-in row with unusable evidence is worse than no row, because it looks like protection.

```json
// method = EMAIL_REPLY   (SAMPLE)
{
  "response_id": "rsp_01JB2X8P0000000000000R3",
  "message_id": "msg_01JB2X8P00000000000000M1",
  "from_address": "admin@abchospital-sample.in",
  "received_at": "2026-08-25T11:02:44Z",
  "quote": "Yes please share the details on WhatsApp - 98765 43210",
  "quote_offset": [0, 58],
  "classification": "MORE_INFORMATION",
  "number_extracted_from": "REPLY_BODY"
}
```

```json
// method = VERBAL   (SAMPLE)
{
  "spoke_to_name": "Dr. R. Patil",
  "spoke_to_role": "Administrator",
  "spoken_at": "2026-08-26T09:15:00Z",
  "words_used": "Send it on WhatsApp to this number, it is easier for me.",
  "number_given_verbally": true,
  "call_initiated_by": "SAGAR",
  "attested_by": "usr_01JB2X8P0000000000000U1",
  "attestation": "I confirm this consent was given to me directly and I have recorded it accurately."
}
```

```json
// method = INBOUND_WHATSAPP   (SAMPLE)
{
  "webhook_event_id": "wev_01JB2X8P0000000000000W9",
  "wamid": "wamid.HBgMOTE5ODc2NTQzMjEwFQIAEhggMEE...",
  "from_wa_id": "919876543210",
  "profile_name": "ABC Hospital",
  "body": "Hi, saw your website. Can you send details here?",
  "received_at": "2026-08-25T14:30:11Z"
}
```

### 8.7.3 The web form, if it is ever built

If Sagar adds a "Request a demo" form, the WhatsApp checkbox must be unticked by default and must
read approximately:

> [ ] You may contact me on WhatsApp at this number about **Sagar's business-management software**.
> I understand I can reply STOP at any time.

Three requirements, all of them Meta's: the business must be **named**, the **purpose** must be
stated, and the box must not be pre-ticked. A bundled "I agree to be contacted" checkbox that does
not say WhatsApp does not create a WhatsApp opt-in, and the form handler must not write one.

### 8.7.4 Capture, expiry, revocation

```http
POST /api/v1/businesses/biz_01JB2X8P0000000000000B1/whatsapp-optin
Content-Type: application/json

{
  "wa_e164": "+919876543210",
  "contact_id": "cnt_01JB2X8P0000000000000C1",
  "method": "EMAIL_REPLY",
  "consent_text": "Yes please share the details on WhatsApp - 98765 43210",
  "captured_at": "2026-08-25T11:02:44Z",
  "evidence_kind": "RESPONSE_ROW",
  "evidence_ref": "rsp_01JB2X8P0000000000000R3",
  "evidence_json": { "...": "as in 8.7.2" }
}
```

```json
{
  "optin_id": "opt_01JB2X8P0000000000000O1",
  "business_id": "biz_01JB2X8P0000000000000B1",
  "wa_e164": "+919876543210",
  "method": "EMAIL_REPLY",
  "captured_at": "2026-08-25T11:02:44Z",
  "expires_at": "2027-08-25T11:02:44Z",
  "recorded_by": "usr_01JB2X8P0000000000000U1",
  "audit_id": "aud_01JB2X8P0000000000000A3",
  "live": true
}
```

```python
# radar/channels/whatsapp.py

def record_optin(conn, *, business_id: str, wa_e164: str, method: str,
                 consent_text: str, captured_at: str, evidence_kind: str,
                 evidence_ref: str | None, evidence_json: dict[str, Any],
                 recorded_by: str, contact_id: str | None = None,
                 cfg) -> str:
    """Write one opt-in row, its audit row, and nothing else. Returns the opt_... id.

    Refuses, loudly, when: the number does not normalise to the E.164 given; a live
    suppression covers the business or the number (an opt-out outranks a later opt-in, and
    clearing one is a manual DB operation by design); a live opt-in already exists;
    evidence_json fails the per-method schema; captured_at is in the future; or method is
    VERBAL and recorded_by is not a human session.

    The suppression rule is the one people argue with. It stands: if a business said stop
    and then someone believes they said yes again, that is a conversation for a human and a
    deliberate DB operation, not an API call that silently reverses an opt-out.
    """


def live_optin(conn, business_id: str, wa_e164: str, *, now: str) -> Optin | None:
    """The one query the send path trusts. Mirrors trg_waw_cloud_needs_optin_ins exactly."""


def revoke_optin(conn, optin_id: str, *, reason: str, source_ref: str | None,
                 actor: str) -> None:
    """Mark an opt-in revoked. Called by the STOP handler, by suppression creation, and by
    Sagar. Never un-revokes; the immutability trigger sees to that."""
```

```sql
-- the liveness predicate, written once, used by the trigger, the gate and the UI
-- Parameter :now is bound by the caller so this ports to Postgres unchanged.
SELECT o.*
  FROM whatsapp_optins o
 WHERE o.business_id = :business_id
   AND o.wa_e164     = :wa_e164
   AND o.revoked_at IS NULL
   AND o.expires_at  > :now;
```

### 8.7.5 Audit and display

- Every write to `whatsapp_optins` produces an `audit_log` row with `action = 'WA_OPTIN_RECORDED'`
  or `'WA_OPTIN_REVOKED'`, `entity_id` = the `opt_` id, and the actor. `audit_id` on the opt-in row
  is `NOT NULL`, so an opt-in without an audit trail cannot be inserted at all.
- `/business/<id>` renders an "Opt-in" panel: method, who recorded it, when consent was given (not
  when it was typed in), the verbatim `consent_text`, the evidence link, expiry, and status. A
  `VERBAL` row carries a visible "recorded by Sagar, not independently evidenced" marker.
- `/settings` shows the full ledger with a filter for expiring-within-30-days.
- Under India's DPDP Act 2023, this row is the record of consent and the record of purpose. It is
  also the first thing to produce if a recipient ever complains, which is why the evidence columns
  are append-only.

### 8.7.6 The hard rule

> `CLOUD_API` dispatch without a live opt-in row is not possible. Not "not permitted" — not
> possible. Four database triggers stand between the intent and the row (§8.3.9), the `NOT NULL`
> path runs through `outreach_whatsapp.optin_id`, and the only function that resolves an opt-in id
> is `live_optin()`, which takes `now` as a bound parameter and re-checks revocation.

---

## 8.8 `CLOUD_API` — built, and gated

Everything in this section is implementable now and switched off. `16-mvp-plan.md` schedules it
after the first campaign has produced real replies, because opt-ins come from replies and there is
nothing to send until then.

### 8.8.1 Account setup, in order

| # | Step | Where | What it needs | What goes wrong |
|---|---|---|---|---|
| 1 | Create a Meta Business Portfolio | business.facebook.com | Legal business name exactly as it appears on the documents | A trading name that does not match the paperwork fails verification later, after everything else is built |
| 2 | Business verification | Business Manager → Security Centre | Certificate of Incorporation / GST registration certificate / Shop & Establishment licence / PAN in the legal name, plus a utility bill or bank statement showing the same name and address; a business phone number and email on the same domain | Mismatched address, a document older than the accepted window, a name in a different script. Rejections are common and re-submission is slow. Budget days-to-weeks, not hours. |
| 3 | Domain verification | Business Manager → Brand Safety → Domains | A DNS `TXT` record, a `<meta>` tag, or an uploaded HTML file | DNS propagation. Use the `TXT` method and check with `dig`. |
| 4 | Create a Meta app of type **Business** | developers.facebook.com | The portfolio from step 1 | Creating it under a personal account and having to migrate it |
| 5 | Add the **WhatsApp** product to the app | App dashboard | — | — |
| 6 | Create or attach a WABA | App → WhatsApp → API Setup | The verified business | One WABA per business; note the `WABA_ID` |
| 7 | Add and register the phone number | §8.8.2 | A number not currently on WhatsApp | See §8.8.2 — this step is destructive |
| 8 | Submit the display name | §8.8.3 | A name related to the business | Rejection for a generic or unrelated name |
| 9 | Create a **system user** and issue a permanent access token | Business Settings → Users → System Users | Scopes `whatsapp_business_messaging` and `whatsapp_business_management`, asset-scoped to the WABA | Using a short-lived user token that expires in 60 days and takes the integration down on a Sunday |
| 10 | Configure the webhook | App → WhatsApp → Configuration | A public HTTPS callback URL and a verify token | Caddy already terminates TLS on the VPS (`_CONTEXT.md` §2); the callback path is `/api/v1/webhooks/whatsapp` |
| 11 | Subscribe the WABA to webhook fields | Same screen | `messages`, `message_template_status_update`, `message_template_quality_update`, `template_category_update`, `phone_number_quality_update`, `phone_number_name_update`, `account_update` | Subscribing only to `messages` and then wondering why nobody noticed the account restriction |
| 12 | Add a payment method | Business Settings → Payments | An Indian card or account, billing in INR | Template sends fail silently past the free tier without one |

```ini
# config/.env   (never in config.yaml, per _CONTEXT.md §1)
WA_ACCESS_TOKEN=EAAG...             # system user permanent token
WA_APP_SECRET=...                   # for X-Hub-Signature-256 verification
WA_VERIFY_TOKEN=...                 # random 32+ chars, our own value
WA_WABA_ID=...
WA_PHONE_NUMBER_ID=...
WA_DISPLAY_PHONE_NUMBER=+91...      # the registered number, for display and log masking
```

```yaml
# config/config.yaml
whatsapp:
  graph_api_version: "v23.0"        # pin it; check Meta's changelog before bumping
  base_url: "https://graph.facebook.com"
  timeout_seconds: 20
  connect_timeout_seconds: 5
  max_retries: 3
  retry_backoff_seconds: [5, 30, 180]
  mark_inbound_as_read: false       # see 8.8.9
  templates:
    intro: "business_radar_intro_v1"
    languages: ["en"]
  cost:
    # SAMPLE placeholder. Replace from Meta's published India rate card before enabling
    # sending. The system records what Meta actually billed via the webhook pricing
    # object and reconciles against this number, flagging drift.
    marketing_inr_micros: 0
    utility_inr_micros: 0
```

### 8.8.2 Phone number registration

| Fact | Detail |
|---|---|
| The number must be free | It cannot be active on the WhatsApp consumer app or the WhatsApp Business app. Removing it there (Settings → Account → Delete my account) is **irreversible** and destroys that account's chat history. |
| It must receive an OTP | SMS or an international voice call. Many VoIP and virtual numbers fail this step. |
| Two-step PIN | A 6-digit PIN is set at registration and is required for re-registration and for some support operations. Store it in `config/.env` as well as offline; losing it is a support ticket. |
| It cannot be used in the app afterwards | Once on Cloud API, the number is API-only. This is why manual mode and API mode need two different numbers (§8.6.7). |
| Display name is separate | Registration and display-name approval are different reviews (§8.8.3). |

```http
POST https://graph.facebook.com/v23.0/<WA_PHONE_NUMBER_ID>/register
Authorization: Bearer <WA_ACCESS_TOKEN>
Content-Type: application/json

{ "messaging_product": "whatsapp", "pin": "482913" }
```

```json
{ "success": true }
```

The health check reads the number's live state and drives `/settings`:

```http
GET https://graph.facebook.com/v23.0/<WA_WABA_ID>/phone_numbers
    ?fields=id,display_phone_number,verified_name,code_verification_status,
            quality_rating,messaging_limit_tier,name_status,throughput
```

```json
{
  "data": [{
    "id": "1234567890",
    "display_phone_number": "+91 99999 00000",
    "verified_name": "Sagar Software SAMPLE",
    "code_verification_status": "VERIFIED",
    "quality_rating": "GREEN",
    "messaging_limit_tier": "TIER_250",
    "name_status": "APPROVED",
    "throughput": { "level": "STANDARD" }
  }]
}
```

### 8.8.3 Display name

- The name shown to recipients. It must relate to the business — a generic word, a person's own
  name unrelated to the business, or a name suggesting an affiliation the business does not have is
  rejected.
- Reviewed separately from business verification, and re-reviewed on every change. While a change is
  pending, `name_status` is `PENDING_REVIEW` and the previous approved name stays in use.
- Values on `name_status`: `APPROVED`, `PENDING_REVIEW`, `DECLINED`, `EXPIRED`, `AVAILABLE_WITHOUT_REVIEW`.
- The `phone_number_name_update` webhook carries the decision and, on rejection, the reason. The
  handler writes it to `audit_log` and pages Sagar; a declined name blocks nothing immediately but
  it is the sort of thing that goes unnoticed for a month otherwise.

### 8.8.4 Template categories, and what a prospecting message honestly is

| Category | What it is for | Our message? |
|---|---|---|
| `MARKETING` | Promotions, offers, product announcements, invitations, **anything that is not strictly transactional** — including a cold introduction | **Yes. This is the honest category.** |
| `UTILITY` | A message about a specific, existing transaction the user initiated: order updates, appointment reminders, receipts, account alerts | No. There is no transaction. |
| `AUTHENTICATION` | One-time passcodes only | No. |

The temptation is to phrase the introduction as a UTILITY template because utility is cheaper and,
inside an open service window, free. Do not. Meta reviews the template text, auto-categorises it,
and re-categorises approved templates when it disagrees (`template_category_update` webhook). Three
consequences of trying it: the template is rejected with `INCORRECT_CATEGORY` or silently
re-categorised and billed at the marketing rate anyway; the WABA collects a policy strike; and the
system's own audit trail records that it deliberately mislabelled outreach, which is exactly the
kind of thing an audit trail exists to prevent. `radar/channels/whatsapp.py` refuses to submit a
template whose `category` is not `MARKETING` unless the body matches a UTILITY allow-list that, in
v1, is empty.

### 8.8.5 Our template, and the personalisation it costs us

`business_radar_intro_v1`, language `en`, category `MARKETING`:

```json
{
  "name": "business_radar_intro_v1",
  "language": "en",
  "category": "MARKETING",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}} team, I work on customised business-management software for established businesses.\n\nI came across your organisation while researching businesses in {{2}}. Based on your business type, I believe a centralised system for {{3}} could improve operational visibility and reporting.\n\nWe have a working demonstration for this type of business. If it is relevant, I can share a short demo and explain how it could be customised around your workflow.\n\nRegards, Sagar",
      "example": {
        "body_text": [["ABC Hospital", "Dhule", "patient records, appointments and billing"]]
      }
    },
    { "type": "FOOTER", "text": "Reply STOP and I will not message again." },
    {
      "type": "BUTTONS",
      "buttons": [ { "type": "QUICK_REPLY", "text": "Stop messages" } ]
    }
  ]
}
```

Design notes on that JSON:

| Choice | Reason |
|---|---|
| No `HEADER` | Every component is a rejection surface. A text header adds nothing the first body line does not. |
| `FOOTER` carries the opt-out | Footers cannot contain variables, so it cannot be personalised away. 40 characters, inside the 60-character limit. |
| One `QUICK_REPLY` button, no URL button | A URL button in a cold first message reads like phishing and drags the template into extra review. The demo link goes in the conversation, after they reply. |
| `example.body_text` is mandatory | Meta rejects a template with variables and no example. The example is SAMPLE data and must be plausible, not placeholder text like "xxx". |
| Three variables, no more | See below. |

**The functional cost, stated plainly.** §22 and §24 ask for a genuinely personalised message. In
`MANUAL_LINK` mode the system delivers that: `gemini-2.5-flash` writes prose grounded in this
business's `research_findings`. In `CLOUD_API` mode it cannot. The template is fixed at approval
time and only the three slots vary. Worse, stuffing LLM prose into a variable is precisely the abuse
pattern that gets templates paused — Meta reviews the skeleton, not the parameters, and parameters
may not contain newlines or tabs anyway. So:

```python
# radar/channels/whatsapp.py

# Parameter 3 is drawn from this closed vocabulary, keyed on businesses.category
# (_CONTEXT.md §6), derived from spec §26 and owned jointly with
# 06-message-engine.md. An LLM may choose among these strings. It may not write one.
RELEVANT_AREA: dict[str, str] = {
    "HOSPITAL":            "patient records, appointments and billing",
    "DIAGNOSTIC_CENTER":   "patient records, test workflow and reporting",
    "SCHOOL":              "student records, fees and attendance",
    "COLLEGE":             "admissions, examinations and fee records",
    "MANUFACTURER":        "inventory, production and purchasing",
    "DISTRIBUTOR":         "inventory, orders and receivables",
    "VEHICLE_DEALER":      "vehicle inventory, sales and customer records",
    "GARAGE":              "job cards, spare parts and billing",
    "HOTEL":               "bookings, housekeeping and billing",
    "RESTAURANT":          "orders, inventory and daily sales",
    "BAKERY":              "orders, production and delivery",
    "RETAIL_STORE":        "inventory, variants and daily sales",
    "REAL_ESTATE_AGENCY":  "listings, enquiries and follow-ups",
    "OTHER":               "day-to-day operations and reporting",
}
```

The policy check in API mode therefore reduces to one question, which `radar/policy.py` answers
against the stored facts: *is the chosen `relevant_area` supported by at least one `OBSERVED` or
`INFERRED` finding for this business?* If the only findings are `UNKNOWN`, the message is
`POLICY_BLOCKED` in API mode exactly as it would be in manual mode. The claim surface is smaller,
so the check is smaller. It is not skipped.

Parameters 1 and 2 come from `businesses.name` and `businesses.city` verbatim — both `OBSERVED` by
definition, both confirmed by a human at the §16 verification step.

### 8.8.6 Submission, approval, rejection

```http
POST https://graph.facebook.com/v23.0/<WA_WABA_ID>/message_templates
Authorization: Bearer <WA_ACCESS_TOKEN>
Content-Type: application/json

{ ...the components JSON from 8.8.5... }
```

```json
{ "id": "1234567890123456", "status": "PENDING", "category": "MARKETING" }
```

| `whatsapp_templates.status` | Meaning | What the system does |
|---|---|---|
| `LOCAL_DRAFT` | Written, validated locally, not submitted | Visible on `/settings`, not usable |
| `PENDING` | With Meta. Usually minutes, up to 24 h | Gate `I_WA_TEMPLATE_UNAVAILABLE` |
| `APPROVED` | Usable | The only status `trg_waw_cloud_needs_approved_template` accepts |
| `REJECTED` | Refused. `rejected_reason` carries Meta's string | Telegram alert with the reason; edit and resubmit under a new name |
| `PAUSED` | Recipient feedback pushed template quality to red. Auto-paused for an escalating interval | Gate blocks; alert; do not resubmit the same text |
| `DISABLED` | Paused too often, or a policy violation | Terminal. Alert as URGENT |
| `IN_APPEAL` | Appeal lodged | Gate blocks |
| `PENDING_DELETION` / `DELETED` | Removed | Gate blocks |

Rejection reasons Meta returns, and what each actually means for a prospecting template:

| Reason | Cause | Fix |
|---|---|---|
| `INVALID_FORMAT` | Variable at the very start or end of the body, two adjacent variables, missing `example`, bad button config, stray whitespace | Structural. §8.8.7's validator catches all of these before submission. |
| `INCORRECT_CATEGORY` / `TAG_CONTENT_MISMATCH` | Promotional text submitted as UTILITY | Submit as `MARKETING`. §8.8.4. |
| `PROMOTIONAL` | Marketing content in a non-marketing category | Same. |
| `SCAM` | Text resembling a known scam pattern: unexplained links, money, urgency, impersonation | Remove links and figures; the §8.6.4 `validate()` rules already forbid both. |
| `ABUSIVE_CONTENT` | Policy-violating content | Rewrite. |
| `NONE` | Approved, or no reason given | — |

Sync back with `GET /<WABA_ID>/message_templates?fields=name,status,category,quality_score,rejected_reason`
on the `wa_template_sync` job, and immediately on a `message_template_status_update` webhook. Meta's
state is authoritative; the local row is a mirror and is overwritten, never merged.

### 8.8.7 Variable rules and the local validator

Meta's rules, encoded once as constants so a template is never submitted to fail:

| Rule | Limit |
|---|---|
| Template name | lowercase letters, digits, underscores; must be unique per (WABA, language) |
| `HEADER` text | 60 characters, at most 1 variable |
| `BODY` text | 1024 characters, variables numbered `{{1}}`…`{{n}}` contiguously from 1 (or named, matching `^[a-z_][a-z0-9_]*$`) |
| `FOOTER` text | 60 characters, **no variables** |
| Button text | 25 characters |
| Buttons | at most 10 total, with per-type limits; at most one phone-number button; URL buttons may carry at most one variable, at the end |
| Body may not begin or end with a variable | Structural — a common `INVALID_FORMAT` cause |
| Two variables may not be adjacent | `{{1}} {{2}}` is rejected |
| Variable-to-text ratio | A body that is mostly variables is rejected; there is no published exact threshold, so the validator warns above roughly one variable per 40 characters of static text |
| Parameter values at send time | No newlines, no tabs, no more than 4 consecutive spaces (error `132000`/`132012`) |
| Hydrated length | The rendered body must still be within 1024 characters (error `132005`) |

```python
def validate_template(components: list[dict[str, Any]], *, category: str) -> list[str]:
    """Reject locally what Meta would reject remotely, before the 24-hour round trip.

    Every rejection costs a submission and, more importantly, a day. The list here is the
    published rule set as of the version pinned in config; when Meta changes it the fix is
    one file, and the test suite in tests/test_whatsapp_template.py has a case per rule.

    Codes: WAT_NAME_FORMAT, WAT_BODY_TOO_LONG, WAT_FOOTER_TOO_LONG, WAT_FOOTER_VARIABLE,
           WAT_HEADER_TOO_LONG, WAT_HEADER_MULTI_VAR, WAT_VAR_AT_EDGE, WAT_VAR_ADJACENT,
           WAT_VAR_NOT_CONTIGUOUS, WAT_MISSING_EXAMPLE, WAT_EXAMPLE_ARITY,
           WAT_VAR_DENSITY, WAT_BUTTON_TEXT_TOO_LONG, WAT_TOO_MANY_BUTTONS,
           WAT_URL_BUTTON_VAR, WAT_CATEGORY_MISMATCH
    """


def validate_params(template: WhatsAppTemplate, params: list[str]) -> list[str]:
    """Send-time parameter check. Codes: WAP_COUNT_MISMATCH, WAP_NEWLINE, WAP_TAB,
    WAP_MULTISPACE, WAP_EMPTY, WAP_HYDRATED_TOO_LONG, WAP_NOT_IN_VOCAB."""
```

`WAP_NOT_IN_VOCAB` is ours, not Meta's: parameter 3 must be a value from `RELEVANT_AREA`.

### 8.8.8 Sending

```http
POST https://graph.facebook.com/v23.0/<WA_PHONE_NUMBER_ID>/messages
Authorization: Bearer <WA_ACCESS_TOKEN>
Content-Type: application/json

{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "919876543210",
  "type": "template",
  "template": {
    "name": "business_radar_intro_v1",
    "language": { "code": "en" },
    "components": [
      { "type": "body",
        "parameters": [
          { "type": "text", "text": "ABC Hospital" },
          { "type": "text", "text": "Dhule" },
          { "type": "text", "text": "patient records, appointments and billing" }
        ] }
    ]
  }
}
```

```json
{
  "messaging_product": "whatsapp",
  "contacts": [{ "input": "919876543210", "wa_id": "919876543210" }],
  "messages": [{ "id": "wamid.HBgMOTE5ODc2NTQzMjEwFQIAERgSMEE...",
                 "message_status": "accepted" }]
}
```

A `200` here means **accepted**, not delivered. `delivery_state = 'API_ACCEPTED'`,
`outreach_messages.status = 'QUEUED'`. Only the `sent` status webhook moves it to `SENT`. Getting
this wrong is the classic Cloud API integration bug: a dashboard that says "sent" for messages that
were never delivered because the recipient is not on WhatsApp.

The API call happens **outside** the write transaction, as `05-outreach-workflow.md` §5.2.1
requires, with the `idempotency_key` already committed. If the process dies between the HTTP call
and the row write, the recovery job resolves the ambiguity by looking for the `wamid` in received
webhooks rather than by re-sending — `delivery_state` stays `PENDING` and `outreach_events` records
`INDETERMINATE`. Re-sending a message that may already have arrived is worse than not knowing.

Error handling, by code:

| Code | Meta's meaning | Our response |
|---|---|---|
| `131026` | Message undeliverable — recipient not on WhatsApp, or cannot receive | `API_UNDELIVERED` → `FAILED`; `wa_capability = 'NOT_ON_WHATSAPP'`; deactivate the WHATSAPP contact; no retry |
| `131047` | Re-engagement message — 24 h window closed and a non-template was attempted | Bug in our code. `FAILED`, alert. We never send free-form outside a window |
| `131049` | Not delivered to maintain healthy ecosystem engagement (marketing frequency capping by Meta) | `API_UNDELIVERED` → `FAILED`, no retry, no resend to that user for this campaign; increment a marketing-health counter |
| `130472` | Recipient is in an experiment group; marketing message not delivered | Same as `131049` |
| `132000` | Parameter count mismatch | Bug. `FAILED`, alert; `validate_params` should have caught it |
| `132001` | Template does not exist in this language | Re-sync templates, `FAILED` |
| `132005` | Hydrated text too long | `FAILED`; shorten and re-draft |
| `132007` | Format character policy violated | `FAILED`; parameter contained a newline or tab |
| `132012` | Parameter format mismatch | `FAILED` |
| `132015` | Template paused | `FAILED`; set local status `PAUSED`; block the gate; URGENT alert |
| `132016` | Template disabled | `FAILED`; local status `DISABLED`; URGENT alert |
| `133010` | Phone number not registered | `FAILED`; kill switch; URGENT alert |
| `368` | Temporarily blocked for policy violations | **Kill switch**: `whatsapp_api_enabled = 0`, URGENT handoff |
| `131031` | Account locked / WABA disabled | **Kill switch**, URGENT handoff |
| `190` | Access token expired or invalid | **Kill switch** until the token is rotated; alert |
| `130429`, `131056`, `80007` | Rate limits (API, business-consumer pair, throughput) | Retryable, exponential backoff per `retry_backoff_seconds` |
| `133004`, `131000`, `500`–`599` | Transient server-side | Retryable |
| `100` | Invalid parameter | `FAILED`, alert; do not retry a malformed request |

```python
WA_KILL_SWITCH_CODES = frozenset({368, 131031, 190, 133010})
WA_RETRYABLE_CODES  = frozenset({130429, 131056, 80007, 133004, 131000})
WA_TERMINAL_CODES   = frozenset({131026, 131049, 130472, 132000, 132001, 132005,
                                 132007, 132012, 132015, 132016, 100})


def trip_kill_switch(conn, *, code: int, detail: str, actor: str = "system") -> None:
    """Set contact_policy.whatsapp_api_enabled = 0 and page Sagar. No auto-recovery.

    An account-level policy error is not a transient failure to retry through. Every
    additional message sent after code 368 makes the appeal harder. The switch goes off
    automatically and only a human turns it back on, after reading what happened.
    """
```

### 8.8.9 The 24-hour customer service window

| Fact | Consequence here |
|---|---|
| An inbound message from the user opens a 24-hour window | Only *they* can open it. Nothing we send opens one. |
| Inside the window, free-form (non-template) messages are allowed | This is the only way to send genuinely personalised WhatsApp text through the API — and it is only reachable after they reply. |
| Each new inbound message resets the 24 hours | Tracked from `responses.received_at` for WhatsApp responses. |
| Outside the window, template only | Error `131047` otherwise. |
| Service conversations (inside the window) are not charged | Since Meta's November 2024 change. Utility templates sent inside an open window are likewise not charged. |

**And the system still does not use it.** `_CONTEXT.md` §3 invariant 6 and spec §55: the AI
classifies inbound responses, it never replies to them. An open service window is an opportunity for
*Sagar* to reply from the `/handoffs` screen, not for the machine to. What the window does in this
design is exactly two things: it is recorded as `INBOUND_WHATSAPP` opt-in evidence, and it is
displayed on the handoff brief as "you can reply freely until 14:30 tomorrow", so Sagar knows the
clock is running.

```python
@dataclass(slots=True, frozen=True)
class ServiceWindow:
    open: bool
    opened_at: str | None
    expires_at: str | None
    source_response_id: str | None


def service_window(conn, business_id: str, wa_e164: str, *, now: str) -> ServiceWindow:
    """Is a 24-hour customer service window open for this number? Read-only, advisory.

    Nothing in radar/ sends a message because this returns open=True. It exists so the
    handoff brief can tell Sagar how long he has before a reply needs a template again.
    """
```

`config.whatsapp.mark_inbound_as_read` defaults to `false`. Marking a message read via
`POST /<PHONE_NUMBER_ID>/messages {"status":"read","message_id":"wamid..."}` shows the sender blue
ticks, which tells them a human has read their message. At the moment that fires, no human has.

### 8.8.10 Pricing in India, and the cost ledger

The pricing model, as it stands after Meta's July 2025 move from conversation-based to per-message
pricing:

| Fact | Detail |
|---|---|
| Unit of charge | The **delivered template message**, not the conversation. Marketing, utility and authentication templates each have their own rate. |
| Free | Service conversations — free-form messages sent inside an open customer service window. Utility templates sent inside an open window. |
| Our messages | Every first-touch message is a MARKETING template and is charged at the India marketing rate. |
| Rate card | Per-country, per-category, published by Meta and revised periodically. India has its own INR rates. |
| Free tier | Meta has historically granted a monthly allowance of free service conversations; it does not cover marketing templates and must not be assumed. |
| Billing | Against the payment method on the Business Portfolio, in INR. |

**No rupee figure appears in this document.** Any number written here would be stale by the time the
code is built and would end up quoted in a report as fact, which `_CONTEXT.md` §3 invariant 5
forbids. Instead:

1. `config.whatsapp.cost.marketing_inr_micros` holds the current rate, entered by Sagar from Meta's
   published India rate card. It ships as `0`, which renders as `—` and never as `₹0.00`.
2. Every `outreach_whatsapp` row records what Meta itself said in the status webhook's `pricing`
   object: `pricing_billable`, `pricing_model`, `pricing_category`.
3. `cost_inr_micros` is computed at delivery time from the configured rate when
   `pricing_billable = 1`, in integer micro-rupees. Never a float, because the §37/§38 comparison
   reports sum it.
4. A `wa_cost_reconcile` job compares the sum of `cost_inr_micros` against the WABA's billing figure
   monthly and logs a warning on drift above a threshold. A silently changed rate card is a real
   failure mode.

```sql
-- SAMPLE shape only; the numbers depend on a rate card this document does not quote.
SELECT b.city,
       COUNT(*)                                   AS messages,
       SUM(w.pricing_billable)                    AS billable,
       SUM(COALESCE(w.cost_inr_micros, 0))        AS cost_inr_micros
  FROM outreach_whatsapp w
  JOIN outreach_messages om ON om.id = w.message_id
  JOIN businesses b ON b.id = w.business_id
 WHERE w.dispatch_mode = 'CLOUD_API'
   AND om.sent_at >= :from_ts
 GROUP BY b.city
 ORDER BY cost_inr_micros DESC;
```

The economic point worth stating: at any plausible marketing rate, the cost per message is trivial
next to the cost of a burned number. Cost is not the reason to be careful here.

### 8.8.11 Quality rating, messaging tiers, and the automatic kill switch

| Concept | Values | Driven by |
|---|---|---|
| Quality rating (per phone number) | `GREEN` (high), `YELLOW` (medium), `RED` (low), `UNKNOWN`/`NA` | Recipient blocks and reports over a rolling window, weighted against volume |
| Messaging limit tier (per phone number) | `TIER_250`, `TIER_1K`, `TIER_10K`, `TIER_100K`, `TIER_UNLIMITED` — unique recipients you may *start* conversations with per rolling 24 h | Business verification status, quality rating, and sustained volume |
| Template quality score (per template) | `GREEN`, `YELLOW`, `RED` | Feedback specific to that template |
| Account state | violations, restrictions, scheduled disable | Policy enforcement on the WABA |

The escalation path is: blocks accumulate → quality drops to `YELLOW` then `RED` → the number is
flagged and the tier is cut → repeated flagging restricts the account → the WABA is disabled. The
first two steps are visible through webhooks; if the system waits until the last one, it is too
late.

```python
def on_quality_change(conn, *, phone_number_id: str, previous: str, current: str,
                      current_limit: str | None, cfg) -> None:
    """React to phone_number_quality_update. Downgrades stop sending; upgrades do not
    resume it.

    Asymmetry is the point. A drop to RED disables the API channel automatically and a
    human turns it back on; an automatic re-enable on recovery would let the system
    oscillate its way to a ban while nobody was watching.
    """
```

| Signal | Automatic response |
|---|---|
| Quality below `whatsapp_quality_floor` (default: anything below `YELLOW`, i.e. `RED`) | `whatsapp_api_enabled = 0`; URGENT Telegram; `audit_log`; all `PENDING_APPROVAL`/`APPROVED` WhatsApp messages remain but the gate downgrades them to `MANUAL_LINK` |
| Quality `GREEN` → `YELLOW` | Warning notification; `whatsapp_daily_api_cap` halved automatically; no shutdown |
| Tier downgrade | Notification; gate `I_WA_TIER_EXHAUSTED` recomputed against the new tier |
| `account_update` with `ACCOUNT_VIOLATION` or `ACCOUNT_RESTRICTION` | Kill switch, URGENT handoff, and the restriction detail stored verbatim |
| `account_update` with `waba_ban_state` in `SCHEDULE_FOR_DISABLE` / `DISABLE` | Kill switch, URGENT handoff. This is the one that ends the channel |
| Template quality `RED` or `PAUSED` | That template is blocked locally; other templates continue |

The tier gate is computed from our own data rather than trusted from Meta, because the tier counts
unique recipients in a rolling 24 hours and we know exactly who we messaged:

```sql
-- Parameters: :window_start, :tier_limit
SELECT COUNT(DISTINCT w.to_e164) AS unique_recipients_24h
  FROM outreach_whatsapp w
  JOIN outreach_messages om ON om.id = w.message_id
 WHERE w.dispatch_mode = 'CLOUD_API'
   AND om.sent_at >= :window_start;
```

### 8.8.12 How the gate is actually opened

There is no toggle on `/settings` labelled "enable WhatsApp API". Turning it on is:

1. `whatsapp_api_enabled` is `0` in `contact_policy` and no application code writes that column.
2. Sagar opens `sqlite3 data/radar.db` and runs the documented `UPDATE`, which requires him to also
   insert an `audit_log` row with `action = 'WA_API_ENABLED'` — enforced by a trigger with the same
   shape as `trg_suppressions_release_needs_audit` in `05-outreach-workflow.md` §5.3.2.
3. `whatsapp_daily_api_cap` is separately raised above `0`.
4. `GET /api/v1/whatsapp/health` must report `code_verification_status = VERIFIED`,
   `name_status = APPROVED`, an `APPROVED` template, quality at or above the floor, and a non-zero
   tier before the first message is drafted; the preflight refuses otherwise.

Four deliberate acts. That is proportionate to the fact that step 5 is messaging strangers' phones
from a business identity that can be permanently destroyed.

---

## 8.9 Webhooks

### 8.9.1 Verification handshake

```http
GET /api/v1/webhooks/whatsapp
    ?hub.mode=subscribe
    &hub.verify_token=<WA_VERIFY_TOKEN>
    &hub.challenge=1158201444
```

Respond `200` with the raw challenge string when `hub.mode == "subscribe"` and the token matches
under `hmac.compare_digest`; `403` otherwise. The response body is the challenge and nothing else —
a JSON wrapper fails the handshake.

### 8.9.2 Signature verification

```python
def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """X-Hub-Signature-256 check over the exact bytes received.

    Over the RAW body, before any JSON parsing: re-serialising the payload changes key
    order and whitespace and the HMAC no longer matches. Flask's request.get_data() gives
    the right bytes; request.json does not.

    An unsigned or wrongly-signed request is stored with signature_ok = 0 and dropped
    without interpretation. Anyone on the internet can POST to this URL, and a forged
    'the recipient replied STOP' is a nuisance while a forged 'the recipient is
    interested' would put a fake lead in front of Sagar.
    """
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])
```

### 8.9.3 Handler shape

```python
@bp.post("/api/v1/webhooks/whatsapp")
def whatsapp_webhook():
    """Persist, acknowledge, then interpret. In that order, always.

    Meta retries on anything slower than a few seconds and treats sustained failure as a
    reason to disable the subscription. Interpretation touches the LLM classifier and can
    take seconds, so it happens in a job. The raw row is the durable part; if the job
    crashes the event is replayable from the payload column.
    """
    raw = request.get_data()
    ok = verify_signature(raw, request.headers.get("X-Hub-Signature-256"), cfg.wa_app_secret)
    event_ids = store_raw_events(conn, raw, signature_ok=ok)     # one row per change entry
    if ok:
        enqueue(conn, kind="wa_webhook_process", payload={"event_ids": event_ids})
    return "", 200
```

`store_raw_events` splits `entry[].changes[]` into one `whatsapp_webhook_events` row per change, so
a single POST carrying a status update and an inbound message becomes two independently replayable
rows.

### 8.9.4 Deduplication

Meta redelivers. The `event_key` is deterministic and unique-indexed, so a redelivery is a rejected
insert rather than a second status change:

| Change type | `event_key` |
|---|---|
| status update | `sha256(f"status:{wamid}:{status}:{timestamp}")` |
| inbound message | `sha256(f"msg:{wamid}")` |
| template status | `sha256(f"tpl:{message_template_id}:{event}:{timestamp}")` |
| quality update | `sha256(f"quality:{phone_number_id}:{current_limit}:{timestamp}")` |
| account update | `sha256(f"account:{waba_id}:{event}:{timestamp}")` |

Derived `outreach_events` rows carry `provider_event_id = event_key`, which
`05-outreach-workflow.md` §5.3.7 already unique-indexes. Two layers, because status webhooks arrive
out of order often enough to matter.

### 8.9.5 Status payloads

```json
// sent   (SAMPLE)
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "<WABA_ID>",
    "changes": [{
      "field": "messages",
      "value": {
        "messaging_product": "whatsapp",
        "metadata": { "display_phone_number": "919900000000",
                      "phone_number_id": "1234567890" },
        "statuses": [{
          "id": "wamid.HBgMOTE5ODc2NTQzMjEwFQIAERgSMEE...",
          "status": "sent",
          "timestamp": "1787000000",
          "recipient_id": "919876543210",
          "conversation": {
            "id": "b1f0c2d3e4f5a6b7c8d9e0f1a2b3c4d5",
            "expiration_timestamp": "1787086400",
            "origin": { "type": "marketing" }
          },
          "pricing": { "billable": true, "pricing_model": "PMP",
                       "category": "marketing", "type": "regular" }
        }]
      }
    }]
  }]
}
```

```json
// delivered   (SAMPLE, statuses[] only)
[{ "id": "wamid.HBgM...", "status": "delivered", "timestamp": "1787000012",
   "recipient_id": "919876543210",
   "conversation": { "id": "b1f0c2...", "origin": { "type": "marketing" } },
   "pricing": { "billable": true, "pricing_model": "PMP", "category": "marketing" } }]
```

```json
// read   (SAMPLE, statuses[] only)
[{ "id": "wamid.HBgM...", "status": "read", "timestamp": "1787000480",
   "recipient_id": "919876543210" }]
```

```json
// failed   (SAMPLE, statuses[] only)
[{ "id": "wamid.HBgM...", "status": "failed", "timestamp": "1787000005",
   "recipient_id": "919876543210",
   "errors": [{
     "code": 131049,
     "title": "This message was not delivered to maintain healthy ecosystem engagement.",
     "message": "This message was not delivered to maintain healthy ecosystem engagement.",
     "error_data": { "details": "Message failed to send because of a marketing frequency cap." },
     "href": "https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes/"
   }] }]
```

Mapping:

| `status` | `outreach_whatsapp.delivery_state` | `outreach_messages.status` | `outreach_events.event` |
|---|---|---|---|
| `sent` | `API_SENT` | `SENT` | `SENT` |
| `delivered` | `API_DELIVERED` | `DELIVERED` | `DELIVERED` |
| `read` | `API_READ` | `DELIVERED` (unchanged if already) | `OPENED` |
| `failed` | `API_FAILED` or `API_UNDELIVERED` per §8.8.8 | `FAILED` | `PROVIDER_ERROR`, then `FAILED` |

Out-of-order arrivals are handled by never moving backwards: the handler applies a status only if
its rank exceeds the current one (`sent` 1 < `delivered` 2 < `read` 3), while `failed` always
applies. A `read` arriving before `delivered` sets `read_at` and leaves `delivered_at` `NULL` rather
than inventing a delivery timestamp.

### 8.9.6 Inbound messages

```json
// inbound text   (SAMPLE)
{
  "field": "messages",
  "value": {
    "messaging_product": "whatsapp",
    "metadata": { "display_phone_number": "919900000000", "phone_number_id": "1234567890" },
    "contacts": [{ "profile": { "name": "ABC Hospital" }, "wa_id": "919876543210" }],
    "messages": [{
      "from": "919876543210",
      "id": "wamid.HBgMOTE5ODc2NTQzMjEwFQIAEhggQjFGMEMy...",
      "timestamp": "1787000600",
      "type": "text",
      "text": { "body": "Yes, please show us what you can provide." },
      "context": { "from": "919900000000", "id": "wamid.HBgM...<our message>" }
    }]
  }
}
```

```json
// quick-reply button tap on our template   (SAMPLE, messages[] only)
[{ "from": "919876543210", "id": "wamid.HBgM...", "timestamp": "1787000700",
   "type": "button",
   "button": { "payload": "Stop messages", "text": "Stop messages" },
   "context": { "from": "919900000000", "id": "wamid.HBgM...<our message>" } }]
```

Processing order for an inbound message, and the order matters:

```
1. Store the raw event.                                    always
2. Deterministic STOP scan (§8.10.1) on the raw body.      before any LLM call
3. Resolve the business:  context.id -> our wamid -> outreach_whatsapp -> business_id
                          else wa_id -> business_contacts.phone_e164
                          else UNMATCHED (see below)
4. Write a `responses` row (channel WHATSAPP).             09-response-classification.md
5. Record wa_capability = 'CONFIRMED', wa_id, and open the service window clock.
6. Enqueue classification (gemini-2.5-flash).              09-response-classification.md
7. Handoff triggers evaluate the classification.           10-human-handoff.md
```

Step 2 runs before step 6 for the same reason `10-human-handoff.md` §10.2.3 runs its legal lexicon
before the classifier: an opt-out must not depend on an LLM being reachable.

An `UNMATCHED` inbound — a number we have never messaged — is stored, is **not** discarded, and
appears on `/handoffs` as "unrecognised WhatsApp message". It is usually a wrong number or a
prospect messaging from a second handset, and it is never auto-replied to.

### 8.9.7 Account, template and quality payloads

```json
// message_template_status_update   (SAMPLE)
{ "field": "message_template_status_update",
  "value": { "event": "REJECTED",
             "message_template_id": 1234567890123456,
             "message_template_name": "business_radar_intro_v1",
             "message_template_language": "en",
             "reason": "INCORRECT_CATEGORY",
             "other_info": { "title": "Category", "description": "..." } } }
```

```json
// message_template_quality_update   (SAMPLE)
{ "field": "message_template_quality_update",
  "value": { "previous_quality_score": "GREEN", "new_quality_score": "YELLOW",
             "message_template_id": 1234567890123456,
             "message_template_name": "business_radar_intro_v1",
             "message_template_language": "en" } }
```

```json
// template_category_update   (SAMPLE)
{ "field": "template_category_update",
  "value": { "message_template_id": 1234567890123456,
             "message_template_name": "business_radar_intro_v1",
             "message_template_language": "en",
             "previous_category": "UTILITY", "new_category": "MARKETING",
             "correct_category": "MARKETING" } }
```

```json
// phone_number_quality_update   (SAMPLE)
{ "field": "phone_number_quality_update",
  "value": { "display_phone_number": "919900000000",
             "event": "FLAGGED", "current_limit": "TIER_250" } }
```

```json
// account_update   (SAMPLE)
{ "field": "account_update",
  "value": { "phone_number": "919900000000",
             "event": "ACCOUNT_RESTRICTION",
             "restriction_info": [{ "restriction_type": "RESTRICTED_BIZ_INITIATED_MESSAGING",
                                    "expiration": "2026-09-05T00:00:00+0000" }] } }
```

Every one of these writes an `audit_log` row. The three that trip the kill switch —
`phone_number_quality_update` with a below-floor result, `account_update` with a restriction or ban
state, and `message_template_status_update` with `DISABLED` — also create a `handoffs` row with
priority `URGENT` via `10-human-handoff.md`'s `create_handoff()`, so they page Sagar's phone rather
than sitting in a log.

The handler ignores unknown `field` values with `process_result = 'IGNORED_UNKNOWN_FIELD'` and a
single `log.info`, never an exception. Meta adds fields; an integration that crashes on an unknown
one takes the whole webhook subscription down with it.

---

## 8.10 STOP, opt-out, and how it becomes a suppression

### 8.10.1 The STOP lexicon

Deterministic, case-insensitive, word-boundary regex over the raw inbound body, before any
normalisation the classifier performs. Lives in `config.yaml` so it can grow without a deploy. The
same scan runs on text pasted in from manual mode.

```yaml
whatsapp:
  stop_lexicon:
    # English
    - "^\\s*stop\\s*$"
    - "\\bstop (messag|send|contact)"
    - "\\bunsubscribe\\b"
    - "\\bopt(-| )?out\\b"
    - "\\b(do ?n'?t|dont|do not) (message|msg|contact|call|whatsapp) me\\b"
    - "\\b(remove|delete) (me|my number)\\b"
    - "\\bnot interested\\b.*\\b(stop|again|remove)\\b"
    - "\\bhow did you get my number\\b"
    - "\\bthis is spam\\b|\\bspam(ming)?\\b"
    - "\\bwrong number\\b"
    # Transliterated Hindi / Marathi, as typed in Maharashtra business chat
    - "\\bband kar(o|a)\\b"
    - "\\bmat bhej(o|na)\\b"
    - "\\bmessage mat\\b"
    - "\\bnahi chahiye\\b|\\bnako\\b"
    - "\\bpareshan mat\\b"
    # Devanagari
    - "बंद कर"
    - "मेसेज करू नका|मेसेज मत"
    - "नको"
    - "नहीं चाहिए"
```

Rules, mirroring `10-human-handoff.md` §10.2.3 deliberately:

1. The scan runs in `radar/channels/whatsapp.py` **before** any classifier call, and its result is
   stored regardless of what the classifier later says.
2. A match writes a `suppressions` row immediately, in the same transaction as the `responses` row.
   It does not wait for classification, a job, or Sagar.
3. False positives are expected and acceptable. `wrong number` and `how did you get my number` are
   in the list on purpose: neither is a formal opt-out, both mean stop.
4. A `responses.classification` of `OPT_OUT` or `COMPLAINT` from the classifier produces the same
   suppression by the path `09-response-classification.md` already defines. The lexicon is the
   floor, not the ceiling.

### 8.10.2 The opt-out affordance in the outgoing message

| Mode | Mechanism |
|---|---|
| `MANUAL_LINK` | The line `Reply STOP and I will not message you again.` is mandatory in the body; `validate()` returns `WA_NO_OPTOUT_LINE` without it, and a `POLICY_BLOCKED` message cannot have a link issued. |
| `CLOUD_API` | The same sentence in the template `FOOTER` (which cannot be personalised away because footers take no variables), **plus** a `QUICK_REPLY` button reading "Stop messages". |

The button matters more than the sentence: it turns opting out into one tap, which is the difference
between a recipient opting out and a recipient blocking and reporting. A block costs quality rating;
an opt-out costs one prospect.

### 8.10.3 The handler

```python
def handle_stop(conn, *, business_id: str | None, wa_e164: str, response_id: str | None,
                matched_pattern: str, excerpt: str, source: str, actor: str = "system") -> str:
    """Turn an inbound stop signal into a permanent suppression. Returns the sup_ id.

    Called from the webhook processor, from the manual-response endpoint, and from the
    classifier when it returns OPT_OUT or COMPLAINT. Idempotent on (scope, value_norm).

    Order of writes matters and is: suppression first, then opt-in revocation, then
    business status, then notification. If the process dies halfway the suppression
    already exists, which is the failure mode we want - the opposite ordering can leave a
    business notified but still contactable.
    """
```

### 8.10.4 The fan-out (invariant 3)

One "STOP" from a WhatsApp number produces, in one transaction:

| Write | Value |
|---|---|
| `suppressions` | `scope='WHATSAPP'`, `value_norm='+919876543210'`, `reason='REPLY_OPT_OUT'`, `source='whatsapp_inbound'`, `source_ref=<rsp_ id>`, `detail={pattern, excerpt, wamid}` |
| `suppressions` | `scope='BUSINESS'`, `value_norm=<biz_ id>`, same reason — when the number resolves to a business. This is what makes the opt-out cross-channel: their email is now blocked too |
| `suppressions` | `scope='PHONE'`, same E.164 — the phone channel closes as well |
| `whatsapp_optins` | Any live row for that number: `revoked_at = now`, `revoked_reason = 'STOP_REPLY'`, `revoked_source_ref = <rsp_ id>` |
| `responses` | `classification = 'OPT_OUT'` (set by the deterministic scan; the classifier may not override it) |
| `outreach_events` | `event = 'UNSUBSCRIBED'` on the message the reply is in reply to, when resolvable |
| `businesses` | No status change. `CONTACTED` stays `CONTACTED`; suppression is a separate axis and the §17 lifecycle has no opt-out state |
| `audit_log` | One row per suppression, actor `system`, with the verbatim matched text |
| Telegram | A quiet, non-urgent notification. Sagar should know, and does not need to act |

None of it is reversible by the application. `05-outreach-workflow.md` §5.3.2 is explicit: there is
no `unsuppress()` and there never will be one in that file.

The cross-channel scope is worth defending, because it will feel wrong the first time it costs a
lead. Someone who says "don't WhatsApp me" has not consented to being emailed instead, and a system
that reads a stop signal as channel-specific is a system that looks like it is gaming the request.
Sagar can reverse it with a manual DB operation and an audit row if a business explicitly asks for
email later.

### 8.10.5 Manual mode: capturing what only Sagar can see

In `MANUAL_LINK` mode there is no inbound webhook. The reply arrives on Sagar's phone and the system
is blind to it. Three mechanisms close that gap:

```http
POST /api/v1/responses/manual
Content-Type: application/json

{
  "business_id": "biz_01JB2X8P0000000000000B1",
  "message_id": "msg_01JB2X8P00000000000000M1",
  "channel": "WHATSAPP",
  "received_at": "2026-08-28T05:12:00Z",
  "from_display": "+91 98765 43210",
  "body_text": "Please don't message me here, use email.",
  "capture_method": "PASTED"
}
```

```json
{
  "response_id": "rsp_01JB2X8P0000000000000R7",
  "stop_matched": true,
  "stop_pattern": "\\b(do ?n'?t|dont|do not) (message|msg|contact|call|whatsapp) me\\b",
  "suppressions_created": [
    { "id": "sup_01JB2X8P0000000000000S1", "scope": "WHATSAPP", "value_norm": "+919876543210" },
    { "id": "sup_01JB2X8P0000000000000S2", "scope": "BUSINESS", "value_norm": "biz_01JB2X8P0000000000000B1" },
    { "id": "sup_01JB2X8P0000000000000S3", "scope": "PHONE",    "value_norm": "+919876543210" }
  ],
  "classification_job_id": "job_01JB2X8P0000000000000J4",
  "note": "Recorded as a WhatsApp opt-out. This business is now blocked on every channel."
}
```

Note what that SAMPLE reply says: "use email". The system still blocks email, because the request
was made in the middle of a sentence declining contact and the safe reading is the strict one. The
`note` tells Sagar exactly what happened so he can make a deliberate, audited decision to reverse
it if he judges otherwise. The system does not make that judgement.

The other two mechanisms:

- A daily Telegram digest line: "4 WhatsApp messages sent 1–7 days ago have no recorded response —
  check your phone." Sent by `10-human-handoff.md`'s digest job.
- A "Record reply" button on `/business/<id>` next to every WhatsApp message, two clicks from the
  outreach history, so recording a reply is faster than not recording it.

### 8.10.6 A blocked recipient

There is no webhook for "this user blocked you". The signal arrives indirectly:

| Signal | Interpretation |
|---|---|
| Quality rating drops with no other change | Blocks are accumulating. Not attributable to a specific recipient. |
| Error `131049` / `130472` on send | Meta declined to deliver a marketing message to that user. Treated as terminal for that recipient in that campaign, and recorded — but **not** as an opt-out, because the user did not ask for anything. |
| `delivered` never arrives after `sent` | Ambiguous: phone off, no data, or blocked. Never inferred as an opt-out. |

`131049` sets `wa_capability` to `UNLIKELY` rather than `NOT_ON_WHATSAPP`, since the number works
fine — Meta simply will not carry marketing to it right now.

---

## 8.11 The decision table: which WhatsApp mode is available

Evaluated top to bottom by `WhatsAppChannel.availability()`. The first matching row wins. Every
outcome carries a reason string that is rendered verbatim in the report grid tooltip and in the
preview panel, so "WhatsApp unavailable" is never shown without a because.

| # | Condition | Mode | Reason shown to Sagar |
|---|---|---|---|
| 1 | Live `suppressions` row on business, phone or WhatsApp id | **NONE** | "Do not contact — opted out on {date}, via {source}." (§30) |
| 2 | `businesses.status` in `INTERESTED`, `HUMAN_HANDOFF` | **NONE** | "This is a live lead. The machine stops here and you take it." (§55) |
| 3 | `businesses.status` not in `CONTACT_READY`, `CONTACTED`, `RESPONDED` | **NONE** | "Not verified with a confirmed contact yet." (§18) |
| 4 | `contact_policy.whatsapp_enabled = 0` | **NONE** | "WhatsApp is switched off in settings." |
| 5 | No active human-verified contact with a parseable number | **NONE** | "No usable phone number on file." |
| 6 | `phone_number_type` in `FIXED_LINE`, `TOLL_FREE`, `PREMIUM_RATE` | **NONE** | "The only number on file is a landline / toll-free line. WhatsApp needs a mobile." |
| 7 | `wa_capability = 'NOT_ON_WHATSAPP'` | **NONE** | "This number is not on WhatsApp (confirmed on {date})." |
| 8 | The E.164 is shared with `>= whatsapp_same_number_max` already-messaged businesses inside the window | **NONE** | "This number was already used to contact {n} other businesses. Same phone, same person." (§29) |
| 9 | Frequency gate: attempts, follow-ups, or min-days exceeded | **NONE** | "Contacted on WhatsApp {date}. Next allowed {date}." (§31) |
| 10 | Another message is `AWAITING_MANUAL_DISPATCH` for this business | **NONE** | "You already have a WhatsApp message waiting to be sent to this business." |
| 11 | Daily cap reached | **NONE (today)** | "{n} of {cap} manual WhatsApp messages used today. Resets at {time}." |
| 12 | All above pass; `whatsapp_api_enabled = 0` | **MANUAL_LINK** | "You will send this yourself. The WhatsApp API is not enabled." |
| 13 | API enabled; no live opt-in row | **MANUAL_LINK** | "No opt-in on record, so the API cannot be used. You will send this yourself." (`I_WA_NO_OPTIN`) |
| 14 | API enabled; live opt-in; no `APPROVED` template in the required language | **MANUAL_LINK** | "Template {name} is {status}. Falling back to manual." |
| 15 | API enabled; live opt-in; approved template; quality below floor **or** account restricted | **MANUAL_LINK** | "WhatsApp API paused: number quality is {rating}. Falling back to manual." |
| 16 | API enabled; live opt-in; approved template; tier limit reached for the rolling 24 h | **MANUAL_LINK** | "API tier limit reached ({n}/{tier}). Falling back to manual." |
| 17 | API enabled; live opt-in; approved template; quality fine; tier headroom; API daily cap not reached | **CLOUD_API** | "Sent automatically using template {name}. Opt-in recorded {date} via {method}." |

Rows 12–16 are the interesting ones: the API being unavailable **never blocks the message**, it
downgrades the mode. Rows 1–11 block. That split is the whole design in one table — availability of
a convenient transport is not a permission question, and permission questions never get downgraded.

Worked example, SAMPLE data:

| Business (SAMPLE) | Number | Type | Opt-in | Row | Mode |
|---|---|---|---|---|---|
| ABC Hospital, Dhule | `+91 98765 43210` | MOBILE | none | 12 | `MANUAL_LINK` |
| Shirpur Steel Works | `02563 234567` | FIXED_LINE | none | 6 | NONE |
| Nashik Diagnostics | `+91 98220 12345` | MOBILE | `EMAIL_REPLY`, 2026-08-25 | 12 (API off) | `MANUAL_LINK` |
| Nashik Diagnostics, after the API is enabled | same | MOBILE | same | 17 | `CLOUD_API` |
| Jalgaon Motors | `+91 90000 11111` | MOBILE | none | 1 (replied STOP on 2026-08-20) | NONE |
| Dhule Bakery | `+91 98765 43210` | MOBILE | none | 8 (same number as ABC Hospital) | NONE |

---

## 8.12 What we deliberately do not build

Each row states the thing, why it is tempting, and what it would actually cost. This section exists
so that in six months, when a campaign is slow, the reasons are written down.

| Not built | Why it is tempting | What it costs |
|---|---|---|
| `whatsapp-web.js`, Baileys, venom-bot, WPPConnect, `go-whatsapp` | Free, no approval, no opt-in, full personalisation, unlimited volume. Everything the compliant path is not. | Explicitly banned by spec §21 and by WhatsApp's Terms. Detection is routine — these clients have recognisable protocol fingerprints. The account is banned, taking Sagar's real chats and contacts with it. Repeat bans follow the device and the number. And every one of these libraries needs the session credentials for a live WhatsApp account sitting on a VPS, which is a data-protection incident waiting for a server compromise. |
| Selenium/Playwright driving `web.whatsapp.com` | The repo already has Playwright infrastructure. | Same ban, same detection, plus brittleness: WhatsApp Web's DOM changes without notice and a selector drift mid-campaign sends a half-built message to a stranger. |
| Android accessibility-service or ADB automation of the WhatsApp app | Physically possible with a spare phone. | Same Terms violation. Worse audit story: no record of what was actually sent, which breaks §48 and §49 outright. |
| Third-party "WhatsApp panel" / grey BSP resellers | Cheap, instant, no verification, they promise bulk. | Almost all are unofficial gateways behind a web form. The number gets banned, there is no audit trail, no delivery truth, and every prospect's phone number and message body is now sitting in a stranger's database — a DPDP problem with Sagar's name on it, not theirs. |
| Scraping `wa.me` or any endpoint to test whether a number is on WhatsApp | Would let the report show "WhatsApp: yes/no" instead of "likely". | Rate-limited and against the Terms; produces a signal that a hostile reviewer reads as enumeration. §8.5.4's evidence model is the honest substitute. |
| WhatsApp broadcast lists in the Business app | 15 messages become 1 action. | Bulk messaging, ban trigger, and it destroys the per-business personalisation that is the reason the research pipeline exists. §54: optimise for qualified conversations, not messages sent. |
| Purchased number lists, and any number not found by our own research with a recorded `sources` row | Volume. | No provenance, so §14's source panel is a lie, DPDP purpose limitation is broken, and the numbers are stale enough to spike the block rate immediately. |
| An auto-reply bot on inbound WhatsApp | The 24-hour window makes it technically easy, and replying in 30 seconds looks responsive. | Violates `_CONTEXT.md` §3 invariant 6 and §55 directly. The AI classifies; Sagar replies. An interested prospect getting a bot answer is the single worst outcome this system can produce. |
| Marketing Messages Lite API (MM Lite) | Meta's marketing-optimised send path, with delivery optimisation. | It is for higher-volume marketing programmes with established opt-in bases. Nothing about a 15-message-a-day prospecting tool needs it, and adopting it means a second send path to keep safe. Revisit only if opt-in volume ever justifies it. |
| WhatsApp Flows, catalogues, product messages, click-to-WhatsApp ads | Richer first contact. | Every one is a new review surface and a new rejection reason on a template that only has to do one job: introduce a person. |
| Sending the same message to a business on WhatsApp *and* email | Twice the reach. | §29's duplicate protection exists precisely to stop this. Two channels in one week is what a person calls spam regardless of what the policy says. `whatsapp_min_days_between_outreach` and the shared `BUSINESS` suppression scope both enforce it. |
| Auto-re-enabling the API after quality recovers | Removes a manual step. | §8.8.11: the asymmetry is deliberate. A system that can turn its own sending back on can oscillate into a ban unattended. |

---

## 8.13 Module contract

### 8.13.1 `radar/channels/whatsapp.py`

```python
"""WhatsApp, done the only way that does not end with a banned number.

Meta lets a business start a WhatsApp conversation on exactly two conditions: the text is
a template they approved in advance, and the recipient opted in first. A business we found
by researching Dhule has done neither. So this module's main job is refusing: it will not
call the Cloud API without a row in whatsapp_optins, and four database triggers stand
behind that refusal in case a future version of this file forgets.

What it does instead, for every business that has not opted in, is build a wa.me link.
Sagar clicks it, WhatsApp opens with the message already typed, he reads it once more and
presses send himself. That is slower, does not scale, and gives us no delivery receipts -
and it is the difference between a person contacting a business and a machine doing it.

Without this module the tempting shortcut is whatsapp-web.js: free, unlimited, and against
the Terms of Service in a way that gets accounts banned along with every real conversation
in them. Spec 21 says do not, and this file is what "do not" looks like when it still has
to ship a working channel.

The E.164 normaliser lives here too, because until '0257 2223344 / 9822012345' becomes two
rows with two canonical numbers, the duplicate-contact check in spec 29 is comparing
strings that will never match anything, and the same business gets messaged twice.
"""
```

### 8.13.2 Public API

```python
# channel protocol (radar/channels/base.py)
class WhatsAppChannel:
    name = "WHATSAPP"
    contact_kinds = ("WHATSAPP", "PHONE")
    suppression_scopes = ("BUSINESS", "WHATSAPP", "PHONE")
    supports_delivery_receipts = True      # CLOUD_API only; False in MANUAL_LINK
    supports_inbound_capture   = True      # CLOUD_API only

    def normalise(self, raw, *, region="IN") -> NormalisedAddress: ...
    def availability(self, conn, business_id, *, cfg, policy) -> ChannelAvailability: ...
    def render(self, conn, draft_id, *, cfg) -> RenderedMessage: ...
    def validate(self, rendered, *, policy) -> list[str]: ...
    def dispatch(self, conn, message_id, approval_id, *, worker_id, cfg) -> DispatchResult: ...
    def parse_callback(self, payload, *, headers, cfg) -> list[ChannelEvent]: ...

# numbers
def split_phone_field(raw: str) -> list[str]: ...
def normalise_in_phone(raw: str, *, region: str = "IN") -> NormalisedAddress: ...
def wa_id_for(e164: str) -> str: ...
def classify_capability(number_type: str, prior: str) -> str: ...

# manual mode
def build_wa_link(e164: str, body: str) -> str: ...
def build_wa_qr(link: str) -> bytes: ...
def issue_link(conn, message_id: str, *, user_id: str, reissue: bool = False,
               cfg) -> ManualLink: ...
def record_manual(conn, message_id: str, *, sent: bool, sent_at: str | None,
                  edited: bool, final_body: str | None, note: str | None,
                  user_id: str, reason: str | None = None) -> ManualResult: ...

# opt-in ledger
def record_optin(conn, **kw) -> str: ...
def live_optin(conn, business_id: str, wa_e164: str, *, now: str) -> Optin | None: ...
def revoke_optin(conn, optin_id: str, *, reason: str, source_ref: str | None,
                 actor: str) -> None: ...

# cloud api
def send_template(conn, message_id: str, approval_id: str, *, worker_id: str,
                  cfg) -> DispatchResult: ...
def submit_template(conn, template_id: str, *, cfg) -> WhatsAppTemplate: ...
def sync_templates(conn, *, cfg) -> list[WhatsAppTemplate]: ...
def validate_template(components: list[dict], *, category: str) -> list[str]: ...
def validate_params(template: WhatsAppTemplate, params: list[str]) -> list[str]: ...
def health(conn, *, cfg) -> WhatsAppHealth: ...
def service_window(conn, business_id: str, wa_e164: str, *, now: str) -> ServiceWindow: ...
def trip_kill_switch(conn, *, code: int, detail: str, actor: str = "system") -> None: ...

# webhooks and stop
def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool: ...
def store_raw_events(conn, raw_body: bytes, *, signature_ok: bool) -> list[str]: ...
def process_events(conn, event_ids: list[str], *, cfg) -> ProcessSummary: ...
def scan_stop(body: str, *, cfg) -> StopMatch | None: ...
def handle_stop(conn, **kw) -> str: ...
```

### 8.13.3 Endpoints contributed to `13-api-endpoints.md`

```
POST   /api/v1/outreach/<message_id>/whatsapp-link      issue/re-issue the wa.me link (session auth)
POST   /api/v1/outreach/<message_id>/record-manual      confirm or abandon a manual send
GET    /api/v1/outreach/<message_id>/whatsapp           channel state for the preview panel
POST   /api/v1/businesses/<business_id>/whatsapp-optin  record an opt-in
GET    /api/v1/businesses/<business_id>/whatsapp-optin  the live opt-in, or 404
POST   /api/v1/whatsapp/optins/<optin_id>/revoke        revoke an opt-in
GET    /api/v1/whatsapp/optins                          the ledger, filterable, for /settings
GET    /api/v1/whatsapp/templates                       local mirror + Meta status
POST   /api/v1/whatsapp/templates                       create a LOCAL_DRAFT
POST   /api/v1/whatsapp/templates/<template_id>/submit  submit to Meta
POST   /api/v1/whatsapp/templates/sync                  force a sync
GET    /api/v1/whatsapp/health                          quality, tier, name status, caps, switches
GET    /api/v1/webhooks/whatsapp                        Meta verification handshake (unauthenticated)
POST   /api/v1/webhooks/whatsapp                        events (signature-authenticated)
POST   /api/v1/responses/manual                         paste an inbound reply (shared with PHONE)
```

UI surfaces, using only the canonical routes from `_CONTEXT.md` §6: the WhatsApp panel and link
button live on `/outreach/<draft_id>`; the opt-in panel, contact capability and "Record reply"
button live on `/business/<id>`; the ledger, template list, health and caps live on `/settings`.
The exported HTML report shows WhatsApp *status* and never a link (§8.6.6 rule 4, §19).

### 8.13.4 Jobs contributed to `14-background-jobs.md`

| Job kind | Trigger | Idempotency |
|---|---|---|
| `wa_webhook_process` | Enqueued by the webhook endpoint | `ux_wa_webhook_key` plus `processed_at IS NULL` claim |
| `wa_send_template` | Enqueued at APPROVE, `CLOUD_API` mode only | `outreach_messages.idempotency_key`; on an indeterminate outcome it resolves by looking for the `wamid` in webhooks, never by re-sending |
| `wa_template_sync` | Every 6 hours, and on `message_template_status_update` | Overwrites the local mirror; naturally idempotent |
| `wa_quality_poll` | Every 30 minutes while `whatsapp_api_enabled = 1` | Reads `GET /<WABA_ID>/phone_numbers`; a no-change poll writes nothing |
| `wa_manual_reminder` | Every hour | Fires once per `outreach_whatsapp` row per `whatsapp_manual_reminder_hours`, tracked on `link_issued_at` |
| `wa_response_nudge` | Daily, folded into the handoff digest | Keyed on the digest date |
| `wa_renormalise_contacts` | On a `PHONE_NORM_VERSION` bump | Only touches rows with an older `phone_norm_version` |
| `wa_cost_reconcile` | Monthly | Reads only; writes a log line and a `/settings` banner on drift |
| `wa_webhook_purge` | Daily | Sets `payload_purged_at` and blanks `payload` on rows older than the retention window; the row survives |

### 8.13.5 Security and data protection (§47, DPDP)

| Concern | Measure |
|---|---|
| Credentials | `WA_ACCESS_TOKEN`, `WA_APP_SECRET`, `WA_VERIFY_TOKEN` in `config/.env`, never in `config.yaml`, never in a log line, never in an API response. `/api/v1/whatsapp/health` returns states, not secrets. |
| Token rotation | System-user token is long-lived, not permanent in practice. `wa_quality_poll` treats error `190` as a kill-switch condition so a dead token surfaces within 30 minutes rather than on the next send. |
| Webhook authenticity | HMAC-SHA256 over the raw body; `signature_ok = 0` events are stored and never interpreted. |
| Webhook replay | `event_key` unique index; the endpoint is idempotent by construction. |
| Rate limiting | The webhook path is rate-limited per source IP by Caddy; the app additionally caps stored unsigned events per hour to stop a disk-fill attack. |
| Log hygiene | Phone numbers are masked to `+91******3210` in every log line. `radar/config.py`'s `setup_logging()` installs the filter, so a `log.debug` written in haste cannot leak a full number. |
| Purpose limitation | An opt-in row states the purpose in `consent_text`; the evidence records where the number came from. `sources` already records where the number was found. |
| Retention | `whatsapp_webhook_events.payload` is purged after 90 days (configurable); derived rows persist. Message bodies persist because §48 and §49 require the audit. |
| Erasure | A DPDP erasure request is handled by the same manual, audited path as a suppression release: the `suppressions` row stays (it is the record that they must not be contacted), contact values are tombstoned, and an `audit_log` row records the operation. |
| Least privilege | The system-user token is asset-scoped to the one WABA and holds only `whatsapp_business_messaging` and `whatsapp_business_management`. |

---

## 8.14 Failure modes

| Failure | Symptom | Design response |
|---|---|---|
| Sagar clicks the link and never confirms | Message sits `QUEUED` / `AWAITING_MANUAL_DISPATCH` | `wa_manual_reminder` nags after 6 hours; nothing auto-completes it. An unconfirmed message is never counted as sent, so the duplicate gate stays honest. |
| Sagar sends but forgets to confirm, then the business is re-selected next campaign | Risk of a duplicate message | Gate `H_WA_MANUAL_IN_FLIGHT` blocks a second draft while one is outstanding, and the reminder makes an outstanding one visible. |
| He edits the text in WhatsApp before sending | Approved body no longer matches what was sent | `edited: true` + `final_body` capture; §49's audit shows drafted, approved and actually-sent as three fields. |
| `wa.me` link opens on a machine with no WhatsApp session | Browser shows Meta's "download WhatsApp" page | The QR code is offered on the same panel; scanning it opens the same chat on the phone that holds the account. |
| Body contains a character that breaks the URL | Truncated message in the compose box | `quote(safe="")` encodes everything; a test asserts round-trip fidelity for `&`, `#`, `+`, newline and Devanagari text. |
| Number is a landline, WhatsApp is offered anyway | Message to a switchboard nobody reads | Gate `H_WA_NOT_MOBILE` blocks before it is drafted; the reason is shown in the grid. |
| Number is shared by three businesses in a directory | One person messaged three times | Gate `H_WA_SHARED_NUMBER` plus the preview warning panel. |
| Cloud API returns 200, process dies before the row write | Unknown whether the message went out | `INDETERMINATE` event; the recovery job resolves by matching the `wamid` in webhooks. Never re-sends. |
| `delivered` webhook arrives before `sent` | Out-of-order status | Rank-based application; a lower rank never overwrites a higher one. |
| Meta redelivers a webhook 5 times | 5 status changes, 5 responses | `event_key` unique index, then `provider_event_id` unique index on `outreach_events`. One row, one change. |
| Meta adds a webhook field we do not know | Handler exception, subscription disabled | Unknown fields are stored, marked `IGNORED_UNKNOWN_FIELD`, and logged at info. The handler never raises on shape. |
| Template silently re-categorised to MARKETING | Higher cost than budgeted | `template_category_update` webhook updates the local mirror and notifies; the cost ledger picks up the change from the `pricing` object regardless. |
| Template paused mid-campaign | Every send fails with 132015 | The first `132015` sets local status `PAUSED`, which trips the gate, so message two is downgraded to `MANUAL_LINK` rather than failing. |
| Quality drops to RED overnight | Silent degradation | `phone_number_quality_update` webhook + a 30-minute poll; either trips the kill switch and pages Sagar. |
| Access token expires | Every send fails with 190 | Kill switch; the API channel goes off; manual mode is unaffected, so outreach continues. |
| Inbound reply from an unknown number | No business to attach it to | Stored, surfaced on `/handoffs` as unrecognised, never auto-replied, never discarded. |
| The classifier is down when a STOP arrives | Risk of missing an opt-out | The STOP scan is a deterministic regex that runs before and independently of the classifier, in the same transaction as the `responses` row. |
| `phonenumbers` upgrade changes a classification | Numbers silently change meaning | `phone_norm_version` on every row; a bump triggers a re-run that writes an `audit_log` row per changed value. |
| Someone POSTs a forged webhook claiming a lead is interested | A fake handoff on Sagar's phone | Signature verification; unsigned events are stored with `signature_ok = 0` and never interpreted. |
| WABA disabled by Meta | Channel gone | Kill switch, URGENT handoff, and the whole campaign continues on email and manual WhatsApp. Nothing in the pipeline depends on the API existing. |

---

## 8.15 Tests that must exist

`tests/test_whatsapp_numbers.py`

- Every SAMPLE row of §8.5.3 round-trips to the stated E.164, type and reason.
- `split_phone_field` splits the compound listing strings and never returns a compound value.
- A landline, a toll-free number and a 9-digit number all produce `ok=False` with the right reason.

`tests/test_whatsapp_link.py`

- `build_wa_link` strips `+`, encodes newline as `%0A`, space as `%20`, and `&`/`#` correctly.
- Round-trip: `unquote(link.split('?text=')[1]) == body` for an ASCII body, a Devanagari body and a
  body containing `&`, `#` and `+`.
- Bodies over 1024 characters and over the encoded byte limit raise.

`tests/test_whatsapp_optin.py`

- Inserting an `outreach_whatsapp` row with `dispatch_mode='CLOUD_API'` and `optin_id=NULL` raises
  `IntegrityError`.
- The same with an expired opt-in raises.
- The same with a revoked opt-in raises.
- Revoking an opt-in between insert and the `API_ACCEPTED` update makes the update raise.
- `record_optin` refuses when a live suppression covers the business.
- An opt-in row cannot be deleted, and `revoked_at` cannot be cleared.

`tests/test_whatsapp_stop.py`

- Every lexicon entry matches its intended sample and none matches a benign SAMPLE reply such as
  "Please stop by our office next week".
- A STOP creates all three suppression scopes plus the opt-in revocation in one transaction.
- The scan runs with the classifier patched to raise, and the suppression is still written.

`tests/test_whatsapp_template.py`

- One case per `validate_template` code in §8.8.7.
- A body ending in `{{3}}` is rejected; the shipped template is accepted.
- `validate_params` rejects a newline, a tab, 5 spaces, the wrong count, and a `relevant_area` value
  not in `RELEVANT_AREA`.

`tests/test_whatsapp_webhook.py`

- A recorded SAMPLE payload for each of `sent`, `delivered`, `read`, `failed`, inbound text, button
  reply, `message_template_status_update`, `phone_number_quality_update`, `account_update`.
- Signature verification passes on the real bytes and fails after one byte is changed.
- The same payload delivered twice produces one `outreach_events` row.
- `read` arriving before `delivered` leaves `delivered_at` `NULL`.
- An unknown `field` returns 200 and writes `IGNORED_UNKNOWN_FIELD`.
- Error `368` trips the kill switch and leaves `whatsapp_api_enabled = 0`.

`tests/test_whatsapp_modes.py`

- Every row of §8.11's decision table, as a parameterised case, asserting mode and gate.
- A `CLOUD_API`-eligible business downgrades to `MANUAL_LINK` when the template is `PAUSED`, and
  blocks outright when a suppression exists.

All of it against fixtures, no network — `_CONTEXT.md` §1. The Graph API client is exercised through
a recorded-response transport, not a mock of our own functions.

---

## Open questions

1. **Four new tables.** `whatsapp_optins`, `whatsapp_templates`, `outreach_whatsapp` and
   `whatsapp_webhook_events` are not in `_CONTEXT.md` §6's canonical list, and neither are the id
   prefixes `opt_`, `wat_`, `waw_`, `wev_`. They are not foldable into existing tables: the opt-in
   ledger is a legal record with its own lifecycle, and putting WhatsApp columns on
   `outreach_messages` would channel-pollute a table three other documents depend on. If
   `01-data-model.md` names them differently, that wins.
2. **`SENT_MANUAL`.** The brief for this document calls it a delivery status; the canonical
   `outreach_messages.status` enum has no such value. §8.2.1 resolves it as
   `status='SENT'` + `delivery_state='SENT_MANUAL'`. If `01-data-model.md` prefers a
   `dispatch_mode` column directly on `outreach_messages` instead of a side table, only §8.3.3 and
   §8.3.8 change.
3. **Where the phone normaliser lives.** `normalise_in_phone()` is specified inside
   `radar/channels/whatsapp.py` because `_CONTEXT.md` §6's module list has no `radar/phones.py`, but
   `radar/discover.py`, `radar/research.py`, `radar/verify.py` and the PHONE channel all need it,
   and importing a channel module from the discovery pipeline is backwards. A small
   `radar/channels/numbers.py` or a top-level `radar/phones.py` is the cleaner home; I have not
   moved it because the module list is meant to be shared across the pack.
4. **`suppressions.reason` values.** `05-outreach-workflow.md` §5.3.2 fixes the CHECK list;
   `10-human-handoff.md` §10.2.3 already writes `LEGAL_LANGUAGE`, which is not in it. This document
   stays inside the existing list (`REPLY_OPT_OUT` for a STOP, `COMPLAINT` for a report, `MANUAL`
   for Sagar's own entry), but the enum needs one owner to reconcile it.
5. **Gate prefixes.** `05-outreach-workflow.md` reserves `H_*` and `I_*` for per-channel gates
   without enumerating them. This document uses `H_WA_*` for channel blocks and `I_WA_*` for
   API-mode downgrades. If the email document has already claimed conflicting names in those
   namespaces, the eligibility engine's gate registry needs a reconciliation pass.
6. **Graph API version.** Pinned in `config.yaml` as `v23.0` with no code depending on the value.
   Meta versions expire roughly two years after release; whoever builds this should check the
   changelog at build time rather than trusting a version number written in a design document.
7. **Cost figures.** No INR rate appears anywhere in this document, deliberately. Sagar must enter
   the current India marketing rate into `config.whatsapp.cost.marketing_inr_micros` before the API
   is enabled, and until he does, every cost cell renders `—`.
8. **Which number for manual mode.** §8.6.7 says "a dedicated business number, not the primary
   personal one", and code cannot enforce that. It belongs in `16-mvp-plan.md`'s setup checklist as
   a day-one purchase, alongside the second number that will eventually be burned into the Cloud
   API registration.
