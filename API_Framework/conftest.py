import pytest
import json
from playwright.sync_api import sync_playwright, Playwright, APIRequestContext
import allure
from typing import Generator, Any


# 1. Define the 'playwright_instance' fixture.
@pytest.fixture(scope="session")
def playwright_instance() -> Generator[Playwright, Any, None]:
    """
    Provides a Playwright instance for the test session.
    """
    with sync_playwright() as p:
        yield p


# 2. Define the 'api_client' fixture.
@pytest.fixture(scope="session")
def api_client(playwright_instance: Playwright) -> Generator[APIRequestContext, Any, None]:
    """
    Provides an APIRequestContext for making HTTP requests.
    """
    request_context = playwright_instance.request.new_context(base_url="https://automationexercise.com")
    yield request_context
    request_context.dispose()


# 3. Define the 'api_with_allure_logging' fixture.
@pytest.fixture(scope="function", autouse=False)
def api_with_allure_logging(api_client: APIRequestContext):
    """
    A wrapper for api_client that logs requests and responses to Allure steps.
    """

    class AllureLoggingAPIClient:
        def __getattr__(self, name):
            original_method = getattr(api_client, name)

            if callable(original_method) and name in ["get", "post", "put", "delete", "patch", "head"]:
                def wrapped_method(url, **kwargs):
                    method_name = name.upper()
                    request_details = f"URL: {url}\nMethod: {method_name}\n"
                    if 'params' in kwargs:
                        request_details += f"Params: {kwargs['params']}\n"
                    if 'data' in kwargs:
                        request_details += f"Data (form/body): {kwargs['data']}\n"
                    if 'json' in kwargs:
                        request_details += f"JSON Body: {kwargs['json']}\n"
                    if 'headers' in kwargs:
                        request_details += f"Headers: {kwargs['headers']}\n"

                    with allure.step(f"API {method_name} Request to {url}"):
                        allure.attach(request_details, name="Request Details",
                                      attachment_type=allure.attachment_type.TEXT)

                        response = original_method(url, **kwargs)

                        # We'll assign this within the try/except block to ensure it always gets a value
                        # and is then used. No initial empty string assignment needed here.

                        response_content_for_summary: str  # Declare type to help linters, no initial value

                        try:
                            # Attempt to parse as JSON
                            response_json = response.json()
                            pretty_json_str = json.dumps(response_json, indent=2)
                            allure.attach(pretty_json_str, name="Response JSON",
                                          attachment_type=allure.attachment_type.JSON)
                            response_content_for_summary = pretty_json_str
                        except json.JSONDecodeError:
                            # If JSON parsing fails, use raw text
                            response_raw_text = response.text()
                            allure.attach(response_raw_text, name="Response Body (Raw)",
                                          attachment_type=allure.attachment_type.TEXT)
                            response_content_for_summary = response_raw_text

                        response_summary = (
                            f"Status: {response.status} {response.status_text}\n"
                            f"URL: {response.url}\n"
                            f"Response Body (partial): {response_content_for_summary[:500]}..."
                        )
                        allure.attach(response_summary, name="Response Summary",
                                      attachment_type=allure.attachment_type.TEXT)
                        allure.attach(str(response.headers), name="Response Headers",
                                      attachment_type=allure.attachment_type.TEXT)

                        return response

                return wrapped_method
            return original_method

    return AllureLoggingAPIClient()