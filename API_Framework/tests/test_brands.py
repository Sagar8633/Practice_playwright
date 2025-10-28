# tests/test_brands.py

import allure # Import allure

@allure.epic("API Automation Exercise") # High-level grouping for your entire project
@allure.feature("Brand Catalog & Management") # Feature related to this test file
class TestBrandAPI: # Wrap related tests in a class
    @allure.story("Brand Listing") # Specific story for getting all brands
    @allure.title("Get all brands list successfully (API 3)") # More descriptive title
    def test_api3_get_all_brands(self, api_with_allure_logging): # <<-- Change fixture name
        """API 3: GET /api/brandsList → 200 with brands list."""
        with allure.step("Send GET request to /api/brandsList"):
            response = api_with_allure_logging.get("/api/brandsList") # <<-- Use the logging fixture

        with allure.step("Verify HTTP status code is 200"):
            assert response.status == 200

        data = response.json()
        with allure.step("Verify API responseCode is 200 and 'brands' key exists"):
            assert data["responseCode"] == 200
            assert "brands" in data
            assert len(data["brands"]) > 0

        with allure.step("Validate structure of the first brand"):
            brand = data["brands"][0]
            assert "id" in brand
            assert "brand" in brand


    @allure.story("Brand Management - Negative Scenarios") # Specific story for negative testing
    @allure.title("Attempt PUT to /api/brandsList - Method Not Allowed (API 4)") # More descriptive title
    def test_api4_put_to_brands_not_allowed(self, api_with_allure_logging): # <<-- Change fixture name
        """API 4: PUT /api/brandsList → 405 Method Not Allowed (indicated in response body)."""
        with allure.step("Send PUT request to /api/brandsList"):
            response = api_with_allure_logging.put("/api/brandsList") # <<-- Use the logging fixture

        with allure.step("Verify HTTP status code is 200 (as per API design for errors)"):
            assert response.status == 200

        data = response.json()
        with allure.step("Verify API responseCode is 405 and correct error message"):
            assert data["responseCode"] == 405
            assert data["message"] == "This request method is not supported."