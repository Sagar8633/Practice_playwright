"""The append-only record of who did what, and the hash chain that makes tampering detectable.

The question this module exists to answer is asked after the fact, usually once, usually badly:
"why did this business receive that email?" Everything else in the system is a live view that
research can rewrite - a finding can be superseded, a score recomputed, a contact deactivated.
The audit log is the only place that keeps what was true at the moment a human clicked approve.
Without it, a complaint arrives and the honest answer is a shrug.

Two properties make it evidence rather than logging.

It is append-only, enforced by triggers: UPDATE and DELETE against audit_log abort the
statement and its transaction. That stops an application bug and a hurried interactive session,
which are the two realistic threats on a single-operator laptop.

It is chained: each row carries the sha256 of the row before it, and its own hash covers its
own content plus that link. Deleting or editing a row in the middle - which requires first
dropping the trigger - leaves every subsequent row's prev_hash pointing at something that no
longer hashes to that value, and verify_chain() finds the exact seq where it happened.

The chain is also why audit() must run inside the same transaction as the thing it records.
The seq must be one past the current head, and two concurrent writers would otherwise both
compute the same next seq and one would fail the trigger. transaction() takes the write lock
up front, which serialises them.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from typing import Any

from .ids import new_id
from .models import ActorKind, utc_now

log = logging.getLogger("radar.audit")

GENESIS_HASH = "0" * 64

#: Detail keys that a trigger rejects because they would carry a raw contact address into a
#: table that is kept forever. Use address_masked / address_sha256 instead.
FORBIDDEN_DETAIL_KEYS = ("address", "to")


class AuditError(RuntimeError):
    """An audit row could not be written. For a CRITICAL action this aborts the operation."""


class UnknownAuditAction(AuditError):
    """The action is not in the audit_actions catalogue.

    Adding one is a migration, not a string literal at a call site: an action nobody declared
    has no severity, no PII class, and no description, which makes the row it produces
    uninterpretable six months later.
    """


def _canonical(value: Any) -> str | None:
    """Serialise a payload the same way every time, so the hash is reproducible.

    sort_keys and compact separators: a dict that happens to iterate in a different order must
    not produce a different row_hash for the same content.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str,
                      ensure_ascii=False)


def compute_row_hash(
    *,
    seq: int,
    at: str,
    actor_kind: str,
    actor_label: str,
    action: str,
    entity_table: str,
    entity_id: str | None,
    before_json: str | None,
    after_json: str | None,
    detail_json: str,
    prev_hash: str,
) -> str:
    """The row hash: sha256 over the fields that constitute the claim, plus the previous link.

    Deliberately not every column. request_id, client_ip and user_agent are context, not the
    claim; including them would mean a row could not be re-derived from what it asserts. What
    is covered is who, what, to which entity, with what before and after, and where in the
    chain.
    """
    parts = [
        str(seq), at, actor_kind, actor_label, action, entity_table, entity_id or "",
        before_json or "", after_json or "", detail_json, prev_hash,
    ]
    payload = "\x1e".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def head(conn: sqlite3.Connection) -> tuple[int, str]:
    """The current chain head: (seq, row_hash). (0, GENESIS_HASH) on an empty log."""
    row = conn.execute(
        "SELECT seq, row_hash FROM audit_log ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return 0, GENESIS_HASH
    return int(row["seq"]), str(row["row_hash"])


def known_actions(conn: sqlite3.Connection) -> frozenset[str]:
    """Every action the catalogue declares. Cheap; call it in a validation pass."""
    return frozenset(
        r["action"] for r in conn.execute("SELECT action FROM audit_actions")
    )


def audit(
    conn: sqlite3.Connection,
    actor: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before: Any = None,
    after: Any = None,
    *,
    actor_kind: str | None = None,
    business_id: str | None = None,
    campaign_id: str | None = None,
    message_id: str | None = None,
    detail: dict[str, Any] | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    route: str | None = None,
    http_method: str | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
    job_id: str | None = None,
    job_run_id: str | None = None,
) -> str:
    """Append one row to the audit log and return its id.

    `actor` is a users.id for a human action, or a label like 'worker-1' or 'poll_inbox' for a
    system one. `actor_kind` is inferred from the shape of `actor` when not given: a usr_ id
    means HUMAN, anything else means SYSTEM, None means SYSTEM with the label '-'.

    `before` and `after` are the state delta. Pass dicts of the columns that changed, not whole
    rows: an audit row that copies forty unchanged columns buries the one that moved.

    Call this inside the same transaction as the change it records. If the change commits and
    the audit row does not, the system has done something it cannot explain, which for a send
    is the exact failure this whole design exists to prevent.
    """
    if actor_kind is None:
        if actor is None:
            actor_kind = ActorKind.SYSTEM.value
        elif actor.startswith("usr_"):
            actor_kind = ActorKind.HUMAN.value
        else:
            actor_kind = ActorKind.SYSTEM.value

    actor_user_id = actor if actor_kind == ActorKind.HUMAN.value else None
    actor_label = actor or "-"

    if actor_kind == ActorKind.HUMAN.value and not actor_user_id:
        raise AuditError(
            "a HUMAN audit row needs a users.id as its actor; "
            "a row whose actor is unknown is worse than no row, because it looks like evidence"
        )

    detail = dict(detail or {})
    for key in FORBIDDEN_DETAIL_KEYS:
        if key in detail:
            raise AuditError(
                f"audit detail key {key!r} would carry a raw contact address into a table "
                f"that is kept forever. Use 'address_masked' or 'address_sha256'."
            )

    at = utc_now()
    before_json = _canonical(before)
    after_json = _canonical(after)
    detail_json = _canonical(detail) or "{}"

    prev_seq, prev_hash = head(conn)
    seq = prev_seq + 1
    row_hash = compute_row_hash(
        seq=seq, at=at, actor_kind=actor_kind, actor_label=actor_label, action=action,
        entity_table=entity_type, entity_id=entity_id, before_json=before_json,
        after_json=after_json, detail_json=detail_json, prev_hash=prev_hash,
    )
    audit_id = new_id("aud")

    try:
        conn.execute(
            """
            INSERT INTO audit_log (
                id, seq, at, actor_kind, actor_user_id, actor_label,
                action, entity_table, entity_id,
                business_id, campaign_id, message_id,
                before_json, after_json, detail_json,
                request_id, session_id, route, http_method, client_ip, user_agent,
                job_id, job_run_id, prev_hash, row_hash, hash_version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            """,
            (
                audit_id, seq, at, actor_kind, actor_user_id, actor_label,
                action, entity_type, entity_id,
                business_id, campaign_id, message_id,
                before_json, after_json, detail_json,
                request_id, session_id, route, http_method, client_ip, user_agent,
                job_id, job_run_id, prev_hash, row_hash,
            ),
        )
    except sqlite3.IntegrityError as exc:
        message = str(exc)
        if "audit_actions" in message or "FOREIGN KEY" in message:
            raise UnknownAuditAction(
                f"audit action {action!r} is not in the audit_actions catalogue. Add it to "
                f"the seed block in radar/migrations/001_schema.sql (or a new migration) "
                f"rather than passing an undeclared string."
            ) from exc
        if "chain break" in message:
            raise AuditError(
                "audit_log chain break: another writer appended between reading the head and "
                "inserting. Wrap the operation in db.transaction(), which takes the write "
                "lock up front."
            ) from exc
        raise AuditError(f"could not write audit row for {action}: {exc}") from exc

    log.debug("audit %s %s %s/%s", audit_id, action, entity_type, entity_id or "-")
    return audit_id


def verify_chain(conn: sqlite3.Connection, *, start: int = 1) -> list[str]:
    """Recompute every row's hash and check the links. Empty list means intact.

    Reports the first problem per row rather than cascading: one edited row makes every later
    prev_hash wrong, and forty thousand lines of that hides the seq that actually matters.
    """
    problems: list[str] = []
    expected_seq = start
    prev_hash = GENESIS_HASH

    if start > 1:
        anchor = conn.execute(
            "SELECT row_hash FROM audit_log WHERE seq = ?", (start - 1,)
        ).fetchone()
        if anchor is None:
            return [f"cannot verify from seq {start}: seq {start - 1} is missing"]
        prev_hash = str(anchor["row_hash"])

    cursor = conn.execute(
        """
        SELECT seq, at, actor_kind, actor_label, action, entity_table, entity_id,
               before_json, after_json, detail_json, prev_hash, row_hash
          FROM audit_log
         WHERE seq >= ?
         ORDER BY seq
        """,
        (start,),
    )

    for row in cursor:
        seq = int(row["seq"])
        if seq != expected_seq:
            problems.append(f"seq gap: expected {expected_seq}, found {seq}")
            expected_seq = seq
        if row["prev_hash"] != prev_hash:
            problems.append(
                f"seq {seq}: prev_hash does not match the previous row's row_hash "
                f"(expected {prev_hash[:16]}..., stored {str(row['prev_hash'])[:16]}...)"
            )
        else:
            recomputed = compute_row_hash(
                seq=seq, at=row["at"], actor_kind=row["actor_kind"],
                actor_label=row["actor_label"], action=row["action"],
                entity_table=row["entity_table"], entity_id=row["entity_id"],
                before_json=row["before_json"], after_json=row["after_json"],
                detail_json=row["detail_json"], prev_hash=str(row["prev_hash"]),
            )
            if recomputed != row["row_hash"]:
                problems.append(
                    f"seq {seq}: content does not hash to its stored row_hash; "
                    f"this row was edited after it was written"
                )
        prev_hash = str(row["row_hash"])
        expected_seq = seq + 1

    return problems


def history(
    conn: sqlite3.Connection,
    *,
    business_id: str | None = None,
    campaign_id: str | None = None,
    message_id: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    limit: int = 200,
    user_visible_only: bool = True,
) -> list[sqlite3.Row]:
    """The audit trail for one thing, newest first.

    `user_visible_only` filters to the rows the business timeline shows; pass False for the
    raw view under /settings, which is an OWNER-only screen.
    """
    where: list[str] = []
    params: list[Any] = []
    if business_id:
        where.append("a.business_id = ?")
        params.append(business_id)
    if campaign_id:
        where.append("a.campaign_id = ?")
        params.append(campaign_id)
    if message_id:
        where.append("a.message_id = ?")
        params.append(message_id)
    if entity_id:
        where.append("a.entity_id = ?")
        params.append(entity_id)
    if action:
        where.append("a.action = ?")
        params.append(action)
    if user_visible_only:
        where.append("act.user_visible = 1")

    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(int(limit))

    return conn.execute(
        f"""
        SELECT a.*, act.domain, act.severity, act.description
          FROM audit_log a
          JOIN audit_actions act ON act.action = a.action
          {clause}
         ORDER BY a.seq DESC
         LIMIT ?
        """,
        params,
    ).fetchall()


def mask_address(value: str | None) -> str:
    """'owner@abchospital.in' -> 'ow***@abchospital.in'. Safe for a detail payload.

    Here as well as on Contact because the audit path frequently has a bare string - an
    inbound From header, a bounced recipient - and no Contact row to hang it off.
    """
    if not value:
        return "***"
    if "@" in value:
        local, _, domain = value.partition("@")
        head_part = local[:2] if len(local) > 2 else local[:1]
        return f"{head_part}***@{domain}"
    if len(value) > 4:
        return f"{value[:3]}***{value[-2:]}"
    return "***"


def hash_address(value: str | None) -> str:
    """sha256 of a normalised address, for 'is this the same address' without storing it."""
    return hashlib.sha256((value or "").strip().lower().encode("utf-8")).hexdigest()
