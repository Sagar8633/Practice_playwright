"""Combined HTML report - Naukri (India) + global boards. No result cap."""
from __future__ import annotations

import html
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

log = logging.getLogger("global_remote_finder.report")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def careers_url(company: str) -> str:
    if not company:
        return "#"
    return f"https://www.google.com/search?q={quote_plus(company + ' careers jobs apply')}"


def _board_color(source: str) -> str:
    return {
        "Naukri": "#4a7fd4",
        "RemoteOK": "#0a66c2",
        "WeWorkRemotely": "#34c759",
        "Remotive": "#ff6b6b",
    }.get(source, "#666")


def unified(jobs: list[dict], output_path=None, title="All Remote Jobs",
            subtitle="") -> Path:
    """Generate an HTML report from unified job dicts."""
    if output_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = DATA_DIR / f"global-remote-jobs-{today}.html"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(jobs)
    companies = sorted(set(j.get("company", "") for j in jobs if j.get("company")))

    # Per-board counts
    board_counts = {}
    for j in jobs:
        src = j.get("source", "?")
        board_counts[src] = board_counts.get(src, 0) + 1

    rows_html = ""
    for i, job in enumerate(jobs, 1):
        title = html.escape(job.get("title") or "N/A")
        company = html.escape(job.get("company") or "N/A")
        location = html.escape(job.get("location") or "Remote")
        url = html.escape(job.get("url") or "#")
        source = html.escape(job.get("source") or "?")
        color = _board_color(job.get("source"))
        experience = html.escape(job.get("experience") or "")
        salary = html.escape(job.get("salary") or "")
        skills = ", ".join(job.get("skills", [])[:6])
        skills = html.escape(skills)
        posted = html.escape(job.get("posted") or "")
        age = job.get("age_days")
        age_label = f"{age:.1f}d ago" if age is not None else ""
        careers = html.escape(careers_url(job.get("company")))
        easy = '<span class="badge badge-easy">1-Click</span>' if job.get("_naukri") and not job.get("has_questionnaire") else ""

        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>
                <a href="{url}" target="_blank" class="job-title">{title}</a>
                <div class="badges"><span class="badge badge-board" style="background:{color}">{source}</span>{easy}</div>
            </td>
            <td>
                <span class="company-name">{company}</span>
                <a href="{careers}" target="_blank" class="careers-link">Careers →</a>
            </td>
            <td>{location}</td>
            <td>{experience}</td>
            <td>{salary}</td>
            <td>{skills}</td>
            <td>{posted}<div class="age">{age_label}</div></td>
            <td><a href="{url}" target="_blank" class="apply-btn">Apply →</a></td>
        </tr>"""

    stat_cards = "".join(
        f'<div class="stat-card"><h3>{html.escape(k)}</h3><div class="value">{v}</div></div>'
        for k, v in board_counts.items()
    )

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - {datetime.now().strftime('%Y-%m-%d')}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,'Segoe UI',Roboto,Oxygen,Ubuntu,sans-serif; background:#f3f2ef; color:#333; line-height:1.6; }}
.container {{ max-width:1500px; margin:0 auto; padding:20px; }}
header {{ background:#111827; color:white; padding:30px 0; margin-bottom:30px; }}
header h1 {{ font-size:28px; font-weight:600; }}
header p {{ opacity:.9; margin-top:5px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:20px; margin-bottom:30px; }}
.stat-card {{ background:white; padding:20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.1); }}
.stat-card h3 {{ font-size:14px; color:#666; text-transform:uppercase; letter-spacing:.5px; }}
.stat-card .value {{ font-size:32px; font-weight:700; color:#111827; margin-top:5px; }}
.filters {{ background:white; padding:15px 20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.1); margin-bottom:20px; }}
.filters input {{ padding:8px 12px; border:1px solid #ddd; border-radius:4px; font-size:14px; width:300px; }}
.filters input:focus {{ outline:2px solid #111827; }}
table {{ width:100%; background:white; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.1); overflow:hidden; }}
thead {{ background:#111827; color:white; }}
th {{ padding:12px 15px; text-align:left; font-weight:600; font-size:13px; text-transform:uppercase; letter-spacing:.5px; }}
td {{ padding:12px 15px; border-bottom:1px solid #eee; font-size:14px; vertical-align:top; }}
tr:hover {{ background:#f8f9fa; }}
.job-title {{ color:#111827; text-decoration:none; font-weight:500; }}
.job-title:hover {{ text-decoration:underline; }}
.company-name {{ font-weight:500; }}
.careers-link {{ display:block; font-size:12px; color:#666; text-decoration:none; }}
.careers-link:hover {{ color:#111827; }}
.badges {{ margin-top:4px; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:500; margin-right:4px; color:white; }}
.badge-easy {{ background:#d4edda; color:#155724; }}
.age {{ font-size:11px; color:#888; }}
.apply-btn {{ display:inline-block; padding:6px 16px; background:#111827; color:white; text-decoration:none; border-radius:4px; font-weight:500; font-size:13px; white-space:nowrap; }}
.apply-btn:hover {{ background:#000; }}
.companies-list {{ background:white; padding:20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.1); margin-top:30px; }}
.companies-list h2 {{ font-size:18px; margin-bottom:15px; }}
.companies-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:10px; }}
.company-chip {{ padding:8px 12px; background:#f3f2ef; border-radius:4px; font-size:13px; }}
.company-chip a {{ color:#111827; text-decoration:none; }}
.company-chip a:hover {{ text-decoration:underline; }}
footer {{ text-align:center; padding:30px; color:#666; font-size:13px; }}
</style>
</head>
<body>
<header>
  <div class="container">
    <h1>{title}</h1>
    <p>Generated on {now} | {total} remote jobs | {html.escape(subtitle)}</p>
  </div>
</header>
<div class="container">
  <div class="stats">
    <div class="stat-card"><h3>Total</h3><div class="value">{total}</div></div>
    {stat_cards}
  </div>
  <div class="filters">
    <input type="text" id="searchInput" placeholder="Filter by title, company, skill, location, board...">
  </div>
  <table id="jobsTable">
    <thead><tr>
      <th>#</th><th>Title</th><th>Company</th><th>Location</th><th>Exp</th>
      <th>Salary</th><th>Skills</th><th>Posted</th><th>Action</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="companies-list">
    <h2>Companies Hiring Remotely ({len(companies)})</h2>
    <div class="companies-grid">
      {''.join(f'<div class="company-chip"><a href="{html.escape(careers_url(c))}" target="_blank">{html.escape(c)}</a></div>' for c in companies)}
    </div>
  </div>
</div>
<footer>
  <p>Global Remote Job Finder | Naukri (India) + RemoteOK + WeWorkRemotely + Remotive</p>
  <p>All results kept - no cap. Click a source badge to see the board it came from.</p>
</footer>
<script>
const input=document.getElementById('searchInput');const table=document.getElementById('jobsTable');
const rows=table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
input.addEventListener('input',function(){{const f=this.value.toLowerCase();
for(let i=0;i<rows.length;i++){{rows[i].style.display=rows[i].textContent.toLowerCase().includes(f)?'':'none';}}}});
</script>
</body>
</html>"""

    output_path.write_text(report_html, encoding="utf-8")
    log.info("Report written to %s (%d jobs)", output_path, total)
    return output_path


def save_json(jobs: list[dict], output_path=None) -> Path:
    if output_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = DATA_DIR / f"global-remote-jobs-{today}.json"
    output_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("JSON written to %s (%d jobs)", output_path, len(jobs))
    return output_path
