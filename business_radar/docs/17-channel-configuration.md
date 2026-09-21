# 17. Deferred channel configuration

This document decides that channel configuration is **optional, deferred and separable**: a fresh
clone of `business_radar` with an empty `config/.env` boots, serves the web app, runs a campaign,
researches businesses, produces the §5 HTML report, walks the §15 verification gate, records
selections, drafts messages through Gemini, runs the §6 claim-policy engine, renders the §27 preview
and writes a real `outreach_approvals` row — and the only thing it cannot do is put bytes on a
socket. It defines `CHANNEL_UNCONFIGURED` as a first-class, informative, per-channel state rather
than an error; the `ChannelStatus` record that carries it; the new eligibility gate `B3` and where it
sits in `05-outreach-workflow.md`'s A-I ordering; the ruling that an approval created while a channel
is unconfigured **stops at `APPROVED` and never queues**, together with the shelf life that retires
it; the three configuration surfaces (`config.yaml`, `config/.env`, and four `main.py` flags); the
connection test that verifies SMTP, IMAP and plus-addressing without ever touching a prospect; the
order Sagar should do things in with wall-clock waits marked; and the rule that configuring a channel
later must never retroactively transmit anything approved earlier. It owns no table and adds no
migration.

---

## 17.1 The principle

> **Channel configuration is optional and deferred. The system is completely usable with zero channel
> credentials, it says so in a sentence a human can act on, and it never fails to explain itself.**

Stated as four rules that the rest of this document implements:

| # | Rule |
|---|---|
| R1 | A fresh install with **no `config/.env` at all** must start, migrate, serve `127.0.0.1`, and run every pipeline stage from `AI_RESEARCHED` to `APPROVED`. The only credential that gates real work is `GEMINI_API_KEY` — and its absence blocks research, not the app |
| R2 | Absence of a channel credential is reported as **state**, never as an exception. No stack trace, no `KeyError`, no 500, no silent no-op |
| R3 | Every surface that could offer a send explains, in one sentence, that the channel is not configured and where to configure it — using `15-ui-wireframe.md` §15.18.3's `BLOCK_REASON` conventions and its one-sentence register |
| R4 | Turning a channel on is a **separate, self-contained step** with its own command, its own test, and no dependency on anything else in the system. Turning it on transmits nothing that was approved before it was turned on (§17.4.5) |

**This is not a degraded mode.** `07-email-integration.md` §7.3.4 already makes `NullEmailTransport`
the default "everywhere until a human edits config", and §7.3.9 defines MVP milestone 5 as the entire
send path running with `email.transport: null`. Milestone 6 — the same nine assertions against a real
Gmail account with exactly one recipient, Sagar himself — is a *later* milestone by design.
`16-mvp-plan.md` owns the milestone list; at the time of writing §7.3.9 is the only place it is
defined, and this document is written against that definition (amendment request in Open questions).

Milestone 5 is where Sagar is meant to **live for weeks**: researching four cities, tuning the
opportunity score, learning which verification checks he actually trips on, reading the messages the
LLM writes for a hospital versus a bakery, and finding the wording he is willing to put his name to —
all before a single stranger receives anything. `07` §7.4.5's ramp starts at three messages a day
precisely because the first day of sending should be boring, and it can only be boring if everything
else was already working the day before. So the design target is not "the system tolerates a missing
App Password". It is: **the missing App Password is the expected state, and the system is built
around it.**

---

## 17.2 What works with nothing configured

The precise inventory. "Nothing configured" means: `config.yaml` as shipped (`config.example.yaml`
copied), `config/.env` containing `GEMINI_API_KEY` and nothing else, no Gmail account in existence,
no phone number decided, no Meta account.

| Feature | State | Detail |
|---|---|---|
| App boots, `python main.py serve` | **Works** | waitress on `127.0.0.1`. `validate_secrets()` (`12` §12.5.4) passes: every email variable is `required_when="email_live"`, and email is not live |
| Migrations `001`-`057`; `python main.py doctor`; login, TOTP, RBAC | **Works** | No migration reads a credential; the doctor checks are local; auth is local password plus TOTP, with no external identity provider in this build |
| Campaign creation (§1, §2); discovery via Overpass, Nominatim and websites (§1) | **Works** | Discovery is free and keyless. `_CONTEXT.md` §4 |
| Research synthesis (§12) | **Works**, needs `GEMINI_API_KEY` | The one credential that gates real work. Without it, `research_runs` fail with a named config error, not a crash |
| Scoring, opportunity, modules (§13); sources panel (§14) | **Works** | Local arithmetic over stored findings |
| HTML report, CSV, XLSX, PDF (§5, §41); archive (§42); daily report (§43) | **Works** | Self-contained files on disk. The send-readiness chip renders a new state (§17.3.6). The daily report's Telegram delivery needs `TELEGRAM_BOT_TOKEN`; without it, it is written to disk and logged |
| Verification workflow (§15, §16, §17) | **Works** | The whole nine-check gate, verdicts, revocation, re-verification |
| Contact capture and confirmation | **Works** | `business_contacts`, `human_verified`, provenance. Contacts are *stored*; nothing is *sent* to them |
| Bulk selection (§18); outreach workspace (§20) | **Works** | Gate B3 is not evaluated at `SELECT` stage — §17.3.7 |
| Channel selection (§21) | **Limited** | Every channel is offerable; `EMAIL` carries the unconfigured note. `WHATSAPP`/`MANUAL_LINK` and `MANUAL` are fully available |
| Message generation, email and WhatsApp (§22-§26) | **Works** | Needs Gemini, not a mailbox. `06-message-engine.md` never reads a channel credential |
| Claim-policy engine, rules A/K/M/P/R (§23) | **Works** | Pure function over the draft and the findings. `policy_result` stored |
| Message preview (§27) | **Works** | All nine panels render. Panel 8 (eligibility) carries gate B3's sentence as a note |
| Duplicate protection (§29), opt-out (§30), frequency (§31) | **Works** | Gates A, F, G evaluate normally over real rows |
| **Approval (§28)** | **Works** | `CONFIRM & SEND` is enabled; the click writes a real `outreach_approvals` row with `session_auth_method`, `approved_body_hash`, `eligibility_snapshot` and the verbatim §28 confirmation text. §17.4.1 |
| **The `.eml` on disk** | **Works** | Written at approval, to `data/outbox/unsent/<date>/<msg_id>.eml`. Parses with `email.parser`; opens in any mail client; greps like text. §17.4.5 |
| Message reaches `APPROVED` | **Works** | And **stops there.** No `QUEUED`, no `SENT`, no `businesses.status -> CONTACTED` |
| **SMTP transmission** | **Unavailable** | Gate B3 at `SEND` stage. The one thing that is genuinely blocked |
| **IMAP ingestion** | **Unavailable** | `poll_inbox` self-disables with one `INFO` line per launch, not a per-tick error |
| Reply capture, bounce/DSN parsing, `mailto:` unsubscribe ingest | **Unavailable** | All three are IMAP-derived. There is nothing to ingest: nothing was sent |
| Telegram alerts | **Limited** | Needs `TELEGRAM_BOT_TOKEN`. Without it, alerts go to `logs/` and the handoff inbox, and `10` §10.6's fallback ladder ends at the UI |
| **WhatsApp `MANUAL_LINK`** | **Works — with no credential, ever** | `build_wa_link()` needs the *recipient's* E.164 and the body. No Meta account, no token, no verification, no phone number of Sagar's. §17.8 |
| WhatsApp `CLOUD_API` | **Unavailable, and stays that way** | Gated behind `whatsapp_api_enabled = 0` plus a recorded `whatsapp_optins` row, enforced by DB trigger (`08` §8.3.9). Not a configuration question |
| `PHONE` and `MANUAL` channels | **Works** | `PHONE` is script-only by design (gate H4) — the system never dials. `MANUAL` records a send Sagar performed himself, with the same audit row |
| Response classification (§33), handoffs (§34), audit chain (§48, §49), backups, DPDP erasure | **Works** | `python main.py email reingest <path.eml>` feeds a saved message through the fixture path, so §33 and §34 are exercisable with no mailbox. `OUTREACH_APPROVED` audit rows exist; `OUTREACH_SENT` rows do not, because nothing was sent |
| Campaign dashboard (§36), city/industry comparison (§37, §38) | **Works** | Aggregates over real rows. Figures 8-13 render `—`, per `_CONTEXT.md` invariant 5 |

### 17.2.1 The four entries worth arguing about

| Entry | Why it is where it is |
|---|---|
| **Draft generation works** | Drafting needs `GEMINI_API_KEY` and the findings. It does not read `OUTREACH_GMAIL_*`, does not construct a MIME message, and does not know a transport exists. `06-message-engine.md` §6.13's prompt carries business name, city, category and findings — `_CONTEXT.md` §2 forbids contact values in it anyway, so the *absence* of a mailbox removes nothing the drafter had |
| **Approval works and writes a real row** | The approval record is the system's most important artefact — `_CONTEXT.md` invariant 1 makes it the thing a send requires. Making it conditional on a mailbox would mean milestone 5 exercises a *different* approval path from milestone 6, which is exactly the "null path short-circuits the recording path" that `07` §7.3.4 refuses. The row is real, the hash is real, the session proof is real |
| **The `.eml` is on disk** | Because the question Sagar will actually have in week one is "what does this look like when it lands", and the honest answer is a file he can open in Outlook. Reading the exact bytes — the 78-column wrapped plain text, the RFC 2047-encoded Devanagari subject, the `List-Unsubscribe` header — is what turns the message engine from a black box into something he can edit with confidence |
| **`MANUAL_LINK` needs nothing** | The entry most likely to be got wrong. Examined in §17.8 |

### 17.2.2 What "unavailable" is allowed to look like

| Not allowed | Required instead |
|---|---|
| `KeyError: 'OUTREACH_GMAIL_APP_PASSWORD'` | `ChannelStatus(channel='EMAIL', configured=False, missing=('OUTREACH_GMAIL_USER','OUTREACH_GMAIL_APP_PASSWORD'))` |
| A 500 from `/outreach/<draft_id>` | The page renders; panel 8 carries the gate B3 sentence; `CONFIRM & SEND` behaves per §17.4.1 |
| `poll_inbox` failing every 2 minutes and filling `logs/` | The job self-disables at registration with one line: `poll_inbox not scheduled: EMAIL is not configured` |
| A send that silently does nothing and reports success | Gate B3 blocks at `SEND` stage with a sentence, an `ELIGIBILITY_BLOCK` event and no status change |
| `email.transport: gmail` with no credentials, quietly falling back | It already falls back to null (`07` §7.3.7 lock 4) **and logs `ERROR` naming the missing variables**. §17.3.1 adds: it is also `configured=False` with `last_error` set, so the state is visible in the UI and not only in a log file |

---

## 17.3 The `CHANNEL_UNCONFIGURED` state

### 17.3.1 Detection — the four locks, generalised per channel

`07-email-integration.md` §7.3.7 defines four independent locks for email. This document reads the
same four locks as a **detector** rather than only as a factory guard, and generalises their shape to
every channel so that one function answers the question for all four.

| Lock | Meaning | `EMAIL` | `WHATSAPP` | `PHONE` | `MANUAL` |
|---|---|---|---|---|---|
| 1 | A live mode is named in `config.yaml` | `email.transport` (`null` \| `gmail`) | `whatsapp.mode` (`manual_link` \| `cloud_api`) | n/a — never transmits | n/a — never transmits |
| 2 | An explicit boolean in `config.yaml` / `contact_policy` | `email.live_send_enabled` | `contact_policy.whatsapp_api_enabled` | `contact_policy.phone_enabled` | `contact_policy.manual_enabled` |
| 3 | An environment variable set only by the production launcher | `RADAR_EMAIL_LIVE=yes` | `RADAR_WHATSAPP_LIVE=yes` | n/a | n/a |
| 4 | Credentials present in `config/.env` | `OUTREACH_GMAIL_USER`, `OUTREACH_GMAIL_APP_PASSWORD`, `UNSUBSCRIBE_SIGNING_SECRET` | `WA_ACCESS_TOKEN`, `WA_PHONE_NUMBER_ID`, `WA_APP_SECRET` | none | none |

Three readings fall straight out of that table, and they are the whole of the detection logic:

1. **`PHONE` and `MANUAL` have no locks 1, 3 or 4.** They are never unconfigured, because they never
   transmit. `PHONE` produces a call script; `MANUAL` produces text Sagar sends himself. Both are
   `configured=True` on a machine that has never seen a credential.
2. **`WHATSAPP` in `manual_link` mode has no locks 3 or 4 either.** Lock 1 is satisfied by the shipped
   default and lock 2 by `whatsapp_enabled = 1`. §17.8.
3. **`EMAIL` is the only channel where deferred configuration is a real state**, and its four locks
   are already written, already default-closed, and already tested (`07` §7.16 row 2).

```python
# radar/channels/status.py
"""Answers 'is this channel set up?' in one place, so that no screen has to guess.

The failure this module prevents is the one that greets a new install: a KeyError from deep
inside a transport because config/.env has never existed, surfacing as a 500 on the one
screen Sagar was trying to learn the system from. A missing credential is a fact about the
laptop, not an exception, and this is where that fact lives. Every surface that could offer
a send - the eligibility engine, /settings, the report chip, the dashboard, the CLI - reads
its answer from here and from nowhere else.
"""
CHANNELS: tuple[str, ...] = ("EMAIL", "WHATSAPP", "PHONE", "MANUAL")

# lock 4, keyed by (channel, live mode). Mirrors 07 7.3.7's _REQUIRED_ENV and extends it.
_REQUIRED_ENV: dict[tuple[str, str], tuple[str, ...]] = {
    ("EMAIL", "gmail"): ("OUTREACH_GMAIL_USER", "OUTREACH_GMAIL_APP_PASSWORD",
                         "UNSUBSCRIBE_SIGNING_SECRET"),
    ("WHATSAPP", "cloud_api"): ("WA_ACCESS_TOKEN", "WA_PHONE_NUMBER_ID", "WA_APP_SECRET"),
}

# lock 3, per channel. A channel absent from this map has no environment lock.
_LIVE_ENV: dict[str, str] = {"EMAIL": "RADAR_EMAIL_LIVE", "WHATSAPP": "RADAR_WHATSAPP_LIVE"}
```

### 17.3.2 `ChannelStatus`

```python
@dataclass(frozen=True)
class ChannelStatus:
    """What one channel can do right now, and what is missing if it cannot.

    Frozen, and `missing` is a tuple rather than a list, because this object is cached and
    handed to five callers. A cached value a caller can append to is a cache that lies.
    """
    channel: str                    # EMAIL | WHATSAPP | PHONE | MANUAL
    configured: bool                # can this channel complete its own transmission step?
    mode: str                       # UNCONFIGURED | REHEARSAL | GMAIL_LIVE
                                    # MANUAL_LINK | CLOUD_API | SCRIPT_ONLY | CLIPBOARD
    missing: tuple[str, ...]        # ordered, human-readable, most-blocking first
    last_verified_at: str | None    # ISO-8601 UTC; when the connection test last passed
    last_error: str | None          # one sentence from the last failed test or startup check

    @property
    def unconfigured(self) -> bool: return not self.configured

    def sentence(self) -> str:
        """The one sentence every surface renders. 15-ui-wireframe.md 15.18.3's register:
        name the missing precondition and where to fix it, never a generic refusal."""

    def to_json(self) -> dict: ...
```

The `mode` values, and what each means:

| Channel | `mode` | `configured` | Meaning |
|---|---|---|---|
| `EMAIL` | `UNCONFIGURED` | `False` | Lock 1 closed (`transport: null`) and `email.rehearsal` false. **The shipped default.** Drafting, policy, preview and approval all run; transmission is refused by gate B3 |
| `EMAIL` | `REHEARSAL` | `False` | Lock 1 closed, `email.rehearsal: true`, `email.rehearsal_recipients` non-empty. `07` §7.3.9's milestone-5 drill: the full recording path runs against an allowlist of Sagar's own addresses. §17.4.6 |
| `EMAIL` | `GMAIL_LIVE` | `True` | All four locks open and `identity.from_address` set. Real businesses can receive real mail |
| `WHATSAPP` | `MANUAL_LINK` | `True` | The default. Zero credentials. §17.8 |
| `WHATSAPP` | `CLOUD_API` | `True` | All four locks open. Still per-message gated by `whatsapp_optins` at the database level |
| `PHONE` | `SCRIPT_ONLY` | `True` | Always. The system never dials |
| `MANUAL` | `CLIPBOARD` | `True` | Always |

Note what `configured` does **not** mean. It is not "this business can be contacted" — that is
`check_send_eligibility()`, and it evaluates forty things. It is not "this channel is switched on" —
that is `contact_policy.<channel>_enabled` and gate B2. It is exactly: *if every other gate passed,
could this channel put the message where it is supposed to go?*

`EMAIL` with `mode='REHEARSAL'` is deliberately `configured=False`. A rehearsal writes a file; it does
not contact anybody; and reporting it as configured would make `/settings` claim a capability the
system does not have. The rehearsal is a drill, and drills are labelled.

### 17.3.3 Evaluation, caching and invalidation

```python
def evaluate(cfg: Config, policy: ContactPolicy,
             env: Mapping[str, str] = os.environ) -> dict[str, ChannelStatus]:
    """Read the locks for every channel. No network, no database write, no exception.

    Nothing here raises. A channel this function cannot understand - a mode name that is not
    in the enum, a config block that is absent entirely - is reported as UNCONFIGURED with
    the reason in `missing`, because the alternative is a startup crash on a laptop whose
    only problem is a typo in a YAML file.
    """

def channel_status(channel: str) -> ChannelStatus: ...          # the cached answer
def refresh(cfg, policy, *, reason: str) -> dict[str, ChannelStatus]: ...
def record_test_result(channel: str, *, ok: bool, error: str | None, now: str) -> None: ...
```

| Property | Decision | Why |
|---|---|---|
| When evaluated | Once at startup, in `create_app()` and in the worker bootstrap, immediately after `validate_secrets()` and immediately before `07` §7.3.8's `assert_transport_declared()` | The startup assertion is about a *live* transport and may raise; this is about all four channels and must not |
| Cached | Module-level dict behind a `threading.Lock` | Read once per eligibility call, once per grid row, once per page render. Re-reading `os.environ` and the config for each of 200 grid rows is waste |
| Invalidated by | `PUT /api/v1/settings/channels`; a completed `--test-email` / `--test-whatsapp`; an explicit `refresh()` from the CLI. Nothing else | Env vars and `config.yaml` cannot change under a running process without a restart. `contact_policy` can, and that is lock 2 |
| Never invalidated by | A failed send, a bounce, a 535 at runtime | That is `07` §7.9.7's account-notice path, not a configuration change. Flipping `configured` on the first auth error would let one transient network failure erase the setup state |
| Startup log | One line per channel, at `INFO`, always: `channel EMAIL configured=False mode=UNCONFIGURED missing=OUTREACH_GMAIL_USER,OUTREACH_GMAIL_APP_PASSWORD` | — |
| Persistence | `last_verified_at` and `last_error` live in `config/state/channels.json`, written `.tmp` then `os.replace` | They must survive a restart, they are not secrets, and they do not belong in `contact_policy` — that table holds policy Sagar sets, not observations the system made. No migration, no table |

`config/state/channels.json`, SAMPLE:

```json
{
  "version": 1,
  "EMAIL":    {"last_verified_at": null,
               "last_error": "SMTP AUTH refused: 535-5.7.8 Username and Password not accepted"},
  "WHATSAPP": {"last_verified_at": "2026-08-27T09:12:04Z", "last_error": null}
}
```

It contains no address, no password and no token — only a timestamp and a sentence. It is safe to
screenshot, which is the same property `python main.py config check` has and for the same reason
(`12` §12.5.4).

### 17.3.4 The identity placeholder, so an empty `.env` can still build a message

`build_mime()` needs a `From`. `06-message-engine.md`'s rule `P2` compares the body against
`identity.reply_to` and `identity.unsubscribe_mailbox`. `07` §7.7.2's unsubscribe address is derived
from the local part of `identity.from_address`. On a machine with no Gmail account, none of those
exist — and without them, drafting and approval would fail, which R1 forbids.

The ruling: when `EMAIL` is unconfigured, `radar/config.py` substitutes a **reserved placeholder
identity** that cannot be a mailbox anywhere.

```yaml
# Not written into config.yaml. Applied by Config.load() when identity.from_address is empty.
identity:
  from_address:        radar-rehearsal@localhost.invalid    # RFC 2606: .invalid never resolves
  unsubscribe_mailbox: radar-rehearsal+unsub@localhost.invalid
  reply_to:            radar-rehearsal@localhost.invalid
  sender_name:         Sagar                                # from config.yaml, real
  company_name:        <as configured>                      # from config.yaml, real
  phone_display:       ""            # rendered as an omitted signature line, never a placeholder
```

| Rule | Enforcement |
|---|---|
| A live transport may never be constructed with a `.invalid` from-address | `assert_transport_declared()` (`07` §7.3.8) gains one check: `if transport.is_live and from_address.endswith('.invalid'): raise ConfigError`. Boot fails, loudly, before anything can send |
| A built MIME message whose `From` ends in `.invalid` may only be produced by `NullEmailTransport` | New transport check `T10` in `radar/email/checks.py`, beside `T1`-`T9`. Amendment request to `07` |
| The placeholder is never shown to Sagar as if it were his address | `/settings` renders `not set`; the §28 confirmation renders the From row as `— no sending address configured —` |
| `identity.phone_display` empty renders **nothing** | Not `+91 XXXXXXXXXX`. A message that goes out with a placeholder phone number in the signature is the most embarrassing failure available here, and `06`'s rule `A3` allowlists signature digits, so nothing else would catch it |
| The 64-character budget check still runs | `radar-rehearsal` is 15 characters and the `+unsub-<32 hex>` form is 54 — inside `07` §7.4.2's ceiling, so the boot assertion behaves identically before and after configuration |

The placeholder is why an `.eml` written on day one is a complete, valid, readable message rather than
a template with holes in it — and why it still cannot be dragged into a mail client and accidentally
delivered.

### 17.3.5 `UNSUBSCRIBE_SIGNING_SECRET` is minted, not obtained

Of the three variables in `_REQUIRED_ENV[("EMAIL","gmail")]`, two come from Google and one does not.
`UNSUBSCRIBE_SIGNING_SECRET` is 32 random bytes; nobody issues it; there is no account to create and
no wait. Treating it as something Sagar has to go and get would make the empty-`.env` case need a
manual step for no reason, and would put a credential-shaped obstacle in front of a value the machine
can produce in a microsecond.

| Decision | Detail |
|---|---|
| Minted on first run | `python main.py migrate` (and `serve` against a fresh database) generates `secrets.token_hex(32)` and appends it to `config/.env`, creating the file with `12` §12.5.2's ACL if it does not exist |
| Never regenerated | If the variable is present it is left alone. `07` §7.12.2: rotating it invalidates every outstanding unsubscribe token |
| Logged as | `minted UNSUBSCRIBE_SIGNING_SECRET (fp 3f9a1c02) into config/.env; back this up with the database` — fingerprint only, never the value |
| Same treatment | `SUPPRESSION_HMAC_PEPPER` and `AUDIT_EXPORT_HMAC_KEY`: local random values whose loss is unrecoverable and whose absence blocks work for no reason |
| Not the same treatment | `OUTREACH_GMAIL_APP_PASSWORD`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `WA_ACCESS_TOKEN` — issued by somebody else and impossible to invent |

Amendment request to `12-security-model.md` §12.5.4, which currently treats every variable in the
inventory as operator-supplied.

### 17.3.6 Where it surfaces, and the exact sentence at each surface

Five surfaces. One source of truth: `ChannelStatus.sentence()`, called from `radar/policy.py`'s gate
B3 and re-used by the four presentation layers. `15-ui-wireframe.md` §15.18.3's rules hold — the
sentence names the missing precondition and where to fix it, never a generic refusal; and rule 3
holds too: the map holds the generic form, the renderer specialises it when it has the detail.

The `BLOCK_REASON` addition (`15` §15.18.3 and `03` §3.7.1 — one map, imported from `radar/policy.py`,
never re-typed):

```python
BLOCK_REASON["B_CHANNEL_UNCONFIGURED"] = "This channel is not configured yet - Settings > Channels."
```

Specialised per channel and per missing item at render time:

| Surface | Condition | Exact sentence |
|---|---|---|
| **Gate B3, generic** | `EMAIL` unconfigured | `Email is not configured yet - Settings > Channels.` |
| **Gate B3, specialised** | lock 4, App Password absent | `Email is not configured yet: the Gmail App Password is missing. Settings > Channels.` |
| **Gate B3, specialised** | lock 4, `OUTREACH_GMAIL_USER` absent | `Email is not configured yet: no Gmail account has been set. Settings > Channels.` |
| **Gate B3, specialised** | credentials present, connection test never passed | `Email credentials are present but have never been tested - run python main.py --test-email.` |
| **Gate B3, `WHATSAPP`** | `cloud_api` named, credentials absent | `WhatsApp Cloud API is not configured. Manual mode works now: prepare the message and open the link yourself.` |
| **Settings > Channels** | `EMAIL` unconfigured | `Not configured. Run python main.py --setup-email, or fill this in below.` — with the ordered `missing` list rendered as a checklist |
| **Report send-readiness chip** (`03` §3.8.3) | approved, channel unconfigured | Chip `Approved - email not configured` (blue), linking to `/settings#channels` |
| **Campaign dashboard** (`15` §15.3.2) | ≥1 message `APPROVED` and the channel unconfigured | Banner: `9 messages are approved and waiting. Email is not configured, so nothing has been sent. Set it up in Settings > Channels, then approve them again - approvals expire after 72 hours.` |
| **Confirm & send dialog** (`15` §15.10) | channel unconfigured | The button reads `APPROVE (nothing will be sent yet)`, and the dialog's last line is `Email is not configured, so this records your approval and writes the message to data/outbox/unsent/. Nobody receives anything.` |
| **CLI, any send command** | channel unconfigured | `EMAIL is not configured. Nothing was sent. Run: python main.py --setup-email` and exit code `2` |
| **`GET /api/v1/health`** | always | `{"channels": [{"channel": "EMAIL", "configured": false, "mode": "UNCONFIGURED", "missing": ["OUTREACH_GMAIL_USER", "OUTREACH_GMAIL_APP_PASSWORD"], "last_verified_at": null, "last_error": null}]}` |

**Register.** Every one of those is a statement of fact plus a next action. None is an apology, a
warning triangle, or a word like `ERROR`, `FAILED` or `DISABLED`. The colour token is `--info` (blue)
and not `--bad` (red), because `03` §3.9.1 assigns red to opt-outs, bounces and policy blocks — things
that are wrong. An unconfigured channel is not wrong; it is Tuesday.

The one exception, deliberate: the **half-configured** states (lock 1 or lock 3 closed while
credentials exist, or credentials present but never tested) render in `--warn` yellow, because those
*are* mistakes. Somebody started and stopped, and the system should say so more sharply than it says
"you have not started".

### 17.3.7 The new gate, and the revised gate order

One new gate, in the `B` family, because `B` is already "mode and switches" and this is a switch that
was never thrown.

| Gate | Code | Question | Hard | Stages | One sentence to Sagar (template) |
|---|---|---|---|---|---|
| B3 | `B_CHANNEL_UNCONFIGURED` | is the channel configured to transmit? | yes | **SEND only** | "{channel_sentence}" — §17.3.6's table |

The revised catalogue, `05-outreach-workflow.md` §5.9.1. Only the `B` family changes; every other
letter is verbatim as `05` has it:

```
A1..A5  A_SUPPRESSED_BUSINESS / _EMAIL / _PHONE / _WHATSAPP / _DOMAIN     unchanged
B1      B_MODE_NOT_HUMAN_APPROVAL
B2      B_CHANNEL_DISABLED
B3      B_CHANNEL_UNCONFIGURED                                            <- new, SEND only
C1..C3  D1..D5  E1..E4  F1..F7  G1..G6  H1..H5  I1..I4                    unchanged
```

**What changed, exactly:**

| Change | Detail |
|---|---|
| One gate added | `B3`, immediately after `B2` |
| Gate count | 39 -> 40. `Eligibility.gates` carries 40 entries; `05` §5.9.12's payload note updates |
| Precedence | **Unchanged for every existing gate.** Nothing was reordered |
| Stage scope | `B3` is **`SEND` only**. Not evaluated at `SELECT` or `PREVIEW` |
| `05` §5.8.1's purity contract | Held. `B3` performs no write, no network call and no LLM call. It reads a process-local dict |
| `05` §5.9.4's "gate B is campaign-wide" note | Extends to B3, which is machine-wide. When B3 blocks, the workspace renders one banner, not N tooltips |

### 17.3.8 Why B3 sits there — three arguments and one counter-argument

**Why not before gate A.** A suppression is a permanent fact about *a person who asked us to stop*;
the state of Sagar's laptop is a temporary fact about Sagar's laptop. `05` §5.9.1 already states the
ordering principle — *"permanent legal facts first, then configuration"* — and B3 is configuration by
definition.

The concrete failure if B3 preempted A: during milestone 5 every business would report
`Email is not configured yet` and **nothing else**, because `blocking_code` is the first block in
precedence order. Sagar would spend three weeks looking at a system that never once tells him a
business has opted out, and the day he configures Gmail, forty rows would simultaneously reveal DO NOT
CONTACT banners he has never seen. He would also have spent those weeks verifying, selecting and
drafting for suppressed businesses, because nothing told him not to. An opt-out is the single most
important thing this system knows; it must be the first thing it says, in every configuration state,
including the one where it cannot send anyway. The same argument holds against putting B3 ahead of
`C`, `D`, `E`, `F` or `G`: "you rejected this business in June" and "you contacted them six days ago"
are both more useful than "you have not set up Gmail", which he has known since Tuesday.

**Why `SEND` only, and not `PREVIEW`.** This is the decision that makes §17.4 possible. Gate B2 is
`PREVIEW, SEND` because a channel Sagar deliberately switched off is one he does not want to prepare
messages for. B3 is the opposite: an unconfigured channel is one he *does* want to prepare messages
for — that is the entire point of milestone 5. If B3 blocked at `PREVIEW`, `CONFIRM & SEND` would
render disabled, no `outreach_approvals` row could ever be written, and §17.2's "approval works" would
be false. The preview screen still *mentions* it, in panel 8, in `--info`; it does not block.

**Why not `SELECT` either.** Same reason, sharper: at `SELECT` stage the grid greys out rows, and a
gate that greyed out all 148 rows of a campaign because email is not configured would make the
selection grid useless on the one day it matters most. B3 returns no result at `SELECT`; the
`Eligibility` payload marks it `checked at send`, per `05` §5.8.2's handling of gates a stage cannot
evaluate. `SKIP` is not `PASS`, and the workspace renders it as such.

**The counter-argument, stated fairly.** Letting a human approve a message that cannot be sent invites
"why did you let me do that?" — fifteen approvals, none of which went anywhere. Three answers: the
confirm dialog says so in the sentence immediately above the button, before the click (§17.3.6); the
72-hour shelf life stops them accumulating silently (§17.4.3); and the alternative is worse, because
blocking approval means the first `outreach_approvals` row ever written would be written on the first
day a stranger receives mail — the arrangement `07` §7.3.4 rejects when it refuses to let the null
transport short-circuit the recording path.

---

## 17.4 What happens to work done while unconfigured

### 17.4.1 The ruling

> **An approval created while the channel is unconfigured is written, is real, and is honoured. The
> message stops at `APPROVED`. It does not queue, it is not held, and it is not sent when the channel
> is later configured. Approvals expire after 72 hours; expired ones are retired visibly, and Sagar
> approves again from a fresh preview.**

Stated per state transition:

| Step | Configured | Unconfigured |
|---|---|---|
| Draft -> `PENDING_APPROVAL` | identical | identical |
| `CONFIRM & SEND` clicked | writes `outreach_approvals`; `PENDING_APPROVAL -> APPROVED` | **identical** — same row, same hash, same session proof, same `eligibility_snapshot` |
| `.eml` written | at send, by `NullEmailTransport` or by the SMTP transport's capture, to `data/outbox/<date>/` | at **approval**, to `data/outbox/unsent/<date>/` |
| `POST /api/v1/outreach/messages/<id>/send` | `APPROVED -> QUEUED`, enqueues `send_email` | `409 BLOCKED`, envelope carries `blocking_code: "B_CHANNEL_UNCONFIGURED"` and the sentence. **No status change.** The endpoint is not offered by the UI in this state |
| Worker | claims, gates, transmits, `SENT` | nothing to claim |
| `businesses.status` | `-> CONTACTED` | stays `CONTACT_READY` |
| `campaigns.n_contacted` | incremented | unchanged |
| Audit | `OUTREACH_APPROVED`, then `OUTREACH_SENT` | `OUTREACH_APPROVED` only, plus `OUTREACH_APPROVED_UNSENT` detail flag `{"channel_status": "UNCONFIGURED"}` |
| After 72 h | n/a — it was sent | `APPROVED -> CANCELLED`, `revoke_reason = 'APPROVAL_EXPIRED_UNSENT'`. §17.4.3 |

`businesses.status` staying at `CONTACT_READY` is the entry that matters most. Marking a business
`CONTACTED` when nobody contacted it corrupts four things at once: §29's duplicate protection (gate F6
would refuse a real send later), the §36 funnel, the §37 city comparison, and `_CONTEXT.md` invariant
5's promise that report numbers come from SQL aggregates over real rows. A rehearsal that lies to the
funnel is worse than no rehearsal.

### 17.4.2 Why not a queue

The tempting design is: approve now, hold in `QUEUED`, drain when the channel comes up. Four reasons
it is wrong, in increasing order of severity.

| # | Reason |
|---|---|
| 1 | **The TTL already forbids it.** `05` §5.9.11's gate I3 refuses any approval older than `approval_ttl_minutes` (default 60). A queue that waits three weeks is a queue in which *every* element is guaranteed to be refused at the moment it is drained. That is not a queue; it is a list of work to redo, wearing a queue's clothes |
| 2 | **The world moves.** `05` §5.10.1 lists what happens between approval and send over four minutes: an unsubscribe, a bounce pushing the rate over the limit, a manual contact from another campaign, a policy edit. Over three weeks add: `verification_valid_days` (30) elapsing so gate D3 blocks, the research going stale, the business being rejected, and the contact being flagged `WRONG_CONTACT`. An approval is a statement about a world that no longer exists |
| 3 | **The approval record's meaning decays.** Invariant 1 is not "a flag was set"; it is *a human read this exact message to this exact address and clicked once*. §28's confirmation sentence is present tense — "You are about to contact this business using the selected business contact." Three weeks later that sentence is false, and the stored `confirmation_text` would be a record of a claim that did not hold |
| 4 | **It produces the worst possible first sending day.** Fifteen or forty messages leaving in one burst on the day the account goes live. `07` §7.4.6 names burst shape as one of the two dominant abuse signals for a free Gmail account, and §7.4.5's ramp starts at three a day for exactly this reason. A drain-on-configure queue would ship, as a *feature*, the precise event the ramp exists to prevent — on day zero of the account's life, before the ramp has even started |

Reason 4 alone would settle it. A design where "finish setting up email" is also "send forty cold
messages in ninety seconds" is a design with a loaded gun in it.

### 17.4.3 The approval freshness window

Two numbers, doing two different jobs. Only the second is new.

| Name | Default | Where | Job |
|---|---|---|---|
| `contact_policy.approval_ttl_minutes` | 60 | gate I3, at the send boundary | "Is this approval still current *right now*, as we transmit?" Unchanged from `05` |
| `contact_policy.approval_shelf_life_hours` | **72** | a nightly job, `expire_approvals` | "Has this approval sat un-transmitted long enough that it should be retired rather than left lying around?" **New** |

Why 72 and not 60 minutes: an approval made at 18:00 on Friday should still be sendable on Monday
morning once the channel is configured, because the intervening days contained no working hours. 72
hours covers a weekend. Why not 30 days: `verification_valid_days` is 30, so an approval that outlived
the verification behind it would be blocked by gate D3 anyway; picking a shelf life longer than the
weakest upstream freshness window just moves the refusal later.

Why the two numbers are not one: they answer different questions and merging them breaks both. Setting
`approval_ttl_minutes` to 72 hours would let a queued batch that a crashed worker left sitting for
three days fire blind — the exact case §5.9.11 cites for the 60-minute TTL. Setting the shelf life to
60 minutes would retire every approval Sagar made just before lunch.

```python
# radar/outreach.py, run by the nightly `expire_approvals` job (14-background-jobs.md 14.9)

def expire_stale_approvals(conn, *, now: str, policy: ContactPolicy) -> list[str]:
    """Retire approvals that were never transmitted, so that none is ever acted on stale.

    Without this, the day Sagar finishes setting up Gmail is the day three weeks of
    rehearsal approvals become a decision he never actually made about businesses whose
    circumstances he last looked at in August. Retiring them is not losing work: the draft
    survives, the research survives, and re-approving is one click from a preview that
    re-evaluates every gate against today.
    """
```

| Property | Value |
|---|---|
| Selects | `outreach_messages.status = 'APPROVED'` and `outreach_approvals.approved_at < now - approval_shelf_life_hours` and `revoked_at IS NULL` |
| Writes | `revoked_at = now`, `revoked_by = NULL` (system), `revoke_reason = 'APPROVAL_EXPIRED_UNSENT'` |
| Message status | `APPROVED -> CANCELLED`. **This transition already exists** in `05` §5.3.7's `outreach_status_transitions` (`'approval revoked before queueing'`), so no schema change and no new trigger |
| Draft | Untouched. `superseded_by` stays `NULL`; the draft remains current and re-previewable. Gate F1 clears, because it counts `PENDING_APPROVAL`/`APPROVED`/`QUEUED`, so a new message can be created from the same draft |
| Records | One `outreach_events` row `APPROVAL_REVOKED`, `actor_type='SYSTEM'`, detail `{"reason": "SHELF_LIFE", "hours": 72, "channel_status": "UNCONFIGURED"}`; one `audit_log` row `OUTREACH_APPROVAL_REVOKED` per approval; one aggregated Telegram message per run, never one per approval |
| Idempotent | Re-running selects nothing, because the rows are `CANCELLED` |

### 17.4.4 What Sagar sees when one expires

Telegram, the morning after (SAMPLE):

```
business_radar - approvals retired

9 approvals expired without being sent (shelf life 72h).
Email is still not configured, so nothing left the machine.

  Dhule     4    Nashik    3    Jalgaon   2
  Oldest approved 2026-08-24 17:42 IST

The drafts are intact. Set up email (python main.py --setup-email),
then re-approve from /outreach - each preview re-checks every gate
against today.
```

`/outreach` grows one band above the others (`15` §15.8) — SAMPLE counts — headed
`RETIRED - APPROVED BUT NEVER SENT   9`, with the two lines
`These approvals expired after 72 hours. Nothing was sent, nothing is lost.` and
`Email is not configured - Settings > Channels.` Each row carries the business, the city, the
approval timestamp and a `[ Review again ]` control.

`Review again` opens `/outreach/<draft_id>` — the ordinary preview, which re-runs
`check_send_eligibility(stage='PREVIEW')` against current data. If the business was suppressed in the
meantime, he finds out there, which is the whole point.

### 17.4.5 The `.eml` files, and why nothing ever sweeps them

The requirement in one line: **configuring a channel must not transmit anything approved before it was
configured.** Five mechanisms, any one of which is sufficient, because this is the failure mode with
the worst blast radius in the document.

| # | Mechanism |
|---|---|
| 1 | **The outbox is write-only.** No code path in `radar/` opens a file under `data/outbox/` for reading, and none constructs an `OutboundEmail` from a file on disk. There is no directory-scanning sender, no "drain the outbox" command, and no plan for one. `test_outbox_is_write_only` greps the package for reads under the outbox root and fails on any |
| 2 | **Transmission is keyed on database state, never on file state.** The only producer of a `send_email` job is `POST /api/v1/outreach/messages/<id>/send`, which requires `status='APPROVED'` and a live approval. Configuring a channel changes a `ChannelStatus` in memory and three lines in `config/.env`; it enqueues nothing, touches no `outreach_messages` row, and runs no migration over existing rows |
| 3 | **Two different trees.** Rehearsal and live captures go to `data/outbox/<date>/`; unconfigured-approval previews go to `data/outbox/unsent/<date>/`. Even a hypothetical future drain command written by somebody who did not read this document would have to name the second path deliberately |
| 4 | **The files are marked.** Every `.eml` written while unconfigured carries two headers the live path never emits: `X-Radar-Outbox-Reason: CHANNEL_UNCONFIGURED` and `X-Radar-Transmitted: no`. Transport check `T10` refuses to transmit any built message carrying either header |

**What if Sagar deliberately opens one and sends it by hand?** Legitimate — it is the `MANUAL`
channel, which `_CONTEXT.md` §6 lists as first-class and `07` §7.2.8 calls the escape hatch and the
floor. But it must be recorded, or the duplicate protection, the frequency policy and the funnel are
all wrong about that business from then on. So `POST /api/v1/outreach/messages/<id>/record-manual`
(or `python main.py outreach record-manual --message msg_...`) writes `channel='MANUAL'`,
`provider='manual_email'`, `status='SENT'`, the §48 audit row, and moves `businesses.status` to
`CONTACTED`. If he does not record it, gate F2 will not block a second message to that address, the
§32 history is missing a row, and the §36 funnel under-counts — so the `.eml` says so in its own
headers: `X-Radar-Note: if you send this by hand, record it: python main.py outreach record-manual
--message <id>`.

Retention: `data/outbox/unsent/` is swept by `11` §11.12's nightly `retention_purge` on the same
`P3Y` class as raw inbound `.eml.gz`. A file whose message was later `CANCELLED` by shelf-life expiry
is kept, not deleted — it is the only surviving copy of what would have gone out, and it is what makes
an expired approval reviewable rather than merely gone.

### 17.4.6 `REHEARSAL`, and why it is not the default

`07` §7.3.9's milestone-5 drill needs the full recording path: `status='SENT'`, `provider='null'`,
`businesses.status='CONTACTED'`, `campaigns.n_contacted` incremented, the `OUTREACH_SENT` audit row,
and a replay of the sent `.eml` through the inbound fixture path. That is a valuable test and it must
stay. It is also, by construction, a path that writes `CONTACTED` against businesses — so it cannot be
the default, or day-one browsing would corrupt the funnel (§17.4.1).

The reconciliation: rehearsal is an explicit, allowlisted opt-in.

```yaml
email:
  transport:            null
  live_send_enabled:    false
  rehearsal:            false      # 17.4.6. When true, the null transport runs the FULL
                                   # recording path: SENT, CONTACTED, counters, audit rows.
  rehearsal_recipients: []         # non-empty required when rehearsal is true. Gate B3 blocks
                                   # any message whose to_address_norm is not in this list.
```

| Rule | Detail |
|---|---|
| `rehearsal: true` with an empty `rehearsal_recipients` | `ConfigError` at boot. A rehearsal with no allowlist is indistinguishable from a live send that happens not to have a socket |
| Gate B3 under `mode='REHEARSAL'` | Passes only when `to_address_norm` is in `rehearsal_recipients`. Otherwise blocks with `Rehearsal mode only writes to your own addresses; contact@abc-hospital-sample.in is not one of them.` |
| The addresses | Sagar's own, as `07` §7.3.9 already stipulates ("one real researched business whose only contact is Sagar's own address"). This makes the stipulation enforceable rather than a note in a document |
| `provider` on the row | `'null'`, so `SELECT COUNT(*) ... WHERE provider = 'null'` (`07` §7.3.4) still answers "did this actually leave the machine" with a query |
| Turning it off | Rows written during rehearsal keep `provider='null'`. `v_campaign_counters` and every §36/§37/§38 aggregate exclude `provider='null'` rows from the `Sent` and `Contacted` figures — amendment request to `03` and `15`, because a rehearsal must not appear in a report as outreach |
| Who uses it | The test suite, and Sagar once, on the day he wants to see the whole chain including a reply. Not the daily working mode |

---

## 17.5 The configuration surfaces

Three, and they are strictly separated: non-secret shape in `config.yaml`, secrets in `config/.env`,
and a guided command that writes the second and tells him what to put in the first.

### 17.5.1 `config.yaml` — the non-secret channel block

Shipped verbatim as `config.example.yaml`. Every value below is the shipped default, and the shipped
default is "nothing is configured".

```yaml
# config.yaml  (channel block). Secrets NEVER appear here - 12-security-model.md 12.5.3.

email:
  transport:            null      # null | gmail                    <- lock 1
  live_send_enabled:    false     #                                 <- lock 2
  # lock 3 is RADAR_EMAIL_LIVE in the environment; lock 4 is config/.env
  rehearsal:            false     # 17.4.6
  rehearsal_recipients: []        # required non-empty when rehearsal is true
  outbox_dir:           data/outbox        # live/rehearsal .eml captures
  unsent_dir:           data/outbox/unsent # 17.4.5 - approvals made unconfigured
  # inert until configured; shipped so --setup-email has somewhere to write
  smtp_host: smtp.gmail.com     smtp_port: 587
  imap_host: imap.gmail.com     imap_port: 993
  sent_folder: "[Gmail]/Sent Mail"

whatsapp:
  mode:                 manual_link   # manual_link | cloud_api     <- lock 1
  # manual_link needs NO credential of any kind. 17.8
  manual_daily_cap:     15            # 08 8.6.7

identity:
  # Left empty on a fresh install. radar/config.py substitutes the placeholder identity
  # of 17.3.4 while EMAIL is unconfigured, so drafting and policy still work.
  from_address:         ""
  unsubscribe_mailbox:  ""
  sender_name:          "Sagar"
  role:                 "Founder"
  company_name:         ""          # the real registered name, before any send
  site_url:             ""
  phone_display:        ""          # empty renders NOTHING, never a placeholder (17.3.4)

contact_policy:                     # the lock-2 switches, seeded into the GLOBAL row
  email_enabled:        1
  whatsapp_enabled:     1
  whatsapp_api_enabled: 0           # 08: stays 0
  phone_enabled: 1      manual_enabled: 1
  approval_ttl_minutes:      60     # 05 5.9.11, gate I3
  approval_shelf_life_hours: 72     # 17.4.3, new
```

Note `email_enabled: 1` on a machine with no mailbox. That is correct and the distinction matters:
gate B2 asks "did Sagar switch this channel off?", gate B3 asks "is it set up?". Shipping with
`email_enabled: 0` would conflate the two and would mean the day Sagar configures Gmail he also has to
find a second switch he never knew was off.

### 17.5.2 `config/.env` — secrets, and only secrets

```
# config/.env   - NEVER committed, NEVER in config.yaml, NEVER in a backup that leaves the
#                 machine unencrypted. 12-security-model.md 12.5.

# ---- the only thing needed on day one ----------------------------------------
GEMINI_API_KEY=AIza...                    # aistudio.google.com. Free tier.

# ---- minted locally on first run; do not edit, do back up (17.3.5) -----------
UNSUBSCRIBE_SIGNING_SECRET=<64 hex>
SUPPRESSION_HMAC_PEPPER=<64 hex>
AUDIT_EXPORT_HMAC_KEY=<64 hex>

# ---- EMAIL: absent until `python main.py --setup-email` writes them ----------
#OUTREACH_GMAIL_USER=
#OUTREACH_GMAIL_APP_PASSWORD=

# ---- lock 3: set by the production launcher only, never written here ---------
#RADAR_EMAIL_LIVE=yes

# ---- alerting: a DIFFERENT Gmail account (07 7.12.1, 10 10.6.2) -------------
#NOTIFY_GMAIL_USER=
#NOTIFY_GMAIL_APP_PASSWORD=
#ALERT_EMAIL_TO=
#TELEGRAM_BOT_TOKEN=

# ---- WhatsApp Cloud API: not used in v1 (08). manual_link needs none of these -
#WA_ACCESS_TOKEN=
#WA_PHONE_NUMBER_ID=
#WA_APP_SECRET=
```

Rules from `12-security-model.md` that a setup command could violate, and how `--setup-email` obeys
each:

| Rule | Source | How `--setup-email` obeys it |
|---|---|---|
| No secret in `config.yaml` | `_CONTEXT.md` §1, `12` §12.5.3 | Host/port/account-shape answers go to `config.yaml`, the App Password to `config/.env`, never the reverse |
| Owner-only ACL | `12` §12.5.2 | On creating or first writing `config/.env` it runs the `icacls` sequence and prints what it did. A world-readable `.env` refuses startup |
| Never printed back | `12` §12.5.4 | Read with `getpass`; never echoed, logged, rendered in `/settings`, or returned by any API. Only an 8-hex fingerprint is ever displayed |
| No placeholders, and shape validated | `12` §12.5.4 | `validate_secrets()` runs before the command exits: `CHANGEME` and its friends are refused, and the App Password must be 16 `[a-z]` after spaces are stripped. Google displays them in four groups of four and pasting the spaces is the commonest setup error, so the loader strips and *then* validates |
| Not in a synced folder | `12` §12.5.2 | `--setup-email` refuses to write into a path under `OneDrive\`, `Dropbox\`, `Google Drive\` or `iCloudDrive\`, naming the path |
| Rotation writes an audit row | `12` §12.5.5 | Overwriting an existing `OUTREACH_GMAIL_APP_PASSWORD` writes `SECRET_ROTATED` with `fingerprint_before` and `fingerprint_after`, and reminds him that revoking the old one is the step that constitutes the rotation |

### 17.5.3 The CLI

Four flags, in the style of `option_chain_reader/main.py`: top-level flags on `main.py`, aligned
`label : value` output, `FAIL:` lines carrying the remediation, and a meaningful exit code.

```
python main.py --setup-email       interactive; walks 07 7.2.4's six Gmail prerequisites in
                                   order; writes config/.env and the non-secret half of
                                   config.yaml; refuses to continue past a failed step
python main.py --test-email        connection test only. Sends nothing to anyone except the
                                   account's own address (17.6). Non-interactive, scriptable
python main.py --check-channels    prints ChannelStatus for every channel. Reads nothing but
                                   config and the environment. Always exits 0
python main.py --setup-whatsapp    the phone number and the manual/cloud mode choice (17.8)
```

| Flag | Exit codes | Writes | Network |
|---|---|---|---|
| `--setup-email` | `0` complete; `1` aborted by the user; `2` a prerequisite failed | `config/.env`, `config.yaml`, `config/state/channels.json` | Yes, at steps 7-9 only |
| `--test-email` | `0` all steps passed; `2` a step failed; `3` `EMAIL` is not configured at all | `config/state/channels.json` (`last_verified_at` / `last_error`) | Yes |
| `--check-channels` | `0` always | nothing | No |
| `--setup-whatsapp` | `0` complete; `1` aborted | `config.yaml`; `config/.env` only if `cloud_api` was chosen | No under `manual_link` |

`--check-channels` always exits `0` on purpose. It is a status command, not an assertion; a machine
with nothing configured is a machine in a valid state, and a non-zero exit would make an ordinary
first run look like a failure in any wrapper script.

These four flags are the operator-facing names Sagar asked for. `07` §7.15 already defines a
subcommand surface (`python main.py email preflight`, `email test-send`, `email health`) which stays
and is the deeper tool; `--test-email` is `email preflight` **plus** the plus-address probe of §17.6.3
and the persistence of the result. The overlap is recorded as an amendment request in Open questions.

### 17.5.4 `--setup-email`: the walk, and a sample session

The command walks `07` §7.2.4's six prerequisites **in order**, and refuses to continue past a failed
step. The order is not cosmetic: step 2 must precede step 3, because Google will not offer App
Passwords on an account without 2-Step Verification, and that single dependency is the commonest place
this setup stalls.

| Step | Prompt / action | Failure is fatal | Remediation printed |
|---|---|---|---|
| 0 | Refuse if the repo is under a synced folder; refuse if `config/.env` is world-readable | yes | the exact `icacls` line |
| 1 | "Have you created a dedicated Gmail account for this? (not your personal one)" -> account address | yes | `07` §7.2.6's blast-radius paragraph, condensed to three lines |
| 1b | Validate the local part is ≤ 25 characters | yes | `07` §7.4.2's 64-character arithmetic, with this account's numbers |
| 2 | "Is 2-Step Verification on for that account?" + the URL | yes | `myaccount.google.com/signinoptions/two-step-verification` |
| 3 | App Password, read with `getpass`; spaces stripped; shape validated | yes | where to create one; the 16-character rule |
| 4 | "Is IMAP enabled? (Gmail > See all settings > Forwarding and POP/IMAP)" | no — warn | verified for real at §17.6.2 step 4 |
| 5 | "Is the account's profile display name set to your real name?" | no — warn | it is what appears beside the From address |
| 6 | Plus-addressing probe (§17.6.3) | yes | the whole unsubscribe mechanism depends on it |
| 7 | SMTP test (§17.6.1) | yes | per-failure, from §17.6.3's catalogue |
| 8 | IMAP test (§17.6.2) | yes | per-failure |
| 9 | Write `config/.env` (ACL first), write the non-secret half of `config.yaml`, record the result | yes | — |
| 10 | Print what is still left to do: the ramp, lock 1, lock 2, lock 3 | — | §17.7's checklist, tail end |

**A sample session, including a failure and its remediation.** SAMPLE throughout; the account,
the fingerprint and the timings are invented.

```
D:\Practice_Playwright\business_radar> python main.py --setup-email

business_radar - email channel setup
Follows 07-email-integration.md 7.2.4. Six prerequisites, in order.
Nothing is sent to anybody but your own account. Ctrl-C is safe at any point.

[0/9] Environment
  Repository path      : D:\Practice_Playwright\business_radar   OK (not a synced folder)
  config/.env          : exists, owner-only (R,W)                OK
  Signing secret       : present (fp 3f9a1c02)                   OK

[1/9] The dedicated account
  This must be a NEW Gmail account created for outreach - not the address your
  clients already have. If it is ever suspended, you lose the account and
  nothing else. See 07-email-integration.md 7.2.6.
  Outreach Gmail address: sagar.radar.mail@gmail.com
  Local part           : sagar.radar.mail (16 chars, limit 25)   OK
  Unsub address length : 55 of 64                                OK

[2/9] 2-Step Verification
  An App Password cannot exist without it. This is Google's rule.
  Turn it on at: https://myaccount.google.com/signinoptions/two-step-verification
  Is 2-Step Verification ON for sagar.radar.mail@gmail.com? [y/N]: y

[3/9] App Password
  Create one at https://myaccount.google.com/apppasswords - choose "Mail".
  Google shows 16 characters in four groups; paste them with or without spaces.
  It is shown once and never again.
  App Password (not echoed): ****************
  Length after stripping spaces : 16   Shape : [a-z]{16}         OK
  Fingerprint                   : 8c41ba07

[4/9] IMAP
  Gmail > See all settings > Forwarding and POP/IMAP > Enable IMAP.
  On newer accounts this is on by default and the toggle may not appear.
  Continuing - this is verified for real in step 8.

[5/9] Display name
  Set the account profile name to your real name. It is what recipients see
  beside the From address.
  Is it set? [y/N]: y

[6/9] Plus-addressing probe
  Your entire unsubscribe mechanism is a plus-address on this account
  (07-email-integration.md 7.7.2). If plus-addressing does not work here,
  nobody can ever opt out, and you must find that out now.
  Sending to sagar.radar.mail+radarprobe-9f2c4e1a@gmail.com ...
  SMTP submit          : accepted                                OK
  Waiting for delivery : polling IMAP, up to 120s ...            11s
  Delivered-To header  : sagar.radar.mail+radarprobe-9f2c4e1a@gmail.com
  Tag survived         : yes                                     OK

[7/9] SMTP
  DNS smtp.gmail.com   : 142.250.x.x, 2404:6800:...              OK
  TCP 587              : connected in 84ms                       OK
  EHLO                 : STARTTLS advertised                     OK
  STARTTLS             : TLS1.3, cert valid for smtp.gmail.com   OK
  AUTH LOGIN           : FAILED

FAIL: Gmail rejected the App Password.
  535-5.7.8 Username and Password not accepted.

  This means one of three things, in order of likelihood:
    1. The App Password was mistyped or was copied with a character missing.
       Create a fresh one and try again - they are free and instant.
    2. This App Password was revoked (deleting it in the Google console is
       immediate, and there is no warning here).
    3. You pasted your ACCOUNT password instead of an App Password. Those are
       different things; the account password will never work here.

  Nothing has been written. config/.env is unchanged.
  Re-run: python main.py --setup-email

D:\Practice_Playwright\business_radar> echo %ERRORLEVEL%
2
```

Re-run, second attempt, from step 7 onward:

```
[7/9] SMTP
  DNS / TCP 587 / EHLO / STARTTLS as above                       OK
  AUTH LOGIN           : authenticated as sagar.radar.mail       OK
  MAIL FROM / RCPT TO  : probe to own address accepted, RSET     OK
                         (no message was queued; RSET discards it)
[8/9] IMAP
  TCP 993 / TLS1.3 / LOGIN                                       OK
  SELECT INBOX         : 3 messages, UIDVALIDITY 12              OK
  Sent folder          : [Gmail]/Sent Mail readable, 1 message   OK
[9/9] Writing configuration
  config/.env          : OUTREACH_GMAIL_USER          written
                         OUTREACH_GMAIL_APP_PASSWORD  written (fp 8c41ba07)
  ACL                  : owner-only (R,W) reapplied              OK
  config.yaml          : identity.from_address, identity.unsubscribe_mailbox set
  audit_log            : CONFIG_CHANGED, SECRET_ROTATED (fp none -> 8c41ba07)
  channels.json        : EMAIL last_verified_at 2026-08-27T09:12:04Z

EMAIL is now CREDENTIALED but not LIVE. Three locks are still closed, on purpose:
  lock 1  config.yaml  email.transport: null           -> set to: gmail
  lock 2  config.yaml  email.live_send_enabled: false  -> set to: true
  lock 3  environment  RADAR_EMAIL_LIVE is not set     -> set by run-radar.cmd only

Before you open them (07-email-integration.md 7.4.7 steps 11-13):
  - use the account by hand for 7 days                      [WALL CLOCK]
  - send and reply to 8-10 messages across 5 providers      [3 DAYS]
  - set contact_policy.warmup_started_on to that day        [1 MINUTE]

Until then everything else works. python main.py --check-channels
```

The three properties of that session that are design requirements rather than presentation:

1. **Nothing is written until every fatal step has passed.** A half-written `config/.env` is the
   half-configured state of §17.3.6, and it is worse than no state at all.
2. **The failure message names the three real causes in likelihood order**, and does not say "check
   your credentials". `15` §15.18.3's first rule applied to a terminal.
3. **The command ends by saying what is still not done.** Finishing `--setup-email` does not make the
   system live, and a command that implied otherwise would be the single most dangerous line of output
   in the project.

### 17.5.5 `--check-channels`

```
D:\Practice_Playwright\business_radar> python main.py --check-channels

business_radar - channel status                        2026-08-27T09:14:22Z

CHANNEL    CONFIGURED  MODE           MISSING
EMAIL      no          UNCONFIGURED   OUTREACH_GMAIL_USER, OUTREACH_GMAIL_APP_PASSWORD
WHATSAPP   yes         MANUAL_LINK    -
PHONE      yes         SCRIPT_ONLY    -
MANUAL     yes         CLIPBOARD      -

EMAIL
  Locks     1 config email.transport : null      CLOSED
            2 config email.live_send : false     CLOSED
            3 env    RADAR_EMAIL_LIVE: not set   CLOSED
            4 env    credentials     : 2 missing CLOSED
  Switch    contact_policy.email_enabled  : 1
  Identity  from_address : not set (using rehearsal placeholder)
  Tested    never
  Effect    Drafting, policy checks, previews and approvals all work.
            Transmission is refused at send time by gate B_CHANNEL_UNCONFIGURED.
            Approvals expire after 72h unsent.
  Next      python main.py --setup-email

WHATSAPP
  Mode      manual_link - needs no credentials, no Meta account, no verification.
  Switch    whatsapp_enabled 1   whatsapp_api_enabled 0  (Cloud API stays off - 08)
  Cap       15 manual sends/day
  Signature identity.phone_display : not set. Messages render without a phone
            line. Set it in config.yaml when you have decided which number.
  Effect    Fully usable now. Prepare a message, open the wa.me link, press send.

Nothing here is an error. This is the expected state of a new install.
```

SAMPLE account and figures. Exit code `0`. The last line is not decoration: it is the difference between a new user believing the
install is broken and knowing it is not.

After `--setup-email` but before the locks are opened, the `EMAIL` block changes to
`MISSING email.transport=null, email.live_send_enabled=false, RADAR_EMAIL_LIVE`, `Tested` carries the
timestamp, and `Effect` reads `Credentials are present and verified. Three locks are still closed, so
nothing transmits. This is 07-email-integration.md 7.4.7 step 13.` — rendered in `--warn`, per
§17.3.6's half-configured rule.

### 17.5.6 `--setup-whatsapp`

SAMPLE session; the number and the mode choice are invented.

```
D:\Practice_Playwrightusiness_radar> python main.py --setup-whatsapp

business_radar - WhatsApp channel setup

Mode. v1 is MANUAL_LINK and this is not a placeholder for something better:
business-initiated WhatsApp through the Cloud API needs a pre-approved template
AND a recorded opt-in from the recipient, and almost no business the research
pipeline finds has opted in to anything. See 08-whatsapp-integration.md 8.1.

  [1] manual_link  (default) - the system drafts and checks the message, then
                    gives you a wa.me link. You press send, from your own phone.
                    No Meta account. No token. No business verification.
  [2] cloud_api    - not available in this build. whatsapp_api_enabled is 0 and
                    a database trigger refuses a CLOUD_API dispatch without a
                    live opt-in row.

  Mode [1]: 1

Your own number. This is NOT needed to send anything - the wa.me link carries
the RECIPIENT's number. It is used for one thing: the phone line in the message
signature, shared with email. Leave it blank and set it later if you prefer.

  identity.phone_display (blank to skip): +91 98765 43210
  Parsed as             : +919876543210 (IN, valid)              OK

Which handset. Not enforceable in code, so it is on the record here (08 8.6.7):
  - A dedicated business number on the free WhatsApp Business app. A ban takes
    the whole account, including years of personal chats.
  - Not a number you might later register on the Cloud API: registering
    requires deleting it from the Business app first, irreversibly.
  - Never broadcast lists. That is bulk messaging and it is a ban trigger.

  Acknowledge [y/N]: y

  config.yaml   : identity.phone_display set; whatsapp.mode manual_link (unchanged)
  audit_log     : CONFIG_CHANGED

WHATSAPP is configured. It was already usable before you ran this.
```


### 17.5.7 Settings > Channels

`15-ui-wireframe.md` §15.15's Channels tab, specified here in both states. `OWNER` only, per `13`
§13.3's role matrix; `PUT /api/v1/settings/channels`.

**Unconfigured** (SAMPLE):

```
+------------------------------------------------------------------------------+
| SETTINGS   [ Contact policy ] [ Channels* ] [ Templates ] [ Quota ] [ Jobs ] |
+------------------------------------------------------------------------------+
| EMAIL                                              NOT CONFIGURED     (blue)  |
|  Not configured. Run  python main.py --setup-email  , or fill this in below.  |
|  Still needed:                                                               |
|    [ ] A dedicated Gmail account          (not your personal address)         |
|    [ ] 2-Step Verification on that account                                    |
|    [ ] An App Password for Mail                                               |
|    [x] Unsubscribe signing secret         present (fp 3f9a1c02)               |
|  Gmail account   [                                        ]                  |
|  App Password    [                                        ] (never shown back)|
|                                        [ Save ] [ Test connection ]-         |
|  Channel switch  [x] email_enabled     (this is not the same as configured)   |
|  Transport null lock 1   Live send false lock 2                              |
|  RADAR_EMAIL_LIVE not set lock 3   Credentials 2 missing lock 4                |
|  Last tested     never                                                        |
|  What works right now: research, reports, verification, selection, drafting,  |
|  policy checks, previews and approvals. Approved messages are written to      |
|  data/outbox/unsent/ and are NOT sent. They expire after 72 hours.            |
|  No custom domain. The from-address will be an @gmail.com address, SPF, DKIM  |
|  and DMARC are Google's and cannot be configured, and a spam complaint costs  |
|  the account rather than a domain.                                            |
+------------------------------------------------------------------------------+
| WHATSAPP                                           MANUAL_LINK        (green) |
|  Business-initiated WhatsApp needs a pre-approved template and a recorded     |
|  opt-in. v1 sends wa.me links you open yourself, and needs no credentials.    |
|  Your number in the signature  [ +91 98765 43210        ]                     |
|  Manual cap  15 / day        Cloud API  off (whatsapp_api_enabled = 0)   -    |
+------------------------------------------------------------------------------+
| PHONE   SCRIPT_ONLY  The system never dials. Log the call after you make it.  |
| MANUAL  CLIPBOARD    Copy the approved body and send it yourself.             |
+------------------------------------------------------------------------------+
```

**Configured** (SAMPLE) — the same panel, with the checklist replaced by state:

```
+------------------------------------------------------------------------------+
| EMAIL                                              LIVE               (green) |
|  Gmail account   sagar.radar.mail@gmail.com                                   |
|  App Password    set - fingerprint 8c41ba07 - last used 27 Aug 09:12          |
|                  [ Replace ]   (the value is never displayed)                 |
|  Unsubscribe     sagar.radar.mail+unsub-<token>@gmail.com   55 of 64 chars     |
|                                        [ Save ] [ Test connection ]           |
|  Transport gmail lock 1 OPEN   Live send true lock 2 OPEN                     |
|  RADAR_EMAIL_LIVE yes lock 3 OPEN   Credentials present lock 4 OPEN            |
|  Last tested     27 Aug 2026 09:12 IST - all 11 steps passed                  |
|  Account ramp    day 24 of 42 - today's cap 12 - 7 sent                       |
|  IMAP poll       every 2 min - last successful poll 3 min ago                 |
+------------------------------------------------------------------------------+
```

| Control | Enabled when | When off, it says |
|---|---|---|
| `Save` | `OWNER` session, at least one field changed and valid | `Only the owner can change channel settings.` / `Nothing has changed.` |
| `Test connection` | account and App Password both present (saved or in the form) | `Enter the account and App Password first.` |
| Lock 1 / lock 2 | **read-only in the UI.** Editable only in `config.yaml` | `Set this in config.yaml. It is deliberately not a checkbox.` |
| Lock 3 | read-only, always | `Set by the launcher that starts the service. Nothing here can change it.` |

**What the screen never reveals:**

| Never | Instead |
|---|---|
| The App Password, in any form, to any role including `OWNER` | `set - fingerprint 8c41ba07 - last used <date>`. `12` §12.5.4's fingerprint-only rule |
| `UNSUBSCRIBE_SIGNING_SECRET`, `SUPPRESSION_HMAC_PEPPER`, `WA_ACCESS_TOKEN` | `present (fp ...)` / `missing` |
| A full unsubscribe token | The address shape with `<token>` elided, plus its character count |
| Anything in a `GET` response body | `GET /api/v1/settings/channels` returns `ChannelStatus` objects: booleans, modes, missing *variable names*, timestamps. No value of any secret, ever |
| Anything in an audit row | `CONFIG_CHANGED` carries the field names that changed; `SECRET_ROTATED` carries `fingerprint_before` / `fingerprint_after` (`11` §11.6) |

Lock 1 and lock 2 being read-only in the UI is deliberate and is the point of having four locks rather
than one. `07` §7.3.7's whole design is that going live requires touching four different kinds of
thing in four different places. A `Go live` button on a settings page would collapse three of them
into one click, which is exactly the failure the locks exist to prevent.

---

## 17.6 The connection test

`--test-email` runs eleven steps in a fixed order, prints each with `OK` or `FAILED`, stops at the
first failure, and records the outcome in `config/state/channels.json`. It **sends exactly one
message, to the account's own address**, and it is impossible for it to reach a prospect: the
recipient is computed from `OUTREACH_GMAIL_USER`, never read from the database, and the module does
not import `radar/db.py`.

### 17.6.1 SMTP and IMAP, steps 1-10

| # | Step | Method | Passes when |
|---|---|---|---|
| 1 | DNS | `socket.getaddrinfo(smtp_host, 587)` | At least one A or AAAA record, reported with the addresses — "it resolved to nothing" and "the port is blocked" are different problems with the same symptom |
| 2 | TCP 587 | `socket.create_connection((host, 587), timeout=10)` | Connected, with the handshake time in ms |
| 3 | EHLO / STARTTLS advertised | `smtplib.SMTP.ehlo()`, `'starttls' in esmtp_features` | Advertised. If it is not, we are not talking to Gmail, and continuing would be a downgrade |
| 4 | STARTTLS | `starttls(context=ssl.create_default_context())` | TLS established, certificate valid for `smtp.gmail.com`, hostname matched. Never disabled, not even by a config key (`07` §7.12.4) |
| 5 | AUTH | `login(user, app_password)` | Authenticated. The most informative step; §17.6.3 decodes the codes |
| 6 | Envelope probe | `mail(user)`, `rcpt(user)`, then **`rset()`** | Both accepted, then discarded |
| 7 | TCP 993 | `socket.create_connection((imap_host, 993), timeout=10)` | Connected |
| 8 | TLS | `imaplib.IMAP4_SSL(host, 993, ssl_context=...)` | Certificate valid for `imap.gmail.com`, hostname matched |
| 9 | LOGIN | `.login(user, app_password)` | Authenticated. A `NO` here after a successful step 5 is the IMAP-disabled case |
| 10 | `SELECT INBOX` and the Sent folder | `.select('INBOX', readonly=True)`, then `.select('"[Gmail]/Sent Mail"', readonly=True)` | Both selectable; message counts and `UIDVALIDITY` reported |

Step 6 is the one worth defending. `MAIL FROM` / `RCPT TO` followed by `RSET` completes the envelope
negotiation and then abandons the transaction: the server has confirmed that the sender may submit and
that the recipient is accepted, and no `DATA` was ever sent, so no message exists. The recipient is the
account's **own** address, so even a server that mis-implements `RSET` can only deliver to Sagar.

**A `RCPT TO` probe against a prospect address is forbidden.** It would be a silent, unlogged,
unapproved contact attempt against a stranger's mail server, it appears in their logs, it is what
address-harvesting software does, and it is precisely the behaviour that ends a free Gmail account.
There is no configuration flag that enables it and no code path that constructs one; the probe
function's signature takes no address argument.

Step 10's second half is not optional. `07` §7.10.4 makes the `[Gmail]/Sent Mail` search the **only**
reconciliation available on this stack — no provider API, no webhook — so an account whose Sent folder
is named differently (a non-English Gmail interface names it differently) or is unreadable would leave
every indeterminate send unresolvable. Everything is `readonly=True`: a connection test must not mark
anything read, must not move anything, and must not advance the UID cursor `poll_inbox` depends on.

### 17.6.2 The plus-address probe, step 11

The most important step, and the one that would otherwise be discovered at the worst possible moment.

`07` §7.7 makes the entire unsubscribe mechanism a plus-address on this one account:
`List-Unsubscribe: <mailto:sagar.radar.mail+unsub-<token>@gmail.com?subject=unsubscribe>`. There is no
HTTPS endpoint and no fallback — `_CONTEXT.md` §2 removed both. If plus-addressing is disabled,
rewritten or stripped for this account, **nobody can ever opt out**, and the way Sagar would find out
is a prospect who tried to unsubscribe, could not, and reported the message as spam instead.

| Property | Value |
|---|---|
| What it sends | One plain-text message, from the account, to `<account>+radarprobe-<8 hex>@gmail.com` |
| How it confirms | Polls IMAP `INBOX` (readonly) for up to 120 s, searching `HEADER Subject` for the token |
| What it asserts | (a) the message arrived; (b) its raw source carries `Delivered-To: <account>+radarprobe-<hex>@gmail.com` — **the tag survived** |
| Why (b) matters more than (a) | Delivery proves the mailbox works. Only the surviving tag proves that `apply_unsubscribe()` can resolve a token from an incoming mail, which is what `07` §7.7.7 does |
| Cost | One message against Gmail's 500/24h ceiling. Named in the output so it is not a surprise |
| Cleanup | The probe message is **left in the inbox**, unread and unmoved. Deleting it would need write access; leaving it is one message and it is evidence |
| If it times out | `FAILED`, not `WARNING`. §17.6.3's message |

### 17.6.3 The failure catalogue

Exact server strings where Gmail emits one, and the sentence `--test-email` prints. Every message
names the cause, the fix and where to do it — `15` §15.18.3's rule, applied to a terminal.

| Case | What the server says | What we print |
|---|---|---|
| **2SV not enabled** | `534-5.7.9 Application-specific password required. Learn more at https://support.google.com/mail/?p=InvalidSecondFactor` | `FAIL: this account does not have 2-Step Verification, so App Passwords do not exist for it yet. Turn it on at https://myaccount.google.com/signinoptions/two-step-verification , then create an App Password. This is Google's rule and there is no way round it - it is the single commonest place this setup stalls.` |
| **App Password wrong or revoked** | `535-5.7.8 Username and Password not accepted. Learn more at https://support.google.com/mail/?p=BadCredentials` | `FAIL: Gmail rejected the App Password. Most likely: mistyped or short by a character; or it was revoked in the Google console (that is immediate and silent); or you pasted the ACCOUNT password, which will never work here. Create a fresh App Password - they are free and instant.` |
| **Web login required / account flagged** | `534-5.7.14 <https://accounts.google.com/signin/continue?...> Please log in via your web browser and then try again.` | `FAIL: Google wants a browser sign-in on this account before it will accept SMTP. Open https://mail.google.com , sign in as sagar.radar.mail@gmail.com , clear whatever it asks for, then re-run. This usually means new account, new location, or a security prompt nobody answered.` |
| **IMAP disabled in Gmail settings** | SMTP passes; IMAP `LOGIN` returns `NO [ALERT] Your account is not enabled for IMAP use. Please visit your Gmail settings page and enable your account for IMAP access.` | `FAIL: SMTP works but IMAP is switched off for this account. Gmail > See all settings > Forwarding and POP/IMAP > Enable IMAP > Save. Without it, sending works and NOTHING comes back: no replies, no bounces, and no unsubscribes - which means nobody can opt out. Do not open lock 3 until this passes.` |
| **IMAP credentials rejected while SMTP passed** | `NO [AUTHENTICATIONFAILED] Invalid credentials (Failure)` | `FAIL: SMTP accepted this App Password and IMAP did not, which normally means IMAP access is off rather than the password being wrong. Check the IMAP setting first; if it is already on, create a fresh App Password.` |
| **Sent folder missing or unreadable** | `SELECT "[Gmail]/Sent Mail"` returns `NO` | `FAIL: cannot read [Gmail]/Sent Mail. If this account's Gmail interface is not in English the folder has a different name - set email.sent_folder in config.yaml to the name shown by python main.py email find-sent. Without it, a send whose outcome is unknown can never be resolved (07 7.10.4).` |
| **Port 587 blocked by network** | `TimeoutError` after 10 s, or `ConnectionRefusedError` | `FAIL: could not open TCP 587 to smtp.gmail.com. DNS resolved fine, so this is a network block, not a name problem. Common causes: a corporate or hotel wifi that blocks mail submission ports; a VPN; an antivirus mail-scanning module. Try a phone hotspot to confirm. If 587 is permanently blocked here, port 465 with implicit TLS is equivalent - set email.smtp_port: 465.` |
| **TLS certificate failure** | `ssl.SSLCertVerificationError` | `FAIL: the TLS certificate for smtp.gmail.com did not verify. Something is intercepting this connection - a corporate proxy, an antivirus TLS-inspection module, or worse. This check is never bypassed: submitting through it would hand the App Password to whatever is in the middle. Get off this network.` |
| **Plus-address probe times out** | no failure string; nothing arrives in 120 s | `FAIL: the probe to sagar.radar.mail+radarprobe-9f2c4e1a@gmail.com was accepted for delivery but has not arrived in 120s. Check the account's Spam and All Mail folders by hand. If it is genuinely not there, plus-addressing does not work for this account and the unsubscribe mechanism in 07-email-integration.md 7.7 cannot function. Do not send to anybody until this passes.` |
| **Plus-address probe arrives, tag stripped** | arrives; `Delivered-To:` shows the bare address | `FAIL: the probe arrived but the +radarprobe-9f2c4e1a tag was stripped from Delivered-To. Every unsubscribe depends on reading that tag back (07 7.7.2). Sending would produce an unsubscribe address that cannot be resolved to a message, which is worse than having none. Do not open lock 3.` |
| **Rate-limited during the probe** | `421 4.7.0 Try again later` | `FAIL: Gmail is rate-limiting this account right now. Wait an hour and re-run. If this happens on a brand-new account it usually clears by itself; if it keeps happening, the account is flagged and the ramp in 07 7.4.5 is not optional.` |

Two rules that hold across the whole catalogue:

1. **The credential is never echoed**, not in a success line, not in a failure line, not in a debug
   line. `smtplib.set_debuglevel` is never enabled (`07` §7.12.3: it prints the `AUTH` line verbatim,
   and on this stack that line is the whole mailbox).
2. **Nothing is written to `config/.env` on a failure.** The half-configured state is a state the
   setup command must never create by itself.

---

## 17.7 The order Sagar should do things in

Two columns that matter: **WORK** is time at the keyboard; **WALL** is time that passes whether he
works or not, and it cannot be compressed. The whole point of this table is that the WALL rows can
start while everything else proceeds, and that nothing in phase 1 depends on anything in phase 3.

| Phase | # | Step | Kind | Time |
|---|---|---|---|---|
| **1. Today** | 1 | Clone; `python -m venv`; `pip install -r requirements.txt` | WORK | 10 min |
| | 2 | `cp config.example.yaml config.yaml`; set `identity.sender_name`, `.role`, `.company_name` | WORK | 5 min |
| | 3 | Gemini API key from `aistudio.google.com` into `config/.env` — **the only credential that gates real work** | WORK | 5 min |
| | 4 | `python main.py migrate` — mints the three local secrets (§17.3.5), creates `data/radar.db` | WORK | 1 min |
| | 5 | `python main.py bootstrap-owner --email <sagar>` | WORK | 2 min |
| | 6 | `python main.py doctor` — ACLs, synced-folder check, dependencies | WORK | 1 min |
| | 7 | `python main.py --check-channels` — confirm `EMAIL no / UNCONFIGURED` is the expected state | WORK | 1 min |
| | 8 | `python main.py serve`; log in; run a real campaign on Dhule | WORK | 5 min |
| **2. Start early** | 9 | Create the dedicated Gmail account; local part ≤ 25 characters. **Do this on day one even if sending is a month away** — step 11's clock starts here | WORK | 10 min |
| | 10 | Turn on 2-Step Verification. Blocks the App Password; Google's rule | WORK | 5 min |
| | 11 | **Use the account like a human**: send Sagar ordinary messages, reply from the other side, read them. `07` §7.4.7 step 11 — the only account-age signal we can honestly produce | **WALL** | **7 days** |
| | 12 | Publish the identity page on GitHub Pages; set `identity.site_url` (`07` §7.4.4) | WORK | 30 min |
| | 13 | Decide the WhatsApp number and handset; `python main.py --setup-whatsapp`. Independent of everything else | WORK | 5 min |
| **3. Credentials** | 14 | Create the App Password for Mail. Shown once | WORK | 3 min |
| | 15 | Enable IMAP if the toggle appears. Verified for real at step 17 | WORK | 2 min |
| | 16 | Set the profile display name and photo | WORK | 3 min |
| | 17 | `python main.py --setup-email` — steps 0-9 including the plus-address probe (§17.5.4) | WORK | 10 min |
| | 18 | `python main.py email test-send --to <second address>`; check placement, three auth passes, and **whether the `Message-ID` survived** (`07` §7.4.7 step 9) | WORK | 10 min |
| | 19 | 8-10 messages by hand across Gmail, Outlook.com, Yahoo, Zoho and one M365 tenant; **reply to each**. `07` §7.4.7 step 12 | **WALL** | **3 days** |
| **4. Live** | 20 | `contact_policy.warmup_started_on = today`, by hand. `07` §7.4.5: automatic means a restored backup can silently finish the ramp | WORK | 1 min |
| | 21 | Lock 1: `email.transport: gmail` | WORK | 1 min |
| | 22 | Lock 2: `email.live_send_enabled: true` | WORK | 1 min |
| | 23 | Lock 3: start via `run-radar.cmd`, which sets `RADAR_EMAIL_LIVE=yes`. `python main.py serve` typed by hand still runs null — that asymmetry is the point | WORK | 2 min |
| | 24 | Confirm the boot line: grep `LIVE EMAIL` in the log file under `data/logs/` - it names transport, From, today's cap and ramp day | WORK | 1 min |
| | 25 | Send three. That is the whole of day one — week 1's cap exists so the first categorically wrong message reaches three people, not thirty | — | — |

**At the end of phase 1 the system is fully usable**: research, reports, verification, selection,
drafting, policy checks, previews, approvals, `.eml` files, WhatsApp manual links. Weeks of work live
there. Nothing in phases 2-4 is required for any of it, and phase 2's two WALL rows cost nothing if
step 9 is done on day one.

### The summary Sagar actually needs

| Question | Answer |
|---|---|
| What do I need to start today? | A Gemini API key. Thirty minutes. |
| When must I decide about email? | Never, until you want a stranger to receive something. |
| What is the longest unavoidable wait? | 7 days of ordinary account use (step 11), plus 3 days of the five-receiver test (step 19). Both are wall clock. Start step 9 on day one and they cost you nothing. |
| What does turning email on later break? | Nothing. It adds a capability. Approvals made before it was turned on are not sent (§17.4.5); they expire and are re-approved from a fresh preview. |
| Do I need to configure WhatsApp? | No. §17.8. |

---

## 17.8 WhatsApp specifically

`08-whatsapp-integration.md` §8.2 settles `MANUAL_LINK` as v1: the system drafts the §25 message, runs
it through the same policy engine and the same eligibility gates as email, records the same approval,
and then produces a `wa.me` click-to-chat link. Sagar opens the link and presses send, from his own
phone, in the ordinary WhatsApp UI.

**What `MANUAL_LINK` needs from a configuration file: nothing.**

| Thing | Needed? | Why not |
|---|---|---|
| A Meta / Facebook account; business verification; a WABA | **No** | `wa.me` is a public URL scheme. No account is involved in constructing or opening one, and verification is a Cloud API requirement |
| An access token, an app secret, a phone number id | **No** | `WA_ACCESS_TOKEN`, `WA_APP_SECRET` and `WA_PHONE_NUMBER_ID` are `cloud_api` credentials, commented out in `config/.env` and never read under `manual_link` |
| A webhook endpoint | **No** | And impossible anyway: nothing on the internet reaches `127.0.0.1` |
| An approved message template | **No** | A Cloud API requirement. Manual mode sends fully personalised §25 prose, which is *better* content and only possible because a human sends it |
| **Sagar's own phone number** | **No — not for sending** | The entry everybody gets wrong. `build_wa_link(e164, body)` takes the **recipient's** E.164. Sagar's own number appears nowhere in the link, the URL, or the dispatch path |
| The recipient's phone number | Yes — but it is data, not configuration | From `business_contacts`, captured during research and confirmed at `04`'s verification check 5 |

So **`WHATSAPP` is `configured=True` on a machine that has never had a `config/.env`.** It is the one
channel that is fully available on the first afternoon.

### 17.8.1 What "configure WhatsApp later" actually defers

Three things, none of which is a credential and none of which blocks anything:

| Deferred | What it is | Consequence of deferring | Where |
|---|---|---|---|
| `identity.phone_display` | The phone line in the message **signature**, shared with the email channel | The signature renders **without** a phone line. Not a placeholder, not `+91 XXXXXXXXXX` — the line is omitted. `06`'s rule `P2` exempts `identity.phone_display` from the personal-identifier block, and an empty value simply exempts nothing | `config.yaml`, `identity` |
| Which handset | Whether Sagar uses a dedicated business number on the free WhatsApp Business app, or his personal one | Not enforceable in code. A ban takes the whole account, including years of personal chats — `08` §8.6.7 | `--setup-whatsapp`'s acknowledgement, and `/settings` |
| Which number he will **not** use later for Cloud API | Registering a number on the Cloud API requires deleting it from the WhatsApp Business app first, irreversibly | If he ever wants the API path he needs a second number. Deciding this now costs nothing; discovering it later costs a phone number's chat history | `08` §8.6.7 |

That is genuinely the whole of it. "Configure WhatsApp later" means "decide the phone number later",
and the number in question is for the *signature*, not for the sending.

### 17.8.2 What is not deferred, and never becomes available

| Fact | Detail |
|---|---|
| `CLOUD_API` stays gated regardless of configuration | `contact_policy.whatsapp_api_enabled = 0` by default (lock 2); and even with every lock open, `08` §8.3.9's trigger `RAISE(ABORT)`s any `CLOUD_API` dispatch without a live, unexpired, matching `whatsapp_optins` row for that business and number. That is a database constraint, not a policy setting |
| An opt-in cannot be manufactured by configuring anything | `whatsapp_optins` is append-only, trigger-enforced, and rows are created only from a recorded act by the business |
| Manual mode is lower risk, not zero risk | `08` §8.1.2. WhatsApp's consumer Terms prohibit bulk, automated and unsolicited messaging; a human sending forty cold introductions a day from one number is still doing the thing the ban heuristics look for. `manual_daily_cap: 15` and `whatsapp_max_attempts: 1` are part of the design, not decoration |
| Manual mode obeys every suppression | Gate A is channel-blind (`05` §5.9.3): an opt-out on an email address blocks WhatsApp for that business too. There is no "it is just WhatsApp, it is informal" exemption anywhere |
| Manual mode captures no replies | `08` §8.6.8. Replies arrive on Sagar's phone and are pasted in by hand. That is a real cost of the mode, and configuring something later does not remove it |

---

## 17.9 Re-configuration and rotation

Three distinct operations, with distinct consequences. The invariant that governs all three:

> **A suppression is a fact about the recipient, not about our sender.** It survives every change to
> our account, our credentials and our address. There is no operation in this system that clears a
> suppression, and changing the mailbox is not a loophole.

### 17.9.1 Rotating the App Password — no consequence for history

The address does not change, so nothing in the database refers to anything that moved.

| Affected | Effect |
|---|---|
| `suppressions` | None. Keyed on `value_norm` = the **recipient's** address |
| Outstanding `+unsub-<token>` addresses in already-sent mail | None. Same account, same mailbox, and `UNSUBSCRIBE_SIGNING_SECRET` is untouched |
| In flight | `05` §5.19: an auth failure leaves the message `QUEUED`, so nothing is lost across the swap |

Procedure: `12` §12.5.5's nine steps, unchanged, with one insertion — step 5 becomes
`python main.py --test-email` rather than `email preflight`, so the plus-address probe re-runs and
`last_verified_at` is refreshed. **Step 7 (revoke the old App Password in the Google console) is the
step that constitutes the rotation**, and it is the one that gets skipped; `python main.py doctor`
reports any `SECRET_ROTATED` row for an App Password without an operator confirmation of revocation
within 24 hours.

### 17.9.2 Changing the Gmail account — the address moves, the history does not

This is the interesting one. It happens for two reasons: the account was suspended (`07` §7.2.8's
fallback), or Sagar simply wants a different address.

| Affected | Effect | Ruling |
|---|---|---|
| `suppressions` | **Survive, entirely.** Every row is keyed on the recipient's `value_norm` | Nothing to migrate. Gate A behaves identically the day after the change |
| `outreach_messages`, `outreach_events`, `responses`, `handoffs`; §29 duplicate protection, §31 frequency, §32 history, §36-§38 aggregates; `businesses.status` | **Survive.** All of them are about the recipient | Nothing to migrate |
| **Replies to already-sent messages** | **Break.** Every sent message's `Reply-To` is `<old-account>+msg_<ulid>@gmail.com`, a mailbox we no longer poll | §17.9.3 |
| **Outstanding unsubscribe addresses** | **Break, and this is worse.** Every `List-Unsubscribe` ever sent points at `<old-account>+unsub-<token>@gmail.com`. A recipient trying to opt out reaches a mailbox nobody reads | §17.9.3 |
| `UNSUBSCRIBE_SIGNING_SECRET` | Keep it. Tokens derive from `(message_id, to_address_norm)`, not from our account | Rotating it here breaks token resolution for no benefit |
| `identity.from_address`, `identity.unsubscribe_mailbox` | Change | `--setup-email` rewrites both |
| The account ramp | **Restarts at day 1.** `warmup_started_on = today` | `07` §7.2.8: the new account is a brand-new account, and the throwaway-spam-account shape is what the ramp guards against |
| `07` §7.2.8's honest caveat | Applies | Whatever behaviour closed the first account will close the second. The correct response to a closure is to find which of `07` §7.2.5's expiry conditions broke |

### 17.9.3 The decommission window

The two broken items above are both "a stranger sends mail to an address we abandoned", and one of
them is the unsubscribe mechanism, which `_CONTEXT.md` §4 requires to be reliable. So an account is
not switched off; it is **retired over a window**.

```yaml
email:
  legacy_mailboxes:                 # 17.9.3. Polled read-only during a decommission window.
    - user:        sagar.radar.old@gmail.com     # SAMPLE
      env_prefix:  LEGACY_GMAIL_1   # LEGACY_GMAIL_1_USER / _APP_PASSWORD in config/.env
      retire_after: 2027-02-27      # 180 days after the switch
```

| Rule | Value | Why |
|---|---|---|
| Window length | **180 days**, default | Longer than `response.match_days` (60) and long enough for an unsubscribe from an old message to arrive. An unsubscribe has no expiry from the recipient's side |
| What runs against a legacy mailbox | `poll_inbox` **only**, readonly. Unsubscribe ingest, reply attribution, DSN parsing | Everything inbound |
| What never runs against a legacy mailbox | Any send. `build_transport()` never constructs a transport for a legacy entry, and `_LIVE` has no entry for one | It is a listening post, not a sender |
| The old App Password | **Not revoked until the window closes.** This is an explicit, documented exception to `12` §12.5.5's "revoke immediately" | A revoked credential means an unsubscribe from an old message is never read, which is worse than a live read-only credential on a mailbox containing nothing new |
| The exception's limit | If the account change was caused by a **compromise**, revoke immediately and accept the loss. Record it as an incident (`12` §12.14.1) | A stolen credential outranks an unsubscribe window |
| When the window closes | `retire_after` passes; the entry is removed; the App Password is revoked; a `CONFIG_CHANGED` audit row records it | — |
| Warning | From 30 days before `retire_after`, the daily report and `/settings` say `The old mailbox sagar.radar.old@gmail.com stops being polled on 27 Feb 2027. After that, unsubscribe mails sent to it are not read.` | It is a deadline nobody would otherwise remember |

Amendment request to `07` §7.8.4, whose IMAP poller reads exactly one mailbox today.

### 17.9.4 What is never permitted

| Never | Because |
|---|---|
| Clearing a suppression by changing the sending account, or re-contacting "because the old messages went from a different address" | Invariant 3: opt-out is absolute and permanent, clearable only by a manual DB operation with an audit row. Gate A does not read our address and never will |
| Re-running the ramp from a later day because "the pipeline is warm" | Ramp state is per account. A new account is day 1 |
| Reusing the old address later | `07` §7.10.7's dedupe folds `+tag` and gmail dots; more importantly a resurrected address with a suspension history is the worst of both |
| Copying `config/.env` from the old machine to a new one and starting | Lock 3 is not in `config/.env`. That is the lock's entire purpose (`07` §7.3.7) |

---

## 17.10 Tests

`tests/test_channel_configuration.py` unless noted. No network in any of them; `conftest.py` already
asserts `email.transport == "null"` and unsets `RADAR_EMAIL_LIVE` (`12` §12.6).

**The four the requirement names.**

| # | Test | Asserts |
|---|---|---|
| 1 | `test_fresh_install_empty_env_boots_and_serves` | With only `GEMINI_API_KEY` in `config/.env`: `create_app()` returns, `GET /` is 200, `GET /api/v1/health` reports `channels[EMAIL].configured == false`, and **no exception is raised** — asserted by a logging handler that fails the test on any `ERROR` record other than the four expected lock lines |
| 2 | `test_full_pipeline_to_approved_with_no_channel_configured` | Discovery -> research -> score -> report -> verify -> select -> draft -> policy -> preview -> approve, all green. `outreach_messages.status == 'APPROVED'`; one `outreach_approvals` row with non-null `approved_body_hash` and `session_auth_method='PASSWORD_TOTP'`; one `OUTREACH_APPROVED` audit row; `data/outbox/unsent/<date>/<msg_id>.eml` exists and parses with `email.parser` |
| 3 | `test_send_with_no_channel_configured_is_refused_informatively` | `POST /api/v1/outreach/messages/<id>/send` returns `409` with `blocking_code == 'B_CHANNEL_UNCONFIGURED'` and the specialised sentence; **`COUNT(*) FROM outreach_messages WHERE status IN ('QUEUED','SENT','DELIVERED')` is 0**; `businesses.status` still `CONTACT_READY`; `campaigns.n_contacted` 0; no `OUTREACH_SENT` audit row |
| 4 | `test_configuring_a_channel_transmits_nothing_approved_earlier` | Approve 5 unconfigured, assert 5 `.eml` under `unsent/`; open all four locks, `refresh()`, run the worker 10 s; assert zero `send_email` jobs were ever enqueued, zero rows left `APPROVED`, and the five files are byte-identical |

**Detection, status and the gate.**

| # | Test | Asserts |
|---|---|---|
| 5 | `test_status_with_no_config_block_at_all` | No `email:` and no `whatsapp:` key: four statuses, `EMAIL` `UNCONFIGURED`, `WHATSAPP` `MANUAL_LINK`, no exception |
| 6 | `test_each_lock_alone_leaves_email_unconfigured` | Four cases, three locks open and one closed: `configured is False` every time, `missing` names the closed lock |
| 7 | `test_all_four_locks_open_is_configured` | `configured is True`, `mode == 'GMAIL_LIVE'` |
| 8 | `test_whatsapp_manual_link_needs_no_credentials` | `WA_*` absent: `configured is True`, `mode == 'MANUAL_LINK'`, `missing` empty |
| 9 | `test_status_cache_invalidation` | `PUT /api/v1/settings/channels` replaces the cached object; a simulated `535` during a send does **not** |
| 10 | `test_channels_json_holds_no_secret` | After a failed test the file holds the error sentence and no substring of the App Password, the user, or any 16-lowercase run |
| 11 | `test_b3_blocks_only_at_send_stage` | `SELECT` not evaluated; `PREVIEW` present but not `BLOCK`; `SEND` `BLOCK` |
| 12 | `test_b3_does_not_preempt_gate_a` | Suppressed business, `EMAIL` unconfigured: `blocking_code == 'A_SUPPRESSED_EMAIL'`, B3 a later `BLOCK` in `gates` |
| 13 | `test_b3_does_not_preempt_verification_or_contact_gates` | Same, for `D_NOT_VERIFIED` and `E_CONTACT_MISSING` |
| 14 | `test_gate_catalogue_is_forty` | 40 gate results, precedence order matching `05` §5.9.1 verbatim |
| 15 | `test_block_reason_single_source` (extends `15` §15.18.3) | Keys still equal the gate codes; `B_CHANNEL_UNCONFIGURED` present; no template hardcodes a string |
| 16 | `test_grid_carries_no_b_codes` | `GET /api/v1/campaigns/<id>/selectable` with `EMAIL` unconfigured returns rows `selectable = true` where they otherwise would be, and no `B_` code anywhere |

**Approvals, the outbox, setup and surfaces.**

| # | Test | Asserts |
|---|---|---|
| 17 | `test_approval_unconfigured_writes_a_real_row` | Every non-null column populated identically to the configured case; `approved_body_hash` matches the hash of the approved subject and body |
| 18 | `test_approval_unconfigured_does_not_queue` | No `jobs` row with `kind='send_email'` after approval |
| 19 | `test_shelf_life_expires_at_72h_not_before` | 71 h 59 m: `APPROVED`. 72 h 01 m: `CANCELLED`, `revoke_reason='APPROVAL_EXPIRED_UNSENT'`, one `APPROVAL_REVOKED` event, one audit row |
| 20 | `test_expiry_leaves_the_draft_current` | `superseded_by IS NULL`; gate F1 no longer blocks; a new message can be created from the same draft |
| 21 | `test_outbox_is_write_only` | An AST scan of `radar/`: no read, `glob` or `iterdir` resolving under `cfg.paths.outbox_dir`, except `NullEmailTransport`'s write and the retention purge |
| 22 | `test_unsent_eml_carries_the_marker_headers` | `X-Radar-Outbox-Reason: CHANNEL_UNCONFIGURED` and `X-Radar-Transmitted: no` present; `T10` refuses to transmit a message carrying either |
| 23 | `test_unsent_eml_from_address_is_invalid_tld` | With no identity, `From` ends `@localhost.invalid` |
| 24 | `test_live_transport_refuses_placeholder_identity` | `assert_transport_declared()` raises `ConfigError` when `is_live` and the from-address ends `.invalid` |
| 25 | `test_rehearsal_requires_a_recipient_allowlist` | `rehearsal: true` with an empty allowlist raises `ConfigError` at boot |
| 26 | `test_rehearsal_blocks_a_non_allowlisted_recipient` | Gate B3 blocks with the rehearsal sentence; nothing is written |
| 27 | `test_rehearsal_rows_excluded_from_report_aggregates` | A `provider='null'` `SENT` row is absent from the §36 `Sent` figure and the §37 comparison |
| 28 | `test_setup_email_writes_nothing_on_a_failed_step` | Fake SMTP refusing `AUTH`: `config/.env` byte-identical before and after; exit code 2 |
| 29 | `test_setup_email_input_validation` | A 30-character local part is refused with the 64-character arithmetic; an App Password pasted with spaces is stored as 16 characters; a path containing `OneDrive` is refused, naming the path |
| 30 | `test_test_email_never_targets_a_prospect` | The module does not import `radar/db.py`; the probe function accepts no address argument; the recipient equals `OUTREACH_GMAIL_USER` |
| 31 | `test_test_email_uses_rset_not_data` | Against a recording fake server: `MAIL FROM`, `RCPT TO`, `RSET`, and **no `DATA`** |
| 32 | `test_failure_catalogue_covers_every_documented_code` | Each §17.6.3 server string maps to its sentence; an unmapped code falls back to one that still names the step |
| 33 | `test_no_credential_in_any_output` | Every line printed and every log record emitted by the three commands is searched for the App Password, the Gemini key and the signing secret. Zero hits |
| 34 | `test_settings_channels_reveals_no_secret` | The `GET` body, searched recursively, holds no secret value; `OWNER` required and `OPERATOR` gets 403; after a `PUT` the subsequent `GET` returns a fingerprint and no value |
| 35 | `test_poll_inbox_not_scheduled_when_unconfigured` | No `poll_inbox` entry in the registry; exactly one `INFO` line explains why; no `ERROR` in 60 simulated seconds |
| 36 | `test_report_chip_when_approved_and_unconfigured` | The HTML holds `Approved - email not configured` linking to `/settings#channels`, and no transmit control (extends `03`'s `test_export_has_no_form_no_post_no_secret`) |
| 37 | `test_dashboard_sent_figure_is_em_dash_not_zero` | Figure 8 renders an em dash when nothing has been sent and email is unconfigured |
| 38 | `test_signature_omits_phone_line_when_unset` | With `identity.phone_display` empty the body holds no `+91`, no `XXXX`, and no empty signature line |

---

## Open questions

**Amendment requests.** Each names the file and the change; none has been made by this document.

| # | File | Change |
|---|---|---|
| 1 | `05-outreach-workflow.md` §5.9.1, §5.9.4, §5.9.12 | Add gate `B3` / `B_CHANNEL_UNCONFIGURED` immediately after `B2`, `SEND` stage only, hard. Gate count 39 -> 40 in §5.9.12's payload note. Extend §5.9.4's "gate B is campaign-wide rather than per-row" paragraph: B3 is machine-wide and renders as one banner, not N tooltips |
| 2 | `05-outreach-workflow.md` §5.3.1 + `contact_policy` DDL | Add `approval_shelf_life_hours INTEGER NOT NULL DEFAULT 72 CHECK (approval_shelf_life_hours >= 1)`, and the `revoke_reason` value `APPROVAL_EXPIRED_UNSENT`. Needs a migration number from `01-data-model.md` §1.13.2 — `058`, since `07` has taken the sequence to `057`. The `APPROVED -> CANCELLED` transition already exists and needs no change |
| 3 | `14-background-jobs.md` §14.9 | Register the nightly `expire_approvals` job (§17.4.3) with catch-up-on-launch semantics: after four days off it runs once, not four times, and it runs **before** the day's first `send_email` so a worker that started first cannot transmit a stale approval. Same ordering argument as `07` §7.7.7 rule 2's "poll before send", applied to a different staleness |
| 4 | `07-email-integration.md` §7.3.8, §7.6.4 | Add the `.invalid` from-address check to `assert_transport_declared()`, and transport check `T10`: a built message whose `From` ends `.invalid`, or which carries `X-Radar-Transmitted: no` / `X-Radar-Outbox-Reason`, may never be transmitted by a live transport |
| 5 | `07-email-integration.md` §7.14, §7.15 | Add `email.rehearsal`, `email.rehearsal_recipients`, `email.unsent_dir`, `email.legacy_mailboxes` to the config block. Add §17.5.3's four operator flags to the CLI list, recording that `--test-email` is `email preflight` plus §17.6.2's probe plus persistence, and that the other three are new |
| 6 | `07-email-integration.md` §7.8.4 | The IMAP poller reads one mailbox. §17.9.3 needs a list: the live mailbox plus zero or more read-only legacy mailboxes, each with its own UID cursor in `config/state/`, and sending strictly impossible from a legacy entry |
| 7 | `08-whatsapp-integration.md` §8.8.1 | Add `whatsapp.mode: manual_link` as lock 1. It is currently implicit — `MANUAL_LINK` is documented as v1 and default but no config key names it, which makes it undetectable by `radar/channels/status.py` |
| 8 | `12-security-model.md` §12.5.1, §12.5.4, §12.5.5 | Record that `UNSUBSCRIBE_SIGNING_SECRET`, `SUPPRESSION_HMAC_PEPPER` and `AUDIT_EXPORT_HMAC_KEY` are **minted locally on first run** (§17.3.5), not operator-supplied. Add §17.9.3's decommission-window exception to the "revoke immediately" rule, with the compromise case explicitly excluded from the exception |
| 9 | `13-api-endpoints.md` §13.15 | `GET /api/v1/settings/channels` returns a `statuses[]` array of `ChannelStatus` objects alongside the existing switches; `GET /api/v1/health` carries the same array (§17.3.6). Confirm the `OWNER`-only role on the `GET` — the `missing` list names environment variables |
| 10 | `15-ui-wireframe.md` §15.8, §15.10, §15.15, §15.18.3 | Replace the Channels tab paragraph with §17.5.7's wireframes; add `B_CHANNEL_UNCONFIGURED` to `BLOCK_REASON`; add the `APPROVED - NOT SENT` and `RETIRED` bands to the outreach workspace; add §17.3.6's confirm-dialog variant |
| 11 | `03-html-report.md` §3.8.3 and `15-ui-wireframe.md` §15.3.2 | Add the `Approved - email not configured` chip state, and exclude `provider = 'null'` rows from every `Sent` / `Contacted` aggregate so a rehearsal never appears in a report as outreach (§17.4.6) |
| 12 | `16-mvp-plan.md` (not yet written) | Define milestone 5 as "everything except transmission, with `email.transport: null`" and milestone 6 as the live send with one recipient — `07` §7.3.9 already says both, and §17.7 is written against that. §17.7's checklist belongs in that plan: its two WALL rows are the only unavoidable delays in the whole build |

**Genuinely unsettled.**

13. **Should the plus-address probe repeat on a schedule?** It proves the unsubscribe mechanism
    works *today*. If Google changed plus-address handling for this account tomorrow, the path would
    fail silently and the first symptom would be a spam complaint. A periodic self-probe catches it,
    at one message against the daily ceiling. Leaning monthly, folded into `email health`.

14. **72 hours, or the end of the next working day?** The alternative — "18:30 IST on the second
    working day after approval" — is more natural for a person and handles the Friday-evening case
    exactly rather than approximately, at the cost of being harder to test and explain. Left at 72
    hours, flagged because Sagar is the only user.

15. **`identity.reply_to` versus `identity.from_address`.** `06` §6.14 uses the first, `07` §7.14 the
    second, for the same account. This document populates both from one value and treats
    `from_address` as canonical, but one of the two documents should rename. `07` records it in its
    own Open questions; noted here because `--setup-email` writes both and is what breaks if their
    meanings diverge.

16. **Whether an unconfigured `EMAIL` should suppress draft generation to save Gemini quota.**
    Drafting forty messages that cannot be sent for three weeks spends free-tier requests research
    could have used. The counter-argument is that reading those forty drafts is the entire value of
    milestone 5. Decided in favour of drafting, but the lever exists: `06`'s draft job could refuse
    when `ChannelStatus.unconfigured` **and** the campaign has more than N unsent approvals. Not
    implemented; recorded so it is not re-derived from scratch later.
