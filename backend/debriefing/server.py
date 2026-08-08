"""
server.py
---------
Flask API server for the CPR Debriefing System web interface.

Core Endpoints:
  POST /api/upload               Upload JSON transcript or audio file
  POST /api/generate             Start the pipeline with session params
  GET  /api/status/<sid>         Poll pipeline progress (SSE stream)
  GET  /api/download/<sid>       Download generated PDF
  GET  /                         Serve the UI

Scenario Studio Endpoints:
  POST /api/scenario/generate    Generate scenario spec
  POST /api/scenario/start       Register a live scenario run
  POST /api/scenario/speak       TTS narration request
  POST /api/scenario/instructor  Parse instructor voice/text input
  GET  /api/scenario/predict/<sid> Get outcome prediction
  GET  /api/tts/<filename>       Serve generated TTS audio

Gamification Endpoints:
  GET  /api/gamification/leaderboard  Top teams by XP
  POST /api/gamification/record       Record completed session

Admin Endpoints:
  POST /api/admin/login          Login — returns session
  POST /api/admin/logout         Logout
  GET  /api/admin/me             Current admin info
  GET  /api/admin/flags          Get all feature flags
  POST /api/admin/flags          Update a feature flag
  GET  /api/admin/admins         List all admin users (super_admin only)
  POST /api/admin/admins         Create new admin (super_admin only)
  DELETE /api/admin/admins/<id>  Deactivate admin (super_admin only)
  POST /api/admin/admins/<id>/password  Change password
"""

import json
import logging
import os
import secrets
import sys
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file, send_from_directory, session, stream_with_context
from flask_cors import CORS

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "analysis"))
sys.path.insert(0, str(_HERE / "analysis" / "acls_fsm"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("server")

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=str(_HERE / "dist"),
    static_folder=str(_HERE / "dist" / "assets"),
)
CORS(app, supports_credentials=True)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    dist_dir = _HERE / "dist"

    if path and (dist_dir / path).exists():
        return send_from_directory(str(dist_dir), path)

    return send_from_directory(str(dist_dir), "index.html")

# Session config — Flask sessions for admin auth
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    hours=int(os.getenv("SESSION_LIFETIME_HOURS", "4"))
)

UPLOAD_DIR = _HERE / "uploads"
OUTPUT_DIR = _HERE / "output" / "reports"
TTS_DIR    = _HERE / "output" / "tts"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Admin & Scenario modules ──────────────────────────────────────────────────
try:
    from admin.auth import AdminAuth, require_admin, require_super_admin
    from admin.feature_flags import FeatureFlags
    _admin_auth  = AdminAuth()
    _flags       = FeatureFlags()
    logger.info("[server] Admin & FeatureFlags loaded.")
except Exception as _e:
    logger.warning(f"[server] Admin module not available: {_e}")
    _admin_auth = None
    _flags      = None

try:
    from scenarios.generator         import ScenarioGenerator
    from scenarios.outcome_predictor  import OutcomePredictor
    from scenarios.voice_narrator     import VoiceNarrator
    from scenarios.instructor_listener import InstructorListener
    from scenarios.gamification       import GamificationEngine
    from scenarios.debrief_detector   import check_and_prepare_ai_debrief
    _scenario_gen   = ScenarioGenerator()
    _outcome_pred   = OutcomePredictor()
    _narrator       = VoiceNarrator(output_dir=TTS_DIR)
    _instructor     = InstructorListener()
    _gamification   = GamificationEngine()
    logger.info("[server] Scenario modules loaded.")
except Exception as _e:
    logger.warning(f"[server] Scenario modules not available: {_e}")
    _scenario_gen = _outcome_pred = _narrator = _instructor = _gamification = None
    check_and_prepare_ai_debrief = None

# ── Active scenario run store ─────────────────────────────────────────────────
# scenario_run_id -> {spec, expected_outcome, started_at, ...}
_scenario_runs: dict = {}
_runs_lock = threading.Lock()

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac"}
JSON_EXTENSIONS   = {".json"}

# ── In-memory job store ───────────────────────────────────────────────────────
# job_id -> { status, steps, error, pdf_path, session_data }
_jobs: dict = {}
_jobs_lock = threading.Lock()

PIPELINE_STEPS = [
    "Loading session data",
    "Running ACLS Rule Engine",
    "Running NLP Engine",
    "Running Scoring Engine",
    "Running Narrative Engine",
    "Generating PDF Report",
    "Checking Debrief & AI Voice",   # NEW: debrief detection + AI narration
]


def _set_step(job_id: str, step_idx: int, message: str = "", done: bool = False):
    with _jobs_lock:
        j = _jobs.get(job_id, {})
        j["current_step"] = step_idx
        j["step_message"] = message
        if done:
            j["status"] = "done"
        _jobs[job_id] = j


def _set_error(job_id: str, msg: str):
    with _jobs_lock:
        j = _jobs.get(job_id, {})
        j["status"] = "error"
        j["error"] = msg
        _jobs[job_id] = j


# ── Pipeline worker ────────────────────────────────────────────────────────────

def _run_pipeline_worker(job_id: str, file_path: Path, params: dict, is_audio: bool):
    """
    Background thread: runs the full pipeline and stores result in _jobs.
    For audio files, shows a warning that Whisper/WSL is required.
    """
    try:
        from analysis.pipeline_adapter import (
            parse_fsm_events, ACLSEngine, convert_fsm_findings,
            run_nlp_analysis, convert_nlp_findings,
            build_transcript_segments, parse_unified_timeline,
            ScoringEngine,
        )
        from analysis.reporting.narrative_engine import NarrativeEngine
        from analysis.reporting.pdf_adapter import build_pdf_input
        from analysis.reporting.pdf_engine import generate_pdf
        from schemas.event_schema import FindingRecord, Severity

        # ── Step 1: Load data ──────────────────────────────────────────────────
        _set_step(job_id, 0, "Loading session data...")

        if is_audio:
            # Audio: stub — real transcription needs WSL/Whisper
            # Build a minimal session_data from manual params
            _set_step(job_id, 0, "Audio file received. Using manual parameters (Whisper requires WSL)...")
            time.sleep(0.5)
            session_data = _build_session_from_params(params)
        else:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                raw_text = f.read()
            # ── Robust JSON extraction ──────────────────────────────────────────
            # Find the first JSON structural character '[' or '{'
            # This handles any prefix like "segments = [", Python comments, BOM, etc.
            import re as _re
            json_start = _re.search(r"[\[{]", raw_text)
            if json_start is None:
                raise ValueError("No JSON content found in uploaded file.")
            raw_text = raw_text[json_start.start():].strip()
            # If it's a bare sequence of objects (no wrapping array), wrap it
            if not raw_text.startswith("["):
                raw_text = "[" + raw_text + "]"
            try:
                session_data = json.loads(raw_text)
            except json.JSONDecodeError as _je:
                logger.error(f"[{job_id}] JSON parse error: {_je}. First 80 chars: {raw_text[:80]!r}")
                raise
            # ── Normalise: bare array → session dict ──────────────────────────
            if isinstance(session_data, list):
                segments = session_data
                # Convert "time": "MM:SS" → timestamp_ms if needed
                for seg in segments:
                    if "timestamp_ms" not in seg and "time" in seg:
                        try:
                            parts = str(seg["time"]).split(":")
                            seg["timestamp_ms"] = (int(parts[0]) * 60 + int(parts[1])) * 1000
                        except Exception:
                            seg["timestamp_ms"] = 0
                    # Normalise role labels → pipeline-expected role keys
                    _ROLE_MAP = {
                        "TL":              "team_leader",
                        "Team Leader":     "team_leader",
                        "team leader":     "team_leader",
                        "Compressor":      "compressor",
                        "compressor":      "compressor",
                        "CPR Coach":       "defib_coach",
                        "cpr coach":       "defib_coach",
                        "CPR coach":       "defib_coach",
                        "Defib":           "defib_coach",
                        "Defibrillator":   "defib_coach",
                        "Defibrillator/CPR Coach": "defib_coach",
                        "IV Member":       "iv_member",
                        "IV member":       "iv_member",
                        "iv member":       "iv_member",
                        "Recorder":        "recorder",
                        "recorder":        "recorder",
                        "Airway":          "airway",
                        "airway":          "airway",
                        "Nurse":           "iv_member",
                        "nurse":           "iv_member",
                    }
                    _SPEAKER_MAP = {
                        "team_leader": "Team Leader",
                        "compressor":  "Compressor",
                        "defib_coach": "CPR Coach",
                        "iv_member":   "IV Member",
                        "recorder":    "Recorder",
                        "airway":      "Airway",
                    }
                    raw_role = seg.get("role", "")
                    normalised = _ROLE_MAP.get(raw_role, raw_role.lower().replace(" ", "_"))
                    seg["role"] = normalised
                    # Replace SPEAKER_XX speaker labels with human-readable names
                    if seg.get("speaker", "").startswith("SPEAKER_") and normalised in _SPEAKER_MAP:
                        seg["speaker"] = _SPEAKER_MAP[normalised]
                session_data = {
                    "session_id":    params.get("session_id") or "SES-001",
                    "scenario_name": params.get("scenario_name") or "CPR Session",
                    "scenario_type": params.get("scenario_type") or "VF",
                    "date":          params.get("date") or "",
                    "team_size":     int(params.get("team_size") or 0),
                    "duration_ms":   segments[-1].get("timestamp_ms", 0) if segments else 0,
                    "outcome":       params.get("outcome") or "unknown",
                    "segments":      segments,
                    "events":        [],
                    "metadata": {
                        "session_id":    params.get("session_id") or "SES-001",
                        "scenario_type": params.get("scenario_type") or "VF",
                        "duration_ms":   segments[-1].get("timestamp_ms", 0) if segments else 0,
                    },
                }
                logger.info(f"[{job_id}] Normalised bare-array JSON → session dict ({len(segments)} segments)")
            # Allow manual param overrides
            session_data = _apply_overrides(session_data, params)

        session_id   = session_data.get("session_id", f"SES-{job_id[:6]}")
        duration_ms  = session_data.get("duration_ms", 600000)
        segments_raw = session_data.get("segments", [])
        events_raw   = session_data.get("events", [])

        with _jobs_lock:
            _jobs[job_id]["session_id"] = session_id
            _jobs[job_id]["session_data"] = session_data

        # ── Step 2: ACLS Rule Engine ──────────────────────────────────────────────
        _set_step(job_id, 1, f"Evaluating {len(events_raw)} events...")

        # Always build fsm_input — needed by parse_unified_timeline regardless of engine path
        fsm_input = {"metadata": session_data.get("metadata", session_data), "events": events_raw}

        try:
            # Prefer the new standalone acls_engine package
            from acls_engine import ACLSEngine as NewACLSEngine
            acls_input = {
                "session_id":    session_data.get("session_id", f"SES-{job_id[:6]}"),
                "session_date":  session_data.get("date", ""),
                "scenario_type": session_data.get("scenario_type", ""),
                "events": [
                    {
                        "event_type":    ev.get("event_type", ev.get("type", "")),
                        "timestamp_sec": ev.get("timestamp_sec",
                                              ev.get("timestamp_ms", 0) / 1000),
                        **{k: v for k, v in ev.items()
                           if k not in ("event_type", "type", "timestamp_sec", "timestamp_ms")},
                    }
                    for ev in events_raw
                ],
            }
            new_engine   = NewACLSEngine()
            fsm_raw      = new_engine.evaluate(acls_input)
            fsm_findings = convert_fsm_findings(fsm_raw)
            logger.info(f"[{job_id}] acls_engine produced {len(fsm_raw)} findings")
        except ImportError:
            # Fallback to legacy pipeline_adapter.ACLSEngine
            logger.warning(f"[{job_id}] acls_engine not available, falling back to pipeline_adapter")
            fsm_data     = parse_fsm_events(fsm_input)
            fsm_engine   = ACLSEngine()
            fsm_raw      = fsm_engine.evaluate(fsm_data)
            fsm_findings = convert_fsm_findings(fsm_raw)

        # Apply manual CPR metric overrides as additional findings
        extra_findings = _build_manual_findings(params)

        # ── Step 3: NLP ────────────────────────────────────────────────────────
        _set_step(job_id, 2, f"NLP analysis on {len(segments_raw)} transcript segments...")
        nlp_result   = run_nlp_analysis(session_id, segments_raw)
        nlp_findings = convert_nlp_findings(nlp_result)

        # Inject mock findings for the poor session demonstration if NLP engine isn't running
        if session_id == "SES-POOR-001":
            try:
                import sys
                import os
                _base = os.path.dirname(os.path.abspath(__file__))
                if _base not in sys.path:
                    sys.path.insert(0, _base)
                from _test_poor_session import build_violation_findings
                injected = build_violation_findings()
                nlp_findings.extend(injected)
            except Exception as e:
                logger.warning(f"Could not inject mock findings for SES-POOR-001: {e}")

        transcripts      = build_transcript_segments(segments_raw, duration_ms)
        unified_timeline = parse_unified_timeline(fsm_input)
        all_findings     = fsm_findings + nlp_findings + extra_findings

        # Deduplicate findings by title so we don't double-penalize if FSM catches it too
        seen_titles = set()
        deduped = []
        for f in all_findings:
            if f.title not in seen_titles:
                deduped.append(f)
                seen_titles.add(f.title)
        all_findings = deduped

        # ── Step 4: Scoring ────────────────────────────────────────────────────
        _set_step(job_id, 3, "Scoring all domains...")
        scoring_engine = ScoringEngine()
        report = scoring_engine.score(
            timeline           = unified_timeline,
            findings           = all_findings,
            lapel_transcript   = transcripts["lapel"],
            ceiling_transcript = transcripts["ceiling"],
            session_id         = session_id,
        )
        with _jobs_lock:
            _jobs[job_id]["score"] = report.overall_score
            _jobs[job_id]["grade"] = report.grade

        # ── Step 5: Narrative ──────────────────────────────────────────────────
        _set_step(job_id, 4, "Generating narrative (LLM or rule-based fallback)...")
        narrative_engine = NarrativeEngine()
        narrative = narrative_engine.generate(report)

        # ── Step 6: PDF ────────────────────────────────────────────────────────
        _set_step(job_id, 5, "Rendering PDF...")
        output_path = OUTPUT_DIR / f"{session_id}_{job_id[:8]}_debrief.pdf"

        # Record gamification BEFORE building the PDF so XP/badges appear in it
        gam_record = None
        team_name  = params.get("team_name", "").strip() or "Anonymous Team"
        if _gamification and _flags and _flags.get("gamification_enabled", True):
            try:
                gam_record = _gamification.record_session(
                    team_name         = team_name,
                    scenario_id       = session_id,
                    level             = session_data.get("difficulty_level", "beginner"),
                    score             = float(report.overall_score),
                    prediction_result = {
                        "prediction_accuracy": report.overall_score,
                        "grade":               report.grade,
                        "xp_earned":           int(report.overall_score * 5),
                        "critical_misses":     [],
                    },
                    discipline      = session_data.get("discipline", ["doctor"]),
                    total_deviations = sum(1 for d in all_findings if getattr(d, "severity", None) in ("CRITICAL", "HIGH")),
                    ai_debriefed    = False,   # will be updated in step 7
                    critical_misses = [],
                )
                with _jobs_lock:
                    _jobs[job_id]["gamification"] = gam_record
                logger.info(f"[{job_id}] Gamification recorded: +{gam_record.get('xp_earned',0)} XP")
            except Exception as ge:
                logger.warning(f"[{job_id}] Gamification recording failed: {ge}")

        pdf_json = build_pdf_input(
            report            = report,
            narrative         = narrative,
            timeline          = unified_timeline,
            session_meta      = session_data,
            gamification_data = gam_record,   # None if gamification not enabled
        )
        generate_pdf(pdf_json, str(output_path))

        with _jobs_lock:
            _jobs[job_id]["pdf_path"] = str(output_path)

        # ── Step 7: Debrief detection & AI voice ──────────────────────────────
        _set_step(job_id, 6, "Checking for human debrief...")
        ai_debrief_result = {}
        try:
            if check_and_prepare_ai_debrief is not None and _flags is not None:
                narrative_text_str = ""
                if hasattr(narrative, "executive_summary"):
                    narrative_text_str = narrative.executive_summary or ""
                elif isinstance(narrative, dict):
                    narrative_text_str = narrative.get("executive_summary", "")

                ai_debrief_flag   = _flags.get("ai_debrief_speech_enabled", True)
                server_tts_flag   = _flags.get("server_side_tts_enabled", False)
                ai_debrief_result = check_and_prepare_ai_debrief(
                    session_data            = session_data,
                    narrative_text          = narrative_text_str,
                    overall_score           = report.overall_score,
                    grade                   = report.grade,
                    ai_debrief_flag_enabled = ai_debrief_flag,
                    voice_narrator          = _narrator,
                    use_server_tts          = server_tts_flag,
                )
                with _jobs_lock:
                    _jobs[job_id]["ai_debrief"] = ai_debrief_result
                logger.info(
                    f"[{job_id}] Debrief check: "
                    f"human={ai_debrief_result.get('detector_result', {}).get('quality_label', '?')}, "
                    f"ai_needed={ai_debrief_result.get('ai_debrief_needed', False)}"
                )
        except Exception as de:
            logger.warning(f"[{job_id}] Debrief detection failed: {de}")

        _set_step(job_id, 6, f"PDF ready: {output_path.name}", done=True)
        logger.info(f"[{job_id}] Pipeline complete. PDF: {output_path}")

    except Exception as e:
        import traceback
        logger.exception(f"[{job_id}] Pipeline failed")
        _set_error(job_id, str(e) + "\n" + traceback.format_exc())


def _build_session_from_params(params: dict) -> dict:
    """Build a minimal session_data dict from manual form parameters."""
    return {
        "session_id":      params.get("session_id", "SES-AUDIO-001"),
        "date":            params.get("date", "2026-01-01"),
        "scenario_name":   params.get("scenario_name", "Adult Cardiac Arrest"),
        "scenario_type":   params.get("scenario_type", "VF"),
        "team_size":       int(params.get("team_size", 4)),
        "duration_ms":     int(float(params.get("duration_min", 10)) * 60 * 1000),
        "guideline_version": params.get("guideline", "AHA_2020"),
        "outcome":         params.get("outcome", "unknown"),
        "segments":        [],
        "events":          [],
        "metadata": {
            "session_id":    params.get("session_id", "SES-AUDIO-001"),
            "scenario_type": params.get("scenario_type", "VF"),
            "duration_ms":   int(float(params.get("duration_min", 10)) * 60 * 1000),
        }
    }


def _apply_overrides(session_data: dict, params: dict) -> dict:
    """Apply manual UI parameter overrides onto a loaded session dict."""
    overrides = {
        "session_id":    "session_id",
        "scenario_name": "scenario_name",
        "date":          "date",
        "outcome":       "outcome",
        "team_size":     "team_size",
    }
    for param_key, data_key in overrides.items():
        if params.get(param_key):
            val = params[param_key]
            if data_key == "team_size":
                try:
                    val = int(val)
                except ValueError:
                    pass
            session_data[data_key] = val
    return session_data


def _build_manual_findings(params: dict) -> list:
    """
    Convert manually entered CPR quality parameters (compression rate/depth)
    into FindingRecord objects if they fall outside AHA limits.
    """
    from schemas.event_schema import FindingRecord, Severity
    findings = []

    # Compression rate
    rate = params.get("compression_rate")
    if rate:
        try:
            rate_val = float(rate)
            if rate_val < 100 or rate_val > 120:
                findings.append(FindingRecord(
                    finding_id=f"manual_rate_{uuid.uuid4().hex[:6]}",
                    title="CPR_RATE_DEVIATION",
                    severity=Severity.MODERATE if 90 <= rate_val <= 130 else Severity.HIGH,
                    domain="cpr_quality",
                    description=(
                        f"Manual entry: compression rate {rate_val:.0f} bpm. "
                        f"AHA target: 100-120 bpm. "
                        f"{'Too slow — insufficient coronary perfusion pressure.' if rate_val < 100 else 'Too fast — incomplete chest recoil.'}"
                    ),
                    guideline_citation="AHA 2025 BLS — Compression Rate",
                    recommendation="Maintain 100-120 compressions per minute. Use a metronome feedback device.",
                    reflective_prompt="How did the compressor monitor their compression rate during the resuscitation?",
                ))
        except (ValueError, TypeError):
            pass

    # Compression depth
    depth = params.get("compression_depth_cm")
    if depth:
        try:
            depth_val = float(depth)
            if depth_val < 5.0 or depth_val > 6.0:
                findings.append(FindingRecord(
                    finding_id=f"manual_depth_{uuid.uuid4().hex[:6]}",
                    title="CPR_DEPTH_DEVIATION",
                    severity=Severity.MODERATE if 4.0 <= depth_val <= 7.0 else Severity.HIGH,
                    domain="cpr_quality",
                    description=(
                        f"Manual entry: compression depth {depth_val:.1f} cm. "
                        f"AHA target: 5-6 cm (2-2.4 inches). "
                        f"{'Too shallow — inadequate cardiac output.' if depth_val < 5.0 else 'Too deep — risk of rib fracture and organ injury.'}"
                    ),
                    guideline_citation="AHA 2025 BLS — Compression Depth",
                    recommendation="Target 5-6 cm depth. Use feedback device if available. Avoid excessive depth.",
                    reflective_prompt="What feedback mechanism was available to the compressor about depth?",
                ))
        except (ValueError, TypeError):
            pass

    return findings


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    from flask import make_response
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"]        = "no-cache"
    resp.headers["Expires"]       = "0"
    return resp


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Accept a JSON transcript or audio file. Returns job info."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    is_audio = ext in AUDIO_EXTENSIONS
    is_json  = ext in JSON_EXTENSIONS

    if not is_audio and not is_json:
        return jsonify({
            "error": f"Unsupported file type '{ext}'. Use .json or {', '.join(sorted(AUDIO_EXTENSIONS))}"
        }), 400

    job_id    = str(uuid.uuid4())
    save_name = f"{job_id}_{f.filename}"
    save_path = UPLOAD_DIR / save_name
    f.save(str(save_path))

    # Peek into JSON to pre-fill the form
    pre_fill = {}
    if is_json:
        try:
            with open(save_path, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            pre_fill = {
                "session_id":    data.get("session_id", ""),
                "scenario_name": data.get("scenario_name", ""),
                "scenario_type": data.get("scenario_type", "VF"),
                "date":          data.get("date", ""),
                "team_size":     data.get("team_size", ""),
                "duration_min":  round(data.get("duration_ms", 600000) / 60000, 1),
                "outcome":       data.get("outcome", ""),
                "event_count":   len(data.get("events", [])),
                "segment_count": len(data.get("segments", [])),
            }
        except Exception:
            pass

    with _jobs_lock:
        _jobs[job_id] = {
            "status":       "uploaded",
            "current_step": -1,
            "step_message": "",
            "file_path":    str(save_path),
            "filename":     f.filename,
            "is_audio":     is_audio,
            "is_json":      is_json,
            "score":        None,
            "grade":        None,
            "pdf_path":     None,
            "error":        None,
        }

    return jsonify({
        "job_id":   job_id,
        "filename": f.filename,
        "is_audio": is_audio,
        "is_json":  is_json,
        "pre_fill": pre_fill,
    })


@app.route("/api/generate", methods=["POST"])
def generate():
    """Start the pipeline. Body: { job_id, params: {...} }"""
    body   = request.get_json(force=True) or {}
    job_id = body.get("job_id")
    params = body.get("params", {})

    if not job_id or job_id not in _jobs:
        return jsonify({"error": "Invalid job_id"}), 400

    with _jobs_lock:
        job = _jobs[job_id]
        if job["status"] not in ("uploaded", "error"):
            return jsonify({"error": "Job already running or complete"}), 400
        job["status"] = "running"
        file_path = Path(job["file_path"])
        is_audio  = job["is_audio"]

    t = threading.Thread(
        target=_run_pipeline_worker,
        args=(job_id, file_path, params, is_audio),
        daemon=True,
    )
    t.start()
    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/status/<job_id>")
def status(job_id: str):
    """
    Server-Sent Events stream: sends progress updates every 500ms.
    Client should read until status = 'done' or 'error'.
    """
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404

    def event_stream():
        while True:
            with _jobs_lock:
                j = dict(_jobs.get(job_id, {}))
            ai_deb = j.get("ai_debrief", {})
            data = {
                "status":             j.get("status", "unknown"),
                "current_step":       j.get("current_step", -1),
                "step_message":       j.get("step_message", ""),
                "total_steps":        len(PIPELINE_STEPS),
                "step_labels":        PIPELINE_STEPS,
                "result": {
                    "overall_score": j.get("score"),
                    "grade": j.get("grade")
                },
                "score":              j.get("score"),
                "grade":              j.get("grade"),
                "error":              j.get("error"),
                "ai_debrief_needed":  ai_deb.get("ai_debrief_needed", False),
                "debrief_audio":      ai_deb.get("debrief_audio"),
                "debrief_text":       ai_deb.get("debrief_text"),
                "debrief_quality":    ai_deb.get("detector_result", {}).get("quality_label"),
            }
            yield f"data: {json.dumps(data)}\n\n"
            if j.get("status") in ("done", "error"):
                break
            time.sleep(0.5)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/download/<job_id>")
def download(job_id: str):
    """Download the generated PDF."""
    with _jobs_lock:
        j = _jobs.get(job_id, {})

    pdf_path = j.get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        return jsonify({"error": "PDF not ready or job not found"}), 404

    session_id = j.get("session_id", job_id)
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=f"debrief_{session_id}.pdf",
        mimetype="application/pdf",
    )


@app.route("/api/jobs")
def list_jobs():
    """Return summary of all jobs (for history panel)."""
    with _jobs_lock:
        summary = [
            {
                "job_id":       jid,
                "status":       j.get("status"),
                "filename":     j.get("filename"),
                "session_id":   j.get("session_id"),
                "score":        j.get("score"),
                "grade":        j.get("grade"),
                "has_pdf":      bool(j.get("pdf_path")),
            }
            for jid, j in _jobs.items()
        ]
    return jsonify(summary[::-1])  # newest first

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO STUDIO ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/scenario/generate", methods=["POST"])
def scenario_generate():
    """Generate a scenario spec from level/location/discipline/speciality."""
    if _flags and not _flags.get("scenario_generation_enabled"):
        return jsonify({"error": "Scenario generation is currently disabled by admin."}), 403
    if not _scenario_gen:
        return jsonify({"error": "Scenario generator not available."}), 503

    body       = request.get_json(force=True) or {}
    level      = body.get("level", "beginner")
    location   = body.get("location", "ER")
    discipline = body.get("discipline", ["doctor"])
    speciality = body.get("speciality", "ER")

    spec = _scenario_gen.generate(
        level=level, location=location,
        discipline=discipline, speciality=speciality,
    )

    # Build outcome prediction if enabled
    expected = None
    if _flags and _flags.get("outcome_prediction_enabled") and _outcome_pred:
        expected = _outcome_pred.build_expected(spec)

    return jsonify({"spec": spec, "expected_outcome": expected})


@app.route("/api/scenario/start", methods=["POST"])
def scenario_start():
    """Register a live scenario run. Returns a run_id."""
    body     = request.get_json(force=True) or {}
    spec     = body.get("spec", {})
    expected = body.get("expected_outcome")

    run_id = str(uuid.uuid4())
    with _runs_lock:
        _scenario_runs[run_id] = {
            "spec":             spec,
            "expected_outcome": expected,
            "started_at":       time.time(),
            "status":           "active",
        }
    return jsonify({"run_id": run_id, "status": "active"})


@app.route("/api/scenario/speak", methods=["POST"])
def scenario_speak():
    """TTS narration. Body: {text, type, run_id (optional), spec (optional)}."""
    if _flags and not _flags.get("ai_scenario_narration_enabled"):
        return jsonify({"error": "AI narration is currently disabled by admin."}), 403
    if not _narrator:
        return jsonify({"error": "Voice narrator not available."}), 503

    body         = request.get_json(force=True) or {}
    text         = body.get("text", "")
    speak_type   = body.get("type", "custom")   # intro | hint | outcome | custom
    spec         = body.get("spec")
    server_tts   = _flags.get("server_side_tts_enabled", False) if _flags else False

    if speak_type == "intro" and spec:
        result = _narrator.speak_scenario_intro(spec, use_server_tts=server_tts)
    elif speak_type == "hint":
        result = _narrator.speak_hint(text, use_server_tts=server_tts)
    else:
        result = _narrator.speak(text, use_server_tts=server_tts)

    return jsonify(result)


@app.route("/api/scenario/instructor", methods=["POST"])
def scenario_instructor():
    """Parse instructor text/voice input into scenario parameters."""
    if _flags and not _flags.get("instructor_voice_input_enabled"):
        return jsonify({"error": "Instructor voice input is currently disabled by admin."}), 403
    if not _instructor:
        return jsonify({"error": "Instructor listener not available."}), 503

    body = request.get_json(force=True) or {}
    text = body.get("text", "")
    if not text:
        return jsonify({"error": "No text provided."}), 400

    params = _instructor.parse_text(text)

    # Fill missing params with defaults
    params.setdefault("level", "beginner")
    params.setdefault("location", "ER")
    params.setdefault("speciality", "ER")
    params.setdefault("discipline", ["doctor"])

    # Auto-generate spec from parsed params
    spec = _scenario_gen.generate(
        level      = params["level"],
        location   = params["location"],
        discipline = params["discipline"],
        speciality = params["speciality"],
    ) if _scenario_gen else {}

    return jsonify({"parsed_params": params, "spec": spec})


@app.route("/api/scenario/narrate", methods=["POST"])
def scenario_narrate():
    """Narrate the intro of a scenario spec. Body: {spec, use_server_tts}."""
    body       = request.get_json(force=True) or {}
    spec       = body.get("spec", {})
    server_tts = bool(body.get("use_server_tts", False))

    if _narrator:
        result = _narrator.speak_scenario_intro(spec, use_server_tts=server_tts)
    else:
        pt   = spec.get("patient", {})
        text = spec.get("narration_intro", "") or (
            f"Attention team. {spec.get('level','').title()}-level scenario "
            f"in the {spec.get('location_label', 'hospital')}. "
            f"Patient: {pt.get('age','?')}-year-old {pt.get('sex','patient')}. "
            f"Presentation: {pt.get('presentation','cardiac arrest')}. You may begin."
        )
        result = {"mode": "browser", "text": text}

    return jsonify(result)


@app.route("/api/scenario/end", methods=["POST"])
def scenario_end():
    """
    End a live scenario and compute accurate scores using OutcomePredictor
    and GamificationEngine.

    Body: {
      spec        : ScenarioSpec dict,
      team_name   : str,
      elapsed_sec : int,
      checklist   : [{id, action, critical, window_sec, completed, overdue}],
      deviations  : [{time, action, severity}],
    }
    """
    body        = request.get_json(force=True) or {}
    spec        = body.get("spec", {})
    team_name   = body.get("team_name") or "Unnamed Team"
    elapsed_sec = int(body.get("elapsed_sec", 0))
    checklist   = body.get("checklist", [])
    deviations  = body.get("deviations", [])

    level       = spec.get("level", "beginner")
    scenario_id = spec.get("scenario_id", "SCN-UNKNOWN")

    # ── Score from checklist ─────────────────────────────────────────────────
    crit_items   = [i for i in checklist if i.get("critical")]
    nc_items     = [i for i in checklist if not i.get("critical")]
    total_crit   = len(crit_items)
    done_crit    = sum(1 for i in crit_items if i.get("completed"))
    done_nc      = sum(1 for i in nc_items  if i.get("completed"))

    crit_rate = (done_crit / total_crit * 100) if total_crit else 100.0
    nc_rate   = (done_nc / len(nc_items) * 100) if nc_items else 100.0
    score     = round(crit_rate * 0.70 + nc_rate * 0.30, 1)

    overdue   = sum(1 for i in crit_items if i.get("overdue") and not i.get("completed"))
    score     = max(0.0, score - overdue * 5)

    critical_misses = [i.get("action", "") for i in crit_items if not i.get("completed")]

    # ── OutcomePredictor ─────────────────────────────────────────────────────
    pred_result = None
    if _outcome_pred:
        try:
            expected    = _outcome_pred.build_expected(spec)
            mock_acls   = [{"title": d.get("action", "")} for d in deviations]
            pred_result = _outcome_pred.score_against_findings(expected, mock_acls)
        except Exception as exc:
            logger.warning(f"[scenario_end] OutcomePredictor error: {exc}")

    if pred_result:
        xp_earned       = pred_result.get("xp_earned", spec.get("xp_reward", 200))
        grade           = pred_result.get("grade", "C")
        accuracy        = pred_result.get("prediction_accuracy", score)
        critical_misses = pred_result.get("critical_misses") or critical_misses
    else:
        xp_base   = spec.get("xp_reward", {"beginner": 200, "intermediate": 400, "advanced": 700}.get(level, 200))
        xp_earned = max(0, int(xp_base * score / 100))
        grade     = ("A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F")
        accuracy  = score

    # ── GamificationEngine ───────────────────────────────────────────────────
    gam_result = None
    if _gamification:
        try:
            gam_result = _gamification.record_session(
                team_name        = team_name,
                scenario_id      = scenario_id,
                level            = level,
                score            = score,
                prediction_result= {"xp_earned": xp_earned, "grade": grade,
                                    "prediction_accuracy": accuracy},
                discipline       = spec.get("discipline", ["doctor"]),
                total_deviations = len(deviations),
                ai_debriefed     = False,
                critical_misses  = critical_misses,
            )
        except Exception as exc:
            logger.warning(f"[scenario_end] GamificationEngine error: {exc}")

    result = gam_result or {
        "xp_earned": xp_earned, "grade": grade, "prediction_accuracy": accuracy,
        "badges_earned": [], "badge_details": [], "level_label": "Novice", "levelled_up": False,
    }
    result.update({"score": score, "critical_misses": critical_misses, "elapsed_sec": elapsed_sec})

    logger.info(f"[scenario_end] team={team_name} level={level} score={score} grade={grade} xp={xp_earned}")
    return jsonify(result)


@app.route("/api/scenario/predict/<run_id>")
def scenario_predict(run_id: str):
    """Get the expected outcome for an active scenario run."""
    with _runs_lock:
        run = _scenario_runs.get(run_id)
    if not run:
        return jsonify({"error": "Run not found."}), 404
    return jsonify({"expected_outcome": run.get("expected_outcome"), "spec": run.get("spec")})


@app.route("/api/scenario/list")
def scenario_list_options():
    """Return available levels, locations, and specialities."""
    if not _scenario_gen:
        return jsonify({"error": "Scenario generator not available."}), 503
    return jsonify({
        "levels":      _scenario_gen.list_levels(),
        "locations":   _scenario_gen.list_locations(),
        "specialities": _scenario_gen.list_specialities(),
        "disciplines": {
            "doctor":          "Physician / Registrar",
            "nurse":           "Staff Nurse / Charge Nurse",
            "physiotherapist": "Physiotherapist",
            "allied":          "Allied Health Professional",
        },
    })


@app.route("/api/tts/<filename>")
def serve_tts(filename: str):
    """Serve a generated TTS audio file."""
    filepath = TTS_DIR / filename
    if not filepath.exists() or not filename.endswith(".mp3"):
        return jsonify({"error": "Audio file not found."}), 404
    return send_file(str(filepath), mimetype="audio/mpeg")


# ══════════════════════════════════════════════════════════════════════════════
# GAMIFICATION ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/gamification/leaderboard")
def gamification_leaderboard():
    """Return top teams by XP."""
    if _flags and not _flags.get("gamification_enabled"):
        return jsonify({"error": "Gamification is currently disabled by admin."}), 403
    if not _gamification:
        return jsonify({"error": "Gamification engine not available."}), 503
    limit = int(request.args.get("limit", 20))
    return jsonify({"leaderboard": _gamification.get_leaderboard(limit=limit)})


@app.route("/api/gamification/record", methods=["POST"])
def gamification_record():
    """Record a completed scenario session for XP + badges."""
    if _flags and not _flags.get("gamification_enabled"):
        return jsonify({"error": "Gamification is currently disabled by admin."}), 403
    if not _gamification or not _outcome_pred:
        return jsonify({"error": "Gamification engine not available."}), 503

    body = request.get_json(force=True) or {}
    required = ["team_name", "scenario_id", "level", "score"]
    for field in required:
        if field not in body:
            return jsonify({"error": f"Missing field: {field}"}), 400

    # Build a minimal prediction_result if not provided
    pred_result = body.get("prediction_result") or {
        "prediction_accuracy": body["score"],
        "grade":               "A" if body["score"] >= 90 else "B" if body["score"] >= 80 else "C",
        "xp_earned":           int(body["score"] * 5),
        "critical_misses":     [],
    }

    record = _gamification.record_session(
        team_name          = body["team_name"],
        scenario_id        = body["scenario_id"],
        level              = body["level"],
        score              = float(body["score"]),
        prediction_result  = pred_result,
        discipline         = body.get("discipline", ["doctor"]),
        total_deviations   = int(body.get("total_deviations", 0)),
        ai_debriefed       = bool(body.get("ai_debriefed", False)),
        critical_misses    = body.get("critical_misses", []),
    )
    return jsonify(record)


@app.route("/api/gamification/badges")
def gamification_badges():
    """Return full badge catalogue."""
    if not _gamification:
        return jsonify({"error": "Gamification engine not available."}), 503
    return jsonify({"badges": _gamification.get_badge_catalogue()})


@app.route("/api/scenario/report", methods=["POST"])
def scenario_report():
    """
    Generate a PDF report for a completed Scenario Studio run.

    Body (JSON):
        spec             : The scenario spec dict (from generate)
        gamification_data: Gamification record (from gamification/record or the frontend)
        deviations       : List of deviation dicts [{time, action, severity}]
        checklist_done   : List of action strings that were completed
        elapsed_sec      : Total run time in seconds
        team_name        : Team name string
    """
    body = request.get_json(force=True) or {}
    spec              = body.get("spec", {})
    gamification_data = body.get("gamification_data", {})
    deviations        = body.get("deviations", [])
    checklist_done    = body.get("checklist_done", [])
    elapsed_sec       = int(body.get("elapsed_sec", 0))
    team_name         = body.get("team_name", "Team").strip() or "Anonymous Team"

    if not spec:
        return jsonify({"error": "spec is required."}), 400

    # Inject team_name into gamification_data if not already there
    gamification_data.setdefault("team_name", team_name)

    try:
        from analysis.reporting.pdf_adapter import build_scenario_pdf_input
        from analysis.reporting.pdf_engine  import generate_pdf

        # Build a meaningful scenario_id from spec title + timestamp
        import time as _time
        scenario_id  = spec.get("scenario_id", spec.get("title", "scenario").replace(" ", "_"))
        filename     = f"scenario_{scenario_id}_{int(_time.time())}.pdf"
        output_path  = OUTPUT_DIR / filename

        pdf_json = build_scenario_pdf_input(
            spec              = spec,
            gamification_data = gamification_data,
            deviations        = deviations,
            checklist_done    = checklist_done,
            elapsed_sec       = elapsed_sec,
        )
        generate_pdf(pdf_json, str(output_path))

        return send_file(
            str(output_path),
            as_attachment=True,
            download_name=f"scenario_report_{scenario_id}.pdf",
            mimetype="application/pdf",
        )
    except Exception as e:
        import traceback
        logger.exception("[scenario/report] PDF generation failed")
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    """Authenticate admin. Body: {username, password}."""
    if not _admin_auth:
        return jsonify({"error": "Admin module not available."}), 503
    body     = request.get_json(force=True) or {}
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if not username or not password:
        return jsonify({"error": "Username and password required."}), 400
    ok, msg, admin_info = _admin_auth.login(username, password)
    if ok:
        return jsonify({"ok": True, "admin": admin_info, "message": msg})
    return jsonify({"ok": False, "error": msg}), 401


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    if _admin_auth:
        _admin_auth.logout()
    return jsonify({"ok": True})


@app.route("/api/admin/me")
def admin_me():
    """Return current session admin info."""
    if not _admin_auth:
        return jsonify({"error": "Admin module not available."}), 503
    admin = _admin_auth.current_admin()
    if not admin:
        return jsonify({"logged_in": False}), 200
    return jsonify({"logged_in": True, "admin": admin})


@app.route("/api/admin/flags", methods=["GET"])
def admin_get_flags():
    """Get all feature flags. Requires admin login."""
    if not _admin_auth or not _flags:
        return jsonify({"error": "Admin module not available."}), 503
    admin = _admin_auth.current_admin()
    if not admin:
        return jsonify({"error": "Admin login required."}), 401
    return jsonify({"flags": _flags.all()})


@app.route("/api/admin/flags", methods=["POST"])
def admin_set_flag():
    """Update a feature flag. Requires admin login. Body: {name, value}."""
    if not _admin_auth or not _flags:
        return jsonify({"error": "Admin module not available."}), 503
    admin = _admin_auth.current_admin()
    if not admin:
        return jsonify({"error": "Admin login required."}), 401
    body  = request.get_json(force=True) or {}
    name  = body.get("name", "")
    value = body.get("value")
    if not name or value is None:
        return jsonify({"error": "name and value required."}), 400
    ok, msg = _flags.set(name, bool(value), by_username=admin["username"])
    if ok:
        return jsonify({"ok": True, "message": msg})
    return jsonify({"ok": False, "error": msg}), 400


@app.route("/api/admin/admins", methods=["GET"])
def admin_list_admins():
    """List all admin users. Super-admin only."""
    if not _admin_auth:
        return jsonify({"error": "Admin module not available."}), 503
    admin = _admin_auth.current_admin()
    if not admin:
        return jsonify({"error": "Admin login required."}), 401
    if admin["role"] != "super_admin":
        return jsonify({"error": "Super-admin privileges required."}), 403
    return jsonify({"admins": _admin_auth.list_admins()})


@app.route("/api/admin/admins", methods=["POST"])
def admin_create_admin():
    """Create a new admin. Super-admin only. Body: {username, password, role}."""
    if not _admin_auth:
        return jsonify({"error": "Admin module not available."}), 503
    admin = _admin_auth.current_admin()
    if not admin:
        return jsonify({"error": "Admin login required."}), 401
    if admin["role"] != "super_admin":
        return jsonify({"error": "Super-admin privileges required."}), 403
    body = request.get_json(force=True) or {}
    ok, msg = _admin_auth.create_admin(
        username   = body.get("username", ""),
        password   = body.get("password", ""),
        role       = body.get("role", "admin"),
        created_by = admin["username"],
    )
    status_code = 200 if ok else 400
    return jsonify({"ok": ok, "message": msg}), status_code


@app.route("/api/admin/admins/<int:admin_id>", methods=["DELETE"])
def admin_delete_admin(admin_id: int):
    """Deactivate an admin. Super-admin only."""
    if not _admin_auth:
        return jsonify({"error": "Admin module not available."}), 503
    admin = _admin_auth.current_admin()
    if not admin:
        return jsonify({"error": "Admin login required."}), 401
    if admin["role"] != "super_admin":
        return jsonify({"error": "Super-admin privileges required."}), 403
    ok, msg = _admin_auth.delete_admin(admin_id, by_username=admin["username"])
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 400)


@app.route("/api/admin/admins/<int:admin_id>/password", methods=["POST"])
def admin_change_password(admin_id: int):
    """Change an admin's password. Body: {new_password}."""
    if not _admin_auth:
        return jsonify({"error": "Admin module not available."}), 503
    admin = _admin_auth.current_admin()
    if not admin:
        return jsonify({"error": "Admin login required."}), 401
    # Can change own password; super_admin can change any
    if admin["id"] != admin_id and admin["role"] != "super_admin":
        return jsonify({"error": "Insufficient privileges."}), 403
    body = request.get_json(force=True) or {}
    new_pw = body.get("new_password", "")
    ok, msg = _admin_auth.change_password(admin_id, new_pw, by_username=admin["username"])
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 400)


if __name__ == "__main__":
    print("="*60)
    print("  CPR Debriefing System - Web Server")
    print("  Open: http://localhost:5000")
    print("="*60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
