# 7. Email integration architecture

This document decides how a message that Sagar has approved becomes bytes on the wire, and how a
reply becomes a row. It names the mailbox `business_radar` sends through in v1 — a dedicated **free
Gmail account** over authenticated SMTP submission, with IMAP on the same mailbox as the only
inbound path — and it names the ESPs that must not be used, because several of them forbid cold B2B
outreach in their acceptable-use policies and would terminate the account. It defines the
`EmailTransport` Protocol that sits under `08-whatsapp-integration.md` §8.4's `Channel`, the
`NullEmailTransport` that writes `.eml` files instead of sending and is the default everywhere until
a human edits config, what inheriting `gmail.com`'s authentication does and does not buy, the ramp
that keeps a brand-new account from looking like a throwaway, the exact header set and MIME shape of
an outbound message (§24 on the wire), the **`mailto:` unsubscribe** that is the only unsubscribe
mechanism this build can offer and the inbox path that turns one into a `suppressions` row, the
deterministic `Message-ID` and plus-addressed `Reply-To` that let a reply attribute to one
`outreach_messages` row, the ingest path and the matching algorithm including the cases that break
naive matching, bounce handling by parsing RFC 3464 DSNs out of the same mailbox, the honest account
of why a spam complaint is invisible to this system, and the credentials rules. It owns spec §21
(channel selection, email half), §24 (email template, as transmitted), §28 (final send confirmation,
email specifics), §29 (duplicate contact protection, email specifics), §32 (outreach history, email
delivery states) and §41 (export, and the rule that nothing is ever attached to a prospect email).

---

## 7.0 What changed and why

An earlier revision of this document designed against a paid stack: a Zoho Mail mailbox on a
separately registered domain, a full SPF/DKIM/DMARC record set with a 42-day DMARC ramp and a dated
DKIM selector, an HTTPS one-click unsubscribe endpoint at `/u/<token>`, Amazon SES with SNS webhooks
as the fallback, and an eleven-provider price comparison in INR.

`_CONTEXT.md` §2 and §4 have since settled two decisions that void most of that: **the build is
completely free**, and **it runs on Sagar's own Windows laptop on `127.0.0.1`**. There is no VPS, no
public hostname, no registrable domain, and no vendor bill. If you read the earlier version, this is
the delta:

| Then | Now | Why |
|---|---|---|
| Zoho Mail on `sampleworks.in`, SES fallback | A dedicated **free Gmail** account, `smtp.gmail.com:587` STARTTLS with an App Password | `_CONTEXT.md` §4. Nothing is paid for |
| SPF / DKIM / DMARC records we publish and rotate | Google's records, which we inherit and cannot configure | There is no domain to publish under |
| A 42-day DMARC ramp, a dated DKIM selector, rDNS, MTA-STS, TLS-RPT, BIMI | **Deleted.** None of it exists without a domain | §7.4.1 |
| Six-week IP and domain warm-up | A six-week **account-age ramp**, same numbers, different reason | §7.4.5 |
| `https://{domain}/u/<token>`, `List-Unsubscribe-Post`, RFC 8058 one-click | **`mailto:` unsubscribe** per RFC 2369, honoured by the inbox poller | §7.7. Nothing on the internet can reach this process |
| The crawler-prefetch bug and its seven mitigations | Gone with the endpoint. A different, smaller risk replaces it | §7.7.8 |
| SES/SNS webhooks, signature verification, replay protection, `email_webhook_events` | **Deleted.** Every inbound path is an IMAP poll | §7.9.6 |
| Bounce events from a provider API | **RFC 3464 DSNs** parsed out of the same Gmail mailbox | §7.9.6 |
| Complaint events from a feedback loop | **Nothing.** A spam-marking is invisible to this system, and this document says so plainly rather than pretending otherwise | §7.9.4 |
| A per-message provider id as the reconciliation key | Our own `Message-ID`, plus the `[Gmail]/Sent Mail` folder | §7.10.2, §7.10.4 |
| Cost tables in INR, cost per thousand | **Deleted.** Volume is bounded by policy and by Gmail's 500/day, not by money | §7.2.9 |
| A scoped ESP API key | A Gmail **App Password**, which grants full mailbox access and is therefore a *more* dangerous credential | §7.12.2 |

Two things that did **not** change, and are the reason most of this file survived: the AUP argument
that permits one-to-one researched business mail and forbids anything that looks like bulk, and the
whole inbound half — threading, the `M1`-`M8` reply-matching precedence, the auto-reply trap, the
hard cases, and the rule that an unattributable message goes to a human rather than being guessed at.

One thing is new, and it is a consequence of the LLM decision rather than the hosting one:
`_CONTEXT.md` §2 forbids any `business_contacts` value from reaching an LLM, and inbound reply bodies
quote our messages and carry addresses. §7.8.12 puts the scrubber on the inbound path, because this
document is what produces `body_text`.

---

## 7.1 Where this document sits

### 7.1.1 What it owns, and what it must not touch

| Concern | Owner |
|---|---|
| `outreach_messages`, `outreach_events`, `outreach_approvals`, `suppressions`, `contact_policy`, `selections`, `outreach_drafts`, the eligibility gates | `05-outreach-workflow.md` |
| The `Channel` Protocol, `radar/channels/base.py`, the channel registry | `08-whatsapp-integration.md` §8.4 |
| Message wording, slots, claim binding, policy rules A/K/M/P/R | `06-message-engine.md` |
| `jobs`, `job_runs`, `rate_buckets`, `spend_ledger`, the `send_email` / `poll_inbox` job contracts, catch-up-on-launch | `14-background-jobs.md` |
| `responses`, `business_contacts`, `businesses`, migration numbering, id prefixes | `01-data-model.md` |
| `audit_log`, the action catalogue, address hashing, retention | `11-audit-architecture.md` |
| Classifying a reply once it is a `responses` row | `09-response-classification.md` |
| **The transport under the channel, the wire format, the Gmail account and its ramp, deliverability, unsubscribe, inbound ingest, DSN parsing, email credentials** | **this document** |

This document adds **one** table (`inbound_emails`), three migrations and one config block. It adds
no Flask blueprint — the `/u` blueprint of the earlier revision is deleted, because there is nothing
for a stranger's browser to reach. It adds no column to `outreach_messages`: the one field whose
meaning changes, `provider_message_id`, already exists in `05` §5.3.5 and is simply written
differently (§7.10.2).

### 7.1.2 Rulings from `01-data-model.md` that this document obeys

`research_runs.status = 'COMPLETE'`; `verifications.verdict`; `opportunity_modules.ordinal`;
`sources.checked_at`; `responses.body_excerpt`; `handoffs.won_value_inr`; `report_exports` per
`11-audit-architecture.md` as amended (`fmt` = file format, `scope` = subject); `businesses` and
`campaigns` are many-to-many through `campaign_businesses`; migration numbers come from
`01-data-model.md` §1.13.2 and nowhere else.

### 7.1.3 What this document adds to the migration sequence

`01-data-model.md` §1.13.2 ends at `054`. These three continue it. Extending that sequence is an
amendment request to `01`, recorded in Open questions.

| # | File | Creates |
|---|---|---|
| 055 | `055_inbound_emails.sql` | `inbound_emails` + indexes (§7.8.5) |
| 056 | `056_email_account_ramp.sql` | `UPDATE contact_policy` ramp columns; `UPDATE rate_buckets` for `email.hour` / `email.day` (§7.4.5) |
| 057 | `057_v_email_health.sql` | `v_email_health` (§7.6.7) |

One new id prefix, also an amendment request to `01` §1.1.3: `inb_` for `inbound_emails`. The
earlier revision also asked for `eev_` (`email_webhook_events`); **that request is withdrawn** — the
table is deleted along with the webhook endpoint.

---

## 7.2 Provider selection

### 7.2.1 The requirement, stated before the shopping

| Property | Value |
|---|---|
| Steady-state volume | 15-25 messages/day, MON-SAT, inside a 09:30-18:30 IST window (`14-background-jobs.md` §14.9.3) |
| Peak | 40/day, the `email.day` bucket ceiling |
| Monthly | 300-600 at steady state; 50-200 during the ramp |
| Budget | **Zero.** Not "low" — zero. `_CONTEXT.md` §2. Anything with a card number attached is out before its features are read |
| Message shape | One recipient per message. No `Bcc`, no list, no merge-blast. Individually researched, individually rendered, individually approved by a human (`_CONTEXT.md` §3 invariant 1) |
| Content | Plain text, under 320 words, at most two URLs, no attachments, no images |
| Recipient | A published business address at an Indian SME. Frequently `info@`, `contact@`, `admin@` on the business's own domain |
| Prior relationship | **None.** This is cold B2B prospecting. Everything below turns on that one fact |
| Must have | Bounce detection, reply capture, a working unsubscribe |
| Must not have | Sagar's personal address in the `From` header; any dependency on an inbound HTTP request reaching this machine |

That last line removes half the options before the AUP test does. The process runs on a laptop
behind a home router with no port forwarded and no public name. **Nothing on the internet can make a
request to it.** A provider whose bounce, complaint, unsubscribe or inbound-mail story is "we POST to
your endpoint" has no story here at all.

### 7.2.2 The test that matters, and why it is not "deliverability"

Every provider comparison on the internet ranks by deliverability and price. For this system the
first filter is different: **does the provider's acceptable use policy permit sending to someone who
did not ask?** A provider with excellent deliverability whose AUP forbids the use case is not a
better choice that needs care — it is an account that gets closed, usually after the first complaint,
usually at the exact moment the pipeline finally has leads in it.

The questions, in order:

1. Does it cost money? If yes, it is out. `_CONTEXT.md` §2.
2. Does it require an inbound HTTP request to function? If yes, it is out. §7.2.1.
3. Does the AUP permit unsolicited B2B mail? If no, it is out regardless of everything else.
4. If the account is terminated, what else does Sagar lose? (Blast radius.)
5. Only then: deliverability, ergonomics, setup.

### 7.2.3 Why not an ESP — the short version

The eleven-provider comparison in the earlier revision is moot: every ESP on it either charges money
or delivers its events by webhook, and most do both. But the AUP reasoning is **not** moot — it is
exactly what justifies the Gmail decision, and Sagar should not have to rediscover it the next time
a free tier looks tempting. Condensed, with the substance of the operative clause. These are
paraphrases, not quotations of a specific revision; re-read the live policy before signing up for
anything.

| Provider | Free tier | AUP for cold B2B | Substance of the clause | Verdict |
|---|---|---|---|---|
| SendGrid (Twilio) | yes | **NO** | Requires prior consent from every recipient, and separately prohibits lists that were purchased, rented, **harvested** or otherwise compiled without permission | Disqualified. `business_radar` compiles addresses from public listings, which is "compiled without permission" however carefully it is done. The account also covers SMS |
| Mailgun (Sinch) | trial only | **NO** | Requires opt-in, and explicitly prohibits addresses obtained by scraping web pages or harvesting directories | Disqualified. The harvesting clause is a description of the discovery pipeline |
| Brevo | yes | **NO** | Consent required per contact; prospecting contacts must not be imported; suspension on complaint rate alone. An EU processor applying a GDPR-shaped standard to all customers contractually | Disqualified |
| Resend | yes | **NO** | Prohibits unsolicited email; requires evidenced opt-in for any imported list | Disqualified |
| Postmark | no | **NO** | Explicit consent required; the transactional stream is for mail triggered by the recipient's own action; cold outreach and prospecting are not permitted on the platform. Accounts are reviewed by hand at signup and asked how the list was built | Disqualified. The honest answer fails |
| Zoho ZeptoMail | no | **NO** | Sold as transactional-only by product definition: bulk, marketing and prospecting mail are outside the product | Disqualified |
| Amazon SES | 12-month trial, then paid | GREY | Expects you to send only to recipients who asked; enforces on outcomes — bounce over 5%, complaint over 0.1% | Out on cost, and out on shape: its entire event story is SNS POSTing to an endpoint we do not have |
| Instantly / Smartlead / Lemlist class | no | **OK** — the only class whose own terms bless cold outreach | — | Out on cost (roughly ₹3,000+/month), and they send through *your* Google or Microsoft mailbox anyway, so the governing policy is still Google's. Their warm-up pools — networks of accounts mailing each other and marking it important — are engineered deception aimed at a filter, which sits badly beside a system whose central rule is that a claim must trace to a stored fact |
| A self-hosted MTA | free software | **OK** — Sagar is the operator, so there is no third party's policy to breach | — | Needs a static IP with clean reputation, correct forward-confirmed rDNS, and outbound port 25 open. Home broadband has none of those and sits on the Spamhaus PBL by default. Not available on this hardware |

The pattern is worth naming: transactional ESPs make money on deliverability, deliverability is
reputation on shared IP pools, and cold mail is the fastest way to damage a shared pool. Their
policies are not boilerplate they ignore — they are the product working as designed. Reading them as
"everyone does this anyway" is how the account ends.

### 7.2.4 The selection

**A dedicated free Gmail account, sent through authenticated SMTP submission, with replies, bounces
and unsubscribe mails read back from the same mailbox over IMAP.**

| Setting | Value |
|---|---|
| Account | A **new, dedicated** free Gmail account created for this purpose. SAMPLE: `sagar.radar.mail@gmail.com` |
| Submission | `smtp.gmail.com`, port **587**, **STARTTLS**, `AUTH LOGIN` with the App Password |
| Alternative submission | `smtp.gmail.com` port 465, implicit TLS. Equivalent; 587 is the default because a refused STARTTLS is a visible error and a refused implicit handshake sometimes is not |
| Reply capture | `imap.gmail.com`, port **993**, implicit TLS, same account, same App Password |
| Sent-copy folder | `[Gmail]/Sent Mail` — Gmail files a copy of anything submitted through `smtp.gmail.com` there. §7.10.4 depends on this, and §7.4.7 step 9 verifies it on the actual account before anything else does |
| Cost | ₹0 |
| Daily ceiling | 500 recipients per rolling 24 hours, enforced by Google. Policy binds at 25 (§7.4.8) |

**Prerequisites, in order. None are optional, and the first two block each other:**

| # | Step | Note |
|---|---|---|
| 1 | Create the account | Not an alias, not a delegated address on Sagar's existing account — a separate login. §7.2.6 |
| 2 | Turn on **2-Step Verification** | An App Password cannot be created without it. This is Google's rule, not ours, and it is the single most common reason this setup stalls |
| 3 | Create an **App Password** for Mail | 16 characters, shown once. It becomes `OUTREACH_GMAIL_APP_PASSWORD` in `config/.env`. §7.12 |
| 4 | Enable **IMAP** in Gmail settings → *Forwarding and POP/IMAP* | On newer accounts IMAP is on by default and the toggle no longer appears; if it appears, it must say enabled. Without it `poll_inbox` authenticates successfully and then sees nothing — the failure that looks like "nobody ever replies" |
| 5 | Set the account's profile display name to Sagar's real name | It is what appears beside the `From` address in most clients |
| 6 | Confirm plus-addressing and `Delivered-To` | Send `<account>+test@gmail.com` a message from elsewhere, confirm it arrives, and confirm the raw source carries `Delivered-To: <account>+test@gmail.com`. The whole of §7.7.2 and §7.8.3 rests on this |

The App Password is a full-mailbox credential — it can send, read and delete. That is a real
downgrade from a scoped ESP key, and §7.12.2 says so at length rather than burying it.

### 7.2.5 The AUP argument, restated in Gmail's terms

No mailbox provider's policy says "cold B2B outreach is fine". What Google's Terms of Service and
Program Policies prohibit is **bulk unsolicited commercial mail** and using the service to send spam.
The distinction that keeps a mailbox inside the line is not a loophole, and it is worth stating
precisely, because it is also the specification for the rest of this document:

| Property | This system | Bulk mail |
|---|---|---|
| Recipients per message | 1 | many |
| `Bcc` | never used | the mechanism |
| Body | rendered per business from that business's own research findings and its own opportunity record | one body, merge fields |
| Approval | a human read this exact message to this exact address and clicked once, per message (§28) | a campaign was scheduled |
| Volume | 15-25/day, ramped from 3 | thousands |
| Unsubscribe | present, honoured automatically, permanently, business-wide | present, list-scoped |
| Complaint response | permanent, business-wide, automatic | list removal |
| Bounces | suppress the address immediately and permanently | absorbed |

Under those conditions this is a person writing business letters from a mailbox, which is what Gmail
is for. **The argument has expiry conditions, and they are structural rather than aspirational:**

| Condition | Where it is enforced |
|---|---|
| One recipient per message | `T1` (§7.6.4); `to_addrs=[msg.to_addr]` in the transport; `OutboundEmail.to_addr` is a single string and there is no list type to widen it to |
| A per-business rendered body | `06-message-engine.md`'s slot binding; `T2`'s hash equality against the approved body |
| Per-message human approval | Invariant 1; `ApprovalId` is a required argument; `trg_om_sent_needs_audit` |
| 15-25 a day | Gate H3, `email.day` (40), `email.hour` (6) — §7.4.8 |
| A working unsubscribe | Gate H5; `T5`; §7.7 end to end |
| Automatic permanent suppression on any complaint or opt-out | §7.7.7, §7.9.4, invariant 3 |

Break any one of them — a loop that sends without approval, a jump to 200/day, one template with
merge fields, a `Bcc` — and the argument stops holding, and so does the account. That is a design
constraint, not a disclaimer.

### 7.2.6 Sagar's personal Gmail is forbidden, and the reason is blast radius

`_CONTEXT.md` §4 requires a dedicated account. Restated with the consequences spelled out, because
this is the decision most likely to be "simplified" later by whoever is in a hurry:

| If the outreach account is suspended or its reputation is damaged, and it is… | …what is lost |
|---|---|
| **A dedicated account** | The account. Sagar creates another, updates two lines of `config/.env`, and re-runs the ramp from day 1. His clients, his invoices, his calendar, his Drive, his logins and his phone sign-in are untouched |
| **Sagar's personal account** | The address his existing clients already have; every service anywhere that uses it for password reset; Drive; Calendar; Photos; Android sign-in; every third party that federates through Google. And a Google account suspension is appealed through a web form, with no support number and no deadline |

Two further reasons that hold even if nothing ever goes wrong:

- **Reputation on a free Gmail account is per-account.** There is no domain to isolate it into and no
  subdomain to sacrifice. The account *is* the reputation boundary, so the account has to be
  disposable, which means it must contain nothing else.
- **The mailbox is read and written by a daemon.** `poll_inbox` connects with a credential that can
  read every message in the mailbox. Pointing that at Sagar's personal correspondence — on a laptop
  that also holds a contact database — widens the blast radius of a stolen machine from "a prospect
  list" to "everything".

One consequence for `10-human-handoff.md` §10.6.2, whose email fallback mails Sagar himself when
Telegram fails: that path uses `NOTIFY_GMAIL_*`, a **different** account, and Sagar's personal
address is perfectly acceptable *there*. It is mail to himself; it carries no unsubscribe, passes no
policy engine and contacts no stranger. Two accounts, two credentials, neither a fallback for the
other — so an AUP termination of the outreach account does not also remove Sagar's ability to be
told about it.

### 7.2.7 What is given up by having no domain

Stated here rather than in §7.4, so the trade is visible at the point of decision:

| Lost | Severity | Mitigation |
|---|---|---|
| A `From` address that reads as a company (`sagar@company.in`) rather than an individual (`sagar.radar.mail@gmail.com`) | Real. A small, permanent credibility cost on every message | The signature carries the real company name, a real phone number and a link to a real identity page (§7.4.4). An Indian SME receiving mail from a `gmail.com` address is entirely ordinary — a large fraction of the recipients' own published contact addresses are `gmail.com` |
| Domain identity and control | Real | None available. Accepted |
| The ability to abandon a burned domain | Neutral | Replaced by the ability to abandon a burned *account*, which is faster and free |
| A per-domain reputation isolating outreach from other mail | Replaced by per-account isolation | §7.2.6 |
| DMARC aggregate reports about our own traffic | Real but small at this volume | There is nothing to report on: one sender, one account, and no forgery surface worth watching |

### 7.2.8 The ruling

| Rank | Choice | When it applies |
|---|---|---|
| **v1** | **A dedicated free Gmail account**: `smtp.gmail.com:587` STARTTLS with an App Password for submission, `imap.gmail.com:993` for reply, bounce and unsubscribe capture, plus-addressed `Reply-To` for attribution | Day one, and for as long as this stays a one-operator tool at 15-25/day |
| **Fallback** | **A second dedicated free Gmail account**, ramp restarted at day 1 | If the first account is closed. Honest caveat: whatever behaviour closed the first will close the second. The correct response to a closure is to find out which of §7.2.5's expiry conditions broke, not to open another account and carry on |
| **Escape hatch** | **`MANUAL`** — Sagar copies the approved body out of `/outreach` and sends it from whatever mail client he already uses | If email is closed off entirely. The channel already exists (`_CONTEXT.md` §6), the approval record and the audit row are identical, and the only things lost are automatic bounce and reply capture. This is the floor, and it is not nothing |

There is no paid rung on this ladder, by design. If Sagar later wants delivery events, per-message
VERP and a feedback loop, that is a different build with a domain and a bill — and the transport
abstraction in §7.3 is what makes it a new adapter rather than a rewrite.

### 7.2.9 Cost

₹0. There is no pricing table in this document any more, and no `spend_ledger` entry for email. The
free tier's constraint is Google's 500-recipients-per-24-hours ceiling and its unpublished abuse
heuristics, and neither of those is a bill. `spend_ledger` (`14` §14.3.5) records LLM request and
token counts against the Gemini free-tier quota — that is `02`, `06` and `09`'s concern, not this
one. Email consumes no quota and costs nothing; it is bounded by `contact_policy`, by two token
buckets and by policy, and all three are §7.4.8.

---
## 7.3 The abstraction

### 7.3.1 Two layers, not one

`08-whatsapp-integration.md` §8.4.1 already defines `Channel`, the Protocol that makes `EMAIL`,
`WHATSAPP`, `PHONE` and `MANUAL` interchangeable to the eligibility engine. This document does not
redefine it. `EmailChannel` **implements** it, and holds one `EmailTransport` — the narrower thing
that actually puts bytes on a socket.

```
check_send_eligibility()  ->  send_message()            radar/outreach.py            (05)
                                    |
                              get_channel("EMAIL")      radar/channels/__init__.py   (08)
                                    |
                              EmailChannel              radar/channels/email.py      (this document)
                                 |        |
                       build_message()  transport.send()
                                 |        |
                      radar/email/mime.py |
                                          |
                          +---------------+---------------+
                          |                               |
                 NullEmailTransport              SmtpEmailTransport
                 writes .eml to disk             smtplib + STARTTLS to smtp.gmail.com
```

The split exists because the two layers change for different reasons. `EmailChannel` changes when
the *policy* changes — a new gate, a new header the compliance checklist requires. `EmailTransport`
changes when the *account or the protocol* changes. Collapsing them means switching mailboxes
touches the class that enforces the unsubscribe header.

There are now exactly two transports where the earlier revision had three. `SesEmailTransport` is
deleted: SES costs money after the trial and reports its events by webhook, and neither is available
here. The Protocol keeps its shape anyway, because the entire argument for having a Protocol at all
is the day the mailbox changes.

### 7.3.2 The value objects

```python
# radar/email/types.py
"""The email-shaped values the transport layer moves, kept apart from the policy layer.

Without this module the transport grows its own notion of what an outbound message is, and
the version of it that forgets List-Unsubscribe is the version that gets the account closed.
OutboundEmail is deliberately closed: it has no attachments field, no arbitrary headers dict,
no bcc, and no html field that can be set without also setting text - so the four mistakes
that would actually matter cannot be expressed in the type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True, frozen=True)
class OutboundEmail:
    message_id: str                 # msg_..., the outreach_messages row
    rfc_message_id: str             # '<msg_01JB...@gmail.com>', derived, recorded before send
    from_addr: str                  # 'sagar.radar.mail@gmail.com'
    from_name: str                  # 'Sagar'
    to_addr: str                    # outreach_messages.to_address_norm
    reply_to: str                   # 'sagar.radar.mail+msg_01jb...@gmail.com'
    subject: str                    # outreach_messages.subject_final
    text: str                       # outreach_messages.body_final, verbatim
    html: str | None                # None unless email.html_alternative is on (7.5.1)
    unsubscribe_mailto: str         # 'mailto:sagar.radar.mail+unsub-9f13...@gmail.com?subject=unsubscribe'
    unsubscribe_addr: str           # 'sagar.radar.mail+unsub-9f13...@gmail.com', printed in the body
    in_reply_to: str | None         # follow-ups only (7.8.2)
    references: tuple[str, ...] = ()
    date: str = ""                  # RFC 5322 date, filled at build time

    # There is no `attachments` field.       See 7.5.5 and 7.11.
    # There is no `headers: dict` field.     Every header sent is named in 7.5.2.
    # There is no `cc` or `bcc` field.       See 7.2.5: one recipient is the whole argument.
    # There is no `unsubscribe_url` field.   There is no public HTTPS endpoint. See 7.7.1.
    # There is no `return_path` field.       Gmail sets the envelope sender and rewriting it
    #                                        is neither possible nor useful. See 7.8.3.


@dataclass(slots=True, frozen=True)
class TransportResult:
    outcome: Literal["ACCEPTED", "FAILED", "INDETERMINATE"]
    provider: str                   # 'null' | 'gmail'
    provider_message_id: str | None # our own Message-ID on 'gmail'; see 7.10.2
    status_code: int | None
    failure_code: str | None        # 'INVALID_RECIPIENT', 'AUTH_FAILED', 'NETWORK', ...
    failure_detail: str | None
    retryable: bool
    retry_after_s: int | None
    raw: dict[str, Any] = field(default_factory=dict)   # truncated to 4 KB before storage
```

### 7.3.3 The Protocol

```python
# radar/email/transport.py
from typing import ClassVar, Protocol, runtime_checkable


@runtime_checkable
class EmailTransport(Protocol):
    name: ClassVar[str]                     # goes into outreach_messages.provider
    is_live: ClassVar[bool]                 # True means real recipients receive real mail
    supports_delivery_receipts: ClassVar[bool]   # False for both transports in this build

    def send(self, msg: OutboundEmail, *, idempotency_key: str) -> TransportResult:
        """Transmit one message. Never raises for a transport-side problem.

        An exception escaping send() leaves an outreach_messages row with
        provider_send_started_at set and no record of what happened - the one state that
        costs a human ten minutes in a mail client (05-outreach-workflow.md 5.10.2). Every
        network error becomes a TransportResult with an outcome; only a programming error
        propagates.
        """
        ...

    def preflight(self) -> list[str]:
        """Check credentials and configuration without sending. [] means ready."""
        ...
```

Three class variables where the earlier revision had five. `supports_verp`,
`supports_webhooks` and `supports_idempotency_key` are gone: on this stack all three are false for
every transport that exists, and a flag that is always false is dead weight that invites somebody to
write a branch for it. `supports_delivery_receipts` survives because it has a real reader — `03`'s
delivery column renders `—` rather than "unknown" when it is false (§7.9.5), which is
`_CONTEXT.md` invariant 5 applied to a column that will never be populated.

`is_live` is a class variable rather than an instance flag on purpose: it is read at startup by the
assertion in §7.3.8, and a class variable cannot be flipped by a stray line of configuration code.

### 7.3.4 `NullEmailTransport` — the default

```python
# radar/email/null_transport.py
"""The transport that cannot contact anybody, and is what runs unless a human said otherwise.

Every other safety mechanism in this system is a check that can, in principle, be passed. This
one is the absence of a socket. It is the default in config.example.yaml, the default when the
config key is missing, the default when the key is misspelled, and the default in every test.
The .eml files it writes open in any mail client and grep like text, which is what makes MVP
milestone 5 - the whole send path, end to end, with nothing leaving the laptop - an afternoon
rather than a leap of faith.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import ClassVar

from radar.email.mime import build_mime
from radar.email.types import OutboundEmail, TransportResult

log = logging.getLogger("radar.email.null")


class NullEmailTransport:
    name: ClassVar[str] = "null"
    is_live: ClassVar[bool] = False
    supports_delivery_receipts: ClassVar[bool] = False

    def __init__(self, outbox_dir: Path) -> None:
        self._dir = outbox_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def send(self, msg: OutboundEmail, *, idempotency_key: str) -> TransportResult:
        raw = build_mime(msg).as_bytes()
        day = msg.date[:10] or "undated"
        target = self._dir / day / f"{msg.message_id}.eml"
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp = target.with_suffix(".eml.tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, target)                    # _CONTEXT.md 1: atomic write

        log.info("null transport wrote %s (%d bytes) for %s to %s",
                 target, len(raw), msg.message_id, msg.to_addr)
        return TransportResult(
            outcome="ACCEPTED",
            provider=self.name,
            provider_message_id=f"null:{msg.message_id}",
            status_code=200,
            failure_code=None,
            failure_detail=None,
            retryable=False,
            retry_after_s=None,
            raw={"path": str(target), "bytes": len(raw)},
        )

    def preflight(self) -> list[str]:
        if not os.access(self._dir, os.W_OK):
            return [f"outbox directory {self._dir} is not writable"]
        return []
```

Two properties worth naming. `ACCEPTED` is returned rather than some special "not really sent"
outcome, so that the rest of the pipeline — `status = 'SENT'`, the §48 audit row, the counters, the
`businesses.status -> CONTACTED` transition — runs exactly as it will in production. A null
transport that short-circuits the recording path proves nothing. And `provider = 'null'` is stored
on the row, so the database can always answer "did this actually leave the machine" with a query
instead of an inference:

```sql
SELECT COUNT(*) FROM outreach_messages
 WHERE status IN ('SENT','DELIVERED') AND provider = 'null';
```

### 7.3.5 `SmtpEmailTransport` — the v1 live transport

```python
# radar/email/smtp_transport.py
"""Authenticated SMTP submission to Gmail.

The failures this module prevents are quiet ones: smtplib will connect without TLS if asked
nicely, will accept an unverified certificate if a context is not supplied, and reports
partial success for a multi-recipient message rather than raising. All three are closed here,
once, so that no caller has to remember them and no future transport re-opens them. The
fourth quiet failure is Gmail's own: an App Password that has been revoked authenticates as
a plain 535, which reads like a typo and is not.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from typing import ClassVar

from radar.email.mime import build_mime
from radar.email.types import OutboundEmail, TransportResult

log = logging.getLogger("radar.email.smtp")

_PERMANENT = {501, 502, 503, 504, 521, 541, 550, 551, 552, 553, 554}


class SmtpEmailTransport:
    name: ClassVar[str] = "gmail"
    is_live: ClassVar[bool] = True
    supports_delivery_receipts: ClassVar[bool] = False

    def __init__(self, *, host: str, port: int, user: str, app_password: str,
                 timeout_s: int = 30) -> None:
        self._host, self._port, self._user, self._pw = host, port, user, app_password
        self._timeout = timeout_s

    def send(self, msg: OutboundEmail, *, idempotency_key: str) -> TransportResult:
        mime = build_mime(msg)
        ctx = ssl.create_default_context()        # verifies chain and hostname; never relax this
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(self._user, self._pw)
                refused = s.send_message(
                    mime,
                    from_addr=msg.from_addr,      # Gmail rewrites the envelope sender anyway
                    to_addrs=[msg.to_addr],       # exactly one recipient, always
                )
        except smtplib.SMTPAuthenticationError as e:
            # 535 here is almost always one of three things, in this order of likelihood:
            # a revoked App Password, 2-Step Verification switched off, or the account's own
            # password pasted in instead of the App Password. The log line says so.
            return self._fail("AUTH_FAILED", e.smtp_code, e, retryable=False)
        except smtplib.SMTPRecipientsRefused as e:
            code = next(iter(e.recipients.values()))[0]
            return self._fail("INVALID_RECIPIENT", code, e, retryable=False)
        except smtplib.SMTPResponseException as e:
            # 421/450/452 from Gmail are the daily-limit and rate responses; they are
            # retryable tomorrow, not in ninety seconds. 7.10.3 maps them.
            return self._fail("SMTP_ERROR", e.smtp_code, e,
                              retryable=e.smtp_code not in _PERMANENT)
        except (smtplib.SMTPServerDisconnected, TimeoutError) as e:
            # The connection died. We do not know whether DATA completed. Never guess.
            return TransportResult("INDETERMINATE", self.name, None, None,
                                   "CONNECTION_LOST", str(e)[:500], False, None, {})
        except OSError as e:
            return self._fail("NETWORK", None, e, retryable=True)

        if refused:            # unreachable with one recipient; asserted rather than assumed
            return self._fail("INVALID_RECIPIENT", None, refused, retryable=False)

        return TransportResult(
            outcome="ACCEPTED", provider=self.name,
            provider_message_id=msg.rfc_message_id.strip("<>"),
            status_code=250, failure_code=None, failure_detail=None,
            retryable=False, retry_after_s=None,
            raw={"host": self._host, "envelope_from": msg.from_addr},
        )

    def preflight(self) -> list[str]:
        """EHLO + STARTTLS + AUTH, then QUIT. Sends nothing.

        Also the only cheap way to distinguish 'the App Password is wrong' from 'the network
        is down' before a queue of fifteen approved messages discovers it one at a time.
        """
```

`provider_message_id` is our own RFC 5322 `Message-ID`, because SMTP submission returns no provider
id of its own — the `250` response carries a queue token that is Gmail's, not addressable by us, and
not stable. §7.10.2 explains why that is workable and what it costs, and §7.8.1 carries the caveat
that matters most: **Gmail may replace a client-supplied `Message-ID` on submission.**

`INDETERMINATE` on a dropped connection is the branch that matters, and it is why
`14-background-jobs.md` §14.8.12 can set `max_attempts = 1` at the transmit boundary: a disconnect
after `DATA` may or may not have delivered, and SMTP submission offers no lookup that can settle it.
§7.10.4 says what happens next, and the answer is a question to Sagar plus a search of the Sent
folder, not a resend.

### 7.3.6 There is no third transport

The earlier revision's `SesEmailTransport` is deleted. So is the Postfix escape hatch: it needs a
VPS with a clean static IP, forward-confirmed rDNS and outbound port 25, and this build has a laptop
on home broadband. Neither one leaves a stub class behind — a class that cannot be constructed
because its dependency does not exist is a class somebody will eventually try to construct.

What survives is the seam. Adding a transport later is: one module implementing §7.3.3's three
members, one entry in `_LIVE`, one entry in `_REQUIRED_ENV`, and one row in the §7.16 test matrix.
Nothing above `radar/email/` learns about it.

### 7.3.7 Choosing a transport, and the four locks

```python
# radar/email/factory.py

_LIVE: dict[str, type] = {"gmail": SmtpEmailTransport}

_REQUIRED_ENV = {
    "gmail": ("OUTREACH_GMAIL_USER", "OUTREACH_GMAIL_APP_PASSWORD",
              "UNSUBSCRIBE_SIGNING_SECRET"),
}


def build_transport(cfg: Config, policy: ContactPolicy) -> EmailTransport:
    """Return the configured transport, or the null one. Never guesses upward.

    Four separate things must all be true before a real business can receive real mail. They
    are separate on purpose: any one of them being wrong - a copied config file, a restored
    backup, a typo, an environment variable that did not survive a Windows reinstall -
    produces .eml files on disk instead of email to strangers. Nothing here raises: a
    misconfigured mailer must not take down the web app, because the web app is where Sagar
    reads his handoffs.
    """
    mode = cfg.email.transport                       # lock 1: config.yaml, default 'null'
    if mode == "null":
        return NullEmailTransport(cfg.paths.outbox_dir)

    if mode not in _LIVE:
        log.error("email.transport=%r is not a known transport; using null", mode)
        return NullEmailTransport(cfg.paths.outbox_dir)

    if not cfg.email.live_send_enabled:              # lock 2: a second, explicit boolean
        log.error("email.transport=%s but email.live_send_enabled is false; using null", mode)
        return NullEmailTransport(cfg.paths.outbox_dir)

    if os.environ.get("RADAR_EMAIL_LIVE") != "yes":  # lock 3: env var, in no file
        log.error("email.transport=%s but RADAR_EMAIL_LIVE is not 'yes'; using null", mode)
        return NullEmailTransport(cfg.paths.outbox_dir)

    missing = [k for k in _REQUIRED_ENV[mode] if not os.environ.get(k)]
    if missing:                                      # lock 4: credentials must exist
        log.error("email.transport=%s but %s missing from config/.env; using null",
                  mode, ", ".join(missing))
        return NullEmailTransport(cfg.paths.outbox_dir)

    transport = _LIVE[mode](**_kwargs_from_env(mode, cfg))
    log.warning(
        "LIVE EMAIL TRANSPORT ACTIVE provider=%s from=%s daily_cap=%d ramp_day=%s "
        "- real messages will reach real businesses",
        transport.name, cfg.identity.from_address,
        effective_daily_cap(policy, today_ist()),
        ramp_day_index(policy) if policy.warmup_started_on else "n/a",
    )
    return transport
```

| Lock | Where it lives | What it survives |
|---|---|---|
| 1. `email.transport` | `config.yaml`, shipped as `config.example.yaml` with the value `null` | A fresh clone; a second machine; a developer who never read this file |
| 2. `email.live_send_enabled` | `config.yaml` | Somebody naming a transport while experimenting |
| 3. `RADAR_EMAIL_LIVE=yes` | the process environment, set only by the launcher that starts the production service | A production `config.yaml` copied to another machine; a test that loaded the real config |
| 4. Credentials in `config/.env` | never in YAML, never in git | A repository leak; a restore that excludes `.env` |

Lock 3 deserves a note now that the deploy target is a laptop rather than a systemd unit. On Windows
the launcher is a shortcut or a `.cmd` that sets `RADAR_EMAIL_LIVE=yes` and then starts waitress;
`python main.py serve` typed by hand in a shell does **not** set it, and therefore runs with the null
transport. That asymmetry is the point: the exploratory way to start the app is the safe one.

The startup log line is the fifth mechanism and the one a human reads. It names the transport, the
`From` identity, today's cap and the ramp day. On Windows,
`Select-String "LIVE EMAIL" .\data\logs\radar.log | Select-Object -Last 1` answers "is it live, and
how live" in one command.

### 7.3.8 The startup assertion

```python
# radar/web/app.py :: create_app(), and main.py worker startup

def assert_transport_declared(transport: EmailTransport, cfg: Config) -> None:
    """A live transport must be able to build a working unsubscribe before it may exist.

    Gate H5 (05-outreach-workflow.md 5.9.10) already blocks every send when the signing
    secret or the sending identity is missing, so a live transport without them can only
    produce a run of identical per-message refusals. Failing at boot says the same thing
    once, in one line, at the moment somebody can still fix it.
    """
    if not transport.is_live:
        return
    if not cfg.identity.from_address:
        raise ConfigError("a live email transport requires identity.from_address")
    if not os.environ.get("UNSUBSCRIBE_SIGNING_SECRET"):
        raise ConfigError("a live email transport requires UNSUBSCRIBE_SIGNING_SECRET")
    if len(unsub_address(cfg.identity.from_address, "0" * 32)) > 64:
        raise ConfigError(
            "identity.from_address local part is too long: the +unsub- token address "
            "would exceed 64 characters and Gmail will refuse it. See 7.7.2")
    problems = transport.preflight()
    if problems:
        raise ConfigError("email transport preflight failed: " + "; ".join(problems))
```

The third check is new and is specific to this stack: the unsubscribe mechanism lives in the local
part of an address, and an address local part has a 64-character budget. §7.7.2 does the arithmetic.
Discovering that at boot is a config error; discovering it at send time is fifteen refused messages.

`GET /api/v1/health` and `/settings` both render `transport.name` and `transport.is_live`.
`14-background-jobs.md` §14.8.18's daily report carries the same two values, so a transport that went
live by accident is visible in Telegram the next morning without anybody looking for it.

### 7.3.9 MVP milestone 5

Milestone 5 is "SEND works", and it is complete when all nine hold with `email.transport: null`, on
a database seeded with one real researched business whose only contact is Sagar's own address:

| # | Assertion |
|---|---|
| 1 | `POST /api/v1/outreach/messages/<id>/send` moves `APPROVED -> QUEUED` and enqueues `send_email` with dedupe key `send_email:{message_id}` |
| 2 | The worker claims it, passes every gate, writes `SEND_ATTEMPT`, calls the transport, writes `SENT` |
| 3 | `data/outbox/<date>/<msg_id>.eml` exists and parses with `email.parser`; its `To` equals `outreach_messages.to_address_norm` |
| 4 | The `text/plain` part equals `outreach_messages.body_final` byte-for-byte, and `sha256(subject_final + '\x1e' + body_final)` equals `outreach_approvals.approved_body_hash` |
| 5 | `List-Unsubscribe` is present, is a single `mailto:` URI, and the token in its local part equals `outreach_drafts.unsubscribe_token`. `List-Unsubscribe-Post` is **absent** |
| 6 | Feeding a synthetic unsubscribe mail addressed to that `+unsub-<token>` address through the inbound fixture path writes a `suppressions` row, and a second send to that business is refused by gate A |
| 7 | An `audit_log` row with action `OUTREACH_SENT` exists and `trg_om_sent_needs_audit` never fired |
| 8 | `businesses.status` is `CONTACTED` and `campaigns.n_contacted` incremented |
| 9 | Feeding the sent `.eml` back through the inbound fixture path as a reply produces an `inbound_emails` row, a `responses` row attributed `THREAD_HEADER`, and a `classify_response` job |

None of that needs an account, a domain, a DNS record or a network connection. Milestone 6 is the
same nine assertions with `email.transport: gmail` and exactly one recipient: Sagar, at a second
address he owns.

---

## 7.4 Identity, authentication and the account ramp

Throughout this section the outreach account is `sagar.radar.mail@gmail.com` and the identity page is
`https://sample-software-works.github.io/`. Both are SAMPLE.

This section replaces the earlier revision's "Domain and reputation". Most of that section described
records we published under a domain we owned. **There is no domain.** What follows is an honest
account of what that means: what `gmail.com` gives us for free, what it takes away, and what
discipline still has to be applied by hand because Google's reputation does not cover the one thing
we actually control, which is who we mail and how often.

### 7.4.1 What inheriting `gmail.com` buys, and what it costs

| Authentication | Who controls it | What we get |
|---|---|---|
| **SPF** | Google. `gmail.com`'s TXT record authorises Google's own outbound ranges | `spf=pass`, always, with no record to publish, no include limit to blow, and no chance of the classic two-SPF-records permerror |
| **DKIM** | Google. Messages leaving `smtp.gmail.com` are signed with a `d=gmail.com` key Google mints and rotates | `dkim=pass` with a 2048-bit key we neither generate, store, rotate nor can leak. There is no `DKIM_PRIVATE_KEY` in `config/.env` any more, which is one fewer secret on a portable machine |
| **DMARC** | Google. `_dmarc.gmail.com` publishes a policy | `dmarc=pass` with strict-enough alignment, because `From:` is `@gmail.com` and `d=` is `gmail.com` |
| **Alignment** | Automatic | The `From` domain, the DKIM domain and the envelope domain are all `gmail.com`. Alignment is not something we have to reason about; it is structural |
| **IP reputation** | Google | Google's outbound ranges are among the most trusted on the internet. There is no warm-up curve to climb in the usual sense, because the IPs are already warm and are shared with an enormous volume of legitimate mail |
| **rDNS / PTR / HELO** | Google | Correct by construction. The earlier revision's forward-confirmed-rDNS checklist is deleted |
| **MTA-STS, TLS-RPT** | Google | Published for `gmail.com`. Nothing for us to do |
| **BIMI** | n/a | Not available without a domain, a trademark and a paid VMC. It was already rejected on cost |

And the other side of the ledger, which matters more:

| Lost | Consequence | What we do instead |
|---|---|---|
| **Domain identity** | The `From` reads as a person, not a company. There is no `@company.in` to lend authority | §7.4.4's identity page, and a signature that names the company, a phone number and that page |
| **Any control at all** | If Google changes a policy, we adapt. There is no lever | Accepted. The `EmailTransport` seam is the hedge |
| **The ability to abandon a domain** | A burned domain can be replaced in an afternoon; a burned identity here is a burned account | The account is disposable *because* §7.2.6 keeps it empty of everything else |
| **Per-domain reputation** | Reputation is **per account**, and it is Google's private view of that account. It is not visible to us at all — there is no Postmaster Tools, which requires a domain | §7.6.7's `v_email_health` measures the two things we *can* see: bounces and replies. §7.9.4 is honest that complaints are invisible |
| **DMARC aggregate reports** | We receive none, because `rua` for `gmail.com` points at Google | Nothing to do. At one sender and one account there is no forgery surface to watch |
| **VERP / envelope tagging** | Gmail sets the envelope sender to the account address. A bounce cannot be attributed by its return path | Attribution moves entirely to the returned original headers and the plus-tagged `Reply-To`. §7.8.3, §7.9.6 |

**The one that surprises people:** inheriting excellent authentication does *not* mean inheriting
excellent placement. `spf=pass dkim=pass dmarc=pass` from `gmail.com` is table stakes — every spammer
with a free account has exactly the same three passes. What decides placement for a `gmail.com`
sender is per-account behaviour: how many messages, to how many strangers, how fast, and how they
react. That is precisely the list §7.4.5 and §7.4.8 constrain, and it is why the discipline survived
the deletion of the DNS section.

### 7.4.2 The addresses

One account. Every address below is the same mailbox, reached by Gmail's plus-addressing, and
`poll_inbox` reads it with one IMAP connection, one credential and one UID cursor.

| Address | Purpose | Appears in |
|---|---|---|
| `sagar.radar.mail@gmail.com` | The `From` address, and the untagged address printed in the signature | `From`, body signature |
| `sagar.radar.mail+msg_<ulid>@gmail.com` | The per-message `Reply-To` (§7.8.3) | `Reply-To` |
| `sagar.radar.mail+unsub-<token>@gmail.com` | The `mailto:` unsubscribe target (§7.7.2) | `List-Unsubscribe`, and in the body as plain text |

**The 64-character budget.** An address local part is limited to 64 octets, and Gmail enforces it.
Both tagged forms have to fit, and the base account name is what eats the budget:

| Form | Arithmetic | Length with the SAMPLE account |
|---|---|---|
| Base local part | `sagar.radar.mail` | 16 |
| Reply-To tag | base + `+` + `msg_` + 26-char ULID | 16 + 1 + 30 = **47** |
| Unsubscribe tag | base + `+` + `unsub-` + 32 hex | 16 + 1 + 6 + 32 = **55** |
| Ceiling | | 64 |

**A base local part longer than 25 characters breaks the unsubscribe address**, silently, at the
moment the first message is built. §7.3.8's boot assertion checks it, and the account-creation step
in §7.4.7 says to keep the name short for this reason and no other.

Three addresses the earlier revision required and this build does **not** have: `dmarc@`, `tlsrpt@`
and `abuse@`/`postmaster@`. The first two have nothing to report to us. The last two are RFC 2142
obligations of a *domain operator*, and the domain operator is Google — `abuse@gmail.com` exists and
is Google's. That is one genuine reduction in surface, and it is worth saying so rather than
inventing an equivalent.

### 7.4.3 What a receiver sees

```
Authentication-Results: mx.example-hospital.in;
       dkim=pass header.i=@gmail.com header.s=20230601 header.b=...;
       spf=pass (google.com: domain of sagar.radar.mail@gmail.com designates
            209.85.xxx.xxx as permitted sender) smtp.mailfrom=sagar.radar.mail@gmail.com;
       dmarc=pass (p=NONE sp=QUARANTINE dis=NONE) header.from=gmail.com
```

SAMPLE. Three things follow from those three lines, and they are the whole of what authentication
does for this system:

1. **A forged `From` on our identity fails.** Nobody can send as `sagar.radar.mail@gmail.com` without
   Google's key. That protects the identity, which is the only asset here.
2. **`dmarc=pass` with `p=none` at the organisational level** means gmail.com's policy is permissive,
   because it must be — millions of legitimate senders forward gmail.com mail. So DMARC buys us
   authentication, not enforcement. Nothing about our mail is protected by a `p=reject` we do not
   control.
3. **None of it says anything about content.** Placement is decided after authentication, by
   reputation and by content signals. §7.5 and §7.6 are where the actual work is.

### 7.4.4 The identity page — free, static, and not the unsubscribe endpoint

`_CONTEXT.md` §2 permits a free **GitHub Pages** site for a static "who is this" page, and it is
worth having: an unfamiliar `gmail.com` sender making a business claim is exactly the message a
careful recipient wants to check, and a page they can reach in one click is the cheapest possible
answer.

| Property | Value |
|---|---|
| Host | GitHub Pages, `https://<user>.github.io/` or a project page. Free, static, HTTPS by default |
| Content | Sagar's real name, the registered business name, the registered address, a phone number, one paragraph on what the software does, and one line saying that `sagar.radar.mail@gmail.com` is the address used for business correspondence |
| Referenced from | The signature block, as one of the at most two URLs rule `R7` allows (`06` §6.9.7) |
| Config | `identity.site_url`, and `identity.site_host` is the only host in `T4`'s URL allowlist (§7.6.4) |
| **Not** | The unsubscribe endpoint. **Not** a form. **Not** a contact form. **Not** anything that pretends to write to a database |

The last row is the constraint that forces §7.7's design and it is worth being blunt about: GitHub
Pages serves static files. It cannot run code, cannot reach `data/radar.db`, and cannot POST anywhere
useful. A page there that renders an "unsubscribe" button would be a **lie** — a control that appears
to opt somebody out and does nothing. That is materially worse than having no button at all, because
the recipient who clicks it stops looking for the real mechanism. If the identity page mentions
unsubscribing at all, it says: *reply to the message with the word STOP, or write to the address in
the message's unsubscribe header.*

An optional and genuinely useful extra: put the page under version control in the same repository, so
that the claims on it are reviewable in the same way the message templates are.

### 7.4.5 The ramp — account age, not IP warm-up

The earlier revision's six-week warm-up schedule survives **unchanged in numbers and changed
completely in justification**.

It is no longer an IP warm-up. The IPs belong to Google and are already warm; nothing we do at 20
messages a day moves them, in either direction. It is no longer a domain warm-up either; there is no
domain. What it is now:

> **A brand-new Gmail account that sends 25 cold messages on its first day is the exact shape of a
> throwaway spam account,** and it is the shape Google's own abuse detection is best at recognising.
> The single most common way a free Gmail account gets its sending suspended is not content — it is
> a new account with no history emitting a burst of outbound mail to strangers who have never
> corresponded with it.

Seeded by `056_email_account_ramp.sql`:

```sql
-- radar/migrations/056_email_account_ramp.sql   (idempotent, forward-only)
UPDATE contact_policy
   SET warmup_schedule = '[3,3,3,3,3,3,3,' ||
                          '5,5,5,5,5,5,5,' ||
                          '8,8,8,8,8,8,8,' ||
                          '12,12,12,12,12,12,12,' ||
                          '15,15,15,15,15,15,15,' ||
                          '20,20,20,20,20,20,20]',
       daily_send_cap  = 25,
       updated_at      = strftime('%Y-%m-%dT%H:%M:%SZ','now')
 WHERE id = 'GLOBAL';

UPDATE rate_buckets SET capacity = 6.0,  refill_per_sec = 6.0/3600.0   WHERE name = 'email.hour';
UPDATE rate_buckets SET capacity = 40.0, refill_per_sec = 40.0/86400.0 WHERE name = 'email.day';
```

Read as elapsed days from `contact_policy.warmup_started_on`, which is what `effective_daily_cap()`
in `05-outreach-workflow.md` §5.9.10 already does. Sundays need no entry: the send window is MON-SAT
(`14-background-jobs.md` §14.9.3), so Sunday's cap is irrelevant.

| Week | Elapsed days | Cap/day | Send days | Messages that week | Cumulative |
|---|---|---|---|---|---|
| 1 | 0-6 | 3 | 6 | 18 | 18 |
| 2 | 7-13 | 5 | 6 | 30 | 48 |
| 3 | 14-20 | 8 | 6 | 48 | 96 |
| 4 | 21-27 | 12 | 6 | 72 | 168 |
| 5 | 28-34 | 15 | 6 | 90 | 258 |
| 6 | 35-41 | 20 | 6 | 120 | 378 |
| 7+ | 42+ | 25 (`daily_send_cap`) | 6 | 150 | — |

The `email.hour` bucket is 6 so that a day's allowance cannot leave in one twenty-minute burst even
at steady state: 25/day against 6/hour means at least four separate hours of the working day are
involved. A burst is a stronger abuse signal than a volume, and it is the one an automated sender
produces by accident.

**`warmup_started_on` is set by a human**, at §7.4.7 step 12, and never by the application. An
automatic start means a restored backup or a re-run migration can silently restart — or silently
finish — the ramp.

### 7.4.6 Why these numbers, and why they are not the numbers in a warm-up guide

Every published warm-up schedule ramps to thousands per day, because it is written for senders whose
problem is IP reputation. None of that applies here. At 15-25 messages a day:

| Signal | Relevance at 15/day, on a free Gmail account |
|---|---|
| IP warm-up curve | **None.** The IPs are Google's, already warm, shared with enormous legitimate volume |
| Domain age and DNS correctness | **None to earn.** `gmail.com` is old and correct. This was the dominant input in the earlier design and it has simply been handed to us |
| **Account age and history** | **Dominant, and it is the one that replaced the two above.** A three-week-old account that has only ever sent is a different object to Google than a three-month-old account that has sent, received and been replied to |
| **Burst shape** | **Dominant.** Twenty-five messages in four minutes and twenty-five messages across six hours are different events to an abuse classifier. `email.hour` is the control |
| Complaint rate | **Dominant, and invisible to us** (§7.9.4). One complaint in 100 messages is 1% — ten times the threshold that gets an ESP account reviewed. At this volume one angry recipient is a statistical event |
| Bounce rate | **Dominant.** Twenty percent of a five-message day is one bad address |
| Reply rate and thread depth | Strongly positive, and this system optimises for it by construction (§54: qualified conversations, not messages sent). A mailbox that receives replies looks like a mailbox |
| Content | Plain text, no images, no tracking, two links maximum. Nothing here looks like bulk mail because nothing here is bulk mail |

So the schedule is not really a reputation ramp any more. It is two things at once: an
account-age hedge, and a **blast-radius limiter** — it bounds how many businesses can be affected by
a mistake (a bad address list, a template regression, a policy engine bug) before somebody notices.
Week 1's cap of three exists so that the first categorically wrong message reaches three people, not
thirty.

**The ceiling.** For an account under six months old: **40 messages a day, hard**, which is the
`email.day` bucket capacity and is not raised by the ramp schedule ending. Beyond that, two things
must be true first — no observed complaint proxy (§7.9.4) over at least 500 sent messages, and a
bounce rate under 2% over the same window — and raising it is a manual `contact_policy` edit that
writes a `CONFIG_CHANGED` audit row.

### 7.4.7 Before the first message: the pre-flight

| # | Step | Wait |
|---|---|---|
| 1 | Create the dedicated Gmail account. **Keep the local part at 25 characters or fewer** (§7.4.2's budget). Prefer a name that reads as a person plus a purpose, not a random string | — |
| 2 | Turn on 2-Step Verification | — |
| 3 | Create an App Password for Mail; put it in `config/.env` as `OUTREACH_GMAIL_APP_PASSWORD` | — |
| 4 | Enable IMAP if the setting exists | — |
| 5 | Set the profile display name to Sagar's real name and add a profile photo | — |
| 6 | Publish the identity page (§7.4.4) and put its URL in `identity.site_url` | — |
| 7 | Confirm plus-addressing: mail `<account>+test@gmail.com` from elsewhere, confirm arrival, confirm `Delivered-To` carries the tag | — |
| 8 | `python main.py email preflight` — EHLO, STARTTLS, AUTH, IMAP login, `[Gmail]/Sent Mail` exists, the unsubscribe address fits in 64 characters. Sends nothing | — |
| 9 | **`python main.py email test-send --to <sagar's own second address>`.** Then check three things in the received copy: that it arrived in the inbox and not Promotions or Spam; that `Authentication-Results` shows three passes; and — the one that changes a design decision — **whether the `Message-ID` we generated survived, or whether Gmail replaced it** (§7.8.1). The command prints both | — |
| 10 | Confirm the sent copy is in `[Gmail]/Sent Mail` and that `python main.py email find-sent <msg_id>` locates it | — |
| 11 | Use the account like a human for a week: send Sagar a few ordinary messages from it, reply to them from the other side, read them | **7 days minimum** |
| 12 | Send 8-10 messages by hand to Sagar's own accounts across Gmail, Outlook.com, Yahoo, Zoho and one corporate Microsoft 365 tenant. Open each. **Reply to each from the receiving account.** Confirm inbox placement and correct reply attribution | 3 days |
| 13 | Set `contact_policy.warmup_started_on` to today and open lock 3 | — |

Steps 11 and 12 are not warm-up tricks — ten messages change no reputation. Step 11 gives the account
a shape other than "created, then began mailing strangers", which is the only account-age signal we
can honestly produce. Step 12 is a test that the pipeline works end to end against five real
receivers, including the reply path, before it works against a stranger.

Step 9's `Message-ID` check is the most important single line in this table, because §7.8.1's entire
attribution design has a branch that depends on the answer, and the answer is a property of the
account rather than of anything we can read in a specification.

### 7.4.8 Four ceilings, and which one binds

| Ceiling | Where | Kind | Value | Purpose |
|---|---|---|---|---|
| `contact_policy.daily_send_cap` + `warmup_schedule` | gate H3, `05` §5.9.10 | calendar day (IST) | 3-25 | The business rule. Ramp-aware. Blocks with "later", not "no" |
| `rate_buckets['email.day']` | `14` §14.10.2 | rolling 24 h | 40 | Mechanical ceiling. Survives a policy bug because it is a different table read by different code |
| `rate_buckets['email.hour']` | `14` §14.10.2 | rolling 1 h | 6 | Burst limiter, and the one that matters most to an abuse classifier (§7.4.6) |
| **Gmail's own limit** | Google | rolling 24 h | ~500 recipients | Not ours to configure, not documented precisely, and **it must never be the thing that stops us** |

The smallest always binds, and the first three all run: gate H3 inside the send transaction, the
buckets in the job handler at step 5 of `14-background-jobs.md` §14.8.12's order of operations. They
are not redundant — a token bucket cannot express "the third day of a ramp", and a calendar-day
counter cannot stop a burst.

**On Gmail's 500.** Policy binds at 25, which is 5% of it. That headroom is deliberate and it is not
laziness about the real number: hitting Google's limit does not produce a tidy error. It produces a
`421 4.7.0` or a temporary lock on outbound mail for up to 24 hours, sometimes with a security notice
on the account, and it is exactly the event that turns "a person sending business letters" into "an
account exhibiting bulk-sender behaviour" in whatever model Google runs. A system that plans to use
even half of it has already lost the §7.2.5 argument. The number appears here so that nobody later
reads `daily_send_cap = 25` as an arbitrary conservatism and raises it to 400 because "the limit is
500".

The two mechanisms we do own are kept from drifting by one reconciliation, executed inside the same
`BEGIN IMMEDIATE` as the token take:

```python
# radar/email/caps.py

def reconcile_day_bucket(conn, policy: ContactPolicy, today: date) -> None:
    """Keep rate_buckets['email.day'] no larger than today's policy cap.

    Without this the ramp lives in one table and the throttle in another, and the day
    somebody edits daily_send_cap in /settings the bucket keeps handing out forty tokens.
    Clamping only downward is deliberate: the bucket is a ceiling, and a policy that wants
    more than the ceiling does not get to raise it from here.
    """
    cap = float(min(effective_daily_cap(policy, today), _HARD_CEILING))   # 40.0
    conn.execute(
        """UPDATE rate_buckets
              SET capacity = ?, refill_per_sec = ?/86400.0,
                  tokens = MIN(tokens, ?), updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
            WHERE name = 'email.day' AND capacity <> ?""",
        (cap, cap, cap, cap))
```

The IST/UTC question is closed by the send window rather than by arithmetic: sends only happen
09:30-18:30 IST, which is 04:00-13:00 UTC, entirely inside one UTC day. Gate H3's `:utc_day_start`
and an IST calendar day therefore always agree for messages this system sends. A test asserts it.

---
## 7.5 §24 on the wire

`06-message-engine.md` owns the words. This section owns the bytes.

### 7.5.1 Plain text first, and by default only

```yaml
email:
  html_alternative: false      # config.example.yaml default
```

| Argument | Weight |
|---|---|
| A one-to-one business email from a consultant is plain text. Anything else contradicts the message's own claim about what it is | Decisive |
| `multipart/alternative` where the two parts differ in content is a classic filter signal, and generating an HTML part that is provably identical in content is work with no benefit | Strong |
| Rule `R8` (`06` §6.9.7) already blocks raw HTML in the body, so the plain text is authoritative anyway | Strong |
| Plain text has no images to block, no CSS to break, no dark-mode failure, and renders identically in every client including the ancient Outlook builds common in Indian SMEs | Strong |
| Some corporate filters score a text-only message very slightly worse than multipart | Weak, and disputed |

If `html_alternative` is ever turned on, the HTML part is generated **from** the plain text by a
deterministic converter — blank-line-separated blocks become `<p>`, the identity page URL becomes the
single `<a>`, and nothing else. No CSS, no tables, no images, no fonts, no `<style>`. And:

```python
assert mime.get_payload(0).get_payload(decode=True).decode() == msg.text
```

The `text/plain` part is `outreach_messages.body_final` byte-for-byte, always. That is what the
approval hash covers, what the policy engine checked, and what the §48 audit record is a hash of. An
HTML part that says anything the text does not is a claim nobody approved.

### 7.5.2 The header set, in full

Every header this system emits. There is no mechanism to add another, because `OutboundEmail` has no
`headers` dict.

| Header | Value | Notes |
|---|---|---|
| `From` | `Sagar <sagar.radar.mail@gmail.com>` | `identity.sender_name` and `identity.from_address`. Display name is a real human name, never a company or a role |
| `To` | `<to_address_norm>` | Exactly one address. No display name — we usually do not know the recipient's name, and inventing one is rule `P1` |
| `Reply-To` | `Sagar <sagar.radar.mail+msg_01jb...@gmail.com>` | §7.8.3 |
| `Subject` | `outreach_messages.subject_final` | RFC 2047 encoded only if non-ASCII (§7.5.4) |
| `Date` | RFC 5322, with the real `+0530` offset | Not UTC. A business email from India timestamped `+0000` is a small tell |
| `Message-ID` | `<msg_01JB...@gmail.com>` | §7.8.1. **Gmail may replace this on submission**; we generate and record it regardless |
| `In-Reply-To` | parent's `Message-ID` | Follow-ups only |
| `References` | the thread chain | Follow-ups only |
| `MIME-Version` | `1.0` | |
| `Content-Type` | `text/plain; charset="utf-8"` | Or `multipart/alternative` if §7.5.1 is enabled |
| `Content-Transfer-Encoding` | `quoted-printable` | §7.5.4 |
| `List-Unsubscribe` | `<mailto:sagar.radar.mail+unsub-9f13...@gmail.com?subject=unsubscribe>` | §7.7.3. **One URI, and it is a `mailto:`** |
| `List-Unsubscribe-Post` | **absent** | RFC 8058 one-click requires an HTTPS endpoint we cannot host. Sending the header without the URI would be a header that instructs clients to POST nowhere. §7.7.1 |
| `Auto-Submitted` | **absent** | This message is written and approved by a human. Claiming otherwise would be false, and `auto-generated` also invites receivers to suppress replies |
| `Precedence` | **absent** | `bulk` would be a lie about volume and instructs some systems to suppress bounces — the exact signal this system needs |
| `X-Mailer` | **absent** | Names the tool, tells the receiver nothing useful, and is a fingerprint |
| `List-Id`, `List-Help`, `List-Post` | **absent** | This is not a mailing list. `List-Unsubscribe` without `List-Id` is well-defined and correct |
| `Return-Path` | set by Gmail to the account address | Never set by the application. Gmail rewrites the envelope sender on submission, and a mismatch is worse than absence |
| `DKIM-Signature` | added by Google | §7.4.1 |
| Tracking pixel, open beacon, click-wrapped URL | **absent, structurally** | §7.6.1, §7.6.2 |

Two headers left the set with the paid stack: `List-Unsubscribe-Post`, for the reason above, and the
second `List-Unsubscribe` URI, because there is no HTTPS half to list first.

### 7.5.3 A message on the wire

```
Return-Path: <sagar.radar.mail@gmail.com>
Authentication-Results: mx.example-hospital.in;
       dkim=pass header.i=@gmail.com header.s=20230601;
       spf=pass smtp.mailfrom=sagar.radar.mail@gmail.com;
       dmarc=pass (p=NONE sp=QUARANTINE dis=NONE) header.from=gmail.com
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed; d=gmail.com; s=20230601;
       h=from:to:subject:date:message-id:mime-version:content-type:reply-to
        :list-unsubscribe; bh=...; b=...
Date: Thu, 27 Aug 2026 11:12:06 +0530
From: Sagar <sagar.radar.mail@gmail.com>
To: info@abc-hospital-sample.in
Reply-To: Sagar <sagar.radar.mail+msg_01jb3k7qw5zxy8n4mdp2vr6t9c@gmail.com>
Subject: A possible digital operations solution for ABC Hospital
Message-ID: <msg_01JB3K7QW5ZXY8N4MDP2VR6T9C@gmail.com>
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: quoted-printable
List-Unsubscribe: <mailto:sagar.radar.mail+unsub-9f13c0aa4b7d4e1e8a2c5f60d3b81c47@gmail.com?subject=unsubscribe>

Hello ABC Hospital team,

We build customised business-management software for established organisations. While
researching businesses in Dhule we came across ABC Hospital and reviewed its publicly
available business information.

The hospital lists six departments and an outpatient department across two floors. Based on
that scale, we believe patient records, appointments and departmental billing may be areas
where a single system could give management clearer visibility.

...

Regards,
Sagar
Founder, SAMPLE Software Works
sagar.radar.mail@gmail.com | +91 XXXXXXXXXX
https://sample-software-works.github.io

Not the right person, or not interested? Reply with the word STOP and we will not contact you
again. You can also write to sagar.radar.mail+unsub-9f13c0aa4b7d4e1e8a2c5f60d3b81c47@gmail.com.
```

SAMPLE. Note what the signature is doing, because it is carrying more weight than it did in the
earlier revision: the `From` is an individual on a free consumer domain, so the signature has to
supply the company name, a phone number and a checkable page. That is §7.2.7's cost being paid back
in the only place available.

Note also that the closing line names **two** ways out, and that the first is the one a human will
actually use. §7.7.4 explains why the plain-text STOP line is not a nicety.

### 7.5.4 Encoding

| Rule | Value | Reason |
|---|---|---|
| Charset | `utf-8` always | Business names carry Devanagari and diacritics; anything else mangles them |
| Body encoding | `quoted-printable` | `base64` bodies of short plain text are a mild spam signal and unreadable in a raw `.eml`, which defeats the null transport's whole purpose. `8bit` requires `8BITMIME` at every hop |
| Subject | ASCII passes through; non-ASCII becomes RFC 2047 `=?utf-8?Q?...?=` | Python's `email.headerregistry` does this correctly; hand-rolling it is where the mojibake comes from |
| Line length | Hard-wrapped at 78 columns before submission | Long lines get folded in transit, which changes the body and looks wrong in narrow clients |
| Address encoding | ASCII only; an address with non-ASCII characters is rejected at capture with `valid = 0` | SMTPUTF8 is not universally supported and a message that cannot be addressed is not a message |
| Line endings | `CRLF` on the wire; `LF` in the database | The conversion happens once, in `build_mime()`. `body_final` in the database is the `LF` form and is what the approval hash covers |

### 7.5.5 No attachments, structurally

`OutboundEmail` has no `attachments` field. This is not a policy that could be relaxed by a config
key; there is nowhere to put a file. Reasons:

| # | Reason |
|---|---|
| 1 | An unexpected attachment from an unknown sender is among the strongest spam and malware signals there is. Many corporate gateways quarantine the message outright, and some report it |
| 2 | Nothing in §24's structure needs one. A demonstration is a conversation (§34, §55), not a PDF |
| 3 | Attachments are the mechanism by which a research report containing other businesses' data leaves the system by accident. §7.11 |
| 4 | Size. A 2 MB attachment against a 20-message day is 40 MB of outbound from a young account with no sending history |

If Sagar wants to send a prospect a document, that happens after a handoff, from his own mail client,
as a human conversation — which is what `10-human-handoff.md` says the whole post-interest path is.

---

## 7.6 Deliverability engineering

### 7.6.1 No tracking pixels, and no open tracking of any kind

```yaml
email:
  open_tracking:  false        # and there is no code path that sets it true
  click_tracking: false
```

Two independent arguments, and either alone is sufficient.

**The deliverability argument.** A 1x1 remote image referenced from a message to a stranger is one
of the oldest and most reliably-scored bulk-mail signals in existence. Beyond that, the data it
would produce is worthless in 2026: Apple Mail Privacy Protection pre-fetches every image on every
message regardless of whether anyone looked at it, Gmail proxies and caches images so the fetch is
Google's and not the recipient's, and most corporate gateways pre-fetch remote content to scan it.
An "open rate" built on that is noise presented as a number — which `_CONTEXT.md` invariant 5
forbids for report numbers and which there is no reason to permit here.

A third argument now joins them and it is decisive on its own: **there is nowhere to host the
pixel.** A tracking beacon needs a public HTTPS endpoint the recipient's client can fetch, and this
build has none. Open tracking is not merely forbidden here, it is unbuildable, which is the most
durable kind of forbidden.

**The honesty argument, which is the one that would decide it anyway.** This system's central rule is
that it does not assert what it cannot support and does not do to a business anything it would not
say in the message. A tracking pixel is a covert beacon in a first-contact letter to somebody who has
never heard of us: it reports the moment a stranger read a message, roughly where they were, and on
what device, and the message does not mention that it does this. Reading an email is not consent to
be measured. Under the DPDP Act 2023 the pixel would also be processing a named individual's IP
address and access time for a purpose that appears in no notice given to them, which is a
purpose-limitation problem on top of a manners problem.

**Consequences, made explicit so nothing silently invents the number anyway.**

- `outreach_events` keeps its `OPENED` and `CLICKED` values (`05` §5.3.7) because the enum is shared
  with other channels; **no row with those events is ever written for `EMAIL`.**
- `11-audit-architecture.md`'s `OUTREACH_OPENED` and `OUTREACH_CLICKED` actions stay in the
  catalogue, unused, correctly annotated there as "recorded only if open tracking is enabled; off by
  default". On this stack "off by default" can be strengthened to "not implementable".
- Any report, KPI card or funnel row that would show an open rate renders `—`, never `0` and never
  `0%`. Per `_CONTEXT.md` invariant 5, a metric with no data is a dash.
- The measurable engagement signal in this system is a **reply**, which is also the only signal that
  correlates with the metric §54 says to optimise for.

### 7.6.2 No link shorteners, no click wrapping, no redirects

| Forbidden | Why |
|---|---|
| Shorteners (`bit.ly` and every peer) | They are on blocklists because spam uses them; they hide the destination from a recipient deciding whether to click, which is dishonest; and they break permanently when the shortener does |
| Click-tracking redirect domains | Same hidden-destination problem, and there is nowhere to host one anyway |
| Any URL outside `{identity.site_host}` | Rule `R7` (`06` §6.9.7) blocks it at policy time; §7.6.4's `T4` re-checks the rendered MIME, because the policy engine reads the draft body and the transport reads what was actually built |
| More than two URLs | Rule `R7`. In practice there is now exactly **one**: the identity page. The unsubscribe is a `mailto:`, not a URL |

The single URL in a sent message is bare, complete and readable, and it points at a page that names
the sender. A recipient can hover it and see where it goes.

**One change from the earlier revision worth flagging to `06`:** `T4`'s allowlist used to be
`{sending_domain, identity.site_host}`. With `sending_domain` now being `gmail.com`, keeping it in the
allowlist would permit links to arbitrary `gmail.com` URLs, which is not a thing we want to allow and
not a thing we need. **The allowlist is `{identity.site_host}` alone.** Amendment request to `06`
rule `R7` in Open questions.

### 7.6.3 The division of labour with `06-message-engine.md`'s policy engine

This is the boundary, and neither side re-implements the other:

| Layer | Reads | Owns | Examples |
|---|---|---|---|
| `06`'s policy engine | The draft body and subject, plus the claim map | **Content**: what may be asserted, hedged, promised, named; required elements; spam-trigger phrasing | `A1` forbidden assertive, `A2` fake urgency, `A3` unbound statistic, `A6` guarantee, `M3` price claim, `R1` missing unsubscribe, `R3` misleading subject, `R7` link policy, `P1`-`P4` personal data |
| `07` (this document) | The **rendered MIME object**, after `build_mime()` | **Transport**: headers, encoding, structure, addressing, the envelope | `T1`-`T9` below |

`07` has no phrase list and never will. If a phrase is a problem, it is a problem in the draft, the
draft is what Sagar approved, and adding a second phrase list in the transport would mean a message
could pass the check Sagar saw and fail one he did not. The transport checks only things that do not
exist until the MIME is built.

### 7.6.4 The transport checks

```python
# radar/email/checks.py

def transport_checks(mime: EmailMessage, msg: OutboundEmail,
                     draft: OutreachDraft, cfg: Config) -> list[str]:
    """Assertions about the built message that the policy engine could not have made.

    Every one of these has a specific failure behind it. T2 exists because a message whose
    text/plain part no longer equals what Sagar approved is a message nobody approved. T5
    exists because a List-Unsubscribe header carrying a token that does not resolve is an
    unsubscribe that silently does not work, which is worse than none.
    """
```

| # | Check | Severity |
|---|---|---|
| `T1` | Exactly one `To`; no `Cc`; no `Bcc`; the address equals `outreach_messages.to_address_norm` | BLOCK |
| `T2` | The `text/plain` part decodes to exactly `outreach_messages.body_final`, and `sha256(subject + '\x1e' + body)` equals `outreach_approvals.approved_body_hash` | BLOCK |
| `T3` | `From` and `Reply-To` are both on `identity.from_address`'s own account (same local base, same domain), and the `List-Unsubscribe` `mailto:` is too | BLOCK |
| `T4` | Every URL in the body has host `identity.site_host`; no `<img>`; no `data:` URI; at most 2 URLs | BLOCK |
| `T5` | `List-Unsubscribe` present, exactly one URI, scheme `mailto:`, its local part is `<base>+unsub-<token>`, `token` equals `outreach_drafts.unsubscribe_token`, and the whole local part is ≤ 64 characters | BLOCK |
| `T6` | `Message-ID` equals `derive_message_id(outreach_messages.id)`, and no other message in `outreach_messages` has produced it | BLOCK |
| `T7` | No message part is `application/*`; total size under `email.max_bytes` (default 100 KB) | BLOCK |
| `T8` | `Auto-Submitted`, `Precedence`, `X-Mailer`, `List-Id`, **`List-Unsubscribe-Post`** absent | BLOCK |
| `T9` | Subject is 1-78 characters after decoding; no `Re:`/`Fwd:` prefix unless `sequence_no > 1` | WARN |

Three of these changed with the stack. `T3` no longer checks a sending domain, because the domain is
`gmail.com` and checking it would assert nothing; it checks that all three addresses belong to *our
account*, which is the property that actually matters. `T5` checks a `mailto:` and the 64-character
budget instead of an HTTPS URL and a one-click path. `T8` now also asserts the **absence** of
`List-Unsubscribe-Post`, because emitting it without an HTTPS URI tells conforming clients to POST to
a `mailto:`, which is undefined and in practice means the client shows an unsubscribe button that
fails.

A `T*` block is a `PERMANENT_FAILURE` — it means the code built something wrong, so retrying builds
the same wrong thing. It writes `outreach_messages.status = 'FAILED'`,
`failure_code = 'TRANSPORT_CHECK'`, an `OUTREACH_SEND_FAILED` audit row, and a Telegram alert,
because a `T*` failure is a bug and not a business condition.

### 7.6.5 Pacing: delay and jitter

`05-outreach-workflow.md` §5.15.1 specifies a minimum gap of `send_min_gap_seconds` (default 45)
between two email transmissions, jittered ±30%, and assumes a single-threaded sender.
`14-background-jobs.md` §14.2.2 puts `send_email` on the `io` lane with **three** threads. Three
threads can transmit three messages in the same second and defeat the gap.

The gap is therefore enforced where three threads cannot race it — inside the same `BEGIN IMMEDIATE`
that already holds SQLite's single writer lock during the send decision:

```sql
-- radar/email/pacing.py :: LAST_SEND_SQL   (inside the send transaction, before SEND_ATTEMPT)
SELECT MAX(m.sent_at)                   AS last_sent_at,
       MAX(m.provider_send_started_at)  AS last_started_at
  FROM outreach_messages m
 WHERE m.channel = 'EMAIL'
   AND m.provider_send_started_at IS NOT NULL;
```

```python
def pacing_delay(last_started_at: str | None, policy: ContactPolicy,
                 rng: random.Random) -> float:
    """Seconds to wait before this transmission may start, 0 if it may start now.

    last_started_at, not last_sent_at: the previous message may still be in flight. Pacing
    from the attempt marker rather than the success marker is what makes this correct with
    three worker threads and with a server that takes eight seconds to answer.
    """
    if last_started_at is None:
        return 0.0
    gap = policy.send_min_gap_seconds * rng.uniform(0.7, 1.3)
    elapsed = (utcnow() - parse_iso(last_started_at)).total_seconds()
    return max(0.0, gap - elapsed)
```

A non-zero result is a `Defer(now + delay, "PACING")`, not a sleep: `14-background-jobs.md`
§14.10.2 is explicit that a handler holding a lease while sleeping wastes a lane thread, and on a
three-thread lane it would park all three behind the same clock. Deferring costs no attempt.

Jitter is drawn per message from the worker's `random.Random`, not from a fixed schedule. Twenty-five
messages leaving at exactly 45-second intervals is itself a machine pattern; ±30% turns it into a
distribution. On a young Gmail account this is not cosmetic — §7.4.6 puts burst shape among the
dominant signals.

Two further pacing rules, both from §29's family:

- **Never two messages to the same recipient domain in the same batch.** Gate F3 caps
  `same_domain_max` (default 1) inside `same_domain_days` (default 30), so this is already enforced
  — but the `email.domain.{etld1}.day` bucket (`14` §14.10.1, capacity 2) is the mechanical version,
  and it is what stops a bug in the gate from mailing four departments of one hospital in a minute.
- **Never two messages to the same address**, ever, without a new draft and a new approval. Gate F1.

### 7.6.6 The daily cap, in the send path

Step 5 of `14-background-jobs.md` §14.8.12's order of operations takes one token from `email.hour`,
`email.day` and `email.domain.{d}.day`. §7.4.8's `reconcile_day_bucket()` runs immediately before
that take, in the same transaction. An empty bucket is a `Defer` with an ETA plus an
`outreach_events(RATE_LIMITED)` row, exactly as `14` §14.10.3 specifies, and Sagar sees "daily send
limit reached, 3 messages queued for tomorrow 09:30" on `/outreach`.

One laptop-specific consequence. `_CONTEXT.md` §2 says the machine is not on 24/7, and a token bucket
refills by wall-clock arithmetic rather than by a timer, so a bucket that was empty when the laptop
was closed is correctly partly-refilled when it opens — no catch-up job, no drift, no special case.
That is a property of the token-bucket design in `14` §14.10.2 and it is worth naming here because
the alternative implementation (a counter reset by a nightly job) would silently hand out a full
day's allowance every time the machine woke up.

### 7.6.7 The health view

```sql
-- radar/migrations/057_v_email_health.sql
CREATE VIEW v_email_health AS
WITH win AS (SELECT strftime('%Y-%m-%dT%H:%M:%SZ','now','-30 days') AS since),
sent AS (
    SELECT COUNT(*) AS n_sent,
           SUM(CASE WHEN m.status = 'BOUNCED' THEN 1 ELSE 0 END) AS n_bounced
      FROM outreach_messages m, win
     WHERE m.channel = 'EMAIL'
       AND m.status IN ('SENT','DELIVERED','BOUNCED')
       AND m.sent_at >= win.since
),
comp AS (
    SELECT COUNT(DISTINCT e.message_id) AS n_complained
      FROM outreach_events e
      JOIN outreach_messages m ON m.id = e.message_id, win
     WHERE e.event = 'COMPLAINED' AND e.at >= win.since AND m.channel = 'EMAIL'
),
repl AS (
    SELECT COUNT(DISTINCT r.message_id) AS n_replied
      FROM responses r
      JOIN outreach_messages m ON m.id = r.message_id, win
     WHERE m.channel = 'EMAIL' AND r.received_at >= win.since
),
today AS (
    SELECT COUNT(*) AS n_today
      FROM outreach_messages m
     WHERE m.channel = 'EMAIL'
       AND m.status IN ('SENT','DELIVERED','BOUNCED')
       AND m.sent_at >= strftime('%Y-%m-%dT00:00:00Z','now')
)
SELECT sent.n_sent, sent.n_bounced, comp.n_complained, repl.n_replied, today.n_today,
       CASE WHEN sent.n_sent >= 20
            THEN ROUND(sent.n_bounced * 100.0 / sent.n_sent, 2) END AS bounce_pct,
       CASE WHEN sent.n_sent >= 20
            THEN ROUND(comp.n_complained * 100.0 / sent.n_sent, 3) END AS complaint_pct,
       CASE WHEN sent.n_sent >= 20
            THEN ROUND(repl.n_replied * 100.0 / sent.n_sent, 2) END AS reply_pct
  FROM sent, comp, repl, today;
```

`bounce_pct`, `complaint_pct` and `reply_pct` are `NULL` below `bounce_rate_min_sample` (20), and
`/settings` renders `—` for a `NULL`. Two bounces out of three sends is not a 67% bounce rate; it is
three sends. This is `_CONTEXT.md` invariant 5 applied to the one panel where a fabricated percentage
would cause Sagar to pause a working system.

`reply_pct` is new in this revision and it is there for a specific reason: on this stack the reply
rate is the **only** positive delivery signal that exists. There is no `DELIVERED` event, no open
rate, and no feedback loop. A reply rate that was 8% for six weeks and is 0% for the last two is the
closest thing to a delivery alarm this system can build, and §7.9.4 makes it one.

---

## 7.7 Unsubscribe

This is the most safety-critical mechanism in the application. It is also the part of the earlier
design that the free stack demolished most completely, so this section is written from scratch rather
than edited. It must work with no authentication, be idempotent, be impossible to lose, and — the
new constraint — **work entirely inside a mailbox**, because there is no server anybody can reach.

### 7.7.1 There is no HTTPS endpoint, and therefore no RFC 8058 one-click

`_CONTEXT.md` §2: the app is Flask + waitress bound to `127.0.0.1` on Sagar's laptop. There is no
public hostname, no port forwarded, no TLS certificate for a name anybody else can resolve, and the
machine is not on 24 hours a day.

| Mechanism | Requires | Available here |
|---|---|---|
| `https://{host}/u/<token>` link in the body | A public HTTPS host reachable from the recipient's browser | **No** |
| RFC 8058 `List-Unsubscribe-Post: List-Unsubscribe=One-Click` | A public HTTPS URI that accepts `POST` from the recipient's *mail provider* | **No** |
| A static page on GitHub Pages with an unsubscribe button | Somewhere for the button to POST that can write `data/radar.db` | **No** — §7.4.4 |
| `mailto:` in `List-Unsubscribe`, per RFC 2369 | A mailbox we read | **Yes** |
| "Reply with STOP" in the body | A mailbox we read | **Yes** |

**RFC 8058 one-click is not offered, and the header is not emitted.** This is a real loss and it is
worth being precise about what is lost, because "we could not do one-click" is often written as
though it were a formality:

- Gmail's and Yahoo's bulk-sender requirements expect one-click unsubscribe **for bulk senders**
  (the published thresholds are around 5,000 messages per day to their users). At 15-25 messages a
  day across all receivers, this system is three orders of magnitude below that, and the requirement
  does not attach. If it ever did attach, the correct response would not be to fake it; it would be
  that this system had become a bulk sender and §7.2.5's argument had expired.
- What the recipient loses is the button their client renders next to the sender name. With a
  `mailto:`-only `List-Unsubscribe`, some clients still render that button and send the mail for the
  user; many render nothing at all.
- **That is exactly why §7.7.4's visible plain-text STOP line is mandatory rather than a nicety.**
  In the earlier design the body link was the backup and the header was primary. Here the header is
  the backup and the human-readable line in the body is primary.

The `/u` Flask blueprint, its `GET`/`POST` split, `robots.txt`, the one-click route and the whole
seven-layer crawler mitigation are **deleted**. §7.7.8 says what replaced the risk they managed.

### 7.7.2 The address and the token

```python
# radar/email/unsubscribe.py

def unsubscribe_token(message_id: str, contact_norm: str) -> str:
    """The 32-hex token that appears in the unsubscribe address and in the body.

    Derived rather than random so that it can be recomputed and verified, and stored so
    that verification is an indexed lookup rather than a table scan. Both properties are
    needed: recomputation catches a token minted with a different secret, and the stored
    column is what turns an inbound unsubscribe into one primary-key hop.
    """
    secret = os.environ["UNSUBSCRIBE_SIGNING_SECRET"].encode()
    return hmac.new(secret, f"{message_id}|{contact_norm}".encode(),
                    "sha256").hexdigest()[:32]


def unsub_address(from_address: str, token: str) -> str:
    """sagar.radar.mail+unsub-<token>@gmail.com

    The token lives in the LOCAL PART, not in the subject and not in the body, because the
    local part is the only place a mail client cannot drop. Clients routinely strip the
    ?subject= parameter of a mailto: URI, some rewrite the body, and a human forwarding the
    message by hand types nothing at all - but every one of them sends to the address.
    """
    local, _, domain = from_address.partition("@")
    addr = f"{local}+unsub-{token}@{domain}"
    if len(addr.split("@")[0]) > 64:                 # asserted at boot too; see 7.3.8
        raise ConfigError(f"unsubscribe local part is {len(addr)} chars; Gmail caps at 64")
    return addr


def unsubscribe_mailto(from_address: str, token: str) -> str:
    return f"mailto:{unsub_address(from_address, token)}?subject=unsubscribe"
```

The token is written to `outreach_drafts.unsubscribe_token` when the draft is created (`06` §6.3's
`ALTER`, unique index `ux_drafts_unsub`), so resolution is one indexed lookup:

```sql
-- radar/email/unsubscribe.py :: RESOLVE_TOKEN_SQL     params: :token
SELECT d.id AS draft_id, m.id AS message_id, m.business_id, m.contact_id,
       m.to_address_norm, m.channel, m.sent_at
  FROM outreach_drafts d
  JOIN outreach_messages m ON m.draft_id = d.id
 WHERE d.unsubscribe_token = :token;
```

Verification is both: the row must exist **and**
`hmac.compare_digest(token, unsubscribe_token(row.message_id, row.to_address_norm))` must hold. The
second check is what makes a token minted under a rotated or leaked secret useless.

**How the token identifies the business and the message, and what "spoofable" means here.** The
question is worth answering precisely, because a mailbox accepts mail from anybody and the `From`
header of an inbound unsubscribe is worth nothing.

| Property | Answer |
|---|---|
| What the token identifies | Exactly one `outreach_drafts` row, hence exactly one `outreach_messages` row, hence one business and one contact address. The lookup needs no reasoning about the sender at all |
| What we trust | **The token, and nothing else.** Not the `From` address, not the `Reply-To`, not the display name, not SPF or DKIM on the inbound message. An unsubscribe mail is honoured because it carries a token only a recipient of that message could have |
| Can a stranger forge one? | Only by guessing 128 bits of HMAC output, or by having received the message. Both are fine |
| What if they succeed? | They cause a suppression. **Suppression is the safe direction** (`_CONTEXT.md` invariant 3): the worst outcome of a forged unsubscribe is that a business we would have mailed is not mailed. There is no forged input to this path that causes a message to be *sent* |
| What if the token leaks — a forwarded message, a shared inbox, a pasted screenshot? | Same answer. Whoever holds it can stop mail to that one business and can do nothing else. There is no enumeration risk either: a token is not derivable from another token, and unknown tokens produce no observable difference (§7.7.7) |
| Why not just accept "any mail to `+unsub@`"? | Because then the sender's address would have to identify the business, and that is exactly the thing that is forgeable. A plain `+unsub@` mail with no resolvable token is still handled — §7.7.5 case 4 — but it goes to a human rather than being attributed by inference |

The asymmetry is the whole design: **this path can only ever stop mail, so it needs no
authentication, and giving it any would only create a way for a genuine unsubscribe to fail.**

### 7.7.3 The header

```
List-Unsubscribe: <mailto:sagar.radar.mail+unsub-9f13c0aa4b7d4e1e8a2c5f60d3b81c47@gmail.com?subject=unsubscribe>
```

| Decision | Reason |
|---|---|
| Exactly one URI, and it is a `mailto:` | There is no HTTPS half. RFC 2369 permits a `mailto:` alone and it is the original form of the header |
| The token is in the local part, not only in `?subject=` | Clients strip query parameters. §7.7.2 |
| `?subject=unsubscribe` is included anyway | Belt and braces: it makes the mail recognisable even in the case where a client rewrites the recipient (it does not, but the subject costs nothing), and it makes a human-forwarded copy self-describing |
| No `?body=` | Some clients ignore it, some prompt, and the body is not consulted when the address already carries the token |
| `List-Unsubscribe-Post` **not** emitted | §7.7.1. Emitting it without an HTTPS URI produces a client-rendered button that POSTs nowhere |
| Google signs `List-Unsubscribe` as part of its DKIM `h=` list | We do not control the `h=` list, but Gmail's signing includes it in practice, which means an intermediary that rewrites the header breaks the signature rather than silently removing the recipient's way out |

### 7.7.4 The visible line in the body, which is now the primary path

```
Not the right person, or not interested? Reply with the word STOP and we will not contact you
again. You can also write to sagar.radar.mail+unsub-9f13c0aa...@gmail.com.
```

| Property | Reason |
|---|---|
| It is plain text in the body, not a link and not a header | `List-Unsubscribe` is invisible in a large fraction of clients, and with no HTTPS URI more of them will render nothing at all. A mechanism the recipient cannot see is not a mechanism |
| "Reply with the word STOP" comes **first** | It is the lowest-effort action available to a human reading mail on a phone: hit reply, type four letters, send. No copying an address, no new compose window, no thinking |
| It says STOP rather than "unsubscribe" | Short, unambiguous, and already the token every Indian recipient knows from SMS. §7.8.7 rule 5 and `09-response-classification.md` §9.5's `B2` both match `stop`, `unsubscribe` and `remove`, so the recipient can say any of them |
| The `+unsub-` address is printed too | For the recipient who prefers not to reply — commonly someone forwarding to whoever handles this — and for the one whose client shows the header button and whose click produces the same mail |
| It is a frozen span | `06` §6.3's `unsubscribe` slot; rule `R1` requires it; the send path rewrites it from the token regardless of what the model produced (`06` §6.14) |

**Amendment request to `06`.** Rule `R1` today requires the body to contain
`https://{sending_domain}/u/[0-9a-f]{32}`. That URL cannot exist. `R1` for `EMAIL` becomes: the body
must contain the literal STOP instruction matching `/\breply\s+with\s+the\s+word\s+STOP\b/i` **and**
the address `{base}+unsub-<token>@{domain}` whose token equals `outreach_drafts.unsubscribe_token`.
Recorded in Open questions.

### 7.7.5 How the poller recognises an unsubscribe

Five shapes arrive, and all five are honoured. This runs inside §7.8.7's `kind` classification as
rule 5, and it runs **before** anything is treated as a reply.

| # | Shape | What arrives | Detection | Token from |
|---|---|---|---|---|
| 1 | **Client-generated, the common case.** The recipient's client renders the `List-Unsubscribe` button; they press it; the client composes and sends a mail on their behalf, often with an empty body | `Delivered-To: <base>+unsub-<token>@gmail.com`, `Subject: unsubscribe`, body empty or client boilerplate | `+unsub-` tag in `Delivered-To` / `To` / `X-Original-To` | The tag. Exact |
| 2 | **Human writes to the printed address.** They copy the address out of the body, or forward the message to it | Same recipient tag; body is whatever they typed, possibly a forwarded message | Same | The tag. Exact |
| 3 | **Human replies with STOP.** They hit reply and type "STOP", "unsubscribe", "remove me", "please don't contact us again" | `To: <base>+msg_<ulid>@gmail.com` (the `Reply-To` tag), first non-quoted body line matches the opt-out pattern | Body pattern + the `msg_` tag | The **message** tag resolves the message; the token is then derived from it |
| 4 | **Untokenised mail to the unsubscribe address.** A stripped tag, a mail client that rewrote the recipient, a human who typed `+unsub@` without the token, or an address harvested from an old forward | `+unsub` present, token absent or not resolvable | Recipient starts `<base>+unsub` | **None.** §7.7.6 |
| 5 | **Opt-out in the body of an ordinary reply**, arriving on the untagged address or from a different address entirely | First non-quoted line matches the opt-out pattern | Body pattern | Whatever `M1`-`M7` attribution produced (§7.8.8) |

```python
# radar/email/unsubscribe.py

_UNSUB_TAG = re.compile(r"\+unsub-([0-9a-f]{32})@", re.I)
_OPT_OUT   = re.compile(r"^\s*(stop|unsubscribe|remove(?:\s+me)?|opt[\s-]?out)\b", re.I)

def find_unsubscribe(headers: Mapping[str, str], body_first_line: str) -> UnsubSignal | None:
    """Decide whether this inbound message is an unsubscribe, and on what evidence.

    Header first, body second, and never the other way round: a body that merely contains
    the word 'unsubscribe' inside a quoted copy of our own footer is not an opt-out, and a
    tagged recipient address is not a matter of interpretation. body_first_line is the first
    line AFTER quote-stripping (7.8.6 step 5) for exactly that reason.
    """
    for h in ("Delivered-To", "X-Original-To", "To", "Envelope-To"):
        m = _UNSUB_TAG.search(headers.get(h, ""))
        if m:
            return UnsubSignal(via="HEADER_TAG", token=m.group(1).lower(), confidence="HIGH")
    if "+unsub" in headers.get("Delivered-To", "") or "+unsub" in headers.get("To", ""):
        return UnsubSignal(via="UNTOKENISED", token=None, confidence="LOW")
    if _OPT_OUT.match(body_first_line or ""):
        return UnsubSignal(via="BODY_STOP", token=None, confidence="HIGH")
    return None
```

Rule 3 and rule 5 are the same code path and they are deliberately generous: **a person who types
STOP has opted out, and they should not have to find anything.** That suppression is written by this
path immediately — it does not wait for `classify_response`, which also has a deterministic pre-pass
for the same phrases (`09` §9.5 rule `B2`). Two independent paths honour an opt-out and neither
depends on an LLM being reachable, which matters more on this stack than it did on the last one: the
Gemini free tier can and will return 429 for a day.

### 7.7.6 The untokenised case, and why it is not silently dropped

Case 4 is the one that would rot quietly. Mail arrives at `+unsub@` with no resolvable token: we know
somebody wants out, and we do not know who.

| Step | Behaviour |
|---|---|
| 1 | `inbound_emails` row with `kind='UNSUBSCRIBE'`, `state='UNMATCHED'`, `match_rule` null |
| 2 | Attribution is attempted anyway by `M5`/`M6`/`M7` on the sender address (§7.8.8). A person writing from the address we mailed is resolved that way and the case collapses into a normal opt-out |
| 3 | If that fails: **`scope='EMAIL'` suppression on the sender's own address**, `reason='REPLY_OPT_OUT'`, `business_id = NULL`. We may not know which business they are, but we know one address that must never receive mail from this system again, and `suppressions` is keyed on `(scope, value_norm)` with a nullable `business_id` precisely so this row can exist |
| 4 | It appears in the unmatched band on `/outreach` with the subject line "someone asked to be unsubscribed and we could not tell who", and Sagar can attach it to a business by hand (`M8`) |
| 5 | A `send_notification` at `NORMAL` priority the same day, because an unattributable opt-out is the one unmatched item that is not merely tidying |

Step 3 is the important one and it is a deliberate over-block: suppressing an address we cannot
attribute costs us at most one prospect, and not suppressing it costs us the one thing this system
must never get wrong.

### 7.7.7 Applying it: idempotency, latency, and the send-time gate

```python
# radar/email/unsubscribe.py  (called from ingest_one(), inside the ingest transaction)

def apply_unsubscribe(conn, inb, signal: UnsubSignal, cfg: Config) -> str | None:
    """Turn an inbound unsubscribe into a suppressions row. Idempotent, no network, no LLM.

    Runs inside the same transaction that stores the inbound message, so there is no window
    in which we have read an opt-out and not yet honoured it. A crash rolls back both; the
    IMAP UID cursor has not advanced; the next poll re-reads the same mail and the unique
    index absorbs the duplicate. Nothing here can leave an opt-out un-applied.
    """
    row = None
    if signal.token:
        row = conn.execute(RESOLVE_TOKEN_SQL, {"token": signal.token}).fetchone()
        if row and not hmac.compare_digest(
                signal.token, unsubscribe_token(row["message_id"], row["to_address_norm"])):
            row = None                       # minted under a different secret; treat as unknown

    if row is None and inb.matched_message_id:          # BODY_STOP on an attributed reply
        row = conn.execute(RESOLVE_BY_MESSAGE_SQL,
                           {"message_id": inb.matched_message_id}).fetchone()

    if row is None:                                     # 7.7.6: suppress the sender, flag it
        if not inb.from_address_norm:
            return None
        return policy.suppress(
            conn, scope="EMAIL", value_norm=inb.from_address_norm, business_id=None,
            reason="REPLY_OPT_OUT",
            source=f"unattributed unsubscribe mail {inb.id}", source_ref=inb.id,
            detail={"via": signal.via, "inbound_email_id": inb.id})

    sup_id = policy.suppress(
        conn, scope="EMAIL", value_norm=row["to_address_norm"],
        business_id=row["business_id"], reason="UNSUBSCRIBE_LINK",
        source=f"unsubscribe {signal.via.lower()} on {row['message_id']}",
        source_ref=row["message_id"],
        detail={"via": signal.via, "inbound_email_id": inb.id,
                "token_sha256": sha256_hex(signal.token) if signal.token else None,
                "from_address_hmac": inb.from_address_hmac})
    emit_event(conn, row["message_id"], "UNSUBSCRIBED",
               actor_type="HUMAN", actor_id=None, detail={"via": signal.via})
    audit.write(conn, action="UNSUBSCRIBE_RECEIVED", entity="suppressions",
                entity_id=sup_id, actor="ANONYMOUS",
                detail={"token_sha256": sha256_hex(signal.token) if signal.token else None,
                        "message_id": row["message_id"], "inbound_email_id": inb.id,
                        "via": signal.via, "suppression_id": sup_id})
    return sup_id
```

| Property | How |
|---|---|
| **Idempotent** | `policy.suppress()` (`05` §5.3.2) is idempotent: an existing live row for `(scope, value_norm)` wins. The same mail re-ingested writes no second suppression, and `ux_inbound_msgid` means it is normally not re-ingested at all. Two genuine unsubscribes from the same person produce one suppression and two `UNSUBSCRIBED` events, which is correct — they pressed the button twice |
| **Atomic with the ingest** | One transaction. There is no state in which the message is stored and the opt-out is pending |
| **No authentication** | Nothing to authenticate. §7.7.2 |
| **Business-wide effect** | The row is `scope='EMAIL'`, but gate A (`05` §5.9.3) joins every contact point of the business, so the next eligibility check blocks **every** channel for that business — §30, and the recipient's expectation |
| **Reason code** | `UNSUBSCRIBE_LINK` when a token resolved, `REPLY_OPT_OUT` when it came from body text or an unattributable mail. Both are refusals and both are channel-blind at gate A. The distinction exists so `v_email_health` and the §32 history can tell "used the mechanism we provided" from "wrote and asked" |

**Latency, stated honestly.** The earlier design's HTTPS endpoint honoured an unsubscribe in under
ten milliseconds. This one cannot.

| Interval | Value |
|---|---|
| Recipient acts → mail reaches the Gmail mailbox | Seconds |
| Mail in mailbox → `poll_inbox` reads it | Up to `poll_inbox`'s 2-minute schedule (`14` §14.9.4) — **while the laptop is running** |
| Laptop closed | **Unbounded.** Overnight, a weekend, a week |
| Target | Honoured within 2 minutes of the mailbox being polled, and within 5 minutes of the application starting |

The unbounded case is the one that matters, and it is a direct consequence of `_CONTEXT.md` §2's
"the machine is not on 24/7". **The queued-message problem is the real risk**: fifteen messages are
approved on Friday, three are still `QUEUED` when the laptop closes, and the recipient of one of them
unsubscribes on Saturday. On Monday the queue drains.

Two rules close it, and the second is the one that actually matters:

1. **Gate A is re-evaluated inside the send transaction, immediately before transmission**, not when
   the message was queued. `05` §5.9.3 and step 2 of §7.10.1. A `QUEUED` message whose business was
   suppressed at any point since approval is **blocked at send time**, not merely dequeued — it moves
   to `CANCELLED` with `A_SUPPRESSED_EMAIL`, appears in the `BLOCKED` band on `/outreach` with a full
   sentence, and is never transmitted. Dequeuing would not be enough: a message can be re-queued by a
   retry path or an operator, and the gate is what makes the answer the same every time.
2. **No message may be sent until the mailbox has been read in this process lifetime.** Step 0 of
   §7.10.1: `send_email` defers if `poll_inbox` has not completed successfully since the worker
   started. On a machine that has been closed for four days, the first thing that happens on launch
   is a poll, and only then does the queue drain. The cost is a delay of seconds; the failure it
   prevents is mailing somebody who asked to be left alone while the laptop was shut.

Rule 2 is cheap, and it is the closest this stack can get to the property the HTTPS endpoint had for
free. It is stated again as a precondition in §7.10.1 and tested in §7.16 case 12.

### 7.7.8 The crawler-prefetch bug is gone; what replaced it

The earlier revision documented at length a real and nasty bug: corporate mail security appliances
(Microsoft Defender Safe Links, Proofpoint URL Defense, Mimecast URL Protect, Barracuda Link
Protection) fetch every URL in an incoming message to check it. If `GET /u/<token>` had written the
opt-out, a large fraction of corporate recipients would have been unsubscribed by a security
appliance before a human ever opened the message — and because opt-out is permanent and unclearable
by the application (invariant 3), the damage would have been unrepairable through the product. Seven
layered mitigations existed to prevent it.

**All of that is deleted, because there is no URL to prefetch.** The `mailto:` mechanism has no HTTP
surface at all, which removes an entire class of automated false opt-out. That is a genuine, if
accidental, benefit of the constraint.

The equivalent residual risk is smaller but not zero:

| Risk | Assessment |
|---|---|
| **A mail client auto-sending the `List-Unsubscribe` `mailto:` without the user asking** | This is the direct analogue, and it essentially does not happen. Clients do not silently send mail on a user's behalf from reading a message; sending mail is a visible, attributable act and clients treat it as one. The button exists, and pressing it is a deliberate action by a person. Some clients confirm first ("Unsubscribe from this sender?"), which is *more* friction than the HTTPS one-click flow had, not less |
| **A security appliance that "tests" a `mailto:`** | Appliances rewrite and follow `http(s)` URIs. They do not compose and send mail — doing so would make the appliance a spam source, and the vendors know it |
| **A shared mailbox where one person unsubscribes for everyone** | Real, and identical under any mechanism. It is also the correct outcome: the address is one inbox and one inbox asked to stop |
| **A mail loop: our unsubscribe address auto-replying to an auto-reply** | Prevented structurally — this system never sends automatically to anybody, ever (invariant 6). Nothing on the `+unsub-` path composes mail. §7.8.7 rule 7 detects loops caused by the *other* side |
| **Does the residual risk matter?** | **No.** And the asymmetry is the same as before: an unsubscribe that fires when the person did not intend it costs one prospect; an unsubscribe that fails to fire costs the thing the whole system exists to protect. Where those trade off, this design always errs toward suppressing |

One thing genuinely got worse, and it is worth recording next to the thing that got better: with the
HTTPS endpoint, the `UNSUBSCRIBE_RECEIVED` audit row carried the requester's IP address and user
agent, which is strong evidence in a dispute. Now it carries the inbound message id, the `From`
address HMAC and the raw `.eml` under `P3Y` retention. That is different evidence, arguably better
evidence — a whole message, in the recipient's own words, that a human sent — and it is what
§7.12.3 permits us to keep.

### 7.7.9 Test matrix

| # | Case | Expected |
|---|---|---|
| 1 | Client-generated unsubscribe to `+unsub-<valid token>`, empty body | One `suppressions` row `UNSUBSCRIBE_LINK`, one `UNSUBSCRIBED` event, one `UNSUBSCRIBE_RECEIVED` audit row |
| 2 | The same mail ingested twice (UIDVALIDITY reset) | One `inbound_emails` row, one `suppressions` row, one audit row |
| 3 | Two genuinely different unsubscribe mails, same address | One `suppressions` row, **two** `UNSUBSCRIBED` events |
| 4 | Unsubscribe to `+unsub-<token>` where the token was minted under a different secret | No token-resolved suppression; falls through to §7.7.6, sender address suppressed, unmatched band |
| 5 | Unsubscribe to bare `+unsub@` with no token, from an address we mailed | `M5` attributes it; normal `UNSUBSCRIBE_LINK` suppression on the business |
| 6 | Unsubscribe to bare `+unsub@` from an address we have never seen | `REPLY_OPT_OUT` suppression on the sender address with `business_id IS NULL`; unmatched band; one notification |
| 7 | Reply "STOP" on the `+msg_` tagged address | `UNSUBSCRIBE` kind, suppression before any `classify_response` job is enqueued, **no `responses` row consumed by an LLM before the suppression exists** |
| 8 | Reply "please remove us from your list" as the first line, quoted original below | Matches `_OPT_OUT` after quote-stripping; suppressed |
| 9 | Reply whose only occurrence of "unsubscribe" is inside the quoted copy of our own footer | **Not** an unsubscribe. Classified `REPLY` and passed to `09` |
| 10 | After any of the above, `check_send_eligibility()` for that business on `WHATSAPP` | Blocked by gate A |
| 11 | A message `QUEUED` for that business at the moment the unsubscribe is ingested | Never transmitted. Gate A blocks it inside the send transaction; status `CANCELLED`, reason `A_SUPPRESSED_EMAIL`, shown in the `BLOCKED` band |
| 12 | Worker starts with unread unsubscribe mail in the mailbox and 3 `QUEUED` messages | The poll runs first; the suppression exists before the first `send_email` is allowed to transmit |
| 13 | `apply_unsubscribe()` raises after the suppression insert (fault injection) | Transaction rolls back, UID cursor unmoved, next poll re-processes, exactly one suppression at the end |
| 14 | `identity.from_address` with a 40-character local part | `ConfigError` at boot; no live transport is constructed |
| 15 | Built MIME contains `List-Unsubscribe-Post` | `T8` blocks; message `FAILED` with `TRANSPORT_CHECK` |

---
## 7.8 Threading and reply capture

### 7.8.1 `Message-ID`, and the one thing Gmail may take away

```python
# radar/email/threading.py

def derive_message_id(message_id: str, from_domain: str = "gmail.com") -> str:
    """The RFC 5322 Message-ID for an outreach_messages row. Deterministic.

    Deterministic because it must be reconstructible from the row alone, months later,
    when a reply arrives quoting it. It is also the reconciliation key for the crash window
    in 7.10.2, which is why it is generated and recorded BEFORE the socket is opened rather
    than read back from a response that does not carry one.

    It buys one thing for free: if reconciliation is ever wrong and a message is transmitted
    twice, both copies carry the same Message-ID, and most receiving mail stores collapse
    duplicates on exactly that.
    """
    return f"<{message_id}@{from_domain}>"
```

`msg_01JB3K7QW5ZXY8N4MDP2VR6T9C` is a ULID with a type prefix (`01-data-model.md` §1.1.3). It is
opaque, globally unique by construction, and leaks nothing about the recipient. Check `T6` (§7.6.4)
asserts the built header equals this function's output before the message goes out.

**The caveat that is new on this stack, and it is a real one.** A submission server is entitled to
replace a client-supplied `Message-ID`, and Gmail has historically done so for mail submitted through
`smtp.gmail.com`, substituting one of its own in the `CA...@mail.gmail.com` form. Whether it does so
for a given account is not something a specification can settle, so the design does not assume either
way:

| We do | Because |
|---|---|
| Generate our own, put it in the header, and **record it in `outreach_messages.provider_message_id` before the send** | It is the reconciliation key (§7.10.2) whether or not it survives the hop, and it is the only value that exists at the moment the crash window opens |
| Treat its survival as **unknown until measured on the actual account** | §7.4.7 step 9. `python main.py email test-send` prints the ID we generated and the ID present in the received copy, side by side |
| Learn the delivered id from the Sent copy when they differ | §7.10.4's `[Gmail]/Sent Mail` search records the Gmail-assigned `Message-ID` in `outreach_events(SEND_RECONCILED)` detail, and — where present — `X-Google-Original-Message-ID`, which is how the two are tied together |
| Match inbound replies against **both** | §7.8.8 `M1` queries our derived id and any recorded delivered id |
| **Not** depend on it for attribution | §7.8.3. The plus-addressed `Reply-To` is a tag we place in an address rather than a header a server may rewrite, and it is therefore the primary mechanism on this stack where `Message-ID` was primary on the last one |

Parsing back is the inverse and is case-insensitive on the ULID half, because Crockford base32 is:

```python
_MSGID_RE = re.compile(r"<(msg_[0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{26})@([^>]+)>", re.I)

def message_ids_in(header_or_body: str) -> list[str]:
    """Every one of our Message-IDs appearing in a header or a quoted body, upper-cased."""
```

Upper-casing before the database lookup matters: `outreach_messages.id` is stored in Crockford's
canonical upper case, and a reply quoting the header in lower case must still find its row.

### 7.8.2 `In-Reply-To` and `References`

A follow-up (`outreach_messages.sequence_no > 1`, `parent_message_id` set) threads onto its parent.

```python
def thread_headers(conn, message_id: str) -> tuple[str | None, tuple[str, ...]]:
    """(In-Reply-To, References) for a message, walking parent_message_id to the root.

    Threading a follow-up is honest - it is a follow-up, and the recipient's client showing
    it under the original is a true statement about what it is. It also makes rule R3's
    'Re:' prefix legitimate, which the policy engine already checks against thread_key.

    It uses the delivered Message-ID where one was recorded and our derived one otherwise,
    because a References chain that names an id the recipient's client never saw threads
    nothing.
    """
    chain = []                                     # root first
    cur = conn.execute("SELECT parent_message_id FROM outreach_messages WHERE id = ?",
                       (message_id,)).fetchone()["parent_message_id"]
    while cur:
        chain.insert(0, cur)
        cur = conn.execute("SELECT parent_message_id FROM outreach_messages WHERE id = ?",
                           (cur,)).fetchone()["parent_message_id"]
    if not chain:
        return None, ()
    refs = tuple(delivered_or_derived_message_id(conn, m) for m in chain)
    if len(refs) > 10:                             # RFC 5322 guidance: keep the root and the tail
        refs = (refs[0],) + refs[-9:]
    return refs[-1], refs
```

`contact_policy.max_followups` is 2, so the chain is at most three deep in practice. The cap exists
because a `References` header that grows without bound is a header that gets truncated in transit by
somebody else's rules rather than ours.

### 7.8.3 The return path: plus-addressing, and nothing else

Three candidate mechanisms for making a reply identify its message. On the paid stack, all three were
available and `Message-ID` was primary. Here:

| Mechanism | Attribution strength | Available on this stack |
|---|---|---|
| `Message-ID` in the reply's `In-Reply-To`/`References` | Exact when it fires | **Conditional.** Depends on whether Gmail preserved our id (§7.8.1). Free to check, so it is checked first |
| Plus-addressed `Reply-To` (`<base>+msg_01jb...@gmail.com`) | Exact, survives header stripping, survives a `Message-ID` rewrite | **Yes, and it is now the load-bearing one.** Gmail delivers `+tag` mail to the same mailbox and records the tag in `Delivered-To` |
| VERP envelope sender (`bounce+msg_...@`) | Exact, and it is what a **bounce** carries | **No.** Gmail sets the envelope sender to the account address on submission. There is no VERP on this stack, and §7.9.6 attributes bounces from the returned original headers instead |

The `Reply-To` header is:

```
Reply-To: Sagar <sagar.radar.mail+msg_01jb3k7qw5zxy8n4mdp2vr6t9c@gmail.com>
```

and the signature prints the untagged `sagar.radar.mail@gmail.com`, which is what rule `R2` compares
byte-for-byte against `identity.from_address`. Both are the same mailbox. The consequence is exactly
the design intent:

- A recipient who clicks Reply uses the tagged address. Attribution is exact and does not depend on
  any header surviving.
- A recipient who copies the address out of the signature uses the untagged one. Attribution falls
  back to rule `M5` (address match), which is fine.
- Neither address is a machine-looking string in the visible sense: the display name is "Sagar", and
  the long local part is only visible to somebody who looks at the raw address.

**Verify the tag arrives.** §7.4.7 step 7 is not optional. If plus-addressing were disabled or the
tag were stripped, `M2` would stop firing and the whole attribution design would quietly degrade to
address matching, which fails exactly in the case that matters most — the managing director replying
from a different address than the one we mailed.

### 7.8.4 IMAP polling, and what a laptop changes

| | IMAP poll (every 2 min) | IMAP IDLE | Provider inbound webhook |
|---|---|---|---|
| Latency | up to 2 min while running | seconds | seconds |
| Works on this stack | **yes** | yes | **no — impossible.** Nothing on the internet can reach `127.0.0.1` |
| Fits the job model | **yes** — a bounded job that claims a lease, does work, returns | **no** — a socket held open for 29 minutes is a job that never returns, a lease renewed indefinitely, and one of three `io` threads permanently occupied | n/a |
| Behaviour on a network blip | next slot picks up everything; the UID cursor did not move | reconnect logic, `NOOP` keepalives, and a reconnect storm when the wifi flaps | n/a |
| Behaviour when the laptop is closed for a week | The next poll reads a week of mail. The UID cursor makes it exactly correct | The connection died on day one and nothing noticed | n/a |
| Mailbox stays human-readable | yes — Sagar can open the account in a browser at any time and see everything the poller saw | yes | n/a |
| Duplicate protection | `ux_inbound_msgid` | same | n/a |

**Ruling: IMAP polling, matching `14-background-jobs.md` §14.8.13's existing `poll_inbox` contract**
(2-minute schedule, `SKIP` catch-up, UID cursor in `config/state/imap_uid.json`, three retries on the
`fast` policy). The webhook column is not a rejected alternative any more, it is an impossibility, and
`response.ingest`'s `webhook` and `both` values are deleted from the config enum (§7.14).

Three additions the laptop forces, none of which existed in the earlier revision:

| # | Addition | Reason |
|---|---|---|
| 1 | **Run one poll immediately at worker startup**, before the scheduler's first 2-minute tick, and before any `send_email` may transmit (§7.7.7 rule 2, §7.10.1 step 0) | The machine was off. The mailbox may hold an unsubscribe from Saturday and it is Monday morning |
| 2 | **Bound the batch**: `email.poll_max_per_run` (default 200) messages per run; if the folder holds more, ingest 200, commit, and re-enqueue `poll_inbox` immediately rather than waiting for the next tick | `poll_inbox` has a 15-second duration budget and a 180-second lease (`14` §14.7.1). A week of accumulated mail must not blow either, and a partial batch is safe because the UID cursor advances per message |
| 3 | **`catch_up = 'SKIP'` stays correct** | Running four missed inbox polls achieves nothing the current one will not — the current one reads everything since the cursor. This is exactly the case `14` §14.9.5 describes, and the laptop makes it more true, not less |

Latency is therefore: 2 minutes while the machine is running, plus however long it was closed. §7.7.7
states what that means for opt-outs and how the send-time gate covers it. For a reply, the
consequence is only that a lead is seen when Sagar next opens his laptop — which is also when he
would have read it.

### 7.8.5 `inbound_emails`

`01-data-model.md` §1.9.1 makes `responses.business_id` `NOT NULL`. `14-background-jobs.md`
§14.8.13's rule 5 says an unmatched reply becomes a `responses` row with `business_id = NULL`. Those
cannot both be true, and `01` is the arbiter. **An unattributable message therefore does not become a
`responses` row at all**, which is also the better design: `responses` stays the table of replies
from known businesses, and everything that arrives in the mailbox lands first in a staging table that
keeps the raw bytes, absorbs redelivery, and holds the things that are not replies.

```sql
-- radar/migrations/055_inbound_emails.sql
CREATE TABLE inbound_emails (
    id                  TEXT PRIMARY KEY,               -- inb_...

    -- INGEST
    ingest              TEXT NOT NULL
                          CHECK (ingest IN ('IMAP','MANUAL','FIXTURE')),
    mailbox             TEXT NOT NULL,                  -- 'outreach'
    provider            TEXT,                           -- 'gmail' | NULL for FIXTURE
    imap_uid            INTEGER,
    imap_uidvalidity    INTEGER,
    received_at         TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    date_header         TEXT,                           -- the sender's own Date, may be a lie

    -- IDENTITY. rfc_message_id is the idempotency key for the whole system.
    rfc_message_id      TEXT NOT NULL,                  -- Message-ID without angle brackets
    rfc_message_id_synth INTEGER NOT NULL DEFAULT 0
                          CHECK (rfc_message_id_synth IN (0,1)),
    in_reply_to         TEXT,
    references_raw      TEXT,

    -- ADDRESSING (11-audit-architecture.md 11.10: raw addresses never reach audit_log)
    from_address_norm   TEXT,
    from_address_hmac   TEXT,
    from_display        TEXT,
    to_address_norm     TEXT,
    delivered_to_norm   TEXT,                           -- Gmail records the +tag here
    return_path_norm    TEXT,
    envelope_tag        TEXT,                           -- the +tag we planted, if present
    subject             TEXT,

    -- AUTHENTICATION, as Gmail's receiving side saw it
    spf_result          TEXT,
    dkim_result         TEXT,
    dmarc_result        TEXT,

    -- CONTENT
    size_bytes          INTEGER NOT NULL,
    raw_path            TEXT NOT NULL,                  -- data/inbound/YYYY/MM/<id>.eml.gz
    raw_sha256          TEXT NOT NULL,
    body_text           TEXT,                           -- extracted, quoted part stripped
    body_scrubbed       TEXT,                           -- 7.8.12: the only form an LLM may see
    body_excerpt        TEXT,                           -- first 280 chars of body_scrubbed

    -- WHAT IT IS (7.8.7)
    kind                TEXT NOT NULL DEFAULT 'UNKNOWN'
                          CHECK (kind IN ('REPLY','AUTO_REPLY','BOUNCE','COMPLAINT',
                                          'UNSUBSCRIBE','LOOP','SPAM','UNKNOWN')),
    auto_submitted      TEXT,
    precedence          TEXT,

    -- ATTRIBUTION (7.8.8)
    state               TEXT NOT NULL DEFAULT 'NEW'
                          CHECK (state IN ('NEW','MATCHED','UNMATCHED','ACTIONED',
                                           'IGNORED','FAILED')),
    match_rule          TEXT CHECK (match_rule IS NULL OR match_rule IN
                          ('M1','M2','M3','M4','M5','M6','M7','M8')),
    matched_message_id  TEXT REFERENCES outreach_messages(id),
    matched_business_id TEXT REFERENCES businesses(id),
    attribution         TEXT CHECK (attribution IS NULL OR attribution IN
                          ('THREAD_HEADER','PROVIDER_ID','ADDRESS_MATCH',
                           'OPERATOR','UNATTRIBUTED')),
    attribution_confidence TEXT CHECK (attribution_confidence IS NULL OR
                          attribution_confidence IN ('HIGH','MEDIUM','LOW')),
    response_id         TEXT REFERENCES responses(id),

    -- DSN (7.9)
    dsn_action          TEXT,                           -- RFC 3464 Action:
    dsn_status          TEXT,                           -- RFC 3463 Status: e.g. '5.1.1'
    dsn_diagnostic      TEXT,
    dsn_final_recipient TEXT,
    bounce_class        TEXT CHECK (bounce_class IS NULL OR bounce_class IN
                          ('HARD','SOFT','BLOCKED','UNKNOWN')),
    arf_feedback_type   TEXT,                           -- 7.9.4: nothing populates this in v1

    error               TEXT,
    created_at          TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

    CHECK (state <> 'MATCHED' OR (matched_message_id IS NOT NULL
                                  AND matched_business_id IS NOT NULL
                                  AND match_rule IS NOT NULL
                                  AND attribution IS NOT NULL)),
    CHECK (state <> 'FAILED' OR error IS NOT NULL),
    CHECK (kind <> 'BOUNCE' OR bounce_class IS NOT NULL),
    CHECK (length(body_excerpt) IS NULL OR length(body_excerpt) <= 280)
);

CREATE UNIQUE INDEX ux_inbound_msgid    ON inbound_emails(mailbox, rfc_message_id);
CREATE UNIQUE INDEX ux_inbound_uid      ON inbound_emails(mailbox, imap_uidvalidity, imap_uid)
    WHERE imap_uid IS NOT NULL;
CREATE INDEX ix_inbound_state           ON inbound_emails(state, received_at);
CREATE INDEX ix_inbound_unmatched       ON inbound_emails(received_at)
    WHERE state = 'UNMATCHED';
CREATE INDEX ix_inbound_message         ON inbound_emails(matched_message_id);
CREATE INDEX ix_inbound_business        ON inbound_emails(matched_business_id, received_at);
CREATE INDEX ix_inbound_from            ON inbound_emails(from_address_norm, received_at);
CREATE INDEX ix_inbound_kind            ON inbound_emails(kind, received_at);
```

| Index | Query it serves |
|---|---|
| `ux_inbound_msgid` | **The idempotency guarantee.** `poll_inbox` re-scanning after a `UIDVALIDITY` change, and a re-ingest of a saved `.eml`, both collapse here rather than creating duplicate leads or duplicate suppressions |
| `ux_inbound_uid` | The UID cursor's correctness check; also detects a `UIDVALIDITY` change |
| `ix_inbound_unmatched` | The unmatched-replies band on `/outreach`, and the 24-hour nag |
| `ix_inbound_message` | The §32 history panel: every inbound artefact attached to a message, including the bounce DSN |
| `ix_inbound_kind` | Counting auto-replies separately from real ones, which is the difference between a 30% reply rate and a real one |

Four changes from the earlier revision. `ingest` loses `'WEBHOOK'`. `kind` loses `'DMARC_REPORT'` and
`'TLS_REPORT'` — we publish no `rua` or TLS-RPT address, so no such report will ever arrive.
`body_scrubbed` is added for §7.8.12. And `arf_feedback_type` stays but is documented as
never-populated in v1 (§7.9.4): a free Gmail account is in no feedback loop, so no ARF report is
generated by anybody on our behalf. The column costs nothing and its absence would be the thing that
needs a migration on the day a third-party receiver does send one.

`rfc_message_id_synth = 1` marks a message that arrived with no `Message-ID` header at all; the value
is then `sha256(from_norm || date_header || subject || size_bytes || first 512 bytes of body)`,
prefixed `synth:`. Rare, and almost always spam, but it must not break the unique index.

### 7.8.6 The ingest pipeline

```python
# radar/email/inbound.py

def ingest_one(conn, raw: bytes, *, ingest: str, mailbox: str,
               uid: int | None, uidvalidity: int | None, cfg: Config) -> IngestResult:
    """Store one inbound message, decide what it is, and try to attribute it.

    Order matters and is not negotiable. The raw bytes are written and committed before
    anything is parsed, because a parser crash on a malformed message must not lose the
    message - and a message that cannot be parsed is exactly the one somebody will need to
    read by hand. Attribution runs after classification because a bounce and a reply from
    the same address are different events, and matching them the same way is how a
    mailer-daemon becomes an INTERESTED lead.
    """
```

| Step | Action | Failure |
|---|---|---|
| 1 | Write `raw` to `data/inbound/YYYY/MM/<inb_id>.eml.gz`, atomically | Abort; the UID cursor does not advance |
| 2 | `INSERT INTO inbound_emails ... ON CONFLICT (mailbox, rfc_message_id) DO NOTHING` with `state='NEW'` | A conflict means already ingested: return `duplicate`, advance the cursor |
| 3 | Parse headers; fill addressing, authentication and threading columns | On exception: `state='FAILED'`, `error`, and it appears in the unmatched band |
| 4 | Classify `kind` (§7.8.7) | Default `UNKNOWN`, which routes to a human |
| 5 | Extract `body_text` with the quoted reply stripped; produce `body_scrubbed` (§7.8.12); take `body_excerpt` from the scrubbed form | — |
| 6 | Attribute (§7.8.8) -> `state='MATCHED'` or `'UNMATCHED'` | — |
| 7 | For `kind='UNSUBSCRIBE'`, and for any message whose first unquoted line matches the opt-out pattern: `apply_unsubscribe()` (§7.7.7), **in this transaction, before anything else acts on the message** | — |
| 8 | For `kind='REPLY'` and `state='MATCHED'`: insert the `responses` row, set `response_id`, enqueue `classify_response` **in the same transaction** (`14` §14.8.15) | — |
| 9 | For `kind='BOUNCE'`: apply §7.9's side effects in the same transaction | — |
| 10 | `state='ACTIONED'`; advance the UID cursor | — |

Step 7 moved ahead of the reply handling in this revision, and the reason is the LLM change rather
than the hosting one: `classify_response` sends text to Gemini, and a message whose first line is
"unsubscribe" should have produced a suppression **before** any part of it is queued for a network
call that may be rate-limited for a day. The suppression is deterministic, local and free; the
classification is neither.

The UID cursor is advanced **after** the transaction commits, never before. Re-processing a message
is free (step 2 absorbs it); losing one is not.

`UIDVALIDITY` change handling is `14` §14.8.13's, unchanged: log an `ERROR` naming the old and new
values, reset the cursor to 1, re-scan, and let `ux_inbound_msgid` absorb the re-scan. Recover
loudly, never silently reset. On Gmail specifically, a `UIDVALIDITY` change is rare but a **folder
rename or a label change is not**, which is why `poll_inbox` reads `INBOX` by name and never a label
Sagar might reorganise.

### 7.8.7 What kind of message is it

Run in order; first match wins. Every rule is a header or structural test, never a guess about
wording.

| # | `kind` | Test |
|---|---|---|
| 1 | `BOUNCE` | `Content-Type: multipart/report; report-type=delivery-status` (RFC 3464), **or** `From` matches `mailer-daemon@googlemail.com` / `mailer-daemon@` / `postmaster@` with a `message/delivery-status` part |
| 2 | `COMPLAINT` | `multipart/report; report-type=feedback-report` (ARF, RFC 5965). §7.9.4: nothing in this build generates one, and the rule exists so that one arriving from a third party is not silently read as a reply |
| 3 | `UNSUBSCRIBE` | `find_unsubscribe()` (§7.7.5) returns a signal: a `+unsub-` recipient tag, a bare `+unsub` recipient, or a first unquoted body line matching `/^\s*(stop|unsubscribe|remove|opt.?out)\b/i` |
| 4 | `AUTO_REPLY` | `Auto-Submitted:` present and not `no` (RFC 3834); or `Precedence: auto_reply\|bulk\|junk`; or `X-Autoreply`, `X-Autorespond`, `X-Auto-Response-Suppress` present; or `Return-Path: <>` on a non-DSN |
| 5 | `LOOP` | More than `email.loop_threshold` (default 3) messages from the same `from_address_norm` in 10 minutes, all `AUTO_REPLY` |
| 6 | `SPAM` | `dmarc_result = 'fail'` **and** no rule 1-5 matched **and** no thread header or tag of ours appears anywhere in the message |
| 7 | `REPLY` | Everything else |

Two rules from the earlier revision are gone: `DMARC_REPORT` and `TLS_REPORT`, because there is no
domain publishing an `rua` or a TLS-RPT address, so nobody will ever send us one. The
`python main.py email dmarc-report` command goes with them.

Rule 4 is the one most systems omit and it matters more than any other here. Out-of-office
auto-replies are the single most common inbound message a cold campaign receives. Classifying one as
a `REPLY` means an LLM call against a rationed free-tier quota, a `responses` row, possibly an
`INTERESTED` misclassification, a handoff, and a Telegram alert for a message that says "I am on
leave until Monday". An `AUTO_REPLY` is stored, counted, attached to its message for the §32 history,
and **creates no `responses` row, no handoff and no LLM call**.

Rule 3 sits above rule 4 deliberately, and the ordering is a real decision: an auto-responder that
happens to say "to unsubscribe, reply STOP" in its own footer would otherwise be read as an opt-out.
That is why `find_unsubscribe()` matches the **first unquoted line** and matches at the start of it,
not anywhere in the body. §7.7.9 case 9 tests exactly this.

Rule 5 exists because a `LOOP` is what happens when an auto-responder somewhere answers a bounce and
something in between amplifies it. A `LOOP` message is stored, `state='IGNORED'`, and raises a
`send_notification` — because a loop involving our account is an account-reputation event, and on a
free Gmail account the account is the only reputation there is.

### 7.8.8 The matching algorithm

Precedence order. First rule that produces a business wins. `M1`-`M4` are exact and are **not
bounded by time**; `M5`-`M7` are heuristic and are bounded by `response.match_days` (default 60).

| # | Rule | Signal | `attribution` | Confidence | Time bound |
|---|---|---|---|---|---|
| `M1` | **Thread header.** `In-Reply-To` or `References` contains a `Message-ID` of ours — either the one `derive_message_id()` produces, or a delivered id recorded by §7.10.4's Sent-folder reconciliation | Exact | `THREAD_HEADER` | HIGH | none |
| `M2` | **Planted tag.** The `+msg_<ulid>` tag from our `Reply-To`, found in `Delivered-To`, `To`, `X-Original-To` or `Envelope-To` | Exact | `THREAD_HEADER` | HIGH | none |
| `M3` | **Unsubscribe tag.** The `+unsub-<token>` tag resolves through `outreach_drafts.unsubscribe_token` | Exact | `PROVIDER_ID` | HIGH | none |
| `M4` | **Quoted header.** One of our `Message-ID`s or tags appears in the raw body, typically inside a quoted or forwarded block | Strong | `THREAD_HEADER` | MEDIUM | none |
| `M5` | **Address.** `from_address_norm` equals a `business_contacts.value_norm` for a business with an `outreach_messages` row `SENT` in the window | Strong | `ADDRESS_MATCH` | MEDIUM | `match_days` |
| `M6` | **Loose address.** `from_address_norm`'s `value_dedupe` matches (`05` §5.9.2: `+tag` stripped, Gmail dots folded) | Moderate | `ADDRESS_MATCH` | LOW | `match_days` |
| `M7` | **Domain.** The sender's eTLD+1 equals `outreach_messages.recipient_domain` for exactly one business in the window | Weak | `ADDRESS_MATCH` | LOW | `match_days` |
| `M8` | **Operator.** Sagar attached it by hand from the unmatched band | Exact | `OPERATOR` | HIGH | none |
| — | No rule fired | — | `UNATTRIBUTED` | LOW | — |

`M3` is new in this revision: the unsubscribe tag is a second planted tag with its own resolution
path, and on the mailto: mechanism it is a first-class attribution signal rather than a footnote. It
maps onto `attribution='PROVIDER_ID'` because that CHECK value is otherwise unused now that there is
no provider callback — see Open questions, where the honest fix is a `RETURN_PATH_TAG` value in
`01` §1.9.1.

```sql
-- radar/email/inbound.py :: M1_SQL       params: :ids (from message_ids_in())
SELECT m.id AS message_id, m.business_id, m.thread_key, m.sequence_no, m.campaign_id,
       m.contact_id
  FROM outreach_messages m
 WHERE (m.id IN (SELECT value FROM json_each(:ids))
        OR m.provider_message_id IN (SELECT value FROM json_each(:raw_ids)))
   AND m.channel = 'EMAIL'
 ORDER BY m.sequence_no DESC
 LIMIT 1;

-- radar/email/inbound.py :: M5_SQL       params: :from_norm, :since
SELECT m.id AS message_id, m.business_id, m.thread_key, m.sequence_no, m.campaign_id,
       c.id AS contact_id, COUNT(*) OVER () AS n_candidates
  FROM outreach_messages m
  JOIN business_contacts c
    ON c.business_id = m.business_id AND c.kind = 'EMAIL'
   AND c.value_norm = :from_norm
 WHERE m.channel = 'EMAIL'
   AND m.status IN ('SENT','DELIVERED','BOUNCED')
   AND m.sent_at >= :since
 ORDER BY m.sent_at DESC;
```

`M5` and `M7` both compute `n_candidates`. **If more than one business matches, the rule does not
fire** and evaluation continues to the next; if no later rule fires, the message is `UNMATCHED`. An
ambiguous match is not a match, and guessing between two businesses is exactly the error that would
attach a demo request to the wrong company.

### 7.8.9 The cases that break naive matching

| Case | What arrives | What happens | Why it works |
|---|---|---|---|
| **Reply from a different address.** We mailed `info@abc-hospital.in`; the managing director replies from `dr.rao@abc-hospital.in`, or from a personal Gmail | `To:` is the `+msg_` tagged address their client offered | `M2` fires. `From` is never consulted | This is why the planted tag outranks every address rule. The reply is attributed to the exact message even though the sender is somebody we have never seen |
| **Gmail rewrote our `Message-ID` on submission** | The reply's `In-Reply-To` names an id we never generated | `M1` misses on our derived id, hits on the recorded delivered id if §7.10.4 found one; `M2` fires regardless | **The failure mode of a rewritten `Message-ID` is a rule that does not fire, not a wrong match.** That is the entire reason attribution has two independent exact rules on this stack |
| **Thread headers stripped.** The recipient composed a new message, or a gateway rewrote the headers | No `In-Reply-To`, but `To` is `<base>+msg_01jb...@gmail.com` | `M2` fires | The tag is in the address, not in a header an intermediary rewrites |
| **Both stripped, address typed by hand from the signature** | `To: sagar.radar.mail@gmail.com`, no tag, no thread header | `M5` on `from_address_norm` | Degrades to `MEDIUM`, still attributed |
| **Forwarded reply from a colleague.** `info@` forwards our mail to `accounts@` who answers us | `From` is an address we have never contacted; the body quotes our full message including its headers | `M4` fires on the quoted id or tag; `attribution_confidence = 'MEDIUM'` | A forward is evidence of a route, not necessarily an answer. MEDIUM is what makes `10-human-handoff.md` show it to Sagar rather than act on it |
| **Reply to a follow-up, not the original** | `In-Reply-To`/`To` names the sequence-2 message | `M1`/`M2` resolve to that row; `responses.message_id` is the follow-up. `thread_key` comes from the matched row, so the §32 history groups the whole conversation | `sequence_no` on the matched message is also the answer to "which touch produced the reply", which is the only honest input to §54's funnel |
| **Reply arriving months later.** A message from March answered in September | `M1`-`M4` fire regardless of age; `M5`-`M7` would not | Attributed, `responses` row created, handoff created if the classification triggers | **Age never invalidates an exact match.** Age only bounds the heuristics, because an address match nine months on is a coincidence and a planted tag is not |
| **Reply from a business that has since been suppressed** | Any of the above | Stored, attributed, `responses` row created, handoff created | An opt-out blocks **outbound**. It has never blocked listening. A reply from a suppressed business is often "actually, tell me more" or a complaint, and both need a human. Nothing automatic is ever sent back |
| **Out-of-office** | `Auto-Submitted: auto-replied` | `kind='AUTO_REPLY'`, attributed, **no `responses` row, no LLM call** | §7.8.7 rule 4 |
| **Two businesses share `info@` at a shared-hosting domain** | `M5` returns two candidates | Rule does not fire; falls through to `UNMATCHED` | Gate F2 (`05` §5.9.8) already refuses to mail one address for two businesses; if it happened anyway, the reply goes to a human rather than to the wrong file |
| **The laptop was closed for five days** | Sixty messages at once, mixed kinds | Batched at 200/run (§7.8.4), each ingested and attributed independently, cursor advancing per message | Nothing about attribution is time-of-arrival sensitive. The only thing five days costs is five days |

### 7.8.10 When attribution fails

`state = 'UNMATCHED'`. Nothing is guessed, and nothing is discarded.

| Surface | Behaviour |
|---|---|
| `/outreach` | An **Unmatched replies** band above the batch list: sender, subject, excerpt, arrival time, and an "Attach to…" control |
| `POST /api/v1/inbound/<inb_id>/attach` | Session-authenticated. Body `{"message_id": "msg_..."}` or `{"business_id": "biz_..."}`. Creates the `responses` row with `attribution='OPERATOR'`, `attribution_confidence='HIGH'`, sets `match_rule='M8'`, enqueues `classify_response` |
| `POST /api/v1/inbound/<inb_id>/ignore` | Body `{"reason": "..."}`. `state='IGNORED'`. For spam and misdirected mail |
| Nag | An `UNMATCHED` row older than 24 h raises one `send_notification` per day listing the count. An unattributable **unsubscribe** (§7.7.6) notifies the same day, not after 24 h. `10-human-handoff.md` owns the notifier |
| Daily report | `14` §14.8.18's morning message carries `unmatched_inbound` as a line item |
| Audit | `RESPONSE_UNMATCHED` (`11` §11.6), with `from_address_sha256` and `subject_sha256` — never the raw address |
| Retention | The raw `.eml.gz` is `P3Y`, matching `RESPONSE_RECEIVED` |

The rule this enforces: **an inbound message that cannot be attributed goes to a human. It is never
attributed by inference and never dropped.** A wrong attribution puts a stranger's words in another
business's file, which corrupts the research record, the funnel and possibly a message that gets sent
later; an unmatched row costs Sagar ten seconds.

### 7.8.11 Addresses discovered in a reply are not captured

When a forwarded reply arrives from `accounts@abc-hospital.in`, the system now knows an address it
did not have. It does **not** write a `business_contacts` row for it.

| Reason | Detail |
|---|---|
| DPDP purpose limitation | The address was disclosed to answer one message, not to be added to a prospecting database. Storing it as a contact and mailing it later is processing for a purpose the person never saw |
| `human_verified` | `01-data-model.md` §1.5.5's `UPSERT_CONTACT_SQL` never sets `human_verified` from capture, and gate E requires it. An auto-captured address could not satisfy `CONTACT_READY` anyway |
| The failure it prevents | Auto-capturing reply-senders is how a system ends up mailing a person who wrote in once to say "wrong department" |

What happens instead: the address is on the `inbound_emails` row, the verification screen for that
business shows it as a **suggested contact** with its provenance ("appeared as the sender of a reply
on 2026-09-02"), and ticking the §16 checklist item is what creates the `business_contacts` row with
`human_verified = 1`. A human decides.

### 7.8.12 The scrubber: what an inbound message may never carry into an LLM payload

New in this revision, and it exists because of `_CONTEXT.md` §2's first LLM consequence: the build
uses the Gemini **free tier**, whose content may be used by Google to improve their products.
Therefore **no `business_contacts` value — no email address, no phone number, no named individual —
is ever sent to an LLM.**

The outbound half of that rule lives in `06-message-engine.md` (the contact address is substituted
into the rendered message locally, after generation). The **inbound** half lives here, because this
document produces `body_text`, and `09-response-classification.md` sends a reply body to Gemini to
classify it. A reply body is exactly the place where contact data hides:

| Where it hides | Example |
|---|---|
| The quoted copy of our own message | Our signature block, containing `identity.from_address` and Sagar's phone number |
| Our own unsubscribe line | The `+unsub-<token>` address |
| The sender's signature | "Dr. A. R. Rao, Medical Superintendent, +91 XXXXXXXXXX, dr.rao@abc-hospital.in" — a named individual, a phone and an address, all `business_contacts`-shaped |
| The body itself | "please call me on 98xxxxxxxx" |
| Headers pasted into the body by a forward | `From:`, `To:`, `Reply-To:` |

```python
# radar/email/scrub.py
"""The gate between an inbound message and anything that can reach a model.

Without this module a reply body walks into a Gemini free-tier prompt carrying a hospital
administrator's direct line and personal address, and _CONTEXT.md 2's rule - that no
business_contacts value ever reaches an LLM - is broken by the one code path nobody thinks of,
because the outbound half of that rule got all the attention. The scrubber runs at ingest,
once, and what it produces is the ONLY body form any prompt-assembly path is allowed to read.
"""

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?91[\s-]?)?(?:\d[\s-]?){9,13}\d")
_URL_RE   = re.compile(r"https?://\S+")

def scrub_for_model(body_text: str) -> str:
    """Replace every address, phone number and URL with a typed placeholder.

    Placeholders rather than deletion, because the classifier has to be able to tell
    'call me on <PHONE>' (a meeting request) from 'not interested' - the SHAPE of the
    message is signal and the VALUE is not. 09-response-classification.md's stage-1 rules
    already read the scrubbed form and its prompt fixtures are built from it.
    """
    out = _EMAIL_RE.sub("<EMAIL>", body_text)
    out = _PHONE_RE.sub("<PHONE>", out)
    out = _URL_RE.sub("<URL>", out)
    return out
```

| Rule | Detail |
|---|---|
| Where it runs | Step 5 of §7.8.6, at ingest, once, in the same transaction |
| What is stored | `inbound_emails.body_text` (unscrubbed, in the database, under retention and disk encryption) **and** `body_scrubbed`. `responses.body_excerpt` is taken from the **scrubbed** form |
| What may reach a prompt | `body_scrubbed` only. Never `body_text`, never `raw_path`, never `from_address_norm`, never `from_display`, never a `business_contacts` row |
| Why keep the unscrubbed copy at all | Sagar reads the real message on the handoff card, and a scrubbed body is unreadable for the human whose job is to answer it. The unscrubbed form never leaves the machine |
| Over-scrubbing | Accepted. A business name that looks like a phone number is rare; a leaked personal phone number is not recoverable |
| The test that must exist | `_CONTEXT.md` §2 requires it, and §7.16 case 30 is it: assemble every prompt this system can build from a corpus of fixture replies containing known contact values, and **fail if any of those values appears in any payload**. Not a review — an assertion, in CI, that a specific string cannot get through |

`06-message-engine.md` and `09-response-classification.md` both own prompt assembly and both must
read `body_scrubbed`. Cross-referenced in Open questions so neither one has to rediscover it.

---
## 7.9 Bounce and complaint handling

The earlier revision handled both by webhook: SES posted a `Bounce` or `Complaint` notification to an
HTTPS endpoint, the endpoint verified a signature and enqueued a job. **None of that is possible.**
There is no endpoint, no SNS, no signature to verify and no replay window to guard. `email_webhook_events`,
`radar/web/webhooks.py` and the whole of the earlier §7.9.6 are deleted.

What replaces them is asymmetric, and the asymmetry is the most important thing in this section:

| Event | Earlier stack | This stack |
|---|---|---|
| **Bounce** | Provider webhook, structured, seconds | **A DSN in our own mailbox**, structured (RFC 3464), minutes to hours. Fully solvable, and §7.9.6 solves it |
| **Complaint** | Provider feedback loop, structured, hours | **Nothing at all.** A free Gmail account is in no feedback loop. A recipient pressing "report spam" produces no message, no event and no signal we can observe. §7.9.4 |

### 7.9.1 Classifying a bounce

One classifier, one input: the RFC 3463 enhanced status code carried in the DSN.

```python
# radar/email/bounce.py

def classify_bounce(*, dsn_status: str | None, dsn_action: str | None,
                    smtp_code: int | None, diagnostic: str | None) -> str:
    """HARD | SOFT | BLOCKED | UNKNOWN, from the enhanced status code first.

    The enhanced code is structured and the diagnostic text is a free-form string written
    by whoever wrote that MTA. Reading the text first is how 'mailbox full' becomes a hard
    bounce and a real dead address becomes a soft one - and a hard bounce misread as soft
    means four more messages to an address that does not exist, which is the fastest way to
    make a young Gmail account look like a list-blaster.
    """
```

| `Status:` | Meaning | Class | Effect |
|---|---|---|---|
| `5.1.1` | Bad destination mailbox address | `HARD` | §7.9.2 |
| `5.1.2` | Bad destination system (domain does not exist) | `HARD` | §7.9.2, and the domain is flagged on the business |
| `5.1.10` | Recipient address has null MX | `HARD` | §7.9.2 |
| `5.4.1`, `5.4.4` | No answer from host / unable to route | `HARD` | §7.9.2 |
| `5.2.1` | Mailbox disabled | `HARD` | §7.9.2 |
| `5.2.2` | Mailbox full | **`SOFT`** | §7.9.3. A full mailbox is a temporary condition wearing a 5.x code |
| `5.7.1`, `5.7.26`, `5.7.x` generally | Policy rejection, authentication failure, reputation block | **`BLOCKED`** | §7.9.4 |
| `4.x.x` (any) | Transient | `SOFT` | §7.9.3 |
| No enhanced code, SMTP 5xx | — | `HARD` unless the diagnostic matches the mailbox-full or greylisting patterns | §7.9.2 |
| No enhanced code, SMTP 4xx | — | `SOFT` | §7.9.3 |
| Unparseable | — | `UNKNOWN` | Recorded, no suppression, surfaced to Sagar |

`BLOCKED` is separated from `HARD` deliberately. A `5.7.x` policy rejection says something about
**our account**, not about the recipient's address. Suppressing the recipient would be wrong twice
over: the address is fine, and the actual problem — that a receiver is refusing our mail — would be
hidden inside a per-contact suppression instead of raising an alarm. On this stack that matters more
than it did on the last one, because a `5.7.x` is now one of the very few signals available that the
account itself is in trouble (§7.9.4).

### 7.9.2 Hard bounce

One transaction, all of it:

```python
def apply_hard_bounce(conn, *, message_id: str, address_norm: str,
                      business_id: str, evidence: dict) -> None:
    """Deactivate the contact, suppress the address, mark the message, alert nothing.

    A hard bounce is the system working. It needs no human. What it must not do is leave
    the address live: 01-data-model.md 1.5.5 already refuses to re-activate a bounced
    contact when a re-crawl finds it on the website again, and this is the write that makes
    that rule meaningful.
    """
```

| # | Write | Detail |
|---|---|---|
| 1 | `outreach_events` | `event='BOUNCED'`, `actor_type='PROVIDER'`, `provider_event_id = inbound_emails.id`, `detail={"class":"HARD","status":"5.1.1","diagnostic_sha256":...}` |
| 2 | `outreach_messages` | `status = 'BOUNCED'`, `failed_at`, `failure_code='HARD_BOUNCE'` |
| 3 | `business_contacts` | `is_active = 0`, `deactivated_at`, `deactivated_reason = 'BOUNCED'` |
| 4 | `suppressions` | `scope='EMAIL'`, `value_norm=<address>`, `reason='BOUNCE_HARD'`, `source_ref=message_id` |
| 5 | `audit_log` | `OUTREACH_BOUNCED` with `bounce_type='HARD'`, `provider_code`, `diagnostic_sha256`, `suppression_id`, `inbound_email_id` |

`provider_event_id` is now the `inbound_emails.id` of the DSN rather than an SES event id. That keeps
`ux_events_provider_event` (`05` §5.3.7) meaningful — the same DSN re-ingested cannot write a second
event — and it makes the evidence link in the §32 history a row Sagar can actually open and read.

No Telegram alert: a hard bounce is a normal outcome of researching public listings, and paging Sagar
for each one trains him to ignore the channel that also carries demo requests.

**An honest consequence that must be named.** Gate A (`05` §5.9.3) joins `suppressions` against every
contact point of the business and deliberately does not filter by channel — "a phone opt-out blocks
email", which is right for a refusal. But a `BOUNCE_HARD` row is not a refusal: it means one mailbox
does not exist. As `05` is written today, a bounced `info@` address permanently blocks WhatsApp and
phone for that business too. That is over-blocking in the safe direction, so this document does not
unilaterally change another document's gate — but the correct fix is small and is filed as an
amendment request in Open questions: gate A should treat the *refusal* reasons (`UNSUBSCRIBE_LINK`,
`REPLY_OPT_OUT`, `COMPLAINT`, `DNC_LIST`, `LEGAL_REQUEST`, `MANUAL`) as channel-blind, and
`BOUNCE_HARD` as binding only on the `EMAIL` channel. Until that edit lands, step 3 alone would be
sufficient to stop email (gate E2 rejects an inactive contact) and step 4 is what makes it
cross-channel.

### 7.9.3 Soft bounce

A soft bounce does not suppress and does not fail the message. It is recorded, counted, and
eventually gives up.

| Attempt | Behaviour |
|---|---|
| 1st soft bounce on a message | `outreach_events(BOUNCED, detail={"class":"SOFT"})`. `outreach_messages.status` stays `SENT` — Gmail accepted it, and a deferral is not a failure |
| Retry | **None at the message level.** The receiving MTA is already retrying, and so is Gmail's queue; ours would put a third copy in the same queue |
| 3rd soft bounce on the **same address** within `email.soft_bounce_window_days` (default 30) | Treat as `HARD`: run §7.9.2 with `reason='BOUNCE_HARD'` and `detail={"promoted_from":"SOFT","count":3}` |
| A later message to that address | Blocked by gate E2 once promoted |

The give-up threshold is three because the interesting soft-bounce cause at this volume is a mailbox
that has been full for months, which is functionally a dead address. Two is too twitchy for a genuine
greylisting run; five means five messages into a hole.

```sql
-- radar/email/bounce.py :: SOFT_BOUNCE_COUNT_SQL   params: :address_norm, :since
SELECT COUNT(DISTINCT e.message_id) AS n_soft
  FROM outreach_events e
  JOIN outreach_messages m ON m.id = e.message_id
 WHERE m.to_address_norm = :address_norm
   AND e.event = 'BOUNCED'
   AND json_extract(e.detail, '$.class') = 'SOFT'
   AND e.at >= :since;
```

One Gmail-specific note. A `4.x.x` DSN whose diagnostic names Gmail itself rather than the recipient's
server — the daily-limit and rate responses — is **not** a bounce about the recipient and must not be
counted against the address. `classify_bounce()` checks whether `dsn_final_recipient` is the intended
recipient and whether the reporting MTA is `googlemail.com`; a Gmail-side deferral becomes
`bounce_class='UNKNOWN'` with `detail={"origin":"submission"}`, raises a `HIGH` notification, and is
handled as §7.4.8's ceiling problem rather than as a contact problem.

### 7.9.4 Complaints are invisible, and the honest response

**Say this plainly, because every part of the design downstream depends on it being true rather than
comfortable: on this stack, a recipient marking our message as spam produces nothing we can see.**

| Mechanism | Available? | Why not |
|---|---|---|
| ESP complaint webhook | No | There is no ESP |
| A feedback loop (ARF reports from the receiving provider) | No | FBLs are registered per sending IP or per domain by the operator of that IP or domain. The IP and the domain belong to Google. We are not the sender of record for FBL purposes and cannot register |
| Google Postmaster Tools | No | It reports on a **domain** you verify. We have no domain. There is nothing to verify and no dashboard to read |
| Gmail's own "this message is spam" signal | No | It is an input to Google's filters, not an output to the sender |
| A bounce | Sometimes, much later | A recipient who marks spam repeatedly may eventually cause a `5.7.x` from their provider, which arrives as a `BLOCKED` bounce. That is a lagging, lossy proxy and nothing more |

`outreach_events.COMPLAINED` therefore has **no automatic writer for `EMAIL` in v1**. It is not
deleted — the WhatsApp channel writes it, `09-response-classification.md` writes it from a reply
classified `COMPLAINT`, and Sagar can write one by hand — but nothing on the email path produces one
on its own, and any number computed from it is a floor, not a rate. `v_email_health.complaint_pct` is
correspondingly labelled on `/settings` as "complaints we were told about", not "complaint rate".

**The four proxies, and what each is worth.** None of them is a substitute; together they are what we
have.

| # | Proxy | Signal strength | Where it is measured |
|---|---|---|---|
| 1 | **A reply that says so.** "stop sending me this", "this is spam", "how did you get my address" | Strongest available, and it is a *real* complaint even if no button was pressed | `09-response-classification.md` classifies it `COMPLAINT`, which fans out exactly as §7.9.5 describes. This is already built and needs nothing from this document |
| 2 | **A sharp drop in reply rate.** `v_email_health.reply_pct` over 30 days against the previous 30 | Weak individually, meaningful as a trend. A campaign that replied at 8% and now replies at 0% over 40 messages is probably not being read | §7.6.7's view; the daily report carries it; §7.9.4's alarm below |
| 3 | **A cluster of `5.7.x` `BLOCKED` bounces** across unrelated recipient domains | Strong when it happens. Receivers refusing our mail for policy reasons is the closest thing to a direct statement about our reputation | Classified in §7.9.1, mapped in §7.9.5, acted on in the table below |
| 4 | **A Google account warning** — a security or policy notice in the account itself, or a sudden inability to send | Decisive, and it arrives too late to be prevention. It is caught because `poll_inbox` reads the same mailbox those notices land in | §7.9.7 |

**The conservative response**, which is what replaces the automatic complaint machinery:

```
-- radar/email/health.py :: DELIVERY_ALARM_SQL   (evaluated by the daily report job)
```

| Condition | Action |
|---|---|
| Any reply classified `COMPLAINT` (proxy 1) | Immediate, and identical to the earlier design's complaint handling: `suppressions` at `scope='BUSINESS'` **and** `scope='EMAIL'`, `reason='COMPLAINT'`, permanent; `audit_log` `OUTREACH_COMPLAINED` at `P7Y`; Telegram at `HIGH`. §7.9.5 |
| 3 `BLOCKED` bounces across 3 distinct recipient domains in 24 h (proxy 3) | **Pause email**: `contact_policy.email_enabled = 0` with a `SEND_DISABLED_CHANGED` audit row, plus a Telegram alert naming the domains and the status codes |
| `reply_pct` over the last 30 days is `0` with `n_sent >= 40`, and the previous 30 days was non-zero (proxy 2) | **Warn, do not pause.** A Telegram alert and a banner on `/outreach`: "40 messages, no replies, where the previous month replied at 8%. This may mean the account is being filtered. Send a test message to an outside address before continuing." Pausing on a lagging statistical proxy would stop a working system on noise; not warning would let a filtered account keep spending its reputation |
| A Google security/policy notice arrives in the mailbox (proxy 4) | `kind='UNKNOWN'`, `state='UNMATCHED'`, immediate `HIGH` Telegram alert, and `contact_policy.email_enabled = 0`. §7.9.7 |

**Gate H2 still exists and half of it went blind.** `05-outreach-workflow.md` §5.9.10's gate H2
blocks sending when `sent >= bounce_rate_min_sample` (20) and either the bounce rate exceeds
`bounce_rate_max_pct` or the complaint rate exceeds `complaint_rate_max_pct` (0.1). The **bounce**
half is unaffected and is the more useful of the two on this stack, because DSN parsing (§7.9.6)
feeds it accurately. The **complaint** half can now only fire on complaints we were told about, so it
is a floor rather than a rate and will read 0.0 on an account that is being reported daily. It is
kept, because a complaint we *were* told about is exactly the kind that should stop the machine — but
nothing in this document treats a passing H2 as evidence that there are no complaints. The two rows
above are what stands in for the missing half.

Pausing is the only place in this document where the system disables itself, and re-enabling is a
human action at `/settings` — because what fixes a filtered account is investigating it, not waiting.

**And one rule that is more important than all the machinery**: because a complaint cannot be
detected, it cannot be responded to, which means the **only** available defence is not causing one.
That is not a slogan; it is the reason §7.2.5's expiry conditions are enforced structurally rather
than by policy, the reason the ramp starts at three a day, and the reason gate A is re-evaluated
inside the send transaction. On a stack with a feedback loop, the complaint machinery is a safety
net. Here there is no net, so the height matters.

### 7.9.5 The mapping from an inbound artefact to `outreach_events`

The mapping is data, not code: one dict keyed by `(kind, class)`, so a new inbound shape is a table
entry rather than a branch.

```python
# radar/email/events_map.py

@dataclass(frozen=True, slots=True)
class EventMapping:
    event: str                        # an outreach_events.event value
    status: str | None                # new outreach_messages.status, or None to leave it
    suppress: str | None              # a suppressions.reason, or None
    suppress_scope: str | None        # 'EMAIL' | 'BUSINESS'
    alert: str | None                 # notification priority, or None

MAP: dict[tuple[str, str | None], EventMapping] = { ... }
```

| `inbound_emails.kind` + `bounce_class` | `outreach_events.event` | `outreach_messages.status` | Suppression | Alert |
|---|---|---|---|---|
| `BOUNCE` / `HARD` | `BOUNCED` | `BOUNCED` | `EMAIL` / `BOUNCE_HARD` | — |
| `BOUNCE` / `SOFT` | `BOUNCED` | unchanged | after 3, §7.9.3 | — |
| `BOUNCE` / `BLOCKED` | `BOUNCED` | `FAILED` (`failure_code='RECEIVER_POLICY'`) | none | HIGH |
| `BOUNCE` / `UNKNOWN`, origin submission | `RATE_LIMITED` | unchanged | none | HIGH |
| `COMPLAINT` (ARF, if one ever arrives) | `COMPLAINED` | unchanged | `BUSINESS` + `EMAIL` / `COMPLAINT` | HIGH |
| `UNSUBSCRIBE` | `UNSUBSCRIBED` | unchanged | `EMAIL` / `UNSUBSCRIBE_LINK` or `REPLY_OPT_OUT` | — |
| `AUTO_REPLY` | none | unchanged | none | — |
| `LOOP` | none | unchanged | none | NORMAL |
| `REPLY` classified `COMPLAINT` by `09` | `COMPLAINED` | unchanged | `BUSINESS` + `EMAIL` / `COMPLAINT` | HIGH |
| `REPLY` classified `OPT_OUT` by `09` | `UNSUBSCRIBED` | unchanged | `EMAIL` / `REPLY_OPT_OUT` | — |

The last two rows are `09-response-classification.md` §9.9.3's fan-out, listed here so that the full
set of things that can suppress an email address is visible in one table.

**There is no `DELIVERED` event on this stack, ever.** SMTP submission acceptance is not delivery, and
inventing a `DELIVERED` because nothing bounced would be a fabricated fact — `_CONTEXT.md` invariant
5. Messages stay `SENT`. `03-html-report.md`'s delivery column renders `—` for delivered-at, and
`EmailTransport.supports_delivery_receipts = False` is what tells it to. `outreach_messages.status`
therefore has one unreachable value on the email path, which is honest and worth a comment in `05`
§5.3.5 rather than a schema change.

### 7.9.6 Parsing the DSN

This section replaces the earlier revision's webhook endpoint entirely. A bounce is a message in the
mailbox, ingested by §7.8.6 like everything else, and classified `BOUNCE` by §7.8.7 rule 1.

**What Gmail sends.** SAMPLE, trimmed:

```
From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>
To: sagar.radar.mail@gmail.com
Subject: Delivery Status Notification (Failure)
Content-Type: multipart/report; report-type=delivery-status; boundary="000000000000abcd"
Message-ID: <68b0f0a1.a70a0220.1f2c3.0000@mx.google.com>

--000000000000abcd
Content-Type: text/plain; charset="UTF-8"

** Address not found **
Your message wasn't delivered to info@abc-hospital-sample.in because the address
couldn't be found, or is unable to receive mail.

--000000000000abcd
Content-Type: message/delivery-status

Reporting-MTA: dns; googlemail.com
Received-From-MTA: dns; sagar.radar.mail@gmail.com
Arrival-Date: Thu, 27 Aug 2026 11:12:07 +0530

Final-Recipient: rfc822; info@abc-hospital-sample.in
Action: failed
Status: 5.1.1
Remote-MTA: dns; mail.abc-hospital-sample.in
Diagnostic-Code: smtp; 550-5.1.1 The email account that you tried to reach does not
 exist.

--000000000000abcd
Content-Type: message/rfc822-headers

Date: Thu, 27 Aug 2026 11:12:06 +0530
From: Sagar <sagar.radar.mail@gmail.com>
To: info@abc-hospital-sample.in
Reply-To: Sagar <sagar.radar.mail+msg_01jb3k7qw5zxy8n4mdp2vr6t9c@gmail.com>
Message-ID: <msg_01JB3K7QW5ZXY8N4MDP2VR6T9C@gmail.com>
Subject: A possible digital operations solution for ABC Hospital

--000000000000abcd--
```

Three parts, and each is load-bearing:

| Part | Carries | Used for |
|---|---|---|
| `text/plain` | The human-readable explanation | Shown to Sagar in the §32 history. Never parsed for meaning |
| `message/delivery-status` | `Final-Recipient`, `Action`, `Status`, `Diagnostic-Code`, `Reporting-MTA` | `classify_bounce()`, §7.9.1 |
| `message/rfc822-headers` (or a full `message/rfc822`) | **Our original headers**, including `Message-ID` and the plus-tagged `Reply-To` | **Attribution.** This is what replaces VERP |

```python
# radar/email/bounce.py

def parse_dsn(msg: EmailMessage) -> DsnReport | None:
    """Pull the machine-readable half out of an RFC 3464 delivery-status notification.

    Two things make this worth writing carefully rather than regexing the human part.
    First, the human part is prose written by whichever MTA produced it, in whichever
    language it felt like, and 'not delivered' in Portuguese is not a status code. Second,
    a multi-recipient DSN has one per-recipient block per recipient - we only ever send to
    one, so more than one block means this DSN is not about a message of ours and must not
    be attributed to one.
    """
    if msg.get_content_type() != "multipart/report":
        return None
    ds = next((p for p in msg.walk()
               if p.get_content_type() == "message/delivery-status"), None)
    if ds is None:
        return None

    blocks = ds.get_payload()                 # [per-message fields, per-recipient fields...]
    if len(blocks) != 2:                      # exactly one recipient block expected
        log.warning("DSN with %d recipient blocks; not attributing", len(blocks) - 1)
        return None
    per_msg, per_rcpt = blocks

    return DsnReport(
        reporting_mta   = _hdr(per_msg,  "Reporting-MTA"),
        final_recipient = _addr(_hdr(per_rcpt, "Final-Recipient")),   # 'rfc822; a@b' -> 'a@b'
        action          = (_hdr(per_rcpt, "Action") or "").lower(),   # failed|delayed|delivered
        status          = _hdr(per_rcpt, "Status"),                   # '5.1.1'
        diagnostic      = _hdr(per_rcpt, "Diagnostic-Code"),
        smtp_code       = _smtp_code_from(_hdr(per_rcpt, "Diagnostic-Code")),
        original        = _returned_headers(msg),                     # EmailMessage or None
    )


def attribute_dsn(conn, dsn: DsnReport) -> Row | None:
    """Find the outreach_messages row this DSN is about. Exact rules only.

    Order matters and it is the same order as 7.8.8's, for the same reason: a returned
    Message-ID may have been rewritten by Gmail on the way out, so the tag we planted in
    Reply-To is the more reliable of the two exact signals and is tried alongside it. There
    is deliberately NO fallback to 'the only message we sent to that address' - a DSN we
    cannot attribute is stored and surfaced, never guessed.
    """
    if dsn.original is not None:
        ids = message_ids_in(dsn.original.get("Message-ID", ""))
        if ids and (row := _by_message_ids(conn, ids)):
            return row                                             # B1
        tag = _msg_tag(dsn.original.get("Reply-To", ""))           # +msg_<ulid>
        if tag and (row := _by_message_id(conn, tag)):
            return row                                             # B2
    if dsn.final_recipient:
        rows = _sent_to_address(conn, normalise(dsn.final_recipient),
                                since_days=cfg.email.dsn_match_days)   # default 14
        if len(rows) == 1:
            return rows[0]                                         # B3
    return None                                                    # B4: unattributed
```

| Rule | Signal | Confidence | Notes |
|---|---|---|---|
| `B1` | Our `Message-ID` in the returned headers | HIGH | Fails silently if Gmail rewrote it (§7.8.1); that is why `B2` exists |
| `B2` | The `+msg_<ulid>` tag in the returned `Reply-To` | HIGH | A header we wrote, returned verbatim. The most reliable rule on this stack |
| `B3` | `Final-Recipient` matches exactly one message sent to that address in the last `dsn_match_days` (14) | MEDIUM | Bounded tightly because a DSN arrives within hours, not months. More than one candidate means no attribution |
| `B4` | Nothing | — | `state='UNMATCHED'`, `kind='BOUNCE'`, unmatched band, no suppression. An unattributable DSN is rare and is usually a bounce of a message we did not send |

**What a DSN never does**: create a `responses` row, trigger a handoff, reach an LLM, or count as a
reply. §7.8.7 rule 1 runs before rule 7 for exactly that reason, and `09-response-classification.md`
§9.3's stage 0 diverts one anyway if it ever got that far — two independent guards, because a
mailer-daemon classified as `INTERESTED` would page Sagar at 2 a.m. about a dead address.

**Timing.** An immediate rejection produces a DSN within seconds of submission; a deferred one after
the receiving server gives up, typically 24-72 hours later. Both arrive in the same mailbox and are
handled identically. The only visible difference is that the second kind attaches to a message whose
status has been `SENT` for two days, which is correct and is why §7.9.3 does not treat lateness as
information.

### 7.9.7 The account-notice path

One case has no equivalent in the earlier design and needs naming, because it is the failure that
ends the build rather than degrading it: **Google writing to the account itself.**

Security alerts, policy notices, "critical security alert", and unusual-activity warnings all arrive
as ordinary mail in the same mailbox `poll_inbox` reads, from a `google.com` or `accounts.google.com`
sender. They are not replies, not bounces and not unsubscribes, so §7.8.7 lands them in `UNKNOWN`.

```python
_GOOGLE_NOTICE = re.compile(r"@(accounts\.)?google\.com$", re.I)
```

| Condition | Action |
|---|---|
| `from_address_norm` matches a Google notice sender **and** the subject matches `email.account_notice_patterns` (default: `critical security alert`, `unusual`, `suspended`, `disabled`, `policy`) | `kind='UNKNOWN'`, `state='UNMATCHED'`, **`contact_policy.email_enabled = 0`** with a `SEND_DISABLED_CHANGED` audit row, and an immediate `HIGH` Telegram alert quoting the subject line |
| Any other Google notice | Stored, unmatched band, no action |

Pausing on a subject-line match is deliberately twitchy, and the asymmetry justifies it: a false
positive costs Sagar one click at `/settings` to resume; a false negative is a system that keeps
sending into an account Google has already flagged, which is the fastest way to turn a warning into a
closure. This is the one automatic pause in the document that fires on a *guess*, and it is allowed
to because the guess is cheap in one direction and expensive in the other.

---

## 7.10 Sending mechanics

### 7.10.1 How `send_email` drains the queue

The job contract is `14-background-jobs.md` §14.8.12's, unchanged. Repeated here because everything
in this document hangs off it:

| Property | Value |
|---|---|
| Type | `send_email` (io lane) |
| Payload | `{"message_id","approval_id","business_id","campaign_id","contact_id"}` — no body, no subject, no address |
| Dedupe key | `send_email:{message_id}` — permanent, never pruned |
| `max_attempts` | **1** |
| Lease expiry | `RECONCILE` |

**`05-outreach-workflow.md` §5.15.1 calls this job `send_message` with dedupe key `send:{message_id}`
and `max_attempts = 5`.** `14` is the job registry and its contract wins; the name is `send_email`,
the key is `send_email:{message_id}`, and the retry policy is one attempt at the transmit boundary
with `Defer` for everything before it. Amendment request to `05` in Open questions.

Order of operations, with the email-specific steps filled in:

```
 0. has poll_inbox completed successfully since this worker started?
                                                     -> no      => Defer(now + 15s), 7.7.7
 1. load message + approval; assert status='QUEUED' and the approval is live and unrevoked
 2. check_send_eligibility(stage=SEND)               -> block   => Fail(ELIGIBILITY_BLOCK), no transmit
 3. send window open? (14.9.3)                       -> no      => Defer(next open)
 4. pacing_delay() from the last SEND_ATTEMPT (7.6.5)-> > 0     => Defer(now + delay)
 5. reconcile_day_bucket(); take 1 token from
    email.hour, email.day, email.domain.{d}.day      -> empty   => Defer(eta) + RATE_LIMITED event
 6. body_hash == approval.approved_body_hash?        -> no      => Fail(permanent), page immediately
 7. build_mime(); transport_checks() T1-T9           -> block   => Fail('TRANSPORT_CHECK'), page
 8. T1  COMMIT the intent (SEND_ATTEMPT + attempt_count + provider + provider_send_started_at
        + provider_message_id = derive_message_id(...))
 9. ---- network: transport.send(), no transaction open, no lock held ----
10. T2  COMMIT the outcome (SENT | PROVIDER_ERROR | INDETERMINATE + audit_log + counters)
```

Steps 0, 3, 4 and 5 are `Defer`, not `Retry`: they do not consume the one attempt. Only step 8 does,
and by then every gate has passed.

**Step 0 is new in this revision** and is §7.7.7 rule 2: on a machine that is not on 24/7, the
mailbox may hold an opt-out from whenever it was last closed, and reading the mailbox has to precede
the first transmission of the session. It is a `Defer` of fifteen seconds, evaluated against a
process-lifetime flag set by a successful `poll_inbox`, so in normal running it is free — the poller
has run within the last two minutes and the check passes on the first evaluation.

**Step 8 now writes `provider_message_id`** before the network call rather than after it, which is
the change §7.10.2 exists to explain.

### 7.10.2 At-most-once, and what the reconciliation key is now

There is no exactly-once. There is **at-most-once with a human tiebreak**, and that is the correct
choice here. The earlier revision could lean on a provider-assigned message id to settle an ambiguous
outcome. SMTP submission assigns nothing we can query, so the key has to be one we generate:

| Question | Answer |
|---|---|
| **What is the reconciliation key?** | `derive_message_id(outreach_messages.id)` — `<msg_01JB...@gmail.com>` — written to `outreach_messages.provider_message_id` in step 8's transaction, **before** the socket is opened. It is deterministic, so it can be recomputed from the row alone even if the write were lost |
| Why not the SMTP `250` response? | It carries a queue token that is Gmail's internal identifier, is not documented as stable, and is not queryable by any interface available to us. Recording it is harmless; depending on it is not |
| What if Gmail rewrote the `Message-ID`? | Then the Sent-folder copy carries a different one, and §7.10.4's search matches on the plus-tagged `Reply-To` instead — a header Gmail does not rewrite. The recorded delivered id is then stored in the reconciliation event. §7.8.1 |
| Can a message be sent twice by this system? | Only if Gmail accepted it, the process died before the outcome commit, and reconciliation wrongly concluded it had not been sent. §7.10.4 makes that require a human saying so |
| Can a message silently not be sent? | Yes, and this is the chosen failure direction. It is visible: `QUEUED` with an `INDETERMINATE` event, on screen, in the daily report |
| What guarantees at-most-once | `ux_om_idempotency` on `outreach_messages(idempotency_key)`; the permanent `send_email:{message_id}` dedupe key; `max_attempts = 1`; `AND status = 'QUEUED'` on both the SELECT and the UPDATE in `05` §5.10.2; `provider_send_started_at` and `provider_message_id` both written before the network call |
| Why not at-least-once | A duplicate cold email to a business that has never heard of us reads as a malfunctioning bulk sender, which is the exact impression this whole design exists to avoid — and on a free Gmail account, "malfunctioning bulk sender" is also the description of an account about to be closed |

**The crash window, walked with SMTP semantics.** Between step 8's commit and step 10's commit there
is a network call. Three ways it can end badly:

| Failure | What the database says | What actually happened | How it is settled |
|---|---|---|---|
| Process killed after step 8, before the socket opened | `SEND_ATTEMPT`, no terminal event | Nothing was sent | §7.10.4 finds no Sent copy; `NOT_SENT`; back to `QUEUED` |
| Process killed after `DATA` completed and `250` was received, before step 10 | `SEND_ATTEMPT`, no terminal event | It **was** sent | §7.10.4 finds the Sent copy; `SENT` recorded, no resend |
| Connection dropped during `DATA` | `SEND_ATTEMPT`, `INDETERMINATE` event | **Unknowable from our side** | §7.10.4: search the Sent folder; if that is inconclusive, ask Sagar |

Row two is the one that makes the Sent folder worth depending on, and row three is the one that makes
"ask a human" the right answer rather than a cop-out.

### 7.10.3 Retry, mapped

`05-outreach-workflow.md` §5.15.3 names its result type `DispatchOutcome` with six values;
`08-whatsapp-integration.md` §8.4.1 names it `DispatchResult` with four plus `retryable`. `08` owns
`radar/channels/base.py`, so `DispatchResult` is the type. The mapping from this document's
`TransportResult` through it:

| `TransportResult` | `failure_code` | `DispatchResult.outcome` | `retryable` | `outreach_messages` | Job |
|---|---|---|---|---|---|
| `ACCEPTED` | — | `ACCEPTED` | false | `SENT`, `sent_at`, `provider_message_id` already set | `SUCCEEDED` |
| `FAILED` | `INVALID_RECIPIENT` | `FAILED` | false | `FAILED` | `FAILED` |
| `FAILED` | `AUTH_FAILED` | `FAILED` | false | stays `QUEUED` | `FAILED` + banner + Telegram |
| `FAILED` | `SMTP_ERROR`, permanent code | `FAILED` | false | `FAILED` | `FAILED` |
| `FAILED` | `SMTP_ERROR`, `421`/`4.7.0` from Gmail (daily limit) | `FAILED` | **true** | stays `QUEUED` | `Defer` to the next send window, `RATE_LIMITED` event, `email.day` bucket drained to zero, `HIGH` alert |
| `FAILED` | `SMTP_ERROR`, other 4xx | `FAILED` | **true** | stays `QUEUED`, `next_retry_at` set | `FAILED`; a new `send_email` may be enqueued by the operator only |
| `FAILED` | `NETWORK` | `FAILED` | true | stays `QUEUED` | as above |
| `INDETERMINATE` | `CONNECTION_LOST` | `INDETERMINATE` | false | stays `QUEUED`, `INDETERMINATE` event | `DEAD`, §7.10.4 |

Two rows deserve their reasons in text.

`AUTH_FAILED` deliberately leaves the message `QUEUED` rather than failing it: the message is fine,
the credentials are not, and failing fifteen good messages because an App Password was revoked would
require fifteen new drafts and fifteen new approvals. It raises a banner across `/outreach` and a
Telegram alert instead, and the queue drains once `config/.env` is fixed and the service restarted.
On this stack the alert text names the three likely causes in order (§7.3.5's docstring), because
"535 authentication failed" against a Gmail App Password is one of three specific things and reading
the log should not require guessing which.

`421`/`4.7.0` from Gmail is separated from other 4xx because it is not a transient network condition,
it is §7.4.8's ceiling. Retrying in ninety seconds makes it worse. The correct response is to stop
for the day, drain the day bucket so nothing else tries, and tell Sagar — because if the system hit
Gmail's limit at a policy cap of 25, something is very wrong with the policy cap.

A `retryable` failure does **not** automatically re-enqueue, because `max_attempts = 1` and the
dedupe key is permanent. It surfaces as a row Sagar can re-queue from `/outreach` with one click,
which writes a new `send_email` job with `regen_no` appended to the dedupe key. That is deliberate
friction: an automatic retry loop against a mail server that is refusing us is how a rate limit
becomes a block.

### 7.10.4 Reconciliation, and the Sent folder

`14-background-jobs.md` §14.5.1 step 6 runs a reconciliation pass at worker startup over every `DEAD`
`send_email` job and every message with a `SEND_ATTEMPT` and no terminal event. `05` §5.17.2 prints
the selection query. The email-specific part is what "ask the provider" means when there is no
provider API:

| Transport | Can it answer "did this send?" | How |
|---|---|---|
| `null` | Yes, definitively | The `.eml` file exists or it does not |
| `gmail` | **Usually** | Search `[Gmail]/Sent Mail` over IMAP |

**The Sent-folder search.** Gmail files a copy of a message submitted through `smtp.gmail.com` into
`[Gmail]/Sent Mail`. That copy is the only evidence outside our own database that a transmission
happened, and it is available over the same IMAP connection `poll_inbox` already uses.

```python
# radar/email/reconcile.py

def find_sent_copy(imap, message_id: str, sent_at_hint: str) -> SentCopy | None:
    """Look for our own message in [Gmail]/Sent Mail. Three keys, tried in order.

    HEADER Message-ID is tried first and is exact when it works. It is tried SECOND-guessing
    nothing: if Gmail rewrote the id on submission (7.8.1) this search finds nothing, which
    is why the Reply-To tag - a header Gmail does not rewrite - is tried next. The date
    window exists because Gmail's IMAP search is fast on a bounded range and slow on a
    mailbox; a 48-hour window around the attempt is generous for a crash-recovery search.
    """
    since = (parse_iso(sent_at_hint) - timedelta(hours=24)).strftime("%d-%b-%Y")
    imap.select('"[Gmail]/Sent Mail"', readonly=True)

    for criteria in (
        ['SINCE', since, 'HEADER', 'Message-ID', derive_message_id(message_id)],
        ['SINCE', since, 'HEADER', 'Reply-To', msg_tag_address(message_id)],
        ['SINCE', since, 'HEADER', 'X-Google-Original-Message-ID',
         derive_message_id(message_id)],
    ):
        uids = imap.uid('SEARCH', None, *criteria)
        if uids:
            return _load(imap, uids[0])
    return None
```

| Outcome | Recorded |
|---|---|
| Found | `outreach_messages.status = 'SENT'`, `sent_at` from the copy's `Date`, `outreach_events(SEND_RECONCILED)` with `detail={"via":"sent_folder","delivered_message_id":"<...>"}`, and if the copy's `Message-ID` differs from ours, `provider_message_id` is updated to the delivered one so `M1` can match a reply against it (§7.8.8) |
| Not found, and the attempt is older than `email.sent_search_grace_minutes` (default 10) | Treated as evidence of non-delivery **only in combination with** the absence of an `INDETERMINATE` event. A clean "socket never opened" crash resolves to `NOT_SENT` automatically and the message returns to `QUEUED` |
| Not found, and there **is** an `INDETERMINATE` event | **Not settled automatically.** The message goes to the indeterminate band below |
| IMAP unreachable | Not settled. Try again on the next startup; the message stays `QUEUED` with its `INDETERMINATE` event |

The distinction in rows two and three is the important one. A missing Sent copy is weak evidence: the
copy may be delayed, the search may have missed it on a header Gmail rewrote, or the folder may have
been reorganised. Combining it with what we know about *how* the attempt ended is what makes an
automatic resolution safe in one case and unsafe in the other.

If nothing can settle it:

| Step | Behaviour |
|---|---|
| 1 | The message stays `QUEUED` with an `INDETERMINATE` event and `OUTREACH_SEND_INDETERMINATE` in the audit log |
| 2 | It appears on `/outreach` in an **indeterminate** band, amber, with the sentence "We are not sure whether this one went out. Open the account's Sent Mail and search for `<Message-ID>` or for `+msg_01jb...`, then tell us." |
| 3 | `POST /api/v1/outreach/messages/<id>/resolve-indeterminate` with `{"outcome": "SENT"|"NOT_SENT", "note": "..."}` — session-authenticated, writes an audit row naming the human. `14` §14.3.2 closes the generic job-revive route for `send_email` precisely so that this is the only path |
| 4 | `SENT` records the message as sent with `sent_by` = the resolving human. `NOT_SENT` returns it to `QUEUED` and permits one new `send_email` job |
| 5 | Telegram alert on creation, because an indeterminate message is the one state that needs a person and will otherwise sit |

Guessing is not on the list. "We do not know, here is exactly what to look at" is an honest state and
takes Sagar thirty seconds in a browser tab he has open anyway; a wrong guess in either direction
costs a duplicate cold email or a lost lead.

### 7.10.5 A fifteen-message batch, partially failed, on Sagar's screen

Fifteen approved messages are fifteen jobs, not one. `05` §5.17.1 defines the batch endpoint; this is
what the email rows look like rendered.

```
BATCH  bat_01JB...B7          confirmed 27 Aug 2026, 11:12 IST        SAMPLE
approved 15   sent 11   queued 2   held 1   blocked 1   failed 1   indeterminate 1

SENT (11)   via gmail  (sagar.radar.mail@gmail.com)
  11:12:06  ABC Hospital            DHULE     info@abc-hospital-sample.in
  11:12:54  Shree Traders           NASHIK    contact@shree-sample.in
  ... 9 more

QUEUED (2)  -- waiting on pacing and the hourly bucket
  PQR Motors              JALGAON   next attempt 11:19  (6 messages/hour limit)
  Nashik Diagnostics      NASHIK    next attempt 11:26

HELD UNTIL TOMORROW (1)
  Sunrise School          DHULE     daily send limit reached (cap 12, account ramp day 24)
                                    will send 28 Aug from 09:30 IST

BLOCKED (1)  -- never transmitted
  XYZ Traders             NASHIK    The address ops@example-sample.in asked to be removed on
                                    2026-08-27, so no email can be sent to it.
                                                                          [A_SUPPRESSED_EMAIL]

FAILED (1)  -- transmitted, rejected
  LMN Bakery              DHULE     The address was rejected as invalid (550 5.1.1).
                                    Fix the contact and prepare a new message.
                                                                          [INVALID_RECIPIENT]

WE ARE NOT SURE (1)
  Deshmukh Motors         JALGAON   The connection dropped after we sent the message and
                                    before Gmail answered. We looked in Sent Mail and could
                                    not find it, but that is not proof. Search Sent Mail for
                                    +msg_01jb3k7q, then tell us.
                                    [ It was sent ]  [ It was not sent ]
```

SAMPLE. Five rules the screen obeys:

1. **No batch-level retry button** (`05` §5.17.1). Re-sending one message is a fresh draft and a
   fresh approval, because if the address was wrong the fix is a different address and a different
   address is a different decision.
2. Counts come from one `GROUP BY status` over the batch, never from a Python counter (invariant 5).
3. Every non-`SENT` row carries a full sentence, not a code. The code is in a tooltip for grepping.
4. `HELD` is distinguished from `BLOCKED` in the strongest terms available, because they mean
   opposite things: one is "tomorrow", the other is "never". Gate H3 is the only gate whose block
   means later (`05` §5.9.10).
5. The indeterminate row is the only one with buttons; both write an audit record naming Sagar; and
   its text now says what we already looked for and why the result was not conclusive, because
   "search your Sent folder" is a much more useful instruction when the reader knows the system
   already tried.

### 7.10.6 §28's confirmation screen, the email half

`05-outreach-workflow.md` §5.13 owns the confirmation flow and its seven items. Four of them have
email-specific content this document supplies, and they are shown because they are the things a
recipient will see and Sagar will not otherwise:

| §28 item | Email-specific rendering |
|---|---|
| Contact | `info@abc-hospital-sample.in`, plus its provenance line ("found on the hospital's own contact page, 12 Aug 2026, confirmed by you on 20 Aug") and its two DPDP flags (§1.5.4) |
| Channel | `EMAIL via gmail (sagar.radar.mail@gmail.com)` — the **transport name and the actual From address**, so a live send is never mistaken for a dry run and vice versa. When the transport is `null`, the button reads **CONFIRM & WRITE .EML** and the panel says no message will leave the machine |
| Message | Subject and body exactly as transmitted, **including the signature and the STOP line**, plus a collapsed "headers" panel showing `From`, `Reply-To`, `List-Unsubscribe` and `Message-ID` |
| Opt-out status | Gate A's result, and today's cap position: "12 of 25 sent today (account ramp day 24 of 42)" |

The transport name on the confirm button is the last of the five mechanisms in §7.3.7. Four of them
protect against a machine being wrong. This one protects against a human being wrong.

### 7.10.7 §29, the email specifics

`05` §5.9.8's gates F1-F4 are the general duplicate protection. The email-specific behaviour is
entirely in normalisation, which `05` §5.9.2 owns and this document consumes without variation:

| Case | Mechanism | Outcome |
|---|---|---|
| Same address, different case (`Sales@ABC.IN` vs `sales@abc.in`) | `value_norm` lowercases the whole address | One address. F1 blocks the second send |
| Same address with a tag (`sales+web@abc.in` vs `sales@abc.in`) | `value_dedupe` strips `+tag` | F2 blocks: it is one inbox |
| Gmail dot variants | `value_dedupe` folds dots and `googlemail.com` | F2 blocks. Note that this now applies to **our own** address too, which is why §7.8.3's tag design uses `+tag` rather than dots |
| **Two "different" businesses sharing one inbox** — a common Indian SME pattern where a proprietor's `gmail.com` address is listed for three firms | F2 compares `to_address_dedupe` across businesses | Blocked. One human receives one message, not three, which is what §29 is actually protecting |
| Several addresses at one company domain (`info@`, `accounts@`, `md@`) | F3: `same_domain_max` (1) within `same_domain_days` (30), plus the `email.domain.{etld1}.day` bucket (2) | One department gets one message |
| A shared-hosting or aggregator domain where many unrelated businesses share an eTLD+1 | F3 would over-block | `email.domain_allowlist_shared` in config lists known shared hosts; F3 downgrades to a `WARN` for those and F2 still binds on the address |
| **A prospect whose published contact is itself a `gmail.com` address** | Nothing special. F2's dedupe folding applies to the recipient exactly as it does to any address | Very common in this market and worth stating: a `gmail.com` sender writing to a `gmail.com` recipient is the ordinary case here, not an edge case |
| Re-discovery of a bounced address | `01` §1.5.5's upsert never re-activates | Gate E2 blocks; no second send to a dead mailbox |

### 7.10.8 §32, the email rows in outreach history

`05` §5.18.1 owns the history query. The email channel contributes these delivery states, and the
history panel renders each with its evidence:

| Shown as | Source | Evidence link |
|---|---|---|
| Sent 11:12, via gmail | `outreach_messages.sent_at`, `.provider` | The `OUTREACH_SENT` audit row |
| Delivered | — | **Never shown.** `supports_delivery_receipts` is false, so the column renders `—`. Not "unknown", not "assumed delivered" |
| Bounced (hard, 5.1.1) | `outreach_events(BOUNCED)` | The `inbound_emails` row for the DSN, openable as raw text |
| Refused by receiver policy (5.7.1) | `outreach_events(BOUNCED, class=BLOCKED)` | The DSN, and the alert that was raised |
| Complained | `outreach_events(COMPLAINED)` | The reply that said so, or the manual entry. **Never** an automatic feedback-loop event; §7.9.4 |
| Unsubscribed 14:02 | `outreach_events(UNSUBSCRIBED)` | The `suppressions` row, the `UNSUBSCRIBE_RECEIVED` audit row, and the inbound mail that carried it |
| Auto-reply received | `inbound_emails(kind='AUTO_REPLY')` | The message. **Not** counted as a response anywhere |
| Replied 09:14, classified DEMO_REQUESTED | `responses` | The `responses` row, its attribution rule, and the raw `.eml` |
| Attribution: planted tag (exact) / address match (medium) | `responses.attribution`, `.attribution_confidence`, `inbound_emails.match_rule` | — |
| Reconciled: found in Sent Mail | `outreach_events(SEND_RECONCILED)` | The audit row naming the human, if a human resolved it |

The attribution row is shown, not hidden. When a reply reached this business's file by a `MEDIUM`
address match rather than an exact tag, Sagar should be able to see that before he acts on it —
which is the same principle as §12's OBSERVED/INFERRED split applied to inbound mail.

---
## 7.11 Exports and email (§41)

§41 asks for HTML, CSV, PDF and Excel exports preserving business, city, industry, score, research,
verification, contact and outreach status. `03-html-report.md` builds them, `11-audit-architecture.md`
owns `report_exports`, and `14-background-jobs.md` §§14.8.7-14.8.10 run the jobs. The only part that
is this document's is where an export meets a mailbox — and there the ruling is short.

| Destination | Permitted | Mechanism |
|---|---|---|
| A prospect, attached to an outreach message | **Never.** `OutboundEmail` has no attachments field (§7.5.5) | — |
| A prospect, as a link in an outreach message | **Never.** Rule `R7` allows two URLs on known hosts, and there is no host that could serve an export anyway: the app is on `127.0.0.1` and GitHub Pages is static and public. A public link to a file containing other businesses' data would be the single worst thing this system could do | — |
| Sagar himself | Yes | The self-notification identity (`10-human-handoff.md` §10.6.2): a **different Gmail account**, different credentials, no unsubscribe footer, no suppression check, no policy pass |
| Anyone else | Only by Sagar downloading it and sending it himself | `GET /api/v1/report_exports/<rex_id>/download` on `127.0.0.1`, which writes a `REPORT_DOWNLOADED` audit row |

Rules for the self-mail path:

| # | Rule |
|---|---|
| 1 | It uses `notify.email_self`'s credentials (`NOTIFY_GMAIL_*`), never `OUTREACH_GMAIL_*`. Two accounts, two App Passwords, so a deliverability or suspension problem in one cannot silence the other. `10` §10.6.2's reasoning is unchanged by the stack; only the credential names moved |
| 2 | Attach only when `report_exports.bytes <= email.self_attach_max_bytes` (default 5 MB — well under Gmail's 25 MB limit, deliberately) and `contains_pii = 0`. Above either threshold, send the path, not the file |
| 3 | A `contains_pii = 1` export — anything with contact columns — is **never attached**, only named by `rex_id` and local path, because an attachment is a copy that leaves the retention regime `11` §11.12 manages and lands in a second Gmail account's storage indefinitely. The `DATA_EXPORTED` audit row already records that a file with contact columns left the system; a mailbox copy makes that record incomplete |
| 4 | The mail names the `rex_id` and the `content_sha256`, so an export mailed in March can be identified against the archive in September |
| 5 | The daily report (`14` §14.8.18) goes to Telegram first; email-to-self is the fallback when Telegram fails, per `10` §10.6 |

Rule 3 is stricter on this stack than it was on the last one, and worth the extra sentence: the
self-notification mailbox is now a consumer Gmail account, quite possibly Sagar's personal one, on a
phone he carries. Mailing a spreadsheet of prospect contact details into it is a copy of the contact
database in a place with none of the controls `11` §11.16 specifies for the real one.

---

## 7.12 Security

### 7.12.1 Credentials

Every email secret lives in `config/.env`, which is never in git, never in `config.yaml`, and never
in a backup that leaves the machine unencrypted (`11` §11.16.5's backup recipient covers the
backups).

```
# config/.env   (additions from this document)
RADAR_EMAIL_LIVE=yes                     # lock 3; set only by the production launcher
UNSUBSCRIBE_SIGNING_SECRET=<32 random bytes, hex>

# the outreach account
OUTREACH_GMAIL_USER=sagar.radar.mail@gmail.com
OUTREACH_GMAIL_APP_PASSWORD=<16-character Gmail App Password, no spaces>
OUTREACH_SMTP_HOST=smtp.gmail.com
OUTREACH_SMTP_PORT=587
OUTREACH_IMAP_HOST=imap.gmail.com
OUTREACH_IMAP_PORT=993

# the alerting account - a DIFFERENT Gmail account (10-human-handoff.md 10.6.2)
NOTIFY_GMAIL_USER=<sagar's own address>
NOTIFY_GMAIL_APP_PASSWORD=<a second, separate App Password>
ALERT_EMAIL_TO=<sagar's own address>
```

Note that `NOTIFY_GMAIL_*` is a **different** account, not merely a different variable name. A code
path that reads `OUTREACH_GMAIL_*` to send Sagar an alert is a bug, and a test asserts that
`radar/notify.py` never imports `radar/email/factory.py`.

Two variables from the earlier revision are gone: `DKIM_PRIVATE_KEY` (Google holds the key) and the
whole AWS block. That is a real reduction — the most dangerous secret in the old design, a signing
key that could forge mail from the sending domain, does not exist here at all.

### 7.12.2 Least privilege — and the App Password is not that

**An App Password is a worse credential than a scoped ESP API key, and this needs saying rather than
assuming.** The earlier revision could scope an SES key to `ses:SendRawEmail` on one identity with a
`ses:FromAddress` condition: a leaked key could send mail as Sagar and do nothing else. There is no
equivalent here.

| Property | A scoped ESP API key | A Gmail App Password |
|---|---|---|
| Can send mail as the account | Yes | Yes |
| Can **read every message in the mailbox** | No | **Yes** — every reply, every prospect's words, every DSN, and anything else that account ever receives |
| Can delete mail | No | **Yes**, over IMAP |
| Can be scoped to send-only | Yes | **No.** Google shows an app-type label when you create one, but the credential authorises the full IMAP/SMTP surface of the account |
| Can be scoped to one From address | Yes (IAM condition) | No |
| Can be restricted by IP | Often | No |
| Revocable independently | Yes | Yes — this is the one property it does keep, and it is why an App Password is still far better than the account password |
| Visible in a management console after creation | Usually | No — shown once, then only its name and last-used date |

Consequences that follow from that table, all of which are actual design decisions rather than
advice:

| # | Rule |
|---|---|
| 1 | **One App Password, not two.** The earlier design used separate SMTP and IMAP credentials so that the reader could not send. Gmail cannot express that split — both would be full-mailbox credentials — so a second one would add a second copy of the same power for no isolation. One credential, one place to revoke |
| 2 | **2-Step Verification stays on, permanently.** It is what makes App Passwords available at all, and it is what stops the account password alone from being enough to take the mailbox |
| 3 | **The account contains nothing else** (§7.2.6). Since the credential cannot be scoped, the *account* is the scope. That is the whole reason for the dedicated-account rule, restated as a security control rather than a reputation one |
| 4 | **`config/.env` is the highest-value file on the laptop after `data/radar.db`.** It grants read access to a mailbox full of prospect correspondence. `_CONTEXT.md` §2's threat model — a portable machine that leaves the building daily — makes full-disk encryption a requirement rather than a recommendation, and `11` §11.16 owns it |
| 5 | **Revoke on any suspicion, immediately.** Revoking an App Password is instant, free, and costs one restart. There is no reason to hesitate: the recovery is `python main.py email preflight` after pasting a new one |
| 6 | Rotate on a schedule anyway: `SECRET_ROTATED` audit rows (`11` §11.6) record `secret_name` and an 8-hex fingerprint of before and after, never the value |

`UNSUBSCRIBE_SIGNING_SECRET` is the one secret that **must not be rotated casually**: every
unsubscribe token in every message ever sent is derived from it, and rotating it makes every
outstanding token fail the HMAC recomputation. If it must be rotated (compromise), the old secret
moves to `UNSUBSCRIBE_SIGNING_SECRET_PREVIOUS` and the verifier accepts either for 24 months — longer
than any message is likely to be acted on. A broken unsubscribe is not an acceptable cost of key
hygiene, and on this stack it is worse than it was: with the HTTPS endpoint a failed token still
rendered a page a human could act on, whereas a failed token here means an unsubscribe mail that
falls through to §7.7.6's fallback and lands in a band Sagar has to read.

### 7.12.3 What must never be logged

| Never | Instead | Enforced by |
|---|---|---|
| A recipient email address, raw, at any level | `to_address_hmac`, or the masked form `in***@abc-hospital-sample.in` | `trg_audit_log_no_raw_address` for `audit_log`; `_scrub_addresses()` in `radar/audit.py` for excerpts; a log filter that redacts anything matching an address pattern in `radar/config.py::setup_logging()` |
| The message body, or any part of it | `body_hash`; the full body lives in `outreach_messages.body_final` and in the send capture under `P7Y` | Log filter, plus code review: the transport logs `len(raw)` and never `raw` |
| An inbound message body | `body_excerpt` (scrubbed, §7.8.12) in the database, `body_sha256` in the audit row | §7.8.5 |
| The Gmail App Password, the unsubscribe secret | 8-hex fingerprints, if anything | Never interpolated into a log line; **`smtplib.set_debuglevel` is never enabled in production, because it prints the `AUTH` line verbatim** — and on this stack that line is the whole mailbox |
| The unsubscribe token | `sha256(token)` | §7.7.7's audit payload uses `token_sha256` |
| A full DSN diagnostic containing the recipient address | `dsn_diagnostic` in `inbound_emails` (inside the database, under retention) and `diagnostic_sha256` in the audit row | §7.9.2 |
| An LLM prompt containing any inbound body | Only `body_scrubbed` reaches a prompt; prompts are logged by hash | §7.8.12, and `09` §9.11 |

At `DEBUG` the transport may log the `Message-ID`, the recipient **domain**, the byte count, the
provider and the elapsed milliseconds. That is enough to debug every failure this document describes,
and it identifies nobody.

### 7.12.4 Transport security

| Rule | Reason |
|---|---|
| `ssl.create_default_context()` always; certificate and hostname verification never disabled, not even by a config key | The one setting that turns authenticated submission into a credential handed to whoever is on the path — and on a laptop that connects to cafe and client wifi, "whoever is on the path" is not hypothetical |
| STARTTLS on 587 (or implicit TLS on 465). **Never** plain 25 | Port 25 outbound from an application is submission-without-authentication, is blocked by most consumer ISPs anyway, and is not offered by Gmail |
| A `starttls()` that fails is a hard failure, never a fallback to cleartext | A silent downgrade is how the App Password leaves the machine in the clear |
| IMAP on 993, implicit TLS, same context | |
| `timeout` set on every socket | An SMTP connection with no timeout holds a lease and a lane thread indefinitely — and a laptop that goes to sleep mid-connection is a routine event here, not an exotic one |
| The IMAP connection is re-established per `poll_inbox` run rather than held | A held connection across a sleep/wake cycle is a connection in an undefined state. Reconnecting costs a second every two minutes and removes an entire class of "it stopped working after I closed the lid" |
| No inbound network surface at all | waitress binds `127.0.0.1`. There is no webhook endpoint, no unsubscribe endpoint, and nothing listening that a stranger can reach. That is the one security property this stack has that the paid one did not |

---

## 7.13 The compliance checklist for every sent message

One function, run at step 7 of §7.10.1, whose failure is a `PERMANENT_FAILURE`. Every row has a
statutory or contractual reason and a mechanical check.

| # | Requirement | Source | Check | Where it is enforced |
|---|---|---|---|---|
| C1 | The message identifies the sender by real name | DPDP notice; ordinary commercial honesty; rule `R2` | Body contains `identity.sender_name` byte-for-byte | `06` `R2`, re-checked by `T2`'s hash |
| C2 | It identifies the business by its registered name | Same. **Load-bearing here**: with a `gmail.com` From address, the signature is the only place the company is named | Body contains `identity.company_name` | `06` `R2` |
| C3 | It gives a working reply address on the sending account | DPDP: a data principal must be able to reach the fiduciary | `identity.from_address` in the body; `Reply-To` header set to the tagged form of the same account | `06` `R2`; `T3`; `assert_transport_declared()` |
| C4 | It carries a working unsubscribe mechanism | `_CONTEXT.md` §4 | `List-Unsubscribe` present, exactly one `mailto:` URI, token matches the draft, local part ≤ 64 chars. **One-click / RFC 8058 is not offered and `List-Unsubscribe-Post` must be absent** | `T5`, `T8`; gate H5 |
| C5 | It carries a visible unsubscribe instruction in the body | Headers are invisible in most clients, and more so with a `mailto:`-only header | The STOP line and the `+unsub-` address present and matching | `06` `R1` as amended (§7.7.4) |
| C6 | The unsubscribe writes an opt-out automatically, without a human at our end | `_CONTEXT.md` §4 | §7.7.9 test matrix cases 1, 3, 5, 7 | `radar/email/unsubscribe.py`, inside the ingest transaction |
| C7 | The recipient was not already suppressed on any contact point | §30; invariant 3 | Gate A, re-evaluated **inside the send transaction**, plus §7.10.1 step 0's requirement that the mailbox has been read | `05` §5.9.3 |
| C8 | There is a record of where this contact came from | DPDP purpose limitation and accountability; §14 | `business_contacts.source_id`, `.source_url`, `.source_note`, `.discovered_at` are non-null for any contact that reaches `CONTACT_READY` | Gate E; the verification screen |
| C9 | The contact is classified for DPDP | `_CONTEXT.md` §4; `01` §1.5.4 | `is_public_business_contact` and `is_named_individual` set; `retention_class` follows | `radar/contacts.py::classify_contact()` |
| C10 | A named individual's data carries the shorter retention and is erasable | DPDP erasure | `retention_class = 'P180D'` where `is_public_business_contact = 0 AND is_named_individual = 1`; `11` §11.12's erasure path reaches it | `11` §11.12 |
| C11 | A human approved this exact message to this exact address | Invariant 1; §28; §45 | `ApprovalId.load()`; `approved_body_hash == body_hash`; `approved_to_address == to_address_norm` | `05` §5.15.2, step 6 of §7.10.1 |
| C12 | The message asserts nothing not traceable to a stored fact | Invariant 4; §12; §23 | `outreach_drafts.policy_result = 'PASS'`, `policy_checked_body_hash` equals the approved hash | `06` §6.10 |
| C13 | No third party's personal data appears in the body | DPDP; rules `P1`-`P4` | `06`'s `P` family | `06` §6.9.6 |
| C14 | No covert tracking | §7.6.1 | `T4`: no `<img>`, no remote content, no redirect host. On this stack also structurally impossible | `T4` |
| C15 | **No contact value reached an LLM** | `_CONTEXT.md` §2 | The prompt-assembly scrubber, outbound (`06`) and inbound (§7.8.12); the CI assertion in §7.16 case 30 | `radar/email/scrub.py`, `06` §6.8 |
| C16 | The message is retained with its evidence for as long as a complaint might arrive | `11` §11.12: `OUTREACH_SENT` is `P7Y` | The §48 audit row and the send capture | `11` §11.7 |
| C17 | Sending stays within the declared volume | AUP argument in §7.2.5 | Gate H3, `email.day`, `email.hour` | §7.4.8 |

C15 is new in this revision and C4 changed shape. C1-C3 and C5 do more work than they used to,
because a `gmail.com` From address supplies none of the identity a company domain supplied for free.

```python
# radar/email/compliance.py

def assert_compliant(conn, mime: EmailMessage, msg: OutboundEmail,
                     message_row, approval_row, draft_row, cfg) -> None:
    """C1-C17, immediately before transmission. Raises PermanentSendFailure.

    Most of these were checked earlier, by the policy engine or by a gate, on a draft or on
    a screen. This runs on the bytes, after everything else, because every earlier check ran
    on something that is not quite the thing being transmitted. The cost is a few
    milliseconds; the failure it prevents is a message that satisfied every check except the
    one that describes what actually left the machine.
    """
```

The DPDP Act 2023 obligations, mapped explicitly since §7.13 is where they land:

| Obligation | How this system meets it |
|---|---|
| **Purpose limitation** | Contacts are captured for one declared purpose — evaluating and, after human verification, proposing business software. `business_contacts.source_note` records the purpose context. Addresses learned from replies are not captured (§7.8.11), and no contact value is ever sent to a third-party model (§7.8.12) |
| **Notice** | Every message names the sender, the company, why we are writing and how we found the business (`06`'s `process` slot: "while researching businesses in Dhule we reviewed its publicly available business information"), and how to stop |
| **Accuracy** | Bounces deactivate; a complaint we are told about suppresses; a human verifies before any contact |
| **Storage limitation** | `retention_class` per contact; `11` §11.12's nightly `retention_purge`; `retention.contact_idle_months` default 24; raw inbound `.eml.gz` at `P3Y` |
| **Erasure** | `11` §11.12's path reaches `business_contacts`, `responses` and `inbound_emails` (both `body_text` and `body_scrubbed`). `suppressions` survives pseudonymised, because erasing an opt-out would permit re-contact — the one case where the Act's erasure right and its purpose are best served by keeping a hash |
| **Accountability** | `audit_log`, hash-chained, with `OUTREACH_SENT` and `UNSUBSCRIBE_RECEIVED` at `P7Y` |
| **Grievance** | A reply of any kind reaches a human within one working day of the laptop being opened, via the handoff path. Note honestly that `abuse@` and `postmaster@` for `gmail.com` are Google's, not ours (§7.4.2) — a complainant who escalates to the domain operator reaches Google, and Google's response to a complaint about one of its own accounts is the account action in §7.9.7 |
| **Cross-border transfer** | The mailbox is Google's and the model is Google's, so prospect correspondence and scrubbed reply text are processed outside India. §7.8.12 is what bounds what crosses: business names, cities, categories and scrubbed text, never a contact value |

---

## 7.14 Configuration

```yaml
# config.yaml (excerpt). Shipped as config.example.yaml with these exact values.
email:
  transport:            null        # null | gmail            <- lock 1
  live_send_enabled:    false       #                         <- lock 2
  # lock 3 is RADAR_EMAIL_LIVE in the environment; lock 4 is config/.env

  html_alternative:     false       # 7.5.1
  open_tracking:        false       # 7.6.1 - there is no code path that honours true,
  click_tracking:       false       #         and on this stack no way to build one
  max_bytes:            102400      # T7
  outbox_dir:           data/outbox # the null transport's .eml tree

  soft_bounce_window_days: 30       # 7.9.3
  soft_bounce_give_up:     3
  dsn_match_days:          14       # 7.9.6 rule B3
  loop_threshold:          3        # 7.8.7 rule 5
  poll_max_per_run:        200      # 7.8.4 - bounds the first poll after days offline
  sent_search_grace_minutes: 10     # 7.10.4
  account_notice_patterns:          # 7.9.7 - subject fragments that pause sending
    - "critical security alert"
    - "unusual"
    - "suspended"
    - "disabled"
    - "policy"

  self_attach_max_bytes:   5242880  # 7.11
  domain_allowlist_shared: []       # 7.10.7; eTLD+1s where F3 downgrades to WARN

response:
  ingest:               imap        # imap only. 'webhook' and 'both' are deleted: nothing
                                    # on the internet can reach 127.0.0.1 (7.8.4)
  match_days:           60          # bounds M5-M7 only; M1-M4 are unbounded
  mailbox:              outreach
  imap_folder:          INBOX
  sent_folder:          "[Gmail]/Sent Mail"
  state_file:           config/state/imap_uid.json

identity:                           # owned by 06-message-engine.md; constrained here
  from_address:         sagar.radar.mail@gmail.com   # the dedicated account (7.2.4)
  sender_name:          Sagar
  company_name:         SAMPLE Software Works
  site_url:             https://sample-software-works.github.io   # 7.4.4
  # identity.sending_domain is retired. It was a registrable domain we controlled; it is now
  # always 'gmail.com', which is not a fact any check should assert. Where a check needs the
  # account, it uses identity.from_address. See 7.6.2 and Open questions.
```

Deleted from the earlier revision's block, each for a reason already given: `check_sent_folder` (the
Sent-folder search is not optional any more — it is the only reconciliation available, §7.10.4),
`webhook_max_skew_s` and `webhook_reject_alert` (no webhook), `sending_domain` (no domain).

---

## 7.15 Module map

| Module | Responsibility | Docstring, one line |
|---|---|---|
| `radar/channels/email.py` | Implements `08`'s `Channel` for `EMAIL`: availability, render handoff to `06`, `validate`, `dispatch` | "Without this module every send is a hand-rolled SMTP call, and the one that forgets the unsubscribe header is the one that gets the account closed." |
| `radar/email/types.py` | `OutboundEmail`, `TransportResult` | §7.3.2 |
| `radar/email/transport.py` | The `EmailTransport` Protocol | §7.3.3 |
| `radar/email/null_transport.py` | `.eml` to disk; the default | §7.3.4 |
| `radar/email/smtp_transport.py` | Authenticated submission to Gmail | §7.3.5 |
| `radar/email/factory.py` | The four locks and the startup log line | §7.3.7 |
| `radar/email/mime.py` | `build_mime()`: §24's structure as bytes, headers, encoding, wrapping | "The one place that decides what a message looks like on the wire, so that 'we send plain text with a working unsubscribe' is a property of one function rather than a habit." |
| `radar/email/threading.py` | `derive_message_id()`, `thread_headers()`, `message_ids_in()`, `msg_tag_address()` | §7.8.1 |
| `radar/email/unsubscribe.py` | Token derivation, the `+unsub-` address, `find_unsubscribe()`, `apply_unsubscribe()` | "The only way a business can make this system stop, and it works by reading a mailbox because there is no server anybody outside this laptop can reach." |
| `radar/email/checks.py` | `T1`-`T9` | §7.6.4 |
| `radar/email/compliance.py` | `C1`-`C17` | §7.13 |
| `radar/email/pacing.py` | Gap and jitter, computed under the writer lock | §7.6.5 |
| `radar/email/caps.py` | `reconcile_day_bucket()` | §7.4.8 |
| `radar/email/inbound.py` | IMAP client, `ingest_one()`, kind classification, `M1`-`M8` | "Without this the replies that justify the entire pipeline sit unread in a mailbox, and the one that says 'yes, show us' is indistinguishable from the ninety that say 'out of office'." |
| `radar/email/scrub.py` | `scrub_for_model()` | "The gate between an inbound message and anything that can reach a model, because the free tier we use may train on what we send it." |
| `radar/email/bounce.py` | `parse_dsn()`, `attribute_dsn()`, `classify_bounce()`, the side effects | §7.9 |
| `radar/email/reconcile.py` | `find_sent_copy()` and the indeterminate resolution | §7.10.4 |
| `radar/email/events_map.py` | `(kind, class) -> EventMapping` | §7.9.5 |
| `radar/email/health.py` | `v_email_health` readers and the §7.9.4 delivery alarms | "The only place that answers 'is the account still working', on a stack that will never be told when it stops." |

Deleted from the earlier revision: `radar/email/ses_transport.py`, `radar/web/webhooks.py`,
`radar/web/unsubscribe.py`.

CLI:

```
python main.py email preflight                 # SMTP AUTH + IMAP login + Sent folder + address
                                               # length check. Sends nothing
python main.py email test-send --to <addr>     # one message through the live transport; prints
                                               # the Message-ID we generated and, after a poll,
                                               # the one that actually arrived (7.4.7 step 9)
python main.py email poll --once               # run poll_inbox synchronously, verbose
python main.py email reingest <path.eml>       # ingest a saved .eml through the fixture path
python main.py email find-sent <msg_id>        # search [Gmail]/Sent Mail; prints what 7.10.4 sees
python main.py email ramp-status               # ramp day index, today's cap, and what has been used
python main.py email health                    # v_email_health, plus the 7.9.4 proxy alarms
```

`email dns-check` and `email dmarc-report` are deleted: there is no DNS of ours to check and no
aggregate report that will ever arrive.

---

## 7.16 Test matrix

| # | Area | Test | Asserts |
|---|---|---|---|
| 1 | Default | `build_transport()` on a config with no `email` block at all | Returns `NullEmailTransport` |
| 2 | Locks | Each of the four locks, opened three-at-a-time in all four combinations | Null transport, and an `ERROR` naming the closed lock |
| 3 | Null | Send one message | `.eml` on disk, parses, `To`/`Subject`/body correct, `status='SENT'`, `provider='null'` |
| 4 | Hash | Body edited in the database after approval, then sent | `PermanentSendFailure` at step 6; no transmission |
| 5 | `T1` | `to_addrs` list of two constructed by hand; and a `Bcc` header injected | Blocked, both cases |
| 6 | `T5` | A draft whose `unsubscribe_token` does not match the built header | Blocked |
| 7 | `T5` | An `identity.from_address` whose local part makes the `+unsub-` address 65 characters | `ConfigError` at boot (§7.3.8); if forced past it, `T5` blocks |
| 8 | `T8` | A built message carrying `List-Unsubscribe-Post` | Blocked. (Replaces the earlier revision's one-click header test, which asserted the opposite) |
| 9 | `T6` | Two messages producing the same `Message-ID` | Blocked |
| 10 | MIME | A business name with Devanagari characters in the subject | RFC 2047 encoded; round-trips through `email.parser` unchanged |
| 11 | MIME | A body with a 200-character line | Wrapped at 78; `text/plain` still equals `body_final` after unwrapping |
| 12 | **Startup order** | Worker starts with an unread unsubscribe mail and 3 `QUEUED` messages | `poll_inbox` completes first; the suppression exists before any `send_email` transmits; the message for that business is `CANCELLED` by gate A, not transmitted (§7.7.7 rule 2) |
| 13 | Unsubscribe | The fifteen cases in §7.7.9 | As listed |
| 14 | Unsubscribe | The same unsubscribe mail ingested 50 times concurrently | One `suppressions` row, one audit row |
| 15 | Unsubscribe | A reply whose only "unsubscribe" is inside the quoted footer of our own message | Not an opt-out; classified `REPLY` |
| 16 | Threading | Follow-up at `sequence_no=3` | `In-Reply-To` names sequence 2; `References` has three ids, root first |
| 17 | Inbound | The same `.eml` ingested twice | One `inbound_emails` row, one `responses` row, one `classify_response` job |
| 18 | Inbound | `UIDVALIDITY` changes and the whole mailbox is re-scanned | Zero duplicate rows; one `ERROR` log naming both values |
| 19 | Inbound | 600 messages waiting after five days offline | Three `poll_inbox` runs of 200; every message ingested exactly once; no run exceeds its duration budget |
| 20 | Matching | Each of `M1`-`M8` with a purpose-built fixture | Correct `match_rule`, `attribution`, `attribution_confidence` |
| 21 | Matching | Reply from an address never contacted, correct `+msg_` tag, **no `In-Reply-To` at all** | `M2`, `HIGH`, attributed to the right business |
| 22 | Matching | Reply whose `In-Reply-To` names a Gmail-rewritten id recorded by §7.10.4 | `M1` fires on `provider_message_id` |
| 23 | Matching | Reply whose `In-Reply-To` names an id we never generated and with no tag | No exact match; falls to `M5`, or `UNMATCHED`. **Never a wrong match** |
| 24 | Matching | Forwarded reply quoting our headers | `M4`, `MEDIUM` |
| 25 | Matching | `M5` where two businesses share the address | No match; `UNMATCHED` |
| 26 | Matching | Exact-match reply 200 days later | `M1`/`M2` fire; `M5` would not |
| 27 | Matching | Out-of-office with `Auto-Submitted: auto-replied` | `AUTO_REPLY`, no `responses` row, no handoff, **no LLM call** |
| 28 | Matching | Reply from a suppressed business | `responses` row created, handoff created, nothing sent |
| 29 | **Scrubber** | A reply fixture containing an email address, an Indian mobile number and a URL, in the body and in the quoted section | `body_scrubbed` contains `<EMAIL>`, `<PHONE>`, `<URL>` and none of the literals; `body_excerpt` is taken from the scrubbed form |
| 30 | **Scrubber, the required one** | Build every prompt this system can assemble from a corpus of fixtures whose contact values are known sentinel strings | **Fail if any sentinel appears in any LLM payload.** `_CONTEXT.md` §2 requires this test to exist |
| 31 | Bounce | The eleven status codes in §7.9.1 | Correct class each time; `5.2.2` is `SOFT`; `5.7.1` is `BLOCKED` and suppresses nothing |
| 32 | Bounce | A real Gmail DSN fixture (§7.9.6) | `parse_dsn()` extracts `5.1.1` and the final recipient; `B1` or `B2` attributes it; contact deactivated; suppression written |
| 33 | Bounce | A DSN whose returned headers were stripped, `Final-Recipient` matching exactly one recent message | `B3`, `MEDIUM`; attributed |
| 34 | Bounce | A DSN whose returned headers were stripped and whose recipient matches two messages | `B4`, `UNMATCHED`, **no suppression** |
| 35 | Bounce | A DSN with two per-recipient blocks | Not attributed; logged; unmatched band |
| 36 | Bounce | Three soft bounces on one address in 30 days | Promoted to hard; contact deactivated; suppression written |
| 37 | Bounce | Three `5.7.x` `BLOCKED` bounces across three domains in 24 h | `contact_policy.email_enabled = 0`; `SEND_DISABLED_CHANGED` audit row; `HIGH` alert |
| 38 | Bounce | A Gmail-side `4.7.0` deferral naming `googlemail.com` as reporting MTA | `bounce_class='UNKNOWN'`, `origin=submission`, **no suppression on the recipient**, `HIGH` alert |
| 39 | Account notice | A fixture from `no-reply@accounts.google.com` with subject "Critical security alert" | Email paused; `HIGH` alert; unmatched band (§7.9.7) |
| 40 | Complaint | A reply classified `COMPLAINT` by `09` | `BUSINESS`- and `EMAIL`-scope suppressions, `HIGH` alert, `P7Y` audit row |
| 41 | Health | 40 sends in 30 days, zero replies, previous month non-zero | Warning raised, **sending not paused** (§7.9.4) |
| 42 | Caps | Ramp day 3 with `daily_send_cap=25` | `effective_daily_cap()` is 3; the fourth send defers to tomorrow |
| 43 | Caps | `reconcile_day_bucket()` after a `/settings` cap change | `email.day` capacity follows downward, never upward past 40 |
| 44 | Caps | The laptop is closed for 18 hours and reopened | `email.day` tokens refill by elapsed wall-clock time; no catch-up job runs; the cap is not silently reset to full |
| 45 | Pacing | Three `io` threads claiming three sends at once | Two defer; the gap between successive `provider_send_started_at` values is at least `0.7 * send_min_gap_seconds` |
| 46 | Indeterminate | Kill the process between step 8 and step 10, with a matching message present in a fake Sent folder | Reconciliation finds it, records `SENT`, no resend, `SEND_RECONCILED` event |
| 47 | Indeterminate | The same, with no Sent copy and an `INDETERMINATE` event | Stays `QUEUED`; indeterminate band; the resolve endpoint is the only way out |
| 48 | Logging | Run the whole send path at `DEBUG` and grep the log for the recipient address, the body and the App Password | Zero hits; `set_debuglevel` is never enabled |
| 49 | Audit | Every send | `trg_om_sent_needs_audit` never fires; the `OUTREACH_SENT` payload has `address_masked`, not `address` |
| 50 | Isolation | Import graph | `radar/notify.py` does not import `radar/email/factory.py`; nothing outside `radar/email/` imports `smtplib` or `imaplib`; no module anywhere imports `boto3` |

Tests deleted from the earlier revision, listed so their absence is deliberate rather than
accidental: the four webhook tests (valid signature delivered five times, bad signature, stale signed
body, foreign `TopicArn`), the HTTPS unsubscribe `GET`-does-not-write and one-click tests, the
crawler-prefetch simulation, and the DKIM selector rotation test.

---

## Open questions

1. **Migrations 055-057 extend `01-data-model.md` §1.13.2's 54-file sequence.** `01` is the arbiter
   for migration numbering and its list ends at `054_seed_reference.sql`. This document appends
   `055_inbound_emails.sql`, `056_email_account_ramp.sql` and `057_v_email_health.sql`. Amendment
   request to `01` §1.13.2 to adopt them, and to §1.1.1's ownership map to record `inbound_emails` as
   owned by `07`. (The earlier revision asked for a fourth migration and a second table,
   `email_webhook_events`; **that request is withdrawn.**)

2. **One new id prefix.** `inb_` (`inbound_emails`) must be added to `01` §1.1.3's table and to
   `_PREFIXES` in `radar/ids.py`. The earlier request for `eev_` is withdrawn.

3. **`responses.business_id` is `NOT NULL` (`01` §1.9.1), but `14` §14.8.13 rule 5 requires an
   unmatched reply to become a `responses` row with `business_id = NULL`.** Resolved here by adding
   `inbound_emails` and creating the `responses` row only on a successful attribution (§7.8.5,
   §7.8.10). `14` §14.8.13's rule 5 should be restated as "a row in `inbound_emails` with
   `state='UNMATCHED'`, surfaced in an unmatched-replies band. Never discarded." Confirmation
   requested from the owners of `01` and `14`.

4. **`responses.attribution`'s CHECK has five values and none of them describes a planted tag.**
   §7.8.8 maps `M2` onto `THREAD_HEADER` and `M3` onto `PROVIDER_ID`. Both are defensible — the tag
   is a header we generated, and the unsubscribe token is the closest thing to a provider id that
   exists now — but both lose a real distinction, and `PROVIDER_ID` is otherwise dead on this stack
   since there are no provider callbacks. Amendment request to `01` §1.9.1: add `RETURN_PATH_TAG` and
   `DOMAIN_MATCH` to the CHECK. `inbound_emails.match_rule` keeps the finer answer meanwhile.

5. **`14` §14.8.14 registers `process_webhook_event`, and there is nothing for it to process.**
   Nothing on the internet can reach `127.0.0.1`, so `POST /api/v1/webhooks/<provider>` has no
   caller. For `EMAIL` the job and the endpoint are dead. `08-whatsapp-integration.md`'s WhatsApp
   Cloud API webhook is dead for exactly the same reason, so the decision is not this document's to
   make alone — but `14` §14.8.14 should either be deleted or explicitly marked "reserved for a
   future deployment with a public endpoint; unreachable in v1", and `05` §5.3.1's step-10 row
   ("delivery webhook") should be re-pointed at §7.9.6's DSN path.

6. **The `send_email` versus `send_message` collision.** `14` §14.8.12 registers `send_email`,
   dedupe key `send_email:{message_id}`, `max_attempts = 1`. `05` §5.15.1 prints `send_message`,
   dedupe key `send:{message_id}`, `max_attempts = 5`, and §5.15.4 gives a five-step backoff table.
   This document follows `14` throughout. `05` §5.15.1 and §5.15.4 need the rename and the retry
   policy replaced by §7.10.3's mapping.

7. **The unsubscribe mechanism changed shape entirely and three documents describe the old one.**
   `05` §5.9.10's `unsubscribe_url()` returns `https://{PUBLIC_HOST}/u/{message_id}/{token}`; `06`
   rule `R1` requires `https://{sending_domain}/u/[0-9a-f]{32}` in the body; `05` §5.9.10's prose
   describes `POST /u/<message_id>/<token>`. All three are impossible. The replacements are §7.7.2's
   `unsub_address()` and §7.7.4's body line, and the required edits are: `05` §5.9.10 returns the
   `mailto:` and drops the route; `06` `R1` for `EMAIL` matches the STOP instruction plus the
   `+unsub-<token>@` address. Flagged rather than edited, since `05` and `06` own those sections.

8. **Gate A over-blocks on `BOUNCE_HARD`.** `05` §5.9.3 joins every suppression scope without
   filtering by channel, which is correct for a refusal and wrong for a dead mailbox: one bounced
   address permanently blocks WhatsApp and phone for that business. Amendment request to `05`
   §5.9.3: make `BOUNCE_HARD` bind only on `EMAIL`, leaving the refusal reasons channel-blind. Not
   changed unilaterally here because `05` owns the gate, and the current behaviour errs safely.

9. **`identity.sending_domain` is retired and `identity.reply_to` is renamed.** With no domain,
   `sending_domain` is always `gmail.com`, which is not a fact any check should assert — §7.6.2 shows
   the concrete harm (an allowlist containing `gmail.com` would permit links to arbitrary Gmail
   URLs). This document uses `identity.from_address` throughout. `06` §6.14's config sample and rule
   `R2`'s comparison need the rename, and `05` §5.9.10's gate H5 should test
   `contact_policy.email_sending_domain IS NULL` **or** the configured from-address, since the
   column's name is now misleading. Whether to rename the column (`email_from_address`) or leave it
   and document the meaning is `05`'s call; renaming costs a migration and the value is one row.

10. **`DispatchOutcome` (`05` §5.15.3) versus `DispatchResult` (`08` §8.4.1).** Same concept, two
    names, six outcome values against four. `08` owns `radar/channels/base.py`, so `DispatchResult`
    is used here and §7.10.3 gives the mapping. `05` §5.15.3 should adopt it.

11. **`postmark` appears as the SAMPLE provider in `05` §5.3.5, `11` §11.7.2, `08` §8.4.1 and `14`
    §14.8.21.** §7.2.3 disqualifies Postmark for this use case and it is not a provider this build
    can use at any price. The literals are illustrative and in an unconstrained `TEXT` column so
    nothing breaks, but they should be re-lettered to `gmail` or `null` so that nobody implements
    against the example. The values this document actually emits are `null` and `gmail`.

12. **`14` §14.13 is referenced eleven times inside `14-background-jobs.md` (the exactly-once send
    argument, §14.13.2's "deterministic `Message-ID`", §14.13.4's reconciliation pass, §14.13.5's
    indeterminate-resolution screen) and does not exist in the file.** §7.8.1 defines the
    `Message-ID`, §7.10.2 defines the reconciliation key and §7.10.4 defines the reconciliation
    behaviour and the resolve endpoint, so the pack is not missing the content — but `14`'s
    cross-references should either be written or re-pointed here.

13. **`11` §11.6's `RESPONSE_UNMATCHED` action has entity type `responses`**, but under §7.8.10 an
    unmatched inbound never creates a `responses` row. The action's entity should become
    `inbound_emails`. Same for the `capture_path` in `RESPONSE_RECEIVED`, which this document writes
    as `inbound_emails.raw_path`. Additionally, `11` §11.6's `UNSUBSCRIBE_RECEIVED` payload lists
    `remote_ip` and `user_agent`, which existed only because the mechanism was an HTTP request; the
    payload is now `token_sha256`, `message_id`, `inbound_email_id`, `via` and `suppression_id`
    (§7.7.7). And `PROVIDER_CALLBACK` / `PROVIDER_CALLBACK_REJECTED` have no writer on this stack —
    they should be marked as reserved rather than deleted, since `08` may still want them if a
    public endpoint ever exists.

14. **`06` rule `R2` requires the body to contain `identity.from_address` byte-for-byte, while the
    `Reply-To` header carries the plus-tagged form.** These are the same mailbox and the design is
    deliberate (§7.8.3), but a future reader may see two addresses and think one is wrong. Worth a
    sentence in `06` §6.9.7 saying so — and the same applies to the third form, the `+unsub-`
    address, which now also appears in the body.

15. **`06` and `09` must both read `inbound_emails.body_scrubbed`, never `body_text`.** §7.8.12 is
    this document's half of `_CONTEXT.md` §2's no-contact-values-to-an-LLM rule, and the enforcement
    only works if the prompt-assembly paths in `06` §6.8 and `09` §9.11 consume the scrubbed column.
    `09` also still names `claude-haiku-4-5-20251001` as its classifier model in several places,
    which contradicts `_CONTEXT.md` §2's `gemini-2.5-flash`; not this document's section to edit, but
    it is the same rewrite pass and should be caught in it.

16. **Whether Gmail preserves a client-supplied `Message-ID` on SMTP submission is unresolved and
    unresolvable from a specification.** §7.8.1 designs for both outcomes and §7.4.7 step 9 measures
    it on the real account before the first cold message. If it turns out that Gmail always rewrites,
    two small simplifications become available — `M1` could be dropped in favour of `M2` alone, and
    `T6`'s uniqueness check becomes purely local — but neither is worth pre-committing to. This is
    an empirical question with a ten-minute experiment attached, not a design question.

17. **Unresolved, and needs Sagar's input rather than a designer's:** the account's display name and
    local part. `sagar.radar.mail@gmail.com` is SAMPLE. A name obviously derived from the real
    business reads better to a recipient and ties the account to the brand; a neutral one is cleaner
    to abandon if the account is closed. The 25-character local-part budget (§7.4.2) constrains both.
    §7.4.7 step 1 assumes the former.

18. **The identity page's hosting is stated as GitHub Pages and its content is not specified beyond
    §7.4.4's list.** If Sagar already owns a domain and a website for the real business — which the
    free-stack constraint does not forbid, it only forbids *buying* one for outreach — then
    `identity.site_url` should point at that instead, and it is strictly better: an established site
    with a history is a stronger answer to "who is this" than a fresh Pages site. Needs a yes/no from
    Sagar, and nothing else in this document changes either way.
