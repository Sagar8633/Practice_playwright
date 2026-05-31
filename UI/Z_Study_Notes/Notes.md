# Playwright Automation Framework - Interview Notes (मराठी)

## Project Summary

मी AutomationExercise वेबसाईटसाठी Playwright + Python वापरून Page Object Model (POM) आधारित Automation Framework तयार केला.

Final Result:

```text
14 Passed
0 Failed
```

---

# Q1. Page Object Model (POM) म्हणजे काय?

### Answer

POM हा Design Pattern आहे ज्यामध्ये प्रत्येक Page साठी स्वतंत्र Class तयार केली जाते.

उदाहरण:

```python
HomePage
CartPage
ProductsPage
LoginPage
```

यामुळे:

* Code Reusability वाढते
* Maintenance सोपी होते
* Locators एका ठिकाणी राहतात
* Test Cases Clean राहतात

---

# Q2. BasePage का तयार केला?

### Answer

Common methods सर्व pages मध्ये repeat होऊ नयेत म्हणून.

उदाहरण:

```python
click()
fill()
goto()
expect_visible()
```

हे BasePage मध्ये ठेवले.

बाकी सर्व pages:

```python
class HomePage(BasePage):
```

inherit करतात.

---

# Q3. Playwright Auto Wait म्हणजे काय?

### Answer

Playwright action करण्यापूर्वी element:

* Visible आहे का
* Enabled आहे का
* Stable आहे का

हे स्वतः check करतो.

उदाहरण:

```python
locator.click()
```

Playwright internally wait करतो.

---

# Q4. Hard Wait आणि Smart Wait मधला फरक?

### Wrong

```python
page.wait_for_timeout(5000)
```

Problem:

* Page 1 second मध्ये load झाला तरी 5 sec waste
* Page 7 second घेत असेल तर fail

### Correct

```python
expect(locator).to_be_visible()
```

किंवा

```python
locator.wait_for()
```

---

# Q5. Strict Mode Violation म्हणजे काय?

### Error

```text
strict mode violation
locator resolved to multiple elements
```

### Reason

Locator unique नाही.

उदाहरण:

```python
a[href='/view_cart']
```

Page वर multiple elements होते.

---

### Fix

```python
page.get_by_role(
    "link",
    name="Cart"
)
```

---

# Q6. Locator Strategy Interview Question

### Priority Order

1. get_by_role()
2. get_by_label()
3. get_by_placeholder()
4. get_by_text()
5. CSS Selector

---

### Example

Wrong

```python
a[href='/view_cart']
```

Better

```python
get_by_role(
    "link",
    name="Cart"
)
```

---

# Q7. Cart Page Issue कसा Fix केला?

### Problem

```text
strict mode violation
76 elements found
```

### Wrong Locator

```python
a:has-text('Cart')
```

### Fix

```python
self.page.get_by_role(
    "link",
    name="Cart"
).click()
```

---

# Q8. Test Cases Page Issue

### Problem

```python
text=Test Cases
```

Page वर multiple matches.

### Error

```text
resolved to 7 elements
```

### Fix

```python
b:has-text('Test Cases')
```

Specific locator वापरला.

---

# Q9. Contact Us Issue

### Problem

```python
expect_navigation()
```

वापरले होते.

### Actual Behaviour

Submit नंतर page redirect होत नव्हता.

फक्त success message येत होता.

### Fix

```python
expect(success_message).to_be_visible()
```

---

# Q10. Expect Navigation कधी वापरायचे?

### Use

Login

```python
Login -> Home
```

Logout

```python
Home -> Login
```

Product Details

```python
Product List -> Product Detail
```

---

### Avoid

Success Popup

Toast Message

Validation Message

Same Page Form Submission

---

# Q11. Scroll Handling

### Old

```python
window.scrollTo()
wait_for_timeout()
```

### Better

```python
locator.scroll_into_view_if_needed()
```

---

# Q12. Assertion म्हणजे काय?

Application ची expected behaviour verify करणे.

उदाहरण:

```python
assert "view_cart" in page.url
```

किंवा

```python
expect(locator).to_be_visible()
```

---

# Q13. Framework मध्ये वापरलेले Concepts

### Python

* Classes
* Objects
* Inheritance
* Functions
* Exception Handling

### Playwright

* Locators
* Assertions
* Auto Wait
* Browser Context
* Page Object Model

### Pytest

* Fixtures
* Parametrization
* Markers
* HTML Reports

---

# Q14. Exception Handling Example

```python
for attempt in range(3):
    try:
        page.goto(url)
        return
    except Exception:
        pass
```

Use Case:

Retry navigation failures.

---

# Q15. Why BasePage?

Benefits:

* Reusable code
* Centralized changes
* Better maintainability

---

# Q16. Real Interview Question

### Question

How do you debug Playwright failures?

### Answer

Step 1

Read failure log.

Step 2

Check locator count.

```python
print(locator.count())
```

Step 3

Verify locator uniqueness.

Step 4

Verify page state.

Step 5

Check screenshots.

Step 6

Fix locator instead of increasing timeout.

---

# Q17. What did I learn from this project?

* Playwright Auto Wait
* Locator Strategy
* Strict Mode Handling
* Page Object Model
* Framework Design
* Debugging Failures
* Assertions
* Synchronization
* Test Maintenance

---

# Final Learning

Golden Rule:

```text
Never fix a locator problem by increasing timeout.
```

First verify:

1. Locator unique आहे का?
2. Element visible आहे का?
3. Page navigation होते का?
4. Correct assertion आहे का?

त्यानंतरच timeout विचारात घ्या.
