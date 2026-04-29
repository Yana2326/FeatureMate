"""
Map all Altegio section URLs by systematically clicking through every
menu item in both Digital Schedule and Administration modes.

Outputs:
  - output/url_map.json  — machine-readable
  - output/url_map.md    — human-readable markdown for CLAUDE.md
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL      = "yanabar2304@gmail.com"
PASSWORD   = "Yanatest23"
COMPANY_ID = "1253779"
OUT        = Path("output")
OUT.mkdir(parents=True, exist_ok=True)
DEBUG_DIR  = OUT / "url_map_debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

VW, VH = 1440, 900

# Results collector
urls: dict = {
    "digital_schedule": {},   # section_name -> url
    "administration":   {},   # section_name -> url
    "submenus":         {},   # section_name -> [(sub_name, sub_url)]
}


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(DEBUG_DIR / name))


def nuke_overlays(page: Page) -> None:
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    for label in ["Not now", "View later", "Later", "Skip", "Close", "×", "✕"]:
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
        // Tooltips
        for (const sel of ['[class*="tooltip"]','[class*="q-tooltip"]',
                           '[class*="popover"]','[class*="hint"]','[class*="tour"]']) {
            for (const el of document.querySelectorAll(sel)) {
                if (el.isConnected) el.style.display = 'none';
            }
        }
    }""")
    page.wait_for_timeout(300)


def login(page: Page) -> None:
    print("── Login ──")
    page.goto("https://app.alteg.io", wait_until="networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")


def get_sidebar_links(page: Page) -> list[dict]:
    """Extract all visible navigation links from the left sidebar."""
    return page.evaluate("""() => {
        const candidates = document.querySelectorAll(
            'nav a, [class*="sidebar"] a, [class*="side-menu"] a, ' +
            '[class*="nav-menu"] a, aside a, [class*="left-menu"] a, ' +
            '[class*="menu-item"] a'
        );
        const seen = new Set();
        const out = [];
        for (const a of candidates) {
            const r = a.getBoundingClientRect();
            if (r.width < 5 || r.height < 5) continue;
            if (!a.href || a.href === '' || a.href === '#') continue;
            if (seen.has(a.href)) continue;
            seen.add(a.href);
            const text = (a.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
            out.push({href: a.href, text: text, rect: {x: r.x, y: r.y, w: r.width, h: r.height}});
        }
        return out;
    }""")


def dump_all_clickable(page: Page) -> list[dict]:
    """Find anything clickable in the sidebar that could be a menu item."""
    return page.evaluate("""() => {
        const cs = [...document.querySelectorAll(
            'a, [role="link"], [role="menuitem"], ' +
            '[class*="menu-item"], [class*="nav-item"], [class*="sidebar-item"]'
        )];
        const out = [];
        const seen = new Set();
        for (const el of cs) {
            const r = el.getBoundingClientRect();
            if (r.width < 5 || r.height < 5) continue;
            // Only left sidebar (x < 260)
            if (r.x > 260) continue;
            const text = (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
            if (!text) continue;
            const key = text + '|' + r.y;
            if (seen.has(key)) continue;
            seen.add(key);
            out.push({
                tag: el.tagName,
                href: el.href || null,
                text: text,
                cls: (el.className || '').slice(0, 80),
                rect: {x: r.x, y: r.y, w: r.width, h: r.height}
            });
        }
        return out.sort((a, b) => a.rect.y - b.rect.y);
    }""")


def explore_mode(page: Page, mode_name: str, start_url: str) -> None:
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Exploring mode: {mode_name}")
    print(f"  Start URL:      {start_url}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    page.goto(start_url, wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    shot(page, f"{mode_name}_00_home.png")
    print(f"  Home URL: {page.url}")

    # Get all clickable left-sidebar items
    items = dump_all_clickable(page)
    print(f"\n  Left sidebar items ({len(items)}):")
    for it in items:
        href = it.get('href') or '—'
        text = it.get('text', '')
        y = int(it.get('rect', {}).get('y', 0))
        print(f"    y={y:4d}  {text:40s}  {href}")

    # Click each unique text item to discover its URL
    seen_urls = set()
    for idx, it in enumerate(items):
        text = it.get('text', '').strip()
        if not text or len(text) < 2:
            continue
        # Skip numeric-only items
        if text.replace(' ', '').replace('.', '').replace(',', '').isdigit():
            continue
        # Skip if no meaningful text
        if len(text) < 3 and text not in ('+', '★'):
            continue

        # Return to home first
        page.goto(start_url, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1500)
        nuke_overlays(page)

        # Click by text
        try:
            # First try direct href click
            if it.get('href'):
                page.goto(it['href'], wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(1500)
                url_after = page.url
                if url_after not in seen_urls:
                    seen_urls.add(url_after)
                    key = text[:50]
                    urls.setdefault(mode_name, {})[key] = url_after
                    print(f"    ✓ [{idx}] {text[:40]:40s} → {url_after}")
                    shot(page, f"{mode_name}_{idx:02d}_{text[:20].replace('/','_')}.png")
                    # Collect submenu links if any
                    sub_links = page.evaluate("""() => {
                        const cs = [...document.querySelectorAll('a')];
                        const out = [];
                        const seen = new Set();
                        for (const el of cs) {
                            const r = el.getBoundingClientRect();
                            if (r.width < 5 || r.height < 5) continue;
                            if (r.x > 280) continue;  // sidebar only
                            if (!el.href || el.href.endsWith('#')) continue;
                            if (seen.has(el.href)) continue;
                            seen.add(el.href);
                            const text = (el.textContent||'').trim().slice(0, 60);
                            if (!text || text.length < 2) continue;
                            out.push({href: el.href, text: text});
                        }
                        return out;
                    }""")
                    if sub_links:
                        urls['submenus'].setdefault(key, [])
                        for sl in sub_links:
                            if sl['href'] != url_after:
                                urls['submenus'][key].append(sl)
        except Exception as e:
            print(f"    ✗ [{idx}] {text[:40]} — {e}")


def explore_admin_sections(page: Page) -> None:
    """Systematically visit each Administration menu section and sub-section."""
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Exploring Administration sub-sections")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Navigate to Admin home
    admin_url = f"https://app.alteg.io/location/{COMPANY_ID}/"
    page.goto(admin_url, wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  Admin home: {page.url}")
    shot(page, "admin_home.png")

    # Try candidate URL patterns for common admin sections
    candidates = [
        # Settings
        "/settings", "/settings/main", "/settings/services",
        "/settings/positions", "/settings/resources", "/settings/notifications",
        "/settings/users", "/settings/branches", "/settings/rights",
        # Team
        "/staff", "/staff/list", "/staff/schedule", "/staff/rights",
        "/employees", "/employees/list", "/employees/schedule",
        # Products
        "/goods", "/goods/list", "/goods/categories", "/goods/inventory",
        "/products", "/products/list", "/products/categories",
        "/warehouses", "/warehouse",
        # Finance
        "/finance", "/finance/accounts", "/finance/cash-registers",
        "/finance/payment-methods", "/finance/categories",
        # Loyalty
        "/loyalty", "/loyalty/programs", "/loyalty/certificates",
        "/loyalty/subscriptions", "/loyalty/abonements",
        # Online booking
        "/online-booking", "/online-booking/widget",
        "/widget", "/webforms", "/online-record",
        # Integrations
        "/integrations", "/marketplace", "/apps",
        # Schedule (Digital mode sections)
        "/timetable", "/timetable/#mode=0", "/timetable/#mode=1",
        "/clients", "/overview", "/analytics", "/payroll",
    ]

    # Test each candidate URL
    working_urls = {}
    for path in candidates:
        full_url = f"https://app.alteg.io/company/{COMPANY_ID}{path}"
        try:
            page.goto(full_url, wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1200)
            final_url = page.url
            # Check for "Not found"
            body_text = page.evaluate("() => document.body.innerText.slice(0, 500)")
            is_404 = "Not found" in body_text or "не существует" in body_text or "не найден" in body_text
            status = "✓" if not is_404 else "✗ (404)"
            print(f"    {status} {path:40s} → {final_url}")
            if not is_404:
                working_urls[path] = final_url
        except Exception as e:
            print(f"    ✗ {path:40s} — {type(e).__name__}")

    # Also try /location/ prefix
    print(f"\n  Try /location/{COMPANY_ID}/ prefix:")
    for path in candidates:
        full_url = f"https://app.alteg.io/location/{COMPANY_ID}{path}"
        try:
            page.goto(full_url, wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1200)
            final_url = page.url
            body_text = page.evaluate("() => document.body.innerText.slice(0, 500)")
            is_404 = "Not found" in body_text or "не существует" in body_text or "не найден" in body_text
            status = "✓" if not is_404 else "✗ (404)"
            print(f"    {status} {path:40s} → {final_url}")
            if not is_404 and path not in working_urls:
                working_urls[f"location{path}"] = final_url
        except Exception as e:
            print(f"    ✗ {path:40s} — {type(e).__name__}")

    urls['administration_urls_tested'] = working_urls


# ── Main ──────────────────────────────────────────────────────────────────────

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=["--lang=en-US"],
    )
    ctx = browser.new_context(
        viewport={"width": VW, "height": VH},
        locale="en-US",
    )
    page = ctx.new_page()

    login(page)

    # Explore Digital Schedule mode from timetable
    digital_home = f"https://app.alteg.io/timetable/{COMPANY_ID}/"
    explore_mode(page, "digital_schedule", digital_home)

    # Test candidate admin URLs
    explore_admin_sections(page)

    browser.close()

# Save results
(OUT / "url_map.json").write_text(json.dumps(urls, indent=2, ensure_ascii=False))
print(f"\n✅ Saved to {OUT / 'url_map.json'}")

# Print summary
print("\n━━━━━ SUMMARY ━━━━━")
for mode, items in urls.items():
    if isinstance(items, dict) and items:
        print(f"\n{mode}:")
        for k, v in items.items():
            print(f"  {k:40s} → {v}")
