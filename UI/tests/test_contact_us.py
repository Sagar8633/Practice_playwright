"""
Test Suite: Contact Us form
Application Under Test: https://automationexercise.com/contact_us

WHAT THIS FILE COVERS
    test_contact_us_form - fill and submit the Contact Us form (including a file
    upload and a JavaScript confirm dialog) and verify the success message.

KEY TECHNIQUES DEMONSTRATED (useful reference for new engineers)
    - File upload: handled in ContactUsPage.upload_file via set_input_files.
    - JavaScript dialog (alert/confirm): clicking Submit triggers a native confirm
      box. A native dialog BLOCKS the page until dismissed, so we must register a
      handler with page.once("dialog", ...) BEFORE clicking. (Note: Playwright
      Python has no page.expect_dialog() - that is the JS/TS API only.)
    - report_steps entries are surfaced in reports/report.html by conftest's
      pytest_runtest_makereport hook.
"""

import os

from playwright.sync_api import expect
import pytest

from pages.home_page import HomePage
from pages.contact_us_page import ContactUsPage


@pytest.mark.data_driven
def test_contact_us_form(page, base_url, contact_us_user, report_steps):
    """
    Objective : Submit the Contact Us form with a file attachment and verify the
                green success banner, then navigate back home.
    Data      : contact_us_user (name/email/subject/message/file_name) from YAML.
    Expected  : 'Success! Your details have been submitted successfully.' is shown,
                and the Home button returns to the home page.
    """
    # --- Arrange ----------------------------------------------------------
    home_page = HomePage(page)
    contact_us_page = ContactUsPage(page)

    print("\n========== TEST STARTED ==========")

    report_steps.append("1. Open the home page and confirm it loaded")
    home_page.open(base_url)
    home_page.verify_home_is_visible()
    # Match on domain only: base_url is http:// but the site redirects to https.
    assert "automationexercise.com" in page.url, f"Did not land on home page, got: {page.url}"

    report_steps.append("2. Click 'Contact Us' and confirm navigation")
    page.locator(contact_us_page.contact_us_button).click()
    page.wait_for_load_state("domcontentloaded")
    # Proven, stable assertion: the URL must now be the contact_us page.
    assert "contact_us" in page.url, f"Expected contact_us URL, got: {page.url}"

    report_steps.append("3. EXPECT the 'GET IN TOUCH' form is visible")
    contact_us_page.verify_get_in_touch_visible()

    # --- Act: fill the form fields ----------------------------------------
    report_steps.append("4. Enter name, email, subject and message")
    contact_us_page.enter_name(contact_us_user["name"])
    contact_us_page.enter_email(contact_us_user["email"])
    contact_us_page.enter_subject(contact_us_user["subject"])
    contact_us_page.enter_message(contact_us_user["message"])

    report_steps.append("5. Upload the attachment file")
    # Resolve the data file relative to THIS test file so it works on any machine.
    file_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", contact_us_user["file_name"])
    )
    # Assert the fixture file exists before we try to upload it - a clear failure
    # message here is far easier to debug than a Playwright timeout later.
    assert os.path.exists(file_path), f"Upload file not found: {file_path}"
    contact_us_page.upload_file(file_path)

    # --- Act: submit and accept the JS confirm dialog ---------------------
    report_steps.append("6. Submit the form and accept the confirmation dialog")
    # Register the dialog handler BEFORE clicking. A native confirm() blocks the
    # page, so the click only returns once this handler accepts it. Using .once
    # means it auto-removes after firing and won't affect later steps.
    def handle_dialog(dialog):
        print("Dialog message:", dialog.message)
        dialog.accept()

    page.once("dialog", handle_dialog)
    
    # Expect navigation when clicking submit (the form submission redirects)
    page.once("dialog", lambda dialog: dialog.accept())

    contact_us_page.click_submit()

    expect(
        page.locator(".status.alert.alert-success")
    ).to_be_visible()

    # --- Assert: success message ------------------------------------------
    report_steps.append("7. EXPECT the success message to be visible")
    contact_us_page.verify_success_message_visible()

    # --- Act / Assert: return home ----------------------------------------
    report_steps.append("8. Click 'Home' and EXPECT the home page again")
    contact_us_page.click_home_button()
    home_page.verify_home_is_visible()

    print("========== TEST PASSED ==========")
