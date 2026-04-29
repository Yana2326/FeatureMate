"""Inspect what DOM the + Add panel has."""
import json
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    enable_new_ui_flags, nuke_overlays,
)

with sync_playwright() as pw:
    browser, ctx, page = launch_isolated_browser(pw, headless=False)
    login(page); switch_language_to_english(page)
    page.goto(f"{BASE}/timetable/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    enable_new_ui_flags(page)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2500)
    page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)

    page.locator('[data-locator="create_employee_btn"]').first.click()
    page.wait_for_timeout(2500)

    # Dump every element whose textContent has "Add and edit employees"
    info = page.evaluate("""
    () => {
        const all = [...document.querySelectorAll('*')];
        const out = [];
        for (const el of all) {
            const txt = (el.textContent || '').replace(/\\s+/g, ' ').trim();
            if (!txt.includes('Add and edit employees')) continue;
            const r = el.getBoundingClientRect();
            if (r.width < 50 || r.height < 20) continue;
            out.push({
                tag: el.tagName,
                cls: (el.className?.toString?.() || '').slice(0, 100),
                data_locator: el.getAttribute('data-locator'),
                txt_len: txt.length,
                txt_start: txt.slice(0, 60),
                xywh: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                children: el.children.length,
            });
        }
        return out.slice(0, 30);
    }
    """)
    print(json.dumps(info, indent=2))

    # Dump full content of the v-sidebar-teleport-container
    panel_full = page.evaluate("""
    () => {
        const root = document.querySelector('#v-sidebar-teleport-container .v-sidebar__content');
        return root ? root.outerHTML : null;
    }
    """)
    if panel_full:
        from pathlib import Path
        Path("output/add-team-member/discovery_v2/panel.html").write_text(panel_full)
        print(f"\n=== Wrote panel.html ({len(panel_full)} chars) ===")

    browser.close()
