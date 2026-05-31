from .base_page import BasePage


class AccountCreationPage(BasePage):
    account_information_label = "text=Account Information"
    title_mr = "input[id='id_gender1']"
    title_mrs = "input[id='id_gender2']"
    password_field = "input[id='password']"
    days_select = "select[id='days']"
    months_select = "select[id='months']"
    years_select = "select[id='years']"
    newsletter_checkbox = "input[id='newsletter']"
    offers_checkbox = "input[id='optin']"
    first_name_field = "input[id='first_name']"
    last_name_field = "input[id='last_name']"
    company_field = "input[id='company']"
    address1_field = "input[id='address1']"
    address2_field = "input[id='address2']"
    country_select = "select[id='country']"
    state_field = "input[id='state']"
    city_field = "input[id='city']"
    zipcode_field = "input[id='zipcode']"
    mobile_number_field = "input[id='mobile_number']"
    create_account_button = "button[data-qa='create-account']"

    def verify_account_information_visible(self):
        self.expect_visible(self.account_information_label)

    def select_title(self, title: str):
        if title.lower() == "mr":
            self.check(self.title_mr)
        else:
            self.check(self.title_mrs)

    def fill_account_information(self, password: str, dob: dict, newsletter: bool, offers: bool):
        self.fill(self.password_field, password)
        self.select_option(self.days_select, dob["day"])
        self.select_option(self.months_select, dob["month"])
        self.select_option(self.years_select, dob["year"])
        if newsletter:
            self.check(self.newsletter_checkbox)
        if offers:
            self.check(self.offers_checkbox)

    def fill_address_information(self, user: dict):
        self.fill(self.first_name_field, user["first_name"])
        self.fill(self.last_name_field, user["last_name"])
        self.fill(self.company_field, user["company"])
        self.fill(self.address1_field, user["address1"])
        self.fill(self.address2_field, user["address2"])
        self.select_option(self.country_select, user["country"])
        self.fill(self.state_field, user["state"])
        self.fill(self.city_field, user["city"])
        self.fill(self.zipcode_field, user["zipcode"])
        self.fill(self.mobile_number_field, user["mobile_number"])

    def click_create_account(self):
        self.click(self.create_account_button)
