from playwright.sync_api import expect
from pathlib import Path
from datetime import datetime


class BasePage:
    def __init__(self, page):
        self.page = page

    def goto(self, url):
        for attempt in range(3):
            try:
                self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )
                return
            except Exception as e:
                print(f"Navigation attempt {attempt + 1} failed: {e}")

        raise Exception(f"Failed to navigate to {url}")

    def click(self, selector):
        locator = self.page.locator(selector)

        expect(locator).to_be_visible()

        locator.click()
    
    # CHANGED: Added method to click and wait for navigation (used for logout)
    def click_and_wait_for_navigation(self, selector: str):
        # Wait for navigation after clicking to handle page redirects
        with self.page.expect_navigation():
            self.page.locator(selector).click()
        # CHANGED: Wait for page to be fully loaded after navigation
        self.page.wait_for_load_state('domcontentloaded')

    def fill(self, selector, value):
        locator = self.page.locator(selector)

        expect(locator).to_be_visible()

        locator.fill(value)

    def check(self, selector: str):
        self.page.locator(selector).check()

    def select_option(self, selector: str, value: str):
        self.page.locator(selector).select_option(value)

    def expect_visible(self, selector: str, text: str = None, timeout: int = None):
        # timeout is optional (ms); pass it for elements that appear after a
        # slow server round-trip (e.g. signup/login error banners).
        locator = self.page.locator(selector)
        if text:
            expect(locator).to_have_text(text, timeout=timeout)
        else:
            expect(locator).to_be_visible(timeout=timeout)

    def expect_text_contains(self, selector: str, text: str):
        expect(self.page.locator(selector)).to_contain_text(text)

    def take_screenshot(self, name):

        today = datetime.now().strftime("%Y-%m-%d")

        screenshot_dir = Path("Snapshots") / today
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        self.page.screenshot(
            path=screenshot_dir / f"{name}.png",
            full_page=True
        )