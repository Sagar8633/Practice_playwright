from playwright.sync_api import expect

from .base_page import BasePage


class TestCasesPage(BasePage):
    """Page object for the Test Cases page"""
    __test__ = False
    # Locators
    # test_cases_button = "a[href='/test_cases']:visible"
    test_cases_heading = "b:has-text('Test Cases')"
    test_case_items = "div.row div[id]"  # Test case items typically have IDs

    # Page URL pattern
    test_cases_url_pattern = "test_cases"

    # -------- Verification Methods --------

    def navigate_to_test_cases(self):
        self.page.get_by_role("link",name="Test Cases",exact=True).first.click()

    def verify_test_cases_page_visible(self):
        """Verify that the Test Cases page is loaded and visible"""
        print("Verifying Test Cases page loaded...")

        # Verify URL contains test_cases
        assert self.test_cases_url_pattern in self.page.url, (
            f"Expected URL to contain '{self.test_cases_url_pattern}', "
            f"but got: {self.page.url}"
        )

        # Verify page heading is visible
        self.expect_visible(self.test_cases_heading)
        print("Test Cases page loaded successfully")

    def get_test_cases_count(self):
        """Get the number of test case items visible on the page"""
        locators = self.page.locator(self.test_case_items)
        return locators.count()
