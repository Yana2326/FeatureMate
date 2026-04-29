"""
One-shot probe: log in, switch to Administration mode, navigate to
Team members list, take a single screenshot. Used to verify that the
mode-switch logic is correct and that the test account's Admin UI
matches what the user expects.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    login, switch_language_to_english, nuke_overlays, close_translate_popup,
)

OUT = Path("output/add-team-member/_probe_admin.png")
OUT.parent.mkdir(parents=True, exist_ok=True)


def click_admin_button(page) -> str:
    """
    The bottom-left mode-toggle button shows the OTHER mode (where it
    would take you). Find a button whose text matches Administration or
    Digital Schedule (case-insensitive) and is in the bottom-left.
    Click whichever exists; report what was found.
    """
    info = page.evaluate("""
    () => {
        const btns = [...document.querySelectorAll('button, a, div')];
        const vh = window.innerHeight;
        for (const b of btns) {
            const txt = (b.textContent || '').trim();
            if (txt.length === 0 || txt.length > 30) continue;
            if (!/^(administration|digital\\s*schedule)$/i.test(txt)) continue;
            const r = b.getBoundingClientRect();
            if (r.left < 260 && r.right > 0 && r.bottom > vh - 120 && r.top < vh) {
                return {text: txt, x: r.x, y: r.y, w: r.width, h: r.height};
            }
        }
        return null;
    }
    """)
    if info is None:
        return "(no mode-toggle button found)"
    print(f"  mode-toggle button at bottom-left reads: {info['text']!r}")
    if info["text"].lower() == "administration":
        # Currently in Digital Schedule → click to switch
        page.evaluate("""
        () => {
            const btns = [...document.querySelectorAll('button, a, div')];
            const vh = window.innerHeight;
            for (const b of btns) {
                const txt = (b.textContent || '').trim();
                if (!/^administration$/i.test(txt)) continue;
                const r = b.getBoundingClientRect();
                if (r.left < 260 && r.bottom > vh - 120) { b.click(); return; }
            }
        }
        """)
        page.wait_for_timeout(2500)
        return "switched-from-digital-schedule"
    return "already-in-administration"


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=False,  # visible so we can watch what happens
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

    print("== go to team members list ==")
    page.goto(f"{BASE}/settings/filial_staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(800)

    print("== probe + switch to Administration ==")
    state = click_admin_button(page)
    print(f"  state: {state}")

    # If we switched, we may have been redirected to /timetable/. Re-navigate.
    page.goto(f"{BASE}/settings/filial_staff/{COMPANY_ID}/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page); close_translate_popup(page); page.wait_for_timeout(800)

    # Verify final state
    final = page.evaluate("""
    () => {
        const btns = [...document.querySelectorAll('button, a, div')];
        const vh = window.innerHeight;
        for (const b of btns) {
            const txt = (b.textContent || '').trim();
            if (!/^(administration|digital\\s*schedule)$/i.test(txt)) continue;
            const r = b.getBoundingClientRect();
            if (r.left < 260 && r.bottom > vh - 120) return txt;
        }
        return '(none)';
    }
    """)
    print(f"  final mode-toggle text: {final!r}  "
          f"(should read 'Digital Schedule' if we are in Administration mode)")

    # Dump a few signals that might indicate the UI version
    diagnostics = page.evaluate("""
    () => {
        const keys_local = Object.keys(localStorage);
        const keys_session = Object.keys(sessionStorage);
        // Any sidebar markers?
        const dark_sidebar = !!document.querySelector(
            '[class*="sidebar"][class*="dark"], aside.dark, [data-theme="dark"]'
        );
        const has_quick_bar = !!document.querySelector(
            'a[href*="product_sales"], [class*="quick-bar"], [class*="QuickBar"]'
        );
        const has_position_tab = !!Array.from(document.querySelectorAll('*'))
            .find(el => /^Position$/.test((el.textContent || '').trim()) && el.children.length === 0);
        const has_specialization_tab = !!Array.from(document.querySelectorAll('*'))
            .find(el => /^Specialization$/.test((el.textContent || '').trim()) && el.children.length === 0);
        const has_system_users_tab = !!Array.from(document.querySelectorAll('*'))
            .find(el => /^System users$/.test((el.textContent || '').trim()) && el.children.length === 0);
        return {
            href: location.href,
            viewport: {w: innerWidth, h: innerHeight, dpr: devicePixelRatio},
            local_keys: keys_local,
            session_keys: keys_session,
            dark_sidebar, has_quick_bar,
            new_ui_tabs: {has_position_tab, has_specialization_tab, has_system_users_tab},
        };
    }
    """)
    print("\n=== Diagnostics ===")
    import json
    print(json.dumps(diagnostics, indent=2))

    page.screenshot(path=str(OUT), full_page=False)
    print(f"\n✓ Probe screenshot saved to {OUT}")
    browser.close()
