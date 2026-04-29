"""
Find the correct Finance → Payment Methods URL by navigating directly
to the /location/{id}/ Administration mode URL.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
OUT      = Path("output/payment-methods/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

VW, VH = 1440, 900
COMPANY_ID = "1253779"


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / name))
    print(f"  📸 {name}")


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
    browser = pw.chromium.launch(
        headless=False,
        args=["--lang=en-US"],
    )
    ctx = browser.new_context(
        viewport={"width": VW, "height": VH},
        locale="en-US",
    )
    page = ctx.new_page()

    # ── Login ──
    print("── Login ──")
    page.goto("https://app.alteg.io", wait_until="networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")

    # ── Navigate directly to Administration mode ──
    print("\n── Navigate directly to /location/{id}/ (Admin mode) ──")
    page.goto(f"https://app.alteg.io/location/{COMPANY_ID}/",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")
    shot(page, "_admin2_01_location.png")

    # Dump all visible links
    links = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].filter(a => {
            const r = a.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }).map(a => ({href: a.href, text: a.textContent.trim().slice(0, 80)}));
    }""")
    print(f"  Visible links ({len(links)}):")
    for l in links[:30]:
        print(f"    {l.get('href','')}  |  {l.get('text','')}")

    # ── Try Force-clicking the hidden /location/{id}/ link ──
    print("\n── Force-click hidden location link ──")
    try:
        # Use JS to navigate directly
        page.evaluate(f"window.location.href = 'https://app.alteg.io/location/{COMPANY_ID}/'")
        page.wait_for_load_state("networkidle", timeout=20000)
        page.wait_for_timeout(3000)
        print(f"  URL after JS navigate: {page.url}")
        shot(page, "_admin2_02_after_js_nav.png")
    except Exception as e:
        print(f"  JS navigate failed: {e}")

    # Dump links again
    links2 = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].filter(a => {
            const r = a.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }).map(a => ({href: a.href, text: a.textContent.trim().slice(0, 80)}));
    }""")
    print(f"  Visible links after nav ({len(links2)}):")
    for l in links2[:30]:
        print(f"    {l.get('href','')}  |  {l.get('text','')}")

    # Look for Finance in all text
    page_text = page.evaluate("() => document.body.innerText.slice(0, 2000)")
    print(f"\n  Page text:\n{page_text}")

    # ── Try Finance click ──
    print("\n── Try Finance ──")
    for sel in [
        "text=Finance", "text=Финансы",
        "a:has-text('Finance')", "a:has-text('Финансы')",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click()
                page.wait_for_timeout(1500)
                page.wait_for_load_state("networkidle")
                print(f"  ✓ Finance: {sel} → {page.url}")
                shot(page, "_admin2_03_finance.png")

                # Now dump links in finance
                fin_links = page.evaluate("""() => {
                    return [...document.querySelectorAll('a')].filter(a => {
                        const r = a.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    }).map(a => ({href: a.href, text: a.textContent.trim().slice(0, 80)}));
                }""")
                print(f"  Finance links ({len(fin_links)}):")
                for l in fin_links[:20]:
                    print(f"    {l.get('href','')}  |  {l.get('text','')}")
                break
        except Exception:
            pass

    # ── Try Payment Methods ──
    print("\n── Try Payment Methods ──")
    for sel in [
        "text=Payment methods",
        "text=Платёжные методы",
        "text=Платежные методы",
        "a[href*='payment']",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click()
                page.wait_for_timeout(1500)
                page.wait_for_load_state("networkidle")
                print(f"  ✓ Payment methods: {sel} → {page.url}")
                shot(page, "_admin2_04_payment_methods.png")
                break
        except Exception:
            pass

    print(f"\n  Final URL: {page.url}")
    page_text2 = page.evaluate("() => document.body.innerText.slice(0, 1000)")
    print(f"  Page text:\n{page_text2}")

    browser.close()
    print("\n✅ Done.")
