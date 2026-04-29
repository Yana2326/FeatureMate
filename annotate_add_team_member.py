"""
Annotate the 13 Add team member screenshots (new dark-sidebar UI) with
red Pillow rectangles.

Rule 3 — every rectangle uses the EXACT bounding box captured by Playwright
into bboxes.json, then expands by 10 px symmetric padding on every side.

Source of bboxes : output/add-team-member/bboxes.json
Clean input PNGs : output/add-team-member/screenshots/_originals/
Annotated PNGs   : output/add-team-member/screenshots/

Bbox JSON shape (new format):
  {
    "<screenshot_slug>": {
        "<region_label>": {x, y, w, h}     # flat per-region rect
        | {x, y, w, h, ...nested...}       # if the region wraps multiple rects
    }
  }

For ergonomics we hand-pick which region(s) to draw per screenshot below.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

RED   = (220, 38, 38)
THICK = 3
PAD   = 10

ROOT      = Path("output/add-team-member")
SHOTS     = ROOT / "screenshots"
ORIG      = SHOTS / "_originals"
BBOX_JSON = ROOT / "bboxes.json"


# Per-screenshot annotation plan: map each PNG slug to a list of bbox specs.
# Each spec is either:
#   {"key1": "key2"}        # path inside bboxes.json -> draws that single rect
# A spec can also be inline {x,y,w,h}.
ANNOTATION_PLAN: dict[str, list[dict]] = {
    "01_team_members_list":         [{"path": ["add_button"]}],
    "02_add_chooser_panel":         [{"path": ["employee_tile"]}],
    "03_add_form_empty":            [{"path": ["form_panel"]}],
    "04_add_form_filled":           [],          # no annotation
    "05_member_card_information":   [{"path": ["tabs", "Information"]}],
    "06_member_card_services":      [],
    "07_member_card_online_booking":[],
    "08_member_card_payroll":       [],
    "09_member_card_work_schedule": [],
    "10_member_card_access":        [],
    "11_member_card_notifications": [],
    "12_member_card_settings":      [],
    "13_member_card_legal_info":    [],
}


def lookup(spec: dict, slug_data: dict) -> dict | None:
    """Resolve a spec into a flat bbox {x, y, w, h}."""
    if "x" in spec:
        return spec
    cur = slug_data
    for key in spec.get("path", []):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    if isinstance(cur, dict) and "x" in cur and "y" in cur:
        return cur
    return None


def draw_rect(img: Image.Image, bbox: dict) -> None:
    W, H = img.size
    bw = bbox.get("w", bbox.get("width"))
    bh = bbox.get("h", bbox.get("height"))
    if bw is None or bh is None:
        return
    x0 = max(0, round(bbox["x"] - PAD))
    y0 = max(0, round(bbox["y"] - PAD))
    x1 = min(W - 1, round(bbox["x"] + bw + PAD))
    y1 = min(H - 1, round(bbox["y"] + bh + PAD))

    ImageDraw.Draw(img).rectangle(
        [(x0, y0), (x1, y1)],
        outline=RED,
        width=THICK,
    )


def refresh_backup() -> None:
    ORIG.mkdir(parents=True, exist_ok=True)
    for p in SHOTS.glob("*.png"):
        if p.parent == ORIG:
            continue
        shutil.copy2(p, ORIG / p.name)


def annotate_one(slug: str, specs: list[dict], slug_data: dict | None) -> None:
    src = ORIG / f"{slug}.png"
    dst = SHOTS / f"{slug}.png"
    if not src.exists():
        print(f"  ! pristine source missing: {src}")
        return

    img = Image.open(src).convert("RGB")
    rect_count = 0
    for spec in specs:
        bbox = lookup(spec, slug_data or {})
        if bbox is None:
            print(f"  ! {slug}: unresolved spec {spec}")
            continue
        draw_rect(img, bbox)
        rect_count += 1
    img.save(dst)
    print(f"  ✓ {slug:35s} rects={rect_count}")


def main() -> None:
    if not BBOX_JSON.exists():
        raise SystemExit(
            f"{BBOX_JSON} is missing. Run capture_add_team_member_v3.py first."
        )
    all_bboxes = json.loads(BBOX_JSON.read_text())

    refresh_backup()

    print(f"Annotating {len(ANNOTATION_PLAN)} screenshots")
    for slug, specs in ANNOTATION_PLAN.items():
        annotate_one(slug, specs, all_bboxes.get(slug))

    print("\nDone.")


if __name__ == "__main__":
    main()
