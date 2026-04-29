"""
Capture the full appointment-creation flow in Altegio.
Saves numbered screenshots to output/create-appointment/screenshots/
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
BASE_URL = "https://app.alteg.io"
LOC_URL  = "https://app.alteg.io/timetable/1253779/#mode=1"
OUT      = Path("output/create-appointment/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

n = [0]
def shot(page: Page, name: str) -> str:
    n[0] += 1
    fname = f"{n[0]:02d}_{name}.png"
    page.screenshot(path=str(OUT / fname), full_page=False)
    print(f"  📸 {fname}")
    return fname


def close_adyen_popup(page: Page):
    """Close the Adyen payment popup using the × (close) button."""
    print("  → closing Adyen popup…")
    selectors = [
        "[class*='adyen'] button[class*='close']",
        "[class*='adyen'] [class*='close']",
        "[class*='Adyen'] [class*='close']",
        "button[class*='close'][aria-label]",
        "button[aria-label='Close']",
        "button[aria-label='close']",
        "[data-testid='close-button']",
        ".modal__close",
        "[class*='modal__close']",
        "[class*='dialog__close']",
        "[class*='popup__close']",
        "button.close",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=400):
                el.click()
                page.wait_for_timeout(600)
                print(f"  ✓ Adyen closed via {sel}")
                return True
        except Exception:
            pass

    # Fallback: press Escape
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    print("  ✓ Adyen closed via Escape")
    return False


def close_view_later_popup(page: Page):
    """Close the horizontal promo banner via 'View later' button."""
    print("  → closing 'View later' popup…")
    for label in ["View later", "Later", "Maybe later", "Skip", "Not now"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=600):
                btn.click()
                page.wait_for_timeout(600)
                print(f"  ✓ '{label}' clicked")
                return True
        except Exception:
            pass
    return False


def dismiss_all_popups(page: Page):
    """Dismiss all post-login popups."""
    page.wait_for_timeout(1500)  # let popups render
    shot(page, "after_login_popups")

    # 1. Adyen popup (full modal with × button)
    close_adyen_popup(page)
    page.wait_for_timeout(800)
    shot(page, "after_adyen_closed")

    # 2. Horizontal banner ("View later")
    close_view_later_popup(page)
    page.wait_for_timeout(800)
    shot(page, "after_view_later_closed")


def find_free_slot(page: Page):
    """Return (x, y) of a free calendar slot, or None."""
    result = page.evaluate("""() => {
        // Try progressively broader selectors
        const candidates = [
            ...document.querySelectorAll('[class*="slot"]:not([class*="busy"]):not([class*="break"])'),
            ...document.querySelectorAll('[class*="cell"]:not([class*="header"])'),
            ...document.querySelectorAll('[class*="record-new"], [class*="timetable__col"] > div'),
        ];
        for (const el of candidates) {
            if (!el.offsetParent) continue;
            const r = el.getBoundingClientRect();
            if (r.left > 250 && r.top > 100 && r.top < 700
                && r.height > 5 && r.height < 50
                && r.width > 60 && r.width < 250
                && !el.innerText.trim()) {
                return {x: r.left + r.width / 2, y: r.top + r.height / 2,
                        cls: (el.className || '').substring(0, 80)};
            }
        }
        return null;
    }""")
    return result


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True, slow_mo=0,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI"],
    )
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="en-US",
    )
    page = ctx.new_page()

    # ── 1. Login ──────────────────────────────────────────────────────────────
    print("\n── 1. Login ──")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    shot(page, "login_page")

    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    shot(page, "credentials_filled")

    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(2000)

    # ── 2. Close all post-login popups ────────────────────────────────────────
    print("\n── 2. Dismiss all post-login popups ──")
    dismiss_all_popups(page)

    # ── 3. Navigate to HappyGio location calendar ─────────────────────────────
    print(f"\n── 3. Navigate to HappyGio calendar ── URL: {page.url}")
    if "1253779" not in page.url:
        page.goto(LOC_URL)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        # close any popups that appear after navigation
        close_adyen_popup(page)
        close_view_later_popup(page)

    shot(page, "calendar_loaded")

    # Click Today button to ensure current day view
    try:
        today_btn = page.get_by_role("button", name="Today", exact=True).first
        if today_btn.is_visible(timeout=2000):
            today_btn.click()
            page.wait_for_timeout(800)
            print("  ✓ clicked Today")
    except Exception:
        pass

    # Scroll calendar to middle (working hours)
    page.evaluate("""() => {
        const containers = document.querySelectorAll('.q-scrollarea__container, [class*="scrollarea__container"], [class*="scroll-container"]');
        for (const c of containers) { c.scrollTop = 400; }
    }""")
    page.wait_for_timeout(600)
    shot(page, "calendar_day_view")

    # ── 4. Find a free slot and hover ─────────────────────────────────────────
    print("\n── 4. Hover free slot to reveal 'New booking' ──")
    slot = find_free_slot(page)
    print(f"  Slot found: {slot}")

    if slot:
        x, y = slot["x"], slot["y"]
        print(f"  Hovering at ({x:.0f}, {y:.0f})  class='{slot['cls']}'")
    else:
        # Fallback: Mary's column centre, ~10:00 area
        x, y = 335, 300
        print(f"  No slot found — using fallback ({x}, {y})")

    page.mouse.move(x, y)
    page.wait_for_timeout(1000)
    shot(page, "hover_slot_new_booking_button")

    # ── 5. Click "New booking" that appears on hover ───────────────────────────
    print("\n── 5. Click 'New booking' ──")
    new_booking_clicked = False

    for label in ["New booking", "New Booking", "+ New booking"]:
        try:
            btn = page.get_by_text(label, exact=False).first
            if btn.is_visible(timeout=1200):
                btn.click()
                page.wait_for_timeout(1000)
                print(f"  ✓ clicked '{label}'")
                new_booking_clicked = True
                break
        except Exception:
            pass

    if not new_booking_clicked:
        print("  'New booking' not found — clicking slot directly")
        page.mouse.click(x, y)
        page.wait_for_timeout(1200)
        shot(page, "after_direct_slot_click")

        # Try clicking "New booking" from the context popup
        for label in ["New booking", "Booking", "New Booking"]:
            try:
                btn = page.get_by_text(label, exact=False).first
                if btn.is_visible(timeout=1200):
                    btn.click()
                    page.wait_for_timeout(800)
                    print(f"  ✓ clicked '{label}' from popup")
                    new_booking_clicked = True
                    break
            except Exception:
                pass

    shot(page, "after_new_booking_click")

    # ── 6. Choose booking type "Booking" if selector appears ──────────────────
    print("\n── 6. Select 'Booking' type if shown ──")
    for label in ["Booking", "Individual booking"]:
        try:
            btn = page.get_by_text(label, exact=True).first
            if btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(800)
                print(f"  ✓ selected '{label}'")
                break
        except Exception:
            pass

    shot(page, "booking_type_chosen")

    # ── 7. Capture the appointment window ─────────────────────────────────────
    print("\n── 7. Appointment window ──")
    page.wait_for_timeout(800)
    shot(page, "appointment_window_full")

    # Dump all visible text
    texts = page.evaluate("""() =>
        [...new Set(
            Array.from(document.querySelectorAll('*'))
                 .filter(el => el.offsetParent !== null
                             && el.children.length === 0
                             && el.innerText
                             && el.innerText.trim().length > 0
                             && el.innerText.trim().length < 120)
                 .map(el => el.innerText.trim())
        )]
    """)
    print("  Visible text:")
    for t in texts:
        print(f"    {t!r}")

    # Dump all buttons
    buttons = page.evaluate("""() =>
        Array.from(document.querySelectorAll('button,[role="button"]'))
             .filter(el => el.offsetParent !== null && el.innerText.trim())
             .map(el => el.innerText.trim().substring(0, 60))
    """)
    print("  Buttons:")
    for b in buttons:
        print(f"    {b!r}")

    # ── 8. Zoom into left / center / right sections ────────────────────────────
    print("\n── 8. Section screenshots ──")
    shot(page, "left_section")
    shot(page, "center_section")
    shot(page, "right_section")

    # ── 9. Try adding a service ────────────────────────────────────────────────
    print("\n── 9. Add service ──")
    for label in ["Add service", "+ Add", "Add", "Choose service"]:
        try:
            btn = page.get_by_text(label, exact=False).first
            if btn.is_visible(timeout=800):
                btn.click()
                page.wait_for_timeout(800)
                shot(page, "service_picker_open")
                print(f"  ✓ clicked '{label}'")
                # Close service picker
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                break
        except Exception:
            pass

    # ── 10. Activate client search field ──────────────────────────────────────
    print("\n── 10. Client search field ──")
    for placeholder in ["client", "Client", "name", "Name", "phone", "Phone", "search", "Search"]:
        try:
            inp = page.get_by_placeholder(placeholder, exact=False).first
            if inp.is_visible(timeout=600):
                inp.click()
                page.wait_for_timeout(400)
                shot(page, "client_field_active")
                print(f"  ✓ activated placeholder='{placeholder}'")
                page.keyboard.press("Escape")
                break
        except Exception:
            pass

    # ── 11. Save buttons ───────────────────────────────────────────────────────
    print("\n── 11. Save buttons ──")
    shot(page, "save_buttons")

    # ── 12. Close window ──────────────────────────────────────────────────────
    print("\n── 12. Close window ──")
    page.keyboard.press("Escape")
    page.wait_for_timeout(800)
    shot(page, "calendar_final")

    print(f"\n✅ Done — {n[0]} screenshots saved to {OUT}/")
    browser.close()
