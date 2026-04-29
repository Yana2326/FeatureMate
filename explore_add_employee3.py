"""
Explore deeper:
  - Dump the modal DOM contents fully
  - Try selecting the alternate radio options
  - Fill the form, save it, and see what page comes next
  - Capture every distinct state cleanly
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login,
    nuke_overlays, close_translate_popup,
    verify_administration_mode,
)


TEAM_LIST = f"{BASE}/settings/filial_staff/{COMPANY_ID}/"
EXPLORE = Path("output/add-employee/screenshots/_explore")


def screenshot(page, name: str) -> None:
    EXPLORE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EXPLORE / f"{name}.png"), full_page=False)
    print(f"   ✓ {name}.png")


def dump_modal(page, label: str) -> None:
    """Dump modal text + visible inputs/buttons/radios."""
    info = page.evaluate("""() => {
        const modal = document.querySelector('.staff-create-modal-featured, .q-dialog .q-card');
        if (!modal) return null;
        const r = modal.getBoundingClientRect();
        const inner = modal.querySelector('.q-card, .q-dialog__inner > *') || modal;
        const irect = inner.getBoundingClientRect();
        const out = {
            modal_bbox: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
            inner_bbox: {x: Math.round(irect.x), y: Math.round(irect.y), w: Math.round(irect.width), h: Math.round(irect.height)},
            text: (modal.innerText || '').slice(0, 1500),
            buttons: [],
            inputs: [],
            radios: [],
            checkboxes: [],
        };
        for (const b of modal.querySelectorAll('button, a, [role="button"]')) {
            const t = (b.textContent || '').trim();
            const rb = b.getBoundingClientRect();
            if (t && rb.width > 5 && rb.height > 5) {
                out.buttons.push({text: t.slice(0, 60), x: Math.round(rb.x), y: Math.round(rb.y),
                                  w: Math.round(rb.width), h: Math.round(rb.height),
                                  attr: b.getAttribute('data-locator') || ''});
            }
        }
        for (const i of modal.querySelectorAll('input, select, textarea')) {
            const ri = i.getBoundingClientRect();
            if (ri.width < 5) continue;
            let label = i.getAttribute('placeholder') || i.getAttribute('aria-label') || '';
            if (!label) {
                let p = i.parentElement;
                for (let k = 0; k < 4 && p; k++) {
                    const lab = p.querySelector('label');
                    if (lab && lab.textContent.trim()) { label = lab.textContent.trim(); break; }
                    p = p.parentElement;
                }
            }
            out.inputs.push({tag: i.tagName, type: i.type || '', name: i.name || '',
                             label: label.slice(0, 60), x: Math.round(ri.x), y: Math.round(ri.y),
                             w: Math.round(ri.width), h: Math.round(ri.height)});
        }
        for (const r of modal.querySelectorAll('[role="radio"], .q-radio')) {
            const rr = r.getBoundingClientRect();
            const lab = r.closest('label') || r.parentElement;
            const t = (lab?.textContent || r.textContent || '').trim();
            const ariaChecked = r.getAttribute('aria-checked') || '';
            const cls = r.className || '';
            const truthy = (cls.includes('q-radio--truthy') || cls.includes('truthy') || ariaChecked === 'true');
            out.radios.push({text: t.slice(0, 80), checked: truthy,
                             x: Math.round(rr.x), y: Math.round(rr.y), w: Math.round(rr.width)});
        }
        return out;
    }""")
    if info:
        print(f"\n── MODAL {label} ──")
        print(f"Modal bbox: {info['modal_bbox']}")
        print(f"Inner bbox: {info['inner_bbox']}")
        print(f"Text: {info['text']!r}")
        print(f"Buttons: {info['buttons']}")
        print(f"Inputs: {info['inputs']}")
        print(f"Radios: {info['radios']}")
        EXPLORE.mkdir(parents=True, exist_ok=True)
        (EXPLORE / f"{label}.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        print("(no modal found)")


def main():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    with sync_playwright() as pw:
        browser, ctx, page = launch_isolated_browser(pw, headless=True)
        try:
            print("══ Login ══")
            login(page)

            print("══ Open Team list ══")
            page.goto(TEAM_LIST, wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page)
            close_translate_popup(page)
            verify_administration_mode(page)
            screenshot(page, "20_team_list_clean")

            print("\n══ Click Add team member ══")
            page.locator("button:has-text('Add team member')").first.click()
            page.wait_for_timeout(2500)
            close_translate_popup(page)
            screenshot(page, "21_modal_default")
            dump_modal(page, "21_modal_default")

            print("\n══ Click 'Non-billable member' radio ══")
            try:
                # Click the second main radio
                page.evaluate("""() => {
                    const radios = [...document.querySelectorAll('.q-radio, [role="radio"]')];
                    for (const r of radios) {
                        const lab = r.closest('label') || r.parentElement;
                        const t = (lab?.textContent || '').trim();
                        if (t.startsWith('Non-billable member')) { r.click(); return; }
                    }
                }""")
                page.wait_for_timeout(800)
                screenshot(page, "22_modal_nonbillable")
                dump_modal(page, "22_modal_nonbillable")
            except Exception as e:
                print(f"   ! {e}")

            print("\n══ Switch back to Billable, fill name + specialization ══")
            page.evaluate("""() => {
                const radios = [...document.querySelectorAll('.q-radio, [role="radio"]')];
                for (const r of radios) {
                    const lab = r.closest('label') || r.parentElement;
                    const t = (lab?.textContent || '').trim();
                    if (t.startsWith('Billable member')) { r.click(); return; }
                }
            }""")
            page.wait_for_timeout(500)
            # Find the name input (Enter name placeholder)
            page.evaluate("""() => {
                const inputs = [...document.querySelectorAll('input')];
                for (const i of inputs) {
                    if ((i.placeholder || '').toLowerCase().includes('enter name') ||
                        (i.getAttribute('aria-label') || '').toLowerCase() === 'name') {
                        i.focus();
                        i.value = '';
                        return;
                    }
                }
            }""")
            page.keyboard.type("Test Stylist", delay=20)
            page.wait_for_timeout(300)
            # Specialization
            page.evaluate("""() => {
                const inputs = [...document.querySelectorAll('input')];
                let nameSeen = false;
                for (const i of inputs) {
                    const r = i.getBoundingClientRect();
                    if (r.width < 5) continue;
                    const ph = (i.placeholder || '').toLowerCase();
                    if (ph.includes('enter name')) { nameSeen = true; continue; }
                    if (nameSeen && r.top > 0 && i !== document.activeElement) {
                        i.focus();
                        return;
                    }
                }
            }""")
            page.keyboard.type("Hair Stylist", delay=20)
            page.wait_for_timeout(500)
            screenshot(page, "23_modal_filled")
            dump_modal(page, "23_modal_filled")

            print("\n══ Click Save ══")
            print(f"URL before save: {page.url}")
            page.locator("button:has-text('Save')").first.click()
            page.wait_for_timeout(5000)
            close_translate_popup(page)
            print(f"URL after save: {page.url}")
            screenshot(page, "24_after_save")
            # Dump page-level state
            after = page.evaluate("""() => {
                const out = {h: [], tabs: [], buttons: []};
                for (const h of document.querySelectorAll('h1,h2,h3,h4')) {
                    const t = (h.textContent || '').trim();
                    if (t) {
                        const r = h.getBoundingClientRect();
                        if (r.width > 0) out.h.push({tag: h.tagName, text: t.slice(0, 80), y: Math.round(r.y)});
                    }
                }
                for (const t of document.querySelectorAll('[role="tab"], .q-tab, .yc-tab, .nav-tabs__item')) {
                    const txt = (t.textContent || '').trim();
                    const r = t.getBoundingClientRect();
                    if (txt && r.width > 5 && r.height > 5) {
                        out.tabs.push({text: txt, x: Math.round(r.x), y: Math.round(r.y)});
                    }
                }
                for (const b of document.querySelectorAll('button, a')) {
                    const t = (b.textContent || '').trim();
                    const r = b.getBoundingClientRect();
                    if (t && t.length < 50 && r.top > 50 && r.top < 200 && r.width > 10 && r.height > 10) {
                        out.buttons.push({text: t, x: Math.round(r.x), y: Math.round(r.y)});
                    }
                }
                return out;
            }""")
            print("After save:")
            print(json.dumps(after, indent=2, ensure_ascii=False))

        finally:
            browser.close()


if __name__ == "__main__":
    main()
