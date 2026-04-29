"""
Discover the new-UI structure for the "Add a team member" article.

The new UI has two facets:
  - dark sidebar with new nav (Quick Bar / calendar / Favorites in Digital
    Schedule, or Analytical Reports / Team / Clients / etc in Administration)
  - the new "Team members list" view at /settings/sidebar/staff/{id}/ that
    shows Position / Specialization / System users tabs and groups members
    by position

Discovered 2026-04-28: the new tabbed view ONLY renders in Digital Schedule
mode — when forced into Administration, the page falls back to the legacy
table at /settings/filial_staff/. So we work in Digital Schedule throughout.

Output:
  output/add-team-member/discovery_v2.json   (urls + DOM dumps)
  output/add-team-member/discovery_v2/*.png  (one per stage)
"""
from __future__ import annotations

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    enable_new_ui_flags,
    nuke_overlays, close_translate_popup,
)


OUT_DIR = Path("output/add-team-member/discovery_v2")
OUT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST = OUT_DIR.parent / "discovery_v2.json"


SNAPSHOT_JS = r"""
() => {
    const trim = s => (s || '').trim();
    const txtOf = el => trim(el.textContent).slice(0, 80);
    const visible = el => {
        const r = el.getBoundingClientRect();
        if (r.width < 5 || r.height < 5) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        return true;
    };

    const headings = [...document.querySelectorAll('h1, h2, h3')]
        .filter(visible).slice(0, 8).map(h => ({tag: h.tagName, text: txtOf(h)}));

    const buttons = [...document.querySelectorAll(
        'button, a.q-btn, [role="button"], input[type="submit"]'
    )].filter(visible).map(b => txtOf(b))
       .filter(t => t.length > 0 && t.length < 60);

    const tabs = [...document.querySelectorAll('.q-tab, [role="tab"]')]
        .filter(visible).map(t => txtOf(t));

    // Modal detection
    const modal = [...document.querySelectorAll('.q-dialog')].find(visible);
    const modal_text = modal ? txtOf(modal).slice(0, 200) : null;

    // Field labels (q-field is Quasar input)
    const labels = [...document.querySelectorAll(
        'label, .q-field__label, .q-item__label'
    )].filter(visible).map(txtOf).filter(t => t.length > 0 && t.length < 60);

    return {
        url: location.href,
        title: document.title,
        headings,
        buttons: [...new Set(buttons)],
        tabs,
        labels: [...new Set(labels)].slice(0, 30),
        modal: modal ? {text: modal_text} : null,
    };
}
"""


def snapshot(page, name: str) -> dict:
    page.wait_for_timeout(800)
    nuke_overlays(page); close_translate_popup(page)
    page.wait_for_timeout(400)
    info = page.evaluate(SNAPSHOT_JS)
    info["stage"] = name
    png = OUT_DIR / f"{name}.png"
    page.screenshot(path=str(png), full_page=False)
    info["screenshot"] = str(png)
    print(f"  ✓ {name:35s} {info['url']}")
    print(f"    headings: {[h['text'] for h in info['headings'][:3]]}")
    print(f"    tabs: {info['tabs']}")
    return info


def click_text_real(page, text: str, *, in_main: bool = True,
                    max_top: float = 9999) -> bool:
    """Click an element by exact text using real mouse coords."""
    bbox = page.evaluate("""
    (params) => {
        const {target, in_main, max_top} = params;
        const cands = [...document.querySelectorAll(
            'a, button, span, div, li, .q-tab, .q-item, [role="tab"]'
        )];
        for (const el of cands) {
            if ((el.textContent || '').trim() !== target) continue;
            const r = el.getBoundingClientRect();
            if (r.width < 5 || r.height < 5) continue;
            const st = getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;
            if (in_main && r.left < 260) continue;
            if (r.top > max_top) continue;
            el.scrollIntoView({block: 'center'});
            return {x: r.x + r.width / 2, y: r.y + r.height / 2};
        }
        return null;
    }
    """, {"target": text, "in_main": in_main, "max_top": max_top})
    if not bbox:
        return False
    page.mouse.click(bbox["x"], bbox["y"])
    return True


def main() -> None:
    out = []
    with sync_playwright() as pw:
        browser, ctx, page = launch_isolated_browser(pw, headless=False)
        try:
            print("== login ==")
            login(page)
            print("== switch language ==")
            switch_language_to_english(page)

            print("== enable new UI flags ==")
            page.goto(f"{BASE}/timetable/{COMPANY_ID}/", wait_until="networkidle")
            page.wait_for_timeout(2000)
            enable_new_ui_flags(page)
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page); close_translate_popup(page)

            # ── Stage 1: new Team members list ─────────────────────────────
            print("\n-- stage 1: team members list --")
            page.goto(f"{BASE}/settings/sidebar/staff/{COMPANY_ID}/",
                      wait_until="networkidle")
            page.wait_for_timeout(3000)
            out.append(snapshot(page, "01_team_members_list"))

            # ── Stage 2: click "+ Add" → modal ─────────────────────────────
            print("\n-- stage 2: + Add → modal --")
            clicked = page.evaluate("""
            () => {
                const btns = [...document.querySelectorAll('button, a.q-btn')];
                for (const b of btns) {
                    const t = (b.textContent || '').trim();
                    if (!/^\\+?\\s*Add$/i.test(t) && t !== 'Add') continue;
                    const r = b.getBoundingClientRect();
                    if (r.width < 5 || r.height < 5) continue;
                    if (r.left < 260) continue;
                    b.scrollIntoView({block: 'center'});
                    b.click();
                    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                }
                return null;
            }
            """)
            print(f"  + Add click result: {clicked}")
            if clicked:
                # Real mouse click as fallback in case Vue handler ignores JS click
                page.mouse.click(clicked["x"], clicked["y"])
                page.wait_for_timeout(2500)
            out.append(snapshot(page, "02_add_modal_default"))

            # ── Stage 3: fill modal ───────────────────────────────────────
            print("\n-- stage 3: fill modal --")
            fill_result = page.evaluate("""
            () => {
                const modal = document.querySelector('.q-dialog');
                if (!modal) return 'no-modal';
                const inputs = [...modal.querySelectorAll(
                    'input[type="text"], input:not([type]), input[type="email"], input[type="tel"]'
                )].filter(i => {
                    const r = i.getBoundingClientRect();
                    return r.width > 5 && r.height > 5;
                });
                if (inputs.length === 0) return 'no-inputs';
                const setVal = (el, v) => {
                    const setter = Object.getOwnPropertyDescriptor(
                        HTMLInputElement.prototype, 'value').set;
                    setter.call(el, v);
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                };
                if (inputs[0]) setVal(inputs[0], 'Anna Smith');
                if (inputs[1]) setVal(inputs[1], 'Hair Stylist');
                return `filled-${inputs.length}`;
            }
            """)
            print(f"  fill: {fill_result}")
            page.wait_for_timeout(1500)
            out.append(snapshot(page, "03_add_modal_filled"))

            # ── Stage 4: close modal ──────────────────────────────────────
            print("\n-- stage 4: close modal --")
            page.evaluate("""
            () => {
                const modal = document.querySelector('.q-dialog');
                if (!modal) return false;
                const btns = [...modal.querySelectorAll('button')];
                const cancel = btns.find(b => /cancel|close|отмена/i.test(
                    (b.textContent || '').trim()
                ));
                if (cancel) { cancel.click(); return 'cancel'; }
                const x = modal.querySelector(
                    '[class*="close"], button[aria-label*="lose"]'
                );
                if (x) { x.click(); return 'x'; }
                return false;
            }
            """)
            page.wait_for_timeout(800)
            page.keyboard.press("Escape")
            page.wait_for_timeout(1500)

            # ── Stage 5: expand "Without position" group + click first member
            print("\n-- stage 5: expand group + open member card --")
            # First expand each group accordion
            page.evaluate("""
            () => {
                const groups = [...document.querySelectorAll('*')].filter(el => {
                    const t = (el.textContent || '').trim();
                    return /^Without position$/.test(t)
                        || /^Cosmetologist$/.test(t)
                        || /^Hairdresser$/.test(t);
                });
                // Click only the first that has visible bbox
                for (const g of groups) {
                    const r = g.getBoundingClientRect();
                    if (r.width > 50 && r.height > 5 && r.left > 260) {
                        g.click();
                        return (g.textContent || '').trim();
                    }
                }
                return null;
            }
            """)
            page.wait_for_timeout(1200)

            # Now find a clickable team-member name in the list
            opened = page.evaluate("""
            () => {
                const cands = [...document.querySelectorAll(
                    'a, span, div, [class*="employee"], [class*="staff"], [class*="member"]'
                )];
                // Look for something that resembles a name (starts capital, short)
                const seen = new Set();
                for (const el of cands) {
                    const t = (el.textContent || '').trim();
                    if (t.length === 0 || t.length > 30) continue;
                    if (!/^[A-ZА-Я][a-zа-я]+(?: [A-ZА-Я][a-zа-я]+)?$/.test(t)) continue;
                    if (['Position', 'Specialization', 'System', 'Find',
                         'Reset', 'Add', 'Team', 'Find', 'Team members list',
                         'All', 'Search', 'Without position'].includes(t)) continue;
                    const r = el.getBoundingClientRect();
                    if (r.left < 260 || r.left > 600) continue;
                    if (r.width < 5 || r.height < 5) continue;
                    if (seen.has(t)) continue;
                    seen.add(t);
                    el.click();
                    return {clicked: t, x: r.x + r.width / 2, y: r.y + r.height / 2};
                }
                return null;
            }
            """)
            print(f"  opened: {opened}")
            page.wait_for_timeout(3000)
            out.append(snapshot(page, "04_member_card_information"))

            # ── Stage 6-12: walk each tab ─────────────────────────────────
            tab_names = [
                ("05_member_card_services",       "Services"),
                ("06_member_card_online_booking", "Online booking"),
                ("07_member_card_payroll",        "Payroll"),
                ("08_member_card_work_schedule",  "Work Schedule"),
                ("09_member_card_access",         "Access"),
                ("10_member_card_notifications",  "Notifications"),
                ("11_member_card_settings",       "Settings"),
            ]
            for stage_name, tab_label in tab_names:
                print(f"\n-- {stage_name}: tab '{tab_label}' --")
                # Try Quasar tab first
                clicked = page.evaluate(f"""
                () => {{
                    const want = {json.dumps(tab_label)};
                    const cands = [...document.querySelectorAll(
                        '.q-tab, [role="tab"], .q-item, button, a, span, div'
                    )];
                    for (const el of cands) {{
                        const t = (el.textContent || '').trim();
                        if (t.toLowerCase() !== want.toLowerCase()) continue;
                        const r = el.getBoundingClientRect();
                        if (r.width < 5 || r.height < 5) continue;
                        if (r.left < 260) continue;
                        if (r.top > 500) continue;
                        el.scrollIntoView({{block: 'center'}});
                        el.click();
                        return true;
                    }}
                    return false;
                }}
                """)
                if not clicked:
                    print(f"  ! tab '{tab_label}' not found")
                page.wait_for_timeout(2500)
                out.append(snapshot(page, stage_name))

        finally:
            MANIFEST.write_text(json.dumps(out, indent=2, ensure_ascii=False))
            print(f"\n✓ wrote {MANIFEST} ({len(out)} stages)")
            browser.close()


if __name__ == "__main__":
    main()
