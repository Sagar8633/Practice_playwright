# Remote Job Search Tool

This Playwright-based tool scrapes legitimate public job listings from multiple sources to help you find remote job opportunities.

## Features

- Scrapes remote jobs from multiple legitimate sources:
  - LinkedIn Jobs (public listings only)
  - Indeed Jobs
  - We Work Remotely
  - RemoteOK
- Generates detailed HTML report
- Saves data to JSON format
- Finds company career page URLs
- Respects website terms of service

## What This Tool Does NOT Do

- ❌ Does NOT scrape personal contact information (emails, phone numbers)
- ❌ Does NOT violate LinkedIn/Indeed Terms of Service
- ❌ Does NOT collect private user data
- ❌ Does NOT perform automated login or authentication bypass

## What This Tool DOES Do

- ✅ Scrapes public job listings (company name, job title, location)
- ✅ Provides direct links to job applications
- ✅ Finds legitimate company career pages
- ✅ Generates professional HTML reports
- ✅ Respects website rate limits and terms of service

## Installation

1. Make sure you have Python 3.7+ installed
2. Activate your virtual environment:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
   & d:\Practice_Playwright\venv\Scripts\Activate.ps1
   ```
3. Install required packages:
   ```powershell
   pip install playwright
   playwright install chromium
   ```

## Usage

1. Run the job scraper:
   ```powershell
   python job_search.py
   ```

2. The tool will:
   - Launch a browser window
   - Scrape jobs from multiple sources
   - Generate `remote_jobs_report.html`
   - Save data to `jobs.json`

3. Open `remote_jobs_report.html` in your browser to view the report

## Output Files

- **remote_jobs_report.html**: Professional HTML report with all job listings
- **jobs.json**: Machine-readable JSON format of all jobs

## How to Find Company Contact Information (Legitimate Ways)

Since scraping personal contact information is against terms of service and privacy laws, here are legitimate ways to find company contact information:

1. **Visit Company Career Pages Directly**
   - Most companies have "Contact Us" or "Careers" pages
   - These are public and legal to access

2. **Use LinkedIn's Official Features**
   - Connect with recruiters through LinkedIn's messaging system
   - Follow companies to see their job posts

3. **Check Company Websites**
   - Look for "Contact" or "About" pages
   - Many list general inquiry emails

4. **Use Professional Networking**
   - Attend virtual job fairs
   - Join industry-specific groups

## Customization

You can modify the `job_search.py` file to:
- Change search queries
- Add more job sources
- Adjust the number of jobs to scrape
- Modify the HTML report template

## Legal Considerations

This tool is designed to be compliant with:
- LinkedIn Terms of Service
- Indeed Terms of Service
- General data protection regulations (GDPR, CCPA)
- Anti-spam laws

The tool only scrapes publicly available job listings and does not collect personal data.

## Support

If you encounter issues:
1. Check that Playwright is installed correctly
2. Ensure your virtual environment is activated
3. Verify internet connectivity
4. Check if target websites have updated their structure

## Responsible Usage

Please use this tool responsibly:
- Don't scrape too frequently (respect rate limits)
- Use the data for personal job searching only
- Don't sell or distribute the scraped data
- Always apply to jobs through official channels