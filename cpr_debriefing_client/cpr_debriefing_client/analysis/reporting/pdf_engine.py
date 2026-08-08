"""
PDF Generation Engine
=====================
Takes a JSON input file and generates a styled PDF report.

Usage:
    python pdf_engine.py input.json output.pdf

JSON Schema:
    See example_input.json for a full example.
"""

import json
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.platypus.flowables import Flowable


# ─────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────
THEME = {
    "primary":       colors.HexColor("#1B3A6B"),   # deep navy
    "accent":        colors.HexColor("#2E86AB"),   # teal blue
    "accent_light":  colors.HexColor("#E8F4F8"),   # very light teal
    "success":       colors.HexColor("#27AE60"),
    "warning":       colors.HexColor("#F39C12"),
    "danger":        colors.HexColor("#E74C3C"),
    "table_header":  colors.HexColor("#1B3A6B"),
    "table_alt":     colors.HexColor("#F0F4FA"),
    "table_border":  colors.HexColor("#CBD5E1"),
    "text":          colors.HexColor("#1A1A2E"),
    "muted":         colors.HexColor("#64748B"),
    "white":         colors.white,
    "section_bg":    colors.HexColor("#F8FAFD"),
}

SEVERITY_COLORS = {
    "excellent": colors.HexColor("#27AE60"),
    "very good": colors.HexColor("#2980B9"),
    "good":      colors.HexColor("#8E44AD"),
    "moderate":  colors.HexColor("#F39C12"),
    "mild":      colors.HexColor("#E67E22"),
    "severe":    colors.HexColor("#E74C3C"),
    "partial":   colors.HexColor("#F39C12"),
    "present":   colors.HexColor("#27AE60"),
}

W, H = A4
MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 20 * mm
MARGIN_B = 18 * mm
CONTENT_W = W - MARGIN_L - MARGIN_R


# ─────────────────────────────────────────────
#  STYLES
# ─────────────────────────────────────────────
def make_styles():
    return {
        "doc_title": ParagraphStyle(
            "doc_title",
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=22,
            textColor=THEME["white"],
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "doc_subtitle": ParagraphStyle(
            "doc_subtitle",
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#BFD9F0"),
            alignment=TA_CENTER,
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=THEME["primary"],
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=THEME["text"],
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=THEME["text"],
            leftIndent=12,
            spaceBefore=1,
            spaceAfter=1,
            bulletIndent=4,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=THEME["white"],
            alignment=TA_LEFT,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=THEME["text"],
        ),
        "table_cell_bold": ParagraphStyle(
            "table_cell_bold",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=THEME["primary"],
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=THEME["muted"],
        ),
        "label": ParagraphStyle(
            "label",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=THEME["muted"],
            spaceAfter=1,
        ),
        "meta_value": ParagraphStyle(
            "meta_value",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=THEME["primary"],
        ),
    }


# ─────────────────────────────────────────────
#  HEADER / FOOTER CANVAS
# ─────────────────────────────────────────────
class HeaderFooterCanvas(canvas.Canvas):
    def __init__(self, *args, doc_meta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._doc_meta = doc_meta or {}
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_header_footer(total)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_header_footer(self, total_pages):
        page = self._pageNumber
        w, h = A4

        # ── Header bar ──
        self.setFillColor(THEME["primary"])
        self.rect(0, h - 52, w, 52, fill=1, stroke=0)

        # Logo/brand strip
        self.setFillColor(THEME["accent"])
        self.rect(0, h - 52, 6, 52, fill=1, stroke=0)

        # Title
        title = self._doc_meta.get("title", "Report")
        subtitle = self._doc_meta.get("subtitle", "")
        self.setFillColor(colors.white)
        self.setFont("Helvetica-Bold", 13)
        self.drawString(MARGIN_L, h - 26, title)
        self.setFont("Helvetica", 8.5)
        self.setFillColor(colors.HexColor("#BFD9F0"))
        self.drawString(MARGIN_L, h - 40, subtitle)

        # Date top right
        date_str = self._doc_meta.get("date", datetime.today().strftime("%d %b %Y"))
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#BFD9F0"))
        self.drawRightString(w - MARGIN_R, h - 26, date_str)

        # ── Footer ──
        self.setStrokeColor(THEME["table_border"])
        self.setLineWidth(0.4)
        self.line(MARGIN_L, 22, w - MARGIN_R, 22)

        self.setFillColor(THEME["muted"])
        self.setFont("Helvetica", 7.5)
        org = self._doc_meta.get("organization", "")
        self.drawString(MARGIN_L, 12, org)
        self.drawRightString(w - MARGIN_R, 12, f"Page {page} of {total_pages}")


# ─────────────────────────────────────────────
#  COLORED BADGE (inline rating chips)
# ─────────────────────────────────────────────
class Badge(Flowable):
    """A small coloured pill badge."""
    def __init__(self, text, color=None):
        super().__init__()
        self.text = text
        key = text.lower()
        self.bg = color or SEVERITY_COLORS.get(key, THEME["accent"])
        self.width = len(text) * 5.5 + 12
        self.height = 13

    def draw(self):
        self.canv.setFillColor(self.bg)
        self.canv.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        self.canv.setFillColor(colors.white)
        self.canv.setFont("Helvetica-Bold", 7.5)
        self.canv.drawCentredString(self.width / 2, 3.5, self.text)


# ─────────────────────────────────────────────
#  BUILDER HELPERS
# ─────────────────────────────────────────────
def divider(story):
    story.append(HRFlowable(
        width="100%", thickness=0.4,
        color=THEME["table_border"],
        spaceBefore=4, spaceAfter=6
    ))


def section_heading(title, styles, story):
    story.append(Spacer(1, 4))
    story.append(Paragraph(title.upper(), styles["section_heading"]))
    story.append(HRFlowable(
        width="100%", thickness=1.5,
        color=THEME["accent"],
        spaceBefore=0, spaceAfter=5
    ))


def build_table(rows, col_widths, styles, *, badge_col=None, bold_col0=True):
    """
    rows: list of [col, col, …]
    badge_col: index of column to render as Badge (e.g. severity)
    """
    table_data = []
    # header
    header = [Paragraph(str(c), styles["table_header"]) for c in rows[0]]
    table_data.append(header)

    for i, row in enumerate(rows[1:], start=1):
        cells = []
        for j, cell in enumerate(row):
            text = str(cell) if cell is not None else ""
            if j == 0 and bold_col0:
                cells.append(Paragraph(text, styles["table_cell_bold"]))
            elif j == badge_col and text:
                # Colour the cell text directly
                key = text.lower()
                bg = SEVERITY_COLORS.get(key, THEME["accent"])
                style = ParagraphStyle(
                    "badge_cell",
                    parent=styles["table_cell"],
                    textColor=bg,
                    fontName="Helvetica-Bold",
                )
                cells.append(Paragraph(text, style))
            else:
                cells.append(Paragraph(text, styles["table_cell"]))
        table_data.append(cells)

    # alternating row colours
    row_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), THEME["table_header"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [THEME["white"], THEME["table_alt"]]),
        ("GRID", (0, 0), (-1, -1), 0.35, THEME["table_border"]),
        ("LINEBELOW", (0, 0), (-1, 0), 0, THEME["table_header"]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(row_styles))
    return t


# ─────────────────────────────────────────────
#  COVER HEADER BLOCK  (inside content flow)
# ─────────────────────────────────────────────
def build_cover_block(meta, styles, story):
    # Meta info grid below header
    info = meta.get("info", {})
    if not info:
        return

    cols = list(info.items())
    half = (len(cols) + 1) // 2
    left_cols = cols[:half]
    right_cols = cols[half:]

    col_data = []
    for i in range(max(len(left_cols), len(right_cols))):
        row = []
        for col_set in (left_cols, right_cols):
            if i < len(col_set):
                k, v = col_set[i]
                row.append(Paragraph(k, styles["label"]))
                row.append(Paragraph(str(v), styles["meta_value"]))
            else:
                row.extend([Paragraph("", styles["label"]), Paragraph("", styles["label"])])
        col_data.append(row)

    cw = CONTENT_W / 4
    t = Table(col_data, colWidths=[cw * 0.6, cw * 1.4, cw * 0.6, cw * 1.4])
    t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), THEME["accent_light"]),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("BOX", (0, 0), (-1, -1), 0.5, THEME["accent"]),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))


# ─────────────────────────────────────────────
#  SECTION RENDERERS
# ─────────────────────────────────────────────
def render_section(section, styles, story):
    stype = section.get("type", "table")
    title = section.get("title", "")

    if title:
        section_heading(title, styles, story)

    if stype == "table":
        _render_table_section(section, styles, story)
    elif stype == "bullets":
        _render_bullets_section(section, styles, story)
    elif stype == "two_column_bullets":
        _render_two_col_bullets(section, styles, story)
    elif stype == "text":
        story.append(Paragraph(section.get("content", ""), styles["body"]))
    elif stype == "page_break":
        story.append(PageBreak())

    story.append(Spacer(1, 6))


def _render_table_section(section, styles, story):
    rows = section.get("rows", [])
    if not rows:
        return
    ncols = len(rows[0])
    badge_col = section.get("badge_col", None)
    # auto col widths: equal split
    raw_widths = section.get("col_widths", None)
    if raw_widths:
        col_widths = [CONTENT_W * w for w in raw_widths]
    else:
        col_widths = [CONTENT_W / ncols] * ncols

    t = build_table(rows, col_widths, styles, badge_col=badge_col)
    story.append(KeepTogether([t]))


def _render_bullets_section(section, styles, story):
    items = section.get("items", [])
    for item in items:
        story.append(Paragraph(f"• {item}", styles["bullet"]))


def _render_two_col_bullets(section, styles, story):
    items = section.get("items", [])
    half = (len(items) + 1) // 2
    left = items[:half]
    right = items[half:]

    rows = []
    for i in range(max(len(left), len(right))):
        l_txt = f"• {left[i]}" if i < len(left) else ""
        r_txt = f"• {right[i]}" if i < len(right) else ""
        rows.append([
            Paragraph(l_txt, styles["bullet"]),
            Paragraph(r_txt, styles["bullet"]),
        ])

    t = Table(rows, colWidths=[CONTENT_W * 0.5, CONTENT_W * 0.5])
    t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)


# ─────────────────────────────────────────────
#  MAIN GENERATOR
# ─────────────────────────────────────────────
def generate_pdf(input_json: dict, output_path: str):
    meta = input_json.get("meta", {})
    sections = input_json.get("sections", [])

    styles = make_styles()

    doc_meta = {
        "title": meta.get("title", "Report"),
        "subtitle": meta.get("subtitle", ""),
        "date": meta.get("date", datetime.today().strftime("%d %b %Y")),
        "organization": meta.get("organization", ""),
    }

    def canvas_factory(filename, **kw):
        return HeaderFooterCanvas(filename, doc_meta=doc_meta, **kw)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T + 40,   # leave room for header
        bottomMargin=MARGIN_B + 20,
    )

    story = []

    # Cover info block
    build_cover_block(meta, styles, story)

    # Sections
    for sec in sections:
        render_section(sec, styles, story)

    doc.build(story, canvasmaker=canvas_factory)
    print(f"[OK] PDF written to: {output_path}")


# ─────────────────────────────────────────────
#  CLI ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python pdf_engine.py <input.json> <output.pdf>")
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        data = json.load(f)

    generate_pdf(data, sys.argv[2])
