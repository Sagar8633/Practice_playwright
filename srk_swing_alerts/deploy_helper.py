#!/usr/bin/env python3
"""Serve a copy-paste helper page for getting the scanners into TradingView.

Why a page and not browser automation: this TradingView account allows one
active session, so driving it from a script disconnects the browser the user is
actually trading in. And typing Pine into the editor corrupts indentation via
Monaco's auto-indent, so the text has to arrive through the clipboard anyway.
A local page with a Copy button per script solves both without touching the
account.

It is served over http://localhost rather than opened as a file:// URL because
navigator.clipboard needs a secure context, and localhost counts as one.

    python deploy_helper.py            # build, serve, open the browser
    python deploy_helper.py --port 8900
    python deploy_helper.py --build-only
"""
from __future__ import annotations

import argparse
import http.server
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from srk.universe import load_symbols, tradingview_symbol  # noqa: E402

ROOT = Path(__file__).resolve().parent
PINE_DIR = ROOT / "pine"

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>SRK Scanner - TradingView setup</title>
<style>
  :root {
    --bg:#131722; --panel:#1e222d; --line:#2a2e39; --ink:#d1d4dc;
    --dim:#787b86; --accent:#2962ff; --ok:#26a69a; --warn:#f7931a;
  }
  * { box-sizing:border-box }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:14px/1.6 -apple-system,"Segoe UI",Roboto,sans-serif; }
  .wrap { max-width:900px; margin:0 auto; padding:32px 20px 80px }
  h1 { font-size:22px; margin:0 0 6px }
  h2 { font-size:16px; margin:34px 0 10px; padding-bottom:6px;
       border-bottom:1px solid var(--line) }
  .sub { color:var(--dim); margin:0 0 24px }
  .note { background:var(--panel); border-left:3px solid var(--warn);
          padding:12px 16px; border-radius:0 6px 6px 0; margin:16px 0 }
  .note.ok { border-left-color:var(--ok) }
  ol.steps { padding-left:20px } ol.steps li { margin:7px 0 }
  kbd { background:var(--line); border-radius:3px; padding:1px 6px;
        font:12px ui-monospace,monospace }
  code { font:12.5px ui-monospace,SFMono-Regular,Consolas,monospace;
         background:var(--line); padding:1px 5px; border-radius:3px }
  table.scripts { width:100%; border-collapse:collapse; margin-top:8px }
  table.scripts th { text-align:left; font-size:11px; letter-spacing:.06em;
        text-transform:uppercase; color:var(--dim); font-weight:600;
        padding:8px 10px; border-bottom:1px solid var(--line) }
  table.scripts td { padding:11px 10px; border-bottom:1px solid var(--line);
        vertical-align:middle }
  tr.skip { opacity:.45 }
  .rank { font:12px ui-monospace,monospace; color:var(--dim) }
  .name { font-weight:600 }
  .range { color:var(--dim); font-size:12.5px }
  button.copy { background:var(--accent); color:#fff; border:0; cursor:pointer;
        padding:7px 15px; border-radius:5px; font-size:13px; font-weight:600;
        white-space:nowrap; min-width:92px }
  button.copy:hover { filter:brightness(1.12) }
  button.copy.done { background:var(--ok) }
  button.peek { background:none; border:1px solid var(--line); color:var(--dim);
        cursor:pointer; padding:6px 11px; border-radius:5px; font-size:12px }
  pre { background:var(--panel); border:1px solid var(--line); border-radius:6px;
        padding:14px; overflow:auto; max-height:340px; font-size:11.5px;
        margin:10px 0 0 }
  .chk { display:flex; align-items:flex-start; gap:10px; padding:7px 0 }
  .chk input { margin-top:5px; width:15px; height:15px; accent-color:var(--ok) }
  .chk label { flex:1 } .chk input:checked + label { color:var(--dim);
        text-decoration:line-through }
  .syms { color:var(--dim); font-size:12px; margin-top:6px; line-height:1.7 }
</style>
<div class="wrap">
<h1>SRK Swing Scanner &rarr; TradingView</h1>
<p class="sub">{{total}} F&amp;O symbols across {{nscripts}} scripts &middot; 15-minute timeframe
&middot; one alert per script</p>

<div class="note">
<strong>Your budget: 5 alerts (free plan).</strong> Deploy <strong>b1&ndash;b5</strong>
below, in that order. The list is sorted by traded value, so b1 carries the 40
busiest F&amp;O stocks and each later batch matters less. b1&ndash;b5 covers
<strong>200 of {{total}} names</strong>; only b6 (the 12 thinnest, plus the four
indices Yahoo reports no volume for) is left out.
</div>

<h2>1 &middot; Copy each script</h2>
<table class="scripts"><thead><tr>
  <th>#</th><th>Script</th><th>Symbols</th><th>Turnover rank</th><th></th><th></th>
</tr></thead><tbody>
{{rows}}
</tbody></table>

<h2>2 &middot; Paste into the Pine Editor</h2>
<ol class="steps">
  <li>On TradingView, open <strong>Pine Editor</strong> (bottom panel).</li>
  <li><strong>Open &rarr; New indicator</strong>.</li>
  <li>Click inside the editor, <kbd>Ctrl</kbd>+<kbd>A</kbd>, then
      <kbd>Ctrl</kbd>+<kbd>V</kbd>. Paste &mdash; never type. Monaco's
      auto-indent silently corrupts hand-typed Pine.</li>
  <li><strong>Save</strong> (<kbd>Ctrl</kbd>+<kbd>S</kbd>), keep the script's own
      name, then <strong>Add to chart</strong>.</li>
  <li>Set the chart to the <strong>15m</strong> timeframe.</li>
</ol>

<h2>3 &middot; Create the alert</h2>
<ol class="steps">
  <li>Press <kbd>Alt</kbd>+<kbd>A</kbd>.</li>
  <li><strong>Condition</strong> &rarr; the scanner script's name.</li>
  <li>The dropdown just below it &rarr; <strong>Any alert() function call</strong>.
      This is the setting that makes one alert cover all 40 symbols &mdash; get it
      wrong and you get nothing.</li>
  <li><strong>Notifications</strong> tab &rarr; tick <strong>Notify on app</strong>
      (this is the phone push), plus <strong>Show popup</strong> and
      <strong>Play sound</strong>.</li>
  <li>Leave the message box alone. The script writes it.</li>
  <li><strong>Expiration</strong> &rarr; as far out as the plan allows, then
      <strong>Create</strong>.</li>
</ol>

<div class="note">
<strong>Only 2 indicators fit on a chart at once (free plan).</strong> That is
fine: an alert keeps running after you remove the indicator. So &mdash; add b1,
create its alert, <em>remove b1 from the chart</em>, add b2, and so on. Check the
Alerts panel afterwards; all five should read as active.
</div>

<div class="note ok">
<strong>These alerts never fire on history.</strong> TradingView ignores
<code>alert()</code> on historical bars, and the script also gates on
<code>barstate.isconfirmed</code> with <code>alert.freq_once_per_bar_close</code>.
Nothing triggers until a real 15m candle closes while the alert is live.
</div>

<h2>4 &middot; Prove the phone push works</h2>
<ol class="steps">
  <li>Install the TradingView app and sign in as the same account.</li>
  <li>Open b1's settings on the chart and set <strong>ADX threshold</strong> to
      <code>0</code>, then edit its alert so it uses that setting.</li>
  <li>Wait for the next 15m close &mdash; with the threshold at 0 something fires
      almost immediately. Confirm the phone buzzes.</li>
  <li>Put the threshold back to <code>20</code>.</li>
</ol>

<h2>Progress</h2>
<div id="checklist"></div>

<script>
const SCRIPTS = {{scripts_json}};
const DEPLOY  = {{deploy_json}};

function copyText(t) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(t);
  const ta = document.createElement('textarea');
  ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta); ta.select();
  document.execCommand('copy'); ta.remove();
  return Promise.resolve();
}

document.querySelectorAll('button.copy').forEach(btn => {
  btn.onclick = () => {
    copyText(SCRIPTS[btn.dataset.key]).then(() => {
      const old = btn.textContent;
      btn.textContent = 'Copied'; btn.classList.add('done');
      setTimeout(() => { btn.textContent = old; btn.classList.remove('done') }, 1600);
    });
  };
});

document.querySelectorAll('button.peek').forEach(btn => {
  btn.onclick = () => {
    const pre = document.getElementById('src-' + btn.dataset.key);
    const open = pre.style.display === 'block';
    pre.style.display = open ? 'none' : 'block';
    btn.textContent = open ? 'View' : 'Hide';
    if (!open && !pre.textContent) pre.textContent = SCRIPTS[btn.dataset.key];
  };
});

const box = document.getElementById('checklist');
DEPLOY.forEach(k => {
  ['pasted and saved', 'alert created with Any alert() function call',
   'Notify on app ticked', 'removed from chart'].forEach(step => {
    const id = k + '-' + step.slice(0, 8).replace(/\\W/g, '');
    const d = document.createElement('div');
    d.className = 'chk';
    d.innerHTML = '<input type="checkbox" id="' + id + '">' +
                  '<label for="' + id + '"><b>' + k + '</b> &mdash; ' + step + '</label>';
    box.appendChild(d);
  });
});
document.querySelectorAll('#checklist input').forEach(cb => {
  const k = 'srk-' + cb.id;
  try { cb.checked = localStorage.getItem(k) === '1' } catch (e) {}
  cb.onchange = () => { try { localStorage.setItem(k, cb.checked ? '1' : '0') } catch (e) {} };
});
</script>
</div>
"""

ROW = """<tr class="{{cls}}">
  <td class="rank">{{idx}}</td>
  <td class="name">{{stem}}{{tag}}<div class="syms">{{preview}}</div></td>
  <td>{{count}}</td>
  <td class="range">{{rank_range}}</td>
  <td><button class="copy" data-key="{{key}}">Copy</button></td>
  <td><button class="peek" data-key="{{key}}">View</button>
      <pre id="src-{{key}}" style="display:none"></pre></td>
</tr>"""


def render(template: str, values: dict) -> str:
    """{{token}} substitution - safe against CSS percents and braces alike."""
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def build() -> str:
    files = sorted(PINE_DIR.glob("srk_swing_scanner_b*.pine"),
                   key=lambda p: int(p.stem.rsplit("b", 1)[1]))
    if not files:
        raise SystemExit("No scripts in pine/ - run: python generate_scanners.py")

    order = load_symbols(ROOT / "fno_symbols.txt")
    rank = {s: i + 1 for i, s in enumerate(order)}
    scripts, rows, deploy = {}, [], []
    total = 0

    for i, path in enumerate(files, start=1):
        key = path.stem.rsplit("_", 1)[1]                 # "b1"
        text = path.read_text(encoding="utf-8")
        scripts[key] = text
        syms = [ln.split('"')[1] for ln in text.splitlines()
                if ln.startswith("sym") and "input.symbol" in ln]
        plain = [s.split(":", 1)[1] for s in syms]
        total += len(plain)
        ranks = [rank.get(p, 999) for p in plain]
        keep = i <= 5
        if keep:
            deploy.append(key)
        rows.append(render(ROW, {
            "cls": "" if keep else "skip",
            "idx": i, "stem": key.upper(), "key": key, "count": len(plain),
            "tag": "" if keep else "  — skipped at 5 alerts",
            "rank_range": f"#{min(ranks)}–#{max(ranks)}",
            "preview": ", ".join(plain[:9]) + (" …" if len(plain) > 9 else ""),
        }))

    html = render(PAGE, {
        "total": total, "nscripts": len(files), "rows": "\n".join(rows),
        "scripts_json": json.dumps(scripts).replace("</", "<\\/"),
        "deploy_json": json.dumps(deploy),
    })
    out = ROOT / "deploy.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--no-open", action="store_true",
                    help="serve but do not launch a browser")
    args = ap.parse_args()

    out = build()
    print(f"Built {out}")
    if args.build_only:
        return 0

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT), **kw)

        def log_message(self, *a):                        # keep the console quiet
            pass

    # 127.0.0.1, not "localhost": that name resolves to ::1 first on Windows,
    # and this server binds IPv4. 127.0.0.1 is still a secure context, so the
    # clipboard API keeps working.
    url = f"http://127.0.0.1:{args.port}/deploy.html"
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    httpd.daemon_threads = True

    # Serve BEFORE opening the browser. webbrowser.open() can block for a long
    # time on Windows, and anything queued behind it never gets answered.
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"Serving {url}\nPress Ctrl+C when you have finished pasting.")

    if not args.no_open:
        try:
            threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        except Exception as exc:                       # noqa: BLE001
            print(f"(could not launch a browser: {exc} - open the URL yourself)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
