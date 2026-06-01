from playwright.sync_api import expect

from .base_page import BasePage


class ProductsPage(BasePage):
    """Page object for the All Products page"""

    # Locators
    # Scope to the navbar: on brand/category pages a bare a[href='/products']
    # also matches an in-page link, causing a strict-mode violation.
    products_button = ".shop-menu a[href='/products']"
    all_products_heading = "text=All Products"
    product_list = "div.productinfo"
    view_product_button = "a:has-text('View Product')"
    first_product_view_button = "a[href*='product_details']"
    
    # Search locators
    search_input = "input#search_product"
    search_button = "button#submit_search"
    searched_products_heading = "text=Searched Products"

    # Brand locators
    brands_sidebar = "div.left-sidebar"
    brands_section = "div.brands_products"
    brand_links = "div.brands_products a"

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

    def get_search_results_count(self):
        """Get the count of products in search results"""
        print("Getting search results count...")
        products = self.page.locator(self.product_list)
        count = products.count()
        print(f"Search results have {count} products")
        return count

    def add_search_result_to_cart(self, index: int = 0):
        """Click on a search result product and add it to cart"""
        print(f"Adding search result product {index} to cart...")
        products = self.page.locator(self.product_list)
        
        if products.count() <= index:
            raise IndexError(f"Product index {index} not found in search results")
        
        # Find the "Add to cart" button within the product card at this index
        product_card = products.nth(index)
        add_to_cart_button = product_card.locator("a:has-text('Add to cart')")
        
        expect(add_to_cart_button).to_be_visible(timeout=10000)
        add_to_cart_button.click()
        
        # Handle modal if it appears
        try:
            self.page.wait_for_timeout(1000)
            continue_button = self.page.locator("button:has-text('Continue Shopping')")
            if continue_button.is_visible(timeout=2000):
                continue_button.click()
                self.page.wait_for_load_state("domcontentloaded")
        except:
            pass
        
        print(f"Product {index} added to cart")

    def add_all_search_results_to_cart(self):
        """Add all search result products to cart"""
        print("Adding all search results to cart...")
        count = self.get_search_results_count()
        
        for i in range(count):
            print(f"Adding product {i + 1}/{count} to cart...")
            try:
                self.add_search_result_to_cart(index=i)
            except Exception as e:
                print(f"Warning: Could not add product {i} to cart: {e}")
        
        print(f"All {count} products added to cart")
        return count

    # -------- Brand Navigation Methods --------

    def verify_brands_visible(self):
        """Verify that brands section is visible on left sidebar"""
        print("Verifying brands section is visible...")
        self.expect_visible(self.brands_section)
        print("Brands section is visible")

    def get_brands_count(self):
        """Get the count of brands available"""
        print("Getting brands count...")
        brands = self.page.locator(self.brand_links)
        count = brands.count()
        print(f"Found {count} brands")
        return count

    def click_brand(self, index: int = 0):
        """Click on a brand by index"""
        print(f"Clicking brand at index {index}...")
        brands = self.page.locator(self.brand_links)
        
        if brands.count() <= index:
            raise IndexError(f"Brand index {index} not found. Only {brands.count()} brands available")
        
        brand_text = brands.nth(index).text_content()
        print(f"Clicking brand: {brand_text}")
        brands.nth(index).click()
        self.page.wait_for_load_state("domcontentloaded")
        print(f"Brand {index} clicked")

    def get_brand_name(self, index: int = 0):
        """Get brand name by index"""
        brands = self.page.locator(self.brand_links)
        if brands.count() <= index:
            return None
        return brands.nth(index).text_content().strip()
