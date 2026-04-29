"""
Focused discovery script — only visits the 9 actual categories.
Re-captures missing screenshots and writes discovery.json.
Uses isolated headless Chromium (per CLAUDE.md SECURITY RULE).
"""

import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, Page


def _load_env():
    env_path = Path(__file__).parent / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

_load_env()

EMAIL      = os.environ["ALTEGIO_EMAIL"]
PASSWORD   = os.environ["ALTEGIO_PASSWORD"]
COMPANY_ID = "1253779"
BASE_URL   = "https://app.alteg.io"

OUT_DIR    = Path("output/integrations-overview")
SHOTS_DIR  = OUT_DIR / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

# 9 actual categories (URL pattern from earlier discovery)
CATEGORIES = [
    ("main",                 f"{BASE_URL}/appstore/{COMPANY_ID}/applications/overview/"),
    ("payment_systems",      f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=11"),
    ("analytics",            f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=13"),
    ("loyalty",              f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=14"),
    ("crm",                  f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=10"),
    ("telephony",            f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=15"),
    ("fiscal_documents",     f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=23"),
    ("notifications",        f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=1"),
    ("promotion",            f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=7"),
    ("client_acquisition",   f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=4"),
    ("installed",            f"{BASE_URL}/appstore/{COMPANY_ID}/applications/installed"),
]


def shot(page: Page, name: str, full_page=False) -> str:
    path = str(SHOTS_DIR / name)
    page.screenshot(path=path, full_page=full_page)
    print(f"  📸 {name}")
    return path


def nuke_overlays(page: Page) -> None:
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    for label in ["Not now", "View later", "Later", "Skip", "Close",
                  "Посмотрю позже", "Посмотреть позже"]:
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
            const st = getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;
            const z = parseInt(st.zIndex) || 0;
            if (z < 50) continue;
            const r = el.getBoundingClientRect();
            if (r.width > 300 && r.height > 200
                && (st.position === 'fixed' || st.position === 'absolute')) el.remove();
        }
        for (const sel of ['[class*="tooltip"]','[class*="q-tooltip"]',
                           '[class*="popover"]','[class*="hint"]','[class*="tour"]']) {
            for (const el of document.querySelectorAll(sel))
                if (el.isConnected) el.style.display = 'none';
        }
    }""")
    page.wait_for_timeout(300)


def scrape_integration_cards(page: Page) -> list:
    """Extract integration cards from a category page."""
    return page.evaluate("""() => {
        // Look for cards in main content area
        const main = document.querySelector('main, [class*="content"], [class*="main"]') || document.body;
        // Try to find integration cards by their typical structure
        const cards = [...main.querySelectorAll('a[href*="/applications/"]')].filter(a => {
            const href = a.href;
            // Only individual-app links
            return /\\/applications\\/\\d+/.test(href);
        });

        const seen = new Set();
        const results = [];
        for (const a of cards) {
            const href = a.href.split('?')[0];  // strip utm params for dedup
            if (seen.has(href)) continue;
            seen.add(href);

            const text = a.textContent.trim().replace(/\\s+/g, ' ');
            const img = a.querySelector('img');
            const rect = a.getBoundingClientRect();

            // Extract status badge ("Connected", "Suspended") — usually first words
            let status = null;
            for (const s of ['Connected', 'Suspended', 'Pending', 'Coming soon']) {
                if (text.startsWith(s)) {
                    status = s;
                    break;
                }
            }

            // Extract price marker
            let price = null;
            const priceMatch = text.match(/(Free|Freemium|From\\s+[\\d.]+\\s*[€$]\\/mth)/);
            if (priceMatch) price = priceMatch[1];

            // App ID from URL
            const idMatch = href.match(/\\/applications\\/(\\d+)/);

            results.push({
                href,
                id: idMatch ? idMatch[1] : null,
                full_text: text.slice(0, 250),
                logo_alt: img ? img.alt : '',
                logo_src: img ? img.src : '',
                status,
                price,
                visible: rect.width > 0 && rect.height > 0,
                position: {x: Math.round(rect.x), y: Math.round(rect.y)},
            });
        }
        return results;
    }""")


def get_page_meta(page: Page) -> dict:
    """Get page metadata: title, description, count."""
    return page.evaluate("""() => {
        // Try to find category title
        const headings = [...document.querySelectorAll('h1,h2,h3')]
            .map(h => h.textContent.trim())
            .filter(t => t.length > 0 && t.length < 100);

        // Look for "See all (N)" patterns to count category sizes
        const seeAlls = [];
        for (const el of document.querySelectorAll('a, span, div')) {
            const t = el.textContent.trim();
            const m = t.match(/^See all \\((\\d+)\\)$/);
            if (m) seeAlls.push({text: t, count: parseInt(m[1]), context: el.parentElement?.textContent.trim().slice(0, 80)});
        }

        // Section labels (category headers when on overview page)
        const sectionHeaders = [];
        for (const el of document.querySelectorAll('div, section, h3, h4')) {
            const t = el.textContent.trim();
            // Match "Notifications See all (12)" patterns
            const m = t.match(/^([A-Z][A-Za-z ]+)\\s*See all \\((\\d+)\\)/);
            if (m && m[1].length < 30) sectionHeaders.push({label: m[1].trim(), count: parseInt(m[2])});
        }

        return {
            url: window.location.href,
            title: document.title,
            headings,
            see_alls: seeAlls.slice(0, 20),
            section_counts: sectionHeaders,
        };
    }""")


discovery = {
    "categories": [],
    "by_category": {},
    "all_apps": [],
    "section_counts": {},
}

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--lang=en-US",
            "--disable-features=Translate,TranslateUI",
            "--no-sandbox",
        ]
    )
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="en-US",
    )
    page = ctx.new_page()

    print("══ Login ══")
    page.goto(BASE_URL, wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")

    # ── Visit each category ──
    print("\n══ Visit categories ══")
    seen_apps = {}

    for slug, url in CATEGORIES:
        print(f"\n── {slug} ──")
        print(f"   URL: {url}")
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(2500)
        nuke_overlays(page)

        # Scroll to load any lazy items
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(800)
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(500)

        # Screenshot
        shot_name = f"03_cat_{slug}.png"
        shot(page, shot_name)

        # Full-page version for the main overview
        if slug == "main":
            shot(page, f"03_cat_{slug}_full.png", full_page=True)

        meta = get_page_meta(page)
        cards = scrape_integration_cards(page)
        print(f"   Cards: {len(cards)}")
        for c in cards:
            name = c.get('logo_alt', '') or c.get('full_text','')[:50]
            print(f"     [{c.get('status') or c.get('price') or '-'}] {name}")
            # Dedup across categories
            if c['id'] and c['id'] not in seen_apps:
                seen_apps[c['id']] = c.copy()
                seen_apps[c['id']]['categories'] = [slug]
            elif c['id']:
                seen_apps[c['id']]['categories'].append(slug)

        discovery["by_category"][slug] = {
            "url": url,
            "screenshot": shot_name,
            "meta": meta,
            "cards": cards,
        }

    # ── Capture section counts from overview page ──
    print("\n══ Section counts from overview ══")
    page.goto(f"{BASE_URL}/appstore/{COMPANY_ID}/applications/overview/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    overview_meta = get_page_meta(page)
    for sc in overview_meta.get("section_counts", []):
        discovery["section_counts"][sc["label"]] = sc["count"]
        print(f"   {sc['label']}: {sc['count']} apps")

    discovery["all_apps"] = list(seen_apps.values())
    discovery["categories"] = [slug for slug, _ in CATEGORIES]

    browser.close()

# ── Save ──
with open(OUT_DIR / "discovery.json", "w", encoding="utf-8") as f:
    json.dump(discovery, f, indent=2, ensure_ascii=False)
print(f"\n✓ Saved discovery.json")
print(f"  Categories: {len(discovery['categories'])}")
print(f"  Unique apps: {len(discovery['all_apps'])}")
print(f"  Screenshots: {len(list(SHOTS_DIR.glob('*.png')))}")
