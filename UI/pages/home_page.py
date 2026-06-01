from playwright.sync_api import expect

from .base_page import BasePage


class HomePage(BasePage):
    # Scope to the navbar: a populated cart adds a second "Register / Login"
    # link, so a bare a[href='/login'] hits a strict-mode violation.
    signup_login_button = ".shop-menu a[href='/login']"
    home_logo = "img[alt='Website for automation practice']"
    products_button = ".shop-menu a[href='/products']"
    
    # Category sidebar locators
    category_sidebar = "div.left-sidebar"
    women_category = "a[href='#Women']"
    women_subcategories = "div#Women .panel-body a"
    men_category = "a[href='#Men']"
    men_subcategories = "div#Men .panel-body a"
    
    # Subscription locators
    subscription_heading = "text=SUBSCRIPTION"
    subscription_email_input = "input#susbscribe_email"
    subscription_button = "button#subscribe"
    subscription_success_message = "div.alert-success.alert"

    # Recommended items locators
    recommended_items_heading = "text=RECOMMENDED ITEMS"
    recommended_items_container = "div.recommended_items"
    recommended_products = "div.recommended_items div.productinfo"
    recommended_add_to_cart_buttons = "div.recommended_items a.add-to-cart"

    # Scroll button and hero text locators
    # The scroll-up arrow has id 'scrollUp' and no href; the hero text appears
    # in 3 duplicated carousel slides, so target the active slide only.
    scroll_up_button = "#scrollUp"
    home_hero_text = ".carousel-inner .item.active h2:has-text('Full-Fledged practice website')"

    def open(self, url: str):
        self.goto(url)

    def verify_home_is_visible(self):
        self.page.wait_for_load_state("networkidle")
        self.expect_visible(self.home_logo, timeout=15000)

    def verify_home_page_loaded(self):
        """Verify that the home page has loaded"""
        print("Verifying home page loaded...")
        self.expect_visible(self.home_logo, timeout=10000)
        print("Home page loaded successfully")

    def click_products_button(self):
        """Click on 'Products' button in the navbar"""
        print("Clicking on Products button...")
        self.click(self.products_button)
        self.page.wait_for_load_state("domcontentloaded")
        print("Navigated to Products page")

    def click_signup_login(self):
        print("Current URL:", self.page.url)

        links = self.page.locator("a").all_text_contents()
        print("Available links:", links)

        self.page.wait_for_load_state("networkidle")

        self.expect_visible(self.signup_login_button, timeout=15000)

        self.click(self.signup_login_button)

    def click_cart_button(self):
        """Click on the Cart button in the navbar"""
        print("Clicking on Cart button...")
        # Scope to the navbar; a bare a[href='/view_cart'] also matches the
        # add-to-cart modal link (strict-mode violation when the modal is open).
        cart_button = ".shop-menu a[href='/view_cart']"
        self.click(cart_button)
        self.page.wait_for_load_state("domcontentloaded")
        print("Navigated to Cart page")

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

    def click_scroll_up_button(self):
        """Click the scroll-up arrow button to move to the top of the page"""
        print("Clicking scroll-up arrow button...")
        self.expect_visible(self.scroll_up_button, timeout=10000)
        self.click(self.scroll_up_button)
        self.page.wait_for_timeout(1000)
        print("Clicked scroll-up arrow button")

    def scroll_to_top(self):
        """Scroll up page to the top without using the arrow button"""
        print("Scrolling to top of page...")
        self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        self.page.wait_for_timeout(1000)
        print("Scrolled to top of page")

    def verify_home_hero_text_visible(self):
        """Verify the home page hero text is visible after scrolling up"""
        print("Verifying home page hero text is visible...")
        self.expect_visible(self.home_hero_text, timeout=10000)
        print("Home page hero text is visible")

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

    # -------- Category Navigation Methods --------

    def verify_categories_visible(self):
        """Verify that categories sidebar is visible on the left side"""
        print("Verifying categories sidebar is visible...")
        self.expect_visible(self.category_sidebar)
        print("Categories sidebar is visible")

    def click_women_category(self):
        """Click on 'Women' category to expand it"""
        print("Clicking on Women category...")
        self.click(self.women_category)
        self.page.wait_for_load_state("domcontentloaded")
        print("Women category expanded")

    def get_women_subcategories_count(self):
        """Get the count of sub-categories under Women"""
        print("Getting Women sub-categories count...")
        subcategories = self.page.locator(self.women_subcategories)
        count = subcategories.count()
        print(f"Women has {count} sub-categories")
        return count

    def click_women_subcategory(self, index: int = 0):
        """Click on a Women sub-category by index (e.g., Dress)"""
        print(f"Clicking Women sub-category at index {index}...")
        subcategories = self.page.locator(self.women_subcategories)
        if subcategories.count() <= index:
            raise IndexError(f"Women sub-category index {index} not found")
        subcategories.nth(index).click()
        self.page.wait_for_load_state("domcontentloaded")
        print(f"Women sub-category {index} clicked")

    def click_men_category(self):
        """Click on 'Men' category to expand it"""
        print("Clicking on Men category...")
        self.click(self.men_category)
        self.page.wait_for_load_state("domcontentloaded")
        print("Men category expanded")

    def get_men_subcategories_count(self):
        """Get the count of sub-categories under Men"""
        print("Getting Men sub-categories count...")
        subcategories = self.page.locator(self.men_subcategories)
        count = subcategories.count()
        print(f"Men has {count} sub-categories")
        return count

    def click_men_subcategory(self, index: int = 0):
        """Click on a Men sub-category by index"""
        print(f"Clicking Men sub-category at index {index}...")
        subcategories = self.page.locator(self.men_subcategories)
        if subcategories.count() <= index:
            raise IndexError(f"Men sub-category index {index} not found")
        subcategories.nth(index).click()
        self.page.wait_for_load_state("domcontentloaded")
        print(f"Men sub-category {index} clicked")

    # -------- Recommended Items Methods --------

    def scroll_to_recommended_items(self):
        """Scroll down to the Recommended Items section"""
        print("Scrolling to Recommended Items section...")
        # Scroll to bottom of page to see recommended items
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        # Wait for scroll animation to complete
        self.page.wait_for_timeout(1000)
        print("Scrolled to Recommended Items section")

    def verify_recommended_items_visible(self):
        """Verify that 'RECOMMENDED ITEMS' heading is visible"""
        print("Verifying RECOMMENDED ITEMS heading is visible...")
        self.expect_visible(self.recommended_items_heading, timeout=10000)
        print("RECOMMENDED ITEMS heading is visible")

    def get_recommended_items_count(self):
        """Get the count of recommended products"""
        print("Getting recommended items count...")
        products = self.page.locator(self.recommended_products)
        count = products.count()
        print(f"Found {count} recommended items")
        return count

    def click_add_to_cart_on_recommended_item(self, index: int = 0):
        """Click on 'Add To Cart' button on a recommended product by index"""
        print(f"Clicking Add To Cart on recommended item at index {index}...")

        # Recommended items live in an auto-rotating Bootstrap carousel; only the
        # active slide's buttons are clickable. Targeting a bare nth() can resolve
        # to a hidden slide and the click then races the rotation, so the add
        # never registers. Scope to the active slide instead.
        add_to_cart_buttons = self.page.locator(
            "div.recommended_items .item.active a.add-to-cart"
        )
        expect(add_to_cart_buttons.nth(index)).to_be_visible(timeout=10000)
        add_to_cart_buttons.nth(index).click()

        # Wait for the add-to-cart modal — its appearance confirms the item was
        # actually added — then dismiss it before navigating away.
        modal = self.page.locator("#cartModal")
        expect(modal).to_be_visible(timeout=10000)
        self.page.locator("#cartModal button:has-text('Continue Shopping')").click()
        expect(modal).to_be_hidden(timeout=10000)

        print(f"Added recommended item {index} to cart")