"""
Test Suite: View Category Products
Application Under Test: https://automationexercise.com/

WHAT THIS FILE COVERS
    test_view_category_products - a user navigates through product categories
                                 using the left sidebar, views sub-category
                                 products, and verifies category headings.

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - Navigation using the left sidebar category menu
    - Expanding/collapsing category sections
    - Clicking on sub-categories to filter products
    - Verifying category page headings and product lists
    - Category-based URL pattern verification
    - Multiple category navigation (Women → Men)
    - Screenshots for evidence/debugging
    - report_steps entries are rendered into reports/report.html by conftest's
      pytest_runtest_makereport hook.

DESIGN NOTES
    - No login/registration required for this test
    - Tests the category navigation and filtering functionality
    - All selectors and verifications live in page objects (pages/) for maintainability
    - Each step is logged in report_steps for clear test execution visibility
"""

import logging

import pytest

from pages.home_page import HomePage
from pages.category_page import CategoryPage


@pytest.mark.data_driven
def test_view_category_products(page, base_url, report_steps):
    """
    Objective : Navigate through product categories (Women & Men) using the 
                left sidebar and verify category pages display correctly.
    Expected  : Category pages load with correct headings and product lists visible.
    """
    # --- Arrange: build the page objects this test will drive ---------------
    home_page = HomePage(page)
    category_page = CategoryPage(page)

    print("\n========== TEST STARTED: View Category Products ==========")

    # ========== STEP 1-3: Launch Browser & Verify Categories ==================
    report_steps.append("1. Launch browser and navigate to https://automationexercise.com")
    logging.info("Opening home page")
    home_page.open(base_url)

    report_steps.append("2. Verify that home page is visible successfully")
    home_page.verify_home_is_visible()
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"
    logging.info("Home page verified")

    report_steps.append("3. Verify that categories are visible on left side bar")
    logging.info("Verifying categories sidebar")
    home_page.verify_categories_visible()

    # ========== STEP 4-6: Click Women Category & Sub-category ================
    report_steps.append("4. Click on 'Women' category to expand it")
    logging.info("Expanding Women category")
    home_page.click_women_category()

    # Get count of Women sub-categories for verification
    women_subcats_count = home_page.get_women_subcategories_count()
    report_steps.append(f"5. Click on first Women sub-category (Dress) - {women_subcats_count} sub-categories available")
    logging.info(f"Clicking first Women sub-category (Women has {women_subcats_count} sub-categories)")
    assert women_subcats_count > 0, "Women category should have at least one sub-category"
    home_page.click_women_subcategory(index=0)

    report_steps.append("6. Verify that category page is displayed with 'WOMEN' heading and products visible")
    logging.info("Verifying category page content")
    category_page.verify_category_page_visible()
    # The heading should contain "WOMEN" - the exact format varies but should have WOMEN in it
    category_page.verify_category_heading_contains("WOMEN")
    category_page.verify_products_list_visible()
    products_count = category_page.get_products_count()
    logging.info(f"Category page verified with {products_count} products")

    # ========== STEP 7-8: Click Men Category & Sub-category =================
    report_steps.append("7. On left side bar, click on a Men sub-category")
    logging.info("Navigating to Men category")
    
    # Scroll back up or reload to ensure categories are visible
    page.wait_for_load_state("domcontentloaded")
    home_page.verify_categories_visible()
    
    # Expand Men category if needed
    try:
        home_page.click_men_category()
        men_subcats_count = home_page.get_men_subcategories_count()
        logging.info(f"Men category has {men_subcats_count} sub-categories")
        assert men_subcats_count > 0, "Men category should have at least one sub-category"
    except Exception as e:
        logging.warning(f"Could not expand Men category, trying to click sub-category directly: {e}")
        men_subcats_count = home_page.get_men_subcategories_count()
        if men_subcats_count == 0:
            # Try expanding Men category
            home_page.click_men_category()
            men_subcats_count = home_page.get_men_subcategories_count()

    # Click first Men sub-category
    home_page.click_men_subcategory(index=0)

    report_steps.append("8. Verify that user is navigated to Men category page")
    logging.info("Verifying Men category page")
    category_page.verify_category_page_visible()
    category_page.verify_category_heading_contains("MEN")
    category_page.verify_products_list_visible()
    men_products_count = category_page.get_products_count()
    logging.info(f"Men category page verified with {men_products_count} products")

    print("\n========== TEST COMPLETED SUCCESSFULLY ==========")
    logging.info("Test completed successfully - both Women and Men categories navigated")
