"""
Reusable Playwright helpers for Altegio automation.

All functions here are shared across capture scripts. They enforce the three
mandatory rules from prompts.py:

  Rule 1  — never emit direct URLs in articles     (nothing to do here;
                                                    capture scripts are
                                                    allowed to use URLs)
  Rule 2  — verify_administration_mode() before every screenshot in an
            Administration-mode section
  Rule 3  — capture element bounding boxes from Playwright so rectangles
            can be drawn with exact symmetric 10 px padding
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Iterable

from playwright.sync_api import Page, BrowserContext, sync_playwright


# ── Credentials (isolated test account only — never personal) ──────────────
EMAIL    = os.environ.get("ALTEGIO_EMAIL", "yanabar2304@gmail.com")
PASSWORD = os.environ.get("ALTEGIO_PASSWORD", "Yanatest23")

# Test-account location id (HappyGio). Hardcoded deliberately — see CLAUDE.md.
COMPANY_ID = "1253779"

BASE = "https://app.alteg.io"

# Red / thickness / padding constants shared with annotate_integrations.py
RED      = (220, 38, 38)
THICK    = 3
PAD      = 10


# ═══════════════════════════════════════════════════════════════════════════
# Browser bootstrap — ALWAYS isolated Chromium (CLAUDE.md SECURITY RULE)
# ═══════════════════════════════════════════════════════════════════════════
def launch_isolated_browser(
    pw,
    headless: bool = True,
    storage_state: str | Path | None = None,
) -> tuple[Any, BrowserContext, Page]:
    """Launch a fresh Chromium — no CDP attach, no profile reuse.

    If `storage_state` points to a JSON file, the browser context is created
    with that state pre-loaded (cookies + localStorage + sessionStorage).
    This is how we reuse a manually-established Administration-mode session
    captured by save_admin_state.py — see CLAUDE.md.
    """
    browser = pw.chromium.launch(
        headless=headless,
        args=[
            "--lang=en-US",
            "--disable-features=Translate,TranslateUI",
            "--no-sandbox",
        ],
    )
    ctx_kwargs = dict(
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    )
    if storage_state is not None and Path(storage_state).exists():
        ctx_kwargs["storage_state"] = str(storage_state)
    ctx = browser.new_context(**ctx_kwargs)
    page = ctx.new_page()
    return browser, ctx, page


# ═══════════════════════════════════════════════════════════════════════════
# Feature flag: new dark-sidebar / new-nav UI
# ═══════════════════════════════════════════════════════════════════════════
def enable_new_ui_flags(page: Page) -> None:
    """
    Switch the test account into the new dark-sidebar / Position-tab UI.

    Discovered 2026-04-28: the test account renders the LEGACY light-sidebar
    UI by default in a fresh isolated profile because two storage flags are
    missing or set to compact-mode values. Flipping them to the values below
    + reloading turns on the new UI.

    Must be called AFTER login + AFTER landing on any altegio page (so the
    storage origin is correct), then a `page.reload()` is required for the
    Vue app to pick up the change.
    """
    page.evaluate("""
    () => {
        // Discovered via probe_flags.py — these are the values that flip the
        // legacy light-sidebar Vue app into the new dark-sidebar / Position-tab UI.
        // 'true' = compact mini-sidebar (legacy). 'expanded' = new full sidebar.
        localStorage.setItem('erp_client_sidebar_compact_navigation', 'expanded');
        localStorage.setItem('new_navigation_enabled', 'true');
        localStorage.setItem('new_nav_enabled', 'true');
        localStorage.setItem('nav_menu_mode', 'new');
        // Session-scoped toggles that mark the new nav-mode as activated
        sessionStorage.setItem('erp-nav-menu-mode-switch:enabled', '1');
        sessionStorage.setItem('erp-nav-menu-mode-switch', 'new');
        sessionStorage.setItem('erp-nav-menu-version', '2');
    }
    """)


# ═══════════════════════════════════════════════════════════════════════════
# Overlays / popups
# ═══════════════════════════════════════════════════════════════════════════
def close_translate_popup(page: Page) -> None:
    """Chrome's translate bar occasionally slips through even with
    --disable-features=Translate,TranslateUI. Dismiss it before capture."""
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
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)
    page.evaluate("""() => {
        for (const sel of ['#goog-gt-tt', '.goog-te-banner-frame',
                           '[id^="google_translate"]',
                           '[class*="translate-banner"]']) {
            for (const el of document.querySelectorAll(sel))
                if (el.isConnected) el.style.display = 'none';
        }
    }""")


def nuke_overlays(page: Page) -> None:
    """Dismiss Adyen promo modal, tooltips, and tours."""
    close_translate_popup(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    for label in ["Not now", "View later", "Later", "Skip", "Close",
                  "Посмотрю позже", "Посмотреть позже"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=300):
                btn.click()
                page.wait_for_timeout(200)
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
        for (const sel of ['[class*="tooltip"]', '[class*="q-tooltip"]',
                           '[class*="popover"]', '[class*="hint"]',
                           '[class*="tour"]']) {
            for (const el of document.querySelectorAll(sel))
                if (el.isConnected) el.style.display = 'none';
        }
    }""")
    page.wait_for_timeout(200)


# ═══════════════════════════════════════════════════════════════════════════
# Login + language
# ═══════════════════════════════════════════════════════════════════════════
def login(page: Page) -> None:
    page.goto(BASE, wait_until="networkidle")
    page.locator("input[name='email']").fill(EMAIL)
    page.locator("input[type='password']").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    nuke_overlays(page)


def switch_language_to_english(page: Page) -> bool:
    page.goto(f"{BASE}/cabinet/info/", wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(2000)
    nuke_overlays(page)
    if page.evaluate("() => document.querySelector('#user_lang')?.value") == "2":
        return True
    page.select_option("#user_lang", value="2")
    page.evaluate("""() => {
        document.querySelector('#user_lang')
            .dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    page.wait_for_timeout(400)
    page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button, input[type="submit"], a.btn')];
        const btn = btns.find(b => /изменить данные|save changes|update profile|update data/i
            .test(b.textContent || b.value || ''));
        if (btn) btn.click();
    }""")
    page.wait_for_timeout(4000)
    page.goto(f"{BASE}/cabinet/info/", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1500)
    return page.evaluate("() => document.querySelector('#user_lang')?.value") == "2"


# ═══════════════════════════════════════════════════════════════════════════
# RULE 2 — mandatory mode check before every screenshot
# ═══════════════════════════════════════════════════════════════════════════
MODE_PROBE_JS = """
() => {
    const btns = [...document.querySelectorAll('button, a, div')];
    for (const b of btns) {
        const txt = (b.textContent || '').trim();
        // The button label is one of these (case may vary across versions):
        //   "Administration"      → click would take you to Admin (so we are in DS)
        //   "Digital Schedule" / "Digital schedule"
        //                          → click would take you to DS (so we are in Admin)
        if (!/^(administration|digital\\s*schedule)$/i.test(txt)) continue;
        if (txt.length > 30) continue;
        const r = b.getBoundingClientRect();
        const vh = window.innerHeight;
        // The mode-toggle sits in the bottom-left corner of the viewport.
        if (r.left < 260 && r.right > 0 && r.bottom > vh - 120 && r.top < vh) {
            return {text: txt, x: r.x, y: r.y, w: r.width, h: r.height};
        }
    }
    return null;
}
"""


def verify_administration_mode(page: Page, *, max_attempts: int = 3) -> dict:
    """
    MANDATORY Rule 2 check. Call this before EVERY screenshot in an
    Administration-mode section.

    The bottom-left mode-toggle button shows the label of the OTHER mode
    (i.e. where clicking would take you):

      • Button reads "Digital Schedule"   → we are already in Administration.
      • Button reads "Administration"     → we are in Digital Schedule, must click.

    Switch strategy (in order):
      1. Real Playwright click on the button via XY coordinates
      2. Hash-based fallback: navigate to /timetable/{id}/#mode=0

    Returns the button's bounding box (proof-of-mode) for the caller. Raises
    RuntimeError if the button can't be found or the switch fails.
    """
    for attempt in range(max_attempts + 1):
        probe = page.evaluate(MODE_PROBE_JS)
        if probe is None:
            if attempt < max_attempts:
                page.wait_for_timeout(900)
                continue
            raise RuntimeError(
                "Mode-toggle button not found in bottom-left. "
                "Cannot verify Administration mode → screenshot skipped."
            )
        # Already in Administration?
        if probe["text"].strip().lower().startswith("digital"):
            return probe

        # We are in Digital Schedule. Try a real click first.
        cx = probe["x"] + probe["w"] / 2
        cy = probe["y"] + probe["h"] / 2
        try:
            page.mouse.click(cx, cy)
        except Exception:
            pass
        page.wait_for_timeout(2000)

        # If still not Admin, try hash fallback
        check = page.evaluate(MODE_PROBE_JS)
        if check is not None and check["text"].strip().lower().startswith("digital"):
            return check
        page.goto(f"{BASE}/timetable/{COMPANY_ID}/#mode=0",
                  wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2500)
    raise RuntimeError(
        "Mode switch to Administration failed after retries → screenshot skipped."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Bounding-box capture (RULE 3 — exact element coords from Playwright)
# ═══════════════════════════════════════════════════════════════════════════
def element_bbox(page: Page, selector: str) -> dict:
    """
    Return the first matching element's on-screen bounding box as
    {'x', 'y', 'width', 'height'}. Raises if the element is not found or
    not visible.
    """
    el = page.locator(selector).first
    el.wait_for(state="visible", timeout=5000)
    el.scroll_into_view_if_needed()
    page.wait_for_timeout(200)
    bbox = el.bounding_box()
    if bbox is None:
        raise RuntimeError(f"Element has no bounding box: {selector!r}")
    return bbox


def union_bbox(boxes: Iterable[dict]) -> dict:
    """Compute the union (outer rectangle) of multiple bounding boxes."""
    boxes = list(boxes)
    if not boxes:
        raise ValueError("union_bbox needs at least one box")
    x0 = min(b["x"] for b in boxes)
    y0 = min(b["y"] for b in boxes)
    x1 = max(b["x"] + b["width"]  for b in boxes)
    y1 = max(b["y"] + b["height"] for b in boxes)
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


def js_bbox(page: Page, js_selector_fn: str) -> dict | None:
    """
    Get a bounding box via a raw JS function that returns a DOM element
    (or null). Useful when CSS selectors can't express the target cleanly.

    `js_selector_fn` must be a self-contained JS arrow fn like:
        "() => [...document.querySelectorAll('a')].find(a => /Connect/.test(a.textContent))"
    """
    result = page.evaluate(f"""() => {{
        const el = ({js_selector_fn})();
        if (!el) return null;
        el.scrollIntoView({{block: 'center'}});
        const r = el.getBoundingClientRect();
        return {{x: r.x, y: r.y, width: r.width, height: r.height}};
    }}""")
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Screenshot helpers — wraps Rule 2 check + optional full-page
# ═══════════════════════════════════════════════════════════════════════════
def safe_screenshot(page: Page, path: Path, *, full_page: bool = False,
                    assert_admin: bool = True) -> dict:
    """
    Take a screenshot, enforcing Rule 2 if `assert_admin`. Returns a dict with
    the saved path and the captured mode-button bbox (proof-of-mode).
    """
    mode_bbox = None
    if assert_admin:
        mode_bbox = verify_administration_mode(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=full_page)
    return {"path": str(path), "full_page": full_page, "mode_bbox": mode_bbox}


def save_bboxes(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


__all__ = [
    "EMAIL", "PASSWORD", "COMPANY_ID", "BASE",
    "RED", "THICK", "PAD",
    "launch_isolated_browser",
    "login", "switch_language_to_english",
    "nuke_overlays", "close_translate_popup",
    "enable_new_ui_flags",
    "verify_administration_mode",
    "element_bbox", "union_bbox", "js_bbox",
    "safe_screenshot", "save_bboxes",
]
