"""
Retake all 14 Integrations screenshots using Playwright.

For every screenshot:
  1. Navigate by direct URL (CLAUDE.md rule: never click sidebar).
  2. Verify Administration mode via altegio_helpers.verify_administration_mode().
  3. Locate the element/region the screenshot will highlight.
  4. Ask Playwright for its exact bounding box — never estimate.
  5. Take the screenshot + persist the bbox to bboxes.json.

Output:
  output/integrations-overview/screenshots/NN_*.png     (14 files, clean, no annotations)
  output/integrations-overview/screenshots/bboxes.json  {name: {x,y,width,height,kind}}
"""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

from altegio_helpers import (
    BASE, COMPANY_ID,
    launch_isolated_browser, login, switch_language_to_english,
    nuke_overlays, close_translate_popup,
    verify_administration_mode,
    save_bboxes,
)


# ═══════════════════════════════════════════════════════════════════════════
# URLs
# ═══════════════════════════════════════════════════════════════════════════
OVERVIEW_URL  = f"{BASE}/appstore/{COMPANY_ID}/applications/overview/"
INSTALLED_URL = f"{BASE}/appstore/{COMPANY_ID}/applications/installed"
CATEGORY_URL  = f"{BASE}/appstore/{COMPANY_ID}/applications?category_id={{cid}}"
DETAIL_URL    = f"{BASE}/appstore/{COMPANY_ID}/applications/{{app_id}}"

CATEGORY_IDS = {
    "payment_systems":     11,
    "analytics":           13,
    "loyalty":             14,
    "crm":                 10,
    "telephony":           15,
    "fiscal_documents":    23,
    "notifications":        1,
    "promotion":            7,
    "client_acquisition":   4,
}

APP_IDS = {
    "google_analytics":   102,
    "viva_wallet":        333,
}

OUT = Path("output/integrations-overview/screenshots")


# ═══════════════════════════════════════════════════════════════════════════
# Robust DOM probes — all return {x,y,width,height} or None
# ═══════════════════════════════════════════════════════════════════════════
JS_SIDEBAR = r"""
() => {
    // The appstore sidebar wrapper is `.marketplace-catalog__sidebar-wrapper`.
    // Its own bounding rect includes a Vue scrollable area much taller than
    // the viewport, so we instead take the *union* of its visible children:
    //   · .marketplace-catalog__search  — application search input
    //   · .marketplace-catalog__sidebar — Main / Categories / Installed menu
    const wrapper = document.querySelector('.marketplace-catalog__sidebar-wrapper');
    if (wrapper && wrapper.children.length) {
        let x0=Infinity, y0=Infinity, x1=-Infinity, y1=-Infinity;
        for (const c of wrapper.children) {
            const r = c.getBoundingClientRect();
            if (r.width <= 0 || r.height <= 0) continue;
            if (r.left   < x0) x0 = r.left;
            if (r.top    < y0) y0 = r.top;
            if (r.right  > x1) x1 = r.right;
            if (r.bottom > y1) y1 = r.bottom;
        }
        if (x0 !== Infinity) {
            return {x: x0, y: y0, width: x1 - x0, height: y1 - y0};
        }
    }
    // Fallback heuristic: find any tall left column holding the expected text.
    const candidates = [...document.querySelectorAll('aside, nav, div, section')];
    for (const c of candidates) {
        const r = c.getBoundingClientRect();
        if (r.left < 240 || r.left > 320) continue;
        if (r.width < 130 || r.width > 260) continue;
        if (r.height < 350 || r.height > 1200) continue;   // skip scroll-inflated
        if (r.top > 200) continue;
        const txt = c.textContent || '';
        if (!/main/i.test(txt)) continue;
        if (!/categor/i.test(txt)) continue;
        if (!/install/i.test(txt)) continue;
        return {x: r.x, y: r.y, width: r.width, height: r.height};
    }
    return null;
}
"""

JS_USER_CHOICE = r"""
() => {
    // Find the "User Choice" heading, then the enclosing section that also
    // contains the featured cards below.
    const all = [...document.querySelectorAll('h1,h2,h3,h4,div,span')];
    let header = null;
    for (const el of all) {
        const t = (el.textContent || '').trim();
        if (t === 'User Choice' || t === 'user choice') { header = el; break; }
    }
    if (!header) return null;

    // The enclosing container is typically <section> or the nearest parent
    // whose width fills the main content area (≥ 700 px).
    let node = header.parentElement;
    for (let i = 0; i < 8 && node; i++) {
        const r = node.getBoundingClientRect();
        if (r.width >= 700 && r.height >= 150) {
            // Cap height so we don't swallow adjacent category previews.
            const cap = Math.min(r.height, 400);
            return {x: r.x, y: r.y, width: r.width, height: cap};
        }
        node = node.parentElement;
    }
    const r = header.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height};
}
"""

JS_CARD_GRID = r"""
() => {
    // Cards are links to /applications/<numericId>.
    const links = [...document.querySelectorAll('a[href*="/applications/"]')];
    const visibleCards = [];
    for (const a of links) {
        const m = a.href.match(/\/applications\/(\d+)(?:\?|$|#|\/)/);
        if (!m) continue;
        const r = a.getBoundingClientRect();
        if (r.width < 150 || r.height < 100) continue;
        if (r.left < 260) continue;           // exclude sidebar links
        if (r.top < 80) continue;              // exclude top-nav links
        visibleCards.push(r);
    }
    if (!visibleCards.length) return null;
    let x0 =  Infinity, y0 =  Infinity;
    let x1 = -Infinity, y1 = -Infinity;
    for (const r of visibleCards) {
        if (r.left   < x0) x0 = r.left;
        if (r.top    < y0) y0 = r.top;
        if (r.right  > x1) x1 = r.right;
        if (r.bottom > y1) y1 = r.bottom;
    }
    return {x: x0, y: y0, width: x1 - x0, height: y1 - y0};
}
"""

JS_NOTIFICATIONS_FILTER_ROW = r"""
() => {
    // Find the row that contains "Channels", "Features", "All application
    // types" as button/tag children. We look for a container whose
    // direct-ish descendants include those three labels.
    const wanted = ['channels', 'features', 'all application types'];
    const all = [...document.querySelectorAll('div, section, ul, header')];
    for (const c of all) {
        const r = c.getBoundingClientRect();
        if (r.top < 120 || r.top > 320) continue;
        if (r.width < 500 || r.height > 80) continue;
        const txt = (c.textContent || '').toLowerCase();
        let ok = true;
        for (const w of wanted) { if (!txt.includes(w)) { ok = false; break; } }
        if (!ok) continue;
        return {x: r.x, y: r.y, width: r.width, height: r.height};
    }
    return null;
}
"""

JS_YELLOW_CTA = r"""
(needleRegex) => {
    const rx = new RegExp(needleRegex, 'i');
    const els = [...document.querySelectorAll('button, a, .q-btn, div[role="button"]')];
    for (const el of els) {
        const t = (el.textContent || '').trim();
        if (!t || t.length > 60) continue;
        if (!rx.test(t)) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 20 || r.height < 20) continue;
        const st = getComputedStyle(el);
        // Collect bg from self + up to 2 ancestors (q-btn colour lives on a child span sometimes)
        let bg = st.backgroundColor;
        let node = el;
        for (let i = 0; i < 3 && node; i++) {
            const s = getComputedStyle(node).backgroundColor;
            if (/rgba?\(\s*\d+/.test(s) && !/rgba\([^)]*,\s*0\)/.test(s)) { bg = s; break; }
            node = node.parentElement;
        }
        const m = bg.match(/rgba?\((\d+)[,\s]+(\d+)[,\s]+(\d+)/);
        if (!m) { /* accept anyway by text match */
            return {x: r.x, y: r.y, width: r.width, height: r.height};
        }
        const [_, rc, gc, bc] = m.map(Number);
        // Altegio yellow is ~ (245, 197, 24) — accept broad yellow range OR
        // fall back to text match if colour is transparent/white.
        const isYellow = rc > 220 && gc > 170 && gc < 230 && bc < 120;
        if (isYellow || (rc >= 250 && gc >= 250 && bc >= 250)) {
            return {x: r.x, y: r.y, width: r.width, height: r.height};
        }
        // Still return on strong text match — some CTAs use SVG backgrounds.
        return {x: r.x, y: r.y, width: r.width, height: r.height};
    }
    return null;
}
"""

JS_CONNECTED_BADGE = r"""
() => {
    // First visible element whose text reads "Connected" and is small
    // (< 150 px wide) — these are the green status pills on cards.
    const all = [...document.querySelectorAll('div, span, small, p, button')];
    for (const el of all) {
        const t = (el.textContent || '').trim();
        if (t !== 'Connected') continue;
        const r = el.getBoundingClientRect();
        if (r.width < 30 || r.width > 200) continue;
        if (r.height < 10 || r.height > 60) continue;
        if (r.top < 80) continue;
        return {x: r.x, y: r.y, width: r.width, height: r.height};
    }
    return null;
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
def probe(page: Page, js: str, *args) -> dict | None:
    return page.evaluate(js, *args) if args else page.evaluate(js)


def ensure_bbox(name: str, bbox: dict | None) -> dict:
    if bbox is None:
        raise RuntimeError(f"Could not locate highlight target for {name!r}")
    # Validate non-degenerate rect
    if bbox["width"] <= 1 or bbox["height"] <= 1:
        raise RuntimeError(f"Degenerate bbox for {name!r}: {bbox}")
    return bbox


def capture(page: Page, name: str, full_page: bool = False) -> None:
    path = OUT / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=full_page)
    print(f"   ✓ {path.name}")


# ═══════════════════════════════════════════════════════════════════════════
# Per-target capture routines
# ═══════════════════════════════════════════════════════════════════════════
def cap_overview(page: Page, bboxes: dict) -> None:
    page.goto(OVERVIEW_URL, wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)
    verify_administration_mode(page)
    bboxes["01_integrations_overview"] = {
        **ensure_bbox("01_integrations_overview", probe(page, JS_SIDEBAR)),
        "kind": "rect",
    }
    capture(page, "01_integrations_overview", full_page=False)

    # 02 — full-page scroll of the same page; highlight is the User-Choice
    # section, so its bbox (measured at scrollY=0) matches the full-page PNG.
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    verify_administration_mode(page)
    bboxes["02_integrations_overview_full"] = {
        **ensure_bbox("02_integrations_overview_full", probe(page, JS_USER_CHOICE)),
        "kind": "rect",
    }
    capture(page, "02_integrations_overview_full", full_page=True)


def cap_category(page: Page, name: str, cid: int, *, kind: str,
                 highlight_js: str | None = None,
                 highlight_args: tuple = (),
                 scroll_to_bbox: bool = False,
                 bboxes: dict | None = None) -> None:
    page.goto(CATEGORY_URL.format(cid=cid), wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    verify_administration_mode(page)

    js = highlight_js or JS_CARD_GRID
    bbox = probe(page, js, *highlight_args) if highlight_args else probe(page, js)
    bbox = ensure_bbox(name, bbox)
    bboxes[name] = {**bbox, "kind": kind}
    capture(page, name, full_page=False)


def cap_installed(page: Page, bboxes: dict) -> None:
    page.goto(INSTALLED_URL, wait_until="networkidle")
    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    verify_administration_mode(page)
    bboxes["12_installed_apps"] = {
        **ensure_bbox("12_installed_apps", probe(page, JS_CONNECTED_BADGE)),
        "kind": "arrow",
    }
    capture(page, "12_installed_apps", full_page=False)


def cap_detail(page: Page, name: str, app_id: int,
               needle_regex: str, bboxes: dict) -> None:
    page.goto(DETAIL_URL.format(app_id=app_id), wait_until="networkidle")
    page.wait_for_timeout(4500)          # detail pages async-load the CTA
    nuke_overlays(page)
    close_translate_popup(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    verify_administration_mode(page)

    # Altegio currently ships the primary Connect/Install button wrapped in
    # `.marketplace-product-controls__btn-tooltip` whose inline style is
    # `display:none` (the tooltip is meant for an error-state hover message,
    # not to hide the CTA itself). Strip that inline style so the button
    # renders exactly as users see it — this matches the original approved
    # capture, where the Connect button was clearly visible.
    page.evaluate("""() => {
        for (const el of document.querySelectorAll(
            '.marketplace-product-controls__btn-tooltip'
        )) {
            if (el.style.display === 'none') el.style.display = '';
        }
    }""")
    page.wait_for_timeout(400)

    bboxes[name] = {
        **ensure_bbox(name, probe(page, JS_YELLOW_CTA, needle_regex)),
        "kind": "arrow",
    }
    capture(page, name, full_page=False)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
def main():
    # Load credentials from .env if present
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    OUT.mkdir(parents=True, exist_ok=True)
    bboxes: dict = {}

    with sync_playwright() as pw:
        browser, ctx, page = launch_isolated_browser(pw, headless=True)
        try:
            print("══ Login ══")
            login(page)

            print("══ Switch language ══")
            if not switch_language_to_english(page):
                raise RuntimeError("Could not switch UI to English")

            print("\n── 01 + 02: Overview ──")
            cap_overview(page, bboxes)

            print("\n── 03: Payment systems ──")
            cap_category(page, "03_category_payment_systems", CATEGORY_IDS["payment_systems"],
                         kind="rect", bboxes=bboxes)

            print("\n── 04: Analytics ──")
            cap_category(page, "04_category_analytics", CATEGORY_IDS["analytics"],
                         kind="rect", bboxes=bboxes)

            print("\n── 05: Loyalty ──")
            cap_category(page, "05_category_loyalty", CATEGORY_IDS["loyalty"],
                         kind="rect", bboxes=bboxes)

            print("\n── 06: CRM ──")
            cap_category(page, "06_category_crm", CATEGORY_IDS["crm"],
                         kind="rect", bboxes=bboxes)

            print("\n── 07: Telephony ──")
            cap_category(page, "07_category_telephony", CATEGORY_IDS["telephony"],
                         kind="rect", bboxes=bboxes)

            print("\n── 08: Fiscal documents (arrow → Learn about… CTA) ──")
            cap_category(page, "08_category_fiscal_documents", CATEGORY_IDS["fiscal_documents"],
                         kind="arrow",
                         highlight_js=JS_YELLOW_CTA,
                         highlight_args=("learn about new integrations",),
                         bboxes=bboxes)

            print("\n── 09: Notifications (rect → filter row) ──")
            cap_category(page, "09_category_notifications", CATEGORY_IDS["notifications"],
                         kind="rect",
                         highlight_js=JS_NOTIFICATIONS_FILTER_ROW,
                         bboxes=bboxes)

            print("\n── 10: Promotion ──")
            cap_category(page, "10_category_promotion", CATEGORY_IDS["promotion"],
                         kind="rect", bboxes=bboxes)

            print("\n── 11: Client acquisition ──")
            cap_category(page, "11_category_client_acquisition", CATEGORY_IDS["client_acquisition"],
                         kind="rect", bboxes=bboxes)

            print("\n── 12: Installed ──")
            cap_installed(page, bboxes)

            print("\n── 13: Google Analytics detail (arrow → Connect) ──")
            cap_detail(page, "13_integration_detail_google_analytics",
                       APP_IDS["google_analytics"], "^connect$", bboxes)

            print("\n── 14: Viva Wallet detail (arrow → Go to website) ──")
            cap_detail(page, "14_integration_detail_viva_wallet",
                       APP_IDS["viva_wallet"], "go to website", bboxes)

        finally:
            browser.close()

    save_bboxes(OUT / "bboxes.json", bboxes)
    print(f"\n══ DONE ══")
    print(f"Wrote {len(bboxes)} bboxes → {OUT / 'bboxes.json'}")
    for k, v in bboxes.items():
        print(f"  {k}  {v['kind']:5s}  "
              f"x={v['x']:.1f}  y={v['y']:.1f}  w={v['width']:.1f}  h={v['height']:.1f}")


if __name__ == "__main__":
    main()
