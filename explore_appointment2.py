"""
Targeted exploration: click a free slot → capture New Booking dialog.
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
OUT      = Path("output/create-appointment/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

idx = [0]
def shot(page, name):
    idx[0] += 1
    f = f"{idx[0]:02d}_{name}.png"
    page.screenshot(path=str(OUT / f))
    print(f"  📸 {f}")
    return f

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False, slow_mo=400,
        args=["--lang=en-US", "--disable-features=Translate"],
    )
    ctx  = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    page = ctx.new_page()

    # ── Login ──────────────────────────────────────────────────────────────────
    print("\n── Login ──")
    page.goto("https://app.alteg.io")
    page.wait_for_load_state("networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(2000)

    # ── Close post-login popup (× then "View later") ───────────────────────────
    print("\n── Closing post-login popup ──")
    shot(page, "popup_before_close")

    # Try × close button
    for sel in [
        "button.sc-dialog__close", "[class*='dialog__close']",
        "[class*='modal__close']",  "[class*='close-button']",
        "button.close",             "[aria-label='Close']",
        "button:has(.q-icon)",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=700):
                btn.click(); page.wait_for_timeout(500)
                print(f"  ✓ × closed via {sel}"); break
        except Exception: pass
    else:
        page.keyboard.press("Escape"); page.wait_for_timeout(500)

    # Try "View later"
    for label in ["View later", "Later", "Maybe later", "Skip", "Dismiss", "Close"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=500):
                btn.click(); page.wait_for_timeout(500)
                print(f"  ✓ '{label}' clicked"); break
        except Exception: pass

    shot(page, "calendar_clean")

    # ── Scroll calendar to 10:00 ───────────────────────────────────────────────
    print("\n── Scrolling to top of calendar ──")
    # Scroll the calendar container (not window) to top
    page.evaluate("""
        const scroller = document.querySelector(
            '[class*="timetable__scroll"], [class*="calendar__scroll"], ' +
            '[class*="scroll-area"], .q-scrollarea__container'
        );
        if (scroller) scroller.scrollTop = 0;
        else window.scrollTo(0, 0);
    """)
    page.wait_for_timeout(800)
    shot(page, "calendar_scrolled_top")

    # ── Inspect the calendar grid to find clickable cells ─────────────────────
    print("\n── Inspecting calendar grid structure ──")
    cell_info = page.evaluate("""() => {
        // Look for the time-slot rows/cells in the timetable
        const selectors = [
            '[class*="record-slot"]',
            '[class*="time-cell"]',
            '[class*="timetable-record"]',
            '[class*="slot"]',
            '[class*="cell"]',
        ];
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            if (els.length > 3) {
                const sample = Array.from(els).slice(0, 5).map(el => ({
                    tag: el.tagName,
                    cls: el.className.substring(0, 80),
                    rect: el.getBoundingClientRect(),
                    text: el.innerText.trim().substring(0, 30),
                }));
                return {selector: sel, count: els.length, sample};
            }
        }
        return null;
    }""")
    print(f"  Cell info: {json.dumps(cell_info, indent=2)[:600]}")

    # ── Find the first empty slot by scanning all cells ───────────────────────
    print("\n── Clicking first empty time slot ──")
    clicked = page.evaluate("""() => {
        // Find cells that are empty (no child records/appointments)
        const cols = document.querySelectorAll('[class*="timetable__col"], [class*="staff-col"]');
        if (cols.length > 0) {
            // Click inside the first staff column at a mid-height position
            const col = cols[0];
            const rect = col.getBoundingClientRect();
            return {found: 'column', x: rect.left + rect.width/2, y: rect.top + 80, cls: col.className.substring(0,60)};
        }
        return null;
    }""")
    print(f"  Column found: {clicked}")

    if clicked and clicked.get("found"):
        x, y = clicked["x"], clicked["y"]
        print(f"  Clicking at ({x:.0f}, {y:.0f})")
        page.mouse.click(x, y)
        page.wait_for_timeout(1500)
        shot(page, "after_col_click")
    else:
        # Fallback: use known pixel coordinates from the screenshot
        # Calendar content starts at x≈270, employee columns ~130px wide each
        # Mary's column centre ≈ 335, 11:00 row ≈ y depends on scroll
        # After scrolling to top, 10:00 row is near y≈120
        print("  Fallback: clicking by known coordinates (Mary @ ~11:00)")
        page.mouse.click(335, 150)
        page.wait_for_timeout(1500)
        shot(page, "after_fallback_click")

    # ── Detect and analyse the New Booking dialog ─────────────────────────────
    print("\n── Detecting New Booking dialog ──")
    page.wait_for_timeout(1000)

    dialog_found = page.evaluate("""() => {
        const sels = [
            '[class*="modal"]', '[class*="dialog"]', '[class*="drawer"]',
            '[role="dialog"]',  '[class*="booking"]', '[class*="appointment"]',
            '[class*="record-form"]', '[class*="new-record"]',
        ];
        for (const sel of sels) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) {
                return {found: true, sel, cls: el.className.substring(0,80)};
            }
        }
        return {found: false};
    }""")
    print(f"  Dialog: {dialog_found}")
    shot(page, "dialog_state")

    if not dialog_found.get("found"):
        # The calendar might need a different interaction — try clicking a time label row
        print("  No dialog yet. Dumping all clickable elements near calendar grid...")
        grid_els = page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            const hits = [];
            for (const el of all) {
                if (el.offsetParent === null) continue;
                const r = el.getBoundingClientRect();
                // Elements in the main calendar area (x > 250, y > 80, not too tall)
                if (r.left > 250 && r.top > 80 && r.height < 40 && r.height > 5
                    && r.width > 60 && hits.length < 30) {
                    hits.push({
                        tag: el.tagName,
                        cls: el.className.substring(0, 60),
                        x: Math.round(r.left + r.width/2),
                        y: Math.round(r.top + r.height/2),
                        text: el.innerText.trim().substring(0, 20),
                    });
                }
            }
            return hits;
        }""")
        print("  Calendar area elements:")
        for e in grid_els[:20]:
            print(f"    ({e['x']},{e['y']}) {e['tag']} cls={e['cls'][:40]} text={e['text']!r}")

        # Try clicking the first calendar-area element
        if grid_els:
            el = grid_els[0]
            print(f"  Clicking ({el['x']}, {el['y']}) — {el['cls'][:40]!r}")
            page.mouse.click(el["x"], el["y"])
            page.wait_for_timeout(1500)
            shot(page, "after_grid_el_click")

    # ── Final: dump all inputs + buttons visible now ───────────────────────────
    print("\n── All visible inputs + buttons ──")
    inputs = page.evaluate("""() =>
        Array.from(document.querySelectorAll('input,select,textarea'))
             .filter(el => el.offsetParent !== null)
             .map(el => ({tag:el.tagName, type:el.type, name:el.name,
                          placeholder:el.placeholder, value:el.value.substring(0,30)}))
    """)
    for i in inputs:
        print(f"  INPUT {i['type']} name={i['name']!r} placeholder={i['placeholder']!r}")

    buttons = page.evaluate("""() =>
        Array.from(document.querySelectorAll('button,[role="button"]'))
             .filter(el => el.offsetParent !== null && el.innerText.trim())
             .map(el => ({text: el.innerText.trim().substring(0,40),
                          cls:  el.className.substring(0,60)}))
    """)
    for b in buttons:
        print(f"  BTN {b['text']!r}")

    all_text = page.evaluate("""() =>
        [...new Set(
            Array.from(document.querySelectorAll('*'))
                 .filter(el => el.offsetParent !== null && el.children.length === 0
                             && el.innerText && el.innerText.trim().length > 0
                             && el.innerText.trim().length < 150)
                 .map(el => el.innerText.trim())
        )]
    """)
    print(f"\n  All visible text ({len(all_text)} strings):")
    for t in all_text:
        print(f"    {t!r}")

    shot(page, "final")

    # Save JSON
    data = {"inputs": inputs, "buttons": buttons, "text": all_text,
            "dialog": dialog_found, "cell_info": cell_info}
    json_out = Path("output/create-appointment/exploration2.json")
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {json_out}")

    input("\n⏸  Browser open — inspect if needed. Press Enter to close.")
    browser.close()
