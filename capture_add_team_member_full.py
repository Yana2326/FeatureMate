"""
Comprehensive capture for "How to add a team member" article.

Captures:
  01 - Team members list page (with Add team member button highlighted)
  02 - Add team member modal (empty/default state)
  03 - Add team member modal (filled with example data)
  04 - Team member card — Information tab
  05 - Team member card — Services tab
  06 - Team member card — Online Booking tab
  07 - Team member card — Payroll tab
  08 - Team member card — Work Schedule tab
  09 - Team member card — Access tab
  10 - Team member card — Notifications tab
  11 - Team member card — Settings tab

Also dumps all UI elements to ui_dumps.json for page_analysis.json generation.
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
OUT = Path("output/add-team-member/screenshots")


def probe(page: Page, js: str):
    return page.evaluate(js)


def ensure(name: str, bbox) -> dict:
    if bbox is None or bbox.get("width", 0) <= 1 or bbox.get("height", 0) <= 1:
        raise RuntimeError(f"Bad bbox for {name!r}: {bbox}")
    return bbox


def shoot(page: Page, name: str, full_page: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full_page)
    print(f"   ✓ {name}.png")


def open_team_list(page: Page) -> None:
    page.goto(TEAM_LIST, wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    close_translate_popup(page)
    page.wait_for_timeout(500)
    verify_administration_mode(page)


def open_add_modal(page: Page) -> None:
    """Click the Add team member button and wait for the modal."""
    page.evaluate("""() => {
        const b = document.querySelector('button[data-locator="create_employee_btn"]');
        if (b) b.click();
    }""")
    page.wait_for_timeout(2000)
    # Wait for modal input to be visible
    try:
        page.wait_for_selector(".staff-create-modal-featured input", state="visible", timeout=8000)
    except Exception:
        # Fallback: try any modal
        page.wait_for_selector(".yc-modal__container, .q-dialog", state="visible", timeout=5000)
    page.wait_for_timeout(1200)


def dump_all_text(page: Page, context: str = "") -> dict:
    """Extract all visible UI elements from the page."""
    return page.evaluate(r"""() => {
        const result = {
            buttons: [],
            inputs: [],
            labels: [],
            links: [],
            headings: [],
            selects: [],
            radios: [],
            checkboxes: [],
            toggles: [],
            tabs: [],
            text_blocks: []
        };

        for (const b of document.querySelectorAll('button, [role="button"]')) {
            const t = (b.textContent || '').trim();
            const r = b.getBoundingClientRect();
            if (t && t.length < 100 && r.width > 0 && r.height > 0) {
                result.buttons.push({label: t, x: Math.round(r.x), y: Math.round(r.y),
                    w: Math.round(r.width), h: Math.round(r.height),
                    disabled: b.disabled || false});
            }
        }

        for (const i of document.querySelectorAll('input:not([type="hidden"])')) {
            const label = i.closest('.q-field')?.querySelector('.q-field__label')?.textContent?.trim()
                || i.closest('label')?.textContent?.trim()
                || i.getAttribute('aria-label') || '';
            const r = i.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) {
                result.inputs.push({
                    label: label,
                    type: i.type || 'text',
                    placeholder: i.placeholder || '',
                    name: i.name || '',
                    value: (i.value || '').slice(0, 80),
                    required: i.required || false,
                    x: Math.round(r.x), y: Math.round(r.y)
                });
            }
        }

        for (const l of document.querySelectorAll('label, .q-field__label')) {
            const t = (l.textContent || '').trim();
            if (t && t.length < 100) result.labels.push(t);
        }

        for (const a of document.querySelectorAll('a')) {
            const t = (a.textContent || '').trim();
            const r = a.getBoundingClientRect();
            if (t && t.length < 100 && r.width > 0) {
                result.links.push({label: t, href: a.href || ''});
            }
        }

        for (const h of document.querySelectorAll('h1, h2, h3, h4, .page-title')) {
            const t = (h.textContent || '').trim();
            if (t) result.headings.push(t);
        }

        for (const s of document.querySelectorAll('select')) {
            const opts = [...s.querySelectorAll('option')].map(o => o.textContent.trim());
            const label = s.closest('.q-field')?.querySelector('.q-field__label')?.textContent?.trim() || '';
            result.selects.push({label, options: opts, value: s.value});
        }

        for (const r of document.querySelectorAll('input[type="radio"]')) {
            const label = r.closest('label')?.textContent?.trim()
                || r.parentElement?.textContent?.trim() || '';
            result.radios.push({name: r.name, value: r.value, checked: r.checked, label});
        }

        for (const c of document.querySelectorAll('input[type="checkbox"]')) {
            const label = c.closest('label')?.textContent?.trim()
                || c.closest('.q-field')?.querySelector('.q-field__label')?.textContent?.trim() || '';
            result.checkboxes.push({name: c.name, checked: c.checked, label});
        }

        // Quasar toggles
        for (const t of document.querySelectorAll('.q-toggle, [role="switch"]')) {
            const label = t.textContent?.trim() || t.getAttribute('aria-label') || '';
            const isOn = t.classList.contains('q-toggle--active') ||
                         t.getAttribute('aria-checked') === 'true';
            result.toggles.push({label, isOn});
        }

        // Tabs
        for (const el of document.querySelectorAll('a, button, [role="tab"], .q-tab, li')) {
            const t = (el.textContent || '').trim();
            const r = el.getBoundingClientRect();
            if (r.width < 30 || r.height < 15 || r.height > 80) continue;
            if (r.top < 60 || r.top > 220) continue;
            if (t && t.length < 50) result.tabs.push(t);
        }

        return result;
    }""")


def dump_modal_content(page: Page) -> dict:
    """Extract all UI elements from the Add team member modal."""
    return page.evaluate(r"""() => {
        const modal = document.querySelector('.staff-create-modal-featured')
            || document.querySelector('.yc-modal__container')
            || document.querySelector('.q-dialog');
        if (!modal) return {error: "No modal found"};

        const result = {
            title: '',
            inputs: [],
            buttons: [],
            labels: [],
            radios: [],
            selects: [],
            checkboxes: [],
            toggles: [],
            text_blocks: [],
            all_visible_text: []
        };

        // Title
        const titleEl = modal.querySelector('h2, h3, .modal-title, .q-card__section--vert h2');
        if (titleEl) result.title = titleEl.textContent.trim();

        // Inputs
        for (const i of modal.querySelectorAll('input:not([type="hidden"])')) {
            const field = i.closest('.q-field, .form-group, .field');
            const label = field?.querySelector('.q-field__label, label')?.textContent?.trim()
                || i.getAttribute('aria-label') || '';
            result.inputs.push({
                label,
                type: i.type || 'text',
                placeholder: i.placeholder || '',
                name: i.name || '',
                value: (i.value || '').slice(0, 80),
                required: i.required
            });
        }

        // Textareas
        for (const t of modal.querySelectorAll('textarea')) {
            const field = t.closest('.q-field, .form-group');
            const label = field?.querySelector('.q-field__label, label')?.textContent?.trim() || '';
            result.inputs.push({label, type: 'textarea', placeholder: t.placeholder || ''});
        }

        // Buttons
        for (const b of modal.querySelectorAll('button, [role="button"]')) {
            const t = (b.textContent || '').trim();
            if (t && t.length < 60) result.buttons.push({label: t, disabled: b.disabled || false});
        }

        // Labels
        for (const l of modal.querySelectorAll('label, .q-field__label, .label, .field-label')) {
            const t = (l.textContent || '').trim();
            if (t && t.length < 100) result.labels.push(t);
        }

        // Radio buttons
        for (const r of modal.querySelectorAll('input[type="radio"]')) {
            const label = r.closest('label')?.textContent?.trim()
                || r.parentElement?.textContent?.trim() || '';
            result.radios.push({name: r.name, value: r.value, checked: r.checked, label});
        }

        // Selects
        for (const s of modal.querySelectorAll('select, .q-select')) {
            const opts = [...s.querySelectorAll('option')].map(o => o.textContent.trim());
            const field = s.closest('.q-field');
            const label = field?.querySelector('.q-field__label')?.textContent?.trim() || '';
            result.selects.push({label, options: opts});
        }

        // Checkboxes
        for (const c of modal.querySelectorAll('input[type="checkbox"]')) {
            const label = c.closest('label')?.textContent?.trim() || '';
            result.checkboxes.push({label, checked: c.checked});
        }

        // Toggles
        for (const t of modal.querySelectorAll('.q-toggle, [role="switch"]')) {
            const label = t.textContent?.trim() || '';
            const isOn = t.classList.contains('q-toggle--active') ||
                         t.getAttribute('aria-checked') === 'true';
            result.toggles.push({label, isOn});
        }

        // All visible text
        const walker = document.createTreeWalker(modal, NodeFilter.SHOW_TEXT, null);
        const texts = new Set();
        while (walker.nextNode()) {
            const t = walker.currentNode.textContent.trim();
            if (t && t.length > 1 && t.length < 300) texts.add(t);
        }
        result.all_visible_text = [...texts];

        return result;
    }""")


def click_tab(page: Page, tab_name: str) -> bool:
    """Click a tab by its label text. Returns True if successful."""
    result = page.evaluate(f"""() => {{
        const wanted = "{tab_name}";
        for (const el of document.querySelectorAll('a, button, [role="tab"], .q-tab, li, .q-tabs__content > *')) {{
            const t = (el.textContent || '').trim();
            if (t === wanted || t.startsWith(wanted + ' ') || t.startsWith(wanted + '\\u00A0')) {{
                const r = el.getBoundingClientRect();
                if (r.width > 20 && r.height > 10 && r.top < 250 && r.top > 50) {{
                    el.click();
                    return true;
                }}
            }}
        }}
        return false;
    }}""")
    if result:
        page.wait_for_timeout(2000)
        nuke_overlays(page)
    return result


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
    ui_dumps: dict = {}

    with sync_playwright() as pw:
        browser, ctx, page = launch_isolated_browser(pw, headless=True)
        try:
            # ═══════════════════════════════════════════════════════════════
            # Login & language
            # ═══════════════════════════════════════════════════════════════
            print("══ Login ══")
            login(page)
            print("══ Switch language ══")
            if not switch_language_to_english(page):
                raise RuntimeError("Could not switch UI to English")
            print("   Language: English ✓")

            # ═══════════════════════════════════════════════════════════════
            # 01: Team members list page
            # ═══════════════════════════════════════════════════════════════
            print("\n── 01: Team members list ──")
            open_team_list(page)
            ui_dumps["01_team_list"] = dump_all_text(page)

            # Get the Add button bbox for highlighting
            add_btn_bbox = probe(page, r"""() => {
                const b = document.querySelector('button[data-locator="create_employee_btn"]');
                if (!b) return null;
                const r = b.getBoundingClientRect();
                return {x: r.x, y: r.y, width: r.width, height: r.height};
            }""")
            if add_btn_bbox:
                bboxes["01_team_members_list"] = {**ensure("01_add_btn", add_btn_bbox), "kind": "rect"}
            shoot(page, "01_team_members_list")

            # Also capture full page to see all team members
            shoot(page, "01_team_members_list_full", full_page=True)

            # ═══════════════════════════════════════════════════════════════
            # 02: Add team member modal — empty/default state
            # ═══════════════════════════════════════════════════════════════
            print("\n── 02: Add modal (default) ──")
            open_add_modal(page)
            verify_administration_mode(page)
            ui_dumps["02_modal_default"] = dump_modal_content(page)

            modal_bbox = probe(page, r"""() => {
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
                    if (r.width < 300 || r.width > 800) continue;
                    if (r.height < 200) continue;
                    if (!best || r.height > best.h) {
                        best = {x: r.x, y: r.y, w: r.width, h: r.height};
                    }
                }
                if (!best) return null;
                return {x: best.x, y: best.y, width: best.w, height: best.h};
            }""")
            if modal_bbox:
                bboxes["02_modal_default"] = {**ensure("02_modal", modal_bbox), "kind": "rect"}
            shoot(page, "02_modal_default")

            # ═══════════════════════════════════════════════════════════════
            # 03: Add team member modal — filled with example data
            # ═══════════════════════════════════════════════════════════════
            print("\n── 03: Add modal (filled) ──")
            # Focus the name field and type
            page.evaluate("""() => {
                const modal = document.querySelector('.staff-create-modal-featured')
                    || document.querySelector('.yc-modal__container');
                if (!modal) return;
                for (const i of modal.querySelectorAll('input')) {
                    const ph = (i.placeholder || '').toLowerCase();
                    const label = i.closest('.q-field')?.querySelector('.q-field__label')?.textContent?.toLowerCase() || '';
                    if (ph.includes('name') || label.includes('name')) {
                        i.focus();
                        return;
                    }
                }
                // Fallback: focus the first visible text input
                const first = modal.querySelector('input[type="text"], input:not([type])');
                if (first) first.focus();
            }""")
            page.keyboard.type("Anna Smith", delay=20)
            page.wait_for_timeout(400)

            # Tab to next field (specialization/position)
            page.keyboard.press("Tab")
            page.wait_for_timeout(300)
            page.keyboard.type("Hair Stylist", delay=20)
            page.wait_for_timeout(500)

            verify_administration_mode(page)
            ui_dumps["03_modal_filled"] = dump_modal_content(page)

            save_btn_bbox = probe(page, r"""() => {
                const modal = document.querySelector('.staff-create-modal-featured')
                    || document.querySelector('.yc-modal__container');
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
            }""")
            if save_btn_bbox:
                bboxes["03_modal_filled"] = {**ensure("03_save", save_btn_bbox), "kind": "rect"}
            shoot(page, "03_modal_filled")

            # Close the modal without saving
            page.evaluate("""() => {
                const modal = document.querySelector('.staff-create-modal-featured')
                    || document.querySelector('.yc-modal__container');
                if (modal) {
                    const btns = modal.querySelectorAll('button');
                    for (const b of btns) {
                        if ((b.textContent || '').trim() === 'Cancel') { b.click(); return; }
                    }
                }
            }""")
            page.wait_for_timeout(1500)

            # ═══════════════════════════════════════════════════════════════
            # Find an existing team member to explore the card
            # ═══════════════════════════════════════════════════════════════
            print("\n── Finding existing team member ──")
            # Navigate back to team list
            open_team_list(page)

            # Get the first team member link
            member_url = page.evaluate(f"""() => {{
                const links = document.querySelectorAll('a[href*="/settings/staff/{COMPANY_ID}/"]');
                for (const a of links) {{
                    const r = a.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) return a.href;
                }}
                // Fallback: look for any staff link
                const allLinks = document.querySelectorAll('a');
                for (const a of allLinks) {{
                    if (a.href && a.href.includes('/staff/') && a.href.includes('{COMPANY_ID}')) {{
                        return a.href;
                    }}
                }}
                return null;
            }}""")

            if not member_url:
                # Try clicking on the first row in the table
                print("   No direct link found, trying table row click...")
                member_url = f"{BASE}/settings/staff/{COMPANY_ID}/2745268"  # Known ID from old script

            print(f"   Using member: {member_url}")

            # ═══════════════════════════════════════════════════════════════
            # 04: Team member card — Information tab
            # ═══════════════════════════════════════════════════════════════
            print("\n── 04: Team member card — Information ──")
            page.goto(member_url, wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page)
            close_translate_popup(page)
            nuke_overlays(page)
            verify_administration_mode(page)

            ui_dumps["04_information_tab"] = dump_all_text(page)

            # Get tabs bbox
            tabs_bbox = probe(page, r"""() => {
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
                    if (r.top < 60 || r.top > 220) continue;
                    found.push(r);
                }
                if (!found.length) return null;
                let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
                for (const r of found) {
                    if (r.left < x0) x0 = r.left;
                    if (r.top < y0) y0 = r.top;
                    if (r.right > x1) x1 = r.right;
                    if (r.bottom > y1) y1 = r.bottom;
                }
                return {x: x0, y: y0, width: x1 - x0, height: y1 - y0};
            }""")
            if tabs_bbox:
                bboxes["04_information_tabs"] = {**ensure("04_tabs", tabs_bbox), "kind": "rect"}
            shoot(page, "04_information_tab")
            shoot(page, "04_information_tab_full", full_page=True)

            # ═══════════════════════════════════════════════════════════════
            # 05: Services tab
            # ═══════════════════════════════════════════════════════════════
            print("\n── 05: Services tab ──")
            if click_tab(page, "Services"):
                verify_administration_mode(page)
                ui_dumps["05_services_tab"] = dump_all_text(page)
                shoot(page, "05_services_tab")
                shoot(page, "05_services_tab_full", full_page=True)
            else:
                print("   ⚠ Could not click Services tab")

            # ═══════════════════════════════════════════════════════════════
            # 06: Online Booking tab
            # ═══════════════════════════════════════════════════════════════
            print("\n── 06: Online Booking tab ──")
            if click_tab(page, "Online Booking"):
                verify_administration_mode(page)
                ui_dumps["06_online_booking_tab"] = dump_all_text(page)
                shoot(page, "06_online_booking_tab")
                shoot(page, "06_online_booking_tab_full", full_page=True)
            else:
                print("   ⚠ Could not click Online Booking tab")

            # ═══════════════════════════════════════════════════════════════
            # 07: Payroll tab
            # ═══════════════════════════════════════════════════════════════
            print("\n── 07: Payroll tab ──")
            if click_tab(page, "Payroll"):
                verify_administration_mode(page)
                ui_dumps["07_payroll_tab"] = dump_all_text(page)
                shoot(page, "07_payroll_tab")
                shoot(page, "07_payroll_tab_full", full_page=True)
            else:
                print("   ⚠ Could not click Payroll tab")

            # ═══════════════════════════════════════════════════════════════
            # 08: Work Schedule tab
            # ═══════════════════════════════════════════════════════════════
            print("\n── 08: Work Schedule tab ──")
            if click_tab(page, "Work Schedule"):
                verify_administration_mode(page)
                ui_dumps["08_work_schedule_tab"] = dump_all_text(page)
                shoot(page, "08_work_schedule_tab")
                shoot(page, "08_work_schedule_tab_full", full_page=True)
            else:
                print("   ⚠ Could not click Work Schedule tab")

            # ═══════════════════════════════════════════════════════════════
            # 09: Access tab
            # ═══════════════════════════════════════════════════════════════
            print("\n── 09: Access tab ──")
            if click_tab(page, "Access"):
                verify_administration_mode(page)
                ui_dumps["09_access_tab"] = dump_all_text(page)
                shoot(page, "09_access_tab")
                shoot(page, "09_access_tab_full", full_page=True)
            else:
                print("   ⚠ Could not click Access tab")

            # ═══════════════════════════════════════════════════════════════
            # 10: Notifications tab
            # ═══════════════════════════════════════════════════════════════
            print("\n── 10: Notifications tab ──")
            if click_tab(page, "Notifications"):
                verify_administration_mode(page)
                ui_dumps["10_notifications_tab"] = dump_all_text(page)
                shoot(page, "10_notifications_tab")
            else:
                print("   ⚠ Could not click Notifications tab")

            # ═══════════════════════════════════════════════════════════════
            # 11: Settings tab
            # ═══════════════════════════════════════════════════════════════
            print("\n── 11: Settings tab ──")
            if click_tab(page, "Settings"):
                verify_administration_mode(page)
                ui_dumps["11_settings_tab"] = dump_all_text(page)
                shoot(page, "11_settings_tab")
                shoot(page, "11_settings_tab_full", full_page=True)
            else:
                print("   ⚠ Could not click Settings tab")

        finally:
            browser.close()

    # Save outputs
    save_bboxes(OUT / "bboxes.json", bboxes)

    ui_dump_path = OUT.parent / "ui_dumps.json"
    ui_dump_path.write_text(json.dumps(ui_dumps, indent=2, ensure_ascii=False))
    print(f"\n══ UI dumps saved to {ui_dump_path} ══")

    print(f"\n══ DONE ══")
    print(f"  Screenshots: {OUT}")
    for k, v in bboxes.items():
        print(f"  {k}  {v['kind']:5s}  "
              f"x={v['x']:.1f}  y={v['y']:.1f}  w={v['width']:.1f}  h={v['height']:.1f}")


if __name__ == "__main__":
    main()
