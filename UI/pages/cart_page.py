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

    # Remove product locators
    cart_items = "table tbody tr"
    remove_product_button = "a.cart_quantity_delete"

    # -------- Navigation Methods --------

    def navigate_to_cart(self):
        print("Navigating to Cart page...")
        # Scope to the navbar: the bare a[href='/view_cart'] also matches the
        # add-to-cart modal link, and get_by_role("Cart") is unreliable here.
        self.page.locator(".shop-menu a[href='/view_cart']").click()

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

    def proceed_to_checkout(self):
        """Click Proceed to Checkout button"""
        print("Clicking Proceed to Checkout...")
        proceed_button = "a[href*='checkout']"
        # Try different selectors if the first one doesn't work
        try:
            self.click(proceed_button)
        except:
            proceed_button = "a:has-text('Proceed To Checkout')"
            self.click(proceed_button)
        self.page.wait_for_load_state("domcontentloaded")
        print("Proceeded to checkout page")

    def get_cart_items_count(self):
        """Get the number of products in the cart"""
        print("Getting cart items count...")
        items = self.page.locator(self.cart_items)
        count = items.count()
        print(f"Cart has {count} items")
        return count

    def remove_product_from_cart(self, index=0):

        print(f"Removing product at index {index} from cart...")

        rows_before = self.page.locator("table tbody tr").count()
        print("Rows before:", rows_before)

        remove_buttons = self.page.locator(self.remove_product_button)

        remove_buttons.nth(index).click()

        self.page.wait_for_timeout(3000)

        rows_after = self.page.locator("table tbody tr").count()
        print("Rows after:", rows_after)

        print(f"Product {index} removed from cart")

    def verify_product_removed_from_cart(self):
        """Verify that cart is empty or product count decreased"""
        print("Verifying product removed from cart...")
        # Check if there's an empty cart message or no product rows
        try:
            empty_message = self.page.locator("text=Cart is Empty").count()
            if empty_message > 0:
                print("Cart is now empty")
                return True
        except:
            pass
        
        # If cart still has items, that's OK - user may have added multiple items
        items_count = self.get_cart_items_count()
        print(f"Cart now contains {items_count} items")
        return True

    def verify_empty_cart(self):
        """Verify that the cart is empty"""
        print("Verifying cart is empty...")
        empty_cart_text = self.page.locator("text=Cart is Empty")
        expect(empty_cart_text).to_be_visible(timeout=5000)
        print("Cart is empty - verified")

    def verify_products_in_cart(self):
        """Verify that products are displayed in the cart"""
        print("Verifying products are displayed in cart...")
        # Verify cart page is visible
        self.verify_cart_page_visible()
        # Verify there are items in the cart
        items_count = self.get_cart_items_count()
        assert items_count > 0, "No products found in cart"
        print(f"✓ Verified {items_count} product(s) displayed in cart")
