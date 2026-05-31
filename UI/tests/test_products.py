"""
Test Suite: All Products and Product Detail Page
Application Under Test: https://automationexercise.com/products

WHAT THIS FILE COVERS
    test_verify_all_products_and_product_detail - navigate to All Products page,
    verify products list is visible, click on first product's 'View Product' button,
    and verify product detail page with all details (name, category, price,
    availability, condition, brand).

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - Navigation to products page via button click
    - Verification of products list visibility
    - Clicking on specific product (first product)
    - Verification of product detail page and all product attributes
    - Screenshots are saved at key points for evidence/debugging
    - report_steps entries are surfaced in reports/report.html by conftest's
      pytest_runtest_makereport hook.
"""

import pytest

from pages.home_page import HomePage
from pages.products_page import ProductsPage
from pages.product_detail_page import ProductDetailPage


@pytest.mark.data_driven
def test_verify_all_products_and_product_detail(page, base_url, report_steps):
    """
    Objective : Navigate to All Products page, verify products list is visible,
                click on first product, and verify product detail page.
    Expected  : Product detail page loads with all details (name, category, price,
                availability, condition, brand) visible.
    """
    # --- Arrange ----------------------------------------------------------
    home_page = HomePage(page)
    products_page = ProductsPage(page)
    product_detail_page = ProductDetailPage(page)

    print("\n========== TEST STARTED ==========")

    # --- Act: Open home page -----------------------------------------------
    report_steps.append("1. Open the home page and confirm it loaded")
    home_page.open(base_url)
    home_page.verify_home_is_visible()
    # Match on domain only: base_url is http:// but the site redirects to https.
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"
    page.screenshot(path="01_home_page.png", full_page=True)

    # --- Act: Navigate to products page ------------------------------------
    report_steps.append("2. Click 'Products' button to navigate")
    page.locator(products_page.products_button).click()
    page.wait_for_load_state("domcontentloaded")
    page.screenshot(path="02_all_products_page.png", full_page=True)

    # --- Assert: Verify All Products page loaded ---------------------------
    report_steps.append("3. Verify navigation to all products page was successful")
    products_page.verify_all_products_page_visible()

    report_steps.append("4. Verify products list is visible")
    products_page.verify_products_list_visible()

    # --- Act: Click on first product view button ----------------------------
    report_steps.append("5. Click 'View Product' button of first product")
    products_page.click_first_product_view_button()
    page.screenshot(path="03_product_detail_page.png", full_page=True)

    # --- Assert: Verify Product Detail page loaded -------------------------
    report_steps.append("6. Verify user is landed on product detail page")
    product_detail_page.verify_product_detail_page_visible()

    report_steps.append("7. Verify all product details are visible")
    product_detail_page.verify_product_details_visible()

    # Log product information
    product_name = product_detail_page.get_product_name()
    product_price = product_detail_page.get_product_price()
    print(f"\nProduct Details:")
    print(f"  Name: {product_name}")
    print(f"  Price: {product_price}")

    print("\n========== TEST COMPLETED SUCCESSFULLY ==========")
