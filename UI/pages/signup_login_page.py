from .base_page import BasePage


class SignupLoginPage(BasePage):
    new_user_signup_label = "xpath=//h2[text()='New User Signup!']"
    signup_name_field = "input[data-qa='signup-name']"
    signup_email_field = "input[data-qa='signup-email']"
    signup_button = "button[data-qa='signup-button']"
    # Use contains() rather than an exact text match so stray whitespace/markup
    # in the rendered banner doesn't break the assertion.
    signup_error_message = "xpath=//p[contains(., 'already exist')]"

    login_title = "xpath=//h2[text()='Login to your account']"
    login_email_field = "input[data-qa='login-email']"
    login_password_field = "input[data-qa='login-password']"
    login_button = "button[data-qa='login-button']"
    login_error_message = "xpath=//p[contains(., 'email or password is incorrect')]"

    def verify_new_user_signup_visible(self):
        self.expect_visible(self.new_user_signup_label)

    def enter_signup_name_and_email(self, name: str, email: str):
        self.fill(self.signup_name_field, name)
        self.fill(self.signup_email_field, email)

    def click_signup(self):
        self.click(self.signup_button)
        # Signup triggers a full server round-trip; wait for the response page
        # so the next assertion (success or "already exist" error) is reliable.
        self.page.wait_for_load_state("domcontentloaded")

    def verify_login_to_your_account_visible(self):
        self.expect_visible(self.login_title)

    def enter_login_credentials(self, email: str, password: str):
        self.fill(self.login_email_field, email)
        self.fill(self.login_password_field, password)

    def click_login(self):
        self.click(self.login_button)

    def verify_signup_error_visible(self):
        # Longer timeout: the error renders after a server round-trip.
        self.expect_visible(self.signup_error_message, timeout=15000)

    def verify_login_error_visible(self):
        # Longer timeout: the error renders after a server round-trip.
        self.expect_visible(self.login_error_message, timeout=15000)
