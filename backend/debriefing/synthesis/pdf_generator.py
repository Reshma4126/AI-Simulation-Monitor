"""
PDF Report Generator for CPR Debriefing System.
Accepts ScoreReport + DebriefReport + FindingRecords.
Produces a formatted clinical debriefing PDF.

Sections:
  1. Cover page
  2. Scenario summary
  3. Domain scores with confidence indicators
  4. Protocol deviations
  5. Communication analysis
  6. Reflective prompts
  7. Recommendations
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether
)

logger = logging.getLogger(__name__)

# ── Colour palette ──────────────────────────────────────────────
PRIMARY     = HexColor("#1F3A5F")   # deep navy
ACCENT      = HexColor("#0F6E56")   # clinical teal
MUTED       = HexColor("#5F5E5A")   # gray
LIGHT_BG    = HexColor("#F4F2EC")   # warm off-white
RULE        = HexColor("#D3D1C7")   # rule line

SEVERITY_COLORS = {
    "critical": HexColor("#A32D2D"),
    "high":     HexColor("#BA7517"),
    "moderate": HexColor("#185FA5"),
    "low":      HexColor("#3B6D11"),
}

CONFIDENCE_COLORS = {
    "high":   HexColor("#3B6D11"),
    "medium": HexColor("#BA7517"),
    "low":    HexColor("#A32D2D"),
}

GRADE_COLORS = {
    "Excellent":    HexColor("#3B6D11"),
    "Good":         HexColor("#185FA5"),
    "Needs Work":   HexColor("#BA7517"),
    "Critical":     HexColor("#A32D2D"),
    "A":            HexColor("#3B6D11"),
    "B":            HexColor("#185FA5"),
    "C":            HexColor("#BA7517"),
    "D":            HexColor("#BA7517"),
    "F":            HexColor("#A32D2D"),
}


# ── Style factory ───────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()

    styles = {}

    styles["title"] = ParagraphStyle(
        "TitleS", parent=base["Title"],
        fontName="Helvetica-Bold", fontSize=22,
        textColor=white, spaceAfter=4,
        leading=26, alignment=TA_LEFT,
    )
    styles["subtitle"] = ParagraphStyle(
        "SubtitleS", parent=base["Normal"],
        fontName="Helvetica", fontSize=11,
        textColor=HexColor("#C8D8E8"),
        spaceAfter=0, leading=14, alignment=TA_LEFT,
    )
    styles["h1"] = ParagraphStyle(
        "H1S", parent=base["Heading1"],
        fontName="Helvetica-Bold", fontSize=14,
        textColor=PRIMARY, spaceBefore=16,
        spaceAfter=8, leading=17,
    )
    styles["h2"] = ParagraphStyle(
        "H2S", parent=base["Heading2"],
        fontName="Helvetica-Bold", fontSize=11.5,
        textColor=ACCENT, spaceBefore=10,
        spaceAfter=5, leading=14,
    )
    styles["body"] = ParagraphStyle(
        "BodyS", parent=base["Normal"],
        fontName="Helvetica", fontSize=10.5,
        textColor=black, leading=15.5,
        spaceAfter=8, alignment=TA_JUSTIFY,
    )
    styles["body_left"] = ParagraphStyle(
        "BodyLS", parent=base["Normal"],
        fontName="Helvetica", fontSize=10.5,
        textColor=black, leading=15.5,
        spaceAfter=6, alignment=TA_LEFT,
    )
    styles["small"] = ParagraphStyle(
        "SmallS", parent=base["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=MUTED, leading=12,
        spaceAfter=4, alignment=TA_LEFT,
    )
    styles["citation"] = ParagraphStyle(
        "CitationS", parent=base["Normal"],
        fontName="Helvetica-Oblique", fontSize=9,
        textColor=MUTED, leading=12,
        spaceAfter=4, alignment=TA_LEFT,
        leftIndent=10,
    )
    styles["callout"] = ParagraphStyle(
        "CalloutS", parent=base["Normal"],
        fontName="Helvetica-Oblique", fontSize=10.5,
        textColor=MUTED, leading=14.5,
        leftIndent=14, rightIndent=14,
        spaceBefore=6, spaceAfter=10,
        alignment=TA_LEFT,
    )
    styles["footer"] = ParagraphStyle(
        "FooterS", parent=base["Normal"],
        fontName="Helvetica", fontSize=8,
        textColor=MUTED, alignment=TA_CENTER,
    )
    return styles


def _hr():
    return HRFlowable(
        width="100%", thickness=0.5,
        color=RULE, spaceBefore=4, spaceAfter=10,
    )


def _table(data, col_widths, header=True, row_colors=None):
    cmds = [
        ("FONTNAME",     (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9.5),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.25, RULE),
        ("LEADING",      (0, 0), (-1, -1), 13),
    ]
    if header:
        cmds += [
            ("BACKGROUND",    (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
            ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ]
    if row_colors:
        for row_idx, color in row_colors.items():
            cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), color))
    return Table(data, colWidths=col_widths, style=TableStyle(cmds))


# ── Page decorations ────────────────────────────────────────────
def _page_decorations(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        2 * cm, 1.2 * cm,
        "CPR Debriefing System  |  Simulation Lab Report"
    )
    canvas.drawRightString(
        A4[0] - 2 * cm, 1.2 * cm,
        f"Page {doc.page}"
    )
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.3)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


def _cover_page_decorations(canvas, doc):
    """Full-bleed navy cover on page 1 only."""
    if doc.page == 1:
        canvas.saveState()
        canvas.setFillColor(PRIMARY)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        # Accent stripe
        canvas.setFillColor(ACCENT)
        canvas.rect(0, A4[1] * 0.42, A4[0], 4, fill=1, stroke=0)
        canvas.restoreState()
    else:
        _page_decorations(canvas, doc)


# ── Section builders ────────────────────────────────────────────

def _build_cover(styles, metadata: dict) -> list:
    s = []
    s.append(Spacer(1, 3.5 * cm))
    s.append(Paragraph(
        "CPR Debriefing Report", styles["title"]
    ))
    s.append(Spacer(1, 0.3 * cm))
    s.append(Paragraph(
        f"Simulation Lab  ·  {metadata.get('date', '')}",
        styles["subtitle"]
    ))
    s.append(Spacer(1, 0.15 * cm))
    s.append(Paragraph(
        f"Session {metadata.get('session_id', '')}  "
        f"·  {metadata.get('scenario_name', '')}",
        styles["subtitle"]
    ))
    s.append(Spacer(1, 0.15 * cm))
    s.append(Paragraph(
        f"Team Leader: {metadata.get('team_leader_name', 'Unknown')}",
        styles["subtitle"]
    ))
    s.append(Spacer(1, 0.15 * cm))
    s.append(Paragraph(
        f"Guideline: {metadata.get('guideline_version', 'AHA 2020')}",
        styles["subtitle"]
    ))
    s.append(PageBreak())
    return s


def _build_scenario_summary(
    styles, metadata: dict, score_report
) -> list:
    s = []
    s.append(Paragraph("1. Scenario summary", styles["h1"]))
    s.append(_hr())

    # Metadata table
    duration_s = metadata.get("duration_ms", 0) // 1000
    duration_str = f"{duration_s // 60}m {duration_s % 60:02d}s"
    meta_data = [
        ["Session ID",    metadata.get("session_id", "—")],
        ["Date",          metadata.get("date", "—")],
        ["Scenario",      metadata.get("scenario_name", "—")],
        ["Scenario type", metadata.get("scenario_type", "—")],
        ["Team leader",   metadata.get("team_leader_name", "—")],
        ["Team size",     str(metadata.get("team_size", "—"))],
        ["Duration",      duration_str],
        ["Guideline",     metadata.get("guideline_version", "AHA 2020")],
    ]
    s.append(_table(
        meta_data,
        col_widths=[5 * cm, 11.5 * cm],
        header=False,
    ))
    s.append(Spacer(1, 12))

    # Score summary strip — handle both object and dict
    def _attr(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    grade       = _attr(score_report, "overall_grade", _attr(score_report, "grade", "—"))
    grade_color = GRADE_COLORS.get(grade, MUTED)
    overall     = _attr(score_report, "overall_score", 0) or 0
    score_display = f"{overall:.0f} / 100" if overall > 1.0 else f"{overall * 100:.0f} / 100"
    n_findings  = _attr(score_report, "total_findings", len(getattr(score_report, "findings", []))) or 0
    by_sev      = _attr(score_report, "findings_by_severity", {}) or {}

    strip = [
        ["Overall score", "Grade", "Findings", "Critical", "High", "Moderate"],
        [
            score_display,
            grade,
            str(n_findings),
            str(by_sev.get("critical", by_sev.get("CRITICAL", 0))),
            str(by_sev.get("high", by_sev.get("HIGH", 0))),
            str(by_sev.get("moderate", by_sev.get("MODERATE", 0))),
        ],
    ]
    strip_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9.5),
        ("BACKGROUND",    (0, 1), (-1, 1), LIGHT_BG),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 1), (-1, 1), 13),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR",     (1, 1), (1, 1), grade_color),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.25, RULE),
    ])
    w = (A4[0] - 4 * cm) / 6
    t = Table(strip, colWidths=[w] * 6, style=strip_style)
    s.append(t)
    return s


def _build_domain_scores(styles, score_report) -> list:
    s = []
    s.append(Paragraph("2. Domain scores", styles["h1"]))
    s.append(_hr())
    s.append(Paragraph(
        "Scores are derived from AHA 2020 guideline rules applied to "
        "SimMan 3G sensor data and audio transcripts. Confidence "
        "indicators reflect data completeness — scores marked medium "
        "or low confidence should not be over-interpreted.",
        styles["body"],
    ))

    domain_scores_raw = getattr(score_report, "domain_scores", []) if not isinstance(score_report, dict) else score_report.get("domain_scores", [])
    if not domain_scores_raw:
        s.append(Paragraph("No domain scores available.", styles["body_left"]))
        return s

    if isinstance(domain_scores_raw, dict):
        items = list(domain_scores_raw.items())
    elif isinstance(domain_scores_raw, list):
        items = []
        for ds in domain_scores_raw:
            if isinstance(ds, dict):
                d_key = ds.get("domain_label", ds.get("domain_key", ds.get("domain", "Domain")))
            else:
                d_key = getattr(ds, "domain_label", getattr(ds, "domain_key", getattr(ds, "domain", "Domain")))
            items.append((d_key, ds))
    else:
        items = []

    rows = [["Domain", "Score", "Confidence", "Key finding"]]
    row_colors = {}
    for i, (domain, ds) in enumerate(items, start=1):
        if isinstance(ds, dict):
            score_val = ds.get("final_score", ds.get("score", 0))
            ci_lower  = ds.get("ci_lower", score_val)
            ci_upper  = ds.get("ci_upper", score_val)
            conf      = ds.get("completeness_flag", ds.get("confidence", "medium"))
            conf_str  = conf.value if hasattr(conf, "value") else str(conf)
            conf_label = conf_str.title() + " confidence"
            key = ds.get("key_finding", "") or "—"
            is_wide = ds.get("is_wide_ci", False)
        else:
            score_val = getattr(ds, "final_score", getattr(ds, "score", 0))
            ci_lower  = getattr(ds, "ci_lower", score_val)
            ci_upper  = getattr(ds, "ci_upper", score_val)
            conf      = getattr(ds, "completeness_flag", getattr(ds, "confidence", "medium"))
            conf_str  = conf.value if hasattr(conf, "value") else str(conf)
            conf_label = conf_str.title() + " confidence"
            key = getattr(ds, "key_finding", "") or "—"
            is_wide = getattr(ds, "is_wide_ci", False)

        score_str = (
            f"{score_val:.0f}/100\n"
            f"CI: {ci_lower:.0f}–{ci_upper:.0f}"
        )
        if is_wide:
            score_str += " ⚠"

        rows.append([
            str(domain).replace("_", " ").title(),
            score_str,
            conf_label,
            key,
        ])

        if str(conf_str).lower() in ["low", "uncertain", "low_data"]:
            row_colors[i] = HexColor("#FFF4F4")

    s.append(_table(
        rows,
        col_widths=[4.5 * cm, 3.5 * cm, 4 * cm, 4.5 * cm],
        row_colors=row_colors,
    ))

    warnings = getattr(score_report, "data_completeness_warnings", []) if not isinstance(score_report, dict) else score_report.get("data_completeness_warnings", [])
    if warnings:
        s.append(Spacer(1, 6))
        for w in warnings:
            s.append(Paragraph(f"⚠  {w}", styles["small"]))

    return s


def _build_protocol_deviations(
    styles, findings: list
) -> list:
    s = []
    s.append(Paragraph("3. Protocol deviations", styles["h1"]))
    s.append(_hr())

    if not findings:
        s.append(Paragraph(
            "No protocol deviations detected.", styles["body_left"]
        ))
        return s

    def _get_sev(f):
        if isinstance(f, dict):
            return str(f.get("severity", "info")).lower()
        sev = getattr(f, "severity", "info")
        return str(sev.value if hasattr(sev, "value") else sev).lower()

    sev_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings,
        key=lambda f: sev_order.get(_get_sev(f), 4)
    )

    for finding in sorted_findings:
        sev = _get_sev(finding)
        sev_color = SEVERITY_COLORS.get(sev, MUTED)
        if isinstance(finding, dict):
            ts_ms = int(finding.get("timestamp_sec", 0) * 1000) if finding.get("timestamp_sec") else finding.get("timestamp_ms", 0)
            f_title = finding.get("rule_id", finding.get("title", "—"))
            f_desc = finding.get("deviation_message", finding.get("description", ""))
        else:
            ts_ms = getattr(finding, "timestamp_ms", 0)
            f_title = getattr(finding, "title", "—")
            f_desc = getattr(finding, "description", "")

        ts_s = ts_ms // 1000
        ts_str = f"{ts_s // 60}:{ts_s % 60:02d}"

        block = []

        # Finding header row
        header = _table(
            [[
                Paragraph(
                    f"<b>{sev.upper()}</b>",
                    ParagraphStyle(
                        "SevP", fontName="Helvetica-Bold",
                        fontSize=9, textColor=white,
                    )
                ),
                Paragraph(
                    f"<b>{f_title}</b>",
                    ParagraphStyle(
                        "TitleP", fontName="Helvetica-Bold",
                        fontSize=10.5, textColor=PRIMARY,
                    )
                ),
                Paragraph(
                    f"@ {ts_str}",
                    ParagraphStyle(
                        "TimeP", fontName="Helvetica",
                        fontSize=9, textColor=MUTED,
                        alignment=TA_RIGHT,
                    )
                ),
            ]],
            col_widths=[2 * cm, 11 * cm, 3.5 * cm],
            header=False,
        )
        header.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), sev_color),
            ("BACKGROUND",    (1, 0), (-1, 0), LIGHT_BG),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ]))
        block.append(header)

        # Description
        block.append(Paragraph(
            f_desc,
            styles["body_left"]
        ))

        # Guideline citation
        f_citation = finding.get("guideline", finding.get("guideline_citation", "")) if isinstance(finding, dict) else getattr(finding, "guideline_citation", "")
        if f_citation:
            block.append(Paragraph(
                f"Guideline reference: {f_citation}",
                styles["citation"]
            ))

        # Finding ID for traceability
        fid = finding.get("finding_id", "") if isinstance(finding, dict) else getattr(finding, "finding_id", "")
        if fid:
            block.append(Paragraph(
                f"Finding ID: {fid}",
                styles["small"]
            ))

        block.append(Spacer(1, 8))
        s.append(KeepTogether(block))

    return s


def _build_communication_analysis(
    styles, debrief_report, score_report
) -> list:
    s = []
    s.append(Paragraph("4. Communication analysis", styles["h1"]))
    s.append(_hr())

    # Read directly from DebriefReport dataclass field
    comm_text = ""
    if debrief_report:
        section = getattr(debrief_report, "communication_analysis", None)
        if section and hasattr(section, "content"):
            comm_text = section.content or ""
        elif isinstance(section, str):
            comm_text = section

    if comm_text:
        s.append(Paragraph(comm_text, styles["body"]))
    else:
        s.append(Paragraph(
            "Detailed communication analysis requires audio transcription. "
            "Ensure lapel and ceiling mic audio files are provided for "
            "full closed-loop communication metrics.",
            styles["callout"]
        ))

    return s


def _build_reflective_prompts(
    styles, findings: list, debrief_report
) -> list:
    s = []
    s.append(Paragraph("5. Reflective prompts", styles["h1"]))
    s.append(_hr())
    s.append(Paragraph(
        "The following questions are mapped to specific findings "
        "detected during this session. Use them to guide the "
        "debriefing conversation with the team leader.",
        styles["body"],
    ))

    # Read directly from DebriefReport dataclass field
    prompts_text = ""
    if debrief_report:
        section = getattr(debrief_report, "reflective_prompts", None)
        if section and hasattr(section, "content"):
            prompts_text = section.content or ""
        elif isinstance(section, str):
            prompts_text = section

    if prompts_text:
        s.append(Paragraph(prompts_text, styles["body"]))
    else:
        sev_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        sorted_findings = sorted(
            findings,
            key=lambda f: sev_order.get(
                f.severity.value
                if hasattr(f.severity, "value") else f.severity, 4
            )
        )[:6]
        for i, finding in enumerate(sorted_findings, 1):
            prompt = getattr(finding, "reflective_prompt", "")
            if prompt:
                s.append(Paragraph(
                    f"<b>{i}.</b> {prompt}",
                    styles["body_left"]
                ))
                s.append(Spacer(1, 4))

    return s


def _build_recommendations(
    styles, findings: list, debrief_report
) -> list:
    s = []
    s.append(Paragraph("6. Recommendations", styles["h1"]))
    s.append(_hr())
    s.append(Paragraph(
        "Ranked by clinical impact. Address critical and high-severity "
        "findings before moderate ones in the next training session.",
        styles["body"],
    ))

    # Read directly from DebriefReport dataclass field
    rec_text = ""
    if debrief_report:
        section = getattr(debrief_report, "recommendations", None)
        if section and hasattr(section, "content"):
            rec_text = section.content or ""
        elif isinstance(section, str):
            rec_text = section

    if rec_text:
        s.append(Paragraph(rec_text, styles["body"]))
    else:
        seen = set()
        rank = 1
        sev_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        sorted_findings = sorted(
            findings,
            key=lambda f: sev_order.get(
                f.severity.value
                if hasattr(f.severity, "value") else f.severity, 4
            )
        )
        for finding in sorted_findings:
            rec = getattr(finding, "recommendation", "")
            if rec and rec not in seen:
                seen.add(rec)
                s.append(Paragraph(
                    f"<b>{rank}.</b> {rec}",
                    styles["body_left"]
                ))
                rank += 1
                if rank > 8:
                    break

    return s


def _build_strengths(styles, debrief_report) -> list:
    s = []
    s.append(Paragraph("7. Strengths", styles["h1"]))
    s.append(_hr())

    # Read directly from DebriefReport dataclass field
    strengths_text = ""
    if debrief_report:
        section = getattr(debrief_report, "strengths", None)
        if section and hasattr(section, "content"):
            strengths_text = section.content or ""
        elif isinstance(section, str):
            strengths_text = section

    if strengths_text:
        s.append(Paragraph(strengths_text, styles["body"]))
    else:
        s.append(Paragraph(
            "No strengths data available from narrative synthesis.",
            styles["callout"]
        ))

    return s


# ── Main entry point ────────────────────────────────────────────

def generate_pdf(
    score_report,
    findings: list,
    timeline,
    output_path,
    debrief_report=None,
) -> Path:
    """
    Generate the full debriefing PDF.

    Args:
        score_report:   ScoreReport from scoring_engine
        findings:       List of FindingRecord from ACLS FSM
        timeline:       UnifiedTimeline (or any object with session fields)
        output_path:    Where to write the PDF (str or Path)
        debrief_report: Optional DebriefReport from claude_api

    Returns:
        Path to the generated PDF
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()

    # Build metadata dict from timeline
    metadata = {
        "session_id":        getattr(timeline, "session_id",        "—"),
        "date":              getattr(timeline, "session_date",
                             getattr(timeline, "date",               "—")),
        "scenario_name":     getattr(timeline, "scenario_name",      "—"),
        "scenario_type":     getattr(timeline, "scenario_type",      "—"),
        "team_leader_name":  getattr(timeline, "team_leader_name",
                             getattr(timeline, "team_leader_id",     "—")),
        "team_size":         getattr(timeline, "team_size",          "—"),
        "duration_ms":       getattr(timeline, "duration_ms",        0),
        "guideline_version": getattr(timeline, "guideline_version",  "AHA 2020"),
    }

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"CPR Debrief — {metadata['session_id']}",
        author="CPR Debriefing System",
    )

    story = []
    story += _build_cover(styles, metadata)
    story += _build_scenario_summary(styles, metadata, score_report)
    story.append(Spacer(1, 10))
    story += _build_domain_scores(styles, score_report)
    story.append(PageBreak())
    story += _build_protocol_deviations(styles, findings)
    story.append(PageBreak())
    story += _build_communication_analysis(styles, debrief_report, score_report)
    story.append(Spacer(1, 10))
    story += _build_strengths(styles, debrief_report)
    story.append(PageBreak())
    story += _build_reflective_prompts(styles, findings, debrief_report)
    story.append(PageBreak())
    story += _build_recommendations(styles, findings, debrief_report)

    doc.build(
        story,
        onFirstPage=_cover_page_decorations,
        onLaterPages=_page_decorations,
    )

    logger.info(f"PDF generated: {output_path}")
    return output_path
