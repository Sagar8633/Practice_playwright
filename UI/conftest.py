import yaml
from pathlib import Path
import os
import pytest
from pytest_html import extras


def load_user_data():
    data_file = Path(__file__).parent / "data" / "users.yaml"
    with data_file.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["users"]


def pytest_generate_tests(metafunc):
    if "user" in metafunc.fixturenames:
        users = load_user_data()
        metafunc.parametrize("user", users, ids=[user.get("test_name", str(i)) for i, user in enumerate(users)])
    if "login_user" in metafunc.fixturenames:
        data_file = Path(__file__).parent / "data" / "users.yaml"
        with data_file.open("r", encoding="utf-8") as handle:
            login_users = yaml.safe_load(handle).get("login_users", [])
        metafunc.parametrize("login_user", login_users, ids=[user.get("test_name", str(i)) for i, user in enumerate(login_users)])
    if "invalid_login_user" in metafunc.fixturenames:
        data_file = Path(__file__).parent / "data" / "users.yaml"
        with data_file.open("r", encoding="utf-8") as handle:
            invalid_logins = yaml.safe_load(handle).get("invalid_login_users", [])
        metafunc.parametrize("invalid_login_user", invalid_logins, ids=[user.get("test_name", str(i)) for i, user in enumerate(invalid_logins)])
    if "invalid_signup_user" in metafunc.fixturenames:
        data_file = Path(__file__).parent / "data" / "users.yaml"
        with data_file.open("r", encoding="utf-8") as handle:
            invalid_signups = yaml.safe_load(handle).get("invalid_signup_users", [])
        metafunc.parametrize("invalid_signup_user", invalid_signups, ids=[user.get("test_name", str(i)) for i, user in enumerate(invalid_signups)])
    # CHANGED: Added contact_us_user fixture for Contact Us form test
    if "contact_us_user" in metafunc.fixturenames:
        data_file = Path(__file__).parent / "data" / "users.yaml"
        with data_file.open("r", encoding="utf-8") as handle:
            contact_us_users = yaml.safe_load(handle).get("contact_us_users", [])
        metafunc.parametrize("contact_us_user", contact_us_users, ids=[user.get("test_name", str(i)) for i, user in enumerate(contact_us_users)])
    # CHANGED: Added search_product fixture for Search Product test
    if "search_product" in metafunc.fixturenames:
        data_file = Path(__file__).parent / "data" / "users.yaml"
        with data_file.open("r", encoding="utf-8") as handle:
            search_products = yaml.safe_load(handle).get("search_products", [])
        metafunc.parametrize("search_product", search_products, ids=[product.get("test_name", str(i)) for i, product in enumerate(search_products)])
    # CHANGED: Added subscription_email fixture for Subscription test
    if "subscription_email" in metafunc.fixturenames:
        data_file = Path(__file__).parent / "data" / "users.yaml"
        with data_file.open("r", encoding="utf-8") as handle:
            subscription_emails = yaml.safe_load(handle).get("subscription_emails", [])
        metafunc.parametrize("subscription_email", subscription_emails, ids=[email_data.get("test_name", str(i)) for i, email_data in enumerate(subscription_emails)])


@pytest.fixture
def report_steps():
    steps = []
    yield steps


# Fixture to capture logs for each test
@pytest.fixture
def log_capture(caplog):
    yield caplog


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        steps = item.funcargs.get("report_steps", None)
        log_capture = item.funcargs.get("log_capture", None)
        extra = getattr(report, "extra", [])
        if steps:
            html = (
                "<div class='report-steps'><strong>Test Steps</strong>"
                "<ol>" + "".join(f"<li>{step}</li>" for step in steps) + "</ol></div>"
            )
            extra.append(extras.html(html))
        if log_capture:
            log_html = (
                "<div class='log-capture'><strong>Captured Logs</strong>"
                f"<pre>{log_capture.text}</pre></div>"
            )
            extra.append(extras.html(log_html))
        report.extra = extra


def pytest_html_report_title(report):
    report.title = "Automation Exercise Test Report"


@pytest.fixture(scope="session")
def browser(browser_type, pytestconfig):
    # Launch headed if --headed is passed, otherwise headless
    headless = not pytestconfig.getoption("--headed")
    browser = browser_type.launch(headless=headless)
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def context(browser):
    context = browser.new_context()
    context.set_default_navigation_timeout(60000)
    context.set_default_timeout(60000)
    yield context
    context.close()


@pytest.fixture(scope="session")
def page(context):
    page = context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="session")
def base_url():
    return "http://automationexercise.com"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item):

    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:

        page = item.funcargs.get("page")

        if page:
            os.makedirs("Snapshots", exist_ok=True)

            page.screenshot(
                path=f"Snapshots/{item.name}.png",
                full_page=True
            )
