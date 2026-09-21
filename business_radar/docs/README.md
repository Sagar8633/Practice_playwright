# business_radar — design pack

Seventeen documents, 48,699 lines, describing a system that has not been written yet. This file is
the way in.

---

## What this is

`business_radar` is Sagar's AI business-opportunity and software-sales platform. It researches
businesses city by city in Maharashtra — Dhule, Shirpur, Nashik, Jalgaon — from free public sources,
scores each one for "would a custom business-management system help this business?", produces a
self-contained HTML research report, and then stops. Everything after the report is gated on a human.
The rule that shapes every document in the pack is spec §45, quoted in `_CONTEXT.md` §0:

> The AI must NEVER contact a business just because it discovered and qualified it.
> RESEARCH -> REPORT -> VERIFY -> SELECT -> PERSONALIZE -> PREVIEW -> CONFIRM -> SEND.

That is not a policy statement the code is asked to remember. It is a shape: there is no HTTP route
that takes a `business_id` and transmits, `send_message()` takes an `approval_id` whose only
constructor reads a row out of `outreach_approvals`, and a SQLite trigger aborts the write if that
row is not there. A large part of this pack is the work of making that rule expensive to break by
accident and impossible to break silently.

---

## The free stack

Every design decision below is downstream of one constraint: nothing in this build costs money. Meet
the constraints before opening a document, because several documents are mostly about what a
constraint forces.

| Concern | Choice | What the constraint costs |
|---|---|---|
| LLM | Google Gemini free tier, `gemini-2.5-flash` via `google-genai` | Free-tier content may be used to improve Google's products, so **no `business_contacts` value ever reaches a prompt** — contact strings are substituted into the rendered message locally, after generation. Quota is a hard 429, not a bill: RPM 10 / RPD 250 at time of writing, budgeted 150 research + 50 drafting. Hitting the ceiling **pauses the campaign until tomorrow** rather than failing it |
| Outbound email | A dedicated free Gmail account, SMTP with an App Password | No custom domain. From-address is `something@gmail.com`; SPF/DKIM/DMARC are Google's and cannot be configured. Reputation is inherited, not earned, so account age and behaviour are the only levers. Google's cap is 500 recipients/day; the working limit is 15–25/day and it is set by policy, not by Google |
| Inbound email | IMAP polling on the same mailbox | **No webhooks are possible** — nothing on the public internet can reach this process. Every inbound path is a poll: replies, bounces and unsubscribes all arrive through `poll_inbox` |
| Unsubscribe | `mailto:` per RFC 2369 | RFC 8058 one-click needs a public HTTPS endpoint that can write to the database. There isn't one. `List-Unsubscribe: <mailto:...+unsub@gmail.com?subject=unsubscribe>` is the **only** unsubscribe mechanism in the build, so it has to be reliable |
| Discovery | OpenStreetMap — Overpass API for POIs, Nominatim for geocoding — plus the businesses' own websites and free registries (MCA21, GST public search, UDISE+) | No Google Places, no Maps Platform, no paid vendor. Nominatim's 1 request/second policy and a real User-Agent are mandatory. OSM density in Nashik is decent; in Dhule and Shirpur it is thin, and the pipeline must **surface "we found few businesses here" as a stated finding** rather than return a short list and say nothing |
| WhatsApp | A `wa.me` click-to-chat link that Sagar sends by hand | Cloud API business-initiated messaging requires a pre-approved template **and** prior opt-in. Cold outreach without opt-in is a policy violation that degrades the number's quality rating and eventually blocks it. The Cloud API path is designed but gated behind a recorded opt-in row |
| Web | Flask + waitress + Jinja2, bound to `127.0.0.1` on Sagar's Windows laptop | The laptop is a legitimate deployment, not a placeholder for a VPS. It is also **not on 24/7**, so every periodic job needs catch-up-on-launch semantics |
| Storage | SQLite `data/radar.db`, WAL, `PRAGMA foreign_keys = ON` | Enums are `CHECK` constraints and state machines are transition tables, so the database refuses illegal states even when the Python is wrong. No SQLite-only cleverness in application queries — a Postgres port must stay possible |
| Background work | One in-process thread pool over a `jobs` table, claim-by-UPDATE with a lease | No Celery, no Redis. A crash mid-job must be recoverable: leases expire, jobs are idempotent |
| Alerts | Telegram bot, plus optional mail to self | Handoff pages (§34) go to Telegram, which Sagar already runs in `option_chain_reader` |
| Identity page | GitHub Pages, static | Static only. It can say who is sending the mail; it cannot host the unsubscribe endpoint, because that has to write to the database. Hence `mailto:` |
| Threat model | Disk encryption and backup security, not network hardening | No exposed port and no public attack surface — but `data/radar.db` is a contact database that leaves the building in a backpack every day |

---

## The pipeline

Seven stages. Three of them are a person, and the system cannot advance past them on its own.

```
   RESEARCH             REPORT               VERIFY  [HUMAN]     SELECT  [HUMAN]
   ────────             ──────               ──────              ──────
   OSM / Overpass  ───> city-wise       ───> nine-item      ───> pick the
   + site fetch         HTML report          checklist,           businesses
   + Gemini             every number         one business         to contact
     synthesis          a SQL aggregate      at a time
   + scoring
       │                    │                    │                   │
   02-research-         03-html-             04-verification-    05-outreach-
   pipeline.md          report.md            workflow.md         workflow.md
                                             AI_RESEARCHED       writes a
                                             -> VERIFIED         selections row
                                             -> CONTACT_READY
                                                                     │
       ┌─────────────────────────────────────────────────────────────┘
       v
   PERSONALIZE          PREVIEW  [HUMAN]                       SEND
   ───────────          ───────                                ────
   Gemini drafts        the CONFIRM of §45 lives here:         transport puts
   from findings   ───> Sagar reads the exact bytes that   ───> bytes on a socket
   + policy engine      will be sent, edits freely, and         EMAIL: SMTP
     PASS/WARN/BLOCK    approves                                WHATSAPP: a wa.me
     before he sees it  -> outreach_approvals row               link he sends himself
       │                    │                                       │
   06-message-          05-outreach-workflow.md §5.9–§5.12      07-email-integration.md
   engine.md            15-ui-wireframe.md                      08-whatsapp-integration.md
                        17-channel-configuration.md
                        (channel unconfigured: the approval
                         stops at APPROVED and never queues)

   After SEND, the loop that is deliberately not a loop:

   09-response-classification.md  — classifies the reply into thirteen categories.
                                    It never writes one.
   10-human-handoff.md            — an interested lead stops the machine, pages
                                    Sagar, and halts every automated follow-up
                                    to that business.
   11-audit-architecture.md       — records the whole causal chain, so that in six
                                    months "why did this message say that?" has
                                    an answer.
```

Editing an AI draft does not bypass the policy engine: `06-message-engine.md` re-checks the edited
body, and a human who removes a hedge — "may help" to "will help" — turns a PASS into a BLOCK.

---

## The seventeen documents

Spec §56 asked for sixteen deliverables. The pack has seventeen files. Three things about the mapping
before reading the table:

- **Deliverables 1 and 2 share one file.** `01-data-model.md` is both the schema and the campaign
  schema; its §1.3 opens with "Deliverable 2 of §56".
- **`02-research-pipeline.md` has no §56 number.** §56 assumed the research pipeline and never listed
  it as a deliverable. The document exists because spec §11–§14 — the evidence model, sources and
  scoring — had no owner otherwise.
- **Deliverables 12 and 15 are swapped relative to the filenames.** §56 lists (12) UI wireframe and
  (15) Security model; the files went the other way. `13-api-endpoints.md` §13.18 settles it: the
  filenames win, `12-` is the security model and `15-` is the wireframe. `01`, `04` and `11` still
  cite the old numbers and owe a one-word repair.

| §56 | Deliverable | File | Lines |
|---|---|---|---|
| 1 | Database schema additions | `01-data-model.md` | 3,291 |
| 2 | Campaign schema | `01-data-model.md` §1.3 | (same file) |
| — | Discovery, research and opportunity scoring | `02-research-pipeline.md` | 4,173 |
| 3 | HTML report architecture | `03-html-report.md` | 3,770 |
| 4 | Verification workflow | `04-verification-workflow.md` | 2,964 |
| 5 | Outreach workflow | `05-outreach-workflow.md` | 3,544 |
| 6 | Message template engine | `06-message-engine.md` | 3,216 |
| 7 | Email integration architecture | `07-email-integration.md` | 3,466 |
| 8 | WhatsApp official API integration | `08-whatsapp-integration.md` | 2,704 |
| 9 | Response classification | `09-response-classification.md` | 1,959 |
| 10 | Human handoff | `10-human-handoff.md` | 2,036 |
| 11 | Audit architecture | `11-audit-architecture.md` | 3,275 |
| 15 | Security model | `12-security-model.md` | 2,251 |
| 13 | API endpoints | `13-api-endpoints.md` | 3,387 |
| 14 | Background jobs | `14-background-jobs.md` | 3,675 |
| 12 | UI wireframe | `15-ui-wireframe.md` | 1,842 |
| 16 | MVP implementation plan | `16-mvp-plan.md` | 1,737 |
| addition | **Deferred channel configuration** | `17-channel-configuration.md` | 1,409 |

**Document 17 is not part of the original sixteen.** It exists because Sagar asked to configure email
and WhatsApp later, after the rest was built and working. That turned out not to be a small request.
It required `CHANNEL_UNCONFIGURED` as a first-class, informative, per-channel state rather than an
error; a `ChannelStatus` record to carry it; a new eligibility gate `B3` inserted into
`05-outreach-workflow.md`'s A–I ordering; a shelf life for approvals created while a channel was
dark; and one hard rule — configuring a channel later must **never** retroactively transmit anything
approved before it was on. It owns no table and adds no migration.

Supporting files: `_SPEC.md` (289 lines, the 56-section requirement list), `_CONTEXT.md` (262 lines,
the shared contract), and `mockups/report_mockup.html` (a rendered sample of the §5 report).

---

## The safety invariants and what enforces them

`_CONTEXT.md` §3 lists six invariants. They are the reason the system exists, so not one of them is
enforced in a single place. Each row names the documents that carry the mechanism and the mechanism
itself. `16-mvp-plan.md` §16.7.4 lists the named test functions for every invariant, and each test
exists **before** the code path it guards can transmit.

| # | Invariant | Enforced in | Mechanism |
|---|---|---|---|
| 1 | **No send path exists that does not pass through a human approval record** — a row, not a config flag | `05` §5.3.5, §5.15.2 · `07` §7.10.1 · `13` · `15` §15.18 · `09` §9.11 | `outreach_messages.approval_id` FK; the `trg_om_send_needs_approval` trigger; an `ApprovalId` NewType whose only constructor is a query against `outreach_approvals`, so `send_message()` rejects a null approval at the type level. At the route layer: no endpoint accepts a `business_id` and transmits, the send route is registered on exactly one blueprint, and the worker cannot import the web layer. Approval itself requires a `PASSWORD` or `PASSWORD_TOTP` session and writes an `actor_kind='HUMAN'` audit row |
| 2 | **`outreach_status` may only reach `SENT` from `APPROVED`** | `05` §5.3.5 · `01` §1.2 · `14` | An `outreach_status_transitions` table plus the `trg_om_transition` trigger. `DRAFT -> SENT`, `PENDING_APPROVAL -> SENT` and `POLICY_BLOCKED -> SENT` are absent from that table, so SQLite aborts them. A test asserts the Python transition map and the table are permutations of each other — neither is allowed an entry the other lacks |
| 3 | **Opt-out is absolute and permanent**, on any contact point, across every channel, and not clearable by the app | `05` §5.3.7 · `04` §4.7 · `07` §7.7 · `08` §8.7 · `09` §9.10 | `trg_suppressions_no_delete` makes the table append-only; `trg_suppressions_release_needs_audit` refuses a release without a matching `SUPPRESSION_RELEASED` audit row, and no application code path sets `released_at`. Values are matched by HMAC (`trg_suppressions_hmac_required`) against **every** `business_contacts` row for the business — active or not — plus the business id and the registrable domain, so deactivating a contact row cannot un-say a stop. The deterministic unsubscribe path runs with the LLM unreachable and the daily quota exhausted, and `poll_inbox` completes before any `send_email` transmits on worker start |
| 4 | **Every claim in a message traces to a stored fact**, typed OBSERVED / INFERRED / UNKNOWN | `02` §2.4 · `06` §6.9 · `01` §1.6 | Generation side: an `OBSERVED` finding with no `finding_sources` row is dropped, not quietly relabelled `INFERRED`, inferences cascade to a fixpoint when their basis is dropped, and a DB trigger aborts a research run that completes with unsourced `OBSERVED` rows. Checking side: `radar/policy.py` **re-segments the message body itself** rather than trusting the model's claim map, and emits `PASS` / `WARN` / `BLOCK` per rule — `F1` unbound factual segment, `F2` a finding belonging to another business, `F4` a sourceless finding, `K1` an `INFERRED` claim with no hedge in the same sentence, `K2`/`K3` any mention of an `UNKNOWN`. The result is stored on the draft, and a human edit re-runs the engine |
| 5 | **Report numbers come from SQL aggregates over real rows**; no data renders `—`, never `0` | `03` §3.4, §3.7 | Every number in the report passes through one `render_metric()` helper; `NA` emits `<span class="na">&mdash;</span>`. A `0` asserts we looked and the answer was none; an em dash asserts we do not know, and the two must not be confused. `report_queries.py` is tested to contain no `COALESCE(..., 0)` on a nullable metric, templates are forbidden from reading denormalised counters that could drift, and the XLSX export writes an **empty cell** rather than an em dash, because in a spreadsheet a dash is a text value that poisons the column |
| 6 | **The AI classifies inbound responses; it never replies** | `09` §9.11 · `10` §10.1, §10.8 · `08` §8.8 | Seven layers. `radar/classify.py` imports neither `radar.channels` nor any transport, asserted by an AST walk. No code path passes `responses.recommended_action` or `interpretation` into `radar/messages.py` — the draft builder reads `research_findings` and `opportunities`, never a `responses` row. The classifier cannot create an `outreach_approvals` row, so invariant 1 blocks it regardless. Validator V4 strips second-person address from `interpretation` even though the prompt already forbids it. The handoff subsystem produces advice and explicitly not a draft, "not even a draft that requires approval". `trg_outreach_blocked_by_open_handoff` aborts any move to `QUEUED` or `SENT` while a handoff is open. And the WhatsApp 24-hour service window, in which a free-form reply is technically trivial, is deliberately left unused |
| — | **No `business_contacts` value may reach an LLM** (`_CONTEXT.md` §2, the free-tier consequence) | `02` §2.9 · `06` §6.13 | A scrubber on the prompt-assembly path that raises `ContactLeak` and fails the job, plus nine tests. `test_scrubber_sentinel_corpus` is the backstop: it builds **every prompt the system can assemble** from fixtures whose contact values are sentinels, and fails if any sentinel appears in any payload. It must never be skipped or marked `xfail` — if it fails, the correct response is to stop calling the model until it passes |

---

## Start here

Reading order for someone picking this up cold. Roughly one evening per step for the first four.

| # | Read | Why this one next |
|---|---|---|
| 1 | `_CONTEXT.md`, all 262 lines | It is the contract every other file obeys, and §6 is the canonical name list. Nothing else parses without it |
| 2 | `_SPEC.md` §45 and §56 | §45 is the rule the system exists to keep; §56 is the deliverable list this pack answers |
| 3 | `16-mvp-plan.md` §16.1–§16.4 | The only document that says what gets built **first**. §16.4's vertical slice is the smallest thing that proves the pipeline end to end. Read it before the design documents so you know which parts are month one and which are month five |
| 4 | `01-data-model.md` §1.1–§1.3 | The tables, the id prefixes, and the six conflict rulings. Every other document's DDL is either from here or overruled by it |
| 5 | `02-research-pipeline.md` §2.1–§2.4 | Where a business comes from and what a "finding" is. The OBSERVED / INFERRED / UNKNOWN model introduced here is exactly what invariant 4 checks later |
| 6 | `04-verification-workflow.md` §4.2 | The ten-state machine for `businesses.status`, and the gate itself. This is the shape of the whole product in one section |
| 7 | `05-outreach-workflow.md` §5.1–§5.3 | The nine-step pipeline and `check_send_eligibility()`, the single function that answers "may we contact this business, on this channel, through this contact, right now?" |
| 8 | `06-message-engine.md` §6.9 | The policy engine's rules written out. The most interesting fifty lines in the pack |
| 9 | `03-html-report.md` §3.1–§3.4, with `mockups/report_mockup.html` open beside it | The deliverable Sagar actually looks at every day |
| 10 | `17-channel-configuration.md` §17.1 | Four rules that explain why a fresh clone with an empty `config/.env` boots and runs everything except transmitting |
| 11 | Everything else, on demand | `07`, `08`, `09`, `10`, `11`, `12`, `13`, `14` and `15` are reference documents. Read a section when you are building that section, not before |

---

## Two files that outrank the others

**`_CONTEXT.md` is the canonical-names contract.** §6 fixes every table name, every enum value, every
status string, the id prefixes, the API prefix, the UI routes and the `radar/` module list. Where a
design document and `_CONTEXT.md` §6 disagree, §6 wins. Consistency across seventeen documents was
judged worth more than any local preference, and the documents say so in their own words.

**`01-data-model.md` is the schema arbiter.** Seven documents committed to DDL before it existed and
six genuine conflicts resulted. §1.2 resolves each one and states the losing document's required edit
precisely.

| Conflict | Ruling |
|---|---|
| A — `report_exports` is defined three times | `11-audit-architecture.md` §11.11.1 wins, with three amendments; `11`'s `kind` column is renamed `fmt` to clear the collision |
| B — does a business belong to one campaign or many? | One row per real-world business, globally unique on `business_key`; membership moves to a join table. The index becomes `UNIQUE`, because the key is now an identity rather than a hint, and a non-unique index would permit the exact duplicate the ruling exists to prevent |
| C — `research_findings` column names, four competing sets | `03`'s set, plus `detail`. It is a strict superset of the others, so no document loses a column |
| D — nine smaller name and value collisions | `COMPLETE` over `COMPLETED`; `verdict` over `result`; `ordinal` over "rank"; `checked_at` over `fetched_at`; `body_excerpt` over `excerpt`; `won_value_inr` over `realised_value_inr`; `QUOTA_CEILING` over `SPEND_CEILING`, because the free tier bills nothing and there is no money in the model; `reason` over `trigger`, which reads badly in a file full of `CREATE TRIGGER`; and every sample `model_id` literal becomes `gemini-2.5-flash`, because an Anthropic model id in a live row is a value nothing in this build can produce |
| E and F | `04`/`10`'s table claims and `draft_findings` were examined and found not to be conflicts; ownership is recorded in §1.1.1 |

---

## What to do first

Two kinds of setup task live in `16-mvp-plan.md` §16.6, and they are not interchangeable. **Work**
items take an evening and can be done whenever a milestone needs them. **Wall-clock** items take
calendar days no matter how hard anyone works, and if they are started in month five they add days
to month five.

### The only credential needed to start building

A **Gemini API key** from Google AI Studio, in `config/.env` as `GEMINI_API_KEY` (§16.6.1 W7). It
takes minutes to obtain and it blocks M2 entirely. Nothing else is required to write code: a fresh
clone with an otherwise empty `config/.env` boots, migrates, serves `127.0.0.1`, runs a campaign,
researches, reports, walks the verification gate, drafts, policy-checks, previews and writes a real
`outreach_approvals` row (`17-channel-configuration.md` R1). The only thing it cannot do is put bytes
on a socket.

### The seven-and-a-half-week chain — start it on day one

W1 through W6 of §16.6.1 form one chain with a floor of about **seven and a half weeks**, from
creating the account to reaching a 20/day cap. None of it is code.

| # | Item | Elapsed | Why it cannot be compressed |
|---|---|---|---|
| W1 | **Create the dedicated Gmail account.** Local part 25 characters or fewer, or the `+unsub-<32 hex>` address silently breaks the 64-octet limit | minutes, but see W4 | Account *age* is the dominant reputation input for a free Gmail sender. An account created on the day of the first send is the exact shape of a throwaway. Create it in week one of M1 and let it get old while the software gets written |
| W2 | **Enable 2-Step Verification** on that account | minutes | An App Password cannot be generated without it. Do it immediately after W1 |
| W3 | **Generate the App Password for Mail** into `OUTREACH_GMAIL_APP_PASSWORD`, and **enable IMAP** | minutes | IMAP is the only inbound path in the entire system. Without it, `poll_inbox` has nothing to poll |
| W4 | **Use the account like a person for at least a week.** Real display name and profile photo; ordinary messages sent, replied to from the other side, and read | **7 days minimum** | This is the only account-age signal that can be honestly produced, and it cannot be done in an afternoon. It gives the account a shape other than "created, then began mailing strangers" |
| W5 | **Send 8–10 messages by hand** to Sagar's own addresses across Gmail, Outlook.com, Yahoo, Zoho and one corporate Microsoft 365 tenant. Open each, reply from the receiving side, confirm inbox placement | **3 days**, after W4 | It is also a real test of five receivers' filters before a stranger is one of them |
| W6 | **The six-week ramp.** A human sets `contact_policy.warmup_started_on` at the end of W5; the schedule then runs 3 / 5 / 8 / 12 / 15 / 20 per day before reaching the 25 cap | **6 weeks after W5** | It bounds blast radius as much as reputation: week one's cap of three means the first categorically wrong message reaches three people, not thirty |
| W8 | **Publish the GitHub Pages identity page** (optional, recommended): real name, registered business name, address, phone, one paragraph on the software, one line naming the outreach address as the business correspondence address | an evening, plus propagation | It should be live and indexed *before* it is cited in a message. A URL in a cold email that 404s is worse than no URL |

Started at the beginning of M1, the chain finishes around M3 and the ramp is done by the time M6 is.
Started at the beginning of M6, it delays the first real send by two months. That is the single
strongest argument in the pack for doing something on day one that has nothing to do with code.

### Then, in milestone order

§16.6.2 lists fifteen work items against the milestone that needs each one. The M1 set: Python 3.11+
and a venv; `config.yaml` and `config/.env` from their examples; `python main.py bootstrap-owner`
followed by TOTP enrolment; **BitLocker on the volume holding `data/`**, which `python main.py doctor`
refuses to pass without; owner-only ACLs on `config/.env`, `data/radar.db*`, `data/backups/` and
`logs/`; a `data/` directory that is **not** inside OneDrive, Dropbox or any synced folder, which
`radar/config.py` refuses to boot from; and an external drive plus an `age` keypair stored off the
laptop, because a backup habit started at M6 has nothing to back up from M1 to M5.

Before the first real message reaches a stranger, §16.6.3 is a thirteen-line checklist, most of it
automated by `python main.py doctor --security`. The last line is the one that cannot be automated:
Sagar can state, without looking it up, what `python main.py email halt` does and where the
`HALT_SENDING` file lives.

---

## Pack size, 27 August 2026

| | |
|---|---|
| Numbered design documents | 17 |
| Lines across those 17 | 48,699 |
| Including `_CONTEXT.md` and `_SPEC.md` | 49,250 |
| Largest | `02-research-pipeline.md`, 4,173 lines |
| Smallest | `17-channel-configuration.md`, 1,409 lines |
| Lines of code written so far | 0 |
