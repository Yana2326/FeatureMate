"""
Find the language selector in cabinet/info and document its URL/selector.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
OUT      = Path("output/url_verify")
OUT.mkdir(parents=True, exist_ok=True)


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--lang=en-US"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    page = ctx.new_page()

    print("── Login ──")
    page.goto("https://app.alteg.io", wait_until="networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Close Adyen modal if present
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    # Go to cabinet/info
    page.goto("https://app.alteg.io/cabinet/info/", wait_until="networkidle")
    page.wait_for_timeout(3000)

    # Dismiss modals
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    for label in ["Посмотрю позже", "Посмотреть позже", "View later", "Later", "Close"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=400):
                btn.click()
                page.wait_for_timeout(400)
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
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "cabinet_info_clean.png"))

    # Look for language elements
    print("\n── Language-related elements ──")
    lang_els = page.evaluate("""() => {
        const matches = [];
        // Look for any element containing 'язык', 'language', 'english', 'русский'
        for (const el of document.querySelectorAll('*')) {
            const txt = (el.textContent || '').slice(0, 150);
            const hasLang = /язык|language|English|Русский|English|Русский/i.test(txt);
            if (hasLang && txt.length < 200) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && r.width < 500) {
                    matches.push({
                        tag: el.tagName,
                        cls: (el.className || '').slice(0, 60),
                        text: txt.trim().replace(/\\s+/g, ' '),
                        x: Math.round(r.x), y: Math.round(r.y)
                    });
                }
            }
        }
        // Dedupe by y coordinate
        const seen = new Set();
        return matches.filter(m => {
            const key = m.y + '|' + m.text.slice(0, 30);
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        }).slice(0, 30);
    }""")
    for m in lang_els:
        print(f"  y={m['y']:4d} x={m['x']:4d} {m['tag']}.{m['cls'][:40]:40s} | {m['text'][:80]}")

    # Check all tabs in cabinet
    print("\n── Cabinet tabs/menu items ──")
    tabs = page.evaluate("""() => {
        return [...document.querySelectorAll('a[href*="/cabinet/"], [role="tab"]')]
            .filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            })
            .map(el => ({
                href: el.href || '',
                text: (el.textContent || '').trim().slice(0, 60),
                x: Math.round(el.getBoundingClientRect().x),
                y: Math.round(el.getBoundingClientRect().y)
            }));
    }""")
    for t in tabs:
        print(f"  y={t['y']:4d} x={t['x']:4d} | {t['text'][:40]:40s} | {t['href']}")

    # Explore cabinet subsections
    print("\n── Test cabinet/* URLs ──")
    for path in ["/cabinet/info/", "/cabinet/settings/", "/cabinet/language/",
                 "/cabinet/personal/", "/cabinet/security/", "/cabinet/notifications/"]:
        url = f"https://app.alteg.io{path}"
        try:
            page.goto(url, wait_until="networkidle", timeout=8000)
            page.wait_for_timeout(800)
            body = page.evaluate("() => document.body.innerText.slice(0, 300)")
            is_404 = "Not found" in body or "не существует" in body or "не найден" in body
            has_lang = "язык" in body.lower() or "language" in body.lower()
            print(f"  {'✓' if not is_404 else '✗'} {'+lang' if has_lang else '     '} {path:30s} → {page.url}")
        except Exception as e:
            print(f"  ✗ {path:30s} — {type(e).__name__}")

    browser.close()
print("\n✅ Done.")
