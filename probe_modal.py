"""Find the actual DOM structure of the staff-create modal so we can
write a robust JS probe for its inner card."""
from __future__ import annotations
import os, json
from pathlib import Path
from playwright.sync_api import sync_playwright
from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    nuke_overlays, close_translate_popup,
)

TEAM_LIST = f"{BASE}/settings/filial_staff/{COMPANY_ID}/"


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
            login(page)
            switch_language_to_english(page)
            page.goto(TEAM_LIST, wait_until="networkidle")
            page.wait_for_timeout(2500)
            nuke_overlays(page)
            close_translate_popup(page)
            page.evaluate("""() => {
                const b = document.querySelector('button[data-locator="create_employee_btn"]');
                if (b) b.click();
            }""")
            page.wait_for_selector(".staff-create-modal-featured input", state="visible", timeout=10000)
            page.wait_for_timeout(1200)

            # Now dump the DOM tree under .staff-create-modal-featured
            tree = page.evaluate("""() => {
                const root = document.querySelector('.staff-create-modal-featured');
                if (!root) return null;
                const out = [];
                function walk(el, depth) {
                    if (depth > 6) return;
                    const r = el.getBoundingClientRect();
                    if (r.width < 5 || r.height < 5) return;
                    const cls = (el.className || '').toString().slice(0, 80);
                    out.push({
                        tag: el.tagName,
                        cls: cls,
                        x: Math.round(r.x), y: Math.round(r.y),
                        w: Math.round(r.width), h: Math.round(r.height),
                    });
                    for (const c of el.children) walk(c, depth + 1);
                }
                walk(root, 0);
                return out;
            }""")
            for t in tree[:80]:
                print(f"{t['tag']:8s}  cls={t['cls']:80s}  pos=({t['x']:4d},{t['y']:4d})  size=({t['w']:4d},{t['h']:4d})")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
