"""Quick login test — opens Altegio, logs in, saves a screenshot."""

from pathlib import Path
from playwright.sync_api import sync_playwright

EMAIL = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
LOGIN_URL = "https://app.alteg.io"
OUTPUT = Path("output/login_test")
OUTPUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    print("1. Opening login page...")
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")

    # Dump all inputs to find correct selectors
    inputs = page.eval_on_selector_all("input", """els => els.map(el => ({
        type: el.type,
        name: el.name,
        id: el.id,
        placeholder: el.placeholder,
        className: el.className
    }))""")
    print("   Inputs found on page:")
    for i, inp in enumerate(inputs):
        print(f"   [{i}] {inp}")

    print("\n2. Filling in credentials...")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.screenshot(path=str(OUTPUT / "02_credentials_filled.png"))
    print("   Screenshot saved: 02_credentials_filled.png")

    print("3. Clicking Sign in button...")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=15000)

    print("4. Closing popup if present...")
    try:
        close_btn = page.locator("button.modal__close, button[class*='close'], .popup__close").first
        if close_btn.is_visible(timeout=3000):
            close_btn.click()
            page.wait_for_timeout(500)
    except Exception:
        pass  # No popup — that's fine

    page.screenshot(path=str(OUTPUT / "03_after_login.png"))
    print("   Screenshot saved: 03_after_login.png")

    print(f"\nCurrent URL: {page.url}")
    print(f"Page title:  {page.title()}")

    if "login" not in page.url and "alteg.io" in page.url:
        print("\n✅ Login successful!")
    else:
        print("\n❌ Login may have failed — check 03_after_login.png")

    browser.close()

print(f"\nScreenshots saved to: {OUTPUT}/")
