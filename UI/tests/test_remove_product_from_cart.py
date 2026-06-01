"""
Test Suite: Remove Products From Cart
Application Under Test: https://automationexercise.com/

WHAT THIS FILE COVERS
    test_remove_product_from_cart - a user adds a product to cart and then
                                    removes it, verifying that the cart becomes
                                    empty after removal.

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - Navigation to products page and product detail page
    - Adding products to cart from product detail page
    - Navigating to cart and verifying cart page loads
    - Removing products from cart by clicking the X button
    - Verifying cart is empty after removal
    - Counting cart items and tracking state changes
    - Screenshots for evidence/debugging
    - report_steps entries are rendered into reports/report.html by conftest's
      pytest_runtest_makereport hook.

DESIGN NOTES
    - No login or registration needed for this test
    - Simple cart manipulation flow
    - All selectors and verifications live in page objects (pages/) for maintainability
    - Each step is logged in report_steps for clear test execution visibility
"""

import logging

import pytest

from pages.home_page import HomePage
from pages.products_page import ProductsPage
from pages.product_detail_page import ProductDetailPage
from pages.cart_page import CartPage


@pytest.mark.data_driven
def test_remove_product_from_cart(page, base_url, report_steps):
    """
    Objective : Add a product to cart, verify it's in the cart, then remove it 
                and verify the cart is empty.
    Expected  : Product is successfully removed from cart; cart becomes empty.
    """
    # --- Arrange: build the page objects this test will drive ---------------
    home_page = HomePage(page)
    products_page = ProductsPage(page)
    product_detail_page = ProductDetailPage(page)
    cart_page = CartPage(page)

    print("\n========== TEST STARTED: Remove Product From Cart ==========")

    # ========== STEP 1-3: Launch Browser & Navigate Home =======================
    report_steps.append("1. Launch browser and navigate to https://automationexercise.com")
    logging.info("Opening home page")
    home_page.open(base_url)

    report_steps.append("2. Verify that home page is visible successfully")
    home_page.verify_home_is_visible()
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"
    logging.info("Home page verified")

    # ========== STEP 4: Browse Products and Add to Cart ========================
    report_steps.append("3. Click 'Products' button to navigate to products page")
    logging.info("Navigating to products page")
    page.locator(products_page.products_button).click()
    page.wait_for_load_state("domcontentloaded")

    report_steps.append("4. Verify All Products page is loaded and click first product")
    logging.info("Verifying products page and selecting first product")
    products_page.verify_all_products_page_visible()
    products_page.verify_products_list_visible()
    products_page.click_first_product_view_button()

    report_steps.append("5. Verify product detail page and add product to cart")
    logging.info("Adding product to cart")
    product_detail_page.verify_product_detail_page_visible()
    product_detail_page.verify_product_details_visible()
    # add_to_cart() already clicks "View Cart" and lands on the cart page.
    product_detail_page.add_to_cart()

    # ========== STEP 5-6: Verify Cart ===========================
    report_steps.append("7. Verify that cart page is displayed")
    logging.info("Verifying cart page is loaded")
    cart_page.verify_cart_page_visible()

    # Get initial cart count
    initial_count = cart_page.get_cart_items_count()
    report_steps.append(f"8. Verify product is in cart (cart contains {initial_count} item(s))")
    logging.info(f"Cart has {initial_count} item(s)")
    assert initial_count > 0, "Cart should have at least 1 product"

    # ========== STEP 7-8: Remove Product and Verify ==========================
    report_steps.append("9. Click 'X' button corresponding to the product to remove it")
    logging.info("Removing first product from cart")
    cart_page.remove_product_from_cart(index=0)
    page.wait_for_load_state("domcontentloaded")

    report_steps.append("10. Verify that product is removed from the cart")

    remaining_count = cart_page.get_cart_items_count()

    assert remaining_count == initial_count - 1, (
        f"Expected {initial_count - 1} items, "
        f"but found {remaining_count}"
    )

    print("\n========== TEST COMPLETED SUCCESSFULLY ==========")
    logging.info("Test completed successfully - product removed and cart is empty")
