"""
Render article.html → article.pdf using headless Chromium via Playwright.
Uses an isolated browser profile — never touches the user's personal Chrome.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
HTML_PATH = HERE / "output/integrations-overview/article.html"
PDF_PATH  = HERE / "output/integrations-overview/article.pdf"

# Minimal print stylesheet — clean professional layout, no custom CSS in the HTML itself.
PRINT_CSS = """
@page { size: A4; margin: 20mm 18mm; }
body {
    font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #222;
    max-width: 170mm;
    margin: 0 auto;
}
h1 { font-size: 22pt; margin: 0 0 10mm 0; color: #111; line-height: 1.2; }
h2 { font-size: 15pt; margin: 8mm 0 3mm 0; color: #111; page-break-after: avoid; }
h3 { font-size: 12pt; margin: 5mm 0 2mm 0; color: #333; page-break-after: avoid; }
p  { margin: 0 0 3mm 0; }
ul, ol { margin: 0 0 4mm 0; padding-left: 6mm; }
li { margin-bottom: 1.2mm; }
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 3mm auto 4mm auto;
    border: 1px solid #e4e4e4;
    border-radius: 3px;
    page-break-inside: avoid;
}
blockquote {
    margin: 4mm 0;
    padding: 3mm 4mm;
    border-left: 3px solid #e6b800;
    background: #fffbea;
    page-break-inside: avoid;
}
strong { color: #111; }
"""

with sync_playwright() as pw:
    # Fresh isolated Chromium — no CDP attach, no user profile reuse.
    browser = pw.chromium.launch(
        headless=True,
        args=["--lang=en-US", "--no-sandbox"]
    )
    ctx  = browser.new_context(locale="en-US")
    page = ctx.new_page()

    page.goto(f"file://{HTML_PATH}", wait_until="networkidle")
    page.add_style_tag(content=PRINT_CSS)
    page.wait_for_timeout(500)

    page.pdf(
        path=str(PDF_PATH),
        format="A4",
        margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"},
        print_background=True,
    )
    browser.close()

size_kb = PDF_PATH.stat().st_size / 1024
print(f"✓ Wrote {PDF_PATH} ({size_kb:.0f} KB)")
