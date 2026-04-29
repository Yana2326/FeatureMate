"""
Direct comparison: try multiple flag combinations + URL strategies and
observe which one actually produces the new dark Admin sidebar.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    nuke_overlays, close_translate_popup,
)

OUT = Path("output/add-team-member/discovery_v2")
OUT.mkdir(parents=True, exist_ok=True)


SIDEBAR_PROBE = """
() => {
    const want = ['Analytical Reports', 'Team', 'Clients', 'Online Booking',
                  'Services', 'Products', 'Finance', 'Payroll',
                  'Notifications', 'Loyalty', 'Resources', 'Integrations',
                  'Settings', 'Billing'];
    const cands = [...document.querySelectorAll('a, span, div')];
    const out = {};
    for (const lbl of want) {
        let visible = null;
        let any = null;
        for (const el of cands) {
            const t = (el.textContent || '').trim();
            if (t !== lbl) continue;
            const r = el.getBoundingClientRect();
            const rec = {x: Math.round(r.x), y: Math.round(r.y),
                         w: Math.round(r.width), h: Math.round(r.height),
                         tag: el.tagName, parent: el.parentElement?.tagName};
            if (any === null) any = rec;
            if (r.width > 5 && r.height > 5) {
                visible = rec; break;
            }
        }
        out[lbl] = visible || any;
    }
    // Mode-toggle button at bottom-left
    const vh = window.innerHeight;
    const btns = [...document.querySelectorAll('button, a, div')];
    let toggle = null;
    for (const b of btns) {
        const t = (b.textContent || '').trim();
        if (!/^(administration|digital\\s*schedule)$/i.test(t)) continue;
        const r = b.getBoundingClientRect();
        if (r.left < 260 && r.bottom > vh - 120) {
            toggle = {text: t, x: Math.round(r.x), y: Math.round(r.y),
                      w: Math.round(r.width), h: Math.round(r.height)};
            break;
        }
    }
    return {url: location.href, sidebar: out, toggle};
}
"""


def set_full_flags(page):
    page.evaluate("""
    () => {
        localStorage.setItem('new_navigation_enabled', 'true');
        localStorage.setItem('new_nav_enabled', 'true');
        localStorage.setItem('nav_menu_mode', 'new');
        localStorage.setItem('erp_client_sidebar_compact_navigation', 'expanded');
        sessionStorage.setItem('erp-nav-menu-mode-switch:enabled', 'true');
        sessionStorage.setItem('erp-nav-menu-mode-switch', 'new');
        sessionStorage.setItem('erp-nav-menu-version', '2');
    }
    """)


with sync_playwright() as pw:
    browser, ctx, page = launch_isolated_browser(pw, headless=False)
    print("== login ==")
    login(page)
    print("== language ==")
    switch_language_to_english(page)

    # Test A: legacy URL, set flags, reload (probe_flags.py style)
    print("\n=== Test A: /settings/filial_staff/ + flags + reload ===")
    page.goto(f"{BASE}/settings/filial_staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    set_full_flags(page)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(500)
    snap_a = page.evaluate(SIDEBAR_PROBE)
    page.screenshot(path=str(OUT / "test_A.png"), full_page=False)
    print(f"  url: {snap_a['url']}")
    print(f"  toggle: {snap_a['toggle']}")
    visible = [k for k, v in snap_a['sidebar'].items() if v and v['w'] > 5]
    print(f"  visible Admin labels: {visible}")

    # Test B: Force admin via #mode=0 hash, then reload
    print("\n=== Test B: /timetable/#mode=0 + flags + goto staff URL ===")
    page.goto(f"{BASE}/timetable/{COMPANY_ID}/#mode=0", wait_until="networkidle")
    page.wait_for_timeout(2500)
    set_full_flags(page)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(500)
    page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(500)
    snap_b = page.evaluate(SIDEBAR_PROBE)
    page.screenshot(path=str(OUT / "test_B.png"), full_page=False)
    print(f"  url: {snap_b['url']}")
    print(f"  toggle: {snap_b['toggle']}")
    visible = [k for k, v in snap_b['sidebar'].items() if v and v['w'] > 5]
    print(f"  visible Admin labels: {visible}")

    # Test C: Click the bottom-left "Administration" button to toggle to Admin
    print("\n=== Test C: click 'Administration' bottom-left button ===")
    if snap_b['toggle'] and snap_b['toggle']['text'].lower() == 'administration':
        cx = snap_b['toggle']['x'] + snap_b['toggle']['w']/2
        cy = snap_b['toggle']['y'] + snap_b['toggle']['h']/2
        page.mouse.click(cx, cy)
        page.wait_for_timeout(3500)
        # navigate back to staff URL
        page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/", wait_until="networkidle")
        page.wait_for_timeout(3000)
        nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(500)
        snap_c = page.evaluate(SIDEBAR_PROBE)
        page.screenshot(path=str(OUT / "test_C.png"), full_page=False)
        print(f"  url: {snap_c['url']}")
        print(f"  toggle: {snap_c['toggle']}")
        visible = [k for k, v in snap_c['sidebar'].items() if v and v['w'] > 5]
        print(f"  visible Admin labels: {visible}")
    else:
        print(f"  skipped (toggle = {snap_b['toggle']})")

    # Save raw data
    out_path = OUT / "compare_flags.json"
    out_path.write_text(json.dumps({
        "test_A": snap_a, "test_B": snap_b,
        "test_C": snap_c if 'snap_c' in dir() else None,
    }, indent=2, ensure_ascii=False))
    print(f"\n✓ saved {out_path}")

    browser.close()
