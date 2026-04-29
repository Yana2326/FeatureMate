"""Inspect what '+ Add' does and how member-card opens."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    enable_new_ui_flags, nuke_overlays, close_translate_popup,
)

OUT = Path("output/add-team-member/discovery_v2")


with sync_playwright() as pw:
    browser, ctx, page = launch_isolated_browser(pw, headless=False)
    print("== login ==")
    login(page)
    switch_language_to_english(page)
    page.goto(f"{BASE}/timetable/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    enable_new_ui_flags(page)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(3500)
    nuke_overlays(page)

    # Inspect the + Add button structure
    info = page.evaluate("""
    () => {
        const btns = [...document.querySelectorAll('button, a, [role="button"]')];
        for (const b of btns) {
            const t = (b.textContent || '').trim();
            if (!/^\\+\\s*Add$/.test(t) && t !== 'Add') continue;
            const r = b.getBoundingClientRect();
            if (r.width < 5 || r.left < 260) continue;
            return {
                tag: b.tagName,
                cls: b.className?.toString?.() || '',
                href: b.href || null,
                onclick: b.onclick ? 'has' : null,
                outerHTML: b.outerHTML.slice(0, 400),
                xy: [r.x + r.width/2, r.y + r.height/2],
            };
        }
        return null;
    }
    """)
    print("\n+ Add button:", json.dumps(info, indent=2))

    # Real mouse click via XY
    print("\n== mouse click + Add ==")
    if info:
        page.mouse.click(info["xy"][0], info["xy"][1])
        page.wait_for_timeout(2500)
        # What changed?
        state = page.evaluate("""
        () => {
            const dialogs = [...document.querySelectorAll('.q-dialog, [role="dialog"], [class*="modal"]')]
                .filter(d => {
                    const r = d.getBoundingClientRect();
                    return r.width > 5 && r.height > 5;
                });
            const inputs_in_dialog = dialogs[0]
                ? [...dialogs[0].querySelectorAll('input, textarea, select')].map(i => ({
                    type: i.type || i.tagName,
                    name: i.name,
                    placeholder: i.placeholder,
                    label: (i.closest('.q-field')?.querySelector('.q-field__label')?.textContent || '').trim(),
                  }))
                : [];
            return {
                url: location.href,
                dialog_count: dialogs.length,
                dialog_text: dialogs[0] ? (dialogs[0].textContent || '').slice(0, 400) : null,
                inputs: inputs_in_dialog,
            };
        }
        """)
        print("\n  state after click:", json.dumps(state, indent=2, ensure_ascii=False))
        page.screenshot(path=str(OUT / "probe_add_click.png"), full_page=False)

    # Member-card click probe: try clicking accordion arrow + then a member name
    print("\n== expanding 'Without position' group ==")
    expand = page.evaluate("""
    () => {
        // Find the chevron/header for Without position
        const groups = [...document.querySelectorAll('*')].filter(el => {
            const t = (el.textContent || '').trim();
            return t.startsWith('Without position') && el.children.length <= 5;
        });
        for (const g of groups) {
            const r = g.getBoundingClientRect();
            if (r.width > 100 && r.left > 260) {
                g.click();
                return {
                    clicked: (g.textContent || '').slice(0, 60),
                    x: r.x + r.width/2, y: r.y + r.height/2,
                };
            }
        }
        return null;
    }
    """)
    print(f"  expand: {expand}")
    page.wait_for_timeout(1500)

    # After expand, dump first 5 visible names in the table
    names = page.evaluate("""
    () => {
        // Find children of .q-list/.q-item or any rows under the group
        const rows = [...document.querySelectorAll('.q-item, [class*="Row"], [class*="row"], a, span, div')];
        const seen = new Set();
        const out = [];
        for (const el of rows) {
            const t = (el.textContent || '').trim();
            if (t.length === 0 || t.length > 30) continue;
            if (!/^[A-Z][a-z]+(?: [A-Z][a-z]+)?$/.test(t)) continue;
            const r = el.getBoundingClientRect();
            if (r.left < 260 || r.left > 600) continue;
            if (r.width < 5 || r.height < 5) continue;
            if (seen.has(t)) continue;
            seen.add(t);
            out.push({name: t, tag: el.tagName,
                      cls: (el.className?.toString?.() || '').slice(0, 60),
                      xy: [Math.round(r.x + r.width/2), Math.round(r.y + r.height/2)],
                      parent: el.parentElement?.tagName});
            if (out.length >= 6) break;
        }
        return out;
    }
    """)
    print(f"\n  visible names: {json.dumps(names, indent=2)}")

    # Try click first name with real mouse
    if names:
        n = names[0]
        print(f"\n== mouse click on '{n['name']}' at {n['xy']} ==")
        page.mouse.click(n["xy"][0], n["xy"][1])
        page.wait_for_timeout(3500)
        state = page.evaluate("""
        () => ({
            url: location.href,
            h1: (document.querySelector('h1, h2')?.textContent || '').trim(),
            tabs: [...document.querySelectorAll('.q-tab, [role="tab"]')]
                .filter(t => t.getBoundingClientRect().width > 5)
                .map(t => (t.textContent || '').trim()),
        })
        """)
        print(f"  after click: {json.dumps(state, indent=2)}")
        page.screenshot(path=str(OUT / "probe_member_click.png"), full_page=False)

    browser.close()
