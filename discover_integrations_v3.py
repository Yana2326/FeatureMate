"""
v3 — extract integration data using the working DOM-walking approach.
Visits the overview page + each category page, extracts every integration card.
"""

import json
import os
import re
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

CATEGORIES = [
    ("main",                 "Main",               f"{BASE_URL}/appstore/{COMPANY_ID}/applications/overview/"),
    ("payment_systems",      "Payment systems",    f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=11"),
    ("analytics",            "Analytics",          f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=13"),
    ("loyalty",              "Loyalty",            f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=14"),
    ("crm",                  "CRM",                f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=10"),
    ("telephony",            "Telephony",          f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=15"),
    ("fiscal_documents",     "Fiscal documents",   f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=23"),
    ("notifications",        "Notifications",      f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=1"),
    ("promotion",            "Promotion",          f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=7"),
    ("client_acquisition",   "Client acquisition", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category_id=4"),
    ("installed",            "Installed",          f"{BASE_URL}/appstore/{COMPANY_ID}/applications/installed"),
]


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
            const st = getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;
            const z = parseInt(st.zIndex) || 0;
            if (z < 50) continue;
            const r = el.getBoundingClientRect();
            if (r.width > 300 && r.height > 200
                && (st.position === 'fixed' || st.position === 'absolute')) el.remove();
        }
    }""")
    page.wait_for_timeout(300)


# Walk all elements with image+text and extract integration card data.
SCRAPE_JS = """
() => {
    const results = [];
    // Cards typically: link with image + text containing "From XX €/mth", "Free", or "Freemium"
    const links = [...document.querySelectorAll('a[href*="/applications/"]')];
    const seen = new Set();
    for (const a of links) {
        const href = a.href;
        // Match individual app pages: /applications/123
        const idMatch = href.match(/\\/applications\\/(\\d+)/);
        if (!idMatch) continue;
        const id = idMatch[1];
        if (seen.has(id)) continue;
        seen.add(id);

        const text = a.textContent.replace(/\\s+/g, ' ').trim();
        const img = a.querySelector('img');
        const rect = a.getBoundingClientRect();

        // Detect status
        let status = null;
        for (const s of ['Connected', 'Suspended', 'Pending', 'Coming soon']) {
            if (text.startsWith(s)) { status = s; break; }
        }

        // Detect price
        let price = 'Unknown';
        const priceMatch = text.match(/(Freemium|Free|From [^,)]+?\\/mth|From [^,)]+?\\/yr)/);
        if (priceMatch) price = priceMatch[1];

        results.push({
            id,
            href: href.split('?')[0],
            full_text: text.slice(0, 300),
            logo_alt: img ? img.alt : '',
            status,
            price,
            position: {x: Math.round(rect.x), y: Math.round(rect.y)},
        });
    }
    return results;
}
"""


discovery = {
    "categories": [],
    "by_category": {},
    "all_apps_unique": [],
    "section_counts": {},
}

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=["--lang=en-US", "--disable-features=Translate,TranslateUI", "--no-sandbox"]
    )
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    page = ctx.new_page()

    # Login
    print("══ Login ══")
    page.goto(BASE_URL, wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)

    seen_apps = {}

    for slug, name, url in CATEGORIES:
        print(f"\n── {name} ({slug}) ──")
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(2500)
        nuke_overlays(page)

        # Scroll to bottom to load lazy items
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1200)
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(500)

        cards = page.evaluate(SCRAPE_JS)
        print(f"   Cards: {len(cards)}")

        # Get section counts (only meaningful on overview page)
        if slug == "main":
            section_data = page.evaluate("""() => {
                // Find category section headers like "Notifications See all (12)"
                const sections = [];
                for (const el of document.querySelectorAll('div, section')) {
                    const text = el.textContent.replace(/\\s+/g, ' ').trim();
                    const m = text.match(/^([A-Z][a-zA-Z ]{1,30}?)See all \\((\\d+)\\)/);
                    if (m && !sections.find(s => s.label === m[1])) {
                        sections.push({label: m[1].trim(), count: parseInt(m[2])});
                    }
                }
                return sections;
            }""")
            for sd in section_data:
                discovery["section_counts"][sd["label"]] = sd["count"]
                print(f"     SECTION: {sd['label']}: {sd['count']} apps")

        for c in cards:
            print(f"     [{c.get('status') or '-'}] [{c.get('price')}] {c.get('logo_alt') or c.get('full_text','')[:60]}")
            if c['id'] not in seen_apps:
                seen_apps[c['id']] = dict(c, categories=[name])
            else:
                if name not in seen_apps[c['id']]['categories']:
                    seen_apps[c['id']]['categories'].append(name)

        discovery["by_category"][slug] = {
            "url": url,
            "name": name,
            "card_count": len(cards),
            "cards": cards,
        }
        discovery["categories"].append({"slug": slug, "name": name, "url": url})

    discovery["all_apps_unique"] = list(seen_apps.values())
    browser.close()

with open(OUT_DIR / "discovery.json", "w", encoding="utf-8") as f:
    json.dump(discovery, f, indent=2, ensure_ascii=False)

print(f"\n══ SUMMARY ══")
print(f"Categories visited: {len(discovery['categories'])}")
print(f"Unique apps found:  {len(discovery['all_apps_unique'])}")
print(f"Section counts:")
for label, count in discovery["section_counts"].items():
    print(f"  {label}: {count}")
