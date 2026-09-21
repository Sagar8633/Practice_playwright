import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import json

class RemoteJobScraper:
    def __init__(self):
        self.jobs = []
        
    async def scrape_linkedin_jobs(self, page, query="remote", location=""):
        """Scrape LinkedIn public job listings (no login required)"""
        print("Scraping LinkedIn Jobs...")
        url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&f_WT=2"  # f_WT=2 is remote filter
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Get job cards
            job_cards = await page.query_selector_all(".base-card")
            
            for card in job_cards[:20]:  # Limit to 20 jobs
                try:
                    title = await card.query_selector(".base-search-card__title")
                    company = await card.query_selector(".base-search-card__subtitle a")
                    location_el = await card.query_selector(".job-search-card__location")
                    link = await card.query_selector("a.base-card__full-link")
                    
                    job_data = {
                        "source": "LinkedIn",
                        "title": await title.inner_text() if title else "N/A",
                        "company": await company.inner_text() if company else "N/A",
                        "location": await location_el.inner_text() if location_el else "Remote",
                        "link": await link.get_attribute("href") if link else "N/A",
                        "scraped_at": datetime.now().isoformat()
                    }
                    self.jobs.append(job_data)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error scraping LinkedIn: {e}")
    
    async def scrape_indeed_jobs(self, page, query="remote"):
        """Scrape Indeed public job listings"""
        print("Scraping Indeed Jobs...")
        url = f"https://www.indeed.com/jobs?q={query}&l=&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            job_cards = await page.query_selector_all(".job_seen_beacon")
            
            for card in job_cards[:20]:
                try:
                    title = await card.query_selector(".jobTitle a")
                    company = await card.query_selector("[data-testid='company-name']")
                    location_el = await card.query_selector("[data-testid='text-location']")
                    
                    job_data = {
                        "source": "Indeed",
                        "title": await title.inner_text() if title else "N/A",
                        "company": await company.inner_text() if company else "N/A",
                        "location": await location_el.inner_text() if location_el else "Remote",
                        "link": f"https://www.indeed.com" + await title.get_attribute("href") if title else "N/A",
                        "scraped_at": datetime.now().isoformat()
                    }
                    self.jobs.append(job_data)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error scraping Indeed: {e}")
    
    async def scrape_glassdoor_jobs(self, page, query="remote"):
        """Scrape Glassdoor public job listings"""
        print("Scraping Glassdoor Jobs...")
        url = f"https://www.glassdoor.com/Job/remote-jobs-SRCH_IL.0,6_IS11047_KO7,13.htm"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            job_cards = await page.query_selector_all("[data-test='jobListing']")
            
            for card in job_cards[:20]:
                try:
                    title = await card.query_selector(".jobTitle a")
                    company = await card.query_selector(". работодатель a")
                    location_el = await card.query_selector(".loc")
                    
                    job_data = {
                        "source": "Glassdoor",
                        "title": await title.inner_text() if title else "N/A",
                        "company": await company.inner_text() if company else "N/A",
                        "location": await location_el.inner_text() if location_el else "Remote",
                        "link": await title.get_attribute("href") if title else "N/A",
                        "scraped_at": datetime.now().isoformat()
                    }
                    self.jobs.append(job_data)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error scraping Glassdoor: {e}")
    
    async def scrape_weworkremotely(self, page):
        """Scrape We Work Remotely - legitimate remote job board"""
        print("Scraping We Work Remotely...")
        url = "https://weworkremotely.com/remote-jobs"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            job_cards = await page.query_selector_all(".feature")
            
            for card in job_cards[:20]:
                try:
                    title = await card.query_selector("h2 a")
                    company = await card.query_selector(".company")
                    location_el = await card.query_selector(".region")
                    
                    job_data = {
                        "source": "WeWorkRemotely",
                        "title": await title.inner_text() if title else "N/A",
                        "company": await company.inner_text() if company else "N/A",
                        "location": await location_el.inner_text() if location_el else "Remote",
                        "link": await title.get_attribute("href") if title else "N/A",
                        "scraped_at": datetime.now().isoformat()
                    }
                    self.jobs.append(job_data)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error scraping WeWorkRemotely: {e}")
    
    async def scrape_remoteok(self, page):
        """Scrape RemoteOK - legitimate remote job board"""
        print("Scraping RemoteOK...")
        url = "https://remoteok.com/remote-dev-jobs"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            job_cards = await page.query_selector_all(".company_and_position")
            
            for card in job_cards[:20]:
                try:
                    title = await card.query_selector("h2")
                    company = await card.query_selector("h3")
                    
                    job_data = {
                        "source": "RemoteOK",
                        "title": await title.inner_text() if title else "N/A",
                        "company": await company.inner_text() if company else "N/A",
                        "location": "Remote",
                        "link": url,
                        "scraped_at": datetime.now().isoformat()
                    }
                    self.jobs.append(job_data)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error scraping RemoteOK: {e}")
    
    async def get_company_careers(self, company_name):
        """Search for company career pages (public information)"""
        career_urls = []
        
        # Common career page patterns
        patterns = [
            f"https://www.google.com/search?q={company_name}+careers",
            f"https://www.google.com/search?q={company_name}+jobs+apply"
        ]
        
        return patterns
    
    async def scrape_all_sources(self):
        """Scrape all job sources"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Scrape from multiple sources
            await self.scrape_weworkremotely(page)
            await self.scrape_remoteok(page)
            await self.scrape_linkedin_jobs(page)
            await self.scrape_indeed_jobs(page)
            
            await browser.close()
    
    def generate_html_report(self):
        """Generate HTML report with job listings"""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Remote Jobs Report - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; text-align: center; }}
        .stats {{ background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .job-card {{ background: #fff; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .job-card h3 {{ margin: 0 0 10px 0; color: #0066cc; }}
        .company {{ color: #666; font-weight: bold; }}
        .location {{ color: #888; font-size: 0.9em; }}
        .source {{ background: #e0e0e0; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }}
        .link {{ display: inline-block; margin-top: 10px; padding: 8px 16px; background: #0066cc; color: #fff; text-decoration: none; border-radius: 4px; }}
        .link:hover {{ background: #0055aa; }}
        .footer {{ text-align: center; margin-top: 40px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Remote Job Listings Report</h1>
        
        <div class="stats">
            <h2>Statistics</h2>
            <p><strong>Total Jobs Found:</strong> {len(self.jobs)}</p>
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Sources:</strong> LinkedIn, Indeed, We Work Remotely, RemoteOK</p>
        </div>
        
        <h2>Job Listings</h2>
"""
        
        for i, job in enumerate(self.jobs, 1):
            html += f"""
        <div class="job-card">
            <h3>{job['title']}</h3>
            <p class="company">Company: {job['company']}</p>
            <p class="location">Location: {job['location']}</p>
            <p class="source">Source: {job['source']}</p>
            <a href="{job['link']}" class="link" target="_blank">Apply / View Job</a>
        </div>
"""
        
        html += """
        <div class="footer">
            <p>This report contains legitimate public job listings.</p>
            <p>For company contact information, visit their official career pages directly.</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def save_to_json(self, filename="jobs.json"):
        """Save jobs to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.jobs, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(self.jobs)} jobs to {filename}")

async def main():
    scraper = RemoteJobScraper()
    await scraper.scrape_all_sources()
    
    # Generate HTML report
    html_content = scraper.generate_html_report()
    with open("remote_jobs_report.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\nGenerated HTML report: remote_jobs_report.html")
    print(f"Total jobs found: {len(scraper.jobs)}")
    
    # Save to JSON
    scraper.save_to_json()
    
    # Print summary
    print("\nTop Companies Hiring:")
    companies = set(job['company'] for job in scraper.jobs if job['company'] != 'N/A')
    for company in list(companies)[:10]:
        print(f"  - {company}")

if __name__ == "__main__":
    asyncio.run(main())