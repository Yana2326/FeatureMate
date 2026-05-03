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

**Mode switching:**

The mode is toggled by a yellow button in the bottom-left corner of the sidebar. The button label shows the OTHER mode (where clicking takes you), so:
- Button text "Administration" → currently in Digital Schedule mode (click to switch)
- Button text "Digital Schedule" → currently in Administration mode (do not click)

**Verification:** in Administration mode, the sidebar shows these items at the top: Analytical Reports, Team, Clients, Online Booking, Services, Products, Finance, Payroll, Notifications, Loyalty, Resources, Integrations, Settings.

**Working selector for the mode-switch button:**

```css
.erp-nav-menu-mode-switch-footer-button
```

Exact HTML structure (verified 2026-04-30 on the test account):

```html
<div class="erp-nav-menu-mode-switch-footer-button">
  <i class="q-icon my-icon-ds-settings" aria-hidden="true" role="presentation"></i>
  <span>Administration</span>
</div>
```

The button has yellow background (`rgb(255, 203, 0)`) and `cursor: pointer`. The text label is in the inner `<span>`. Position in the test viewport: x=0, y=1006, w=220, h=44.

> ✅ **WORKING SOLUTION — Playwright `storageState` captured from a manual click.**
>
> Mode is held in Vue 3 reactive state tied to the browser session. It is NOT in cookies, localStorage, or sessionStorage as a discoverable flag, and clicking the yellow `.erp-nav-menu-mode-switch-footer-button` from Playwright reaches the Vue handler (verified: trusted events, handler executes) but does not switch the mode (0 network requests after click — see KNOWN LIMITATION below).
>
> **One-time setup** (run on the user's machine, headful):
>
> ```bash
> python3 save_admin_state.py
> ```
>
> The script auto-logs in and opens a headful browser. The user manually clicks the yellow "Administration" button in the bottom-left, verifies the sidebar now shows Analytical Reports / Team / Clients / Online Booking / Services / Products / Finance / Payroll / Notifications / Loyalty / Resources / Integrations / Settings, then presses Enter in the terminal. The script saves cookies + localStorage + sessionStorage to `admin_storage_state.json`.
>
> **Subsequent capture runs** (any article): `launch_isolated_browser(pw, storage_state="admin_storage_state.json")` — the context starts already in Administration mode. Skip `login()` and skip the mode-switch click entirely.
>
> Re-run `save_admin_state.py` only if Altegio invalidates the session (cookie expiry, etc.) or the saved state stops producing the admin sidebar.
>
> ⚠️ **KNOWN LIMITATION — the click handler does not fire from Playwright in a fresh session.**
>
> Verified 2026-04-30 with diagnostic capture-event listeners: clicks from Playwright **do** reach the button as fully trusted native events (`isTrusted: True`, all of pointerdown / mousedown / pointerup / mouseup / click fire on the `<span>` inside `.erp-nav-menu-mode-switch-footer-button`, `defaultPrevented: false`). The Vue 3 click handler on the button **does** execute. But it produces **zero** network requests, no URL change, no DOM mutation, and no console output. Mode does not switch.
>
> The screenshot the product owner provided shows account `yana.b@alteg.io` (an Altegio employee account). The `.env` test account is `yanabar2304@gmail.com` (user_id 12735899, customer account). The mode-switch handler in this Vue 3 build appears to silently no-op when the logged-in user lacks an internal "employee/staff" role — explaining why the click is received but nothing happens. This is an **account-permissions issue**, not a browser-automation issue.
>
> Tested and ruled out: `locator.click()`, `locator.click(force=True)`, `mouse.move(steps)+down/up`, `mouse.click(delay=…)`, focus + Enter / Space, `dispatchEvent()` with full pointer/mouse sequences, CDP `Input.dispatchMouseEvent`, clicking the parent wrapper, inner span, gear icon, scroll-into-view + hover, stealth (`navigator.webdriver=undefined`), longer hydration waits (4–10 s), headless Chromium, headful Chromium, Firefox, `#mode=0` hash, `location.hash` JS assignment.
>
> **What to do:**
> 1. To get screenshots that show the genuine Administration-mode sidebar (Analytical Reports, Team, Clients, Online Booking, Services, Products, Finance, Payroll, Notifications, Loyalty, Resources, Integrations, Settings), the test account needs to be upgraded to an employee/staff role in Altegio's user model — or use a different account that already has the role. Ping the product owner.
> 2. **Until then, navigate directly to admin-only URLs** (e.g. `/settings/sidebar/staff/{id}/?…`). The page content lands on the correct admin section with correct page-content elements (filters, tabs, action buttons, member cards, all 9 inner tabs). The left sidebar will still show Digital-Schedule-style elements (mini-calendar, Quick Bar, Favorites), which is a visual gap from a real admin-mode session. Document this gap in the article QA checklist.

| Section | URL |
|---|---|
| Digital Schedule mode | `/timetable/{id}/#mode=1` |
| Administration mode (legacy hash — does NOT switch sidebar in current UI) | `/timetable/{id}/#mode=0` |
| Admin-only entry (workaround) | `/analytics/{id}/?start_date=…&end_date=…&user_id=0&position_id=0&master_id=0` |
| Admin Team list (direct) | `/settings/sidebar/staff/{id}/?position_id=-1&fired=0&deleted=0&user_linked=2&is_paid=2` |

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

## Article Quality Rules

These rules apply to every article written with this agent. Check all of them before saving the final article and generating the PDF.

### 1. Administration mode (MANDATORY first step)
Always switch to **Administration** mode before navigating the UI or taking screenshots. Screenshots taken in Digital Schedule mode do not match the Administration UI and must be retaken.

### 2. Screenshot accuracy
Before taking a screenshot for each section, navigate to that exact tab or page. Every screenshot must match the section it illustrates — do not reuse a screenshot from a different tab or step.

### 3. Annotations (MANDATORY)
Every screenshot must have at least one red rectangle annotation highlighting the relevant UI element. Use `element.bounding_box()` from Playwright to get exact coordinates, expand by 10 px padding on every side, and draw a 3 px red rectangle with Pillow. Never publish a screenshot without an annotation.

### 4. Writing style
Do not list UI elements mechanically. Write as a guide: explain what the user can do here and why it matters. Each section should answer "why would I use this?" in addition to "what is here?" Use clear, helpful language — if you would not say something out loud to a colleague, do not write it.

### 5. Placeholder check (MANDATORY)
Never leave `[Screenshot]` or any other placeholder in the final article. Every placeholder must be replaced with a real `![alt](screenshots/filename.png)` reference before saving. Run `grep '\[Screenshot\]' article.md` as a final check.

### 6. Section completeness
Every tab and section must be fully described. One-sentence summaries are not acceptable. Describe what the user can configure, what the controls do, and when they would use each option.

### 7. Article title
The title must accurately reflect the full content of the article, not just the first action. If the article covers adding and configuring a team member across nine tabs, the title must say so. Use the form "How to [full scope] in Altegio".

### 8. Empty and locked states
When describing a tab or section, always cover both:
- The **active/configured state** — what the user can see and do when the feature is set up.
- The **empty or locked state** — what happens when access is missing, no data has been entered, or a prerequisite is not met (for example, "No access — assign access rights first").

---

## Screenshot Rules (MANDATORY — applies to every article, every time)

### 1. Always switch to Administration mode first
Before any navigation or screenshot, explicitly click the yellow **Administration** button in the bottom-left corner. Do not assume the correct mode is already active.

### 2. Verify Administration mode is active
After switching, confirm the left sidebar contains all of these items:
**Analytical Reports, Team, Clients, Online Booking, Services, Products, Finance, Payroll, Notifications, Loyalty, Resources, Integrations, Settings**
If any are missing, the mode switch failed — do not proceed until verified.

### 3. First screenshot of any navigation article: sidebar, not action button
The first screenshot must show the **Administration mode sidebar** with a red rectangle around the specific menu item being described (e.g. "Team members list" under "Team"). Never highlight an action button (like "+ Add") in a navigation step. The sidebar navigation — not the page content — is what illustrates navigation instructions.

### 4. Before every tab screenshot: click, wait, verify
Before capturing each tab screenshot:
1. Explicitly click the tab by its exact label
2. Wait for a unique element inside that tab to confirm it has fully loaded
3. Read the active tab label from the DOM and confirm it matches the section
4. If it does not match — re-click and verify before shooting

### 5. Every screenshot must have at least one red rectangle annotation
No screenshot goes into the article without a red rectangle highlighting the relevant UI element. Annotate immediately after capture (inline PIL, 10 px padding, 3 px stroke, colour #DC2626). Use `element.bounding_box()` from Playwright for exact coordinates.

### 6. Verify every screenshot against its section before finishing
After all screenshots are captured, read the screenshots index and confirm each file matches the section it illustrates. Wrong screenshots must be retaken — never left in place.

### 7. These rules apply to every future article without exception

---

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
