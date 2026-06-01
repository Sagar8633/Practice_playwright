from playwright.sync_api import expect
from .base_page import BasePage


class BrandPage(BasePage):
    """Page object for the Brand Products page"""

    # Locators
    # h2.title is the products heading (e.g. "Brand - Polo Products"); a bare
    # "h2" also matches the left-sidebar "Category"/"Brands" panel headings.
    brand_heading = "h2.title"
    product_list = "div.productinfo"
    
    # Page URL pattern
    brand_url_pattern = "brand_products"

    # -------- Verification Methods --------

    def verify_brand_page_visible(self):
        """Verify that the brand page is loaded"""
        print("Verifying brand page loaded...")

        # Verify URL contains brand_products
        assert self.brand_url_pattern in self.page.url, (
            f"Expected URL to contain '{self.brand_url_pattern}', "
            f"but got: {self.page.url}"
        )

        print("Brand page loaded successfully")

    def verify_brand_products_displayed(self):
        """Verify that brand products are displayed on the page"""
        print("Verifying brand products are displayed...")
        
        products = self.page.locator(self.product_list)
        count = products.count()
        
        assert count > 0, "Expected brand products to be visible on the page"
        print(f"Found {count} products for this brand")
        return count

    def verify_brand_heading_visible(self):
        """Verify that brand heading is visible"""
        print("Verifying brand heading is visible...")
        
        heading = self.page.locator(self.brand_heading).first
        expect(heading).to_be_visible(timeout=10000)
        
        actual_text = heading.text_content()
        print(f"Brand heading verified: {actual_text}")

    def verify_brand_heading_contains(self, expected_text: str):
        """Verify that the brand heading contains the expected text"""
        print(f"Verifying brand heading contains '{expected_text}'...")
        
        heading = self.page.locator(self.brand_heading).first
        expect(heading).to_contain_text(expected_text, ignore_case=True, timeout=10000)

        actual_text = heading.text_content()
        print(f"Brand heading verified: {actual_text}")

    def get_products_count(self):
        """Get the count of products on the brand page"""
        products = self.page.locator(self.product_list)
        count = products.count()
        return count
