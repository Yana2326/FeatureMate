"""
run_audit_extras.py — Targeted re-audit of Chain Interface + Quick Bar.

Fixes the two quality issues from the first `run_audit.py` pass:

1. **Chain interface** — the initial audit only visited the chain landing
   page. This script walks every chain sub-section listed by the user
   (Settings, Services/Merge, Team, Inventory, Clients, Loyalty, Online
   Booking, Positions, Translations, Backoffice, Marketing) and also
   auto-discovers anything else in the chain sidebar.

2. **Quick Bar** — the initial audit picked up calendar day numbers
   because the `x<80` filter also caught the mini-calendar. This script
   uses `y>280` to skip the calendar and requires a non-numeric label,
   then CLICKS each Quick Bar item and captures the panel/form it opens.

The new chain + quick_bar records replace the old chain + quick_bar
records in `output/system-map/system_map.{md,json}`. Admin + digital
schedule records are preserved untouched.

Run:
    .venv/bin/python run_audit_extras.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

# Reuse helpers from the main audit script
from run_audit import (
    BASE_URL, COMPANY_ID, VIEWPORT, OUT, SHOTS, LOG_PATH,
    log, shot, nuke_overlays, close_translate_popup,
    login, switch_language_to_english, extract_page_data,
    SectionRecord, write_md,
)

load_dotenv()

CHAIN_ID = os.getenv("ALTEGIO_CHAIN_ID", "1241258")   # discovered from first audit


# ─── Chain interface walker ────────────────────────────────────────────────────

# Expected chain sections per user's spec. Paths are attempts — we also
# auto-discover any sidebar links that weren't pre-listed.
CHAIN_EXPECTED: list[tuple[str, str, str]] = [
    ("Chain — Settings (General)",    f"/group/{CHAIN_ID}",                      "00_settings_general"),
    ("Chain — Services (Merge)",      f"/group/{CHAIN_ID}/services",             "01_services"),
    ("Chain — Team members",          f"/group/{CHAIN_ID}/staff",                "02_team"),
    ("Chain — Positions",             f"/group/{CHAIN_ID}/positions",            "03_positions"),
    ("Chain — Inventory",             f"/group/{CHAIN_ID}/inventory",            "04_inventory"),
    ("Chain — Clients",               f"/group/{CHAIN_ID}/clients",              "05_clients"),
    ("Chain — Loyalty",               f"/group/{CHAIN_ID}/loyalty",              "06_loyalty"),
    ("Chain — Online booking widget", f"/group/{CHAIN_ID}/online_booking",       "07_online_booking"),
    ("Chain — Translation panel",     f"/group/{CHAIN_ID}/translations",         "08_translations"),
    ("Chain — Backoffice",            f"/group/{CHAIN_ID}/backoffice",           "09_backoffice"),
    ("Chain — Marketing tools",       f"/group/{CHAIN_ID}/marketing",            "10_marketing"),
]


def _visit_chain(page: Page, name: str, path: str, slug: str) -> SectionRecord:
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    rec = SectionRecord(section_name=name, url=url, mode="chain")
    log(f"\n── {name}")
    log(f"    URL: {path}")
    try:
        page.goto(url, wait_until="networkidle", timeout=25000)
    except PWTimeout:
        log("    ⚠️  networkidle timeout")

    page.wait_for_timeout(2500)
    nuke_overlays(page)
    close_translate_popup(page)
    nuke_overlays(page)

    # 404 detection
    try:
        snippet = page.evaluate("() => document.body.innerText.slice(0, 400)")
    except Exception:
        snippet = ""
    if "404" in snippet[:200] or "Page not found" in snippet or "не найдена" in snippet:
        rec.error = "404 / not found"
        log("    ❌ 404")

    shot_rel = f"chain/{slug}.png"
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
            [f"[heading] {h['text']}" for h in rec.headings[:6]]
            + [f"[button] {b}" for b in rec.buttons[:15]]
            + [f"[input] {i}" for i in rec.inputs[:15]]
            + [f"[tab] {t}" for t in rec.tabs[:10]]
        )
    return rec


def explore_chain_full(page: Page) -> list[SectionRecord]:
    log("\n" + "=" * 60)
    log("  CHAIN INTERFACE WALK")
    log("=" * 60)

    # 1. Visit all expected sections
    records: list[SectionRecord] = []
    visited_urls: set[str] = set()
    for name, path, slug in CHAIN_EXPECTED:
        url = f"{BASE_URL}{path}" if path.startswith("/") else path
        visited_urls.add(url.rstrip("/"))
        records.append(_visit_chain(page, name, path, slug))

    # 2. Auto-discover sidebar items on /group/ via text-based scraping.
    # The chain sidebar uses Vue <div>/<li> elements with click handlers, not
    # <a href>, so we find elements by visible text in the left strip, click
    # each one, capture the resulting URL, and go back.
    log("\n── Auto-discovery: sidebar items on /group/ ──")
    try:
        page.goto(f"{BASE_URL}/group/{CHAIN_ID}", wait_until="networkidle", timeout=20000)
    except PWTimeout:
        pass
    page.wait_for_timeout(2500)
    nuke_overlays(page)

    try:
        candidates = page.evaluate("""() => {
            const out = [];
            const seen = new Set();
            // Text that looks like a sidebar item: inside left 300px,
            // has visible text under 50 chars, not a form input.
            for (const el of document.querySelectorAll('a, li, div, span, button')) {
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                if (r.x < 0 || r.x > 300) continue;
                if (r.y < 60 || r.y > window.innerHeight - 60) continue;
                // Use only the direct text of the element (not its descendants'
                // nested content) to avoid capturing the whole nav as one blob.
                let text = '';
                for (const node of el.childNodes) {
                    if (node.nodeType === Node.TEXT_NODE) text += node.textContent;
                }
                text = text.trim().replace(/\\s+/g, ' ');
                if (text.length < 2 || text.length > 50) continue;
                if (/^[\\d\\s.,:\\/-]+$/.test(text)) continue;    // skip numeric
                // Make sure this element is clickable: has role, button, or
                // has an ancestor <a>/<li>/[role] within 2 levels.
                let clickable = (el.tagName === 'A' || el.tagName === 'BUTTON');
                let p = el;
                for (let i = 0; i < 3 && !clickable; i++) {
                    if (!p) break;
                    if (p.tagName === 'A' || p.tagName === 'BUTTON'
                        || p.getAttribute('role') === 'button'
                        || /cursor-pointer|clickable|q-item/.test(p.className || '')) {
                        clickable = true;
                    }
                    p = p.parentElement;
                }
                if (!clickable) continue;
                const key = text;
                if (seen.has(key)) continue;
                seen.add(key);
                out.push({text, x: r.x, y: r.y, w: r.width, h: r.height});
                if (out.length >= 40) break;
            }
            return out;
        }""") or []
    except Exception as e:
        log(f"  ⚠️  discovery failed: {e}")
        candidates = []

    log(f"  Discovered {len(candidates)} candidate sidebar items")
    for d in candidates:
        log(f"    • {d['text']!r}  @ ({int(d['x'])}, {int(d['y'])})")

    # 3. Click each candidate, capture its URL + page state, go back to /group/
    extra_count = 0
    click_visited_urls: set[str] = set()
    for d in candidates:
        label = d["text"]
        # Return to chain home before each click
        try:
            page.goto(f"{BASE_URL}/group/{CHAIN_ID}", wait_until="networkidle", timeout=20000)
        except PWTimeout:
            pass
        page.wait_for_timeout(1500)
        nuke_overlays(page)

        try:
            page.mouse.click(d["x"] + d["w"] / 2, d["y"] + d["h"] / 2)
            page.wait_for_timeout(2500)
            nuke_overlays(page)
        except Exception as e:
            log(f"    ⚠️  click failed for {label!r}: {e}")
            continue

        url_after = page.url.rstrip("/")
        # If clicking didn't change the URL (e.g. opened a sub-menu) and it
        # was already visited, skip.
        if url_after in visited_urls or url_after in click_visited_urls:
            continue
        click_visited_urls.add(url_after)

        extra_count += 1
        slug_src = url_after.rstrip("/").split("/")[-1] or "root"
        slug_src = "".join(c if c.isalnum() else "_" for c in slug_src)[:30]
        slug = f"auto_{extra_count:02d}_{slug_src}"[:60]
        name = f"Chain — {label}"

        rec = SectionRecord(section_name=name, url=page.url, mode="chain")
        shot(page, f"chain/{slug}.png")
        rec.screenshot = f"chain/{slug}.png"

        data = extract_page_data(page)
        if "error" not in data:
            rec.title = data.get("title", "")
            rec.headings = data.get("headings", [])
            rec.buttons = data.get("buttons", [])
            rec.inputs = data.get("inputs", [])
            rec.tabs = data.get("tabs", [])
            rec.content_links = data.get("contentLinks", [])
            rec.body_excerpt = data.get("bodyExcerpt", "")
            rec.key_elements = (
                [f"[heading] {h['text']}" for h in rec.headings[:6]]
                + [f"[button] {b}" for b in rec.buttons[:15]]
                + [f"[input] {i}" for i in rec.inputs[:15]]
            )
        rec.action_performed = (
            f"Clicked chain sidebar item labelled '{label}' at "
            f"({int(d['x'])}, {int(d['y'])})"
        )
        records.append(rec)
        log(f"    ✓ captured {label!r} → {page.url}")

    return records


# ─── Quick Bar walker (v2, with click-through) ────────────────────────────────

def explore_quick_bar_v2(page: Page) -> list[SectionRecord]:
    log("\n" + "=" * 60)
    log("  QUICK BAR WALK (v2 — click-through)")
    log("=" * 60)

    def go_baseline():
        page.goto(f"{BASE_URL}/timetable/{COMPANY_ID}/", wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(2500)
        nuke_overlays(page)
        close_translate_popup(page)

    go_baseline()
    shot(page, "quick_bar/00_baseline.png")

    # Quick Bar icons are Vue <div> components, not <button>/<a>. Match by
    # visible text label (case-insensitive, any tag) constrained to the left
    # strip and below the mini-calendar.
    QUICK_BAR_LABELS = [
        "Product sales",
        "New payment",
        "Service list",
        "Product Catalog",
        "Favorites",
    ]
    items = page.evaluate("""(labels) => {
        const out = [];
        const seen = new Set();
        const wanted = new Set(labels.map(s => s.toLowerCase()));
        for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            if (r.x < 0 || r.x > 220) continue;       // left strip only
            if (r.y < 280 || r.y > 780) continue;     // below calendar, above user info
            // Direct text content (not descendants), collapsed whitespace
            let text = '';
            for (const node of el.childNodes) {
                if (node.nodeType === Node.TEXT_NODE) text += node.textContent;
            }
            text = text.trim().replace(/\\s+/g, ' ');
            if (!text) continue;
            const low = text.toLowerCase();
            if (!wanted.has(low)) continue;
            if (seen.has(low)) continue;      // one per label (smallest match)
            seen.add(low);
            // Find the real click target — walk up to find a clickable ancestor
            // that spans the whole icon tile, if there is one.
            let target = el;
            for (let i = 0; i < 3; i++) {
                const p = target.parentElement;
                if (!p) break;
                const pr = p.getBoundingClientRect();
                if (pr.width > r.width && pr.width < 220 &&
                    pr.height >= r.height && pr.x < 220) {
                    target = p;
                    const tr = target.getBoundingClientRect();
                    r.x = tr.x; r.y = tr.y; r.width = tr.width; r.height = tr.height;
                } else break;
            }
            out.push({label: text, href: target.getAttribute?.('href') || '',
                      x: r.x, y: r.y, w: r.width, h: r.height});
        }
        out.sort((a, b) => (a.y - b.y) || (a.x - b.x));
        return out;
    }""", QUICK_BAR_LABELS)

    log(f"  Found {len(items)} Quick Bar items")
    for it in items:
        log(f"    • {it['label']!r:40s} @ ({int(it['x']):>3}, {int(it['y']):>3})")

    records: list[SectionRecord] = []

    for i, item in enumerate(items):
        label = item["label"]
        slug_base = "".join(c if c.isalnum() else "_" for c in label.lower())[:30]
        slug = f"{i+1:02d}_{slug_base}" or f"{i+1:02d}_item"

        # Reset to baseline before each click (so click lands on the real icon,
        # not whatever panel the previous click opened).
        go_baseline()

        log(f"\n  → Clicking: {label}")
        try:
            page.mouse.click(item["x"] + item["w"] / 2, item["y"] + item["h"] / 2)
            # NOTE: do NOT call nuke_overlays() here — Quick Bar items open
            # modals/panels that have high z-index + fixed positioning, which
            # is exactly what nuke_overlays() targets. Just wait for the
            # panel to render.
            page.wait_for_timeout(3500)
        except Exception as e:
            log(f"    ⚠️  click failed: {e}")

        shot_rel = f"quick_bar/{slug}.png"
        shot(page, shot_rel)

        data = extract_page_data(page)
        rec = SectionRecord(
            section_name=f"Quick Bar — {label}",
            url=data.get("url", page.url),
            mode="quick_bar",
            screenshot=shot_rel,
            title=data.get("title", ""),
            headings=data.get("headings", []),
            buttons=data.get("buttons", []),
            inputs=data.get("inputs", []),
            tabs=data.get("tabs", []),
            content_links=data.get("contentLinks", []),
            body_excerpt=data.get("bodyExcerpt", ""),
            action_performed=(
                f"Clicked Quick Bar icon labelled '{label}' at "
                f"({int(item['x'])}, {int(item['y'])})"
            ),
        )
        rec.key_elements = (
            [f"position: x={int(item['x'])} y={int(item['y'])}"]
            + [f"[heading] {h['text']}" for h in rec.headings[:6]]
            + [f"[button] {b}" for b in rec.buttons[:15]]
            + [f"[input] {i}" for i in rec.inputs[:15]]
            + [f"[tab] {t}" for t in rec.tabs[:10]]
        )
        records.append(rec)

    # Extra 1: Location switcher — click the HappyGio logo (top-left, y < 80)
    go_baseline()
    log("\n  → Clicking: Location switcher (HappyGio logo)")
    try:
        page.mouse.click(55, 25)
        page.wait_for_timeout(2500)
        # Skip nuke_overlays — the dropdown is positioned: fixed, z-index high
        shot(page, "quick_bar/99_location_switcher.png")
        data = extract_page_data(page)
        rec = SectionRecord(
            section_name="Quick Bar — Location switcher",
            url=page.url,
            mode="quick_bar",
            screenshot="quick_bar/99_location_switcher.png",
            title=data.get("title", ""),
            headings=data.get("headings", []),
            buttons=data.get("buttons", []),
            body_excerpt=data.get("bodyExcerpt", ""),
            action_performed="Clicked HappyGio logo (top-left) to expand location switcher",
        )
        rec.key_elements = [f"[button] {b}" for b in rec.buttons[:15]]
        records.append(rec)
    except Exception as e:
        log(f"    ⚠️  location switcher click failed: {e}")

    # Extra 2: Calendar Week view (covers the user's "Employee list with Week mode")
    go_baseline()
    log("\n  → Switching calendar to Week mode")
    try:
        clicked = page.evaluate("""() => {
            const candidates = [...document.querySelectorAll('button, a, [role="button"]')];
            const btn = candidates.find(el => {
                const t = (el.textContent || '').trim().toLowerCase();
                const al = (el.getAttribute('aria-label') || '').toLowerCase();
                return /^week$/i.test(t) || /week/.test(al);
            });
            if (!btn) return false;
            btn.click();
            return true;
        }""")
        if clicked:
            page.wait_for_timeout(2500)
            # Week mode is a layout switch, not a modal — overlay-nuking would
            # actually be safe here, but keep consistent with other QuickBar
            # captures and skip it.
            shot(page, "quick_bar/98_calendar_week_mode.png")
            data = extract_page_data(page)
            rec = SectionRecord(
                section_name="Quick Bar — Calendar in Week mode (employee list)",
                url=page.url,
                mode="quick_bar",
                screenshot="quick_bar/98_calendar_week_mode.png",
                title=data.get("title", ""),
                headings=data.get("headings", []),
                buttons=data.get("buttons", []),
                body_excerpt=data.get("bodyExcerpt", ""),
                action_performed="Clicked the 'Week' button in the calendar toolbar",
            )
            rec.key_elements = [f"[button] {b}" for b in rec.buttons[:20]]
            records.append(rec)
        else:
            log("    ⚠️  'Week' button not found in toolbar — skipping")
    except Exception as e:
        log(f"    ⚠️  Week mode switch failed: {e}")

    return records


# ─── Merge & write ─────────────────────────────────────────────────────────────

def _records_from_dicts(dicts: list[dict]) -> list[SectionRecord]:
    """Re-hydrate SectionRecord dataclass instances from the JSON dicts."""
    out = []
    fields = set(SectionRecord.__dataclass_fields__.keys())
    for d in dicts:
        filtered = {k: v for k, v in d.items() if k in fields}
        out.append(SectionRecord(**filtered))
    return out


def main() -> None:
    email = os.getenv("ALTEGIO_EMAIL")
    password = os.getenv("ALTEGIO_PASSWORD")
    if not email or not password:
        print("Error: ALTEGIO_EMAIL and ALTEGIO_PASSWORD must be set in .env", flush=True)
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    for sub in ["chain", "quick_bar"]:
        (SHOTS / sub).mkdir(parents=True, exist_ok=True)

    # Append-mode log so we don't wipe the first-pass history
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write("  RE-AUDIT: chain + quick_bar\n")
        f.write("=" * 60 + "\n")

    existing_json = OUT / "system_map.json"
    if existing_json.exists():
        existing = json.loads(existing_json.read_text(encoding="utf-8"))
    else:
        existing = []
    keep = [r for r in existing if r.get("mode") not in ("chain", "quick_bar")]
    log(f"Loaded {len(existing)} existing records; keeping {len(keep)} "
        f"(dropping old chain + quick_bar)")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--lang=en-US", "--disable-features=Translate,TranslateUI"],
        )
        ctx = browser.new_context(viewport=VIEWPORT, locale="en-US")
        page = ctx.new_page()
        page.set_default_timeout(20000)

        try:
            login(page, email, password)
            switch_language_to_english(page)

            chain_records = explore_chain_full(page)
            quick_records = explore_quick_bar_v2(page)

        finally:
            browser.close()

    # Merge: preserved admin/digital + new chain + new quick_bar
    all_records = _records_from_dicts(keep) + chain_records + quick_records

    # Write JSON
    (OUT / "system_map.json").write_text(
        json.dumps([asdict(r) for r in all_records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"\n✅ system_map.json → {len(all_records)} records")

    # Write MD (reuses run_audit.write_md which groups by mode)
    write_md(all_records)

    log("\nDone.")
    log(f"  system_map.md:   {(OUT/'system_map.md').resolve()}")
    log(f"  system_map.json: {(OUT/'system_map.json').resolve()}")
    log(f"  screenshots:     {SHOTS.resolve()}")


if __name__ == "__main__":
    main()
