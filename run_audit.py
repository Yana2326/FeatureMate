"""
run_audit.py — Altegio system exploration audit (pure Playwright).

Walks every documented Altegio section, takes a screenshot, and records the
visible DOM data (title, headings, buttons, inputs, nav) into a structured
map. No AI calls — this script is pure browser automation.

Run:
    .venv/bin/python run_audit.py

Outputs (under output/system-map/):
    system_map.md        Human-readable section-by-section map.
    system_map.json      Array of section records for downstream analysis.
    screenshots/
        administration/
        digital_schedule/
        quick_bar/
        chain/
    audit_run.log        Console mirror.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass, asdict, field
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, TimeoutError as PWTimeout

load_dotenv()

# ─── Configuration ─────────────────────────────────────────────────────────────
BASE_URL   = "https://app.alteg.io"
COMPANY_ID = os.getenv("ALTEGIO_COMPANY_ID", "1253779")   # HappyGio test account
VIEWPORT   = {"width": 1440, "height": 900}
OUT        = Path("output/system-map")
SHOTS      = OUT / "screenshots"
LOG_PATH   = OUT / "audit_run.log"


# ─── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(msg, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def shot(page: Page, rel_path: str) -> Path:
    """Save a screenshot to SHOTS/<rel_path>. Returns the absolute path."""
    p = SHOTS / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(p), full_page=False)
        log(f"  📸 {rel_path}")
    except Exception as e:
        log(f"  ⚠️  screenshot failed ({rel_path}): {e}")
    return p


def nuke_overlays(page: Page) -> None:
    """Dismiss Adyen, onboarding, and modal overlays."""
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
    except Exception:
        pass
    for label in ["Not now", "View later", "Later", "Skip", "Close",
                  "Посмотрю позже", "Посмотреть позже"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=300):
                btn.click()
                page.wait_for_timeout(250)
        except Exception:
            pass
    try:
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
    except Exception:
        pass
    page.wait_for_timeout(200)


def close_translate_popup(page: Page) -> None:
    try:
        close = page.locator(
            'button[aria-label="Close"], button[aria-label="Закрыть"], '
            '.translate-close, [class*="translate"] [class*="close"]'
        ).first
        if close.is_visible(timeout=300):
            close.click()
            page.wait_for_timeout(150)
    except Exception:
        pass
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    try:
        page.evaluate("""() => {
            for (const sel of ['#goog-gt-tt', '.goog-te-banner-frame',
                                '[id^="google_translate"]',
                                '[class*="translate-banner"]']) {
                for (const el of document.querySelectorAll(sel))
                    if (el.isConnected) el.style.display = 'none';
            }
        }""")
    except Exception:
        pass


def login(page: Page, email: str, password: str) -> None:
    log("── Login ──")
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.locator("input[name='email']").fill(email)
    page.locator("input[type='password']").fill(password)
    page.get_by_role("button", name="Sign in").click()
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PWTimeout:
        pass
    page.wait_for_timeout(2000)
    nuke_overlays(page)
    close_translate_popup(page)
    log(f"  → {page.url}")


def switch_language_to_english(page: Page) -> bool:
    log("── Switch language to English ──")
    page.goto(f"{BASE_URL}/cabinet/info/", wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)

    current = page.evaluate("() => document.querySelector('#user_lang')?.value")
    if current == "2":
        log("  Already English")
        return True

    page.select_option("#user_lang", value="2")
    page.evaluate("""() => {
        const el = document.querySelector('#user_lang');
        el && el.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    page.wait_for_timeout(500)
    page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button, input[type="submit"], a.btn')];
        const btn = btns.find(b => /изменить данные|save changes|update profile|update data/i
            .test(b.textContent || b.value || ''));
        if (btn) btn.click();
    }""")
    page.wait_for_timeout(4000)

    page.goto(f"{BASE_URL}/cabinet/info/", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1500)
    final = page.evaluate("() => document.querySelector('#user_lang')?.value")
    log(f"  #user_lang value after save+reload: {final}")
    return final == "2"


def extract_page_data(page: Page) -> dict:
    """Snapshot the visible DOM — title, headings, buttons, inputs, nav links."""
    try:
        data = page.evaluate("""() => {
            const visible = (el) => {
                if (!el.isConnected) return false;
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) return false;
                const st = getComputedStyle(el);
                return st.display !== 'none' && st.visibility !== 'hidden';
            };
            const text = (el) => (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 120);

            const headings = [];
            for (const tag of ['h1','h2','h3']) {
                for (const el of document.querySelectorAll(tag)) {
                    if (visible(el) && text(el)) headings.push({tag, text: text(el)});
                    if (headings.length >= 30) break;
                }
            }

            const buttons = [];
            const seen = new Set();
            for (const el of document.querySelectorAll('button, a.btn, [role="button"], input[type="submit"]')) {
                if (!visible(el)) continue;
                const t = text(el) || el.getAttribute('aria-label') || el.value || '';
                if (!t || seen.has(t)) continue;
                seen.add(t);
                buttons.push(t);
                if (buttons.length >= 40) break;
            }

            const inputs = [];
            for (const el of document.querySelectorAll('input, select, textarea')) {
                if (!visible(el)) continue;
                const label = el.getAttribute('placeholder') || el.getAttribute('aria-label') ||
                              el.getAttribute('name') || el.id || el.getAttribute('type');
                if (label) inputs.push(label);
                if (inputs.length >= 30) break;
            }

            const tabs = [];
            for (const el of document.querySelectorAll('[role="tab"], .tabs a, .q-tab, [class*="tab-"]:not(table)')) {
                if (!visible(el)) continue;
                const t = text(el);
                if (t && t.length < 60 && !tabs.includes(t)) tabs.push(t);
                if (tabs.length >= 20) break;
            }

            const contentLinks = [];
            const cseen = new Set();
            for (const el of document.querySelectorAll('main a[href], .content a[href], .page-content a[href]')) {
                if (!visible(el)) continue;
                const href = el.getAttribute('href');
                const t = text(el);
                if (!href || !t || cseen.has(href)) continue;
                cseen.add(href);
                contentLinks.push({text: t, href});
                if (contentLinks.length >= 20) break;
            }

            return {
                title: document.title,
                url: location.href,
                headings, buttons, inputs, tabs, contentLinks,
                bodyExcerpt: document.body.innerText.replace(/\\s+/g, ' ').slice(0, 800),
            };
        }""")
        return data
    except Exception as e:
        return {"error": str(e), "url": page.url, "title": ""}


# ─── Section records ───────────────────────────────────────────────────────────

@dataclass
class SectionRecord:
    section_name: str
    url: str
    mode: str            # administration | digital_schedule | quick_bar | chain
    subsections: list = field(default_factory=list)
    key_elements: list = field(default_factory=list)
    action_performed: str = ""
    kb_article_used: str = ""
    title: str = ""
    headings: list = field(default_factory=list)
    buttons: list = field(default_factory=list)
    inputs: list = field(default_factory=list)
    tabs: list = field(default_factory=list)
    content_links: list = field(default_factory=list)
    body_excerpt: str = ""
    screenshot: str = ""
    error: str = ""


# ─── Visit logic ───────────────────────────────────────────────────────────────

def visit(page: Page, name: str, path: str, mode: str, slug: str) -> SectionRecord:
    url = f"{BASE_URL}{path}"
    rec = SectionRecord(section_name=name, url=url, mode=mode)
    log(f"\n── {name} — {path}")
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
    except PWTimeout:
        log(f"  ⚠️  networkidle timeout on {path}")
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)
    nuke_overlays(page)  # second pass — Adyen sometimes reappears

    # Detect 404 / error pages early
    status_text = ""
    try:
        status_text = page.evaluate("() => document.body.innerText.slice(0, 500)")
    except Exception:
        pass
    if "404" in status_text[:200] or "Page not found" in status_text:
        log(f"  ❌ Looks like 404")
        rec.error = "404 or not found"

    shot_rel = f"{mode}/{slug}.png"
    shot(page, shot_rel)
    rec.screenshot = shot_rel

    data = extract_page_data(page)
    if "error" in data:
        rec.error = (rec.error + "; " if rec.error else "") + f"extract: {data['error']}"
    else:
        rec.title = data.get("title", "")
        rec.headings = data.get("headings", [])
        rec.buttons = data.get("buttons", [])
        rec.inputs = data.get("inputs", [])
        rec.tabs = data.get("tabs", [])
        rec.content_links = data.get("contentLinks", [])
        rec.body_excerpt = data.get("bodyExcerpt", "")
        rec.key_elements = (
            [f"[heading] {h['text']}" for h in rec.headings[:5]]
            + [f"[button] {b}" for b in rec.buttons[:10]]
            + [f"[input] {i}" for i in rec.inputs[:10]]
            + [f"[tab] {t}" for t in rec.tabs[:10]]
        )
    return rec


def explore_quick_bar(page: Page) -> list[SectionRecord]:
    """Walk the Quick Bar icons on /timetable/ and record their labels + hrefs."""
    log("\n── Quick Bar walk ──")
    page.goto(f"{BASE_URL}/timetable/{COMPANY_ID}/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)

    shot(page, "quick_bar/_overview.png")

    # Quick bar lives in the left 80px strip. Scrape all visible interactive
    # elements there that aren't the mode-switch button.
    items = page.evaluate("""() => {
        const out = [];
        const seen = new Set();
        for (const el of document.querySelectorAll('a, button, [role="button"]')) {
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            if (r.x > 80) continue;                 // left strip only
            if (r.y < 40 || r.y > window.innerHeight - 40) continue;
            const label = (el.getAttribute('aria-label') ||
                           el.getAttribute('title') ||
                           (el.textContent || '').trim()).slice(0, 80);
            const href = el.getAttribute('href') || '';
            const key = label + '|' + href;
            if (!label || seen.has(key)) continue;
            seen.add(key);
            out.push({label, href, x: r.x, y: r.y});
            if (out.length >= 20) break;
        }
        return out;
    }""")

    records = []
    for i, item in enumerate(items):
        rec = SectionRecord(
            section_name=f"QuickBar: {item['label']}",
            url=(f"{BASE_URL}{item['href']}" if item['href'].startswith('/') else item['href']),
            mode="quick_bar",
        )
        rec.key_elements = [f"label: {item['label']}", f"href: {item['href']}",
                             f"position: x={int(item['x'])} y={int(item['y'])}"]
        records.append(rec)
        log(f"  • {item['label']} → {item['href']}")
    return records


def explore_chain(page: Page) -> list[SectionRecord]:
    """Open the top-left location switcher and document chain-interface entry."""
    log("\n── Chain / Location switcher ──")
    page.goto(f"{BASE_URL}/timetable/{COMPANY_ID}/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)

    # The location switcher is top-left (x<260, y<80). Try to click it.
    try:
        switcher = page.evaluate("""() => {
            for (const el of document.querySelectorAll('*')) {
                const r = el.getBoundingClientRect();
                if (r.x < 0 || r.y < 0 || r.x > 260 || r.y > 80) continue;
                if (r.width < 80 || r.width > 250 || r.height < 20 || r.height > 70) continue;
                const t = (el.textContent || '').trim();
                if (!t || t.length > 60) continue;
                return {text: t, x: r.x, y: r.y, w: r.width, h: r.height};
            }
            return null;
        }""")
    except Exception:
        switcher = None

    records = []
    if not switcher:
        log("  ⚠️  Location switcher not found")
        rec = SectionRecord(
            section_name="Chain interface",
            url="",
            mode="chain",
            action_performed="Could not locate location switcher element",
            error="switcher not found",
        )
        records.append(rec)
        return records

    log(f"  Switcher candidate: '{switcher['text']}' at ({int(switcher['x'])}, {int(switcher['y'])})")
    try:
        page.mouse.click(switcher['x'] + switcher['w'] / 2, switcher['y'] + switcher['h'] / 2)
        page.wait_for_timeout(1200)
        shot(page, "chain/01_switcher_expanded.png")
    except Exception as e:
        log(f"  ⚠️  Click failed: {e}")

    # Scrape any menu / dropdown items visible after the click.
    menu_items = []
    try:
        menu_items = page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('[class*="menu"] a, [class*="dropdown"] a, [role="menuitem"], li a')) {
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                const t = (el.textContent || '').trim().slice(0, 80);
                const href = el.getAttribute('href') || '';
                if (!t) continue;
                out.push({text: t, href});
                if (out.length >= 25) break;
            }
            return out;
        }""")
    except Exception:
        pass

    rec = SectionRecord(
        section_name="Location switcher",
        url=page.url,
        mode="chain",
        screenshot="chain/01_switcher_expanded.png",
    )
    rec.key_elements = [f"menu_item: {m['text']} → {m['href']}" for m in menu_items[:20]]
    rec.body_excerpt = "; ".join(m['text'] for m in menu_items[:15])
    records.append(rec)

    # Try to find a chain / group entry
    chain_entry = next((m for m in menu_items
                        if any(k in m['text'].lower()
                               for k in ['chain', 'сеть', 'group', 'группа'])), None)
    if chain_entry and chain_entry['href']:
        href = chain_entry['href']
        chain_url = href if href.startswith('http') else BASE_URL + href
        log(f"  Chain entry found: {chain_entry['text']} → {chain_url}")
        try:
            page.goto(chain_url, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(2500)
            nuke_overlays(page)
            shot(page, "chain/02_chain_landing.png")
            data = extract_page_data(page)
            rec2 = SectionRecord(
                section_name=f"Chain landing: {chain_entry['text']}",
                url=page.url,
                mode="chain",
                screenshot="chain/02_chain_landing.png",
                title=data.get("title", ""),
                headings=data.get("headings", []),
                buttons=data.get("buttons", []),
                body_excerpt=data.get("bodyExcerpt", ""),
            )
            records.append(rec2)
        except Exception as e:
            log(f"  ⚠️  Chain navigation failed: {e}")
    else:
        log("  No chain/group entry in the switcher menu")
        records.append(SectionRecord(
            section_name="Chain interface",
            url="",
            mode="chain",
            action_performed="No chain entry in location switcher — account has only one location",
        ))
    return records


# ─── Section catalog ───────────────────────────────────────────────────────────

def build_catalog(cid: str) -> tuple[list[tuple], list[tuple]]:
    """Return (admin_sections, digital_sections) as [(name, path, slug), ...]."""
    admin = [
        ("Personal account",         f"/cabinet/info/",                                    "personal_account"),
        ("Services & categories",    f"/settings/sidebar/service_categories/{cid}/",       "services"),
        ("Team — filial staff",      f"/settings/filial_staff/{cid}/",                     "team"),
        ("Positions",                f"/positions/list/{cid}/",                            "positions"),
        ("Resources",                f"/resources/{cid}/",                                 "resources"),
        ("Salary — general settings", f"/salary_general_settings/{cid}/",                  "salary_general"),
        ("Salary — calculations",    f"/salary/calculations/{cid}/",                       "salary_calc"),
        ("Salary — daily",           f"/salary_daily/{cid}/",                              "salary_daily"),
        ("Salary — period",          f"/salary_period/{cid}/",                             "salary_period"),
        ("Salary — bonuses/penalties", f"/salary_extension_reasons/{cid}/",                "salary_bonuses"),
        ("Products catalog",         f"/goods/list/{cid}/",                                "products"),
        ("Technology cards",         f"/technological_cards/{cid}/",                       "tech_cards"),
        ("Price tags",               f"/price_tags/{cid}/",                                "price_tags"),
        ("Warehouses (storages)",    f"/storages/storages/list/{cid}/",                    "storages"),
        ("Warehouse transactions",   f"/storages/transactions/list/{cid}/",                "storage_transactions"),
        ("Inventory (stocktaking)",  f"/inventory/list/{cid}/",                            "inventory"),
        ("Settings menu",            f"/settings/menu/{cid}/",                             "settings_menu"),
        ("Finance settings",         f"/settings/menu/{cid}/setting_finances/",            "finance_settings"),
        ("Storage settings",         f"/settings/menu/{cid}/setting_storage/",             "storage_settings"),
        ("Online booking — forms",   f"/online/booking_forms/{cid}/",                      "online_booking_forms"),
        ("Online booking — links",   f"/online/links/{cid}/",                              "online_booking_links"),
        ("Online booking — settings", f"/online/online_settings/{cid}/",                   "online_booking_settings"),
        ("Online booking — personal domain", f"/online/personal_domain/{cid}/",            "online_booking_domain"),
        ("Loyalty / discounts",      f"/clients_settings/discounts/{cid}/",                "loyalty_discounts"),
        ("Integrations marketplace", f"/appstore/{cid}/applications/overview/",            "integrations"),
        ("Notifications (may 404)",  f"/notifications/{cid}/",                             "notifications"),
        ("Loyalty info (may 404)",   f"/loyalty/info/{cid}/",                              "loyalty_info"),
    ]
    digital = [
        ("Appointment Calendar",         f"/timetable/{cid}/",                             "timetable"),
        ("Records list",                 f"/dashboard_records/{cid}/",                     "records"),
        ("Work schedule",                f"/work_schedule/{cid}/",                         "work_schedule"),
        ("Clients — base",               f"/clients/{cid}/base/",                          "clients"),
        ("Client categories",            f"/labels/client/{cid}/",                         "client_categories"),
        ("Dashboard (Reports home)",     f"/dashboard/{cid}/",                             "dashboard"),
        ("Activities / Events",          f"/dashboard/activities/{cid}/",                  "activities"),
        ("All reports",                  f"/dashboard/all_reports/{cid}/",                 "all_reports"),
        ("Analytics — main metrics",     f"/analytics/{cid}/",                             "analytics"),
        ("Analytics — financial reports", f"/analytics/reports/{cid}/reports_finances/",   "analytics_finances"),
        ("Analytics — storage reports",  f"/analytics/reports/{cid}/reports_storage/",     "analytics_storage"),
        ("Financial transactions",       f"/finances/transactions/list/{cid}/",            "finances_transactions"),
        ("Accounts & cash registers",    f"/finances/accounts/list/{cid}/",                "finances_accounts"),
        ("Counterparties / suppliers",   f"/finances/suppliers/list/{cid}/",               "finances_suppliers"),
        ("Expense items",                f"/finances/expenses/list/{cid}/",                "finances_expenses"),
        ("Documents",                    f"/documents/{cid}/",                             "documents"),
        ("Payment acceptance (Adyen)",   f"/finances/acquiring/{cid}/payment_methods/",    "acquiring"),
        ("Payment methods and fees",     f"/finances/payment_methods_settings/{cid}/",     "payment_methods_settings"),
        ("Billing",                      f"/balance/{cid}/",                               "billing"),
        ("Invoices",                     f"/balance/invoices/{cid}/",                      "invoices"),
    ]
    return admin, digital


# ─── Output writers ────────────────────────────────────────────────────────────

def write_json(records: list[SectionRecord]) -> None:
    data = [asdict(r) for r in records]
    (OUT / "system_map.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"\n✅ system_map.json ({len(data)} records)")


def write_md(records: list[SectionRecord]) -> None:
    lines: list[str] = []
    lines.append("# Altegio system map\n")
    lines.append(f"Test account: `COMPANY_ID={COMPANY_ID}`\n")
    lines.append(f"Total sections audited: **{len(records)}**\n")

    by_mode: dict[str, list[SectionRecord]] = {}
    for r in records:
        by_mode.setdefault(r.mode, []).append(r)

    lines.append("## Contents\n")
    for mode in ["administration", "digital_schedule", "quick_bar", "chain"]:
        if mode in by_mode:
            lines.append(f"- [{mode}](#{mode.replace('_','-')}) — {len(by_mode[mode])} entries")
    lines.append("")

    for mode in ["administration", "digital_schedule", "quick_bar", "chain"]:
        if mode not in by_mode:
            continue
        lines.append(f"## {mode}\n")
        for r in by_mode[mode]:
            lines.append(f"### {r.section_name}\n")
            lines.append(f"- **URL:** `{r.url}`")
            if r.title:
                lines.append(f"- **Page title:** {r.title}")
            if r.error:
                lines.append(f"- **Error:** {r.error}")
            if r.screenshot:
                lines.append(f"- **Screenshot:** `screenshots/{r.screenshot}`")
            if r.tabs:
                lines.append(f"- **Tabs:** {', '.join(r.tabs[:10])}")
            if r.headings:
                lines.append("- **Headings:**")
                for h in r.headings[:8]:
                    lines.append(f"    - {h['tag']}: {h['text']}")
            if r.buttons:
                lines.append(f"- **Buttons:** {', '.join(r.buttons[:15])}")
            if r.inputs:
                lines.append(f"- **Inputs:** {', '.join(r.inputs[:15])}")
            if r.key_elements and mode in ("quick_bar", "chain"):
                lines.append("- **Key elements:**")
                for k in r.key_elements[:20]:
                    lines.append(f"    - {k}")
            if r.body_excerpt:
                excerpt = r.body_excerpt.replace("\n", " ")[:300]
                lines.append(f"- **Body excerpt:** {excerpt}")
            lines.append("")

    (OUT / "system_map.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"✅ system_map.md ({sum(1 for _ in lines)} lines)")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    email    = os.getenv("ALTEGIO_EMAIL")
    password = os.getenv("ALTEGIO_PASSWORD")
    if not email or not password:
        print("Error: ALTEGIO_EMAIL and ALTEGIO_PASSWORD must be set in .env", flush=True)
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    for sub in ["administration", "digital_schedule", "quick_bar", "chain"]:
        (SHOTS / sub).mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")   # fresh log

    log("=" * 60)
    log("  Altegio System Exploration Audit (pure Playwright)")
    log("=" * 60)
    log(f"  Output:     {OUT.resolve()}")
    log(f"  Company id: {COMPANY_ID}")

    records: list[SectionRecord] = []

    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(
            headless=True,
            args=[
                "--lang=en-US",
                "--disable-features=Translate,TranslateUI",
            ],
        )
        ctx: BrowserContext = browser.new_context(viewport=VIEWPORT, locale="en-US")
        page: Page = ctx.new_page()
        page.set_default_timeout(20000)

        try:
            login(page, email, password)
            switch_language_to_english(page)

            admin, digital = build_catalog(COMPANY_ID)

            for name, path, slug in admin:
                try:
                    records.append(visit(page, name, path, "administration", slug))
                except Exception as e:
                    log(f"  ❌ {name} failed: {e}")
                    records.append(SectionRecord(
                        section_name=name, url=f"{BASE_URL}{path}",
                        mode="administration", error=str(e),
                    ))

            for name, path, slug in digital:
                try:
                    records.append(visit(page, name, path, "digital_schedule", slug))
                except Exception as e:
                    log(f"  ❌ {name} failed: {e}")
                    records.append(SectionRecord(
                        section_name=name, url=f"{BASE_URL}{path}",
                        mode="digital_schedule", error=str(e),
                    ))

            try:
                records.extend(explore_quick_bar(page))
            except Exception as e:
                log(f"  ❌ Quick Bar walk failed: {e}")
                traceback.print_exc()

            try:
                records.extend(explore_chain(page))
            except Exception as e:
                log(f"  ❌ Chain exploration failed: {e}")
                traceback.print_exc()

        finally:
            browser.close()

    write_json(records)
    write_md(records)

    log("\nDone.")
    log(f"  screenshots:  {SHOTS.resolve()}")
    log(f"  system_map.md:  {(OUT/'system_map.md').resolve()}")
    log(f"  system_map.json: {(OUT/'system_map.json').resolve()}")


if __name__ == "__main__":
    main()
