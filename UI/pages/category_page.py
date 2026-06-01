from playwright.sync_api import expect
from .base_page import BasePage


class CategoryPage(BasePage):
    """Page object for the Category Products page"""

    # Locators
    # h2.title is the products heading (e.g. "Women - Dress Products"); a bare
    # "h2" also matches the left-sidebar "Category"/"Brands" panel headings.
    category_heading = "h2.title"
    product_list = "div.productinfo"
    
    # Page URL pattern
    category_url_pattern = "category_products"

    # -------- Verification Methods --------

    def verify_category_page_visible(self):
        """Verify that the category page is loaded"""
        print("Verifying category page loaded...")

        # Verify URL contains category_products
        assert self.category_url_pattern in self.page.url, (
            f"Expected URL to contain '{self.category_url_pattern}', "
            f"but got: {self.page.url}"
        )

        print("Category page loaded successfully")

    def verify_category_heading_contains(self, expected_text: str):
        """Verify that the category heading contains the expected text"""
        print(f"Verifying category heading contains '{expected_text}'...")
        
        heading = self.page.locator(self.category_heading).first
        # ignore_case: the heading renders as title-case "Women - Dress Products"
        # (the all-caps look is CSS text-transform), but tests pass "WOMEN"/"MEN".
        expect(heading).to_contain_text(expected_text, ignore_case=True, timeout=10000)

        actual_text = heading.text_content()
        print(f"Category heading verified: {actual_text}")

    def verify_category_heading(self, expected_text: str):
        """Verify the exact category heading text"""
        print(f"Verifying category heading is '{expected_text}'...")
        
        heading = self.page.locator(self.category_heading).first
        expect(heading).to_have_text(expected_text, timeout=10000)
        
        actual_text = heading.text_content()
        print(f"Category heading verified: {actual_text}")

    def verify_products_list_visible(self):
        """Verify that products list is visible on the category page"""
        print("Verifying products list is visible...")
        
        products = self.page.locator(self.product_list)
        count = products.count()
        
        assert count > 0, "Expected products to be visible on the category page"
        print(f"Found {count} products on the category page")

    def get_products_count(self):
        """Get the count of products on the category page"""
        products = self.page.locator(self.product_list)
        count = products.count()
        return count
