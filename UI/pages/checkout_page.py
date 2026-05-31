from playwright.sync_api import expect
from pages.base_page import BasePage

class CheckoutPage(BasePage):
    def __init__(self, page):
        super().__init__(page)
        self.delivery_address_details = '.address_left'
        self.billing_address_details = '.address_right'
        self.review_order_products = '#cart_info'
        self.comment_textarea = '.form-control'
        self.place_order_button = '#submit'

    def verify_address_details(self, expected_delivery_address, expected_billing_address):
        expect(self.page.locator(self.delivery_address_details)).to_contain_text(expected_delivery_address)
        expect(self.page.locator(self.billing_address_details)).to_contain_text(expected_billing_address)

    def verify_review_order_products(self):
        expect(self.page.locator(self.review_order_products)).to_be_visible()

    def enter_comment_and_place_order(self, comment):
        self.fill(self.comment_textarea, comment)
        self.click(self.place_order_button)
