-- ===========================================================================
-- 075_web.sql - what the browser layer needs that 001 did not anticipate
-- ===========================================================================
-- Two changes, both forced by the deploy target rather than by taste.
--
-- 1. users.password_algo accepted 'argon2id' or 'bcrypt'. Both mean a third-party wheel on a
--    Windows laptop that has to `pip install` before Sagar can log in for the first time.
--    hashlib.scrypt has been in the standard library since 3.6, is memory-hard, and is what
--    12-security-model.md's argument actually asks for: a slow KDF with a per-user salt. The
--    CHECK is widened rather than removed, so 'sha256' still cannot be written by accident.
--    SQLite cannot ALTER a CHECK, so the table is rebuilt. Nothing references users by rowid
--    and no trigger fires on it; the fifteen tables that reference users(id) resolve the name
--    after the rename, which is why foreign_keys is off for the swap and on again after it.
--
-- 2. Two audit actions the web layer writes. audit() refuses an action the catalogue does not
--    declare, and a login screen that cannot record a password change is not auditable.
--
-- Forward-only. 001 is untouched.

PRAGMA foreign_keys = OFF;

BEGIN;

CREATE TABLE users_new (
    id                   TEXT PRIMARY KEY,
    email                TEXT NOT NULL,
    email_norm           TEXT NOT NULL,
    display_name         TEXT NOT NULL,

    password_hash        TEXT NOT NULL,
    password_algo        TEXT NOT NULL DEFAULT 'scrypt'
                           CHECK (password_algo IN ('argon2id','bcrypt','scrypt')),
    password_set_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0,1)),

    role                 TEXT NOT NULL DEFAULT 'VIEWER'
                           CHECK (role IN ('OWNER','OPERATOR','VIEWER')),

    totp_secret          TEXT,
    totp_enrolled_at     TEXT,
    totp_last_used_step  INTEGER,

    failed_logins        INTEGER NOT NULL DEFAULT 0 CHECK (failed_logins >= 0),
    locked_until         TEXT,
    last_login_at        TEXT,
    last_login_ip        TEXT,

    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_by           TEXT REFERENCES users(id),
    disabled_at          TEXT,
    disabled_by          TEXT REFERENCES users(id),
    disabled_reason      TEXT,

    CHECK ((totp_secret IS NULL) = (totp_enrolled_at IS NULL)),
    CHECK ((disabled_at IS NULL) = (disabled_by IS NULL)),
    CHECK (email_norm = lower(email_norm))
);

INSERT INTO users_new SELECT
    id, email, email_norm, display_name, password_hash, password_algo, password_set_at,
    must_change_password, role, totp_secret, totp_enrolled_at, totp_last_used_step,
    failed_logins, locked_until, last_login_at, last_login_ip, created_at, created_by,
    disabled_at, disabled_by, disabled_reason
FROM users;

DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

CREATE UNIQUE INDEX ux_users_email ON users(email_norm);
CREATE INDEX ix_users_role ON users(role) WHERE disabled_at IS NULL;

INSERT OR IGNORE INTO audit_actions
    (action, domain, severity, user_visible, pii_class, description) VALUES
    ('PASSWORD_SET', 'ACCESS', 'CRITICAL', 1, 'REFERENCE',
     'A local login password was set or changed'),
    ('USER_LOGOUT',  'ACCESS', 'INFO',     0, 'REFERENCE',
     'A browser session was ended');

COMMIT;

PRAGMA foreign_keys = ON;
