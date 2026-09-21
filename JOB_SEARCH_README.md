# Remote Job Search Tool - Usage Instructions

## Quick Start

1. **Activate your virtual environment:**
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
   & d:\Practice_Playwright\venv\Scripts\Activate.ps1
   ```

2. **Install Playwright (if not already installed):**
   ```powershell
   pip install playwright
   playwright install chromium
   ```

3. **Run the job search tool:**
   ```powershell
   python job_search.py
   ```

4. **View results:**
   - Open `remote_jobs_report.html` in your web browser
   - Check `jobs.json` for raw data

## What This Tool Does

✅ **Legitimate job scraping from public sources:**
- LinkedIn Jobs (public listings only)
- Indeed Jobs
- We Work Remotely
- RemoteOK

✅ **Extracts public information:**
- Job titles
- Company names
- Job locations
- Application links

✅ **Generates professional reports:**
- HTML report with clickable links
- JSON data file
- Company statistics

## What This Tool Does NOT Do

❌ **Does NOT scrape personal contact information:**
- No email addresses
- No phone numbers
- No private profiles

❌ **Does NOT violate terms of service:**
- Respects website rate limits
- Only accesses public data
- No automated login or bypass

## Finding Company Contact Information (Legitimate Ways)

Since scraping personal contact info is against privacy laws, here are legal alternatives:

### 1. **Visit Company Career Pages**
Most companies have public "Contact Us" or "Careers" pages with general inquiry emails.

### 2. **Use LinkedIn's Official Features**
- Send connection requests to recruiters
- Use LinkedIn's messaging system
- Follow companies for job updates

### 3. **Check Company Websites**
- Look for "Contact" or "About" pages
- Many list press/media contact emails
- Some have investor relations contacts

### 4. **Professional Networking**
- Attend virtual job fairs
- Join industry groups on LinkedIn
- Participate in webinars and events

## Customization

Edit `job_search.py` to:
- Change search keywords
- Add more job sources
- Modify the HTML report
- Adjust the number of jobs scraped

## Troubleshooting

**If Playwright doesn't work:**
1. Ensure virtual environment is activated
2. Run `playwright install chromium`
3. Check internet connection

**If websites block scraping:**
1. The tool uses legitimate headers
2. Try running at different times
3. Check if website structure has changed

## Legal Compliance

This tool is designed to comply with:
- LinkedIn Terms of Service
- Indeed Terms of Service
- GDPR and CCPA regulations
- Anti-spam laws

The tool only collects publicly available job listing data, not personal information.