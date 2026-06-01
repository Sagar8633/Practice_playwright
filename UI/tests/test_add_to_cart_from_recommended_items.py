import pytest

from pages.home_page import HomePage
from pages.cart_page import CartPage


@pytest.mark.recommended_items
def test_add_to_cart_from_recommended_items(page, base_url, report_steps):
    """
    Test Case 22: Add to cart from Recommended items
    
    Test Steps:
    1. Launch browser
    2. Navigate to url 'http://automationexercise.com'
    3. Scroll to bottom of page
    4. Verify 'RECOMMENDED ITEMS' are visible
    5. Click on 'Add To Cart' on Recommended product
    6. Click on 'View Cart' button
    7. Verify that product is displayed in cart page
    """

    # Initialize page objects
    home_page = HomePage(page)
    cart_page = CartPage(page)

    try:
        # Step 1: Launch browser (implicit in pytest fixture)
        report_steps.append("Step 1: Browser launched")
        print("Step 1: Browser launched")

        # Step 2: Navigate to url 'http://automationexercise.com'
        report_steps.append("Step 2: Navigating to Home Page")
        print("Step 2: Navigating to Home Page")
        home_page.goto(base_url)
        home_page.verify_home_page_loaded()

        # Step 3: Scroll to bottom of page
        report_steps.append("Step 3: Scrolling to bottom of page")
        print("Step 3: Scrolling to bottom of page")
        home_page.scroll_to_recommended_items()

        # Step 4: Verify 'RECOMMENDED ITEMS' are visible
        report_steps.append("Step 4: Verifying RECOMMENDED ITEMS are visible")
        print("Step 4: Verifying RECOMMENDED ITEMS are visible")
        home_page.verify_recommended_items_visible()
        recommended_count = home_page.get_recommended_items_count()
        assert recommended_count > 0, "No recommended items found"
        report_steps.append(f"   Found {recommended_count} recommended items")

        # Step 5: Click on 'Add To Cart' on Recommended product
        report_steps.append("Step 5: Clicking Add To Cart on first recommended item")
        print("Step 5: Clicking Add To Cart on first recommended item")
        home_page.click_add_to_cart_on_recommended_item(index=0)
        report_steps.append("   Product added to cart")

        # Step 6: Click on 'View Cart' button
        report_steps.append("Step 6: Clicking View Cart button")
        print("Step 6: Clicking View Cart button")
        home_page.click_cart_button()

        # Step 7: Verify that product is displayed in cart page
        report_steps.append("Step 7: Verifying product is displayed in cart page")
        print("Step 7: Verifying product is displayed in cart page")
        cart_page.verify_products_in_cart()

        # Test passed
        report_steps.append("✅ Test Passed: Product added from recommended items to cart successfully")
        print("\n✅ Test Passed: Product added from recommended items to cart successfully")

    except AssertionError as e:
        report_steps.append(f"❌ Test Failed: {str(e)}")
        print(f"\n❌ Test Failed: {str(e)}")
        raise

    except Exception as e:
        report_steps.append(f"❌ Test Error: {str(e)}")
        print(f"\n❌ Test Error: {str(e)}")
        raise
