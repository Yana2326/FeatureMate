"""
Walk the new-UI add flow: click + Add → choose Employee → modal/screen.
Also expand "Without position" group + click Mary to land on member card.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    enable_new_ui_flags, nuke_overlays, close_translate_popup,
)

OUT = Path("output/add-team-member/discovery_v2")


def snap(page, name, *, nuke=False):
    page.wait_for_timeout(700)
    if nuke:
        nuke_overlays(page); close_translate_popup(page)
        page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    info = page.evaluate("""
    () => {
        const tabs = [...document.querySelectorAll('.q-tab, [role="tab"]')]
            .filter(t => t.getBoundingClientRect().width > 5)
            .map(t => (t.textContent || '').trim());
        const headings = [...document.querySelectorAll('h1, h2, h3, h4')]
            .filter(h => h.getBoundingClientRect().width > 5)
            .slice(0, 6).map(h => (h.textContent || '').trim());
        const labels = [...document.querySelectorAll('.q-field__label, label')]
            .filter(l => l.getBoundingClientRect().width > 5)
            .slice(0, 25).map(l => (l.textContent || '').trim());
        return {url: location.href, headings, tabs, labels: [...new Set(labels)]};
    }
    """)
    print(f"\n  {name}: {info['url']}")
    print(f"    headings: {info['headings'][:4]}")
    print(f"    tabs: {info['tabs']}")
    print(f"    labels: {info['labels'][:15]}")
    return info


with sync_playwright() as pw:
    browser, ctx, page = launch_isolated_browser(pw, headless=False)
    print("== login + lang + flags ==")
    login(page); switch_language_to_english(page)
    page.goto(f"{BASE}/timetable/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    enable_new_ui_flags(page)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2500)
    page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)

    # ── Click + Add ────────────────────────────────────────────────────
    print("\n== click + Add ==")
    page.locator('[data-locator="create_employee_btn"]').first.click()
    page.wait_for_timeout(2000)
    snap(page, "flow_01_add_chooser")

    # ── Click Employee in right panel ──────────────────────────────────
    print("\n== click Employee tile (2nd y-core-card-button) ==")
    clicked = page.evaluate("""
    () => {
        const cards = [...document.querySelectorAll('y-core-card-button')];
        // Second card is the Employee tile
        const target = cards[cards.length - 1];
        if (!target) return null;
        const r = target.getBoundingClientRect();
        return {x: r.x + r.width/2, y: r.y + r.height/2,
                count: cards.length, cls: (target.className?.toString?.() || '')};
    }
    """)
    print(f"  click coords: {clicked}")
    if clicked:
        page.mouse.click(clicked["x"], clicked["y"])
    page.wait_for_timeout(4000)
    snap(page, "flow_02_add_employee_screen")

    # Dump form/modal structure
    form_info = page.evaluate("""
    () => {
        const dialog = [...document.querySelectorAll('.q-dialog, [class*="modal"]')]
            .find(d => d.getBoundingClientRect().width > 100);
        const root = dialog || document.body;
        const inputs = [...root.querySelectorAll('input, textarea, select')]
            .filter(i => i.getBoundingClientRect().width > 5)
            .map(i => ({
                type: i.type || i.tagName,
                name: i.name,
                placeholder: i.placeholder,
                label: (i.closest('.q-field')?.querySelector('.q-field__label')?.textContent || '').trim(),
            }));
        const buttons = [...root.querySelectorAll('button')]
            .filter(b => b.getBoundingClientRect().width > 5)
            .map(b => (b.textContent || '').trim())
            .filter(t => t.length > 0 && t.length < 40);
        return {
            modal_present: !!dialog,
            url: location.href,
            inputs: inputs.slice(0, 30),
            buttons: [...new Set(buttons)].slice(0, 20),
        };
    }
    """)
    print(f"\n  form: {json.dumps(form_info, indent=2, ensure_ascii=False)}")

    # ── Close, then go back to list ────────────────────────────────────
    page.keyboard.press("Escape")
    page.wait_for_timeout(800)
    page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)

    # ── Expand "Without position" accordion ────────────────────────────
    print("\n== expand 'Without position' (chevron click) ==")
    expand = page.evaluate("""
    () => {
        // Accordion header: parent contains both "Without position" + "employees: ..."
        const all = [...document.querySelectorAll('div, [class*="group"], [class*="accordion"], [class*="expansion"]')];
        for (const el of all) {
            const t = (el.textContent || '').replace(/\\s+/g, ' ').trim();
            if (!/^Without position\\s*employees:\\s*\\d+$/i.test(t)) continue;
            const r = el.getBoundingClientRect();
            if (r.width < 200 || r.left < 100) continue;
            return {x: r.x + r.width/2, y: r.y + r.height/2, text: t};
        }
        return null;
    }
    """)
    if expand:
        page.mouse.click(expand["x"], expand["y"])
    print(f"  expand: {expand}")
    page.wait_for_timeout(2000)
    snap(page, "flow_03_group_expanded")

    # ── Find a member name + click ─────────────────────────────────────
    print("\n== find + click a team member ==")
    members = page.evaluate("""
    () => {
        // Inside the expanded group, members are listed. Find rows whose
        // text starts with a name.
        const cands = [...document.querySelectorAll(
            '[class*="employee"], [class*="staff-row"], [class*="member"], [class*="StaffItem"], li, tr, a'
        )];
        const out = [];
        const seen = new Set();
        for (const el of cands) {
            const t = (el.textContent || '').trim();
            if (t.length < 3 || t.length > 80) continue;
            // Names: starts with capital, single word or two words
            const m = t.match(/^([A-Z][a-z]{2,}(?:\\s[A-Z][a-z]{2,})?)/);
            if (!m) continue;
            const r = el.getBoundingClientRect();
            if (r.left < 260 || r.left > 700) continue;
            if (r.width < 50 || r.height < 20 || r.height > 100) continue;
            if (seen.has(m[1])) continue;
            seen.add(m[1]);
            out.push({
                name: m[1], full: t.slice(0, 80),
                tag: el.tagName, cls: (el.className?.toString?.() || '').slice(0, 60),
                xy: [Math.round(r.x + r.width/2), Math.round(r.y + r.height/2)],
            });
            if (out.length >= 8) break;
        }
        return out;
    }
    """)
    print(f"  members: {json.dumps(members, indent=2)}")

    if members:
        m = members[0]
        print(f"\n  clicking {m['name']} at {m['xy']}")
        page.mouse.click(m["xy"][0], m["xy"][1])
        page.wait_for_timeout(3500)
        nuke_overlays(page)
        snap(page, "flow_04_member_card")

    browser.close()
