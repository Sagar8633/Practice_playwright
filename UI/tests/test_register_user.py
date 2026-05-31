"""
Test Suite: User Registration (Sign Up)
Application Under Test: https://automationexercise.com/

WHAT THIS FILE COVERS
    1. test_register_user                  - a brand new user can register, is
                                             logged in, and the account can be deleted.
    2. test_register_user_with_existing_email - registering with an email that already
                                             exists is rejected with the correct error.

HOW THE FRAMEWORK FITS TOGETHER (read this first if you are new)
    - Page Object Model (POM): every screen lives in pages/ (e.g. HomePage,
      SignupLoginPage). Tests NEVER touch raw selectors; they call readable page
      methods like `home_page.click_signup_login()`. Selectors live only in the
      page classes, so a UI change is fixed in ONE place.
    - Fixtures come from conftest.py:
        * page          - a fresh Playwright browser page (pytest-playwright).
        * base_url      - the application URL.
        * user / invalid_signup_user - test data loaded from data/users.yaml.
        * report_steps  - a list we append human-readable steps to; conftest's
                          pytest_runtest_makereport hook renders them into the
                          HTML report (reports/report.html) so each test row
                          shows exactly what was exercised.
    - @pytest.mark.data_driven marks these as data-driven (data comes from YAML).
    - Assertions: the verify_* page methods use Playwright's `expect`, which
      auto-waits and raises on failure. We also add a few explicit `assert`
      statements in the test for state the report should make obvious.
"""

import time

import pytest

from pages.home_page import HomePage
from pages.signup_login_page import SignupLoginPage
from pages.account_creation_page import AccountCreationPage
from pages.account_created_page import AccountCreatedPage
from pages.account_page import AccountPage


@pytest.mark.data_driven
def test_register_user(page, base_url, user, report_steps):
    """
    Objective : Register a NEW user end-to-end and verify success.
    Precondition: `user` email in data/users.yaml is not already registered.
                  (The test deletes the account at the end so it stays repeatable.)
    Expected  : "Account Created!" is shown, the user is logged in by name, and
                the account is successfully deleted.
    """
    # --- Arrange: build the page objects this test will drive --------------
    home_page = HomePage(page)
    signup_page = SignupLoginPage(page)
    account_creation_page = AccountCreationPage(page)
    account_created_page = AccountCreatedPage(page)
    account_page = AccountPage(page)

    # --- Act / Assert: walk the registration journey ----------------------
    report_steps.append("1. Open the home page and confirm it loaded")
    home_page.open(base_url)
    home_page.verify_home_is_visible()
    # Explicit URL assertion so the report proves we landed on the right site.
    # Match on the domain only: base_url is http:// but the site redirects to https.
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"

    report_steps.append("2. Click 'Signup / Login' and confirm the signup section")
    home_page.click_signup_login()
    signup_page.verify_new_user_signup_visible()

    report_steps.append(f"3. Enter new signup name '{user['name']}' and email")
    signup_page.enter_signup_name_and_email(user["name"], user["email"])
    signup_page.click_signup()

    report_steps.append("4. Confirm the 'Enter Account Information' form is shown")
    account_creation_page.verify_account_information_visible()

    report_steps.append("5. Fill account details (title, password, DOB, preferences)")
    account_creation_page.select_title(user["title"])
    account_creation_page.fill_account_information(
        password=user["password"],
        dob=user["dob"],
        newsletter=user["newsletter"],
        offers=user["offers"],
    )

    report_steps.append("6. Fill the address details")
    account_creation_page.fill_address_information(user)
    account_creation_page.click_create_account()

    report_steps.append("7. EXPECT 'Account Created!' confirmation, then continue")
    account_created_page.verify_account_created_visible()
    account_created_page.click_continue()

    report_steps.append(f"8. EXPECT user is logged in as '{user['name']}'")
    account_page.verify_logged_in_as(user["name"])

    report_steps.append("9. Delete the account and EXPECT 'Account Deleted!' (cleanup)")
    account_page.click_delete_account()
    account_page.verify_account_deleted_visible()
    account_page.click_continue()


@pytest.mark.data_driven
def test_register_user_with_existing_email(page, base_url, invalid_signup_user, report_steps):
    """
    Objective : Verify a user CANNOT register twice with the same email.
    Approach  : Register a fresh account first (so the email is guaranteed to
                exist), then try to register again with that same email.
    Expected  : The second attempt shows 'Email Address already exist!'.
    Cleanup   : Log in with the created account and delete it so the run is repeatable.
    """
    # --- Arrange ----------------------------------------------------------
    home_page = HomePage(page)
    signup_page = SignupLoginPage(page)
    account_creation_page = AccountCreationPage(page)
    account_created_page = AccountCreatedPage(page)
    account_page = AccountPage(page)

    # Make the email unique per run so the "first" registration always succeeds.
    # int(time.time()) appends a timestamp; the +tag keeps it a valid address.
    unique_email = f"{invalid_signup_user['email_prefix']}+{int(time.time())}@example.com"
    invalid_signup_user["email"] = unique_email

    # --- Act / Assert: first registration (setup the precondition) --------
    report_steps.append("1. Register a user so this email definitely exists")
    home_page.open(base_url)
    home_page.verify_home_is_visible()
    home_page.click_signup_login()
    signup_page.verify_new_user_signup_visible()
    signup_page.enter_signup_name_and_email(invalid_signup_user["name"], invalid_signup_user["email"])
    signup_page.click_signup()

    account_creation_page.verify_account_information_visible()
    account_creation_page.select_title(invalid_signup_user["title"])
    account_creation_page.fill_account_information(
        password=invalid_signup_user["password"],
        dob=invalid_signup_user["dob"],
        newsletter=invalid_signup_user["newsletter"],
        offers=invalid_signup_user["offers"],
    )
    account_creation_page.fill_address_information(invalid_signup_user)
    account_creation_page.click_create_account()

    account_created_page.verify_account_created_visible()
    account_created_page.click_continue()
    account_page.click_logout()

    # --- Act / Assert: the actual test - re-register the same email -------
    report_steps.append("2. Attempt to register AGAIN with the same email")
    home_page.click_signup_login()
    signup_page.verify_new_user_signup_visible()
    signup_page.enter_signup_name_and_email(invalid_signup_user["name"], invalid_signup_user["email"])
    signup_page.click_signup()

    report_steps.append("3. EXPECT error: 'Email Address already exist!'")
    signup_page.verify_signup_error_visible()

    # --- Cleanup: log in to the account we created and delete it ----------
    report_steps.append("4. Cleanup - log in and delete the created account")
    signup_page.enter_login_credentials(invalid_signup_user["email"], invalid_signup_user["password"])
    signup_page.click_login()
    account_page.verify_logged_in_as(invalid_signup_user["name"])
    account_page.click_delete_account()
    account_page.verify_account_deleted_visible()
