"""
Explore the Appointment Calendar → New Booking flow in Altegio.
Captures screenshots and dumps all UI element info for article writing.
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
BASE_URL = "https://app.alteg.io"
OUT      = Path("output/create-appointment/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

shot_index = [0]

def screenshot(page: Page, name: str) -> str:
    shot_index[0] += 1
    fname = f"{shot_index[0]:02d}_{name}.png"
    path  = str(OUT / fname)
    page.screenshot(path=path, full_page=False)
    print(f"  📸 {fname}")
    return fname

def close_any_popup(page: Page):
    """Close any visible modal/popup/banner. Tries all known selectors."""
    selectors = [
        # Altegio-specific
        ".sc-dialog__close",
        ".sc-modal__close",
        ".modal__close",
        "[class*='modal__close']",
        "[class*='dialog__close']",
        "[class*='popup__close']",
        "[class*='notification__close']",
        "[class*='banner__close']",
        "[class*='toast__close']",
        # Generic
        "button[class*='close']",
        "button.close",
        "[aria-label='Close']",
        "[aria-label='close']",
        "[aria-label='Dismiss']",
        # Overlay backdrop click (last resort)
        ".sc-overlay",
        ".modal-overlay",
        "[class*='overlay']",
    ]
    closed = 0
    for sel in selectors:
        try:
            btns = page.locator(sel)
            for i in range(btns.count()):
                btn = btns.nth(i)
                if btn.is_visible(timeout=400):
                    btn.click()
                    page.wait_for_timeout(400)
                    print(f"  ✓ closed popup via {sel}[{i}]")
                    closed += 1
        except Exception:
            pass
    # Also dismiss browser translate bar via keyboard shortcut
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    except Exception:
        pass
    return closed

def dump_inputs(page: Page, context: str) -> list:
    data = page.eval_on_selector_all(
        "input, select, textarea",
        """els => els.map(el => ({
            tag:         el.tagName,
            type:        el.type || '',
            name:        el.name || '',
            id:          el.id   || '',
            placeholder: el.placeholder || '',
            value:       el.value || '',
            label:       (document.querySelector('label[for="' + el.id + '"]') || {}).innerText || '',
            visible:     el.offsetParent !== null,
            className:   el.className
        }))"""
    )
    visible = [d for d in data if d["visible"]]
    print(f"\n  Inputs in [{context}] ({len(visible)} visible):")
    for d in visible:
        print(f"    {d['tag']} type={d['type']} name={d['name']} placeholder={d['placeholder']!r} label={d['label']!r}")
    return visible

def dump_buttons(page: Page, context: str) -> list:
    data = page.eval_on_selector_all(
        "button, [role='button'], input[type='submit'], input[type='button']",
        """els => els.map(el => ({
            text:    (el.innerText || el.value || '').trim(),
            type:    el.type || '',
            visible: el.offsetParent !== null,
            class:   el.className
        }))"""
    )
    visible = [d for d in data if d["visible"] and d["text"]]
    print(f"\n  Buttons in [{context}] ({len(visible)} visible):")
    for d in visible:
        print(f"    '{d['text']}'  class={d['class'][:60]}")
    return visible

def dump_modal_text(page: Page) -> str:
    texts = page.eval_on_selector_all(
        "[class*='modal'] *, [class*='dialog'] *, [class*='popup'] *, [class*='drawer'] *",
        """els => [...new Set(
            els.filter(el => el.offsetParent !== null && el.children.length === 0)
               .map(el => el.innerText.trim())
               .filter(t => t.length > 0 && t.length < 200)
        )]"""
    )
    print(f"\n  Visible text in modal ({len(texts)} strings):")
    for t in texts[:60]:
        print(f"    {t!r}")
    return "\n".join(texts)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        slow_mo=300,
        args=[
            "--lang=en-US",
            "--disable-features=Translate",
            "--disable-translate",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="en-US",
    )
    # Disable browser translation prompt via CDP
    context.add_init_script("""
        Object.defineProperty(navigator, 'language',  { get: () => 'en-US' });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    """)
    page = context.new_page()
    results = {}

    # ── 1. Login ──────────────────────────────────────────────────────────────
    print("\n── Step 1: Login ──")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    screenshot(page, "login_page")

    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    screenshot(page, "credentials_filled")

    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    screenshot(page, "after_login_with_popup")

    # Step 1: close × button on the promo popup
    print("  Closing popup × button...")
    for sel in [
        "button.sc-dialog__close",
        "button[class*='dialog__close']",
        "button[class*='modal__close']",
        ".sc-modal__close",
        "button.close",
        "[aria-label='Close']",
        "[aria-label='close']",
        # SVG × icons inside buttons
        "button:has(svg)",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=600):
                btn.click()
                page.wait_for_timeout(600)
                print(f"  ✓ closed × via {sel}")
                break
        except Exception:
            pass
    else:
        # Fallback: press Escape
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    # Step 2: click "View later" if still visible
    print("  Looking for 'View later' button...")
    for label in ["View later", "Later", "Maybe later", "Skip", "Not now"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=600):
                btn.click()
                page.wait_for_timeout(600)
                print(f"  ✓ clicked '{label}'")
                break
        except Exception:
            pass

    page.wait_for_timeout(500)
    screenshot(page, "dashboard_after_login")
    print(f"  URL: {page.url}")

    # ── 2. Find Appointment Calendar nav ──────────────────────────────────────
    print("\n── Step 2: Navigate to Appointment Calendar ──")

    # Dump top-level nav links to find the right one
    nav_items = page.eval_on_selector_all(
        "nav a, [class*='sidebar'] a, [class*='menu'] a, [class*='nav'] a",
        "els => els.map(el => ({text: el.innerText.trim(), href: el.href}))"
    )
    print("  Nav links found:")
    for n in nav_items:
        if n["text"]:
            print(f"    {n['text']!r}  →  {n['href']}")

    results["nav_items"] = nav_items

    # Try clicking "Appointment Calendar" or "Timetable" link
    calendar_clicked = False
    for label in ["Appointment calendar", "Calendar", "Timetable", "Журнал"]:
        try:
            link = page.get_by_role("link", name=label, exact=False).first
            if link.is_visible(timeout=1500):
                link.click()
                page.wait_for_load_state("networkidle", timeout=8000)
                page.wait_for_timeout(1000)
                close_any_popup(page)
                screenshot(page, f"calendar_via_{label.lower().replace(' ','_')}")
                print(f"  ✓ navigated via '{label}'")
                calendar_clicked = True
                break
        except Exception:
            pass

    if not calendar_clicked:
        # Already on timetable from login redirect
        print("  Already on calendar page (redirect from login)")
        close_any_popup(page)
        screenshot(page, "calendar_page")

    print(f"  URL: {page.url}")

    # ── 3. Capture the calendar page fully ────────────────────────────────────
    print("\n── Step 3: Capture calendar overview ──")
    page.wait_for_timeout(1000)
    close_any_popup(page)
    screenshot(page, "calendar_overview")

    # Dump what's visible on the calendar
    dump_buttons(page, "calendar page")

    # ── 4. Click a free time slot ──────────────────────────────────────────────
    print("\n── Step 4: Click a free time slot ──")

    slot_clicked = False
    # Try various selectors for empty calendar cells
    for sel in [
        "[class*='timetable-cell']:not([class*='busy'])",
        "[class*='time-slot']:not([class*='busy'])",
        "[class*='free-slot']",
        "[class*='empty-slot']",
        "[class*='available']",
        "td.free",
        "[class*='cell--free']",
        "[class*='slot--empty']",
    ]:
        try:
            cells = page.locator(sel)
            count = cells.count()
            if count > 0:
                print(f"  Found {count} cells via {sel!r}")
                # Click the 3rd one to avoid header rows
                idx = min(2, count - 1)
                cells.nth(idx).click(timeout=3000)
                page.wait_for_timeout(1500)
                screenshot(page, "after_slot_click")
                slot_clicked = True
                print(f"  ✓ clicked cell {idx}")
                break
        except Exception as e:
            pass

    if not slot_clicked:
        print("  ⚠ Could not find free slot via class selectors — trying coordinate click")
        # Click in the middle of the calendar area
        page.mouse.click(500, 400)
        page.wait_for_timeout(1500)
        screenshot(page, "after_coord_click")

    # ── 5. Check if a modal / new-booking dialog opened ───────────────────────
    print("\n── Step 5: New booking dialog ──")
    page.wait_for_timeout(1000)

    # Check for any modal/dialog/drawer
    modal_visible = False
    for modal_sel in [
        "[class*='modal']:not([class*='hidden'])",
        "[class*='dialog']",
        "[class*='drawer']",
        "[class*='booking-form']",
        "[class*='appointment-form']",
        "[class*='new-booking']",
        "[role='dialog']",
    ]:
        try:
            el = page.locator(modal_sel).first
            if el.is_visible(timeout=1000):
                print(f"  ✓ Modal/dialog found: {modal_sel}")
                modal_visible = True
                break
        except Exception:
            pass

    if modal_visible:
        screenshot(page, "new_booking_dialog_opened")
        modal_text = dump_modal_text(page)
        modal_inputs = dump_inputs(page, "new booking dialog")
        modal_buttons = dump_buttons(page, "new booking dialog")
        results["modal_text"]    = modal_text
        results["modal_inputs"]  = modal_inputs
        results["modal_buttons"] = modal_buttons
    else:
        print("  ⚠ No modal detected — check screenshot")
        screenshot(page, "no_modal_state")
        modal_text   = dump_modal_text(page)
        modal_inputs = dump_inputs(page, "full page after click")
        modal_buttons = dump_buttons(page, "full page after click")
        results["modal_text"]    = modal_text
        results["modal_inputs"]  = modal_inputs
        results["modal_buttons"] = modal_buttons

    # ── 6. Scroll through the form and capture all fields ─────────────────────
    print("\n── Step 6: Scroll and capture all form fields ──")

    # Try to capture each major section with screenshots
    for field_name in ["employee", "service", "client", "date", "time"]:
        try:
            el = page.locator(
                f"[class*='{field_name}'], [data-field='{field_name}'], "
                f"label:has-text('{field_name.capitalize()}')"
            ).first
            if el.is_visible(timeout=500):
                el.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
        except Exception:
            pass

    screenshot(page, "new_booking_full_form")

    # Try to open dropdowns to capture options
    print("\n  Trying to open dropdowns...")
    for sel in ["[class*='select']", "[class*='dropdown']", "[class*='v-select']"]:
        try:
            dropdowns = page.locator(sel)
            count = dropdowns.count()
            if count > 0:
                print(f"  Found {count} elements via {sel}")
                break
        except Exception:
            pass

    # Capture any tabs inside the dialog
    tabs = page.eval_on_selector_all(
        "[class*='tab']:not(script), [role='tab']",
        """els => els.filter(el => el.offsetParent !== null)
                     .map(el => ({text: el.innerText.trim(), active: el.className.includes('active') || el.getAttribute('aria-selected') === 'true'}))
                     .filter(el => el.text.length > 0)"""
    )
    if tabs:
        print(f"\n  Tabs found ({len(tabs)}):")
        for t in tabs:
            print(f"    {'[active]' if t['active'] else '       '} {t['text']!r}")
        results["tabs"] = tabs

        # Click each tab and screenshot
        for i, tab in enumerate(tabs[:6]):
            try:
                tab_el = page.locator(
                    f"[class*='tab']:not(script), [role='tab']"
                ).filter(has_text=tab["text"]).first
                if tab_el.is_visible(timeout=500):
                    tab_el.click()
                    page.wait_for_timeout(600)
                    screenshot(page, f"tab_{i+1}_{tab['text'][:20].replace(' ','_').lower()}")
            except Exception:
                pass

    # ── 7. Capture all visible text in the form ────────────────────────────────
    print("\n── Step 7: Full form text extraction ──")
    all_text = page.eval_on_selector_all(
        "*",
        """els => [...new Set(
            els.filter(el => el.offsetParent !== null
                          && el.children.length === 0
                          && el.innerText
                          && el.innerText.trim().length > 0
                          && el.innerText.trim().length < 300)
               .map(el => el.innerText.trim())
        )]"""
    )
    print(f"  All visible text strings: {len(all_text)}")
    results["all_visible_text"] = all_text

    # ── 8. Try clicking "New booking" button if dialog not open ───────────────
    if not modal_visible:
        print("\n── Step 8: Try 'New booking' / '+' button ──")
        for label in ["New booking", "New appointment", "Add booking", "Add appointment", "+"]:
            try:
                btn = page.get_by_role("button", name=label, exact=False).first
                if btn.is_visible(timeout=1000):
                    btn.click()
                    page.wait_for_timeout(1500)
                    screenshot(page, f"after_btn_{label[:10].replace(' ','_')}")
                    print(f"  ✓ clicked '{label}'")
                    modal_text2   = dump_modal_text(page)
                    modal_inputs2 = dump_inputs(page, f"after '{label}'")
                    modal_buttons2 = dump_buttons(page, f"after '{label}'")
                    results["modal_text2"]    = modal_text2
                    results["modal_inputs2"]  = modal_inputs2
                    results["modal_buttons2"] = modal_buttons2
                    break
            except Exception:
                pass

    # Final full-page screenshot
    screenshot(page, "final_state")

    # ── Save JSON ──────────────────────────────────────────────────────────────
    json_path = Path("output/create-appointment/exploration.json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON saved: {json_path}")

    browser.close()

print("\nDone. Check output/create-appointment/screenshots/")
