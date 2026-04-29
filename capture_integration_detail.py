"""
Capture screenshots of one integration detail page (Google Analytics — Free, not installed)
and the Application search functionality.
Uses isolated headless Chromium.
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright, Page


def _load_env():
    env_path = Path(__file__).parent / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

_load_env()

EMAIL      = os.environ["ALTEGIO_EMAIL"]
PASSWORD   = os.environ["ALTEGIO_PASSWORD"]
COMPANY_ID = "1253779"
BASE_URL   = "https://app.alteg.io"

OUT_DIR    = Path("output/integrations-overview")
SHOTS_DIR  = OUT_DIR / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)


def shot(page: Page, name: str, full_page=False):
    path = str(SHOTS_DIR / name)
    page.screenshot(path=path, full_page=full_page)
    print(f"  📸 {name}")


def nuke_overlays(page: Page):
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    for label in ["Not now", "View later", "Later", "Skip", "Close"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=400):
                btn.click()
                page.wait_for_timeout(300)
        except Exception:
            pass
    page.evaluate("""() => {
        for (const el of [...document.querySelectorAll('*')]) {
            if (!el.isConnected) continue;
            const st = getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;
            const z = parseInt(st.zIndex) || 0;
            if (z < 50) continue;
            const r = el.getBoundingClientRect();
            if (r.width > 300 && r.height > 200
                && (st.position === 'fixed' || st.position === 'absolute')) el.remove();
        }
    }""")
    page.wait_for_timeout(300)


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI", "--no-sandbox"]
    )
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    page = ctx.new_page()

    # Login
    print("── Login ──")
    page.goto(BASE_URL, wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)

    # Integration detail — Google Analytics (id 102, not installed)
    print("── Google Analytics detail page ──")
    page.goto(f"{BASE_URL}/appstore/{COMPANY_ID}/applications/102", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    shot(page, "04_detail_google_analytics.png")
    shot(page, "04_detail_google_analytics_full.png", full_page=True)

    # Try Viva Wallet (Payment system detail)
    print("── Viva Wallet detail page ──")
    page.goto(f"{BASE_URL}/appstore/{COMPANY_ID}/applications/333", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    shot(page, "05_detail_viva_wallet.png")

    # Application search on the main integrations page
    print("── Application search ──")
    page.goto(f"{BASE_URL}/appstore/{COMPANY_ID}/applications/overview/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    search = page.locator('input[placeholder*="search" i], input[placeholder*="Search" i], input[placeholder*="Application" i]').first
    if search.is_visible(timeout=3000):
        search.fill("whats")
        page.wait_for_timeout(1500)
        shot(page, "06_search_results.png")
        search.fill("")
        page.wait_for_timeout(500)

    # Clean main overview screenshot (without search)
    print("── Clean main overview ──")
    page.goto(f"{BASE_URL}/appstore/{COMPANY_ID}/applications/overview/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    shot(page, "02_integrations_overview.png")
    shot(page, "02_integrations_overview_full.png", full_page=True)

    # Category: Payment systems clean
    print("── Payment systems clean ──")
    page.goto(f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=11", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    shot(page, "07_cat_payment_systems_clean.png")

    browser.close()

print("\n✓ Done")
