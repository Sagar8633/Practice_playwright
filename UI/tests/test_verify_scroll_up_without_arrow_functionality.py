import pytest

from pages.home_page import HomePage


@pytest.mark.scroll_functionality
def test_verify_scroll_up_without_arrow_functionality(page, base_url, report_steps):
    """
    Test Case 26: Verify Scroll Up without 'Arrow' button and Scroll Down functionality

    Test Steps:
    1. Launch browser
    2. Navigate to url 'http://automationexercise.com'
    3. Verify that home page is visible successfully
    4. Scroll down page to bottom
    5. Verify 'SUBSCRIPTION' is visible
    6. Scroll up page to top
    7. Verify that page is scrolled up and 'Full-Fledged practice website for Automation Engineers' text is visible on screen
    """

    home_page = HomePage(page)

    try:
        report_steps.append("Step 1: Browser launched")
        print("Step 1: Browser launched")

        report_steps.append("Step 2: Navigating to Home Page")
        print("Step 2: Navigating to Home Page")
        home_page.goto(base_url)

        report_steps.append("Step 3: Verifying Home Page is visible")
        print("Step 3: Verifying Home Page is visible")
        home_page.verify_home_page_loaded()

        report_steps.append("Step 4: Scrolling down to bottom of page")
        print("Step 4: Scrolling down to bottom of page")
        home_page.scroll_to_footer()

        report_steps.append("Step 5: Verifying SUBSCRIPTION heading is visible")
        print("Step 5: Verifying SUBSCRIPTION heading is visible")
        home_page.verify_subscription_heading_visible()

        report_steps.append("Step 6: Scrolling up to top of page without arrow button")
        print("Step 6: Scrolling up to top of page without arrow button")
        home_page.scroll_to_top()

        report_steps.append("Step 7: Verifying home page hero text is visible after scrolling up")
        print("Step 7: Verifying home page hero text is visible after scrolling up")
        home_page.verify_home_hero_text_visible()

        report_steps.append("✅ Test Passed: Scroll up without arrow and scroll down functionality verified")
        print("\n✅ Test Passed: Scroll up without arrow and scroll down functionality verified")

    except AssertionError as e:
        report_steps.append(f"❌ Test Failed: {str(e)}")
        print(f"\n❌ Test Failed: {str(e)}")
        raise

    except Exception as e:
        report_steps.append(f"❌ Test Error: {str(e)}")
        print(f"\n❌ Test Error: {str(e)}")
        raise
