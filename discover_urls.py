"""
Discover Altegio URLs by finding all <a> elements after login and
testing candidates with the /{section}/{id}/ pattern.
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL      = "yanabar2304@gmail.com"
PASSWORD   = "Yanatest23"
COMPANY_ID = "1253779"
OUT        = Path("output")
OUT.mkdir(parents=True, exist_ok=True)
VW, VH = 1440, 900


def nuke_overlays(page: Page) -> None:
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    for label in ["Not now", "View later", "Later", "Skip", "Close"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=400):
                btn.click()
                page.wait_for_timeout(300)
        except Exception:
            pass
    page.evaluate("""() => {
        for (const el of [...document.querySelectorAll('*')]) {
            if (!el.isConnected) continue;
            const st = window.getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;
            const z = parseInt(st.zIndex) || 0;
            if (z < 50) continue;
            const r = el.getBoundingClientRect();
            if (r.width > 300 && r.height > 200
                && (st.position === 'fixed' || st.position === 'absolute')) {
                el.remove();
            }
        }
    }""")
    page.wait_for_timeout(300)


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--lang=en-US"])
    ctx = browser.new_context(viewport={"width": VW, "height": VH}, locale="en-US")
    page = ctx.new_page()

    print("── Login ──")
    page.goto("https://app.alteg.io", wait_until="networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")

    # ── Find ALL <a> elements (visible AND hidden) with href ──
    print("\n── All <a> hrefs in DOM ──")
    all_hrefs = page.evaluate("""() => {
        return [...document.querySelectorAll('a[href]')].map(a => ({
            href: a.href,
            text: (a.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 60),
            visible: (a.getBoundingClientRect().width > 0)
        }));
    }""")

    # Show unique hrefs
    seen = set()
    unique = []
    for h in all_hrefs:
        if h['href'] in seen:
            continue
        seen.add(h['href'])
        unique.append(h)
    print(f"  Total unique hrefs: {len(unique)}")
    for h in unique:
        vis = "V" if h['visible'] else " "
        print(f"    [{vis}] {h['href']:80s} | {h['text']}")

    # ── Look at top bar nav ──
    print("\n── Top navbar items ──")
    top_items = page.evaluate("""() => {
        return [...document.querySelectorAll('a, [role="link"]')]
            .filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.y < 100;
            })
            .map(el => ({
                href: el.href || null,
                text: (el.textContent || '').trim().slice(0, 60),
                rect: el.getBoundingClientRect()
            }));
    }""")
    for it in top_items:
        print(f"    y={int(it['rect']['y']):3d} x={int(it['rect']['x']):4d} | {it.get('text','')} | {it.get('href','')}")

    # ── Look at left sidebar nav ──
    print("\n── Left sidebar items (including hidden) ──")
    left_items = page.evaluate("""() => {
        return [...document.querySelectorAll('a, [role="menuitem"]')]
            .filter(el => {
                const r = el.getBoundingClientRect();
                return r.x < 250 && r.width > 0;
            })
            .map(el => ({
                href: el.href || null,
                text: (el.textContent || '').trim().slice(0, 60),
                y: el.getBoundingClientRect().y
            }));
    }""")
    for it in sorted(left_items, key=lambda x: x.get('y', 0))[:50]:
        print(f"    y={int(it.get('y',0)):4d} | {it.get('text','')} | {it.get('href','')}")

    # ── Dump full DOM of the left navigation menu ──
    print("\n── Extract sidebar HTML ──")
    sidebar_html = page.evaluate("""() => {
        const cs = document.querySelectorAll(
            'nav, aside, [class*="sidebar"], [class*="nav-menu"], ' +
            '[class*="left-menu"], .erp-nav-menu'
        );
        let html = '';
        for (const el of cs) {
            const r = el.getBoundingClientRect();
            if (r.width < 50 || r.height < 200) continue;
            html += '---' + el.className.slice(0, 80) + '---\\n';
            html += el.outerHTML.slice(0, 3000) + '\\n';
        }
        return html;
    }""")
    (OUT / "sidebar_html.txt").write_text(sidebar_html[:20000])
    print(f"  Saved to output/sidebar_html.txt (total {len(sidebar_html)} chars)")

    # ── Test URL patterns: /{section}/{id}/ ──
    print("\n── Test /{section}/{id}/ pattern ──")
    sections = [
        "timetable", "clients", "overview", "analytics", "finance", "payroll",
        "settings", "staff", "goods", "products", "loyalty", "integrations",
        "pos", "cashbox", "warehouse", "warehouses", "online-booking",
        "online-record", "widget", "reports", "marketing", "sms",
        "employees", "services", "categories", "positions", "notifications",
        "rights", "access", "calendar", "dashboard", "payment-methods",
        "webforms", "accounts", "cash-registers", "abonements",
    ]
    working = {}
    for section in sections:
        url = f"https://app.alteg.io/{section}/{COMPANY_ID}/"
        try:
            page.goto(url, wait_until="networkidle", timeout=8000)
            page.wait_for_timeout(500)
            body = page.evaluate("() => document.body.innerText.slice(0, 300)")
            is_404 = "Not found" in body or "не существует" in body
            ok = "✓" if not is_404 else "✗"
            final = page.url
            print(f"    {ok} /{section}/{COMPANY_ID}/ → {final[:80]}")
            if not is_404:
                working[section] = final
        except Exception as e:
            print(f"    ✗ /{section}/ — {type(e).__name__}")

    # Save results
    (OUT / "discovered_urls.json").write_text(json.dumps(working, indent=2, ensure_ascii=False))
    print(f"\n✅ Working sections saved to output/discovered_urls.json")
    print(f"\n━━━ Working URLs ━━━")
    for k, v in working.items():
        print(f"  {k:25s} → {v}")

    browser.close()
