/**
 * guard.js - read-only SQL validation.
 *
 * This is SAFETY LAYER 1 of 3:
 *
 *   1. guard.js          rejects non-read-only SQL before it is sent anywhere   <- this file
 *   2. PostgreSQL        the session runs with default_transaction_read_only=on,
 *                        so the engine itself refuses every write, even if this
 *                        file were bypassed entirely
 *   3. isolation         the database is PGlite (PostgreSQL compiled to WASM)
 *                        living in this browser tab. There is no driver, no
 *                        socket and no credentials anywhere in this app, so
 *                        there is no production database within reach.
 *
 * Layer 1 exists to give a clear, teachable error message rather than a raw
 * engine error, and to catch things the engine permits but we do not want
 * (pg_sleep, file access functions, and so on).
 */

// Statement kinds that write, change structure, or change permissions.
// Scanned across the WHOLE statement, not just the first word, because
// PostgreSQL allows data-modifying CTEs:
//     WITH x AS (INSERT INTO t ... RETURNING *) SELECT * FROM x;
const FORBIDDEN = [
  'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'UPSERT',
  'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'RENAME',
  'GRANT', 'REVOKE',
  'COPY', 'IMPORT',
  'VACUUM', 'REINDEX', 'CLUSTER', 'REFRESH',
  'LOCK', 'CALL', 'DO', 'EXECUTE', 'PREPARE', 'DEALLOCATE',
  'BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'START', 'END',
  'SET', 'RESET', 'DISCARD',
  'LISTEN', 'NOTIFY', 'UNLISTEN',
  'COMMENT', 'SECURITY', 'CHECKPOINT', 'LOAD',
];

// Functions that are read-only to the database but still undesirable:
// they touch the host, stall the tab, or leak the filesystem.
const FORBIDDEN_FUNCTIONS = [
  'pg_sleep', 'pg_sleep_for', 'pg_sleep_until',
  'pg_read_file', 'pg_read_binary_file', 'pg_ls_dir', 'pg_stat_file',
  'lo_import', 'lo_export', 'lo_unlink',
  'dblink', 'dblink_exec', 'postgres_fdw_handler',
  'pg_terminate_backend', 'pg_cancel_backend',
  'pg_reload_conf', 'pg_rotate_logfile',
  'pg_create_restore_point', 'pg_switch_wal',
];

// Statement may begin with one of these and nothing else.
const ALLOWED_STARTS = ['SELECT', 'WITH', 'TABLE', 'VALUES', 'EXPLAIN'];

/**
 * Remove everything a keyword scan must not look inside:
 *   - line comments      -- ...
 *   - block comments     /* ... *\/   (nesting is legal in PostgreSQL)
 *   - single-quoted strings, including '' escapes
 *   - dollar-quoted strings  $$...$$  and  $tag$...$tag$
 *   - double-quoted identifiers  "Update", "Events"
 *
 * That last one matters a great deal here: the Events table genuinely has a
 * column called "Update". Without stripping quoted identifiers, every correct
 * query touching that column would be wrongly rejected.
 *
 * Replaced with a single space so token boundaries survive.
 */
export function stripNonCode(sql) {
  let out = '';
  let i = 0;
  const n = sql.length;

  while (i < n) {
    const c = sql[i];
    const c2 = sql[i + 1];

    // -- line comment
    if (c === '-' && c2 === '-') {
      while (i < n && sql[i] !== '\n') i++;
      out += ' ';
      continue;
    }

    // /* block comment */  (PostgreSQL nests these)
    if (c === '/' && c2 === '*') {
      let depth = 1;
      i += 2;
      while (i < n && depth > 0) {
        if (sql[i] === '/' && sql[i + 1] === '*') { depth++; i += 2; }
        else if (sql[i] === '*' && sql[i + 1] === '/') { depth--; i += 2; }
        else i++;
      }
      out += ' ';
      continue;
    }

    // 'string literal'
    if (c === "'") {
      i++;
      while (i < n) {
        if (sql[i] === "'" && sql[i + 1] === "'") { i += 2; continue; }
        if (sql[i] === "'") { i++; break; }
        i++;
      }
      out += " '' ";
      continue;
    }

    // "quoted identifier"
    if (c === '"') {
      i++;
      while (i < n) {
        if (sql[i] === '"' && sql[i + 1] === '"') { i += 2; continue; }
        if (sql[i] === '"') { i++; break; }
        i++;
      }
      out += ' "id" ';
      continue;
    }

    // $$ dollar quoted $$   /   $tag$ ... $tag$
    if (c === '$') {
      const m = /^\$([A-Za-z_][A-Za-z0-9_]*)?\$/.exec(sql.slice(i));
      if (m) {
        const tag = m[0];
        const close = sql.indexOf(tag, i + tag.length);
        i = close === -1 ? n : close + tag.length;
        out += ' $$ ';
        continue;
      }
    }

    out += c;
    i++;
  }
  return out;
}

/** Split on semicolons that are real statement separators. */
export function splitStatements(sql) {
  const code = stripNonCode(sql);
  // Map positions back is unnecessary: we only need to know how many
  // non-empty statements there are.
  return code.split(';').map((s) => s.trim()).filter((s) => s.length > 0);
}

/**
 * Validate a user-submitted query.
 * @returns {{ok: boolean, code?: string, reason?: string, hint?: string}}
 */
export function validate(sql) {
  const raw = (sql || '').trim();

  if (!raw) {
    return { ok: false, code: 'EMPTY', reason: 'The editor is empty.', hint: 'Write a SELECT query and press Ctrl+Enter.' };
  }

  const code = stripNonCode(raw);

  // --- multiple statements -------------------------------------------------
  const statements = code.split(';').map((s) => s.trim()).filter(Boolean);
  if (statements.length > 1) {
    return {
      ok: false,
      code: 'MULTI_STATEMENT',
      reason: 'Only one statement can run at a time.',
      hint: 'Remove the extra statements (and any semicolon in the middle). Stacking statements is the classic SQL-injection shape, so it is refused here.',
    };
  }

  const body = statements[0] || '';
  const tokens = body.toUpperCase().match(/[A-Z_][A-Z0-9_]*/g) || [];
  if (tokens.length === 0) {
    return { ok: false, code: 'EMPTY', reason: 'No SQL statement found.' };
  }

  // --- first keyword -------------------------------------------------------
  const first = tokens[0];
  if (!ALLOWED_STARTS.includes(first)) {
    return {
      ok: false,
      code: 'NOT_READ_ONLY',
      reason: `Statements starting with ${first} are not allowed.`,
      hint: 'This lab is strictly read-only. A query must begin with SELECT, WITH, TABLE, VALUES or EXPLAIN.',
    };
  }

  // --- forbidden keyword anywhere in the statement -------------------------
  // Catches data-modifying CTEs, which are legal PostgreSQL and would
  // otherwise slip past a first-word-only check.
  const tokenSet = new Set(tokens);
  for (const kw of FORBIDDEN) {
    if (tokenSet.has(kw)) {
      return {
        ok: false,
        code: 'FORBIDDEN_KEYWORD',
        reason: `${kw} is not permitted in this lab.`,
        hint:
          kw === 'INSERT' || kw === 'UPDATE' || kw === 'DELETE'
            ? 'PostgreSQL allows data-modifying CTEs such as WITH x AS (INSERT ... RETURNING *) SELECT ..., so write keywords are rejected anywhere in the statement, not only at the start.'
            : 'Only read-only constructs are available: SELECT, WITH/CTE, JOIN, GROUP BY, HAVING, window functions, subqueries, UNION/INTERSECT/EXCEPT.',
      };
    }
  }

  // --- forbidden functions -------------------------------------------------
  const lowered = body.toLowerCase();
  for (const fn of FORBIDDEN_FUNCTIONS) {
    const re = new RegExp(`\\b${fn}\\s*\\(`, 'i');
    if (re.test(lowered)) {
      return {
        ok: false,
        code: 'FORBIDDEN_FUNCTION',
        reason: `The function ${fn}() is not available here.`,
        hint: 'It either stalls the browser tab or reaches outside the database. Neither is useful for practising SQL.',
      };
    }
  }

  return { ok: true };
}

/**
 * A short, human explanation of the three safety layers, shown in the UI.
 */
export const SAFETY_NOTE = [
  'Validator rejects anything that is not read-only before execution.',
  'PostgreSQL runs this session with default_transaction_read_only = on, so the engine refuses writes on its own.',
  'The database is PGlite (PostgreSQL in WebAssembly) inside this browser tab. No driver, no socket, no credentials, no production database in reach.',
];
