# tests/products.py

import allure # Make sure to import allure

@allure.epic("API Automation Exercise") # High-level grouping for your entire project
@allure.feature("Product Catalog & Management") # Feature related to this test file
class TestProductAPI: # It's good practice to wrap related tests in a class
    @allure.story("Product Listing") # Specific story for getting all products
    @allure.title("Get all products list successfully (API 1)") # More descriptive title
    def test_api1_get_all_products(self, api_with_allure_logging): # <<-- Change fixture name
        """API 1: GET /api/productsList → 200 with products list."""
        with allure.step("Send GET request to /api/productsList"):
            response = api_with_allure_logging.get("/api/productsList") # <<-- Use the logging fixture

        with allure.step("Verify HTTP status code is 200"):
            assert response.status == 200

        data = response.json()
        with allure.step("Verify API responseCode is 200 and 'products' key exists"):
            assert data["responseCode"] == 200
            assert "products" in data
            assert len(data["products"]) > 0

        with allure.step("Validate structure of the first product"):
            product = data["products"][0]
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert "brand" in product
            assert "category" in product

            # Optionally, more detailed assertions for the category structure
            assert "usertype" in product["category"]
            assert "category" in product["category"]
            assert "usertype" in product["category"]["usertype"]


    @allure.story("Product Management - Negative Scenarios") # Specific story for negative testing
    @allure.title("Attempt POST to /api/productsList - Method Not Allowed (API 2)") # More descriptive title
    def test_api2_post_to_products_not_allowed(self, api_with_allure_logging): # <<-- Change fixture name
        """API 2: POST /api/productsList → 405 Method Not Allowed (indicated in response body)."""
        with allure.step("Send POST request to /api/productsList"):
            response = api_with_allure_logging.post("/api/productsList") # <<-- Use the logging fixture

        with allure.step("Verify HTTP status code is 200 (as per API design for errors)"):
            assert response.status == 200

        data = response.json()
        with allure.step("Verify API responseCode is 405 and correct error message"):
            assert data["responseCode"] == 405
            assert data["message"] == "This request method is not supported."