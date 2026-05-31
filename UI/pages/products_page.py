from playwright.sync_api import expect

from .base_page import BasePage


class ProductsPage(BasePage):
    """Page object for the All Products page"""

    # Locators
    products_button = "a[href='/products']"
    all_products_heading = "text=All Products"
    product_list = "div.productinfo"
    view_product_button = "a:has-text('View Product')"
    first_product_view_button = "a[href*='product_details']"
    
    # Search locators
    search_input = "input#search_product"
    search_button = "button#submit_search"
    searched_products_heading = "text=Searched Products"

    # Page URL pattern
    products_url_pattern = "products"

    # -------- Verification Methods --------

    def verify_all_products_page_visible(self):
        """Verify that the All Products page is loaded and visible"""
        print("Verifying All Products page loaded...")

        # Verify URL contains products
        assert self.products_url_pattern in self.page.url, (
            f"Expected URL to contain '{self.products_url_pattern}', "
            f"but got: {self.page.url}"
        )

        # Verify page heading is visible
        self.expect_visible(self.all_products_heading)
        print("All Products page loaded successfully")

    def verify_products_list_visible(self):
        """Verify that products list is visible on the page"""
        print("Verifying products list is visible...")
        
        products = self.page.locator(self.product_list)
        count = products.count()
        
        assert count > 0, "Expected products to be visible on the page"
        print(f"Found {count} products on the page")

    def click_first_product_view_button(self):
        print("Clicking View Product")

        first_button = self.page.locator(
            self.first_product_view_button
        ).first

        expect(first_button).to_be_visible(timeout=10000)

        first_button.scroll_into_view_if_needed()

        first_button.click()

        self.page.wait_for_load_state("domcontentloaded")

    def search_product(self, product_name: str):
        """Search for a product by name"""
        print(f"Searching for product: {product_name}")
        
        # Enter search term in search input
        self.fill(self.search_input, product_name)
        print(f"Entered product name: {product_name}")
        
        # Click search button
        self.click(self.search_button)
        
        # Wait for search results to load
        self.page.wait_for_load_state("domcontentloaded")
        print("Search completed")

    def verify_searched_products_page_visible(self):
        """Verify that the Searched Products page is displayed"""
        print("Verifying Searched Products page...")
        
        # Verify searched products heading is visible
        self.expect_visible(self.searched_products_heading)
        print("Searched Products page loaded successfully")

    def verify_search_results_visible(self):
        """Verify that search results are visible on the page"""
        print("Verifying search results are visible...")
        
        products = self.page.locator(self.product_list)
        count = products.count()
        
        assert count > 0, "Expected search results to be visible on the page"
        print(f"Found {count} products in search results")
