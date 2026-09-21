# 6. Message template engine and claim-safety policy

This document decides how a personalised outreach message is built and how the system proves, before
Sagar ever reads it, that every factual sentence in it is traceable to a stored `research_findings`
row. It settles the three-layer template bundle (channel template -> industry block -> business
slots) and the `template_version` recorded on every draft, the exact §24 email skeleton plus four
fully written industry variants, the §25 WhatsApp variant and its length budget, the §26
industry-to-module map extended to every `businesses.category` value in `_CONTEXT.md` §6, the policy
engine in `radar/policy.py` that emits `PASS` / `WARN` / `BLOCK` with per-rule detail, the human edit
path that cannot bypass that engine, the §49 AI message audit record, and the exact Gemini API call
(model, prompts, JSON response schema, token and quota budget). It covers spec §22, §23, §24, §25,
§26, §27 and §49.

**Changed for the free stack (binding, `_CONTEXT.md` §2).** The drafting model is `gemini-2.5-flash`
on the Google AI Studio **free tier**, called through the `google-genai` SDK. There is no `anthropic`
dependency and no rupee budget anywhere in this document: the per-message ceiling is a **quota**
ceiling (requests and tokens against the daily free-tier allowance), and exhausting it pauses
drafting until the quota resets rather than costing money. Two further rules follow from the free
tier and are new: **no `business_contacts` value may ever appear in an LLM prompt** (§6.13.0), and
the unsubscribe mechanism in the body is a `mailto:` address rather than an HTTPS link, because
there is no public endpoint to link to (§6.4). Everything else in this document — the template
bundle, the claim map, the policy engine, the audit record — is unchanged, because none of it
depended on which model wrote the text.

**Cross-references.** `05-outreach-workflow.md` owns the pipeline this module sits inside (step 3
DRAFT, step 4 POLICY CHECK), the lifecycle columns of `outreach_drafts`, and every *eligibility*
gate (opt-out, duplicate, frequency). Nothing in this document decides whether a business may be
contacted — only whether a message is honest. `01-data-model.md` carries the canonical schema;
`10-human-handoff.md` owns what happens after a reply. Where this document prints DDL it is an
additive migration on top of `05-outreach-workflow.md`'s `013_outreach_drafts.sql`, not a
replacement.

---

## 6.1 The rule this module exists to enforce

`_CONTEXT.md` §3 invariant 4, restated as something a function can return:

> A generated message may **state** an `OBSERVED` finding, may **hedge about** an `INFERRED` finding,
> and may **never mention** an `UNKNOWN` finding. Every factual sentence carries the id of the
> `research_findings` row it came from. A sentence with no id is not a sentence we are allowed to
> send.

Two design consequences that everything below follows from:

| Consequence | Mechanism |
|---|---|
| The model cannot be trusted to self-police, so it is required to **show its work** | The Gemini call returns `{subject, body, claim_map, confidence}` as structured output (`response_schema`, §6.13.4). The `claim_map` binds each sentence to finding ids. A draft without a well-formed claim map is `BLOCK`ed before any content rule runs (rule `T2`). |
| The checker must not trust the claim map either | `radar/policy.py` re-segments the body itself and matches the model's claim entries onto *its own* segments. A segment the model did not describe is treated as unbound, not as safe (rule `T3`, then `F1`). |

The policy engine is deterministic, pure Python, does no network I/O, and reads the database only to
resolve finding ids and to build the similarity corpus. It is the one part of this system that must
be trivially unit-testable, because it is the part that stops Sagar from sending a lie.

**The free-tier model makes this engine more load-bearing, not less.** `gemini-2.5-flash` is a small,
fast model chosen because it is free, not because it is the most careful writer available. A smaller
model follows a long constraint list less reliably: it is likelier to drop a hedge, to merge two
sentences and orphan a binding, to restate an `UNKNOWN` finding as a fact, or to return a claim map
that does not match the body it just wrote. Every one of those is a rule in §6.9 that already fires.
So the correct response to "we downgraded the model" is **more** reliance on the deterministic
checker and the repair loop, not a softer checker to accommodate a weaker writer. Concretely: no rule
in §6.9 may be relaxed, downgraded from BLOCK to WARN, or made model-conditional to raise the
first-pass acceptance rate. If the acceptance rate is poor, the prompt (§6.13.2) or the skeleton
(§6.4) is what changes. `test_templates.py::test_rendered_variants_pass_policy` is the guard: the
templates must pass the checker with no model involved at all, so a weak model can only fail to
improve on a message that was already legal.

---

## 6.2 Modules and files

| Path | Responsibility |
|---|---|
| `radar/messages.py` | Assemble research context, render the template bundle, call Gemini, run the repair loop, persist `outreach_drafts` content columns, produce the §49 audit payload |
| `radar/policy.py` | `check_draft()` and every rule in §6.9. No LLM calls, no template knowledge |
| `radar/templates/messages/` | The versioned template bundle (§6.3) |
| `radar/prompts/messages/` | Versioned prompt files (`system.v3.txt`, `user.v3.j2`, `repair.v2.j2`), pinned by `prompt_version`. The `v3` files are **redefined** for Gemini rather than superseded, because nothing has shipped: the first version that runs against a real business is the one that gets frozen |
| `radar/migrations/018_message_engine.sql` | Additive columns on `outreach_drafts`, plus `v_ai_message_audit` |

Module docstrings, in the house voice (`_CONTEXT.md` §1 — name the real-world failure the module
prevents):

```python
# radar/messages.py
"""Turn a verified business and its research findings into one message Sagar can defend.

Without this module the alternative is a mail-merge: the same paragraph, the same opening
line, the same three modules, sent to forty businesses across four cities. That message is
recognisable as a bot on the second copy, and the first person who forwards it to the
second person who received it has all the evidence they need. Worse, a free-writing model
will happily state that a hospital "is managing patients in Excel", because that is the
kind of sentence that appears in sales copy - and nobody researched it.

So this module does two things at once: it varies the wording per business from a
structured pool plus a rewrite pass, and it forces the model to emit, alongside the
message, the finding id behind every factual sentence it wrote. Nothing it produces is
sent from here; the output goes to radar/policy.py and then to a human.
"""

# radar/policy.py
"""Refuse to show Sagar a message that claims something the research did not establish.

The failure this prevents is specific and it is not hypothetical: a business receives a
cold email asserting a fact about its internal operations that the sender cannot possibly
know, replies "how do you know that?", and there is no answer. That single exchange costs
the prospect, the sending domain's reputation, and any claim the system had to being a
research tool rather than a spam cannon.

So every draft - generated or hand-edited - is segmented into sentences, every sentence
that asserts something about the recipient is matched to a research_findings row, and the
kind of that row decides what the sentence is allowed to sound like: OBSERVED may be
stated, INFERRED must be hedged, UNKNOWN must not appear. The result is stored, not just
returned, so six months later the audit record still says which rule passed and which rule
fired. BLOCK means the approve endpoint will not accept the draft at all.
"""
```

---

## 6.3 Template architecture

### 6.3.1 The three layers

A message is never a single template. It is a resolution of three layers, in this order:

```
 layer 1  CHANNEL TEMPLATE          radar/templates/messages/channel/email.base.v3.j2
          ----------------------    Structure only: the nine §24 elements in order, the
          the per-channel           signature block, the unsubscribe line. Identical for
          envelope                  every business on that channel. Never names an industry.
                    |
                    v
 layer 2  INDUSTRY BLOCK            radar/templates/messages/industry/hospital.v2.yaml
          ----------------------    Vocabulary for one businesses.category: the solution
          what this kind of         name, the ordered module keys (§26), the "relevant area"
          business is called and    phrase, and a pool of 3-6 phrasings for each variable
          what its modules are      sentence role.
                    |
                    v
 layer 3  BUSINESS SLOTS            resolved per draft in radar/messages.py
          ----------------------    business_name, city, size_phrase, form of address, the
          the only per-business     OBSERVED detail, the INFERRED opportunity line, the three
          content, all of it        module labels. Every factual slot carries the finding id
          bound to a finding id     it came from.
```

Rendering order matters for claim safety: layer 3 is the **only** layer that can introduce a factual
assertion about the recipient, and every layer-3 value arrives with a `finding_id` attached or is
declared non-factual in the slot pack. Layers 1 and 2 are audited once, when their version is cut,
not once per message.

### 6.3.2 Bundle layout on disk

```
radar/templates/messages/
    MANIFEST.yaml                     # which version of each layer is live
    channel/
        email.base.v3.j2
        whatsapp.base.v2.j2
        phone.script.v1.j2            # a call script, never transmitted (05-outreach-workflow.md)
    industry/
        hospital.v2.yaml
        diagnostic_center.v1.yaml
        school.v2.yaml
        college.v1.yaml
        manufacturer.v2.yaml
        distributor.v1.yaml
        vehicle_dealer.v2.yaml
        garage.v1.yaml
        hotel.v1.yaml
        restaurant.v1.yaml
        bakery.v1.yaml
        retail_store.v1.yaml
        real_estate_agency.v1.yaml
        _industry_healthcare.v1.yaml  # industry-level fallback, used when category = OTHER
        _industry_education.v1.yaml
        _industry_automobile.v1.yaml
        _industry_manufacturing.v1.yaml
        _industry_retail.v1.yaml
        _industry_hospitality.v1.yaml
        _industry_distribution.v1.yaml
        _industry_real_estate.v1.yaml
        _industry_professional_services.v1.yaml
        _default.v1.yaml              # last resort, generic §13 module vocabulary
    slots/slots.v4.yaml               # slot catalogue: type, source, hedge requirement, max length
    variation/pools.v4.yaml           # channel-level (industry-independent) phrasing pools
```

Files are **append-only by version**. `hospital.v2.yaml` is never edited once a message generated
from it has reached `outreach_messages.status = 'SENT'`; a change means `hospital.v3.yaml` plus a
one-line `MANIFEST.yaml` edit. `tests/test_templates.py::test_frozen_bundles` fails if the sha256 of
any file referenced by a `template_version` present in the database has changed.

### 6.3.3 `MANIFEST.yaml`

```yaml
# radar/templates/messages/MANIFEST.yaml
bundle_name: msg-bundle
slots:     slots/slots.v4.yaml
variation: variation/pools.v4.yaml

channel:
  EMAIL:    channel/email.base.v3.j2
  WHATSAPP: channel/whatsapp.base.v2.j2
  PHONE:    channel/phone.script.v1.j2
  MANUAL:   channel/email.base.v3.j2      # MANUAL drafts reuse the email body, minus the send path

# keyed on businesses.category
category:
  HOSPITAL:            industry/hospital.v2.yaml
  DIAGNOSTIC_CENTER:   industry/diagnostic_center.v1.yaml
  SCHOOL:              industry/school.v2.yaml
  COLLEGE:             industry/college.v1.yaml
  MANUFACTURER:        industry/manufacturer.v2.yaml
  DISTRIBUTOR:         industry/distributor.v1.yaml
  VEHICLE_DEALER:      industry/vehicle_dealer.v2.yaml
  GARAGE:              industry/garage.v1.yaml
  HOTEL:               industry/hotel.v1.yaml
  RESTAURANT:          industry/restaurant.v1.yaml
  BAKERY:              industry/bakery.v1.yaml
  RETAIL_STORE:        industry/retail_store.v1.yaml
  REAL_ESTATE_AGENCY:  industry/real_estate_agency.v1.yaml

# keyed on businesses.industry, used only when category resolves to OTHER
industry:
  HEALTHCARE:             industry/_industry_healthcare.v1.yaml
  EDUCATION:              industry/_industry_education.v1.yaml
  AUTOMOBILE:             industry/_industry_automobile.v1.yaml
  MANUFACTURING:          industry/_industry_manufacturing.v1.yaml
  RETAIL:                 industry/_industry_retail.v1.yaml
  HOSPITALITY:            industry/_industry_hospitality.v1.yaml
  DISTRIBUTION:           industry/_industry_distribution.v1.yaml
  REAL_ESTATE:            industry/_industry_real_estate.v1.yaml
  PROFESSIONAL_SERVICES:  industry/_industry_professional_services.v1.yaml
  OTHER:                  industry/_default.v1.yaml

default: industry/_default.v1.yaml
```

Resolution is strictly `category` -> `industry` -> `default`. A `businesses.category` value with no
manifest entry raises `TemplateResolutionError` at draft time; it does not fall through silently,
because a silent fall-through is how a vehicle dealer receives a message about patient records.

### 6.3.4 `template_version`

One string, stored on every draft, that identifies all three layers **and** their bytes:

```
<channel_stem>@<ver>+<industry_stem>@<ver>+slots@<ver>+pools@<ver>#<bundle_sha8>

SAMPLE:  email.base@v3+ind.hospital@v2+slots@v4+pools@v4#7c1ad93e
SAMPLE:  whatsapp.base@v2+ind.manufacturer@v2+slots@v4+pools@v4#b1e4f207
```

`bundle_sha8` is the first 8 hex characters of `sha256` over the concatenated raw bytes of the four
resolved files, joined by `\x1e`, in the order shown. The version numbers say what Sagar *meant* to
use; the hash catches the case where he edited a template file and forgot to bump the version. Rule
`T1` blocks any draft whose recomputed bundle hash does not match its stored `template_version`.

```python
# radar/messages.py
@dataclass(frozen=True)
class TemplateBundle:
    channel: str                     # EMAIL | WHATSAPP | PHONE | MANUAL
    channel_path: Path
    industry_path: Path
    slots_path: Path
    pools_path: Path
    template_version: str
    channel_source: str              # the Jinja2 source, already read
    industry: dict[str, Any]         # parsed YAML
    slots: dict[str, Any]
    pools: dict[str, Any]


def load_bundle(channel: str, category: str, industry: str, *, root: Path) -> TemplateBundle:
    """Resolve MANIFEST.yaml to four files and compute the template_version.

    Raises TemplateResolutionError when the manifest has no entry for the category and no
    entry for the industry - never falls through to the generic block by accident.
    """


def verify_bundle(template_version: str, *, root: Path) -> bool:
    """Re-read the four files named by template_version and confirm the bundle hash.

    Called by radar/policy.py (rule T1) and by the frozen-bundle test.
    """
```

### 6.3.5 The slot catalogue

`slots/slots.v4.yaml` is the contract between the template and the policy engine. Every slot declares
what kind of sentence it produces, which decides how the checker treats it.

| Slot | Claim type | Bound to | Hedge | Max chars | Source |
|---|---|---|---|---|---|
| `subject` | `SUBJECT` | — | no | 78 | template + `business_name` |
| `greeting` | `GREETING` | — | no | 60 | `business_contacts.contact_name` or "team" |
| `self_intro` | `SELF` | `config: identity.*` | no | 200 | channel pool |
| `process` | `PROCESS` | `research_runs.id` + >=1 `sources.id` | no | 220 | channel pool |
| `observation` | `FACTUAL` | >=1 `research_findings.id` (`OBSERVED`) | no | 240 | industry pool + finding |
| `opportunity` | `FACTUAL` | >=1 `research_findings.id` (`INFERRED`) | **required** | 300 | industry pool + finding |
| `solution_concept` | `OFFER` | `opportunities.potential_solution` | no | 200 | industry block |
| `benefit` | `FACTUAL` | >=1 `research_findings.id` (`INFERRED`) | **required** | 220 | industry pool |
| `demo_offer` | `SELF_CAPABILITY` | `config: identity.demo_modules` | no | 220 | industry block |
| `cta` | `CTA` | — | no | 180 | channel pool |
| `signature_*` | `IDENTITY` | `config: identity.*` | no | 300 total | config |
| `unsubscribe` | `COMPLIANCE` | `outreach_drafts.unsubscribe_token` | no | 200 | channel template. 200, not 160: the `mailto:` form (§6.4) spells out an address and a 32-hex token where a link used to be |
| `relevant_modules` | `MODULE_LIST` | `opportunity_modules` or §26 map | no | 90 | §6.8 |
| `modules` | `MODULE_LIST` | `config: identity.demo_modules` ∩ map | no | 120 | §6.8 |
| `relevant_area` | `MODULE_LIST` | §26 map | no | 60 | §6.8 (WhatsApp only) |

Claim types, and what the policy engine does with each:

| Claim type | Must bind to a finding | May assert | Notes |
|---|---|---|---|
| `FACTUAL` | **yes** | per finding kind | The only type that may say something about the recipient |
| `PROCESS` | to a research run + a source | yes | "we reviewed its publicly available business information" |
| `SELF`, `SELF_CAPABILITY` | to config, not findings | yes | Claims about Sagar and his product; rule `M2` |
| `OFFER` | to `opportunities` | conditional only | Must read as a proposal, never as a diagnosis |
| `GREETING`, `CTA`, `IDENTITY`, `COMPLIANCE`, `SUBJECT` | no | n/a | Carry no assertion about the recipient |
| `MODULE_LIST` | to the §26 map | n/a | Rule `M1`: no module label outside the allowed set |

### 6.3.6 Rendering

Jinja2, sandboxed environment, `StrictUndefined`, autoescape **off** (these are plain-text bodies; the
HTML alternative part is generated later by `radar/channels/email.py` from the same plain text). An
undefined slot raises, never renders empty — a message with a hole in it is a message that says
`{{ business_name }}` to a stranger.

```python
def render_bundle(bundle: TemplateBundle, slots: SlotValues) -> RenderedMessage:
    """Render layer 1 with layers 2-3 substituted. Pure: no DB, no LLM.

    Returns subject (None for WHATSAPP/PHONE), body, and the seed claim_map built from the
    slot catalogue - the bindings the template itself knows about, before the model runs.
    """
```

### 6.3.7 Schema additions

```sql
-- radar/migrations/018_message_engine.sql
-- Additive on top of 013_outreach_drafts.sql (05-outreach-workflow.md 5.3.4).
-- Forward-only. SQLite ALTER TABLE ADD COLUMN is safe on a WAL database.

ALTER TABLE outreach_drafts ADD COLUMN template_version   TEXT;
ALTER TABLE outreach_drafts ADD COLUMN industry_block     TEXT;   -- e.g. 'industry/hospital.v2.yaml'
ALTER TABLE outreach_drafts ADD COLUMN variant_seed       TEXT;   -- hex, see 6.6.1
ALTER TABLE outreach_drafts ADD COLUMN variant_ids        TEXT;   -- JSON {slot: variant_id}
ALTER TABLE outreach_drafts ADD COLUMN slot_values        TEXT;   -- JSON, the layer-3 inputs
ALTER TABLE outreach_drafts ADD COLUMN claim_map          TEXT;   -- JSON, schema claim_map/v1
ALTER TABLE outreach_drafts ADD COLUMN raw_generation     TEXT;   -- JSON, the model's untouched reply
ALTER TABLE outreach_drafts ADD COLUMN rewrite_applied    INTEGER NOT NULL DEFAULT 0
                                          CHECK (rewrite_applied IN (0,1));
ALTER TABLE outreach_drafts ADD COLUMN repair_attempts    INTEGER NOT NULL DEFAULT 0;
ALTER TABLE outreach_drafts ADD COLUMN similarity_max     REAL;   -- max J3 against the corpus
ALTER TABLE outreach_drafts ADD COLUMN similarity_peer_id TEXT REFERENCES outreach_messages(id);
ALTER TABLE outreach_drafts ADD COLUMN unsubscribe_token  TEXT;   -- 32 hex, per draft
ALTER TABLE outreach_drafts ADD COLUMN body_edit_diff     TEXT;   -- unified diff, generated -> edited
ALTER TABLE outreach_drafts ADD COLUMN policy_checked_body_hash TEXT;  -- what the checker actually read
ALTER TABLE outreach_drafts ADD COLUMN quota_requests     INTEGER NOT NULL DEFAULT 0;
                                                  -- Gemini requests this draft consumed
                                                  -- (generate + rewrite + repairs), 6.13.6

CREATE UNIQUE INDEX ux_drafts_unsub ON outreach_drafts(unsubscribe_token)
    WHERE unsubscribe_token IS NOT NULL;
CREATE INDEX ix_drafts_template ON outreach_drafts(template_version);
```

**Changed for the free stack:** the column here used to be `cost_inr REAL`, the rupee cost of the
draft. There is no rupee cost on the free tier, so the thing worth recording per draft is how much of
the day's request allowance it consumed. `input_tokens` / `output_tokens` (from
`05-outreach-workflow.md`'s `013_outreach_drafts.sql`) already carry the token side; `quota_requests`
adds the request side, and the two together are exactly what `14-background-jobs.md` §14.10.4's
quota ceiling is measured in. No other document referenced `outreach_drafts.cost_inr`, so this rename
is contained.

`policy_checked_body_hash` is the anti-bypass column: the approve endpoint in
`05-outreach-workflow.md` recomputes `sha256(subject_final || '\x1e' || final_body)` and refuses to
write an `outreach_approvals` row unless it equals `policy_checked_body_hash`. A human edit that
never went back through the checker therefore cannot be approved, even if `policy_result` still says
`PASS` from the previous pass. See §6.10.

---

## 6.4 The §24 email skeleton

`channel/email.base.v3.j2`, printed in full. The right-hand comments name the §24 structural element
and the claim type each line produces.

```jinja
{#- radar/templates/messages/channel/email.base.v3.j2
    Layer 1. Structure only. Every {{ s.* }} is a slot from slots/slots.v4.yaml.
    Do not put industry vocabulary in this file - that is layer 2. -#}
---
subject: "{{ s.subject }}"
---
{{ s.greeting }},

{{ s.self_intro }} {{ s.process }}

{{ s.observation }} {{ s.opportunity }}

{{ s.solution_concept }} {{ s.benefit }}

{{ s.demo_offer }}

{{ s.cta }}

Regards,
{{ s.signature_name }}
{{ s.signature_role }}, {{ s.signature_company }}
{{ s.signature_contact }}

{{ s.unsubscribe }}
```

Mapping to §24, so nothing in the spec's structure is lost:

| §24 element | Slot | Claim type | Notes |
|---|---|---|---|
| Subject | `subject` | `SUBJECT` | Rule `R3` (not misleading), `R4` (length) |
| Greeting | `greeting` | `GREETING` | "Hello {{contact_name}}" or "Hello {{business_name}} team" |
| Business-specific observation | `observation` | `FACTUAL` / `OBSERVED` | Must bind; this is the sentence §23 is about |
| Problem / opportunity | `opportunity` | `FACTUAL` / `INFERRED` | Hedge mandatory (rule `K1`) |
| Solution concept | `solution_concept` | `OFFER` | From `opportunities.potential_solution` |
| Relevant benefit | `benefit` | `FACTUAL` / `INFERRED` | Hedge mandatory |
| Demo offer | `demo_offer` | `SELF_CAPABILITY` | Rule `M2`: only declared demo modules |
| Short CTA | `cta` | `CTA` | Rule `A8`: no pressure |
| Professional signature | `signature_*` | `IDENTITY` | Rule `R2`: real name, real company, real reply address |
| (added, not in §24) | `unsubscribe` | `COMPLIANCE` | Rule `R1`; `_CONTEXT.md` §4 requires it |

The §24 wording itself is the `v1` variant of each slot pool, so `email.base@v3` with every pool at
variant index 0 reproduces the spec text almost verbatim. That is deliberate: Sagar can diff any
generated message against the skeleton he wrote.

**The §24 text as the baseline render (SAMPLE, all variants at index 0, hospital block):**

```
Subject: A possible digital operations solution for ABC Hospital

Hello ABC Hospital team,

We work on customised business-management software for established organisations. While
researching businesses in Dhule, we came across ABC Hospital and reviewed its publicly
available business information.

Based on the nature of your operations, we believe there may be opportunities to
centralise areas such as patient records, appointments and billing, and to provide
management visibility through a controlled dashboard.

We are building demonstration systems for businesses in this category covering areas such
as patients, appointments, departments, billing, inventory and reports.

If this is relevant to your organisation, I would be happy to show you a short
demonstration and discuss whether such a system could fit your current workflow.

Regards,
Sagar
Founder, SAMPLE Software Works
sagar.softwareworks@gmail.com | +91 XXXXXXXXXX

To stop these emails: reply STOP, or email sagar.softwareworks+unsub@gmail.com
with subject: unsubscribe 9f13c0aa4b7d4e1e8a2c5f60d3b81c47
```

Identity strings (`Sagar`, role, company, reply address, unsubscribe mailbox) come from
`config.yaml` `identity.*`; the values above are `SAMPLE` placeholders, not settings.

**Changed for the free stack: the unsubscribe line is a `mailto:` instruction, not an HTTPS link.**
The earlier version of this document rendered `https://{sending_domain}/u/{token}`. There is no
sending domain and no public endpoint any more (`_CONTEXT.md` §2: the app is bound to `127.0.0.1` on
Sagar's laptop), so a link would point at nothing a recipient could reach. RFC 2369 permits a
`mailto:` unsubscribe, and that is what the build uses, in two places that must agree:

| Where | Form | Owner |
|---|---|---|
| `List-Unsubscribe` header | `<mailto:{identity.unsubscribe_mailbox}?subject=unsubscribe%20{token}>` | `07-email-integration.md` sets the header |
| Body, the `unsubscribe` slot | a plain-English instruction naming the same mailbox and the same 32-hex token, plus `reply STOP` | this document, rule `R1` |

`identity.unsubscribe_mailbox` is a **plus-address on the same free Gmail account**
(`sagar.softwareworks+unsub@gmail.com`), so it needs no second mailbox and no second credential:
Gmail delivers it to the same inbox that `poll_inbox` already reads, and the `+unsub` tag plus the
`Subject:` token are what the deterministic pre-classifier keys on
(`09-response-classification.md` §9.5, stage 1 rule `B2`). The token still comes from
`outreach_drafts.unsubscribe_token`, which is why that column and its unique index survive the change
unaltered — it is now carried in a subject line instead of a URL path.

`reply STOP` is not a nicety here. It is the fallback for the case where the recipient's mail client
does not render `List-Unsubscribe` and they answer the message instead, and since this build has no
HTTPS unsubscribe at all, those two forms are the **entire** opt-out surface. `09` §9.5 treats both
as deterministic, pre-model, non-overridable.

§24 ends with "Do not use this exact wording for every business." §6.6 is the mechanism that enforces
that, and it is enforced by a rule (`V1`), not by good intentions.

---

## 6.5 Four industry variants, written out

Each variant is one layer-2 YAML file plus the message it produces. The pools are the variation
surface: `radar/messages.py` picks one entry per role using the deterministic seed from §6.6.1, then
the LLM rewrite pass (§6.6.2) adjusts phrasing without changing bindings.

### 6.5.1 Hospital — `industry/hospital.v2.yaml`

```yaml
# radar/templates/messages/industry/hospital.v2.yaml
category: HOSPITAL
industry: HEALTHCARE
solution_name: "Hospital Operations Platform"          # matched against opportunities.potential_solution
module_keys: [PATIENTS, APPOINTMENTS, DEPARTMENTS, BILLING, INVENTORY, REPORTS]
relevant_area: "patient, appointment and billing records"
noun_singular: "hospital"
noun_plural: "hospitals"
audience_phrase: "hospitals and multi-department clinics"

observation_pool:                                       # FACTUAL / OBSERVED - needs {{ observed_detail }}
  - id: obs.h1
    text: "While researching healthcare providers in {{ city }}, we came across {{ business_name }};
           your public listing shows {{ observed_detail }}."
  - id: obs.h2
    text: "{{ business_name }} appears in {{ city }} healthcare listings with {{ observed_detail }}."
  - id: obs.h3
    text: "From {{ business_name }}'s publicly available information we noted {{ observed_detail }}."
  - id: obs.h4
    text: "Your public information for {{ business_name }} in {{ city }} lists {{ observed_detail }}."

opportunity_pool:                                       # FACTUAL / INFERRED - hedge required
  - id: opp.h1
    text: "Based on the nature of a {{ size_word }} hospital's operations, we believe there may be
           opportunities to bring {{ relevant_modules }} into one system."
  - id: opp.h2
    text: "In hospitals of this scale, coordinating {{ relevant_modules }} across departments could
           be an area where a single system helps."
  - id: opp.h3
    text: "Based on the scale and nature of your operations, {{ relevant_modules }} may be areas
           where centralised records reduce duplicate entry."

benefit_pool:                                           # FACTUAL / INFERRED - hedge required
  - id: ben.h1
    text: "That would typically mean one place to see today's appointments, department load and
           pending billing, rather than separate registers."
  - id: ben.h2
    text: "The practical benefit is usually visibility: current patient flow, department-wise load
           and outstanding billing on one dashboard."

solution_concept:
  text: "What we build for this category is a {{ solution_name }} - a controlled dashboard over
         {{ relevant_modules }}, with role-based access and an audit trail."

demo_offer:
  text: "We are building demonstration systems for {{ audience_phrase }} covering {{ modules }}."

whatsapp_area: "patient records, appointments and billing"
```

**Rendered SAMPLE — email, variants `obs.h2` / `opp.h3` / `ben.h1`:**

```
Subject: A possible operations system for ABC Hospital, Dhule

Hello ABC Hospital team,

We work on customised business-management software for established organisations. While
researching businesses in Dhule we came across ABC Hospital and reviewed its publicly
available business information.

ABC Hospital appears in Dhule healthcare listings with four named departments and an
online appointment enquiry form. Based on the scale and nature of your operations,
patient records, appointments and billing may be areas where centralised records reduce
duplicate entry.

What we build for this category is a Hospital Operations Platform - a controlled
dashboard over patient records, appointments and billing, with role-based access and an
audit trail. That would typically mean one place to see today's appointments, department
load and pending billing, rather than separate registers.

We are building demonstration systems for hospitals and multi-department clinics covering
patients, appointments, departments, billing, inventory and reports.

If a short demonstration would be useful, I can walk your team through it in about twenty
minutes and we can discuss whether it fits your current workflow.

Regards,
Sagar
Founder, SAMPLE Software Works
sagar.softwareworks@gmail.com | +91 XXXXXXXXXX

Not the right person, or not interested? Reply STOP, or email
sagar.softwareworks+unsub@gmail.com with subject: unsubscribe
9f13c0aa4b7d4e1e8a2c5f60d3b81c47 - and we will not contact you again.
```

**Claim map for that render (SAMPLE):**

| Segment | Text (truncated) | Type | Bound to | Kind | Hedged |
|---|---|---|---|---|---|
| 0 | `A possible operations system for ABC Hospital, Dhule` | `SUBJECT` | — | — | — |
| 1 | `Hello ABC Hospital team,` | `GREETING` | — | — | — |
| 2 | `We work on customised business-management software...` | `SELF` | `config:identity` | — | — |
| 3 | `While researching businesses in Dhule we came across...` | `PROCESS` | `res_01J...RUN`, `src_01J...A2` | — | — |
| 4 | `ABC Hospital appears in Dhule healthcare listings with four named departments...` | `FACTUAL` | `res_01J...F7` | `OBSERVED` | no |
| 5 | `Based on the scale and nature of your operations, patient records...may be areas...` | `FACTUAL` | `res_01J...F9` | `INFERRED` | yes (`based on the scale`, `may`) |
| 6 | `What we build for this category is a Hospital Operations Platform...` | `OFFER` | `opportunities.id=opp_01J...` | — | — |
| 7 | `That would typically mean one place to see today's appointments...` | `FACTUAL` | `res_01J...F9` | `INFERRED` | yes (`typically`, `would`) |
| 8 | `We are building demonstration systems for hospitals...` | `SELF_CAPABILITY` | `config:identity.demo_modules` | — | — |
| 9 | `If a short demonstration would be useful...` | `CTA` | — | — | — |
| 10-12 | signature lines | `IDENTITY` | `config:identity` | — | — |
| 13 | unsubscribe line | `COMPLIANCE` | `outreach_drafts.unsubscribe_token` | — | — |

### 6.5.2 School — `industry/school.v2.yaml`

```yaml
category: SCHOOL
industry: EDUCATION
solution_name: "School Management System"
module_keys: [STUDENTS, FEES, ATTENDANCE, STAFF, TRANSPORT, REPORTS]
relevant_area: "student records, fees and attendance"
noun_singular: "school"
audience_phrase: "schools and junior colleges"

observation_pool:
  - id: obs.s1
    text: "While looking at schools in {{ city }} we came across {{ business_name }};
           its public information mentions {{ observed_detail }}."
  - id: obs.s2
    text: "{{ business_name }}'s public listing in {{ city }} shows {{ observed_detail }}."
  - id: obs.s3
    text: "From publicly available information about {{ business_name }} we noted {{ observed_detail }}."

opportunity_pool:
  - id: opp.s1
    text: "Based on the nature of a school of this size, {{ relevant_modules }} may be areas where a
           single system reduces manual register work."
  - id: opp.s2
    text: "We believe keeping {{ relevant_modules }} in one place could make each term's reporting
           less dependent on individual spreadsheets."
  - id: opp.s3
    text: "In schools with several sections, {{ relevant_modules }} could be areas where centralised
           records help parents and staff get the same answer."

benefit_pool:
  - id: ben.s1
    text: "In practice that usually means fee status, attendance and section-wise strength are
           available on one screen instead of being compiled at month end."
  - id: ben.s2
    text: "The benefit is typically time at reporting points - term end, fee cycles and inspections."

solution_concept:
  text: "For schools we build a {{ solution_name }}: one dashboard over {{ relevant_modules }}, with
         separate access for office staff, teachers and management."

demo_offer:
  text: "We have a working demonstration for {{ audience_phrase }} covering {{ modules }}."

whatsapp_area: "student records, fees and attendance"
```

**Rendered SAMPLE — email, variants `obs.s2` / `opp.s1` / `ben.s1`:**

```
Subject: A possible school management system for SAMPLE Vidyalaya

Hello SAMPLE Vidyalaya office team,

We build customised business-management software for established organisations in
Maharashtra. While researching schools in Shirpur we came across SAMPLE Vidyalaya and
reviewed its publicly available information.

SAMPLE Vidyalaya's public listing in Shirpur shows classes from 1 to 10, two sections per
class and a school bus service. Based on the nature of a school of this size, student
records, fees and attendance may be areas where a single system reduces manual register
work.

For schools we build a School Management System: one dashboard over student records, fees
and attendance, with separate access for office staff, teachers and management. In
practice that usually means fee status, attendance and section-wise strength are available
on one screen instead of being compiled at month end.

We have a working demonstration for schools and junior colleges covering students, fees,
attendance, staff, transport and reports.

If it would be useful, I can show it in a short call at a time that suits your office.

Regards,
Sagar
Founder, SAMPLE Software Works
sagar.softwareworks@gmail.com | +91 XXXXXXXXXX

To stop receiving email from us, reply STOP, or email
sagar.softwareworks+unsub@gmail.com with subject: unsubscribe
2b7e5c1948af4d3aa0c6e9f27d40b135
```

### 6.5.3 Manufacturer — `industry/manufacturer.v2.yaml`

```yaml
category: MANUFACTURER
industry: MANUFACTURING
solution_name: "Manufacturing Management Platform"      # §35 uses this exact phrase
module_keys: [INVENTORY, PRODUCTION, PURCHASING, SALES, QUALITY, REPORTS]
relevant_area: "inventory, production and purchase records"
noun_singular: "manufacturing unit"
audience_phrase: "manufacturing units and processing plants"

observation_pool:
  - id: obs.m1
    text: "While researching manufacturing units in {{ city }} we came across {{ business_name }};
           your public information describes {{ observed_detail }}."
  - id: obs.m2
    text: "{{ business_name }} is listed in {{ city }} with {{ observed_detail }}."
  - id: obs.m3
    text: "Publicly available information for {{ business_name }} mentions {{ observed_detail }}."

opportunity_pool:
  - id: opp.m1
    text: "Based on the nature of that kind of operation, we believe {{ relevant_modules }} may be
           areas where a centralised system gives management better visibility."
  - id: opp.m2
    text: "In units with more than one product line, {{ relevant_modules }} could be where a single
           system saves the most reconciliation effort."
  - id: opp.m3
    text: "We believe inventory visibility may be an area where a centralised system could provide
           value, alongside {{ relevant_modules }}."          # §23 "good" wording, verbatim

benefit_pool:
  - id: ben.m1
    text: "That normally shows up as one view of stock on hand, work in progress and pending
           purchase orders, instead of three separate registers."
  - id: ben.m2
    text: "The usual benefit is knowing, without asking three people, what is in stock, what is in
           production and what has been dispatched."

solution_concept:
  text: "For this category we build a {{ solution_name }} - a controlled dashboard over
         {{ relevant_modules }}, with role-based access and an audit trail on every change."

demo_offer:
  text: "We are building demonstration systems for {{ audience_phrase }} covering {{ modules }}."

whatsapp_area: "inventory, production and purchase tracking"
```

**Rendered SAMPLE — email, variants `obs.m2` / `opp.m3` / `ben.m1`:**

```
Subject: A possible production and inventory system for ABC Industries

Hello ABC Industries team,

We work on customised business-management software for established organisations. While
researching manufacturing units in Dhule we came across ABC Industries and reviewed its
publicly available business information.

ABC Industries is listed in Dhule with two product lines and an ISO 9001 certification
mark on its website. We believe inventory visibility may be an area where a centralised
system could provide value, alongside inventory, production and purchasing.

For this category we build a Manufacturing Management Platform - a controlled dashboard
over inventory, production and purchasing, with role-based access and an audit trail on
every change. That normally shows up as one view of stock on hand, work in progress and
pending purchase orders, instead of three separate registers.

We are building demonstration systems for manufacturing units and processing plants
covering inventory, production, purchasing, sales, quality and reports.

If this is relevant, I would be glad to show a short demonstration and discuss whether it
fits how you work today.

Regards,
Sagar
Founder, SAMPLE Software Works
sagar.softwareworks@gmail.com | +91 XXXXXXXXXX

If you would rather not hear from us, reply STOP, or email
sagar.softwareworks+unsub@gmail.com with subject: unsubscribe
c04a9d2f61b84e77b5d3e8106af2c9d0
```

### 6.5.4 Vehicle dealer — `industry/vehicle_dealer.v2.yaml`

```yaml
category: VEHICLE_DEALER
industry: AUTOMOBILE
solution_name: "Dealership Management System"
module_keys: [INVENTORY, PURCHASES, EXPENSES, SALES, PROFIT, CUSTOMERS]
relevant_area: "vehicle stock, purchases and sales records"
noun_singular: "dealership"
audience_phrase: "vehicle dealerships and used-vehicle businesses"

observation_pool:
  - id: obs.v1
    text: "While researching vehicle dealers in {{ city }} we came across {{ business_name }};
           your public information lists {{ observed_detail }}."
  - id: obs.v2
    text: "{{ business_name }} appears in {{ city }} listings as a dealership with
           {{ observed_detail }}."
  - id: obs.v3
    text: "From {{ business_name }}'s publicly available information we noted {{ observed_detail }}."

opportunity_pool:
  - id: opp.v1
    text: "Based on the nature of vehicle sales, {{ relevant_modules }} may be areas where per-unit
           cost and margin are easier to see in one system."
  - id: opp.v2
    text: "We believe tracking {{ relevant_modules }} against each vehicle could make month-end
           profit per unit clearer."
  - id: opp.v3
    text: "In dealerships handling both new and pre-owned stock, {{ relevant_modules }} could be
           where a single system removes the most manual matching."

benefit_pool:
  - id: ben.v1
    text: "That usually means each vehicle carries its own purchase cost, refurbishment expense and
           sale price, so margin per unit is a report rather than a calculation."
  - id: ben.v2
    text: "The practical result is normally a clear view of ageing stock and margin per vehicle."

solution_concept:
  text: "For dealerships we build a {{ solution_name }} covering {{ relevant_modules }}, with
         customer records attached to each sale."

demo_offer:
  text: "We have a working demonstration for {{ audience_phrase }} covering {{ modules }}."

whatsapp_area: "vehicle stock, purchases and sales"
```

**Rendered SAMPLE — email, variants `obs.v1` / `opp.v2` / `ben.v1`:**

```
Subject: A possible stock and margin system for SAMPLE Motors

Hello SAMPLE Motors team,

We build customised business-management software for established businesses. While
researching vehicle dealers in Jalgaon we came across SAMPLE Motors and reviewed its
publicly available business information.

While researching vehicle dealers in Jalgaon we came across SAMPLE Motors; your public
information lists two showroom locations and both new and pre-owned vehicles. We believe
tracking vehicle stock, purchases and expenses against each vehicle could make month-end
profit per unit clearer.

For dealerships we build a Dealership Management System covering vehicle stock, purchases
and expenses, with customer records attached to each sale. That usually means each vehicle
carries its own purchase cost, refurbishment expense and sale price, so margin per unit is
a report rather than a calculation.

We have a working demonstration for vehicle dealerships and used-vehicle businesses
covering inventory, purchases, expenses, sales, profit and customers.

If useful, I can show it in about fifteen minutes and we can discuss whether it fits your
current process.

Regards,
Sagar
Founder, SAMPLE Software Works
sagar.softwareworks@gmail.com | +91 XXXXXXXXXX

Reply STOP, or email sagar.softwareworks+unsub@gmail.com with subject:
unsubscribe 71ae3f5c8d2b4c96a4f0b7e13c6d2058
```

Note the defect this SAMPLE deliberately shows: `obs.v1` repeats the `process` sentence's "While
researching ... in {{ city }} we came across ..." opening, so the paragraph says the same thing
twice. That is caught before Sagar sees it — `pools.v4.yaml` declares `process` and `observation`
mutually exclusive on their opening clause (§6.6.1, `conflicts:`), and the selector re-rolls. It is
printed here because the failure is easy to reintroduce when adding an industry block, and
`tests/test_templates.py::test_pool_conflicts` exists precisely for it.

---

## 6.6 Not sending the same message twice (§24)

§24 says: "Do not use this exact wording for every business. Personalize the message." That is
implemented as three mechanisms in series, and audited by one rule.

```
  slot values (per business, from findings)
            |
            v
  [1] structured slot variation      deterministic pick from the pools, seeded per business
            |                        -> different sentence shapes, same meaning, reproducible
            v
  [2] LLM rewrite pass               gemini-2.5-flash rewrites for flow within hard constraints
            |                        -> natural prose, bindings unchanged
            v
  [3] similarity ceiling             token-set + shingle similarity against recently SENT messages
            |                        -> re-roll, then re-rewrite, then WARN, then BLOCK
            v
  policy engine rule V1
```

### 6.6.1 Structured slot variation

Every variable sentence role has a pool of 2-6 entries in the industry block (`observation_pool`,
`opportunity_pool`, `benefit_pool`) or in `variation/pools.v4.yaml` (channel-level roles:
`self_intro`, `process`, `cta`, `greeting`, `subject`, `unsubscribe`).

```yaml
# radar/templates/messages/variation/pools.v4.yaml (extract)
subject:
  - id: sub.1
    text: "A possible digital operations solution for {{ business_name }}"      # §24 verbatim
  - id: sub.2
    text: "A possible operations system for {{ business_name }}, {{ city }}"
  - id: sub.3
    text: "A possible {{ short_area }} system for {{ business_name }}"
  - id: sub.4
    text: "Custom business software for {{ business_name }} - short demonstration"

self_intro:
  - id: intro.1
    text: "We work on customised business-management software for established organisations."
  - id: intro.2
    text: "We build customised business-management software for established organisations."
  - id: intro.3
    text: "We build customised business-management software for established businesses in
           Maharashtra."

process:
  - id: proc.1
    text: "While researching businesses in {{ city }}, we came across {{ business_name }} and
           reviewed its publicly available business information."                # §24 verbatim
  - id: proc.2
    text: "While researching businesses in {{ city }} we came across {{ business_name }} and
           reviewed its publicly available information."
  - id: proc.3
    text: "We were reviewing publicly available information about businesses in {{ city }} and
           came across {{ business_name }}."

cta:
  - id: cta.1
    text: "If this is relevant to your organisation, I would be happy to show you a short
           demonstration and discuss whether such a system could fit your current workflow."
  - id: cta.2
    text: "If a short demonstration would be useful, I can walk your team through it in about
           twenty minutes and we can discuss whether it fits your current workflow."
  - id: cta.3
    text: "If useful, I can show it in a short call at a time that suits you."

conflicts:
  # (role_a, variant_prefix_a, role_b, variant_prefix_b) - never select both
  - [process, "proc.1", observation, "obs.*.while_researching"]
  - [process, "proc.2", observation, "obs.*.while_researching"]
```

Selection is deterministic, so regenerating a draft for the same business produces the same message
unless something real changed:

```python
def variant_seed(business_id: str, sequence_no: int, template_version: str) -> str:
    """Stable per (business, attempt, bundle). Reproducible in an audit six months later."""
    material = f"{business_id}|{sequence_no}|{template_version}".encode()
    return hashlib.sha256(material).hexdigest()


def pick_variants(seed: str, pools: dict[str, list[dict]], *, reroll: int = 0) -> dict[str, str]:
    """Map role -> variant id. reroll shifts the index when the similarity gate re-rolls (6.6.3).

    Uses a per-role slice of the seed so adding a variant to one pool does not reshuffle
    every other role's choice for every business.
    """
    picks: dict[str, str] = {}
    for role, pool in sorted(pools.items()):
        digest = hashlib.sha256(f"{seed}|{role}|{reroll}".encode()).digest()
        idx = int.from_bytes(digest[:4], "big") % len(pool)
        picks[role] = pool[idx]["id"]
    return _resolve_conflicts(picks, pools)
```

`variant_ids` and `variant_seed` are stored on the draft. With `template_version`, they are enough to
re-derive the pre-LLM text exactly.

Pool arithmetic, for the record: with 4 subject variants, 3 intros, 3 process lines, 3 CTAs and
(per industry) 3-4 observation, 3 opportunity and 2 benefit variants, the pre-LLM combination count
per industry is 4x3x3x3x3x3x2 = 1,944. That is the *shape* space; the finding-derived slot values
differ per business on top of it. This is a property of the files above, not a measurement.

### 6.6.2 The LLM rewrite pass

Structured variation alone still reads like a template, because the joins between sentences are
fixed. The rewrite pass is one additional Gemini call (`prompt_version = "msg-rewrite-v2"`) whose
entire job is prose flow. It is the second of the two requests a typical draft spends against the
daily quota (§6.13.6), and it runs on the **un-hydrated** body — the contact greeting is still a
placeholder at this point (§6.13.0), so the rewrite pass is as contact-free as the generation pass.

What the rewrite pass **may** do:

- reorder clauses inside a sentence, merge two short sentences, split a long one;
- change connectives and transitions;
- change the subject line to any of the pool variants' meaning, within 78 characters;
- adjust register (slightly more or less formal).

What it **may not** do, enforced by re-running the full policy check on its output (not by asking
nicely):

- add, remove or change a factual assertion, or move an assertion between sentences without updating
  the returned `claim_map`;
- remove a hedge from an `INFERRED`-bound sentence;
- introduce a number, percentage, currency amount, client name, person's name or date;
- change the module labels, the solution name, the identity block, the CTA's offer or the
  unsubscribe line (these arrive as `frozen_spans` and are compared byte-for-byte after the call).

```python
@dataclass(frozen=True)
class RewriteRequest:
    draft_body: str
    subject: str
    claim_map: ClaimMap
    frozen_spans: list[str]          # must appear unchanged in the output
    avoid_phrases: list[str]         # from the similarity gate, 6.6.3
    max_chars: int


def rewrite(req: RewriteRequest, *, cfg: Config) -> RewriteResult:
    """One gemini-2.5-flash call for flow only. Returns the rewritten text plus its claim map.

    On any of: API error, invalid JSON, a frozen span that no longer matches byte-for-byte,
    or a claim map that fails T2 - the rewrite is discarded and the pre-rewrite text is kept.
    A failed rewrite is a cosmetic loss, so it never fails the draft; it sets
    outreach_drafts.rewrite_applied = 0 and logs at WARNING.
    """
```

### 6.6.3 The similarity ceiling

**What is measured.** Two numbers, both computed on a *skeleton* of the text — the message with
every business-specific token replaced by a placeholder, so that "different because the business name
differs" does not count as different.

```python
_STOPWORDS = frozenset("a an and are as at be by for from has have i if in is it of on or our so \
that the to we with you your".split())

def skeleton(text: str, slots: SlotValues) -> str:
    """Strip everything that is per-business, so what remains is the phrasing."""
    out = text
    for token, placeholder in (
        (slots.business_name, "<BIZ>"), (slots.city, "<CITY>"),
        (slots.contact_name or "\x00", "<PERSON>"), (slots.solution_name, "<SOLUTION>"),
        (slots.unsubscribe_token, "<UNSUB>"), (slots.observed_detail, "<OBS>"),
    ):
        out = out.replace(token, placeholder)
    for label in slots.all_module_labels:
        out = re.sub(rf"\b{re.escape(label)}\b", "<MODULE>", out, flags=re.I)
    out = out.casefold()
    out = re.sub(r"https?://\S+", "<URL>", out)
    out = re.sub(r"[\w.+-]+@[\w.-]+\.\w+", "<EMAIL>", out)   # identity + unsubscribe mailbox
    out = re.sub(r"[^a-z0-9<>\s]+", " ", out)
    return re.sub(r"\s+", " ", out).strip()


def token_set(sk: str) -> frozenset[str]:
    return frozenset(t for t in sk.split() if t not in _STOPWORDS and len(t) > 2)


def shingles(sk: str, n: int = 3) -> frozenset[tuple[str, ...]]:
    toks = sk.split()
    return frozenset(tuple(toks[i:i + n]) for i in range(max(0, len(toks) - n + 1)))


def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0

# TSR = jaccard(token_set(A), token_set(B))     "token-set similarity"  - what words are used
# J3  = jaccard(shingles(A),  shingles(B))      "shingle similarity"    - what order they are in
```

`TSR` alone is too permissive (two messages built from the same industry block share almost all
content words by construction). `J3` alone is too strict on short WhatsApp bodies. So the gate uses
both.

**The corpus.** Recently sent messages, on the same channel, to *other* businesses:

```sql
-- radar/policy.py :: SIMILARITY_CORPUS_SQL
SELECT m.id, m.subject_final, m.body_final
  FROM outreach_messages m
 WHERE m.channel      = :channel
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.business_id <> :business_id
   AND m.sent_at     >= :cutoff              -- now - policy.similarity_window_days (default 120)
 ORDER BY m.sent_at DESC
 LIMIT :corpus_limit;                        -- default 500
```

Follow-ups in the same thread are excluded by `business_id <> :business_id`: repeating yourself to
the same business across a thread is normal, repeating yourself to strangers is not.

**Thresholds** (`config.yaml` `policy.similarity.*`, defaults):

| Band | Condition | Effect |
|---|---|---|
| Clear | `J3 < 0.42` and not (`TSR >= 0.85` and `J3 >= 0.30`) | Rule `V1` passes |
| Similar | `0.42 <= J3 < 0.75`, or `TSR >= 0.85` and `J3 >= 0.30` | Re-roll / rewrite; if still here after the loop, `V1` = **WARN**, shown inline in the preview with a link to the peer message |
| Near-duplicate | `J3 >= 0.75` | `V1` = **BLOCK** |

**The loop.** In `radar/messages.py`, before the policy check:

```
render with reroll=0
  -> rewrite pass
  -> measure against corpus
     if Clear:            done
     if Similar:          reroll=1, re-render, re-rewrite, re-measure
     if still Similar:    rewrite again with avoid_phrases = the 3-grams shared with the peer
     if still Similar:    keep it, V1 = WARN, store similarity_max + similarity_peer_id
     if Near-duplicate at any point after reroll=1: stop, V1 = BLOCK
```

Maximum two re-rolls and two rewrite calls per draft; the cost ceiling in §6.13.6 accounts for the
worst case. `similarity_max` and `similarity_peer_id` are stored on the draft whatever the outcome,
so the preview can always answer "what does this look like?".

**Worked measurement (SAMPLE).** Two hospital emails, one to ABC Hospital (Dhule) and one to a
different hospital in Nashik, both from `ind.hospital@v2`:

| Pair | `TSR` | `J3` | Band | Action |
|---|---|---|---|---|
| Same variants (`obs.h2`/`opp.h3`/`ben.h1`) both times | 0.94 | 0.81 | Near-duplicate | BLOCK, then re-roll to a different variant set |
| After re-roll to `obs.h4`/`opp.h1`/`ben.h2` | 0.88 | 0.47 | Similar | rewrite with `avoid_phrases` |
| After rewrite | 0.83 | 0.29 | Clear | `V1` passes |

These numbers are a worked illustration of the thresholds, not measurements from a running system.

---

## 6.7 The WhatsApp variant (§25)

### 6.7.1 What may actually be sent

From `_CONTEXT.md` §4, restated because it decides the template's shape: a business-initiated
WhatsApp message through the Cloud API requires a **pre-approved template** and prior **opt-in**.
Cold outreach to a business that never opted in is a Business Messaging Policy violation. So v1
produces a `wa.me` deep link that Sagar sends by hand, and the Cloud API path is built but gated
behind a recorded opt-in. The message engine therefore emits **two artefacts** from one draft:

| Artefact | Used when | Constraint that shapes it |
|---|---|---|
| `body` (free text) | Always. Rendered in the preview, copied into `wa.me` | URL length; Sagar reads it on a phone |
| `template_params` (JSON) | Only when `contact_policy` records an opt-in and the Cloud API is enabled | Meta-approved template with positional variables; no free text |

### 6.7.2 `channel/whatsapp.base.v2.j2`

```jinja
{#- radar/templates/messages/channel/whatsapp.base.v2.j2
    Layer 1, WhatsApp. No subject. No unsubscribe URL (the opt-out instruction is inline).
    Hard budget enforced by rule R6 - see 6.7.3. -#}
{{ s.greeting }}, {{ s.self_intro_short }}

{{ s.process_short }} {{ s.opportunity_short }}

{{ s.demo_offer_short }} {{ s.cta_short }}

{{ s.signature_name }}, {{ s.signature_company }}
{{ s.optout_line }}
```

The §25 text is variant index 0 of these short slots, so the baseline render is the spec's own
wording:

```
Hello ABC Hospital team, I work on customised business-management software for established
businesses.

I came across your organisation while researching businesses in Dhule. Based on your
business type, I believe a centralised system for patient records, appointments and
billing could potentially improve operational visibility and reporting.

We have a working demonstration for this type of business. If you are interested, I can
share a short demo and explain how it could be customised around your workflow.

Regards, Sagar
Reply STOP and I will not message again.
```

Differences from the email variant, and why:

| Difference | Reason |
|---|---|
| No `observation` slot by default | The §25 body has no room for a cited OBSERVED detail *and* a hedged opportunity. The opportunity line is kept because it is the one that carries the offer. If the observation is included (`whatsapp.include_observation: true`), the demo-offer sentence is dropped to stay inside budget. |
| `relevant_area` (one phrase) instead of `relevant_modules` (three labels) | Length. §26's `relevant_area` column exists for this slot. |
| Opt-out is an instruction, not a URL | A URL in a WhatsApp first message reads as spam and consumes the `wa.me` budget. Rule `R1` accepts `Reply STOP...` for `WHATSAPP`, and the classifier maps a `STOP` reply to `responses.classification = 'OPT_OUT'` -> a `suppressions` row (`05-outreach-workflow.md` §5.3.2). |
| No unsubscribe link, no tracking link, no attachment | Rule `R7` allows zero URLs on this channel. |

### 6.7.3 Length budget

| Measure | Soft (WARN) | Hard (BLOCK) | Why that number |
|---|---|---|---|
| Body characters | 640 | 900 | WhatsApp shows roughly the first 600-700 characters before "Read more" on a typical phone; past that the recipient decides from a truncated view |
| Body words | 110 | 150 | Reading budget for a message received during a working day |
| Paragraphs | 3 | 4 | Anything longer looks like a forwarded broadcast |
| Sentences | 6 | 8 | One claim per sentence; more than 8 means the message is arguing |
| `wa.me` URL total length | 1,800 | 2,000 | Practical URL length ceiling across browsers and the WhatsApp handler; the body is percent-encoded, so a 900-character body can reach ~1,700 encoded characters |
| Emoji | 0 | 0 | House style (`_CONTEXT.md` §5) and it reads as consumer marketing |

Enforcement (rule `R6`) measures the **rendered** body, after the rewrite pass, and the encoded URL:

```python
def wa_click_to_chat(phone_e164: str, body: str) -> str:
    """https://wa.me/<digits>?text=<percent-encoded body>. Sagar clicks this; nothing is sent
    by the system on this channel in v1."""
    digits = re.sub(r"\D", "", phone_e164)
    return f"https://wa.me/{digits}?text={urllib.parse.quote(body, safe='')}"
```

### 6.7.4 Cloud API template mapping (gated)

When `contact_policy.automation_mode` permits and a recorded opt-in exists, the same draft is sent as
an approved template rather than free text. The message engine emits the parameters; it never emits
free text on that path.

```json
{
  "messaging_product": "whatsapp",
  "to": "<E.164 digits>",
  "type": "template",
  "template": {
    "name": "business_software_intro_v1",
    "language": { "code": "en" },
    "components": [
      { "type": "body", "parameters": [
        { "type": "text", "text": "ABC Hospital" },
        { "type": "text", "text": "Dhule" },
        { "type": "text", "text": "patient records, appointments and billing" }
      ] }
    ]
  }
}
```

The approved template body registered with Meta must itself pass the policy engine once, at
registration time, with `{{1}}`/`{{2}}`/`{{3}}` bound to `business_name`, `city` and `relevant_area`.
Since the fixed text cannot be re-checked per recipient, it contains **no** slot of claim type
`FACTUAL`: the only per-recipient variables are a name, a city and a module phrase. Rule `M1` still
applies to `{{3}}`.

### 6.7.5 Two more WhatsApp renders (SAMPLE)

Manufacturer, `ind.manufacturer@v2` (412 characters, 68 words — inside budget):

```
Hello ABC Industries team, I work on customised business-management software for
established businesses.

I came across your organisation while researching manufacturing units in Dhule. Based on
your business type, I believe a centralised system for inventory, production and purchase
tracking could improve day-to-day visibility and month-end reporting.

We have a working demonstration for this type of business. If it is of interest, I can
share a short demo and explain how it could be customised around your workflow.

Regards, Sagar
Reply STOP and I will not message again.
```

Vehicle dealer, `ind.vehicle_dealer@v2` (398 characters, 65 words):

```
Hello SAMPLE Motors team, I build customised business-management software for established
businesses.

I came across your dealership while researching vehicle dealers in Jalgaon. Based on your
business type, a single system for vehicle stock, purchases and sales could make margin
per vehicle easier to see.

We have a working demonstration for this type of business. If useful, I can share a short
demo and explain how it could be customised around how you work.

Regards, Sagar
Reply STOP and I will not message again.
```

---

## 6.8 The §26 industry-to-module map

One data table, keyed on `businesses.category`, used by three consumers: the message engine (this
document), the opportunity scorer (`radar/score.py`, for `opportunities.potential_solution`) and the
report's "Potential Solution" column (§9, §10).

It lives in code, not in the template bundle, because the scorer needs it before any template is
resolved:

```python
# radar/messages.py
@dataclass(frozen=True)
class ModuleProfile:
    category: str            # businesses.category
    industry: str            # businesses.industry
    solution_name: str       # -> opportunities.potential_solution
    module_keys: tuple[str, ...]      # ordered, §26 order preserved where §26 gives one
    relevant_area: str       # WhatsApp single phrase
    source: str              # 'SPEC_26' | 'DERIVED'

MODULE_MAP: dict[str, ModuleProfile] = {...}   # the table below, verbatim
```

### 6.8.1 The map

| `category` | `industry` | `solution_name` | `module_keys` (ordered) | `relevant_area` (WhatsApp) | Source |
|---|---|---|---|---|---|
| `HOSPITAL` | `HEALTHCARE` | Hospital Operations Platform | `PATIENTS, APPOINTMENTS, DEPARTMENTS, BILLING, INVENTORY, REPORTS` | patient records, appointments and billing | §26 verbatim |
| `SCHOOL` | `EDUCATION` | School Management System | `STUDENTS, FEES, ATTENDANCE, STAFF, TRANSPORT, REPORTS` | student records, fees and attendance | §26 verbatim |
| `COLLEGE` | `EDUCATION` | College Management System | `ADMISSIONS, STUDENTS, DEPARTMENTS, FEES, EXAMINATIONS, REPORTS` | admissions, fees and examination records | §26 verbatim |
| `MANUFACTURER` | `MANUFACTURING` | Manufacturing Management Platform | `INVENTORY, PRODUCTION, PURCHASING, SALES, QUALITY, REPORTS` | inventory, production and purchase tracking | §26 verbatim |
| `DISTRIBUTOR` | `DISTRIBUTION` | Distribution Management System | `INVENTORY, ORDERS, CUSTOMERS, RECEIVABLES, SALES, REPORTS` | inventory, orders and receivables | §26 verbatim (`REPORTS` appended) |
| `BAKERY` | `RETAIL` | Bakery Operations System | `ORDERS, PRODUCTION, INVENTORY, DELIVERY, CUSTOMERS, PAYMENTS` | orders, production and delivery | §26 verbatim |
| `RETAIL_STORE` | `RETAIL` | Retail Inventory and Sales System | `INVENTORY, VARIANTS, PURCHASING, SALES, CUSTOMERS, PROFITABILITY` | stock, variants and sales | §26 "Clothing business" |
| `VEHICLE_DEALER` | `AUTOMOBILE` | Dealership Management System | `INVENTORY, PURCHASES, EXPENSES, SALES, PROFIT, CUSTOMERS` | vehicle stock, purchases and sales | §26 verbatim |
| `DIAGNOSTIC_CENTER` | `HEALTHCARE` | Diagnostic Centre Operations Platform | `PATIENTS, TEST_ORDERS, SAMPLES, REPORTS, BILLING, INVENTORY` | test orders, reports and billing | Derived |
| `GARAGE` | `AUTOMOBILE` | Service Workshop Management System | `JOB_CARDS, SPARES, LABOUR, BILLING, CUSTOMERS, REPORTS` | job cards, spare parts and billing | Derived |
| `HOTEL` | `HOSPITALITY` | Hotel Operations Platform | `ROOMS, BOOKINGS, GUESTS, HOUSEKEEPING, BILLING, REPORTS` | bookings, room status and billing | Derived |
| `RESTAURANT` | `HOSPITALITY` | Restaurant Operations System | `ORDERS, TABLES, MENU, INVENTORY, BILLING, REPORTS` | orders, inventory and billing | Derived |
| `REAL_ESTATE_AGENCY` | `REAL_ESTATE` | Property Sales Management System | `LISTINGS, ENQUIRIES, SITE_VISITS, BOOKINGS, PAYMENTS, REPORTS` | listings, enquiries and bookings | Derived |
| `OTHER` | (any) | Custom Business Management System | `DASHBOARD, WORKFLOW, FINANCE, INVENTORY, REPORTS, ROLES, AUDIT` | day-to-day operations and reporting | §13 generic |

Derivation rules used for the five categories §26 omits, so a sixth can be added consistently:
six module keys maximum; the first three are the ones the business would name if asked what it tracks
daily; `REPORTS` or `PAYMENTS`/`BILLING` closes the list; nothing that implies a claim about how the
business currently works.

### 6.8.2 Industry-level fallback

Used only when `businesses.category = 'OTHER'`:

| `industry` | `solution_name` | `module_keys` | `relevant_area` |
|---|---|---|---|
| `HEALTHCARE` | Healthcare Operations Platform | `PATIENTS, APPOINTMENTS, BILLING, INVENTORY, REPORTS` | patient records and billing |
| `EDUCATION` | Education Management System | `STUDENTS, FEES, ATTENDANCE, STAFF, REPORTS` | student records and fees |
| `AUTOMOBILE` | Automotive Business Management System | `INVENTORY, PURCHASES, SALES, CUSTOMERS, REPORTS` | stock, sales and customers |
| `MANUFACTURING` | Manufacturing Management Platform | `INVENTORY, PRODUCTION, PURCHASING, SALES, REPORTS` | inventory and production |
| `RETAIL` | Retail Management System | `INVENTORY, SALES, PURCHASING, CUSTOMERS, REPORTS` | stock and sales |
| `HOSPITALITY` | Hospitality Operations System | `BOOKINGS, ORDERS, INVENTORY, BILLING, REPORTS` | bookings and billing |
| `DISTRIBUTION` | Distribution Management System | `INVENTORY, ORDERS, RECEIVABLES, CUSTOMERS, REPORTS` | orders and receivables |
| `REAL_ESTATE` | Property Business Management System | `LISTINGS, ENQUIRIES, PAYMENTS, CUSTOMERS, REPORTS` | listings and enquiries |
| `PROFESSIONAL_SERVICES` | Practice Management System | `CLIENTS, ENGAGEMENTS, DOCUMENTS, BILLING, REPORTS` | client records and billing |
| `OTHER` | Custom Business Management System | `DASHBOARD, WORKFLOW, FINANCE, INVENTORY, REPORTS, ROLES, AUDIT` | day-to-day operations and reporting |

### 6.8.3 Module labels

`module_keys` are stable identifiers; the text a message prints is a label, and labels differ by
category (a `REPORTS` module is "reports" everywhere, but `INVENTORY` is "stock" in a retail store and
"inventory" in a factory).

```yaml
# radar/templates/messages/slots/slots.v4.yaml (extract)
module_labels:
  default:
    PATIENTS: "patient records"
    APPOINTMENTS: "appointments"
    DEPARTMENTS: "departments"
    BILLING: "billing"
    INVENTORY: "inventory"
    REPORTS: "reports"
    STUDENTS: "student records"
    FEES: "fees"
    ATTENDANCE: "attendance"
    STAFF: "staff records"
    TRANSPORT: "transport"
    ADMISSIONS: "admissions"
    EXAMINATIONS: "examinations"
    PRODUCTION: "production"
    PURCHASING: "purchasing"
    PURCHASES: "purchases"
    SALES: "sales"
    QUALITY: "quality checks"
    ORDERS: "orders"
    CUSTOMERS: "customer records"
    RECEIVABLES: "receivables"
    DELIVERY: "delivery"
    PAYMENTS: "payments"
    VARIANTS: "size and colour variants"
    PROFITABILITY: "profitability"
    EXPENSES: "expenses"
    PROFIT: "profit per unit"
    TEST_ORDERS: "test orders"
    SAMPLES: "sample tracking"
    JOB_CARDS: "job cards"
    SPARES: "spare parts"
    LABOUR: "labour hours"
    ROOMS: "room status"
    BOOKINGS: "bookings"
    GUESTS: "guest records"
    HOUSEKEEPING: "housekeeping"
    TABLES: "table management"
    MENU: "menu and recipes"
    LISTINGS: "property listings"
    ENQUIRIES: "enquiries"
    SITE_VISITS: "site visits"
    CLIENTS: "client records"
    ENGAGEMENTS: "engagements"
    DOCUMENTS: "documents"
    DASHBOARD: "a management dashboard"
    WORKFLOW: "workflow"
    FINANCE: "finance tracking"
    ROLES: "role management"
    AUDIT: "audit logs"
  overrides:
    RETAIL_STORE: { INVENTORY: "stock" }
    BAKERY:       { PRODUCTION: "daily production", INVENTORY: "ingredient stock" }
    GARAGE:       { INVENTORY: "spare parts stock" }
    HOTEL:        { INVENTORY: "supplies" }
```

### 6.8.4 Reconciling with `opportunity_modules`

The map is the vocabulary; `opportunity_modules` is what the research actually recommended for *this*
business (§13). The message must never name a module the research did not recommend, and must never
name a module outside the category's vocabulary.

```python
def resolve_modules(conn, business_id: str, profile: ModuleProfile, *, k: int = 3) -> ModuleChoice:
    """Pick the module labels the message is allowed to print.

    1. Read opportunity_modules for the current opportunity, ordered by rank.
    2. Keep only keys present in profile.module_keys (the intersection - a recommended module
       outside the category vocabulary means the scorer and the map disagree; log at WARNING
       and drop it rather than print a module this category has no label for).
    3. If >= 2 survive: relevant = first k of them.
       Else: relevant = first k of profile.module_keys (the map is the documented fallback).
    4. allowed_labels = labels for the whole of profile.module_keys, plus config
       identity.demo_modules ∩ profile.module_keys for the demo sentence.

    Returns relevant (for {{ relevant_modules }}), demo (for {{ modules }}), allowed_labels
    (rule M1's allowlist) and source ('OPPORTUNITY' | 'MAP_FALLBACK').
    """
```

`{{ relevant_modules }}` renders as an Oxford-comma-free list: `"a, b and c"`. `{{ modules }}` renders
the full ordered `module_keys` list. Both are recorded in `slot_values`, and `allowed_labels` is
recorded in the claim map's header so the policy engine can enforce `M1` from the stored draft alone.

---

## 6.9 The policy engine

This is the part that matters. It runs on **every** draft — freshly generated, LLM-rewritten, or
hand-edited by Sagar — before the draft is displayable as approvable, and its result is stored.

### 6.9.1 Where it runs

| Trigger | Caller | Effect on `outreach_messages.status` |
|---|---|---|
| Draft generated (step 3, `05-outreach-workflow.md`) | `radar/messages.py` job | `DRAFT` -> `PENDING_APPROVAL` (PASS/WARN) or `POLICY_BLOCKED` (BLOCK) |
| Draft edited by Sagar | `POST /api/v1/outreach/drafts/<draft_id>/edit` | `PENDING_APPROVAL` -> `DRAFT` -> re-check -> `PENDING_APPROVAL` or `POLICY_BLOCKED` |
| Draft regenerated | `POST /api/v1/outreach/drafts/<draft_id>/regenerate` | new `outreach_drafts` row; old row gets `superseded_by` |
| Approval attempted | `POST /api/v1/outreach/drafts/<draft_id>/approve` | Refuses if `policy_result = 'BLOCK'` **or** `policy_checked_body_hash <> sha256(final)` |
| Policy version bump | `radar/policy.py` CLI `recheck --since` | Re-checks every draft not yet `SENT`, rewrites `policy_result` |

The engine never mutates the message. It reads text and returns a verdict.

**It always reads the hydrated text.** The contact greeting is substituted into the body locally,
after generation and before the draft row is written (§6.13.0), so `check_draft()` and
`policy_checked_body_hash` cover the message *including* the substituted value. There is no ordering
in which a substitution can land in a message the checker did not read: hydration is a step of
`draft_outreach`, not of the send path, and the send path has nothing left to substitute.

### 6.9.2 Sentence segmentation

The claim map is indexed by segment, so the checker and the generator must agree on what a segment
is. They agree because **the checker segments and the generator's map is matched onto that
segmentation** — never the other way round.

```python
_ABBREV = {"dr", "mr", "mrs", "ms", "pvt", "ltd", "co", "no", "e.g", "i.e", "sr", "jr", "st"}

def segment(subject: str | None, body: str) -> list[Segment]:
    """Deterministic segmentation. Segment 0 is the subject when the channel has one.

    Rules, in order:
      1. Split the body on blank lines into blocks; keep the block index.
      2. A line starting with '-', '*' or a digit followed by '.' or ')' is its own segment.
      3. Inside a block, split after [.!?] followed by whitespace and an uppercase letter or
         a digit, unless the token before the punctuation is in _ABBREV or is a single
         initial (one letter).
      4. Trailing whitespace stripped; internal whitespace collapsed to single spaces.
      5. Segments shorter than 3 characters are merged into the previous segment.
    """


def normalise(text: str) -> str:
    """casefold, collapse whitespace, strip terminal punctuation. Used for map matching only."""
```

Matching the model's claim entries onto those segments:

```python
def bind_claims(segments: list[Segment], claim_map: ClaimMap) -> list[BoundSegment]:
    """Attach each claim entry to exactly one segment.

    1. Exact match on normalise(entry.text) == normalise(segment.text).
    2. Otherwise the highest-TSR segment with TSR >= 0.95, if unique.
    3. Otherwise the entry is unmatched -> rule T3.
    A segment with no entry attached is 'unbound' and goes to the classifier in 6.9.3.
    """
```

### 6.9.3 Fact binding (rules F1-F5)

Every segment is assigned a claim type. Two sources: the slot catalogue (for text the template
produced, matched via `slot_values`), and a classifier for anything else (edited text, rewritten
text). The classifier is lexical and conservative:

```python
def classify_segment(seg: Segment, ctx: DraftContext) -> str:
    """Return a claim type from 6.3.5. Conservative: when unsure, FACTUAL.

    IDENTITY / COMPLIANCE / GREETING : matched against the rendered identity, unsubscribe and
        greeting slot values byte-for-byte (these are frozen spans).
    SELF / SELF_CAPABILITY : first-person subject ('we', 'I') AND the object is our company,
        our software or a demonstration - i.e. no second-person possessive ('your ...') and
        no reference to the recipient's operations.
    PROCESS : first-person subject AND a research verb ('researching', 'reviewed', 'came
        across', 'looked at') AND an object that is public information.
    OFFER : contains the solution_name, or a conditional construction about what we would
        build ('we build', 'what we build', 'a system that would').
    CTA : ends with an offer to meet, call or demonstrate, and contains no assertion about
        the recipient.
    FACTUAL : everything else, including every segment containing a second-person
        possessive ('your'), the business name in subject position, or a present-tense
        statement about the recipient's operations.
    """
```

The bias is the whole design: an unclassifiable sentence is `FACTUAL`, and a `FACTUAL` sentence with
no binding is a `BLOCK`. The engine's failure mode is refusing a safe message, never passing an
unsafe one.

| Rule | Name | Severity | Condition | Remedy shown to Sagar |
|---|---|---|---|---|
| `F1` | `UNBOUND_ASSERTION` | BLOCK | A `FACTUAL` segment has zero `finding_ids` | "Sentence N asserts something about the business with no research behind it. Cite a finding, hedge it, or delete it." |
| `F2` | `BINDING_NOT_FOUND` | BLOCK | A cited `finding_id` does not exist, belongs to another `business_id`, or is not from the current `research_runs` row | "Sentence N cites research that is not this business's current research." |
| `F3` | `PROCESS_CLAIM_UNSUPPORTED` | BLOCK | A `PROCESS` segment exists but there is no `research_runs` row with `status='COMPLETE'` for this business, or zero `sources` rows | "The message says we reviewed public information. There is no completed research run to back that." |
| `F4` | `SOURCELESS_FINDING` | BLOCK | A cited finding has zero `finding_sources` rows | "Sentence N cites a finding with no source. Findings without sources are not citable." |
| `F5` | `STALE_RESEARCH` | WARN | A cited finding's `sources.checked_at` is older than `policy.max_finding_age_days` (default 180) | "Sentence N is based on information checked N days ago. Re-research or soften." |

Binding SQL:

```sql
-- radar/policy.py :: BINDING_SQL  (one call, all cited ids)
SELECT f.id,
       f.kind,                 -- OBSERVED | INFERRED | UNKNOWN
       f.statement,
       f.confidence,
       f.confidence_pct,
       f.business_id,
       f.research_run_id,
       COUNT(fs.source_id)        AS n_sources,
       MAX(s.checked_at)          AS latest_checked_at
  FROM research_findings f
  LEFT JOIN finding_sources fs ON fs.finding_id = f.id
  LEFT JOIN sources         s  ON s.id = fs.source_id
 WHERE f.id IN (/* :ids expanded */)
 GROUP BY f.id;
```

### 6.9.4 Kind discipline (rules K1-K4)

This is §23 in executable form.

**`OBSERVED` may be stated.** No hedge required. Rule `K4` warns when an `OBSERVED` finding whose own
`confidence` is `LOW` is stated flatly.

**`INFERRED` must be hedged.** At least one hedge marker must appear **inside the same segment**:

```python
HEDGE_RE = re.compile(r"""\b(
      may | might | could | can\s+potentially | would\s+typically | typically | often | usually
    | we\s+believe | we\s+think | it\s+is\s+possible\s+that | it\s+may\s+be
    | appears?\s+to | seems?\s+to | suggests?\s+that
    | based\s+on\s+the\s+nature\s+of | based\s+on\s+the\s+scale
    | in\s+businesses\s+of\s+this\s+type | for\s+a\s+business\s+of\s+this\s+size
    | if\s+that\s+is\s+the\s+case | where\s+relevant | potentially
)\b""", re.I | re.X)
```

A hedge inside a *different* sentence does not count. "Your billing is manual. We believe a system
could help." leaves the first sentence unhedged, and the first sentence is the one that gets the
reply.

**`UNKNOWN` must not appear at all.** Two rules, because there are two ways it leaks:

- `K2` — the claim map cites an `UNKNOWN` finding. Trivial to detect.
- `K3` — the body says the thing anyway, without citing it. Detected by comparing every `FACTUAL`
  segment against every `UNKNOWN` finding's `statement` for this business:
  `TSR(skeleton(segment), skeleton(statement)) >= policy.unknown_overlap_threshold` (default 0.55).
  A hit is a BLOCK with both texts shown side by side, because the honest fix is to delete the
  sentence, not to reword it past the threshold.

| Rule | Name | Severity | Condition |
|---|---|---|---|
| `K1` | `INFERRED_UNHEDGED` | BLOCK | Segment bound to an `INFERRED` finding contains no `HEDGE_RE` match |
| `K2` | `UNKNOWN_CITED` | BLOCK | Claim map cites a finding with `kind = 'UNKNOWN'` |
| `K3` | `UNKNOWN_LEAKED` | BLOCK | A `FACTUAL` segment overlaps an `UNKNOWN` finding above threshold |
| `K4` | `LOW_CONFIDENCE_STATED` | WARN | Segment bound only to `OBSERVED` findings with `confidence = 'LOW'` and no hedge |

### 6.9.5 Banned assertive forms and banned phrases (rules A1-A8)

Derived directly from the §23 bad examples, then extended to the neighbouring failures.

```python
# radar/policy.py :: BANNED
FORBIDDEN_ASSERTIVE = [
    # §23 bad example 1: "We noticed that you are managing your hospital through Excel."
    (r"\bwe\s+(noticed|observed|saw|found|spotted|see)\b",                    "A1"),
    (r"\bwe\s+know\b",                                                        "A1"),
    (r"\bwe\s+understand\s+that\s+(you|your)\b",                              "A1"),
    (r"\bwe\s+can\s+see\s+that\s+(you|your)\b",                               "A1"),
    (r"\byou\s+are\s+(currently\s+)?(using|running|managing|handling|relying\s+on|"
     r"struggling|losing|wasting)\b",                                         "A1"),
    (r"\byou\s+(still\s+)?(use|run|manage|handle|rely\s+on)\b",               "A1"),
    # §23 bad example 2: "We know your company has inventory problems."
    (r"\byour\s+(problem|issue|pain\s*point|bottleneck|challenge)\s+is\b",    "A1"),
    (r"\byour\s+(company|business|organisation|organization|team)\s+has\s+"
     r"(a\s+|an\s+|serious\s+|major\s+)?(problem|issues?|difficult)",         "A1"),
    (r"\byou\s+(have|face|suffer\s+from)\s+(a\s+|an\s+)?(problem|issues?)\b", "A1"),
    (r"\b(clearly|obviously|evidently|no\s+doubt)\b",                         "A1"),
    (r"\byour\s+current\s+(system|software|process)\s+(is|does|cannot|can't)", "A1"),
]

FAKE_URGENCY = [
    (r"\b(limited\s+time|offer\s+expires?|expires\s+(today|tomorrow|soon))\b", "A2"),
    (r"\b(act\s+now|last\s+chance|final\s+(call|reminder)|don'?t\s+miss)\b",   "A2"),
    (r"\b(only\s+(a\s+)?few|few\s+slots?|limited\s+slots?|closing\s+soon)\b",  "A2"),
    (r"\b(this\s+week\s+only|today\s+only|hurry|urgent(ly)?\s+reply)\b",       "A2"),
]

UNBOUND_STATISTIC = [
    (r"\b\d{1,3}(\.\d+)?\s?%",                                                "A3"),
    (r"\b\d+\s?x\b",                                                          "A3"),
    (r"\b(hundreds|thousands|dozens)\s+of\s+(businesses|clients|customers)\b", "A3"),
    (r"\b(most|many|nine\s+out\s+of\s+ten)\s+(hospitals|schools|colleges|"
     r"manufacturers|dealers|businesses|companies)\b",                        "A3"),
    (r"\b(save|reduce|cut|increase|improve)\s+[^.]{0,20}\bby\s+\d",           "A3"),
]

FABRICATED_RELATIONSHIP = [
    (r"\bas\s+(discussed|promised|agreed|per\s+our\s+(call|conversation|meeting))\b", "A5"),
    (r"\b(following\s+up\s+on|further\s+to)\s+(our|my|the)\s+"
     r"(call|conversation|meeting|email|message)\b",                          "A5"),
    (r"\b(referred\s+by|on\s+the\s+recommendation\s+of|introduced\s+(to\s+you\s+)?by)\b", "A5"),
    (r"\b(your|a)\s+(colleague|friend|associate|contact)\s+(suggested|mentioned|told)\b", "A5"),
    (r"\bwe\s+(met|spoke)\s+(at|during|last)\b",                              "A5"),
    (r"\b(mutual|common)\s+(contact|connection|friend)\b",                    "A5"),
]

GUARANTEE = [
    (r"\bguarantee[ds]?\b",                                                   "A6"),
    (r"\b100\s?%\b",                                                          "A6"),
    (r"\b(will|shall)\s+(definitely\s+)?(reduce|increase|save|eliminate|fix|solve)\b", "A6"),
    (r"\brisk[- ]free\b",                                                     "A6"),
    (r"\bno\s+obligation\s+guarantee\b",                                      "A6"),
]

SUPERLATIVE = [
    (r"\b(best|leading|number\s*one|#\s*1|world[- ]class|cutting[- ]edge|"
     r"state[- ]of[- ]the[- ]art|revolutionary|game[- ]chang)\w*\b",          "A7"),
]

PRESSURE_CTA = [
    (r"\b(call|reply|respond|confirm)\s+(me\s+)?(back\s+)?(today|now|immediately|"
     r"right\s+away|within\s+\d+\s+hours?)\b",                                "A8"),
    (r"\bwhen\s+(can|shall)\s+we\s+(meet|talk)\s+(today|tomorrow)\b",         "A8"),
]
```

| Rule | Name | Severity | Notes |
|---|---|---|---|
| `A1` | `FORBIDDEN_ASSERTIVE` | BLOCK | The §23 forms. Matching is on the raw segment text, case-insensitive |
| `A2` | `FAKE_URGENCY` | BLOCK | There is no deadline. Inventing one is a lie about our own offer |
| `A3` | `UNBOUND_STATISTIC` | BLOCK | Any number, percentage or multiplier in a `FACTUAL`/`OFFER`/`SELF_CAPABILITY` segment that is not present verbatim in a bound finding's `statement`. Digits inside module counts, times ("twenty minutes") and the signature are allowlisted by segment type |
| `A4` | `INVENTED_CLIENT` | BLOCK | A capitalised multi-word proper noun in the body that is not the recipient's `business_name`, a city in `campaign_cities`, `identity.company_name`, a module label, or the `solution_name`. Catches "we did this for XYZ Hospital" |
| `A5` | `FABRICATED_RELATIONSHIP` | BLOCK | Unless `outreach_messages` already has a `SENT` row in the same `thread_key`, in which case `A5` degrades to WARN for the "following up" forms only |
| `A6` | `GUARANTEE` | BLOCK | Outcome promises we cannot keep |
| `A7` | `SUPERLATIVE` | WARN | Not dishonest, just bad; Sagar can send it |
| `A8` | `PRESSURE_CTA` | WARN | §24 says "short CTA", not "urgent CTA" |

### 6.9.6 PII and named individuals (rules P1-P4)

`_CONTEXT.md` §4: the moment a named individual's contact detail is stored it is personal data under
the DPDP Act 2023. The message engine's job is to keep personal data out of the message body unless
it is the recipient's own verified name.

```python
PERSONAL_IDENTIFIER = [
    (r"\b[A-Z]{5}\d{4}[A-Z]\b",                       "P2"),  # PAN
    (r"\b\d{4}\s?\d{4}\s?\d{4}\b",                    "P2"),  # Aadhaar-shaped
    (r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]Z[A-Z\d]\b", "P2"),  # GSTIN
    (r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b",               "P2"),  # a mobile number in the body
    (r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",                  "P2"),  # an email address in the body
    (r"\b(date\s+of\s+birth|d\.?o\.?b\.?)\b",         "P2"),
]

SENSITIVE_INFERENCE = [
    (r"\b(financial(ly)?\s+(trouble|distress|difficulty)|cash\s?flow\s+problem|"
     r"losing\s+money|near\s+bankrupt|debt)\b",       "P4"),
    (r"\b(illness|health\s+condition|caste|religion|political)\b", "P4"),
]
```

| Rule | Name | Severity | Condition |
|---|---|---|---|
| `P1` | `UNAUTHORISED_NAME` | BLOCK | A personal name appears in the body that is not `business_contacts.contact_name` for the draft's `contact_id`, where that row has `human_verified = 1`. Detection: a capitalised token in a greeting/vocative position, or a token matched against the campaign's name lexicon; the allowlist is exactly one name |
| `P2` | `PERSONAL_IDENTIFIER` | BLOCK | Any pattern above appears in the body. Sagar's own contact details are exempt: they are compared byte-for-byte against `config identity.*` and skipped. The exempt set is exactly `identity.reply_to`, `identity.phone_display` and `identity.unsubscribe_mailbox` — the last one is new, because the free-stack opt-out mechanism puts an email address in the body on purpose (§6.4), and a rule that blocks it would block every compliant message |
| `P3` | `THIRD_PARTY_INDIVIDUAL` | BLOCK | The body names a person other than the recipient contact and Sagar (a doctor, principal, proprietor found during research). Public research may know these names; a first-contact message has no reason to use them |
| `P4` | `SENSITIVE_INFERENCE` | BLOCK | The body infers financial distress, health, or any special-category attribute about the business or its people |

`P1` and `P3` together mean: a message addresses either a verified named contact or "the {{business_name}} team", and mentions no other human being.

### 6.9.7 Required elements (rules R1-R8)

| Rule | Name | Severity | Channel | Condition |
|---|---|---|---|---|
| `R1` | `MISSING_UNSUBSCRIBE` | BLOCK | `EMAIL` | Body must contain **all three**: `identity.unsubscribe_mailbox` byte-for-byte, a `[0-9a-f]{32}` token equal to `outreach_drafts.unsubscribe_token`, and an instruction matching `/\breply\s+STOP\b/i`. For `WHATSAPP`, only the `reply STOP` instruction is required. **Changed for the free stack:** this rule used to demand an `https://{sending_domain}/u/{token}` link. There is no public endpoint to host one (`_CONTEXT.md` §2), so the mechanism is `mailto:` per RFC 2369 (§6.4). All three elements are mandatory rather than any-one-of, because `mailto:` unsubscribe and `reply STOP` are now the **only** opt-out mechanisms in the system — there is no web page to fall back to |
| `R2` | `MISSING_IDENTITY` | BLOCK | all | Body does not contain, byte-for-byte, `identity.sender_name`, `identity.company_name` and (email) a reply address equal to `identity.reply_to` |
| `R3` | `SUBJECT_MISLEADING` | BLOCK | `EMAIL` | Subject is empty; or starts with `Re:`/`Fwd:`/`RE:`/`FW:` with no prior message in `thread_key`; or contains `A1`-`A6` matches; or contains no token in common with the body's content tokens (a subject unrelated to the message is a misleading subject); or is entirely uppercase for tokens longer than 3 characters; or contains more than one `!` |
| `R4` | `SUBJECT_LENGTH` | WARN | `EMAIL` | `len(subject) < 25` or `> 78` |
| `R5` | `MISSING_PURPOSE` | WARN | all | No `SELF` segment (the message never says who we are or why we are writing) |
| `R6` | `LENGTH_BUDGET` | WARN/BLOCK | `WHATSAPP`, `EMAIL` | §6.7.3 for WhatsApp. Email: WARN over 320 words, BLOCK over 500 |
| `R7` | `LINK_POLICY` | BLOCK | all | Any `http(s)` URL whose host is not `identity.site_host`; more than one such URL (email); any URL at all (WhatsApp); any `<img>`, tracking pixel or shortener host; any email address in the body other than `identity.reply_to` or `identity.unsubscribe_mailbox`. **Changed for the free stack:** `sending_domain` no longer exists — the from-address is a `gmail.com` account with no web presence, and `identity.site_host` is the static GitHub Pages identity page, which is the only URL this build is allowed to put in a message |
| `R8` | `MARKUP_IN_BODY` | BLOCK | all | Raw HTML tags, Jinja delimiters (`{{`, `{%`), or a leftover placeholder token matching `<<[A-Z_]+>>` or `<[A-Z_]{3,}>` in the body. The `<<...>>` form is the one that matters most: it is how the contact greeting travels through the model un-hydrated (§6.13.0), so this rule is what turns a failed substitution into a blocked draft instead of a message addressed to `<<CONTACT_GREETING>>` |

### 6.9.8 Module, offer and price discipline (rules M1-M3)

| Rule | Name | Severity | Condition |
|---|---|---|---|
| `M1` | `MODULE_NOT_IN_MAP` | BLOCK | A module-like noun phrase in the body is not in `allowed_labels` from `resolve_modules()`. The check is positive, not negative: the engine extracts every label from `module_labels` (all categories) present in the body and asserts membership in the allowlist. A label from another category is exactly the failure this catches (a school offered "production tracking") |
| `M2` | `CAPABILITY_NOT_DECLARED` | BLOCK | A `SELF_CAPABILITY` segment claims a demonstration covering a module not in `config identity.demo_modules`. We do not offer to demo what does not exist |
| `M3` | `PRICE_CLAIM` | BLOCK | Any currency amount (`₹`, `Rs.`, `INR`, `$`) or the words `price`, `pricing`, `cost per`, `quote` in the body. Pricing is a human conversation (§34, §55) |

### 6.9.9 Provenance and variation (rules T1-T3, V1-V2)

| Rule | Name | Severity | Condition |
|---|---|---|---|
| `T1` | `TEMPLATE_BUNDLE_UNPINNED` | BLOCK | `template_version` is NULL, malformed, or its bundle hash does not match the current files |
| `T2` | `CLAIM_MAP_MALFORMED` | BLOCK | `claim_map` is absent, not valid JSON, wrong `schema`, or has an entry without `text` / `type` |
| `T3` | `SEGMENT_UNMATCHED` | BLOCK | A claim entry could not be matched to any segment (§6.9.2 step 3). The map describes text that is not in the body |
| `V1` | `NEAR_DUPLICATE` | WARN/BLOCK | §6.6.3 thresholds |
| `V2` | `TEMPLATE_UNRENDERED` | BLOCK | Subsumed by `R8` for Jinja delimiters; also fires when a slot rendered as the literal string `None` or `[]` |

### 6.9.10 Verdict algebra

```python
def verdict(outcomes: list[RuleOutcome]) -> str:
    if any(o.status == "FIRED" and o.severity == "BLOCK" for o in outcomes):
        return "BLOCK"
    if any(o.status == "FIRED" and o.severity == "WARN" for o in outcomes):
        return "WARN"
    return "PASS"
```

- **PASS** — the draft is approvable. The preview shows a green POLICY CHECK panel (§51: green =
  verified/clear).
- **WARN** — the draft is approvable, and every fired WARN renders inline in the preview next to the
  sentence that caused it (yellow, §51). Sagar can approve anyway; the approval record stores the
  warnings he approved over (`outreach_approvals.displayed`).
- **BLOCK** — the draft is **not** approvable. `outreach_messages.status = 'POLICY_BLOCKED'`, the
  CONFIRM & SEND control is not rendered, and `POST .../approve` returns `409` with the rule list even
  if a client fabricates the request. `POLICY_BLOCKED -> SENT` is not in
  `outreach_status_transitions`, so the database refuses it too.

One escalation: three or more distinct WARN rules on a single draft escalate to BLOCK
(`policy.warn_escalation_count`, default 3). A message with three things slightly wrong with it is a
message worth regenerating.

### 6.9.11 The stored result

`outreach_drafts.policy_result` holds `PASS`/`WARN`/`BLOCK`; `policy_detail` holds this JSON;
`policy_version` and `policy_checked_at` are set in the same UPDATE.

```json
{
  "schema": "policy_result/v1",
  "policy_version": "policy@v1.4+rules@2026-08-20",
  "checked_at": "2026-08-27T11:42:08Z",
  "draft_id": "out_01JAV6QK3M7X2ZC5R9TB0DHNE4",
  "channel": "EMAIL",
  "verdict": "WARN",
  "counts": { "block": 0, "warn": 1, "pass": 27, "skipped": 4 },
  "body_hash": "sha256:5f0a...c31d",
  "segments": 14,
  "rules": [
    {
      "rule_id": "F1", "name": "UNBOUND_ASSERTION", "severity": "BLOCK",
      "status": "PASS", "segments": [], "detail": null
    },
    {
      "rule_id": "F5", "name": "STALE_RESEARCH", "severity": "WARN",
      "status": "FIRED", "segments": [4],
      "detail": "Finding res_01JAV5S8W2K4M6P8R0TC2VEXF7 was last checked 194 days ago.",
      "evidence": {
        "finding_id": "res_01JAV5S8W2K4M6P8R0TC2VEXF7",
        "checked_at": "2026-02-14T09:03:11Z",
        "age_days": 194,
        "threshold_days": 180
      },
      "remedy": "Re-run research for this business, or remove the observation sentence."
    },
    {
      "rule_id": "V1", "name": "NEAR_DUPLICATE", "severity": "WARN",
      "status": "PASS", "segments": [],
      "evidence": { "max_j3": 0.29, "max_tsr": 0.83,
                    "peer_message_id": "msg_01JAT9F1H4N6Q8S0U2W4Y6A8C1",
                    "corpus_size": 128, "window_days": 120 }
    }
  ],
  "similarity": { "max_j3": 0.29, "max_tsr": 0.83,
                  "peer_message_id": "msg_01JAT9F1H4N6Q8S0U2W4Y6A8C1" },
  "claim_summary": {
    "factual_segments": 3,
    "observed_ids": ["res_01JAV5S8W2K4M6P8R0TC2VEXF7"],
    "inferred_ids": ["res_01JAV5T1X3L5N7Q9S1UD3WFYG8"],
    "unknown_ids_present": [],
    "unbound_segments": []
  }
}
```

Every rule appears in `rules[]` with `status` in `PASS` / `FIRED` / `SKIPPED` (not applicable to this
channel). A rule that did not run is visible as `SKIPPED`, so a future reader can tell "the rule
passed" from "the rule did not exist yet".

### 6.9.12 Signatures

```python
# radar/policy.py
POLICY_VERSION = "policy@v1.4+rules@2026-08-20"

@dataclass(frozen=True)
class Segment:
    idx: int
    text: str
    block: int
    kind: str                      # claim type, filled by classify_segment
    slot: str | None               # the slot it came from, when known

@dataclass(frozen=True)
class ClaimEntry:
    text: str
    type: str
    finding_ids: tuple[str, ...]
    bound_by: str                  # 'MODEL' | 'TEMPLATE' | 'HUMAN'
    bound_at: str | None

@dataclass(frozen=True)
class RuleOutcome:
    rule_id: str
    name: str
    severity: str                  # 'BLOCK' | 'WARN'
    status: str                    # 'PASS' | 'FIRED' | 'SKIPPED'
    segments: tuple[int, ...]
    detail: str | None
    evidence: dict[str, Any] | None
    remedy: str | None

@dataclass(frozen=True)
class PolicyResult:
    verdict: str                   # 'PASS' | 'WARN' | 'BLOCK'
    rules: tuple[RuleOutcome, ...]
    similarity: SimilarityResult
    policy_version: str
    body_hash: str
    checked_at: str

    def to_row(self) -> dict[str, Any]: ...
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "PolicyResult": ...


def check_draft(
    conn: sqlite3.Connection,
    *,
    draft_id: str,
    subject: str | None,
    body: str,
    claim_map: ClaimMap,
    channel: str,
    business_id: str,
    template_version: str,
    slot_values: SlotValues,
    cfg: Config,
) -> PolicyResult:
    """Run every rule. No writes, no LLM, no network. Deterministic for a fixed database."""


def store_policy_result(
    conn: sqlite3.Connection, draft_id: str, result: PolicyResult, *, actor: str
) -> None:
    """One UPDATE on outreach_drafts + one outreach_events row (POLICY_PASS | POLICY_BLOCK)
    + the outreach_messages.status transition, in one transaction.

    Also writes policy_checked_body_hash = result.body_hash. That column is what the approve
    endpoint compares against; without it, an edit that skipped the checker would inherit the
    previous PASS.
    """
```

### 6.9.13 Versioning and re-checking

`POLICY_VERSION` is `policy@<engine semver>+rules@<date the rule table last changed>`. It is stored
on every draft. When it changes:

```bash
python main.py policy recheck --since 2026-08-01 --dry-run
python main.py policy recheck --since 2026-08-01
```

Re-check applies to drafts whose message has not reached `SENT`. A `SENT` message's stored
`policy_result` is never rewritten — it is the record of what was true when it was approved. A rule
added later that would have blocked an already-sent message produces a report, not a mutation:

```sql
-- what would today's rules say about what we already sent?
SELECT m.id, m.business_id, d.policy_version, d.policy_result
  FROM outreach_messages m JOIN outreach_drafts d ON d.id = m.draft_id
 WHERE m.status IN ('SENT','DELIVERED') AND d.policy_version <> :current_version;
```

### 6.9.14 Worked run 1 — a draft that PASSES (SAMPLE)

Input: the hospital render from §6.5.1. Claim map as tabled there.

```
$ python main.py policy check --draft out_01JAV6QK3M7X2ZC5R9TB0DHNE4 --explain

DRAFT  out_01JAV6QK3M7X2ZC5R9TB0DHNE4   EMAIL   ABC Hospital (Dhule)   SAMPLE
BUNDLE email.base@v3+ind.hospital@v2+slots@v4+pools@v4#7c1ad93e   [T1 ok]
MODEL  gemini-2.5-flash   PROMPT msg-email-v3   REWRITE applied

SEGMENTS 14   FACTUAL 3   bound 3   unbound 0

  seg 4  FACTUAL  OBSERVED  res_...F7  "ABC Hospital appears in Dhule healthcare listings
                                        with four named departments and an online
                                        appointment enquiry form."
                  finding: "Website lists four departments; an appointment enquiry form is
                            present on the contact page."  conf HIGH (88)  sources: 2
                  [F1 ok] [F2 ok] [F4 ok] [F5 ok] [K-observed: statement permitted]

  seg 5  FACTUAL  INFERRED  res_...F9  "Based on the scale and nature of your operations,
                                        patient records, appointments and billing may be
                                        areas where centralised records reduce duplicate
                                        entry."
                  hedges matched: "based on the scale", "may"   [K1 ok]

  seg 7  FACTUAL  INFERRED  res_...F9  "That would typically mean one place to see today's
                                        appointments, department load and pending billing,
                                        rather than separate registers."
                  hedges matched: "would typically"             [K1 ok]

  A1..A8   no match
  P1..P4   no match      (greeting addresses "ABC Hospital team"; no person named)
  R1 ok    unsubscribe URL present, token matches draft
  R2 ok    identity.sender_name / identity.company_name / identity.reply_to all present
  R3 ok    R4 ok (52 chars)   R6 ok (231 words)   R7 ok (1 URL, sending domain)
  M1 ok    labels used: patient records, appointments, billing, inventory, reports,
           departments - all in allowed_labels
  M2 ok    M3 ok
  V1 ok    max_j3 0.29 vs msg_...C1   (corpus 128, window 120d)

VERDICT PASS      27 rules passed, 0 fired, 4 skipped (WhatsApp-only)
```

Effect: `outreach_messages.status` `DRAFT -> PENDING_APPROVAL`; `outreach_events` gets `POLICY_PASS`;
the preview renders the POLICY CHECK panel green.

### 6.9.15 Worked run 2 — a §23 "bad" sentence, rewritten into the §23 "good" one (SAMPLE)

The model's first attempt for the same hospital contains the §23 bad example verbatim:

```
... While researching businesses in Dhule we came across ABC Hospital.

We noticed that you are managing your hospital through Excel. A centralised system would
fix this.
...
```

with a claim map that binds sentence 4 to `res_...F7` (the finding that says "the website lists four
departments").

```
$ python main.py policy check --draft out_01JAV6QK3M7X2ZC5R9TB0DHNE4 --explain

  seg 4  FACTUAL  "We noticed that you are managing your hospital through Excel."
         [A1 FIRED] pattern \bwe\s+(noticed|observed|saw|found|spotted|see)\b
         [A1 FIRED] pattern \byou\s+are\s+(currently\s+)?(using|running|managing|...)\b
         [F2 FIRED] cited res_...F7 states: "Website lists four departments; an appointment
                    enquiry form is present on the contact page." The segment asserts a
                    different fact (spreadsheet use). Binding rejected.
         [F1 FIRED] after F2 rejection the segment has no valid binding.
         [K3 FIRED] overlaps UNKNOWN finding res_...U2 "Could not determine what software,
                    if any, is used for patient records." TSR 0.61 >= 0.55.

  seg 5  OFFER    "A centralised system would fix this."
         [A6 FIRED] pattern \b(will|shall)\s+... -> variant "would fix"
         [F1 FIRED] classified FACTUAL (asserts an outcome for the recipient), unbound.

VERDICT BLOCK     5 rules fired
```

Because every fired rule is in `REPAIRABLE` (§6.13.5), `radar/messages.py` runs one repair pass. The
exact feedback block appended to the conversation:

```
Your previous draft was rejected by the claim-safety checker. Fix it and return the same
JSON shape.

REJECTED SENTENCE 4: "We noticed that you are managing your hospital through Excel."
  A1  Uses a forbidden assertive form ("we noticed", "you are managing"). We did not observe
      this and cannot claim it.
  F2  The finding you cited (res_...F7) says: "Website lists four departments; an appointment
      enquiry form is present on the contact page." It does not support this sentence.
  K3  This restates UNKNOWN finding res_...U2: "Could not determine what software, if any, is
      used for patient records." UNKNOWN findings must not appear in the message at all.
  FIX Either state only what res_...F7 supports, or make this a hedged statement about what a
      hospital of this scale may benefit from, bound to INFERRED finding res_...F9.

REJECTED SENTENCE 5: "A centralised system would fix this."
  A6  Promises an outcome ("would fix").
  F1  No finding supports it.
  FIX Describe what the system does, hedged, bound to res_...F9.

AVAILABLE FINDINGS (unchanged from the original prompt) - use only these.
```

The repaired draft:

```
Based on the scale and nature of your operations, a centralized management system may help
provide better visibility across workflows and reporting.
```

which is §23's "good" wording verbatim, with the claim map entry:

```json
{ "text": "Based on the scale and nature of your operations, a centralized management system may help provide better visibility across workflows and reporting.",
  "type": "FACTUAL", "finding_ids": ["res_01JAV5T1X3L5N7Q9S1UD3WFYG8"], "bound_by": "MODEL" }
```

Re-check:

```
  seg 4  FACTUAL  INFERRED  res_...F9
         hedges matched: "based on the scale", "may"            [K1 ok]
         [A1 ok] [A6 ok] [F1 ok] [F2 ok] [K3 ok] TSR vs res_...U2 = 0.19

VERDICT PASS      repair_attempts = 1
```

The same substitution applied to the §23 second pair, for the manufacturer block:

| §23 | Text | Verdict | Rules |
|---|---|---|---|
| Bad | "We know your company has inventory problems." | BLOCK | `A1` (`we know`, `your company has ... problem`), `F1` (unbound) |
| Good | "We believe inventory visibility may be an area where a centralised system could provide value." | PASS | `K1` satisfied by `we believe`, `may`, `could`; bound to an `INFERRED` finding |

That "good" sentence is variant `opp.m3` in `industry/manufacturer.v2.yaml`, so the safe wording is
in the template rather than a thing the model has to rediscover on every draft.

### 6.9.16 Worked run 3 — a draft that BLOCKS and stays blocked (SAMPLE)

```
Subject: Urgent - inventory losses at SAMPLE Steel Industries

Hello SAMPLE Steel team,

Your colleague suggested I write to you. We know your company has inventory problems -
most manufacturers in Dhule lose around 20% of stock value every year, and you are still
running everything on paper.

We built the same system for ABC Steel Ltd and guaranteed a 30% reduction in stock losses.
Limited slots this month - reply today.

Regards, Sagar
```

```
$ python main.py policy check --draft out_01JAV7ZZ0Q9W3X5Y7A9C1E3G5J --explain

  seg 0  SUBJECT  "Urgent - inventory losses at SAMPLE Steel Industries"
         [R3 FIRED] subject contains an A2 urgency match and asserts a fact ("inventory
                    losses") that no finding supports.

  seg 3  FACTUAL  "Your colleague suggested I write to you."
         [A5 FIRED] pattern \b(your|a)\s+(colleague|friend|...)\s+(suggested|...)\b
         [F1 FIRED] unbound. [P3 FIRED] references an unnamed third-party individual.

  seg 4  FACTUAL  "We know your company has inventory problems - most manufacturers in
                   Dhule lose around 20% of stock value every year, and you are still
                   running everything on paper."
         [A1 FIRED] x2   [A3 FIRED] x2 ("20%", "most manufacturers")
         [F1 FIRED] unbound
         [K3 FIRED] overlaps UNKNOWN res_...U7 "Could not determine stock-keeping method."

  seg 5  FACTUAL  "We built the same system for ABC Steel Ltd and guaranteed a 30%
                   reduction in stock losses."
         [A4 FIRED] "ABC Steel Ltd" is not the recipient, a campaign city, our company or a
                    module label.
         [A6 FIRED] "guaranteed"   [A3 FIRED] "30%"   [F1 FIRED] unbound

  seg 6  CTA      "Limited slots this month - reply today."
         [A2 FIRED] x2   [A8 FIRED]

  R1 FIRED  no unsubscribe URL
  R2 FIRED  identity.company_name absent from the body

VERDICT BLOCK     18 rules fired across 5 segments
REPAIR            not attempted: A4 (invented client) is in NON_REPAIRABLE - a model that
                  invented a client reference is not trusted to repair itself.
```

Effect and what Sagar sees:

| Consequence | Where |
|---|---|
| `outreach_drafts.policy_result = 'BLOCK'`, full JSON in `policy_detail` | DB |
| `outreach_messages.status = 'POLICY_BLOCKED'` | DB, via the transition table |
| `outreach_events` row `POLICY_BLOCK`, `actor_type='SYSTEM'` | DB |
| `/outreach/<draft_id>` renders the message read-only, red POLICY CHECK panel, every fired rule against its sentence | UI |
| No CONFIRM & SEND control is rendered; `POST .../approve` returns `409 policy_blocked` | UI + API |
| Sagar's three options: **Edit** (goes through §6.10), **Regenerate** (new draft row), **Cancel** (`CANCELLED`) | UI |
| A Telegram notification is **not** sent — a blocked draft is a workflow event, not a lead | `radar/handoff.py` scope |

---

## 6.10 The human edit path

§45 makes Sagar the final decision-maker. That does not make him an exemption from the checker: a
hand-edited message is a message nobody has checked yet.

### 6.10.1 Flow

```
  PENDING_APPROVAL (or POLICY_BLOCKED)
        |
        | POST /api/v1/outreach/drafts/<draft_id>/edit
        |   { "subject": "...", "body": "...", "bindings": [ {...} ] }
        v
  1. store body_edited, edited_by, edited_at, edit_count += 1
  2. compute body_edit_diff = unified diff(body -> body_edited)
  3. status -> DRAFT                      (transition exists: PENDING_APPROVAL -> DRAFT)
  4. outreach_events: EDITED (actor_type HUMAN)
  5. audit_log row (aud_...), action 'DRAFT_EDITED'
  6. re-derive the claim map (6.10.3)
  7. check_draft() on the EDITED text
  8. store_policy_result() -> policy_checked_body_hash = sha256(edited)
        |
        +--> PASS/WARN -> PENDING_APPROVAL
        +--> BLOCK     -> POLICY_BLOCKED
```

Steps 1-8 are one transaction. There is no intermediate state in which an edited body is approvable
with a stale policy result.

### 6.10.2 The stored diff

```python
def edit_diff(original: str, edited: str, *, draft_id: str) -> str:
    """Unified diff, 3 lines of context, stored verbatim in outreach_drafts.body_edit_diff."""
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        edited.splitlines(keepends=True),
        fromfile=f"{draft_id}/generated", tofile=f"{draft_id}/edited", n=3,
    ))
```

SAMPLE:

```diff
--- out_01JAV6QK3M7X2ZC5R9TB0DHNE4/generated
+++ out_01JAV6QK3M7X2ZC5R9TB0DHNE4/edited
@@ -6,7 +6,7 @@
 ABC Hospital appears in Dhule healthcare listings with four named departments and an
-online appointment enquiry form. Based on the scale and nature of your operations,
-patient records, appointments and billing may be areas where centralised records reduce
-duplicate entry.
+online appointment enquiry form. Based on the scale and nature of your operations,
+patient records, appointments and billing may be areas where a single system reduces
+duplicate entry across departments.
```

A second edit diffs against the *generated* text again, not against the previous edit, so
`body_edit_diff` always answers one question: what did the human change about what the AI wrote.
Successive edits are recoverable from `audit_log` rows, which store the before/after body hashes.

### 6.10.3 Re-deriving the claim map after an edit

```python
def rebind_after_edit(
    old_map: ClaimMap, old_body: str, new_body: str, *, human_bindings: list[ClaimEntry]
) -> ClaimMap:
    """Carry forward what survived the edit; leave anything new unbound.

    1. Segment both bodies (6.9.2).
    2. For each new segment, find the old segment with the highest TSR.
         TSR >= 0.95  -> carry the old entry over unchanged (bound_by preserved).
         0.70 <= TSR < 0.95 -> carry the finding ids over but mark bound_by='HUMAN' and
                               re-run every rule against the NEW text (a hedge may have
                               been edited out - that is exactly K1's job).
         TSR < 0.70   -> no carry-over. The segment is new and unbound.
    3. Apply human_bindings from the request: Sagar may attach a finding id to a segment
       from the preview UI ("cite research" control). These enter as bound_by='HUMAN' with
       bound_at set.
    4. Never carry a binding onto a segment whose claim type changed.
    """
```

What Sagar can and cannot do from the edit screen:

| Action | Allowed | Why |
|---|---|---|
| Reword a sentence | yes | Re-checked; if he removes a hedge, `K1` blocks it |
| Attach a `research_findings` id to a sentence he wrote | yes | `bound_by = 'HUMAN'`, recorded in the audit. He is asserting he read the finding |
| Attach a finding id belonging to a different business | no | `F2` |
| Attach an `UNKNOWN` finding | no | `K2` |
| Mark a sentence as "not a claim" to skip binding | **no** | The classifier decides claim type. There is no override control, because an override control is the bypass |
| Approve a `BLOCK` draft | no | `409`, and the DB transition does not exist |
| Edit the unsubscribe line or the identity block | no | Frozen spans; `R1`/`R2` fire, and the send path rewrites the unsubscribe URL from the token regardless |

### 6.10.4 The final message

Exactly as `05-outreach-workflow.md` defines: `final_body = COALESCE(body_edited, body)`. The approve
endpoint hashes that, compares it to `policy_checked_body_hash`, and only then writes
`outreach_approvals.approved_body` + `approved_body_hash`. The send path transmits
`outreach_messages.body_final`, whose hash the `trg_om_send_needs_approval` trigger compares to the
approval. So the chain generated -> hydrated -> checked -> edited -> re-checked -> approved -> sent is
hash-linked end to end, and the message that was checked is the message that goes out.

Two ways someone might expect to slip text past the checker, and why neither works:

| Attempt | Why it fails |
|---|---|
| The local contact substitution (§6.13.0) inserts a name the model never wrote | Hydration runs **before** the draft row is written, so `check_draft()` sees the substituted text and `policy_checked_body_hash` is computed over it. `R8` also fires on any placeholder that hydration failed to replace, so a broken substitution blocks rather than sends |
| Sagar edits the body and pastes in a contact detail | The edit endpoint sets `policy_checked_body_hash = NULL` and re-runs the checker; `P2` blocks any email address or phone number that is not one of the three exempt `identity.*` values, so pasting the recipient's mobile number into the body BLOCKs. Approving without a re-check returns `409` |

The one thing that is deliberately **not** in the body is the recipient's email address: it is an
envelope field, read from `business_contacts.value_norm` by `radar/channels/email.py` at send time
(`07-email-integration.md`). It never enters a prompt, never enters the draft body, and never enters
the claim map.

---

## 6.11 What the message engine contributes to the §27 preview

The preview screen is `05-outreach-workflow.md`'s (step 5, route `/outreach/<draft_id>`). This
document owns the data behind four of its nine panels.

| §27 panel | Source | Owner |
|---|---|---|
| BUSINESS | `businesses` | 05 |
| CHANNEL | `outreach_drafts.channel` | 05 |
| CONTACT | `business_contacts` | 05 |
| **RESEARCH BASIS** | The claim map, joined to `research_findings` + `sources`: every `FACTUAL` sentence rendered with its finding statement, kind badge, confidence badge and source links | **06** |
| **OPPORTUNITY** | `opportunities` + `opportunity_modules` + `resolve_modules()` source flag (`OPPORTUNITY` / `MAP_FALLBACK`) | **06** |
| **GENERATED MESSAGE** | `subject` + `COALESCE(body_edited, body)`, with per-sentence hover showing its binding | **06** |
| **AI CONFIDENCE** | `ai_confidence`, `ai_confidence_pct`, plus `model_id`, `prompt_version`, `template_version`, `rewrite_applied` | **06** |
| **POLICY CHECK** | `policy_result` + `policy_detail`, rendered per rule and inline per sentence | **06** |
| CONTACT HISTORY | `outreach_messages` + `responses` for the business | 05 |

The RESEARCH BASIS panel's rendering rules are the ones already stated in
`05-outreach-workflow.md` §5.5.3(b): `OBSERVED` plain with sources, `INFERRED` prefixed "Inferred:",
`UNKNOWN` greyed and marked "Not verified". An `UNKNOWN` finding is shown in the panel (so Sagar can
see what we do *not* know) and can never appear in the message (rules `K2`, `K3`).

```
GET /api/v1/outreach/drafts/<draft_id>/preview   ->  200
{
  "draft_id": "out_...",
  "channel": "EMAIL",
  "subject": "...",
  "body": "...",
  "segments": [
    { "idx": 4, "text": "...", "type": "FACTUAL", "kind": "OBSERVED",
      "findings": [ { "id": "res_...F7", "statement": "...", "confidence": "HIGH",
                      "confidence_pct": 88,
                      "sources": [ { "id": "src_...", "name": "SAMPLE hospital website",
                                     "url": "https://...", "source_type": "WEBSITE",
                                     "checked_at": "2026-02-14T09:03:11Z" } ] } ],
      "warnings": [ "F5" ] }
  ],
  "policy": { /* the 6.9.11 payload */ },
  "ai": { "model_id": "gemini-2.5-flash", "prompt_version": "msg-email-v3",
          "template_version": "email.base@v3+ind.hospital@v2+slots@v4+pools@v4#7c1ad93e",
          "confidence": "MEDIUM", "confidence_pct": 71, "rewrite_applied": true,
          "repair_attempts": 1 },
  "modules": { "relevant": ["patient records","appointments","billing"],
               "source": "OPPORTUNITY" }
}
```

---

## 6.12 The §49 AI message audit record

§49: store the original research, facts used, inferences used, prompt/version, generated message,
policy result, human edits, final message, approval and send result — "so Sagar can understand
exactly why the AI generated the message".

### 6.12.1 The view

```sql
-- radar/migrations/018_message_engine.sql (continued)
CREATE VIEW v_ai_message_audit AS
SELECT
    d.id                          AS draft_id,
    d.business_id,
    b.name                        AS business_name,
    b.city,
    b.category,
    b.industry,
    d.campaign_id,
    d.channel,
    d.sequence_no,

    -- WHAT THE AI WAS GIVEN
    (SELECT r.id FROM research_runs r
      WHERE r.business_id = d.business_id AND r.status = 'COMPLETE'
      ORDER BY r.finished_at DESC LIMIT 1)          AS research_run_id,
    d.facts_used,                 -- JSON array of OBSERVED research_findings ids
    d.inferences_used,            -- JSON array of INFERRED research_findings ids
    d.slot_values,                -- JSON, the layer-3 inputs actually substituted

    -- HOW IT WAS ASKED
    d.model_id,
    d.prompt_version,
    d.template_version,
    d.industry_block,
    d.variant_seed,
    d.variant_ids,
    d.input_tokens,
    d.output_tokens,
    d.quota_requests,

    -- WHAT IT PRODUCED
    d.raw_generation,             -- JSON, the model reply before any post-processing
    d.subject,
    d.body,
    d.claim_map,
    d.ai_confidence,
    d.ai_confidence_pct,
    d.rewrite_applied,
    d.repair_attempts,
    d.similarity_max,
    d.similarity_peer_id,

    -- WHAT THE CHECKER SAID
    d.policy_result,
    d.policy_detail,
    d.policy_version,
    d.policy_checked_at,
    d.policy_checked_body_hash,

    -- WHAT THE HUMAN DID
    d.body_edited,
    d.body_edit_diff,
    d.edit_count,
    d.edited_by,
    d.edited_at,
    COALESCE(d.body_edited, d.body)                 AS final_body,

    -- APPROVAL
    a.id                          AS approval_id,
    a.approved_by,
    a.approved_at,
    a.approved_body_hash,
    a.confirmation_text,
    a.session_auth_method,

    -- SEND RESULT
    m.id                          AS message_id,
    m.status                      AS message_status,
    m.to_address_display,
    m.provider,
    m.provider_message_id,
    m.provider_status_code,
    m.sent_at,
    m.delivered_at,
    m.failure_code,
    m.failure_detail
FROM outreach_drafts d
JOIN businesses b               ON b.id = d.business_id
LEFT JOIN outreach_messages m   ON m.draft_id = d.id
LEFT JOIN outreach_approvals a  ON a.message_id = m.id AND a.revoked_at IS NULL;
```

### 6.12.2 The exact row (SAMPLE)

```
$ python main.py audit message --draft out_01JAV6QK3M7X2ZC5R9TB0DHNE4
```

| Column | Value (SAMPLE) |
|---|---|
| `draft_id` | `out_01JAV6QK3M7X2ZC5R9TB0DHNE4` |
| `business_id` / `business_name` | `biz_01JAV4R7T9V1X3Z5B7D9F1H3K5` / `ABC Hospital` |
| `city` / `category` / `industry` | `Dhule` / `HOSPITAL` / `HEALTHCARE` |
| `campaign_id` | `cmp_01JAV3M5P7R9T1V3X5Z7B9D1F3` |
| `channel` / `sequence_no` | `EMAIL` / `1` |
| `research_run_id` | `res_01JAV5R6S8U0W2Y4A6C8E0G2J4` |
| `facts_used` | `["res_01JAV5S8W2K4M6P8R0TC2VEXF7"]` |
| `inferences_used` | `["res_01JAV5T1X3L5N7Q9S1UD3WFYG8"]` |
| `slot_values` | `{"business_name":"ABC Hospital","city":"Dhule","size_word":"medium-sized","observed_detail":"four named departments and an online appointment enquiry form","relevant_modules":"patient records, appointments and billing","modules":"patients, appointments, departments, billing, inventory and reports","solution_name":"Hospital Operations Platform"}` |
| `model_id` | `gemini-2.5-flash` |
| `prompt_version` | `msg-email-v3` |
| `template_version` | `email.base@v3+ind.hospital@v2+slots@v4+pools@v4#7c1ad93e` |
| `industry_block` | `industry/hospital.v2.yaml` |
| `variant_seed` | `4b8f1c2e9d07a5136e0f8b47c2a91d5e3f60b8927ac4d1e5f30b6a72c98d4e10` |
| `variant_ids` | `{"subject":"sub.2","self_intro":"intro.1","process":"proc.2","observation":"obs.h2","opportunity":"opp.h3","benefit":"ben.h1","cta":"cta.2"}` |
| `input_tokens` / `output_tokens` | `3412` / `984` |
| `quota_requests` | `3` (generate + rewrite + one repair) |
| `raw_generation` | `{"subject":"...","body":"...","claim_map":{...},"confidence":{"level":"MEDIUM","pct":71,"why":"one OBSERVED finding with two sources; the operational inference is category-level, not business-specific"}}` |
| `subject` | `A possible operations system for ABC Hospital, Dhule` |
| `body` | (the §6.5.1 render) |
| `claim_map` | (the §6.5.1 table, as `claim_map/v1` JSON) |
| `ai_confidence` / `ai_confidence_pct` | `MEDIUM` / `71` |
| `rewrite_applied` / `repair_attempts` | `1` / `1` |
| `similarity_max` / `similarity_peer_id` | `0.29` / `msg_01JAT9F1H4N6Q8S0U2W4Y6A8C1` |
| `policy_result` | `WARN` |
| `policy_detail` | (the §6.9.11 payload) |
| `policy_version` | `policy@v1.4+rules@2026-08-20` |
| `policy_checked_at` | `2026-08-27T11:42:08Z` |
| `policy_checked_body_hash` | `sha256:5f0a...c31d` |
| `body_edited` | (the §6.10.2 edited text) |
| `body_edit_diff` | (the §6.10.2 diff) |
| `edit_count` / `edited_by` / `edited_at` | `1` / `usr_01JAV0A1B2C3D4E5F6G7H8J9K0` / `2026-08-27T11:51:44Z` |
| `final_body` | = `body_edited` |
| `approval_id` / `approved_by` / `approved_at` | `apr_01JAV8B2D4F6H8K0M2P4R6T8V0` / `usr_01JAV0A1...` / `2026-08-27T11:53:02Z` |
| `approved_body_hash` | `sha256:5f0a...c31d` (equal to `policy_checked_body_hash`) |
| `confirmation_text` | `You are about to contact this business using the selected business contact.` |
| `session_auth_method` | `PASSWORD_TOTP` |
| `message_id` / `message_status` | `msg_01JAV8C3E5G7J9L1N3Q5S7U9W1` / `SENT` |
| `to_address_display` | `contact@sample-abchospital.in` |
| `provider` / `provider_message_id` / `provider_status_code` | `gmail_smtp` / `<9c1f...@mail.gmail.com>` / `250` |
| `sent_at` / `delivered_at` | `2026-08-27T11:53:09Z` / `2026-08-27T11:53:14Z` |
| `failure_code` / `failure_detail` | — / — |

### 6.12.3 Export

```
GET /api/v1/outreach/drafts/<draft_id>/audit          -> 200 application/json
GET /api/v1/outreach/drafts/<draft_id>/audit?format=html -> 200 text/html (self-contained)
```

The JSON is the view row plus two resolved sub-objects the view cannot carry: the full text of every
finding in `facts_used` / `inferences_used` with its sources, and the `research_runs` row's own
`model_id` / `prompt_version`. That is the answer to "why did the AI say that": the sentence, the
finding, the source URL, the date it was checked, the prompt that was used and the rule that let it
through.

Retention: the audit row lives as long as the draft. `_CONTEXT.md` §4 purpose-limitation means a
`suppressions` row for a business triggers redaction of `to_address_display` and `slot_values`
contact fields in the audit export after `retention.contact_days` (default 365), while the message
text, policy result and approval record are kept — the compliance record must outlive the contact
detail.

---

## 6.13 The Gemini API call

**Changed for the free stack.** This whole section used to describe an `anthropic` call to
`claude-opus-5` with a rupee cost table. `_CONTEXT.md` §2 now binds the build to `gemini-2.5-flash`
on the Google AI Studio **free tier**, called through `google-genai`. Three things change: the SDK
and its parameter names, the response-schema dialect (§6.13.4), and the budget, which is a quota
budget rather than a money budget (§6.13.6). One thing is added: §6.13.0, which did not need saying
when the provider contractually did not train on the traffic.

### 6.13.0 The PII rule: no contact value ever reaches the model

`_CONTEXT.md` §2, consequence 1: **free-tier content may be used by Google to improve their
products.** A proprietor's mobile number, sent to a free API as part of a drafting prompt, is a
contact detail Sagar collected for one purpose being handed to a third party for another. Under the
DPDP Act that is a purpose-limitation failure, and it is not one a disclaimer fixes.

So the rule is absolute and mechanical:

> **No value from any column of `business_contacts` may appear in any payload sent to an LLM.**
> Not the email, not the phone, not the WhatsApp id, not `contact_name`, not `designation`.

What the drafting call **does** receive, and why none of it is a contact value:

| Given to the model | Source | Why it is safe |
|---|---|---|
| Business name, city, category, industry, size band | `businesses` | A business name is not a person; it is on the signboard |
| Website host | `businesses.website` | Public |
| Finding statements, kinds, confidences, source names and dates | `research_findings`, `sources` | Scraped public page text, already public |
| Opportunity score, solution name, potential problem, expected benefit | `opportunities` | Our own derived data |
| Allowed and emphasised module labels | §6.8 | Our own vocabulary |
| Frozen identity block, CTA offer, opt-out line | `config identity.*` | Sagar's **own** contact details, which he is choosing to disclose |
| `<<CONTACT_GREETING>>` | a literal placeholder | Carries no information at all |

The three values that would otherwise leak, and where each is handled instead:

| Contact value | Where it used to go | Where it goes now |
|---|---|---|
| `contact_name` (the person to address) | The `greeting` slot, rendered before the prompt was assembled | Rendered as the literal token `<<CONTACT_GREETING>>`. Substituted locally after generation |
| `business_contacts.value_norm` (the email address) | Never in the body, but in the draft context and the preview payload | An **envelope** field only. `radar/channels/email.py` reads it from the database at send time (`07-email-integration.md`). It never enters a prompt, a draft body or a claim map |
| `designation` | The greeting or a vocative | Not used by any template. Dropped from `SlotValues` entirely |

**Where the substitution happens.** Exactly one place, in `radar/messages.py`, between the last model
call and the first database write:

```
  build_context()        DraftContext assembled from businesses + findings + opportunities;
        |                the greeting slot renders as the literal "<<CONTACT_GREETING>>"
        v
  assert_no_contact()    the scrubber below. Raises ContactLeak; the job fails, loudly
        |
        v
  generate_message()     Gemini call 1. Body comes back still carrying <<CONTACT_GREETING>>
        |
        v
  rewrite()   optional   Gemini call 2. <<CONTACT_GREETING>> is a frozen span, byte-compared after
        |
        v
  hydrate_contact()      LOCAL, no network. <<CONTACT_GREETING>> -> "Hello Dr. <name>," or
        |                "Hello <business_name> team,". The only line in the drafting path
        |                that reads business_contacts, and it is a pure string substitution.
        v
  persist draft          outreach_drafts.body is the HYDRATED text
        |
        v
  check_draft()          the policy engine reads the HYDRATED text (§6.9.1)
        |
        v
  sha256 -> policy_checked_body_hash
```

The ordering is the whole guarantee, and it has two halves:

1. **Hydration is upstream of the checker.** The policy engine, `policy_checked_body_hash`, the §27
   preview, the audit record and the approval hash all see the substituted text. There is no
   "checked version" and separate "sent version": there is one body, and it contains the name.
2. **Nothing downstream substitutes anything.** The send path in `05-outreach-workflow.md` transmits
   `outreach_messages.body_final` verbatim and the `trg_om_send_needs_approval` trigger compares its
   hash to the approval. If the send path were allowed to interpolate, that hash would be a hash of
   something else and the invariant would be decoration. It is not allowed to, and rule `R8` is the
   backstop: any `<<...>>` token still present at check time is a BLOCK, so a hydration bug produces
   a blocked draft rather than a message that says `<<CONTACT_GREETING>>` to a stranger.

A human edit does not bypass this either; see the table in §6.10.4.

**The scrubber.** Belt and braces on top of "the templates do not render contact values":

```python
# radar/messages.py
class ContactLeak(RuntimeError):
    """A business_contacts value was found in an outbound LLM payload."""


def assert_no_contact_values(payload: str, *, business_id: str, conn) -> None:
    """Fail the job rather than send a contact detail to a free-tier API.

    Loads every business_contacts row for this business AND its campaign siblings (a
    copy-paste bug is exactly how the wrong business's contact ends up in a context block),
    normalises each value the way ingestion did, and searches the assembled prompt for it.
    Also searches for the bare shapes - an e-mail address, a 10-digit Indian mobile, a PAN,
    a GSTIN - that are not in our contact table but are obviously somebody's, because a
    scraped page excerpt can carry a phone number we never stored.

    Not a warning. Not a redaction. ContactLeak, the draft_outreach job fails, and the
    failure is visible in job_runs. A redaction here would hide the template bug that
    produced it, and the next template bug would leak something the redactor did not know
    about.
    """
```

`radar/policy.py` rules `P1`-`P4` check the *output* for the same shapes; the scrubber checks the
*input*. Two independent code paths against one failure, which is the point.

| Test | Asserts |
|---|---|
| `test_pii_no_contact_in_prompt.py::test_fixture_business` | A fixture business with an email, a mobile, a WhatsApp id and a named contact produces a `DraftContext` whose assembled system + user prompt contains none of the four |
| `test_pii_no_contact_in_prompt.py::test_scrubber_catches_injected` | Splicing the contact email into the user prompt by hand raises `ContactLeak` |
| `test_pii_no_contact_in_prompt.py::test_scraped_phone_in_finding` | A `research_findings.statement` that happens to contain a 10-digit mobile raises `ContactLeak`. Findings are public text, but a phone number in one is still a phone number |
| `test_pii_hydration.py::test_placeholder_survives_rewrite` | The rewrite pass returns `<<CONTACT_GREETING>>` byte-identical, or the rewrite is discarded |
| `test_pii_hydration.py::test_unhydrated_blocks` | A draft persisted with the placeholder still in it gives `R8` BLOCK, never `PASS` |

The third test is the one that will actually fire in practice. The research pipeline scrapes contact
pages; a finding statement quoting one is not hypothetical.

### 6.13.1 Call parameters

| Parameter | Value | Reason |
|---|---|---|
| SDK | `google-genai` (`from google import genai`), `client.models.generate_content()` | `_CONTEXT.md` §2. The current Google AI Studio SDK; `google-generativeai` is the retired predecessor and must not be used |
| Auth | `GEMINI_API_KEY` from `config/.env` | Never in `config.yaml`, per `_CONTEXT.md` §1 |
| `model` | `gemini-2.5-flash` | `_CONTEXT.md` §2. **The value changed; the requirement did not** - it is still pinned into `outreach_drafts.model_id` on every row alongside `prompt_version`, because §49's question ("why did the AI write that sentence") is unanswerable without knowing which model wrote it. `resp.model_version` is stored rather than the requested string, so an alias that resolves to a dated build is recorded as the dated build |
| `config.response_mime_type` | `"application/json"` | Required alongside `response_schema` |
| `config.response_schema` | `DraftResponse`, §6.13.4 | Gemini structured output. The SDK accepts the Pydantic class directly and returns `resp.parsed` as an instance of it |
| `config.temperature` | `0.4` | Gemini **does** accept sampling parameters. Pinned in config and recorded in `raw_generation.request` so an audit can reproduce the call. It is not the variation mechanism - §6.6 is, because §6.6 is reproducible and a temperature roll is not |
| `config.top_p` / `top_k` | not sent | One sampling knob is enough to record and reason about |
| `config.max_output_tokens` | `4096` | A 250-word email is ~400 output tokens; the rest is headroom for the claim map, which is the long part of the response |
| `config.thinking_config` | first generation: default (dynamic). Rewrite and repair passes: `ThinkingConfig(thinking_budget=0)` | Drafting under a claim-binding constraint benefits from reasoning. A flow-only rewrite does not, and thinking tokens are charged against the free tier's token allowance like any other output token (§6.13.6) |
| `config.system_instruction` | `radar/prompts/messages/system.v3.txt` | Gemini's system slot. Stable per `prompt_version`; see §6.13.7 |
| `contents` | one user turn, §6.13.3 | Repair appends a `model` turn and a `user` turn (§6.9.15). Gemini's roles are `user` and `model`, not `user` and `assistant` |
| `config.candidate_count` | `1` | More than one candidate is more than one response charged against the quota, to pick one |
| `config.safety_settings` | default | Not loosened. A business email that trips a safety filter is a message worth reading by hand |
| Client retries | **disabled** | `14-background-jobs.md` §14.1 decision 7: retries belong to the job runtime, which owns the lease, the rate bucket and the quota ledger. An SDK-internal retry spends quota that nothing recorded |
| Client timeout | `120_000` ms | A draft job that hangs blocks a worker lease |

```python
# radar/messages.py
from google import genai
from google.genai import types

# One client per process, built in radar/llm.py, key from config/.env: GEMINI_API_KEY.
# radar/llm.py is the only module under radar/ permitted to import google.genai
# (14-background-jobs.md 14.10.2), and a test asserts that.

def generate_message(ctx: DraftContext, *, cfg: Config) -> Generation:
    """One gemini-2.5-flash call. Returns the parsed response plus token counts.

    Raises ContactLeak if the assembled prompt contains a business_contacts value (6.13.0),
    QuotaExhausted on 429 RESOURCE_EXHAUSTED - the caller defers, it does not fail - and
    GenerationError on a safety block, on max_output_tokens truncation, or on a response the
    schema could not parse. The caller writes no draft row on failure: an empty or partial
    draft in outreach_drafts is worse than a failed job that retries.
    """
    assert_no_contact_values(ctx.system_prompt + "\n" + ctx.user_prompt,
                             business_id=ctx.business_id, conn=ctx.conn)

    resp = llm.client().models.generate_content(
        model=cfg.get("llm.messages.model", "gemini-2.5-flash"),
        contents=ctx.user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=ctx.system_prompt,
            response_mime_type="application/json",
            response_schema=DraftResponse,        # the Pydantic model in 6.13.4
            temperature=cfg.get("llm.messages.temperature", 0.4),
            max_output_tokens=cfg.get("llm.messages.max_output_tokens", 4096),
            candidate_count=1,
        ),
    )

    cand = resp.candidates[0]
    if cand.finish_reason in (types.FinishReason.SAFETY,
                              types.FinishReason.PROHIBITED_CONTENT,
                              types.FinishReason.BLOCKLIST):
        raise GenerationError(f"blocked: {cand.finish_reason.name}")
    if cand.finish_reason == types.FinishReason.MAX_TOKENS:
        raise GenerationError("truncated: raise llm.messages.max_output_tokens")
    if resp.parsed is None:
        raise GenerationError("response did not satisfy response_schema; see raw_generation")

    u = resp.usage_metadata
    return Generation(
        parsed=resp.parsed,                       # a DraftResponse instance
        model_id=resp.model_version or cfg.get("llm.messages.model"),
        input_tokens=u.prompt_token_count,
        output_tokens=u.candidates_token_count,
        thinking_tokens=u.thoughts_token_count or 0,
        cached_tokens=u.cached_content_token_count or 0,
        requests=1,                               # charged to the day's quota, 6.13.6
        request_id=resp.response_id,
    )
```

Two SDK differences worth writing down, because both bite people porting between providers:

- **`resp.parsed` can be `None` on a successful HTTP call.** Gemini's structured output is a strong
  constraint on decoding, not a validating parse of the finished response; a truncated or
  safety-trimmed candidate still returns 200. The `resp.parsed is None` check is therefore
  load-bearing, and it must come *after* the `finish_reason` checks so the error names the real cause
  instead of "bad JSON".
- **`thoughts_token_count` is charged output that is not in `candidates_token_count`.**
  `Generation` carries it separately and §6.13.6 counts it, because a budget that ignores thinking
  tokens under-counts by more than the visible answer.

### 6.13.2 System prompt — `radar/prompts/messages/system.v3.txt`

```
You draft first-contact business emails and WhatsApp messages for a one-person custom
software company in Maharashtra, India. Every message you write is reviewed by a human
before it is sent, and is first checked by an automated claim-safety checker. Your job is
to produce a message that passes that checker on the first attempt.

THE ONE RULE
Every sentence that says something about the recipient business must be supported by a
research finding supplied in the user message, and you must return the finding id for that
sentence in the claim map. If no finding supports a sentence, do not write the sentence.

FINDING KINDS
- OBSERVED  : directly supported by a cited source. You may state it plainly.
- INFERRED  : a reasonable conclusion, not verified. You may refer to it ONLY with a hedge
              in the same sentence: "may", "could", "we believe", "based on the nature of",
              "based on the scale of", "typically", "in businesses of this type".
- UNKNOWN   : could not be verified. Do not mention it, do not allude to it, do not write a
              sentence that a reader would take as a claim about it.

NEVER WRITE
- "we noticed", "we know", "we saw", "we can see that you", "you are currently using",
  "you are still running", "your problem is", "your company has problems"
- any number, percentage, multiplier or currency amount that is not present verbatim in a
  supplied finding
- the name of any other business as a client or reference
- any claim of a prior relationship: "as discussed", "following up on our call", "your
  colleague suggested", "referred by"
- urgency: "limited time", "only a few slots", "reply today", "last chance"
- guarantees: "guaranteed", "100%", "will reduce", "risk-free"
- the name of ANY person. You are never given one - see GREETING below
- an email address or a phone number other than the ones inside the frozen identity block
- superlatives about our own company
- pricing of any kind

GREETING
The body must begin with the exact token <<CONTACT_GREETING>> followed by a comma, then a
blank line. Reproduce that token character for character. Do not replace it with a name, do
not guess who the recipient is, do not add "Dear" or "Respected" in front of it. You are not
told who reads this message, and that is deliberate. A human process substitutes the correct
form of address after you finish.

ALWAYS
- Address the business by name, or the <<CONTACT_GREETING>> token. Nobody else.
- Keep the module names to the list supplied in ALLOWED MODULES. Do not invent modules.
- Keep the identity block, the call-to-action offer and the opt-out line exactly as
  supplied; they are frozen text.
- Write in plain Indian business English. No exclamation marks, no emoji, no marketing
  adjectives. Short paragraphs.
- Sound like one person who did some reading, not like a campaign.

OUTPUT
Return JSON only, matching the supplied schema: subject, body, claim_map, confidence.
The claim_map must contain one entry for every sentence of the body, in order, with its
type and the finding ids it rests on. Sentences that assert nothing about the recipient
(greeting, our self-description, the offer, the call to action, the signature, the opt-out
line) take type GREETING / SELF / SELF_CAPABILITY / PROCESS / OFFER / CTA / IDENTITY /
COMPLIANCE and an empty finding_ids list. Everything else is FACTUAL and must have at
least one finding id.
```

### 6.13.3 User prompt — `radar/prompts/messages/user.v3.j2`

Rendered by `radar/messages.py` from a `DraftContext`. SAMPLE fill for the hospital draft:

```
CHANNEL: EMAIL
LENGTH BUDGET: 180-280 words, 4-6 short paragraphs.

BUSINESS
  name:      ABC Hospital
  city:      Dhule
  category:  HOSPITAL
  industry:  HEALTHCARE
  size_band: MEDIUM
  website:   https://sample-abchospital.in

GREETING TOKEN: <<CONTACT_GREETING>>
  Open the body with this token, a comma, then a blank line. It is frozen text. You are not
  told the recipient's name and must not invent one - 6.13.0.

OBSERVED FINDINGS - you may state these plainly, and must cite the id.
  [res_01JAV5S8W2K4M6P8R0TC2VEXF7] (HIGH, 88)
      Website lists four departments; an appointment enquiry form is present on the
      contact page.
      sources: SAMPLE hospital website (WEBSITE, checked 2026-02-14)
               SAMPLE city business directory (DIRECTORY, checked 2026-08-20)

INFERRED FINDINGS - you may refer to these ONLY with a hedge, and must cite the id.
  [res_01JAV5T1X3L5N7Q9S1UD3WFYG8] (MEDIUM, 64)
      A hospital with four departments and public appointment intake is likely to be
      coordinating patient records, appointments and billing across more than one register.

UNKNOWN - DO NOT MENTION, DO NOT ALLUDE TO:
  [res_01JAV5U2Y4M6P8R0T2VE4XG6J8] Could not determine what software, if any, is used for
      patient records.
  [res_01JAV5V3Z5N7Q9S1U3WF5YH7K9] Could not determine staff count.

OPPORTUNITY (from our own scoring, not from the business)
  score 86 (HIGH), solution: Hospital Operations Platform
  potential_problem:  Coordination across four departments with separate records
  expected_benefit:   One view of appointments, department load and pending billing

ALLOWED MODULES (use only these labels):
  patient records, appointments, departments, billing, inventory, reports
EMPHASISE (top-ranked for this business): patient records, appointments, billing

DEMO MODULES WE ACTUALLY HAVE (for the demonstration sentence only):
  patients, appointments, departments, billing, inventory, reports

FROZEN TEXT - reproduce exactly, do not reword:
  greeting:  "<<CONTACT_GREETING>>"
  identity:  "Sagar\nFounder, SAMPLE Software Works\nsagar.softwareworks@gmail.com | +91 XXXXXXXXXX"
  opt_out:   "Not the right person, or not interested? Reply STOP, or email
              sagar.softwareworks+unsub@gmail.com with subject: unsubscribe
              9f13c0aa4b7d4e1e8a2c5f60d3b81c47 - and we will not contact you again."

DRAFT SKELETON - this is the message we would send without you. Improve its flow; keep its
claims. You may reorder and merge sentences. You may not add a claim.

  <the rendered template from 6.4-6.5, with the chosen variants>

AVOID THESE PHRASINGS (they appear in a message already sent to a different business):
  "appears in <CITY> healthcare listings with"
  "may be areas where centralised records reduce"
```

The `AVOID THESE PHRASINGS` block appears only on a re-roll driven by the similarity gate (§6.6.3).

Note what is **not** in that prompt, and was in the previous version: a contact name, a contact email,
a contact phone number, a designation. `radar/messages.py` renders the greeting slot as the literal
`<<CONTACT_GREETING>>` token before the prompt is assembled, and the scrubber in §6.13.0 re-checks the
assembled string. The `identity:` and `opt_out:` frozen spans do contain email addresses, and that is
correct: they are Sagar's own, disclosed on purpose.

### 6.13.4 Response schema

```python
# radar/messages.py
from pydantic import BaseModel, Field

class ClaimMapEntry(BaseModel):
    text: str = Field(description="the sentence, verbatim from the body")
    type: Literal["FACTUAL", "PROCESS", "SELF", "SELF_CAPABILITY", "OFFER",
                  "GREETING", "CTA", "IDENTITY", "COMPLIANCE", "SUBJECT"]
    finding_ids: list[str] = Field(default_factory=list)

class Confidence(BaseModel):
    level: Literal["HIGH", "MEDIUM", "LOW"]
    pct: int = Field(ge=0, le=100)
    why: str

class DraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")     # see the note below - this is the closed schema

    subject: str | None
    body: str
    claim_map: list[ClaimMapEntry]
    confidence: Confidence
```

The Pydantic class is passed straight to `config.response_schema`; the SDK translates it. The
translated form, for the record, is Gemini's **OpenAPI 3.0 subset**, not JSON Schema draft 2020-12:

```json
{
  "type": "OBJECT",
  "required": ["subject", "body", "claim_map", "confidence"],
  "propertyOrdering": ["subject", "body", "claim_map", "confidence"],
  "properties": {
    "subject": { "type": "STRING", "nullable": true, "maxLength": 78 },
    "body":    { "type": "STRING", "maxLength": 4000 },
    "claim_map": {
      "type": "ARRAY", "minItems": 1,
      "items": {
        "type": "OBJECT",
        "required": ["text", "type", "finding_ids"],
        "propertyOrdering": ["text", "type", "finding_ids"],
        "properties": {
          "text": { "type": "STRING" },
          "type": { "type": "STRING", "enum": ["FACTUAL","PROCESS","SELF",
                     "SELF_CAPABILITY","OFFER","GREETING","CTA","IDENTITY",
                     "COMPLIANCE","SUBJECT"] },
          "finding_ids": { "type": "ARRAY", "items": { "type": "STRING" } }
        }
      }
    },
    "confidence": {
      "type": "OBJECT",
      "required": ["level", "pct", "why"],
      "propertyOrdering": ["level", "pct", "why"],
      "properties": {
        "level": { "type": "STRING", "enum": ["HIGH","MEDIUM","LOW"] },
        "pct":   { "type": "INTEGER", "minimum": 0, "maximum": 100 },
        "why":   { "type": "STRING", "maxLength": 400 }
      }
    }
  }
}
```

**Three differences from the previous version, all forced by the dialect and none of them cosmetic:**

| Was | Is | Consequence |
|---|---|---|
| `"additionalProperties": false` | not expressible | The closed-schema guarantee moves from the API to `ConfigDict(extra="forbid")` on the Pydantic model. An extra key is now caught at parse time in our process instead of at generation time in theirs. Same outcome, one round trip later, and the failure surfaces as `resp.parsed is None` -> `GenerationError` |
| `"type": ["string","null"]` | `"type": "STRING", "nullable": true` | Union types are not supported. `subject` is null for `WHATSAPP` and `PHONE`, so `nullable` is load-bearing, not decorative |
| (implicit key order) | `propertyOrdering` | Gemini honours declared property order and its output quality is sensitive to it. `body` is declared **before** `claim_map` on purpose: the model must write the message before it explains it, because a claim map produced first becomes a plan the body then drifts from |

Everything downstream is unchanged. `resp.parsed` is a `DraftResponse`, the four fields land where
they landed before, and `radar/policy.py` neither knows nor cares which provider produced them.

`confidence.level` and `confidence.pct` land in `outreach_drafts.ai_confidence` /
`ai_confidence_pct` and are shown in the §27 AI CONFIDENCE panel. `confidence.why` is stored inside
`raw_generation` — it is the model's own account of how much the message rests on, and it is useful
in exactly one place: when Sagar is deciding whether to send a `MEDIUM`.

### 6.13.5 The repair loop

```python
REPAIRABLE = {"F1","F2","F3","K1","K3","A1","A2","A6","A7","A8","R3","R4","R5","R6","M1","M2","M3","V1"}
NON_REPAIRABLE = {"A3","A4","A5","P1","P2","P3","P4","T1","T2","T3","F4","R1","R2","R7","R8","K2","V2"}

MAX_REPAIR_ATTEMPTS = 2      # config: llm.messages.max_repair_attempts
```

A model that invented a statistic (`A3`), a client (`A4`), a relationship (`A5`) or leaked personal
data (`P*`) is not asked to try again — that is a prompt or model problem, and the draft goes to
`POLICY_BLOCKED` with the evidence intact so Sagar can see what happened. Structural failures
(`T*`, `R1`, `R2`, `R7`, `R8`) mean the pipeline, not the wording, is wrong.

Each repair attempt appends the previous **model** turn (Gemini's name for the assistant role) and a
user turn containing the rejection block from §6.9.15. `repair_attempts` is stored on the draft; a
draft that needed two repairs is worth a look even when it ends up `PASS`, and the `/outreach` list
shows a marker for it.

`MAX_REPAIR_ATTEMPTS = 2` is now also a quota decision, not only a quality one: each repair is a
request against the daily ceiling (§6.13.6). Raising it trades drafts-per-day for
first-pass-acceptance, and the honest lever when acceptance is poor is the prompt, not the retry
count — see the argument in §6.1 about the checker becoming *more* load-bearing on a smaller model.

### 6.13.6 Token and quota budget per message

**Changed for the free stack: there is no rupee cost to budget, so the budget is a quota budget.**
`gemini-2.5-flash` on the free tier is metered in three ceilings, not in money — requests per minute,
tokens per minute, and requests per day — and exceeding any of them returns `429 RESOURCE_EXHAUSTED`.
A 429 is not a bill; it is a wall, and the correct response to a wall is to stop and resume when it
moves, which is what `14-background-jobs.md` §14.10.4 now does.

The published free-tier limits are config, not constants, because Google changes them without
notice and a hard-coded ceiling is a ceiling that becomes wrong silently:

```yaml
llm:
  quota:                          # gemini-2.5-flash, Google AI Studio free tier.
    rpm: 10                       # VERIFY against the current rate-limits page before shipping.
    tpm: 250000                   # These are the values at the time of writing, not a guarantee.
    rpd: 250
```

Budget per draft (a ceiling the code enforces, not a measurement):

| Component | Requests | Input tokens | Output tokens | Note |
|---|---|---|---|---|
| System prompt | — | ~900 | — | Stable prefix; implicit-cache candidate, §6.13.7 |
| Industry block + frozen text | — | ~500 | — | In the user turn |
| Business + findings + skeleton | — | <= 4,000 | — | Hard cap; trimming rule below |
| Generation | 1 | — | <= 1,500 | Includes thinking tokens |
| Rewrite pass (optional) | 1 | <= 3,000 | <= 1,200 | §6.6.2, `thinking_budget=0` |
| Repair pass 1-2 (optional) | 1 each | <= 3,500 each | <= 1,500 each | §6.13.5, `thinking_budget=0` |
| **Ceiling per draft (worst case: rewrite + 2 repairs)** | **4** | **<= 18,000** | **<= 6,900** | |
| **Typical path (generate + rewrite)** | **2** | **~7,400** | **~2,000** | |

Quota arithmetic, against the SAMPLE ceilings above:

| Question | Arithmetic | Answer |
|---|---|---|
| Drafts per day, if drafting had the whole daily allowance | 250 RPD / 2 requests | 125 typical drafts, 62 worst-case drafts |
| Drafts per day at Sagar's real send cap | 15-25 approved sends/day (`_CONTEXT.md` §4) | 30-50 requests. **Drafting is not the constraint** |
| What actually consumes the day | `02-research-pipeline.md`'s synthesis calls, one or more per business researched | Research is the quota driver, exactly as it was the cost driver before |
| Can one draft exhaust TPM? | 18,000 worst-case input tokens vs 250,000 TPM | No. A single request cannot hit the token wall |
| So what binds? | 10 RPM against 2-4 requests per draft | **RPM.** A batch of 20 drafts is 40-80 requests, i.e. 4-8 minutes of wall clock at the bucket's refill rate, and that is fine — nothing is waiting on it |

The conclusion that matters: **the per-draft budget is now about not starving research, not about
money.** The ordering rule is in `14-background-jobs.md` §14.10.4 — `draft_outreach` is a priority-900
interactive job and research is priority-300, so a draft Sagar is waiting for wins the bucket, but
research is what runs out of day.

Enforcement, in order:

```python
def enforce_budget(ctx: DraftContext, *, cfg: Config) -> DraftContext:
    """Count before calling; trim if over; refuse if still over.

    1. client.models.count_tokens(model=..., contents=...) - the real count from the same
       tokenizer the model uses, not an estimate from a third-party library. Note that
       count_tokens is itself an API call, but it is not charged against the free tier's
       generate-content quota; it has its own, far larger, limit.
    2. If over llm.messages.max_input_tokens (default 6000): drop findings from the bottom
       of the confidence ordering, UNKNOWN block first (it is the longest and the model is
       forbidden to use it anyway - but never drop it entirely: the model needs to know what
       not to say), then INFERRED with confidence LOW, then truncate the skeleton.
    3. If still over: raise BudgetExceeded. The job fails and is visible in job_runs; it does
       not silently send a message drafted from half the research.
    """
```

Two ceilings above the per-message budget, both in `contact_policy`-adjacent config rather than in
this module: `llm.daily_request_cap` (default 200, i.e. leave headroom under the 250 RPD ceiling) and
`llm.campaign_request_cap` (default 400). `radar/jobs.py` checks the running total from
`v_spend_today` before claiming a `draft_outreach` job and **parks** the job rather than exceeding
the cap; parked is not failed, and it resumes when the quota day rolls over.
`outreach_drafts.quota_requests` is written at the same time as the token counts, so "how much of a
day did this campaign's drafting consume" is a SQL question rather than a guess.

**What changed and why, for a reader of the earlier version.** The earlier text had
`llm.daily_cost_cap_inr` (500) and `llm.campaign_cost_cap_inr` (2000) enforced over `SUM(cost_inr)`.
Those existed to stop a runaway loop emptying a prepaid balance. On the free tier there is no balance
to empty; the failure mode is a 429 that stops research for the rest of the day. The caps therefore
became request caps whose job is *reserving* quota for the work Sagar cares about most, not
*preventing* an expense.

### 6.13.7 Context reuse, and why there is no explicit cache

**Changed for the free stack.** The earlier version placed `cache_control: {"type": "ephemeral"}` on
the system block and reasoned about cache-write versus cache-read pricing. Gemini's model is
different in two ways that between them delete the section's arithmetic:

| | Then | Now |
|---|---|---|
| How caching is requested | An explicit `cache_control` marker on a content block | **Implicit** for 2.5 models: a request whose prefix matches a recent request may hit the cache with no parameter at all. Explicit caching exists (`client.caches.create`) but is a paid-tier cost optimisation |
| What a hit is worth | A discount on the input price | Nothing, financially — there is no price. A hit reduces `prompt_token_count` charged against **TPM**, which is not the binding ceiling (§6.13.6) |

So: **no explicit cache, no `cache_control`, nothing to configure.** What survives from the earlier
section is the layout rule, and it survives for a better reason than caching:

| Position | Content | Volatility |
|---|---|---|
| `config.system_instruction` | `system.v3.txt` — identical for every draft on this prompt version | Frozen per `prompt_version` |
| `contents[0]` user turn | Business, findings, skeleton, avoid-list | Different every draft |

The industry block and the frozen text stay *inside* the user turn rather than the system
instruction, because they change per category. That was a cache-fragmentation argument; it is now a
reproducibility argument, and a stronger one: `system_instruction` is the thing `prompt_version`
names, so anything that varies per business must not be in it, or `prompt_version` stops identifying
what was actually sent.

`usage_metadata.cached_content_token_count` is still recorded on every `Generation`, and is still
worth watching for one reason: if it is zero across an entire campaign run, something is appending a
timestamp or a per-business token to the system instruction, and `prompt_version` is lying.

### 6.13.8 Failure handling

| Failure | Detection | Response |
|---|---|---|
| `ContactLeak` from the scrubber | §6.13.0, before the call | **Never retried.** The `draft_outreach` job fails, loudly, and the draft is not written. This is a template or context-assembly bug and retrying it would leak the same value again |
| `finish_reason` in `SAFETY` / `PROHIBITED_CONTENT` / `BLOCKLIST` | Checked before reading content | `GenerationError`; the job retries once, then fails visibly. Do not fall back to a generic template message — a blocked draft is a signal, not a hiccup |
| `finish_reason = MAX_TOKENS` | Checked | `GenerationError` naming the config key to raise |
| `resp.parsed is None` (schema not satisfied) | Checked after the `finish_reason` checks | Retry once with the same prompt; then fail. The raw candidate text is stored in `raw_generation` either way, so the failure is diagnosable |
| Extra key in the response | `ConfigDict(extra="forbid")` at parse time | Same path as above. Gemini's schema dialect cannot express `additionalProperties: false`, so this check lives in our process (§6.13.4) |
| `ClientError` 429 `RESOURCE_EXHAUSTED` | `google.genai.errors.ClientError`, `code == 429` | `QuotaExhausted`, **not** an error. `radar/jobs.py` drains the `llm.gemini.rpm` bucket to zero and defers the job to the next quota window (`14-background-jobs.md` §14.10.3, §14.10.4). No attempt is consumed. A campaign paused by quota resumes tomorrow where it stopped |
| `ServerError` 500 / 503 `UNAVAILABLE` | `google.genai.errors.ServerError` | Retried by the job runtime with backoff — not by the SDK, which has retries disabled (§6.13.1) |
| `ClientError` 400 `INVALID_ARGUMENT` | typed | No retry. A malformed request is malformed again next time |
| `ClientError` 403 / 401 | typed | No retry; raises the credentials alert in `14` §14.12.3 |
| Connection error / timeout | `httpx` exception surfaced by the SDK | Retried by the job runtime; idempotent, because no draft row was written |
| Model returns a body whose claim map does not match its own body | Rule `T3` at policy time | Repair attempt, then `POLICY_BLOCKED` |
| Model quietly drops the unsubscribe/identity frozen span | Rules `R1`/`R2` | Non-repairable; `POLICY_BLOCKED` |
| Model replaced `<<CONTACT_GREETING>>` with an invented name | Frozen-span byte comparison, then rule `R8` and rule `P1` | Non-repairable; `POLICY_BLOCKED`. A model that invents a recipient's name is a model whose output cannot be trusted on this draft |

Nothing in this table produces a message. Every failure path ends in a retried job, a deferred job,
or a visible blocked draft.

---

## 6.14 Configuration

```yaml
# config.example.yaml (extract) - secrets live in config/.env, never here
identity:
  sender_name:   "Sagar"
  role:          "Founder"
  company_name:  "SAMPLE Software Works"        # set to the real registered name
  reply_to:      "sagar.softwareworks@gmail.com"          # the dedicated free Gmail, _CONTEXT §4
  unsubscribe_mailbox: "sagar.softwareworks+unsub@gmail.com"
                                                # plus-address on the SAME account: no second
                                                # mailbox, no second credential, and poll_inbox
                                                # already reads it. 6.4
  site_host:     "sagar-software-works.github.io"
                                                # the free static identity page. The only http(s)
                                                # host rule R7 permits in a body.
  site_url:      "https://sagar-software-works.github.io/"
  phone_display: "+91 XXXXXXXXXX"
  # sending_domain: REMOVED. There is no custom domain and no HTTPS endpoint (_CONTEXT §2, §4);
  # the from-address is a gmail.com account, SPF/DKIM/DMARC are Google's, and the unsubscribe
  # mechanism is mailto: rather than a link. See 6.4 and rules R1 / R7.
  demo_modules:                                  # what we can actually demonstrate today
    - PATIENTS
    - APPOINTMENTS
    - DEPARTMENTS
    - BILLING
    - INVENTORY
    - REPORTS
    - STUDENTS
    - FEES
    - ATTENDANCE
    - PRODUCTION
    - PURCHASING
    - SALES

llm:
  provider: "google-genai"        # Google AI Studio free tier. There is no paid tier in this build
                                  # and no `anthropic` dependency anywhere. _CONTEXT §2.
  quota:                          # gemini-2.5-flash free-tier ceilings, 6.13.6.
    rpm: 10                       # VERIFY against the current rate-limits page before shipping;
    tpm: 250000                   # Google changes these without notice, which is why they are
    rpd: 250                      # config and not constants.
  daily_request_cap:    200       # our own reserve under rpd - leaves headroom, 6.13.6
  campaign_request_cap: 400
  messages:
    model: "gemini-2.5-flash"
    prompt_version: "msg-email-v3"
    temperature: 0.4
    max_output_tokens: 4096
    max_input_tokens: 6000
    max_repair_attempts: 2
    rewrite_enabled: true
    rewrite_thinking_budget: 0    # flow only; no reasoning tokens on the rewrite pass, 6.13.1

policy:
  version: "policy@v1.4+rules@2026-08-20"
  max_finding_age_days: 180
  unknown_overlap_threshold: 0.55
  warn_escalation_count: 3
  similarity:
    window_days: 120
    corpus_limit: 500
    j3_warn: 0.42
    j3_block: 0.75
    tsr_high: 0.85
    j3_with_high_tsr: 0.30
    max_rerolls: 2

templates:
  root: "radar/templates/messages"
  whatsapp:
    include_observation: false
    soft_chars: 640
    hard_chars: 900
    soft_words: 110
    hard_words: 150
  email:
    warn_words: 320
    block_words: 500

retention:
  contact_days: 365
```

---

## 6.15 Tests

`tests/` is pytest, no network, fixtures over mocks (`_CONTEXT.md` §1). The policy engine is pure, so
its tests are table-driven and fast.

| Test | Asserts |
|---|---|
| `test_policy_spec23.py::test_bad_examples_block` | Both §23 "bad" sentences produce BLOCK, with the expected rule ids |
| `test_policy_spec23.py::test_good_examples_pass` | Both §23 "good" sentences pass when bound to an `INFERRED` finding |
| `test_policy_binding.py::test_unbound_factual_blocks` | Every `FACTUAL` segment without a finding id gives `F1` |
| `test_policy_binding.py::test_cross_business_binding_blocks` | `F2` on a finding from another `business_id` |
| `test_policy_binding.py::test_sourceless_finding_blocks` | `F4` on a finding with zero `finding_sources` |
| `test_policy_kinds.py::test_inferred_needs_hedge` | Each `HEDGE_RE` alternative satisfies `K1`; a hedge in the *next* sentence does not |
| `test_policy_kinds.py::test_unknown_never_appears` | `K2` on citation, `K3` on paraphrase above threshold |
| `test_policy_banned.py` | One case per regex in §6.9.5, plus one near-miss per regex that must **not** fire |
| `test_policy_pii.py` | `P1`-`P4`, including Sagar's own phone and email being exempt |
| `test_policy_required.py` | `R1`-`R8` per channel, including WhatsApp accepting `Reply STOP` for `R1` |
| `test_policy_verdict.py` | Verdict algebra, including three-WARN escalation |
| `test_similarity.py` | `skeleton()` strips every per-business token; `J3`/`TSR` on the §6.6.3 worked pairs; corpus SQL excludes the same business |
| `test_templates.py::test_frozen_bundles` | No file referenced by a stored `template_version` has changed |
| `test_templates.py::test_every_category_resolves` | Every `businesses.category` and `businesses.industry` value in `_CONTEXT.md` §6 resolves to a manifest entry |
| `test_templates.py::test_pool_conflicts` | No conflicting variant pair is selectable (the §6.5.4 duplication) |
| `test_templates.py::test_rendered_variants_pass_policy` | Every variant combination of every industry block, rendered with fixture findings, passes the policy engine. This is the regression test that stops a new template from shipping an unhedged sentence |
| `test_modules.py::test_map_matches_spec26` | The eight §26 rows in `MODULE_MAP` match the spec text exactly |
| `test_modules.py::test_labels_exist` | Every key in every `module_keys` has a label |
| `test_edit_path.py::test_edit_requires_recheck` | Approving after an edit without a re-check returns 409 (hash mismatch) |
| `test_edit_path.py::test_hedge_removal_blocks` | Editing "may help" to "will help" turns a PASS into a BLOCK |
| `test_audit.py::test_view_row_complete` | `v_ai_message_audit` returns every §49 field for a sent message |
| `test_budget.py::test_trim_order` | `enforce_budget()` drops findings in the documented order and never drops the UNKNOWN block entirely |
| `test_budget.py::test_request_cap_parks` | A `draft_outreach` job with `v_spend_today` already at `llm.daily_request_cap` is **parked**, not failed, and carries a `run_after` in the next quota day |
| `test_pii_no_contact_in_prompt.py` | The four cases in §6.13.0. This is the test that must never be quarantined: it is the only mechanical guarantee that a free-tier prompt carries no contact detail |
| `test_pii_hydration.py` | `<<CONTACT_GREETING>>` survives the rewrite byte-identical; an unhydrated draft gives `R8` BLOCK |
| `test_llm_import_boundary.py::test_only_llm_imports_genai` | No module under `radar/` imports `google.genai` except `radar/llm.py`, and no module imports `anthropic` at all |
| `test_policy_required.py::test_r1_mailto_form` | `R1` requires the mailbox, the token and `reply STOP` together; removing any one of the three BLOCKs. Regression guard for the §6.4 change |
| `test_policy_pii.py::test_unsub_mailbox_exempt` | `P2` does **not** fire on `identity.unsubscribe_mailbox` in the body, and **does** fire on any other address |

---

## Open questions

1. **`research_findings` column names.** `05-outreach-workflow.md` reads `f.statement`, `f.dimension`
   and `f.confidence_pct`; `10-human-handoff.md` reads `f.label`, `f.detail` and `f.weight`. This
   document assumes `statement` / `kind` / `confidence` / `confidence_pct`. `01-data-model.md` must
   pick one set and the other two documents must follow; the policy engine's `BINDING_SQL` and the
   `K3` overlap check both depend on there being a single canonical statement column.

2. **Free-tier quota numbers are not a contract.** `llm.quota.{rpm,tpm,rpd}` in §6.14 records the
   published `gemini-2.5-flash` free-tier ceilings at the time of writing. Google changes them, and
   has changed them, without notice and without a deprecation window. The design copes — a 429 is a
   deferral, not a failure (§6.13.8) — but the config values will drift out of date, and a config
   value that is *higher* than reality just means the local cap never fires and the wall is Google's
   instead of ours. Options: (a) leave it, and treat 429 as the only real signal; (b) have
   `14-background-jobs.md`'s startup check call a lightweight endpoint and log the observed limits;
   (c) derive the effective RPM from observed 429s and write it back to `rate_buckets`. (a) is
   implemented. (c) is tempting and is how a rate-limit storm gets built, so it is not.

3. **Id prefix for `outreach_approvals`, `selections`, `outreach_events`.** This document uses
   `05-outreach-workflow.md`'s `apr_` / `sel_` / `evt_` extensions, which are not in `_CONTEXT.md`
   §2's list. Same open question as that document's; recording it here so the two stay aligned.

4. **`P1` name detection.** Detecting "this capitalised token is a person's name" without a name
   lexicon is unreliable in Indian business names (`SAMPLE Suresh Traders` contains a personal name
   as part of the business name). The design above allowlists exactly the verified contact name and
   the business name tokens, which will produce false positives on businesses named after a founder.
   Options: ship a small Marathi/Hindi/English given-name lexicon, or degrade `P1` to WARN when the
   candidate token is a substring of `businesses.name`. The second is implemented as written; the
   first is better if a lexicon is available.

5. **WhatsApp template registration.** The Cloud API path assumes one approved template
   (`business_software_intro_v1`) with three positional variables. Whether Meta will approve a
   template whose third variable is a free-text module phrase is not something this document can
   settle; if it is rejected, the fallback is one approved template per industry with a fixed
   `relevant_area`, which multiplies the registration work by thirteen. Decide before building the
   gated path.

6. **Sentence segmentation vs. Indian business English.** The `_ABBREV` list covers the common cases,
   but abbreviations like `M/s`, `Sr. No.` and initial-heavy names will occasionally split a sentence
   in the wrong place, shifting segment indices. This affects rule reporting (a rule points at the
   wrong sentence number), not correctness (the text still gets checked). If it proves noisy, the
   answer is a fixture corpus of real drafts in `tests/fixtures/segmentation/`, not a smarter
   heuristic.
