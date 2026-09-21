# 10. Human handoff

This document decides what happens at the only moment in `business_radar` that produces revenue: a
business replies and the reply is worth a human. It fixes the trigger conditions that create a
`handoffs` row, the DDL and state machine for that row, the exact brief Sagar reads on his phone at
9pm and on the web at his desk, how the notification is delivered and de-duplicated, how the
"recommended next action" is generated and why it can never be executed, the enforcement that stops
every automated follow-up to that business the instant a handoff opens, the §54 funnel with each
stage's entry condition written as SQL, and how won deals feed back into scoring so next month's
research is aimed better. Owns spec §34, §35 and §54, plus the outcome half of §53.

Related documents: `01-data-model.md` (`businesses`, `opportunities`, `suppressions`),
`09-response-classification.md` (`responses`, the classifier), `05-outreach-workflow.md`
(`outreach_drafts`, `outreach_messages`, follow-up scheduling), `11-audit-architecture.md`
(`audit_log`), `15-ui-wireframe.md` (shared components), `13-api-endpoints.md` (route registry),
`14-background-jobs.md` (`jobs`, `job_runs`).

---

## 10.1 The rule this document exists to enforce

Spec §34 and §55 together say one thing:

> The AI classifies inbound responses. It never replies to them. An interested lead stops the
> machine and pages Sagar.

So the handoff subsystem has exactly two jobs and no third one.

| Job | Meaning |
|---|---|
| Stop the machine | The moment a handoff row exists, every automated outbound path to that business is closed. Not deprioritised — closed, at the database level. See §10.8. |
| Page the human, with everything he needs | One message, one screen, all of §34's fields, assembled once and stored, so it renders identically at 9pm on a phone with one bar of signal and at 9am on a laptop. See §10.5 and §10.6. |

Explicit non-goals, restated so nobody adds them later:

- The handoff subsystem does not draft a reply. Not even a draft that requires approval. §55 says
  Sagar personally handles serious prospects; a machine-drafted reply to a prospect who just said
  "yes" is the thing most likely to read as a bot at the worst possible moment.
- The handoff subsystem does not schedule a demo, send a calendar invite, or touch a contact point.
- The handoff subsystem never auto-closes a handoff. An expired SLA changes how loudly the system
  shouts. It never changes the state of the lead.

---

## 10.2 Trigger conditions

### 10.2.1 Spec-mandated triggers (§34)

These five `responses.classification` values create a handoff. No configuration switch disables
them; they are the product.

| `responses.classification` | `handoffs.priority` | Why this priority |
|---|---|---|
| `VERY_INTERESTED` | `HIGH` | Buying signal with heat. A same-day human reply is the difference between a demo and a cold trail. |
| `DEMO_REQUESTED` | `HIGH` | They asked for the thing the product exists to sell. |
| `MEETING_REQUESTED` | `HIGH` | A calendar ask decays fast; a two-day-late reply loses the slot. |
| `PRICE_REQUESTED` | `HIGH` | Price is the highest-intent question a stranger asks. |
| `INTERESTED` | `NORMAL` | Real, but soft. A next-morning reply costs nothing. |

`priority` is a scheduling dimension for notification and SLA. It is **not** the `HIGH`/`MEDIUM`/
`LOW` confidence scale from `_CONTEXT.md` §6, and the UI must never render it adjacent to a
confidence badge without its own label.

### 10.2.2 Triggers worth adding, and why

| Added trigger | `trigger_rule` | Priority | Reason it must exist |
|---|---|---|---|
| `classification = 'COMPLAINT'` | `COMPLAINT` | `URGENT` | A complaint is a handoff of a different kind: not a lead, a live compliance incident. Left in a queue for a week it becomes a WABA quality downgrade (`_CONTEXT.md` §4), an ESP abuse report that kills the sending domain, or a DPDP grievance. The system's first response is to stop permanently, then tell a human. |
| `confidence_pct < handoff.low_confidence_below_pct`, any class | `LOW_CONFIDENCE` | `NORMAL` | A classifier 45% sure a reply means `NOT_INTERESTED` has, in practice, thrown a lead away. `gemini-2.5-flash` is the right tool for volume and the wrong tool to trust unsupervised. A low-confidence read of *any* class — including the negative ones — gets eyes. |
| Raw body matches the legal lexicon | `LEGAL_LANGUAGE` | `URGENT` | The one category where a slow response has an unbounded cost. It runs on raw text **before** the LLM classifier, deterministically, so a model outage or a prompt-injection attempt inside the reply body cannot suppress it. |
| Sagar clicks "Hand this to me" on `/business/<id>` | `MANUAL` | as chosen | Escape hatch. He saw something the classifier did not. |

Considered and deliberately **not** made triggers:

| Classification | Handling instead |
|---|---|
| `MORE_INFORMATION` | Daily digest line only. A brochure request, not a buying signal. Sagar can escalate with the `MANUAL` trigger. |
| `LATER` | Digest only. Writes a not-before date used by the follow-up scheduler in `05-outreach-workflow.md`. |
| `NOT_INTERESTED`, `ALREADY_HAVE_SOFTWARE` | Terminal, no handoff — unless `LOW_CONFIDENCE` also fires. `ALREADY_HAVE_SOFTWARE` additionally feeds the category penalty in §10.10. |
| `WRONG_CONTACT` | Digest only. Routes to a contact-correction task, not a lead. |
| `OPT_OUT` | Writes the `suppressions` row **immediately and unconditionally** (invariant 3). Creates a handoff only when `LOW_CONFIDENCE` also fires, and even then the handoff is informational: nothing Sagar can click in this application reverses a suppression. |
| `UNKNOWN` | Low confidence by construction, so it reaches Sagar through the `LOW_CONFIDENCE` rule rather than a rule of its own. |

### 10.2.3 The legal lexicon

Deterministic, case-insensitive, word-boundary regex over the raw inbound body, before any
normalisation the classifier performs. Held in `config.yaml` so it can grow without a deploy.

```yaml
handoff:
  legal_lexicon:
    # English
    - "cease and desist"
    - "legal (action|notice|proceeding)"
    - "lawyer|advocate|attorney|legal counsel"
    - "defamation|harassment"
    - "unsolicited|spam(ming)?"
    - "data protection|privacy (act|law)|dpdp|gdpr"
    - "consent (was )?(not )?(given|obtained)"
    - "how did you (get|obtain) my (email|number|details)"
    - "trai|do not disturb|dnd registry"
    - "cyber ?(cell|crime)|police|lodge an? fir"
    - "report (you|this) to"
    - "grievance officer"
    # Transliterated Hindi / Marathi seen in Maharashtra business email
    - "kanooni|vakil|notice bhej"
    - "takrar|takraar"
```

Rules:

1. The scan runs in `radar/classify.py` **before** the Gemini call. Its result is written to
   `responses.legal_flag`, `responses.legal_flag_pattern` and `responses.legal_flag_excerpt`
   regardless of what the classifier later returns.
2. A match forces `trigger_rule = 'LEGAL_LANGUAGE'`, `priority = 'URGENT'`, and writes a
   `suppressions` row for the business with `reason = 'LEGAL_LANGUAGE'`.
3. `handoffs.trigger_detail` stores the matched pattern plus a 200-character window of surrounding
   text, so Sagar sees why it fired without opening the full body.
4. False positives are expected and acceptable. A wrongly-flagged business costs one suppression,
   reversible only by a manual DB operation with an audit row (invariant 3). A missed legal notice
   costs more than that.

### 10.2.4 Evaluation order

An earlier rule wins and sets the priority ceiling.

```
1. LEGAL_LANGUAGE   deterministic regex on raw text, pre-LLM     -> URGENT
2. COMPLAINT        classification                               -> URGENT
3. CLASSIFICATION   the five §34 values                          -> HIGH | NORMAL
4. LOW_CONFIDENCE   confidence_pct < threshold, any class        -> NORMAL
5. MANUAL           operator initiated                           -> as chosen
```

```python
# radar/handoff.py

@dataclass(slots=True)
class TriggerDecision:
    rule: str                     # CLASSIFICATION | COMPLAINT | LOW_CONFIDENCE | LEGAL_LANGUAGE | MANUAL
    priority: str                 # URGENT | HIGH | NORMAL
    classification: str | None    # responses.classification that produced it, if any
    detail: str                   # human-readable reason -> handoffs.trigger_detail
    suppress_business: bool       # COMPLAINT / LEGAL_LANGUAGE write a suppressions row first


HANDOFF_CLASSIFICATIONS: dict[str, str] = {
    "VERY_INTERESTED":   "HIGH",
    "DEMO_REQUESTED":    "HIGH",
    "MEETING_REQUESTED": "HIGH",
    "PRICE_REQUESTED":   "HIGH",
    "INTERESTED":        "NORMAL",
}


def evaluate_triggers(response: Response, cfg: Config) -> TriggerDecision | None:
    """Decide whether this response stops the machine. Pure: no I/O, no side effects.

    Returns None when the response belongs in the daily digest rather than on a phone.
    """
    if response.legal_flag:
        return TriggerDecision(
            rule="LEGAL_LANGUAGE",
            priority="URGENT",
            classification=response.classification,
            detail=f"matched {response.legal_flag_pattern!r}: {response.legal_flag_excerpt}",
            suppress_business=True,
        )
    if response.classification == "COMPLAINT":
        return TriggerDecision("COMPLAINT", "URGENT", "COMPLAINT",
                               "classified COMPLAINT", suppress_business=True)

    if response.classification in HANDOFF_CLASSIFICATIONS:
        return TriggerDecision(
            "CLASSIFICATION",
            HANDOFF_CLASSIFICATIONS[response.classification],
            response.classification,
            f"classified {response.classification} at {response.confidence_pct}%",
            suppress_business=False,
        )

    threshold = int(cfg.get("handoff.low_confidence_below_pct", 70))
    if (response.confidence_pct or 0) < threshold:
        return TriggerDecision(
            "LOW_CONFIDENCE", "NORMAL", response.classification,
            f"classifier only {response.confidence_pct}% sure of "
            f"{response.classification} (threshold {threshold}%)",
            suppress_business=False,
        )
    return None
```

```yaml
handoff:
  low_confidence_below_pct: 70     # any class below this gets human eyes
  auto_suppress_on_complaint: true
  auto_suppress_on_legal: true
```

Both `auto_suppress_*` keys exist so the behaviour is visible in the file Sagar reads. `Config.load`
logs an error and ignores the value if either is set to `false`. Stopping on a complaint is not a
preference.

---

## 10.3 Data model

### 10.3.1 `handoffs`

Id prefix `hnd_` (26-char Crockford base32 via `radar/ids.py`, consistent with `_CONTEXT.md` §2).

```sql
-- radar/migrations/010_handoffs.sql
-- Forward-only, idempotent. Applied by the schema_version table.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS handoffs (
    id                      TEXT PRIMARY KEY,                       -- hnd_...
    business_id             TEXT NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    campaign_id             TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
    response_id             TEXT NOT NULL REFERENCES responses(id) ON DELETE RESTRICT,
    outreach_message_id     TEXT REFERENCES outreach_messages(id) ON DELETE SET NULL,
    previous_handoff_id     TEXT REFERENCES handoffs(id) ON DELETE SET NULL,
    owner_user_id           TEXT REFERENCES users(id) ON DELETE SET NULL,

    -- why this row exists (§10.2)
    trigger_rule            TEXT NOT NULL CHECK (trigger_rule IN (
                                'CLASSIFICATION','COMPLAINT','LOW_CONFIDENCE',
                                'LEGAL_LANGUAGE','MANUAL')),
    trigger_classification  TEXT CHECK (trigger_classification IS NULL OR trigger_classification IN (
                                'INTERESTED','VERY_INTERESTED','DEMO_REQUESTED','MEETING_REQUESTED',
                                'PRICE_REQUESTED','MORE_INFORMATION','LATER','NOT_INTERESTED',
                                'ALREADY_HAVE_SOFTWARE','WRONG_CONTACT','OPT_OUT','COMPLAINT',
                                'UNKNOWN')),
    trigger_detail          TEXT NOT NULL DEFAULT '',
    confidence              TEXT NOT NULL CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    confidence_pct          INTEGER CHECK (confidence_pct IS NULL
                                           OR confidence_pct BETWEEN 0 AND 100),

    -- lifecycle (§10.4)
    priority                TEXT NOT NULL DEFAULT 'NORMAL'
                                CHECK (priority IN ('URGENT','HIGH','NORMAL')),
    state                   TEXT NOT NULL DEFAULT 'OPEN'
                                CHECK (state IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','CLOSED')),
    outcome                 TEXT CHECK (outcome IS NULL OR outcome IN (
                                'DEMO_SCHEDULED','PROPOSAL_SENT','WON','LOST','NO_RESPONSE')),
    lost_reason             TEXT CHECK (lost_reason IS NULL OR lost_reason IN (
                                'PRICE','ALREADY_HAVE_SOFTWARE','NO_BUDGET','NO_DECISION_MAKER',
                                'WRONG_FIT','WENT_QUIET','OTHER')),

    -- the §34 brief, denormalised at creation (§10.5)
    brief_json              TEXT NOT NULL,
    brief_version           INTEGER NOT NULL DEFAULT 1,
    response_count          INTEGER NOT NULL DEFAULT 1,

    -- recommended next action (§10.7) - text only, never executable
    recommended_action      TEXT NOT NULL,
    recommended_channel     TEXT CHECK (recommended_channel IS NULL OR recommended_channel IN (
                                'EMAIL','WHATSAPP','PHONE','MANUAL')),
    recommended_by_when     TEXT,                                   -- ISO-8601 UTC, advisory only
    action_rule_id          TEXT NOT NULL,                          -- deterministic rule that fired
    action_model_id         TEXT,                                   -- null when no LLM was used
    action_prompt_version   TEXT,
    action_input_tokens     INTEGER,
    action_output_tokens    INTEGER,

    -- notification bookkeeping (§10.6). No separate notifications table: the canonical
    -- table list in _CONTEXT.md §6 does not have one and one handoff needs one row.
    notify_count            INTEGER NOT NULL DEFAULT 0,
    first_notified_at       TEXT,
    last_notified_at        TEXT,
    last_notify_channel     TEXT CHECK (last_notify_channel IS NULL OR last_notify_channel IN (
                                'TELEGRAM','EMAIL','DIGEST','NONE')),
    telegram_chat_id        TEXT,
    telegram_message_id     INTEGER,                                -- for editMessageText in place
    snoozed_until           TEXT,

    -- SLA (§10.4.3)
    sla_ack_due_at          TEXT NOT NULL,
    sla_progress_due_at     TEXT NOT NULL,
    sla_close_due_at        TEXT NOT NULL,
    sla_breach_count        INTEGER NOT NULL DEFAULT 0,
    sla_last_breach_at      TEXT,

    -- post-handoff tracking (§54 stages 7-9, §53 feedback) (§10.10)
    demo_scheduled_at       TEXT,
    demo_held_at            TEXT,
    proposal_sent_at        TEXT,
    proposal_value_inr      INTEGER CHECK (proposal_value_inr IS NULL OR proposal_value_inr >= 0),
    won_value_inr           INTEGER CHECK (won_value_inr IS NULL OR won_value_inr >= 0),

    created_at              TEXT NOT NULL
                                DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    acknowledged_at         TEXT,
    started_at              TEXT,
    closed_at               TEXT,
    updated_at              TEXT NOT NULL
                                DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    -- state/outcome coherence, enforced by the database, not only by Python
    CHECK (state <> 'CLOSED' OR outcome IS NOT NULL),
    CHECK (state <> 'CLOSED' OR closed_at IS NOT NULL),
    CHECK (outcome IS NULL OR state = 'CLOSED'),
    CHECK (state = 'OPEN' OR acknowledged_at IS NOT NULL),
    CHECK (state <> 'IN_PROGRESS' OR started_at IS NOT NULL),
    CHECK (outcome <> 'WON' OR won_value_inr IS NOT NULL),
    CHECK (outcome <> 'LOST' OR lost_reason IS NOT NULL),
    CHECK (outcome <> 'DEMO_SCHEDULED' OR demo_scheduled_at IS NOT NULL),
    CHECK (outcome <> 'PROPOSAL_SENT' OR proposal_sent_at IS NOT NULL)
);

-- One live handoff per business. This partial unique index IS the de-duplication
-- guarantee from §10.6.3; everything in Python is a courtesy on top of it.
CREATE UNIQUE INDEX IF NOT EXISTS ux_handoffs_open_business
    ON handoffs(business_id) WHERE state <> 'CLOSED';

-- One live handoff per response: makes the create job idempotent under retry.
CREATE UNIQUE INDEX IF NOT EXISTS ux_handoffs_open_response
    ON handoffs(response_id) WHERE state <> 'CLOSED';

CREATE INDEX IF NOT EXISTS ix_handoffs_queue
    ON handoffs(state, priority, created_at);
CREATE INDEX IF NOT EXISTS ix_handoffs_sla
    ON handoffs(state, sla_ack_due_at);
CREATE INDEX IF NOT EXISTS ix_handoffs_campaign
    ON handoffs(campaign_id, created_at);
CREATE INDEX IF NOT EXISTS ix_handoffs_outcome
    ON handoffs(outcome, closed_at);
CREATE INDEX IF NOT EXISTS ix_handoffs_business
    ON handoffs(business_id, created_at);
```

Notes on the shape:

- `brief_json` is a **snapshot**, not a cache. It is what was true when the trigger fired. Research
  can change afterwards; the message Sagar was paged with must not silently rewrite itself.
  `brief_version` increments when a second response attaches (§10.6.3).
- Money is `INTEGER` rupees, not float. No currency column: this is one operator selling in INR.
- `previous_handoff_id` links a re-opened conversation to the closed one it succeeded. There is no
  `CLOSED -> IN_PROGRESS` transition; see §10.4.2.

### 10.3.2 State-machine and safety triggers

```sql
-- Illegal transitions abort at the database, per _CONTEXT.md §2.
CREATE TRIGGER IF NOT EXISTS trg_handoffs_state_transition
BEFORE UPDATE OF state ON handoffs
FOR EACH ROW
WHEN OLD.state <> NEW.state
     AND (OLD.state || '>' || NEW.state) NOT IN (
         'OPEN>ACKNOWLEDGED',
         'OPEN>CLOSED',              -- fast dismiss; API stamps ack/start/close together
         'ACKNOWLEDGED>IN_PROGRESS',
         'ACKNOWLEDGED>CLOSED',
         'IN_PROGRESS>CLOSED')
BEGIN
    SELECT RAISE(ABORT, 'illegal handoff state transition');
END;

CREATE TRIGGER IF NOT EXISTS trg_handoffs_touch
AFTER UPDATE ON handoffs
FOR EACH ROW
BEGIN
    UPDATE handoffs
       SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.id;
END;

-- Opening a handoff moves the business into HUMAN_HANDOFF (§17 lifecycle).
CREATE TRIGGER IF NOT EXISTS trg_handoffs_business_status
AFTER INSERT ON handoffs
FOR EACH ROW
BEGIN
    UPDATE businesses
       SET status = 'HUMAN_HANDOFF',
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.business_id
       AND status <> 'HUMAN_HANDOFF';
END;
```

The follow-up blocking trigger lives in §10.8.2 with the rest of the enforcement.

### 10.3.3 Columns this document adds to tables owned elsewhere

| Table | Column | Type / constraint | Purpose |
|---|---|---|---|
| `responses` | `legal_flag` | `INTEGER NOT NULL DEFAULT 0` | Set by the pre-LLM regex scan. |
| `responses` | `legal_flag_pattern` | `TEXT` | Which lexicon entry matched. |
| `responses` | `legal_flag_excerpt` | `TEXT` | 200-char window around the match. |
| `responses` | `handoff_id` | `TEXT REFERENCES handoffs(id)` | Back-link; null for digest-only responses. |
| `contact_policy` | `stop_while_handoff_open` | `INTEGER NOT NULL DEFAULT 1 CHECK (stop_while_handoff_open = 1)` | §31's stop conditions plus this one. The `CHECK` pins it to 1: the column exists to be visible and auditable, not to be turned off in v1. |
| `businesses` | (none added) | — | `status = 'HUMAN_HANDOFF'` already covers it. |

### 10.3.4 Dataclasses

```python
# radar/models.py  (handoff section)

@dataclass(slots=True)
class Handoff:
    id: str
    business_id: str
    campaign_id: str | None
    response_id: str
    outreach_message_id: str | None
    previous_handoff_id: str | None
    owner_user_id: str | None
    trigger_rule: str
    trigger_classification: str | None
    trigger_detail: str
    confidence: str                       # HIGH | MEDIUM | LOW
    confidence_pct: int | None
    priority: str                         # URGENT | HIGH | NORMAL
    state: str                            # OPEN | ACKNOWLEDGED | IN_PROGRESS | CLOSED
    outcome: str | None
    lost_reason: str | None
    brief_version: int
    response_count: int
    recommended_action: str
    recommended_channel: str | None
    recommended_by_when: str | None
    action_rule_id: str
    action_model_id: str | None
    action_prompt_version: str | None
    notify_count: int
    first_notified_at: str | None
    last_notified_at: str | None
    telegram_message_id: int | None
    snoozed_until: str | None
    sla_ack_due_at: str
    sla_progress_due_at: str
    sla_close_due_at: str
    sla_breach_count: int
    demo_scheduled_at: str | None
    demo_held_at: str | None
    proposal_sent_at: str | None
    proposal_value_inr: int | None
    won_value_inr: int | None
    created_at: str
    acknowledged_at: str | None
    started_at: str | None
    closed_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Handoff": ...
    def to_row(self) -> dict[str, object]: ...

    @property
    def is_live(self) -> bool:
        return self.state != "CLOSED"

    @property
    def is_qualified_conversation(self) -> bool:
        """§54's unit of value: a real buying signal, not a complaint or a shrug."""
        return self.trigger_rule == "CLASSIFICATION"


@dataclass(slots=True)
class HandoffBrief:
    """The §34 payload. Serialised into handoffs.brief_json and rendered three ways."""
    handoff_id: str
    generated_at: str
    # identity
    business_name: str
    city: str
    industry: str                          # HEALTHCARE | ... | OTHER
    category: str                          # HOSPITAL | MANUFACTURER | ...
    size_band: str                         # MICRO | SMALL | MEDIUM | LARGE | UNKNOWN
    website: str | None
    business_url_internal: str             # /business/<id>
    # contact
    contacts: list[BriefContact]
    # research
    opportunity_score: int
    opportunity_band: str                  # HIGH | MEDIUM | LOW
    research_confidence: str               # HIGH | MEDIUM | LOW
    potential_problem: str
    potential_solution: str
    recommended_modules: list[str]
    expected_benefit: str
    observed_facts: list[BriefFact]        # kind == OBSERVED
    inferred_facts: list[BriefFact]        # kind == INFERRED
    unknowns: list[str]                    # kind == UNKNOWN, labels only
    report_export_url: str | None          # /api/v1/report_exports/<id>
    # conversation
    messages_sent: list[BriefMessage]
    response_channel: str                  # EMAIL | WHATSAPP | PHONE | MANUAL
    response_received_at: str
    response_from: str
    response_full_text: str
    response_excerpt: str                  # <= 280 chars, for the phone
    # interpretation
    ai_classification: str
    ai_confidence: str
    ai_confidence_pct: int | None
    ai_interpretation: str                 # one sentence, from the classifier
    classifier_model_id: str
    classifier_prompt_version: str
    # action
    recommended_action: str
    recommended_channel: str | None
    recommended_by_when: str | None
    talking_points: list[str]
    # compliance context
    suppression_note: str | None           # set for COMPLAINT / LEGAL_LANGUAGE handoffs
    follow_ups_stopped: bool               # always True; rendered so it is visible
```

---

## 10.4 Lifecycle

### 10.4.1 States

| State | Means | Set by |
|---|---|---|
| `OPEN` | The system has stopped and told Sagar. Nobody has looked yet. | `create_handoff()` |
| `ACKNOWLEDGED` | Sagar has seen it. The clock for "did anyone act" starts. | `POST /api/v1/handoffs/<id>/acknowledge`, or the Telegram inline button |
| `IN_PROGRESS` | Sagar has contacted the prospect himself, or has a next step booked. | `POST /api/v1/handoffs/<id>/start` |
| `CLOSED` | Terminal. Carries a mandatory `outcome`. | `POST /api/v1/handoffs/<id>/close` |

Outcomes, all recorded on close:

| `outcome` | Definition — deliberately narrow | Required companion field |
|---|---|---|
| `DEMO_SCHEDULED` | A demo is on the calendar but has not happened yet. Close-with-follow-up: closing here is legitimate because the lead now lives in Sagar's calendar, not in this queue. | `demo_scheduled_at` |
| `PROPOSAL_SENT` | A priced proposal has gone out and is awaiting a decision. | `proposal_sent_at`, `proposal_value_inr` recommended |
| `WON` | Signed or paid. | `won_value_inr` |
| `LOST` | They said no, or chose someone else. | `lost_reason` |
| `NO_RESPONSE` | **Sagar contacted them and they went quiet.** | — |

`NO_RESPONSE` is the outcome most likely to be abused, so it is constrained: it may only be set on a
handoff whose `state` reached `IN_PROGRESS`. A handoff Sagar never worked cannot be closed
`NO_RESPONSE` — that is not the prospect going quiet, that is the operator going quiet, and it must
show up as an aging `OPEN` row rather than being laundered into a funnel statistic.

```python
def close(conn, handoff_id: str, user_id: str, outcome: str, *,
          note: str | None = None,
          value_inr: int | None = None,
          lost_reason: str | None = None) -> Handoff:
    h = get(conn, handoff_id)
    if outcome == "NO_RESPONSE" and h.started_at is None:
        raise HandoffError(
            "NO_RESPONSE requires the handoff to have reached IN_PROGRESS. "
            "An untouched lead is aging, not unresponsive."
        )
    ...
```

### 10.4.2 Transitions

```
                  acknowledge                start                  close(outcome)
   [OPEN] ──────────────────► [ACKNOWLEDGED] ──────► [IN_PROGRESS] ──────────────► [CLOSED]
      │                              │                                                 ▲
      │                              └─────────────── close(outcome) ──────────────────┤
      │                                                                                │
      └──────────────────────── close(outcome)  "fast dismiss" ────────────────────────┘

   No CLOSED -> * transition exists.
```

- **Fast dismiss** (`OPEN -> CLOSED`) exists for misclassified junk. The endpoint stamps
  `acknowledged_at = started_at = closed_at = now` in one statement so the `CHECK` constraints hold,
  and writes an `audit_log` row with `action = 'HANDOFF_FAST_DISMISS'`. `NO_RESPONSE` is still
  rejected on this path by the rule above.
- **No re-open.** A closed handoff stays closed. If the prospect writes again, the classifier
  produces a new `responses` row, `evaluate_triggers` fires again, and `create_handoff()` inserts a
  **new** row with `previous_handoff_id` pointing at the old one. The partial unique index permits
  this because the old row is `CLOSED`. Consequence for the funnel: a business can contribute more
  than one handoff over its life, so every §54 count is `COUNT(DISTINCT business_id)`, never
  `COUNT(*)`.
- **Mis-close correction** uses the same path: `POST /api/v1/handoffs` with
  `{"business_id": ..., "response_id": ..., "previous_handoff_id": ...}` and
  `trigger_rule = 'MANUAL'`.

Every transition writes an `audit_log` row (see `11-audit-architecture.md`):

```json
{
  "id": "aud_01JSAMPLE0000000000000001",
  "at": "2026-08-27T04:11:09Z",
  "actor_user_id": "usr_sagar",
  "actor_kind": "HUMAN",
  "action": "HANDOFF_STATE_CHANGE",
  "entity_table": "handoffs",
  "entity_id": "hnd_01JSAMPLE0000000000000001",
  "detail_json": {
    "from": "OPEN",
    "to": "ACKNOWLEDGED",
    "via": "telegram_callback",
    "sla_ack_due_at": "2026-08-27T08:12:00Z",
    "sla_ack_met": true
  }
}
```

Free-text notes are `action = 'HANDOFF_NOTE'` rows on the same entity. There is no `handoff_notes`
table; the audit log is already append-only and already the place a note belongs.

### 10.4.3 SLA timers

Three clocks per handoff, computed at insert and stored, so a config change never rewrites history.

| Priority | Acknowledge within | In progress within | Close within |
|---|---|---|---|
| `URGENT` | 30 minutes | 2 hours | 24 hours |
| `HIGH` | 4 working hours | 24 working hours | 7 days |
| `NORMAL` | 24 working hours | 3 days | 14 days |

```yaml
handoff:
  sla:
    URGENT: {ack_minutes: 30,   progress_minutes: 120,  close_hours: 24,  clock: WALL}
    HIGH:   {ack_minutes: 240,  progress_minutes: 1440, close_hours: 168, clock: WAKING}
    NORMAL: {ack_minutes: 1440, progress_minutes: 4320, close_hours: 336, clock: WAKING}
  waking_hours:
    tz: "Asia/Kolkata"
    start: "07:30"
    end: "22:00"
```

Clock semantics:

- `WALL` — real elapsed time. Nights and Sundays count. Only `URGENT` uses it, because a complaint
  or a legal notice runs on the sender's clock, not Sagar's.
- `WAKING` — minutes elapsed inside `waking_hours` only. A `HIGH` handoff created at 21:50 IST is
  due for acknowledgement at 10:20 the next morning, not at 01:50.

```python
def waking_deadline(start: datetime, minutes: int, cfg: Config) -> datetime:
    """Add `minutes` of waking time to `start`, skipping the quiet window.

    Without this an evening lead is 'breached' before Sagar's alarm goes off, and
    the escalation ladder in sweep_slas() spends the night shouting at a sleeping man.
    """
```

### 10.4.4 What happens when an SLA expires

`handoff_sla_sweep` runs every 5 minutes (`14-background-jobs.md`). Breaching a clock never changes
`state` and never changes `outcome`. It changes only how loudly the system asks.

| Breach | Effect |
|---|---|
| 1st (any clock) | `sla_breach_count = 1`. Re-notify on Telegram with a `SLA BREACH` prefix, and force `disable_notification: false` even if the item was previously delivered silently. |
| 2nd (one full clock interval after the 1st) | `sla_breach_count = 2`. Email-to-self fires **in addition** to Telegram, regardless of whether Telegram reported success — this is the point where "my phone was on silent" stops being a plausible explanation. |
| 3rd and later | `sla_breach_count += 1`, at most once per 24h per handoff. The handoff pins to the top of `/handoffs` with an age badge, appears in the daily digest header, and increments the `Aging handoffs` tile on the dashboard (§10.9.4). No further pages. |
| Never | Auto-close, auto-reply, auto-resume of follow-ups, or auto-reassignment. |

```python
@dataclass(slots=True)
class SweepResult:
    checked: int
    newly_breached: list[str]      # handoff ids
    renotified: list[str]
    emailed: list[str]
    skipped_snoozed: list[str]


def sweep_slas(conn, now: datetime, cfg: Config) -> SweepResult:
    """Escalate handoffs nobody has touched. Idempotent; safe to run twice a minute."""
```

Breach query:

```sql
SELECT id, priority, state, sla_breach_count, sla_last_breach_at
  FROM handoffs
 WHERE state <> 'CLOSED'
   AND (snoozed_until IS NULL OR snoozed_until <= :now)
   AND (
        (state = 'OPEN'          AND sla_ack_due_at      <= :now) OR
        (state = 'ACKNOWLEDGED'  AND sla_progress_due_at <= :now) OR
        (state <> 'CLOSED'       AND sla_close_due_at    <= :now)
       )
   AND (sla_last_breach_at IS NULL OR sla_last_breach_at <= :breach_cooloff)
 ORDER BY CASE priority WHEN 'URGENT' THEN 0 WHEN 'HIGH' THEN 1 ELSE 2 END,
          created_at;
```

**Snooze.** `POST /api/v1/handoffs/<id>/snooze {"until": "..."}` sets `snoozed_until` and suppresses
notification only. Maximum snooze is 72 hours (`handoff.max_snooze_hours`), `URGENT` cannot be
snoozed at all, and every snooze writes an audit row. Snoozing is not closing, and the aging badge
keeps counting from `created_at`.

**Aging review.** There is no auto-close, so `/handoffs?state=OPEN&older_than=30d` renders a bulk
review screen where Sagar closes stale rows by hand, one outcome each. That screen is the only place
a multi-row close exists, and it still refuses `NO_RESPONSE` for untouched rows.

---

## 10.5 The handoff brief

### 10.5.1 §34's field list, mapped

Every field §34 demands, with the query that fills it and where it renders. `T` = Telegram, `W` =
web view, `E` = email fallback, `D` = digest.

| §34 field | `HandoffBrief` field | Source | T | W | E | D |
|---|---|---|---|---|---|---|
| Business | `business_name` | `businesses.name` | yes | yes | yes | yes |
| City | `city` | `businesses.city` | yes | yes | yes | yes |
| Category | `industry`, `category` | `businesses.industry`, `businesses.category` | yes | yes | yes | no |
| Contact | `contacts[]` | `business_contacts` where not suppressed | yes (best 2) | all | all | no |
| Research report | `observed_facts`, `inferred_facts`, `unknowns`, `report_export_url` | `research_findings` + `finding_sources` + `sources` | top 3 OBSERVED | all, expandable | top 5 | no |
| Opportunity | `opportunity_score`, `opportunity_band`, `potential_problem`, `potential_solution`, `expected_benefit` | `opportunities` | score + solution | all | all | score |
| Recommended modules | `recommended_modules` | `opportunity_modules` | yes | yes | yes | no |
| Messages sent | `messages_sent[]` | `outreach_messages` + `outreach_events` | count + last date | full table | full list | no |
| Full response | `response_full_text`, `response_excerpt` | `responses.body_text` | excerpt (280) | full | full | no |
| AI interpretation | `ai_interpretation` | `responses.interpretation` | yes | yes | yes | no |
| Confidence | `ai_confidence`, `ai_confidence_pct` | `responses.confidence`, `.confidence_pct` | yes | yes | yes | no |
| Recommended next action | `recommended_action`, `talking_points`, `recommended_by_when` | §10.7 | action only | action + points | action + points | no |

Fact rendering obeys invariant 4 in spirit but not in letter: invariant 4 governs what an
**outbound message** may claim. The brief is an internal screen for the operator, so it does show
`UNKNOWN` items — under a heading that says exactly what they are ("Not verified — do not assert
these"). Knowing what the system could not find out is the difference between Sagar sounding
informed and Sagar sounding like he read a scraped listing.

### 10.5.2 Assembly

```python
def build_brief(conn, handoff_id: str, *, cfg: Config) -> HandoffBrief:
    """Assemble the §34 payload once, at trigger time, from live SQL.

    Every number here is a SELECT over real rows (invariant 5). A field with no data
    renders as an em dash downstream; nothing in this function substitutes a zero.
    """
```

Facts are ordered by usefulness to a human on a phone, not by database order:

```sql
SELECT f.id, f.kind, f.label, f.detail, f.confidence,
       s.name AS source_name, s.url AS source_url, s.source_type, fs.checked_at
  FROM research_findings f
  LEFT JOIN finding_sources fs ON fs.finding_id = f.id
  LEFT JOIN sources s          ON s.id = fs.source_id
 WHERE f.business_id = :business_id
   AND f.kind = 'OBSERVED'
 ORDER BY CASE f.confidence WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END,
          f.weight DESC
 LIMIT 12;
```

Storage: `brief_json = json.dumps(asdict(brief), ensure_ascii=False)`, written in the same
transaction as the `handoffs` insert. If assembly raises, the transaction rolls back and the create
job retries — a handoff with a half-built brief is worse than a handoff that arrives 60 seconds late.

### 10.5.3 The Telegram message (SAMPLE)

Designed for the 9pm case: standing in a kitchen, one hand, poor light. Constraints that follow from
that and are therefore rules, not suggestions:

1. **The first line must contain the decision.** Not a banner, not the system name — what happened
   and how hot it is. Telegram's notification preview shows roughly the first 100 characters and
   that is often all that gets read.
2. **The business name and city are on line 2.** Sagar recognises leads by name, not by id.
3. **The prospect's own words appear above the machine's opinion.** Always. The AI interpretation is
   a hint; the quote is the fact.
4. **No emoji.** Text prefixes (`URGENT`, `SLA BREACH`) survive copy-paste into email, are greppable
   in the log line that mirrors every send, and do not render as tofu on a desktop client. This
   deliberately differs from `option_chain_reader`'s alerting, where an emoji encodes a numeric bias
   band that has no equivalent here.
5. **Under 15 short lines above the buttons.** Anything longer is a web-view job.
6. `parse_mode: "HTML"`, `disable_web_page_preview: true` — a link preview of a prospect's website
   pushes the buttons off the first screen.

Rendered `SAMPLE` for the §35 example:

```
HUMAN ACTION REQUIRED - DEMO REQUESTED

ABC Industries - Dhule
Manufacturing / Manufacturer - Size MEDIUM
Opportunity 91 (HIGH) - Research confidence MEDIUM

They wrote (22 Aug, 18:41):
"Yes, please show us what you can provide."

Read as DEMO_REQUESTED, confidence HIGH (92%)

Fit: Manufacturing Management Platform
Modules: Inventory, Production, Purchasing, Sales,
Quality, Reports

Contact: info@abc-industries.example  (business)
Sent so far: 1 email, 22 Aug 09:12 IST, delivered

RECOMMENDED (for you to do, not done):
Reply by email within 24h with two demo slots this
week. Lead with production and inventory visibility -
those are the OBSERVED gaps, not guesses.

Automated follow-ups to this business are stopped.

[ Open brief ]  [ Acknowledge ]  [ Snooze 12h ]
```

SAMPLE data only. `abc-industries.example` is a reserved example domain and is never a real contact.

Source form (HTML entities escaped by `_escape()`, same helper shape as
`option_chain_reader/oc/outputs/telegram.py`):

```python
def render_telegram(brief: HandoffBrief, *, sla_breach: bool = False) -> str:
    """One screen. The decision on line 1, the prospect's words above ours."""
    head = "HUMAN ACTION REQUIRED"
    if sla_breach:
        head = "SLA BREACH - " + head
    if brief.ai_classification == "COMPLAINT":
        head = "URGENT - COMPLAINT RECEIVED"
    lines = [
        f"<b>{head} - {brief.ai_classification.replace('_', ' ')}</b>",
        "",
        f"<b>{_escape(brief.business_name)}</b> - {_escape(brief.city)}",
        f"{brief.industry.title()} / {brief.category.title()} - Size {brief.size_band}",
        f"Opportunity <b>{brief.opportunity_score}</b> ({brief.opportunity_band})"
        f" - Research confidence {brief.research_confidence}",
        "",
        f"They wrote ({_short_dt(brief.response_received_at)}):",
        f"<i>\"{_escape(brief.response_excerpt)}\"</i>",
        "",
        f"Read as {brief.ai_classification}, confidence "
        f"{brief.ai_confidence} ({brief.ai_confidence_pct}%)",
        "",
        f"Fit: {_escape(brief.potential_solution)}",
        f"Modules: {', '.join(brief.recommended_modules)}",
        "",
        f"Contact: {_escape(brief.contacts[0].value)}  ({brief.contacts[0].kind.lower()})",
        _messages_line(brief.messages_sent),
        "",
        "<b>RECOMMENDED (for you to do, not done):</b>",
        _escape(brief.recommended_action),
        "",
        "<i>Automated follow-ups to this business are stopped.</i>",
    ]
    return "\n".join(lines)
```

Inline keyboard:

```json
{
  "inline_keyboard": [
    [
      {"text": "Open brief",  "url": "https://radar.example/handoffs/hnd_01JSAMPLE0000000000000001"},
      {"text": "Acknowledge", "callback_data": "hoack:hnd_01JSAMPLE0000000000000001"}
    ],
    [
      {"text": "Snooze 12h",  "callback_data": "hosnz:hnd_01JSAMPLE0000000000000001:12"}
    ]
  ]
}
```

`callback_data` is capped at 64 bytes by Telegram, which a `hnd_` id plus a 5-char verb fits. The
callback handler:

- rejects any `callback_query` whose `from.id` is not the configured operator id — the bot token is
  a bearer credential and an inline button is a state-changing endpoint (§47);
- is idempotent: acknowledging an already-acknowledged handoff returns success and re-renders;
- edits the original message in place via `editMessageText` rather than sending a new one, so the
  chat holds one message per handoff, not a thread of five.

Callback transport in v1 is `getUpdates` long-polling from a single `telegram_poll` job with a
lease, because it needs no inbound port — and on this deploy target there is no inbound port to be
had. `_CONTEXT.md` §2 binds waitress to `127.0.0.1` with no VPS and no public hostname, so Telegram
has nowhere to POST; this is the transport permanently, not until DNS is configured. The webhook
path (`POST /api/v1/notifications/telegram/callback`, secret-token header verified) is built the
same way and stays opt-in via `notify.telegram.mode: webhook`, for a host that has a public HTTPS
URL. `13-api-endpoints.md` §13.13.2 registers it on the same terms.

The `COMPLAINT` and `LEGAL_LANGUAGE` variant is a different message, because opportunity scores and
module lists are irrelevant and slightly grotesque in that context:

```
URGENT - COMPLAINT RECEIVED

XYZ Traders - Nashik

They wrote (23 Aug, 11:02):
"Who gave you my email? Remove me and do not
contact this company again."

This business is now permanently suppressed.
All channels blocked. This cannot be undone from
the app.

What we sent: 1 email, 21 Aug 10:04 IST, from
outreach@radar-sample.example, campaign
cmp_01JSAMPLE0000000000000001

RECOMMENDED (for you to do, not done):
Reply personally within 24h. Confirm removal,
name the source the address came from (business
listing, captured 19 Aug), and offer erasure of
the stored record.

[ Open brief ]  [ Acknowledge ]
```

SAMPLE. No snooze button on an `URGENT` handoff.

### 10.5.4 The web view: `/handoffs/<handoff_id>`

```
+--------------------------------------------------------------------------------+
| business_radar                        Campaigns  Outreach  Handoffs*  Settings  |
+--------------------------------------------------------------------------------+
| < All handoffs                                                                  |
|                                                                                 |
|  ABC Industries                                    [ DEMO REQUESTED ]  [ OPEN ] |
|  Dhule - Manufacturing / Manufacturer - MEDIUM     Opened 22 Aug 18:42 (14h ago)|
|  Opportunity 91 HIGH   Research confidence MEDIUM  Ack due 23 Aug 10:20         |
|                                                                                 |
|  [ Acknowledge ]  [ Mark in progress ]  [ Close... ]  [ Snooze 12h ]            |
+--------------------------------------------------------------------------------+
|                                                                                 |
|  THEIR RESPONSE                                          via EMAIL, 22 Aug 18:41|
|  From: rajesh@abc-industries.example                                            |
|  +--------------------------------------------------------------------------+  |
|  | Yes, please show us what you can provide.                                 |  |
|  |                                                                           |  |
|  | -- Rajesh, ABC Industries                                                 |  |
|  +--------------------------------------------------------------------------+  |
|  AI read: DEMO_REQUESTED   confidence HIGH (92%)                                |
|  "Direct, unqualified request for a demonstration. No pricing or timing         |
|   constraint stated."                                                           |
|  gemini-2.5-flash / classify.v3     [ Disagree with this reading ]              |
|                                                                                 |
+--------------------------------------------------------------------------------+
|  RECOMMENDED NEXT ACTION                        this is advice, nothing was sent|
|  +--------------------------------------------------------------------------+  |
|  | Reply by email within 24h with two demo slots this week.                  |  |
|  |                                                                           |  |
|  | Talking points                                                            |  |
|  |  - Production and inventory visibility across the two units (OBSERVED)    |  |
|  |  - Purchase-to-dispatch traceability, which their tender page implies     |  |
|  |    they already report on manually (INFERRED - hedge this)                |  |
|  |  - Do not claim anything about their current software. UNKNOWN.           |  |
|  |                                                                           |  |
|  | rule R-DEMO-EMAIL-01 - phrasing by gemini-2.5-flash / handoff_action.v2   |  |
|  +--------------------------------------------------------------------------+  |
|  [ Copy to clipboard ]   [ Open mail client ]   (no send button exists here)    |
+--------------------------------------------------------------------------------+
|  CONTACT                                                                        |
|  info@abc-industries.example      business email   source: company website 19 Aug|
|  +91 XXXXX XXXXX                  listed phone     source: business listing      |
|  Opt-out status: none    Suppressions: none    Contact policy: HUMAN_APPROVAL   |
+--------------------------------------------------------------------------------+
|  OPPORTUNITY                                                            score 91|
|  Potential problem   Multi-unit production tracked on spreadsheets per unit;     |
|                      no consolidated dispatch or quality record.                 |
|  Potential solution  Manufacturing Management Platform                           |
|  Modules             Inventory - Production - Purchasing - Sales - Quality -     |
|                      Reports                                                     |
|  Expected benefit    Single view of stock and production across units; audit     |
|                      trail for dispatch and quality.                             |
+--------------------------------------------------------------------------------+
|  RESEARCH BASIS                                             [ Full report .html ]|
|  OBSERVED (3)                                                                    |
|   - Two manufacturing units listed at different addresses in Dhule MIDC          |
|     source: MIDC directory listing - checked 19 Aug - HIGH        [ open ]       |
|   - Careers page advertises "Store Keeper" and "Production Supervisor"           |
|     source: abc-industries.example/careers - checked 19 Aug - HIGH [ open ]      |
|   - No customer login or order-tracking portal on the website                    |
|     source: abc-industries.example - checked 19 Aug - MEDIUM      [ open ]       |
|  INFERRED (2)                        hedge these in conversation                 |
|   - Dispatch coordination likely manual across units - MEDIUM                    |
|   - Quality records likely paper-based - LOW                                     |
|  NOT VERIFIED (2)                    do not assert these                         |
|   - Current ERP or accounting software in use                                    |
|   - Annual turnover                                                              |
+--------------------------------------------------------------------------------+
|  WHAT WE SENT                                                                   |
|  22 Aug 09:12  EMAIL  msg_01JSAMPLE...  DELIVERED  approved by Sagar 22 Aug 09:05|
|                Subject: A possible digital operations solution for ABC Industries|
|                [ view exact message sent ]                                      |
|  Follow-ups: STOPPED - reason: open handoff hnd_01JSAMPLE...  since 22 Aug 18:42 |
+--------------------------------------------------------------------------------+
|  ACTIVITY                                                                       |
|  22 Aug 18:42  handoff opened          trigger CLASSIFICATION / DEMO_REQUESTED   |
|  22 Aug 18:42  telegram notified       message_id 4812                          |
|  23 Aug 10:20  SLA breach (ack)        re-notified, audible                     |
+--------------------------------------------------------------------------------+
```

Colour discipline follows §51: green only on `INTERESTED`/`VERIFIED`/`WON` badges, yellow on the SLA
and aging badges, red on `COMPLAINT`/suppression/blocked, blue on research panels. The state badge
(`OPEN`/`ACKNOWLEDGED`/`IN_PROGRESS`) is neutral grey — an open handoff is neither good nor bad, it
is work.

### 10.5.5 The queue: `/handoffs`

```
+--------------------------------------------------------------------------------+
|  HANDOFFS                                                                       |
|  [ Open 4 ]  [ Acknowledged 1 ]  [ In progress 2 ]  [ Closed ]  [ All ]         |
|  City: All v   Priority: All v   Trigger: All v   Older than: -- v              |
+--------------------------------------------------------------------------------+
| ! URGENT  XYZ Traders        Nashik    COMPLAINT        opened 2h   ack OVERDUE |
|   HIGH    ABC Industries     Dhule     DEMO_REQUESTED   opened 14h  ack OVERDUE |
|   HIGH    Sunrise Diagnostics Jalgaon  PRICE_REQUESTED  opened 5h   ack 3h left |
|   NORMAL  Model High School  Shirpur   INTERESTED       opened 1d   ack 4h left |
|   NORMAL  Patil Motors       Dhule     LOW_CONFIDENCE   opened 2d   ack OVERDUE |
+--------------------------------------------------------------------------------+
```

SAMPLE rows. Sort order is fixed and not user-configurable: `URGENT` first, then overdue-by-most,
then oldest. A queue that can be sorted by "newest" is a queue that hides the thing you are avoiding.

---

## 10.6 Notification delivery

### 10.6.1 Channels

| Channel | Role | Module | Failure behaviour |
|---|---|---|---|
| Telegram bot | Primary. Same pattern as `option_chain_reader/oc/outputs/telegram.py`: `requests.Session`, `sendMessage`, 10s timeout, HTML parse mode, failures logged and never raised into the caller. | `radar/notify.py` | Retries 3 times with backoff (0s, 30s, 120s) inside the `handoff_notify` job. On exhaustion the job fails, `job_runs` records it, the email fallback fires, and the handoff stays `OPEN` with `notify_count = 0`. |
| Email-to-self | Fallback and second-breach escalation. Plain text plus a minimal HTML part, to `ALERT_EMAIL_TO`. | `radar/notify.py` | Logged; the handoff still stands. |
| Daily digest | Non-urgent roll-up at 09:00 IST, and the §43 daily report. | `radar/notify.py` + `radar/report.py` | Missing a digest loses nothing: every item in it is already a row in `/handoffs`. |

**`radar/notify.py` is a new module and is deliberately not inside `radar/channels/`.** Everything
under `radar/channels/` addresses a prospect; everything in `radar/notify.py` addresses Sagar. Keeping
them in separate packages means an accidental import can never route a handoff alert to a business
contact, and a `grep` for "who can send to a prospect" has exactly one answer. A unit test asserts
`radar.notify` does not import `radar.channels` and vice versa.

```python
# radar/notify.py — signatures

class TelegramNotifier:
    def __init__(self, cfg: Config) -> None: ...
    @property
    def configured(self) -> bool: ...
    def send(self, text: str, *, silent: bool = False,
             reply_markup: dict | None = None) -> int | None:   # message_id or None
    def edit(self, message_id: int, text: str,
             reply_markup: dict | None = None) -> bool: ...

class EmailSelfNotifier:
    def send(self, subject: str, text: str, html: str | None = None) -> bool: ...

def notify_handoff(conn, handoff_id: str, cfg: Config, *,
                   reason: str = "CREATED") -> NotifyResult: ...
def send_digest(conn, day: date, cfg: Config) -> NotifyResult: ...
```

### 10.6.2 The self-notification identity must not be the outreach identity

The email fallback sends through a **different** SMTP identity and a **different** domain from cold
outreach. Reasons, all concrete:

- `_CONTEXT.md` §4 puts cold outreach on a separate sending domain with its own reputation. Mixing
  operational alerts into that stream means a deliverability problem in one silences the other.
- If the outreach provider terminates the account for AUP reasons, the alerting channel must survive
  that, or the first thing Sagar loses is the ability to be told about it.
- Self-mail needs no unsubscribe footer, no suppression check, and no policy engine pass; outreach
  needs all three. Sharing a code path invites one of those checks to be skipped.

```yaml
notify:
  telegram:
    enabled: true
    mode: polling            # polling | webhook
    # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_OPERATOR_ID in config/.env
    heartbeat: true
  email_self:
    enabled: true
    # NOTIFY_SMTP_HOST / _PORT / _USER / _PASS / ALERT_EMAIL_TO in config/.env
    # Deliberately NOT the outreach SMTP credentials. See 07-email-integration.md.
    from_name: "business_radar"
  digest:
    enabled: true
    at: "09:00"
    tz: "Asia/Kolkata"
```

### 10.6.3 De-duplication

Five rules, ordered from strongest to weakest.

| # | Rule | Enforced by |
|---|---|---|
| 1 | One live handoff per business. A second triggering response on a business that already has an `OPEN`/`ACKNOWLEDGED`/`IN_PROGRESS` handoff **attaches** to it. | `ux_handoffs_open_business` partial unique index |
| 2 | An attach does not page again. It increments `response_count`, appends the new response to `brief_json`, bumps `brief_version`, and **edits** the existing Telegram message (`telegram_message_id`) so the chat still holds one message for this lead. | `attach_response()` |
| 3 | Exception to rule 2: if the attach **raises the priority** (`NORMAL -> HIGH`, anything `-> URGENT`), one new page is allowed, at most one per escalation step. A prospect who says "interested" then "actually can you call me today" deserves a second buzz; a prospect who sends three paragraphs in a row does not. | `attach_response()` |
| 4 | Per-handoff rate cap: `notify.max_pages_per_handoff` (default 4 = initial + up to 3 breach escalations) and `notify.dedupe_window_minutes` (default 15). Two pages for the same handoff inside the window collapse into one. | `notify_handoff()` |
| 5 | Global cap: `notify.max_pages_per_hour` (default 10). Beyond it, further handoffs are created normally but their notification is replaced by one batched message ("6 more handoffs opened in the last hour - open /handoffs"). This exists for the day a mail loop or a classifier regression fires 200 triggers at 3am. | `notify_handoff()` |

```python
def attach_response(conn, handoff_id: str, response_id: str,
                    decision: TriggerDecision) -> AttachResult:
    """Fold a second reply into a live handoff instead of opening a second one.

    Without this, a prospect who replies twice in an evening pages Sagar twice for
    one conversation, and the funnel counts one lead as two.
    """
```

```sql
-- The create path, written so a job retry cannot double-insert.
INSERT INTO handoffs (id, business_id, response_id, ...)
SELECT :id, :business_id, :response_id, ...
 WHERE NOT EXISTS (
       SELECT 1 FROM handoffs
        WHERE business_id = :business_id AND state <> 'CLOSED')
   AND NOT EXISTS (
       SELECT 1 FROM handoffs
        WHERE response_id = :response_id);
```

Note the second `NOT EXISTS` has no `state` filter: a response that already produced a handoff, even
a closed one, never produces a second automatic handoff. Re-opening is a `MANUAL` act (§10.4.2).

### 10.6.4 Quiet hours

```yaml
notify:
  quiet_hours:
    enabled: true
    tz: "Asia/Kolkata"
    start: "22:00"
    end: "07:30"
```

| Priority | Inside quiet hours | Outside |
|---|---|---|
| `URGENT` | **Ignores quiet hours. Audible.** | Audible |
| `HIGH` | Delivered immediately with `disable_notification: true` — the message is on the phone, the phone stays silent — then re-sent audibly at `quiet_hours.end` if still `OPEN`. | Audible |
| `NORMAL` | Delivered silently, and rolled into the 09:00 digest. | Delivered silently, and in the digest |

The argument for each half, stated because someone will want to change it later:

- **Urgent items break quiet hours.** A complaint or a legal-language reply runs on a clock Sagar
  does not control. The downside of waking him is one bad night. The downside of a nine-hour delay
  is a WABA quality strike, an ESP abuse escalation, or a DPDP grievance that now has "and they
  ignored it for a day" attached. That is not a close call. The `URGENT` band is narrow on purpose
  precisely so this override is rare — a demo request, however exciting, is not urgent.
- **High and normal items still get delivered, just silently.** Delivering-but-silent beats
  queueing, because a queue is a thing that can be lost: if the digest job dies overnight, a queued
  page vanishes, whereas a silently-delivered message is already sitting in the chat. The
  re-notify-at-07:30 pass is a courtesy on top of a message that already exists, not the only
  delivery attempt.
- **Nothing is ever dropped.** Quiet hours change sound, never delivery.

`URGENT` also skips the global hourly cap (rule 5 above): the batching message says how many
`NORMAL`/`HIGH` items were collapsed, and pages each `URGENT` one individually.

### 10.6.5 Daily digest

Runs at 09:00 IST as the `handoff_digest` job; the same query also feeds the §43 DAILY BUSINESS
OPPORTUNITY REPORT.

```
business_radar - 27 Aug 2026

NEEDS YOU
  2 open handoffs, 1 overdue
  - ABC Industries, Dhule - DEMO_REQUESTED - opened 14h ago - ACK OVERDUE
  - Model High School, Shirpur - INTERESTED - opened 1d ago

IN FLIGHT
  1 demo scheduled (29 Aug), 1 proposal awaiting decision

YESTERDAY
  Replies received 4 - qualified conversations 2 - not interested 1 -
  wrong contact 1
  Soft replies not paged: 1 MORE_INFORMATION (Patil Motors, Dhule),
  1 LATER (Shree Bakery, Nashik - not before 15 Sep)

RESEARCH
  Discovered 31 - qualified 12 - awaiting your verification 9
  Top new opportunity: Sunrise Diagnostics, Jalgaon - 88 - Diagnostic
  Operations Platform

  Open /handoffs
```

SAMPLE. Ordering is the point: what needs a human is first, what is in flight is second, and the
research volume — the biggest number on the page — is last. See §10.9.4.

---

## 10.7 Recommended next action

### 10.7.1 Generation

Two layers, deterministic first.

**Layer 1 — rule table.** A lookup keyed on `(trigger_classification, best_contact_kind,
opportunity_band, size_band)` producing the action skeleton, the channel and the by-when. Stored in
`config/handoff_actions.yaml` so Sagar can edit the playbook without touching Python, and the
matched `rule_id` is written to `handoffs.action_rule_id` for every row.

```yaml
# config/handoff_actions.yaml  (extract)
rules:
  - id: R-DEMO-EMAIL-01
    when: {classification: DEMO_REQUESTED, contact: EMAIL}
    channel: EMAIL
    by_when_hours: 24
    skeleton: >-
      Reply by email within 24h with two demo slots this week. Lead with the
      OBSERVED operational gaps, not the score.
  - id: R-DEMO-PHONE-01
    when: {classification: DEMO_REQUESTED, contact: PHONE}
    channel: PHONE
    by_when_hours: 24
    skeleton: >-
      Call during business hours and offer to send a calendar invite by email
      afterwards. Do not send a WhatsApp template - no opt-in on record.
  - id: R-PRICE-01
    when: {classification: PRICE_REQUESTED}
    channel: EMAIL
    by_when_hours: 24
    skeleton: >-
      Do not quote a number from the report. Reply with an indicative range tied
      to module count and ask two scoping questions before pricing.
  - id: R-MEETING-01
    when: {classification: MEETING_REQUESTED}
    channel: EMAIL
    by_when_hours: 12
    skeleton: >-
      Offer three concrete slots in the next five working days and confirm the
      city so travel is not assumed.
  - id: R-INTEREST-SOFT-01
    when: {classification: INTERESTED}
    channel: EMAIL
    by_when_hours: 48
    skeleton: >-
      Reply personally with one specific observation and a single question.
      Do not attach a brochure.
  - id: R-COMPLAINT-01
    when: {trigger_rule: COMPLAINT}
    channel: MANUAL
    by_when_hours: 24
    skeleton: >-
      Reply personally within 24h. Confirm removal, name where the contact came
      from and when it was captured, and offer erasure of the stored record.
  - id: R-LEGAL-01
    when: {trigger_rule: LEGAL_LANGUAGE}
    channel: MANUAL
    by_when_hours: 12
    skeleton: >-
      Do not reply on substance before reading the full message and the outreach
      audit trail. Confirm suppression is in place, then respond factually.
  - id: R-LOWCONF-01
    when: {trigger_rule: LOW_CONFIDENCE}
    channel: MANUAL
    by_when_hours: 48
    skeleton: >-
      Read the reply yourself and set the correct classification. The classifier
      was not confident enough to act on.
  - id: R-FALLBACK-01
    when: {}
    channel: MANUAL
    by_when_hours: 48
    skeleton: Read the reply and decide. No rule matched this combination.
```

**Layer 2 — phrasing and talking points.** `gemini-2.5-flash` receives the skeleton plus the brief's
`observed_facts`, `inferred_facts` and `unknowns`, and returns strict JSON: a one-sentence action and
2-4 talking points. Its job is to make the advice specific to this business, not to decide the
strategy — the strategy came from layer 1.

```python
NEXT_ACTION_PROMPT_VERSION = "handoff_action.v2"

def recommend_next_action(conn, brief: HandoffBrief, cfg: Config) -> RecommendedAction:
    """Turn the matched playbook rule into advice about this specific business.

    Layer 1 (the rule) always produces a usable answer. The model only rewrites it.
    If the API is down, slow or returns unparseable JSON, the rule skeleton ships
    verbatim - a handoff must never wait on an LLM.
    """
```

```json
{
  "action": "Reply by email within 24h with two demo slots this week. Lead with production and inventory visibility - those are the OBSERVED gaps, not guesses.",
  "talking_points": [
    "Two units listed at different MIDC addresses - ask how stock moves between them (OBSERVED)",
    "Careers page advertises Store Keeper and Production Supervisor - staffed but manual (OBSERVED)",
    "Dispatch coordination is probably manual across units - hedge this, it is INFERRED",
    "Say nothing about their current software. UNKNOWN."
  ]
}
```

SAMPLE. Every generation writes `action_model_id`, `action_prompt_version`, `action_input_tokens` and
`action_output_tokens` onto the `handoffs` row, per `_CONTEXT.md` §2: never call an LLM without
recording model, prompt version and token counts.

Validation before storage: the returned action must not contain a URL, must not exceed 400
characters, and must not contain any of `{{`, `Subject:`, `Dear ` or `Regards,` — those are the
shape of a drafted message, and a drafted message is not what this field is for. A validation
failure falls back to the rule skeleton and logs an error.

### 10.7.2 The hard constraint: a recommendation is not an action

| Enforcement | Mechanism |
|---|---|
| Type | `RecommendedAction` is a frozen dataclass whose every field is `str` or `list[str]`. It holds no draft id, no contact id, no callable, no channel handle. `recommended_channel` is an advisory enum value, not a route. |
| Import boundary | `radar/handoff.py` and `radar/notify.py` must not import `radar/channels/*` or `radar/messages.py`. A test asserts this by walking the module AST for `Import`/`ImportFrom` nodes. |
| Data | Generating a recommendation does not create an `outreach_drafts` row. It cannot: the draft generator refuses while a live handoff exists (§10.8). |
| Send path | Unchanged and unreachable from here. Per invariant 1, `send()` requires an `approval_id` from `outreach_approvals`; nothing in the handoff subsystem creates approvals. |
| UI | The `/handoffs/<id>` action panel has `Copy to clipboard` and `Open mail client` (a `mailto:` link, which hands the message to Sagar's own client and sends nothing). There is no send control on this screen, by the same reasoning §19 uses to keep a send button off the raw research result. |

A blunt restatement for the person tempted to add "just one auto-reply for demo requests": the
system's answer to a prospect who is ready to buy is to get out of the way. Automating that reply
would put an LLM in charge of the single highest-value message the business ever sends, at the exact
moment a human is most obviously required.

---

## 10.8 Follow-ups stop while a handoff is open

### 10.8.1 The rule

While any handoff for a business is in `OPEN`, `ACKNOWLEDGED` or `IN_PROGRESS`:

- no `outreach_drafts` row may be created for that business;
- no existing draft may move to `PENDING_APPROVAL` or `APPROVED`;
- no `outreach_messages` row may reach `QUEUED` or `SENT`;
- the follow-up scheduler must not select the business at all.

Closing a handoff does not automatically resume follow-ups. `businesses.status` stays
`HUMAN_HANDOFF` after close, and only an explicit operator action on `/business/<id>` returns it to
`CONTACT_READY`. A business that reached a human conversation is out of the automated pool until a
human says otherwise.

### 10.8.2 Five enforcement layers

**Layer 1 — the scheduler query.** The follow-up job simply cannot see the business.

```sql
-- radar/jobs.py :: select_follow_up_candidates
SELECT b.id
  FROM businesses b
  JOIN contact_policy cp ON cp.business_id = b.id
 WHERE b.status IN ('CONTACTED','RESPONDED')
   AND NOT EXISTS (SELECT 1 FROM handoffs h
                    WHERE h.business_id = b.id AND h.state <> 'CLOSED')
   AND NOT EXISTS (SELECT 1 FROM suppressions s
                    WHERE s.business_id = b.id AND s.active = 1)
   AND cp.stop_while_handoff_open = 1
   AND cp.follow_ups_sent < cp.max_follow_ups
   AND (cp.last_contacted_at IS NULL
        OR julianday(:now) - julianday(cp.last_contacted_at) >= cp.min_days_between_outreach)
 ORDER BY b.id;
```

**Layer 2 — the policy engine.** `radar/policy.py` gains a check that runs on every draft and every
approval, and whose result is stored on the draft (invariant 4's pattern: the check result is a row,
not a runtime opinion).

```python
BLOCK_HANDOFF_OPEN = "HANDOFF_OPEN"

def check_handoff_open(conn, business_id: str) -> PolicyFinding | None:
    """Refuse to prepare outreach for a business a human is already talking to."""
    row = conn.execute(
        "SELECT id, state, created_at FROM handoffs "
        "WHERE business_id = ? AND state <> 'CLOSED' LIMIT 1", (business_id,)
    ).fetchone()
    if row is None:
        return None
    return PolicyFinding(
        code=BLOCK_HANDOFF_OPEN,
        severity="BLOCK",
        message=f"Open handoff {row['id']} ({row['state']}) since {row['created_at']}. "
                f"Sagar is handling this business personally.",
    )
```

A `BLOCK` finding drives the draft to `POLICY_BLOCKED`, which has no transition to `APPROVED`.

**Layer 3 — claim-time re-check.** The lease-based worker (`_CONTEXT.md` §2) can hold a job that was
queued before the handoff opened. So the send job re-checks after claiming and before doing anything:

```python
def run_send_job(conn, job: Job) -> JobResult:
    blocked = handoff.is_follow_up_blocked(conn, job.payload["business_id"])
    if blocked is not None:
        cancel_message(conn, job.payload["message_id"], reason=blocked.code)
        audit.write(conn, action="OUTREACH_CANCELLED_BY_HANDOFF", ...)
        return JobResult.cancelled(blocked.message)
    ...
```

**Layer 4 — the database.** The last line, because layers 1-3 are all application code and
application code gets refactored.

```sql
CREATE TRIGGER IF NOT EXISTS trg_outreach_blocked_by_open_handoff
BEFORE UPDATE OF status ON outreach_messages
FOR EACH ROW
WHEN NEW.status IN ('QUEUED','SENT')
     AND EXISTS (SELECT 1 FROM handoffs h
                  WHERE h.business_id = NEW.business_id AND h.state <> 'CLOSED')
BEGIN
    SELECT RAISE(ABORT, 'blocked: open handoff for this business');
END;

CREATE TRIGGER IF NOT EXISTS trg_outreach_insert_blocked_by_open_handoff
BEFORE INSERT ON outreach_messages
FOR EACH ROW
WHEN NEW.status IN ('QUEUED','SENT')
     AND EXISTS (SELECT 1 FROM handoffs h
                  WHERE h.business_id = NEW.business_id AND h.state <> 'CLOSED')
BEGIN
    SELECT RAISE(ABORT, 'blocked: open handoff for this business');
END;
```

Both triggers port to Postgres as a single `BEFORE INSERT OR UPDATE` trigger function; no SQLite-only
construct is used.

**Layer 5 — visibility.** Anywhere the UI would offer outreach for a business with a live handoff,
the control renders disabled with the reason inline:

```
[ Prepare outreach ]   BLOCKED - open handoff hnd_01JSAMPLE... since 22 Aug 18:42
```

Never a silent no-op. A disabled button with no explanation is how an operator concludes the system
is broken and works around it.

### 10.8.3 The shared guard

```python
@dataclass(frozen=True, slots=True)
class BlockReason:
    code: str          # HANDOFF_OPEN | SUPPRESSED | FREQUENCY_CAP | REJECTED
    message: str
    handoff_id: str | None = None


def is_follow_up_blocked(conn, business_id: str) -> BlockReason | None:
    """The single question every outreach path must ask before it does anything.

    Called by the scheduler, the policy engine, the send job and the UI. One
    function so there is one answer, and so adding a sixth caller is a one-liner
    rather than a fifth copy of the same SELECT that drifts.
    """
```

### 10.8.4 Tests that must exist

| Test | Asserts |
|---|---|
| `test_open_handoff_blocks_draft_creation` | `POST /api/v1/outreach/drafts` returns 409 with `HANDOFF_OPEN`. |
| `test_open_handoff_blocks_queued_message_at_db` | Direct `UPDATE outreach_messages SET status='QUEUED'` raises `sqlite3.IntegrityError`. |
| `test_handoff_opened_after_queue_cancels_send` | Job claimed pre-handoff, handoff opens, job run cancels the message and writes the audit row. |
| `test_scheduler_skips_business_with_open_handoff` | Candidate query returns zero rows. |
| `test_closing_handoff_does_not_resume_follow_ups` | Business remains `HUMAN_HANDOFF` after close. |
| `test_handoff_module_imports_no_channels` | AST walk of `radar/handoff.py` and `radar/notify.py` finds no import of `radar.channels` or `radar.messages`. |
| `test_second_response_attaches_not_duplicates` | One `handoffs` row, `response_count == 2`, one Telegram `edit`, zero extra `send`. |
| `test_urgent_ignores_quiet_hours` | `disable_notification` false at 02:00 IST for `COMPLAINT`. |
| `test_high_silent_in_quiet_hours_then_repaged` | Silent at 22:30, audible re-notify at 07:30. |
| `test_no_response_requires_in_progress` | Closing an `OPEN` handoff as `NO_RESPONSE` raises. |
| `test_legal_flag_survives_classifier_failure` | Classifier raises; handoff still created as `LEGAL_LANGUAGE`/`URGENT`. |

---

## 10.9 The §54 funnel

### 10.9.1 Stage definitions

Nine stages. Every count is `COUNT(DISTINCT business_id)`, because a business can produce more than
one handoff over its life (§10.4.2) and counting events would inflate the bottom of the funnel — the
exact part that must not be inflated.

| # | Stage | Entry condition | Authoritative test |
|---|---|---|---|
| 1 | RESEARCH | A completed `research_runs` row exists for the business. | `businesses.status <> 'SKIPPED'` and a `research_runs` row with `status='COMPLETE'` |
| 2 | QUALIFICATION | Opportunity score meets the campaign's floor. | `opportunities.score >= campaigns.min_opportunity_score` |
| 3 | VERIFICATION | A human passed all nine §16 checks. | `verifications.verdict='VERIFIED'` |
| 4 | OUTREACH | A message actually left the building. | `outreach_messages.status IN ('SENT','DELIVERED')` |
| 5 | RESPONSE | Anything came back. | a `responses` row exists |
| 6 | INTEREST | A **qualified conversation**: a handoff whose trigger was one of the five §34 buying signals. | `handoffs.trigger_rule='CLASSIFICATION'` |
| 7 | DEMO | A demo was **held**. | `handoffs.demo_held_at IS NOT NULL` |
| 8 | PROPOSAL | A proposal was sent. | `handoffs.proposal_sent_at IS NOT NULL` |
| 9 | CLIENT | Signed or paid. | `handoffs.outcome='WON'` |

Two deliberate precisions:

- **Stage 6 excludes `COMPLAINT`, `LEGAL_LANGUAGE` and `LOW_CONFIDENCE` handoffs.** They are
  handoffs; they are not interest. A funnel that counts a complaint as a conversion is a funnel that
  rewards annoying people. Those rows are counted separately, in a compliance panel, not here.
- **Stage 7 uses `demo_held_at`, not `demo_scheduled_at`.** A demo that was booked and no-showed is
  not a demo. `demo_scheduled_at` drives a separate "in flight" number in the digest and dashboard,
  where a pending thing belongs.

### 10.9.2 One view, three reports

```sql
-- radar/migrations/011_funnel_view.sql
-- One row per business, nine 0/1 columns. Drives the §54 funnel, the §37 city
-- comparison and the §38 industry comparison from a single definition, so those
-- three tables can never disagree about what "qualified" means.
--
-- The opportunities join carries is_current = 1. 01-data-model.md keeps superseded
-- score rows, so without the predicate a re-scored business contributes one funnel
-- row per score and every SUM() below counts it twice.

CREATE VIEW IF NOT EXISTS v_funnel_business AS
SELECT
    b.id                                   AS business_id,
    b.campaign_id                          AS campaign_id,
    b.city                                 AS city,
    b.industry                             AS industry,
    b.category                             AS category,
    b.size_band                            AS size_band,
    b.discovered_at                        AS discovered_at,
    o.score                                AS opportunity_score,

    CASE WHEN EXISTS (SELECT 1 FROM research_runs rr
                       WHERE rr.business_id = b.id AND rr.status = 'COMPLETE')
         THEN 1 ELSE 0 END                 AS s1_research,

    CASE WHEN o.score IS NOT NULL
          AND o.score >= COALESCE(c.min_opportunity_score, 0)
         THEN 1 ELSE 0 END                 AS s2_qualified,

    CASE WHEN EXISTS (SELECT 1 FROM verifications v
                       WHERE v.business_id = b.id AND v.verdict = 'VERIFIED')
         THEN 1 ELSE 0 END                 AS s3_verified,

    CASE WHEN EXISTS (SELECT 1 FROM outreach_messages m
                       WHERE m.business_id = b.id
                         AND m.status IN ('SENT','DELIVERED'))
         THEN 1 ELSE 0 END                 AS s4_outreach,

    CASE WHEN EXISTS (SELECT 1 FROM responses r
                       WHERE r.business_id = b.id)
         THEN 1 ELSE 0 END                 AS s5_response,

    CASE WHEN EXISTS (SELECT 1 FROM handoffs h
                       WHERE h.business_id = b.id
                         AND h.trigger_rule = 'CLASSIFICATION')
         THEN 1 ELSE 0 END                 AS s6_interest,

    CASE WHEN EXISTS (SELECT 1 FROM handoffs h
                       WHERE h.business_id = b.id AND h.demo_held_at IS NOT NULL)
         THEN 1 ELSE 0 END                 AS s7_demo,

    CASE WHEN EXISTS (SELECT 1 FROM handoffs h
                       WHERE h.business_id = b.id AND h.proposal_sent_at IS NOT NULL)
         THEN 1 ELSE 0 END                 AS s8_proposal,

    CASE WHEN EXISTS (SELECT 1 FROM handoffs h
                       WHERE h.business_id = b.id AND h.outcome = 'WON')
         THEN 1 ELSE 0 END                 AS s9_client,

    COALESCE((SELECT SUM(h.won_value_inr) FROM handoffs h
               WHERE h.business_id = b.id AND h.outcome = 'WON'), 0) AS won_value_inr

FROM businesses b
LEFT JOIN opportunities o ON o.business_id = b.id AND o.is_current = 1
LEFT JOIN campaigns     c ON c.id = b.campaign_id;
```

If `01-data-model.md` makes the business-to-campaign link many-to-many, replace the
`b.campaign_id` column and the `campaigns` join with a join through the membership table. Nothing
else in this document changes; every query below reads only `v_funnel_business`.

Campaign funnel:

```sql
SELECT campaign_id,
       SUM(s1_research)  AS research,
       SUM(s2_qualified) AS qualified,
       SUM(s3_verified)  AS verified,
       SUM(s4_outreach)  AS outreach,
       SUM(s5_response)  AS response,
       SUM(s6_interest)  AS interest,
       SUM(s7_demo)      AS demo,
       SUM(s8_proposal)  AS proposal,
       SUM(s9_client)    AS client,
       SUM(won_value_inr) AS revenue_inr
  FROM v_funnel_business
 WHERE campaign_id = :campaign_id
 GROUP BY campaign_id;
```

City comparison (§37) and industry comparison (§38) are the same query grouped by `city` or
`industry`.

### 10.9.3 Conversion metrics

| Metric | Formula | What a bad number means |
|---|---|---|
| Qualification rate | `s2 / s1` | Discovery is pulling in the wrong businesses, or the score floor is set wrong. Fix targeting, not volume. |
| Verification pass rate | `s3 / s2` | The AI's qualification disagrees with Sagar's eyes. Low here means the score is measuring the wrong thing — this is the primary input to §10.10's recalibration. |
| Outreach rate | `s4 / s3` | Verified businesses are not being contacted: missing contacts, suppressions, or a backlog of unapproved drafts. |
| Response rate | `s5 / s4` | Message quality, channel choice, or sending-domain reputation. |
| **Interest rate** | `s6 / s4` | The headline quality metric. Replies that are buying signals, per message sent. |
| Qualification-of-response | `s6 / s5` | How much of the reply volume is real. A high response rate with a low ratio here means the messages are provoking replies, not interest. |
| Demo rate | `s7 / s6` | Handoff handling. If interest is high and demos are low, the lag between reply and Sagar's response is the problem — cross-check against `sla_breach_count`. |
| Proposal rate | `s8 / s7` | Demo quality and fit. |
| Win rate | `s9 / s8` | Pricing and scope. |
| End-to-end | `s9 / s1` | The only number that matters over a quarter. |
| Cost per qualified conversation | `s4 / s6` | Messages sent per qualified conversation. Lower is better. This is the efficiency ratio that makes "messages sent" a denominator rather than an achievement. |

Presentation rules, from invariant 5 and from ordinary honesty:

```python
def rate(numerator: int, denominator: int, *, min_denominator: int = 20) -> str:
    """Render a conversion rate, or refuse to.

    A percentage computed on seven businesses is a decoration, not a measurement.
    Below the threshold this prints the raw fraction so the eye supplies the
    correct amount of scepticism; with no denominator at all it prints an em dash,
    never 0% (invariant 5).
    """
    if denominator <= 0:
        return "—"
    if denominator < min_denominator:
        return f"{numerator} / {denominator}"
    return f"{numerator / denominator * 100:.1f}%"
```

**Cohort rule.** The funnel is cohorted by `campaigns.id` and, for month-over-month views, by
`businesses.discovered_at` — never by event date. A business discovered in July that wins in
September is a July cohort win. Mixing event dates makes a slow month look good because last month's
pipeline landed in it.

**Maturity rule.** Stages 7-9 lag stages 1-6 by weeks. Any funnel view renders
`days_since_campaign_start` next to the campaign name, and any stage whose typical lag exceeds the
campaign's age renders `—` with the tooltip "too early to measure" rather than a zero. Config:

```yaml
funnel:
  min_denominator: 20
  maturity_days:
    demo: 14
    proposal: 30
    client: 60
```

### 10.9.4 The design consequence: what the dashboard shows first

§54 says do not optimise for messages sent, optimise for qualified conversations. A metric nobody
sees is not a goal, and a metric on the top card is one whether or not anybody meant it to be. So
the ordering below is a specification, not a suggestion.

**Definition, fixed here and referenced everywhere else:**

> A **qualified conversation** is a distinct business that reached stage 6: a `handoffs` row with
> `trigger_rule = 'CLASSIFICATION'`. Not a reply. Not a message. A business that answered with a
> buying signal.

`/campaigns` header, first screen, above the fold:

```
+--------------------------------------------------------------------------------+
|                                                                                 |
|   QUALIFIED CONVERSATIONS                                                       |
|                                                                                 |
|                    7                                                            |
|            this month    (4 last month)                                         |
|                                                                                 |
|   Demos held  3      Proposals out  2      Won  1      Revenue  Rs 2,40,000     |
|                                                                                 |
|   Needs you now:  2 open handoffs, 1 overdue                    [ Open queue ]  |
|                                                                                 |
+--------------------------------------------------------------------------------+
```

SAMPLE numbers. Then, in order:

| Position | Block | Contents |
|---|---|---|
| 1 | Headline | Qualified conversations this month, prior month in parentheses. One number, largest type on the page. |
| 2 | Outcomes | Demos held, proposals out, won, revenue. Green permitted here (§51). |
| 3 | Work waiting | Open handoffs, overdue count, oldest age. Yellow at 1 overdue, red at 3. This is the only block that is allowed to be alarming. |
| 4 | Funnel | The nine-stage bar with conversion rates between stages, rendered by §10.9.3's rules. |
| 5 | Where it is working | City comparison (§37) and industry comparison (§38), sorted by interest rate, not by volume. |
| 6 | Pipeline health | Awaiting verification, drafts awaiting approval. Actionable backlogs. |
| 7 | Activity | Greyed, small type, header "Activity (inputs, not results)": businesses discovered, businesses researched, messages sent, messages delivered. |

**What the dashboard deliberately does not celebrate:**

| Not shown, or shown only in block 7 | Why |
|---|---|
| Messages sent | Rendered in grey in block 7, with no delta arrow, no sparkline and no colour. Immediately beside it: "per qualified conversation: 9.7" — its only honest use is as a denominator. |
| Businesses discovered / researched | Same block. Discovery volume is a cost, and the platform-policy risk in `_CONTEXT.md` §4 rises with it. Putting it on the top card would optimise for the exact behaviour §45 exists to prevent. |
| Emails delivered, open rate, click rate | Not shown at all. Open tracking means a tracking pixel, which is a DPDP-relevant processing decision taken for a vanity number. |
| Streaks, "days active", run counts | Not shown. They measure the tool's habit, not the business's. |
| Any total-since-inception counter | Not shown. Monotonic counters only go up and therefore always look like progress. |
| Response rate as a headline | Demoted into the funnel block. A reply that says "stop emailing me" is a response. |

Two hard UI rules that fall out of this:

1. **No volume metric may be green.** §51 reserves green for verified, interested and won. A green
   "68 messages sent" trains the eye to read activity as achievement.
2. **The headline number can go down.** A month with 4 qualified conversations after a month with 7
   shows 4, in the same type size, with the prior month beside it. There is no cumulative variant of
   the top card, because a cumulative variant would never fall and would therefore never prompt a
   change.

The same ordering governs the digest (§10.6.5) and the §43 daily report: needs-you first, in-flight
second, volume last.

### 10.9.5 Funnel endpoint

```
GET /api/v1/funnel?campaign_id=cmp_01JSAMPLE0000000000000001&group_by=city
```

```json
{
  "campaign_id": "cmp_01JSAMPLE0000000000000001",
  "campaign_started_at": "2026-08-26T04:30:00Z",
  "days_since_start": 1,
  "min_denominator": 20,
  "groups": [
    {
      "key": "DHULE",
      "stages": {
        "research": 42, "qualified": 18, "verified": 11, "outreach": 9,
        "response": 3, "interest": 2, "demo": null, "proposal": null, "client": null
      },
      "rates": {
        "qualification": "42.9%",
        "verification_pass": "11 / 18",
        "outreach": "9 / 11",
        "response": "3 / 9",
        "interest": "2 / 9",
        "demo": null,
        "proposal": null,
        "client": null
      },
      "immature": ["demo", "proposal", "client"],
      "revenue_inr": 0
    }
  ]
}
```

SAMPLE. `null` means no data or not yet measurable and renders as an em dash. The client never
substitutes 0 for `null`.

---

## 10.10 Post-handoff tracking and the feedback loop

### 10.10.1 Capturing outcomes

Recording a demo or proposal is one tap, because an outcome Sagar does not bother to record is an
outcome the scoring model never learns from.

| Endpoint | Body | Effect |
|---|---|---|
| `POST /api/v1/handoffs/<id>/demo` | `{"scheduled_at": "2026-08-29T05:30:00Z"}` | Sets `demo_scheduled_at`. Moves state to `IN_PROGRESS` if not already. |
| `POST /api/v1/handoffs/<id>/demo` | `{"held_at": "2026-08-29T05:34:00Z"}` | Sets `demo_held_at`. Stage 7 entry. |
| `POST /api/v1/handoffs/<id>/proposal` | `{"sent_at": "...", "value_inr": 240000}` | Sets `proposal_sent_at`, `proposal_value_inr`. Stage 8 entry. |
| `POST /api/v1/handoffs/<id>/close` | `{"outcome": "WON", "value_inr": 240000, "note": "..."}` | Stage 9 entry. |
| `POST /api/v1/handoffs/<id>/close` | `{"outcome": "LOST", "lost_reason": "ALREADY_HAVE_SOFTWARE"}` | Feeds the category penalty below. |
| `POST /api/v1/handoffs/<id>/note` | `{"text": "..."}` | `audit_log` row, `action='HANDOFF_NOTE'`. |

A `demo_scheduled_at` in the past with no `demo_held_at` after 48 hours produces one digest line
("demo on 29 Aug not marked as held") and nothing more. The system asks once.

### 10.10.2 The labelled outcome set

```sql
-- radar/migrations/012_outcome_labels.sql
-- The training set for score recalibration. Only CONTACTED businesses are in it:
-- a business nobody messaged did not fail to convert, it was never asked, and
-- treating its silence as a negative label teaches the model to avoid whatever
-- the verification queue happened to be slow on.

CREATE VIEW IF NOT EXISTS v_outcome_labels AS
SELECT
    f.business_id,
    f.campaign_id,
    f.city,
    f.industry,
    f.category,
    f.size_band,
    f.opportunity_score,
    b.digital_maturity,
    CASE WHEN b.website IS NULL OR b.website = '' THEN 0 ELSE 1 END AS has_website,
    f.s6_interest   AS label_interest,
    f.s7_demo       AS label_demo,
    f.s9_client     AS label_won,
    f.won_value_inr,
    (SELECT MIN(m.sent_at) FROM outreach_messages m
      WHERE m.business_id = f.business_id AND m.status IN ('SENT','DELIVERED')) AS first_contacted_at
FROM v_funnel_business f
JOIN businesses b ON b.id = f.business_id
WHERE f.s4_outreach = 1;
```

Per-bucket lift, with a small-sample guard:

```sql
-- Interest rate by (industry, size_band), Wilson lower bound at 95%.
SELECT industry,
       size_band,
       COUNT(*)                AS contacted,
       SUM(label_interest)     AS interested,
       SUM(label_won)          AS won,
       SUM(won_value_inr)      AS revenue_inr
  FROM v_outcome_labels
 WHERE first_contacted_at >= :window_start
 GROUP BY industry, size_band
HAVING COUNT(*) >= :min_bucket_n
 ORDER BY interested * 1.0 / COUNT(*) DESC;
```

```python
def wilson_lower_bound(successes: int, trials: int, z: float = 1.96) -> float:
    """Rank buckets by what we can defend, not by what we got lucky on.

    Raw conversion sorts a 1-for-1 bucket above a 40-for-100 bucket, which is how a
    scoring model ends up chasing one hospital in Shirpur for a quarter.
    """
    if trials == 0:
        return 0.0
    p = successes / trials
    denom = 1 + z * z / trials
    centre = p + z * z / (2 * trials)
    margin = z * ((p * (1 - p) / trials + z * z / (4 * trials * trials)) ** 0.5)
    return (centre - margin) / denom
```

### 10.10.3 Recalibration: a proposal, not an application

The monthly `score_calibration` job (`14-background-jobs.md`) reads `v_outcome_labels`, computes
per-feature lift against the global baseline, and writes two artefacts:

1. `data/reports/score_calibration_2026-09.html` — a self-contained report in the same Jinja2
   pipeline as §5's research report: bucket table, lift chart, proposed deltas, sample sizes, and
   the businesses that drove each change by name.
2. `config/score_weights.2026-09.yaml` — a **proposal** file.

Nothing is applied automatically. Sagar diffs the proposal against `config.yaml` and copies what he
agrees with. Auto-applying would silently change which businesses get researched next month, and the
first symptom would be a month of bad leads with no obvious cause — which is precisely the failure
`naukri_job_screener/screener/score.py` avoids by keeping every weight inspectable in a YAML file
rather than learned into a model you cannot interrogate.

Guardrails baked into the proposal generator:

| Guardrail | Value | Reason |
|---|---|---|
| Minimum bucket size | 25 contacted businesses | Below this the bucket is a rumour. |
| Maximum monthly shift per feature | ±10 score points | One good month cannot rewrite the model. |
| Score domain | clamped to 0-100 | §6's band definitions must stay meaningful. |
| Look-back window | 180 days, rolling | Long enough to accumulate wins, short enough to notice a market change. |
| Every adopted change | `audit_log` row, `action='SCORE_WEIGHTS_ADOPTED'`, with the before/after weights in `detail_json` | Explains, six months later, why the model started favouring distributors. |

### 10.10.4 What actually feeds back (§53)

| §53 question | Answer computed from | Where it lands |
|---|---|---|
| Which city gives the best opportunities? | `v_funnel_business` grouped by `city`, sorted by interest rate with Wilson bound | Next campaign's `campaign_cities` default selection |
| Which industries respond most? | grouped by `industry` | `score.py` industry weight proposal; campaign industry filter default |
| Which businesses have the highest software potential? | `label_won` and `label_demo` regressed against `size_band`, `digital_maturity`, `has_website`, `category` | Score feature weight proposals |
| Which outreach works? | Response and interest rate by `outreach_drafts.prompt_version` and template id | `06-message-engine.md` template ranking; losing templates retired |
| Which demos generate interest? | `s7_demo -> s8_proposal` by `industry` and by module set | Demo build priority |
| Which proposals convert? | `s8 -> s9` by `proposal_value_inr` band | Pricing guidance in the `R-PRICE-01` playbook rule |
| What software to build next? | `opportunity_modules` frequency across `label_won = 1` rows, weighted by `won_value_inr` | The product roadmap; the single most valuable output of the whole system |

```sql
-- Modules present in won deals, weighted by realised revenue. SAMPLE shape.
SELECT om.module,
       COUNT(DISTINCT l.business_id)                AS won_deals,
       SUM(l.won_value_inr)                         AS revenue_inr
  FROM v_outcome_labels l
  JOIN opportunity_modules om ON om.business_id = l.business_id
 WHERE l.label_won = 1
 GROUP BY om.module
 ORDER BY revenue_inr DESC;
```

Negative feedback is narrower on purpose. A `LOST` outcome with
`lost_reason = 'ALREADY_HAVE_SOFTWARE'` increments a category-level saturation counter; once a
category exceeds `score.saturation_threshold` such losses inside the look-back window, the proposal
file suggests a research-priority demotion for that category — a demotion, never a ban, because a
saturated category still contains businesses whose software is being replaced this year.

---

## 10.11 Module contract

```python
"""radar/handoff.py

Turns a reply into a human decision, and stops the machine while it waits.

Without this module the most valuable event the system produces - a business
saying yes - lands in a `responses` row and dies there, while the follow-up
scheduler keeps nudging a person who already answered. That second nudge is
worse than no system at all: it tells the prospect, in the clearest possible
way, that nobody read what they wrote.

Two guarantees live here and nowhere else:

  1. A trigger writes a `handoffs` row before anything else happens, and that
     row is what blocks every automated outbound path to the business. Not a
     config flag, not a status field somebody can forget to check - a row, with
     a partial unique index behind it and a database trigger behind that.

  2. Nothing in this module can contact a business. It does not import
     radar.channels or radar.messages, it produces text and not drafts, and the
     one thing it hands Sagar is advice with a rule id attached so he can see
     where the advice came from.

Everything else here - SLA clocks, de-duplication, the Telegram brief - exists
to make sure a lead reaches a phone at 9pm in a form a tired person can act on.
"""
```

Public API:

```python
# triggering
def evaluate_triggers(response: Response, cfg: Config) -> TriggerDecision | None: ...
def create_handoff(conn, response_id: str, decision: TriggerDecision, *,
                   cfg: Config, actor: str = "system") -> Handoff: ...
def attach_response(conn, handoff_id: str, response_id: str,
                    decision: TriggerDecision) -> AttachResult: ...

# brief and advice
def build_brief(conn, handoff_id: str, *, cfg: Config) -> HandoffBrief: ...
def recommend_next_action(conn, brief: HandoffBrief, cfg: Config) -> RecommendedAction: ...
def render_telegram(brief: HandoffBrief, *, sla_breach: bool = False) -> str: ...
def render_email(brief: HandoffBrief) -> tuple[str, str]: ...   # (subject, body)

# lifecycle
def get(conn, handoff_id: str) -> Handoff: ...
def acknowledge(conn, handoff_id: str, user_id: str, *, via: str = "web") -> Handoff: ...
def start(conn, handoff_id: str, user_id: str) -> Handoff: ...
def close(conn, handoff_id: str, user_id: str, outcome: str, *,
          note: str | None = None, value_inr: int | None = None,
          lost_reason: str | None = None) -> Handoff: ...
def snooze(conn, handoff_id: str, until: datetime, user_id: str) -> Handoff: ...
def record_demo(conn, handoff_id: str, *, scheduled_at: str | None = None,
                held_at: str | None = None) -> Handoff: ...
def record_proposal(conn, handoff_id: str, sent_at: str,
                    value_inr: int | None) -> Handoff: ...

# enforcement and sweeps
def is_follow_up_blocked(conn, business_id: str) -> BlockReason | None: ...
def sweep_slas(conn, now: datetime, cfg: Config) -> SweepResult: ...
def open_queue(conn, *, state: str | None = None, priority: str | None = None,
               city: str | None = None, older_than_days: int | None = None) -> list[Handoff]: ...
```

Endpoint registry contributed to `13-api-endpoints.md`:

```
GET    /api/v1/handoffs                        list, filterable
POST   /api/v1/handoffs                        manual creation / re-open
GET    /api/v1/handoffs/<handoff_id>           row + brief
GET    /api/v1/handoffs/<handoff_id>/brief     brief only, JSON
POST   /api/v1/handoffs/<handoff_id>/acknowledge
POST   /api/v1/handoffs/<handoff_id>/start
POST   /api/v1/handoffs/<handoff_id>/close
POST   /api/v1/handoffs/<handoff_id>/snooze
POST   /api/v1/handoffs/<handoff_id>/note
POST   /api/v1/handoffs/<handoff_id>/demo
POST   /api/v1/handoffs/<handoff_id>/proposal
POST   /api/v1/handoffs/<handoff_id>/renotify  force a re-page
GET    /api/v1/funnel                          §54 funnel, grouped
POST   /api/v1/notifications/telegram/callback webhook mode only
```

UI routes: `/handoffs` (queue), `/handoffs/<handoff_id>` (brief). Both are behind the same auth as
the rest of the app (§47); there is no unauthenticated deep link, and the Telegram `Open brief`
button lands on a login redirect if the session has expired.

Jobs contributed to `14-background-jobs.md`:

| Job kind | Trigger | Idempotency |
|---|---|---|
| `handoff_create` | Enqueued by `radar/classify.py` after a response is classified | `ux_handoffs_open_response` + the `NOT EXISTS` insert |
| `handoff_notify` | Enqueued by `handoff_create`, and by `handoff_sla_sweep` | `notify_count` cap and `dedupe_window_minutes` |
| `handoff_sla_sweep` | Every 5 minutes | `sla_last_breach_at` cool-off |
| `handoff_digest` | Daily at `notify.digest.at` | Keyed on the digest date |
| `telegram_poll` | Continuous, leased, polling mode only | `getUpdates` offset persisted |
| `score_calibration` | Monthly, first of the month | Writes proposal files only; applies nothing |

---

## 10.12 Failure modes

| Failure | Symptom | Design response |
|---|---|---|
| Telegram API down at trigger time | `notify_count` stays 0 | Handoff exists regardless; email fallback fires; `handoff_notify` retries with backoff; the row sits `OPEN` and shows on `/handoffs`. The lead is never lost because notification failed. |
| Bot token revoked | Every send 401 | `TelegramNotifier.configured` is False; startup logs an error; digest and email still work; `/handoffs` is unaffected. |
| Classifier returns garbage | `confidence_pct` low or `classification = 'UNKNOWN'` | `LOW_CONFIDENCE` trigger fires; a human reads it. The failure mode of the classifier is a handoff, not silence. |
| Gemini API down or over quota during `recommend_next_action` | No phrasing | Rule skeleton ships verbatim; `action_model_id` is NULL, which is the honest record that no model contributed. |
| Two responses arrive in the same second | Race on insert | Partial unique index rejects the second; caller catches `IntegrityError` and calls `attach_response()`. |
| Worker crashes between insert and notify | Handoff exists, nobody told | `handoff_sla_sweep` finds it `OPEN` past `sla_ack_due_at` with `notify_count = 0` and notifies. |
| Sagar closes a handoff by mistake | Lead looks handled | No re-open; he creates a new handoff with `previous_handoff_id`. The audit log carries both rows and the mistake stays visible. |
| Mail loop: an autoresponder replies to every message | Hundreds of triggers | Global hourly page cap batches them; one live handoff per business caps the row count; the autoresponder's own replies classify `UNKNOWN` and land in `LOW_CONFIDENCE`, not `INTERESTED`. |
| `brief_json` unreadable (corrupt or schema drift) | Page render fails | Same posture as `naukri_job_screener/screener/ledger.py`: log an error naming the handoff id, render the row's scalar columns plus a "brief unavailable, rebuild" control, and never silently substitute an empty brief. |

---

## Open questions

1. **Id prefix `hnd_`.** `_CONTEXT.md` §2 lists prefixes for nine tables and does not name one for
   `handoffs`. This document uses `hnd_`. If `01-data-model.md` picks something else, that wins and
   every literal here changes with it.
2. **`radar/notify.py` is a new module** not present in `_CONTEXT.md` §6's module list. The reason it
   is not `radar/channels/notify.py` is in §10.6.1 and I believe it is the right call, but the module
   list may want updating for consistency across the pack.
3. **`businesses.campaign_id`.** §10.9.2's view assumes a single first-discovering campaign per
   business. If the same business can be discovered by two campaigns and `01-data-model.md` models
   that as a join table, `v_funnel_business` needs one join changed and the cohort rule in §10.9.3
   needs a tie-break (first campaign wins is the natural choice).
4. **Operator identity for the Telegram callback.** This assumes one operator (`TELEGRAM_OPERATOR_ID`
   in `config/.env`). If `users` ever holds more than Sagar, the callback handler needs a mapping
   from Telegram user id to `users.id`, and `owner_user_id` starts to matter for routing rather than
   just for the record.
5. **`URGENT` SLA of 30 minutes for acknowledgement** is aggressive for a solo operator who sleeps.
   It is set there deliberately so that a complaint at 02:00 is a breach by 02:30 and escalates to
   email — which costs nothing and guarantees the item is unmissable in the morning. If the breach
   noise proves annoying in practice, raise the ack window rather than moving `COMPLAINT` out of
   `URGENT`.
6. **Cross-document filenames.** Doc numbering here follows §56's sixteen deliverables
   (`09-response-classification.md`, `05-outreach-workflow.md`, and so on). If the pack's actual
   slugs differ, the links need a pass.
