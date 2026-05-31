"""
Test Suite: Test Cases Page
Application Under Test: https://automationexercise.com/test_cases

WHAT THIS FILE COVERS
    test_verify_test_cases_page - navigate to the Test Cases page and verify it loads
    successfully, then verify that test case items are displayed.

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - Navigation to test cases page via button click
    - Verification of page URL and heading
    - Screenshots are saved at key points for evidence/debugging
    - report_steps entries are surfaced in reports/report.html by conftest's
      pytest_runtest_makereport hook.
"""

import pytest

from pages.home_page import HomePage
from pages.test_cases_page import TestCasesPage


@pytest.mark.data_driven
def test_verify_test_cases_page(page, base_url, report_steps):
    """
    Objective : Navigate to Test Cases page and verify it loads successfully.
    Expected  : User is navigated to test cases page with test case items visible.
    """
    # --- Arrange ----------------------------------------------------------
    home_page = HomePage(page)
    test_cases_page = TestCasesPage(page)

    print("\n========== TEST STARTED ==========")

    # --- Act: Open home page and navigate to test cases -------------------
    report_steps.append("1. Open the home page and confirm it loaded")
    home_page.open(base_url)
    home_page.verify_home_is_visible()
    # Match on domain only: base_url is http:// but the site redirects to https.
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"
    page.screenshot(path="01_home_page.png", full_page=True)

    report_steps.append("2. Click 'Test Cases' button to navigate")
    test_cases_page.navigate_to_test_cases()
    page.wait_for_load_state("domcontentloaded")
    page.screenshot(path="02_test_cases_page.png", full_page=True)

    # --- Assert: Verify Test Cases page loaded ---------------------------
    report_steps.append("3. Verify navigation to test cases page was successful")
    test_cases_page.verify_test_cases_page_visible()

    report_steps.append("4. Verify test case items are displayed")
    test_cases_count = test_cases_page.get_test_cases_count()
    assert test_cases_count > 0, "Expected test case items to be visible on the page"
    print(f"Found {test_cases_count} test case items on the page")

    print("\n========== TEST COMPLETED SUCCESSFULLY ==========")
