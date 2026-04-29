"""
Annotate all article screenshots with red arrows or rectangles.
Rules:
  - Red color (#DC2626) for all annotations
  - ONE method per screenshot: either arrow OR rectangle
  - Arrow: points to the main action element (never on top of a button)
  - Rectangle: outlines the key UI area with consistent padding (8px)
  - Never place arrow tip directly on a button (offset by ~15px)
Saves annotated versions back to the same filename (overwrites originals).

Screenshot dimensions after fix_screenshots.py:
  z04 / z05 / z06  — 1245 × 900  (calendar, left quick-bar removed)
  z07 / z08 / z08_advanced / z09 / z10 / btn02 — 1100 × 900  (full sidebar)
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw

SHOTS = Path("output/create-appointment/screenshots")
PAD   = 8    # rectangle padding
RED   = (220, 38, 38)
THICK = 3    # line thickness


# ── Drawing helpers ──────────────────────────────────────────────────────────

def rect(img: Image.Image, x1, y1, x2, y2, pad=PAD) -> Image.Image:
    """Draw a red rectangle with padding around (x1,y1)-(x2,y2)."""
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [x1 - pad, y1 - pad, x2 + pad, y2 + pad],
        outline=RED, width=THICK,
    )
    return img


def arrow(img: Image.Image, x0, y0, x1, y1, head=14) -> Image.Image:
    """Draw a red arrow from (x0,y0) to (x1,y1) with a filled arrowhead."""
    draw = ImageDraw.Draw(img)
    draw.line([(x0, y0), (x1, y1)], fill=RED, width=THICK)

    # Arrowhead: filled triangle at tip
    angle = math.atan2(y1 - y0, x1 - x0)
    spread = math.pi / 5  # 36°
    lx = x1 - head * math.cos(angle - spread)
    ly = y1 - head * math.sin(angle - spread)
    rx = x1 - head * math.cos(angle + spread)
    ry = y1 - head * math.sin(angle + spread)
    draw.polygon([(x1, y1), (lx, ly), (rx, ry)], fill=RED)
    return img


def load(name: str) -> tuple[Image.Image, Path]:
    path = SHOTS / name
    return Image.open(path).convert("RGB"), path


def save(img: Image.Image, path: Path):
    img.save(str(path))
    w, h = img.size
    print(f"  ✅ {path.name}  ({w}×{h})")


# ── Per-screenshot annotation specs ─────────────────────────────────────────
#
# Calendar shots (1245 × 900):
#   Time labels occupy x=0–82; first staff column: x≈82–215 (width ≈133px)
#   Calendar grid rows: 10:00 starts at y≈155; each 30 min ≈ 30px
#
# Appointment sidebar shots (1100 × 900):
#   Left panel:   x=0–297      (Team member, Date, Time, buttons)
#   Center panel: x=297–760    (Services, Products, status pills)
#   Right panel:  x=760–1100   (Client name, Phone, Email …)
#   Footer bar:   y≈855–900    (New appointment | Save blank appointment)

def annotate_all():

    # 1. z04 — calendar with free slots; rectangle around first column free slots
    img, path = load("z04_calendar_scrolled.png")
    w, h = img.size
    print(f"\nz04  {w}×{h}")
    # First staff column (Mary): x=82–215; free slots 10:00–11:30 band: y=155–245
    img = rect(img, 82, 155, 215, 245)
    save(img, path)

    # 2. z05 — hover "New Booking" indicator; arrow from above pointing at the label
    img, path = load("z05_hover_shows_new_booking.png")
    w, h = img.size
    print(f"\nz05  {w}×{h}")
    # "11:15 New Booking" block: x≈83–218, y≈240–258
    # Arrow tail at (150, 185), tip just above the block at (150, 240)
    img = arrow(img, 150, 185, 150, 240)
    save(img, path)

    # 3. z06 — Booking/Event dropdown; rectangle around the dropdown card
    img, path = load("z06_after_slot_click_dropdown.png")
    w, h = img.size
    print(f"\nz06  {w}×{h}")
    # Dropdown card: x≈78–253, y≈265–345
    img = rect(img, 78, 265, 253, 345)
    save(img, path)

    # 4 & 5. z08 — load once (clean full-sidebar source), annotate two copies
    clean_z08_path = SHOTS / "z08_left_panel.png"
    clean_z08 = Image.open(clean_z08_path).convert("RGB")
    w, h = clean_z08.size
    print(f"\nz08 clean source  {w}×{h}")

    # 4. z08_left_panel — scheduling fields (Team member, Date, Time/duration)
    img_sched = clean_z08.copy()
    # Fields span x=22–280, y=27–175
    img_sched = rect(img_sched, 22, 27, 280, 175)
    save(img_sched, clean_z08_path)

    # 5. z08_left_panel_advanced — Advanced fields / Repeat / Notifications buttons
    img_adv = clean_z08.copy()
    # Buttons are in the bottom-left section: x=22–280, y=455–630
    img_adv = rect(img_adv, 22, 455, 280, 630)
    adv_path = SHOTS / "z08_left_panel_advanced.png"
    save(img_adv, adv_path)

    # 6. z09 — center panel; rectangle around status pills row at the top
    img, path = load("z09_center_panel.png")
    w, h = img.size
    print(f"\nz09  {w}×{h}")
    # Status pills row (Pending/Arrived/No-show/Confirmed): x=305–755, y=18–55
    img = rect(img, 305, 18, 755, 55)
    save(img, path)

    # 7. z10 — right panel; rectangle around Client name field
    img, path = load("z10_right_panel.png")
    w, h = img.size
    print(f"\nz10  {w}×{h}")
    # "Client name" label + input: x=765–1090, y=18–55
    img = rect(img, 765, 18, 1090, 55)
    save(img, path)

    # 8. btn02 — save button; arrow pointing at "Save blank appointment" from left
    img, path = load("btn02_save_button_with_client.png")
    w, h = img.size
    print(f"\nbtn02  {w}×{h}")
    # "Save blank appointment" / "Create appointment" button: far right, y≈857–895
    # Arrow tail at x≈700, tip at x≈870 (stopping before the button text)
    mid_y = 876
    img = arrow(img, 700, mid_y, 870, mid_y)
    save(img, path)

    print("\n✅ All annotations applied.")


if __name__ == "__main__":
    annotate_all()
