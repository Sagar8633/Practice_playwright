"""HTML report generator for Naukri remote job listings.

No result cap - all jobs supplied are rendered.
"""
from __future__ import annotations

import html
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

log = logging.getLogger("naukri_remote_finder.report")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def _company_careers_url(company: str) -> str:
    if not company or company == "N/A":
        return "#"
    return f"https://www.google.com/search?q={quote_plus(company + ' careers jobs apply')}"


def generate_report(jobs, output_path: Path | None = None) -> Path:
    """Generate an HTML report from Job objects. No result cap."""
    if output_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = DATA_DIR / f"naukri-remote-jobs-{today}.html"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(jobs)
    easy_apply_count = sum(1 for j in jobs if getattr(j, "auto_applicable", False))
    companies = sorted(set(j.company for j in jobs if j.company))
    questionnaire_count = sum(1 for j in jobs if j.has_questionnaire)

    rows_html = ""
    for i, job in enumerate(jobs, 1):
        title = html.escape(job.title or "N/A")
        company = html.escape(job.company or "N/A")
        location = html.escape(job.location or "Remote")
        url = html.escape(job.url or "#")
        salary = html.escape(job.salary_label or "")
        experience = html.escape(job.experience_label or "")
        skills = ", ".join(job.skills[:8])
        skills = html.escape(skills)
        posted = html.escape(job.posted_label or "")

        badges = []
        badges.append('<span class="badge badge-remote">Remote</span>')
        if job.company_apply:
            badges.append('<span class="badge badge-company">Company Apply</span>')
        if job.has_questionnaire:
            badges.append('<span class="badge badge-question">Questionnaire</span>')
        else:
            badges.append('<span class="badge badge-easy">1-Click Apply</span>')
        badges_html = " ".join(badges)

        careers_url = html.escape(_company_careers_url(job.company))

        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>
                <a href="{url}" target="_blank" class="job-title">{title}</a>
                <div class="badges">{badges_html}</div>
            </td>
            <td>
                <span class="company-name">{company}</span>
                <a href="{careers_url}" target="_blank" class="careers-link">Careers →</a>
            </td>
            <td>{location}</td>
            <td>{experience}</td>
            <td>{salary}</td>
            <td>{skills}</td>
            <td>{posted}</td>
            <td><a href="{url}" target="_blank" class="apply-btn">Apply →</a></td>
        </tr>"""

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Naukri Remote Jobs - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f7f6f3;
            color: #333;
            line-height: 1.6;
        }}
        .container {{ max-width: 1500px; margin: 0 auto; padding: 20px; }}
        header {{
            background: #4a7fd4;
            color: white;
            padding: 30px 0;
            margin-bottom: 30px;
        }}
        header h1 {{ font-size: 28px; font-weight: 600; }}
        header p {{ opacity: 0.9; margin-top: 5px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stat-card h3 {{
            font-size: 14px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .stat-card .value {{
            font-size: 32px;
            font-weight: 700;
            color: #4a7fd4;
            margin-top: 5px;
        }}
        .filters {{
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filters label {{ font-weight: 500; color: #555; }}
        .filters input {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            width: 280px;
        }}
        .filters input:focus {{ outline: 2px solid #4a7fd4; }}
        table {{
            width: 100%;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        thead {{ background: #4a7fd4; color: white; }}
        th {{
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
            font-size: 14px;
            vertical-align: top;
        }}
        tr:hover {{ background: #f8f9fa; }}
        tr:last-child td {{ border-bottom: none; }}
        .job-title {{ color: #4a7fd4; text-decoration: none; font-weight: 500; }}
        .job-title:hover {{ text-decoration: underline; }}
        .company-name {{ font-weight: 500; }}
        .careers-link {{
            display: block;
            font-size: 12px;
            color: #666;
            text-decoration: none;
            margin-top: 2px;
        }}
        .careers-link:hover {{ color: #4a7fd4; }}
        .badges {{ margin-top: 4px; }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
            margin-right: 4px;
        }}
        .badge-remote {{ background: #cce5ff; color: #004085; }}
        .badge-easy {{ background: #d4edda; color: #155724; }}
        .badge-company {{ background: #fff3cd; color: #856404; }}
        .badge-question {{ background: #f8d7da; color: #721c24; }}
        .apply-btn {{
            display: inline-block;
            padding: 6px 16px;
            background: #4a7fd4;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 500;
            font-size: 13px;
            white-space: nowrap;
        }}
        .apply-btn:hover {{ background: #3868b8; }}
        .companies-list {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-top: 30px;
        }}
        .companies-list h2 {{ font-size: 18px; margin-bottom: 15px; color: #333; }}
        .companies-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 10px;
        }}
        .company-chip {{
            padding: 8px 12px;
            background: #f7f6f3;
            border-radius: 4px;
            font-size: 13px;
        }}
        .company-chip a {{ color: #4a7fd4; text-decoration: none; }}
        .company-chip a:hover {{ text-decoration: underline; }}
        footer {{ text-align: center; padding: 30px; color: #666; font-size: 13px; }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>Naukri Remote Jobs</h1>
            <p>Generated on {now} | {total} remote jobs | Posted in last 24h | Across India</p>
        </div>
    </header>

    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <h3>Total Remote Jobs</h3>
                <div class="value">{total}</div>
            </div>
            <div class="stat-card">
                <h3>1-Click Apply</h3>
                <div class="value">{easy_apply_count}</div>
            </div>
            <div class="stat-card">
                <h3>With Questionnaire</h3>
                <div class="value">{questionnaire_count}</div>
            </div>
            <div class="stat-card">
                <h3>Companies</h3>
                <div class="value">{len(companies)}</div>
            </div>
        </div>

        <div class="filters">
            <label for="searchInput">Filter:</label>
            <input type="text" id="searchInput" placeholder="Search by title, company, skill, location...">
        </div>

        <table id="jobsTable">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Title</th>
                    <th>Company</th>
                    <th>Location</th>
                    <th>Exp</th>
                    <th>Salary</th>
                    <th>Skills</th>
                    <th>Posted</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <div class="companies-list">
            <h2>Companies Hiring Remotely ({len(companies)})</h2>
            <div class="companies-grid">
                {''.join(f'<div class="company-chip"><a href="{_company_careers_url(c)}" target="_blank">{html.escape(c)}</a></div>' for c in companies)}
            </div>
        </div>
    </div>

    <footer>
        <p>Naukri Remote Job Finder | Remote-only, posted in last 24h, across India</p>
        <p>Click "Careers →" to find each company's official job page</p>
    </footer>

    <script>
        const searchInput = document.getElementById('searchInput');
        const table = document.getElementById('jobsTable');
        const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
        searchInput.addEventListener('input', function() {{
            const filter = this.value.toLowerCase();
            for (let i = 0; i < rows.length; i++) {{
                rows[i].style.display = rows[i].textContent.toLowerCase().includes(filter) ? '' : 'none';
            }}
        }});
    </script>
</body>
</html>"""

    output_path.write_text(report_html, encoding="utf-8")
    log.info("Report written to %s (%d jobs)", output_path, total)
    return output_path


def save_json(jobs, output_path: Path | None = None) -> Path:
    """Save raw job data to JSON. No result cap."""
    if output_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = DATA_DIR / f"naukri-remote-jobs-{today}.json"

    clean = []
    for job in jobs:
        d = job.to_dict() if hasattr(job, "to_dict") else dict(job)
        d["is_remote"] = getattr(job, "is_remote", False)
        d["auto_applicable"] = getattr(job, "auto_applicable", False)
        d["age_days"] = getattr(job, "age_days", None)
        clean.append(d)

    output_path.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("JSON written to %s (%d jobs)", output_path, len(clean))
    return output_path
