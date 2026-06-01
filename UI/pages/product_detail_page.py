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

    # Review section locators
    # "Write Your Review" is rendered as an <a> tab toggle, not an <h3>.
    review_section = "div.row:has(a:has-text('Write Your Review'))"
    review_heading = "a:has-text('Write Your Review')"
    # The name/email fields have an id but no name attribute on this site.
    review_name_input = "#name"
    review_email_input = "#email"
    review_textarea = "textarea[name='review']"
    review_submit_button = "button#button-review"
    # Scope by text: there is a second .alert-success div for the newsletter.
    review_success_message = "div.alert-success:has-text('Thank you for your review')"

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

    def add_to_cart(self):
        print("Adding product to cart...")

        add_btn = self.page.locator("button:has-text('Add to cart')")
        expect(add_btn).to_be_visible(timeout=10000)

        add_btn.click()

        self.page.locator("#cartModal").wait_for(state="visible",timeout=10000)
        self.page.get_by_role("link",name="View Cart").click()

        print("Product successfully added to cart")

    # -------- Review Methods --------

    def verify_review_section_visible(self):
        """Verify that 'Write Your Review' section is visible"""
        print("Verifying 'Write Your Review' section is visible...")
        self.expect_visible(self.review_heading, timeout=10000)
        print("'Write Your Review' section is visible")

    def enter_review_name(self, name: str):
        """Enter name in the review form"""
        print(f"Entering review name: {name}")
        self.fill(self.review_name_input, name)
        print(f"Review name entered: {name}")

    def enter_review_email(self, email: str):
        """Enter email in the review form"""
        print(f"Entering review email: {email}")
        self.fill(self.review_email_input, email)
        print(f"Review email entered: {email}")

    def enter_review_text(self, review_text: str):
        """Enter review text/message in the review form"""
        print(f"Entering review text...")
        self.fill(self.review_textarea, review_text)
        print(f"Review text entered")

    def click_submit_review(self):
        """Click the Submit Review button"""
        print("Clicking Submit review button...")
        self.click(self.review_submit_button)
        # Wait for page to process
        self.page.wait_for_load_state("domcontentloaded")
        print("Submit review button clicked")

    def verify_review_success_message(self):
        """Verify success message 'Thank you for your review.' is displayed"""
        print("Verifying review success message...")
        # Wait for success message to be visible
        self.expect_visible(self.review_success_message, timeout=10000)
        # Verify the message contains the expected text
        success_message = self.page.locator(self.review_success_message).inner_text()
        assert "Thank you for your review" in success_message, (
            f"Expected success message to contain 'Thank you for your review', "
            f"but got: {success_message}"
        )
        print(f"Review success message verified: {success_message}")
