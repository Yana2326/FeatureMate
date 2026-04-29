"""
After enabling new sidebar, click Team → Team members list via the new
nav, and inspect the resulting URL + tabs.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    login, switch_language_to_english, nuke_overlays, close_translate_popup,
)

OUT = Path("output/add-team-member/_probe_via_nav.png")


def enable_new_nav(page):
    """Apply the storage flag flips that activate the new dark sidebar."""
    page.evaluate("""
    () => {
        localStorage.setItem('erp_client_sidebar_compact_navigation', 'expanded');
        localStorage.setItem('new_navigation_enabled', 'true');
        sessionStorage.setItem('erp-nav-menu-mode-switch:enabled', '1');
    }
    """)


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=False,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI", "--no-sandbox"],
    )
    ctx  = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()

    print("== login ==")
    login(page)
    print("== switch language ==")
    switch_language_to_english(page)

    page.goto(f"{BASE}/timetable/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    enable_new_nav(page)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(800)

    # Click "Digital schedule" / "Administration" toggle if needed to enter Admin
    btn_text = page.evaluate("""
    () => {
        const btns = [...document.querySelectorAll('button, a, div')];
        const vh = window.innerHeight;
        for (const b of btns) {
            const t = (b.textContent || '').trim();
            if (!/^(administration|digital\\s*schedule)$/i.test(t)) continue;
            const r = b.getBoundingClientRect();
            if (r.left < 260 && r.bottom > vh - 120) return t;
        }
        return null;
    }
    """)
    print(f"  bottom-left button text: {btn_text!r}")
    if btn_text and btn_text.lower() == "administration":
        # We're in Digital Schedule, switch to Admin
        print("  switching to Administration via button")
        page.evaluate("""
        () => {
            const btns = [...document.querySelectorAll('button, a, div')];
            const vh = window.innerHeight;
            for (const b of btns) {
                const t = (b.textContent || '').trim();
                if (!/^administration$/i.test(t)) continue;
                const r = b.getBoundingClientRect();
                if (r.left < 260 && r.bottom > vh - 120) { b.click(); return; }
            }
        }
        """)
        page.wait_for_timeout(2500)

    # Click "Team" in the dark sidebar to expand it
    print("\n== click Team in sidebar ==")
    page.evaluate("""
    () => {
        const candidates = [...document.querySelectorAll('a, span, div, button')];
        for (const el of candidates) {
            const t = (el.textContent || '').trim();
            if (t !== 'Team') continue;
            const r = el.getBoundingClientRect();
            if (r.left < 260 && r.right < 400 && r.height < 80) {
                el.click(); return;
            }
        }
    }
    """)
    page.wait_for_timeout(1200)

    print("== click Team members list ==")
    page.evaluate("""
    () => {
        const candidates = [...document.querySelectorAll('a, span, div, button')];
        for (const el of candidates) {
            const t = (el.textContent || '').trim();
            if (t !== 'Team members list') continue;
            const r = el.getBoundingClientRect();
            if (r.left < 320 && r.height < 80) {
                el.click(); return;
            }
        }
    }
    """)
    page.wait_for_timeout(3000)
    nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(500)

    # What URL did we end up on?
    url_now = page.evaluate("() => location.href")
    print(f"\n  landed on: {url_now}")

    # Look for new-UI tab labels
    found_tabs = page.evaluate("""
    () => {
        const labels = ['Position', 'Specialization', 'System users'];
        const out = {};
        for (const lbl of labels) {
            const el = [...document.querySelectorAll('a, span, button, div, li')]
                .find(e => (e.textContent || '').trim() === lbl);
            out[lbl] = el ? {tag: el.tagName, cls: el.className.toString().slice(0, 80)} : null;
        }
        return out;
    }
    """)
    print(f"\n  tabs:")
    import json
    print(json.dumps(found_tabs, indent=2))

    page.screenshot(path=str(OUT), full_page=False)
    print(f"\n✓ Saved {OUT}")
    browser.close()
