"""
Capture all screenshots for the "How to add a team member" article.

Five clean screenshots, each verified in Administration mode (Rule 2),
each with an exact bounding box from Playwright (Rule 3) saved to
output/add-employee/screenshots/bboxes.json so annotate_add_employee.py
draws perfectly symmetric red overlays.

Outputs:
  output/add-employee/screenshots/01_team_members_list.png
  output/add-employee/screenshots/02_modal_default.png
  output/add-employee/screenshots/03_modal_filled.png
  output/add-employee/screenshots/04_member_card_information.png
  output/add-employee/screenshots/05_member_card_tabs.png
  output/add-employee/screenshots/bboxes.json
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


TEAM_LIST = f"{BASE}/settings/filial_staff/{COMPANY_ID}/"
# Lili's team-member settings page (one of the existing non-chain members) —
# captured to demonstrate what users land on after Save.
MEMBER_CARD = f"{BASE}/settings/staff/{COMPANY_ID}/2745268"

OUT = Path("output/add-employee/screenshots")


# ═══════════════════════════════════════════════════════════════════════════
# DOM probes
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
    // The inner card is `.yc-modal__container` (Vue component class). Try
    // both as a child of the staff-create dialog and as a top-level element.
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
        // Centered inner card: width ~ 380–500 px, height ~ 500–800 px,
        // not full viewport, not zero-sized.
        if (r.width < 320 || r.width > 700) continue;
        if (r.height < 300) continue;
        if (r.left < 100 || r.right > 1340) continue;     // skip backdrop
        if (!best || r.height > best.h) {
            best = {x: r.x, y: r.y, w: r.width, h: r.height};
        }
    }
    if (!best) return null;
    return {x: best.x, y: best.y, width: best.w, height: best.h};
}
"""

JS_MODAL_NAME_FIELD = r"""
() => {
    // Find the Name <input> by its placeholder, return its bbox.
    for (const i of document.querySelectorAll('input')) {
        const ph = (i.placeholder || '').toLowerCase();
        if (ph.includes('enter name')) {
            const r = i.getBoundingClientRect();
            if (r.width > 5 && r.height > 5)
                return {x: r.x, y: r.y, width: r.width, height: r.height};
        }
    }
    return null;
}
"""

JS_MODAL_SAVE = r"""
() => {
    // Within the modal, find the visible Save button (the modal one,
    // not the legacy invisible Save button on the page).
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
    // Union the bbox of the tab row at the top of the team-member card:
    // Information / Services / Online Booking / Payroll / Work Schedule /
    // Access / Notifications / Settings.
    const wanted = ['Information', 'Services', 'Online Booking',
                    'Payroll', 'Work Schedule', 'Access',
                    'Notifications', 'Settings'];
    const found = [];
    for (const el of document.querySelectorAll('a, button, [role="tab"], .q-tab, li')) {
        const t = (el.textContent || '').trim();
        // Tab labels include numeric counters (e.g. "Services 29") so use startsWith.
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


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
def probe(page: Page, js: str) -> dict | None:
    return page.evaluate(js)


def ensure(name: str, bbox: dict | None) -> dict:
    if bbox is None or bbox["width"] <= 1 or bbox["height"] <= 1:
        raise RuntimeError(f"Bad bbox for {name!r}: {bbox}")
    return bbox


def shoot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    print(f"   ✓ {name}.png")


def open_team_list(page: Page) -> None:
    page.goto(TEAM_LIST, wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)
    page.wait_for_timeout(400)
    verify_administration_mode(page)


def open_modal(page: Page) -> None:
    """Click the Add team member button and wait for the modal to render.

    Important: do NOT press Escape after the modal opens — Quasar dismisses
    the dialog on Escape, so close_translate_popup() (and the Escape key in
    nuke_overlays()) must run before this function, never after.
    """
    page.evaluate("""() => {
        const b = document.querySelector('button[data-locator="create_employee_btn"]');
        if (b) b.click();
    }""")
    page.wait_for_selector(".staff-create-modal-featured input", state="visible", timeout=10000)
    page.wait_for_timeout(1200)


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

            # ── 01: Team members list, highlight Add team member button ──
            print("\n── 01: Team members list ──")
            open_team_list(page)
            verify_administration_mode(page)
            bboxes["01_team_members_list"] = {
                **ensure("01_team_members_list", probe(page, JS_ADD_BUTTON)),
                "kind": "rect",
            }
            shoot(page, "01_team_members_list")

            # ── 02: Modal default state, highlight whole modal card ──
            print("\n── 02: Modal default ──")
            open_modal(page)
            verify_administration_mode(page)

            bboxes["02_modal_default"] = {
                **ensure("02_modal_default", probe(page, JS_MODAL_INNER)),
                "kind": "rect",
            }
            shoot(page, "02_modal_default")

            # ── 03: Modal filled with example values, highlight Save button ──
            print("\n── 03: Modal filled ──")
            # Fill Name
            page.evaluate("""() => {
                for (const i of document.querySelectorAll('input')) {
                    const ph = (i.placeholder || '').toLowerCase();
                    if (ph.includes('enter name')) {
                        i.focus();
                        return;
                    }
                }
            }""")
            page.keyboard.type("Test Stylist", delay=15)
            page.wait_for_timeout(300)
            # Tab to next field (Specialization) and type
            page.keyboard.press("Tab")
            page.wait_for_timeout(150)
            page.keyboard.type("Hair Stylist", delay=15)
            page.wait_for_timeout(500)
            # NB: never call close_translate_popup() while a Quasar modal is
            # open — it presses Escape, which dismisses the modal.
            verify_administration_mode(page)
            # The Save button sits right next to the Cancel button — a 120 px
            # arrow tail would overlap Cancel, so we highlight Save with a
            # tight rectangle instead.
            bboxes["03_modal_filled"] = {
                **ensure("03_modal_filled", probe(page, JS_MODAL_SAVE)),
                "kind": "rect",
            }
            shoot(page, "03_modal_filled")

            # Close modal (don't actually save — keep the test account clean)
            page.evaluate("""() => {
                const modal = document.querySelector('.staff-create-modal-featured');
                if (modal) {
                    const btns = modal.querySelectorAll('button');
                    for (const b of btns) {
                        if ((b.textContent || '').trim() === 'Cancel') { b.click(); return; }
                    }
                }
            }""")
            page.wait_for_timeout(1500)

            # ── 04: Team member card — Information tab, highlight tab row ──
            print("\n── 04: Team member card (tabs) ──")
            page.goto(MEMBER_CARD, wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page)
            close_translate_popup(page)
            page.wait_for_timeout(500)
            nuke_overlays(page)
            verify_administration_mode(page)
            bboxes["04_member_card_information"] = {
                **ensure("04_member_card_information", probe(page, JS_MEMBER_TABS)),
                "kind": "rect",
            }
            shoot(page, "04_member_card_information")

        finally:
            browser.close()

    save_bboxes(OUT / "bboxes.json", bboxes)
    print(f"\n══ DONE ══")
    for k, v in bboxes.items():
        print(f"  {k}  {v['kind']:5s}  "
              f"x={v['x']:.1f}  y={v['y']:.1f}  w={v['width']:.1f}  h={v['height']:.1f}")


if __name__ == "__main__":
    main()
