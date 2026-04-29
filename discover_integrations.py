"""
Discover all integrations in Altegio's Integrations Marketplace.
Uses headless Chromium — does NOT touch personal Chrome.
Saves screenshots to output/integrations-overview/screenshots/
Saves discovery data to output/integrations-overview/discovery.json
"""

import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# Load credentials from .env (per CLAUDE.md SECURITY RULE — isolated browser only)
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
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


# ── Helpers ─────────────────────────────────────────────────────────────────

def shot(page: Page, name: str) -> str:
    path = str(SHOTS_DIR / name)
    page.screenshot(path=path, full_page=False)
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


def switch_language_to_english(page: Page) -> bool:
    """Switch Altegio UI to English. Returns True if verified."""
    page.goto(f"{BASE_URL}/cabinet/info/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page)

    current = page.evaluate("() => document.querySelector('#user_lang')?.value")
    print(f"  Current language value: {current}")
    if current == "2":
        print("  ✓ Already English")
        return True

    page.select_option("#user_lang", value="2")
    page.evaluate("""() => {
        document.querySelector('#user_lang')
            .dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    page.wait_for_timeout(500)

    # Click the correct "Save changes" button
    page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button, input[type="submit"], a.btn')];
        const btn = btns.find(b => /изменить данные|save changes|update profile|update data/i
            .test(b.textContent || b.value || ''));
        if (btn) { console.log('Clicking: ' + btn.textContent); btn.click(); }
        else console.log('Save button not found');
    }""")
    page.wait_for_timeout(5000)

    page.goto(f"{BASE_URL}/cabinet/info/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    result = page.evaluate("() => document.querySelector('#user_lang')?.value") == "2"
    print(f"  Language switch result: {'✓ English' if result else '✗ Failed'}")
    return result


def scrape_integrations_on_page(page: Page) -> list:
    """Extract integration cards from the current page."""
    cards = page.evaluate("""() => {
        const results = [];
        // Try multiple card selectors
        const selectors = [
            '[class*="application-card"]',
            '[class*="app-card"]',
            '[class*="integration-card"]',
            '[class*="appstore-item"]',
            '.b-appstore__item',
            '[class*="marketplace-item"]',
        ];

        let found = [];
        for (const sel of selectors) {
            found = [...document.querySelectorAll(sel)];
            if (found.length > 0) break;
        }

        // Fallback: any element with an image and a heading
        if (found.length === 0) {
            found = [...document.querySelectorAll('[class*="item"], [class*="card"]')].filter(el => {
                return el.querySelector('img') &&
                       (el.querySelector('h2,h3,h4,[class*="title"],[class*="name"]'));
            });
        }

        for (const card of found) {
            const nameEl = card.querySelector('h2,h3,h4,[class*="title"],[class*="name"],[class*="heading"]');
            const descEl = card.querySelector('[class*="desc"],[class*="text"],[class*="subtitle"],p');
            const linkEl = card.querySelector('a') || card.closest('a');
            const imgEl  = card.querySelector('img');
            const btnEl  = card.querySelector('button,[class*="btn"]');

            results.push({
                name: nameEl ? nameEl.textContent.trim() : '',
                description: descEl ? descEl.textContent.trim().slice(0, 200) : '',
                link: linkEl ? linkEl.href : '',
                logo: imgEl ? imgEl.src : '',
                button_text: btnEl ? btnEl.textContent.trim() : '',
                classes: card.className.slice(0, 100),
            });
        }
        return results;
    }""")
    return cards


def scrape_page_text_structure(page: Page) -> dict:
    """Get the full text structure of the page for analysis."""
    return page.evaluate("""() => {
        // Get sidebar categories
        const sidebar = [];
        const sidebarEls = [...document.querySelectorAll(
            '[class*="sidebar"] a, [class*="filter"] a, [class*="category"] a, nav a, .aside a'
        )].filter(el => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        });
        for (const el of sidebarEls) {
            sidebar.push({
                text: el.textContent.trim(),
                href: el.href,
                active: el.classList.contains('active') ||
                        el.getAttribute('aria-current') === 'page' ||
                        el.parentElement?.classList.contains('active')
            });
        }

        // Get all headings
        const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5')].map(h => ({
            tag: h.tagName,
            text: h.textContent.trim()
        }));

        // Get integration count if shown
        const countEl = document.querySelector('[class*="count"], [class*="total"]');

        return {
            sidebar,
            headings,
            count: countEl ? countEl.textContent.trim() : null,
            url: window.location.href,
            title: document.title,
        };
    }""")


def get_all_integration_cards(page: Page) -> list:
    """More thorough card scraping using multiple strategies."""
    return page.evaluate("""() => {
        const results = [];

        // Strategy 1: Look for application/integration cards by class patterns
        const cardPatterns = [
            '[class*="application"]',
            '[class*="integration"]',
            '[class*="appstore"]',
            '[class*="marketplace"]',
            '[class*="plugin"]',
            '[class*="connector"]',
        ];

        let cards = [];
        for (const pattern of cardPatterns) {
            const found = [...document.querySelectorAll(pattern)].filter(el => {
                const r = el.getBoundingClientRect();
                const hasImage = el.querySelector('img') != null;
                const hasText = el.textContent.trim().length > 5;
                return r.width > 80 && r.height > 80 && hasImage && hasText;
            });
            if (found.length > cards.length) cards = found;
        }

        // Strategy 2: List items with images in the main content
        if (cards.length === 0) {
            const main = document.querySelector('main, [class*="content"], [class*="main"], [role="main"]');
            if (main) {
                cards = [...main.querySelectorAll('li, [class*="item"]')].filter(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 80 && r.height > 60 && el.querySelector('img');
                });
            }
        }

        for (const card of cards) {
            const rect = card.getBoundingClientRect();
            // Skip tiny/hidden items
            if (rect.width < 50 || rect.height < 50) continue;

            const textNodes = [];
            const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
            let node;
            while (node = walker.nextNode()) {
                const t = node.textContent.trim();
                if (t.length > 1) textNodes.push(t);
            }

            const allText = textNodes.join(' | ').slice(0, 300);
            const linkEl = card.querySelector('a') || card.closest('a');
            const imgEl = card.querySelector('img');
            const btnEl = card.querySelector('button');

            results.push({
                text_content: allText,
                link: linkEl ? linkEl.href : '',
                logo_src: imgEl ? imgEl.src : '',
                logo_alt: imgEl ? imgEl.alt : '',
                button: btnEl ? btnEl.textContent.trim() : '',
                tag: card.tagName,
                class: card.className.slice(0, 120),
                rect: {x: Math.round(rect.x), y: Math.round(rect.y),
                       w: Math.round(rect.width), h: Math.round(rect.height)}
            });
        }

        return results;
    }""")


# ── Main discovery ───────────────────────────────────────────────────────────

discovery = {
    "categories": [],
    "all_integrations": [],
    "raw_pages": {}
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

    # ── Step 1: Login ────────────────────────────────────────────────────────
    print("\n══ Step 1: Login ══")
    page.goto(BASE_URL, wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL after login: {page.url}")
    shot(page, "01_login.png")

    # ── Step 2: Switch to English ────────────────────────────────────────────
    print("\n══ Step 2: Switch to English ══")
    ok = switch_language_to_english(page)
    if not ok:
        print("  ⚠️  Language switch failed — continuing anyway")

    # ── Step 3: Navigate to Integrations marketplace ─────────────────────────
    print("\n══ Step 3: Navigate to Integrations ══")
    integ_url = f"{BASE_URL}/appstore/{COMPANY_ID}/applications/overview/"
    page.goto(integ_url, wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")

    shot(page, "02_integrations_main.png")

    # Get page structure
    structure = scrape_page_text_structure(page)
    print(f"\n  Page title: {structure.get('title')}")
    print(f"\n  Sidebar categories ({len(structure.get('sidebar', []))}):")
    for item in structure.get('sidebar', []):
        print(f"    {'[ACTIVE] ' if item.get('active') else '         '}{item.get('text')} → {item.get('href','')}")

    print(f"\n  Headings:")
    for h in structure.get('headings', []):
        print(f"    {h['tag']}: {h['text']}")

    # Store categories
    sidebar_categories = structure.get('sidebar', [])
    discovery["categories"] = sidebar_categories

    # Get main page integrations
    main_cards = get_all_integration_cards(page)
    print(f"\n  Cards found on main page: {len(main_cards)}")
    for card in main_cards[:10]:
        print(f"    [{card.get('logo_alt','?')}] {card.get('text_content','')[:80]}")

    discovery["raw_pages"]["overview"] = {
        "url": page.url,
        "structure": structure,
        "cards": main_cards
    }

    # ── Step 4: Visit each category ──────────────────────────────────────────
    print("\n══ Step 4: Visit each category ══")

    # First, collect all sidebar links by reading the DOM directly
    sidebar_links = page.evaluate("""() => {
        // Get all sidebar/filter links
        const links = [...document.querySelectorAll('a')].filter(a => {
            const r = a.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && a.href &&
                   (a.href.includes('category') || a.href.includes('appstore'));
        }).map(a => ({
            text: a.textContent.trim(),
            href: a.href,
            x: Math.round(a.getBoundingClientRect().x),
            y: Math.round(a.getBoundingClientRect().y),
        }));
        return links;
    }""")

    print(f"\n  All category links found: {len(sidebar_links)}")
    for link in sidebar_links:
        print(f"    [{link.get('x')},{link.get('y')}] {link.get('text')} → {link.get('href','')}")

    # Determine categories to visit
    # Use sidebar links from the page, or fall back to known categories
    categories_to_visit = []
    seen_hrefs = set()
    for link in sidebar_links:
        href = link.get('href', '')
        text = link.get('text', '')
        if href and href not in seen_hrefs and text:
            categories_to_visit.append({"name": text, "url": href})
            seen_hrefs.add(href)

    # Also try known category URLs directly
    known_categories = [
        ("Main", f"{BASE_URL}/appstore/{COMPANY_ID}/applications/overview/"),
        ("Payment systems", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=payment_systems"),
        ("Analytics", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=analytics"),
        ("Loyalty", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=loyalty"),
        ("CRM", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=crm"),
        ("Telephony", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=telephony"),
        ("Fiscal documents", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=fiscal_documents"),
        ("Notifications", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=notifications"),
        ("Promotion", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=promotion"),
        ("Client acquisition", f"{BASE_URL}/appstore/{COMPANY_ID}/applications?category=client_acquisition"),
    ]

    if not categories_to_visit:
        print("  No category links found in DOM, using known category URLs")
        categories_to_visit = [{"name": n, "url": u} for n, u in known_categories]

    all_integrations = []
    category_data = {}

    for i, cat in enumerate(categories_to_visit):
        cat_name = cat.get("name", f"Category {i}")
        cat_url  = cat.get("url", "")
        print(f"\n  ── Category: {cat_name} ──")
        print(f"     URL: {cat_url}")

        page.goto(cat_url, wait_until="networkidle")
        page.wait_for_timeout(2500)
        nuke_overlays(page)

        # Scroll to load lazy content
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(500)

        # Screenshot
        slug = cat_name.lower().replace(" ", "_").replace("/", "_")
        shot_name = f"03_{i:02d}_cat_{slug}.png"
        shot(page, shot_name)

        # Get structure and cards
        cat_structure = scrape_page_text_structure(page)
        cat_cards = get_all_integration_cards(page)

        print(f"     Cards found: {len(cat_cards)}")
        for card in cat_cards:
            name = card.get('logo_alt') or card.get('text_content','')[:40]
            print(f"       • {name}")

        # Also get raw text to help identify integrations
        raw_text = page.evaluate("""() => {
            const main = document.querySelector('main,[class*="content"],[role="main"]') || document.body;
            return main.innerText.slice(0, 3000);
        }""")

        category_data[cat_name] = {
            "url": cat_url,
            "screenshot": shot_name,
            "cards": cat_cards,
            "headings": cat_structure.get("headings", []),
            "raw_text": raw_text,
        }

        for card in cat_cards:
            card["category"] = cat_name
        all_integrations.extend(cat_cards)

    # ── Step 5: Take full-page screenshots of key pages ─────────────────────
    print("\n══ Step 5: Return to overview for full screenshot ══")
    page.goto(integ_url, wait_until="networkidle")
    page.wait_for_timeout(2000)
    nuke_overlays(page)

    # Full-page screenshot
    page.screenshot(path=str(SHOTS_DIR / "02_integrations_overview_full.png"), full_page=True)
    print("  📸 02_integrations_overview_full.png (full page)")

    # ── Step 6: Re-visit each category for clean screenshots ────────────────
    print("\n══ Step 6: Clean screenshots of each category ══")
    clean_categories = [
        ("main", f"{BASE_URL}/appstore/{COMPANY_ID}/applications/overview/", "overview"),
    ]

    # Try to get categories from the sidebar now that we're on the page
    final_sidebar = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].filter(a => {
            const r = a.getBoundingClientRect();
            const text = a.textContent.trim();
            return r.width > 0 && r.height > 0 && text.length > 1 && text.length < 50;
        }).filter(a => {
            // Likely sidebar category items
            const x = a.getBoundingClientRect().x;
            return x < 300;  // left side of page
        }).map(a => ({
            text: a.textContent.trim(),
            href: a.href,
        }));
    }""")

    print(f"\n  Left-side links (categories): {len(final_sidebar)}")
    for link in final_sidebar:
        print(f"    {link.get('text')} → {link.get('href','')}")

    discovery["all_integrations"] = all_integrations
    discovery["category_data"] = category_data
    discovery["sidebar_links"] = sidebar_links
    discovery["final_sidebar"] = final_sidebar

    browser.close()
    print("\n  Browser closed.")


# ── Save discovery data ──────────────────────────────────────────────────────
print("\n══ Saving discovery data ══")
with open(OUT_DIR / "discovery.json", "w", encoding="utf-8") as f:
    json.dump(discovery, f, indent=2, ensure_ascii=False)
print(f"  Saved: {OUT_DIR}/discovery.json")

# Summary
print(f"\n══ Discovery Summary ══")
print(f"  Categories found: {len(discovery.get('categories', []))}")
print(f"  Category data:    {len(discovery.get('category_data', {}))}")
print(f"  Total cards:      {len(discovery.get('all_integrations', []))}")
print(f"  Screenshots:      {len(list(SHOTS_DIR.glob('*.png')))}")
