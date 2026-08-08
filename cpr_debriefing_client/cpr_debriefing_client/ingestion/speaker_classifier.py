"""
ingestion/speaker_classifier.py
================================
Standalone speaker diarization tool for the CPR debriefing system.

Runs pyannote.audio on a WAV/MP3/MP4 file and prints a timestamped
speaker turn list.  Designed to be used as a quick sanity check
*before* the full pipeline runs, or independently to inspect a recording.

CLI usage:
    python -m ingestion.speaker_classifier audio.wav
    python -m ingestion.speaker_classifier audio.wav --num-speakers 5
    python -m ingestion.speaker_classifier audio.wav --output-json turns.json

Programmatic usage:
    from ingestion.speaker_classifier import classify_speakers
    turns = classify_speakers("audio.wav", num_speakers=5)
    # turns → [{"speaker": "SPEAKER_00", "start_ms": 0, "end_ms": 12300}, ...]

Requirements:
    - pyannote.audio installed  (pip install pyannote.audio)
    - HF_TOKEN set in environment / .env
    - torch with CUDA support recommended (CPU fallback available)

Author: Deva
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

PYANNOTE_MODEL = "pyannote/speaker-diarization-3.1"
DEFAULT_MIN_SPEAKERS = 2
DEFAULT_MAX_SPEAKERS = 6

# ANSI colours for terminal output (disabled on non-TTY)
_COLOURS = [
    "\033[96m",  # cyan       — SPEAKER_00
    "\033[93m",  # yellow     — SPEAKER_01
    "\033[92m",  # green      — SPEAKER_02
    "\033[95m",  # magenta    — SPEAKER_03
    "\033[94m",  # blue       — SPEAKER_04
    "\033[91m",  # red        — SPEAKER_05
]
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


# ─────────────────────────────────────────────────────────────────────────────
# Device detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_device() -> str:
    """
    Return 'cuda' if PyTorch + CUDA are available, else 'cpu'.
    Safe to call even if torch is not installed.
    """
    try:
        import torch
        if torch.cuda.is_available():
            name   = torch.cuda.get_device_name(0)
            vram   = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"GPU detected: {name} ({vram:.1f} GB VRAM) — using CUDA")
            return "cuda"
        else:
            logger.info("CUDA not available — using CPU")
            return "cpu"
    except ModuleNotFoundError:
        logger.warning("torch not installed — running on CPU")
        return "cpu"


# ─────────────────────────────────────────────────────────────────────────────
# Audio preprocessing (mono 16 kHz WAV)
# ─────────────────────────────────────────────────────────────────────────────

def _preprocess_audio(audio_path: str) -> str:
    """
    Convert any audio format to mono 16 kHz WAV.
    Returns path to the preprocessed file. Skips if already exists.

    Strategy:
      - Plain .wav  → pydub (no ffmpeg needed)
      - Everything else (.m4a, .mp4, .mp3 …) → PyAV (FFmpeg compiled in)
    """
    path        = Path(audio_path)
    output_path = path.parent / f"{path.stem}_sc_preprocessed.wav"

    if output_path.exists():
        logger.debug(f"Using cached preprocessed file: {output_path}")
        return str(output_path)

    logger.info(f"Preprocessing audio → mono 16 kHz WAV: {path.name}")

    if path.suffix.lower() == ".wav":
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(str(path))
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            audio.export(str(output_path), format="wav")
        except Exception as e:
            logger.warning(f"pydub WAV read failed ({e}) — falling back to PyAV")
            _av_decode(str(path), str(output_path))
    else:
        _av_decode(str(path), str(output_path))

    logger.info(f"Preprocessed saved: {output_path}")
    return str(output_path)


def _av_decode(audio_path: str, output_path: str) -> None:
    """
    Decode any FFmpeg-supported audio file to mono 16kHz 16-bit WAV.
    Uses PyAV which ships with FFmpeg compiled in — no system ffmpeg needed.
    """
    import wave
    try:
        import av as _av
    except ImportError:
        raise ImportError("PyAV required: pip install av")

    logger.info(f"PyAV decoding: {Path(audio_path).name}")
    container = _av.open(audio_path)
    resampler = _av.AudioResampler(format="s16", layout="mono", rate=16000)

    pcm_chunks: list[bytes] = []

    def _collect(result) -> None:
        if result is None:
            return
        frames = result if isinstance(result, list) else [result]
        for f in frames:
            pcm_chunks.append(bytes(f.planes[0]))

    for frame in container.decode(audio=0):
        _collect(resampler.resample(frame))
    _collect(resampler.resample(None))
    container.close()

    if not pcm_chunks:
        raise ValueError(f"PyAV produced no audio from: {audio_path}")

    raw_pcm = b"".join(pcm_chunks)
    n_sec   = len(raw_pcm) / (2 * 16000)
    logger.info(f"Decoded {n_sec:.1f}s via PyAV")

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(raw_pcm)



# ─────────────────────────────────────────────────────────────────────────────
# Core diarization
# ─────────────────────────────────────────────────────────────────────────────

def classify_speakers(
    audio_path:   str,
    num_speakers: Optional[int] = None,
    min_speakers: int = DEFAULT_MIN_SPEAKERS,
    max_speakers: int = DEFAULT_MAX_SPEAKERS,
    preprocess:   bool = True,
) -> list[dict]:
    """
    Run pyannote diarization on an audio file and return speaker turns.

    Args:
        audio_path:   Path to WAV / MP3 / MP4 file.
        num_speakers: Exact number of speakers (if known). Overrides min/max.
        min_speakers: Minimum speaker count hint (used if num_speakers is None).
        max_speakers: Maximum speaker count hint (used if num_speakers is None).
        preprocess:   If True, convert audio to mono 16 kHz before diarizing.

    Returns:
        List of dicts:
            [
                {
                    "speaker":  "SPEAKER_00",
                    "start_ms": 0,
                    "end_ms":   12300,
                    "duration_s": 12.3,
                },
                ...
            ]
        Sorted by start_ms.

    Raises:
        ImportError:     pyannote.audio is not installed.
        EnvironmentError: HF_TOKEN not set in environment.
        FileNotFoundError: audio_path does not exist.
    """
    # ── Pre-flight checks ──────────────────────────────────────────────────
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        raise ImportError(
            "pyannote.audio is required for speaker classification.\n"
            "Install with: pip install pyannote.audio"
        )

    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        raise EnvironmentError(
            "HF_TOKEN environment variable is not set.\n"
            "Set it in your .env file or export HF_TOKEN=<your_token>.\n"
            "Get a free token at: https://huggingface.co/settings/tokens"
        )

    audio_path = str(Path(audio_path).resolve())
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # ── Preprocessing ──────────────────────────────────────────────────────
    if preprocess:
        audio_path = _preprocess_audio(audio_path)

    # ── Device selection ───────────────────────────────────────────────────
    device = _detect_device()

    # ── Load pyannote pipeline ─────────────────────────────────────────────
    logger.info(f"Loading pyannote pipeline: {PYANNOTE_MODEL}")
    pipeline = Pipeline.from_pretrained(
        PYANNOTE_MODEL,
        token=hf_token,   # pyannote 3.x — NOT use_auth_token
    )
    try:
        import torch
        pipeline.to(torch.device(device))
        logger.info(f"pyannote pipeline moved to {device}")
    except Exception as e:
        logger.warning(f"Could not move pipeline to {device}: {e}")

    # ── Build kwargs ───────────────────────────────────────────────────────
    kwargs: dict = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
        logger.info(f"Using fixed speaker count: {num_speakers}")
    else:
        kwargs["min_speakers"] = min_speakers
        kwargs["max_speakers"] = max_speakers
        logger.info(f"Speaker count: auto-detect [{min_speakers}–{max_speakers}]")

    # ── Run diarization ────────────────────────────────────────────────────
    logger.info(f"Running diarization on: {Path(audio_path).name}")
    diarization = pipeline(audio_path, **kwargs)

    # ── Parse turns ────────────────────────────────────────────────────────
    turns = []
    for segment, _, speaker in diarization.itertracks(yield_label=True):
        start_ms   = int(segment.start * 1000)
        end_ms     = int(segment.end   * 1000)
        duration_s = (end_ms - start_ms) / 1000
        turns.append({
            "speaker":    speaker,
            "start_ms":   start_ms,
            "end_ms":     end_ms,
            "duration_s": round(duration_s, 2),
        })

    turns.sort(key=lambda t: t["start_ms"])
    logger.info(f"Diarization complete — {len(turns)} turns detected")
    return turns


# ─────────────────────────────────────────────────────────────────────────────
# Pretty-print summary
# ─────────────────────────────────────────────────────────────────────────────

def _ms_to_mmss(ms: int) -> str:
    total_s = ms // 1000
    return f"{total_s // 60:02d}:{total_s % 60:02d}"


def print_speaker_summary(turns: list[dict], use_colour: bool = True) -> None:
    """Print a formatted, colour-coded speaker turn summary to stdout."""
    if not turns:
        print("No speaker turns detected.")
        return

    use_colour = use_colour and sys.stdout.isatty()

    # Build speaker → colour index
    unique_speakers = sorted(set(t["speaker"] for t in turns))
    colour_map = {
        spk: _COLOURS[i % len(_COLOURS)]
        for i, spk in enumerate(unique_speakers)
    }

    # Header
    sep = "─" * 60
    print(f"\n{_BOLD if use_colour else ''}{'SPEAKER DIARIZATION RESULTS'}{_RESET if use_colour else ''}")
    print(sep)
    print(f"  {'Speaker':<14} {'Start':>6}  {'End':>6}  {'Duration':>8}")
    print(sep)

    for turn in turns:
        spk  = turn["speaker"]
        col  = colour_map.get(spk, "") if use_colour else ""
        rst  = _RESET if use_colour else ""
        bold = _BOLD  if use_colour else ""
        print(
            f"  {col}{bold}{spk:<14}{rst}"
            f"  {_ms_to_mmss(turn['start_ms']):>6}"
            f"  {_ms_to_mmss(turn['end_ms']):>6}"
            f"  {turn['duration_s']:>7.1f}s"
        )

    print(sep)

    # Per-speaker totals
    print(f"\n{_BOLD if use_colour else ''}SPEAKER TOTALS:{_RESET if use_colour else ''}")
    totals: dict[str, float] = {}
    for t in turns:
        totals[t["speaker"]] = totals.get(t["speaker"], 0) + t["duration_s"]
    for spk in unique_speakers:
        col = colour_map.get(spk, "") if use_colour else ""
        rst = _RESET if use_colour else ""
        print(f"  {col}{spk}{rst}  →  {totals[spk]:.1f}s total speaking time")

    print(f"\n  Total speakers detected: {len(unique_speakers)}")
    print(f"  Total turns:             {len(turns)}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Speaker diarization tool — classify voices in a CPR session audio file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ingestion.speaker_classifier session.wav
  python -m ingestion.speaker_classifier session.wav --num-speakers 5
  python -m ingestion.speaker_classifier session.wav --output-json turns.json
        """,
    )
    parser.add_argument(
        "audio",
        help="Path to audio file (WAV / MP3 / MP4)",
    )
    parser.add_argument(
        "--num-speakers", type=int, default=None,
        help="Exact number of speakers (optional — auto-detect if not set)",
    )
    parser.add_argument(
        "--min-speakers", type=int, default=DEFAULT_MIN_SPEAKERS,
        help=f"Minimum number of speakers for auto-detection (default: {DEFAULT_MIN_SPEAKERS})",
    )
    parser.add_argument(
        "--max-speakers", type=int, default=DEFAULT_MAX_SPEAKERS,
        help=f"Maximum number of speakers for auto-detection (default: {DEFAULT_MAX_SPEAKERS})",
    )
    parser.add_argument(
        "--output-json", default=None,
        help="Optional path to save turns as JSON (e.g. turns.json)",
    )
    parser.add_argument(
        "--no-preprocess", action="store_true",
        help="Skip audio preprocessing (use if audio is already mono 16 kHz WAV)",
    )
    parser.add_argument(
        "--no-colour", action="store_true",
        help="Disable ANSI colour output",
    )
    args = parser.parse_args()

    try:
        turns = classify_speakers(
            audio_path=args.audio,
            num_speakers=args.num_speakers,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
            preprocess=not args.no_preprocess,
        )
    except (ImportError, EnvironmentError, FileNotFoundError) as e:
        print(f"\n[ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)

    print_speaker_summary(turns, use_colour=not args.no_colour)

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(turns, f, indent=2)
        print(f"  Turns saved to: {out_path}")


if __name__ == "__main__":
    main()
