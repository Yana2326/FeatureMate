"""
Retake all article screenshots cleanly:
- Dismiss every tooltip/banner before each capture
- Calendar shots: full viewport cropped to remove the left quick-bar
- Appointment window shots: full sidebar crop (1100×900) so all images
  share the same 11:9 aspect ratio → consistent page-width display in PDF
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
LOC_URL  = "https://app.alteg.io/timetable/1253779/#mode=1"
OUT      = Path("output/create-appointment/screenshots")

# Appointment sidebar starts at x=340 in a 1440×900 viewport
SIDEBAR_X = 340
SIDEBAR_W = 1100   # 1440 - 340
SIDEBAR_H = 900

# Calendar crop: remove the 195px dark quick-bar on the left
CAL_X = 195
CAL_W = 1440 - CAL_X   # 1245


# ── Helpers ──────────────────────────────────────────────────────────────────

def shot(page: Page, name: str, clip=None) -> Path:
    path = OUT / name
    kwargs: dict = {"path": str(path)}
    if clip:
        kwargs["clip"] = clip
    page.screenshot(**kwargs)
    w = clip["width"] if clip else 1440
    h = clip["height"] if clip else 900
    print(f"  📸 {name}  ({w}×{h})")
    return path


def nuke_overlays(page: Page) -> None:
    """Aggressively remove any large modal/overlay covering the calendar."""
    # 1. Escape key
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # 2. Click common close-button labels
    for label in ["Not now", "Skip", "Close", "Later", "View later", "×", "✕"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=300):
                btn.click()
                page.wait_for_timeout(300)
        except Exception:
            pass

    # 3. JS: remove large overlays by z-index, and tooltips by class
    page.evaluate("""() => {
        // Remove any element with high z-index that covers a large area
        // (Adyen promo modal, other product modals)
        const bodyW = document.documentElement.clientWidth;
        const bodyH = document.documentElement.clientHeight;
        for (const el of [...document.querySelectorAll('*')]) {
            if (!el.isConnected) continue;
            const st = window.getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;
            const r = el.getBoundingClientRect();
            const z = parseInt(st.zIndex) || 0;
            // Large overlay with z-index ≥ 100 that is NOT the calendar sidebar
            if (r.width > 280 && r.height > 200 && z >= 100
                    && !el.querySelector('[class*="timetable"]')
                    && !el.querySelector('[class*="erp-visit"]')
                    && !el.querySelector('[class*="q-scrollarea"]')) {
                el.remove();
            }
        }
        // Tooltips / popovers / hints (including Quasar q-tooltip)
        for (const sel of ['[class*="tooltip"]', '[class*="popover"]',
                            '[class*="hint"]', '[class*="tour__"]',
                            '[class*="q-tooltip"]', '[class*="q-menu"]',
                            '[class*="tippy"]', '[class*="balloon"]']) {
            for (const el of document.querySelectorAll(sel)) {
                if (el.isConnected && el.offsetParent) el.remove();
            }
        }
        // Any small dark overlay in the top-right (onboarding hints anchored to toolbar)
        for (const el of [...document.querySelectorAll('*')]) {
            if (!el.isConnected) continue;
            const r = el.getBoundingClientRect();
            if (r.right > 900 && r.top > 30 && r.top < 220
                    && r.height > 30 && r.height < 220
                    && r.width > 50 && r.width < 320) {
                const st = window.getComputedStyle(el);
                const bg = st.backgroundColor;
                const z = parseInt(st.zIndex) || 0;
                // Dark background (tooltip-like) with non-trivial z-index
                if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent' && z > 10
                        && el.tagName !== 'BUTTON' && el.tagName !== 'INPUT'
                        && el.tagName !== 'A' && el.tagName !== 'SELECT') {
                    el.remove();
                }
            }
        }
        // Inline "Start onboarding" card
        for (const el of document.querySelectorAll('button, a, [role="button"]')) {
            if (!el.offsetParent) continue;
            if (el.innerText && el.innerText.trim() === 'Start onboarding') {
                let cur = el.parentElement;
                while (cur && cur !== document.body) {
                    const r = cur.getBoundingClientRect();
                    if (r.height > 40 && r.height < 200 && r.width > 80 && r.width < 420) {
                        cur.style.display = 'none';
                        break;
                    }
                    cur = cur.parentElement;
                }
            }
        }
    }""")
    page.wait_for_timeout(300)


def dismiss_all(page: Page) -> None:
    """Remove every tooltip, popup, and banner before taking a screenshot."""
    page.wait_for_timeout(600)
    nuke_overlays(page)


def dismiss_form_banners(page: Page) -> None:
    """Light cleanup inside the appointment form: only removes banners/tooltips,
    never touches the appointment sidebar itself."""
    page.wait_for_timeout(400)
    # Click onboarding dismiss buttons
    for label in ["Not now", "Skip"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=400):
                btn.click()
                page.wait_for_timeout(300)
        except Exception:
            pass
    # JS: remove only tooltips/hints and the inline "Start onboarding" card
    page.evaluate("""() => {
        for (const sel of ['[class*="tooltip"]', '[class*="popover"]',
                            '[class*="hint"]', '[class*="tour__"]']) {
            for (const el of document.querySelectorAll(sel)) {
                if (el.isConnected && el.offsetParent
                        && !el.closest('[class*="erp-visit"]')) {
                    el.remove();
                }
            }
        }
        for (const el of document.querySelectorAll('button, a, [role="button"]')) {
            if (!el.offsetParent) continue;
            if (el.innerText && el.innerText.trim() === 'Start onboarding') {
                let cur = el.parentElement;
                while (cur && cur !== document.body) {
                    const r = cur.getBoundingClientRect();
                    if (r.height > 40 && r.height < 200 && r.width > 80 && r.width < 420) {
                        cur.style.display = 'none';
                        break;
                    }
                    cur = cur.parentElement;
                }
            }
        }
    }""")
    page.wait_for_timeout(200)


def login(page: Page) -> None:
    print("── Login ──")
    page.goto("https://app.alteg.io")
    page.wait_for_load_state("networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(2000)


def ensure_location(page: Page) -> None:
    if "1253779" not in page.url:
        page.goto(LOC_URL)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(2000)


def scroll_calendar(page: Page) -> None:
    page.evaluate("""() => {
        const cs = document.querySelectorAll(
            '.q-scrollarea__container, [class*="scrollarea__container"]');
        for (const c of cs) c.scrollTop = 200;
    }""")
    page.wait_for_timeout(400)


def open_appointment(page: Page) -> bool:
    """Click a slot → select Booking → return True if form opened."""
    page.mouse.click(370, 250)
    page.wait_for_timeout(1200)
    try:
        booking = page.get_by_text("Booking", exact=True).first
        if booking.is_visible(timeout=1500):
            booking.click()
            page.wait_for_timeout(2500)
            return True
    except Exception:
        pass
    return False


def hide_onboarding_banner(page: Page) -> None:
    """Hide the inline 'Start onboarding' card inside the appointment form."""
    page.evaluate("""() => {
        for (const el of document.querySelectorAll('button, a, [role="button"]')) {
            if (!el.offsetParent) continue;
            if (el.innerText && el.innerText.trim() === 'Start onboarding') {
                let cur = el.parentElement;
                while (cur && cur !== document.body) {
                    const r = cur.getBoundingClientRect();
                    if (r.height > 40 && r.height < 200 && r.width > 80 && r.width < 420) {
                        cur.style.display = 'none';
                        return;
                    }
                    cur = cur.parentElement;
                }
            }
        }
    }""")
    page.wait_for_timeout(200)


# ── Main ─────────────────────────────────────────────────────────────────────

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI"],
    )
    ctx  = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="en-US",
    )
    page = ctx.new_page()

    login(page)
    dismiss_all(page)
    ensure_location(page)

    # Dismiss any post-nav popups
    for label in ["View later", "Later"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=600):
                btn.click(); page.wait_for_timeout(400)
        except Exception:
            pass

    scroll_calendar(page)

    # ── z04: Calendar clean view ──────────────────────────────────────────────
    print("\n── Calendar screenshots ──")
    # Wait for delayed popups (Adyen loads ~1-2 s after navigation)
    page.wait_for_timeout(2000)
    nuke_overlays(page)
    page.wait_for_timeout(800)
    nuke_overlays(page)   # second pass
    page.wait_for_timeout(400)
    # Move mouse to the dark left quick-bar (x<195) — no calendar slot hover,
    # no toolbar button hover → tooltip won't appear
    page.mouse.move(100, 400)
    page.wait_for_timeout(500)
    shot(page, "z04_calendar_scrolled.png",
         clip={"x": CAL_X, "y": 0, "width": CAL_W, "height": 900})

    # ── z05: Hover over free slot ─────────────────────────────────────────────
    nuke_overlays(page)
    page.mouse.move(370, 250)
    page.wait_for_timeout(900)
    shot(page, "z05_hover_shows_new_booking.png",
         clip={"x": CAL_X, "y": 0, "width": CAL_W, "height": 900})

    # ── z06: Click slot → Booking/Event dropdown ──────────────────────────────
    page.mouse.click(370, 250)
    page.wait_for_timeout(1200)
    shot(page, "z06_after_slot_click_dropdown.png",
         clip={"x": CAL_X, "y": 0, "width": CAL_W, "height": 900})

    # ── Open appointment form ─────────────────────────────────────────────────
    # The dropdown from z06 is still open — click Booking directly
    print("\n── Appointment window screenshots ──")
    try:
        booking = page.get_by_text("Booking", exact=True).first
        booking.click(timeout=3000)
        page.wait_for_timeout(2500)
        print("  ✓ Booking clicked")
    except Exception:
        # Fallback: reopen dropdown and try again
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        page.mouse.click(370, 250)
        page.wait_for_timeout(1400)
        try:
            booking = page.get_by_text("Booking", exact=False).first
            booking.click(timeout=3000)
            page.wait_for_timeout(2500)
            print("  ✓ Booking clicked (fallback)")
        except Exception as e:
            print(f"  ✗ Booking click failed: {e}")

    # Light cleanup: dismiss onboarding banners without removing the sidebar
    hide_onboarding_banner(page)
    dismiss_form_banners(page)

    CLIP = {"x": SIDEBAR_X, "y": 0, "width": SIDEBAR_W, "height": SIDEBAR_H}

    # ── z07: Full appointment window (reference) ──────────────────────────────
    shot(page, "z07_appointment_window_full.png", clip=CLIP)

    # ── z08: Left panel — scheduling fields ───────────────────────────────────
    shot(page, "z08_left_panel.png", clip=CLIP)

    # ── z08 advanced: left panel — Advanced/Repeat/Notifications ─────────────
    shot(page, "z08_left_panel_advanced.png", clip=CLIP)

    # ── z09: Center panel — services + status pills ───────────────────────────
    shot(page, "z09_center_panel.png", clip=CLIP)

    # ── z10: Right panel — client fields ─────────────────────────────────────
    shot(page, "z10_right_panel.png", clip=CLIP)

    # ── btn02: Save button — client name filled ───────────────────────────────
    try:
        inp = page.get_by_placeholder("John", exact=False).first
        if inp.is_visible(timeout=600):
            inp.fill("Anna Smith")
            page.wait_for_timeout(600)
    except Exception:
        pass
    shot(page, "btn02_save_button_with_client.png", clip=CLIP)

    print(f"\n✅ All screenshots saved to {OUT}/")
    browser.close()
