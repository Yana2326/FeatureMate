"""Find member-card tabs for the new UI."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    enable_new_ui_flags, nuke_overlays,
)

OUT = Path("output/add-team-member/discovery_v2")


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

    # ── Expand "Without position" using Playwright locator ─────────────
    # Click the chevron / header row
    print("== try expand 'Without position' via locator ==")
    expand_via_locator = page.locator('text="Without position"').first
    if expand_via_locator.count() > 0:
        # Click parent (or the wrapper) — the click should propagate to accordion
        expand_via_locator.click(force=True)
        page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT / "card_01_after_expand_attempt.png"), full_page=False)

    # Inspect what's now visible
    members = page.evaluate("""
    () => {
        // Look for actual member rows after expand. They should be inside
        // the accordion content area.
        const cands = [...document.querySelectorAll(
            '[class*="employee-row"], [class*="StaffRow"], [class*="member-row"], [class*="staff-list-row"], a[href*="employee"], a[href*="staff"]'
        )];
        const rows = cands.filter(el => el.getBoundingClientRect().width > 100);
        return rows.slice(0, 10).map(el => ({
            tag: el.tagName, cls: (el.className?.toString?.() || '').slice(0, 80),
            href: el.href || null,
            text: (el.textContent || '').replace(/\\s+/g, ' ').slice(0, 80),
            xywh: (() => {
                const r = el.getBoundingClientRect();
                return [Math.round(r.x), Math.round(r.y),
                        Math.round(r.width), Math.round(r.height)];
            })(),
        }));
    }
    """)
    print(f"  member rows: {json.dumps(members, indent=2)}")

    # Try clicking "Mary" via Playwright text locator
    print("\n== try click Mary via text locator ==")
    mary = page.locator('text="Mary"').first
    if mary.count() > 0:
        try:
            mary.click(force=True, timeout=5000)
            page.wait_for_timeout(3500)
            print(f"  url after click: {page.url}")
            page.screenshot(path=str(OUT / "card_02_after_mary_click.png"), full_page=False)
        except Exception as e:
            print(f"  click failed: {e}")

    # If we ended up on the member card, dump tab structure
    tabs = page.evaluate("""
    () => {
        const tabs = [...document.querySelectorAll('.q-tab, [role="tab"]')]
            .filter(t => t.getBoundingClientRect().width > 5);
        return tabs.map(t => ({
            text: (t.textContent || '').trim(),
            cls: (t.className?.toString?.() || '').slice(0, 60),
            xywh: (() => {
                const r = t.getBoundingClientRect();
                return [Math.round(r.x), Math.round(r.y),
                        Math.round(r.width), Math.round(r.height)];
            })(),
        }));
    }
    """)
    print(f"\n  tabs found: {json.dumps(tabs, indent=2)}")

    # Look for ALL clickable items inside the right panel (since maybe member card is in side panel)
    sidepanel = page.evaluate("""
    () => {
        const root = document.querySelector('#v-sidebar-teleport-container');
        if (!root) return {visible: false};
        const r = root.getBoundingClientRect();
        return {
            visible: r.width > 100 && r.height > 100,
            xywh: [Math.round(r.x), Math.round(r.y),
                   Math.round(r.width), Math.round(r.height)],
            html_len: root.outerHTML.length,
            nav_items: [...root.querySelectorAll('[class*="nav"], [class*="tab"], [class*="item"], a')]
                .filter(e => e.getBoundingClientRect().width > 5)
                .map(e => ({
                    text: (e.textContent || '').replace(/\\s+/g, ' ').slice(0, 50),
                    tag: e.tagName,
                    cls: (e.className?.toString?.() || '').slice(0, 60),
                })).slice(0, 30),
        };
    }
    """)
    print(f"\n  side panel: {json.dumps(sidepanel, indent=2)}")

    browser.close()
