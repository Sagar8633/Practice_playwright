# 13. API endpoints

This document is the control surface of `business_radar`: every HTTP route the system exposes, who
may call it, what it accepts, what it returns, what it refuses, and which `audit_log` action it
writes. Ten documents named endpoints before this one existed and several named the same thing
differently; §13.1 consolidates them, picks one name per operation, and records every rename in
`## Corrections to other documents` for a later repair pass. It settles the conventions that were
never settled anywhere — the error envelope, cursor pagination, the sort and filter grammar, the
`Idempotency-Key` contract, the HTTP rate-limit buckets §47 asks for, and the RBAC matrix
`12-security-model.md` will build on. It specifies `POST /api/v1/outreach/messages/<message_id>/send`
in full, because that is the one request in the system that can put a message in front of a stranger,
and it specifies at equal length **the endpoints that deliberately do not exist**: nothing sends
without an approval row, nothing bulk-approves, nothing clears a suppression, nothing raises
`automation_mode` above `HUMAN_APPROVAL`, and nothing hands back a contact list without leaving a
row behind. The negative space is the deliverable as much as the routes are.

Two whole groups moved into that negative space when `_CONTEXT.md` §2 settled the deploy target as
waitress on `127.0.0.1` with no public hostname. **There are no webhook endpoints** — every inbound
path is `poll_inbox` over IMAP (§13.19) — and **there is no unsubscribe route**: unsubscribe is a
`mailto:` per RFC 2369, which §13.20 explains at length because a first-contact commercial email
whose opt-out link resolves to nothing is the single most damaging defect this system could ship.

---

## 13.1 What this consolidates

### 13.1.1 Provenance map

Every endpoint below already existed in another document, was implied by one, or is named here for
the first time. This table is the index of where each group came from.

| Group | Source documents | This document does |
|---|---|---|
| campaigns | `14-background-jobs.md` §14.8.1, `03-html-report.md` §3.16 | consolidates; adds `start`, `stats`, `archive` |
| research | `02-research-pipeline.md` §2.2.3, `14-background-jobs.md` §14.8.2-3, §14.11 | consolidates; adds per-business research read and re-research |
| businesses | `03-html-report.md` §3.6.2 (the §39 eleven filters), `04-verification-workflow.md` §4.12.1 | turns the export's client-side filter set into query parameters |
| verification | `04-verification-workflow.md` §4.12.1 | consolidates; disambiguates two id types on one path |
| selection | `05-outreach-workflow.md` §5.4.3, §5.4.4 | verbatim |
| outreach | `05-outreach-workflow.md` §5.21, `06-message-engine.md` §6.11 / §6.12.3, `08-whatsapp-integration.md` §8.11 | renames three routes onto one scheme |
| eligibility | `05-outreach-workflow.md` §5.8, §5.9.12 | gives the gate engine its HTTP face |
| responses | `08-whatsapp-integration.md` §8.10.5, `01-data-model.md` §1.9 | consolidates; adds list, get, reclassify |
| handoffs | `10-human-handoff.md` §10.13 | verbatim |
| suppressions | `05-outreach-workflow.md` §5.3.2 | adds the list endpoint and states the missing DELETE |
| reports / exports | `03-html-report.md` §3.16, `11-audit-architecture.md` §11.11.6 | consolidates two archive listings into one |
| jobs | `14-background-jobs.md` §14.12.2 | verbatim |
| settings | `04-verification-workflow.md` §4.9.1, `05-outreach-workflow.md` §5.3.1, `08-whatsapp-integration.md` §8.11 | replaces one untyped `POST /api/v1/settings` with typed sub-resources |
| auth | `01-data-model.md` §1.10, `11-audit-architecture.md` §11.6.13 | named here for the first time |
| inbound (was: webhooks) | `05-outreach-workflow.md` §5.21, `08-whatsapp-integration.md` §8.9, `14-background-jobs.md` §14.8 | **deletes them.** `_CONTEXT.md` §2 settles that nothing on the public internet can reach `127.0.0.1`, so no inbound HTTP route exists. §13.19 points at `07-email-integration.md` §7.8's IMAP poll and adds the two operator triage routes; §13.21 records the absent paths |
| unsubscribe | `05-outreach-workflow.md` §5.9.10, `07-email-integration.md` §7.7 | **deletes the `/u/...` routes.** There is no public HTTPS endpoint, so unsubscribe is `mailto:` per RFC 2369 and is ingested by the poller. §13.20 |
| quota, coverage, inbound triage, session control | `15-ui-wireframe.md` §15.16, `02-research-pipeline.md` Open question 6, `07-email-integration.md` §7.8.10, `12-security-model.md` §12.4.4 | named here for the first time: `GET /api/v1/quota`, `GET /api/v1/campaigns/<campaign_id>/coverage`, `POST /api/v1/inbound/<inb_id>/attach` and `/ignore`, `POST /api/v1/auth/unlock`, `POST /api/v1/auth/revoke-all` |

### 13.1.2 The four naming rules the consolidation applied

Where two documents disagreed, the winner was chosen by these rules in order, not by document age.

| # | Rule | Consequence |
|---|---|---|
| N1 | **The path names the entity whose row changes.** | `POST /api/v1/outreach/messages/<message_id>/send`, not `/outreach/drafts/<draft_id>/approve`: the row that moves `PENDING_APPROVAL -> APPROVED -> QUEUED` is the `outreach_messages` row |
| N2 | **Collections are plural, always.** | `/api/v1/businesses/<business_id>/sources`, not `/api/v1/business/<id>/sources` |
| N3 | **One path parameter, one id type.** | `/api/v1/verifications/<verification_id>` is always a `ver_`; the business-scoped verification read moves to `/api/v1/businesses/<business_id>/verification` |
| N4 | **A verb suffix only where REST has no shape for it.** | `/send`, `/cancel`, `/submit`, `/acknowledge`, `/close`, `/retry` survive; `/get`, `/list`, `/update` do not exist |

---

## 13.2 Conventions

### 13.2.1 Prefix, versioning, media types

| Property | Value |
|---|---|
| API prefix | `/api/v1` (`_CONTEXT.md` §6). UI routes carry no prefix |
| Versioning | Path-based. `v2` would be a second blueprint, not a header negotiation. A single-operator tool does not need content negotiation, and a header-versioned API is one a browser cannot bookmark |
| Request media type | `application/json; charset=utf-8` for every body. `multipart/form-data` appears nowhere — nothing in v1 uploads a file |
| Response media type | `application/json; charset=utf-8`, except the export streams (`GET /api/v1/report_exports/<rex_id>`), the SSE stream, and the two HTML surfaces (`?format=html`) |
| Unknown fields | Rejected, not ignored. A body carrying a key the schema does not define returns `422 UNPROCESSABLE` naming the key. A silently ignored `"channel": "WHATSAPP"` on a send is how a message goes out on the wrong channel |
| Trailing slash | Not accepted; `strict_slashes=True` |
| Timestamps | ISO-8601 UTC, `YYYY-MM-DDTHH:MM:SSZ`, matching `01-data-model.md` §1.1.2 exactly. Dates are `YYYY-MM-DD`; a date that is IST-relative carries `_ist` in the field name |
| Money | Integer whole rupees in a field ending `_inr` |
| Nulls | A metric with no data is `null`, never `0` (`_CONTEXT.md` invariant 5). The UI renders `null` as an em dash |

### 13.2.2 Authentication

Three authenticators plus one opt-in fourth, registered as Flask blueprints. Which blueprint a route
lives on is the security boundary, not a decorator on the view.

| Blueprint | Authenticator | Used by | Cannot do |
|---|---|---|---|
| `bp_session` | Signed session cookie (`HttpOnly`, `Secure`, `SameSite=Lax`) plus a CSRF token on every unsafe method | Every human route | — |
| `bp_token` | `Authorization: Bearer rdt_<32 hex>`, stored hashed, read-only scopes in v1 | Read endpoints for scripting and monitoring | Reach any route that writes an `outreach_approvals` row, a `verifications` verdict, or a `contact_policy` change. It is not registered on those routes at all |
| `bp_callback` | A shared-secret header compared with `hmac.compare_digest` over the raw body before any parsing (§13.13.2) | **One route: the Telegram inline-button callback**, and only when `notify.telegram.mode: webhook`, which is off by default and needs a public host this deploy target does not have | Read anything. It writes one row and enqueues one job |
| `bp_public` | None | `GET /api/v1/health` | Everything else |

**`bp_webhook` is gone.** An earlier revision of this document registered a fourth blueprint carrying
`POST /api/v1/webhooks/<provider>` for `postmark`, `ses`, `resend` and `whatsapp`. `_CONTEXT.md` §2
settles the deploy target as waitress on `127.0.0.1` with no public hostname: nothing on the public
internet can reach this process, so those routes were unreachable code with a security surface.
`12-security-model.md` §12.9 records the same correction ("`bp_webhook` does not exist on this
stack"). §13.19 replaces it with the IMAP poll, and §13.21 keeps the paths absent by test.

Two rules that are structural rather than conventional:

1. **`outreach_approvals.session_auth_method` has no legal value a token can produce.** Its `CHECK`
   admits only `PASSWORD` and `PASSWORD_TOTP` (`05-outreach-workflow.md` §5.3.6). The API-token
   authenticator mints no session, so even if `/send` were mistakenly registered on `bp_token` the
   insert would fail on a database constraint. Two layers, because one of them is a routing decision
   that a refactor can undo.
2. **`bp_callback` verifies the secret token before any parsing**, and binds
   `Actor(kind="ANONYMOUS")` until it passes, then `Actor(kind="PROVIDER", label="telegram")`
   (`11-audit-architecture.md` §11.16.4). It exists for exactly one opt-in route and registers no
   other; if `notify.telegram.mode` is left at its default `getUpdates`, the blueprint is not
   registered at all and the app has three.

### 13.2.3 CSRF

Every unsafe method (`POST`, `PUT`, `PATCH`, `DELETE`) on `bp_session` requires an `X-CSRF-Token`
header matching the session's token. `bp_token` is exempt because a bearer header is not sent by a
browser cross-site. `bp_callback` and `bp_public` are exempt: the first is protected by its secret
token, the second has nothing worth forging on a `GET` that returns no business data.

Missing or wrong token is `403 CSRF_INVALID`. Deliberately not `401`: the session is fine, the
request is not.

### 13.2.4 The error envelope

One shape, every error, every blueprint.

```json
{
  "error": {
    "code": "BLOCKED",
    "message": "It has been 9 days since the last message to ABC Hospital (SAMPLE); your minimum is 21.",
    "detail": {},
    "field_errors": [],
    "request_id": "req_01JBSAMPLE0000000000000001",
    "doc": "13-api-endpoints.md#1311-post-apiv1outreachmessagesmessage_idsend"
  }
}
```

| Field | Rule |
|---|---|
| `code` | `SCREAMING_SNAKE`, stable, greppable, never localised. The client switches on this and on nothing else |
| `message` | **One sentence, addressed to Sagar, renderable verbatim in the UI.** Not a stack trace, not a field path, not "an error occurred". For a blocked send this is `Eligibility.blocking_sentence` unchanged, which is why `05-outreach-workflow.md` §5.9.1 spends a whole table writing those sentences |
| `detail` | Object. Code-specific structured data — the numbers behind the sentence. Empty object when there are none, never `null` |
| `field_errors` | Array of `{"field": "channel", "code": "INVALID_ENUM", "message": "..."}`. Empty for non-validation errors |
| `request_id` | Always present, always equal to the `X-Request-Id` response header, always equal to `audit_log.request_id` for any row this request wrote (`11-audit-architecture.md` §11.16.4). A screenshot of an error and the audit rows behind it join on this string |
| `doc` | Anchor into this file. Optional; present for the codes a developer hits first |

There is no top-level `errors[]` array and no partial success at HTTP level. Endpoints that
genuinely process a list — `POST /api/v1/selections`, `POST /api/v1/jobs/retry-batch` — return
`200` with `created[]` and `rejected[]` **inside the success body**, because "eleven of fifteen
worked" is a result, not an error.

### 13.2.5 Status codes

| Code | Used for | Never used for |
|---|---|---|
| `200` | A read, or a write that changed nothing new (an idempotent replay) | — |
| `201` | A row was created; `Location` header set | Enqueued work |
| `202` | Work was enqueued; body carries `job_id` or `batch_id` | Anything already finished |
| `204` | A write with nothing to say (a visit beacon) | Any error |
| `302` | Only `GET /api/v1/messages/<message_id>/explain` -> the draft's explain URL | — |
| `400` | Malformed JSON, wrong types | A business-rule refusal |
| `401` | No session, no token, expired session | A role that is too low |
| `403` | Authenticated but not permitted; CSRF failure; `HUMAN_SESSION_REQUIRED` | A missing row |
| `404` | The row does not exist, or the caller may not know that it does | A row that exists but is in the wrong state |
| `409` | **The state of the world refuses.** Every eligibility block, every illegal transition, every stale token, every non-idempotent duplicate | Validation |
| `410` | An unsubscribe token whose message row has been erased | — |
| `422` | Schema-valid JSON that fails validation: unknown key, bad enum, missing required field | Malformed JSON (that is `400`) |
| `429` | Rate limit; carries `Retry-After` | A `contact_policy` daily cap — that is `409 BLOCKED` with gate `H_DAILY_CAP`, because it is a policy decision, not a throttle |
| `500` | Unhandled. Body carries `code: "INTERNAL"` and the `request_id`, nothing else | Anything the code anticipated |
| `503` | SQLite locked beyond `busy_timeout`, or the worker pool is down for a route that needs it | — |

The `409`-versus-`422` line matters more than it looks. `422` means "fix your request"; `409` means
"the request was fine, the world says no". Every gate refusal in `05-outreach-workflow.md` is the
second kind, and a UI that renders them as validation errors teaches Sagar to argue with the form
instead of reading the sentence.

### 13.2.6 Pagination, sorting, filtering

Applied identically by every list endpoint. Implemented once, in `radar/web/api/_list.py`.

**Pagination is keyset (cursor), not offset.**

| Parameter | Type | Default | Max | Notes |
|---|---|---|---|---|
| `limit` | int | 50 | 200 | `422 LIMIT_TOO_LARGE` above the max, never a silent clamp |
| `cursor` | opaque string | — | — | Base64url of `{"k": <last sort key>, "id": "<last id>"}`. Opaque means opaque: a client that decodes it and hand-builds one gets `422 CURSOR_INVALID` on the next schema change, which is the intended outcome |
| `count` | `none` \| `exact` | `none` | — | `exact` adds `page.total` at the cost of a second `COUNT(*)`. Off by default because the grid does not need it and 5,000 rows should not pay for it |

Every list response is enveloped:

```json
{
  "data": [ ],
  "page": {
    "limit": 50,
    "returned": 50,
    "has_more": true,
    "next_cursor": "eyJrIjo4NiwiaWQiOiJiaXpfMDFKQlNBTVBMRSJ9",
    "total": null
  }
}
```

Offset paging is absent on purpose: the business grid is sorted by a score that a background job
rewrites while Sagar is reading page 3, and an offset page silently drops or duplicates rows across
that write. A keyset cursor is stable under concurrent rescoring.

**Sorting.** `sort=<field>` ascending, `sort=-<field>` descending. Each endpoint publishes an
allow-list; anything else is `422 SORT_FIELD_NOT_ALLOWED` naming the permitted fields. Every sort is
tie-broken by `id ASC` so the keyset cursor is total. A sort on a nullable column puts nulls last in
both directions, because "unscored" is not "worst".

**Filtering.**

| Form | Grammar | SAMPLE |
|---|---|---|
| Enum set (OR within, AND across) | comma-separated | `industry=HEALTHCARE,EDUCATION` |
| Numeric range | `<field>_min`, `<field>_max`, both inclusive | `score_min=70&score_max=100` |
| Null policy for a range | explicit boolean, defaults to including nulls | `include_unscored=false` |
| Date range | `<field>_from`, `<field>_to`, `YYYY-MM-DD`, inclusive | `discovered_from=2026-08-01` |
| Boolean | `true` / `false` and nothing else; `1` / `yes` / `on` are `422` | `has_website=true` |
| Free text | `q=`, case-insensitive substring, no fuzzy matching | `q=hospital` |

The null policy is not decoration. `03-html-report.md` §3.6.2 makes the same point about its
client-side filters: a score range that silently drops the forty businesses whose score is `NULL` is
a filter that lies, and the only fix is to make the decision explicit in the query string.

### 13.2.7 Idempotency

Three mechanisms, used in different places for different reasons.

| Mechanism | Where | Behaviour |
|---|---|---|
| **Natural idempotency** | `POST /api/v1/verifications`, `POST /api/v1/selections`, `POST /api/v1/suppressions`, `POST /api/v1/inbound/<inb_id>/attach` | A unique index makes the second call a no-op returning the existing row with `200`, not `409`. Re-selecting a selected business is not an error |
| **Client `Idempotency-Key` header** | Every `POST` that creates a row and is not naturally idempotent | Client-generated (a UUID is fine), scoped to `(user_id, method, path)`, retained 24 h. A replay returns the **original response body and status** plus `Idempotency-Replayed: true`. A replay with a *different* body under the same key is `409 IDEMPOTENCY_KEY_REUSED` |
| **Server-minted nonce** | The send path only | `outreach_approvals.idempotency_key` (`cnf_...`) is generated when the preview renders and embedded in the confirm form (`05-outreach-workflow.md` §5.14). The client cannot choose it, so it cannot collide with a key from another workflow, and a double-clicked CONFIRM & SEND hits `ux_approvals_idem` and returns the first response with `"duplicate": true` |

The send path uses the third and not the second because a header a client controls is a header a
buggy client can omit. A nonce minted with the form is present or the request is refused.

### 13.2.8 Rate limits

Spec §47 requires rate limits. **This is the only layer that provides them.** There is no reverse
proxy in front: `_CONTEXT.md` §2 binds waitress to `127.0.0.1` on Sagar's laptop, and
`12-security-model.md` §12.8 accepts the in-process buckets as sufficient on that stack, because the
only reachable client is a browser on the same machine and these limits exist to stop a runaway local
script, not a distributed attacker.

Implementation: in-process token buckets in `radar/web/ratelimit.py`, keyed by `(bucket, principal)`
where principal is `users.id` for an authenticated request and the client IP (always `127.0.0.1` in
practice) for an anonymous one. In-process is honest for this deployment — there is exactly one
waitress process — and a restart resetting the buckets is acceptable.

| Bucket | Limit | Applies to | On exhaustion |
|---|---|---|---|
| `read` | 300 / min | every `GET` on `bp_session` and `bp_token` | `429`, `Retry-After: 1` |
| `write` | 60 / min | every unsafe method on `bp_session` | `429` |
| `llm` | 10 / min, 200 / day | `outreach/prepare`, `drafts/<id>/regenerate`, `businesses/<id>/research` | `429` with `detail.bucket = "llm"`. Not a cost control — there is no bill. It is the app-side reservation against Gemini's free-tier RPM/RPD ceiling (`_CONTEXT.md` §2), and it is reported by `GET /api/v1/quota` (§13.16.1) and `GET /api/v1/jobs/stats` |
| `send` | 6 / min | `/send`, `/record-manual`, `/whatsapp-link` | `429`. This is a *throttle*; the policy caps (`daily_send_cap`, `send_min_gap_seconds`) are gates and return `409` |
| `auth` | 10 / 15 min per IP **and** per `email_norm` | `POST /api/v1/auth/login` | `429`. Independent of `users.locked_until`, which is the account lockout and returns `401 ACCOUNT_LOCKED` |
| `export` | 6 / min | `POST /api/v1/report_exports`, `POST /api/v1/campaigns/<id>/report` | `429` |
| `callback` | 60 / min | `bp_callback` (the Telegram callback only, when it is registered at all) | `429` with no body. Telegram backs off on `429`, and a body would only slow the response |
| `public` | 30 / min per IP | `GET /api/v1/health` | `429` |

Headers on every rate-limited response: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`
(seconds), and `Retry-After` on a `429`.

Two exemptions, both deliberate. `GET /api/v1/campaigns/<id>/progress` is polled every two seconds
by design (`14-background-jobs.md` §14.11) and gets its own 60/min bucket;
`GET /api/v1/campaigns/<id>/events` is one SSE connection, capped at 4 concurrent per user.

### 13.2.9 Request context and audit binding

`radar/web/app.py::_bind_request_actor` (`11-audit-architecture.md` §11.16.4) runs before every
request and binds the actor that `audit.write()` will use. Consequences for this document:

- Every response carries `X-Request-Id`, echoed from the request header when present, minted as
  `req_<ULID>` otherwise.
- `audit_log.route` and `audit_log.http_method` are the values in the tables below, verbatim.
- A route whose **Audit action** column reads `—` writes no audit row. That is a claim, not an
  omission: reads are not audited, except where a read discloses contact values (§13.6.4) or a file
  (`REPORT_DOWNLOADED`).

### 13.2.10 Response headers

| Header | Where | Value |
|---|---|---|
| `X-Request-Id` | everywhere | `req_...` |
| `Cache-Control` | every `/api/v1` response | `no-store`. Contact data and eligibility verdicts must not sit in a proxy or a bfcache |
| `X-Content-Type-Options` | everywhere | `nosniff` |
| `Content-Disposition` | `report_exports` streams | `attachment; filename="..."` |
| `Content-Security-Policy` | `report_exports` HTML streams | `sandbox` (`03-html-report.md` §3.13) |
| `X-Content-SHA256`, `X-Data-SHA256` | `report_exports` streams | the two hashes from `11-audit-architecture.md` §11.11.2 |
| `RateLimit-*` | rate-limited routes | §13.2.8 |
| `Idempotency-Replayed` | replayed writes | `true` |

### 13.2.11 UI routes

`_CONTEXT.md` §6 lists eight canonical UI routes. `15-ui-wireframe.md` §15.1.1 proposes five more and
its Open question 1 asks this document to ratify them, since the route registry is where a path
becomes real. **Ratified: the canonical list is thirteen.** They carry no `/api/v1` prefix, render
Jinja2 templates, and every one of them is on `bp_session`.

| UI route | Renders | Wireframe | Status |
|---|---|---|---|
| `/campaigns` | Campaign list | `15` §15.3.1 | canonical (`_CONTEXT.md` §6) |
| `/campaigns/<campaign_id>` | Campaign dashboard and report view (§36, §3-§10) | `15` §15.3, §15.4 | canonical |
| `/business/<business_id>` | Business detail and research panel (§11-§14, §32) | `15` §15.5, §15.11 | canonical |
| `/verify/<business_id>` | The §15/§16 verification screen | `15` §15.6 | canonical |
| `/outreach` | Outreach workspace (§20) | `15` §15.8 | canonical |
| `/outreach/<draft_id>` | The §27 preview and the §28 confirm dialog | `15` §15.9, §15.10 | canonical |
| `/handoffs` | Handoff inbox (§34) | `15` §15.12.1 | canonical |
| `/settings` | Contact policy, channels, templates, quota, jobs tabs (§21, §22, §31, §46) | `15` §15.15, §15.16 | canonical |
| `/campaigns/new` | New campaign form (§1) | `15` §15.2 | **ratified here** |
| `/handoffs/<handoff_id>` | Handoff detail (§34) | `15` §15.12.2 | **ratified here** |
| `/suppressions` | The do-not-contact list (§30), read-only | `15` §15.13 | **ratified here** |
| `/reports/daily/<YYYY-MM-DD>` | The §43 daily report | `15` §15.14.3 | **ratified here**, also proposed by `03` §3.16 |
| `/compare` | City (§37) and industry (§38) comparison, cross-campaign | `15` §15.14 | **ratified here** |

Three rules that come with the ratification:

1. **A UI route renders; it does not decide.** Every one of the thirteen reads through the `/api/v1`
   endpoints in this document and holds no query of its own. The failure this prevents is a template
   that grows a `SELECT` and then a filter and then a second, subtly different eleven-filter grid.
2. **`/suppressions` has no control that clears anything.** It is a list and a `POST` form for adding
   one, matching §13.14 exactly. `_CONTEXT.md` invariant 3 is a routing decision here as much as it
   is a trigger in the schema.
3. **There is no `/jobs`, no `/audit` and no `/quota` UI route.** The jobs console and the quota panel
   are tabs of `/settings` (§13.16, §13.16.1), and raw audit rows are OWNER-only JSON. Each of those
   would be a fourteenth route whose only content is a table somebody already has a tab for.

`/compare` is the one a reviewer may reasonably cut: §37 and §38 already render inside
`/campaigns/<campaign_id>`, and the cross-campaign view is the only thing it adds. It is ratified
because §38's whole point is comparing industries across cities and campaigns, and a comparison
trapped inside one campaign is not that.

---

## 13.3 RBAC matrix

Three roles, from `01-data-model.md` §1.10: `OWNER`, `OPERATOR`, `VIEWER`. `12-security-model.md`
owns the security model; this matrix is the authority on which role may call which route, and that
document is expected to reference it rather than restate it.

Legend: `Y` permitted, `-` forbidden (`403 FORBIDDEN`), `M` permitted but contact values are masked
in the response. Paths are written in shorthand here (`<id>` for whichever id the route takes); the
per-group tables in §13.4 onwards carry the exact parameter names.

| Route group | OWNER | OPERATOR | VIEWER | Notes |
|---|---|---|---|---|
| `GET` campaigns, businesses, research, reports, funnel | Y | Y | M | A VIEWER never sees a contact value |
| `POST /api/v1/campaigns`, `/start`, `/cancel`, `/archive` | Y | Y | - | |
| `POST /api/v1/businesses/<id>/research` (re-research) | Y | Y | - | Costs money; `llm` bucket |
| `PATCH /api/v1/businesses/<id>` (classification) | Y | Y | - | |
| Verification: open, answer, submit, abandon, bulk | Y | Y | - | `VERIFIED` is only ever written by a session (`04` §4.10.5) |
| `POST /api/v1/businesses/<id>/revoke-verification`, `/skip`, `/unskip`, `/reopen` | Y | Y | - | |
| Selection: create, remove, counts | Y | Y | - | |
| Outreach: prepare, regenerate, edit, preview, policy-check | Y | Y | - | |
| `POST .../messages/<id>/send`, `/record-manual`, `/whatsapp-link` | Y | Y | - | Session only; `bp_token` cannot reach these |
| `POST .../messages/<id>/cancel` | Y | Y | - | |
| `GET /api/v1/outreach/eligibility` | Y | Y | M | A VIEWER sees gate outcomes with masked contact values |
| Responses: list, get, manual entry | Y | Y | M | |
| `POST /api/v1/responses/<id>/reclassify` | Y | Y | - | A write |
| Handoffs: acknowledge, start, close, note, demo, proposal, snooze, renotify | Y | Y | - | `GET` is `M` for VIEWER |
| `POST /api/v1/suppressions` | Y | Y | - | |
| `GET /api/v1/suppressions` | Y | M | M | Values are masked for OPERATOR, hashed for VIEWER |
| Reports: generate, download, list | Y | Y | M | An export with `include_contacts=true` is OWNER-only |
| `DELETE /api/v1/report_exports/<id>` | Y | - | - | |
| Jobs: list, get, retry, cancel | Y | Y | - | |
| `POST /api/v1/jobs/<id>/revive` | Y | - | - | Requires a typed reason and writes an audit row |
| `GET` / `PUT /api/v1/settings/contact_policy` | Y | - | - | §31 / §46 policy is the owner's, not the operator's (`01` §1.10) |
| `GET` / `PUT /api/v1/settings/channels` | Y | - | - | |
| `GET /api/v1/settings/templates`, WhatsApp template read | Y | Y | - | Submitting a template to Meta is OWNER |
| `GET /api/v1/settings/users`, user create / disable | Y | - | - | |
| `GET /api/v1/audit/*` | Y | - | - | Raw audit rows |
| `GET /api/v1/outreach/<draft_id>/explain` | Y | Y | - | The assembled view, not the raw rows |
| `POST /api/v1/erasure`, `/erasure/<id>/execute` | Y | - | - | |
| Auth: login, logout, session, password, TOTP, unlock | any | any | any | |
| `POST /api/v1/auth/revoke-all` | any (own sessions) | any (own sessions) | any (own sessions) | A user may always revoke their own sessions; `?user_id=` for another user is OWNER (`12` §12.4.4) |
| `GET /api/v1/quota` | Y | Y | Y | Counts and ceilings only, no business data (§13.16.1) |
| `GET /api/v1/campaigns/<id>/coverage` | Y | Y | Y | `discovery_coverage` rows; no contact values exist on them |
| Inbound triage: `POST /api/v1/inbound/<id>/attach`, `/ignore` | Y | Y | - | Session only; §13.19.1 |
| `GET /api/v1/health` | n/a | n/a | n/a | No role, no business data; §13.15.3 |
| Webhooks, `/u/...` unsubscribe | — | — | — | **These routes do not exist.** §13.19, §13.20, §13.21 |

Enforcement is one decorator, `@require_role("OWNER")`, reading `users.role` for the session user.
A route on `bp_session` with no decorator fails a startup assertion in `radar/web/app.py` — the
default is not "any authenticated user", the default is "the app refuses to boot".

```python
def test_every_session_route_declares_a_role():
    """Walks app.url_map; every rule on bp_session must carry a role marker.

    Without this test the failure mode is a route added on a Friday with no decorator, quietly
    readable by a VIEWER account that exists so somebody can look at a report. The assertion is
    cheap; discovering the gap from an access log is not.
    """
```

---

## 13.4 Campaigns

`campaigns` is owned by `01-data-model.md` §1.3.1, `campaign_cities` by §1.3.2 and
`campaign_businesses` by §1.3.4. Campaign status values are
`DRAFT | QUEUED | DISCOVERING | RESEARCHING | REPORTING | COMPLETE | PAUSED | FAILED | CANCELLED`.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `POST /api/v1/campaigns` | Create a campaign (§1, §2); optionally start it | OPERATOR | `write` | `Idempotency-Key` | `CAMPAIGN_CREATED`, then `CAMPAIGN_STARTED` when `start=true` |
| `GET /api/v1/campaigns` | List, newest first | VIEWER | `read` | n/a | — |
| `GET /api/v1/campaigns/<campaign_id>` | One campaign with its cities and live aggregates | VIEWER | `read` | n/a | — |
| `POST /api/v1/campaigns/<campaign_id>/start` | `DRAFT -> QUEUED`; fan out `discover_city` | OPERATOR | `write` | Natural — a second call on a non-`DRAFT` campaign is `409` | `CAMPAIGN_STARTED` |
| `POST /api/v1/campaigns/<campaign_id>/cancel` | Set `cancel_requested = 1` on the campaign and every non-terminal job | OPERATOR | `write` | Natural — already cancelled returns `200` | `CAMPAIGN_CANCELLED` |
| `GET /api/v1/campaigns/<campaign_id>/stats` | The §36 dashboard block and the §37 / §38 comparisons | VIEWER | `read` | n/a | — |
| `GET /api/v1/campaigns/<campaign_id>/progress` | O(1) progress poll while running | VIEWER | `progress` (60/min) | n/a | — |
| `GET /api/v1/campaigns/<campaign_id>/events` | SSE stream of the same, for the live page | VIEWER | 4 concurrent | n/a | — |
| `POST /api/v1/campaigns/<campaign_id>/archive` | Hide from the default list; the campaign stays readable and its exports stay downloadable | OPERATOR | `write` | Natural | `CAMPAIGN_ARCHIVED` |
| `GET /api/v1/campaigns/<campaign_id>/selectable` | The §18 selection grid: one row per `campaign_businesses` row, with `selectable` and `blocking_gate` | OPERATOR | `read` | n/a | — |
| `GET /api/v1/campaigns/<campaign_id>/selection-counts` | Per-city selection counts (§18) | OPERATOR | `read` | n/a | — |
| `GET /api/v1/campaigns/<campaign_id>/coverage` | The `discovery_coverage` rows for the campaign: one per `(city, category)` with `band`, `coverage_pct`, `elements_found`, `elements_kept`, `tag_rich_pct`, `denominator`, `denominator_kind` and `note` | VIEWER | `read` | n/a | — |
| `GET /api/v1/campaigns/<campaign_id>/report` | `ReportData` as JSON (`03` §3.16) | VIEWER | `read` | n/a | — |
| `POST /api/v1/campaigns/<campaign_id>/report` | Re-generate the campaign HTML report | OPERATOR | `export` | Job dedupe key | `REPORT_GENERATED` (written by the job) |

`coverage` answers `02-research-pipeline.md`'s Open question 6. The exported report reads
`discovery_coverage` (§2.2.9, §2.3.6) directly off the database, but the live app's city tabs need it
over HTTP and no other endpoint carries it. Filters: `city`, `category`, `band` (enum set over
`HIGH | MEDIUM | LOW | UNKNOWN`). Sort allow-list: `city` (default `city`), `coverage_pct`,
`elements_kept`. `coverage_pct` and `denominator` are `null`, never `0`, when `denominator_kind` is
`NONE` — §2.3.6's priority-3 rule and `_CONTEXT.md` invariant 5 are the same rule seen from two
sides, and a coverage chip that renders `0%` for "we could not assess this" is the exact lie §2.2.9
exists to prevent. `denominator_kind` travels with every row, because a `POPULATION_MODEL`
denominator is a prior and a `REGISTRY` one is a count, and a UI that renders them identically
launders the second into the first.

`archive` is new here. `campaigns` has no `archived_at` column, so this is an amendment request
against `01-data-model.md`, recorded in Open questions. Until it lands the endpoint is
unimplemented and the list endpoint's `archived` filter is absent. §42 requires that every campaign
is stored and reopenable, which the current schema already satisfies; archiving is only about the
default view.

### 13.4.1 Create

```http
POST /api/v1/campaigns
Content-Type: application/json
X-CSRF-Token: <session csrf>
Idempotency-Key: 6e6bb1c2-0f0e-4a6a-9b45-3a2c1d0e5f77

{
  "name": "Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026",
  "cities": ["Dhule", "Shirpur", "Nashik", "Jalgaon"],
  "industries": [],
  "categories": ["HOSPITAL", "SCHOOL", "MANUFACTURER"],
  "size_filter": ["MEDIUM", "LARGE"],
  "min_opportunity_score": 70,
  "research_depth": "STANDARD",
  "max_businesses": 400,
  "notes": "SAMPLE",
  "start": true
}
```

| Field | Type | Required | Rule |
|---|---|---|---|
| `name` | string 3..200 | no | Defaults to `"<City-City-...> - <DD Mon YYYY>"` (§2). `slug` is derived and unique-indexed; a collision appends `-2` |
| `cities` | array of string, 1..12 | **yes** | Each is normalised by `radar/identity.py::city_slug`. Order is preserved into `campaign_cities.ordinal` — Sagar's typed order, not alphabetical |
| `industries` | array of the §6 industry enum | no | `[]` means all |
| `categories` | array of the §6 category enum | no | `[]` means all |
| `size_filter` | array of `size_band` | no | `[]` means no size filter |
| `min_opportunity_score` | int 0..100 | no | Defaults to `0`, not `70` — see `01-data-model.md` §1.3.1 |
| `research_depth` | `STANDARD` \| `DEEP` | no | Default `STANDARD` |
| `max_businesses` | int > 0 | no | Null means uncapped |
| `start` | bool | no | Default `false` gives `status='DRAFT'`. `true` gives `QUEUED` plus the fan-out, in the same transaction |

Response `201`, `Location: /api/v1/campaigns/cmp_01JBSAMPLE0000000000000001`:

```json
{
  "id": "cmp_01JBSAMPLE0000000000000001",
  "name": "Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026",
  "slug": "dhule-shirpur-nashik-jalgaon-2026-08-26",
  "status": "QUEUED",
  "cities": [
    {"city": "Dhule", "city_slug": "dhule", "ordinal": 0, "status": "PENDING"},
    {"city": "Shirpur", "city_slug": "shirpur", "ordinal": 1, "status": "PENDING"}
  ],
  "min_opportunity_score": 70,
  "research_depth": "STANDARD",
  "research_model_id": "gemini-2.5-flash",
  "research_prompt_version": "research-v3",
  "created_by": "usr_01JBSAMPLE000000000000U1",
  "created_at": "2026-08-26T04:10:00Z",
  "batch_id": "bat_01JBSAMPLE0000000000000B1",
  "trace_id": "trc_01JBSAMPLE0000000000000T1"
}
```

Errors:

| Code | HTTP | When |
|---|---|---|
| `CITIES_REQUIRED` | 422 | `cities` empty or absent |
| `CITY_LIMIT` | 422 | More than 12 cities. Discovery cost is linear in cities, and a 40-city campaign is a runaway bill rather than a plan |
| `INVALID_ENUM` | 422 | An industry, category or size outside `_CONTEXT.md` §6 |
| `SLUG_CONFLICT` | 409 | A campaign with the same slug exists **and** no `Idempotency-Key` was supplied |
| `SPEND_CEILING` | 409 | `start=true` while `v_spend_today` is over the ceiling. The campaign is still created, as `DRAFT`, and the body says so |

### 13.4.2 Read, list, stats

`GET /api/v1/campaigns` filters: `status` (enum set), `created_from` / `created_to`, `q` (name and
slug substring), `archived` (`true` / `false` / `only`, default `false`). Sort allow-list:
`created_at` (default `-created_at`), `name`, `status`.

`GET /api/v1/campaigns/<id>` returns the `Campaign` schema plus:

```json
{
  "counters": {
    "source": "aggregate",
    "n_discovered": 148, "n_researched": 141, "n_qualified": 63,
    "n_skipped": 12, "n_verified": 21, "n_contacted": 9,
    "drift": {"n_researched": {"stored": 140, "aggregate": 141}}
  }
}
```

`counters.source` is always `"aggregate"`. The numbers come from `v_campaign_counters`
(`01-data-model.md` §1.3.5), never from `campaigns.n_*`. The stored counters appear only inside
`drift`, and only when they disagree. This is the API expression of the rule `01` states once for
the whole pack: the counter is a progress hint, the view is the number. §8's "never fabricate them"
is enforced here by there being no field a template could read that is not an aggregate.

`GET /api/v1/campaigns/<id>/stats` returns the §36 dashboard figures, the §37 city comparison and
the §38 industry comparison, each as an array of rows with `null` — not `0` — for a metric with no
data:

```json
{
  "funnel": {"found": 148, "researched": 141, "qualified": 63, "verified": 21,
             "selected": 15, "prepared": 15, "approved": 9, "sent": 9,
             "responses": 3, "interested": 2, "demos": 1, "proposals": null, "won": null},
  "by_city": [
    {"city": "Dhule", "businesses": 41, "qualified": 18, "high_opportunity": 6,
     "verified": 7, "contacted": 4, "responses": 2, "interested": 1,
     "conversion_pct": 25.0, "potential_revenue_inr": null}
  ],
  "by_industry": [
    {"industry": "HEALTHCARE", "businesses": 33, "avg_opportunity": 74,
     "verified": 9, "contacted": 5, "responses": 2, "interested": 1,
     "demos": 1, "won": null, "revenue_inr": null}
  ]
}
```

`potential_revenue_inr` is `null` rather than `0` wherever `opportunities.est_value_inr` is unset
for every row in the group. `03-html-report.md` Open question 3 records that nothing writes that
column yet, and a `0` there reads as "worth nothing" instead of "not priced".

### 13.4.3 Progress and events

`GET /api/v1/campaigns/<id>/progress` is the O(1) poll (`14-background-jobs.md` §14.11). It reads
`campaigns.n_*` and the `jobs` queue depth — the one place a stored counter is legitimately the
source, because it is labelled a progress hint and is never rendered as a fact:

```json
{
  "campaign_id": "cmp_01JBSAMPLE0000000000000001",
  "status": "RESEARCHING",
  "hint": {"n_discovered": 148, "n_researched": 96},
  "jobs": {"queued": 45, "running": 4, "failed": 1, "dead": 0},
  "cities": [{"city_slug": "dhule", "status": "COMPLETE", "n_discovered": 41}],
  "eta_seconds": 1260,
  "as_of": "2026-08-26T05:02:11Z"
}
```

`Cache-Control: no-store`. The key name `hint` is deliberate: a client that renders these numbers as
final counts is contradicting the field name.

`GET /api/v1/campaigns/<id>/events` is `text/event-stream`, one event per state change, with
`event: progress | city | job | done` and a `retry: 5000` hint. It closes on `CANCELLED`, `FAILED`
or `COMPLETE`. It is a convenience over the poll, not a replacement: a browser that loses the stream
falls back to `/progress` and nothing is lost, because the stream carries no state the database does
not.

---

## 13.5 Research

`research_runs`, `research_findings`, `sources` and `finding_sources` are owned by
`01-data-model.md` §1.6. `research_runs.status` is
`PENDING | RUNNING | COMPLETE | FAILED | CANCELLED` — `COMPLETE`, never `COMPLETED` (§1.2.4 D1).

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `POST /api/v1/campaigns/<campaign_id>/start` | Trigger research for a whole campaign (§13.4) | OPERATOR | `write` | Natural | `CAMPAIGN_STARTED` |
| `GET /api/v1/campaigns/<campaign_id>/progress` | Campaign-wide research status | VIEWER | `progress` | n/a | — |
| `GET /api/v1/businesses/<business_id>/research` | The current run, its findings by `kind`, and its sources (§12, §14) | VIEWER | `read` | n/a | — |
| `GET /api/v1/research/runs/<research_run_id>` | One historical run, including a superseded one | VIEWER | `read` | n/a | — |
| `POST /api/v1/businesses/<business_id>/research` | Re-research one business (`research_runs.trigger='MANUAL'`) | OPERATOR | `llm` | Job dedupe key `research_business:{business_id}:{fingerprint}` | `RESEARCH_RUN_STARTED` |
| `GET /api/v1/businesses/<business_id>/sources` | The §14 source panel | VIEWER | `read` | n/a | — |
| `POST /api/v1/businesses/<business_id>/sources` | Record a source Sagar opened by hand (`02` §2.2.3) | OPERATOR | `write` | `Idempotency-Key`, and naturally idempotent on `ux_sources_business_url` | `SOURCE_FETCHED` |

### 13.5.1 `GET /api/v1/businesses/<business_id>/research`

Query: `run_id` (default: the latest `COMPLETE` run), `include=findings,sources,opportunity`
(default: all three).

```json
{
  "run": {
    "id": "res_01JBSAMPLE0000000000000R1",
    "business_id": "biz_01JBSAMPLE000000000000B1",
    "campaign_id": "cmp_01JBSAMPLE0000000000000001",
    "status": "COMPLETE",
    "depth": "STANDARD",
    "trigger": "CAMPAIGN",
    "model_id": "gemini-2.5-flash",
    "prompt_version": "research-v3",
    "n_findings_observed": 6, "n_findings_inferred": 3, "n_findings_unknown": 2,
    "n_sources": 4,
    "started_at": "2026-08-26T05:11:00Z",
    "finished_at": "2026-08-26T05:12:41Z",
    "fingerprint": "8c41a09b"
  },
  "findings": {
    "OBSERVED": [
      {"id": "fnd_01JBSAMPLE000000000000F1", "kind": "OBSERVED", "dimension": "OPERATIONS",
       "label": "Multi-department outpatient load",
       "statement": "The hospital lists six departments and an outpatient department across two floors. (SAMPLE)",
       "detail": "Departments listed: medicine, surgery, orthopaedics, paediatrics, pathology, radiology. (SAMPLE)",
       "confidence": "HIGH", "confidence_pct": 88, "weight": 1.0,
       "source_ids": ["src_01JBSAMPLE00000000000S1"]}
    ],
    "INFERRED": [
      {"id": "fnd_01JBSAMPLE000000000000F7", "kind": "INFERRED", "dimension": "SYSTEMS",
       "label": "Departmental records likely uncoordinated",
       "statement": "Records may be maintained separately per department. (SAMPLE)",
       "confidence": "MEDIUM", "confidence_pct": 61, "weight": 0.6,
       "derived_from": ["fnd_01JBSAMPLE000000000000F1"],
       "inference_note": "Six departments with no shared portal on the site. (SAMPLE)",
       "source_ids": []}
    ],
    "UNKNOWN": [
      {"id": "fnd_01JBSAMPLE000000000000F9", "kind": "UNKNOWN", "dimension": "FINANCE",
       "label": "Billing system",
       "statement": "No public information on billing software. (SAMPLE)",
       "confidence": "LOW", "unknown_reason": "NOT_PUBLISHED", "source_ids": []}
    ]
  },
  "sources": [
    {"id": "src_01JBSAMPLE00000000000S1", "name": "ABC Hospital official website (SAMPLE)",
     "url": "https://abc-hospital.example.invalid/departments",
     "source_type": "SITE", "checked_at": "2026-08-26T05:11:22Z",
     "information_obtained": "Department list and floor plan. (SAMPLE)",
     "confidence": "HIGH", "http_status": 200,
     "snapshot_path": "snapshots/2026/08/26/src_01JBSAMPLE00000000000S1.html.gz"}
  ]
}
```

Three rules the shape enforces:

1. **The three `kind` buckets are separate keys, not a flat list with a field.** §12 calls the
   separation mandatory. A client that wants one list has to write the code to flatten it, and a
   client that forgets to filter cannot accidentally show an `UNKNOWN` as a fact.
2. `source_ids` on an `OBSERVED` finding is never empty. `01-data-model.md` §1.6.5 makes that a
   write-time invariant with a trigger, an assertion and a nightly probe; the API relies on it
   rather than re-checking it, and probe `P7` is what catches a violation.
3. `checked_at` is the field name (§1.2.4 D4). `fetched_at` appears in no API payload.

### 13.5.2 `POST /api/v1/businesses/<business_id>/research`

```json
{"depth": "DEEP", "reason": "Website changed since the last run. (SAMPLE)", "force": false}
```

| Field | Rule |
|---|---|
| `depth` | `STANDARD` \| `DEEP`; defaults to the campaign's |
| `reason` | Required, >= 10 chars. It lands in the job payload and in `RESEARCH_RUN_STARTED.detail_json`, because "why did we pay for this run again" is a question that gets asked when the bill arrives |
| `force` | `false` (default) puts the current `research_fingerprint` in the job dedupe key, so re-running against unchanged inputs is a no-op that returns the existing run. `true` mints a fresh key |

Response `202`: `{"job_id": "job_01JBSAMPLE0000000000000J1", "research_run_id": null,
"deduplicated": false}`. A duplicate returns `200` with `"deduplicated": true`.

| Code | HTTP | When |
|---|---|---|
| `BUSINESS_MERGED` | 409 | The business is a merge tombstone; `detail.merged_into_id` names the winner |
| `SPEND_CEILING` | 409 | `v_spend_today` is over the ceiling (`14` §14.10.4). Research pauses rather than degrading |
| `RESEARCH_IN_FLIGHT` | 409 | A `RUNNING` run exists and `force` was not set |

---

## 13.6 Businesses

`businesses` is owned by `01-data-model.md` §1.4 and is **one row per real-world business**, not one
per campaign (§1.2.2). Campaign membership lives in `campaign_businesses`, so every campaign-scoped
read here takes `campaign_id` as a *filter*, never as a column on the row.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `GET /api/v1/businesses` | The §9 grid, with the §39 eleven filters as query parameters | VIEWER (M) | `read` | n/a | — |
| `GET /api/v1/businesses/<business_id>` | The §11 detail: identity, place, assessment, lifecycle | VIEWER (M) | `read` | n/a | `CONTACTS_REVEALED` when `reveal=contacts` |
| `GET /api/v1/businesses/<business_id>/detail` | Detail plus findings, sources, opportunity, modules, contacts, history — one round trip for `/business/<id>` | VIEWER (M) | `read` | n/a | `CONTACTS_REVEALED` when `reveal=contacts` |
| `PATCH /api/v1/businesses/<business_id>` | Correct classification: `industry`, `category`, `size_band`, `city`, `website` | OPERATOR | `write` | `Idempotency-Key` | `BUSINESS_RECLASSIFIED` |
| `GET /api/v1/businesses/<business_id>/history` | The §32 outreach history: messages, events, responses | OPERATOR | `read` | n/a | — |
| `GET /api/v1/businesses/<business_id>/readiness` | `ContactReadiness` — why this business is or is not selectable (`04` §4.12.1) | OPERATOR | `read` | n/a | — |
| `GET /api/v1/businesses/<business_id>/contacts` | Contact points for one business | OPERATOR (M) | `read` | n/a | `CONTACTS_REVEALED` when `reveal=1` |
| `POST /api/v1/businesses/<business_id>/contacts/<contact_id>/confirm` | Check 5's contact confirmation; sets `human_verified = 1` (`04` §4.6.7) | OPERATOR | `write` | Natural | `CONTACT_CONFIRMED` |

### 13.6.1 The §39 eleven filters as query parameters

`03-html-report.md` §3.6.2 implements these eleven filters client-side inside the exported HTML
file. `GET /api/v1/businesses` is the server-side twin, and the two must agree row for row — the
export is generated from this query's result set, and a filter that means one thing in the file and
another in the app is a filter Sagar cannot trust.

| # | §39 filter | Query parameter | Type | Maps to |
|---|---|---|---|---|
| 1 | City | `city` | enum set of `city_slug` | `businesses.city_slug` |
| 2 | Industry | `industry` | enum set | `businesses.industry` |
| 3 | Business size | `size` | enum set incl. `UNKNOWN` | `businesses.size_band` |
| 4 | Opportunity score | `score_min`, `score_max`, `include_unscored` | int 0..100, bool (default `true`) | `businesses.opportunity_score` |
| 5 | Website status | `website` | enum set `PRESENT,ABSENT,UNKNOWN` | `businesses.website_status` |
| 6 | Digital maturity | `dm_min`, `dm_max`, `include_unassessed` | int 0..100, bool (default `true`) | `businesses.digital_maturity` |
| 7 | Research confidence | `confidence` | enum set `HIGH,MEDIUM,LOW,NONE` | `businesses.research_confidence`; `NONE` matches `NULL` |
| 8 | Verification status | `verification` | enum set | `verif_state()` (`03` §3.6.1), **not** `businesses.status` directly |
| 9 | Contact status | `contact` | enum set `EMAIL,PHONE,WHATSAPP,UNVERIFIED,NONE`, OR-combined | `business_contacts` |
| 10 | Outreach status | `outreach` | enum set | derived, §13.6.2 |
| 11 | Date discovered | `discovered_from`, `discovered_to` | `YYYY-MM-DD` | `campaign_businesses.first_seen_at` when `campaign_id` is given, else `businesses.first_discovered_at` |

Plus, not part of §39 but needed by every caller:

| Parameter | Type | Notes |
|---|---|---|
| `campaign_id` | `cmp_...` | Restricts to `campaign_businesses` rows for that campaign. **Absent means every business in the database**, which is the global view, not a campaign report |
| `membership` | `INCLUDED` \| `EXCLUDED` \| `ALL` | Only with `campaign_id`. Default `INCLUDED`. `EXCLUDED` is what makes the report say "excluded: you rejected this in June" instead of dropping the row |
| `category` | enum set | The finer §6 vocabulary, used for the §4 category grouping |
| `q` | string | Substring over name, city, category label, industry label, `potential_solution`, website domain and `business_id` — the same blob `03` §3.6.1 builds |
| `sort` | see below | |
| `limit`, `cursor`, `count` | §13.2.6 | |

Sort allow-list: `opportunity_score` (default `-opportunity_score`), `name`, `city_slug`,
`digital_maturity`, `first_discovered_at`, `status`, `last_contacted_at`. Unscored rows sort last in
both directions.

Worked example — the §52 campaign view, medium and large healthcare in Dhule and Nashik scoring 70+,
still needing verification:

```http
GET /api/v1/businesses
    ?campaign_id=cmp_01JBSAMPLE0000000000000001
    &city=dhule,nashik
    &industry=HEALTHCARE
    &size=MEDIUM,LARGE
    &score_min=70&include_unscored=false
    &verification=NEEDS_VERIFICATION
    &sort=-opportunity_score&limit=50
```

### 13.6.2 The derived `outreach` filter

Filter 10 does not read one column. `businesses.status` carries the lifecycle and
`outreach_messages.status` carries the message, and §39 requires them to be independent — a
`CONTACTED` business is still `VERIFIED` for filter 8. The derived value, computed once in
`radar/web/api/businesses.py` and matching `03` §3.6.1's `data-outreach`:

| Value | Condition (latest non-`CANCELLED` message for the business) |
|---|---|
| `NOT_CONTACTED` | no message rows |
| `QUEUED` | latest is `DRAFT`, `PENDING_APPROVAL`, `APPROVED` or `QUEUED` |
| `SENT` / `DELIVERED` / `BOUNCED` / `FAILED` | latest is that status |
| `RESPONDED` | a `responses` row exists for the business |
| `INTERESTED` | `businesses.status` is `INTERESTED` or `HUMAN_HANDOFF` |
| `BLOCKED` | a live `suppressions` row matches the business or any of its contact points |

`BLOCKED` outranks everything else. A business that was contacted in June and opted out in July
shows as `BLOCKED`, because that is the fact that governs what may happen next.

### 13.6.3 Row shape

```json
{
  "id": "biz_01JBSAMPLE000000000000B1",
  "name": "ABC Hospital (SAMPLE)",
  "city": "Dhule", "city_slug": "dhule",
  "industry": "HEALTHCARE", "category": "HOSPITAL",
  "size_band": "MEDIUM",
  "website": "https://abc-hospital.example.invalid",
  "website_status": "PRESENT",
  "digital_maturity": 62,
  "operational_complexity": 71,
  "opportunity_score": 86, "opportunity_band": "HIGH",
  "potential_solution": "Hospital Operations Platform (SAMPLE)",
  "research_confidence": "MEDIUM", "research_confidence_pct": 64,
  "status": "NEEDS_VERIFICATION",
  "verification_state": "NEEDS_VERIFICATION",
  "outreach_state": "NOT_CONTACTED",
  "contact_available": ["EMAIL"],
  "contact_confirmed": false,
  "suppressed": false,
  "selectable": false,
  "blocking_gate": "D_NOT_VERIFIED",
  "blocking_sentence": "ABC Hospital (SAMPLE) is NEEDS_VERIFICATION - verify it before preparing outreach.",
  "campaign": {"campaign_id": "cmp_01JBSAMPLE0000000000000001",
               "state": "INCLUDED", "exclusion_reason": null,
               "first_seen_at": "2026-08-26T05:04:00Z", "is_rediscovery": false},
  "first_discovered_at": "2026-08-26T05:04:00Z",
  "last_contacted_at": null
}
```

`campaign` is present only when `campaign_id` was supplied, and it carries the per-campaign facts
from `campaign_businesses` — including `city_at_discovery` on the detail endpoint, so an archived
report stays reproducible after a city correction.

`contact_available` is an array of *kinds*, never of values. The list endpoint returns no contact
value for any role, including OWNER. §13.21 explains why.

### 13.6.4 Revealing contact values, and the audit row it writes

One business at a time, one deliberate parameter, one audit row:

```http
GET /api/v1/businesses/biz_01JBSAMPLE000000000000B1?reveal=contacts
```

```json
{
  "contacts": [
    {"id": "cnt_01JBSAMPLE000000000000C1", "kind": "EMAIL",
     "value_display": "info@abc-hospital.example.invalid",
     "domain": "abc-hospital.example.invalid",
     "is_public_business_contact": true, "is_named_individual": false,
     "is_role_address": true, "human_verified": true, "is_active": true,
     "confidence": "HIGH", "source_url": "https://abc-hospital.example.invalid/contact",
     "captured_at": "2026-08-26T05:11:40Z", "retention_class": "P2Y"}
  ]
}
```

| Behaviour | Rule |
|---|---|
| Without `reveal` | `value_display` is masked (`i***@abc-hospital.example.invalid`), no audit row |
| With `reveal=contacts` | Full values for OWNER and OPERATOR; `403 FORBIDDEN` for VIEWER; one `CONTACTS_REVEALED` audit row carrying `business_id`, `contact_ids[]`, `kinds[]` and `count` — never the values |
| Named individuals | A contact with `is_named_individual = 1` is personal data under DPDP. Revealing it always writes the audit row, even for OWNER, and `detail_json.named_individuals` counts them |

`CONTACTS_REVEALED` does not exist in `11-audit-architecture.md` §11.6's catalogue and is an
amendment request (§ Corrections). Without it, "no endpoint returns a contact list without an audit
row" is a claim with no row behind it.

### 13.6.5 `PATCH /api/v1/businesses/<business_id>`

The §16 verification checklist has an item "Business category is correct". When it is not, this is
what fixes it.

```json
{
  "industry": "HEALTHCARE",
  "category": "DIAGNOSTIC_CENTER",
  "size_band": "SMALL",
  "reason": "SAMPLE - diagnostics only, no inpatient beds; checked their own site."
}
```

| Rule | Detail |
|---|---|
| Fields | Only `industry`, `category`, `size_band`, `city` / `city_slug`, `website`, `listing_url`, `name`. Nothing else is patchable; `status`, `opportunity_score` and every assessment column are written by their own modules |
| `reason` | Required, >= 10 chars, stored in `BUSINESS_RECLASSIFIED.detail_json` alongside `before_json` / `after_json` |
| Side effect | A change to `city_slug`, `industry` or `category` recomputes `contact_fingerprint` and may make a live verification stale (`04` §4.9.2). The response carries `"verification_now_stale": true` when it did |
| Refusals | `409 BUSINESS_MERGED` on a tombstone; `409 STATUS_LOCKED` when `businesses.status` is `HUMAN_HANDOFF` — a live lead is not reclassified underneath Sagar |

Errors common to this whole group:

| Code | HTTP | When |
|---|---|---|
| `NOT_FOUND` | 404 | No such business, or the caller's role may not know it exists |
| `BUSINESS_MERGED` | 409 | Tombstoned by a merge; `detail.merged_into_id` |
| `INVALID_ENUM` | 422 | A value outside `_CONTEXT.md` §6 |
| `FILTER_CONFLICT` | 422 | `membership` supplied without `campaign_id` |
| `SORT_FIELD_NOT_ALLOWED` | 422 | `detail.allowed[]` lists the permitted fields |

---

## 13.7 Verification

`verifications` and `verification_checks` are owned by `01-data-model.md` §1.8; the workflow, the
state machine and the anti-rubber-stamp ladder are owned by `04-verification-workflow.md`. The
verdict column is `verdict`, never `result` (§1.2.4 D2).

`04` §4.12.1 put the business-scoped read and the verification-scoped writes on the same path
prefix, so `/api/v1/verifications/<x>` meant a `biz_` on one route and a `ver_` on another. Rule N3
splits them.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `GET /api/v1/verifications/queue` | The §4.5.4 queue: businesses awaiting a verdict | OPERATOR | `read` | n/a | — |
| `GET /api/v1/businesses/<business_id>/verification` | The §15 screen payload: identity, contact, research summary, sources, AI recommendation, opportunity | OPERATOR | `read` | n/a | — |
| `GET /api/v1/businesses/<business_id>/verifications` | Prior verifications for this business | OPERATOR | `read` | n/a | — |
| `POST /api/v1/verifications` | Open or resume a draft. Idempotent per `(business, user)` via `ux_verifications_draft` | OPERATOR | `write` | Natural | `VERIFICATION_OPENED` |
| `PUT /api/v1/verifications/<verification_id>/checks/<check_key>` | Answer one of the nine §16 checks | OPERATOR | `write` | Natural (last write wins per key) | `VERIFICATION_SAVED`, at most once per 60 s |
| `POST /api/v1/verifications/<verification_id>/sources/<source_id>/visited` | Visit beacon; `204` | OPERATOR | `write` | Natural | — |
| `POST /api/v1/verifications/<verification_id>/sources/<source_id>/waive` | Waive a source with a reason | OPERATOR | `write` | Natural | `VERIFICATION_SAVED` |
| `POST /api/v1/verifications/<verification_id>/submit` | **The only writer of a `VERIFIED` verdict.** Also writes `REJECTED` and `SKIPPED` | OPERATOR, session only | `write` | `Idempotency-Key` | `BUSINESS_VERIFIED` / `BUSINESS_REJECTED` / `BUSINESS_SKIPPED` |
| `POST /api/v1/verifications/<verification_id>/abandon` | `DRAFT -> ABANDONED` | OPERATOR | `write` | Natural | `VERIFICATION_ABANDONED` |
| `POST /api/v1/verifications/bulk` | Bulk reject / skip / unskip / requeue (§4.8.2) | OPERATOR | `write` | `Idempotency-Key` | one row per business |
| `POST /api/v1/businesses/<business_id>/revoke-verification` | **Re-verify**: `VERIFIED -> NEEDS_VERIFICATION` (T11 / T16) | OPERATOR | `write` | Natural | `VERIFICATION_REVOKED` |
| `POST /api/v1/businesses/<business_id>/skip` | Park it (T04 / T08 / T13 / T18) | OPERATOR | `write` | Natural | `BUSINESS_SKIPPED` |
| `POST /api/v1/businesses/<business_id>/unskip` | T23 | OPERATOR | `write` | Natural | `BUSINESS_STATUS_CHANGED` |
| `POST /api/v1/businesses/<business_id>/reopen` | T29, after a non-permanent rejection (§4.2.4) | OPERATOR | `write` | Natural | `BUSINESS_STATUS_CHANGED` |

**There is no `/approve` and no `/reject` route.** Both verdicts are `POST .../submit` with a
`verdict` field, because both must pass the same thirteen-step ladder and the same nine checklist
rows. Two endpoints would be two ladders, and the second one is the one that drifts.

### 13.7.1 Submit

```http
POST /api/v1/verifications/ver_01JBSAMPLE000000000000V1/submit
Content-Type: application/json
X-CSRF-Token: <session csrf>
Idempotency-Key: 0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0

{
  "verdict": "VERIFIED",
  "checks": [
    {"check_key": "IDENTITY_CORRECT",       "passed": true,  "note": null},
    {"check_key": "IN_TARGET_CITY",         "passed": true,  "note": null},
    {"check_key": "CATEGORY_CORRECT",       "passed": true,  "note": "SAMPLE - diagnostics, not a hospital; corrected."},
    {"check_key": "APPEARS_OPERATIONAL",    "passed": true,  "note": null},
    {"check_key": "CONTACT_LEGITIMATE",     "passed": true,  "note": null},
    {"check_key": "RESEARCH_RELEVANT",      "passed": true,  "note": null},
    {"check_key": "OPPORTUNITY_REASONABLE", "passed": true,  "note": null},
    {"check_key": "OUTREACH_APPROPRIATE",   "passed": true,  "note": null},
    {"check_key": "NO_DNC_RECORD",          "passed": true,  "note": null}
  ],
  "why_note": "SAMPLE - paper report collection confirmed on their own site; owner-run, 2 branches.",
  "contact_id_confirmed": "cnt_01JBSAMPLE000000000000C1",
  "active_ms": 61240,
  "client_fingerprint": "sha256:SAMPLE"
}
```

The nine `check_key` values are `01-data-model.md` §1.8.2's, exactly: `IDENTITY_CORRECT`,
`IN_TARGET_CITY`, `CATEGORY_CORRECT`, `APPEARS_OPERATIONAL`, `CONTACT_LEGITIMATE`,
`RESEARCH_RELEVANT`, `OPPORTUNITY_REASONABLE`, `OUTREACH_APPROPRIATE`, `NO_DNC_RECORD`.
`04` §4.6.4's sample payload writes `CITY_IN_TARGET` for the second one; that is a typo against the
schema's `CHECK` and is recorded in Corrections.

Response `200`:

```json
{
  "verification_id": "ver_01JBSAMPLE000000000000V1",
  "verdict": "VERIFIED",
  "business_status": "CONTACT_READY",
  "readiness": {"ok": true, "failing_clause": null, "blocking_code": null},
  "next_business_id": "biz_01JBSAMPLE000000000000B2",
  "audit_ids": ["aud_01JBSAMPLE00000000000AB1", "aud_01JBSAMPLE00000000000AB2"]
}
```

`business_status` is returned rather than assumed: a `VERIFIED` verdict may chain straight to
`CONTACT_READY` (T09) when a confirmed contact exists, and a UI that hard-codes `VERIFIED` shows the
wrong badge for the businesses that matter most.

The thirteen-step ladder from `04` §4.6.4, as HTTP:

| # | Check | HTTP | `error.code` |
|---|---|---|---|
| 1 | Session, CSRF, `verify` permission | 401 / 403 | `NOT_AUTHORISED` |
| 2 | Verification exists, `state='DRAFT'`, opened by this user | 409 | `NOT_YOUR_DRAFT` |
| 3 | `businesses.status` still admits this verdict (§4.2.3) | 409 | `ILLEGAL_TRANSITION`; `detail.transition` names the T-number |
| 4 | Exactly nine `checks`, keys matching the schema | 422 | `CHECKLIST_MALFORMED` |
| 5 | Every `passed=false` carries a note >= 10 chars | 422 | `FAILED_CHECK_NEEDS_NOTE` |
| 6 | Any `passed=false` implies `verdict='REJECTED'` | 422 | `FAILED_CHECK_REQUIRES_REJECTION` |
| 7 | `REJECTED` resolves a `reason_code`; `OTHER` needs >= 20 chars; `DUPLICATE_OF_EXISTING` needs `duplicate_of_business_id` | 422 | `REASON_REQUIRED` |
| 8 | `VERIFIED` requires all nine `passed=true` | 422 | `INCOMPLETE_CHECKLIST` |
| 9 | `VERIFIED` requires `why_note` >= 15 chars after trim | 422 | `WHY_NOTE_REQUIRED` |
| 10 | `VERIFIED` requires every required source visited or waived | 422 | `SOURCES_NOT_REVIEWED`; `detail.source_ids[]` |
| 11 | `VERIFIED` requires `now - opened_at >= dwell_required_ms` | 422 | `DWELL_NOT_MET`; `detail.remaining_ms` |
| 12 | `VERIFIED` requires no live suppression (gate A) | 409 | `SUPPRESSED`; `detail.suppression_id`, `detail.scope` |
| 13 | `VERIFIED` requires `contact_id_confirmed` to name an active contact of this business | 422 | `CONTACT_NOT_CONFIRMED` |

Steps 1-13 run **before** `BEGIN IMMEDIATE`. Everything after runs inside one transaction, in
`04` §4.6.4's order: freeze the checks, supersede the prior live verification, submit, confirm the
contact, `set_status()`, audit, refresh readiness.

### 13.7.2 Bulk

`POST /api/v1/verifications/bulk` exists and **rejects `verdict='VERIFIED'` before it reads the row
list**:

```json
{"action": "REJECT", "business_ids": ["biz_...B1", "biz_...B2"],
 "reason_code": "OUT_OF_SCOPE", "reason_note": "SAMPLE - all veterinary clinics."}
```

`action` is `REJECT | SKIP | UNSKIP | REQUEUE`. `VERIFY` is not a value; a request naming it returns
`400 BULK_VERIFY_FORBIDDEN` as the handler's **first statement**, before any parsing, per
`04` §4.8.2. §13.21 records why.

Response `200`: `{"applied": [...], "rejected": [{"business_id": "...", "code":
"ILLEGAL_TRANSITION", "message": "..."}], "audit_ids": [...]}`.

---

## 13.8 Selection

`selections` is owned by `05-outreach-workflow.md` §5.3.3. §18 is bulk selection across cities; §19
is that nothing on this surface transmits.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `POST /api/v1/selections` | Select one or many businesses for a campaign (§18) | OPERATOR | `write` | Natural, via `ux_selections_live` | `SELECTION_CREATED` per row, `SELECTION_BLOCKED` per refusal |
| `DELETE /api/v1/selections/<selection_id>` | Deselect. Soft: `state='REMOVED'`, row kept | OPERATOR | `write` | Natural | `SELECTION_REMOVED` |
| `GET /api/v1/selections` | List selections, filterable by `campaign_id`, `state`, `city` | OPERATOR | `read` | n/a | — |
| `GET /api/v1/campaigns/<campaign_id>/selection-counts` | The per-city counts strip (§18) | OPERATOR | `read` | n/a | — |

Request and response are `05` §5.4.3's, unchanged:

```json
{"campaign_id": "cmp_01JBSAMPLE0000000000000001",
 "business_ids": ["biz_...B1", "biz_...B2", "biz_...B3"],
 "intent_channel": "EMAIL"}
```

```json
{
  "campaign_id": "cmp_01JBSAMPLE0000000000000001",
  "created": [
    {"selection_id": "sel_01JBSAMPLE00000000000S1", "business_id": "biz_...B1", "city": "Dhule",
     "eligible_at_select": true, "blocking_gate": null}
  ],
  "rejected": [
    {"business_id": "biz_...B3", "blocking_gate": "A_SUPPRESSED_EMAIL",
     "reason": "The address contact@example-sample.in opted out on 2026-06-14 via the unsubscribe link, so no email can be sent to it."}
  ],
  "counts": {"Dhule": 5, "Nashik": 7, "Jalgaon": 3, "_total": 15}
}
```

Five rules, from `05` §5.4.3 and unchanged here:

1. Re-selecting an already-selected business is a **no-op returning the existing `selection_id`**,
   `200`, not an error.
2. Every business runs `check_send_eligibility(stage='SELECT')` and the whole `Eligibility` JSON is
   stored in `selections.eligibility_snapshot`.
3. A **hard** gate means the row is not inserted; it comes back in `rejected[]` with one sentence.
4. A **soft** gate means the row is inserted with `eligible_at_select = 0` and `blocking_gate` set,
   so the workspace shows it in an attention band rather than silently dropping it.
5. `city` and `industry` are copied onto the selection row, so a later reclassification does not
   move the counts Sagar saw when he selected.

`GET /api/v1/campaigns/<id>/selection-counts` returns `05` §5.4.4's aggregate. A city with no
selections is absent from the array rather than present with `0`; the UI renders an em dash for it,
and `0` is reserved for "we counted and the answer is zero".

| Code | HTTP | When |
|---|---|---|
| `NOT_IN_CAMPAIGN` | 409 | A `business_id` has no `INCLUDED` `campaign_businesses` row for that campaign |
| `SELECTION_LIMIT` | 422 | More than 200 ids in one call. A selection that large is a script, and a script should page |
| `INVALID_ENUM` | 422 | `intent_channel` outside `EMAIL,WHATSAPP,PHONE,MANUAL` |

---

## 13.9 Outreach

`outreach_drafts`, `outreach_messages`, `outreach_approvals` and `outreach_events` are owned by
`05-outreach-workflow.md` §5.3; the draft content and the claim policy are owned by
`06-message-engine.md`. This is the group where three documents disagreed on paths, so the whole
group is restated on one scheme: **draft-scoped routes take `out_`, message-scoped routes take
`msg_`, and no route takes a bare `business_id`.**

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `POST /api/v1/outreach/prepare` | §20 PREPARE OUTREACH: enqueue one `draft_outreach` job per selection | OPERATOR | `llm` | `Idempotency-Key`; jobs also dedupe per selection | — (the job writes `MESSAGE_GENERATED`) |
| `GET /api/v1/outreach/batches/<batch_id>` | Batch progress and per-selection outcomes | OPERATOR | `read` | n/a | — |
| `GET /api/v1/outreach/workspace/<business_id>` | The §20 seven-panel workspace payload | OPERATOR | `read` | n/a | — |
| `GET /api/v1/outreach/drafts` | List drafts, filterable by `campaign_id`, `channel`, `policy_result`, `status` | OPERATOR | `read` | n/a | — |
| `GET /api/v1/outreach/drafts/<draft_id>` | One draft, raw | OPERATOR | `read` | n/a | — |
| `GET /api/v1/outreach/drafts/<draft_id>/preview` | The §27 nine-panel preview plus the preview token and the confirm nonce | OPERATOR | `read` | n/a | `MESSAGE_PREVIEWED` |
| `PUT /api/v1/outreach/drafts/<draft_id>/body` | Edit the draft; forces a fresh policy check | OPERATOR | `write` | `Idempotency-Key` | `MESSAGE_EDITED` |
| `POST /api/v1/outreach/drafts/<draft_id>/regenerate` | New draft row; the old one gets `superseded_by` | OPERATOR | `llm` | `Idempotency-Key` | `MESSAGE_REGENERATED` |
| `POST /api/v1/outreach/drafts/<draft_id>/policy-check` | Re-run the claim policy without editing | OPERATOR | `write` | Natural | `MESSAGE_POLICY_CHECKED`, plus `POLICY_BLOCK` on a block |
| `GET /api/v1/outreach/drafts/<draft_id>/audit` | The §49 AI message audit record; `?format=html` for a self-contained file | OPERATOR | `read` | n/a | — |
| `GET /api/v1/outreach/<draft_id>/explain` | The §11.9 eleven-band "explain this message" payload | OPERATOR | `read` | n/a | — |
| `GET /api/v1/messages/<message_id>/explain` | `302` to the draft's explain URL | OPERATOR | `read` | n/a | — |
| **`POST /api/v1/outreach/messages/<message_id>/send`** | **§28 CONFIRM & SEND.** Approve and queue, atomically | OPERATOR, session only | `send` | Server-minted nonce | `OUTREACH_APPROVED`, `OUTREACH_QUEUED` |
| `POST /api/v1/outreach/messages/<message_id>/cancel` | Revoke the approval and cancel the message | OPERATOR | `write` | Natural | `OUTREACH_APPROVAL_REVOKED`, `OUTREACH_CANCELLED` |
| `POST /api/v1/outreach/messages/<message_id>/record-manual` | Record a hand-sent message or a logged call (§21) | OPERATOR, session only | `send` | Server-minted nonce | `MANUAL_SEND_RECORDED` |
| `POST /api/v1/outreach/messages/<message_id>/whatsapp-link` | Issue or re-issue the `wa.me` deep link (`08` §8.6.6) | OPERATOR, session only | `send` | Natural; `reissue` is explicit | `OUTREACH_QUEUED` with `dispatch_method='WA_ME_LINK'` |
| `GET /api/v1/outreach/messages/<message_id>/whatsapp` | Channel state for the preview panel | OPERATOR | `read` | n/a | — |
| `POST /api/v1/outreach/messages/<message_id>/resolve-indeterminate` | Resolve a crashed-mid-send message (`14` §14.13.5) | OWNER | `write` | `Idempotency-Key` | `OUTREACH_SEND_INDETERMINATE` resolution |
| `GET /api/v1/outreach/messages` | List messages, filterable by `campaign_id`, `business_id`, `status`, `channel` | OPERATOR | `read` | n/a | — |
| `GET /api/v1/businesses/<business_id>/history` | §32 history: messages, events, responses, next action | OPERATOR | `read` | n/a | — |

### 13.9.1 Prepare

```http
POST /api/v1/outreach/prepare
{"campaign_id": "cmp_...01", "selection_ids": ["sel_...S1", "sel_...S2"],
 "channel": "EMAIL", "depth": "STANDARD"}
```

`202`: `{"batch_id": "bat_01JBSAMPLE0000000000000B7", "queued": 2, "skipped": 0,
"blocked": [{"selection_id": "sel_...S3", "blocking_gate": "G_MIN_DAYS", "reason": "..."}]}`.

Every selection re-runs `check_send_eligibility(stage='SELECT')` before enqueueing. One that has
become ineligible since selection moves to `state='BLOCKED'` and appears in `blocked[]` — never
silently dropped, because a row that vanishes is how a person stops trusting the tool.

### 13.9.2 Edit and regenerate

`PUT /api/v1/outreach/drafts/<draft_id>/body` takes `{"subject": "...", "body": "...",
"reason": "SAMPLE - shortened the second paragraph."}`. It writes `body_edited`, increments
`edit_count`, moves the message `PENDING_APPROVAL -> DRAFT`, and **immediately re-runs the claim
policy**, landing at `PENDING_APPROVAL` or `POLICY_BLOCKED` (`06` §6.11). It revokes any live
approval, because an approval is a signature over a specific body hash.

`POST .../regenerate` takes `{"reason": "...", "steer": "Shorter, and drop the demo offer."}` and
returns `202` with the new `draft_id`. `steer` is passed to the model as a constraint; it cannot
introduce a claim, because the binding rules in `06` §6.9 run over the output regardless of what
asked for it.

### 13.9.3 Preview

`GET /api/v1/outreach/drafts/<draft_id>/preview` returns `06` §6.11's payload plus the three fields
the confirm form needs:

```json
{
  "draft_id": "out_01JBSAMPLE000000000000D1",
  "message_id": "msg_01JBSAMPLE000000000000M1",
  "channel": "EMAIL",
  "subject": "A possible digital operations solution for ABC Hospital (SAMPLE)",
  "body": "Hello ABC Hospital team, ... (SAMPLE)",
  "body_hash": "3d1f9ac2",
  "segments": [],
  "policy": {"result": "PASS", "policy_version": "claims-v4", "violations": []},
  "ai": {"model_id": "gemini-2.5-flash", "prompt_version": "msg-email-v3",
         "confidence": "MEDIUM", "confidence_pct": 71},
  "contact": {"contact_id": "cnt_...C1", "display": "info@abc-hospital.example.invalid",
              "kind": "EMAIL", "human_verified": true},
  "history": {"messages": 0, "responses": 0, "last_contacted_at": null},
  "eligibility": {},
  "preview_token": "pvt_01JBSAMPLE00000000000T9.1d0ac7",
  "idempotency_key": "cnf_01JBSAMPLE00000000000N4",
  "confirm_blockers": [],
  "confirmation_text": "You are about to contact this business using the selected business contact.",
  "expires_at": "2026-08-27T06:11:12Z"
}
```

`idempotency_key` is minted here, server-side, and is the only value
`POST .../messages/<id>/send` will accept. `confirm_blockers` is `05` §5.13.3's list; an empty array
is what enables the button, and the server recomputes it on the send regardless.

`eligibility` carries the full `Eligibility` object of §13.10 — all gates, in precedence order, at
`stage='PREVIEW'`.

### 13.9.4 Cancel

`POST /api/v1/outreach/messages/<message_id>/cancel` takes `{"reason": "SAMPLE - wrong contact."}`.
It revokes the live approval (`revoked_at`, `revoked_by`, `revoke_reason`) and moves the message to
`CANCELLED`. Valid from `DRAFT`, `POLICY_BLOCKED`, `PENDING_APPROVAL`, `APPROVED` and `QUEUED`;
`409 ALREADY_SENT` from `SENT` and beyond, because a sent message cannot be unsent and pretending
otherwise would put a lie in the §32 history.

Cancelling a `QUEUED` message also sets `cancel_requested = 1` on its `send_email` job. The worker
checks that flag immediately before the provider call, which is the same window §13.11's gate
re-evaluation covers; the two mechanisms overlap on purpose.

`05` §5.21 calls this route `/revoke`. Renamed to `/cancel` here because the message status it
produces is `CANCELLED` and the audit action is `OUTREACH_CANCELLED`; the approval revocation is a
side effect, not the headline. Recorded in Corrections.

### 13.9.5 Record-manual

Consolidated from `05` §5.6.3 (`/outreach/drafts/<draft_id>/record-manual`) and `08` §8.6.6
(`/outreach/<message_id>/record-manual`) onto `POST /api/v1/outreach/messages/<message_id>/record-manual`.

```json
{
  "sent": true,
  "channel": "WHATSAPP",
  "sent_at": "2026-08-27T06:44:03Z",
  "edited": true,
  "final_body": "Hello ABC Hospital team, ... (SAMPLE)",
  "outcome": "SENT",
  "note": "Removed the last line, felt long in the chat window. (SAMPLE)",
  "idempotency_key": "cnf_01JBSAMPLE00000000000N4"
}
```

It is a **send path** and obeys every send-path rule: the full gate set at `stage='SEND'` inside
`BEGIN IMMEDIATE`, an `outreach_approvals` row written first, then
`PENDING_APPROVAL -> APPROVED -> QUEUED -> SENT` in the same transaction, `provider='manual'`,
`sent_by` = the human. `outcome` is `SENT | NO_ANSWER | WRONG_NUMBER | REFUSED`; anything but `SENT`
lands the message in `FAILED` with `failure_code = 'MANUAL_' + outcome`, and `WRONG_NUMBER`
additionally deactivates the contact.

`{"sent": false, "reason": "NOT_ON_WHATSAPP"}` sets `CANCELLED` and writes
`business_contacts.wa_capability = 'NOT_ON_WHATSAPP'` with source `OPERATOR`. Other reasons:
`CHANGED_MY_MIND`, `WRONG_NUMBER`, `BUSINESS_CLOSED`, `LOOKS_PERSONAL`.

**The one acknowledgeable block in the entire API.** On a `MANUAL`, `PHONE` or `WHATSAPP` manual
record where gate A blocks, the response is `409` with `"acknowledgeable": true`, and re-posting
with `"acknowledge_block": "A_SUPPRESSED_EMAIL"` records the message with `policy_override = 1`,
writes an `OUTREACH_POLICY_OVERRIDE` audit row carrying the gate result verbatim, and fires a
Telegram alert. On any system-transmit path the `acknowledge_block` field **is not in the schema**,
so supplying it is `422 UNKNOWN_FIELD`.

The reasoning, from `05` §5.6.3: recording is not sending. If Sagar phoned a business that had
opted out, the honest state is "this happened, and it should not have". The override records
history; it can never cause a transmission.

### 13.9.6 WhatsApp link issue

`POST /api/v1/outreach/messages/<message_id>/whatsapp-link` takes
`{"confirm_token": "b4d1f0a2c8e94a6f", "reissue": false}` and returns `08` §8.6.6's payload: the
`wa.me` URL, its hash, a QR data URI, the body preview and hash, and the reminder time. Three rules
from `08`, restated because they are API-level and easy to lose:

1. It re-runs `check_send_eligibility(stage='SEND')` first. An approval that was valid ten minutes
   ago is not a licence.
2. It verifies `sha256(rendered_body) == outreach_approvals.approved_body_hash` and returns
   `409 BODY_CHANGED_SINCE_APPROVAL` on any difference.
3. The link never appears in an exported report, an email or a Telegram message. It exists only
   inside an authenticated page, because §19's "no send control on the raw research result" would
   be defeated by a report carrying click-to-send links.

---

## 13.10 Eligibility

`GET /api/v1/outreach/eligibility` is the HTTP face of `05-outreach-workflow.md` §5.8's
`check_send_eligibility()`. Every control in the UI that can be disabled is disabled by this
response, and the sentence it renders comes from here rather than from the client.

| Property | Value |
|---|---|
| Method + path | `GET /api/v1/outreach/eligibility` |
| Purpose | Answer "may we contact this business, this way, right now?" with a result per gate |
| Role | OPERATOR; VIEWER gets the same gates with masked contact values |
| Rate | `read` |
| Idempotency | Read-only; the function never writes |
| Audit action | — |

Query parameters:

| Parameter | Required | Notes |
|---|---|---|
| `business_id` | yes | |
| `contact_id` | no | Absent means the per-contact gates return `SKIP`, not `PASS` |
| `channel` | no | `EMAIL \| WHATSAPP \| PHONE \| MANUAL` |
| `stage` | no | `SELECT \| PREVIEW \| SEND`, default `PREVIEW`. `SEND` from HTTP is evaluated read-only and is advisory; the authoritative `SEND` evaluation happens inside §13.11's transaction |
| `campaign_id` | no | Selects the effective `contact_policy` (`05` §5.3.1) |
| `message_id` | no | Enables gate group I |

Response `200` is `05` §5.9.12's payload verbatim — `allowed`, `blocking_code`,
`blocking_sentence`, `fingerprint`, `policy_version`, `warnings[]`, and `gates[]` carrying **every**
gate result in precedence order, never a short-circuit:

```json
{
  "business_id": "biz_01JBSAMPLE000000000000B1",
  "contact_id": "cnt_01JBSAMPLE000000000000C1",
  "channel": "EMAIL",
  "stage": "PREVIEW",
  "evaluated_at": "2026-08-27T05:41:12Z",
  "policy_version": "cp-1",
  "allowed": false,
  "blocking_code": "G_MIN_DAYS",
  "blocking_sentence": "It has been 9 days since the last message to ABC Hospital (SAMPLE); your minimum is 21.",
  "fingerprint": "9f2ce41a",
  "warnings": [
    {"gate": "F7", "code": "F_PRIOR_RESPONSE", "outcome": "WARN",
     "sentence": "ABC Hospital (SAMPLE) has replied before (LATER on 2026-08-18) - read the thread before sending again.",
     "detail": {"classification": "LATER", "received_at": "2026-08-18T10:02:00Z"},
     "evidence_ids": ["rsp_01JBSAMPLE000000000000R2"]}
  ],
  "gates": [
    {"gate": "A1", "code": "A_SUPPRESSED_BUSINESS", "outcome": "PASS",
     "sentence": "No opt-out on file for this business.", "detail": {}, "evidence_ids": []},
    {"gate": "G1", "code": "G_MIN_DAYS", "outcome": "BLOCK",
     "sentence": "It has been 9 days since the last message to ABC Hospital (SAMPLE); your minimum is 21.",
     "detail": {"days_since": 9, "min_days": 21, "last_sent_at": "2026-08-18T09:00:00Z"},
     "evidence_ids": ["msg_01JBSAMPLE000000000000M8"]}
  ]
}
```

Four contract points this endpoint must keep, because the UI is built on them:

1. **Per-gate results, always.** `gates[]` carries all 39 results from `05` §5.9.1's catalogue —
   A1-A5, B1-B2, C1-C3, D1-D5, E1-E4, F1-F7, G1-G6, H1-H5, I1-I4 — in precedence order, with
   `outcome` in `PASS | WARN | BLOCK | SKIP`. A screen that reveals one objection at a time turns
   fixing a business into whack-a-mole, which is exactly the experience §5.8.1 forbids.
2. **`SKIP` is not `PASS`.** A per-contact gate evaluated with no `contact_id` returns `SKIP`, and
   the UI renders those as "checked at preview" rather than as green ticks. Pretending an
   unevaluated gate passed is how a grid promises something the send path refuses.
3. **`blocking_sentence` is renderable verbatim.** One sentence, Sagar's vocabulary, the numbers
   filled in. It is the same string §13.11 puts in `error.message` on a `409`, so the UI has one
   string to show whether the block was found before or during the send.
4. **`fingerprint` is a hash over the `(gate, outcome)` pairs.** It is what makes drift detectable:
   the preview stores it, the send recomputes it, and a difference is why §13.11 can say "this
   changed while you were reading".

The endpoint is read-only and never writes, including no audit row. That is deliberate: it runs once
per row of a 200-row grid, and an endpoint the UI polls must not be an endpoint that grows the audit
log.

| Code | HTTP | When |
|---|---|---|
| `BUSINESS_ID_REQUIRED` | 422 | Missing `business_id` |
| `CONTACT_NOT_ON_BUSINESS` | 422 | `contact_id` belongs to a different business |
| `NOT_FOUND` | 404 | No such business |

---

## 13.11 `POST /api/v1/outreach/messages/<message_id>/send`

The single most important endpoint in the system. It is the only HTTP path in `business_radar` that
can cause a stranger to receive a message, and it is the HTTP expression of `_CONTEXT.md` invariant
1: no send path exists that does not pass through a human approval **row**.

`05-outreach-workflow.md` §5.13.4 calls this `POST /api/v1/outreach/drafts/<draft_id>/approve`;
`14-background-jobs.md` §14.8 already calls it `POST /api/v1/outreach/messages/<message_id>/send`.
This document settles on the second (rule N1: the path names the entity whose row changes), and the
rename is recorded in Corrections. Approving and queueing remain **one call and one transaction**,
exactly as `05` §5.13.5 requires. There is no separate approve step and no separate send step; §13.21
explains why splitting them would be a defect rather than a feature.

### 13.11.1 Identity card

| Property | Value |
|---|---|
| Method + path | `POST /api/v1/outreach/messages/<message_id>/send` |
| Purpose | §28 CONFIRM & SEND: revalidate everything server-side, write the approval row, move the message `PENDING_APPROVAL -> APPROVED -> QUEUED`, enqueue the transmit job |
| Blueprint | `bp_session` **only**. Not registered on `bp_token`, `bp_callback` or `bp_public` |
| Role | `OWNER` or `OPERATOR`. `VIEWER` is `403` |
| Auth | Session cookie plus `X-CSRF-Token`. `session_auth_method` must be `PASSWORD` or `PASSWORD_TOTP` |
| Rate limit | `send` bucket, 6/min. The policy caps (`daily_send_cap`, `send_min_gap_seconds`) are gates H3 and G, not throttles, and return `409` |
| Idempotency | Server-minted nonce (`cnf_...`) from the preview, plus `ux_approvals_idem`, plus the status guard, plus the job dedupe key, plus `ux_om_idempotency` |
| Audit actions | `OUTREACH_APPROVED` (CRITICAL) and `OUTREACH_QUEUED` (INFO), both inside the transaction. `OUTREACH_SENT` is written later by the worker, not by this request |
| Transaction | `BEGIN IMMEDIATE` for the whole body of the handler after validation |

### 13.11.2 Request

```http
POST /api/v1/outreach/messages/msg_01JBSAMPLE000000000000M1/send
Content-Type: application/json
X-CSRF-Token: <session csrf>

{
  "draft_id": "out_01JBSAMPLE000000000000D1",
  "preview_token": "pvt_01JBSAMPLE00000000000T9.1d0ac7",
  "idempotency_key": "cnf_01JBSAMPLE00000000000N4",
  "body_hash": "3d1f9ac2",
  "to_address_norm": "info@abc-hospital.example.invalid",
  "eligibility_fingerprint": "9f2ce41a",
  "displayed": {
    "business": true, "contact": true, "channel": true, "message": true,
    "history": true, "opt_out": true, "approval": true
  },
  "confirmation_text": "You are about to contact this business using the selected business contact."
}
```

| Field | Required | What the server does with it |
|---|---|---|
| `draft_id` | yes | Must match `outreach_messages.draft_id`. A mismatch is `422 DRAFT_MISMATCH` |
| `preview_token` | yes | Must be live, unexpired, and bound to this session and this message |
| `idempotency_key` | yes | Must be the nonce the preview minted. A client-generated value is `422 NONCE_NOT_ISSUED` |
| `body_hash` | yes | Compared against `sha256(subject_final || '\x1e' || body_final)` recomputed from the row |
| `to_address_norm` | yes | Compared against the row's `to_address_norm`, recomputed through `normalise_contact()` |
| `eligibility_fingerprint` | yes | Compared against the fingerprint of the fresh `SEND`-stage evaluation |
| `displayed` | yes | All seven §28 items must be `true` |
| `confirmation_text` | yes | Must equal the §28 sentence byte for byte; stored verbatim in `outreach_approvals.confirmation_text` |

**Every one of these is re-derived server-side and compared.** The client is not trusted to tell the
truth about what it drew; it is required to *echo* what the server issued, which is a different and
much weaker claim to have to believe. A client that lies about `displayed` fails on the preview
token, which the server issued only after rendering all seven panels and recording
`MESSAGE_PREVIEWED`.

### 13.11.3 Preconditions, revalidated server-side

The client's eligibility check is advisory and is discarded. Nineteen preconditions run again here,
in this order. The first eight are outside the transaction because they cannot change under a lock;
the rest are inside it.

| # | Precondition | Inside txn | On failure |
|---|---|---|---|
| 1 | Session valid, CSRF valid | no | `401` / `403 CSRF_INVALID` |
| 2 | Role is OWNER or OPERATOR | no | `403 FORBIDDEN` |
| 3 | `session_auth_method` in (`PASSWORD`, `PASSWORD_TOTP`) | no | `403 HUMAN_SESSION_REQUIRED` |
| 4 | Body schema valid, no unknown fields | no | `422` |
| 5 | `send` rate bucket has a token | no | `429` |
| 6 | Message exists and the caller may see it | no | `404 NOT_FOUND` |
| 7 | `draft_id` matches the message | no | `422 DRAFT_MISMATCH` |
| 8 | `confirmation_text` is the §28 sentence | no | `422 CONFIRMATION_TEXT_MISMATCH` |
| 9 | `SELECT ... FOR UPDATE` equivalent: re-read the message row under the write lock | yes | — |
| 10 | `outreach_messages.status = 'PENDING_APPROVAL'` | yes | `409 BAD_STATUS`, `detail.status` |
| 11 | Preview token live, unexpired, bound to this session and message | yes | `409 PREVIEW_STALE` |
| 12 | `body_hash` equals the recomputed hash of `COALESCE(body_edited, body)` | yes | `409 BODY_CHANGED` |
| 13 | `to_address_norm` equals the recomputed normalised address | yes | `409 ADDRESS_CHANGED` |
| 14 | `outreach_drafts.policy_result <> 'BLOCK'` and `policy_checked_body_hash` equals `body_hash` | yes | `409 CLAIM_POLICY` |
| 15 | `displayed` has all seven `true` | yes | `409 PANELS_INCOMPLETE` |
| 16 | No live handoff blocks outreach for this business (`10` §10) | yes | `409 HANDOFF_OPEN` |
| 17 | **`check_send_eligibility(stage='SEND')` returns `allowed = true`** | yes | `409 BLOCKED`, `detail.gate`, `error.message` = the gate sentence |
| 18 | `eligibility_fingerprint` equals the fresh evaluation's fingerprint | yes | `409 ELIGIBILITY_CHANGED` |
| 19 | `contact_policy.automation_mode = 'HUMAN_APPROVAL'` | yes | `409 BLOCKED`, gate `B_MODE_NOT_HUMAN_APPROVAL` |

Precondition 17 is the one the whole document exists for. It runs **inside** the write transaction,
immediately before anything is written, because the world moves between preview and send:

```
T0  09:00:10  Sagar previews msg_...M12                            -> eligibility allowed
T1  09:00:14  Sagar reviews and approves messages one at a time
T2  09:02:40  the recipient unsubscribes from a message we sent in June: their mail client
              sends the List-Unsubscribe mailto: to <base>+unsub-<token>@gmail.com (07 7.7.3)
T3  09:03:02  the next poll_inbox run reads it, resolves the token, and writes
              suppressions(scope='EMAIL', value_norm='...')            (07 7.7.5, 7.7.7)
T4  09:07:41  Sagar reaches M12 and presses CONFIRM & SEND
```

Without the re-check at T4, M12 goes to somebody who opted out five minutes ago, and every screen
the system drew was truthful at the time it drew it. Note what T2 and T3 are: **two events, not
one.** On this stack an unsubscribe is a mail we have to fetch, so the suppression lands one poll
interval (`07` §7.8.4, two minutes on the `fast` policy) after the recipient acted, not
instantaneously. That widens this window rather than closing it, which is the honest reason the
re-check is inside the transaction rather than a nicety. `05` §5.10.1 lists the five other events that
fit in the same window — an inbound `OPT_OUT`, a hard bounce pushing the bounce rate over the limit,
a manual contact from another campaign, a `contact_policy` edit in another tab, a re-verification or
a classifier-triggered `HUMAN_HANDOFF` — and every one is caught by a different gate at T4. Three of
those five also arrive through `poll_inbox`, so the same two-event latency applies to them.

Precondition 18 is the softer companion. If the gate set still allows the send but *some* gate
outcome changed since the preview, the fingerprint differs and the request is refused with
`ELIGIBILITY_CHANGED`. The UI reloads the preview and Sagar decides again with the current facts.
The alternative — sending anyway because nothing hard blocked — is a system that quietly changes
what a human approved.

### 13.11.4 The transaction

One `BEGIN IMMEDIATE`, matching `05` §5.13.5 exactly. There is no moment at which a message is
approved but not queued, and none at which it is queued but not approved.

```python
# radar/web/api/outreach.py -> radar/outreach.py

def approve_and_queue(conn, *, message_id: str, req: SendRequest,
                      session: Session, user_id: str) -> ApprovalResult:
    """Approve a message and queue its transmit job, atomically.

    Splitting these into two transactions creates a window in which outreach_messages says
    APPROVED and no job exists - a message a human signed for that will never go out, and which
    no screen reports as stuck. Splitting them the other way creates a queued message with no
    approval row, which trg_om_send_needs_approval aborts, so the failure is loud but the
    system is still wrong. One transaction is the only arrangement with no bad intermediate
    state, and the eligibility re-check has to live inside it or the lock buys nothing.
    """
    with db.transaction(conn, immediate=True):          # BEGIN IMMEDIATE
        m = load_message_for_update(conn, message_id)   # precondition 9, 10
        assert_preview_token(conn, req.preview_token, m, session)          # 11
        assert_hashes(conn, m, req.body_hash, req.to_address_norm)         # 12, 13
        assert_claim_policy(conn, m.draft_id, req.body_hash)               # 14
        assert_displayed(req.displayed)                                    # 15
        assert_no_open_handoff(conn, m.business_id)                        # 16

        elig = policy.check_send_eligibility(                              # 17
            conn, m.business_id, m.contact_id, m.channel,
            stage="SEND", campaign_id=m.campaign_id, message_id=message_id)
        if not elig.allowed:
            emit_event(conn, message_id, "ELIGIBILITY_BLOCK", actor_type="SYSTEM",
                       actor_id="web", detail={"gate": elig.blocking_code})
            audit.write(conn, action="ELIGIBILITY_BLOCK", entity="outreach_messages",
                        entity_id=message_id,
                        detail={"stage": "SEND", "gate": elig.blocking_code,
                                "eligibility_snapshot": json.loads(elig.to_json())})
            raise Blocked(elig)                                            # -> 409
        if elig.fingerprint != req.eligibility_fingerprint:                # 18
            raise EligibilityChanged(elig)

        approval_id = ids.new_id("apr")
        conn.execute(INSERT_APPROVAL, (...))            # outreach_approvals, §5.3.6
        conn.execute("UPDATE outreach_messages SET approval_id = ?, status = 'APPROVED' "
                     "WHERE id = ? AND status = 'PENDING_APPROVAL'", (approval_id, message_id))
        emit_event(conn, message_id, "APPROVED", actor_type="HUMAN", actor_id=user_id)
        audit.write(conn, action="OUTREACH_APPROVED", entity="outreach_approvals",
                    entity_id=approval_id, message_id=message_id, actor_id=user_id,
                    detail=APPROVAL_DETAIL)             # 11 §11.6.6's key list

        job_id = jobs.enqueue(conn, kind="send_email" if m.channel == "EMAIL" else "send_whatsapp",
                              dedupe_key=f"send:{message_id}",
                              payload={"message_id": message_id, "approval_id": approval_id})
        conn.execute("UPDATE outreach_messages SET status = 'QUEUED', "
                     "queued_at = strftime('%Y-%m-%dT%H:%M:%SZ','now'), sent_by = ? "
                     "WHERE id = ? AND status = 'APPROVED'", (user_id, message_id))
        emit_event(conn, message_id, "QUEUED", actor_type="SYSTEM", actor_id="web",
                   detail={"job_id": job_id})
        audit.write(conn, action="OUTREACH_QUEUED", entity="outreach_messages",
                    entity_id=message_id, detail={"job_id": job_id,
                                                  "idempotency_key": m.idempotency_key})
    return ApprovalResult(approval_id=approval_id, job_id=job_id, duplicate=False)
```

Three database-level guarantees sit under that Python and would hold even if it were wrong:

| Guarantee | Mechanism |
|---|---|
| A message cannot reach `SENT` except from `APPROVED` / `QUEUED` | `outreach_status_transitions` plus `trg_om_transition` (`05` §5.3.8) |
| A message at or past `APPROVED` must carry an `approval_id` | `CHECK (status NOT IN ('APPROVED','QUEUED','SENT','DELIVERED','BOUNCED') OR approval_id IS NOT NULL)` |
| A `SENT` message must have an `OUTREACH_SENT` audit row | `trg_om_sent_needs_audit` (`11` §11.6.7, migration `036`) |

### 13.11.5 What this endpoint does not do

It does not transmit. It enqueues. The provider call happens in the `send_email` / `send_whatsapp`
job (`14` §14.8), which re-reads the approval, re-checks the status guard
(`UPDATE ... WHERE status = 'QUEUED'`), writes `provider_send_started_at` before the call, and
writes `OUTREACH_SENT` with the §48 payload inside its own transaction.

The split is not laziness. A waitress worker held open across an SMTP round trip to
`smtp.gmail.com:587` is a request that can hang for as long as the socket does — on a laptop whose
network moves between a phone hotspot and an office Wi-Fi, that is a real event, not a hypothetical
— and a browser or a waitress channel timing out over a provider call that already succeeded is the
indeterminate case `11` §11.7.4 spends a section on. Enqueueing takes milliseconds and cannot be
indeterminate.

### 13.11.6 Success

`200` (not `201`; the approval row is an artefact of the action, not the resource the caller asked
for):

```json
{
  "approval_id": "apr_01JBSAMPLE000000000000P3",
  "message_id": "msg_01JBSAMPLE000000000000M1",
  "draft_id": "out_01JBSAMPLE000000000000D1",
  "status": "QUEUED",
  "channel": "EMAIL",
  "to_address_display": "info@abc-hospital.example.invalid",
  "queued_at": "2026-08-27T05:44:03Z",
  "job_id": "job_01JBSAMPLE000000000000J8",
  "eligibility_fingerprint": "9f2ce41a",
  "duplicate": false,
  "audit_ids": ["aud_01JBSAMPLE00000000000AA1", "aud_01JBSAMPLE00000000000AA2"],
  "next_message_id": "msg_01JBSAMPLE000000000000M2"
}
```

`next_message_id` is the next message in the review queue, so the keyboard flow in `05` §5.13.6
(`j`/`k`, `Enter`, one explicit confirm per message) needs no second request. It is a navigation
hint, never an instruction: nothing is approved by moving to it.

`"duplicate": true` with the same body and `200` is the double-click case. The second click lands on
the same "queued" screen as the first. A double click should feel like a single click, not like an
error.

### 13.11.7 Every 4xx it can return

Each row's `error.message` is rendered by the UI directly, with no client-side rewriting.

| HTTP | `error.code` | `error.message` (SAMPLE) | `error.detail` |
|---|---|---|---|
| 401 | `NOT_AUTHENTICATED` | "Your session has expired. Sign in and open the preview again." | — |
| 403 | `FORBIDDEN` | "Your account may not send outreach." | `{"required_role": "OPERATOR"}` |
| 403 | `HUMAN_SESSION_REQUIRED` | "This action can only be taken from a signed-in browser session." | `{"auth_method": "TOKEN"}` |
| 403 | `CSRF_INVALID` | "This page is out of date. Reload it and try again." | — |
| 404 | `NOT_FOUND` | "That message no longer exists." | — |
| 409 | `BAD_STATUS` | "This message is APPROVED, not waiting for your approval." | `{"status": "APPROVED"}` |
| 409 | `PREVIEW_STALE` | "Your preview expired. Reload it and check the message again." | `{"reload": true, "expired_at": "..."}` |
| 409 | `BODY_CHANGED` | "The message text changed since you previewed it. Reload and read it again." | `{"reload": true, "expected": "3d1f9ac2", "actual": "88b0e412"}` |
| 409 | `ADDRESS_CHANGED` | "The recipient address changed since you previewed it." | `{"reload": true}` |
| 409 | `CLAIM_POLICY` | "The message makes a claim the research does not support; edit it or regenerate." | `{"violations": [{"rule": "K2", "sentence_idx": 4, "finding_id": null}]}` |
| 409 | `PANELS_INCOMPLETE` | "The confirmation screen did not show everything it has to show. Reload it." | `{"missing": ["history"]}` |
| 409 | `HANDOFF_OPEN` | "ABC Hospital (SAMPLE) is a live lead you are handling personally - the system stops here." | `{"handoff_id": "hnd_..."}` |
| 409 | `BLOCKED` | the gate's sentence, verbatim | `{"gate": "A2", "code": "A_SUPPRESSED_EMAIL", "eligibility": { }}` |
| 409 | `ELIGIBILITY_CHANGED` | "Something changed while you were reading this. Reload the preview and decide again." | `{"reload": true, "changed_gates": ["F5"], "eligibility": { }}` |
| 409 | `IDEMPOTENCY_KEY_REUSED` | "This confirmation was already used for a different message." | `{"approval_id": "apr_..."}` |
| 422 | `NONCE_NOT_ISSUED` | "That confirmation code did not come from a preview of this message." | — |
| 422 | `DRAFT_MISMATCH` | "This confirmation belongs to a different draft." | — |
| 422 | `CONFIRMATION_TEXT_MISMATCH` | "The confirmation wording did not match. Reload the page." | — |
| 422 | `UNKNOWN_FIELD` | "Unexpected field: acknowledge_block." | `{"field": "acknowledge_block"}` |
| 429 | `RATE_LIMITED` | "Slow down - too many sends in the last minute." | `{"bucket": "send", "retry_after": 12}` |

Note two absences. There is no `4xx` for "the daily cap is reached" — that is `409 BLOCKED` with
gate `H_DAILY_CAP`, because a cap is a policy decision Sagar set and its sentence is
"You have sent 25 of today's 25 emails - this one goes out tomorrow." And there is no `403` for
`automation_mode`: an unsupported mode is `409 BLOCKED` with gate `B_MODE_NOT_HUMAN_APPROVAL`,
because it is a state of the world, not a permission.

### 13.11.8 Worked blocked-send response

The full envelope for the case a developer will hit first — a suppression that landed between
preview and confirm:

```json
{
  "error": {
    "code": "BLOCKED",
    "message": "The address info@abc-hospital.example.invalid opted out on 2026-08-27 via the unsubscribe link, so no email can be sent to it.",
    "detail": {
      "gate": "A2",
      "gate_code": "A_SUPPRESSED_EMAIL",
      "stage": "SEND",
      "message_id": "msg_01JBSAMPLE000000000000M1",
      "suppression": {
        "id": "sup_01JBSAMPLE00000000000S1",
        "scope": "EMAIL",
        "reason": "UNSUBSCRIBE_LINK",
        "created_at": "2026-08-27T05:39:48Z",
        "source": "unsubscribe link in msg_01JBSAMPLE000000000000M4"
      },
      "eligibility": {
        "allowed": false,
        "blocking_code": "A_SUPPRESSED_EMAIL",
        "fingerprint": "c71b0d92",
        "gates": [
          {"gate": "A1", "code": "A_SUPPRESSED_BUSINESS", "outcome": "PASS",
           "sentence": "No opt-out on file for this business.", "detail": {}, "evidence_ids": []},
          {"gate": "A2", "code": "A_SUPPRESSED_EMAIL", "outcome": "BLOCK",
           "sentence": "The address info@abc-hospital.example.invalid opted out on 2026-08-27 via the unsubscribe link, so no email can be sent to it.",
           "detail": {"suppressed_at": "2026-08-27T05:39:48Z", "reason": "UNSUBSCRIBE_LINK"},
           "evidence_ids": ["sup_01JBSAMPLE00000000000S1"]}
        ]
      },
      "message_status": "CANCELLED",
      "reload": true
    },
    "field_errors": [],
    "request_id": "req_01JBSAMPLE0000000000000002",
    "doc": "13-api-endpoints.md#131107-every-4xx-it-can-return"
  }
}
```

`message_status: "CANCELLED"` is not a courtesy. A message blocked at `stage='SEND'` moves to
`CANCELLED` in the same transaction that refused it (`05` §5.10), writes an `ELIGIBILITY_BLOCK`
event and audit row, and fires a Telegram alert. Leaving it `PENDING_APPROVAL` would leave a message
in the queue that a retry could send, which is the exact outcome the gate exists to prevent.

### 13.11.9 Idempotency, layer by layer

Four independent layers, each of which alone would prevent the duplicate, because the cost of a
duplicate here is a second cold email to a stranger (`05` §5.14).

| Layer | Mechanism | What it catches |
|---|---|---|
| 1 | `ux_approvals_idem` on `outreach_approvals(idempotency_key)`, with the nonce minted by the preview | A double-clicked button; two tabs on the same preview |
| 2 | `UPDATE ... WHERE id = ? AND status = 'PENDING_APPROVAL'` returning `rowcount = 0` | The unique index being absent or the key being reused across a rewrite |
| 3 | `ux_jobs_dedupe` on `jobs(dedupe_key)` with `dedupe_key = 'send:' || message_id` | Two enqueue attempts producing two transmit jobs |
| 4 | `ux_om_idempotency` on `outreach_messages(idempotency_key)`, and the provider's own `Idempotency-Key` header where supported | The same draft producing two message rows to one address at one sequence position; a provider double-accepting |

The double-click timeline, with SQLite's single writer serialising the two requests:

| T | Request A | Request B | Database |
|---|---|---|---|
| 0 | `POST .../send` | — | — |
| 1 | `BEGIN IMMEDIATE`; preconditions pass | arrives, blocks on the write lock | — |
| 2 | approval inserted; `PENDING_APPROVAL -> APPROVED -> QUEUED`; job enqueued | still blocked | one approval, one job |
| 3 | `COMMIT`, `200`, `duplicate: false` | acquires the lock | — |
| 4 | — | insert hits `ux_approvals_idem` | unchanged |
| 5 | — | rollback, look up the existing approval, `200` `duplicate: true` | unchanged |

The one case that is deliberately **not** a duplicate: approve, cancel, approve again. That is a
second decision. The cancel sets `revoked_at`, a fresh preview mints a fresh nonce, and the new
approval is a new row — which is correct, because §48 wants both decisions on the record.

### 13.11.10 Tests that hold this endpoint

```python
def test_send_is_registered_only_on_the_session_blueprint(app):
    """The rule from _CONTEXT.md invariant 1, as a routing assertion.

    Walks app.url_map for '/send', '/record-manual' and '/whatsapp-link' and asserts each rule's
    blueprint is bp_session. A refactor that moves one onto the token blueprint to 'make
    scripting easier' is the exact change this test exists to stop, and it is the kind of change
    that looks harmless in a diff.
    """


def test_suppression_between_preview_and_confirm_blocks(client, db):
    """Preview, then insert a suppression, then confirm. Expect 409 BLOCKED / A_SUPPRESSED_EMAIL,
    the message CANCELLED, one ELIGIBILITY_BLOCK audit row, and zero provider calls."""


def test_double_click_produces_one_approval_and_one_job(client):
    """Two concurrent POSTs with the same nonce. Expect two 200s, one outreach_approvals row,
    one jobs row, the second response carrying duplicate: true."""


def test_body_edited_in_another_tab_refuses(client, db):
    """Preview, PUT a new body from a second session, confirm with the old hash.
    Expect 409 BODY_CHANGED and no approval row - a signature over text nobody read is not a
    signature."""
```

---

## 13.12 Responses

`responses` is owned by `01-data-model.md` §1.9. The excerpt column is `body_excerpt`, never
`excerpt` (§1.2.4 D5). `_CONTEXT.md` invariant 6: the AI classifies, it never replies — which is why
there is no endpoint here that sends anything.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `GET /api/v1/responses` | List inbound replies | OPERATOR (M) | `read` | n/a | — |
| `GET /api/v1/responses/<response_id>` | One reply, full body, classification, attribution | OPERATOR (M) | `read` | n/a | — |
| `POST /api/v1/responses/<response_id>/reclassify` | Human correction of the AI's classification | OPERATOR | `write` | `Idempotency-Key` | `RESPONSE_RECLASSIFIED` |
| `POST /api/v1/responses/manual` | Paste an inbound reply the system cannot see (WhatsApp manual mode, a phone call) | OPERATOR | `write` | `Idempotency-Key` | `RESPONSE_RECEIVED` |

List filters: `business_id`, `campaign_id`, `channel`, `classification` (enum set over the thirteen
§33 values), `classification_state`, `legal_flag`, `received_from` / `received_to`, `unhandled`
(`true` returns replies with no handoff and no snooze), `q` over `body_excerpt`. Sort allow-list:
`received_at` (default `-received_at`), `classification`, `confidence_pct`.

The list row carries `effective_classification`, computed as
`COALESCE(human_classification, classification)` (`01` §1.9.2). **No consumer reads the bare
`classification` column**, and the API does not expose a field that invites one to: both raw columns
appear only on the single-response read, beside `classifier_model_id` and
`classifier_prompt_version`, where they are evidently provenance rather than the answer.

### 13.12.1 Reclassify

```json
{"classification": "DEMO_REQUESTED", "note": "SAMPLE - they asked to see it on a call."}
```

| Rule | Detail |
|---|---|
| Writes | `human_classification`, `human_classified_by`, `human_classified_at`, `human_note`, and `classification_state='HUMAN_CORRECTED'` |
| Never writes | `classification`. Overwriting the model's answer destroys the only measurement that says whether the classifier is worth its cost |
| Side effect, to `OPT_OUT` or `COMPLAINT` | A `suppressions` row for every contact point on the business, in the same transaction (`01` §1.9.3). `detail.suppressions_created[]` names them |
| Side effect, away from `OPT_OUT` | **None.** The suppression is not released. The app has no code that clears one, and this endpoint is not an exception |
| Side effect, into a handoff-triggering value | A `handoffs` row is created if none is open (`10` §10.2.1), because correcting a `NOT_INTERESTED` to `DEMO_REQUESTED` is exactly the case the AI missed |

Response `200` carries `effective_classification`, `suppressions_created[]`, `handoff_id` and
`audit_ids[]`.

The asymmetry in rows three and four is the whole point and is worth stating in an API document
rather than only in a docstring: a correction *towards* an opt-out takes effect immediately and
permanently; a correction *away* from one changes the label and nothing else.

### 13.12.2 Manual entry

`08` §8.10.5's payload, unchanged:

```json
{
  "business_id": "biz_01JBSAMPLE000000000000B1",
  "message_id": "msg_01JBSAMPLE000000000000M1",
  "channel": "WHATSAPP",
  "received_at": "2026-08-28T05:12:00Z",
  "from_display": "+91 98765 43210",
  "body_text": "Please don't message me here, use email. (SAMPLE)",
  "capture_method": "PASTED"
}
```

`201` returns the response id, the pre-LLM stop-pattern result, every suppression the paste created,
and the classification job id. The stop-pattern scan runs **before** the LLM and its result is
returned synchronously, because a reply containing "do not contact" must suppress in the request
that recorded it, not in a job that might be retried at 02:00.

| Code | HTTP | When |
|---|---|---|
| `MESSAGE_NOT_FOR_BUSINESS` | 422 | `message_id` belongs to a different business |
| `BODY_REQUIRED` | 422 | `body_text` empty |
| `DUPLICATE_RESPONSE` | 200 | Same `(channel, provider_message_id)` already stored; returns the existing row |

---

## 13.13 Handoffs

`handoffs` is owned by `10-human-handoff.md`. The won-value column is `won_value_inr`, never
`realised_value_inr` (`01` §1.2.4 D6). §34: on the five interest classifications the machine stops
and pages Sagar.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `GET /api/v1/handoffs` | The queue, filterable | OPERATOR (M) | `read` | n/a | — |
| `POST /api/v1/handoffs` | Manual creation, or re-open after a mis-close | OPERATOR | `write` | Natural via `ux_handoffs_open_business` | `HANDOFF_CREATED` |
| `GET /api/v1/handoffs/<handoff_id>` | The row plus its §34 brief | OPERATOR (M) | `read` | n/a | — |
| `GET /api/v1/handoffs/<handoff_id>/brief` | The brief alone, for the Telegram card and the print view | OPERATOR | `read` | n/a | — |
| `POST /api/v1/handoffs/<handoff_id>/acknowledge` | `OPEN -> ACKNOWLEDGED` | OPERATOR | `write` | Natural | `HANDOFF_STATE_CHANGE` |
| `POST /api/v1/handoffs/<handoff_id>/start` | `-> IN_PROGRESS` | OPERATOR | `write` | Natural | `HANDOFF_STATE_CHANGE` |
| `POST /api/v1/handoffs/<handoff_id>/close` | `-> CLOSED` with a mandatory outcome | OPERATOR | `write` | `Idempotency-Key` | `HANDOFF_STATE_CHANGE` |
| `POST /api/v1/handoffs/<handoff_id>/snooze` | Defer the SLA clock | OPERATOR | `write` | Natural | `HANDOFF_STATE_CHANGE` |
| `POST /api/v1/handoffs/<handoff_id>/note` | Append a note | OPERATOR | `write` | `Idempotency-Key` | `HANDOFF_NOTE` |
| `POST /api/v1/handoffs/<handoff_id>/demo` | Record `demo_scheduled_at` or `demo_held_at` | OPERATOR | `write` | `Idempotency-Key` | `HANDOFF_STATE_CHANGE` |
| `POST /api/v1/handoffs/<handoff_id>/proposal` | Record `proposal_sent_at`, `proposal_value_inr` | OPERATOR | `write` | `Idempotency-Key` | `HANDOFF_STATE_CHANGE` |
| `POST /api/v1/handoffs/<handoff_id>/renotify` | Force a re-page | OPERATOR | `write` | Natural, 1 per 5 min | `HANDOFF_STATE_CHANGE` |
| `GET /api/v1/funnel` | The §54 funnel, grouped by `city` or `industry` | VIEWER | `read` | n/a | — |
| `POST /api/v1/notifications/telegram/callback` | Telegram inline-button callback; registered only in `notify.telegram.mode: webhook`, which needs a public host this deploy target does not have | none (secret token) | `callback` | Natural | `HANDOFF_STATE_CHANGE` |

List filters: `state` (enum set), `priority`, `campaign_id`, `business_id`, `outcome`, `overdue`
(`true` returns rows past an SLA), `created_from` / `created_to`. Sort allow-list: `created_at`
(default `-created_at`), `priority`, `sla_ack_due_at`.

### 13.13.1 Acknowledge and close

`acknowledge` takes no body and is idempotent: acknowledging an already-acknowledged handoff returns
`200` and the current row. That matters because the same action is reachable from a Telegram inline
button and from the web UI, and a person will press both.

`close` requires an outcome and its companion field, enforced by the table's `CHECK`s:

```json
{"outcome": "WON", "won_value_inr": 240000, "note": "SAMPLE - signed for the hospital module set."}
```

| `outcome` | Required companion |
|---|---|
| `DEMO_SCHEDULED` | `demo_scheduled_at` |
| `PROPOSAL_SENT` | `proposal_sent_at` |
| `WON` | `won_value_inr` |
| `LOST` | `lost_reason` from the seven-value enum |
| `NO_RESPONSE` | only permitted when `started_at` is set (`10` §10.4) |

| Code | HTTP | When |
|---|---|---|
| `OUTCOME_REQUIRED` | 422 | `close` without `outcome` |
| `OUTCOME_COMPANION_REQUIRED` | 422 | The companion field is missing; `detail.field` names it |
| `NO_RESPONSE_NOT_STARTED` | 422 | `NO_RESPONSE` on a handoff that was never started |
| `ALREADY_CLOSED` | 409 | Re-closing. Re-opening is `POST /api/v1/handoffs` with `previous_handoff_id` |
| `HANDOFF_OPEN` | 409 | `POST /api/v1/handoffs` while one is already open for the business (`ux_handoffs_open_business`) |

### 13.13.2 The Telegram callback

`POST /api/v1/notifications/telegram/callback` exists only when `notify.telegram.mode: webhook`.
**The default transport is `getUpdates` long-polling from the `telegram_poll` job** (`10` §10.6),
and on this deploy target it is the only one that works: `_CONTEXT.md` §2 binds waitress to
`127.0.0.1` with no public hostname, so Telegram has nowhere to POST. The webhook path is specified
below because `10` §10.6 builds it, and because it is the one inbound-HTTP shape in the pack that
becomes reachable the day the app is ever hosted somewhere public — not because it is reachable now.
Its route is registered only when the config asks for it (§13.2.2).

| Property | Value |
|---|---|
| Auth | `X-Telegram-Bot-Api-Secret-Token` header, compared with `hmac.compare_digest` against the configured secret. Mismatch is `403` and a `PROVIDER_CALLBACK_REJECTED` audit row |
| Second check | `callback_query.from.id` must equal the configured operator id. An inline button is a state-changing endpoint and a bot token is a bearer credential |
| Replay | `callback_query.id` is stored and re-delivery is a no-op returning `200` |
| Body | Telegram's `Update` object; only `callback_query` with `callback_data` matching `^(ack\|start\|snz\|cls):hnd_[0-9A-HJKMNP-TV-Z]{26}$` is acted on |
| Response | Always `200` with an empty body, even on rejection, after the audit row is written. Telegram retries anything else, and a retry storm against a forged callback is worse than a silent drop |

---

## 13.14 Suppressions, and the DELETE that does not exist

`suppressions` is owned by `05-outreach-workflow.md` §5.3.2. `_CONTEXT.md` invariant 3: an opt-out
on any contact point blocks every channel for that business, forever, and **cannot be cleared by the
app**.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `GET /api/v1/suppressions` | List do-not-contact records | OWNER full, OPERATOR masked, VIEWER hashed | `read` | n/a | — |
| `POST /api/v1/suppressions` | Add a manual do-not-contact record | OPERATOR | `write` | Natural via `ux_suppressions_scope_value` | `SUPPRESSION_CREATED` |

There is no `DELETE /api/v1/suppressions/<id>`, no `PATCH`, no `POST .../release`, and no
`?released=true` parameter on any endpoint. That is not an oversight; it is the invariant.

**Why the endpoint is absent rather than restricted to OWNER.**

| Option | Why it was rejected |
|---|---|
| `DELETE`, OWNER-only | A route that exists can be reached by a CSRF bug, a mis-scoped token, a copy-pasted `fetch` in a console, or a future refactor that widens the role check. The strongest access control is a route that is not in `url_map` |
| `POST .../release` with a mandatory reason | Same objection, plus it makes releasing feel like a supported workflow. It is not a workflow; it is an exception that should require somebody to open a database session and think |
| A soft `released_at` written by the app | `trg_suppressions_release_needs_audit` already aborts any `UPDATE OF released_at` that does not name a matching `SUPPRESSION_RELEASED` audit row, and `SUPPRESSION_RELEASED` is the one action in `11` §11.6's catalogue **with no code path that can emit it**. An app endpoint would have to invent one |

What releasing actually takes, and why that is the right cost: a `sqlite3` session against
`data/radar.db` on the laptop, an
`INSERT` into `audit_log` with `action='SUPPRESSION_RELEASED'` carrying `reason_note`,
`authorised_by` and `evidence_path`, and then the `UPDATE`. The trigger checks the audit row exists
and matches the suppression id, and `trg_suppressions_no_delete` refuses any `DELETE` outright. The
person who types that is the person who has to write down why.

The API's obligation is to make the *state* visible, which it does: `GET /api/v1/suppressions` and
the `suppressed` flag on every business row and every eligibility response.

### 13.14.1 Create

```json
{"scope": "DOMAIN", "value": "abc-hospital.example.invalid",
 "business_id": "biz_01JBSAMPLE000000000000B1",
 "reason": "MANUAL",
 "source": "Phone call from the practice manager, 27 Aug (SAMPLE)",
 "detail": {"spoken_to": "practice manager"}}
```

| Field | Rule |
|---|---|
| `scope` | `BUSINESS \| EMAIL \| PHONE \| WHATSAPP \| DOMAIN` |
| `value` | Raw; normalised server-side by `normalise_contact()` into `value_norm`. The response echoes both, so Sagar can see what was actually stored |
| `reason` | `MANUAL`, `DNC_LIST` or `LEGAL_REQUEST` from this endpoint. `UNSUBSCRIBE_LINK`, `REPLY_OPT_OUT`, `COMPLAINT` and `BOUNCE_HARD` are written only by their own code paths and are `422 REASON_NOT_MANUAL` here |
| `source` | Required, >= 10 chars, human-readable provenance |

`201` on create, `200` with the existing row when a live suppression already covers
`(scope, value_norm)`. Adding the same opt-out twice is not an error; it is a person being careful.

### 13.14.2 List

Filters: `scope`, `reason`, `business_id`, `created_from` / `created_to`, `q` over `source`.
Masking by role, because a do-not-contact list is a list of people who asked to be left alone:

| Role | `value_norm` rendered as |
|---|---|
| OWNER | the value |
| OPERATOR | masked (`i***@abc-hospital.example.invalid`, `+9198*****10`) |
| VIEWER | `sha256` prefix only, 12 hex chars |

`11-audit-architecture.md` §11.6.11 already refuses to put `value_norm` in a `SUPPRESSION_CREATED`
audit row for the same reason; this is the read-side twin of that rule.

---

## 13.15 Reports and exports

`report_exports` is owned by `11-audit-architecture.md` §11.11.1 **as amended by**
`01-data-model.md` §1.2.1: the file-format column is `fmt`, the report subject is `scope` +
`scope_key`, the content hash is `content_sha256`, and a row is written `PENDING` before the file
exists. `03-html-report.md`'s `022_report_exports.sql` and its own `kind` column are gone.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `POST /api/v1/report_exports` | Generate one or more formats for a campaign or a filter set (§41) | OPERATOR; `include_contacts=true` is OWNER | `export` | `Idempotency-Key`; jobs also dedupe | `REPORT_GENERATED` / `DATA_EXPORTED` (by the job) |
| `GET /api/v1/report_exports` | The §42 archive listing | VIEWER | `read` | n/a | — |
| `GET /api/v1/report_exports/<rex_id>` | Stream the archived file, byte-for-byte as generated | VIEWER | `read` | n/a | `REPORT_DOWNLOADED` (`best_effort = 1`) |
| `GET /api/v1/report_exports/<rex_id>/payload` | Stream `data_rel_path`, the canonical aggregate payload | OWNER | `read` | n/a | — |
| `GET /api/v1/report_exports/<rex_id>/verify` | Recompute both hashes from disk | OWNER | `read` | n/a | — |
| `DELETE /api/v1/report_exports/<rex_id>` | Delete the file; tombstone the row | OWNER | `write` | Natural | `REPORT_FILE_DELETED` |
| `GET /api/v1/campaigns/<campaign_id>/report` | `ReportData` as JSON, live | VIEWER | `read` | n/a | — |
| `POST /api/v1/campaigns/<campaign_id>/report` | Re-generate the campaign HTML report | OPERATOR | `export` | Job dedupe key | `REPORT_GENERATED` |
| `GET /api/v1/reports/daily/<day_ist>` | The §43 daily report as JSON | VIEWER | `read` | n/a | — |
| `POST /api/v1/reports/daily` | Re-run the daily report for a given day | OPERATOR | `export` | Job dedupe key | `REPORT_GENERATED` |
| `GET /api/v1/health` | The export's liveness probe (§3.1.4) | none | `public` | n/a | — |

### 13.15.1 Generate

```json
{
  "campaign_id": "cmp_01JBSAMPLE0000000000000001",
  "formats": ["HTML", "CSV", "XLSX", "PDF"],
  "scope": "CAMPAIGN",
  "scope_key": null,
  "filters_json": {"city": ["dhule"], "score_min": 70},
  "include_contacts": false,
  "title": "Dhule healthcare, 70+ (SAMPLE)"
}
```

| Field | Rule |
|---|---|
| `formats` | Non-empty subset of `HTML, CSV, XLSX, PDF, JSON`. One `report_exports` row per format, each with its own `rex_id` and its own `fmt` |
| `scope` | `CAMPAIGN \| DAILY \| CITY \| INDUSTRY \| TOP_OPPORTUNITIES \| SUBJECT_ACCESS \| AUDIT` |
| `filters_json` | The §39 filters, using §13.6.1's parameter names, applied server-side to the same query the live grid runs |
| `include_contacts` | OWNER only. `true` forces `contains_pii = 1`, which the table's `CHECK` then forbids from `retention_class='PERMANENT'`, and the job writes `DATA_EXPORTED` rather than `REPORT_GENERATED` |

`202`: `{"job_id": "job_...", "exports": [{"rex_id": "rex_...", "fmt": "HTML", "status": "PENDING"}]}`.
The rows exist before the files do, so a crashed build is visible rather than invisible
(`01` §1.2.1 Amendment 2). The UI polls `GET /api/v1/jobs/<job_id>` and offers the download when the
export flips to `READY` — a 5,000-row export takes seconds, and a request that holds a waitress
worker for three seconds is a request that blocks the small thread pool this single process has, on a
machine that is also running the research workers.

### 13.15.2 Archive listing and download

`GET /api/v1/report_exports` filters: `campaign_id`, `fmt` (enum set), `scope`, `scope_key`,
`report_date_from` / `report_date_to`, `include_deleted` (default `false`), `status`. Sort
allow-list: `generated_at` (default `-generated_at`), `bytes`, `row_count`.

`11-audit-architecture.md` §11.11.6 documents this filter as `?kind=`. It is `?fmt=` here, following
`01` §1.2.1 Amendment 1. Recorded in Corrections.

**There is no `/download` suffix.** `07-email-integration.md` §7.11 names
`GET /api/v1/report_exports/<rex_id>/download`; the ratified path is
`GET /api/v1/report_exports/<rex_id>`, because rule N4 admits a verb suffix only where REST has no
shape for the operation, and `GET` on a file resource is exactly that shape. Recorded in Corrections.

`GET /api/v1/report_exports/<rex_id>` streams the bytes with `Content-Disposition: attachment`,
`X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox`, and both hashes as
`X-Content-SHA256` and `X-Data-SHA256`. A `PURGED` or tombstoned row returns
`410 EXPORT_PURGED` with `detail.content_sha256` and `detail.deleted_reason`, so the archive can
still prove what existed even after retention removed the file.

`DELETE` sets `deleted_at` and `deleted_reason='MANUAL'` and removes the file.
`trg_report_exports_no_delete` refuses any attempt to remove the row itself: files get deleted, rows
get tombstoned.

### 13.15.3 `GET /api/v1/health`

The one endpoint an exported HTML report is allowed to call (`03` §3.1.4). It is unauthenticated,
CORS-enabled for `GET` only, and returns the minimum that answers "is the app up":

```json
{"status": "ok", "version": "radar 0.4.2", "db": "ok", "workers": 2, "at": "2026-08-27T05:44:03Z"}
```

It carries no campaign name, no counts and no business data, because an exported report can be
opened on any machine and this response is readable by whatever else is on that machine's network.
`db: "degraded"` with `status: "ok"` is possible and means reads work and writes do not; the export
treats anything other than a `200` as "app absent" and leaves its action links inert.

---

## 13.16 Jobs

`jobs` and `job_runs` are owned by `14-background-jobs.md`. The console is the jobs tab of
`/settings`; there is no `/jobs` UI route.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `GET /api/v1/jobs` | List, filterable by `state`, `type`, `lane`, `campaign_id`, `business_id`, `batch_id`, `trace_id`, `last_error_class`, `finished_from` / `finished_to` | OPERATOR | `read` | n/a | — |
| `GET /api/v1/jobs/<job_id>` | The row plus every `job_runs` attempt | OPERATOR | `read` | n/a | — |
| `POST /api/v1/jobs/<job_id>/retry` | `FAILED -> QUEUED`, `run_after = now`, `max_attempts = attempts + 1` | OPERATOR | `write` | Natural | — |
| `POST /api/v1/jobs/<job_id>/cancel` | Set `cancel_requested = 1` | OPERATOR | `write` | Natural | — |
| `POST /api/v1/jobs/<job_id>/revive` | `DEAD -> QUEUED`; `{"reason": "..."}` required | OWNER | `write` | `Idempotency-Key` | `JOB_REVIVED` |
| `POST /api/v1/jobs/retry-batch` | `{"job_ids": [...]}` or `{"type", "error_class", "since"}` | OPERATOR | `write` | `Idempotency-Key` | `JOB_RETRY_BATCH` |
| `GET /api/v1/jobs/stats` | `v_jobs_queue_depth` plus 24 h outcome counts and today's LLM spend | OPERATOR | `read` | n/a | — |
| `GET /api/v1/jobs/dead` | `v_jobs_dead` | OPERATOR | `read` | n/a | — |

Sort allow-list: `created_at` (default `-created_at`), `finished_at`, `priority`, `attempts`.

Retry semantics are `14` §14.12.2's, unchanged: one more attempt rather than a reset to zero, so
the history of what already failed stays true; `last_error` preserved; `retried_by` and `retried_at`
written into `jobs.result`.

Two refusals worth naming, both from `14`:

| Code | HTTP | When |
|---|---|---|
| `REVIVE_FORBIDDEN_FOR_SEND` | 409 | `type = 'send_email'`. `error.message` names the correct route, `POST /api/v1/outreach/messages/<message_id>/resolve-indeterminate`. Making the unsafe thing hard to do by accident is cheaper than making it recoverable |
| `NOT_RETRYABLE` | 409 | The job is `SUCCEEDED`, `RUNNING` or `CANCELLED`; `detail.state` says which |

All eight routes are session-authenticated. The API-token authenticator cannot reach them, for the
same reason `05` §5.3.6 keeps approvals off the token blueprint: a token that can requeue a
`send_email` job is a token that can send.

### 13.16.1 `GET /api/v1/quota`

`15-ui-wireframe.md` §15.16 needs this and no other document defines it, so it is ratified here.
`_CONTEXT.md` §2 consequence 2 is the reason it exists: on the free tier there is no bill to cap,
there is a requests-per-minute and requests-per-day ceiling that returns 429, and hitting it
**pauses research and resumes tomorrow**. A pause the operator cannot see is indistinguishable from
a hang, which is the failure this endpoint prevents.

| Property | Value |
|---|---|
| Method + path | `GET /api/v1/quota` |
| Role | VIEWER. It carries counts, ceilings and timestamps — no business name, no contact value, nothing a mask would apply to |
| Rate | `read`. The global strip polls it on the same timer the page already uses; it is one indexed read over `v_spend_today` plus one `rate_buckets` row |
| Audit | — |
| Sources | `v_spend_today` and `spend_ledger` for the day counts (`14-background-jobs.md` §14.10), `rate_buckets` for the live per-minute figure, `config.yaml` `llm.free_tier.*` for the ceilings |

```json
{
  "day_ist": "2026-08-27",
  "model_id": "gemini-2.5-flash",
  "requests_used": 231,
  "requests_cap": 250,
  "rpm_used": 6,
  "rpm_cap": 10,
  "tokens_today": 412880,
  "tokens_cap": null,
  "reset_at_ist": "2026-08-28T12:30:00+05:30",
  "paused": true,
  "paused_reason": "RATE_LIMIT",
  "paused_campaign_ids": ["cmp_01JBSAMPLE0000000000000001"],
  "by_kind": [
    {"purpose": "RESEARCH", "requests": 188, "tokens": 351200},
    {"purpose": "DRAFT",    "requests": 31,  "tokens": 48900},
    {"purpose": "CLASSIFY", "requests": 12,  "tokens": 12780}
  ]
}
```

SAMPLE figures throughout. Four rules the payload obeys:

| Rule | Why |
|---|---|
| **The ceilings come from `config.yaml`, never from a constant in the view.** `requests_cap` and `rpm_cap` are `llm.free_tier.requests_per_day` and `requests_per_minute` | Google changes free-tier limits without notice, and a number baked into a response is a lie the day they do (`15` §15.16.2 makes the same point about the template) |
| `tokens_cap` is `null` on this tier, and `null` means "no ceiling", not "unknown" | Rendering `412,880 / 0` would be the worst of both readings |
| `paused` is derived from real rows — `campaigns.status = 'PAUSED' AND paused_reason = 'RATE_LIMIT'` — not from `requests_used >= requests_cap` | The quota can be exhausted with nothing running, and a campaign can be paused for `MANUAL`. Two different facts, reported separately |
| When the LLM has not been called today, every count is `0` and not `null` | `_CONTEXT.md` invariant 5 is about metrics with **no data**. A count over a day that has begun is a real measurement whose value is zero |

`by_kind[]` groups `spend_ledger` by its `detail` JSON `purpose` key (`RESEARCH`, `DRAFT`,
`CLASSIFY`), which is what `15` §15.16.2's "what used it today" block renders. A purpose with no
requests is **absent from the array**, not present with `0`, matching the selection-counts rule in
§13.4.

The two controls on `15` §15.16.2's tab are not new routes: `Resume paused campaigns now` is
`POST /api/v1/campaigns/<campaign_id>/start` per paused campaign, and `Pause all research` is
`POST /api/v1/campaigns/<campaign_id>/cancel`'s milder sibling — an amendment request, recorded in
Open questions, because `campaigns` has a `paused_reason` but §13.4 has no route that sets it to
`MANUAL`.

**There is no `PUT /api/v1/quota` and no way to raise a ceiling over HTTP.** The ceiling is Google's.
An endpoint that appeared to edit it would be an endpoint that edits our belief about it, which is
the more expensive of the two mistakes.

---

## 13.17 Settings

`04-verification-workflow.md` §4.9.1 refers to one untyped `POST /api/v1/settings`. That is replaced
by typed sub-resources, because `contact_policy`, the channel switches and the templates have
different roles, different audit actions and different blast radii.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `GET /api/v1/settings/contact_policy` | The effective policy, and the `GLOBAL` and per-campaign rows behind it | OWNER | `read` | n/a | — |
| `PUT /api/v1/settings/contact_policy` | Update §31 frequency, §29 windows, verification freshness, approval TTL, caps | OWNER | `write` | `Idempotency-Key` | `CONFIG_CHANGED`, plus `POLICY_VERSION_CHANGED` |
| `PUT /api/v1/settings/contact_policy/automation_mode` | The §46 dial, on its own route | OWNER | `write` | `Idempotency-Key` | `AUTOMATION_MODE_CHANGED` |
| `GET /api/v1/settings/channels` | Channel switches, and the from-address the outreach account actually sends as | OWNER | `read` | n/a | — |
| `PUT /api/v1/settings/channels` | `email_enabled`, `whatsapp_enabled`, `whatsapp_api_enabled`, `phone_enabled`, `manual_enabled` | OWNER | `write` | `Idempotency-Key` | `CONFIG_CHANGED`; `SEND_DISABLED_CHANGED` when a switch flips |
| `GET /api/v1/settings/templates` | Message template versions and their hashes | OPERATOR | `read` | n/a | — |
| `GET /api/v1/whatsapp/templates` | Local mirror plus Meta status (`08` §8.11) | OPERATOR | `read` | n/a | — |
| `POST /api/v1/whatsapp/templates` | Create a `LOCAL_DRAFT` | OWNER | `write` | `Idempotency-Key` | `TEMPLATE_CHANGED` |
| `POST /api/v1/whatsapp/templates/<template_id>/submit` | Submit to Meta for approval | OWNER | `write` | Natural | `TEMPLATE_CHANGED` |
| `POST /api/v1/whatsapp/templates/sync` | Force a sync with Meta | OWNER | `write` | Natural | — |
| `GET /api/v1/whatsapp/health` | Quality rating, tier, name status, caps, switches — **states, never secrets** | OWNER | `read` | n/a | — |
| `GET /api/v1/whatsapp/optins` | The opt-in ledger, filterable | OPERATOR | `read` | n/a | — |
| `POST /api/v1/businesses/<business_id>/whatsapp-optin` | Record an opt-in with its evidence | OPERATOR | `write` | `Idempotency-Key` | `CONFIG_CHANGED` |
| `GET /api/v1/businesses/<business_id>/whatsapp-optin` | The live opt-in, or `404` | OPERATOR | `read` | n/a | — |
| `POST /api/v1/whatsapp/optins/<optin_id>/revoke` | Revoke an opt-in | OPERATOR | `write` | Natural | `CONFIG_CHANGED` |
| `GET /api/v1/settings/users` | The user list | OWNER | `read` | n/a | — |
| `POST /api/v1/settings/users` | Create a user | OWNER | `write` | `Idempotency-Key` | `USER_CREATED` |
| `POST /api/v1/settings/users/<user_id>/disable` | Disable; never delete | OWNER | `write` | Natural | `USER_DISABLED` |
| `POST /api/v1/erasure` | Open a DPDP erasure request; returns a scope preview | OWNER | `write` | `Idempotency-Key` | `ERASURE_REQUESTED` |
| `POST /api/v1/erasure/<erasure_id>/execute` | Execute it | OWNER | `write` | `Idempotency-Key` | `ERASURE_EXECUTED` |

### 13.17.1 `PUT /api/v1/settings/contact_policy`

Body carries only the fields being changed, plus `scope` (`GLOBAL` or a `cmp_` id) and a required
`reason`. Two rules:

1. **A campaign-scoped row may only be stricter than `GLOBAL`.** `05` §5.3.1's `effective_policy()`
   takes the stricter value per field, and this endpoint refuses to *store* a looser one rather than
   storing it and quietly ignoring it: `422 CAMPAIGN_POLICY_LOOSER` with
   `detail.fields[{"field": "min_days_between_outreach", "global": 21, "requested": 7}]`.
2. **Tightening takes effect immediately, including on already-approved messages.** The gates re-run
   at `stage='SEND'` (§13.11), so a message approved under the old policy and blocked under the new
   one is cancelled at send time with an `ELIGIBILITY_BLOCK`. The response says how many queued
   messages the change would affect, so the change is made with that number visible:
   `{"policy_version": "cp-2", "queued_messages_affected": 3}`.

**`email_sending_domain` is not a settable field, and `GET .../channels` returns the from-address
read-only.** `_CONTEXT.md` §4 binds the outreach identity to a dedicated free Gmail account: there is
no custom domain, SPF/DKIM/DMARC are Google's, and the from-address is whatever
`OUTREACH_GMAIL_ADDRESS` is configured as at boot. A writable sending-domain setting is a leftover
from the deleted custom-domain design, and a UI field that appears to change the from-address but
cannot is worse than no field at all. `07-email-integration.md` §7.14 deletes `sending_domain` from
the config schema for the same reason.

`PUT .../automation_mode` is its own route because it is the one setting that changes what the
product is. In v1 it accepts only `MANUAL` and `HUMAN_APPROVAL`; `SEMI_AUTOMATED` and
`FULLY_AUTOMATED` are `409 MODE_NOT_IMPLEMENTED`, which is the HTTP twin of
`trg_contact_policy_v1_mode`. §13.21 records why there is no route that can raise the dial.

---

## 13.18 Auth

`users` is owned by `01-data-model.md` §1.10. The mechanism — password hashing, TOTP, session
lifetimes — is owned by `12-security-model.md`; this is the surface.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `POST /api/v1/auth/login` | Exchange credentials for a session cookie | none | `auth` | Not idempotent | `LOGIN_SUCCEEDED` / `LOGIN_FAILED` / `LOGIN_LOCKED` |
| `POST /api/v1/auth/logout` | Destroy the session | any | `write` | Natural | `LOGOUT` |
| `GET /api/v1/auth/session` | Who am I, what may I do | any | `read` | n/a | — |
| `POST /api/v1/auth/unlock` | Clear `locked_at` on an idle-locked session by re-proving the **password** (`12` §12.4.4) | any | `auth` | Natural — unlocking an unlocked session is `200` | `SESSION_UNLOCKED` |
| `POST /api/v1/auth/revoke-all` | Revoke every live session for the user | any for self, OWNER for another user via `{"user_id": "usr_..."}` | `write` | Natural | `LOGOUT` per row, `reason='REVOKE_ALL'` |
| `POST /api/v1/auth/password` | Change own password | any | `write` | Not idempotent | `PASSWORD_CHANGED` |
| `POST /api/v1/auth/totp/enrol` | Begin TOTP enrolment; returns a provisioning URI once | any | `write` | Not idempotent | `TOTP_ENROLLED` |
| `POST /api/v1/auth/totp/confirm` | Confirm with a code | any | `write` | Not idempotent | `TOTP_ENROLLED` |

```http
POST /api/v1/auth/login
{"email": "sagar@example.invalid", "password": "...", "totp": "123456"}
```

```json
{"user_id": "usr_01JBSAMPLE000000000000U1", "display_name": "Sagar", "role": "OWNER",
 "auth_method": "PASSWORD_TOTP", "must_change_password": false,
 "session_expires_at": "2026-08-27T13:44:03Z"}
```

| Code | HTTP | When | Note |
|---|---|---|---|
| `INVALID_CREDENTIALS` | 401 | Wrong email, wrong password, wrong TOTP, or no such user | **One code for all four.** A distinguishable "no such user" turns the audit log's `username_sha256` protection into theatre by making the endpoint itself an account oracle |
| `TOTP_REQUIRED` | 401 | Password correct, TOTP enrolled, code absent | Safe to distinguish: the caller already proved the password |
| `ACCOUNT_LOCKED` | 401 | `users.locked_until` in the future | `detail.unlock_at` |
| `PASSWORD_CHANGE_REQUIRED` | 403 | `must_change_password = 1` | The session is created but every route except `/auth/password` returns this |
| `RATE_LIMITED` | 429 | `auth` bucket | Per IP **and** per `email_norm`, so one attacker cannot lock a real account out of its own IP budget |

`GET /api/v1/auth/session` returns the user, the role, and the **permission list the UI uses to
decide what to render**. That list is advisory: every route enforces its own role, and a UI that
renders a button it should not have rendered gets a `403` rather than an effect.

### 13.18.1 Unlock and revoke-all

Both are `12-security-model.md` §12.4.4's, given their HTTP shape here.

| Property | `POST /api/v1/auth/unlock` |
|---|---|
| When it applies | `sessions.locked_at` is set, because `last_seen_at` fell outside `security.session_idle_minutes` (default 30). The session is **locked, not destroyed** — the page, the filters and the draft Sagar was reading are all still there |
| What it re-proves | The **password**, and only the password. Not TOTP: a second factor at every thirty-minute gap is the control that gets turned off in a week, and the factor that matters at the send button is re-proved separately by the §12.4.4 step-up |
| Body | `{"password": "..."}` |
| Rate bucket | `auth`, not `write` — this is a credential check and belongs in the bucket that throttles credential checks |
| Refusals | `401 INVALID_CREDENTIALS` (the same single code as login, for the same reason); `401 SESSION_EXPIRED` when the absolute lifetime has passed, which is a logout and not an unlock; `403 PASSWORD_CHANGE_REQUIRED` |
| What a locked session may still call | `GET /api/v1/auth/session` and this route. **Every other route returns `401 SESSION_LOCKED`**, including every read. A locked session that can still list businesses is a lock that protects nothing on a laptop somebody else is sitting in front of |

`POST /api/v1/auth/revoke-all` sets `revoked_at` and `revoked_reason='REVOKE_ALL'` on every live
session for the user and returns `{"revoked": 3}`. It is also fired automatically by
`POST /api/v1/auth/password` and by a role change, so the endpoint is the manual door onto a path the
system already walks. Revoking your own sessions includes the one making the request: the response is
`200` and the next request is `401`, which is the intended behaviour for the "I left it logged in
somewhere" case that the button exists for. Passing another user's `user_id` is OWNER-only and writes
the same rows with the acting user in `audit_log.actor_id`.

---

## 13.19 Inbound: there are no webhooks

An earlier revision of this section specified `POST /api/v1/webhooks/<provider>` over `postmark`,
`ses`, `resend` and `whatsapp`, with per-provider signature schemes, a Postmark URL-secret scheme
validated against an `X-Forwarded-For` header set by a reverse proxy, and a handler that enqueued
`process_webhook_event`. **All of it is deleted.**

`_CONTEXT.md` §2 settles the deploy target: Flask under waitress bound to `127.0.0.1` on Sagar's
laptop, no VPS, no public hostname, no reverse proxy, and the machine is not on 24 hours a day.
Nothing on the public internet can reach this process, so *"any design that depends on a provider
POSTing to us is void"*. Four other documents already recorded the consequence and this one was the
last to be edited:

| Document | What it already says |
|---|---|
| `07-email-integration.md` §7.2.3 | Postmark is disqualified outright for this use case; the honest answer fails their signup review |
| `07-email-integration.md` §7.9 | The SES/SNS webhook path, `email_webhook_events` and `radar/web/webhooks.py` are **deleted**. A bounce is a DSN in our own mailbox |
| `14-background-jobs.md` §14.8.14 | `process_webhook_event` is **removed** from the job registry. `poll_inbox` is the only automatic inbound path |
| `12-security-model.md` §12.1, §12.9 | "Inbound network: **none.** No webhooks, no public endpoint, no reverse proxy" and "`bp_webhook` does not exist on this stack" |

The routes were not merely useless. A route that cannot be reached is still a route in `url_map`, and
this particular set carried signature verification, raw-body persistence and a job enqueue — the
largest unauthenticated attack surface in the application, defending nothing. §13.21 records both
paths so `test_absent_routes_stay_absent` keeps them gone.

**What replaces them: a poll.** `poll_inbox` (`14` §14.8.13) opens an IMAP connection to
`imap.gmail.com:993`, fetches what is new since its stored cursor, and does itself everything the
webhook handlers were going to do — attribution (`07` §7.8.8), DSN parsing for bounces (`07` §7.9.6),
unsubscribe-token resolution (`07` §7.7.5), and enqueueing `classify_response`. There is no HTTP
route in that path at any point, which is why this section has no route table.

| Old inbound path | New inbound path | Owner |
|---|---|---|
| `POST /api/v1/webhooks/postmark` — delivery, bounce, complaint | `poll_inbox` reads the DSN out of the mailbox | `07` §7.9 |
| `POST /api/v1/webhooks/ses` — SNS `Bounce` / `Complaint` | same | `07` §7.9.2, §7.9.4 |
| `POST /api/v1/webhooks/resend` | same | `07` §7.9 |
| `POST /u/<message_id>/<token>` — unsubscribe | `poll_inbox` resolves the `+unsub-<token>` address | `07` §7.7, §13.20 |
| `POST /api/v1/webhooks/whatsapp` — status and inbound messages | Nothing automatic. `MANUAL_LINK` mode has Sagar paste the reply into `POST /api/v1/responses/manual` (§13.12.2) | `08` §8.6.8, §8.10.5 |
| `GET /api/v1/webhooks/whatsapp` — Meta's verification handshake | Not registered. `08` §8.9.1 specifies the handshake for the day the `CLOUD_API` gate opens **on a host that has a public HTTPS callback URL**, which this one does not | `08` §8.8.12 |

**The WhatsApp pair is specified in `08` and absent here on purpose.** `08` §8.8 builds the Cloud API
path and gates it behind a recorded opt-in; §8.9 specifies its webhooks in full. That work is not
wasted and it is not contradicted — it is simply unreachable on this deploy target, and the endpoint
registry is where "unreachable" has to be stated as "not registered". `08` §8.9 should carry the
caveat explicitly; recorded in Corrections.

**Latency is the honest cost, and it is small.** A webhook arrives in seconds; a poll arrives within
one interval (`07` §7.8.4: two minutes on the `fast` policy) plus however long the laptop was closed.
The two places that cost anything are the unsubscribe-to-suppression window (§13.11.3's walkthrough
now shows it) and the bounce-rate gate, and both are handled by re-checking eligibility inside the
send transaction rather than by trusting a timestamp.

### 13.19.1 Inbound triage: the three routes that do exist

`07` §7.8.10: an inbound message that cannot be attributed goes to a human. It is never attributed by
inference and never dropped. These are the routes that human uses, and they are ordinary
session-authenticated writes rather than anything provider-facing.

| Method + path | Purpose | Role | Rate | Idempotency | Audit action |
|---|---|---|---|---|---|
| `GET /api/v1/inbound` | The `UNMATCHED` band above the batch list on `/outreach` | OPERATOR (M) | `read` | n/a | — |
| `POST /api/v1/inbound/<inb_id>/attach` | Attach an unmatched inbound message to a message or a business | OPERATOR | `write` | Natural — a second attach on an already-attached row returns `200` and the existing `responses` row | `RESPONSE_RECEIVED` with `match_rule='M8'` |
| `POST /api/v1/inbound/<inb_id>/ignore` | Mark it spam or misdirected | OPERATOR | `write` | Natural | `RESPONSE_UNMATCHED` resolution, `detail.reason` |

`attach` takes `{"message_id": "msg_..."}` **or** `{"business_id": "biz_..."}` and exactly one of
them; both, or neither, is `422 ATTACH_TARGET_REQUIRED`. It creates the `responses` row with
`attribution='OPERATOR'`, `attribution_confidence='HIGH'` and `match_rule='M8'`, then enqueues
`classify_response`. `ignore` takes `{"reason": "..."}`, required and >= 10 chars, and sets
`inbound_emails.state='IGNORED'`.

| Code | HTTP | When |
|---|---|---|
| `ATTACH_TARGET_REQUIRED` | 422 | Neither `message_id` nor `business_id`, or both |
| `ALREADY_ATTACHED` | 200 | The row already has a `responses` row; returns it, because attaching twice is a person being careful |
| `ALREADY_IGNORED` | 200 | `state='IGNORED'` already |
| `BAD_STATE` | 409 | Attaching a row that was ignored, or ignoring one that was attached. `detail.state` says which; the fix is a database operation, not a second click |

Two rules that are not obvious from the payloads:

1. **`attribution='OPERATOR'` is a distinct value, not `'HEURISTIC'` with a high number.** The funnel
   and the classifier-quality measurement both need to know which attributions a human made, and a
   confidence score cannot carry that. `07` §7.8.10 fixes `M8` as the rule id for exactly this
   reason.
2. **Attaching does not capture the sender's address as a contact.** `07` §7.8.11: the address
   appeared in order to answer one message, and writing a `business_contacts` row for it is
   processing for a purpose the person never saw. It surfaces on the verification screen as a
   *suggested* contact, and a human ticking the §16 checklist item is what creates the row.

The `inbound_emails` table and the `inb_` id prefix are `07-email-integration.md` §7.8.5's, and both
are amendment requests against `01-data-model.md` §1.1.3 that this document's routes now depend on.

---

## 13.20 Unsubscribe: a `mailto:`, not a route

**There is no unsubscribe endpoint. There is no `/u/` blueprint. This section exists to say so and to
name the one mechanism that replaces it**, because the previous revision of this document specified
`GET /u/<message_id>/<token>`, `POST /u/<message_id>/<token>` and `POST /u/one-click/...` as "the
one-click endpoint every outbound email carries", and a developer building from a route registry
builds what the registry lists. A first-contact commercial email whose unsubscribe link resolves to
nothing is a broken promise to the recipient, a failed `_CONTEXT.md` §4 obligation, and the single
fact most likely to turn one annoyed recipient into the complaint that closes the Gmail account.

`_CONTEXT.md` §4 requires a working unsubscribe on every outbound message and requires it to write an
opt-out row automatically. Both obligations stand. What changed is that `_CONTEXT.md` §2 removed the
public HTTPS host those routes needed:

| Mechanism | Requires | Available here |
|---|---|---|
| `https://{host}/u/<token>` in the body | A public HTTPS host the recipient's browser can resolve | **No** |
| RFC 8058 `List-Unsubscribe-Post: List-Unsubscribe=One-Click` | A public HTTPS URI that accepts `POST` from the recipient's *mail provider* | **No** |
| A button on the free GitHub Pages identity page | Somewhere for it to POST that can write `data/radar.db` | **No** (`07` §7.4.4) |
| `mailto:` in `List-Unsubscribe`, per RFC 2369 | A mailbox we read | **Yes** |
| "Reply with STOP" in the visible body | A mailbox we read | **Yes** |

`07-email-integration.md` §7.7 is the sole specification of the replacement and this section does not
restate it. In outline: the token is `hmac_sha256(secret, f"{message_id}|{contact_norm}")[:32]`,
stored on `outreach_drafts.unsubscribe_token`; it rides in the **local part** of the reply address
(`<base>+unsub-<token>@gmail.com`) because that is the one place a mail client cannot drop it; the
header carries a single `mailto:` URI; and the primary path is now the visible plain-text STOP line
in the body, with the header as the backup rather than the other way round. `poll_inbox` resolves the
token against `07` §7.7.2's `RESOLVE_TOKEN_SQL`, and `policy.suppress(scope='EMAIL',
reason='UNSUBSCRIBE_LINK', source_ref=message_id)` writes the `suppressions` row, the `UNSUBSCRIBED`
outreach event and the `UNSUBSCRIBE_RECEIVED` audit row in one transaction.

Four things follow that belong in an endpoint registry rather than in an email document:

| # | Consequence for this document |
|---|---|
| 1 | **`List-Unsubscribe-Post` is not emitted.** `07`'s transport check `T8` BLOCKs any message carrying that header. Offering RFC 8058 without an HTTPS URI produces a client-rendered button that POSTs nowhere, which is worse than no button |
| 2 | **A draft carrying `https://{sending_domain}/u/{token}` is BLOCKED, not repaired.** `06-message-engine.md` rule `R1` refuses it at the claim-policy gate. That rule exists precisely because this document used to publish the route |
| 3 | **The `public` rate bucket now covers only `GET /api/v1/health`** (§13.2.8), and `bp_public` serves no HTML at all |
| 4 | **The `410` row in §13.2.5 no longer has an HTTP caller.** It survives as the case `poll_inbox` records when a token resolves to a message row erased under DPDP retention; `07` §7.7.6 handles that by notifying a human the same day rather than by rendering a page |

**Why the audit trail is not weaker for it.** The old `POST /u/...` row recorded `remote_ip` and
`user_agent` as "the proof a complaint disputes". Neither was worth much — a link scanner in a
corporate mail gateway has an IP and a user agent too, which is why that design needed a GET/POST
split and a seven-layer crawler mitigation to stop an appliance unsubscribing people who never read
the mail. What replaces them is better evidence: a real message, from a real mailbox, carrying a
token only a recipient of that message could hold, retained as `.eml.gz` for `P3Y` (`07` §7.8.5). The
`UNSUBSCRIBE_RECEIVED` audit row carries `token_sha256`, `message_id`, the `inb_` id and
`received_at`, and never the raw address.

**Why this is more reliable than the routes it replaces, not less.** The `/u/` design failed whenever
the laptop was closed, whenever a mail gateway prefetched the link, and whenever a proxy stripped the
URL. The `mailto:` design fails only if the mailbox stops being read — and the mailbox is also how
replies, bounces and complaints arrive, so it is the one component whose failure is already loud and
already alarmed. `_CONTEXT.md` §2: *"This is the only unsubscribe mechanism in the build and it must
be reliable."* One mechanism, one failure mode, one alarm.

---

## 13.21 The endpoints that do not exist

This section is a deliverable, not an appendix. Every row is a route a competent developer will
reach for, will not find, and will be tempted to add. The absence is the design.

| Route a developer will reach for | Why it is absent | Use instead |
|---|---|---|
| `POST /api/v1/businesses/<id>/send` | §19, stated as a route table. No endpoint accepts a `business_id` and transmits. A path shaped like this is one refactor away from a "quick send" button on the research grid, which is the exact thing §45 forbids | Verify, select, prepare, preview, then `POST /api/v1/outreach/messages/<message_id>/send` |
| `POST /api/v1/outreach/messages/<id>/send` **without** a preview-minted `idempotency_key` | The nonce is the proof a preview was rendered, and the preview is where `MESSAGE_PREVIEWED` is written. No nonce means no evidence a human read the message | `GET .../drafts/<id>/preview` first; it mints the nonce |
| A separate `POST .../approve` followed by `POST .../send` | Two calls means two transactions and two bad intermediate states: approved-but-never-queued (a signed message that never goes out and no screen reports as stuck), or queued-without-approval (which `trg_om_send_needs_approval` aborts — loud, but the system is still wrong) | The one call in §13.11, which does both in one `BEGIN IMMEDIATE` |
| `POST /api/v1/outreach/approve-batch`, `POST /api/v1/outreach/send-all` | §45's entire content is that a human decision stands between research and contact. One click producing fifteen `outreach_approvals` rows is one decision wearing fifteen costumes | The keyboard review queue at `/outreach?batch=<batch_id>`: full preview each, `j`/`k` to move, an explicit confirm per message. Fifteen approvals means fifteen decisions |
| `POST /api/v1/verifications/bulk` with `action: "VERIFY"` | Same reason, on the other gate. The endpoint exists and rejects the value as its **first statement**, before parsing the row list, so the refusal cannot be reached by a body that is otherwise valid | `POST /api/v1/verifications/<id>/submit`, one business at a time, past the thirteen-step ladder |
| `DELETE /api/v1/suppressions/<id>`, `POST .../release`, `PATCH .../suppressions` | `_CONTEXT.md` invariant 3: opt-out is permanent and the app cannot clear it. A route that exists can be reached by a CSRF bug, a mis-scoped token, or a refactor that widens a role check. `trg_suppressions_no_delete` and `trg_suppressions_release_needs_audit` are the floor; the missing route is the ceiling | A `sqlite3` session on the laptop, a `SUPPRESSION_RELEASED` audit row written by hand with `reason_note` and `authorised_by`, then the `UPDATE`. §13.14 |
| `POST /api/v1/webhooks/<provider>` for `postmark`, `ses`, `resend` | **No public ingress.** `_CONTEXT.md` §2: waitress binds `127.0.0.1`, there is no VPS, no public hostname and no reverse proxy, so nothing on the internet can reach this process. Postmark is separately disqualified by `07` §7.2.3, and `process_webhook_event` was removed from the job registry by `14` §14.8.14. A signature-verifying, raw-body-persisting, job-enqueueing handler that nobody can call is attack surface defending nothing | `poll_inbox` over IMAP. `07` §7.9 parses bounces and complaints out of DSNs in our own mailbox; §13.19 |
| `POST /api/v1/webhooks/whatsapp`, `GET /api/v1/webhooks/whatsapp` | Same reason. `08` §8.9 specifies both in full for the gated `CLOUD_API` path, and both need a public HTTPS callback URL that this deploy target does not have. The v1 WhatsApp channel is `MANUAL_LINK` (`08` §8.6), which has no inbound leg at all | `POST /api/v1/responses/manual` (§13.12.2) for a pasted reply; `08` §8.8.12 for what opening the gate would require |
| `GET /u/<message_id>/<token>`, `POST /u/<message_id>/<token>`, `POST /u/one-click/<message_id>/<token>` | **No public HTTPS endpoint, so RFC 8058 one-click cannot be offered and a body link would resolve to nothing.** An unsubscribe URL in a first-contact commercial email that goes nowhere is the single most damaging defect available to this system. `06` rule `R1` BLOCKs any draft carrying `https://{sending_domain}/u/{token}`; `07` check `T8` BLOCKs a `List-Unsubscribe-Post` header | `mailto:` per RFC 2369: `List-Unsubscribe: <mailto:...+unsub-<token>@gmail.com?subject=unsubscribe>` plus the visible STOP line, ingested by `poll_inbox`. `07` §7.7, §13.20 |
| `PUT /api/v1/quota`, `POST /api/v1/quota/reset`, or anything that raises `requests_cap` | The ceiling is Google's and lives in `config.yaml` so a changed free-tier limit can be corrected in one place. An endpoint that appeared to edit it would edit our belief about it, and the campaign would then run into a 429 the UI said could not happen | Wait for the reset, or reduce `research_depth`. §13.16.1 |
| `PUT /api/v1/settings/contact_policy/automation_mode` with `SEMI_AUTOMATED` or `FULLY_AUTOMATED` | v1 has no non-human approval source, so storing a mode it cannot honour would mean a screen claiming the machine may send when nothing can produce the approval row. The route exists; the values are `409 MODE_NOT_IMPLEMENTED`, matching `trg_contact_policy_v1_mode` | Nothing. Raising the dial is a migration that drops the trigger plus an implementation of what the mode means (`05` §5.20.3) |
| `GET /api/v1/contacts`, `GET /api/v1/businesses?include_contacts=1`, `GET /api/v1/export/contacts.csv` | A bulk contact list is the artefact DPDP purpose-limitation is about, and one that leaves the system with no record of who took it is the failure nobody notices. No list endpoint returns a contact **value** for any role, including OWNER | One business at a time via `?reveal=contacts`, which writes `CONTACTS_REVEALED`; or `POST /api/v1/report_exports` with `include_contacts=true`, which is OWNER-only, forces `contains_pii = 1`, and writes `DATA_EXPORTED` |
| `POST /api/v1/responses/<id>/reply` | `_CONTEXT.md` invariant 6: the AI classifies inbound replies and never answers them. An interested lead stops the machine and pages Sagar (§34, §55) | Read the handoff, reply from your own mail client, then `POST /api/v1/handoffs/<id>/start` |
| `POST /api/v1/businesses/<id>/status` | `businesses.status` is `04`'s ten-state machine, written by exactly one function (`radar/verify.py::set_status()`) behind a transition table and four triggers. A general status setter is that machine with the rules removed | The specific transitions: `/submit`, `/skip`, `/unskip`, `/reopen`, `/revoke-verification` |
| `DELETE /api/v1/businesses/<id>`, `DELETE /api/v1/campaigns/<id>` | Almost nothing in this schema is deleted (`01` §1.1.2). A deleted business takes its suppressions, its attempt count and its rejection with it, and the next campaign rediscovers it clean — which is the failure §1.2.2 exists to prevent | `POST .../archive` for a campaign; `REJECTED` with `is_permanent` for a business; `POST /api/v1/erasure` for a DPDP subject request |
| `PATCH /api/v1/report_exports/<id>` | An archived report whose identity can be edited is not an archive. `trg_report_exports_identity_immutable` refuses the `UPDATE` | Generate a new export. `superseded_by` links them |
| `POST /api/v1/audit/...` anything | `audit_log` is append-only with four immutability triggers and a hash chain. An endpoint that writes to it directly would be an endpoint for writing history | `audit.write()` inside the transaction of the thing being recorded |
| `POST /api/v1/jobs/<id>/revive` for `type='send_email'` | Reviving an indeterminate send re-enters the one path where "did the provider accept it?" is genuinely unknown, and a wrong answer sends a stranger the same cold email twice | `POST /api/v1/outreach/messages/<id>/resolve-indeterminate`, which reconciles against the provider before deciding |
| Any transmit route on `bp_token` | An API token is a bearer credential. `outreach_approvals.session_auth_method` admits only `PASSWORD` and `PASSWORD_TOTP`, so a token-authenticated send fails on a database `CHECK` even if routing let it through | A browser session |

Two tests keep this table true rather than aspirational:

```python
def test_no_endpoint_sends_from_a_business_id(app):
    """A route that takes business_id must not reach the transmit path.

    Walks app.url_map, and for every rule whose arguments include 'business_id', asserts that
    radar.outreach.send_message is not reachable from its view function's call graph. This test
    is the machine-readable form of spec 19, and it is the one that catches the helpful refactor
    that adds a convenience route six months from now.
    """


def test_absent_routes_stay_absent(app):
    """Asserts that every path in 13.21's table resolves to 404 (or, for the two that exist with
    forbidden values, to the documented 4xx). A route added by accident fails this test with the
    path in the message, which is a faster explanation than a code review."""


def test_no_route_outside_the_three_blueprints(app):
    """Walks app.url_map and asserts every rule belongs to bp_session, bp_token or bp_public -
    plus bp_callback when notify.telegram.mode is 'webhook'.

    This is the test that keeps 13.19 true after the person who reads 08's webhook section
    decides to 'just wire it up'. There is no host for a provider to POST to, so a fifth
    blueprint is not a feature that arrived early; it is an unauthenticated handler nobody can
    reach and nobody is reviewing.
    """


def test_no_https_unsubscribe_url_is_ever_rendered(app, db):
    """Renders every message template with a fixture draft and asserts no output contains
    'https://' followed by '/u/', and that no outbound message carries List-Unsubscribe-Post.

    07's R1 and T8 already block a draft that grows one. This test blocks the template that
    would produce it, because the failure is silent at the point it matters: the recipient
    clicks, nothing happens, and the first anybody hears is a complaint.
    """
```

---

## 13.22 OpenAPI 3.1 skeleton

`radar/web/openapi.py` builds this document from the route table and serves it at
`GET /api/v1/openapi.json` (OPERATOR). It is generated rather than hand-maintained, and a test
asserts that every rule in `app.url_map` under `/api/v1` appears in it and vice versa.

The paths section below is printed in flow style for density. Two conventions apply throughout and
are not repeated per operation: every path parameter is the `$ref` in `components/parameters` whose
name matches it (`{campaign_id}` -> `CampaignId`, and so on), and every operation inherits
`security: [{sessionCookie: []}]` unless it declares otherwise.

```yaml
openapi: 3.1.0
info:
  title: business_radar API
  version: "1.0.0"
  description: >
    Control surface for the AI Business Opportunity and Software Sales Platform.
    RESEARCH -> REPORT -> VERIFY -> SELECT -> PERSONALIZE -> PREVIEW -> CONFIRM -> SEND.
    No endpoint transmits a message without an outreach_approvals row signed by a human session.
servers: [{url: 'http://127.0.0.1:8080/api/v1'}]
security: [{sessionCookie: []}]
tags: [{name: campaigns}, {name: research}, {name: businesses}, {name: verification},
       {name: selection}, {name: outreach}, {name: eligibility}, {name: responses},
       {name: inbound}, {name: handoffs}, {name: suppressions}, {name: reports},
       {name: jobs}, {name: quota}, {name: settings}, {name: auth}, {name: public}]

paths:
  # --- campaigns -------------------------------------------------------------------
  /campaigns:
    get:  {operationId: listCampaigns, tags: [campaigns], parameters: [{$ref: '#/components/parameters/Limit'}, {$ref: '#/components/parameters/Cursor'}, {$ref: '#/components/parameters/Sort'}], responses: {'200': {$ref: '#/components/responses/CampaignPage'}}}
    post: {operationId: createCampaign, tags: [campaigns], requestBody: {$ref: '#/components/requestBodies/CampaignCreate'}, responses: {'201': {$ref: '#/components/responses/Campaign'}, '409': {$ref: '#/components/responses/Conflict'}, '422': {$ref: '#/components/responses/Unprocessable'}}}
  /campaigns/{campaign_id}:
    get: {operationId: getCampaign, tags: [campaigns], responses: {'200': {$ref: '#/components/responses/Campaign'}, '404': {$ref: '#/components/responses/NotFound'}}}
  /campaigns/{campaign_id}/start:
    post: {operationId: startCampaign, tags: [campaigns], responses: {'202': {$ref: '#/components/responses/Campaign'}, '409': {$ref: '#/components/responses/Conflict'}}}
  /campaigns/{campaign_id}/cancel:
    post: {operationId: cancelCampaign, tags: [campaigns], responses: {'200': {$ref: '#/components/responses/Campaign'}}}
  /campaigns/{campaign_id}/archive:
    post: {operationId: archiveCampaign, tags: [campaigns], responses: {'200': {$ref: '#/components/responses/Campaign'}}}
  /campaigns/{campaign_id}/stats:
    get: {operationId: getCampaignStats, tags: [campaigns], responses: {'200': {description: Funnel plus city and industry comparisons; nulls, never zeros}}}
  /campaigns/{campaign_id}/progress:
    get: {operationId: getCampaignProgress, tags: [campaigns], responses: {'200': {description: Progress hint, never a rendered fact}}}
  /campaigns/{campaign_id}/events:
    get: {operationId: streamCampaignEvents, tags: [campaigns], responses: {'200': {description: text/event-stream}}}
  /campaigns/{campaign_id}/selectable:
    get: {operationId: listSelectable, tags: [selection], responses: {'200': {$ref: '#/components/responses/BusinessPage'}}}
  /campaigns/{campaign_id}/selection-counts:
    get: {operationId: getSelectionCounts, tags: [selection], responses: {'200': {description: Per-city counts; a city with none is absent, not zero}}}
  /campaigns/{campaign_id}/coverage:
    get: {operationId: getCampaignCoverage, tags: [campaigns], parameters: [{name: city, in: query, schema: {type: string}}, {name: category, in: query, schema: {type: string}}, {name: band, in: query, schema: {type: string}}], responses: {'200': {description: 'discovery_coverage rows; coverage_pct and denominator are null when denominator_kind is NONE'}}}
  /campaigns/{campaign_id}/report:
    get:  {operationId: getReportData, tags: [reports], responses: {'200': {description: ReportData}}}
    post: {operationId: regenerateReport, tags: [reports], responses: {'202': {description: Job enqueued}}}

  # --- research --------------------------------------------------------------------
  /research/runs/{research_run_id}:
    get: {operationId: getResearchRun, tags: [research], responses: {'200': {description: One run with findings and sources}}}

  # --- businesses ------------------------------------------------------------------
  /businesses:
    get:
      operationId: listBusinesses
      tags: [businesses]
      description: The section 39 eleven filters, as query parameters. See 13.6.1.
      parameters:
        - {name: campaign_id, in: query, schema: {type: string}}
        - {name: membership, in: query, schema: {type: string, enum: [INCLUDED, EXCLUDED, ALL], default: INCLUDED}}
        - {name: city,       in: query, description: 'filter 1',  schema: {type: string}}
        - {name: industry,   in: query, description: 'filter 2',  schema: {type: string}}
        - {name: size,       in: query, description: 'filter 3',  schema: {type: string}}
        - {name: score_min,  in: query, description: 'filter 4',  schema: {type: integer, minimum: 0, maximum: 100}}
        - {name: score_max,  in: query, schema: {type: integer, minimum: 0, maximum: 100}}
        - {name: include_unscored, in: query, schema: {type: boolean, default: true}}
        - {name: website,    in: query, description: 'filter 5',  schema: {type: string}}
        - {name: dm_min,     in: query, description: 'filter 6',  schema: {type: integer}}
        - {name: dm_max,     in: query, schema: {type: integer}}
        - {name: include_unassessed, in: query, schema: {type: boolean, default: true}}
        - {name: confidence, in: query, description: 'filter 7',  schema: {type: string}}
        - {name: verification, in: query, description: 'filter 8', schema: {type: string}}
        - {name: contact,    in: query, description: 'filter 9',  schema: {type: string}}
        - {name: outreach,   in: query, description: 'filter 10', schema: {type: string}}
        - {name: discovered_from, in: query, description: 'filter 11', schema: {type: string, format: date}}
        - {name: discovered_to,   in: query, schema: {type: string, format: date}}
        - {name: category,   in: query, schema: {type: string}}
        - {name: q,          in: query, schema: {type: string}}
        - {$ref: '#/components/parameters/Limit'}
        - {$ref: '#/components/parameters/Cursor'}
        - {$ref: '#/components/parameters/Sort'}
      responses: {'200': {$ref: '#/components/responses/BusinessPage'}}
  /businesses/{business_id}:
    get:   {operationId: getBusiness, tags: [businesses], parameters: [{name: reveal, in: query, schema: {type: string, enum: [contacts]}, description: Writes CONTACTS_REVEALED}], responses: {'200': {$ref: '#/components/responses/Business'}, '404': {$ref: '#/components/responses/NotFound'}}}
    patch: {operationId: reclassifyBusiness, tags: [businesses], responses: {'200': {$ref: '#/components/responses/Business'}, '409': {$ref: '#/components/responses/Conflict'}}}
  /businesses/{business_id}/detail:
    get: {operationId: getBusinessDetail, tags: [businesses], responses: {'200': {description: Business plus findings, sources, opportunity, contacts, history}}}
  /businesses/{business_id}/research:
    get:  {operationId: getBusinessResearch, tags: [research], responses: {'200': {description: Run, findings keyed by kind, sources}}}
    post: {operationId: rerunResearch, tags: [research], responses: {'202': {description: Job enqueued}, '409': {$ref: '#/components/responses/Conflict'}}}
  /businesses/{business_id}/sources:
    get:  {operationId: listSources, tags: [research], responses: {'200': {description: The section 14 source panel}}}
    post: {operationId: recordSource, tags: [research], responses: {'201': {description: Source recorded}}}
  /businesses/{business_id}/history:
    get: {operationId: getOutreachHistory, tags: [outreach], responses: {'200': {description: Messages, events, responses}}}
  /businesses/{business_id}/readiness:
    get: {operationId: getContactReadiness, tags: [verification], responses: {'200': {description: ContactReadiness}}}
  /businesses/{business_id}/contacts:
    get: {operationId: listContacts, tags: [businesses], responses: {'200': {description: Contact points, masked unless reveal=1}}}
  /businesses/{business_id}/contacts/{contact_id}/confirm:
    post: {operationId: confirmContact, tags: [verification], responses: {'200': {description: human_verified set}}}
  /businesses/{business_id}/verification:
    get: {operationId: getVerificationForm, tags: [verification], responses: {'200': {description: The section 15 screen payload}}}
  /businesses/{business_id}/verifications:
    get: {operationId: listVerifications, tags: [verification], responses: {'200': {description: Prior verifications}}}
  /businesses/{business_id}/skip:
    post: {operationId: skipBusiness, tags: [verification], responses: {'200': {$ref: '#/components/responses/Business'}}}
  /businesses/{business_id}/unskip:
    post: {operationId: unskipBusiness, tags: [verification], responses: {'200': {$ref: '#/components/responses/Business'}}}
  /businesses/{business_id}/reopen:
    post: {operationId: reopenBusiness, tags: [verification], responses: {'200': {$ref: '#/components/responses/Business'}}}
  /businesses/{business_id}/revoke-verification:
    post: {operationId: revokeVerification, tags: [verification], summary: Re-verify, responses: {'200': {$ref: '#/components/responses/Business'}}}
  /businesses/{business_id}/whatsapp-optin:
    get:  {operationId: getWhatsappOptin, tags: [settings], responses: {'200': {description: Live opt-in}, '404': {$ref: '#/components/responses/NotFound'}}}
    post: {operationId: recordWhatsappOptin, tags: [settings], responses: {'201': {description: Opt-in recorded}}}

  # --- verification ----------------------------------------------------------------
  /verifications:
    post: {operationId: openVerification, tags: [verification], responses: {'200': {description: Draft opened or resumed}}}
  /verifications/queue:
    get: {operationId: getVerificationQueue, tags: [verification], responses: {'200': {$ref: '#/components/responses/BusinessPage'}}}
  /verifications/{verification_id}/checks/{check_key}:
    put: {operationId: answerCheck, tags: [verification], parameters: [{name: check_key, in: path, required: true, schema: {type: string, enum: [IDENTITY_CORRECT, IN_TARGET_CITY, CATEGORY_CORRECT, APPEARS_OPERATIONAL, CONTACT_LEGITIMATE, RESEARCH_RELEVANT, OPPORTUNITY_REASONABLE, OUTREACH_APPROPRIATE, NO_DNC_RECORD]}}], responses: {'200': {description: Answered}}}
  /verifications/{verification_id}/sources/{source_id}/visited:
    post: {operationId: markSourceVisited, tags: [verification], responses: {'204': {description: Recorded}}}
  /verifications/{verification_id}/sources/{source_id}/waive:
    post: {operationId: waiveSource, tags: [verification], responses: {'200': {description: Waived}}}
  /verifications/{verification_id}/submit:
    post: {operationId: submitVerification, tags: [verification], summary: The only writer of a VERIFIED verdict, responses: {'200': {description: Verdict recorded}, '409': {$ref: '#/components/responses/Conflict'}, '422': {$ref: '#/components/responses/Unprocessable'}}}
  /verifications/{verification_id}/abandon:
    post: {operationId: abandonVerification, tags: [verification], responses: {'200': {description: Abandoned}}}
  /verifications/bulk:
    post: {operationId: bulkVerificationAction, tags: [verification], description: 'action is REJECT | SKIP | UNSKIP | REQUEUE. VERIFY is refused before the body is parsed.', responses: {'200': {description: Applied and rejected lists}, '400': {$ref: '#/components/responses/Conflict'}}}

  # --- selection -------------------------------------------------------------------
  /selections:
    get:  {operationId: listSelections, tags: [selection], responses: {'200': {description: Selection page}}}
    post: {operationId: createSelections, tags: [selection], responses: {'200': {description: created and rejected lists}}}
  /selections/{selection_id}:
    delete: {operationId: removeSelection, tags: [selection], responses: {'200': {description: Soft-removed}}}

  # --- outreach --------------------------------------------------------------------
  /outreach/prepare:
    post: {operationId: prepareOutreach, tags: [outreach], responses: {'202': {description: Batch enqueued}}}
  /outreach/batches/{batch_id}:
    get: {operationId: getBatch, tags: [outreach], responses: {'200': {description: Batch progress}}}
  /outreach/workspace/{business_id}:
    get: {operationId: getWorkspace, tags: [outreach], responses: {'200': {description: The section 20 seven panels}}}
  /outreach/drafts:
    get: {operationId: listDrafts, tags: [outreach], responses: {'200': {description: Draft page}}}
  /outreach/drafts/{draft_id}:
    get: {operationId: getDraft, tags: [outreach], responses: {'200': {$ref: '#/components/responses/Draft'}}}
  /outreach/drafts/{draft_id}/preview:
    get: {operationId: previewDraft, tags: [outreach], summary: Mints the preview token and the confirm nonce, responses: {'200': {description: The section 27 preview}}}
  /outreach/drafts/{draft_id}/body:
    put: {operationId: editDraft, tags: [outreach], responses: {'200': {$ref: '#/components/responses/Draft'}}}
  /outreach/drafts/{draft_id}/regenerate:
    post: {operationId: regenerateDraft, tags: [outreach], responses: {'202': {description: New draft enqueued}}}
  /outreach/drafts/{draft_id}/policy-check:
    post: {operationId: policyCheckDraft, tags: [outreach], responses: {'200': {description: Policy result}}}
  /outreach/drafts/{draft_id}/audit:
    get: {operationId: getMessageAudit, tags: [outreach], responses: {'200': {description: The section 49 AI message audit record}}}
  /outreach/{draft_id}/explain:
    get: {operationId: explainMessage, tags: [outreach], responses: {'200': {description: The eleven bands}}}
  /messages/{message_id}/explain:
    get: {operationId: explainMessageByMessage, tags: [outreach], responses: {'302': {description: Redirect to the draft explain URL}}}
  /outreach/messages:
    get: {operationId: listMessages, tags: [outreach], responses: {'200': {description: Message page}}}
  /outreach/messages/{message_id}/send:
    post:
      operationId: confirmAndSend
      tags: [outreach]
      summary: CONFIRM & SEND - approve and queue, atomically
      description: >
        Revalidates every precondition server-side, including a fresh SEND-stage eligibility
        evaluation inside the write transaction. Writes outreach_approvals, moves the message
        PENDING_APPROVAL -> APPROVED -> QUEUED, enqueues the transmit job. Session auth only;
        this operation is not registered on the bearer-token blueprint.
      requestBody: {$ref: '#/components/requestBodies/SendConfirm'}
      responses:
        '200': {$ref: '#/components/responses/SendResult'}
        '403': {$ref: '#/components/responses/Forbidden'}
        '409': {$ref: '#/components/responses/Blocked'}
        '422': {$ref: '#/components/responses/Unprocessable'}
        '429': {$ref: '#/components/responses/RateLimited'}
  /outreach/messages/{message_id}/cancel:
    post: {operationId: cancelMessage, tags: [outreach], responses: {'200': {$ref: '#/components/responses/Message'}, '409': {$ref: '#/components/responses/Conflict'}}}
  /outreach/messages/{message_id}/record-manual:
    post: {operationId: recordManualSend, tags: [outreach], responses: {'200': {$ref: '#/components/responses/Message'}, '409': {$ref: '#/components/responses/Blocked'}}}
  /outreach/messages/{message_id}/whatsapp-link:
    post: {operationId: issueWhatsappLink, tags: [outreach], responses: {'200': {description: wa.me link, QR and hashes}, '409': {$ref: '#/components/responses/Blocked'}}}
  /outreach/messages/{message_id}/whatsapp:
    get: {operationId: getWhatsappState, tags: [outreach], responses: {'200': {description: Channel state}}}
  /outreach/messages/{message_id}/resolve-indeterminate:
    post: {operationId: resolveIndeterminate, tags: [outreach], responses: {'200': {$ref: '#/components/responses/Message'}}}
  /outreach/eligibility:
    get:
      operationId: checkEligibility
      tags: [eligibility]
      parameters:
        - {name: business_id, in: query, required: true, schema: {type: string}}
        - {name: contact_id,  in: query, schema: {type: string}}
        - {name: channel,     in: query, schema: {$ref: '#/components/schemas/Channel'}}
        - {name: stage,       in: query, schema: {type: string, enum: [SELECT, PREVIEW, SEND], default: PREVIEW}}
        - {name: campaign_id, in: query, schema: {type: string}}
        - {name: message_id,  in: query, schema: {type: string}}
      responses: {'200': {$ref: '#/components/responses/Eligibility'}}

  # --- responses, handoffs, suppressions -------------------------------------------
  /responses:
    get: {operationId: listResponses, tags: [responses], responses: {'200': {$ref: '#/components/responses/ResponsePage'}}}
  /responses/manual:
    post: {operationId: recordManualResponse, tags: [responses], responses: {'201': {description: Recorded; stop-pattern suppressions applied synchronously}}}
  /responses/{response_id}:
    get: {operationId: getResponse, tags: [responses], responses: {'200': {$ref: '#/components/responses/Response'}}}
  /responses/{response_id}/reclassify:
    post: {operationId: reclassifyResponse, tags: [responses], responses: {'200': {$ref: '#/components/responses/Response'}}}
  /inbound:
    get: {operationId: listInbound, tags: [inbound], description: 'Unmatched inbound mail awaiting a human. There is no webhook; poll_inbox fills this table. See 13.19.', responses: {'200': {description: Inbound page; sender masked by role}}}
  /inbound/{inb_id}/attach:
    post: {operationId: attachInbound, tags: [inbound], description: 'Exactly one of message_id or business_id.', responses: {'201': {description: responses row created with attribution OPERATOR, match_rule M8}, '200': {description: Already attached; returns the existing row}, '409': {$ref: '#/components/responses/Conflict'}, '422': {$ref: '#/components/responses/Unprocessable'}}}
  /inbound/{inb_id}/ignore:
    post: {operationId: ignoreInbound, tags: [inbound], responses: {'200': {description: state IGNORED}, '409': {$ref: '#/components/responses/Conflict'}}}
  /handoffs:
    get:  {operationId: listHandoffs, tags: [handoffs], responses: {'200': {description: Handoff page}}}
    post: {operationId: createHandoff, tags: [handoffs], responses: {'201': {$ref: '#/components/responses/Handoff'}, '409': {$ref: '#/components/responses/Conflict'}}}
  /handoffs/{handoff_id}:
    get: {operationId: getHandoff, tags: [handoffs], responses: {'200': {$ref: '#/components/responses/Handoff'}}}
  /handoffs/{handoff_id}/brief:
    get: {operationId: getHandoffBrief, tags: [handoffs], responses: {'200': {description: The section 34 brief}}}
  /handoffs/{handoff_id}/acknowledge:
    post: {operationId: acknowledgeHandoff, tags: [handoffs], responses: {'200': {$ref: '#/components/responses/Handoff'}}}
  /handoffs/{handoff_id}/start:
    post: {operationId: startHandoff, tags: [handoffs], responses: {'200': {$ref: '#/components/responses/Handoff'}}}
  /handoffs/{handoff_id}/close:
    post: {operationId: closeHandoff, tags: [handoffs], responses: {'200': {$ref: '#/components/responses/Handoff'}, '422': {$ref: '#/components/responses/Unprocessable'}}}
  /handoffs/{handoff_id}/snooze:
    post: {operationId: snoozeHandoff, tags: [handoffs], responses: {'200': {$ref: '#/components/responses/Handoff'}}}
  /handoffs/{handoff_id}/note:
    post: {operationId: addHandoffNote, tags: [handoffs], responses: {'201': {description: Note added}}}
  /handoffs/{handoff_id}/demo:
    post: {operationId: recordDemo, tags: [handoffs], responses: {'200': {$ref: '#/components/responses/Handoff'}}}
  /handoffs/{handoff_id}/proposal:
    post: {operationId: recordProposal, tags: [handoffs], responses: {'200': {$ref: '#/components/responses/Handoff'}}}
  /handoffs/{handoff_id}/renotify:
    post: {operationId: renotifyHandoff, tags: [handoffs], responses: {'200': {$ref: '#/components/responses/Handoff'}}}
  /funnel:
    get: {operationId: getFunnel, tags: [handoffs], parameters: [{name: campaign_id, in: query, schema: {type: string}}, {name: group_by, in: query, schema: {type: string, enum: [city, industry]}}], responses: {'200': {description: The section 54 funnel}}}
  /suppressions:
    get:  {operationId: listSuppressions, tags: [suppressions], responses: {'200': {description: Suppression page; values masked by role}}}
    post: {operationId: createSuppression, tags: [suppressions], description: There is no DELETE, PATCH or release operation on this resource. See 13.14., responses: {'201': {description: Created}, '200': {description: Already suppressed}}}

  # --- reports and jobs ------------------------------------------------------------
  /report_exports:
    get:  {operationId: listExports, tags: [reports], parameters: [{name: campaign_id, in: query, schema: {type: string}}, {name: fmt, in: query, schema: {type: string}}, {name: scope, in: query, schema: {type: string}}], responses: {'200': {description: Archive listing}}}
    post: {operationId: createExport, tags: [reports], responses: {'202': {description: One PENDING row per format, job enqueued}}}
  /report_exports/{rex_id}:
    get:    {operationId: downloadExport, tags: [reports], responses: {'200': {description: The file bytes}, '410': {description: Purged; the hashes survive}}}
    delete: {operationId: deleteExport, tags: [reports], responses: {'200': {description: Tombstoned}}}
  /report_exports/{rex_id}/payload:
    get: {operationId: downloadExportPayload, tags: [reports], responses: {'200': {description: Canonical aggregate payload}}}
  /report_exports/{rex_id}/verify:
    get: {operationId: verifyExport, tags: [reports], responses: {'200': {description: content_ok, data_ok, bytes_on_disk}}}
  /reports/daily/{day_ist}:
    get: {operationId: getDailyReport, tags: [reports], responses: {'200': {description: The section 43 daily report}}}
  /reports/daily:
    post: {operationId: rerunDailyReport, tags: [reports], responses: {'202': {description: Job enqueued}}}
  /jobs:
    get: {operationId: listJobs, tags: [jobs], responses: {'200': {description: Job page}}}
  /jobs/stats:
    get: {operationId: getJobStats, tags: [jobs], responses: {'200': {description: Queue depth, 24h outcomes, today's spend}}}
  /jobs/dead:
    get: {operationId: listDeadJobs, tags: [jobs], responses: {'200': {description: v_jobs_dead}}}
  /jobs/retry-batch:
    post: {operationId: retryJobBatch, tags: [jobs], responses: {'200': {description: Applied and rejected lists}}}
  /jobs/{job_id}:
    get: {operationId: getJob, tags: [jobs], responses: {'200': {description: Job plus every attempt}}}
  /jobs/{job_id}/retry:
    post: {operationId: retryJob, tags: [jobs], responses: {'200': {description: Requeued}, '409': {$ref: '#/components/responses/Conflict'}}}
  /jobs/{job_id}/cancel:
    post: {operationId: cancelJob, tags: [jobs], responses: {'200': {description: Cancel requested}}}
  /jobs/{job_id}/revive:
    post: {operationId: reviveJob, tags: [jobs], description: Refused for type send_email; use resolve-indeterminate., responses: {'200': {description: Requeued}, '409': {$ref: '#/components/responses/Conflict'}}}
  /quota:
    get: {operationId: getQuota, tags: [quota], description: 'Gemini free-tier counts and ceilings. Read-only; ceilings come from config.yaml. See 13.16.1.', responses: {'200': {description: 'day_ist, requests_used/cap, rpm_used/cap, tokens_today, reset_at_ist, paused, paused_reason, by_kind[]'}}}

  # --- settings and auth -----------------------------------------------------------
  /settings/contact_policy:
    get: {operationId: getContactPolicy, tags: [settings], responses: {'200': {description: Effective and stored policy}}}
    put: {operationId: updateContactPolicy, tags: [settings], responses: {'200': {description: Updated; body reports queued_messages_affected}, '422': {$ref: '#/components/responses/Unprocessable'}}}
  /settings/contact_policy/automation_mode:
    put: {operationId: setAutomationMode, tags: [settings], description: 'v1 accepts MANUAL and HUMAN_APPROVAL only.', responses: {'200': {description: Updated}, '409': {$ref: '#/components/responses/Conflict'}}}
  /settings/channels:
    get: {operationId: getChannels, tags: [settings], responses: {'200': {description: Channel switches}}}
    put: {operationId: updateChannels, tags: [settings], responses: {'200': {description: Updated}}}
  /settings/templates:
    get: {operationId: listTemplates, tags: [settings], responses: {'200': {description: Template versions and hashes}}}
  /settings/users:
    get:  {operationId: listUsers, tags: [settings], responses: {'200': {description: User list}}}
    post: {operationId: createUser, tags: [settings], responses: {'201': {description: Created}}}
  /settings/users/{user_id}/disable:
    post: {operationId: disableUser, tags: [settings], responses: {'200': {description: Disabled, never deleted}}}
  /whatsapp/templates:
    get:  {operationId: listWhatsappTemplates, tags: [settings], responses: {'200': {description: Local mirror plus Meta status}}}
    post: {operationId: createWhatsappTemplate, tags: [settings], responses: {'201': {description: LOCAL_DRAFT created}}}
  /whatsapp/templates/{template_id}/submit:
    post: {operationId: submitWhatsappTemplate, tags: [settings], responses: {'202': {description: Submitted to Meta}}}
  /whatsapp/templates/sync:
    post: {operationId: syncWhatsappTemplates, tags: [settings], responses: {'202': {description: Sync enqueued}}}
  /whatsapp/health:
    get: {operationId: getWhatsappHealth, tags: [settings], responses: {'200': {description: Quality, tier, name status, caps - states, never secrets}}}
  /whatsapp/optins:
    get: {operationId: listWhatsappOptins, tags: [settings], responses: {'200': {description: Opt-in ledger}}}
  /whatsapp/optins/{optin_id}/revoke:
    post: {operationId: revokeWhatsappOptin, tags: [settings], responses: {'200': {description: Revoked}}}
  /erasure:
    post: {operationId: requestErasure, tags: [settings], responses: {'201': {description: Request opened with a scope preview}}}
  /erasure/{erasure_id}/execute:
    post: {operationId: executeErasure, tags: [settings], responses: {'202': {description: Erasure job enqueued}}}
  /auth/login:
    post: {operationId: login, tags: [auth], security: [], responses: {'200': {description: Session established}, '401': {$ref: '#/components/responses/Unauthorised'}, '429': {$ref: '#/components/responses/RateLimited'}}}
  /auth/logout:
    post: {operationId: logout, tags: [auth], responses: {'204': {description: Session destroyed}}}
  /auth/session:
    get: {operationId: getSession, tags: [auth], responses: {'200': {description: Current user, role, advisory permission list}}}
  /auth/unlock:
    post: {operationId: unlockSession, tags: [auth], description: 'Re-proves the password to clear an idle lock. See 13.18.1.', responses: {'200': {description: Unlocked}, '401': {$ref: '#/components/responses/Unauthorised'}, '429': {$ref: '#/components/responses/RateLimited'}}}
  /auth/revoke-all:
    post: {operationId: revokeAllSessions, tags: [auth], description: 'Own sessions for any role; another user_id is OWNER only.', responses: {'200': {description: 'revoked count'}, '403': {$ref: '#/components/responses/Forbidden'}}}
  /auth/password:
    post: {operationId: changePassword, tags: [auth], responses: {'204': {description: Changed}}}
  /auth/totp/enrol:
    post: {operationId: enrolTotp, tags: [auth], responses: {'200': {description: Provisioning URI, returned once}}}
  /auth/totp/confirm:
    post: {operationId: confirmTotp, tags: [auth], responses: {'204': {description: Enrolled}}}

  # --- unauthenticated -------------------------------------------------------------
  # There are no /webhooks/* paths. Nothing on the public internet can reach 127.0.0.1;
  # poll_inbox is the only inbound path. See 13.19 and 13.21.
  /notifications/telegram/callback:
    post: {operationId: telegramCallback, tags: [public], security: [{telegramSecret: []}], description: 'Registered only when notify.telegram.mode is webhook, which needs a public host this deploy target does not have. The default transport is getUpdates long-polling. See 13.13.2.', responses: {'200': {description: Always 200}}}
  /health:
    get: {operationId: health, tags: [public], security: [], responses: {'200': {description: Liveness probe for the exported report; no business data}}}
```

**Three route groups are absent from the paths block on purpose**, and a reviewer should read the
absence as a statement rather than as an omission:

| Absent | Why |
|---|---|
| `/webhooks/{provider}` and `/webhooks/whatsapp` | They do not exist (§13.19, §13.21). A generated document is generated from `url_map`, so they cannot appear unless somebody re-adds the routes — which is what `test_openapi_covers_every_route` and `test_absent_routes_stay_absent` are for, from the two opposite directions |
| The unsubscribe routes `/u/<message_id>/<token>` | They do not exist either (§13.20). Unsubscribe is a `mailto:` handled by `poll_inbox`, and there is no HTTP surface for a client library to consume |
| `POST /outreach/messages/{message_id}/send` without a body `$ref` | It has one — `SendConfirm` — and it is the only operation in the document whose request body is fully specified in `components`. That is deliberate: it is the request that can put a message in front of a stranger |

### 13.22.1 Component schemas

```yaml
components:
  securitySchemes:
    sessionCookie:     {type: apiKey, in: cookie, name: radar_session}
    bearerToken:       {type: http, scheme: bearer, description: Read-only API token; cannot reach any approval or transmit route}
    telegramSecret:    {type: apiKey, in: header, name: X-Telegram-Bot-Api-Secret-Token, description: 'The only shared-secret authenticator in the document, and it guards one opt-in route. There is no providerSignature scheme: 13.19 deleted the webhook blueprint'}

  parameters:
    Limit:          {name: limit, in: query, schema: {type: integer, minimum: 1, maximum: 200, default: 50}}
    Cursor:         {name: cursor, in: query, schema: {type: string}, description: Opaque keyset cursor}
    Sort:           {name: sort, in: query, schema: {type: string}, description: "field or -field; allow-listed per endpoint"}
    CampaignId:     {name: campaign_id, in: path, required: true, schema: {type: string, pattern: '^cmp_[0-9A-HJKMNP-TV-Z]{26}$'}}
    BusinessId:     {name: business_id, in: path, required: true, schema: {type: string, pattern: '^biz_[0-9A-HJKMNP-TV-Z]{26}$'}}
    VerificationId: {name: verification_id, in: path, required: true, schema: {type: string, pattern: '^ver_[0-9A-HJKMNP-TV-Z]{26}$'}}
    DraftId:        {name: draft_id, in: path, required: true, schema: {type: string, pattern: '^out_[0-9A-HJKMNP-TV-Z]{26}$'}}
    MessageId:      {name: message_id, in: path, required: true, schema: {type: string, pattern: '^msg_[0-9A-HJKMNP-TV-Z]{26}$'}}
    HandoffId:      {name: handoff_id, in: path, required: true, schema: {type: string, pattern: '^hnd_[0-9A-HJKMNP-TV-Z]{26}$'}}

  schemas:
    Timestamp: {type: string, pattern: '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'}
    Confidence: {type: string, enum: [HIGH, MEDIUM, LOW]}
    Channel:    {type: string, enum: [EMAIL, WHATSAPP, PHONE, MANUAL]}
    Industry:   {type: string, enum: [HEALTHCARE, EDUCATION, AUTOMOBILE, MANUFACTURING, RETAIL, HOSPITALITY, DISTRIBUTION, REAL_ESTATE, PROFESSIONAL_SERVICES, OTHER]}
    Category:   {type: string, enum: [HOSPITAL, DIAGNOSTIC_CENTER, SCHOOL, COLLEGE, MANUFACTURER, DISTRIBUTOR, VEHICLE_DEALER, GARAGE, HOTEL, RESTAURANT, BAKERY, RETAIL_STORE, REAL_ESTATE_AGENCY, OTHER]}
    SizeBand:   {type: string, enum: [MICRO, SMALL, MEDIUM, LARGE, UNKNOWN]}
    BusinessStatus: {type: string, enum: [AI_RESEARCHED, NEEDS_VERIFICATION, VERIFIED, REJECTED, SKIPPED, CONTACT_READY, CONTACTED, RESPONDED, INTERESTED, HUMAN_HANDOFF]}
    MessageStatus:  {type: string, enum: [DRAFT, POLICY_BLOCKED, PENDING_APPROVAL, APPROVED, QUEUED, SENT, DELIVERED, BOUNCED, FAILED, CANCELLED]}
    Classification: {type: string, enum: [INTERESTED, VERY_INTERESTED, DEMO_REQUESTED, MEETING_REQUESTED, PRICE_REQUESTED, MORE_INFORMATION, LATER, NOT_INTERESTED, ALREADY_HAVE_SOFTWARE, WRONG_CONTACT, OPT_OUT, COMPLAINT, UNKNOWN]}

    Page:
      type: object
      required: [limit, returned, has_more]
      properties:
        limit:       {type: integer}
        returned:    {type: integer}
        has_more:    {type: boolean}
        next_cursor: {type: [string, "null"]}
        total:       {type: [integer, "null"], description: Only when count=exact}

    Error:
      type: object
      required: [error]
      properties:
        error:
          type: object
          required: [code, message, request_id]
          properties:
            code:    {type: string, pattern: '^[A-Z][A-Z0-9_]*$'}
            message: {type: string, description: One sentence, rendered verbatim by the UI}
            detail:  {type: object, additionalProperties: true}
            field_errors:
              type: array
              items:
                type: object
                required: [field, code, message]
                properties:
                  field:   {type: string}
                  code:    {type: string}
                  message: {type: string}
            request_id: {type: string, pattern: '^req_[0-9A-HJKMNP-TV-Z]{26}$'}
            doc:        {type: string}

    Campaign:
      type: object
      required: [id, name, slug, status, created_at]
      properties:
        id:     {type: string, pattern: '^cmp_[0-9A-HJKMNP-TV-Z]{26}$'}
        name:   {type: string}
        slug:   {type: string}
        status: {type: string, enum: [DRAFT, QUEUED, DISCOVERING, RESEARCHING, REPORTING, COMPLETE, PAUSED, FAILED, CANCELLED]}
        paused_reason: {type: [string, "null"], enum: [SPEND_CEILING, MANUAL, PROVIDER_ERROR, RATE_LIMIT, null]}
        cities:
          type: array
          items:
            type: object
            properties:
              city:         {type: string}
              city_slug:    {type: string}
              ordinal:      {type: integer}
              status:       {type: string, enum: [PENDING, DISCOVERING, COMPLETE, FAILED, SKIPPED]}
              n_discovered: {type: integer}
        industries:  {type: array, items: {$ref: '#/components/schemas/Industry'}}
        categories:  {type: array, items: {$ref: '#/components/schemas/Category'}}
        size_filter: {type: array, items: {$ref: '#/components/schemas/SizeBand'}}
        min_opportunity_score: {type: integer, minimum: 0, maximum: 100}
        research_depth:  {type: string, enum: [STANDARD, DEEP]}
        research_model_id: {type: [string, "null"]}
        research_prompt_version: {type: [string, "null"]}
        created_by:  {type: string}
        created_at:  {$ref: '#/components/schemas/Timestamp'}
        started_at:  {type: [string, "null"]}
        finished_at: {type: [string, "null"]}
        counters:
          type: object
          description: Always aggregates from v_campaign_counters; stored counters appear only under drift
          properties:
            source: {type: string, const: aggregate}
            drift:  {type: object, additionalProperties: true}

    Business:
      type: object
      required: [id, name, city, city_slug, industry, category, size_band, status]
      properties:
        id:          {type: string, pattern: '^biz_[0-9A-HJKMNP-TV-Z]{26}$'}
        name:        {type: string}
        city:        {type: string}
        city_slug:   {type: string}
        industry:    {$ref: '#/components/schemas/Industry'}
        category:    {$ref: '#/components/schemas/Category'}
        size_band:   {$ref: '#/components/schemas/SizeBand'}
        website:     {type: [string, "null"], format: uri}
        website_status: {type: string, enum: [PRESENT, ABSENT, UNKNOWN]}
        digital_maturity:       {type: [integer, "null"], minimum: 0, maximum: 100}
        operational_complexity: {type: [integer, "null"], minimum: 0, maximum: 100}
        opportunity_score:      {type: [integer, "null"], minimum: 0, maximum: 100}
        opportunity_band:       {type: [string, "null"], enum: [HIGH, MEDIUM, LOW, null]}
        potential_solution:     {type: [string, "null"]}
        research_confidence:    {type: [string, "null"], enum: [HIGH, MEDIUM, LOW, null]}
        status:             {$ref: '#/components/schemas/BusinessStatus'}
        verification_state: {type: string}
        outreach_state:     {type: string, enum: [NOT_CONTACTED, QUEUED, SENT, DELIVERED, BOUNCED, FAILED, RESPONDED, INTERESTED, BLOCKED]}
        contact_available:  {type: array, items: {type: string, enum: [EMAIL, PHONE, WHATSAPP]}, description: Kinds only. Never values}
        contact_confirmed:  {type: boolean}
        suppressed:         {type: boolean}
        selectable:         {type: boolean}
        blocking_gate:      {type: [string, "null"]}
        blocking_sentence:  {type: [string, "null"]}
        campaign:
          type: [object, "null"]
          description: Present only when campaign_id was supplied; the campaign_businesses row
          properties:
            campaign_id:      {type: string}
            state:            {type: string, enum: [INCLUDED, EXCLUDED]}
            exclusion_reason: {type: [string, "null"]}
            first_seen_at:    {$ref: '#/components/schemas/Timestamp'}
            is_rediscovery:   {type: boolean}
            city_at_discovery: {type: string}
        first_discovered_at: {$ref: '#/components/schemas/Timestamp'}
        last_contacted_at:   {type: [string, "null"]}

    Finding:
      type: object
      required: [id, kind, dimension, label, statement, confidence]
      properties:
        id:        {type: string, pattern: '^fnd_[0-9A-HJKMNP-TV-Z]{26}$'}
        kind:      {type: string, enum: [OBSERVED, INFERRED, UNKNOWN]}
        dimension: {type: string, enum: [IDENTITY, SCALE, OPERATIONS, DIGITAL_PRESENCE, SYSTEMS, STAFFING, CUSTOMERS, FINANCE, COMPLIANCE, OTHER]}
        label:     {type: string, maxLength: 80}
        statement: {type: string, minLength: 10, maxLength: 600, description: The canonical claim text a message may cite}
        detail:    {type: [string, "null"], description: Never citable by a message}
        confidence:     {$ref: '#/components/schemas/Confidence'}
        confidence_pct: {type: [integer, "null"], minimum: 0, maximum: 100}
        weight:         {type: number, minimum: 0}
        derived_from:   {type: array, items: {type: string}, description: INFERRED only; never empty when kind is INFERRED}
        inference_note: {type: [string, "null"]}
        unknown_reason: {type: [string, "null"], enum: [NOT_PUBLISHED, SOURCE_UNREACHABLE, AMBIGUOUS, OUT_OF_SCOPE, CONFLICTING_SOURCES, null]}
        source_ids:     {type: array, items: {type: string}, description: Never empty when kind is OBSERVED}

    Source:
      type: object
      required: [id, name, url, source_type, checked_at, information_obtained, confidence]
      properties:
        id:          {type: string, pattern: '^src_[0-9A-HJKMNP-TV-Z]{26}$'}
        name:        {type: string}
        url:         {type: string, format: uri}
        source_type: {type: string, enum: [SITE, LISTING, DIRECTORY, NEWS, SOCIAL, REGISTRY, MAP, REVIEW, DOCUMENT, OTHER]}
        checked_at:  {$ref: '#/components/schemas/Timestamp'}
        information_obtained: {type: string}
        confidence:     {$ref: '#/components/schemas/Confidence'}
        confidence_pct: {type: [integer, "null"]}
        http_status:    {type: [integer, "null"]}
        content_sha256: {type: [string, "null"]}
        snapshot_path:  {type: [string, "null"]}

    Draft:
      type: object
      required: [id, business_id, campaign_id, channel, body, model_id, prompt_version]
      properties:
        id:          {type: string, pattern: '^out_[0-9A-HJKMNP-TV-Z]{26}$'}
        business_id: {type: string}
        campaign_id: {type: string}
        contact_id:  {type: [string, "null"]}
        channel:     {$ref: '#/components/schemas/Channel'}
        sequence_no: {type: integer, minimum: 1}
        subject:     {type: [string, "null"], description: Null for WHATSAPP and PHONE}
        body:        {type: string, description: As generated}
        body_edited: {type: [string, "null"]}
        final_body:  {type: string, description: COALESCE(body_edited, body); computed nowhere else}
        body_hash:   {type: string}
        edit_count:  {type: integer}
        model_id:       {type: string}
        prompt_version: {type: string}
        facts_used:      {type: array, items: {type: string}}
        inferences_used: {type: array, items: {type: string}}
        ai_confidence:     {$ref: '#/components/schemas/Confidence'}
        ai_confidence_pct: {type: [integer, "null"]}
        policy_result:  {type: [string, "null"], enum: [PASS, WARN, BLOCK, null]}
        policy_version: {type: [string, "null"]}
        superseded_by:  {type: [string, "null"]}

    GateResult:
      type: object
      required: [gate, code, outcome, sentence]
      properties:
        gate:    {type: string, description: "Stable id: A1, F5, H2"}
        code:    {type: string, description: "Stable code: A_SUPPRESSED_EMAIL"}
        outcome: {type: string, enum: [PASS, WARN, BLOCK, SKIP]}
        sentence: {type: string, description: One sentence, rendered verbatim}
        detail:   {type: object, additionalProperties: true}
        evidence_ids: {type: array, items: {type: string}}

    Eligibility:
      type: object
      required: [business_id, stage, evaluated_at, allowed, gates, fingerprint]
      properties:
        business_id: {type: string}
        contact_id:  {type: [string, "null"]}
        channel:     {type: [string, "null"]}
        stage:       {type: string, enum: [SELECT, PREVIEW, SEND]}
        evaluated_at: {$ref: '#/components/schemas/Timestamp'}
        policy_version:    {type: string}
        allowed:           {type: boolean}
        blocking_code:     {type: [string, "null"]}
        blocking_sentence: {type: [string, "null"]}
        fingerprint: {type: string, description: sha256 over the ordered (gate, outcome) pairs}
        gates:    {type: array, items: {$ref: '#/components/schemas/GateResult'}, description: Every gate, in precedence order, never short-circuited}
        warnings: {type: array, items: {$ref: '#/components/schemas/GateResult'}}

    Message:
      type: object
      required: [id, draft_id, business_id, campaign_id, channel, status]
      properties:
        id:          {type: string, pattern: '^msg_[0-9A-HJKMNP-TV-Z]{26}$'}
        draft_id:    {type: string}
        business_id: {type: string}
        campaign_id: {type: string}
        contact_id:  {type: [string, "null"]}
        channel:     {$ref: '#/components/schemas/Channel'}
        status:      {$ref: '#/components/schemas/MessageStatus'}
        approval_id: {type: [string, "null"], description: Non-null for APPROVED and beyond, by database CHECK}
        sequence_no: {type: integer}
        to_address_display: {type: [string, "null"], description: Masked unless the caller may reveal}
        subject_final: {type: [string, "null"]}
        body_hash:     {type: [string, "null"]}
        provider:      {type: [string, "null"]}
        provider_message_id: {type: [string, "null"]}
        queued_at:  {type: [string, "null"]}
        sent_at:    {type: [string, "null"]}
        delivered_at: {type: [string, "null"]}
        failed_at:  {type: [string, "null"]}
        failure_code: {type: [string, "null"]}
        sent_by:    {type: [string, "null"], description: The approving human (section 32 Sender)}

    Response:
      type: object
      required: [id, business_id, channel, body_excerpt, received_at]
      properties:
        id:          {type: string, pattern: '^rsp_[0-9A-HJKMNP-TV-Z]{26}$'}
        business_id: {type: string}
        message_id:  {type: [string, "null"], description: Nullable; a reply may not be attributable}
        campaign_id: {type: [string, "null"]}
        channel:     {$ref: '#/components/schemas/Channel'}
        attribution: {type: string, enum: [THREAD_HEADER, PROVIDER_ID, ADDRESS_MATCH, OPERATOR, UNATTRIBUTED]}
        attribution_confidence: {$ref: '#/components/schemas/Confidence'}
        from_display: {type: [string, "null"], description: Masked by role}
        subject:      {type: [string, "null"]}
        body_excerpt: {type: string, maxLength: 280}
        body_text:    {type: [string, "null"], description: Single-response read only}
        received_at:  {$ref: '#/components/schemas/Timestamp'}
        classification:          {type: [string, "null"]}
        human_classification:    {type: [string, "null"]}
        effective_classification: {$ref: '#/components/schemas/Classification'}
        confidence:      {$ref: '#/components/schemas/Confidence'}
        confidence_pct:  {type: [integer, "null"]}
        interpretation:  {type: [string, "null"]}
        recommended_action: {type: [string, "null"]}
        classification_state: {type: string, enum: [PENDING, CLASSIFIED, FAILED, HUMAN_CORRECTED]}
        legal_flag:  {type: boolean}
        handoff_id:  {type: [string, "null"]}
        is_stopper:  {type: boolean}

    Handoff:
      type: object
      required: [id, business_id, response_id, trigger_rule, state, priority, created_at]
      properties:
        id:          {type: string, pattern: '^hnd_[0-9A-HJKMNP-TV-Z]{26}$'}
        business_id: {type: string}
        campaign_id: {type: [string, "null"]}
        response_id: {type: string}
        outreach_message_id: {type: [string, "null"]}
        trigger_rule: {type: string, enum: [CLASSIFICATION, COMPLAINT, LOW_CONFIDENCE, LEGAL_LANGUAGE, MANUAL]}
        trigger_classification: {type: [string, "null"]}
        confidence:  {$ref: '#/components/schemas/Confidence'}
        priority:    {type: string, enum: [URGENT, HIGH, NORMAL]}
        state:       {type: string, enum: [OPEN, ACKNOWLEDGED, IN_PROGRESS, CLOSED]}
        outcome:     {type: [string, "null"], enum: [DEMO_SCHEDULED, PROPOSAL_SENT, WON, LOST, NO_RESPONSE, null]}
        lost_reason: {type: [string, "null"], enum: [PRICE, ALREADY_HAVE_SOFTWARE, NO_BUDGET, NO_DECISION_MAKER, WRONG_FIT, WENT_QUIET, OTHER, null]}
        recommended_action:  {type: string, description: Text only. Never executable}
        recommended_channel: {type: [string, "null"]}
        sla_ack_due_at:      {$ref: '#/components/schemas/Timestamp'}
        sla_progress_due_at: {$ref: '#/components/schemas/Timestamp'}
        sla_close_due_at:    {$ref: '#/components/schemas/Timestamp'}
        demo_scheduled_at: {type: [string, "null"]}
        demo_held_at:      {type: [string, "null"]}
        proposal_sent_at:  {type: [string, "null"]}
        proposal_value_inr: {type: [integer, "null"]}
        won_value_inr:      {type: [integer, "null"]}
        created_at:      {$ref: '#/components/schemas/Timestamp'}
        acknowledged_at: {type: [string, "null"]}
        closed_at:       {type: [string, "null"]}

  requestBodies:
    CampaignCreate: {required: true, content: {application/json: {schema: {type: object, required: [cities], properties: {name: {type: string}, cities: {type: array, minItems: 1, maxItems: 12, items: {type: string}}, industries: {type: array, items: {$ref: '#/components/schemas/Industry'}}, categories: {type: array, items: {$ref: '#/components/schemas/Category'}}, size_filter: {type: array, items: {$ref: '#/components/schemas/SizeBand'}}, min_opportunity_score: {type: integer, minimum: 0, maximum: 100}, research_depth: {type: string, enum: [STANDARD, DEEP]}, max_businesses: {type: integer, minimum: 1}, notes: {type: string}, start: {type: boolean}}, additionalProperties: false}}}}
    SendConfirm:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [draft_id, preview_token, idempotency_key, body_hash, to_address_norm, eligibility_fingerprint, displayed, confirmation_text]
            additionalProperties: false
            properties:
              draft_id:         {type: string}
              preview_token:    {type: string}
              idempotency_key:  {type: string, pattern: '^cnf_[0-9A-HJKMNP-TV-Z]{26}$', description: Server-minted by the preview}
              body_hash:        {type: string}
              to_address_norm:  {type: string}
              eligibility_fingerprint: {type: string}
              confirmation_text: {type: string}
              displayed:
                type: object
                required: [business, contact, channel, message, history, opt_out, approval]
                properties:
                  business: {type: boolean, const: true}
                  contact:  {type: boolean, const: true}
                  channel:  {type: boolean, const: true}
                  message:  {type: boolean, const: true}
                  history:  {type: boolean, const: true}
                  opt_out:  {type: boolean, const: true}
                  approval: {type: boolean, const: true}

  responses:
    Campaign:     {description: One campaign, content: {application/json: {schema: {$ref: '#/components/schemas/Campaign'}}}}
    CampaignPage: {description: Campaign page, content: {application/json: {schema: {type: object, properties: {data: {type: array, items: {$ref: '#/components/schemas/Campaign'}}, page: {$ref: '#/components/schemas/Page'}}}}}}
    Business:     {description: One business, content: {application/json: {schema: {$ref: '#/components/schemas/Business'}}}}
    BusinessPage: {description: Business page, content: {application/json: {schema: {type: object, properties: {data: {type: array, items: {$ref: '#/components/schemas/Business'}}, page: {$ref: '#/components/schemas/Page'}}}}}}
    Draft:        {description: One draft, content: {application/json: {schema: {$ref: '#/components/schemas/Draft'}}}}
    Message:      {description: One message, content: {application/json: {schema: {$ref: '#/components/schemas/Message'}}}}
    Response:     {description: One inbound reply, content: {application/json: {schema: {$ref: '#/components/schemas/Response'}}}}
    ResponsePage: {description: Response page, content: {application/json: {schema: {type: object, properties: {data: {type: array, items: {$ref: '#/components/schemas/Response'}}, page: {$ref: '#/components/schemas/Page'}}}}}}
    Handoff:      {description: One handoff, content: {application/json: {schema: {$ref: '#/components/schemas/Handoff'}}}}
    Eligibility:  {description: Gate results, content: {application/json: {schema: {$ref: '#/components/schemas/Eligibility'}}}}
    SendResult:
      description: Approved and queued
      content:
        application/json:
          schema:
            type: object
            required: [approval_id, message_id, status, queued_at, job_id, duplicate]
            properties:
              approval_id: {type: string, pattern: '^apr_[0-9A-HJKMNP-TV-Z]{26}$'}
              message_id:  {type: string}
              draft_id:    {type: string}
              status:      {type: string, const: QUEUED}
              channel:     {$ref: '#/components/schemas/Channel'}
              to_address_display: {type: string}
              queued_at:   {$ref: '#/components/schemas/Timestamp'}
              job_id:      {type: string}
              eligibility_fingerprint: {type: string}
              duplicate:   {type: boolean}
              audit_ids:   {type: array, items: {type: string}}
              next_message_id: {type: [string, "null"], description: Navigation hint; approves nothing}
    Blocked:      {description: "409 - the state of the world refuses; error.message is the gate sentence", content: {application/json: {schema: {$ref: '#/components/schemas/Error'}}}}
    Conflict:     {description: "409", content: {application/json: {schema: {$ref: '#/components/schemas/Error'}}}}
    Unprocessable: {description: "422", content: {application/json: {schema: {$ref: '#/components/schemas/Error'}}}}
    NotFound:     {description: "404", content: {application/json: {schema: {$ref: '#/components/schemas/Error'}}}}
    Forbidden:    {description: "403", content: {application/json: {schema: {$ref: '#/components/schemas/Error'}}}}
    Unauthorised: {description: "401", content: {application/json: {schema: {$ref: '#/components/schemas/Error'}}}}
    RateLimited:  {description: "429", headers: {Retry-After: {schema: {type: integer}}}, content: {application/json: {schema: {$ref: '#/components/schemas/Error'}}}}
```

---

## 13.23 Module map

| Module | Contents | Docstring, in the house voice |
|---|---|---|
| `radar/web/app.py` | App factory, the three blueprints (plus `bp_callback` when configured), `_bind_request_actor`, the error handler that renders the §13.2.4 envelope, the startup assertions | "Without this module the API is a pile of view functions with individually-decided auth. It exists so that which blueprint a route is registered on *is* its security boundary, and so that the app refuses to boot when a route forgets to say who may call it." |
| `radar/web/api/_list.py` | `paginate()`, `parse_sort()`, `parse_filters()`, the cursor codec | "Without this module every list endpoint invents its own paging, and the third one uses OFFSET — which silently drops rows from a grid a background job is rescoring while somebody reads page 3." |
| `radar/web/api/_errors.py` | `ApiError` and its subclasses, the envelope renderer, the code catalogue | "Without this module the UI has to guess whether a refusal means 'fix your request' or 'the world says no', and it will guess wrong on the one that matters — a blocked send rendered as a validation error teaches Sagar to argue with the form instead of reading the sentence." |
| `radar/web/ratelimit.py` | Token buckets, the `RateLimit-*` headers. **The only rate-limiting layer** — there is no proxy in front (§13.2.8) | "Without this module a runaway script burns the whole Gemini daily quota in four minutes, research pauses until tomorrow, and the reason is a `for` loop somebody left running over lunch." |
| `radar/web/api/campaigns.py` | §13.4, §13.5 | per house style |
| `radar/web/api/businesses.py` | §13.6, the §39 filter translation, the reveal audit row | "Without this module the eleven filters in the exported report and the eleven filters in the app drift apart, and a filter that means two things is a filter Sagar cannot trust." |
| `radar/web/verify_views.py` | §13.7 (owned by `04-verification-workflow.md`) | per `04` §4.12.2 |
| `radar/web/api/outreach.py` | §13.8-§13.11 | "Without this module the send decision lives in a view function, and the day a second caller needs to send a message it grows a second, subtly different send path." |
| `radar/web/api/handoffs.py` | §13.13 | per house style |
| `radar/web/api/reports.py` | §13.15 | per house style |
| `radar/web/api/jobs.py` | §13.16, §13.16.1 | "Without this module the quota ceiling is invisible until a campaign stops, and a pause the operator cannot see is indistinguishable from a hang." |
| `radar/web/api/settings.py` | §13.17, §13.18 | per house style |
| `radar/web/api/inbound.py` | §13.19.1 — the unmatched-mail list and the attach / ignore writes | "Without this module a reply the matcher could not attribute has no home, and the two honest options are both bad: guess, and put a stranger's words in another business's file; or drop it, and lose the one reply that was going to be a customer. This module is the third option — a human, ten seconds, and a `match_rule` that says a human did it." |
| `radar/web/public.py` | `GET /api/v1/health`, and the Telegram callback when `notify.telegram.mode: webhook` | "Without this module the one route an exported report may call sits beside the authenticated ones and eventually acquires a session decorator, and every report Sagar mailed last quarter starts reporting the app as absent." |
| `radar/web/openapi.py` | §13.22, generated from `url_map` | per house style |

**One module from the earlier revision does not exist: `radar/web/api/webhooks.py`.**
`07-email-integration.md` §7.14 already deletes `radar/web/webhooks.py` from the file list for the
same reason. There is nowhere for a provider to POST, so there is no handler, no per-provider
verifier and no `bp_webhook` to register them on (§13.19). If a future deploy ever acquires a public
hostname, that module comes back with `08` §8.9's WhatsApp verifier in it and nothing else — the
email providers are disqualified on their own terms (`07` §7.2.3), not merely on topology.

### 13.23.1 Cross-cutting tests

```python
def test_openapi_covers_every_route(app):
    """Every rule in app.url_map under /api/v1 appears in the generated OpenAPI document, and
    every path in the document resolves to a rule. A route that exists and is undocumented is a
    route nobody reviewed."""


def test_error_envelope_shape_everywhere(client):
    """Drives one deliberate failure per error code in this document and asserts the response
    matches the 13.2.4 schema: error.code, error.message as one sentence, error.request_id equal
    to the X-Request-Id header."""


def test_list_endpoints_share_pagination(app):
    """Every GET returning a collection accepts limit and cursor, rejects limit > 200 with 422,
    and returns the {data, page} envelope. Asserted by walking url_map rather than by a
    hand-maintained list, so a new endpoint is covered the day it is added."""


def test_no_api_response_contains_a_contact_value_in_a_list(client, db):
    """Requests every list endpoint with a fixture whose contact is a distinctive sentinel
    string, and asserts the sentinel appears in no response body. The single-business reveal
    path is exercised separately and asserted to write CONTACTS_REVEALED."""
```

---

## Corrections to other documents

A later repair pass should apply these. Each names the file, the location and the change.

| # | File | Location | Change |
|---|---|---|---|
| C1 | `05-outreach-workflow.md` | §5.13.4, §5.13.5, §5.21, §5.4.5 | Rename `POST /api/v1/outreach/drafts/<draft_id>/approve` to `POST /api/v1/outreach/messages/<message_id>/send`. The request body, the transaction and the four idempotency layers are unchanged. `14-background-jobs.md` §14.8 already uses the new name |
| C2 | `06-message-engine.md` | §6.11's state table, §6.12.3 | Same rename in the "Approval attempted" row |
| C3 | `05-outreach-workflow.md` | §5.21 | Rename `POST /api/v1/outreach/messages/<message_id>/revoke` to `.../cancel`; the audit action is `OUTREACH_CANCELLED` and the resulting status is `CANCELLED` |
| C4 | `05-outreach-workflow.md` | §5.6.3 | Move `record-manual` from `/outreach/drafts/<draft_id>/record-manual` to `/outreach/messages/<message_id>/record-manual` |
| C5 | `08-whatsapp-integration.md` | §8.6.6, §8.11 | Move `/outreach/<message_id>/whatsapp-link`, `/record-manual` and `GET /outreach/<message_id>/whatsapp` under `/outreach/messages/<message_id>/...` |
| C6 | `05-outreach-workflow.md` | §5.13.4's failure table, §5.12 | Replace the flat error bodies with the §13.2.4 envelope. Mapping: `{"error":"preview_stale"}` -> `code: PREVIEW_STALE`; `{"error":"body_changed"}` -> `BODY_CHANGED`; `{"error":"blocked","code":X}` -> `code: BLOCKED`, `detail.gate_code = X`; `{"error":"claim_policy"}` -> `CLAIM_POLICY`; `{"error":"bad_status"}` -> `BAD_STATUS`; `{"error":"human_session_required"}` -> `HUMAN_SESSION_REQUIRED` |
| C7 | `04-verification-workflow.md` | §4.6.4's sample payload | `CITY_IN_TARGET` -> `IN_TARGET_CITY`, matching `01-data-model.md` §1.8.2's `CHECK`. The current sample would fail the constraint |
| C8 | `04-verification-workflow.md` | §4.12.1 | Split the two id types: `GET /api/v1/verifications/<business_id>` -> `GET /api/v1/businesses/<business_id>/verification`; `GET /api/v1/verifications/<business_id>/history` -> `GET /api/v1/businesses/<business_id>/verifications` |
| C9 | `04-verification-workflow.md` | §4.9.1, §4.10.2's P8 row | `POST /api/v1/settings` -> `PUT /api/v1/settings/contact_policy` |
| C10 | `02-research-pipeline.md` | §2.2.3 | `POST /api/v1/business/<id>/sources` -> `POST /api/v1/businesses/<business_id>/sources` (rule N2) |
| C11 | `11-audit-architecture.md` | §11.11.6 | The archive listing filter is `?fmt=`, not `?kind=`, following `01-data-model.md` §1.2.1 Amendment 1 |
| C12 | `11-audit-architecture.md` | §11.6.5 or §11.6.7 | **Add `OUTREACH_POLICY_OVERRIDE`** to the catalogue: domain `POLICY`, severity `CRITICAL`, sidecar `P7Y`, visible `1`, `pii_class REFERENCE`, written by `record-manual` when a gate-A block is acknowledged (`05` §5.6.3). It is referenced by `05` and by §13.9.5 and exists in no catalogue |
| C13 | `11-audit-architecture.md` | §11.6.13 (ACCESS) | **Add `CONTACTS_REVEALED`**: domain `ACCESS`, severity `NOTICE`, sidecar `NONE`, visible `1`, `pii_class REFERENCE`, `detail_json` = `business_id`, `contact_ids[]`, `kinds[]`, `count`, `named_individuals`. Written by §13.6.4. Without it, "no endpoint returns a contact list without an audit row" has no row behind it |
| C14 | `11-audit-architecture.md` | §11.6.1, §11.6.16 | **Add** `CAMPAIGN_CANCELLED` (SYSTEM/HUMAN, NOTICE, visible), `CAMPAIGN_ARCHIVED` (HUMAN, INFO, visible), `BUSINESS_RECLASSIFIED` (HUMAN, NOTICE, visible, with `before_json`/`after_json` and `reason`), `CONTACT_CONFIRMED` (HUMAN, NOTICE, visible), `VERIFICATION_ABANDONED` (SYSTEM/HUMAN, INFO), `USER_DISABLED` (HUMAN, CRITICAL), `JOB_REVIVED` and `JOB_RETRY_BATCH` (HUMAN, NOTICE). All eight are written by routes in this document and none is in the catalogue; `audit.write()` fails on the foreign key without them |
| C15 | `14-background-jobs.md` | §14.8's export trigger | `POST /api/v1/campaigns/<id>/exports` and `GET /api/v1/campaigns/<id>/exports` -> `POST /api/v1/report_exports` and `GET /api/v1/report_exports?campaign_id=...`. One archive surface, owned by the document that owns the table |
| C16 | `14-background-jobs.md` | §14.12.2 | `POST /api/v1/jobs/retry-batch` is the name; the stray `POST /api/v1/jobs/retry` earlier in the document is the same route |
| C17 | `03-html-report.md` | §3.16 | `POST /api/v1/report_exports`'s `include_contacts` is OWNER-only and forces `contains_pii = 1`; the response is `202` with one `rex_id` per requested format, each `PENDING`, per `01-data-model.md` §1.2.1 Amendment 2 |
| C18 | `10-human-handoff.md` | §10.13 | No path changes. Note only that `POST /api/v1/handoffs/<id>/close` returns `422 OUTCOME_COMPANION_REQUIRED` rather than a bare `400`, per §13.2.5 |

### The webhook and unsubscribe repair (C19-C24)

These follow from §13.19 and §13.20 and are the corrections that matter most, because a developer
building from a stale path in one of these documents ships a dead unsubscribe link or an
unauthenticated handler.

| # | File | Location | Change |
|---|---|---|---|
| C19 | `08-whatsapp-integration.md` | §8.8.1 step 10, §8.9, §8.13.3's route list | Step 10 says "Caddy already terminates TLS on the VPS (`_CONTEXT.md` §2)". There is no Caddy and no VPS. Prefix §8.9 with an explicit caveat — **requires a public HTTPS callback URL, which the v1 localhost deploy does not have; both routes are unregistered until the §8.8.12 gate opens on a public host** — and move `POST /api/v1/webhooks/whatsapp` and `GET /api/v1/webhooks/whatsapp` out of §8.13.3's contributed-route list into a gated-and-absent block. The signature scheme, the `event_key` dedupe and the fan-out are unchanged and stay specified |
| C20 | `05-outreach-workflow.md` | §5.10.1's race narrative, §5.21's route list | `POST /u/... writes suppressions(...)` becomes "the recipient's mail client sends the `List-Unsubscribe` `mailto:`, and the next `poll_inbox` run resolves the token and writes `suppressions(...)`" — which also makes the latency in that story honest (§13.11.3 now shows it as two events). Delete `/u/<message_id>/<token>` and the webhook rows from §5.21 |
| C21 | `05-outreach-workflow.md` | §5.3.5, and wherever `postmark` appears as a SAMPLE provider | `postmark` is disqualified by `07` §7.2.3 and is not a provider in this build. The SAMPLE should read `gmail`. The same substitution is needed in `11` §11.7.2, `08` §8.4.1 and `14` §14.8.21 (`07` Open question 11 already asks for it) |
| C22 | `10-human-handoff.md` | §10.6 | Delete "because that works before DNS and Caddy are configured". `getUpdates` long-polling is the transport because there is no inbound port and no public hostname at all, not because one has not been configured yet — the sentence as written implies the webhook path becomes available later, and on this deploy target it does not |
| C23 | `07-email-integration.md` | §7.11's export-destination table | `GET /api/v1/report_exports/<rex_id>/download` -> `GET /api/v1/report_exports/<rex_id>`. Rule N4: a verb suffix only where REST has no shape for the operation, and `GET` on a file resource is that shape |
| C24 | `12-security-model.md` | §12.1's "three documents still describe the VPS" paragraph, §12.8, Open question 5 | All three §13 items are now fixed: §13.2.8 no longer names Caddy, §13.19 no longer specifies webhook blueprints, and §13.14 says "on the laptop". `12` should close its Open question 5 against `13` and keep only the `11` §11.13.3 backup-location item open |

### Path corrections against documents that call routes 13 does not have (C25-C30)

Finding: ten endpoints were referenced by other documents and were not in this registry. Five are now
added here (`GET /api/v1/campaigns/<campaign_id>/coverage` §13.4, `POST /api/v1/inbound/<inb_id>/attach`
and `/ignore` §13.19.1, `POST /api/v1/auth/unlock` and `POST /api/v1/auth/revoke-all` §13.18.1,
`GET /api/v1/quota` §13.16.1). The rest are renames, and the calling document is the one that moves.

| # | File | Location | Change |
|---|---|---|---|
| C25 | `09-response-classification.md` | §9.12.1, §9.13.2's endpoint list | `PATCH /api/v1/responses/<response_id>/classification` -> `POST /api/v1/responses/<response_id>/reclassify`. Rule N4: this is not a partial update of a resource, it is a human correction that writes five columns, may create a `handoffs` row and may create a `suppressions` row. `PATCH` understates it |
| C26 | `05-outreach-workflow.md` | §5.19's report-row action table | `POST /api/v1/businesses/<id>/reject` does not exist. Rejection is `POST /api/v1/verifications/<verification_id>/submit` with `verdict='REJECTED'`, or `POST /api/v1/verifications/bulk` with `action='REJECT'`. §13.7: two verdict routes would be two ladders, and the second one is the one that drifts |
| C27 | `06-message-engine.md` | §6.9.1's state table, §6.10.1's flow diagram | `POST /api/v1/outreach/drafts/<draft_id>/edit` -> `PUT /api/v1/outreach/drafts/<draft_id>/body`. Editing a draft body is a replacement of a sub-resource, which `PUT` says and a verb suffix does not |
| C28 | `09-response-classification.md` | §9.2.6 | Extends C4: `POST /api/v1/outreach/drafts/<id>/record-manual` -> `POST /api/v1/outreach/messages/<message_id>/record-manual`. `05` §5.6.3 carries the same stale path |
| C29 | `10-human-handoff.md` | §10.8.4's `test_open_handoff_blocks_draft_creation` | There is no `POST /api/v1/outreach/drafts`. Draft creation is `POST /api/v1/outreach/prepare`, which enqueues one `draft_outreach` job per selection; the test should assert that a selection whose business has an open handoff comes back in `blocked[]` with `blocking_gate='H_HANDOFF_OPEN'` rather than expecting a `409` from a route that does not exist |
| C30 | `02-research-pipeline.md`, `15-ui-wireframe.md` | `02` Open question 6, `15` Open questions 1 and 2 | All three are now answered and can be closed: `GET /api/v1/campaigns/<campaign_id>/coverage` is §13.4, `GET /api/v1/quota` is §13.16.1, and the five UI-route extensions are ratified in §13.2.11 — `_CONTEXT.md` §6's canonical UI list grows from eight to thirteen, in that one place |

---

## Open questions

1. **`campaigns.archived_at` does not exist.** §13.4's `POST /api/v1/campaigns/<id>/archive` and the
   `archived` list filter need one nullable `TEXT` column plus `archived_by TEXT REFERENCES
   users(id)` on `campaigns`. Amendment request against `01-data-model.md` §1.3.1. Until it lands,
   the route is unimplemented and `/campaigns` lists everything. §42 is unaffected — nothing is ever
   removed from the archive — so this is cosmetic and can wait for the first campaign that has
   scrolled off the screen.

2. **Idempotency-key storage has no table.** §13.2.7's client-supplied `Idempotency-Key` needs a
   24-hour store of `(user_id, method, path, key) -> (status, response_sha256, response_path)`.
   `01-data-model.md` has no such table and none of the ten written documents needs one; the send
   path uses `outreach_approvals.idempotency_key` instead. Options: a small `idempotency_keys` table
   (amendment against `01`), or restricting the header to the endpoints that already have a natural
   unique index and dropping it elsewhere. The second is cheaper and loses only the retry-safety of
   `POST /api/v1/campaigns` and the bulk endpoints. Not settled here because it is a schema
   decision, and `01` is the arbiter.

3. **The `AUDITOR` role.** `01-data-model.md` §1.10 records that `11-audit-architecture.md` §11.9.1
   and `/settings` assume a read-only `AUDITOR`, and that v1 ships three roles with `VIEWER` covering
   the audit-reader case. §13.3 follows that: `GET /api/v1/audit/*` is OWNER-only and the explain
   view is OPERATOR. If `12-security-model.md` adds a fourth role, §13.3's matrix gains a column and
   nothing else changes.

4. **API tokens have no table either.** §13.2.2's `bp_token` needs a store for hashed tokens, scopes
   and revocation, and `11` §11.6.13 already catalogues `API_TOKEN_CREATED` / `API_TOKEN_REVOKED`
   against `entity_table = 'users'`. Either `01` gains an `api_tokens` table or v1 ships without
   `bp_token` at all. Shipping without it is defensible for a single-operator tool and removes an
   entire authenticator from the attack surface; the cost is that the monitoring script Sagar will
   eventually write has to use a session cookie.

5. **Deliverable numbering — settled, and applied.** Spec §56 lists (12) UI wireframe and (15)
   Security model, and an earlier revision of this document followed `01`, `04` and `11` in citing
   the security model as document 15. The pack's file naming settled the other way: the security
   model is
   `12-security-model.md` and the UI wireframe is `15-ui-wireframe.md`. Every reference in this
   document has been changed accordingly. `01`, `04` and `11` still carry the old number and need
   the same one-word repair; that is the only part of this question still open.

6. **`GET /api/v1/campaigns/<id>/events` needs a worker-to-web publish channel.**
   `14-background-jobs.md` §14.11 describes it, but the mechanism inside one waitress process with a
   thread pool — a `queue.Queue` fan-out, or polling the progress row on a short timer — is not
   settled. Polling at 2 s is the honest fallback and costs one indexed read per connected browser;
   the SSE route can ship as sugar over that without changing its contract.

7. **Masking format is unspecified.** §13.3 and §13.14.2 say contact values are "masked" for
   OPERATOR and VIEWER without fixing the algorithm. It should be one function in `radar/contacts.py`
   so a masked email and a masked phone look the same everywhere, and so a test can assert that no
   response body contains an unmasked value for a role that may not see one. Proposed:
   `first char + '***' + '@' + domain` for email, last two digits for phone. Not settled here
   because `12-security-model.md` may have an opinion about how much of a domain is safe to show.

8. **`inbound_emails` and the `inb_` prefix are not ratified in `01`.** §13.19.1's two triage routes
   take an `inb_` id and read a table `07-email-integration.md` §7.8.5 defines and `01-data-model.md`
   §1.1.3 does not list. `07` already files both as amendment requests; this document now depends on
   them, which raises the priority but does not change the arbiter. If `01` renames either, §13.19.1
   and §13.22's `/inbound/{inb_id}/*` paths follow it.

9. **There is no route that pauses research manually.** §13.16.1's quota tab offers "Pause all
   research", which needs to write `campaigns.paused_reason = 'MANUAL'`, and §13.4 has `start` and
   `cancel` but nothing between them. `POST /api/v1/campaigns/<campaign_id>/pause` and `/resume`
   would close it; `14-background-jobs.md` owns what a pause does to in-flight jobs and should say
   whether a paused campaign's running job finishes or is asked to yield. Until then the tab's two
   controls are `cancel` and `start`, which is coarser than the wireframe implies.

10. **`403 REAUTH_REQUIRED` is in `12` and not in §13.11.7.** `12-security-model.md` §12.4.4 requires
    `authenticated_at` within `security.approval_reauth_minutes` (default 60) for the send
    transaction, and returns `403 REAUTH_REQUIRED` when it has lapsed. §13.11.3's precondition 3
    checks `session_auth_method` but not its age, so the ladder in this document is one rung short of
    the one `12` specifies. Adding it is a precondition 3b and one row in §13.11.7's error table; it
    is listed here rather than applied because `12` owns the window and the step-up flow, and a
    re-auth prompt that appears at the wrong moment in the CONFIRM & SEND path is worse than one
    document being behind the other.
