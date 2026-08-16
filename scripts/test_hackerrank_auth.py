import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://www.hackerrank.com/login.html"
SUBMISSIONS_URL = "https://www.hackerrank.com/submissions/all"


def visible_input(driver, selectors):
    for selector in selectors:
        for element in driver.find_elements(By.CSS_SELECTOR, selector):
            if element.is_displayed() and element.is_enabled():
                return element
    return None


def dump_login_diagnostics(driver):
    Path("hackerrank-login-diagnostics").mkdir(exist_ok=True)
    driver.save_screenshot("hackerrank-login-diagnostics/login.png")
    Path("hackerrank-login-diagnostics/page.html").write_text(
        driver.page_source, encoding="utf-8"
    )
    print(f"Login title: {driver.title}")
    print(f"Login URL: {driver.current_url.split('?')[0]}")
    print("Visible body text (first 3000 chars):")
    print(driver.find_element(By.TAG_NAME, "body").text[:3000])
    print("Input elements found:")
    for i, element in enumerate(driver.find_elements(By.CSS_SELECTOR, "input")):
        print(
            f"  input[{i}] type={element.get_attribute('type')!r} "
            f"name={element.get_attribute('name')!r} "
            f"placeholder={element.get_attribute('placeholder')!r} "
            f"aria-label={element.get_attribute('aria-label')!r} "
            f"displayed={element.is_displayed()} enabled={element.is_enabled()}"
        )


def main():
    email = os.environ.get("HACKERRANK_EMAIL")
    password = os.environ.get("HACKERRANK_PASSWORD")

    if not email:
        raise SystemExit("HACKERRANK_EMAIL secret is missing.")
    if not password:
        raise SystemExit("HACKERRANK_PASSWORD secret is missing.")

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-US")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)

    try:
        print("Opening HackerRank login page...")
        driver.get(LOGIN_URL)

        try:
            wait.until(
                lambda d: visible_input(
                    d,
                    [
                        'input[type="email"]',
                        'input[name="email"]',
                        'input[name="username"]',
                        'input[placeholder*="Email"]',
                        'input[placeholder*="email"]',
                        'input[placeholder*="Username"]',
                        'input[placeholder*="username"]',
                        'input[placeholder*="Your username or email"]',
                    ],
                )
            )
        except TimeoutException:
            dump_login_diagnostics(driver)
            raise

        email_input = visible_input(
            driver,
            [
                'input[type="email"]',
                'input[name="email"]',
                'input[name="username"]',
                'input[placeholder*="Email"]',
                'input[placeholder*="email"]',
                'input[placeholder*="Username"]',
                'input[placeholder*="username"]',
                'input[placeholder*="Your username or email"]',
            ],
        )
        password_input = wait.until(
            lambda d: visible_input(
                d,
                [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[placeholder*="Password"]',
                    'input[placeholder*="password"]',
                    'input[placeholder*="Your password"]',
                ],
            )
        )

        email_input.clear()
        email_input.send_keys(email)
        password_input.clear()
        password_input.send_keys(password)

        submit = visible_input(
            driver,
            [
                'button[type="submit"]',
                'input[type="submit"]',
                'button',
            ],
        )
        if submit is None:
            raise RuntimeError("Could not find the HackerRank login button.")

        submit.click()
        time.sleep(5)
        print(f"Post-login URL: {driver.current_url.split('?')[0]}")

        if "/auth/login" in driver.current_url or "/login.html" in driver.current_url:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "captcha" in body or "recaptcha" in body:
                raise RuntimeError("HackerRank presented a CAPTCHA/anti-bot challenge during login.")
            raise RuntimeError("HackerRank login did not leave the login page.")

        print("HackerRank email/password authentication succeeded.")

        print("Opening authenticated submissions page...")
        driver.get(SUBMISSIONS_URL)
        wait.until(lambda d: "/submissions" in d.current_url)
        time.sleep(3)

        body = driver.find_element(By.TAG_NAME, "body").text
        print(f"Authenticated submissions URL: {driver.current_url.split('?')[0]}")

        lower_body = body.lower()
        if "you have not made any submissions yet" in lower_body:
            print("Submission history is empty, as expected for this account.")
        else:
            print("Submission page is accessible; no assumption is made about submission count yet.")

        print("HackerRank read-only authentication/submissions access test passed.")

    except TimeoutException as exc:
        raise RuntimeError("Timed out while interacting with the current HackerRank login/submissions UI.") from exc
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
