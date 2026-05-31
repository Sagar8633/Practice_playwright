# Playwright Data-Driven POM Framework

This repository contains a Python + Playwright automation framework using:
- Page Object Model (POM)
- Data-driven tests via YAML fixtures
- Pytest for execution

## Install

1. Create a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
3. Install Playwright browsers:
   ```powershell
   python -m playwright install
   ```

## Run tests

```powershell
pytest
```

## View the test report

After the test run, open `reports/report.html` in your browser to inspect the generated HTML report. The report now includes a friendly "Test Steps" section for each executed test.

The framework keeps the browser and page open across the full test session, so cache or in-memory browser state issues are preserved and can be detected between tests.

## Add new test data

Edit `data/users.yaml` and add additional user blocks under `users:`.

## Extend the framework

- Add page actions in `pages/`
- Add new tests in `tests/`
- Use YAML values in `data/users.yaml` for additional scenarios
