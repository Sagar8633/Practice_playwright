# 14. Background jobs

This document decides how every slow, expensive or failure-prone piece of work in `business_radar`
runs without a message broker: the `jobs` and `job_runs` tables and their DDL, the atomic
claim-with-lease protocol that lets more than one worker thread share one SQLite file without ever
running the same job twice, the worker's lifecycle, shutdown and **resume from sleep**, the complete
registry of job types with their payloads, dedupe keys, retry policies and failure modes, the
cron-like schedule in IST **and its catch-up-on-launch rules for a machine that is not on 24/7**,
the token buckets and daily quota ceiling that keep a runaway campaign inside the free tier's daily
allowance, how a running campaign reports live progress without hammering the database, the
dead-letter surface and its alert rule, a write-by-write proof that `kill -9` in the middle of
`send_email` cannot produce a duplicate send or a lost record, and the complete `jobs` configuration
block. It covers spec §2 (the search job and
its campaign bookkeeping), §33 (the inbound response pipeline), §42 (the report archive and its
retention) and §43 (the daily report).

**Cross-references.** `01-data-model.md` carries the canonical schema file; the DDL for `jobs`,
`job_runs`, `job_schedules`, `rate_buckets` and `spend_ledger` printed here is the definition and
`01-data-model.md` must match it byte-for-byte. Tables owned elsewhere (`campaigns`, `businesses`,
`research_runs`, `opportunities`, `outreach_messages`, `outreach_events`, `outreach_approvals`,
`responses`, `handoffs`, `suppressions`, `report_exports`, `audit_log`) appear here only as a
"columns this document writes" contract. `05-outreach-workflow.md` owns the send eligibility gates
and the `outreach_messages` state machine that `send_email` obeys; `10-human-handoff.md` owns
`create_handoff`, `send_notification` and the SLA sweep semantics; `03-html-report.md` owns the
report template that `generate_report` renders.

**Changed for the free stack (binding, `_CONTEXT.md` §2).** Four decisions in this document were
written against a Linux VPS with a paid API and a webhook-capable public host. None of those three
things exists. The corrections are made in place and each is labelled where it appears:

| Was | Is | Where |
|---|---|---|
| A 1-2 GB Linux VPS, one `systemd` unit, a `systemd` timer for the doctor | **Sagar's Windows laptop.** A Startup shortcut or a Task Scheduler entry; the doctor is a second Task Scheduler entry | §14.2.1, §14.5.4, §14.12.4 |
| A process that is always up, so a cron slot at 07:35 was always observed | **A laptop that is closed at night and asleep in between.** Every schedule needs a catch-up-on-launch rule, decided per job type, and a worker that wakes from suspend must re-establish its leases before writing anything | §14.5.6, §14.9.1, §14.9.2 |
| `process_webhook_event`, fed by `POST /api/v1/webhooks/<provider>` | **Removed.** Nothing on the public internet can reach `127.0.0.1`. `poll_inbox` is the only automatic inbound path and it parses DSNs, unsubscribe mail and replies itself | §14.8.13, §14.8.14 |
| A daily spend ceiling in rupees over `SUM(cost_micros_inr)`, protecting a prepaid balance | **A daily quota ceiling in requests and tokens** against the Gemini free tier. Hitting it **pauses** research until the quota day rolls over; there is no bill to cap, only a 429 to stay under | §14.3.5, §14.10.4 |

---

## 14.1 The decisions, in one page

| # | Decision | Because |
|---|---|---|
| 1 | No broker. One `jobs` table in `data/radar.db`, claimed by `UPDATE ... RETURNING` under a lease. | `_CONTEXT.md` §2. Redis or RabbitMQ on a laptop that also has a browser and an IDE open costs more memory than the whole application, and adds a second Windows service that can be down while the database is up. |
| 2 | The worker is a **thread pool inside the same process that serves Flask/waitress**, started once at app creation. | §14.2.1. One process, one Startup entry, one log, one connection policy, no IPC. One thing for Sagar to see in Task Manager. |
| 3 | The pool is split into five **lanes** (`llm`, `io`, `export`, `notify`, `maint`) with independent thread counts and independent claim loops. | A 12-minute PDF render must not be able to delay a handoff notification. §14.2.2. |
| 4 | A job holds a **lease**, renewed by a heartbeat. The lease, not the job, has the short timeout. | A crashed process stops renewing; recovery is time-bounded without guessing how long work takes. §14.4.4. |
| 5 | **No attempt outlives `timeout_seconds`.** Long work chunks itself and re-enqueues with a cursor. | §14.5.2. A 40-minute running job is indistinguishable from a wedged one. |
| 6 | `dedupe_key` has a **permanent** unique index, not a partial one over live states. Repeating work puts its schedule slot in the key. | §14.6.2. A partial index lets a completed job be recreated; for `send_email` that is a second email. |
| 7 | Retries are the job runtime's business, not the SDK's. The `google-genai` client and the HTTP session are constructed with retries disabled. | An invisible SDK retry burns lease time, spends a request against the daily free-tier quota that nothing recorded, and never appears in `job_runs`. §14.7. |
| 8 | `send_email` is **at-most-once with a human tiebreak**, not at-least-once. `max_attempts = 1` at the transmit boundary; an indeterminate attempt stops and asks Sagar. | §14.13. Against a provider with no idempotency key and no authoritative lookup, exactly-once is not achievable; the correct failure direction for cold outreach is "did not send, here is a question", never "sent twice". |
| 9 | Job payloads carry **ids, not content**. No message bodies, no API keys, no personal data beyond an id. | `jobs` rows are pruned, printed in logs and dumped into support bundles. §14.6.3. |
| 10 | A daily **quota** ceiling **pauses research and says so**, and it resumes by itself tomorrow. It never silently degrades to a shorter prompt or fewer sources. | §14.10.4. On a free tier the ceiling is a 429, not a bill: the campaign is not in danger, it is just not finished today. Silent degradation would make two campaigns incomparable, which destroys §53's whole point. |
| 11 | Progress is served from process memory and campaign counter columns, never from a `COUNT(*)` per poll. | §14.11. |
| 12 | The worker cannot page itself when it is dead. A separate **Windows Task Scheduler** entry runs `main.py jobs doctor`. | §14.12.4. |
| 13 | **The machine is not on 24/7.** Every schedule carries a catch-up rule and a grace window, decided per job type, applied once at startup. | §14.9.2. A daily report missed by ten hours is worth running; a staleness sweep missed three nights should run once, not three times. |
| 14 | **Suspend is not a crash.** A worker resuming from sleep re-establishes each lease it still owns, or abandons the work. The fence in §14.4.4 makes "abandons" safe rather than merely intended. | §14.5.6. A laptop lid closes mid-job every day; treating that as a crash would either duplicate work or lose it. |
| 15 | **No inbound webhook exists.** `poll_inbox` is the only automatic inbound path, and it parses bounces, unsubscribe mail and replies itself. | §14.8.13. Nothing on the public internet can reach `127.0.0.1`. |

---

## 14.2 Execution model

### 14.2.1 Thread pool in the web process, not a separate process

Both were considered. The choice is the embedded pool, and the reasoning is deployment-shaped, not
taste-shaped.

| Criterion | Threads inside the waitress process | Separate `radar-worker` process |
|---|---|---|
| Memory on a laptop that is also Sagar's daily machine | One Python interpreter, one set of imports (`google-genai`, `openpyxl`, the Jinja2 environment and its compiled template cache). | Two interpreters importing the same heavy modules; the template cache is duplicated. Tens of megabytes for no functional gain, competing with a browser and an editor. |
| Operational surface | One Startup entry, one log file, one restart, one thing to be up, one icon in Task Manager. | Two entries, two logs, an ordering dependency, and a failure mode where the site is up and nothing is processing — the failure that is hardest to notice, and the one a solo operator will notice last. |
| SQLite contention | One process, one connection per thread, writers that are cooperating threads. `busy_timeout` almost never fires. | Two processes contend for the same WAL write lock with no shared knowledge; `SQLITE_BUSY` becomes routine and the retry logic has to be real. |
| Progress to the UI | The worker publishes to an in-process `EventBus`; the SSE endpoint subscribes. Zero database reads to stream progress. | Progress must round-trip through the database or a socket, so live progress costs a query per viewer per tick. §14.11 gets materially worse. |
| GIL | The work is IO-bound: HTTPS to the Gemini API, SMTP to Gmail, IMAP from Gmail, HTTP to Overpass and Nominatim, disk writes. Threads are the right tool. The CPU-bound exports are pushed to a subprocess anyway (§14.8.10). | Removes a GIL problem the workload does not have. |
| Blast radius | A worker thread that leaks memory or crashes a C extension takes the website down with it. **This is the real cost.** | Isolated. |
| Deploy | One restart drains the pool and restarts the site together (§14.5.4). | Can restart one without the other. |

The blast-radius row is the only serious argument for separation, and it is answered rather than
ignored: `export_pdf` — the one job that drives a browser engine and the one realistic source of an
OOM kill — runs in a `subprocess` with an explicit memory and wall-clock cap (§14.8.10), so the
component most likely to die is not the component serving the site.

**The escape hatch is built, not promised.** `radar/jobs.py` exposes `run_worker(cfg, lanes=...)`,
which the Flask app factory calls in-process when `jobs.worker.mode == "embedded"` and which
`main.py worker --lanes llm,export` calls as a standalone process when
`jobs.worker.mode == "standalone"`. The claim protocol in §14.4 is process-agnostic — it is correct
across threads, across processes and across machines with no change — so moving the `llm` and
`export` lanes onto their own process later is a config edit plus a second Startup entry, not a rewrite.
Exactly one topology is active at a time: `mode: standalone` makes the web process start no lanes.

```yaml
# config.yaml (excerpt; full block in §14.14.3)
jobs:
  worker:
    enabled: true
    mode: embedded          # embedded | standalone
    lanes:                  # in standalone mode, --lanes overrides this
      llm:    {threads: 2}
      io:     {threads: 3}
      export: {threads: 1}
      notify: {threads: 1}
      maint:  {threads: 1}
```

### 14.2.2 Lanes

One shared pool is wrong here for a specific reason: job durations in this system differ by three
orders of magnitude. `send_notification` takes 300 ms. `export_pdf` for a 400-business campaign takes
minutes. With one pool of four threads, four concurrent exports mean a demo request sits unnotified
for ten minutes — precisely the failure `10-human-handoff.md` exists to prevent.

| Lane | Threads | Job types | Why it is separate |
|---|---|---|---|
| `llm` | 2 | `research_business`, `assess_opportunity`, `draft_outreach`, `classify_response`, `score_calibration` | The only jobs that spend quota. Concurrency here is the throughput dial, bounded hard by the shared `llm.gemini.rpm` bucket in §14.10 — raising it past the bucket buys nothing but 429s. |
| `io` | 3 | `discover_city`, `score_business`, `send_email`, `poll_inbox`, `create_handoff`, `campaign_finalize`, `suppression_sync` | Short network and database work. Wants enough threads that one slow provider does not stall the rest. |
| `export` | 1 | `generate_report`, `export_csv`, `export_xlsx`, `export_pdf`, `daily_report` | CPU and memory heavy. Serialised on purpose: two simultaneous renders on a laptop that is also running a browser is how the machine starts swapping while Sagar is using it. |
| `notify` | 1 | `send_notification`, `handoff_sla_sweep`, `telegram_poll` | Must never queue behind anything. One thread is sufficient (the work is one HTTPS call) and it gives Telegram messages a natural global order. |
| `maint` | 1 | `backup_db`, `prune_logs`, `staleness_sweep` | Long, low priority, database-heavy. Isolated so a `VACUUM INTO` cannot occupy a thread the site needs. |

Each lane runs its own claim loop, so the claim query always filters on `lane`. A type is bound to
one lane by its registration decorator, and `lane` is denormalised onto the `jobs` row at enqueue
time so the claim query never joins to a registry.

### 14.2.3 The SQLite facts that shape all of this

| Fact | Consequence |
|---|---|
| WAL allows many concurrent readers and exactly **one** writer. | Every write transaction is short. No transaction is ever held open across a network call — in §14.13 that rule is the entire safety argument. |
| A `DEFERRED` transaction that reads first and writes later must **upgrade** its lock. If another connection wrote in between, the upgrade returns `SQLITE_BUSY` and the busy handler cannot help, because waiting would not refresh the stale snapshot. | Every claim, state change and counter update opens with `BEGIN IMMEDIATE`. This is not a micro-optimisation: deferred transactions in the claim path produce a `SQLITE_BUSY` that no timeout value fixes. |
| `sqlite3.Connection` is not safe to share across threads. | One connection per worker thread, created in that thread. `radar/db.py` exposes `connect()` plus a `threading.local` cache and closes connections at thread exit. |
| `PRAGMA busy_timeout` retries a *lock*, not a *transaction*. | `busy_timeout = 5000` everywhere, plus an application-level retry of the whole claim on `SQLITE_BUSY` with jitter (§14.4.3). |
| `RETURNING` needs SQLite 3.35 (2021-03). CPython 3.11 on Debian 12 links 3.40. | The `RETURNING` claim is the primary path; §14.4.3 gives the two-statement fallback and the runtime check that selects between them, because an old SQLite in a stray Python install on a Windows machine is a real possibility and a silently wrong claim is not acceptable. |
| Timestamps are fixed-width ISO-8601 UTC (`_CONTEXT.md` §2), so lexicographic order equals chronological order. | `run_after <= :now` and `lease_expires_at < :now` are plain string comparisons that index cleanly and stay correct verbatim against Postgres `timestamptz`. |

Connection settings applied by `radar/db.py::connect()` on every connection, worker connections
included:

```sql
PRAGMA journal_mode  = WAL;
PRAGMA foreign_keys  = ON;
PRAGMA busy_timeout  = 5000;
PRAGMA synchronous   = FULL;
PRAGMA wal_autocheckpoint = 1000;
```

`synchronous = FULL`, not the more common `NORMAL`. In WAL mode `NORMAL` can lose the last few
committed transactions when the *machine* loses power (a process crash is always safe under either
setting). In this system the last committed transaction is routinely "we are about to put an email on
the wire" (§14.13), and losing it converts a provable at-most-once send into a guess. The cost is one
extra `fsync` per commit on a box doing single-digit writes per second. Pay it.

### 14.2.4 Worker identity

```python
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{lane}:{thread_index}"
# SAMPLE: "SAGAR-LAPTOP:8421:llm:0"
```

Stored in `jobs.lease_owner`, `job_runs.worker_id` and `outreach_messages.worker_id`. It is
deliberately readable and deliberately **not** trusted for recovery: PIDs are reused, so a restarted
process can legitimately produce the same string. Recovery keys on `lease_expires_at` alone
(§14.4.5). The id exists so a log line and a `job_runs` row can be tied together during an incident,
and for nothing else.

---

## 14.3 Schema

### 14.3.1 `jobs`

```sql
-- radar/migrations/030_jobs.sql
CREATE TABLE jobs (
    id                TEXT PRIMARY KEY,                    -- job_...
    type              TEXT NOT NULL,                       -- registry key, see 14.8
    lane              TEXT NOT NULL DEFAULT 'io'
                        CHECK (lane IN ('llm','io','export','notify','maint')),
    payload           TEXT NOT NULL DEFAULT '{}'
                        CHECK (json_valid(payload) AND json_type(payload) = 'object'),

    state             TEXT NOT NULL DEFAULT 'QUEUED'
                        CHECK (state IN ('QUEUED','LEASED','RUNNING',
                                         'SUCCEEDED','FAILED','DEAD','CANCELLED')),
    priority          INTEGER NOT NULL DEFAULT 100
                        CHECK (priority BETWEEN 0 AND 1000),
    run_after         TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    attempts          INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts      INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),

    lease_owner       TEXT,
    lease_expires_at  TEXT,
    heartbeat_at      TEXT,

    last_error        TEXT,                                -- one line, human-readable first
    last_error_class  TEXT,                                -- see 14.7.1
    dedupe_key        TEXT,

    campaign_id       TEXT REFERENCES campaigns(id),
    business_id       TEXT REFERENCES businesses(id),
    parent_job_id     TEXT REFERENCES jobs(id),
    batch_id          TEXT,                                -- bat_..., groups a fan-out
    trace_id          TEXT NOT NULL,                       -- trc_..., survives re-enqueue

    cancel_requested  INTEGER NOT NULL DEFAULT 0
                        CHECK (cancel_requested IN (0,1)),

    progress_done     INTEGER NOT NULL DEFAULT 0,
    progress_total    INTEGER,
    progress_note     TEXT,

    timeout_seconds   INTEGER NOT NULL DEFAULT 300 CHECK (timeout_seconds > 0),
    result            TEXT CHECK (result IS NULL OR json_valid(result)),

    created_by        TEXT REFERENCES users(id),           -- NULL = system
    created_at        TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at        TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    started_at        TEXT,
    finished_at       TEXT,

    CHECK (state NOT IN ('LEASED','RUNNING')
           OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CHECK (state NOT IN ('SUCCEEDED','FAILED','DEAD','CANCELLED')
           OR finished_at IS NOT NULL),
    CHECK (state NOT IN ('SUCCEEDED','FAILED','DEAD','CANCELLED')
           OR (lease_owner IS NULL AND lease_expires_at IS NULL)),
    CHECK (attempts <= max_attempts),
    CHECK (state <> 'FAILED' OR last_error IS NOT NULL),
    CHECK (progress_total IS NULL OR progress_done <= progress_total)
);

-- The hot path. Partial, so the index holds only what a claim can see.
CREATE INDEX ix_jobs_claim
    ON jobs(lane, priority DESC, run_after)
    WHERE state = 'QUEUED';

-- The reaper's index.
CREATE INDEX ix_jobs_lease
    ON jobs(lease_expires_at)
    WHERE state IN ('LEASED','RUNNING');

-- Permanent, not partial. See 14.6.2 for why.
CREATE UNIQUE INDEX ux_jobs_dedupe
    ON jobs(dedupe_key) WHERE dedupe_key IS NOT NULL;

CREATE INDEX ix_jobs_campaign  ON jobs(campaign_id, state) WHERE campaign_id IS NOT NULL;
CREATE INDEX ix_jobs_business  ON jobs(business_id, type)  WHERE business_id IS NOT NULL;
CREATE INDEX ix_jobs_batch     ON jobs(batch_id, state)    WHERE batch_id IS NOT NULL;
CREATE INDEX ix_jobs_type_time ON jobs(type, state, finished_at);
CREATE INDEX ix_jobs_dead      ON jobs(finished_at)        WHERE state IN ('FAILED','DEAD');
CREATE INDEX ix_jobs_trace     ON jobs(trace_id);
```

Column notes that are not obvious from the name:

| Column | Note |
|---|---|
| `priority` | Higher runs first. Bands: 900 human-initiated and interactive (`draft_outreach`, an export Sagar clicked); 700 `send_email`, `send_notification`; 500 inbound (`poll_inbox`, `classify_response`, `create_handoff`); 300 campaign pipeline (`discover_city`, `research_business`); 100 scheduled maintenance. Ties break on `run_after`, then `created_at`. |
| `run_after` | The single scheduling primitive. A retry is a `QUEUED` row with a future `run_after`. So is a scheduled tick, and so is a deferred job. There is no `RETRY` or `SCHEDULED` state, which keeps the claim predicate to one condition. |
| `attempts` | Incremented **by the claim**, not by the handler. A job that crashes the whole process still shows a consumed attempt, which is what makes a poison job terminate instead of looping forever. |
| `heartbeat_at` | Written by the runtime, not the handler. Distinguishes "leased 90 seconds ago and working" from "leased 90 seconds ago and wedged". |
| `trace_id` | Minted once at the top of a causal chain and copied into every descendant. The `discover_city`, `research_business`, `score_business`, `generate_report` and `campaign_finalize` rows for one campaign share one `trc_`. `GET /api/v1/jobs?trace_id=...` reconstructs the whole history including retries. |
| `result` | Small JSON, capped at 8 KB by the runtime (truncated with `"_truncated": true`). It is for the UI and for debugging, never a data channel between jobs — jobs communicate through the tables they write. |
| `timeout_seconds` | Wall clock for one attempt, enforced by the runtime (§14.5.2), always set below the type's real-world worst case. Work that cannot fit chunks itself. |

### 14.3.2 The job state machine

```
                    claim (14.4.1)
      ┌──────────┐  ───────────────►  ┌──────────┐  dispatch   ┌──────────┐
      │  QUEUED  │                    │  LEASED  │ ──────────► │ RUNNING  │
      └──────────┘  ◄───────────────  └──────────┘             └──────────┘
        ▲   ▲   ▲   release / reap          │                    │ │ │ │
        │   │   │                           │ reap               │ │ │ └─► SUCCEEDED
        │   │   └── Retry / Defer (future run_after)              │ │ └───► FAILED
        │   └────── manual retry from FAILED                      │ └─────► DEAD
        └────────── revive from DEAD (forced, audited)            └───────► CANCELLED
```

```sql
-- radar/migrations/031_job_state_transitions.sql
CREATE TABLE job_state_transitions (
    from_state TEXT NOT NULL,
    to_state   TEXT NOT NULL,
    note       TEXT NOT NULL,
    PRIMARY KEY (from_state, to_state)
);

INSERT INTO job_state_transitions (from_state, to_state, note) VALUES
    ('QUEUED',   'LEASED',    'claimed by a worker'),
    ('QUEUED',   'CANCELLED', 'cancelled before it ran'),
    ('LEASED',   'RUNNING',   'handler dispatched'),
    ('LEASED',   'QUEUED',    'released on shutdown, or lease reaped'),
    ('LEASED',   'CANCELLED', 'cancel_requested seen before dispatch'),
    ('LEASED',   'FAILED',    'reaped with no attempts left'),
    ('LEASED',   'DEAD',      'unknown type, or unparseable payload'),
    ('RUNNING',  'SUCCEEDED', 'handler returned Done'),
    ('RUNNING',  'QUEUED',    'handler returned Retry or Defer'),
    ('RUNNING',  'FAILED',    'permanent error, or attempts exhausted'),
    ('RUNNING',  'DEAD',      'poison payload, or a type whose retry is unsafe'),
    ('RUNNING',  'CANCELLED', 'handler observed ctx.should_stop() and stopped'),
    ('FAILED',   'QUEUED',    'manual retry from the jobs console'),
    ('DEAD',     'QUEUED',    'manual revive, forced, writes an audit_log row');

CREATE TRIGGER trg_jobs_transition
BEFORE UPDATE OF state ON jobs
WHEN NEW.state <> OLD.state
 AND NOT EXISTS (SELECT 1 FROM job_state_transitions t
                 WHERE t.from_state = OLD.state AND t.to_state = NEW.state)
BEGIN
    SELECT RAISE(ABORT, 'illegal jobs.state transition');
END;
```

The two states people conflate, stated plainly:

| State | Meaning | Auto-retried | In the dead-letter view | How it leaves |
|---|---|---|---|---|
| `FAILED` | Every attempt was used, or the error was classified permanent. Running it again would probably fail the same way, but running it again is **safe**. | No | Yes | `POST /api/v1/jobs/<id>/retry` — one click, no ceremony. |
| `DEAD` | Running it again is not safe or not possible: the type is missing from the registry (a rolled-back deploy), the payload does not parse, or the type's `on_lease_expiry` policy is `RECONCILE` and reconciliation could not decide. That last case is `send_email`, §14.13. | No | Yes, in a separate band | `POST /api/v1/jobs/<id>/revive` with a typed reason, writing an `audit_log` row. For `send_email` the revive route is closed entirely; resolution runs through `POST /api/v1/outreach/messages/<message_id>/resolve-indeterminate`. |

A job waiting to retry is `QUEUED` with a future `run_after` and a populated `last_error`. The console
renders that as "attempt 2 of 3, next at 14:12 IST" — the state name is not what the human reads.

### 14.3.3 `job_runs`

One row per attempt. `jobs` holds current truth; `job_runs` holds history, and it is what the failure
rate alert (§14.12.3) and the quota accounting (§14.10.4) read.

```sql
-- radar/migrations/032_job_runs.sql
CREATE TABLE job_runs (
    id                 TEXT PRIMARY KEY,                   -- run_...
    job_id             TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    attempt_no         INTEGER NOT NULL CHECK (attempt_no >= 1),
    type               TEXT NOT NULL,                      -- denormalised on purpose
    lane               TEXT NOT NULL,
    worker_id          TEXT NOT NULL,

    started_at         TEXT NOT NULL,
    finished_at        TEXT,
    duration_ms        INTEGER,

    outcome            TEXT
                         CHECK (outcome IS NULL OR outcome IN
                           ('SUCCEEDED','RETRY','DEFERRED','FAILED','DEAD',
                            'CANCELLED','TIMEOUT','LEASE_EXPIRED')),
    error_class        TEXT,                               -- 14.7.1
    error_message      TEXT,
    error_detail       TEXT CHECK (error_detail IS NULL OR json_valid(error_detail)),

    -- quota and provider accounting, written by ctx.spend()
    model_id           TEXT,
    prompt_version     TEXT,
    input_tokens       INTEGER,
    output_tokens      INTEGER,
    thinking_tokens    INTEGER,                            -- Gemini thoughts_token_count; charged
    cached_tokens      INTEGER,                            -- implicit-cache hit, 06 6.13.7
    quota_units        INTEGER,                            -- requests charged to the day; see 14.3.5
    provider           TEXT,
    provider_request_id TEXT,                              -- google-genai resp.response_id, or the SMTP id

    UNIQUE (job_id, attempt_no)
);

CREATE INDEX ix_job_runs_job    ON job_runs(job_id, attempt_no);
CREATE INDEX ix_job_runs_recent ON job_runs(type, started_at);
CREATE INDEX ix_job_runs_failed ON job_runs(type, finished_at)
    WHERE outcome IN ('FAILED','TIMEOUT','LEASE_EXPIRED');
CREATE INDEX ix_job_runs_quota  ON job_runs(started_at) WHERE quota_units IS NOT NULL;
```

**Changed for the free stack.** These four columns used to be `cache_read_tokens`,
`cache_write_tokens`, `cost_micros_inr` and an index named `ix_job_runs_cost`. There is no cost and
there is no explicit cache to write (`06-message-engine.md` §6.13.7), so what is worth recording per
attempt is what the free tier meters: requests (`quota_units`), the token counts including thinking
tokens, and whether an implicit cache hit reduced the tokens charged. `01-data-model.md`'s `032`
must follow — see this document's Open questions.

`LEASE_EXPIRED` is written by the **reaper**, not by the dead worker — the dead worker cannot write
anything, which is the point. The reaper closes the orphaned run row it finds open
(`finished_at IS NULL`), so no attempt is left dangling and a hard crash becomes a visible row rather
than a silent gap in the history.

`provider_request_id` is populated from `resp.response_id` on every Gemini call, and from the SMTP
server's accepted-message id on every send. It is the only thing that makes a conversation about one
specific bad response possible, and it costs one column.

### 14.3.4 `job_schedules`

```sql
-- radar/migrations/033_job_schedules.sql
CREATE TABLE job_schedules (
    id                TEXT PRIMARY KEY,                    -- sch_...
    type              TEXT NOT NULL,                       -- must exist in the registry
    enabled           INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),

    -- Exactly one of these two is used.
    cron_expr         TEXT,                                -- 5-field, minute resolution
    every_seconds     INTEGER CHECK (every_seconds IS NULL OR every_seconds >= 30),
    tz                TEXT NOT NULL DEFAULT 'Asia/Kolkata',

    payload           TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload)),
    priority          INTEGER NOT NULL DEFAULT 100,
    jitter_seconds    INTEGER NOT NULL DEFAULT 0 CHECK (jitter_seconds >= 0),
    catch_up          TEXT NOT NULL DEFAULT 'SKIP'
                        CHECK (catch_up IN ('SKIP','ONCE','ALL')),
    catch_up_grace_minutes INTEGER NOT NULL DEFAULT 0
                        CHECK (catch_up_grace_minutes >= 0),
                        -- 0 = no grace, run a missed ONCE/ALL slot however late it is.
                        -- >0 = run the missed slot only if (now - slot) <= this many minutes;
                        --      otherwise skip to the next occurrence. 14.9.2.

    last_tick_at      TEXT,                                -- last slot materialised, UTC
    last_job_id       TEXT REFERENCES jobs(id),
    note              TEXT NOT NULL,

    created_at        TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at        TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK ((cron_expr IS NULL) <> (every_seconds IS NULL))
);

CREATE UNIQUE INDEX ux_job_schedules_type ON job_schedules(type);
```

`catch_up_grace_minutes` is **new, and it exists because the deploy target changed**. On an
always-on VPS a missed slot meant the process had crashed, which was rare and short. On Sagar's
laptop a missed slot is Tuesday: the machine was shut at 21:00 and opened at 09:40, and every
overnight schedule was missed by design. `catch_up` alone answers "how many of the missed slots
should run"; it cannot answer "is a slot that is eleven hours stale still worth running", and for a
laptop that is the question that decides everything. §14.9.2 gives the value per job.

Seeded by `034_seed_job_schedules.sql` with the rows in §14.9.1 and editable from `/settings` (jobs
tab), with an `audit_log` row per edit. One schedule per type is a deliberate restriction: two
schedules for one type means two dedupe-key namespaces, and a class of bug where a job silently stops
running because the other schedule's key won the unique index.

### 14.3.5 `rate_buckets` and `spend_ledger`

**Changed for the free stack.** `spend_ledger` keeps its name — `_CONTEXT.md` §2 and
`01-data-model.md` both use it, and renaming a table across the pack to make a word more accurate is
a bad trade — but it no longer records money. It records **quota units**: one request against the
day's request allowance, plus the token count that request consumed. One column changes name
(`cost_micros_inr` -> `quota_units`) and the view's output columns change with it; everything else,
including every index, is byte-identical to the earlier version.

```sql
-- radar/migrations/035_rate_buckets.sql
CREATE TABLE rate_buckets (
    name            TEXT PRIMARY KEY,                      -- 'llm.gemini.rpm', 'email.day', ...
    capacity        REAL NOT NULL CHECK (capacity > 0),    -- burst size, in tokens
    refill_per_sec  REAL NOT NULL CHECK (refill_per_sec >= 0),
    tokens          REAL NOT NULL CHECK (tokens >= 0),
    updated_at      TEXT NOT NULL
                      DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    last_empty_at   TEXT,                                  -- drives the throttling banner
    note            TEXT NOT NULL
);

-- radar/migrations/036_spend_ledger.sql
CREATE TABLE spend_ledger (
    id              TEXT PRIMARY KEY,                      -- spn_...
    at              TEXT NOT NULL
                      DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    day_ist         TEXT NOT NULL,                         -- 'YYYY-MM-DD' in Asia/Kolkata
    kind            TEXT NOT NULL CHECK (kind IN ('LLM','EMAIL','SEARCH','OTHER')),
    job_id          TEXT REFERENCES jobs(id),
    job_run_id      TEXT REFERENCES job_runs(id),
    campaign_id     TEXT REFERENCES campaigns(id),
    business_id     TEXT REFERENCES businesses(id),

    model_id        TEXT,
    units           INTEGER,                               -- tokens for LLM (in+out+thinking),
                                                           -- 1 for an email, 1 for a discovery call
    quota_units     INTEGER NOT NULL CHECK (quota_units >= 0),
                                                           -- REQUESTS charged against the day's
                                                           -- ceiling. 1 per Gemini call, 1 per
                                                           -- email send, 1 per Overpass/Nominatim
                                                           -- call. Was cost_micros_inr.
    detail          TEXT CHECK (detail IS NULL OR json_valid(detail))
);

CREATE INDEX ix_spend_day      ON spend_ledger(day_ist, kind);
CREATE INDEX ix_spend_campaign ON spend_ledger(campaign_id, day_ist);

CREATE VIEW v_spend_today AS
SELECT day_ist,
       SUM(quota_units)                                          AS total_requests,
       SUM(CASE WHEN kind = 'LLM'   THEN quota_units ELSE 0 END) AS llm_requests,
       SUM(CASE WHEN kind = 'EMAIL' THEN quota_units ELSE 0 END) AS email_requests,
       SUM(CASE WHEN kind = 'LLM'   THEN units       ELSE 0 END) AS llm_tokens,
       COUNT(*)                                                  AS entries
  FROM spend_ledger
 WHERE day_ist = strftime('%Y-%m-%d', 'now', '+330 minutes')
 GROUP BY day_ist;
```

`+330 minutes` is IST as a fixed offset. India has had no DST since 1945, so the offset is constant
and this stays correct; the Python side still uses `zoneinfo.ZoneInfo("Asia/Kolkata")` so that SQL
and code agree if that ever changes, and a test asserts they agree across a sample of timestamps.

**The IST day and the quota day are not the same day, and the code must not pretend they are.**
Google's free-tier request-per-day counter resets on **Pacific time**, not IST. `v_spend_today` is
grouped by IST because every other number in this system — the daily report, the send window, quiet
hours — is IST, and a ledger Sagar cannot line up against his own day is useless. But the *ceiling*
in §14.10.4 is our own conservative reserve (`llm.daily_request_cap`, default 200 against a published
250), specifically so that a few hours of misalignment between the two day boundaries cannot turn
"we are near our reserve" into "Google is refusing us". The authoritative signal that the real
ceiling was hit is a 429, never our own arithmetic; our arithmetic exists to make 429 rare.

Quota units are **integer counts**. Never a float, never `REAL`, never a formatted string — the same
rule the money version had, for the same reason: a ceiling that is wrong at the fourth decimal place
is a ceiling nobody trusts. `units` (tokens) is also an integer and is recorded even though tokens
are not the binding ceiling, because the day a Gemini prompt grows past a token limit, the ledger is
the only place that will show it happening.

### 14.3.6 Id prefixes used here

| Table / concept | Prefix | Source |
|---|---|---|
| `jobs` | `job_` | extension; matches `05-outreach-workflow.md` §5.5.1, which already prints a `job_` id |
| `job_runs` | `run_` | extension |
| batch group (`jobs.batch_id`) | `bat_` | extension |
| trace (`jobs.trace_id`) | `trc_` | extension |
| `job_schedules` | `sch_` | extension |
| `spend_ledger` | `spn_` | extension |

All are 26-character Crockford base32 ULIDs from `radar/ids.py` per `_CONTEXT.md` §2. `rate_buckets`
is keyed by a stable name instead, because there are ten of them (§14.10.1) and a name is what both
the config file and the log line want to say.

### 14.3.7 Columns this document writes but does not own

| Table | Columns written by a job | By |
|---|---|---|
| `campaigns` | `status`, `started_at`, `finished_at`, `paused_reason`, `n_discovered`, `n_researched`, `n_qualified`, `n_skipped`, `n_verified`, `n_contacted` | §14.8.1-§14.8.6 |
| `businesses` | `status`, `research_status`, `last_researched_at` | `discover_city`, `research_business`, `staleness_sweep` |
| `research_runs`, `research_findings`, `sources`, `finding_sources` | inserts | `research_business` |
| `opportunities`, `opportunity_modules` | inserts, `is_current` flips | `score_business`, `assess_opportunity` |
| `outreach_drafts`, `outreach_messages`, `outreach_events` | see `05-outreach-workflow.md` | `draft_outreach`, `send_email`, `poll_inbox` (delivery outcomes parsed out of DSNs, §14.8.13) |
| `responses` | inserts, `classification`, `confidence`, `confidence_pct`, `classifier_model_id`, `classifier_prompt_version` | `poll_inbox`, `classify_response` |
| `handoffs` | inserts, `notify_count`, `telegram_message_id` | `create_handoff`, `send_notification` |
| `suppressions` | inserts | `classify_response` (OPT_OUT), `poll_inbox` (hard bounce, `mailto:` unsubscribe — `09-response-classification.md` §9.4 rule `E9`), `suppression_sync` |
| `report_exports` | inserts, `status`, `path`, `bytes`, `sha256` | `generate_report`, `export_*`, `daily_report` |
| `audit_log` | inserts | every job that changes something a human would later want explained |

`report_exports` is used by five job types, so the columns they depend on are pinned here as a
contract even though `03-html-report.md` owns the table:

```sql
-- CONTRACT ONLY. Owned by 03-html-report.md.
-- report_exports(
--   id                  TEXT PRIMARY KEY,     -- rex_...
--   campaign_id         TEXT REFERENCES campaigns(id),  -- NULL for daily_report
--   fmt                 TEXT CHECK (fmt IN ('HTML','CSV','XLSX','PDF','DAILY_HTML')),
--                                         -- 01-data-model.md renames 11's `kind` to `fmt`;
--                                         -- the payload key below stays "kind", it is not a column
--   scope               TEXT,                 -- JSON: the filter set the export was built from
--   path                TEXT,                 -- relative to data/reports/
--   filename            TEXT,                 -- the §5 download name
--   bytes               INTEGER,
--   sha256              TEXT,
--   row_count           INTEGER,
--   status              TEXT CHECK (status IN ('PENDING','READY','FAILED','PURGED')),
--   generated_by_job_id TEXT REFERENCES jobs(id),
--   generated_at        TEXT,
--   expires_at          TEXT,                 -- NULL = keep forever (the default for HTML)
--   error               TEXT
-- )
```

---

## 14.4 The claim protocol

### 14.4.1 The claim query

One statement, inside `BEGIN IMMEDIATE`, per lane, per idle worker thread.

```sql
-- radar/jobs.py :: _claim_returning
WITH candidate AS (
    SELECT id
      FROM jobs
     WHERE state    = 'QUEUED'
       AND lane     = :lane
       AND run_after <= :now
       AND attempts  < max_attempts
       AND cancel_requested = 0
     ORDER BY priority DESC, run_after ASC, created_at ASC
     LIMIT 1
)
UPDATE jobs
   SET state            = 'LEASED',
       lease_owner      = :worker_id,
       lease_expires_at = :lease_until,
       heartbeat_at     = :now,
       attempts         = attempts + 1,
       updated_at       = :now
 WHERE id = (SELECT id FROM candidate)
   AND state = 'QUEUED'                    -- re-check, inside the write
RETURNING id, type, lane, payload, attempts, max_attempts,
          campaign_id, business_id, batch_id, trace_id,
          timeout_seconds, dedupe_key, priority;
```

Bindings: `:lane` from the loop, `:now = strftime('%Y-%m-%dT%H:%M:%SZ','now')` computed in Python (so
the same instant is used for the lease arithmetic), `:lease_until = now + jobs.worker.lease_seconds`,
`:worker_id` from §14.2.4. An empty `RETURNING` set means "nothing to do" — the loop sleeps on its
wake-up channel (§14.5.3) and tries again.

Four parts of that statement are load-bearing:

| Clause | Why it is there |
|---|---|
| `AND attempts < max_attempts` | The `CHECK (attempts <= max_attempts)` constraint means a claim that would exceed the ceiling aborts the transaction rather than failing quietly. This clause makes the query skip such a row instead, so the constraint never actually fires. Belt and braces: the reaper is what moves an exhausted row to `FAILED`. |
| `ORDER BY priority DESC, run_after ASC, created_at ASC` | Deterministic order. Without `created_at` as the final tie-break, two jobs enqueued in the same second with equal priority claim in arbitrary order, and the campaign progress bar goes backwards on a re-run because the city order changed. |
| `LIMIT 1` | One job per claim. Batch claiming (`LIMIT 4`) is faster and wrong here: a worker holding four leases that dies loses four jobs' worth of lease time, and for `send_email` it multiplies the indeterminate window by four. |
| `AND state = 'QUEUED'` in the `UPDATE` | The re-check. On SQLite it is redundant — the whole statement runs under one write lock — but it is what makes the query correct when the same SQL is run on Postgres, where the CTE reads a snapshot that another transaction may already have changed. See §14.4.6. |

### 14.4.2 The race this prevents

Without the claim being one atomic statement, the natural implementation is "SELECT a queued job,
then UPDATE it to mine". Under WAL, readers never block, so two worker threads run the SELECT
concurrently and both see the same row.

```
  time    worker A (llm:0)                    worker B (llm:1)              jobs row job_01H…SEND
  ────────────────────────────────────────────────────────────────────────────────────────────
  t0      BEGIN DEFERRED                                                    state=QUEUED
  t1      SELECT id … LIMIT 1  -> job_01H…    BEGIN DEFERRED                state=QUEUED
  t2                                          SELECT id … -> job_01H…       state=QUEUED
  t3      UPDATE … lease_owner='A'                                          state=LEASED owner=A
  t4      COMMIT                                                            committed
  t5                                          UPDATE … lease_owner='B'      state=LEASED owner=B
  t6                                          COMMIT                        committed
  t7      handler runs: transmits email       handler runs: transmits email  TWO EMAILS SENT
```

`t5` succeeds because the naive `UPDATE` says `WHERE id = ?` and the row still exists. The lost
update is invisible: nothing errors, nothing logs, and the only artifact is a prospect receiving the
same cold email twice — the single behaviour `_CONTEXT.md` §3 is built to make impossible.

With the query in §14.4.1:

```
  time    worker A (llm:0)                    worker B (llm:1)              jobs row
  ────────────────────────────────────────────────────────────────────────────────────────────
  t0      BEGIN IMMEDIATE (write lock held)                                 state=QUEUED
  t1      claim … RETURNING -> 1 row          BEGIN IMMEDIATE -> waits      state=LEASED owner=A
  t2      COMMIT (lock released)              …acquires lock                committed
  t3                                          claim: candidate CTE finds
                                              no row with state='QUEUED'
                                              -> 0 rows, RETURNING empty    unchanged
  t4      handler runs                        loop sleeps, retries          ONE EMAIL SENT
```

Three properties fall out of it, and each is worth naming because a future refactor will be tempted
to break one:

1. **Serialisation comes from `BEGIN IMMEDIATE`, not from the CTE.** A `DEFERRED` transaction would
   take a read lock at `t0` and try to upgrade at the `UPDATE`; with two of them, the upgrade returns
   `SQLITE_BUSY` immediately and `busy_timeout` cannot rescue it, because the busy handler is not
   invoked for a deadlock it cannot break by waiting.
2. **The claim increments `attempts` in the same statement.** A separate `UPDATE jobs SET attempts…`
   after the claim opens a window in which a crash loses the attempt count, and a poison job then
   loops forever.
3. **Nothing in the handler re-reads the row to decide whether it owns the job.** Ownership is
   established once, by a successful `RETURNING`. Any "am I still the owner?" check later would be a
   TOCTOU bug wearing a safety costume — the correct guard is the fenced write in §14.4.4.

### 14.4.3 The fallback for SQLite without `RETURNING`, and `SQLITE_BUSY`

```python
# radar/jobs.py
_HAS_RETURNING = sqlite3.sqlite_version_info >= (3, 35, 0)

def claim(conn: sqlite3.Connection, lane: str, worker_id: str,
          *, lease_seconds: int, now: str) -> ClaimedJob | None:
    """Take exactly one job, or return None. Never raises on contention."""
    for attempt in range(CLAIM_BUSY_RETRIES):          # 4
        try:
            conn.execute("BEGIN IMMEDIATE")
            if _HAS_RETURNING:
                row = conn.execute(_CLAIM_RETURNING, params).fetchone()
            else:
                cand = conn.execute(_CANDIDATE_SQL, params).fetchone()
                if cand is None:
                    conn.execute("COMMIT")
                    return None
                cur = conn.execute(_CLAIM_UPDATE_SQL, {**params, "id": cand["id"]})
                if cur.rowcount != 1:                  # someone else won it
                    conn.execute("COMMIT")
                    return None
                row = conn.execute(_RELOAD_SQL, {"id": cand["id"]}).fetchone()
            conn.execute("COMMIT")
            return ClaimedJob.from_row(row) if row else None
        except sqlite3.OperationalError as exc:
            conn.execute("ROLLBACK")
            if "locked" not in str(exc) and "busy" not in str(exc):
                raise
            time.sleep(random.uniform(0.02, 0.08) * (2 ** attempt))
    log.warning("claim on lane %s gave up after %d busy retries", lane, CLAIM_BUSY_RETRIES)
    return None
```

The fallback path is correct for the same reason the primary path is: the whole thing sits inside one
`IMMEDIATE` transaction, and `cur.rowcount != 1` is the same re-check the `RETURNING` version does in
its `WHERE`. It is slower by one round trip and that is all. A startup log line states which path is
in use, because "why is this slower than it was yesterday" should be answerable from the log.

Giving up after four busy retries returns `None`, not an exception: a busy database is a reason to
wait, not a reason to log an error every second. Persistent busy-ness surfaces through the
`jobs.queue_stalled` alert in §14.12.3, which is the honest place for it.

### 14.4.4 Heartbeats, lease renewal, and fenced writes

`lease_seconds` (default 120) is not how long a job may run. It is how long the rest of the system
waits before deciding the worker is gone. The runtime renews it from a single daemon thread per lane
pool:

```python
# every jobs.worker.heartbeat_seconds (default 20), for each RUNNING job this process owns
UPDATE jobs
   SET lease_expires_at = :now_plus_lease,
       heartbeat_at     = :now,
       progress_done    = :done,          -- only when it changed, see 14.11.1
       progress_note    = :note
 WHERE id = :job_id
   AND lease_owner = :worker_id
   AND state = 'RUNNING';
```

`AND lease_owner = :worker_id` is a **fence**. If this worker was reaped while it was blocked on a
slow HTTPS call, the row now belongs to somebody else and the renewal updates zero rows. The
heartbeat thread counts that: two consecutive zero-row renewals mean this thread has lost its lease,
and it sets the job's cancellation event so the handler stops at its next `ctx.should_stop()` check
and returns without writing anything. The same fence appears on every terminal write
(`_finish_ok`, `_finish_retry`, `_finish_fail`), so a zombie handler physically cannot overwrite the
work of the worker that legitimately took over.

| Timer | Default | Relationship |
|---|---|---|
| `heartbeat_seconds` | 20 | Must be well under `lease_seconds`, so a transient database busy period does not cost a lease. |
| `lease_seconds` | 120 | 6 heartbeats of slack. Also the worst-case delay before a crashed job is recoverable. |
| `reaper_interval_seconds` | 30 | How often expired leases are swept. Worst-case recovery latency is `lease_seconds + reaper_interval_seconds` = 150 s. |
| `timeout_seconds` (per type) | 60-1800 | Enforced by the runtime, independent of the lease. A job can be inside its lease and still be over its timeout. |

### 14.4.5 Lease expiry recovery

The reaper runs in the `maint` lane's loop every `reaper_interval_seconds`, and also once at startup
before any lane begins claiming (§14.5.1). It is three statements in one `IMMEDIATE` transaction, and
the order matters.

```sql
-- (1) Close the orphaned attempt rows so the history shows the crash.
UPDATE job_runs
   SET finished_at = :now,
       outcome     = 'LEASE_EXPIRED',
       error_class = 'LEASE_EXPIRED',
       error_message = 'worker stopped renewing the lease',
       duration_ms = CAST((julianday(:now) - julianday(started_at)) * 86400000 AS INTEGER)
 WHERE finished_at IS NULL
   AND job_id IN (SELECT id FROM jobs
                   WHERE state IN ('LEASED','RUNNING')
                     AND lease_expires_at < :now);

-- (2) Jobs whose type says a blind retry is safe, and that have attempts left.
UPDATE jobs
   SET state = 'QUEUED',
       lease_owner = NULL,
       lease_expires_at = NULL,
       run_after = :requeue_at,                 -- now + backoff(attempts)
       last_error_class = 'LEASE_EXPIRED',
       last_error = 'lease expired (worker ' || COALESCE(lease_owner,'?') || '); requeued'
 WHERE state IN ('LEASED','RUNNING')
   AND lease_expires_at < :now
   AND attempts < max_attempts
   AND type IN (SELECT type FROM json_each(:requeue_types));

-- (3) Everything else expired: out of attempts, or a type that must not blind-retry.
UPDATE jobs
   SET state = CASE WHEN type IN (SELECT type FROM json_each(:reconcile_types))
                    THEN 'DEAD' ELSE 'FAILED' END,
       lease_owner = NULL,
       lease_expires_at = NULL,
       finished_at = :now,
       last_error_class = 'LEASE_EXPIRED',
       last_error = 'lease expired with no safe automatic recovery'
 WHERE state IN ('LEASED','RUNNING')
   AND lease_expires_at < :now
   AND id NOT IN (SELECT id FROM jobs
                   WHERE state IN ('LEASED','RUNNING') AND lease_expires_at < :now
                     AND attempts < max_attempts
                     AND type IN (SELECT type FROM json_each(:requeue_types)));
```

`:requeue_types` and `:reconcile_types` are JSON arrays built from the registry at startup, so the
policy lives with the handler and not in a SQL literal.

| `on_lease_expiry` | Behaviour | Types |
|---|---|---|
| `REQUEUE` | Back to `QUEUED` with backoff. Safe because the handler is idempotent: re-running writes the same rows or detects its own prior output. | `discover_city`, `research_business`, `score_business`, `assess_opportunity`, `campaign_finalize`, `generate_report`, `export_csv`, `export_xlsx`, `export_pdf`, `draft_outreach`, `poll_inbox`, `classify_response`, `create_handoff`, `daily_report`, `staleness_sweep`, `suppression_sync`, `backup_db`, `prune_logs`, `handoff_sla_sweep`, `telegram_poll`, `score_calibration` |
| `RECONCILE` | To `DEAD`, and a reconciliation pass decides what actually happened before anything is retried. | `send_email` (§14.13) |
| `FAIL` | Straight to `FAILED`. Retrying is harmless but pointless because the trigger has passed. | `send_notification` — a page about a 40-minute-old event that a later sweep will re-raise anyway (`10-human-handoff.md` §10.12) |

After (2) the reaper enqueues a `send_notification` for each job it moved to `FAILED`/`DEAD`, subject
to the alert rules in §14.12.3, and logs one line per reaped job at `WARNING` naming the job id, type
and previous `lease_owner`. A silent reaper is a reaper nobody believes exists.

It also calls `request_reconcile()` whenever it moved at least one `RECONCILE` type to `DEAD`, so the
`maint` lane runs §14.13.4 on its next iteration instead of leaving an unresolved send until the next
launch. On a laptop that stays up all afternoon, "the next launch" is tomorrow, and an indeterminate
send that Sagar cannot see until tomorrow is the one failure §14.13 exists to make visible today.

### 14.4.6 The Postgres port

`_CONTEXT.md` §2 requires that nothing here become a wall later. The claim is the only query with a
concurrency contract, so it is the only one that needs a documented translation:

```sql
-- Postgres form. Same shape, same re-check, one extra clause.
WITH candidate AS (
    SELECT id FROM jobs
     WHERE state = 'QUEUED' AND lane = $1 AND run_after <= $2
       AND attempts < max_attempts AND cancel_requested = false
     ORDER BY priority DESC, run_after ASC, created_at ASC
     LIMIT 1
     FOR UPDATE SKIP LOCKED            -- <- the only addition
)
UPDATE jobs SET state='LEASED', ... WHERE id = (SELECT id FROM candidate) AND state='QUEUED'
RETURNING ...;
```

`FOR UPDATE SKIP LOCKED` gets concurrency that SQLite achieves by serialising the whole write. The
redundant `AND state = 'QUEUED'` in the `UPDATE` becomes load-bearing there. Everything else — the
lease columns, the reaper, the fences, the backoff — is portable as written. No application query in
this document uses `json_each`, `julianday`, `strftime` or `RETURNING` outside `radar/jobs.py` and
`radar/db.py`, so the port surface is two modules.

---

## 14.5 The worker

### 14.5.1 Startup

Ordered, and the order is the design:

| # | Step | If it fails |
|---|---|---|
| 1 | Run migrations (`schema_version`), then `PRAGMA integrity_check` if `data/radar.db` was not cleanly closed. | Refuse to start. A worker on a half-migrated schema writes rows that violate constraints introduced by the next migration. |
| 2 | Validate the registry against the database: every distinct `type` in a live (`QUEUED`/`LEASED`/`RUNNING`) `jobs` row must exist in the registry, and every `job_schedules.type` must exist. | Log `ERROR` naming each unknown type, move those live rows to `DEAD` with `last_error_class='UNKNOWN_TYPE'`, and continue. This is what a rollback looks like, and it must be loud rather than fatal. |
| 3 | Verify pinned model ids resolve: `client.models.get(model=model_id)` for each id in `llm.models`, and record the resolved `version` so §14.10.4's ledger and `09`'s `classifier_model_id` agree on what "gemini-2.5-flash" meant today. | Log `ERROR` and disable the `llm` lane; every other lane starts. The site stays usable, research and drafting stop, and `/settings` shows why. A laptop that opened without a network connection hits this every morning, so it is a disabled lane and a banner, never a refusal to boot. |
| 4 | Reconcile `rate_buckets` rows against `jobs.limits` config; insert missing buckets at full capacity, update `capacity`/`refill_per_sec` for changed ones, leave `tokens` alone. | Fatal only if the config is malformed. |
| 5 | Run the reaper once, synchronously, **before any lane starts claiming** (§14.4.5). | Fatal — an unreaped lease from the previous process would sit for `lease_seconds` doing nothing. |
| 6 | Run the `send_email` reconciliation pass over every `DEAD` `send_email` job and every `outreach_messages` row that has a `SEND_ATTEMPT` event and no terminal event (§14.13.4). | Log and continue; unresolved rows stay `DEAD` and appear on `/outreach` in the indeterminate band. |
| 7 | **Catch-up-on-launch:** materialise missed schedule ticks per each schedule's `catch_up` policy **and its `catch_up_grace_minutes` window** (§14.9.2). On this deploy target this step runs with real work to do almost every morning, not only after a crash. | Log and continue. |
| 8 | Start the lane pools, the heartbeat thread, and the reaper timer. | — |
| 9 | Log one `INFO` line: worker id, lanes and thread counts, claim path (`RETURNING` or fallback), SQLite version, reaped count, reconciled count, **hours since the previous shutdown and how many schedule slots were caught up versus skipped**. | — |

The last two fields in step 9 are not decoration. On a machine that is off half the day, "what did
this launch decide to skip" is the first question when something did not happen, and the answer has
to be in the log rather than reconstructed from `job_schedules.last_tick_at` afterwards.

Under the Flask app factory, steps 1-9 run exactly once. The guard is an `os.environ` sentinel plus a
`threading.Lock`, because the Werkzeug reloader in development imports the module twice and waitress
does not; both must produce one pool.

```python
# radar/web/app.py
def create_app(cfg: Config) -> Flask:
    app = Flask(__name__)
    ...
    if cfg.get("jobs.worker.enabled", True) and cfg.get("jobs.worker.mode") == "embedded":
        if os.environ.get("WERKZEUG_RUN_MAIN") != "false":     # not the reloader's parent
            app.extensions["radar_worker"] = jobs.start_worker(cfg)
    return app
```

### 14.5.2 The lane loop

```python
def _lane_loop(cfg: Config, lane: str, index: int, bus: EventBus, stop: threading.Event) -> None:
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{lane}:{index}"
    conn = db.connect(cfg)                       # this thread's connection, for the whole life
    idle_backoff = Backoff(base=0.25, cap=cfg.get(f"jobs.worker.lanes.{lane}.poll_seconds", 2.0))

    while not stop.is_set():
        job = claim(conn, lane, worker_id, lease_seconds=LEASE, now=utcnow_iso())
        if job is None:
            wake.wait(idle_backoff.next())       # 14.5.3
            continue
        idle_backoff.reset()
        _run_one(conn, job, worker_id, cfg, bus, stop)
    conn.close()
```

`_run_one` is where the contract with a handler lives:

```python
def _run_one(conn, job, worker_id, cfg, bus, stop) -> None:
    handler = REGISTRY.get(job.type)
    if handler is None:
        _finish(conn, job, worker_id, state="DEAD",
                error_class="UNKNOWN_TYPE", message=f"no handler for {job.type!r}")
        return
    try:
        payload = handler.payload_model(**json.loads(job.payload))     # dataclass validation
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        _finish(conn, job, worker_id, state="DEAD",
                error_class="BAD_PAYLOAD", message=str(exc))
        return

    run_id = _open_run(conn, job, worker_id)                 # 1: LEASED -> RUNNING + job_runs insert
    ctx = JobContext(conn=conn, job=job, run_id=run_id, worker_id=worker_id,
                     cfg=cfg, bus=bus, stop=stop,
                     deadline=time.monotonic() + job.timeout_seconds)
    HEARTBEAT.register(ctx)
    try:
        result = handler.fn(ctx, payload)                    # 2: the actual work
    except Exception as exc:                                 # noqa: BLE001 - classified below
        result = _classify_exception(exc, job, handler)      # 14.7.1
    finally:
        HEARTBEAT.unregister(ctx)
    _apply_result(conn, job, run_id, worker_id, result)      # 3: one transaction, terminal write
```

Three enforcement details:

- **Timeout.** `ctx.deadline` is monotonic. Handlers check it through `ctx.should_stop()` at chunk
  boundaries, and every network client is constructed with a per-request timeout smaller than the
  remaining budget (`ctx.remaining_seconds()`). There is no thread-kill: Python cannot safely
  interrupt a thread, and pretending otherwise produces a corrupted half-write. A handler that
  ignores its deadline entirely is caught by the lease + reaper, one level up. The registry's
  `timeout_seconds` is therefore a *contract with the handler*, and the lease is the *enforcement*.
- **Cancellation.** `ctx.should_stop()` is `stop.is_set() or ctx.cancelled` where `ctx.cancelled` is
  set by the heartbeat thread when it observes `cancel_requested = 1` or a lost fence (§14.4.4).
  Handlers return `Cancelled()` and write nothing.
- **Payload validation happens before `RUNNING`.** A payload that does not parse is `DEAD` without
  ever consuming a `job_runs` row, so "bad deploy" and "bad provider" never look alike in the history.

### 14.5.3 The wake-up channel

Polling every 2 seconds means a click on CONFIRM & SEND waits up to 2 seconds before anything
happens, and it means 43,200 pointless queries per lane per day on an idle box. Both are fixed by an
in-process condition variable:

```python
class Wake:
    """Cross-thread nudge so an enqueue in a Flask request thread wakes an idle lane."""
    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._lanes: set[str] = set()

    def poke(self, lane: str) -> None:
        with self._cv:
            self._lanes.add(lane)
            self._cv.notify_all()

    def wait(self, lane: str, timeout: float) -> bool: ...
```

`enqueue()` calls `wake.poke(lane)` **after** the enclosing transaction commits — never inside it, or
a lane wakes, claims nothing (the row is not visible yet), and goes back to sleep having burned a
query. The commit hook lives in `radar/db.py::transaction()` as an `on_commit` callback list.

The timed `wait` is still there and still matters: it is what makes the design work in standalone
mode, where a poke cannot cross the process boundary. Idle poll interval backs off from 0.25 s to the
lane's `poll_seconds` and resets on every successful claim, so a busy queue polls tightly and an idle
one settles to one query per lane per `poll_seconds`.

### 14.5.4 Graceful shutdown

**Changed for the free stack: the target is Windows, and the signals are different.** There is no
`systemd` and no `SIGTERM`. What Windows actually delivers to a console process, and what each one
means here:

| Event | Delivered as | Grace Windows allows | What it means |
|---|---|---|---|
| Ctrl-C in the console | `SIGINT` (`CTRL_C_EVENT`) | unlimited | Sagar is stopping it deliberately |
| The console window is closed | `CTRL_CLOSE_EVENT` via `SetConsoleCtrlHandler` | ~5 s, then the process is killed | Same intent, much less time |
| Log off | `CTRL_LOGOFF_EVENT` | short, not configurable by us | Same |
| Shut down / restart | `CTRL_SHUTDOWN_EVENT` | short, not configurable by us | Same |
| **Lid closed / Sleep / Hibernate** | **nothing** | — | **Not a shutdown at all.** The process is frozen and will resume. §14.5.6 |

Two consequences, and the second one is the important one:

1. `radar/jobs.py::install_signal_handlers()` registers `signal.SIGINT` **and** a
   `SetConsoleCtrlHandler` callback (via `ctypes`, no new dependency) for `CTRL_CLOSE_EVENT`,
   `CTRL_LOGOFF_EVENT` and `CTRL_SHUTDOWN_EVENT`. All four route to the one handler below.
2. **`shutdown_grace_seconds` cannot be 25 on the close/logoff/shutdown paths.** Windows gives a
   console app a few seconds and then kills it; a 25-second grace period means every shutdown becomes
   the `kill -9` case in §14.5.5. So the grace is split: `jobs.worker.shutdown_grace_seconds` (25)
   applies to `SIGINT`, where Sagar is watching and nothing is racing us, and
   `jobs.worker.os_shutdown_grace_seconds` (**4**) applies to the three OS-initiated events. On the
   short path steps 3-6 are skipped entirely and the handler goes straight to step 7, because
   releasing the leases is the only thing that is both fast and worth more than the in-flight work.

The handler itself:

```
SIGTERM
  │
  ├─ 1. stop.set()                     lanes stop claiming immediately; nothing new is taken
  ├─ 2. wake.poke(all lanes)           idle threads wake at once instead of sleeping out their timer
  ├─ 3. for each RUNNING job:          ctx.cancelled is NOT set — in-flight work gets its chance
  │        heartbeats keep renewing
  ├─ 4. join(threads, timeout = jobs.worker.shutdown_grace_seconds)   default 25 s
  ├─ 5. for threads still alive:       ctx.cancelled = True; handlers stop at their next checkpoint
  ├─ 6. join(threads, timeout = 5)
  ├─ 7. for any job still LEASED/RUNNING owned by this worker:
  │        UPDATE jobs SET state='QUEUED', lease_owner=NULL, lease_expires_at=NULL,
  │               run_after=:now, last_error='released on shutdown'
  │         WHERE lease_owner = :worker_id AND state IN ('LEASED','RUNNING')
  │           AND type IN (:requeue_types)          -- send_email is excluded, see below
  ├─ 8. flush the EventBus, close SSE streams with a final `event: shutdown`
  └─ 9. log: released N, abandoned M, ran for T, exit cause (SIGINT | CLOSE | LOGOFF | SHUTDOWN)
```

On the OS-initiated paths, steps 3-6 are skipped: `stop.set()`, `wake.poke()`, then step 7 and step
9. Four seconds is enough for one `UPDATE` inside one `BEGIN IMMEDIATE` and one log line, and not
enough for anything else.

Step 7 is the difference between a clean deploy and a two-minute stall: explicitly released jobs are
claimable immediately by the new process, instead of waiting out `lease_seconds`. It excludes
`RECONCILE` types on purpose — a `send_email` that was mid-transmit when SIGTERM arrived must go
through reconciliation (§14.13.4), not back into the queue, and the released-vs-abandoned counts in
step 9 make that visible.

`shutdown_grace_seconds = 25` is chosen for the `SIGINT` case: Sagar pressed Ctrl-C, nothing is
racing us, and 25 seconds lets a `send_email` finish rather than go to reconciliation. There is no
`TimeoutStopSec` to stay under any more, which is the one way this target is easier than the old one.

**How the app is started, and restarted.** Two supported forms, both plain Windows, neither of them a
service (a Windows Service needs a service wrapper, an install step and Administrator rights, and
buys nothing a solo operator on his own laptop needs):

```bat
:: deploy/radar-start.cmd  -- placed in shell:startup, or run by the Task Scheduler entry below
@echo off
cd /d D:\radar
call .venv\Scripts\activate.bat
:loop
python main.py serve
echo [%DATE% %TIME%] radar exited with %ERRORLEVEL%, restarting in 5s >> logs\supervisor.log
timeout /t 5 /nobreak > nul
goto loop
```

```
:: deploy/radar-task.xml  -- schtasks /Create /XML deploy\radar-task.xml /TN radar
   Trigger 1 : At log on of <user>
   Trigger 2 : On workstation unlock          <- covers "I closed the lid, opened it, and forgot"
   Settings  : StartWhenAvailable = true      <- a missed logon trigger still fires
               DisallowStartIfOnBatteries = false
               StopIfGoingOnBatteries      = false
               RestartOnFailure: every 5 minutes, 3 times
               MultipleInstancesPolicy = IgnoreNew   <- the startup guard in 14.5.1 is the backstop
```

The `:loop` in the `.cmd` is the `Restart=on-failure` replacement and it is deliberately dumber than
`systemd` was: no backoff cap, no failure counting, no `OnFailure=` unit. What `systemd` gave that
this does not is a restart-storm limiter, so the limiter moves into the app — `main.py serve` refuses
to start and exits `2` (which the loop treats as fatal and stops on) if `logs/supervisor.log` shows
more than `jobs.worker.max_restarts_per_hour` (default 6) restarts in the last hour. A crash loop
that eats a laptop battery overnight is a worse failure than being down.

`MultipleInstancesPolicy = IgnoreNew` matters because "at log on" and "on workstation unlock" will
both fire in a single morning. Two triggers, one process, and §14.5.1's `os.environ` sentinel plus
`threading.Lock` as the last line of defence.

### 14.5.5 Recovery after a hard crash

Task Manager "End task", a battery that ran out, a blue screen, or Windows killing the process four
seconds into a shutdown. Nothing runs on the way down; there is no chance to release anything. The
recovery is entirely time-based and entirely in the database.

| t | What is true |
|---|---|
| `t0` | Process dies. Job `job_…A1` is `RUNNING`, `lease_owner='SAGAR-LAPTOP:8421:llm:0'`, `lease_expires_at = t0 + 100s` (last renewed 20 s ago), `job_runs` row open with `finished_at IS NULL`. |
| `t0 + 5s` | `radar-start.cmd`'s `:loop` (§14.5.4) starts a new process, new PID. If the machine itself died, this row instead reads "next time Sagar opens the laptop", and every row below shifts with it — the recovery is correct either way because it keys on the lease, not on the clock. |
| `t0 + 6s` | Startup step 5: the reaper runs synchronously. `job_…A1`'s lease has **not** expired yet, so it is untouched. Lanes start; they cannot claim it because its state is `RUNNING`. |
| `t0 + 100s` | The lease expires. |
| `t0 + ≤130s` | The reaper's next pass closes the open `job_runs` row with `LEASE_EXPIRED`, and — because `research_business` is a `REQUEUE` type with attempts left — sets `job_…A1` back to `QUEUED` with `run_after = now + backoff(2)`. |
| `t0 + ~135s` | A lane claims it as attempt 2. The handler re-runs; its idempotency (§14.8) means the partial work from attempt 1 is either detected and reused or harmlessly rewritten. |

Worst-case recovery latency is `lease_seconds + reaper_interval_seconds` = 150 s with the defaults.
That is the number to change if it ever feels wrong, and the only cost of lowering it is that a
worker blocked on a slow provider for longer than `lease_seconds` without heartbeating would be
reaped from under itself — which the fence in §14.4.4 makes safe, but wasteful.

**Why the startup reaper does not simply requeue everything owned by "a dead-looking worker".** It is
tempting to say "any job whose `lease_owner` names this hostname and a PID that is not running is
crashed, requeue it now" and skip the 150 seconds. That check is wrong on a machine that runs two
workers (the standalone escape hatch in §14.2.1), wrong when PIDs are reused, and wrong in a container
where PID 1 is always alive. Time is the only signal that is correct in every topology, so time is
the only signal used.

### 14.5.6 Suspend and resume: the laptop lid

**New for the free stack.** On the old target this case did not exist; on this one it happens most
days. Sagar closes the lid mid-campaign, the machine suspends, and two hours later it wakes up with
the same process, the same threads, the same open sockets and a `jobs` table full of leases that
expired ninety minutes ago.

**Suspend is not a crash and must not be treated as one.** The process did not die; it was frozen.
Every thread resumes exactly where it was, including a thread that was one line away from writing a
`SENT` row. Treating that as a crash would either lose the write or, far worse for `send_email`,
repeat it.

**Detection: measure the sleep, do not ask the OS.** The heartbeat thread (§14.4.4) already wakes
every `heartbeat_seconds`. It records the wall-clock time before and after each wait and compares the
elapsed wall clock against the interval it asked for:

```python
# radar/jobs.py :: _heartbeat_loop
SUSPEND_FACTOR = 4          # jobs.worker.suspend_detect_factor

intended = cfg.get("jobs.worker.heartbeat_seconds", 20)
before = time.time()
stop.wait(intended)
elapsed = time.time() - before
if elapsed > intended * SUSPEND_FACTOR:
    # Either the machine was suspended or this thread was starved for 80+ seconds.
    # We do not need to know which: the correct response is identical, and it is the
    # conservative one. Do NOT try to distinguish them with monotonic vs wall clock -
    # whether CPython's monotonic() advances across suspend is platform- and
    # version-dependent on Windows, and a recovery path must not rest on that.
    on_resume(elapsed_seconds=elapsed)
```

**Recovery: re-establish, or abandon.** For every job this worker still believes it owns:

```sql
-- radar/jobs.py :: reestablish_lease   (inside BEGIN IMMEDIATE, one row at a time)
UPDATE jobs
   SET lease_expires_at = :now_plus_lease,
       heartbeat_at     = :now
 WHERE id           = :job_id
   AND lease_owner  = :worker_id           -- the fence from 14.4.4, unchanged
   AND state        = 'RUNNING'
RETURNING id;
```

The fence does all the work, and it does it without a single new concept:

| Outcome | What it means | What the worker does |
|---|---|---|
| One row returned | Nobody reclaimed the job while we were asleep. On a single-worker laptop this is the **normal** case, because the reaper lives in this same process and was asleep too | Renew, and let the handler continue. The job is not restarted, not re-attempted, and `attempts` is untouched |
| Zero rows returned | Somebody else took it — a second worker (§14.2.1's escape hatch), or a restarted process whose startup reaper swept the expired lease | Set `ctx.cancelled`. The handler stops at its next `ctx.should_stop()` and returns without writing. §14.4.4's fence on every terminal write makes this safe even if it does not check |

**But the in-flight network call is already dead.** A TCP connection to Gemini, to Gmail's SMTP
server or to Overpass does not survive two hours of suspend; the socket comes back readable and
broken, or hangs until its timeout. So re-establishing the lease keeps the *job*, not the *attempt*:

| Handler state at suspend | On resume |
|---|---|
| Between steps, no socket open | Continues. This is the case the lease renewal is for |
| Blocked on an HTTP/SMTP/IMAP call | The call fails with a connection error or times out, is classified `NETWORK` (§14.7.1), and the attempt retries normally — **inside the lease we just re-established**, so no other worker races it |
| `send_email`, past the `SEND_ATTEMPT` event and unsure whether the SMTP transaction completed | **Never retried.** `on_lease_expiry='RECONCILE'`: the job goes to `DEAD` and the reconciliation pass in §14.13.4 decides, or asks Sagar. This is the whole reason `send_email` is at-most-once, and a sleeping laptop is now its most likely trigger — more likely than the crash the rule was written for |

**And the schedule is stale.** `on_resume()` finishes by calling `materialise_due_schedules()` with
the catch-up rules in §14.9.2, exactly as startup step 7 does. A resume is a small launch: the same
question ("what did we miss, and is it still worth doing") has the same answer, so it has one
implementation.

```python
def on_resume(*, elapsed_seconds: float) -> None:
    """The machine was asleep. Keep what we can still legitimately own; give up the rest.

    Order matters and is the reverse of shutdown's: leases first (so that a reaper in
    another process cannot take work we are about to continue), then the schedule
    catch-up (which may enqueue), then the buckets.
    """
    log.warning("resumed after %.0f s of wall clock; re-establishing %d leases",
                elapsed_seconds, len(owned))
    for job_id in owned:
        if not reestablish_lease(job_id):
            cancel(job_id, reason="LEASE_LOST_ACROSS_SUSPEND")
    materialise_due_schedules(conn, now=utcnow())        # 14.9.2
    request_reconcile()                                 # 14.13.4, run by the maint lane
    # rate_buckets need nothing: 14.10.2's lazy refill computes from updated_at, so a
    # two-hour sleep leaves every bucket correctly full with no catch-up code at all.
```

The last comment is worth its line. The lazy-refill design in §14.10.2 was chosen so a worker that
was down for an hour would find a full bucket; on this target that stopped being a nice property and
became a required one, and it needed no change to keep.

A `send_notification` is **not** raised on resume. A laptop waking up is not an incident, and an
operator who is paged every morning stops reading pages. The `WARNING` line above is the record.

---

## 14.6 Enqueue and dedupe

### 14.6.1 `enqueue()`

```python
# radar/jobs.py
@dataclass(frozen=True)
class EnqueueResult:
    job_id: str
    created: bool          # False => an existing row won the dedupe key
    existing_state: str | None


def enqueue(
    conn: sqlite3.Connection,
    type: str,
    payload: dict[str, Any] | None = None,
    *,
    dedupe_key: str | None = None,
    priority: int | None = None,           # default from the registry
    run_after: datetime | None = None,     # default: now
    max_attempts: int | None = None,       # default from the registry
    timeout_seconds: int | None = None,    # default from the registry
    campaign_id: str | None = None,
    business_id: str | None = None,
    parent_job_id: str | None = None,
    batch_id: str | None = None,
    trace_id: str | None = None,           # default: parent's, else a new trc_
    created_by: str | None = None,         # users.id when a human clicked something
    on_conflict: Literal["ignore", "error", "bump"] = "ignore",
) -> EnqueueResult:
    """Put one row in `jobs`. Idempotent when dedupe_key is set."""
```

Rules the implementation enforces:

| Rule | Reason |
|---|---|
| `type` must be in the registry, or `enqueue` raises `UnknownJobType` **at enqueue time**. | A typo becomes a 500 on the request that caused it, not a `DEAD` row discovered next week. |
| `lane`, `priority`, `max_attempts` and `timeout_seconds` default from the registry entry, never from the caller's memory. | One place to change a job's cost profile. |
| `payload` is validated against the handler's payload dataclass before insert. | Same reason. The failure is the caller's, so it belongs at the caller. |
| The insert participates in the **caller's** transaction. `enqueue` never commits. | This is what makes "write the row and enqueue the job that acts on it" atomic. `classify_response` writing a `responses` row and enqueueing `create_handoff` in one transaction is the difference between a lead being handed off and a lead being lost. |
| `wake.poke(lane)` is registered as an `on_commit` callback, never called inline. | §14.5.3. |
| On unique-index violation of `ux_jobs_dedupe`: `ignore` returns the existing row with `created=False`; `error` raises `DuplicateJob`; `bump` lowers `run_after` to `min(existing.run_after, requested)` **only if the existing row is `QUEUED`** and returns `created=False`. | `bump` exists for one case: a manual "run it now" on a scheduled job. |

### 14.6.2 Dedupe key grammar

The unique index is over **all** rows, not just live ones. This is the important choice in the whole
table design, so here is the argument in full.

A partial index (`WHERE state IN ('QUEUED','LEASED','RUNNING')`) is the common pattern and it means
"only one live job with this key". It permits a completed job to be enqueued again with the same key
— which is exactly what you want for a nightly sweep and exactly what you must never allow for
`send_email`. Since the table cannot have two policies, it takes the strict one, and repeating work
makes its key unique by including its slot:

| Job type | `dedupe_key` | Notes |
|---|---|---|
| `discover_city` | `discover_city:{campaign_id}:{city_slug}:{cursor_page}` | Each page of a paginated discovery is one job. |
| `research_business` | `research_business:{business_id}:{research_run_id}` | The run id is minted before the job is enqueued, so a retry-by-hand cannot start a second run against the same business. |
| `score_business` | `score_business:{business_id}:{research_run_id}` | |
| `assess_opportunity` | `assess_opportunity:{business_id}:{research_run_id}` | |
| `campaign_finalize` | `campaign_finalize:{campaign_id}:{tick_iso}` | Self-rescheduling; the tick makes each poll unique. |
| `generate_report` | `generate_report:{campaign_id}:{scope_hash}` | `scope_hash` = sha256 of the canonicalised filter JSON. Re-running with identical filters returns the existing export instead of building a byte-identical file twice. |
| `export_csv` / `export_xlsx` / `export_pdf` | `export_{fmt}:{campaign_id}:{scope_hash}` | Same. |
| `draft_outreach` | `draft_outreach:{selection_id}` | One draft per selection; a regenerate creates a new `selection`-scoped draft with an explicit suffix `:{regen_no}`. |
| `send_email` | `send_email:{message_id}` | **The permanent one.** One `outreach_messages` row can have at most one send job in the entire history of the database. §14.13. |
| `poll_inbox` | `poll_inbox:{slot_iso}` | Slot is the schedule tick, minute resolution. Per-message idempotency is a different mechanism and lives on `responses(provider_message_id)` — §14.8.13. |
| `classify_response` | `classify_response:{response_id}` | |
| `create_handoff` | `create_handoff:{response_id}` | Matches the `NOT EXISTS` insert in `10-human-handoff.md` §10.6.3, one layer up. |
| `send_notification` | `send_notification:{kind}:{subject_id}:{reason}:{window_slot}` | `window_slot` = the `notify.dedupe_window_minutes` bucket, so two pages inside the window collapse to one row. |
| `daily_report` | `daily_report:{day_ist}` | |
| `staleness_sweep` / `suppression_sync` / `backup_db` / `prune_logs` | `{type}:{slot_iso}` | |
| `handoff_sla_sweep` | `handoff_sla_sweep:{slot_iso}` | |
| `telegram_poll` | `telegram_poll` (no slot) | Deliberately keyless-in-time: exactly one such job may exist, ever. It re-arms itself by resetting its own row rather than enqueuing a new one — the one exception, and it is documented on the handler. |
| `score_calibration` | `score_calibration:{month_ist}` | |

**Interaction with pruning.** `prune_logs` deletes `SUCCEEDED` job rows older than
`jobs.retention.success_days` (default 30), which frees their dedupe keys. That is safe for every key
above **except** `send_email:{message_id}`, whose guarantee must outlive any retention window. Two
things make it safe anyway:

1. `prune_logs` never deletes rows whose `type` is in `jobs.retention.never_prune` (default
   `["send_email"]`).
2. Even if it did, the real uniqueness guarantee for a send is
   `ux_om_idempotency` on `outreach_messages.idempotency_key` (`05-outreach-workflow.md` §5.3.5),
   which lives in a table nothing prunes. The job key is defence in depth, not the depth.

### 14.6.3 What may be in a payload

| Allowed | Not allowed |
|---|---|
| Row ids (`biz_…`, `msg_…`, `cmp_…`), enum values, small integers, ISO timestamps, cursors, `scope_hash`, booleans | Message bodies, subject lines, email addresses, phone numbers, contact names, API keys or tokens, raw research text, anything from a `.env` |

Two reasons, both concrete: `jobs.payload` is printed in the jobs console and in log lines at DEBUG,
and `prune_logs` decides retention by age rather than by sensitivity, so anything in a payload has an
undefined lifetime. Under DPDP purpose-limitation (`_CONTEXT.md` §4) a contact email sitting in a job
payload is a second, unmanaged copy of personal data.

**There is no longer an exception.** The old one was `process_webhook_event`, which had to carry the
provider's raw POST body in its payload because that body was the only copy. With webhooks gone
(§14.8.14) nothing puts foreign content in a payload at all: `poll_inbox` writes the raw MIME part
to a file under `data/inbound/` and puts the *path* in `responses.body_html_path`, never in a job
payload. `prune_logs` deletes those files on `jobs.retention.inbound_days` (default 14) instead of
blanking a payload.

That is a strict improvement for `_CONTEXT.md` §4's purpose-limitation, and it is worth naming why:
an inbound reply contains the sender's address, signature block and often a phone number. In the
webhook design that sat in `jobs.payload`, a column printed in the jobs console and dumped into
support bundles. Now it sits in one file with a known deletion date and one database column that
points at it.

---

## 14.7 Retries

### 14.7.1 Error classification

The handler does not decide whether to retry. It raises, or it returns a `JobResult`; the runtime
classifies. One table, used by `_classify_exception`:

| `error_class` | Raised by / detected as | Retry | Notes |
|---|---|---|---|
| `RATE_LIMIT` | `google.genai.errors.ClientError` with `code == 429`, SMTP 421/450 throttling | Yes, and **not against `max_attempts`** | Honours `retry-after` / `RetryInfo` when present; otherwise the standard backoff. Also drains the corresponding bucket to zero (§14.10.3). **Distinguish two 429s:** a per-minute limit is a short defer; a per-day limit is `QUOTA_EXHAUSTED` below. The `RetryInfo.retryDelay` and the error's `status`/`message` naming `PerDay` are what separate them, and when the response is ambiguous the code treats it as per-day, because guessing "per-minute" on a per-day wall produces a retry storm against an exhausted quota. |
| `QUOTA_EXHAUSTED` | A 429 whose detail names a per-day limit, or `jobs.quota.daily_request_cap` reached locally | Yes, and **not against `max_attempts`** | `Defer(run_after = next quota window)`. §14.10.4. This is the free tier's characteristic failure and it is not an error: research pauses and resumes tomorrow. |
| `OVERLOADED` | `google.genai.errors.ServerError` with `code == 503` (`UNAVAILABLE`) | Yes | The model is temporarily out of capacity; a longer floor (30 s) than a plain 5xx. Common on a free tier at peak hours. |
| `PROVIDER_5XX` | `google.genai.errors.ServerError` with `code >= 500`, SMTP 5xx that is not a permanent recipient failure | Yes | |
| `NETWORK` | `httpx.ConnectError`, `requests.ConnectionError`, `smtplib.SMTPServerDisconnected`, `imaplib.IMAP4.abort`, `socket.timeout` | Yes | **The common case on this deploy target**, and not because anything is broken: a laptop moves between networks, sleeps (§14.5.6), and loses Wi-Fi. Retrying is the whole answer. |
| `TIMEOUT` | `httpx.ReadTimeout`, our own deadline | Yes | `job_runs.outcome = 'TIMEOUT'`. |
| `DB_BUSY` | `sqlite3.OperationalError` matching busy/locked | Yes, short backoff | Should be rare; if it is not, §14.12.3 alerts. |
| `BAD_REQUEST` | `ClientError` with `code == 400` (`INVALID_ARGUMENT`), SMTP 5xx permanent | **No** -> `FAILED` | A malformed request will be malformed again. |
| `AUTH` | `ClientError` with `code in (401, 403)` (`UNAUTHENTICATED`, `PERMISSION_DENIED`), `smtplib.SMTPAuthenticationError`, IMAP `AUTHENTICATIONFAILED` | **No** -> `FAILED`, and raises the `credentials` alert immediately | An API key or a Gmail App Password expired or was revoked. Retrying 3 times just delays the page — and a revoked App Password is the single most likely credential failure in this build, because it happens silently when the Google account's 2-Step Verification is re-run. |
| `NOT_FOUND` | `ClientError` with `code == 404`, a referenced row that has vanished | **No** -> `FAILED` | |
| `CONTACT_LEAK` | `radar.messages.ContactLeak` (`06-message-engine.md` §6.13.0) | **No** -> `FAILED`, immediately, no retry | A `business_contacts` value reached an LLM prompt assembly. Retrying would attempt the same disclosure a second time. The job fails loudly and the draft is not written. |
| `POLICY_BLOCK` | The claim-policy engine refused the draft | **No** -> `FAILED` | The message is `POLICY_BLOCKED`; the job's work is done and its outcome is "blocked". |
| `ELIGIBILITY_BLOCK` | `check_send_eligibility()` returned a block at SEND stage | **No** -> `FAILED` | Opt-out, duplicate, frequency cap. Never retried: the block is the correct answer. |
| `QUOTA_CEILING` | §14.10.4, our own `daily_request_cap` reached before the provider's | Deferred, not retried | `Defer(run_after = next quota window)`; does not consume an attempt. Distinct from `QUOTA_EXHAUSTED` above only in who said no first — us or Google. Both defer to the same place. |
| `BUCKET_EMPTY` | §14.10.3 | Deferred | `Defer(run_after = now + bucket.eta())`; does not consume an attempt. |
| `SEND_WINDOW` | §14.9.3 | Deferred | `Defer(run_after = next window open)`; does not consume an attempt. |
| `BAD_PAYLOAD` | Payload does not parse | **No** -> `DEAD` | |
| `UNKNOWN_TYPE` | Not in the registry | **No** -> `DEAD` | |
| `INDETERMINATE` | §14.13 | **No** -> `DEAD` | Only `send_email` produces it. |
| `LEASE_EXPIRED` | Written by the reaper | Per §14.4.5 | |
| `BUG` | Any other exception | Yes, up to `max_attempts` | Full traceback into `job_runs.error_detail`; one line into `jobs.last_error`. A `BUG` that exhausts attempts pages via §14.12.3, because an unclassified exception in this system is a design gap, not weather. |

`Defer` deserves its own line: it exists so that "I cannot run right now for a policy reason" is not
recorded as a failure. Deferred jobs do not consume attempts, do not appear in the failure-rate
alert, and do not accumulate `last_error` noise. The runtime implements it by writing
`attempts = attempts - 1` alongside `state = 'QUEUED'` in the same transaction that sets the new
`run_after`, and by writing `job_runs.outcome = 'DEFERRED'` so the history still shows what happened.

### 14.7.2 Backoff

```python
def backoff_seconds(attempt: int, *, base: float, cap: float, floor: float = 0.0) -> float:
    """Exponential with full jitter. attempt is 1-based."""
    raw = min(cap, base * (2 ** (attempt - 1)))
    return max(floor, random.uniform(0, raw))
```

Full jitter rather than fixed or "equal jitter": when a provider comes back after an outage, twelve
queued research jobs with the same deterministic backoff hit it in the same millisecond and get
429ed together. Full jitter spreads them across the window at the cost of an occasionally shorter
first retry, which is a trade this workload can afford.

| Profile | `base` | `cap` | `floor` | Applied to |
|---|---|---|---|---|
| `fast` | 2 s | 60 s | — | `io` and `notify` lane types |
| `standard` | 15 s | 900 s | — | `llm` lane types, exports |
| `provider` | 30 s | 1800 s | 30 s | `OVERLOADED`, and any `RATE_LIMIT` with no `retry-after` |
| `retry_after` | — | — | — | `RATE_LIMIT` with a `retry-after` header: `run_after = now + header + uniform(0, 5)` |
| `maint` | 300 s | 3600 s | — | `backup_db`, `prune_logs`, sweeps |

`max_attempts` per type is in the registry table (§14.8.0). The general shape: 1 for anything that
transmits to a third party under a human approval, 3 for LLM and network work, 5 for cheap idempotent
sweeps that are better late than missing.

---

## 14.8 The job registry

### 14.8.0 Registration, and the whole registry at a glance

```python
# radar/jobs.py
@job(
    "research_business",
    lane="llm",
    priority=300,
    max_attempts=3,
    timeout_seconds=900,
    backoff="standard",
    on_lease_expiry="REQUEUE",
    payload_model=ResearchBusinessPayload,
)
def research_business(ctx: JobContext, p: ResearchBusinessPayload) -> JobResult:
    ...
```

The decorator is the single source of truth: `enqueue()` reads defaults from it, the reaper builds
its `:requeue_types` / `:reconcile_types` arrays from it, `/settings` renders it, and a startup
assertion fails the boot if a `job_schedules.type` has no registration.

"Spends quota" replaces the old "Spends money" column: there is no bill on this stack, only a daily
request allowance (§14.10.4).

| Type | Lane | Prio | Timeout | Attempts | Lease expiry | Trigger | Spends quota |
|---|---|---|---|---|---|---|---|
| `discover_city` | io | 300 | 300 s | 3 | REQUEUE | Campaign start, one per city per page | Overpass / Nominatim calls |
| `research_business` | llm | 300 | 900 s | 3 | REQUEUE | Fan-out from `discover_city` | Yes |
| `score_business` | io | 320 | 60 s | 3 | REQUEUE | After `research_business` | No |
| `assess_opportunity` | llm | 310 | 300 s | 3 | REQUEUE | After `score_business` | Yes |
| `campaign_finalize` | io | 200 | 60 s | 5 | REQUEUE | Self-rescheduling while a campaign runs | No |
| `generate_report` | export | 400 | 600 s | 3 | REQUEUE | Campaign completion; manual regenerate | No |
| `export_csv` | export | 900 | 300 s | 3 | REQUEUE | Sagar clicks EXPORT | No |
| `export_xlsx` | export | 900 | 600 s | 3 | REQUEUE | Sagar clicks EXPORT | No |
| `export_pdf` | export | 900 | 900 s | 2 | REQUEUE | Sagar clicks EXPORT | No |
| `draft_outreach` | llm | 900 | 300 s | 3 | REQUEUE | `POST /api/v1/outreach/prepare` | Yes |
| `send_email` | io | 700 | 120 s | **1** | **RECONCILE** | Approval + queue | Gmail daily send cap |
| `poll_inbox` | io | 500 | 180 s | 3 | REQUEUE | Every 2 min | No |
| `classify_response` | llm | 500 | 120 s | 3 | REQUEUE | After a `responses` insert | Yes |
| `create_handoff` | io | 500 | 60 s | 5 | REQUEUE | After classification | No |
| `send_notification` | notify | 700 | 60 s | 3 | **FAIL** | Handoff, alert, digest | No |
| `handoff_sla_sweep` | notify | 200 | 120 s | 3 | REQUEUE | Every 5 min | No |
| `telegram_poll` | notify | 200 | 90 s | 5 | REQUEUE | Continuous (polling mode) | No |
| `daily_report` | export | 400 | 600 s | 3 | REQUEUE | 07:35 IST | No |
| `staleness_sweep` | maint | 100 | 900 s | 3 | REQUEUE | 01:00 IST | No |
| `suppression_sync` | io | 150 | 300 s | 3 | REQUEUE | 02:00 IST | No |
| `backup_db` | maint | 100 | 1800 s | 2 | REQUEUE | 00:20 IST | No |
| `prune_logs` | maint | 100 | 900 s | 2 | REQUEUE | 00:40 IST | No |
| `score_calibration` | llm | 100 | 900 s | 2 | REQUEUE | 1st of month, 03:30 IST | Yes |

`process_webhook_event` is **no longer** in the registry either; §14.8.14 records what happened to it
and where each of its responsibilities went.

`send_whatsapp` is **not** in the registry. `_CONTEXT.md` §4 puts WhatsApp on a `wa.me` click-to-chat
link that Sagar sends by hand in v1, so there is no job that transmits on that channel and no code
path that could be enabled by a config flag. `06-message-templates.md` and
`08-whatsapp-integration.md` describe the Cloud API path that is built but gated; when it is enabled
it registers `send_whatsapp` with `max_attempts=1` and `on_lease_expiry="RECONCILE"`, exactly like
`send_email`, and it must not be registered before then.

### 14.8.1 The campaign pipeline (§2)

Spec §2 says "starting a search creates a Search Campaign" and lists what it stores. Everything after
"starting" is this pipeline. It is a fan-out DAG with one polling collector at the end.

```
POST /api/v1/campaigns            (Flask request thread, one transaction)
  │   INSERT campaigns(status='QUEUED', …)         <- §2's stored fields
  │   INSERT campaign_cities(one per target city)
  │   enqueue discover_city  x N cities            batch_id = bat_…, trace_id = trc_…
  │   enqueue campaign_finalize (run_after = now + 60s)
  └── COMMIT ──► wake.poke('io')
        │
        ▼
   discover_city (per city, per page)
        │  writes businesses + sources; campaigns.n_discovered += k
        │  more pages? enqueue discover_city with cursor_page+1  (same batch, same trace)
        └─ per new business ──► research_business
                                   │  writes research_runs, research_findings,
                                   │         sources, finding_sources
                                   │  campaigns.n_researched += 1
                                   └──► score_business
                                           │  writes opportunities (numeric), band
                                           │  campaigns.n_qualified / n_skipped += 1
                                           └──► assess_opportunity
                                                   │  writes opportunities (narrative),
                                                   │         opportunity_modules
                                                   └──► (nothing; the leaf)
        ▲
        │
   campaign_finalize  (every 60 s while work remains)
        │  no outstanding jobs for this campaign?
        └─► reconcile counters, enqueue generate_report, campaigns.status='COMPLETE'
```

**Campaign status.** `_CONTEXT.md` §6 fixes the business lifecycle and outreach statuses but not the
campaign's, so this document proposes the set and `01-data-model.md` owns the final say (flagged in
Open questions):

```sql
-- contract, owned by 01-data-model.md
-- campaigns.status CHECK (status IN
--   ('DRAFT','QUEUED','DISCOVERING','RESEARCHING','REPORTING',
--    'COMPLETE','PAUSED','FAILED','CANCELLED'))
```

| Status | Set by | Meaning |
|---|---|---|
| `DRAFT` | `POST /api/v1/campaigns` with `"start": false` | Filters chosen, nothing enqueued. |
| `QUEUED` | Campaign create | Jobs enqueued, none claimed yet. |
| `DISCOVERING` | First `discover_city` to start | At least one discovery job is live. |
| `RESEARCHING` | First `research_business` to start | Discovery finished for at least one city. |
| `REPORTING` | `campaign_finalize` | All pipeline jobs terminal; `generate_report` enqueued. |
| `COMPLETE` | `generate_report` success | §42's archive entry exists. |
| `PAUSED` | Daily quota ceiling (§14.10.4), or Sagar | No new pipeline jobs are claimed; live ones finish. A quota pause clears itself when the quota day rolls over; a Sagar pause does not. |
| `FAILED` | `campaign_finalize` | Every city's discovery failed. Partial failure is not campaign failure. |
| `CANCELLED` | `POST /api/v1/campaigns/<id>/cancel` | `cancel_requested = 1` on every non-terminal job for the campaign. |

**The counters (§2).** `n_discovered`, `n_researched`, `n_qualified`, `n_skipped`, `n_verified`,
`n_contacted` are columns on `campaigns`, incremented **in the same transaction as the row that
causes the increment** — never by a periodic recount:

```sql
-- inside research_business's terminal transaction
UPDATE campaigns SET n_researched = n_researched + 1 WHERE id = :campaign_id;
```

Two reasons an increment beats a recount here. It is O(1) instead of a `COUNT(*)` over `businesses`
joined to `research_runs` every time a progress bar ticks (§14.11), and it is exactly consistent with
the write that caused it, so a reader can never see "researched 41" while the 41st research row is
still uncommitted. The cost is drift if a write path is ever added that forgets, which is why
`campaign_finalize` recomputes all six from aggregates once, at the end, and `staleness_sweep`
recomputes them nightly for live campaigns and logs `WARNING` on any mismatch (§14.8.20). Drift is
therefore bounded, detected and named rather than assumed away.

`n_verified` and `n_contacted` are incremented by the verification and send paths respectively, not
by this pipeline; they are listed here because §2 stores them on the campaign and
`campaign_finalize`'s reconciliation covers all six.

### 14.8.2 `discover_city`

| | |
|---|---|
| **Trigger** | Campaign create (one per `campaign_cities` row), and its own continuation for page 2..n |
| **Payload** | `{"campaign_id","city","city_slug","industries","size_filter","cursor_page","cursor_token","source":"OSM_OVERPASS"}` |
| **Dedupe key** | `discover_city:{campaign_id}:{city_slug}:{cursor_page}` |
| **Duration** | 5-45 s per page (an Overpass query, zero or more Nominatim lookups, plus inserts) |
| **Retries** | 3, `fast` backoff; `RATE_LIMIT` deferred against `discovery.overpass.rpm` or `discovery.nominatim.rps` as appropriate (§14.10.1). Overpass answers a query it cannot serve with a 429 or a 504 and both are deferrals, not failures |
| **Writes** | `businesses` (new rows, `status='AI_RESEARCHED'`, `research_status='PENDING'`), `sources`, `campaigns.n_discovered`, `campaigns.status='DISCOVERING'`, one `jobs` row per new business (`research_business`), one continuation `jobs` row if a next page exists |
| **Idempotency** | Per-business natural key. A re-run of the same page inserts nothing new because the upsert keys on `(city_slug, name_norm, phone_norm | website_domain)`; `INSERT … ON CONFLICT DO NOTHING`, then `changes()` decides whether to increment the counter and enqueue research |
| **Failure mode** | Provider down -> retries, then `FAILED`; the campaign continues with the cities that worked and `campaign_finalize` records `cities_failed` in the campaign result. One dead city never fails a campaign |

```json
{
  "campaign_id": "cmp_01JB0000000000000000000001",
  "city": "Dhule",
  "city_slug": "dhule",
  "industries": ["HEALTHCARE", "EDUCATION", "MANUFACTURING"],
  "size_filter": ["MEDIUM", "LARGE"],
  "cursor_page": 1,
  "cursor_token": null,
  "source": "SEARCH_API"
}
```
SAMPLE.

**The chunking rule, stated here because this is where it first bites.** Discovery for a city can be
hundreds of results across many pages. One job per page, each re-enqueueing the next with
`cursor_page + 1`, keeps every attempt inside `timeout_seconds = 300` and means a crash costs one
page, not one city. The rule generalises: *if a job's duration scales with data volume, it processes
one bounded chunk and enqueues its own continuation.* `discover_city`, `export_xlsx` and
`suppression_sync` all follow it.

### 14.8.3 `research_business`

| | |
|---|---|
| **Trigger** | Fan-out from `discover_city`; `staleness_sweep`; manual re-research from `/business/<id>` |
| **Payload** | `{"business_id","campaign_id","research_run_id","depth":"STANDARD"|"DEEP","reason":"CAMPAIGN"|"STALE"|"MANUAL"|"RECHECK"}` |
| **Dedupe key** | `research_business:{business_id}:{research_run_id}` |
| **Duration** | 40-240 s standard, up to 600 s deep |
| **Retries** | 3, `standard` backoff |
| **Model** | `gemini-2.5-flash` via `google-genai`, structured output through `response_schema`, `thinking_config` dynamic for `DEEP` and `thinking_budget=0` for `STANDARD`. **Source fetching is ours, not the model's**: `02-research-pipeline.md` owns the Overpass / Nominatim / website / MCA21 / GST fetchers and passes the retrieved text in, because `_CONTEXT.md` §4 forbids a paid search API and a free-tier grounding tool is not a source we can cite a `checked_at` for. Exact call in `02-research-pipeline.md` |
| **Writes** | `research_runs` (status `RUNNING` -> `COMPLETE`), `research_findings` (each typed `OBSERVED`/`INFERRED`/`UNKNOWN` per §12), `sources`, `finding_sources`, `businesses.research_status`, `businesses.last_researched_at`, `campaigns.n_researched`, `job_runs` quota columns, `spend_ledger` |
| **Idempotency** | The `research_run_id` is minted by the **enqueuer** and written into the payload. On retry the handler finds the existing `research_runs` row: if `status='COMPLETE'` it returns `Done` immediately (the crash happened after the work); if `RUNNING` it deletes that run's partial `research_findings` and `finding_sources` in one transaction and starts over. Partial findings are never merged with a second run's — a half-set of findings that looks complete is how a message ends up citing a fact that was never finished |
| **Failure mode** | Exhausted attempts -> `FAILED`, `research_runs.status='FAILED'`, `businesses.research_status='FAILED'`. The business still appears in the report with research confidence `LOW` and a visible "research failed" state; it is not silently dropped, because a business missing from a city section looks like the city has fewer businesses than it does |

Every LLM call records what `_CONTEXT.md` §2 requires — `model_id`, `prompt_version`, input/output
tokens — onto both the `research_runs` row and the `job_runs` row, plus a `spend_ledger` entry. There
is no code path in this job that calls the API without going through `ctx.llm()` (§14.10.2), which is
what makes that guarantee mechanical rather than a convention.

### 14.8.4 `score_business`

| | |
|---|---|
| **Trigger** | After `research_business` succeeds |
| **Payload** | `{"business_id","campaign_id","research_run_id"}` |
| **Dedupe key** | `score_business:{business_id}:{research_run_id}` |
| **Duration** | < 1 s |
| **Retries** | 3, `fast` |
| **Model** | **None.** Pure Python in `radar/score.py` over the stored findings |
| **Writes** | `opportunities` (new row: `score`, `band`, `digital_maturity`, `operational_complexity`, `confidence`, `confidence_pct`, `score_breakdown` JSON with a `because_finding_id` per component, `is_current=1`, prior row's `is_current=0`), `businesses.status` -> `NEEDS_VERIFICATION` when the score clears `campaigns.min_opportunity_score`, `campaigns.n_qualified` or `n_skipped` |
| **Idempotency** | Deterministic: same findings in, same score out. A retry recomputes and rewrites; the `is_current` flip is inside the same transaction, so there is never a moment with two current rows or none |
| **Failure mode** | Cannot fail for provider reasons. A `BUG` here is a real bug and pages after attempts are exhausted |

Splitting the numeric score from the narrative (§14.8.5) is deliberate. The score is what §7's KPI
cards, §8's city summaries, §37's city comparison and §44's Top 20 are built from, and those must
work when the Gemini API is down — or, far more often on this stack, when the day's free-tier quota
is spent (§14.10.4). A campaign that ran through an outage or a quota pause produces a complete,
ranked, honest report with empty "Potential Solution" cells rather than no report at all. The split
was insurance against an outage; on a metered free tier it is closer to a routine operating mode.

### 14.8.5 `assess_opportunity`

| | |
|---|---|
| **Trigger** | After `score_business` |
| **Payload** | `{"business_id","campaign_id","research_run_id","opportunity_id"}` |
| **Dedupe key** | `assess_opportunity:{business_id}:{research_run_id}` |
| **Duration** | 15-60 s |
| **Retries** | 3, `standard` |
| **Model** | `gemini-2.5-flash`, `thinking_budget=0`, structured output (`response_schema`) for the §13 fields |
| **Writes** | `opportunities` (updates `potential_problem`, `potential_solution`, `expected_benefit`, `model_id`, `prompt_version`, `assessed_at` on the current row), `opportunity_modules` (§13's module list, replaced wholesale inside one transaction), `job_runs` quota columns, `spend_ledger` |
| **Idempotency** | Keyed on `opportunity_id`; the update is a full overwrite of the narrative columns and a delete-then-insert of the module rows, in one transaction. Re-running produces a consistent row, never a merge |
| **Failure mode** | `FAILED` leaves the numeric score intact and the narrative columns NULL. The report renders `—` for them, per `_CONTEXT.md` §3 invariant 5 — never a placeholder sentence, never a fabricated problem statement |

The prompt for this job may only reference findings from the run named in the payload, and the
structured output is validated to ensure every claim carries a `finding_id`. A claim without one is
dropped and counted in `job_runs.error_detail` as `"unsourced_claims": n`. This is the upstream half
of `_CONTEXT.md` §3 invariant 4: the policy engine at draft time can only be as good as the facts
this job stored.

### 14.8.6 `campaign_finalize`

| | |
|---|---|
| **Trigger** | Enqueued at campaign create with `run_after = now + 60 s`; re-enqueues itself every 60 s while work remains |
| **Payload** | `{"campaign_id","tick":1}` |
| **Dedupe key** | `campaign_finalize:{campaign_id}:{tick_iso}` |
| **Duration** | < 200 ms |
| **Retries** | 5, `fast` |
| **Writes** | `campaigns.status`, `campaigns.finished_at`, all six §2 counters (reconciled from aggregates), the `generate_report` job |
| **Idempotency** | Reads state, writes a conclusion. Running it twice for the same tick is a no-op |
| **Failure mode** | If it stops running the campaign hangs in `RESEARCHING` forever, so the stall alert in §14.12.3 watches for a campaign in a live status with zero non-terminal jobs for more than 10 minutes |

```sql
-- the completion test
SELECT COUNT(*) AS outstanding
  FROM jobs
 WHERE campaign_id = :campaign_id
   AND type IN ('discover_city','research_business','score_business','assess_opportunity')
   AND state IN ('QUEUED','LEASED','RUNNING');
```

**Why a poll rather than a countdown.** The obvious alternative is an `outstanding` counter on
`campaigns`, decremented by each child job as it finishes, with the last one triggering the report.
It is O(1) and it is a trap: any path that ends a job without decrementing — a reaper moving a job to
`FAILED`, a manual cancel, a `DEAD` from a bad deploy — leaves the counter permanently above zero and
the campaign never completes, with no error anywhere. The poll costs one indexed `COUNT(*)` per
minute per live campaign (`ix_jobs_campaign` covers it exactly) and is self-healing: whatever
happened to the children, the next tick sees the truth. On a single-operator tool with a handful of
concurrent campaigns, correctness is worth a query a minute.

The tick has a deadline: `campaigns.finished_at IS NULL AND created_at < now - jobs.campaign_max_hours`
(default 24) moves the campaign to `FAILED` with `paused_reason='campaign timed out'` and stops the
self-rescheduling, so a wedged campaign cannot re-enqueue itself forever.

### 14.8.7 `generate_report` (§5, §42)

| | |
|---|---|
| **Trigger** | `campaign_finalize`; `POST /api/v1/campaigns/<id>/report` (manual regenerate) |
| **Payload** | `{"campaign_id","scope":{…filters…},"scope_hash","kind":"HTML"}` |
| **Dedupe key** | `generate_report:{campaign_id}:{scope_hash}` |
| **Duration** | 5-90 s |
| **Retries** | 3, `standard` |
| **Writes** | `report_exports` (`PENDING` -> `READY`), the file at `data/reports/{campaign_id}/{filename}`, `campaigns.status='COMPLETE'`, an `audit_log` row |
| **Failure mode** | `report_exports.status='FAILED'` with the error stored; the campaign shows "report failed, retry" rather than looking complete with a broken download link |

The filename follows §5 exactly:
`business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.html` (SAMPLE) — city slugs joined by `_`
in `campaign_cities.ordinal` order, then the campaign's IST date.

Write discipline, per `_CONTEXT.md` §1:

```python
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(html, encoding="utf-8")
os.replace(tmp, path)                       # atomic within one filesystem
sha = hashlib.sha256(path.read_bytes()).hexdigest()
```

The `report_exports` row moves to `READY` only after `os.replace` returns and the hash is computed,
so a reader can never be handed a path to a half-written file.

**§42, the archive.** Every generation creates a **new** `report_exports` row; nothing is ever
overwritten in place. Re-running with the same `scope_hash` returns the existing `READY` row and does
no work (the dedupe key sees to it), while a different filter set produces a new artifact with its
own row. `GET /api/v1/campaigns/<id>/exports` lists them newest first, and `/campaigns/<id>` renders
that list so a previous campaign can be reopened exactly as it was. Retention:
`report_exports.expires_at IS NULL` for `HTML` and `DAILY_HTML` (the archive is the product), and
`now + jobs.retention.export_days` (default 30) for `CSV`/`XLSX`/`PDF`, which are re-derivable from
the same rows at any time. `prune_logs` moves an expired artifact to `status='PURGED'` and deletes
the file, keeping the row so the archive still shows that the export existed and when.

Numbers in the report come from SQL aggregates over real rows (`_CONTEXT.md` §3 invariant 5). This
job passes the connection to `radar/report.py` and passes **no counters of its own** — not even the
campaign's `n_*` columns, which are progress accounting rather than report truth. If an aggregate
returns no rows the template renders `—`.

### 14.8.8 `export_csv` (§41)

| | |
|---|---|
| **Trigger** | `POST /api/v1/campaigns/<id>/exports {"format":"CSV", …}` |
| **Payload** | `{"campaign_id","scope","scope_hash","kind":"CSV"}` |
| **Dedupe key** | `export_csv:{campaign_id}:{scope_hash}` |
| **Duration** | < 5 s for a few hundred rows |
| **Retries** | 3, `fast` |
| **Writes** | `report_exports`, the file, an `audit_log` row (an export is a copy of business and contact data leaving the system, and §47 wants that recorded) |
| **Failure mode** | `FAILED` with the error on the row; the UI shows a retry control |

Columns are §41's preserved set, in this order: Business, City, Industry, Category, Size,
Opportunity Score, Band, Digital Maturity, Research Confidence, Verification Status, Contact
Available, Contact Channel, Outreach Status, Last Contacted, Discovered At. Written UTF-8 with a BOM,
`\r\n` line endings, and `csv.QUOTE_MINIMAL` — the BOM because the primary consumer is Excel on
Windows and without it every Devanagari business name renders as mojibake, which makes the export
look broken even though the bytes are right.

Contact values are included only where a verified contact exists and no live suppression covers it;
a suppressed contact exports as `SUPPRESSED`, never as the address. An export is a place personal
data escapes the app's own gates, so the gates travel with it.

### 14.8.9 `export_xlsx` (§41)

| | |
|---|---|
| **Trigger** | As `export_csv`, `"format":"XLSX"` |
| **Payload** | `{"campaign_id","scope","scope_hash","kind":"XLSX"}` |
| **Dedupe key** | `export_xlsx:{campaign_id}:{scope_hash}` |
| **Duration** | 3-60 s |
| **Retries** | 3, `standard` |
| **Writes** | `report_exports`, the file, `audit_log` |
| **Failure mode** | `FAILED`; `MemoryError` is classified `BUG` and pages |

`openpyxl` in `write_only=True` mode, matching `naukri_job_screener/screener/export.py`. Write-only
mode is not an optimisation here, it is the memory ceiling: the normal mode holds every cell object
in RAM, and a 2000-row export with 15 columns on a laptop competing with the web server and a browser is exactly
the shape of an OOM kill. Sheets: `Businesses` (the §9 column set), `By City` (§8), `By Industry`
(§38), `Top Opportunities` (§44). One frozen header row, an auto-filter, and column widths computed
from the 95th-percentile value length rather than the maximum, so one long business name does not
produce a 300-character-wide column.

### 14.8.10 `export_pdf` (§41)

| | |
|---|---|
| **Trigger** | As `export_csv`, `"format":"PDF"` |
| **Payload** | `{"campaign_id","scope","scope_hash","kind":"PDF","engine":"weasyprint"}` |
| **Dedupe key** | `export_pdf:{campaign_id}:{scope_hash}` |
| **Duration** | 20 s - 5 min |
| **Retries** | 2, `standard` |
| **Writes** | `report_exports`, the file, `audit_log` |
| **Failure mode** | The single most likely OOM in the system, so it is the one job that does not run in-process |

```python
proc = subprocess.run(
    [sys.executable, "-m", "radar.render_pdf", str(html_path), str(tmp_pdf)],
    timeout=ctx.remaining_seconds(),
    capture_output=True,
    check=False,
)
```

The child sets `resource.setrlimit(RLIMIT_AS, (cfg.jobs.export.pdf_mem_mb * 1024 * 1024,) * 2)` on
POSIX before importing the renderer, so a runaway render dies as a non-zero exit code with a clear
message instead of as an OOM kill that takes the website with it. On a `MemoryError` exit the handler
returns `Fail(permanent=False)`; on the second failure `report_exports.error` reads "PDF rendering
exceeded the memory cap; export the HTML or the XLSX instead", which is an instruction rather than a
stack trace.

The PDF is rendered from the **same** self-contained HTML the `generate_report` job produced, not
from a second template. One template, three outputs; a PDF that disagrees with the HTML it claims to
be a copy of is worse than no PDF.

---

### 14.8.11 `draft_outreach`

Owned in behaviour by `05-outreach-workflow.md` §5.5.1; listed here for its job properties.

| | |
|---|---|
| **Trigger** | `POST /api/v1/outreach/prepare`, one job per selection, grouped by `batch_id` |
| **Payload** | `{"selection_id","business_id","campaign_id","channel":"EMAIL","depth":"STANDARD","regen_no":0}` |
| **Dedupe key** | `draft_outreach:{selection_id}` (plus `:{regen_no}` on a regenerate) |
| **Duration** | 10-40 s |
| **Retries** | 3, `standard` |
| **Writes** | `outreach_drafts`, `outreach_messages` (`DRAFT` -> `PENDING_APPROVAL` or `POLICY_BLOCKED`), `outreach_events` (`DRAFTED`, then `POLICY_PASS`/`POLICY_BLOCK`), `job_runs` quota columns, `spend_ledger`. The local contact substitution in `06-message-engine.md` §6.13.0 happens inside this job, between the last model call and the draft insert, so the policy check reads the hydrated text |
| **Idempotency** | Keyed on `selection_id`. A retry finds the existing draft: if it already reached `PENDING_APPROVAL` the job returns `Done` without a second LLM call |
| **Failure mode** | `POLICY_BLOCK` is a **success** for the job and a block for the message — `job_runs.outcome='SUCCEEDED'`, `result={"policy":"BLOCKED","rule_ids":[…]}`. Recording a policy block as a job failure would put it in the dead-letter view and invite someone to "retry" it, which is the last thing that should be easy |

This job cannot send. It has no import of `radar/channels/`, and a test asserts that
(`test_draft_outreach_cannot_import_channels`), mirroring the `radar.notify` / `radar.channels`
separation in `10-human-handoff.md` §10.6.1.

### 14.8.12 `send_email` — the exactly-once job

| | |
|---|---|
| **Trigger** | `POST /api/v1/outreach/messages/<message_id>/send`, after `outreach_messages.status` moves `APPROVED` -> `QUEUED` in the request transaction |
| **Payload** | `{"message_id","approval_id","business_id","campaign_id","contact_id"}` — **no body, no subject, no address** |
| **Dedupe key** | `send_email:{message_id}` — permanent, never pruned |
| **Duration** | 0.5-8 s |
| **Retries** | **`max_attempts = 1`** |
| **Lease expiry** | `RECONCILE` (§14.13.4) |
| **Writes** | `outreach_events` (`SEND_ATTEMPT`, then one of `SENT` / `PROVIDER_ERROR` / `RATE_LIMITED` / `INDETERMINATE`), `outreach_messages` (`status`, `sent_at`, `provider`, `provider_message_id`, `provider_status_code`, `provider_response`, `attempt_count`, `worker_id`, `eligibility_snapshot`), `audit_log` (§48), `campaigns.n_contacted`, `businesses.status` -> `CONTACTED`, `spend_ledger` |
| **Failure mode** | Three distinct ones, and keeping them distinct is the whole design: **refused** (a gate said no — message `CANCELLED` or left `QUEUED` with the block recorded, job `FAILED`, no transmission), **rejected** (provider returned a definite 4xx — message `FAILED`, job `FAILED`, no transmission), **indeterminate** (we do not know — message stays `QUEUED`, `INDETERMINATE` event, job `DEAD`, Sagar is asked) |

The payload carries ids only. The body is read from `outreach_messages.body_final` at transmit time
and hashed against `outreach_approvals.approved_body_hash` inside the send function, so the bytes
that go on the wire are provably the bytes Sagar approved. A payload carrying the body would let an
edit between approval and send slip through, and would put a personalised business email into a table
that gets pruned and logged.

Order of operations inside the handler, in full, because §14.13 depends on it:

```
 1. load message + approval; assert status = 'QUEUED' and approval is live and unrevoked
 2. check_send_eligibility(stage=SEND)              -> block => Fail(ELIGIBILITY_BLOCK), no transmit
 3. send window open? (14.9.3)                      -> no    => Defer(next open)
 4. take 1 token from email.hour, email.day, email.domain.{d}.day   -> empty => Defer(eta)
 5. body_hash == approval.approved_body_hash?       -> no    => Fail(permanent), page immediately
 6. T1  COMMIT the intent  (SEND_ATTEMPT event + attempt_count + provider)
 7. ---- network: SMTP session to Gmail, no transaction open, no lock held ----
 8. T2  COMMIT the outcome (SENT | PROVIDER_ERROR | INDETERMINATE + audit_log + counters)
```

Steps 3 and 4 are `Defer`, not `Retry`: they do not consume the one attempt. Only step 6 does, and by
then every gate has passed. That is what makes `max_attempts = 1` workable rather than brittle.

**Changed for the free stack: step 7 is an SMTP session, not an HTTPS API call, and that makes
step 8's "indeterminate" case both more likely and less resolvable.** An ESP API returned an id and
had a lookup endpoint to ask afterwards; `smtplib` against `smtp.gmail.com` gives a `250` on the
final `.` and nothing to query later. Two consequences:

- The `provider` column is the literal `gmail_smtp`, and `provider_message_id` is the `Message-ID`
  **we generated** (`14.13.2`), not one the server assigned — which is what makes reply attribution
  work at all (`09` §9.2.4 signal 1).
- A connection that drops between `DATA` and the `250` is genuinely indeterminate and there is no
  authoritative lookup to settle it. `07-email-integration.md`'s IMAP `[Gmail]/Sent Mail` check is
  the best available evidence and `§14.13.4` uses it, but it is evidence and not proof, so the design
  ends where it always ended: at-most-once, and ask Sagar.

§14.5.6 adds one more trigger for this path that did not exist on the old target: a laptop that
suspends between steps 7 and 8. It is handled by the same `RECONCILE` rule, and it is now the most
likely way an indeterminate send happens.

### 14.8.13 `poll_inbox` (§33)

**Promoted for the free stack: this is the primary and only automatic inbound path.** It used to be
one of two, with `process_webhook_event` (§14.8.14) carrying delivery events and, optionally, inbound
parse. There is no second path now, so everything that arrives at this system arrives here:

| What arrives | What `poll_inbox` does with it | Owner of the rule |
|---|---|---|
| A reply from a business | `responses` row + a `classify_response` job, same transaction | `09-response-classification.md` §9.2 |
| A DSN / bounce | Parses `Status:`; `5.x.x` -> `outreach_events(BOUNCED)` + `suppressions(BOUNCE_HARD)`; `4.x.x` -> `outreach_events(BOUNCED, soft)`. No `responses` row | `09` §9.4 rule `E1`, `07-email-integration.md` |
| A `mailto:` unsubscribe (the recipient pressed Unsubscribe in their mail client) | `suppressions` + `outreach_events(UNSUBSCRIBED)`, in the same transaction as the row, settled with no model call | `09` §9.4 rule `E9` |
| An auto-responder / out-of-office | `responses` row marked as an auto-reply; no handoff | `09` §9.4 rules `E2`, `E3` |
| A read receipt, a mailing-list message | Diverted; logged; no row | `09` §9.4 rules `E4`, `E6` |

Because delivery outcomes now arrive as bounce mail rather than as provider events, **there is no
`DELIVERED` signal at all** on this stack. SMTP acceptance by Gmail means "handed over", not
"delivered". `05-outreach-workflow.md`'s `DELIVERED` status is therefore reachable only through the
gated WhatsApp path, and an email that was accepted and never bounced stays `SENT` forever, which is
the honest state. Nothing in the funnel (§54) may treat absence of a bounce as delivery.

| | |
|---|---|
| **Trigger** | Schedule, every 2 minutes |
| **Payload** | `{"mailbox":"replies","slot":"2026-08-27T05:02:00Z"}` |
| **Dedupe key** | `poll_inbox:{slot_iso}` |
| **Duration** | 1-20 s; up to 180 s on the first run against a full mailbox |
| **Retries** | 3, `fast` |
| **Writes** | `responses` (one row per new message), `outreach_events` (`MANUAL_RECORDED` is not used here; a matched reply writes nothing to the message row directly), one `classify_response` job per new response, `businesses.status` -> `RESPONDED` |
| **Idempotency** | Two layers: IMAP `UID` per folder stored in `config/state/imap_uid.json` (atomic write, corrupt-file recovery per `_CONTEXT.md` §1), and a unique index on `responses(provider_message_id)` where `provider_message_id` is the RFC 5322 `Message-ID` header. The UID is an optimisation; the unique index is the guarantee |
| **Failure mode** | IMAP down, or the laptop has no network -> retries -> `FAILED`; the next slot's job picks up everything that arrived meanwhile, because the UID cursor did not advance. Missing one poll costs latency, never data. **This is why `poll_inbox` is `catch_up = SKIP` with no grace** (§14.9.2): the mailbox is the queue, so one poll after twelve hours of downtime collects twelve hours of mail in a single pass, and running the eleven missed slots as well would achieve nothing except eleven no-ops |
| **Per-message failure** | One unparseable message must not fail the whole poll. Each message is processed in its own transaction; a message that raises is logged at `ERROR` with its UID, its raw MIME is written to `data/inbound/failed/`, the UID cursor still advances past it, and a `send_notification` with `kind='JOB_ALERT'` names it. Blocking the cursor on one bad message would stop every reply behind it, which on a single inbound path means stopping the business |

Matching a reply to an outreach message, in priority order:

| # | Signal | Strength |
|---|---|---|
| 1 | `In-Reply-To` / `References` contains the deterministic `Message-ID` we generated (§14.13.2) | Exact |
| 2 | The `+tag` in the `Reply-To` address (`replies+msg_01JB…@send.example.com`) | Exact |
| 3 | Sender address matches a `business_contacts.value_norm` with an `outreach_messages` row `SENT` in the last `response.match_days` (default 60) | Strong |
| 4 | Sender's eTLD+1 matches `outreach_messages.recipient_domain` in the same window | Weak — creates the `responses` row with `business_id` set and `match_confidence='LOW'`, which forces a human check before any handoff acts on it |
| 5 | No match | `responses` row with `business_id = NULL`, `classification` deferred, surfaced in an "unmatched replies" band. Never discarded |

A `UIDVALIDITY` change on the server (a mailbox rebuild) invalidates every stored UID. The handler
detects it, logs an `ERROR` naming the old and new values, resets the cursor to 1 and re-scans; the
unique index on `provider_message_id` absorbs the re-scan without creating a single duplicate
response. That is the same posture as `ledger.py`: recover loudly, never silently reset.

**Why IMAP polling rather than an inbound webhook.** The earlier version of this paragraph called
IMAP the pragmatic first step and a webhook "the eventual answer". `_CONTEXT.md` §2 settles it the
other way and permanently: the app is bound to `127.0.0.1` on Sagar's laptop, there is no public
hostname, no MX record and no reachable HTTPS endpoint, so **a webhook is not a later upgrade, it is
not possible**. IMAP against a Gmail mailbox works from behind any firewall, on a machine with a
changing IP, with an App Password Sagar already has — which is precisely the set of properties this
deploy target has.

Two costs, stated plainly rather than hidden:

- **Latency is a floor of the poll interval.** A reply that lands at 10:00:30 is seen at 10:02. That
  is invisible next to the hours it takes Sagar to act on a handoff, so it costs nothing real.
- **Latency is unbounded while the laptop is shut.** A reply that arrives at 22:00 is seen when the
  machine is next opened. There is no design that fixes this without a server, and `10`'s SLA sweep
  must therefore measure its clocks from **first observation**, not from `responses.received_at`, or
  every overnight reply is born already breaching (§14.12.3's uptime rule is the same point).

`response.ingest` stays in `09`'s config as a single-valued key (`imap`) rather than being deleted,
so that a future deployment onto a host with a public name is a config change and not an archaeology
exercise. The unique index on `responses(provider_message_id)` also stays, and it is what would make
a second ingestion path a no-op rather than a duplicate lead if one ever existed.

### 14.8.14 `process_webhook_event` — removed

**This job type no longer exists, and neither does the endpoint that fed it.** The section number is
kept, and so is this explanation, because the earlier version of this document specified the job in
detail and several other documents were written against it.

**Why.** `_CONTEXT.md` §2: the app is Flask + waitress bound to `127.0.0.1` on Sagar's Windows
laptop. There is no public hostname, no TLS certificate, no port forwarded, and the machine is not on
at night. A provider webhook is an inbound HTTP POST from the public internet; nothing can deliver
one. This is not "not built yet" — it is not reachable, and a design that keeps an unreachable
endpoint keeps a hole where a signature-verification bug can live for nothing.

Removed with it: `POST /api/v1/webhooks/<provider>`, the `webhook:{provider}:{provider_event_id}`
dedupe namespace, `jobs.retention.webhook_days`, and the `"raw"` payload exception in §14.6.3.

**Where each responsibility went.**

| Was handled by `process_webhook_event` | Now |
|---|---|
| `BOUNCED` on a hard bounce, plus `suppressions(BOUNCE_HARD)` | `poll_inbox` parses the DSN itself (§14.8.13; `09-response-classification.md` §9.4 rule `E1`). A bounce is an email; we were always going to receive it |
| `BOUNCED` soft | Same, `4.x.x` status, no suppression |
| `COMPLAINED` (a feedback-loop report) | **Gone, and this is a real loss.** Gmail publishes no feedback loop to a free account (`_CONTEXT.md` §4: SPF/DKIM/DMARC are Google's and there is no postmaster relationship). A spam complaint is now invisible to the system until the recipient also replies. The compensating control is the one `_CONTEXT.md` §4 already names: 15-25 sends a day, one recipient per message, per-message human approval, and `09` §9.5's `B4` complaint lexicon on any reply that does arrive. Volume is the control, because instrumentation is not available |
| `UNSUBSCRIBED` from a provider one-click endpoint | `poll_inbox` + `09` §9.4 rule `E9`: the RFC 2369 `mailto:` unsubscribe arrives as mail. `06-message-engine.md` §6.4 and rule `R1` put the address and the token in every message |
| `DELIVERED` | **Gone.** SMTP acceptance is not delivery, and nothing else reports it. §14.8.13 states the consequence: an accepted, un-bounced email stays `SENT` |
| `OPENED` / `CLICKED` | **Gone, and deliberately not replaced.** Open tracking needs a pixel on a host we control and click tracking needs a redirector on one; §6.9.7 rule `R7` forbids both in a body regardless, and `_CONTEXT.md` §4's AUP argument ("a person writing business letters") is weakened by every tracker added. Not a loss worth mourning |
| Inbound parse of a reply | `poll_inbox`, which is where it was always going to be better |

**What this costs, in one sentence, so nobody later reads the absence as an oversight:** the system
loses delivery confirmation, open/click telemetry and automated complaint capture, and keeps the two
signals that actually gate behaviour — bounces and opt-outs — because both of those arrive as email
and email is the one channel that reaches a laptop behind a router.

### 14.8.15 `classify_response` (§33)

| | |
|---|---|
| **Trigger** | After a `responses` insert, from `poll_inbox` or the manual endpoint (`09` §9.2.6), enqueued **in the same transaction as the insert** |
| **Payload** | `{"response_id","business_id"}` |
| **Dedupe key** | `classify_response:{response_id}` |
| **Duration** | 2-8 s |
| **Retries** | 3, `standard` |
| **Model** | `gemini-2.5-flash` (`_CONTEXT.md` §2), `max_output_tokens=512`, `temperature=0.0`, `thinking_budget=0`, structured output via `response_schema`. The pinned id is verified at startup (§14.5.1 step 3) and the resolved `model_version` is what lands in `responses.classifier_model_id` |
| **Writes** | `responses.classification`, `.confidence`, `.confidence_pct`, `.classifier_model_id`, `.classifier_prompt_version`, `.interpretation`, `.recommended_action`, `.is_stopper`, `.classified_at`; `suppressions` when the classification is `OPT_OUT`; `businesses.status` -> `RESPONDED` or `INTERESTED`; a `create_handoff` job when a trigger fires; `job_runs` quota columns; `spend_ledger`. Column names per `09-response-classification.md` §9.1.2, which is the arbiter |
| **Idempotency** | Keyed on `response_id`; the write is a full overwrite of the classification columns. A re-classification after a prompt change is a new job with `regen_no` and it supersedes rather than merges |
| **Failure mode** | Exhausted attempts -> `classification='UNKNOWN'`, `confidence='LOW'`, and — this is the important part — **a handoff is created anyway**. Per `10-human-handoff.md` §10.12, the failure mode of the classifier is a human being asked to read it, never silence |

The output is constrained to the §6 enum exactly, and the field names are
`09-response-classification.md` §9.7.4's, which owns the `response_schema`:

```json
{
  "classification": "DEMO_REQUESTED",
  "confidence_pct": 88,
  "evidence_spans": ["please show us what you can provide"],
  "interpretation": "Asks to be shown the system; names a time window.",
  "suggested_next_action": "Offer two slots this week.",
  "contains_opt_out": false,
  "contains_complaint": false
}
```
SAMPLE. **Three names in this block were wrong in the revision written before `01-data-model.md`
ruled, and are corrected here rather than carried:** `rationale` is `interpretation` (`01` §1.9.1's
column, and §9.7.5's mapping), `opt_out_signal` is `contains_opt_out` (which sets `responses.is_stopper`
— there is no `opt_out_signal` column and never was), and the single `quoted_span` is the
`evidence_spans` array. `09` §9.15 item 2 asks for exactly these three edits and this is where they
land. `confidence` is not a model output at all: it is the band derived from `confidence_pct` by
§9.8.1, which is why it appears in the **Writes** row above and not here.

Every `evidence_spans` entry must be a verbatim substring of the response body; the handler validates
that and drops the offending span if it is not (`09` §9.7.7 check `V3`), because a paraphrase
presented as a quote is the same class of error as an unsourced claim in a message. The spans land in
`audit_log.detail_json.evidence_spans` and in the highlight ranges on `/responses/<id>`, **not** in a
`responses` column — `01` §1.9.1 has no column for them, and this document does not request one.

**`OPT_OUT` is special.** When the model returns `OPT_OUT`, or when the deterministic pre-pass in
`radar/classify.py` matches an unsubscribe phrase, the `suppressions` insert happens in the **same
transaction** as the classification update, covering every contact point of that business per
`_CONTEXT.md` §3 invariant 3. The model is not the only gate: the deterministic pre-pass runs first
and can set `OPT_OUT` without any API call at all, so an opt-out is honoured even when the Gemini API
is unreachable, when the day's free-tier quota is exhausted, and when the laptop has no network at
all. A classifier that is down must never be able to delay an opt-out — and on this stack that
deterministic pre-pass, together with `09` §9.4's `E9`, **is** the entire unsubscribe mechanism, since
there is no HTTPS endpoint a recipient could click instead.

### 14.8.16 `create_handoff` (§34)

Behaviour owned by `10-human-handoff.md`; job properties here. Note the name: this document's
registry uses `create_handoff` and `send_notification`, which `10-human-handoff.md` §10.11 calls
`handoff_create` and `handoff_notify`. See Open questions.

| | |
|---|---|
| **Trigger** | `classify_response`, when `evaluate_triggers()` returns a decision |
| **Payload** | `{"response_id","business_id","trigger_rule_id","priority":"NORMAL"}` |
| **Dedupe key** | `create_handoff:{response_id}` |
| **Duration** | < 500 ms plus brief assembly |
| **Retries** | 5, `fast` |
| **Writes** | `handoffs` (via the `NOT EXISTS` insert in `10-human-handoff.md` §10.6.3), `businesses.status` -> `HUMAN_HANDOFF`, a `send_notification` job |
| **Idempotency** | Three layers: the dedupe key, the partial unique index `ux_handoffs_open_business`, and the `NOT EXISTS` insert. On `IntegrityError` the handler calls `attach_response()` and returns `Done` |
| **Failure mode** | If it never runs, the lead exists as a classified `responses` row and `handoff_sla_sweep` does not see it — so `staleness_sweep` also looks for classified trigger-worthy responses with no handoff and enqueues the missing job. Two independent paths to the same row, because this is the most valuable event in the system |

### 14.8.17 `send_notification` (§34)

| | |
|---|---|
| **Trigger** | `create_handoff`, `handoff_sla_sweep`, the job alert rules (§14.12.3), the quota ceiling (§14.10.5), `daily_report` |
| **Payload** | `{"kind":"HANDOFF"|"JOB_ALERT"|"QUOTA"|"DIGEST"|"BACKUP","subject_id":"…","reason":"CREATED","priority":"NORMAL"}` |
| **Dedupe key** | `send_notification:{kind}:{subject_id}:{reason}:{window_slot}` |
| **Duration** | 0.3-3 s |
| **Retries** | 3, backoff `0 s, 30 s, 120 s` (fixed, matching `10-human-handoff.md` §10.6.1) |
| **Lease expiry** | `FAIL` — a page about a stale event is noise; the sweep re-raises what still matters |
| **Writes** | `handoffs.notify_count`, `handoffs.telegram_message_id`, `handoffs.last_notified_at`, an `audit_log` row for `JOB_ALERT` and `QUOTA` |
| **Failure mode** | Telegram exhausted -> email-to-self fallback inside the same attempt -> if that also fails, `FAILED` and the underlying row (handoff, alert) still stands and still shows in the UI. A notification failure never deletes the thing it was about |

Quiet hours, per-handoff caps and the global hourly cap are evaluated **inside this job**, not by its
callers, so every notification path is subject to them and no caller can accidentally bypass them by
calling the notifier directly. `radar/notify.py` is import-restricted to this handler and the CLI.

### 14.8.18 `daily_report` (§43)

| | |
|---|---|
| **Trigger** | Schedule, 07:35 IST; `POST /api/v1/reports/daily {"day":"2026-08-27"}` for a re-run |
| **Payload** | `{"day_ist":"2026-08-27","deliver":true}` |
| **Dedupe key** | `daily_report:{day_ist}` |
| **Duration** | 5-40 s |
| **Retries** | 3, `standard` |
| **Writes** | `report_exports` (`fmt='DAILY_HTML'`, `campaign_id = NULL`, `expires_at = NULL`), the file at `data/reports/daily/business_radar_daily_2026-08-27.html`, a `send_notification` job with `kind='DIGEST'` |
| **Idempotency** | Keyed on the IST day. A manual re-run for the same day returns the existing export unless `"force": true`, which creates a second row with a `-r2` filename suffix — the archive never loses the first version |
| **Failure mode** | `FAILED` -> the 07:35 page does not arrive. §14.12.3's `schedule_missed` alert fires at 08:05, because the failure mode of "the daily report is silent" must not be silence |

Every §43 field, and the aggregate behind it. All are computed over the IST day; none is ever a
placeholder (`—` when there is no data):

| §43 field | Source |
|---|---|
| Date | The IST day being reported |
| Cities researched | `COUNT(DISTINCT city_slug)` over `businesses` joined to `research_runs` finished that day |
| Businesses discovered | `COUNT(*)` over `businesses.discovered_at` in the day |
| Businesses qualified | `COUNT(*)` where the current `opportunities.score >= campaigns.min_opportunity_score` and the run finished that day |
| Top opportunities | Top 10 by current `opportunities.score` among businesses discovered or scored that day — Rank, Business, City, Industry, Score, Potential System, Confidence, Verification (§44's shape, cut to 10 for a phone screen; the full Top 20 lives in the campaign report) |
| Businesses needing verification | `COUNT(*)` where `businesses.status = 'NEEDS_VERIFICATION'` — the whole backlog, not just today's, because the backlog is the number that decides Sagar's morning |
| Businesses ready for outreach | `COUNT(*)` where `status = 'CONTACT_READY'` and no live suppression |
| Outreach sent | `COUNT(*)` over `outreach_messages.sent_at` in the day, split by channel |
| Responses | `COUNT(*)` over `responses.received_at` in the day, grouped by `classification` |
| Interested leads | `COUNT(*)` where `classification IN ('INTERESTED','VERY_INTERESTED','DEMO_REQUESTED','MEETING_REQUESTED','PRICE_REQUESTED')`, listed individually with their handoff state |

Ordering on the page follows `10-human-handoff.md` §10.6.5: what needs a human first, what is in
flight second, research volume last. The Telegram message is a short digest with the counts and the
handoff list; the HTML file is the full version, archived under §42 and linked from the digest.

**Why 07:35 IST.** Quiet hours in `10-human-handoff.md` §10.6.4 end at 07:30, so a 07:35 delivery is
the first audible notification of the day — Sagar reads it at breakfast rather than finding it under
nine hours of silent messages. It is also after the overnight research window (01:15-06:00, §14.9.1),
so the numbers are the finished night's, and it is well before a 09:30 workday start, so the
verification queue is known before the day is planned. Generating it earlier would report a night
that was still running; generating it later would mean the day's first decision is made without it.

### 14.8.19 Types this document registers on behalf of other documents

| Type | Owner | Job properties |
|---|---|---|
| `handoff_sla_sweep` | `10-human-handoff.md` §10.4.3 | notify lane, every 5 min, dedupe `handoff_sla_sweep:{slot_iso}`, 3 attempts, writes `handoffs.sla_*` and enqueues `send_notification`; also finds handoffs with `notify_count = 0` past their ack window — the crash-between-insert-and-notify recovery |
| `telegram_poll` | `10-human-handoff.md` §10.6.1 | notify lane, continuous, `getUpdates` long-poll with a 60 s timeout inside a 90 s job timeout, offset persisted in `config/state/telegram_offset.json` (atomic write), re-arms by resetting its own row's `state` to `QUEUED` rather than enqueuing a new one. Only registered when `notify.telegram.mode == "polling"` |
| `score_calibration` | `10-human-handoff.md` §10.10.3 | llm lane, monthly, reads `v_outcome_labels`, writes a proposal file under `data/calibration/` and **applies nothing**; enqueues a `send_notification` pointing at the proposal |

### 14.8.20 `staleness_sweep`

The re-verification job. Five independent passes, each capped so a backlog cannot produce a thousand
jobs in one night.

| Pass | Finds | Does | Cap |
|---|---|---|---|
| Research staleness | `businesses.last_researched_at < now - research.ttl_days` (default 90) and `status NOT IN ('REJECTED','SKIPPED','HUMAN_HANDOFF')` | Enqueues `research_business` with `reason='STALE'`, priority 150 | `sweep.max_research_per_night` (default 25) |
| Verification staleness | `verifications.verified_at < now - verify.ttl_days` (default 45) and the business has not been contacted since | Writes an `audit_log` row and asks `radar/verify.py` to move the business back to `NEEDS_VERIFICATION`. This document does **not** perform the status transition itself — `04-verification-workflow.md` owns which transitions are legal | `sweep.max_reverify_per_night` (default 50) |
| Source re-check | `sources.checked_at < now - research.source_ttl_days` (default 120) for sources cited by a `CONTACT_READY` business | Enqueues a light `research_business` with `depth='STANDARD'` | Shares the research cap |
| Orphan repair | Classified responses with a trigger-worthy classification and no `handoffs` row; `QUEUED` `outreach_messages` older than 24 h with no live `send_email` job; campaigns in a live status with no outstanding jobs | Enqueues the missing job; logs `WARNING` naming each orphan | 100 |
| Counter reconciliation | Live campaigns whose six §2 counters disagree with the aggregates | Rewrites them; logs `WARNING` with both values | — |

| | |
|---|---|
| **Trigger** | Schedule, 01:00 IST |
| **Payload** | `{"slot":"…","passes":["research","verify","sources","orphans","counters"]}` |
| **Dedupe key** | `staleness_sweep:{slot_iso}` |
| **Duration** | 10-120 s (it enqueues; it does not do the work) |
| **Retries** | 3, `maint` backoff |
| **Failure mode** | A missed night means work is one day staler. Nothing is lost, and the next night's pass finds a slightly larger set |

Verification staleness deserves its justification: a business verified in March and never contacted
is not a business whose contact details were checked yesterday. `_CONTEXT.md` §3 invariant 1 is about
a human approval existing; §16's checklist is about that human having looked at something *current*.
A 45-day-old tick on "contact information appears to be a legitimate business contact" is not
evidence about today, so the business goes back into the verification queue rather than staying
`CONTACT_READY` indefinitely.

### 14.8.21 `suppression_sync`

| | |
|---|---|
**Changed for the free stack: there is no provider suppression list to sync with.** Gmail over SMTP
with an App Password (`_CONTEXT.md` §4) has no suppression API, no bounce API and no feedback loop —
those are ESP features and there is no ESP. The job is kept, with the same name, schedule and dedupe
key, but its two directions collapse to one **local** reconciliation pass.

| | |
|---|---|
| **Trigger** | Schedule, 02:00 IST; also on demand after a bounce spike |
| **Payload** | `{"slot":"…","since":"2026-08-26T00:00:00Z"}` |
| **Dedupe key** | `suppression_sync:{slot_iso}` (continuations append `:{cursor}`) |
| **Duration** | 1-20 s |
| **Retries** | 3, `standard` |
| **Writes** | `suppressions` (repair inserts), an `audit_log` row when it writes anything |
| **Idempotency** | Inserts are `ON CONFLICT DO NOTHING` against `ux_suppressions_live` |
| **Failure mode** | A missed night costs nothing, which is why it is `catch_up = SKIP` (§14.9.1): every suppression it would have written was already written by the path that produced the evidence; this job only catches the case where that write was lost |

What it reconciles, now that there is no remote list:

| Finds | Writes | Why the primary path could miss it |
|---|---|---|
| A `responses` row classified `OPT_OUT` or `COMPLAINT`, or with `contains_opt_out`, that has no live `suppressions` row for its contact | The missing suppression | A crash between the classification commit and the fan-out. `09` §9.9.4 makes those one transaction, so this should find nothing — and "should find nothing" is exactly the kind of claim that needs a job checking it |
| An `outreach_events(BOUNCED)` with a `5.x.x` status and no `BOUNCE_HARD` suppression | The missing suppression | Same, for `poll_inbox`'s DSN path (§14.8.13) |
| A `suppressions` row whose `contact_id` no longer resolves | An `audit_log` row and a `WARNING`; **never a delete** | A contact row was replaced. A suppression that has lost its anchor still suppresses (`05` matches on the normalised value as well as the id), and deleting it would be the one bug this whole subsystem exists to prevent |

**Why this is not simply deleted along with the webhook.** Because it now tests an invariant rather
than mirroring a third party. `_CONTEXT.md` §3 invariant 3 says opt-out is absolute; the primary
paths write it in the same transaction as the evidence, and this job is the nightly proof that they
did. If it ever writes a row, something upstream is broken and the `audit_log` entry is the first
evidence of it. A reconciliation job that finds nothing every night for a year is not a job that
should be removed — it is the job doing its work.

The one thing genuinely lost with the ESP is the **pull** direction's original purpose: a recipient
who unsubscribed through a provider-hosted page we never saw. `06-message-engine.md` §6.4 replaces
that mechanism entirely with the `mailto:` unsubscribe, which arrives in our own mailbox, so there is
no longer a place an opt-out can be recorded that we cannot see.

Neither direction can ever **clear** a suppression. `_CONTEXT.md` §3 invariant 3 makes opt-out
permanent and clearable only by a manual database operation with an audit row; the sync job runs with
a connection whose only write to `suppressions` is `INSERT`, and a trigger on the table rejects any
`UPDATE OF released_at` that lacks an audit id (`05-outreach-workflow.md` §5.3.2).

### 14.8.22 `backup_db`

| | |
|---|---|
| **Trigger** | Schedule, 00:20 IST; weekly variant Sunday 03:10 with `{"verify": true}` |
| **Payload** | `{"slot":"…","verify":false,"offsite":true}` |
| **Dedupe key** | `backup_db:{slot_iso}` |
| **Duration** | 5-300 s depending on database size |
| **Retries** | 2, `maint` |
| **Writes** | `data/backups/radar-YYYYMMDD-HHMM.db.gz`, a `.sha256` sidecar, an `audit_log` row, a `send_notification` on failure **and** on the weekly success (a backup nobody ever hears about is a backup nobody trusts) |
| **Failure mode** | Disk full is the common one; the handler checks free space **before** starting and fails fast with "backup needs N MB, M MB free" rather than producing a truncated file |

```python
# VACUUM INTO takes a read lock only: the site stays up and writable during a backup.
conn.execute("VACUUM INTO ?", (str(tmp_path),))
# then: gzip -> sha256 -> os.replace into place -> rotate
```

`VACUUM INTO` rather than copying `radar.db` with `cp`: a file copy under WAL can capture a database
file plus an unrelated `-wal` file and produce a backup that will not open. `VACUUM INTO` writes a
consistent, already-compacted database from a read snapshot.

Rotation: `jobs.backup.keep_daily` 14, `keep_weekly` 8, `keep_monthly` 6. Offsite copy is
`rclone copy` or `scp` to whatever `jobs.backup.offsite_cmd` names, run as a subprocess with a
timeout; a failed offsite copy does not fail the job but does notify, because the local backup
succeeding is the part that matters most and the two failures deserve different urgency.

`{"verify": true}` additionally gunzips the newest backup into a temp file, opens it, runs
`PRAGMA integrity_check` and `SELECT COUNT(*)` on `businesses`, `outreach_messages` and `audit_log`,
and records the counts in `jobs.result`. An untested backup is a hypothesis.

### 14.8.23 `prune_logs`

| | |
|---|---|
| **Trigger** | Schedule, 00:40 IST — **after** `backup_db`, so anything pruned exists in a backup taken 20 minutes earlier |
| **Payload** | `{"slot":"…","dry_run":false}` |
| **Dedupe key** | `prune_logs:{slot_iso}` |
| **Duration** | 5-120 s |
| **Retries** | 2, `maint` |
| **Writes** | Deletes from `jobs` and `job_runs`; deletes aged raw inbound MIME under `data/inbound/`; deletes expired export files and flips those `report_exports` rows to `PURGED`; rotates `logs/radar.log`; deletes `data/tmp/` leftovers |
| **Failure mode** | Disk fills. The `disk_low` alert in §14.12.3 fires from the doctor timer, independently of this job running |

| Target | Retention key | Default | Never pruned |
|---|---|---|---|
| `jobs` rows in `SUCCEEDED` | `jobs.retention.success_days` | 30 | `type IN jobs.retention.never_prune` (default `["send_email"]`) |
| `jobs` rows in `FAILED`/`DEAD`/`CANCELLED` | `jobs.retention.failed_days` | 180 | as above |
| `job_runs` | cascade from `jobs` | — | — |
| `data/inbound/*` raw MIME | `jobs.retention.inbound_days` | 14 | The `responses` row survives; only the raw file is deleted and `body_html_path` is nulled. `body_text` — the evidence a classification rests on — is a column and is never touched. **Replaces** the old `process_webhook_event.payload` blanking (§14.6.3) |
| `report_exports` files with `expires_at < now` | per row | 30 for CSV/XLSX/PDF | HTML and DAILY_HTML (`expires_at IS NULL`) |
| `logs/radar.log` | `logging.rotate_days` | 30 | — |
| `data/tmp/*` | age > 24 h | — | — |
| **`audit_log`, `outreach_*`, `responses`, `handoffs`, `suppressions`, `businesses`, `research_*`, `opportunities`, `spend_ledger`** | — | — | **Never touched by this job.** §48 wants outreach audit records to behave as immutable, DPDP erasure is a deliberate, audited operation and not a scheduled cleanup, and a suppression that expires is a suppression that stops working |

`--dry-run` prints the counts and deletes nothing. The scheduled row runs with `dry_run: false`; the
CLI defaults to `true`, because the version of this command a human types at 1 a.m. should be the
safe one.

---

## 14.9 Scheduling

### 14.9.1 The schedule, in IST

Seeded into `job_schedules` by `034_seed_job_schedules.sql`. `cron_expr` is a 5-field expression
evaluated in `tz`; `every_seconds` is a fixed interval from the last tick.

**Changed for the free stack.** Every row now carries a **grace** as well as a catch-up policy, and
the two together are the per-job answer to "the laptop was shut when this slot came round" — which,
on this deploy target, is the normal case rather than an incident. §14.9.2 explains the mechanism;
this table gives the decision and the reason for each job.

| Type | Expression | IST time | Jitter | Catch-up | Grace | Why this slot |
|---|---|---|---|---|---|---|
| `backup_db` | `20 0 * * *` | 00:20 daily | 60 s | `ONCE` | **none** | After the IST day rolls over, so a backup contains a complete previous day. Before the research window, so it never competes with the heaviest write phase. |
| `prune_logs` | `40 0 * * *` | 00:40 daily | 60 s | `SKIP` | — | 20 minutes after the backup, so everything it deletes already exists in a backup taken tonight. |
| `staleness_sweep` | `0 1 * * *` | 01:00 daily | 120 s | `ONCE` | **none** | Enqueues the night's re-research just before the window opens. |
| — (window) | — | 01:15-06:00 | — | — | — | The `llm` lane runs at `jobs.limits.llm_concurrency_night` (3) instead of the daytime 1. **On a laptop this window is aspirational**: it is a concurrency setting that applies if the machine happens to be awake, never a promise that work happens overnight. |
| `suppression_sync` | `0 2 * * *` | 02:00 daily | 300 s | `SKIP` | — | Inside the window. Missing a night costs nothing: local suppression is already enforced (§14.8.21). |
| `backup_db` (verify) | `10 3 * * 0` | Sun 03:10 | 60 s | `SKIP` | — | Weekly restore test, deep in the quiet period. Same type, `{"verify": true}` payload, driven by the handler's weekday check (see the note below). |
| `score_calibration` | `30 3 1 * *` | 1st, 03:30 | 300 s | `ONCE` | **7 days** | Monthly, after a full month of outcomes exists. |
| `daily_report` | `35 7 * * *` | 07:35 daily | 0 | `ONCE` | **14 hours** | Five minutes after quiet hours end (07:30), so it is the first audible message of the day and lands before work. §14.8.18. **Jitter is zero on purpose**: a report that arrives at a different time every morning stops being a routine. |
| `poll_inbox` | `every_seconds: 120` | every 2 min | 15 s | `SKIP` | — | Reply latency Sagar can live with, against a mailbox that costs nothing to poll. |
| `handoff_sla_sweep` | `every_seconds: 300` | every 5 min | 30 s | `SKIP` | — | `10-human-handoff.md` §10.4.3. |
| `telegram_poll` | `every_seconds: 60` | continuous | 0 | `SKIP` | — | Only in polling mode; the job long-polls for 60 s and re-arms itself. |
| `campaign_finalize` | not scheduled | — | — | — | — | Self-rescheduling per live campaign, §14.8.6. |

**The grace column, job by job, with the reasoning.** This is the part a reader should disagree with
if they are going to disagree with anything, so each one is argued rather than asserted.

| Job | Rule | Argument |
|---|---|---|
| `backup_db` | `ONCE`, no grace — **always run it, however late** | A backup missed by eighteen hours is still the only backup of eighteen hours of work. There is no staleness at which "do not back up" becomes the right answer. It runs first, before the catch-up enqueues anything else, so a launch that then crashes still leaves a backup. |
| `staleness_sweep` | `ONCE`, no grace | It only *enqueues*; the work it schedules is idempotent and capped per night. Three missed nights produce one sweep that finds a slightly larger set, which is exactly right — running it three times would produce the same set three times and burn the caps. This is the case the task of "missed three times should run once" describes, and `ONCE` already expresses it. |
| `daily_report` | `ONCE`, **14 h grace** | The report is a summary of an IST day. Run at 09:40 for the 07:35 slot it is a slightly late morning report and entirely useful. Run at 23:00 it would arrive after the day it describes has ended and would compete with tomorrow's, so past 14 hours the slot is dropped and the next 07:35 covers it. 14 h, not 12 h: the boundary should fall in the evening, not in the middle of the working day. **Note the second effect:** the report is `ONCE`, so opening the laptop on Wednesday after being shut since Monday produces **one** report — Wednesday morning's — and not two. Tuesday's numbers are not lost; they are in the database and in the campaign report. A digest is a notification, and re-notifying about Tuesday on Wednesday is noise. |
| `score_calibration` | `ONCE`, **7 day grace** | Monthly and advisory: it writes a proposal file and applies nothing (§14.8.19). Running the 1st-of-month job on the 4th is fine. Running it on the 25th means the proposal lands a week before the next one, so it is dropped. |
| `prune_logs` | `SKIP` | Deletes by age. A missed run means rows live one day longer, and tomorrow's run deletes them. Never worth catching up, and catching it up would run a delete pass against a database Sagar is actively using. |
| `suppression_sync` | `SKIP` | Reconciliation, not enforcement. Local suppression already blocks the send (`05` gate G); this job only mirrors state. A missed night self-heals. |
| `backup_db (verify)` | `SKIP` | A restore test is only meaningful on a quiet machine. Running it at 11:00 on a laptop Sagar is working on would decompress a full database into `data/tmp/` and compete for the disk. Next Sunday will do. |
| `poll_inbox` | `SKIP` | The mailbox **is** the queue. One poll collects everything that arrived while we were off; running the 340 missed 2-minute slots would run 339 no-ops behind it. |
| `handoff_sla_sweep` | `SKIP` | It recomputes from current state on every run, so the current slot subsumes every missed one. |
| `telegram_poll` | `SKIP` | Long-poll; `getUpdates` returns the backlog on its own with its persisted offset. |

Two rules that fall out of the table and are worth stating separately because they generalise:

1. **A job that recomputes from current state is always `SKIP`.** `handoff_sla_sweep`, `poll_inbox`,
   `suppression_sync` and `telegram_poll` all read the world and act on what they find; the newest
   run strictly dominates every older one. Only jobs whose output is *about a specific past interval*
   (`daily_report`) or that *must have happened at all* (`backup_db`) can be `ONCE`.
2. **A grace is a statement about the output's shelf life, not about how late is tolerable.** The
   question to ask of a new job is "is the artefact this produces still worth having?" — not "how
   overdue is it?". A backup has infinite shelf life, a daily digest has about a day, a monthly
   proposal has about a week.

The `backup_db` weekly-verify row is the one place the "one schedule per type" rule (§14.3.4) needs a

The `backup_db` weekly-verify row is the one place the "one schedule per type" rule (§14.3.4) needs a
carve-out. It is handled without breaking the rule: the daily row's payload is
`{"verify": false, "verify_on_weekday": 0}`, and the handler itself sets `verify=true` when the IST
weekday matches. One schedule row, one dedupe namespace, and the weekly behaviour lives with the
handler that implements it.

**Send windows are not schedules.** `send_email` is enqueued the moment Sagar confirms, and the
window check happens in the handler (§14.9.3). Queuing a send for 09:30 would mean an approval sitting
in `APPROVED` for fourteen hours with nothing visible happening.

### 14.9.2 The scheduler tick

The scheduler is not a thread. It is a function, `materialise_due_schedules(conn, now)`, called at
the top of every `maint` lane loop iteration, once at startup (§14.5.1 step 7), and once on resume
from suspend (§14.5.6). No separate timer means no separate thing to crash, and a `maint` lane that
is alive is by definition scheduling.

**The startup call is not a corner case on this deploy target.** On a VPS it fired after a deploy or
a crash. On Sagar's laptop it fires every morning, with a real backlog, and it is the only thing
standing between "the machine was off from 21:00 to 09:40" and "nothing that was supposed to happen
overnight happened, and nothing says so".

```python
def materialise_due_schedules(conn: sqlite3.Connection, now: datetime) -> int:
    """Turn every due schedule row into a jobs row. Idempotent by dedupe key."""
    created = 0
    for sch in _enabled_schedules(conn):
        slots = _due_slots(sch, now)              # [] when nothing is due
        for slot in _apply_catch_up(sch, slots, now):
            with db.transaction(conn):            # BEGIN IMMEDIATE
                res = enqueue(
                    conn, sch.type, json.loads(sch.payload) | {"slot": iso(slot)},
                    dedupe_key=f"{sch.type}:{iso(slot)}",
                    priority=sch.priority,
                    run_after=slot + timedelta(seconds=random.randint(0, sch.jitter_seconds)),
                    on_conflict="ignore",
                )
                conn.execute(
                    "UPDATE job_schedules SET last_tick_at=?, last_job_id=?, updated_at=? WHERE id=?",
                    (iso(slot), res.job_id, iso(now), sch.id),
                )
            created += int(res.created)
    return created
```

The dedupe key **is** the scheduling guarantee. `last_tick_at` is bookkeeping for the catch-up
calculation and for the UI; if it were lost or wrong, the unique index would still prevent a second
job for a slot that already has one. Two workers materialising the same tick concurrently is
therefore a no-op for the loser, which is what makes the standalone topology safe without a leader
election.

| `catch_up` | Behaviour after downtime | Used by |
|---|---|---|
| `SKIP` | Only the current slot is materialised; missed slots are gone. | `poll_inbox`, `handoff_sla_sweep`, `prune_logs`, `suppression_sync`, `telegram_poll`, `backup_db (verify)` — running four missed inbox polls at once achieves nothing the current one will not. |
| `ONCE` | The **most recent** missed slot runs, once, then normal scheduling resumes. Older missed slots are dropped without running. | `backup_db`, `staleness_sweep`, `daily_report`, `score_calibration` — a missed backup should still happen; four missed backups should not all happen. |
| `ALL` | Every missed slot is materialised. | Nothing uses it today. It exists for a future per-day job whose output must exist for every day, and it is capped at `jobs.schedule.max_catch_up` (default 7) so a week of downtime cannot enqueue a year. |

**Catch-up-on-launch.** `catch_up` decides **how many** missed slots run. `catch_up_grace_minutes` (§14.3.4) decides
**whether the one it chose is still worth running**. Both are needed, and neither substitutes for the
other: `ONCE` with no grace runs an eleven-hour-stale daily report, and a grace with no `ONCE` would
run six stale backups inside the window.

```python
def _apply_catch_up(sch: Schedule, slots: list[datetime], now: datetime) -> list[datetime]:
    """Decide which missed slots actually become jobs. Pure; every branch is table-tested.

    `slots` is every slot between last_tick_at and now, oldest first, and on this deploy
    target it is routinely 300+ entries long (a 2-minute schedule across a night). The
    function is called on every maint loop iteration, so it must be cheap when the answer
    is "just the current one", which is the overwhelmingly common case.
    """
    if not slots:
        return []

    current, missed = slots[-1], slots[:-1]

    if sch.catch_up == "SKIP" or not missed:
        return [current]

    if sch.catch_up == "ONCE":
        candidate = missed[-1]                      # the most recent missed slot only
    else:                                           # ALL
        cap = cfg.get("jobs.schedule.max_catch_up", 7)
        return _within_grace(sch, missed[-cap:], now) + [current]

    return _within_grace(sch, [candidate], now) + [current]


def _within_grace(sch: Schedule, slots: list[datetime], now: datetime) -> list[datetime]:
    """Drop slots that are too stale to be worth running.

    grace == 0 means "no expiry": run it however late. That is not the same as SKIP, and
    the difference is the whole point of having two columns.
    """
    if sch.catch_up_grace_minutes == 0:
        return slots
    cutoff = timedelta(minutes=sch.catch_up_grace_minutes)
    kept, dropped = [], []
    for s in slots:
        (kept if now - s <= cutoff else dropped).append(s)
    for s in dropped:
        log.info("schedule %s: dropping missed slot %s, %.1f h stale > %d min grace",
                 sch.type, iso(s), (now - s).total_seconds() / 3600,
                 sch.catch_up_grace_minutes)
    return kept
```

**`current` is always materialised**, whatever the catch-up policy says, because the current slot is
not a missed slot. A grace window can never suppress a job that is due now.

**Worked example, the ordinary Tuesday.** Laptop shut 21:10 Monday, opened 09:40 Tuesday. Startup
step 7 calls `materialise_due_schedules`, and this is the whole of what it decides:

| Schedule | Missed slots | Decision | Runs? |
|---|---|---|---|
| `backup_db` | Mon 00:20 already ran; Tue 00:20 missed | `ONCE`, grace 0 -> keep Tue 00:20 | **yes**, at 09:40 |
| `prune_logs` | Tue 00:40 | `SKIP` | no. Tomorrow's run deletes the same rows plus a day |
| `staleness_sweep` | Tue 01:00 | `ONCE`, grace 0 -> keep | **yes**. Enqueues the re-research it would have enqueued at 01:00, against a slightly larger set |
| `suppression_sync` | Tue 02:00 | `SKIP` | no |
| `daily_report` | Tue 07:35 | `ONCE`, 2.1 h old, inside the 14 h grace -> keep | **yes**. Sagar gets his morning digest at 09:40 |
| `poll_inbox` | ~375 slots | `SKIP` | one poll, which collects every reply that arrived overnight |
| `handoff_sla_sweep` | ~150 slots | `SKIP` | one sweep, which recomputes every SLA from current state |

Seven schedules, four jobs, no duplicates, and the one artefact with a shelf life (the digest) landed
inside it. Contrast the same launch at 23:30 instead of 09:40: `daily_report`'s Tuesday 07:35 slot is
15.9 h stale, past its grace, so it is dropped with an `INFO` line and Wednesday's 07:35 covers it —
while `backup_db` and `staleness_sweep`, which have no grace, still run.

**Ordering within the catch-up.** `_enabled_schedules()` returns rows ordered by
`priority DESC, type ASC`, and the catch-up materialises in that order inside one pass. That puts
`backup_db` ahead of `staleness_sweep`, which matters: the sweep enqueues research that will start
writing, and a backup taken before it reflects the state the previous session ended in. It is the
only ordering constraint, and it is a property of the priority column rather than a special case.

`_due_slots` computes in the schedule's `tz` and returns UTC instants. The IST fixed offset means no
DST discontinuities — no skipped 02:30, no doubled slot — which is why the whole schedule is
expressed in one timezone and why `tz` is nonetheless a column: if a second operator in another zone
ever exists, the DST-correct path is `zoneinfo` from day one rather than a retrofit.

### 14.9.3 Send windows and quiet hours

Two different clocks, for two different audiences.

| Clock | Applies to | Config | Behaviour outside |
|---|---|---|---|
| **Send window** | `send_email` (outbound, to a prospect) | `outreach.send_window: {days: [MON..SAT], start: "09:30", end: "18:30", tz: "Asia/Kolkata"}` | `Defer(run_after = next window open)`. No attempt consumed, `outreach_messages` stays `QUEUED`, the workspace shows "will send at 09:30 IST tomorrow". |
| **Quiet hours** | `send_notification` (inbound, to Sagar) | `notify.quiet_hours` (`10-human-handoff.md` §10.6.4) | Delivered silently or audibly by priority. **Never deferred, never dropped.** |

The asymmetry is the point. A business email arriving at 03:00 reads as a machine, and on this stack
that is worse than it used to be: there is no sending domain of our own to damage, so what a
machine-shaped send pattern damages is the **free Gmail account's standing with Google**
(`_CONTEXT.md` §4), and the remedy for a closed account is to abandon it. A Telegram message to Sagar
at 03:00 costs a moment of sleep and may save a lead. Outbound is delayed; inbound is muted.

One consequence of the laptop: **the send window is now a filter on when the machine is on, not only
on when it is polite to send.** A message approved at 22:00 is queued for 09:30, and if the laptop is
shut until 10:15 it goes at 10:15. That is correct and needs no code — the window check runs in the
handler when the job is claimed — but it means the "will send at 09:30 IST tomorrow" text in the
workspace is a best case. It says "on or after".

The window also caps the practical daily volume in a way the token bucket alone would not: nine
working hours against `email.hour` at 8/h and `email.day` at 40/day means the day bucket is the
binding constraint, which is the intended order. Note that neither bucket is the real ceiling on this
stack — `_CONTEXT.md` §4's policy figure of **15-25 sends a day** is, and it is set by the AUP
argument rather than by any mechanism. `07-email-integration.md` owns the bucket values; this
document only guarantees that whatever they are set to is enforced by a table read by different code
than the policy that chose them.

---

## 14.10 Rate limiting and quota control

### 14.10.1 The buckets

Ten rows in `rate_buckets`, seeded from `jobs.limits` at startup. Every one is shared by every
worker thread and survives a restart, because it is a database row rather than a process variable.

**Changed for the free stack:** the three provider buckets are replaced by three Gemini buckets, and
the discovery bucket is replaced by two, because OSM discovery talks to two services with very
different published limits.

| Bucket | Capacity | Refill | Guards |
|---|---|---|---|
| `llm.gemini.rpm` | 10 | 10/60 per s | Gemini free-tier requests per minute. **One bucket for the whole application** — research, drafting and classification all take from it, because the free-tier limit is per project, not per call site. Three separate buckets would each believe they had the whole allowance, and the first sign of the mistake would be a 429 storm |
| `llm.gemini.tpm` | 250000 | 250000/60 per s | Gemini free-tier tokens per minute; charged with the `count_tokens` result (§14.10.2) |
| `llm.gemini.rpd` | 250 | 250/86400 per s | Gemini free-tier requests per day. A day bucket rather than a `COUNT(*)`: it refills continuously instead of resetting at a boundary, which is a closer approximation to a rolling limit than midnight arithmetic and needs no timezone decision (§14.3.5) |
| `llm.global.concurrent` | 3 | — | Not a bucket: the `llm` lane's thread count, 1 by day and 3 in the night window |
| `email.hour` | 8 | 8/3600 per s | Gmail account standing; an account that emits 40 messages in a minute is an account with a spam problem |
| `email.day` | 40 | 40/86400 per s | Mechanical ceiling under the policy figure, `_CONTEXT.md` §4's 15-25/day. Owned by `07-email-integration.md` |
| `email.domain.day` | 2 | 2/86400 per s | Per recipient eTLD+1, created lazily as `email.domain.{etld1}.day`. Two cold emails a day to one company is already generous |
| `discovery.nominatim.rps` | 1 | 1/1 per s | **Nominatim's published usage policy is an absolute maximum of 1 request per second**, and it is enforced by them with bans, not with 429s. `_CONTEXT.md` §4 also requires a real `User-Agent`. This bucket is the one in the table whose limit is a condition of being allowed to use a free public service at all |
| `discovery.overpass.rpm` | 6 | 6/60 per s | Overpass public instances are shared, unmetered and easy to abuse. 6/min with a burst of 6 keeps a city sweep polite; the handler also backs off hard on a 429 or a 504 |
| `telegram.rpm` | 20 | 20/60 per s | Telegram's own limit |

Capacity equals burst. `email.hour` with capacity 8 means eight approvals confirmed in one minute all
transmit immediately and the ninth waits — deliberate, because Sagar approving a batch by hand should
not be throttled into next week, while a loop that tries to send 500 hits the wall at eight.

`llm.gemini.rpm` at capacity 10 is the bucket that will actually be felt. A drafting batch of twenty
messages is 40 requests (§6.13.6) and therefore at least four minutes of wall clock. That is fine and
is not worth engineering around: nothing is waiting on it, and §14.10.3 makes a full bucket a
deferral rather than a stall.

### 14.10.2 Taking a token

One statement, atomic, no read-modify-write in Python:

```sql
-- radar/jobs.py :: take_tokens  (inside BEGIN IMMEDIATE)
UPDATE rate_buckets
   SET tokens = MIN(capacity,
                    tokens + (julianday(:now) - julianday(updated_at)) * 86400.0 * refill_per_sec)
                - :cost,
       updated_at = :now
 WHERE name = :name
   AND MIN(capacity,
           tokens + (julianday(:now) - julianday(updated_at)) * 86400.0 * refill_per_sec) >= :cost
RETURNING tokens;
```

An empty `RETURNING` means the bucket could not pay. The caller computes an ETA and defers:

```python
def take(conn, name: str, cost: float = 1.0) -> TakeResult:
    """Take `cost` tokens or report when they will exist. Never blocks, never sleeps."""
    # on failure: eta_seconds = (cost - current_tokens) / refill_per_sec, and
    # rate_buckets.last_empty_at is stamped so /settings can show "throttled since 14:02".
```

Two properties worth stating:

- **Lazy refill.** No timer refills buckets; the elapsed time since `updated_at` is converted to
  tokens inside the same statement that spends them. A worker that was down for an hour finds a full
  bucket, correctly, with no catch-up job.
- **No sleeping inside a job.** A handler that hits an empty bucket returns `Defer`, releases its
  lease and frees the thread. Sleeping would hold a lease and a thread to accomplish nothing, and on
  a one-thread lane it would deadlock the lane behind a bucket that only a different job can refill.

LLM calls charge **three** buckets, not two. `llm.gemini.rpm` takes 1 and `llm.gemini.rpd` takes 1.
`llm.gemini.tpm` takes the count from `client.models.count_tokens(model=…, contents=…)` before the
call, and the difference between that count and `usage_metadata.prompt_token_count` is settled
afterwards by taking or returning the delta. Counting first is what keeps the bucket honest under
concurrency; settling afterwards is what keeps it accurate. `ctx.llm()` is the only place any of it
happens:

```python
class JobContext:
    def llm(self, *, model: str, prompt_version: str, **kwargs) -> LLMResult:
        """The only way a job may call Gemini.

        Enforces the three rate buckets, the daily quota ceiling, quota-unit
        recording, and the _CONTEXT.md 2 rule that model id, prompt version and
        token counts are stored with every output. Also runs the 06 6.13.0
        contact scrubber over the assembled payload, so the PII rule cannot be
        bypassed by a call site that forgot it.

        A job that constructs its own client bypasses all five, so a test asserts
        no module under radar/ imports google.genai except radar/llm.py - and a
        second test asserts nothing under radar/ imports anthropic at all.
        """
```

The `genai.Client` is constructed once, in `radar/llm.py`, with SDK retries disabled and an explicit
timeout. Decision 7 in §14.1: an SDK-internal retry spends a request against a daily allowance that
nothing accounted for, burns lease time invisibly, and leaves no `job_runs` row. Retries belong to
the runtime that owns the ledger — and on a metered free tier that is not a preference, it is the
difference between "we used 180 of 250 today" being true and being fiction.

Putting the contact scrubber (`06-message-engine.md` §6.13.0) in `ctx.llm()` as well as at the
prompt-assembly site is deliberate belt-and-braces. `06` runs it where the context is built, because
that is where a useful error message can be produced; `ctx.llm()` runs it again on the final payload,
because that is the last place anything can be stopped. Two call sites, one function, and the second
one cannot be forgotten by a new job type.

### 14.10.3 What a job does when a bucket is empty

| Bucket | Handler | Consumes an attempt | Visible as |
|---|---|---|---|
| `llm.gemini.rpm` / `llm.gemini.tpm` | `Defer(now + eta, "BUCKET_EMPTY")` | No | Campaign progress note: "throttled, resuming in ~40 s" |
| `llm.gemini.rpd` | `Defer(now + eta, "QUOTA_EXHAUSTED")` and the §14.10.4 pause | No | The banner and the Telegram message in §14.10.5. The ETA here is hours, not seconds, and the UI must say so rather than showing a spinner |
| `discovery.nominatim.rps` / `discovery.overpass.rpm` | `Defer` | No | — |
| `email.hour` / `email.day` | `Defer(now + eta, "BUCKET_EMPTY")`, and `outreach_events(RATE_LIMITED)` | No | Workspace: "daily send limit reached, 3 messages queued for tomorrow 09:30" |
| `email.domain.day` | Same, but the ETA is up to 24 h | No | The same message naming the domain |

A `429` from a provider **also** drains the corresponding bucket to zero (`tokens = 0`,
`last_empty_at = now`) before deferring. The provider's opinion of our rate outranks our local
estimate of it, and treating a 429 as a plain retry is how a rate limit becomes a rate-limit storm.

On the free tier this rule needs one refinement, because there are two kinds of 429 and they want
opposite responses. `radar/llm.py::classify_429()` reads the error's `status`, `message` and any
`RetryInfo` to decide:

| Signal | Bucket drained | Defer to |
|---|---|---|
| The detail names a per-minute limit, or `RetryInfo.retryDelay` is under 120 s | `llm.gemini.rpm` | now + the stated delay, or the bucket ETA |
| The detail names a per-day limit, or `retryDelay` is hours, **or the response is ambiguous** | `llm.gemini.rpd` **and** the §14.10.4 pause | the next quota window |

The ambiguous case resolving to *per-day* is the important half. Guessing "per-minute" against a
per-day wall produces a job that retries every sixty seconds for the rest of the day, which is a
retry storm against a service that has already said no — and on a free tier, sustained hammering
after a quota refusal is exactly the behaviour that gets a key restricted.

### 14.10.4 The daily quota ceiling

**Changed for the free stack: this used to be a spend ceiling in rupees, protecting a prepaid
balance.** There is no balance. What there is, is a daily request allowance that returns
`429 RESOURCE_EXHAUSTED` when it runs out, and the job of this section is now to make that ceiling
arrive as a **planned pause** rather than as a surprise error in the middle of a campaign. The
shape of the mechanism is unchanged — check before the call, warn, hard-stop, pause, resume — because
the shape was right; only the unit changed, from money to requests.

```yaml
jobs:
  quota:
    daily_request_cap: 200      # our reserve. Below the published free-tier rpd (250) on purpose.
                                # Mirrors llm.daily_request_cap (06 6.13.6, 02 2.16) and is
                                # asserted equal to it at startup, so there is one number.
    warn_at_pct: 80
    hard_stop_pct: 100
    provider_limits:            # gemini-2.5-flash, Google AI Studio free tier.
      rpm: 10                   # VERIFY against the current rate-limits page before shipping;
      tpm: 250000               # Google changes these without notice. Mirrored in 06 6.13.6
      rpd: 250                  # and asserted equal at startup.
    email_quota_units: 1        # one send = one unit against Gmail's daily cap
    reserve:                    # who gets the allowance when it is short. 14.10.4 below.
      classify_response: 20     # never spend the last 20 on anything else
```

**One consumer has a tighter cap of its own, and it binds first.** `02-research-pipeline.md` §2.16
sets `research.quota.daily_request_cap` (default 150) as research's share of the 200, so that the
remaining 50 are still there for the drafting and classification Sagar waits on. `ctx.llm()`
therefore evaluates two ceilings for a `research_business` or `assess_opportunity` job — the research
share first, then the global cap — and either one raises the same `QuotaExhausted` with the same
deferral. The split is a **reservation, not a queue limit**: research stops at 150 even when drafting
is idle all day, because an idle afternoon is not evidence that no reply will arrive in the evening.

```python
def quota_units(kind: str, usage=None) -> int:
    """What this call cost the day, in the unit the day is measured in.

    One request is one unit. It is deliberately not weighted by tokens: the free tier's
    binding ceiling is a request count, and a unit that mixes two currencies is a unit
    nobody can reason about at a glance. Tokens are recorded separately in
    spend_ledger.units, and they are what proves a prompt has grown.
    """
    return 1


def tokens_charged(usage) -> int:
    """Everything the tier counts, including the part that is invisible in the answer."""
    return (usage.prompt_token_count
            + usage.candidates_token_count
            + (usage.thoughts_token_count or 0))
```

The published limits are config, not constants, and a missing limit is `KeyError` at startup rather
than a silent infinity — a quota model that believes it has unlimited requests because a key was
missing is worse than no quota model. The startup check in §14.5.1 step 3 already proves every pinned
model id resolves; a companion assertion proves `jobs.quota.provider_limits` matches
`06-message-engine.md`'s `llm.quota` byte for byte, so the two documents cannot drift.

**The gate.** `ctx.llm()` checks the ceiling *before* each call:

```
projected = v_spend_today.llm_requests + 1
  projected <  warn_at_pct  * daily_request_cap  -> proceed
  projected >= warn_at_pct  * daily_request_cap  -> proceed, and fire the QUOTA warning once per day
  projected >= hard_stop_pct * daily_request_cap -> raise QuotaExhausted

and, for the research share only (02 2.16):
research  = SUM(quota_units) today over spend_ledger joined to job_runs on job_run_id,
            WHERE job_runs.type IN ('research_business','assess_opportunity')
  job.type in that set AND research + 1 > research.quota.daily_request_cap
                                                 -> raise QuotaExhausted
```

The research share needs **no new column**: `job_runs.type` is denormalised (§14.3.3) precisely so
that a question about what kind of work spent the day can be answered by a join rather than by a
second copy of the type on `spend_ledger`.

`QuotaExhausted` is classified `QUOTA_EXHAUSTED` (§14.7.1) and becomes
`Defer(run_after = next quota window)`. It consumes no attempt, so a campaign paused by the ceiling
resumes on its own the next day exactly where it stopped, with its research jobs intact. **The
campaign is not in trouble; it is simply not finished today**, and that distinction is the whole
difference between this ceiling and the one it replaces. A spend ceiling meant "stop before this
costs more than you meant to spend". A quota ceiling means "there is no more today".

The first job to hit the hard stop also, in one transaction:

1. Sets every live campaign with outstanding `llm`-lane work to `status='PAUSED'`,
   `paused_reason='QUOTA_CEILING'`. That is an enum value, not a sentence:
   `01-data-model.md` §1.3.1 constrains the column to
   `('QUOTA_CEILING','MANUAL','PROVIDER_ERROR','RATE_LIMIT')`, and the human wording
   ("resumes automatically tomorrow") belongs to the banner in §14.10.5, not to the column.
2. Enqueues `send_notification` with `kind='QUOTA'`.
3. Writes an `audit_log` row.

Campaigns are paused rather than cancelled, and **only the LLM lane stops**: `send_email`,
`poll_inbox`, `classify_response`'s deterministic pre-pass, notifications, exports and the daily
report all keep working. A quota freeze must not stop Sagar from answering a lead that yesterday's
allowance already bought — and it must never stop an opt-out, which is why `09`'s stage 0 and stage 1
are outside this gate entirely (`09-response-classification.md` §9.3.2).

**The reserve, which is new.** Under a spend ceiling every LLM job was equally entitled to the money,
because money is fungible and Sagar could always raise the cap. Under a quota ceiling he cannot raise
anything: 250 requests is 250 requests. So the allowance has to be *allocated*, and the allocation is
one line of config and one clause in the gate:

```
if projected > daily_request_cap - reserve.get(job.type, 0) and job.type != 'classify_response':
    raise QuotaExhausted
```

`classify_response` keeps the last 20 requests of the day. The reasoning is the same asymmetry that
runs through the whole pack: research that does not happen tonight happens tomorrow and costs
nothing, while a reply that is not classified tonight is a lead sitting unread — and unlike research,
it has a human on the other end who is waiting. Nothing else has a reserve, because nothing else is
both cheap and time-critical.

What is explicitly **not** done: no automatic switch to a different model, no silent reduction in
research depth, no truncation of prompts, no dropping of sources to fit more businesses into the
allowance. `_CONTEXT.md` §3 invariant 5 and §53 both depend on two campaigns being comparable; a
system that quietly changes its own method when the allowance runs low produces a report whose
numbers mean different things in different rows, and nothing on the screen says so. Under a paid tier
that was a discipline about honesty. Under a free tier it is that **and** the only thing stopping the
obvious bad idea, which is "use a smaller model when quota is tight" — there is no smaller model, and
`06` §6.1 already argues that a weaker writer needs a *stricter* checker, not a looser one.

### 14.10.5 What Sagar sees when the ceiling is hit

Telegram, once per day per kind:

```
business_radar - quota

Daily Gemini allowance used at 14:06 IST.
  Used today    200 of 200 requests (free-tier limit 250)
  Research      148 requests, 31 businesses
  Drafting       32 requests, 9 messages
  Classifying     8 requests, 8 replies
  Reserved       20 requests, held for incoming replies

PAUSED
  "Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026"
  18 businesses still to research - they resume automatically tomorrow.

Still running: sending, replies, classification, reports.
Nothing is lost and nothing is owed. This is a free-tier limit, not a bill.

  /settings
```
SAMPLE.

In the web UI: a persistent amber banner on `/campaigns` and `/settings` reading
"Daily Gemini allowance used (200 of 200 requests). Research is paused and resumes tomorrow." with
one control — **Raise today's reserve** (a one-day override up to the published `rpd`, `audit_log`
row, requires typing the new number, no default pre-filled). The old **Resume anyway** control is
**removed**: there is nothing to resume into. Overriding a spend cap spent more of Sagar's money and
that was his call to make; overriding a provider's quota just produces 429s, and a button whose only
effect is a different error message is a button that teaches the operator to distrust the UI.

`/settings` shows the last 30 days from `spend_ledger` grouped by day and kind — requests and tokens,
side by side — and the per-campaign totals from `ix_spend_campaign`, so "how much of the allowance
did that campaign use" has an answer, and "is our average prompt getting longer" has one too.

The banner is not dismissible while the condition holds. A dismissible warning about a hard limit is
a warning that gets dismissed and then rediscovered as "why did nothing happen last night".

---

## 14.11 Progress reporting

The requirement: a running campaign shows live discovered/researched counts without hammering the
database. Four mechanisms, layered.

### 14.11.1 Throttled writes

Handlers call `ctx.progress(done, total, note)` as often as they like. The runtime writes to `jobs`
only when the note changed, or `done` advanced by at least `max(1, total // 100)`, or
`jobs.worker.progress_min_interval_seconds` (default 5) has passed. The write itself piggybacks on
the heartbeat `UPDATE` (§14.4.4), so a progressing job costs the same number of writes as an idle one.

### 14.11.2 Counters, not counts

Campaign-level progress reads six integer columns on one `campaigns` row (§14.8.1), maintained
transactionally by the jobs that cause them. The alternative — `COUNT(*)` over `businesses` joined to
`research_runs` per poll — is the thing that hammers the database, and it is also wrong more often,
because it can observe a moment when the count and the row that produced it disagree.

### 14.11.3 One cached read, however many viewers

```python
class ProgressCache:
    """Two seconds of memoised campaign progress, shared by every viewer and every tab.

    Without this, five open browser tabs polling every two seconds is 2.5 queries a
    second forever, on a box whose entire job is to write.
    """
    TTL = 2.0
    def get(self, campaign_id: str) -> Progress: ...   # single-flight: concurrent
                                                       # callers await one query
```

`GET /api/v1/campaigns/<campaign_id>/progress` serves from it, with `Cache-Control: no-store` and a
weak `ETag` over the payload so an unchanged poll returns `304` and ~200 bytes.

```json
{
  "campaign_id": "cmp_01JB0000000000000000000001",
  "status": "RESEARCHING",
  "as_of": "2026-08-27T09:14:03Z",
  "counters": {"discovered": 118, "researched": 74, "qualified": 31,
               "skipped": 43, "verified": 0, "contacted": 0},
  "jobs": {"queued": 44, "running": 2, "failed": 1, "dead": 0, "deferred_until": null},
  "cities": [
    {"city": "Dhule",   "discovered": 41, "researched": 41, "state": "DONE"},
    {"city": "Nashik",  "discovered": 52, "researched": 24, "state": "RUNNING"},
    {"city": "Jalgaon", "discovered": 25, "researched": 9,  "state": "RUNNING"}
  ],
  "throttle": {"reason": null, "resumes_at": null},
  "eta_seconds": 2280
}
```
SAMPLE. `eta_seconds` is `outstanding_jobs * median_duration_ms(type, last 50 runs) / llm_threads`,
computed from `job_runs` in the same cached read, and rendered as "about 40 minutes" — never as a
progress bar percentage that goes backwards when a new page of discovery arrives.

### 14.11.4 The push path

`GET /api/v1/campaigns/<campaign_id>/events` is a Server-Sent Events stream. The worker publishes to
an in-process `EventBus` on every state change and every throttled progress write; the SSE handler
subscribes and forwards. **The stream performs no database reads at all** — its payload is exactly
what the worker already knew.

```
event: progress
data: {"campaign_id":"cmp_…01","counters":{"discovered":118,"researched":75},"as_of":"…"}

: heartbeat                     <- every 15 s; keeps the browser from idling the stream out

event: job
data: {"job_id":"job_…","type":"research_business","state":"SUCCEEDED","business_id":"biz_…"}

event: shutdown
data: {"reason":"worker stopping"}
```

**Changed for the free stack: there is no reverse proxy.** The earlier version needed
`flush_interval -1` on a Caddy `reverse_proxy` block, because a buffering proxy turns SSE into a file
download that arrives at the end. `_CONTEXT.md` §2 puts waitress on `127.0.0.1` with the browser on
the same machine, so there is nothing between the two to buffer anything — the one genuine
simplification the deploy-target change buys.

What still has to be right is waitress itself: it must not be started behind
`waitress.serve(..., outbuf_overflow=...)` defaults that batch small writes, and the SSE view must
`yield` bytes and set `Cache-Control: no-cache`, `X-Accel-Buffering: no` and `Connection: keep-alive`.
The last two are inert with no proxy present, and they are set anyway, because the day this moves
behind one is the day nobody remembers this paragraph.

The client uses SSE when available and falls back to the cached poll endpoint at 3 s otherwise; both
render from the same shape, so there is one renderer. SSE is capped at
`jobs.progress.max_streams` (default 8) — beyond it, new clients get a `503` and fall back to polling,
which keeps a runaway tab from consuming waitress threads.

---

## 14.12 Failure surfaces

### 14.12.1 The dead-letter view

```sql
CREATE VIEW v_jobs_dead AS
SELECT j.id, j.type, j.lane, j.state, j.attempts, j.max_attempts,
       j.last_error_class, j.last_error,
       j.campaign_id, j.business_id, j.batch_id, j.trace_id,
       j.created_at, j.finished_at,
       CAST((julianday('now') - julianday(j.finished_at)) * 24 AS INTEGER) AS age_hours,
       (SELECT r.error_detail FROM job_runs r
         WHERE r.job_id = j.id ORDER BY r.attempt_no DESC LIMIT 1)          AS last_detail,
       (SELECT COUNT(*) FROM job_runs r WHERE r.job_id = j.id)              AS runs
  FROM jobs j
 WHERE j.state IN ('FAILED','DEAD');

CREATE VIEW v_jobs_queue_depth AS
SELECT lane, state, COUNT(*) AS n,
       MIN(run_after) AS oldest_run_after,
       CAST((julianday('now') - julianday(MIN(run_after))) * 86400 AS INTEGER) AS oldest_age_seconds
  FROM jobs
 WHERE state IN ('QUEUED','LEASED','RUNNING')
 GROUP BY lane, state;
```

Rendered as the **jobs tab of `/settings`** (the canonical UI route set has no `/jobs`, and a jobs
console is a settings-shaped thing). Three bands, in this order:

1. **Needs a decision** — `DEAD` rows, excluding `send_email` rows whose `result.reconciled` is
   already `SENT` or `NOT_SENT` (§14.13.4), which have been settled and are not asking for anything.
   The `send_email` rows that remain link to the indeterminate resolution screen (§14.13.5) rather
   than to a retry button.
2. **Failed, retryable** — `FAILED` rows grouped by `type` and `last_error_class`, with a per-group
   "retry all" and a per-row retry.
3. **Recently recovered** — jobs that succeeded on attempt >= 2 in the last 24 h. This band exists so
   the console is not exclusively bad news: a system that retried and won should say so, or every
   transient blip looks like an incident.

### 14.12.2 Manual retry and cancel

```
GET    /api/v1/jobs?state=FAILED&type=research_business&limit=50&cursor=…
GET    /api/v1/jobs/<job_id>                     row + every job_runs attempt
POST   /api/v1/jobs/<job_id>/retry               FAILED -> QUEUED
POST   /api/v1/jobs/<job_id>/cancel              sets cancel_requested = 1
POST   /api/v1/jobs/<job_id>/revive              DEAD -> QUEUED, {"reason": "..."} required
POST   /api/v1/jobs/retry-batch                  {"job_ids": [...]} or {"type","error_class","since"}
GET    /api/v1/jobs/stats                        v_jobs_queue_depth + 24 h outcome counts
GET    /api/v1/jobs/dead                         v_jobs_dead
```

Retry semantics: `state='QUEUED'`, `run_after=now`, `max_attempts = attempts + 1` (one more go, not a
reset to zero — the history of what already failed stays true), `last_error` preserved,
`retried_by`/`retried_at` written into `jobs.result` and an `audit_log` row for `revive` and for
`retry-batch`. All six endpoints are session-authenticated; the API-token authenticator cannot reach
them, for the same reason `05-outreach-workflow.md` §5.3.6 keeps approvals off the token blueprint.

`revive` refuses outright when `type = 'send_email'`, with a 409 whose body names the correct
endpoint. Making the unsafe thing hard to do by accident is cheaper than making it recoverable.

### 14.12.3 Alert rules

Evaluated in one function, `evaluate_job_alerts(conn, cfg)`, called by `handoff_sla_sweep` (already
running every 5 minutes in the `notify` lane) and by `main.py jobs doctor`. Each rule fires at most
once per `cooldown`, keyed through `send_notification`'s dedupe key.

| Rule id | Condition | Severity | Cooldown |
|---|---|---|---|
| `job.dead` | Any job entered `DEAD` since the last evaluation | HIGH | none — every `DEAD` row pages |
| `job.type_failing` | `>= N` attempts of one `type` ended `FAILED`/`TIMEOUT`/`LEASE_EXPIRED` within `W` (defaults `N=5`, `W=30 min`) | HIGH | 60 min per type |
| `job.repeat_offender` | One `job_id` has `>= 3` `job_runs` with a non-success outcome | NORMAL | per job |
| `job.queue_stalled` | `v_jobs_queue_depth.oldest_age_seconds > 1800` for any lane with `QUEUED` work | HIGH | 30 min per lane |
| `job.lane_idle_with_work` | A lane has `QUEUED` work and zero `RUNNING` for > 10 min while the process is up | HIGH | 30 min |
| `job.schedule_missed` | A schedule's `last_tick_at` is older than 2 intervals **of worker uptime** (or, for `daily_report`, more than 30 minutes of uptime past its slot with no `READY` export and the slot still inside its grace) | NORMAL | per schedule per day |
| `campaign.stalled` | A campaign in `DISCOVERING`/`RESEARCHING` with zero non-terminal jobs for > 10 min | HIGH | per campaign |
| `quota.warn` / `quota.stop` | §14.10.4 | NORMAL / HIGH | once per IST day |
| `credentials.invalid` | Any `AUTH` classification | HIGH | 60 min |
| `disk.low` | Free space on the data volume < `jobs.alerts.disk_min_mb` (default 1024) | HIGH | 60 min |
| `backup.failed` | `backup_db` ended `FAILED`, or no `READY` backup in 48 h | HIGH | 12 h |
| `worker.down` | The doctor ran (so the machine is on) and there is no `job_runs` row started and no successful claim in `jobs.alerts.silence_minutes` (default 20) | HIGH | 60 min — **evaluated only by the doctor** (§14.12.4) |
| `credentials.app_password` | An `AUTH` classification whose source is SMTP or IMAP | HIGH | 60 min. Split from `credentials.invalid` because the remedy is different and specific: regenerate the Gmail App Password. It is the failure `_CONTEXT.md` §4's stack makes most likely, since re-running 2-Step Verification silently invalidates every App Password on the account |

`N=5 in 30 minutes` is the answer to "the alert rule for a job that has failed N times", and the
reason it counts *attempts of a type* rather than failures of one job is that the interesting signal
is systemic: one job failing five times is a bad row, five jobs of one type failing once each is a
provider or a credential, and the second is the one that needs a human tonight.

**Every wall-clock threshold in this table is measured against worker uptime, not against the
clock.** This is new, and without it the alert set is unusable on the deploy target. A laptop that
was shut from 21:00 to 09:40 has a `poll_inbox` schedule whose `last_tick_at` is twelve hours old, a
queue whose oldest `QUEUED` job is twelve hours old, and a campaign that has had zero non-terminal
jobs for twelve hours — which is `job.schedule_missed`, `job.queue_stalled` and `campaign.stalled`
all firing at once, every single morning, about nothing.

The fix is small and needs no schema. `evaluate_job_alerts()` runs **inside** the worker, so it knows
`WORKER_STARTED_AT` from process memory, and every rule reads `uptime = now - WORKER_STARTED_AT`
instead of an absolute age:

| Rule | Reads | Consequence |
|---|---|---|
| `job.schedule_missed` | `min(now - last_tick_at, uptime)` against 2 intervals | A schedule that ticked at startup is fine; one that has not ticked in ten minutes of *running* is not |
| `job.queue_stalled` | `min(oldest_age_seconds, uptime)` against 1800 s | Twelve hours of queued work found on launch is normal; thirty minutes of untouched queue while running is a stall |
| `job.lane_idle_with_work` | `uptime > 10 min` as a precondition | Already scoped to "while the process is up"; now the phrase is enforced rather than assumed |
| `campaign.stalled` | `min(idle_seconds, uptime)` against 600 s | Same |
| `backup.failed` | **not** uptime-scoped | "No `READY` backup in 48 h" stays absolute. A laptop that has not been opened in two days genuinely has no recent backup, and Sagar should hear about it the moment he opens it |

The last row is the one to notice: the rule is not "make every alert uptime-relative", it is "ask
whether the alert is about the *system misbehaving* or about the *world being in a bad state*".
Misbehaviour needs uptime. A stale backup, a full disk and an expired credential are true whether or
not we were running.

Alert text is a `send_notification` with `kind='JOB_ALERT'`:

```
business_radar - jobs

HIGH  job.type_failing
  research_business: 6 failed attempts in 28 min
  Last error  PROVIDER_5XX  "529 overloaded"
  Affected    cmp_…01 (Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026)
  Queue       llm 44 queued, oldest 31 min

  /settings -> jobs
```
SAMPLE.

### 14.12.4 Who watches the worker

Every rule above runs inside the worker. If the worker is dead, none of them fire — the classic
gap. It is closed with a second, tiny process on a **Windows Task Scheduler** entry, which is the
only piece of this system that lives outside the app process:

```
:: deploy/radar-doctor-task.xml  --  schtasks /Create /XML deploy\radar-doctor-task.xml /TN radar-doctor
   Trigger  : Daily at 00:00, repeat every 15 minutes for 24 hours
   Action   : D:\radar\.venv\Scripts\python.exe main.py jobs doctor --alert
   Settings : StartWhenAvailable        = true    <- fires once after a missed window, not 40 times
              DisallowStartIfOnBatteries = false
              StopIfGoingOnBatteries     = false
              ExecutionTimeLimit         = PT2M
```

`jobs doctor` opens the database read-only, evaluates `worker.down`, `disk.low`, `queue_stalled` and
`backup.failed`, and notifies through `radar/notify.py` directly. It never claims a job and never
writes to `jobs`. It is under 200 lines and imports neither Flask nor `google.genai`, so the thing
that reports the outage is the least likely component to be part of it.

**What the deploy-target change does to this watchdog, in both directions.**

The bad direction is that the doctor cannot see the most important outage any more. On a VPS,
"the worker has not claimed anything in 20 minutes" was unambiguous. On a laptop it is usually
"the lid is shut", and there is no process running to notice, because the Task Scheduler entry is
asleep too. **A machine that is off cannot page anybody, and no design fixes that** — which is why
`worker.down` is written as "the doctor ran, so the machine is on, and the worker still is not
working". The doctor's own existence is the liveness signal; its absence proves nothing.

The good direction is that `StartWhenAvailable` gives the doctor a property `systemd`'s
`Persistent=true` gave it and that the worker itself has to implement by hand (§14.9.2): a missed
window fires once on resume rather than 40 times. The one number to watch is
`ExecutionTimeLimit = PT2M`, which replaces `Type=oneshot`'s implicit "it finishes or it hangs
forever" — a doctor that hangs on a locked database would otherwise accumulate one stuck process
every fifteen minutes.

Belt and braces on top: the `:loop` in `radar-start.cmd` (§14.5.4) handles a crash and the
`max_restarts_per_hour` guard handles a crash loop; the "on workstation unlock" trigger handles a
laptop that was opened without a fresh logon; and the worker sends a daily `heartbeat` line inside
the 07:35 report, so a silent morning is itself a signal — with the caveat that on this target a
silent morning also means "the report was outside its grace window" (§14.9.1), and the two are
distinguished by whether the `INFO` line about a dropped slot appears in `logs/radar.log`.

---

## 14.13 `send_email` reconciliation

§14.1 decision 8 claims at-most-once with a human tiebreak, and the introduction to this document
promises a write-by-write proof that `kill -9` in the middle of `send_email` can neither duplicate a
send nor lose the record of one. This section discharges both. Four things have to be pinned down
before either claim means anything: **where the transmit boundary actually is** on SMTP (§14.13.1),
**what key survives a process death** and can still be used to ask the world what happened
(§14.13.2), **in what order the two transactions write** and what the database therefore says at
every point a process can die (§14.13.3), and **the pass that reads the wreckage** on the next launch
(§14.13.4). §14.13.5 is the screen for the one case the machine is not allowed to decide.

`07-email-integration.md` §7.10.2 and §7.10.4 own the email half of this — the Sent-folder search,
the transport's result type, the account behaviour. This section owns the job-runtime half: state,
write order, when the pass runs, what it is allowed to conclude, and what it must refuse to conclude.
Where the two documents touch, `07` is the arbiter for anything with `smtp`, `imap` or Gmail in it.

**Why this is more load-bearing on this deploy target than it was on the last one.** `_CONTEXT.md` §2
puts the app on a laptop that is closed at night and asleep in between. §14.5.6 establishes that a
suspend between the socket write and the reply read is now the *most likely* way an indeterminate
send happens — more likely than the crash the rule was originally written for. The indeterminate path
is not a rare corner here. It is a path that will be walked.

### 14.13.1 The SMTP transaction boundary

Step 7 of §14.8.12 is one `smtplib` session and nothing else. No database transaction is open across
it (§14.2.3), no lock is held, and it has exactly one recipient (`_CONTEXT.md` §4).

```python
# radar/channels/email.py :: SmtpEmailTransport.send   (07 §7.3.5 owns the class)
smtp = smtplib.SMTP(host, 587, timeout=cfg.get("email.smtp.timeout_seconds", 30))
try:
    smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
    smtp.login(user, app_password)
    refused = smtp.send_message(msg)     # <-- THE BOUNDARY IS INSIDE THIS CALL
    # smtplib writes DATA, writes the body, writes the terminating '.', then READS the reply.
    # Everything up to the read is "not sent". The read of a 250 is "sent". There is no
    # observable instant in between, which is the entire reason this section exists.
    return TransportResult.accepted() if not refused else TransportResult.failed(...)
finally:
    try:
        smtp.quit()
    except (smtplib.SMTPException, OSError):
        log.debug("QUIT failed after the message was accepted; it is sent regardless")
```

The explicit `quit()` in a `finally` is not style. `smtplib.SMTP.__exit__` swallows
`SMTPServerDisconnected` on `QUIT` but **re-raises a non-221 reply** as `SMTPResponseException`, and a
`with` block would let that escape from a session in which the `250` had already been read — turning
a successful send into an indeterminate one and putting a message in front of Sagar for nothing. That
one line is worth more than the context manager's tidiness.

| Where the session ends | Python raises | Side of the boundary | Recorded |
|---|---|---|---|
| DNS, connect, `EHLO`, `STARTTLS` | `socket.gaierror`, `SMTPConnectError`, `ssl.SSLError` | before | `PROVIDER_ERROR`, class `NETWORK`, message stays `QUEUED` |
| `AUTH` | `SMTPAuthenticationError` (535) | before | `PROVIDER_ERROR`, class `AUTH`, message stays `QUEUED`, banner + Telegram (`07` §7.10.3, alert `credentials.app_password`) |
| `MAIL FROM` / `RCPT TO` refused | `SMTPSenderRefused`, `SMTPRecipientsRefused` | before | `PROVIDER_ERROR`, then message `FAILED`, `INVALID_RECIPIENT` |
| `DATA` refused up front (`552`, `554`) | `SMTPDataError` | before | message `FAILED` |
| `421` / `4.7.0` mid-session | `SMTPResponseException` | before | `RATE_LIMITED`, `Defer`, `email.day` drained to zero (`07` §7.10.3) |
| **Body written, terminating `.` sent, reply not read** | `SMTPServerDisconnected`, `socket.timeout`, `ConnectionResetError` | **on it** | **`INDETERMINATE`**, message stays `QUEUED`, job `DEAD` |
| Reply read as `250` | — | after | `SENT` |
| `QUIT` fails after a `250` | `SMTPServerDisconnected`, or `SMTPResponseException` on a non-221 | after | `SENT`. Caught above, logged at `DEBUG`, never propagated |
| The process dies anywhere in the session | — | unknown from inside | §14.13.3, §14.13.4 |

Two properties of this table are bought by decisions made elsewhere, and are worth naming because a
future edit that gave them up would quietly break this section:

- **One recipient per message** (`_CONTEXT.md` §4) means `send_message()`'s per-recipient refusal dict
  is either empty or the send failed outright. There is no partial success to model, no "two of three
  accepted", and therefore no state between `SENT` and `FAILED` other than the one genuine unknown.
- **`email.smtp.timeout_seconds` (30) is far below the type's `timeout_seconds` (120, §14.8.0).** A
  wedged socket therefore produces a typed transport outcome — `NETWORK` before the boundary,
  `INDETERMINATE` on it — instead of the runtime's `TIMEOUT`, and those are settled differently. If
  the two were ever inverted, every stalled send would arrive as an untyped timeout and reconciliation
  would lose the one distinction it runs on.

### 14.13.2 The deterministic `Message-ID`

`07-email-integration.md` §7.8.1 owns `derive_message_id(outreach_messages.id)` ->
`<msg_01JB…@gmail.com>`. This section states why the job runtime depends on it rather than on
anything the server said.

| Property | What the runtime needs it for |
|---|---|
| A **pure function of `outreach_messages.id`** | The reconciler computes the key from the row alone. Even in the one crash where T1's write was lost, the search key still exists — because it was never data, it was arithmetic |
| Written into `outreach_messages.provider_message_id` in **T1, before the socket opens** | A reader who never calls `derive_message_id()` still sees it: `05` §5.18.1's history, `09` §9.2.4's attribution, `/outreach` |
| Placed in the `Message-ID:` header and asserted by `07` §7.6.4's check `T6` | The copy Gmail files in `[Gmail]/Sent Mail` carries it, and that copy is what §14.13.4 searches for |
| Identical across two transmissions of the same row | If reconciliation is ever wrong, both copies carry one `Message-ID` and most receiving mail stores collapse on exactly that. **Defence in depth, not a licence** — it is a property of the receiver, not a guarantee we can make |

**Gmail may rewrite it on submission** (`07` §7.8.1), and no specification settles whether it will for
a given account. The job runtime must therefore never assume the header survived, and it does not need
to: `find_sent_copy()` (`07` §7.10.4) tries three keys in order — our `Message-ID`, then the
plus-addressed `Reply-To` tag `msg_tag_address(message_id)`, which Gmail does **not** rewrite, then
`X-Google-Original-Message-ID`. §14.13.4 calls that function rather than writing an IMAP search of its
own. Where the delivered id differs from ours the reconciler records it, and from then on
`provider_message_id` holds the delivered one so a reply can match against it (`07` §7.8.8 rule `M1`).

Note what this means for the channel that is **not** built. If the WhatsApp Cloud API path in
`08-whatsapp-integration.md` is ever enabled it registers `send_whatsapp` with
`on_lease_expiry="RECONCILE"` exactly like `send_email` (§14.8.0), but its provider id does not exist
until *after* the call, so it has no key with this property and its reconciliation would be strictly
weaker than this one. That is a reason to keep the channel manual, and it belongs in the record here
rather than being discovered later.

### 14.13.3 The write order, and the proof

Two transactions, a network call between them, and nothing else. `05-outreach-workflow.md` §5.10.2
owns `send_message()`; this is the same code with the reconciliation-relevant writes labelled.

```sql
-- T1  "the intent". Commits BEFORE the socket opens. 14.8.12 step 6.
BEGIN IMMEDIATE;
  SELECT * FROM outreach_messages WHERE id = :mid AND status = 'QUEUED';          -- (a)
  UPDATE outreach_messages SET eligibility_snapshot = :snap WHERE id = :mid;      -- (b)
  UPDATE outreach_messages
     SET attempt_count            = attempt_count + 1,
         worker_id                = :worker_id,
         provider                 = 'gmail_smtp',
         provider_message_id      = :derived_message_id,   -- 14.13.2, before the wire
         provider_send_started_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
   WHERE id = :mid AND status = 'QUEUED';                                         -- (c)
  INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, detail)
       VALUES (:evt, :mid, 'SEND_ATTEMPT', 'SYSTEM', :worker_id, :detail);        -- (d)
COMMIT;
```

```
---- no transaction, no lock, no writer held: the SMTP session of 14.13.1 ----
```

```sql
-- T2  "the outcome". Nothing here touches the network and nothing here is retried.
BEGIN IMMEDIATE;
  UPDATE jobs
     SET state = :terminal, finished_at = :now, lease_owner = NULL,
         lease_expires_at = NULL, result = :result
   WHERE id = :job_id AND lease_owner = :worker_id;         -- (e) THE FENCE, 14.4.4
  -- rowcount 0 => this worker no longer owns the job. ROLLBACK and write nothing at all.
  UPDATE outreach_messages
     SET status = 'SENT', sent_at = :now,
         provider_status_code = '250', provider_response = :resp
   WHERE id = :mid AND status = 'QUEUED';                                         -- (f)
  INSERT INTO outreach_events (...) VALUES (..., 'SENT', 'SYSTEM', :worker_id, ...);  -- (g)
  UPDATE campaigns  SET n_contacted = n_contacted + 1 WHERE id = :cmp;            -- (h)
  UPDATE businesses SET status = 'CONTACTED'
   WHERE id = :biz AND status = 'CONTACT_READY';
  -- audit.write('OUTREACH_SENT', ...) inside this same transaction (11-audit-architecture.md)
COMMIT;
```

**The fence is T2's first statement, not its last.** If this worker was reaped while it was on the
wire, statement (e) matches zero rows and the transaction rolls back having written nothing. Putting
the fence last would mean five writes had already been applied by the time we discovered we had no
right to make any of them — and one of those writes is `SENT`.

**Every point a process can die, and what the database says afterwards.** This is the proof §14.1
promises; read it as a case analysis, because that is what it is.

| # | Kill point | `jobs` | `outreach_messages` | `outreach_events` | What actually happened | What §14.13.4 concludes |
|---|---|---|---|---|---|---|
| 1 | Before T1's `COMMIT` | `RUNNING`, lease will expire | `QUEUED`, `provider_send_started_at` NULL | none | **Nothing on the wire.** The socket had not been opened | Reaper -> `DEAD` (`RECONCILE`). No `SEND_ATTEMPT` -> `NOT_SENT`, decided **without touching IMAP** |
| 2 | After T1, before the socket opened | `RUNNING` -> reaped `DEAD` | `QUEUED`, marker set | `SEND_ATTEMPT` | Not sent | No Sent copy **and** no `INDETERMINATE` event -> `NOT_SENT` |
| 3 | During `EHLO` / `AUTH` / `RCPT TO` | as above | as above | `SEND_ATTEMPT` | Not sent | Same as 2 |
| 4 | Body written, `.` sent, reply not read, **handler survives** | `DEAD` | `QUEUED`, marker set | `SEND_ATTEMPT`, `INDETERMINATE` | **Unknowable from here** | Sent copy found -> `SENT`. Not found -> **`INDETERMINATE`**; Sagar decides (§14.13.5) |
| 5 | Body written, `.` sent, reply not read, **process dies** | `RUNNING` -> reaped `DEAD` | `QUEUED`, marker set | `SEND_ATTEMPT` | **Unknowable from here** | Sent copy found -> `SENT`. Not found -> `NOT_SENT`, and this is the one automatic verdict that can be wrong. See below |
| 6 | `250` read, before T2 | `RUNNING` -> reaped `DEAD` | `QUEUED`, marker set | `SEND_ATTEMPT` | **It was sent** | Sent copy found -> `SENT`, and nothing is resent |
| 7 | During T2's `COMMIT` | atomic | atomic | atomic | Either the whole outcome or none of it | `synchronous = FULL` (§14.2.3) makes a committed T2 survive a power cut, not merely a process kill. This is what that `fsync` is for |
| 8 | After T2 | terminal | `SENT` / `FAILED` | terminal event | Settled | Neither of §14.13.4's selection queries matches it |

**Rows 5 and 6 are the same three rows in the database and opposite facts in the world.** Nothing
inside this system can tell them apart. The only discriminator that exists anywhere is the copy in
`[Gmail]/Sent Mail`, and a copy that has not appeared *yet* is indistinguishable from one that never
will. Three things make row 5's automatic `NOT_SENT` as safe as it can be made:

1. `email.sent_search_grace_minutes` (`07` §7.14, default 10) — a message whose attempt started less
   than the grace ago is not judged at all; it is left for the next pass.
2. The pass runs **at the next launch**, which on this deploy target is typically the next morning. By
   then the copy has had hours rather than seconds to appear.
3. §14.13.5's endpoint re-runs the search at the moment a human clicks, so the last chance to catch a
   late copy is taken after the human has looked too.

**Why no kill point can double-send.** Five independent locks, none of which is the application
remembering to be careful:

| # | Lock | Where |
|---|---|---|
| 1 | `attempts` is incremented **by the claim**, `max_attempts = 1`, and the DDL carries `CHECK (attempts <= max_attempts)`. The claim predicate can never select this job a second time | §14.3.1, §14.4.1 |
| 2 | `on_lease_expiry = 'RECONCILE'` sends an expired `send_email` lease to `DEAD`, never back to `QUEUED`; §14.5.4 step 7 excludes the type from the shutdown release for the same reason | §14.4.5, §14.5.4 |
| 3 | `ux_jobs_dedupe` over `send_email:{message_id}` is permanent and `jobs.retention.never_prune` keeps the row forever, so a second send job for that message cannot be inserted at all | §14.6.2 |
| 4 | `ux_om_idempotency` on `outreach_messages.idempotency_key` means a genuine re-send is a new draft, a new approval and a new row — never this row twice | `05` §5.3.5 |
| 5 | `AND status = 'QUEUED'` on both T1 statements, and the lease fence on T2's first statement | `05` §5.10.2, §14.4.4 |

What remains, stated plainly rather than buried: **exactly one path in this system can transmit the
same message twice, and it is a human clicking "It was not sent" in §14.13.5 on a message that was in
fact sent.** That path is audited with the human's user id, it is guarded by a fresh Sent-folder
search taken at the instant of the click, and it is not closed — because closing it would mean the
machine guessing, and §14.1 decision 8 is that the machine does not guess. The mitigation of last
resort is §14.13.2's: both copies would carry one `Message-ID`.

The symmetric claim is easier and is worth stating too. **No kill point loses the record of a send.**
T1 commits the intent before the socket opens, so a transmission that happened always has a
`SEND_ATTEMPT` row and a `provider_message_id` behind it; there is no window in which bytes go out
with nothing written down. The worst outcome available is a send recorded as unresolved, which is
visible on three surfaces (§14.13.5, §14.12.1, the 07:35 report) rather than silent.

### 14.13.4 The reconciliation pass

```python
# radar/jobs.py :: reconcile_sends
def reconcile_sends(conn, cfg, *, imap: imaplib.IMAP4_SSL | None = None) -> ReconcileReport:
    """Decide what happened to sends whose worker died between the intent and the outcome.

    Resending is the tempting default and the wrong one. A duplicate cold email to a business
    that has never heard of us reads as a malfunctioning bulk sender, which is the impression
    this whole pack exists to avoid - and on a free Gmail account it is also the description
    of an account about to be closed.

    So this pass moves a message FORWARD to SENT only on evidence, moves it BACK to sendable
    only on proof or on the one bounded inference in 14.13.3 row 5, and refuses to decide at
    all when it has neither. It never enqueues a send, and it never writes a verdict it could
    not reach.
    """
```

**It is one function with three call sites**, all of which hand it the same job and all of which are
safe to repeat:

| Call site | When | Why there |
|---|---|---|
| §14.5.1 step 6 | Startup, **synchronously, before any lane starts claiming** | Nothing can be mid-send while it decides, and on this deploy target every morning is a startup with real work for it |
| The `maint` lane loop | The next iteration after `request_reconcile()` has been set | §14.5.6's `on_resume()` sets the flag rather than doing IMAP I/O on the heartbeat thread, and §14.4.5's reaper sets it whenever it moves a `send_email` to `DEAD`. Without this, a lid closed at 11:00 would leave an unresolved send sitting until the next launch |
| `main.py jobs reconcile` | By hand | What Sagar runs when `/outreach` shows an amber row and he wants the machine to look once more before he answers |

**Two selection queries, unioned on `message_id`.**

```sql
-- A. Every DEAD send_email job. Catches 14.13.3 row 1, which has no message-side marker at all.
SELECT j.id AS job_id,
       json_extract(j.payload, '$.message_id') AS message_id
  FROM jobs j
 WHERE j.type  = 'send_email'
   AND j.state = 'DEAD'
   AND (j.result IS NULL OR json_extract(j.result, '$.reconciled') IS NULL);

-- B. Every message past the transmit boundary with no terminal outcome.
--    05 §5.17.2 prints this query; the two differences are noted in Open questions.
SELECT m.id AS message_id, m.provider, m.provider_send_started_at
  FROM outreach_messages m
 WHERE m.status  = 'QUEUED'
   AND m.channel = 'EMAIL'
   AND m.provider_send_started_at IS NOT NULL
   AND m.sent_at IS NULL
   AND m.provider_send_started_at <
       strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-' || :grace_minutes || ' minutes')
   AND m.provider_send_started_at >
       strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-' || :lookback_days || ' days')
 ORDER BY m.provider_send_started_at
 LIMIT :max_per_run;
```

Set A exists because a job can die before it marks the message (row 1); set B exists because a message
can carry a marker written by a job that was later pruned or that never reached `DEAD`. Neither set is
a superset of the other, which is why both are read.

**The decision ladder, in order. The first rule that fires wins.**

| # | Evidence | Verdict | Costs an IMAP round trip |
|---|---|---|---|
| 1 | No `SEND_ATTEMPT` event for the message | `NOT_SENT` — **proof**, not inference. T1 commits before the socket opens (§14.13.3 row 1) | No |
| 2 | Transport is `null` (`07` §7.3.4) | The `.eml` under `email.outbox_dir` exists -> `SENT`; it does not -> `NOT_SENT`. Definitive both ways | No |
| 3 | `find_sent_copy()` returns a copy (`07` §7.10.4) | `SENT` | Yes |
| 4 | No copy, **no** `INDETERMINATE` event, attempt older than `email.sent_search_grace_minutes` | `NOT_SENT` — the bounded inference of §14.13.3 row 5 | Yes |
| 5 | No copy, **an** `INDETERMINATE` event exists | `INDETERMINATE`. A human decides (§14.13.5) | Yes |
| 6 | IMAP unreachable, login refused, or the folder is missing | `UNRESOLVED`. Nothing is written | Attempted |

Rules 4 and 5 differ by one event row, and that is deliberate. An `INDETERMINATE` event means the
handler was alive at the boundary and reported that it did not know — the strongest available signal
that the bytes may have landed. Its absence means the process died, and a process that died before
opening a socket is far more common than one that died in the millisecond between `.` and `250`.
Combining a missing Sent copy with *how the attempt ended* is what makes rule 4 safe and rule 5
unsafe; `07` §7.10.4 draws the same distinction and this is the job-runtime statement of it.

**What each verdict writes**, all inside one `BEGIN IMMEDIATE` per message:

| Verdict | Writes |
|---|---|
| `SENT` | `outreach_messages.status = 'SENT'`, `sent_at` from the Sent copy's `Date`, `provider_message_id` replaced by the delivered id when it differs (`07` §7.8.8 `M1`); `outreach_events('SEND_RECONCILED', actor_type='SYSTEM', detail={"via":"sent_folder","verdict":"SENT","delivered_message_id":"<…>"})`; `campaigns.n_contacted`; `businesses.status` -> `CONTACTED`; `audit_log('OUTREACH_SEND_RECONCILED')`; `jobs.result` gains `{"reconciled":"SENT"}` |
| `NOT_SENT` | `outreach_messages.provider_send_started_at = NULL` — the marker is cleared, so the row leaves set B — with `status` **unchanged** at `QUEUED`; `outreach_events('SEND_RECONCILED', detail={"via":"no_attempt"\|"no_sent_copy","verdict":"NOT_SENT"})`; `audit_log`; `jobs.result` gains `{"reconciled":"NOT_SENT"}` |
| `INDETERMINATE` | Nothing on the message changes: it stays `QUEUED` with its `INDETERMINATE` event. `outreach_events('SEND_RECONCILED', detail={"via":"sent_folder","verdict":"INDETERMINATE"})`; `audit_log('OUTREACH_SEND_INDETERMINATE')`; `jobs.result` gains `{"reconciled":"INDETERMINATE"}`; **on the first such row only**, a `send_notification` `{"kind":"JOB_ALERT","subject_id":"<message_id>","reason":"SEND_INDETERMINATE","priority":"HIGH"}` |
| `UNRESOLVED` | **Nothing.** One `WARNING` line and a counter in `ReconcileReport` |

`status` deliberately does not move on `NOT_SENT`: `05` §5.3.8's transition table has no
`QUEUED` -> `QUEUED` row, and there is nothing else to move it to. Clearing
`provider_send_started_at` is the whole state change, and that column is exactly the marker `05`
§5.10.2 point 4 defines as "we are past the boundary".

The **first such row only** rule on the notification matters more than it looks. This pass runs at
every launch and an unresolved message stays unresolved until Sagar answers, so without the rule he
would be paged about the same amber row every single morning — and an operator paged daily about a
thing he already knows stops reading pages, which is the failure `10-human-handoff.md` exists to
prevent. The condition is concrete: notify only when no earlier `outreach_events` row for this message
has `event = 'SEND_RECONCILED'` with `verdict = 'INDETERMINATE'` in its `detail`. The row is still on
`/outreach` and in the 07:35 report every day; it just does not ring twice.

**Three things this pass never does, each with the reason it would be wrong.**

1. **It never enqueues a send.** A `NOT_SENT` message becomes sendable again and waits for a click,
   exactly as `07` §7.10.3 requires of any retryable failure. An automatic re-enqueue after a crash is
   an automatic loop pointed at a mail server that may have just refused us, and it is also the only
   shape in which a wrong `NOT_SENT` becomes a second cold email with no human anywhere in the path.
   The friction is the feature. A new send re-uses the still-live `outreach_approvals` row through the
   normal `POST /api/v1/outreach/messages/<message_id>/send` route and takes the dedupe key
   `send_email:{message_id}:r{n}`, because the original key is permanent (§14.6.2).
2. **It never revives the `DEAD` job.** The job's work is over whatever the verdict, and reviving it
   would hand it the second attempt the design does not have. `jobs.result.reconciled` carries the
   verdict instead, and §14.12.1's "needs a decision" band filters out `DEAD` `send_email` rows whose
   `result.reconciled` is `SENT` or `NOT_SENT`, so only the genuinely undecided rows ask for anything.
3. **It never writes a verdict it could not reach.** IMAP down is `UNRESOLVED`, not `NOT_SENT`. A
   `SEND_RECONCILED` row saying "no copy found" when what happened was "we could not look" is a false
   entry in the audit trail, and it is precisely the entry a later resend would cite as its
   justification. `_CONTEXT.md` §3 invariant 5's rule about never fabricating a number is the same
   rule as this one about never fabricating a verdict.

**Bounds**, because this runs at startup and startup must not become slow:

| Key | Default | Why |
|---|---|---|
| `jobs.reconcile.max_per_run` | 50 | At 15-25 sends a day (`_CONTEXT.md` §4), fifty unresolved sends is already a catastrophe, and a pass that tried to search a thousand would turn a bad week into a slow launch. The remainder is picked up on the next call |
| `jobs.reconcile.lookback_days` | 30 | Gmail's IMAP search over a wide date range is slow, and a month-old undecided send is a human's problem rather than a search's. Older rows skip the ladder and go straight to the indeterminate band |
| `email.sent_search_grace_minutes` | 10 | Owned by `07` §7.14. A copy needs time to appear |

`ReconcileReport` carries the per-verdict counts and is what §14.5.1 step 9's "reconciled count" logs.
The pass is idempotent by construction: every write is conditional on the current state, and a message
that has been settled leaves both selection queries.

### 14.13.5 The indeterminate band, and the one endpoint that closes it

An `INDETERMINATE` message is the only state in this system that needs a person and will otherwise sit
forever. It gets a band of its own on `/outreach`, amber, above the sent rows and below the queue.
`07-email-integration.md` §7.10.5 owns the full batch screen; this is the row and its two buttons.

```
WE ARE NOT SURE (1)                                                          SAMPLE
  Deshmukh Motors        JALGAON    The connection dropped after we sent the message and
                                    before Gmail answered. We looked in Sent Mail just now
                                    and could not find it, but that is not proof.
                                    Search Sent Mail for  +msg_01jb3k7q  then tell us.
                                    [ It was sent ]   [ It was not sent ]
```

Three rules the band obeys, and the third is the one that keeps it honest:

1. It is the **only** place a `send_email` can be resolved by hand. `POST /api/v1/jobs/<job_id>/revive`
   refuses `type = 'send_email'` outright with `REVIVE_FORBIDDEN_FOR_SEND` (409) whose body names this
   route (§14.12.2, `13-api-endpoints.md` §13.16), and §14.12.1's dead-letter band 1 links here rather
   than to a retry button.
2. The row says **what the system already looked for and why the result was not conclusive**. "Check
   your Sent folder" is a far more useful instruction to a reader who knows the machine already tried
   and knows what it tried on.
3. There is no third button. "Leave it for now" is what closing the tab does, and the row will still be
   there tomorrow.

**The endpoint.** `13-api-endpoints.md` §13.9 registers it; this is its behaviour.

```http
POST /api/v1/outreach/messages/<message_id>/resolve-indeterminate
Idempotency-Key: <client nonce>
{"outcome": "SENT" | "NOT_SENT", "note": "Found it in Sent Mail, 11:12."}
```

`OWNER`, and **session-authenticated only** — the API-token blueprint cannot reach it, for the same
reason it cannot reach an approval (`05` §5.3.6): a token that can resolve an indeterminate send is a
token that can cause a send.

| Precondition | Failure |
|---|---|
| The message exists, `channel = 'EMAIL'`, `status = 'QUEUED'` | 404, or 409 `SEND_NOT_INDETERMINATE` |
| It has a `SEND_ATTEMPT` event and no terminal event | 409 `SEND_NOT_INDETERMINATE`, `detail.state` naming what it is instead |
| **On `NOT_SENT` only:** `find_sent_copy()` is re-run synchronously and must return nothing | 409 `SENT_COPY_FOUND`, whose body shows the copy's `Date` and delivered `Message-ID` and asks the human to press the other button |

That last row is the guard on the single remaining double-send path named in §14.13.3. It costs one
IMAP search on a click a human makes a handful of times a year, and it catches the exact case that
path is made of: a Sent copy that arrived after the pass looked and before the human answered.

| `outcome` | Writes |
|---|---|
| `SENT` | `outreach_messages.status = 'SENT'` — a legal `QUEUED` -> `SENT` transition (`05` §5.3.8), and `trg_om_send_needs_approval` still demands the `approval_id` that has been on the row since it was queued, so `_CONTEXT.md` §3 invariants 1 and 2 are untouched by this route; `sent_at` = the copy's `Date` if the re-check found one, otherwise `provider_send_started_at`; `outreach_events('SENT', actor_type='HUMAN', actor_id=<users.id>, detail={"resolved":"manual","note":…})`; `campaigns.n_contacted`; `businesses.status` -> `CONTACTED`; `audit_log('OUTREACH_SEND_INDETERMINATE')` naming the human; `jobs.result.reconciled = 'SENT'` |
| `NOT_SENT` | `provider_send_started_at = NULL`, `status` stays `QUEUED`; `outreach_events('SEND_RECONCILED', actor_type='HUMAN', detail={"verdict":"NOT_SENT","resolved":"manual","note":…})`; `audit_log` naming the human; `jobs.result.reconciled = 'NOT_SENT'`. The message becomes sendable again under its existing approval; if that approval has been revoked it needs a new one, because there is no path to `SENT` that does not pass through a live approval row |

`sent_at` is deliberately **not** `now()` on a manual `SENT`: the message went out when it went out,
and stamping it with the moment Sagar noticed would put a false time into `05` §5.18's history and into
every frequency gate that counts backwards from it.

Both outcomes are recorded with `actor_type = 'HUMAN'`. That is the point of the whole section: the
system's last word on an ambiguous send is a row that names the person who decided, not a heuristic
that decided quietly.

---

## 14.14 Configuration

Everything this document's runtime reads, in one block, at the paths the rest of the document has been
naming. `_CONTEXT.md` §1: `config.yaml` is committed as `config.example.yaml` and secrets live in
`config/.env`. **Nothing in the `jobs` block is a secret** — the job runtime never reads a credential
directly; it calls into `radar/config.py`, and the transports fetch their own.

### 14.14.1 Job-type configuration, and what config may not override

The registration decorator in §14.8.0 is the single source of truth for a job type. Config may
override **three fields and no others**:

```yaml
jobs:
  types:
    export_pdf:        {timeout_seconds: 1200}
    research_business: {max_attempts: 4}
```

| Field | Overridable | Why |
|---|---|---|
| `timeout_seconds` | Yes | A wall-clock budget is a property of the machine, and a laptop that renders a 400-business PDF in eleven minutes needs a different number from one that does it in four |
| `max_attempts` | Yes, except where the guard below forbids it | How much a transient failure is worth retrying is an operational judgement |
| `priority` | Yes | Which work matters today is Sagar's call |
| `lane` | **No** | Moving `send_email` into `llm` would put a send behind a quota wait; moving `export_pdf` into `notify` would put a handoff behind a PDF. §14.2.2 exists precisely to prevent both |
| `on_lease_expiry` | **No** | It is the difference between "retry it" and "never retry it, ask a human". §14.13 is built on `send_email` having `RECONCILE`, and a YAML file that can change it is a YAML file that can double-send |
| `backoff` | **No** | Tied to the lane's latency profile (§14.7.2); a `fast` profile on an LLM type is a 429 generator |
| `dedupe_key` grammar, the state machine | **No** | Correctness, not policy. §14.6.2, §14.3.2 |

**The guard, asserted at startup and fatal:**

| Rule | On violation |
|---|---|
| Every key under `jobs.types` names a registered type | Refuse to start, naming the unknown type |
| Only `priority`, `timeout_seconds` and `max_attempts` appear under a type | Refuse to start, naming the rejected field |
| `max_attempts` is **absent** for every type registered with `on_lease_expiry = 'RECONCILE'` — today, `send_email` | Refuse to start, with a message that names §14.1 decision 8 in words: "send_email is at-most-once by design; it cannot be given more attempts from config" |
| `1 <= timeout_seconds <= 3600` | Refuse to start |

Refuse rather than warn, and the reason is not tidiness. A worker that silently ignored
`send_email: {max_attempts: 3}` would be a worker whose operator believes something false about the
send path, and he would go on believing it right up until the first duplicate email. A configuration
error that cannot be acted on correctly should stop the process — the same rule §14.5.1 step 1 applies
to a half-migrated schema.

### 14.14.2 Worker configuration

| Key | Default | Section | What a wrong value does |
|---|---|---|---|
| `jobs.worker.enabled` | `true` | §14.2.1 | `false` serves the site with nothing processing — the failure a solo operator notices last. `/settings` shows a permanent banner while it is off |
| `jobs.worker.mode` | `embedded` | §14.2.1 | `standalone` makes the web process start no lanes; exactly one topology is active at a time |
| `jobs.worker.lanes.<lane>.threads` | 2/3/1/1/1 | §14.2.2 | Raising `llm` past the `llm.gemini.rpm` bucket buys 429s and nothing else (§14.10.1) |
| `jobs.worker.lanes.<lane>.poll_seconds` | 1.0-10.0 | §14.5.3 | The idle backoff ceiling. It only bites in `standalone` mode, where a `wake.poke()` cannot cross the process boundary |
| `jobs.worker.lease_seconds` | 120 | §14.4.4 | Too low and a slow provider call costs a lease mid-flight; too high and a crashed job is unrecoverable for that long |
| `jobs.worker.heartbeat_seconds` | 20 | §14.4.4 | Must stay well under the lease. Also the suspend detector's base interval (§14.5.6) |
| `jobs.worker.reaper_interval_seconds` | 30 | §14.4.5 | Worst-case recovery latency is `lease_seconds + reaper_interval_seconds` |
| `jobs.worker.shutdown_grace_seconds` | 25 | §14.5.4 | `SIGINT` only. Long enough to let a `send_email` finish rather than fall to §14.13.4 |
| `jobs.worker.os_shutdown_grace_seconds` | 4 | §14.5.4 | `CTRL_CLOSE`/`LOGOFF`/`SHUTDOWN`. Anything larger and Windows kills the process first, turning every shutdown into §14.5.5's hard-crash case |
| `jobs.worker.suspend_detect_factor` | 4 | §14.5.6 | A false positive costs one lease round trip; a false negative is noisier. Config because the right value is a measurement nobody has taken |
| `jobs.worker.progress_min_interval_seconds` | 5 | §14.11.1 | Lower makes a progressing job cost more writes than an idle one |
| `jobs.worker.max_restarts_per_hour` | 6 | §14.5.4 | The restart-storm limiter `systemd` used to provide. Exceeded, `main.py serve` exits `2` and `radar-start.cmd`'s loop stops |

**Relationships asserted at startup**, because each of these is a way to configure a worker that looks
fine and is not:

```
heartbeat_seconds * 3       <= lease_seconds           # 6 heartbeats of slack; 3 is the floor
reaper_interval_seconds     <= lease_seconds           # or an expired lease waits a whole cycle
os_shutdown_grace_seconds   <  shutdown_grace_seconds  # 14.5.4's split is meaningless otherwise
email.smtp.timeout_seconds  <  types.send_email.timeout_seconds     # 14.13.1's last note
sum(lanes[*].threads)       <= 12                      # WARNING only; this is a laptop
mode == 'standalone'        => the web process starts no lanes
```

### 14.14.3 The full `jobs` block

This is the block §14.2.1 promises.

```yaml
# config.yaml -- the complete `jobs` block. Shipped as config.example.yaml with these values.
jobs:

  # ---- 14.2.1, 14.4, 14.5 : the worker ---------------------------------------------------
  worker:
    enabled: true
    mode: embedded                     # embedded | standalone            14.2.1
    lanes:                             # in standalone mode, --lanes overrides this
      llm:    {threads: 2, poll_seconds: 2.0}
      io:     {threads: 3, poll_seconds: 2.0}
      export: {threads: 1, poll_seconds: 5.0}
      notify: {threads: 1, poll_seconds: 1.0}
      maint:  {threads: 1, poll_seconds: 10.0}
    lease_seconds:                 120                                   # 14.4.4
    heartbeat_seconds:              20                                   # 14.4.4
    reaper_interval_seconds:        30                                   # 14.4.5
    shutdown_grace_seconds:         25                                   # 14.5.4  SIGINT
    os_shutdown_grace_seconds:       4                                   # 14.5.4  CLOSE/LOGOFF
    suspend_detect_factor:           4                                   # 14.5.6
    progress_min_interval_seconds:   5                                   # 14.11.1
    max_restarts_per_hour:           6                                   # 14.5.4

  # ---- 14.14.1 : per-type overrides. Three fields, and only three ------------------------
  types: {}
    # export_pdf:        {timeout_seconds: 1200}
    # research_business: {max_attempts: 4}
    # send_email:        {max_attempts: 3}    <- REFUSED at startup. 14.1 decision 8.

  # ---- 14.10.1 : token buckets, seeded into rate_buckets at startup step 4 ---------------
  limits:
    llm_concurrency_day:             1        # 14.9.1's night-window note
    llm_concurrency_night:           3
    buckets:
      llm.gemini.rpm:          {capacity:     10, refill_per_sec: 0.16667}
      llm.gemini.tpm:          {capacity: 250000, refill_per_sec: 4166.67}
      llm.gemini.rpd:          {capacity:    250, refill_per_sec: 0.002894}
      email.hour:              {capacity:      8, refill_per_sec: 0.002222}
      email.day:               {capacity:     40, refill_per_sec: 0.000463}
      email.domain.day:        {capacity:      2, refill_per_sec: 0.0000231}  # per eTLD+1, lazy
      discovery.nominatim.rps: {capacity:      1, refill_per_sec: 1.0}   # their policy, 14.10.1
      discovery.overpass.rpm:  {capacity:      6, refill_per_sec: 0.1}
      telegram.rpm:            {capacity:     20, refill_per_sec: 0.33333}

  # ---- 14.10.4 : the daily quota ceiling -------------------------------------------------
  quota:
    daily_request_cap:             200        # our reserve, under the published rpd on purpose.
                                              # Asserted equal to llm.daily_request_cap, 06 6.13.6
    warn_at_pct:                    80
    hard_stop_pct:                 100
    provider_limits:                          # gemini-2.5-flash, Google AI Studio free tier.
      rpm:                          10        # VERIFY against the current rate-limits page
      tpm:                      250000        # before shipping; Google changes these without
      rpd:                         250        # notice. Asserted equal to 06's llm.quota.
    email_quota_units:               1        # one send = one unit against Gmail's daily cap
    reserve:
      classify_response:            20        # never spend the last 20 on anything else

  # ---- 14.13.4 : the send reconciliation pass --------------------------------------------
  reconcile:
    max_per_run:                    50
    lookback_days:                  30
    notify_on_first_indeterminate: true

  # ---- 14.9.2 : catch-up-on-launch -------------------------------------------------------
  schedule:
    max_catch_up:                    7        # caps the ALL policy; ONCE and SKIP ignore it

  # ---- 14.8.23 : retention ---------------------------------------------------------------
  retention:
    success_days:                   30
    failed_days:                   180
    export_days:                    30
    inbound_days:                   14        # data/inbound/* raw MIME; 14.6.3
    never_prune:      ["send_email"]          # 14.6.2 - the permanent dedupe key

  # ---- 14.8.22 : backups -----------------------------------------------------------------
  backup:
    dir:                data/backups
    keep_daily:                     14
    keep_weekly:                     8
    keep_monthly:                    6
    offsite_cmd:                  null        # e.g. "rclone copy {src} radar-backup:"
    offsite_timeout_seconds:       600

  # ---- 14.11 : progress ------------------------------------------------------------------
  progress:
    max_streams:                     8        # SSE cap; beyond it clients get 503 and poll
    sse_heartbeat_seconds:          15

  # ---- 14.12.3 : alert rule thresholds ---------------------------------------------------
  alerts:
    type_failing_n:                  5
    type_failing_window_minutes:    30
    queue_stalled_seconds:        1800
    lane_idle_minutes:              10
    campaign_stalled_seconds:      600
    disk_min_mb:                  1024
    silence_minutes:                20        # worker.down; evaluated only by the doctor
```

**Keys this document reads but does not own.** Duplicating any of them here would create two places to
change one number, which is how a pair silently diverges:

| Key | Owner | Read by |
|---|---|---|
| `email.*` — `transport`, `sent_search_grace_minutes`, `outbox_dir`, `smtp.timeout_seconds` | `07` §7.14 | §14.8.12, §14.13.1, §14.13.4 |
| `response.*` — `ingest`, `imap_folder`, `sent_folder`, `state_file` | `07` §7.14 | §14.8.13 |
| `outreach.send_window` | `05` | §14.9.3 |
| `notify.quiet_hours`, `notify.dedupe_window_minutes` | `10` §10.6.4 | §14.8.17, §14.9.3 |
| `llm.models`, `llm.quota`, `llm.daily_request_cap`, `llm.campaign_request_cap` | `06` §6.13 | §14.5.1 step 3, §14.10.4's equality assertion |
| `research.quota.daily_request_cap`, `research.quota.pause_campaign_on_exhaustion` | `02` §2.16 | §14.10.4's research share |

**Keys deleted by the free-stack pass**, listed so that a reader who meets one in an old branch knows
it was removed on purpose rather than lost: `jobs.retention.webhook_days` (§14.8.14 — there is no
webhook), the rupee ceiling keys under `jobs.spend` (§14.10.4 — there is no bill, only a 429), and
`jobs.worker.systemd_notify` (§14.5.4 — the target is Windows and there is no `systemd`).

---

## Open questions

1. **`01-data-model.md` amendments this document now requires.** Three, all mechanical, all in
   tables `01` records as owned by `14`:

   ```sql
   -- 031_spend_ledger.sql
   -- cost_micros_inr INTEGER NOT NULL CHECK (cost_micros_inr >= 0)
   +  quota_units     INTEGER NOT NULL CHECK (quota_units >= 0)
   -- and v_spend_today's output columns: total_micros_inr / llm_micros_inr / email_micros_inr
   -- become total_requests / llm_requests / email_requests, plus a new llm_tokens.

   -- 032_job_runs.sql
   -- cache_read_tokens, cache_write_tokens, cost_micros_inr
   +  thinking_tokens, cached_tokens, quota_units
   -- and ix_job_runs_cost -> ix_job_runs_quota.

   -- 029_job_schedules.sql
   +  catch_up_grace_minutes INTEGER NOT NULL DEFAULT 0 CHECK (catch_up_grace_minutes >= 0)
   ```

   §14.3.5 argues the first, §14.3.3 the second, §14.3.4 the third. All three are against tables `01`
   registers to this document but does not print DDL for, so nothing else in the pack moves with them.
   The matching rename on `research_runs` is **already done and needs nothing further**:
   `02-research-pipeline.md` §2.3.2 and `01` §1.6.1 both carry `quota_requests` (with
   `ix_research_runs_quota`) per `01` §1.2.4 conflict D7, and neither writes `cost_micros_inr` any
   more. What is still owed is outside this document: `13-api-endpoints.md` references `v_spend_today`
   by name only, but its two `SPEND_CEILING` error codes and the `paused_reason` enum in its §13.22
   OpenAPI block must become `QUOTA_CEILING`, and `12` §12.9 has one reference of the same kind.

2. **`spend_ledger` is now a misleading name.** It records requests and tokens, not spend. It is kept
   because `_CONTEXT.md` §2 names it, `01` owns the migration number, and five documents reference
   it; renaming a table across the pack to make one word more accurate is a bad trade. If the pack is
   ever renumbered, `quota_ledger` is the right name, and §14.3.5's opening paragraph is written so
   that a reader who meets the old name is not confused.

3. **Two additive requests that fall out of §14.13, both against tables this document does not
   own.** §14.13 and §14.14 are now written, and every reference into them resolves; what is left is
   what writing them exposed in the neighbours.

   a. **`outreach_events.event` needs `SEND_RECONCILED` in its `CHECK` list.**
      `05-outreach-workflow.md` §5.3.7 owns the enum (migration `016`) and does not have the value.
      `07-email-integration.md` §7.10.4 already writes it and §14.13.4 depends on it for every one of
      its four verdicts. One value, one line. Until it lands the insert fails a `CHECK`, and
      reconciliation failing silently is the one property reconciliation may not have.

   b. **`05` §5.17.2's selection query needs two one-line edits.** It hard-codes `-5 minutes` where
      §14.13.4 uses `email.sent_search_grace_minutes` (`07` §7.14, default 10), and it does not filter
      on `channel`. `07` owns the Sent-folder search that consumes the grace, so the config key is the
      arbiter and the literal should go; the `channel = 'EMAIL'` filter matters because a WhatsApp row
      has no Sent folder to search and must not enter this pass. §5.17.2's prose also describes asking
      "the provider" by idempotency key, which is the ESP-shaped design `07` §7.10.2 replaced — the
      key is our own `Message-ID` and the provider is an IMAP folder.

   Neither is a design disagreement. Both are the cost of §14.13 being written after the documents it
   reads.

4. **How the quota reserve interacts with a second campaign.** §14.10.4 reserves 20 requests a day for
   `classify_response` and gives everything else to whoever asks first. With one campaign running
   that is correct. With two, the first campaign to start consumes the day and the second makes no
   progress at all until it finishes, which is arguably worse than both progressing slowly. A
   per-campaign fair share is implementable (`v_spend_today` already indexes by `campaign_id`) and is
   not implemented, because at 250 requests a day the honest answer is that this machine runs one
   campaign at a time and a fair-share scheduler would be elaborate machinery for a situation Sagar
   should avoid rather than manage.

5. **The suspend detector's threshold is a guess.** §14.5.6 declares a suspend when a
   `heartbeat_seconds` wait takes more than four times as long as requested — 80 seconds against a
   20-second interval. That will also fire on a genuinely starved thread during a heavy export, and
   the consequence of a false positive is one extra lease re-establishment round trip, which is
   harmless. The consequence of a false *negative* is a worker holding a lease it no longer owns and
   discovering it at the fence instead — also handled, but noisier in the log. The factor is config
   (`jobs.worker.suspend_detect_factor`) precisely because the right value is a measurement nobody
   has taken yet.
