"""
Pipeline Workers — CPR Debriefing System
==========================================
One worker class per pipeline stage.
Each worker: consumes one queue → does work → publishes to next queue.

Instantiate and run the relevant worker on each machine/process.
For a single sim-lab machine: run all workers in separate threads.

Author: Deva
"""

from __future__ import annotations
import logging
import os
from pipeline.broker import Broker

logger = logging.getLogger(__name__)


class TranscriptionWorker:
    """audio_ready → transcript_ready"""
    def __init__(self, broker: Broker):
        self.broker = broker

    def run(self):
        self.broker.consume("audio_ready", self._handle)

    def _handle(self, session_id: str, payload: dict):
        from ingestion.whisper_pipeline import WhisperPipeline
        from ingestion.diarization import DiarizationPipeline

        lapel_path   = payload["lapel_path"]
        ceiling_path = payload.get("ceiling_path")
        protocol     = payload.get("protocol", "acls")

        pipeline = WhisperPipeline(
            model_size=os.getenv("WHISPER_MODEL", "large-v3"),
            device=os.getenv("WHISPER_DEVICE", "cuda"),
        )
        results = pipeline.transcribe_session(lapel_path, ceiling_path or lapel_path)

        # Diarize if ceiling mic available
        if ceiling_path:
            diarizer = DiarizationPipeline()
            results  = diarizer.annotate(results)

        self.broker.publish("transcript_ready", session_id, {
            "protocol": protocol,
            "lapel_segments":   [s.__dict__ for s in results["lapel"].segments],
            "ceiling_segments": [s.__dict__ for s in results["ceiling"].segments],
        })


class ExtractionWorker:
    """transcript_ready → events_ready"""
    def __init__(self, broker: Broker):
        self.broker = broker

    def run(self):
        self.broker.consume("transcript_ready", self._handle)

    def _handle(self, session_id: str, payload: dict):
        from analysis.event_extractor import EventExtractor
        from data.schemas.event_schema import SourceSystem

        lapel_extractor   = EventExtractor(source=SourceSystem.LAPEL)
        ceiling_extractor = EventExtractor(source=SourceSystem.CEILING)

        lapel_events   = lapel_extractor.extract(payload["lapel_segments"])
        ceiling_events = ceiling_extractor.extract(payload["ceiling_segments"])
        all_events     = sorted(
            lapel_events + ceiling_events,
            key=lambda e: e.timestamp_ms,
        )

        self.broker.publish("events_ready", session_id, {
            "protocol": payload["protocol"],
            "events":   [e.to_dict() for e in all_events],
        })


class AnalysisWorker:
    """events_ready → findings_ready"""
    def __init__(self, broker: Broker):
        self.broker = broker

    def run(self):
        self.broker.consume("events_ready", self._handle)

    def _handle(self, session_id: str, payload: dict):
        from data.schemas.event_schema import UnifiedTimeline, UnifiedEvent, EventType

        timeline = UnifiedTimeline(
            session_id=session_id,
            scenario_name=payload.get("scenario_name", "Unknown"),
            team_leader_id=payload.get("team_leader_id", "Unknown"),
            session_date=payload.get("session_date", ""),
        )
        for ev_dict in payload["events"]:
            # Reconstruct minimal UnifiedEvent from serialized dict
            try:
                event = UnifiedEvent(
                    timestamp_ms=ev_dict.get("timestamp_ms", 0),
                    event_type=EventType(ev_dict["event_type"]),
                )
                timeline.add_event(event)
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping malformed event: {e}")

        try:
            # Prefer the new ACLSEngine (acls_engine package)
            from acls_engine import ACLSEngine
            acls_events_data = {
                "session_id":    session_id,
                "session_date":  payload.get("session_date", ""),
                "scenario_type": payload.get("scenario_type", ""),
                "events": [
                    {
                        "event_type":    ev.get("event_type", ""),
                        "timestamp_sec": ev.get("timestamp_ms", 0) / 1000,
                    }
                    for ev in payload["events"]
                ],
            }
            engine_obj = ACLSEngine()
            findings   = engine_obj.evaluate(acls_events_data)
        except ImportError:
            # Fallback to legacy ACLSFiniteStateMachine
            logger.warning("acls_engine not available — falling back to analysis.acls_fsm")
            from analysis.acls_fsm import ACLSFiniteStateMachine
            fsm      = ACLSFiniteStateMachine()
            findings = fsm.evaluate(timeline)

        timeline.findings = findings

        self.broker.publish("findings_ready", session_id, {
            "protocol":   payload["protocol"],
            "timeline":   timeline.summary(),
            "findings":   [f.to_dict() if hasattr(f, "to_dict") else f for f in findings],
            "events":     payload["events"],
        })


class ScoringWorker:
    """findings_ready → scores_ready"""
    def __init__(self, broker: Broker):
        self.broker = broker

    def run(self):
        self.broker.consume("findings_ready", self._handle)

    def _handle(self, session_id: str, payload: dict):
        from scoring.scoring_engine import ScoringEngine
        from data.schemas.event_schema import (
            UnifiedTimeline, FindingRecord, Severity,
        )

        timeline = UnifiedTimeline(
            session_id=session_id,
            scenario_name=payload["timeline"].get("scenario_name", ""),
            team_leader_id=payload["timeline"].get("team_leader_id", ""),
            session_date=payload["timeline"].get("session_date", ""),
        )
        timeline.findings = [
            FindingRecord(**f) for f in payload["findings"]
        ]

        engine = ScoringEngine()
        report = engine.compute(timeline)

        self.broker.publish("scores_ready", session_id, {
            "protocol":      payload["protocol"],
            "score_report":  report.to_dict(),
            "findings":      payload["findings"],
            "timeline":      payload["timeline"],
        })


class ReportWorker:
    """scores_ready → report_ready"""
    def __init__(self, broker: Broker):
        self.broker = broker

    def run(self):
        self.broker.consume("scores_ready", self._handle)

    def _handle(self, session_id: str, payload: dict):
        from synthesis.openai_api import ReportGenerator
        from synthesis.pdf_generator import generate_pdf

        generator    = ReportGenerator()
        debrief      = generator.generate_report_from_payload(payload)
        pdf_path     = generate_pdf(
            score_report=payload["score_report"],
            findings=payload["findings"],
            timeline=payload["timeline"],
            output_path=f"output/{session_id}_report.pdf",
            debrief_report=debrief,
        )

        self.broker.publish("report_ready", session_id, {
            "pdf_path":      str(pdf_path),
            "session_id":    session_id,
            "overall_score": payload["score_report"]["overall_score"],
            "overall_grade": payload["score_report"]["overall_grade"],
        })
        logger.info(f"Report delivered: {pdf_path}")
