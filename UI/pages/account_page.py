from .base_page import BasePage


class AccountPage(BasePage):
    logged_in_as_label = "xpath=//a[contains(text(),'Logged in as')]"
    delete_account_button = "a[href='/delete_account']"
    logout_button = "a[href='/logout']"
    account_deleted_label = "xpath=//b[text()='Account Deleted!']"
    continue_button = "a[data-qa='continue-button']"

    def verify_logged_in_as(self, name: str):
        self.expect_text_contains(self.logged_in_as_label, name)

    def click_delete_account(self):
        self.click(self.delete_account_button)

    def click_logout(self):
        # CHANGED: Use click_and_wait_for_navigation instead of regular click to handle logout navigation properly
        self.click_and_wait_for_navigation(self.logout_button)

    def verify_account_deleted_visible(self):
        self.expect_visible(self.account_deleted_label)

    def click_continue(self):
        self.click(self.continue_button)
