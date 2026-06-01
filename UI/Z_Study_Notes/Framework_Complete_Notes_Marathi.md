# Playwright + Pytest Framework — संपूर्ण नोट्स (Interview दृष्टिकोनातून)

> हा फाइल अभ्यासासाठी आहे. इथे आपल्या `d:\Practice_Playwright\UI` framework मधला प्रत्येक topic detail मध्ये, coding logic + Playwright methods सकट, मराठीत समजावला आहे.

---

## अनुक्रमणिका (Table of Contents)
1. Framework म्हणजे काय आणि का (Overview)
2. Tech Stack आणि Folder Structure
3. Design Pattern — Page Object Model (POM)
4. `pytest.ini` — Configuration
5. `conftest.py` — Fixtures + Hooks + Data-driven
6. `BasePage` — common methods चा पाया
7. Page Objects (प्रत्येक page चं काम)
8. Test files — रचना (Arrange-Act-Assert)
9. Data-Driven Testing (YAML + parametrize)
10. वापरलेल्या सर्व Playwright Methods (detail)
11. Locator Strategies (selectors)
12. Assertions (`expect`) आणि Auto-waiting
13. Reporting (pytest-html, screenshots, logs)
14. आपण fix केलेले Real Bugs (interview gold)
15. Framework कसा run करायचा
16. Interview Questions & Answers

---

## 1. Framework म्हणजे काय आणि का (Overview)

**Framework** म्हणजे test automation साठी एक structured, reusable setup. नुसते scripts न लिहिता आपण एक अशी रचना बनवतो जिथे:
- **code reuse** होतो (एकच method अनेक tests वापरतात),
- **maintenance सोपं** होतं (locator बदलला तर एकाच ठिकाणी बदलतो),
- **data वेगळा** ठेवतो (YAML मध्ये), code वेगळा,
- **reporting + screenshots** आपोआप मिळतात.

आपलं framework **automationexercise.com** या practice website वर UI tests चालवतं.

**मुख्य घटक (components):**
- **Playwright** → browser automation library (clicks, fill, navigation).
- **Pytest** → test runner (tests शोधणं, चालवणं, fixtures, reporting).
- **pytest-playwright** → Playwright ला pytest सोबत जोडणारा plugin (browser/context/page fixtures देतो).
- **pytest-html** → HTML report बनवतो.
- **PyYAML** → YAML test data वाचतो.
- **Page Object Model (POM)** → design pattern.

---

## 2. Tech Stack आणि Folder Structure

```
UI/
├── conftest.py          # सर्व fixtures + pytest hooks (framework चा "brain")
├── pytest.ini           # pytest configuration
├── requirements.txt     # dependencies
├── data/
│   ├── users.yaml       # सर्व test data (users, payment, search इ.)
│   └── test_file.txt    # contact-us form च्या upload साठी
├── pages/               # Page Object Model — प्रत्येक web page चा एक class
│   ├── base_page.py     # सर्व pages चा parent (common methods)
│   ├── home_page.py
│   ├── products_page.py
│   ├── product_detail_page.py
│   ├── cart_page.py
│   ├── checkout_page.py
│   ├── payment_page.py
│   ├── signup_login_page.py
│   ├── account_creation_page.py
│   ├── account_created_page.py
│   ├── account_page.py
│   ├── contact_us_page.py
│   ├── category_page.py
│   ├── brand_page.py
│   └── test_cases_page.py
├── tests/               # actual test cases (फक्त "काय test करायचं" — कसं ते pages मध्ये)
│   └── test_*.py
├── reports/
│   └── report.html      # pytest-html report
└── Snapshots/
    └── <date>/          # fail झालेल्या tests चे screenshots
```

**Interview point:** "मी layered architecture वापरतो — **Tests layer** (काय करायचं), **Pages layer** (कसं करायचं), **Data layer** (कोणत्या data ने). त्यामुळे separation of concerns मिळतं."

---

## 3. Design Pattern — Page Object Model (POM)

**POM** म्हणजे: प्रत्येक web page साठी एक वेगळा **Python class**. त्या class मध्ये —
- **Locators** (elements कुठे आहेत — selectors),
- **Methods/Actions** (त्या page वर काय करता येतं — click, fill, verify).

**फायदे (interview मध्ये नक्की सांगा):**
1. **Reusability** — एकच `login()` method अनेक tests वापरतात.
2. **Maintainability** — website वर locator बदलला तर फक्त त्या page class मध्ये बदलतो, सगळ्या tests मध्ये नाही.
3. **Readability** — test वाचताना business flow कळतो (`home_page.click_signup_login()`), selectors चा गोंधळ नसतो.
4. **Less duplication** — DRY principle (Don't Repeat Yourself).

**आपल्या framework मधलं उदाहरण:**
```python
class HomePage(BasePage):
    products_button = ".shop-menu a[href='/products']"   # Locator

    def click_products_button(self):                      # Action
        self.click(self.products_button)
        self.page.wait_for_load_state("domcontentloaded")
```
Test मध्ये फक्त: `home_page.click_products_button()` — selector test ला माहीत नसतो.

**Inheritance:** सर्व page classes `BasePage` कडून inherit होतात → common methods (`click`, `fill`, `goto`) सगळीकडे मिळतात.

---

## 4. `pytest.ini` — Configuration

```ini
[pytest]
addopts = -q --html=reports/report.html --self-contained-html
python_files = tests/*.py
markers =
    data_driven: mark tests that use data-driven inputs
```

- **`addopts`** → प्रत्येक वेळी default command-line options:
  - `-q` = quiet output,
  - `--html=reports/report.html` = HTML report बनव,
  - `--self-contained-html` = सगळं CSS/JS एकाच html file मध्ये (share करायला सोपं).
- **`python_files = tests/*.py`** → pytest कोणत्या files मध्ये tests शोधेल.
- **`markers`** → custom markers register करणं (warning टाळण्यासाठी). उदा. `@pytest.mark.data_driven`.

> **टीप:** आपल्याकडे काही markers (`review`, `recommended_items`, `scroll_functionality`) register केलेले नाहीत म्हणून `PytestUnknownMarkWarning` येतं. ते इथे add केले की warning जातं.

---

## 5. `conftest.py` — Fixtures + Hooks + Data-driven (Framework चा brain)

`conftest.py` ही special file आहे — pytest ती automatically load करतो. इथले fixtures कोणत्याही test ला नुसतं **parameter** म्हणून मागितले की मिळतात (dependency injection).

### 5.1 Fixtures म्हणजे काय?
**Fixture** = test च्या आधी setup आणि नंतर teardown करणारं function. Test ला फक्त नाव parameter म्हणून द्यायचं.

```python
@pytest.fixture
def page(context):
    page = context.new_page()   # setup (yield च्या आधी)
    yield page                  # test ला हे object मिळतं
    page.close()                # teardown (yield च्या नंतर)
```

### 5.2 Browser → Context → Page ची साखळी (hierarchy)
Playwright मध्ये तीन levels:
- **Browser** — पूर्ण browser process (Chromium). महाग (heavy), म्हणून `scope="session"` (एकदाच उघडतो).
- **Context** — browser मधलं एक isolated session (incognito सारखं — वेगळ्या cookies, storage). एका context मध्ये login केलं तर ते त्याच context पुरतं.
- **Page** — context मधला एक tab.

```python
@pytest.fixture(scope="session")
def browser(browser_type, pytestconfig):
    headless = not pytestconfig.getoption("--headed")  # --headed दिलं तर browser दिसेल
    browser = browser_type.launch(headless=headless)
    yield browser
    browser.close()

@pytest.fixture
def context(browser):
    context = browser.new_context()
    context.set_default_navigation_timeout(60000)  # navigation साठी 60s timeout
    context.set_default_timeout(60000)             # actions साठी 60s timeout
    yield context
    context.close()

@pytest.fixture
def page(context):
    page = context.new_page()
    yield page
    page.close()
```

**Fixture Scopes (महत्त्वाचं interview topic):**
| Scope | केव्हा नवीन बनतो |
|-------|------------------|
| `function` (default) | प्रत्येक test साठी नवीन |
| `class` | प्रत्येक class साठी एकदा |
| `module` | प्रत्येक file साठी एकदा |
| `session` | पूर्ण run मध्ये एकदाच |

> **आपण इथे एक मोठा bug fix केला:** `context` आणि `page` आधी `scope="session"` होते. म्हणजे **एकच page सगळ्या tests मध्ये share** होत होता → एका test मध्ये login केलं तर पुढच्या test ला तोच logged-in state मिळायचा → tests एकमेकांवर अवलंबून (order-dependent) होते. आपण ते **function scope** केलं → प्रत्येक test ला fresh, logged-out context मिळतो (**test isolation**). Browser मात्र session-scoped ठेवला (speed साठी).

### 5.3 `base_url` fixture
```python
@pytest.fixture(scope="session")
def base_url():
    return "http://automationexercise.com"
```
URL एकाच ठिकाणी — environment बदलायचं तर इथे बदलतो.

### 5.4 Data-Driven Parametrization — `pytest_generate_tests`
हा एक **hook** आहे. Test collect होताना pytest प्रत्येक test साठी हे function call करतो. इथे आपण YAML मधून data वाचून test ला **parametrize** करतो.

```python
def pytest_generate_tests(metafunc):
    if "login_user" in metafunc.fixturenames:   # test ने 'login_user' मागितला असेल तर
        login_users = yaml.safe_load(...)["login_users"]
        metafunc.parametrize(
            "login_user",
            login_users,
            ids=[u.get("test_name") for u in login_users]  # report मध्ये दिसणारी नावं
        )
```
म्हणजे YAML मध्ये 2 users असतील तर तोच test **2 वेळा** चालेल (प्रत्येक user साठी एकदा). हेच `user`, `contact_us_user`, `subscription_email`, `checkout_user`, `payment_data` साठी केलंय.

**Interview line:** "Data आणि test logic वेगळे ठेवण्यासाठी मी `pytest_generate_tests` + YAML वापरून data-driven testing केलं. नवीन data add करायला फक्त YAML edit करावा लागतो, code नाही."

### 5.5 Hook — `pytest_runtest_makereport` (Reporting चा गाभा)
हा hook प्रत्येक test नंतर चालतो. आपण इथे:
1. **Test steps** report मध्ये टाकतो (`report_steps` list मधून),
2. **Captured logs** टाकतो,
3. **Fail झाल्यास screenshot** घेतो आणि `Snapshots/<date>/` मध्ये save करतो.

```python
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield                       # आधी default report बनू देतो
    report = outcome.get_result()
    if report.when == "call":             # फक्त actual test run च्या वेळी
        if report.failed:
            page = item.funcargs.get("page")
            today = datetime.now().strftime("%Y-%m-%d")
            screenshot_dir = Path("Snapshots") / today
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_dir / f"{item.name}.png"), full_page=True)
```

- **`hookwrapper=True`** → `yield` च्या आधी = test च्या आधी, नंतर = test नंतर.
- **`item.funcargs`** → त्या test ला मिळालेले fixtures (इथून `page`, `report_steps` मिळतात).
- **`report.when == "call"`** → setup/teardown नाही, फक्त test body.

### 5.6 इतर fixtures
- **`report_steps`** → रिकामी list; test मध्ये steps append करतो, report मध्ये दिसतात.
- **`log_capture`** → pytest च्या `caplog` ने logs पकडतो.

---

## 6. `BasePage` — common methods चा पाया

सर्व page objects याच्याकडून inherit होतात. Constructor मध्ये `page` object ठेवतो:

```python
class BasePage:
    def __init__(self, page):
        self.page = page
```

### वापरलेल्या methods:

**`goto(url)`** — navigation with **retry logic** (network flaky असेल तर 3 वेळा प्रयत्न):
```python
def goto(self, url):
    for attempt in range(3):
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return
        except Exception as e:
            print(f"Navigation attempt {attempt + 1} failed: {e}")
    raise Exception(f"Failed to navigate to {url}")
```

**`click(selector)`** — आधी visible आहे का बघतो, मग click (safe click):
```python
def click(self, selector):
    locator = self.page.locator(selector)
    expect(locator).to_be_visible()   # auto-wait + assertion
    locator.click()
```

**`fill(selector, value)`** — input भरणं (आधी visibility check):
```python
def fill(self, selector, value):
    locator = self.page.locator(selector)
    expect(locator).to_be_visible()
    locator.fill(value)
```

**`check(selector)`** — checkbox/radio select करणं → `locator.check()`.

**`select_option(selector, value)`** — dropdown मधून value निवडणं → `locator.select_option(value)`.

**`expect_visible(selector, text=None, timeout=None)`** — element दिसतंय / त्यात text आहे हे verify:
```python
def expect_visible(self, selector, text=None, timeout=None):
    locator = self.page.locator(selector)
    if text:
        expect(locator).to_have_text(text, timeout=timeout)
    else:
        expect(locator).to_be_visible(timeout=timeout)
```

**`expect_text_contains(selector, text)`** → `expect(locator).to_contain_text(text)` (substring match).

**`click_and_wait_for_navigation(selector)`** — click केल्यावर page बदलणार असेल तर navigation ची वाट बघतो (logout साठी):
```python
def click_and_wait_for_navigation(self, selector):
    with self.page.expect_navigation():
        self.page.locator(selector).click()
    self.page.wait_for_load_state('domcontentloaded')
```

**`take_screenshot(name)`** — `Snapshots/<date>/` मध्ये full-page screenshot.

**Interview point:** "मी common actions (`click`, `fill`) BasePage मध्ये wrap केल्या जेणेकरून प्रत्येक click आधी **explicit visibility check** होईल — त्यामुळे flakiness कमी होतं आणि fail झाला तर नक्की कुठे ते कळतं."

---

## 7. Page Objects (प्रत्येक page चं काम थोडक्यात)

| Page Object | जबाबदारी | महत्त्वाच्या methods |
|-------------|----------|---------------------|
| `HomePage` | होम पेज, navbar, category sidebar, subscription, recommended items, scroll | `open`, `verify_home_is_visible`, `click_signup_login`, `click_cart_button`, `subscribe_with_email`, `click_women_category`, `click_add_to_cart_on_recommended_item`, `scroll_to_top` |
| `ProductsPage` | All Products, search, brands | `verify_all_products_page_visible`, `search_product`, `click_first_product_view_button`, `add_all_search_results_to_cart`, `click_brand` |
| `ProductDetailPage` | product detail, add to cart, review | `verify_product_details_visible`, `add_to_cart`, `enter_review_name/email/text`, `click_submit_review` |
| `CartPage` | cart, subscription, remove product | `navigate_to_cart`, `verify_cart_page_visible`, `get_cart_items_count`, `remove_product_from_cart`, `proceed_to_checkout` |
| `CheckoutPage` | address + order review + comment | `verify_checkout_page_visible`, `verify_delivery_address_contains`, `enter_comment_and_place_order` |
| `PaymentPage` | payment form, order success, invoice | `enter_payment_details`, `pay_and_confirm_order`, `verify_success_message`, `download_invoice` |
| `SignupLoginPage` | signup + login forms | `verify_new_user_signup_visible`, `enter_signup_name_and_email`, `click_signup`, `enter_login_credentials`, `click_login` |
| `AccountCreationPage` | registration form (title, DOB, address) | `select_title`, `fill_account_information`, `fill_address_information`, `click_create_account` |
| `AccountCreatedPage` | "Account Created!" | `verify_account_created_visible`, `click_continue` |
| `AccountPage` | logged-in state, delete, logout | `verify_logged_in_as`, `click_delete_account`, `click_logout` |
| `ContactUsPage` | contact form + file upload + dialog | `enter_name/email/subject/message`, `upload_file`, `click_submit` |
| `CategoryPage` / `BrandPage` | category/brand filtered products | `verify_category_heading_contains`, `verify_brand_products_displayed` |
| `TestCasesPage` | Test Cases page | `navigate_to_test_cases`, `get_test_cases_count` |

---

## 8. Test files — रचना (Arrange-Act-Assert / AAA pattern)

प्रत्येक test साधारण असा असतो:
```python
@pytest.mark.data_driven
def test_verify_subscription_in_home_page(page, base_url, subscription_email, report_steps):
    # 1) ARRANGE — page objects तयार
    home_page = HomePage(page)

    # 2) ACT — actions
    home_page.open(base_url)
    home_page.scroll_to_footer()
    home_page.subscribe_with_email(subscription_email["email"])

    # 3) ASSERT — verify
    home_page.verify_subscription_success_message()
```

**मुद्दे:**
- Test function ला fixtures **parameters** म्हणून मिळतात (`page`, `base_url`, `subscription_email`, `report_steps`).
- `@pytest.mark.data_driven` = marker (categorize करायला, `-m data_driven` ने फक्त हेच चालवता येतात).
- `report_steps.append(...)` ने प्रत्येक step report मध्ये नोंदवतो.
- Test मध्ये **selectors नसतात** — सगळं page objects मधून.

**AAA pattern (interview):** Arrange (setup) → Act (action) → Assert (verify). काही tests मध्ये `try/except` ने error catch करून report मध्ये टाकलं आहे (`test_download_invoice`).

---

## 9. Data-Driven Testing (YAML + parametrize)

`data/users.yaml` मध्ये वेगवेगळे sections:
```yaml
login_users:
  - test_name: "login_user_correct_credentials"
    email_prefix: "testuser.login"
    password: "Password123"
    ...

payment_data:
  - test_name: "valid_payment_info"
    card_number: "4111111111111111"
    cvc: "123"
    ...
```

**Flow:**
1. Test ला `login_user` parameter हवा.
2. `pytest_generate_tests` बघतो की test ला `login_user` हवा → YAML वाचतो → `metafunc.parametrize` ने प्रत्येक entry साठी एक test instance बनवतो.
3. Report मध्ये `ids` मुळे `test_name` दिसतं (उदा. `[login_user_correct_credentials-chromium]`).

**Unique email trick (महत्त्वाचं):** registration tests प्रत्येक run ला unique email बनवतात (नाहीतर "email already exists"):
```python
login_user["email"] = f"{login_user['email_prefix']}+{int(time.time())}@example.com"
```
`int(time.time())` = current timestamp → प्रत्येक वेळी वेगळा email.

---

## 10. वापरलेल्या सर्व Playwright Methods (detail मध्ये)

### Navigation
- **`page.goto(url, wait_until="domcontentloaded", timeout=30000)`** — URL ला जा. `wait_until`: `load` / `domcontentloaded` / `networkidle`.
- **`page.wait_for_load_state("domcontentloaded")`** — page load होईपर्यंत थांब.
- **`page.url`** — सध्याचा URL (property).
- **`page.expect_navigation()`** — context manager; आत click केल्यावर navigation होईल याची वाट.

### Locators (element शोधणं)
- **`page.locator(selector)`** — CSS/XPath/text selector ने element. **Lazy** — लगेच शोधत नाही, action च्या वेळी शोधतो.
- **`page.get_by_role("link", name="Cart", exact=True)`** — accessibility role ने (user सारखं).
- **`page.get_by_text("Order Placed", exact=False)`** — text ने.
- **`locator.first` / `locator.nth(index)`** — अनेक matches मधला पहिला / n-वा.
- **`locator.filter(has_text=...)`** — आणखी narrow करणं.
- **`locator.count()`** — किती elements match झाले (assertion नाही, नुसती संख्या).

### Actions
- **`locator.click()`** — click. (auto-waits for actionable).
- **`locator.fill(value)`** — input clear करून value टाकणं.
- **`locator.check()`** — checkbox/radio select.
- **`locator.select_option(value)`** — `<select>` dropdown.
- **`locator.set_input_files(path)`** — file upload (contact-us form).
- **`locator.scroll_into_view_if_needed()`** — element दिसेपर्यंत scroll.
- **`locator.highlight()`** — debug साठी element highlight.

### State / Reading
- **`locator.is_visible()`** — visible आहे का (bool).
- **`locator.text_content()` / `locator.inner_text()`** — element मधला text.
- **`locator.inner_html()` / `locator.evaluate("e => e.outerHTML")`** — HTML (debug).
- **`locator.all_text_contents()`** — सगळ्या matches चे texts (list).

### Waiting
- **`locator.wait_for(state="visible", timeout=10000)`** — element specific state ची वाट (उदा. `#cartModal`).
- **`page.wait_for_timeout(1000)`** — fixed wait (शक्यतो टाळावं — flaky/slow).

### JavaScript
- **`page.evaluate("window.scrollTo(0, document.body.scrollHeight)")`** — browser मध्ये JS चालवणं (footer ला scroll).

### Dialogs (alert/confirm)
- **`page.once("dialog", handler)`** — native JS dialog (confirm box) handle. **Click च्या आधी** register करावं लागतं, कारण native dialog page block करतं:
```python
def handle_dialog(dialog):
    print(dialog.message)
    dialog.accept()
page.once("dialog", handle_dialog)
contact_us_page.click_submit()
```
> टीप: Python Playwright मध्ये `page.expect_dialog()` नाही (तो फक्त JS/TS API). म्हणून `page.once(...)`.

### Downloads
- **`page.expect_download()`** — context manager; आत download trigger करणारी click:
```python
with self.page.expect_download() as download_info:
    download_button.click()
download = download_info.value
download.save_as("reports/invoice.txt")
print(download.suggested_filename)
```

### Screenshots
- **`page.screenshot(path=..., full_page=True)`** — screenshot.

---

## 11. Locator Strategies (selectors) — कोणता कधी

| Strategy | उदाहरण | केव्हा |
|----------|--------|--------|
| **CSS id** | `#scrollUp`, `input#password` | id असेल तर सर्वात fast/stable |
| **CSS attribute** | `input[data-qa='login-email']` | `data-qa` सारखे test hooks असतील तर best |
| **CSS class scoped** | `.shop-menu a[href='/products']` | navbar मधलाच link हवा असेल तर |
| **Text** | `text=SUBSCRIPTION`, `a:has-text('Write Your Review')` | text दिसतोय पण stable attr नाही |
| **XPath** | `//h2[text()='Login to your account']`, `//b[text()='Account Created!']` | exact text / structure हवं तेव्हा |
| **Role (a11y)** | `get_by_role("link", name="Cart")` | user-facing, semantic |

**Best practice (interview):** प्राधान्यक्रम → `data-qa`/id > CSS attribute > role/text > XPath. XPath शक्यतो शेवटचा पर्याय.

**`:has-text()` vs `text=`:** `:has-text()` substring + कोणत्याही tag सोबत combine होतो (`a:has-text('...')`). `text=` हे whole/normalized text match.

---

## 12. Assertions (`expect`) आणि Auto-waiting

Playwright चं **`expect()`** हे **web-first / auto-retrying assertion** आहे. म्हणजे लगेच fail न होता **timeout पर्यंत retry** करतं (default context timeout = 60s इथे).

```python
from playwright.sync_api import expect
expect(locator).to_be_visible(timeout=10000)
expect(locator).to_have_text("Order Placed!")
expect(locator).to_contain_text("WOMEN", ignore_case=True)
expect(locator).to_be_hidden()
```

**वापरलेली matchers:**
- `to_be_visible()` / `to_be_hidden()`
- `to_have_text(text)` — पूर्ण text match (exact).
- `to_contain_text(text, ignore_case=True)` — substring match (`ignore_case` ने case ignore).

**Python `assert` vs Playwright `expect` (interview):**
- `assert x in page.url` — instant, retry नाही (नुसती Python assertion).
- `expect(locator).to_be_visible()` — auto-retry, UI साठी best.

**Strict Mode (फार महत्त्वाचं — आपण इथे bug fix केला):**
`expect(locator).to_be_visible()` जर locator ला **एकापेक्षा जास्त elements** match झाले तर **strict mode violation** error येतो. म्हणून selector unique असावा. उदा. `a[href='/view_cart']` navbar + modal दोन्ही match करायचा → आपण `.shop-menu a[href='/view_cart']` ने scope केला.

---

## 13. Reporting (pytest-html, screenshots, logs)

- **HTML report:** `pytest.ini` मधल्या `--html=reports/report.html --self-contained-html` मुळे प्रत्येक run ला `reports/report.html` बनतो.
- **Test steps:** `report_steps` list → `pytest_runtest_makereport` hook ती report मध्ये HTML `<ol>` म्हणून टाकतो.
- **Logs:** `log_capture` (caplog) → report मध्ये `<pre>` block.
- **Failure screenshots:** test fail झाला की hook आपोआप `Snapshots/<date>/<test_name>.png` बनवतो → debugging सोपं.
- **Report title:** `pytest_html_report_title` hook ने custom title ("Automation Exercise Test Report").

**Interview line:** "Failure वर full-page screenshot + step-by-step log report मध्ये येतो, त्यामुळे fail झाला तर browser परत न उघडता root cause कळतो."

---

## 14. आपण fix केलेले Real Bugs (हे interview मध्ये सोनं आहे)

> "तुम्ही कधी flaky/failing tests debug केलेत का?" — या प्रश्नाला ही उदाहरणं सांगा.

**Bug 1 — Test isolation (fixture scope):**
- *लक्षण:* `test_register_user` एकटा चालला तर pass, पूर्ण suite मध्ये fail (`Locator expected to be visible`).
- *कारण:* `context`/`page` fixtures `scope="session"` होते → एकच browser session सगळ्या tests मध्ये share → आधीच्या test चा logged-in state पुढच्या test ला मिळायचा.
- *Fix:* `context` व `page` ला **function scope** केलं (प्रत्येक test ला fresh context).

**Bug 2 — Strict mode violation (non-unique selector):**
- *लक्षण:* `strict mode violation: locator("a[href='/view_cart']") resolved to 2 elements`.
- *कारण:* navbar Cart link + add-to-cart modal चा "View Cart" — दोघांचा href सारखा.
- *Fix:* selector navbar पुरता scope — `.shop-menu a[href='/view_cart']`. तसंच `/products`, `/login` साठीही.

**Bug 3 — चुकीचा selector (tag/structure वेगळी):**
- "Write Your Review" `<h3>` नसून `<a>` tab होता → `h3:has-text(...)` ला 0 match. Fix: `a:has-text('Write Your Review')`.
- Review name/email inputs ला `name` attribute नाही, फक्त `id` → `input[name='name']` चुकीचा. Fix: `#name`, `#email`.
- Scroll-up arrow ला `href` नाही, फक्त `id` → `a[href='#scrollUp']` चुकीचा. Fix: `#scrollUp`.
- Checkout address `.address_left/.address_right` नसून `#address_delivery/#address_invoice`.

**Bug 4 — Case-sensitive text:**
- Heading DOM मध्ये "Women - Dress Products" पण test "WOMEN" शोधत होता (uppercase दिसतो तो CSS `text-transform` मुळे). Fix: `to_contain_text("WOMEN", ignore_case=True)`.

**Bug 5 — Carousel timing (race condition):**
- Recommended items auto-rotating carousel मध्ये → `nth(0)` कधी hidden slide वर पडायचा → add register व्हायचं नाही → cart empty.
- *Fix:* active slide वर scope (`.item.active a.add-to-cart`) + `#cartModal` दिसेपर्यंत वाट (म्हणजे add झाल्याची खात्री) मग navigate.

**Bug 6 — Brittle assertion (redirect):**
- Payment नंतर page `/payment_done/` ला redirect होतो; तिथे `#success_message` नसतं. `to_have_text("...successfully!")` fail.
- *Fix:* stable hook `[data-qa='order-placed']` ("Order Placed!") वर assert.

**Bug 7 — Logged-in असताना login link click:**
- Cleanup मध्ये delete account करण्याआधी `click_signup_login()` केलं — पण login असताना "Signup/Login" link नसतोच (navbar ला "Delete Account" थेट असतो). Fix: तो call काढून थेट `account_page.click_delete_account()`.

**Bug 8 — Wrong import (module-level fixture):**
- `from pytest_playwright... import page` ने **fixture function** module मध्ये import झाला; `print(page.url)` → `'FixtureFunctionDefinition' object has no attribute 'url'`. Fix: तो चुकीचा import + debug prints काढले.

---

## 15. Framework कसा run करायचा (commands)

```cmd
REM सर्व tests
python -m pytest -v

REM एकच file
python -m pytest tests/test_register_user.py -v -s

REM एकच test
python -m pytest "tests/test_register_user.py::test_register_user" -v

REM browser दिसण्यासाठी (headed)
python -m pytest tests/test_products.py --headed

REM marker ने filter
python -m pytest -m data_driven

REM print/console output बघण्यासाठी
python -m pytest -s

REM short traceback
python -m pytest --tb=short
```

- **`-v`** verbose, **`-s`** print दाखव, **`-k "नाव"`** नावाने filter, **`--tb=short/long/line`** traceback format.
- Report: `reports/report.html`. Fail screenshots: `Snapshots/<date>/`.

---

## 16. Interview Questions & Answers (quick revision)

**Q1. Page Object Model म्हणजे काय? फायदे?**
प्रत्येक page चा वेगळा class (locators + actions). फायदे: reusability, maintainability, readability, less duplication (DRY).

**Q2. Fixture म्हणजे काय? scope कोणते?**
Setup/teardown देणारं function (dependency injection). Scopes: function, class, module, session. आपण browser=session, context+page=function वापरले (isolation).

**Q3. `conftest.py` का?**
Shared fixtures + hooks ठेवायची special file; pytest ती auto-discover करतो, import न करता fixtures मिळतात.

**Q4. Data-driven testing कसं केलं?**
YAML मध्ये data + `pytest_generate_tests` hook + `metafunc.parametrize`. एकच test अनेक data sets वर चालतो.

**Q5. Playwright auto-waiting म्हणजे?**
`expect()` व actions actionable/visible होईपर्यंत timeout पर्यंत retry करतात → कमी explicit waits, कमी flakiness.

**Q6. Strict mode म्हणजे?**
Locator ला 1 पेक्षा जास्त element match झाले तर error. Selector unique ठेवावा लागतो.

**Q7. `assert` vs `expect`?**
`assert` instant, retry नाही (Python). `expect` auto-retrying web assertion (Playwright) — UI साठी best.

**Q8. CSS vs XPath, कोणता प्राधान्याने?**
`data-qa`/id > CSS attribute > role/text > XPath. XPath शेवटी (slow, brittle).

**Q9. Browser vs Context vs Page?**
Browser = process; Context = isolated session (incognito सारखं); Page = tab. Context login isolation साठी.

**Q10. Alert/confirm dialog कसा handle केला?**
`page.once("dialog", handler)` **click च्या आधी** register, मग `dialog.accept()`. (Python मध्ये `expect_dialog()` नाही.)

**Q11. File upload / download कसं?**
Upload: `locator.set_input_files(path)`. Download: `with page.expect_download() as info: ... ; info.value.save_as(...)`.

**Q12. Flaky test कसे debug केले?** → वरचा "Real Bugs" विभाग सांगा (isolation, strict mode, timing, selectors).

**Q13. Reporting कसं?**
pytest-html (`report.html`) + custom hook ने steps/logs/failure-screenshots.

**Q14. `wait_for_load_state` चे options?**
`load`, `domcontentloaded`, `networkidle`. आपण मुख्यतः `domcontentloaded` (networkidle flaky असू शकतो).

**Q15. Headless vs headed?**
Headless = browser UI न दिसता (CI साठी fast). `--headed` ने दिसतो (debug). आपण `pytestconfig.getoption("--headed")` ने control केलं.

---

### एका ओळीत framework (elevator pitch)
"Python + Playwright + Pytest वर **Page Object Model** based UI automation framework. **YAML data-driven**, **fixtures/hooks** ने setup-teardown + reporting, **pytest-html report** आणि **failure वर auto-screenshot**. Selectors page objects मध्ये centralize, त्यामुळे maintainable + scalable."
