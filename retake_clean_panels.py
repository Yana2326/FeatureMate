"""
Retake z08_left_panel.png and z09_center_panel.png without the onboarding tooltip.
Dismisses the tooltip via "Not now" before capturing.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
LOC_URL  = "https://app.alteg.io/timetable/1253779/#mode=1"
OUT      = Path("output/create-appointment/screenshots")

def close_popups(page: Page):
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
        for (const sel of ['[class*="modal"]','[class*="dialog"]','[class*="adyen"]',
                           '[class*="Adyen"]','[role="dialog"]']) {
            for (const el of document.querySelectorAll(sel)) {
                const r = el.getBoundingClientRect();
                if (r.width > 300 && r.height > 200
                    && !el.querySelector('[class*="timetable"]'))
                    el.remove();
            }
        }
    }""")
    page.wait_for_timeout(300)
    for label in ["View later", "Later"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=400):
                btn.click(); page.wait_for_timeout(400); break
        except Exception: pass


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI"],
    )
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    page = ctx.new_page()

    # Login
    print("── Login ──")
    page.goto("https://app.alteg.io")
    page.wait_for_load_state("networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(2000)
    close_popups(page)

    if "1253779" not in page.url:
        page.goto(LOC_URL)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        close_popups(page)

    page.evaluate("""() => {
        const cs = document.querySelectorAll('.q-scrollarea__container, [class*="scrollarea__container"]');
        for (const c of cs) c.scrollTop = 200;
    }""")
    page.wait_for_timeout(500)

    # Open appointment
    print("── Opening appointment window ──")
    page.mouse.click(370, 250)
    page.wait_for_timeout(1200)
    try:
        booking = page.get_by_text("Booking", exact=True).first
        if booking.is_visible(timeout=1500):
            booking.click()
            page.wait_for_timeout(2500)
            print("  ✓ Booking clicked")
    except Exception: pass

    # ── Dismiss the onboarding tooltip ──────────────────────────────────────────
    print("── Dismissing onboarding tooltip ──")
    dismissed = False
    for label in ["Not now", "Skip", "Close", "Dismiss"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=800):
                btn.click()
                page.wait_for_timeout(600)
                print(f"  ✓ dismissed via '{label}'")
                dismissed = True
                break
        except Exception: pass

    # Hide the inline "Start onboarding" card via CSS.
    # Find the button itself, then walk up to the first ancestor that is a
    # self-contained card: height < 200px AND width < 400px.
    banner_hidden = page.evaluate("""() => {
        // Find the "Start onboarding" button
        for (const el of document.querySelectorAll('button, a, [role="button"]')) {
            if (!el.offsetParent) continue;
            if (el.innerText && el.innerText.trim() === 'Start onboarding') {
                // Walk up ancestors looking for a card-like element
                let cur = el.parentElement;
                while (cur && cur !== document.body) {
                    const r = cur.getBoundingClientRect();
                    if (r.height > 40 && r.height < 200 && r.width > 80 && r.width < 400) {
                        cur.style.display = 'none';
                        return `hidden card h=${r.height} w=${r.width} cls=${cur.className.substring(0,50)}`;
                    }
                    cur = cur.parentElement;
                }
            }
        }
        return null;
    }""")
    print(f"  Onboarding banner: {banner_hidden}")
    page.wait_for_timeout(400)

    # Get dialog bounds
    dialog = page.evaluate("""() => {
        for (const el of document.querySelectorAll('*')) {
            if (!el.offsetParent) continue;
            const r = el.getBoundingClientRect();
            const cls = (el.className || '').toString();
            if (r.left >= 190 && r.width >= 800 && r.height >= 500 && r.top <= 10
                && (cls.includes('visit') || cls.includes('appointment')
                    || cls.includes('record') || cls.includes('booking')
                    || cls.includes('drawer') || cls.includes('panel'))) {
                return {x: r.left, y: r.top, w: r.width, h: r.height};
            }
        }
        return {x: 340, y: 0, w: 1100, h: 900};
    }""")
    print(f"  Dialog: {dialog}")

    dx, dy, dw, dh = dialog["x"], dialog["y"], dialog["w"], dialog["h"]

    # Left panel: first 27% of dialog width
    left_w = int(dw * 0.27)
    left_clip  = {"x": dx, "y": dy, "width": left_w, "height": dh}

    # Center panel: next 43%
    center_x = dx + left_w
    center_w = int(dw * 0.43)
    center_clip = {"x": center_x, "y": dy, "width": center_w, "height": dh}

    # Take screenshots
    left_path   = str(OUT / "z08_left_panel.png")
    center_path = str(OUT / "z09_center_panel.png")

    page.screenshot(path=left_path,   clip=left_clip)
    page.screenshot(path=center_path, clip=center_clip)

    print(f"\n✅ Saved:")
    print(f"  {left_path}   (clip: {left_clip})")
    print(f"  {center_path} (clip: {center_clip})")
    browser.close()
