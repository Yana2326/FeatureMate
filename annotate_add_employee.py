"""
Annotate the four Add team member screenshots with red Pillow overlays.

Rule 3 (prompts.py) — RECTANGLE ALIGNMENT:
  Use the EXACT bounding box captured by Playwright (in bboxes.json),
  then apply the user's padding formula verbatim:

      x      = bounding_box.x      - 10
      y      = bounding_box.y      - 10
      width  = bounding_box.width  + 20
      height = bounding_box.height + 20

  This produces 10 px of padding on every side, pixel-perfect, with
  no manual estimation anywhere in the pipeline.

For arrow annotations (kind == "arrow") the tip sits 6 px before the
target's left edge on the horizontal midline, and the tail extends
120 px further left.

Source of bboxes : output/add-employee/screenshots/bboxes.json
Clean input PNGs : output/add-employee/screenshots/_originals/
Annotated PNGs   : output/add-employee/screenshots/
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

RED   = (220, 38, 38)
THICK = 3
PAD   = 10

SHOTS = Path("output/add-employee/screenshots")
ORIG  = SHOTS / "_originals"
BBOX_JSON = SHOTS / "bboxes.json"

ARROW_LEN  = 120
ARROW_GAP  = 6
ARROW_HEAD = 14


def draw_rect(img: Image.Image, bbox: dict) -> None:
    W, H = img.size
    x = bbox["x"] - PAD
    y = bbox["y"] - PAD
    w = bbox["width"]  + 2 * PAD
    h = bbox["height"] + 2 * PAD

    x0 = max(0, round(x))
    y0 = max(0, round(y))
    x1 = min(W - 1, round(x + w))
    y1 = min(H - 1, round(y + h))

    ImageDraw.Draw(img).rectangle(
        [(x0, y0), (x1, y1)],
        outline=RED,
        width=THICK,
    )


def draw_arrow(img: Image.Image, bbox: dict) -> None:
    tip_x  = bbox["x"] - ARROW_GAP
    tail_x = tip_x - ARROW_LEN
    mid_y  = bbox["y"] + bbox["height"] / 2

    x0, y0 = round(tail_x), round(mid_y)
    x1, y1 = round(tip_x),  round(mid_y)

    draw = ImageDraw.Draw(img)
    draw.line([(x0, y0), (x1, y1)], fill=RED, width=THICK)

    angle  = math.atan2(y1 - y0, x1 - x0)
    spread = math.pi / 5
    lx = x1 - ARROW_HEAD * math.cos(angle - spread)
    ly = y1 - ARROW_HEAD * math.sin(angle - spread)
    rx = x1 - ARROW_HEAD * math.cos(angle + spread)
    ry = y1 - ARROW_HEAD * math.sin(angle + spread)
    draw.polygon([(x1, y1), (lx, ly), (rx, ry)], fill=RED)


def refresh_backup() -> None:
    ORIG.mkdir(parents=True, exist_ok=True)
    for p in SHOTS.glob("*.png"):
        if p.parent == ORIG:
            continue
        shutil.copy2(p, ORIG / p.name)


def annotate_one(name: str, spec: dict) -> None:
    src = ORIG / f"{name}.png"
    dst = SHOTS / f"{name}.png"
    if not src.exists():
        raise FileNotFoundError(f"Pristine source missing: {src}")

    img = Image.open(src).convert("RGB")
    kind = spec["kind"]
    if kind == "rect":
        draw_rect(img, spec)
    elif kind == "arrow":
        draw_arrow(img, spec)
    else:
        raise ValueError(f"Unknown annotation kind: {kind!r}")
    img.save(dst)

    if kind == "rect":
        print(f"  ✓ {name:45s} rect  "
              f"bbox=({spec['x']:.0f},{spec['y']:.0f},{spec['width']:.0f},{spec['height']:.0f})  "
              f"padding=10/10/10/10")
    else:
        print(f"  ✓ {name:45s} arrow "
              f"tip=({spec['x']-ARROW_GAP:.0f},{spec['y']+spec['height']/2:.0f})")


def main() -> None:
    if not BBOX_JSON.exists():
        raise SystemExit(
            f"{BBOX_JSON} is missing. Run capture_add_employee.py first."
        )
    bboxes = json.loads(BBOX_JSON.read_text())

    refresh_backup()

    print(f"Annotating {len(bboxes)} screenshots from bboxes.json")
    for name, spec in bboxes.items():
        annotate_one(name, spec)

    print(f"\nDone — {len(bboxes)} screenshots annotated from pristine originals.")


if __name__ == "__main__":
    main()
