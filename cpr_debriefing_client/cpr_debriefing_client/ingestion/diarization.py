"""
ingestion/diarization.py — Speaker Diarization + Role Attribution
==================================================================
Two operating modes, selected automatically at runtime:

  Mode A — Keyword-only (default, no HuggingFace token required):
    Skips acoustic speaker separation entirely.
    Calls RoleAssigner.assign_per_segment() on the Whisper transcript.
    speaker_label field is set to "keyword_assigned".
    Sufficient for structured dialogue; works on any hardware.

  Mode B — Full pyannote (requires HF_TOKEN in environment):
    Runs pyannote.audio Pipeline on the audio file.
    Aligns pyannote speaker turns with Whisper segments by timestamp overlap.
    Calls RoleAssigner.assign() with real speaker labels (SPEAKER_00 etc.).
    Activates automatically when pyannote is installed and HF_TOKEN is set.

Public interface (unchanged from original stub):
    attribute_roles(segments, mode="structured")
    attribute_roles_audio(whisper_segments, audio_path, lapel_timestamps, num_speakers)

Author: Deva
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from data.schemas.event_schema import ActorRole, SourceSystem
from ingestion.role_assigner import RoleAssigner

logger = logging.getLogger(__name__)

# =============================================================================
# Pyannote availability guard
# =============================================================================

try:
    from pyannote.audio import Pipeline as _PyannotePipeline
    PYANNOTE_AVAILABLE = True
    logger.debug("pyannote.audio found — Mode B available")
except ImportError:
    PYANNOTE_AVAILABLE = False
    logger.debug("pyannote.audio not installed — running in keyword-only mode (Mode A)")


def _get_diarization_device() -> str:
    """
    Detect the best available device for pyannote.

    On Windows, pyannote's PyTorch cuDNN conflicts with CTranslate2's
    bundled CUDA runtime (cudnnGetLibConfig symbol mismatch → Error 127).
    Forcing CPU avoids the crash; pyannote on CPU is ~3-4 min for 15-min audio.
    GPU is used only on Linux/macOS where the runtimes coexist cleanly.
    """
    import platform
    if platform.system() == "Windows":
        logger.info("pyannote: running on CPU (Windows cuDNN/CTranslate2 conflict avoided)")
        return "cpu"

    try:
        import torch
        if torch.cuda.is_available():
            logger.info(
                f"pyannote will run on GPU: {torch.cuda.get_device_name(0)} "
                f"({torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB VRAM)"
            )
            return "cuda"
    except ModuleNotFoundError:
        pass
    logger.info("pyannote will run on CPU")
    return "cpu"

# Minimum fractional overlap for a Whisper segment to be claimed by a speaker turn
_MIN_OVERLAP_FRACTION = 0.30

# Maps role strings to canonical ActorRole enum values
ROLE_MAPPING = {
    "team_leader":             ActorRole.TEAM_LEADER,
    "Team Leader":             ActorRole.TEAM_LEADER,
    "compressor":              ActorRole.COMPRESSOR,
    "Compressor":              ActorRole.COMPRESSOR,
    "airway":                  ActorRole.AIRWAY,
    "Airway":                  ActorRole.AIRWAY,
    "iv_member":               ActorRole.MEDICATION,
    "IV Member":               ActorRole.MEDICATION,
    "defib_coach":             ActorRole.UNKNOWN,
    "Defibrillator/CPR Coach": ActorRole.UNKNOWN,
    "recorder":                ActorRole.RECORDER,
    "Recorder":                ActorRole.RECORDER,
    "team":                    ActorRole.UNKNOWN,
    "Team":                    ActorRole.UNKNOWN,
}


# =============================================================================
# Structured mode (unchanged from original — JSON input path)
# =============================================================================

def attribute_roles_structured(segments: list[dict]) -> list[dict]:
    """
    Mode 1: Role is already labeled in each segment (structured JSON input).
    Maps the string role to the canonical ActorRole enum.
    Returns the same list with 'actor_role' field added.
    """
    attributed = []
    for seg in segments:
        speaker = seg.get("speaker", seg.get("role", "unknown"))
        role = ROLE_MAPPING.get(speaker, ActorRole.UNKNOWN)
        attributed.append({
            **seg,
            "actor_role": role,
            "source": (
                SourceSystem.LAPEL_AUDIO
                if role == ActorRole.TEAM_LEADER
                else SourceSystem.CEILING_AUDIO
            ),
        })
    logger.info(f"Structured role attribution complete — {len(attributed)} segments")
    return attributed


# =============================================================================
# Audio mode — auto-selects Mode A or Mode B
# =============================================================================

def attribute_roles_audio(
    whisper_segments: list[dict],
    audio_path: Optional[str] = None,
    lapel_timestamps: Optional[list[dict]] = None,
    num_speakers: Optional[int] = None,
) -> list[dict]:
    """
    Infer roles from audio transcript.

    Selects Mode A or Mode B automatically:
      Mode B: PYANNOTE_AVAILABLE AND HF_TOKEN env var set AND audio_path provided
      Mode A: everything else (keyword-only, no acoustic separation)

    Args:
        whisper_segments: Segment dicts from WhisperPipeline.to_event_dicts().
                          Must have: timestamp_ms, end_ms, text.
        audio_path:       Path to room audio WAV file (required for Mode B only).
        lapel_timestamps: Optional lapel segment dicts for team-leader boost.
        num_speakers:     Hint for pyannote (4–6 typical); None = auto-detect.

    Returns:
        Same list with "role", "speaker", "speaker_label", "actor_role",
        and "source" fields added to each segment.
    """
    if not whisper_segments:
        logger.warning("attribute_roles_audio() called with empty segments list")
        return []

    use_pyannote = (
        PYANNOTE_AVAILABLE
        and bool(os.getenv("HF_TOKEN"))
        and audio_path is not None
    )

    if use_pyannote:
        logger.info("Mode B — pyannote speaker diarization active")
        return _mode_b_pyannote(
            whisper_segments, audio_path, lapel_timestamps, num_speakers
        )
    else:
        reason = (
            "pyannote not installed" if not PYANNOTE_AVAILABLE
            else "HF_TOKEN not set" if not os.getenv("HF_TOKEN")
            else "audio_path not provided"
        )
        logger.info(f"Mode A — keyword-only fallback ({reason})")
        return _mode_a_keyword_only(whisper_segments, lapel_timestamps)


# =============================================================================
# Mode A — keyword-only (active path — no HF token needed)
# =============================================================================

def _mode_a_keyword_only(
    whisper_segments: list[dict],
    lapel_timestamps: Optional[list[dict]],
) -> list[dict]:
    """
    Assign roles per-segment using keyword voting alone.
    No acoustic speaker separation required.
    """
    assigner = RoleAssigner()
    normalised = _normalise_segments(whisper_segments, source_label="keyword_assigned")
    attributed = assigner.assign_per_segment(normalised)

    result = []
    for seg in attributed:
        result.append({
            **seg,
            "actor_role": ROLE_MAPPING.get(seg["role"], ActorRole.UNKNOWN),
            "source": SourceSystem.CEILING_AUDIO,
        })
    return result


# =============================================================================
# Mode B — full pyannote (future path — requires HF_TOKEN)
# =============================================================================

def _mode_b_pyannote(
    whisper_segments: list[dict],
    audio_path: str,
    lapel_timestamps: Optional[list[dict]],
    num_speakers: Optional[int],
) -> list[dict]:
    """
    Full pyannote diarization → Whisper alignment → RoleAssigner.assign().
    Only called when PYANNOTE_AVAILABLE and HF_TOKEN are both confirmed.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(
            f"Audio file not found for diarization: {audio_path}\n"
            "Ensure the file has been preprocessed by WhisperPipeline._preprocess()."
        )

    # ── Audio format for pyannote ─────────────────────────────────────────────
    # soundfile (pyannote's audio backend) only reads WAV/FLAC/OGG — not .m4a.
    # WhisperPipeline._preprocess() already created a mono-16kHz WAV alongside
    # the original; use that. Derive the path from the audio_path stem.
    from pathlib import Path as _Path
    p = _Path(audio_path)
    wav_candidate = p.parent / (p.stem + "_preprocessed.wav")
    if wav_candidate.exists():
        audio_for_pyannote = str(wav_candidate)
        logger.info(f"pyannote using preprocessed WAV: {wav_candidate.name}")
    elif audio_path.lower().endswith(".wav"):
        audio_for_pyannote = audio_path
    else:
        # Fallback: convert inline with av (fast, no ffmpeg dependency)
        import av as _av, numpy as _np, wave as _wave, tempfile as _tmp
        logger.info("pyannote: converting audio to WAV on-the-fly (av fallback)")
        tmp = _tmp.NamedTemporaryFile(suffix=".wav", delete=False)
        with _av.open(audio_path) as src:
            stream = src.streams.audio[0]
            sr = stream.codec_context.sample_rate
            frames = b"".join(
                bytes(frame.to_ndarray().tobytes())
                for frame in src.decode(audio=0)
            )
        with _wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(frames)
        audio_for_pyannote = tmp.name

    hf_token = os.getenv("HF_TOKEN", "")
    num_sp   = str(num_speakers) if num_speakers is not None else ""
    backend  = os.getenv("DIARIZATION_BACKEND", "hybrid").lower()  # "hybrid" | "pyannote"

    # ── Step 1 — Run diarization in a SEPARATE SUBPROCESS (GPU-safe on Windows) ─
    # PyTorch CUDA and CTranslate2's bundled CUDA conflict in the same process
    # (cudnnGetLibConfig symbol clash). A subprocess has its own DLL namespace.
    # "hybrid"  → diarize_worker_hybrid.py  (pyannote seg + Resemblyzer GE2E)
    # "pyannote" → diarize_worker.py         (pure pyannote pipeline)
    import subprocess, sys as _sys, json as _json
    from pathlib import Path as _Path

    if backend == "hybrid":
        worker = _Path(__file__).parent / "diarize_worker_hybrid.py"
        logger.info(f"Running HYBRID diarization (pyannote seg + Resemblyzer): {audio_for_pyannote}")
    else:
        worker = _Path(__file__).parent / "diarize_worker.py"
        logger.info(f"Running pyannote diarization subprocess: {audio_for_pyannote}")

    cmd = [_sys.executable, str(worker), audio_for_pyannote, hf_token]
    if num_sp:
        cmd.append(num_sp)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,   # 30 min ceiling — safe for any session length
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "diarize_worker exited non-zero")
        turns: list[dict] = _json.loads(result.stdout.strip())
    except Exception as exc:
        logger.warning(
            f"pyannote subprocess failed ({exc}), falling back to in-process CPU"
        )
        # ── CPU fallback (in-process, slower but always works) ────────────────
        device = "cpu"
        pipeline = _PyannotePipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )
        pyannote_kwargs: dict = {}
        if num_speakers is not None:
            pyannote_kwargs["num_speakers"] = num_speakers
        else:
            pyannote_kwargs["min_speakers"] = 2
            pyannote_kwargs["max_speakers"] = 6
        diarization = pipeline(audio_for_pyannote, **pyannote_kwargs)
        turns = [
            {
                "speaker":  spk,
                "start_ms": int(turn.start * 1000),
                "end_ms":   int(turn.end   * 1000),
            }
            for turn, _, spk in diarization.itertracks(yield_label=True)
        ]

    unique_speakers = set(t["speaker"] for t in turns)
    logger.info(
        f"pyannote detected {len(unique_speakers)} speaker(s): "
        f"{', '.join(sorted(unique_speakers))} | {len(turns)} turns total"
    )

    # Step 3 — Align Whisper segments with speaker turns
    normalised = _normalise_segments(whisper_segments, source_label=None)
    aligned = _align_segments_to_turns(normalised, turns)

    # Step 4 — Keyword voting with speaker labels
    assigner = RoleAssigner()
    role_map = assigner.assign(aligned, lapel_timestamps=lapel_timestamps)
    attributed = assigner.apply_role_map(aligned, role_map)

    # Step 5 — Add actor_role enum and source
    result = []
    for seg in attributed:
        result.append({
            **seg,
            "actor_role": ROLE_MAPPING.get(seg["role"], ActorRole.UNKNOWN),
            "source": SourceSystem.CEILING_AUDIO,
        })

    logger.info(f"Mode B attribution complete — {len(result)} segments")
    return result


def _align_segments_to_turns(
    segments: list[dict],
    turns: list[dict],
) -> list[dict]:
    """
    For each Whisper segment, find the pyannote turn with maximum temporal overlap.
    If overlap < _MIN_OVERLAP_FRACTION of segment duration → label UNKNOWN.

    Turns are assumed sorted by start_ms (pyannote always returns them in order).
    Uses early-exit once turns are past the segment's end for O(n+m) performance.
    """
    result = []
    n_turns = len(turns)

    for seg in segments:
        seg_start    = seg.get("timestamp_ms", 0)
        seg_end      = seg.get("end_ms", seg_start)
        seg_duration = max(1, seg_end - seg_start)

        best_speaker = "UNKNOWN"
        best_overlap = 0

        for turn in turns:
            # Early-exit: turns are sorted; once a turn starts after seg ends, stop
            if turn["start_ms"] >= seg_end:
                break
            # Skip turns that end before the segment starts
            if turn["end_ms"] <= seg_start:
                continue

            overlap = min(seg_end, turn["end_ms"]) - max(seg_start, turn["start_ms"])
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn["speaker"]

        if best_overlap / seg_duration < _MIN_OVERLAP_FRACTION:
            best_speaker = "UNKNOWN"

        result.append({**seg, "speaker_label": best_speaker})
    return result


# =============================================================================
# Shared helpers
# =============================================================================

def _normalise_segments(
    segments: list[dict],
    source_label: Optional[str],
) -> list[dict]:
    """
    Ensure every segment has the keys downstream code expects.
    Fills in missing timestamp/end_ms/speaker_label safely.
    """
    result = []
    for seg in segments:
        start = seg.get("timestamp_ms", seg.get("start_ms", 0))
        end = seg.get("end_ms", start + 1000)   # 1-second fallback
        result.append({
            **seg,
            "timestamp_ms": start,
            "end_ms": end,
            "speaker_label": (
                seg.get("speaker_label") or source_label or "UNKNOWN"
            ),
        })
    return result


# =============================================================================
# Unified public entry point (original interface preserved exactly)
# =============================================================================

def attribute_roles(
    segments: list[dict],
    mode: str = "structured",
) -> list[dict]:
    """
    Main entry point. Preserves the original public interface exactly.

    mode: 'structured' — role already labeled in segment JSON (scenario data)
          'audio'      — infer from audio / keyword voting (Whisper output)
    """
    if mode == "structured":
        return attribute_roles_structured(segments)
    elif mode == "audio":
        return attribute_roles_audio(segments)
    else:
        raise ValueError(
            f"Unknown diarization mode: '{mode}'. Use 'structured' or 'audio'."
        )
