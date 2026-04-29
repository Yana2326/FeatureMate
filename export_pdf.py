"""
export_pdf.py — Convert a KB article (Markdown + screenshots) to a styled PDF.

Usage (standalone):
    python export_pdf.py output/create-appointment/

Programmatic:
    from export_pdf import export_pdf
    export_pdf(Path("output/create-appointment/article.md"),
               Path("output/create-appointment/screenshots"),
               Path("output/create-appointment/article.pdf"))
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Page geometry ────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4               # 595 × 842 pt
MARGIN_H = 22 * mm               # left / right
MARGIN_V = 20 * mm               # top / bottom
BODY_W   = PAGE_W - 2 * MARGIN_H # usable text width ≈ 463 pt

# ── Colour palette ───────────────────────────────────────────────────────────
C_TITLE   = colors.HexColor("#111827")   # near-black
C_H2      = colors.HexColor("#1F2937")
C_BODY    = colors.HexColor("#374151")
C_MUTED   = colors.HexColor("#6B7280")
C_RED     = colors.HexColor("#DC2626")   # Important label
C_BG_IMP  = colors.HexColor("#FFF5F5")  # Important block background
C_BORDER  = colors.HexColor("#E5E7EB")  # rule / borders
C_NUM     = colors.HexColor("#2563EB")  # step numbers
C_IMG_BG  = colors.HexColor("#F9FAFB")  # image container fill

# ── Styles ───────────────────────────────────────────────────────────────────
def _styles() -> dict[str, ParagraphStyle]:
    base = dict(
        fontName="Helvetica",
        fontSize=10.5,
        leading=16,
        textColor=C_BODY,
        spaceAfter=4,
    )
    return {
        "h1": ParagraphStyle("h1",
            fontName="Helvetica-Bold", fontSize=22, leading=28,
            textColor=C_TITLE, spaceAfter=6, spaceBefore=0),
        "h1_sub": ParagraphStyle("h1_sub",
            fontName="Helvetica", fontSize=11, leading=16,
            textColor=C_MUTED, spaceAfter=14),
        "h2": ParagraphStyle("h2",
            fontName="Helvetica-Bold", fontSize=14, leading=20,
            textColor=C_H2, spaceBefore=18, spaceAfter=6),
        "body": ParagraphStyle("body", **base, alignment=TA_JUSTIFY),
        "step_num": ParagraphStyle("step_num",
            fontName="Helvetica-Bold", fontSize=10.5, leading=16,
            textColor=C_NUM),
        "step_text": ParagraphStyle("step_text",
            fontName="Helvetica", fontSize=10.5, leading=16,
            textColor=C_BODY, alignment=TA_JUSTIFY),
        "bullet": ParagraphStyle("bullet",
            fontName="Helvetica", fontSize=10.5, leading=16,
            textColor=C_BODY, leftIndent=14, spaceAfter=3),
        "bq_label": ParagraphStyle("bq_label",
            fontName="Helvetica-Bold", fontSize=10, leading=14,
            textColor=C_RED),
        "bq_body": ParagraphStyle("bq_body",
            fontName="Helvetica", fontSize=10, leading=14,
            textColor=C_BODY),
        "img_caption": ParagraphStyle("img_caption",
            fontName="Helvetica", fontSize=8.5, leading=12,
            textColor=C_MUTED, alignment=TA_CENTER, spaceAfter=10),
        "footer": ParagraphStyle("footer",
            fontName="Helvetica", fontSize=8, leading=10,
            textColor=C_MUTED, alignment=TA_CENTER),
    }


# ── Inline markdown → ReportLab XML ─────────────────────────────────────────
def _rl(text: str) -> str:
    """Convert **bold** and `code` spans to ReportLab paragraph markup."""
    # Escape XML special chars first (except our own tags)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # **bold**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # `code`
    text = re.sub(r'`(.+?)`',
                  r'<font name="Courier" size="9" color="#1F2937">\1</font>', text)
    return text


# ── Image helper ─────────────────────────────────────────────────────────────
IMG_CELL_PAD = 8       # pt — padding on each side inside the image cell
IMG_MAX_W    = BODY_W - 2 * IMG_CELL_PAD   # usable width inside padded cell
IMG_MAX_H    = 320     # pt — cap so tall panel crops don't dominate the page
IMG_NARROW_W = 260     # pt — max for portrait / panel-style images

def _make_image(img_path: Path) -> RLImage | None:
    if not img_path.exists():
        return None
    try:
        with PILImage.open(img_path) as pil:
            px_w, px_h = pil.size
    except Exception:
        return None

    # Choose display size: fit within bounding box preserving aspect ratio.
    # Portrait crops get a narrower max width so they don't look blown-up.
    if px_h > px_w:                         # portrait / panel crop
        max_w = min(IMG_NARROW_W, IMG_MAX_W)
    else:
        max_w = IMG_MAX_W

    scale = min(max_w / px_w, IMG_MAX_H / px_h, 1.0)
    disp_w = px_w * scale
    disp_h = px_h * scale
    return RLImage(str(img_path), width=disp_w, height=disp_h)


# ── Markdown block parser ────────────────────────────────────────────────────
# Returns a list of (type, *data) tuples.
#
# Types: h1 h2 body numbered bullet image blockquote space

_IMG_RE  = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
_NUM_RE  = re.compile(r'^(\d+)\.\s+(.*)')
_BUL_RE  = re.compile(r'^[-*]\s+(.*)')

def _parse(text: str, article_dir: Path) -> list[tuple]:
    blocks: list[tuple] = []
    in_bq   = False
    bq_buf: list[str] = []
    skip    = False   # drop Self-check report section

    def flush_bq():
        nonlocal in_bq, bq_buf
        if bq_buf:
            blocks.append(("blockquote", "\n".join(bq_buf)))
            bq_buf = []
        in_bq = False

    for raw in text.splitlines():
        line = raw.rstrip()

        # ── Self-check section: skip to EOF ──────────────────────────────
        if re.match(r'^##\s+Self-check report', line):
            skip = True
        if skip:
            continue

        # ── Blockquote accumulation ───────────────────────────────────────
        if line.startswith("> "):
            flush_bq() if not in_bq and bq_buf else None
            in_bq = True
            bq_buf.append(line[2:])
            continue
        elif in_bq:
            flush_bq()

        # ── Headings ─────────────────────────────────────────────────────
        if re.match(r'^# [^#]', line):
            blocks.append(("h1", line[2:].strip()))
        elif re.match(r'^## ', line):
            blocks.append(("h2", line[3:].strip()))

        # ── Images ───────────────────────────────────────────────────────
        elif m := _IMG_RE.match(line):
            alt, rel_path = m.group(1), m.group(2)
            blocks.append(("image", alt, article_dir / rel_path))

        # ── Numbered list ─────────────────────────────────────────────────
        elif m := _NUM_RE.match(line):
            blocks.append(("numbered", m.group(1), m.group(2)))

        # ── Bullet list ───────────────────────────────────────────────────
        elif m := _BUL_RE.match(line):
            blocks.append(("bullet", m.group(1)))

        # ── Blank line ────────────────────────────────────────────────────
        elif not line.strip():
            blocks.append(("space",))

        # ── Plain paragraph ───────────────────────────────────────────────
        else:
            blocks.append(("body", line.strip()))

    flush_bq()
    return blocks


# ── Flowable builders ────────────────────────────────────────────────────────

def _numbered_row(num: str, text: str, S: dict) -> Table:
    """A two-column table: step number | step text — keeps them on one line."""
    num_p  = Paragraph(num + ".", S["step_num"])
    text_p = Paragraph(_rl(text), S["step_text"])
    t = Table([[num_p, text_p]],
              colWidths=[22, BODY_W - 22],
              hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ("TOPPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    return t


def _blockquote_flowable(raw: str, S: dict) -> Table:
    """Render a > Important / > Note block as a tinted box with red label."""
    lines  = raw.splitlines()
    items  = []

    for ln in lines:
        # Strip bold markdown from the label line
        label_m = re.match(r'\*\*(Important|Note|Warning|Example)\*\*', ln)
        if label_m:
            items.append(Paragraph(label_m.group(1).upper(), S["bq_label"]))
        elif ln.strip():
            items.append(Paragraph(_rl(ln), S["bq_body"]))

    # Pack into a single-cell table for background + left border
    inner = Table([[items]], colWidths=[BODY_W - 24], hAlign="LEFT")
    inner.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C_BG_IMP),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [4, 4, 4, 4]),
        ("LINEBEFORE",   (0, 0), (0, -1), 3, C_RED),
    ]))
    return inner


def _image_flowable(alt: str, img_path: Path, S: dict) -> list:
    """Return [image_table, spacer]; falls back to alt-text on missing file."""
    rl_img = _make_image(img_path)
    if rl_img is None:
        return [Paragraph(f"[Image not found: {img_path.name}]", S["img_caption"]),
                Spacer(1, 6)]

    # Center image in a shaded cell; colWidths caps the table to BODY_W.
    cell = Table([[rl_img]], colWidths=[BODY_W], hAlign="CENTER")
    cell.setStyle(TableStyle([
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND",   (0, 0), (-1, -1), C_IMG_BG),
        ("TOPPADDING",   (0, 0), (-1, -1), IMG_CELL_PAD),
        ("BOTTOMPADDING",(0, 0), (-1, -1), IMG_CELL_PAD),
        ("LEFTPADDING",  (0, 0), (-1, -1), IMG_CELL_PAD),
        ("RIGHTPADDING", (0, 0), (-1, -1), IMG_CELL_PAD),
        ("BOX",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [4, 4, 4, 4]),
    ]))
    return [Spacer(1, 4), cell, Spacer(1, 10)]


# ── Header / footer ──────────────────────────────────────────────────────────

def _on_page(canvas, doc):
    """Draw page number in the footer on every page except the first."""
    page = doc.page
    if page == 1:
        return
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_MUTED)
    canvas.drawCentredString(PAGE_W / 2, 12 * mm, str(page))
    canvas.restoreState()


# ── Main entry point ─────────────────────────────────────────────────────────

def export_pdf(article_path: Path,
               screenshots_dir: Path,
               output_path: Path) -> None:
    """
    Convert *article_path* (Markdown) + screenshots to a PDF at *output_path*.
    """
    md_text = article_path.read_text(encoding="utf-8")
    article_dir = article_path.parent
    S = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN_H, rightMargin=MARGIN_H,
        topMargin=MARGIN_V,  bottomMargin=MARGIN_V + 8 * mm,
        title=article_path.stem.replace("-", " ").title(),
    )

    story: list = []
    blocks = _parse(md_text, article_dir)

    prev_type = None
    for block in blocks:
        btype = block[0]

        if btype == "h1":
            title_text = block[1]
            story += [
                Paragraph(_rl(title_text), S["h1"]),
                HRFlowable(width="100%", thickness=1.5,
                           color=C_BORDER, spaceAfter=10),
            ]

        elif btype == "h2":
            # Keep heading with whatever follows (avoids orphan heading)
            story.append(Spacer(1, 4))
            story.append(Paragraph(_rl(block[1]), S["h2"]))
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=C_BORDER, spaceAfter=6))

        elif btype == "body":
            story.append(Paragraph(_rl(block[1]), S["body"]))

        elif btype == "numbered":
            story.append(_numbered_row(block[1], block[2], S))

        elif btype == "bullet":
            story.append(Paragraph("• " + _rl(block[1]), S["bullet"]))

        elif btype == "blockquote":
            story.append(Spacer(1, 6))
            story.append(_blockquote_flowable(block[1], S))
            story.append(Spacer(1, 8))

        elif btype == "image":
            story += _image_flowable(block[1], block[2], S)

        elif btype == "space":
            # Suppress double-spaces; single blank line → small gap
            if prev_type not in ("space", "h1", "h2"):
                story.append(Spacer(1, 5))

        prev_type = btype

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    size_kb = output_path.stat().st_size // 1024
    print(f"  ✅ PDF saved → {output_path}  ({size_kb} KB)")


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python export_pdf.py <output-folder>")
        print("Example: python export_pdf.py output/create-appointment/")
        sys.exit(1)

    folder = Path(sys.argv[1])
    art    = folder / "article.md"
    shots  = folder / "screenshots"
    out    = folder / "article.pdf"

    if not art.exists():
        print(f"Error: {art} not found")
        sys.exit(1)

    print(f"Exporting PDF from {art} …")
    export_pdf(art, shots, out)
