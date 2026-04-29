"""
Open appointment window and take zoomed screenshots of each section.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
LOC_URL  = "https://app.alteg.io/timetable/1253779/#mode=1"
OUT      = Path("output/create-appointment/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

n = [0]
def shot(page: Page, name: str, clip=None) -> str:
    n[0] += 1
    fname = f"z{n[0]:02d}_{name}.png"
    kwargs = {"path": str(OUT / fname)}
    if clip:
        kwargs["clip"] = clip
    page.screenshot(**kwargs)
    print(f"  📸 {fname}")
    return fname


def force_close_all_modals(page: Page):
    """Remove all modal/overlay/popup DOM elements."""
    removed = page.evaluate("""() => {
        let count = 0;
        const overlaySelectors = [
            '[class*="modal"]',
            '[class*="dialog"]',
            '[class*="popup"]',
            '[class*="overlay"]',
            '[class*="adyen"]',
            '[class*="Adyen"]',
            '[role="dialog"]',
            '[role="alertdialog"]',
        ];
        for (const sel of overlaySelectors) {
            for (const el of document.querySelectorAll(sel)) {
                // Don't remove the main timetable area
                const r = el.getBoundingClientRect();
                if (r.width > 300 && r.height > 200
                    && !el.querySelector('[class*="timetable"]')
                    && !el.querySelector('[class*="calendar"]')) {
                    el.remove();
                    count++;
                }
            }
        }
        // Also remove any body-level backdrop
        document.body.style.overflow = 'auto';
        return count;
    }""")
    print(f"  ✓ force-removed {removed} modal elements")
    page.wait_for_timeout(300)


def click_x_button(page: Page):
    """Try to click × close button on visible modals."""
    # Evaluate position of any visible close button
    btn_pos = page.evaluate("""() => {
        const closeSelectors = [
            'button[aria-label="Close"]',
            'button[aria-label="close"]',
            '[class*="close"][role="button"]',
            'button[class*="close"]',
            '[class*="__close"]',
            '[class*="-close"]',
            'button svg[class*="close"]',
        ];
        for (const sel of closeSelectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    return {x: r.left + r.width/2, y: r.top + r.height/2, sel};
                }
            }
        }
        return null;
    }""")
    if btn_pos:
        print(f"  Close button at ({btn_pos['x']:.0f}, {btn_pos['y']:.0f}), sel='{btn_pos['sel']}'")
        page.mouse.click(btn_pos["x"], btn_pos["y"])
        page.wait_for_timeout(500)
        return True
    return False


def dismiss_popups(page: Page):
    page.wait_for_timeout(1500)
    shot(page, "popup_state")

    # Step 1: Try clicking × button
    if not click_x_button(page):
        # Step 2: Try Escape
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        print("  Pressed Escape")

    page.wait_for_timeout(500)

    # Step 3: View later button
    for label in ["View later", "Later", "Skip", "Not now"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=600):
                btn.click()
                page.wait_for_timeout(600)
                print(f"  ✓ '{label}' clicked")
                break
        except Exception:
            pass

    # Step 4: Force remove any remaining modals
    force_close_all_modals(page)
    page.wait_for_timeout(300)
    shot(page, "after_popups")


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True, slow_mo=0,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI"],
    )
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    page = ctx.new_page()

    # ── Login ──
    print("── Login ──")
    page.goto("https://app.alteg.io")
    page.wait_for_load_state("networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(2500)

    # ── Dismiss popups ──
    print("\n── Dismiss popups ──")
    dismiss_popups(page)

    # ── Navigate to correct location if needed ──
    if "1253779" not in page.url:
        page.goto(LOC_URL)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        dismiss_popups(page)

    print(f"\n── Calendar ── URL: {page.url}")
    shot(page, "calendar_clean")

    # Scroll to working hours and take a calendar screenshot
    page.evaluate("""() => {
        const cs = document.querySelectorAll('.q-scrollarea__container, [class*="scrollarea__container"]');
        for (const c of cs) c.scrollTop = 200;
    }""")
    page.wait_for_timeout(500)
    shot(page, "calendar_scrolled")

    # ── Open appointment window ──
    print("\n── Open appointment window ──")

    # Find a free slot in the calendar grid
    slot = page.evaluate("""() => {
        // The timetable columns: find small empty cells after x=250
        for (const el of document.querySelectorAll('*')) {
            if (!el.offsetParent) continue;
            const r = el.getBoundingClientRect();
            const cls = (el.className || '').toString();
            if (r.left > 250 && r.top > 80 && r.top < 650
                && r.height >= 10 && r.height <= 45
                && r.width >= 80 && r.width <= 230
                && !el.innerText.trim()
                && (cls.includes('slot') || cls.includes('cell')
                    || cls.includes('col') || cls.includes('record')
                    || cls.includes('time') || cls.includes('row'))) {
                return {x: r.left + r.width/2, y: r.top + r.height/2};
            }
        }
        return null;
    }""")

    if slot:
        x, y = slot["x"], slot["y"]
        print(f"  Slot at ({x:.0f}, {y:.0f})")
    else:
        x, y = 370, 250  # fallback: Mary column, ~10:00 area
        print(f"  No slot found — fallback ({x}, {y})")

    # Hover first
    page.mouse.move(x, y)
    page.wait_for_timeout(900)
    shot(page, "hover_shows_new_booking")

    # Click slot → dropdown with "Booking" / "Event" appears
    page.mouse.click(x, y)
    page.wait_for_timeout(1200)
    shot(page, "after_slot_click_dropdown")

    # Click exactly "Booking" from the dropdown (NOT "New Booking" header)
    clicked = False
    try:
        # The dropdown option text is exactly "Booking"
        booking_option = page.get_by_text("Booking", exact=True).first
        if booking_option.is_visible(timeout=1500):
            booking_option.click()
            page.wait_for_timeout(2500)  # form animation
            print("  ✓ clicked 'Booking' option")
            clicked = True
    except Exception:
        pass

    if not clicked:
        # Try role=menuitem or listitem
        for sel in ["[role='menuitem']", "[role='option']", "li"]:
            try:
                items = page.locator(sel).filter(has_text="Booking")
                if items.count() > 0 and items.first.is_visible(timeout=600):
                    items.first.click()
                    page.wait_for_timeout(2500)
                    print(f"  ✓ clicked Booking via {sel}")
                    clicked = True
                    break
            except Exception:
                pass

    shot(page, "appointment_window_full")

    # ── Get dialog bounds ──
    dialog = page.evaluate("""() => {
        // Find the widest visible overlay that's not the main nav
        let best = null;
        for (const el of document.querySelectorAll('*')) {
            if (!el.offsetParent) continue;
            const r = el.getBoundingClientRect();
            if (r.left >= 190 && r.width >= 800 && r.height >= 500 && r.top <= 10) {
                const cls = (el.className || '').toString();
                if (cls.includes('visit') || cls.includes('appointment')
                    || cls.includes('record') || cls.includes('booking')
                    || cls.includes('drawer') || cls.includes('panel')) {
                    best = {x: r.left, y: r.top, w: r.width, h: r.height, cls: cls.substring(0,60)};
                    break;
                }
            }
        }
        if (!best) best = {x: 200, y: 0, w: 1240, h: 900, cls: 'fallback'};
        return best;
    }""")
    print(f"  Dialog: {dialog}")

    dx, dy, dw, dh = dialog["x"], dialog["y"], dialog["w"], dialog["h"]

    # Capture left panel (team member, date, time, advanced)
    shot(page, "left_panel", clip={"x": dx, "y": dy, "width": int(dw * 0.27), "height": dh})

    # Capture center panel (services/products + status pills)
    shot(page, "center_panel", clip={"x": dx + int(dw * 0.27), "y": dy, "width": int(dw * 0.43), "height": dh})

    # Capture right panel (client)
    shot(page, "right_panel", clip={"x": dx + int(dw * 0.70), "y": dy, "width": int(dw * 0.30), "height": dh})

    # Status pills close-up
    shot(page, "status_pills", clip={"x": dx + int(dw * 0.27), "y": dy + 40, "width": int(dw * 0.43), "height": 55})

    # Save buttons area
    shot(page, "save_buttons", clip={"x": dx, "y": dy + dh - 110, "width": dw, "height": 110})

    # Dump visible text & buttons
    texts = page.evaluate("""() =>
        [...new Set(
            Array.from(document.querySelectorAll('*'))
                 .filter(el => el.offsetParent !== null
                             && el.children.length === 0
                             && el.innerText && el.innerText.trim().length > 0
                             && el.innerText.trim().length < 120)
                 .map(el => el.innerText.trim())
        )]
    """)
    print("\n  Visible text:")
    for t in texts: print(f"    {t!r}")

    buttons = page.evaluate("""() =>
        Array.from(document.querySelectorAll('button,[role="button"]'))
             .filter(el => el.offsetParent !== null && el.innerText.trim())
             .map(el => el.innerText.trim().substring(0, 60))
    """)
    print("\n  Buttons:")
    for b in buttons: print(f"    {b!r}")

    print(f"\n✅ Done — {n[0]} screenshots in {OUT}/")
    browser.close()
