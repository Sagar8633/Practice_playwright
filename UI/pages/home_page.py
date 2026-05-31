from playwright.sync_api import expect

from .base_page import BasePage


class HomePage(BasePage):
    signup_login_button = "a[href='/login']"
    home_logo = "img[alt='Website for automation practice']"
    
    # Subscription locators
    subscription_heading = "text=SUBSCRIPTION"
    subscription_email_input = "input#susbscribe_email"
    subscription_button = "button#subscribe"
    subscription_success_message = "div.alert-success.alert"

    def open(self, url: str):
        self.goto(url)

    def verify_home_is_visible(self):
        self.expect_visible(self.home_logo)

    def click_signup_login(self):
        # Wait for the signup/login button to be visible before clicking
        self.expect_visible(self.signup_login_button, timeout=15000)
        self.click(self.signup_login_button)

    def scroll_to_footer(self):
        """Scroll down to the footer section of the page"""
        print("Scrolling down to footer...")
        # Evaluate JavaScript to scroll to bottom of page
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        # Wait a moment for scroll animation to complete
        self.page.wait_for_timeout(1000)
        print("Scrolled to footer")

    def verify_subscription_heading_visible(self):
        """Verify that the SUBSCRIPTION heading is visible"""
        print("Verifying SUBSCRIPTION heading is visible...")
        self.expect_visible(self.subscription_heading)
        print("SUBSCRIPTION heading is visible")

    def subscribe_with_email(self, email: str):
        """Enter email address in subscription input and click subscribe button"""
        print(f"Subscribing with email: {email}")
        
        # Enter email in subscription input
        self.fill(self.subscription_email_input, email)
        print(f"Entered email: {email}")
        
        # Click subscribe button
        self.click(self.subscription_button)
        print("Clicked subscribe button")
        
        # Wait for page to process subscription
        self.page.wait_for_timeout(1000)

    def verify_subscription_success_message(self):
        locator = self.page.locator(".alert-success")

        print("Count:", locator.count())

        print("Text:", locator.first.text_content())

        # self.page.screenshot(path="subscription_debug.png",full_page=True        )

        assert "successfully subscribed" in locator.first.text_content().lower()