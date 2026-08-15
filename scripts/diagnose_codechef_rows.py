import os
import re
from bs4 import BeautifulSoup
from scripts.codechef_adapter import build_driver, _login


def main():
    username = os.environ["CODECHEF_USERNAME"]
    password = os.environ["CODECHEF_PASSWORD"]
    driver = build_driver()
    try:
        _login(driver, username, password)
        driver.get(f"https://www.codechef.com/users/{username}")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        print(f"PROFILE URL: {driver.current_url}")
        rows = soup.select("tr")
        print(f"ROWS: {len(rows)}")
        for i, row in enumerate(rows, 1):
            links = [(a.get_text(" ", strip=True), a.get("href", "")) for a in row.select("a[href]")]
            text = " ".join(row.stripped_strings)
            if any("/viewsolution/" in href or "/problems/" in href for _, href in links):
                print(f"ROW[{i}] TEXT={text!r}")
                print(f"ROW[{i}] LINKS={links!r}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
