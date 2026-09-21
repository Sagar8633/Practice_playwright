"""The human gate. Nothing the AI discovered may be contacted until a person signs for it here.

The whole system exists to make one thing impossible: a message going out because a model was
confident. Research produces a business, a score and a page of findings, and every one of those
is a machine's opinion. This module is where a human reads them, answers nine questions one at
a time, and puts a signature on the answer. Without it `businesses.status` would be a field the
research pipeline sets, and "verified" would mean "the pipeline finished".

Three things live here, and they are separate on purpose.

`set_status()` is the only writer of `businesses.status` in the codebase. Every transition is
checked against `business_status_transitions` in Python before the database trigger checks it
again, so a violation surfaces as a sentence naming the T-number rather than as a bare
IntegrityError in a log file. Two layers is not belt and braces here: the trigger is the layer
that cannot be bypassed, this one is the layer a human can read.

`submit_verification()` writes the nine-item checklist from spec section 16. All nine must pass
to reach VERIFIED; any single "no" routes to REJECTED with a mandatory reason code. There is
deliberately no "eight of nine with a note" outcome, because within a month the common case
becomes eight ticks and a free-text apology, and the nine-check gate has quietly become an
eight-check gate. The escape valve for "I cannot answer this today" is SKIP, which is one
click, needs no reason and is fully reversible. Making rejection strict is only defensible
because parking is cheap.

`contact_ready_predicate()` answers the second question, which is not the same as the first.
VERIFIED asks "did a human sign this research?"; CONTACT_READY asks "given that signature, may
outreach begin today?". They go wrong for different reasons and are repaired by different
people. Collapsing them means either an opt-out silently deletes Sagar's signature - and
re-earning it costs nine checks that produce the same nine answers, which is the fastest route
to a rubber stamp - or the grid shows a green badge for a business nobody may ever contact.
So a broken clause demotes CONTACT_READY -> VERIFIED and the signature survives untouched.

The predicate never reimplements a gate. It reads `radar.eligibility.check_send_eligibility()`
and maps gate codes onto clauses, because two implementations of "is this business suppressed"
is how a system ends up with a grid that says yes and a send path that says no.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Mapping, Sequence

from . import db
from .audit import audit
from .eligibility import (
    Eligibility,
    check_send_eligibility,
    effective_policy,
    live_suppressions,
)
from .ids import new_id
from .models import (
    ActorKind,
    BusinessStatus,
    Verdict,
    VERIFICATION_CHECK_KEYS,
    parse_ts,
    utc_now,
)

log = logging.getLogger("radar.verify")


class VerifyError(RuntimeError):
    """Something about this verification is wrong and the write must not happen."""


class TransitionError(VerifyError):
    """A businesses.status move that the transition table does not allow."""


class ChecklistError(VerifyError):
    """The nine answers are malformed, incomplete, or disagree with the verdict."""


# ===========================================================================
# The nine checks (spec section 16)
# ===========================================================================


@dataclass(frozen=True)
class CheckDef:
    """One row of the checklist, as it appears on screen and in verification_checks."""

    key: str
    ordinal: int
    prompt: str
    helper: str
    zone: str
    source_visit_required: bool
    default_reason: str


#: The nine items, in the order they are asked. The prompt column is spec section 16's wording,
#: unedited, so the spec stays quotable; `helper` carries the elaboration.
CHECK_DEFS: tuple[CheckDef, ...] = (
    CheckDef("IDENTITY_CORRECT", 1, "Business identity appears correct",
             "The name, the legal entity and the address describe one real trading entity, and "
             "it is the one the research is about.",
             "Z2", True, "NOT_A_REAL_BUSINESS"),
    CheckDef("IN_TARGET_CITY", 2, "Business is located in target city",
             "A branch in a campaign city whose head office is elsewhere is in scope.",
             "Z2", False, "WRONG_CITY"),
    CheckDef("CATEGORY_CORRECT", 3, "Business category is correct",
             "The wrong category produces the wrong pitch. Correcting the category and "
             "re-queueing is usually better than rejecting.",
             "Z2", False, "WRONG_CATEGORY"),
    CheckDef("APPEARS_OPERATIONAL", 4, "Business appears operational",
             "Trading now, not a shell, not shut. Recent evidence beats an old listing.",
             "Z4", True, "CLOSED"),
    CheckDef("CONTACT_LEGITIMATE", 5,
             "Contact information appears to be a legitimate business contact",
             "The address or number belongs to the business itself, not to a directory, an "
             "aggregator or somebody else entirely.",
             "Z3", True, "CONTACT_NOT_LEGITIMATE"),
    CheckDef("RESEARCH_RELEVANT", 6, "Research is relevant",
             "The findings survive opening the sources they cite.",
             "Z4", True, "RESEARCH_UNRELIABLE"),
    CheckDef("OPPORTUNITY_REASONABLE", 7, "Software opportunity appears reasonable",
             "A management system would plausibly help an operation of this size and shape.",
             "Z5", False, "TOO_SMALL"),
    CheckDef("OUTREACH_APPROPRIATE", 8, "Outreach is appropriate",
             "Nothing about this business, sector or moment makes a cold approach wrong.",
             "Z5", False, "OTHER"),
    CheckDef("NO_DNC_RECORD", 9, "No do-not-contact record exists",
             "The machine's suppression answer is shown beside this box and is deliberately "
             "not ticked for you. What this item asks about is the record that lives in your "
             "memory, your inbox, or a conversation at a wedding.",
             "Z6", False, "DO_NOT_CONTACT"),
)

CHECK_BY_KEY: dict[str, CheckDef] = {d.key: d for d in CHECK_DEFS}

if tuple(d.key for d in CHECK_DEFS) != VERIFICATION_CHECK_KEYS:  # pragma: no cover - import guard
    raise ImportError(
        "radar/verify.py CHECK_DEFS has drifted from models.VERIFICATION_CHECK_KEYS; the "
        "database CHECK constraint follows models.py, so one of the two is now unwritable"
    )


@dataclass(frozen=True)
class CheckAnswer:
    """One answer, with the note a failure is required to carry."""

    passed: bool
    note: str | None = None
    evidence_ref: str | None = None

    @classmethod
    def coerce(cls, value: Any) -> CheckAnswer:
        if isinstance(value, CheckAnswer):
            return value
        if isinstance(value, bool):
            return cls(passed=value)
        if isinstance(value, Mapping):
            return cls(
                passed=bool(value.get("passed")),
                note=value.get("note"),
                evidence_ref=value.get("evidence_ref"),
            )
        raise ChecklistError(
            f"a check answer must be a bool, a CheckAnswer or a mapping, got {type(value).__name__}"
        )


# ===========================================================================
# set_status - the only writer of businesses.status
# ===========================================================================


def allowed_transitions(conn: sqlite3.Connection, from_status: str,
                        actor_kind: str | None = None) -> list[sqlite3.Row]:
    """Every move the table permits out of this status, for the operator's error message."""
    if actor_kind is None:
        return conn.execute(
            "SELECT to_status, actor_kind, ref, note FROM business_status_transitions "
            " WHERE from_status = ? ORDER BY ref",
            (from_status,),
        ).fetchall()
    return conn.execute(
        "SELECT to_status, actor_kind, ref, note FROM business_status_transitions "
        " WHERE from_status = ? AND actor_kind = ? ORDER BY ref",
        (from_status, actor_kind),
    ).fetchall()


def _actor_kind_of(actor: str | None) -> str:
    """A usr_ actor is a person; anything else is the machine acting on its own."""
    return ActorKind.HUMAN.value if (actor or "").startswith("usr_") else ActorKind.SYSTEM.value


def set_status(
    conn: sqlite3.Connection,
    business_id: str,
    new_status: str,
    actor: str | None,
    reason: str,
    *,
    verification_id: str | None = None,
    skip_reason: str | None = None,
    detail: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> bool:
    """The only writer of businesses.status in the codebase. Returns True if it moved.

    Reads the current status inside the caller's transaction, checks the pair against
    business_status_transitions in Python so the error can name the T-number and list what is
    actually reachable, performs the UPDATE with the actor columns set in the same statement -
    the triggers read NEW.status_actor_kind, so a writer that forgot it would be refused - and
    writes the BUSINESS_STATUS_CHANGED audit row.

    The database triggers are the real enforcement. This function exists so a violation reaches
    a human as a readable sentence rather than as sqlite3.IntegrityError.
    """
    now_iso = now or utc_now()
    actor_kind = _actor_kind_of(actor)

    with db.transaction(conn):
        row = conn.execute(
            "SELECT id, name, status, status_verification_id FROM businesses WHERE id = ?",
            (business_id,),
        ).fetchone()
        if row is None:
            raise VerifyError(f"no businesses row for {business_id!r}")
        current = row["status"]
        if current == new_status:
            return False
        if new_status not in {s.value for s in BusinessStatus}:
            raise TransitionError(f"{new_status!r} is not a business lifecycle status")

        move = conn.execute(
            """
            SELECT ref, note FROM business_status_transitions
             WHERE from_status = ? AND to_status = ? AND actor_kind = ?
            """,
            (current, new_status, actor_kind),
        ).fetchone()
        if move is None:
            reachable = ", ".join(
                f"{r['to_status']} ({r['ref']})"
                for r in allowed_transitions(conn, current, actor_kind)
            ) or "nothing"
            raise TransitionError(
                f"{row['name'] or business_id} is {current} and a {actor_kind} actor cannot "
                f"move it to {new_status}; from {current} a {actor_kind} actor may reach: "
                f"{reachable}"
            )

        conn.execute(
            """
            UPDATE businesses
               SET status                 = :status,
                   status_actor_kind      = :actor_kind,
                   status_actor_user_id   = :actor_user_id,
                   status_verification_id = COALESCE(:verification_id, status_verification_id),
                   skip_reason            = CASE WHEN :status = 'SKIPPED' THEN :skip_reason
                                                 ELSE skip_reason END,
                   contact_ready_at       = CASE WHEN :status = 'CONTACT_READY' THEN :now
                                                 WHEN :was = 'CONTACT_READY' THEN NULL
                                                 ELSE contact_ready_at END
             WHERE id = :id
            """,
            {
                "status": new_status,
                "actor_kind": actor_kind,
                "actor_user_id": actor if actor_kind == ActorKind.HUMAN.value else None,
                "verification_id": verification_id,
                "skip_reason": skip_reason,
                "now": now_iso,
                "was": current,
                "id": business_id,
            },
        )

        payload = {"reason": reason, "transition": move["ref"], "note": move["note"]}
        if detail:
            payload.update(dict(detail))
        audit(
            conn,
            actor,
            "BUSINESS_STATUS_CHANGED",
            "businesses",
            business_id,
            before={"status": current},
            after={"status": new_status},
            business_id=business_id,
            detail=payload,
        )
    log.info("business %s %s -> %s (%s, %s)", business_id, current, new_status,
             move["ref"], reason)
    return True


# ===========================================================================
# The checklist screen payload
# ===========================================================================


@dataclass(frozen=True)
class ChecklistItem:
    """One check as the screen renders it, with anything the machine already knows."""

    definition: CheckDef
    machine_answer: bool | None = None
    machine_note: str | None = None
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_key": self.definition.key,
            "ordinal": self.definition.ordinal,
            "prompt": self.definition.prompt,
            "helper": self.definition.helper,
            "zone": self.definition.zone,
            "source_visit_required": self.definition.source_visit_required,
            "machine_answer": self.machine_answer,
            "machine_note": self.machine_note,
            "evidence_ids": list(self.evidence_ids),
        }


def checklist_for(conn: sqlite3.Connection, business_id: str) -> list[ChecklistItem]:
    """The nine items, with item 9's machine answer attached but deliberately not ticked.

    Item 9 is the only check the system can pre-compute, and auto-ticking it would make the
    checklist agree with the send path by construction and prove nothing: it is the same
    suppression query that runs at send time. What item 9 actually asks about is the record the
    query cannot see.
    """
    hits = live_suppressions(conn, business_id)
    items: list[ChecklistItem] = []
    for definition in CHECK_DEFS:
        if definition.key != "NO_DNC_RECORD":
            items.append(ChecklistItem(definition))
            continue
        if hits:
            note = "; ".join(
                f"{h['scope']} {h['display']} suppressed on {(h['created_at'] or '')[:10]} "
                f"({h['reason']})"
                for h in hits
            )
            items.append(ChecklistItem(definition, machine_answer=False, machine_note=note,
                                       evidence_ids=tuple(h["id"] for h in hits)))
        else:
            items.append(ChecklistItem(
                definition,
                machine_answer=True,
                machine_note="No live suppression and no prior opt-out on file for this business.",
            ))
    return items


# ===========================================================================
# Opening a verification
# ===========================================================================


def open_verification(
    conn: sqlite3.Connection,
    business_id: str,
    user_id: str,
    *,
    campaign_id: str | None = None,
    mode: str = "FULL",
    trigger_reason: str = "INITIAL",
    dwell_required_ms: int = 20_000,
    session_id: str | None = None,
    now: str | None = None,
) -> str:
    """Open (or resume) the draft checklist for this business and return its ver_ id.

    Idempotent per business: `ux_verifications_draft` allows one draft at a time, so a second
    call resumes the first rather than starting a parallel checklist whose answers would race.

    `started_at` on the draft is the clock the dwell floor is measured against at submit, and
    it is the server's clock rather than the browser's for the obvious reason.
    """
    now_iso = now or utc_now()
    with db.transaction(conn):
        business = conn.execute(
            "SELECT id, name, status, merged_into_id, research_fingerprint, contact_fingerprint "
            "  FROM businesses WHERE id = ?",
            (business_id,),
        ).fetchone()
        if business is None:
            raise VerifyError(f"no businesses row for {business_id!r}")
        if business["merged_into_id"]:
            raise VerifyError(
                f"{business['name']} was merged into {business['merged_into_id']}; verify that "
                f"row instead"
            )

        existing = conn.execute(
            "SELECT id FROM verifications WHERE business_id = ? AND state = 'DRAFT'",
            (business_id,),
        ).fetchone()
        if existing is not None:
            return existing["id"]

        # AI_RESEARCHED means the pipeline finished and nobody has looked yet. Moving it into
        # the queue is T01 and it is the system's own move, not the operator's.
        if business["status"] == BusinessStatus.AI_RESEARCHED:
            set_status(conn, business_id, BusinessStatus.NEEDS_VERIFICATION.value,
                       "open_verification", "research complete and qualified", now=now_iso)

        run = conn.execute(
            """
            SELECT id FROM research_runs
             WHERE business_id = ? AND status = 'COMPLETE'
             ORDER BY finished_at DESC LIMIT 1
            """,
            (business_id,),
        ).fetchone()
        prior = conn.execute(
            """
            SELECT id FROM verifications
             WHERE business_id = ? AND state = 'SUBMITTED' AND superseded_at IS NULL
             ORDER BY created_at DESC LIMIT 1
            """,
            (business_id,),
        ).fetchone()

        ver_id = new_id("ver")
        conn.execute(
            """
            INSERT INTO verifications
                (id, business_id, campaign_id, state, mode, dwell_required_ms, trigger_reason,
                 prior_verification_id, research_run_id, research_fingerprint,
                 contact_fingerprint, session_id, started_at, created_at)
            VALUES (:id, :business_id, :campaign_id, 'DRAFT', :mode, :dwell_required_ms,
                    :trigger_reason, :prior_id, :run_id, :research_fp, :contact_fp,
                    :session_id, :now, :now)
            """,
            {
                "id": ver_id,
                "business_id": business_id,
                "campaign_id": campaign_id,
                "mode": mode,
                "dwell_required_ms": max(0, int(dwell_required_ms)),
                "trigger_reason": trigger_reason,
                "prior_id": prior["id"] if prior else None,
                "run_id": run["id"] if run else None,
                "research_fp": research_fingerprint(conn, business_id),
                "contact_fp": contact_fingerprint(conn, business_id),
                "session_id": session_id,
                "now": now_iso,
            },
        )
        audit(conn, user_id, "VERIFICATION_STARTED", "verifications", ver_id,
              after={"business_id": business_id, "mode": mode, "trigger": trigger_reason},
              business_id=business_id, campaign_id=campaign_id)
    log.info("verification %s opened for %s by %s", ver_id, business_id, user_id)
    return ver_id


# ===========================================================================
# Submitting
# ===========================================================================


@dataclass(frozen=True)
class SubmitResult:
    """What the submit did, so the caller does not have to re-read four tables to find out."""

    verification_id: str
    business_id: str
    verdict: str
    business_status: str
    readiness: ContactReadiness | None
    reason_code: str | None = None
    suppression_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "business_id": self.business_id,
            "verdict": self.verdict,
            "business_status": self.business_status,
            "reason_code": self.reason_code,
            "suppression_id": self.suppression_id,
            "readiness": self.readiness.to_dict() if self.readiness else None,
        }


def submit_verification(
    conn: sqlite3.Connection,
    business_id: str,
    user_id: str,
    checks: Mapping[str, Any],
    note: str | None = None,
    *,
    verification_id: str | None = None,
    campaign_id: str | None = None,
    contact_id_confirmed: str | None = None,
    reason_code: str | None = None,
    reason_note: str | None = None,
    sources_visited: Sequence[str] = (),
    sources_waived: Sequence[str] = (),
    now: str | None = None,
) -> SubmitResult:
    """Freeze the nine answers, sign them, and move the business where they say it belongs.

    All nine must pass to reach VERIFIED. Any single "no" routes to REJECTED with a mandatory
    reason code, defaulted from the first failed check and overridable. `note` becomes
    `why_note`: for a VERIFIED verdict the database requires at least fifteen characters of it,
    because a signature with no sentence behind it is the artefact of a rubber stamp.

    Everything is validated before BEGIN IMMEDIATE. Inside the transaction the order is fixed:
    freeze the checks, supersede the prior live verification, submit this one, then move the
    status - the status trigger reads the verification row, so submitting after the status
    change would abort, and superseding after submitting would collide with the partial unique
    index that keeps "is this business verified" a question with one answer.
    """
    now_iso = now or utc_now()

    business = conn.execute(
        "SELECT id, name, status, merged_into_id FROM businesses WHERE id = ?", (business_id,)
    ).fetchone()
    if business is None:
        raise VerifyError(f"no businesses row for {business_id!r}")

    user = conn.execute(
        "SELECT id, role, disabled_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        raise VerifyError(f"no users row for {user_id!r}: a verification needs a real signature")
    if user["disabled_at"]:
        raise VerifyError(f"user {user_id} is disabled and may not verify anything")

    answers = _coerce_checks(checks)
    failed = [key for key in VERIFICATION_CHECK_KEYS if not answers[key].passed]
    verdict = Verdict.REJECTED.value if failed else Verdict.VERIFIED.value

    if verdict == Verdict.REJECTED.value:
        reason_code = reason_code or CHECK_BY_KEY[failed[0]].default_reason
        # The note on the failed check already says why. Asking for it twice is how an
        # operator learns to type "see above" into the second box.
        reason_note = reason_note or answers[failed[0]].note
        reason = conn.execute(
            "SELECT code, requires_note, writes_suppression, suppression_reason, is_permanent "
            "  FROM verification_reason_codes WHERE code = ?",
            (reason_code,),
        ).fetchone()
        if reason is None:
            raise ChecklistError(
                f"{reason_code!r} is not a verification reason code; "
                f"see verification_reason_codes"
            )
        if reason["requires_note"] and len((reason_note or "").strip()) < 10:
            raise ChecklistError(
                f"reason {reason_code} requires a note of at least 10 characters"
            )
    else:
        reason = None
        if len((note or "").strip()) < 15:
            raise ChecklistError(
                "a VERIFIED verdict needs a why-note of at least 15 characters saying what "
                "convinced you"
            )

    ver_id = verification_id or open_verification(
        conn, business_id, user_id, campaign_id=campaign_id, now=now_iso
    )
    verification = conn.execute(
        "SELECT * FROM verifications WHERE id = ?", (ver_id,)
    ).fetchone()
    if verification is None:
        raise VerifyError(f"no verifications row for {ver_id!r}")
    if verification["state"] != "DRAFT":
        raise VerifyError(
            f"verification {ver_id} is {verification['state']}, not a draft; open a new one"
        )
    if verification["business_id"] != business_id:
        raise VerifyError(f"verification {ver_id} does not belong to {business_id}")

    started = parse_ts(verification["started_at"]) or parse_ts(now_iso)
    ended = parse_ts(now_iso)
    dwell_ms = int(max(0.0, (ended - started).total_seconds() * 1000)) if started and ended else 0
    required_ms = verification["dwell_required_ms"] or 0
    if verdict == Verdict.VERIFIED.value and dwell_ms < required_ms:
        raise ChecklistError(
            f"this checklist has been open {dwell_ms} ms and the floor is {required_ms} ms; "
            f"read the sources before signing"
        )

    contact_id = None
    if verdict == Verdict.VERIFIED.value:
        blocks = live_suppressions(conn, business_id)
        if blocks:
            raise VerifyError(
                f"{business['name']} carries a live suppression "
                f"({blocks[0]['scope']}, {blocks[0]['reason']}); it cannot be verified for "
                f"outreach"
            )
        contact_id = _resolve_confirmed_contact(conn, business_id, contact_id_confirmed)

    with db.transaction(conn):
        _freeze_checks(conn, ver_id, business_id, user_id, answers, now_iso)
        superseded = _supersede_prior(conn, business_id, ver_id, user_id,
                                      "REJECTED" if failed else "REVERIFY", now_iso)
        conn.execute(
            """
            UPDATE verifications
               SET state         = 'SUBMITTED',
                   verdict       = :verdict,
                   checks_passed = :passed,
                   checks_failed = :failed,
                   reason_code   = :reason_code,
                   reason_note   = :reason_note,
                   why_note      = :why_note,
                   dwell_ms      = :dwell_ms,
                   sources_visited = :sources_visited,
                   sources_waived  = :sources_waived,
                   verified_by   = :user_id,
                   verified_at   = :now,
                   note          = :note
             WHERE id = :id
            """,
            {
                "verdict": verdict,
                "passed": 9 - len(failed),
                "failed": len(failed),
                "reason_code": reason_code if failed else None,
                "reason_note": reason_note if failed else None,
                "why_note": (note or "").strip() or None,
                "dwell_ms": dwell_ms,
                "sources_visited": json.dumps(list(sources_visited)),
                "sources_waived": json.dumps(list(sources_waived)),
                "user_id": user_id,
                "now": now_iso,
                "note": (note or "").strip() or None,
                "id": ver_id,
            },
        )
        audit(conn, user_id, "VERIFICATION_SUBMITTED", "verifications", ver_id,
              after={"verdict": verdict, "checks_failed": len(failed),
                     "reason_code": reason_code, "dwell_ms": dwell_ms},
              business_id=business_id, campaign_id=campaign_id,
              detail={"failed_checks": failed, "superseded": superseded})

        suppression_id = None
        readiness: ContactReadiness | None = None
        if verdict == Verdict.VERIFIED.value:
            if contact_id:
                _confirm_contact(conn, contact_id, user_id, now_iso)
            set_status(conn, business_id, BusinessStatus.VERIFIED.value, user_id,
                       "the nine checks passed", verification_id=ver_id, now=now_iso)
            readiness = refresh_contact_readiness(conn, business_id, campaign_id=campaign_id,
                                                  now=now_iso)
        else:
            suppression_id = _apply_rejection(conn, business_id, ver_id, user_id, reason,
                                              reason_note, now_iso)

        status = conn.execute(
            "SELECT status FROM businesses WHERE id = ?", (business_id,)
        ).fetchone()["status"]

    log.info("verification %s submitted %s for %s; business is %s",
             ver_id, verdict, business_id, status)
    return SubmitResult(
        verification_id=ver_id,
        business_id=business_id,
        verdict=verdict,
        business_status=status,
        readiness=readiness,
        reason_code=reason_code if failed else None,
        suppression_id=suppression_id,
    )


def _coerce_checks(checks: Mapping[str, Any]) -> dict[str, CheckAnswer]:
    """Exactly the nine keys, each with a note where the answer is "no"."""
    if not isinstance(checks, Mapping):
        raise ChecklistError("checks must be a mapping of check_key -> answer")
    supplied = set(checks)
    expected = set(VERIFICATION_CHECK_KEYS)
    if supplied != expected:
        missing = sorted(expected - supplied)
        unknown = sorted(supplied - expected)
        parts = []
        if missing:
            parts.append(f"missing {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown {', '.join(unknown)}")
        raise ChecklistError(
            f"the checklist is all nine items or nothing: {'; '.join(parts)}"
        )
    answers: dict[str, CheckAnswer] = {}
    for key in VERIFICATION_CHECK_KEYS:
        answer = CheckAnswer.coerce(checks[key])
        if not answer.passed and len((answer.note or "").strip()) < 10:
            raise ChecklistError(
                f"{key} was answered no and needs a note of at least 10 characters saying why; "
                f'"no" without a reason is the same as no answer'
            )
        answers[key] = answer
    return answers


def _freeze_checks(conn: sqlite3.Connection, ver_id: str, business_id: str, user_id: str,
                   answers: Mapping[str, CheckAnswer], now_iso: str) -> None:
    conn.execute("DELETE FROM verification_checks WHERE verification_id = ?", (ver_id,))
    for definition in CHECK_DEFS:
        answer = answers[definition.key]
        conn.execute(
            """
            INSERT INTO verification_checks
                (id, verification_id, business_id, check_key, ordinal, passed, note,
                 evidence_ref, answered_at, answered_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id("chk"), ver_id, business_id, definition.key, definition.ordinal,
             1 if answer.passed else 0, (answer.note or "").strip() or None,
             answer.evidence_ref, now_iso, user_id),
        )


def _supersede_prior(conn: sqlite3.Connection, business_id: str, new_ver_id: str | None,
                     actor: str | None, reason: str, now_iso: str) -> list[str]:
    """Retire any live verification so the partial unique index stays satisfiable.

    `new_ver_id` is NULL when nothing replaces the retired signature - a staleness demotion
    withdraws it without a successor, and pointing superseded_by at anything other than a real
    verifications row would break the foreign key that makes the chain readable later.
    """
    rows = conn.execute(
        """
        SELECT id FROM verifications
         WHERE business_id = ? AND state = 'SUBMITTED' AND superseded_at IS NULL
           AND (? IS NULL OR id <> ?)
        """,
        (business_id, new_ver_id, new_ver_id),
    ).fetchall()
    superseded: list[str] = []
    for row in rows:
        conn.execute(
            """
            UPDATE verifications
               SET superseded_at = ?, superseded_by = ?, superseded_reason = ?
             WHERE id = ?
            """,
            (now_iso, new_ver_id, reason, row["id"]),
        )
        audit(conn, actor, "VERIFICATION_SUPERSEDED", "verifications", row["id"],
              after={"superseded_by": new_ver_id, "reason": reason},
              business_id=business_id)
        superseded.append(row["id"])
    return superseded


def _resolve_confirmed_contact(conn: sqlite3.Connection, business_id: str,
                               contact_id: str | None) -> str | None:
    """Which contact did check 5 confirm? Ambiguity is refused rather than guessed at."""
    if contact_id is not None:
        row = conn.execute(
            "SELECT id, business_id, is_active FROM business_contacts WHERE id = ?",
            (contact_id,),
        ).fetchone()
        if row is None or row["business_id"] != business_id:
            raise VerifyError(f"{contact_id!r} is not a contact of {business_id}")
        if not row["is_active"]:
            raise VerifyError(f"{contact_id!r} is deactivated and cannot be confirmed")
        return contact_id

    rows = conn.execute(
        """
        SELECT id FROM business_contacts
         WHERE business_id = ? AND is_active = 1 AND valid = 1
           AND kind IN ('EMAIL','PHONE','WHATSAPP')
         ORDER BY is_primary DESC, created_at
        """,
        (business_id,),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise VerifyError(
            f"{business_id} has {len(rows)} active contacts; pass contact_id_confirmed to say "
            f"which one check 5 confirmed"
        )
    return rows[0]["id"]


def _confirm_contact(conn: sqlite3.Connection, contact_id: str, user_id: str,
                     now_iso: str) -> None:
    conn.execute(
        """
        UPDATE business_contacts
           SET human_verified = 1, human_verified_at = ?, human_verified_by = ?, updated_at = ?
         WHERE id = ?
        """,
        (now_iso, user_id, now_iso, contact_id),
    )
    audit(conn, user_id, "CONTACT_VERIFIED", "business_contacts", contact_id,
          after={"human_verified": True})


def _apply_rejection(conn: sqlite3.Connection, business_id: str, ver_id: str, user_id: str,
                     reason: sqlite3.Row, reason_note: str | None,
                     now_iso: str) -> str | None:
    """Reject the business, and write the suppression that makes "permanent" mean something."""
    set_status(conn, business_id, BusinessStatus.REJECTED.value, user_id,
               f"verification rejected: {reason['code']}", verification_id=ver_id,
               detail={"reason_code": reason["code"]}, now=now_iso)

    if not reason["writes_suppression"]:
        return None
    existing = conn.execute(
        """
        SELECT id FROM suppressions
         WHERE scope = 'BUSINESS' AND value_norm = ? AND released_at IS NULL
        """,
        (business_id,),
    ).fetchone()
    if existing is not None:
        return existing["id"]
    sup_id = new_id("sup")
    conn.execute(
        """
        INSERT INTO suppressions
            (id, scope, value_norm, business_id, reason, source, source_ref, detail,
             created_at, created_by)
        VALUES (?, 'BUSINESS', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sup_id, business_id, business_id, reason["suppression_reason"],
         f"verification rejection {reason['code']}", ver_id,
         json.dumps({"reason_code": reason["code"], "note": reason_note}),
         now_iso, user_id),
    )
    audit(conn, user_id, "SUPPRESSION_CREATED", "suppressions", sup_id,
          after={"scope": "BUSINESS", "reason": reason["suppression_reason"]},
          business_id=business_id,
          detail={"reason_code": reason["code"], "permanent": bool(reason["is_permanent"])})
    log.warning("business %s permanently suppressed by verification reason %s",
                business_id, reason["code"])
    return sup_id


# ===========================================================================
# The contact-ready predicate
# ===========================================================================

CLAUSES: tuple[str, ...] = (
    "C1_VERIFIED_FRESH",
    "C2_NOT_JUDGED",
    "C3_CONTACT_USABLE",
    "C4_NO_SUPPRESSION",
    "C5_FREQUENCY_OPEN",
    "C6_RESEARCH_USABLE",
    "C7_CONFIDENCE_ADEQUATE",
)

#: Which eligibility gates decide each clause. A BLOCK on any listed gate fails the clause; a
#: SKIP - a gate that could not be evaluated without a contact and a channel - is not a failure.
#: Adding a gate to the engine changes the predicate only if its code is added here.
#:
#: DEVIATION from 04-verification-workflow.md section 4.3.4, deliberately: that table maps
#: D_NOT_VERIFIED onto C1, and gate D1 blocks for any status outside the CONTACT_READY family -
#: which includes VERIFIED, the status every promotion starts from. Reading it here would make
#: C1 permanently false and CONTACT_READY unreachable. D_VERIFICATION_STALE already blocks when
#: no live verification exists, so C1 loses nothing by leaving D1 out.
CLAUSE_GATES: dict[str, tuple[str, ...]] = {
    "C1_VERIFIED_FRESH": ("D_VERIFICATION_STALE", "D_CHECKLIST_INCOMPLETE"),
    "C2_NOT_JUDGED": ("D_VERIFICATION_REVOKED", "D_HUMAN_OWNED"),
    "C3_CONTACT_USABLE": ("E_CONTACT_MISSING",),
    "C4_NO_SUPPRESSION": ("A_SUPPRESSED_BUSINESS", "A_SUPPRESSED_EMAIL", "A_SUPPRESSED_PHONE",
                          "A_SUPPRESSED_WHATSAPP", "A_SUPPRESSED_DOMAIN"),
    "C5_FREQUENCY_OPEN": ("G_MIN_DAYS", "G_SNOOZED", "G_MAX_ATTEMPTS",
                          "G_STOP_AFTER_REJECTION", "G_STOP_AFTER_OPT_OUT",
                          "F_RECENT_CAMPAIGN"),
    "C6_RESEARCH_USABLE": ("C_RESEARCH_INCOMPLETE", "C_NO_SOURCED_FINDINGS", "C_NO_OPPORTUNITY"),
    "C7_CONFIDENCE_ADEQUATE": ("C_CONFIDENCE_LOW",),
}

#: Where a broken clause sends the business. Only C1 and C6 withdraw the signature; everything
#: else demotes to VERIFIED and leaves it untouched, which is the whole point of two states.
CLAUSE_DEMOTES_TO: dict[str, str | None] = {
    "C1_VERIFIED_FRESH": BusinessStatus.NEEDS_VERIFICATION.value,
    "C2_NOT_JUDGED": None,
    "C3_CONTACT_USABLE": BusinessStatus.VERIFIED.value,
    "C4_NO_SUPPRESSION": BusinessStatus.VERIFIED.value,
    "C5_FREQUENCY_OPEN": BusinessStatus.VERIFIED.value,
    "C6_RESEARCH_USABLE": BusinessStatus.NEEDS_VERIFICATION.value,
    "C7_CONFIDENCE_ADEQUATE": BusinessStatus.VERIFIED.value,
}


@dataclass(frozen=True)
class ClauseResult:
    clause: str
    ok: bool
    gate: str | None = None
    sentence: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"clause": self.clause, "ok": self.ok, "gate": self.gate,
                "sentence": self.sentence, "detail": self.detail}


@dataclass(frozen=True)
class ContactReadiness:
    """Should this business be in the outreach pool at all, today?"""

    business_id: str
    evaluated_at: str
    policy_version: str
    ok: bool
    failing_clause: str | None
    blocking_code: str | None
    blocking_sentence: str | None
    clauses: tuple[ClauseResult, ...]
    demote_to: str | None

    def clause(self, name: str) -> ClauseResult | None:
        return next((c for c in self.clauses if c.clause == name), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "evaluated_at": self.evaluated_at,
            "policy_version": self.policy_version,
            "ok": self.ok,
            "failing_clause": self.failing_clause,
            "blocking_code": self.blocking_code,
            "blocking_sentence": self.blocking_sentence,
            "demote_to": self.demote_to,
            "clauses": [c.to_dict() for c in self.clauses],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def contact_ready_predicate(
    conn: sqlite3.Connection,
    business_id: str,
    *,
    campaign_id: str | None = None,
    now: str | None = None,
    eligibility: Eligibility | None = None,
) -> ContactReadiness:
    """Answer "should this business be in the outreach pool at all, today?".

    Read-only. Evaluates all seven clauses on every call - no short circuit - so the screen can
    show every reason at once instead of one per refresh. C1 is evaluated first so `demote_to`
    is unambiguous: a stale or missing signature sends the business back to NEEDS_VERIFICATION,
    and every other broken clause sends it back to VERIFIED with the signature intact.

    The clauses are read from `check_send_eligibility(stage='SELECT')` rather than recomputed
    here. Two implementations of "is this business suppressed" is how a system ends up with a
    grid that says yes and a send path that says no.
    """
    now_iso = now or utc_now()
    elig = eligibility or check_send_eligibility(
        conn, business_id, None, None, stage="SELECT", campaign_id=campaign_id,
        now=now_iso, require_transaction=False,
    )
    by_code = {g.code: g for g in elig.gates}

    clauses: list[ClauseResult] = []
    for clause in CLAUSES:
        blocked = None
        for code in CLAUSE_GATES[clause]:
            gate = by_code.get(code)
            if gate is not None and gate.blocks:
                blocked = gate
                break
        if blocked is None:
            clauses.append(ClauseResult(clause, True))
        else:
            clauses.append(ClauseResult(clause, False, blocked.code, blocked.sentence,
                                        dict(blocked.detail)))

    failing = next((c for c in clauses if not c.ok), None)
    return ContactReadiness(
        business_id=business_id,
        evaluated_at=now_iso,
        policy_version=elig.policy_version,
        ok=failing is None,
        failing_clause=failing.clause if failing else None,
        blocking_code=failing.gate if failing else None,
        blocking_sentence=failing.sentence if failing else None,
        clauses=tuple(clauses),
        demote_to=CLAUSE_DEMOTES_TO[failing.clause] if failing else None,
    )


# The set-based form of the same question. It is an indexed pre-filter for the nightly sweep and
# for the grid, NOT a second implementation: every decision to write businesses.status is taken
# by contact_ready_predicate() above. Keeping the authority in one place is worth the extra
# query the sweep pays to confirm each candidate.
#
# SIMPLIFIED: 04-verification-workflow.md section 4.3.3 makes this a per-(campaign, business)
# view over v_effective_policy and campaign_businesses. Neither the view nor a campaign-scoped
# policy merge exists in SQL here, so the scan is per business against the GLOBAL policy, bound
# as parameters. A campaign whose policy is stricter than GLOBAL will surface its extra
# demotions through the Python predicate the sweep calls per row.
CONTACT_READY_SCAN_SQL = """
WITH ver AS (
    SELECT v.business_id, v.id AS verification_id, v.verified_at
      FROM verifications v
     WHERE v.state = 'SUBMITTED' AND v.verdict = 'VERIFIED' AND v.superseded_at IS NULL
       AND v.checks_passed = 9 AND v.checks_failed = 0
),
usable_contact AS (
    SELECT c.business_id, COUNT(*) AS n
      FROM business_contacts c
     WHERE c.human_verified = 1 AND c.is_active = 1 AND c.valid = 1
       AND c.value_norm IS NOT NULL AND c.value_norm <> ''
       AND (c.is_role_address = 1 OR c.source_ref IS NOT NULL OR c.source_url IS NOT NULL
            OR c.source_id IS NOT NULL)
       AND ( (c.kind = 'EMAIL'    AND :email_enabled = 1)
          OR (c.kind = 'PHONE'    AND (:phone_enabled = 1 OR :manual_enabled = 1))
          OR (c.kind = 'WHATSAPP' AND :whatsapp_enabled = 1) )
     GROUP BY c.business_id
),
suppressed AS (
    SELECT DISTINCT b.id AS business_id
      FROM businesses b
      LEFT JOIN business_contacts c ON c.business_id = b.id
      JOIN suppressions s
        ON s.released_at IS NULL
       AND ( (s.scope = 'BUSINESS' AND s.value_norm = b.id)
          OR (s.scope = 'DOMAIN'   AND s.value_norm IN (c.domain, b.website_domain))
          OR (s.scope IN ('EMAIL','PHONE','WHATSAPP')
              AND s.scope      = c.kind
              AND s.value_norm = c.value_norm
              AND (s.reason <> 'BOUNCE_HARD' OR c.is_active = 1)) )
),
hist AS (
    SELECT m.business_id,
           MAX(m.sent_at) AS last_sent_at,
           COUNT(*)       AS attempts
      FROM outreach_messages m
     WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
     GROUP BY m.business_id
),
stopper AS (
    SELECT r.business_id, MIN(r.received_at) AS at
      FROM responses r
     WHERE COALESCE(r.human_classification, r.classification)
           IN ('NOT_INTERESTED','ALREADY_HAVE_SOFTWARE','OPT_OUT','COMPLAINT')
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
           (SELECT COUNT(*) FROM research_runs rr
             WHERE rr.business_id = b.id AND rr.status = 'COMPLETE')          AS complete_runs,
           (SELECT COUNT(*) FROM research_findings f
              JOIN finding_sources fs ON fs.finding_id = f.id
             WHERE f.business_id = b.id AND f.kind = 'OBSERVED')              AS observed_sourced,
           (SELECT o.id FROM opportunities o
             WHERE o.business_id = b.id AND o.is_current = 1)                 AS opportunity_id,
           (SELECT o.confidence FROM opportunities o
             WHERE o.business_id = b.id AND o.is_current = 1)                 AS opportunity_confidence
      FROM businesses b
)
SELECT b.id                                          AS business_id,
       b.name,
       b.status,
       ver.verification_id,
       ver.verified_at,
       CASE WHEN ver.verification_id IS NOT NULL
             AND ver.verified_at >= :verification_cutoff THEN 1 ELSE 0 END    AS c1_verified_fresh,
       CASE WHEN b.status IN ('REJECTED','SKIPPED','INTERESTED','HUMAN_HANDOFF')
            THEN 0 ELSE 1 END                                                AS c2_not_judged,
       CASE WHEN COALESCE(uc.n, 0) > 0 THEN 1 ELSE 0 END                      AS c3_contact_usable,
       CASE WHEN sup.business_id IS NULL THEN 1 ELSE 0 END                    AS c4_no_suppression,
       CASE WHEN COALESCE(h.attempts, 0) < :max_attempts
             AND (h.last_sent_at IS NULL OR h.last_sent_at < :frequency_cutoff)
             AND st.business_id IS NULL
             AND (sn.until IS NULL OR sn.until <= :now)
            THEN 1 ELSE 0 END                                                AS c5_frequency_open,
       CASE WHEN r.complete_runs > 0 AND r.observed_sourced > 0
             AND r.opportunity_id IS NOT NULL THEN 1 ELSE 0 END               AS c6_research_usable,
       CASE WHEN r.opportunity_confidence IS NOT NULL THEN 1 ELSE 0 END       AS c7_confidence_adequate
  FROM businesses b
  LEFT JOIN ver            ON ver.business_id = b.id
  LEFT JOIN usable_contact uc ON uc.business_id = b.id
  LEFT JOIN suppressed     sup ON sup.business_id = b.id
  LEFT JOIN hist           h  ON h.business_id  = b.id
  LEFT JOIN stopper        st ON st.business_id = b.id
  LEFT JOIN snooze         sn ON sn.business_id = b.id
  LEFT JOIN res            r  ON r.business_id  = b.id
 WHERE b.merged_into_id IS NULL
   AND b.status IN ('VERIFIED','CONTACT_READY')
 ORDER BY ver.verified_at
 LIMIT :limit
"""


def scan_contact_ready(conn: sqlite3.Connection, *, limit: int = 500,
                       now: str | None = None) -> list[sqlite3.Row]:
    """One indexed pass over the businesses whose pool membership could have changed."""
    now_iso = now or utc_now()
    policy = effective_policy(conn)
    return conn.execute(CONTACT_READY_SCAN_SQL, {
        "now": now_iso,
        "limit": limit,
        "email_enabled": 1 if policy.email_switch_on else 0,
        "phone_enabled": 1 if policy.phone_enabled else 0,
        "manual_enabled": 1 if policy.manual_enabled else 0,
        "whatsapp_enabled": 1 if policy.whatsapp_enabled else 0,
        "max_attempts": policy.max_attempts,
        "verification_cutoff": _shift_days(now_iso, -policy.verification_valid_days),
        "frequency_cutoff": _shift_days(now_iso, -policy.min_days_between_outreach),
    }).fetchall()


def _shift_days(now_iso: str, days: int) -> str:
    moment = parse_ts(now_iso)
    if moment is None:
        raise VerifyError(f"not one of our timestamps: {now_iso!r}")
    return (moment + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ===========================================================================
# Promotion, demotion, and the one entry point that decides which
# ===========================================================================


def promote_contact_ready(conn: sqlite3.Connection, business_id: str, *,
                          readiness: ContactReadiness | None = None,
                          campaign_id: str | None = None,
                          now: str | None = None) -> bool:
    """VERIFIED -> CONTACT_READY (T09) when the predicate holds. Promotion only, never demotion.

    Idempotent: called on a business that is already CONTACT_READY it re-stamps nothing and
    returns False.
    """
    now_iso = now or utc_now()
    with db.transaction(conn):
        state = conn.execute(
            "SELECT status FROM businesses WHERE id = ?", (business_id,)
        ).fetchone()
        if state is None:
            raise VerifyError(f"no businesses row for {business_id!r}")
        if state["status"] != BusinessStatus.VERIFIED:
            return False
        check = readiness or contact_ready_predicate(conn, business_id,
                                                     campaign_id=campaign_id, now=now_iso)
        if not check.ok:
            return False
        moved = set_status(conn, business_id, BusinessStatus.CONTACT_READY.value,
                           "refresh_contact_readiness", "the contact-ready predicate holds",
                           now=now_iso)
        conn.execute(
            """
            UPDATE businesses
               SET contact_ready_block_code = NULL, contact_ready_checked_at = ?
             WHERE id = ?
            """,
            (now_iso, business_id),
        )
        if moved:
            audit(conn, None, "CONTACT_READY_GRANTED", "businesses", business_id,
                  after={"status": BusinessStatus.CONTACT_READY.value},
                  business_id=business_id, campaign_id=campaign_id,
                  detail={"policy_version": check.policy_version})
    return moved


def revoke_contact_ready(conn: sqlite3.Connection, business_id: str, *,
                         readiness: ContactReadiness,
                         campaign_id: str | None = None,
                         now: str | None = None) -> bool:
    """Demote to wherever the broken clause says the business belongs, and clean up after it.

    CONTACT_READY -> VERIFIED (T14) keeps the signature; -> NEEDS_VERIFICATION (T15, or T10
    from VERIFIED) withdraws it and supersedes the verification row, because C1 and C6 are the
    only clauses whose failure means the human's answer is no longer about the current world.

    Live selections move to REMOVED and messages still in PENDING_APPROVAL move to CANCELLED.
    APPROVED and QUEUED messages are deliberately left alone: they are re-checked by
    check_send_eligibility(stage='SEND') inside the send transaction, which is the only reader
    holding the write lock and therefore the only one that can close that race. Cancelling them
    from out here would either miss a message a worker has already claimed or deadlock with it.
    """
    if readiness.ok or readiness.demote_to is None:
        return False
    now_iso = now or utc_now()

    with db.transaction(conn):
        state = conn.execute(
            "SELECT status FROM businesses WHERE id = ?", (business_id,)
        ).fetchone()
        if state is None:
            raise VerifyError(f"no businesses row for {business_id!r}")
        current = state["status"]
        target = readiness.demote_to
        if current not in (BusinessStatus.CONTACT_READY, BusinessStatus.VERIFIED):
            return False
        if current == target:
            conn.execute(
                "UPDATE businesses SET contact_ready_block_code = ?, contact_ready_checked_at = ?"
                " WHERE id = ?",
                (readiness.blocking_code, now_iso, business_id),
            )
            return False

        if target == BusinessStatus.NEEDS_VERIFICATION:
            _supersede_prior(conn, business_id, None, None, "STALE", now_iso)

        moved = set_status(conn, business_id, target, "refresh_contact_readiness",
                           f"contact-ready clause {readiness.failing_clause} broke",
                           detail={"blocking_code": readiness.blocking_code}, now=now_iso)
        conn.execute(
            """
            UPDATE businesses
               SET contact_ready_block_code = ?, contact_ready_checked_at = ?
             WHERE id = ?
            """,
            (readiness.blocking_code, now_iso, business_id),
        )
        removed = _withdraw_pending_outreach(conn, business_id, readiness, now_iso)
        if moved:
            audit(conn, None, "CONTACT_READY_REVOKED", "businesses", business_id,
                  before={"status": current}, after={"status": target},
                  business_id=business_id, campaign_id=campaign_id,
                  detail={"failing_clause": readiness.failing_clause,
                          "blocking_code": readiness.blocking_code, **removed})
    return moved


def _withdraw_pending_outreach(conn: sqlite3.Connection, business_id: str,
                               readiness: ContactReadiness, now_iso: str) -> dict[str, int]:
    selections = conn.execute(
        """
        SELECT id, campaign_id FROM selections
         WHERE business_id = ? AND state <> 'REMOVED'
        """,
        (business_id,),
    ).fetchall()
    for row in selections:
        conn.execute(
            "UPDATE selections SET state = 'REMOVED', removed_at = ?, updated_at = ?,"
            "       blocking_gate = ? WHERE id = ?",
            (now_iso, now_iso, readiness.blocking_code, row["id"]),
        )
        audit(conn, None, "SELECTION_REMOVED", "selections", row["id"],
              after={"state": "REMOVED"}, business_id=business_id,
              campaign_id=row["campaign_id"],
              detail={"blocking_code": readiness.blocking_code})

    messages = conn.execute(
        """
        SELECT id, campaign_id FROM outreach_messages
         WHERE business_id = ? AND status IN ('DRAFT','POLICY_BLOCKED','PENDING_APPROVAL')
        """,
        (business_id,),
    ).fetchall()
    for row in messages:
        conn.execute(
            "UPDATE outreach_messages SET status = 'CANCELLED', cancelled_at = ? WHERE id = ?",
            (now_iso, row["id"]),
        )
        audit(conn, None, "MESSAGE_CANCELLED", "outreach_messages", row["id"],
              after={"status": "CANCELLED"}, business_id=business_id,
              campaign_id=row["campaign_id"], message_id=row["id"],
              detail={"blocking_code": readiness.blocking_code})
    return {"selections_removed": len(selections), "messages_cancelled": len(messages)}


def refresh_contact_readiness(conn: sqlite3.Connection, business_id: str, *,
                              campaign_id: str | None = None,
                              now: str | None = None) -> ContactReadiness:
    """Evaluate the predicate and move the business to wherever it now belongs.

    The single entry point for every event that can change a clause: a verification submitted,
    a contact edited, a suppression inserted, a response classified, a message sent, an
    opportunity rescored, a policy saved, and the nightly sweep that catches whichever of those
    somebody forgot to wire. Promotes, demotes or does nothing, always inside the caller's
    transaction, and always writing contact_ready_block_code so the grid can render an accurate
    reason for a business that is verified but held back.
    """
    now_iso = now or utc_now()
    with db.transaction(conn):
        readiness = contact_ready_predicate(conn, business_id, campaign_id=campaign_id,
                                            now=now_iso)
        status = conn.execute(
            "SELECT status FROM businesses WHERE id = ?", (business_id,)
        ).fetchone()["status"]

        if readiness.ok:
            if status == BusinessStatus.VERIFIED:
                promote_contact_ready(conn, business_id, readiness=readiness,
                                      campaign_id=campaign_id, now=now_iso)
            else:
                conn.execute(
                    "UPDATE businesses SET contact_ready_block_code = NULL,"
                    "       contact_ready_checked_at = ? WHERE id = ?",
                    (now_iso, business_id),
                )
        elif status in (BusinessStatus.CONTACT_READY, BusinessStatus.VERIFIED):
            revoke_contact_ready(conn, business_id, readiness=readiness,
                                 campaign_id=campaign_id, now=now_iso)
        else:
            conn.execute(
                "UPDATE businesses SET contact_ready_block_code = ?,"
                "       contact_ready_checked_at = ? WHERE id = ?",
                (readiness.blocking_code, now_iso, business_id),
            )
    return readiness


# ===========================================================================
# Staleness
# ===========================================================================


@dataclass(frozen=True)
class SweepResult:
    scanned: int = 0
    promoted: int = 0
    demoted: int = 0
    reverify_queued: int = 0
    drafts_abandoned: int = 0
    capped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "promoted": self.promoted,
            "demoted": self.demoted,
            "reverify_queued": self.reverify_queued,
            "drafts_abandoned": self.drafts_abandoned,
            "capped": self.capped,
        }


def sweep_verification_staleness(conn: sqlite3.Connection, *, limit: int = 500,
                                 draft_ttl_hours: int = 72,
                                 now: str | None = None) -> SweepResult:
    """The verification pass of the nightly sweep. Never verifies anything.

    A stale verification is not a flag on a CONTACT_READY business; it makes the business
    NEEDS_VERIFICATION again so it reappears in the queue where the work actually is. The
    alternative - finding out at preview time - costs Sagar five minutes and one of the day's
    free-tier Gemini requests to be told something the system knew a week ago, and four
    repetitions of that turn the eligibility panel into noise.

    Each business is handled in its own transaction, so a crash or a cap leaves a consistent
    prefix of the work done rather than an all-or-nothing rollback of a night's sweep. The
    sweep is a SYSTEM actor throughout, and the VERIFIED trigger would abort it if it tried to
    sign anything.
    """
    now_iso = now or utc_now()
    rows = scan_contact_ready(conn, limit=limit, now=now_iso)
    promoted = demoted = reverify = 0

    for row in rows:
        business_id = row["business_id"]
        try:
            before = row["status"]
            readiness = refresh_contact_readiness(conn, business_id, now=now_iso)
            after = conn.execute(
                "SELECT status FROM businesses WHERE id = ?", (business_id,)
            ).fetchone()["status"]
            if before == after:
                continue
            if after == BusinessStatus.CONTACT_READY:
                promoted += 1
            elif after == BusinessStatus.NEEDS_VERIFICATION:
                reverify += 1
                demoted += 1
            else:
                demoted += 1
            log.info("sweep moved %s %s -> %s (%s)", business_id, before, after,
                     readiness.blocking_code or "predicate holds")
        except VerifyError:
            log.exception("sweep could not settle %s; leaving it where it is", business_id)

    abandoned = _abandon_stale_drafts(conn, draft_ttl_hours=draft_ttl_hours, now=now_iso)
    return SweepResult(
        scanned=len(rows),
        promoted=promoted,
        demoted=demoted,
        reverify_queued=reverify,
        drafts_abandoned=abandoned,
        capped=len(rows) >= limit,
    )


def _abandon_stale_drafts(conn: sqlite3.Connection, *, draft_ttl_hours: int,
                          now: str) -> int:
    """A three-day-old half-answered checklist is the input that produces a rubber stamp.

    Its six ticks are already there, the work looks nearly done, and finishing it costs three
    clicks and no attention. So the draft is abandoned rather than resumed, and reopening
    starts a fresh one that inherits none of the answers.
    """
    cutoff = _shift_days(now, 0)
    moment = parse_ts(now)
    if moment is not None:
        cutoff = (moment - timedelta(hours=draft_ttl_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        "SELECT id, business_id FROM verifications WHERE state = 'DRAFT' AND started_at < ?",
        (cutoff,),
    ).fetchall()
    for row in rows:
        with db.transaction(conn):
            conn.execute("UPDATE verifications SET state = 'ABANDONED' WHERE id = ?",
                         (row["id"],))
            audit(conn, None, "VERIFICATION_SUPERSEDED", "verifications", row["id"],
                  after={"state": "ABANDONED"}, business_id=row["business_id"],
                  detail={"reason": "draft idle beyond the TTL",
                          "draft_ttl_hours": draft_ttl_hours})
    if rows:
        log.info("sweep abandoned %d idle verification drafts", len(rows))
    return len(rows)


# ===========================================================================
# Fingerprints
# ===========================================================================


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def research_fingerprint(conn: sqlite3.Connection, business_id: str) -> str:
    """sha256 over the current research run's citable content, canonically ordered.

    Deliberately excludes ids, timestamps, model_id and prompt_version: a re-run of the same
    prompt that produces the same findings must not look like a change, or every nightly
    re-research would invalidate every verification in the database. A prompt change that
    produces different findings does change this hash, and that is the case that matters.
    """
    run = conn.execute(
        """
        SELECT id FROM research_runs
         WHERE business_id = ? AND status = 'COMPLETE'
         ORDER BY finished_at DESC LIMIT 1
        """,
        (business_id,),
    ).fetchone()
    findings: list[Any] = []
    if run is not None:
        rows = conn.execute(
            """
            SELECT f.id, f.kind, f.dimension, f.statement, f.confidence, f.confidence_pct
              FROM research_findings f
             WHERE f.research_run_id = ?
             ORDER BY f.kind, f.dimension, f.statement
            """,
            (run["id"],),
        ).fetchall()
        for row in rows:
            sources = [
                r["source_id"] for r in conn.execute(
                    "SELECT source_id FROM finding_sources WHERE finding_id = ? "
                    " ORDER BY source_id",
                    (row["id"],),
                ).fetchall()
            ]
            findings.append([row["kind"], row["dimension"], row["statement"],
                             row["confidence"], row["confidence_pct"], sources])

    opportunity = conn.execute(
        """
        SELECT score, band, confidence, potential_problem, potential_solution
          FROM opportunities WHERE business_id = ? AND is_current = 1
        """,
        (business_id,),
    ).fetchone()
    modules = [
        r["module"] for r in conn.execute(
            "SELECT module FROM opportunity_modules WHERE business_id = ? AND is_current = 1"
            " ORDER BY module",
            (business_id,),
        ).fetchall()
    ]
    payload = {
        "findings": findings,
        "opportunity": ([opportunity["score"], opportunity["band"], opportunity["confidence"],
                         opportunity["potential_problem"], opportunity["potential_solution"]]
                        if opportunity else None),
        "modules": modules,
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def contact_fingerprint(conn: sqlite3.Connection, business_id: str) -> str:
    """sha256 over the sorted (kind, value_norm, human_verified, is_active) of every contact.

    value_norm, not value_display: re-typing 'Info@ABC.in' as 'info@abc.in' is not a change,
    and treating it as one sends a business back to the queue for a capitalisation edit.
    """
    rows = conn.execute(
        """
        SELECT kind, value_norm, human_verified, is_active
          FROM business_contacts WHERE business_id = ?
         ORDER BY kind, value_norm
        """,
        (business_id,),
    ).fetchall()
    payload = [[r["kind"], r["value_norm"], int(r["human_verified"]), int(r["is_active"])]
               for r in rows]
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")
_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
_SPACE_RE = re.compile(r"\s+")


def website_hash(html: bytes | str) -> str:
    """sha256 over the normalised text of a page.

    Script and style elements dropped, comments removed, tags stripped, whitespace collapsed. A
    rotating banner, a session id in a URL and a copyright year must not read as a change; a new
    phone number, a closure notice or a different business name must.
    """
    text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    text = _SCRIPT_RE.sub(" ", text)
    text = _COMMENT_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "CHECK_BY_KEY",
    "CHECK_DEFS",
    "CLAUSES",
    "CLAUSE_GATES",
    "CONTACT_READY_SCAN_SQL",
    "CheckAnswer",
    "CheckDef",
    "ChecklistError",
    "ChecklistItem",
    "ClauseResult",
    "ContactReadiness",
    "SubmitResult",
    "SweepResult",
    "TransitionError",
    "VerifyError",
    "allowed_transitions",
    "checklist_for",
    "contact_fingerprint",
    "contact_ready_predicate",
    "open_verification",
    "promote_contact_ready",
    "refresh_contact_readiness",
    "research_fingerprint",
    "revoke_contact_ready",
    "scan_contact_ready",
    "set_status",
    "submit_verification",
    "sweep_verification_staleness",
    "website_hash",
]
