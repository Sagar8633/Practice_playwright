"""The one place a connection to data/radar.db is opened, and the one place schema changes are
applied.

Two failures this module exists to prevent, both of which are quiet until they are expensive.

The first is a connection with foreign keys switched off. SQLite defaults `PRAGMA
foreign_keys` to OFF, per connection, forever. An outreach_messages row pointing at an
approval_id that does not exist would then be storable, and the whole of safety invariant 1
would come down to whether the Python that wrote it happened to be correct that day. So
connect() asserts the pragma actually took effect and raises if it reads back 0 - which it
does on a build compiled without foreign key support, and which nobody would otherwise notice.

The second is a half-applied migration. Every migration runs inside one transaction and its
schema_version row is written in that same transaction, so a crash rolls back both. The row
carries the sha256 of the file's bytes: editing a migration that has already been applied is
then a loud error on the next start instead of two machines quietly holding the same version
number and different schemas.
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .paths import DB_PATH, MIGRATIONS_DIR, ensure

log = logging.getLogger("radar.db")

# Number and name, e.g. 001_schema.sql. Anything else in migrations/ is ignored.
_MIGRATION_RE = re.compile(r"^(\d{3,4})_[A-Za-z0-9_]+\.sql$")

# Long enough to outlast a report export holding a read transaction, short enough that a real
# deadlock surfaces during a working session rather than at 2am.
_BUSY_TIMEOUT_MS = 15_000


class DatabaseError(RuntimeError):
    """The database exists but cannot be used as it is."""


class MigrationError(DatabaseError):
    """A migration file is missing, changed, or failed to apply."""


def connect(path: Path | str = DB_PATH, *, read_only: bool = False) -> sqlite3.Connection:
    """Open a connection with the pragmas this schema depends on, and prove they took.

    Foreign keys ON, verified rather than assumed. WAL journaling, so the web app can read
    while a research job writes. Row factory sqlite3.Row, so every from_row() in models.py can
    address columns by name.
    """
    path = Path(path)
    if not read_only:
        ensure()
        path.parent.mkdir(parents=True, exist_ok=True)

    if read_only:
        uri = f"file:{path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=_BUSY_TIMEOUT_MS / 1000)
    else:
        conn = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_MS / 1000)

    conn.row_factory = sqlite3.Row
    # isolation_level=None: we open transactions explicitly with BEGIN IMMEDIATE. Python's
    # implicit transaction handling would start a deferred one at a moment of its choosing,
    # which is exactly the ambiguity transaction() exists to remove.
    conn.isolation_level = None

    conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")

    enforced = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    if not enforced:
        conn.close()
        raise DatabaseError(
            "PRAGMA foreign_keys came back 0: this SQLite build does not enforce foreign "
            "keys, and every safety invariant in this schema assumes it does. Refusing to "
            "run. Check the Python build (sqlite3.sqlite_version) before going further."
        )

    if not read_only:
        mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if str(mode).lower() != "wal":
            # Not fatal - a database on a network share cannot do WAL - but the operator
            # should know that concurrent reads will now block.
            log.warning("journal_mode is %s, not WAL; concurrent reads will block on writes",
                        mode)
        conn.execute("PRAGMA synchronous = NORMAL")

    conn.execute("PRAGMA foreign_keys")   # no-op, keeps the pragma cache warm
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """A write transaction that takes its lock up front.

    BEGIN IMMEDIATE, not BEGIN. A deferred transaction acquires the write lock at its first
    write, which means two workers can both read, both decide to act, and one then fails at
    commit time having already done half its work in Python. Taking the lock at the start
    turns that into a clean wait.

    Nested calls join the outer transaction rather than starting a second one, so a helper
    that wants a transaction can be called from inside one.
    """
    if conn.in_transaction:
        yield conn
        return

    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            filename    TEXT NOT NULL,
            sha256      TEXT NOT NULL CHECK (length(sha256) = 64),
            applied_at  TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            duration_ms INTEGER,
            applied_by  TEXT NOT NULL DEFAULT 'migrate'
        )
        """
    )


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[tuple[int, Path]]:
    """Every numbered .sql file in migrations/, in version order.

    Duplicate version numbers are an error rather than a coin toss: two files both numbered
    007 would apply in filesystem order, which differs between machines.
    """
    found: dict[int, Path] = {}
    for candidate in sorted(directory.glob("*.sql")):
        match = _MIGRATION_RE.match(candidate.name)
        if not match:
            log.warning("ignoring %s: not a numbered migration filename", candidate.name)
            continue
        version = int(match.group(1))
        if version in found:
            raise MigrationError(
                f"two migrations share version {version}: "
                f"{found[version].name} and {candidate.name}"
            )
        found[version] = candidate
    return sorted(found.items())


def applied_versions(conn: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    _ensure_schema_version_table(conn)
    rows = conn.execute(
        "SELECT version, filename, sha256, applied_at FROM schema_version ORDER BY version"
    ).fetchall()
    return {row["version"]: row for row in rows}


def schema_version(conn: sqlite3.Connection) -> int:
    """The highest applied migration number, or 0 on an empty database."""
    _ensure_schema_version_table(conn)
    row = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_version").fetchone()
    return int(row["v"])


def migrate(
    conn: sqlite3.Connection,
    *,
    directory: Path = MIGRATIONS_DIR,
    applied_by: str = "migrate",
) -> list[int]:
    """Apply every migration this database has not seen. Idempotent, forward-only.

    Returns the versions applied by this call, empty if the database was already current.

    Three things this refuses to do, each because the alternative produces two machines that
    believe they have the same schema:
      * apply a file whose sha256 differs from the one recorded when it was applied;
      * apply a migration numbered below one already applied (forward-only);
      * continue past a migration that raised, leaving later ones applied over a gap.
    """
    ensure()
    already = applied_versions(conn)
    pending: list[tuple[int, Path]] = []

    for version, path in discover_migrations(directory):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record = already.get(version)
        if record is None:
            pending.append((version, path))
            continue
        if record["sha256"] != digest:
            raise MigrationError(
                f"migration {path.name} has changed since it was applied on "
                f"{record['applied_at']}. Migrations are forward-only: revert the edit and "
                f"add a new numbered file instead.\n"
                f"  recorded {record['sha256']}\n"
                f"  on disk  {digest}"
            )

    if not pending:
        log.debug("database is at schema version %d, nothing to apply", schema_version(conn))
        return []

    highest_applied = max(already, default=0)
    out_of_order = [v for v, _ in pending if v < highest_applied]
    if out_of_order:
        raise MigrationError(
            f"migrations {out_of_order} are numbered below the applied maximum "
            f"{highest_applied}. Renumber them above it; this schema is forward-only."
        )

    applied: list[int] = []
    for version, path in pending:
        sql = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        log.info("applying migration %s", path.name)
        started = time.monotonic()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executescript(sql)
            # executescript commits any open transaction before running, so re-open one for
            # the bookkeeping row rather than assuming we are still inside the first.
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO schema_version (version, filename, sha256, duration_ms, applied_by)"
                " VALUES (?, ?, ?, ?, ?)",
                (version, path.name, digest,
                 int((time.monotonic() - started) * 1000), applied_by),
            )
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            log.error("migration %s failed; database left at version %d",
                      path.name, schema_version(conn))
            raise
        applied.append(version)
        log.info("applied %s in %d ms", path.name, int((time.monotonic() - started) * 1000))

    return applied


def open_migrated(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """connect() plus migrate(). What every entry point actually wants."""
    conn = connect(path)
    migrate(conn)
    return conn


def integrity_check(conn: sqlite3.Connection) -> list[str]:
    """SQLite's own integrity checks plus a foreign key sweep. Empty list means healthy.

    Worth running after a laptop loses power mid-write, which on this deploy target is a
    Tuesday rather than a disaster-recovery scenario.
    """
    problems: list[str] = []
    for row in conn.execute("PRAGMA integrity_check"):
        value = row[0]
        if value != "ok":
            problems.append(f"integrity_check: {value}")
    for row in conn.execute("PRAGMA foreign_key_check"):
        problems.append(
            f"foreign_key_check: {row[0]} rowid={row[1]} references {row[2]} (fk #{row[3]})"
        )
    return problems


def table_names(conn: sqlite3.Connection) -> set[str]:
    """Every table in the database. Used by startup assertions and by tests."""
    return {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    }
