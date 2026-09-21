// Small shared helpers: logging, date parsing, formatting, escaping.

export const log = (...a) => console.log(...a);

// NSE is inconsistent: PIT list is {data:[...]}, the SHP master is a bare array.
export const asArray = x => Array.isArray(x) ? x : (x && Array.isArray(x.data) ? x.data : []);

const MONTHS = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 };

// Handles "23-Jun-2026 22:23:51", "31-MAR-2026", "17-APR-2026".
export function parseNseDate(s) {
  if (!s) return null;
  const m = String(s).match(/(\d{1,2})-([A-Za-z]{3})-(\d{4})(?:\s+(\d{1,2}):(\d{2}):(\d{2}))?/);
  if (!m) return null;
  const [, dd, mon, yyyy, hh = 0, mi = 0, ss = 0] = m;
  const mo = MONTHS[mon.toLowerCase()];
  if (mo == null) return null;
  return new Date(+yyyy, mo, +dd, +hh, +mi, +ss);
}

export function withinWindow(dateStr, days) {
  const d = parseNseDate(dateStr);
  if (!d) return false;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  return d >= cutoff;
}

export function argNum(flag, dflt) {
  const i = process.argv.indexOf(flag);
  return i > -1 && process.argv[i + 1] ? Number(process.argv[i + 1]) : dflt;
}

export const rsToCr = n => `${(n / 1_00_00_000).toFixed(2)} Cr`;

export function nowStamp() {
  const d = new Date(), p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`;
}

export const esc = s => String(s ?? '').replace(/[&<>"]/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
