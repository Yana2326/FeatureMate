"""
From the new dark Admin sidebar (Test A state), click "Team" then any
sub-item. Record what URL+view that produces.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    enable_new_ui_flags,
    nuke_overlays, close_translate_popup,
)

OUT = Path("output/add-team-member/discovery_v2")
OUT.mkdir(parents=True, exist_ok=True)


def probe(page, name):
    page.wait_for_timeout(1000)
    nuke_overlays(page); close_translate_popup(page)
    info = page.evaluate("""
    () => {
        const tabs = [...document.querySelectorAll('.q-tab, [role="tab"]')]
            .filter(t => {
                const r = t.getBoundingClientRect();
                return r.width > 5 && r.height > 5;
            }).map(t => (t.textContent || '').trim());
        const headings = [...document.querySelectorAll('h1, h2, h3')]
            .map(h => (h.textContent || '').trim()).filter(t => t.length > 0);
        const buttons = [...document.querySelectorAll('button, a.q-btn')]
            .filter(b => {
                const r = b.getBoundingClientRect();
                return r.width > 5 && r.height > 5 && r.top < 600 && r.left > 260;
            })
            .map(b => (b.textContent || '').trim())
            .filter(t => t.length > 0 && t.length < 50);
        return {url: location.href, tabs, headings, buttons: [...new Set(buttons)]};
    }
    """)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    print(f"\n  {name}: {info['url']}")
    print(f"    headings: {info['headings'][:5]}")
    print(f"    tabs: {info['tabs']}")
    print(f"    buttons: {info['buttons'][:8]}")
    return info


with sync_playwright() as pw:
    browser, ctx, page = launch_isolated_browser(pw, headless=False)
    print("== login ==")
    login(page)
    print("== language ==")
    switch_language_to_english(page)

    # Land in Admin mode + new sidebar
    print("== goto /settings/filial_staff/ + flags ==")
    page.goto(f"{BASE}/settings/filial_staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    enable_new_ui_flags(page)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3500)
    nuke_overlays(page); close_translate_popup(page)
    probe(page, "step1_filial_staff_admin")

    # Click "Team" in the dark sidebar to expand it (or visit team root)
    print("\n== click 'Team' in dark Admin sidebar ==")
    teams = page.evaluate("""
    () => {
        const cands = [...document.querySelectorAll('a, span, div, button')];
        const out = [];
        for (const el of cands) {
            const t = (el.textContent || '').trim();
            if (t !== 'Team') continue;
            const r = el.getBoundingClientRect();
            if (r.left > 260) continue;
            if (r.width < 5 || r.height < 5) continue;
            out.push({tag: el.tagName, x: Math.round(r.x), y: Math.round(r.y),
                      w: Math.round(r.width), h: Math.round(r.height),
                      cls: el.className?.toString?.().slice(0, 60) || ''});
        }
        return out;
    }
    """)
    print(f"  Team candidates: {teams}")

    if teams:
        t = teams[0]
        cx, cy = t['x'] + t['w']/2, t['y'] + t['h']/2
        print(f"  clicking Team at ({cx}, {cy})")
        page.mouse.click(cx, cy)
        page.wait_for_timeout(2000)
        probe(page, "step2_after_team_click")

    # Look for Team submenu items
    print("\n== look for Team submenu items ==")
    submenu = page.evaluate("""
    () => {
        const labels = ['Team members list', 'Schedule', 'Working schedule',
                        'Work Schedule', 'Positions', 'Access rights'];
        const out = {};
        const cands = [...document.querySelectorAll('a, span, div, button, li')];
        for (const lbl of labels) {
            for (const el of cands) {
                const t = (el.textContent || '').trim();
                if (t !== lbl) continue;
                const r = el.getBoundingClientRect();
                if (r.left > 320) continue;
                if (r.width < 5 || r.height < 5) continue;
                out[lbl] = {tag: el.tagName, x: Math.round(r.x), y: Math.round(r.y),
                            w: Math.round(r.width), h: Math.round(r.height),
                            href: el.href || null};
                break;
            }
        }
        return out;
    }
    """)
    print(f"  Team submenu: {json.dumps(submenu, indent=2)}")

    # Click "Team members list" if it exists
    if 'Team members list' in submenu:
        item = submenu['Team members list']
        cx, cy = item['x'] + item['w']/2, item['y'] + item['h']/2
        print(f"\n  clicking 'Team members list' at ({cx}, {cy})")
        page.mouse.click(cx, cy)
        page.wait_for_timeout(3500)
        probe(page, "step3_team_members_list")

    # Also try direct URL goto to see what these resolve to
    print("\n== direct goto candidates ==")
    for url_path in [
        "/team/staff/", "/team/members/", "/team/list/",
        "/settings/sidebar/staff/", "/staff/", "/staff/list/",
    ]:
        url = f"{BASE}{url_path}{COMPANY_ID}/"
        page.goto(url, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2500)
        nuke_overlays(page)
        info = page.evaluate("""
        () => {
            const h1 = document.querySelector('h1, h2, h3');
            const tabs = [...document.querySelectorAll('.q-tab, [role="tab"]')]
                .filter(t => {
                    const r = t.getBoundingClientRect();
                    return r.width > 5;
                }).map(t => (t.textContent || '').trim());
            // Is dark Admin sidebar present?
            const adminLabels = ['Analytical Reports', 'Team', 'Clients',
                                 'Online Booking', 'Services'];
            const cands = [...document.querySelectorAll('a, span, div')];
            const adminFound = adminLabels.filter(lbl => cands.some(el => {
                if ((el.textContent || '').trim() !== lbl) return false;
                const r = el.getBoundingClientRect();
                return r.width > 5 && r.left < 260;
            }));
            return {
                url: location.href,
                heading: h1 ? (h1.textContent || '').trim() : null,
                tabs, dark_admin: adminFound.length >= 4,
            };
        }
        """)
        print(f"  {url_path:35s} -> {info['url']}")
        print(f"    heading: {info['heading']!r}, tabs: {info['tabs']}, dark_admin: {info['dark_admin']}")

    browser.close()
