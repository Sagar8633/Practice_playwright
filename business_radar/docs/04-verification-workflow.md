# 4. Human verification workflow

This document settles the gate. It defines the complete ten-state machine for `businesses.status`
(spec §17) as a database-enforced transition table, the DDL for `verification_check_defs`,
`verification_reason_codes` and `verification_sources`, the element-by-element contract of the
verification screen (§15), the nine-item checklist and its rejection reason taxonomy (§16), the
exact predicate that separates `CONTACT_READY` from `VERIFIED`, the anti-rubber-stamp measures that
make the checklist worth more than the time it costs, the staleness and re-verification rules, and
the three-layer (UI / API / DB) enforcement of the hardest rule in the system: there is no send
action reachable from a research view (§19, §45).

**Ownership.** This document owns `verification_check_defs`, `verification_reason_codes`,
`verification_sources`, `business_status_transitions`, the `businesses.status` state machine, and
every route under `/verify/...`. Where it prints DDL for a table it owns, that DDL is the
definition. It does **not** own `verifications` or `verification_checks`: `01-data-model.md` §1.2.5
rules that §1.8 defines both, built to carry every column this document reads, and §4.4 cites §1.8
instead of reprinting it. Tables owned elsewhere
(`businesses`, `campaign_businesses`, `business_contacts`, `campaigns`, `research_runs`,
`research_findings`, `sources`, `finding_sources`, `opportunities`, `selections`,
`outreach_messages`, `suppressions`, `contact_policy`, `handoffs`, `users`, `audit_log`, `jobs`)
appear only as a "columns this document depends on" contract. Everything after
`CONTACT_READY` — selection, drafting, policy check, preview, approval, transmit — belongs to
`05-outreach-workflow.md`. Response classification and handoff belong to `10-human-handoff.md`.

---

## 4.1 The rule this document exists to enforce

Spec §45 and §19, restated as three implementable invariants:

> **V1.** `businesses.status = 'VERIFIED'` can only be written by a human actor, and only when a
> `verifications` row exists for that business with `state = 'SUBMITTED'`, `verdict = 'VERIFIED'`,
> `superseded_at IS NULL` and all nine `verification_checks` rows answered `passed = 1`. No system
> actor, no job, no LLM, no migration writes it.
>
> **V2.** `businesses.status = 'CONTACTED'` is reachable from exactly one predecessor state,
> `CONTACT_READY`, and only by a system actor executing the send path in
> `05-outreach-workflow.md`. There is no transition from `AI_RESEARCHED`, `NEEDS_VERIFICATION`,
> `VERIFIED`, `REJECTED` or `SKIPPED` to `CONTACTED`.
>
> **V3.** No `outreach_drafts` or `outreach_messages` row may exist for a business that has never
> reached `CONTACT_READY`. Enforced by a trigger, so it holds for code that never went through
> Flask.

V1 is the checklist. V2 is the state machine. V3 is why the "Send" button in §19 has nothing to
send: the storage layer refuses to hold the object the button would need.

Everything else in this file is either a step that produces the `verifications` row V1 demands, or
a gate that stops a stale or careless one from counting.

---

## 4.2 `businesses.status`: what it means, and what it does not

### 4.2.1 The ten states

`businesses.status` is **not** a research-progress field. Research progress lives in
`research_runs.status`; a business can have three research runs in three states while its own
status never moves. `businesses.status` answers exactly one question: **whose move is it?**

| State | Meaning | Whose move | Kind | Selectable (`05-outreach-workflow.md` §5.4.1) |
|---|---|---|---|---|
| `AI_RESEARCHED` | The machine owns this row. Discovered, being researched, or researched but not yet queued for a human. Sagar has never been asked about it. | Machine | Working | no |
| `NEEDS_VERIFICATION` | The machine is finished and has put this in Sagar's queue. The only state the verification screen accepts work from. | Sagar | Working | no |
| `VERIFIED` | A human signed all nine checks. The research is trusted. Says nothing about whether we may write to it. | Machine (promotion) | Working | no |
| `CONTACT_READY` | `VERIFIED` **and** the full §4.3 predicate holds. The only state from which outreach may begin. | Sagar (select) | Working | yes |
| `REJECTED` | A human judged this business not to be contacted, with a recorded reason. | Nobody | Judged / terminal-ish | no |
| `SKIPPED` | Parked without judgement: below the campaign bar, research failed, or "not now". | Nobody | Parked | no |
| `CONTACTED` | At least one message reached `SENT`. Follow-ups are selectable from here under the frequency gates. | Prospect | Working | follow-up only |
| `RESPONDED` | An inbound `responses` row exists and has been classified. | Machine (classify) | Working | follow-up only |
| `INTERESTED` | Classification landed in the interested set. Automation stops (§55). | Sagar | Human-owned | no |
| `HUMAN_HANDOFF` | A `handoffs` row is open. The lead is Sagar's, not the system's. | Sagar | Human-owned | no |

Two distinctions the rest of this document leans on constantly:

- **`REJECTED` is a judgement; `SKIPPED` is a shelf.** Rejection means "a human looked and said no,
  here is why". Skipping means "nobody decided anything". They are handled completely differently on
  rediscovery (§4.2.6). Conflating them is how a system quietly re-contacts a business that was
  deliberately excluded.
- **`VERIFIED` is about the research; `CONTACT_READY` is about the world.** Verification does not go
  stale because Sagar was wrong; it goes stale because the business moved, the contact bounced, or a
  suppression appeared. Separating them means a suppression does not erase a human's signature
  (§4.3.5).

### 4.2.2 The diagram

```
                     ┌───────────────────────────────────────────────────────────────────┐
                     │                        MACHINE TERRITORY                          │
                     │                                                                   │
   discovery ───────►│  ┌─────────────────┐   research COMPLETE + passes campaign bar    │
                     │  │  AI_RESEARCHED  │──────────────────────────────┐               │
                     │  └────────┬────────┘                              │               │
                     │           │ below bar / research failed           │               │
                     │           ▼                                       ▼               │
                     │  ┌─────────────────┐  unskip (human)  ┌───────────────────────┐   │
                     │  │     SKIPPED     │─────────────────►│  NEEDS_VERIFICATION   │   │
                     │  │    (parked)     │◄─────────────────│                       │   │
                     │  └────────┬────────┘   skip (human)   └──────┬────────┬───────┘   │
                     │           │ re-research queued               │        │           │
                     │           └──────────────────────────────────┘        │           │
                     └─────────────────────────────────────────────────────┬─┼───────────┘
                                                             reject        │ │  approve
                                                        (1 click + reason) │ │  (9 checks +
                                                                           │ │   dwell + note)
                                                                           ▼ ▼
                     ┌──────────────────────────────┐               ┌───────────────┐
                     │           REJECTED           │◄──────────────│   VERIFIED    │
                     │  reason_code recorded.       │   revoke      │  human signed │
                     │  A permanent reason also     │   (human)     └───┬───────▲───┘
                     │  writes a suppressions row,  │                   │       │
                     │  which the app can never     │       predicate   │       │  predicate broke
                     │  clear.                      │       holds       │       │  (non-verification
                     └──────────────┬───────────────┘                   ▼       │   clause)
                                    │ reopen (human, non-permanent      ┌───────┴────────┐
                                    │  reason only) -> NEEDS_VERIFI-    │ CONTACT_READY  │
                                    │  CATION, never straight to        └───────┬────────┘
                                    └──► VERIFIED                               │
                     ═══════════════════════════════════════════════════════════│═════════
                          HUMAN GATE PASSED — 05-outreach-workflow.md           │ SELECT ->
                                                                                │ ... -> SEND
                                                                                ▼
                                                                        ┌───────────────┐
                                                                        │   CONTACTED   │
                                                                        └───────┬───────┘
                                                                                │ inbound
                                                                                ▼
                                                                        ┌───────────────┐
                                                                        │   RESPONDED   │
                                                                        └───────┬───────┘
                                                                                │ interested set
                                                                                ▼
                                                                        ┌───────────────┐
                                                                        │  INTERESTED   │
                                                                        └───────┬───────┘
   ┌────────────────────────────────────────────────────────────────────────────┘
   │  THE HANDOFF DOOR — reachable from every one of the other nine states, never locked.
   ▼  (10-human-handoff.md's trg_handoffs_business_status fires unconditionally on insert.)
┌──────────────────┐
│  HUMAN_HANDOFF   │── explicit operator action on /business/<id> ──► CONTACT_READY
│  closing a       │                                                | VERIFIED
│  handoff does    │   (the endpoint re-evaluates the §4.3          | NEEDS_VERIFICATION
│  NOT resume      │    predicate and lands the business at the
│  outreach        │    highest level the predicate supports)
└──────────────────┘

   Re-verification demotions (§4.9), all SYSTEM-actor, all recorded:

        CONTACT_READY ─── verification went stale / trigger fired ───► NEEDS_VERIFICATION
        CONTACT_READY ─── non-verification clause broke ────────────► VERIFIED
        VERIFIED      ─── verification went stale / trigger fired ───► NEEDS_VERIFICATION
```

### 4.2.3 The transition table

Every legal transition, exhaustively. `actor_kind` is `HUMAN` or `SYSTEM` and is stored on the row
being changed (`businesses.status_actor_kind`), so the database enforces the actor as well as the
state pair. Audit action names are defined in §4.11.1.

| # | From | To | Actor | Trigger | Precondition | Side effects | Audit written |
|---|---|---|---|---|---|---|---|
| T01 | `AI_RESEARCHED` | `NEEDS_VERIFICATION` | SYSTEM | `research_runs` row reaches `COMPLETE` | A current `opportunities` row exists; `score >= campaigns.min_opportunity_score`; `size_band`, `city`, `industry` pass the campaign filter | Business enters the verification queue; `campaigns.n_researched` and `n_qualified` recomputed | `BUSINESS_STATUS_CHANGED` |
| T02 | `AI_RESEARCHED` | `SKIPPED` | SYSTEM | Research complete but below the campaign bar | `score < min_opportunity_score`, or filter mismatch | `businesses.skip_reason` set (`BELOW_MIN_SCORE`, `SIZE_FILTER`, `CITY_FILTER`, `INDUSTRY_FILTER`); `campaigns.n_skipped` recomputed; never enters the queue | `BUSINESS_STATUS_CHANGED` |
| T03 | `AI_RESEARCHED` | `SKIPPED` | SYSTEM | Research failed irrecoverably | `research_runs.status = 'FAILED'`, retries exhausted | `skip_reason = 'RESEARCH_FAILED'`; eligible for T22 | `BUSINESS_STATUS_CHANGED` |
| T04 | `AI_RESEARCHED` | `SKIPPED` | HUMAN | Sagar skips from the campaign grid before research finishes | Session bound to a `users` row permitted to verify | `skip_reason = 'MANUAL'`; queued research jobs for the business cancelled | `BUSINESS_SKIPPED`, `BUSINESS_STATUS_CHANGED` |
| T05 | `AI_RESEARCHED` | `REJECTED` | HUMAN | `REJECT` row action (§40) without opening the verification screen | A `verifications` row is created and submitted in the same transaction: `mode='QUICK_REJECT'`, `verdict='REJECTED'`, `reason_code` non-null | §4.6.6 reject side-effects (may write `suppressions`); queued research cancelled | `BUSINESS_REJECTED`, `BUSINESS_STATUS_CHANGED` |
| T06 | `NEEDS_VERIFICATION` | `VERIFIED` | HUMAN | Checklist submitted, all nine `passed = 1` | Invariant V1 in full: nine answered checks, `dwell_ms >= dwell_required_ms`, `why_note` length >= 15, every citable source visited or waived, no live suppression | `verifications.verified_at` stamped; prior verification superseded; `promote_contact_ready()` runs in the same transaction and may chain to T09 | `BUSINESS_VERIFIED`, `BUSINESS_STATUS_CHANGED` |
| T07 | `NEEDS_VERIFICATION` | `REJECTED` | HUMAN | Any check answered `passed = 0`, or explicit REJECT | `reason_code` resolvable in `verification_reason_codes`; `reason_note >= 20` chars when `reason_code = 'OTHER'` | §4.6.6 | `BUSINESS_REJECTED`, `BUSINESS_STATUS_CHANGED` |
| T08 | `NEEDS_VERIFICATION` | `SKIPPED` | HUMAN | "Decide later" | none | Draft verification, if any, moves to `state = 'ABANDONED'`; business leaves the queue, keeps its research | `BUSINESS_SKIPPED`, `BUSINESS_STATUS_CHANGED` |
| T09 | `VERIFIED` | `CONTACT_READY` | SYSTEM | `promote_contact_ready()` after a verification, a contact edit, a suppression release, or the readiness sweep | The §4.3 predicate returns `ok = True` | `businesses.contact_ready_at` stamped; business becomes selectable | `CONTACT_READY_GRANTED`, `BUSINESS_STATUS_CHANGED` |
| T10 | `VERIFIED` | `NEEDS_VERIFICATION` | SYSTEM | A re-verification trigger fired (§4.9.2) | Live verification superseded in the same transaction | `superseded_at` and `superseded_reason` set; new queue item carries `trigger_reason` and a targeted recheck scope (§4.9.3) | `REVERIFY_TRIGGERED`, `VERIFICATION_SUPERSEDED`, `BUSINESS_STATUS_CHANGED` |
| T11 | `VERIFIED` | `NEEDS_VERIFICATION` | HUMAN | Sagar revokes his own verification | none | As T10, `superseded_reason = 'MANUAL'` | `VERIFICATION_SUPERSEDED`, `BUSINESS_STATUS_CHANGED` |
| T12 | `VERIFIED` | `REJECTED` | HUMAN | Sagar changes his mind after verifying | New `verifications` row, `verdict='REJECTED'`, `reason_code` non-null; prior superseded | §4.6.6; live `selections` set to `REMOVED`; `outreach_messages` in `DRAFT`/`POLICY_BLOCKED`/`PENDING_APPROVAL` moved to `CANCELLED` | `BUSINESS_REJECTED`, `VERIFICATION_SUPERSEDED`, `BUSINESS_STATUS_CHANGED` |
| T13 | `VERIFIED` | `SKIPPED` | HUMAN | Park a verified business without rejecting it | none | Verification superseded, `superseded_reason = 'PARKED'` | `BUSINESS_SKIPPED`, `BUSINESS_STATUS_CHANGED` |
| T14 | `CONTACT_READY` | `VERIFIED` | SYSTEM | A **non-verification** predicate clause stopped holding: last active contact deactivated, suppression appeared, channel disabled, campaign closed | `contact_ready_predicate()` returns `ok = False` with `failing_clause != 'C1_VERIFIED_FRESH'` | `contact_ready_at` cleared; live `selections` set to `REMOVED`; `outreach_messages` in `PENDING_APPROVAL` moved to `CANCELLED`; the verification signature is **kept** | `CONTACT_READY_REVOKED`, `BUSINESS_STATUS_CHANGED` |
| T15 | `CONTACT_READY` | `NEEDS_VERIFICATION` | SYSTEM | Verification went stale or a re-verification trigger fired | as T10 | as T10, plus the T14 cleanup | `REVERIFY_TRIGGERED`, `VERIFICATION_SUPERSEDED`, `CONTACT_READY_REVOKED`, `BUSINESS_STATUS_CHANGED` |
| T16 | `CONTACT_READY` | `NEEDS_VERIFICATION` | HUMAN | Sagar revokes | none | as T11 + T14 cleanup | `VERIFICATION_SUPERSEDED`, `CONTACT_READY_REVOKED`, `BUSINESS_STATUS_CHANGED` |
| T17 | `CONTACT_READY` | `REJECTED` | HUMAN | Reject a ready business | as T12 | as T12 | `BUSINESS_REJECTED`, `BUSINESS_STATUS_CHANGED` |
| T18 | `CONTACT_READY` | `SKIPPED` | HUMAN | Park a ready business | as T13 | as T13 + T14 cleanup | `BUSINESS_SKIPPED`, `BUSINESS_STATUS_CHANGED` |
| T19 | `CONTACT_READY` | `CONTACTED` | SYSTEM | Step 9 (RECORD) of `05-outreach-workflow.md` | An `outreach_messages` row for this business reached `SENT`, which itself required a live `outreach_approvals` row | `selections.state = 'DISPATCHED'`; campaign counters; §48 audit | `BUSINESS_STATUS_CHANGED` |
| T20 | `CONTACTED` | `RESPONDED` | SYSTEM | A `responses` row is created and classified | `responses.classification` set | Follow-up gates re-evaluate; a stopper classification blocks further sends | `BUSINESS_STATUS_CHANGED` |
| T21 | `RESPONDED` | `INTERESTED` | SYSTEM | Classification in `INTERESTED`, `VERY_INTERESTED`, `DEMO_REQUESTED`, `MEETING_REQUESTED`, `PRICE_REQUESTED` | `10-human-handoff.md` §10.2.1 | Automated preparation stops; a `handoffs` row normally follows in the same transaction, chaining to T24 | `BUSINESS_STATUS_CHANGED` |
| T22 | `SKIPPED` | `AI_RESEARCHED` | SYSTEM | Re-research job queued for a business skipped with `skip_reason = 'RESEARCH_FAILED'` | `jobs` row `kind = 'research_business'` claimed | `skip_reason` cleared | `BUSINESS_STATUS_CHANGED` |
| T23 | `SKIPPED` | `NEEDS_VERIFICATION` | HUMAN | Unskip | A `research_runs` row with `status = 'COMPLETE'` and a current `opportunities` row exist | `skip_reason` cleared; business re-enters the queue | `BUSINESS_STATUS_CHANGED` |
| T24 | *any other state* | `HUMAN_HANDOFF` | SYSTEM | `INSERT INTO handoffs` (`10-human-handoff.md` §10.3.2) | none — **the handoff door is never locked** | Outreach for the business stops entirely while the handoff is open | `BUSINESS_STATUS_CHANGED` |
| T25 | *any other state* | `HUMAN_HANDOFF` | HUMAN | Manual handoff from `/handoffs` or `/business/<id>` | none | as T24 | `BUSINESS_STATUS_CHANGED` |
| T26 | `HUMAN_HANDOFF` | `CONTACT_READY` | HUMAN | "Return to the automated pool" on `/business/<id>`, no handoff open | The §4.3 predicate returns `ok = True` | Business becomes selectable again | `CONTACT_READY_GRANTED`, `BUSINESS_STATUS_CHANGED` |
| T27 | `HUMAN_HANDOFF` | `VERIFIED` | HUMAN | Same action, predicate fails on a non-verification clause | `ok = False`, `failing_clause != 'C1_VERIFIED_FRESH'` | Operator is shown the failing clause verbatim | `BUSINESS_STATUS_CHANGED` |
| T28 | `HUMAN_HANDOFF` | `NEEDS_VERIFICATION` | HUMAN | Same action, verification is stale | `failing_clause = 'C1_VERIFIED_FRESH'` | Verification superseded; queue item created | `VERIFICATION_SUPERSEDED`, `BUSINESS_STATUS_CHANGED` |
| T29 | `REJECTED` | `NEEDS_VERIFICATION` | HUMAN | Reopen (§4.2.4) | `verification_reason_codes.is_permanent = 0` for the rejection's reason **and** no live `suppressions` row matches the business or its contacts **and** `cool_off_days` elapsed | Rejection superseded with `superseded_reason = 'REOPENED'`; new queue item carries `prior_verification_id` so the screen shows the prior verdict banner | `VERIFICATION_REOPENED`, `BUSINESS_STATUS_CHANGED` |

**Transitions that deliberately do not exist**, and why:

| Non-transition | Why |
|---|---|
| `AI_RESEARCHED` / `NEEDS_VERIFICATION` / `VERIFIED` / `REJECTED` / `SKIPPED` -> `CONTACTED` | Invariant V2. This is spec §19 in the schema: a raw research row has no path to "contacted". |
| `* -> VERIFIED` with `actor_kind = 'SYSTEM'` | Invariant V1. No job, no LLM, no backfill signs the checklist. |
| `NEEDS_VERIFICATION -> CONTACT_READY` | `CONTACT_READY` is only ever entered from `VERIFIED`, so the human signature is always exactly one hop behind it. |
| `REJECTED -> VERIFIED` | Reopening lands in `NEEDS_VERIFICATION`. Undoing a rejection costs a full checklist, not one click. |
| `REJECTED -> CONTACT_READY`, `SKIPPED -> CONTACT_READY` | Same reason. |
| `CONTACTED -> REJECTED` | The message already left. Rejecting it is theatre; a suppression actually stops the next one. |
| `CONTACTED -> CONTACT_READY` | Follow-ups are selected from `CONTACTED` directly. Rewinding would lose the fact that a message was sent. |
| `INTERESTED -> CONTACTED` / `-> RESPONDED` | §55: once a lead is real, the machine does not take it back. |
| `HUMAN_HANDOFF -> CONTACTED` | Same. It re-enters via T26 and goes round the selection path again. |
| Anything out of `CONTACTED`/`RESPONDED` back into the verification states | Verification is a pre-contact gate. Re-verifying after contact un-sends nothing; the frequency and suppression gates own that period. |

### 4.2.4 `REJECTED`: how, and whether, a business leaves it

`REJECTED` is terminal for the machine and conditionally terminal for the human. There is exactly
one exit, T29, and it is fenced:

```
REJECTED ──┬── reason is_permanent = 1 ─────────────────────► no exit exists in the application.
           │   COMPETITOR_OR_CONFLICT                          A permanent rejection also wrote a
           │   SENSITIVE_SECTOR                                suppressions row, and per
           │   DO_NOT_CONTACT_RECORD                           _CONTEXT.md invariant 3 the app has
           │   PRIOR_COMPLAINT                                 no code that clears a suppression.
           │                                                   Leaving requires a sqlite3 session,
           │                                                   a written reason, and an audit row.
           │
           └── reason is_permanent = 0 ──► POST /api/v1/businesses/<business_id>/reopen
                                            requires: reopen_note >= 20 chars
                                                      no live suppression matches
                                                      cool_off_days elapsed since rejected_at
                                            lands in: NEEDS_VERIFICATION, checklist blank,
                                                      prior verdict banner shown (§4.5.2 E14)
```

`cool_off_days` comes from `verification_reason_codes.cool_off_days` — 0 for a clerical rejection
(`WRONG_CATEGORY`, `DUPLICATE_OF_EXISTING`), 180 for `CLOSED_OR_DEFUNCT`, because a business that
looked shut last month probably still is, and re-checking it weekly is exactly the busywork that
teaches Sagar to click through the checklist without reading it.

The reopen endpoint **cannot** land a business in `VERIFIED`. The prior checklist is shown as
history, never as pre-filled answers. A reopened business costs a full nine-check verification.

### 4.2.5 `SKIPPED`: parked, not judged

`SKIPPED` carries `businesses.skip_reason`, and the reason determines the exit:

| `skip_reason` | Set by | Exit |
|---|---|---|
| `BELOW_MIN_SCORE` | T02 | T23 unskip (human). Within one campaign the bar does not move; a different campaign with a lower bar produces a new row (§4.2.6). |
| `SIZE_FILTER` / `CITY_FILTER` / `INDUSTRY_FILTER` | T02 | T23 unskip. |
| `RESEARCH_FAILED` | T03 | T22 (system re-research) or T23. |
| `MANUAL` | T04 / T08 / T13 / T18 | T23 unskip. No reason required, no cool-off. |

There is no `PRIOR_PERMANENT_REJECTION` skip reason. Excluding a previously-rejected business from
a later campaign is a *membership* fact, not a status: it is
`campaign_businesses.exclusion_reason = 'PRIOR_PERMANENT_REJECTION'` (§4.2.6), and the business's
own status stays `REJECTED`, which is the truth about it.

Unskipping requires no reason and writes no `verifications` row, because skipping was never a
judgement about the business. That asymmetry is deliberate: making it cheap to shelf things and
cheap to bring them back means Sagar never uses `REJECTED` as a filing cabinet, which is what keeps
`REJECTED` meaningful.

### 4.2.6 What happens when a later campaign rediscovers a `REJECTED` business

`01-data-model.md` §1.2.2 rules that **`businesses` is one row per real-world business, globally
unique on `business_key`**, and that campaign participation lives in the join table
`campaign_businesses` (§1.3.4). A second campaign covering Dhule therefore does **not** create a
second row for the same clinic; it inserts a `campaign_businesses` row pointing at the row that
already exists, and `businesses.status` — the ten-state machine this section owns — keeps meaning
what it claims to mean: whose move is it on this business. A business rejected in August is
`REJECTED` in September, with no rediscovery branch and no carry-forward code to get wrong.

`business_key` is still computed at discovery, because it is what makes the row identifiable before
it exists. It is now an identity rather than a hint: `NOT NULL` with `ux_businesses_key`
(`01-data-model.md` §1.4).

```python
# radar/discover.py
def business_key(name: str, city: str, website: str | None, phone_norm: str | None) -> str:
    """A stable identity for one real-world business across campaigns.

    Preference order, first non-empty wins:
      1. registrable domain of `website`   -> "d:example-clinic.in"
      2. E.164 phone                       -> "p:+919812345678"
      3. slug(name) + '@' + slug(city)     -> "n:example-clinic@dhule"

    Deliberately not fuzzy. A false merge (two clinics collapsed into one) silently hides a real
    prospect and, worse, applies one business's rejection to another. A false split costs one
    extra verification. Prefer the cheap error. Near-misses go to merge_candidates
    (01-data-model.md §1.12.5), which never acts on its own.
    """
```

Membership resolution runs before any research job is enqueued. It decides what the **membership
row** says, not what a new business row would say, because there is no new business row:

```python
def resolve_prior_verdict(conn: sqlite3.Connection, business_id: str) -> PriorVerdict | None:
    """The live SUBMITTED verification on this business, if any.

    SELECT ... FROM verifications WHERE business_id = ? AND state = 'SUBMITTED'
      AND superseded_at IS NULL
    One row at most: ux_verifications_live guarantees it.
    """
```

The outcome table is unchanged in substance and now writes `campaign_businesses.state` and
`.exclusion_reason` (`01-data-model.md` §1.3.4) instead of inserting a row:

| Live verdict on the business | `campaign_businesses` row | `businesses.status` | Research runs? | Verification screen shows |
|---|---|---|---|---|
| `REJECTED`, `is_permanent = 1` | `EXCLUDED`, `PRIOR_PERMANENT_REJECTION` | unchanged (`REJECTED`) | **no** | never queued |
| `REJECTED`, `is_permanent = 0`, inside `cool_off_days` | `EXCLUDED`, `PRIOR_REJECTION_COOLING_OFF`, `exclusion_detail = {"cool_off_until": ...}` | unchanged (`REJECTED`) | no | never queued; the report shows "previously rejected, cooling off until <date>" |
| `REJECTED`, `is_permanent = 0`, past cool-off | `INCLUDED` | unchanged until a human reopens it (T29) | on reopen | **prior verdict banner** (§4.5.2 E14), checklist blank |
| `SKIPPED` | `INCLUDED` | `SKIPPED` -> `AI_RESEARCHED` if re-research is queued (T22) | yes | prior-skip note, checklist blank |
| `VERIFIED`, superseded or older than `verification_valid_days` | `INCLUDED` | `VERIFIED` -> `NEEDS_VERIFICATION` (T10) | yes | prior checklist shown as history |
| `VERIFIED`, live, in window, **research fingerprint identical** | `INCLUDED` | unchanged | yes | eligible for carry-forward (§4.8.3) |
| none — never seen before | `INCLUDED`, `is_rediscovery = 0` | new row, `AI_RESEARCHED` | yes | nothing |

A live `suppressions` row on the business or any of its contact values short-circuits all of this:
the membership row is inserted `EXCLUDED`, `LIVE_SUPPRESSION`, and no research job is enqueued,
because researching a business we may never contact spends Gemini free-tier quota — the daily
request ceiling in `_CONTEXT.md` §2 — on a row that can never produce an outreach message.

Every membership decision writes an audit row, `action = 'REDISCOVERY_RESOLVED'`, carrying the
`business_key`, the `campaign_businesses.id`, the prior `verification_id`, and the branch taken.
Six months later, "why was this hospital never researched in the September campaign" has a
one-query answer.

`businesses.skip_reason = 'PRIOR_PERMANENT_REJECTION'` and `businesses.prior_business_id` are
therefore gone: both existed only to describe a second row, and both are replaced by
`campaign_businesses.exclusion_reason`. §4.2.5's `skip_reason` table drops that row.

### 4.2.7 DDL: the transition table and its triggers

```sql
-- radar/migrations/011_business_status_transitions.sql
CREATE TABLE business_status_transitions (
    from_status TEXT NOT NULL,
    to_status   TEXT NOT NULL,
    actor_kind  TEXT NOT NULL CHECK (actor_kind IN ('HUMAN','SYSTEM')),
    ref         TEXT NOT NULL,   -- the T-number in 04-verification-workflow.md §4.2.3
    note        TEXT NOT NULL,
    PRIMARY KEY (from_status, to_status, actor_kind)
);

INSERT INTO business_status_transitions (from_status, to_status, actor_kind, ref, note) VALUES
    ('AI_RESEARCHED',      'NEEDS_VERIFICATION', 'SYSTEM', 'T01', 'research complete and qualified'),
    ('AI_RESEARCHED',      'SKIPPED',            'SYSTEM', 'T02', 'below campaign bar or research failed'),
    ('AI_RESEARCHED',      'SKIPPED',            'HUMAN',  'T04', 'skipped from the grid'),
    ('AI_RESEARCHED',      'REJECTED',           'HUMAN',  'T05', 'rejected from the grid'),
    ('NEEDS_VERIFICATION', 'VERIFIED',           'HUMAN',  'T06', 'nine checks passed'),
    ('NEEDS_VERIFICATION', 'REJECTED',           'HUMAN',  'T07', 'a check failed, reason recorded'),
    ('NEEDS_VERIFICATION', 'SKIPPED',            'HUMAN',  'T08', 'decide later'),
    ('VERIFIED',           'CONTACT_READY',      'SYSTEM', 'T09', 'contact-ready predicate holds'),
    ('VERIFIED',           'NEEDS_VERIFICATION', 'SYSTEM', 'T10', 're-verification trigger fired'),
    ('VERIFIED',           'NEEDS_VERIFICATION', 'HUMAN',  'T11', 'verification revoked'),
    ('VERIFIED',           'REJECTED',           'HUMAN',  'T12', 'rejected after verifying'),
    ('VERIFIED',           'SKIPPED',            'HUMAN',  'T13', 'parked'),
    ('CONTACT_READY',      'VERIFIED',           'SYSTEM', 'T14', 'non-verification clause broke'),
    ('CONTACT_READY',      'NEEDS_VERIFICATION', 'SYSTEM', 'T15', 'verification went stale'),
    ('CONTACT_READY',      'NEEDS_VERIFICATION', 'HUMAN',  'T16', 'verification revoked'),
    ('CONTACT_READY',      'REJECTED',           'HUMAN',  'T17', 'rejected after promotion'),
    ('CONTACT_READY',      'SKIPPED',            'HUMAN',  'T18', 'parked'),
    ('CONTACT_READY',      'CONTACTED',          'SYSTEM', 'T19', 'a message reached SENT'),
    ('CONTACTED',          'RESPONDED',          'SYSTEM', 'T20', 'inbound response classified'),
    ('RESPONDED',          'INTERESTED',         'SYSTEM', 'T21', 'classification in the interested set'),
    ('SKIPPED',            'AI_RESEARCHED',      'SYSTEM', 'T22', 're-research queued'),
    ('SKIPPED',            'NEEDS_VERIFICATION', 'HUMAN',  'T23', 'unskipped'),
    ('HUMAN_HANDOFF',      'CONTACT_READY',      'HUMAN',  'T26', 'returned to the automated pool'),
    ('HUMAN_HANDOFF',      'VERIFIED',           'HUMAN',  'T27', 'returned, predicate not satisfied'),
    ('HUMAN_HANDOFF',      'NEEDS_VERIFICATION', 'HUMAN',  'T28', 'returned, verification stale'),
    ('REJECTED',           'NEEDS_VERIFICATION', 'HUMAN',  'T29', 'reopened, non-permanent reason');

-- T24 / T25: the handoff door. Reachable from every other state, by either actor kind.
-- A legal complaint, a threat, or a misrouted reply must never be blocked by a state machine.
INSERT INTO business_status_transitions (from_status, to_status, actor_kind, ref, note)
SELECT s.v, 'HUMAN_HANDOFF', a.v, 'T24/T25', 'the handoff door is never locked'
  FROM (SELECT 'AI_RESEARCHED' AS v UNION ALL SELECT 'NEEDS_VERIFICATION'
        UNION ALL SELECT 'VERIFIED'  UNION ALL SELECT 'REJECTED'
        UNION ALL SELECT 'SKIPPED'   UNION ALL SELECT 'CONTACT_READY'
        UNION ALL SELECT 'CONTACTED' UNION ALL SELECT 'RESPONDED'
        UNION ALL SELECT 'INTERESTED') s
 CROSS JOIN (SELECT 'HUMAN' AS v UNION ALL SELECT 'SYSTEM') a;
```

Columns this document's triggers read on `businesses`. They are **not** added by an `ALTER` here:
`01-data-model.md` §1.2.2 folds all nine into §1.4's `CREATE TABLE businesses` in migration `003`,
because `businesses` is created before the triggers in `012` and the mutual reference
`businesses.status_verification_id` -> `verifications.id` is resolved by write order, not by
migration order (§1.13.3, C2). This document depends on them and defines none of them:

| Column | Shape | Read by |
|---|---|---|
| `status_actor_kind` | `TEXT NOT NULL DEFAULT 'SYSTEM' CHECK (status_actor_kind IN ('HUMAN','SYSTEM'))` | triggers (1) and (2) |
| `status_actor_user_id` | `TEXT REFERENCES users(id)` | trigger (2), invariant V1 |
| `status_changed_at` | `TEXT` | trigger (4) |
| `status_verification_id` | `TEXT REFERENCES verifications(id)` | trigger (2), §4.5.4's `QUEUE_SQL` |
| `contact_ready_at` | `TEXT` | T09 / T14 |
| `skip_reason` | `TEXT CHECK (skip_reason IS NULL OR skip_reason IN ('BELOW_MIN_SCORE','SIZE_FILTER','CITY_FILTER','INDUSTRY_FILTER','RESEARCH_FAILED','MANUAL'))` | §4.2.5 |
| `business_key` | `TEXT NOT NULL`, with `ux_businesses_key` — an identity, not a hint (§1.2.2) | §4.2.6 |
| `research_fingerprint`, `contact_fingerprint`, `website_hash` | `TEXT` | §4.9.6 |

`prior_business_id` is gone: it pointed at the second row that §4.2.6 no longer creates.

Two indexes this document needs, in the shapes `01-data-model.md` §1.2.2 item 3 rules:

```sql
-- 01-data-model.md §1.4.2 and §1.3.4 own these; listed here because §4.5.4's queue reads them.
CREATE INDEX ix_businesses_status ON businesses(status);
CREATE INDEX ix_cb_queue          ON campaign_businesses(campaign_id, business_id)
    WHERE state = 'INCLUDED';
```

The verification queue is a join of the two: businesses in this campaign whose status is
`NEEDS_VERIFICATION`. There is no `businesses.campaign_id` to index (§4.2.6).

The four triggers. These are the DB layer of §4.10.

```sql
-- radar/migrations/012_business_status_triggers.sql

-- (1) Only transitions in the table, and only by the declared actor kind.
CREATE TRIGGER trg_biz_status_transition
BEFORE UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status <> OLD.status
 AND NOT EXISTS (SELECT 1 FROM business_status_transitions t
                  WHERE t.from_status = OLD.status
                    AND t.to_status   = NEW.status
                    AND t.actor_kind  = NEW.status_actor_kind)
BEGIN
    SELECT RAISE(ABORT, 'illegal businesses.status transition for this actor kind');
END;

-- (2) Invariant V1. VERIFIED is a human signature backed by a real, complete, live checklist.
CREATE TRIGGER trg_biz_verified_needs_human_checklist
BEFORE UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status = 'VERIFIED' AND OLD.status <> 'VERIFIED'
 AND (NEW.status_actor_kind <> 'HUMAN'
      OR NEW.status_actor_user_id IS NULL
      OR NEW.status_verification_id IS NULL
      OR NOT EXISTS (SELECT 1 FROM verifications v
                      WHERE v.id            = NEW.status_verification_id
                        AND v.business_id   = NEW.id
                        AND v.state         = 'SUBMITTED'
                        AND v.verdict       = 'VERIFIED'
                        AND v.superseded_at IS NULL
                        AND v.checks_passed = 9
                        AND v.checks_failed = 0))
BEGIN
    SELECT RAISE(ABORT,
      'VERIFIED requires a live human verification with all nine checks passed');
END;

-- (3) Invariant V2 at the row level. Belt to the transition table's braces: this holds even if
--     someone inserts a ('VERIFIED','CONTACTED') row into business_status_transitions.
CREATE TRIGGER trg_biz_contacted_only_from_ready
BEFORE UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status = 'CONTACTED' AND OLD.status <> 'CONTACT_READY'
BEGIN
    SELECT RAISE(ABORT, 'CONTACTED is reachable only from CONTACT_READY (spec 19, 45)');
END;

-- (4) Stamp provenance and keep updated_at honest.
CREATE TRIGGER trg_biz_status_touch
AFTER UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status <> OLD.status
BEGIN
    UPDATE businesses
       SET status_changed_at = strftime('%Y-%m-%dT%H:%M:%SZ','now'),
           updated_at        = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.id;
END;
```

Because `status_actor_kind` sits on the row being updated, every writer must set it in the same
`UPDATE`. `radar/verify.py` exposes exactly one function that does so, and no other module issues
an `UPDATE businesses SET status`:

```python
def set_status(conn: sqlite3.Connection, business_id: str, to_status: str, *,
               actor_kind: Literal["HUMAN", "SYSTEM"],
               actor_user_id: str | None,
               verification_id: str | None = None,
               reason: str,
               detail: dict[str, Any] | None = None) -> None:
    """The only writer of businesses.status in the codebase.

    Reads the current status inside the caller's transaction, checks the pair against
    business_status_transitions in Python so the error message can name the T-number, performs
    the UPDATE with the actor columns set, and writes the BUSINESS_STATUS_CHANGED audit row. The
    database triggers are the real enforcement; this function exists so a violation surfaces as
    a TransitionError with a readable message rather than a bare sqlite3.IntegrityError.
    """
```

A grep test enforces the "only writer" claim:

```python
def test_only_verify_module_writes_business_status():
    """Any UPDATE of businesses.status outside radar/verify.py::set_status is a bug.

    Greps radar/**/*.py for 'businesses' within four lines of 'SET status' and asserts the only
    hit is radar/verify.py. Crude, and it catches the mistake.
    """
```

---

## 4.3 `CONTACT_READY`: the predicate that separates it from `VERIFIED`

### 4.3.1 Why two states and not one flag

`VERIFIED` and `CONTACT_READY` answer two different questions, they go wrong for different reasons,
and they are repaired by different people:

| | `VERIFIED` | `CONTACT_READY` |
|---|---|---|
| Question | "Did a human look at this research and sign it?" | "Given that signature, may outreach begin today?" |
| Subject | the research | the world |
| Written by | a human, through the checklist | the system, by evaluating §4.3.2 |
| Goes wrong because | Sagar was wrong, or the research aged | the business opted out, the contact went dead, the campaign closed, the frequency window shut |
| Repaired by | a new nine-check verification | fixing a contact, waiting out a window, reopening a campaign |
| Cost of being wrong | a message built on a false premise | a message that should not have been sent at all |

Collapsing them into one state forces a choice between two bad behaviours. If a suppression sets the
business back to `NEEDS_VERIFICATION`, then somebody's opt-out silently deletes Sagar's signature,
and re-earning it costs nine checks that will produce exactly the same nine answers — the definition
of busywork, and the fastest route to a rubber stamp (§4.7). If a suppression instead leaves the
business `VERIFIED` and the block is applied only at send time, then the grid shows a green
"verified" badge for a business nobody may ever contact, and §40's send-readiness chip becomes the
only honest thing on the screen.

Two states fix both. A suppression demotes `CONTACT_READY -> VERIFIED` (T14). The signature survives
untouched, `verifications.superseded_at` stays `NULL`, and if the suppression is a deliverability
fact rather than an opt-out (§4.3.2 C4) and Sagar replaces the dead contact,
`promote_contact_ready()` puts the business straight back without asking him a single question he
has already answered.

There is a third reason, and it is the operational one: **`CONTACT_READY` is a set that can be
computed on a schedule.** `businesses.status = 'CONTACT_READY'` is a materialised answer to a
seven-clause predicate, refreshed by the events in §4.3.7 and swept nightly (§4.9.5). Because it is
materialised, the campaign grid can render 200 rows with one indexed `WHERE` instead of 200 policy
evaluations, and `05-outreach-workflow.md` §5.4.2's grid query stays a single pass.

### 4.3.2 The seven clauses

The predicate is `C1 AND C2 AND C3 AND C4 AND C5 AND C6 AND C7`. Clause order is also **precedence
order**: `failing_clause` is the first clause that fails, because the first failure in this order is
the one that most changes what Sagar should do next.

| # | Clause | Holds when | Gate code reported | Demotes to |
|---|---|---|---|---|
| C1 | `C1_VERIFIED_FRESH` | A `verifications` row exists for the business with `state='SUBMITTED'`, `verdict='VERIFIED'`, `superseded_at IS NULL`, `checks_passed = 9`, `checks_failed = 0`, and `verified_at >= now - verification_valid_days` | `D_NOT_VERIFIED`, `D_CHECKLIST_INCOMPLETE`, `D_VERIFICATION_STALE` | `NEEDS_VERIFICATION` |
| C2 | `C2_NOT_JUDGED` | `businesses.status` is not `REJECTED`, `SKIPPED`, `INTERESTED` or `HUMAN_HANDOFF` | `D_VERIFICATION_REVOKED`, `D_HUMAN_OWNED` | n/a — those states are already terminal or human-owned |
| C3 | `C3_CONTACT_USABLE` | At least one `business_contacts` row with `human_verified = 1`, `is_active = 1`, a non-empty valid `value_norm`, a `kind` that at least one **enabled** channel can carry, and — unless `is_role_address = 1` — a non-null `source_ref` or `source_url` | `E_CONTACT_MISSING`, `E_CONTACT_NOT_VERIFIED`, `E_CONTACT_NO_PROVENANCE` | `VERIFIED` |
| C4 | `C4_NO_SUPPRESSION` | No live `suppressions` row matches the business id or any of its contact points, under the two-tier rule below | `A_SUPPRESSED_BUSINESS`, `A_SUPPRESSED_EMAIL`, `A_SUPPRESSED_PHONE`, `A_SUPPRESSED_WHATSAPP`, `A_SUPPRESSED_DOMAIN` | `VERIFIED` |
| C5 | `C5_FREQUENCY_OPEN` | The business-level §31 window is open. One `businesses` row per real business (§4.2.6) makes the count, the last-sent date and the stopper business-wide; `F_RECENT_CAMPAIGN` alone is evaluated per campaign | `G_MIN_DAYS`, `G_MAX_ATTEMPTS`, `G_SNOOZED`, `G_STOP_AFTER_REJECTION`, `G_STOP_AFTER_OPT_OUT`, `F_RECENT_CAMPAIGN` | `VERIFIED` |
| C6 | `C6_RESEARCH_USABLE` | A `research_runs` row with `status='COMPLETE'`, at least one `research_findings` row with `kind='OBSERVED'` that has a `finding_sources` row, and a current `opportunities` row | `C_RESEARCH_INCOMPLETE`, `C_NO_SOURCED_FINDINGS`, `C_NO_OPPORTUNITY` | `NEEDS_VERIFICATION` |
| C7 | `C7_CONFIDENCE_ADEQUATE` | `opportunities.confidence` ranks at or above `verify.min_research_confidence` **and** `opportunities.confidence_pct >= verify.min_research_confidence_pct` | `C_CONFIDENCE_LOW` (new — §4.11.1) | `VERIFIED` |

Notes that matter more than they look:

- **C1 is first so that its demotion target is unambiguous.** Every other clause demotes to
  `VERIFIED` and keeps the signature; only C1 supersedes it. This document and
  `05-outreach-workflow.md` both branch on `failing_clause == 'C1_VERIFIED_FRESH'` and nothing else.
- **C3 requires the contact to fit an enabled channel.** A business whose only human-verified contact
  is a phone number, on a deployment where `phone_enabled = 0` and `manual_enabled = 0`, is verified
  and uncontactable. Saying so in the state is more useful than saying it in a tooltip at preview
  time.
- **C3 does not require a *specific* contact.** Which contact and which channel is a decision Sagar
  makes at selection (`05-outreach-workflow.md` §5.4.3), and gates E2/E3/E4 evaluate that choice.
  C3 only asserts that a defensible choice exists.
- **C4 is deliberately business-wide.** `_CONTEXT.md` invariant 3: an opt-out on *any* contact point
  blocks *every* channel for that business, forever. C4 makes that a state, not a query somebody has
  to remember to write.
- **C5 is cross-campaign for free.** Spec §29 lists "recent campaign" as a duplicate condition.
  Under `01-data-model.md` §1.2.2 a second campaign in Nashik reuses the same `businesses` row
  (§4.2.6), so every campaign's `outreach_messages` already hang off one `business_id` and the
  attempt count, the last-sent date and the stopper classification are business-wide by
  construction. Only `F_RECENT_CAMPAIGN` is still per-campaign, and it is the one question that
  genuinely is: did some *other* campaign write to this business inside `recent_campaign_days`.
- **C7 is the only clause with no existing gate.** It is requested as gate `C4 / C_CONFIDENCE_LOW`
  in §4.11.1 and listed in "Open questions".

**C4's two-tier suppression rule.** `suppressions.reason` splits into two families with different
consequences, and conflating them makes one of two mistakes:

| Family | `suppressions.reason` values | C4 effect | Rationale |
|---|---|---|---|
| Opt-out origin | `UNSUBSCRIBE_LINK`, `REPLY_OPT_OUT`, `COMPLAINT`, `DNC_LIST`, `LEGAL_REQUEST`, `MANUAL` | Blocks the business permanently. Matched against **every** `business_contacts` row for the business, active or not, plus the business id and the registrable domain | A person said stop. Deactivating the contact row must not un-say it, or the app has invented a way to clear an opt-out, which `_CONTEXT.md` invariant 3 forbids |
| Deliverability origin | `BOUNCE_HARD` | Blocks the address permanently, and blocks the business only while that address is one of its `is_active = 1` contact points | A mailbox that does not exist is not a person who objected. Deactivating the dead address and human-verifying a different one restores C4 — the suppression row is still never cleared, and the dead address is still unusable forever |

Both tiers leave the `suppressions` row untouched forever. The difference is only in what the row is
allowed to imply about a *different* address at the same business. Without this split, one hard
bounce on `info@` permanently kills a hospital that also published a working `accounts@`, and the
re-verification trigger for a previous hard bounce (§4.9.2 R6) would have nothing useful to offer.

### 4.3.3 The predicate as a SQL expression

Used by the nightly sweep, by the campaign grid, and by `radar/report.py` — anywhere a **set** of
businesses is scanned. It is a view so that there is exactly one copy of it.

```sql
-- radar/migrations/057_v_contact_ready.sql
--
-- One row per (campaign, business), every clause as a 0/1 column.
--
-- Per campaign, not per business, because 01-data-model.md §1.2.2 makes `businesses` one global
-- row and `campaign_businesses` the membership: `businesses.campaign_id` does not exist. Policy
-- (channel enables, the frequency window, the verification TTL) is per campaign, so a business in
-- two campaigns genuinely has two readiness answers. This is exactly the shape §1.2.2 gave
-- `v_report_business`, and the single-business form below collapses it.
--
-- Parameters cannot be bound inside a view, so the policy numbers are resolved through
-- v_effective_policy (05-outreach-workflow.md §5.3.1's effective_policy(), materialised as a view
-- over contact_policy so set-based callers see the same GLOBAL/CAMPAIGN merge the Python callers
-- see) and app_settings.
CREATE VIEW v_contact_ready AS
WITH pol AS (
    SELECT cb.campaign_id,
           cb.business_id,
           p.verification_valid_days,
           p.min_days_between_outreach,
           p.recent_campaign_days,
           p.max_attempts,
           p.stop_after_rejection,
           p.stop_after_opt_out,
           p.email_enabled, p.whatsapp_enabled, p.phone_enabled, p.manual_enabled
      FROM campaign_businesses cb
      JOIN v_effective_policy p ON p.campaign_id = cb.campaign_id
     WHERE cb.state = 'INCLUDED'
),
ver AS (
    SELECT v.business_id, v.id AS verification_id, v.verified_at
      FROM verifications v
     WHERE v.state         = 'SUBMITTED'
       AND v.verdict       = 'VERIFIED'
       AND v.superseded_at IS NULL
       AND v.checks_passed = 9
       AND v.checks_failed = 0
),
usable_contact AS (
    -- Per campaign, because which channels are enabled is a campaign policy.
    SELECT pol.campaign_id, c.business_id, COUNT(*) AS n
      FROM business_contacts c
      JOIN pol ON pol.business_id = c.business_id
     WHERE c.human_verified = 1
       AND c.is_active      = 1
       AND c.value_norm IS NOT NULL AND c.value_norm <> ''
       AND (c.is_role_address = 1 OR c.source_ref IS NOT NULL OR c.source_url IS NOT NULL)
       AND ( (c.kind = 'EMAIL'    AND pol.email_enabled    = 1)
          OR (c.kind = 'PHONE'    AND (pol.phone_enabled   = 1 OR pol.manual_enabled = 1))
          OR (c.kind = 'WHATSAPP' AND pol.whatsapp_enabled = 1) )
     GROUP BY pol.campaign_id, c.business_id
),
suppressed AS (
    -- C4, both tiers. Business-wide and campaign-independent: an opt-out is not a campaign fact.
    -- released_at is NULL forever in the application (invariant 3).
    SELECT DISTINCT b.id AS business_id
      FROM businesses b
      LEFT JOIN business_contacts c ON c.business_id = b.id
      JOIN suppressions s
        ON s.released_at IS NULL
       AND ( (s.scope = 'BUSINESS' AND s.value_norm = b.id)
          OR (s.scope = 'DOMAIN'   AND s.value_norm = c.domain)
          OR (s.scope IN ('EMAIL','PHONE','WHATSAPP')
              AND s.scope      = c.kind
              AND s.value_norm = c.value_norm
              AND (s.reason <> 'BOUNCE_HARD' OR c.is_active = 1)) )
),
hist AS (
    -- C5. Under §1.2.2 there is one businesses row per real business, so every campaign's
    -- messages already hang off one business_id and the old business_key self-join is gone.
    -- `last_other_campaign_at` is still needed: §29's "recent campaign" asks whether SOME OTHER
    -- campaign wrote to this business recently, which is a per-campaign question.
    SELECT pol.campaign_id,
           pol.business_id,
           MAX(m.sent_at)                            AS last_sent_at,
           COUNT(m.id)                               AS attempts,
           MAX(CASE WHEN m.campaign_id <> pol.campaign_id
                    THEN m.sent_at END)              AS last_other_campaign_at
      FROM pol
      LEFT JOIN outreach_messages m
             ON m.business_id = pol.business_id
            AND m.status IN ('SENT','DELIVERED','BOUNCED')
     GROUP BY pol.campaign_id, pol.business_id
),
stopper AS (
    SELECT r.business_id,
           MIN(r.received_at)    AS at,
           MIN(r.classification) AS classification
      FROM responses r
     WHERE r.classification IN ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE',
                                'WRONG_CONTACT','OPT_OUT','COMPLAINT')
     GROUP BY r.business_id
),
snooze AS (
    SELECT r.business_id, MAX(r.snooze_until) AS until
      FROM responses r
     WHERE r.snooze_until IS NOT NULL
     GROUP BY r.business_id
),
res AS (
    SELECT b.id AS business_id,
           MAX(CASE WHEN rr.status = 'COMPLETE' THEN 1 ELSE 0 END) AS research_complete,
           MAX(CASE WHEN f.kind = 'OBSERVED' AND fs.source_id IS NOT NULL
                    THEN 1 ELSE 0 END)                             AS observed_sourced
      FROM businesses b
      LEFT JOIN research_runs     rr ON rr.business_id = b.id
      LEFT JOIN research_findings f  ON f.business_id  = b.id
      LEFT JOIN finding_sources   fs ON fs.finding_id  = f.id
     GROUP BY b.id
)
SELECT
    b.id       AS business_id,
    pol.campaign_id,
    b.status,
    v.verification_id,
    v.verified_at,

    CASE WHEN v.verification_id IS NOT NULL
          AND v.verified_at >= datetime('now', '-' || pol.verification_valid_days || ' days')
         THEN 1 ELSE 0 END                                            AS c1_verified_fresh,
    CASE WHEN b.status NOT IN ('REJECTED','SKIPPED','INTERESTED','HUMAN_HANDOFF')
         THEN 1 ELSE 0 END                                            AS c2_not_judged,
    CASE WHEN COALESCE(uc.n, 0) > 0   THEN 1 ELSE 0 END               AS c3_contact_usable,
    CASE WHEN sup.business_id IS NULL THEN 1 ELSE 0 END               AS c4_no_suppression,
    CASE WHEN COALESCE(h.attempts, 0) < pol.max_attempts
          AND (h.last_sent_at IS NULL
               OR h.last_sent_at < datetime('now','-' || pol.min_days_between_outreach || ' days'))
          AND (h.last_other_campaign_at IS NULL
               OR h.last_other_campaign_at
                  < datetime('now','-' || pol.recent_campaign_days || ' days'))
          AND (sn.until IS NULL OR sn.until <= strftime('%Y-%m-%dT%H:%M:%SZ','now'))
          AND (st.business_id IS NULL
               OR (pol.stop_after_rejection = 0
                   AND st.classification NOT IN ('OPT_OUT','COMPLAINT'))
               OR (pol.stop_after_opt_out   = 0
                   AND st.classification     IN ('OPT_OUT','COMPLAINT')))
         THEN 1 ELSE 0 END                                            AS c5_frequency_open,
    CASE WHEN COALESCE(res.research_complete,0) = 1
          AND COALESCE(res.observed_sourced,0)  = 1
          AND o.id IS NOT NULL            THEN 1 ELSE 0 END           AS c6_research_usable,
    CASE WHEN o.confidence IS NOT NULL
          AND CASE o.confidence WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END
              >= (SELECT CASE value WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END
                    FROM app_settings WHERE key = 'verify.min_research_confidence')
          AND COALESCE(o.confidence_pct, 0)
              >= (SELECT CAST(value AS INTEGER)
                    FROM app_settings WHERE key = 'verify.min_research_confidence_pct')
         THEN 1 ELSE 0 END                                            AS c7_confidence_adequate
  FROM pol
  JOIN businesses b           ON b.id            = pol.business_id
  LEFT JOIN ver v             ON v.business_id   = pol.business_id
  LEFT JOIN usable_contact uc ON uc.business_id  = pol.business_id
                            AND uc.campaign_id   = pol.campaign_id
  LEFT JOIN suppressed sup    ON sup.business_id = pol.business_id
  LEFT JOIN hist h            ON h.business_id   = pol.business_id
                            AND h.campaign_id    = pol.campaign_id
  LEFT JOIN stopper st        ON st.business_id  = pol.business_id
  LEFT JOIN snooze sn         ON sn.business_id  = pol.business_id
  LEFT JOIN res               ON res.business_id = pol.business_id
  LEFT JOIN opportunities o   ON o.business_id   = pol.business_id AND o.is_current = 1;
```

A business in no `INCLUDED` campaign produces no row at all, and therefore is never contact-ready.
That is the correct failure direction: `businesses.status` can only be promoted by a query that
found a live membership and a live policy, so an archived or excluded business fails closed rather
than inheriting the `GLOBAL` policy by accident.

`businesses.status` is one column on one global row, so the promotion path needs exactly one answer
per business. A second view in the same migration collapses the per-campaign rows to **the campaign
under which the business comes closest to ready**. Every campaign-specific gate is re-evaluated per
selection by `05-outreach-workflow.md` §5.9 before anything is drafted, so "ready somewhere" never
becomes "sendable anywhere":

```sql
-- radar/migrations/057_v_contact_ready.sql (continued)
CREATE VIEW v_contact_ready_business AS
SELECT business_id,
       campaign_id AS ready_campaign_id,
       status, verification_id, verified_at,
       c1_verified_fresh, c2_not_judged, c3_contact_usable, c4_no_suppression,
       c5_frequency_open, c6_research_usable, c7_confidence_adequate,
       contact_ready, failing_clause
  FROM (
    SELECT cr.*,
           (cr.c1_verified_fresh * cr.c2_not_judged * cr.c3_contact_usable * cr.c4_no_suppression
            * cr.c5_frequency_open * cr.c6_research_usable * cr.c7_confidence_adequate)
                                                                          AS contact_ready,
           CASE WHEN cr.c1_verified_fresh      = 0 THEN 'C1_VERIFIED_FRESH'
                WHEN cr.c2_not_judged          = 0 THEN 'C2_NOT_JUDGED'
                WHEN cr.c3_contact_usable      = 0 THEN 'C3_CONTACT_USABLE'
                WHEN cr.c4_no_suppression      = 0 THEN 'C4_NO_SUPPRESSION'
                WHEN cr.c5_frequency_open      = 0 THEN 'C5_FREQUENCY_OPEN'
                WHEN cr.c6_research_usable     = 0 THEN 'C6_RESEARCH_USABLE'
                WHEN cr.c7_confidence_adequate = 0 THEN 'C7_CONFIDENCE_ADEQUATE'
                ELSE NULL END                                             AS failing_clause,
           ROW_NUMBER() OVER (
             PARTITION BY cr.business_id
             -- Ready campaigns first; among failures the one whose failing clause is furthest
             -- down the precedence order, because that is the campaign closest to ready and the
             -- clause Sagar can act on. campaign_id breaks the remaining ties deterministically,
             -- so the same input always names the same ready_campaign_id.
             ORDER BY (cr.c1_verified_fresh * cr.c2_not_judged * cr.c3_contact_usable
                       * cr.c4_no_suppression * cr.c5_frequency_open * cr.c6_research_usable
                       * cr.c7_confidence_adequate) DESC,
                      cr.c1_verified_fresh DESC, cr.c2_not_judged DESC,
                      cr.c3_contact_usable DESC, cr.c4_no_suppression DESC,
                      cr.c5_frequency_open DESC, cr.c6_research_usable DESC,
                      cr.campaign_id
           ) AS rn
      FROM v_contact_ready cr
  )
 WHERE rn = 1;
```

`ROW_NUMBER() OVER` is standard SQL, supported by SQLite since 3.25 and by Postgres, so it does not
breach `_CONTEXT.md` §2's "no SQLite-only cleverness" rule.

The single-business form, which is what the promotion path reads, is now one line:

```sql
-- radar/verify.py :: CONTACT_READY_SQL          params: :business_id
SELECT * FROM v_contact_ready_business WHERE business_id = :business_id;
```

`ready_campaign_id` is the campaign whose policy the promotion was made under.
`CONTACT_READY_GRANTED` records it (§4.11.2), so "ready under which campaign's rules" is answerable
six months later instead of being inferred.

`app_settings` is the key/value settings table owned by `01-data-model.md`; the two `verify.*` keys
are written from `config.yaml` at startup so that a view can read them without a bound parameter. If
`01-data-model.md` does not provide `app_settings`, the two subselects become literals rewritten by
the migration that changes the setting — see "Open questions".

### 4.3.4 The predicate as a Python function

The SQL above scans sets. **Every decision** — every write of `businesses.status = 'CONTACT_READY'`
— goes through the function below, which does not reimplement the clauses. It asks
`check_send_eligibility()` for the six clauses that map onto existing gates and runs one extra query
for C7. One implementation of the shared logic, in `radar/policy.py`, where
`05-outreach-workflow.md` already put it.

```python
# radar/verify.py

CLAUSES: tuple[str, ...] = (
    "C1_VERIFIED_FRESH", "C2_NOT_JUDGED", "C3_CONTACT_USABLE", "C4_NO_SUPPRESSION",
    "C5_FREQUENCY_OPEN", "C6_RESEARCH_USABLE", "C7_CONFIDENCE_ADEQUATE",
)

# Which policy gates decide each clause. A BLOCK on any listed gate fails the clause.
# SKIP - a gate the engine could not evaluate without a contact and channel - is not a failure.
CLAUSE_GATES: dict[str, tuple[str, ...]] = {
    "C1_VERIFIED_FRESH":      ("D_NOT_VERIFIED", "D_VERIFICATION_STALE", "D_CHECKLIST_INCOMPLETE"),
    "C2_NOT_JUDGED":          ("D_VERIFICATION_REVOKED", "D_HUMAN_OWNED"),
    "C3_CONTACT_USABLE":      ("E_CONTACT_MISSING",),
    "C4_NO_SUPPRESSION":      ("A_SUPPRESSED_BUSINESS", "A_SUPPRESSED_EMAIL", "A_SUPPRESSED_PHONE",
                               "A_SUPPRESSED_WHATSAPP", "A_SUPPRESSED_DOMAIN"),
    "C5_FREQUENCY_OPEN":      ("G_MIN_DAYS", "G_SNOOZED", "G_MAX_ATTEMPTS",
                               "G_STOP_AFTER_REJECTION", "G_STOP_AFTER_OPT_OUT",
                               "F_RECENT_CAMPAIGN"),
    "C6_RESEARCH_USABLE":     ("C_RESEARCH_INCOMPLETE", "C_NO_SOURCED_FINDINGS", "C_NO_OPPORTUNITY"),
    "C7_CONFIDENCE_ADEQUATE": ("C_CONFIDENCE_LOW",),
}


@dataclass(frozen=True)
class ClauseResult:
    clause: str                     # one of CLAUSES
    ok: bool
    gate: str | None                # the policy gate code that failed, if any
    sentence: str | None            # the gate's one-sentence explanation, verbatim
    detail: dict[str, Any]


@dataclass(frozen=True)
class ContactReadiness:
    business_id: str
    evaluated_at: str                   # ISO-8601 UTC
    policy_version: str                 # contact_policy.policy_version in force
    ok: bool
    failing_clause: str | None          # first failure in CLAUSES order
    blocking_code: str | None           # the gate code behind failing_clause
    blocking_sentence: str | None
    clauses: tuple[ClauseResult, ...]   # all seven, always, in CLAUSES order
    demote_to: str | None               # 'NEEDS_VERIFICATION' | 'VERIFIED' | None

    def to_json(self) -> str: ...


def contact_ready_predicate(conn: sqlite3.Connection, business_id: str, *,
                            now: str | None = None) -> ContactReadiness:
    """Answer 'should this business be in the outreach pool at all, today?'

    Read-only. Evaluates all seven clauses on every call - no short circuit - so the screen can
    show Sagar every reason at once instead of one per refresh. Clause C1 is evaluated first so
    that `demote_to` is unambiguous: a stale or missing signature sends the business back to
    NEEDS_VERIFICATION, and every other broken clause sends it back to VERIFIED with the
    signature intact.

    C1-C6 are read from check_send_eligibility(stage='SELECT', contact_id=None, channel=None)
    rather than recomputed here. Two implementations of 'is this business suppressed' is how a
    system ends up with a grid that says yes and a send path that says no.
    """


def promote_contact_ready(conn: sqlite3.Connection, business_id: str, *,
                          reason: str = "PREDICATE_HOLDS") -> bool:
    """VERIFIED -> CONTACT_READY (T09) when contact_ready_predicate().ok is True.

    Promotion only; it never demotes. Returns True if the status changed. Idempotent: called on a
    business that is already CONTACT_READY it re-stamps nothing and returns False. Sets
    businesses.contact_ready_at, clears contact_ready_block_code, emits CONTACT_READY_GRANTED.
    """


def revoke_contact_ready(conn: sqlite3.Connection, business_id: str, *,
                         readiness: ContactReadiness) -> bool:
    """CONTACT_READY -> VERIFIED (T14) or -> NEEDS_VERIFICATION (T15), per readiness.demote_to.

    Performs the T14 cleanup in the same transaction: contact_ready_at cleared,
    contact_ready_block_code set to readiness.blocking_code, live selections moved to REMOVED,
    outreach_messages in PENDING_APPROVAL moved to CANCELLED. APPROVED and QUEUED messages are
    NOT touched here - they are re-checked by check_send_eligibility(stage='SEND') inside the
    send transaction, which is the only reader holding the write lock and therefore the only one
    that can close that race.
    """


def refresh_contact_readiness(conn: sqlite3.Connection, business_id: str) -> ContactReadiness:
    """Evaluate the predicate and move the business to wherever it now belongs.

    The single entry point for every event in section 4.3.7. Promotes, demotes or does nothing,
    always inside the caller's transaction, always writing contact_ready_block_code and
    contact_ready_checked_at so the grid can render an accurate reason for a business that is
    VERIFIED but held back.
    """
```

Two columns on `businesses` cache the last answer, so a held-back business can explain itself
without a policy evaluation per grid row:

| Column | Shape | Written by |
|---|---|---|
| `contact_ready_block_code` | `TEXT` — the gate code, `NULL` when ready | `refresh_contact_readiness()`, §4.9.4 |
| `contact_ready_checked_at` | `TEXT` | the same call |

They belong in `01-data-model.md` §1.4's `CREATE TABLE businesses` alongside the nine columns
§1.2.2 already folds in, not in an `ALTER` inside a view migration. Requested in "Open questions".

### 4.3.5 What a broken clause does, and why the signature survives

| Failing clause | New status | `verifications` row | `selections` | `outreach_messages` | Recovers automatically when |
|---|---|---|---|---|---|
| C1 (stale, superseded, checks incomplete) | `NEEDS_VERIFICATION` | superseded, `superseded_reason` set | live rows -> `REMOVED` | `DRAFT` / `POLICY_BLOCKED` / `PENDING_APPROVAL` -> `CANCELLED` | never — a human re-signs |
| C2 (`REJECTED` / `SKIPPED`) | already there | superseded on rejection (T12), kept on a park (T13) | -> `REMOVED` | -> `CANCELLED` | never — T23 / T29 are human actions |
| C2 (`INTERESTED` / `HUMAN_HANDOFF`) | already there | **untouched** | -> `REMOVED` | -> `CANCELLED` | T26, a human action |
| C3 (no usable contact) | `VERIFIED` | **untouched** | -> `REMOVED` | `PENDING_APPROVAL` -> `CANCELLED` | a contact is confirmed (`human_verified = 1`) |
| C4 (suppression) | `VERIFIED` | **untouched** | -> `REMOVED` | `PENDING_APPROVAL` -> `CANCELLED` | only for `BOUNCE_HARD`, when the dead address is deactivated and another is confirmed |
| C5 (frequency) | `VERIFIED` | **untouched** | -> `REMOVED` | `PENDING_APPROVAL` -> `CANCELLED` | the window elapses; the nightly sweep re-promotes |
| C6 (research unusable) | `NEEDS_VERIFICATION` | superseded, `superseded_reason='RESEARCH_CHANGED'` | -> `REMOVED` | -> `CANCELLED` | never — re-research, then re-verify |
| C7 (confidence below floor) | `VERIFIED` | **untouched** | -> `REMOVED` | `PENDING_APPROVAL` -> `CANCELLED` | a rescore raises the confidence, or the floor is lowered |

The column marked **untouched** is the point of the two-state design, and it is why
`verifications.superseded_at` is not a nullable convenience: it is the record of whether a human's
signature was withdrawn or merely overtaken by circumstance. `05-outreach-workflow.md` §5.5.3
renders the live verification verbatim in the "why was this selected" panel; a suppression that
silently blanked it would make that panel lie about who decided what.

`APPROVED` and `QUEUED` messages are deliberately not cancelled by a demotion. They are cancelled by
`check_send_eligibility(stage='SEND')` inside the send transaction (`05-outreach-workflow.md`
§5.10). A demotion that tried to cancel them from outside that lock would either miss a message
already claimed by a worker or deadlock against it.

### 4.3.6 Division of labour with `check_send_eligibility()`

Two functions answer overlapping questions. They are not redundant, and the boundary is exact:

| | `contact_ready_predicate()` — `radar/verify.py` | `check_send_eligibility()` — `radar/policy.py` |
|---|---|---|
| Question | "Should this business be in the pool at all, today?" | "May this message go to this contact on this channel right now?" |
| Grain | one business | (business, contact, channel, message, stage) |
| Owns | `businesses.status` within the `VERIFIED` / `CONTACT_READY` pair | every send decision |
| Gates evaluated | A\*, C\*, D\*, E1, F6, G1–G5, plus C7 | all of A–I |
| Gates never evaluated | E2, E3, E4, F1–F5, H\*, I\* — they need a contact, a channel or a message | none |
| Called when | verification submitted, contact edited, suppression inserted, response classified, message `SENT`, campaign closed, policy changed, nightly sweep | SELECT, PREVIEW, SEND |
| Writes | nothing itself; `refresh_contact_readiness()` writes the status | never writes |
| Authority | decides membership of the selectable set | decides transmission — **the last word, always** |
| Failure if it drifts | a business sits in the wrong pool: annoying, visible, recoverable | a message goes to somebody it should not: not recoverable |

Three rules keep them honest:

1. **The predicate never reimplements a gate.** C1–C6 read `Eligibility.gates`. Adding a gate to
   `05-outreach-workflow.md` §5.9.1 changes the predicate only if its code is added to
   `CLAUSE_GATES` — one dictionary and one test.
2. **The predicate may be stricter, never looser.** `contact_ready_predicate().ok == True` must imply
   that `check_send_eligibility(stage='SELECT')` returned no `BLOCK` on any gate in `CLAUSE_GATES`.
   Test 4 in §4.12.4 asserts this over the whole fixture corpus. The reverse implication does not
   hold and is not meant to: C7 has no gate today, so the predicate blocks businesses the engine
   would allow.
3. **`CONTACT_READY` is never treated as permission.** It is a *precondition*. The send path
   re-evaluates everything at PREVIEW and again at SEND under the write lock. A stale
   `CONTACT_READY` row is a stale cache, not a licence — which is exactly why §4.9.4 demotes on a
   schedule instead of trusting the state to age gracefully.

One consequence worth stating because it changes a query somebody else owns: a business held back by
C5 or C7 stays `VERIFIED`, and `05-outreach-workflow.md` §5.4.2's grid `CASE` would label it
`D_NOT_VERIFIED` — the one wrong sentence on an otherwise accurate screen. The fix is one branch,
placed above the existing `D_NOT_VERIFIED` arm:

```sql
         WHEN b.status = 'VERIFIED'
              AND b.contact_ready_block_code IS NOT NULL THEN b.contact_ready_block_code
```

Because clause codes *are* gate codes, this needs no new vocabulary anywhere. It is listed in "Open
questions" as a change this document requires in a document it does not own.

### 4.3.7 When the predicate is evaluated

`refresh_contact_readiness()` is called at exactly these points. Anything else that changes a clause
input without calling it is a bug, and test 6 in §4.12.4 is the grep that finds it.

| # | Event | Caller | Clauses it can change |
|---|---|---|---|
| P1 | A verification is submitted with `verdict='VERIFIED'` | `POST /api/v1/verifications/<id>/submit`, same transaction | C1 |
| P2 | A contact is added, edited, confirmed, deactivated or deleted | the contact editor and the §4.6.7 confirm dialog | C3, C4 |
| P3 | A `suppressions` row is inserted | `radar/policy.py::suppress()` | C4 |
| P4 | A response is classified | `radar/classify.py` | C2, C5 |
| P5 | A message reaches `SENT` | `radar/outreach.py::record_send()` | C5 — for this business it is T19 into `CONTACTED`; the send also moves `F_RECENT_CAMPAIGN` for **every other campaign** that includes the row, so the predicate is re-evaluated for each `campaign_businesses` row |
| P6 | An `opportunities` row is recomputed | `radar/score.py` | C6, C7 |
| P7 | A research run completes | `radar/research.py` | C6, C7, plus the §4.9.2 triggers |
| P8 | `contact_policy` is saved | `POST /api/v1/settings` | C1, C3, C5, C7 — batched over the affected campaign, capped at `verify.refresh_batch_max` per transaction |
| P9 | A campaign is closed or reopened | `radar/jobs.py::campaign_finalize` | C2 |
| P10 | Nightly | `staleness_sweep` (§4.9.5) | all seven — the backstop for every event above that somebody forgot to wire |

P10 exists because P1–P9 is a list somebody has to maintain. The sweep costs one indexed pass over
`v_contact_ready` per night, and it is the only reason a missed call site degrades into "a business
was promoted a few hours late" rather than "a business was never promoted at all".

---

## 4.4 The verification schema

Five tables. `verifications` is the signature, `verification_checks` is the nine answers,
`verification_check_defs` is the catalogue of the nine questions, `verification_reason_codes` is the
rejection taxonomy, and `verification_sources` is the anti-rubber-stamp evidence that Sagar actually
opened something.

**Two of the five are defined elsewhere.** `01-data-model.md` §1.2.5 rules that `01` §1.8 defines
`verifications` and `verification_checks`, built to carry every column this document reads, and that
"if `04` later prints `verifications` DDL that differs from §1.8, §1.8 wins". This document
therefore prints no DDL for either table and drops the two names from its ownership paragraph. What
it owns here is `verification_check_defs`, `verification_reason_codes`, `verification_sources`, the
behaviour triggers on `verifications` and `verification_checks`, and the meaning of every column —
which is the part that decides whether a message may be sent.

### 4.4.1 `verifications`

**The DDL is `01-data-model.md` §1.8.1, in `radar/migrations/010_verifications.sql`.** It is not
reprinted here. An earlier draft of this section printed a competing `CREATE TABLE verifications`
and the two disagreed on six things, one of them fatal: `verdict` was constrained to
`('VERIFIED','REJECTED')` while T08, T13 and T18 write `SKIPPED`, so every "decide later" would have
aborted on a `CHECK` in the same transaction as the status change. §1.8.1 wins, per §1.2.5.

What this document depends on, and where each column is used:

| Column (`01` §1.8.1) | This document reads it at |
|---|---|
| `state` (`DRAFT`/`SUBMITTED`/`ABANDONED`) | §4.6.3 drafts, §4.6.4 submit, the sweep's `ABANDONED` pass |
| `verdict` (`VERIFIED`/`REJECTED`/`SKIPPED`, nullable) | invariant V1, T05–T08, T12–T13, T17–T18, §4.6.6 |
| `mode` (`FULL`/`QUICK_REJECT`/`RECHECK`) | §4.7.6's considered-vs-batched audit, §4.9.3's targeted recheck |
| `checks_total` (always 9), `checks_passed`, `checks_failed` | §4.6.2's "all nine", trigger (2) in §4.2.7, gate D4 |
| `reason_code` -> `verification_reason_codes(code)`, `reason_note` | §4.6.5, §4.6.6 |
| `why_note`, `dwell_ms`, `dwell_required_ms` (default 20000) | §4.7.3, §4.7.5, the V1 row-level `CHECK` |
| `sources_visited`, `sources_waived` — **JSON arrays of `sources.id`**, not counters | §4.7.2. Counts are `json_array_length(...)`; the identities are what makes a waiver auditable |
| `trigger_reason`, `recheck_scope`, `prior_verification_id` | §4.9.2, §4.9.3, T29 |
| `superseded_at`, `superseded_by`, `superseded_reason` | T10–T18, §4.9 |
| `research_run_id`, `research_fingerprint`, `contact_fingerprint` | §4.9.6 |
| `verified_by`, `verified_at`, `note`, `session_id`, `started_at` | §48 provenance, §4.11.2's payload |
| `campaign_id` — **nullable** | §4.11.2. A revocation from `/business/<id>`, a sweep demotion and a merge all happen outside a campaign context; `01` §1.2.2 makes campaign membership a `campaign_businesses` fact, so a `NOT NULL` here would have forced a lie |

The two indexes everything else leans on are `01`'s: `ux_verifications_live` (at most one live
submitted verification per business) and `ux_verifications_draft`. Gate D's query, §4.3.3's `ver`
CTE, §5.5.3's "what Sagar ticked" panel and trigger (2) in §4.2.7 all assume that
`verdict='VERIFIED' AND superseded_at IS NULL` selects at most one row. The index makes it true in
the storage layer rather than in four callers' `ORDER BY ... LIMIT 1`.

Note that `01` §1.8.1's `ux_verifications_draft` is on `(business_id)` alone, not on
`(business_id, opened_by)`. On a single-operator deployment (`_CONTEXT.md` §2) the two are the same
constraint; the stricter one is `01`'s and this document uses it. §4.6.3's "idempotent per
(business, user)" therefore means "idempotent per business, and there is one user".

The columns this document uses that §1.8.1 does not carry are listed in "Open questions" as an
amendment request against §1.8.1 rather than being declared here, because a second `CREATE TABLE`
is exactly what produced the `SKIPPED` bug above.

Immutability after submit. These triggers are this document's, on `01`'s table; they need a
migration of their own after `010` (see "Open questions"). A submitted verification is evidence, and
evidence that can be edited is not evidence:

```sql
-- radar/migrations/056_verification_immutability.sql
CREATE TRIGGER trg_verifications_immutable
BEFORE UPDATE ON verifications
FOR EACH ROW
WHEN OLD.state = 'SUBMITTED'
 AND (NEW.state         <> OLD.state
   OR NEW.verdict       IS NOT OLD.verdict
   OR NEW.business_id   <> OLD.business_id
   OR NEW.checks_passed <> OLD.checks_passed
   OR NEW.checks_failed <> OLD.checks_failed
   OR NEW.checks_total  <> OLD.checks_total
   OR NEW.why_note      IS NOT OLD.why_note
   OR NEW.reason_code   IS NOT OLD.reason_code
   OR NEW.reason_note   IS NOT OLD.reason_note
   OR NEW.verified_at   IS NOT OLD.verified_at
   OR NEW.verified_by   IS NOT OLD.verified_by
   OR NEW.dwell_ms      <> OLD.dwell_ms)
BEGIN
    SELECT RAISE(ABORT,
      'a submitted verification is immutable; supersede it with a new row instead');
END;

CREATE TRIGGER trg_verifications_no_delete
BEFORE DELETE ON verifications
FOR EACH ROW
WHEN OLD.state = 'SUBMITTED'
BEGIN
    SELECT RAISE(ABORT, 'submitted verifications are never deleted');
END;

CREATE TRIGGER trg_verifications_touch
AFTER UPDATE ON verifications
FOR EACH ROW
BEGIN
    UPDATE verifications SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.id;
END;
```

The only columns a submitted row may ever change are `superseded_at`, `superseded_by` and
`superseded_reason`. That is what the `WHEN` clause above allows through, and it is the entire
mutation surface of the table after submission.

### 4.4.2 `verification_check_defs` and `verification_checks`

The nine questions live in a table, not in a Python list, because the screen renders their text, the
audit stores their keys, and §4.9.3 maps re-verification triggers onto subsets of them. One source
of truth for all three.

```sql
-- radar/migrations/009_verification_reason_codes.sql (continued)
--
-- 01-data-model.md §1.13.2 assigns 009 to this document for verification_reason_codes.
-- verification_check_defs ships in the same file, after it, because the two reference each other
-- (defs.default_reason -> codes.code, codes.applies_to_check -> defs.check_key) and one file with
-- a fixed statement order is how §1.13.3 handles every other mutual pair.
CREATE TABLE verification_check_defs (
    check_key        TEXT PRIMARY KEY
                       -- The same nine values as 01 §1.8.2's inline CHECK on
                       -- verification_checks.check_key. Duplicated deliberately: there is no FK
                       -- between the two tables, so this is what stops them drifting.
                       CHECK (check_key IN ('IDENTITY_CORRECT','IN_TARGET_CITY','CATEGORY_CORRECT',
                                            'APPEARS_OPERATIONAL','CONTACT_LEGITIMATE',
                                            'RESEARCH_RELEVANT','OPPORTUNITY_REASONABLE',
                                            'OUTREACH_APPROPRIATE','NO_DNC_RECORD')),
    ordinal          INTEGER NOT NULL UNIQUE CHECK (ordinal BETWEEN 1 AND 9),
    prompt           TEXT NOT NULL,       -- §16 verbatim; rendered as the checkbox label
    helper           TEXT NOT NULL,       -- one line under the checkbox: what to look at
    evidence_zone    TEXT NOT NULL,       -- the §4.5.2 zone the check is anchored to
    requires_source  INTEGER NOT NULL DEFAULT 0 CHECK (requires_source IN (0,1)),
    default_reason   TEXT NOT NULL REFERENCES verification_reason_codes(code)
);

-- Seeded below the verification_reason_codes seed (§4.6.5), so `default_reason` resolves.
INSERT INTO verification_check_defs
    (check_key, ordinal, prompt, helper, evidence_zone, requires_source, default_reason) VALUES
 ('IDENTITY_CORRECT', 1,
  'Business identity appears correct',
  'Name, address and website belong to one real business, not a directory stub or an aggregator page.',
  'Z2_IDENTITY', 1, 'NOT_A_BUSINESS'),
 ('IN_TARGET_CITY', 2,
  'Business is located in target city',
  'The address is in a campaign city, not a branch listing or a head office elsewhere.',
  'Z2_IDENTITY', 0, 'WRONG_CITY'),
 ('CATEGORY_CORRECT', 3,
  'Business category is correct',
  'The category drives the message template and the module list. A diagnostic lab tagged HOSPITAL gets the wrong pitch.',
  'Z2_IDENTITY', 0, 'WRONG_CATEGORY'),
 ('APPEARS_OPERATIONAL', 4,
  'Business appears operational',
  'Recent evidence of trading: a live site, a recent review, a listing checked this month.',
  'Z4_FINDINGS', 1, 'CLOSED_OR_DEFUNCT'),
 ('CONTACT_LEGITIMATE', 5,
  'Contact information appears to be a legitimate business contact',
  'A published business address or number, not a personal mobile scraped from a social profile.',
  'Z3_CONTACTS', 1, 'CONTACT_NOT_BUSINESS'),
 ('RESEARCH_RELEVANT', 6,
  'Research is relevant',
  'The observed findings are about this business, and they are about how it operates.',
  'Z4_FINDINGS', 1, 'RESEARCH_NOT_RELEVANT'),
 ('OPPORTUNITY_REASONABLE', 7,
  'Software opportunity appears reasonable',
  'The problem, the modules and the score are ones you would defend to the owner in person.',
  'Z5_OPPORTUNITY', 0, 'OPPORTUNITY_NOT_CREDIBLE'),
 ('OUTREACH_APPROPRIATE', 8,
  'Outreach is appropriate',
  'Nothing about this business, its sector or its moment makes an unsolicited pitch a bad idea.',
  'Z5_OPPORTUNITY', 0, 'OUTREACH_INAPPROPRIATE'),
 ('NO_DNC_RECORD', 9,
  'No do-not-contact record exists',
  'No suppression, no prior opt-out, no complaint, no earlier permanent rejection on this business key.',
  'Z6_SUPPRESSION', 0, 'DO_NOT_CONTACT_RECORD');
```

**`verification_checks` is `01-data-model.md` §1.8.2**, in `radar/migrations/010_verifications.sql`,
and is not reprinted here. The differences matter, so they are named rather than glossed: `01` gives
the table a `chk_` surrogate `id` (registered in `radar/ids.py`'s `_PREFIXES`) with
`UNIQUE (verification_id, check_key)` rather than a composite primary key, adds `business_id` so
"has this business ever failed the contact-legitimacy check" is one index seek instead of a join
through `verifications`, and adds `evidence_ref` so an answer can point at the source that produced
it. It also constrains `check_key` **inline**, with the same nine values as
`verification_check_defs` — there is no foreign key between the two tables.

That inline `CHECK` is the constraint. `verification_check_defs` is a **presentation catalogue**:
prompt text, helper line, evidence zone, source requirement, default rejection reason. It exists so
the screen, the audit and §4.9.3's recheck scopes read one source of truth for the *wording* and the
*routing*, not so it can be the referent of a foreign key that `01` does not declare. The `CHECK` on
`check_key` above keeps the two from drifting: adding a tenth question means editing both, which is
correct — a tenth question changes the meaning of "all nine passed" and should not be a data edit.

`carried_from` (§4.8.3 / §4.9.3) is not in `01` §1.8.2. It is requested there as an additive column
in "Open questions"; nothing else in this document depends on where it lives.

The one trigger this document adds to `01`'s table, in the same migration as §4.4.1's:

```sql
-- radar/migrations/056_verification_immutability.sql (continued)
--
-- A failed check must say why. 01 §1.8.2 already carries
-- CHECK (passed <> 0 OR (note IS NOT NULL AND length(note) >= 10)), which holds on INSERT as
-- well as UPDATE, so no trigger is needed for it and none is declared here.

-- Answers are frozen once the parent is submitted.
CREATE TRIGGER trg_verification_checks_immutable
BEFORE UPDATE ON verification_checks
FOR EACH ROW
WHEN (SELECT state FROM verifications WHERE id = OLD.verification_id) = 'SUBMITTED'
BEGIN
    SELECT RAISE(ABORT, 'checks belonging to a submitted verification are immutable');
END;
```

All nine rows are inserted when the verification is opened, with `passed = NULL`. A checklist with
nine rows and three answers is a visible half-finished job; a checklist with three rows is
indistinguishable from a checklist someone truncated.

```sql
-- radar/verify.py :: OPEN_CHECKS_SQL
-- params: :verification_id, :business_id, and nine ids from radar/ids.py (chk_)
INSERT INTO verification_checks (id, verification_id, business_id, check_key, ordinal, passed)
SELECT :[id_for(d.ordinal)], :verification_id, :business_id, d.check_key, d.ordinal, NULL
  FROM verification_check_defs d
 ORDER BY d.ordinal;
```

(The nine `chk_` ids are generated in Python and bound positionally; SQLite has no id generator and
`01` §1.8.2's surrogate key is `NOT NULL`.)

### 4.4.3 `verification_reason_codes`

The rejection taxonomy, as data. §4.6.5 explains when to use each one; this is the shape and the
two constraints that make the safety rules structural.

```sql
-- radar/migrations/009_verification_reason_codes.sql
CREATE TABLE verification_reason_codes (
    code               TEXT PRIMARY KEY,
    label              TEXT NOT NULL,          -- the radio-button text on the reject panel
    guidance           TEXT NOT NULL,          -- when this one and not its neighbour
    applies_to_check   TEXT REFERENCES verification_check_defs(check_key),
    is_permanent       INTEGER NOT NULL CHECK (is_permanent IN (0,1)),
    cool_off_days      INTEGER NOT NULL CHECK (cool_off_days >= 0),
    writes_suppression INTEGER NOT NULL CHECK (writes_suppression IN (0,1)),
    suppression_reason TEXT
                         CHECK (suppression_reason IS NULL OR suppression_reason IN
                                ('UNSUBSCRIBE_LINK','REPLY_OPT_OUT','COMPLAINT','BOUNCE_HARD',
                                 'MANUAL','DNC_LIST','LEGAL_REQUEST')),
    bulk_ok            INTEGER NOT NULL CHECK (bulk_ok IN (0,1)),
    requires_note      INTEGER NOT NULL DEFAULT 0 CHECK (requires_note IN (0,1)),
    cancels_research   INTEGER NOT NULL DEFAULT 1 CHECK (cancels_research IN (0,1)),
    ordinal            INTEGER NOT NULL,

    -- A permanent rejection always writes the suppression that makes it permanent. Without this
    -- the two halves of "permanent" can drift apart and a permanent rejection becomes a label.
    CHECK (is_permanent = 0 OR writes_suppression = 1),
    CHECK (writes_suppression = 0 OR suppression_reason IS NOT NULL),
    -- Nothing that writes a suppression may be applied in bulk. This one CHECK is the whole of
    -- §4.8.1's "never bulk-appliable" rule, enforced where it cannot be forgotten.
    CHECK (bulk_ok = 0 OR writes_suppression = 0),
    CHECK (is_permanent = 0 OR cool_off_days = 0)   -- permanent has no cool-off; it has no exit
);

CREATE INDEX ix_reason_codes_bulk ON verification_reason_codes(bulk_ok, ordinal);
```

The seed is in §4.6.5, where the guidance text belongs next to the table that explains it.

### 4.4.4 `verification_sources`

One row per (verification, source) pair that the checklist depends on. This is what makes "the
sources must open" (§15, §14) checkable rather than aspirational, and it is the evidence behind
§4.7.2.

```sql
-- radar/migrations/055_verification_sources.sql
CREATE TABLE verification_sources (
    verification_id  TEXT NOT NULL REFERENCES verifications(id) ON DELETE CASCADE,
    source_id        TEXT NOT NULL REFERENCES sources(id),
    finding_ids      TEXT NOT NULL,      -- JSON array: which findings cite it, for the screen
    is_required      INTEGER NOT NULL DEFAULT 0 CHECK (is_required IN (0,1)),
    rank             INTEGER NOT NULL,   -- 1 = highest-weight citing finding; the top N are required
    visited_at       TEXT,
    visit_count      INTEGER NOT NULL DEFAULT 0,
    waived_at        TEXT,
    waive_reason     TEXT,
    fetch_status     TEXT                -- last known HTTP status from SOURCE_FETCHED, or 'DEAD'
                       CHECK (fetch_status IS NULL OR fetch_status IN
                              ('OK','DEAD','BLOCKED','UNCHECKED')),
    snapshot_path    TEXT,               -- audit sidecar from 11-audit-architecture.md §11.6.1
    PRIMARY KEY (verification_id, source_id),
    CHECK (waived_at IS NULL OR (waive_reason IS NOT NULL
                                 AND length(trim(waive_reason)) >= 10))
);

CREATE INDEX ix_verification_sources_open
    ON verification_sources(verification_id)
 WHERE is_required = 1 AND visited_at IS NULL AND waived_at IS NULL;
```

### 4.4.5 Id prefixes and migration order

`01-data-model.md` §1.13.2 owns the numbering: six documents allocated numbers independently and
eleven collided, so this document's earlier `005`–`014` are void. The sequence below is §1.13.2's,
with the four files it does not yet list marked as requests (see "Open questions").

| Table / object | Prefix | Migration | Owner |
|---|---|---|---|
| `verifications` | `ver_` (`_CONTEXT.md` §2) | `010_verifications.sql` | **01** (§1.8.1) |
| `verification_checks` | `chk_` — surrogate id, `radar/ids.py` | `010_verifications.sql` | **01** (§1.8.2) |
| `verification_reason_codes` | none — natural key | `009_verification_reason_codes.sql` | 04 |
| `verification_check_defs` | none — natural key | `009_verification_reason_codes.sql` | 04 — **§1.13.2's "Creates" column must name it too** |
| `business_status_transitions` | none — natural key | `011_business_status_transitions.sql` (§4.2.7) | 04 |
| `businesses` status provenance columns | — | folded into `003_businesses.sql` per §1.2.2 (§4.2.7) | 01 |
| the four `trg_biz_*` status triggers | — | `012_business_status_triggers.sql` (§4.2.7) | 04 |
| `verification_sources` | none — composite key | `055_verification_sources.sql` — **requested** | 04 |
| verification immutability triggers | — | `056_verification_immutability.sql` — **requested** | 04 |
| `v_contact_ready`, `v_contact_ready_business` | — | `057_v_contact_ready.sql` — **requested** (§4.3.3) | 04 |
| the V3 draft guard | — | `058_no_draft_before_contact_ready.sql` — **requested** (§4.10.4) | 04 |

Two ordering constraints this document contributes, in §1.13.3's terms:

- `verification_check_defs.default_reason` references `verification_reason_codes(code)` and
  `verification_reason_codes.applies_to_check` references `verification_check_defs(check_key)`. The
  migration runner applies each file in its own transaction with `PRAGMA foreign_keys = ON`, so both
  tables and both seeds go in `009`, in the order: codes table, defs table, codes seed, defs seed.
- `057` creates a view over `v_effective_policy` (`05-outreach-workflow.md` §5.3.1) and
  `campaign_businesses`, so it must follow `013_contact_policy.sql` and `004`. Appending it after
  §1.13.2's `054` satisfies both and matches §1.13.3's constraint C8 — views last.

---

## 4.5 The verification screen (§15)

### 4.5.1 What the screen is for

Spec §15: *"Add a VERIFY BUSINESS button. Business must NOT become outreach-eligible until verified.
Verification screen shows: Business Name, Category, Location, Website, Contact, Research Summary,
Sources, AI Recommendation, Potential Software Opportunity."*

Those nine items are the minimum. The screen's actual job is narrower and harder: **put every piece
of evidence the nine checks ask about within one click of the checkbox that asks about it.** A
checklist whose evidence is two screens away is a checklist that gets answered from memory.

The layout is one page, no tabs, no accordion that starts collapsed on anything a check depends on:

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Z1  HEADER   name · city · industry/category · score badge · confidence badge ·      │
│              status badge · queue position "12 of 38" · [ Skip ] [ Reject ]          │
├───────────────────────────────────────────┬──────────────────────────────────────────┤
│ Z2  IDENTITY                              │ Z7  THE CHECKLIST                        │
│     name, aka, address, maps link,        │     nine checkboxes, each anchored to    │
│     website + last probe, listing url     │     its zone, each with a note field     │
│     [checks 1,2,3]                        │     that opens when answered "no"        │
├───────────────────────────────────────────┤                                          │
│ Z3  CONTACTS                              │     ─────────────────────────────────    │
│     one row per business_contacts row:    │     WHY (>= 15 chars, required)          │
│     raw · normalised · provenance ·       │                                          │
│     [Confirm] [Not a business contact]    │     sources 3 of 3 opened                │
│     [checks 5]                            │     time on page 00:47 / 00:47           │
├───────────────────────────────────────────┤                                          │
│ Z4  RESEARCH  observed / inferred /       │     [ APPROVE — all nine ticked ]        │
│     unknown, verbatim, each with its      │     [ Reject with a reason ]             │
│     source refs   [checks 4,6]            │     [ Save draft ]  [ Skip for now ]     │
├───────────────────────────────────────────┤                                          │
│ Z5  OPPORTUNITY  problem · solution ·     │  Z8  HISTORY                             │
│     modules · benefit · score · why-86    │      prior verifications, prior verdicts │
│     [checks 7,8]                          │      on this business, outreach so       │
├───────────────────────────────────────────┤      far, responses so far               │
│ Z6  SUPPRESSION & DNC  [check 9]          │                                          │
└───────────────────────────────────────────┴──────────────────────────────────────────┘
```

`Z7` is sticky on desktop and collapses to the bottom of the flow on narrow screens. The approve
control is inside `Z7` and nowhere else: there is no duplicate approve at the top of the page,
because a control that is reachable before the evidence has been scrolled past is a control that
gets used that way.

### 4.5.2 Element contract

Every element, its exact source, and what clicking it does. `E##` ids are stable and are used by the
template, the API payload keys and the tests.

| Id | Zone | Element | Source (table.column or query) | Click-through |
|---|---|---|---|---|
| E01 | Z1 | Business name | `businesses.name` | — |
| E02 | Z1 | City | `businesses.city` | filters the queue to that city |
| E03 | Z1 | Industry / category | `businesses.industry`, `businesses.category` | opens the category corrector (§4.6.5, `WRONG_CATEGORY`) |
| E04 | Z1 | Opportunity score + band | `opportunities.score`, `.band` where `is_current = 1` | anchors to E22 |
| E05 | Z1 | Research confidence | `opportunities.confidence`, `.confidence_pct` | anchors to E18 |
| E06 | Z1 | Status badge | `businesses.status` | — |
| E07 | Z1 | Queue position | `ROW_NUMBER()` over the §4.5.4 queue query | previous / next in queue |
| E08 | Z2 | Address | `businesses.address` | opens a maps search for `name + address` in a new tab |
| E09 | Z2 | Website + probe result | `businesses.website`, `businesses.website_status`, `sources.checked_at` of the `SITE` source | opens `businesses.website` in a new tab, `rel="noopener noreferrer nofollow"`, and records a source visit if that URL is a cited source |
| E10 | Z2 | Listing URL | `businesses.listing_url` | opens in a new tab |
| E11 | Z2 | Size band | `businesses.size_band` | — |
| E12 | Z2 | Discovered | `businesses.discovered_at`, `audit_log` `BUSINESS_DISCOVERED` `detail.discovery_source` | opens the audit row |
| E13 | Z2 | Duplicate hint | open `merge_candidates` rows naming this business (`01-data-model.md` §1.12.5) — `business_key` itself is `UNIQUE`, so an exact duplicate cannot exist | opens the candidate pair at `/business/<id>` |
| E14 | Z2 | **Prior verdict banner** | the most recent `SUBMITTED` verification on this business, live or superseded (`resolve_prior_verdict()`) | opens that verification's read-only detail |
| E15 | Z3 | Contact row | `business_contacts.{kind, value_display, value_norm, domain, person_name, is_role_address}` | — |
| E16 | Z3 | Contact provenance | `business_contacts.{source_ref, source_url, captured_at}` | opens `source_url`, or the `sources` row behind `source_ref` |
| E17 | Z3 | Confirm control | writes `business_contacts.human_verified = 1` (§4.6.7) | — |
| E18 | Z4 | Findings, three fieldsets | `research_findings.{kind, dimension, label, statement, confidence, confidence_pct}` for the latest `COMPLETE` run, rendered verbatim, `OBSERVED` / `INFERRED` / `UNKNOWN` in that order, empty fieldsets shown as empty | each statement anchors to its sources |
| E19 | Z4 | Source list | `sources.{name, url, source_type, checked_at}` + `finding_sources.excerpt` | **opens the live URL**; a second link opens the stored snapshot (§4.5.3) |
| E20 | Z4 | Research run meta | `research_runs.{depth, finished_at, model_id, prompt_version}` | opens the `RESEARCH_RUN_COMPLETED` audit row |
| E21 | Z5 | Problem / solution / benefit | `opportunities.{potential_problem, potential_solution, expected_benefit}` | — |
| E22 | Z5 | Score breakdown ("why 86") | `opportunities.score_breakdown` JSON, each component's `because_finding_id` | each component anchors to the finding in E18 |
| E23 | Z5 | Recommended modules | `opportunity_modules.{module, ordinal, rationale}` | — |
| E24 | Z5 | AI recommendation | `opportunities.{band, confidence}` rendered as the fixed sentence in §4.5.5 | — |
| E25 | Z6 | Suppression status | live `suppressions` rows matching the business or its contacts (§4.3.3 `suppressed` CTE) | opens the suppression's source row (`rsp_` / `msg_` / `aud_`) |
| E26 | Z6 | Prior responses | `responses.{classification, received_at, body_excerpt}` for this business, across every campaign | opens `/business/<id>#history` |
| E27 | Z6 | Prior permanent rejection | `verifications` + `verification_reason_codes.is_permanent` for this business | opens that verification |
| E28 | Z7 | The nine checkboxes | `verification_check_defs.{ordinal, prompt, helper}` + `verification_checks.{passed, note, carried_from}` | each anchors to `evidence_zone` |
| E29 | Z7 | Why-note | `verifications.why_note` | — |
| E30 | Z7 | Source progress | `verification_sources` counts | opens the first unvisited required source |
| E31 | Z7 | Dwell meter | client timer vs `verifications.dwell_required_ms` | — |
| E32 | Z7 | Approve control | disabled until §4.6.4's ladder passes | `POST /api/v1/verifications/<id>/submit` |
| E33 | Z7 | Reject control | opens the reason panel (§4.6.5) | `POST .../submit` with `verdict='REJECTED'` |
| E34 | Z7 | Save draft / Skip | `verifications.state` | `PUT .../checks/<key>` / `POST /api/v1/businesses/<id>/skip` |
| E35 | Z8 | Prior verifications | `verifications` for this business, newest first, with verdict, author, mode and supersession reason | opens each read-only |
| E36 | Z8 | Outreach so far | `outreach_messages.{channel, status, sent_at}` | opens `/outreach/<draft_id>` |
| E37 | Z8 | Staleness banner | `verifications.trigger_reason` + `recheck_scope` (§4.9.3) | — |

Two elements are absent by design and their absence is tested (§4.10.2): there is **no** send
control, and there is **no** "verify all" control. See §4.7.4 and §4.10.

### 4.5.3 "The user must be able to open the source" — what that requires

§14 says the user must be able to open the source. On a screen whose whole purpose is checking, a
link that 404s is worse than no link: it teaches Sagar that the source column is decorative.

| Case | What E19 renders | Why |
|---|---|---|
| `sources.url` absolute `http`/`https`, last probe `OK` | Live link, opens in a new tab. Hover shows `checked_at` in full ISO | The normal case |
| Live link plus a **snapshot** link | `snapshot_path` from the `SOURCE_FETCHED` audit sidecar (`11-audit-architecture.md` §11.6.1, retention `P3Y`) | The page changes or dies between research and verification; the snapshot is what the finding was actually derived from |
| Last probe failed or the URL is dead | Link rendered struck-through with a `DEAD` chip, snapshot link primary, and check 4 (`APPEARS_OPERATIONAL`) pre-highlighted as needing attention | A dead source is itself evidence about check 4, so the screen routes it there instead of hiding it |
| `sources.url` is not absolute `http(s)` | Name only, `title="URL withheld: not an absolute http(s) URL"` | Matches `03-html-report.md` §3.4.6.3's `safe_url` rule exactly, so live and exported views agree |
| A finding with no `finding_sources` row | Rendered with a `no source` badge and **excluded from the citable set** | Same rule as the report; the policy engine's view of citable findings and the screen's must match |

Clicking a source link fires a beacon that records the visit. It is a `POST`, it is fire-and-forget,
and a failure to record it never blocks the navigation:

```http
POST /api/v1/verifications/ver_01JSAMPLE00000000000000V1/sources/src_01JSAMPLE0000000000000S1/visited
Content-Type: application/json

{"target": "LIVE"}          // or "SNAPSHOT"
-> 204 No Content
```

Which sources are **required** (`verification_sources.is_required = 1`): the top
`verify.source_visit_required_top_n` sources ranked by the highest `research_findings.weight` among
the `OBSERVED` findings that cite them. Not all of them — a research run can cite eleven sources and
requiring eleven visits is how §4.7's medicine becomes the disease.

### 4.5.4 The screen payload

```http
GET /api/v1/verifications/biz_01JSAMPLE00000000000000A1
```

```json
{
  "business": {
    "id": "biz_01JSAMPLE00000000000000A1",
    "name": "SAMPLE Diagnostics Centre",
    "city": "Dhule", "industry": "HEALTHCARE", "category": "DIAGNOSTIC_CENTER",
    "size_band": "SMALL", "status": "NEEDS_VERIFICATION",
    "address": "SAMPLE — Station Road, Dhule 424001",
    "website": "https://sample-diagnostics.example.in",
    "website_status": "OK", "website_checked_at": "2026-08-24T04:11:02Z",
    "listing_url": "https://listing.example/sample-diagnostics",
    "business_key": "d:sample-diagnostics.example.in",
    "discovered_at": "2026-08-22T19:40:11Z"
  },
  "opportunity": {
    "id": "opp_01JSAMPLE0000000000000O1",
    "score": 86, "band": "HIGH", "confidence": "MEDIUM", "confidence_pct": 64,
    "potential_problem": "SAMPLE — report delivery is tracked on paper …",
    "potential_solution": "SAMPLE — …",
    "expected_benefit": "SAMPLE — …",
    "modules": [{"module": "Workflow", "ordinal": 1, "rationale": "SAMPLE — …"}],
    "score_breakdown": [
      {"component": "digital_maturity", "points": 22, "of": 25,
       "because_finding_id": "res_01JSAMPLE0000000000000F1"}
    ]
  },
  "findings": {
    "OBSERVED": [
      {"id": "res_01JSAMPLE0000000000000F1", "dimension": "DIGITAL_MATURITY",
       "label": "SAMPLE — no online report portal",
       "statement": "SAMPLE — the site lists a phone number for report collection and no portal.",
       "confidence": "HIGH", "confidence_pct": 82,
       "sources": [{"id": "src_01JSAMPLE0000000000000S1", "ref": 1}]}
    ],
    "INFERRED": [], "UNKNOWN": []
  },
  "sources": [
    {"id": "src_01JSAMPLE0000000000000S1", "ref": 1, "name": "SAMPLE — official website",
     "url": "https://sample-diagnostics.example.in/reports",
     "source_type": "SITE", "checked_at": "2026-08-24T04:11:02Z",
     "excerpt": "SAMPLE — 'Collect your reports from the front desk between 9am and 8pm.'",
     "confidence": "HIGH", "fetch_status": "OK",
     "snapshot_url": "/api/v1/audit/sidecar/aud_01JSAMPLE000000000000AA1",
     "is_required": true, "rank": 1, "visited_at": null, "waived_at": null}
  ],
  "contacts": [
    {"id": "cnt_01JSAMPLE0000000000000C1", "kind": "EMAIL",
     "value_display": "info@sample-diagnostics.example.in",
     "value_norm": "info@sample-diagnostics.example.in",
     "domain": "sample-diagnostics.example.in",
     "is_role_address": true, "person_name": null,
     "human_verified": false, "is_active": true,
     "source_url": "https://sample-diagnostics.example.in/contact",
     "captured_at": "2026-08-22T19:44:03Z"}
  ],
  "suppression": {"blocked": false, "rows": []},
  "prior": {
    "verdict_banner": null,
    "verifications": [],
    "responses": [],
    "outreach": []
  },
  "verification": {
    "id": "ver_01JSAMPLE00000000000000V1",
    "state": "DRAFT", "mode": "FULL", "entry_point": "QUEUE",
    "started_at": "2026-08-27T06:02:10Z",
    "dwell_required_ms": 47000,
    "recheck_scope": null,
    "checks": [
      {"check_key": "IDENTITY_CORRECT", "ordinal": 1,
       "prompt": "Business identity appears correct",
       "helper": "Name, address and website belong to one real business, …",
       "evidence_zone": "Z2_IDENTITY", "passed": null, "note": null, "carried_from": null}
    ]
  },
  "queue": {"position": 12, "total": 38,
            "next_business_id": "biz_01JSAMPLE00000000000000A2"},
  "readiness_preview": {
    "ok": false, "failing_clause": "C1_VERIFIED_FRESH",
    "blocking_code": "D_NOT_VERIFIED",
    "blocking_sentence": "SAMPLE Diagnostics Centre is NEEDS_VERIFICATION — verify it before preparing outreach."
  }
}
```

(SAMPLE content throughout.) `readiness_preview` is `contact_ready_predicate()` run against the
business **as it is now**, so the screen can warn before the work rather than after: if C4 already
fails, the banner at the top of `Z6` says so, and Sagar can skip a business he would otherwise verify
and then watch bounce straight back to `VERIFIED`.

The queue itself:

```sql
-- radar/verify.py :: QUEUE_SQL
-- params: :campaign_id, :city (nullable), :industry (nullable), :limit, :offset
SELECT b.id AS business_id, b.name, b.city, b.industry, b.category,
       o.score, o.band, o.confidence, o.confidence_pct,
       v.trigger_reason, v.recheck_scope,
       COALESCE(draft.id, '')             AS draft_verification_id,
       COALESCE(cnt.n, 0)                 AS n_contacts,
       CASE WHEN sup.business_id IS NOT NULL THEN 1 ELSE 0 END AS is_suppressed
  FROM campaign_businesses cb
  JOIN businesses b         ON b.id = cb.business_id
  LEFT JOIN opportunities o ON o.business_id = b.id AND o.is_current = 1
  LEFT JOIN verifications v ON v.id = b.status_verification_id
  LEFT JOIN verifications draft
         ON draft.business_id = b.id AND draft.state = 'DRAFT'
  LEFT JOIN (SELECT business_id, COUNT(*) AS n FROM business_contacts
              WHERE is_active = 1 GROUP BY business_id) cnt ON cnt.business_id = b.id
  LEFT JOIN (SELECT DISTINCT business_id FROM v_contact_ready WHERE c4_no_suppression = 0) sup
         ON sup.business_id = b.id
 WHERE cb.campaign_id = :campaign_id
   AND cb.state       = 'INCLUDED'
   AND b.status       = 'NEEDS_VERIFICATION'
   AND (:city IS NULL     OR b.city     = :city)
   AND (:industry IS NULL OR b.industry = :industry)
 ORDER BY is_suppressed ASC,          -- already-blocked businesses last: verifying them is wasted
          o.score DESC,               -- the best opportunity first, while attention is freshest
          b.city, b.name
 LIMIT :limit OFFSET :offset;
```

Ordering by score descending is a deliberate anti-rubber-stamp choice (§4.7.7): attention degrades
through a session, so the businesses whose verification matters most are the ones seen first.

### 4.5.5 The AI recommendation, and what the screen must never do

§15 asks for an "AI Recommendation". The screen renders exactly one sentence, assembled from stored
columns with no LLM call at render time — the same rule `05-outreach-workflow.md` §5.5.3 applies to
the "why selected" panel:

```
Opportunity score {score} ({band}); research confidence {confidence} ({confidence_pct}%),
from {n_observed} observed and {n_inferred} inferred findings across {n_sources} sources.
```

Nothing on this screen is generated, re-worded or summarised at render time. Everything is a column
value or a count. If a string on the verification screen is not traceable to a row id the screen can
show, that is a bug — because the one thing this screen exists to do is let a human check the
machine, and a machine that re-writes its own evidence at check time cannot be checked.

Absent by design:

| Not on the screen | Why |
|---|---|
| Any send control | §19, §45. Enforced at three layers, §4.10 |
| A "verify all" / "approve remaining" control | §4.7.4 |
| Pre-ticked checkboxes | except carry-forward, which is labelled and audited (§4.8.3) |
| An LLM-generated summary of the research | it would be an unsourced claim on the screen whose job is checking sources |
| A "confidence" the AI assigns to *its own* verification | verification confidence is Sagar's, and it is expressed by ticking or not ticking |

---

## 4.6 The nine-item checklist (§16)

### 4.6.1 The nine items, verbatim

Spec §16's nine lines, unedited, each one row in `verification_check_defs` (§4.4.2) and one row in
`verification_checks` per verification. The wording on screen is the spec's wording; the `helper`
column carries the elaboration so the spec text stays quotable.

| # | `check_key` | Prompt (verbatim §16) | Evidence zone | Source visit required | What "no" usually means |
|---|---|---|---|---|---|
| 1 | `IDENTITY_CORRECT` | Business identity appears correct | Z2 | yes | `NOT_A_BUSINESS`, `DUPLICATE_OF_EXISTING` |
| 2 | `IN_TARGET_CITY` | Business is located in target city | Z2 | no | `WRONG_CITY` |
| 3 | `CATEGORY_CORRECT` | Business category is correct | Z2 | no | `WRONG_CATEGORY` |
| 4 | `APPEARS_OPERATIONAL` | Business appears operational | Z4 | yes | `CLOSED_OR_DEFUNCT` |
| 5 | `CONTACT_LEGITIMATE` | Contact information appears to be a legitimate business contact | Z3 | yes | `CONTACT_NOT_BUSINESS`, `NO_USABLE_CONTACT` |
| 6 | `RESEARCH_RELEVANT` | Research is relevant | Z4 | yes | `RESEARCH_NOT_RELEVANT` |
| 7 | `OPPORTUNITY_REASONABLE` | Software opportunity appears reasonable | Z5 | no | `OPPORTUNITY_NOT_CREDIBLE` |
| 8 | `OUTREACH_APPROPRIATE` | Outreach is appropriate | Z5 | no | `OUTREACH_INAPPROPRIATE`, `SENSITIVE_SECTOR`, `COMPETITOR_OR_CONFLICT` |
| 9 | `NO_DNC_RECORD` | No do-not-contact record exists | Z6 | no | `DO_NOT_CONTACT_RECORD`, `PRIOR_COMPLAINT` |

Item 9 is the only check the system can pre-compute, and it is deliberately **not** auto-ticked. The
screen shows the machine's answer next to the box — "no live suppression, no prior opt-out, no
permanent rejection on this business key" with each fact linked — and Sagar ticks it himself. The
reason is spec §30 and `_CONTEXT.md` invariant 3: the machine's suppression query is the same query
that will run at send time, so auto-ticking item 9 would make the checklist agree with the send path
by construction and prove nothing. What item 9 actually asks for is the thing the query cannot know:
a do-not-contact record that exists in Sagar's memory, his inbox, or a conversation at a wedding.

### 4.6.2 The three rules

> **All nine required.** `verdict = 'VERIFIED'` demands `checks_total = 9`, `checks_passed = 9`,
> `checks_failed = 0`. Enforced by a `CHECK` on `verifications` (§4.4.1), by trigger (2) in §4.2.7,
> and by gate D4 at send time. Three layers, because this is the definition of the gate.
>
> **Any single "no" routes to `REJECTED` with a mandatory reason.** There is no "eight of nine, note
> attached" outcome. Answering a check `passed = 0` requires a note of at least 10 characters on the
> check itself, and submitting requires a `reason_code` from `verification_reason_codes`. The
> default offered is the failed check's `default_reason`, and Sagar can pick another.
>
> **Partial completion saves as a draft.** `state = 'DRAFT'`, no verdict, no status change, no audit
> row beyond `VERIFICATION_SAVED`. A draft is resumable, is visible in the queue as "in progress",
> and expires (§4.6.3).

The middle rule is the one that draws objections, so here is the reasoning. The alternative — allow
a verification with one unticked box and a note — sounds humane and is corrosive: within a month the
common case becomes "eight ticks and 'contact not confirmed but the number looks fine'", and the
nine-check gate has become an eight-check gate with a free-text apology. The escape valve for "I do
not want to reject this, I just cannot answer today" already exists and is one click: **SKIP**. It
costs nothing, requires no reason, and is fully reversible (§4.2.5). Making rejection strict is only
defensible because parking is cheap.

### 4.6.3 Drafts

| Property | Rule |
|---|---|
| Created | On `POST /api/v1/verifications`, which is what `GET /verify/<id>` calls behind the screen. Idempotent per (business, user) via `ux_verifications_draft` |
| Saved | `PUT /api/v1/verifications/<id>/checks/<check_key>` per answer, plus a debounced save of `why_note`. No "save" button — the state is the answers |
| Audit | One `VERIFICATION_OPENED` on create; `VERIFICATION_SAVED` at most once per 60 s per verification (`11-audit-architecture.md` §11.6.2 deliberately has no per-checkbox action) |
| Visible | In the queue as "in progress, 4 of 9", and on `/business/<id>` |
| Status effect | **None.** A draft never changes `businesses.status`. `NEEDS_VERIFICATION` means "Sagar's move" whether or not he has started |
| Expiry | A draft with no write for `verify.draft_ttl_hours` (default 72) moves to `state = 'ABANDONED'` in the nightly sweep, with `VERIFICATION_ABANDONED`. Its answers are kept, and reopening starts a fresh draft that does **not** inherit them |
| Dwell | `active_ms` accumulates across sessions; `dwell_ms` is recomputed at submit from the server's own `started_at` (§4.7.3) |

Abandoned answers are not inherited because a three-day-old half-answered checklist is exactly the
input that produces a rubber stamp: the six ticks are already there, the work looks nearly done, and
finishing it costs three clicks and no attention.

### 4.6.4 Submit

```http
POST /api/v1/verifications/ver_01JSAMPLE00000000000000V1/submit
Content-Type: application/json
X-CSRF-Token: <session csrf>

{
  "verdict": "VERIFIED",
  "checks": [
    {"check_key": "IDENTITY_CORRECT",       "passed": true,  "note": null},
    {"check_key": "IN_TARGET_CITY",         "passed": true,  "note": null},
    {"check_key": "CATEGORY_CORRECT",       "passed": true,  "note": "SAMPLE — diagnostics, not a hospital; corrected."},
    {"check_key": "APPEARS_OPERATIONAL",    "passed": true,  "note": null},
    {"check_key": "CONTACT_LEGITIMATE",     "passed": true,  "note": null},
    {"check_key": "RESEARCH_RELEVANT",      "passed": true,  "note": null},
    {"check_key": "OPPORTUNITY_REASONABLE", "passed": true,  "note": null},
    {"check_key": "OUTREACH_APPROPRIATE",   "passed": true,  "note": null},
    {"check_key": "NO_DNC_RECORD",          "passed": true,  "note": null}
  ],
  "why_note": "SAMPLE — paper report collection confirmed on their own site; owner-run, 2 branches.",
  "contact_id_confirmed": "cnt_01JSAMPLE0000000000000C1",
  "active_ms": 61240,
  "client_fingerprint": "sha256:SAMPLE…"
}
```

The validation ladder, in order. The first failure returns and nothing is written:

| # | Check | HTTP | Error code |
|---|---|---|---|
| 1 | Session, CSRF, and a `users` row with the `verify` permission (`15-security-model.md`) | 401 / 403 | `NOT_AUTHORISED` |
| 2 | The verification exists, `state = 'DRAFT'`, and `opened_by` is this user | 409 | `NOT_YOUR_DRAFT` |
| 3 | `businesses.status` is still one this verdict can be applied from (§4.2.3) | 409 | `ILLEGAL_TRANSITION` — body names the T-number |
| 4 | Exactly nine `checks` entries, keys matching `verification_check_defs` | 400 | `CHECKLIST_MALFORMED` |
| 5 | Every `passed = false` entry has a note ≥ 10 chars | 400 | `FAILED_CHECK_NEEDS_NOTE` |
| 6 | If any `passed = false` -> `verdict` must be `REJECTED` | 400 | `FAILED_CHECK_REQUIRES_REJECTION` |
| 7 | `verdict = 'REJECTED'` -> `reason_code` resolves; `OTHER` needs ≥ 20 chars; `DUPLICATE_OF_EXISTING` needs `duplicate_of_business_id` | 400 | `REASON_REQUIRED` |
| 8 | `verdict = 'VERIFIED'` -> all nine `passed = true` | 400 | `INCOMPLETE_CHECKLIST` |
| 9 | `verdict = 'VERIFIED'` -> `why_note` ≥ 15 chars after trim | 400 | `WHY_NOTE_REQUIRED` |
| 10 | `verdict = 'VERIFIED'` -> every required source visited or waived | 400 | `SOURCES_NOT_REVIEWED` — body lists the source ids |
| 11 | `verdict = 'VERIFIED'` -> `now - started_at >= dwell_required_ms` (§4.7.3) | 400 | `DWELL_NOT_MET` — body gives the remaining ms |
| 12 | `verdict = 'VERIFIED'` -> no live suppression matches (C4) | 409 | `SUPPRESSED` |
| 13 | `verdict = 'VERIFIED'` -> `contact_id_confirmed` names an active contact of this business | 400 | `CONTACT_NOT_CONFIRMED` |

Steps 1–13 all run **before** `BEGIN IMMEDIATE`. Inside the transaction, in this order:

```python
with db.transaction(conn):                       # BEGIN IMMEDIATE
    freeze_checks(conn, ver_id, payload.checks)  # UPDATE verification_checks, then the rollup
    supersede_prior(conn, business_id, ver_id)   # ux_verifications_live must stay satisfiable
    submit(conn, ver_id, verdict, ...)           # state='SUBMITTED', verdict, verified_at/rejected_at
    if verdict == "VERIFIED":
        contacts.confirm(conn, payload.contact_id_confirmed)      # human_verified = 1
        set_status(conn, business_id, "VERIFIED",                  # T06; trigger (2) re-checks it all
                   actor_kind="HUMAN", actor_user_id=user.id,
                   verification_id=ver_id, reason="CHECKLIST_PASSED")
        audit.write(conn, action="BUSINESS_VERIFIED", ...)
        refresh_contact_readiness(conn, business_id)               # may chain to T09
    else:
        apply_rejection(conn, ver_id)                              # §4.6.6
```

`supersede_prior()` runs before `submit()` because `ux_verifications_live` is a unique index: writing
the new live row first would collide with the old one. Ordering a write against a partial unique
index is the kind of thing that works in every test until two verifications happen in one minute.

Response:

```json
{
  "verification_id": "ver_01JSAMPLE00000000000000V1",
  "verdict": "VERIFIED",
  "business_status": "CONTACT_READY",
  "readiness": {"ok": true, "failing_clause": null, "blocking_code": null},
  "next_business_id": "biz_01JSAMPLE00000000000000A2",
  "audit_ids": ["aud_01JSAMPLE000000000000AB1", "aud_01JSAMPLE000000000000AB2"]
}
```

Returning `business_status` rather than assuming `VERIFIED` matters: the promotion to
`CONTACT_READY` happens in the same transaction, and a screen that reported `VERIFIED` and then
showed a `CONTACT_READY` badge on refresh would teach Sagar that the states are noise.

### 4.6.5 The rejection reason taxonomy

Seventeen codes. Each one exists because it implies something different about what happens next: how
long before the business can be looked at again, whether a `suppressions` row is written, and
whether a later campaign may research it at all (§4.2.6).

```sql
-- radar/migrations/009_verification_reason_codes.sql (seed)
INSERT INTO verification_reason_codes
 (code, label, guidance, applies_to_check, is_permanent, cool_off_days,
  writes_suppression, suppression_reason, bulk_ok, requires_note, cancels_research, ordinal) VALUES
 ('WRONG_CATEGORY','Wrong category',
  'The business is real and in scope but the category is wrong, and the wrong category produces the wrong pitch. Prefer correcting the category and re-queueing over rejecting, unless the correct category is out of scope for this campaign.',
  'CATEGORY_CORRECT',        0,   0, 0, NULL, 1, 0, 0,  1),
 ('WRONG_CITY','Outside the target area',
  'The address is not in a campaign city. A branch in a campaign city with a head office elsewhere is not this - that is in scope.',
  'IN_TARGET_CITY',          0,   0, 0, NULL, 1, 0, 1,  2),
 ('NOT_A_BUSINESS','Not a real business',
  'A directory stub, an aggregator page, a duplicate listing with no independent existence, a personal profile. Nothing to contact.',
  'IDENTITY_CORRECT',        0,   0, 0, NULL, 1, 0, 1,  3),
 ('DUPLICATE_OF_EXISTING','Duplicate of a business already in the system',
  'The same real-world business as another row. Requires the other business id, which is what makes the report say "excluded, duplicate of X" rather than losing the row.',
  'IDENTITY_CORRECT',        0,   0, 0, NULL, 1, 0, 1,  4),
 ('CLOSED_OR_DEFUNCT','Closed or no longer trading',
  'Evidence of closure: dead site plus a closed listing, or a review saying so. 180-day cool-off because a business that looked shut last month probably still is.',
  'APPEARS_OPERATIONAL',     0, 180, 0, NULL, 0, 0, 1,  5),
 ('TOO_SMALL_NO_FIT','Too small for a custom system',
  'A one-person operation whose entire workflow is a phone and a notebook. Not a judgement about them; a judgement about whether a custom build is honest to propose.',
  'OPPORTUNITY_REASONABLE',  0,  90, 0, NULL, 0, 0, 1,  6),
 ('ALREADY_HAS_SOFTWARE','Already running a comparable system',
  'Evidence of an existing system that covers the recommended modules. Different from a response classified ALREADY_HAVE_SOFTWARE, which arrives after contact.',
  'OPPORTUNITY_REASONABLE',  0, 180, 0, NULL, 0, 0, 1,  7),
 ('NO_USABLE_CONTACT','No usable business contact',
  'Nothing to write to, and nothing findable. Prefer SKIP if you intend to look again; rejection here means you looked and there is nothing.',
  'CONTACT_LEGITIMATE',      0,  30, 0, NULL, 0, 0, 0,  8),
 ('CONTACT_NOT_BUSINESS','Contact is personal, not a business contact',
  'A personal mobile or private address scraped from a social profile. DPDP purpose limitation: we have no defensible reason to hold it, and the erasure path runs from this rejection.',
  'CONTACT_LEGITIMATE',      0,  30, 0, NULL, 0, 1, 0,  9),
 ('RESEARCH_NOT_RELEVANT','Research is about something else',
  'The findings are about a different business, or about nothing operational. Rejecting keeps the research; re-research is available after the cool-off.',
  'RESEARCH_RELEVANT',       0,  14, 0, NULL, 0, 1, 0, 10),
 ('OPPORTUNITY_NOT_CREDIBLE','Opportunity is not credible',
  'You would not defend this problem statement or this score to the owner. Rejecting here is a signal to the scoring model, not only to this row.',
  'OPPORTUNITY_REASONABLE',  0,  90, 0, NULL, 0, 1, 0, 11),
 ('OUTREACH_INAPPROPRIATE','Outreach would be inappropriate',
  'Something about this business or this moment makes an unsolicited pitch wrong - a bereavement, a closure notice, a public crisis. A year, because the circumstance usually passes.',
  'OUTREACH_APPROPRIATE',    0, 365, 0, NULL, 0, 1, 1, 12),
 ('EXISTING_RELATIONSHIP','Existing client or relationship',
  'Already a client, or a personal relationship that makes cold outreach absurd. Not permanent, because the right way to contact them is outside this system entirely.',
  'OUTREACH_APPROPRIATE',    0,   0, 0, NULL, 0, 0, 1, 13),
 ('SENSITIVE_SECTOR','Sensitive sector - never contact',
  'A sector where unsolicited software outreach is inappropriate as a policy, not as a judgement call. Permanent, and it writes a suppression.',
  'OUTREACH_APPROPRIATE',    1,   0, 1, 'MANUAL',      0, 1, 1, 14),
 ('COMPETITOR_OR_CONFLICT','Competitor or conflict of interest',
  'A competitor, a client of a competitor, or anyone where contact creates a conflict. Permanent, and it writes a suppression.',
  'OUTREACH_APPROPRIATE',    1,   0, 1, 'MANUAL',      0, 1, 1, 15),
 ('DO_NOT_CONTACT_RECORD','A do-not-contact record exists',
  'They have asked not to be contacted - anywhere, by any route, including a conversation you had in person. Permanent, and it writes a DNC_LIST suppression.',
  'NO_DNC_RECORD',           1,   0, 1, 'DNC_LIST',    0, 1, 1, 16),
 ('PRIOR_COMPLAINT','Prior complaint',
  'They complained about being contacted, by us or about this kind of outreach. Permanent, and it writes a COMPLAINT suppression.',
  'NO_DNC_RECORD',           1,   0, 1, 'COMPLAINT',   0, 1, 1, 17),
 ('OTHER','Other - explain',
  'Nothing above fits. Requires 20 characters. If OTHER exceeds 10% of rejections in a month the taxonomy is wrong and needs a new code, which is a migration.',
  NULL,                      0,  30, 0, NULL, 0, 1, 1, 18);
```

Three properties of this table are load-bearing:

- **`is_permanent = 1` implies `writes_suppression = 1`**, by `CHECK`. "Permanent" that does not write
  a suppression is a label a future query forgets to read; a suppression is enforced by gate A on
  every channel and by C4 on every promotion.
- **`writes_suppression = 1` implies `bulk_ok = 0`**, by `CHECK`. §4.8.1's central rule — no bulk
  action may create an irreversible record — is enforced in the catalogue rather than in the bulk
  endpoint, so a new code cannot accidentally be both.
- **`cancels_research = 0` for the clerical codes.** Rejecting for `WRONG_CATEGORY` does not throw
  away a completed research run; the row can be corrected and re-queued. Rejecting for
  `CLOSED_OR_DEFUNCT` cancels queued research jobs, because there is nothing left to research.

### 4.6.6 What a rejection actually does

`apply_rejection()`, in one transaction:

| # | Step | Detail |
|---|---|---|
| 1 | Freeze the checks | Whatever was answered, including the `passed = 0` row and its note |
| 2 | Submit the verification | `state='SUBMITTED'`, `verdict='REJECTED'`, `rejected_at`, `reason_code`, `reason_note` |
| 3 | Supersede any prior live verification | `superseded_reason = 'REJECTED'` |
| 4 | `set_status(... 'REJECTED', actor_kind='HUMAN' ...)` | T05 / T07 / T12 / T17 depending on the source state |
| 5 | Remove live selections | `selections.state = 'REMOVED'`, reason `BUSINESS_REJECTED` |
| 6 | Cancel drafts in flight | `outreach_messages` in `DRAFT` / `POLICY_BLOCKED` / `PENDING_APPROVAL` -> `CANCELLED`. `APPROVED` and `QUEUED` are left to the SEND-stage gate, per §4.3.5 |
| 7 | If `cancels_research = 1` | Queued `research_business` jobs for this business are cancelled (`14-background-jobs.md`) |
| 8 | If `writes_suppression = 1` | `INSERT INTO suppressions (scope='BUSINESS', value_norm=<business_id>, reason=<suppression_reason>, source='verification', source_ref=<verification_id>)`. Never released by the app, ever |
| 9 | Audit | `BUSINESS_REJECTED` (CRITICAL), plus `BUSINESS_STATUS_CHANGED`, plus `SUPPRESSION_CREATED` from step 8 |
| 10 | Recompute campaign counters | `n_qualified`, `n_verified` |

Step 8 is the step that makes rejection meaningful across campaigns. Without it, `REJECTED` lives on
one `businesses` row, and §4.2.6's rediscovery logic is the only thing standing between a permanent
rejection and a message six months later. With it, there are two independent mechanisms, and the
second one is the one that also blocks a manual send, an export deep link and a `wa.me` click.

### 4.6.7 Check 5 and the contact confirmation

Check 5 is the only check that writes to a table outside this document. `08-whatsapp-integration.md`
§8.5.7 already states the contract: *"The verification screen shows raw and normalised side by side.
Sagar ticking the box sets `human_verified = 1`."*

| Element | Behaviour |
|---|---|
| E15 | One row per `business_contacts` row: `value_display` (as captured) beside `value_norm` (as the suppression tables and the send path will see it), `kind`, `domain`, `is_role_address`, `person_name` |
| E16 | Provenance: `source_url` opens the page the contact came from; `captured_at`; "no provenance recorded" in red for a named individual, which is gate E4's DPDP block waiting to happen |
| E17 | `[Confirm this is a business contact]` writes `human_verified = 1`, `human_verified_at`, `human_verified_by`, and calls `refresh_contact_readiness()`. `[Not a business contact]` writes `is_active = 0` with a reason |
| Check 5 | Cannot be ticked `passed = 1` unless at least one contact on the business has `human_verified = 1`. The screen disables the tick and points at E17 |
| Submit | `contact_id_confirmed` records **which** contact carried the tick, so §5.5.3's panel can say "you confirmed info@… on 27 Aug" rather than "contact confirmed" |

A phone number is confirmed the same way, and confirming it is what makes `wa.me` and the call
script legal to prepare — not what makes anything send.

---

## 4.7 Anti-rubber-stamp design

### 4.7.1 The failure this section exists to prevent

A checklist that takes four seconds is not a gate; it is a log entry that says a gate happened. And
it is worse than no checklist, because every document downstream of it — the message engine's claim
policy, §48's audit record, the "why was this selected" panel — treats `VERIFIED` as a human
statement about reality. If that statement is a reflex, the whole chain is a very well-audited lie.

The design constraints are unusual and worth stating, because they rule out most of the standard
answers:

- **The operator is the owner.** Sagar cannot be prevented from rubber-stamping; he can only be
  prevented from doing it *accidentally* or *unknowingly*. Nothing here is a security control.
- **The system's value is proportional to his attention.** Fifty rubber-stamped verifications are
  worth less than five considered ones, because five good messages beat fifty that misread the
  business.
- **Friction is a budget, not a virtue.** Every second added is a second he pays for on every row,
  forever. Measures that cost attention without producing evidence are rejected in §4.7.9.

So the four measures below share one property: each of them produces a **stored artefact** that an
audit can read, rather than merely slowing things down.

### 4.7.2 Measure 1 — required sources are visited, or waived with a reason

The top `verify.source_visit_required_top_n` (default 3) sources, ranked by the weight of the
`OBSERVED` findings citing them, are marked `is_required = 1` when the verification is opened. The
approve control stays disabled while any of them has neither `visited_at` nor `waived_at`.

| Path | Mechanics | Stored |
|---|---|---|
| Visit | Clicking E19's link fires the §4.5.3 beacon | `visited_at`, `visit_count`, `target` |
| Waive | `[Skip this source]` opens a required reason field (≥ 10 chars) | `waived_at`, `waive_reason` |
| Dead source | A source with `fetch_status = 'DEAD'` is auto-waived with `waive_reason = 'source unreachable at verification time'` and does not count against Sagar | `waived_at`, the auto reason |

Honesty about what this measures: **an opened link is not a read link.** This catches "verified
without ever looking at the evidence", which is the common failure, and it does not catch "opened it
and skimmed". That is fine — the point is not to police reading, it is to make skipping the evidence
a deliberate act with a name attached. A waiver rate above `verify.waiver_alert_pct` (default 40%)
over a rolling 30 days produces a Telegram note, because a high waiver rate means either the sources
are bad or the measure has become a formality, and both are worth knowing.

### 4.7.3 Measure 2 — a minimum dwell before approve enables

```python
def dwell_required_ms(n_in_scope_checks: int, cfg: VerifyConfig) -> int:
    """Milliseconds between opening the screen and being allowed to approve.

    Scales with how much is actually being asked. A targeted re-verification of two checks
    (§4.9.3) does not deserve the same wait as a first verification of nine, and pretending
    otherwise is how a sensible rule becomes a thing to route around.
    """
    return cfg.dwell_base_ms + cfg.dwell_per_check_ms * n_in_scope_checks
```

At the recommended settings — `dwell_base_ms = 20000`, `dwell_per_check_ms = 3000` — a full nine-check
verification requires 47 s and a two-check targeted recheck requires 26 s.

| Property | Rule |
|---|---|
| Applies to | `verdict = 'VERIFIED'` only. **Rejection and skip have no dwell requirement at all** |
| Client meter | E31 counts *active* time: the tab focused, with input or scroll in the last 30 s. Purely a UX affordance |
| Server enforcement | Step 11 of §4.6.4 compares `now - verifications.started_at` (the server's own timestamp, from the row it wrote) against `dwell_required_ms`. The client's `active_ms` is stored for the audit and **is not trusted for the decision** |
| Stored | `dwell_ms` (server-measured), `active_ms` (client-reported), `dwell_required_ms` (what was in force) |
| Setting to zero | Permitted, logged as a `CONFIG_CHANGED` audit row, and surfaced on `/settings` as "verification dwell disabled" — a visible state, not a silent one |

The asymmetry between approve and reject is the whole design in one line. **Approving is the
expensive action, because it is the one that authorises a message to a stranger.** Rejecting costs a
reason and nothing else, and skipping costs a click. When a checklist is slow to pass and instant to
decline, the path of least resistance under time pressure is to *not* contact somebody, which is
exactly where the pressure should push.

### 4.7.4 Measure 3 — there is no "verify all" control

Not disabled. Not permission-gated. **Absent**, at every layer:

| Layer | What is absent |
|---|---|
| Template | No macro renders a multi-row approve. `test_no_bulk_verify_control` greps `templates/` for `verify-all`, `approve-all`, `approve_selected`, `verify_selected` and fails the build on a hit |
| API | `POST /api/v1/verifications/bulk` exists and rejects `verdict = 'VERIFIED'` with 400 `BULK_VERIFY_FORBIDDEN` before reading the body's row list |
| Data | `CHECK (bulk_batch_id IS NULL OR verdict <> 'VERIFIED')` on `verifications`, so the row cannot exist. Requested against `01-data-model.md` §1.8.1 in "Open questions" — until it lands, the endpoint and the template grep are the only two layers, which is one fewer than this rule deserves |
| Queue | The queue offers "next" and "previous", never "select rows" with an approve action |

The reason it is absent rather than disabled is behavioural: a greyed-out "Verify all (17)" button
that becomes enabled under some condition is a permanent invitation, and the day the condition is
met by accident is the day 17 businesses are verified by one click.

### 4.7.5 Measure 4 — the why-note

`why_note`, minimum 15 characters after trimming, required for `VERIFIED` only, rendered verbatim in
`05-outreach-workflow.md` §5.5.3's "why was this selected" panel and in §48's audit record.

Fifteen characters is deliberately low. It is not an essay requirement; it is a *context switch*
requirement. Typing one specific sentence about this business forces the retrieval of at least one
concrete fact, which is the cheapest available test of whether the previous 47 seconds involved
reading. The screen refuses a note that exactly matches the previous verification's note (`400
WHY_NOTE_DUPLICATE`), which costs nothing to comply with honestly and blocks the obvious shortcut.

### 4.7.6 Measure 5 — the audit can tell considered from batched

Three fields distinguish a considered verification from every cheaper thing:

| Field | Considered | Bulk | Carry-forward | Targeted recheck |
|---|---|---|---|---|
| `verifications.mode` | `FULL` | `BULK` | `CARRY_FORWARD` | `RECHECK` |
| Audit action | `BUSINESS_VERIFIED` | `VERIFICATION_BULK_APPLIED` + one `BUSINESS_REJECTED`/`BUSINESS_SKIPPED` per row | `VERIFICATION_CARRIED_FORWARD` | `BUSINESS_VERIFIED` with `detail.mode = 'RECHECK'` |
| `detail_json` | `dwell_ms`, `active_ms`, `sources_visited/total`, `checklist{}` | `bulk_batch_id`, `bulk_size`, `filter{}` | `carried_from_verification_id`, inherited `verified_at` | `recheck_scope[]`, `carried_check_keys[]` |

The question this answers is a real one, six months out: *"this message went to a hospital that had
closed — was that verification a considered one?"* One query on `verifications.mode` and
`dwell_ms` answers it, and the answer is either "yes, 71 seconds, three sources opened, here is the
note" or "no, it came through in a batch of twenty on 3 September". Both are useful; only the second
is a lesson.

### 4.7.7 The speed tradeoff, honestly

Per-business cost at each profile, with the dwell being a floor rather than an estimate of real
reading time:

| Profile | `dwell_base_ms` | `dwell_per_check_ms` | Required source visits | Floor per business | Realistic per business | 200-business campaign |
|---|---|---|---|---|---|---|
| Off | 0 | 0 | 0 | ~4 s | ~10 s | ~35 min |
| Light | 10 000 | 1 000 | 1 | 19 s | ~35 s | ~2 h |
| **Recommended** | **20 000** | **3 000** | **3** | **47 s** | **75–90 s** | **~4.5 h** |
| Strict | 45 000 | 6 000 | all | 99 s | ~150 s | ~8 h |

The honest reading of this table: **the recommended profile costs about four and a half hours per
200-business campaign, and the "off" profile costs thirty-five minutes.** That is a real difference
and it is not worth pretending otherwise. Three things make the four and a half hours the better
trade:

1. It is not four and a half hours of *new* work. Reading the research is the work; the dwell floor
   is below the time a genuine read takes, so it binds only on rows being clicked through.
2. The output is not 200 messages. After rejections, skips and eligibility, a 200-business campaign
   produces a few dozen contacts. The verification cost per *message actually sent* is closer to
   fifteen minutes, which is cheap for something Sagar has to defend to a stranger.
3. The queue does not have to be finished. Which leads to the actual recommendation.

### 4.7.8 Recommended settings

```yaml
# config.yaml
verify:
  dwell_base_ms: 20000              # ~20 s floor before APPROVE enables
  dwell_per_check_ms: 3000          # + 3 s per in-scope check; 47 s for a full nine
  source_visit_required_top_n: 3    # the three highest-weight cited sources
  waiver_alert_pct: 40              # Telegram note above this waiver rate over 30 days
  why_note_min_chars: 15
  draft_ttl_hours: 72
  queue_daily_target: 30            # a soft banner, never a block
  session_reminder_after: 25        # "you have verified 25 in a row - take a break" banner
  bulk_max_rows: 25
  bulk_requires_filter: true
  min_research_confidence: MEDIUM
  min_research_confidence_pct: 50
  refresh_batch_max: 500
```

**Run the recommended profile.** The two settings that matter most are not the dwell numbers:

- `queue_daily_target: 30`. The pressure that produces rubber-stamping is a queue of 200 and a wish
  to be finished. A soft daily target, shown as "30 of 30 today — the rest will keep", removes the
  wish. It never blocks anything.
- `session_reminder_after: 25`. Attention degrades measurably through a session, and the queue is
  ordered by score descending (§4.5.4) precisely so that degradation lands on the least valuable
  rows. The banner is the cheapest intervention in this document.

Loosen to `Light` only for a campaign of known-shape businesses in a city already worked — where the
research is mostly confirmatory. Do not loosen for a new city, a new industry, or the first campaign
after a change to the research prompt, which are the three situations where the research is most
likely to be confidently wrong.

### 4.7.9 Deliberately rejected measures

| Rejected | Why |
|---|---|
| A confirmation dialog on approve | Trained away in a week. It produces no artefact, and its only effect is one extra click on every row, including the considered ones |
| Retyping the business name to confirm | Costs attention, proves the name is on screen and nothing else. This is the anti-pattern the other measures are designed to avoid |
| A comprehension quiz generated from the findings | An LLM call on the checking screen, grading a human on the machine's own output. It inverts the relationship the gate exists to establish |
| Randomly re-showing an already-verified business | Wastes time on rows that are already decided and teaches Sagar that the queue lies about what is left |
| A hard daily cap | Blocks a legitimate afternoon of focused work. `queue_daily_target` is a banner for exactly this reason |
| Requiring a note on every check | Nine notes per business is a transcription exercise. Notes are required where they carry information: on a failure, and once on approval |

---

## 4.8 Bulk verification

### 4.8.1 What may be applied in bulk, and what may not

The dividing line is not "how many rows" or "how confident is Sagar". It is: **does the action create
a record that authorises contact, or a record that cannot be undone?**

| Action | Bulk? | Why |
|---|---|---|
| `REJECT` with a `bulk_ok = 1` reason (`WRONG_CATEGORY`, `WRONG_CITY`, `NOT_A_BUSINESS`, `DUPLICATE_OF_EXISTING`) | **yes** | Clerical facts, verifiable from the grid columns alone. A whole page of veterinary clinics returned by a search for "hospital" is one judgement applied to twenty rows, and forcing twenty screens teaches nothing |
| `SKIP` | **yes** | Parks without judging. Fully reversible, writes no verdict, requires no reason (§4.2.5) |
| `UNSKIP` | **yes** | Same, in reverse |
| Re-queue for research | **yes** | Enqueues jobs; changes no verdict |
| `REJECT` with a permanent reason (`SENSITIVE_SECTOR`, `COMPETITOR_OR_CONFLICT`, `DO_NOT_CONTACT_RECORD`, `PRIOR_COMPLAINT`) | **no** | Writes a `suppressions` row the application can never clear. An irreversible act applied to a list is an irreversible act applied to the row somebody misread |
| `REJECT` with an evidence-based reason (`CLOSED_OR_DEFUNCT`, `ALREADY_HAS_SOFTWARE`, `OPPORTUNITY_NOT_CREDIBLE`, `OUTREACH_INAPPROPRIATE`, …) | **no** | The claim is about a specific business's specific evidence. There is no filter that establishes "closed" for twenty rows at once |
| `VERIFIED` | **never** | §16, §19, §45. Nine checks are nine statements about one business. There is no filter that can establish "the contact information appears to be a legitimate business contact" for a set |

`VERIFIED` is absent from the bulk path at four layers — no control, an endpoint that refuses the
verdict before parsing the rows, a `CHECK` constraint on `verifications`, and trigger (2) in §4.2.7
which requires a per-business checklist that a bulk write does not produce. §4.7.4 lists them.

### 4.8.2 The bulk endpoint

```http
POST /api/v1/verifications/bulk
Content-Type: application/json
X-CSRF-Token: <session csrf>

{
  "action": "REJECT",
  "campaign_id": "cmp_01JSAMPLE0000000000000001",
  "filter": {"city": "Dhule", "category": "OTHER", "query": "veterinary"},
  "business_ids": ["biz_01JSAMPLE...A1", "biz_01JSAMPLE...A2", "biz_01JSAMPLE...A3"],
  "reason_code": "WRONG_CATEGORY",
  "note": "SAMPLE — veterinary clinics returned by the hospital search; out of scope for this campaign.",
  "expected_count": 3
}
```

| Rule | Value | Reason |
|---|---|---|
| Verdict allowed | `REJECT`, `SKIP`, `UNSKIP`, `REQUEUE_RESEARCH` | `VERIFY` returns 400 `BULK_VERIFY_FORBIDDEN` |
| Reason must satisfy | `verification_reason_codes.bulk_ok = 1` | else 400 `REASON_NOT_BULK_APPLIABLE` |
| Max rows | `verify.bulk_max_rows`, default 25 | else 400 `BULK_TOO_LARGE`. Twenty-five is roughly one screen of grid: a set you can actually look at |
| Filter required | `verify.bulk_requires_filter` | The batch must correspond to something visible on screen, not an accumulated multi-page selection |
| `expected_count` | Must equal `len(business_ids)` | Optimistic concurrency against a grid that moved under the click |
| Note | ≥ 20 characters, one per batch | The batch is one judgement, so it gets one justification |
| Rows already decided | Skipped, reported in `rejected[]` | A bulk action never overwrites an existing verdict |
| Transaction | One `BEGIN IMMEDIATE` for the whole batch | Partial application would leave a batch that no audit row describes |

```json
{
  "batch_id": "vbat_01JSAMPLE00000000000B1",
  "applied": 3,
  "skipped": 0,
  "results": [
    {"business_id": "biz_01JSAMPLE...A1", "status": "REJECTED",
     "verification_id": "ver_01JSAMPLE...B1"}
  ],
  "rejected": []
}
```

Each row gets its own `verifications` row with `mode='BULK'`, `bulk_batch_id`, `bulk_size`, and its
nine `verification_checks` rows: the check named by the reason code's `applies_to_check` is written
`passed = 0` with the batch note, and the other eight stay `NULL`. That shape is deliberate — the
rejection is honest about having answered exactly one question, and `checks_passed = 0` means no
query anywhere can mistake it for a verification.

### 4.8.3 Carry-forward: the one pre-fill, and why it is not bulk verification

The case §4.2.6's last-but-one row and §4.9's staleness sweep both produce: a business back in
`NEEDS_VERIFICATION` whose most recent superseded verification said `VERIFIED`, inside the freshness
window, with an **identical research fingerprint**. It happens on a rediscovery under a campaign
with a shorter `verification_valid_days`, and it happens whenever a trigger fires on one dimension
and nothing else moved. Re-answering nine questions whose evidence has not changed by one byte is
the purest form of busywork, and busywork is what produces rubber stamps.

Carry-forward handles it without becoming a bulk verify:

| Property | Rule |
|---|---|
| Eligibility | The most recent prior verification of **this business**, `verdict='VERIFIED'`, `verified_at` inside `verification_valid_days`, and `research_fingerprint`, `contact_fingerprint` and `website_hash` all equal to the business's current values (§4.9.6). Live or superseded — a superseded one is the normal case, because the demotion is what put the business back in the queue |
| What carries | The nine `verification_checks` answers and their notes, each with `carried_from` set to the source verification id |
| What does not carry | `why_note` — Sagar writes a new one. `dwell_ms` — the clock runs again, at the `RECHECK` rate |
| Required action | **One explicit approve, on the screen, per business.** Carry-forward is a pre-fill, not a decision |
| Banner | E14 renders "Nine checks carried from your verification of 12 Aug 2026 on the Dhule campaign — the research has not changed since. Untick anything you disagree with." |
| `verified_at` | **Inherited from the source verification, not stamped fresh** |
| Mode | `CARRY_FORWARD` (an amendment request against `01` §1.8.1's `mode` CHECK — see "Open questions"); audit action `VERIFICATION_CARRIED_FORWARD` |
| Availability | Only from the verification screen. There is no bulk carry-forward endpoint |

The inherited `verified_at` is the rule that makes this safe. Without it, carry-forward launders a
29-day-old verification into a fresh one, and a chain of three campaigns produces a signature that
is permanently young and increasingly wrong. With it, a carried verification expires on the
original's schedule, and the third campaign gets a real re-verification whether or not anybody
noticed.

This is why "no bulk verify" and "carry-forward exists" are not in tension: the count of human
decisions is unchanged. Carry-forward reduces the *work per decision* when the evidence is provably
identical. It never reduces the *number of decisions*.

---

## 4.9 Re-verification and staleness

### 4.9.1 The window

A verification is a statement about a business **as it was on one day**. "Appears operational",
"contact information appears to be a legitimate business contact" and "no do-not-contact record
exists" all decay, and they decay at the speed of the world, not at the speed of the database.

| Setting | Value | Source of truth |
|---|---|---|
| `verification_valid_days` | 30 | `contact_policy.verification_valid_days` (`05-outreach-workflow.md` §5.3.1), merged by `effective_policy()` |
| Amber "expiring" band | age ≥ 75% of the window | Derived, no column. The grid and `/verify` show "expires in 6 days" |
| Hard expiry | age > window | C1 fails; gate D3 blocks; the sweep demotes |

**There is exactly one number.** `14-background-jobs.md` §14.8.20 currently names a separate
`verify.ttl_days` default 45 for its verification-staleness pass; two windows means fifteen days in
which gate D3 blocks a business the sweep still believes is fine — the exact "blocked at report
time" behaviour §4.9.4 exists to prevent. The sweep must read `effective_policy().verification_valid_days`.
Listed in "Open questions".

### 4.9.2 The triggers

Age is one of nine reasons a verification stops being true. Every trigger below supersedes the live
verification and creates a `NEEDS_VERIFICATION` queue item carrying `trigger_reason` and a
`recheck_scope` (§4.9.3).

| # | Trigger | Detection | `superseded_reason` | Recheck scope |
|---|---|---|---|---|
| R1 | Research older than the window | `verified_at < now - verification_valid_days` | `STALE` | **all nine** |
| R2 | Contact changed | `businesses.contact_fingerprint <> verifications.contact_fingerprint` | `CONTACT_CHANGED` | 5 |
| R3 | Website changed materially | `businesses.website_hash <> verifications.website_hash` | `WEBSITE_CHANGED` | 1, 3, 4, 6, 7 |
| R4 | Website went dark | `businesses.website_status` moves to `DEAD` on two consecutive probes | `WEBSITE_DARK` | 1, 4 |
| R5 | Research re-ran and changed | `businesses.research_fingerprint <> verifications.research_fingerprint` after a `research_business` job | `RESEARCH_CHANGED` | 4, 6, 7, 8 |
| R6 | A previous hard bounce | A `suppressions` row `reason='BOUNCE_HARD'` matching one of this business's contacts | `HARD_BOUNCE` | 5 |
| R7 | A category correction | `businesses.category` or `.industry` changed since `verified_at` | `CATEGORY_CORRECTED` | 3, 7, 8 |
| R8 | A `WRONG_CONTACT` response | `responses.classification = 'WRONG_CONTACT'` | `WRONG_CONTACT_REPORTED` | 5 |
| R9 | Manual revocation | T11 / T16, Sagar's own action | `MANUAL` | all nine |

Two events that look like triggers and are **not**:

- **A suppression appearing.** That is C4, and it demotes `CONTACT_READY -> VERIFIED` without
  touching the signature (§4.3.5). Sagar's answer to "no do-not-contact record existed on 27 August"
  was correct then and is still correct; there is nothing to re-check.
- **A policy change (`min_research_confidence` raised, a channel disabled).** That re-evaluates the
  predicate for every affected business (P8), which may demote, but it does not invalidate any
  human judgement. `superseded_reason = 'POLICY_CHANGED'` exists for the one case where a policy
  change *shortens the window* and businesses fall out of R1 as a result.

R2, R3, R5 and R7 fire from the code that makes the change, in the same transaction. R1, R4 and R6
are found by the sweep. R8 fires from `radar/classify.py`. R9 is an endpoint.

### 4.9.3 Targeted recheck scope

A trigger that invalidates one check should not cost nine. `verifications.recheck_scope` is a JSON
array of `check_key` values; `NULL` means all nine.

| Behaviour | Rule |
|---|---|
| In-scope checks | Rendered unanswered, must be answered fresh, their evidence zone is expanded and highlighted |
| Out-of-scope checks | Rendered answered, `carried_from` set to the superseded verification, with "carried from 12 Aug" beside each |
| Dwell | `dwell_required_ms` is computed from the in-scope count only (§4.7.3) |
| Sources | Only sources cited by findings behind an in-scope check are marked `is_required` |
| Mode | `RECHECK` (`01` §1.8.1's value for a targeted re-answer); `carried_check_keys[]` recorded in the audit detail |
| Banner E37 | "Re-verification: this business's contact details changed on 3 Sep. Check 5 needs a fresh answer; the other eight are carried forward." |
| Escape hatch | `[Re-check everything]` clears the carry-forward and turns it into a `FULL` verification |

The risk is obvious and worth naming: a targeted recheck is a pre-filled checklist, which is exactly
what §4.7 argues against. Three things keep it defensible — the carry-forward is *labelled per check*
rather than silent, its source verification is a real row an audit can open, and the scope is
computed from the trigger rather than chosen by the person doing the checking. A `FULL`
re-verification after R1 carries nothing at all, because age invalidates every answer equally.

### 4.9.4 Demote before outreach, not at report time

The failure mode this rule exists to prevent, concretely: a business verified on 1 August sits
`CONTACT_READY` through September. On 4 September Sagar selects it, waits for a draft, reads the
preview, and *then* gets "your verification of this business is 34 days old". He has spent five
minutes and a Gemini request out of the day's free-tier quota to be told something the system knew
on 31 August. Repeat that four times in a session and the eligibility panel becomes noise.

| Approach | When Sagar finds out | Cost of a stale verification |
|---|---|---|
| Block at send time only | After selecting, drafting, previewing | Wasted attention, a wasted LLM call, a cancelled draft |
| Grey out in the grid | On the grid, before selecting | Better, but the grid then needs its own freshness logic |
| **Demote the state** | Immediately: the business is in the verification queue, not the selectable set | The business reappears where the work actually is |

So a stale verification is not a flag on a `CONTACT_READY` business; it makes the business
`NEEDS_VERIFICATION` again, with a targeted scope, in the queue, ordered by score. The demotion
happens at the moment of staleness (a trigger firing) or within 24 hours (the sweep), and gate D3
remains as the backstop for the window between a business going stale at 09:00 and the sweep running
at 01:00 the following night.

### 4.9.5 The sweep

`staleness_sweep` is defined by `14-background-jobs.md` §14.8.20 — five passes, `maint` lane, 01:00
IST, priority 100, 900 s lease, 3 retries, `REQUEUE` on failure, dedupe key
`staleness_sweep:{slot_iso}`. That contract stands unchanged. This document specifies only what its
**verification pass** does, because that pass calls into `radar/verify.py`:

```python
# radar/verify.py — called by the staleness_sweep handler, never by the web app

@dataclass(frozen=True)
class SweepResult:
    scanned: int
    reverify_queued: int          # R1/R4/R6 demotions to NEEDS_VERIFICATION
    promoted: int                 # VERIFIED -> CONTACT_READY, predicate now holds
    demoted: int                  # CONTACT_READY -> VERIFIED, a clause broke
    drafts_abandoned: int
    capped: bool                  # True if a cap stopped the pass short


def sweep_verification_staleness(conn: sqlite3.Connection, *, limit: int,
                                 now: str | None = None) -> SweepResult:
    """The verification pass of staleness_sweep (14-background-jobs.md §14.8.20).

    Four things, in one pass, each in its own transaction so a cap or a crash leaves a
    consistent prefix of the work done:

      1. R1/R4/R6 detection -> supersede the verification, demote to NEEDS_VERIFICATION with a
         recheck scope, write REVERIFY_TRIGGERED and VERIFICATION_EXPIRED.
      2. Every VERIFIED business whose predicate now holds -> promote (T09). This is the pass
         that recovers a business whose frequency window closed in July and reopened in August.
      3. Every CONTACT_READY business whose predicate no longer holds -> demote (T14/T15).
      4. Drafts idle beyond verify.draft_ttl_hours -> ABANDONED.

    Respects sweep.max_reverify_per_night (default 50) for step 1 only; steps 2-4 are cheap
    status writes over an indexed view and are not capped. Never verifies anything: the sweep
    is a SYSTEM actor and trigger (2) in §4.2.7 would abort it if it tried.
    """
```

The scan is one pass over `v_contact_ready_business` joined to `verifications`. It reads the
collapsed view, not `v_contact_ready`, because the sweep decides `businesses.status` and that is one
row per business (§4.3.3):

```sql
-- radar/verify.py :: SWEEP_SCAN_SQL      params: :limit
SELECT cr.business_id, cr.ready_campaign_id, cr.status, cr.verification_id, cr.verified_at,
       cr.c1_verified_fresh, cr.c2_not_judged, cr.c3_contact_usable, cr.c4_no_suppression,
       cr.c5_frequency_open, cr.c6_research_usable, cr.c7_confidence_adequate,
       b.website_status, b.contact_fingerprint, b.research_fingerprint, b.website_hash,
       v.contact_fingerprint AS ver_contact_fp,
       v.research_fingerprint AS ver_research_fp,
       v.website_hash         AS ver_website_hash
  FROM v_contact_ready_business cr
  JOIN businesses b     ON b.id = cr.business_id
  LEFT JOIN verifications v ON v.id = cr.verification_id
 WHERE cr.status IN ('VERIFIED','CONTACT_READY')
 ORDER BY cr.verified_at
 LIMIT :limit;
```

A `VERIFIED` business that has dropped out of every campaign produces no row in either view and is
therefore never re-promoted by the sweep. It is also never demoted by it, which is correct: nothing
about the world changed, only its membership, and C2 keeps it out of the selectable pool anyway.

Ordering by `verified_at` ascending means a cap always takes the stalest rows first, so a backlog
drains from the wrong end rather than starving.

### 4.9.6 Fingerprints

Three hashes decide whether "something changed" is a real change or a whitespace edit. Each is stored
on `businesses` (§4.2.7 added the columns) and copied onto `verifications` at submit, so a comparison
is a string equality rather than a diff.

```python
# radar/verify.py

def research_fingerprint(conn: sqlite3.Connection, business_id: str) -> str:
    """sha256 over the current research run's citable content, canonically ordered.

    Input: for the latest COMPLETE research_runs row, each finding's (kind, dimension, statement,
    confidence, confidence_pct) plus its sorted source ids, then the current opportunity's
    (score, band, confidence, potential_problem, potential_solution, module list). Serialised
    with canonical_json() from 11-audit-architecture.md so the ordering is not the caller's
    problem.

    Deliberately excludes ids, timestamps, model_id and prompt_version: a re-run of the same
    prompt that produces the same findings must not look like a change, or every nightly
    re-research would invalidate every verification in the database.
    """

def contact_fingerprint(conn: sqlite3.Connection, business_id: str) -> str:
    """sha256 over the sorted (kind, value_norm, human_verified, is_active) of every contact.

    value_norm, not value_display: re-typing 'Info@ABC.in' as 'info@abc.in' is not a change, and
    treating it as one sends a business back to the queue for a capitalisation edit.
    """

def website_hash(html: bytes) -> str:
    """sha256 over the normalised text of the site's landing page and contact page.

    Script and style elements dropped, whitespace collapsed, tags stripped, comments removed.
    A rotating banner, a session id in a URL and a copyright year must not read as a change; a
    new phone number, a closure notice or a different business name must.
    """
```

`research_fingerprint()` excluding `model_id` and `prompt_version` is a decision with a visible
consequence: a prompt change that produces identical findings will not trigger re-verification.
That is intended. What is being verified is the *content*, and the content is unchanged. A prompt
change that produces *different* findings changes the fingerprint and triggers R5, which is the case
that matters.

---

## 4.10 §19 and §45 at three layers

### 4.10.1 Why one layer is not enough

Spec §19: *"The 'Send' button must NOT exist on the raw AI research result."* Spec §45: *"NEVER: AI
finds business -> automatically sends message."* Both are usually implemented as a UI decision, and
a UI decision is the weakest of the three available layers.

Each layer catches a class of failure the other two cannot. The table is the argument:

| Layer | Catches | Cannot catch | The concrete failure it is there for |
|---|---|---|---|
| **UI** — the control does not exist | Sagar's own hand. Muscle memory, a mis-click, "I'll just fire this one off from the grid while I'm here" | Anything not going through a template: the API, a job, a script, a second client | It is 23:40, the grid is open, a business looks obviously good, and there is a button. The absence of the button is the only thing operating at that moment |
| **API** — the endpoint rejects | A stale browser tab replaying a form. A bookmarked URL. An export deep-link with a hand-edited query string. A `curl` from Sagar's own shell. A future mobile client written against a half-remembered API | A writer that never speaks HTTP: the worker thread, a migration, a REPL | Six weeks from now the report export gains a "quick send" link because it seemed useful; the endpoint it points at refuses, and the mistake is a 409 instead of a message |
| **DB** — the trigger aborts | Everything that reaches the database, including code that did not exist when the UI and API were written | Nothing in scope. It cannot produce a good error message on its own, which is why `set_status()` exists | A 01:00 debugging session: `sqlite3 data/radar.db` and `UPDATE businesses SET status='CONTACTED' WHERE …` to "fix" a stuck row. The trigger aborts. Without it, an `outreach_messages` row is now missing for a business the system believes was contacted, and §48's audit record has a hole nobody will ever explain |

There is a fourth reason, which is about people rather than machines: **a layer that only exists at
the bottom teaches the wrong lesson.** If the DB triggers were the only enforcement, the UI would
show a Send button that always errors, and within a week the errors are noise. If the UI were the
only enforcement, the invariant would be a styling decision that survives exactly until the next
template refactor. The three layers together mean the rule is visible where the work happens,
explained where the integration happens, and true where the data lives.

### 4.10.2 Layer 1 — UI

| Surface | Present | Absent, and tested |
|---|---|---|
| `/verify/<id>` | approve, reject, skip, save-draft, contact confirm, source links | any send control; any bulk approve; any link to `/outreach/<draft_id>` for a business that is not `CONTACT_READY` |
| `/campaigns/<id>` grid | VIEW, RESEARCH, VERIFY, REJECT, SELECT, HISTORY (`05-outreach-workflow.md` §5.4.5) | any control that transmits |
| Exported HTML report | deep links only, `<a href>` only (`03-html-report.md` §3.1.2) | `<form>`, `fetch`, any POST target, SEND in either mode |
| Verification queue | next / previous / filter | row checkboxes with an approve action |

The tests that keep it true:

```python
def test_no_send_control_in_verification_templates():
    """§19 as a grep. templates/verify/**.html must contain no send affordance.

    Fails on: 'send', 'dispatch', 'transmit', 'wa.me', 'mailto:' in an href or a button label,
    and on any <form> whose action resolves to a route outside /api/v1/verifications/*.
    """

def test_no_bulk_verify_control():
    """No template renders a multi-row approve. §4.7.4."""

def test_verify_screen_has_no_outreach_link_for_unready_business(client, fixtures):
    """A NEEDS_VERIFICATION business's screen contains no /outreach/ link at all."""
```

### 4.10.3 Layer 2 — API

Every route this document owns is listed in §4.12.1, and **none of them transmit anything**. The
enforcement is four rules:

| Rule | Implementation |
|---|---|
| No verification endpoint reaches the transmit path | `05-outreach-workflow.md` §5.4.5's `test_no_endpoint_sends_from_a_business_id` walks the Flask `url_map`; every rule under `/api/v1/verifications` and `/api/v1/businesses/<business_id>` is asserted not to reach `radar.outreach.send_message` in its call graph |
| The state machine answers before the write | Step 3 of §4.6.4's ladder checks `business_status_transitions` in Python and returns 409 `ILLEGAL_TRANSITION` naming the T-number. The trigger is the enforcement; this is the readable error |
| `VERIFIED` is only writable by a session | `POST /api/v1/verifications/<id>/submit` requires a session, CSRF and the `verify` permission. There is no API-key path to it, no job path, and no CLI subcommand in `main.py` that writes a verdict |
| Bulk refuses the verdict before parsing | `POST /api/v1/verifications/bulk` checks `action != 'VERIFY'` as its first statement (§4.8.2) |

`main.py` deserves an explicit line, because a CLI is the classic hole. The argparse subcommands are
`discover`, `research`, `score`, `report`, `export`, `sweep`, `serve`, `migrate`, `audit-verify`.
There is no `verify` subcommand and no `send` subcommand. Verification is a human act performed in a
session; a command-line verifier would be an unattended one by definition.

### 4.10.4 Layer 3 — DB

§4.2.7 already defines the four triggers on `businesses`: the transition-table check, the
`VERIFIED`-needs-a-human-checklist check (invariant V1), the `CONTACTED`-only-from-`CONTACT_READY`
check (invariant V2), and the provenance stamp. §4.4.1 and §4.4.2 add immutability on submitted
verifications and their checks. One trigger pair remains — invariant **V3**, which is the storage
layer's answer to §19: *a business that has never reached `CONTACT_READY` cannot have an outreach
object at all.*

```sql
-- radar/migrations/058_no_draft_before_contact_ready.sql
--
-- Invariant V3. §19 says the Send button must not exist on a raw research result. This is the
-- same rule one level down: the object the button would need cannot be stored. A draft may only
-- exist for a business that has passed the human gate - CONTACT_READY for a first touch, or
-- CONTACTED / RESPONDED for a follow-up, both of which are reachable only through CONTACT_READY
-- (invariant V2 and the transition table).
CREATE TRIGGER trg_no_draft_before_contact_ready
BEFORE INSERT ON outreach_drafts
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM businesses b
                  WHERE b.id = NEW.business_id
                    AND b.status IN ('CONTACT_READY','CONTACTED','RESPONDED'))
BEGIN
    SELECT RAISE(ABORT,
      'no outreach draft may exist for a business that has not passed verification (spec 19, 45)');
END;

CREATE TRIGGER trg_no_message_before_contact_ready
BEFORE INSERT ON outreach_messages
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM businesses b
                  WHERE b.id = NEW.business_id
                    AND b.status IN ('CONTACT_READY','CONTACTED','RESPONDED'))
BEGIN
    SELECT RAISE(ABORT,
      'no outreach message may exist for a business that has not passed verification (spec 19, 45)');
END;

-- The same rule for selections, one step earlier in the pipeline, so §18's "only VERIFIED and
-- CONTACT_READY can be selected" is storage-enforced too.
CREATE TRIGGER trg_no_selection_before_contact_ready
BEFORE INSERT ON selections
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM businesses b
                  WHERE b.id = NEW.business_id
                    AND b.status IN ('CONTACT_READY','CONTACTED','RESPONDED'))
BEGIN
    SELECT RAISE(ABORT, 'only CONTACT_READY businesses may be selected (spec 18)');
END;
```

These read the *current* status rather than a historical flag deliberately. A business demoted by
T14 or T15 loses the right to acquire **new** outreach objects immediately, which is the behaviour
§4.9.4 wants: demote first, so the next step cannot start.

Together with §4.2.7 the full DB layer is:

| Trigger | Invariant | Section |
|---|---|---|
| `trg_biz_status_transition` | only declared transitions, by the declared actor kind | §4.2.7 |
| `trg_biz_verified_needs_human_checklist` | V1 — `VERIFIED` is a human signature over nine passed checks | §4.2.7 |
| `trg_biz_contacted_only_from_ready` | V2 — `CONTACTED` only from `CONTACT_READY` | §4.2.7 |
| `trg_biz_status_touch` | provenance stamp | §4.2.7 |
| `trg_verifications_immutable` / `_no_delete` | a submitted verification is evidence | §4.4.1 |
| `verification_checks`'s `CHECK (passed <> 0 OR note >= 10 chars)` | a "no" carries its reason | `01-data-model.md` §1.8.2 |
| `trg_verification_checks_immutable` | answers freeze on submit | §4.4.2 |
| `trg_no_draft_before_contact_ready` and its two siblings | V3 — no outreach object before the gate | here |
| `trg_om_send_needs_approval` | invariant 1 — `SENT` needs a live matching approval | `05-outreach-workflow.md` §5.3.8 |

### 4.10.5 The tests that hold the three layers together

| # | Test | Asserts |
|---|---|---|
| L1 | `test_system_actor_cannot_write_verified` | `set_status(..., 'VERIFIED', actor_kind='SYSTEM')` raises; a raw `UPDATE` with `status_actor_kind='SYSTEM'` aborts at the trigger |
| L2 | `test_verified_requires_nine_passed_checks` | Eight passed and one `NULL` aborts; nine passed on a *superseded* verification aborts; nine passed with `verdict='REJECTED'` aborts |
| L3 | `test_contacted_only_from_contact_ready` | Every one of the other nine states raises on `-> CONTACTED` |
| L4 | `test_no_draft_for_unverified_business` | Inserting `outreach_drafts`, `outreach_messages` and `selections` rows for an `AI_RESEARCHED`, `NEEDS_VERIFICATION`, `VERIFIED`, `REJECTED` and `SKIPPED` business all abort |
| L5 | `test_no_endpoint_under_verifications_transmits` | The `url_map` walk, restricted to this document's routes |
| L6 | `test_no_send_control_in_verification_templates` | §4.10.2 |
| L7 | `test_cli_has_no_verify_or_send_subcommand` | `main.py`'s argparse tree |

---

## 4.11 Audit

`11-audit-architecture.md` owns `audit_log`, the `audit_actions` catalogue and `audit.write()`. This
section states which actions this document emits, which of them already exist, which must be added,
and what `detail_json` each one carries.

### 4.11.1 Action codes

**There is no shorthand.** `audit_log.action` is `TEXT NOT NULL REFERENCES audit_actions(action)`
(`11-audit-architecture.md` §11.6), so an action name that is not in the catalogue does not degrade
to a mislabelled row — it aborts the transaction it was written in, which for T06 is the same
transaction as the status change. §4.2.3's "Audit written" column therefore names catalogue actions
verbatim, and this table records which of them exist today and which this document asks
`11-audit-architecture.md` to add:

| Action written by this document | Status |
|---|---|
| `BUSINESS_STATUS_CHANGED` | exists (§11.6.1). **Not** `BUSINESS_STATUS_CHANGE`, which is in no catalogue and would fail the foreign key |
| `BUSINESS_VERIFIED` | exists (§11.6.2). This is the approve action; there is no `VERIFICATION_SUBMITTED` |
| `BUSINESS_REJECTED` | exists (§11.6.2) |
| `BUSINESS_SKIPPED` | exists (§11.6.2) |
| `VERIFICATION_SUPERSEDED` | **new** |
| `CONTACT_READY_GRANTED` | **new** |
| `CONTACT_READY_REVOKED` | **new** |
| `REVERIFY_TRIGGERED` | **new** |
| `VERIFICATION_REOPENED` | **new** |
| `REDISCOVERY_RESOLVED` | **new** |

Reused unchanged: `VERIFICATION_OPENED`, `VERIFICATION_SAVED`, `VERIFICATION_EXPIRED`,
`VERIFICATION_REVOKED`, `VERIFICATION_ABANDONED` (`13-api-endpoints.md` §13.16 C14 asks for it),
`SUPPRESSION_CREATED`, `SELECTION_REMOVED`.

`D_VERIFICATION_STALE` and `D_VERIFICATION_REVOKED` (§4.3.2, `05-outreach-workflow.md` §5.9.1) are
**gate decline codes, not audit actions**. They never reach `audit_log.action`; they appear as
`blocking_code` inside a `detail_json` payload. No catalogue row is needed for either.

Rows to add to `11-audit-architecture.md`'s catalogue seed,
`radar/migrations/033_audit_actions_seed.sql` (`01-data-model.md` §1.13.2 assigns that number and
`11` owns the file — this document contributes the rows and creates no seed file of its own), in
that file's column order
(`action, domain, severity, sidecar_ret, user_visible, pii_class, best_effort, description`):

```sql
INSERT INTO audit_actions
 (action, domain, severity, sidecar_ret, user_visible, pii_class, best_effort, description) VALUES
 ('VERIFICATION_SUPERSEDED','VERIFICATION','NOTICE','NONE',1,'NONE',0,
  'A live verification was replaced or invalidated; superseded_reason says by what.'),
 ('VERIFICATION_ABANDONED','VERIFICATION','INFO','NONE',0,'NONE',1,
  'A draft verification expired unfinished.'),
 ('VERIFICATION_REOPENED','VERIFICATION','CRITICAL','NONE',1,'NONE',0,
  'A non-permanent rejection was reopened; the business re-entered the verification queue.'),
 ('VERIFICATION_BULK_APPLIED','VERIFICATION','CRITICAL','NONE',1,'NONE',0,
  'One judgement applied to several businesses at once. Never a VERIFIED verdict.'),
 ('VERIFICATION_CARRIED_FORWARD','VERIFICATION','NOTICE','NONE',1,'NONE',0,
  'Checklist answers pre-filled from an identical prior verification; verified_at inherited.'),
 ('VERIFICATION_SOURCE_WAIVED','VERIFICATION','NOTICE','NONE',0,'NONE',0,
  'A required source was skipped with a written reason instead of being opened.'),
 ('CONTACT_READY_GRANTED','VERIFICATION','NOTICE','NONE',1,'NONE',0,
  'The seven-clause predicate held and the business entered the selectable pool.'),
 ('CONTACT_READY_REVOKED','VERIFICATION','NOTICE','NONE',1,'NONE',0,
  'A predicate clause broke and the business left the selectable pool.'),
 ('REVERIFY_TRIGGERED','VERIFICATION','NOTICE','NONE',1,'NONE',0,
  'A staleness trigger fired; the business went back to NEEDS_VERIFICATION with a scope.'),
 ('REDISCOVERY_RESOLVED','RESEARCH','NOTICE','NONE',0,'NONE',0,
  'A rediscovered business was matched to its own prior verdict; the membership row records the outcome.');
```

`C_CONFIDENCE_LOW` is deliberately **not** in that list. It is a policy gate code belonging to
`05-outreach-workflow.md` §5.9.1's catalogue, not an audit action; it reaches `audit_log` only as a
`blocking_code` inside a `CONTACT_READY_REVOKED` payload. See "Open questions".

Two catalogue notes that need amending in `11-audit-architecture.md`, both listed in "Open
questions":

- `VERIFICATION_EXPIRED`'s description says the business *"drops out of eligibility on its own"*.
  Under §4.9.4 it does not drop out; it is actively demoted to `NEEDS_VERIFICATION` by the sweep.
- `BUSINESS_SKIPPED`'s `detail_json` names `reason_code` values `OUT_OF_SCOPE` / `BELOW_SCORE` /
  `NO_CONTACT` / `DUPLICATE`. This document's `businesses.skip_reason` enum (§4.2.7) is
  `BELOW_MIN_SCORE` / `SIZE_FILTER` / `CITY_FILTER` / `INDUSTRY_FILTER` / `RESEARCH_FAILED` /
  `MANUAL` / `PRIOR_PERMANENT_REJECTION`. The column is the source of truth; the catalogue note
  should name those seven.

### 4.11.2 What each event writes

Every row below is written inside the same transaction as the change it describes, per
`audit.write()`'s contract. `business_id` is always set. `audit_log.campaign_id` is the campaign the
action happened under when there is one — a queue verification, a bulk apply — and
`businesses.first_seen_campaign_id` otherwise, per `01-data-model.md` §1.2.2: a revocation from
`/business/<id>`, a sweep demotion and a merge all happen outside a campaign. `entity_table` /
`entity_id` point at the row that changed.

| Event | Action(s), in order | `entity_table` | `detail_json` keys |
|---|---|---|---|
| Screen opened | `VERIFICATION_OPENED` | `verifications` | `business_id`, `research_run_id`, `entry_point`, `mode`, `dwell_required_ms`, `recheck_scope[]`, `from_export` |
| Draft saved | `VERIFICATION_SAVED` (≤ 1 per 60 s) | `verifications` | `checks_passed`, `checks_total`, `elapsed_s` |
| Source waived | `VERIFICATION_SOURCE_WAIVED` | `verification_sources` | `source_id`, `source_url`, `waive_reason`, `rank` |
| Approved | `BUSINESS_VERIFIED`, then `BUSINESS_STATUS_CHANGED`, then `CONTACT_READY_GRANTED` + a second `BUSINESS_STATUS_CHANGED` if the predicate holds | `businesses` | see below |
| Rejected | `BUSINESS_REJECTED`, `VERIFICATION_SUPERSEDED` (if one was live), `SUPPRESSION_CREATED` (if permanent), `SELECTION_REMOVED` (per selection), `BUSINESS_STATUS_CHANGED` | `businesses` | `verification_id`, `reason_code`, `reason_note`, `checklist{}`, `is_permanent`, `cool_off_days`, `suppression_id` |
| Skipped | `BUSINESS_SKIPPED`, `BUSINESS_STATUS_CHANGED` | `businesses` | `skip_reason`, `draft_verification_id` |
| Bulk applied | `VERIFICATION_BULK_APPLIED` once, then the per-row actions above | `campaigns` for the batch row | `batch_id`, `action`, `reason_code`, `note`, `filter{}`, `bulk_size`, `business_ids[]` |
| Carry-forward | `VERIFICATION_CARRIED_FORWARD`, then `BUSINESS_VERIFIED` | `verifications` | `carried_from_verification_id`, `carried_check_keys[]`, `inherited_verified_at`, `fingerprints{}` |
| Trigger fired | `REVERIFY_TRIGGERED`, `VERIFICATION_SUPERSEDED`, `BUSINESS_STATUS_CHANGED` (+ `CONTACT_READY_REVOKED` if it was ready) | `businesses` | `trigger` (R-code), `recheck_scope[]`, `before_fingerprint`, `after_fingerprint`, `age_days` |
| Expired by the sweep | `VERIFICATION_EXPIRED`, then the trigger set above | `businesses` | `verified_at`, `verification_valid_days`, `policy_version`, `job_run_id` |
| Revoked by hand | `VERIFICATION_REVOKED`, `VERIFICATION_SUPERSEDED`, `BUSINESS_STATUS_CHANGED` | `verifications` | `reason_note` |
| Promoted | `CONTACT_READY_GRANTED`, `BUSINESS_STATUS_CHANGED` | `businesses` | `ready_campaign_id`, `readiness{}` — the full seven-clause snapshot |
| Demoted | `CONTACT_READY_REVOKED`, `BUSINESS_STATUS_CHANGED` | `businesses` | `failing_clause`, `blocking_code`, `blocking_sentence`, `readiness{}` |
| Reopened | `VERIFICATION_REOPENED`, `BUSINESS_STATUS_CHANGED` | `businesses` | `prior_verification_id`, `prior_reason_code`, `reopen_note`, `cool_off_days`, `days_since_rejection` |
| Rediscovery | `REDISCOVERY_RESOLVED` | `campaign_businesses` | `business_key`, `campaign_business_id`, `prior_verification_id`, `branch`, `cb_state`, `exclusion_reason` |

The `BUSINESS_VERIFIED` payload in full, because it is the row that authorises everything downstream
and §48 reads it:

```json
{
  "verification_id": "ver_01JSAMPLE00000000000000V1",
  "mode": "FULL",
  "entry_point": "QUEUE",
  "checklist": {
    "IDENTITY_CORRECT":       {"passed": true, "note": null},
    "IN_TARGET_CITY":         {"passed": true, "note": null},
    "CATEGORY_CORRECT":       {"passed": true, "note": "SAMPLE — diagnostics, not a hospital."},
    "APPEARS_OPERATIONAL":    {"passed": true, "note": null},
    "CONTACT_LEGITIMATE":     {"passed": true, "note": null},
    "RESEARCH_RELEVANT":      {"passed": true, "note": null},
    "OPPORTUNITY_REASONABLE": {"passed": true, "note": null},
    "OUTREACH_APPROPRIATE":   {"passed": true, "note": null},
    "NO_DNC_RECORD":          {"passed": true, "note": null}
  },
  "why_note": "SAMPLE — paper report collection confirmed on their own site; owner-run, 2 branches.",
  "contact_id_confirmed": "cnt_01JSAMPLE0000000000000C1",
  "dwell_ms": 71240,
  "dwell_required_ms": 47000,
  "active_ms": 61240,
  "sources_total": 5,
  "sources_visited": ["src_01JSAMPLE0000000000000S1","src_01JSAMPLE0000000000000S2",
                      "src_01JSAMPLE0000000000000S3"],
  "sources_waived": [],
  "research_run_id": "rr_01JSAMPLE0000000000000R1",
  "opportunity_id": "opp_01JSAMPLE0000000000000O1",
  "research_fingerprint": "sha256:SAMPLE…",
  "contact_fingerprint": "sha256:SAMPLE…",
  "policy_version": "cp-1",
  "session_id": "sess_SAMPLE",
  "from_export": false
}
```

(SAMPLE content.) `pii_class` for every action in this section is `NONE` or `REFERENCE`: the
checklist carries booleans and notes, `contact_id_confirmed` is a foreign key, and no contact value
appears in any payload. `audit.write()`'s `_scrub_addresses()` asserts this at write time.

### 4.11.3 Deliberately not audited

| Not written | Why |
|---|---|
| A row per checkbox toggle | `11-audit-architecture.md` §11.6.2 already rules this out: nine boxes toggled a few times each triples audit volume and answers nothing. The final `checklist{}` is what matters, and the intermediate state lives in `verification_checks` |
| A row per source **visit** | High volume, low value, and the identities are already in `verifications.sources_visited`, the JSON array `01` §1.8.1 defines. A *waiver* is audited, because a waiver is a decision |
| Scroll depth, mouse movement, keystroke timing | Surveillance of a one-person team by itself. `dwell_ms` and `active_ms` are the two numbers that carry information, and both are aggregates |
| A row when the predicate is evaluated and nothing changes | The sweep evaluates thousands per night. Only transitions are audited; the `SweepResult` counts go in `jobs.result` |

### 4.11.4 The reconstruction query

The question this whole document exists to answer, six months later:

```sql
-- "Why was this business contacted, and who said it was allowed?"
SELECT a.at, a.action, a.actor_label, a.entity_table, a.entity_id,
       json_extract(a.detail_json, '$.verification_id') AS verification_id,
       json_extract(a.detail_json, '$.reason_code')     AS reason_code,
       json_extract(a.detail_json, '$.dwell_ms')        AS dwell_ms,
       json_extract(a.detail_json, '$.mode')            AS mode
  FROM audit_log a
 WHERE a.business_id = :business_id
   AND a.action IN ('BUSINESS_DISCOVERED','RESEARCH_RUN_COMPLETED','OPPORTUNITY_SCORED',
                    'VERIFICATION_OPENED','BUSINESS_VERIFIED','BUSINESS_REJECTED',
                    'VERIFICATION_CARRIED_FORWARD','VERIFICATION_BULK_APPLIED',
                    'CONTACT_READY_GRANTED','CONTACT_READY_REVOKED','REVERIFY_TRIGGERED',
                    'SELECTION_CREATED','MESSAGE_GENERATED','MESSAGE_APPROVED','MESSAGE_SENT')
 ORDER BY a.seq;
```

Read top to bottom it is spec §45's chain with a timestamp and an actor on every arrow. If any row
between `BUSINESS_VERIFIED` and `MESSAGE_SENT` is missing, the send should not have happened, and the
chain hash in `11-audit-architecture.md` §11.5 is what makes "missing" detectable rather than
deniable.

---

## 4.12 Surface, module, config, tests

### 4.12.1 Endpoint index

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/verify/<business_id>` | session | The screen. Query: `?intent=reject`, `?from=export`, `?campaign=`, `?return=` |
| GET | `/api/v1/verifications/queue` | session | The queue (§4.5.4). Params: `campaign_id`, `city`, `industry`, `limit`, `offset` |
| GET | `/api/v1/verifications/<business_id>` | session | The screen payload (§4.5.4) |
| POST | `/api/v1/verifications` | session | Open or resume a draft. Idempotent per (business, user) |
| PUT | `/api/v1/verifications/<verification_id>/checks/<check_key>` | session | Answer one check |
| POST | `/api/v1/verifications/<verification_id>/sources/<source_id>/visited` | session | Visit beacon, 204 |
| POST | `/api/v1/verifications/<verification_id>/sources/<source_id>/waive` | session | Waive with a reason |
| POST | `/api/v1/verifications/<verification_id>/submit` | session | **The only writer of a `VERIFIED` verdict** (§4.6.4) |
| POST | `/api/v1/verifications/<verification_id>/abandon` | session | Draft -> `ABANDONED` |
| POST | `/api/v1/verifications/bulk` | session | Bulk reject / skip / unskip / requeue (§4.8.2) |
| GET | `/api/v1/verifications/<business_id>/history` | session | Every prior verification of this business, across every campaign |
| POST | `/api/v1/businesses/<business_id>/skip` | session | T04 / T08 / T13 / T18 |
| POST | `/api/v1/businesses/<business_id>/unskip` | session | T23 |
| POST | `/api/v1/businesses/<business_id>/reopen` | session | T29 (§4.2.4) |
| POST | `/api/v1/businesses/<business_id>/revoke-verification` | session | T11 / T16 |
| POST | `/api/v1/businesses/<business_id>/contacts/<contact_id>/confirm` | session | Check 5's contact confirmation (§4.6.7) |
| GET | `/api/v1/businesses/<business_id>/readiness` | session | `ContactReadiness` as JSON, for the badge and the debugging of "why is this not selectable" |

Every path in this table reads or writes a verdict. None of them transmits anything, none of them
accepts a channel, and none of them can reach `radar.outreach.send_message`. That absence is §19,
and test L5 in §4.10.5 is its proof.

### 4.12.2 Module map

| Module | Contents | Docstring, in the house voice |
|---|---|---|
| `radar/verify.py` | `set_status()`, `contact_ready_predicate()`, `promote_contact_ready()`, `revoke_contact_ready()`, `refresh_contact_readiness()`, `open_verification()`, `answer_check()`, `submit_verification()`, `apply_rejection()`, `bulk_apply()`, `sweep_verification_staleness()`, the fingerprints | "Without this module `VERIFIED` is a string somebody sets. This is the only place that writes it, the only place that decides who may, and the only place that knows what it stops being true. Every other module in the system treats `VERIFIED` as a human's word about a real business; this module is where that word is actually taken." |
| `radar/web/verify_views.py` | The routes in §4.12.1, the validation ladder, the screen payload | "Without this module the checklist is a form that posts anywhere. It exists so that exactly one HTTP path can produce a verdict, and so that every refusal on the way has a sentence Sagar can act on." |
| `radar/models.py` | `Verification`, `VerificationCheck`, `ReasonCode`, `ContactReadiness`, `ClauseResult`, with `from_row()` / `to_row()` | per house style |

### 4.12.3 Config

The `verify:` block is in §4.7.8. Two settings live in `contact_policy` rather than `config.yaml`,
because they are policy and are per-campaign overridable: `verification_valid_days` and the
`*_enabled` channel switches that clause C3 reads. Two are mirrored into `app_settings` at startup so
`v_contact_ready` can read them without a bound parameter: `verify.min_research_confidence` and
`verify.min_research_confidence_pct`.

### 4.12.4 Test matrix

| # | Test | Asserts |
|---|---|---|
| 1 | `test_only_verify_module_writes_business_status` | §4.2.7's grep |
| 2 | `test_every_transition_in_the_table_is_reachable` | Each of T01–T29 executes against a fixture; every pair **not** in `business_status_transitions` aborts |
| 3 | `test_contact_ready_predicate_clause_matrix` | One fixture per clause: exactly that clause fails, `failing_clause` and `demote_to` are right, the other six pass |
| 4 | `test_predicate_never_looser_than_engine` | Over the fixture corpus, `predicate.ok` implies no `BLOCK` from `check_send_eligibility(stage='SELECT')` on any gate in `CLAUSE_GATES` |
| 5 | `test_view_and_function_agree` | `v_contact_ready`'s seven columns equal `contact_ready_predicate()`'s seven clause results, for every fixture business |
| 6 | `test_every_clause_input_change_calls_refresh` | Import-graph walk: each writer of `business_contacts`, `suppressions`, `responses`, `opportunities` reaches `refresh_contact_readiness` |
| 7 | `test_nine_checks_required_for_verified` | Eight passed, nine with one `NULL`, and nine passed on a superseded row all fail — at the API, at the `CHECK` and at the trigger |
| 8 | `test_failed_check_forces_rejection` | `verdict='VERIFIED'` with any `passed=0` returns 400 `FAILED_CHECK_REQUIRES_REJECTION` |
| 9 | `test_failed_check_needs_note` | `passed=0` with a 4-character note aborts at the trigger |
| 10 | `test_partial_completion_saves_as_draft` | Four answers, reload, the four are still there, `businesses.status` never moved, one `VERIFICATION_OPENED` and at most one `VERIFICATION_SAVED` per minute |
| 11 | `test_reason_code_taxonomy_invariants` | Every seed row satisfies the three `CHECK`s; every `applies_to_check` resolves; every check has at least one `default_reason` |
| 12 | `test_permanent_rejection_writes_suppression` | Each of the four permanent codes writes a `suppressions` row, and gate A blocks every channel afterwards |
| 13 | `test_dwell_enforced_server_side` | Submitting at `dwell_required_ms - 1` returns 400 `DWELL_NOT_MET` even when the client reports a large `active_ms` |
| 14 | `test_required_sources_block_approve` | Approve refused while a required source is neither visited nor waived; a 9-character waive reason refused |
| 15 | `test_no_bulk_verify_anywhere` | Endpoint 400s; `CHECK` rejects `mode='BULK'` with `verdict='VERIFIED'`; template grep clean |
| 16 | `test_bulk_limits` | Over `bulk_max_rows` refused; a non-`bulk_ok` reason refused; `expected_count` mismatch refused; a decided row skipped not overwritten |
| 17 | `test_carry_forward_inherits_verified_at` | The carried verification's `verified_at` equals the source's; it expires on the source's schedule; a differing fingerprint makes it ineligible |
| 18 | `test_staleness_demotes_before_selection` | A business verified 31 days ago is `NEEDS_VERIFICATION` after the sweep and absent from the selectable grid, not merely blocked at preview |
| 19 | `test_reverify_scope_per_trigger` | Each of R1–R9 produces the `recheck_scope` in §4.9.2 and carries the rest |
| 20 | `test_fingerprints_ignore_noise` | A whitespace-only site edit, a re-run with the same findings, and a capitalisation change to an email all leave the fingerprints equal |
| 21 | `test_suppression_keeps_signature` | A suppression demotes `CONTACT_READY -> VERIFIED`; `verifications.superseded_at` stays `NULL`; §5.5.3's panel still renders the checklist |
| 22 | `test_hard_bounce_two_tier` | A `BOUNCE_HARD` on one address blocks the business; deactivating it and confirming another restores C4; a `REPLY_OPT_OUT` on the same address does not |
| 23 | `test_reopen_requires_non_permanent_reason_and_cooloff` | Each of the four permanent codes has no reopen path; a non-permanent one inside its cool-off returns 409; past it, the business lands in `NEEDS_VERIFICATION` with a blank checklist |
| 24 | `test_rediscovery_branches` | Each row of §4.2.6's table produces the stated insert status and the `REDISCOVERY_RESOLVED` audit row |
| 25 | `test_audit_completeness_for_verification` | Every action in §4.11.2 is emitted for its event, with every named `detail_json` key present and no contact value anywhere in the payload |
| 26 | L1–L7 from §4.10.5 | The three layers |

---

## Open questions

1. **Gate `C4 / C_CONFIDENCE_LOW` does not exist yet.** Clause C7 (`research_confidence` adequate)
   is required by §15's confidence display and by the brief for this document, but
   `05-outreach-workflow.md` §5.9.1's gate catalogue has no confidence gate. Either it is added
   there as `C4 / C_CONFIDENCE_LOW` — hard, all stages, sentence *"Research confidence for {name} is
   {confidence} ({pct}%), below your floor of {min}"* — or C7 stays local to `radar/verify.py` and
   the predicate is knowingly stricter than the engine on one clause. Adding the gate is the
   recommendation; it is one row in a table and one branch in `GATE_C_SQL`.

2. **`05-outreach-workflow.md` §5.4.2's grid `CASE` needs one branch** (`b.status = 'VERIFIED' AND
   b.contact_ready_block_code IS NOT NULL THEN b.contact_ready_block_code`), or a business held back
   by clause C5 or C7 is labelled `D_NOT_VERIFIED` on a screen where it is plainly verified. Related:
   §5.4.2's `suppressed` CTE does not implement C4's `BOUNCE_HARD` tier (§4.3.2) and will therefore
   disagree with the predicate for exactly one case — a bounced address that has since been
   deactivated.

3. **The staleness window has two values.** `05-outreach-workflow.md` §5.3.1 defines
   `contact_policy.verification_valid_days = 30` and gate D3 uses it; `14-background-jobs.md`
   §14.8.20 names `verify.ttl_days` default 45 for the sweep's verification pass. Fifteen days apart
   means a business is blocked by D3 for two weeks before the sweep demotes it. This document treats
   `contact_policy.verification_valid_days` as the single source of truth and asks that
   §14.8.20's pass read `effective_policy()`. Whether 30 is the right default is a separate
   question, already open as §5.25 item 5 in that document.

4. **`promote_contact_ready()`'s docstring in `05-outreach-workflow.md` §5.4.1** says a contact
   deleted later "is caught by gate E1 at send time". Under §4.9.4 it is caught earlier, by
   `refresh_contact_readiness()` at P2 and by the nightly sweep. Gate E1 remains the backstop, so
   these are compatible, but the docstring understates what happens and should be amended when that
   function is written.

5. **Settled: `verifications.note` vs `why_note`.** `01-data-model.md` §1.8.1 carries **both** —
   `why_note` is the anti-rubber-stamp justification this document requires at approve time, `note`
   is the free-text field `03-html-report.md` §3.3.1 renders. Two columns, two purposes, no alias.
   Nothing to decide.

6. **Settled: `verifications.result` vs `.verdict`.** `01-data-model.md` §1.2.4 ruling D2 makes it
   `verdict` and assigns `10-human-handoff.md` the one-word fix in `v_funnel_business`. Nothing to
   decide here.

7. **Four migration files this document needs have no slot in `01-data-model.md` §1.13.2.** The
   collision it flagged is settled — §1.13.2 is the single renumbered sequence and §4.4.5 now uses
   it — but that sequence is 54 files and lists none of the following. All four are appended after
   `054`, which satisfies every ordering constraint in §1.13.3 (C8 in particular: views last):

   | Requested | Creates | Must follow |
   |---|---|---|
   | `055_verification_sources.sql` | `verification_sources` (§4.4.4) | `010`, `005` |
   | `056_verification_immutability.sql` | `trg_verifications_immutable`, `_no_delete`, `_touch`, `trg_verification_checks_immutable` (§4.4.1, §4.4.2) | `010` |
   | `057_v_contact_ready.sql` | `v_contact_ready`, `v_contact_ready_business` (§4.3.3) | `004`, `013`, `023` |
   | `058_no_draft_before_contact_ready.sql` | the three V3 triggers (§4.10.4) | `015`, `016`, `017` |

   §1.13.2's row for `009_verification_reason_codes.sql` also needs its "Creates" column to name
   `verification_check_defs` as well, per §4.4.5.

8. **`app_settings` is assumed.** `v_contact_ready` reads `verify.min_research_confidence` and
   `verify.min_research_confidence_pct` from a key/value table that `01-data-model.md` has not been
   confirmed to provide. If it does not exist, the view needs those two values inlined and rewritten
   by a migration whenever the setting changes — workable, but a `CREATE VIEW` in a settings save
   path is unpleasant enough to be worth avoiding.

9. **Three tables and two views are extensions to `_CONTEXT.md` §6's canonical list**:
   `verification_check_defs`, `verification_reason_codes` (already introduced by §4.2's text),
   `verification_sources`, `business_status_transitions`, `v_contact_ready` and
   `v_contact_ready_business`. All are owned here and none of them renames anything canonical, but
   if the intent was that §6's list is exhaustive rather than authoritative-for-shared-names, they
   need approval. `campaign_businesses` is in the same position and is `01-data-model.md` §1.2.2's
   to justify.

10. **Whether the dwell floor should scale with opportunity score.** A score-95 business arguably
    deserves more attention than a score-62 one, and `dwell_required_ms` could scale with the band.
    Not designed in, because a longer wait on the best rows is also the most annoying wait, and the
    queue ordering in §4.5.4 already spends Sagar's freshest attention on them. Worth revisiting
    after a few real campaigns, when there are actual verification-time numbers to look at.

11. **What happens to a `CONTACT_READY` business when its campaign is archived** (§42 wants
    campaigns reopenable). This document demotes on campaign close via P9 and clause C2, which
    assumes `campaigns.status` has a closed value that `05-outreach-workflow.md` and
    `14-background-jobs.md` agree on. If archived campaigns keep their businesses selectable, C2
    needs a different definition and §42's "reopen a previous campaign" needs to say what reopening
    does to a verification that expired while the campaign was shut.

12. **Amendment request against `01-data-model.md` §1.8.1 (`verifications`).** §1.8.1 is the
    arbiter and this document no longer prints competing DDL. Fourteen columns it uses are not in
    §1.8.1, and all fourteen are additive — no existing column changes shape, no `CHECK` loosens:

    | Column | Shape | Used at |
    |---|---|---|
    | `opened_by` | `TEXT NOT NULL REFERENCES users(id)` | §4.6.4 step 2, `NOT_YOUR_DRAFT` |
    | `submitted_at` | `TEXT` | §4.6.4, the `SUBMITTED` stamp distinct from `verified_at` |
    | `rejected_at` | `TEXT` | §4.6.6, T29's `cool_off_days` clock |
    | `entry_point` | `TEXT NOT NULL DEFAULT 'QUEUE' CHECK (entry_point IN ('QUEUE','GRID','EXPORT','DEEP_LINK','OUTREACH_RETURN','BULK','SWEEP'))` | §4.7.6, the considered-vs-batched audit |
    | `contact_id_confirmed` | `TEXT REFERENCES business_contacts(id)` | §4.6.7, check 5. A foreign key, never a contact value |
    | `duplicate_of_business_id` | `TEXT REFERENCES businesses(id)` | reason code `DUPLICATE_OF_EXISTING` |
    | `active_ms` | `INTEGER NOT NULL DEFAULT 0 CHECK (active_ms >= 0)` | §4.7.3, client-reported, never trusted for the decision |
    | `bulk_batch_id`, `bulk_size` | `TEXT`, `INTEGER` | §4.8.2 |
    | `carried_from_verification_id` | `TEXT REFERENCES verifications(id)` | §4.8.3 |
    | `opportunity_id` | `TEXT REFERENCES opportunities(id)` | §4.11.2's payload |
    | `website_hash`, `policy_version` | `TEXT` | §4.9.6, §4.9.2 R8 |
    | `updated_at` | `TEXT NOT NULL DEFAULT (strftime(...))` | `trg_verifications_touch` (§4.4.1) |

    Plus two `CHECK`s: `CHECK (bulk_batch_id IS NULL OR verdict <> 'VERIFIED')`, which is the whole
    of §4.8.1's "a bulk action is never a VERIFIED verdict" rule enforced where it cannot be
    forgotten; and `CHECK (reason_code <> 'DUPLICATE_OF_EXISTING' OR duplicate_of_business_id IS
    NOT NULL)`.

    Plus two values on the `mode` `CHECK`: `('FULL','QUICK_REJECT','RECHECK','CARRY_FORWARD',
    'BULK')`. `TARGETED` is gone — §1.8.1's `RECHECK` is the same thing and this document now uses
    that name — but `CARRY_FORWARD` and `BULK` are genuinely distinct modes that §4.7.6's audit and
    §4.8.1's rules branch on, and folding them into `QUICK_REJECT` would lose the distinction the
    audit exists to record.

13. **Amendment request against `01-data-model.md` §1.8.2 (`verification_checks`) and §1.4
    (`businesses`).** §1.8.2 needs one additive column, `carried_from TEXT REFERENCES
    verifications(id)`, for §4.8.3's carry-forward and §4.9.3's targeted recheck: without it a
    pre-filled answer is indistinguishable from one Sagar typed, which is exactly the distinction
    §4.7 exists to preserve. §1.4 needs two more beyond the nine §1.2.2 already folds in:
    `contact_ready_block_code TEXT` and `contact_ready_checked_at TEXT` (§4.3.4).

14. **Where the four `verification_check_defs` seed values live.** `prompt` and `helper` are UI
    strings in a table, which means changing the wording of §16's nine questions is a data edit
    rather than a code change. That is deliberate — the screen, the audit and §4.9.3's recheck
    scopes read one source of truth — but it also means a migration is the only reviewable record
    of a wording change. If that turns out to be the wrong trade, the alternative is a Python
    constant in `radar/verify.py` and a `check_key`-only table; not recommended, but worth naming.
