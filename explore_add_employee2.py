"""
Probe what kind of element the "Add team member" button actually is, and
where it navigates. Try Playwright's high-level click + wait_for_url.
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

            # Inspect the button HTML (tag, attributes, parent, etc.)
            info = page.evaluate("""() => {
                const btns = [...document.querySelectorAll('button, a, [role="button"]')];
                for (const b of btns) {
                    const t = (b.textContent || '').trim();
                    if (t === 'Add team member') {
                        return {
                            tag: b.tagName,
                            outerHTML: b.outerHTML.slice(0, 800),
                            href: b.href || '',
                            parentHTML: (b.parentElement?.outerHTML || '').slice(0, 800),
                        };
                    }
                }
                return null;
            }""")
            print("Button info:")
            print(json.dumps(info, indent=2, ensure_ascii=False))

            print("\n══ Click via Playwright locator (force=False) ══")
            print(f"URL before click: {page.url}")
            try:
                page.locator("button:has-text('Add team member'), a:has-text('Add team member')").first.click(timeout=5000)
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"Click error: {e}")
            print(f"URL after click: {page.url}")
            EXPLORE.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(EXPLORE / "10_after_click.png"), full_page=False)

            # If URL didn't change, look for a modal or new content area
            content_check = page.evaluate("""() => {
                const out = {h1: [], h2: [], modals: [], visible_inputs: 0};
                for (const h of document.querySelectorAll('h1,h2,h3,h4')) {
                    const t = (h.textContent || '').trim();
                    if (!t) continue;
                    const r = h.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.top < window.innerHeight) {
                        out.h1.push({tag: h.tagName, text: t, x: Math.round(r.x), y: Math.round(r.y)});
                    }
                }
                for (const m of document.querySelectorAll('.q-dialog, [role="dialog"], .modal, .v-dialog, .drawer, .q-drawer')) {
                    const r = m.getBoundingClientRect();
                    if (r.width > 200 && r.height > 200) {
                        out.modals.push({class: m.className.slice(0, 100),
                                         x: Math.round(r.x), y: Math.round(r.y),
                                         w: Math.round(r.width), h: Math.round(r.height)});
                    }
                }
                for (const i of document.querySelectorAll('input, select, textarea')) {
                    const r = i.getBoundingClientRect();
                    if (r.width > 5 && r.height > 5 && r.top < window.innerHeight && r.top > 0)
                        out.visible_inputs += 1;
                }
                return out;
            }""")
            print("\nVisible after click:")
            print(json.dumps(content_check, indent=2, ensure_ascii=False))

            # Try waiting longer
            print("\n══ Wait 5s and check again ══")
            page.wait_for_timeout(5000)
            page.screenshot(path=str(EXPLORE / "11_after_5s.png"), full_page=False)
            late = page.evaluate("""() => {
                const out = [];
                for (const h of document.querySelectorAll('h1,h2,h3,h4,h5')) {
                    const t = (h.textContent || '').trim();
                    if (!t) continue;
                    const r = h.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0)
                        out.push({tag: h.tagName, text: t.slice(0, 80), y: Math.round(r.y)});
                }
                return out;
            }""")
            print(f"Headings: {late}")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
