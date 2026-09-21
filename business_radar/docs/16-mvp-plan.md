# 16. MVP implementation plan

This document decides what gets built first, in what order, and how each step is proved. It takes the
fifteen design documents that precede it — roughly 44,000 lines describing a complete system — and
extracts the subset that must exist before Sagar can research a city, read a report, verify a business
by hand, and send one email he wrote and approved. It commits to six milestones, a file tree, a CLI, a
test strategy anchored on `_CONTEXT.md` §3's safety invariants, a quota-derived working rhythm, and a
definition of done. Its governing constraint is spec §56: *do not implement automatic outreach first*.
Everything here is ordered so that the last thing built is the only thing that can transmit.

---

## 16.1 Scope

### 16.1.1 What v1 does

| # | Capability | Owning documents |
|---|---|---|
| 1 | Creates a campaign over one or more Maharashtra cities, with category, size, minimum-score and depth filters (§1, §2) | `01` §1.3 |
| 2 | Discovers businesses from OpenStreetMap via Overpass, bounded by a pinned relation or a recorded radius, deduped to a stable `business_key` | `02` §2.2, §2.4, §2.5; `01` §1.12 |
| 3 | **Measures and prints coverage** per (city, category), so "we found six businesses in Shirpur" is a stated finding rather than a silent short list | `02` §2.2.9 |
| 4 | Fetches the business's own website politely (robots, 1 req/s per host, SSRF-guarded) and extracts contacts locally | `02` §2.6; `12` §12.2.8 |
| 5 | Synthesises research through `gemini-2.5-flash` into typed `OBSERVED` / `INFERRED` / `UNKNOWN` findings, each `OBSERVED` one carrying a verified source excerpt | `02` §2.8, §2.10 |
| 6 | Scores `digital_maturity`, `operational_complexity` and `opportunity_score` deterministically, leaving unmeasured components NULL rather than zero | `02` §2.11–§2.14 |
| 7 | Produces a self-contained HTML report — KPI cards, city cards, city/industry tabs, filterable table, expandable research panels, source panel, top 20 — plus CSV and XLSX | `03` |
| 8 | Serves the same data live from Flask + waitress on `127.0.0.1`, behind a password + TOTP session | `03` §3.2; `13`; `15`; `12` §12.4 |
| 9 | Enforces the nine-item verification checklist as the **only** path to `VERIFIED`, at the API, at a `CHECK` constraint, and at a DB trigger | `04` §4.6, §4.10 |
| 10 | Computes `CONTACT_READY` as a seven-clause predicate and demotes it automatically when any input changes | `04` §4.3 |
| 11 | Lets Sagar select verified businesses across cities and prepare outreach on `EMAIL`, or emit a `wa.me` link he sends by hand | `05` §5.4–§5.6; `08` §8.6 |
| 12 | Generates a per-business message from a three-layer template bundle plus a Gemini rewrite, every factual sentence bound to a `research_findings` id | `06` §6.3–§6.8 |
| 13 | Runs a policy engine over every draft — binding, hedging, banned claims, PII, required elements — and stores the verdict | `06` §6.9 |
| 14 | Runs the forty-gate eligibility engine (suppression, verification, contact, duplicate, frequency, channel, paperwork) at SELECT, PREVIEW and SEND | `05` §5.9 |
| 15 | Shows a nine-panel preview and a confirmation dialog whose button reads **CONFIRM & SEND**, then writes an `outreach_approvals` row | `05` §5.11–§5.13 |
| 16 | Sends through a `NullEmailTransport` that writes `.eml` files to `data/outbox/` until four independent locks are all opened | `07` §7.3.4, §7.3.7 |
| 17 | Sends real mail over `smtp.gmail.com:587` with an App Password: one recipient per message, a `mailto:` unsubscribe, a ramped daily cap | `07` §7.4–§7.6 |
| 18 | Polls `imap.gmail.com:993` every two minutes for replies, bounces, unsubscribes and Google account notices | `07` §7.8, §7.9; `09` §9.2 |
| 19 | Classifies replies deterministically first, then with Gemini, into the thirteen §33 categories — and **never replies** | `09` |
| 20 | Creates a `handoffs` row on any interested classification, pages Telegram, and blocks every automated path to that business | `10` |
| 21 | Writes a hash-chained `audit_log` row for every consequential action, and can answer "why did this message say that" from stored rows alone | `11` §11.7–§11.9 |
| 22 | Runs discovery, research, drafting, sending, polling and maintenance as leased jobs in an in-process worker with catch-up-on-launch | `14` |
| 23 | Backs up to three copies, one of them `age`-encrypted on removable media | `11` §11.13; `12` §12.12 |

### 16.1.2 What v1 explicitly does not do

Each row is a deliberate exclusion, with the reason and the document that argues it. None of them is
"we ran out of time".

| Not built | Why | Where |
|---|---|---|
| **Any send path that does not take an `approval_id`** | `_CONTEXT.md` §3 invariant 1. No config flag, no `--yes`, no batch approve | `05` §5.13 |
| **WhatsApp Cloud API transmission** | Business-initiated messages need a pre-approved template and a recorded opt-in. v1 emits a `wa.me` link Sagar clicks himself. `send_whatsapp` is not registered in the job registry at all | `08` §8.6; `14` §14.8.0 |
| **SMS and automated phone** | TRAI / DND. `PHONE` produces a call script; nothing dials | `05` gate H4 |
| **Automatic replies to inbound mail** | `_CONTEXT.md` §3 invariant 6. `radar/classify.py` imports no channel, and no screen has a reply box | `09` §9.11 |
| **`SEMI_AUTOMATED` / `FULLY_AUTOMATED` modes** | Two DB triggers refuse the values; probe P8 checks nightly | `05` §5.20; `11` §11.14 |
| **Google Places, Maps Platform, JustDial, IndiaMART** | `_CONTEXT.md` §4: discovery must be free and must not violate terms. All four are on the host denylist | `02` §2.2 |
| **Review-volume and review-recency signals** | No free source exists in v1. They are `None` with `why_null='NO_FREE_SOURCE_IN_V1'`, never `0` | `02` §2.11.1 |
| **RFC 8058 one-click unsubscribe** | No public HTTPS endpoint exists. `mailto:` per RFC 2369 is the only mechanism, and check `T8` blocks any message carrying `List-Unsubscribe-Post` | `07` §7.7 |
| **Inbound webhooks of any kind** | Nothing on the internet can reach `127.0.0.1`. `process_webhook_event` is removed from the registry | `14` §14.8.14 |
| **Open / click tracking pixels** | A tracking pixel in a cold message to a stranger is a strong bulk-sender signal and buys nothing at 15 messages a day | `07` §7.6 |
| **Multi-user RBAC beyond one OWNER** | One operator. `users` and the role checks exist; the second user does not | `12` §12.3 |
| **Postgres** | SQLite on one machine. The DDL is written to port, and `01` §1.13.6 lists the seven rewrites | `01` §1.1.2 |
| **PDF export** | `export_pdf` is registered but ships disabled: the print stylesheet plus the browser's "Save as PDF" covers §41 without a headless-Chrome dependency on a laptop | `03` §3.10 |
| **An identity page that does anything** | GitHub Pages is static. A page with an unsubscribe button that cannot write to the database is a lie | `07` §7.4.4 |
| **Bulk verification** | `test_no_bulk_verify_anywhere` asserts the endpoint 400s, the `CHECK` rejects `mode='BULK'` with `verdict='VERIFIED'`, and no template contains the control | `04` §4.8 |
| **A Windows Service, Docker, nginx, systemd** | Deploy is a `.cmd` in `shell:startup` plus two Task Scheduler entries | `14` §14.5.4 |

### 16.1.3 The order everything obeys

```
RESEARCH  ->  REPORT  ->  VERIFY  ->  SELECT  ->  PREVIEW  ->  SEND
   M2          M3          M4         M5          M5          M6
```

The milestones are that pipeline read left to right, with one addition at the front — M1, the schema
the pipeline writes into. Transmission is the last capability added, not the first, and it is added
behind four locks that all default closed.

---

## 16.2 The complete file tree at the end of the MVP

Every file that exists when M6 is done, with a one-line purpose. Directories holding generated data are
shown by shape rather than contents.

```
business_radar/
├── main.py                        argparse CLI: migrate, campaign, report, serve, worker, email,
│                                    policy, audit, dpdp, backup, doctor, incident, auth  (16.5)
├── config.example.yaml            the committed config; copied to config.yaml on first run
├── config.yaml                    local, gitignored, the running configuration
├── requirements.txt               pinned: flask, waitress, jinja2, google-genai, pydantic, openpyxl,
│                                    python-dotenv, pyyaml, argon2-cffi, pyotp, requests, ulid-py
├── pytest.ini                     markers: slow, ui, live. The default run excludes all three
├── conftest.py                    repo-root fixtures: temp db, frozen clock, offline socket guard
├── README.md                      what this is, how to run it, and what it will not do
├── .gitignore                     config.yaml, config/.env, data/, logs/, *.db*
│
├── config/
│   ├── .env                       SECRETS ONLY. Never in git. Owner-only ACL (12.5)
│   ├── .env.example               the key names with empty values and one comment line each
│   ├── festivals.yaml             IST dates the send window skips (14.9.3)
│   ├── handoff_actions.yaml       the 10.7 recommended-next-action rule table
│   ├── score_weights.sw-1.yaml    the frozen weight set the first campaign scored against
│   └── state/
│       ├── imap_uid.json          UIDVALIDITY plus last-UID cursor for poll_inbox (7.8)
│       └── telegram_offset.json   getUpdates offset for telegram_poll (10.6)
│
├── deploy/                        Windows only. No systemd unit, no Dockerfile, no nginx conf
│   ├── radar-start.cmd            activates .venv, sets RADAR_EMAIL_LIVE, loops `main.py serve`
│   ├── radar-task.xml             schtasks XML: at logon and on workstation unlock (14.5.4)
│   ├── radar-doctor-task.xml      schtasks XML: every 15 min, `main.py jobs doctor --alert`
│   └── WINDOWS.md                 the commands that install both tasks and verify them
│
├── data/                          gitignored in full. This directory IS a contact database
│   ├── radar.db                   SQLite, WAL. `-wal` and `-shm` beside it
│   ├── backups/                   VACUUM INTO snapshots, copy 1 (11.13)
│   ├── cache/overpass/            Overpass responses keyed by query hash, 30-day TTL (2.2.4)
│   ├── registries/                MCA21 / UDISE / PIN-code local tables, refreshed quarterly
│   ├── outbox/YYYY-MM-DD/*.eml    what the NULL transport writes instead of sending (7.3.4)
│   ├── inbound/YYYY/MM/*.eml.gz   raw captured inbound mail, P3Y retention (7.8.4)
│   ├── reports/campaign/*.html    exported campaign reports, indexed by report_exports
│   ├── reports/daily/*.html       the 43 daily report
│   ├── exports/*.csv, *.xlsx      41 exports
│   └── HALT_SENDING               sentinel file; its existence stops all transmission (12.2.10)
│
├── logs/
│   ├── radar.log                  the app; rotated by prune_logs
│   └── supervisor.log             one line per restart, read by the max_restarts_per_hour guard
│
├── radar/
│   ├── __init__.py
│   ├── config.py                  Config dataclass + setup_logging(); refuses to boot on a synced
│   │                                path or a non-loopback bind (12.16)
│   ├── ids.py                     new_id(prefix) over 34 registered prefixes; unknown ones raise
│   ├── db.py                      connect() with the four pragmas asserted, migrate(), verify_schema()
│   ├── models.py                  every @dataclass record with from_row() / to_row()
│   ├── paths.py                   safe_filename(), resolve_within() — path traversal (12.7.4)
│   ├── security.py                volume-encryption and ACL posture, field encrypt / decrypt (12.6)
│   ├── auth.py                    argon2id, TOTP, sessions, require_role, bootstrap_owner
│   ├── audit.py                   audit.write(), the hash chain, verify_chain(), the probe set
│   ├── campaigns.py               create / start / cancel / archive a campaign; counters reader
│   ├── identity.py                business_key derivation, dedupe, merge_businesses()
│   ├── contacts.py                contact capture, kind detection, human_verified transitions
│   ├── phones.py                  E.164 normalisation, IN default region, WhatsApp capability
│   ├── fetch.py                   safe_fetch(): SSRF guard, robots, per-host 1 req/s, size caps
│   ├── llm.py                     THE ONLY module that imports google.genai. Retry, 429 -> Defer,
│   │                                token accounting, model-id pinning
│   ├── discover.py                Overpass query building, city bounds, coverage arithmetic
│   ├── research.py                GATHER / SYNTHESISE / ASSESS, excerpt verification, the PII split
│   ├── score.py                   digital_maturity, operational_complexity, opportunity_score
│   ├── verify.py                  set_status() — the ONLY writer of businesses.status — the nine
│   │                                checks, contact_ready_predicate(), the staleness sweep
│   ├── policy.py                  the forty eligibility gates AND check_draft()'s claim rules
│   ├── messages.py                template resolution, the Gemini rewrite, the repair loop
│   ├── outreach.py                selections, prepare, approve, send_message(approval_id), history
│   ├── classify.py                stage 0 envelope, stage 1 lexicon, the model, apply_classification
│   ├── handoff.py                 triggers, the brief, SLA sweep, follow-up blocking
│   ├── notify.py                  Telegram bot plus email-to-self. Imports no channel module
│   ├── report.py                  build orchestration, filenames, archive rows, dash() / inr()
│   ├── report_queries.py          Q1-Q12 and Q_DAILY_*; the only place report SQL lives
│   ├── report_export.py           CSV (BOM, formula-injection guard) and XLSX writers
│   ├── jobs.py                    the registry decorator, claim-by-lease, retries, the scheduler,
│   │                                catch-up-on-launch, rate buckets, spend ledger
│   │
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py                the Channel protocol: available(), validate(), dispatch()
│   │   ├── email.py               EMAIL channel: availability, render handoff, dispatch
│   │   └── whatsapp.py            wa.me link building; the Cloud API path built and gated
│   │
│   ├── email/
│   │   ├── types.py               OutboundEmail, TransportResult
│   │   ├── transport.py           the EmailTransport Protocol
│   │   ├── null_transport.py      writes .eml to data/outbox/. THE DEFAULT
│   │   ├── smtp_transport.py      smtp.gmail.com:587, STARTTLS, App Password
│   │   ├── factory.py             build_transport() and the four locks (7.3.7)
│   │   ├── mime.py                build_mime(): 24's structure as bytes, headers, encoding, wrapping
│   │   ├── threading.py           Message-ID derivation, +msg_ tagging, References chains
│   │   ├── unsubscribe.py         token derivation, the +unsub- address, find / apply_unsubscribe
│   │   ├── checks.py              T1-T9, the pre-transmission refusals
│   │   ├── compliance.py          C1-C17, the per-message compliance checklist
│   │   ├── pacing.py              inter-send gap and jitter, computed under the writer lock
│   │   ├── caps.py                reconcile_day_bucket(), effective_daily_cap()
│   │   ├── inbound.py             IMAP client, ingest_one(), kind classification, M1-M8 matching
│   │   ├── scrub.py               scrub_for_model() — the gate between inbound text and any model
│   │   ├── bounce.py              parse_dsn(), attribute_dsn(), classify_bounce()
│   │   ├── reconcile.py           find_sent_copy() for the indeterminate-send case
│   │   ├── events_map.py          (kind, class) -> EventMapping
│   │   └── health.py              v_email_health readers and the invisible-complaint proxies
│   │
│   ├── web/
│   │   ├── app.py                 create_app(), four blueprints, error envelope, boot assertions
│   │   ├── public.py              /unsubscribe-info and GET /api/v1/health. No auth, no writes
│   │   ├── ratelimit.py           token buckets and the RateLimit-* headers
│   │   ├── openapi.py             OpenAPI 3.1 generated from url_map
│   │   ├── verify_views.py        every route that can produce a verdict, and nothing else
│   │   ├── api/
│   │   │   ├── _list.py           paginate(), parse_sort(), parse_filters(), the cursor codec
│   │   │   ├── _errors.py         ApiError, the 13.2.4 envelope, the code catalogue
│   │   │   ├── campaigns.py       13.4, 13.5
│   │   │   ├── businesses.py      13.6, the 39 filter translation, the reveal audit row
│   │   │   ├── outreach.py        13.8-13.11, including the one send route
│   │   │   ├── handoffs.py        13.13
│   │   │   ├── reports.py         13.15 and report_exports
│   │   │   ├── jobs.py            13.16
│   │   │   └── settings.py        13.17, 13.18
│   │   ├── templates/
│   │   │   ├── base.html          live chrome; the EXPORT rendering never uses it
│   │   │   ├── report/            report.html, export.html, daily.html, _macros.html, _header,
│   │   │   │                        _kpis, _city_summary, _filters, _tabs, _table, _panel,
│   │   │   │                        _cmp_city, _cmp_industry, _top20, _selection_bar
│   │   │   ├── verify/            screen.html, _checklist.html, _sources.html, _reject.html
│   │   │   ├── outreach/          workspace.html, preview.html, confirm_dialog.html
│   │   │   │                        (the ONLY template in the tree containing a send control)
│   │   │   ├── handoffs/          queue.html, brief.html
│   │   │   └── settings/          index.html, quota.html, security.html, jobs.html
│   │   └── static/
│   │       ├── tokens.css         the only file containing hex colour literals
│   │       ├── report.css         ~28 KB, inlined into the export
│   │       └── report.js          ~22 KB, zero dependencies, inlined into the export
│   │
│   ├── prompts/
│   │   ├── research/              system.v1.txt, gather.system.v1.txt, assess.system.v1.txt,
│   │   │                            user.v1.j2, repair.v1.j2
│   │   ├── messages/              system.v3.txt, user.v3.j2, repair.v2.j2
│   │   └── classify/              system.v1.txt, user.v1.j2
│   │
│   ├── templates/messages/
│   │   ├── MANIFEST.yaml          category -> industry block -> variant pool bindings
│   │   ├── channel/               email.base.v3.j2, whatsapp.base.v2.j2
│   │   ├── industry/              hospital.v2.yaml, school.v2.yaml, manufacturer.v2.yaml,
│   │   │                            distributor.v2.yaml, ... one per 26 row
│   │   ├── slots/slots.v4.yaml    the slot grammar the model must fill
│   │   └── variation/pools.v4.yaml  observation / opportunity / benefit / demo phrase pools
│   │
│   ├── sql/audit/                 the 11.15 saved queries, exposed as `main.py audit query <name>`:
│   │                                sent_last_week.sql, contacted_more_than_once.sql,
│   │                                policy_blocks.sql, blast_radius.sql, ...
│   │
│   └── migrations/
│       ├── README.md              the Postgres-port notes for the five mutual references
│       ├── 001_bootstrap.sql ... 054_seed_reference.sql
│       │     001-008  schema_version, users, campaigns, businesses, research, contacts, opportunities
│       │     009-012  verification reason codes, verifications, status transitions, status triggers
│       │     013-022  contact_policy, suppressions, selections, drafts, messages, approvals, events,
│       │              status transitions, outreach triggers, message-engine columns
│       │     023-025  responses, handoffs, the handoff outreach block
│       │     026-031  jobs, job transitions, job_runs, schedules, rate_buckets, spend_ledger
│       │     032-039  audit_actions, its seed, audit_log, the immutability triggers,
│       │              sent-needs-audit, suppression release trigger, draft_findings, suppression HMAC
│       │     040-045  the WhatsApp block: applied on day one, tables stay empty until gated on
│       │     046-054  merges, identity view, report_exports, report view, counters view,
│       │              funnel view, outcome labels, job views, reference seed
│       ├── 055_inbound_emails.sql      the IMAP ingestion table (7.8.4)
│       ├── 056_email_account_ramp.sql  the six-week warm-up schedule (7.4.5)
│       └── 057_v_email_health.sql      bounce and reply rates, the only visible health signal
│
└── tests/
    ├── conftest.py                offline guard: any socket() in a default-marked test fails
    ├── fixtures/
    │   ├── overpass/              stored Overpass JSON per (city, category) — the discovery corpus
    │   ├── pages/                 stored HTML: hospital, school, bakery, contact pages, hostile pages
    │   ├── gemini/                recorded generate_content payloads: research, drafting, classify
    │   ├── email/inbound/         .eml replies: interested, OOO, opt-out, forwarded, Devanagari
    │   ├── email/dsn/             real Gmail DSNs: 5.1.1, 5.2.2, 5.7.1, stripped, two-block
    │   ├── classify/corpus.jsonl  the labelled reply corpus, grown from human corrections
    │   └── xss/                   the hostile-name corpus for template escaping
    ├── test_schema.py             every table, enum CHECK, trigger and index in 01 1.16
    ├── test_ids.py                prefix registry, ULID sortability, unknown prefix raises
    ├── test_migrations.py         idempotency, checksum tamper, gap detection, dry-run
    ├── test_audit_chain.py        chain continuity, immutability triggers, verify_chain()
    ├── test_discover.py           coverage bands, cache hits, truncation, landuse rejection
    ├── test_research.py           excerpt verification, injection defence, finding cascade
    ├── test_score.py              the three worked examples, NULL-vs-zero, determinism
    ├── test_pii.py                the contact-leak sentinel tests — the ones that matter most
    ├── test_report.py             self-containment, determinism, KPI parity, no COALESCE-to-zero
    ├── test_report_archive.py     report_exports rows, sha256, retention, path traversal
    ├── test_verify.py             the nine checks at three layers, transitions, contact-ready matrix
    ├── test_policy_eligibility.py the forty gates, precedence, read-only-ness
    ├── test_policy_claims.py      23's bad and good examples, binding, hedging, banned regexes
    ├── test_templates.py          frozen bundles, every category resolves, variants pass policy
    ├── test_messages.py           the repair loop, budget trimming, the similarity guard
    ├── test_outreach.py           approval requirement, illegal transitions, idempotency, races
    ├── test_email_transport.py    the four locks, T1-T9, MIME, threading, unsubscribe
    ├── test_email_inbound.py      M1-M8 matching, UIDVALIDITY, backlog, dedupe
    ├── test_email_bounce.py       the eleven status codes, attribution, soft-to-hard promotion
    ├── test_classify.py           the thirteen categories, the deterministic stage, corpus eval
    ├── test_handoff.py            triggers, dedupe, follow-up blocking, SLA sweep
    ├── test_jobs.py               claim protocol, lease expiry, catch-up, quota deferral
    ├── test_web_routes.py         url_map walks: RBAC, OpenAPI coverage, absent routes stay absent
    ├── test_send_containment.py   each of the nine send-stop layers, independently
    ├── test_security.py           SSRF, the XSS corpus, path safety, secrets, the import allowlist
    ├── test_erasure.py            DPDP erasure and the replay journal
    ├── perf/test_report_budget.py the 5,000-business ceilings, marked slow
    └── ui/                        Playwright: filter round-trip, selection persistence, print
```

**On `deploy/`.** It exists, but it is not a deploy directory in the usual sense — no unit file, no
container, no reverse proxy, no TLS certificate, because the service binds `127.0.0.1` and the only
client is the browser on the same machine. It holds three Windows artefacts:

| File | What it is | Installed by |
|---|---|---|
| `radar-start.cmd` | A `.cmd` that activates the venv, sets `RADAR_EMAIL_LIVE=yes`, and runs `python main.py serve` in a restart loop with a five-second delay | Placed in `shell:startup`, or run by the task below |
| `radar-task.xml` | Task Scheduler definition: triggers at logon **and** on workstation unlock, `StartWhenAvailable=true`, `MultipleInstancesPolicy=IgnoreNew` | `schtasks /Create /XML deploy\radar-task.xml /TN radar` |
| `radar-doctor-task.xml` | Task Scheduler definition: every 15 minutes, runs `main.py jobs doctor --alert` in a separate process that imports neither Flask nor `google.genai` | `schtasks /Create /XML deploy\radar-doctor-task.xml /TN radar-doctor` |

Lock 3 lives in `radar-start.cmd` and nowhere else. `python main.py serve` typed by hand in a terminal
does **not** set `RADAR_EMAIL_LIVE`, so the exploratory way to start the app is the one that cannot
transmit. That asymmetry is the entire reason lock 3 is an environment variable rather than a setting.

---

## 16.3 The six milestones

Estimates are in **evenings**, where an evening is roughly three focused hours for one person who has
already read the design documents. They assume Python 3.11+, familiarity with SQLite and Flask, and no
pair to review. They do **not** include the wall-clock waits in §16.6, which run in parallel.

| M | Goal | Evenings | Cumulative |
|---|---|---|---|
| M1 | Skeleton, schema, campaign creation. CLI only, no network | 8–10 | 8–10 |
| M2 | OSM discovery, Gemini research, scoring. Real rows | 14–18 | 22–28 |
| M3 | The HTML report and the read-only Flask app | 12–15 | 34–43 |
| M4 | Verification workflow and the state machine, enforced | 10–12 | 44–55 |
| M5 | Message generation, policy engine, preview, approval, NULL transport | 16–20 | 60–75 |
| M6 | Real Gmail sending, IMAP inbound, classification, handoff, audit hardening | 14–18 | 74–93 |

At four evenings a week that is five to six months. Stating that plainly up front is more useful than
discovering it in month three; and because M5 is a genuinely usable product, most of that time is spent
with something running rather than something half-built.

---

### M1 — Skeleton, schema, campaign creation

**Goal.** The database exists, is correct, and enforces the state machine before any code can write to
it. A campaign can be created, listed, re-opened. Nothing touches the network. This milestone is where
the safety model becomes structural rather than aspirational: after it, an illegal status transition is
a `sqlite3.IntegrityError`, not a code review comment.

**Files built.**

```
main.py                       (subcommands: migrate, verify-schema, bootstrap-owner, campaign)
config.example.yaml, pytest.ini, conftest.py, requirements.txt, .gitignore, README.md
config/.env.example
radar/{__init__,config,ids,db,models,paths,audit,auth,campaigns}.py
radar/migrations/001_bootstrap.sql ... 054_seed_reference.sql   (all 54, plus 055-057)
radar/migrations/README.md
tests/{conftest,test_schema,test_ids,test_migrations,test_audit_chain}.py
```

All 57 migrations are written in M1, including the WhatsApp block (040–045) and the analytics views
(051–053), per `01` §1.13.4: an empty table costs nothing, and a migration applied later against a live
database is a change to a running system, which is the more expensive of the two.

**Acceptance test.** `pytest tests/test_schema.py tests/test_migrations.py tests/test_audit_chain.py`
green, containing at minimum:

| Test | Asserts |
|---|---|
| `test_every_table_in_the_ownership_index_exists` | Every table named in `01` §1.1.1 is in `sqlite_master` after `migrate()` |
| `test_every_enum_column_has_a_check` | Walk `sqlite_master.sql`; every column whose name appears in `_CONTEXT.md` §6's enum lists carries a `CHECK (col IN (...))` |
| `test_pragmas_are_asserted_not_assumed` | `connect()` raises if `PRAGMA foreign_keys` returns 0 |
| `test_migration_tamper_raises` | Editing an applied file byte-for-byte makes the next `migrate()` raise `MigrationTamperError` and apply nothing |
| `test_migration_is_idempotent` | Two consecutive `migrate()` runs leave 57 `schema_version` rows and change no schema |
| `test_illegal_business_transition_aborts` | `UPDATE businesses SET status='CONTACTED'` from `AI_RESEARCHED` raises at the trigger |
| `test_send_requires_live_approval` | `UPDATE outreach_messages SET status='SENT'` with `approval_id IS NULL` raises. **This test exists in M1, four milestones before anything can send.** |
| `test_automation_mode_refuses_automated_values` | Both triggers reject `SEMI_AUTOMATED` and `FULLY_AUTOMATED` |
| `test_audit_log_is_append_only` | `UPDATE` and `DELETE` on `audit_log` both raise; `seq` has no gaps |
| `test_unregistered_id_prefix_raises` | `new_id("xyz")` raises `ValueError` naming `radar/ids.py` |

**The demo Sagar can run.**

```powershell
python main.py migrate --dry-run          # lists 57 pending files with their hashes
python main.py migrate                    # applies them
python main.py verify-schema              # exit 0
python main.py bootstrap-owner --email sagar@example.invalid --name "Sagar"
python main.py campaign new `
    --name "Dhule-Shirpur - 27 Aug 2026" `
    --cities dhule,shirpur `
    --categories HOSPITAL,SCHOOL `
    --min-size MEDIUM --min-score 70 --depth STANDARD
python main.py campaign list
python main.py campaign show cmp_01JB...
```

`campaign show` prints the campaign row with every counter rendering as `—`, not `0`, because no
discovery has run. That single detail is `_CONTEXT.md` §3 invariant 5 visible on a terminal, and it is
the thing to point at when explaining why the report will be trustworthy.

**Estimate: 8–10 evenings.** Most of it is DDL transcription and the trigger tests; the migration
runner and `ids.py` are half an evening each.

---

### M2 — OSM discovery, Gemini research, scoring

**Goal.** Real rows in `businesses`, `research_findings`, `sources` and `opportunities`, produced from
OpenStreetMap and the businesses' own websites, with every `OBSERVED` finding carrying a verified quote
from a stored source, and coverage stated per (city, category). This is the milestone where the free
stack's two hard edges appear: OSM thinness in Dhule and Shirpur, and the Gemini daily request cap.

**Files built.**

```
radar/{fetch,llm,discover,identity,contacts,phones,research,score,jobs}.py
radar/prompts/research/*
main.py                       (+ campaign start, campaign show --coverage, llm ping, worker)
tests/{test_discover,test_research,test_score,test_pii,test_jobs}.py
tests/fixtures/overpass/**, tests/fixtures/pages/**, tests/fixtures/gemini/**
```

`radar/jobs.py` arrives here rather than in M1 because until there is work to run, a job runtime is a
table with no rows. It ships with the five lanes, the claim protocol, the reaper, retries, the rate
buckets and the spend ledger; the scheduler and catch-up-on-launch arrive with M6's periodic jobs.

**Acceptance test.** `pytest tests/test_discover.py tests/test_research.py tests/test_score.py
tests/test_pii.py` green, no network. The four that decide whether the milestone is real:

| Test | Asserts |
|---|---|
| `test_worked_example_hospital` / `_school` / `_bakery` | The three `02` §2.13.6 fixtures reproduce `opportunity_score` 75, 65 and 49 **exactly**. If scoring drifts, these break |
| `test_pii_no_contact_in_research_payload` | The fully assembled Gemini request contains no `business_contacts` value for the business or its campaign siblings. `_CONTEXT.md` §2 asks for this test by name |
| `test_coverage_band_arithmetic` | The six SAMPLE rows in `02` §2.2.9 reproduce, including the `tag_rich_pct` demotion and the `min_absolute` floor. Shirpur / `RETAIL_STORE` comes out `LOW` at 17% |
| `test_quota_exhausted_pauses_not_fails` | A 429 with the day's cap reached defers the job, sets `campaigns.status='PAUSED'` with `pause_reason='QUOTA'`, and consumes **no** attempt |

Plus `test_observed_without_source_is_rejected`, `test_excerpt_must_match_document`,
`test_unknown_signal_is_not_zero`, `test_review_signals_are_none_not_zero`,
`test_overpass_cache_hit_makes_no_request`, `test_delimiter_cannot_be_closed_from_content`,
`test_score_is_deterministic`.

**The demo Sagar can run.**

```powershell
python main.py llm ping                   # one trivial generate_content; confirms the key works
python main.py campaign start cmp_01JB... --limit 5
python main.py worker --lanes io,llm      # in a second terminal; watch the log
python main.py campaign show cmp_01JB... --coverage
```

`campaign show --coverage` prints, for each (city, category), the elements found, the denominator, its
kind, the coverage percentage and the band — so the first thing Sagar sees is not "five hospitals in
Dhule" but "five hospitals in Dhule, coverage `LOW`, 17% of a population-model estimate of 30". Then:

```powershell
python main.py business show biz_01JB...  # findings grouped OBSERVED / INFERRED / UNKNOWN,
                                          # each OBSERVED one with its source URL and quoted excerpt
```

**Estimate: 14–18 evenings.** The fixture corpus is a third of it and is not optional: without stored
Overpass responses and stored Gemini payloads, every test costs quota and every test is flaky.

---

### M3 — The HTML report and the read-only Flask app

**Goal.** The artefact Sagar actually reads. One self-contained HTML file that opens offline with wifi
off, plus the same data served live at `127.0.0.1` behind a session. Read-only throughout: no verdict
can be recorded and nothing can be prepared. The app at the end of M3 is a viewer.

**Files built.**

```
radar/{report,report_queries,report_export}.py
radar/web/{app,public,ratelimit,openapi}.py
radar/web/api/{_list,_errors,campaigns,businesses,reports}.py
radar/web/templates/base.html, radar/web/templates/report/**
radar/web/static/{tokens.css,report.css,report.js}
radar/security.py                    (posture checks, so `serve` refuses a bad bind or a synced path)
main.py                              (+ report, serve)
tests/{test_report,test_report_archive,test_web_routes}.py, tests/perf/, tests/ui/
```

**Acceptance test.** The self-containment and honesty tests are what prove this milestone, not the
routes:

| Test | Asserts |
|---|---|
| `test_export_is_self_contained` | No `<link rel=stylesheet>`, no `<script src>`, no `http(s)://` in `src`/`href` except allow-listed source links |
| `test_export_is_offline` | With `app_base_url=None` the file contains zero absolute URLs to the app host and no `connect-src` beyond `'none'` |
| `test_export_has_no_send_control` | No element with the text `SEND` or class `send` exists in either rendering |
| `test_export_has_no_form_no_post_no_secret` | The bytes contain no `<form`, no `method=`, no `XMLHttpRequest`, and nothing matching the secret patterns |
| `test_kpi_sql_matches_python` | The twelve KPI aggregates equal counts computed in Python over the same fixture |
| `test_kpi_zero_vs_null_render_differently` | `class="na"` where NULL, a literal `0` where zero. `_CONTEXT.md` §3 invariant 5 |
| `test_no_coalesce_to_zero` | `report_queries.py` contains no `COALESCE(...,0)` on a nullable metric |
| `test_export_is_deterministic` | Two renders with a frozen clock are byte-identical |
| `test_city_card_for_empty_city` | A targeted city with no businesses still gets a card, showing `—` |
| `test_autoescape_business_name` | A business named `<img onerror=…>` renders escaped |
| `test_report_has_no_forms` | Zero `<form>` elements anywhere under `templates/report/` |

**The demo Sagar can run.**

```powershell
python main.py report --campaign cmp_01JB... --formats html,csv,xlsx
# -> data/reports/campaign/business_research_dhule_shirpur_2026-08-27.html
```

Turn wifi off. Open the file. Every KPI card, every city card, both tab strips, the filter bar, the
table, the expandable research panels and the source links all work. Then, with the app running:

```powershell
python main.py serve --port 8765
# browse http://127.0.0.1:8765/campaigns/cmp_01JB...
```

The live view is the same page with real navigations enabled. There is still no VERIFY button that
does anything — it links to `/verify/<id>`, which returns 404 until M4. That 404 is the correct state
of the world at the end of M3.

**Estimate: 12–15 evenings.** The twelve report queries and the twelve KPI aggregates are the bulk;
the inlining pass and the print stylesheet are one evening each.

---

### M4 — Verification workflow and the state machine, enforced

**Goal.** `VERIFIED` becomes something only a human can produce, provably, at three independent layers.
`CONTACT_READY` becomes a computed predicate that demotes itself when its inputs change. After M4 the
system knows the difference between "the AI likes this business" and "Sagar looked at it".

**Files built.**

```
radar/verify.py
radar/web/verify_views.py
radar/web/templates/verify/**
main.py                              (+ verify queue, verify show)
tests/test_verify.py
```

The migrations (009–012) already exist from M1; M4 is where the code that respects them is written.

**Acceptance test.** `pytest tests/test_verify.py` green, with the three-layer proof at its centre:

| Test | Asserts |
|---|---|
| `test_nine_checks_required_for_verified` | Eight passed; nine with one `NULL`; and nine passed on a superseded row all fail — **at the API, at the `CHECK`, and at the trigger**, independently |
| `test_only_verify_module_writes_business_status` | A grep over `radar/` finds exactly one `UPDATE businesses SET status` and it is inside `verify.set_status()` |
| `test_every_transition_in_the_table_is_reachable` | Each of T01–T29 executes against a fixture; every pair **not** in `business_status_transitions` aborts |
| `test_contact_ready_predicate_clause_matrix` | One fixture per clause: exactly that clause fails, `failing_clause` and `demote_to` are right, the other six pass |
| `test_predicate_never_looser_than_engine` | Over the fixture corpus, `predicate.ok` implies no `BLOCK` from `check_send_eligibility(stage='SELECT')` on any gate in `CLAUSE_GATES` |
| `test_no_bulk_verify_anywhere` | The endpoint 400s; the `CHECK` rejects `mode='BULK'` with `verdict='VERIFIED'`; a template grep is clean |
| `test_dwell_enforced_server_side` | Submitting at `dwell_required_ms - 1` returns 400 `DWELL_NOT_MET` even when the client reports a large `active_ms` |
| `test_required_sources_block_approve` | Approve is refused while a required source is neither visited nor waived; a nine-character waive reason is refused |
| `test_failed_check_forces_rejection` | `verdict='VERIFIED'` with any `passed=0` returns 400 `FAILED_CHECK_REQUIRES_REJECTION` |
| `test_no_send_control_in_verification_templates` | No template under `templates/verify/` contains a send, transmit or dispatch control |
| `test_verify_screen_has_no_outreach_link_for_unready_business` | The PREPARE OUTREACH link is absent, not merely disabled, when the predicate fails |

**The demo Sagar can run.**

```powershell
python main.py verify queue --campaign cmp_01JB...
# browse http://127.0.0.1:8765/verify/biz_01JB...
```

Work the screen: read the identity block, open two sources (the beacon records the visit), tick the
nine checks, add a note, approve. The business becomes `VERIFIED` and then `CONTACT_READY` by the
predicate. Then the demo that matters:

```powershell
python -c "import sqlite3;c=sqlite3.connect('data/radar.db');c.execute('PRAGMA foreign_keys=ON');c.execute(\"UPDATE businesses SET status='VERIFIED' WHERE id='biz_...OTHER'\");c.commit()"
# sqlite3.IntegrityError: business_status transition AI_RESEARCHED -> VERIFIED requires a verification
```

Forcing `VERIFIED` by hand fails at the database. That is the whole product rule, demonstrable in one
command.

**Estimate: 10–12 evenings.** The predicate and its demotion callers are the hard half; the screen
itself is two evenings.

---

### M5 — Message generation, policy engine, preview, approval, NULL transport

**Goal.** The complete outreach pipeline, ending in a `.eml` file on disk instead of a transmission.
Every gate runs, every policy rule runs, the approval row is written, the message is built as real MIME
bytes with real headers and a real unsubscribe address — and then it is written to
`data/outbox/2026-08-27/msg_01JB....eml` and nothing leaves the machine.

**This must be a genuinely usable milestone, not a stub.** The `.eml` files open in Outlook or
Thunderbird and read exactly as the recipient would read them. Sagar can forward one to himself. The
only difference between M5 and M6 is which class `build_transport()` returns.

**Files built.**

```
radar/{policy,messages,outreach}.py
radar/channels/{__init__,base,email,whatsapp}.py
radar/email/{types,transport,null_transport,factory,mime,threading,unsubscribe,checks,compliance}.py
radar/templates/messages/**, radar/prompts/messages/**
radar/web/api/outreach.py
radar/web/templates/outreach/{workspace,preview,confirm_dialog}.html
main.py            (+ outreach prepare, outreach preview, policy check, config check)
tests/{test_policy_eligibility,test_policy_claims,test_templates,test_messages,test_outreach,
       test_email_transport,test_send_containment}.py
```

**Acceptance test.** This is the largest test surface in the plan, and the milestone is not done until
all of it is green:

| Test | Asserts |
|---|---|
| `test_send_requires_live_approval` | Already passing since M1, now exercised by real code: `send_message()` with a null, revoked, or hash-mismatched approval raises before any transport is touched |
| `test_illegal_transitions_abort` | Every pair not in `outreach_status_transitions` raises, including `DRAFT -> SENT` and `PENDING_APPROVAL -> SENT` |
| `test_suppression_blocks_every_channel` | An `EMAIL`-scope suppression blocks `WHATSAPP`, `PHONE` and `MANUAL` for that business |
| `test_suppression_cannot_be_released_by_app` | No code path sets `released_at`; the trigger rejects a release without a matching audit row; `DELETE` raises |
| `test_gate_precedence_stable` | With every gate failing at once, `blocking_code` is `A_SUPPRESSED_BUSINESS` |
| `test_every_gate_has_a_sentence` | Every one of the forty gate codes renders a non-empty single sentence with all placeholders filled |
| `test_eligibility_is_read_only` | The engine executes no statement outside `SELECT` / `WITH` (connection trace) |
| `test_bad_examples_block` / `test_good_examples_pass` | Both §23 "bad" sentences BLOCK with the expected rule ids; both "good" ones pass when bound to an `INFERRED` finding |
| `test_unbound_factual_blocks` | Every `FACTUAL` segment with no finding id gives rule `F1` |
| `test_unknown_never_appears` | Rule `K2` on citation, `K3` on paraphrase above threshold. `_CONTEXT.md` §3 invariant 4 |
| `test_inferred_needs_hedge` | Each hedge alternative satisfies `K1`; a hedge in the *next* sentence does not |
| `test_pii_no_contact_in_prompt` | The four cases in `06` §6.13.0. **Never quarantine this test** |
| `test_rendered_variants_pass_policy` | Every variant combination of every industry block, rendered with fixture findings, passes the policy engine |
| `test_build_transport_defaults_to_null` | A config with no `email` block at all returns `NullEmailTransport` |
| `test_four_locks_each_alone` | Each lock opened three-at-a-time in all four combinations yields the null transport and an `ERROR` naming the closed lock |
| `test_null_transport_writes_parsable_eml` | `.eml` on disk parses with `email.parser`; `To` / `Subject` / body correct; `status='SENT'`; `provider='null'` |
| `test_t5_unsubscribe_header_must_match` | A draft whose `unsubscribe_token` disagrees with the built header is blocked |
| `test_t8_rejects_one_click_header` | A built message carrying `List-Unsubscribe-Post` is blocked |
| `test_double_click_produces_one_approval_and_one_job` | Two concurrent POSTs with one idempotency key: one approval row, one job, one write, both HTTP 200 |
| `test_suppression_between_preview_and_confirm_blocks` | Approve, insert a suppression, then send: the message becomes `CANCELLED` with `A_SUPPRESSED_EMAIL` and the transport is never called |
| `test_no_endpoint_sends_from_a_business_id` | A `url_map` walk: no route accepts a business id and transmits |
| `test_no_forbidden_send_labels` | No template contains a bulk or automatic send label |
| `test_send_control_is_local` | No send / transmit / dispatch control in any template outside `templates/outreach/confirm_dialog.html` |
| `test_send_containment` (nine sub-cases) | Each of `12` §12.2.10's nine layers, independently: disable eight, assert the ninth still stops the tenth message |

**The demo Sagar can run.**

```powershell
python main.py config check           # every secret present; email.transport = null
python main.py serve --port 8765
```

In the browser: tick the verified business in the grid, click PREPARE OUTREACH, choose EMAIL, wait
about fifteen seconds for `draft_outreach`, then open `/outreach/out_01JB...`. Read the nine panels —
business, channel, contact, research basis, opportunity, generated message, AI confidence, policy check,
contact history. Edit one sentence and watch the status fall back to `DRAFT` and the policy engine
re-run. Then click the button, which at this milestone reads **CONFIRM & WRITE .EML** and is
accompanied by a panel saying no message will leave the machine.

```powershell
python main.py policy check --draft out_01JB... --explain
Get-Content .\data\outbox\2026-08-27\msg_01JB....eml
```

The `.eml` has a `From`, a single `To`, a `Reply-To` carrying the `+msg_` tag, a `List-Unsubscribe`
`mailto:` with a real token, quoted-printable text, and the message Sagar approved. Open it in a mail
client. That is what the recipient would have received.

**Estimate: 16–20 evenings.** The policy engine is six to eight of them on its own, and it is the part
worth over-testing: it is the only thing standing between a hallucinated sentence and a stranger.

---

### M6 — Real Gmail sending, IMAP inbound, classification, handoff, audit hardening

**Goal.** Open the four locks. Add the inbound half, without which the outbound half is a system that
talks and does not listen.

**Files built.**

```
radar/email/{smtp_transport,pacing,caps,inbound,scrub,bounce,reconcile,events_map,health}.py
radar/{classify,handoff,notify}.py
radar/web/api/{handoffs,jobs,settings}.py
radar/web/templates/{handoffs,settings}/**
radar/jobs.py                  (+ the scheduler, catch-up-on-launch, the periodic registry)
radar/sql/audit/*.sql
radar/prompts/classify/**
deploy/{radar-start.cmd,radar-task.xml,radar-doctor-task.xml,WINDOWS.md}
main.py       (+ email *, audit *, dpdp *, backup *, doctor, incident *, jobs doctor, classify-*)
tests/{test_email_inbound,test_email_bounce,test_classify,test_handoff,test_erasure}.py
tests/fixtures/email/**, tests/fixtures/classify/corpus.jsonl
```

**Acceptance test.** The whole of `07` §7.16's fifty-row matrix, plus:

| Test | Asserts |
|---|---|
| `test_startup_order_unsubscribe_wins` | Worker starts with an unread unsubscribe mail and three `QUEUED` messages: `poll_inbox` completes first, the suppression exists before any `send_email` transmits, and that business's message is `CANCELLED` by gate A rather than sent |
| `test_scrubber_sentinel_corpus` | Build every prompt this system can assemble from fixtures whose contact values are known sentinels. **Fail if any sentinel appears in any LLM payload** |
| `test_same_eml_ingested_twice` | One `inbound_emails` row, one `responses` row, one `classify_response` job |
| `test_backlog_after_five_days_offline` | 600 waiting messages: three `poll_inbox` runs of 200, every message ingested exactly once, no run exceeds its duration budget |
| `test_ooo_never_calls_the_model` | `Auto-Submitted: auto-replied` produces `AUTO_REPLY`, no `responses` row, no handoff, **no LLM call** |
| `test_dsn_unattributable_creates_no_suppression` | A DSN with stripped headers matching two messages is `B4`, `UNMATCHED`, and suppresses nothing |
| `test_optout_is_honoured_without_the_model` | The deterministic stage writes the suppression in the same transaction as the reply, with the LLM unreachable |
| `test_no_module_reads_responses_into_a_message_body` | Import-graph and grep proof of `_CONTEXT.md` §3 invariant 6 |
| `test_ramp_day_three_caps_at_three` | `effective_daily_cap()` is 3 on ramp day 3 even with `daily_send_cap=25`; the fourth send defers to tomorrow |
| `test_laptop_closed_eighteen_hours` | `email.day` tokens refill by elapsed wall-clock time; no catch-up job runs; the cap is not silently reset to full |
| `test_indeterminate_send_reconciles` | Kill the process between transmit and record, with a matching Sent copy present: reconciliation finds it, records `SENT`, does not resend |
| `probe_P1` … `probe_P10` | All ten invariant probes return zero rows, run as tests against a fixture database seeded with each violation |

**The demo Sagar can run.** This one has a prerequisite: §16.6's account ramp must be complete and
`contact_policy.warmup_started_on` must be set. Then:

```powershell
python main.py email preflight            # SMTP AUTH + IMAP login + Sent folder + address length
python main.py email test-send --to <sagar's own second address>
python main.py email ramp-status          # ramp day index, today's cap, what has been used
```

Set `email.transport: gmail` and `email.live_send_enabled: true` in `config.yaml`, then start the app
through `deploy\radar-start.cmd` — which is the only launcher that sets `RADAR_EMAIL_LIVE=yes`. The
startup log prints one `LIVE EMAIL TRANSPORT ACTIVE` warning line naming the transport, the `From`
address, today's cap and the ramp day. The confirm dialog's button now reads **CONFIRM & SEND**.

Send one message to one real business. Then wait for the reply, and watch the chain: `poll_inbox` →
`inbound_emails` → `responses` → `classify_response` → `DEMO_REQUESTED` → `create_handoff` → Telegram
"HUMAN ACTION REQUIRED" → `/handoffs`. Sagar phones the business himself. Gate D5 now blocks every
further automated message to them, which is the correct end of the pipeline.

**Estimate: 14–18 evenings.** The inbound matching rules M1–M8 and the DSN parser are the surprise
cost: bounce handling is always three times the work it looks like.

---

### 16.3.7 Why M5 must be lived in before M6 is switched on

M6 is a small code change gated behind a config edit and an environment variable. That is exactly why
it needs a deliberate barrier in front of it: there is no engineering friction to slow it down, so the
friction has to be a decision.

**The rule: do not open lock 2 until at least three weeks and forty `.eml` files have passed.**

Six reasons, in order of how much they cost if ignored.

| # | Reason |
|---|---|
| 1 | **The policy engine's error rate is unknown until it has seen real drafts.** Its false negatives are the dangerous ones — a hallucinated claim it let through. Forty `.eml` files read carefully is the only way to find out whether `check_draft()` is calibrated or merely present. At M5 a false negative costs a file; at M6 it costs a stranger's opinion of Sagar |
| 2 | **The blast radius of a template regression differs by three orders of magnitude.** A bad variant pool at M5 produces forty identical files in `data/outbox/`, which is a five-minute discovery. The same bug at M6 produces forty near-identical cold emails from one Gmail account, which is the precise shape `07` §7.4.6 identifies as the thing that gets accounts suspended |
| 3 | **The account ramp is wall-clock, not work.** `07` §7.4.7 steps 11 and 12 require seven days of ordinary human use of the mailbox and three more days of hand-sent test mail across five receivers. Those ten days have to happen anyway. Living in M5 while they run costs nothing and is the only sequencing that does not waste them |
| 4 | **The `.eml` corpus is the input to the only question that matters.** §54 says optimise for qualified conversations, not messages sent. Read forty drafts and mark each one "would I actually send this?". If the answer is yes six times out of forty, the fault is upstream — in discovery, in scoring, in verification — and fixing the mailer would not have helped. That diagnosis is only available before anything is sent |
| 5 | **Suppression, duplicate and frequency gates need history to be exercised at all.** Gates F2, F6, G1, G2 and G3 all compare against prior sends. With an empty `outreach_messages` table they are structurally unreachable, and an untested gate is an assumption. Weeks of `.eml` writes give them rows to compare against, and `test_frequency_gates_against_fixtures` becomes a claim about code that has actually run |
| 6 | **Sagar's own approval habit needs calibrating before it has consequences.** §16.10 risk R5 is rubber-stamping, and it is the risk with no technical mitigation. Forty preview screens where the button is harmless is where the habit of actually reading them is formed. Forming it after the button transmits is forming it too late |

**The exit criteria from M5,** as a checklist rather than a feeling:

- [ ] At least 40 drafts have been generated and 40 `.eml` files exist in `data/outbox/`
- [ ] At least 20 of them have been opened in a real mail client and read end to end
- [ ] Each of those 20 carries a recorded verdict: would Sagar have sent it, yes or no
- [ ] The yes rate is at or above 70%. Below that, fix the pipeline, not the transport
- [ ] Zero policy-engine false negatives found by hand in those 20 (a claim the research does not support that the engine passed)
- [ ] `python main.py policy check --draft <id> --explain` has been run on at least 5 of them and its reasoning agrees with Sagar's
- [ ] The similarity guard has been exercised: two businesses in the same category produced visibly different messages
- [ ] The full account ramp in §16.6 is complete, including the ten wall-clock days
- [ ] `python main.py email preflight` passes and `email test-send` landed in an inbox, not Promotions
- [ ] The `Message-ID` question from `07` §7.4.7 step 9 has an answer recorded in `config.yaml`

---

## 16.4 The first vertical slice

The smallest end-to-end path that proves the architecture: **one city, one category, five businesses,
one report, one verification, one dry-run message.** It touches every layer once. It is the thing to
build toward when M1–M5 feel like five separate projects, and it is worth running end to end at the
close of every milestone with whatever exists so far.

Target: **Dhule / `HOSPITAL` / 5 businesses.** Dhule because it is the honest case — coverage is thin,
so the coverage machinery is exercised rather than bypassed. `HOSPITAL` because `02` §2.2 rates OSM
coverage best for `HEALTHCARE`, so five real elements will actually come back.

### 16.4.1 The exact files this slice needs

Nothing outside this list is required for the slice to run end to end. The rest of the tree can be
absent or stubbed.

```
main.py
config.yaml, config/.env
radar/config.py            Config, setup_logging
radar/ids.py               new_id
radar/db.py                connect, migrate, verify_schema
radar/models.py            Campaign, Business, Contact, ResearchRun, Finding, Source,
                             Opportunity, Verification, Draft, Message, Approval
radar/audit.py             audit.write
radar/auth.py              bootstrap_owner, login, require_role
radar/campaigns.py         create_campaign, start_campaign, campaign_counters
radar/jobs.py              the registry, claim, the io and llm lanes, the worker loop
radar/fetch.py             safe_fetch
radar/llm.py               generate(), the 429 path, token accounting
radar/discover.py          discover_city (Overpass), coverage_for
radar/identity.py          business_key, upsert_business
radar/contacts.py          extract_contacts, normalise
radar/research.py          research_business (SYNTHESISE + ASSESS at STANDARD depth)
radar/score.py             score_business, assess_opportunity
radar/report.py            build_campaign_report
radar/report_queries.py    Q1-Q12
radar/verify.py            open_verification, answer_check, submit_verification,
                             set_status, contact_ready_predicate
radar/policy.py            check_send_eligibility, check_draft
radar/messages.py          draft_outreach
radar/outreach.py          create_selection, prepare, approve, send_message
radar/channels/{base,email}.py
radar/email/{types,transport,null_transport,factory,mime,threading,unsubscribe,checks}.py
radar/web/app.py           create_app + the routes below
radar/web/verify_views.py  /verify/<id> and its API
radar/web/api/{campaigns,businesses,outreach,reports}.py
radar/web/templates/       base.html, report/*, verify/*, outreach/*
radar/web/static/          tokens.css, report.css, report.js
radar/migrations/          001-057
radar/prompts/research/    system.v1.txt, user.v1.j2, assess.system.v1.txt
radar/prompts/messages/    system.v3.txt, user.v3.j2
radar/templates/messages/  MANIFEST.yaml, channel/email.base.v3.j2, industry/hospital.v2.yaml,
                             slots/slots.v4.yaml, variation/pools.v4.yaml
```

Routes the slice needs, and no others: `GET /campaigns/<id>`, `GET /business/<id>`,
`GET /verify/<id>` and its four verification API calls, `POST /api/v1/selections`,
`POST /api/v1/outreach/prepare`, `GET /outreach/<draft_id>`,
`POST /api/v1/outreach/messages/<message_id>/send`.

### 16.4.2 The exact commands

```powershell
# ---- one-time setup -------------------------------------------------------
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
Copy-Item config\.env.example config\.env
notepad config\.env                       # paste GEMINI_API_KEY. Nothing else is needed yet.

python main.py migrate
python main.py verify-schema              # exit 0
python main.py bootstrap-owner --email sagar@example.invalid --name "Sagar"
python main.py doctor                     # ACLs, disk, encryption posture, config sanity

# ---- 1. RESEARCH ----------------------------------------------------------
python main.py campaign new `
    --name "Dhule slice - 27 Aug 2026" `
    --cities dhule `
    --categories HOSPITAL `
    --min-score 0 `
    --depth STANDARD
# -> cmp_01JB2K...

python main.py campaign start cmp_01JB2K... --limit 5
python main.py worker --lanes io,llm --until-idle
# ~10 Gemini requests, ~8 minutes of wall time, well inside one day's quota

python main.py campaign show cmp_01JB2K... --coverage
#   Dhule / HOSPITAL   found 5   expected 30 (POPULATION_MODEL)   17%   LOW
# The coverage line is the point of running this in Dhule.

# ---- 2. REPORT ------------------------------------------------------------
python main.py report --campaign cmp_01JB2K... --formats html
# -> data\reports\campaign\business_research_dhule_2026-08-27.html
# Turn wifi off. Open it. Every number came from a SELECT; empty metrics show as a dash.

python main.py serve --port 8765          # note: this does NOT set RADAR_EMAIL_LIVE
# browse http://127.0.0.1:8765/campaigns/cmp_01JB2K...

# ---- 3. VERIFY ------------------------------------------------------------
# browse http://127.0.0.1:8765/verify/biz_01JB2K...
#   read the identity block, open both sources (the visit beacon records them),
#   tick all nine checks, write a note, click APPROVE.
python main.py verify show biz_01JB2K...
#   status VERIFIED -> CONTACT_READY, 9/9 checks, verification ver_01JB2K...

# ---- 4. SELECT ------------------------------------------------------------
# In the grid, tick the row. The checkbox is enabled only because the predicate passed.
# -> selections row sel_01JB2K..., state SELECTED, with a SELECT-stage eligibility snapshot

# ---- 5. PREVIEW -----------------------------------------------------------
# Click PREPARE OUTREACH, choose EMAIL. draft_outreach runs (1 Gemini request, ~15 s).
# browse http://127.0.0.1:8765/outreach/out_01JB2K...
python main.py policy check --draft out_01JB2K... --explain
#   PASS. F1 bound: 3 factual sentences -> fnd_..., fnd_..., fnd_...
#         K1 hedged: 1 inferred sentence carries "may"
#         R1 unsubscribe present; R7 2 URLs (limit 2)

# ---- 6. DRY-RUN SEND ------------------------------------------------------
# Click CONFIRM & WRITE .EML in the confirm dialog.
Get-ChildItem .\data\outbox\2026-08-27\
Get-Content .\data\outbox\2026-08-27\msg_01JB2K....eml
python main.py audit explain --draft out_01JB2K... --html slice.html
```

### 16.4.3 What the slice proves

| Layer | Proved by |
|---|---|
| Schema and state machine | The business moved `AI_RESEARCHED -> NEEDS_VERIFICATION -> VERIFIED -> CONTACT_READY` and every step was a permitted transition |
| Free discovery | Five real businesses out of Overpass, with a coverage band attached that says the list is short on purpose |
| Free LLM, safely | Ten Gemini requests, no `business_contacts` value in any payload, every `OBSERVED` finding carrying a verified quote |
| Honest arithmetic | The report's empty metrics render `—`; the KPI counts equal a Python count over the same rows |
| The human gate | The `.eml` exists because Sagar ticked nine boxes and clicked a button; forcing it any other way raises at the database |
| Traceable claims | `policy check --explain` names the finding id behind every factual sentence |
| Auditability | `audit explain` reconstructs the whole path from stored rows with no code re-run |
| The transport seam | The identical code path, with lock 1 flipped, sends real mail. Nothing else changes |

If those eight hold on one business in Dhule, they hold on four hundred across four cities. The rest of
the build is breadth, not risk.

---

## 16.5 The CLI surface

`main.py` uses argparse **subcommands** rather than the flat flags of `option_chain_reader/main.py`,
because there are around sixty verbs here and a flat namespace would collide. The docstring keeps the
house shape: one line of purpose, then `Examples`, then the commands that matter with an inline comment
each.

```python
#!/usr/bin/env python3
"""business_radar - city-wise business research, human-verified outreach.

Researches businesses city by city, scores them for software opportunity, produces an HTML
report, and walks one human through verification before any message is written. Nothing here
sends anything unless four separate locks are open; the default configuration writes .eml
files to data/outbox/ and touches no network on the way out.

Examples
--------
  python main.py migrate                          # apply pending schema migrations
  python main.py doctor                           # ACLs, disk, backups, config, secrets
  python main.py campaign new --cities dhule,shirpur --categories HOSPITAL --depth STANDARD
  python main.py campaign start cmp_01JB... --limit 5
  python main.py worker --lanes io,llm            # run the job lanes in the foreground
  python main.py report --campaign cmp_01JB...    # write the self-contained HTML report
  python main.py serve --port 8765                # Flask+waitress on 127.0.0.1 (NOT live email)
  python main.py policy check --draft out_01JB... --explain
  python main.py email preflight                  # SMTP+IMAP auth check; sends nothing
  python main.py audit explain --draft out_01JB... --html why.html
  python main.py backup now                       # VACUUM INTO + age-encrypt + verify
"""
```

### 16.5.1 Every subcommand

**Schema and setup**

| Command | Flags | Example |
|---|---|---|
| `migrate` | `--dry-run`, `--target N` | `python main.py migrate --target 023` |
| `verify-schema` | — | `python main.py verify-schema` |
| `bootstrap-owner` | `--email`, `--name` | `python main.py bootstrap-owner --email sagar@example.invalid --name "Sagar"` |
| `config check` | `--json` | `python main.py config check` |
| `doctor` | `--fix-acl`, `--security`, `--audit-deps`, `--json` | `python main.py doctor --security` |
| `auth enrol-totp` | `--email` | `python main.py auth enrol-totp --email sagar@example.invalid` |
| `auth benchmark` | — | `python main.py auth benchmark` |
| `auth rekey-totp` | `--confirm` | `python main.py auth rekey-totp --confirm` |
| `auth unlock` | `--email` | `python main.py auth unlock --email sagar@example.invalid` |

**Campaigns and research**

| Command | Flags | Example |
|---|---|---|
| `campaign new` | `--name`, `--cities`, `--categories`, `--industries`, `--min-size`, `--min-score`, `--depth {STANDARD,DEEP}` | `python main.py campaign new --name "Q3 Nashik" --cities nashik --categories SCHOOL,COLLEGE --min-size MEDIUM --min-score 70 --depth STANDARD` |
| `campaign list` | `--status`, `--limit` | `python main.py campaign list --status LIVE` |
| `campaign show` | `<id>`, `--coverage`, `--json` | `python main.py campaign show cmp_01JB... --coverage` |
| `campaign start` | `<id>`, `--limit N`, `--city SLUG` | `python main.py campaign start cmp_01JB... --limit 5` |
| `campaign pause` / `resume` / `cancel` / `archive` | `<id>`, `--reason` | `python main.py campaign pause cmp_01JB... --reason "quota"` |
| `business show` | `<id>`, `--findings`, `--sources`, `--json` | `python main.py business show biz_01JB... --sources` |
| `business research` | `<id>`, `--depth DEEP`, `--reason RECHECK` | `python main.py business research biz_01JB... --depth DEEP --reason RECHECK` |
| `llm ping` | — | `python main.py llm ping` |

**Verification**

| Command | Flags | Example |
|---|---|---|
| `verify queue` | `--campaign`, `--city`, `--limit` | `python main.py verify queue --campaign cmp_01JB... --city dhule` |
| `verify show` | `<business_id>`, `--json` | `python main.py verify show biz_01JB...` |

There is no `verify approve` subcommand, and there will not be one. A verdict requires the nine-check
screen and a server-side dwell measurement; a CLI approve would be exactly the bulk-verify path `04`
§4.8 refuses to build.

**Reports**

| Command | Flags | Example |
|---|---|---|
| `report` | `--campaign ID`, `--daily [DATE]`, `--formats html,csv,xlsx`, `--filters JSON`, `--include-contacts` | `python main.py report --campaign cmp_01JB... --formats html,xlsx` |
| `report list` | `--campaign`, `--fmt` | `python main.py report list --campaign cmp_01JB... --fmt html` |

**Outreach (never transmits)**

| Command | Flags | Example |
|---|---|---|
| `outreach prepare` | `--business ID`, `--channel EMAIL` | `python main.py outreach prepare --business biz_01JB... --channel EMAIL` |
| `outreach preview` | `<draft_id>`, `--raw` | `python main.py outreach preview out_01JB...` |
| `outreach eligibility` | `--business ID`, `--channel`, `--stage SELECT` | `python main.py outreach eligibility --business biz_01JB... --channel EMAIL --stage PREVIEW` |
| `outreach record-manual` | `--message ID`, `--note` | `python main.py outreach record-manual --message msg_01JB... --note "sent from my phone"` |
| `policy check` | `--draft ID`, `--explain`, `--json` | `python main.py policy check --draft out_01JB... --explain` |
| `policy recheck` | `--since DATE`, `--dry-run` | `python main.py policy recheck --since 2026-08-01 --dry-run` |

`outreach prepare` builds and stores a draft. There is no `outreach send` subcommand: the only send
path is `POST /api/v1/outreach/messages/<message_id>/send`, registered on the session blueprint, and
`test_send_is_registered_only_on_the_session_blueprint` asserts it.

**Serving and workers**

| Command | Flags | Example |
|---|---|---|
| `serve` | `--host 127.0.0.1`, `--port 8765`, `--no-worker` | `python main.py serve --port 8765` |
| `worker` | `--lanes llm,io,export,notify,maint`, `--until-idle`, `--once` | `python main.py worker --lanes io,llm --until-idle` |
| `jobs list` | `--state`, `--type`, `--lane`, `--limit` | `python main.py jobs list --state DEAD` |
| `jobs retry` | `--job ID` or `--type T --since DATE` | `python main.py jobs retry --type send_email --since 2026-08-26` |
| `jobs doctor` | `--alert`, `--json` | `python main.py jobs doctor --alert` |

`serve` binds `127.0.0.1` and refuses any other host with an error rather than a warning. It starts the
in-process worker unless `--no-worker` is given.

**Email (M6)**

| Command | Flags | Example |
|---|---|---|
| `email preflight` | — | `python main.py email preflight` |
| `email test-send` | `--to ADDR` | `python main.py email test-send --to sagar.other@example.invalid` |
| `email poll` | `--once`, `--verbose` | `python main.py email poll --once` |
| `email reingest` | `<path.eml>` | `python main.py email reingest .\saved\reply.eml` |
| `email find-sent` | `<message_id>` | `python main.py email find-sent msg_01JB...` |
| `email ramp-status` | — | `python main.py email ramp-status` |
| `email health` | `--json` | `python main.py email health` |
| `email halt` / `resume` | `--reason` | `python main.py email halt --reason "bad template shipped"` |
| `email breaker-reset` | `--reason` | `python main.py email breaker-reset --reason "false alarm, 5.7.1 was one domain"` |
| `email reconcile` | `--since DATE` | `python main.py email reconcile --since 2026-08-20` |

**Responses and handoffs**

| Command | Flags | Example |
|---|---|---|
| `response show` | `<id>`, `--raw` | `python main.py response show rsp_01JB...` |
| `classify-corpus add` | `--response ID` | `python main.py classify-corpus add --response rsp_01JB...` |
| `classify-eval` | `--corpus PATH`, `--live` | `python main.py classify-eval --corpus tests/fixtures/classify/corpus.jsonl` |
| `handoff list` | `--state OPEN`, `--older-than-days` | `python main.py handoff list --state OPEN` |
| `handoff show` | `<id>`, `--brief` | `python main.py handoff show hnd_01JB... --brief` |

**Audit, DPDP, backups, incidents**

| Command | Flags | Example |
|---|---|---|
| `audit verify` | `--full`, `--from SEQ` | `python main.py audit verify --full` |
| `audit head` | — | `python main.py audit head` |
| `audit explain` | `--draft ID`, `--json`, `--html OUT` | `python main.py audit explain --draft out_01JB... --html why.html` |
| `audit timeline` | `--business ID`, `--all` | `python main.py audit timeline --business biz_01JB...` |
| `audit query` | `<name>`, `--since`, `--csv OUT`, `--verify` | `python main.py audit query sent_last_week --since 2026-08-01 --verify` |
| `audit probes` | `--json` | `python main.py audit probes` |
| `audit export` | `--day DATE`, `--no-upload` | `python main.py audit export --day 2026-08-26` |
| `audit verify-reports` | `--campaign`, `--since`, `--repair-index` | `python main.py audit verify-reports --since 2026-01-01` |
| `audit record-rotation` | `--secret NAME` | `python main.py audit record-rotation --secret GEMINI_API_KEY` |
| `dpdp preview-erasure` | `--email ADDR` | `python main.py dpdp preview-erasure --email x@y.invalid` |
| `dpdp erase` | `--email`, `--request-audit aud_...` | `python main.py dpdp erase --email x@y.invalid --request-audit aud_01JB...` |
| `dpdp export-subject` | `--email`, `--out PATH` | `python main.py dpdp export-subject --email x@y.invalid --out sar.json.gz` |
| `dpdp replay-erasures` | `--db PATH`, `--since TS` | `python main.py dpdp replay-erasures --db .\restore\radar.db --since 2026-08-27T02:00:00Z` |
| `backup now` / `list` | — | `python main.py backup now` |
| `backup restore-test` | `--archive PATH` | `python main.py backup restore-test --archive data\backups\radar-2026-08-27T02-00-00Z.db.age` |
| `incident open` / `close` | `--kind`, `--note`, `--incident` | `python main.py incident open --kind MISDIRECTED_SEND --note "wrong contact"` |

---

## 16.6 Setup prerequisites

Two kinds of item live here and they are not interchangeable. **Work** items take an evening and can
be done whenever. **Wall-clock** items take calendar days no matter how hard anyone works, and if they
are started in month five they add days to month five.

### 16.6.1 Start these NOW — they are wall-clock, not work

| # | Item | Elapsed | Why it cannot be compressed |
|---|---|---|---|
| **W1** | **Create the dedicated Gmail account.** Local part **25 characters or fewer** — `07` §7.4.2's arithmetic means a longer one silently breaks the `+unsub-<32 hex>` address at 64 octets | minutes to create, but see W4 | Account *age* is the dominant reputation input for a free Gmail sender (`07` §7.4.6). An account created on the day of the first send is the exact shape of a throwaway. Create it in week one of M1 and let it get old while the software gets written |
| **W2** | **Enable 2-Step Verification on that account** | minutes | An App Password cannot be generated without it. Do it immediately after W1 |
| **W3** | **Generate the App Password for Mail** and put it in `config/.env` as `OUTREACH_GMAIL_APP_PASSWORD`. **Enable IMAP** in Gmail settings | minutes | IMAP is the only inbound path in the entire system. Without it, `poll_inbox` has nothing to poll |
| **W4** | **Use the account like a person for at least a week.** Send Sagar a few ordinary messages from it; reply to them from the other side; read them. Set a real display name and a profile photo | **7 days minimum** | `07` §7.4.7 step 11. This gives the account a shape other than "created, then began mailing strangers". It is the only account-age signal that can be honestly produced, and it cannot be done in an afternoon |
| **W5** | **Send 8–10 messages by hand** from the account to Sagar's own addresses across Gmail, Outlook.com, Yahoo, Zoho and one corporate Microsoft 365 tenant. Open each. **Reply to each from the receiving side.** Confirm inbox placement | **3 days**, after W4 | Step 12. It is also a real test of five receivers' filters before a stranger is one of them |
| **W6** | **The six-week ramp itself.** `contact_policy.warmup_started_on` is set by a human at the end of W5, and the schedule runs 3 / 5 / 8 / 12 / 15 / 20 per day before reaching the 25 cap | **6 weeks after W5** | It bounds blast radius as much as reputation: week 1's cap of three means the first categorically wrong message reaches three people, not thirty. Starting the clock at the end of W5 — i.e. around M2 — means the ramp is finished by the time M6 is |
| **W7** | **Get a Gemini API key** from Google AI Studio; put it in `config/.env` as `GEMINI_API_KEY` | minutes | Blocks M2 entirely. Trivial to obtain, but there is no reason to discover a problem with it in month two |
| **W8** | **Publish the GitHub Pages identity page** (optional but recommended): real name, registered business name, address, phone, one paragraph on the software, one line naming the outreach address as the business correspondence address | an evening + DNS/CDN propagation | It should be live and indexed *before* it is cited in a message. A URL in a cold email that 404s is worse than no URL |

**W1 through W6 form one chain with a floor of about seven and a half weeks** from creating the account
to reaching a 20/day cap. Started at the beginning of M1, it finishes around M3. Started at the
beginning of M6, it delays the first real send by two months. That is the single strongest argument in
this document for doing something on day one that has nothing to do with code.

### 16.6.2 Work items — do them when the milestone needs them

| # | Item | Needed by |
|---|---|---|
| S1 | Python 3.11+, a venv, `pip install -r requirements.txt` | M1 |
| S2 | `config.yaml` from `config.example.yaml`; `config/.env` from `config/.env.example` | M1 |
| S3 | `python main.py bootstrap-owner`, then enrol TOTP | M1 |
| S4 | **BitLocker on the volume holding `data/`.** `python main.py doctor` refuses to pass without it | M1 |
| S5 | Owner-only ACLs on `config/.env`, `data/radar.db*`, `data/backups/`, `logs/` — `doctor --fix-acl` emits the `icacls` commands | M1 |
| S6 | `data/` must **not** be inside OneDrive, Dropbox or any synced folder. `radar/config.py` refuses to boot if it is | M1 |
| S7 | Pin Overpass city relation ids once, by hand, into `discovery.osm.cities`; record a radius and its justification where no usable relation exists (Shirpur) | M2 |
| S8 | Set a real `User-Agent` with a contact address for Overpass, Nominatim and the site fetcher. A blank one gets an IP banned from the public Overpass instances | M2 |
| S9 | Download the registry tables into `data/registries/`: MCA21 company master extract, UDISE+ school list for the target districts, the India Post PIN directory | M2 |
| S10 | Build the fixture corpus: Overpass responses for two cities, ~15 stored HTML pages, recorded Gemini payloads for the three worked examples | M2 |
| S11 | Telegram: create the bot with BotFather, get `TELEGRAM_BOT_TOKEN`, send it one message to learn `TELEGRAM_CHAT_ID` | M6 (M2 if alerts are wanted early) |
| S12 | Generate `UNSUBSCRIBE_SIGNING_SECRET`, `SUPPRESSION_HMAC_PEPPER`, `FIELD_ENCRYPTION_KEY`, `AUDIT_EXPORT_HMAC_KEY` — 32 random bytes each | M5 (the unsubscribe token is built at M5, even in dry-run) |
| S13 | An external SSD or USB drive for backup copy 2, plus an `age` keypair whose identity is stored **off** the laptop — second USB and on paper | M1. A backup habit started at M6 has nothing to back up from M1 to M5 |
| S14 | A cloud bucket for copy 3, client-side `age`-encrypted, with an application key that can write but not delete. Not in the same Google account as the mailbox | M3 |
| S15 | Install the two Task Scheduler entries from `deploy/` | M6 |

### 16.6.3 The pre-launch checklist, before the first real message

Tick every line. `python main.py doctor --security` automates the ones marked auto.

- [ ] `python main.py config check` shows every required secret present and valid (auto)
- [ ] `python main.py verify-schema` exits 0 (auto)
- [ ] `python main.py audit verify --full` reports an unbroken chain (auto)
- [ ] `python main.py audit probes` returns zero rows on all ten (auto)
- [ ] `python main.py auth benchmark` reports argon2id verification between 150 ms and 500 ms (auto)
- [ ] `python main.py email preflight` authenticates SMTP and IMAP and sends nothing (auto)
- [ ] `python main.py email ramp-status` shows ramp day ≥ 0 and a cap of 3
- [ ] `python main.py backup restore-test` on the newest archive succeeds
- [ ] The halt sentinel works: `email halt`, confirm the queue stops, `email resume`
- [ ] The identity page is live, correct, and its URL is in `identity.site_url`
- [ ] `contact_policy.automation_mode` is `HUMAN_APPROVAL` and probe P8 confirms it
- [ ] The `.eml` exit criteria in §16.3.7 are all ticked
- [ ] Sagar can state, without looking it up, what `python main.py email halt` does and where the `HALT_SENDING` file lives

---

## 16.7 Test strategy

The house rule from `_CONTEXT.md` §1 is pytest in `tests/`, **no network**, fixtures over mocks. That
is not a style preference here: the network in this system is a free-tier LLM with a daily request cap
and a public Overpass instance with a fair-use policy. A test suite that calls either is a test suite
that cannot be run twice in an hour.

### 16.7.1 The offline guarantee

`tests/conftest.py` installs a `socket.socket` guard at session start. Any test not explicitly marked
`live` that opens a socket fails with the test name and the address it tried to reach. The three marks:

| Mark | Runs by default | Contents |
|---|---|---|
| *(unmarked)* | yes | Everything. No network, no clock dependence, under two minutes for the whole suite |
| `slow` | no | `perf/test_report_budget.py` at 5,000 businesses; the 600-message IMAP backlog |
| `ui` | no | Playwright: filter hash round-trip, selection persistence across filtering, `beforeprint` hydration |
| `live` | no | `classify-eval --live`, `email preflight`. Run by hand, never in a default run |

### 16.7.2 What is unit tested (pure functions, table-driven)

These are the cheapest and most valuable tests in the build, because the logic they cover is where the
subtle bugs live and none of it needs a database:

| Area | Module | Shape |
|---|---|---|
| Id prefixes | `radar/ids.py` | Registry membership, ULID sortability, unknown prefix raises |
| Contact normalisation | `radar/policy.py`, `radar/phones.py` | Every row of `05` §5.9.2's table, plus invalid inputs producing `valid=False` |
| Scoring arithmetic | `radar/score.py` | Round-half-up, coverage floors, NULL-vs-zero, renormalisation, determinism |
| Coverage bands | `radar/discover.py` | The six SAMPLE rows of `02` §2.2.9 reproduce exactly |
| The claim policy | `radar/policy.py::check_draft` | One case per rule, plus one deliberate near-miss per banned regex that must **not** fire |
| Gate precedence | `radar/policy.py` | All forty gates failing at once yields `A_SUPPRESSED_BUSINESS` |
| MIME construction | `radar/email/mime.py` | Devanagari subject RFC 2047 round-trip, 78-column wrapping, quoted-printable |
| Threading | `radar/email/threading.py` | `In-Reply-To` and `References` chains at sequence 3 |
| Filename slugging | `radar/report.py` | The five-city case and the `Nashik Road` case |
| DSN parsing | `radar/email/bounce.py` | The eleven status codes; `5.2.2` soft, `5.7.1` `BLOCKED` and suppressing nothing |
| Deterministic classification | `radar/classify.py` | Every lexicon rule, with the model unreachable |

### 16.7.3 What needs a fixture corpus

Five corpora. Each is checked into `tests/fixtures/`, each is recorded once from the real world, and
each replaces a network call that would otherwise be made hundreds of times.

| Corpus | Contents | Recorded from | What it guards |
|---|---|---|---|
| **Overpass responses** | Raw JSON per (city, category) for Dhule/`HOSPITAL`, Dhule/`SCHOOL`, Shirpur/`RETAIL_STORE`, Nashik/`HOSPITAL`, plus a truncated response at `element_cap`, a `landuse=industrial` polygon, and a `disused:shop=bakery` node | One real Overpass run per pair, saved verbatim | Coverage arithmetic, dedupe, lifecycle-prefix skipping, truncation detection, and `test_overpass_cache_hit_makes_no_request` |
| **Scraped pages** | ~15 stored HTML files: a hospital site, a school site, a bakery with no website (positive absence), three contact pages with real-shaped emails and phone numbers, a page with `display:none` injected instructions, a page containing the literal string `</untrusted_content>`, a page with a GSTIN, and a Devanagari-heavy page | Saved by hand with `curl` at build time | Excerpt verification, prompt-injection defence, hidden-text stripping, and the whole PII split |
| **Gemini payloads** | Recorded `generate_content` request/response pairs for the three worked examples, a malformed response, a response with an extra key, a response whose excerpt does not match the source document, and a repair round-trip | Captured once with a debug flag that writes the payload to disk | Every research test, without spending quota |
| **Reply texts** | `.eml` files: an `INTERESTED` reply, a `DEMO_REQUESTED` reply, an out-of-office with `Auto-Submitted: auto-replied`, an opt-out saying only "unsubscribe", a reply whose only "unsubscribe" is in the quoted footer of our own message, a forwarded reply quoting our headers, a reply with a correct `+msg_` tag but no `In-Reply-To`, a reply 200 days late, a reply from an address never contacted, and one containing an email + Indian mobile + URL for the scrubber | Assembled by hand from real message shapes | M1–M8 attribution, the thirteen categories, the scrubber, dedupe |
| **DSN bounces** | Real Gmail DSNs: `5.1.1` user unknown, `5.2.2` mailbox full, `5.7.1` blocked, one with returned headers stripped and a unique `Final-Recipient`, one stripped with an ambiguous recipient, one with two per-recipient blocks, a `4.7.0` deferral naming `googlemail.com`, and a `no-reply@accounts.google.com` "Critical security alert" | Produced by mailing deliberately-bad addresses from the account during W5 | Every attribution rule, and the two cases that must suppress *nothing* |

Plus a sixth that is not a network recording but is corpus-shaped: **`tests/fixtures/xss/`**, a list of
hostile business names (`<img onerror=…>`, `=cmd|'/c calc'!A1`, a name containing `</script>`, a
1,000-character name) driven through every template and every export writer.

### 16.7.4 The tests guarding each safety invariant

These are the tests that matter most. Each `_CONTEXT.md` §3 invariant gets named test functions, and
every one of them exists **before** the code path it guards can transmit.

**Invariant 1 — No send path exists that does not pass through a human approval record.**

| Test | Layer | Lands in |
|---|---|---|
| `test_send_requires_live_approval` | DB trigger: `status='SENT'` with `approval_id IS NULL`, with a revoked approval, and with a mismatched `body_hash` all raise | M1 |
| `test_only_the_web_approve_handler_writes_approvals` | Grep: exactly one `INSERT INTO outreach_approvals` in the codebase | M5 |
| `test_send_is_registered_only_on_the_session_blueprint` | `url_map` walk: the send route is on no other blueprint | M5 |
| `test_no_endpoint_sends_from_a_business_id` | `url_map` walk: no route takes a business id and transmits | M5 |
| `test_approval_requires_human_session` | Probe P5 as a test: `session_auth_method` must be `PASSWORD` or `PASSWORD_TOTP`, and an `OUTREACH_APPROVED` audit row with `actor_kind='HUMAN'` must exist | M5 |
| `test_double_click_produces_one_approval_and_one_job` | Two concurrent POSTs, one idempotency key | M5 |
| `test_worker_cannot_import_web` | Import graph: the worker cannot reach the approve handler | M5 |

**Invariant 2 — `outreach_status` may only reach `SENT` from `APPROVED`.**

| Test | Layer | Lands in |
|---|---|---|
| `test_illegal_transitions_abort` | Every pair absent from `outreach_status_transitions` raises, `DRAFT -> SENT` and `PENDING_APPROVAL -> SENT` named explicitly | M1 (schema), M5 (code) |
| `test_two_workers_one_message` | Two workers claim the same `QUEUED` message: one `SENT`, one `already_handled` | M5 |
| `test_transition_table_and_python_agree` | The Python transition map is a permutation of the table's rows — neither is allowed to have an entry the other lacks | M5 |

**Invariant 3 — Opt-out is absolute, permanent, and not clearable by the app.**

| Test | Layer | Lands in |
|---|---|---|
| `test_suppression_blocks_every_channel` | An `EMAIL`-scope suppression blocks `WHATSAPP`, `PHONE` and `MANUAL` for that business | M5 |
| `test_suppression_cannot_be_released_by_app` | No code path sets `released_at`; the trigger rejects a release without a matching audit row; `DELETE` raises | M5 |
| `test_suppression_between_preview_and_confirm_blocks` | Approve, suppress, then send: `CANCELLED` with `A_SUPPRESSED_EMAIL`, the transport never called | M5 |
| `test_startup_order_unsubscribe_wins` | `poll_inbox` completes before any `send_email` transmits on worker start | M6 |
| `test_optout_is_honoured_without_the_model` | The deterministic stage writes the suppression with the LLM unreachable and the quota exhausted | M6 |
| `test_unsubscribe_fifteen_cases` | The fifteen `07` §7.7.9 cases, including the quoted-footer false positive | M6 |
| `test_same_unsubscribe_ingested_fifty_times_concurrently` | One `suppressions` row, one audit row | M6 |
| `probe_P3_no_send_to_suppressed_contact` | The nightly probe as a test, against a seeded violation | M6 |

**Invariant 4 — Every claim traces to a stored fact, typed OBSERVED / INFERRED / UNKNOWN.**

| Test | Layer | Lands in |
|---|---|---|
| `test_observed_without_source_is_rejected` | The finding is dropped, `findings_rejected` increments, and it is **not** silently relabelled `INFERRED` | M2 |
| `test_excerpt_must_match_document` | A paraphrased excerpt drops the citation, and the `OBSERVED` finding drops with it | M2 |
| `test_inferred_cascade_to_fixpoint` | An inference on an inference on a dropped observation is itself dropped | M2 |
| `test_run_cannot_complete_with_unsourced_observed` | The DB trigger aborts the transaction | M2 |
| `test_unbound_factual_blocks` | Rule `F1`: a factual segment with no finding id | M5 |
| `test_cross_business_binding_blocks` | Rule `F2`: a finding belonging to another `business_id` | M5 |
| `test_sourceless_finding_blocks` | Rule `F4`: a finding with zero `finding_sources` rows | M5 |
| `test_inferred_needs_hedge` | Rule `K1`, and a hedge in the *next* sentence does not satisfy it | M5 |
| `test_unknown_never_appears` | Rules `K2` and `K3`, on citation and on paraphrase | M5 |
| `test_bad_examples_block` / `test_good_examples_pass` | §23's four literal sentences | M5 |
| `test_hedge_removal_blocks` | Editing "may help" to "will help" turns a PASS into a BLOCK | M5 |
| `probe_P7_unknown_finding_behind_a_claim` | The probe as a test | M6 |

**Invariant 5 — Report numbers come from SQL aggregates over real rows; no data renders `—`, not `0`.**

| Test | Layer | Lands in |
|---|---|---|
| `test_kpi_sql_matches_python` | The twelve KPI aggregates equal a Python count over the same fixture | M3 |
| `test_kpi_zero_vs_null_render_differently` | `class="na"` where NULL, a literal `0` where zero | M3 |
| `test_no_coalesce_to_zero` | `report_queries.py` contains no `COALESCE(...,0)` on a nullable metric | M3 |
| `test_unknown_signal_is_not_zero` | A `SiteProbe` with `reachable=None` gives `digital_maturity IS NULL` | M2 |
| `test_review_signals_are_none_not_zero` | `review_volume` and `review_recency` are `None` with `why_null='NO_FREE_SOURCE_IN_V1'` | M2 |
| `test_city_card_for_empty_city` | A targeted city with no businesses still gets a card, showing dashes | M3 |
| `test_xlsx_null_metrics_are_empty_cells` | `sheet["I2"].value is None`, not `0` | M3 |
| `test_no_template_reads_a_campaign_counter` | Templates read the view, never a denormalised counter that could drift | M3 |

**Invariant 6 — The AI classifies inbound responses; it never replies.**

| Test | Layer | Lands in |
|---|---|---|
| `test_no_module_reads_responses_into_a_message_body` | Import graph plus grep: nothing in `radar/messages.py` or `radar/channels/` reads `responses.body_text` | M6 |
| `test_classify_imports_no_channel` | `radar/classify.py` imports neither `radar.channels` nor `radar.email` transports | M6 |
| `test_no_reply_control_in_any_template` | Grep over `templates/`: no reply, respond or send-reply control on any response or handoff screen | M6 |
| `test_handoff_produces_advice_not_a_draft` | `recommend_next_action()` returns a rule id and prose; it creates no `outreach_drafts` row | M6 |
| `test_ooo_never_calls_the_model` | An `Auto-Submitted` reply produces no `responses` row and no LLM call | M6 |

**And the one `_CONTEXT.md` §2 asks for by name — no contact value may reach an LLM.**

| Test | Asserts | Lands in |
|---|---|---|
| `test_pii_no_contact_in_research_payload` | The fully assembled research request contains no `business_contacts` value for the business or its campaign siblings | M2 |
| `test_pii_contact_page_split` | One pass over a contact-page fixture yields the contacts in the database and none of them in `prompt_text` | M2 |
| `test_pii_scrubber_raises_on_injected` | A hand-spliced contact value raises `ContactLeak` and fails the job | M2 |
| `test_pii_business_name_survives` | "Dr. Patil Hospital" is not redacted from a page about Dr. Patil Hospital | M2 |
| `test_pii_gstin_survives` | A GSTIN reaches the prompt and becomes a `REGULATORY` finding | M2 |
| `test_pii_no_contact_in_prompt` | The four drafting cases in `06` §6.13.0 | M5 |
| `test_pii_hydration` | `<<CONTACT_GREETING>>` survives the model rewrite byte-identical; an unhydrated draft gives `R8` BLOCK | M5 |
| `test_scrubber_sentinel_corpus` | **Build every prompt this system can assemble** from fixtures whose contact values are sentinels; fail if any sentinel appears in any payload | M6 |
| `test_only_llm_imports_genai` | No module under `radar/` imports `google.genai` except `radar/llm.py`, and no module imports `anthropic` at all | M2 |

`test_scrubber_sentinel_corpus` is the backstop: the other eight test known paths, and it tests all
paths by construction. It must never be quarantined, skipped or marked `xfail`. If it fails, the
correct response is to stop calling the model until it passes.

### 16.7.5 Tests that must run with no network, specifically

Every unmarked test, without exception — but four categories are worth calling out because the
temptation to make them live is real:

| Category | Why it must stay offline |
|---|---|
| Every research test | Each live run costs 2–3 requests out of a 250/day ceiling. A 40-test research suite run twice would consume half a day's quota and then start failing with 429s that look like bugs |
| Every classification test | Same arithmetic, and worse: a flaky classifier test that re-runs eats the reserve set aside for the drafting Sagar is actually waiting on |
| Every discovery test | Overpass fair use is a small number of concurrent slots per IP. A test suite hammering it gets the laptop's IP banned, and the ban is not instant to lift |
| Every email test | An accidental live send from a test is the one failure this whole document is arranged to prevent. `tests/conftest.py` binds `email.transport` to `null` and asserts `RADAR_EMAIL_LIVE` is unset before any test in `test_email_*` runs |

### 16.7.6 What is deliberately not tested

Naming these keeps their absence a decision rather than an oversight: the exact wording of any
Gemini output (it is non-deterministic; the tests assert structure, binding and policy compliance);
Gmail's actual placement behaviour (unmeasurable from here — `07` §7.9.4 is explicit that complaints
are invisible); the visual appearance of the report beyond contrast ratios and the absence of forms;
and Overpass's own data quality, which is what the coverage bands exist to *report* rather than assert.

---

## 16.8 Operating it on a laptop

### 16.8.1 What runs when the machine is on

| Component | How it starts | What it does |
|---|---|---|
| `main.py serve` | `deploy\radar-start.cmd`, triggered at logon **and** on workstation unlock | waitress on `127.0.0.1:8765`, plus the in-process worker unless `--no-worker` |
| The five job lanes | Inside `serve` | `llm` (research, drafting, classification), `io` (fetching, sending, polling), `export` (reports), `notify` (Telegram), `maint` (backups, sweeps) |
| The scheduler | Inside `serve` | Materialises schedule ticks, applies catch-up, refills rate buckets |
| The reaper | Inside `serve`, `maint` lane | Reclaims expired leases; runs once synchronously at startup before any lane claims |
| `main.py jobs doctor --alert` | Task Scheduler, every 15 minutes | Opens the database read-only, checks `worker.down`, `disk.low`, `queue_stalled`, `backup.failed`, notifies through Telegram. Imports neither Flask nor `google.genai` |

The restart loop in `radar-start.cmd` has no backoff, so the limiter lives in the app: `serve` refuses
to start and exits 2 if `logs/supervisor.log` shows more than `jobs.worker.max_restarts_per_hour`
(default 6) restarts in the last hour. A crash loop that drains a battery overnight is worse than being
down.

### 16.8.2 What catch-up-on-launch does

The machine is closed at night and asleep in between, so no schedule can assume its slot was observed.
Every periodic job carries a `catch_up` policy and a `catch_up_grace_minutes` window, applied once at
startup, in `priority DESC, type ASC` order:

| Job | Slot (IST) | Catch-up | Grace | Behaviour after a night off |
|---|---|---|---|---|
| `backup_db` | 00:20 | `ONCE` | none — **always run it, however late** | Runs first, before catch-up enqueues anything else, so a launch that then crashes still leaves a backup. There is no staleness at which "do not back up" is right |
| `prune_logs` | 00:40 | `ONCE` | generous | Runs late; harmless |
| `staleness_sweep` | 01:00 | `ONCE` | wide | Three missed nights run **once**, not three times |
| `suppression_sync` | 02:00 | `SKIP` | — | Missing a night costs nothing: every suppression it would have written was already written by the path that produced the evidence |
| `daily_report` | 07:35 | `ONCE` | **14 hours** | Opened at 18:00, the morning report still runs and lands. Opened the next afternoon, the slot is dropped with one `INFO` line rather than delivering yesterday's news as today's |
| `poll_inbox` | every 2 min | `SKIP` | none | The mailbox **is** the queue. One poll after twelve hours offline collects twelve hours of mail in a single pass; running the missed slots too would achieve eleven no-ops |
| `handoff_sla_sweep` | every 5 min | `SKIP` | none | The clock is stored on the row; the next sweep sees the same breach |
| `score_calibration` | monthly | `ONCE` | 7 days | Advisory only. Run on the 4th, fine. Run on the 25th, dropped |

Rate buckets need no catch-up code at all: they refill by elapsed wall-clock time, so a two-hour sleep
leaves every bucket correctly full and an eighteen-hour sleep does not silently reset the daily cap.

**The honest limitation.** A machine that is off cannot page anybody, and no design fixes that. The
doctor's `worker.down` rule is written as "the doctor ran, so the machine is on, and the worker still
is not working". Its own existence is the liveness signal; its absence proves nothing.

### 16.8.3 Backups

Three copies, per `12` §12.12.1:

| Copy | Where | Survives | Encryption | Cadence |
|---|---|---|---|---|
| 1 | `data/backups/` on the laptop | An operator mistake — a bad migration, a wrong `DELETE`. **Not** theft, not disk failure | BitLocker only | Nightly, `backup_db` at 00:20 |
| 2 | External SSD or USB, kept at home | Laptop theft, loss, disk failure | **`age`, always** | **Weekly, by hand.** `doctor` flags a copy 2 older than 14 days |
| 3 | Cloud object storage, client-side encrypted | The house | **`age`, always, key the provider never sees** | Nightly upload after copy 1 |

Copy 2 is the one that matters and the one that requires a habit. Two rules with no exceptions: the
`age` identity never lives in `config/.env` and never on the encrypted volume alone — it lives on a
second USB and on paper, in a different physical place; and `SUPPRESSION_HMAC_PEPPER` is never in the
same archive as the database, because an archive holding both is an archive of plaintext opt-out
addresses. A restore test runs monthly: `python main.py backup restore-test --archive <path>`. An
untested backup is a hypothesis.

### 16.8.4 What Sagar does day to day

**Morning, five minutes.** Open the laptop. `radar-start.cmd` fires on unlock. Read the 07:35 Telegram
daily report if it landed. Open `http://127.0.0.1:8765/` and glance at the quota strip and the job
queue depth.

**Research, hands-off.** If a campaign is live, the worker spends the day's research quota — about 75
businesses at `STANDARD` — in well under an hour of the machine being on. Nothing to supervise. When
the cap is reached the campaign pauses with one Telegram line naming the campaign, how many businesses
remain, and when it resumes (roughly 12:30–13:30 IST, when Google's Pacific-time quota day rolls over).

**Verification, the real work, 20–45 minutes.** Open `/campaigns/<id>`, work the verification queue.
Each business is: read the identity block, open two sources, tick nine boxes, approve or reject. The
server-measured dwell means this cannot be rushed below its floor, which is the point. Ten to fifteen
businesses is a comfortable evening.

**Outreach, 10–20 minutes.** Select the verified businesses worth writing to. PREPARE OUTREACH, wait
about fifteen seconds per draft, read each preview properly. At M5 the button writes a `.eml`; at M6 it
sends. Either way it is one business at a time, and the daily cap (3 rising to 25) means this is a
short session by construction.

**Replies, whenever Telegram buzzes.** A "HUMAN ACTION REQUIRED" message means a business said
something interesting. Open the brief, read the full reply, and **phone them**. The system stops here
by design: gate D5 blocks every further automated message to that business the moment the handoff
opens.

**Weekly, ten minutes.** Plug in the backup drive. Run `python main.py doctor` and read the findings.
Skim `python main.py audit query sent_last_week`. Check `email health` and `email ramp-status`.

**Monthly.** `backup restore-test`. `audit verify --full`. Read `classify-eval` agreement and correct
any misclassifications, which is also how the labelled corpus grows.

---

## 16.9 Quota model and the working rhythm

### 16.9.1 The arithmetic

`gemini-2.5-flash` on the Google AI Studio free tier is metered in requests per minute, tokens per
minute and requests per day. Exceeding any returns `429 RESOURCE_EXHAUSTED`. The published values at
time of writing — **verify against the current rate-limits page before shipping** — are RPM 10,
TPM 250,000, RPD 250.

```yaml
llm:
  quota: { rpm: 10, tpm: 250000, rpd: 250 }
  daily_request_cap: 200        # global headroom under 250
research:
  quota:
    daily_request_cap: 150      # research's share; the other 50 are reserved for drafting
    pause_campaign_on_exhaustion: true
```

The 150/50 split is a **reservation**, not a queue limit. If drafting is idle, research still stops at
150 — because a campaign that eats the whole day leaves Sagar unable to draft a message to the one
business that answered, and that message is worth more than the four hundredth researched bakery.

| Depth | Requests per business | **Businesses per day** | If every business needs a repair |
|---|---|---|---|
| `STANDARD` | 2 (GATHER skipped, SYNTHESISE + ASSESS) | **75** | 50 |
| `DEEP` | 3 (GATHER + SYNTHESISE + ASSESS) | **50** | 37 |

RPD is the only ceiling that binds. RPM 10 permits five `STANDARD` businesses a minute, and the
polite fetcher (1 req/s per host, 6 pages, 40–90 s per business) is far slower than that. TPM 250,000
against roughly 11,500 tokens per `STANDARD` business at five a minute is 57,500 — under a quarter of
the ceiling. There is no daily token cap at all.

### 16.9.2 What that means for the calendar

| Campaign | Depth | Requests | Days at 150/day |
|---|---|---|---|
| 50 businesses, one city | `STANDARD` | 100 | under 1 |
| 150 businesses, two cities | `STANDARD` | 300 | 2 |
| 400 businesses, four cities | `STANDARD` | 800 | 5–6 |
| 400 businesses, four cities | `DEEP` | 1,200 | 8 |
| 400 `STANDARD` + a `DEEP` re-run on the 80 borderline scorers | mixed | 1,040 | 7 |

The campaign creation form must print this arithmetic **before** the run starts:
`400 businesses at STANDARD: about 800 requests, roughly 6 days at your 150/day research cap.` A
number seen before the run is worth more than a Telegram alert during it.

The recommended pattern, and what the form should default to: **run the city at `STANDARD`, then
re-research at `DEEP` only the businesses that scored within 10 points of `min_opportunity_score`, or
that came back `MEDIUM` confidence with a `HIGH`-band raw score.** On a quota budget the targeted
second pass is strictly better than raising the depth of the whole campaign — `DEEP` costs one extra
request out of 150, and it buys `research_confidence`, which is exactly what is uncertain for the
borderline cases and already settled for the rest.

### 16.9.3 The daily rhythm this produces

The consequence is the opposite of a paid stack's: **a day's research quota is spent in well under an
hour of the laptop being switched on.** The machine not running 24/7 costs nothing. What costs is the
calendar.

| Time | What happens | Who is involved |
|---|---|---|
| Laptop opens | Catch-up runs; backup first, then the missed daily report if inside its 14-hour grace | Nobody |
| First 30–50 minutes on | The `llm` lane spends the day's 150 research requests — 75 businesses at `STANDARD` | Nobody |
| Roughly 12:30–13:30 IST | Google's quota day rolls over (Pacific midnight). A campaign paused at 11:00 resumes after lunch, not tomorrow | Nobody |
| Any time | Verification queue: 10–15 businesses, 20–45 minutes | **Sagar, and only Sagar** |
| 09:30–18:30 IST, MON–SAT | The send window. Today's cap (3 rising to 25) with at least 4 separate hours involved, because `email.hour` is 6 | Sagar approves each one |
| Every 2 minutes | `poll_inbox` | Nobody |
| Whenever a reply arrives | Telegram pages; Sagar phones the business | **Sagar, personally** |
| 07:35 next morning | The daily report | Nobody |

**The shape to internalise:** a four-city, four-hundred-business campaign is a *week*, and the right
response is to run it as a week rather than to try to make it a day. The pipeline never degrades to fit
— it does not switch to a smaller model, a shorter prompt or a shallower depth to squeeze inside the
remaining quota, because a campaign half-researched at two different depths produces two incomparable
halves and destroys §53's entire point.

---

## 16.10 Risks, ranked

Ranked by expected cost — probability multiplied by how bad it is — not by how likely they are.

### R1 — Gmail account suspension

**Cost: catastrophic and immediate.** The account is the only identity, the only outbound path, and the
only inbound path. Losing it loses sending, reply capture, unsubscribe capture and bounce capture in a
single event. Worse, reputation is per-account and invisible to us: there is no Postmaster Tools
without a domain, so the first signal is the suspension itself.

**Mitigation, layered:**

- The six-week ramp (3 / 5 / 8 / 12 / 15 / 20 → 25), started as wall-clock work in §16.6 W6
- A hard 40/day ceiling in `rate_buckets['email.day']` that the ramp ending does **not** raise; going higher requires no complaint proxy over 500 sent messages, a bounce rate under 2%, and a manual `contact_policy` edit that writes a `CONFIG_CHANGED` audit row
- `email.hour` capacity 6, so a day's allowance cannot leave in one twenty-minute burst. Burst shape is a stronger abuse signal than volume, and it is the one an automated sender produces by accident
- Policy binds at 25, which is 5% of Gmail's own ~500. Hitting Google's limit does not produce a tidy error; it produces a `421 4.7.0` or a 24-hour outbound lock, sometimes with a security notice
- The AUP argument's expiry conditions are enforced mechanically, not remembered: one recipient per message (`T1`), a per-business rendered body (the similarity guard), per-message human approval (invariant 1), a working unsubscribe (`T5`, `R1`, `H5`), automatic permanent suppression on complaint
- W4's seven days of ordinary human use, so the account has a shape other than "created, then began mailing strangers"
- Three `5.7.x` `BLOCKED` bounces across three domains in 24 hours sets `contact_policy.email_enabled = 0` automatically
- The account is disposable **because** it is kept empty of everything else — no personal mail, no other services

### R2 — Sagar rubber-stamps verification

**Cost: severe, and it is the one risk with no technical fix.** The entire safety argument reduces to
"a human looked". If the human ticks nine boxes without reading, the system is a spam cannon with an
audit trail — and the audit trail makes it *worse*, because it documents that he approved it.

**Mitigation:**

- Server-measured dwell (`test_dwell_enforced_server_side`), not a client timer that a fast click defeats
- Required source visits: at least two sources must be opened, and the visit beacon records it. A waive needs a reason of real length
- No bulk verify anywhere, at three layers — the endpoint 400s, the `CHECK` rejects it, the template grep is clean
- A failed check forces a rejection reason from a controlled taxonomy; it cannot be a shrug
- The nine checks are questions about *this* business with its research beside them, not a generic acknowledgement
- `04` §4.7's anti-rubber-stamp measures: check order varies, and the verification history across a `business_key` is shown so a repeat looks like a repeat
- **The behavioural mitigation is M5.** Forty preview screens where the button is harmless is where the habit of reading them forms. That is the argument in §16.3.7 reason 6, and it is the only mitigation that addresses the actual mechanism
- The measurable early warning: a verification session averaging under 90 seconds per business, and a rejection rate near zero. A rejection rate of zero over fifty businesses means the checklist is not being used

### R3 — Invisible spam complaints

**Cost: high, and undetectable until it becomes R1.** One complaint in 100 messages is 1% — ten times
the threshold that gets an ESP account reviewed. At 15 a day, one annoyed recipient is a statistical
event. And with no domain there is no feedback loop, no DMARC aggregate report and no Postmaster Tools:
`07` §7.9.4 is explicit that complaints are invisible to us.

**Mitigation:**

- Measure the proxies that *are* visible: `v_email_health` on bounce rate and reply rate. Forty sends in 30 days with zero replies, after a non-zero previous month, raises a warning
- Optimise for the thing that reduces complaints: §54's qualified conversations. A message that is genuinely about this business is not the message people report
- The policy engine's whole purpose is preventing the message most likely to be reported — one asserting a fact about a stranger's internal operations that the sender cannot know
- A working `mailto:` unsubscribe in every message, plus the plain-text instruction to reply STOP, so the annoyed recipient has a cheaper option than the report button
- Any reply classified `COMPLAINT` writes both `BUSINESS`- and `EMAIL`-scope suppressions, raises a `HIGH` alert, and keeps a `P7Y` audit row
- Volume itself is the mitigation: at 15–25 a day the absolute number of possible complainants is bounded
- **Accept honestly** that this cannot be measured directly, and treat the reply rate as the health signal it is a proxy for

### R4 — OSM coverage in Dhule and Shirpur

**Cost: moderate, but insidious.** OSM is decent in Nashik, patchy in Jalgaon, and thin in Dhule and
Shirpur. The failure is not that the list is short — it is that a short list *reads* as complete. Sagar
works down six retail businesses in Shirpur and concludes there is no retail opportunity in Shirpur.
What actually happened is that nobody has mapped Shirpur's main market street.

**Mitigation:**

- `02` §2.2.9's `discovery_coverage`: an explicit band per (city, category), computed against a registry count or a population model, **printed in the report and on the campaign screen**. "We found six businesses in Shirpur, coverage `LOW`, 17%" is a finding, not a footnote
- Registries as a second source where they are genuinely better: UDISE+ for schools, MCA21 for companies, MIDC unit directories and district chamber lists — which are unusually good for Dhule and Shirpur manufacturers, precisely where OSM is worst
- The India Post PIN directory used *negatively*: reject an OSM element whose `addr:postcode` belongs to a different taluka, which is the main way a radius-bounded Shirpur query picks up a Dondaicha business
- Category-aware expectations: OSM is best for `HOSPITALITY`, `HEALTHCARE` and `EDUCATION`, weakest for `RETAIL` and `DISTRIBUTION`. Start campaigns where coverage is real
- The radius bound for Shirpur is recorded as a judgement with its value, not presented as a boundary
- Where coverage is `LOW`, a manual seed list is a legitimate input — the schema does not care whether a business arrived from Overpass or from Sagar typing it in, as long as the source is recorded

### R5 — Gemini free-tier limits and model quality

**Cost: moderate. Two distinct failures wearing one name.**

*Throughput.* 250 RPD caps the system at ~75 businesses a day. A four-city campaign is a week.

*Quality.* `gemini-2.5-flash` is a fast model doing research synthesis, message drafting and reply
classification. Its failure mode is confident fabrication — exactly the sentence §23 forbids.

**Mitigation:**

- Throughput: quota is a wall, not a bill. A 429 defers the job, pauses the campaign and consumes no attempt. Resumption is automatic at the Pacific-midnight rollover, and catch-up-on-launch means a laptop opened at 18:00 resumes a campaign paused at 11:00 that morning
- Throughput: the calendar expectation is stated on the campaign form before the run starts
- Throughput: the limits live in `config.yaml`, not in constants, because Google changes them without notice and a hard-coded ceiling becomes wrong silently
- Quality: **every `OBSERVED` finding must carry an excerpt that matches its source document character by character.** Fabrication fails this mechanically and the finding is dropped, not relabelled
- Quality: `INFERRED` findings that depend on a dropped observation cascade to a fixpoint
- Quality: the policy engine is a second, independent check on the drafting model — every factual sentence must name a finding id, and an unbound one is `F1` BLOCK
- Quality: classification runs a deterministic stage **first**. Opt-out, complaint and out-of-office are decided by lexicon, in the same transaction as the reply, whether or not the model is reachable. With no HTTPS unsubscribe endpoint, that deterministic stage *is* the opt-out system
- Quality: `classify-eval` against a labelled corpus with thresholds — 85% overall accuracy, 95% interest recall, under 2% confident errors. Human corrections feed the corpus
- Never degrade silently: no fallback to a smaller model, a shorter prompt or a shallower depth to fit inside remaining quota
- Both the model id and the prompt version are pinned in the row that stores every output, so a quality regression is attributable

### R6 — Scope creep toward automation

**Cost: low probability, total severity.** Every constraint in this document is a friction that a
frustrated evening will want to remove. The specific shape: "just let it auto-approve the ones scoring
above 90", or "just send the follow-ups automatically, they're template anyway". Each is one line of
code and each destroys the product.

**Mitigation, and this is why the safety model is structural rather than procedural:**

- The send function takes an `approval_id` and rejects a null one **at the database**. Auto-approval requires forging an approval row, which requires a human session and writes an audit row
- `automation_mode` has two triggers refusing `SEMI_AUTOMATED` and `FULLY_AUTOMATED`, and probe P8 checks nightly
- `send_whatsapp` is not registered in the job registry at all — there is no code path a config flag could enable
- No template outside `templates/outreach/confirm_dialog.html` may contain a send control, asserted by grep
- Probe P9 — a business in `CONTACTED` with no `BUSINESS_VERIFIED` audit row — is §45 as a single query, run nightly, paging Telegram on any row
- `test_send_containment.py` asserts each of the nine send-stop layers works **alone**. A defence in depth never tested with the other layers removed is a defence whose depth is a guess
- §16.11's definition of done includes none of these being weakened. Removing one is a decision to be made deliberately, in daylight, and it will require editing tests whose names say what they protect
- The honest note: **the real defence is that Sagar wrote §45 himself.** Every mechanism above exists to make sure that a tired evening cannot quietly overrule a considered decision

---

## 16.11 Definition of done for the MVP

A checklist to tick. The MVP is done when every line is true.

**Schema and safety**

- [ ] `python main.py migrate` applies 57 files to an empty database and `verify-schema` exits 0
- [ ] Re-running `migrate` is a no-op; editing an applied file makes it raise `MigrationTamperError`
- [ ] Every enum column in `_CONTEXT.md` §6 has a `CHECK` constraint, asserted by a test
- [ ] `UPDATE outreach_messages SET status='SENT'` with a null approval raises at the database
- [ ] Forcing `businesses.status='VERIFIED'` by hand raises at the trigger
- [ ] `python main.py audit probes` returns zero rows on all ten
- [ ] `python main.py audit verify --full` reports an unbroken chain
- [ ] `test_send_containment.py` passes with each of the nine layers exercised alone

**Research**

- [ ] A four-city campaign completes and pauses cleanly on quota, resuming at the next rollover
- [ ] Coverage bands print per (city, category), including at least one `LOW` band Sagar has read
- [ ] `test_worked_example_hospital` / `_school` / `_bakery` reproduce 75 / 65 / 49 exactly
- [ ] Every `OBSERVED` finding in the database has at least one `finding_sources` row
- [ ] `test_scrubber_sentinel_corpus` passes and has never been skipped
- [ ] `test_only_llm_imports_genai` passes; no module anywhere imports `anthropic`

**Report**

- [ ] The exported HTML opens correctly with wifi off, with no external request attempted
- [ ] The export contains no `<form>`, no send control, and no absolute URL to the app host
- [ ] Two renders with a frozen clock are byte-identical
- [ ] Every KPI equals a Python count over the same rows; a metric with no data renders `—`
- [ ] CSV and XLSX exports preserve business, city, industry, score, research, verification, contact and outreach status
- [ ] `report_exports` has one row per generated file, with a correct `sha256`, and `audit verify-reports` reports OK

**Verification**

- [ ] The only way to `VERIFIED` is the nine-check screen, refused at three independent layers
- [ ] `CONTACT_READY` demotes automatically when a suppression, a contact change or a re-score invalidates a clause
- [ ] There is no bulk-verify control, endpoint or template anywhere
- [ ] A verification older than `verification_valid_days` demotes before selection, not merely at preview
- [ ] Every one of T01–T29 executes; every unlisted transition aborts

**Outreach**

- [ ] Every gate in `05` §5.9.1 renders a complete one-sentence explanation with all placeholders filled
- [ ] Both §23 "bad" sentences BLOCK; both "good" ones pass when bound to an `INFERRED` finding
- [ ] Every factual sentence in every generated draft names a `research_findings` id
- [ ] No `UNKNOWN` finding appears in any draft, cited or paraphrased
- [ ] A double-clicked CONFIRM produces one approval, one job and one send
- [ ] A suppression inserted between approval and send cancels the message before transmission
- [ ] The similarity guard has visibly produced different messages for two businesses in one category

**Email**

- [ ] `build_transport()` returns `NullEmailTransport` on a config with no `email` block at all
- [ ] Each of the four locks, closed alone, forces the null transport and logs an `ERROR` naming it
- [ ] `python main.py serve` typed by hand does **not** produce a live transport
- [ ] The `.eml` files parse, open in a mail client, and read as the recipient would read them
- [ ] `email preflight` passes; `email test-send` landed in an inbox with three authentication passes
- [ ] The `Message-ID` survival question from `07` §7.4.7 step 9 has a recorded answer
- [ ] The ramp is running from a human-set `warmup_started_on`, and `email ramp-status` agrees
- [ ] An unsubscribe mail becomes a `suppressions` row within one poll interval, tested end to end
- [ ] A real Gmail DSN fixture attributes correctly, deactivates the contact and writes a suppression
- [ ] `poll_inbox` completes before any `send_email` transmits on worker start

**Responses and handoff**

- [ ] All thirteen §33 categories are reachable and tested
- [ ] The deterministic stage honours an opt-out with the LLM unreachable and the quota exhausted
- [ ] An out-of-office produces no `responses` row and no LLM call
- [ ] An interested classification creates a handoff, pages Telegram, and blocks every automated path
- [ ] No screen anywhere has a reply box, and no module reads a response into a message body

**Operations**

- [ ] Both Task Scheduler entries are installed and have fired at least once each
- [ ] The app survives a hard kill: leases expire, jobs resume, no duplicate sends
- [ ] Catch-up-on-launch behaves correctly for each of the eight periodic jobs after a night off
- [ ] `data/` is on a BitLocker volume, outside any synced folder, with owner-only ACLs
- [ ] Three backup copies exist; copy 2 is `age`-encrypted on removable media less than 14 days old
- [ ] `backup restore-test` has succeeded at least once
- [ ] The `age` identity is stored off the laptop, in a different physical place
- [ ] `python main.py doctor --security` reports no findings

**The product rule**

- [ ] Every business in `CONTACTED` or beyond has a `BUSINESS_VERIFIED` audit row (probe P9)
- [ ] Every sent message has a live approval and a §48 audit row (probes P1, P2)
- [ ] `contact_policy.automation_mode` is `HUMAN_APPROVAL` (probe P8)
- [ ] `python main.py audit explain --draft <id>` reconstructs any message's full provenance from stored rows with no code re-run
- [ ] Sagar has personally read every message that has been sent, before it was sent

---

## 16.12 What v2 considers, explicitly deferred

Nothing here is needed for the MVP to be complete and useful. Each is listed with its trigger — the
observation that would justify building it.

| # | Deferred | Trigger that would justify it |
|---|---|---|
| V1 | **WhatsApp Cloud API sending** | A recorded opt-in path that businesses actually use, plus a WABA with an approved template. Until then `wa.me` links Sagar clicks himself are both legal and sufficient. The schema, the channel and the five gate triggers already exist and stay empty |
| V2 | **A custom domain and real DKIM control** | The Gmail account's per-account reputation becoming the binding constraint, or a volume above 40/day being genuinely needed. Buys SPF/DKIM/DMARC control, Postmaster Tools visibility, a burnable identity, and RFC 8058 one-click — and costs the inherited `gmail.com` reputation, which has to be earned from zero |
| V3 | **A public HTTPS endpoint** | A domain (V2) plus somewhere to host. Turns unsubscribe into one-click, makes provider webhooks possible, and removes the polling latency. It also adds an attack surface this build deliberately does not have |
| V4 | **A second data source with real coverage** | The coverage bands consistently reading `LOW` in the cities that matter. Candidates in order: district chamber and MIDC member lists loaded properly, IMA/NIMA branch directories, specific `data.gov.in` datasets once one is known to cover Dhule |
| V5 | **Review signals** | A free source appearing. `review_volume` and `review_recency` are already in the weight table with `why_null='NO_FREE_SOURCE_IN_V1'`, so adding the source is a loader, not a rescoring |
| V6 | **Follow-up sequences beyond the first message** | Enough sent messages to know the reply rate. The schema supports `sequence_no`, the threading headers are built, and gates G1–G3 already bound it. What is missing is evidence that a second message helps rather than annoys |
| V7 | **`SEMI_AUTOMATED` mode** | Fifty consecutive approvals with no edit and no regret, plus a legal review. Even then the honest first step is auto-approval of *follow-ups in an existing thread*, never of a first contact |
| V8 | **Score calibration from outcomes** | Twenty closed handoffs with recorded outcomes. `score_calibration` already runs monthly and writes a proposal file it does not apply; V8 is the decision to start applying them |
| V9 | **PDF export via headless Chrome** | Somebody asking for a PDF that the browser's Save-as-PDF cannot produce. The job type is registered and disabled |
| V10 | **Postgres and a real server** | A second operator, or a dataset past roughly 50,000 businesses where SQLite's single-writer model starts to bite. `01` §1.13.6 lists the seven DDL rewrites; no application query needs touching |
| V11 | **Multi-user RBAC** | A second person. The `users` table, roles and `require_role` already exist; what is missing is invitation, per-user rate limits, and a considered answer to who may approve a send |
| V12 | **Proposal and contract tracking past the handoff** | Enough won deals for §37's Potential Revenue column to mean something. `handoffs.won_value_inr` exists; `businesses.est_value_inr` has no owner yet (see Open questions) |
| V13 | **A phone-shaped view of the handoff brief** | Sagar finding himself reading briefs on his phone while walking to a meeting. `15` §15.12 already designs it phone-first; it is a stylesheet, not a system |

---

## Open questions

1. **`config.yaml` at the root, or `config/config.yaml`?** `_CONTEXT.md` §1 says "`config.yaml`
   (committed as `config.example.yaml`), secrets in `config/.env`", which puts the YAML at the project
   root and matches `option_chain_reader`. `12-security-model.md` refers to `config/config.yaml` in
   three places. This document uses the root, with `config/` holding secrets, runtime state
   (`imap_uid.json`, `telegram_offset.json`) and auxiliary YAML. If §12's form is preferred, it is a
   `sed` over four references — but it should be decided before the first `Config` loader is written,
   because `Config.root` resolution depends on it.

2. **The `radar/templates/` versus `radar/web/templates/` split.** `06-message-engine.md` puts the
   message template bundle at `radar/templates/messages/`; `03-html-report.md` puts the Jinja page
   templates at `radar/web/templates/`. Two different `templates/` directories two levels apart will be
   confused by somebody, probably at 11pm. This document keeps both as written because both documents
   are explicit, but a rename of the message bundle to `radar/message_templates/` would remove the
   collision at the cost of one path edit in `06`.

3. **`est_value_inr` still has no owner.** `03` §3.16 flagged it, `10`'s funnel reads it, §37's
   Potential Revenue column depends on it, and no module writes it. Until it is settled the column
   renders `—` for every city — which is correct, and useless. The two candidates are `radar/score.py`
   from a per-category rule, or Sagar typing it on the business detail screen. This plan assumes the
   latter and does not build it in v1; a per-category rule is a better v2 answer once V12's outcome
   data exists to calibrate it.

4. **Whether M2 should ship the scheduler.** This plan puts the job registry, claim protocol and lanes
   in M2, and the scheduler with catch-up-on-launch in M6, on the grounds that M2–M5 have no periodic
   jobs worth scheduling. But `backup_db` is a periodic job, and §16.6 S13 argues the backup habit
   should start at M1. The cheap resolution is to ship the scheduler in M2 with exactly one registered
   schedule (`backup_db`) and add the rest at M6; that is what this plan assumes, but it is not what
   the milestone table says, and one of the two should be corrected.

5. **How the `.eml` review verdicts in §16.3.7 get recorded.** The exit criteria require a per-draft
   "would I have sent this, yes or no" for twenty drafts, but no table holds that. Options: a column on
   `outreach_drafts` written by a `main.py outreach review --draft <id> --verdict SEND|NO --note`
   subcommand; a plain CSV Sagar keeps by hand; or an `audit_log` action `DRAFT_REVIEWED`. The third is
   tidiest and needs a new `audit_actions` row. Unresolved, and it should be resolved before M5 starts,
   because a criterion with no recording mechanism is a criterion that will be ticked from memory.

6. **The evening estimates assume no unknown-unknowns in the Gemini SDK.** `google-genai` structured
   output, `thinking_budget`, and grounded search have all changed shape more than once. M2 and M5 both
   depend on getting a strict JSON schema honoured reliably. If the SDK's structured-output mode cannot
   express "no additional properties" (which `02` §2.8.3 already works around with
   `ConfigDict(extra="forbid")` in-process), the repair loop carries more weight than budgeted and M2
   grows by two to three evenings.
