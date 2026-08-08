"""
pipeline_adapter.py
-------------------
Orchestrates the full backend analysis pipeline:

  [Timeline JSON / Session JSON]
       │
       ├─► ACLS FSM Engine        → Clinical deviation FindingRecords
       │
  [Transcript Segments]
       │
       ├─► NLP Engine (LangGraph 4-agent)
       │       │
       │       ├─► Communication FindingRecords (CLOSED_LOOP, CALLOUT)
       │       └─► TranscriptSegments (lapel / ceiling) for completeness scoring
       │
       ├─► CPR Scoring Engine     → ScoreReport (grade + CI + domain breakdown)
       │
       ├─► NarrativeEngine        → NarrativeOutput (LLM-generated text sections)
       │
       └─► PDF Adapter + Engine   → debriefing_report.pdf
"""

import json
import uuid
import sys
import os
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# ── Sys-path setup so sub-packages resolve correctly ─────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_ROOT)
sys.path.append(os.path.join(_ROOT, "acls_fsm"))

# ── ACLS FSM Engine ───────────────────────────────────────────────────────────
from engine import ACLSEngine  # noqa: E402  (after sys.path tweak)

# ── Scoring Engine ────────────────────────────────────────────────────────────
from analysis.scoring.scoring_engine import ScoringEngine  # noqa: E402
from schemas.event_schema import (  # noqa: E402
    UnifiedTimeline, UnifiedEvent, EventType, ActorRole,
    Severity, FindingRecord, SourceSystem, TranscriptSegment,
)
from analysis.scoring.score_models import ScoreReport  # noqa: E402

# ── Reporting (Narrative + PDF) ───────────────────────────────────────────────
from analysis.reporting.narrative_engine import NarrativeEngine, NarrativeOutput  # noqa: E402
from analysis.reporting.pdf_adapter import build_pdf_input                         # noqa: E402
from analysis.reporting.pdf_engine import generate_pdf                             # noqa: E402


# =============================================================================
# Severity & Domain helpers
# =============================================================================

_SEVERITY_MAP = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH":     Severity.HIGH,
    "MEDIUM":   Severity.MODERATE,
    "MODERATE": Severity.MODERATE,
    "LOW":      Severity.LOW,
    "INFO":     Severity.INFO,
}

# Maps ACLS FSM rule IDs → scoring domain keys
_RULE_TO_DOMAIN: Dict[str, str] = {
    "R_ARREST_001": "cpr_quality",
    "R_ARREST_003": "cpr_quality",
    "R_ARREST_005": "cpr_quality",
    "R_ARREST_002": "shock_delivery",
    "R_ARREST_010": "shock_delivery",
    "R_ARREST_004": "drug_administration",
    "R_ARREST_006": "drug_administration",
    "R_ARREST_007": "drug_administration",
    "R_ARREST_008": "drug_administration",
    "R_ARREST_009": "drug_administration",
    "R_ARREST_011": "drug_administration",
    "R_ARREST_012": "team_leadership",
}

def _map_severity(sev_str: str) -> Severity:
    return _SEVERITY_MAP.get(str(sev_str).upper(), Severity.INFO)

def _map_domain(rule_id: str) -> str:
    return _RULE_TO_DOMAIN.get(rule_id, "cpr_quality")


# =============================================================================
# Step 1 – ACLS FSM: parse timeline JSON into FSM event format
# =============================================================================

def parse_fsm_events(timeline_data: dict) -> dict:
    """
    Converts the UnifiedTimeline dict (from JSON or event_extractor) into the
    flat event format expected by the ACLS FSM Engine.
    """
    fsm_events = []
    for evt in timeline_data.get("events", []):
        evt_type = evt.get("event_type", "")
        val = evt.get("value", {})

        # Map our rich event_type names to the FSM's expected strings
        fsm_type = evt_type
        if evt_type == "rhythm_check":
            rhythm = val.get("rhythm", "")
            if rhythm in ("VF", "pVT"):
                fsm_type = "vf_pvt_detected"
            elif rhythm in ("PEA", "ASYSTOLE"):
                fsm_type = "pea_detected"
        elif evt_type == "drug_administered":
            drug = val.get("drug", "")
            if drug == "epinephrine":
                fsm_type = "epinephrine_given"
            elif drug == "amiodarone":
                fsm_type = "amiodarone_given"
            elif drug == "lidocaine":
                fsm_type = "lidocaine_given"

        fsm_events.append({
            "event_id":      evt.get("event_id"),
            "timestamp_sec": evt.get("timestamp_ms", 0) // 1000,
            "event_type":    fsm_type,
            "actor_role":    evt.get("actor_role", "unknown"),
        })

    # Always inject a session_end so the FSM runs its end-of-session checks
    duration_sec = timeline_data.get("metadata", {}).get("duration_ms", 0) // 1000
    fsm_events.append({
        "event_id":      "evt_session_end",
        "timestamp_sec": duration_sec,
        "event_type":    "session_end",
        "actor_role":    "system",
    })

    meta = timeline_data.get("metadata", {})
    return {
        "session_id":    meta.get("session_id", "unknown"),
        "session_date":  meta.get("date", "2026-01-01"),
        "scenario_type": meta.get("scenario_type", "VF"),
        "events":        fsm_events,
    }


# =============================================================================
# Step 2 – Convert FSM findings → FindingRecord objects
# =============================================================================

def convert_fsm_findings(fsm_findings: List[dict]) -> List[FindingRecord]:
    """Converts raw FSM deviation dicts into strongly-typed FindingRecords."""
    records: List[FindingRecord] = []
    for f in fsm_findings:
        if f.get("status") != "deviation":
            continue
        rule_id = f.get("rule_id", "")
        records.append(FindingRecord(
            finding_id=f.get("finding_id", str(uuid.uuid4())),
            title=rule_id,
            severity=_map_severity(f.get("severity", "LOW")),
            domain=_map_domain(rule_id),
            description=f.get("deviation_message", ""),
            guideline_citation=f.get("guideline", ""),
            recommendation=f.get("recommendation", ""),
            reflective_prompt="How could the team have improved timing here?",
            event_timestamp_ms=(
                int(f["actual_gap_sec"]) * 1000 if f.get("actual_gap_sec") else None
            ),
            delay_seconds=f.get("actual_gap_sec"),
        ))
    logger.info(f"FSM produced {len(records)} deviation finding(s).")
    return records


# =============================================================================
# Step 3 – NLP Engine: run 4-agent LangGraph analysis on transcript segments
# =============================================================================

def run_nlp_analysis(session_id: str, segments: list) -> Dict[str, Any]:
    """
    Runs the LangGraph NLP engine on diarized transcript segments.
    Returns the raw nlp_engine output dict.
    Gracefully returns empty result if Ollama is unavailable or any error occurs.
    """
    if not segments:
        logger.warning("NLP Engine: no segments provided, skipping NLP analysis.")
        return {"nlp_analysis": {}, "raw_transcript": ""}

    logger.info(f"NLP Engine: processing {len(segments)} segments for session {session_id}...")
    try:
        from analysis.nlp_engine import NLPEngine  # use full package path so relative imports resolve
        nlp = NLPEngine()
        return nlp.process(session_id=session_id, segments=segments)
    except (ImportError, ModuleNotFoundError) as e:
        logger.warning(
            f"NLP Engine: required packages not available ({e}). "
            "Skipping NLP analysis — install langgraph/langchain_ollama to enable."
        )
        return {"nlp_analysis": {}, "raw_transcript": ""}
    except Exception as e:
        # Catches Ollama connection errors, timeouts, model-not-found, etc.
        logger.warning(
            f"NLP Engine: analysis failed ({type(e).__name__}: {e}). "
            "Ollama may not be running — skipping NLP step and continuing pipeline."
        )
        return {"nlp_analysis": {}, "raw_transcript": ""}


# =============================================================================
# Step 4 – Parse NLP output → communication FindingRecords
# =============================================================================

def _detect_closed_loop_issues(nlp_analysis: dict) -> bool:
    """
    Heuristic: look for negative language about closed-loop communication in
    the branch_1.closed_loop_analysis field from the NLP agents.
    """
    analysis_text = str(
        nlp_analysis.get("branch_1", {}).get("closed_loop_analysis", "")
    ).lower()
    negative_keywords = [
        "lack", "missing", "no explicit feedback", "not closed",
        "no confirmation", "unconfirmed", "absence", "did not confirm",
        "weakness", "no explicit", "fail",
    ]
    return any(kw in analysis_text for kw in negative_keywords)


def _detect_callout_issues(nlp_analysis: dict) -> bool:
    """
    Heuristic: look for callout completeness issues in branch_2.callout_validation.
    """
    callout_text = str(
        nlp_analysis.get("branch_2", {}).get("callout_validation", "")
    ).lower()
    negative_keywords = [
        "missing", "ambiguous", "unclear", "not specified",
        "unspecified", "incomplete", "no clear", "confusing",
        "not stated",
    ]
    return any(kw in callout_text for kw in negative_keywords)


def convert_nlp_findings(nlp_result: Dict[str, Any]) -> List[FindingRecord]:
    """
    Interprets the NLP agent output and generates FindingRecords for the
    team_communication and team_leadership scoring domains.
    """
    records: List[FindingRecord] = []
    nlp_analysis = nlp_result.get("nlp_analysis", {})

    if not nlp_analysis:
        return records

    # ── Team Communication: Closed-loop check ────────────────────────────────
    if _detect_closed_loop_issues(nlp_analysis):
        records.append(FindingRecord(
            finding_id=f"nlp_comm_{uuid.uuid4().hex[:8]}",
            title="CLOSED_LOOP_FAILURE",
            severity=Severity.MODERATE,
            domain="team_communication",
            description=(
                "NLP analysis detected incomplete or missing closed-loop "
                "communication patterns. Orders were not consistently confirmed "
                "back by the receiving team member."
            ),
            guideline_citation="AHA 2025 Team Dynamics — Closed-Loop Communication",
            recommendation=(
                "All drug orders and critical actions should be verbally confirmed "
                "by the receiving member within 30 seconds."
            ),
            reflective_prompt=(
                "At which point could the team have improved verbal confirmation "
                "of orders?"
            ),
        ))
        logger.info("NLP: CLOSED_LOOP_FAILURE finding generated.")

    # ── Team Communication: Callout completeness check ────────────────────────
    if _detect_callout_issues(nlp_analysis):
        records.append(FindingRecord(
            finding_id=f"nlp_callout_{uuid.uuid4().hex[:8]}",
            title="CRITICAL_CALLOUT_MISSED",
            severity=Severity.LOW,
            domain="team_communication",
            description=(
                "NLP analysis identified incomplete or ambiguous callout "
                "communications. Critical events may not have been clearly "
                "verbalized to the full team."
            ),
            guideline_citation="AHA 2025 Team Dynamics — Explicit Callouts",
            recommendation=(
                "Key clinical events (rhythm changes, drug doses, shock delivery) "
                "should be announced aloud to the team with clear language."
            ),
            reflective_prompt=(
                "Which critical events could have been announced more clearly "
                "to the whole team?"
            ),
        ))
        logger.info("NLP: CRITICAL_CALLOUT_MISSED finding generated.")

    # ── Team Leadership: Protocol compliance check ────────────────────────────
    compliance_text = str(
        nlp_analysis.get("branch_1", {}).get("protocol_compliance", "")
    ).lower()
    leadership_negative = [
        "lack", "unclear", "not defined", "missing", "no clear",
        "no decision", "delayed", "not provided",
    ]
    if any(kw in compliance_text for kw in leadership_negative):
        records.append(FindingRecord(
            finding_id=f"nlp_lead_{uuid.uuid4().hex[:8]}",
            title="DECISION_DELAYED",
            severity=Severity.LOW,
            domain="team_leadership",
            description=(
                "NLP analysis detected unclear or delayed leadership directives. "
                "The team leader's protocol decisions were not clearly communicated."
            ),
            guideline_citation="AHA 2025 Team Dynamics — Clear Role Assignment",
            recommendation=(
                "The team leader should issue explicit, directed orders and "
                "announce key decisions to the whole team."
            ),
            reflective_prompt=(
                "How could the team leader have communicated more clearly during "
                "critical decision points?"
            ),
        ))
        logger.info("NLP: DECISION_DELAYED (leadership) finding generated.")

    logger.info(f"NLP Engine produced {len(records)} communication finding(s).")
    return records


# =============================================================================
# Step 5 – Convert diarized segments → scoring engine TranscriptSegments
# =============================================================================

def build_transcript_segments(
    segments: list,
    session_duration_ms: int,
) -> Dict[str, List[TranscriptSegment]]:
    """
    Converts the diarization output (list of TranscriptionResult-like objects)
    into the two transcript lists the Scoring Engine expects:
      - "lapel"  : team-leader utterances only
      - "ceiling": all utterances (full room mic)
    """
    lapel_segments: List[TranscriptSegment] = []
    ceiling_segments: List[TranscriptSegment] = []

    if not segments:
        return {"lapel": lapel_segments, "ceiling": ceiling_segments}

    # Estimate per-segment duration from position in the session
    total_segments = len(segments)
    per_seg_ms = session_duration_ms // total_segments if total_segments > 0 else 5000

    for idx, seg in enumerate(segments):
        # Extract fields — handle both dataclass objects and plain dicts
        if isinstance(seg, dict):
            text        = seg.get("text", "")
            actor_role  = seg.get("actor_role") or seg.get("role", "UNKNOWN")
            start_ms    = seg.get("start_ms", idx * per_seg_ms)
            end_ms      = seg.get("end_ms", start_ms + per_seg_ms)
            confidence  = seg.get("confidence", 1.0)
            role_name   = str(actor_role).upper()
        else:
            text       = getattr(seg, "text", "")
            role_obj   = getattr(seg, "actor_role", None)
            role_name  = (
                role_obj.name.upper() if role_obj and hasattr(role_obj, "name")
                else str(role_obj).upper() if role_obj else "UNKNOWN"
            )
            start_ms   = getattr(seg, "start_ms", idx * per_seg_ms)
            end_ms     = getattr(seg, "end_ms",   start_ms + per_seg_ms)
            confidence = getattr(seg, "confidence", 1.0)

        # Map role string to scoring schema ActorRole
        try:
            actor = ActorRole(role_name.lower())
        except ValueError:
            actor = ActorRole.UNKNOWN

        ts = TranscriptSegment(
            segment_id=f"seg_{idx:04d}",
            text=text,
            speaker_role=actor,
            start_ms=start_ms,
            end_ms=end_ms,
            source="ceiling",
            confidence=confidence,
        )
        ceiling_segments.append(ts)

        # Lapel = team_leader utterances only
        if actor == ActorRole.TEAM_LEADER:
            lapel_ts = TranscriptSegment(
                segment_id=f"lapel_{idx:04d}",
                text=text,
                speaker_role=actor,
                start_ms=start_ms,
                end_ms=end_ms,
                source="lapel",
                confidence=confidence,
            )
            lapel_segments.append(lapel_ts)

    logger.info(
        f"Built {len(ceiling_segments)} ceiling segment(s), "
        f"{len(lapel_segments)} lapel segment(s)."
    )
    return {"lapel": lapel_segments, "ceiling": ceiling_segments}


# =============================================================================
# Step 6 – Build UnifiedTimeline from timeline JSON
# =============================================================================

def parse_unified_timeline(timeline_data: dict) -> UnifiedTimeline:
    """Converts the raw timeline dict into a typed UnifiedTimeline."""
    meta = timeline_data.get("metadata", {})
    timeline = UnifiedTimeline(
        session_id=meta.get("session_id", "unknown"),
        scenario_name=meta.get("scenario_name", "Unknown Scenario"),
        total_duration_ms=meta.get("duration_ms", 0),
        team_size=meta.get("team_size"),
        guideline_version=meta.get("guideline_version", "AHA_2025_ACLS"),
    )

    evt_type_map = {
        "arrest_recognized": EventType.ARREST_RECOGNISED,
        "cpr_initiated":     EventType.CPR_STARTED,
        "cpr_paused":        EventType.CPR_PAUSED,
        "cpr_resumed":       EventType.CPR_RESUMED,
        "shock_delivered":   EventType.SHOCK_DELIVERED,
        "drug_administered": EventType.DRUG_ADMINISTERED,
        "rosc_achieved":     EventType.ROSC_ACHIEVED,
        "rhythm_check":      EventType.RHYTHM_IDENTIFIED,
    }

    for evt in timeline_data.get("events", []):
        evt_type = evt.get("event_type", "")
        val = evt.get("value", {})

        try:
            actor = ActorRole(evt.get("actor_role", "unknown"))
        except ValueError:
            actor = ActorRole.UNKNOWN

        timeline.events.append(UnifiedEvent(
            event_id=evt.get("event_id", str(uuid.uuid4())),
            event_type=evt_type_map.get(evt_type, EventType.UNKNOWN),
            timestamp_ms=evt.get("timestamp_ms", 0),
            actor_role=actor,
            source_system=SourceSystem.SIMMAN,
            drug_name=val.get("drug"),
            drug_dose_mg=val.get("dose_mg"),
            shock_energy_joules=val.get("energy_joules"),
            nlp_confidence=evt.get("confidence", 1.0),
        ))

    return timeline


# =============================================================================
# Main public function: run_pipeline
# =============================================================================

def run_pipeline(
    timeline_json_path: str,
    segments: Optional[list] = None,
) -> ScoreReport:
    """
    Runs the full backend pipeline:
      1. Load timeline JSON
      2. Run ACLS FSM on timeline events → FSM FindingRecords
      3. Run NLP Engine on transcript segments → Communication FindingRecords
      4. Merge all FindingRecords
      5. Convert segments → TranscriptSegments (lapel + ceiling)
      6. Build UnifiedTimeline
      7. Run Scoring Engine → ScoreReport

    Args:
        timeline_json_path: Path to the UnifiedTimeline JSON file.
        segments:           Optional list of diarized TranscriptionResult objects.
                            Pass None (or empty) to skip NLP analysis.

    Returns:
        ScoreReport — complete scoring output with domain scores, grade and CI.
    """
    print("=" * 60)
    print("  CPR DEBRIEFING — FULL BACKEND PIPELINE")
    print("=" * 60)

    # ── 1. Load raw timeline ──────────────────────────────────────────────────
    print("\n[1/5] Loading timeline data...")
    with open(timeline_json_path, "r", encoding="utf-8") as f:
        timeline_data = json.load(f)
    session_id = timeline_data.get("metadata", {}).get("session_id", "unknown")
    duration_ms = timeline_data.get("metadata", {}).get("duration_ms", 0)
    print(f"      Session: {session_id} | Duration: {duration_ms // 1000}s")

    # ── 2. ACLS FSM Engine ────────────────────────────────────────────────────
    print("\n[2/5] Running ACLS FSM Rule Engine...")
    fsm_data = parse_fsm_events(timeline_data)
    fsm_engine = ACLSEngine()
    fsm_raw = fsm_engine.evaluate(fsm_data)
    fsm_findings = convert_fsm_findings(fsm_raw)
    print(f"      FSM findings: {len(fsm_findings)} deviation(s)")

    # ── 3. NLP Engine (optional, requires segments) ───────────────────────────
    nlp_findings: List[FindingRecord] = []
    transcripts: Dict[str, List[TranscriptSegment]] = {"lapel": [], "ceiling": []}

    if segments:
        print(f"\n[3/5] Running NLP Engine on {len(segments)} transcript segments...")
        nlp_result = run_nlp_analysis(session_id, segments)
        nlp_findings = convert_nlp_findings(nlp_result)
        transcripts = build_transcript_segments(segments, duration_ms)
        print(f"      NLP findings: {len(nlp_findings)} communication finding(s)")
        print(
            f"      Transcript: {len(transcripts['ceiling'])} ceiling seg(s), "
            f"{len(transcripts['lapel'])} lapel seg(s)"
        )
    else:
        print("\n[3/5] Skipping NLP Engine (no transcript segments provided)")

    # ── 4. Merge all findings ─────────────────────────────────────────────────
    print("\n[4/5] Merging findings and building UnifiedTimeline...")
    all_findings = fsm_findings + nlp_findings
    unified_timeline = parse_unified_timeline(timeline_data)
    print(f"      Total findings: {len(all_findings)}")

    # ── 5. Scoring Engine ─────────────────────────────────────────────────────
    print("\n[5/5] Running CPR Scoring Engine...")
    scoring_engine = ScoringEngine()
    report = scoring_engine.score(
        timeline=unified_timeline,
        findings=all_findings,
        lapel_transcript=transcripts["lapel"],
        ceiling_transcript=transcripts["ceiling"],
        session_id=session_id,
    )

    print("\n" + "=" * 60)
    print(f"  {report.summary_str()}")
    print("=" * 60 + "\n")

    return report


# =============================================================================
# generate_pdf_report  — full end-to-end pipeline → PDF
# =============================================================================

def generate_pdf_report(
    session_json_path: str,
    output_pdf_path: str,
    segments: Optional[list] = None,
) -> str:
    """
    End-to-end pipeline runner that outputs a formatted PDF debriefing report.

    Orchestrates all five pipeline stages:
        1. ACLS FSM   → protocol deviation FindingRecords
        2. NLP Engine → communication FindingRecords  (optional)
        3. Scoring    → ScoreReport with grade and domain breakdown
        4. Narrative  → LLM-generated human-readable text sections
        5. PDF        → beautifully rendered debriefing_report.pdf

    The function accepts a unified session JSON file that may contain either:
        - A UnifiedTimeline object (``events`` key) used by the FSM/Scoring engines
        - OR a scenario session file (``segments`` key) for the NLP transcript

    If the file contains ``segments`` but no ``events``, the FSM engine will run
    with an empty event list and the NLP engine will use the segment data.

    Args:
        session_json_path : Path to the session JSON file.
        output_pdf_path   : Where to write the output PDF.
        segments          : Optional list of diarized TranscriptionResult objects
                            for NLP analysis.  If None, the function will try to
                            load segments from the session JSON ``segments`` key.

    Returns:
        output_pdf_path on success.
    """
    print("=" * 60)
    print("  CPR DEBRIEFING — FULL PDF PIPELINE")
    print("=" * 60)

    # ── Load raw session JSON ─────────────────────────────────────────────────
    print("\n[1/6] Loading session data...")
    with open(session_json_path, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    session_id = (
        session_data.get("session_id")
        or session_data.get("metadata", {}).get("session_id", "unknown")
    )
    duration_ms = (
        session_data.get("duration_ms")
        or session_data.get("metadata", {}).get("duration_ms", 0)
    )
    print(f"      Session: {session_id} | Duration: {duration_ms // 1000}s")

    # ── ACLS FSM Engine ───────────────────────────────────────────────────────
    print("\n[2/6] Running ACLS FSM Rule Engine...")
    # Support both timeline-style (events key) and scenario-style (segments key)
    if "events" in session_data or "metadata" in session_data:
        # Standard UnifiedTimeline JSON
        fsm_input = session_data
    else:
        # Scenario session JSON — build a minimal wrapper so the FSM can run
        fsm_input = {
            "metadata": {
                "session_id": session_id,
                "duration_ms": duration_ms,
            },
            "events": [],   # FSM will produce zero deviations; NLP carries the load
        }

    fsm_data = parse_fsm_events(fsm_input)
    fsm_engine = ACLSEngine()
    fsm_raw = fsm_engine.evaluate(fsm_data)
    fsm_findings = convert_fsm_findings(fsm_raw)
    print(f"      FSM findings: {len(fsm_findings)} deviation(s)")

    # ── Build UnifiedTimeline ─────────────────────────────────────────────────
    unified_timeline = parse_unified_timeline(fsm_input)

    # ── NLP Engine (optional) ─────────────────────────────────────────────────
    nlp_findings: List[FindingRecord] = []
    transcripts: Dict[str, List[TranscriptSegment]] = {"lapel": [], "ceiling": []}

    # Auto-load segments from JSON if not provided externally
    if segments is None and "segments" in session_data:
        segments = session_data["segments"]

    if segments:
        print(f"\n[3/6] Running NLP Engine on {len(segments)} transcript segments...")
        nlp_result = run_nlp_analysis(session_id, segments)
        nlp_findings = convert_nlp_findings(nlp_result)
        transcripts = build_transcript_segments(segments, duration_ms)
        print(f"      NLP findings: {len(nlp_findings)} communication finding(s)")
    else:
        print("\n[3/6] Skipping NLP Engine (no segments found)")

    # ── Scoring Engine ────────────────────────────────────────────────────────
    print("\n[4/6] Running CPR Scoring Engine...")
    all_findings = fsm_findings + nlp_findings
    scoring_engine = ScoringEngine()
    report = scoring_engine.score(
        timeline=unified_timeline,
        findings=all_findings,
        lapel_transcript=transcripts["lapel"],
        ceiling_transcript=transcripts["ceiling"],
        session_id=session_id,
    )
    print(f"      {report.summary_str()}")

    # ── Narrative Engine ──────────────────────────────────────────────────────
    print("\n[5/6] Running Narrative Engine (LLM synthesis)...")
    narrative_engine = NarrativeEngine()
    narrative = narrative_engine.generate(report)
    print(f"      Strengths: {len(narrative.strengths)} | Deficiencies: {len(narrative.deficiencies)}")
    print(f"      Recommendations: {len(narrative.recommendations)} | Summary: {'LLM' if narrative.final_summary else 'fallback'}")

    # ── PDF Generation ────────────────────────────────────────────────────────
    print("\n[6/6] Generating PDF report...")
    pdf_json = build_pdf_input(
        report=report,
        narrative=narrative,
        timeline=unified_timeline,
        session_meta=session_data,
    )
    generate_pdf(pdf_json, output_pdf_path)

    print("\n" + "=" * 60)
    print(f"  PDF REPORT GENERATED: {output_pdf_path}")
    print(f"  {report.summary_str()}")
    print("=" * 60 + "\n")

    return output_pdf_path
