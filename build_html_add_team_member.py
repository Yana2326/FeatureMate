"""
Convert output/add-team-member/article.md → article.html.

Maps each [Screenshot] marker (in document order) to a real PNG in
screenshots/ — using the 13 fresh PNGs captured for the new dark-sidebar UI.

The article has 14 [Screenshot] markers but only 13 unique screens; the
"Team member card" intro and the "Information tab" section both display
the same default-opened card, so 05_member_card_information.png is reused
for both.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

ART = Path("output/add-team-member/article.md")
OUT = Path("output/add-team-member/article.html")

# Document-order mapping for the 14 [Screenshot] markers in article.md.
SHOT_ORDER = [
    ("01_team_members_list.png",
     "Team members list page — the new dark sidebar shows Favorites with Services, Team (starred), Work Schedule, Appointments, Financial transactions; the main view shows Position / Specialization / System users tabs with members grouped by position"),
    ("02_add_chooser_panel.png",
     "After clicking + Add, a side panel opens with the heading 'You're here to add' and two cards: Position and Employee"),
    ("03_add_form_empty.png",
     "Empty Add new team member form — Name and Specialization fields plus the Team member settings section with Billable / Non-billable radios"),
    ("04_add_form_filled.png",
     "Add new team member form filled with Name 'Anna Smith' and Specialization 'Hair Stylist'; Save button is shown bottom-right"),
    ("05_member_card_information.png",
     "Team member card opens in a side panel — the row of nine tabs is shown at the top: Information, Services, Online booking, Payroll, Work Schedule, Access, Notifications, Settings, Legal information"),
    ("05_member_card_information.png",
     "Information tab — Display name, Position (optional), Specialization fields and the photo upload area; chain banner explains that chain members are read-only at the location level"),
    ("06_member_card_services.png",
     "Services tab — heading 'Team member services'; Assign services and Create a service buttons; service categories listed with provider counts (Haircuts 6 of 6, Yoga Classes 4 of 4, Hair coloring 19 of 19, Packages 1 of 3, Manicure 6 of 17)"),
    ("07_member_card_online_booking.png",
     "Online booking tab — Available / Not available cards at the top; Professional's profile, Description, Preferences, and Available time sections below"),
    ("08_member_card_payroll.png",
     "Payroll tab — Copy from another employee button; Service-based compensation, Product sales compensation sections; Pay a percentage for sold products toggled on with payout value"),
    ("09_member_card_work_schedule.png",
     "Work Schedule tab — the team member's recurring shifts and time-off configuration"),
    ("10_member_card_access.png",
     "Access tab — heading 'System Access' with the Grant system access toggle"),
    ("11_member_card_notifications.png",
     "Notifications tab — 'No access' message with the Assign rights button (visible because system access is not yet granted)"),
    ("12_member_card_settings.png",
     "Settings tab — Appointments (Markup in Appointment Calendar, Hide from Calendar), Statistics (Include in occupancy statistics), Integration (Google Calendar Sync, External ID)"),
    ("13_member_card_legal_info.png",
     "Legal information tab — Name, Last name, Middle name, Citizenship, Gender, ID number, TIN, ID, Employment start date, Registration/patent expiration date, Additional phone number"),
]


def md_inline(text: str) -> str:
    """Convert inline markdown (**bold**, _italic_) to HTML, escaping the rest."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", out)
    return out


def convert(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    shot_idx = 0
    in_ul = in_ol = False
    in_block = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def close_block():
        nonlocal in_block
        if in_block:
            out.append("</blockquote>")
            in_block = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Blank line — close lists, skip
        if not stripped:
            close_lists()
            close_block()
            i += 1
            continue

        # H1
        if stripped.startswith("# "):
            close_lists(); close_block()
            out.append(f"<h1>{md_inline(stripped[2:])}</h1>")
            i += 1
            continue

        # H2
        if stripped.startswith("## "):
            close_lists(); close_block()
            out.append(f"<h2>{md_inline(stripped[3:])}</h2>")
            i += 1
            continue

        # H3
        if stripped.startswith("### "):
            close_lists(); close_block()
            out.append(f"<h3>{md_inline(stripped[4:])}</h3>")
            i += 1
            continue

        # [Screenshot] marker
        if stripped == "[Screenshot]":
            close_lists(); close_block()
            if shot_idx >= len(SHOT_ORDER):
                raise SystemExit(
                    f"More [Screenshot] markers ({shot_idx + 1}) than mapped slots "
                    f"({len(SHOT_ORDER)}). Update SHOT_ORDER."
                )
            fname, alt = SHOT_ORDER[shot_idx]
            shot_idx += 1
            out.append(
                f'<p><img src="screenshots/{fname}" alt="{html.escape(alt)}"></p>'
            )
            i += 1
            continue

        # Blockquote (>)
        if stripped.startswith(">"):
            content = stripped.lstrip(">").strip()
            if not in_block:
                close_lists()
                out.append("<blockquote>")
                in_block = True
            if content:
                # Strip leading **Important** title style → use <strong> + <br>
                if content.startswith("**") and content.endswith("**"):
                    out.append(f"<strong>{md_inline(content[2:-2])}</strong><br>")
                else:
                    out.append(md_inline(content))
            i += 1
            continue
        else:
            close_block()

        # Numbered list
        m_ol = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m_ol:
            if not in_ol:
                close_lists()
                # Start with `start=` if first item is not 1
                start = int(m_ol.group(1))
                if start != 1:
                    out.append(f'<ol start="{start}">')
                else:
                    out.append("<ol>")
                in_ol = True
            content = m_ol.group(2)
            # Look ahead for nested bullet list and continuation lines
            sub_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if re.match(r"^\s+- ", nxt) or (nxt.startswith("   ") and nxt.strip()):
                    sub_lines.append(nxt)
                    j += 1
                else:
                    break
            li_html = md_inline(content)
            if sub_lines:
                # Group nested bullets into <ul>
                inner: list[str] = []
                for sl in sub_lines:
                    sl_strip = sl.strip()
                    if sl_strip.startswith("- "):
                        inner.append(f"<li>{md_inline(sl_strip[2:])}</li>")
                if inner:
                    li_html += "<ul>" + "".join(inner) + "</ul>"
            out.append(f"<li>{li_html}</li>")
            i = j
            continue

        # Bullet list
        if stripped.startswith("- "):
            if not in_ul:
                close_lists()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{md_inline(stripped[2:])}</li>")
            i += 1
            continue

        # Plain paragraph
        close_lists()
        out.append(f"<p>{md_inline(stripped)}</p>")
        i += 1

    close_lists(); close_block()
    return "\n".join(out)


def main() -> None:
    md = ART.read_text()
    body = convert(md)

    if "[Screenshot]" in md:
        markers = md.count("[Screenshot]")
        print(f"Replaced {markers} [Screenshot] markers with <img> tags.")

    html_doc = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        "<title>How to add a team member in Altegio</title>\n"
        "</head>\n"
        "<body>\n\n"
        f"{body}\n\n"
        "</body>\n"
        "</html>\n"
    )

    OUT.write_text(html_doc)
    print(f"✓ Wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
