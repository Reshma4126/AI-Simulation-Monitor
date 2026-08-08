"""
ingestion/audio_pipeline.py — Audio Ingestion Entry Point
==========================================================
Single public entry point for the audio path.

Orchestrates:
  1. Audio preprocessing  (via WhisperPipeline._preprocess)
  2. Language detection   (Whisper on first 30 s)
  3. Transcription        (Whisper, with translate mode for Tamil/Tanglish)
  4. Role attribution     (diarization.attribute_roles_audio)
  5. Output formatting    (list[dict] identical to structured JSON mode)

Output format is identical to what EventExtractor already consumes from
structured scenario JSON — no downstream changes required.

Usage:
    from ingestion.audio_pipeline import AudioPipeline

    ap = AudioPipeline()
    segments = ap.process("session.wav")
    segments = ap.process("ceiling.wav", lapel_path="lapel.wav")

    # Each segment dict:
    {
        "timestamp_ms":  int,
        "time":          "MM:SS",
        "speaker":       "Team Leader",
        "role":          "team_leader",
        "text":          "Start CPR.",     # always English
        "confidence":    0.87,
        "source":        "room" | "lapel",
        "speaker_label": "SPEAKER_00" | "keyword_assigned",
        "was_translated": bool,
        "segment_id":    str,
    }

Author: Deva
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Availability flag — set at import time, no hardware needed
# =============================================================================

try:
    from faster_whisper import WhisperModel as _WhisperModel  # noqa: F401
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning(
        "faster-whisper not installed. "
        "AudioPipeline.process() will raise if called. "
        "Install with: pip install faster-whisper"
    )


# =============================================================================
# Constants
# =============================================================================

_TAMIL_LANGUAGE_CODES    = {"ta", "tam"}
_LANG_DETECT_DURATION_S  = 30          # seconds used for language pre-pass
_DEFAULT_MODEL           = "medium"    # GPU: ~1.4 GB VRAM int8; best Tamil/Tanglish accuracy
_DEFAULT_DEVICE          = "cuda"      # GPU-first; WhisperPipeline handles fallback to cpu
_DEFAULT_COMPUTE         = "int8"


# =============================================================================
# AudioPipeline
# =============================================================================

class AudioPipeline:
    """
    Orchestrates audio → attributed English transcript.

    Args:
        whisper_model: Whisper model size. Default "medium" (~1.4 GB VRAM int8 on GPU).
                       Upgrade to "large-v2" for maximum accuracy (~2.9 GB VRAM).
        device:        "cuda" (GPU-first, auto-falls to cpu) or "cpu".
        compute_type:  "int8" (memory-efficient, works on both CPU and GPU).
        num_speakers:  Hint for pyannote when Mode B is active (4–6 typical).
                       None = auto-detect.
    """

    def __init__(
        self,
        whisper_model: str = _DEFAULT_MODEL,
        device: str = _DEFAULT_DEVICE,
        compute_type: str = _DEFAULT_COMPUTE,
        num_speakers: Optional[int] = None,
    ):
        if not WHISPER_AVAILABLE:
            raise ImportError(
                "faster-whisper is required for AudioPipeline. "
                "Install with: pip install faster-whisper"
            )

        logger.info(
            f"Initialising AudioPipeline — model={whisper_model}, "
            f"device={device}, compute_type={compute_type}"
        )

        # Lazy import so module can be imported without GPU loaded
        from ingestion.whisper_pipeline import WhisperPipeline
        self._whisper = WhisperPipeline(
            model_size=whisper_model,
            device=device,
            compute_type=compute_type,
        )
        self._num_speakers = num_speakers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        audio_path:    str,
        lapel_path:    Optional[str] = None,
        session_id:    str = "UNKNOWN",
        language_mode: Optional[str] = None,
    ) -> list[dict]:
        """
        Full pipeline: audio file(s) → attributed English transcript.

        Args:
            audio_path:    Path to room/ceiling mic audio (WAV/MP3/MP4).
            lapel_path:    Optional path to lapel mic audio.
                           Used for team-leader identification boost.
            session_id:    Session identifier — stored in each output segment.
            language_mode: User-specified language: 'english' | 'tamil' | 'tanglish' | None.
                           When set, skips 30-second auto-detection entirely.
                           None = auto-detect (slower, less reliable for Tanglish).

        Returns:
            list[dict] ready for EventExtractor — same format as structured JSON.
        """
        audio_path = str(Path(audio_path).resolve())
        logger.info(
            f"AudioPipeline.process() — session={session_id}, "
            f"audio={audio_path}, language_mode={language_mode!r}"
        )

        # ── Step 1: Transcribe room audio ──────────────────────────────
        room_result, was_translated = self._transcribe_with_language_detection(
            audio_path, source="room", language_mode=language_mode
        )
        room_segments = room_result.to_event_dicts()

        if not room_segments:
            logger.warning("Whisper produced no segments from room audio")
            return []

        # ── Step 2: Transcribe lapel (optional) ────────────────────────
        lapel_timestamps: Optional[list[dict]] = None
        if lapel_path:
            lapel_path = str(Path(lapel_path).resolve())
            logger.info(f"Transcribing lapel mic: {lapel_path}")
            lapel_result, _ = self._transcribe_with_language_detection(
                lapel_path, source="lapel", language_mode=language_mode
            )
            lapel_timestamps = lapel_result.to_event_dicts()
            logger.info(f"Lapel: {len(lapel_timestamps)} segments")

        # ── Step 3: Role attribution (Mode A keyword-only or Mode B pyannote)
        from ingestion.diarization import attribute_roles_audio
        attributed = attribute_roles_audio(
            whisper_segments=room_segments,
            audio_path=audio_path,
            lapel_timestamps=lapel_timestamps,
            num_speakers=self._num_speakers,
        )

        # ── Step 4: Format output ──────────────────────────────────────
        output = self._format_output(attributed, session_id, was_translated)

        logger.info(
            f"AudioPipeline complete — {len(output)} segments, "
            f"was_translated={was_translated}, session={session_id}"
        )
        return output

    # ------------------------------------------------------------------
    # Language detection + transcription
    # ------------------------------------------------------------------

    def _transcribe_with_language_detection(
        self,
        audio_path:    str,
        source:        str,
        language_mode: Optional[str] = None,
    ):
        """
        Transcribe audio with user-specified or auto-detected language mode.

        When language_mode is set ('english'/'tamil'/'tanglish'):
          Delegates directly to WhisperPipeline.transcribe_with_language_detection()
          with the mode — no 30-second pre-pass needed.

        When language_mode is None:
          Falls back to auto-detection (confidence-score based).

        Returns:
            (TranscriptionResult, was_translated: bool)
        """
        if hasattr(self._whisper, "transcribe_with_language_detection"):
            result = self._whisper.transcribe_with_language_detection(
                audio_path, source=source, language_mode=language_mode
            )
            return result, result.was_translated

        # Legacy fallback path (should not be reached with current WhisperPipeline)
        preprocessed = self._whisper._preprocess(audio_path)
        if language_mode:
            mode   = language_mode.lower().strip()
            task   = "translate" if mode in ("tamil", "tanglish") else "transcribe"
            result = self._whisper.transcribe(audio_path, source=source, task=task)
            return result, (task == "translate")

        detected_lang = self._detect_language(preprocessed)
        logger.info(f"Auto-detected language: {detected_lang} for {source}")
        needs_translation = detected_lang in _TAMIL_LANGUAGE_CODES
        if needs_translation:
            result = self._transcribe_translate(preprocessed, source)
        else:
            result = self._whisper.transcribe(audio_path, source=source)
        return result, needs_translation

    def _detect_language(self, preprocessed_path: str) -> str:
        """
        Run Whisper on first 30 s to detect language.
        Returns language code, e.g. "en", "ta".
        """
        try:
            model = self._whisper.model

            # Load audio array
            try:
                from faster_whisper.audio import decode_audio
                audio = decode_audio(preprocessed_path)
            except ImportError:
                import soundfile as sf
                audio, _ = sf.read(preprocessed_path, dtype="float32")

            # Trim to 30 s (16 000 samples/s)
            max_samples = _LANG_DETECT_DURATION_S * 16_000
            audio_snippet = audio[:max_samples]

            result = model.detect_language(audio_snippet)

            # faster-whisper returns (language, probs_dict) in some versions
            # and just probs_dict in others — handle both
            if isinstance(result, tuple):
                _, probs = result
            else:
                probs = result

            if isinstance(probs, dict):
                detected = max(probs, key=probs.get)
            else:
                # list of (lang, prob) tuples
                detected = max(probs, key=lambda x: x[1])[0]

            logger.debug(
                f"Language detection result: {detected} "
                f"(raw type={type(probs).__name__})"
            )
            return detected

        except Exception as exc:
            logger.warning(
                f"Language detection failed ({exc}) — defaulting to 'en'. "
                "If audio is Tamil/Tanglish, pass translate=True explicitly."
            )
            return "en"

    def _transcribe_translate(self, preprocessed_path: str, source: str):
        """
        Transcribe with task='translate' — output is always English.
        Used when Tamil/Tanglish is detected.
        """
        from pydub import AudioSegment as _AudioSegment
        from ingestion.whisper_pipeline import TranscriptSegment, TranscriptionResult

        audio = _AudioSegment.from_wav(preprocessed_path)
        duration_ms = len(audio)

        segments_raw, info = self._whisper.model.transcribe(
            preprocessed_path,
            language=None,          # Whisper auto-detects source language
            task="translate",       # output always English
            beam_size=5,
            word_timestamps=True,
            initial_prompt=self._whisper._build_initial_prompt(source),
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 200,
            },
        )

        segments = []
        for i, seg in enumerate(segments_raw):
            words = []
            if seg.words:
                for w in seg.words:
                    words.append({
                        "word":        w.word.strip(),
                        "start_ms":    int(w.start * 1000),
                        "end_ms":      int(w.end * 1000),
                        "probability": round(w.probability, 3),
                    })
            segments.append(TranscriptSegment(
                segment_id=f"{source}_seg_{i:04d}",
                start_ms=int(seg.start * 1000),
                end_ms=int(seg.end * 1000),
                text=seg.text,
                words=words,
                avg_logprob=round(seg.avg_logprob, 4),
                no_speech_prob=round(seg.no_speech_prob, 4),
                source=source,
                was_translated=True,    # always True — translate mode
            ))

        return TranscriptionResult(
            audio_path=preprocessed_path,
            source=source,
            language=info.language,
            was_translated=True,        # required field in updated schema
            duration_ms=duration_ms,
            segments=segments,
        )

    # ------------------------------------------------------------------
    # Output formatting
    # ------------------------------------------------------------------

    def _format_output(
        self,
        attributed: list[dict],
        session_id: str,
        was_translated: bool,
    ) -> list[dict]:
        """
        Convert attributed segments to the canonical output format.
        Matches the structure EventExtractor expects from structured JSON.
        """
        result = []
        for seg in attributed:
            ts_ms = seg.get("timestamp_ms", 0)
            result.append({
                # ── Core fields (match structured JSON format) ──────────
                "timestamp_ms":   ts_ms,
                "time":           _ms_to_mmss(ts_ms),
                "speaker":        seg.get("speaker", "Unknown"),
                "role":           seg.get("role", "unknown"),
                "text":           seg.get("text", "").strip(),

                # ── Confidence & traceability ───────────────────────────
                "confidence":     seg.get("confidence", 1.0),
                "source":         seg.get("source", "room"),
                "speaker_label":  seg.get("speaker_label", "keyword_assigned"),
                "was_translated": was_translated,
                "segment_id":     seg.get("segment_id", ""),
                "session_id":     session_id,

                # ── Schema field (for EventExtractor) ───────────────────
                "actor_role":     seg.get("actor_role"),
            })

        # Sort by timestamp — Whisper should be ordered but make it explicit
        result.sort(key=lambda s: s["timestamp_ms"])
        return result


# =============================================================================
# Utility
# =============================================================================

def _ms_to_mmss(ms: int) -> str:
    """Convert milliseconds to MM:SS string. e.g. 168000 → '02:48'"""
    total_s = ms // 1000
    return f"{total_s // 60:02d}:{total_s % 60:02d}"
