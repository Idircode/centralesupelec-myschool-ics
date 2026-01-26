import os
from pathlib import Path
from playwright.sync_api import sync_playwright

LOGIN_START = "https://myschool.centralesupelec.fr/plannings/login"

def main():
    password = "idir.nimgharen@student-cs.fr"
    username = "kTOL!2Zul#R#wF"
    
    Path("debug").mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        print("→ Opening MySchool")
        page.goto(LOGIN_START, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        print("Current URL:", page.url)

        # Si CAS
        if "cas.cloud.centralesupelec.fr" in page.url:
            print("→ On CAS login page")

            page.wait_for_selector("#username, input[name='username']", timeout=30_000)
            page.fill("#username, input[name='username']", username)

            page.wait_for_selector("#password, input[name='password']", timeout=30_000)
            page.fill("#password, input[name='password']", password)

            page.locator("button[type='submit'], input[type='submit']").click()

            # laisser le flux se faire
            page.wait_for_timeout(5000)

        print("Final URL:", page.url)

        # Screenshots
        page.screenshot(path="debug/screenshot.png", full_page=True)
        Path("debug/page.html").write_text(page.content(), encoding="utf-8")

        print("Screenshot + HTML saved in ./debug/")

        browser.close()

if __name__ == "__main__":
    main()
