import os
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://www.hackerrank.com/auth/login"
SUBMISSIONS_URL = "https://www.hackerrank.com/submissions/all"


def visible_input(driver, selectors):
    for selector in selectors:
        for element in driver.find_elements(By.CSS_SELECTOR, selector):
            if element.is_displayed() and element.is_enabled():
                return element
    return None


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

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    try:
        print("Opening HackerRank login page...")
        driver.get(LOGIN_URL)

        email_input = wait.until(
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
                ],
            )
        )
        password_input = wait.until(
            lambda d: visible_input(
                d,
                [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[placeholder*="Password"]',
                    'input[placeholder*="password"]',
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

        # Give redirects/client-side authentication a short window to settle.
        time.sleep(3)
        print(f"Post-login URL: {driver.current_url.split('?')[0]}")

        if "/auth/login" in driver.current_url:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "captcha" in body or "recaptcha" in body:
                raise RuntimeError("HackerRank presented a CAPTCHA/anti-bot challenge during login.")
            raise RuntimeError("HackerRank login did not leave the login page.")

        print("HackerRank email/password authentication succeeded.")

        print("Opening authenticated submissions page...")
        driver.get(SUBMISSIONS_URL)
        wait.until(lambda d: "/submissions" in d.current_url)
        time.sleep(2)

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
