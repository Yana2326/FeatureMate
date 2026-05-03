"""ONE-TIME script: launch headful Playwright, you manually click the
yellow Administration button, then we save the resulting browser state
(cookies + localStorage + sessionStorage) to admin_storage_state.json.

All future capture scripts should load this state instead of logging in
fresh — that way they start in Administration mode without having to
trigger the click handler that doesn't fire under automation.

Usage:
    python3 save_admin_state.py

After the browser opens:
  1. Wait for login + Main Dashboard to load
  2. Click the yellow "Administration" button in the bottom-left
  3. Verify the sidebar now shows Analytical Reports / Team / Clients / ...
  4. Press Enter in this terminal — state will be saved
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID, login, switch_language_to_english, nuke_overlays,
    enable_new_ui_flags, EMAIL, PASSWORD,
)

STATE_FILE = Path("admin_storage_state.json")

ADMIN_URL = (
    f"{BASE}/analytics/{COMPANY_ID}/"
    "?start_date=01.04.2026&end_date=30.04.2026"
    "&user_id=0&position_id=0&master_id=0"
)

with sync_playwright() as pw:
    # Use real Google Chrome (channel="chrome") instead of bundled Chromium.
    # The yellow Administration button's Vue 3 click handler does not produce
    # any state change in Playwright-bundled Chromium (verified — clicks reach
    # the handler with isTrusted=True but the mode never switches). Real
    # Chrome may behave differently. If `channel="chrome"` is not installed,
    # falls back to bundled Chromium with a clear note.
    try:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=False,
            args=[
                "--lang=en-US",
                "--disable-features=Translate,TranslateUI",
                "--no-sandbox",
                "--window-size=1280,800",
            ],
        )
        print("✓ Launched real Google Chrome (channel='chrome')")
    except Exception as e:
        print(f"⚠ Could not launch Google Chrome ({e}); falling back to bundled Chromium")
        browser = pw.chromium.launch(
            headless=False,
            args=[
                "--lang=en-US",
                "--disable-features=Translate,TranslateUI",
                "--no-sandbox",
                "--window-size=1280,800",
            ],
        )
    # Use a viewport that fits any standard MacBook screen — the yellow
    # Administration button sits at y≈1006 in a 1080-tall viewport, which
    # falls below the visible area on screens shorter than 1080px. With an
    # 800-tall viewport the page is laid out shorter and the button moves
    # into the visible area at the bottom-left.
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()

    print("=" * 70)
    print("STEP 1: Logging in automatically...")
    print("=" * 70)
    login(page)
    switch_language_to_english(page)
    enable_new_ui_flags(page)
    page.goto(ADMIN_URL, wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)

    # Check whether the yellow button is in the DOM and where it is
    btn_info = page.evaluate("""
    () => {
        const btn = document.querySelector('.erp-nav-menu-mode-switch-footer-button');
        if (!btn) return {exists: false};
        const r = btn.getBoundingClientRect();
        const vh = window.innerHeight;
        return {
            exists: true,
            text: btn.textContent.trim(),
            x: Math.round(r.x), y: Math.round(r.y),
            w: Math.round(r.width), h: Math.round(r.height),
            visibleInViewport: r.bottom <= vh && r.top >= 0,
            viewportHeight: vh,
        };
    }
    """)
    print(f"\nYellow mode-switch button: {btn_info}")

    if btn_info.get('exists') and not btn_info.get('visibleInViewport'):
        print("  ⚠ Button is in DOM but below viewport — scroll the sidebar to bring it into view.")
    elif not btn_info.get('exists'):
        print("  ⚠ Button NOT found in DOM. Try scrolling the sidebar or check the page.")

    print("\n" + "=" * 70)
    print("STEP 2: NOW go to the browser window and:")
    print("  1. If the yellow 'Administration' button is not visible, scroll the")
    print("     left sidebar down (mouse-wheel or trackpad scroll over the sidebar)")
    print("     until the yellow button appears at the bottom-left.")
    print("  2. Click the yellow 'Administration' button.")
    print("  3. Verify the sidebar now shows Analytical Reports / Team / Clients /")
    print("     Online Booking / Services / Products / Finance / Payroll / etc.")
    print("     (The yellow button text should now read 'Digital schedule'.)")
    print("  4. Come back here and press Enter.")
    print("=" * 70)

    def check_admin():
        return page.evaluate("""
        () => {
            const labels = ['Analytical Reports','Team','Clients','Online Booking','Services',
                            'Products','Finance','Payroll','Notifications','Loyalty',
                            'Resources','Integrations','Settings'];
            let found = 0;
            const foundList = [];
            for (const label of labels) {
                for (const el of document.querySelectorAll('a, span, div')) {
                    const r = el.getBoundingClientRect();
                    if (r.left >= 280 || r.width < 50 || r.height < 14) continue;
                    if (r.top < 0 || r.top > window.innerHeight) continue;
                    if ((el.textContent || '').trim() === label) {
                        found++; foundList.push(label); break;
                    }
                }
            }
            const btn = document.querySelector('.erp-nav-menu-mode-switch-footer-button');
            return {
                url: location.href,
                btnText: btn ? btn.textContent.trim() : null,
                adminItemsVisible: found,
                adminItems: foundList,
            };
        }
        """)

    # Retry loop: keep checking until mode switches or user gives up
    for attempt in range(1, 6):
        input(f"\n>>> [Attempt {attempt}/5] Press Enter after clicking Administration... ")
        state = check_admin()
        print(f"  Verification: {state}")

        if state['adminItemsVisible'] >= 3 and state['btnText'] and 'digital' in state['btnText'].lower():
            print("\n✅ Administration mode is active. Saving state...")
            ctx.storage_state(path=str(STATE_FILE))
            print(f"✅ Saved to {STATE_FILE}")
            break
        else:
            print(f"\n⚠ Mode did NOT switch (still showing '{state['btnText']}', "
                  f"{state['adminItemsVisible']} admin items visible).")
            if attempt < 5:
                print("  → Try clicking the yellow button again, then press Enter.")
                print("  → Or type 's' and Enter to save current state and exit.")
                ans = input("  > ").strip().lower()
                if ans == 's':
                    ctx.storage_state(path=str(STATE_FILE))
                    print(f"  Saved state-as-is to {STATE_FILE}")
                    break
            else:
                print("  → Saving state-as-is for manual review.")
                ctx.storage_state(path=str(STATE_FILE))

    browser.close()
