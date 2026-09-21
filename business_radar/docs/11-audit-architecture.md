# 11. Audit architecture

This document decides how `business_radar` records what it did, so that six months after a message
went out Sagar can open one screen and read the whole causal chain — which sources were fetched,
which findings they produced, which of those findings the model was allowed to use, which prompt
version turned them into a sentence, what the policy engine said about that sentence, what Sagar
edited, what he approved, what the provider actually accepted, and what came back. It defines the
`audit_log` table and its append-only enforcement (triggers plus a per-row hash chain plus a daily
off-box anchor), the full taxonomy of audited actions with severity and retention, the §48 outreach
audit record and the §49 AI message audit record, the "explain this message" reconstruction view,
the `report_exports` archive with content hashing (§42), the DPDP erasure path that removes personal
data without destroying the trail, the backup and restore procedure including its ordering
dependency, and the specific SQL Sagar will run.

Owns spec §42, §48, §49. Depends on `01-data-model.md` (`businesses`, `research_findings`,
`sources`, `opportunities`), `05-outreach-workflow.md` (`outreach_drafts`, `outreach_messages`,
`outreach_approvals`, `outreach_events`, `suppressions`, `contact_policy`), `06-message-engine.md`
(prompt and claim-map contract), `09-response-classification.md` (`responses`),
`10-human-handoff.md` (`handoffs`), `13-api-endpoints.md` (route registry), `14-background-jobs.md`
(`jobs`, `job_runs`), `12-security-model.md` (`users`, sessions, RBAC).

---

## 11.1 The three questions this table has to answer

Everything below exists to make these three answerable from stored rows, without trusting anyone's
memory and without trusting the application code that wrote them.

| # | Question | Answered by | Failure if it cannot be answered |
|---|---|---|---|
| Q1 | "Why did this message go to this business, in these words?" | `explain_message()` — §11.9 | A business replies "where did you get that idea about us?" and there is no answer. The claim policy (invariant 4) becomes unfalsifiable. |
| Q2 | "Prove nothing was sent without my approval." | The invariant probe set — §11.14, probe P1 in particular — plus the hash chain | The one product promise (§45) is a claim, not a fact. |
| Q3 | "What did the Dhule report say on 26 Aug 2026, exactly?" | `report_exports` + `content_sha256` / `data_sha256` — §11.11 | Numbers quoted to a prospect cannot be reproduced; §8's "never fabricate them" has no enforcement after the fact. |

Three design consequences follow immediately, and the rest of the document is mostly detail on them:

1. **The audit row is written in the same transaction as the thing it audits, and before it.**
   Not after, not "best effort", not in a logging handler. Where the DB can enforce it, a trigger on
   the audited table refuses the write unless the audit row is already there (§11.7, §11.8).
2. **`audit_log` never stores raw personal data.** It stores ids, hashes, and masked displays. This
   is what makes a DPDP erasure request survivable: the personal data lives in mutable tables that
   can be redacted, and the immutable chain keeps working because there was never anything in it to
   erase (§11.12).
3. **`audit_log` is never pruned.** Retention applies to attached evidence files, not to rows. The
   arithmetic in §11.3.6 shows why this is affordable.

### 11.1.1 Scope boundary

| Concern | Owned here | Owned elsewhere |
|---|---|---|
| `audit_log` DDL, triggers, hash chain, export, anchor | yes | — |
| `report_exports` DDL, hashing, storage layout, retention | yes | report *content* and templates: `03-html-report.md` |
| Action taxonomy, severity, retention classes | yes | — |
| §48 / §49 record shapes, explain view | yes | draft/message columns: `05-outreach-workflow.md` |
| Backups and restore order | yes | Laptop setup and the daily operating routine: `16-mvp-plan.md` §16.8 |
| DPDP erasure mechanics | yes | consent/purpose text and lawful basis: `12-security-model.md` |
| `outreach_events` | no — it is the operational timeline of one message | `05-outreach-workflow.md` |
| RBAC, sessions, password/TOTP handling | no — only the audit rows they emit | `12-security-model.md` |

`outreach_events` and `audit_log` overlap deliberately and are not the same thing:

| | `outreach_events` | `audit_log` |
|---|---|---|
| Scope | one message | the whole system |
| Mutability | rows are inserted, table has no immutability triggers | append-only, hash-chained |
| Volume | ~10 rows per message | ~15 rows per business per campaign |
| Purpose | drive UI status, dedupe provider callbacks | evidence |
| If it disappeared | the outreach screen loses its timeline | the product loses its central claim |

Where a fact matters for evidence it goes in both. Duplication is cheap; a single-source design that
puts evidence in a mutable table is not.

---

## 11.2 Settled decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | One `audit_log` table for the whole system, not per-domain audit tables | A per-domain design cannot produce a single ordered chain, and the chain is the point. |
| D2 | `TEXT` primary key `aud_<ULID>`, plus a separate gapless `INTEGER seq` | The ULID is what other tables reference (`suppressions.released_audit_id`); `seq` is what the chain walks. A gap in `seq` is itself evidence. |
| D3 | Immutability = `BEFORE UPDATE` / `BEFORE DELETE` triggers that `RAISE(ABORT)` | SQLite has no append-only table mode. Triggers stop the application and stop a careless `sqlite3` session. They do not stop someone who drops the trigger; the chain covers that case. |
| D4 | Per-row SHA-256 hash chain: `row_hash = H(prev_hash ‖ length-prefixed field bytes)` | Makes any edit, deletion or reordering of a committed row detectable by a full-table scan, independent of the triggers. |
| D5 | Daily signed segment export to an append-only off-box store, plus an `AUDIT_ANCHOR` row and a Telegram anchor message | The chain alone does not survive an attacker who has the DB file *and* the code. The off-box copy and the third-party timestamped hash do. §11.5 is explicit about the limits. |
| D6 | No PII in `audit_log`; ids, SHA-256 hashes, and masked displays only | Erasure without breaking the chain (§11.12). |
| D7 | Bulky evidence (rendered prompts, raw model responses, raw provider payloads, raw inbound bodies) lives in **sidecar capture files** under `data/audit/capture/`, referenced by path + sha256 | Keeps the DB small enough to hash-verify in seconds and keeps erasure to a file delete. |
| D8 | `audit_log` rows are permanent; retention classes govern sidecars and export files | Pruning a hash chain requires an offline, trigger-dropping operation. Not worth it at this volume. |
| D9 | Action names live in a lookup table `audit_actions` with an FK from `audit_log.action` | Same precedent as `outreach_status_transitions` in `05-outreach-workflow.md`: a 70-value `CHECK` is migration-hostile, and severity/retention/visibility belong next to the name. |
| D10 | A `draft_findings` join table records which findings a draft used, in addition to the JSON arrays on `outreach_drafts` | "Every message that mentions finding X" must be a plain indexed join, not `json_each`, because it has to survive a Postgres port (`_CONTEXT.md` §2). |
| D11 | Minimum SQLite 3.38, asserted at startup in `radar/db.py` | `json_valid()` in a `CHECK`, `json_extract()`, `json_each()`, `LAG()` (3.25), `RETURNING` (3.35) and `VACUUM INTO` (3.27) are all used. Python 3.11 ships 3.39+ on all three target platforms. The `->>` operator is deliberately avoided: `json_extract()` is what ports cleanly. |

Both new tables (`audit_actions`, `draft_findings`) are extensions to the canonical list in
`_CONTEXT.md` §6 and are flagged in `## Open questions`.

---

## 11.3 The `audit_log` table

### 11.3.1 `audit_actions` — the catalogue

```sql
-- radar/migrations/030_audit_actions.sql
CREATE TABLE audit_actions (
    action        TEXT PRIMARY KEY,
    domain        TEXT NOT NULL CHECK (domain IN (
                      'RESEARCH','VERIFICATION','SELECTION','MESSAGE','POLICY','APPROVAL',
                      'SEND','DELIVERY','RESPONSE','HANDOFF','SUPPRESSION','CONFIG',
                      'ACCESS','EXPORT','DATA','SYSTEM')),
    severity      TEXT NOT NULL CHECK (severity IN ('INFO','NOTICE','CRITICAL')),
    sidecar_ret   TEXT NOT NULL CHECK (sidecar_ret IN
                      ('NONE','P180D','P1Y','P3Y','P7Y','PERMANENT')),
    user_visible  INTEGER NOT NULL CHECK (user_visible IN (0,1)),
    pii_class     TEXT NOT NULL CHECK (pii_class IN ('NONE','REFERENCE','HASHED','MASKED')),
    best_effort   INTEGER NOT NULL DEFAULT 0 CHECK (best_effort IN (0,1)),
    description   TEXT NOT NULL
);
```

| Column | Meaning |
|---|---|
| `severity` | `INFO` = routine, high volume, never alerts. `NOTICE` = a state change worth showing in a business timeline. `CRITICAL` = irreversible or safety-relevant; appears in the daily digest; a failed write aborts the operation. |
| `sidecar_ret` | How long the **evidence files** attached to this action are kept. `NONE` means the action has no sidecar. The `audit_log` row itself is always permanent. |
| `user_visible` | Whether the row is rendered in `/business/<id>` history and the campaign activity feed, or only in the raw audit view under `/settings`. |
| `pii_class` | The strongest class of data the row may contain. `NONE` = ids and enums. `REFERENCE` = foreign keys into tables that hold personal data. `HASHED` = SHA-256 of an identifier. `MASKED` = a partial display such as `sa***@abchospital.in`. There is deliberately no `RAW` value; the `CHECK` is the enforcement of decision D6. |
| `best_effort` | If 1, a failure to write this row logs an error and continues (e.g. `REPORT_DOWNLOADED`). If 0 — the default, and true for everything that matters — a failure rolls back the enclosing transaction. |

The catalogue is seeded by `radar/migrations/031_audit_actions_seed.sql`, generated from the tables
in §11.6. Adding an action is a migration, not a string literal in a call site; `audit.write()` with
an unknown action fails on the foreign key.

### 11.3.2 `audit_log` DDL

```sql
-- radar/migrations/032_audit_log.sql
CREATE TABLE audit_log (
    id             TEXT PRIMARY KEY,                  -- aud_<26-char Crockford base32>
    seq            INTEGER NOT NULL,                  -- 1-based, gapless, assigned in-transaction
    at             TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- who
    actor_kind     TEXT NOT NULL
                     CHECK (actor_kind IN ('HUMAN','SYSTEM','PROVIDER','ANONYMOUS')),
    actor_user_id  TEXT REFERENCES users(id),
    actor_label    TEXT NOT NULL,                     -- 'usr_sagar' | 'worker-1' | 'gmail' | '-'

    -- what
    action         TEXT NOT NULL REFERENCES audit_actions(action),
    entity_table   TEXT NOT NULL,                     -- canonical table name, or '-' for system rows
    entity_id      TEXT,                              -- primary key of the affected row

    -- the three axes every investigation starts from
    business_id    TEXT REFERENCES businesses(id),
    campaign_id    TEXT REFERENCES campaigns(id),
    message_id     TEXT REFERENCES outreach_messages(id),

    -- state delta
    before_json    TEXT,                              -- NULL for creates
    after_json     TEXT,                              -- NULL for deletes/tombstones
    detail_json    TEXT NOT NULL DEFAULT '{}',        -- action-specific payload; see §11.6

    -- request context
    request_id     TEXT,                              -- req_<ULID>, echoed as X-Request-Id
    session_id     TEXT,                              -- matches outreach_approvals.session_id
    route          TEXT,                              -- '/api/v1/outreach/out_.../approve'
    http_method    TEXT CHECK (http_method IS NULL OR
                     http_method IN ('GET','POST','PUT','PATCH','DELETE')),
    client_ip      TEXT,
    user_agent     TEXT,
    job_id         TEXT REFERENCES jobs(id),
    job_run_id     TEXT REFERENCES job_runs(id),

    -- chain
    prev_hash      TEXT NOT NULL,                     -- 64 lowercase hex
    row_hash       TEXT NOT NULL,                     -- 64 lowercase hex
    hash_version   INTEGER NOT NULL DEFAULT 1,

    CHECK (seq >= 1),
    CHECK (length(prev_hash) = 64 AND length(row_hash) = 64),
    CHECK (lower(prev_hash) = prev_hash AND lower(row_hash) = row_hash),
    CHECK (actor_kind <> 'HUMAN' OR actor_user_id IS NOT NULL),
    CHECK (json_valid(detail_json)),
    CHECK (before_json IS NULL OR json_valid(before_json)),
    CHECK (after_json  IS NULL OR json_valid(after_json)),
    CHECK (at LIKE '____-__-__T__:__:__Z')
);

CREATE UNIQUE INDEX ux_audit_seq       ON audit_log(seq);
CREATE UNIQUE INDEX ux_audit_row_hash  ON audit_log(row_hash);
CREATE INDEX ix_audit_at               ON audit_log(at);
CREATE INDEX ix_audit_action_at        ON audit_log(action, at);
CREATE INDEX ix_audit_entity           ON audit_log(entity_table, entity_id, at);
CREATE INDEX ix_audit_business_at      ON audit_log(business_id, at)  WHERE business_id IS NOT NULL;
CREATE INDEX ix_audit_campaign_at      ON audit_log(campaign_id, at)  WHERE campaign_id IS NOT NULL;
CREATE INDEX ix_audit_message_at       ON audit_log(message_id, at)   WHERE message_id IS NOT NULL;
CREATE INDEX ix_audit_actor_at         ON audit_log(actor_user_id, at);
CREATE INDEX ix_audit_request          ON audit_log(request_id)       WHERE request_id IS NOT NULL;
CREATE INDEX ix_audit_job_run          ON audit_log(job_run_id)       WHERE job_run_id IS NOT NULL;
```

Notes on specific columns:

- `entity_table` is the canonical table name from `_CONTEXT.md` §6, stored as text rather than as an
  enum `CHECK`, because a migration that adds a table should not have to alter `audit_log`. A
  startup assertion in `radar/db.py` verifies every distinct `entity_table` value is either `-` or a
  name in `sqlite_master`; a typo surfaces as a startup warning, not a silent orphan.
- `business_id`, `campaign_id`, `message_id` are denormalised copies. They are the difference
  between "the business timeline is one index seek" and "the business timeline is a JSON scan".
  `audit.write()` fills them from the entity when it can infer them, and callers may override.
- `actor_label` is `NOT NULL` on purpose. A row whose actor is unknown is worse than no row, because
  it looks like evidence. `audit.write()` refuses to run with no actor bound (§11.16).
- `user_agent` and `client_ip` are Sagar's own. On the settled deploy shape `client_ip` is
  `127.0.0.1` on every row, because waitress binds loopback and nothing else can reach it
  (§11.16.4); it is stored anyway, as the column that would show it if that ever stopped being
  true. `user_agent` is the one that still discriminates — "was this approval clicked from the
  browser I use, or from something else on this machine?"

### 11.3.3 Immutability triggers

```sql
-- radar/migrations/033_audit_log_immutable.sql

-- SQLite has no append-only table. This is the closest thing: any UPDATE or DELETE against
-- audit_log aborts the statement and its transaction. It stops application bugs and it stops
-- a hurried interactive session. It does not stop someone who first drops the trigger -
-- that is what the hash chain and the off-box export are for. See 11.4.
CREATE TRIGGER trg_audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: UPDATE is not permitted');
END;

CREATE TRIGGER trg_audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: DELETE is not permitted');
END;

-- The chain must be built at the head and nowhere else: seq is exactly one past the current
-- maximum, and prev_hash is exactly the row_hash of the row before it. Genesis (seq = 1) links
-- to 64 zeroes. An INSERT that tries to splice a row into the middle, or to fork the chain,
-- aborts here rather than producing a chain that only fails verification months later.
CREATE TRIGGER trg_audit_log_chain
BEFORE INSERT ON audit_log
WHEN NEW.seq <> 1 + (SELECT COALESCE(MAX(seq), 0) FROM audit_log)
   OR NEW.prev_hash <> COALESCE(
        (SELECT row_hash FROM audit_log WHERE seq = NEW.seq - 1),
        '0000000000000000000000000000000000000000000000000000000000000000')
BEGIN
    SELECT RAISE(ABORT, 'audit_log chain break: seq/prev_hash do not follow the current head');
END;

-- The catalogue's PII contract, enforced rather than documented: an action declared NONE may not
-- arrive carrying request context that identifies a person, and no action may carry an '@' in a
-- top-level detail key named 'address' - the masked/hashed forms use 'address_masked' and
-- 'address_sha256'. Cheap, and it catches the one mistake that would matter.
CREATE TRIGGER trg_audit_log_no_raw_address
BEFORE INSERT ON audit_log
WHEN json_extract(NEW.detail_json, '$.address') IS NOT NULL
   OR json_extract(NEW.detail_json, '$.contact.address') IS NOT NULL
   OR json_extract(NEW.detail_json, '$.to') IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
      'audit_log detail_json must use address_masked / address_sha256, never a raw address');
END;
```

`PRAGMA recursive_triggers` stays at its default `off`; none of these triggers write.

`PRAGMA foreign_keys = ON` matters here for a reason beyond tidiness: it is what makes
`action TEXT NOT NULL REFERENCES audit_actions(action)` reject an unregistered action string.
`radar/db.py` sets it on every connection and asserts `PRAGMA foreign_keys` returns 1 afterwards —
a connection that silently failed to enable it would let typo'd actions through.

### 11.3.4 Sequence assignment and concurrency

`seq` is assigned inside the writing transaction:

```sql
SELECT COALESCE(MAX(seq), 0) + 1 FROM audit_log;
```

That is a read-then-write race in general, and safe here for one specific reason: every write
transaction in `business_radar` opens with `BEGIN IMMEDIATE` (see `radar/db.py`), and SQLite in WAL
mode permits exactly one writer at a time. The `RESERVED` lock is taken before the `SELECT MAX`, so
no second transaction can read the same maximum. Two belts on top of that:

- `ux_audit_seq` turns a race into an `IntegrityError`, not a duplicate.
- `trg_audit_log_chain` turns a stale `prev_hash` into an abort.

`radar/audit.py` retries a `sqlite3.IntegrityError` on `ux_audit_seq` or `ux_audit_row_hash` at most
three times with a fresh `MAX(seq)` read, then gives up and lets the caller's transaction fail. It
never proceeds without an audit row.

The Postgres port replaces `SELECT MAX(seq)+1` with a sequence plus a `SELECT ... FOR UPDATE` on the
head row, or an advisory lock. Flagged here because it is the only place in the schema where the
storage engine's concurrency model is load-bearing.

### 11.3.5 The hash function

```python
# radar/audit.py

CHAIN_VERSION = 1

# Order is part of the hash. Appending a column means CHAIN_VERSION = 2 and a new
# genesis-free branch: old rows keep verifying under version 1, new rows under version 2,
# and verify_chain() dispatches on the stored hash_version. Never reorder this tuple.
CHAIN_FIELDS_V1: tuple[str, ...] = (
    "id", "seq", "at",
    "actor_kind", "actor_user_id", "actor_label",
    "action", "entity_table", "entity_id",
    "business_id", "campaign_id", "message_id",
    "before_json", "after_json", "detail_json",
    "request_id", "session_id", "route", "http_method", "client_ip", "user_agent",
    "job_id", "job_run_id",
    "hash_version",
)

GENESIS_HASH = "0" * 64
_NULL = b"\xff"


def _field(value: object | None) -> bytes:
    """Length-prefixed encoding so no field value can forge a field boundary.

    A plain separator (\\x1e, '|', anything) is forgeable: a value containing the separator
    lets an attacker move bytes between fields and keep the same digest. Four-byte big-endian
    length prefixes make the encoding injective, which is the property the chain needs.
    """
    if value is None:
        return _NULL
    raw = str(value).encode("utf-8")
    return len(raw).to_bytes(4, "big") + raw


def compute_row_hash(prev_hash: str, row: Mapping[str, object | None]) -> str:
    """SHA-256 over prev_hash and every chained field, in CHAIN_FIELDS_V1 order."""
    h = hashlib.sha256()
    h.update(bytes.fromhex(prev_hash))
    for name in CHAIN_FIELDS_V1:
        h.update(_field(row.get(name)))
    return h.hexdigest()


def canonical_json(obj: object) -> str:
    """The exact string that is both stored and hashed.

    json.dumps with sort_keys and no spaces. The bytes written into before_json /
    after_json / detail_json are the bytes fed to compute_row_hash - nothing anywhere
    re-serialises a JSON column, because a re-serialisation with different key order
    would silently break every downstream verification.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str)
```

Three rules that make this hold up:

1. **Store what you hashed.** `audit.write()` calls `canonical_json()` once, hashes that string, and
   binds that same string into the `INSERT`. No `json_set`, no `UPDATE ... json_patch` (both are
   blocked by `trg_audit_log_no_update` anyway), no ORM round-trip.
2. **Hash `prev_hash` as bytes, not hex.** `bytes.fromhex` also validates the stored value is real
   hex; a corrupted `prev_hash` raises before it can produce a plausible-looking digest.
3. **`hash_version` is inside the hash.** A future version-2 layout cannot be replayed as version 1.

Verification:

```python
@dataclass(frozen=True)
class ChainReport:
    checked: int
    first_bad_seq: int | None
    first_bad_reason: str | None       # 'HASH_MISMATCH' | 'PREV_MISMATCH' | 'SEQ_GAP'
    head_seq: int
    head_hash: str
    non_monotonic_at: list[int]        # seqs whose `at` went backwards; warning, not failure
    elapsed_ms: int


def verify_chain(conn: sqlite3.Connection, *, start_seq: int = 1,
                 stop_seq: int | None = None,
                 expect_prev_hash: str = GENESIS_HASH) -> ChainReport:
    """Walk the chain in seq order and recompute every row_hash.

    Stops at the first inconsistency and reports its seq, because after the first break
    every later row is unverifiable anyway and a list of 40,000 'errors' helps nobody.
    """
```

`start_seq`/`expect_prev_hash` exist so a tail verification (the default on startup) can begin at a
known-good anchor instead of rescanning years of rows.

Timestamp monotonicity is checked but never fatal. A laptop whose clock steps backwards on resume,
or during an NTP correction, should produce a warning in `ChainReport.non_monotonic_at`, not an
aborted insert that takes the application down. `at` is evidence of ordering only in combination
with `seq`, and `seq` is authoritative.

### 11.3.6 Volume, and why the table is never pruned

Estimated, not measured — SAMPLE figures for sizing only:

| Event | Audit rows | Notes |
|---|---|---|
| One campaign, 300 businesses discovered | ~1,500 | discovery, research run, findings rollup, scoring |
| Verification of 120 of them | ~400 | one open + one decision each, checklist toggles are not audited individually |
| 40 drafts prepared | ~200 | generate, policy, edits, preview, approve |
| 40 sends + delivery + responses | ~180 | send, delivery, bounce, response, classification |
| Daily system rows | ~10 | export, anchor, backup, verify, probes |
| **Per campaign, all in** | **~2,300** | |

At ~1.4 KB per row including indexes, one campaign is ~3.2 MB of audit. Two campaigns a week for
five years is ~1.7 GB. `verify_chain()` over 1.2 M rows is a sequential scan plus 1.2 M SHA-256
digests of ~1 KB each: seconds, not minutes, on the target laptop.

Therefore: **no pruning, no archival deletion, no rollover.** Retention classes in §11.6 apply to
sidecar files and export artefacts. The `audit_log` row survives the business, the campaign, the
contact and the erasure request, because by construction there is nothing in it that an erasure
request is entitled to remove.

If that ever stops being true, pruning is an offline procedure — stop the app, `DROP TRIGGER
trg_audit_log_no_delete`, export the segment off-box first, delete, recreate the trigger, and record
`AUDIT_CHAIN_PRUNED` as the first row of the shortened chain with the archived head hash in
`detail_json`. `trg_audit_log_chain` keeps working across a pruned prefix because it only ever looks
at `MAX(seq)`. This is documented so that if it ever happens it happens deliberately.

---

## 11.4 What immutability does and does not buy

Being honest about this is the point of the section. The chain is a tamper-**evidence** mechanism,
not a tamper-**prevention** mechanism, and the two are often confused.

| Threat | Prevented? | Detected? | By what |
|---|---|---|---|
| Application bug issues `UPDATE audit_log SET ...` | Yes | n/a | `trg_audit_log_no_update` — statement and transaction abort |
| Application bug issues `DELETE FROM audit_log` | Yes | n/a | `trg_audit_log_no_delete` |
| An ORM or admin UI tries a "soft delete" flag flip | Yes | n/a | Same trigger; there is no nullable status column to flip anyway |
| Sagar opens `sqlite3 data/radar.db` and deletes a row | Yes | n/a | Same trigger |
| Same, after `DROP TRIGGER trg_audit_log_no_delete` | No | Yes | `seq` gap + `prev_hash` mismatch at the following row → `verify_chain()` reports `SEQ_GAP` |
| A single field edited in place with a hex editor or `UPDATE` after dropping triggers | No | Yes | `row_hash` no longer matches recomputation → `HASH_MISMATCH` |
| Rows reordered | No | Yes | `prev_hash` linkage breaks |
| Rows appended with a back-dated `at` | No | Partly | `seq` ordering contradicts `at`; `non_monotonic_at` flags it; the daily anchor bounds when the row could have been inserted |
| Torn write / bit-rot / bad disk | No | Yes | `HASH_MISMATCH`, and `PRAGMA integrity_check` in the backup verifier |
| An old backup restored over the live DB, losing recent rows | No | Yes | `head_seq` regresses below the last `AUDIT_ANCHOR`'s `to_seq` — checked on startup |
| **Someone with the DB file and `radar/audit.py` rewrites the chain from row N forward** | **No** | **No — not from the DB alone** | Only the off-box copy and the external anchor catch this. See below. |
| Someone with the DB file *and* the box *and* the export key rewrites both DB and today's export | No | Only for days already anchored externally | The append-only remote and the Telegram anchor bound the damage to the current day |

### 11.4.1 The unfixable case, stated plainly

Anyone who holds `data/radar.db` and a copy of `radar/audit.py` can recompute a valid chain from any
point forward. Nothing in a single-file SQLite database on a machine the attacker controls can
prevent this. Sagar himself is that person, which is exactly why an auditor should not be asked to
take the local chain as proof.

What the local chain actually buys:

- it converts silent corruption into a loud, dated failure;
- it makes casual tampering (one row, one field, one deletion) impossible to do accidentally and
  impossible to do quietly;
- it makes a *partial* rewrite fail — you cannot change row 4,000 without recomputing rows 4,000 to
  head, which means the head hash changes, which is the value that was already published.

### 11.4.2 Mitigation: the off-box append-only copy

The property that survives a compromised box is: **yesterday's evidence is somewhere the box cannot
rewrite.** Three layers, cheapest first:

| Layer | Mechanism | Rewrites possible? | Cost |
|---|---|---|---|
| A. Daily signed segment export pushed to object storage with a **write-only, no-delete, no-overwrite** credential | `rclone`/`aws s3` with an IAM policy granting `s3:PutObject` only, plus bucket versioning and Object Lock in compliance mode for 7 years | No, not even with the box's own credentials | A few rupees a month |
| B. Head hash posted to the existing Telegram notification channel, once a day | `AUDIT_ANCHOR` message: `2026-08-26 head seq=41203 hash=9f3c…` | Not by Sagar's server; Telegram holds the timestamped copy | Free, already in the stack |
| C. Head hash mailed to a second mailbox Sagar does not administer | The same string in an email-to-self on a different provider | No | Free |

Layer A carries the data; layers B and C carry only the head hash but are the ones that make a
*date* provable. A hash of 64 hex characters sitting in a third party's log on 27 Aug 2026 is a
cheap, real anchor: it pins the entire prefix of the chain up to that seq, and no later rewrite can
produce that hash again for different contents.

The export HMAC key (`AUDIT_EXPORT_HMAC_KEY` in `config/.env`) is deliberately described as a
*integrity tag against transport and storage corruption*, not as a signature against the operator —
the operator has the key. If a genuinely operator-resistant signature is ever needed, it is an
offline Ed25519 private key held on a hardware token, and the export step becomes manual. That
tradeoff is recorded in `## Open questions` rather than pretended away.

---

## 11.5 Segment export and the daily anchor

### 11.5.1 Files

```
data/audit/exports/
  2026/
    08/
      audit-2026-08-26.jsonl.gz        # one canonical JSON object per row, seq order
      audit-2026-08-26.manifest.json   # the thing that is actually checked
      audit-2026-08-26.manifest.hmac   # hex HMAC-SHA256 of the manifest bytes
```

Manifest, SAMPLE:

```json
{
  "day": "2026-08-26",
  "generated_at": "2026-08-27T20:05:11Z",
  "from_seq": 40871,
  "to_seq": 41203,
  "row_count": 333,
  "prev_hash": "1a4f0c2d9b8e77c5a01d3e6f8b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90a1b2",
  "head_hash": "9f3c5e71b0d4a2f68c1e9037bd52a4c8e6f01b3d7a9c2e4f6081b3d5a7c9e2f4",
  "chain_verified": true,
  "hash_version": 1,
  "file": "audit-2026-08-26.jsonl.gz",
  "file_bytes": 214883,
  "file_sha256": "c3d1…",
  "db_schema_version": 41,
  "generator_version": "radar 0.4.2 (git 8f21a0c)"
}
```

`prev_hash` is the `row_hash` of the row before `from_seq`, so consecutive daily manifests chain to
each other independently of the database: a verifier with only the export directory can walk
2026-01-01 through 2026-08-26 and confirm no day was removed or replaced.

### 11.5.2 The job

```python
def export_segment(conn: sqlite3.Connection, *, day: date,
                   out_dir: Path) -> ExportManifest:
    """Write one immutable day-segment of the chain, verified before it is written.

    Runs after the day is closed (config: audit.daily_export_hour_utc). Refuses to run for
    today, because a partial segment would be re-exported tomorrow and the two files would
    disagree about to_seq - and a manifest that can be legitimately superseded is not evidence.
    """
```

Sequence, in order, with the failure each step prevents:

| Step | Action | Prevents |
|---|---|---|
| 1 | `verify_chain(start_seq=from_seq-1, ...)` over the segment | Exporting an already-broken chain and calling it evidence |
| 2 | Stream rows to `<file>.tmp`, gzip, computing SHA-256 as it writes | A second full read pass, and a hash of different bytes than were written |
| 3 | `os.replace()` to the final name (house rule: atomic writes) | A half-written export being picked up by the uploader |
| 4 | Write manifest `.tmp` → `os.replace()`; write `.hmac` the same way | Manifest referring to a file that is not there yet |
| 5 | Upload all three to the append-only remote; on failure retry, then alert | Silent loss of the only off-box copy |
| 6 | `audit.write(action='AUDIT_EXPORTED', detail=manifest)` | No record that the export happened |
| 7 | `audit.write(action='AUDIT_ANCHOR', detail={day, to_seq, head_hash, remote_uri, telegram_message_id})` and send the Telegram message | The head hash existing nowhere outside the box |

Steps 6 and 7 append rows, so tomorrow's segment starts one row after today's anchor. The anchor row
is inside the chain it anchors — which is correct: it commits to everything before it, and the
external copy of its `head_hash` is the part that lives outside.

### 11.5.3 Startup and periodic verification

| When | Mode | Config |
|---|---|---|
| Application start | `tail` — last `audit.verify_tail_rows` (default 5,000) from the last anchor | `audit.verify_on_start: tail` |
| Nightly, before the export | `full` from the last successful full verification's seq | job `audit_verify` |
| Monthly | `full` from seq 1 | job `audit_verify_full` |
| On demand | `python main.py audit verify [--full]` | — |

Any failure writes `AUDIT_CHAIN_BROKEN` (severity `CRITICAL`) — which itself appends to the broken
chain, deliberately, so the break and its discovery sit in the same file — sends a Telegram alert,
and sets the application into read-only mode: `radar/web/app.py` refuses every non-`GET` route
except `/settings` and login while `chain_ok` is false. The reasoning is that a system whose audit
trail is provably wrong must not send anything, because it can no longer honour Q2.

Startup also compares `chain_head().seq` against the `to_seq` of the newest `AUDIT_ANCHOR` row and
against the newest remote manifest. `head_seq < anchor.to_seq` means rows are missing — almost
always an accidental restore of an older backup — and produces the same read-only mode plus a
specific message naming the restore-order checklist in §11.13.

---

## 11.6 The action taxonomy

Every audited action in the system. Columns: the `audit_actions` catalogue values, plus the
`detail_json` keys the writer must supply and the question the row exists to answer.

Severity legend: `I` = INFO, `N` = NOTICE, `C` = CRITICAL. Visible = rendered in
`/business/<id>` history and campaign activity, per §11.10. Retention is the **sidecar** retention;
every row itself is permanent.

### 11.6.1 RESEARCH

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `CAMPAIGN_CREATED` | `campaigns` | HUMAN | N | NONE | yes | `cities[]`, `industries[]`, `size_min`, `min_opportunity_score`, `depth` — the exact §1 filters the campaign ran with |
| `CAMPAIGN_STARTED` | `campaigns` | HUMAN | N | NONE | yes | `job_id` |
| `CAMPAIGN_COMPLETED` | `campaigns` | SYSTEM | N | NONE | yes | `discovered`, `researched`, `qualified`, `skipped` — §2 counters at close |
| `BUSINESS_DISCOVERED` | `businesses` | SYSTEM | I | NONE | no | `city`, `industry`, `category`, `discovery_source`, `source_id`, `dedupe_key` — where the business came from at all |
| `RESEARCH_RUN_STARTED` | `research_runs` | SYSTEM | I | NONE | no | `depth`, `model_id`, `prompt_version` |
| `SOURCE_FETCHED` | `sources` | SYSTEM | I | P3Y | no | `url`, `source_type`, `http_status`, `content_sha256`, `snapshot_path`, `fetched_at`, `robots_allowed` — makes §14's "open the source" survive the page changing |
| `SOURCE_FETCH_FAILED` | `sources` | SYSTEM | I | P180D | no | `url`, `error`, `attempt` |
| `FINDING_RECORDED` | `research_findings` | SYSTEM | I | NONE | no | `kind`, `confidence`, `confidence_pct`, `source_ids[]`, `text_sha256` — the OBSERVED/INFERRED/UNKNOWN split (§12) at the moment it was decided |
| `RESEARCH_RUN_COMPLETED` | `research_runs` | SYSTEM | N | P3Y | yes | `findings_observed`, `findings_inferred`, `findings_unknown`, `model_id`, `prompt_version`, `input_tokens`, `output_tokens`, `capture_path`, `capture_sha256` |
| `OPPORTUNITY_SCORED` | `opportunities` | SYSTEM | I | NONE | yes | `score`, `band`, `confidence`, `weights_version`, `components{}`, `modules[]` — why the number is what it is |
| `SCORE_WEIGHTS_ADOPTED` | `contact_policy` | HUMAN | C | NONE | yes | `before`, `after` weight vectors (also in `before_json`/`after_json`) — see `10-human-handoff.md` §on learning loop |
| `BUSINESS_STATUS_CHANGED` | `businesses` | HUMAN/SYSTEM | N | NONE | yes | `from`, `to`, `trigger` — the §17 lifecycle, one row per transition |

### 11.6.2 VERIFICATION and REJECTION (§15–§17)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `VERIFICATION_OPENED` | `verifications` | HUMAN | I | NONE | no | `business_id`, `research_run_id` — Sagar actually opened the screen before deciding |
| `VERIFICATION_SAVED` | `verifications` | HUMAN | N | NONE | no | `checks_passed`, `checks_total`, `elapsed_s` — a draft save, not a decision |
| `BUSINESS_VERIFIED` | `businesses` | HUMAN | C | NONE | yes | `verification_id`, `checklist{}` (all nine §16 items with their boolean and note), `contact_id_confirmed`, `session_id` — the gate that makes outreach legal |
| `BUSINESS_REJECTED` | `businesses` | HUMAN | C | NONE | yes | `verification_id`, `reason_code`, `reason_note`, `checklist{}` — why this business will never be contacted |
| `BUSINESS_SKIPPED` | `businesses` | HUMAN/SYSTEM | N | NONE | yes | `reason_code` (`OUT_OF_SCOPE`, `BELOW_SCORE`, `NO_CONTACT`, `DUPLICATE`) |
| `VERIFICATION_EXPIRED` | `businesses` | SYSTEM | N | NONE | yes | `verified_at`, `verification_valid_days`, `policy_version` — §5.3.1 freshness; the business drops out of eligibility on its own |
| `VERIFICATION_REVOKED` | `verifications` | HUMAN | C | NONE | yes | `reason_note` — Sagar changed his mind after verifying |

`VERIFICATION_CHECK_TOGGLED` deliberately does **not** exist. Nine checkboxes toggled a few times
each is noise that would triple audit volume and answer nothing; the final `checklist{}` in
`BUSINESS_VERIFIED` / `BUSINESS_REJECTED` is what matters, and the intermediate state lives in
`verification_checks` where it belongs.

### 11.6.3 SELECTION (§18, §19)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `SELECTION_CREATED` | `selections` | HUMAN | N | NONE | yes | `campaign_id`, `city`, `industry`, `intent_channel`, `sequence_no`, `eligibility_snapshot{}`, `bulk_size` — a human, not a scheduler, put this business in the outreach set |
| `SELECTION_REMOVED` | `selections` | HUMAN | N | NONE | yes | `reason_note` |
| `SELECTION_BLOCKED` | `selections` | SYSTEM | N | NONE | yes | `gate`, `detail{}` — an attempted selection that the eligibility predicate refused |

### 11.6.4 MESSAGE (draft generation and human edit) — §22, §49

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `MESSAGE_GENERATED` | `outreach_drafts` | SYSTEM | N | P3Y | yes | the full §49 payload — §11.8 |
| `MESSAGE_REGENERATED` | `outreach_drafts` | HUMAN starts, SYSTEM runs | N | P3Y | yes | as above plus `supersedes_draft_id`, `reason` |
| `MESSAGE_EDITED` | `outreach_drafts` | HUMAN | N | P3Y | yes | `edit_no`, `before_sha256`, `after_sha256`, `chars_added`, `chars_removed`, `diff_path`, `diff_sha256`, `claims_touched[]` — exactly what Sagar changed and whether he edited a policy-relevant sentence |
| `MESSAGE_DISCARDED` | `outreach_drafts` | HUMAN | N | NONE | yes | `reason_note` |

### 11.6.5 POLICY (§12, §23, §29, §30, §31)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `MESSAGE_POLICY_CHECKED` | `outreach_drafts` | SYSTEM | N | P3Y | yes | `result` (`PASS`/`WARN`/`BLOCK`), `policy_version`, `rules_run[]`, `violations[]`, `claims[]`, `capture_path` |
| `POLICY_BLOCK` | `outreach_drafts` | SYSTEM | C | P3Y | yes | as above, plus `blocking_rules[]` — the invariant-4 refusal, kept separately so blocks are one indexed query |
| `ELIGIBILITY_BLOCK` | `outreach_messages` | SYSTEM | C | NONE | yes | `stage` (`SELECT`/`PREVIEW`/`SEND`), `gate`, `eligibility_snapshot{}` |
| `DUPLICATE_BLOCK` | `outreach_messages` | SYSTEM | C | NONE | yes | `rule` (`SAME_ADDRESS`/`SAME_BUSINESS`/`SAME_DOMAIN`/`RECENT_CAMPAIGN`/`MAX_ATTEMPTS`), `previous_message_id`, `days_since`, `limit` — §29 |
| `SUPPRESSION_BLOCK` | `outreach_messages` | SYSTEM | C | NONE | yes | `suppression_id`, `scope`, `reason`, `suppressed_at` — §30's DO NOT CONTACT panel, after the fact |
| `POLICY_VERSION_CHANGED` | `contact_policy` | HUMAN | C | NONE | yes | `before`, `after` |

### 11.6.6 APPROVAL (§28, §45)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `MESSAGE_PREVIEWED` | `outreach_drafts` | HUMAN | I | NONE | no | `preview_token`, `panels_rendered[]`, `eligibility_snapshot{}` — the §27 preview was actually rendered before approval |
| `OUTREACH_APPROVED` | `outreach_approvals` | HUMAN | C | NONE | yes | `approval_id`, `message_id`, `channel`, `approved_body_sha256`, `approved_subject_sha256`, `address_masked`, `address_sha256`, `confirmation_text_sha256`, `displayed{}`, `session_id`, `session_auth_method`, `client_ip`, `preview_to_approve_seconds` — the row that makes invariant 1 true |
| `OUTREACH_APPROVAL_REVOKED` | `outreach_approvals` | HUMAN | C | NONE | yes | `approval_id`, `reason` |

### 11.6.7 SEND (§48)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `OUTREACH_QUEUED` | `outreach_messages` | SYSTEM | I | NONE | no | `job_id`, `idempotency_key` |
| `OUTREACH_SENT` | `outreach_messages` | SYSTEM (on behalf of the approver) | C | P7Y | yes | the full §48 payload — §11.7 |
| `MANUAL_SEND_RECORDED` | `outreach_messages` | HUMAN | C | P7Y | yes | §48 payload with `provider='manual'`, plus `dispatch_method` (`WA_ME_LINK`/`OWN_MAIL_CLIENT`/`CALL`), `recorded_at`, `sent_at_claimed` |
| `OUTREACH_SEND_FAILED` | `outreach_messages` | SYSTEM | C | P7Y | yes | `failure_code`, `failure_detail`, `attempt_count`, `provider_status_code`, `provider_response_sha256`, `capture_path` |
| `OUTREACH_SEND_INDETERMINATE` | `outreach_messages` | SYSTEM | C | P7Y | yes | `idempotency_key`, `last_error`, `reconcile_due_at` — the crash-between-call-and-commit case (§11.7.4) |
| `OUTREACH_CANCELLED` | `outreach_messages` | HUMAN/SYSTEM | N | NONE | yes | `reason_code`, `from_status` |
| `OUTREACH_CANCELLED_BY_HANDOFF` | `outreach_messages` | SYSTEM | N | NONE | yes | `handoff_id`, `blocked_reason` — see `10-human-handoff.md` |
| `SEND_DISABLED_CHANGED` | `contact_policy` | HUMAN | C | NONE | yes | `before`, `after`, `reason` — the global kill switch, on and off |

### 11.6.8 DELIVERY — §7, §8 channel docs

The two `PROVIDER_CALLBACK*` actions are **reserved and unwritten in v1**: there is no inbound HTTP
path on this stack (`_CONTEXT.md` §2), so nothing POSTs to us and nothing produces them. They stay in
the taxonomy rather than being deleted, because `08-whatsapp-integration.md`'s Cloud API path wants
exactly this shape if a public endpoint ever exists (`07-email-integration.md` Open question 13).
The rows that *are* written on the email path come from `poll_inbox` parsing the mailbox, and
`07-email-integration.md` §7.9.5 is the mapping.

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `PROVIDER_CALLBACK` | `outreach_messages` | PROVIDER | I | P1Y | no | **Reserved, no writer in v1.** `provider`, `provider_event_id`, `event_type`, `signature_valid`, `payload_sha256`, `capture_path` — one row per accepted callback, before interpretation |
| `PROVIDER_CALLBACK_REJECTED` | `-` | ANONYMOUS | C | P1Y | no | **Reserved, no writer in v1.** `provider`, `reason` (`BAD_SIGNATURE`/`UNKNOWN_MESSAGE`/`REPLAY`/`MALFORMED`), `remote_ip`, `payload_sha256` |
| `OUTREACH_DELIVERED` | `outreach_messages` | PROVIDER | N | NONE | yes | `provider_event_id`, `delivered_at`, `latency_s` |
| `OUTREACH_BOUNCED` | `outreach_messages` | PROVIDER | C | P1Y | yes | `bounce_type` (`HARD`/`SOFT`), `provider_code`, `diagnostic_sha256`, `suppression_id` if one was created |
| `OUTREACH_COMPLAINED` | `outreach_messages` | PROVIDER | C | P7Y | yes | `provider_event_id`, `suppression_id` — a spam complaint, kept for seven years because it is the one thing an ESP will ask about |
| `OUTREACH_OPENED` | `outreach_messages` | PROVIDER | I | NONE | no | `provider_event_id` — recorded only if open tracking is enabled; off by default |
| `OUTREACH_CLICKED` | `outreach_messages` | PROVIDER | I | NONE | no | `provider_event_id`, `url_sha256` |

### 11.6.9 RESPONSE classification (§33)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `RESPONSE_RECEIVED` | `responses` | SYSTEM | N | P3Y | yes | `channel`, `from_address_masked`, `from_address_sha256`, `in_reply_to_message_id`, `body_sha256`, `body_chars`, `capture_path`, `match_method` (`THREAD_HEADER`/`ADDRESS`/`MANUAL`) |
| `RESPONSE_CLASSIFIED` | `responses` | SYSTEM | N | P3Y | yes | `classification`, `confidence`, `confidence_pct`, `model_id`, `prompt_version`, `input_tokens`, `output_tokens`, `rationale_sha256`, `capture_path`, `alternatives[]`. Two `model_id` forms are permitted and both are real: the resolved `gemini-2.5-flash` build the SDK returned, or the literal `deterministic` when `09-response-classification.md` §9.6 settled the class from the lexicon without calling a model. The columns behind these two keys are `responses.classifier_model_id` and `.classifier_prompt_version` |
| `RESPONSE_RECLASSIFIED` | `responses` | HUMAN | N | NONE | yes | `from`, `to`, `reason_note` — Sagar correcting the model, which is also the training signal |
| `RESPONSE_UNMATCHED` | `responses` | SYSTEM | N | P3Y | no | `from_address_sha256`, `subject_sha256` — an inbound message that matched no outreach thread |

### 11.6.10 HANDOFF (§34, §35)

Defined in `10-human-handoff.md`; catalogued here because the catalogue is the single registry.

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys |
|---|---|---|---|---|---|---|
| `HANDOFF_CREATED` | `handoffs` | SYSTEM | C | NONE | yes | `response_id`, `trigger_rule`, `classification`, `sla_ack_due_at`, `notified_via[]` |
| `HANDOFF_STATE_CHANGE` | `handoffs` | HUMAN/SYSTEM | N | NONE | yes | `from`, `to`, `via`, `sla_ack_met` |
| `HANDOFF_NOTE` | `handoffs` | HUMAN | I | NONE | yes | `text_sha256`, `chars` |
| `HANDOFF_FAST_DISMISS` | `handoffs` | HUMAN | N | NONE | yes | `reason` |
| `HANDOFF_SLA_BREACHED` | `handoffs` | SYSTEM | N | NONE | yes | `sla`, `due_at`, `overdue_minutes` |

### 11.6.11 SUPPRESSION (§30)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys / what it proves |
|---|---|---|---|---|---|---|
| `SUPPRESSION_CREATED` | `suppressions` | SYSTEM/HUMAN | C | P7Y | yes | `scope`, `value_sha256`, `value_masked`, `reason`, `source`, `source_ref`, `evidence_sha256` — never `value_norm` |
| `UNSUBSCRIBE_RECEIVED` | `suppressions` | ANONYMOUS | C | P7Y | yes | `token_sha256`, `message_id`, `remote_ip`, `user_agent`, `suppression_id` — proof the unsubscribe link worked, which is the thing a complaint disputes |
| `SUPPRESSION_RELEASED` | `suppressions` | HUMAN | C | PERMANENT | yes | `suppression_id`, `reason_note`, `authorised_by`, `evidence_path` — the row `trg_suppressions_release_needs_audit` in `05-outreach-workflow.md` requires; written by hand, from a DB session, never by application code |

`SUPPRESSION_RELEASED` is the only action in the catalogue with no code path that can emit it. It
exists so that the trigger in `05-outreach-workflow.md` has something to check against, and so that
the release, when it happens, is recorded by the same person who has to type the `UPDATE`.

### 11.6.12 CONFIG (§46, §47)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys |
|---|---|---|---|---|---|---|
| `CONFIG_CHANGED` | `contact_policy` | HUMAN | C | NONE | yes | `scope`, `fields[]`, full `before_json`/`after_json` of the changed columns |
| `AUTOMATION_MODE_CHANGED` | `contact_policy` | HUMAN | C | NONE | yes | `before`, `after`, `reason_note` — the §46 dial, separated from `CONFIG_CHANGED` because it is the one setting that changes what the product *is* |
| `PROMPT_VERSION_CHANGED` | `-` | HUMAN | C | PERMANENT | yes | `kind` (`RESEARCH`/`MESSAGE_EMAIL`/`MESSAGE_WHATSAPP`/`CLASSIFY`), `before`, `after`, `template_sha256`, `git_sha` |
| `TEMPLATE_CHANGED` | `-` | HUMAN | C | PERMANENT | yes | `template_id`, `before_sha256`, `after_sha256`, `git_sha` |
| `MIGRATION_APPLIED` | `schema_version` | SYSTEM | N | NONE | no | `version`, `filename`, `file_sha256`, `elapsed_ms` |
| `SECRET_ROTATED` | `-` | HUMAN | C | NONE | no | `secret_name`, `fingerprint_before`, `fingerprint_after` — fingerprint is SHA-256 of the value truncated to 8 hex chars; the value itself never appears |

### 11.6.13 ACCESS (login) — mechanism in `12-security-model.md`

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys |
|---|---|---|---|---|---|---|
| `LOGIN_SUCCEEDED` | `users` | HUMAN | N | NONE | no | `session_id`, `auth_method` (`PASSWORD`/`PASSWORD_TOTP`), `client_ip`, `user_agent`, `new_device` |
| `LOGIN_FAILED` | `users` | ANONYMOUS | N | P1Y | no | `username_sha256`, `reason` (`BAD_PASSWORD`/`BAD_TOTP`/`LOCKED`/`UNKNOWN_USER`), `client_ip`, `attempt_no` |
| `LOGIN_LOCKED` | `users` | SYSTEM | C | P1Y | no | `username_sha256`, `client_ip`, `attempts`, `unlock_at` |
| `LOGOUT` | `users` | HUMAN | I | NONE | no | `session_id`, `reason` (`USER`/`IDLE`/`ABSOLUTE`) |
| `SESSION_EXPIRED` | `users` | SYSTEM | I | NONE | no | `session_id`, `lifetime_s` |
| `PASSWORD_CHANGED` | `users` | HUMAN | C | NONE | no | `session_id` |
| `TOTP_ENROLLED` / `TOTP_RESET` | `users` | HUMAN | C | NONE | no | `session_id` |
| `API_TOKEN_CREATED` / `API_TOKEN_REVOKED` | `users` | HUMAN | C | NONE | no | `token_id`, `scopes[]`, `token_fingerprint` |
| `ACCESS_DENIED` | `-` | HUMAN/ANONYMOUS | N | NONE | no | `route`, `required_role`, `actual_role` |

`LOGIN_FAILED` stores `username_sha256`, not the username. A brute-force attempt against a
non-existent account should not turn the audit log into a list of guessed email addresses.

### 11.6.14 EXPORT (§41, §42)

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys |
|---|---|---|---|---|---|---|
| `REPORT_GENERATED` | `report_exports` | SYSTEM | N | PERMANENT | yes | `fmt`, `scope`, `rel_path`, `content_sha256`, `data_sha256`, `row_count`, `filters{}`, `contains_pii`, `template_version` |
| `REPORT_DOWNLOADED` | `report_exports` | HUMAN | I | NONE | no | `rel_path`, `content_sha256`, `bytes_sent` — `best_effort = 1` |
| `DATA_EXPORTED` | `report_exports` | HUMAN | C | P180D | yes | `fmt` (`CSV`/`XLSX`), `columns[]`, `row_count`, `contains_pii`, `content_sha256` — a file with contact columns left the system |
| `SUBJECT_ACCESS_EXPORTED` | `report_exports` | HUMAN | C | P7Y | yes | `subject_sha256`, `tables[]`, `row_count`, `content_sha256` — a DPDP access request was answered |
| `REPORT_FILE_DELETED` | `report_exports` | SYSTEM/HUMAN | N | PERMANENT | yes | `rel_path`, `content_sha256`, `deleted_reason` |

### 11.6.15 DATA (deletion, retention) — §11.12

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys |
|---|---|---|---|---|---|---|
| `ERASURE_REQUESTED` | `business_contacts` | HUMAN | C | P7Y | yes | `subject_kind`, `subject_sha256`, `received_via`, `received_at`, `request_evidence_path`, `scope_preview{}` |
| `ERASURE_EXECUTED` | `business_contacts` | SYSTEM | C | P7Y | yes | the full erasure receipt — §11.12.4 |
| `ERASURE_DEFERRED` | `business_contacts` | HUMAN | C | P7Y | yes | `subject_sha256`, `reason` (`LEGAL_HOLD`/`OPEN_COMPLAINT`/`ACTIVE_DISPUTE`), `review_at` |
| `RETENTION_PURGE` | `-` | SYSTEM | N | PERMANENT | no | `class`, `files_deleted`, `bytes_freed`, `oldest_kept_at` |
| `SUPPRESSION_PSEUDONYMISED` | `suppressions` | SYSTEM | C | P7Y | yes | `suppression_id`, `value_sha256` — the row survived erasure; §11.12.3 |

### 11.6.16 SYSTEM

| Action | `entity_table` | Actor | Sev | Sidecar | Visible | `detail_json` keys |
|---|---|---|---|---|---|---|
| `AUDIT_EXPORTED` | `-` | SYSTEM | I | PERMANENT | no | the manifest of §11.5.1 |
| `AUDIT_ANCHOR` | `-` | SYSTEM | N | PERMANENT | no | `day`, `from_seq`, `to_seq`, `head_hash`, `remote_uri`, `telegram_message_id` |
| `AUDIT_CHAIN_VERIFIED` | `-` | SYSTEM | I | NONE | no | `mode`, `start_seq`, `head_seq`, `elapsed_ms` |
| `AUDIT_CHAIN_BROKEN` | `-` | SYSTEM | C | PERMANENT | yes | `first_bad_seq`, `reason`, `head_seq`, `last_good_anchor` |
| `BACKUP_TAKEN` | `-` | SYSTEM | I | NONE | no | `path`, `bytes`, `sha256`, `head_seq`, `head_hash`, `remote_uri` |
| `BACKUP_RESTORE_TESTED` | `-` | SYSTEM | N | P1Y | yes | `archive`, `assertions{}`, `passed`, `elapsed_s` |
| `BACKUP_RESTORED` | `-` | HUMAN | C | PERMANENT | yes | `archive`, `taken_at`, `head_seq_before`, `head_seq_after`, `erasure_replayed`, `reconciled_messages` |
| `JOB_FAILED_TERMINAL` | `job_runs` | SYSTEM | N | P180D | no | `kind`, `attempts`, `error_class`, `capture_path` |
| `INVARIANT_PROBE_FAILED` | `-` | SYSTEM | C | PERMANENT | yes | `probe`, `row_count`, `sample_ids[]` — §11.14 |

### 11.6.17 Retention class summary

| Class | Duration | Applies to | Enforced by |
|---|---|---|---|
| `PERMANENT` | forever | audit rows (all), export manifests, anchors, prompt/template version history, report hashes | nothing deletes them |
| `P7Y` | 7 years | complaint evidence, unsubscribe evidence, send captures, erasure receipts | job `retention_purge`, nightly |
| `P3Y` | 3 years | LLM prompt/completion captures, source snapshots, policy captures, response bodies | job `retention_purge` |
| `P1Y` | 1 year | provider webhook payloads, failed-login detail, restore-test detail | job `retention_purge` |
| `P180D` | 180 days | CSV/XLSX exports containing contacts, job failure captures, fetch-failure detail | job `retention_purge` |
| `NONE` | — | no sidecar exists | — |

The purge job deletes **files** and writes one `RETENTION_PURGE` row per class per run. It never
touches a database row in `audit_log`. Where a purge removes a sidecar referenced by an audit row,
the row keeps the path and the sha256, and `explain_message()` renders that band as
`evidence expired (P3Y) — sha256 c3d1…` rather than pretending nothing was there.

---

## 11.7 The outreach audit record (§48)

Spec §48: *"Every send creates an immutable-style audit record: Business, Contact, Channel, Message,
Research ID, Campaign ID, User approval, Timestamp, Provider response, Delivery status."*

That record is one `audit_log` row with `action = 'OUTREACH_SENT'`, written **inside the same
transaction that flips `outreach_messages.status` to `SENT`, and before the flip**.

### 11.7.1 Where each §48 field comes from

| §48 field | Location in the audit row | Source of truth | Why not stored raw |
|---|---|---|---|
| Business | `business_id` column + `detail.business{id,name,city,industry,category,size_band}` | `businesses` | Name is snapshotted so a later rename does not rewrite history |
| Contact | `detail.contact{contact_id,kind,address_masked,address_sha256,domain,source,collected_at,collected_from}` | `business_contacts`, `outreach_messages.to_address_norm` | D6 — the raw address lives in erasable tables; `address_sha256` still proves identity, `domain` still supports debugging |
| Channel | `detail.channel` | `outreach_messages.channel` | — |
| Message | `message_id` column + `detail.message{draft_id,subject_sha256,body_sha256,body_chars,sequence_no,thread_key,template_id,template_version}` | `outreach_messages` | The body itself is in `outreach_messages.body_final` and `outreach_approvals.approved_body`; the hash is what survives erasure |
| Research ID | `detail.research{research_run_id,opportunity_id,opportunity_score,finding_ids[],observed_count,inferred_count}` | `research_runs`, `opportunities`, `draft_findings` | Pinned ids, so §11.9 reconstructs the state at generation time, not the state today |
| Campaign ID | `campaign_id` column + `detail.campaign{id,name,selection_id}` | `campaigns`, `selections` | — |
| User approval | `detail.approval{approval_id,approved_by,approved_at,session_id,session_auth_method,client_ip,approved_body_sha256,confirmation_text_sha256,body_hash_matches}` | `outreach_approvals` | — |
| Timestamp | `at` column + `detail.timing{queued_at,attempt_started_at,sent_at,provider_latency_ms}` | `outreach_messages` | `at` is the audit clock; `sent_at` is the message clock; both are kept because they can differ by seconds |
| Provider response | `detail.provider{name,message_id,status_code,accepted,response_sha256,response_excerpt,capture_path,idempotency_key}` | provider SDK result | Full body is a sidecar; excerpt is capped at 240 chars and address-scrubbed |
| Delivery status | `detail.delivery{status_at_write,delivered_at}` | `outreach_messages.status` | Delivery is asynchronous; the §48 row records the status **at send time**, and later `OUTREACH_DELIVERED` / `OUTREACH_BOUNCED` rows extend it. §11.7.6 explains why this is not a gap. |

Two fields §48 does not ask for and the row carries anyway, because Q2 needs them:

| Extra field | Why |
|---|---|
| `detail.eligibility{}` — the full snapshot of every gate at `stage = SEND` | §29/§30/§31 were checked and passed. Without it, "no duplicate block fired" is an absence of evidence rather than evidence. |
| `detail.policy{result,policy_version,checked_at,violations_count}` | Invariant 4. The message that went out passed a specific version of the claim policy, and that version is a git-tracked file. |

### 11.7.2 The payload — SAMPLE

```json
{
  "id": "aud_01JSAMPLE00000000000SEND1",
  "seq": 41197,
  "at": "2026-08-26T11:42:07Z",
  "actor_kind": "SYSTEM",
  "actor_user_id": "usr_sagar",
  "actor_label": "worker-1",
  "action": "OUTREACH_SENT",
  "entity_table": "outreach_messages",
  "entity_id": "msg_01JSAMPLE0000000000000007",
  "business_id": "biz_01JSAMPLE0000000000000042",
  "campaign_id": "cmp_01JSAMPLE0000000000000003",
  "message_id": "msg_01JSAMPLE0000000000000007",
  "before_json": {"status": "QUEUED"},
  "after_json":  {"status": "SENT"},
  "request_id": null,
  "session_id": null,
  "job_id": "job_01JSAMPLE0000000000000019",
  "job_run_id": "jrn_01JSAMPLE0000000000000031",
  "detail_json": {
    "channel": "EMAIL",
    "business": {
      "id": "biz_01JSAMPLE0000000000000042",
      "name": "ABC Hospital",
      "city": "Dhule",
      "industry": "HEALTHCARE",
      "category": "HOSPITAL",
      "size_band": "MEDIUM"
    },
    "contact": {
      "contact_id": "cnt_01JSAMPLE0000000000000058",
      "kind": "BUSINESS_GENERIC",
      "address_masked": "in***@abchospital.example",
      "address_sha256": "4b2e9a17c8d0f35e6a19b74c2d8e0f31a5c7e9b1d3f5a7c9e1b3d5f7a9c1e3b5",
      "domain": "abchospital.example",
      "source": "WEBSITE_CONTACT_PAGE",
      "collected_at": "2026-08-24T06:18:44Z",
      "collected_from": "src_01JSAMPLE0000000000000112"
    },
    "message": {
      "draft_id": "out_01JSAMPLE0000000000000021",
      "sequence_no": 1,
      "thread_key": "biz_01JSAMPLE0000000000000042:EMAIL:4b2e9a17",
      "template_id": "email_generic_v3",
      "template_version": "msg-email-v3",
      "subject_sha256": "7c1d0a44b8e2f60931cd75ae02b4f8619d3c5a7e0f2b4d6a8c0e2f4b6d8a0c2e",
      "body_sha256": "a90f2c8e5b71d34f6082ae19c7d5b3f10e8a6c4d2b0f8e6a4c2d0b8f6e4a2c0d",
      "body_chars": 1184,
      "edited_by_human": true,
      "edit_count": 2
    },
    "research": {
      "research_run_id": "res_01JSAMPLE0000000000000077",
      "opportunity_id": "opp_01JSAMPLE0000000000000090",
      "opportunity_score": 86,
      "opportunity_band": "HIGH",
      "research_confidence": "MEDIUM",
      "finding_ids": ["fnd_01JSAMPLEA1", "fnd_01JSAMPLEA2", "fnd_01JSAMPLEB7"],
      "observed_count": 2,
      "inferred_count": 1,
      "model_id": "gemini-2.5-flash",
      "prompt_version": "msg-email-v3"
    },
    "campaign": {
      "id": "cmp_01JSAMPLE0000000000000003",
      "name": "Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026",
      "selection_id": "sel_01JSAMPLE0000000000000014"
    },
    "approval": {
      "approval_id": "apr_01JSAMPLE0000000000000012",
      "approved_by": "usr_sagar",
      "approved_at": "2026-08-26T11:41:52Z",
      "session_id": "ses_01JSAMPLE0000000000000004",
      "session_auth_method": "PASSWORD_TOTP",
      "client_ip": "127.0.0.1",
      "approved_body_sha256": "a90f2c8e5b71d34f6082ae19c7d5b3f10e8a6c4d2b0f8e6a4c2d0b8f6e4a2c0d",
      "confirmation_text_sha256": "e5b1077c9a3d5f7092b4d6e8a0c2f4b6d8e0a2c4f6b8d0e2a4c6f8b0d2e4a6c8",
      "body_hash_matches": true,
      "preview_to_approve_seconds": 96
    },
    "policy": {
      "result": "PASS",
      "policy_version": "claim-v2",
      "checked_at": "2026-08-26T11:40:44Z",
      "violations_count": 0,
      "warnings_count": 1
    },
    "eligibility": {
      "stage": "SEND",
      "verified": true,
      "verified_at": "2026-08-25T09:02:11Z",
      "contact_ready": true,
      "suppression_hit": null,
      "duplicate_hit": null,
      "days_since_last_contact": null,
      "attempts_used": 0,
      "attempts_max": 3,
      "handoff_open": false,
      "daily_cap_used": 7,
      "daily_cap": 25,
      "policy_version": "cp-1"
    },
    "provider": {
      "name": "gmail",
      "message_id": "msg_01JSAMPLE0000000000000007@gmail.com",
      "status_code": 250,
      "accepted": true,
      "idempotency_key": "msg_01JSAMPLE0000000000000007:1",
      "response_sha256": "b71e3d5f7092a4c6e8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f0a2c4",
      "response_excerpt": "250 2.0.0 OK  1756208526 SAMPLEd2sm4419qkf.7 - gsmtp",
      "capture_path": "capture/2026/08/msg_01JSAMPLE0000000000000007/provider.json.gz"
    },
    "timing": {
      "queued_at": "2026-08-26T11:41:52Z",
      "attempt_started_at": "2026-08-26T11:42:05Z",
      "sent_at": "2026-08-26T11:42:06Z",
      "provider_latency_ms": 641,
      "attempt_count": 1
    },
    "delivery": {
      "status_at_write": "SENT",
      "delivered_at": null
    },
    "sending": {
      "from_domain": "mail.example-outreach.in",
      "from_address_masked": "sa***@mail.example-outreach.in",
      "unsubscribe_url_sha256": "0c4a6e8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f0a2c4e6b8d0f2a4c",
      "list_unsubscribe_header": true
    }
  }
}
```

`response_excerpt` is stored as text and passes `trg_audit_log_no_raw_address` only because the
scrubber in `radar/audit.py` runs first: `_scrub_addresses()` replaces anything matching an email or
E.164 pattern with `<addr:sha8>` before the excerpt is stored. The provider capture file keeps the
unscrubbed body under `P7Y`.

Two keys in the `provider` block read differently on this stack than they would against an ESP HTTP
API, and the SAMPLE above is written the way the code actually produces them. `status_code` is the
**SMTP reply code** — `250` is the accepted case, and `response_excerpt` is the greeting line the
server returned, not JSON. `provider.message_id` is **our own** RFC 5322 `Message-ID` with the angle
brackets stripped, not an id the provider minted: SMTP submission returns no addressable id of its
own, so `07-email-integration.md` §7.8.1 generates a deterministic one before the socket is opened
and §7.10.2 makes it the reconciliation key.

### 11.7.3 Written inside the send transaction

`05-outreach-workflow.md` §5.2 splits the send into a claim phase, a provider call outside any write
transaction, and a recording phase. The §48 row belongs to the recording phase, and it goes in
first.

```python
# radar/channels/base.py

def record_send(conn: sqlite3.Connection, *, message: OutreachMessage,
                result: ProviderResult, elig: Eligibility) -> str:
    """Turn a provider acceptance into a SENT message and its §48 audit record.

    Everything here is one BEGIN IMMEDIATE transaction. The audit row is inserted before
    the status flip because trg_om_sent_needs_audit refuses the flip otherwise: the
    database, not this function, is what guarantees that a SENT row has a §48 record.
    """
    with db.tx(conn):                                   # BEGIN IMMEDIATE ... COMMIT
        aud_id = audit.write(
            conn,
            action="OUTREACH_SENT",
            entity_table="outreach_messages",
            entity_id=message.id,
            business_id=message.business_id,
            campaign_id=message.campaign_id,
            message_id=message.id,
            before={"status": message.status},
            after={"status": "SENT"},
            detail=build_send_detail(conn, message=message, result=result, elig=elig),
        )
        cur = conn.execute(
            """
            UPDATE outreach_messages
               SET status               = 'SENT',
                   sent_at              = :sent_at,
                   provider             = :provider,
                   provider_message_id  = :provider_message_id,
                   provider_status_code = :status_code,
                   provider_response    = :response_json,
                   attempt_count        = attempt_count + 1,
                   eligibility_snapshot = :elig_json,
                   worker_id            = :worker_id
             WHERE id = :id AND status = 'QUEUED'
            """,
            params,
        )
        if cur.rowcount != 1:
            raise ConcurrentSendError(message.id)       # rolls back, audit row included
        conn.execute(
            "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, detail)"
            " VALUES (?,?,'SENT','SYSTEM',?,?)", event_params,
        )
        conn.execute(
            "UPDATE businesses SET status='CONTACTED' WHERE id=? AND status='CONTACT_READY'",
            (message.business_id,),
        )
        conn.execute("UPDATE selections SET state='DISPATCHED' WHERE id=?",
                     (message.selection_id,))
    return aud_id
```

The database side of the guarantee:

```sql
-- radar/migrations/034_outreach_sent_needs_audit.sql
--
-- §48, enforced. A message cannot reach SENT unless its audit record already exists in the
-- same transaction. Combined with trg_om_send_needs_approval from 05-outreach-workflow.md,
-- SENT means: a live approval exists, its body hash matches what is being sent, and there is
-- an OUTREACH_SENT audit row naming this message. Application code cannot arrange otherwise.
CREATE TRIGGER trg_om_sent_needs_audit
BEFORE UPDATE OF status ON outreach_messages
WHEN NEW.status = 'SENT'
 AND NOT EXISTS (SELECT 1 FROM audit_log a
                 WHERE a.message_id = NEW.id
                   AND a.action IN ('OUTREACH_SENT','MANUAL_SEND_RECORDED'))
BEGIN
    SELECT RAISE(ABORT, 'SENT requires an OUTREACH_SENT audit row written first in the same txn');
END;

-- The same pattern one step earlier: an approval row cannot exist without its audit row.
-- The apr_ id is minted in Python before the INSERT, so the audit row can name it.
CREATE TRIGGER trg_oa_needs_audit
BEFORE INSERT ON outreach_approvals
WHEN NOT EXISTS (SELECT 1 FROM audit_log a
                 WHERE a.action = 'OUTREACH_APPROVED'
                   AND a.entity_table = 'outreach_approvals'
                   AND a.entity_id = NEW.id)
BEGIN
    SELECT RAISE(ABORT, 'an approval requires an OUTREACH_APPROVED audit row written first');
END;
```

This is the same shape as `trg_suppressions_release_needs_audit` in `05-outreach-workflow.md`, and
it is used for exactly the three operations that are irreversible from the recipient's point of
view: approving, sending, and un-suppressing.

### 11.7.4 The indeterminate case

The provider call is outside the write transaction, so there is a window: `smtp.gmail.com` accepted
the mail and the process died before the recording transaction committed. On restart the message is still
`QUEUED` with an unchanged `attempt_count`, and a naive retry sends it twice.

Resolution, in order:

1. The claim phase writes `outreach_events(SEND_ATTEMPT)` with the `idempotency_key` **before** the
   provider call, in its own committed transaction. There is therefore always a durable record that
   a call was about to happen.
2. On restart, `reconcile_indeterminate_sends()` finds every `QUEUED` message with a `SEND_ATTEMPT`
   event older than the lease and no `SENT`/`FAILED` outcome, writes
   `OUTREACH_SEND_INDETERMINATE`, and asks the transport whether the message went out before doing
   anything else. On `gmail` there is no provider API to ask: `07-email-integration.md` §7.10.4
   searches `[Gmail]/Sent Mail` over the IMAP connection `poll_inbox` already uses, keyed on the
   derived `Message-ID`, then the plus-tagged `Reply-To`, then `X-Google-Original-Message-ID`. On
   the `null` transport the `.eml` file either exists or it does not. WhatsApp Cloud has a real
   message id and a real lookup.
3. If the provider says it accepted, `record_send()` runs with the recovered result and
   `detail.provider.recovered = true`. If the provider says nothing matches, the message returns to
   `QUEUED` for a normal retry.
4. If the provider cannot answer, the message goes to `FAILED` with
   `failure_code = 'INDETERMINATE'` and **is not retried**. Sending twice is worse than not sending;
   §31 exists precisely so that this system is not the sender who does that.

`OUTREACH_SEND_INDETERMINATE` is `CRITICAL` and appears in the daily digest, because a system that
routinely cannot tell whether it sent something needs looking at.

### 11.7.5 Manual and click-to-chat channels

`WHATSAPP` without a recorded opt-in, and `PHONE`, do not have a provider call. `_CONTEXT.md` §4 is
explicit that the honest MVP answer for WhatsApp is a `wa.me` link Sagar clicks. The audit record is
`MANUAL_SEND_RECORDED` and its shape is identical to §11.7.2 except:

| Key | Manual value |
|---|---|
| `provider.name` | `"manual"` |
| `provider.message_id` | `null` |
| `provider.accepted` | `null` — the system did not observe the send |
| `dispatch_method` | `"WA_ME_LINK"` / `"OWN_MAIL_CLIENT"` / `"CALL"` |
| `dispatch_link_sha256` | SHA-256 of the exact `wa.me` URL that was rendered, so the number and prefilled text are provable |
| `sent_at_claimed` | what Sagar typed |
| `recorded_at` | when he pressed the button |
| `attestation` | the verbatim sentence he confirmed: `"I sent this message, as shown, to this contact."` |

`detail.provider.accepted = null` rather than `true` is deliberate. The system genuinely does not
know a WhatsApp message was delivered; recording `true` would be the system asserting something it
did not observe — the same error the claim policy exists to prevent in message bodies.

### 11.7.6 Delivery status after the fact

§48 lists "Delivery status" as part of the send record, but delivery happens minutes to hours later.
The design: the `OUTREACH_SENT` row carries `delivery.status_at_write`, and later provider callbacks
append their own rows (`OUTREACH_DELIVERED`, `OUTREACH_BOUNCED`, `OUTREACH_COMPLAINED`), each
carrying `message_id`. The §48 "record" is therefore the ordered set of rows for that `message_id`,
and `explain_message()` presents it as one band. The alternative — updating the send row when the
callback arrives — is exactly what `trg_audit_log_no_update` forbids, and for good reason: a record
that changes after the fact is not a record.

---

## 11.8 The AI message audit record (§49)

Spec §49: *"Store: Original research, Facts used, Inferences used, Prompt/version, Generated
message, Policy result, Human edits, Final message, Approval, Send result. So Sagar can understand
exactly why the AI generated the message."*

This spans five audit actions and one join table. §11.9 is the view that reassembles them.

### 11.8.1 Where each §49 field lives

| §49 field | Action carrying it | Column / key | Also in |
|---|---|---|---|
| Original research | `MESSAGE_GENERATED` | `detail.research{research_run_id,opportunity_id,summary_sha256}` | `research_runs`, `opportunities` |
| Facts used | `MESSAGE_GENERATED` | `detail.facts[]` (OBSERVED) | `draft_findings` role `FACT`; `outreach_drafts.facts_used` |
| Inferences used | `MESSAGE_GENERATED` | `detail.inferences[]` (INFERRED) | `draft_findings` role `INFERENCE`; `outreach_drafts.inferences_used` |
| Prompt / version | `MESSAGE_GENERATED` | `detail.generation{model_id,prompt_version,template_id,template_sha256,params,bindings_sha256,prompt_sha256,capture_path}` | `outreach_drafts.model_id`, `.prompt_version` |
| Generated message | `MESSAGE_GENERATED` | `detail.output{body_sha256,subject_sha256,body_chars,finish_reason,input_tokens,output_tokens,thinking_tokens}` | `outreach_drafts.body` |
| Policy result | `MESSAGE_POLICY_CHECKED`, `POLICY_BLOCK` | `detail.result`, `detail.violations[]`, `detail.claims[]` | `outreach_drafts.policy_result`, `.policy_detail` |
| Human edits | `MESSAGE_EDITED`, one row per save | `detail{edit_no,before_sha256,after_sha256,diff_path,claims_touched[]}` | `outreach_drafts.body_edited`, `.edit_count` |
| Final message | `OUTREACH_APPROVED` | `detail.approved_body_sha256` | `outreach_approvals.approved_body` |
| Approval | `OUTREACH_APPROVED` | §11.6.6 | `outreach_approvals` |
| Send result | `OUTREACH_SENT` | §11.7.2 | `outreach_messages` |

### 11.8.2 `draft_findings` — the join that makes finding queries indexable

`outreach_drafts.facts_used` and `.inferences_used` are JSON arrays (`05-outreach-workflow.md`
§5.3.4) and are kept. They are convenient for rendering and useless for the query "every message
that mentioned finding X", which is one of the four queries this document promises (§11.15). A JSON
scan over every draft is both slow and SQLite-specific, and `_CONTEXT.md` §2 forbids SQLite-only
cleverness in application queries.

```sql
-- radar/migrations/035_draft_findings.sql
CREATE TABLE draft_findings (
    draft_id     TEXT NOT NULL REFERENCES outreach_drafts(id) ON DELETE CASCADE,
    finding_id   TEXT NOT NULL REFERENCES research_findings(id),
    role         TEXT NOT NULL CHECK (role IN ('FACT','INFERENCE','CONTEXT')),
    kind         TEXT NOT NULL CHECK (kind IN ('OBSERVED','INFERRED','UNKNOWN')),
    claim_index  INTEGER,                      -- index into detail.claims[]; NULL if not cited
    hedged       INTEGER CHECK (hedged IS NULL OR hedged IN (0,1)),
    PRIMARY KEY (draft_id, finding_id, role),

    -- Invariant 4, in the database. An UNKNOWN finding may be handed to the model as
    -- context (so it can be told not to speculate about it) but may never be a fact or an
    -- inference behind a claim.
    CHECK (kind <> 'UNKNOWN' OR role = 'CONTEXT'),
    -- An INFERRED finding that reached a claim must be hedged (§23).
    CHECK (kind <> 'INFERRED' OR claim_index IS NULL OR hedged = 1)
);

CREATE INDEX ix_draft_findings_finding ON draft_findings(finding_id, role);
CREATE INDEX ix_draft_findings_draft   ON draft_findings(draft_id);
```

Rows are inserted by `radar/messages.py` in the same transaction as the `outreach_drafts` row and
the `MESSAGE_GENERATED` audit row. Probe P6 in §11.14 checks that the JSON arrays and this table
agree; a disagreement means one of the two writers was changed and the other was not.

### 11.8.3 Capture files

```
data/audit/capture/
  2026/08/out_01JSAMPLE0000000000000021/
    prompt.json.gz        # system prompt, user prompt, bindings, model params   (P3Y)
    completion.json.gz    # raw google-genai GenerateContentResponse             (P3Y)
    policy.json.gz        # rule-by-rule output of radar/policy.py               (P3Y)
    edits.jsonl.gz        # one unified diff per human save                      (P3Y)
  2026/08/msg_01JSAMPLE0000000000000007/
    provider.json.gz      # request headers (redacted) + full provider response  (P7Y)
    webhook-<evt>.json.gz # each accepted provider callback body                 (P1Y)
```

`completion.json.gz` holds the response object exactly as the SDK returned it. On `google-genai`
that means `usage_metadata` (`prompt_token_count`, `candidates_token_count`, `thoughts_token_count`,
`cached_content_token_count`), a `finish_reason` on each candidate, `model_version` — the build the
`gemini-2.5-flash` alias actually resolved to — and `response_id`. Those are the field names to
capture. There is no `usage` / `stop_reason` pair on this provider, and a capture contract naming
fields the SDK does not emit records nothing, which leaves §49 unable to do the one thing it exists
for. `06-message-engine.md` §6.13.1 is the mapping from these SDK fields to the `input_tokens` /
`output_tokens` / `thinking_tokens` that this document and `01-data-model.md` store.

`prompt.json.gz`, SAMPLE structure:

```json
{
  "captured_at": "2026-08-26T11:38:02Z",
  "model_id": "gemini-2.5-flash",
  "prompt_version": "msg-email-v3",
  "template_id": "email_generic_v3",
  "template_path": "radar/prompts/msg_email_v3.md",
  "template_sha256": "d41f0b2c4e6a8092b4d6f8a0c2e4b6d8f0a2c4e6b8d0f2a4c6e8b0d2f4a6c8e0",
  "params": {"max_tokens": 1200, "temperature": 0.4, "top_p": null},
  "bindings": {
    "business_name": "ABC Hospital",
    "city": "Dhule",
    "industry": "HEALTHCARE",
    "category": "HOSPITAL",
    "modules": ["Appointments", "Billing", "Inventory", "Reports"],
    "observed": [
      {"id": "fnd_01JSAMPLEA1",
       "text": "Public site lists four departments and no online appointment booking.",
       "confidence": "HIGH"}
    ],
    "inferred": [
      {"id": "fnd_01JSAMPLEB7",
       "text": "Appointment intake is likely handled by phone.",
       "confidence": "MEDIUM"}
    ],
    "unknown_do_not_mention": ["Whether billing is computerised"],
    "sender": {"name": "Sagar", "role": "...", "company": "..."}
  },
  "system_prompt": "...verbatim...",
  "user_prompt": "...verbatim, after template rendering...",
  "prompt_sha256": "9ab35d7f9012b4d6e8a0c2f4b6d8e0a2c4f6b8d0e2a4c6f8b0d2e4a6c8f0b2d4"
}
```

Storing the rendered prompt rather than only the template plus bindings is a deliberate cost. The
template is git-tracked and the bindings are in the file, so the prompt is reproducible in principle
— but "in principle" fails the moment a helper that formats module lists changes. The rendered
prompt is a few kilobytes gzipped; being able to read exactly what the model was asked is worth it.

Writes are atomic (`.tmp` then `os.replace`), the sha256 is computed while streaming, and the audit
row carries both the relative path and that sha256. A capture file that fails to write is logged as
an error and sets `detail.generation.capture_path = null` with `capture_error` — it does **not**
abort the draft, because a missing capture degrades explainability rather than breaking safety.

### 11.8.4 `MESSAGE_GENERATED` — SAMPLE

```json
{
  "id": "aud_01JSAMPLE0000000000000GEN1",
  "action": "MESSAGE_GENERATED",
  "entity_table": "outreach_drafts",
  "entity_id": "out_01JSAMPLE0000000000000021",
  "business_id": "biz_01JSAMPLE0000000000000042",
  "campaign_id": "cmp_01JSAMPLE0000000000000003",
  "message_id": null,
  "actor_kind": "SYSTEM",
  "actor_label": "worker-2",
  "at": "2026-08-26T11:38:04Z",
  "detail_json": {
    "channel": "EMAIL",
    "sequence_no": 1,
    "research": {
      "research_run_id": "res_01JSAMPLE0000000000000077",
      "research_completed_at": "2026-08-24T06:31:09Z",
      "opportunity_id": "opp_01JSAMPLE0000000000000090",
      "opportunity_score": 86,
      "opportunity_band": "HIGH",
      "research_confidence": "MEDIUM",
      "summary_sha256": "5f7709a1b3d5f7092c4e6a8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f",
      "modules": ["Appointments", "Billing", "Inventory", "Reports"]
    },
    "facts": [
      {"finding_id": "fnd_01JSAMPLEA1", "kind": "OBSERVED", "confidence": "HIGH",
       "confidence_pct": 90, "text_sha256": "aa10...",
       "source_ids": ["src_01JSAMPLE0000000000000112"]},
      {"finding_id": "fnd_01JSAMPLEA2", "kind": "OBSERVED", "confidence": "MEDIUM",
       "confidence_pct": 65, "text_sha256": "aa11...",
       "source_ids": ["src_01JSAMPLE0000000000000112", "src_01JSAMPLE0000000000000118"]}
    ],
    "inferences": [
      {"finding_id": "fnd_01JSAMPLEB7", "kind": "INFERRED", "confidence": "MEDIUM",
       "confidence_pct": 55, "text_sha256": "bb20...",
       "source_ids": ["src_01JSAMPLE0000000000000112"]}
    ],
    "unknowns_withheld": 3,
    "generation": {
      "model_id": "gemini-2.5-flash",
      "prompt_version": "msg-email-v3",
      "template_id": "email_generic_v3",
      "template_sha256": "d41f...",
      "params": {"max_tokens": 1200, "temperature": 0.4},
      "bindings_sha256": "6c02...",
      "prompt_sha256": "9ab3...",
      "capture_path": "capture/2026/08/out_01JSAMPLE0000000000000021/prompt.json.gz",
      "capture_sha256": "31de...",
      "api_request_id": "SAMPLE-resp-9f3c1a44b0",
      "attempt": 1,
      "latency_ms": 4820
    },
    "output": {
      "subject_sha256": "1e9c...",
      "body_sha256": "cc31...",
      "body_chars": 1156,
      "finish_reason": "STOP",
      "input_tokens": 2104,
      "output_tokens": 388,
      "thinking_tokens": 96,
      "completion_capture_path":
        "capture/2026/08/out_01JSAMPLE0000000000000021/completion.json.gz"
    },
    "claims": [
      {"index": 0, "sentence_sha256": "d1a0...", "finding_id": "fnd_01JSAMPLEA1",
       "kind": "OBSERVED", "hedged": false},
      {"index": 1, "sentence_sha256": "d1a1...", "finding_id": "fnd_01JSAMPLEB7",
       "kind": "INFERRED", "hedged": false},
      {"index": 2, "sentence_sha256": "d1a2...", "finding_id": null,
       "kind": "GENERIC", "hedged": false}
    ]
  }
}
```

`generation.api_request_id` is `resp.response_id` from `google-genai`, which `06-message-engine.md`
§6.13.1 binds to `Generation.request_id`. It is the only provider-side handle this stack returns,
it is not guaranteed to be present, and `null` is a permitted value — unlike a paid provider's
request id it cannot be quoted back to a support queue, so it is recorded for correlation and
nothing depends on it. `output.finish_reason` is the candidate's `FinishReason` name, `STOP` on a
clean generation; `MAX_TOKENS`, `SAFETY`, `PROHIBITED_CONTENT` and `BLOCKLIST` never reach an audit
row because `06` §6.13.1 raises before a draft exists. `thinking_tokens` is `thoughts_token_count`,
which is charged output that `candidates_token_count` does not include; an audit record that
omitted it would under-report what the request cost against the day's quota.

`claims[]` is the contract that makes invariant 4 checkable. `radar/messages.py` asks the model for
a structured claim map alongside the body (see `06-message-engine.md`); each entry names
the sentence, the finding it rests on, and whether it hedged. `kind = "GENERIC"` covers sentences
that assert nothing about the business — the greeting, the demo offer, the signature — and the
policy engine requires that every non-`GENERIC` sentence names a finding that exists in
`draft_findings` for this draft.

### 11.8.5 `MESSAGE_POLICY_CHECKED` and `POLICY_BLOCK` — SAMPLE detail

```json
{
  "result": "BLOCK",
  "policy_version": "claim-v2",
  "checked_at": "2026-08-26T11:39:10Z",
  "duration_ms": 31,
  "rules_run": ["R1_no_unknown", "R2_observed_supported", "R3_inferred_hedged",
                "R4_no_invented_numbers", "R5_no_competitor_claims",
                "R6_unsubscribe_present", "R7_length", "R8_no_pricing_promise"],
  "counts": {"claims": 3, "observed": 1, "inferred": 1, "generic": 1},
  "violations": [
    {
      "rule": "R3_inferred_hedged",
      "severity": "BLOCK",
      "claim_index": 1,
      "finding_id": "fnd_01JSAMPLEB7",
      "finding_kind": "INFERRED",
      "sentence_sha256": "d1a1...",
      "sentence_excerpt": "We noticed that you are managing appointments by phone.",
      "explanation": "An INFERRED finding was stated as fact; no hedge token found.",
      "suggested_fix": "We believe appointment intake may be handled by phone."
    }
  ],
  "warnings": [
    {"rule": "R7_length", "severity": "WARN", "detail": "body 1156 chars, target <= 900"}
  ],
  "capture_path": "capture/2026/08/out_01JSAMPLE0000000000000021/policy.json.gz",
  "capture_sha256": "77b2..."
}
```

`sentence_excerpt` is the one place a fragment of message text is stored in `audit_log`, capped at
200 characters. It is business content, not personal data, and without it a policy block six months
later is unreadable. It is nulled by the erasure path along with the rest (§11.12.2) on the small
chance a contact's name appears in it.

### 11.8.6 `MESSAGE_EDITED` — SAMPLE detail

```json
{
  "edit_no": 2,
  "before_sha256": "cc31...",
  "after_sha256":  "a90f...",
  "before_chars": 1156,
  "after_chars": 1184,
  "chars_added": 41,
  "chars_removed": 13,
  "sentences_changed": 2,
  "claims_touched": [1],
  "policy_recheck_required": true,
  "diff_path": "capture/2026/08/out_01JSAMPLE0000000000000021/edits.jsonl.gz",
  "diff_sha256": "8ac9...",
  "editor_session_id": "ses_01JSAMPLE0000000000000004",
  "seconds_since_generated": 214
}
```

`claims_touched` is computed by re-running the sentence splitter over the edited body and diffing
sentence hashes against `claims[]`. If a claim sentence changed, `policy_recheck_required` is true
and `outreach_messages.status` returns to `DRAFT` — a transition the table in
`05-outreach-workflow.md` already permits from `PENDING_APPROVAL`. This is the mechanism that stops
Sagar accidentally editing a hedge back out of an inferred claim after the policy check passed.

### 11.8.7 What can and cannot be reproduced

Being clear about this prevents a false expectation later.

| Question | Reproducible? | How |
|---|---|---|
| What exactly was the model asked? | Yes, byte for byte | `prompt.json.gz` |
| What exactly did it return? | Yes, byte for byte | `completion.json.gz` |
| Which findings was it allowed to use? | Yes | `draft_findings` + `detail.facts/inferences` |
| Which policy version judged it, and what did that version say? | Yes | `policy.json.gz` plus `policy_version` in git |
| Would the same prompt produce the same message today? | **No** | Sampling is non-deterministic and `gemini-2.5-flash` is an alias Google repoints, so the build behind it can change without notice — which is why `completion.json.gz` and the audit row store the resolved `model_version` rather than the alias. `temperature` and `top_p` are recorded so the *configuration* is known, not so the output is replayable. |
| Would the same research produce the same score today? | Only if `weights_version` is unchanged | `OPPORTUNITY_SCORED.detail.weights_version` pins it |
| Can I re-fetch the source that supported this claim? | Maybe — the web moves | `sources.snapshot_path` holds the fetched bytes and `content_sha256` proves they are the bytes that were read |

The system's promise is **traceability**, not **replayability**. Every stored artefact is the real
one from that day; nothing claims that re-running produces it again.

---

## 11.9 "Explain this message"

One screen that walks the whole chain from the URLs that were fetched to the reply that came back.

### 11.9.1 Routes

| Route | Returns |
|---|---|
| `GET /outreach/<draft_id>/explain` | The HTML view (Jinja2, same components as the rest of the app) |
| `GET /api/v1/outreach/<draft_id>/explain` | The JSON payload of §11.9.4 |
| `GET /api/v1/messages/<message_id>/explain` | 302 to the draft's explain endpoint |
| `GET /outreach/<draft_id>/explain?format=html-file` | The same page inlined into one self-contained HTML file (`_CONTEXT.md` §2), for attaching to an email |

Entry points in the UI: the `VIEW MESSAGE` row action (§40), the `Explain` button on every row of
`/business/<id>` outreach history (§32), the message panel of a handoff brief
(`10-human-handoff.md`), and a direct link from every `POLICY_BLOCK` row in the audit view.

Authorisation: session-authenticated only, role `OWNER` or `AUDITOR` (see `12-security-model.md`).
Opening it writes nothing — an explain view that mutated the record it explains would be absurd.

### 11.9.2 The eleven bands

```
+--------------------------------------------------------------------------------+
| ABC Hospital - Dhule - HEALTHCARE/HOSPITAL - MEDIUM        [ opportunity 86 ]   |
| Campaign: Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026   Channel: EMAIL   seq 1   |
| draft out_01JSAMPLE...21  ->  message msg_01JSAMPLE...07  ->  DELIVERED         |
|                                                                                |
| 24 Aug 06:18 fetched . 24 Aug 06:31 researched . 25 Aug 09:02 VERIFIED          |
| 26 Aug 11:36 selected . 11:38 drafted . 11:39 POLICY BLOCK . 11:40 edited       |
| 11:40 policy PASS . 11:41 approved . 11:42 SENT . 11:44 delivered               |
| 28 Aug 09:12 replied -> DEMO_REQUESTED -> handoff hnd_...01                     |
+--------------------------------------------------------------------------------+
| 1  SOURCES (3)                                                       [expand]   |
|    src_...112  abchospital.example/contact  WEBSITE   200  24 Aug 06:18         |
|                sha256 e91f...  [ open live ]  [ open snapshot ]   conf HIGH     |
|    src_...118  Google Business listing      LISTING   200  24 Aug 06:19         |
|    src_...121  IndiaMART profile            DIRECTORY 404  24 Aug 06:20   FAIL  |
+--------------------------------------------------------------------------------+
| 2  FINDINGS (2 OBSERVED, 1 INFERRED, 3 UNKNOWN withheld)                        |
|    OBSERVED  fnd_...A1  HIGH 90    "Site lists four departments and no online   |
|                                    appointment booking."      <- src_...112     |
|    OBSERVED  fnd_...A2  MEDIUM 65  "Listing shows 40-60 staff."  <- src_...118  |
|    INFERRED  fnd_...B7  MEDIUM 55  "Appointment intake is likely by phone."     |
|    UNKNOWN   (withheld from the prompt, listed here for completeness)           |
|              - whether billing is computerised                                  |
+--------------------------------------------------------------------------------+
| 3  OPPORTUNITY  opp_...90   score 86 HIGH   confidence MEDIUM   weights sw-v4   |
|    Problem   Appointment and department coordination is manual                  |
|    Solution  Hospital Operations Platform                                       |
|    Modules   Appointments . Billing . Inventory . Reports                       |
+--------------------------------------------------------------------------------+
| 4  TEMPLATE + PROMPT                                                            |
|    template email_generic_v3  sha256 d41f...   prompt_version msg-email-v3      |
|    model gemini-2.5-flash   max_tokens 1200   temperature 0.4                   |
|    tokens in 2104 / out 388   latency 4.8s      [ view rendered prompt ]        |
|    bindings: business_name, city, industry, modules[4], observed[2],            |
|              inferred[1], unknown_do_not_mention[3]                             |
+--------------------------------------------------------------------------------+
| 5  DRAFT AS GENERATED                            [ view raw completion ]        |
|    Subject: A possible digital operations solution for ABC Hospital             |
|    (1) "...four departments..."              <- fnd_...A1   OBSERVED            |
|    (2) "We noticed that you are managing appointments by phone."                |
|                                              <- fnd_...B7   INFERRED  NOT HEDGED|
|    (3) "I would be happy to show you a short demonstration."      GENERIC       |
+--------------------------------------------------------------------------------+
| 6  POLICY  claim-v2   result BLOCK   11:39:10   8 rules run                     |
|    BLOCK  R3_inferred_hedged  claim 2  fnd_...B7                                |
|           An INFERRED finding was stated as fact; no hedge token found.         |
|           suggested: "We believe appointment intake may be handled by phone."   |
|    WARN   R7_length  body 1156 chars, target <= 900                             |
+--------------------------------------------------------------------------------+
| 7  HUMAN EDITS (2)                                                              |
|    edit 1  11:40:02  claims touched: none   +6 -2 chars                         |
|    edit 2  11:40:31  claims touched: [2]    +41 -13 chars      [ view diff ]    |
|      - We noticed that you are managing appointments by phone.                  |
|      + We believe appointment intake may be handled by phone, in which case...  |
|    -> policy re-check required -> re-checked 11:40:44 -> PASS                   |
+--------------------------------------------------------------------------------+
| 8  APPROVAL  apr_...12                                                          |
|    usr_sagar  26 Aug 11:41:52  session ses_...04  PASSWORD_TOTP  127.0.0.1      |
|    96s between preview and approval                                             |
|    "You are about to contact this business using the selected business contact."|
|    body hash a90f... == sent body hash a90f...              MATCH               |
|    shown at approval: business, contact, channel, message, previous contact(0), |
|                       opt-out(none), approval status                            |
+--------------------------------------------------------------------------------+
| 9  SEND  msg_...07                                                              |
|    11:42:06  gmail  250  accepted  msg id msg_...07@gmail.com                   |
|    to in***@abchospital.example (sha256 4b2e...)  from sa***@gmail.com          |
|    idempotency msg_...07:1   attempt 1   latency 641ms                          |
|    eligibility at SEND: verified yes . suppression none . duplicate none .      |
|                         attempts 0/3 . handoff none . daily cap 7/25            |
+--------------------------------------------------------------------------------+
| 10 DELIVERY                                                                     |
|    no delivery receipt exists on this stack - SMTP 250 is not delivery          |
|    no bounce, no complaint, no unsubscribe                                      |
+--------------------------------------------------------------------------------+
| 11 RESPONSE + HANDOFF                                                           |
|    28 Aug 09:12  inbound  rsp_...05   matched by THREAD_HEADER                  |
|    "Yes, please show us what you can provide."                                  |
|    classified DEMO_REQUESTED  confidence HIGH 88                                |
|      gemini-2.5-flash   prompt classify-v1    [ view rationale ]                |
|    handoff hnd_...01 created 09:12:40   ACKNOWLEDGED 09:31   ack SLA met        |
+--------------------------------------------------------------------------------+
| chain: audit rows seq 41102-41240 verified 27 Aug 20:05   head 9f3c...   OK     |
+--------------------------------------------------------------------------------+
```

Band-by-band contract:

| # | Band | Primary source | Rendered even when empty? |
|---|---|---|---|
| 0 | Header + timeline strip | audit spine query | always |
| 1 | Sources | `sources` via `finding_sources` | yes — "no sources recorded" is itself a finding |
| 2 | Findings | `draft_findings` + `research_findings` | yes |
| 3 | Opportunity | `opportunities`, pinned by id from the audit row | yes |
| 4 | Template + prompt | `MESSAGE_GENERATED.detail.generation` + capture | yes |
| 5 | Draft as generated | `outreach_drafts.body` + `detail.claims[]` | yes |
| 6 | Policy | `MESSAGE_POLICY_CHECKED` / `POLICY_BLOCK` rows | yes |
| 7 | Human edits | `MESSAGE_EDITED` rows + diff sidecar | collapsed to "no edits" when none |
| 8 | Approval | `outreach_approvals` + `OUTREACH_APPROVED` | "not approved" when the draft never got there |
| 9 | Send | `OUTREACH_SENT` / `MANUAL_SEND_RECORDED` / `OUTREACH_SEND_FAILED` | "never sent" |
| 10 | Delivery | `OUTREACH_DELIVERED` / `_BOUNCED` / `_COMPLAINED` | "no delivery events" |
| 11 | Response + handoff | `responses`, `handoffs`, their audit rows | "no response" |
| — | Chain footer | `verify_chain(start_seq, stop_seq)` over the spine's range | always |

The chain footer is not decoration. It is what turns the page from "a rendering of some rows" into
"a rendering of rows that have not been altered since they were written", and it is the reason the
page can be exported as a single self-contained HTML file and handed to somebody.

### 11.9.3 Assembly

The governing rule: **the explain view reads ids out of the audit rows and uses those; it joins live
tables only to resolve names and text.** Re-scoring a business, re-running research, or editing a
finding must not silently change the story of a message that was sent last March.

The spine — one query, ordered by `seq`, that finds every audit row belonging to this message:

```sql
-- radar/audit.py :: SPINE_SQL
WITH m AS (SELECT id FROM outreach_messages  WHERE draft_id = :draft_id),
     a AS (SELECT id FROM outreach_approvals WHERE draft_id = :draft_id),
     r AS (SELECT id FROM responses
            WHERE in_reply_to_message_id IN (SELECT id FROM m)),
     h AS (SELECT id FROM handoffs WHERE response_id IN (SELECT id FROM r))
SELECT al.seq, al.id, al.at, al.action, al.actor_kind, al.actor_user_id, al.actor_label,
       al.entity_table, al.entity_id, al.before_json, al.after_json, al.detail_json,
       al.session_id, al.client_ip, al.job_run_id, al.row_hash
  FROM audit_log al
 WHERE (al.entity_table = 'outreach_drafts'    AND al.entity_id = :draft_id)
    OR (al.message_id IS NOT NULL              AND al.message_id IN (SELECT id FROM m))
    OR (al.entity_table = 'outreach_approvals' AND al.entity_id IN (SELECT id FROM a))
    OR (al.entity_table = 'responses'          AND al.entity_id IN (SELECT id FROM r))
    OR (al.entity_table = 'handoffs'           AND al.entity_id IN (SELECT id FROM h))
 ORDER BY al.seq;
```

Then the pinned-id lookups. Each takes its id from the spine, not from the current row of another
table:

```sql
-- Band 1: sources behind the findings this draft used
SELECT s.id, s.name, s.url, s.source_type, s.checked_at, s.http_status,
       s.content_sha256, s.snapshot_path, s.confidence, s.information_obtained
  FROM sources s
 WHERE s.id IN (SELECT fs.source_id
                  FROM draft_findings df
                  JOIN finding_sources fs ON fs.finding_id = df.finding_id
                 WHERE df.draft_id = :draft_id)
 ORDER BY s.checked_at, s.id;

-- Band 2: the findings, in OBSERVED -> INFERRED -> CONTEXT order
SELECT df.role, df.kind, df.claim_index, df.hedged,
       f.id AS finding_id, f.text, f.confidence, f.confidence_pct, f.created_at,
       (SELECT group_concat(fs.source_id, ',')
          FROM finding_sources fs WHERE fs.finding_id = f.id) AS source_ids
  FROM draft_findings df
  JOIN research_findings f ON f.id = df.finding_id
 WHERE df.draft_id = :draft_id
 ORDER BY CASE df.kind WHEN 'OBSERVED' THEN 0 WHEN 'INFERRED' THEN 1 ELSE 2 END,
          df.claim_index NULLS LAST, f.id;

-- Band 2 tail: the UNKNOWN findings that existed and were deliberately withheld
SELECT f.id, f.text, f.confidence
  FROM research_findings f
 WHERE f.research_run_id = :research_run_id       -- pinned from MESSAGE_GENERATED
   AND f.kind = 'UNKNOWN'
 ORDER BY f.id;

-- Band 3: the opportunity as it was, pinned by id
SELECT o.id, o.score, o.band, o.confidence, o.confidence_pct,
       o.potential_problem, o.potential_solution, o.expected_benefit,
       o.weights_version, o.created_at,
       (SELECT group_concat(om.module, ' . ')
          FROM opportunity_modules om
         WHERE om.opportunity_id = o.id) AS modules
  FROM opportunities o
 WHERE o.id = :opportunity_id;

-- Band 5: the bodies. final_body is COALESCE(body_edited, body) and nothing else computes it.
SELECT d.subject, d.body, d.body_edited, COALESCE(d.body_edited, d.body) AS final_body,
       d.edit_count, d.model_id, d.prompt_version, d.policy_result, d.policy_version,
       d.ai_confidence, d.ai_confidence_pct, d.created_at, d.superseded_by
  FROM outreach_drafts d
 WHERE d.id = :draft_id;

-- Band 8: the approval, and whether its hash still matches what was sent
SELECT ap.id, ap.approved_by, ap.approved_at, ap.session_id, ap.session_auth_method,
       ap.client_ip, ap.user_agent, ap.approved_subject, ap.approved_body_hash,
       ap.confirmation_text, ap.displayed, ap.eligibility_snapshot,
       ap.revoked_at, ap.revoke_reason,
       m.body_hash AS sent_body_hash,
       (ap.approved_body_hash = m.body_hash) AS hash_matches
  FROM outreach_approvals ap
  JOIN outreach_messages m ON m.id = ap.message_id
 WHERE ap.draft_id = :draft_id
 ORDER BY ap.approved_at;

-- Bands 10 and 11: delivery events and the reply
SELECT e.event, e.at, e.actor_type, e.actor_id, e.detail, e.provider_event_id
  FROM outreach_events e
 WHERE e.message_id = :message_id
 ORDER BY e.at, e.id;

SELECT r.id, r.received_at, r.channel, r.from_address_display, r.body_excerpt,
       r.classification, r.confidence, r.confidence_pct,
       r.classifier_model_id, r.classifier_prompt_version,
       r.reclassified_from, r.reclassified_by,
       h.id AS handoff_id, h.state AS handoff_state, h.created_at AS handoff_created_at
  FROM responses r
  LEFT JOIN handoffs h ON h.response_id = r.id
 WHERE r.in_reply_to_message_id = :message_id
 ORDER BY r.received_at;
```

Portability notes for the eventual Postgres move: `group_concat(x, sep)` becomes
`string_agg(x, sep)`; `NULLS LAST` is already Postgres syntax and is supported by SQLite 3.30+;
everything else is plain SQL. There is no `json_each` anywhere in this assembly, which is the whole
reason `draft_findings` exists.

### 11.9.4 The JSON payload

`GET /api/v1/outreach/<draft_id>/explain` — key skeleton, values elided:

```json
{
  "draft_id": "out_...",
  "message_id": "msg_...",
  "generated_at": "2026-08-27T21:14:02Z",
  "header": {
    "business": {"id": "", "name": "", "city": "", "industry": "", "category": "",
                 "size_band": "", "status": ""},
    "campaign": {"id": "", "name": ""},
    "channel": "EMAIL",
    "sequence_no": 1,
    "current_status": "DELIVERED",
    "timeline": [{"at": "", "label": "", "action": "", "audit_id": "", "seq": 0}]
  },
  "sources": [{"id": "", "name": "", "url": "", "source_type": "", "checked_at": "",
               "http_status": 0, "content_sha256": "", "snapshot_url": "",
               "confidence": "", "information_obtained": "", "live_url_status": ""}],
  "findings": {"observed": [], "inferred": [], "context": [],
               "unknown_withheld": [{"id": "", "text": ""}]},
  "opportunity": {"id": "", "score": 0, "band": "", "confidence": "",
                  "potential_problem": "", "potential_solution": "",
                  "expected_benefit": "", "modules": [], "weights_version": ""},
  "generation": {"model_id": "", "prompt_version": "", "template_id": "",
                 "template_sha256": "", "params": {}, "prompt_sha256": "",
                 "prompt_url": "", "completion_url": "", "input_tokens": 0,
                 "output_tokens": 0, "thinking_tokens": 0, "finish_reason": "",
                 "latency_ms": 0, "capture_status": "OK"},
  "draft": {"subject": "", "body": "",
            "claims": [{"index": 0, "text": "", "finding_id": "", "kind": "",
                        "hedged": false, "hedge_token": null, "supported": true}]},
  "policy": {"checks": [{"at": "", "result": "", "policy_version": "", "rules_run": [],
                         "violations": [], "warnings": [], "capture_url": ""}],
             "final_result": "PASS"},
  "edits": [{"edit_no": 1, "at": "", "by": "", "chars_added": 0, "chars_removed": 0,
             "claims_touched": [], "diff_unified": "", "policy_recheck_required": false}],
  "approval": {"id": "", "approved_by": "", "approved_at": "", "session_id": "",
               "session_auth_method": "", "client_ip": "", "confirmation_text": "",
               "displayed": {}, "hash_matches": true,
               "preview_to_approve_seconds": 0, "revoked_at": null},
  "send": {"status": "", "provider": "", "provider_message_id": "", "status_code": 0,
           "sent_at": "", "to_masked": "", "to_sha256": "", "from_domain": "",
           "idempotency_key": "", "attempt_count": 1, "eligibility": {}},
  "delivery": {"events": [{"event": "", "at": "", "provider_event_id": "", "detail": {}}],
               "delivered_at": "", "bounced": false, "complained": false,
               "unsubscribed": false},
  "response": {"id": "", "received_at": "", "channel": "", "from_masked": "", "body": "",
               "classification": "", "confidence": "", "confidence_pct": 0,
               "classifier_model_id": "", "classifier_prompt_version": "",
               "rationale_url": "",
               "reclassified_from": null, "handoff": {"id": "", "state": ""}},
  "integrity": {"first_seq": 0, "last_seq": 0, "rows": 0, "verified": true,
                "verified_at": "", "head_hash": "",
                "last_anchor": {"day": "", "to_seq": 0, "head_hash": ""}},
  "redactions": [{"field": "", "reason": "", "erasure_audit_id": "", "erased_at": ""}],
  "gaps": [{"band": "", "reason": ""}]
}
```

`redactions[]` and `gaps[]` are first-class, not error states. A page that quietly omits a band it
could not load is worse than useless in an audit.

### 11.9.5 Python surface

```python
# radar/audit.py

@dataclass(frozen=True)
class Explanation:
    draft_id: str
    message_id: str | None
    header: Header
    sources: list[SourceRef]
    findings: FindingSets
    opportunity: OpportunityRef | None
    generation: GenerationRef | None
    draft: DraftBodies
    policy: PolicyHistory
    edits: list[EditRef]
    approval: ApprovalRef | None
    send: SendRef | None
    delivery: DeliveryRef
    response: ResponseRef | None
    integrity: IntegrityRef
    redactions: list[Redaction]
    gaps: list[Gap]

    def to_dict(self) -> dict[str, Any]: ...


def explain_message(conn: sqlite3.Connection, draft_id: str, *,
                    verify: bool = True,
                    load_captures: bool = True) -> Explanation:
    """Reconstruct the whole causal chain behind one outreach message.

    Sources -> findings -> opportunity -> template + prompt -> draft -> policy -> edits ->
    approval -> send -> delivery -> response.

    Reads ids out of the audit rows and uses those, so a business that was re-scored last
    week still explains the message that went out in March with March's numbers. Never
    writes. verify=False skips the chain check for list views that render a strip of this;
    the full page always verifies.
    """
```

### 11.9.6 Degradation rules

The view has to work on the worst day, which is the day something is missing.

| Missing thing | Rendered as | Recorded in |
|---|---|---|
| Capture file purged by retention | `evidence expired (P3Y) - sha256 9ab3...` | `gaps[]` `RETENTION_P3Y` |
| Capture file absent, no purge recorded | `capture missing - expected sha256 9ab3...`, red | `gaps[]` `CAPTURE_MISSING` |
| Capture present but sha256 mismatch | `capture ALTERED - stored 9ab3..., actual 41cd...`, red; contents still shown, clearly labelled | `gaps[]` `CAPTURE_HASH_MISMATCH` |
| Source URL now 404s | Live link greyed with `404 on last check`; snapshot link still live | `gaps[]` `LIVE_URL_GONE` |
| Source snapshot missing | `snapshot unavailable` | `gaps[]` `SNAPSHOT_MISSING` |
| Draft predates `claims[]` | Body shown unannotated with `claim map not recorded (drafted before claim-v2)` | `gaps[]` `PRE_CLAIM_MAP` |
| Finding row missing (should be impossible) | `finding fnd_... referenced by draft but not found`, red | `gaps[]` `DANGLING_FINDING` |
| Personal data erased | `[erased 2027-02-01 - aud_01J...ER1]`, hash still shown | `redactions[]` |
| Chain verification fails over this range | Footer red: `CHAIN BROKEN at seq 41188 - this page cannot be relied on` | `integrity.verified = false` |

A metric with no data renders `—`, never `0` (`_CONTEXT.md` §3 invariant 5). That rule is not only
for reports.

### 11.9.7 Cost

The spine is one indexed scan (`ix_audit_message_at`, `ix_audit_entity`), typically 15–40 rows. The
pinned lookups are all primary-key or single-index reads. `verify=True` recomputes hashes for the
spine's `seq` range only — tens of rows, not the whole table — starting from the row at
`first_seq - 1` whose hash is already stored. Target: under 150 ms server-side on the laptop, with
capture files read lazily behind the `[ view ... ]` links rather than inlined.

No caching. The page is opened rarely, must always reflect the current chain state, and a cached
audit view that is subtly stale is the one kind of bug that would destroy the point of it.

---

## 11.10 Where the audit trail surfaces in the UI

| Surface | Route | Shows | Filter |
|---|---|---|---|
| Business history | `/business/<id>` — History tab | `timeline(business_id)` — every `user_visible = 1` row for this business, newest first, with an `Explain` link on message rows | `audit_actions.user_visible = 1` |
| Campaign activity | `/campaigns/<id>` — Activity tab | `user_visible = 1` rows for this campaign, grouped by day | same |
| Explain this message | `/outreach/<draft_id>/explain` | §11.9 | — |
| Raw audit log | `/settings` — Audit tab | Every row, paged by `seq` descending, filterable by action, domain, severity, actor, date range, entity | none |
| Chain status | `/settings` — Audit tab header | `head_seq`, `head_hash`, last verification, last export, last anchor, last restore test, plus a `Verify now` button | — |
| Daily digest | Telegram, once a day | Every `CRITICAL` row from the last 24 h, plus any failed probe | `severity = 'CRITICAL'` |

`user_visible = 0` rows (`SOURCE_FETCHED`, `LOGIN_FAILED`, `MESSAGE_PREVIEWED`, …) exist so the
raw log is complete and the business timeline is readable. The distinction is presentational only:
nothing is hidden from `/settings`, and the API returns everything.

---

## 11.11 Report archive (§42)

Spec §42: *"Store every campaign; reopen previous campaigns."* Read alongside §8 ("These numbers
must come from actual database results. Never fabricate them") that means more than keeping files:
an archived report has to be provably the report that was generated on that date, from those
numbers.

### 11.11.1 `report_exports`

```sql
-- radar/migrations/048_report_exports.sql
CREATE TABLE report_exports (
    id                 TEXT PRIMARY KEY,                 -- rex_...
    campaign_id        TEXT REFERENCES campaigns(id),
    fmt                TEXT NOT NULL
                         CHECK (fmt IN ('HTML','CSV','XLSX','PDF','JSON')),
    scope              TEXT NOT NULL
                         CHECK (scope IN ('CAMPAIGN','DAILY','CITY','INDUSTRY',
                                          'TOP_OPPORTUNITIES','SUBJECT_ACCESS','AUDIT')),
    scope_key          TEXT,                             -- 'DHULE' | 'HEALTHCARE' | '2026-08-26'
    title              TEXT NOT NULL,
    filename           TEXT NOT NULL,
    rel_path           TEXT NOT NULL,                    -- relative to config reports.dir

    bytes              INTEGER NOT NULL CHECK (bytes >= 0),
    content_sha256     TEXT NOT NULL CHECK (length(content_sha256) = 64),
    data_sha256        TEXT NOT NULL CHECK (length(data_sha256) = 64),
    data_rel_path      TEXT,                             -- canonical aggregate payload, .json.gz
    row_count          INTEGER NOT NULL CHECK (row_count >= 0),

    filters_json       TEXT NOT NULL DEFAULT '{}',       -- the §39 filters actually applied
    columns_json       TEXT,                             -- the §41 columns actually included
    contains_pii       INTEGER NOT NULL DEFAULT 0 CHECK (contains_pii IN (0,1)),

    template_version   TEXT NOT NULL,                    -- 'report-v2'
    generator_version  TEXT NOT NULL,                    -- 'radar 0.4.2 (git 8f21a0c)'
    db_schema_version  INTEGER NOT NULL,
    query_fingerprint  TEXT NOT NULL,                    -- sha256 of the ordered aggregate SQL

    generated_at       TEXT NOT NULL
                         DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    generated_by       TEXT REFERENCES users(id),
    job_run_id         TEXT REFERENCES job_runs(id),

    retention_class    TEXT NOT NULL
                         CHECK (retention_class IN ('PERMANENT','P2Y','P180D')),
    expires_at         TEXT,
    deleted_at         TEXT,
    deleted_reason     TEXT
                         CHECK (deleted_reason IS NULL OR
                                deleted_reason IN ('RETENTION','ERASURE','MANUAL','SUPERSEDED')),
    superseded_by      TEXT REFERENCES report_exports(id),

    CHECK (json_valid(filters_json)),
    CHECK (deleted_at IS NULL OR deleted_reason IS NOT NULL),
    CHECK (contains_pii = 0 OR retention_class <> 'PERMANENT')
);

CREATE UNIQUE INDEX ux_report_exports_path    ON report_exports(rel_path);
CREATE INDEX ix_report_exports_campaign       ON report_exports(campaign_id, generated_at);
CREATE INDEX ix_report_exports_scope          ON report_exports(scope, scope_key, generated_at);
CREATE INDEX ix_report_exports_data_sha       ON report_exports(data_sha256);
CREATE INDEX ix_report_exports_live           ON report_exports(generated_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_report_exports_expiry         ON report_exports(expires_at)   WHERE deleted_at IS NULL;

-- The identity of an archived report cannot be edited into something else. Retention and
-- deletion columns stay writable; everything that says "this is which file, generated when,
-- containing what" does not.
CREATE TRIGGER trg_report_exports_identity_immutable
BEFORE UPDATE ON report_exports
WHEN NEW.content_sha256    <> OLD.content_sha256
  OR NEW.data_sha256       <> OLD.data_sha256
  OR NEW.rel_path          <> OLD.rel_path
  OR NEW.generated_at      <> OLD.generated_at
  OR NEW.row_count         <> OLD.row_count
  OR NEW.query_fingerprint <> OLD.query_fingerprint
BEGIN
    SELECT RAISE(ABORT, 'report_exports content identity is immutable');
END;

-- Deleting the row would lose the proof that the report existed. Files get deleted;
-- rows get tombstoned.
CREATE TRIGGER trg_report_exports_no_delete
BEFORE DELETE ON report_exports
BEGIN
    SELECT RAISE(ABORT, 'report_exports rows are tombstoned (deleted_at), never deleted');
END;
```

The `CHECK (contains_pii = 0 OR retention_class <> 'PERMANENT')` line is the DPDP purpose-limitation
rule expressed as a constraint: a file with contact columns in it may not be kept forever.

The format column is `fmt`, not `kind`, per `01-data-model.md` §1.2.1 Amendment 1: `kind` meant the
file format here and the report's subject in `03-html-report.md`, and one word cannot mean both in
one archive. `01` §1.2.1 also carries Amendment 2 (a `status` / `error` / `generated_by_job_id`
build lifecycle, with `bytes`, both hashes and `row_count` nullable until `status = 'READY'`) and
Amendment 3 (`report_date`, `cities`) into this table; both are additions to the DDL above and
`048` creates the amended form. `13-api-endpoints.md` §13.16 publishes the same names.

### 11.11.2 Two hashes, because they answer different questions

| Hash | Over | Answers |
|---|---|---|
| `content_sha256` | the exact bytes of the delivered file | "Is this the file I generated on 26 Aug?" |
| `data_sha256` | `canonical_json(payload)` with `generated_at` and `generator_version` removed | "Are these the numbers the database produced on 26 Aug?" |

Both are needed because the HTML file embeds its own generation timestamp, so regenerating the same
report on the same data gives a different `content_sha256` and an identical `data_sha256`. That is
the desirable behaviour, and it gives three useful properties:

- Regenerating a campaign report and getting a **different** `data_sha256` means the underlying rows
  changed since the archived run. The new row gets `superseded_by` pointing back, and the diff is
  investigable. Silent number drift is the thing §8 is afraid of.
- A CSV and the HTML generated from the same payload share a `data_sha256`, so "this spreadsheet and
  that report agree" is one comparison.
- `ix_report_exports_data_sha` makes "which reports contained these exact numbers" a lookup.

The payload is stored: `data_rel_path` points at a gzipped canonical JSON of everything the template
was given — KPI cards (§7), city summary (§8), the business table rows (§9), city and industry
comparisons (§37, §38), top opportunities (§44). It is 1–3× the size of the HTML gzipped, and it is
what makes the archive re-renderable with a newer template.

### 11.11.3 Storage layout

```
data/reports/
  2026/
    08/
      cmp_01JSAMPLE0000000000000003/
        business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.html
        business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.data.json.gz
        business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.csv
        business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.xlsx
        city_dhule_2026-08-26.html
      daily/
        2026-08-26/
          daily_business_opportunity_report_2026-08-26.html
          daily_business_opportunity_report_2026-08-26.data.json.gz
  subject_access/
    2027/02/
      sar_4b2e9a17_2027-02-01.json.gz
```

- Year/month first so a filesystem-level archive or a `find -mtime` sweep is trivial.
- Campaign id, not campaign name, in the path — names contain spaces and are editable.
- Filenames follow §5 exactly: `business_research_<cities>_<date>.html`.
- `rel_path` in the DB is relative to `reports.dir` from `config.yaml`, so moving the data directory
  does not invalidate every row.

### 11.11.4 Generation, atomically

```python
# radar/report.py

def write_export(conn: sqlite3.Connection, *, payload: ReportPayload, fmt: str,
                 scope: str, scope_key: str | None, dest: Path,
                 actor: Actor) -> str:
    """Render a report to disk and register it as an archived, hash-identified artefact.

    Writes .tmp then os.replace, per the house durability rule. The sha256 is computed
    while streaming the bytes out, then re-verified by reading the final file back - a
    hash of what we meant to write is not evidence about what is on disk.
    """
```

Order of operations, and the failure each step prevents:

| Step | Action | Prevents |
|---|---|---|
| 1 | Build `payload` from SQL aggregates only; assert no `None` was silently coerced to `0` | §8 fabricated numbers |
| 2 | `data_sha256 = sha256(canonical_json(payload_without_timestamps))` | Not being able to compare two runs |
| 3 | Write `<name>.data.json.gz.tmp` → `os.replace` | A half-written payload |
| 4 | Render the template, streaming to `<name>.html.tmp`, hashing as it goes | Two passes disagreeing |
| 5 | `os.replace` to the final name | A reader seeing a partial file |
| 6 | Re-read the final file, recompute sha256, compare | Filesystem lying about what landed |
| 7 | In one transaction: `audit.write('REPORT_GENERATED')` then `INSERT INTO report_exports` | A file on disk with no row, or a row with no proof |
| 8 | If `contains_pii`, additionally write `DATA_EXPORTED` | An export with contacts leaving without a `CRITICAL` record |

Step 6 is not paranoia theatre; it costs a few milliseconds and it is the difference between
"we hashed a string" and "we hashed the archived artefact".

### 11.11.5 Reopening a previous campaign

| Route | Behaviour |
|---|---|
| `GET /campaigns/<id>` — Archive tab | Lists every live `report_exports` row for the campaign: fmt, scope, generated_at, row_count, bytes, first 8 chars of `content_sha256`, and its retention/expiry |
| `GET /api/v1/report_exports?campaign_id=<id>&fmt=&scope=` | JSON list, `deleted_at IS NULL` unless `include_deleted=1` |
| `GET /api/v1/report_exports/<id>` | Streams the file with `Content-Disposition: attachment`, `X-Content-SHA256`, and `X-Data-SHA256` headers; writes `REPORT_DOWNLOADED` (best effort) |
| `GET /api/v1/report_exports/<id>/payload` | Streams `data_rel_path`, for re-rendering with a newer template |
| `GET /api/v1/report_exports/<id>/verify` | Recomputes both hashes from disk and returns `{"content_ok": bool, "data_ok": bool, "bytes_on_disk": n}` |

A tombstoned row renders in the archive list as
`deleted 2027-02-01 (ERASURE) — content_sha256 c3d1…`. The row is the proof the report existed; the
bytes are gone on purpose.

### 11.11.6 Verifying the archive

```
python main.py audit verify-reports [--campaign cmp_...] [--since 2026-01-01] [--repair-index]
```

Walks live `report_exports` rows and classifies each as:

| Result | Meaning | Action |
|---|---|---|
| `OK` | file present, `content_sha256` matches | none |
| `MISSING` | row live, file absent | `CRITICAL` alert; likely an out-of-band delete or a bad restore |
| `MODIFIED` | file present, hash differs | `CRITICAL` alert; the archived report is no longer the archived report |
| `ORPHAN_FILE` | file on disk with no live row | listed; `--repair-index` does **not** adopt it, it only reports — adopting an unknown file into the archive would defeat the point |
| `TOMBSTONED_PRESENT` | row deleted but file still there | delete the file, write `REPORT_FILE_DELETED` |

Runs nightly as job `verify_reports` over the last 90 days, monthly over everything, and writes one
`AUDIT_CHAIN_VERIFIED`-style summary row (`action = 'REPORT_ARCHIVE_VERIFIED'`, catalogued under
`SYSTEM`).

### 11.11.7 Retention and size

| `fmt` / `scope` | `contains_pii` | Class | Rationale |
|---|---|---|---|
| `HTML` campaign report | 0 | `PERMANENT` | The §9/§10 table shows `Contact Available: Business Email Available`, not the address. No personal data, small file, permanent. |
| `JSON` payload | 0 | `PERMANENT` | Same content, and it is what makes re-rendering possible |
| `HTML` daily report (§43) | 0 | `PERMANENT` | Small |
| `PDF` | 0 | `P2Y` | Regenerable from the payload; large |
| `CSV` / `XLSX` without contact columns | 0 | `P2Y` | Regenerable |
| `CSV` / `XLSX` **with** contact columns | 1 | `P180D` | Purpose limitation. A spreadsheet of business emails on a laptop is the highest-risk artefact the system produces. |
| `SUBJECT_ACCESS` export | 1 | `P180D` | Delivered to the requester, then purged |
| `AUDIT` segment export | 0 | `PERMANENT` | §11.5 |

Sizing, estimated (SAMPLE, for capacity planning only): a 300-business campaign report is roughly
400–700 KB of HTML with the payload adding ~150 KB gzipped. Two campaigns a week plus a daily report
is well under 1 GB over five years. The archive is not the thing that fills the disk; the source
snapshots under `data/audit/capture/` are, which is why those have a `P3Y` class and reports do not.

The nightly `retention_purge` job deletes files whose `expires_at` has passed, sets `deleted_at` and
`deleted_reason = 'RETENTION'`, and writes one `REPORT_FILE_DELETED` per file plus one
`RETENTION_PURGE` summary. `expires_at` is computed at insert time from `retention_class` so a later
policy change does not retroactively delete an artefact somebody is relying on.

---

## 11.12 Retention and deletion

### 11.12.1 The position

DPDP 2023 applies the moment a named individual's contact details are stored. `business_radar`
stores three kinds of thing, and they are treated differently:

| Category | Examples | Treatment |
|---|---|---|
| Business identity | `businesses.name`, city, industry, website, opportunity score, findings about operations | Not personal data. Retained. A hospital's name and the fact that its site has no online booking are facts about an organisation. |
| Personal data | `business_contacts.name` / `.email` / `.phone`, an individual's reply text, an individual's address in a sent message | Erasable. Purpose: B2B software prospecting. Retained only while that purpose is live. |
| Evidence about processing | audit rows, hashes, suppression records, approval hashes | Retained. Justified by the need to demonstrate compliance and to prevent recurrence of contact. |

Baseline retention, independent of any request: a `business_contacts` row with no outreach in
**24 months** and no open handoff is nulled by the `retention_purge` job and the business drops to
`AI_RESEARCHED` with `contact_ready = 0`. Sitting on contact details for a prospect nobody ever
contacted is the definition of failing purpose limitation.

### 11.12.2 The erasure map

What `erase_subject()` does, table by table. Everything happens in one transaction plus a file pass.

| Table | Erased | Kept | Why |
|---|---|---|---|
| `business_contacts` | `name`, `email`, `phone`, `whatsapp_id`, `role_title`, `notes`; `erased_at` set | `id`, `business_id`, `kind`, `email_sha256`, `phone_sha256`, `domain`, `source`, `collected_at`, `collected_from` | The hashes keep dedupe and suppression matching working; the domain keeps the business record coherent |
| `businesses` | nothing | everything | Organisation data, not personal data. A request from an individual does not erase the hospital. |
| `outreach_drafts` | `subject`, `body`, `body_edited` → `'[ERASED <date> <aud_id>]'` | `facts_used`, `inferences_used`, `model_id`, `prompt_version`, `policy_result`, `policy_detail` (with `sentence_excerpt` nulled), `edit_count` | The body can contain the contact's name; the finding ids cannot |
| `outreach_messages` | `to_address_norm`, `to_address_display`, `subject_final`, `body_final` | `body_hash`, `recipient_domain`, `status`, timestamps, `provider_message_id`, `idempotency_key` | `body_hash` still proves the approval covered this exact message |
| `outreach_approvals` | `approved_subject`, `approved_body`, `approved_to_address` | `approved_body_hash`, `confirmation_text`, `displayed` (address fields masked), `session_id`, `approved_by`, `approved_at` | Proof that a specific body was approved by a specific human survives without retaining the body |
| `outreach_events` | `detail` keys matching an address pattern | everything else | — |
| `responses` | `from_address_display`, `body_raw`, `body_excerpt` | `body_sha256`, `classification`, `confidence`, `model_id`, `received_at` | The funnel metrics of §54 survive erasure |
| `handoffs` | contact snapshot fields, `response_excerpt` | state, timestamps, SLA outcomes | — |
| `selections`, `verifications`, `opportunities`, `research_findings`, `sources` | nothing | everything | These are about the business |
| `suppressions` | `value_norm` → the literal `#erased:` followed by the first 32 chars of `value_hmac` | `value_hmac`, `scope`, `reason`, `source`, `created_at` | §11.12.3 |
| `audit_log` | **nothing** | everything | By construction it never held raw personal data (D6). This is the whole reason D6 exists. |
| `report_exports` | files with `contains_pii = 1` naming the subject are deleted; rows tombstoned `deleted_reason='ERASURE'` | row, `content_sha256`, `data_sha256` | §11.11.5 |
| Capture files | `prompt.json.gz`, `completion.json.gz`, `edits.jsonl.gz` for affected drafts; response captures | the audit row's `capture_path` + `capture_sha256` | Prompts embed the contact name in `bindings` |
| Backups | not modified in place | — | §11.12.6 — this is why the erasure journal exists |

`erased_at` on `business_contacts` and a `redactions[]` entry in every explain view keep the erasure
itself visible. A field that silently becomes empty looks like a bug; a field that says
`[erased 2027-02-01 — aud_01J…ER1]` is an answer.

### 11.12.3 The suppression tension, and how it resolves

The conflict is real and worth stating in full:

> An erasure request says "stop processing my data and delete what you hold." The suppression row is
> the only mechanism that guarantees the system never contacts this person again. Deleting it to
> honour the request is the single action most likely to cause exactly the harm the request was made
> to prevent — the next campaign rediscovers the business, the address is no longer on any block
> list, and another message goes out.

Resolution: **the suppression row survives erasure, holding a keyed hash of the identifier instead
of the identifier.**

```sql
-- radar/migrations/036_suppression_hmac.sql
-- Additive change to the table owned by 05-outreach-workflow.md.
ALTER TABLE suppressions ADD COLUMN value_hmac TEXT;   -- 64 hex, HMAC-SHA256(pepper, value_norm)
ALTER TABLE suppressions ADD COLUMN erased_at  TEXT;

-- Backfilled by radar/policy.py at migration time; the pepper lives only in config/.env.
CREATE UNIQUE INDEX ux_suppressions_scope_hmac
    ON suppressions(scope, value_hmac) WHERE value_hmac IS NOT NULL;
CREATE INDEX ix_suppressions_hmac_live
    ON suppressions(scope, value_hmac) WHERE released_at IS NULL;

-- After the backfill, the column is mandatory. SQLite cannot ALTER a column to NOT NULL,
-- so the requirement is a trigger.
CREATE TRIGGER trg_suppressions_hmac_required
BEFORE INSERT ON suppressions
WHEN NEW.value_hmac IS NULL OR length(NEW.value_hmac) <> 64
BEGIN
    SELECT RAISE(ABORT, 'suppressions.value_hmac is required');
END;
```

```python
# radar/policy.py

def suppression_hmac(value_norm: str) -> str:
    """Keyed hash of a normalised contact point, for a suppression list that survives erasure.

    Keyed, not plain: a plain SHA-256 of an email address is reversible by anyone with a
    wordlist of business domains, so an "erased" suppression table would still be a readable
    list of who asked not to be contacted.
    """
    pepper = os.environ["SUPPRESSION_HMAC_PEPPER"].encode()
    return hmac.new(pepper, value_norm.encode("utf-8"), hashlib.sha256).hexdigest()


def is_suppressed(conn, *, scope: str, value: str) -> Suppression | None:
    """The only lookup. Works identically before and after the subject's data is erased."""
    return conn.execute(
        "SELECT * FROM suppressions "
        " WHERE scope = ? AND value_hmac = ? AND released_at IS NULL",
        (scope, suppression_hmac(normalise(scope, value))),
    ).fetchone()
```

Erasure then does:

```sql
UPDATE suppressions
   SET value_norm = '#erased:' || substr(value_hmac, 1, 32),
       erased_at  = strftime('%Y-%m-%dT%H:%M:%SZ','now')
 WHERE scope = :scope AND value_hmac = :hmac AND erased_at IS NULL;
```

`value_norm` stays `NOT NULL` and stays unique within its scope (the hmac prefix is unique per
value), so `ux_suppressions_scope_value` from `05-outreach-workflow.md` keeps working. A
`SUPPRESSION_PSEUDONYMISED` audit row records it.

What this actually is, said plainly: **pseudonymisation, not erasure.** The system can still answer
"is this address suppressed?" but can no longer produce a list of suppressed addresses from the
database. This is the same trade every ESP makes for its own suppression list, and it is disclosed
in the response sent to the requester rather than glossed over:

> Your contact details have been deleted. We retain a one-way keyed hash of the address so that our
> systems can recognise and block it if it is encountered again. We cannot recover the address from
> that hash, and it is not used for any other purpose.

Two hard constraints follow:

1. **`SUPPRESSION_HMAC_PEPPER` is never rotated.** Rotation would require re-hashing from the
   plaintext, which has been erased. Losing it makes every suppression unmatchable, which is a
   catastrophic silent failure — the block list would appear intact and match nothing. The pepper is
   32 random bytes, generated once, held in `config/.env`, backed up encrypted and separately from
   the database (§11.13.1), and its presence and fingerprint are asserted at startup:
   `SUPPRESSION_HMAC_PEPPER` fingerprint mismatch against the value recorded in `contact_policy`
   refuses to start the app.
2. **A suppression is never released by erasure.** `released_at` stays `NULL`;
   `trg_suppressions_release_needs_audit` still stands.

### 11.12.4 The erasure receipt

`ERASURE_EXECUTED.detail_json`, SAMPLE:

```json
{
  "request_audit_id": "aud_01JSAMPLE00000000000ERQ1",
  "subject_kind": "EMAIL",
  "subject_sha256": "4b2e9a17c8d0f35e6a19b74c2d8e0f31a5c7e9b1d3f5a7c9e1b3d5f7a9c1e3b5",
  "subject_hmac": "77c1e4a9b2d5f80e3a6c9b1d4f7a0c3e6b9d2f5a8c1e4b7d0f3a6c9e2b5d8f1a",
  "received_via": "EMAIL_REPLY",
  "received_at": "2027-01-30T10:14:00Z",
  "executed_at": "2027-02-01T04:00:12Z",
  "businesses_touched": ["biz_01JSAMPLE0000000000000042"],
  "rows": {
    "business_contacts": 1,
    "outreach_drafts": 2,
    "outreach_messages": 2,
    "outreach_approvals": 2,
    "outreach_events": 11,
    "responses": 1,
    "handoffs": 1,
    "suppressions_pseudonymised": 1
  },
  "files": {
    "capture_deleted": 6,
    "capture_bytes_freed": 184320,
    "report_exports_tombstoned": ["rex_01JSAMPLE0000000000000009"]
  },
  "retained": {
    "suppression_id": "sup_01JSAMPLE0000000000000006",
    "reason": "Preventing further contact requires a keyed hash of the address.",
    "audit_rows": "unchanged - audit_log holds no raw personal data",
    "hashes": ["body_hash", "approved_body_hash", "email_sha256"]
  },
  "verification": {
    "residual_scan_passed": true,
    "residual_scan_tables": 14
  }
}
```

`verification.residual_scan_passed` is the result of re-running the erasure predicate over every
table in the map and asserting zero matches. An erasure that reports success without checking is a
promise, not a fact.

### 11.12.5 The path

| Step | Where | Writes |
|---|---|---|
| 1. Request arrives (reply, unsubscribe page note, email) | manual entry at `/settings` → Data tab, or `POST /api/v1/erasure` | `ERASURE_REQUESTED` with `scope_preview{}` — the counts of what *would* be erased |
| 2. Sagar reviews the preview | `/settings` → Data tab | nothing |
| 3. Confirm | `POST /api/v1/erasure/<id>/execute` | job `kind='erasure'` |
| 4. Job runs | `radar/audit.py :: erase_subject()` | the map of §11.12.2, then `ERASURE_EXECUTED` |
| 5. Reply to the requester | manual, template in `radar/prompts/` | `detail.responded_at` on a follow-up note |

```python
def erase_subject(conn: sqlite3.Connection, *, subject_kind: str, subject_value: str,
                  request_audit_id: str, actor: Actor,
                  dry_run: bool = False) -> ErasureReceipt:
    """Remove a person's data without removing the record that we processed it.

    Personal data lives in mutable tables; the audit chain holds only ids and hashes, so
    the chain is untouched and stays verifiable. The one thing that must survive intact is
    the suppression row - erasing that is how you contact somebody again a month after they
    asked you to stop.
    """
```

Deferral. Erasure is refused, with `ERASURE_DEFERRED` and a `review_at`, when:

| Condition | Reason code | Why |
|---|---|---|
| An open `COMPLAINT` suppression referencing this subject | `OPEN_COMPLAINT` | The complaint evidence is the defence if the ESP or a regulator asks |
| An open handoff or live commercial conversation | `ACTIVE_DISPUTE` | There is a live purpose; the request is honoured when it closes |
| A legal notice on file | `LEGAL_HOLD` | — |

In every deferral case the suppression is created or strengthened **immediately**, so the deferral
never means "we keep contacting them".

### 11.12.6 Backups un-erase people — the erasure journal

A backup taken before an erasure contains the erased data. Restoring it silently reverses the
erasure, and nothing in the restored database knows that.

The `ERASURE_EXECUTED` audit rows **are** the erasure journal. The restore procedure (§11.13.6,
step 3) mandatorily replays every `ERASURE_EXECUTED` row whose `executed_at` is later than the
backup's `taken_at` against the restored database, before the application is allowed to read contact
data. `radar/audit.py` exposes:

```python
def replay_erasures(conn: sqlite3.Connection, *, since: str) -> list[ErasureReceipt]:
    """Re-apply every erasure executed after `since`. Idempotent by construction.

    Run against a freshly restored database before anything else touches it. Restoring a
    backup from before an erasure request and skipping this step is how a system contacts
    somebody who asked, in writing, never to be contacted again.
    """
```

Idempotency is real, not aspirational: every operation in the map is "set to a constant" or "delete
a file that may already be gone". Running it twice changes nothing.

Backup encryption (§11.13.1) is the other half: backup archives contain personal data, so they are
encrypted at rest and their retention is bounded at 12 months. An erasure request cannot reach
inside an encrypted archive, and pretending otherwise would be false. What is true and defensible:
archives are encrypted, access-controlled, expire within 12 months, and are never restored without
the journal replay.

### 11.12.7 The purge job

`radar/jobs.py`, job kind `retention_purge`, nightly at 03:10 UTC:

| Pass | Deletes | Writes |
|---|---|---|
| 1 | Capture files past their action's `sidecar_ret` | `RETENTION_PURGE` per class |
| 2 | `report_exports` files past `expires_at` | `REPORT_FILE_DELETED` per file, `RETENTION_PURGE` summary |
| 3 | `business_contacts` with no outreach in 24 months and no open handoff | `ERASURE_EXECUTED` with `reason='RETENTION'` |
| 4 | Backup archives past their rotation slot | `RETENTION_PURGE` |
| 5 | Never | `audit_log` rows, `suppressions` rows, `report_exports` rows |

Every pass is bounded (`LIMIT 500` per run) so a first run after a long gap cannot spend an hour
holding the write lock.

---

## 11.13 Backups

### 11.13.1 What is backed up

| Asset | Path | Personal data | Method | Frequency | Retention |
|---|---|---|---|---|---|
| Database | `data/radar.db` (+ `-wal`, `-shm`) | yes | `VACUUM INTO` snapshot | hourly 07:00–21:00 IST, daily 02:00 | 48 hourly, 14 daily, 8 weekly, 12 monthly |
| Audit segment exports | `data/audit/exports/` | no (ids and hashes) | `rclone copy` — already immutable | daily, after export | forever |
| Capture sidecars | `data/audit/capture/` | yes (prompts carry contact names) | tar + `age` encrypt | daily incremental | 12 months of archives; files themselves per `sidecar_ret` |
| Reports | `data/reports/` | some (`contains_pii = 1` CSV/XLSX) | tar + `age` encrypt | daily incremental | 12 months |
| Config | `config/config.yaml` | no | git | on change | forever |
| Secrets | `config/.env` | n/a | `age`-encrypted, manual, stored **separately** from DB backups | on change | last 3 versions |
| Source snapshots | `data/snapshots/` | no | tar, unencrypted | weekly | 12 months |

Never backed up: `data/tmp/`, `*.tmp`, `radar.db-wal` on its own (a WAL without its database is not
a backup, it is a trap).

`config/.env` holds `SUPPRESSION_HMAC_PEPPER` and `AUDIT_EXPORT_HMAC_KEY`. It is deliberately stored
in a different place from the database backups: an archive containing both the pseudonymised
suppression table and the pepper that de-pseudonymises it is the same archive as one containing
plaintext addresses.

### 11.13.2 How, and how not

```bash
# Correct. Consistent, defragmented, does not block writers for long, works in WAL mode.
sqlite3 data/radar.db "VACUUM INTO 'data/backups/radar-2026-08-27T02-00-00Z.db'"
```

```python
# Equivalent from Python, and what radar/jobs.py actually calls.
with sqlite3.connect("data/radar.db") as src, sqlite3.connect(dest) as dst:
    src.backup(dst)          # online backup API, safe against concurrent writers
```

```bash
# WRONG. Copying the main file while the app runs captures a database whose committed
# transactions are still in the -wal file. It restores as of an arbitrary earlier point,
# usually without any error, which is the worst possible failure mode for a backup.
cp data/radar.db /backups/
```

Post-snapshot pipeline, in order:

| Step | Command | Failure it catches |
|---|---|---|
| 1 | `PRAGMA integrity_check` on the snapshot | A corrupt page copied faithfully |
| 2 | `PRAGMA foreign_key_check` | Referential damage |
| 3 | `audit.verify_chain()` on the snapshot | Backing up an already-broken chain |
| 4 | Record `head_seq` / `head_hash` in the backup's metadata sidecar | Not knowing, later, how far forward this archive reaches |
| 5 | `age -r $BACKUP_AGE_RECIPIENT` | Plaintext personal data at rest off-box |
| 6 | `rclone copyto` to the append-only remote | Loss of the only copy |
| 7 | `audit.write('BACKUP_TAKEN', detail={path, bytes, sha256, head_seq, head_hash, remote_uri})` | No record |

If step 1, 2 or 3 fails, the archive is kept with a `.SUSPECT` suffix, is not rotated out, and a
`CRITICAL` Telegram alert fires. A failing backup that quietly overwrites the last good one is worse
than no backup.

### 11.13.3 Where

There is no VPS (`_CONTEXT.md` §2), which collapsed the old copy 1 ("on the VPS") and copy 3
("pulled to Sagar's own machine") onto the same disk. `12-security-model.md` §12.12.1 owns the
replacement topology; it is restated here because §11.13.2's pipeline writes into it:

| Copy | Location | Survives | Encryption |
|---|---|---|---|
| 1 | `data/backups/` on the laptop | An operator mistake — a bad migration, a wrong `DELETE`. **Not** theft, and not disk failure | BitLocker only. These are the copies restored from most often, and `age`-encrypting them would put the identity file next to them |
| 2 | An external SSD or USB drive kept at home, plugged in weekly | Laptop theft, loss, or disk failure | **`age`, always.** A USB stick is the single most losable object in this design |
| 3 | Cloud object storage, client-side encrypted, uploaded nightly after copy 1 | The house — fire, flood, a burglary that takes both | **`age`, always, with a key the provider never sees** (`12` §12.12.3) |

Copy 3's credential can `PutObject` and nothing else, and the bucket keeps versions — B2 expresses
this as an application key with `writeFiles` and without `deleteFiles`. That is the same property
that protects the audit exports (§11.4.2): a laptop that is stolen or compromised cannot delete or
overwrite what it has already pushed.

Copy 2 is the one that matters and the only one that needs a habit rather than a job.
`python main.py doctor` reports the age of the newest copy-2 archive, and a copy 2 older than 14
days is a finding on the `/settings` security tab. Assertion `A5` below reads "the newest off-box
audit manifest" as the copy-2 drive.

### 11.13.4 Restore test

Monthly, automated, on the newest daily archive:

```
python main.py backup restore-test --archive data/backups/radar-2026-08-27T02-00-00Z.db.age
```

Runs in a scratch directory against a copy, never against `data/`. Assertions:

| # | Assertion | Catches |
|---|---|---|
| A1 | `PRAGMA integrity_check` = `ok` | Corruption |
| A2 | `PRAGMA foreign_key_check` returns no rows | Referential damage |
| A3 | `MAX(version)` in `schema_version` equals the version this code expects | A backup older than the current migrations, which will not open cleanly |
| A4 | `verify_chain()` clean from seq 1 | Chain damage |
| A5 | `head_seq` ≥ the `to_seq` of the newest `AUDIT_ANCHOR` inside the archive, and `head_hash` matches it when equal | A truncated archive |
| A6 | Row counts for `businesses`, `outreach_messages`, `suppressions`, `audit_log` within the drift recorded in the metadata sidecar | A partial snapshot |
| A7 | `explain_message()` on a fixed known `draft_id` returns all eleven bands with `integrity.verified = true` | A backup that restores but is not usable for the thing the system exists to do |
| A8 | `is_suppressed()` for a known suppressed hash returns a row | A pepper/hmac mismatch — the silent failure of §11.12.3 |
| A9 | Three random `report_exports` rows verify against the restored report files | Archive/DB drift |

Writes `BACKUP_RESTORE_TESTED` with the full assertion map. A failure is `CRITICAL` and pages
Telegram. A restore procedure that has not been executed in the last 35 days is itself reported as a
finding on the `/settings` audit tab — an untested backup is a hypothesis.

### 11.13.5 The restore order, and why the order is the whole thing

Restoring in the wrong order does not merely waste time. It re-sends messages, un-erases people, and
loses audit rows. This checklist is the procedure; each step names the failure it prevents.

```
 0. STOP the application and the worker. Do not start it "just to look" - a running worker
    will claim jobs out of the restored queue and start sending.

 1. Restore the database to a SCRATCH path, never over data/radar.db.
    age -d < archive | > /srv/restore/radar.db
    Prevents: destroying the current database before you know the archive is good.

 2. Verify the scratch copy: integrity_check, foreign_key_check, verify_chain(full).
    Compare head_seq/head_hash against the NEWEST off-box audit manifest.
      - head_seq >= manifest.to_seq  -> good.
      - head_seq <  manifest.to_seq  -> the archive is behind the exported chain. Replay
        the missing rows from the exported .jsonl.gz segments BEFORE going further.
    Prevents: silently losing audit rows that were already published off-box.

 3. Replay the erasure journal:
      python main.py dpdp replay-erasures --db /srv/restore/radar.db --since <archive taken_at>
    Prevents: an erased person's contact details coming back to life and being contacted.
    This runs BEFORE anything reads contact data. It is not optional and it is not last.

 4. Restore data/audit/exports/ - copy in, never overwrite an existing file.
    Prevents: replacing a published segment with a stale one.

 5. Restore data/audit/capture/, data/reports/, data/snapshots/.
    Then: python main.py audit verify-reports  (expect OK/MISSING, never MODIFIED)
    Prevents: an archive whose report hashes no longer match.

 6. Expire every job lease:
      UPDATE jobs SET lease_owner = NULL, lease_expires_at = NULL WHERE lease_owner IS NOT NULL;
    Prevents: two workers believing they own the same send job.

 7. Move the scratch database into place. Start the app with sending disabled:
      RADAR_SEND_DISABLED=1 python main.py serve
    Prevents: the queue draining into people's inboxes while state is still wrong.

 8. Reconcile outbound with the provider. For every outreach_messages row in QUEUED, or in
    SENT with sent_at >= archive taken_at, query the provider by idempotency_key /
    provider_message_id and set the true status.
    Prevents: RE-SENDING messages that the archive does not know were already sent. This is
    the single highest-cost mistake available during a restore.

 9. Reconcile suppressions. Import the provider's own suppression/bounce list and every
    SUPPRESSION_CREATED row from the audit export segments after taken_at.
    Prevents: contacting somebody who opted out during the window the backup predates.
    Suppressions MUST be current before step 11.

10. Reconcile inbound. Re-poll the mailbox and the WhatsApp webhook backlog from taken_at,
    so responses received during the window are classified and any handoff is re-created.
    Prevents: an interested lead sitting unanswered because the reply landed in the gap.

11. Only now: unset RADAR_SEND_DISABLED. Write BACKUP_RESTORED with head_seq before/after,
    erasure_replayed, reconciled_messages.
```

The dependency, stated as one sentence so it is not lost in the list: **erasures replay before
anything reads contact data, and suppressions and message statuses are reconciled before the send
worker is allowed to run.** Everything else in the order is convenience; those two are the ones that
determine whether the restore harms a person.

### 11.13.6 What a restore cannot fix

| Situation | Consequence | Handling |
|---|---|---|
| Messages sent between `taken_at` and the failure | The database does not know about them until step 8 | Provider reconciliation; where the provider cannot answer, the message is marked `FAILED` with `INDETERMINATE` and never retried (§11.7.4) |
| Audit rows written in that window and not yet exported | Genuinely lost | The gap is recorded: `BACKUP_RESTORED.detail.head_seq_before/after` makes the discontinuity explicit rather than invisible. The chain restarts cleanly from the restored head because `trg_audit_log_chain` only looks at `MAX(seq)`. |
| A capture file written in the window | Lost; the audit row that references it may also be lost | `explain_message()` reports `CAPTURE_MISSING` |
| An erasure requested but not executed in the window | The request row is lost | Requests are also mailed to Sagar on arrival, so the paper trail survives the database |

---

## 11.14 The invariant probe set

Ten queries that must return **zero rows**. Job `invariant_probes` runs them nightly at 03:40 UTC
and after every restore; any non-empty result writes `INVARIANT_PROBE_FAILED` (`CRITICAL`) with the
offending ids and pages Telegram. They are also the fastest honest answer to Q2 — "prove nothing was
sent without my approval" is P1 and P2 returning nothing, every night, with the result recorded in a
hash-chained row.

Migration `036` adds one more column so P3 is pure SQL:

```sql
ALTER TABLE outreach_messages ADD COLUMN to_address_hmac TEXT;   -- HMAC of to_address_norm
CREATE INDEX ix_om_to_hmac ON outreach_messages(to_address_hmac);
```

It is written at send time and survives erasure, which is exactly when P3 needs to keep working.

| # | Probe | Catches |
|---|---|---|
| P1 | A sent message with no live, matching approval | Invariant 1 broken |
| P2 | A sent message with no §48 audit row | The audit trigger disabled or bypassed |
| P3 | A message sent to a contact point suppressed before the send | Invariant 3 broken |
| P4 | A gap in `audit_log.seq` | Rows deleted after the triggers were dropped |
| P5 | An approval not created by a human web session | The type-level barrier bypassed |
| P6 | `draft_findings` disagreeing with `facts_used` / `inferences_used` | One of two writers changed alone |
| P7 | An `UNKNOWN` finding cited by a claim | Invariant 4 broken |
| P8 | `contact_policy.automation_mode` anything but `HUMAN_APPROVAL` | §46 default silently changed |
| P9 | A business in `CONTACTED` with no `BUSINESS_VERIFIED` audit row | §45 broken — the whole product rule |
| P10 | A `report_exports` row whose file is missing or modified | Archive drift |

```sql
-- P1: sent without a live approval whose hash and address match.
-- After erasure both addresses are NULL and the address comparison is skipped by SQL's
-- three-valued logic; the body-hash comparison still holds, because hashes are retained.
SELECT m.id, m.business_id, m.sent_at, m.status, m.approval_id
  FROM outreach_messages m
  LEFT JOIN outreach_approvals a
         ON a.id = m.approval_id AND a.revoked_at IS NULL
 WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
   AND (a.id IS NULL
        OR a.approved_body_hash  <> m.body_hash
        OR a.approved_to_address <> m.to_address_norm);

-- P2: sent without a §48 audit row.
SELECT m.id, m.sent_at
  FROM outreach_messages m
 WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
   AND NOT EXISTS (SELECT 1 FROM audit_log al
                    WHERE al.message_id = m.id
                      AND al.action IN ('OUTREACH_SENT','MANUAL_SEND_RECORDED'));

-- P3: sent to a contact point that was already suppressed.
SELECT m.id, m.sent_at, s.id AS suppression_id, s.reason, s.created_at
  FROM outreach_messages m
  JOIN suppressions s
    ON s.value_hmac = m.to_address_hmac
   AND s.scope = CASE m.channel WHEN 'EMAIL' THEN 'EMAIL'
                                WHEN 'WHATSAPP' THEN 'WHATSAPP'
                                ELSE 'PHONE' END
 WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
   AND s.released_at IS NULL
   AND s.created_at < m.sent_at;

-- P4: a hole in the chain.
SELECT a.seq + 1 AS missing_seq
  FROM audit_log a
 WHERE a.seq < (SELECT MAX(seq) FROM audit_log)
   AND NOT EXISTS (SELECT 1 FROM audit_log b WHERE b.seq = a.seq + 1);

-- P5: an approval that did not come from a human browser session.
SELECT a.id, a.message_id, a.approved_at
  FROM outreach_approvals a
 WHERE a.approved_by IS NULL
    OR a.session_auth_method NOT IN ('PASSWORD','PASSWORD_TOTP')
    OR NOT EXISTS (SELECT 1 FROM audit_log al
                    WHERE al.action       = 'OUTREACH_APPROVED'
                      AND al.entity_table = 'outreach_approvals'
                      AND al.entity_id    = a.id
                      AND al.actor_kind   = 'HUMAN');

-- P6: the join table and the JSON arrays disagree.
WITH counts AS (
  SELECT d.id AS draft_id,
         (SELECT COUNT(*) FROM draft_findings df
           WHERE df.draft_id = d.id AND df.role = 'FACT')      AS join_facts,
         (SELECT COUNT(*) FROM draft_findings df
           WHERE df.draft_id = d.id AND df.role = 'INFERENCE') AS join_infs,
         json_array_length(d.facts_used)       AS json_facts,
         json_array_length(d.inferences_used)  AS json_infs
    FROM outreach_drafts d
)
SELECT * FROM counts
 WHERE join_facts <> json_facts OR join_infs <> json_infs;

-- P7: an UNKNOWN finding behind a claim. The CHECK constraint prevents it; the probe is
-- there for the day somebody rebuilds the table without the constraint.
SELECT df.draft_id, df.finding_id, df.claim_index
  FROM draft_findings df
 WHERE df.kind = 'UNKNOWN' AND (df.claim_index IS NOT NULL OR df.role <> 'CONTEXT');

-- P8: §46 default changed.
SELECT id, scope, automation_mode
  FROM contact_policy
 WHERE automation_mode <> 'HUMAN_APPROVAL';

-- P9: contacted without a recorded human verification. §45 in one query.
SELECT b.id, b.name, b.city, b.status
  FROM businesses b
 WHERE b.status IN ('CONTACTED','RESPONDED','INTERESTED','HUMAN_HANDOFF')
   AND NOT EXISTS (SELECT 1 FROM audit_log al
                    WHERE al.business_id = b.id
                      AND al.action      = 'BUSINESS_VERIFIED');

-- P10: run by `main.py audit verify-reports`; the SQL half selects the candidates.
SELECT r.id, r.rel_path, r.content_sha256
  FROM report_exports r
 WHERE r.deleted_at IS NULL
 ORDER BY r.generated_at DESC;
```

---

## 11.15 The queries Sagar will actually run

Kept in `radar/sql/audit/*.sql` and exposed as `python main.py audit query <name> [args]`, so they
are version-controlled rather than retyped from memory at the moment they are needed.

### 11.15.1 Everything sent last week

Two versions, deliberately. The operational one reads the working tables; the evidentiary one reads
only `audit_log`, so it answers the question even if somebody argues the working tables were edited.

```sql
-- radar/sql/audit/sent_last_week.sql   (operational)
SELECT m.sent_at,
       b.name        AS business,
       b.city,
       b.industry,
       m.channel,
       m.to_address_display AS contact,
       m.subject_final      AS subject,
       m.status,
       ap.approved_by,
       ap.approved_at,
       m.provider,
       m.provider_message_id,
       c.name        AS campaign,
       m.sequence_no
  FROM outreach_messages m
  JOIN businesses b            ON b.id  = m.business_id
  JOIN campaigns  c            ON c.id  = m.campaign_id
  LEFT JOIN outreach_approvals ap ON ap.id = m.approval_id
 WHERE m.sent_at >= strftime('%Y-%m-%dT%H:%M:%SZ','now','-7 days')
 ORDER BY m.sent_at;
```

```sql
-- radar/sql/audit/sent_last_week_from_audit.sql   (evidentiary)
SELECT al.seq,
       al.at                                                     AS sent_at,
       json_extract(al.detail_json, '$.business.name')           AS business,
       json_extract(al.detail_json, '$.business.city')           AS city,
       json_extract(al.detail_json, '$.channel')                 AS channel,
       json_extract(al.detail_json, '$.contact.address_masked')  AS contact,
       json_extract(al.detail_json, '$.approval.approved_by')    AS approved_by,
       json_extract(al.detail_json, '$.approval.approved_at')    AS approved_at,
       json_extract(al.detail_json, '$.provider.name')           AS provider,
       json_extract(al.detail_json, '$.provider.status_code')    AS status_code,
       json_extract(al.detail_json, '$.policy.result')           AS policy_result,
       al.id                                                     AS audit_id
  FROM audit_log al
 WHERE al.action IN ('OUTREACH_SENT','MANUAL_SEND_RECORDED')
   AND al.at >= strftime('%Y-%m-%dT%H:%M:%SZ','now','-7 days')
 ORDER BY al.seq;
```

`main.py audit query sent_last_week --verify` also runs `verify_chain()` over the returned `seq`
range and prints `chain OK seq 41102-41240` under the table. That line is the difference between a
listing and evidence.

### 11.15.2 Every message mentioning a given finding

```sql
-- radar/sql/audit/messages_citing_finding.sql   :finding_id
SELECT f.kind                         AS finding_kind,
       f.text                         AS finding_text,
       df.role,
       df.claim_index,
       df.hedged,
       b.name                         AS business,
       b.city,
       d.id                           AS draft_id,
       m.id                           AS message_id,
       m.status,
       m.sent_at,
       d.policy_result,
       d.prompt_version
  FROM draft_findings df
  JOIN research_findings f ON f.id = df.finding_id
  JOIN outreach_drafts   d ON d.id = df.draft_id
  JOIN businesses        b ON b.id = d.business_id
  LEFT JOIN outreach_messages m ON m.draft_id = d.id
 WHERE df.finding_id = :finding_id
 ORDER BY m.sent_at NULLS LAST, d.created_at;
```

The inverse — every finding a given message rested on — is band 2 of `explain_message()`. And the
question behind both, "we got a claim wrong; who else did we tell?", is:

```sql
-- radar/sql/audit/blast_radius.sql   :finding_id
SELECT b.name, b.city, m.channel, m.to_address_display, m.sent_at, m.status,
       r.classification
  FROM draft_findings df
  JOIN outreach_drafts   d ON d.id = df.draft_id
  JOIN outreach_messages m ON m.draft_id = d.id
  JOIN businesses        b ON b.id = m.business_id
  LEFT JOIN responses    r ON r.in_reply_to_message_id = m.id
 WHERE df.finding_id = :finding_id
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
 ORDER BY m.sent_at;
```

### 11.15.3 Every business contacted more than once

```sql
-- radar/sql/audit/contacted_more_than_once.sql
SELECT b.id,
       b.name,
       b.city,
       b.industry,
       COUNT(*)                                   AS sends,
       COUNT(DISTINCT m.channel)                  AS channels,
       group_concat(DISTINCT m.channel)           AS channel_list,
       MIN(m.sent_at)                             AS first_sent,
       MAX(m.sent_at)                             AS last_sent,
       CAST(julianday(MAX(m.sent_at)) - julianday(MIN(m.sent_at)) AS INTEGER) AS span_days,
       COUNT(DISTINCT m.campaign_id)              AS campaigns,
       MAX(CASE WHEN r.id IS NOT NULL THEN 1 ELSE 0 END) AS ever_responded
  FROM outreach_messages m
  JOIN businesses b       ON b.id = m.business_id
  LEFT JOIN responses r   ON r.in_reply_to_message_id = m.id
 WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
 GROUP BY b.id, b.name, b.city, b.industry
HAVING COUNT(*) > 1
 ORDER BY sends DESC, last_sent DESC;
```

The version that matters more — repeats that were closer together than policy allows:

```sql
-- radar/sql/audit/repeat_contacts_vs_policy.sql
WITH sends AS (
  SELECT m.id, m.business_id, m.channel, m.sent_at,
         LAG(m.sent_at) OVER (PARTITION BY m.business_id ORDER BY m.sent_at) AS prev_sent_at
    FROM outreach_messages m
   WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
),
gaps AS (
  SELECT s.*,
         CAST(julianday(s.sent_at) - julianday(s.prev_sent_at) AS INTEGER) AS gap_days
    FROM sends s
   WHERE s.prev_sent_at IS NOT NULL
)
SELECT b.name, b.city, g.channel, g.prev_sent_at, g.sent_at, g.gap_days,
       cp.min_days_between_outreach AS policy_min_days,
       g.id AS message_id
  FROM gaps g
  JOIN businesses b       ON b.id = g.business_id
  CROSS JOIN contact_policy cp ON cp.id = 'GLOBAL'
 WHERE g.gap_days < cp.min_days_between_outreach
 ORDER BY g.gap_days, g.sent_at;
```

`LAG()` is SQLite 3.25+ and standard in Postgres. Rows here should be impossible — the duplicate
gate refuses them at send — so a non-empty result is a bug report, not a report.

### 11.15.4 Every policy block, and why

```sql
-- radar/sql/audit/policy_blocks.sql   :since
SELECT al.at,
       b.name                                                   AS business,
       b.city,
       b.industry,
       json_extract(al.detail_json,'$.policy_version')          AS policy_version,
       json_extract(v.value,'$.rule')                           AS rule,
       json_extract(v.value,'$.finding_kind')                   AS finding_kind,
       json_extract(v.value,'$.finding_id')                     AS finding_id,
       json_extract(v.value,'$.sentence_excerpt')               AS sentence,
       json_extract(v.value,'$.explanation')                    AS explanation,
       json_extract(v.value,'$.suggested_fix')                  AS suggested_fix,
       al.entity_id                                             AS draft_id,
       al.id                                                    AS audit_id
  FROM audit_log al
  JOIN outreach_drafts d ON d.id = al.entity_id
  JOIN businesses      b ON b.id = d.business_id,
       json_each(json_extract(al.detail_json,'$.violations')) v
 WHERE al.action = 'POLICY_BLOCK'
   AND al.at >= :since
 ORDER BY al.at DESC;
```

The rollup that says whether the prompt needs fixing rather than the message:

```sql
-- radar/sql/audit/policy_block_rollup.sql   :since
SELECT json_extract(v.value,'$.rule')                  AS rule,
       json_extract(al.detail_json,'$.policy_version') AS policy_version,
       d.prompt_version,
       COUNT(*)                                        AS blocks,
       COUNT(DISTINCT al.entity_id)                    AS drafts,
       COUNT(DISTINCT d.business_id)                   AS businesses
  FROM audit_log al
  JOIN outreach_drafts d ON d.id = al.entity_id,
       json_each(json_extract(al.detail_json,'$.violations')) v
 WHERE al.action = 'POLICY_BLOCK'
   AND al.at >= :since
 GROUP BY rule, policy_version, d.prompt_version
 ORDER BY blocks DESC;
```

`json_each` appears only in these two investigation queries and never on an application code path.
The Postgres translation is `jsonb_array_elements(detail_json->'violations')`, noted here so the
port is a search-and-replace rather than a rewrite.

### 11.15.5 The rest of the standing set

```sql
-- everything that ever happened to one business, in order.
-- The first query to run for "why did this message go to this business?".
SELECT al.seq, al.at, al.action, aa.severity, al.actor_kind, al.actor_label,
       al.entity_table, al.entity_id, al.detail_json
  FROM audit_log al
  JOIN audit_actions aa ON aa.action = al.action
 WHERE al.business_id = :business_id
 ORDER BY al.seq;

-- who approved what, with the session behind it.
SELECT ap.approved_at, u.username, b.name, m.channel, ap.approved_to_address,
       ap.session_auth_method, ap.client_ip, ap.user_agent,
       m.status, m.sent_at,
       (ap.approved_body_hash = m.body_hash) AS hash_matches
  FROM outreach_approvals ap
  JOIN outreach_messages  m ON m.id = ap.message_id
  JOIN businesses         b ON b.id = ap.business_id
  JOIN users              u ON u.id = ap.approved_by
 WHERE ap.approved_at >= :since
 ORDER BY ap.approved_at DESC;

-- every opt-out and where it came from (§30's provenance).
SELECT s.created_at, s.scope, s.value_masked, s.reason, s.source, s.source_ref,
       b.name AS business, b.city, s.released_at, s.erased_at
  FROM suppressions s
  LEFT JOIN businesses b ON b.id = s.business_id
 ORDER BY s.created_at DESC;

-- every send that a gate blocked, and which gate.
SELECT al.at, b.name, b.city,
       al.action                                        AS block_kind,
       json_extract(al.detail_json,'$.rule')            AS rule,
       json_extract(al.detail_json,'$.gate')            AS gate,
       json_extract(al.detail_json,'$.days_since')      AS days_since,
       json_extract(al.detail_json,'$.previous_message_id') AS previous_message_id
  FROM audit_log al
  JOIN businesses b ON b.id = al.business_id
 WHERE al.action IN ('DUPLICATE_BLOCK','SUPPRESSION_BLOCK','ELIGIBILITY_BLOCK','SELECTION_BLOCKED')
   AND al.at >= :since
 ORDER BY al.at DESC;

-- the funnel of §54, from audit rows only, per city.
SELECT b.city,
       COUNT(DISTINCT CASE WHEN al.action='BUSINESS_DISCOVERED' THEN al.business_id END) AS discovered,
       COUNT(DISTINCT CASE WHEN al.action='BUSINESS_VERIFIED'   THEN al.business_id END) AS verified,
       COUNT(DISTINCT CASE WHEN al.action='SELECTION_CREATED'   THEN al.business_id END) AS selected,
       COUNT(DISTINCT CASE WHEN al.action IN ('OUTREACH_SENT','MANUAL_SEND_RECORDED')
                           THEN al.business_id END)                                      AS contacted,
       COUNT(DISTINCT CASE WHEN al.action='RESPONSE_CLASSIFIED' THEN al.business_id END)  AS responded,
       COUNT(DISTINCT CASE WHEN al.action='HANDOFF_CREATED'     THEN al.business_id END)  AS handed_off
  FROM audit_log al
  JOIN businesses b ON b.id = al.business_id
 WHERE al.campaign_id = :campaign_id
 GROUP BY b.city
 ORDER BY b.city;

-- login history and failed attempts.
SELECT al.at, al.action, al.actor_label, al.client_ip, al.user_agent,
       json_extract(al.detail_json,'$.auth_method') AS auth_method,
       json_extract(al.detail_json,'$.reason')      AS reason
  FROM audit_log al
 WHERE al.action IN ('LOGIN_SUCCEEDED','LOGIN_FAILED','LOGIN_LOCKED','PASSWORD_CHANGED')
   AND al.at >= :since
 ORDER BY al.at DESC;

-- everything held about one data principal, for a DPDP access request.
SELECT 'business_contacts' AS src, bc.id, bc.business_id, bc.collected_at, bc.source
  FROM business_contacts bc WHERE bc.email_sha256 = :subject_sha256
UNION ALL
SELECT 'outreach_messages', m.id, m.business_id, m.sent_at, m.channel
  FROM outreach_messages m WHERE m.to_address_hmac = :subject_hmac
UNION ALL
SELECT 'responses', r.id, r.business_id, r.received_at, r.channel
  FROM responses r WHERE r.from_address_sha256 = :subject_sha256
UNION ALL
SELECT 'suppressions', s.id, s.business_id, s.created_at, s.reason
  FROM suppressions s WHERE s.value_hmac = :subject_hmac
 ORDER BY 4;
```

---

## 11.16 `radar/audit.py`

### 11.16.1 Module docstring

```python
"""The record of why every message went where it went, and on whose authority.

Six months after a campaign, a business replies asking where we got an idea about their
operations. Without these rows there is no answer: the research has been re-run, the prompt
has been edited twice, the score has been recomputed under new weights, and the message is
just text in a table. With them, one screen reconstructs the whole chain - the URL that was
fetched, the finding it produced, the hedge the policy engine demanded, the sentence Sagar
edited, the click that approved it, and the provider id that accepted it.

Append-only: triggers refuse UPDATE and DELETE, and every row carries a hash of the row
before it, so a deletion or an edit is detectable rather than invisible. Nothing in here
stores a raw email address or phone number - only ids, hashes and masked displays - which is
what lets an erasure request be honoured without destroying the evidence that we honoured it.
"""
from __future__ import annotations

import contextvars
import hashlib
import hmac
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

log = logging.getLogger("radar.audit")
```

### 11.16.2 The write path

```python
@dataclass(frozen=True)
class Actor:
    kind: str                      # HUMAN | SYSTEM | PROVIDER | ANONYMOUS
    label: str                     # 'usr_sagar' | 'worker-1' | 'gmail' | '-'
    user_id: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    route: str | None = None
    http_method: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None
    job_id: str | None = None
    job_run_id: str | None = None


_ACTOR: contextvars.ContextVar[Actor] = contextvars.ContextVar("radar_actor")


def bind_actor(actor: Actor) -> contextvars.Token:
    """Bind the actor for this request/job. Flask before_request and the job worker call it."""


def write(conn: sqlite3.Connection, *,
          action: str,
          entity_table: str,
          entity_id: str | None = None,
          before: Mapping[str, Any] | None = None,
          after: Mapping[str, Any] | None = None,
          detail: Mapping[str, Any] | None = None,
          business_id: str | None = None,
          campaign_id: str | None = None,
          message_id: str | None = None,
          actor: Actor | None = None) -> str:
    """Append one audit row inside the caller's transaction. Returns its aud_ id.

    Raises if there is no open transaction: an audit row that commits separately from the
    thing it audits can survive a rollback of that thing, which is worse than no row.
    Raises if no actor is bound - a row whose actor is '-' looks like evidence and isn't.
    Unknown `action` fails on the audit_actions foreign key, by design.
    """
```

Internals, in order:

| Step | What |
|---|---|
| 1 | `assert conn.in_transaction` — else `AuditOutsideTransaction` |
| 2 | Resolve the actor: argument, else `_ACTOR.get()`, else `AuditNoActor` |
| 3 | `detail = _scrub_addresses(detail)`; assert no key named `address`, `to`, `email`, `phone` at any depth |
| 4 | Serialise `before`/`after`/`detail` once with `canonical_json()` |
| 5 | `seq = SELECT COALESCE(MAX(seq),0)+1`, `prev_hash = row_hash at seq-1` (or genesis) |
| 6 | `id = ids.new("aud")`, `at = utcnow_iso()` |
| 7 | `row_hash = compute_row_hash(prev_hash, row)` |
| 8 | `INSERT`, binding the exact serialised strings from step 4 |
| 9 | On `IntegrityError` against `ux_audit_seq` / `ux_audit_row_hash`: retry from step 5, max 3 |
| 10 | Return the id |

Helpers used across the codebase, defined here so masking is done one way:

```python
def sha256_hex(value: str) -> str: ...
def mask_email(addr: str) -> str:      # 'invoice@abchospital.example' -> 'in***@abchospital.example'
def mask_phone(e164: str) -> str:      # '+919812345678' -> '+91******5678'
def mask_display(channel: str, value: str) -> str: ...
def _scrub_addresses(obj: Any) -> Any: ...
```

`mask_email` keeps the domain because the domain is a business identifier and is what makes a
duplicate-domain investigation possible; it keeps only the first two characters of the local part.

### 11.16.3 Public surface

| Function | Purpose |
|---|---|
| `write(...) -> str` | The only insert path |
| `chain_head(conn) -> ChainHead` | `(seq, row_hash, at)` of the newest row |
| `verify_chain(conn, ...) -> ChainReport` | §11.3.5 |
| `export_segment(conn, day, out_dir) -> ExportManifest` | §11.5.2 |
| `anchor(conn, manifest) -> str` | Writes `AUDIT_ANCHOR`, sends the Telegram message |
| `explain_message(conn, draft_id, ...) -> Explanation` | §11.9 |
| `timeline(conn, business_id, *, visible_only=True) -> list[AuditEntry]` | The `/business/<id>` history tab |
| `erase_subject(conn, ...) -> ErasureReceipt` | §11.12.5 |
| `replay_erasures(conn, since) -> list[ErasureReceipt]` | §11.12.6 |
| `run_probes(conn) -> list[ProbeResult]` | §11.14 |

### 11.16.4 Binding the actor

```python
# radar/web/app.py
@app.before_request
def _bind_request_actor() -> None:
    rid = request.headers.get("X-Request-Id") or ids.new("req")
    g.request_id = rid
    user = auth.current_user()
    audit.bind_actor(Actor(
        kind="HUMAN" if user else "ANONYMOUS",
        label=user.id if user else "-",
        user_id=user.id if user else None,
        request_id=rid,
        session_id=session.get("sid"),
        route=request.path,
        http_method=request.method,
        client_ip=request.remote_addr,          # never X-Forwarded-For; see below
        user_agent=request.headers.get("User-Agent", "")[:400],
    ))

@app.after_request
def _echo_request_id(resp):
    resp.headers["X-Request-Id"] = g.get("request_id", "")
    return resp
```

`X-Forwarded-For` is **not** read, on any route. There is no reverse proxy in this build — waitress
binds `127.0.0.1` directly (`_CONTEXT.md` §2, `12-security-model.md` §12.1) — so nothing trustworthy
sets that header, and the only party that could set it is the browser on the same machine, which is
the party the field would be used to identify. `client_ip` is therefore `request.remote_addr`, and
it will read `127.0.0.1` on essentially every row. That is the honest value: an audit row carrying
a routable address the application never observed is worse evidence than a boring one, because it
reads as if it located somebody. The job worker binds
`Actor(kind="SYSTEM", label=f"worker-{n}", job_id=..., job_run_id=...)` around each claimed job.
There is no webhook handler to bind an actor in — `_CONTEXT.md` §2 removed inbound HTTP entirely, so
the only thing that can speak for the mail provider is `poll_inbox`, which binds
`Actor(kind="PROVIDER", label="gmail", job_id=..., job_run_id=...)` around the rows it writes on the
strength of something the provider produced (a DSN, an unsubscribe mail) and stays `kind="SYSTEM"`
for everything else it does. `kind="ANONYMOUS"` survives for the pre-authentication cases that are
still real on `127.0.0.1`: `LOGIN_FAILED` and `ACCESS_DENIED`.

Echoing `X-Request-Id` means a screenshot of a browser error and the audit rows behind it join on
one string.

### 11.16.5 Config

```yaml
# config/config.yaml
audit:
  export_dir:            data/audit/exports
  capture_dir:           data/audit/capture
  daily_export_hour_utc: 20
  remote_uri:            "b2:radar-audit/exports"
  anchor_telegram:       true
  anchor_email:          true
  verify_on_start:       tail        # off | tail | full
  verify_tail_rows:      5000
  probe_hour_utc:        3
  digest_hour_utc:       13          # CRITICAL rows of the last 24h, to Telegram

reports:
  dir:                   data/reports
  retention:
    html_campaign:       PERMANENT
    daily_html:          PERMANENT
    pdf:                 P2Y
    tabular_no_contacts: P2Y
    tabular_with_contacts: P180D

backups:
  dir:                   data/backups
  hourly_between:        ["07:00", "21:00"]
  daily_at:              "02:00"
  keep:                  {hourly: 48, daily: 14, weekly: 8, monthly: 12}
  remote_uri:            "b2:radar-backups"
  restore_test_day:      1           # day of month
  restore_test_max_age_days: 35

retention:
  contact_idle_months:   24
  purge_hour_utc:        3
  purge_batch:           500
```

```
# config/.env   (never in YAML, never in git)
AUDIT_EXPORT_HMAC_KEY=<32 random bytes, hex>
SUPPRESSION_HMAC_PEPPER=<32 random bytes, hex - NEVER ROTATED, see 11.12.3>
BACKUP_AGE_RECIPIENT=age1...
RCLONE_CONFIG_PASS=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### 11.16.6 CLI

```
python main.py audit verify [--full] [--from SEQ]
python main.py audit head
python main.py audit export --day 2026-08-26 [--no-upload]
python main.py audit anchor --day 2026-08-26
python main.py audit explain --draft out_01J... [--json] [--html out.html]
python main.py audit timeline --business biz_01J... [--all]
python main.py audit probes [--json]
python main.py audit query <name> [--since 2026-08-01] [--csv out.csv] [--verify]
python main.py audit verify-reports [--campaign cmp_...] [--since DATE]

python main.py dpdp preview-erasure --email x@y.z
python main.py dpdp erase --email x@y.z --request-audit aud_01J...
python main.py dpdp replay-erasures --db PATH --since 2026-08-27T02:00:00Z
python main.py dpdp export-subject --email x@y.z --out sar.json.gz

python main.py backup now
python main.py backup restore-test --archive PATH
python main.py backup list
```

`audit explain --html out.html` writes the self-contained page of §11.9.1, which is what gets
attached to an email when somebody asks a hard question.

### 11.16.7 Tests

`tests/test_audit.py`, `tests/test_audit_chain.py`, `tests/test_erasure.py`,
`tests/test_report_archive.py`. No network; a temporary SQLite file per test.

| Test | Asserts |
|---|---|
| `test_update_audit_row_raises` | `UPDATE audit_log` raises `sqlite3.IntegrityError` with the trigger message |
| `test_delete_audit_row_raises` | Same for `DELETE` |
| `test_chain_links_and_verifies` | 500 rows verify clean; `chain_head` matches the last `row_hash` |
| `test_tampered_row_detected` | Drop triggers, edit `detail_json` of row 200, expect `first_bad_seq == 200`, `HASH_MISMATCH` |
| `test_deleted_row_detected` | Drop triggers, delete row 200, expect `SEQ_GAP` at 200 |
| `test_out_of_order_insert_rejected` | Insert with `seq = MAX+2` aborts |
| `test_forked_prev_hash_rejected` | Insert with a wrong `prev_hash` aborts |
| `test_write_outside_transaction_raises` | `AuditOutsideTransaction` |
| `test_write_without_actor_raises` | `AuditNoActor` |
| `test_unknown_action_rejected` | FK violation on `audit_actions` |
| `test_raw_address_in_detail_rejected` | `trg_audit_log_no_raw_address` fires |
| `test_sent_requires_audit_row` | `UPDATE ... SET status='SENT'` without the audit row aborts |
| `test_approval_requires_audit_row` | Inserting `outreach_approvals` without the audit row aborts |
| `test_send_transaction_rollback_drops_audit_row` | Provider failure mid-transaction leaves neither the audit row nor `SENT` |
| `test_json_canonical_bytes_are_hashed_bytes` | Reordering keys in the input yields the same stored string and hash |
| `test_erasure_preserves_chain` | `verify_chain()` clean before and after `erase_subject()`; `MAX(seq)` grew by exactly the receipt rows |
| `test_erasure_preserves_suppression_match` | `is_suppressed()` returns the row after erasure |
| `test_erasure_is_idempotent` | Second run changes nothing; `residual_scan_passed` still true |
| `test_replay_erasures_on_restored_db` | Restored pre-erasure DB + replay == post-erasure DB, field by field |
| `test_explain_reconstructs_all_bands` | Fixture campaign; all eleven bands populated; no `gaps[]` |
| `test_explain_uses_pinned_ids` | Re-score the business after the send; explain still shows the original score |
| `test_explain_renders_after_erasure` | Bands present, `redactions[]` non-empty, no exception |
| `test_report_hashes_stable_across_regeneration` | Same data, two runs: `data_sha256` equal, `content_sha256` different |
| `test_report_tombstone_not_delete` | `DELETE FROM report_exports` aborts |
| `test_probes_pass_on_fixture` | All ten probes return zero rows on the good fixture |
| `test_probes_catch_seeded_violations` | Each probe returns exactly the seeded bad row |

`test_explain_uses_pinned_ids` is the one that keeps §11.9.3's governing rule from decaying: it
fails the moment somebody "simplifies" the explain view to read the current opportunity.

### 11.16.8 Failure modes

| Failure | Symptom | Handling |
|---|---|---|
| `audit.write()` raises inside a send | Transaction rolls back; message stays `QUEUED` | Retried by the job; if it keeps failing, `JOB_FAILED_TERMINAL` and the message is not sent. Correct: no audit, no send. |
| Chain verification fails at startup | App enters read-only mode | `AUDIT_CHAIN_BROKEN`, Telegram alert, manual investigation from the last off-box manifest |
| Daily export upload fails | Segment exists locally, not off-box | Retried hourly for 24 h, then `CRITICAL`. Anchor row is still written and marked `remote_uri: null` |
| Capture file write fails | `capture_path = null`, `capture_error` set | Draft proceeds; explain shows `CAPTURE_MISSING` |
| `SUPPRESSION_HMAC_PEPPER` missing or changed | Startup refuses | Fingerprint check against `contact_policy`; the app never runs with a suppression list it cannot match |
| Disk full during export or backup | `.tmp` file left, no `os.replace` | Atomic-write rule means nothing partial is ever adopted; alert on the job failure |
| Clock steps backwards | `at` non-monotonic | Warning in `ChainReport.non_monotonic_at`; `seq` remains authoritative; never fatal |
| Two workers race an audit insert | `IntegrityError` on `ux_audit_seq` | Retry up to 3 times with a fresh head read, then fail the caller's transaction |
| Someone restores an old DB by hand | `head_seq` below the last anchor | Startup refuses to leave read-only mode; §11.13.5 checklist referenced by name in the error |

---

## Open questions

1. **Two tables outside the canonical list.** `audit_actions` (the action catalogue backing the FK
   and holding severity/retention/visibility) and `draft_findings` (the join that makes
   "every message citing finding X" indexable and portable). Both follow the precedent set by
   `outreach_status_transitions` in `05-outreach-workflow.md`. If `01-data-model.md` prefers a
   `CHECK` list for actions and JSON-only finding references, that wins and §11.6/§11.8.2 change to
   match — but the finding query then needs `json_each` in application code, which `_CONTEXT.md` §2
   discourages.

2. **Id prefix `rex_` for `report_exports`.** `_CONTEXT.md` §2 names prefixes for nine tables and
   not this one. This document uses `rex_`; `01-data-model.md` decides. Same for `sup_`, `apr_`,
   `evt_`, `sel_`, `cnt_` (already claimed by `05-outreach-workflow.md`) and `jrn_` for `job_runs`.

3. **Additive columns on tables another document owns.** Migration `036` adds `value_hmac` and
   `erased_at` to `suppressions` and `to_address_hmac` to `outreach_messages`, both owned by
   `05-outreach-workflow.md`. They are required by the erasure design (§11.12.3) and probe P3. If
   that document would rather define them itself, the migration number moves and nothing else
   changes.

4. **The export HMAC is not an operator-resistant signature.** `AUDIT_EXPORT_HMAC_KEY` lives on the
   same box as the database, so it protects against transport and storage corruption, not against
   Sagar. A genuinely independent signature means an offline Ed25519 key on a hardware token and a
   manual daily signing step. Not proposed for v1; the append-only remote plus the Telegram anchor
   is judged sufficient for a single-operator tool. Revisit if an external auditor is ever a real
   requirement rather than a hypothetical one.

5. **`sentence_excerpt` in `POLICY_BLOCK` detail.** It is the one fragment of message text stored in
   `audit_log` (capped at 200 characters), and it is what makes a six-month-old policy block
   readable. It is business content, but a contact's name could appear in it. Current resolution:
   keep it, and null it during erasure. The alternative — hash-only — makes the policy history
   almost useless. Flagging it because it is the one place D6 bends.

6. **Anchor cadence.** Daily. A high-value day (a large send batch) is unanchored for up to 24 h.
   Anchoring after every `CRITICAL` row would close that window at the cost of a Telegram message
   per approval, which would be ignored within a week and therefore worthless. Left at daily unless
   volume changes the calculus.

7. **`AUDITOR` role.** §11.9.1 and `/settings` assume a read-only `AUDITOR` role alongside `OWNER`.
   `12-security-model.md` owns the role list; if v1 ships with only `OWNER`, the explain view is
   owner-only and nothing else changes.

8. **Report re-rendering.** `data_rel_path` exists so an archived campaign can be re-rendered with a
   newer template. Nothing in this document specifies the UI for it, and it is not MVP.
   `03-html-report.md` may want it; the storage side is ready either way.
