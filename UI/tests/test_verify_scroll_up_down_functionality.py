import pytest

from pages.home_page import HomePage


@pytest.mark.scroll_functionality
def test_verify_scroll_up_down_functionality(page, base_url, report_steps):
    """
    Test Case 25: Verify Scroll Up using 'Arrow' button and Scroll Down functionality

    Test Steps:
    1. Launch browser
    2. Navigate to url 'http://automationexercise.com'
    3. Verify that home page is visible successfully
    4. Scroll down page to bottom
    5. Verify 'SUBSCRIPTION' is visible
    6. Click on arrow at bottom right side to move upward
    7. Verify that page is scrolled up and 'Full-Fledged practice website for Automation Engineers' text is visible on screen
    """

    home_page = HomePage(page)

    try:
        # Step 1: Browser launched
        report_steps.append("Step 1: Browser launched")
        print("Step 1: Browser launched")

        # Step 2: Navigate to home page
        report_steps.append("Step 2: Navigating to Home Page")
        print("Step 2: Navigating to Home Page")
        home_page.goto(base_url)

        # Step 3: Verify home page is visible
        report_steps.append("Step 3: Verifying Home Page is visible")
        print("Step 3: Verifying Home Page is visible")
        home_page.verify_home_page_loaded()

        # Step 4: Scroll down page to bottom
        report_steps.append("Step 4: Scrolling down to bottom of the page")
        print("Step 4: Scrolling down to bottom of the page")
        home_page.scroll_to_footer()

        # Step 5: Verify 'SUBSCRIPTION' is visible
        report_steps.append("Step 5: Verifying SUBSCRIPTION heading is visible")
        print("Step 5: Verifying SUBSCRIPTION heading is visible")
        home_page.verify_subscription_heading_visible()

        # Step 6: Click on arrow at bottom right side to move upward
        report_steps.append("Step 6: Clicking scroll-up arrow button")
        print("Step 6: Clicking scroll-up arrow button")
        home_page.click_scroll_up_button()

        # Step 7: Verify that page is scrolled up and hero text is visible
        report_steps.append("Step 7: Verifying home page hero text is visible after scroll up")
        print("Step 7: Verifying home page hero text is visible after scroll up")
        home_page.verify_home_hero_text_visible()

        report_steps.append("✅ Test Passed: Scroll up and scroll down functionality verified")
        print("\n✅ Test Passed: Scroll up and scroll down functionality verified")

    except AssertionError as e:
        report_steps.append(f"❌ Test Failed: {str(e)}")
        print(f"\n❌ Test Failed: {str(e)}")
        raise

    except Exception as e:
        report_steps.append(f"❌ Test Error: {str(e)}")
        print(f"\n❌ Test Error: {str(e)}")
        raise
