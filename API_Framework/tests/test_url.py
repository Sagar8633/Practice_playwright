# test_url.py
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    api = p.request.new_context(base_url="https://automationexercise.com")
    resp = api.get("/api/brandsList")
    print(resp.status)  # Should print 200
    print(resp.json()["responseCode"])  # Should print 200