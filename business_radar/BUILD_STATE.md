# Build state — 2026-08-28

The engine runs. This file is the resume point; read it before touching anything.

## RUN IT WITH THE PROJECT VENV

```powershell
cd d:\Practice_Playwright\business_radar
.\.venv311\Scripts\python.exe main.py doctor
```

**Never use bare `python`.** That resolves to `d:\Practice_Playwright\venv`, which is **3.9.9**,
and the code needs 3.11 (`enum.StrEnum`, `@dataclass(slots=True)`). Under 3.9 sixteen modules fail
to import and it looks catastrophically broken. It is not. Use `.venv311`, which was created from
`C:\Users\samja\AppData\Local\Programs\Python\Python311\python.exe` and has every dependency
installed.

## WHAT WORKS RIGHT NOW — verified by running it

| Command | State |
|---|---|
| `main.py doctor` | Reports readiness honestly |
| `main.py setup` | Copies config from the examples |
| `main.py migrate` | 7 migrations, **35 tables, 30 triggers** |
| `main.py places "<anywhere>"` | **Worldwide.** Verified: Pune, Leeds, Austin |
| `main.py campaign new --locations "..."` | Creates a campaign for any place on earth |
| `main.py campaign list` / `show` | Works |
| `main.py check-channels` | Reports email unconfigured, correctly, as supported |
| `pytest tests/` | **188 of 191 pass** |
| `pytest tests/test_safety.py` | **9 of 9 pass** |

Not yet exercised end to end: `discover`, `research`, `report`, `draft`, `web`. They import
cleanly and have unit tests, but no live Overpass/Gemini run has been done.

## THE SAFETY MODEL IS REAL, NOT ASPIRATIONAL

`tests/test_safety.py` proves at the database level, all 9 green:

- A message cannot reach `SENT` with a null `approval_id`.
- `SENT` is reachable only from `APPROVED`/`QUEUED` — never from `DRAFT`.
- A row cannot be *born* `SENT`.
- A suppression cannot be deleted.
- `audit_log` refuses `UPDATE` and `DELETE`.
- `automation_mode` cannot be raised above `HUMAN_APPROVAL`.
- `AI_RESEARCHED -> CONTACTED` aborts at the trigger.
- An unconfigured email channel loads cleanly as a supported state.

Two constraints found while writing those tests, both stricter than expected and both correct:

1. **No outreach draft may exist for an unverified business** (`trg_no_draft_before_contact_ready`,
   citing spec §19/§45). The test fixture had to walk the real status ladder.
2. **A `VERIFIED` verdict requires all nine checks passed, a `why_note` of at least 15 characters,
   and `dwell_ms >= dwell_required_ms`** — doc 04's anti-rubber-stamp design as a CHECK constraint.
   Verification cannot be rubber-stamped even from raw SQL.

## GLOBAL LOCATION SEARCH — added 2026-08-28

`radar/locations.py` (new). Free-text place search anywhere on earth via Nominatim, replacing the
four hardcoded cities.

- `search(query)` returns ranked candidates and never silently picks one — "Springfield" is a real
  question, not a typo.
- `resolve_one()` refuses to guess when the top two matches are within 0.05 importance.
- `bound_for(place)` produces the same `CityBound` the existing discovery path already consumes:
  an OSM relation becomes an exact area, anything else a sized radius, and `source` records which.
- `LocationTooBroad` refuses a country or continent rather than issuing an Overpass query that
  times out after 90 seconds.
- Results cached in `locations` / `location_searches`.

`config.yaml`'s city list still exists and still works; it is now a convenience, not a limit.

## THREE KNOWN FAILURES — all in tests/test_research.py

1 & 2. `PiiLeak: refusing to send a payload containing PERSON to a free-tier LLM`. **The guard is
working and failing safe.** The scrubber blocks named individuals as well as contact values, which
is stricter than the spec demanded and correct under DPDP. The *tests* encode the looser
expectation. Decide which is right; if the guard stays as-is, the fixtures need person-free text.

3. `research_and_score() got an unexpected keyword argument 'fetcher'` — a signature mismatch
between two agents that built in parallel. A one-line fix once you decide the signature.

## STILL MISSING

- `README.md` for the code (the design pack's `docs/README.md` is separate and exists).
- No live Overpass or Gemini call has been made yet.
- `main.py` had three schema bugs that the safety tests caught and that are now fixed (missing
  `slug`, `created_by` needing a real user id, `categories` needing JSON). Assume other CLI paths
  have similar untested edges.

## CREDENTIALS

`config/.env` holds `GEMINI_API_KEY`. Email is deliberately unconfigured — a supported state.
Everything up to and including drafting and approval works without it; drafts land in
`data/outbox/` as `.eml` files.

**`config.yaml` needs your contact address.** `discovery.user_agent` currently reads
`contact: set-your-email-here`. Nominatim returns **403** for placeholder user agents — it did,
until it was changed. OSM policy expects a real contact so a volunteer admin can reach you instead
of blocking you.

## DESIGN REFERENCE

`docs/` — 17 documents, 52,179 lines, plus `mockups/report_mockup.html`.
`docs/_CONTEXT.md` is the contract; `docs/01-data-model.md` is the schema arbiter.

---

## Session 2026-08-28, second half — live run

**Discovery works against real OpenStreetMap data.** A live run wrote **111 businesses** (97
hospitals, 6 schools, 4 colleges in Dhule). Overpass rate limiting, endpoint failover
(overpass-api.de -> kumi.systems) and HTTP 500 retries all behaved correctly and politely.

**`discovery.user_agent` now carries a real contact** (smartbusinesssystems.sj@gmail.com). Nominatim
returns 403 without one.

**Fixed: `discover_campaign` ignored the campaign's own locations.** It read `cfg.cities` and
searched Dhule for a campaign created for Pune. Added `_campaign_targets()` and
`_campaign_categories()` in `radar/discover.py`: `campaign_cities` (joined to the `locations`
cache) now wins over `config.yaml`, falling back only when a campaign named no locations. A stored
OSM relation id goes straight into `City.osm_relation_id`, so a place resolved at campaign-creation
time costs no second geocoder call. Verified: the Pune campaign now targets Pune with its own two
categories. `pytest tests/test_safety.py tests/test_discovery.py` — 61 passed.

### Email account — created, not yet usable

The dedicated Gmail `smartbusinesssystems.sj@gmail.com` exists, so the account-age clock has
started. It is **not** configured in `config/.env` and cannot be yet: what was supplied was the
account password, and Google requires a 16-character **App Password** for SMTP. Next steps on that
account, in order: change the password (it was exposed), enable 2-Step Verification, generate an
App Password for Mail, enable IMAP, then put the App Password in `config/.env` as
`OUTREACH_GMAIL_APP_PASSWORD` and the address as `OUTREACH_GMAIL_ADDRESS`.

### Next session starts here

```powershell
cd d:\Practice_Playwright\business_radar
.\.venv311\Scripts\python.exe main.py discover cmp_01M13AG0RAKMV8A0NX4FAAC149   # now targets Pune
.\.venv311\Scripts\python.exe main.py research cmp_01M13AG0RAKMV8A0NX4FAAC149 --limit 5
.\.venv311\Scripts\python.exe main.py report   cmp_01M13AG0RAKMV8A0NX4FAAC149
```
`research` is the first live Gemini call and has never been run. Expect to fix something.
Overpass is slow and rate-limited: a full city takes several minutes with waits between queries.

---

## Credentials configured and verified — 2026-08-28

`main.py doctor` now reports **all green**: Python 3.11.6, config, database (schema v75),
Gemini key, email, WhatsApp.

Live connection tests, run against the real servers:

| Test | Result |
|---|---|
| SMTP smtp.gmail.com:587 STARTTLS + AUTH | **ok** |
| IMAP imap.gmail.com:993 LOGIN + SELECT INBOX | **ok** (537 messages) |
| Plus-address delivery to `+unsub-probe@` | **ok**, ~6 seconds |

The plus-address probe is the important one: doc 07's entire unsubscribe mechanism is a `mailto:`
to `account+unsub-<token>@gmail.com`. Had Gmail not delivered plus-addressed mail to this inbox,
every opt-out would have silently vanished. It works.

### Two open concerns about this mailbox

1. **537 messages in the inbox.** Doc 07 assumes a *dedicated* account for two reasons: it can be
   abandoned if a spam complaint lands, and the inbox poller reads the whole mailbox. Both weaken
   if this account is also used for other correspondence. Worth deciding before `poll_inbox` runs
   for the first time - it will read everything in there.
2. **The App Password was shared in a chat transcript.** Revoking and regenerating it in Google
   Account settings is a two-minute job and costs nothing; `config/.env` is the only place it needs
   to change afterwards.

### Sending is technically possible now — deliberately do not rush it

Doc 07's account ramp (3 / 5 / 8 / 12 / 15 / 20 per day over six weeks) is justified on account
*age*, and this account is days old. `contact_policy.warmup_started_on` is set by a human and has
not been set. Milestone 5 of `docs/16-mvp-plan.md` - research, verify, draft, approve, with drafts
landing in `data/outbox/` as `.eml` files - is the intended way to use this for the first few weeks.
The safety triggers make an accidental send impossible without an approval row, but nothing stops a
*deliberate* premature one.

---

## 2026-08-28, third session — the pipeline runs end to end

**discover -> research -> report all work against live services.**

### Fixed this session

1. **`main.py research` called a function that does not exist.** `radar/research.py` exposes
   `research_and_score(conn, business_id, *, client, cfg, ...)` - per business, resumable - not a
   campaign wrapper. The campaign loop now lives in `main.py::_stage("research")`, which selects
   `AI_RESEARCHED` businesses for the campaign and calls it one at a time. A crash mid-campaign
   leaves finished businesses finished; re-running picks up the rest.

2. **`gemini-2.5-flash` is no longer available to new API keys.** Google's 404 says so explicitly.
   Now `gemini-3.5-flash` in `config.yaml`, verified working. (`gemini-3.7-flash` exists but timed
   out repeatedly on a trivial prompt; `gemini-flash-latest` returns 503 under load.)

3. **`llm.timeout_seconds` raised 120 -> 240.**

4. **The PII guard aborted every research run.** `build_user_prompt` lays in fields taken straight
   off the business row - the OSM-sourced address and phone - which never passed through
   `extract_and_redact` because they never came from a fetched page. `radar/research.py` now
   redacts the *assembled* prompt and then asserts on it, so the assertion checks that redaction
   worked rather than that every upstream caller remembered to redact. The guard still runs on the
   exact bytes that leave the process.

5. **Gemini rejects several JSON Schema keywords.** `minItems`, `maxItems`, `minLength`,
   `maxLength` and friends produce a bare `400 INVALID_ARGUMENT` naming none of them. Added
   `gemini_schema()` in `radar/llm.py`, applied at the one place `response_schema` is set. Nothing
   is lost: every stripped bound is re-checked by the caller's validator against the parsed
   response, which is where it has to be caught anyway - a model will ignore a bound it was told.

### Proven live

```
discover   111 businesses from OpenStreetMap (97 hospital, 6 school, 4 college)
research   Sanskar Homeopathic Clinic -> 9 findings (3 OBSERVED, 1 INFERRED, 5 UNKNOWN)
           from 1 source; scored 36 LOW, confidence LOW (34%)
report     business_research_pune_2026-08-28.html - 111 rows, 902 KB, 733 ms, self-contained
```

### Still open

- **`assess_opportunity` returns prose, not JSON.** "ASSESS returned 546 characters that are not
  JSON". The exchange is captured under `data/capture/llm/2026-08-28/`. The numeric score is
  already stored, so this is the narrative half only, and `research_and_score` deliberately
  survives it. Read the capture file first.
- **503 UNAVAILABLE from Gemini under load** - transient, not a bug, but there is no retry on it
  yet. Worth adding to the same backoff that handles 429.
- **Stale `research_runs` block retries**: `UNIQUE constraint failed: research_runs.business_id`
  after a failed run. Cleared manually with
  `DELETE FROM research_runs WHERE status NOT IN ('COMPLETE')`. Needs a real fix - a failed run
  should be marked FAILED and not hold the unique slot.
- `draft` and `web` still never run.
- Three `tests/test_research.py` failures, unchanged.
- No code `README.md`.

### Next

```powershell
.\.venv311\Scripts\python.exe main.py research cmp_01M13AG0RAKMV8A0NX4FAAC149 --limit 10
.\.venv311\Scripts\python.exe main.py report   cmp_01M13AG0RAKMV8A0NX4FAAC149
.\.venv311\Scripts\python.exe main.py web
```
