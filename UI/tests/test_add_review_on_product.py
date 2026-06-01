import pytest

from pages.home_page import HomePage
from pages.products_page import ProductsPage
from pages.product_detail_page import ProductDetailPage


@pytest.mark.review
def test_add_review_on_product(page, base_url, report_steps):
    """
    Test Case 21: Add Review on Product
    
    Test Steps:
    1. Launch browser
    2. Navigate to automationexercise.com
    3. Click on 'Products' button
    4. Verify user is navigated to ALL PRODUCTS page
    5. Click on 'View Product' button
    6. Verify 'Write Your Review' is visible
    7. Enter name, email and review
    8. Click 'Submit' button
    9. Verify success message 'Thank you for your review.'
    """

    # Initialize page objects
    home_page = HomePage(page)
    products_page = ProductsPage(page)
    product_detail_page = ProductDetailPage(page)

    # Test data for review
    review_name = "Test User Review"
    review_email = "testreview@example.com"
    review_text = "This is an excellent product! Great quality and fast delivery. Highly recommended!"

    try:
        # Step 1: Launch browser (implicit in pytest fixture)
        report_steps.append("Step 1: Browser launched")
        print("Step 1: Browser launched")

        # Step 2: Navigate to url 'http://automationexercise.com'
        report_steps.append("Step 2: Navigating to Home Page")
        print("Step 2: Navigating to Home Page")
        home_page.goto(base_url)
        home_page.verify_home_page_loaded()

        # Step 3: Click on 'Products' button
        report_steps.append("Step 3: Clicking on Products button")
        print("Step 3: Clicking on Products button")
        home_page.click_products_button()

        # Step 4: Verify user is navigated to ALL PRODUCTS page successfully
        report_steps.append("Step 4: Verifying ALL PRODUCTS page is visible")
        print("Step 4: Verifying ALL PRODUCTS page is visible")
        products_page.verify_all_products_page_visible()
        products_page.verify_products_list_visible()

        # Step 5: Click on 'View Product' button (first product)
        report_steps.append("Step 5: Clicking on View Product button")
        print("Step 5: Clicking on View Product button")
        products_page.click_first_product_view_button()

        # Step 6: Verify 'Write Your Review' is visible
        report_steps.append("Step 6: Verifying Write Your Review section is visible")
        print("Step 6: Verifying Write Your Review section is visible")
        product_detail_page.verify_review_section_visible()

        # Step 7: Enter name, email and review
        report_steps.append("Step 7: Entering review details (name, email, review text)")
        print("Step 7: Entering review details")
        product_detail_page.enter_review_name(review_name)
        product_detail_page.enter_review_email(review_email)
        product_detail_page.enter_review_text(review_text)

        # Step 8: Click 'Submit' button
        report_steps.append("Step 8: Clicking Submit review button")
        print("Step 8: Clicking Submit review button")
        product_detail_page.click_submit_review()

        # Step 9: Verify success message 'Thank you for your review.'
        report_steps.append("Step 9: Verifying success message 'Thank you for your review.'")
        print("Step 9: Verifying success message")
        product_detail_page.verify_review_success_message()

        # Test passed
        report_steps.append("✅ Test Passed: Review submitted successfully")
        print("\n✅ Test Passed: Review submitted successfully")

    except AssertionError as e:
        report_steps.append(f"❌ Test Failed: {str(e)}")
        print(f"\n❌ Test Failed: {str(e)}")
        raise

    except Exception as e:
        report_steps.append(f"❌ Test Error: {str(e)}")
        print(f"\n❌ Test Error: {str(e)}")
        raise
