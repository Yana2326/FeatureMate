"""
Switch Altegio UI language to English.

Flow:
1. Login
2. Dismiss Adyen/onboarding popups
3. Navigate to /cabinet/info/
4. select#user_lang → select option "English" (value="2")
5. Click "Сохранить параметры" button (save settings)
6. Verify UI is in English
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

EMAIL    = "yanabar2304@gmail.com"
PASSWORD = "Yanatest23"
OUT      = Path("output/lang_test")
OUT.mkdir(parents=True, exist_ok=True)


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / name))
    print(f"  📸 {name}")


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
    }""")
    page.wait_for_timeout(300)


def switch_language_to_english(page: Page) -> bool:
    """
    Switch the account UI language to English via /cabinet/info/.
    Returns True if verification confirms English is active.
    """
    # Navigate directly
    page.goto("https://app.alteg.io/cabinet/info/", wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    shot(page, "01_cabinet_info.png")

    # Check current language value
    before = page.evaluate("() => document.querySelector('#user_lang')?.value")
    print(f"  Current lang value: {before}")

    if before == "2":
        print("  Already English (value=2)")
        return True

    # select#user_lang option value="2" = English
    page.select_option("#user_lang", value="2")
    page.wait_for_timeout(500)

    after = page.evaluate("() => document.querySelector('#user_lang')?.value")
    print(f"  Lang after select_option: {after}")

    # Dispatch change event in case it's listening for that
    page.evaluate("""() => {
        const el = document.querySelector('#user_lang');
        el.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    page.wait_for_timeout(500)

    # The correct save button for the language form is "Изменить данные"
    # (Change data) / "Save changes" — it's in the same "Настройки" form as #user_lang.
    # NOT "Сохранить" (Notifications form) or "Сохранить параметры" (redirect form).
    clicked = page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button, input[type="submit"], a.btn')];
        const btn = btns.find(b => /изменить данные|save changes|update profile|update data/i.test(b.textContent || b.value || ''));
        if (!btn) return {error: 'not found'};
        btn.scrollIntoView({block: 'center'});
        const r = btn.getBoundingClientRect();
        return {found: true, text: (btn.textContent || btn.value).trim(),
                x: r.x, y: r.y, w: r.width, h: r.height};
    }""")
    print(f"  Save button: {clicked}")

    if clicked.get('found'):
        page.wait_for_timeout(500)
        # Click via JavaScript to avoid tooltips blocking
        page.evaluate("""() => {
            const btns = [...document.querySelectorAll('button, input[type="submit"], a.btn')];
            const btn = btns.find(b => /изменить данные|save changes|update profile|update data/i.test(b.textContent || b.value || ''));
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(5000)
        shot(page, "02_after_save.png")

    # Reload to verify
    page.goto("https://app.alteg.io/cabinet/info/", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    nuke_overlays(page)
    shot(page, "03_after_reload.png")

    final = page.evaluate("() => document.querySelector('#user_lang')?.value")
    print(f"  Lang after reload: {final}")
    return final == "2"


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--lang=en-US"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    page = ctx.new_page()

    # ── 1. Login ──
    print("── 1. Login ──")
    page.goto("https://app.alteg.io", wait_until="networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    nuke_overlays(page)
    print(f"  URL: {page.url}")

    # ── 2. Switch language ──
    print("\n── 2. Switch language to English ──")
    ok = switch_language_to_english(page)
    print(f"  Language value is 2 (English): {ok}")

    # ── 3. Verify UI language on timetable ──
    print("\n── 3. Verify UI language ──")
    page.goto("https://app.alteg.io/timetable/1253779/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    nuke_overlays(page)
    shot(page, "04_timetable_verify.png")

    body = page.evaluate("() => document.body.innerText.slice(0, 2500)")
    has_en = any(w in body for w in ["Administration", "Sales", "Favorites", "Service list"])
    has_ru = any(w in body for w in ["Администрирование", "Продажа товара", "Список услуг"])
    print(f"  English UI: {has_en}")
    print(f"  Russian UI: {has_ru}")
    print(f"\n  First 400 chars:\n{body[:400]}")

    browser.close()
print(f"\n✅ Done. Screenshots in {OUT}/")
