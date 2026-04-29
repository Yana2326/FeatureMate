"""Quick supplemental capture: Online booking tab + expanded Additional information."""

from __future__ import annotations
import os, json
from pathlib import Path
from playwright.sync_api import sync_playwright

from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    nuke_overlays, close_translate_popup, verify_administration_mode,
)

OUT = Path("output/add-team-member/screenshots")

def main():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    OUT.mkdir(parents=True, exist_ok=True)
    ui_dumps = {}

    with sync_playwright() as pw:
        browser, ctx, page = launch_isolated_browser(pw, headless=True)
        try:
            print("══ Login ══")
            login(page)
            print("══ Switch language ══")
            if not switch_language_to_english(page):
                raise RuntimeError("Could not switch UI to English")

            member_url = f"{BASE}/settings/staff/{COMPANY_ID}/2975117"

            # ── Online booking tab ──
            print("\n── Online booking tab ──")
            page.goto(member_url, wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page)
            close_translate_popup(page)
            nuke_overlays(page)

            # Click "Online booking" tab (lowercase b)
            clicked = page.evaluate("""() => {
                for (const el of document.querySelectorAll('a, button, [role="tab"], .q-tab, li, .q-tabs__content > *')) {
                    const t = (el.textContent || '').trim();
                    if (t === 'Online booking' || t.startsWith('Online booking')) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 20 && r.height > 10 && r.top < 250 && r.top > 50) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            if clicked:
                page.wait_for_timeout(2500)
                nuke_overlays(page)
                verify_administration_mode(page)
                ui_dumps["06_online_booking_tab"] = page.evaluate(r"""() => {
                    const result = {buttons: [], inputs: [], labels: [], headings: [],
                                    toggles: [], checkboxes: [], text_blocks: []};
                    for (const b of document.querySelectorAll('button, [role="button"]')) {
                        const t = (b.textContent || '').trim();
                        const r = b.getBoundingClientRect();
                        if (t && t.length < 100 && r.width > 0 && r.height > 0 && r.y > 80)
                            result.buttons.push({label: t, x: Math.round(r.x), y: Math.round(r.y)});
                    }
                    for (const h of document.querySelectorAll('h1, h2, h3, h4, .page-title'))
                        if (h.textContent.trim()) result.headings.push(h.textContent.trim());
                    for (const t of document.querySelectorAll('.q-toggle, [role="switch"]')) {
                        const label = t.textContent?.trim() || t.getAttribute('aria-label') || '';
                        const isOn = t.classList.contains('q-toggle--active') ||
                                     t.getAttribute('aria-checked') === 'true';
                        result.toggles.push({label, isOn});
                    }
                    for (const c of document.querySelectorAll('input[type="checkbox"]')) {
                        const label = c.closest('label')?.textContent?.trim() ||
                            c.closest('.q-field')?.querySelector('.q-field__label')?.textContent?.trim() || '';
                        result.checkboxes.push({label, checked: c.checked});
                    }
                    // All visible text in main content area
                    const main = document.querySelector('.q-page-container') || document.body;
                    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, null);
                    const texts = new Set();
                    while (walker.nextNode()) {
                        const t = walker.currentNode.textContent.trim();
                        if (t && t.length > 2 && t.length < 300) texts.add(t);
                    }
                    result.text_blocks = [...texts].slice(0, 60);
                    return result;
                }""")
                page.screenshot(path=str(OUT / "06_online_booking_tab.png"), full_page=False)
                print("   ✓ 06_online_booking_tab.png")
                page.screenshot(path=str(OUT / "06_online_booking_tab_full.png"), full_page=True)
                print("   ✓ 06_online_booking_tab_full.png")
            else:
                print("   ⚠ Could not click Online booking tab")

            # ── Information tab with Additional information expanded ──
            print("\n── Information tab (expanded) ──")
            page.goto(member_url, wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page)
            close_translate_popup(page)
            nuke_overlays(page)
            verify_administration_mode(page)

            # Click "Additional information" to expand it
            expanded = page.evaluate("""() => {
                for (const el of document.querySelectorAll('*')) {
                    const t = (el.textContent || '').trim();
                    if (t === 'Additional information' || t === 'Additional information ▾' ||
                        t.startsWith('Additional information')) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 100 && r.height > 10 && r.height < 60 && r.y > 150) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            if expanded:
                page.wait_for_timeout(1500)
                verify_administration_mode(page)
                # Capture all fields in expanded state
                ui_dumps["04b_information_expanded"] = page.evaluate(r"""() => {
                    const result = {inputs: [], labels: [], selects: []};
                    for (const i of document.querySelectorAll('input:not([type="hidden"])')) {
                        const field = i.closest('.q-field, .form-group');
                        const label = field?.querySelector('.q-field__label, label')?.textContent?.trim()
                            || i.getAttribute('aria-label') || '';
                        const r = i.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0 && r.y > 80)
                            result.inputs.push({
                                label, type: i.type || 'text',
                                placeholder: i.placeholder || '',
                                value: (i.value || '').slice(0, 80),
                                x: Math.round(r.x), y: Math.round(r.y)
                            });
                    }
                    for (const l of document.querySelectorAll('label, .q-field__label'))
                        if (l.textContent.trim()) result.labels.push(l.textContent.trim());
                    for (const s of document.querySelectorAll('select')) {
                        const opts = [...s.querySelectorAll('option')].map(o => o.textContent.trim());
                        const field = s.closest('.q-field');
                        const label = field?.querySelector('.q-field__label')?.textContent?.trim() || '';
                        result.selects.push({label, options: opts, value: s.value});
                    }
                    return result;
                }""")
                page.screenshot(path=str(OUT / "04b_information_expanded.png"), full_page=False)
                print("   ✓ 04b_information_expanded.png")
                page.screenshot(path=str(OUT / "04b_information_expanded_full.png"), full_page=True)
                print("   ✓ 04b_information_expanded_full.png")
            else:
                print("   ⚠ Could not expand Additional information")

            # ── Capture the table columns from team list ──
            print("\n── Team list columns ──")
            page.goto(f"{BASE}/settings/filial_staff/{COMPANY_ID}/", wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page)
            ui_dumps["team_list_columns"] = page.evaluate(r"""() => {
                const cols = [];
                // Look for column header text
                for (const el of document.querySelectorAll('th, .q-table__top, [class*="header"]')) {
                    const t = (el.textContent || '').trim();
                    if (t && t.length < 80) cols.push(t);
                }
                // Also check the row structure
                const firstRow = document.querySelector('tr, [class*="row"]');
                return {column_headers: cols};
            }""")

        finally:
            browser.close()

    # Save supplemental UI dumps
    supp_path = OUT.parent / "ui_dumps_supplemental.json"
    supp_path.write_text(json.dumps(ui_dumps, indent=2, ensure_ascii=False))
    print(f"\n══ DONE — supplemental dumps saved to {supp_path} ══")


if __name__ == "__main__":
    main()
