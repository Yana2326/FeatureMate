"""
Capture screenshots for KB article: Payment Methods and Fees
Administration mode → Finance → Payment methods and fees
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
OUT      = Path("output/payment-methods/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

VW, VH = 1440, 900
COMPANY_ID = "1253779"


def shot(page: Page, name: str, clip=None) -> None:
    path = OUT / name
    kwargs: dict = {"path": str(path)}
    if clip:
        kwargs["clip"] = clip
    page.screenshot(**kwargs)
    w = clip["width"] if clip else VW
    h = clip["height"] if clip else VH
    print(f"  📸 {name}  ({w}×{h})")


def nuke_overlays(page: Page) -> None:
    """Remove large modals/overlays aggressively."""
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    for label in ["Not now", "View later", "Later", "Skip", "Close", "×", "✕"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=400):
                btn.click()
                page.wait_for_timeout(300)
        except Exception:
            pass

    page.evaluate("""() => {
        const remove = (el) => { try { el.remove(); } catch(e) {} };
        // Remove large overlays by z-index
        for (const el of [...document.querySelectorAll('*')]) {
            if (!el.isConnected) continue;
            const st = window.getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;
            const z = parseInt(st.zIndex) || 0;
            if (z < 50) continue;
            const r = el.getBoundingClientRect();
            if (r.width > 300 && r.height > 200
                && (st.position === 'fixed' || st.position === 'absolute')) {
                remove(el);
            }
        }
        // Tooltips, popovers
        for (const sel of ['[class*="tooltip"]','[class*="q-tooltip"]',
                           '[class*="popover"]','[class*="hint"]','[class*="tour"]']) {
            for (const el of document.querySelectorAll(sel)) {
                if (el.isConnected) el.style.display = 'none';
            }
        }
    }""")
    page.wait_for_timeout(300)


def login(page: Page) -> None:
    print("── Login ──")
    page.goto("https://app.alteg.io", wait_until="networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")


def change_language_to_english(page: Page) -> bool:
    """Navigate to profile settings and set language to English."""
    print("\n── Change language to English ──")

    # Try profile settings URL directly
    for url in [
        f"https://app.alteg.io/company/{COMPANY_ID}/settings/profile",
        "https://app.alteg.io/settings/profile",
        "https://app.alteg.io/profile",
    ]:
        page.goto(url, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        nuke_overlays(page)
        print(f"  Trying: {url}  →  {page.url}")

        # Look for language selector
        for lang_label in ["English", "Английский", "en", "EN"]:
            try:
                # Look in select elements
                selects = page.locator("select").all()
                for sel in selects:
                    options = sel.locator("option").all()
                    for opt in options:
                        if lang_label.lower() in (opt.text_content() or "").lower():
                            sel.select_option(label=opt.text_content())
                            page.wait_for_timeout(1000)
                            print(f"  ✓ Language set via select: {opt.text_content()}")
                            # Save
                            for save_text in ["Save", "Сохранить", "Apply"]:
                                try:
                                    save_btn = page.get_by_role("button", name=save_text, exact=False).first
                                    if save_btn.is_visible(timeout=1000):
                                        save_btn.click()
                                        page.wait_for_timeout(2000)
                                        print(f"  ✓ Saved")
                                        return True
                                except Exception:
                                    pass
            except Exception:
                pass

    # Alternative: look for language option in a dropdown/menu
    print("  Trying account dropdown approach...")
    try:
        # Click profile/avatar icon
        for sel in [
            '[class*="avatar"]', '[class*="profile"]', '[class*="user-menu"]',
            '.erp-nav-menu-personal-account', '[class*="personal"]'
        ]:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                el.click()
                page.wait_for_timeout(1000)
                shot(page, "_debug_profile_menu.png")
                break
    except Exception:
        pass

    shot(page, "_debug_language_attempt.png")
    print("  ⚠️  Could not change language automatically")
    return False


def switch_to_admin_via_url(page: Page) -> bool:
    """Navigate directly to Admin → Finance → Payment Methods via URL."""
    print("\n── Navigate to Admin → Finance → Payment Methods ──")

    # Direct URL for payment methods in admin mode
    urls_to_try = [
        f"https://app.alteg.io/company/{COMPANY_ID}/finance/payment-methods",
        f"https://app.alteg.io/location/{COMPANY_ID}/finance/payment-methods",
    ]

    for url in urls_to_try:
        print(f"  Trying: {url}")
        page.goto(url, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(3000)
        nuke_overlays(page)

        current = page.url
        print(f"  → Landed at: {current}")

        # Check if we're on the payment methods page
        if "payment" in current or "finance" in current:
            shot(page, "_debug_payment_direct.png")
            print("  ✓ Reached payment methods page")
            return True

    # If direct URL didn't work, try the mode-switch approach with proper waiting
    print("  Direct URL failed, trying mode-switch approach...")
    return switch_to_admin_via_button(page)


def switch_to_admin_via_button(page: Page) -> bool:
    """Click the mode-switch button and wait for the company dropdown."""
    print("\n── Switch via mode-switch button ──")

    # First go to the timetable page (Digital Schedule mode)
    page.goto(f"https://app.alteg.io/timetable/{COMPANY_ID}/#mode=1",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(2000)
    nuke_overlays(page)

    # Click the mode-switch button (Administration button at bottom-left)
    for sel in [
        ".erp-nav-menu-mode-switch-footer-button",
        "div.erp-nav-menu-mode-switch-footer-button",
        "[class*='mode-switch']",
        "[class*='footer-button']",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                print(f"  ✓ Clicked mode-switch via: {sel}")
                # Wait for dropdown with company links
                page.wait_for_timeout(500)
                shot(page, "_debug_after_mode_click.png")

                # Wait for the company link to appear
                try:
                    company_link = page.locator(f"a[href*='/location/{COMPANY_ID}/']").first
                    company_link.wait_for(state="visible", timeout=5000)
                    company_link.click()
                    page.wait_for_load_state("networkidle", timeout=20000)
                    page.wait_for_timeout(2000)
                    print(f"  ✓ Clicked company link → {page.url}")
                    return True
                except Exception as e:
                    print(f"  ⚠️  Company link wait failed: {e}")

                    # Try clicking by href
                    try:
                        page.click(f"a[href*='/location/{COMPANY_ID}/']", timeout=5000)
                        page.wait_for_load_state("networkidle", timeout=20000)
                        print(f"  ✓ Clicked via href selector → {page.url}")
                        return True
                    except Exception as e2:
                        print(f"  ⚠️  href click failed: {e2}")
                break
        except Exception:
            pass

    # Fallback: coordinate click at known position (110, 848) and wait
    print("  Trying coordinate click at (110, 848)...")
    page.mouse.click(110, 848)
    page.wait_for_timeout(800)
    shot(page, "_debug_coord_click.png")

    # Dump visible links
    links = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].filter(a => {
            const r = a.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }).map(a => ({href: a.href, text: a.textContent.trim().slice(0, 50)}));
    }""")
    print(f"  Visible links: {links[:10]}")

    try:
        company_link = page.locator(f"a[href*='/location/{COMPANY_ID}/']").first
        company_link.wait_for(state="visible", timeout=5000)
        company_link.click()
        page.wait_for_load_state("networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        print(f"  ✓ Clicked company link → {page.url}")
        return True
    except Exception as e:
        print(f"  ⚠️  All attempts failed: {e}")
        shot(page, "_debug_failed.png")
        return False


def navigate_to_finance(page: Page) -> bool:
    """Navigate from Admin home to Finance → Payment Methods."""
    print("\n── Navigate to Finance → Payment Methods ──")

    # Try clicking Finance menu item
    for sel in [
        "text=Finance",
        "text=Финансы",
        "a:has-text('Finance')",
        "a:has-text('Финансы')",
        "[class*='menu'] a:has-text('Finance')",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click()
                page.wait_for_timeout(1500)
                page.wait_for_load_state("networkidle")
                print(f"  ✓ Finance via: {sel}")
                shot(page, "_debug_finance.png")
                break
        except Exception:
            pass

    # Now click Payment Methods submenu
    for sel in [
        "text=Payment methods and fees",
        "text=Payment methods",
        "text=Платёжные методы и комиссии",
        "text=Платежные методы",
        "text=Методы оплаты",
        "a[href*='payment']",
        "a[href*='payment-methods']",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click()
                page.wait_for_timeout(1500)
                page.wait_for_load_state("networkidle")
                print(f"  ✓ Payment Methods via: {sel}")
                shot(page, "_debug_payment_methods.png")
                return True
        except Exception:
            pass

    return False


def take_screenshots(page: Page) -> None:
    """Take all required screenshots for the article."""
    print("\n── Taking screenshots ──")

    # s01: Overview of payment methods page
    nuke_overlays(page)
    shot(page, "s01_payment_methods_overview.png")

    # Check for tabs and click through them
    # Try "On-site" / "POS" tab
    for tab_text in ["On-site", "POS", "В салоне", "Онлайн-касса"]:
        try:
            tab = page.get_by_role("tab", name=tab_text, exact=False).first
            if tab.is_visible(timeout=1000):
                tab.click()
                page.wait_for_timeout(1000)
                shot(page, "s02_onsite_pos_tab.png")
                print(f"  ✓ On-site tab via: {tab_text}")
                break
        except Exception:
            pass
    else:
        shot(page, "s02_onsite_pos_tab.png")

    # Scroll to see debit cards section
    page.evaluate("window.scrollTo(0, 300)")
    page.wait_for_timeout(500)
    shot(page, "s03_debit_cards_section.png")

    page.evaluate("window.scrollTo(0, 600)")
    page.wait_for_timeout(500)
    shot(page, "s04_credit_cards_section.png")

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)

    # Custom payment methods section
    for sel in ["text=Custom", "text=Другие", "text=Пользовательские", "[class*='custom']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                el.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                shot(page, "s05_custom_payment_methods.png")
                break
        except Exception:
            pass
    else:
        shot(page, "s05_custom_payment_methods.png")

    # Try to open Add payment method modal
    for btn_text in ["Add payment method", "Add", "Добавить способ оплаты", "Добавить", "+ Add"]:
        try:
            btn = page.get_by_role("button", name=btn_text, exact=False).first
            if btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(1500)
                shot(page, "s06_add_payment_method_modal.png")
                # Close modal
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                print(f"  ✓ Add modal opened via: {btn_text}")
                break
        except Exception:
            pass
    else:
        print("  ⚠️  Add button not found, skipping modal")

    # Try Online tab
    for tab_text in ["Online", "Online cards", "Онлайн", "Онлайн-оплата"]:
        try:
            tab = page.get_by_role("tab", name=tab_text, exact=False).first
            if tab.is_visible(timeout=1000):
                tab.click()
                page.wait_for_timeout(1000)
                shot(page, "s07_online_cards_tab.png")
                print(f"  ✓ Online tab via: {tab_text}")
                break
        except Exception:
            pass
    else:
        print("  ⚠️  Online tab not found, taking screenshot of current state")
        shot(page, "s07_online_cards_tab.png")


# ── Main ──────────────────────────────────────────────────────────────────────

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=False,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI"],
    )
    ctx = browser.new_context(
        viewport={"width": VW, "height": VH},
        locale="en-US",
    )
    page = ctx.new_page()

    # Login
    login(page)
    shot(page, "_debug_01_after_login.png")

    # Try to change language to English
    change_language_to_english(page)
    page.wait_for_timeout(1000)

    # Navigate to Admin → Finance → Payment Methods (try direct URL first)
    success = switch_to_admin_via_url(page)

    if not success:
        # If direct URL failed, try button approach then navigate to Finance
        success = switch_to_admin_via_button(page)
        if success:
            nuke_overlays(page)
            shot(page, "_debug_03_admin_home.png")
            navigate_to_finance(page)

    print(f"\n  Final URL: {page.url}")
    shot(page, "_debug_final.png")

    # Take actual article screenshots if we're on the right page
    if "payment" in page.url or "finance" in page.url:
        take_screenshots(page)
    else:
        print("\n  ⚠️  Not on payment methods page, taking debug screenshot only")

    browser.close()
    print("\n✅ Done.")
