from .base_page import BasePage


class AccountCreatedPage(BasePage):
    account_created_label = "xpath=//b[text()='Account Created!']"
    continue_button = "a[data-qa='continue-button']"

    def verify_account_created_visible(self):
        self.expect_visible(self.account_created_label)

    def click_continue(self):
        self.click(self.continue_button)
