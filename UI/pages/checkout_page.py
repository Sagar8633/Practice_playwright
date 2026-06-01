from playwright.sync_api import expect
from pages.base_page import BasePage

class CheckoutPage(BasePage):
    def __init__(self, page):
        super().__init__(page)
        self.delivery_address_details = '#address_delivery'
        self.billing_address_details = '#address_invoice'
        self.review_order_products = '#cart_info'
        # The comment box is textarea[name='message']; a bare .form-control also
        # matches the footer subscription input (strict-mode violation).
        self.comment_textarea = "textarea[name='message']"
        # 'Place Order' is an <a class="check_out" href="/payment">, not #submit.
        self.place_order_button = 'a.check_out'
        # Additional locators for detailed verification
        self.delivery_heading = "#address_delivery h3"
        self.billing_heading = "#address_invoice h3"

    def verify_address_details(self, expected_delivery_address, expected_billing_address):
        expect(self.page.locator(self.delivery_address_details)).to_contain_text(expected_delivery_address)
        expect(self.page.locator(self.billing_address_details)).to_contain_text(expected_billing_address)

    def verify_review_order_products(self):
        expect(self.page.locator(self.review_order_products)).to_be_visible()

    def enter_comment_and_place_order(self, comment):
        self.fill(self.comment_textarea, comment)
        self.click(self.place_order_button)

    def verify_checkout_page_visible(self):
        """Verify checkout page is loaded with address and review sections"""
        expect(self.page.locator(self.delivery_address_details)).to_be_visible()
        expect(self.page.locator(self.billing_address_details)).to_be_visible()
        print("Checkout page verified with address details visible")

    # -------- Address Verification Methods --------

    def get_delivery_address_text(self):
        """Get the delivery address text from the checkout page"""
        print("Getting delivery address text...")
        address_text = self.page.locator(self.delivery_address_details).inner_text()
        print(f"Delivery address: {address_text}")
        return address_text

    def get_billing_address_text(self):
        """Get the billing address text from the checkout page"""
        print("Getting billing address text...")
        address_text = self.page.locator(self.billing_address_details).inner_text()
        print(f"Billing address: {address_text}")
        return address_text

    def verify_delivery_address_contains(self, *fields):
        """Verify delivery address contains all specified fields
        
        Args:
            *fields: Variable number of strings that should be in delivery address
                    (e.g., first_name, last_name, address1, city, state, zipcode)
        """
        print("Verifying delivery address details...")
        delivery_address = self.get_delivery_address_text()
        
        for field in fields:
            assert str(field) in delivery_address, (
                f"Delivery address missing '{field}'. Address text: {delivery_address}"
            )
        print("✓ All delivery address details verified")

    def verify_billing_address_contains(self, *fields):
        """Verify billing address contains all specified fields
        
        Args:
            *fields: Variable number of strings that should be in billing address
                    (e.g., first_name, last_name, address1, city, state, zipcode)
        """
        print("Verifying billing address details...")
        billing_address = self.get_billing_address_text()
        
        for field in fields:
            assert str(field) in billing_address, (
                f"Billing address missing '{field}'. Address text: {billing_address}"
            )
        print("✓ All billing address details verified")
