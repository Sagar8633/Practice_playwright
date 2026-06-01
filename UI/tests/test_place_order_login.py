"""
Test Suite: Place Order - Login before Checkout
Application Under Test: https://automationexercise.com/

WHAT THIS FILE COVERS
    test_place_order_login_before_checkout - a user logs in to an existing account,
                                            adds products to cart, proceeds to checkout,
                                            enters payment details, places order, and
                                            deletes the account.

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - Full end-to-end order flow with login: login → browse products → add to cart → 
      checkout → payment → order confirmation → account cleanup
    - User registration for setup (helper) then logout to test login workflow
    - Email + password login verification
    - Adding products to cart from product detail page
    - Proceeding through checkout with address and order review verification
    - Payment form completion with card details
    - Order success verification with confirmation message
    - Account deletion for cleanup/repeatability
    - report_steps entries are rendered into reports/report.html by conftest's
      pytest_runtest_makereport hook.
    - Data-driven test: user and payment data from YAML for reusability

DESIGN NOTES
    - The test first registers a fresh account (setup step, so we have a user to log in)
    - Then logs out to test the login workflow (the actual test)
    - Uses unique email (prefix + timestamp) so it can run repeatedly without conflicts
    - All selectors and verifications live in page objects (pages/) for maintainability
    - Each step is logged in report_steps for clear test execution visibility
"""

import time
import logging

import pytest

from pages.home_page import HomePage
from pages.signup_login_page import SignupLoginPage
from pages.account_creation_page import AccountCreationPage
from pages.account_created_page import AccountCreatedPage
from pages.account_page import AccountPage
from pages.products_page import ProductsPage
from pages.product_detail_page import ProductDetailPage
from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage
from pages.payment_page import PaymentPage


def _register_fresh_user_for_login_test(page, base_url, user_data, report_steps):
    """
    Helper: register a brand-new account so we have a real user to log in with.
    
    This is a setup step (prefixed in report_steps), not the actual test.
    Leaves the browser on the logged-in account page.
    """
    logging.info("Setup: Registering a fresh user for login test with email prefix %s", user_data["email_prefix"])
    home_page = HomePage(page)
    signup_page = SignupLoginPage(page)
    account_creation_page = AccountCreationPage(page)
    account_created_page = AccountCreatedPage(page)

    # Guarantee a unique, never-before-seen email for this run.
    user_data["email"] = f"{user_data['email_prefix']}+{int(time.time())}@example.com"

    report_steps.append("Setup - Register a new account to test login with")
    logging.info("Opening home page for registration")
    home_page.open(base_url)
    home_page.verify_home_is_visible()
    logging.info("Home page visible")
    home_page.click_signup_login()
    signup_page.verify_new_user_signup_visible()
    signup_page.enter_signup_name_and_email(user_data["name"], user_data["email"])
    signup_page.click_signup()

    account_creation_page.verify_account_information_visible()
    account_creation_page.select_title(user_data["title"])
    account_creation_page.fill_account_information(
        password=user_data["password"],
        dob=user_data["dob"],
        newsletter=user_data["newsletter"],
        offers=user_data["offers"],
    )
    account_creation_page.fill_address_information(user_data)
    account_creation_page.click_create_account()

    account_created_page.verify_account_created_visible()
    account_created_page.click_continue()
    account_page = AccountPage(page)
    account_page.verify_logged_in_as(user_data["name"])
    
    # Log out so we can test the login workflow
    report_steps.append("Setup - Log out to prepare for login test")
    account_page.click_logout()
    page.wait_for_load_state("domcontentloaded")
    logging.info("Setup complete: user registered and logged out")


@pytest.mark.data_driven
def test_place_order_login_before_checkout(page, base_url, login_user, payment_data, report_steps):
    """
    Objective : Complete a full order flow with login - login → add to cart → 
                checkout → payment → order confirmation → account cleanup.
    Data      : login_user (email/password for login from YAML)
                payment_data (payment card details from YAML)
    Expected  : User logs in, places order successfully, and account is deleted.
    """
    # --- Arrange: build the page objects this test will drive ---------------
    home_page = HomePage(page)
    signup_login_page = SignupLoginPage(page)
    account_page = AccountPage(page)
    products_page = ProductsPage(page)
    product_detail_page = ProductDetailPage(page)
    cart_page = CartPage(page)
    checkout_page = CheckoutPage(page)
    payment_page = PaymentPage(page)

    print("\n========== TEST STARTED: Place Order - Login Before Checkout ==========")

    # --- Setup: Register a fresh user so we have an account to log in with ----
    _register_fresh_user_for_login_test(page, base_url, login_user, report_steps)

    # ========== STEP 1-3: Launch Browser & Navigate Home =======================
    report_steps.append("1. Launch browser and navigate to https://automationexercise.com")
    logging.info("Opening home page for login test")
    home_page.open(base_url)

    report_steps.append("2. Verify home page is visible successfully")
    home_page.verify_home_is_visible()
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"
    logging.info("Home page verified")

    # ========== STEP 4-6: Login with Email & Password =========================
    report_steps.append("3. Click 'Signup / Login' button")
    logging.info("Clicking signup/login button")
    home_page.click_signup_login()
    signup_login_page.verify_login_to_your_account_visible()

    report_steps.append(f"4. Fill email '{login_user['email']}' and password, then click 'Login'")
    logging.info(f"Logging in with email {login_user['email']}")
    signup_login_page.enter_login_credentials(login_user["email"], login_user["password"])
    signup_login_page.click_login()
    page.wait_for_load_state("domcontentloaded")

    report_steps.append(f"5. Verify 'Logged in as {login_user['name']}' at top")
    logging.info("Verifying logged in status")
    account_page.verify_logged_in_as(login_user["name"])

    # ========== STEP 7-9: Browse and Add Products to Cart =======================
    report_steps.append("6. Click 'Products' button to navigate to products page")
    logging.info("Navigating to products page")
    page.locator(products_page.products_button).click()
    page.wait_for_load_state("domcontentloaded")

    report_steps.append("7. Verify All Products page is loaded and click first product")
    logging.info("Verifying products page and selecting first product")
    products_page.verify_all_products_page_visible()
    products_page.verify_products_list_visible()
    products_page.click_first_product_view_button()

    report_steps.append("8. Verify product detail page and add product to cart")
    logging.info("Adding product to cart")
    product_detail_page.verify_product_detail_page_visible()
    product_detail_page.verify_product_details_visible()
    product_detail_page.add_to_cart()

    # Handle the "Continue Shopping" modal if it appears
    try:
        continue_button = page.locator("button:has-text('Continue Shopping')")
        if continue_button.is_visible(timeout=2000):
            page.wait_for_load_state("domcontentloaded")
    except:
        pass

    # ========== STEP 10-11: Verify Cart and Proceed to Checkout ================
    report_steps.append("9. Click 'Cart' button to navigate to cart page")
    logging.info("Navigating to cart page")
    cart_page.navigate_to_cart()

    report_steps.append("10. Verify that cart page is displayed with products")
    logging.info("Verifying cart page")
    cart_page.verify_cart_page_visible()

    report_steps.append("11. Click 'Proceed To Checkout' button")
    logging.info("Proceeding to checkout")
    cart_page.proceed_to_checkout()
    page.wait_for_load_state("domcontentloaded")

    # ========== STEP 12-14: Review Order and Place Order =======================
    report_steps.append("12. Verify Address Details and Review Your Order on checkout page")
    logging.info("Verifying checkout page details")
    checkout_page.verify_checkout_page_visible()
    checkout_page.verify_review_order_products()

    report_steps.append("13. Enter comment in comment text area and click 'Place Order'")
    logging.info("Entering order comment and placing order")
    checkout_page.enter_comment_and_place_order(login_user.get("comment", "Please deliver at earliest convenience."))
    page.wait_for_load_state("domcontentloaded")

    # ========== STEP 15-16: Payment Details ====================================
    report_steps.append("14. Enter payment details (Name, Card Number, CVC, Expiry)")
    logging.info("Filling payment details")
    payment_page.enter_payment_details(
        name_on_card=payment_data["name_on_card"],
        card_number=payment_data["card_number"],
        cvc=payment_data["cvc"],
        expiry_month=payment_data["expiry_month"],
        expiry_year=payment_data["expiry_year"]
    )

    report_steps.append("15. Click 'Pay and Confirm Order' button")
    logging.info("Confirming payment")
    payment_page.pay_and_confirm_order()
    page.wait_for_load_state("domcontentloaded")

    # ========== STEP 17: Verify Order Success ==================================
    report_steps.append("16. Verify success message 'Your order has been placed successfully!'")
    logging.info("Verifying order success message")
    payment_page.verify_success_message("Your order has been placed successfully!")
    print("Order placed successfully!")

    # ========== STEP 18-20: Delete Account (Cleanup) ===========================
    report_steps.append("17. Click 'Delete Account' button for cleanup")
    logging.info("Deleting account for cleanup")
    # 'Delete Account' is a navbar link available while logged in.
    account_page.click_delete_account()
    page.wait_for_load_state("domcontentloaded")

    report_steps.append("18. Verify 'ACCOUNT DELETED!' message and click 'Continue'")
    logging.info("Verifying account deleted")
    account_page.verify_account_deleted_visible()
    account_page.click_continue()

    print("\n========== TEST COMPLETED SUCCESSFULLY ==========")
    logging.info("Test completed successfully")
