"""Load admin_storage_state.json and verify it actually grants admin mode.
Take a screenshot so we can see what loads."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID, launch_isolated_browser, nuke_overlays,
)

STATE_FILE = Path("admin_storage_state.json")
ADMIN_URL = (
    f"{BASE}/analytics/{COMPANY_ID}/"
    "?start_date=01.04.2026&end_date=30.04.2026"
    "&user_id=0&position_id=0&master_id=0"
)

if not STATE_FILE.exists():
    raise SystemExit(f"{STATE_FILE} not found — run save_admin_state.py first")

with sync_playwright() as pw:
    browser, ctx, page = launch_isolated_browser(
        pw, headless=True, storage_state=STATE_FILE
    )
    try:
        page.goto(ADMIN_URL, wait_until="networkidle")
        page.wait_for_timeout(4000)
        nuke_overlays(page)

        result = page.evaluate("""
        () => {
            const labels = ['Analytical Reports','Team','Clients','Online Booking','Services',
                            'Products','Finance','Payroll','Notifications','Loyalty',
                            'Resources','Integrations','Settings'];
            const dsLabels = ['Product sales','New payment','Service list','Product Catalog'];
            let admin = 0, ds = 0;
            const adminFound = [], dsFound = [];
            for (const label of labels) {
                for (const el of document.querySelectorAll('a, span, div')) {
                    const r = el.getBoundingClientRect();
                    if (r.left >= 280 || r.width < 50 || r.height < 14) continue;
                    if (r.top < 0 || r.top > window.innerHeight) continue;
                    if ((el.textContent || '').trim() === label) {
                        admin++; adminFound.push(label); break;
                    }
                }
            }
            for (const label of dsLabels) {
                for (const el of document.querySelectorAll('a, span, div')) {
                    const r = el.getBoundingClientRect();
                    if (r.left >= 280 || r.width < 30 || r.height < 14) continue;
                    if (r.top < 0 || r.top > window.innerHeight) continue;
                    if ((el.textContent || '').trim() === label) {
                        ds++; dsFound.push(label); break;
                    }
                }
            }
            const btn = document.querySelector('.erp-nav-menu-mode-switch-footer-button');
            return {
                url: location.href,
                btnText: btn ? btn.textContent.trim() : null,
                adminItems: adminFound,
                dsItems: dsFound,
            };
        }
        """)
        print(f"URL:        {result['url']}")
        print(f"Button:     {result['btnText']}")
        print(f"Admin items in sidebar: {len(result['adminItems'])} → {result['adminItems']}")
        print(f"DS items in sidebar:    {len(result['dsItems'])} → {result['dsItems']}")

        if result['adminItems'] and not result['dsItems']:
            print("\n✅ ADMIN MODE — saved state works")
        elif result['dsItems'] and not result['adminItems']:
            print("\n❌ DIGITAL SCHEDULE MODE — saved state does NOT have admin mode")
        else:
            print("\n⚠ Mixed/unclear state")

        page.screenshot(path="output/add-team-member/diag_state_check.png")
        print("\nScreenshot saved → output/add-team-member/diag_state_check.png")
    finally:
        browser.close()
