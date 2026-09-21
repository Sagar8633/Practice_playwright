# SHARED DESIGN CONTEXT — read this before writing your section

Every design document in `business_radar/docs/` must obey the decisions below. They are already
settled. Do not re-litigate them, do not propose alternatives in your section body (if you have a
genuine objection, put it in a short `## Open question` block at the end of your file).

---

## 0. What this project is

`business_radar` — Sagar's **AI Business Opportunity & Software Sales Platform**. It researches
businesses city-by-city in Maharashtra (Dhule, Shirpur, Nashik, Jalgaon...), scores each one for
"would a custom business-management system help them?", produces a self-contained HTML research
report, and then walks Sagar through a **mandatory human verification gate** before any message is
sent to anybody.

The single hardest rule in the system, from spec §45:

> The AI must NEVER contact a business just because it discovered and qualified it.
> RESEARCH -> REPORT -> VERIFY -> SELECT -> PERSONALIZE -> PREVIEW -> CONFIRM -> SEND.

Read `docs/_SPEC.md` for the full 56-section requirement list. Your section prompt names the spec
sections you own. Cover **every** requirement in the sections you own — do not summarize them away.

There is no existing codebase. This is greenfield. Ignore any instinct to "extend existing code";
there is none. Design it fresh, but in the house style below.

---

## 1. House style (from Sagar's other projects in this repo)

Sagar's two closest projects are `naukri_job_screener/` and `option_chain_reader/`. Match them:

| Aspect | Convention |
|---|---|
| Language | Python 3.11+, `from __future__ import annotations`, full type hints |
| Layout | `main.py` argparse CLI at project root + one package dir (`radar/`) with focused modules |
| Config | `config.yaml` (committed as `config.example.yaml`), secrets in `config/.env`, never in YAML |
| Config object | A `Config` dataclass in `radar/config.py`, `setup_logging()` beside it |
| Models | `@dataclass` records in `radar/models.py`, `from_row()` / `to_row()` classmethods |
| Logging | `log = logging.getLogger("radar.<module>")` at module top |
| Web | Flask app, served by **waitress** in production (not the dev server) |
| Reports | Self-contained HTML written to disk, plus CSV/XLSX via openpyxl |
| Tests | pytest in `tests/`, no network, fixtures over mocks where possible |
| Docstrings | Module-level docstring that explains **why the module exists and what breaks without it**, not what it does. Sagar's existing docstrings are prose that names the real-world failure the module prevents. Match that voice. |
| Durability | Atomic writes: write `.tmp`, then `.replace(path)`. Corrupt-file recovery moves the bad file aside **loudly** and logs an error rather than silently resetting |

Look at `naukri_job_screener/screener/ledger.py` for the tone: it opens by explaining that without
the ledger the agent re-applies to the same jobs every morning and reads as a bot. Every module
docstring you specify should have that quality.

---

## 2. Settled technical decisions

**Storage: SQLite** (`data/radar.db`), accessed through `sqlite3` with `row_factory = sqlite3.Row`.
Not Postgres — this is a single-operator tool on one machine/VPS. But:

- Write real DDL with `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`.
- Use `TEXT` ISO-8601 timestamps (`YYYY-MM-DDTHH:MM:SS`), UTC, `strftime('%Y-%m-%dT%H:%M:%SZ','now')`.
- Use `CHECK (col IN (...))` constraints for every enum. The state machine must be enforced by the
  database, not only by Python.
- Migrations: numbered SQL files `radar/migrations/001_*.sql`, applied by a `schema_version` table.
  Idempotent, forward-only.
- Everything must survive a Postgres port later: no SQLite-only cleverness in application queries.

**Identity:** every table gets a `TEXT` primary key ULID-style id with a type prefix — `cmp_`,
`biz_`, `res_`, `src_`, `ver_`, `msg_`, `out_`, `rsp_`, `aud_`. Human-readable in logs and audit
records. (Use `ulid-py` or a 26-char Crockford base32 helper in `radar/ids.py`.)

**LLM: Google Gemini free tier**, via the `google-genai` Python SDK against Google AI Studio.
Model: `gemini-2.5-flash` for research synthesis, message drafting and response classification.
There is no paid tier in this build and no `anthropic` dependency anywhere.

Always pin the model id **in the database row** that stores the output, alongside a `prompt_version`
string, so an audit can reproduce why a message came out the way it did (spec §49). Never call an
LLM without recording model + prompt version + token counts.

Two consequences you must design around, not around which there is any negotiating:

1. **Free-tier content may be used by Google to improve their products.** Therefore: **no value from
   `business_contacts` is ever sent to the LLM.** Not an email, not a phone number, not a named
   individual. The research synthesis call receives business name, city, category and scraped public
   page text; it does not receive and does not need the contact row. The message-drafting call
   receives the findings and the business name, and the contact address is substituted into the
   rendered message **after** generation, locally. Enforce this with a scrubber on the prompt-
   assembly path plus a test that fails if a contact value can reach an LLM payload.
2. **Free-tier quota is a hard rate limit, not a bill.** There is no spend to cap — there is a
   requests-per-minute and requests-per-day ceiling that returns 429. Everything in the design that
   was a rupee budget becomes a quota budget: `spend_ledger` records request counts and token counts
   against the daily quota, `rate_buckets` throttles to stay under RPM, and hitting the ceiling
   **pauses research and resumes tomorrow** rather than failing the campaign.

**Web stack:** Flask + waitress + Jinja2 templates for the live app; the **exported** HTML report is
generated by the same Jinja2 templates but inlined into one self-contained file (CSS inlined, JS
inlined, no CDN) so Sagar can email it or open it offline.

**Background work:** no Celery/Redis. A single in-process worker thread pool driven by a `jobs`
table in SQLite (claim-by-UPDATE with a lease), because the deploy target is one small VPS. Design
it so a crash mid-job is recoverable (leases expire, jobs are idempotent).

**Notifications:** Telegram bot (Sagar already uses this in `option_chain_reader`), plus optional
email-to-self. Human handoff alerts (§34) go to Telegram.

**Deploy target: Sagar's own Windows laptop. There is no VPS and no public hostname.**
Flask + waitress bound to `127.0.0.1`, opened in a local browser. This is a single-operator tool and
localhost is a legitimate deployment, not a placeholder for one.

Four consequences that change designs already written:

- **No inbound webhooks are possible.** Nothing on the public internet can reach this process. Every
  inbound path is therefore a **poll**: replies and bounces are read by polling the Gmail mailbox
  over IMAP. Any design that depends on a provider POSTing to us is void.
- **No public HTTPS endpoint**, so RFC 8058 one-click unsubscribe (`List-Unsubscribe-Post`) cannot
  be offered. Use **`mailto:` unsubscribe** — `List-Unsubscribe: <mailto:...+unsub@gmail.com?subject=unsubscribe>`
  — which RFC 2369 fully permits. The inbox poller turns such a mail into a `suppressions` row. This
  is the only unsubscribe mechanism in the build and it must be reliable.
- **The machine is not on 24/7.** The scheduler cannot assume it was running at 07:35. Every periodic
  job needs catch-up-on-launch semantics: on start, work out what was missed and decide per job type
  whether to run it late or skip to the next occurrence.
- **The threat model changes.** No exposed port, no public attack surface — but the laptop is
  portable and `data/radar.db` is a contact database that leaves the building every day. Disk
  encryption and backup security matter more than network hardening.

**Hosting the identity page:** a free GitHub Pages site is acceptable for a static "who is this"
page referenced from outreach mail. It is static only — it cannot host the unsubscribe endpoint,
because that has to write to the database. Hence `mailto:`.

---

## 3. Non-negotiable safety invariants

These are the reason the system exists. Every section must respect them, and several sections must
enforce them:

1. **No send path exists that does not pass through a human approval record.** Not a config flag —
   a row. The send function must take an `approval_id` and reject a null one at the type level.
2. `outreach_status` may only reach `SENT` from `APPROVED`. Enforce with a DB CHECK + a transition
   table, not just app logic.
3. **Opt-out is absolute and permanent.** An opt-out on any contact point (email, phone, WhatsApp
   id, domain) blocks every channel for that business, forever, and cannot be cleared by the app —
   only by a manual DB operation with an audit row.
4. **Every claim in a generated message must be traceable to a stored fact.** Facts are typed
   OBSERVED / INFERRED / UNKNOWN (§12). A message may state OBSERVED facts, may *hedge* about
   INFERRED ones ("may", "could", "we believe"), and must never mention UNKNOWN ones. This is
   checked by a policy engine before the message is shown to Sagar, and the check result is stored.
5. **Report numbers come from SQL aggregates over real rows** (§8: "Never fabricate them"). No
   placeholder numbers anywhere in the generation path. If a metric has no data, render `—`, not 0.
6. The AI **classifies** inbound responses; it never replies to them. Interested leads stop the
   machine and page Sagar (§34, §55).

---

## 4. Legal / platform constraints you must design around (India, 2026)

Do not soften these; do not skip them because they are inconvenient.

- **WhatsApp Business Platform (Cloud API):** business-initiated conversations require a
  **pre-approved template** and, per Meta's Business Messaging Policy, prior **opt-in** from the
  recipient. Cold outreach to a business that never opted in is a policy violation and gets the WABA
  number quality-rated down and eventually blocked. Design the WhatsApp channel accordingly — the
  honest MVP answer is a **`wa.me` click-to-chat deep link that Sagar sends by hand**, with the
  Cloud API path built but gated behind a recorded opt-in. Say this plainly.
- **Email: a dedicated free Gmail account, sent over SMTP with an App Password.** Not Sagar's
  personal address — a separate free account created for this purpose, so the blast radius of a
  spam complaint is an account he can abandon rather than the address his clients already use.
  There is **no custom domain**: the from-address is `something@gmail.com`, SPF/DKIM/DMARC are
  Google's and cannot be configured, and gmail.com's own excellent sending reputation is inherited
  rather than earned. Free Gmail caps at 500 recipients/day; the real working limit here is far
  lower and set by policy, not by Google.

  The AUP argument that permits this is the same one already written into `07-email-integration.md`,
  and it has the same expiry conditions: **one recipient per message, a per-business rendered body,
  per-message human approval, 15–25 sends a day, a working unsubscribe, and automatic permanent
  suppression on any complaint.** Under those conditions this is a person writing business letters,
  which is what Gmail permits. Bulk it, template it identically, or automate the approval, and it
  becomes exactly the thing that gets accounts closed. Say this plainly wherever it is relevant.

  App Passwords require 2-Step Verification on the account. IMAP must be enabled for reply capture.

- **Discovery must be free.** No Google Places, no Maps Platform, no paid data vendor. The v1 source
  set is OpenStreetMap (Overpass API for POI extraction, Nominatim for geocoding — respect its
  1 request/second usage policy and set a real User-Agent), the businesses' own websites, and free
  public registries (MCA21 company master data, GST public search). Be honest in the design about
  what this costs in coverage: OSM density in Nashik is decent, in Dhule and Shirpur it is thin, and
  the pipeline must surface "we found few businesses here" as a finding rather than silently
  returning a short list.
- **India DPDP Act 2023:** publicly-listed business contact details are lower risk than personal
  data, but the moment a named individual's email/phone is stored it is personal data. Design for
  purpose limitation, retention limits, an erasure path, and a record of where each contact came from.
- **TRAI / DND** applies to phone and SMS channels — another reason phone is "manual only" in v1.
- Every outbound email carries a working unsubscribe mechanism, and the unsubscribe must write an
  opt-out row automatically.

---

## 5. Writing rules for your document

- Write **Markdown**, to the exact path your prompt gives you. Nothing else — no code files.
- Be concrete and implementable. Real DDL, real function signatures, real endpoint paths, real JSON
  payloads. A competent Python dev should be able to build from your file without asking questions.
- Prefer tables and fenced code blocks over prose paragraphs.
- Cross-reference other docs by filename (e.g. "see `01-data-model.md` for `businesses`").
- **Use only the table names, column names, enum values, state names and endpoint paths defined in
  §6 below.** Consistency across the 13 documents matters more than your local preference.
- No emoji. No marketing language. Sagar is the only reader and he is technical.
- Do not invent statistics or example numbers presented as real. Sample data must be labelled
  `SAMPLE` wherever it appears.
- Start your file with a `# <Number>. <Title>` H1 and a one-paragraph "what this document decides".
- End with a `## Open questions` section listing anything you could not settle (or "None").

---

## 6. THE CANONICAL NAMES — use these exactly

**Tables:** `campaigns`, `campaign_cities`, `businesses`, `business_contacts`, `research_runs`,
`research_findings`, `sources`, `finding_sources`, `opportunities`, `opportunity_modules`,
`verifications`, `verification_checks`, `selections`, `outreach_drafts`, `outreach_approvals`,
`outreach_messages`, `outreach_events`, `responses`, `handoffs`, `suppressions`, `contact_policy`,
`users`, `audit_log`, `jobs`, `job_runs`, `report_exports`, `schema_version`.

**Business lifecycle status** (`businesses.status`), spec §17 — exactly these values:
`AI_RESEARCHED`, `NEEDS_VERIFICATION`, `VERIFIED`, `REJECTED`, `SKIPPED`, `CONTACT_READY`,
`CONTACTED`, `RESPONDED`, `INTERESTED`, `HUMAN_HANDOFF`

**Outreach message status** (`outreach_messages.status`):
`DRAFT`, `POLICY_BLOCKED`, `PENDING_APPROVAL`, `APPROVED`, `QUEUED`, `SENT`, `DELIVERED`,
`BOUNCED`, `FAILED`, `CANCELLED`

**Response classification** (`responses.classification`), spec §33 — exactly these:
`INTERESTED`, `VERY_INTERESTED`, `DEMO_REQUESTED`, `MEETING_REQUESTED`, `PRICE_REQUESTED`,
`MORE_INFORMATION`, `LATER`, `NOT_INTERESTED`, `ALREADY_HAVE_SOFTWARE`, `WRONG_CONTACT`, `OPT_OUT`,
`COMPLAINT`, `UNKNOWN`

**Finding kind** (`research_findings.kind`), spec §12: `OBSERVED`, `INFERRED`, `UNKNOWN`

**Confidence** (everywhere): `HIGH`, `MEDIUM`, `LOW` — plus a numeric `confidence_pct` 0–100 where a
score is needed. Never invent a fourth level.

**Channel** (`outreach_messages.channel`): `EMAIL`, `WHATSAPP`, `PHONE`, `MANUAL`

**Business size** (`businesses.size_band`): `MICRO`, `SMALL`, `MEDIUM`, `LARGE`, `UNKNOWN`

**Industry** (`businesses.industry`) — the report's city sections (§3): `HEALTHCARE`, `EDUCATION`,
`AUTOMOBILE`, `MANUFACTURING`, `RETAIL`, `HOSPITALITY`, `DISTRIBUTION`, `REAL_ESTATE`,
`PROFESSIONAL_SERVICES`, `OTHER`. The finer `category` column holds the specific type (`HOSPITAL`,
`DIAGNOSTIC_CENTER`, `SCHOOL`, `COLLEGE`, `MANUFACTURER`, `DISTRIBUTOR`, `VEHICLE_DEALER`, `GARAGE`,
`HOTEL`, `RESTAURANT`, `BAKERY`, `RETAIL_STORE`, `REAL_ESTATE_AGENCY`, `OTHER`).

**Automation mode** (`contact_policy.automation_mode`), §46: `MANUAL`, `HUMAN_APPROVAL`,
`SEMI_AUTOMATED`, `FULLY_AUTOMATED`. Default and only supported value in v1: `HUMAN_APPROVAL`.

**Score bands:** opportunity 0–100; `HIGH` >= 80, `MEDIUM` 60–79, `LOW` < 60.

**API prefix:** `/api/v1/...`. **UI routes:** `/campaigns`, `/campaigns/<id>`, `/business/<id>`,
`/verify/<id>`, `/outreach`, `/outreach/<draft_id>`, `/handoffs`, `/settings`.

**Python package:** `radar/`. Modules referenced across docs: `radar/config.py`, `radar/models.py`,
`radar/db.py`, `radar/ids.py`, `radar/discover.py`, `radar/research.py`, `radar/score.py`,
`radar/verify.py`, `radar/policy.py`, `radar/messages.py`, `radar/channels/email.py`,
`radar/channels/whatsapp.py`, `radar/classify.py`, `radar/handoff.py`, `radar/audit.py`,
`radar/report.py`, `radar/jobs.py`, `radar/web/app.py`.
