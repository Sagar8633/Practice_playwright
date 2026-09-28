"""Render report.html from results/report_data.json (charts as inline SVG drawn by page JS)."""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(ROOT, "results", "report_data.json")))
PT = pd.DataFrame(D["period_tables"])
PBN = {"A_pingpong": "A ping-pong", "B1_pullback": "B1 breakout + pullback", "B2_immediate": "B2 breakout at close"}


def row(pb, cost, period):
    return PT[(PT.playbook == pb) & (PT.cost == cost) & (PT.period == period)].iloc[0].to_dict()


def clean(v):
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return None
    return v


def recs(df):
    return [{k: clean(v) for k, v in r.items()} for r in df.to_dict(orient="records")]


eq_comb = pd.read_csv(os.path.join(ROOT, "results", "baseline", "equity_AB1_combined_real.csv"))
payload = {
    "period": {pb: {cost: {p: {k: clean(v) for k, v in row(pb, cost, p).items()} for p in ("DEV", "VAL", "OOS", "ALL")} for cost in ("ideal", "real")} for pb in PBN},
    "combined": D["combined"],
    "equity": {pb: D[f"equity_{pb}"] for pb in PBN},
    "equity_ideal": {pb: D[f"equity_ideal_{pb}"] for pb in PBN},
    "equity_comb": {"t": eq_comb.entry_time.tolist(), "eq": eq_comb.equity_r.round(2).tolist(), "dd": eq_comb.drawdown_r.round(2).tolist(),
                    "dd_pct": eq_comb.drawdown_pct_1pct.round(1).tolist(), "eq_usd": eq_comb.equity_usd_1pct_10k.round(0).tolist()},
    "monthly": {pb: D[f"monthly_{pb}"] for pb in PBN},
    "session": {pb: D[f"by_session_{pb}"] for pb in PBN},
    "stype_side": {pb: D[f"by_stype_side_{pb}"] for pb in PBN},
    "year": {pb: D[f"by_year_{pb}"] for pb in PBN},
    "taxonomy": {pb: D[f"taxonomy_{pb}"] for pb in PBN},
    "filters": {pb: D[f"filters_{pb}"] for pb in PBN},
    "exp": {k: D["experiments"][k] for k in ("impulse_definition", "impulse_k", "impulse_N", "range_min_bars", "stop_pingpong", "stop_breakout",
                                              "session_filter", "volatility_filter", "breakout_confirmation", "breakout_penetration",
                                              "va_proximity", "va_source_sensitivity", "va_level_differences", "news_filter", "structure_side")},
    "stages": D["stages"], "stages_yearly": D["stages_yearly"], "walk_forward": D["walk_forward"], "costs": D["costs"],
    "grids": D["grids"], "structure_stats": D["structure_stats"], "A_facts": D["A_facts"], "data": D["data"],
    "examples_A": D["examples_A"], "examples_B1": D["examples_B1"], "label_rules": D["label_rules"], "signals": D["signals"],
}


def js_clean(o):
    if isinstance(o, dict):
        return {k: js_clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [js_clean(v) for v in o]
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)):
        return None
    return o


payload = js_clean(payload)
A = payload["period"]["A_pingpong"]["real"]["ALL"]; Ai = payload["period"]["A_pingpong"]["ideal"]["ALL"]
B1 = payload["period"]["B1_pullback"]["real"]["ALL"]; B1i = payload["period"]["B1_pullback"]["ideal"]["ALL"]
B2 = payload["period"]["B2_immediate"]["real"]["ALL"]; B2i = payload["period"]["B2_immediate"]["ideal"]["ALL"]
S = payload["structure_stats"]; F = payload["A_facts"]

HTML = r"""<title>PBD Gold Backtest</title>
<meta name="description" content="Baseline test, loss taxonomy and no-trade conditions for the PBD counter-trend framework on XAUUSD, 2021-2026.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  color-scheme:light;
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7;
  --border:rgba(11,11,11,.10); --accent:#8a6a1f; --accent-soft:#f3ecd9;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --neg:#e34948; --pos:#2a78d6; --mid:#f0efec;
  --good:#006300; --crit:#d03b3b;
  --serif:"Source Serif 4",Georgia,"Times New Roman",serif; --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif; --mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); --accent:#d4aa4a; --accent-soft:#2a2410;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --neg:#e66767; --pos:#3987e5; --mid:#383835; --good:#0ca30c; --crit:#e66767;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); --accent:#d4aa4a; --accent-soft:#2a2410;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --neg:#e66767; --pos:#3987e5; --mid:#383835; --good:#0ca30c; --crit:#e66767;
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.55}
.wrap{max-width:1040px;margin:0 auto;padding-inline:16px;padding-block:24px 64px}
header.hero{display:grid;grid-template-columns:minmax(0,1fr);gap:14px;padding-block:8px 28px;border-bottom:1px solid var(--border)}
header.hero>*{min-width:0}
.eyebrow{font-family:var(--sans);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);font-weight:600}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(28px,4.5vw,40px);line-height:1.15;margin:0;text-wrap:balance;max-width:22ch}
.lede{max-width:70ch;color:var(--ink2);font-size:16px;margin:0}
.verdict{display:inline-flex;align-items:center;gap:10px;background:var(--accent-soft);border:1px solid var(--border);border-radius:24px;padding:6px 14px;font-weight:600;font-size:14px;justify-self:start;max-width:100%;text-wrap:balance}
.verdict .dot{width:10px;height:10px;border-radius:50%;background:var(--accent);flex:none}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:8px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 14px;display:grid;gap:4px}
.tile .l{font-size:12px;color:var(--ink2)}
.tile .v{font-size:26px;font-weight:600;line-height:1.1}
.tile .d{font-size:12px;color:var(--muted)}
nav.toc{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--plane);border-bottom:1px solid var(--border);margin:0 -16px;padding:8px 16px;overflow-x:auto;white-space:nowrap;scrollbar-width:thin}
nav.toc a{display:inline-block;font-size:12.5px;color:var(--ink2);text-decoration:none;padding:5px 10px;border-radius:999px;border:1px solid transparent;margin-right:4px}
nav.toc a:hover,nav.toc a:focus-visible{border-color:var(--border);color:var(--ink);outline:none}
section{padding-block:36px 8px;border-bottom:1px solid var(--border)}
section h2{font-family:var(--serif);font-weight:600;font-size:26px;margin:0 0 6px;text-wrap:balance}
section h2 .n{color:var(--accent);font-family:var(--mono);font-size:15px;margin-right:10px;font-weight:500}
section h3{font-size:16px;font-weight:600;margin:26px 0 8px}
p{max-width:72ch}
p.note{color:var(--ink2);font-size:14px}
ul{max-width:72ch;padding-left:20px}
li{margin-bottom:6px}
.fig{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 14px 10px;margin:14px 0}
.fig .t{font-weight:600;font-size:14px;margin:0 0 2px}
.fig .s{font-size:12.5px;color:var(--ink2);margin:0 0 10px}
.fig svg{width:100%;height:auto;display:block;overflow:visible}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--ink2);margin:8px 0 2px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:14px;height:3px;border-radius:2px;display:inline-block}
.legend i.sq{width:11px;height:11px;border-radius:2px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.tbl{overflow-x:auto;margin:10px 0 4px;border:1px solid var(--border);border-radius:8px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap;font-variant-numeric:tabular-nums}
th{color:var(--ink2);font-weight:600;text-align:right;background:var(--surface);position:sticky;top:0}
th:first-child,td:first-child{text-align:left}
td.txt{text-align:left;white-space:normal;min-width:180px}
tr:last-child td{border-bottom:none}
td.neg{color:var(--crit)} td.posv{color:var(--good)}
details{margin:4px 0 10px}
summary{cursor:pointer;font-size:13px;color:var(--ink2)}
.tip{position:fixed;pointer-events:none;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:6px 9px;font-size:12px;color:var(--ink);box-shadow:0 4px 14px rgba(0,0,0,.12);z-index:20;display:none;max-width:260px;font-family:var(--mono)}
.callout{border-left:3px solid var(--accent);padding:6px 14px;margin:14px 0;background:var(--surface);border-radius:0 8px 8px 0;max-width:72ch}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:14px;max-width:72ch}
.kv div:nth-child(odd){color:var(--ink2)}
code{font-family:var(--mono);font-size:12.5px;background:var(--accent-soft);padding:1px 5px;border-radius:4px}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:999px;border:1px solid var(--border);color:var(--ink2);margin-left:6px}
.tag.ok{border-color:var(--good);color:var(--good)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px}
.chips button{font:inherit;font-size:12.5px;padding:4px 10px;border-radius:999px;border:1px solid var(--border);background:var(--surface);color:var(--ink2);cursor:pointer}
.chips button[aria-pressed="true"]{border-color:var(--accent);color:var(--ink);background:var(--accent-soft)}
.chips button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion: no-preference){ .fig svg path.line{transition:opacity .2s} }
@media (max-width:520px){ .tile .v{font-size:22px} section h2{font-size:22px} }
</style>
<div class="wrap">
<header class="hero">
  <div class="eyebrow">XAUUSD · 15-minute PBD structures · Sep 2021 to Sep 2026</div>
  <h1>PBD counter-trend framework on Gold: what the data shows</h1>
  <p class="lede">Patrick Nill's P/B impulse-then-range method, translated into pre-registered objective rules and run on five years of Dukascopy M1 gold with XM costs. Both playbooks, every losing trade classified, no-trade filters, controlled adaptations, walk-forward, out-of-sample.</p>
  <div class="verdict"><span class="dot"></span>Verdict: no positive expectancy in any period; no Gold specification issued</div>
  <div class="tiles" id="tiles"></div>
</header>
<nav class="toc" id="toc"></nav>
<div id="content"></div>
</div>
<div class="tip" id="tip"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const PBN = {A_pingpong:'A ping-pong', B1_pullback:'B1 breakout + pullback', B2_immediate:'B2 breakout at close'};
const tip = document.getElementById('tip');
const fmt = (v,d=3) => (v==null||Number.isNaN(v)) ? '' : (typeof v==='number' ? v.toFixed(d) : String(v));
const fmtR = v => v==null ? '' : (v>=0?'+':'')+v.toFixed(3)+'R';
const pct = v => v==null ? '' : (v*100).toFixed(1)+'%';
function el(tag, attrs={}, ...kids){ const e=document.createElement(tag); for(const [k,v] of Object.entries(attrs)){ if(k==='html') e.innerHTML=v; else if(k==='text') e.textContent=v; else e.setAttribute(k,v);} for(const k of kids){ if(k==null) continue; e.append(k.nodeType?k:document.createTextNode(k)); } return e; }
function showTip(ev, html){ tip.innerHTML=html; tip.style.display='block'; const x=Math.min(ev.clientX+14, window.innerWidth-280), y=Math.min(ev.clientY+14, window.innerHeight-90); tip.style.left=x+'px'; tip.style.top=y+'px'; }
function hideTip(){ tip.style.display='none'; }
const SV='http://www.w3.org/2000/svg';
function sv(tag, attrs={}){ const e=document.createElementNS(SV,tag); for(const [k,v] of Object.entries(attrs)) e.setAttribute(k,v); return e; }
function niceTicks(lo, hi, n=5){ const span=hi-lo||1; const step0=span/n; const p=Math.pow(10,Math.floor(Math.log10(step0))); const m=step0/p; const step=(m<1.5?1:m<3?2:m<7?5:10)*p; const t=[]; for(let v=Math.ceil(lo/step)*step; v<=hi+1e-9; v+=step) t.push(+v.toFixed(10)); return t; }

// ---------- table ----------
function table(rows, cols, opts={}){
  const t=el('table'); const thead=el('thead'); const tr=el('tr');
  cols.forEach(c=>tr.append(el('th',{text:c.label||c.key}))); thead.append(tr); t.append(thead);
  const tb=el('tbody');
  rows.forEach(r=>{ const tr=el('tr'); cols.forEach(c=>{ let v=r[c.key]; let txt; if(c.fmt) txt=c.fmt(v); else if(typeof v==='number') txt=Number.isInteger(v)?String(v):v.toFixed(c.d??3); else txt=(v==null?'':String(v));
    const td=el('td',{text:txt}); if(c.text) td.className='txt'; if(c.sign && typeof v==='number'){ td.className = v<0?'neg':(v>0?'posv':''); } tr.append(td); }); tb.append(tr); });
  t.append(tb); const box=el('div',{class:'tbl'}); box.append(t); return box;
}
function tableView(rows, cols){ const d=el('details'); d.append(el('summary',{text:'Table view'})); d.append(table(rows, cols)); return d; }

// ---------- line chart ----------
function lineChart(series, opts={}){
  const W=opts.w||900, H=opts.h||300, m={t:14,r:16,b:34,l:52};
  const xs=series.flatMap(s=>s.x), ys=series.flatMap(s=>s.y);
  const x0=Math.min(...xs), x1=Math.max(...xs); let y0=Math.min(...ys,0), y1=Math.max(...ys,0);
  if(opts.zeroLine===false){ y0=Math.min(...ys); y1=Math.max(...ys);} const pad=(y1-y0)*0.06||1; y0-=pad; y1+=pad;
  const sx=v=>m.l+(v-x0)/(x1-x0||1)*(W-m.l-m.r), sy=v=>m.t+(y1-v)/(y1-y0||1)*(H-m.t-m.b);
  const svg=sv('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':opts.label||''});
  niceTicks(y0,y1,5).forEach(v=>{ svg.append(sv('line',{x1:m.l,x2:W-m.r,y1:sy(v),y2:sy(v),stroke:'var(--grid)','stroke-width':1})); const tx=sv('text',{x:m.l-8,y:sy(v)+4,'text-anchor':'end','font-size':11,fill:'var(--muted)','font-family':'var(--mono)'}); tx.textContent=opts.yfmt?opts.yfmt(v):v; svg.append(tx); });
  if(y0<0&&y1>0) svg.append(sv('line',{x1:m.l,x2:W-m.r,y1:sy(0),y2:sy(0),stroke:'var(--axis)','stroke-width':1}));
  // x ticks: years
  const d0=new Date(x0), d1=new Date(x1);
  for(let y=d0.getUTCFullYear()+1;y<=d1.getUTCFullYear();y++){ const t=Date.UTC(y,0,1); if(t<x0||t>x1) continue; svg.append(sv('line',{x1:sx(t),x2:sx(t),y1:m.t,y2:H-m.b,stroke:'var(--grid)'})); const tx=sv('text',{x:sx(t),y:H-m.b+16,'text-anchor':'middle','font-size':11,fill:'var(--muted)','font-family':'var(--mono)'}); tx.textContent=y; svg.append(tx); }
  // period shading
  if(opts.periods){ opts.periods.forEach(p=>{ const a=Math.max(x0,p.a), b=Math.min(x1,p.b); if(b<=a) return; const tx=sv('text',{x:sx(a)+4,y:m.t+11,'font-size':10,fill:'var(--muted)','font-family':'var(--mono)'}); tx.textContent=p.name; svg.append(tx); if(p.name!=='DEV') svg.append(sv('line',{x1:sx(a),x2:sx(a),y1:m.t,y2:H-m.b,stroke:'var(--axis)','stroke-dasharray':'0','stroke-width':1})); }); }
  series.forEach((s,i)=>{ let d=''; s.x.forEach((x,k)=>{ d+=(k?'L':'M')+sx(x).toFixed(1)+' '+sy(s.y[k]).toFixed(1); }); const p=sv('path',{d,fill:'none',stroke:s.color||`var(--s${i+1})`,'stroke-width':2,'stroke-linejoin':'round','stroke-linecap':'round',class:'line'}); svg.append(p);
    if(s.area){ const ad=d+`L${sx(s.x[s.x.length-1]).toFixed(1)} ${sy(0)}L${sx(s.x[0]).toFixed(1)} ${sy(0)}Z`; svg.append(sv('path',{d:ad,fill:s.color||`var(--s${i+1})`,'fill-opacity':0.1,stroke:'none'})); }
    const n=s.x.length-1; const c=sv('circle',{cx:sx(s.x[n]),cy:sy(s.y[n]),r:4,fill:s.color||`var(--s${i+1})`,stroke:'var(--surface)','stroke-width':2}); svg.append(c); });
  // hover crosshair
  const cross=sv('line',{x1:0,x2:0,y1:m.t,y2:H-m.b,stroke:'var(--axis)','stroke-width':1,visibility:'hidden'}); svg.append(cross);
  const hit=sv('rect',{x:m.l,y:m.t,width:W-m.l-m.r,height:H-m.t-m.b,fill:'transparent'}); svg.append(hit);
  hit.addEventListener('mousemove',ev=>{ const r=svg.getBoundingClientRect(); const px=(ev.clientX-r.left)/r.width*W; const xv=x0+(px-m.l)/(W-m.l-m.r)*(x1-x0); cross.setAttribute('x1',px); cross.setAttribute('x2',px); cross.setAttribute('visibility','visible');
    let html=new Date(xv).toISOString().slice(0,10); series.forEach(s=>{ let k=s.x.findIndex(x=>x>=xv); if(k<0) k=s.x.length-1; html+=`<br>${s.name}: ${opts.yfmt?opts.yfmt(s.y[k]):s.y[k]}`; }); showTip(ev,html); });
  hit.addEventListener('mouseleave',()=>{ cross.setAttribute('visibility','hidden'); hideTip(); });
  return svg;
}
function legend(items){ const l=el('div',{class:'legend'}); items.forEach((it,i)=>{ const s=el('span'); const b=el('i',{class:it.sq?'sq':''}); b.style.background=it.color||`var(--s${i+1})`; s.append(b, it.name); l.append(s); }); return l; }

// ---------- grouped bar chart ----------
function barChart(cats, series, opts={}){
  const W=opts.w||900, H=opts.h||280, m={t:14,r:12,b:opts.bottom||44,l:56};
  const vals=series.flatMap(s=>s.values.filter(v=>v!=null)); let y0=Math.min(0,...vals), y1=Math.max(0,...vals); const pad=(y1-y0)*0.08||0.1; y0-=pad; y1+=pad;
  const sy=v=>m.t+(y1-v)/(y1-y0||1)*(H-m.t-m.b); const band=(W-m.l-m.r)/cats.length; const bw=Math.min(24,(band-8)/series.length);
  const svg=sv('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':opts.label||''});
  niceTicks(y0,y1,5).forEach(v=>{ svg.append(sv('line',{x1:m.l,x2:W-m.r,y1:sy(v),y2:sy(v),stroke:'var(--grid)'})); const tx=sv('text',{x:m.l-8,y:sy(v)+4,'text-anchor':'end','font-size':11,fill:'var(--muted)','font-family':'var(--mono)'}); tx.textContent=opts.yfmt?opts.yfmt(v):v; svg.append(tx); });
  svg.append(sv('line',{x1:m.l,x2:W-m.r,y1:sy(0),y2:sy(0),stroke:'var(--axis)'}));
  cats.forEach((c,ci)=>{ const cx=m.l+band*ci+band/2; const tx=sv('text',{x:cx,y:H-m.b+16,'text-anchor':'middle','font-size':11,fill:'var(--ink2)'}); tx.textContent=c; svg.append(tx);
    series.forEach((s,si)=>{ const v=s.values[ci]; if(v==null) return; const x=cx-(series.length*bw+ (series.length-1)*2)/2+si*(bw+2); const y=Math.min(sy(v),sy(0)), h=Math.abs(sy(v)-sy(0)); const col=s.color||(opts.signColor?(v<0?'var(--neg)':'var(--pos)'):`var(--s${si+1})`);
      const r=sv('rect',{x,y,width:bw,height:Math.max(h,0.5),fill:col,rx:0}); r.addEventListener('mousemove',ev=>showTip(ev,`${c}<br>${s.name}: ${opts.yfmt?opts.yfmt(v):v}${s.extra?'<br>'+s.extra[ci]:''}`)); r.addEventListener('mouseleave',hideTip); svg.append(r); }); });
  return svg;
}
// ---------- horizontal bars ----------
function hbar(items, opts={}){
  const W=opts.w||900, rowH=22, m={t:6,r:60,b:22,l:opts.left||250}; const H=m.t+m.b+items.length*rowH;
  const vals=items.map(i=>i.v); const x0=Math.min(0,...vals), x1=Math.max(0,...vals); const sx=v=>m.l+(v-x0)/(x1-x0||1)*(W-m.l-m.r);
  const svg=sv('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':opts.label||''});
  niceTicks(x0,x1,5).forEach(v=>{ svg.append(sv('line',{x1:sx(v),x2:sx(v),y1:m.t,y2:H-m.b,stroke:'var(--grid)'})); const tx=sv('text',{x:sx(v),y:H-6,'text-anchor':'middle','font-size':11,fill:'var(--muted)','font-family':'var(--mono)'}); tx.textContent=opts.xfmt?opts.xfmt(v):v; svg.append(tx); });
  items.forEach((it,i)=>{ const y=m.t+i*rowH; const tx=sv('text',{x:m.l-10,y:y+15,'text-anchor':'end','font-size':12,fill:'var(--ink)'}); tx.textContent=it.name; svg.append(tx);
    const r=sv('rect',{x:Math.min(sx(0),sx(it.v)),y:y+4,width:Math.max(Math.abs(sx(it.v)-sx(0)),0.5),height:14,fill:it.color||'var(--s1)'}); r.addEventListener('mousemove',ev=>showTip(ev,`${it.name}<br>${it.tip||fmt(it.v,2)}`)); r.addEventListener('mouseleave',hideTip); svg.append(r);
    const vt=sv('text',{x:sx(Math.max(it.v,0))+6,y:y+15,'font-size':11,fill:'var(--ink2)','font-family':'var(--mono)'}); vt.textContent=it.labelText||(opts.xfmt?opts.xfmt(it.v):fmt(it.v,2)); svg.append(vt); });
  return svg;
}
// ---------- heatmap (diverging around 0) ----------
function heatmap(rows, cols, get, opts={}){
  const cw=opts.cw||96, ch=30, m={t:26,l:opts.left||120}; const W=m.l+cols.length*cw+10, H=m.t+rows.length*ch+6;
  const svg=sv('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':opts.label||''}); svg.style.maxWidth=W+'px';
  const vmax=opts.vmax||0.35;
  cols.forEach((c,j)=>{ const tx=sv('text',{x:m.l+j*cw+cw/2,y:16,'text-anchor':'middle','font-size':11,fill:'var(--ink2)'}); tx.textContent=c; svg.append(tx); });
  rows.forEach((r,i)=>{ const tx=sv('text',{x:m.l-8,y:m.t+i*ch+19,'text-anchor':'end','font-size':11.5,fill:'var(--ink)'}); tx.textContent=r; svg.append(tx);
    cols.forEach((c,j)=>{ const v=get(i,j); if(v==null) return; const a=Math.min(Math.abs(v)/vmax,1); const col=v<0?`color-mix(in oklab, var(--neg) ${Math.round(15+a*85)}%, var(--surface))`:`color-mix(in oklab, var(--pos) ${Math.round(15+a*85)}%, var(--surface))`;
      const rc=sv('rect',{x:m.l+j*cw+1,y:m.t+i*ch+1,width:cw-2,height:ch-2,fill:col,rx:3}); rc.addEventListener('mousemove',ev=>showTip(ev,`${r} / ${c}<br>${fmtR(v)}`)); rc.addEventListener('mouseleave',hideTip); svg.append(rc);
      const t=sv('text',{x:m.l+j*cw+cw/2,y:m.t+i*ch+19,'text-anchor':'middle','font-size':11,'font-family':'var(--mono)',fill:a>0.55?'#fff':'var(--ink)'}); t.textContent=(v>=0?'+':'')+v.toFixed(2); svg.append(t); }); });
  return svg;
}
function fig(title, sub, node, tv){ const f=el('div',{class:'fig'}); f.append(el('p',{class:'t',text:title})); if(sub) f.append(el('p',{class:'s',text:sub})); f.append(node); if(tv) f.append(tv); return f; }

// ================= content =================
const content=document.getElementById('content');
const secs=[];
function section(n, title, ...kids){ const s=el('section',{id:'s'+n}); const h=el('h2'); h.append(el('span',{class:'n',text:String(n).padStart(2,'0')}), title); s.append(h); kids.forEach(k=>k&&s.append(k)); content.append(s); secs.push({n,title}); return s; }
const P=D.period, A=P.A_pingpong.real.ALL, Ai=P.A_pingpong.ideal.ALL, B1=P.B1_pullback.real.ALL, B1i=P.B1_pullback.ideal.ALL, B2=P.B2_immediate.real.ALL, B2i=P.B2_immediate.ideal.ALL;
const S=D.structure_stats, F=D.A_facts;
const PERIODS=[{name:'DEV',a:Date.UTC(2021,8,1),b:Date.UTC(2024,0,1)},{name:'VAL',a:Date.UTC(2024,0,1),b:Date.UTC(2025,3,1)},{name:'OOS',a:Date.UTC(2025,3,1),b:Date.UTC(2026,9,1)}];
const ts=arr=>arr.map(t=>Date.parse(t.replace(' ','T')+'Z'));

// tiles
const tiles=document.getElementById('tiles');
[['Trades (A + B1 + B2, real)', (A.n+B1.n+B2.n).toLocaleString(), '5 years, one position at a time per playbook'],
 ['Expectancy, real', fmtR(A.expectancy)+' / '+fmtR(B1.expectancy)+' / '+fmtR(B2.expectancy), 'A / B1 / B2 per trade'],
 ['Expectancy, ideal', fmtR(Ai.expectancy)+' / '+fmtR(B1i.expectancy)+' / '+fmtR(B2i.expectancy), 'zero costs, signal-close fill'],
 ['Profit factor, real', fmt(A.pf,2)+' / '+fmt(B1.pf,2)+' / '+fmt(B2.pf,2), 'ideal: '+fmt(Ai.pf,2)+' / '+fmt(B1i.pf,2)+' / '+fmt(B2i.pf,2)],
 ['Median hold', A.median_hold_h.toFixed(1)+' h', pct(F.hold_le_4h_share)+' of trades closed within 4 h'],
 ['Max drawdown at 1% risk', A.max_dd_pct_1pct.toFixed(0)+'%', 'ping-pong, real; source rejects > 20%']].forEach(([l,v,d])=>{ const t=el('div',{class:'tile'}); t.append(el('div',{class:'l',text:l}), el('div',{class:'v',text:v}), el('div',{class:'d',text:d})); tiles.append(t); });

const perCols=[{key:'period'},{key:'n'},{key:'win_rate',label:'win rate',fmt:pct},{key:'avg_win',label:'avg win R'},{key:'avg_loss',label:'avg loss R'},{key:'pf',label:'PF',d:2},{key:'expectancy',label:'expectancy R',sign:true},{key:'total_r',label:'total R',d:1},{key:'max_dd_r',label:'max DD R',d:1},{key:'max_loss_streak',label:'max losses in a row'},{key:'median_hold_h',label:'median hold h',d:2},{key:'avg_rr',label:'planned R:R',d:2},{key:'mfe_r',label:'MFE R',d:2},{key:'mae_r',label:'MAE R',d:2},{key:'ci_lo',label:'CI 2.5%'},{key:'ci_hi',label:'CI 97.5%'}];
const perRows=(pb,cost)=>['DEV','VAL','OOS','ALL'].map(p=>P[pb][cost][p]);

// 1
section(1,'Strategy explanation',
  el('p',{html:'The source is Patrick Nill’s <em>Counter-Trend Swing Trading</em>, built on the PBD model of Market Profile shapes. A <strong>P structure</strong> is a large upward impulse followed by a consolidation that forms above the impulse origin; a <strong>B structure</strong> is the mirror after a downward impulse. The impulse itself is never traded. The 15-minute chart frames impulse and range; the weekly Value Area High and Low are the reference zones; footprint and order flow time the entry.'}),
  el('p',{html:'<strong>Playbook 1, ping-pong:</strong> buy near the range low, sell near the range high, repeat until the range breaks. <strong>Playbook 2, breakout / pullback:</strong> wait for a decisive break, preferably a pullback to the broken edge, enter with the resumed move. Targets sit near the origin of the impulse; the stop is fixed before entry; risk is at most 1% of equity.'}),
  el('p',{class:'note',html:'Published expectations for the method: 50–60% win rate, holds of 4 hours to 3 days, losing streaks of 10–20 called normal, drawdowns above 20% rejected, no trading during high-impact news.'}));

// 2
section(2,'Exact objective rules',
  el('p',{html:'Every discretionary word was replaced by a measurable rule and fixed <em>before</em> the first run. The full machine-readable specification is <code>spec/pbd_xauusd_rules.json</code>.'}),
  (()=>{ const k=el('div',{class:'kv'}); [['Impulse','8-bar (2 h) net move ≥ 3.5 × pre-window ATR14, efficiency ratio ≥ 0.6, no data gap; origin = swing extreme within 32 bars if the path never retraced > 50%'],
   ['Range','last 8 bars from the extreme onward: width ≤ 0.6 × impulse, ≥ 0.5 × pre-impulse ATR, drift ≤ 0.5 × width, box inside the terminal 61.8% of the impulse; high/low frozen; expires after 288 bars'],
   ['Ping-pong','low enters the 20% zone and the bar closes back inside below the midpoint (rejection close = Version-A confirmation proxy); stop = boundary ∓ 0.5 ATR; target = 0.9 × width; re-arm after a close 30% of width away'],
   ['Breakout','close beyond a boundary by ≥ 0.25 ATR; pullback within 16 bars to boundary ± 0.25 ATR closing on the breakout side; failed if a close returns > 0.25 ATR inside; stop = beyond min(pullback extreme, boundary) by 0.5 ATR; target = impulse origin (counter) or 1 × width (continuation)'],
   ['Weekly VA','Sunday 21:00 UTC week, 0.025%-of-price bins, uniform volume distribution, 70% area expanded two bins at a time from the POC; previous completed week used for the whole current week; Dukascopy volume primary, tick volume and TPO as sensitivity'],
   ['Execution','fill at the open of the M1 bar after the signal bar (+1 min), M1 path for stops and targets, stop first when both touch, gap-through at the open, 72 h time stop, one position at a time'],
   ['Split','DEV Sep 2021–Dec 2023 · VAL Jan 2024–Mar 2025 · OOS Apr 2025–Sep 2026 (fixed before any result)']].forEach(([a,b])=>{ k.append(el('div',{text:a}), el('div',{text:b})); }); return k; })());

// 3
section(3,'Data used',
  (()=>{ const k=el('div',{class:'kv'}); [['M1 bars',D.data.m1_bars.toLocaleString()+' Dukascopy bid bars, UTC, '+D.data.start.slice(0,10)+' to '+D.data.end.slice(0,10)],
   ['M15 bars',D.data.m15_bars.toLocaleString()+' in '+D.data.months+' months (July 2024 missing: Dukascopy returned HTTP 429 on every attempt)'],
   ['Volume','Dukascopy traded volume = REAL volume from one ECN venue. Not COMEX futures volume, not footprint.'],
   ['Tick volume','XM MT5 tick volume, M15, from July 2022 (value-area sensitivity only)'],
   ['Spread','XM GOLD per-bar spread, server time converted from Europe/Athens; '+(D.data.spread_filled_share*100).toFixed(1)+'% of bars filled with the monthly median (before Jul 2022: 0.25 USD)'],
   ['Sessions','DST-aware from the London, New York and Tokyo clocks; overlap = both London and New York open'],
   ['News','proxy slots (08:30 and 10:00 ET weekdays, FOMC 14:00 ET) plus an ex-post shock-bar label; no calendar file offline'],
   ['Version B','not available: no bid/ask footprint or COMEX order-flow data exists in the dataset; tick volume is not treated as footprint data']].forEach(([a,b])=>{ k.append(el('div',{text:a}), el('div',{text:b})); }); return k; })());

// 4
section(4,'Gold market assumptions',
  el('ul',{html:`<li>XM GOLD: 100 oz per lot, swap long −0.8684 / short +0.1979 USD per oz per night, Wednesday ×3; slippage 0.10 USD per oz on market fills; commission 0 (ECN 0.07 USD/oz tested).</li>
  <li>Median M15 ATR14 rose from ${F.atr_median_by_year['2021']} USD (2021) to ${F.atr_median_by_year['2026']} USD (2026) while the spread stayed at 0.25–0.40 USD, so the spread as a share of the median ping-pong stop fell from ${(F.spread_r_median_by_year['2021']*100).toFixed(0)}% to ${(F.spread_r_median_by_year['2026']*100).toFixed(0)}%. Year-by-year comparisons must be read against this.</li>
  <li>Weekend gaps are in the data: the worst baseline trade lost ${F.worst_r.toFixed(1)}R (long into a Sunday open); ${F.n_below_minus2} trades lost more than 2R, together ${F.sum_below_minus2.toFixed(0)}R.</li>
  <li>Median risk per trade grew from ${F.risk_usd_median_by_year['2021']} USD/oz (2021) to ${F.risk_usd_median_by_year['2026']} USD/oz (2026); all results are in R so the regime change does not distort the sums.</li>`}));

// 5 baseline
const eqA=D.equity.A_pingpong, eqB1=D.equity.B1_pullback, eqB2=D.equity.B2_immediate;
function eqFig(pb){ const e=D.equity[pb], ei=D.equity_ideal[pb]; const svg=lineChart([{name:'ideal',x:ts(ei.t),y:ei.eq,color:'var(--s1)'},{name:'real',x:ts(e.t),y:e.eq,color:'var(--s2)'}],{h:260,periods:PERIODS,yfmt:v=>v.toFixed(0)+'R',label:'Equity in R, '+PBN[pb]}); const f=fig(PBN[pb]+': cumulative R', 'ideal (blue) vs realistic execution (orange); vertical rules mark the VAL and OOS starts', svg); f.append(legend([{name:'ideal',color:'var(--s1)'},{name:'real',color:'var(--s2)'}])); return f; }
section(5,'Baseline results',
  el('p',{html:`${S.impulses_detected.toLocaleString()} impulses detected, ${S.ranges_confirmed.toLocaleString()} ranges confirmed (about ${S.ranges_per_month} a month), ${S.abandoned_retrace} abandoned on a > 61.8% retrace. Median impulse ${S.imp_size_atr_q10_50_90[1]} pre-impulse ATR over ${S.imp_bars_q10_50_90[1]} bars; median range width ${S.width_atr_q10_50_90[1]} ATR; median range life ${S.range_life_bars_q10_50_90[1]} bars (about 6 h). ${S.failed_bo_per_range} failed breakouts per range. Signals proposed: ${D.signals.pingpong.toLocaleString()} ping-pong, ${D.signals.breakout_pullback.toLocaleString()} pullback, ${D.signals.breakout_immediate.toLocaleString()} immediate.`}),
  el('div',{class:'callout',html:`<strong>Structural finding first.</strong> Median hold ${A.median_hold_h.toFixed(1)} h; ${pct(F.hold_le_4h_share)} of trades closed within 4 h and ${pct(F.hold_ge_24h_share)} held 24 h or more, against the source’s 4 h to 3 days. The objective 15-minute impulse-and-box rules find intraday structures, not multi-day swings. Longer confirmation windows were tested (section 10) and are worse.`}),
  eqFig('A_pingpong'), eqFig('B1_pullback'), eqFig('B2_immediate'),
  el('h3',{text:'Combined A + B1, one position across both playbooks, realistic costs'}),
  table(D.combined,[{key:'period'},{key:'n'},{key:'win_rate',label:'win rate',fmt:pct},{key:'expectancy',label:'expectancy R',sign:true},{key:'pf',label:'PF',d:2},{key:'total_r',label:'total R',d:1},{key:'max_dd_r',label:'max DD R',d:1},{key:'max_loss_streak',label:'max losses in a row'},{key:'ci_lo',label:'CI 2.5%'},{key:'ci_hi',label:'CI 97.5%'}]));

// 6 ping-pong
function sessFig(pb){ const rows=D.session[pb]; const cats=rows.map(r=>r.group); return fig('Expectancy by session, '+PBN[pb], 'realistic costs, all periods; bars show R per trade, hover for trade counts', barChart(cats,[{name:'expectancy',values:rows.map(r=>r.expectancy),extra:rows.map(r=>`n ${r.n}, win ${pct(r.win_rate)}, PF ${fmt(r.pf,2)}`)}],{h:220,signColor:true,yfmt:v=>v.toFixed(2)}), tableView(rows,[{key:'group',label:'session'},{key:'n'},{key:'win_rate',label:'win rate',fmt:pct},{key:'expectancy',sign:true},{key:'pf',d:2},{key:'total_r',d:1},{key:'max_dd_r',d:1},{key:'median_hold_h',d:2}])); }
function monthlyFig(pb){ const rows=D.monthly[pb]; return fig('Monthly total R, '+PBN[pb],'realistic costs; blue = positive month, red = negative', barChart(rows.map(r=>r.month.slice(2)),[{name:'total R',values:rows.map(r=>r.total_r),extra:rows.map(r=>`n ${r.n}, win ${pct(r.win_rate)}`)}],{h:220,signColor:true,yfmt:v=>v.toFixed(0),bottom:34}), tableView(rows,[{key:'month'},{key:'n'},{key:'total_r',d:2,sign:true},{key:'expectancy',sign:true},{key:'win_rate',fmt:pct}])); }
const ssCols=[{key:'group',label:'structure_side'},{key:'n'},{key:'win_rate',fmt:pct},{key:'expectancy',sign:true},{key:'pf',d:2},{key:'total_r',d:1},{key:'max_dd_r',d:1}];
section(6,'Ping-pong results (playbook A)',
  el('h3',{text:'Realistic execution'}), table(perRows('A_pingpong','real'),perCols),
  el('h3',{text:'Ideal execution'}), table(perRows('A_pingpong','ideal'),perCols),
  el('p',{html:`Median planned reward-to-risk ${F.rr_median.toFixed(2)}, median stop ${F.risk_atr_median.toFixed(2)} ATR, win rate ${pct(A.win_rate)} against the 50–60% the source expects. Mean MFE ${A.mfe_r.toFixed(2)}R and MAE ${A.mae_r.toFixed(2)}R: the typical trade travels as far against as for.`}),
  sessFig('A_pingpong'), monthlyFig('A_pingpong'),
  el('h3',{text:'P vs B structure and side'}), table(D.stype_side.A_pingpong, ssCols),
  el('h3',{text:'By year'}), table(D.year.A_pingpong,[{key:'group',label:'year'},{key:'n'},{key:'win_rate',fmt:pct},{key:'expectancy',sign:true},{key:'pf',d:2},{key:'total_r',d:1},{key:'max_dd_r',d:1}]));

// 7 breakout
section(7,'Breakout / pullback results (playbooks B1 and B2)',
  el('h3',{text:'B1 pullback, realistic'}), table(perRows('B1_pullback','real'),perCols),
  el('h3',{text:'B1 pullback, ideal'}), table(perRows('B1_pullback','ideal'),perCols),
  el('h3',{text:'B2 breakout at the close, realistic'}), table(perRows('B2_immediate','real'),perCols),
  el('h3',{text:'B2 breakout at the close, ideal'}), table(perRows('B2_immediate','ideal'),perCols),
  el('p',{html:`The pullback playbook has the lowest win rate (${pct(B1.win_rate)}) and the highest planned R:R (${B1.avg_rr.toFixed(1)}) because counter-impulse breaks target the impulse origin. Waiting for the pullback did not beat entering at the breakout close (B2 ${fmtR(B2.expectancy)} vs B1 ${fmtR(B1.expectancy)} real). Breakout losses are false breakouts: price closes back inside the range within 8 bars.`}),
  sessFig('B1_pullback'), sessFig('B2_immediate'), monthlyFig('B1_pullback'),
  el('h3',{text:'P vs B structure and side, B1'}), table(D.stype_side.B1_pullback, ssCols));

// 8 taxonomy
function taxFig(pb){ const rows=D.taxonomy[pb].filter(r=>r.losses>0).sort((a,b)=>a.total_loss-b.total_loss); return fig('Loss taxonomy, '+PBN[pb],'primary category per losing trade; bar = share of total loss (%)', hbar(rows.map(r=>({name:r.category.replace(/_/g,' '),v:r.share_of_total_loss,tip:`${r.losses} losses of ${r.trades_flagged} flagged (${r.loss_pct.toFixed(0)}% lose)<br>total ${r.total_loss.toFixed(1)}R, avg ${r.avg_loss.toFixed(2)}R, max ${r.max_loss.toFixed(2)}R<br>longest run ${r.max_consec}`,labelText:r.share_of_total_loss.toFixed(1)+'%'})),{xfmt:v=>v+'%',left:240}), tableView(D.taxonomy[pb],[{key:'category',text:true},{key:'trades_flagged'},{key:'losses'},{key:'loss_pct',d:1},{key:'avg_loss',d:2},{key:'max_loss',d:2},{key:'total_loss',d:1},{key:'share_of_total_loss',d:1},{key:'max_consec'},{key:'dd_window_contribution',d:1}])); }
section(8,'Loss taxonomy',
  el('p',{html:'Every losing trade carries all matching labels; the primary category is the first match in a fixed priority order (news/shock, false breakout, trend continuation, …). Each label is a measurable condition on the recorded trade; the definitions are listed below the charts. “Trades flagged” counts winners too, so the loss % shows whether a condition actually discriminates.'}),
  taxFig('A_pingpong'), taxFig('B1_pullback'), taxFig('B2_immediate'),
  el('div',{class:'callout',html:'<strong>Reading.</strong> Ping-pong: the largest bucket is <em>trend continuation against the counter-trend side</em> (short in a P or long in a B, stopped as the impulse resumed), then news/shock bars and poor VAH/VAL location. Both breakout playbooks: <em>false breakout</em>. “Stop too tight” (a stop twice as far would have reached the target) is a small bucket, so wider stops help through the cost ratio, not by avoiding wick-outs. “Bad footprint confirmation” cannot be evaluated without footprint data; the volume row is a labelled proxy.'}),
  (()=>{ const d=el('details'); d.append(el('summary',{text:'Label definitions'})); const k=el('div',{class:'kv'}); Object.entries(D.label_rules.loss_labels).forEach(([a,b])=>k.append(el('div',{text:a}),el('div',{text:b}))); d.append(k); return d; })());

// 9 filters
function filtTable(pb){ const rows=D.filters[pb].filter(r=>r.period==='ALL'); return table(rows,[{key:'filter',text:true},{key:'description',text:true},{key:'n_before'},{key:'exp_before',label:'exp before',sign:true},{key:'n_after'},{key:'exp_after',label:'exp after',sign:true},{key:'removed'},{key:'removed_mean_r',label:'removed mean R',sign:true},{key:'survives',text:true}]); }
function filtPeriodFig(pb){ const names=[...new Set(D.filters[pb].map(r=>r.filter))]; const per=['DEV','VAL','OOS']; return fig('No-trade filters: change in expectancy after the filter, by period, '+PBN[pb],'positive = the filter improved expectancy in that period; a filter is retained only if expectancy and PF improve in DEV, VAL and OOS', heatmap(names.map(n=>n.replace(/_/g,' ')),per,(i,j)=>{ const r=D.filters[pb].find(x=>x.filter===names[i]&&x.period===per[j]); return r&&r.n_after&&r.n_after<r.n_before? r.exp_after-r.exp_before : null; },{vmax:0.1,cw:80,left:210,label:'filter heatmap'})); }
section(9,'No-trade conditions',
  el('p',{html:'Each filter removes the flagged signals before entry (pre-entry information only). “survives” = expectancy <em>and</em> profit factor both improve in DEV, in VAL and in OOS; the rule was fixed before the runs. Every “after” column is still negative.'}),
  el('h3',{text:'Ping-pong (A)'}), filtTable('A_pingpong'), filtPeriodFig('A_pingpong'),
  el('h3',{text:'Breakout + pullback (B1)'}), filtTable('B1_pullback'),
  el('h3',{text:'Breakout at close (B2)'}), filtTable('B2_immediate'),
  el('div',{class:'callout',html:`<strong>Supported as NO-TRADE:</strong> impulse larger than 15 pre-impulse ATR (removed trades average −0.40 to −0.54R, survives all periods in every playbook); spread above 15% of the stop (A and B2); off-hours or volume below half the 20-bar average (B1); Asia session for breakout pullbacks (win rate ${pct(D.session.B1_pullback.find(r=>r.group==='asia').win_rate)}); New York afternoon for ping-pong (${fmtR(D.session.A_pingpong.find(r=>r.group==='newyork').expectancy)}).<br><strong>Not supported:</strong> VAH/VAL proximity in any form, the news-slot proxy, the volatility percentile, range width, mid-range entry, touch count.`}));

// 10 adaptations
function expFig(name, pb, title, sub, xkey='variant'){ const rows=D.exp[name].filter(r=>r.playbook===pb&&r.period!=='ALL'); const vars=[...new Set(rows.map(r=>r[xkey]))]; const per=['DEV','VAL','OOS']; const series=per.map((p,i)=>({name:p,values:vars.map(v=>{const r=rows.find(x=>x[xkey]===v&&x.period===p); return r?r.expectancy:null;}),extra:vars.map(v=>{const r=rows.find(x=>x[xkey]===v&&x.period===p); return r?`n ${r.n}, win ${pct(r.win_rate)}, PF ${fmt(r.pf,2)}`:'';})})); const f=fig(title, sub, barChart(vars.map(v=>String(v).replace(/^[a-z_]+=/,'')),series,{h:230,yfmt:v=>v.toFixed(2),bottom:40}), tableView(rows,[{key:'variant',text:true},{key:'period'},{key:'n'},{key:'win_rate',fmt:pct},{key:'expectancy',sign:true},{key:'pf',d:2},{key:'total_r',d:1},{key:'max_dd_r',d:1},{key:'median_hold_h',d:2}])); f.insertBefore(legend(per.map((p,i)=>({name:p,color:`var(--s${i+1})`}))), f.lastChild); return f; }
section(10,'Gold-specific adaptations, one variable at a time',
  el('p',{html:'Every experiment changes exactly one rule from the baseline. Bars are expectancy per trade under realistic costs for DEV, VAL and OOS. Nothing here was selected on OOS.'}),
  el('h3',{text:'Impulse definition (Part 3A): four definitions, none positive anywhere'}), expFig('impulse_definition','A_pingpong','Impulse definition, ping-pong','atr = 3.5 × ATR; pct = 98th percentile of 30-day moves; rangeexp = 3 × median window range; consec = 5 closes + 2 ATR'), expFig('impulse_definition','B1_pullback','Impulse definition, breakout + pullback',''),
  el('h3',{text:'Impulse threshold and window'}), expFig('impulse_k','A_pingpong','Impulse threshold k (× ATR), ping-pong','trade count falls with k; sign never changes'), expFig('impulse_N','A_pingpong','Impulse window N (bars), ping-pong',''),
  el('h3',{text:'Experiment 1: stop methodology'}), expFig('stop_pingpong','A_pingpong','Ping-pong stop distance (× ATR beyond the boundary)','the 0.25-ATR stop is destroyed by slippage and gaps on stops of a few cents (DEV −1.9R per trade, off the scale); win rate reaches 56–60% at 2 ATR while expectancy stays negative'), expFig('stop_breakout','B1_pullback','Breakout + pullback stop distance (× ATR)','monotone: wider stops lose less, never gain'),
  el('h3',{text:'Experiment 2: range definition'}), expFig('range_min_bars','A_pingpong','Confirmation window (bars), ping-pong','4 bars is less bad in every period; 12–24 bars, closer to the source’s multi-hour boxes, is worse everywhere'), expFig('range_min_bars','B1_pullback','Confirmation window (bars), breakout + pullback','4 bars is positive in OOS only (+0.12R) with DEV worse than baseline: not robust'),
  el('h3',{text:'Experiment 3: session filter'}), expFig('session_filter','A_pingpong','Session variants A–G, ping-pong','E = London/New York overlap: VAL +0.03R and OOS +0.07R on 65 and 91 trades, DEV −0.22R'), expFig('session_filter','B1_pullback','Session variants A–G, breakout + pullback',''),
  el('h3',{text:'Experiment 4: volatility filter'}), expFig('volatility_filter','A_pingpong','ATR-percentile bands, ping-pong','no band improves all three periods'),
  el('h3',{text:'Experiment 5: breakout confirmation'}), expFig('breakout_confirmation','B2_immediate','Breakout confirmation, entry at the close (B2)','both = bar range ≥ 1.5 ATR AND volume ≥ 1.5×: win rate 39–52%, VAL +0.09R, OOS +0.06R, DEV still −0.20R'), expFig('breakout_confirmation','B1_pullback','Breakout confirmation, pullback entry (B1)','no variant positive anywhere'), expFig('breakout_penetration','B2_immediate','Breakout penetration (× ATR), B2','deeper penetration raises the win rate to 42–50%; expectancy −0.15 / −0.08 / −0.02'),
  el('h3',{text:'VAH/VAL proximity and volume source'}), expFig('va_proximity','A_pingpong','Weekly value-area alignment, ping-pong','requiring the boundary within 1 or 2 ATR of the previous week’s VAH/VAL is worse; the developing current-week VA is the least bad and still negative'), expFig('va_proximity','B1_pullback','Weekly value-area alignment, breakout + pullback',''),
  el('p',{class:'note',html:`Level differences between volume sources are small: Dukascopy vs tick-volume VAH ${D.exp.va_level_differences[0].median_abs_diff_usd.toFixed(2)} USD median (${D.exp.va_level_differences[0].median_abs_diff_atr.toFixed(2)} ATR), vs TPO ${D.exp.va_level_differences[2].median_abs_diff_usd.toFixed(2)} USD. Applying the same 1-ATR alignment filter with each source gives the same negative sign (table view below).`}),
  tableView(D.exp.va_source_sensitivity.filter(r=>r.period!=='ALL'),[{key:'playbook'},{key:'variant',text:true},{key:'period'},{key:'n'},{key:'expectancy',sign:true},{key:'pf',d:2}]),
  el('h3',{text:'News proxy filter'}), expFig('news_filter','A_pingpong','Skipping the 08:30 / 10:00 ET and FOMC slots, ping-pong','the proxy filter does not improve any period'));

// 11 robustness
function gridFig(key, title, sub, rk, ck){ const rows=D.grids[key]; const rv=[...new Set(rows.map(r=>r[rk]))], cv=[...new Set(rows.map(r=>r[ck]))]; const per=['DEV','VAL','OOS']; const box=el('div',{class:'grid2'}); per.forEach(p=>{ const f=fig(title+' · '+p, sub, heatmap(rv.map(v=>rk+' '+v), cv.map(v=>ck.replace(/^(rng_|pp_|bo_|pb_|imp_)/,'')+' '+v), (i,j)=>{ const r=rows.find(x=>x[rk]===rv[i]&&x[ck]===cv[j]&&x.period===p); return r?r.expectancy:null; },{vmax:0.35,cw:78,left:120})); box.append(f); }); return box; }
function stageFig(pb){ const rows=D.stages.filter(r=>r.playbook===pb&&r.cost==='real'&&r.period!=='ALL'); const labels=[...new Set(rows.map(r=>r.label))]; const per=['DEV','VAL','OOS']; const f=fig('Staged combination, '+PBN[pb]+' (real)','each stage adds one change; increments measured on DEV and VAL, OOS read once at the end', barChart(labels.map((l,i)=>'stage '+i),per.map((p,i)=>({name:p,values:labels.map(l=>{const r=rows.find(x=>x.label===l&&x.period===p); return r?r.expectancy:null;}),extra:labels.map(l=>{const r=rows.find(x=>x.label===l&&x.period===p); return r?`${l}<br>n ${r.n}, win ${pct(r.win_rate)}, PF ${fmt(r.pf,2)}, CI ${fmt(r.ci_lo)}..${fmt(r.ci_hi)}`:'';})})),{h:230,yfmt:v=>v.toFixed(2)}), tableView(D.stages.filter(r=>r.playbook===pb&&r.period!=='ALL'),[{key:'stage'},{key:'label',text:true},{key:'cost'},{key:'period'},{key:'n'},{key:'win_rate',fmt:pct},{key:'expectancy',sign:true},{key:'pf',d:2},{key:'total_r',d:1},{key:'max_dd_r',d:1},{key:'ci_lo'},{key:'ci_hi'},{key:'max_loss_streak'}])); f.insertBefore(legend(per.map((p,i)=>({name:p,color:`var(--s${i+1})`}))), f.lastChild); const ol=el('ol',{style:'font-size:13px;color:var(--ink2);margin:6px 0 0 18px;padding:0'}); labels.forEach((l,i)=>ol.append(el('li',{text:`stage ${i}: ${l}`}))); f.append(ol); return f; }
function yearlyFig(pb){ const rows=D.stages_yearly.filter(r=>r.playbook===pb); const stages=[...new Set(rows.map(r=>r.stage))], years=[...new Set(rows.map(r=>r.year))].sort(); return fig('Year-by-year expectancy of each stage, '+PBN[pb],'the positive sign of the best stage comes from 2025', heatmap(stages.map(s=>'stage '+s), years.map(String), (i,j)=>{ const r=rows.find(x=>x.stage===stages[i]&&x.year===years[j]); return r?r.expectancy:null; },{vmax:0.35,cw:78,left:80})); }
section(11,'Robustness tests',
  el('p',{html:'Two-dimensional parameter grids on each period, then a pre-specified staged combination of the changes that improved both expectancy and profit factor in DEV and VAL. No grid cell is positive in DEV. The least-bad region is broad and monotone (wider stops, wider zones, shorter windows), the opposite of a knife-edge, but it is a region of smaller losses.'}),
  gridFig('impk_x_minbars_A','Ping-pong: impulse k × confirmation bars','expectancy R per trade, real','imp_k','rng_min_bars'),
  gridFig('stop_x_zone_A','Ping-pong: stop × entry zone','','pp_stop_atr','zone'),
  gridFig('impk_x_minbars_B1','Breakout + pullback: impulse k × confirmation bars','','imp_k','rng_min_bars'),
  gridFig('stop_x_depth_B1','Breakout + pullback: stop × pullback depth','','bo_stop_atr','pb_depth_atr'),
  el('h3',{text:'Staged combinations'}), stageFig('A_pingpong'), yearlyFig('A_pingpong'), stageFig('B1_pullback'), yearlyFig('B1_pullback'), stageFig('B2_immediate'), yearlyFig('B2_immediate'),
  el('div',{class:'callout',html:'The best stage (B2: stop 1.5 ATR + confirmed breakout + 0.5 ATR penetration) is −0.07R in DEV, +0.06R in VAL and +0.08R in OOS. Every confidence interval contains zero, and the year table shows the sign comes from 2025 (+0.26R) with 2021, 2023, 2024 and 2026 negative. That is a regime result, not a robust edge.'}));

// 12 walk-forward
section(12,'Walk-forward results',
  el('p',{html:'For each test year the candidate with the best expectancy on all earlier years (at least 100 trades) is chosen and applied to that year. The chosen variant is always the wider stop; it loses less than the baseline in every test year and is positive in one (ping-pong 2024, +0.02R).'}),
  table(D.walk_forward,[{key:'playbook'},{key:'test_year'},{key:'chosen'},{key:'train_expectancy',sign:true},{key:'train_n'},{key:'test_n'},{key:'test_expectancy',sign:true},{key:'test_pf',d:2},{key:'baseline_test_n'},{key:'baseline_test_expectancy',sign:true}]));

// 13 OOS
section(13,'Out-of-sample results (Apr 2025 to Sep 2026, never used for selection)',
  table(['A_pingpong','B1_pullback','B2_immediate'].flatMap(pb=>['ideal','real'].map(c=>({playbook:PBN[pb],cost:c,...P[pb][c].OOS}))),[{key:'playbook'},{key:'cost'},{key:'n'},{key:'win_rate',fmt:pct},{key:'expectancy',sign:true},{key:'pf',d:2},{key:'total_r',d:1},{key:'max_dd_r',d:1},{key:'max_loss_streak'},{key:'ci_lo'},{key:'ci_hi'}]),
  el('p',{html:'Baseline OOS: negative under real costs for all three playbooks; B2 ideal is closest to flat (−0.011R). The staged adaptations reach +0.06 to +0.08R in OOS for B2 and −0.09 to −0.14R for A and B1 (section 11).'}));

// 14 costs
function costFig(pb){ const rows=D.costs[pb].filter(r=>r.period==='ALL'); return fig('Execution-model sensitivity, '+PBN[pb],'expectancy R per trade, all periods', barChart(rows.map(r=>r.variant.replace('real_','real ').replace('_',' ')),[{name:'expectancy',values:rows.map(r=>r.expectancy),extra:rows.map(r=>`n ${r.n}, PF ${fmt(r.pf,2)}, spread ${fmt(r.spread_r,3)}R`)}],{h:230,signColor:true,yfmt:v=>v.toFixed(2),bottom:44}), tableView(rows,[{key:'variant',text:true},{key:'n'},{key:'expectancy',sign:true},{key:'pf',d:2},{key:'total_r',d:1},{key:'spread_r',label:'spread as R'}])); }
section(14,'Transaction-cost sensitivity',
  el('p',{html:'ideal = zero costs at the signal close; spread only; real without slippage; real (spread + 0.10 USD slippage + 1-min delay + swap); slippage 0.20; ECN commission 0.07 USD/oz; 5-minute delay; spread halved, ×1.5 and doubled.'}),
  costFig('A_pingpong'), costFig('B1_pullback'),
  el('p',{html:'The spread alone costs about 0.08–0.09R per trade, slippage 0.05R, swap 0.02R, a 5-minute delay another 0.05R for ping-pong. Doubling the spread doubles the damage; halving it does not restore the sign.'}));

// 15 drawdown
const ec=D.equity_comb;
section(15,'Maximum drawdown',
  fig('Drawdown, combined A + B1, realistic (R units)','from the running peak of cumulative R', lineChart([{name:'drawdown R',x:ts(ec.t),y:ec.dd,color:'var(--neg)',area:true}],{h:220,periods:PERIODS,yfmt:v=>v.toFixed(0)+'R'})),
  fig('Equity at 1% risk per trade, compounding from 10,000 USD, ping-pong realistic','the source rejects any strategy with a drawdown above 20%', lineChart([{name:'equity USD',x:ts(eqA.t),y:eqA.eq_usd,color:'var(--s2)'}],{h:220,periods:PERIODS,yfmt:v=>v.toLocaleString(),zeroLine:false})),
  el('p',{html:`Fixed 1R per trade: A ${A.max_dd_r.toFixed(0)}R, B1 ${B1.max_dd_r.toFixed(0)}R, B2 ${B2.max_dd_r.toFixed(0)}R, combined ${D.combined.find(r=>r.period==='ALL').max_dd_r.toFixed(0)}R. Compounding at 1% risk from 10,000 USD the equity ends at ${(A.end_equity_1pct*100).toFixed(0)}% (A), ${(B1.end_equity_1pct*100).toFixed(0)}% (B1), ${(B2.end_equity_1pct*100).toFixed(0)}% (B2) of the start with maximum drawdowns of ${A.max_dd_pct_1pct.toFixed(0)}%, ${B1.max_dd_pct_1pct.toFixed(0)}% and ${B2.max_dd_pct_1pct.toFixed(0)}%. Even ideal execution breaches the 20% limit (${Ai.max_dd_pct_1pct.toFixed(0)}%, ${B1i.max_dd_pct_1pct.toFixed(0)}%, ${B2i.max_dd_pct_1pct.toFixed(0)}%).`}));

// 16 streaks
section(16,'Losing streak analysis',
  el('p',{html:`Maximum consecutive losses: A ${A.max_loss_streak}, B1 ${B1.max_loss_streak}, B2 ${B2.max_loss_streak}. The source calls 10–20 normal, so the streaks themselves are not the diagnostic. The diagnostic is the ratio: at a ${pct(A.win_rate)} win rate a planned ${F.rr_median.toFixed(1)} R:R needs about 42% to break even before costs. Wider stops raise the win rate to 50–60% and cut streaks to 6–9 but lower the average win, and the product stays negative.`}));

// 17 / 18 examples
const exCols=[{key:'entry_time',text:true},{key:'session'},{key:'stype'},{key:'side'},{key:'entry_type',text:true},{key:'entry',d:2},{key:'stop',d:2},{key:'target',d:2},{key:'exit',d:2},{key:'rr_actual',label:'planned R:R',d:2},{key:'r_net',label:'result R',d:2,sign:true},{key:'exit_reason'},{key:'hold_h',d:1},{key:'mfe_r',d:2},{key:'mae_r',d:2},{key:'imp_size_atr',d:1},{key:'width_atr',d:1},{key:'loss_category',text:true}];
section(17,'Failure examples',
  el('h3',{text:'Ping-pong, worst losses'}), table(D.examples_A.worst_losses,exCols),
  el('h3',{text:'Ping-pong, randomly drawn losses'}), table(D.examples_A.typical_losses,exCols),
  el('h3',{text:'Breakout + pullback, worst losses'}), table(D.examples_B1.worst_losses,exCols),
  el('p',{class:'note',html:'The worst losses are longs or shorts held into a Sunday open (gap through the stop) and stops of a few cents in 2021–2022 where slippage alone exceeded the planned risk.'}));
section(18,'Successful examples',
  el('h3',{text:'Ping-pong, best trades'}), table(D.examples_A.best_wins,exCols),
  el('h3',{text:'Ping-pong, randomly drawn wins'}), table(D.examples_A.typical_wins,exCols),
  el('h3',{text:'Breakout + pullback, best trades'}), table(D.examples_B1.best_wins,exCols),
  el('p',{class:'note',html:'The best trades are counter-impulse breakouts that reached the impulse origin (3–9R) and ping-pong entries just after a failed breakout. They are rare: the 99th percentile trade is about +3R.'}));

// 19
section(19,'Limitations',
  el('ul',{html:`<li>The discretionary parts (“well-defined range”, “decisive break”, “confirmation”) were replaced by one objective rule set. The sensitivity grids cover the neighbourhood of the chosen rules, not every reading of the method.</li>
  <li>No footprint or COMEX order-flow data, so Version B is untested. The order-flow confirmation step could be where the method’s edge lives; it cannot be tested here, and the Dukascopy volume proxy carried no information.</li>
  <li>News: proxy slots, not an actual calendar. July 2024 missing. Spread before July 2022 is a constant estimate.</li>
  <li>M1 bar-path execution with a stop-first rule; ticks would place some fills differently.</li>
  <li>The holding-time mismatch (hours vs days) means the test covers the 15-minute structures the rules find. Longer confirmation windows were worse; a daily-scale version of the framework (H1/H4 impulses) was outside the brief and remains untested.</li>
  <li>About 180 variants were run. The pre-registered retention rule and the untouched OOS period limit, but do not remove, selection effects.</li>`}));

// 20
section(20,'Final conclusion',
  el('p',{html:'<strong>Under what measurable conditions does the framework work on XAUUSD, and when should it not trade?</strong>'}),
  el('ul',{html:`<li><strong>It does not show positive expectancy in any period under the original rules</strong>, with costs (${fmtR(A.expectancy)} / ${fmtR(B1.expectancy)} / ${fmtR(B2.expectancy)}) or without (${fmtR(Ai.expectancy)} / ${fmtR(B1i.expectancy)} / ${fmtR(B2i.expectancy)}). The entry logic is roughly a coin flip at the planned geometry; costs decide the sign.</li>
  <li><strong>Least-bad conditions, consistent across DEV, VAL and OOS:</strong> stops of 1.5–2 ATR (never tighter than 1 ATR), the London/New York overlap, impulses no larger than 15 pre-impulse ATR, spread below 15% of the stop, and for breakouts a confirmation bar with range ≥ 1.5 ATR and volume ≥ 1.5× average entered at the close. These reduce the loss from about −0.22R to about −0.07R in DEV and reach +0.06 / +0.08R in VAL / OOS for B2 only; the positive year is 2025 for every playbook.</li>
  <li><strong>No-trade conditions supported by the data:</strong> impulse > 15 ATR; stop < 1 ATR or spread > 15% of the stop; off-hours and low-volume bars; Asia session for breakout pullbacks; New York afternoon for ping-pong; ranges confirmed over 12 or more bars.</li>
  <li><strong>Conditions that did not matter:</strong> alignment with the weekly VAH/VAL (any source, any tolerance), the news-slot proxy, volatility percentile, range width, touch count, pullback depth, target fraction.</li>
  <li><strong>Verdict:</strong> the evidence does not support a Gold Strategy Specification. The measurable part of the framework is not profitable on XAUUSD over 2021–2026; the unmeasurable part (footprint / order-flow confirmation) is where any edge would have to live, and it needs a different dataset to test.</li>`}),
  el('p',{class:'note',html:'Deliverables: <code>GOLD/pbd_counter_trend/results/deliverables/</code> (69 files: rule specification, dataset pointer, all signals and structures, trade-by-trade CSVs per playbook and cost model, loss classification and taxonomy, equity and drawdown, monthly, session, P/B, filters, every experiment, grids, walk-forward, staged adaptations, out-of-sample results) and <code>FINAL_REPORT.md</code>.'}));

// toc
const toc=document.getElementById('toc'); secs.forEach(s=>toc.append(el('a',{href:'#s'+s.n,text:s.n+' '+s.title.replace(/\(.*\)/,'').trim()})));
</script>
"""

out = HTML.replace("__DATA__", json.dumps(payload, separators=(",", ":")).replace("</", "<\\/"))
with open(os.path.join(ROOT, "report.html"), "w", encoding="utf-8") as f:
    f.write(out)
print("report.html", len(out) // 1024, "KB")
