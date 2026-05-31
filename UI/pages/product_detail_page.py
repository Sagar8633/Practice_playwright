from playwright.sync_api import expect

from .base_page import BasePage


class ProductDetailPage(BasePage):
    """Page object for the Product Detail page"""

    # Locators
    product_name = "div.product-information h2"
    product_category = "p:has-text('Category')"
    product_price = "div.product-information span span"
    product_availability = "p:has-text('Availability')"
    product_condition = "p:has-text('Condition')"
    product_brand = "p:has-text('Brand')"

    # Page URL pattern
    product_detail_url_pattern = "product"

    # -------- Verification Methods --------

    def verify_product_detail_page_visible(self):
        """Verify that the Product Detail page is loaded"""
        print("Verifying Product Detail page loaded...")

        # Verify URL contains product
        assert self.product_detail_url_pattern in self.page.url, (
            f"Expected URL to contain '{self.product_detail_url_pattern}', "
            f"but got: {self.page.url}"
        )

        print("Product Detail page loaded successfully")

    def verify_product_details_visible(self):
        """Verify all product details are visible: name, category, price, availability, condition, brand"""
        print("Verifying all product details are visible...")

        # Verify product name is visible
        print("Checking product name...")
        self.expect_visible(self.product_name, timeout=10000)

        # Verify product price is visible
        print("Checking product price...")
        self.expect_visible(self.product_price, timeout=10000)

        # Verify product availability is visible
        print("Checking product availability...")
        self.expect_visible(self.product_availability, timeout=10000)

        # Verify product condition is visible
        print("Checking product condition...")
        self.expect_visible(self.product_condition, timeout=10000)

        # Verify product brand is visible
        print("Checking product brand...")
        self.expect_visible(self.product_brand, timeout=10000)

        # Verify product category is visible
        print("Checking product category...")
        self.expect_visible(self.product_category, timeout=10000)

        print("All product details are visible successfully")

    def get_product_name(self):
        """Get the product name"""
        return self.page.locator(self.product_name).inner_text()

    def get_product_price(self):
        """Get the product price"""
        return self.page.locator(self.product_price).inner_text()
