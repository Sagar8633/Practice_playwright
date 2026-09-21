# 3. HTML report architecture

This document settles how the city-wise business research report is produced, what is inside it, and
— the question everything else hangs off — what an **exported, offline, single-file** copy of it is
allowed to do. It covers spec §3, §4, §5, §6, §7, §8, §9, §10, §37, §38, §39, §40, §41, §42, §43,
§44, §50 and §51, and it renders the research-panel content defined by §11, §12, §13 and §14. Every
number in the report is defined here as a SQL aggregate over real rows, and every number that has no
rows behind it renders as an em dash rather than a zero, because `_CONTEXT.md` invariant 5 forbids
the report from inventing anything.

**Cross-references.** `01-data-model.md` carries the canonical schema and is the arbiter; this
document owns **no tables**. `report_exports` (§3.12) is owned by `11-audit-architecture.md`
§11.11.1 as amended by `01-data-model.md` §1.2.1 — an earlier draft of this document declared it
here and that DDL is deleted. What this document does own is the view `v_report_business` (§3.3.2).
Every table appears as a "columns this document depends on" contract in §3.3.1. Selection and send
eligibility belong to
`05-outreach-workflow.md` — the report *renders* `blocking_gate`, it never computes it. The
verification screen (§15, §16) belongs to the verification document; the report only links to it.
Human handoff (§34, §35) and the funnel analytics behind §38's later columns belong to
`10-human-handoff.md`.

---

## 3.1 The critical architectural question, answered first

### 3.1.1 There are two renderings of the same report, and only one of them can act

Spec §5 wants a "professional HTML report" that is "downloadable, viewable in a browser",
"completely self-contained". Spec §40 wants per-row actions including VERIFY, SELECT, PREPARE
OUTREACH and SEND. Those two requirements are in direct tension: **a file on disk has no server, no
session, and no database. It cannot verify anything, it cannot record a selection, and it must never
be able to transmit a message.**

The resolution is a single flag threaded through one template tree:

| | `LIVE` | `EXPORT` |
|---|---|---|
| Served by | Flask, at `/campaigns/<id>` | nothing — it is a file |
| Origin | `https://<app-host>` | `file://…` or an email attachment |
| Data | queried per request | frozen at export time, embedded |
| Read-only content (header, KPIs, tables, research panels, sources) | full | **full and identical** |
| Filter / search / sort / tab / expand | works | works |
| Row action VIEW / RESEARCH / HISTORY | in-page | **in-page, from embedded data** |
| Row action VERIFY / REJECT / SELECT / PREPARE OUTREACH / VIEW MESSAGE | acts | **deep link to the live app, disabled when the app is unreachable** |
| Row action SEND | **does not exist** | **does not exist** |
| `<form>` elements | zero | zero |
| Outbound network calls | same-origin XHR | **one optional health probe, and nothing else** |

### 3.1.2 The safety property, stated loudly

> **The exported report file carries no capability. It contains no credential, no token, no signed
> URL, no API key, no `<form>`, and no code path that can cause a message to be transmitted. Every
> state-changing control in it is an ordinary `<a href>` to a GET-only UI route on the live app,
> which will demand a session and re-check every eligibility gate before it changes anything. If
> Sagar emails this file to somebody, the worst they can do with it is read it.**

This is enforced in four places, not one:

1. **Template.** `EXPORT` mode renders action controls through the `act_link()` macro, which emits
   `<a>` only. There is no `POST` macro reachable from the export template tree (§3.2.3).
2. **Meta CSP.** The export carries a restrictive `Content-Security-Policy` meta tag whose
   `form-action 'none'` and narrow `connect-src` make the file structurally unable to submit or to
   call anything but the configured app host (§3.1.5).
3. **Server.** Every state-changing route is `POST`-only and CSRF-protected. A deep link lands on a
   *screen*, never on a mutation. `GET /verify/<id>` renders the verification form; it does not
   verify.
4. **Test.** `test_export_has_no_form_no_post_no_secret` greps the produced bytes and fails the
   build on `<form`, `method=`, `XMLHttpRequest`, `fetch(` outside the single allow-listed probe
   function, and on any string matching the app's secret-shaped patterns (§3.15).

The SEND control deserves its own line, because §19 is explicit: *"The Send button must NOT exist on
the raw AI research result."* §40 lists SEND among the row actions with preconditions attached. Those
are reconciled as follows, and this is a settled decision:

> **The report never renders a SEND control, in either mode.** Where §40 says SEND, the report
> renders a read-only **send-readiness chip** (§3.8.3) that states which precondition is outstanding,
> and — only when everything is satisfied and an approved draft exists — links to
> `/outreach/<draft_id>` in the live app, where the CONFIRM & SEND button lives behind the approval
> record described in `05-outreach-workflow.md`. A research report is a document. Documents do not
> send email.

### 3.1.3 Deep-link scheme

`app_base_url` is baked in at export time from `config.yaml → web.public_base_url`. If it is unset,
the export renders **no action links at all** and the report is a pure document. There is no
fallback to `localhost`, because a report emailed to somebody else would then carry links that
silently resolve to *their* machine.

| Action (§40) | Route | Method | Available in `EXPORT` |
|---|---|---|---|
| VIEW | `{base}/business/<business_id>` | GET | link |
| RESEARCH | in-page panel toggle `#biz-<id>-research` | — | in-page, offline |
| VERIFY | `{base}/verify/<business_id>?from=export&campaign=<campaign_id>` | GET | link, gated |
| REJECT | `{base}/verify/<business_id>?intent=reject` | GET | link, gated |
| SELECT | `{base}/campaigns/<campaign_id>?select=<business_id>` | GET | link, gated |
| PREPARE OUTREACH | `{base}/outreach?campaign=<campaign_id>&business=<business_id>` | GET | link, gated |
| VIEW MESSAGE | `{base}/outreach/<draft_id>` | GET | link, gated |
| SEND | — | — | **never** |
| HISTORY | in-page panel `#biz-<id>-history` from embedded `outreach_events` | — | in-page, offline |

`?from=export` is recorded in `audit_log.detail` when the landing screen commits, so an audit can
tell that a verification was initiated from a report file rather than from the live grid.

### 3.1.4 Read-only degradation

The export's default state is **read-only**. It upgrades to "actions available" only on evidence
that the live app answered:

```js
/* report.js — the ONLY network call in an exported report. */
(function probeApp() {
  var root = document.documentElement;
  var base = root.dataset.appBase || "";
  if (!base) { root.dataset.app = "absent"; return; }   // no base URL baked in
  root.dataset.app = "unknown";                          // fail-safe: acts are disabled
  var ctl = new AbortController();
  var timer = setTimeout(function () { ctl.abort(); }, 1500);
  fetch(base + "/api/v1/health", {
    method: "GET", mode: "cors", credentials: "omit",
    cache: "no-store", signal: ctl.signal
  }).then(function (r) {
    root.dataset.app = r.ok ? "up" : "down";
  }).catch(function () {
    root.dataset.app = "down";
  }).finally(function () { clearTimeout(timer); });
})();
```

```css
/* Fail-safe: anything that is not a confirmed-up app leaves actions inert. */
:root:not([data-app="up"]) .act        { pointer-events: none; opacity: .45; }
:root:not([data-app="up"]) .act::after { content: " (offline)"; font-size: 11px; }
:root[data-app="up"]      #banner-ro   { display: none; }
```

and the matching JS strips `href` so keyboard users cannot navigate a control that is presented as
disabled:

```js
function applyAppState() {
  var up = document.documentElement.dataset.app === "up";
  document.querySelectorAll("a.act").forEach(function (a) {
    if (up) {
      if (a.dataset.href) { a.setAttribute("href", a.dataset.href); }
      a.removeAttribute("aria-disabled"); a.removeAttribute("tabindex");
      a.title = a.dataset.title || "";
    } else {
      if (a.hasAttribute("href")) { a.dataset.href = a.getAttribute("href"); }
      a.removeAttribute("href");
      a.setAttribute("aria-disabled", "true"); a.setAttribute("tabindex", "-1");
      a.title = "Requires the live app at " + (document.documentElement.dataset.appBase || "—");
    }
  });
}
```

Rules that follow, and are not negotiable:

- **The probe is optional.** Nothing renders late, nothing is fetched, no layout depends on it. Open
  the file on a plane with no network and the entire document — header, KPIs, all tables, every
  research panel, every source URL — is complete and correct. §5's "completely self-contained" is
  about the *content*, and the content never leaves the file.
- **`credentials: "omit"`.** The probe must not carry Sagar's session cookie to an origin that a
  `file://` page cannot be trusted about.
- **`file://` usually fails the probe** (origin `null` is rejected by CORS), and that is the correct
  outcome: the export stays read-only unless it is opened from a context the app recognises. The
  banner then reads:

  ```
  Read-only. This file was exported 2026-08-26 19:04 IST and shows the data as of that moment.
  The live app at https://radar.example.internal did not respond, so VERIFY / SELECT / PREPARE
  OUTREACH are disabled. Open the campaign in the app to act on these rows.
  ```
  (SAMPLE text; timestamp and host are interpolated.)
- **Nothing degrades the reading experience.** Filtering, search, sort, tabs, research panels, source
  links and the CSV-of-selection helper (§3.7.3) all work with `data-app="down"`.

### 3.1.5 The export's Content-Security-Policy

```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'none';
  style-src 'unsafe-inline';
  script-src 'unsafe-inline';
  img-src data:;
  font-src data:;
  connect-src https://radar.example.internal;
  form-action 'none';
  base-uri 'none';
  frame-ancestors 'none'">
```

`connect-src` is the single configured `app_base_url` and nothing else — if `app_base_url` is unset
the directive becomes `connect-src 'none'`. `form-action 'none'` is the load-bearing one: even if a
future template bug emitted a `<form>`, the browser refuses to submit it. `img-src data:` and
`font-src data:` are what make the inlining in §3.2.4 work while still forbidding every remote fetch.

The `LIVE` rendering gets a *different*, stricter policy set as a real response header by Flask
(nonce-based `script-src`, `connect-src 'self'`, `form-action 'self'`); that belongs to the security
document. The meta tag exists only in `EXPORT`.

---

## 3.2 Generation architecture

### 3.2.1 `radar/report.py`

```python
"""Turn a finished campaign into the one artefact Sagar actually reads.

Everything upstream of this module - discovery, research, scoring, verification - produces rows in
SQLite that nobody looks at. This module is where those rows become a decision. Without it Sagar is
reading a database by hand at 9pm and picking businesses by whichever name he happens to recognise,
which is exactly the failure mode the opportunity score exists to prevent.

Two renderings come out of the same templates. The LIVE one is served by Flask and can act. The
EXPORT one is a single file with no server behind it, so it cannot act, and this module is
responsible for making sure it cannot pretend otherwise: no form, no token, no send path, and every
state-changing control reduced to a link back to the app that will re-check the gates itself.

The other job here is arithmetic honesty. Every figure in the report is a SELECT over real rows. A
metric with no rows behind it renders as an em dash, never as a zero, because a report that shows
"0 verified" when it means "verification has not run" will get a business contacted that nobody
checked.
"""
from __future__ import annotations

import logging

log = logging.getLogger("radar.report")
```

### 3.2.2 File and template tree

```
radar/
  report.py                     build/orchestrate, filename rules, archive rows
  report_queries.py             the 12 SQL constants and their row->dataclass mappers
  report_export.py              CSV / XLSX / PDF writers
  web/
    app.py                      routes
    templates/
      base.html                 live-app chrome (nav, session, flash) - EXPORT never uses this
      report/
        report.html             LIVE   : {% extends "base.html" %}
        export.html             EXPORT : standalone <!doctype html>, no chrome
        daily.html              §43, both modes
        _macros.html            chip(), act_link(), dash(), score_badge(), src_link()
        _header.html            §6
        _kpis.html              §7
        _city_summary.html      §8
        _filters.html           §39
        _tabs.html              §3, §4
        _table.html             §9, §10
        _panel.html             §11-§14
        _cmp_city.html          §37
        _cmp_industry.html      §38
        _top20.html             §44
        _selection_bar.html     §18
    static/
      report.css                ~28 KB source
      report.js                 ~22 KB source
      inter-var-subset.woff2    optional, ~34 KB, see §3.2.4
```

`report.html` and `export.html` differ in **nothing but the shell**. Both do:

```jinja
{% import "report/_macros.html" as m with context %}
{% include "report/_header.html" %}
{% include "report/_kpis.html" %}
{% include "report/_city_summary.html" %}
{% include "report/_filters.html" %}
{% include "report/_tabs.html" %}
{% include "report/_cmp_city.html" %}
{% include "report/_cmp_industry.html" %}
{% include "report/_top20.html" %}
```

A partial that renders differently per mode reads the single global `mode`. There is no second copy
of the table markup; a divergence between what Sagar reviewed in the browser and what he emailed to
somebody is a correctness bug waiting to happen.

### 3.2.3 The Jinja environment

```python
from jinja2 import Environment, PackageLoader, select_autoescape

def make_env(*, mode: str, app_base_url: str | None) -> Environment:
    """Jinja environment shared by the live app and the exporter.

    Autoescape is not optional here. Every string in this report - business names, research
    statements, source URLs - was scraped off the public internet by an LLM pipeline. Rendering any
    of it unescaped turns a research report into a stored-XSS delivery mechanism aimed at the one
    person who opens it every morning.
    """
    env = Environment(
        loader=PackageLoader("radar.web", "templates"),
        autoescape=select_autoescape(default_for_string=True, default=True),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,          # a typo'd variable fails the build, not the report
    )
    env.globals["mode"] = mode              # "LIVE" | "EXPORT"
    env.globals["app_base_url"] = app_base_url
    env.globals["is_export"] = (mode == "EXPORT")
    env.filters["dash"] = dash              # §3.5
    env.filters["pct"] = pct
    env.filters["inr"] = inr
    env.filters["safe_url"] = safe_url      # §3.2.6
    env.filters["ist"] = to_ist
    return env
```

Hard rules for anyone editing these templates:

| Rule | Why |
|---|---|
| `|safe` is banned outside `_macros.html`, and there it is used only on markup this module built | scraped-content XSS |
| `StrictUndefined` | a renamed column must break the build, not silently render blank and look like "no data" |
| No `{% if mode == 'EXPORT' %}` in `_table.html`, `_panel.html`, `_kpis.html` | content must be identical in both modes; only `_macros.act_link` branches |
| Every number goes through `|dash` | §3.5 |
| Every external URL goes through `|safe_url` | scheme allowlist |

### 3.2.4 Inlining: producing one file with no network dependencies

```python
def render_export(data: ReportData, *, app_base_url: str | None) -> str:
    """Render the EXPORT rendering and inline every asset it references."""
    env = make_env(mode="EXPORT", app_base_url=app_base_url)
    html = env.get_template("report/export.html").render(d=data)
    return inline_assets(html, static_dir=STATIC_DIR)
```

`export.html` references its assets with a marker the inliner understands, so the same file is also
servable in dev:

```html
<style data-inline="report.css">/* replaced */</style>
<script data-inline="report.js">/* replaced */</script>
```

```python
def inline_assets(html: str, *, static_dir: Path) -> str:
    """Replace every data-inline placeholder with the asset's literal bytes.

    Nothing is fetched and nothing is minified beyond comment stripping. The point is not a small
    file, it is a file that behaves identically in six months when the CDN that would have served
    the stylesheet has been rebranded twice.
    """
```

| Asset class | Treatment | Notes |
|---|---|---|
| CSS | literal text inlined into `<style>` | `/*!keep*/` comments retained, others stripped |
| JS | literal text inlined into `<script>` | never minified; a mangled report is undebuggable |
| Fonts | **none by default** | see below |
| Icons | inline `<svg>` in `_macros.html` | no icon font, no sprite sheet, no image requests |
| Chart glyphs | CSS-only bars (`width: N%`) | no charting library, no canvas |
| Logo | omitted; a text wordmark is used | avoids a 40 KB data URI on every export |

**Fonts.** The default stack is `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`, the same
stack `option_chain_reader`'s dashboard uses, which requires zero bytes and renders natively on
Sagar's Windows machine and on a phone. `config.yaml → report.embed_font: true` switches on a
base64 `@font-face` from a subset WOFF2 (latin + Devanagari city names) at a cost of roughly 34 KB
per export. Off by default: a self-contained report should not be 34 KB heavier for a typeface.

`@page` sizing, print rules and everything else stay in the same single stylesheet (§3.10) — a
second `media="print"` file would be a second thing to inline.

The **`LIVE`** rendering does the opposite: it links `/static/report.css` and `/static/report.js`
normally so the browser caches them across campaign pages. Same source files, two delivery
mechanisms.

### 3.2.5 The embedded data island

Research panels (§3.4.6) are the bulk of the document. Rendering all of them into DOM up front is
what makes a 5,000-row report unusable (§3.13). Instead the export embeds them as JSON and hydrates
one panel on expand:

```html
<script type="application/json" id="research-data">
{"biz_01JSAMPLE...A1": {"findings": [...], "opportunity": {...}, "sources": [...], "events": [...]}}
</script>
```

```python
def json_island(obj: object) -> Markup:
    """Serialise a JSON island that cannot terminate its own <script> element.

    A research statement containing the literal text "</script>" would otherwise close the block and
    dump the rest of the campaign into the page as HTML. Escaping the three characters that can
    start an HTML token is cheaper than trusting scraped text not to contain them.
    """
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return Markup(raw)
```

Read back with `JSON.parse(document.getElementById("research-data").textContent)`. This is data, not
executable code, and the CSP's `script-src` does not need widening for it because the browser never
executes a `type="application/json"` block.

Below the `report.panels_inline_max` threshold (default 800 businesses) the panels are *also*
rendered inline as `<details>` so that Ctrl+F and print-to-PDF find their text without any JS at
all. Above it, panels are JSON-only and §3.10's print path force-hydrates them first.

### 3.2.6 URL safety

Source URLs (§14) come from a research pipeline that reads the open web. They are rendered as
clickable links, which is a requirement — "The user must be able to open the source" — and therefore
a scheme allowlist is mandatory:

```python
_ALLOWED_SCHEMES = ("http", "https")

def safe_url(value: str | None) -> str | None:
    """Return the URL only if it is one a browser may safely navigate to.

    Source URLs are attacker-influenced: anything the research crawler read can end up here. A
    javascript: or data: href in a source panel executes in the context of the report, which in the
    LIVE rendering is Sagar's authenticated session.
    """
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES or not parsed.netloc:
        return None
    return urlunsplit(parsed)
```

A finding whose source URL fails this check still renders — with the source *name* and a
`title="URL withheld: unsupported scheme"` marker — because hiding the source entirely would make the
finding look unsourced, which has a specific meaning in §12. Every rendered external link carries
`target="_blank" rel="noopener noreferrer nofollow"`.

### 3.2.7 Build entry points

```python
def build_report(
    conn: sqlite3.Connection,
    campaign_id: str,
    *,
    mode: str = "EXPORT",
    app_base_url: str | None = None,
    out_dir: Path | None = None,
    user_id: str | None = None,
) -> ReportBuild:
    """Load, render, inline, write atomically, and record a report_exports row."""

def load_report_data(conn: sqlite3.Connection, campaign_id: str) -> ReportData: ...
def load_daily_data(conn: sqlite3.Connection, on_date: date) -> DailyData: ...      # §43
def render_report(data: ReportData, *, mode: str, app_base_url: str | None) -> str: ...
def inline_assets(html: str, *, static_dir: Path) -> str: ...
def report_filename(cities: Sequence[str], on_date: date, *, scope: str = "CAMPAIGN",
                    ext: str = "html", existing: Callable[[str], bool] | None = None) -> str: ...

# report_exports is owned by 11-audit-architecture.md §11.11.1 as amended by 01-data-model.md
# §1.2.1. The write is two-phase: the row exists before the file does, so a crashed build is a
# FAILED row rather than nothing at all.
def begin_export(conn, *, campaign_id: str | None, scope: str, scope_key: str | None,
                 fmt: str, title: str, filename: str, rel_path: str,
                 report_date: str, cities: str, filters_json: str,
                 contains_pii: bool, retention_class: str,
                 user_id: str | None, job_run_id: str | None) -> str:
    """INSERT a report_exports row with status='PENDING'. Returns rex_id."""

def finish_export(conn, export_id: str, *, path: Path, row_count: int,
                  content_sha256: str, data_sha256: str, data_rel_path: str) -> None:
    """UPDATE ... SET status='READY' with bytes and both hashes, after os.replace()."""

def fail_export(conn, export_id: str, *, error: str) -> None:
    """UPDATE ... SET status='FAILED', error=? . The CHECK forbids a FAILED row with no error."""
```

```python
@dataclass(frozen=True)
class ReportBuild:
    export_id: str          # rex_...
    path: Path
    bytes_written: int
    content_sha256: str     # the bytes of the file as written
    data_sha256: str        # canonical_json(payload), generation metadata stripped
    data_rel_path: str      # <filename>.data.json.gz, beside the report
    row_count: int
    generated_at: str       # ISO-8601 UTC
    duration_ms: int
```

Two hashes, because they answer different questions — `11-audit-architecture.md` §11.11.2 states the
rule and `01-data-model.md` §1.2.1 point 4 makes producing both this document's job.
`content_sha256` answers "is this the file I generated on 26 Aug"; `data_sha256` answers "are these
the numbers the database produced on 26 Aug", which is the only thing that makes `_CONTEXT.md`
invariant 5 checkable after the file has been emailed to somebody. The payload it hashes is

```python
payload = asdict(data)                          # ReportData, §3.3.4
for volatile in ("generated_at", "generated_by", "generator_version"):
    payload.pop(volatile, None)
blob = canonical_json(payload).encode("utf-8")  # sorted keys, no whitespace, "\n"-free
data_sha256 = hashlib.sha256(blob).hexdigest()
# gzip.compress(blob) -> data/reports/<campaign_id>/<filename>.data.json.gz -> data_rel_path
```

so regenerating an unchanged campaign gives a new `content_sha256` and an identical `data_sha256`.
That is what §3.12.4's drift banner compares against.

Writing is atomic, per `_CONTEXT.md` §1, and the row brackets the write:

```python
rex_id = begin_export(conn, ...)               # status='PENDING', no hashes yet
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(html, encoding="utf-8", newline="\n")
os.replace(tmp, path)          # never leaves a half-written report where a whole one was
finish_export(conn, rex_id, path=path, row_count=n,
              content_sha256=..., data_sha256=..., data_rel_path=...)   # status='READY'
```

CLI, matching the house `main.py` argparse shape:

```
python main.py report --campaign cmp_01JSAMPLE0000000000000001 --format html,csv,xlsx
python main.py report --campaign cmp_... --format pdf --pdf-engine chromium
python main.py report --daily 2026-08-26 --format html
python main.py report --campaign cmp_... --open        # write, then os.startfile()
```

### 3.2.8 Filename convention

Spec §5's example is `business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.html`. The rule that
produces it:

```
business_research_<city-slugs>_<YYYY-MM-DD>.<ext>
business_research_daily_<YYYY-MM-DD>.<ext>           # §43, scope="DAILY"
```

The keyword is `scope`, not `kind`, and it takes `report_exports.scope` values. `01-data-model.md`
§1.2.1 Amendment 1 retires the name `kind` from the export path entirely — it meant the file format
in one document and the report's subject in another — so nothing on the way from `build_report()` to
a `report_exports` row is called `kind` any more: the format is `fmt`, the subject is `scope`.
(`research_findings.kind`, `business_contacts.kind` and `outreach_events.kind` are untouched; they
are other tables and `_CONTEXT.md` §6 names them.)

| Step | Rule |
|---|---|
| 1 | City order is `campaign_cities.ordinal` — the order Sagar typed them, not alphabetical |
| 2 | NFKD-normalise, strip combining marks; Devanagari falls back to `unidecode` if installed, else the ASCII already stored in `campaign_cities.city` |
| 3 | Lowercase; replace every run of non-`[a-z0-9]` with a single `_`; strip leading/trailing `_` |
| 4 | A city that slugs to the empty string is dropped |
| 5 | Deduplicate, preserving first occurrence |
| 6 | Keep at most 4 slugs. Beyond that: first 3 + `_plus<N>more` (`N` = remaining count) |
| 7 | Date = `campaigns.created_at` converted to Asia/Kolkata, `%Y-%m-%d`. Sagar's "26 Aug" is IST, not UTC |
| 8 | Truncate the whole basename to 120 characters at a `_` boundary |
| 9 | If the target path exists with different content, append `_v2`, `_v3`, … before the extension |

```python
_SLUG_RE = re.compile(r"[^a-z0-9]+")

def slug_city(city: str) -> str:
    text = unicodedata.normalize("NFKD", city or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return _SLUG_RE.sub("_", text.casefold()).strip("_")


def report_filename(cities, on_date, *, scope="CAMPAIGN", ext="html", existing=None) -> str:
    """Build the report's filename.

    The city list is in the file name on purpose. Sagar's reports live in a folder for months and
    "report_3.html" tells him nothing; "business_research_dhule_shirpur_2026-08-26.html" tells him
    whether he needs to open it.
    """
    if scope == "DAILY":
        stem = f"business_research_daily_{on_date.isoformat()}"
    else:
        slugs, seen = [], set()
        for city in cities:
            s = slug_city(city)
            if s and s not in seen:
                seen.add(s)
                slugs.append(s)
        if len(slugs) > 4:
            slugs = slugs[:3] + [f"plus{len(slugs) - 3}more"]
        joined = "_".join(slugs) or "unspecified"
        stem = f"business_research_{joined}_{on_date.isoformat()}"
    if len(stem) > 120:
        stem = stem[:120].rsplit("_", 1)[0]
    name, n = f"{stem}.{ext}", 1
    while existing and existing(name):
        n += 1
        name = f"{stem}_v{n}.{ext}"
    return name
```

Worked examples (SAMPLE):

| Cities (in campaign order) | Date | Filename |
|---|---|---|
| Dhule, Shirpur, Nashik, Jalgaon | 2026-08-26 | `business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.html` |
| Dhule | 2026-08-26 | `business_research_dhule_2026-08-26.html` |
| Nashik, Jalgaon, Dhule, Shirpur, Malegaon, Chalisgaon | 2026-08-26 | `business_research_nashik_jalgaon_dhule_plus3more_2026-08-26.html` |
| `Nashik Road` | 2026-08-26 | `business_research_nashik_road_2026-08-26.html` |
| (daily digest) | 2026-08-26 | `business_research_daily_2026-08-26.html` |

CSV/XLSX/PDF reuse the same stem with a different extension, so all four formats of one campaign
sort next to each other in a directory listing.

### 3.2.9 Determinism

Two exports of an unchanged campaign must differ only in the generated-at timestamp. Therefore:

- every query has a total `ORDER BY` ending in `b.id`, so ties never reorder between runs;
- JSON islands use `sort_keys=False` but are built from ordered dicts assembled in query order;
- the only volatile value is `generated_at`, which is also the only reason `content_sha256` changes
  between two renders of unchanged data. `data_sha256` does not change, and that asymmetry is the
  point (§3.2.7).

`test_export_is_deterministic` renders twice with a frozen clock and asserts byte equality.

---

## 3.3 The data-loading query set

### 3.3.1 Columns this document depends on

Owned elsewhere. If any of these change, this document's SQL breaks and must change with them.

| Table | Columns the report reads |
|---|---|
| `campaigns` | `id`, `name`, `created_at`, `created_by`, `status`, `industries`, `size_filter`, `min_opportunity_score`, `research_depth`, `n_discovered`, `n_researched`, `n_qualified`, `n_skipped`, `n_verified`, `n_contacted` |
| `campaign_cities` | `campaign_id`, `city`, `ordinal` |
| `campaign_businesses` | `campaign_id`, `business_id`, `state`, `first_seen_at` |
| `businesses` | `id`, `name`, `city`, `industry`, `category`, `size_band`, `status`, `website`, `website_status`, `listing_url`, `address`, `first_discovered_at` |
| `business_contacts` | `business_id`, `kind`, `value_norm`, `value_display`, `domain`, `human_verified`, `is_active`, `source_note` |
| `research_runs` | `id`, `business_id`, `status`, `depth`, `started_at`, `finished_at`, `model_id`, `prompt_version` |
| `research_findings` | `id`, `business_id`, `research_run_id`, `kind`, `dimension`, `label`, `statement`, `confidence`, `confidence_pct`, `weight` |
| `sources` | `id`, `name`, `url`, `source_type`, `checked_at` |
| `finding_sources` | `finding_id`, `source_id`, `excerpt`, `checked_at` |
| `opportunities` | `business_id`, `is_current`, `score`, `band`, `confidence`, `confidence_pct`, `digital_maturity`, `operational_complexity`, `potential_problem`, `potential_solution`, `expected_benefit`, `est_value_inr`, `score_breakdown`, `model_id`, `prompt_version`, `computed_at` |
| `opportunity_modules` | `business_id`, `module`, `ordinal`, `rationale` |
| `verifications` | `business_id`, `verdict`, `verified_at`, `verified_by`, `superseded_at`, `note` |
| `selections` | `campaign_id`, `business_id`, `state`, `selected_at`, `blocking_gate` |
| `outreach_drafts` | `id`, `business_id`, `campaign_id`, `channel`, `policy_result`, `created_at`, `superseded_by` |
| `outreach_messages` | `id`, `business_id`, `campaign_id`, `channel`, `status`, `sent_at`, `queued_at`, `created_at`, `delivered_at`, `subject_final`, `sequence_no` |
| `outreach_events` | `message_id`, `kind`, `occurred_at`, `detail` |
| `responses` | `business_id`, `message_id`, `classification`, `confidence`, `received_at`, `body_excerpt` |
| `handoffs` | `business_id`, `state`, `outcome`, `demo_held_at`, `proposal_sent_at`, `won_value_inr`, `created_at` |
| `suppressions` | `scope`, `value_norm`, `business_id`, `reason`, `created_at`, `released_at` |
| `users` | `id`, `display_name` |

Three names in that table were arbitrated after this document's first draft and are recorded here so
nothing downstream re-learns the losing spelling:

| This document once read | Canonical | Ruling |
|---|---|---|
| `businesses.campaign_id` | `campaign_businesses.campaign_id` | `01-data-model.md` §1.2.2 — `businesses` <-> `campaigns` is many-to-many |
| `businesses.discovered_at` | `businesses.first_discovered_at` (global) / `campaign_businesses.first_seen_at` (per campaign) | `01-data-model.md` §1.2.2 point 2 |
| `handoffs.realised_value_inr` | `handoffs.won_value_inr` | `01-data-model.md` §1.2.4 ruling D6; `10-human-handoff.md` owns `handoffs` and prints the DDL |

`won_value_inr` is not a cosmetic rename: it is read by `Q_CMP_INDUSTRY` (§3.4.8), so the wrong
spelling raises `sqlite3.OperationalError: no such column` and §38 does not render at all. §3.15's
`test_report_queries_execute` runs every query in `report_queries.py` against the migrated schema so
a name that only exists in prose fails the build rather than the report.

Two columns are introduced by this document's needs and must be carried by `01-data-model.md`:

```sql
-- businesses: a tri-state, because "no website" and "we did not check" are different facts (§3.5)
website_status TEXT NOT NULL DEFAULT 'UNKNOWN'
    CHECK (website_status IN ('PRESENT','ABSENT','UNKNOWN')),

-- opportunities: nullable on purpose. §37 "Potential Revenue" sums only priced rows and renders an
-- em dash when nothing is priced, rather than inventing a number per business.
est_value_inr INTEGER CHECK (est_value_inr IS NULL OR est_value_inr >= 0),
```

### 3.3.2 `v_report_business` — the spine

One view flattens everything a report row needs. Every KPI in §7, every city card in §8, every
comparison row in §37 and §38 and the table in §9 aggregates over it. That is what stops twelve KPI
cards from drifting into twelve slightly different definitions of "qualified".

```sql
-- radar/migrations/049_v_report_business.sql   (was 021; renumbered by 01-data-model.md §1.13.2
-- because the view now depends on campaign_businesses, created by 004)
DROP VIEW IF EXISTS v_report_business;
CREATE VIEW v_report_business AS
WITH contact AS (
    SELECT c.business_id,
           COUNT(*)                                             AS n_contacts,
           MAX(CASE WHEN c.kind = 'EMAIL'    THEN 1 ELSE 0 END) AS has_email,
           MAX(CASE WHEN c.kind = 'PHONE'    THEN 1 ELSE 0 END) AS has_phone,
           MAX(CASE WHEN c.kind = 'WHATSAPP' THEN 1 ELSE 0 END) AS has_whatsapp
      FROM business_contacts c
     WHERE c.is_active = 1 AND c.human_verified = 1
     GROUP BY c.business_id
),
contact_any AS (
    SELECT c.business_id, COUNT(*) AS n_contacts_any
      FROM business_contacts c
     WHERE c.is_active = 1
     GROUP BY c.business_id
),
verif AS (
    SELECT v.business_id, MAX(v.verified_at) AS verified_at
      FROM verifications v
     WHERE v.verdict = 'VERIFIED' AND v.superseded_at IS NULL
     GROUP BY v.business_id
),
research AS (
    SELECT r.business_id,
           MAX(CASE WHEN r.status = 'COMPLETE' THEN 1 ELSE 0 END) AS research_complete,
           MAX(r.finished_at)                                     AS researched_at,
           MAX(r.depth)                                           AS research_depth
      FROM research_runs r
     GROUP BY r.business_id
),
sent AS (
    SELECT m.business_id,
           COUNT(*)       AS n_sent,
           MIN(m.sent_at) AS first_sent_at,
           MAX(m.sent_at) AS last_sent_at
      FROM outreach_messages m
     WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
     GROUP BY m.business_id
),
last_msg AS (
    SELECT m.business_id,
           m.status  AS last_message_status,
           m.channel AS last_channel
      FROM outreach_messages m
      JOIN (SELECT business_id,
                   MAX(COALESCE(sent_at, queued_at, created_at)) AS t
              FROM outreach_messages
             GROUP BY business_id) x
        ON x.business_id = m.business_id
       AND COALESCE(m.sent_at, m.queued_at, m.created_at) = x.t
),
resp AS (
    SELECT r.business_id,
           COUNT(*)            AS n_responses,
           MAX(r.received_at)  AS last_response_at,
           MAX(CASE WHEN r.classification IN ('INTERESTED','VERY_INTERESTED','DEMO_REQUESTED',
                                              'MEETING_REQUESTED','PRICE_REQUESTED')
                    THEN 1 ELSE 0 END) AS is_interested
      FROM responses r
     GROUP BY r.business_id
),
modules AS (
    SELECT om.business_id, COUNT(*) AS n_modules
      FROM opportunity_modules om
     GROUP BY om.business_id
),
suppressed AS (
    SELECT DISTINCT b.id AS business_id
      FROM businesses b
      LEFT JOIN business_contacts c ON c.business_id = b.id
      JOIN suppressions s
        ON s.released_at IS NULL
       AND ( (s.scope = 'BUSINESS' AND s.value_norm = b.id)
          OR (s.scope = 'EMAIL'    AND c.kind = 'EMAIL'    AND s.value_norm = c.value_norm)
          OR (s.scope = 'PHONE'    AND c.kind = 'PHONE'    AND s.value_norm = c.value_norm)
          OR (s.scope = 'WHATSAPP' AND c.kind = 'WHATSAPP' AND s.value_norm = c.value_norm)
          OR (s.scope = 'DOMAIN'   AND s.value_norm = c.domain) )
)
SELECT
    b.id                          AS business_id,
    cb.campaign_id,
    b.name,
    b.city,
    b.industry,
    b.category,
    b.size_band,
    b.status,
    b.website,
    b.website_status,
    b.listing_url,
    cb.first_seen_at                AS discovered_at,
    substr(cb.first_seen_at, 1, 10) AS discovered_on,

    o.score                       AS opportunity_score,
    o.band                        AS opportunity_band,
    o.confidence                  AS research_confidence,
    o.confidence_pct              AS research_confidence_pct,
    o.digital_maturity,
    o.operational_complexity,
    o.potential_problem,
    o.potential_solution,
    o.expected_benefit,
    o.est_value_inr,
    COALESCE(md.n_modules, 0)     AS n_modules,

    COALESCE(rs.research_complete, 0) AS research_complete,
    rs.researched_at,
    rs.research_depth,

    COALESCE(ct.n_contacts, 0)    AS n_contacts,
    COALESCE(ca.n_contacts_any, 0) AS n_contacts_any,
    COALESCE(ct.has_email, 0)     AS has_email,
    COALESCE(ct.has_phone, 0)     AS has_phone,
    COALESCE(ct.has_whatsapp, 0)  AS has_whatsapp,

    vf.verified_at,
    CASE WHEN vf.verified_at IS NOT NULL THEN 1 ELSE 0 END AS is_verified,

    COALESCE(sn.n_sent, 0)        AS n_sent,
    sn.first_sent_at,
    sn.last_sent_at,
    lm.last_message_status,
    lm.last_channel,

    COALESCE(rp.n_responses, 0)   AS n_responses,
    rp.last_response_at,
    COALESCE(rp.is_interested, 0) AS is_interested,

    CASE WHEN sp.business_id IS NOT NULL THEN 1 ELSE 0 END AS is_suppressed,

    -- "Qualified" has exactly one definition in this system, and it lives here.
    CASE WHEN COALESCE(rs.research_complete, 0) = 1
          AND o.score IS NOT NULL
          AND o.score >= COALESCE(cm.min_opportunity_score, 0)
          AND b.status NOT IN ('SKIPPED','REJECTED')
         THEN 1 ELSE 0 END        AS is_qualified,

    CASE WHEN b.status = 'CONTACT_READY' THEN 1 ELSE 0 END AS is_ready_for_outreach
FROM campaign_businesses cb
JOIN      businesses   b  ON b.id  = cb.business_id
JOIN      campaigns    cm ON cm.id = cb.campaign_id
LEFT JOIN opportunities o ON o.business_id = b.id AND o.is_current = 1
LEFT JOIN contact      ct ON ct.business_id = b.id
LEFT JOIN contact_any  ca ON ca.business_id = b.id
LEFT JOIN verif        vf ON vf.business_id = b.id
LEFT JOIN research     rs ON rs.business_id = b.id
LEFT JOIN sent         sn ON sn.business_id = b.id
LEFT JOIN last_msg     lm ON lm.business_id = b.id
LEFT JOIN resp         rp ON rp.business_id = b.id
LEFT JOIN modules      md ON md.business_id = b.id
LEFT JOIN suppressed   sp ON sp.business_id = b.id;
```

**The view's grain is one row per (campaign, business), not one row per business.** `businesses` is
one row per real-world business, globally unique on `business_key`, and campaign participation lives
in `campaign_businesses` — `01-data-model.md` §1.2.2 rules it, and the reason is that a suppression,
an attempt count and a response history all have to key on a `business_id` that does not change when
a second campaign rediscovers the same clinic. Three consequences for this document:

- **All twelve queries are unchanged.** Every one of them already filters
  `WHERE r.campaign_id = :campaign_id`, and `campaign_id` now comes from `cb` instead of `b`. A
  business covered by two campaigns appears in both reports, each with that campaign's own
  `min_opportunity_score` applied to `is_qualified`.
- **`discovered_at` is the per-campaign date.** The view projects `cb.first_seen_at` under that name,
  so §3.6.2's "Date discovered" filter, `discovered_on` grouping and the §43 daily all keep working
  and now mean "when *this* campaign first saw it". `businesses.first_discovered_at` is the global
  fact and is deliberately not what a campaign report renders.
- **The view never filters on `cb.state`.** An `EXCLUDED` membership row is still a business this
  campaign found, and §3.4.1.1's "Businesses Found" counts it. Filtering here would make the header
  number quietly shrink; `05-outreach-workflow.md` §5.4.2 adds `AND cb.state = 'INCLUDED'` where
  selection actually needs it.

`businesses.first_seen_campaign_id` exists for cohort attribution (`10-human-handoff.md` §10.9.3) and
is **never** a scope filter for a report. A report scoped by it would silently omit every
rediscovered business — invisible on a first campaign, and months later a report that is quietly
short. `01-data-model.md` §1.2.2 carries the test that greps for exactly that mistake.

Portability: the view uses only CTEs, `CASE`, `COALESCE` and `substr`. A Postgres port changes
`substr(x,1,10)` to `left(x,10)` and nothing else, which is why `discovered_on` is exposed here once
rather than recomputed in five queries.

Indexes the view leans on (declared in `01-data-model.md`):

```sql
CREATE INDEX ix_cb_campaign_state        ON campaign_businesses(campaign_id, state);
CREATE INDEX ix_businesses_geo           ON businesses(city_slug, industry, category);
CREATE INDEX ix_opportunities_current    ON opportunities(business_id) WHERE is_current = 1;
CREATE INDEX ix_research_runs_business   ON research_runs(business_id, status, finished_at);
CREATE INDEX ix_messages_business_status ON outreach_messages(business_id, status, sent_at);
CREATE INDEX ix_responses_business       ON responses(business_id, received_at);
CREATE INDEX ix_findings_business_run    ON research_findings(business_id, research_run_id, kind);
```

### 3.3.3 The twelve queries, and the no-N+1 rule

A report load is **twelve queries regardless of how many businesses it contains.** Per-row data is
fetched in bulk and grouped in Python. A report that issues one query per business takes tens of
seconds at 5,000 rows and gets rewritten the first time a campaign grows.

| # | Constant in `radar/report_queries.py` | Feeds | Params |
|---|---|---|---|
| Q1 | `Q_CAMPAIGN` | §6 header, filename, drift check | `:campaign_id` |
| Q2 | `Q_KPIS` | §7 twelve cards | `:campaign_id` |
| Q3 | `Q_CITY_SUMMARY` | §8 city cards | `:campaign_id` |
| Q4 | `Q_ROWS` | §3/§4 tabs and §9 table | `:campaign_id` |
| Q5 | `Q_FINDINGS` | §12 research panel | `:campaign_id` |
| Q6 | `Q_OPPORTUNITY` | §13 opportunity block, `score_breakdown` | `:campaign_id` |
| Q7 | `Q_MODULES` | §13 recommended modules | `:campaign_id` |
| Q8 | `Q_CONTACTS` | §9 Contact Available, §11 detail | `:campaign_id` |
| Q9 | `Q_HISTORY` | §32 history panel, §40 HISTORY action | `:campaign_id` |
| Q10 | `Q_CMP_CITY` | §37 | `:campaign_id` |
| Q11 | `Q_CMP_INDUSTRY` | §38 | `:campaign_id` |
| Q12 | `Q_TOP20` | §44 | `:campaign_id`, `:limit` |

The daily view (§43) uses a separate set, `Q_DAILY_*`, scoped by date instead of campaign.

```python
def load_report_data(conn: sqlite3.Connection, campaign_id: str) -> ReportData:
    """Twelve queries, one pass, no per-row SQL.

    Grouping happens here rather than in the templates so a template can never accidentally trigger
    a lazy query while rendering row 3,000 of a table.
    """
    conn.row_factory = sqlite3.Row
    p = {"campaign_id": campaign_id}
    campaign = Campaign.from_row(conn.execute(Q_CAMPAIGN, p).fetchone())
    kpis     = Kpis.from_row(conn.execute(Q_KPIS, p).fetchone())
    cities   = [CitySummary.from_row(r) for r in conn.execute(Q_CITY_SUMMARY, p)]
    rows     = [BusinessRow.from_row(r) for r in conn.execute(Q_ROWS, p)]
    findings = group_by(conn.execute(Q_FINDINGS, p),    "business_id", Finding.from_row)
    opps     = index_by(conn.execute(Q_OPPORTUNITY, p), "business_id", Opportunity.from_row)
    modules  = group_by(conn.execute(Q_MODULES, p),     "business_id", Module.from_row)
    contacts = group_by(conn.execute(Q_CONTACTS, p),    "business_id", Contact.from_row)
    history  = group_by(conn.execute(Q_HISTORY, p),     "business_id", HistoryEvent.from_row)
    ...
```

### 3.3.4 `ReportData`

```python
@dataclass(frozen=True)
class ReportData:
    campaign:      Campaign
    header:        HeaderFacts                    # §6
    kpis:          Kpis                           # §7
    city_cards:    list[CitySummary]              # §8
    tree:          list[CityNode]                 # §3 -> §4 nesting
    rows:          list[BusinessRow]              # §9
    findings:      dict[str, list[Finding]]       # §12, keyed by business_id
    opportunities: dict[str, Opportunity]         # §13
    modules:       dict[str, list[Module]]        # §13
    contacts:      dict[str, list[Contact]]       # §11
    history:       dict[str, list[HistoryEvent]]  # §32
    cmp_city:      list[CityCompareRow]           # §37
    cmp_industry:  list[IndustryCompareRow]       # §38
    top20:         list[TopOpportunity]           # §44
    generated_at:  str                            # ISO-8601 UTC
    generated_by:  str | None                     # users.display_name
    mode:          str                            # "LIVE" | "EXPORT"
    warnings:      list[str]                      # counter drift, unscored rows, stale verifications


@dataclass(frozen=True)
class CityNode:
    city: str
    ordinal: int
    industries: list[IndustryNode]


@dataclass(frozen=True)
class IndustryNode:
    industry: str                                 # HEALTHCARE | EDUCATION | ...
    categories: list[CategoryGroup]


@dataclass(frozen=True)
class CategoryGroup:
    category: str                                 # HOSPITAL | SCHOOL | ...
    row_ids: list[str]
```

Every dataclass follows the house `from_row()` convention:

```python
@dataclass(frozen=True)
class BusinessRow:
    business_id: str
    name: str
    city: str
    industry: str
    category: str
    size_band: str
    status: str
    website: str | None
    website_status: str
    digital_maturity: int | None
    opportunity_score: int | None
    opportunity_band: str | None
    potential_solution: str | None
    research_confidence: str | None
    is_verified: bool
    verified_at: str | None
    n_sent: int
    last_message_status: str | None
    n_responses: int
    is_interested: bool
    is_suppressed: bool
    n_contacts: int
    has_email: bool
    has_phone: bool
    has_whatsapp: bool
    discovered_on: str
    selectable: bool
    blocking_gate: str | None
    draft_id: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "BusinessRow":
        return cls(
            business_id=row["business_id"],
            name=row["name"],
            city=row["city"],
            ...
            digital_maturity=row["digital_maturity"],    # may be None - do NOT coalesce to 0
            opportunity_score=row["opportunity_score"],  # may be None - do NOT coalesce to 0
            research_confidence=row["research_confidence"],
            ...
        )
```

`from_row()` never coalesces a nullable metric to zero. That one line of discipline is what makes
§3.5's em-dash rendering possible: once a `None` has become a `0` in Python, no template downstream
can tell "we looked and found none" from "we never measured this".

---

## 3.4 Document structure

Reading order, top to bottom, in both renderings:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 1  Header block                       §6   nine facts                        │
│ 2  Read-only / staleness banner       §3.1.4  (EXPORT only)                  │
│ 3  KPI card row                       §7   twelve cards                      │
│ 4  City summary cards                 §8   five figures per city             │
│ 5  Filter bar + search + sort         §39  eleven filters                    │
│ 6  City tabs -> industry tabs         §3, §4                                 │
│      └─ category groups                                                      │
│           └─ business table           §9, §10                                │
│                └─ research panel      §11, §12, §13, §14                     │
│ 7  Selection bar (sticky)             §18  per-city counts                   │
│ 8  Top 20 opportunities               §44                                    │
│ 9  City comparison                    §37                                    │
│ 10 Industry comparison                §38                                    │
│ 11 Footer: provenance                 model ids, prompt versions, row counts  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.4.1 Header block (§6)

Nine facts, in the order §6 gives them. Every count is a live SQL aggregate; the `campaigns.n_*`
counter columns are read **only** to detect drift (§3.4.1.3), never to render.

| # | Label | Source |
|---|---|---|
| 1 | `AI BUSINESS OPPORTUNITY RESEARCH` | literal wordmark |
| 2 | Campaign | `campaigns.name` (e.g. SAMPLE `Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026`) |
| 3 | Search Date | `campaigns.created_at` rendered in Asia/Kolkata |
| 4 | Number of Businesses Found | `h_found` |
| 5 | Number Researched | `h_researched` |
| 6 | Number Qualified | `h_qualified` |
| 7 | Number Skipped | `h_skipped` |
| 8 | Number Requiring Verification | `h_needs_verification` |
| 9 | Number Ready for Outreach | `h_ready` |

```sql
-- radar/report_queries.py :: Q_CAMPAIGN   (Q1)
SELECT
    c.id                                   AS campaign_id,
    c.name,
    c.created_at,
    c.status                               AS campaign_status,
    c.research_depth,
    c.size_filter,
    c.industries,
    c.min_opportunity_score,
    u.display_name                         AS created_by_name,
    (SELECT group_concat(cc.city, ', ')
       FROM (SELECT city FROM campaign_cities
              WHERE campaign_id = c.id ORDER BY ordinal) cc)   AS cities_display,

    -- fact 4: everything discovery produced, including rows research never reached
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id)                              AS h_found,

    -- fact 5: research actually completed
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.research_complete = 1)  AS h_researched,

    -- fact 6: the single definition from v_report_business.is_qualified
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.is_qualified = 1)       AS h_qualified,

    -- fact 7: skipped by the pipeline plus rejected by Sagar; the tooltip splits them
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.status IN ('SKIPPED','REJECTED'))  AS h_skipped,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.status = 'SKIPPED')     AS h_skipped_pipeline,
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.status = 'REJECTED')    AS h_rejected,

    -- fact 8: researched, not yet adjudicated by a human
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id
        AND r.status IN ('AI_RESEARCHED','NEEDS_VERIFICATION'))          AS h_needs_verification,

    -- fact 9: verified AND carrying a human-confirmed contact
    (SELECT COUNT(*) FROM v_report_business r
      WHERE r.campaign_id = c.id AND r.status = 'CONTACT_READY')         AS h_ready,

    -- drift detection only; never rendered as a fact
    c.n_discovered, c.n_researched, c.n_qualified,
    c.n_skipped, c.n_verified, c.n_contacted
FROM campaigns c
LEFT JOIN users u ON u.id = c.created_by
WHERE c.id = :campaign_id;
```

#### 3.4.1.1 Definitions that the header pins down

These are stated in the report footer as well, because a number without its definition is a number
Sagar has to re-derive every time he reads it.

| Fact | Definition |
|---|---|
| Businesses Found | every `campaign_businesses` row for the campaign, whatever the business's status and whatever the membership `state`. Identical to the old "every `businesses` row" definition for a first campaign, and correctly inclusive of rediscoveries for a later one (`01-data-model.md` §1.2.2 point 4) |
| Researched | at least one `research_runs` row with `status = 'COMPLETE'` |
| Qualified | research complete **and** a current opportunity score **and** score >= `campaigns.min_opportunity_score` **and** status not `SKIPPED`/`REJECTED` |
| Skipped | `status IN ('SKIPPED','REJECTED')`; `title` attribute shows `n skipped by the pipeline, m rejected by you` |
| Requiring Verification | `status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')` |
| Ready for Outreach | `status = 'CONTACT_READY'` — verified *and* a human-confirmed contact exists (see `05-outreach-workflow.md` §5.4.1) |

The header numbers do **not** sum to Businesses Found and are not presented as if they do. A business
can be counted in Researched and in Qualified and in Ready for Outreach simultaneously.

#### 3.4.1.2 Markup (SAMPLE values)

```html
<header class="rpt-header">
  <div class="wordmark">AI BUSINESS OPPORTUNITY RESEARCH</div>
  <h1>Dhule-Shirpur-Nashik-Jalgaon &mdash; 26 Aug 2026</h1>
  <div class="sub">
    <span>Cities: Dhule, Shirpur, Nashik, Jalgaon</span>
    <span>Search date: 26 Aug 2026, 07:12 IST</span>
    <span>Depth: DEEP</span>
    <span>Min score: 70</span>
    <span>Size filter: MEDIUM, LARGE</span>
  </div>
  <dl class="facts">
    <div><dt>Businesses found</dt>        <dd class="num">148</dd></div>
    <div><dt>Researched</dt>              <dd class="num">141</dd></div>
    <div><dt>Qualified</dt>               <dd class="num">63</dd></div>
    <div><dt>Skipped</dt>                 <dd class="num" title="5 skipped by the pipeline, 2 rejected by you">7</dd></div>
    <div><dt>Requiring verification</dt>  <dd class="num">51</dd></div>
    <div><dt>Ready for outreach</dt>      <dd class="num">12</dd></div>
  </dl>
</header>
```

#### 3.4.1.3 Counter drift

`campaigns.n_discovered` and friends exist for the campaign dashboard (§36) and are maintained by the
job pipeline. They are cheap to get wrong — a crashed worker, a manual DB edit, a re-run. The report
compares each counter to its live aggregate and, on a mismatch, renders the **aggregate** and pushes
a line into `ReportData.warnings`, which the footer prints:

```
Note: campaigns.n_qualified says 61, live count is 63. The report shows 63.
```

It never renders the counter, and it never silently repairs it — repairing counters from a read path
is how a reporting bug becomes a data bug.

---

### 3.4.2 KPI card row (§7)

Twelve cards, in §7's order. All twelve come from one query so the row is internally consistent even
if a job writes rows mid-render.

```sql
-- radar/report_queries.py :: Q_KPIS   (Q2)
SELECT
  COUNT(*)                                                                       AS k_total,
  SUM(CASE WHEN is_qualified = 1                       THEN 1 ELSE 0 END)        AS k_qualified,
  SUM(CASE WHEN opportunity_score >= 80                THEN 1 ELSE 0 END)        AS k_high,
  SUM(CASE WHEN opportunity_score BETWEEN 60 AND 79    THEN 1 ELSE 0 END)        AS k_medium,
  SUM(CASE WHEN opportunity_score < 60                 THEN 1 ELSE 0 END)        AS k_low,
  SUM(CASE WHEN opportunity_score IS NULL              THEN 1 ELSE 0 END)        AS k_unscored,
  SUM(CASE WHEN website_status = 'PRESENT'             THEN 1 ELSE 0 END)        AS k_web_yes,
  SUM(CASE WHEN website_status = 'ABSENT'              THEN 1 ELSE 0 END)        AS k_web_no,
  SUM(CASE WHEN website_status = 'UNKNOWN'             THEN 1 ELSE 0 END)        AS k_web_unknown,
  SUM(CASE WHEN potential_solution IS NOT NULL
             AND n_modules > 0                         THEN 1 ELSE 0 END)        AS k_software_opp,
  SUM(CASE WHEN status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')
                                                       THEN 1 ELSE 0 END)        AS k_need_verif,
  SUM(CASE WHEN is_verified = 1                        THEN 1 ELSE 0 END)        AS k_verified,
  SUM(CASE WHEN n_sent > 0                             THEN 1 ELSE 0 END)        AS k_contacted,
  SUM(CASE WHEN is_interested = 1                      THEN 1 ELSE 0 END)        AS k_interested,
  -- denominators used by the sub-lines; kept here so no card recomputes one
  SUM(CASE WHEN opportunity_score IS NOT NULL          THEN 1 ELSE 0 END)        AS k_scored,
  SUM(CASE WHEN research_complete = 1                  THEN 1 ELSE 0 END)        AS k_researched
FROM v_report_business
WHERE campaign_id = :campaign_id;
```

The twelve cards, each with the aggregate behind it and what it renders when the aggregate has no
rows to work with:

| # | Card | Column | Definition | Empty-data rendering |
|---|---|---|---|---|
| 1 | Total Businesses | `k_total` | every row in the campaign | `—` when the campaign has no `businesses` rows at all (a campaign that has not run yet) |
| 2 | Qualified | `k_qualified` | `is_qualified = 1` | `—` if `k_researched = 0`; else `0` |
| 3 | High Opportunity | `k_high` | `opportunity_score >= 80` | `—` if `k_scored = 0`; else `0` |
| 4 | Medium Opportunity | `k_medium` | `60 <= score <= 79` | `—` if `k_scored = 0`; else `0` |
| 5 | Low Opportunity | `k_low` | `score < 60` | `—` if `k_scored = 0`; else `0` |
| 6 | Website Available | `k_web_yes` | `website_status = 'PRESENT'` | `0` (absence is a real finding) |
| 7 | No Website | `k_web_no` | `website_status = 'ABSENT'` | `0` |
| 8 | Potential Software Opportunity | `k_software_opp` | a current opportunity with a `potential_solution` **and** at least one `opportunity_modules` row | `—` if `k_researched = 0`; else `0` |
| 9 | Need Verification | `k_need_verif` | `status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')` | `0` |
| 10 | Verified | `k_verified` | a live `verifications` row with `verdict='VERIFIED'` and `superseded_at IS NULL` | `0` |
| 11 | Already Contacted | `k_contacted` | `n_sent > 0`, i.e. at least one `outreach_messages` row in `SENT`/`DELIVERED`/`BOUNCED` | `0` |
| 12 | Interested | `k_interested` | a `responses` row classified `INTERESTED`, `VERY_INTERESTED`, `DEMO_REQUESTED`, `MEETING_REQUESTED` or `PRICE_REQUESTED` | `0` |

Rules the card row obeys:

- **Cards 3+4+5 do not sum to card 1.** Unscored businesses are excluded from all three bands. The
  card group carries a footnote: `k_unscored not scored yet` — rendered only when `k_unscored > 0`.
- **Cards 6+7 do not sum to card 1 either.** `k_web_unknown` sits in card 6's sub-line as
  `k_web_unknown unknown`. This is the clearest case for §3.5: "No Website: 41" is a sales signal,
  "we never checked 41 of them" is a research gap, and a report that renders both as `41` is lying
  about one of them.
- **Every card carries its denominator** in a `title`, e.g. `title="63 of 141 researched"`.
- **Card 12 is the product metric** (§54). It gets the `is-primary` class and sits visually apart:
  §54 says do not optimise for messages sent, so the card that could be mistaken for a vanity metric
  (card 11) is not the one that is emphasised.

Card markup and its macro:

```jinja
{% macro kpi(label, value, sub=None, denom=None, tone="neutral", primary=False) %}
<div class="kpi tone-{{ tone }}{{ ' is-primary' if primary }}">
  <div class="kpi-label">{{ label }}</div>
  <div class="kpi-value num"{% if denom %} title="{{ denom }}"{% endif %}>{{ value|dash }}</div>
  {% if sub %}<div class="kpi-sub">{{ sub }}</div>{% endif %}
</div>
{% endmacro %}
```

```jinja
{{ m.kpi("Total businesses", d.kpis.total, denom="discovered in this campaign") }}
{{ m.kpi("Qualified", d.kpis.qualified,
         sub="score >= %d"|format(d.campaign.min_opportunity_score),
         denom="%s of %s researched"|format(d.kpis.qualified, d.kpis.researched)) }}
{{ m.kpi("High opportunity", d.kpis.high, sub="score 80-100", tone="green") }}
{{ m.kpi("Medium opportunity", d.kpis.medium, sub="score 60-79", tone="yellow") }}
{{ m.kpi("Low opportunity", d.kpis.low, sub="score below 60", tone="neutral") }}
{{ m.kpi("Website available", d.kpis.web_yes,
         sub=(("%d unknown"|format(d.kpis.web_unknown)) if d.kpis.web_unknown else None),
         tone="blue") }}
{{ m.kpi("No website", d.kpis.web_no, tone="blue") }}
{{ m.kpi("Potential software opportunity", d.kpis.software_opp,
         sub="has a named solution and modules") }}
{{ m.kpi("Need verification", d.kpis.need_verif, tone="yellow") }}
{{ m.kpi("Verified", d.kpis.verified, tone="green") }}
{{ m.kpi("Already contacted", d.kpis.contacted) }}
{{ m.kpi("Interested", d.kpis.interested, tone="green", primary=True) }}
```

Cards are also clickable in both modes: clicking "High opportunity" writes `score=80-100` into the
filter state (§3.6) and scrolls to the table. This is pure client-side filter manipulation, works
offline, and is the fastest route from "the KPI surprised me" to "show me which rows".

---

### 3.4.3 City summary cards (§8)

One card per city in `campaign_cities.ordinal` order, five figures each. §8 is explicit: *"These
numbers must come from actual database results. Never fabricate them."*

```sql
-- radar/report_queries.py :: Q_CITY_SUMMARY   (Q3)
-- LEFT JOIN from campaign_cities so a targeted city that returned nothing still gets a card.
-- A missing card would read as "we did not search Shirpur"; a card of zeros reads as
-- "we searched Shirpur and found nothing", which is the true statement.
SELECT
    cc.city,
    cc.ordinal,
    COUNT(r.business_id)                                                    AS c_found,
    SUM(CASE WHEN r.is_qualified = 1          THEN 1 ELSE 0 END)            AS c_qualified,
    SUM(CASE WHEN r.opportunity_score >= 80   THEN 1 ELSE 0 END)            AS c_high,
    SUM(CASE WHEN r.is_verified = 1           THEN 1 ELSE 0 END)            AS c_verified,
    SUM(CASE WHEN r.is_ready_for_outreach = 1 THEN 1 ELSE 0 END)            AS c_ready,
    SUM(CASE WHEN r.opportunity_score IS NOT NULL THEN 1 ELSE 0 END)        AS c_scored,
    SUM(CASE WHEN r.research_complete = 1     THEN 1 ELSE 0 END)            AS c_researched
FROM campaign_cities cc
LEFT JOIN v_report_business r
       ON r.campaign_id = cc.campaign_id
      AND r.city = cc.city
WHERE cc.campaign_id = :campaign_id
GROUP BY cc.city, cc.ordinal
ORDER BY cc.ordinal;
```

| Figure | Column | `—` when |
|---|---|---|
| Businesses Found | `c_found` | never (0 is a real answer: discovery ran and found nothing) |
| Qualified | `c_qualified` | `c_researched = 0` |
| High Opportunity | `c_high` | `c_scored = 0` |
| Verified | `c_verified` | never |
| Ready for Outreach | `c_ready` | never |

A city whose `c_found = 0` renders the card with a muted class and the line
`Discovery returned no businesses for this city.` — not an empty card, and not a hidden one.

```html
<section class="city-cards" aria-label="City summary">
  <article class="city-card" data-city="DHULE">
    <h3>Dhule</h3>
    <dl>
      <div><dt>Found</dt>              <dd class="num">42</dd></div>
      <div><dt>Qualified</dt>          <dd class="num" title="of 40 researched">18</dd></div>
      <div><dt>High opportunity</dt>   <dd class="num" title="of 40 scored">7</dd></div>
      <div><dt>Verified</dt>           <dd class="num">9</dd></div>
      <div><dt>Ready for outreach</dt> <dd class="num">4</dd></div>
    </dl>
    <a class="card-link" href="#tab=DHULE">Open Dhule</a>
  </article>
  ...
</section>
```
(SAMPLE figures.)

Clicking a city card sets the city tab and applies `city=DHULE` to the filter state, so the KPI row
above it stays global while the table below narrows.

---

### 3.4.4 City tabs, industry tabs, category groups (§3, §4)

§3 requires the report to organise businesses by city, each city carrying industry sections. §4
requires a further grouping by category inside each city. The structure is therefore three levels
deep and is rendered as **tabs -> tabs -> headed groups**, not as three levels of tabs, because a
third tab strip is unusable on a laptop and impossible on a phone.

```
[ ALL ] [ DHULE ] [ SHIRPUR ] [ NASHIK ] [ JALGAON ]          <- city tablist
        [ ALL ] [ HEALTHCARE 12 ] [ EDUCATION 7 ] [ ... ]      <- industry tablist (per city)

          HOSPITAL  (5)                                        <- category group heading
          ┌──────────────────────────────────────────┐
          │ business table rows                      │
          └──────────────────────────────────────────┘
          DIAGNOSTIC_CENTER  (4)
          ┌──────────────────────────────────────────┐
```

Decisions:

| Decision | Reason |
|---|---|
| One `<table>` per city+industry pane; category groups are `<tbody>` blocks with a `<tr class="group-head">` | column widths stay aligned across categories; one table per category would produce ragged columns |
| Both tablists include an `ALL` tab, selected by default | the first thing Sagar does most mornings is sort everything by score, not drill into Dhule |
| Industry tabs are rendered per city, from that city's data | an industry with no businesses in Nashik gets no Nashik tab, rather than an empty tab |
| Tab counts are rendered in the tab label | `HEALTHCARE 12` — the tab strip doubles as a per-industry summary |
| §3's industry list plus `_CONTEXT.md` §6 | `HEALTHCARE`, `EDUCATION`, `AUTOMOBILE`, `MANUFACTURING`, `RETAIL`, `HOSPITALITY`, `DISTRIBUTION`, `REAL_ESTATE`, `PROFESSIONAL_SERVICES`, `OTHER`. §3 omits `REAL_ESTATE` and `PROFESSIONAL_SERVICES`; the canonical enum wins and they get tabs |
| Industry tab order is the enum order above, not count order | tab positions stay put between days, so muscle memory works |
| Category order inside a pane: descending group size, then category name | the biggest group is the one worth reading first |
| `OTHER` sorts last in both lists | |

Display labels come from one map, so the report never shows a raw enum:

```python
INDUSTRY_LABEL = {
    "HEALTHCARE": "Healthcare", "EDUCATION": "Education", "AUTOMOBILE": "Automobile",
    "MANUFACTURING": "Manufacturing", "RETAIL": "Retail", "HOSPITALITY": "Hospitality",
    "DISTRIBUTION": "Distribution", "REAL_ESTATE": "Real estate",
    "PROFESSIONAL_SERVICES": "Professional services", "OTHER": "Other",
}
CATEGORY_LABEL = {
    "HOSPITAL": "Hospitals", "DIAGNOSTIC_CENTER": "Diagnostic centres", "SCHOOL": "Schools",
    "COLLEGE": "Colleges", "MANUFACTURER": "Manufacturers", "DISTRIBUTOR": "Distributors",
    "VEHICLE_DEALER": "Vehicle dealers", "GARAGE": "Garages", "HOTEL": "Hotels",
    "RESTAURANT": "Restaurants", "BAKERY": "Bakeries", "RETAIL_STORE": "Retail stores",
    "REAL_ESTATE_AGENCY": "Real estate agencies", "OTHER": "Other",
}
```

Markup, with real ARIA so keyboard and screen-reader use works (§50 "professional enough to present
internally"):

```html
<div class="tabs" role="tablist" aria-label="City">
  <button role="tab" id="t-ALL"     aria-selected="true"  aria-controls="p-ALL"     data-city="ALL">All <span class="cnt">148</span></button>
  <button role="tab" id="t-DHULE"   aria-selected="false" aria-controls="p-DHULE"   data-city="DHULE">Dhule <span class="cnt">42</span></button>
  ...
</div>

<section role="tabpanel" id="p-DHULE" aria-labelledby="t-DHULE" hidden>
  <div class="tabs sub" role="tablist" aria-label="Industry in Dhule">
    <button role="tab" aria-selected="true" data-industry="ALL">All <span class="cnt">42</span></button>
    <button role="tab" aria-selected="false" data-industry="HEALTHCARE">Healthcare <span class="cnt">12</span></button>
    ...
  </div>
  <table class="btable" data-city="DHULE" data-industry="HEALTHCARE"> ... </table>
</section>
```

Tab behaviour: `ArrowLeft`/`ArrowRight` move, `Home`/`End` jump, `aria-selected` and `hidden` are
kept in sync, and the active pair is written to the URL hash as `tab=DHULE|HEALTHCARE` (§3.6.5).

**Tabs and filters interact, and the rule is stated once:** the tab is a *view*, the filters are a
*predicate*. A row is visible when it is in the active pane **and** passes every filter. Selecting
the `NASHIK` tab while the city filter says `DHULE` yields an empty pane and an explicit message —
`The Nashik tab has 18 rows, but your city filter excludes them. Clear the city filter.` — with a
one-click "clear" affordance, rather than a mysteriously empty table.

---

### 3.4.5 The business table (§9, §10)

§9's fourteen columns, exactly, in that order:

| # | Column | Cell content | Sortable | Data attribute |
|---|---|---|---|---|
| 1 | Select | checkbox, enabled only per §3.7 | no | `data-sel`, `data-block` |
| 2 | Business | name + a `↗` to `website`, second line `category · listing` | text | `data-q` |
| 3 | City | display label | text | `data-city` |
| 4 | Category | display label (§4) | text | `data-cat` |
| 5 | Size | badge `MICRO/SMALL/MEDIUM/LARGE/UNKNOWN` | ordinal | `data-size` |
| 6 | Website | `Yes` link / `No` / `—` (§3.5) | text | `data-web` |
| 7 | Digital Maturity | 0-100 + a 40px CSS bar | numeric | `data-dm` |
| 8 | Opportunity Score | score badge, band-coloured (§3.9) | numeric | `data-score` |
| 9 | Potential Solution | `opportunities.potential_solution`, truncated to 48 chars with full text in `title` | text | — |
| 10 | Contact Available | channel chips `E` `P` `W`, or `None` | ordinal by count | `data-contact` |
| 11 | Research Confidence | confidence badge `HIGH/MEDIUM/LOW` + `confidence_pct` in `title` | ordinal | `data-conf` |
| 12 | Verification Status | verification badge (§3.9.4) | ordinal | `data-verif` |
| 13 | Outreach Status | outreach badge (§3.9.5) | ordinal | `data-outreach` |
| 14 | Actions | action chips per §3.8 | no | — |

§9's "Industry" is not a column: it is the tab the row is under, and it is repeated in the row's
`data-industry` attribute so the filter and the export can still key off it. The `ALL/ALL` pane adds
an Industry column between City and Category, because there the grouping context is gone. That is
the only column-set difference anywhere in the report.

```sql
-- radar/report_queries.py :: Q_ROWS   (Q4)
-- The report renders selectability; it never computes it. blocking_gate comes from the same
-- expression 05-outreach-workflow.md uses, so the greyed checkbox and the live app agree.
SELECT
    r.*,
    sel.state                                   AS selection_state,
    d.id                                        AS draft_id,
    d.policy_result                             AS draft_policy_result,
    CASE
      WHEN r.is_suppressed = 1                                      THEN 'A_SUPPRESSED'
      WHEN r.status IN ('INTERESTED','HUMAN_HANDOFF')               THEN 'D_HUMAN_OWNED'
      WHEN r.status IN ('REJECTED','SKIPPED')                       THEN 'D_VERIFICATION_REVOKED'
      WHEN r.status NOT IN ('CONTACT_READY','CONTACTED','RESPONDED') THEN 'D_NOT_VERIFIED'
      WHEN r.verified_at IS NULL                                    THEN 'D_NOT_VERIFIED'
      WHEN r.n_contacts = 0                                         THEN 'E_CONTACT_MISSING'
      ELSE NULL
    END                                         AS blocking_gate
FROM v_report_business r
LEFT JOIN selections sel
       ON sel.campaign_id = r.campaign_id
      AND sel.business_id = r.business_id
      AND sel.state <> 'REMOVED'
LEFT JOIN outreach_drafts d
       ON d.business_id = r.business_id
      AND d.campaign_id = r.campaign_id
      AND d.superseded_by IS NULL
WHERE r.campaign_id = :campaign_id
ORDER BY r.city,
         r.industry,
         r.category,
         CASE WHEN r.opportunity_score IS NULL THEN 1 ELSE 0 END,   -- unscored sink to the bottom
         r.opportunity_score DESC,
         r.name,
         r.business_id;                                             -- total order, for determinism
```

The report's `blocking_gate` is deliberately the **grid approximation** from
`05-outreach-workflow.md` §5.4.2, not the full `check_send_eligibility()`. It never says "selectable"
where the full engine would say "blocked" for the gates it evaluates; the frequency and per-channel
gates are re-checked when Sagar reaches the outreach workspace. The report is allowed to be
optimistic in a way that costs a click, never in a way that costs a send.

#### 3.4.5.1 A rendered row (§10)

```html
<tr class="brow"
    data-id="biz_01JSAMPLE00000000000000A1"
    data-city="DHULE" data-industry="HEALTHCARE" data-cat="HOSPITAL"
    data-size="MEDIUM" data-score="86" data-web="PRESENT" data-dm="62"
    data-conf="MEDIUM" data-verif="NEEDS_VERIFICATION" data-contact="EMAIL"
    data-outreach="NOT_CONTACTED" data-disc="2026-08-26"
    data-sel="0" data-block="D_NOT_VERIFIED"
    data-q="abc hospital dhule healthcare hospital hospital operations platform">
  <td class="c-sel">
    <input type="checkbox" class="rowsel" disabled
           aria-describedby="blk-A1"
           title="This business still needs your verification.">
    <span id="blk-A1" class="sr-only">This business still needs your verification.</span>
  </td>
  <td class="c-name">
    <a class="bname" href="#biz-A1">ABC Hospital</a>
    <a class="ext" href="https://abc-hospital.example" target="_blank"
       rel="noopener noreferrer nofollow" title="abc-hospital.example">&#8599;</a>
    <div class="sub">Hospital &middot; Dhule</div>
  </td>
  <td>Dhule</td>
  <td>Hospitals</td>
  <td><span class="badge size">MEDIUM</span></td>
  <td class="c-web"><a href="https://abc-hospital.example" target="_blank" rel="noopener noreferrer nofollow">Yes</a></td>
  <td class="c-dm num"><span class="bar" style="--v:62%"></span>62</td>
  <td class="c-score"><span class="badge score high" title="HIGH: 80-100">86</span></td>
  <td class="c-sol" title="Hospital Operations Platform">Hospital Operations Platform</td>
  <td class="c-contact"><span class="chip ch-e" title="Business email available">E</span></td>
  <td><span class="badge conf med" title="confidence 64%">MEDIUM</span></td>
  <td><span class="badge verif needs">NOT VERIFIED</span></td>
  <td><span class="badge out none">NOT CONTACTED</span></td>
  <td class="c-act">
    <button class="nav" data-toggle="#biz-A1">Research</button>
    <a class="act" href="https://radar.example.internal/verify/biz_01JSAMPLE00000000000000A1?from=export&amp;campaign=cmp_01JSAMPLE0000000000000001">Verify</a>
    <a class="act" href="https://radar.example.internal/outreach?campaign=cmp_01JSAMPLE0000000000000001&amp;business=biz_01JSAMPLE00000000000000A1">Prepare</a>
    <button class="nav" data-toggle="#hist-A1">History</button>
  </td>
</tr>
```
(SAMPLE data; §10's example row, rendered.)

That row is exactly §10's worked example: `ABC Hospital / Dhule / Healthcare / Medium / Website: Yes
/ Digital Maturity: 62 / Opportunity: 86 / Potential Solution: Hospital Operations Platform /
Contact: Business Email Available / Confidence: Medium / Verification: NOT VERIFIED / Outreach: NOT
CONTACTED / Actions: View Research, Verify, Generate Message` — with "Generate Message" rendered as
PREPARE OUTREACH, which is what §19's pipeline calls that step, and with no SEND control.

#### 3.4.5.2 Contact Available (§9 column 10, §11)

The cell shows *what channels exist*, never a contact value. Contact values live in the research
panel and in the outreach workspace, behind a session.

| `data-contact` | Cell | Meaning |
|---|---|---|
| `EMAIL` / `PHONE` / `WHATSAPP` (space-separated for multiples) | chips `E` `P` `W` | at least one `business_contacts` row per kind with `human_verified = 1 AND is_active = 1` |
| `UNVERIFIED` | grey chip `?` with `title="n contact(s) found but not yet confirmed"` | `n_contacts = 0` but `n_contacts_any > 0` |
| `NONE` | `—` | no `business_contacts` row at all |

`UNVERIFIED` exists because "we found an email but nobody has confirmed it is a business address" and
"there is no contact" are different states with different next actions, and collapsing them into
"None" hides work that is already half done.

---

### 3.4.6 The expandable research panel (§11, §12, §13, §14)

Each business row is followed by a full-width `<tr class="panel-row" hidden>` holding the panel.
Expanding is `<details>`-equivalent behaviour driven by the row's Research button; the panel is the
single place where §11's detail block, §12's mandatory OBSERVED/INFERRED/UNKNOWN separation, §13's
software opportunity and §14's source list all live.

```
┌─ ABC Hospital ──────────────────────────────────────────────────────  [close] ┐
│                                                                               │
│  IDENTITY (§11)                                                               │
│  Name        ABC Hospital              Size            MEDIUM                 │
│  Category    Hospital (Healthcare)     Digital maturity 62 / 100              │
│  City        Dhule                     Operational cplx 71 / 100              │
│  Website     abc-hospital.example ↗    Opportunity      86  HIGH              │
│  Listing     Google Business ↗         Research conf.   MEDIUM (64%)          │
│  Contact     Business email available (1 confirmed, 1 unconfirmed)            │
│                                                                               │
│  RESEARCH FINDINGS (§12)                                                      │
│  ┌ OBSERVED ─ facts supported by sources ─────────────────────────┐           │
│  │ • The website lists four clinical departments.   HIGH  [1][2]  │           │
│  │ • A public appointment phone number is listed.   HIGH  [1]     │           │
│  └────────────────────────────────────────────────────────────────┘           │
│  ┌ INFERRED ─ reasonable conclusions, not verified ───────────────┐           │
│  │ • Patient records are likely handled department-by-            │           │
│  │   department rather than centrally.              MEDIUM [1]    │           │
│  └────────────────────────────────────────────────────────────────┘           │
│  ┌ UNKNOWN ─ could not be verified ───────────────────────────────┐           │
│  │ • Whether any billing software is currently in use.    —       │           │
│  └────────────────────────────────────────────────────────────────┘           │
│                                                                               │
│  SOFTWARE OPPORTUNITY (§13)                                                   │
│  Potential problem   Department-level records with no single view of a        │
│                      patient's history or of daily throughput.                │
│  Potential solution  Hospital Operations Platform                             │
│  Modules             Dashboard · Workflow · Finance Tracking · Inventory ·    │
│                      Reports · Role Management · Audit Logs                   │
│  Expected benefit    One view of admissions, billing and stock; fewer         │
│                      reconciliations at month end.                            │
│  Score               86 / 100   HIGH        Confidence  MEDIUM (64%)          │
│  Why 86              Operational complexity 22/25  because res_...F1          │
│                      Website quality        10/10  because res_...F1          │
│                      Size band              15/20  because res_...F4          │
│                      ...                                                      │
│                                                                               │
│  SOURCES (§14)                                                                │
│  [1] Practice website — abc-hospital.example ↗  SITE  checked 23 Aug 2026     │
│      "Departments: General Medicine, Orthopaedics, Paediatrics, Pathology"    │
│      confidence HIGH                                                          │
│  [2] Google Business listing ↗                  LISTING  checked 23 Aug 2026  │
│      "40 beds · open 24 hours"                  confidence MEDIUM             │
│                                                                               │
│  Researched 23 Aug 07:41 IST · depth DEEP · gemini-2.5-flash · research-v4    │
└───────────────────────────────────────────────────────────────────────────────┘
```
(SAMPLE content.)

#### 3.4.6.1 §12 is a hard structural requirement, not a styling choice

Spec §12: *"VERIFIED / OBSERVED = facts directly supported by sources. INFERRED = reasonable
conclusions. UNKNOWN = information that could not be verified. This is mandatory."* The panel
therefore renders **three labelled fieldsets, always, in that order, even when one is empty**, and an
empty one says so:

```html
<fieldset class="findings kind-UNKNOWN">
  <legend>Unknown &mdash; could not be verified</legend>
  <p class="empty">Nothing was recorded as unverifiable for this business.</p>
</fieldset>
```

Dropping an empty section would let a business with zero UNKNOWN findings look identical to one where
the research pipeline never populated the kind at all. The three legends are fixed text:

| `kind` | Legend | Rendering |
|---|---|---|
| `OBSERVED` | `Observed — supported by sources` | plain statement, green left rule, source refs |
| `INFERRED` | `Inferred — reasonable conclusion, not verified` | statement prefixed `Inferred:`, blue left rule, source refs for what it was inferred *from* |
| `UNKNOWN` | `Unknown — could not be verified` | statement, muted text, `—` in the confidence column, no source refs |

A finding with no `finding_sources` row renders with a `no source` badge and is **excluded from the
citable set regardless of kind**. `_CONTEXT.md` invariant 4 and the message policy engine both depend
on this rendering matching the policy engine's view of the same rows, so the panel and
`radar/policy.py` read the same query.

```sql
-- radar/report_queries.py :: Q_FINDINGS   (Q5)
SELECT
    f.business_id,
    f.id            AS finding_id,
    f.kind,                            -- OBSERVED | INFERRED | UNKNOWN
    f.dimension,                       -- DIGITAL_MATURITY | OPERATIONAL_COMPLEXITY | ...
    f.label,                           -- short heading, may be NULL
    f.statement,                       -- rendered verbatim, never re-worded
    f.confidence,                      -- HIGH | MEDIUM | LOW
    f.confidence_pct,
    f.weight,
    s.id            AS source_id,
    s.name          AS source_name,
    s.url           AS source_url,
    s.source_type,
    COALESCE(fs.checked_at, s.checked_at) AS checked_at,
    fs.excerpt      AS information_obtained
FROM research_findings f
JOIN v_report_business r ON r.business_id = f.business_id
LEFT JOIN finding_sources fs ON fs.finding_id = f.id
LEFT JOIN sources         s  ON s.id = fs.source_id
WHERE r.campaign_id = :campaign_id
  AND f.research_run_id = (SELECT rr.id FROM research_runs rr
                            WHERE rr.business_id = f.business_id
                              AND rr.status = 'COMPLETE'
                            ORDER BY rr.finished_at DESC
                            LIMIT 1)
ORDER BY f.business_id,
         CASE f.kind WHEN 'OBSERVED' THEN 0 WHEN 'INFERRED' THEN 1 ELSE 2 END,
         f.confidence_pct DESC,
         f.weight DESC,
         f.id;
```

The join fans out one row per (finding, source); `group_by` in `load_report_data` collapses it into
`Finding(sources=[...])`. This is why the query set stays at twelve regardless of row count.

#### 3.4.6.2 §13 software opportunity block

§13's six fields, each with its column:

| §13 field | Column | `—` when |
|---|---|---|
| Potential Problem | `opportunities.potential_problem` | NULL |
| Potential Solution | `opportunities.potential_solution` | NULL |
| Recommended Modules | `opportunity_modules` rows, `ordinal` order | no rows |
| Expected Business Benefit | `opportunities.expected_benefit` | NULL |
| Opportunity Score | `opportunities.score` + band | no current opportunity row |
| Confidence | `opportunities.confidence` + `confidence_pct` | NULL |

```sql
-- radar/report_queries.py :: Q_OPPORTUNITY   (Q6)
SELECT o.business_id, o.score, o.band, o.confidence, o.confidence_pct,
       o.digital_maturity, o.operational_complexity,
       o.potential_problem, o.potential_solution, o.expected_benefit,
       o.est_value_inr, o.score_breakdown,
       o.model_id, o.prompt_version, o.computed_at
FROM opportunities o
JOIN v_report_business r ON r.business_id = o.business_id
WHERE r.campaign_id = :campaign_id AND o.is_current = 1
ORDER BY o.business_id;

-- radar/report_queries.py :: Q_MODULES   (Q7)
SELECT om.business_id, om.module, om.ordinal, om.rationale
FROM opportunity_modules om
JOIN v_report_business r ON r.business_id = om.business_id
WHERE r.campaign_id = :campaign_id
ORDER BY om.business_id, om.ordinal;
```

§13's example module vocabulary — Dashboard, Workflow, Finance Tracking, Inventory, Reports, Role
Management, Audit Logs — is rendered as chips with the module's `rationale` in the `title`. The
report does not own the module enum; it renders whatever `opportunity_modules.module` holds, with an
unknown value falling back to its raw text rather than being dropped.

**"Why 86"** renders `opportunities.score_breakdown`, which is stored JSON of the form
`[{"component": "...", "points": 22, "of": 25, "because_finding_id": "res_..."}]`. Each line links to
the finding it cites, by anchor, inside the same panel. A component with a null
`because_finding_id` renders the component, its points and nothing else — the panel does not
manufacture a justification. The score is never recomputed at render time; a report that disagrees
with the stored score is a report Sagar cannot audit.

#### 3.4.6.3 §14 source panel

§14 requires six fields per source and states *"The user must be able to open the source."*

| §14 field | Column | Rendering |
|---|---|---|
| Source Name | `sources.name` | text |
| Source URL | `sources.url` | `<a target="_blank" rel="noopener noreferrer nofollow">`, via `safe_url` (§3.2.6) |
| Source Type | `sources.source_type` | small caps chip, e.g. `SITE`, `LISTING`, `DIRECTORY`, `NEWS`, `SOCIAL`, `REGISTRY` |
| Date Checked | `finding_sources.checked_at`, falling back to `sources.checked_at` | `23 Aug 2026`, full ISO timestamp in `title` |
| Information Obtained | `finding_sources.excerpt` | blockquote, truncated to 300 chars with the rest behind a `more` toggle |
| Confidence | the citing finding's `confidence` | badge |

Sources are numbered per business, `[1]`, `[2]`, …, in first-citation order, and each finding shows
its refs inline. In the export the numbering is baked into the HTML, so a printed page keeps working
references (§3.10).

Because the export is self-contained, every source URL is **absolute** — a relative URL would resolve
against `file://` and 404. `safe_url` rejects anything that is not absolute `http`/`https`, which
also means a source whose stored URL is a relative fragment renders as name-only with
`title="URL withheld: not an absolute http(s) URL"` rather than as a broken link.

#### 3.4.6.4 History panel (§32)

A second per-row panel, toggled by the HISTORY action, rendering §32's fields: Date, Channel,
Message, Sender, Delivery status, Response, AI classification, Next action.

```sql
-- radar/report_queries.py :: Q_HISTORY   (Q9)
SELECT
    m.business_id,
    m.id                AS message_id,
    m.channel,
    m.status            AS delivery_status,
    m.sequence_no,
    m.subject_final,
    m.sent_at,
    m.delivered_at,
    u.display_name      AS sender,
    resp.classification AS response_classification,
    resp.confidence     AS response_confidence,
    resp.received_at    AS response_at,
    resp.body_excerpt   AS response_excerpt,
    h.state             AS handoff_state,
    h.outcome           AS handoff_outcome
FROM outreach_messages m
JOIN v_report_business r    ON r.business_id = m.business_id
LEFT JOIN outreach_approvals ap ON ap.id = m.approval_id
LEFT JOIN users u           ON u.id = ap.approved_by
LEFT JOIN responses resp    ON resp.message_id = m.id
LEFT JOIN handoffs h        ON h.business_id = m.business_id
WHERE r.campaign_id = :campaign_id
  AND m.status IN ('SENT','DELIVERED','BOUNCED','FAILED')
ORDER BY m.business_id, m.sent_at, m.id;
```

The **message body is not embedded in the export.** The history panel shows channel, subject, date,
delivery status and the response classification; the body is a link to `/outreach/<draft_id>` in the
live app. A file that gets emailed around should not carry the full text of every message Sagar has
ever sent to every prospect in four cities. The `LIVE` rendering shows the body inline.

"Next action" is derived, not stored:

| Condition | Next action shown |
|---|---|
| `handoff_state` open | `With you — see /handoffs` |
| response classified in the §34 interest set | `Human action required` |
| `NOT_INTERESTED` / `ALREADY_HAVE_SOFTWARE` / `WRONG_CONTACT` | `Stop — no further outreach` |
| `OPT_OUT` / `COMPLAINT` | `Do not contact` (red) |
| `LATER` | `Revisit after the frequency window` |
| delivered, no response, inside the follow-up allowance | `Follow-up available` |
| delivered, no response, allowance exhausted | `No further outreach` |
| `BOUNCED` / `FAILED` | `Delivery failed — check the contact` |

---

### 3.4.7 City comparison table (§37)

Ten columns. §37: *"Use actual database values."*

```sql
-- radar/report_queries.py :: Q_CMP_CITY   (Q10)
SELECT
    cc.city,
    cc.ordinal,
    COUNT(r.business_id)                                              AS n_businesses,
    SUM(CASE WHEN r.is_qualified = 1        THEN 1 ELSE 0 END)        AS n_qualified,
    SUM(CASE WHEN r.opportunity_score >= 80 THEN 1 ELSE 0 END)        AS n_high,
    SUM(CASE WHEN r.is_verified = 1         THEN 1 ELSE 0 END)        AS n_verified,
    SUM(CASE WHEN r.n_sent > 0              THEN 1 ELSE 0 END)        AS n_contacted,
    SUM(CASE WHEN r.n_responses > 0         THEN 1 ELSE 0 END)        AS n_responded,
    SUM(CASE WHEN r.is_interested = 1       THEN 1 ELSE 0 END)        AS n_interested,
    -- conversion: interested / contacted. NULL, not 0, when nothing was contacted.
    CASE WHEN SUM(CASE WHEN r.n_sent > 0 THEN 1 ELSE 0 END) > 0
         THEN ROUND(100.0 * SUM(CASE WHEN r.is_interested = 1 THEN 1 ELSE 0 END)
                          / SUM(CASE WHEN r.n_sent > 0 THEN 1 ELSE 0 END), 1)
    END                                                               AS conversion_pct,
    -- potential revenue: sum of PRICED rows only, plus the coverage that produced it
    SUM(CASE WHEN r.is_qualified = 1 THEN r.est_value_inr END)        AS potential_inr,
    SUM(CASE WHEN r.is_qualified = 1 AND r.est_value_inr IS NOT NULL
             THEN 1 ELSE 0 END)                                       AS n_priced,
    SUM(CASE WHEN r.opportunity_score IS NOT NULL THEN 1 ELSE 0 END)  AS n_scored,
    SUM(CASE WHEN r.research_complete = 1 THEN 1 ELSE 0 END)          AS n_researched
FROM campaign_cities cc
LEFT JOIN v_report_business r
       ON r.campaign_id = cc.campaign_id AND r.city = cc.city
WHERE cc.campaign_id = :campaign_id
GROUP BY cc.city, cc.ordinal
ORDER BY cc.ordinal;
```

| §37 column | Source | `—` when |
|---|---|---|
| City | `cc.city` | never |
| Businesses | `n_businesses` | never |
| Qualified | `n_qualified` | `n_researched = 0` |
| High Opportunity | `n_high` | `n_scored = 0` |
| Verified | `n_verified` | never |
| Contacted | `n_contacted` | never |
| Responses | `n_responded` | `n_contacted = 0` |
| Interested | `n_interested` | `n_contacted = 0` |
| Conversion | `conversion_pct` | `n_contacted = 0`, i.e. the SQL returned NULL |
| Potential Revenue | `potential_inr` | `n_priced = 0` |

Two of these deserve the argument spelled out, because they are the places a report most easily
starts lying:

**Conversion.** Zero contacted businesses does not give a conversion rate of 0%. `0/0` is undefined
and the SQL returns NULL, which renders `—`. A `0%` in that cell would tell Sagar that Jalgaon does
not respond, when the truth is that Jalgaon has never been contacted. The cell's `title` always
carries the fraction: `title="0 interested of 0 contacted"`.

**Potential Revenue.** This is the single most tempting number to fabricate, and `_CONTEXT.md`
invariant 5 forbids it. The rules:

- It sums `opportunities.est_value_inr` over **qualified rows that have a value**, and nothing else.
- `est_value_inr` is written only where a pricing rule produced one. There is no default, no average
  deal size applied to unpriced rows, and no per-industry multiplier invented at render time.
- The cell renders `—` when `n_priced = 0`.
- When `n_priced > 0` the cell renders the sum **and its coverage**: `₹ 24,00,000` with a sub-line
  `7 of 18 qualified priced`. A revenue figure without its coverage is a forecast; with it, it is a
  measurement.
- The column footer sums the column and repeats total coverage. It never extrapolates the unpriced
  rows.

Indian digit grouping is used for INR (`₹ 24,00,000`, not `₹ 2,400,000`), via:

```python
def inr(value: int | None) -> str:
    """Format rupees the way an Indian reader expects, or an em dash for no data."""
    if value is None:
        return "—"
    s = str(int(value))
    if len(s) <= 3:
        head, tail = "", s
    else:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        head = ",".join(parts) + ","
    return f"₹ {head}{tail}"
```

The table's last row is a `TOTAL` row aggregating over all cities — not the sum of the displayed
conversion percentages, but a recomputed `SUM(interested)/SUM(contacted)`, which is a different and
correct number.

---

### 3.4.8 Industry comparison table (§38)

Ten columns. Demos, Won and Revenue come from `handoffs`, which is owned by `10-human-handoff.md`.
The money column is `won_value_inr` — `10` prints the DDL and `CHECK (outcome <> 'WON' OR
won_value_inr IS NOT NULL)` with it, and `01-data-model.md` §1.2.4 ruling D6 settled the name. There
is no `realised_value_inr`. The `n_revenue_rows` companion exists because a `WON` handoff with a
NULL value must render `—` and not `₹0` (§3.5).

```sql
-- radar/report_queries.py :: Q_CMP_INDUSTRY   (Q11)
SELECT
    r.industry,
    COUNT(*)                                                          AS n_businesses,
    ROUND(AVG(r.opportunity_score), 1)                                AS avg_score,
    SUM(CASE WHEN r.opportunity_score IS NOT NULL THEN 1 ELSE 0 END)  AS n_scored,
    SUM(CASE WHEN r.is_verified = 1   THEN 1 ELSE 0 END)              AS n_verified,
    SUM(CASE WHEN r.n_sent > 0        THEN 1 ELSE 0 END)              AS n_contacted,
    SUM(CASE WHEN r.n_responses > 0   THEN 1 ELSE 0 END)              AS n_responded,
    SUM(CASE WHEN r.is_interested = 1 THEN 1 ELSE 0 END)              AS n_interested,
    COUNT(DISTINCT CASE WHEN h.demo_held_at IS NOT NULL
                        THEN h.business_id END)                       AS n_demos,
    COUNT(DISTINCT CASE WHEN h.outcome = 'WON'
                        THEN h.business_id END)                       AS n_won,
    SUM(CASE WHEN h.outcome = 'WON' THEN h.won_value_inr END)         AS revenue_inr,
    SUM(CASE WHEN h.outcome = 'WON' AND h.won_value_inr IS NOT NULL
             THEN 1 ELSE 0 END)                                       AS n_revenue_rows
FROM v_report_business r
LEFT JOIN handoffs h ON h.business_id = r.business_id
WHERE r.campaign_id = :campaign_id
GROUP BY r.industry
ORDER BY CASE r.industry
           WHEN 'HEALTHCARE' THEN 0 WHEN 'EDUCATION' THEN 1 WHEN 'AUTOMOBILE' THEN 2
           WHEN 'MANUFACTURING' THEN 3 WHEN 'RETAIL' THEN 4 WHEN 'HOSPITALITY' THEN 5
           WHEN 'DISTRIBUTION' THEN 6 WHEN 'REAL_ESTATE' THEN 7
           WHEN 'PROFESSIONAL_SERVICES' THEN 8 ELSE 9 END;
```

| §38 column | Source | `—` when |
|---|---|---|
| Industry | `r.industry` -> `INDUSTRY_LABEL` | never |
| Businesses | `n_businesses` | never |
| Opportunity | `avg_score`, sub-line `n of m scored` | `n_scored = 0` (AVG over all-NULL returns NULL) |
| Verified | `n_verified` | never |
| Contacted | `n_contacted` | never |
| Responses | `n_responded` | `n_contacted = 0` |
| Interested | `n_interested` | `n_contacted = 0` |
| Demos | `n_demos` | `n_contacted = 0` |
| Won | `n_won` | `n_contacted = 0` |
| Revenue | `revenue_inr` | `n_revenue_rows = 0` |

The Opportunity column is labelled **`Avg opportunity`** in the rendered header, with the count of
scored rows underneath. `AVG()` silently skips NULLs, so an industry where 3 of 20 businesses are
scored would otherwise show a confident-looking average of three rows. Showing `74.3` over
`3 of 20 scored` is the honest version of the same cell.

Rows for industries with `n_businesses = 0` are omitted here — unlike the city table, where a targeted
city that returned nothing is a finding. Nobody asked for `REAL_ESTATE` specifically; its absence
carries no information.

This table answers §53's "which industries respond most" and feeds the roadmap question in
`10-human-handoff.md`; the report shows the counts, the handoff document owns the statistics
(Wilson bounds, small-sample warnings). Where `n_contacted` is under 10 the row is rendered with a
`small sample` marker so a 100% conversion on one contacted business is not read as a trend.

---

### 3.4.9 Top 20 opportunities (§44)

Nine columns: Rank, Business, City, Industry, Opportunity Score, Potential System, Reason,
Confidence, Verification.

```sql
-- radar/report_queries.py :: Q_TOP20   (Q12)     :limit defaults to 20
SELECT
    r.business_id,
    r.name,
    r.city,
    r.industry,
    r.opportunity_score,
    r.opportunity_band,
    r.potential_solution           AS potential_system,
    r.research_confidence,
    r.research_confidence_pct,
    r.status,
    r.is_verified,
    r.verified_at,
    o.score_breakdown,
    (SELECT f.statement
       FROM research_findings f
      WHERE f.business_id = r.business_id
        AND f.kind = 'OBSERVED'
      ORDER BY f.weight DESC, f.confidence_pct DESC, f.id
      LIMIT 1)                     AS top_observed_statement
FROM v_report_business r
LEFT JOIN opportunities o ON o.business_id = r.business_id AND o.is_current = 1
WHERE r.campaign_id = :campaign_id
  AND r.opportunity_score IS NOT NULL
ORDER BY r.opportunity_score DESC, r.name, r.business_id
LIMIT :limit;
```

| §44 column | Rendering |
|---|---|
| Rank | 1..N, dense; ties broken by name then id, so the ordering is stable between exports |
| Business | name, linked to its row anchor in the main table |
| City | display label |
| Industry | display label |
| Opportunity Score | score badge |
| Potential System | `potential_solution`, `—` when NULL |
| Reason | the highest-scoring `score_breakdown` component that has a `because_finding_id`, rendered as `Operational complexity 22/25 — four departments listed on the About page`; falls back to `top_observed_statement`; `—` if neither exists |
| Confidence | confidence badge + `confidence_pct` in `title` |
| Verification | verification badge (§3.9.4) |

The Reason column is the reason this table exists rather than a sorted view of the main table: §53
asks "which businesses have the highest software potential", and a rank without a reason is not an
answer Sagar can act on. It is assembled in Python, not SQL:

```python
def top_reason(breakdown_json: str | None, findings: list[Finding],
               fallback: str | None) -> str | None:
    """One line explaining why this business is near the top.

    Prefers the score component that carries a finding id, because that is the only reason in the
    system that is traceable back to a source. Never composes a reason out of the score itself -
    "scored 86" explains nothing.
    """
```

**Businesses with no score never appear here**, even if the campaign has fewer than 20 scored rows.
The section header states the truth: `Top 12 of 141 researched businesses (12 scored)`. Padding the
table to 20 with unscored rows would put a business Sagar has no information about in a list
literally titled "top opportunities".

---

### 3.4.10 Daily report view (§43)

§43 is a different document with the same components: date-scoped, cross-campaign, deliberately
short. It is generated by the nightly job (see the background-jobs document) and pushed to Telegram
as a link, and it is the thing Sagar reads at 8am.

Route `/reports/daily/<YYYY-MM-DD>`; export filename `business_research_daily_<date>.html`.

| §43 item | Query | Notes |
|---|---|---|
| Date | parameter | rendered in IST |
| Cities researched | `SELECT DISTINCT city FROM businesses WHERE substr(first_discovered_at,1,10) = :d` | joined with campaign names. The daily is cross-campaign, so the global `businesses.first_discovered_at` is the right column here — `campaign_businesses.first_seen_at` would count one rediscovered business once per campaign that saw it that day |
| Businesses discovered | `COUNT(DISTINCT business_id) FROM v_report_business WHERE discovered_on = :d` | `DISTINCT` because the view's grain is (campaign, business) — see below |
| Businesses qualified | `COUNT(DISTINCT CASE WHEN is_qualified = 1 THEN business_id END) FROM v_report_business WHERE discovered_on = :d` | |
| Top opportunities | `Q_TOP20` variant scoped by `discovered_on = :d`, `LIMIT 10` | same Reason logic. The daily variant drops the `:campaign_id` filter, so it groups by `business_id` and keeps `MIN(campaign_id)` — otherwise a business two campaigns found on the same day occupies two of the ten slots |
| Businesses needing verification | `status IN ('AI_RESEARCHED','NEEDS_VERIFICATION')` **as of now**, not as of the date | it is a to-do list, so it must reflect the present |
| Businesses ready for outreach | `status = 'CONTACT_READY'` as of now | |
| Outreach sent | `COUNT(*) FROM outreach_messages WHERE substr(sent_at,1,10) = :d AND status IN ('SENT','DELIVERED','BOUNCED')` | |
| Responses | `COUNT(*) FROM responses WHERE substr(received_at,1,10) = :d` | broken down by classification |
| Interested leads | `responses` on that date in the §34 interest set, each linked to its handoff | |

The mixed time semantics above are a deliberate decision and are stated in the report itself:

> Discovery, outreach and response counts are **for 26 Aug 2026**. Verification and outreach-ready
> counts are **as of now (27 Aug 2026, 08:00 IST)**, because they are work queues rather than
> events.

Without that sentence the two halves of the page look like they disagree.

```sql
-- radar/report_queries.py :: Q_DAILY_HEADLINE
-- Every count over v_report_business here is COUNT(DISTINCT business_id). The view is one row per
-- (campaign, business) since 01-data-model.md §1.2.2, and the daily is cross-campaign: without
-- DISTINCT a business two campaigns are both covering is two businesses on this page. The campaign
-- report (Q1, Q2) does not need DISTINCT because it filters to a single campaign_id, where the
-- grain is one row per business by construction.
SELECT
    (SELECT COUNT(DISTINCT business_id) FROM v_report_business
      WHERE discovered_on = :on_date)                                                AS d_discovered,
    (SELECT COUNT(DISTINCT CASE WHEN is_qualified = 1 THEN business_id END)
       FROM v_report_business WHERE discovered_on = :on_date)                        AS d_qualified,
    (SELECT COUNT(DISTINCT business_id) FROM v_report_business
      WHERE status IN ('AI_RESEARCHED','NEEDS_VERIFICATION'))                        AS d_need_verif_now,
    (SELECT COUNT(DISTINCT business_id) FROM v_report_business
      WHERE status = 'CONTACT_READY')                                                AS d_ready_now,
    (SELECT COUNT(*) FROM outreach_messages
      WHERE substr(sent_at, 1, 10) = :on_date
        AND status IN ('SENT','DELIVERED','BOUNCED'))                                AS d_sent,
    (SELECT COUNT(*) FROM responses WHERE substr(received_at, 1, 10) = :on_date)     AS d_responses,
    (SELECT COUNT(*) FROM responses
      WHERE substr(received_at, 1, 10) = :on_date
        AND classification IN ('INTERESTED','VERY_INTERESTED','DEMO_REQUESTED',
                               'MEETING_REQUESTED','PRICE_REQUESTED'))               AS d_interested;
```

A day with no activity renders the page with every count at its real value and one line at the top:
`No businesses were discovered on 26 Aug 2026.` It is not suppressed — an absent daily report is
indistinguishable from a broken cron job, and the whole point of a daily is that its absence is
alarming.

`interested leads` on the daily page render as handoff cards linking to `/handoffs/<id>`, matching
`10-human-handoff.md`'s brief. The daily report is a *pointer* to those; it never restates the
prospect's full reply, for the same reason the history panel does not embed message bodies.

---

## 3.5 No data is not zero

`_CONTEXT.md` invariant 5 and spec §8 both say the same thing from different directions: report
numbers come from SQL aggregates over real rows, and nothing is fabricated. The failure mode that
rule exists to prevent is not a made-up statistic — nobody would write one — it is the quiet
`COALESCE(x, 0)` that turns "we have not measured this" into "the measurement is zero".

### 3.5.1 The three states, and how each renders

| State | Meaning | Render | Machine-readable |
|---|---|---|---|
| a number | measured | `62` | `data-dm="62"` |
| `0` | measured, and the answer is none | `0` | `data-dm="0"` |
| `NULL` | not measured / not applicable / undefined | `—` | `data-dm=""` |

```python
NA = Markup('<span class="na" title="{t}" aria-label="no data">&mdash;</span>')

def dash(value, *, unit: str = "", why: str = "No data") -> Markup:
    """Render a metric, or an em dash if there is nothing behind it.

    Every number in this report goes through here. The em dash is not decoration: a KPI that shows
    0 is asserting that we looked and the answer was none, and a KPI that shows an em dash is
    admitting we do not know. Sagar acts on those two differently - one is a finding, the other is
    a job that has not run - and a report that renders them identically is worse than one that
    renders neither.
    """
    if value is None or value == "":
        return NA.format(t=why)
    if isinstance(value, float):
        return Markup(f"{value:,.1f}{escape(unit)}")
    return Markup(f"{escape(value)}{escape(unit)}")
```

### 3.5.2 Where it bites, concretely

| Cell | `0` means | `—` means | Wrong rendering would cause |
|---|---|---|---|
| KPI "No Website" | we checked N businesses and all had one | website checking has not run | Sagar targets "no-website" businesses that in fact have websites, and the first line of his email is wrong |
| KPI "Verified" | nothing is verified yet | — (never NULL; a count of live `verifications` rows is always defined) | |
| §37 Conversion | contacted, none interested | never contacted | a city gets written off as unresponsive when it has never been contacted |
| §37 Potential Revenue | every priced row is worth ₹0 | nothing is priced | a forecast presented as a measurement |
| §38 Avg opportunity | every scored business scored 0 | nothing in that industry is scored | an industry looks worthless instead of unexamined |
| Digital Maturity cell | measured at 0, i.e. no digital footprint at all | not assessed | a business with no assessment looks like the best possible prospect |
| Research Confidence | not a numeric field; `LOW` is the floor | no opportunity row | a business with no research looks merely low-confidence |
| Business row Website | n/a | `website_status = 'UNKNOWN'` | see the first row |

The Digital Maturity row is the sharpest example. The opportunity score rewards low digital
maturity — a business with nothing digital needs the most software. Rendering an unassessed business
as `0` puts it at the top of exactly the list Sagar works down first.

### 3.5.3 Enforcement

1. `BusinessRow.from_row()` and every sibling dataclass keep `None` as `None` (§3.3.4).
2. Aggregates that can be undefined are written to return NULL rather than 0 — see the
   `CASE WHEN denominator > 0 THEN ... END` shape in `Q_CMP_CITY`.
3. Templates call `|dash` on every metric; `StrictUndefined` catches a metric that was never passed.
4. `test_no_coalesce_to_zero` greps `radar/report_queries.py` for `COALESCE(` applied to
   `score`, `digital_maturity`, `operational_complexity`, `confidence_pct` or `est_value_inr` and
   fails the build. The `COALESCE(..., 0)` calls that *are* present are all on counts, where zero is
   the correct answer for "no rows joined".
5. `test_kpi_zero_vs_null_render_differently` renders a fixture campaign with an unscored business
   and asserts the HTML contains `class="na"` in the maturity cell and does not contain `>0<` there.

### 3.5.4 The `—` is not silent

Every `—` carries a `title` naming the reason, from a fixed vocabulary:

| `title` | Used when |
|---|---|
| `Not researched yet` | `research_complete = 0` |
| `Not scored yet` | `opportunity_score IS NULL` |
| `Website not checked` | `website_status = 'UNKNOWN'` |
| `No contact recorded` | `n_contacts_any = 0` |
| `Nothing contacted, so there is no rate` | conversion NULL |
| `No business in this group is priced` | revenue NULL |
| `No data` | fallback |

---

## 3.6 Client-side behaviour, with zero dependencies

`report.js` is vanilla ES2019, no framework, no CDN, no build step, roughly 22 KB unminified. It runs
identically in `LIVE` and `EXPORT`, because a filter that behaves differently in the file Sagar
emailed than in the app he reviewed is a bug he will not notice until it matters.

### 3.6.1 The data-attribute scheme

Filtering never touches the DOM's text content. Every predicate reads attributes off the `<tr>`:

| Attribute | Values | Type | Filter (§39) |
|---|---|---|---|
| `data-id` | `biz_…` | id | — (selection) |
| `data-city` | `DHULE` … | enum | 1 City |
| `data-industry` | `HEALTHCARE` … | enum | 2 Industry |
| `data-cat` | `HOSPITAL` … | enum | — (tab grouping, and search) |
| `data-size` | `MICRO`/`SMALL`/`MEDIUM`/`LARGE`/`UNKNOWN` | enum | 3 Business size |
| `data-score` | `0`-`100` or `""` | number-or-null | 4 Opportunity score |
| `data-web` | `PRESENT`/`ABSENT`/`UNKNOWN` | enum | 5 Website status |
| `data-dm` | `0`-`100` or `""` | number-or-null | 6 Digital maturity |
| `data-conf` | `HIGH`/`MEDIUM`/`LOW` or `""` | enum-or-null | 7 Research confidence |
| `data-verif` | `AI_RESEARCHED`/`NEEDS_VERIFICATION`/`VERIFIED`/`REJECTED`/`SKIPPED`/`CONTACT_READY` | enum | 8 Verification status |
| `data-contact` | space-separated `EMAIL PHONE WHATSAPP`, or `UNVERIFIED`, or `NONE` | set | 9 Contact status |
| `data-outreach` | `NOT_CONTACTED`/`QUEUED`/`SENT`/`DELIVERED`/`BOUNCED`/`FAILED`/`RESPONDED`/`INTERESTED`/`BLOCKED` | enum | 10 Outreach status |
| `data-disc` | `YYYY-MM-DD` | date | 11 Date discovered |
| `data-sel` | `1`/`0` | bool | selection gating |
| `data-block` | gate code or `""` | enum | tooltip |
| `data-q` | lowercased search blob | text | full-text search |

`data-verif` is derived, not `businesses.status` directly, because §39's "Verification status" filter
and §39's "Outreach status" filter must be independent — a `CONTACTED` business is still `VERIFIED`
for the purposes of filter 8:

```python
def verif_state(row: BusinessRow) -> str:
    if row.status in ("REJECTED", "SKIPPED"):
        return row.status
    if row.status == "CONTACT_READY":
        return "CONTACT_READY"
    if row.is_verified:
        return "VERIFIED"
    return row.status                # AI_RESEARCHED | NEEDS_VERIFICATION
```

`data-q` is built server-side and lowercased once, so search is a single `indexOf` per row rather
than a DOM walk:

```python
row.q = " ".join(filter(None, [
    row.name, row.city, CATEGORY_LABEL.get(row.category, row.category),
    INDUSTRY_LABEL.get(row.industry, row.industry), row.potential_solution,
    domain_of(row.website), row.business_id,
])).casefold()
```

Including `business_id` means Sagar can paste an id from a log line straight into the search box.

### 3.6.2 The eleven filters (§39)

```js
var F = {                       // the whole filter state, one object
  city: [], industry: [], size: [], web: [], conf: [], verif: [],
  contact: [], outreach: [],
  score: [null, null],          // [min, max] inclusive; null = open end
  dm:    [null, null],
  disc:  [null, null],          // ["2026-08-01", "2026-08-26"]
  q: "",
  nullScore: true,              // include rows whose score is unknown
  nullDm: true,                 // include rows whose maturity is unknown
  tabCity: "ALL", tabIndustry: "ALL",
  sort: {key: "score", dir: "desc"}
};
```

```js
function inSet(list, value) {          // empty list = no constraint
  return list.length === 0 || list.indexOf(value) !== -1;
}

function inSetAny(list, spaceSeparated) {
  if (list.length === 0) { return true; }
  var have = spaceSeparated ? spaceSeparated.split(" ") : [];
  for (var i = 0; i < list.length; i++) {
    if (have.indexOf(list[i]) !== -1) { return true; }
  }
  return false;
}

function inRange(raw, range, includeNull) {
  if (raw === "" || raw === null || raw === undefined) { return includeNull; }
  var v = Number(raw);
  if (range[0] !== null && v < range[0]) { return false; }
  if (range[1] !== null && v > range[1]) { return false; }
  return true;
}

function inDateRange(raw, range) {     // ISO dates compare correctly as strings
  if (!raw) { return range[0] === null && range[1] === null; }
  if (range[0] !== null && raw < range[0]) { return false; }
  if (range[1] !== null && raw > range[1]) { return false; }
  return true;
}

/* One predicate, eleven filters plus search plus the active tab. */
function passes(d) {                    // d = tr.dataset
  return (F.tabCity     === "ALL" || d.city     === F.tabCity)
      && (F.tabIndustry === "ALL" || d.industry === F.tabIndustry)
      && inSet(F.city,     d.city)                       /*  1 City               */
      && inSet(F.industry, d.industry)                   /*  2 Industry           */
      && inSet(F.size,     d.size)                       /*  3 Business size      */
      && inRange(d.score,  F.score, F.nullScore)         /*  4 Opportunity score  */
      && inSet(F.web,      d.web)                        /*  5 Website status     */
      && inRange(d.dm,     F.dm, F.nullDm)               /*  6 Digital maturity   */
      && inSet(F.conf,     d.conf || "NONE")             /*  7 Research confidence*/
      && inSet(F.verif,    d.verif)                      /*  8 Verification status*/
      && inSetAny(F.contact, d.contact)                  /*  9 Contact status     */
      && inSet(F.outreach, d.outreach)                   /* 10 Outreach status    */
      && inDateRange(d.disc, F.disc)                     /* 11 Date discovered    */
      && (F.q === "" || d.q.indexOf(F.q) !== -1);        /*    full-text search   */
}
```

```js
function applyFilters() {
  var t0 = performance.now();
  var rows = ROWS;                       // cached NodeList->Array, built once on load
  var shown = 0, perCity = Object.create(null);
  var frag = document.createDocumentFragment();   // batch, to avoid per-row reflow
  for (var i = 0; i < rows.length; i++) {
    var tr = rows[i], ok = passes(tr.dataset);
    if (tr.hidden !== !ok) { tr.hidden = !ok; }   // touch the DOM only on change
    var panel = tr.nextElementSibling;
    if (panel && panel.classList.contains("panel-row") && !ok) { panel.hidden = true; }
    if (ok) { shown++; perCity[tr.dataset.city] = (perCity[tr.dataset.city] || 0) + 1; }
  }
  updateGroupHeadings();                 // hide a category heading whose rows are all filtered out
  updateTabCounts(perCity);
  updateResultLine(shown, rows.length);
  writeHash();
  log("filter", performance.now() - t0);
}
```

Each of §39's eleven filters has an explicit UI control, and the ones with a null state say so:

| # | §39 filter | Control | Null handling |
|---|---|---|---|
| 1 | City | multi-select chips, from `campaign_cities` | — |
| 2 | Industry | multi-select chips, canonical enum order | — |
| 3 | Business size | chips `MICRO SMALL MEDIUM LARGE UNKNOWN` | `UNKNOWN` is a value, not a null |
| 4 | Opportunity score | dual number inputs + presets `80+`, `60-79`, `<60` | checkbox `include unscored` (default on) |
| 5 | Website status | chips `Has website / No website / Not checked` | `Not checked` is its own chip — §3.5 |
| 6 | Digital maturity | dual number inputs 0-100 | checkbox `include unassessed` (default on) |
| 7 | Research confidence | chips `HIGH MEDIUM LOW` + `No research` | `NONE` sentinel for a missing opportunity row |
| 8 | Verification status | chips over `verif_state()` values | — |
| 9 | Contact status | chips `Email / Phone / WhatsApp / Unconfirmed / None`, OR-combined | — |
| 10 | Outreach status | chips over `data-outreach` values | — |
| 11 | Date discovered | two `<input type="date">` + presets `Today`, `Last 7 days`, `This campaign` | a row with no `discovered_at` is excluded when either bound is set |

The two `include unscored` / `include unassessed` checkboxes are the UI expression of §3.5: a range
filter has to make an explicit decision about nulls, and hiding that decision is how "score 0-100"
silently drops 40 businesses.

A `Clear all filters` button resets `F` to defaults and empties the hash. The result line always
reads `Showing 63 of 148 businesses` with the active filter count beside it.

### 3.6.3 Full-text search

One input, debounced 120 ms, case-insensitive substring over `data-q`. No fuzzy matching, no
tokenising, no ranking: at 5,000 rows a substring scan is well under a millisecond and any cleverness
would produce results Sagar cannot predict. Matched text in the Business column is highlighted by
wrapping with `<mark>` **only on the visible rows after filtering**, so highlighting cost is bounded
by what is on screen.

The search box supports one piece of syntax, because it earns its keep:

| Input | Behaviour |
|---|---|
| `hospital` | substring over `data-q` |
| `city:dhule score:>80` | field-scoped terms are parsed out and folded into `F` before the free-text remainder is applied |

Supported prefixes: `city:`, `industry:`, `cat:`, `size:`, `score:`, `dm:`, `conf:`, `verif:`,
`contact:`, `outreach:`. Anything unrecognised stays part of the free-text query rather than
silently matching nothing.

### 3.6.4 Multi-column sort

Click a `<th data-sort="score" data-sort-type="num">` to sort; click again to reverse;
shift-click to add a secondary key. State lives in `F.sort` as a list of `{key, dir}` up to three
deep, and the header renders `▲`/`▼` plus a small ordinal for secondary keys.

```js
var COMPARATORS = {
  num:  function (a, b) {                    // nulls always last, regardless of direction
    var x = a === "" ? null : Number(a), y = b === "" ? null : Number(b);
    if (x === null && y === null) { return 0; }
    if (x === null) { return 1; }
    if (y === null) { return -1; }
    return x - y;
  },
  text: function (a, b) { return a.localeCompare(b, "en", {sensitivity: "base"}); },
  ord:  function (a, b) { return (ORD[a] || 0) - (ORD[b] || 0); },
  date: function (a, b) { return a < b ? -1 : a > b ? 1 : 0; }
};

var ORD = {                                   // ordinal scales for badge columns
  MICRO: 1, SMALL: 2, MEDIUM: 3, LARGE: 4, UNKNOWN: 0,
  LOW: 1, MEDIUM_C: 2, HIGH: 3,
  AI_RESEARCHED: 1, NEEDS_VERIFICATION: 2, VERIFIED: 3, CONTACT_READY: 4,
  SKIPPED: 0, REJECTED: 0,
  NOT_CONTACTED: 0, QUEUED: 1, SENT: 2, DELIVERED: 3, BOUNCED: 1,
  FAILED: 1, RESPONDED: 4, INTERESTED: 5, BLOCKED: 0
};
```

**Nulls sort last in both directions.** Ascending by score should not open with 40 unscored
businesses; the point of sorting by score is to see scores.

Sorting reorders rows **within their category group**, not across groups, so §4's grouping survives.
A `Sort across all groups` toggle flattens the pane into one `<tbody>` when Sagar wants a pure
ranking; the Top-20 section (§3.4.9) already covers the common case.

Sorting a 5,000-row table: rows are detached into an array once at load, sorted, then re-appended via
a single `DocumentFragment`. Measured target in §3.13.

### 3.6.5 State in the URL hash

The whole view — filters, search, sort, tabs — is serialised into the hash so a filtered view is a
shareable link and a browser reload keeps the view.

```
#tab=DHULE|HEALTHCARE&city=DHULE,NASHIK&size=MEDIUM,LARGE&score=70-&verif=VERIFIED,CONTACT_READY&q=hospital&sort=score:desc,name:asc
```

| Key | Format |
|---|---|
| `tab` | `<city>|<industry>`, `ALL` allowed either side |
| `city`, `industry`, `size`, `web`, `conf`, `verif`, `contact`, `outreach` | comma-separated enum values |
| `score`, `dm` | `min-max`; open ends allowed (`70-`, `-59`); append `!` to exclude nulls (`70-!`) |
| `disc` | `from..to`, ISO dates, open ends allowed |
| `q` | `encodeURIComponent`'d free text |
| `sort` | comma-separated `key:dir` |
| `sel` | **omitted by default** — see below |

```js
function writeHash() {
  var parts = [];
  if (F.tabCity !== "ALL" || F.tabIndustry !== "ALL") {
    parts.push("tab=" + F.tabCity + "|" + F.tabIndustry);
  }
  ["city","industry","size","web","conf","verif","contact","outreach"].forEach(function (k) {
    if (F[k].length) { parts.push(k + "=" + F[k].join(",")); }
  });
  pushRange(parts, "score", F.score, F.nullScore);
  pushRange(parts, "dm", F.dm, F.nullDm);
  if (F.disc[0] || F.disc[1]) { parts.push("disc=" + (F.disc[0]||"") + ".." + (F.disc[1]||"")); }
  if (F.q) { parts.push("q=" + encodeURIComponent(F.q)); }
  if (F.sort.length) {
    parts.push("sort=" + F.sort.map(function (s) { return s.key + ":" + s.dir; }).join(","));
  }
  var hash = parts.length ? "#" + parts.join("&") : "";
  if (hash !== location.hash) {
    history.replaceState(null, "", location.pathname + location.search + hash);
  }
}
```

Rules:

- `history.replaceState`, not `pushState`. Typing in the search box must not create 14 back-button
  entries.
- Unknown keys and unknown enum values in an inbound hash are **ignored with a console warning**, not
  treated as an error. A link from an older export must still open.
- The hash is capped at 2,000 characters; past that, `writeHash` drops `q` last and logs.
- Reading the hash is the single source of truth on load: `parseHash() -> F -> applyFilters()`. There
  is no separate "initial state" that could diverge.
- **Selection is not in the hash by default.** A shared link should carry a view, not a list of
  businesses Sagar is about to contact. A `Copy link including selection` button appends
  `&sel=biz_…,biz_…` explicitly (§3.7.3).
- In `EXPORT` mode the hash works identically on `file://`.

`sessionStorage` holds the last view per campaign under key `radar:view:<campaign_id>` so that
navigating away and back inside the live app restores it. It is a convenience only; the hash always
wins when present, and everything renders correctly when storage throws (private windows, blocked
site data). `localStorage` holds exactly one thing: the theme choice (§3.9.6).

---

## 3.7 Selection in the UI (§18)

### 3.7.1 Only two statuses get an enabled checkbox

§18: *"Only businesses with VERIFIED and CONTACT_READY can be selected for outreach."*
`05-outreach-workflow.md` §5.4.1 resolves that into a sequence — `CONTACT_READY` is strictly
stronger than `VERIFIED` and means "verified, and a human-confirmed contact exists". The report
implements exactly that table and adds nothing:

| `data-verif` / `status` | Checkbox | Tooltip and `aria-describedby` text |
|---|---|---|
| `AI_RESEARCHED` | disabled | `Research has not been reviewed yet.` |
| `NEEDS_VERIFICATION` | disabled | `This business still needs your verification.` |
| `VERIFIED` | disabled | `Verified, but no confirmed contact yet — add or confirm a contact.` |
| `CONTACT_READY` | **enabled** | — |
| `REJECTED` | disabled | `You rejected this business on 24 Aug 2026.` |
| `SKIPPED` | disabled | `You skipped this business on 24 Aug 2026.` |
| `CONTACTED` | enabled only for a follow-up, when the frequency gates pass | the gate's own reason, e.g. `Contacted 6 days ago; the minimum gap is 21 days.` |
| `RESPONDED` | enabled only if the reply was not a rejection | `This business replied NOT_INTERESTED on 22 Aug 2026.` |
| `INTERESTED` | disabled | `This is a live lead — the machine stops here and you take it.` |
| `HUMAN_HANDOFF` | disabled | `This lead is with you, not the system.` |
| any, `is_suppressed = 1` | disabled, row tinted red | `Do not contact: opt-out recorded 12 Aug 2026.` |

The tooltip text is generated from `blocking_gate` through one map, so the report, the live grid and
the outreach workspace all say the same sentence about the same row:

```python
BLOCK_REASON = {
    "A_SUPPRESSED":              "Do not contact: an opt-out or suppression is recorded.",
    "D_HUMAN_OWNED":             "This is a live lead - the machine stops here and you take it.",
    "D_VERIFICATION_REVOKED":    "You rejected or skipped this business.",
    "D_NOT_VERIFIED":            "This business still needs your verification.",
    "D_VERIFICATION_STALE":      "The verification has expired - re-verify before selecting.",
    "E_CONTACT_MISSING":         "Verified, but no confirmed contact yet.",
    "F_IN_FLIGHT":               "A message for this business is already awaiting approval.",
    "G_STOP_AFTER_REJECTION":    "This business replied that it is not interested.",
    "G_MAX_ATTEMPTS":            "The maximum number of outreach attempts has been reached.",
    "G_MAX_FOLLOWUPS":           "The maximum number of follow-ups has been reached.",
    "G_MIN_DAYS":                "Contacted too recently - the minimum gap has not elapsed.",
}
```

Rendering rules that matter for accessibility and for not lying to the user:

- A disabled checkbox is a real `<input type="checkbox" disabled>` — never a hidden input or an
  absent cell. The column must be visually consistent so the eye can scan it.
- `disabled` inputs are not focusable and therefore do not surface their `title` to keyboard or
  screen-reader users, so the reason is **also** rendered as visually-hidden text referenced by
  `aria-describedby`, and the cell carries a small `i` affordance that is focusable.
- The tooltip names *the missing precondition*, never a generic "not eligible". "This business still
  needs your verification" tells Sagar what to click; "not eligible" makes him go and find out.
- Header "select all" ticks only the **enabled, currently visible** checkboxes. It never selects a
  row the filter is hiding, and it never selects a blocked row.

### 3.7.2 Per-city counts (§18)

The sticky selection bar reproduces §18's own example format:

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  DHULE 5  ·  NASHIK 7  ·  JALGAON 3        15 selected                        │
│  [ Clear ]  [ Copy 15 ids ]                  [ PREPARE OUTREACH (15) ]        │
└───────────────────────────────────────────────────────────────────────────────┘
```
(SAMPLE counts, matching §18's `Dhule 5, Nashik 7, Jalgaon 3 = 15 selected`.)

```js
function recount() {
  var perCity = Object.create(null), total = 0;
  SELECTED.forEach(function (id) {
    var tr = document.querySelector('tr[data-id="' + cssEscape(id) + '"]');
    if (!tr) { return; }
    perCity[tr.dataset.city] = (perCity[tr.dataset.city] || 0) + 1;
    total++;
  });
  renderSelectionBar(perCity, total);       // cities in campaign_cities order, zero-count omitted
}
```

Selection **survives filtering and tab switches**. `SELECTED` is a `Set` of business ids, not a query
over checked DOM nodes, so filtering a row out of view does not silently deselect it. The bar states
this when it applies: `3 of your 15 selected businesses are hidden by the current filters.` — a
count that silently dropped would be the worst possible bug in a screen whose entire job is deciding
who gets contacted.

The bar is hidden at zero selections and appears with no layout shift (it is `position: sticky` at
the bottom with a reserved height).

### 3.7.3 What SELECT does in each mode

| | `LIVE` | `EXPORT` |
|---|---|---|
| Ticking a checkbox | updates `SELECTED`, recounts | identical |
| `PREPARE OUTREACH (n)` | `POST /api/v1/selections` with the id list and `intent_channel`, then navigates to `/outreach` | **disabled**; the bar reads `Selection is preview-only in this file. Open the campaign in the app to select.` |
| `Copy n ids` | copies newline-separated ids | identical — pure clipboard, no network |
| `Copy link including selection` | copies the current URL with `&sel=` | copies the **live app** URL `{base}/campaigns/<id>#...&sel=...` |

`Copy n ids` and `Copy link including selection` are the export's honest answer to "I did the triage
on a plane". Sagar picks rows offline, copies, and pastes into the live app, where the selection is
re-validated against current state before anything is prepared. The clipboard call is wrapped:

```js
function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(ok, fallback);
  } else { fallback(); }
  function fallback() { showTextareaFallback(text); }   // pre-selected <textarea>, always works
}
```

A `file://` page is treated as a secure context by current browsers, but the `<textarea>` fallback
exists because that is not something to bet a workflow on.

### 3.7.4 What SELECT never does

The report does not write `selections` rows on its own, in either mode. `LIVE` posts to the API,
which applies `05-outreach-workflow.md`'s rules and can refuse. There is no client-side path that
records a selection, and therefore no path by which a stale export could resurrect a selection for a
business that has since opted out.

---

## 3.8 Row actions (§40)

### 3.8.1 The full matrix

§40 lists nine actions. This is what each one is, in each mode.

| §40 action | Kind | `LIVE` | `EXPORT`, app up | `EXPORT`, app down or absent |
|---|---|---|---|---|
| VIEW | navigate | link to `/business/<id>` | link to `{base}/business/<id>` | disabled chip |
| RESEARCH | in-page | expands the research panel | expands the research panel | **expands the research panel** |
| VERIFY | state-changing | link to `/verify/<id>` | link to `{base}/verify/<id>?from=export` | disabled chip |
| REJECT | state-changing | link to `/verify/<id>?intent=reject` | same, with `?from=export` | disabled chip |
| SELECT | state-changing | checkbox (§3.7) | checkbox, preview-only | checkbox, preview-only |
| PREPARE OUTREACH | state-changing | link to `/outreach?...` | link to `{base}/outreach?...` | disabled chip |
| VIEW MESSAGE | navigate (sensitive) | link to `/outreach/<draft_id>` | link to `{base}/outreach/<draft_id>` | disabled chip |
| SEND | **not rendered** | **not rendered** | **not rendered** | **not rendered** |
| HISTORY | in-page | expands the history panel | expands the history panel | **expands the history panel** |

The three actions that work with no app and no network — RESEARCH, HISTORY, and previewing a
selection — are exactly the three that only read data the file already contains. That is not a
coincidence; it is the design rule: **the export can do anything that is reading, and nothing that is
writing.**

### 3.8.2 The `act_link` macro

```jinja
{% macro act_link(label, path, row, gate=None, title=None) %}
  {%- if not app_base_url and is_export -%}
    {# No app configured: render nothing at all rather than a dead control. #}
  {%- elif gate -%}
    <span class="act disabled" tabindex="0" role="button" aria-disabled="true"
          title="{{ gate }}">{{ label }}</span>
  {%- else -%}
    <a class="act"
       href="{{ (app_base_url ~ path) if is_export else path }}"
       {% if is_export %}target="_blank" rel="noopener noreferrer"{% endif %}
       data-title="{{ title or '' }}">{{ label }}</a>
  {%- endif -%}
{% endmacro %}
```

There is no `post_link` macro. There is no `<form>` anywhere in `templates/report/`. A future
contributor who wants one has to add a macro, and the export lint test (§3.15) fails when they do.

### 3.8.3 The send-readiness chip: §40's preconditions, rendered read-only

§40 says SEND is available only after: research complete, verified, contact eligible, no opt-out, no
duplicate block, message approved. The report renders that as a **six-condition status chip** in the
Actions cell, showing the first unmet condition. It is a diagnosis, not a button.

| State | Chip | Links to |
|---|---|---|
| research incomplete | `Not researched` (grey) | — |
| researched, not verified | `Needs verification` (yellow) | `/verify/<id>` |
| verified, no confirmed contact | `No contact` (yellow) | `/business/<id>#contacts` |
| suppression present | `DO NOT CONTACT` (red) | `/business/<id>#suppression` |
| duplicate/frequency block | `Blocked: contacted 6 days ago` (red) | `/business/<id>#history` |
| eligible, no draft | `Ready to prepare` (blue) | `/outreach?...` |
| draft exists, policy `BLOCK` | `Policy blocked` (red) | `/outreach/<draft_id>` |
| draft exists, awaiting approval | `Awaiting your approval` (yellow) | `/outreach/<draft_id>` |
| approved, not yet sent | `Approved — send in Outreach` (green) | `/outreach/<draft_id>` |
| sent | outreach badge (§3.9.5) | `/business/<id>#history` |

The last-but-one row is the one that matters. Even in the single state where every §40 precondition
is satisfied and the message is approved, the report's control is a **link to the screen where the
CONFIRM & SEND button lives**, and that button is governed by the approval record described in
`05-outreach-workflow.md`. §19 and §45 are satisfied structurally: there is no arrangement of report
state that produces a transmit control inside a research report.

### 3.8.4 Deep-link landing behaviour

A deep link from an export lands on a live screen that may have moved on since the export was made.
The landing screens handle three cases:

| Case | Behaviour |
|---|---|
| the business still needs the action | render the screen normally, with a note: `Opened from a report exported on 26 Aug 2026.` |
| the action is already done | render the current state with `This business was verified on 27 Aug 2026, after your report was exported.` — never re-run the action |
| the business no longer qualifies (opt-out, handoff, rejection) | render a blocking notice naming the reason; the action controls are absent, not merely disabled |

`?from=export` is written into `audit_log.detail` when the landing screen commits anything, so §48's
audit trail records that the human's decision started from a file rather than the live grid.

---

## 3.9 Badges, colour tokens and themes (§50, §51)

### 3.9.1 Four semantic colours, and no more

§51 is a constraint, not a palette suggestion: *"Green: Verified / Interested / Won. Yellow: Needs
verification / Follow-up. Red: Rejected / Opt-out / Blocked. Blue: Research / Information. Do not use
excessive colours."* Everything else in the report is neutral. There is no per-industry colour, no
per-city colour, no rainbow score scale.

| Token family | §51 meaning | Used by |
|---|---|---|
| `--ok` | green | `VERIFIED`, `CONTACT_READY`, `INTERESTED`, `DELIVERED`, `WON`, score band `HIGH`, approved drafts |
| `--warn` | yellow | `NEEDS_VERIFICATION`, `AI_RESEARCHED`, awaiting approval, follow-up due, score band `MEDIUM`, `LATER` |
| `--bad` | red | `REJECTED`, opt-out / suppression, `BOUNCED`, `FAILED`, `POLICY_BLOCKED`, duplicate block, `COMPLAINT` |
| `--info` | blue | research, sources, informational chips, `SENT`/`QUEUED`, "ready to prepare" |
| `--muted` | neutral grey | `SKIPPED`, `UNKNOWN`, unscored, `NOT_CONTACTED`, every `—` |

Score bands use the same three tokens as everything else (`HIGH` green, `MEDIUM` yellow, `LOW`
neutral grey — **not** red). A low opportunity score is not a failure; painting it red would make a
perfectly ordinary business look like a compliance problem, which is what red means everywhere else
in this report.

### 3.9.2 The tokens

Structure follows `option_chain_reader`'s dashboard: the complete light palette on bare `:root`, dark
overrides in a `prefers-color-scheme` block guarded so an explicit light choice wins, and a third
block for the explicit dark choice.

```css
:root{
  color-scheme: light;

  /* surfaces */
  --page:#f4f4f2; --surface-1:#ffffff; --surface-2:#f7f7f5; --surface-3:#efefec;
  --rule:#dcdcd7;  --grid:#e6e6e2;

  /* text */
  --text-1:#0b0b0b; --text-2:#52514e; --text-3:#6f6d68;

  /* §51 semantic families: fg = text on the tint, bg = tint, ln = left rule */
  --ok-fg:#0f6b3f;   --ok-bg:#e6f4ea;   --ok-ln:#1f8a55;
  --warn-fg:#7a5200; --warn-bg:#fdf2d6; --warn-ln:#b07d0a;
  --bad-fg:#9f1f24;  --bad-bg:#fbe7e7;  --bad-ln:#c0393e;
  --info-fg:#14508a; --info-bg:#e5eff9; --info-ln:#2e6fae;
  --muted-fg:#4a4a46;--muted-bg:#eeeeea;--muted-ln:#9b9a94;

  --accent:#14508a;  --focus:#14508a;
  --r:8px;
}

@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --page:#0e0f11; --surface-1:#16171a; --surface-2:#1c1e22; --surface-3:#212429;
    --rule:#2f3339; --grid:#26292e;
    --text-1:#f2f3f5; --text-2:#a9adb6; --text-3:#8a8e97;
    --ok-fg:#5cd08a;   --ok-bg:#10281c;   --ok-ln:#2f7d52;
    --warn-fg:#e8b53d; --warn-bg:#2a2210; --warn-ln:#8a6c1c;
    --bad-fg:#f08a8a;  --bad-bg:#2c1517;  --bad-ln:#8e3a3d;
    --info-fg:#7ab4ec; --info-bg:#0f2237; --info-ln:#3a6c9e;
    --muted-fg:#a9adb6;--muted-bg:#212429;--muted-ln:#5b5f66;
    --accent:#7ab4ec;  --focus:#7ab4ec;
  }
}

:root[data-theme="dark"]{
  color-scheme: dark;
  --page:#0e0f11; --surface-1:#16171a; --surface-2:#1c1e22; --surface-3:#212429;
  --rule:#2f3339; --grid:#26292e;
  --text-1:#f2f3f5; --text-2:#a9adb6; --text-3:#8a8e97;
  --ok-fg:#5cd08a;   --ok-bg:#10281c;   --ok-ln:#2f7d52;
  --warn-fg:#e8b53d; --warn-bg:#2a2210; --warn-ln:#8a6c1c;
  --bad-fg:#f08a8a;  --bad-bg:#2c1517;  --bad-ln:#8e3a3d;
  --info-fg:#7ab4ec; --info-bg:#0f2237; --info-ln:#3a6c9e;
  --muted-fg:#a9adb6;--muted-bg:#212429;--muted-ln:#5b5f66;
  --accent:#7ab4ec;  --focus:#7ab4ec;
}

body{ background:var(--page); color:var(--text-1);
      font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
.num{ font-variant-numeric: tabular-nums; }
```

`body` gets an explicit background token. A transparent body borrows whatever ground the host paints
behind it, which is how a dark-mode reader ends up with black text on black.

### 3.9.3 Measured contrast

WCAG 2.1 AA needs 4.5:1 for body text and 3:1 for large text and UI component boundaries. Every pair
below is above 5:1, and most clear AAA (7:1). Computed with the sRGB relative-luminance formula.

| Pair | Light | Dark |
|---|---|---|
| `--text-1` on `--page` | 17.87 | 17.27 |
| `--text-2` on `--surface-1` | 7.94 | 7.97 |
| `--text-3` on `--surface-1` | 5.17 | 5.46 |
| `--ok-fg` on `--ok-bg` | 5.79 | 8.08 |
| `--ok-fg` on `--surface-1` | 6.57 | 9.26 |
| `--warn-fg` on `--warn-bg` | 6.21 | 8.32 |
| `--warn-fg` on `--surface-1` | 6.92 | 9.48 |
| `--bad-fg` on `--bad-bg` | 6.56 | 7.10 |
| `--bad-fg` on `--surface-1` | 7.79 | 7.43 |
| `--info-fg` on `--info-bg` | 7.09 | 7.34 |
| `--info-fg` on `--surface-1` | 8.25 | 8.17 |
| `--muted-fg` on `--muted-bg` | 7.65 | 6.92 |

Both the on-tint and the on-surface figures are listed because badge text sits on its tint while the
same token is reused for a finding's inline label on the panel surface.

**Colour is never the only channel.** Every badge carries text (`VERIFIED`, `NOT VERIFIED`,
`DO NOT CONTACT`), every finding fieldset carries a legend, and the score badge carries the number.
The report is fully usable in greyscale and by a red-green colour-blind reader, which matters because
the two states most likely to be confused — green `VERIFIED` and red `REJECTED` — are the two whose
confusion is most expensive.

### 3.9.4 Badge inventory

```css
.badge{
  display:inline-flex; align-items:center; gap:5px;
  padding:2px 8px; border-radius:999px;
  font-size:11px; font-weight:600; letter-spacing:.02em; white-space:nowrap;
  color:var(--f); background:var(--b); border:1px solid color-mix(in srgb, var(--f) 28%, transparent);
}
.badge.ok   { --f:var(--ok-fg);    --b:var(--ok-bg);    }
.badge.warn { --f:var(--warn-fg);  --b:var(--warn-bg);  }
.badge.bad  { --f:var(--bad-fg);   --b:var(--bad-bg);   }
.badge.info { --f:var(--info-fg);  --b:var(--info-bg);  }
.badge.mute { --f:var(--muted-fg); --b:var(--muted-bg); }
```

`color-mix` degrades gracefully: browsers without it fall back to the declared `border-color`
shorthand set just above in the cascade, and the badge is legible either way.

| Badge group | Value | Class | Label shown |
|---|---|---|---|
| Score band | `>= 80` | `ok` | the score, `title="HIGH: 80-100"` |
| | `60-79` | `warn` | the score |
| | `< 60` | `mute` | the score |
| | NULL | `mute` | `—` |
| Confidence (§14, §13) | `HIGH` | `ok` | `HIGH`, `title="confidence 87%"` |
| | `MEDIUM` | `warn` | `MEDIUM` |
| | `LOW` | `mute` | `LOW` |
| | none | `mute` | `—` |
| Verification (§9 col 12) | `CONTACT_READY` | `ok` | `READY` |
| | `VERIFIED` | `ok` | `VERIFIED` |
| | `NEEDS_VERIFICATION` | `warn` | `NOT VERIFIED` |
| | `AI_RESEARCHED` | `warn` | `AI RESEARCHED` |
| | `REJECTED` | `bad` | `REJECTED` |
| | `SKIPPED` | `mute` | `SKIPPED` |
| Outreach (§9 col 13) | none sent | `mute` | `NOT CONTACTED` |
| | `QUEUED` | `info` | `QUEUED` |
| | `SENT` | `info` | `SENT` |
| | `DELIVERED` | `ok` | `DELIVERED` |
| | `BOUNCED` | `bad` | `BOUNCED` |
| | `FAILED` | `bad` | `FAILED` |
| | `POLICY_BLOCKED` | `bad` | `POLICY BLOCKED` |
| | responded | `info` | `RESPONDED` |
| | interested | `ok` | `INTERESTED` |
| | suppressed | `bad` | `DO NOT CONTACT` |
| Size | `LARGE`/`MEDIUM`/`SMALL`/`MICRO` | `mute` | the value |
| | `UNKNOWN` | `mute` | `UNKNOWN` |
| Finding kind (§12) | `OBSERVED` | `ok` left rule | legend text |
| | `INFERRED` | `info` left rule | legend text |
| | `UNKNOWN` | `mute` left rule | legend text |
| Source type (§14) | any | `info` | the value |

`INFERRED` is blue rather than yellow on purpose: §51 assigns blue to "Research / Information", and an
inference is information, not a warning. Yellow is reserved for *things Sagar has to do*.

### 3.9.5 Outreach badge derivation

```python
def outreach_badge(row: BusinessRow) -> tuple[str, str]:
    """(css class, label) for §9's Outreach Status column.

    Ordered by severity, not by recency. A business that opted out after a delivered message must
    read DO NOT CONTACT, not DELIVERED - the newest fact is not the one that governs the next action.
    """
    if row.is_suppressed:                 return ("bad",  "DO NOT CONTACT")
    if row.is_interested:                 return ("ok",   "INTERESTED")
    if row.n_responses > 0:               return ("info", "RESPONDED")
    if row.last_message_status in ("BOUNCED", "FAILED", "POLICY_BLOCKED"):
        return ("bad", row.last_message_status.replace("_", " "))
    if row.last_message_status == "DELIVERED":  return ("ok",   "DELIVERED")
    if row.last_message_status == "SENT":       return ("info", "SENT")
    if row.last_message_status == "QUEUED":     return ("info", "QUEUED")
    if row.n_sent > 0:                          return ("info", "SENT")
    return ("mute", "NOT CONTACTED")
```

### 3.9.6 Theme control

A three-state control in the header: `Auto / Light / Dark`. `Auto` sets no `data-theme` attribute and
lets `prefers-color-scheme` decide; the other two stamp `data-theme` on `<html>`. The choice is
persisted in `localStorage` under `radar:theme`, read inside `try/catch`, and the page renders
correctly when the read throws or returns nothing.

```js
try {
  var t = localStorage.getItem("radar:theme");
  if (t === "light" || t === "dark") { document.documentElement.dataset.theme = t; }
} catch (e) { /* private window, blocked storage: Auto is a fine default */ }
```

The attribute is applied by an inline script in `<head>`, before first paint, so a dark-theme reader
does not get a white flash.

### 3.9.7 §50 in one place

§50 asks for a "clean dashboard, KPI cards, city tabs, industry tabs, tables, search, filters, score
badges, confidence badges, verification badges, outreach badges, expandable research panels,
responsive design". Where each lives:

| §50 item | Section |
|---|---|
| clean dashboard | §3.4 structure, §3.9 tokens |
| KPI cards | §3.4.2 |
| city tabs | §3.4.4 |
| industry tabs | §3.4.4 |
| tables | §3.4.5, §3.4.7, §3.4.8, §3.4.9 |
| search | §3.6.3 |
| filters | §3.6.2 |
| score badges | §3.9.4 |
| confidence badges | §3.9.4 |
| verification badges | §3.9.4 |
| outreach badges | §3.9.4, §3.9.5 |
| expandable research panels | §3.4.6 |
| responsive design | §3.14 |

---

## 3.10 Print and PDF stylesheet

Print is a first-class output: the PDF path in §3.11 is browser print-to-PDF, so `@media print` is not
cosmetic — it *is* the PDF layout.

```css
@page {
  size: A4 landscape;
  margin: 12mm 10mm 14mm;
}

@media print {
  :root{                                   /* force the light palette; ink is not a theme */
    color-scheme: light;
    --page:#ffffff; --surface-1:#ffffff; --surface-2:#ffffff; --surface-3:#ffffff;
    --rule:#b9b9b4; --grid:#d5d5d0;
    --text-1:#000000; --text-2:#333333; --text-3:#555555;
    --ok-bg:#ffffff; --warn-bg:#ffffff; --bad-bg:#ffffff; --info-bg:#ffffff; --muted-bg:#ffffff;
  }

  /* Chrome/Edge honour tints only with this; without it badges print as outlines, which is fine. */
  body{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }

  /* Nothing interactive survives paper. */
  .filters, .tabs, .selection-bar, .theme-switch, .c-sel, .c-act,
  .banner, .search, .sort-hint, .copy-btn   { display:none !important; }

  /* All panes at once: tabs mean nothing in a printed document. */
  [role="tabpanel"][hidden]{ display:block !important; }
  [hidden].panel-row       { display:table-row !important; }   /* see forcePrintHydration() */

  table{ width:100%; border-collapse:collapse; font-size:9pt; }
  thead{ display:table-header-group; }        /* repeat headers on every page */
  tfoot{ display:table-footer-group; }
  tr, .kpi, .city-card, fieldset.findings{ break-inside:avoid; page-break-inside:avoid; }
  h2, h3, .group-head{ break-after:avoid; }

  .kpis{ display:grid; grid-template-columns:repeat(4, 1fr); gap:4mm; }
  .city-cards{ display:grid; grid-template-columns:repeat(3, 1fr); gap:4mm; }

  /* Sources must be usable on paper: print the URL after the link text. */
  .sources a[href^="http"]::after{
    content:" (" attr(href) ")"; font-size:8pt; color:#333; word-break:break-all;
  }
  /* ...but only in the sources panel. Doing it globally makes every table cell explode. */
  a[href]:not(.sources a)::after{ content:none; }

  .na{ color:#000; }                          /* an em dash must not fade out on paper */
  .rpt-header{ break-after:avoid; }
  .print-only{ display:block; }
}

.print-only{ display:none; }
```

Two behaviours are driven from JS because CSS cannot do them:

```js
window.addEventListener("beforeprint", function () {
  forcePrintHydration();   // build every JSON-island panel into DOM (§3.2.5), so it prints
  expandAllGroups();       // undo collapsed category groups
  renderAllRows();         // exit windowed rendering (§3.13) - paper has no viewport
});
window.addEventListener("afterprint", restoreView);
```

A `print-only` block is injected above the table stating the filter state, because a printed page
that shows 63 of 148 rows with no explanation is a document that will be misread later:

```
Printed 27 Aug 2026 08:14 IST — filters active: City = Dhule, Nashik; Opportunity score >= 70;
Verification = VERIFIED, CONTACT_READY. Showing 63 of 148 businesses.
```

A `Print / Save as PDF` button in the header calls `window.print()`; it works identically in `LIVE`
and `EXPORT`, and it needs no network.

---

## 3.11 Export formats (§41)

§41: *"HTML, CSV, PDF, Excel. Preserve: Business, City, Industry, Score, Research, Verification,
Contact, Outreach status."* All four are produced from the **same `ReportData`**, so a figure cannot
differ between the HTML and the spreadsheet.

```python
def export_all(conn, campaign_id: str, formats: Sequence[str], *, out_dir: Path,
               user_id: str | None, app_base_url: str | None) -> list[ReportBuild]:
    """Load once, write every requested format.

    One load, four writers. The alternative - each writer running its own queries - is how a CSV
    ends up disagreeing with the HTML it was exported beside, and there is no way to tell which one
    Sagar quoted in a meeting.
    """
    data = load_report_data(conn, campaign_id)
    ...
```

### 3.11.1 The common column set

Every tabular export carries these 24 columns, a superset of §41's eight. Extra columns cost nothing
in a file that exists to be filtered in Excel; missing ones cost a re-export.

| # | Column | Source | Empty rendering |
|---|---|---|---|
| 1 | `business_id` | `business_id` | never empty |
| 2 | `business` | `name` | never empty |
| 3 | `city` | display label | |
| 4 | `industry` | display label | |
| 5 | `category` | display label | |
| 6 | `size` | `size_band` | `UNKNOWN` |
| 7 | `website` | `website` URL | blank when ABSENT, blank when UNKNOWN — column 8 disambiguates |
| 8 | `website_status` | `PRESENT`/`ABSENT`/`UNKNOWN` | |
| 9 | `digital_maturity` | `digital_maturity` | blank cell, never 0 |
| 10 | `operational_complexity` | `operational_complexity` | blank cell |
| 11 | `opportunity_score` | `opportunity_score` | blank cell |
| 12 | `opportunity_band` | `HIGH`/`MEDIUM`/`LOW` | blank |
| 13 | `potential_problem` | `potential_problem` | blank |
| 14 | `potential_solution` | `potential_solution` | blank |
| 15 | `recommended_modules` | `opportunity_modules`, joined `" · "` | blank |
| 16 | `expected_benefit` | `expected_benefit` | blank |
| 17 | `research_status` | `COMPLETE` / `PENDING` / `NONE` | |
| 18 | `research_confidence` | `HIGH`/`MEDIUM`/`LOW` | blank |
| 19 | `n_observed / n_inferred / n_unknown` | finding counts by kind | `0` is correct here |
| 20 | `sources` | count of distinct sources | `0` correct |
| 21 | `verification_status` | `verif_state()` | |
| 22 | `verified_on` | `verified_at` date | blank |
| 23 | `contact_available` | `Email/Phone/WhatsApp/Unconfirmed/None` | |
| 24 | `outreach_status` | outreach badge label | |

Plus `discovered_on`, `last_sent_on`, `n_sent`, `n_responses`, `response_classification`,
`do_not_contact`, `blocking_reason` and `campaign` on the end — 32 columns in total. Contact *values*
are **not** exported by default; `--include-contacts` adds `contact_email`, `contact_phone`,
`contact_whatsapp` and is off by default because a CSV of business contacts emailed around is the
exact artefact the DPDP purpose-limitation design in `_CONTEXT.md` §4 exists to keep from
proliferating. Turning it on writes an `audit_log` row (`action='EXPORT_WITH_CONTACTS'`).

Empty cells are **empty**, not `0` and not `"—"`. In a spreadsheet an em dash is a text value that
poisons a whole numeric column; a blank cell is what `AVERAGE()` and a pivot table expect. §3.5's
distinction survives because a blank in `digital_maturity` alongside a `PENDING` in
`research_status` says exactly what the em dash said in HTML.

### 3.11.2 CSV

```python
def export_csv(data: ReportData, path: Path, *, include_contacts: bool = False) -> Path:
    """Write the flat business table as CSV.

    Written with a UTF-8 BOM because the machine that opens this is running Excel on Windows, and
    Excel without a BOM renders every business name with a Devanagari or accented character as
    mojibake. The BOM is ugly and it is the difference between a usable file and a support call.
    """
    rows = flat_rows(data, include_contacts=include_contacts)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        w.writerow(CSV_HEADERS)
        for r in rows:
            w.writerow([csv_safe(v) for v in r])
    os.replace(tmp, path)
    log.info("Wrote %d business row(s) to %s", len(rows), path)
    return path


_FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")

def csv_safe(value):
    """Neutralise spreadsheet formula injection.

    Business names come off the public web. A business literally named "=cmd|'/c calc'!A1" is
    unlikely, but a research statement that starts with a hyphen is not, and Excel will happily
    evaluate either. Prefixing an apostrophe costs one character of display and removes the class.
    """
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIX):
        return "'" + value
    return value
```

`--include-contacts` is honoured identically in CSV and XLSX.

### 3.11.3 XLSX (openpyxl)

Conventions copied from `naukri_job_screener/screener/export.py`, because that is the spreadsheet
Sagar already knows how to use: dark header fill with bold white text, frozen header row, autofilter
across the used range, explicit column widths, wrapped text on the long columns, hyperlink-blue
links, a tinted score column, dropdown validations on the columns a human fills in, and a second
sheet explaining the ranking.

```python
HEADERS = [
    ("#", 5), ("Score", 7), ("Business", 34), ("City", 14), ("Industry", 18), ("Category", 18),
    ("Size", 10), ("Website", 10), ("Digital maturity", 15), ("Potential solution", 34),
    ("Modules", 30), ("Contact", 14), ("Confidence", 12), ("Verification", 16),
    ("Outreach", 16), ("Discovered", 12), ("Open in app", 14),
    ("Decision", 14), ("Owner note", 30),
]

DECISION_CHOICES = '"To verify,Verified,Rejected,Selected,Contacted,Not now"'

def export_xlsx(data: ReportData, path: Path, *, app_base_url: str | None = None,
                include_contacts: bool = False) -> Path:
    """Write the campaign as a working spreadsheet, not a data dump.

    The two tracking columns on the right are the reason this file exists rather than a CSV. Sagar
    triages on a train, marks rows there, and the sheet is the record of what he decided before the
    app ever sees it.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    sheet = wb.active
    sheet.title = "Businesses"

    header_fill = PatternFill("solid", fgColor="1F3864")
    header_font = Font(bold=True, color="FFFFFF")
    for column, (title, width) in enumerate(HEADERS, start=1):
        cell = sheet.cell(row=1, column=column, value=title)
        cell.fill, cell.font = header_fill, header_font
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
        sheet.column_dimensions[get_column_letter(column)].width = width

    link_font   = Font(color="0563C1", underline="single")
    high_fill   = PatternFill("solid", fgColor="E2EFDA")   # score >= 80
    medium_fill = PatternFill("solid", fgColor="FFF2CC")   # score 60-79
    block_fill  = PatternFill("solid", fgColor="FCE4E4")   # suppressed / do-not-contact

    for index, r in enumerate(data.rows, start=1):
        row = index + 1
        values = [
            index,
            r.opportunity_score,                       # None -> genuinely empty cell (§3.5)
            r.name,
            CITY_LABEL.get(r.city, r.city),
            INDUSTRY_LABEL.get(r.industry, r.industry),
            CATEGORY_LABEL.get(r.category, r.category),
            r.size_band,
            {"PRESENT": "Yes", "ABSENT": "No", "UNKNOWN": None}[r.website_status],
            r.digital_maturity,                        # None -> empty
            r.potential_solution,
            " · ".join(m.module for m in data.modules.get(r.business_id, [])) or None,
            contact_label(r),
            r.research_confidence,
            verif_label(r),
            outreach_badge(r)[1],
            r.discovered_on,
            None,                                      # hyperlink written below
            "To verify",
            None,
        ]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=column, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=column in (3, 10, 11, 19))

        if app_base_url:
            link = sheet.cell(row=row, column=17, value="Open")
            link.hyperlink = f"{app_base_url}/business/{r.business_id}"
            link.font = link_font

        if r.is_suppressed:
            for column in range(1, len(HEADERS) + 1):
                sheet.cell(row=row, column=column).fill = block_fill
        elif r.opportunity_score is not None and r.opportunity_score >= 80:
            sheet.cell(row=row, column=2).fill = high_fill
        elif r.opportunity_score is not None and r.opportunity_score >= 60:
            sheet.cell(row=row, column=2).fill = medium_fill

    last_row = max(len(data.rows) + 1, 2)
    decision = DataValidation(type="list", formula1=DECISION_CHOICES, allow_blank=True)
    sheet.add_data_validation(decision)
    decision.add(f"R2:R{last_row}")

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{last_row}"

    _add_research_sheet(wb, data)     # "Why these scored"
    _add_sources_sheet(wb, data)      # §14, one row per (business, source)
    _add_summary_sheet(wb, data)      # §7 KPIs, §8 city cards, §37, §38

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".xlsx.tmp")
    wb.save(tmp)
    os.replace(tmp, path)
    log.info("Wrote %d business row(s) to %s", len(data.rows), path)
    return path
```

Four sheets:

| Sheet | Contents |
|---|---|
| `Businesses` | the 19 working columns above, with the two human-filled tracking columns |
| `Why these scored` | business, score, and the rendered `score_breakdown` lines including finding ids — the spreadsheet equivalent of the panel's "Why 86" |
| `Sources` | one row per (business, source): name, URL as a hyperlink, type, date checked, excerpt, confidence — §14 in a form that can be sorted by source domain |
| `Summary` | §7's twelve KPIs, §8's per-city cards, §37 and §38 as blocks |

`None` is written as a genuinely empty cell everywhere a metric is unknown; openpyxl writes no value
at all, and `AVERAGE()` skips it. Writing `0` there would corrupt every pivot Sagar builds.

### 3.11.4 PDF: the honest options

| Option | How | Pros | Cons | Verdict |
|---|---|---|---|---|
| **Browser print-to-PDF** | Sagar opens the HTML and presses the `Print / Save as PDF` button; `@media print` (§3.10) does the layout | zero dependencies; byte-identical to what he sees; works on the export file offline; the only path that renders the real stylesheet | manual; cannot be produced by a cron job | **the documented path for v1** |
| **Headless Chromium via Playwright** | `page.goto(file_url)`, `page.emulate_media(media="print")`, `page.pdf(format="A4", landscape=True, print_background=True)` | same renderer, so identical output; scriptable; Playwright is **already a dependency in this repo** (`naukri_job_screener`, `option_chain_reader` both drive it) | ~150 MB browser download on the VPS; needs the JS to have run, so `beforeprint` hydration must be triggered explicitly | **the automated path, optional, behind `--pdf-engine chromium`** |
| **WeasyPrint** | server-side HTML+CSS -> PDF | pure Python, small, no browser | **does not execute JavaScript**, so tabs, filters, sort and every JSON-island panel render as raw or missing; needs a second print-only template maintained in parallel; Pango/cairo/GTK on Windows is a known pain | **rejected** |
| **ReportLab / fpdf2** | draw the PDF directly | full control | a second complete implementation of the report layout | rejected |

WeasyPrint is rejected on a specific ground, not a general one: this report's content structure
depends on JS in exactly one place — the JSON-island research panels (§3.2.5) — and that is the part
of the report Sagar most wants on paper when he takes it to a meeting. Maintaining a second
JS-free template to work around that means two definitions of the research panel, and the day they
diverge is the day a printed panel shows a finding the HTML calls UNKNOWN.

```python
def export_pdf(data: ReportData, path: Path, *, html_path: Path,
               engine: str = "chromium") -> Path:
    """Render the already-written HTML to PDF with headless Chromium.

    Deliberately renders the exported FILE rather than a fresh string: the PDF is then provably a
    picture of the artefact that was archived, not of a second render that might differ.
    """
    if engine != "chromium":
        raise ValueError(f"unsupported pdf engine: {engine!r}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:                       # honest failure, not a silent skip
        raise RuntimeError(
            "PDF export needs Playwright: pip install playwright && playwright install chromium. "
            "Or open the HTML and use the browser's Print / Save as PDF button."
        ) from exc
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="load")
            page.emulate_media(media="print")
            page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
            page.wait_for_timeout(250)               # let hydration settle
            tmp = path.with_suffix(".pdf.tmp")
            page.pdf(path=str(tmp), format="A4", landscape=True, print_background=True,
                     margin={"top": "12mm", "bottom": "14mm", "left": "10mm", "right": "10mm"},
                     display_header_footer=True,
                     footer_template=PDF_FOOTER)     # campaign name, page N of M, generated-at
            os.replace(tmp, path)
        finally:
            browser.close()
    return path
```

**Recommendation:** ship v1 with the browser button only, and register the Chromium path behind the
`--pdf-engine chromium` flag and a `report.pdf_engine` config key for the nightly job. Do not install
Chromium on the VPS until a PDF is actually needed on a schedule; until then, the button is the whole
feature and it has no failure modes.

---

## 3.12 Report archive (§42)

### 3.12.1 `report_exports`

**Owned by `11-audit-architecture.md` §11.11.1 as amended by `01-data-model.md` §1.2.1.** Created by
`radar/migrations/048_report_exports.sql`, with its indexes and its two immutability triggers. No
DDL is printed here; the `CREATE TABLE` and the four indexes an earlier draft of this document
declared, and `022_report_exports.sql` with them, are deleted. Two migrations both creating
`report_exports` is a schema that does not build, and the two definitions collided semantically —
`kind` meant the file format in `11` and the report's subject here, so code written against one and
run against the other writes `'HTML'` into a column checked for `'CAMPAIGN'`.

What this document writes, and the name it writes it under:

| What the report needs to record | Column | Note |
|---|---|---|
| File format | `fmt` | `HTML \| CSV \| XLSX \| PDF \| JSON`. Never `kind`; the name is retired from this table |
| What the report covers | `scope` + `scope_key` | `scope IN ('CAMPAIGN','DAILY','CITY','INDUSTRY','TOP_OPPORTUNITIES','SUBJECT_ACCESS','AUDIT')`; `scope_key` is the city, the industry or the `YYYY-MM-DD` |
| Which campaign | `campaign_id` | NULL for a cross-campaign `DAILY` |
| Human label | `title` | e.g. `Dhule healthcare, 70+` |
| Filename, path | `filename`, `rel_path` | §3.2.8 builds both; `rel_path` is relative to `report.dir` |
| Date and cities in the filename | `report_date`, `cities` | `01` §1.2.1 Amendment 3 carried these over from this document precisely because the archive list groups by them and neither is derivable from `scope_key` for a four-city campaign |
| Size and content hash | `bytes`, `content_sha256` | not `sha256` |
| Number hash and payload | `data_sha256`, `data_rel_path` | §3.2.7 produces both |
| Rows in the file | `row_count` | |
| Filters and columns actually applied | `filters_json`, `columns_json` | `filters_json` also carries the old `mode` and `app_base_url`, which are not columns |
| Contact values present | `contains_pii` | not `include_contacts`. `CHECK (contains_pii = 0 OR retention_class <> 'PERMANENT')` is the DPDP purpose-limitation rule as a constraint |
| Provenance | `template_version`, `generator_version`, `db_schema_version`, `query_fingerprint` | `db_schema_version`, not `schema_version` |
| Who built it | `generated_by`, `job_run_id`, `generated_by_job_id` | `generated_by` is the `users` row for a manual export; the job columns are written by the `14-background-jobs.md` handler, not by `build_report()` |
| Build lifecycle | `status`, `error` | `PENDING \| READY \| FAILED \| PURGED`, per Amendment 2. `CHECK (status <> 'READY' OR (bytes > 0 AND length(content_sha256) = 64 AND length(data_sha256) = 64 AND row_count IS NOT NULL))` — a `READY` row without both hashes is impossible |
| Retention | `retention_class`, `expires_at`, `deleted_at`, `deleted_reason` | `deleted_reason`, not `delete_reason`; values `RETENTION \| ERASURE \| MANUAL \| SUPERSEDED` |
| Supersession | `superseded_by` | unchanged |

Three columns this document used to declare are **gone** and their facts live elsewhere: `mode` and
`app_base_url` fold into `filters_json`, and `include_contacts` becomes `contains_pii`. `duration_ms`
is not on the winning table; build duration is `job_runs`, which `14-background-jobs.md` owns.

The row **outlives the file**. A retention sweep sets `deleted_at` and `deleted_reason` and removes
the bytes; the row stays, so "what did the report say on 26 Aug" has an answer even when the answer
is "that file was purged on 24 Nov, `content_sha256` `a3f1…`, 148 rows". Deleting the row instead
would make an old campaign look like it was never reported on — and
`trg_report_exports_no_delete` makes that impossible rather than merely discouraged.
`trg_report_exports_identity_immutable` is the other half: `content_sha256`, `data_sha256`,
`rel_path`, `generated_at`, `row_count` and `query_fingerprint` cannot be edited after the fact, so
an archived report cannot be quietly turned into a different archived report. §42 is worth nothing
without those two triggers.

### 3.12.2 Storage layout

```
data/
  radar.db
  reports/
    cmp_01JSAMPLE0000000000000001/
      business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.html
      business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.csv
      business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.xlsx
      business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.pdf
      business_research_dhule_shirpur_nashik_jalgaon_2026-08-28_v2.html
    daily/
      2026-08-26/business_research_daily_2026-08-26.html
```

`config.yaml`:

```yaml
report:
  dir: data/reports
  panels_inline_max: 800
  window_rows_over: 3000
  embed_font: false
  pdf_engine: none            # none | chromium
  # retention_class is a report_exports column with three legal values (11-audit-architecture.md
  # §11.11.1): PERMANENT, P2Y, P180D. This block maps fmt -> class; begin_export() writes the class
  # and computes expires_at from it. Days are not stored per file.
  retention:
    class_by_fmt:
      HTML: P2Y               # a campaign's HTML is the audit artefact - keep it years
      CSV:  P180D             # regenerable from the DB
      XLSX: P180D             # regenerable
      PDF:  P180D             # regenerable
      JSON: P180D             # the payload beside the HTML
    daily_class: P180D
    keep_latest_per_campaign: true   # never purge the newest of each fmt per campaign
```

`PERMANENT` is never chosen by this document. A report that carries contact values has
`contains_pii = 1`, and `CHECK (contains_pii = 0 OR retention_class <> 'PERMANENT')` refuses to keep
it forever; a report that does not carry them still ages out, because §42 needs the row rather than
the bytes. An `--include-contacts` export is therefore `contains_pii = 1, retention_class = 'P180D'`
and the constraint, not a convention, is what enforces it.

Path handling rules, because §47 asks for secure file handling:

- `rel_path` is always relative to `report.dir` and is built from a validated campaign id and a slug
  produced by `report_filename()`. It never concatenates user text.
- Before writing or serving, `(report_dir / rel_path).resolve()` must be inside
  `report_dir.resolve()`; otherwise the operation raises. This is checked on both the write and the
  read path, so a hand-edited `rel_path` in the database cannot serve `/etc/passwd`.
- Files are written `0o600` on POSIX, into a directory created `0o700`.

### 3.12.3 Retention sweep

```python
def sweep_reports(conn, *, now: datetime, dry_run: bool = False) -> SweepResult:
    """Delete expired export files, keeping the newest of each format per campaign.

    Retention is per format because the formats are not equally replaceable. The HTML is the thing
    Sagar looked at and possibly emailed - it is evidence. The CSV and XLSX can be regenerated from
    the database in a second, so keeping two years of them is just disk.
    """
```

It selects `WHERE expires_at <= :now AND deleted_at IS NULL`, unlinks the file and the payload, and
writes `deleted_at`, `deleted_reason = 'RETENTION'`, `status = 'PURGED'`. It **never** issues a
`DELETE` — `trg_report_exports_no_delete` would abort it, and that is the intended behaviour: files
get deleted, rows get tombstoned. The identity trigger permits this update because the retention and
deletion columns are exactly the ones it leaves writable.

Runs nightly as a `jobs` row (`type='sweep_reports'`). It never deletes a file whose
`report_exports` row is missing — an unknown file in the reports directory is logged loudly and left
alone, matching the house rule that corrupt or unexpected state is moved aside noisily rather than
cleaned up silently.

### 3.12.4 Reopening an old campaign (§42)

Two distinct actions, and conflating them is the trap:

| Action | Route | What it shows |
|---|---|---|
| **Open the archived file** | `GET /api/v1/report_exports/<rex_id>` | the bytes as exported, frozen; `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox` |
| **Reopen the campaign live** | `GET /campaigns/<campaign_id>` | current state, re-queried |

The archive index at `/campaigns/<id>#exports` lists every export for the campaign — `report_date`,
`fmt`, `scope`/`scope_key`, `row_count`, `bytes`, `generated_by`, `status`, and the first 12 hex of
`content_sha256` — so it is obvious which of the two Sagar is about to do. It groups by `report_date`
and orders by `generated_at DESC`, which is why `01` §1.2.1 Amendment 3 kept `report_date` and
`cities` as real columns. A `PENDING` row renders as `building…` and a `FAILED` row renders its
`error`; a build that crashed is visible in the archive rather than absent from it, which is the
whole point of writing the row before the file (§3.2.7). A `PURGED` row renders the hash and the row
count with the file link disabled.

Opening the live campaign for an old campaign shows a **drift banner** computed on the spot:

```sql
-- :exported_at is the generated_at of the newest live HTML export for this campaign:
--   SELECT generated_at, data_sha256 FROM report_exports
--    WHERE campaign_id = :campaign_id AND fmt = 'HTML' AND scope = 'CAMPAIGN'
--      AND status = 'READY' AND deleted_at IS NULL
--    ORDER BY generated_at DESC LIMIT 1;
-- Re-computing today's data_sha256 and comparing it to that row's is the cheap first check:
-- equal hashes mean nothing that reaches the report has moved and the banner is suppressed
-- outright. The count below is only run when they differ, and it says what moved.
SELECT COUNT(*) AS changed
FROM v_report_business r
WHERE r.campaign_id = :campaign_id
  AND ( r.verified_at   > :exported_at
     OR r.last_sent_at  > :exported_at
     OR r.last_response_at > :exported_at
     OR EXISTS (SELECT 1 FROM audit_log a
                 WHERE a.entity_id = r.business_id
                   AND a.action IN ('BUSINESS_STATUS_CHANGED','SUPPRESSION_CREATED')
                   AND a.created_at > :exported_at) );
```

```
This campaign was last exported 34 days ago. 12 of 148 businesses have changed since:
9 verified, 2 contacted, 1 opted out.   [ Re-export ]
```

An archived HTML file opened directly gets the same message from the other side, from its own
embedded `generated_at` (§3.1.4's banner). Between the two, there is no way to look at stale campaign
data without being told it is stale — which matters most for the one field where staleness is
dangerous: a business that opted out after the export still shows as selectable in the file, and the
export's read-only degradation plus the live app's re-check are the two independent things that stop
that becoming a send.

There is no `ADHOC` value. An export produced from the UI with a filter set applied is an ordinary
`scope='CAMPAIGN'` export whose `filters_json` is not `'{}'`, or — when the filter is a single city
or a single industry — `scope='CITY'` / `scope='INDUSTRY'` with the value in `scope_key`, which is
what makes the archive filterable by "every Dhule export" without parsing JSON. `filters_json`
records the filter state either way, so "the list I sent my accountant" is reproducible.
`01-data-model.md` §1.2.1 Amendment 1 fixes that vocabulary; `ADHOC` was this document's third,
losing spelling of a subject column.

---

## 3.13 Performance: what happens at 5,000 businesses

### 3.13.1 The budget

Targets, measured on the reference machine (a mid-range laptop, Chrome, no throttling). These are
budgets the build asserts against, not aspirations.

| Metric | 500 rows | 1,500 rows | 5,000 rows | Hard ceiling |
|---|---|---|---|---|
| `load_report_data()` | < 120 ms | < 300 ms | < 900 ms | 2 s |
| Jinja render | < 200 ms | < 500 ms | < 1.5 s | 4 s |
| Inline + write | < 50 ms | < 80 ms | < 200 ms | 1 s |
| HTML file size | < 1.2 MB | < 3 MB | **< 8 MB** | 12 MB |
| Time to first paint | < 400 ms | < 700 ms | < 1.8 s | 3 s |
| `applyFilters()` | < 8 ms | < 20 ms | **< 60 ms** | 120 ms |
| Sort | < 10 ms | < 30 ms | < 90 ms | 200 ms |
| Search keystroke (debounced) | < 8 ms | < 20 ms | < 60 ms | 120 ms |
| Peak tab memory | < 120 MB | < 220 MB | < 550 MB | 900 MB |

Where the bytes go, at 5,000 rows (estimates, to be replaced by measurements from
`tests/perf/test_report_budget.py`):

| Component | Per row | 5,000 rows |
|---|---|---|
| `<tr>` markup + 15 data attributes | ~1.1 KB | ~5.5 MB |
| Research panel, if rendered inline | ~3.8 KB | ~19 MB — **not viable** |
| Research panel as JSON island | ~1.4 KB | ~7 MB — still too much |
| JSON island, panels trimmed (see below) | ~0.55 KB | ~2.7 MB |
| CSS + JS, fixed | — | ~50 KB |

The arithmetic settles the design: a 5,000-business campaign cannot carry full research panels for
every business in one self-contained file, and pretending otherwise produces a 25 MB attachment that
Gmail rejects.

### 3.13.2 The three tiers

Chosen by row count at build time, from `config.yaml`:

| Rows | Panels | Table rendering | Notes |
|---|---|---|---|
| <= 800 (`panels_inline_max`) | rendered inline as real DOM | all rows in DOM | Ctrl+F finds panel text; print works with no JS |
| 801 – 3,000 | JSON island, hydrated on expand | all rows in DOM | the normal case for a four-city campaign |
| > 3,000 (`window_rows_over`) | JSON island, **trimmed** | windowed rendering | see below |

**Trimmed panels** at tier 3 keep, per business: the opportunity block, the top 5 OBSERVED findings,
the top 2 INFERRED, all UNKNOWN statements (they are short and §12 makes them mandatory), and every
source. Findings beyond that are replaced by one line — `+ 9 more findings — open in the app` —
linking to `/business/<id>`. The trim is recorded in the footer and in `report_exports.filters_json`
so nobody later mistakes a trimmed export for a complete one.

**Windowed rendering** at tier 3:

```js
/* Render only what is near the viewport. The full row list lives in ROWDATA, an array of the same
   dataset objects the DOM rows carry, so filtering and sorting run over data and never over DOM. */
var WINDOW = 150, OVERSCAN = 60;

function renderWindow(scrollTop) {
  var first = Math.max(0, Math.floor(scrollTop / ROW_H) - OVERSCAN);
  var last  = Math.min(VISIBLE.length, first + WINDOW + 2 * OVERSCAN);
  if (first === WIN.first && last === WIN.last) { return; }
  var frag = document.createDocumentFragment();
  for (var i = first; i < last; i++) { frag.appendChild(buildRow(VISIBLE[i])); }
  tbody.replaceChildren(frag);
  spacerTop.style.height    = (first * ROW_H) + "px";
  spacerBottom.style.height = ((VISIBLE.length - last) * ROW_H) + "px";
  WIN = {first: first, last: last};
}
```

Windowing breaks two things, and both get an explicit answer rather than being ignored:

| Broken | Answer |
|---|---|
| Ctrl+F only finds rendered rows | the in-report search box (§3.6.3) searches all rows; a persistent hint sits beside it: `This report is windowed — use this search box, not Ctrl+F.` A `Render all rows` button exits windowing at the cost of a slow page, and the button says so |
| Printing would print 150 rows | `beforeprint` calls `renderAllRows()` (§3.10) |

Row height is fixed at tier 3 (`--row-h: 34px`, `table-layout: fixed`, one-line cells with
`text-overflow: ellipsis`) because variable heights make the spacer arithmetic wrong and the scrollbar
jump.

### 3.13.3 Rendering the initial DOM without freezing the tab

At tiers 1 and 2 the whole table is in the HTML the browser parses, which is fine — parsing 5 MB of
static markup is a straight-line cost the browser is good at. The expensive part is our own
post-load work, so it is chunked:

```js
function chunked(items, size, fn, done) {
  var i = 0;
  (function step() {
    var end = Math.min(i + size, items.length);
    for (; i < end; i++) { fn(items[i], i); }
    if (i < items.length) { requestAnimationFrame(step); } else if (done) { done(); }
  })();
}
```

Used for building `ROWS`, attaching group headings, and the first `applyFilters()`. The result line
shows `Preparing 5,000 rows…` while it runs and the filter bar is disabled until it finishes — the
one place where showing a control that does not yet work would be worse than showing a spinner.

### 3.13.4 Other measures that keep the budget

| Measure | Effect |
|---|---|
| Filter reads `dataset` only, never text | no layout thrash; `passes()` is pure |
| `tr.hidden` toggled only when it changes | avoids 5,000 no-op style writes per keystroke |
| `content-visibility: auto; contain-intrinsic-size: 0 34px` on `.brow` | the browser skips layout for off-screen rows even at tiers 1-2 |
| Search debounced 120 ms | one pass per pause, not per keystroke |
| Sort on a detached array, re-append via one fragment | one reflow instead of N |
| Category group headings hidden via a count, not a DOM scan | O(groups), not O(rows) |
| No per-row event listeners | one delegated `click` handler on `<tbody>` |
| Panels hydrated on demand and cached | expanding 20 panels costs 20 builds, not 5,000 |
| `report.js` is not minified | debuggability beats 6 KB |

### 3.13.5 When the report is the wrong tool

Above roughly 8,000 businesses the self-contained file stops being the right artefact, and the
document says so rather than degrading silently. `build_report()` logs a warning and the report
header carries a line:

```
This campaign has 9,412 businesses. This file is windowed and its research panels are trimmed.
Use the live app for anything beyond a first pass, or export a filtered subset.
```

Exporting a filtered subset is the intended escape hatch: `POST /api/v1/report_exports` accepts the
current `filters_json`, and the resulting export contains only the matching rows, with the filter set
printed in its header and recorded in `filters_json` on the row (§3.12.4).

---

## 3.14 Responsive layout and accessibility (§50)

| Breakpoint | Layout |
|---|---|
| >= 1280 px | full 14-column table, KPI row 6 across, city cards 4 across |
| 1024 – 1279 px | KPI row 4 across, city cards 3 across; table scrolls horizontally inside `.tablewrap` |
| 720 – 1023 px | KPI row 3 across; columns Digital Maturity, Category and Discovered collapse into the Business cell's sub-line |
| < 720 px | the table becomes **cards**: one `<article>` per business with the same data attributes, so every filter and sort keeps working unchanged |

```css
.tablewrap{ overflow-x:auto; }          /* the table scrolls, the page never does */
body{ overflow-x:hidden; }

@media (max-width: 719px){
  .btable thead{ display:none; }
  .btable tr{ display:block; border:1px solid var(--rule); border-radius:var(--r); margin:8px 0; }
  .btable td{ display:flex; justify-content:space-between; gap:12px; border:0; }
  .btable td::before{ content:attr(data-label); color:var(--text-2); font-size:11px; }
}
```

Every `<td>` carries `data-label` with its column name so the card layout is generated by CSS from
the same markup — there is no second mobile template.

Accessibility requirements, all of which are testable:

| Requirement | Implementation |
|---|---|
| Tabs | `role="tablist"/"tab"/"tabpanel"`, `aria-selected`, `aria-controls`, arrow-key navigation, `Home`/`End` |
| Tables | `<caption>` naming the city+industry pane, `<th scope="col">`, `<th scope="row">` on the business cell |
| Sort state | `aria-sort="ascending|descending|none"` on the active `<th>` |
| Disabled checkbox reason | visually-hidden text + `aria-describedby` (§3.7.1) |
| Filter results | `<div role="status" aria-live="polite">Showing 63 of 148 businesses</div>` |
| Panels | the toggle is a `<button aria-expanded>` with `aria-controls`; focus moves into the panel on open and back to the button on close |
| Focus | `:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }`, never removed |
| Motion | all transitions inside `@media (prefers-reduced-motion: no-preference)` |
| Zoom | layout holds to 200% because every size is `rem`/`%` and nothing is absolutely positioned |
| Colour | never the only channel (§3.9.3) |

---

## 3.15 Tests

`tests/report/`, pytest, no network, fixtures over mocks — matching the house convention.

| Test | Asserts |
|---|---|
| `test_export_has_no_form_no_post_no_secret` | the produced bytes contain no `<form`, no `method=`, no `XMLHttpRequest`, no `fetch(` outside `probeApp`, and nothing matching the secret patterns |
| `test_export_has_no_send_control` | no element with text `SEND` or class `send` exists in either mode |
| `test_export_is_offline` | with `app_base_url=None` the file contains zero absolute URLs to the app host and no `connect-src` beyond `'none'` |
| `test_export_csp_present` | the meta CSP exists and contains `form-action 'none'` |
| `test_export_is_self_contained` | no `<link rel=stylesheet>`, no `<script src>`, no `http(s)://` in `src`/`href` except allow-listed source links |
| `test_export_is_deterministic` | two renders with a frozen clock are byte-identical |
| `test_filename_slugging` | the table in §3.2.8, including the 5-city and `Nashik Road` cases |
| `test_kpi_sql_matches_python` | the twelve KPI aggregates equal counts computed in Python over the same fixture |
| `test_kpi_zero_vs_null_render_differently` | `class="na"` where NULL, a literal `0` where zero |
| `test_no_coalesce_to_zero` | `report_queries.py` contains no `COALESCE(...,0)` on a nullable metric |
| `test_city_card_for_empty_city` | a targeted city with no businesses still gets a card |
| `test_findings_sections_always_render` | all three §12 fieldsets present even when empty |
| `test_finding_without_source_marked` | a finding with no `finding_sources` row renders the `no source` badge |
| `test_source_url_scheme_allowlist` | `javascript:` and `data:` source URLs render name-only |
| `test_json_island_escapes_script` | a finding containing `</script>` does not terminate the block |
| `test_autoescape_business_name` | a business named `<img onerror=…>` renders escaped |
| `test_checkbox_enabled_only_for_contact_ready` | §18's table, row by row |
| `test_block_reason_matches_outreach_doc` | `BLOCK_REASON` keys equal the gate codes in `05-outreach-workflow.md` |
| `test_selection_survives_filtering` | (Playwright) filter out a selected row, count stays |
| `test_hash_roundtrip` | (Playwright) every filter serialises and parses back identically |
| `test_unknown_hash_key_ignored` | an old link with a removed key still opens |
| `test_csv_formula_injection_guarded` | a name starting `=` is prefixed |
| `test_csv_bom` | the file starts with `\xef\xbb\xbf` |
| `test_xlsx_null_metrics_are_empty_cells` | `sheet["I2"].value is None`, not `0` |
| `test_xlsx_sheets_present` | four sheets, header freeze, autofilter range |
| `test_report_queries_execute` | **every** constant in `report_queries.py` is `EXPLAIN`-ed and then executed against a freshly migrated database with fixture rows. A column name that exists only in prose — `realised_value_inr`, `b.campaign_id`, `b.discovered_at` — fails here instead of at generation time. §38's revenue aggregate is the reason: a wrong column name there is `sqlite3.OperationalError: no such column` and the whole industry table does not render, and `_CONTEXT.md` invariant 5 makes the report's numbers a safety property |
| `test_view_grain_is_campaign_business` | a business in two campaigns yields two `v_report_business` rows, one per campaign, and each campaign's KPI query returns it exactly once |
| `test_first_seen_campaign_is_not_a_report_filter` | greps `report_queries.py` for `first_seen_campaign_id`; any hit fails. A report scoped by it silently omits rediscovered businesses |
| `test_report_exports_row_written` | one row per file, correct `content_sha256`, `data_sha256` and `bytes`, `status='READY'` |
| `test_report_exports_pending_before_file` | the row exists with `status='PENDING'` before `os.replace()`, and a raised exception leaves `status='FAILED'` with a non-null `error` rather than no row |
| `test_report_exports_data_sha_stable_across_renders` | two renders with different clocks give different `content_sha256` and identical `data_sha256` |
| `test_report_exports_row_is_not_deletable` | `DELETE FROM report_exports` raises; `content_sha256` and `rel_path` cannot be updated; `deleted_at` / `deleted_reason` can |
| `test_report_exports_no_kind_column` | the migrated schema has `fmt` and `scope`, and no column named `kind`, on `report_exports`; and no migration file creates the table twice |
| `test_report_path_traversal_rejected` | a `rel_path` escaping `report.dir` raises on read and on write |
| `test_retention_keeps_latest` | the sweep never deletes the newest of a format per campaign |
| `test_contacts_export_cannot_be_permanent` | an export with `contains_pii = 1` and `retention_class = 'PERMANENT'` is rejected by the `CHECK` |
| `test_perf_budget_5000` | the §3.13.1 ceilings, marked `slow` |
| `test_print_hydrates_panels` | (Playwright) `beforeprint` renders every panel |
| `test_contrast_ratios` | recomputes §3.9.3's table from the CSS tokens and asserts >= 4.5 |

The two Playwright-driven groups reuse the browser setup already present in this repo; they are
marked `ui` and excluded from the default run.

---

## 3.16 Routes and files

```
UI
  GET  /campaigns/<campaign_id>                     LIVE report
  GET  /campaigns/<campaign_id>#exports             archive index
  GET  /reports/daily/<YYYY-MM-DD>                  §43 daily, LIVE
  GET  /business/<business_id>                      §11 detail, target of VIEW
  GET  /verify/<business_id>                        target of VERIFY / REJECT
  GET  /outreach                                    target of PREPARE OUTREACH
  GET  /outreach/<draft_id>                         target of VIEW MESSAGE

API
  GET  /api/v1/health                               the export's probe target (§3.1.4)
  GET  /api/v1/campaigns/<campaign_id>/report       ReportData as JSON
  POST /api/v1/report_exports                       {campaign_id, formats[], scope, scope_key?,
                                                     filters_json?, include_contacts?, title}
                                                     -> jobs row + one PENDING row per format
  GET  /api/v1/report_exports?campaign_id=&fmt=&scope=   archive listing
  GET  /api/v1/report_exports/<rex_id>              stream the archived file
  DELETE /api/v1/report_exports/<rex_id>            manual delete; sets deleted_at and
                                                     deleted_reason='MANUAL', keeps the row
  GET  /api/v1/reports/daily/<YYYY-MM-DD>           daily as JSON

Files
  radar/report.py            build orchestration, filenames, archive rows, dash()/inr() filters
  radar/report_queries.py    Q1-Q12 and Q_DAILY_*
  radar/report_export.py     CSV / XLSX / PDF writers
  radar/web/app.py           routes above
  radar/web/templates/report/*.html
  radar/web/static/report.css, report.js
  radar/migrations/049_v_report_business.sql
  tests/report/*
```

This document contributes **one** migration. `report_exports` is created by
`radar/migrations/048_report_exports.sql`, which belongs to `11-audit-architecture.md` §11.11.1 as
amended by `01-data-model.md` §1.2.1; the `022_report_exports.sql` an earlier draft listed here does
not exist. `049_v_report_business.sql` was `021` and is renumbered by `01-data-model.md` §1.13.2,
because the view now reads `campaign_businesses` and must be created after it.

`POST /api/v1/report_exports` enqueues a `jobs` row (`type='generate_report'`, and `export_csv` /
`export_xlsx` / `export_pdf` for the other formats — `14-background-jobs.md` §14.8 owns the registry
and the column is `jobs.type`) rather than building inline: a 5,000-row export takes seconds, and a
request that holds a waitress worker for three seconds is a request that times out behind Caddy on a
bad day. The `report_exports` rows are inserted `PENDING` by the request, so the response carries a
`rex_id` per format immediately. The UI polls `GET /api/v1/jobs/<job_id>` and offers the download
when the export flips to `READY`.

---

## Open questions

1. **`digital_maturity` lives in two places.** `05-outreach-workflow.md` reads
   `opportunities.digital_maturity`; `10-human-handoff.md` reads `businesses.digital_maturity`. This
   document uses `opportunities.digital_maturity` throughout, on the grounds that it is a scored
   artefact with a `model_id` and `prompt_version` beside it. `01-data-model.md` must pick one and
   either drop the other or declare it a denormalised mirror maintained by `radar/score.py`.

2. **`research_findings` column names differ between sibling documents.**
   `05-outreach-workflow.md` uses `statement` and `dimension`; `10-human-handoff.md` uses `label`,
   `detail` and `weight`. §3.4.6.1 assumes all of `kind`, `dimension`, `label`, `statement`,
   `confidence`, `confidence_pct`, `weight` exist, with `label` as an optional short heading and
   `statement` as the verbatim text. `01-data-model.md` should confirm or collapse them.

3. **`est_value_inr` has no owner yet.** §37's Potential Revenue column depends on it, and this
   document only specifies that it is nullable and never defaulted. Which module writes it —
   `radar/score.py` from a per-category rule, or Sagar by hand on the business detail screen — is
   not settled. Until it is, the column renders `—` for every city, which is correct but not useful.

4. **Which suppression scopes tint a report row red.** §3.7.1 tints on any live `suppressions` match
   including `DOMAIN` scope. A domain-wide block from one bounced address would then tint every
   business at that domain, which is right for outreach and possibly alarming in a research report.
   Confirm with `05-outreach-workflow.md` whether the report should distinguish "this business opted
   out" from "something at this domain is blocked".

5. **Daily report scope across campaigns.** §43 is date-scoped and this document makes it
   cross-campaign, which is what "DAILY BUSINESS OPPORTUNITY REPORT" implies. If Sagar ever runs two
   unrelated campaigns on the same day, the daily merges them. A `?campaign=` filter is easy to add;
   whether it should be the default is a product call.

6. **PDF on the VPS.** The recommendation is browser print-to-PDF for v1 and Chromium behind a flag.
   If the nightly Telegram message should carry a PDF rather than a link, Chromium becomes a required
   VPS dependency (~150 MB plus fonts) and that needs to be agreed against the small-VPS constraint in
   `_CONTEXT.md` §2.

7. ~~**`id` prefix for `report_exports`.**~~ **Settled.** `01-data-model.md` §1.1.3 ratifies `rex_`.
   The table itself is no longer this document's — `11-audit-architecture.md` §11.11.1 as amended by
   `01-data-model.md` §1.2.1 owns it (§3.12.1).

8. **Two UI routes are extensions.** `_CONTEXT.md` §6's UI route list does not include
   `/reports/daily/<YYYY-MM-DD>` (§43) or the `#exports` archive index on `/campaigns/<id>` (§42).
   Both are needed by spec sections this document owns and neither has an obvious home among the
   eight canonical routes. They are proposed here as additions, not substitutions; the API-endpoints
   document should confirm them.
