"""
DebriefService — Bridge between Simulation Backend and Standalone Debriefing Engine.

Exposes a unified interface `generate_debrief(session_data)` to process a completed
simulation session through the full ACLS/CPR AI Debriefing pipeline.
"""

import os
import sys
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Ensure backend/debriefing is on sys.path so its internal modules resolve correctly
DEBRIEFING_DIR = Path(__file__).resolve().parent / "debriefing"
if str(DEBRIEFING_DIR) not in sys.path:
    sys.path.insert(0, str(DEBRIEFING_DIR))

logger = logging.getLogger("DebriefService")


class DebriefService:
    """
    Service class wrapping the end-to-end CPR/ACLS AI Debriefing pipeline.
    """

    def __init__(self):
        logger.info("Initializing DebriefService bridge...")

    def generate_debrief(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the full debrief pipeline for a given completed simulation session dict.

        Args:
            session_data: Python dictionary representing a completed simulation session.
                          Expected keys:
                          - session_id (str)
                          - scenario_name / scenario (str)
                          - scenario_type (str)
                          - team_leader_name / team_leader_id (str)
                          - team_size (int)
                          - duration_ms (int)
                          - segments (list[dict]) or events (list[dict])

        Returns:
            Structured dictionary with:
            - overall_score (float)
            - grade (str)
            - findings (list[dict])
            - timeline (dict)
            - domain_scores (list[dict])
            - narrative_report (dict)
            - pdf_path (str)
        """
        if not isinstance(session_data, dict):
            raise ValueError(f"session_data must be a dict, got {type(session_data)}")

        session_id = session_data.get("session_id", session_data.get("id", f"SES-{uuid.uuid4().hex[:6].upper()}"))
        scenario_name = session_data.get("scenario_name", session_data.get("scenario", "ACLS Cardiac Arrest"))
        scenario_type = session_data.get("scenario_type", "VF")
        leader_name = session_data.get("team_leader_name", session_data.get("team_leader_id", "Simulation Team Leader"))
        team_size = session_data.get("team_size", 4)
        duration_ms = session_data.get("duration_ms", 0)
        session_date = session_data.get("date", datetime.now().strftime("%Y-%m-%d"))

        raw_segments = session_data.get("segments", [])

        logger.info(f"Starting debrief pipeline for session: {session_id} ({scenario_name})")

        try:
            # ── Stage 1 & 2: Role attribution ─────────────────────────────────
            from ingestion.diarization import attribute_roles
            if raw_segments:
                attributed_segments = attribute_roles(raw_segments, mode="structured")
            else:
                attributed_segments = []

            # ── Stage 3: Event extraction ──────────────────────────────────────
            from analysis.event_extractor import EventExtractor
            extractor = EventExtractor()
            events = extractor.extract(attributed_segments) if attributed_segments else []

            # ── Stage 4: Communication / NLP Analysis ─────────────────────────
            from analysis.nlp_engine import NLPEngine
            nlp = NLPEngine()
            nlp_res = nlp.process(
                session_id=session_id,
                segments=attributed_segments,
            )
            comm_metrics = nlp_res if isinstance(nlp_res, dict) else {}

            # ── Stage 5: Build UnifiedTimeline ────────────────────────────────
            from schemas.event_schema import UnifiedTimeline
            timeline = UnifiedTimeline(
                session_id=session_id,
                session_date=session_date,
                scenario_name=scenario_name,
                team_leader_id=leader_name,
                events=sorted(events, key=lambda e: e.timestamp_ms),
            )
            timeline.team_size = team_size
            timeline.duration_ms = duration_ms
            timeline.guideline_version = session_data.get("guideline_version", "AHA_2020")
            timeline.scenario_type = scenario_type
            timeline.raw_segments = raw_segments

            # ── Stage 6: ACLS Rule Engine ──────────────────────────────────────
            from schemas.event_schema import FindingRecord, Severity
            findings = []
            try:
                from acls_engine import ACLSEngine
                acls_events_data = {
                    "session_id": session_id,
                    "session_date": session_date,
                    "scenario_type": scenario_type,
                    "events": [
                        {
                            "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                            "timestamp_sec": e.timestamp_ms / 1000,
                            **({"rhythm": e.metadata.get("rhythm")} if hasattr(e, "metadata") and isinstance(e.metadata, dict) and e.metadata.get("rhythm") else {}),
                        }
                        for e in timeline.events
                    ],
                }
                acls_engine_obj = ACLSEngine()
                raw_findings = acls_engine_obj.evaluate(acls_events_data)
                for f in raw_findings:
                    sev_str = str(f.get("severity", "INFO")).upper()
                    sev = Severity[sev_str] if sev_str in Severity.__members__ else Severity.INFO
                    rec = FindingRecord(
                        finding_id=f.get("finding_id", f"fnd_{uuid.uuid4().hex[:8]}"),
                        template_id=f.get("rule_id", ""),
                        domain=f.get("domain", ""),
                        severity=sev,
                        title=f.get("rule_id", ""),
                        description=f.get("deviation_message", ""),
                        guideline_citation=f.get("guideline", ""),
                        recommendation=f.get("recommendation", f.get("deviation_message", "")),
                        reflective_prompt="How could the team improve timing and execution for this step?",
                        timestamp_ms=int(f.get("timestamp_sec", 0) * 1000) if f.get("timestamp_sec") else f.get("timestamp_ms", 0),
                    )
                    findings.append(rec)
            except Exception as fsm_err:
                logger.warning(f"ACLS Engine evaluation fallback: {fsm_err}")
                from analysis.acls_fsm import ACLSFiniteStateMachine
                fsm = ACLSFiniteStateMachine()
                findings = fsm.evaluate(timeline)

            timeline.findings = findings

            # ── Stage 7: Scoring Engine ────────────────────────────────────────
            from analysis.scoring.scoring_engine import ScoringEngine
            scorer = ScoringEngine()
            score_report = scorer.compute(timeline)

            # ── Stage 8: Narrative Synthesis (Ollama fallback) ─────────────────
            debrief_report = None
            try:
                from synthesis.ollama_api import ReportGenerator
                generator = ReportGenerator()
                if generator.is_available():
                    debrief_report = generator.generate_report(timeline=timeline)
            except Exception as n_err:
                logger.warning(f"Narrative synthesis skipped: {n_err}")

            # ── Stage 9: PDF Generation ────────────────────────────────────────
            output_dir = DEBRIEFING_DIR / "output" / "reports"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_pdf_path = output_dir / f"{session_id}_debrief.pdf"

            from synthesis.pdf_generator import generate_pdf
            generate_pdf(
                score_report=score_report,
                findings=findings,
                timeline=timeline,
                output_path=output_pdf_path,
                debrief_report=debrief_report,
            )

            # ── Format Response Dictionary ─────────────────────────────────────
            findings_dicts = []
            for f in findings:
                if isinstance(f, dict):
                    findings_dicts.append(f)
                elif hasattr(f, "to_dict"):
                    findings_dicts.append(f.to_dict())
                else:
                    findings_dicts.append({
                        "finding_id": getattr(f, "finding_id", ""),
                        "title": getattr(f, "title", ""),
                        "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                        "description": getattr(f, "description", ""),
                        "timestamp_ms": getattr(f, "timestamp_ms", 0),
                    })

            domain_scores_list = []
            ds_raw = getattr(score_report, "domain_scores", [])
            if isinstance(ds_raw, list):
                for ds in ds_raw:
                    if isinstance(ds, dict):
                        domain_scores_list.append(ds)
                    else:
                        domain_scores_list.append({
                            "domain_key": getattr(ds, "domain_key", getattr(ds, "domain_label", "domain")),
                            "score": getattr(ds, "final_score", getattr(ds, "score", 0)),
                            "ci_lower": getattr(ds, "ci_lower", 0),
                            "ci_upper": getattr(ds, "ci_upper", 0),
                            "completeness": str(getattr(ds, "completeness_flag", "full")),
                        })

            narrative_dict = {}
            if debrief_report:
                if hasattr(debrief_report, "to_dict"):
                    narrative_dict = debrief_report.to_dict()
                else:
                    narrative_dict = {
                        "scenario_summary": getattr(debrief_report, "scenario_summary", ""),
                        "strengths": getattr(debrief_report, "strengths", ""),
                        "recommendations": getattr(debrief_report, "recommendations", ""),
                    }

            result = {
                "overall_score": round(getattr(score_report, "overall_score", 0.0), 2),
                "grade": getattr(score_report, "overall_grade", getattr(score_report, "grade", "N/A")),
                "findings": findings_dicts,
                "timeline": {
                    "session_id": session_id,
                    "total_events": len(events),
                    "events": [
                        {
                            "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                            "timestamp_ms": e.timestamp_ms,
                            "speaker": getattr(e, "actor_role", None).value if hasattr(getattr(e, "actor_role", None), "value") else str(getattr(e, "actor_role", "")),
                        }
                        for e in events
                    ],
                },
                "domain_scores": domain_scores_list,
                "narrative_report": narrative_dict,
                "pdf_path": str(output_pdf_path),
            }

            logger.info(f"Debrief pipeline completed successfully for {session_id}. Score: {result['overall_score']}")

            # ── Auto-Persist Debrief Report to MySQL ───────────────────────────
            try:
                from database import save_debrief_report_sync
                save_debrief_report_sync({
                    "session_code": session_id,
                    "overall_score": result["overall_score"],
                    "grade": result["grade"],
                    "status": "COMPLETED",
                    "debrief_data": result,
                    "pdf_path": result["pdf_path"],
                    "error_message": None,
                })
            except Exception as db_err:
                logger.warning(f"Auto-persistence warning for debrief report: {db_err}")

            return result

        except Exception as e:
            logger.error(f"Failed to generate debrief for session {session_id}: {e}", exc_info=True)
            try:
                from database import save_debrief_report_sync
                save_debrief_report_sync({
                    "session_code": session_id,
                    "overall_score": 0.0,
                    "grade": "N/A",
                    "status": "FAILED",
                    "debrief_data": {},
                    "pdf_path": "",
                    "error_message": str(e),
                })
            except Exception:
                pass
            raise RuntimeError(f"DebriefService failed: {e}") from e


def generate_debrief(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public entry point function exposing DebriefService.generate_debrief.
    """
    service = DebriefService()
    return service.generate_debrief(session_data)
