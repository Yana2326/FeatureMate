"""
Capture all screenshots for the "How to add a team member" article.

Fresh Playwright captures (Rule 4). Each screenshot verified in Administration
mode (Rule 2) with exact bounding boxes saved to bboxes.json (Rule 3).

Outputs:
  output/add-team-member/screenshots/01_team_members_list.png
  output/add-team-member/screenshots/02_modal_default.png
  output/add-team-member/screenshots/03_modal_filled.png
  output/add-team-member/screenshots/04_member_card_information.png
  output/add-team-member/screenshots/bboxes.json
"""

from __future__ import annotations

import os
import json
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
# Use an existing team member card for the post-save demo
MEMBER_CARD = f"{BASE}/settings/staff/{COMPANY_ID}/2745268"

OUT = Path("output/add-team-member/screenshots")


# ═══════════════════════════════════════════════════════════════════════════
# DOM probes — return bounding boxes from the live DOM
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
    const wanted = ['Information', 'Services', 'Online Booking',
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


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
def probe(page: Page, js: str) -> dict | None:
    return page.evaluate(js)


def ensure(name: str, bbox: dict | None) -> dict:
    if bbox is None or bbox.get("width", 0) <= 1 or bbox.get("height", 0) <= 1:
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
    """Click the Add team member button and wait for the modal."""
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

    # Also capture a JSON dump of all visible UI elements for page_analysis.json
    ui_dumps: dict = {}

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

            # Capture all visible text from the toolbar area for analysis
            ui_dumps["team_list_toolbar"] = page.evaluate(r"""() => {
                const result = {buttons: [], filters: [], headings: []};
                for (const b of document.querySelectorAll('button')) {
                    const t = (b.textContent || '').trim();
                    if (t && t.length < 100) {
                        const r = b.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0)
                            result.buttons.push({label: t, x: r.x, y: r.y});
                    }
                }
                for (const s of document.querySelectorAll('select, .q-select')) {
                    const t = (s.textContent || s.value || '').trim();
                    const r = s.getBoundingClientRect();
                    if (r.width > 0) result.filters.push({label: t.slice(0, 80), x: r.x, y: r.y});
                }
                for (const h of document.querySelectorAll('h1, h2, h3, .page-title')) {
                    const t = (h.textContent || '').trim();
                    if (t) result.headings.push(t);
                }
                return result;
            }""")

            # Capture column headers from the team members table
            ui_dumps["team_list_columns"] = page.evaluate(r"""() => {
                const cols = [];
                for (const th of document.querySelectorAll('th, .table-header, [class*="header-cell"]')) {
                    const t = (th.textContent || '').trim();
                    if (t && t.length < 80) cols.push(t);
                }
                return cols;
            }""")

            bboxes["01_team_members_list"] = {
                **ensure("01_team_members_list", probe(page, JS_ADD_BUTTON)),
                "kind": "rect",
            }
            shoot(page, "01_team_members_list")

            # ── 02: Modal default state, highlight whole modal card ──
            print("\n── 02: Modal default ──")
            open_modal(page)
            verify_administration_mode(page)

            # Capture all UI elements inside the modal
            ui_dumps["modal_elements"] = page.evaluate(r"""() => {
                const modal = document.querySelector('.staff-create-modal-featured');
                if (!modal) return {error: "modal not found"};
                const result = {inputs: [], buttons: [], labels: [], radios: [], selects: [], text_blocks: []};
                for (const i of modal.querySelectorAll('input')) {
                    result.inputs.push({
                        type: i.type,
                        placeholder: i.placeholder,
                        name: i.name,
                        value: i.value
                    });
                }
                for (const b of modal.querySelectorAll('button, [role="button"]')) {
                    const t = (b.textContent || '').trim();
                    if (t) result.buttons.push(t);
                }
                for (const l of modal.querySelectorAll('label, .q-field__label, .label')) {
                    const t = (l.textContent || '').trim();
                    if (t) result.labels.push(t);
                }
                for (const r of modal.querySelectorAll('input[type="radio"]')) {
                    const label = r.closest('label')?.textContent?.trim() ||
                                  r.parentElement?.textContent?.trim() || '';
                    result.radios.push({name: r.name, value: r.value, checked: r.checked, label});
                }
                for (const s of modal.querySelectorAll('select, .q-select')) {
                    const opts = [];
                    for (const o of s.querySelectorAll('option')) opts.push(o.textContent.trim());
                    result.selects.push({options: opts, value: s.value});
                }
                // Get all visible text blocks
                const walker = document.createTreeWalker(modal, NodeFilter.SHOW_TEXT, null);
                const texts = new Set();
                while (walker.nextNode()) {
                    const t = walker.currentNode.textContent.trim();
                    if (t && t.length > 2 && t.length < 200) texts.add(t);
                }
                result.text_blocks = [...texts];
                return result;
            }""")

            bboxes["02_modal_default"] = {
                **ensure("02_modal_default", probe(page, JS_MODAL_INNER)),
                "kind": "rect",
            }
            shoot(page, "02_modal_default")

            # ── 03: Modal filled with example values, highlight Save button ──
            print("\n── 03: Modal filled ──")
            page.evaluate("""() => {
                for (const i of document.querySelectorAll('input')) {
                    const ph = (i.placeholder || '').toLowerCase();
                    if (ph.includes('enter name') || ph.includes('name')) {
                        i.focus();
                        return;
                    }
                }
            }""")
            page.keyboard.type("Test Stylist", delay=15)
            page.wait_for_timeout(300)
            page.keyboard.press("Tab")
            page.wait_for_timeout(150)
            page.keyboard.type("Hair Stylist", delay=15)
            page.wait_for_timeout(500)

            verify_administration_mode(page)
            bboxes["03_modal_filled"] = {
                **ensure("03_modal_filled", probe(page, JS_MODAL_SAVE)),
                "kind": "rect",
            }
            shoot(page, "03_modal_filled")

            # Close modal without saving (keep test account clean)
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

            # Capture card UI elements
            ui_dumps["member_card_elements"] = page.evaluate(r"""() => {
                const result = {tabs: [], buttons: [], fields: []};
                for (const el of document.querySelectorAll('a, button, [role="tab"], .q-tab, li')) {
                    const t = (el.textContent || '').trim();
                    const r = el.getBoundingClientRect();
                    if (r.width < 30 || r.height < 18 || r.height > 80) continue;
                    if (r.top < 80 || r.top > 200) continue;
                    if (t && t.length < 40) result.tabs.push(t);
                }
                for (const b of document.querySelectorAll('button')) {
                    const t = (b.textContent || '').trim();
                    const r = b.getBoundingClientRect();
                    if (t && t.length < 60 && r.width > 0 && r.y > 200) result.buttons.push(t);
                }
                for (const i of document.querySelectorAll('input, textarea')) {
                    const label = i.closest('.q-field')?.querySelector('.q-field__label')?.textContent?.trim() || '';
                    result.fields.push({label, type: i.type, placeholder: i.placeholder, value: i.value.slice(0, 50)});
                }
                return result;
            }""")

            bboxes["04_member_card_information"] = {
                **ensure("04_member_card_information", probe(page, JS_MEMBER_TABS)),
                "kind": "rect",
            }
            shoot(page, "04_member_card_information")

        finally:
            browser.close()

    save_bboxes(OUT / "bboxes.json", bboxes)

    # Save UI dumps for page_analysis.json creation
    ui_dump_path = OUT.parent / "ui_dumps.json"
    ui_dump_path.write_text(json.dumps(ui_dumps, indent=2, ensure_ascii=False))

    print(f"\n══ DONE ══")
    for k, v in bboxes.items():
        print(f"  {k}  {v['kind']:5s}  "
              f"x={v['x']:.1f}  y={v['y']:.1f}  w={v['width']:.1f}  h={v['height']:.1f}")


if __name__ == "__main__":
    main()
