from playwright.sync_api import expect

from .base_page import BasePage


class CartPage(BasePage):
    """Page object for the Cart page"""

    # Locators
    # cart_button = "a:has-text('Cart')"
    cart_page_heading = "text=Shopping Cart"

    # Subscription locators
    subscription_heading = "text=SUBSCRIPTION"
    subscription_email_input = "input#susbscribe_email"
    subscription_button = "button#subscribe"
    subscription_success_message = "text=You have been successfully subscribed!"

    # Page URL pattern
    cart_url_pattern = "view_cart"

    # -------- Navigation Methods --------

    def navigate_to_cart(self):
        print("Navigating to Cart page...")

        self.page.get_by_role("link",name="Cart").click()

        self.page.wait_for_load_state("domcontentloaded")

        print("Navigated to Cart page")

    def verify_cart_page_visible(self):
        """Verify that the Cart page is loaded"""
        print("Verifying Cart page loaded...")

        # Verify URL contains view_cart
        assert self.cart_url_pattern in self.page.url, (
            f"Expected URL to contain '{self.cart_url_pattern}', "
            f"but got: {self.page.url}"
        )

        # Verify cart page heading is visible
        self.expect_visible(self.cart_page_heading)
        print("Cart page loaded successfully")

    # -------- Subscription Methods --------

    def scroll_to_footer(self):
        print("Scrolling down to footer...")

        self.page.locator("text=SUBSCRIPTION").scroll_into_view_if_needed()

        expect(
            self.page.locator("text=SUBSCRIPTION")
        ).to_be_visible(timeout=10000)

        print("Scrolled to footer")

    def verify_subscription_heading_visible(self):
        """Verify that the SUBSCRIPTION heading is visible"""
        print("Verifying SUBSCRIPTION heading is visible...")
        self.expect_visible(self.subscription_heading)
        print("SUBSCRIPTION heading is visible")

    def subscribe_with_email(self, email):
        self.fill(self.subscription_email_input, email)
        self.click(self.subscription_button)

        expect(
            self.page.locator(".alert-success")
        ).to_be_visible(timeout=10000)

    def verify_subscription_success_message(self):
        """Verify that the subscription success message is visible"""
        print("Verifying subscription success message...")
        self.expect_visible(self.subscription_success_message, timeout=10000)
        print("Subscription success message is visible")
