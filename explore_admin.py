"""
Exploratory script: find the correct Administration mode URL and
Finance → Payment Methods path.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
OUT      = Path("output/payment-methods/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

VW, VH = 1440, 900
COMPANY_ID = "1253779"


def shot(page: Page, name: str) -> None:
    path = OUT / name
    page.screenshot(path=str(path))
    print(f"  📸 {name}")


def dump_links(page: Page, label: str) -> list:
    links = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].filter(a => {
            const r = a.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && a.href;
        }).map(a => {href: a.href, text: a.textContent.trim().slice(0, 60)});
    }""")
    print(f"  [{label}] visible links ({len(links)}):")
    for l in links[:20]:
        print(f"    {l.get('href', '')}  |  {l.get('text', '')}")
    return links


def dump_buttons(page: Page) -> None:
    btns = page.evaluate("""() => {
        return [...document.querySelectorAll('button, [role="button"]')].filter(b => {
            const r = b.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }).map(b => ({
            text: b.textContent.trim().slice(0, 50),
            cls: b.className.slice(0, 80)
        }));
    }""")
    print(f"  Visible buttons ({len(btns)}):")
    for b in btns[:20]:
        print(f"    [{b.get('text','')}]  cls: {b.get('cls','')}")


def nuke_overlays(page: Page) -> None:
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
            const st = window.getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;
            const z = parseInt(st.zIndex) || 0;
            if (z < 50) continue;
            const r = el.getBoundingClientRect();
            if (r.width > 300 && r.height > 200
                && (st.position === 'fixed' || st.position === 'absolute')) {
                el.remove();
            }
        }
    }""")
    page.wait_for_timeout(300)


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=False,
        args=["--lang=en-US"],
    )
    ctx = browser.new_context(
        viewport={"width": VW, "height": VH},
        locale="en-US",
    )
    page = ctx.new_page()

    # ── Login ──
    print("── Login ──")
    page.goto("https://app.alteg.io", wait_until="networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")
    shot(page, "_explore_01_login.png")

    # ── Try to change language via profile URL ──
    print("\n── Try profile/settings URL to find language ──")
    page.goto(f"https://app.alteg.io/timetable/{COMPANY_ID}/#mode=1", wait_until="networkidle")
    page.wait_for_timeout(2000)
    nuke_overlays(page)

    # Dump all nav items in the left sidebar
    nav_items = page.evaluate("""() => {
        return [...document.querySelectorAll('nav a, .erp-nav-menu a, [class*="nav"] a, [class*="menu"] a')].filter(el => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }).map(el => ({href: el.href, text: el.textContent.trim().slice(0, 60)}));
    }""")
    print(f"\n  Nav items ({len(nav_items)}):")
    for item in nav_items:
        print(f"    {item.get('href','')}  |  {item.get('text','')}")

    # ── Find and click Administration mode switch ──
    print("\n── Click Administration mode switch ──")
    shot(page, "_explore_02_calendar.png")

    # Click the mode-switch button
    switched = False
    for sel in [
        ".erp-nav-menu-mode-switch-footer-button",
        "[class*='mode-switch']",
        "[class*='footer-button']",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                bbox = btn.bounding_box()
                print(f"  Found mode-switch btn: {bbox}")
                btn.click()
                page.wait_for_timeout(1000)
                switched = True
                shot(page, "_explore_03_after_mode_click.png")
                break
        except Exception as e:
            print(f"  {sel}: {e}")

    if not switched:
        # Coordinate click
        print("  Trying coordinate click (110, 848)")
        page.mouse.click(110, 848)
        page.wait_for_timeout(1000)
        shot(page, "_explore_03_after_mode_click.png")

    print(f"  URL after click: {page.url}")

    # Dump all visible links (to find the company dropdown)
    all_links = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].filter(a => {
            const r = a.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }).map(a => ({href: a.href, text: a.textContent.trim().slice(0, 60)}));
    }""")
    print(f"\n  All visible links ({len(all_links)}):")
    for l in all_links:
        print(f"    {l.get('href','')}  |  {l.get('text','')}")

    # Dump all visible elements that might be the dropdown
    dropdown_els = page.evaluate("""() => {
        return [...document.querySelectorAll('[class*="dropdown"], [class*="popup"], [class*="menu"], [role="menu"], [role="listbox"]')]
            .filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            }).map(el => ({
                tag: el.tagName,
                cls: el.className.slice(0, 100),
                text: el.textContent.trim().slice(0, 100),
                rect: el.getBoundingClientRect()
            }));
    }""")
    print(f"\n  Dropdown/menu elements ({len(dropdown_els)}):")
    for el in dropdown_els[:10]:
        print(f"    {el.get('tag')} cls={el.get('cls','')} text={el.get('text','')}")

    # Wait and look for company link
    print("\n── Wait for company link ──")
    try:
        company_link = page.locator(f"a[href*='/location/{COMPANY_ID}/']").first
        company_link.wait_for(state="visible", timeout=5000)
        print(f"  ✓ Company link visible!")
        company_link.click()
        page.wait_for_load_state("networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        print(f"  → URL: {page.url}")
        shot(page, "_explore_04_admin_home.png")
    except Exception as e:
        print(f"  ⚠️  Company link not found: {e}")
        shot(page, "_explore_04_no_company.png")

    # ── Explore what's in Administration mode ──
    print(f"\n── Explore Admin mode navigation ──")
    print(f"  Current URL: {page.url}")

    # Get all nav links
    admin_nav = page.evaluate("""() => {
        return [...document.querySelectorAll('a, [role="menuitem"]')].filter(el => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && el.tagName === 'A';
        }).map(el => ({href: el.href, text: el.textContent.trim().slice(0, 80)}));
    }""")
    print(f"\n  Admin nav links ({len(admin_nav)}):")
    for l in admin_nav:
        print(f"    {l.get('href','')}  |  {l.get('text','')}")

    # Try clicking Finance
    print("\n── Try Finance menu item ──")
    for sel in [
        "text=Finance",
        "text=Финансы",
        "a:has-text('Finance')",
        "a:has-text('Финансы')",
        "[class*='menu'] a:has-text('inance')",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                print(f"  ✓ Found Finance via: {sel}")
                el.click()
                page.wait_for_timeout(1500)
                page.wait_for_load_state("networkidle")
                print(f"  → URL: {page.url}")
                shot(page, "_explore_05_finance.png")
                break
        except Exception as e:
            print(f"  {sel}: not found")

    # Dump links after clicking Finance
    finance_links = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].filter(a => {
            const r = a.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }).map(a => ({href: a.href, text: a.textContent.trim().slice(0, 80)}));
    }""")
    print(f"\n  Finance submenu links ({len(finance_links)}):")
    for l in finance_links:
        print(f"    {l.get('href','')}  |  {l.get('text','')}")

    # Try Payment Methods submenu
    print("\n── Try Payment Methods submenu ──")
    for sel in [
        "text=Payment methods",
        "text=Платёжные методы",
        "text=Платежные методы",
        "text=Payment",
        "a[href*='payment']",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                print(f"  ✓ Found via: {sel}")
                el.click()
                page.wait_for_timeout(1500)
                page.wait_for_load_state("networkidle")
                print(f"  → URL: {page.url}")
                shot(page, "_explore_06_payment_methods.png")
                break
        except Exception as e:
            print(f"  {sel}: not found")

    shot(page, "_explore_final.png")
    print(f"\n  Final URL: {page.url}")

    browser.close()
    print("\n✅ Exploration done.")
