"""
Exploration script — discover the Add team member flow end-to-end.

Captures every distinct screen state into output/add-employee/screenshots/_explore/
so we can decide on the article structure and final highlight targets.
"""

from __future__ import annotations

import os
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    nuke_overlays, close_translate_popup,
    verify_administration_mode,
)


TEAM_LIST = f"{BASE}/settings/filial_staff/{COMPANY_ID}/"
EXPLORE = Path("output/add-employee/screenshots/_explore")


def dump_dom(page, label: str) -> None:
    """Dump a quick summary of all visible buttons + inputs + headings + tabs."""
    info = page.evaluate("""() => {
        const out = {h1: [], h2: [], buttons: [], inputs: [], tabs: [], modals: []};
        for (const h of document.querySelectorAll('h1')) {
            const t = (h.textContent || '').trim();
            if (t) out.h1.push(t);
        }
        for (const h of document.querySelectorAll('h2,h3')) {
            const t = (h.textContent || '').trim();
            if (t && t.length < 80) out.h2.push(t);
        }
        for (const b of document.querySelectorAll('button, a.btn, [role="button"]')) {
            const t = (b.textContent || '').trim();
            const r = b.getBoundingClientRect();
            if (t && t.length < 60 && r.width > 10 && r.height > 10) {
                out.buttons.push({text: t, x: Math.round(r.x), y: Math.round(r.y),
                                  w: Math.round(r.width), h: Math.round(r.height)});
            }
        }
        for (const i of document.querySelectorAll('input, select, textarea')) {
            const r = i.getBoundingClientRect();
            if (r.width < 5 || r.height < 5) continue;
            // try to find a label
            let label = i.getAttribute('placeholder') || i.getAttribute('aria-label') || '';
            if (!label && i.id) {
                const lab = document.querySelector(`label[for="${i.id}"]`);
                if (lab) label = (lab.textContent || '').trim();
            }
            if (!label) {
                // walk up to find sibling label
                let p = i.parentElement;
                for (let k = 0; k < 3 && p; k++) {
                    const lab = p.querySelector('label');
                    if (lab && lab.textContent.trim()) { label = lab.textContent.trim(); break; }
                    p = p.parentElement;
                }
            }
            out.inputs.push({tag: i.tagName.toLowerCase(), type: i.type || '',
                             name: i.name || '', label: label.slice(0, 60),
                             x: Math.round(r.x), y: Math.round(r.y),
                             w: Math.round(r.width), h: Math.round(r.height)});
        }
        for (const t of document.querySelectorAll('[role="tab"], .q-tab')) {
            const txt = (t.textContent || '').trim();
            const r = t.getBoundingClientRect();
            if (txt && r.width > 10) out.tabs.push({text: txt, x: Math.round(r.x), y: Math.round(r.y)});
        }
        for (const m of document.querySelectorAll('.q-dialog, [role="dialog"], .q-drawer')) {
            const r = m.getBoundingClientRect();
            if (r.width > 200 && r.height > 200) {
                out.modals.push({class: m.className.slice(0, 80),
                                 x: Math.round(r.x), y: Math.round(r.y),
                                 w: Math.round(r.width), h: Math.round(r.height)});
            }
        }
        return out;
    }""")
    EXPLORE.mkdir(parents=True, exist_ok=True)
    (EXPLORE / f"{label}.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
    print(f"\n── {label} ──")
    print(f"H1: {info['h1']}")
    print(f"H2/H3 ({len(info['h2'])}): {info['h2'][:15]}")
    print(f"Buttons ({len(info['buttons'])}):")
    for b in info['buttons'][:30]:
        print(f"   {b['text']:30s}  x={b['x']:4d} y={b['y']:4d} w={b['w']:4d} h={b['h']:3d}")
    print(f"Inputs ({len(info['inputs'])}):")
    for i in info['inputs'][:30]:
        print(f"   [{i['tag']}/{i['type']}] {i['label']:30s} name={i['name']:20s} y={i['y']:4d}")
    print(f"Tabs ({len(info['tabs'])}): {info['tabs']}")
    print(f"Modals ({len(info['modals'])}): {info['modals']}")


def screenshot(page, name: str) -> None:
    EXPLORE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EXPLORE / f"{name}.png"), full_page=False)
    print(f"   ✓ {name}.png")


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
            screenshot(page, "01_team_list")
            dump_dom(page, "01_team_list")

            print("\n══ Click Add team member ══")
            # Click the Add team member button
            page.evaluate("""() => {
                const btns = [...document.querySelectorAll('button, a, [role="button"]')];
                for (const b of btns) {
                    const t = (b.textContent || '').trim();
                    if (t === 'Add team member') { b.click(); return; }
                }
            }""")
            page.wait_for_timeout(3000)
            nuke_overlays(page)
            close_translate_popup(page)
            screenshot(page, "02_add_form_empty")
            dump_dom(page, "02_add_form_empty")

            # Try expanding all tabs/sections in the form
            print("\n══ Probe form tabs and sections ══")
            tabs = page.evaluate("""() => {
                const tabs = [];
                for (const t of document.querySelectorAll('[role="tab"], .q-tab, .nav-tabs a, .tabs__item')) {
                    const txt = (t.textContent || '').trim();
                    const r = t.getBoundingClientRect();
                    if (txt && r.width > 10 && r.height > 10) {
                        tabs.push({text: txt, x: Math.round(r.x + r.width/2),
                                   y: Math.round(r.y + r.height/2)});
                    }
                }
                return tabs;
            }""")
            print(f"Found {len(tabs)} tabs: {[t['text'] for t in tabs]}")
            for i, tab in enumerate(tabs[:8]):
                try:
                    page.mouse.click(tab["x"], tab["y"])
                    page.wait_for_timeout(800)
                    screenshot(page, f"03_tab_{i:02d}_{tab['text'][:20].replace(' ', '_').replace('/', '_')}")
                except Exception as e:
                    print(f"   ! tab {tab['text']!r} failed: {e}")

        finally:
            browser.close()

    print("\nExploration done.")


if __name__ == "__main__":
    main()
