"""
Open appointment window, fill in client name, check if save button label changes.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
LOC_URL  = "https://app.alteg.io/timetable/1253779/#mode=1"
OUT      = Path("output/create-appointment/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

n = [0]
def shot(page: Page, name: str, clip=None):
    n[0] += 1
    fname = f"btn{n[0]:02d}_{name}.png"
    kwargs = {"path": str(OUT / fname)}
    if clip:
        kwargs["clip"] = clip
    page.screenshot(**kwargs)
    print(f"  📸 {fname}")
    return fname


def close_popups(page: Page):
    page.wait_for_timeout(1500)
    for sel in ["button[aria-label='Close']", "[class*='close']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=400):
                el.click(); page.wait_for_timeout(500); break
        except Exception: pass
    else:
        page.keyboard.press("Escape"); page.wait_for_timeout(400)
    # force-remove remaining modals
    page.evaluate("""() => {
        for (const sel of ['[class*="modal"]','[class*="dialog"]','[class*="popup"]','[class*="adyen"]','[class*="Adyen"]','[role="dialog"]']) {
            for (const el of document.querySelectorAll(sel)) {
                const r = el.getBoundingClientRect();
                if (r.width > 300 && r.height > 200 && !el.querySelector('[class*="timetable"]'))
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


def get_buttons(page: Page):
    return page.evaluate("""() =>
        Array.from(document.querySelectorAll('button,[role="button"]'))
             .filter(el => el.offsetParent !== null && el.innerText.trim())
             .map(el => el.innerText.trim().substring(0, 80))
    """)


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

    # Open appointment window
    print("\n── Open appointment window ──")
    page.mouse.click(370, 250)
    page.wait_for_timeout(1200)
    try:
        booking = page.get_by_text("Booking", exact=True).first
        if booking.is_visible(timeout=1500):
            booking.click()
            page.wait_for_timeout(2500)
            print("  ✓ clicked 'Booking'")
    except Exception:
        pass

    # Dismiss onboarding tooltip
    try:
        not_now = page.get_by_role("button", name="Not now").first
        if not_now.is_visible(timeout=800):
            not_now.click()
            page.wait_for_timeout(400)
            print("  ✓ dismissed onboarding")
    except Exception:
        pass

    page.wait_for_timeout(500)

    # ── State 1: No client filled ──────────────────────────────────────────────
    print("\n── State 1: No client (blank form) ──")
    buttons_blank = get_buttons(page)
    print("  Buttons:", buttons_blank)

    # Capture save area with no client
    shot(page, "save_button_no_client", clip={"x": 340, "y": 790, "width": 1100, "height": 80})

    # ── Fill in client name ────────────────────────────────────────────────────
    print("\n── Fill client name ──")
    client_filled = False
    for placeholder in ["John", "Client name", "client", "name", "Name"]:
        try:
            inp = page.get_by_placeholder(placeholder, exact=False).first
            if inp.is_visible(timeout=600):
                inp.click()
                page.wait_for_timeout(300)
                inp.fill("Anna Smith")
                page.wait_for_timeout(800)
                print(f"  ✓ filled placeholder='{placeholder}' with 'Anna Smith'")
                client_filled = True
                break
        except Exception:
            pass

    if not client_filled:
        # Try by label
        try:
            inp = page.locator("input").filter(has_placeholder=True).first
            if inp.is_visible(timeout=600):
                inp.fill("Anna Smith")
                page.wait_for_timeout(800)
                print("  ✓ filled first visible input")
                client_filled = True
        except Exception:
            pass

    # ── State 2: Client name filled ───────────────────────────────────────────
    print("\n── State 2: Client name filled ──")
    buttons_with_client = get_buttons(page)
    print("  Buttons:", buttons_with_client)

    shot(page, "save_button_with_client", clip={"x": 340, "y": 790, "width": 1100, "height": 80})
    shot(page, "full_window_with_client")

    # ── Compare ────────────────────────────────────────────────────────────────
    print("\n── Comparison ──")
    save_blank  = [b for b in buttons_blank        if "save" in b.lower() or "appointment" in b.lower()]
    save_client = [b for b in buttons_with_client  if "save" in b.lower() or "appointment" in b.lower()]
    print(f"  Save button (no client):     {save_blank}")
    print(f"  Save button (client filled): {save_client}")

    if save_blank != save_client:
        print("  ✅ Button label CHANGED after filling client name")
    else:
        print("  ⬜ Button label did NOT change")

    print(f"\n✅ Done — {n[0]} screenshots in {OUT}/")
    browser.close()
