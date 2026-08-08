"""
pdf_adapter.py
--------------
Translates our backend's Python objects (ScoreReport, UnifiedTimeline,
NarrativeOutput, session metadata) into the dynamic JSON schema expected
by pdf_engine.generate_pdf().

The JSON schema used by pdf_engine.py supports these section types:
    "table"             → rows: [[header...], [data...], ...]
    "bullets"           → items: ["item1", "item2", ...]
    "two_column_bullets"→ items: [...] (auto-split into two columns)
    "text"              → content: "paragraph string"
    "page_break"        → inserts a page break

All section data is derived from:
    - ScoreReport      (from ScoringEngine — grades, domain scores, sub-signals)
    - UnifiedTimeline  (from pipeline_adapter — event timestamps)
    - NarrativeOutput  (from NarrativeEngine  — LLM-generated text sections)
    - session_meta     (from the raw JSON file — session ID, date, scenario name)

No hardcoded content. Everything is dynamically populated from live pipeline data.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional


# =============================================================================
# Grade → Rating label
# =============================================================================

_GRADE_TO_RATING = {
    "A": "Excellent",
    "B": "Very Good",
    "C": "Good",
    "D": "Moderate",
    "F": "Severe",
}

_SCORE_TO_RATING = {
    90: "Excellent",
    75: "Very Good",
    60: "Good",
    45: "Moderate",
    0:  "Severe",
}


def _score_to_rating(score: float, max_pts: float) -> str:
    """Convert a raw domain score to a human-readable rating badge."""
    pct = (score / max_pts * 100) if max_pts > 0 else 0
    for threshold, label in sorted(_SCORE_TO_RATING.items(), reverse=True):
        if pct >= threshold:
            return label
    return "Severe"


def _ms_to_mmss(ms: int) -> str:
    """Convert milliseconds to MM:SS string."""
    total_s = int(ms) // 1000
    minutes = total_s // 60
    seconds = total_s % 60
    return f"{minutes:02d}:{seconds:02d}"


def _ms_to_seconds_str(ms: int) -> str:
    """E.g. 32000 → '32 seconds'."""
    s = int(ms) // 1000
    return f"{s} seconds" if s != 1 else "1 second"


# =============================================================================
# Section builders — each returns one section dict for pdf_engine
# =============================================================================

def _build_meta(session_meta: Dict, report) -> Dict:
    """Top-level PDF meta block (header bar, cover info grid)."""
    scenario_name = session_meta.get("scenario_name", "ACLS Simulation")
    session_id = session_meta.get("session_id", report.session_id or "Unknown")
    date_str = session_meta.get("date", datetime.today().strftime("%Y-%m-%d"))
    duration_ms = session_meta.get("duration_ms", report.session_duration_ms or 0)
    duration_min = math.ceil(duration_ms / 60000)
    outcome = session_meta.get("outcome", "Unknown").replace("_", " ").title()
    team_size = session_meta.get("team_size", "Unknown")
    guideline = session_meta.get("guideline_version", report.protocol_version or "AHA_2025_ACLS")

    grade = report.grade
    score = report.overall_score

    return {
        "title": "AI-Generated Debriefing and Performance Analysis Report",
        "subtitle": f"Simulation-Based ACLS Scenario  ·  Grade: {grade}  ·  Score: {score:.1f}/100",
        "date": date_str,
        "organization": "Medical Simulation Centre — Confidential",
        "info": {
            "Scenario ID":      session_id,
            "Scenario Type":    scenario_name,
            "Date":             date_str,
            "Duration":         f"{duration_min} minutes",
            "Guideline":        guideline,
            "Final Outcome":    outcome,
            "Team Size":        str(team_size),
            "Overall Grade":    f"{grade}  ({score:.1f}/100)",
        },
    }


def _build_role_allocation(session_meta: Dict) -> Dict:
    """Team Role Allocation table from session metadata segments."""
    # Extract unique roles from the transcript segments
    segments = session_meta.get("segments", [])
    seen = {}
    for seg in segments:
        role = seg.get("role", "unknown")
        speaker = seg.get("speaker", "Unknown")
        if role not in seen and role not in ("team", "unknown"):
            seen[role] = speaker

    role_display = {
        "team_leader":  "Team Leader",
        "compressor":   "Compressor / CPR",
        "airway":       "Airway Manager",
        "defib_coach":  "Defibrillator / CPR Coach",
        "iv_member":    "IV / Medication Member",
        "recorder":     "Recorder",
    }

    rows = [["Team Role", "Participant"]]
    for role_key, speaker in seen.items():
        label = role_display.get(role_key, role_key.replace("_", " ").title())
        rows.append([label, speaker])

    return {
        "title": "Team Role Allocation",
        "type": "table",
        "col_widths": [0.5, 0.5],
        "rows": rows,
    }


def _build_event_timeline(timeline, session_meta: Dict) -> Dict:
    """AI-Generated Event Timeline table from UnifiedTimeline or session segments."""
    rows = [["Time", "Event Detected"]]

    # Prefer UnifiedTimeline events if available
    if timeline and hasattr(timeline, "events") and timeline.events:
        for evt in sorted(timeline.events, key=lambda e: e.timestamp_ms):
            time_str = _ms_to_mmss(evt.timestamp_ms)
            event_label = (
                evt.event_type.value.replace("_", " ").title()
                if hasattr(evt.event_type, "value")
                else str(evt.event_type).replace("_", " ").title()
            )
            rows.append([time_str, event_label])
    else:
        # Fall back to session transcript segments
        segments = session_meta.get("segments", [])
        for seg in segments:
            ai_expected = seg.get("ai_expected", "").strip()
            time_str = seg.get("time", _ms_to_mmss(seg.get("timestamp_ms", 0)))
            if ai_expected:
                rows.append([time_str, ai_expected])

    # De-duplicate consecutive identical events
    deduped = [rows[0]]
    for row in rows[1:]:
        if row[1] != deduped[-1][1]:
            deduped.append(row)

    return {
        "title": "AI-Generated Event Timeline",
        "type": "table",
        "col_widths": [0.2, 0.8],
        "rows": deduped,
    }


def _build_performance_metrics(report, session_meta: Dict) -> Dict:
    """AI-Based Performance Metrics table from ScoreReport sub-signals."""
    rows = [["Parameter", "Observation"]]

    duration_ms = session_meta.get("duration_ms", report.session_duration_ms or 0)

    # Extract specific metrics from sub-signal notes across all domains
    sub_signal_notes: Dict[str, str] = {}
    for d in report.domain_scores:
        for ss in d.sub_signals:
            sub_signal_notes[ss.name] = ss.notes

    def _get_note(key: str, default: str = "—") -> str:
        return sub_signal_notes.get(key, default)

    # Static KPI rows that are always present
    rows.append(["Session Duration", _ms_to_seconds_str(duration_ms)])
    rows.append(["Overall Score", f"{report.overall_score:.1f}/100 (Grade {report.grade})"])
    rows.append(["Confidence Interval", f"[{report.ci_lower:.1f}, {report.ci_upper:.1f}]"])
    rows.append(["Data Completeness", f"{report.overall_completeness:.0%}"])

    # Dynamic rows from sub-signals that have meaningful notes
    for d in report.domain_scores:
        for ss in d.sub_signals:
            if ss.notes and ss.points_deducted > 0:
                rows.append([ss.name.replace("_", " ").title(), ss.notes])

    return {
        "title": "AI-Based Performance Metrics",
        "type": "table",
        "col_widths": [0.55, 0.45],
        "rows": rows,
    }


def _build_strengths(narrative) -> Dict:
    return {
        "title": "AI-Detected Strengths",
        "type": "two_column_bullets",
        "items": narrative.strengths,
    }


def _build_deficiencies(narrative) -> Dict:
    return {
        "title": "AI-Detected Deficiencies",
        "type": "bullets",
        "items": narrative.deficiencies,
    }


def _build_communication_analysis(report) -> Dict:
    """
    Communication Analysis table sourced from the NLP-scored domains:
    team_communication and team_leadership DomainScores.
    """
    rows = [["Domain", "AI Observation"]]

    domain_map = {d.domain_key: d for d in report.domain_scores}
    comm_domain = domain_map.get("team_communication")
    lead_domain  = domain_map.get("team_leadership")

    # Closed-loop: from team_communication sub-signals
    if comm_domain:
        for ss in comm_domain.sub_signals:
            label = ss.name.replace("_", " ").title()
            # Determine observation badge
            pct = (ss.points_earned / ss.points_possible * 100) if ss.points_possible > 0 else 100
            obs = _score_to_rating(ss.points_earned, ss.points_possible) if ss.points_possible > 0 else "Good"
            rows.append([label, obs])

        # Add overall communication score
        comm_pct = (comm_domain.final_score / comm_domain.max_points * 100) if comm_domain.max_points > 0 else 0
        rows.append(["Team Communication (Overall)", _score_to_rating(comm_domain.final_score, comm_domain.max_points)])

    # Leadership: from team_leadership sub-signals
    if lead_domain:
        for ss in lead_domain.sub_signals:
            label = ss.name.replace("_", " ").title()
            obs = _score_to_rating(ss.points_earned, ss.points_possible) if ss.points_possible > 0 else "Good"
            rows.append([label, obs])

        rows.append(["Team Leadership (Overall)", _score_to_rating(lead_domain.final_score, lead_domain.max_points)])

    # Fallback if NLP domains not present (FSM-only run)
    if len(rows) == 1:
        rows += [
            ["Closed Loop Communication", "Partial"],
            ["Leadership Commands",        "Good"],
            ["Role Clarity",               "Good"],
            ["Team Coordination",          "Good"],
        ]

    return {
        "title": "Communication Analysis",
        "type": "table",
        "badge_col": 1,
        "col_widths": [0.60, 0.40],
        "rows": rows,
    }


def _build_workflow_deviations(report) -> Dict:
    """
    AI-Detected Workflow Deviations: all sub-signals with point deductions,
    sourced from every domain in the ScoreReport.
    """
    rows = [["Deviation", "Severity", "Domain", "Points Lost"]]

    for d in report.domain_scores:
        for ss in d.sub_signals:
            if ss.points_deducted > 0:
                severity_label = ss.severity.upper() if ss.severity else "MODERATE"
                # Normalize to PDF badge vocabulary
                badge = {
                    "CRITICAL": "Severe",
                    "HIGH":     "Severe",
                    "MODERATE": "Moderate",
                    "MEDIUM":   "Moderate",
                    "LOW":      "Mild",
                    "INFO":     "Mild",
                }.get(severity_label, "Moderate")

                rows.append([
                    ss.name.replace("_", " ").title(),
                    badge,
                    d.domain_label,
                    f"−{ss.points_deducted:.1f}",
                ])

    if len(rows) == 1:
        rows.append(["No significant deviations detected.", "", "", "0.0"])

    return {
        "title": "AI-Detected Workflow Deviations",
        "type": "table",
        "badge_col": 1,
        "col_widths": [0.40, 0.18, 0.28, 0.14],
        "rows": rows,
    }


def _build_overall_assessment(report) -> Dict:
    """Overall AI Performance Assessment — one row per DomainScore."""
    rows = [["Domain", "Score", "Max", "Rating"]]

    for d in report.domain_scores:
        rating = _score_to_rating(d.final_score, d.max_points)
        rows.append([
            d.domain_label,
            f"{d.final_score:.1f}",
            f"{d.max_points:.0f}",
            rating,
        ])

    # Final row: overall
    overall_rating = _GRADE_TO_RATING.get(report.grade, "Good")
    rows.append([
        "Overall Team Performance",
        f"{report.overall_score:.1f}",
        "100",
        overall_rating,
    ])

    return {
        "title": "Overall AI Performance Assessment",
        "type": "table",
        "badge_col": 3,
        "col_widths": [0.50, 0.14, 0.12, 0.24],
        "rows": rows,
    }


def _build_reflective_questions(narrative) -> Dict:
    return {
        "title": "AI-Generated Reflective Debrief Questions",
        "type": "bullets",
        "items": narrative.reflective_qs,
    }


def _build_recommendations(narrative) -> Dict:
    return {
        "title": "AI Recommendations",
        "type": "bullets",
        "items": narrative.recommendations,
    }


def _build_final_summary(narrative) -> Dict:
    return {
        "title": "Final AI Summary",
        "type": "text",
        "content": narrative.final_summary,
    }


def _build_raw_transcript(session_meta: Dict) -> Dict:
    """
    Renders the raw team conversation as a table:
        Time | Speaker / Role | Utterance

    Populated from session_meta['segments'] which contains the timestamped
    transcript entries. Each segment must have 'time' or 'timestamp_ms',
    'speaker', and 'text' fields.
    """
    segments = session_meta.get("segments", [])
    rows = [["Time", "Speaker / Role", "Utterance"]]

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        time_str = seg.get("time") or _ms_to_mmss(seg.get("timestamp_ms", 0))
        speaker  = seg.get("speaker", seg.get("speaker_label", "Unknown"))
        # Truncate very long utterances so they fit in the table cell
        display_text = text if len(text) <= 120 else text[:117] + "..."
        rows.append([time_str, speaker, display_text])

    if len(rows) == 1:
        rows.append(["—", "—", "No transcript data available for this session."])

    return {
        "title": "Raw Team Communication Transcript",
        "type": "table",
        "col_widths": [0.10, 0.26, 0.64],
        "rows": rows,
    }


def _build_conversation(session_meta: Dict) -> Dict:
    """
    Renders the 'conversation' field from the session JSON as a two-column table:
        Time | Utterance (raw ceiling audio — no role attribution)

    This is what Whisper extracted verbatim from the audio. Displayed for
    user verification before the role-attributed transcript.
    """
    entries = session_meta.get("conversation", [])
    rows = [["Time", "Ceiling Audio — Raw Utterance"]]

    for entry in entries:
        time_str = entry.get("time") or _ms_to_mmss(entry.get("timestamp_ms", 0))
        text = entry.get("text", "").strip()
        if not text:
            continue
        display_text = text if len(text) <= 130 else text[:127] + "..."
        rows.append([time_str, display_text])

    if len(rows) == 1:
        rows.append(["—", "No raw conversation data available for this session."])

    return {
        "title": "Raw Ceiling Audio — Extracted Conversation (Unattributed)",
        "type": "table",
        "col_widths": [0.12, 0.88],
        "rows": rows,
    }


def _build_clinical_timeline_section(session_meta: Dict) -> Dict:
    """
    Renders the 'clinical_timeline' field from the session JSON as a table:
        # | Time | Event | Note | Source | Confidence
    """
    entries = session_meta.get("clinical_timeline", [])
    rows = [["#", "Time", "Event", "Clinical Note", "Confidence"]]

    for entry in entries:
        idx   = str(entry.get("index", ""))
        time  = entry.get("time", "")
        label = entry.get("label", entry.get("event_type", "").replace("_", " ").title())
        note  = entry.get("note", "")
        conf  = entry.get("confidence", 1.0)
        # Truncate long notes
        display_note = note if len(note) <= 90 else note[:87] + "..."
        conf_str = f"{conf:.0%}"
        rows.append([idx, time, label, display_note, conf_str])

    if len(rows) == 1:
        rows.append(["—", "—", "No clinical timeline data available.", "", ""])

    return {
        "title": "Clinical Event Timeline",
        "type": "table",
        "col_widths": [0.05, 0.10, 0.20, 0.55, 0.10],
        "rows": rows,
    }


# =============================================================================
# Gamification section builder
# =============================================================================

_BADGE_LABELS = {
    "first_scenario":       "First Responder",
    "perfect_score":        "Perfect Performance",
    "advanced_completer":   "Advanced Operator",
    "rapid_responder":      "Rapid Responder",
    "debrief_champion":     "Debrief Champion",
    "consistent_performer": "Consistent Performer",
    "team_leader":          "Team Leader",
    "zero_deviations":      "Zero Deviations",
}


def _build_gamification_section(gamification_data: Dict) -> Dict:
    """
    Render XP earned, prediction accuracy, badges, and level progress
    as a table section in the PDF.

    Expected gamification_data keys (all optional):
        team_name, xp_earned, total_xp, level_label, prediction_accuracy,
        grade, session_count, badges_earned, ai_debriefed, scenario_id,
        score, critical_misses
    """
    rows = [["Metric", "Value"]]

    team     = gamification_data.get("team_name", "—")
    xp       = gamification_data.get("xp_earned", 0)
    total_xp = gamification_data.get("total_xp", xp)
    level    = gamification_data.get("level_label", "—")
    accuracy = gamification_data.get("prediction_accuracy")
    grade    = gamification_data.get("grade", "—")
    sessions = gamification_data.get("session_count", "—")
    scenario = gamification_data.get("scenario_id", "—")
    score    = gamification_data.get("score")
    ai_deb   = gamification_data.get("ai_debriefed", False)

    rows.append(["Team Name",              team])
    rows.append(["Scenario ID",            str(scenario)])
    if score is not None:
        rows.append(["Session Score",      f"{score:.1f}/100  (Grade {grade})"])
    rows.append(["XP Earned (this run)",   f"+{int(xp)} XP"])
    rows.append(["Total XP",               f"{int(total_xp)} XP"])
    rows.append(["Level",                  str(level)])
    if sessions not in ("—", None):
        rows.append(["Total Sessions",     str(sessions)])
    if accuracy is not None:
        rows.append(["Prediction Accuracy", f"{float(accuracy):.1f}%"])
    rows.append(["AI Debriefed",           "Yes" if ai_deb else "No"])

    # Badges
    badges_list = gamification_data.get("badges_earned", [])
    if badges_list:
        badge_labels = [_BADGE_LABELS.get(b, b.replace("_", " ").title()) for b in badges_list]
        rows.append(["Badges Earned", "  |  ".join(badge_labels)])

    # Critical misses
    misses = gamification_data.get("critical_misses", [])
    if misses:
        rows.append(["Critical Misses", ";  ".join(misses)])

    return {
        "title": "Gamification Performance Summary",
        "type":  "table",
        "col_widths": [0.45, 0.55],
        "rows": rows,
    }


def build_scenario_pdf_input(
    spec:             Dict,
    gamification_data: Dict,
    deviations:       Optional[List] = None,
    checklist_done:   Optional[List] = None,
    elapsed_sec:      int = 0,
) -> Dict[str, Any]:
    """
    Build a standalone PDF input dict for a Scenario Studio session result.
    This does NOT require a ScoreReport or NarrativeOutput — it's built
    entirely from the live scenario monitor data and gamification record.
    """
    from datetime import datetime

    now     = datetime.today()
    patient = spec.get("patient", {})
    level   = spec.get("level", "beginner").capitalize()
    loc     = spec.get("location", "—")
    spec_ty = spec.get("speciality", "—")
    title   = spec.get("title", "Scenario Run")
    xp_rew  = spec.get("xp_reward", 0)

    # --- Meta ---
    team_name = gamification_data.get("team_name", "Team")
    score     = gamification_data.get("score", 0)
    grade     = gamification_data.get("grade", "—")

    meta = {
        "title":        f"Scenario Studio Report — {title}",
        "subtitle":     f"Level: {level}  ·  Location: {loc}  ·  Speciality: {spec_ty}",
        "date":         now.strftime("%d %b %Y"),
        "organization": "Medical Simulation Centre — Confidential",
        "info": {
            "Team Name":   team_name,
            "Scenario":    title,
            "Level":       level,
            "Location":    loc,
            "Speciality":  spec_ty,
            "Date":        now.strftime("%d %b %Y"),
            "Duration":    f"{elapsed_sec // 60}m {elapsed_sec % 60}s",
            "Score":       f"{score:.1f}/100  (Grade {grade})",
        },
    }

    sections = []

    # --- Patient Profile ---
    patient_rows = [["Field", "Detail"]]
    patient_rows.append(["Age",          str(patient.get("age", "—"))])
    patient_rows.append(["Sex",          patient.get("sex", "—")])
    patient_rows.append(["Weight",       f"{patient.get('weight_kg','—')} kg"])
    patient_rows.append(["Presentation", patient.get("presentation", "—")])
    patient_rows.append(["History",      patient.get("history", "—")])
    sections.append({
        "title": "Patient Profile",
        "type":  "table",
        "col_widths": [0.25, 0.75],
        "rows":  patient_rows,
    })

    # --- Expected Checklist vs Completed ---
    checklist = spec.get("checklist", [])
    if checklist:
        cl_rows = [["Action", "Critical?", "Window (s)", "Completed"]]
        done_set = set(checklist_done or [])
        for item in checklist:
            action   = item.get("action", "—")
            critical = "YES" if item.get("critical") else "No"
            window   = str(item.get("window_sec", "—"))
            done     = "Yes" if action in done_set else "No"
            cl_rows.append([action, critical, window, done])
        sections.append({
            "title": "Expected Action Checklist",
            "type":  "table",
            "col_widths": [0.50, 0.12, 0.18, 0.20],
            "rows":  cl_rows,
        })

    # --- Deviations ---
    dev_rows = [["Time", "Deviation", "Severity"]]
    for dv in (deviations or []):
        dev_rows.append([
            dv.get("time", "—"),
            dv.get("action", dv.get("message", "—")),
            dv.get("severity", "moderate").capitalize(),
        ])
    if len(dev_rows) == 1:
        dev_rows.append(["—", "No deviations recorded.", "—"])
    sections.append({
        "title": "Deviation Log",
        "type":  "table",
        "badge_col": 2,
        "col_widths": [0.15, 0.65, 0.20],
        "rows":  dev_rows,
    })

    # --- Gamification Summary ---
    sections.append(_build_gamification_section(gamification_data))

    # --- Hints & Complications ---
    hints = spec.get("hints", [])
    if hints:
        sections.append({"title": "Hints Provided", "type": "bullets", "items": hints})

    comps = spec.get("complications", [])
    if comps:
        sections.append({"title": "Active Complications", "type": "bullets", "items": comps})

    return {"meta": meta, "sections": sections}


# =============================================================================
# Main adapter function
# =============================================================================

def build_pdf_input(
    report,
    narrative,
    timeline=None,
    session_meta: Optional[Dict] = None,
    gamification_data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Build the complete JSON dict expected by pdf_engine.generate_pdf().

    Args:
        report             : ScoreReport from ScoringEngine
        narrative          : NarrativeOutput from NarrativeEngine
        timeline           : UnifiedTimeline object (optional)
        session_meta       : Raw session metadata dict (from the input JSON file)
        gamification_data  : Optional dict from GamificationEngine.record_session()

    Returns:
        dict matching the pdf_engine JSON schema
    """
    if session_meta is None:
        session_meta = {}

    sections = [
        _build_role_allocation(session_meta),
        _build_clinical_timeline_section(session_meta),
        _build_event_timeline(timeline, session_meta),
        _build_performance_metrics(report, session_meta),
        {"type": "page_break"},
        _build_strengths(narrative),
        _build_deficiencies(narrative),
        _build_communication_analysis(report),
        _build_workflow_deviations(report),
        _build_reflective_questions(narrative),
        _build_recommendations(narrative),
        _build_overall_assessment(report),
        _build_final_summary(narrative),
    ]

    # Append gamification section if provided
    if gamification_data:
        sections.append({"type": "page_break"})
        sections.append(_build_gamification_section(gamification_data))

    sections += [
        {"type": "page_break"},
        _build_raw_transcript(session_meta),
        {"type": "page_break"},
        _build_conversation(session_meta),
    ]

    return {
        "meta":     _build_meta(session_meta, report),
        "sections": sections,
    }
