from playwright.sync_api import expect

from .base_page import BasePage


class ContactUsPage(BasePage):
    # Locators
    contact_us_button = "a[href='/contact_us']"

    get_in_touch_label = "text=GET IN TOUCH"

    name_field = "input[data-qa='name']"
    email_field = "input[data-qa='email']"
    subject_field = "input[data-qa='subject']"
    message_field = "textarea[data-qa='message']"

    upload_file_field = "input[name='upload_file']"
    submit_button = "input[data-qa='submit-button']"

    # Success message shown after form submission
    success_message = ".status.alert.alert-success"

    # Home button shown after successful submission
    home_button = "//a[contains(@class,'btn-success')]"

    # -----------------------------
    # Verification Methods
    # -----------------------------

    def verify_get_in_touch_visible(self):
        print("Verifying Contact Us page loaded...")
        self.expect_visible(self.name_field)
        print("Contact Us page loaded successfully")

    def verify_success_message_visible(self):
        locator = self.page.locator(self.success_message)

        print("Count:", locator.count())
        print("Visible:", locator.is_visible())

        if locator.count() > 0:
            print("Inner HTML:", locator.inner_html())
            print("Outer HTML:", locator.evaluate("e => e.outerHTML"))

        self.page.screenshot(
            path="success_debug.png",
            full_page=True
        )

        # Wait for success message to appear and be visible (30 second timeout)
        expect(locator).to_be_visible(timeout=30000)

    def enter_name(self, name: str):
        self.fill(self.name_field, name)

    def enter_email(self, email: str):
        self.fill(self.email_field, email)

    def enter_subject(self, subject: str):
        self.fill(self.subject_field, subject)

    def enter_message(self, message: str):
        self.fill(self.message_field, message)

    def upload_file(self, file_path: str):
        print(f"Uploading file: {file_path}")

        self.page.locator(
            self.upload_file_field
        ).set_input_files(file_path)

        print("File uploaded successfully")

    def click_submit(self):
        print("Before Submit Click")

        self.page.screenshot(
            path="01_before_submit.png",
            full_page=True
        )

        self.click(self.submit_button)

        print("After Submit Click")

    def click_home_button(self):
        print("Before Home Click")

        locator = self.page.locator(self.home_button)

        print("Home Button Count:", locator.count())

        locator.highlight()

        locator.click()

        # Use domcontentloaded instead of networkidle to avoid flakiness
        # networkidle can timeout on pages with background network activity
        self.page.wait_for_load_state("domcontentloaded", timeout=30000)

        print("After Home Click")