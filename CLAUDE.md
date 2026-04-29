# CLAUDE.md — Altegio System Guide for KB Article Writing

## 🔒 SECURITY RULE — Browser Isolation (MANDATORY)

**When using Computer Use or any browser automation:**

- **NEVER** connect to the user's personal Chrome browser (no `mcp__Claude_in_Chrome__*` tools, no CDP attach to running Chrome)
- **ALWAYS** launch a separate, isolated browser instance
- Use this command to launch isolated Chromium for Computer Use:
  ```bash
  chromium --user-data-dir=/tmp/claude-agent-profile --no-first-run
  ```
- For Playwright, always use `p.chromium.launch(headless=True)` with a fresh `browser.new_context()` — never `connect_over_cdp()` to the user's Chrome
- Always log in with test credentials from `.env`:
  ```
  ALTEGIO_EMAIL=yanabar2304@gmail.com
  ALTEGIO_PASSWORD=Yanatest23
  ```

The isolated profile:
- Has **no access** to personal Chrome data
- Has **no saved passwords or cookies** from the user's accounts
- Is **fully isolated** from the user's browser

**This rule applies to ALL future Computer Use and browser automation sessions without exception.**

---

## What is Altegio
A SaaS platform for managing beauty and wellness businesses. Includes appointment calendar, CRM, inventory, finance, analytics, online booking, and loyalty programs.

## Three Interfaces

### 1. Single Location Interface
Standard interface for managing one business location. All features available.

### 2. Chain Interface
Available for businesses with multiple locations. Allows managing services, products, team members, and settings across all locations at once. Chain-level items are marked with a special chain badge. Switch between chain and individual locations using the location switcher in the top left.

### 3. Mobile App
Available on iOS and Android. Syncs automatically with the web version. Supports appointment management, client work, and visit status updates.

## Two Work Modes (Single Location)
Switch between modes using the yellow button in the bottom left corner:

**Digital Schedule** — daily operations:
- Appointment Calendar — schedule, visits, appointments
- Clients — client database
- Overview — dashboard
- Analytics — reports
- Finance — financial transactions
- Payroll — staff salary
- Inventory — stock management
- Online booking — online booking settings
- Loyalty — loyalty program
- Integrations — third-party integrations

**Administration** — business settings:
- Settings — main settings, services, positions, resources, notifications
- Team — team members, schedules, access rights
- Products — product catalog, inventory management
- Finance — cash registers, financial settings
- Loyalty — loyalty program settings
- Online booking — widget setup
- Integrations — integrations setup

## Quick Bar (left panel, Digital Schedule)
A fast-access panel with the most frequent actions:
- Appointment Calendar
- Favorites — custom shortcuts to any section
- Product sales — sell a product outside of a visit
- New payment — create a financial transaction
- Service list — view all services
- Product catalog — view all products
- Personal account

## How to Navigate

**CRITICAL RULE: ALWAYS navigate by direct URL — NEVER click through menus.**

The left sidebar menu items are hidden in the DOM until hovered, and menu clicks often fail because of overlay modals, Vue.js SPA routing, or language mismatches. Direct URL navigation is instant and 100% reliable.

**Pattern:** `https://app.alteg.io/{section-path}/{company_id}/` — where `company_id` is the numeric location ID (e.g. `1253779` for the test account HappyGio).

### Complete URL Map (test account COMPANY_ID = 1253779)

**Mode switching (hash-based, same base URL):**
| Section | URL |
|---|---|
| Digital Schedule mode | `/timetable/{id}/#mode=1` |
| Administration mode | `/timetable/{id}/#mode=0` |

**Appointment Calendar & Records:**
| Section | URL |
|---|---|
| Appointment Calendar | `/timetable/{id}/` |
| Records list | `/dashboard_records/{id}/` |
| Work schedule | `/work_schedule/{id}/` |

**Clients:**
| Section | URL |
|---|---|
| Client base | `/clients/{id}/base/` |
| Client categories | `/labels/client/{id}/` |
| Loyalty program (client discounts) | `/clients_settings/discounts/{id}/` |

**Overview & Analytics:**
| Section | URL |
|---|---|
| Dashboard (Reports home) | `/dashboard/{id}/` |
| Activities / Events | `/dashboard/activities/{id}/` |
| All reports | `/dashboard/all_reports/{id}/` |
| Main metrics (Analytics) | `/analytics/{id}/` |
| Financial reports | `/analytics/reports/{id}/reports_finances/` |
| Storage reports | `/analytics/reports/{id}/reports_storage/` |

**Finance:**
| Section | URL |
|---|---|
| Financial operations (transactions) | `/finances/transactions/list/{id}/` |
| Accounts & cash registers | `/finances/accounts/list/{id}/` |
| Counterparties (suppliers) | `/finances/suppliers/list/{id}/` |
| Expense items | `/finances/expenses/list/{id}/` |
| Documents | `/documents/{id}/` |
| Payment acceptance (Adyen/acquiring) | `/finances/acquiring/{id}/payment_methods/` |
| **Payment methods and fees** | `/finances/payment_methods_settings/{id}/` |
| Finance settings | `/settings/menu/{id}/setting_finances/` |

**Payroll (Salary):**
| Section | URL |
|---|---|
| Salary calculations | `/salary/calculations/{id}/` |
| General salary settings | `/salary_general_settings/{id}/` |
| Daily salary | `/salary_daily/{id}/` |
| Period salary | `/salary_period/{id}/` |
| Bonuses and penalties | `/salary_extension_reasons/{id}/` |

**Inventory / Storage / Products:**
| Section | URL |
|---|---|
| Warehouses list | `/storages/storages/list/{id}/` |
| All products (goods) | `/goods/list/{id}/` |
| Technology cards | `/technological_cards/{id}/` |
| Warehouse transactions | `/storages/transactions/list/{id}/` |
| Inventory (stocktaking) | `/inventory/list/{id}/` |
| Price tags | `/price_tags/{id}/` |
| Storage settings | `/settings/menu/{id}/setting_storage/` |

**Online Booking:**
| Section | URL |
|---|---|
| Booking forms | `/online/booking_forms/{id}/` |
| Online booking links | `/online/links/{id}/` |
| Online booking settings | `/online/online_settings/{id}/` |
| Personal domain | `/online/personal_domain/{id}/` |

**Settings (Administration → Settings):**
| Section | URL |
|---|---|
| Settings menu (main) | `/settings/menu/{id}/` |
| Services & categories | `/settings/sidebar/service_categories/{id}/` |
| Team members (filial staff) | `/settings/filial_staff/{id}/` |
| Positions | `/positions/list/{id}/` |
| Resources | `/resources/{id}/` |

**Integrations:**
| Section | URL |
|---|---|
| Integrations marketplace | `/appstore/{id}/applications/overview/` |

**Billing & Personal Account (no company_id in path):**
| Section | URL |
|---|---|
| Billing | `/balance/{id}/` |
| Invoices | `/balance/invoices/{id}/` |
| Personal account / profile | `/cabinet/info/` |
| Language selector | `/cabinet/info/` (label "Язык"/"Language" at ~y=220 x=647) |

**Chain / Location switcher:**
| Section | URL |
|---|---|
| Location page (Admin home) | `/location/{id}/` |
| Chain settings | `/group/{chain_id}` |

### Navigation Workflow

1. Look up the target section in the URL map above.
2. Build the URL: `https://app.alteg.io{path}` with `{id}` → `1253779`.
3. Use `page.goto(url, wait_until="networkidle")` — do **not** click the sidebar.
4. Wait 2–3 s after `networkidle`, then run `nuke_overlays(page)` to dismiss Adyen/onboarding modals.
5. Only click inside the content area (x > 260) for in-page interactions (tabs, buttons, modals).

### Standard Overlay Dismiss Routine

```python
def nuke_overlays(page):
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    for label in ["Not now", "View later", "Later", "Skip", "Close",
                  "Посмотрю позже", "Посмотреть позже"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=400):
                btn.click(); page.wait_for_timeout(300)
        except Exception: pass
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
```

### Known Quirks

- **Interface language**: test account defaults to Russian. Before every article run, call `switch_language_to_english(page)` — see the "Language Switching" section below for the verified flow. Still prefer URL navigation and CSS class selectors over text selectors.
- **Browser auto-translate popup**: Chrome shows a "Translate this page?" bar when the UI is Russian but the browser locale is English. It covers the top-right of the page and breaks screenshots. Always launch Chromium with `--disable-features=Translate,TranslateUI`. If it still appears (e.g. in headful mode or a reused profile), close it before taking screenshots — see "Closing the Translate Popup" below.
- **Adyen promo modal** appears on finance/home pages ~1–2 s after navigation. Always wait 2–3 s and call `nuke_overlays` twice.
- **Left sidebar links are hidden** until the Administration mode-switch flyout is open. Never wait for sidebar `<a>` visibility — use direct URLs instead.
- **`/company/{id}/…` and `/location/{id}/…` prefixes return 404**. The correct pattern is `/{section-path}/{id}/` (section-path comes first).
- **`/notifications/{id}/` and `/loyalty/info/{id}/` return 404** — likely moved; find them via the current menu if needed.
- **Trailing slash matters** for some paths; add it when unsure.

### Closing the Translate Popup

Primary defense — disable the feature at launch so the popup never appears:

```python
browser = pw.chromium.launch(
    headless=True,  # or False
    args=[
        "--lang=en-US",
        "--disable-features=Translate,TranslateUI",
    ],
)
ctx = browser.new_context(
    viewport={"width": 1440, "height": 900},
    locale="en-US",
)
```

Fallback — if the popup still slips through (e.g. user profile persists it, or an older Chromium build ignores the flag), dismiss it before every screenshot:

```python
def close_translate_popup(page):
    # 1. The Chrome translate bar is a separate browser UI outside the DOM,
    #    but some builds expose a close <button aria-label="Close"> via the
    #    "translate-element" iframe or a page-level overlay — try both.
    try:
        close = page.locator(
            'button[aria-label="Close"], button[aria-label="Закрыть"], '
            '.translate-close, [class*="translate"] [class*="close"]'
        ).first
        if close.is_visible(timeout=500):
            close.click()
            page.wait_for_timeout(200)
    except Exception:
        pass
    # 2. Keyboard shortcut — Esc closes the translate bar in recent Chrome
    page.keyboard.press("Escape")
    page.wait_for_timeout(150)
    # 3. If Google Translate injected a <div id="goog-gt-tt"> or the translate
    #    banner at the top of the body, hide it
    page.evaluate("""() => {
        for (const sel of ['#goog-gt-tt', '.goog-te-banner-frame',
                            '[id^="google_translate"]',
                            '[class*="translate-banner"]']) {
            for (const el of document.querySelectorAll(sel))
                if (el.isConnected) el.style.display = 'none';
        }
    }""")
```

Call `close_translate_popup(page)` inside `nuke_overlays` or right after every `page.goto(...)` that lands on a Russian page (mostly only between login and the `switch_language_to_english` call — after the language is English, the popup stops appearing).

## Key Terminology
- **Visit** — a group of appointments from one client combined by time interval
- **Appointment / Booking** — an individual client appointment for a service
- **Team member** — a staff member who provides services
- **Location** — a single business branch
- **Chain** — a group of locations managed together
- **Inventory** — a product storage unit (warehouse)
- **Quick bar** — fast-access left panel in Digital Schedule mode

## Workflow for Writing an Article
1. Read the task — identify which mode and section it relates to
2. Search the Knowledge Base via MCP (https://mcp.alteg.io/knowledge/mcp) for similar articles — study structure and terminology
3. Log into Altegio, close the Adyen/onboarding popup (× button → View later)
4. **Close the Chrome translate popup if it appears** (Russian UI + English locale triggers it). Launch Chromium with `--disable-features=Translate,TranslateUI` as the primary defense; if it still shows, call `close_translate_popup(page)` — see "Closing the Translate Popup" below.
5. **MANDATORY: Switch UI language to English** — see "Language Switching" below
6. Verify the UI is in English before proceeding (sidebar shows "Administration", "Product sales", etc.)
7. Navigate to the target section using the URL map (never click through menus)
8. Take screenshots of each screen state
9. Interact freely — create and save data as needed (this is a test account)
10. Write the article following rules in prompts.py
11. Run the checklist before saving

## Language Switching (MANDATORY before every article)

The test account defaults to Russian. Every run must switch the UI to English before capturing screenshots or writing the article.

**URL:** `https://app.alteg.io/cabinet/info/` (Personal account settings — "Настройки личных данных" / "Personal data settings")

**Exact flow (verified working):**

```python
def switch_language_to_english(page):
    """Switch Altegio UI to English. Returns True if verified."""
    page.goto("https://app.alteg.io/cabinet/info/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page)

    # Already English? select#user_lang value=2 means English, value=1 means Russian
    if page.evaluate("() => document.querySelector('#user_lang')?.value") == "2":
        return True

    # Change the native <select>
    page.select_option("#user_lang", value="2")          # 2 = English, 1 = Русский
    page.evaluate("""() => {
        document.querySelector('#user_lang')
            .dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    page.wait_for_timeout(500)

    # Click the "Изменить данные" / "Save changes" button for the Personal data form.
    # CRITICAL: do NOT click "Сохранить" (that's the Notifications form) or
    # "Сохранить параметры" (that's the login-redirect form).
    page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button, input[type="submit"], a.btn')];
        const btn = btns.find(b => /изменить данные|save changes|update profile|update data/i
            .test(b.textContent || b.value || ''));
        if (btn) btn.click();
    }""")
    page.wait_for_timeout(5000)

    # Verify: reload and check the select value
    page.goto("https://app.alteg.io/cabinet/info/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    return page.evaluate("() => document.querySelector('#user_lang')?.value") == "2"
```

**Key selectors:**
| Purpose | Selector | Notes |
|---|---|---|
| Language dropdown | `#user_lang` | Native `<select>`. `value="1"` = Русский, `value="2"` = English |
| Save button for language form | `button:has-text("Изменить данные")` / `"Save changes"` | Right-side "Настройки" form, ≈y=433 |
| Wrong save button #1 | `button:has-text("Сохранить")` btn-sm | Belongs to "Уведомления" (Notifications) form, ≈y=562 — DO NOT CLICK |
| Wrong save button #2 | `button:has-text("Сохранить параметры")` | Belongs to login-redirect form, ≈y=1360 — DO NOT CLICK |

**Verification (after save + reload):**
- `document.querySelector('#user_lang').value === "2"`
- Quick-bar text contains: `"Product sales"`, `"New payment"`, `"Service list"`, `"Product Catalog"`, `"Favorites"`
- Mode-switch button reads: `"Administration"` (not `"Администрирование"`)
- Calendar header shows English days: `su mo tu we th fr sa`

If verification fails, stop and do not proceed — all text-based selectors in navigation will break if the language is wrong.

## YouTube Channel
Altegio has an official YouTube channel with tutorial videos for all sections. Use video descriptions and timecodes as additional context when needed.
