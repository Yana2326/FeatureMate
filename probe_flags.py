"""
Inspect storage flags + cookies + try to flip new-nav feature flag on.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    login, switch_language_to_english, nuke_overlays, close_translate_popup,
)

OUT = Path("output/add-team-member/_probe_after_flag.png")

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=False,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI", "--no-sandbox"],
    )
    ctx  = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()

    print("== login ==")
    login(page)
    print("== switch language ==")
    switch_language_to_english(page)

    page.goto(f"{BASE}/settings/filial_staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2500)

    # Step 1: dump current storage values + cookies
    print("\n=== BEFORE: storage values ===")
    storage = page.evaluate("""
    () => {
        const ls = Object.fromEntries(
            Object.keys(localStorage).map(k => [k, localStorage.getItem(k)])
        );
        const ss = Object.fromEntries(
            Object.keys(sessionStorage).map(k => [k, sessionStorage.getItem(k)])
        );
        return {ls, ss};
    }
    """)
    import json
    print(json.dumps(storage, indent=2))

    cookies = ctx.cookies()
    print(f"\nCookies ({len(cookies)}):")
    for c in cookies:
        if any(k in c["name"].lower() for k in ("nav", "ui", "feature", "experiment", "ab")):
            print(f"  {c['name']} = {c['value'][:80]}")

    # Step 2: try flipping flags
    print("\n=== Flipping new-nav flags ===")
    page.evaluate("""
    () => {
        // Anything that looks navigation-related → set "enabled"/"true"
        const guesses = [
            ['localStorage', 'new_navigation_enabled', 'true'],
            ['localStorage', 'new_nav_enabled', 'true'],
            ['localStorage', 'nav_menu_mode', 'new'],
            ['localStorage', 'erp_client_sidebar_compact_navigation', 'expanded'],
            ['sessionStorage', 'erp-nav-menu-mode-switch:enabled', 'true'],
            ['sessionStorage', 'erp-nav-menu-mode-switch', 'new'],
            ['sessionStorage', 'erp-nav-menu-version', '2'],
        ];
        for (const [store, k, v] of guesses) {
            (store === 'localStorage' ? localStorage : sessionStorage).setItem(k, v);
        }
        return Object.keys(localStorage).concat(Object.keys(sessionStorage));
    }
    """)

    # Step 3: hard reload
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(800)

    # Step 4: verify if dark sidebar appears
    print("\n=== AFTER: did the new UI appear? ===")
    after = page.evaluate("""
    () => {
        // Look for the dark sidebar by its sidebar items.
        const sidebar_items = ['Analytical Reports', 'Team', 'Clients',
                               'Online Booking', 'Services', 'Products',
                               'Finance', 'Payroll', 'Notifications',
                               'Loyalty', 'Resources'];
        const matches = sidebar_items.filter(label =>
            Array.from(document.querySelectorAll('a, span, div'))
                .some(el => (el.textContent || '').trim() === label
                            && el.children.length <= 2)
        );
        // Look for the Position/Specialization/System users tab strip
        const tab_labels = ['Position', 'Specialization', 'System users'];
        const tabs = tab_labels.filter(label =>
            Array.from(document.querySelectorAll('a, span, button, div'))
                .some(el => (el.textContent || '').trim() === label
                            && el.children.length === 0)
        );
        return {sidebar_items_found: matches, tabs_found: tabs};
    }
    """)
    print(json.dumps(after, indent=2))

    page.screenshot(path=str(OUT), full_page=False)
    print(f"\n✓ Saved {OUT}")
    browser.close()
