"""
Capture screenshots for the "How to add a team member" article — v3.

Targets the NEW dark-sidebar UI with:
  - Team members list at /settings/sidebar/staff/{id}/ — Position /
    Specialization / System users tabs, members grouped by position
  - "+ Add" right-side chooser panel (Position / Employee)
  - "Add new team member" form (Name + Specialization + Billable/Non-billable)
  - Member card with 9 tabs (Information / Services / Online booking /
    Payroll / Work Schedule / Access / Notifications / Settings / Legal info)

Output:
  output/add-team-member/screenshots/<NN>_<name>.png
  output/add-team-member/bboxes.json    (per-screenshot annotation rectangles)
  output/add-team-member/screenshots.md (Markdown index of captured states)
"""
from __future__ import annotations

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    enable_new_ui_flags, nuke_overlays, close_translate_popup,
)


OUT_DIR = Path("output/add-team-member/screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)
ROOT = OUT_DIR.parent
BBOXES_PATH = ROOT / "bboxes.json"
INDEX_PATH = ROOT / "screenshots.md"


# ─────────────────────────────────────────────────────────────────────
# Snapshot helper (no nuke_overlays — we manage panels ourselves)
# ─────────────────────────────────────────────────────────────────────
def shoot(page, slug: str) -> str:
    page.wait_for_timeout(500)
    path = OUT_DIR / f"{slug}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"  ✓ {slug}.png")
    return str(path)


# ─────────────────────────────────────────────────────────────────────
# DOM helpers
# ─────────────────────────────────────────────────────────────────────
def js_bbox(page, js: str, params=None) -> dict | None:
    """Run a JS snippet that returns {x,y,w,h} (or null) for one element."""
    return page.evaluate(js, params) if params is not None else page.evaluate(js)


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
def main() -> None:
    bboxes: dict[str, dict] = {}
    index: list[str] = []

    with sync_playwright() as pw:
        browser, ctx, page = launch_isolated_browser(pw, headless=True)
        try:
            print("== login + lang + flags ==")
            login(page); switch_language_to_english(page)
            page.goto(f"{BASE}/timetable/{COMPANY_ID}/", wait_until="networkidle")
            page.wait_for_timeout(2000)
            enable_new_ui_flags(page)
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(2500)

            # ── 01: Team members list ─────────────────────────────────
            print("\n-- 01: team members list --")
            page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/",
                      wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page); close_translate_popup(page)
            page.wait_for_timeout(500)
            shoot(page, "01_team_members_list")
            index.append("01_team_members_list — Team members list with "
                         "Position / Specialization / System users tabs")
            # Bbox: the "+ Add" button
            bbox = page.evaluate("""
            () => {
                const b = document.querySelector('[data-locator="create_employee_btn"]');
                if (!b) return null;
                const r = b.getBoundingClientRect();
                return {x: Math.round(r.x), y: Math.round(r.y),
                        w: Math.round(r.width), h: Math.round(r.height)};
            }
            """)
            if bbox:
                bboxes["01_team_members_list"] = {"add_button": bbox}

            # ── 02: + Add chooser panel ───────────────────────────────
            print("\n-- 02: + Add chooser panel --")
            page.locator('[data-locator="create_employee_btn"]').first.click()
            page.wait_for_timeout(2500)
            shoot(page, "02_add_chooser_panel")
            index.append("02_add_chooser_panel — Right-side panel "
                         "'You're here to add' with Position + Employee tiles")
            chooser_bbox = page.evaluate("""
            () => {
                const cards = [...document.querySelectorAll('y-core-card-button')];
                if (cards.length < 2) return null;
                const r1 = cards[0].getBoundingClientRect();
                const r2 = cards[cards.length - 1].getBoundingClientRect();
                return {
                    position_tile: {x: Math.round(r1.x), y: Math.round(r1.y),
                                    w: Math.round(r1.width), h: Math.round(r1.height)},
                    employee_tile: {x: Math.round(r2.x), y: Math.round(r2.y),
                                    w: Math.round(r2.width), h: Math.round(r2.height)},
                };
            }
            """)
            if chooser_bbox:
                bboxes["02_add_chooser_panel"] = chooser_bbox

            # ── 03: Add new team member — empty form ──────────────────
            print("\n-- 03: empty Add team member form --")
            click_xy = page.evaluate("""
            () => {
                const cards = [...document.querySelectorAll('y-core-card-button')];
                const t = cards[cards.length - 1];
                if (!t) return null;
                const r = t.getBoundingClientRect();
                return {x: r.x + r.width/2, y: r.y + r.height/2};
            }
            """)
            if click_xy:
                page.mouse.click(click_xy["x"], click_xy["y"])
            page.wait_for_timeout(3500)
            shoot(page, "03_add_form_empty")
            index.append("03_add_form_empty — Empty 'Add new team member' "
                         "form with Name / Specialization / Billable settings")
            form_bbox = page.evaluate("""
            () => {
                // The form panel's content area
                const root = document.querySelector(
                    '#v-sidebar-teleport-container .v-sidebar__content'
                );
                if (!root) return null;
                const r = root.getBoundingClientRect();
                return {form_panel: {x: Math.round(r.x), y: Math.round(r.y),
                                     w: Math.round(r.width), h: Math.round(r.height)}};
            }
            """)
            if form_bbox:
                bboxes["03_add_form_empty"] = form_bbox

            # ── 04: Add new team member — filled form ─────────────────
            print("\n-- 04: filled Add team member form --")
            fill_result = page.evaluate("""
            () => {
                const root = document.querySelector(
                    '#v-sidebar-teleport-container'
                );
                if (!root) return 'no-panel';
                const inputs = [...root.querySelectorAll('input[type="text"]')]
                    .filter(i => i.getBoundingClientRect().width > 5);
                if (inputs.length < 1) return 'no-inputs';
                const setVal = (el, v) => {
                    const setter = Object.getOwnPropertyDescriptor(
                        HTMLInputElement.prototype, 'value').set;
                    setter.call(el, v);
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                };
                setVal(inputs[0], 'Anna Smith');
                if (inputs[1]) setVal(inputs[1], 'Hair Stylist');
                return `filled-${inputs.length}`;
            }
            """)
            print(f"  fill: {fill_result}")
            page.wait_for_timeout(1500)
            shoot(page, "04_add_form_filled")
            index.append("04_add_form_filled — 'Add new team member' form "
                         "with Anna Smith / Hair Stylist filled in")

            # Cancel — close the panel without saving (don't bloat test data)
            print("  closing without save")
            page.evaluate("""
            () => {
                const root = document.querySelector(
                    '#v-sidebar-teleport-container'
                );
                if (!root) return;
                const buttons = [...root.querySelectorAll('button')];
                const cancel = buttons.find(b =>
                    /cancel|close|отмена/i.test((b.textContent || '').trim())
                );
                if (cancel) cancel.click();
            }
            """)
            page.wait_for_timeout(1500)
            page.keyboard.press("Escape")
            page.wait_for_timeout(1500)

            # ── 05: Member card — Information tab ─────────────────────
            print("\n-- 05: open Mary's card (Information tab) --")
            # Re-load list to clear panel state
            page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/",
                      wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page)

            # First, expand the "Without position" accordion (so its members
            # render in the DOM). Force-click bypasses overlay quirks.
            try:
                page.locator('text="Without position"').first.click(
                    force=True, timeout=8000
                )
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"  (accordion expand: {e})")

            # Then click Mary
            mary = page.locator('text="Mary"').first
            mary.click(force=True, timeout=10000)
            page.wait_for_timeout(3500)
            shoot(page, "05_member_card_information")
            index.append("05_member_card_information — Member card opens "
                         "in side panel showing Information tab")
            tabs_bbox = page.evaluate("""
            () => {
                const tabs = [...document.querySelectorAll(
                    '#v-sidebar-teleport-container .yc-tabs button'
                )].filter(t => t.getBoundingClientRect().width > 5);
                const out = {};
                for (const t of tabs) {
                    const lbl = (t.textContent || '').trim();
                    const r = t.getBoundingClientRect();
                    out[lbl] = {x: Math.round(r.x), y: Math.round(r.y),
                                w: Math.round(r.width), h: Math.round(r.height)};
                }
                return out;
            }
            """)
            if tabs_bbox:
                bboxes["05_member_card_information"] = {"tabs": tabs_bbox}

            # ── 06–13: walk each tab ──────────────────────────────────
            tab_walk = [
                ("06_member_card_services",       "Services"),
                ("07_member_card_online_booking", "Online booking"),
                ("08_member_card_payroll",        "Payroll"),
                ("09_member_card_work_schedule",  "Work Schedule"),
                ("10_member_card_access",         "Access"),
                ("11_member_card_notifications",  "Notifications"),
                ("12_member_card_settings",       "Settings"),
                ("13_member_card_legal_info",     "Legal information"),
            ]
            for slug, tab_label in tab_walk:
                print(f"\n-- {slug}: tab '{tab_label}' --")
                clicked = page.evaluate(f"""
                () => {{
                    const want = {json.dumps(tab_label)}.toLowerCase();
                    const tabs = [...document.querySelectorAll(
                        '#v-sidebar-teleport-container .yc-tabs button, '
                        + '#v-sidebar-teleport-container [role="tab"]'
                    )];
                    for (const t of tabs) {{
                        const lbl = (t.textContent || '').trim().toLowerCase();
                        // Trim badge digits like "Services37" → "services"
                        const cleaned = lbl.replace(/\\d+$/, '').trim();
                        if (cleaned !== want && lbl !== want) continue;
                        const r = t.getBoundingClientRect();
                        if (r.width < 5) continue;
                        t.scrollIntoView({{block: 'center', inline: 'center'}});
                        return {{x: r.x + r.width/2, y: r.y + r.height/2,
                                 cleaned, lbl}};
                    }}
                    return null;
                }}
                """)
                print(f"  click coords: {clicked}")
                if clicked:
                    page.mouse.click(clicked["x"], clicked["y"])
                page.wait_for_timeout(2500)
                shoot(page, slug)
                index.append(f"{slug} — Member card '{tab_label}' tab")

        finally:
            BBOXES_PATH.write_text(json.dumps(bboxes, indent=2, ensure_ascii=False))
            INDEX_PATH.write_text("\n".join(f"- {line}" for line in index) + "\n")
            print(f"\n✓ wrote {BBOXES_PATH}")
            print(f"✓ wrote {INDEX_PATH}")
            print(f"✓ {len(index)} screenshots in {OUT_DIR}")
            browser.close()


if __name__ == "__main__":
    main()
