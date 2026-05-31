"""
Test Suite: User Login / Logout
Application Under Test: https://automationexercise.com/

WHAT THIS FILE COVERS
    1. test_login_user_with_correct_credentials   - a registered user can log in.
    2. test_login_user_logout                      - a logged-in user can log out.
    3. test_login_user_with_incorrect_credentials  - bad credentials are rejected.

DESIGN NOTES (for engineers new to this framework)
    - The site has no API/seed data, so the positive login tests REGISTER a fresh
      account first, then exercise login against it. Each run uses a unique email
      (email_prefix + timestamp) so tests never collide and can run repeatedly.
    - Page Objects (pages/) hold all selectors and the verify_* assertions; tests
      read as plain English. See test_register_user.py for the full framework
      orientation.
    - `report_steps` entries are rendered into reports/report.html by the
      pytest_runtest_makereport hook in conftest.py - keep them action + expectation.
"""

import time
import logging

import pytest

from pages.home_page import HomePage
from pages.signup_login_page import SignupLoginPage
from pages.account_creation_page import AccountCreationPage
from pages.account_created_page import AccountCreatedPage
from pages.account_page import AccountPage


def _register_fresh_user(page, base_url, user_data, report_steps):
    """
    Helper: register a brand-new account so the login tests have a real user.

    Mutates user_data['email'] to a unique address and leaves the browser on the
    logged-in account page. Kept as a helper so each test's own steps stay focused
    on the behaviour under test rather than repeating registration boilerplate.
    """
    logging.info("Registering a fresh user with email prefix %s", user_data["email_prefix"])
    home_page = HomePage(page)
    signup_page = SignupLoginPage(page)
    account_creation_page = AccountCreationPage(page)
    account_created_page = AccountCreatedPage(page)

    # Guarantee a unique, never-before-seen email for this run.
    user_data["email"] = f"{user_data['email_prefix']}+{int(time.time())}@example.com"

    report_steps.append("Setup - register a new account to log in with")
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


@pytest.mark.data_driven
def test_login_user_with_correct_credentials(page, base_url, login_user, report_steps, log_capture):
    """
    Objective : A registered user logs in with the correct email + password.
    Expected  : The header shows 'Logged in as <name>'.
    Cleanup   : Delete the account so the test is repeatable.
    """
    # --- Arrange: create the account, then log out so we can test login ---
    logging.info("Starting test_login_user_with_correct_credentials")
    _register_fresh_user(page, base_url, login_user, report_steps)
    signup_page = SignupLoginPage(page)
    account_page = AccountPage(page)
    account_page.click_logout()
    logging.info("Logged out after fresh registration")

    # --- Act: log in with the correct credentials -------------------------
    report_steps.append("1. Open the login page and confirm it is shown")
    HomePage(page).click_signup_login()
    logging.info("Clicked signup/login link to reach login page")
    signup_page.verify_login_to_your_account_visible()
    logging.info("Login page visible")

    report_steps.append("2. Enter the correct email and password, then submit")
    signup_page.enter_login_credentials(login_user["email"], login_user["password"])
    logging.info("Entered credentials for login attempt")
    signup_page.click_login()
    logging.info("Clicked login button")

    # --- Assert: correct user is logged in --------------------------------
    report_steps.append(f"3. EXPECT logged in as '{login_user['name']}'")
    account_page.verify_logged_in_as(login_user["name"])

    # --- Cleanup ----------------------------------------------------------
    report_steps.append("4. Cleanup - delete the account")
    account_page.click_delete_account()
    logging.info("Clicked delete account")
    account_page.verify_account_deleted_visible()
    logging.info("Account deleted after cleanup")


@pytest.mark.data_driven
def test_login_user_logout(page, base_url, login_user, report_steps):
    """
    Objective : A logged-in user can log out and is returned to the login page.
    Expected  : After logout, the 'Login to your account' section is shown again.
    Note      : This account is intentionally NOT deleted here - the test verifies
                the logout flow, and the unique email keeps runs isolated.
    """
    # --- Arrange: register, then log in cleanly ---------------------------
    _register_fresh_user(page, base_url, login_user, report_steps)
    signup_page = SignupLoginPage(page)
    account_page = AccountPage(page)

    account_page.click_logout()
    report_steps.append("1. Log back in with the registered credentials")
    HomePage(page).click_signup_login()
    signup_page.verify_login_to_your_account_visible()
    signup_page.enter_login_credentials(login_user["email"], login_user["password"])
    signup_page.click_login()

    report_steps.append(f"2. EXPECT logged in as '{login_user['name']}'")
    account_page.verify_logged_in_as(login_user["name"])

    # --- Act: the behaviour under test - log out --------------------------
    report_steps.append("3. Click Logout")
    account_page.click_logout()

    # --- Assert: back on the login page -----------------------------------
    report_steps.append("4. EXPECT to be back on the 'Login to your account' page")
    signup_page.verify_login_to_your_account_visible()


@pytest.mark.data_driven
def test_login_user_with_incorrect_credentials(page, base_url, invalid_login_user, report_steps):
    """
    Objective : Login with an unregistered email / wrong password is rejected.
    Expected  : The error 'Your email or password is incorrect!' is shown.
    Note      : No account is created - this is a pure negative test.
    """
    # --- Arrange ----------------------------------------------------------
    home_page = HomePage(page)
    signup_page = SignupLoginPage(page)

    report_steps.append("1. Open the home page")
    home_page.open(base_url)
    home_page.verify_home_is_visible()

    report_steps.append("2. Open the login page and confirm it is shown")
    home_page.click_signup_login()
    signup_page.verify_login_to_your_account_visible()

    # --- Act: submit deliberately invalid credentials ---------------------
    report_steps.append("3. Enter invalid email + password, then submit")
    signup_page.enter_login_credentials(invalid_login_user["email"], invalid_login_user["password"])
    signup_page.click_login()

    # --- Assert: the error banner appears ---------------------------------
    report_steps.append("4. EXPECT error: 'Your email or password is incorrect!'")
    signup_page.verify_login_error_visible()
