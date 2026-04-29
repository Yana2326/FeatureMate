"""
Final exploration: capture the post-save state by opening an existing
non-chain team member's settings card. This is what the user reaches
after the Add team member modal saves a new entry.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login,
    nuke_overlays, close_translate_popup,
    verify_administration_mode,
)


TEAM_LIST = f"{BASE}/settings/filial_staff/{COMPANY_ID}/"
EXPLORE = Path("output/add-employee/screenshots/_explore")


def screenshot(page, name: str) -> None:
    EXPLORE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EXPLORE / f"{name}.png"), full_page=False)
    print(f"   ✓ {name}.png")


def main():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    with sync_playwright() as pw:
        browser, ctx, page = launch_isolated_browser(pw, headless=True)
        try:
            print("══ Login ══")
            login(page)

            print("══ Open Team list ══")
            page.goto(TEAM_LIST, wait_until="networkidle")
            page.wait_for_timeout(3000)
            nuke_overlays(page)
            close_translate_popup(page)
            verify_administration_mode(page)

            # Click an existing non-chain member (Lili, Anna, Olivia)
            print("\n══ Click on 'Lili' name to open her settings card ══")
            # Click via JS — find the link/span exactly matching "Lili"
            page.evaluate("""() => {
                const all = [...document.querySelectorAll('a, span')];
                for (const el of all) {
                    if ((el.textContent || '').trim() === 'Lili') {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) { el.click(); return; }
                    }
                }
            }""")
            page.wait_for_timeout(4000)
            close_translate_popup(page)
            print(f"URL: {page.url}")
            screenshot(page, "30_member_card")

            # Dump all visible tabs and headings
            info = page.evaluate("""() => {
                const out = {url: location.href, h: [], tabs: [], buttons: []};
                for (const h of document.querySelectorAll('h1,h2,h3,h4')) {
                    const t = (h.textContent || '').trim();
                    if (!t) continue;
                    const r = h.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0)
                        out.h.push({tag: h.tagName, text: t.slice(0, 80), y: Math.round(r.y)});
                }
                for (const t of document.querySelectorAll('[role="tab"], .nav-tabs__item, .yc-tab, .q-tab, ul.nav > li > a')) {
                    const txt = (t.textContent || '').trim();
                    const r = t.getBoundingClientRect();
                    if (txt && r.width > 5 && r.height > 5 && r.top < 500) {
                        out.tabs.push({text: txt.slice(0, 40), x: Math.round(r.x), y: Math.round(r.y)});
                    }
                }
                for (const b of document.querySelectorAll('button, a.btn, [role="button"]')) {
                    const t = (b.textContent || '').trim();
                    const r = b.getBoundingClientRect();
                    if (t && t.length < 40 && r.top > 0 && r.top < 200 && r.width > 10) {
                        out.buttons.push({text: t, y: Math.round(r.y), x: Math.round(r.x)});
                    }
                }
                return out;
            }""")
            print("Member card info:")
            print(json.dumps(info, indent=2, ensure_ascii=False))
            (EXPLORE / "30_member_card.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))

        finally:
            browser.close()


if __name__ == "__main__":
    main()
