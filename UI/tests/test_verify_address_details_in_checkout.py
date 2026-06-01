import pytest
import time

from pages.home_page import HomePage
from pages.signup_login_page import SignupLoginPage
from pages.account_creation_page import AccountCreationPage
from pages.account_created_page import AccountCreatedPage
from pages.account_page import AccountPage
from pages.products_page import ProductsPage
from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage


@pytest.mark.address_verification
def test_verify_address_details_in_checkout(page, base_url, checkout_user, report_steps):
    """
    Test Case 23: Verify address details in checkout page
    
    Test Steps:
    1. Launch browser
    2. Navigate to url 'http://automationexercise.com'
    3. Verify that home page is visible successfully
    4. Click 'Signup / Login' button
    5. Fill all details in Signup and create account
    6. Verify 'ACCOUNT CREATED!' and click 'Continue' button
    7. Verify ' Logged in as username' at top
    8. Add products to cart
    9. Click 'Cart' button
    10. Verify that cart page is displayed
    11. Click Proceed To Checkout
    12. Verify that the delivery address is same address filled at the time registration of account
    13. Verify that the billing address is same address filled at the time registration of account
    14. Click 'Delete Account' button
    15. Verify 'ACCOUNT DELETED!' and click 'Continue' button
    """

    # Initialize page objects
    home_page = HomePage(page)
    signup_login_page = SignupLoginPage(page)
    account_creation_page = AccountCreationPage(page)
    account_created_page = AccountCreatedPage(page)
    account_page = AccountPage(page)
    products_page = ProductsPage(page)
    cart_page = CartPage(page)
    checkout_page = CheckoutPage(page)

    # Prepare unique email to avoid conflicts
    email_prefix = checkout_user["email_prefix"]
    unique_email = f"{email_prefix}+{int(time.time())}@example.com"

    # Store address details from test data for later verification
    address_details = {
        "first_name": checkout_user["first_name"],
        "last_name": checkout_user["last_name"],
        "address1": checkout_user["address1"],
        "address2": checkout_user["address2"],
        "city": checkout_user["city"],
        "state": checkout_user["state"],
        "country": checkout_user["country"],
        "zipcode": checkout_user["zipcode"],
        "mobile_number": checkout_user["mobile_number"],
    }

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

        # Step 4: Click 'Signup / Login' button
        report_steps.append("Step 4: Clicking Signup/Login button")
        print("Step 4: Clicking Signup/Login button")
        home_page.click_signup_login()

        # Step 5: Fill all details in Signup and create account
        report_steps.append("Step 5: Filling signup details and creating account")
        print("Step 5: Filling signup details and creating account")
        signup_login_page.verify_new_user_signup_visible()
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

        # Step 6: Verify 'ACCOUNT CREATED!' and click 'Continue' button
        report_steps.append("Step 6: Verifying account created and clicking Continue")
        print("Step 6: Verifying account created and clicking Continue")
        account_created_page.verify_account_created_visible()
        account_created_page.click_continue()

        # Step 7: Verify ' Logged in as username' at top
        report_steps.append("Step 7: Verifying logged in as username")
        print("Step 7: Verifying logged in as username")
        account_page.verify_logged_in_as(checkout_user["name"])
        report_steps.append(f"   Logged in as: {checkout_user['name']}")

        # Step 8: Add products to cart
        report_steps.append("Step 8: Adding product to cart")
        print("Step 8: Adding product to cart")
        home_page.click_products_button()
        products_page.verify_all_products_page_visible()
        products_page.click_first_product_view_button()
        # Add product to cart (using product detail page)
        from pages.product_detail_page import ProductDetailPage
        product_detail_page = ProductDetailPage(page)
        product_detail_page.add_to_cart()

        # Step 9: Click 'Cart' button
        report_steps.append("Step 9: Clicking Cart button")
        print("Step 9: Clicking Cart button")
        home_page.click_cart_button()

        # Step 10: Verify that cart page is displayed
        report_steps.append("Step 10: Verifying cart page is displayed")
        print("Step 10: Verifying cart page is displayed")
        cart_page.verify_cart_page_visible()
        items_count = cart_page.get_cart_items_count()
        report_steps.append(f"   Cart contains {items_count} item(s)")

        # Step 11: Click Proceed To Checkout
        report_steps.append("Step 11: Clicking Proceed To Checkout")
        print("Step 11: Clicking Proceed To Checkout")
        cart_page.proceed_to_checkout()

        # Step 12: Verify that the delivery address is same address filled at the time registration
        report_steps.append("Step 12: Verifying delivery address matches registration details")
        print("Step 12: Verifying delivery address")
        checkout_page.verify_checkout_page_visible()
        checkout_page.verify_delivery_address_contains(
            address_details["first_name"],
            address_details["last_name"],
            address_details["address1"],
            address_details["city"],
            address_details["state"],
            address_details["zipcode"],
        )
        report_steps.append("   ✓ Delivery address verified")

        # Step 13: Verify that the billing address is same address filled at the time registration
        report_steps.append("Step 13: Verifying billing address matches registration details")
        print("Step 13: Verifying billing address")
        checkout_page.verify_billing_address_contains(
            address_details["first_name"],
            address_details["last_name"],
            address_details["address1"],
            address_details["city"],
            address_details["state"],
            address_details["zipcode"],
        )
        report_steps.append("   ✓ Billing address verified")

        # Step 14: Click 'Delete Account' button
        report_steps.append("Step 14: Clicking Delete Account button")
        print("Step 14: Clicking Delete Account button")
        # 'Delete Account' is a navbar link available while logged in.
        account_page.click_delete_account()

        # Step 15: Verify 'ACCOUNT DELETED!' and click 'Continue' button
        report_steps.append("Step 15: Verifying account deleted and clicking Continue")
        print("Step 15: Verifying account deleted and clicking Continue")
        account_page.verify_account_deleted_visible()
        account_page.click_continue()

        # Test passed
        report_steps.append("✅ Test Passed: Address details verified successfully in checkout")
        print("\n✅ Test Passed: Address details verified successfully in checkout")

    except AssertionError as e:
        report_steps.append(f"❌ Test Failed: {str(e)}")
        print(f"\n❌ Test Failed: {str(e)}")
        raise

    except Exception as e:
        report_steps.append(f"❌ Test Error: {str(e)}")
        print(f"\n❌ Test Error: {str(e)}")
        raise
