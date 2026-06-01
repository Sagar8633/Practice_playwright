"""
Test Suite: View & Cart Brand Products
Application Under Test: https://automationexercise.com/

WHAT THIS FILE COVERS
    test_view_brand_products - a user navigates to the products page, views
                              brands available on the left sidebar, clicks on
                              different brands to view brand-specific products,
                              and verifies brand pages display correctly.

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - Navigation to products page via button click
    - Brand navigation using left sidebar brand links
    - Clicking on multiple brands and verifying page transitions
    - Verifying brand page headings and product lists
    - Brand-based URL pattern verification
    - Dynamic brand selection by index
    - Screenshots for evidence/debugging
    - report_steps entries are rendered into reports/report.html by conftest's
      pytest_runtest_makereport hook.

DESIGN NOTES
    - No login/registration required for this test
    - Tests the brand filtering and navigation functionality
    - All selectors and verifications live in page objects (pages/) for maintainability
    - Each step is logged in report_steps for clear test execution visibility
"""

import logging

import pytest

from pages.home_page import HomePage
from pages.products_page import ProductsPage
from pages.brand_page import BrandPage


@pytest.mark.data_driven
def test_view_brand_products(page, base_url, report_steps):
    """
    Objective : Navigate to products page, view brands on left sidebar, click on
                different brands, and verify brand pages display with correct
                products.
    Expected  : Brand pages load with correct headings and product lists visible.
    """
    # --- Arrange: build the page objects this test will drive ---------------
    home_page = HomePage(page)
    products_page = ProductsPage(page)
    brand_page = BrandPage(page)

    print("\n========== TEST STARTED: View & Cart Brand Products ==========")

    # ========== STEP 1-4: Launch Home & Navigate to Products ====================
    report_steps.append("1. Launch browser and navigate to https://automationexercise.com")
    logging.info("Opening home page")
    home_page.open(base_url)

    report_steps.append("2. Verify that home page is visible successfully")
    home_page.verify_home_is_visible()
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"
    logging.info("Home page verified")

    report_steps.append("3. Click 'Products' button to navigate to products page")
    logging.info("Navigating to products page")
    page.locator(products_page.products_button).click()
    page.wait_for_load_state("domcontentloaded")

    report_steps.append("4. Verify All Products page is loaded and brands are visible on left sidebar")
    logging.info("Verifying products page and brands sidebar")
    products_page.verify_all_products_page_visible()
    products_page.verify_brands_visible()

    # ========== STEP 5-6: Click First Brand & Verify ===========================
    # Get brand information
    brands_count = products_page.get_brands_count()
    assert brands_count > 0, "Should have at least one brand available"
    
    first_brand_name = products_page.get_brand_name(index=0)
    report_steps.append(f"5. Click on first brand '{first_brand_name}' - {brands_count} brands available")
    logging.info(f"Clicking first brand ({first_brand_name}), {brands_count} brands available")
    products_page.click_brand(index=0)

    report_steps.append(f"6. Verify that user is navigated to brand page and brand products are displayed")
    logging.info(f"Verifying brand page for {first_brand_name}")
    brand_page.verify_brand_page_visible()
    brand_page.verify_brand_heading_visible()
    first_brand_products_count = brand_page.verify_brand_products_displayed()
    logging.info(f"Brand page verified with {first_brand_products_count} products")

    # ========== STEP 7-8: Click Different Brand & Verify =======================
    report_steps.append("7. Navigate back to products and click on a different brand")
    logging.info("Navigating back to products page")
    
    # Navigate back to products page
    page.locator(products_page.products_button).click()
    page.wait_for_load_state("domcontentloaded")
    products_page.verify_all_products_page_visible()
    
    # Get a different brand (if available)
    second_brand_index = 1 if brands_count > 1 else 0
    second_brand_name = products_page.get_brand_name(index=second_brand_index)
    
    if brands_count > 1:
        report_steps.append(f"Clicking second brand '{second_brand_name}'")
        logging.info(f"Clicking second brand ({second_brand_name})")
        products_page.click_brand(index=second_brand_index)
    else:
        report_steps.append(f"Only one brand available, clicking same brand again '{second_brand_name}'")
        logging.info(f"Only one brand available, clicking brand again: {second_brand_name}")
        products_page.click_brand(index=0)

    report_steps.append("8. Verify that user is navigated to that brand page and can see products")
    logging.info(f"Verifying second brand page for {second_brand_name}")
    brand_page.verify_brand_page_visible()
    brand_page.verify_brand_heading_visible()
    second_brand_products_count = brand_page.verify_brand_products_displayed()
    logging.info(f"Second brand page verified with {second_brand_products_count} products")

    print("\n========== TEST COMPLETED SUCCESSFULLY ==========")
    logging.info("Test completed successfully - brand navigation verified")
