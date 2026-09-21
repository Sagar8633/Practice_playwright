"""Passwords, sessions and CSRF tokens for a web app nobody outside this laptop can reach.

The threat this module answers is not a botnet. There is no public hostname (docs/_CONTEXT.md
section 2), so nothing on the internet can POST here. What it answers is the laptop itself: the
machine leaves the building every day carrying a contact database, and the browser on it is the
one thing that can turn a research row into mail sent to a stranger. A tab left open on a
borrowed desk, a family member clicking through an unlocked screen, a page from some other site
quietly submitting a form to 127.0.0.1:8770 - each of those is a send nobody decided to make,
and each is stopped here rather than in the route that would have obeyed it.

Two deliberate narrownesses. Passwords are hashed with hashlib.scrypt, which ships with CPython:
a first-run login must not depend on a wheel building on a Windows laptop. And the session is a
signed cookie holding a users.id, not a server-side table, because the approval row records the
session id anyway and a second store of the same fact is a second thing to keep consistent.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import timedelta

from radar import audit as audit_mod
from radar.models import User, parse_ts, utc_now

log = logging.getLogger("radar.web.security")

# scrypt cost. n=2**15 with r=8 costs roughly 32 MB and ~100 ms on a laptop, which is a
# rounding error on a login and a wall on an offline guess against a stolen database file.
_SCRYPT_N = 1 << 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_SALT_BYTES = 16

# Written verbatim into users.password_hash. The parameters travel with the hash so that
# raising the cost later does not lock out an account hashed at the old one.
_ALGO = "scrypt"

#: How long a browser session survives. Long enough for an afternoon of verification, short
#: enough that a laptop left open overnight asks again.
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60

#: The lockout ladder. Five wrong passwords parks the account for fifteen minutes.
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


class AuthError(RuntimeError):
    """A login attempt that must be refused, carrying the sentence the page renders."""


# ---------------------------------------------------------------------------
# password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Return a self-describing scrypt string: $scrypt$n=..,r=..,p=..$salt$hash.

    Self-describing on purpose. A bare digest is a hash whose parameters live in whatever
    version of the code last touched it, and the first time those parameters change every
    stored password becomes unverifiable.
    """
    if not password:
        raise ValueError("a blank password is not a password")
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_N * _SCRYPT_R * 256,
    )
    params = "n=%d,r=%d,p=%d" % (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return "$%s$%s$%s$%s" % (
        _ALGO, params,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    )


def verify_password(stored: str | None, password: str) -> bool:
    """Constant-time check of a password against a stored scrypt string.

    Returns False, never raises, for the seeded '!locked-no-login' anchor and for any string
    this module did not write: an unreadable hash is a locked account, not a traceback on the
    login screen.
    """
    if not stored or not password or not stored.startswith("$" + _ALGO + "$"):
        return False
    try:
        _empty, _algo, params, salt_b64, hash_b64 = stored.split("$", 4)
        opts = dict(part.split("=", 1) for part in params.split(","))
        n, r, p = int(opts["n"]), int(opts["r"]), int(opts["p"])
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        derived = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected),
            maxmem=n * r * 256,
        )
    except (ValueError, KeyError, TypeError) as exc:
        log.error("stored password hash is unreadable, refusing the login: %s", exc)
        return False
    return hmac.compare_digest(derived, expected)


# ---------------------------------------------------------------------------
# the session object every request carries
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Session:
    """Who is driving this request, resolved once per request from the signed cookie."""

    user: User
    session_id: str
    auth_method: str = "PASSWORD"       # outreach_approvals.session_auth_method

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def display_name(self) -> str:
        return self.user.display_name

    @property
    def is_owner(self) -> bool:
        return self.user.role == "OWNER"

    @property
    def may_approve(self) -> bool:
        return self.user.may_approve


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------

def set_password(conn: sqlite3.Connection, user_id: str, password: str, *,
                 actor: str | None = None) -> None:
    """Set a login password, in one transaction, with an audit row.

    Clears must_change_password and the failed-login counter: the person who just set the
    password is not the person the lockout was protecting against.
    """
    from radar.db import transaction

    if len(password) < 8:
        raise ValueError("a login password must be at least 8 characters")
    encoded = hash_password(password)
    with transaction(conn):
        cur = conn.execute(
            "UPDATE users SET password_hash = ?, password_algo = 'scrypt', "
            "       password_set_at = ?, must_change_password = 0, failed_logins = 0, "
            "       locked_until = NULL "
            " WHERE id = ?",
            (encoded, utc_now(), user_id),
        )
        if cur.rowcount == 0:
            raise ValueError("no such user: " + user_id)
        audit_mod.audit(
            conn, actor or user_id, "PASSWORD_SET", "users", user_id,
            detail={"algo": "scrypt", "self_service": actor in (None, user_id)},
        )
    log.info("password set for %s", user_id)


def authenticate(conn: sqlite3.Connection, email: str, password: str, *,
                 client_ip: str | None = None) -> User:
    """Return the User for a correct password, or raise AuthError with a renderable sentence.

    Every outcome writes an audit row. A login screen whose failures leave no trace cannot tell
    you that somebody spent an evening guessing.
    """
    from radar.db import transaction

    norm = (email or "").strip().lower()
    row = conn.execute(
        "SELECT id, email, email_norm, display_name, role, must_change_password, "
        "       totp_enrolled_at, failed_logins, locked_until, last_login_at, created_at, "
        "       disabled_at, password_hash "
        "  FROM users WHERE email_norm = ?",
        (norm,),
    ).fetchone()

    if row is None:
        # Spend comparable time so the form cannot be used to enumerate accounts.
        verify_password(hash_password("no-such-account-here"), password)
        with transaction(conn):
            audit_mod.audit(conn, None, "USER_LOGIN_FAILED", "users", None,
                            detail={"reason": "NO_SUCH_USER",
                                    "address_masked": audit_mod.mask_address(norm)},
                            client_ip=client_ip)
        raise AuthError("That email address and password do not match an account here.")

    user = User.from_row(row)
    now = utc_now()

    if row["disabled_at"]:
        raise AuthError("This account is disabled.")
    if row["locked_until"] and row["locked_until"] > now:
        raise AuthError(
            "Too many failed attempts. This account is locked until "
            + str(row["locked_until"]) + "."
        )

    if not verify_password(row["password_hash"], password):
        failed = int(row["failed_logins"]) + 1
        locked = _plus_minutes(now, LOCKOUT_MINUTES) if failed >= MAX_FAILED_LOGINS else None
        with transaction(conn):
            conn.execute(
                "UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
                (failed, locked, user.id),
            )
            audit_mod.audit(conn, None, "USER_LOGIN_FAILED", "users", user.id,
                            detail={"reason": "BAD_PASSWORD", "failed_logins": failed,
                                    "locked": bool(locked)},
                            client_ip=client_ip)
        if locked:
            raise AuthError(
                "Too many failed attempts. This account is locked for %d minutes."
                % LOCKOUT_MINUTES
            )
        raise AuthError("That email address and password do not match an account here.")

    with transaction(conn):
        conn.execute(
            "UPDATE users SET failed_logins = 0, locked_until = NULL, "
            "       last_login_at = ?, last_login_ip = ? WHERE id = ?",
            (now, client_ip, user.id),
        )
        audit_mod.audit(conn, user.id, "USER_LOGIN", "users", user.id, client_ip=client_ip)
    return user


def has_usable_password(conn: sqlite3.Connection) -> bool:
    """True when at least one enabled account can actually be logged into.

    A freshly migrated database has one user whose password_hash is deliberately
    '!locked-no-login'. The app routes the first visit to the setup page rather than to a login
    form that cannot succeed.
    """
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM users "
        " WHERE disabled_at IS NULL AND password_hash LIKE '$scrypt$%'"
    ).fetchone()
    return int(row["n"]) > 0


def owner_id(conn: sqlite3.Connection) -> str | None:
    """The OWNER account id, which on this build is the only account that exists."""
    row = conn.execute(
        "SELECT id FROM users WHERE role = 'OWNER' AND disabled_at IS NULL "
        " ORDER BY created_at LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def load_user(conn: sqlite3.Connection, user_id: str) -> User | None:
    row = conn.execute(
        "SELECT id, email, email_norm, display_name, role, must_change_password, "
        "       totp_enrolled_at, failed_logins, locked_until, last_login_at, created_at, "
        "       disabled_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return User.from_row(row) if row else None


def set_owner_email(conn: sqlite3.Connection, user_id: str, email: str,
                    display_name: str) -> None:
    """Rename the seeded owner@localhost anchor to the address Sagar actually signs in with."""
    from radar.db import transaction

    norm = email.strip().lower()
    with transaction(conn):
        conn.execute(
            "UPDATE users SET email = ?, email_norm = ?, display_name = ? WHERE id = ?",
            (email.strip(), norm, display_name.strip() or "Owner", user_id),
        )


# ---------------------------------------------------------------------------
# CSRF and session identifiers
# ---------------------------------------------------------------------------

def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_ok(expected: str | None, supplied: str | None) -> bool:
    """Constant-time comparison. Both missing is a failure, not a pass."""
    if not expected or not supplied:
        return False
    return hmac.compare_digest(expected, supplied)


def new_session_id() -> str:
    """The identifier written to outreach_approvals.session_id.

    Unguessable, and stable for the life of the browser session, because the approval record's
    claim is 'this exact body was approved in this sitting'.
    """
    return "web-" + secrets.token_hex(16)


def new_preview_token() -> str:
    """Binds one rendered preview to one approval attempt (05 section 5.13.4)."""
    return "prv-" + secrets.token_hex(16)


def _plus_minutes(iso: str, minutes: int) -> str:
    moment = parse_ts(iso)
    if moment is None:  # pragma: no cover - utc_now() always parses
        return iso
    return (moment + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
