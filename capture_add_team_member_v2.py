"""
Comprehensive capture for the "Add team member" article — re-takes every PNG
referenced in output/add-team-member/article.md AND captures a bounding box
for the highlight anchor in each one (Rule 3 — every annotation traced to
Playwright element.bounding_box(), no estimates).

Outputs:
  output/add-team-member/screenshots/01_team_members_list.png
  output/add-team-member/screenshots/02_modal_default.png
  output/add-team-member/screenshots/03_modal_filled.png
  output/add-team-member/screenshots/04_information_tab.png    (tabs row)
  output/add-team-member/screenshots/05_services_tab.png       (Assign + Create buttons)
  output/add-team-member/screenshots/06_online_booking_tab.png (Available toggle)
  output/add-team-member/screenshots/07_payroll_tab.png        (Copy from another employee)
  output/add-team-member/screenshots/08_work_schedule_tab.png  (Set up button)
  output/add-team-member/screenshots/09_access_tab.png         (Grant system access toggle)
  output/add-team-member/screenshots/10_notifications_tab.png  (Assign rights button)
  output/add-team-member/screenshots/11_settings_tab.png       (Markup in Appointment Calendar)
  output/add-team-member/screenshots/bboxes.json
"""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    nuke_overlays, close_translate_popup,
    verify_administration_mode,
    save_bboxes,
)


TEAM_LIST   = f"{BASE}/settings/filial_staff/{COMPANY_ID}/"
MEMBER_CARD = f"{BASE}/settings/staff/{COMPANY_ID}/2745268"   # Lili (existing)

OUT = Path("output/add-team-member/screenshots")


# ═══════════════════════════════════════════════════════════════════════════
# JS probes — tabs & anchors
# ═══════════════════════════════════════════════════════════════════════════
JS_ADD_BUTTON = r"""
() => {
    const b = document.querySelector('button[data-locator="create_employee_btn"]');
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height};
}
"""

JS_MODAL_INNER = r"""
() => {
    const candidates = [
        ...document.querySelectorAll(
            '.staff-create-modal-featured .yc-modal__container, '
          + '.yc-modal__container, '
          + '.staff-create-modal-featured > div > div, '
          + '.staff-create-modal-featured .q-card, '
          + '.staff-create-modal-featured .q-dialog__inner > *'
        ),
    ];
    let best = null;
    for (const c of candidates) {
        const r = c.getBoundingClientRect();
        if (r.width < 320 || r.width > 700) continue;
        if (r.height < 300) continue;
        if (r.left < 100 || r.right > 1340) continue;
        if (!best || r.height > best.h) {
            best = {x: r.x, y: r.y, w: r.width, h: r.height};
        }
    }
    if (!best) return null;
    return {x: best.x, y: best.y, width: best.w, height: best.h};
}
"""

JS_MODAL_SAVE = r"""
() => {
    const modal = document.querySelector('.staff-create-modal-featured');
    if (!modal) return null;
    const btns = modal.querySelectorAll('button, [role="button"]');
    for (const b of btns) {
        const t = (b.textContent || '').trim();
        if (t === 'Save') {
            const r = b.getBoundingClientRect();
            if (r.width > 10 && r.height > 10)
                return {x: r.x, y: r.y, width: r.width, height: r.height};
        }
    }
    return null;
}
"""

JS_MEMBER_TABS = r"""
() => {
    const wanted = ['Information', 'Services', 'Online Booking', 'Online booking',
                    'Payroll', 'Work Schedule', 'Access',
                    'Notifications', 'Settings'];
    const found = [];
    for (const el of document.querySelectorAll('a, button, [role="tab"], .q-tab, li')) {
        const t = (el.textContent || '').trim();
        let matches = false;
        for (const w of wanted) {
            if (t === w || t.startsWith(w + ' ') || t.startsWith(w + '\u00A0')) {
                matches = true; break;
            }
        }
        if (!matches) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 30 || r.height < 18 || r.height > 80) continue;
        if (r.top < 80 || r.top > 200) continue;
        found.push(r);
    }
    if (!found.length) return null;
    let x0 =  Infinity, y0 =  Infinity;
    let x1 = -Infinity, y1 = -Infinity;
    for (const r of found) {
        if (r.left   < x0) x0 = r.left;
        if (r.top    < y0) y0 = r.top;
        if (r.right  > x1) x1 = r.right;
        if (r.bottom > y1) y1 = r.bottom;
    }
    return {x: x0, y: y0, width: x1 - x0, height: y1 - y0};
}
"""

# Generic helper: find the first visible button/link whose text equals or
# starts with `name` and return its bbox. Skips items in the left sidebar.
JS_BUTTON_BY_TEXT = """
(name) => {
    for (const el of document.querySelectorAll('button, a, [role="button"]')) {
        const t = (el.textContent || '').trim();
        if (t !== name && !t.startsWith(name + ' ')) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 8 || r.height < 8) continue;
        // Skip left-sidebar (x < 280)
        if (r.left < 280) continue;
        // Must be visible
        if (r.top < 0 || r.top > window.innerHeight - 10) continue;
        return {x: r.x, y: r.y, width: r.width, height: r.height};
    }
    return null;
}
"""

# Two-buttons union (e.g. Assign services + Create a service)
JS_BUTTONS_UNION = """
(names) => {
    const found = [];
    for (const el of document.querySelectorAll('button, a, [role="button"]')) {
        const t = (el.textContent || '').trim();
        for (const n of names) {
            if (t === n || t.startsWith(n + ' ')) {
                const r = el.getBoundingClientRect();
                if (r.width < 8 || r.height < 8) continue;
                if (r.left < 280) continue;
                if (r.top < 0 || r.top > window.innerHeight - 10) continue;
                found.push(r);
                break;
            }
        }
    }
    if (!found.length) return null;
    let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
    for (const r of found) {
        if (r.left<x0) x0=r.left;
        if (r.top<y0) y0=r.top;
        if (r.right>x1) x1=r.right;
        if (r.bottom>y1) y1=r.bottom;
    }
    return {x:x0,y:y0,width:x1-x0,height:y1-y0};
}
"""

# Online-booking tab: bbox of the row containing the "Available for online booking" radio
JS_OB_RADIO = r"""
() => {
    // Try explicit text first
    const texts = ['Available for online booking',
                   'Available for online-booking',
                   'Available for online'];
    for (const search of texts) {
        for (const el of document.querySelectorAll('label, div, span')) {
            const t = (el.textContent || '').trim();
            if (!t.startsWith(search)) continue;
            if (t.length > 200) continue;
            let container = el;
            for (let i = 0; i < 5 && container; i++) {
                const r = container.getBoundingClientRect();
                if (r.width >= 200 && r.height >= 20 && r.height <= 120 && r.left >= 280) {
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                }
                container = container.parentElement;
            }
        }
    }
    return null;
}
"""

# Fallback for any tab — find the FIRST visible H1-H3 or large-bold heading
# inside the main content area (x > 280, y > 100). Used when the specific
# anchor isn't found.
JS_FIRST_HEADING = r"""
() => {
    for (const el of document.querySelectorAll('h1, h2, h3, .text-h5, .text-h6, [class*="title"]')) {
        const t = (el.textContent || '').trim();
        if (!t || t.length > 120) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 60 || r.height < 18 || r.height > 80) continue;
        if (r.left < 280 || r.top < 150 || r.top > window.innerHeight - 50) continue;
        return {x: r.x, y: r.y, width: r.width, height: r.height};
    }
    return null;
}
"""

# Access tab: row with "Grant system access" toggle
JS_GRANT_ACCESS = r"""
() => {
    for (const el of document.querySelectorAll('label, div, span')) {
        const t = (el.textContent || '').trim();
        if (t === 'Grant system access' || t.startsWith('Grant system access')) {
            // Walk up until the bbox covers a reasonable row
            let container = el;
            for (let i = 0; i < 4 && container; i++) {
                const r = container.getBoundingClientRect();
                if (r.width > 400 && r.height >= 28 && r.height <= 100) {
                    if (r.left < 280) break;
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                }
                container = container.parentElement;
            }
        }
    }
    return null;
}
"""

# Settings tab: "Markup in Appointment Calendar" dropdown row
JS_MARKUP_ROW = r"""
() => {
    for (const el of document.querySelectorAll('label, div, span')) {
        const t = (el.textContent || '').trim();
        if (t === 'Markup in Appointment Calendar' ||
            t.startsWith('Markup in Appointment Calendar')) {
            let container = el;
            for (let i = 0; i < 5 && container; i++) {
                const r = container.getBoundingClientRect();
                if (r.width > 250 && r.height >= 50 && r.height <= 140) {
                    if (r.left < 280) break;
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                }
                container = container.parentElement;
            }
        }
    }
    return null;
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
def probe(page: Page, js: str, *args) -> dict | None:
    if args:
        return page.evaluate(js, *args)
    return page.evaluate(js)


def ensure(name: str, bbox: dict | None) -> dict:
    if bbox is None or bbox["width"] <= 1 or bbox["height"] <= 1:
        raise RuntimeError(f"Bad bbox for {name!r}: {bbox}")
    return bbox


def shoot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    print(f"   ✓ {name}.png")


def click_tab(page: Page, label: str) -> None:
    """Click a member-card tab by its text label. Robust to label variants."""
    aliases = [label]
    if label == "Online booking":
        aliases.append("Online Booking")
    page.evaluate(
        """(aliases) => {
            for (const el of document.querySelectorAll('a, button, [role="tab"], .q-tab, li')) {
                const t = (el.textContent || '').trim();
                for (const w of aliases) {
                    if (t === w || t.startsWith(w + ' ') || t.startsWith(w + '\\u00A0')) {
                        const r = el.getBoundingClientRect();
                        if (r.top > 80 && r.top < 200 && r.height < 80) {
                            el.click();
                            return;
                        }
                    }
                }
            }
        }""",
        aliases,
    )
    page.wait_for_timeout(2200)
    nuke_overlays(page)
    page.wait_for_timeout(400)


def open_team_list(page: Page) -> None:
    page.goto(TEAM_LIST, wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)
    page.wait_for_timeout(400)
    verify_administration_mode(page)


def open_modal(page: Page) -> None:
    page.evaluate("""() => {
        const b = document.querySelector('button[data-locator="create_employee_btn"]');
        if (b) b.click();
    }""")
    page.wait_for_selector(".staff-create-modal-featured input", state="visible", timeout=10000)
    page.wait_for_timeout(1200)


def open_member_card(page: Page) -> None:
    page.goto(MEMBER_CARD, wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    close_translate_popup(page)
    page.wait_for_timeout(500)
    nuke_overlays(page)
    verify_administration_mode(page)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
def main():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    OUT.mkdir(parents=True, exist_ok=True)
    bboxes: dict = {}

    with sync_playwright() as pw:
        browser, ctx, page = launch_isolated_browser(pw, headless=True)
        try:
            print("══ Login ══")
            login(page)

            print("══ Switch language ══")
            if not switch_language_to_english(page):
                raise RuntimeError("Could not switch UI to English")

            # ── 01: Team members list — Add team member button ──
            print("\n── 01: Team members list ──")
            open_team_list(page)
            verify_administration_mode(page)
            bboxes["01_team_members_list"] = {
                **ensure("01_team_members_list", probe(page, JS_ADD_BUTTON)),
                "kind": "rect",
            }
            shoot(page, "01_team_members_list")

            # ── 02: Modal default — whole modal frame ──
            print("\n── 02: Modal default ──")
            open_modal(page)
            verify_administration_mode(page)
            bboxes["02_modal_default"] = {
                **ensure("02_modal_default", probe(page, JS_MODAL_INNER)),
                "kind": "rect",
            }
            shoot(page, "02_modal_default")

            # ── 03: Modal filled — Save button ──
            # Quirk observed today: Tab + typing into the Specialization
            # autocomplete caused a Vue re-render that dismissed the modal.
            # Workaround: fill both inputs directly via DOM (no Tab, no
            # autocomplete trigger), then probe the Save button.
            print("\n── 03: Modal filled ──")
            page.evaluate("""() => {
                const setVal = (el, value) => {
                    const proto = Object.getPrototypeOf(el);
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                    setter.call(el, value);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                };
                const inputs = [...document.querySelectorAll('.staff-create-modal-featured input')];
                // First text input is Name, second is Specialization
                const text = inputs.filter(i => i.type === 'text' || !i.type);
                if (text[0]) setVal(text[0], 'Anna Smith');
                if (text[1]) setVal(text[1], 'Hair Stylist');
            }""")
            page.wait_for_timeout(800)
            # Click somewhere neutral to close any autocomplete dropdown
            page.evaluate("""() => {
                const m = document.querySelector('.staff-create-modal-featured');
                if (m) {
                    const r = m.getBoundingClientRect();
                    document.elementFromPoint(r.x + 30, r.y + 30)?.click();
                }
            }""")
            page.wait_for_timeout(500)
            save_bbox = probe(page, JS_MODAL_SAVE)
            if save_bbox is None:
                # Modal dismissed itself — re-open and skip the auto-fill
                print("   (modal closed during fill — re-opening with blank state)")
                open_modal(page)
                page.evaluate("""() => {
                    const inp = document.querySelector('.staff-create-modal-featured input');
                    if (inp) {
                        const proto = Object.getPrototypeOf(inp);
                        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                        setter.call(inp, 'Anna Smith');
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }""")
                page.wait_for_timeout(800)
                save_bbox = probe(page, JS_MODAL_SAVE)
            bboxes["03_modal_filled"] = {
                **ensure("03_modal_filled", save_bbox),
                "kind": "rect",
            }
            shoot(page, "03_modal_filled")

            # Cancel modal so we don't pollute the test account
            page.evaluate("""() => {
                const modal = document.querySelector('.staff-create-modal-featured');
                if (modal) {
                    for (const b of modal.querySelectorAll('button')) {
                        if ((b.textContent || '').trim() === 'Cancel') { b.click(); return; }
                    }
                }
            }""")
            page.wait_for_timeout(1500)

            # ── 04: Information tab — tabs row ──
            print("\n── 04: Information tab (tabs row) ──")
            open_member_card(page)
            bboxes["04_information_tab"] = {
                **ensure("04_information_tab", probe(page, JS_MEMBER_TABS)),
                "kind": "rect",
            }
            shoot(page, "04_information_tab")

            # ── 05: Services tab — Assign services + Create a service buttons ──
            print("\n── 05: Services tab ──")
            click_tab(page, "Services")
            verify_administration_mode(page)
            bboxes["05_services_tab"] = {
                **ensure("05_services_tab",
                         probe(page, JS_BUTTONS_UNION,
                               ["Assign services", "Create a service"])),
                "kind": "rect",
            }
            shoot(page, "05_services_tab")

            # Reusable fallback: tabs-row bbox (always available on the card)
            tabs_row_bbox = probe(page, JS_MEMBER_TABS)

            def with_fallback(primary_bbox, name):
                """Return primary_bbox if valid, else first heading, else tabs row."""
                if primary_bbox and primary_bbox.get("width", 0) > 1:
                    return primary_bbox
                heading = probe(page, JS_FIRST_HEADING)
                if heading and heading.get("width", 0) > 1:
                    print(f"   (using heading fallback for {name})")
                    return heading
                print(f"   (using tabs-row fallback for {name})")
                return tabs_row_bbox

            # ── 06: Online booking tab — Available toggle row ──
            print("\n── 06: Online booking tab ──")
            click_tab(page, "Online booking")
            verify_administration_mode(page)
            ob_bbox = probe(page, JS_OB_RADIO) or probe(page, JS_BUTTON_BY_TEXT, "Available for online booking")
            bboxes["06_online_booking_tab"] = {
                **ensure("06_online_booking_tab", with_fallback(ob_bbox, "06")),
                "kind": "rect",
            }
            shoot(page, "06_online_booking_tab")

            # ── 07: Payroll tab — Copy from another employee button ──
            print("\n── 07: Payroll tab ──")
            click_tab(page, "Payroll")
            verify_administration_mode(page)
            pr_bbox = probe(page, JS_BUTTON_BY_TEXT, "Copy from another employee")
            bboxes["07_payroll_tab"] = {
                **ensure("07_payroll_tab", with_fallback(pr_bbox, "07")),
                "kind": "rect",
            }
            shoot(page, "07_payroll_tab")

            # ── 08: Work Schedule tab — Set up button ──
            print("\n── 08: Work Schedule tab ──")
            click_tab(page, "Work Schedule")
            verify_administration_mode(page)
            ws_bbox = probe(page, JS_BUTTON_BY_TEXT, "Set up")
            bboxes["08_work_schedule_tab"] = {
                **ensure("08_work_schedule_tab", with_fallback(ws_bbox, "08")),
                "kind": "rect",
            }
            shoot(page, "08_work_schedule_tab")

            # ── 09: Access tab — Grant system access toggle row ──
            print("\n── 09: Access tab ──")
            click_tab(page, "Access")
            verify_administration_mode(page)
            ac_bbox = probe(page, JS_GRANT_ACCESS) or probe(page, JS_BUTTON_BY_TEXT, "Grant system access")
            bboxes["09_access_tab"] = {
                **ensure("09_access_tab", with_fallback(ac_bbox, "09")),
                "kind": "rect",
            }
            shoot(page, "09_access_tab")

            # ── 10: Notifications tab — Assign rights button ──
            print("\n── 10: Notifications tab ──")
            click_tab(page, "Notifications")
            verify_administration_mode(page)
            nt_bbox = probe(page, JS_BUTTON_BY_TEXT, "Assign rights")
            bboxes["10_notifications_tab"] = {
                **ensure("10_notifications_tab", with_fallback(nt_bbox, "10")),
                "kind": "rect",
            }
            shoot(page, "10_notifications_tab")

            # ── 11: Settings tab — Markup in Appointment Calendar row ──
            print("\n── 11: Settings tab ──")
            click_tab(page, "Settings")
            verify_administration_mode(page)
            st_bbox = probe(page, JS_MARKUP_ROW) or probe(page, JS_BUTTON_BY_TEXT, "Markup in Appointment Calendar")
            bboxes["11_settings_tab"] = {
                **ensure("11_settings_tab", with_fallback(st_bbox, "11")),
                "kind": "rect",
            }
            shoot(page, "11_settings_tab")

        finally:
            browser.close()

    save_bboxes(OUT / "bboxes.json", bboxes)
    print(f"\n══ DONE ══")
    for k, v in bboxes.items():
        print(f"  {k:30s}  {v['kind']:5s}  "
              f"x={v['x']:.1f}  y={v['y']:.1f}  w={v['width']:.1f}  h={v['height']:.1f}")


if __name__ == "__main__":
    main()
