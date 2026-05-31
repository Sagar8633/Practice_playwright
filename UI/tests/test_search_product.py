"""
Test Suite: Search Product
Application Under Test: https://automationexercise.com/products

WHAT THIS FILE COVERS
    test_search_product - navigate to All Products page, search for a product by name,
    verify the searched products page is visible, and verify search results are displayed.

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - Navigation to products page via button click
    - Search functionality: entering product name in search input and clicking search button
    - Verification of searched products page heading
    - Verification of search results visibility
    - Screenshots are saved at key points for evidence/debugging
    - report_steps entries are surfaced in reports/report.html by conftest's
      pytest_runtest_makereport hook.
    - Data-driven test: search products are parametrized from YAML
"""

import pytest

from pages.home_page import HomePage
from pages.products_page import ProductsPage


@pytest.mark.data_driven
def test_search_product(page, base_url, search_product, report_steps):
    """
    Objective : Search for a product by name and verify search results are displayed.
    Data      : search_product (product_name) from YAML.
    Expected  : 'SEARCHED PRODUCTS' heading is visible and search results are displayed.
    """
    # --- Arrange ----------------------------------------------------------
    home_page = HomePage(page)
    products_page = ProductsPage(page)

    print("\n========== TEST STARTED ==========")

    # --- Act: Open home page -----------------------------------------------
    report_steps.append("1. Open the home page and confirm it loaded")
    home_page.open(base_url)
    home_page.verify_home_is_visible()
    # Match on domain only: base_url is http:// but the site redirects to https.
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"
    # page.screenshot(path="01_home_page.png", full_page=True)

    # --- Act: Navigate to products page ------------------------------------
    report_steps.append("2. Click 'Products' button to navigate")
    page.locator(products_page.products_button).click()
    page.wait_for_load_state("domcontentloaded")
    # page.screenshot(path="02_all_products_page.png", full_page=True)

    # --- Assert: Verify All Products page loaded ---------------------------
    report_steps.append("3. Verify navigation to all products page was successful")
    products_page.verify_all_products_page_visible()

    # --- Act: Search for product -------------------------------------------
    report_steps.append(f"4. Enter '{search_product['product_name']}' in search and click search button")
    products_page.search_product(search_product["product_name"])
    # page.screenshot(path="03_search_results_page.png", full_page=True)

    # --- Assert: Verify Searched Products page loaded ----------------------
    report_steps.append("5. Verify 'SEARCHED PRODUCTS' heading is visible")
    products_page.verify_searched_products_page_visible()

    report_steps.append("6. Verify search results are visible")
    products_page.verify_search_results_visible()

    print("\n========== TEST COMPLETED SUCCESSFULLY ==========")
