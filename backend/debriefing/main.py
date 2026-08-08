"""
CPR Debriefing System — CLI entry point.
Supports two input modes:
  1. --transcript  JSON file from structured scenario data (current mode)
  2. --lapel + --ceiling  Live audio files via Whisper (future mode)

Usage (current):
  python main.py --transcript data/dummy/ses_scn_001.json

Usage (future):
  python main.py --lapel audio/lapel.wav --ceiling audio/ceiling.wav
"""

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")


def ask_language_mode() -> str:
    """
    Interactively prompt the user to select the audio language.
    Returns one of: 'english', 'tamil', 'tanglish'
    """
    print()
    print("  What language is spoken in the audio?")
    print("  [1] English only")
    print("  [2] Tamil only")
    print("  [3] Tanglish  (Tamil + English code-switched)")
    print()
    choices = {
        "1": "english", "2": "tamil", "3": "tanglish",
        "english": "english", "tamil": "tamil", "tanglish": "tanglish",
    }
    while True:
        raw = input("  Enter choice (1/2/3 or name): ").strip().lower()
        if raw in choices:
            mode = choices[raw]
            logger.info(f"Language mode selected: '{mode}'")
            return mode
        print("  Invalid choice. Please enter 1, 2, or 3.")


def load_transcript(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def run_pipeline(args):
    logger.info("=" * 60)
    logger.info("CPR Debriefing System")
    logger.info("=" * 60)

    # ── Stage 1: Load transcript ───────────────────────────────
    if args.transcript:
        logger.info(f"Stage 1: Loading transcript from {args.transcript}")
        transcript = load_transcript(args.transcript)
        session_id    = transcript.get("session_id", args.session_id)
        scenario_name = transcript.get("scenario_name", args.scenario)
        scenario_type = transcript.get("scenario_type", "VF")
        leader_name   = transcript.get("team_leader_name", "Unknown")
        team_size     = transcript.get("team_size", 4)
        duration_ms   = transcript.get("duration_ms", 0)
        raw_segments  = transcript.get("segments", [])
        logger.info(
            f"  Loaded {len(raw_segments)} segments "
            f"— {scenario_name}"
        )
    elif args.audio:
        # ── Audio mode: ask language, then transcribe ──────────
        language_mode = args.language or ask_language_mode()
        logger.info(f"Stage 1: Transcribing audio — {args.audio} (language={language_mode})")
        from ingestion.audio_pipeline import AudioPipeline
        ap = AudioPipeline()
        raw_segments  = ap.process(
            audio_path=args.audio,
            lapel_path=getattr(args, "lapel", None),
            session_id=args.session_id,
            language_mode=language_mode,
        )
        session_id    = args.session_id
        scenario_name = args.scenario
        scenario_type = "VF"
        leader_name   = "Unknown"
        team_size     = 0
        duration_ms   = 0
        logger.info(f"  Transcribed {len(raw_segments)} segments")
    else:
        logger.error("No input provided. Use --transcript <path> or --audio <path>")
        sys.exit(1)

    # ── Stage 2: Role attribution ──────────────────────────────
    logger.info("Stage 2: Role attribution...")
    from ingestion.diarization import attribute_roles
    attributed_segments = attribute_roles(raw_segments, mode="structured")
    logger.info(f"  {len(attributed_segments)} segments attributed")

    # ── Stage 3: Event extraction ──────────────────────────────
    logger.info("Stage 3: Extracting clinical events...")
    from analysis.event_extractor import EventExtractor
    extractor = EventExtractor()
    events = extractor.extract(attributed_segments)
    logger.info(f"  {len(events)} events extracted")

    # ── Stage 4: NLP communication analysis ───────────────────
    logger.info("Stage 4: Communication analysis...")
    from analysis.nlp_engine import NLPEngine
    nlp = NLPEngine()
    leader_segs  = [s for s in attributed_segments
                    if s.get("role") == "team_leader"
                    or s.get("speaker") == "Team Leader"]
    ceiling_segs = [s for s in attributed_segments
                    if s.get("role") != "team_leader"
                    and s.get("speaker") != "Team Leader"]
    nlp_res = nlp.process(
        session_id=session_id,
        segments=attributed_segments,
    )
    nlp_events = []
    comm_metrics = nlp_res if isinstance(nlp_res, dict) else {}
    all_events = events + nlp_events
    logger.info(
        f"  Closed-loop rate: "
        f"{comm_metrics.get('closed_loop_rate', 0)*100:.0f}%"
    )

    # ── Stage 5: Build UnifiedTimeline ────────────────────────
    logger.info("Stage 5: Building unified timeline...")
    from schemas.event_schema import UnifiedTimeline
    timeline = UnifiedTimeline(
        session_id=session_id,
        session_date=transcript.get("date", datetime.now().strftime("%Y-%m-%d")),
        scenario_name=scenario_name,
        team_leader_id=leader_name,
        events=sorted(all_events, key=lambda e: e.timestamp_ms),
    )
    timeline.team_size = team_size
    timeline.duration_ms = duration_ms
    timeline.guideline_version = "AHA_2020"
    timeline.scenario_type = scenario_type
    # Store raw segments so Ollama can inject the full transcript into its prompts
    timeline.raw_segments = raw_segments
    logger.info(f"  Timeline: {len(timeline.events)} total events")

    # ── Stage 6: ACLS FSM ────────────────────────────────────────
    logger.info("Stage 6: ACLS rule engine...")
    try:
        # Prefer the new ACLSEngine (acls_engine package)
        from acls_engine import ACLSEngine
        acls_events_data = {
            "session_id":   session_id,
            "session_date": transcript.get("date", datetime.now().strftime("%Y-%m-%d")),
            "scenario_type": scenario_type,
            "events": [
                {
                    "event_type":    e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                    "timestamp_sec": e.timestamp_ms / 1000,
                    **({"rhythm": e.metadata.get("rhythm")} if hasattr(e, "metadata") and e.metadata.get("rhythm") else {}),
                }
                for e in timeline.events
            ],
        }
        acls_engine_obj = ACLSEngine()
        raw_findings = acls_engine_obj.evaluate(acls_events_data)
        from schemas.event_schema import FindingRecord, Severity
        findings = []
        for f in raw_findings:
            sev_str = f.get("severity", "INFO").upper()
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
        logger.info(f"  {len(findings)} findings (via acls_engine.ACLSEngine)")
        for f in findings:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            logger.info(f"    [{sev.upper()}] {f.title} | {f.description}")
    except ImportError:
        # Fallback to legacy ACLSFiniteStateMachine
        logger.warning("  acls_engine not available — falling back to analysis.acls_fsm")
        from analysis.acls_fsm import ACLSFiniteStateMachine
        fsm = ACLSFiniteStateMachine()
        findings = fsm.evaluate(timeline)
        logger.info(f"  {len(findings)} findings")
        for f in findings:
            sev = f.severity.value if hasattr(f.severity, "value") else f.severity
            logger.info(f"    [{sev.upper()}] {f.title}")


    # ── Stage 7: Scoring ───────────────────────────────────────
    timeline.findings = findings
    from analysis.scoring.scoring_engine import ScoringEngine
    scorer = ScoringEngine()
    score_report = scorer.compute(timeline)
    logger.info(
        f"  Overall: {score_report.overall_score:.1f}/100 "
        f"— {getattr(score_report, 'grade', '')}"
    )

    # ── Stage 8: Ollama narrative synthesis ───────────────────
    logger.info("Stage 8: Generating narrative (Ollama)...")
    debrief_report = None
    try:
        from synthesis.ollama_api import ReportGenerator
        generator = ReportGenerator()
        if generator.is_available():
            debrief_report = generator.generate_report(
                timeline=timeline,
            )
            logger.info("  Narrative generated")
        else:
            logger.warning("  Ollama server not running locally — PDF will use fallback text")
    except Exception as e:
        logger.warning(f"  Ollama synthesis failed: {e}")
        logger.warning("  Continuing without narrative — PDF will use fallback text")

    # ── Stage 9: PDF ───────────────────────────────────────────
    logger.info("Stage 9: Generating PDF...")
    output_dir = Path("output/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{session_id}_debrief.pdf"

    from synthesis.pdf_generator import generate_pdf
    generate_pdf(
        score_report=score_report,
        findings=findings,
        timeline=timeline,
        output_path=output_path,
        debrief_report=debrief_report,
    )
    logger.info(f"  PDF saved: {output_path}")

    logger.info("=" * 60)
    logger.info("Pipeline complete.")
    logger.info(f"Report: {output_path}")
    logger.info("=" * 60)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="CPR Debriefing System"
    )
    parser.add_argument(
        "--transcript", default=None,
        help="Path to structured JSON transcript file"
    )
    parser.add_argument(
        "--audio", default=None,
        help="Path to room/ceiling mic audio file (WAV/MP3/M4A)"
    )
    parser.add_argument(
        "--lapel", default=None,
        help="Path to lapel mic audio (used with --audio for leader boost)"
    )
    parser.add_argument(
        "--language", default=None,
        choices=["english", "tamil", "tanglish"],
        help=(
            "Audio language: english | tamil | tanglish. "
            "Skips auto-detection. If omitted with --audio, you will be prompted."
        ),
    )
    parser.add_argument(
        "--session-id", default="SES-001",
        dest="session_id",
        help="Session ID override"
    )
    parser.add_argument(
        "--scenario", default="Adult Cardiac Arrest",
        help="Scenario name override"
    )
    args = parser.parse_args()

    if not args.transcript and not args.audio:
        parser.print_help()
        sys.exit(1)

    run_pipeline(args)


if __name__ == "__main__":
    main()
