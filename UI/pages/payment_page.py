from playwright.sync_api import expect
from pages.base_page import BasePage

class PaymentPage(BasePage):
    def __init__(self, page):
        super().__init__(page)
        self.name_on_card_input = '[name="name_on_card"]';
        self.card_number_input = '[name="card_number"]';
        self.cvc_input = '[name="cvc"]';
        self.expiry_month_input = '[name="expiry_month"]';
        self.expiry_year_input = '[name="expiry_year"]';
        self.pay_and_confirm_button = '#submit';
        self.success_message = '#success_message';

    def enter_payment_details(self, name_on_card, card_number, cvc, expiry_month, expiry_year):
        self.fill(self.name_on_card_input, name_on_card)
        self.fill(self.card_number_input, card_number)
        self.fill(self.cvc_input, cvc)
        self.fill(self.expiry_month_input, expiry_month)
        self.fill(self.expiry_year_input, expiry_year)

    def pay_and_confirm_order(self):
        self.click(self.pay_and_confirm_button)

    def verify_success_message(self, message):
        expect(self.page.locator(self.success_message)).to_have_text(message)
