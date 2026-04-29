"""
Verify discovered URLs work, find language settings, and save screenshots
for validation.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL      = "yanabar2304@gmail.com"
PASSWORD   = "Yanatest23"
COMPANY_ID = "1253779"
OUT        = Path("output/url_verify")
OUT.mkdir(parents=True, exist_ok=True)


# All discovered URLs to verify
URLS = {
    # Digital Schedule mode
    "timetable":                 "/timetable/{id}/",
    "timetable_admin_mode":      "/timetable/{id}/#mode=0",
    "timetable_schedule_mode":   "/timetable/{id}/#mode=1",
    "clients_base":              "/clients/{id}/base/",
    "client_categories":         "/labels/client/{id}/",
    "client_loyalty":            "/clients_settings/discounts/{id}/",
    "dashboard":                 "/dashboard/{id}/",
    "dashboard_records":         "/dashboard_records/{id}/",
    "dashboard_activities":      "/dashboard/activities/{id}/",
    "dashboard_all_reports":     "/dashboard/all_reports/{id}/",
    "analytics":                 "/analytics/{id}/",

    # Finance
    "finance_transactions":      "/finances/transactions/list/{id}/",
    "finance_accounts":          "/finances/accounts/list/{id}/",
    "finance_suppliers":         "/finances/suppliers/list/{id}/",
    "finance_expenses":          "/finances/expenses/list/{id}/",
    "finance_documents":         "/documents/{id}/",
    "finance_acquiring":         "/finances/acquiring/{id}/payment_methods/",
    "finance_payment_methods":   "/finances/payment_methods_settings/{id}/",
    "finance_reports":           "/analytics/reports/{id}/reports_finances/",
    "finance_settings":          "/settings/menu/{id}/setting_finances/",

    # Salary
    "salary_calculations":       "/salary/calculations/{id}/",
    "salary_general_settings":   "/salary_general_settings/{id}/",
    "salary_daily":              "/salary_daily/{id}/",
    "salary_period":             "/salary_period/{id}/",
    "salary_bonuses_fines":      "/salary_extension_reasons/{id}/",

    # Storage / Products
    "storages_list":             "/storages/storages/list/{id}/",
    "goods_list":                "/goods/list/{id}/",
    "tech_cards":                "/technological_cards/{id}/",
    "storage_transactions":      "/storages/transactions/list/{id}/",
    "inventory":                 "/inventory/list/{id}/",
    "price_tags":                "/price_tags/{id}/",
    "storage_reports":           "/analytics/reports/{id}/reports_storage/",
    "storage_settings":          "/settings/menu/{id}/setting_storage/",

    # Online booking
    "online_booking_forms":      "/online/booking_forms/{id}/",
    "online_links":              "/online/links/{id}/",
    "online_settings":           "/online/online_settings/{id}/",
    "online_personal_domain":    "/online/personal_domain/{id}/",

    # Settings / Team
    "settings_main":             "/settings/menu/{id}/",
    "settings_services":         "/settings/sidebar/service_categories/{id}/",
    "settings_staff":            "/settings/filial_staff/{id}/",
    "work_schedule":             "/work_schedule/{id}/",
    "positions":                 "/positions/list/{id}/",
    "resources":                 "/resources/{id}/",
    "notifications":             "/notifications/{id}/",

    # Loyalty
    "loyalty_info":              "/loyalty/info/{id}/",

    # Integrations
    "integrations":              "/appstore/{id}/applications/overview/",

    # Account
    "billing":                   "/balance/{id}/",
    "invoices":                  "/balance/invoices/{id}/",
    "personal_account":          "/cabinet/info/",
}


def nuke_overlays(page: Page) -> None:
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
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
    page.wait_for_timeout(200)


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
    nuke_overlays(page)

    # Verify each URL
    print("\n── Verify URLs ──")
    results = {}
    for key, path in URLS.items():
        full = f"https://app.alteg.io{path.replace('{id}', COMPANY_ID)}"
        try:
            page.goto(full, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(800)
            body = page.evaluate("() => document.body.innerText.slice(0, 500)")
            is_404 = "Not found" in body or "не существует" in body
            final = page.url
            status = "✓" if not is_404 else "✗"
            print(f"  {status} {key:30s} {path[:50]:50s} → {final[:80]}")
            results[key] = {"path": path, "url": final, "ok": not is_404}
        except Exception as e:
            print(f"  ✗ {key:30s} — {type(e).__name__}: {str(e)[:50]}")
            results[key] = {"path": path, "url": None, "ok": False}

    # ── Look for language/profile settings ──
    print("\n── Find language settings page ──")
    lang_candidates = [
        "/cabinet/info/",
        "/cabinet/profile/",
        "/cabinet/settings/",
        "/cabinet/language/",
        "/user/settings/",
        "/profile/",
        "/settings/language/",
    ]
    for path in lang_candidates:
        url = f"https://app.alteg.io{path}"
        try:
            page.goto(url, wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(800)
            body = page.evaluate("() => document.body.innerText.slice(0, 1500)")
            is_404 = "Not found" in body or "не существует" in body
            has_lang = any(w in body.lower() for w in ["language", "язык", "english", "русский"])
            print(f"  {'✓' if not is_404 else '✗'} {'+lang' if has_lang else '     '} {path:30s} → {page.url[:70]}")
            if not is_404 and has_lang:
                page.screenshot(path=str(OUT / f"lang_{path.replace('/','_')}.png"))
        except Exception as e:
            print(f"  ✗ {path:30s} — {type(e).__name__}")

    # Check cabinet/info page for language selector
    page.goto("https://app.alteg.io/cabinet/info/", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT / "cabinet_info.png"))
    print(f"\n  cabinet/info URL: {page.url}")

    # List all links on cabinet page
    cabinet_links = page.evaluate("""() => {
        return [...document.querySelectorAll('a[href]')].map(a => ({
            href: a.href,
            text: (a.textContent || '').trim().slice(0, 60)
        }));
    }""")
    print(f"\n  Cabinet links:")
    for l in cabinet_links[:30]:
        print(f"    {l.get('href', '')[:80]} | {l.get('text', '')}")

    # Screenshot of the payment methods page (the main goal)
    page.goto(f"https://app.alteg.io/finances/payment_methods_settings/{COMPANY_ID}/",
              wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    page.screenshot(path=str(OUT / "payment_methods.png"))
    print(f"\n  Payment methods URL: {page.url}")

    browser.close()
print("\n✅ Done. See output/url_verify/")
