import pytest
import time

from pages.home_page import HomePage
from pages.products_page import ProductsPage
from pages.product_detail_page import ProductDetailPage
from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage
from pages.signup_login_page import SignupLoginPage
from pages.account_creation_page import AccountCreationPage
from pages.account_created_page import AccountCreatedPage
from pages.account_page import AccountPage
from pages.payment_page import PaymentPage


@pytest.mark.invoice_download
def test_download_invoice_after_purchase_order(page, base_url, checkout_user, payment_data, report_steps):
    """
    Test Case 24: Download Invoice after purchase order
    
    Test Steps:
    1. Launch browser
    2. Navigate to url 'http://automationexercise.com'
    3. Verify that home page is visible successfully
    4. Add products to cart
    5. Click 'Cart' button
    6. Verify that cart page is displayed
    7. Click Proceed To Checkout
    8. Click 'Register / Login' button
    9. Fill all details in Signup and create account
    10. Verify 'ACCOUNT CREATED!' and click 'Continue' button
    11. Verify ' Logged in as username' at top
    12. Click 'Cart' button
    13. Click 'Proceed To Checkout' button
    14. Verify Address Details and Review Your Order
    15. Enter description in comment text area and click 'Place Order'
    16. Enter payment details: Name on Card, Card Number, CVC, Expiration date
    17. Click 'Pay and Confirm Order' button
    18. Verify success message 'Your order has been placed successfully!'
    19. Click 'Download Invoice' button and verify invoice is downloaded successfully.
    20. Click 'Continue' button
    21. Click 'Delete Account' button
    22. Verify 'ACCOUNT DELETED!' and click 'Continue' button
    """

    # Initialize page objects
    home_page = HomePage(page)
    products_page = ProductsPage(page)
    product_detail_page = ProductDetailPage(page)
    cart_page = CartPage(page)
    checkout_page = CheckoutPage(page)
    signup_login_page = SignupLoginPage(page)
    account_creation_page = AccountCreationPage(page)
    account_created_page = AccountCreatedPage(page)
    account_page = AccountPage(page)
    payment_page = PaymentPage(page)

    # Prepare unique email
    email_prefix = checkout_user["email_prefix"]
    unique_email = f"{email_prefix}+{int(time.time())}@example.com"

    # Comment for order
    order_comment = "Please deliver as soon as possible. Handle with care."

    try:
        # Step 1: Launch browser (implicit in pytest fixture)
        report_steps.append("Step 1: Browser launched")
        print("Step 1: Browser launched")

        # Step 2: Navigate to url 'http://automationexercise.com'
        report_steps.append("Step 2: Navigating to Home Page")
        print("Step 2: Navigating to Home Page")
        home_page.goto(base_url)

        # Step 3: Verify that home page is visible successfully
        report_steps.append("Step 3: Verifying home page is visible")
        print("Step 3: Verifying home page is visible")
        home_page.verify_home_page_loaded()

        # Step 4: Add products to cart
        report_steps.append("Step 4: Adding product to cart")
        print("Step 4: Adding product to cart")
        home_page.click_products_button()
        products_page.verify_all_products_page_visible()
        products_page.click_first_product_view_button()
        product_detail_page.add_to_cart()

        # Step 5: Click 'Cart' button
        report_steps.append("Step 5: Clicking Cart button")
        print("Step 5: Clicking Cart button")
        home_page.click_cart_button()

        # Step 6: Verify that cart page is displayed
        report_steps.append("Step 6: Verifying cart page is displayed")
        print("Step 6: Verifying cart page is displayed")
        cart_page.verify_cart_page_visible()

        # Step 7: Click Proceed To Checkout
        report_steps.append("Step 7: Clicking Proceed To Checkout")
        print("Step 7: Clicking Proceed To Checkout")
        cart_page.proceed_to_checkout()

        # Step 8: Click 'Register / Login' button
        report_steps.append("Step 8: Clicking Register/Login button")
        print("Step 8: Clicking Register/Login button")
        # Anonymous checkout shows a modal prompting to register/login first.
        page.locator("#checkoutModal a[href='/login']").click()
        page.wait_for_load_state("domcontentloaded")
        signup_login_page.verify_new_user_signup_visible()

        # Step 9: Fill all details in Signup and create account
        report_steps.append("Step 9: Filling signup details and creating account")
        print("Step 9: Filling signup details and creating account")
        signup_login_page.enter_signup_name_and_email(checkout_user["name"], unique_email)
        signup_login_page.click_signup()

        # Fill account creation details
        account_creation_page.verify_account_information_visible()
        account_creation_page.select_title(checkout_user["title"])
        account_creation_page.fill_account_information(
            checkout_user["password"],
            checkout_user["dob"],
            checkout_user["newsletter"],
            checkout_user["offers"],
        )
        account_creation_page.fill_address_information(checkout_user)
        account_creation_page.click_create_account()

        # Step 10: Verify 'ACCOUNT CREATED!' and click 'Continue' button
        report_steps.append("Step 10: Verifying account created and clicking Continue")
        print("Step 10: Verifying account created and clicking Continue")
        account_created_page.verify_account_created_visible()
        account_created_page.click_continue()

        # Step 11: Verify ' Logged in as username' at top
        report_steps.append("Step 11: Verifying logged in as username")
        print("Step 11: Verifying logged in as username")
        account_page.verify_logged_in_as(checkout_user["name"])
        report_steps.append(f"   Logged in as: {checkout_user['name']}")

        # Step 12: Click 'Cart' button
        report_steps.append("Step 12: Clicking Cart button")
        print("Step 12: Clicking Cart button")
        home_page.click_cart_button()

        # Step 13: Click 'Proceed To Checkout' button
        report_steps.append("Step 13: Clicking Proceed To Checkout")
        print("Step 13: Clicking Proceed To Checkout")
        cart_page.proceed_to_checkout()

        # Step 14: Verify Address Details and Review Your Order
        report_steps.append("Step 14: Verifying Address Details and Review Order")
        print("Step 14: Verifying Address Details and Review Order")
        checkout_page.verify_checkout_page_visible()

        # Step 15: Enter description in comment text area and click 'Place Order'
        report_steps.append("Step 15: Entering comment and placing order")
        print("Step 15: Entering comment and placing order")
        checkout_page.enter_comment_and_place_order(order_comment)

        # Step 16: Enter payment details
        report_steps.append("Step 16: Entering payment details")
        print("Step 16: Entering payment details")
        payment_page.enter_payment_details(
            payment_data["name_on_card"],
            payment_data["card_number"],
            payment_data["cvc"],
            payment_data["expiry_month"],
            payment_data["expiry_year"],
        )

        # Step 17: Click 'Pay and Confirm Order' button
        report_steps.append("Step 17: Clicking Pay and Confirm Order")
        print("Step 17: Clicking Pay and Confirm Order")
        payment_page.pay_and_confirm_order()

        # Step 18: Verify success message 'Your order has been placed successfully!'
        report_steps.append("Step 18: Verifying order success message")
        print("Step 18: Verifying order success message")
        payment_page.verify_order_confirmation_visible()
        report_steps.append("   ✓ Order placed successfully")

        # Step 19: Click 'Download Invoice' button and verify invoice is downloaded successfully
        report_steps.append("Step 19: Downloading invoice and verifying")
        print("Step 19: Downloading invoice and verifying")
        payment_page.verify_invoice_downloaded()
        invoice_path = payment_page.download_invoice()
        report_steps.append(f"   ✓ Invoice downloaded to: {invoice_path}")

        # Step 20: Click 'Continue' button
        report_steps.append("Step 20: Clicking Continue button")
        print("Step 20: Clicking Continue button")
        payment_page.click_continue_after_order()

        # Step 21: Click 'Delete Account' button
        report_steps.append("Step 21: Clicking Delete Account button")
        print("Step 21: Clicking Delete Account button")
        account_page.click_delete_account()

        # Step 22: Verify 'ACCOUNT DELETED!' and click 'Continue' button
        report_steps.append("Step 22: Verifying account deleted and clicking Continue")
        print("Step 22: Verifying account deleted and clicking Continue")
        account_page.verify_account_deleted_visible()
        account_page.click_continue()

        # Test passed
        report_steps.append("✅ Test Passed: Invoice downloaded successfully after purchase order")
        print("\n✅ Test Passed: Invoice downloaded successfully after purchase order")

    except AssertionError as e:
        report_steps.append(f"❌ Test Failed: {str(e)}")
        print(f"\n❌ Test Failed: {str(e)}")
        raise

    except Exception as e:
        report_steps.append(f"❌ Test Error: {str(e)}")
        print(f"\n❌ Test Error: {str(e)}")
        raise
