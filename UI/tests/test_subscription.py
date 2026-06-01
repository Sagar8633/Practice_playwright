"""
Test Suite: Verify Subscription in Home Page
Application Under Test: https://automationexercise.com/

WHAT THIS FILE COVERS
    test_verify_subscription_in_home_page - navigate to home page, scroll to footer,
    verify subscription section, enter email address in subscription input, and verify
    success message.

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - Scrolling down to footer section using JavaScript evaluation
    - Subscription form interaction: entering email and clicking subscribe button
    - Verification of subscription heading and success message
    - report_steps entries are surfaced in reports/report.html by conftest's
      pytest_runtest_makereport hook.
    - Data-driven test: subscription emails are parametrized from YAML
"""

import pytest

from pages.home_page import HomePage


@pytest.mark.data_driven
def test_verify_subscription_in_home_page(page, base_url, subscription_email, report_steps):
    """
    Objective : Navigate to home page, scroll to footer, verify subscription section,
                and verify successful email subscription.
    Data      : subscription_email (email) from YAML.
    Expected  : 'You have been successfully subscribed!' message is visible.
    """
    # --- Arrange ----------------------------------------------------------
    home_page = HomePage(page)

    print("\n========== TEST STARTED ==========")

    # --- Act: Open home page -----------------------------------------------
    report_steps.append("1. Open the home page and confirm it loaded")
    home_page.open(base_url)
    home_page.verify_home_is_visible()
    # Match on domain only: base_url is http:// but the site redirects to https.
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"

    # --- Act: Scroll to footer and verify subscription section -----------
    report_steps.append("2. Scroll down to footer")
    home_page.scroll_to_footer()

    report_steps.append("3. Verify SUBSCRIPTION heading is visible")
    home_page.verify_subscription_heading_visible()

    # --- Act: Subscribe with email ----------------------------------------
    report_steps.append(f"4. Enter email '{subscription_email['email']}' and click subscribe")
    home_page.subscribe_with_email(subscription_email["email"])

    # --- Assert: Verify subscription success message ----------------------
    report_steps.append("5. Verify success message 'You have been successfully subscribed!'")
    home_page.verify_subscription_success_message()

    print("\n========== TEST COMPLETED SUCCESSFULLY ==========")
