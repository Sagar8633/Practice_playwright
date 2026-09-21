"""HTML report generator for LinkedIn remote job listings.

Creates a rich, styled HTML report with company names, job titles,
direct apply links, and company career page links.
"""
from __future__ import annotations

import html
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

log = logging.getLogger("linkedin_finder.report")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def _company_careers_url(company: str) -> str:
    """Generate a Google search URL for company careers page."""
    if not company or company == "N/A":
        return "#"
    return f"https://www.google.com/search?q={quote_plus(company + ' careers jobs apply')}"


def _company_logo_url(company: str) -> str:
    """Generate a company logo URL via Google's favicon service."""
    if not company or company == "N/A":
        return ""
    # Use a placeholder with the first letter
    return ""


def generate_report(cards: list[dict], output_path: Path | None = None,
                    search_info: dict | None = None) -> Path:
    """Generate an HTML report from job cards.

    Args:
        cards: List of job card dicts from search
        output_path: Where to write the HTML file
        search_info: Optional dict with search metadata

    Returns:
        Path to the generated HTML file
    """
    if output_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = DATA_DIR / f"linkedin-jobs-{today}.html"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(cards)
    remote_count = sum(1 for c in cards if c.get("_remote"))
    easy_apply_count = sum(1 for c in cards if c.get("easy_apply"))

    # Unique companies
    companies = sorted(set(c.get("company", "N/A") for c in cards if c.get("company")))

    rows_html = ""
    for i, card in enumerate(cards, 1):
        title = html.escape(card.get("title") or "N/A")
        company = html.escape(card.get("company") or "N/A")
        location = html.escape(card.get("location") or "Remote")
        url = html.escape(card.get("url") or "#")
        insight = html.escape(card.get("insight") or "")

        badges = []
        if card.get("easy_apply"):
            badges.append('<span class="badge badge-easy">Easy Apply</span>')
        if card.get("promoted"):
            badges.append('<span class="badge badge-promoted">Promoted</span>')
        if card.get("_remote"):
            badges.append('<span class="badge badge-remote">Remote</span>')
        badges_html = " ".join(badges)

        careers_url = html.escape(_company_careers_url(card.get("company", "")))

        # Extract salary from metadata if present
        salary = ""
        for item in card.get("metadata") or []:
            if any(mark in item for mark in ("/yr", "/hr", "₹", "$", "LPA", "INR", "€", "£")):
                salary = html.escape(item)
                break

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
            <td>{salary}</td>
            <td>{insight}</td>
            <td><a href="{url}" target="_blank" class="apply-btn">Apply →</a></td>
        </tr>"""

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LinkedIn Remote Jobs - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f3f2ef;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: #0a66c2;
            color: white;
            padding: 30px 0;
            margin-bottom: 30px;
        }}
        header h1 {{
            font-size: 28px;
            font-weight: 600;
        }}
        header p {{
            opacity: 0.9;
            margin-top: 5px;
        }}
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
            color: #0a66c2;
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
        .filters label {{
            font-weight: 500;
            color: #555;
        }}
        .filters input, .filters select {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }}
        .filters input {{
            width: 250px;
        }}
        table {{
            width: 100%;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        thead {{
            background: #0a66c2;
            color: white;
        }}
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
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .job-title {{
            color: #0a66c2;
            text-decoration: none;
            font-weight: 500;
        }}
        .job-title:hover {{
            text-decoration: underline;
        }}
        .company-name {{
            font-weight: 500;
        }}
        .careers-link {{
            display: block;
            font-size: 12px;
            color: #666;
            text-decoration: none;
            margin-top: 2px;
        }}
        .careers-link:hover {{
            color: #0a66c2;
        }}
        .badges {{
            margin-top: 4px;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
            margin-right: 4px;
        }}
        .badge-easy {{
            background: #d4edda;
            color: #155724;
        }}
        .badge-promoted {{
            background: #fff3cd;
            color: #856404;
        }}
        .badge-remote {{
            background: #cce5ff;
            color: #004085;
        }}
        .apply-btn {{
            display: inline-block;
            padding: 6px 16px;
            background: #0a66c2;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 500;
            font-size: 13px;
        }}
        .apply-btn:hover {{
            background: #004182;
        }}
        .companies-list {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-top: 30px;
        }}
        .companies-list h2 {{
            font-size: 18px;
            margin-bottom: 15px;
            color: #333;
        }}
        .companies-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 10px;
        }}
        .company-chip {{
            padding: 8px 12px;
            background: #f3f2ef;
            border-radius: 4px;
            font-size: 13px;
        }}
        .company-chip a {{
            color: #0a66c2;
            text-decoration: none;
        }}
        .company-chip a:hover {{
            text-decoration: underline;
        }}
        footer {{
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 13px;
        }}
        #searchInput:focus {{
            outline: 2px solid #0a66c2;
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>LinkedIn Remote Jobs</h1>
            <p>Generated on {now} | {total} jobs found</p>
        </div>
    </header>

    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <h3>Total Jobs</h3>
                <div class="value">{total}</div>
            </div>
            <div class="stat-card">
                <h3>Remote</h3>
                <div class="value">{remote_count}</div>
            </div>
            <div class="stat-card">
                <h3>Easy Apply</h3>
                <div class="value">{easy_apply_count}</div>
            </div>
            <div class="stat-card">
                <h3>Companies</h3>
                <div class="value">{len(companies)}</div>
            </div>
        </div>

        <div class="filters">
            <label for="searchInput">Filter:</label>
            <input type="text" id="searchInput" placeholder="Search by title, company, location...">
        </div>

        <table id="jobsTable">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Title</th>
                    <th>Company</th>
                    <th>Location</th>
                    <th>Salary</th>
                    <th>Insight</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <div class="companies-list">
            <h2>Companies Hiring ({len(companies)})</h2>
            <div class="companies-grid">
                {''.join(f'<div class="company-chip"><a href="{_company_careers_url(c)}" target="_blank">{html.escape(c)}</a></div>' for c in companies)}
            </div>
        </div>
    </div>

    <footer>
        <p>LinkedIn Remote Job Finder | Data sourced from LinkedIn public job listings</p>
        <p>Click "Careers →" to find each company's official job page</p>
    </footer>

    <script>
        // Live filter
        const searchInput = document.getElementById('searchInput');
        const table = document.getElementById('jobsTable');
        const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');

        searchInput.addEventListener('input', function() {{
            const filter = this.value.toLowerCase();
            for (let i = 0; i < rows.length; i++) {{
                const text = rows[i].textContent.toLowerCase();
                rows[i].style.display = text.includes(filter) ? '' : 'none';
            }}
        }});
    </script>
</body>
</html>"""

    output_path.write_text(report_html, encoding="utf-8")
    log.info("Report written to %s (%d jobs)", output_path, total)
    return output_path


def save_json(cards: list[dict], output_path: Path | None = None) -> Path:
    """Save raw card data to JSON."""
    if output_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = DATA_DIR / f"linkedin-jobs-{today}.json"

    # Clean internal keys
    clean = []
    for card in cards:
        c = {k: v for k, v in card.items() if not k.startswith("_")}
        clean.append(c)

    output_path.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("JSON written to %s (%d jobs)", output_path, len(clean))
    return output_path
