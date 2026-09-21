# 15. UI wireframe

This document decides what every screen in `business_radar` looks like, where every region on it
gets its data, and what makes every control live or dead. It is deliverable 12 of spec §56 and
owns §50 and §51 plus the screen half of §1, §11-§16, §18-§20, §27, §28, §32, §34, §36, §37, §38
and §43. Two things make it more than a layout exercise. First, the safety model of this system is
expressed almost entirely in the user interface: §19's "the Send button must NOT exist on the raw
AI research result" is a statement about markup, and it is enforced here by absence rather than by
a disabled attribute. Second, the free-stack decision in `_CONTEXT.md` §2 introduced a screen no
earlier document specifies — a **quota status** view, because on a free Gemini tier the thing that
stops research is not a bill, it is a 429, and an operator who cannot see the ceiling approaching
will read a pause as a crash.

**Cross-references.** `03-html-report.md` §3.9 defines the colour tokens, the badge inventory and the
`BLOCK_REASON` map; this document extends that same system to the live app and **invents no second
palette**. `04-verification-workflow.md` §4.5.2 defines the verification screen's zones and
element ids (`E01`-`E37`) and §4.7 its anti-rubber-stamp measures; this document renders them.
`05-outreach-workflow.md` §5.5, §5.11 and §5.13 define the workspace panels, the nine preview
panels and the CONFIRM & SEND preconditions; `06-message-engine.md` §6.11 owns four of those
panels. `10-human-handoff.md` §10.5.4 carries the desktop handoff view; §15.12 designs the phone
rendering of the same data. `01-data-model.md` is the schema arbiter for every column named below
and `13-api-endpoints.md` is the route registry. `02-research-pipeline.md`,
`07-email-integration.md` and `12-security-model.md` are referenced but nothing here depends on
their layout decisions.

A static mock of the campaign report view lives at `mockups/report_mockup.html`, rendering §15.4
and §15.17 with SAMPLE data. It is not a second source of truth: where it and this document
disagree, this document wins and the mock is regenerated.

---

## 15.1 The rules every screen obeys

### 15.1.1 Route map

`_CONTEXT.md` §6 fixes eight UI routes. Five more are needed by spec sections this document owns
and are proposed here as additions (Open question 1).

| Route | Screen | Section | Status |
|---|---|---|---|
| `/campaigns` | Campaign list | §15.3.1 | canonical |
| `/campaigns/new` | New campaign form (§1) | §15.2 | **extension** |
| `/campaigns/<id>` | Campaign dashboard + report view (§36, §3-§10) | §15.3, §15.4 | canonical |
| `/business/<id>` | Business detail / research panel (§11-§14, §32) | §15.5, §15.11 | canonical |
| `/verify/<id>` | Verification screen (§15, §16) | §15.6 | canonical |
| `/outreach` | Outreach workspace (§20) | §15.8 | canonical |
| `/outreach/<draft_id>` | Message preview (§27) + confirm dialog (§28) | §15.9, §15.10 | canonical |
| `/handoffs` | Handoff inbox (§34) | §15.12.1 | canonical |
| `/handoffs/<id>` | Handoff detail (§34) | §15.12.2 | **extension** |
| `/settings` | Settings, tabbed (§21, §22, §31, §46) | §15.15 | canonical |
| `/suppressions` | Do-not-contact list (§30) | §15.13 | **extension** |
| `/reports/daily/<YYYY-MM-DD>` | Daily report (§43) | §15.14.3 | **extension**, also proposed by `03` |
| `/compare` | City (§37) and industry (§38) comparison, cross-campaign | §15.14 | **extension** |

There is no `/jobs` route — `13-api-endpoints.md` §13.16 puts the job console in a `/settings` tab
— and there is deliberately no `/send`, `/blast`, `/queue` or `/campaigns/<id>/send-all`.

### 15.1.2 Wireframe notation

Every wireframe is followed by two tables. **Regions** names each labelled area and the
`table.column` or query behind it: a region with no row behind it is not drawn from an f-string,
it is drawn from a SELECT. **Controls** names each control, the predicate that enables it, and the
sentence shown when it is off.

```
[ Button ]        enabled control          ( ) / (o)   radio, unset / set
[ Button ]*       primary control          [ ] / [x]   checkbox, unset / set
[ Button ]-       disabled; always next    < Select v > dropdown
                  to its one-sentence      {{ }}       a value from the database
                  reason                   !           an alert or blocking banner
E12               a 04-verification-workflow.md §4.5.2 element id
```

### 15.1.3 The four rules that hold on every screen

1. **The SEND control is ABSENT, not disabled, anywhere outside the confirm dialog (§19, §45).** Not
   `hidden`, not `disabled`, not permission-gated — no element exists. §15.18.1 has the enforcement.
2. **Irreversible actions require typed confirmation.** §15.18.2 lists the five and their exact
   strings.
3. **Every blocked control explains itself in one sentence, next to the control**, from the shared
   `BLOCK_REASON` map in `03-html-report.md` §3.7.1 — imported, never re-typed. §15.18.3.
4. **No data is not zero.** A metric with no rows behind it renders `—` (`03` §3.5), in the live app
   exactly as in the export, through the same Jinja `|dash` filter.

---

## 15.2 New campaign form (§1) — `/campaigns/new`

§1 asks for five inputs: cities, categories, minimum size, minimum opportunity score, research
depth. One column, because the form is filled in once and the fields are not independent enough to
earn a second.

```
+------------------------------------------------------------------------------+
| business_radar     Campaigns*  Outreach  Handoffs 4  Settings   [Auto|L|D]   |
+------------------------------------------------------------------------------+
| < Campaigns                                          NEW SEARCH CAMPAIGN     |
+------------------------------------------------------------------------------+
|  NAME                                                                        |
|  [ Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026                              ] |
|  Leave blank and the cities plus today's date will name it.                  |
|  TARGET CITIES                                                    required   |
|  [ Dhule x ] [ Shirpur x ] [ Nashik x ] [ Jalgaon x ]                        |
|  [ type a city and press Enter                                             ] |
|  4 of 12. Order is kept: report city tabs follow the order you type.         |
|  CATEGORIES     (o) All categories    ( ) Choose                             |
|      [ ] Hospital        [ ] Diagnostic centre  [ ] School    [ ] College    |
|      [ ] Manufacturer    [ ] Distributor        [ ] Vehicle dealer           |
|      [ ] Garage          [ ] Hotel              [ ] Restaurant [ ] Bakery    |
|      [ ] Retail store    [ ] Real estate agency [ ] Other                    |
|  MINIMUM BUSINESS SIZE                                                       |
|  [ ] Micro  [ ] Small  [x] Medium  [x] Large  [ ] Unknown size               |
|  Unknown size is off by default: an unsized business is usually a stub.      |
|  MINIMUM OPPORTUNITY SCORE   [ 70 ]   0 -------------------o------- 100      |
|  Businesses below this are researched, then SKIPPED with reason              |
|  BELOW_MIN_SCORE. They are not deleted and not re-researched.                |
|  RESEARCH DEPTH   (o) Standard    ( ) Deep                                   |
|  Standard: one Gemini call per business. Deep: up to three, and more page    |
|  fetches - about 3x the daily quota per business.                            |
|  CAP   [ 400 ] businesses. Blank means uncapped.                             |
| +--------------------------------------------------------------------------+ |
| | ESTIMATE   4 cities, depth STANDARD, cap 400.                            | |
| | Gemini requests needed: up to 400. Remaining in today's quota: {{178}}.   | |
| | This will run over about {{3}} days at the current daily limit.           | |
| | Research pauses at the ceiling and resumes the next day by itself.        | |
| +--------------------------------------------------------------------------+ |
|  [ Save as draft ]                              [ START RESEARCH ]*          |
+------------------------------------------------------------------------------+
```
SAMPLE values in the estimate box.

**Regions**

| Region | Source |
|---|---|
| Name placeholder | client-derived from the city chips plus today in IST; server default per `13-api-endpoints.md` §13.4.1 |
| City chips | typed, normalised by `radar/identity.py::city_slug`, stored as `campaign_cities.city` / `.city_slug` / `.ordinal` |
| City autocomplete | `SELECT DISTINCT city, city_slug FROM businesses ORDER BY city` — previously-seen cities only. The form never calls Nominatim; geocoding happens in discovery, under its 1 req/s policy |
| Category checkboxes | `category_ref`, mirroring the `businesses.category` CHECK list in `_CONTEXT.md` §6 |
| Size checkboxes | the `businesses.size_band` CHECK list |
| Min score / Depth / Cap | `campaigns.min_opportunity_score`, `.research_depth`, `.max_businesses` |
| Estimate: remaining quota | `GET /api/v1/quota` (§15.16), bucket `llm.gemini.day` |
| Estimate: days | `ceil(cap / remaining_daily_requests)`; renders `—` when the quota endpoint is unreachable, never a guess |

**Validation.** Client-side for immediacy, re-run server-side because the client is not trusted.
Codes are `13-api-endpoints.md` §13.4.1's.

| Field | Rule | Message under the field | Server code |
|---|---|---|---|
| `cities` | at least 1 | `Add at least one city. Discovery is city-by-city.` | `CITIES_REQUIRED` 422 |
| `cities` | at most 12 | `12 cities is the limit. Each city is a separate Overpass sweep and a separate research queue.` | `CITY_LIMIT` 422 |
| `cities` | no duplicate `city_slug` | `Dhule is already in the list.` | deduped, no error |
| `name` | 3..200 chars if given | `Give it 3 characters or leave it blank.` | 422 |
| `categories`, `size_filter` | subset of the enum | `Unknown category.` / `Unknown size band.` | `INVALID_ENUM` 422 |
| `min_opportunity_score` | integer 0..100 | `A score is 0 to 100.` | 422 |
| `max_businesses` | null or > 0 | `Leave blank for no cap, or give a number above 0.` | 422 |
| slug | unique | `A campaign called that already exists. Rename it, or open the existing one.` | `SLUG_CONFLICT` 409 |

The score field is a number input **and** a slider bound to it: 70 is a value Sagar types and
0-100 is a range he wants to feel. The number is authoritative; the slider writes to it.

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `START RESEARCH` | at least one city chip, no field-level error, and today's Gemini request quota is not exhausted | `Gemini's daily request quota is used up. Save this as a draft - it will start when the quota resets.` |
| `Save as draft` | at least one city chip | `Add a city first.` |
| Category checkbox group | the `Choose` radio is selected | greyed with the group; no per-box sentence |

`START RESEARCH` posts `{"start": true}` to `POST /api/v1/campaigns` and lands on
`/campaigns/<id>`. When the quota is exhausted the server creates the campaign as `DRAFT` anyway
and names the reason in the body; the client shows the banner rather than a failure toast, because
a campaign that was created is not an error.

---

## 15.3 Campaign dashboard (§36) — `/campaigns/<id>`

### 15.3.1 The list at `/campaigns`

```
+------------------------------------------------------------------------------+
|  CAMPAIGNS                                            [ + New campaign ]*    |
|  [ Active 1 ] [ Complete 6 ] [ Draft 2 ] [ All ]      Search [           ]   |
+------------------------------------------------------------------------------+
| RESEARCHING  Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026                      |
|              4 cities - started 2h ago - 96 of 148 researched                |
|              [=================-------------] 65%             [ Open ]      |
+------------------------------------------------------------------------------+
| COMPLETE     Nashik deep sweep - 19 Aug 2026                                 |
|              1 city - 63 qualified - 21 verified - 9 contacted - 2 interested|
|                                                    [ Open ] [ Report .html ] |
+------------------------------------------------------------------------------+
| PAUSED !     Jalgaon retail - 24 Aug 2026                                    |
|              Paused: RATE_LIMIT. Resumes when the Gemini quota resets.       |
|                                                    [ Open ] [ Resume now ]-  |
+------------------------------------------------------------------------------+
```
SAMPLE rows, from `GET /api/v1/campaigns`. The progress figure is `campaigns.n_researched /
campaigns.n_discovered`, labelled a hint and never rendered as a fact (`13` §13.4.3). `Resume now`
on a quota-paused campaign is disabled with `The daily Gemini quota is exhausted. This resumes on
its own after the reset.`

### 15.3.2 The dashboard

```
+------------------------------------------------------------------------------+
| < Campaigns   Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026       [RESEARCHING] |
|               Created by Sagar - 26 Aug 2026 09:40 IST                       |
|               Cities Dhule, Shirpur, Nashik, Jalgaon - Industries All        |
|               Size MEDIUM, LARGE - Min score 70 - Depth STANDARD             |
+------------------------------------------------------------------------------+
| [ Dashboard* ] [ Report ] [ Selection 15 ] [ Exports 3 ] [ Activity ]        |
+------------------------------------------------------------------------------+
|  ! Research is paused: today's Gemini request quota is used up.              |
|    52 businesses are still queued. This resumes by itself after the quota    |
|    resets at 12:30 IST (00:00 America/Los_Angeles).        [ Quota status ]  |
+------------------------------------------------------------------------------+
|  PROGRESS                                              as of 11:42:08 IST    |
|  Discovery   Dhule COMPLETE 41 - Shirpur COMPLETE 18 - Nashik COMPLETE 62    |
|              Jalgaon COMPLETE 27                                             |
|  Research    [==============------------]  96 / 148                          |
|              queued 45  running 0  failed 1  dead 0     ETA --  (paused)     |
+------------------------------------------------------------------------------+
|  STATISTICS (§36)                                                            |
|   Found   Researched  Qualified  Verified  Selected  Prepared  Approved      |
|    148       141          63        21        15        15         9         |
|   Sent    Responses   Interested   Demos   Proposals    Won                  |
|      9        3            2         1         —         —                   |
+------------------------------------------------------------------------------+
|  [ Generate report ]  [ Export CSV ]  [ Cancel campaign ]                    |
+------------------------------------------------------------------------------+
```
SAMPLE figures.

**Regions**

| Region | Source |
|---|---|
| Header line 1 | `campaigns.name`, `.status` |
| Header line 2 | `campaigns.created_by` -> `users.display_name`, `campaigns.created_at` rendered IST |
| Header lines 3-4 | `campaign_cities.city` in `ordinal` order; `campaigns.industries`, `.categories`, `.size_filter`, `.min_opportunity_score`, `.research_depth` |
| Quota banner | `campaigns.status = 'PAUSED' AND campaigns.paused_reason = 'RATE_LIMIT'`; queued count from `GET /api/v1/campaigns/<id>/progress`; reset time from `GET /api/v1/quota` |
| Discovery line | `campaign_cities.status`, `.n_discovered` |
| Research bar | `progress.hint.n_researched / progress.hint.n_discovered`; job counts from the same payload |
| ETA | `progress.eta_seconds`; always `—` while `PAUSED`, because an ETA that ignores the quota wall is a lie |
| Statistics strip | `GET /api/v1/campaigns/<id>/stats` `funnel{}`, reading `v_campaign_counters` aggregates, never `campaigns.n_*` |

The thirteen §36 figures, each an aggregate over `campaign_businesses` joined to the business it
names — that many-to-many join table is what makes "this campaign's numbers" well-defined for a
business appearing in three campaigns:

| # | Figure | Definition | `—` when |
|---|---|---|---|
| 1 | Businesses Found | `COUNT(*)` over `campaign_businesses` for the campaign | never |
| 2 | Researched | `businesses.research_status = 'COMPLETE'` | never |
| 3 | Qualified | `is_qualified = 1`: score >= `campaigns.min_opportunity_score` and every filter passes | nothing researched |
| 4 | Verified | a live `verifications` row, `verdict = 'VERIFIED'`, `superseded_at IS NULL` | never |
| 5 | Selected | `selections.state <> 'REMOVED'` | never |
| 6 | Outreach Prepared | `outreach_drafts` with `superseded_by IS NULL` | never |
| 7 | Approved | `outreach_approvals` rows | never |
| 8 | Sent | `outreach_messages.status IN ('SENT','DELIVERED','BOUNCED')` | never |
| 9 | Responses | `responses` rows against this campaign's messages | nothing sent |
| 10 | Interested | `responses.classification` in the §34 interest set | nothing sent |
| 11 | Demos | `handoffs.demo_held_at IS NOT NULL` | no handoffs |
| 12 | Proposals | `handoffs.proposal_sent_at IS NOT NULL` | no handoffs |
| 13 | Won | `handoffs.outcome = 'WON'`, value from `handoffs.won_value_inr` | no handoffs |

Figures 11-13 render `—` rather than `0` in a campaign that has never produced a handoff. That is
§3.5's argument at its sharpest: `Won: 0` invites the reading "we tried and lost"; `Won: —` says
"this has not got that far".

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `Generate report`, `Export CSV` | `status IN ('RESEARCHING','REPORTING','PAUSED','COMPLETE')` and at least one researched business | `Nothing has been researched yet.` |
| `Cancel campaign` | `status NOT IN ('COMPLETE','CANCELLED','FAILED')` | `This campaign has already finished.` Typed confirmation, §15.18.2 |
| `Resume now` | `status = 'PAUSED'` and `paused_reason = 'MANUAL'` | `Paused by the quota, not by you. It resumes on its own.` |
| Live poll | `status IN ('QUEUED','DISCOVERING','RESEARCHING','REPORTING')` | the poll stops; the page shows `as of` plus `[ Refresh ]` |

The page subscribes to `GET /api/v1/campaigns/<id>/events` (SSE) and falls back to polling
`/progress` every 2 s. Both stop at a terminal state and both stop when the tab is hidden — a
laptop nobody is watching should not be waking its own web server.

---

## 15.4 Campaign report view — `/campaigns/<id>` tab `Report`

This is the live rendering of `03-html-report.md`'s document. The export is the same Jinja
templates inlined into one file; the live view adds the controls that write. Column order, KPI
definitions, filters and badges are `03`'s and are not restated — what follows is the shell, the
tab mechanics and the two divergences.

```
+------------------------------------------------------------------------------+
| [ Dashboard ] [ Report* ] [ Selection 15 ] [ Exports 3 ] [ Activity ]        |
+------------------------------------------------------------------------------+
| AI BUSINESS OPPORTUNITY RESEARCH                                             |
| Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026        Search date 26 Aug 2026    |
| Found 148 - Researched 141 - Qualified 63 - Skipped 12 - Need verification   |
| 21 - Ready for outreach 6                                                    |
+------------------------------------------------------------------------------+
| KPI CARDS (§7, twelve, 03 §3.4.2)                                            |
| +----------+----------+----------+----------+----------+----------+          |
| | Total    | Qualified| High opp | Med opp  | Low opp  | Website  |          |
| |   148    |    63    |    19    |    44    |    66    |    91    |          |
| |          | score>=70|  80-100  |  60-79   | below 60 | 12 unkn. |          |
| | No site  | Software | Need ver.| Verified | Contacted| INTEREST |          |
| |    45    |    58    |    21    |    21    |     9    |    2     |*         |
| +----------+----------+----------+----------+----------+----------+          |
|   19 not scored yet                                                          |
+------------------------------------------------------------------------------+
| CITY CARDS (§8, 03 §3.4.3)                                                   |
| +--------------+--------------+--------------+--------------+                |
| | DHULE        | SHIRPUR      | NASHIK       | JALGAON      |                |
| | Found     41 | Found     18 | Found     62 | Found     27 |                |
| | Qualified 18 | Qualified  4 | Qualified 29 | Qualified 12 |                |
| | High opp   6 | High opp   1 | High opp   9 | High opp   3 |                |
| | Verified   7 | Verified   2 | Verified   9 | Verified   3 |                |
| | Ready      2 | Ready      0 | Ready      3 | Ready      1 |                |
| +--------------+--------------+--------------+--------------+                |
+------------------------------------------------------------------------------+
| CITY TABS      [ All ] [ Dhule* ] [ Shirpur ] [ Nashik ] [ Jalgaon ]         |
| INDUSTRY TABS  [ All ] [ Healthcare* ] [ Education ] [ Automobile ]          |
|                [ Manufacturing ] [ Retail ] [ Hospitality ] [ Distribution ] |
|                [ Real estate ] [ Professional services ] [ Other ]           |
+------------------------------------------------------------------------------+
| FILTERS (§39, eleven, 03 §3.6.2)    Search [                    ]  63 of 148 |
+------------------------------------------------------------------------------+
| [ ] Business        City   Cat.  Size  Web  DM  Score  Solution  Contact ... |
| [ ] SAMPLE Hospital Dhule  HOSP  MED   Yes  62  [86]   Hospital   E          |
|     sample-hosp.in                                     Operations            |
|     .. Conf [MED]  Verif [NOT VERIFIED]  Outreach [NOT CONTACTED]            |
|     .. [View] [Research v] [Verify] [Reject] [History v]  Ready to prepare   |
+------------------------------------------------------------------------------+
| DHULE 5 - NASHIK 7 - JALGAON 3        15 selected                            |
| [ Clear ] [ Copy 15 ids ]                       [ PREPARE OUTREACH (15) ]*   |
+------------------------------------------------------------------------------+
```
SAMPLE row and SAMPLE counts (the selection strip reproduces §18's own example).

**Regions.** All `03-html-report.md`'s: header block §3.4.1, KPI cards §3.4.2 (`Q_KPIS`), city cards
§3.4.3 (`Q_CITY_SUMMARY`), tabs §3.4.4, table §3.4.5 (`Q_ROWS`), filters §3.6.2, selection strip
§3.7.2. The fourteen columns are §9's, in §9's order.

**Tab mechanics.** Two tab strips, city over industry, both `role="tablist"` with arrow-key
navigation, `Home`/`End`, and `aria-selected`. The state lives in the URL hash (`03` §3.6.5), so a
tab selection is linkable, and `history.replaceState` keeps the back button meaningful.

**The two divergences from the export.**

| | Export (`03`) | Live (`15`) |
|---|---|---|
| Row actions | `act_link` emits `<a>` or a disabled chip; no `<form>` exists in `templates/report/` | same macro, plus `VERIFY` / `REJECT` / `SELECT` as real navigations and a real checkbox |
| Freshness | fixed at generation; the header says when | header carries `as of <time>` and `[ Refresh ]`; the page never silently re-renders under the cursor |
| SEND | not rendered | **not rendered** |

That last row is the point. §40 lists SEND as a row action and §19 forbids it here; the resolution
is `03` §3.8.3's read-only **send-readiness chip**, which shows the first unmet precondition (`Not
researched`, `Needs verification`, `No contact`, `DO NOT CONTACT`, `Blocked: contacted 6 days
ago`, `Ready to prepare`, `Policy blocked`, `Awaiting your approval`, `Approved - send in
Outreach`), each linking to the screen where that condition is resolved. Even in the one state
where every §40 precondition is met, the control is a link to `/outreach/<draft_id>`, not a
transmit button.

---

## 15.5 Business detail and research panel (§11-§14) — `/business/<id>`

§12 calls the OBSERVED / INFERRED / UNKNOWN separation mandatory. On screen that has to mean
*visually distinct at a glance and impossible to mistake for one another*: three separate
`<fieldset>` elements, three legends, three left rules in three tokens, no shared list.

```
+------------------------------------------------------------------------------+
| < Dhule / Healthcare        SAMPLE Diagnostics Centre    [NEEDS_VERIFICATION] |
|                             Diagnostic centre - SMALL     Opportunity [72]    |
|                             Dhule                         Confidence [MEDIUM] |
|  [ Verify this business ]*   [ Skip ]   [ Re-research ]   [ Add suppression ] |
+------------------------------------------------------------------------------+
| IDENTITY (§11)                                                               |
|  Website   https://sample-diagnostics.example.in [open] PRESENT              |
|            last checked 23 Aug 2026 04:02 UTC                                |
|  Listing   OpenStreetMap node/1234567890 [open]                              |
|  Address   SAMPLE - Station Road, Dhule 424001 [map]                         |
|  Size      SMALL   evidence: 1 site, no branch list                          |
|  Digital maturity 62/100     Operational complexity 55/100                   |
|  Discovered 26 Aug 2026 from Overpass, campaign cmp_01JSAMPLE...             |
+------------------------------------------------------------------------------+
| PUBLIC BUSINESS CONTACT (§11)                                                |
|  info@sample-diagnostics.example.in   business email   role address          |
|    from .../contact - captured 23 Aug   [ human-confirmed ] by Sagar 24 Aug  |
|  +91 XXXXX XXXXX                      listed phone     not confirmed         |
|    from OpenStreetMap - captured 26 Aug              [ Confirm this ]        |
+------------------------------------------------------------------------------+
| RESEARCH FINDINGS (§12)  run res_01JSAMPLE... COMPLETE                        |
|                          gemini-2.5-flash / research-v3 / 23 Aug 04:10 UTC   |
| +--------------------------------------------------------------------------+ |
| | OBSERVED - supported directly by a source        3 findings  GREEN RULE  | |
| |  - Four services listed on the site: pathology, radiology, ECG, X-ray    | |
| |    HIGH 90%   sources: [1] site/services 23 Aug                          | |
| |  - No online report download or patient login   HIGH 88%   [1] 23 Aug    | |
| |  - Listed opening hours 07:30-21:00, seven days MEDIUM 70% [2] 26 Aug    | |
| +--------------------------------------------------------------------------+ |
| | INFERRED - reasonable conclusions, not facts     2 findings  BLUE RULE   | |
| |  - Report delivery is likely manual (counter collection or WhatsApp)     | |
| |    MEDIUM 64%   drawn from: OBSERVED 1, OBSERVED 2                       | |
| |    why: a four-service lab with no patient portal usually hands reports  | |
| |         over at the counter                                              | |
| +--------------------------------------------------------------------------+ |
| | UNKNOWN - could not be verified. Do not assert these.                    | |
| |                                                  2 findings  GREY RULE   | |
| |  - Daily patient volume     NOT_PUBLISHED                                | |
| |  - Existing lab software    NOT_PUBLISHED                                | |
| +--------------------------------------------------------------------------+ |
+------------------------------------------------------------------------------+
| SOFTWARE OPPORTUNITY (§13)                                        score 72   |
|  Potential problem   Reports and billing tracked on paper across four        |
|                      services; no single record per patient visit.           |
|  Potential solution  Diagnostic Centre Operations Platform                   |
|  Modules             Patients - Billing - Reports - Inventory - Dashboard    |
|  Expected benefit    One record per visit; report turnaround measurable.     |
|  Confidence          MEDIUM (64%)                                            |
|  Why 72?             digital_maturity 24 - operational_complexity 18 -       |
|                      size 12 - contactability 10 - sector fit 8  [expand]    |
+------------------------------------------------------------------------------+
| SOURCES (§14)                                                                |
|  # Name                   Type  Checked       Obtained             Conf      |
|  1 Practice website       SITE  23 Aug 04:02  services, no portal  HIGH      |
|    .../services                                    [open] [snapshot]         |
|  2 OpenStreetMap node     OSM   26 Aug 09:15  hours, address       MEDIUM    |
|    openstreetmap.org/node/1234567890               [open]                    |
+------------------------------------------------------------------------------+
| OUTREACH HISTORY (§32)                             see §15.11                |
+------------------------------------------------------------------------------+
```
SAMPLE business throughout.

**Regions**

| Region | Source |
|---|---|
| Header name / status / score / confidence | `businesses.name`, `.status`; `opportunities.score`, `.confidence` where `is_current = 1` |
| Website, listing, address, size, maturity | `businesses.{website, website_status, website_checked_at, listing_url, address, size_band, size_evidence, digital_maturity, operational_complexity}` |
| Discovered | `campaign_businesses.{first_seen_at, discovery_source, campaign_id}` |
| Contact rows | `business_contacts.{kind, value_display, is_role_address, human_verified, source_url, captured_at}` where `is_active = 1` |
| Run meta | `research_runs.{id, status, model_id, prompt_version, finished_at}` for the latest run with `status = 'COMPLETE'` |
| OBSERVED / INFERRED / UNKNOWN | `research_findings.{kind, label, statement, confidence, confidence_pct, ordinal}` for that run, `is_current = 1`, ordered by `kind` then `ordinal` |
| INFERRED "drawn from" | `research_findings.derived_from` resolved to antecedent labels; `.inference_note` verbatim |
| UNKNOWN reason | `research_findings.unknown_reason` |
| Opportunity block | `opportunities.{potential_problem, potential_solution, expected_benefit, score, confidence, confidence_pct}` |
| Modules | `opportunity_modules.module` ordered by `opportunity_modules.ordinal`, `is_current = 1` |
| Why 72 | `opportunities.score_breakdown` JSON; each component anchors to its `because_finding_id` |
| Sources | `sources.{name, url, source_type, checked_at}` joined via `finding_sources`, plus `finding_sources.excerpt` as "Obtained" |

**Rendering rules for the three groups** — the mandatory part:

| Rule | Why |
|---|---|
| Three `<fieldset>` elements with `<legend>`, never one list with a badge column | a badge is scannable but skippable; a legend is a boundary |
| Legends carry the meaning: `OBSERVED - supported directly by a source`, `INFERRED - reasonable conclusions, not facts`, `UNKNOWN - could not be verified. Do not assert these.` | the reader is about to decide whether a message may say them |
| Left rules `--ok-ln` / `--info-ln` / `--muted-ln` | `03` §3.9.4. `INFERRED` is blue, not yellow: §51 gives blue to information, and yellow is reserved for work Sagar has to do |
| An empty group is **rendered empty**, with `No observed findings.` inside it | a missing OBSERVED fieldset would read as "we did not look" |
| Every OBSERVED statement carries a source link; a finding with no `finding_sources` row gets a `no source` chip and leaves the citable set | matches `03` §3.4.6.3 and `04` §4.5.3 exactly, so the report, this screen and the policy engine agree on what is citable |
| Source links are `target="_blank" rel="noopener noreferrer nofollow"`, only for absolute `http(s)`; otherwise the name renders with `title="URL withheld: not an absolute http(s) URL"` | `03` §3.2.6's `safe_url` |
| Statements render **verbatim** — no summarising, no re-wording, no LLM call at render time | `05` §5.5.3's rule, applied here because this is where the judgement is formed |

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `Verify this business` | `status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')` and no live suppression | suppressed: `Do not contact: an opt-out or suppression is recorded.` Already verified: `Verified on 24 Aug 2026.` with `[ Re-verify ]` beside it |
| `Skip` | `status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')` | `Already parked.` |
| `Re-research` | latest run `COMPLETE` or `FAILED`, none `RUNNING`, quota not exhausted | quota: `Gemini's daily quota is used up. This will queue and run after the reset.` — and it then queues rather than blocking |
| `Add suppression` | always | — Typed confirmation, §15.18.2 |
| `Confirm this` (contact) | `business_contacts.human_verified = 0` and `is_active = 1` | — |
| `Prepare outreach` | **absent** unless `status = 'CONTACT_READY'`; when present it navigates to `/outreach` | §15.18.1 |

---

## 15.6 Verification screen (§15, §16) — `/verify/<id>`

`04-verification-workflow.md` §4.5.2 fixes eight zones and 37 elements. Two columns on a wide
screen: evidence left (Z1-Z6, scrollable), checklist right (Z7, sticky), so no check can be ticked
without its evidence on screen at the same time. Under 1024 px the checklist moves below and each
check keeps its anchor to the zone it is about.

```
+------------------------------------------------------------------------------+
| < Queue 7 of 21     SAMPLE Diagnostics Centre        E01  [NEEDS_VERIFICATION]|
|                     Dhule - Healthcare / Diagnostic centre   E02 E03  E06     |
|                     Opportunity [72] E04   Confidence [MEDIUM] E05            |
|                     [ < Previous ]  [ Next > ]  E07                           |
+--------------------------------------------+---------------------------------+
| EVIDENCE                                   | CHECKLIST (§16)             Z7   |
| Z2 IDENTITY                                | [x] 1 Business identity appears  |
|   Website  sample-diagnostics.example.in   |       correct              E28   |
|           [open] E09  PRESENT 23 Aug       |     Name, address and website    |
|   Listing  OSM node/1234567890 [open] E10  |     belong to one real business. |
|   Address  Station Road, Dhule 424001 E08  |     -> Z2                        |
|   Size     SMALL E11                       | [x] 2 Business is located in     |
|   Found    26 Aug, Overpass E12            |       target city          -> Z2 |
|   ! Possible duplicate: SAMPLE Diagnostic  | [ ] 3 Business category is       |
|     Lab, Dhule  [compare] E13              |       correct  -> Z2             |
| Z3 CONTACTS                                |       [ wrong category? ]        |
|   info@sample-diagnostics.example.in       | [x] 4 Business appears           |
|     role address - from /contact 23 Aug E16|       operational          -> Z4 |
|     [ Confirm this contact ] E17           | [x] 5 Contact information        |
| Z4 FINDINGS                                |       appears to be a legitimate |
|   OBSERVED (3)  INFERRED (2)  UNKNOWN (2)  |       business contact     -> Z3 |
|   ... the three fieldsets of §15.5 ... E18 | [x] 6 Research is relevant -> Z4 |
| Z4 SOURCES                            E19  | [ ] 7 Software opportunity       |
|   [1] Practice website  SITE  23 Aug       |       appears reasonable   -> Z5 |
|       [open live] [open snapshot]  visited | [x] 8 Outreach is appropriate    |
|   [2] OSM node          OSM   26 Aug       |                            -> Z5 |
|       [open live]                  visited | [x] 9 No do-not-contact record   |
|   [3] MCA21 master data REG   22 Aug       |       exists               -> Z6 |
|       [open live] DEAD [snapshot]          | ---------------------------------|
|       [ Skip this source - reason... ]     | SOURCES VISITED            E30   |
| Z5 OPPORTUNITY                        E21  | 2 of 3 required.  1 left:        |
|   Problem / Solution / Modules / Benefit   | [3] MCA21 master data            |
|   Why 72? E22   Modules E23                | [ go to it ]                     |
|   AI recommendation E24                    | TIME ON THIS SCREEN        E31   |
| Z6 SUPPRESSION & HISTORY                   | 00:38 of 00:47   [=========---]  |
|   Opt-out records: none               E25  | WHY (min 15 chars)         E29   |
|   Prior responses: none               E26  | [ Site lists 4 services and no  ]|
|   Prior rejections: none              E27  | [ patient portal; counter       ]|
| Z8 HISTORY                                 | [ collection is plausible.      ]|
|   Prior verifications: none           E35  |  84 characters                   |
|   Outreach so far: none               E36  | [ APPROVE - VERIFIED ]-    E32   |
|                                            |  2 checks unanswered, 1 required |
|                                            |  source not visited, 9s of dwell |
|                                            |  remaining.                      |
|                                            | [ Reject... ] E33  [ Skip ] E34  |
|                                            | Rejecting needs a reason and     |
|                                            | nothing else.                    |
+--------------------------------------------+---------------------------------+
```
SAMPLE business. There is no SEND control here and no "verify all" control anywhere in the app
(§15.18.1, `04` §4.7.4).

**Regions.** `04` §4.5.2's element table is the authority for each `E##`. The five this document is
responsible for rendering rather than sourcing:

| Region | Source | Rendering |
|---|---|---|
| Checklist E28 | `verification_check_defs.{check_key, ordinal, prompt, helper, evidence_zone}` joined to `verification_checks.{passed, note, carried_from}` | nine rows in `ordinal` order, prompt verbatim from §16, helper in `--text-2`, `-> Zn` an in-page anchor to `evidence_zone` |
| Source progress E30 | `verification_sources` where `is_required = 1`: visited-or-waived over total | names the first unvisited source and links straight to it |
| Dwell meter E31 | client timer vs `verifications.dwell_required_ms`; server compares `now - verifications.opened_at` | a bar, not a countdown clock — it is a floor, not a deadline |
| Why-note E29 | `verifications.why_note` | live character count; the count moves from `--warn-fg` to `--text-2` at 15 |
| Approve E32 | the §4.6.4 ladder | see Controls below |

**The nine checks.** `check_key` in `ordinal` order: `IDENTITY_CORRECT`, `CITY_IN_TARGET`,
`CATEGORY_CORRECT`, `APPEARS_OPERATIONAL`, `CONTACT_LEGITIMATE`, `RESEARCH_RELEVANT`,
`OPPORTUNITY_REASONABLE`, `OUTREACH_APPROPRIATE`, `NO_DNC_RECORD`. Tri-state in the data (`passed`
is `1`, `0` or `NULL` for unanswered), two-state on screen: ticked, or not ticked and therefore
unanswered. Unticking after ticking sets `passed = 0`, which is what turns the approve control
into a reject path — a checklist where "no" is invisible is a checklist with one answer.

**The anti-rubber-stamp measures, as UI.** `04` §4.7 specifies five; four are visible here and the
fifth is invisible by design.

| Measure (`04` §) | How this screen renders it |
|---|---|
| §4.7.2 required source visits | E30 is a **progress line, not a warning**: `2 of 3 required. 1 left:` with the name and a link. Visiting fires the §4.5.3 beacon and the line updates without a reload. `[ Skip this source ]` opens a required reason field (>= 10 chars) inline, under the source — never in a modal, because a modal invites a reflex |
| §4.7.2 dead source | struck-through with a `DEAD` chip, snapshot link promoted to primary, auto-waived, and check 4 `APPEARS_OPERATIONAL` gets a `--warn` outline: a dead source is evidence about check 4, so the screen routes it there rather than hiding it |
| §4.7.3 minimum dwell | E31 is a filling bar labelled `00:38 of 00:47 required`, applying to APPROVE only. **Reject and Skip have no dwell at all** and are live from the first second. The asymmetry is the design and it is stated on screen: `Rejecting needs a reason and nothing else.` |
| §4.7.4 no "verify all" | no such control on this screen, on the queue, on the report grid or in any template. Absence, not disablement (§15.18.1) |
| §4.7.5 the why-note | E29 is a required textarea **above** the approve control. 15-char minimum with a live count. A note byte-identical to the previous verification's is refused server-side (`400 WHY_NOTE_DUPLICATE`) and the field says `That is the same sentence you wrote for the previous business.` |
| §4.7.6 audit distinguishability | invisible. `verifications.mode`, `dwell_ms`, `active_ms` and the source counts are stored, not shown; the screen does not tell the operator he is being measured, because the measurement is for the audit |

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `APPROVE - VERIFIED` E32 | all nine checks answered `1`; every required source visited or waived; `now - opened_at >= dwell_required_ms`; `why_note` >= 15 chars trimmed; no live suppression | the first unmet condition, quantified and updating live: `2 checks unanswered, 1 required source not visited, 9s of dwell remaining.` |
| `Reject...` E33 | always | — opens the reason panel from `verification_reason_codes`; a permanent reason also writes a `suppressions` row and the panel says so before submit |
| `Skip` E34 | always | — |
| `Confirm this contact` E17 | contact exists and `human_verified = 0` | — |
| `wrong category?` | always | opens the corrector, writes `businesses.category`, audits `CATEGORY_CORRECTED` |
| `Next >` E07 | a next row exists in the §4.5.4 queue | `This is the last business in the queue.` |
| SEND | **absent** | — |

The approve button is disabled rather than absent, and that is the one deliberate exception to
"absent, not disabled": approving is the action this screen exists for, and hiding it would leave
the operator with no idea what he is working towards. What is absent is *bulk* approval. The
distinction the rule draws is between "the control you are working towards" and "a control that
should never be reachable from here".

Every predicate above is re-evaluated in `POST /api/v1/verifications/<id>/submit` (`04` §4.6.4's
eleven-step ladder). A client that enables the button early gets a `400` naming the step —
`DWELL_NOT_MET` with remaining milliseconds, `SOURCES_NOT_VISITED` with the ids,
`WHY_NOTE_TOO_SHORT`. A disabled button is a suggestion; the ladder is the rule.

---

## 15.7 Selection tray (§18)

§18's example is the specification: *"Dhule 5, Nashik 7, Jalgaon 3 = 15 selected"*. A sticky bar
at the bottom of the report grid, with reserved height so it appears without shifting the table.

```
+------------------------------------------------------------------------------+
|  DHULE 5  -  NASHIK 7  -  JALGAON 3                       15 selected        |
|  3 of your 15 selected businesses are hidden by the current filters.         |
|  [ Clear ]  [ Copy 15 ids ]                      [ PREPARE OUTREACH (15) ]*  |
+------------------------------------------------------------------------------+
```
SAMPLE counts.

**Regions**

| Region | Source |
|---|---|
| Per-city counts | client-side over the `SELECTED` set keyed on `tr[data-city]`; cities in `campaign_cities.ordinal` order, zero-count cities omitted |
| Total | `SELECTED.size` |
| Hidden warning | count of selected ids whose row is currently filtered out |
| Server truth | `GET /api/v1/campaigns/<id>/selection-counts`, reconciled on load and after every write to `selections` |

Rules that matter more than the layout:

- `SELECTED` is a `Set` of business ids, never a query over checked DOM nodes. Filtering a row out of
  view must not deselect it, and the bar says when rows are hidden. A count that silently dropped
  would be the worst possible bug on a screen whose whole job is deciding who gets contacted.
- Only `CONTACT_READY` gets an enabled checkbox in the ordinary case; `CONTACTED` and `RESPONDED` get
  one only for a permitted follow-up. `03` §3.7.1's table is the authority and this screen does not
  extend it.
- A disabled checkbox is a real `<input type="checkbox" disabled>` — never a hidden input, never an
  absent cell — so the column stays scannable. Because a disabled input is not focusable, the reason
  is also visually-hidden text referenced by `aria-describedby`, with a focusable `i` affordance.
- Header "select all" ticks only the **enabled, currently visible** boxes. It never selects a
  filtered-out row and never selects a blocked one.

**Controls**: the row checkbox per `03` §3.7.1, disabled rows carrying their `BLOCK_REASON` sentence;
`PREPARE OUTREACH (n)`, `Clear` and `Copy n ids` all enabled at `n >= 1` (the bar is hidden at
zero, so there is nothing to explain); and nothing that sends.

---

## 15.8 Outreach workspace (§20) — `/outreach`

§20 asks for a dedicated screen showing, per selected business: the business, the research
summary, why it was selected, the opportunity, the recommended solution and modules, and the
available channels. `05` §5.5.2 turns that into seven panels; the workspace is a left rail of the
selection grouped by city and one business at a time in the main area.

```
+---------------------+--------------------------------------------------------+
| DHULE (5)           | 1  SELECTED BUSINESS                                   |
|  > SAMPLE Diagnos.  |    SAMPLE Diagnostics Centre - Dhule - Diagnostic       |
|    SAMPLE Hospital  |    centre - SMALL - CONTACT_READY - Opportunity 72      |
|    ...              | 2  RESEARCH SUMMARY                                    |
| NASHIK (7)          |    OBSERVED 3 / INFERRED 2 / UNKNOWN 2   [ expand ]     |
|    ...              | 3  WHY WAS THIS SELECTED                               |
| JALGAON (3)         |    (a) You ticked all nine checks on 24 Aug 2026,      |
|    ...              |        ver_01JSAMPLE...                                |
|                     |        note: "Site lists 4 services and no patient      |
| BLOCKED SINCE YOU   |        portal; counter collection is plausible."        |
| SELECTED THEM (1)   |    (b) Findings the score was built from, verbatim,     |
|  ! SAMPLE Motors    |        with finding ids and sources                    |
|    Opt-out arrived  |    (c) Score 72, band MEDIUM, breakdown by component   |
|    27 Aug 06:10     |    (d) Eligibility: every gate PASS at SELECT stage    |
|                     | 4  POTENTIAL SOFTWARE OPPORTUNITY   score 72 MEDIUM    |
|                     | 5  RECOMMENDED SOLUTION  Diagnostic Centre Operations  |
|                     |    Expected benefit  One record per visit ...          |
|                     | 6  RECOMMENDED MODULES  Patients - Billing - Reports - |
|                     |    Inventory - Dashboard                               |
|                     | 7  AVAILABLE CONTACT CHANNELS                          |
|                     |    (o) EMAIL   info@sample-diagnostics.example.in      |
|                     |        confirmed - via Gmail SMTP                      |
|                     |    ( ) WHATSAPP  +91 XXXXX XXXXX                    -  |
|                     |        No recorded opt-in. WhatsApp needs one before   |
|                     |        a business-initiated message.  [ what is this ] |
|                     |    ( ) PHONE   Phone is manual only in v1 (TRAI/DND)-  |
|                     |    ( ) MANUAL  record something you sent by hand       |
|                     |                                                        |
|                     |    [ GENERATE MESSAGE ]*    [ Remove from selection ]  |
+---------------------+--------------------------------------------------------+
```
SAMPLE business.

**Regions.** All seven panels are `05` §5.5.2's, with panel 3 governed by §5.5.3's hard rule: every
sentence is a column value or a count, no LLM runs at render time, and every string carries the
row id it came from. The left rail's grouping uses `selections.city`, copied at select time so the
counts survive a later re-classification. The "blocked since you selected them" band is
`selections.state = 'BLOCKED'` with `blocking_gate`, and it is deliberately not silent — a
disappearing row is how a person stops trusting the tool.

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| Channel `EMAIL` | `contact_policy.email_enabled = 1`, a valid active `business_contacts` row of kind `EMAIL`, no suppression on the address or its domain | `No confirmed email contact.` or the `BLOCK_REASON` sentence |
| Channel `WHATSAPP` | a `whatsapp_optins` row exists for the number | `No recorded opt-in. WhatsApp needs one before a business-initiated message.` |
| Channel `PHONE` | never, in v1 | `Phone is manual only in v1 (TRAI/DND).` |
| Channel `MANUAL` | always | — |
| `GENERATE MESSAGE` | a channel is chosen, eligibility passes at SELECT stage, quota not exhausted | quota: `Gemini's daily quota is used up. This will queue and draft after the reset.` — it queues, it does not fail |
| `Remove from selection` | `selections.state <> 'DISPATCHED'` | `A message has already gone out for this selection.` |
| SEND | **absent** | — |

`GENERATE MESSAGE` enqueues one `jobs` row per selection (`kind = 'draft_outreach'`) and the
workspace polls `GET /api/v1/outreach/batches/<batch_id>`. Drafting is asynchronous because it is
a Gemini call per business, and on the free tier those calls are rate-limited: the panel shows
`Drafting 4 of 15 - about 90s remaining at the current rate` rather than a spinner with no number.

---

## 15.9 Message preview (§27) — `/outreach/<draft_id>`

Nine panels in §27's order, because that order is an argument: who, how, to whom, on what
evidence, for what reason, saying what, how sure, allowed by whom, and what has passed between us
before. `05` §5.11 owns the panel table; `06` §6.11 owns the content of four of them.

```
+------------------------------------------------------------------------------+
| < Outreach       Draft out_01JSAMPLE...          status PENDING_APPROVAL      |
+---------------------------------------+--------------------------------------+
| 1 BUSINESS                            | 4 RESEARCH BASIS                     |
|   SAMPLE Diagnostics Centre           |   OBSERVED                           |
|   Dhule - HEALTHCARE / DIAGNOSTIC_    |    - Four services listed on the     |
|   CENTER - SMALL   [CONTACT_READY]    |      site   HIGH 90%                 |
|   Opportunity [72]                    |      [1] site/services 23 Aug [open] |
|                                       |    - No patient login  HIGH 88%      |
| 2 CHANNEL                             |      [1] site 23 Aug [open]          |
|   EMAIL via Gmail SMTP                |   INFERRED  (hedged in the message)  |
|   From radar.sagar@gmail.com (SAMPLE) |    - Report delivery likely manual   |
|   Transmitted by: this machine, on    |      MEDIUM 64%                      |
|   your approval                       |   UNKNOWN  (never mentioned)         |
|                                       |    - Daily patient volume            |
| 3 CONTACT                             |    - Existing lab software           |
|   info@sample-diagnostics.example.in  |                                      |
|   business email - role address       | 5 OPPORTUNITY                        |
|   [ human-confirmed ] by Sagar 24 Aug |   72 MEDIUM 64% - Diagnostic Centre   |
|   from /contact captured 23 Aug       |   Operations Platform                |
|   [ use a different contact ]         |   Modules: Patients, Billing,        |
|                                       |   Reports, Inventory, Dashboard      |
+---------------------------------------+--------------------------------------+
| 6 GENERATED MESSAGE                                        edited 1x [ edit ] |
|   Subject: A possible digital operations solution for SAMPLE Diagnostics      |
|   Hello SAMPLE Diagnostics Centre team, ...                                   |
|   Regards, Sagar                                                              |
|   --                                                                          |
|   To stop receiving these, reply with UNSUBSCRIBE or write to                 |
|   radar.sagar+unsub@gmail.com                                                 |
|   Hovering a sentence shows the finding it is bound to.                       |
+------------------------------------------------------------------------------+
| 7 AI CONFIDENCE   MEDIUM 71%                                                  |
|   gemini-2.5-flash / msg-email-v3 / template email.v2 / rewrite applied       |
|   3412 in, 984 out tokens                                                     |
+------------------------------------------------------------------------------+
| 8 POLICY CHECK                                                      WARN      |
|   CLAIM CHECK (06 §6.9)                        27 passed, 1 fired, 4 n/a      |
|    ! K1  "Report collection is handled at the counter."                       |
|          A claim bound to an INFERRED finding must hedge. Add "may" or         |
|          "we believe".                            [ jump to sentence ]        |
|   ELIGIBILITY CHECK (05 §5.9)                                                 |
|    PASS  A  no suppression on business, address, number or domain             |
|    PASS  B  channel EMAIL enabled, transport SMTP resolved                    |
|    PASS  C  research complete, 3 OBSERVED findings cited                      |
|    PASS  D  verified 24 Aug 2026, 3 days old, valid for 30                    |
|    PASS  E  contact confirmed by a human                                      |
|    PASS  F  no message in flight for this business                            |
|    PASS  G  never contacted; min gap 21 days not applicable                   |
|    WARN  H  today's sends 7 of 25                                             |
+------------------------------------------------------------------------------+
| 9 CONTACT HISTORY   No previous contact.                                      |
+------------------------------------------------------------------------------+
|                                        [ CONFIRM & SEND... ]-                 |
|                                        One claim policy rule is unresolved.   |
+------------------------------------------------------------------------------+
```
SAMPLE draft. `radar.sagar@gmail.com` is SAMPLE and stands for the dedicated free Gmail account of
`_CONTEXT.md` §4.

**Regions.** Panels 1, 2, 3 and 9 from `05` §5.11; panels 4, 5, 6, 7 and 8 from `06` §6.11. Panel 2
names the transport in words because on this stack it is not obvious: there is no ESP, the message
leaves this laptop over Gmail SMTP with an App Password, and the operator should know that "sent"
means "handed to Gmail from here".

**The policy-check panel.** This is the panel that earns the screen. Two blocks, never merged.

| Block | Source | Rendering |
|---|---|---|
| Claim check | `outreach_drafts.policy_result` + `policy_detail` (`06` §6.9.11 JSON) | one line per fired rule, quoting the offending sentence, naming the rule id, saying what would fix it. `[ jump to sentence ]` scrolls panel 6 and highlights the segment |
| Eligibility check | the `Eligibility` object from `05` §5.9.12, evaluated in **this request** | every gate A-H, grouped PASS / WARN / BLOCK, each with its sentence and evidence ids |

Rules the panel obeys:

- Every rule is listed, including the ones that passed and the ones that did not apply. A panel that
  shows only failures cannot be distinguished from a panel that failed to run.
- `PASS` uses `--ok`, `WARN` `--warn`, `BLOCK` `--bad`; the counts line is `--text-2`. Colour is never
  the only channel — each row starts with the literal word.
- A `BLOCK` verdict makes panel 6 read-only. The operator cannot edit his way past a block without
  the edit going back through the engine; `06` §6.10's `policy_checked_body_hash` enforces that
  server-side and the UI reflects it — editing re-runs the check and the new verdict replaces the old
  one before the confirm control re-evaluates.
- Gate H's warning form (`today's sends 7 of 25`) is a warning and says so; its blocking form (`daily
  cap reached`) disables confirm.

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `edit` (panel 6) | `outreach_messages.status IN ('DRAFT','PENDING_APPROVAL','POLICY_BLOCKED')` | `This message has already been approved.` |
| `use a different contact` | more than one active contact of the channel's kind | `This is the only confirmed contact.` |
| `regenerate` | status not `APPROVED`/`QUEUED`/`SENT`, and quota remains | `Gemini's daily quota is used up.` |
| `CONFIRM & SEND...` | `confirm_blockers()` returns empty (`05` §5.13.3) | the **first** blocker's sentence, one line, under the button |
| SEND (direct) | **absent** | — the button opens the §15.10 dialog; it does not transmit |

The label carries an ellipsis: `CONFIRM & SEND...` opens a dialog, and the control that transmits
lives inside it and nowhere else.

---

## 15.10 Confirm and send dialog (§28)

§28 requires seven items on screen before the button enables, and fixes the wording of the
sentence above it. Both are literal requirements and both are tested.

```
+==============================================================================+
|  CONFIRM AND SEND                                                       [x]  |
+==============================================================================+
|  You are about to contact this business using the selected business contact. |
|  1 BUSINESS   SAMPLE Diagnostics Centre - Dhule - DIAGNOSTIC_CENTER          |
|               CONTACT_READY - Opportunity 72                                 |
|  2 CONTACT    info@sample-diagnostics.example.in                             |
|               business email - role address - human-confirmed by Sagar       |
|               24 Aug 2026 - captured from /contact 23 Aug 2026               |
|  3 CHANNEL    EMAIL - Gmail SMTP from radar.sagar@gmail.com (SAMPLE)         |
|               Transmitted by this machine, now, on your approval.            |
|  4 MESSAGE    Subject: A possible digital operations solution for SAMPLE     |
|               Diagnostics                                                    |
|               +---------------------------------------------------------+   |
|               | Hello SAMPLE Diagnostics Centre team,                   |   |
|               | ... full final text, scrollable, not truncated ...      |   |
|               | Regards, Sagar                                          |   |
|               | --                                                      |   |
|               | To stop receiving these, reply with UNSUBSCRIBE or write |   |
|               | to radar.sagar+unsub@gmail.com                          |   |
|               +---------------------------------------------------------+   |
|  5 PREVIOUS   No previous contact.                                           |
|     CONTACT                                                                  |
|  6 OPT-OUT    No opt-out on file for this business, this address, this       |
|     STATUS    number or this domain.  checked just now, 27 Aug 11:52:04 IST  |
|  7 APPROVAL   Approving as Sagar (session, password + TOTP).                 |
|               This writes a permanent approval record: apr_... will name     |
|               you, the time, the exact message text and this sentence.       |
|  This send cannot be recalled.                                               |
|  Type SEND to enable the button:  [           ]                              |
|  [ Cancel ]                                       [ CONFIRM & SEND ]-        |
+==============================================================================+
```
SAMPLE draft.

**The sentence.** `You are about to contact this business using the selected business contact.` is
rendered verbatim from one constant, `radar.web.app.CONFIRMATION_TEXT`, and the same string is
written to `outreach_approvals.confirmation_text` so an audit two years later reads what the
operator was actually shown (`05` §5.13.1). A test asserts constant == template == stored value.

**Regions**

| # | §28 item | Source | Rendered |
|---|---|---|---|
| 1 | Business | `businesses.{name, city, category, status}`, `opportunities.score` | never truncated |
| 2 | Contact | `business_contacts.{value_display, kind, is_role_address, human_verified, human_verified_by, source_url, captured_at}` | the exact address that will be used, not a masked form |
| 3 | Channel | request + `contact_policy` | channel, transport, and who transmits, in words |
| 4 | Message | `outreach_drafts.final_body` (= `COALESCE(body_edited, body)`) and `subject` | the **full** final text including signature and the `mailto:` unsubscribe footer; scrollable, never elided |
| 5 | Previous contact history | `OUTREACH_HISTORY_SQL` (`05` §5.18.1) | the §32 table, or the words `No previous contact.` |
| 6 | Opt-out status | gate A, evaluated **inside this request**, never a cached flag | the positive form with a timestamp, or the §30 `DO NOT CONTACT` banner |
| 7 | Approval status | the session's `users` row and `session_auth_method` | who, when, and that this creates a permanent record |

Item 6's positive form matters: "no opt-out" is a claim the system makes, so it is made from a
live evaluation in the same request that draws the dialog, stamped with the time it was made.

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `CONFIRM & SEND` | `confirm_blockers()` empty **and** the typed field equals `SEND` exactly | the first blocker's sentence, or `Type SEND above to enable this.` |
| `Cancel`, `[x]`, `Esc` | always | closing is never blocked; nothing is written until the button is pressed |

**Behaviour**

- A real `<dialog>` with `showModal()`, focus trapped, focus returned to the opener on close,
  `aria-modal`, `Esc` closing it.
- The button posts `POST /api/v1/outreach/drafts/<draft_id>/approve` with the preview token, body
  hash, eligibility fingerprint, the seven `displayed` flags and the idempotency key (`05` §5.13.4).
  Every field is re-derived server-side.
- On success the dialog is replaced in place by `Queued. job_01JSAMPLE... will transmit within a
  minute.` with a link to `/business/<id>#history`. It does not close on its own — the operator
  closes it when he has read the result.
- A double click is one send: the same `idempotency_key` returns `200` with `duplicate: true` and the
  same screen (`05` §5.14). A double click should feel like a single click, not like an error.
- `409 preview_stale` reloads the preview rather than showing a dead end, with `Something changed
  while this was open. Read the policy panel again.` — if the token died because a gate flipped, that
  is exactly what has to be re-read.

**Forbidden labels, enforced.** `FORBIDDEN_BUTTON_TEXT = ("auto send", "send all", "send now to
all", "blast", "auto-send")` and `test_no_forbidden_send_labels` greps every template. The button
reads `CONFIRM & SEND` and nothing else, on every screen, forever.

---

## 15.11 Outreach history (§32) — `/business/<id>#history`

§32 asks for eight fields per organisation. One query, `OUTREACH_HISTORY_SQL` (`05` §5.18.1),
rendered here, in preview panel 9 and in the handoff brief — one query, three renderings, so the
three cannot disagree.

```
+------------------------------------------------------------------------------+
| OUTREACH HISTORY                                                             |
+------------------------------------------------------------------------------+
| 27 Aug 11:53  EMAIL  seq 1   info@sample-diagnostics.example.in              |
|   Subject: A possible digital operations solution for SAMPLE Diagnostics     |
|   [ view exact message sent ]                                                |
|   Sender    Sagar   approved 27 Aug 11:52  apr_01JSAMPLE...                  |
|   Delivery  [DELIVERED] 27 Aug 11:53:14                                      |
|   Response  28 Aug 09:14  "Please send details and pricing."                 |
|   AI read   [MORE_INFORMATION]  HIGH 88%   gemini-2.5-flash / classify-v3    |
|   Next      Send the material personally                                     |
+------------------------------------------------------------------------------+
| No further outreach: follow-up 2 available from 17 Sep 2026 (21-day gap).    |
+------------------------------------------------------------------------------+
```
SAMPLE row.

**Regions**

| Region | Source |
|---|---|
| Date, channel, sequence, address | `outreach_messages.{sent_at, channel, sequence_no, to_address_display}` |
| Subject / message link | `outreach_messages.subject_final`; the link opens the stored `body_final`, it does not re-render a template |
| Sender | `users.display_name` via `outreach_messages.sent_by`, plus `outreach_approvals.{approved_at, id}` |
| Delivery status | `outreach_messages.status`, badge per `03` §3.9.5, plus `failure_code` when set |
| Response | `responses.body_excerpt`, `responses.received_at` |
| AI classification | `responses.{classification, confidence, confidence_pct, model_id}` |
| Next action | `next_action()` (`05` §5.18.1) — deterministic Python, never a model call |
| Footer line | the gate G evaluation, giving the date the next follow-up becomes available |

The history renders the **excerpt**, not the full reply body, and links to the full text. A screen
that embeds every inbound message in full turns a business record into a mail client, and the full
text lives one click away where it is auditable.

**Controls**: `view exact message sent` (always), `Reclassify` on a response (always; writes an audit
row and never re-runs an LLM without one), and nothing that sends.

---

## 15.12 Handoff inbox and handoff detail (§34) — phone first

`10-human-handoff.md` §10.5.4 and §10.5.5 specify the desktop rendering. This section specifies
the phone one, because that is where Sagar actually reads a handoff: the Telegram alert arrives on
his phone at 9pm and the link opens on the same device. The design target is a 390 px viewport,
one thumb, no horizontal scroll, every decision reachable without pinch-zoom.

Since the app is bound to `127.0.0.1` (`_CONTEXT.md` §2), the phone reaches it over the LAN or not
at all. The Telegram message therefore carries the whole §34 brief in its own text — the link is a
convenience, not the delivery mechanism. A handoff that cannot be opened must still be answerable
from the Telegram text.

### 15.12.1 Inbox — `/handoffs`

```
+--------------------------+
| HANDOFFS            [=]  |
| [Open 4] [Ack 1] [All]   |
+--------------------------+
| ! URGENT                 |
| SAMPLE Traders           |
| Nashik - COMPLAINT       |
| opened 2h - ACK OVERDUE  |
+--------------------------+
| HIGH                     |
| SAMPLE Industries        |
| Dhule - DEMO_REQUESTED   |
| opened 14h - ACK OVERDUE |
+--------------------------+
| NORMAL                   |
| SAMPLE High School       |
| Shirpur - INTERESTED     |
| opened 1d - ack 4h left  |
+--------------------------+
```
SAMPLE rows. Each card is a single tap target of at least 44x44 px. Sort order is fixed and
**not** user-configurable: `URGENT` first, then overdue-by-most, then oldest. A queue that can be
sorted by "newest" is a queue that hides the thing you are avoiding.

**Regions**: `handoffs.{priority, state, trigger_classification, created_at, sla_ack_due_at}` joined
to `businesses.{name, city}`. The ack countdown is `sla_ack_due_at - now`, rendered `ACK OVERDUE`
in `--bad` past due.

### 15.12.2 Detail — `/handoffs/<id>`

The desktop version is `10` §10.5.4. On a phone the same content becomes one column of collapsible
sections, ordered by what a person needs first with the phone in one hand.

```
+--------------------------+
| < Handoffs               |
| SAMPLE Industries        |
| [DEMO_REQUESTED] [OPEN]  |
| Dhule - Manufacturing    |
| Opportunity 91 HIGH      |
| Ack due 23 Aug 10:20     |
+--------------------------+
| [ Acknowledge ]*         |
| [ In progress ] [ Close ]|
| [ Snooze 12h ]           |
+--------------------------+
| THEIR RESPONSE           |
| EMAIL 22 Aug 18:41       |
| rajesh@sample-inds.ex..  |
| +----------------------+ |
| | Yes, please show us  | |
| | what you can provide.| |
| +----------------------+ |
| AI read DEMO_REQUESTED   |
| HIGH 92%                 |
| gemini-2.5-flash /       |
| classify-v3              |
| [ Disagree ]             |
+--------------------------+
| WHAT TO DO       (open)  |
| Reply by email within    |
| 24h with two demo slots. |
| Talking points           |
| - Production and stock   |
|   visibility across two  |
|   units (OBSERVED)       |
| - Dispatch traceability  |
|   (INFERRED - hedge)     |
| - Do not claim anything  |
|   about current software.|
|   UNKNOWN.               |
| rule R-DEMO-EMAIL-01     |
| [ Copy ] [ Open mail ]   |
| No send button exists    |
| here.                    |
+--------------------------+
| CONTACT        (collapsed)|
| OPPORTUNITY    (collapsed)|
| RESEARCH BASIS (collapsed)|
| WHAT WE SENT   (collapsed)|
| ACTIVITY       (collapsed)|
+--------------------------+
```
SAMPLE handoff.

**Phone-specific rules**

| Rule | Reason |
|---|---|
| Order: identity, state, actions, their words, what to do. Everything else collapses | on a phone the first screen is all most readings get, and it must contain the decision |
| The reply is quoted in a bordered block, in full, never truncated here | it is the only text on the page written by the prospect; truncating it is how a lead gets misread |
| `Acknowledge` is one tap, writes `handoffs.acknowledged_at` immediately, no dialog | acknowledgement is not destructive and the SLA is running |
| `Close...` opens a sheet requiring `outcome`; `WON` additionally requires `won_value_inr` | the DB CHECK requires it (`10` DDL); asking after the fact never works |
| Collapsed sections are `<details>`, open state per handoff in `localStorage` inside `try/catch` | a browser that blocks storage still renders every section, closed |
| `Copy` puts the recommended action and talking points on the clipboard | the next thing Sagar does is paste it into his own mail client |
| `Open mail` is a `mailto:` link, subject prefilled, **no body** | §34's recommended action is advice; it is never executable |
| No send control anywhere on the page, and the page says so in words | §19 applies to leads too — this is where automation is supposed to stop |

**Regions**: `handoffs.brief_json` (the `HandoffBrief` snapshot of `10` §10.5.1) with the live
`handoffs.{state, priority, sla_ack_due_at, outcome}` read fresh. When `brief_json` is unreadable
the page renders the scalar columns plus `Brief unavailable - rebuild` and logs an error naming
the handoff id; it never substitutes an empty brief.

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `Acknowledge` | `state = 'OPEN'` | `Acknowledged 23 Aug 09:02.` |
| `In progress` | `state IN ('OPEN','ACKNOWLEDGED')` | `Already in progress.` |
| `Close...` | `state <> 'CLOSED'` | `Closed 25 Aug - WON.` |
| `Snooze 12h` | `state <> 'CLOSED'` | — |
| `Disagree` | a `responses` row exists | — opens reclassification, writes an audit row |
| anything that sends | **absent** | — |

---

## 15.13 Suppression list — `/suppressions`

§30 requires that an opt-out blocks all outreach and that the reason, date and source are shown.
`_CONTEXT.md` invariant 3 makes it permanent and un-clearable by the app. The screen's job is to
make that state legible, and to make the absence of a delete control obvious rather than
mysterious.

```
+------------------------------------------------------------------------------+
| DO NOT CONTACT                                            [ + Add record ]   |
| Scope < All v >  Reason < All v >   Search [                    ]   34 rows  |
+------------------------------------------------------------------------------+
| Scope     Value                        Reason           Recorded    Source   |
| EMAIL     info@sample-motors.example   REPLY_OPT_OUT    27 Aug 06:10 rsp_... |
|   "please remove us from your list"                              [ open ]    |
| BUSINESS  SAMPLE Traders (biz_...)     COMPLAINT        24 Aug 18:02 rsp_... |
| DOMAIN    sample-group.example         BOUNCE_HARD      22 Aug 09:41 msg_... |
| EMAIL     owner@sample-school.example  UNSUBSCRIBE_LINK 20 Aug 07:33 aud_... |
|   mailto: unsubscribe received by the inbox poller                           |
+------------------------------------------------------------------------------+
| These records cannot be removed from this screen, and there is no API route  |
| that removes one. Clearing an opt-out is a manual sqlite3 session plus a     |
| SUPPRESSION_RELEASED audit row. That is deliberate.                          |
+------------------------------------------------------------------------------+
```
SAMPLE rows.

**Regions**: `suppressions.{scope, value_norm, reason, source, source_ref, created_at, detail}` where
`released_at IS NULL`, newest first. The quoted line under a row is `detail` JSON's verbatim
evidence. `source_ref` links to the `rsp_` / `msg_` / `aud_` row that caused it.

**Controls**: `+ Add record` (always; typed confirmation, §15.18.2); `open` on a row when
`source_ref` is set, otherwise `No source row recorded.`; and **no** delete or release control at
all — the footer sentence explains the absence, in place, once.

Value masking follows `13-api-endpoints.md` §13.3: `OWNER` sees the full value, `OPERATOR` a
masked one, `VIEWER` a hash. The screen renders what the API returns and never reconstructs a
masked value.

---

## 15.14 Comparisons and the daily report

### 15.14.1 City comparison (§37) — `/compare#cities`

```
+------------------------------------------------------------------------------+
| CITY COMPARISON            Campaign < Dhule-Shirpur... v >  or < All time v > |
+------------------------------------------------------------------------------+
| City     Busin. Qual. HighOpp Verif. Contact Resp. Inter. Conv.  Potential Rs |
| Dhule       41    18       6      7       4     2      1  25.0%            —  |
| Shirpur     18     4       1      2       0     —      —     —             —  |
| Nashik      62    29       9      9       5     1      1  20.0%            —  |
| Jalgaon     27    12       3      3       0     —      —     —             —  |
+------------------------------------------------------------------------------+
| Conversion is interested / contacted. A city with nothing contacted has no   |
| conversion rate; it renders — , not 0%.                                      |
| Potential revenue sums only priced rows. 0 of 63 qualified rows are priced.  |
+------------------------------------------------------------------------------+
```
SAMPLE figures.

**Regions**: `03` §3.4.7's `Q_CMP_CITY`, unchanged — ten columns, §37's, from `campaign_cities` LEFT
JOINed to the business view so a city that returned nothing still gets a row of zeros rather than
vanishing. `—` appears wherever the query returned NULL, and the two footnotes explain the two
places that happens most.

**Controls**: the campaign selector (always), a sort control on every numeric column (`aria-sort`
maintained), and `[ Export CSV ]`, which writes a `report_exports` row with `fmt = 'CSV'`, `scope
= 'CITY'`.

### 15.14.2 Industry comparison (§38) — `/compare#industries`

Same shell, ten columns from `Q_CMP_INDUSTRY` (`03` §3.4.8): Industry, Businesses, Opportunity
(average, with the scored count in `title`), Verified, Contacted, Responses, Interested, Demos,
Won, Revenue. Demos, Won and Revenue come from `handoffs.{demo_held_at, outcome, won_value_inr}`.
Revenue is `—` when no won handoff carries a value — which, in a system that has not closed a deal
yet, is every row, and that is the honest rendering. Industries with zero businesses in scope are
listed with zeros rather than omitted: §38 is a comparison, and a missing row silently changes
what is compared.

### 15.14.3 Daily report (§43) — `/reports/daily/<YYYY-MM-DD>`

```
+------------------------------------------------------------------------------+
| DAILY BUSINESS OPPORTUNITY REPORT              26 Aug 2026     [ < ] [ > ]   |
+------------------------------------------------------------------------------+
| ! Discovery, outreach and response counts are for 26 Aug 2026. Verification  |
|   and outreach-ready counts are as of now (27 Aug 2026, 08:00 IST), because  |
|   they are work queues rather than events.                                   |
+------------------------------------------------------------------------------+
| Cities researched  Dhule, Shirpur, Nashik, Jalgaon                           |
| Discovered 148   Qualified 63   Sent 9   Responses 3   Interested 2          |
| Needing verification (now) 21   Ready for outreach (now) 6                   |
+------------------------------------------------------------------------------+
| TOP OPPORTUNITIES (10)                                                       |
|  1  SAMPLE Industries    Dhule    MANUFACTURING  91  HIGH  NOT VERIFIED      |
|  2  SAMPLE Hospital      Nashik   HEALTHCARE     86  MED   VERIFIED          |
+------------------------------------------------------------------------------+
| INTERESTED LEADS - these are handoffs, open them                             |
|  SAMPLE Industries   DEMO_REQUESTED   opened 22 Aug 18:42   [ open handoff ] |
+------------------------------------------------------------------------------+
| QUOTA YESTERDAY   Gemini requests 247 of 250 used - research paused 14:20    |
|                   IST and resumed 12:31 IST today.                           |
+------------------------------------------------------------------------------+
```
SAMPLE figures.

**Regions**: `03` §3.4.10's `Q_DAILY_HEADLINE` and its Top-20 variant, plus one addition owed to the
free stack — a **quota line** for the day, from `spend_ledger` grouped by `day_ist` where `kind =
'LLM'`, with pause and resume times from the `audit_log` rows the pause writes. A daily report
that does not say "we stopped at 14:20 because the quota ran out" leaves the operator to infer it
from a small number, and he will infer something worse.

The mixed time semantics are stated on the page, not in a footnote: without that sentence the two
halves look like they disagree. A day with no activity renders every count at its real value plus
one line at the top: `No businesses were discovered on 26 Aug 2026.` It is never suppressed — an
absent daily report is indistinguishable from a broken scheduler, and on a laptop that is not on
24/7 that distinction is the whole value of the page.

**Controls**: `[ < ] [ > ]` step by day, disabled before the first campaign's creation date and after
today, saying `No data before 19 Aug 2026.` / `Tomorrow has not happened yet.` `[ Export .html ]`
writes `report_exports` with `fmt = 'HTML'`, `scope = 'DAILY'`, `scope_key = '2026-08-26'`.

---

## 15.15 Settings — `/settings`

Five tabs. Everything on them writes an `audit_log` row, and the ones that change what may be sent
are `OWNER`-only per `13-api-endpoints.md` §13.3.

```
+------------------------------------------------------------------------------+
| SETTINGS   [ Contact policy* ] [ Channels ] [ Templates ] [ Quota ] [ Jobs ] |
+------------------------------------------------------------------------------+
| AUTOMATION MODE (§46)                                                        |
|  ( ) MANUAL          nothing is drafted; you write everything                |
|  (o) HUMAN_APPROVAL  the only supported mode in v1                           |
|  ( ) SEMI_AUTOMATED                                                       -  |
|  ( ) FULLY_AUTOMATED                                                      -  |
|  The last two are not selectable in this build. They exist in the schema so  |
|  that turning them on is a deliberate, audited, code-level act rather than   |
|  a checkbox somebody finds one evening.                                      |
+------------------------------------------------------------------------------+
| CONTACT FREQUENCY (§31)                                                      |
|  Minimum days between outreach   [ 21 ]                                      |
|  Maximum outreach attempts       [ 3 ]      Maximum follow-ups   [ 2 ]       |
|  [x] Stop after explicit rejection                                           |
|  [x] Stop after opt-out                     these two cannot be unticked  -  |
+------------------------------------------------------------------------------+
| DUPLICATE PROTECTION (§29)                                                   |
|  Recent campaign window [ 90 ] days   Same domain [ 30 ] days  Max [ 1 ]     |
+------------------------------------------------------------------------------+
| SENDING (free Gmail)                                                         |
|  Daily send cap [ 25 ]   Minimum gap between sends [ 45 ] seconds            |
|  Verification valid for [ 30 ] days                                          |
|  ! Free Gmail allows 500 recipients a day. The working limit here is 15-25   |
|    and it is set by policy, not by Google: one recipient per message, a      |
|    per-business body, per-message human approval, a working unsubscribe.     |
|    Raising this past 25 changes what this is.                                |
+------------------------------------------------------------------------------+
```

**Regions**: every field is a `contact_policy` column of the same name (`automation_mode`,
`min_days_between_outreach`, `max_attempts`, `max_followups`, `stop_after_rejection`,
`stop_after_opt_out`, `recent_campaign_days`, `same_domain_days`, `same_domain_max`,
`daily_send_cap`, `send_min_gap_seconds`, `verification_valid_days`), scope `GLOBAL`.

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `SEMI_AUTOMATED`, `FULLY_AUTOMATED` | never in v1 | `Not available in this build.` |
| `Stop after explicit rejection`, `Stop after opt-out` | never untickable | `This cannot be turned off.` |
| numeric fields | `OWNER` session | `Only the owner can change contact policy.` |
| `Save` | at least one field changed and all valid | `Nothing has changed.` |

**Channels tab**: `email_enabled`, the Gmail account address, App Password status (present / absent,
never the value), IMAP polling interval and last successful poll, and a read-only WhatsApp block
saying `Business-initiated WhatsApp needs a pre-approved template and a recorded opt-in. v1 sends
wa.me links you open yourself.` The email block states plainly that there is no custom domain,
that SPF/DKIM/DMARC are Google's, and that a spam complaint costs the account rather than a
domain.

**Templates tab**: the §24 email and §25 WhatsApp skeletons, read-only, with the §26 industry
vocabularies shown per category. Editing a template bumps `template_version`, and the tab says so
before the editor opens.

**Jobs tab**: `13` §13.16's console — queue depth, dead letters, last run per schedule, and the
catch-up state after a launch: `this machine was off from 22:10 to 08:40; the daily report for 26
Aug was generated late, the 07:35 inbox poll was skipped to the next occurrence`. That sentence is
the whole reason the tab exists on a laptop deployment.

**Quota tab**: §15.16.

---

## 15.16 Quota status — `/settings#quota` and the global strip

This screen has no spec section. It exists because the free stack made the LLM ceiling a hard,
visible, daily fact of operating the system: `_CONTEXT.md` §2 replaced every rupee budget with a
quota budget, and a 429 pauses research rather than failing it. A pause the operator cannot see is
indistinguishable from a hang.

### 15.16.1 The global strip

Present on every page, one line, in the header, right of the nav:

```
  Gemini today  178 / 250 requests            (normal, --text-2)
  Gemini today  231 / 250 requests            (>= 80%, --warn)
  Gemini today  250 / 250 - research paused   (exhausted, --bad, links to the tab)
```

Text, not a gauge, because the number is the thing. It updates from the same `GET /api/v1/quota`
payload the pages already poll, and renders `Gemini today —` rather than a stale number when the
endpoint is unreachable.

### 15.16.2 The tab

```
+------------------------------------------------------------------------------+
| SETTINGS  [ Contact policy ] [ Channels ] [ Templates ] [ Quota* ] [ Jobs ]  |
+------------------------------------------------------------------------------+
| GEMINI FREE TIER - gemini-2.5-flash                                          |
|  Requests today     231 of 250   [=====================-----]  92%           |
|                     resets 00:00 America/Los_Angeles = 12:30 IST             |
|                     19 remaining, about 19 more businesses at STANDARD depth |
|  Requests this min. 6 of 10      [============--------------]                |
|  Tokens today       412,880      no daily token ceiling on this tier         |
|  ! When the daily ceiling is reached                                         |
|    - the running campaign moves to PAUSED with paused_reason = RATE_LIMIT    |
|    - queued research jobs stay queued; nothing is lost and nothing fails     |
|    - message drafting queues the same way                                    |
|    - verification, selection, preview, approval and SEND are unaffected:     |
|      none of them calls an LLM                                               |
|    - the scheduler resumes on the first launch after the reset               |
+------------------------------------------------------------------------------+
| WHAT USED IT TODAY                                                           |
|  Research synthesis      188 requests   cmp_01JSAMPLE... (4 cities)          |
|  Message drafting         31 requests   15 drafts, 1 regenerate, 1 repair    |
|  Response classification  12 requests                                        |
+------------------------------------------------------------------------------+
| LAST 7 DAYS                                                                  |
|  26 Aug  250/250  paused 14:20, resumed 12:31 next day                       |
|  25 Aug  198/250          24 Aug   96/250          ...                       |
+------------------------------------------------------------------------------+
| OTHER LIMITS                                                                 |
|  Gmail sends today   7 of 25 (policy cap; Google's own cap is 500)           |
|  Nominatim           1 request/second, enforced by rate_buckets              |
|  Overpass            shared public instance; back off on 429                 |
+------------------------------------------------------------------------------+
```
SAMPLE figures. The 250/day and 10/min numbers are **read from config** (`config.yaml:
llm.free_tier.requests_per_day / requests_per_minute`), not hardcoded, because Google changes
free-tier limits without notice and a number baked into a template becomes a lie the day they do.

**Regions**

| Region | Source |
|---|---|
| Requests today | `v_spend_today.llm_requests` — `SUM(quota_units)` over today's IST `kind='LLM'` rows, per `14-background-jobs.md` §14.3.5. Not `COUNT(*)`: `quota_units` is the count of requests charged against the ceiling, so a call that ever costs more than one stays countable |
| Daily ceiling | `config.yaml` `llm.free_tier.requests_per_day` |
| Reset time | computed from the configured reset zone; rendered in both zones because the ceiling is Pacific and the operator is IST |
| Requests this minute | `rate_buckets` row `llm.gemini.rpm`: `capacity - tokens` |
| Tokens today | `v_spend_today.llm_tokens` — `SUM(units)` over the same `spend_ledger` slice |
| Remaining businesses | `remaining_requests / requests_per_business(depth)`; `—` when depth varies across queued jobs |
| What used it | `spend_ledger` grouped by a `detail` JSON `purpose` key (`RESEARCH`, `DRAFT`, `CLASSIFY`) |
| Last 7 days | `spend_ledger` grouped by `day_ist`; pause/resume times from `audit_log` `CAMPAIGN_PAUSED` / `CAMPAIGN_RESUMED` |
| Gmail sends today | `COUNT(*) FROM outreach_messages WHERE substr(sent_at,1,10) = <today> AND status IN ('SENT','DELIVERED','BOUNCED')`, against `contact_policy.daily_send_cap` |

**Controls**

| Control | Enabled when | When off, it says |
|---|---|---|
| `Resume paused campaigns now` | a campaign is `PAUSED` with `paused_reason = 'RATE_LIMIT'` **and** remaining requests > 0 | `Nothing to resume` / `The quota is still exhausted. This will resume by itself after the reset.` |
| `Pause all research` | any campaign in a running state | `No campaign is running.` Writes `paused_reason = 'MANUAL'` |
| Quota numbers | read-only, always | — the ceiling is not ours to edit |

**The design point.** Every other pause reason in this system is a failure. This one is not, and the
copy says so: `research paused`, `resumes by itself`, `nothing is lost`. The list of what is
*unaffected* is on the screen deliberately — the operator's most likely wrong conclusion when he sees
a red quota strip is "I cannot work", and the correct one is "I cannot research; verification and
outreach are exactly as available as they were".

---

## 15.17 Design system

### 15.17.1 Type scale

One family, one scale, six steps. `system-ui` first: this runs on a Windows laptop and Segoe UI is
already there, correct, and hinted.

```css
:root{
  --font: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace;
  --t-xs: 11px;   /* badges, table meta, provenance ids        line-height 1.35 */
  --t-sm: 12px;   /* helper text, sub-lines, source captions   line-height 1.4  */
  --t-md: 14px;   /* body, table cells, form inputs   BASE     line-height 1.45 */
  --t-lg: 16px;   /* panel titles, card labels                 line-height 1.4  */
  --t-xl: 20px;   /* the one screen title                      line-height 1.3  */
  --t-2xl: 28px;  /* KPI and statistic-strip numbers only      line-height 1.15 */
}
```

| Step | Used for | Never used for |
|---|---|---|
| `--t-xs` | badge text, row ids in `--mono`, `checked_at` stamps | anything a decision depends on |
| `--t-sm` | checkbox helper lines, field errors, panel footnotes | table cell values |
| `--t-md` | everything by default | — |
| `--t-lg` | `<h2>` panel headings, KPI labels | body copy |
| `--t-xl` | the one `<h1>` per screen | — |
| `--t-2xl` | KPI and statistic numbers | anything that is not a number |

Every research finding, message body and prospect reply renders at `--t-md` or larger: the text
this system exists to make readable is never the smallest text on the screen.

### 15.17.2 Spacing scale

A 4 px base, seven steps, no arbitrary values in the templates.

```css
:root{
  --s-1: 4px;    --s-2: 8px;    --s-3: 12px;   --s-4: 16px;
  --s-5: 24px;   --s-6: 32px;   --s-7: 48px;
  --r: 8px;              /* corner radius, everywhere */
  --r-pill: 999px;       /* badges only */
  --measure: 68ch;       /* max line length for prose: findings, messages, notes */
}
```

| Step | Used for |
|---|---|
| `--s-1` | badge padding; gap between a value and its unit |
| `--s-2` | gap between related controls; table cell padding (vertical) |
| `--s-3` | table cell padding (horizontal); gap between form fields |
| `--s-4` | padding inside a card or panel; gap between cards |
| `--s-5` | gap between panels |
| `--s-6` | gap between major sections of a screen |
| `--s-7` | space above a screen's footer actions |



### 15.17.3 Colour tokens (§51)

§51 is a constraint, not a suggestion: green for verified / interested / won, yellow for needs
verification / follow-up, red for rejected / opt-out / blocked, blue for research / information,
and
*do not use excessive colours*. `03-html-report.md` §3.9.2 already defines the token set. **These are
the same tokens, verbatim.** No second palette, no per-industry colour, no per-city colour, no
rainbow score scale.

```css
:root{                                    /* complete LIGHT palette, on bare :root */
  color-scheme: light;
  --page:#f4f4f2; --surface-1:#ffffff; --surface-2:#f7f7f5; --surface-3:#efefec;
  --rule:#dcdcd7;  --grid:#e6e6e2;
  --text-1:#0b0b0b; --text-2:#52514e; --text-3:#6f6d68;
  /* §51 semantic families: fg = text on the tint, bg = tint, ln = left rule */
  --ok-fg:#0f6b3f;   --ok-bg:#e6f4ea;   --ok-ln:#1f8a55;
  --warn-fg:#7a5200; --warn-bg:#fdf2d6; --warn-ln:#b07d0a;
  --bad-fg:#9f1f24;  --bad-bg:#fbe7e7;  --bad-ln:#c0393e;
  --info-fg:#14508a; --info-bg:#e5eff9; --info-ln:#2e6fae;
  --muted-fg:#4a4a46;--muted-bg:#eeeeea;--muted-ln:#9b9a94;
  --accent:#14508a;  --focus:#14508a;
}

/* The DARK values below appear TWICE, verbatim, under two selectors:
     @media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){ ... } }
     :root[data-theme="dark"]{ ... }
   The media block is guarded so an explicit light choice wins; the attribute block
   makes the toggle win in both directions. Neither is the only definition of a token. */
  color-scheme: dark;
  --page:#0e0f11; --surface-1:#16171a; --surface-2:#1c1e22; --surface-3:#212429;
  --rule:#2f3339; --grid:#26292e;
  --text-1:#f2f3f5; --text-2:#a9adb6; --text-3:#8a8e97;
  --ok-fg:#5cd08a;   --ok-bg:#10281c;   --ok-ln:#2f7d52;
  --warn-fg:#e8b53d; --warn-bg:#2a2210; --warn-ln:#8a6c1c;
  --bad-fg:#f08a8a;  --bad-bg:#2c1517;  --bad-ln:#8e3a3d;
  --info-fg:#7ab4ec; --info-bg:#0f2237; --info-ln:#3a6c9e;
  --muted-fg:#a9adb6;--muted-bg:#212429;--muted-ln:#5b5f66;
  --accent:#7ab4ec;  --focus:#7ab4ec;

body{ background:var(--page); color:var(--text-1); font:var(--t-md)/1.45 var(--font); }
```

`body` gets an explicit background token: a transparent body borrows whatever ground the host
paints, which is how a dark-mode reader ends up with black text on black.

**Measured contrast.** WCAG 2.1 AA needs 4.5:1 for body text and 3:1 for large text and UI component
boundaries. Computed with the sRGB relative-luminance formula.

| Pair | Light | Dark | AA body (4.5) | AAA body (7.0) |
|---|---|---|---|---|
| `--text-1` on `--page` | 17.87 | 17.27 | pass | pass |
| `--text-1` on `--surface-1` | 19.68 | 15.44 | pass | pass |
| `--text-2` on `--surface-1` | 7.94 | 7.97 | pass | pass |
| `--text-3` on `--surface-1` | 5.17 | 5.46 | pass | fail |
| `--ok-fg` on `--ok-bg` | 5.79 | 8.08 | pass | dark only |
| `--ok-fg` on `--surface-1` | 6.57 | 9.26 | pass | dark only |
| `--warn-fg` on `--warn-bg` | 6.21 | 8.32 | pass | dark only |
| `--warn-fg` on `--surface-1` | 6.92 | 9.48 | pass | dark only |
| `--bad-fg` on `--bad-bg` | 6.56 | 7.10 | pass | dark only |
| `--bad-fg` on `--surface-1` | 7.79 | 7.43 | pass | pass |
| `--info-fg` on `--info-bg` | 7.09 | 7.34 | pass | pass |
| `--info-fg` on `--surface-1` | 8.25 | 8.17 | pass | pass |
| `--muted-fg` on `--muted-bg` | 7.65 | 6.92 | pass | light only |
| `--focus` on `--page` | 6.94 | 8.44 | pass (3:1 needed) | — |

`--text-3` is the one pair that clears AA but not AAA, and it is confined to provenance metadata —
`checked_at` stamps, row ids, "captured 23 Aug" lines. Nothing a decision rests on uses it.

**Colour is never the only channel.** Every badge carries a word (`VERIFIED`, `NOT VERIFIED`, `DO NOT
CONTACT`), every findings fieldset a legend, every policy row starts with `PASS` / `WARN` /
`BLOCK` in text, every score badge carries its number. The app is usable in greyscale and by a
red-green colour-blind reader — which matters most for the two states whose confusion is most
expensive: green `VERIFIED` and red `REJECTED`.

**Theme control.** A three-state `Auto / Light / Dark` control in the header. `Auto` sets no
attribute; the others stamp `data-theme` on `<html>`. The choice persists in `localStorage` under
`radar:theme`, read inside `try/catch`, applied by an inline script in `<head>` before first paint
so a dark-theme reader gets no white flash. The page renders correctly when the read throws.

### 15.17.4 Badge components

```css
.badge{
  display:inline-flex; align-items:center; gap:var(--s-1);
  padding:2px var(--s-2); border-radius:var(--r-pill);
  font-size:var(--t-xs); font-weight:600; letter-spacing:.02em; white-space:nowrap;
  color:var(--f); background:var(--b);
  border:1px solid color-mix(in srgb, var(--f) 28%, transparent);
}
.badge.ok   { --f:var(--ok-fg);    --b:var(--ok-bg);    }
.badge.warn { --f:var(--warn-fg);  --b:var(--warn-bg);  }
.badge.bad  { --f:var(--bad-fg);   --b:var(--bad-bg);   }
.badge.info { --f:var(--info-fg);  --b:var(--info-bg);  }
.badge.mute { --f:var(--muted-fg); --b:var(--muted-bg); }
```

Four badge families, exactly as `03` §3.9.4 defines them. The live app adds no fifth.

| Family | Value -> class, label, `title` |
|---|---|
| **Score** | `>=80` -> `ok`, the number, `HIGH: 80-100`; `60-79` -> `warn`; `<60` -> `mute`; NULL -> `mute`, `—`, `not scored yet` |
| **Confidence** | `HIGH` -> `ok`; `MEDIUM` -> `warn`; `LOW` -> `mute`; none -> `mute`, `—`. `title` carries `confidence 64%` from `confidence_pct` |
| **Verification** | `CONTACT_READY` -> `ok`, `READY`; `VERIFIED` -> `ok`; `NEEDS_VERIFICATION` -> `warn`, `NOT VERIFIED`; `AI_RESEARCHED` -> `warn`; `REJECTED` -> `bad` with the reason code in `title`; `SKIPPED` -> `mute` with `businesses.skip_reason` |
| **Outreach** | suppressed -> `bad`, `DO NOT CONTACT`; interested -> `ok`; responded -> `info`; `BOUNCED`/`FAILED`/`POLICY_BLOCKED` -> `bad` with `failure_code`; `DELIVERED` -> `ok`; `SENT`/`QUEUED` -> `info`; none -> `mute`, `NOT CONTACTED` |

Two ordering rules carry across from `03` §3.9.5 and must not drift. The outreach badge is chosen
by
**severity, not recency** — a business that opted out after a delivered message reads `DO NOT
CONTACT`, not `DELIVERED`. And a `LOW` score is grey, not red: a low opportunity score is not a
compliance problem, and red means compliance problem everywhere else here.

Two badges are live-app-only additions inside the same five classes: `PAUSED` (`warn`, on a
quota-paused campaign) and `QUOTA EXHAUSTED` (`bad`, in the header strip). Neither adds a colour.

### 15.17.5 Table conventions

| Convention | Rule |
|---|---|
| Alignment | text left, numbers right with `tabular-nums`, badges left, actions right |
| Header | `<th scope="col">`, sticky at `top: 0` inside `.tablewrap`, `--surface-2` background so rows do not show through |
| Row identity | the business cell is `<th scope="row">`, so a screen reader announces the business before every cell value |
| Sorting | click to sort, click again to reverse, shift-click for a secondary key; `aria-sort` maintained; unscored rows always sink to the bottom regardless of direction |
| Zebra | none. Row separation is a 1 px `--grid` bottom border. Zebra plus status tinting gives four background colours per table and none of them mean anything |
| Row tint | only two: `--bad-bg` at 40% for a suppressed row, `--warn-bg` at 40% for a stale verification. Both also carry a badge |
| Hover | `--surface-2`, and only where the row is clickable |
| Overflow | wide tables scroll inside `.tablewrap{ overflow-x:auto }`; `body{ overflow-x:hidden }`. The page never scrolls horizontally |
| Truncation | one line with `text-overflow: ellipsis` and the full value in `title`; never a silent cut |
| Empty cell | `—` in `--muted-fg` with `aria-label="no data"`, never blank and never `0` |
| Every `<td>` | carries `data-label="<column name>"` so the sub-720 px card layout is generated by CSS from the same markup |

### 15.17.6 Empty states

An empty state names what is missing, why, and the one action that changes it. It never renders a
zero and never renders an illustration.

| Screen | Condition | What is shown |
|---|---|---|
| `/campaigns` | none | `No campaigns yet. A campaign is a set of cities and filters; research runs city by city.` + `[ + New campaign ]` |
| Campaign report | not started | `This campaign has not run yet.` + `[ START RESEARCH ]` |
| Campaign report | ran, found nothing in a city | the city card renders zeros and the tab says `We searched Shirpur and found 0 businesses matching the filters. OpenStreetMap coverage in smaller cities is thin; consider widening the categories or the size filter.` |
| Business detail, findings | run `COMPLETE`, no findings | each fieldset renders empty with `No observed findings.` / `No inferences drawn.` / `Nothing was recorded as unknown.` |
| Business detail, contacts | none | `No contact found. Outreach needs one confirmed contact.` + `[ Add a contact ]` |
| Verification queue | empty | `Nothing is waiting for you. 21 businesses are still being researched.` |
| Outreach workspace | no selection | `Nothing selected. Select verified businesses from a campaign report first.` + link |
| Preview panel 9 | no prior contact | `No previous contact.` — itself information, so a sentence, not an empty box |
| `/handoffs` | none open | `No open handoffs. This is the queue that pages you; empty is the normal state.` |
| `/suppressions` | none | `No do-not-contact records.` |
| Comparison tables | no rows in scope | the row renders with zeros and `—`, never omitted |
| Daily report | no activity | `No businesses were discovered on 26 Aug 2026.` — never suppressed |

### 15.17.7 Loading states

| Situation | Rendering |
|---|---|
| Full page | server-rendered; no client-side page loader. Flask on localhost answers in single-digit milliseconds and a spinner would flash |
| Table body over 400 rows | skeleton rows at the true row height (`03` §3.13.3's chunked hydration), so nothing reflows when they fill |
| Live progress poll | no spinner. The `as of HH:MM:SS` stamp is the indicator; it goes `--text-3` while a request is in flight |
| Async batch (drafting) | a determinate line: `Drafting 4 of 15 - about 90s remaining at the current rate`, from the batch counts and the quota's RPM. Never an indeterminate spinner: on a rate-limited free tier the wait is knowable, so showing it as unknowable is a choice to be unhelpful |
| A control that fired a write | it shows `Working...`, keeps its width, and is `aria-busy="true"`; it is never replaced by a spinner that changes the layout |
| SSE reconnecting | one header line, `Reconnecting to live updates...`, which then disappears. The poll fallback continues underneath |

Nothing animates for longer than 200 ms, and every transition is inside `@media
(prefers-reduced-motion: no-preference)`.

### 15.17.8 Error states

Four kinds. The rule is that an error says what failed, what it means for the work in front of the
operator, and what to do next.

| Kind | Rendering | Example |
|---|---|---|
| **Field validation** | inline under the field, `--bad-fg`, `aria-describedby`, focus moves to the first bad field | `12 cities is the limit. Each city is a separate Overpass sweep.` |
| **Blocked action** | one sentence beside the disabled control, from `BLOCK_REASON` (§15.18.3) | `Verified, but no confirmed contact yet.` |
| **Request failure** | an inline banner at the top of the affected panel, not a toast; the panel keeps its last good content | `Could not reach the server. The figures below are from 11:42:08 and may be stale.` + `[ Retry ]` |
| **Job / integration failure** | a persistent row in the affected screen with the failure class and `job_runs` id | `Research failed for 1 business: Overpass returned 429 three times. job_01JSAMPLE... [ retry ]` |

Cases that recur enough to be specified once:

| Condition | Sentence |
|---|---|
| Gemini 429 mid-campaign | `Research paused: today's Gemini request quota is used up. 52 businesses are still queued and nothing is lost.` |
| Gemini 5xx | `Gemini returned an error. This job will retry three times, then move to the dead letter list in Settings > Jobs.` |
| Gmail SMTP auth failure | `Gmail rejected the App Password. Nothing was sent. Check Settings > Channels; App Passwords need 2-Step Verification on the account.` |
| IMAP poll failing | `Replies have not been read since 26 Aug 07:35. Inbound is a poll on this deployment, so a failing poll means replies are invisible, not absent.` |
| Overpass unreachable | `OpenStreetMap's Overpass API did not answer. Discovery for Nashik is incomplete: 62 found so far.` |
| DB write conflict | `Somebody else changed this row while you had it open. Reload to see the current state.` (a single-operator tool still has two tabs) |
| Preview token stale | `Something changed while this was open. Read the policy panel again.` |
| `brief_json` corrupt | `Brief unavailable - rebuild.` with the scalar columns still rendered |

No `alert()`, no toast that disappears before it is read, and no error that says only `Something
went wrong.` An error the operator cannot act on is a log line that escaped onto the screen.

### 15.17.9 Responsive breakpoints

Four, matching `03` §3.14 so the live grid and the exported report behave identically.

| Breakpoint | Layout |
|---|---|
| `>= 1280 px` | full 14-column table; KPI row 6 across; city cards 4 across; verification two columns with a sticky checklist |
| `1024 - 1279 px` | KPI row 4 across; city cards 3 across; table scrolls inside `.tablewrap`; verification stays two-column with a narrower evidence pane |
| `720 - 1023 px` | KPI row 3 across; Digital Maturity, Category and Discovered collapse into the Business cell's sub-line; **verification becomes one column**, checklist below evidence, each check keeping its zone anchor |
| `< 720 px` | the table becomes cards, one `<article>` per business with the same data attributes so every filter and sort keeps working; handoffs use the §15.12 phone layout; the selection tray becomes a two-line sticky bar |

```css
.tablewrap{ overflow-x:auto; }
body{ overflow-x:hidden; }

@media (max-width: 719px){
  .btable thead{ display:none; }
  .btable tr{ display:block; border:1px solid var(--rule);
              border-radius:var(--r); margin:var(--s-2) 0; }
  .btable td{ display:flex; justify-content:space-between; gap:var(--s-3); border:0; }
  .btable td::before{ content:attr(data-label); color:var(--text-2); font-size:var(--t-xs); }
}
```

There is no second mobile template anywhere in the app. Every size is `rem`, a step from the
scale, or `%`; the layout holds at 200% browser zoom because nothing is absolutely positioned.

Accessibility requirements, all testable and all shared with `03` §3.14: `role="tablist"` with
arrow / `Home` / `End` navigation on both tab strips; `<caption>` on every table naming its scope;
`aria-sort` on the active header; visually-hidden text plus `aria-describedby` for every disabled
control's reason; `<div role="status" aria-live="polite">` for filter result counts and the quota
strip; `<button aria-expanded aria-controls>` for every expandable panel, with focus moving in and
back out; `:focus-visible{ outline:2px solid var(--focus); outline-offset:2px; }` never removed.

---

## 15.18 The interaction rules that encode the safety model

### 15.18.1 The SEND control is absent, not disabled (§19, §45)

§19: *"The Send button must NOT exist on the raw AI research result."* Absent means absent at
every layer, and it is checked rather than intended.

| Layer | What is absent |
|---|---|
| Templates | no macro renders a send control outside `templates/outreach/confirm_dialog.html`. `test_send_control_is_local` greps `templates/` for `send`, `transmit`, `dispatch` in a `<button>`, `<a class="act">` or `<form>` and fails on any hit outside that file |
| Report templates | no `<form>` element exists anywhere under `templates/report/`. `test_report_has_no_forms` asserts it |
| Routes | there is no `POST /api/v1/businesses/<id>/send` reachable without an `approval_id`; `send_message()` takes `approval_id: str` — not `str \| None` — and the type is the gate (`_CONTEXT.md` invariant 1) |
| Labels | `FORBIDDEN_BUTTON_TEXT` (§15.10) is grepped across every template |
| Verification | no "verify all" / "approve all" / "approve selected" control at any layer (`04` §4.7.4), enforced by `test_no_bulk_verify_control` |
| Handoff | no send control on `/handoffs/<id>`; the recommended action is copyable text and a `mailto:` link with no body |

Absence beats disablement for the reason `04` §4.7.4 gives about bulk verify: a greyed-out control
that becomes enabled under some condition is a permanent invitation, and the day the condition is
met by accident is the day something is sent that nobody decided to send. The one place a send
control exists is inside the §28 dialog, behind the seven displayed panels, an empty
`confirm_blockers()` list and the typed word.

### 15.18.2 Typed confirmation for irreversible actions

Five actions cannot be undone by the app. Each requires an exact word typed into a field next to
the control; the button stays disabled until the field matches exactly, case-sensitively.

| Action | Screen | Typed word | Why it is irreversible |
|---|---|---|---|
| Send a message | §15.10 confirm dialog | `SEND` | it reaches a stranger's inbox and cannot be recalled |
| Add a suppression | §15.5, §15.13 | `SUPPRESS` | `_CONTEXT.md` invariant 3: the app has no code that clears one |
| Cancel a running campaign | §15.3.2 | `CANCEL` | in-flight jobs are cancelled and partial research is not resumed |
| Revive a dead job | Settings > Jobs | the reason text, min 10 chars | it re-runs something that already failed its retries; `13` §13.16 requires a reason |
| Execute a DPDP erasure | Settings, `OWNER` only | `ERASE` | it destroys contact rows and redacts audit detail permanently |

Rules for the pattern:

- The word is written on screen immediately above the field. It is never guessed at.
- The field is `autocomplete="off"`, `spellcheck="false"`, and is **not** pre-filled.
- The sentence above it names the consequence in one line: `This send cannot be recalled.` / `This
  cannot be removed from the app afterwards.`
- The server checks nothing about the typed word — it is a UI speed bump, not a security control, and
  it is not treated as one. What the server checks is the approval record, the CHECK constraints and
  the role.
- Nothing else in the app uses typed confirmation. A pattern used for six things is a pattern that
  gets typed without reading.

### 15.18.3 Every blocked action explains itself, in one sentence, next to the control

The sentence comes from the map `03-html-report.md` §3.7.1 defines and `05-outreach-workflow.md`
supplies the gate codes for. It is imported from one module, `radar/policy.py`, by the report
generator, the live grid, the selection tray, the outreach workspace and the preview screen.

```python
BLOCK_REASON = {
    "A_SUPPRESSED":              "Do not contact: an opt-out or suppression is recorded.",
    "D_HUMAN_OWNED":             "This is a live lead - the machine stops here and you take it.",
    "D_VERIFICATION_REVOKED":    "You rejected or skipped this business.",
    "D_NOT_VERIFIED":            "This business still needs your verification.",
    "D_VERIFICATION_STALE":      "The verification has expired - re-verify before selecting.",
    "E_CONTACT_MISSING":         "Verified, but no confirmed contact yet.",
    "F_IN_FLIGHT":               "A message for this business is already awaiting approval.",
    "G_STOP_AFTER_REJECTION":    "This business replied that it is not interested.",
    "G_MAX_ATTEMPTS":            "The maximum number of outreach attempts has been reached.",
    "G_MAX_FOLLOWUPS":           "The maximum number of follow-ups has been reached.",
    "G_MIN_DAYS":                "Contacted too recently - the minimum gap has not elapsed.",
}
```

The three UI rules that go with it:

1. **The sentence names the missing precondition, never a generic refusal.** "This business still
   needs your verification" tells the operator what to click. "Not eligible" makes him go and find
   out, and after the third time he stops asking.
2. **It is rendered adjacent to the control, not in a tooltip alone.** A `title` is invisible to
   keyboard and touch users and to anybody who does not hover; disabled inputs are not focusable at
   all. So the reason is also visually-hidden text referenced by `aria-describedby`, with a focusable
   `i` affordance beside the control.
3. **Where a sentence can be specific, it is specialised at render time.** `G_MIN_DAYS` renders as
   `Contacted 6 days ago; the minimum gap is 21 days.` from the actual dates. The map holds the
   generic form; the renderer specialises it where it has the numbers.

Three sentences do not come from this map because they are not eligibility gates: the quota
sentences (§15.16), the verification approve-ladder sentence (§15.6, quantified live) and the
claim-policy sentence (§15.9, which quotes the offending sentence). Each is specified in its own
section and each obeys the same three rules.

`test_block_reason_single_source` asserts that the map's keys equal the gate codes emitted by
`check_send_eligibility()` and that no template contains a hardcoded copy of any of the eleven
strings.

### 15.18.4 Two smaller rules from the same model

**Nothing writes on hover, focus or navigation.** Every state change is a click on a labelled
control. The one exception is the verification source-visit beacon (`04` §4.5.3), which records
that a link was opened; it is fire-and-forget, never blocks navigation, and changes no lifecycle
state.

**The operator can always see what the system thinks it knows.** Every screen showing a conclusion
shows the row ids behind it in `--mono` at `--t-xs`: `res_...`, `src_...`, `ver_...`, `opp_...`,
`apr_...`. That is provenance on screen at the cost of a small grey string per panel, and it is
what makes "why did it say that" answerable without opening the database.

---

## 15.19 What the templates make impossible

The safety rules above are worth only as much as their enforcement. One file,
`templates/outreach/confirm_dialog.html`, contains a send control; nothing else in `templates/`
does, and `static/tokens.css` is the same file the export inlines, so there is one palette in one
file with two consumers. Both facts are held by tests rather than by discipline:

| Test | Asserts |
|---|---|
| `test_send_control_is_local` | no send / transmit / dispatch control in any template outside `templates/outreach/confirm_dialog.html` |
| `test_report_has_no_forms` | zero `<form>` elements under `templates/report/` |
| `test_no_forbidden_send_labels` | no template contains any string in `FORBIDDEN_BUTTON_TEXT` |
| `test_no_bulk_verify_control` | no `verify-all`, `approve-all`, `approve_selected`, `verify_selected` in `templates/` |
| `test_confirmation_text_identical` | `CONFIRMATION_TEXT` == the rendered dialog string == `outreach_approvals.confirmation_text` |
| `test_block_reason_single_source` | `BLOCK_REASON` keys equal the gate codes from `check_send_eligibility()`; no template hardcodes a sentence |
| `test_one_palette` | every colour literal in `static/` and `templates/` is a `var(--token)`; the only hex literals live in `tokens.css` |
| `test_contrast_ratios` | recomputes every pair in §15.17.3 from `tokens.css`; fails below 4.5:1 (3:1 for `--focus`) |
| `test_findings_three_fieldsets` | business detail and verification render exactly three `<fieldset>` elements for findings, each with a `<legend>`, even when a group is empty |
| `test_typed_confirmation_required` | each §15.18.2 action is refused without its exact word |
| `test_every_disabled_control_has_a_reason` | every element with `disabled` or `aria-disabled` has an adjacent reason node referenced by `aria-describedby` |
| `test_no_zero_for_missing` | a campaign with no handoffs renders `—` for Demos/Proposals/Won, not `0` |
| `test_quota_numbers_from_config` | no free-tier limit appears as a literal in a template |
| `test_mobile_cards_use_same_markup` | every `<td>` carries `data-label`; there is no second mobile template |
| `test_theme_survives_storage_failure` | with `localStorage` throwing, every page renders with the Auto palette and no exception |

---

## Open questions

1. **Five UI routes are extensions.** `_CONTEXT.md` §6 lists eight; this document adds
   `/campaigns/new`, `/handoffs/<id>`, `/suppressions`, `/reports/daily/<YYYY-MM-DD>` and `/compare`.
   `03-html-report.md` independently proposes the daily route and `10-human-handoff.md` already
   renders `/handoffs/<handoff_id>`. They are additions, not substitutions; `13-api-endpoints.md`
   should ratify the set. `/compare` is the only arguably optional one — §37 and §38 already render
   inside the campaign report, and a cross-campaign view is a want, not a requirement.

2. **`GET /api/v1/quota` does not exist yet.** §15.16 needs it and `13-api-endpoints.md` has no such
   route. Proposed shape: `{"llm": {"day": {"used": 231, "limit": 250, "resets_at": "..."},
   "minute": {"used": 6, "limit": 10}}, "email": {"day": {"used": 7, "limit": 25}},
   "paused_campaigns": ["cmp_..."]}`, VIEWER role, exempt from rate limiting as `/progress` is. It
   reads `spend_ledger` and `rate_buckets` and adds no table.

3. ~~**`spend_ledger` is still money-shaped.**~~ **Settled.** `14-background-jobs.md` §14.3.5 now
   records quota rather than money. `cost_micros_inr` is renamed `quota_units` — `INTEGER NOT NULL
   CHECK (quota_units >= 0)`, the requests charged against the day's ceiling, one per Gemini call —
   `units` carries the token count beside it, and `v_spend_today` returns `total_requests`,
   `llm_requests`, `email_requests`, `llm_tokens` and `entries` instead of a rupee sum. §15.16 reads
   those columns. The `purpose` discriminator this entry asked for did not become a column: `14`
   keeps it in the row's `detail` JSON, which is where §15.16's "What used it today" region reads
   `RESEARCH` / `DRAFT` / `CLASSIFY` from.

4. ~~**Three stale references in already-written documents.**~~ **Settled — all three are corrected
   at source.** `10-human-handoff.md`'s header now cites `15-ui-wireframe.md` for shared components;
   the deliverable-12 / document-15 numbering is what produced the original slip, so the mismatch is
   worth remembering rather than just fixing. `03-html-report.md` §3.4.8 now reads
   `handoffs.won_value_inr`, the name `01-data-model.md` §1.2.4 ruling D6 binds, and records the
   superseded spelling in its §3.3.1 rename table so nothing downstream re-learns it.
   `06-message-engine.md` names `gemini-2.5-flash` throughout, per `_CONTEXT.md` §2 — the
   `claude-opus-5` still visible in its §6.13 is that section's "changed for the free stack" note,
   not a live call. This document already used the arbiter's names and needed no edit.

5. **The phone can only reach the app on the LAN.** §15.12 designs a phone-first handoff screen, but
   the app is bound to `127.0.0.1` and there is no public hostname. In practice the phone reaches it
   only when both devices are on the same network and waitress is bound to the LAN interface instead,
   which widens the exposure `12-security-model.md` has to cover. The alternative — Telegram-only
   handoffs with no mobile web view — is workable because the alert already carries the whole §34
   brief, but it costs the collapsible research basis and the acknowledge/close controls. That is a
   deployment decision, not a UI one, and it needs settling with `12-security-model.md`.

6. **Whether the verification approve control should be absent rather than disabled.** §15.6 makes it
   the single deliberate exception to absent-not-disabled, on the grounds that it is the action the
   screen exists for. The counter-argument is that a disabled approve button with a live countdown is
   precisely the "permanent invitation" §4.7.4 warns about. An alternative — render no approve control
   until every precondition passes, with the ladder shown as a checklist that completes — was rejected
   as more disorienting, but it is a real option and it is Sagar's call.

7. **`—` versus `0` on the statistics strip is a judgement, not a rule.** §15.3.2 renders Demos,
   Proposals and Won as `—` when no handoff exists, following `03` §3.5. But `Sent: 0` in a campaign
   with approvals and no sends is arguably also "not that far" rather than "we sent nothing". The line
   drawn here is: a stage with no upstream rows renders `—`; a stage with upstream rows and no outcome
   renders `0`. It is defensible and it is not obviously right.
