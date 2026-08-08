"""
ingestion/whisper_pipeline.py
==============================
Wraps faster-whisper for the CPR debriefing system.

Hardware target: NVIDIA RTX 2050 (4 GB GDDR6)
  Default model : small   (int8, ~400-500 MB VRAM)
  Device        : cuda (GPU-first) → auto-falls back to cpu if CUDA unavailable
  Reason        : small + int8 gives good medical-vocabulary accuracy with
                  minimal VRAM usage. Leaves headroom for pyannote (~700 MB)
                  to run sequentially on the same GPU without OOM.

Input modes:
  source="lapel"  — team-leader clip mic
  source="ceiling" — room/overhead mic
  source="room"   — single mixed-room mic (new: single-mic sessions)

Language handling:
  Whisper detects language automatically on first 30 s.
  If Tamil ("ta") or other non-English detected → task="translate"
  so ALL output segments exit as English.
  Tanglish (code-switched) is handled by translate mode equally well.
"""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RTX 2050 safe defaults
# ---------------------------------------------------------------------------

DEFAULT_MODEL_SIZE   = "small"        # ~400-500 MB VRAM with int8 — ample headroom on 4 GB
DEFAULT_DEVICE       = "cuda"         # GPU-first; auto-falls back to cpu if unavailable
DEFAULT_COMPUTE_TYPE = "int8"         # quantised → low VRAM, fast on both CPU and GPU


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TranscriptSegment:
    """A single transcribed segment with word-level timestamps."""
    segment_id:     str
    start_ms:       int
    end_ms:         int
    text:           str
    words:          list[dict]          # [{word, start_ms, end_ms, probability}]
    avg_logprob:    float
    no_speech_prob: float
    source:         str                 # "lapel" | "ceiling" | "room"
    speaker_label:  Optional[str] = None   # filled later by diarization
    was_translated: bool = False           # True if Tamil/non-English input


@dataclass
class TranscriptionResult:
    """Full result from transcribing one audio file."""
    audio_path:     str
    source:         str                 # "lapel" | "ceiling" | "room"
    language:       str                 # detected language code, e.g. "en", "ta"
    was_translated: bool                # True if translate task was used
    duration_ms:    int
    segments:       list[TranscriptSegment] = field(default_factory=list)

    def to_event_dicts(self) -> list[dict]:
        """
        Convert segments to partial unified event dicts.
        source_systems, actor_role, confidence etc. filled later
        by diarization + role_assigner.
        """
        events = []
        for seg in self.segments:
            events.append({
                "event_type":     "speech_segment",
                "timestamp_ms":   seg.start_ms,
                "end_ms":         seg.end_ms,
                "source":         self.source,
                "text":           seg.text.strip(),
                "words":          seg.words,
                "segment_id":     seg.segment_id,
                "speaker_label":  seg.speaker_label,
                "confidence":     round(1.0 - seg.no_speech_prob, 3),
                "was_translated": seg.was_translated,
            })
        return events


# ---------------------------------------------------------------------------
# WhisperPipeline
# ---------------------------------------------------------------------------

class WhisperPipeline:
    """
    Wraps faster-whisper for the CPR debriefing system.

    Tuned for NVIDIA RTX 2050 (4 GB GDDR6):
      - Default model : small + int8 (~400-500 MB VRAM — ample headroom)
      - Device        : cuda (GPU-first), auto-falls back to cpu
      - Whisper and pyannote run sequentially — NOT simultaneously

    Usage:
        pipeline = WhisperPipeline()    # GPU-first, RTX 2050 safe
        result   = pipeline.transcribe_with_language_detection("session.wav")
        # result.language       → "ta" or "en"
        # result.was_translated → True if Tamil was detected and translated
        # result.segments       → always English text
    """

    # Medical terminology hints — improves Whisper accuracy on clinical vocab
    MEDICAL_HOTWORDS = [
        "epinephrine", "amiodarone", "defibrillation", "cardioversion",
        "ventricular fibrillation", "pulseless VT", "asystole", "PEA",
        "ROSC", "chest compressions", "CPR", "intubation", "laryngoscope",
        "atropine", "adenosine", "lidocaine", "vasopressin", "sodium bicarbonate",
        "milligram", "microgram", "intravenous", "intraosseous",
        "sinus rhythm", "rhythm check", "pulse check", "airway",
    ]

    # Languages to auto-translate to English
    TRANSLATE_LANGUAGES = {
        "ta",  # Tamil
        "hi",  # Hindi (Tanglish variant)
        "ml",  # Malayalam
        "te",  # Telugu
        "kn",  # Kannada
    }

    # How many seconds of audio to use for language detection
    LANG_DETECT_SECONDS = 30

    def __init__(
        self,
        model_size:    str = DEFAULT_MODEL_SIZE,
        device:        str = DEFAULT_DEVICE,
        compute_type:  str = DEFAULT_COMPUTE_TYPE,
    ):
        # Lazy import — avoids hard dep at module import time
        from faster_whisper import WhisperModel

        # GPU availability check — safe even if torch is not installed
        if device == "cuda":
            try:
                import torch
                if not torch.cuda.is_available():
                    logger.warning(
                        "CUDA requested but torch.cuda.is_available() is False. "
                        "Auto-falling back to CPU (int8)."
                    )
                    device       = "cpu"
                    compute_type = "int8"
                else:
                    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
                    logger.info(
                        f"CUDA available — {torch.cuda.get_device_name(0)} "
                        f"({vram_gb:.1f} GB VRAM)"
                    )
            except ModuleNotFoundError:
                logger.warning(
                    "torch not installed — cannot use CUDA. "
                    "Install with: pip install torch --index-url https://download.pytorch.org/whl/cu121 "
                    "Auto-falling back to CPU (int8)."
                )
                device       = "cpu"
                compute_type = "int8"

        logger.info(
            f"Loading Whisper model '{model_size}' on {device} "
            f"(compute_type={compute_type})"
        )

        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info(f"Whisper '{model_size}' loaded successfully on {device}.")
        except Exception as load_err:
            if device == "cuda":
                logger.warning(
                    f"WhisperModel failed on CUDA ({load_err}). "
                    "Auto-falling back to CPU (int8)."
                )
                device       = "cpu"
                compute_type = "int8"
                self.model   = WhisperModel(model_size, device=device, compute_type=compute_type)
                logger.info(f"Whisper '{model_size}' loaded on CPU (fallback).")
            else:
                raise

        self.model_size   = model_size
        self.device       = device
        self.compute_type = compute_type

    # Language mode → Whisper task mapping
    # "english"  → transcribe (no translation needed)
    # "tamil"    → translate  (output always English)
    # "tanglish" → translate  (mixed Tamil+English → always safer to translate)
    _LANGUAGE_MODE_TASK = {
        "english":  "transcribe",
        "tamil":    "translate",
        "tanglish": "translate",
    }
    # Human-readable label → language code (informational only)
    _LANGUAGE_MODE_CODE = {
        "english":  "en",
        "tamil":    "ta",
        "tanglish": "ta",
    }

    def transcribe_with_language_detection(
        self,
        audio_path:    str,
        source:        str = "room",
        language_mode: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Full pipeline with user-specified or auto-detected language handling.

        When language_mode is provided (preferred):
          Skips the 30-second auto-detection step entirely.
          Routes directly to transcribe (English) or translate (Tamil/Tanglish).

        When language_mode is None (fallback):
          Auto-detects from first 30 s using Whisper's confidence scores.
          Less reliable for Tanglish code-switching.

        Args:
            audio_path:    Path to any audio file (WAV/MP3/MP4)
            source:        "room" | "lapel" | "ceiling"
            language_mode: "english" | "tamil" | "tanglish" | None (auto-detect)

        Returns:
            TranscriptionResult — segments always in English
        """
        if language_mode is not None:
            mode = language_mode.lower().strip()
            if mode not in self._LANGUAGE_MODE_TASK:
                raise ValueError(
                    f"Invalid language_mode '{language_mode}'. "
                    f"Must be one of: {list(self._LANGUAGE_MODE_TASK)}"
                )
            task      = self._LANGUAGE_MODE_TASK[mode]
            lang_code = self._LANGUAGE_MODE_CODE[mode]
            logger.info(
                f"[{source}] Language mode: '{mode}' → task={task} "
                f"(auto-detection skipped)"
            )
        else:
            # Fallback: auto-detect from first 30 s
            preprocessed = self._preprocess(audio_path)
            lang_code, lang_conf = self.detect_language(preprocessed)
            should_translate = lang_code in self.TRANSLATE_LANGUAGES
            task = "translate" if should_translate else "transcribe"
            logger.info(
                f"[{source}] Auto-detected language: {lang_code} "
                f"(conf={lang_conf:.2f}) → task={task}"
            )

        return self.transcribe(
            audio_path=audio_path,
            source=source,
            task=task,
            detected_language=lang_code,
        )

    def transcribe(
        self,
        audio_path:        str,
        source:            str = "room",
        task:              str = "transcribe",
        detected_language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Core transcription. Accepts task="transcribe" or task="translate".

        Args:
            audio_path:        Path to audio file
            source:            "room" | "lapel" | "ceiling"
            task:              "transcribe" (default) or "translate" (→ English)
            detected_language: Language code from detect_language(); or None to auto-detect again

        Returns:
            TranscriptionResult
        """
        audio_path       = str(Path(audio_path).resolve())
        preprocessed     = self._preprocess(audio_path)
        was_translated   = (task == "translate")

        logger.info(f"Transcribing [{source}] task={task}: {audio_path}")

        audio       = AudioSegment.from_wav(preprocessed)
        duration_ms = len(audio)

        # ── Language hint ──────────────────────────────────────────────────
        lang_hint = detected_language  # "ta", "en", or None

        # ── VAD strategy ───────────────────────────────────────────────────
        # VAD=0.10 is the best stable threshold for whisper-small on Tanglish.
        # Lower thresholds (0.05) let in more borderline audio that small model
        # can't decode → near-duplicate phrases → dedup removes them → fewer results.
        # To capture the remaining ~19 real speech segments (ROSC, ST elevation,
        # debriefing end) upgrade to whisper-medium or large-v2 which have far
        # better Tamil comprehension and produce fewer hallucinations at any threshold.
        logger.info("VAD: enabled — threshold=0.10 (optimal for whisper-small/Tanglish)")

        segments_raw, info = self.model.transcribe(
            preprocessed,
            language=lang_hint,
            task=task,
            beam_size=5,
            word_timestamps=True,
            initial_prompt=self._build_initial_prompt(source),
            vad_filter=True,
            vad_parameters={
                "threshold":              0.10,   # optimal for whisper-small + Tamil
                "min_speech_duration_ms": 100,
                "min_silence_duration_ms":300,
                "speech_pad_ms":          500,
                "max_speech_duration_s":  30,
            },
            no_speech_threshold=0.70,
            condition_on_previous_text=False,
            temperature=0.0,
        )

        # Build TranscriptSegment dataclasses
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
                was_translated=was_translated,
            ))

        # ── Hallucination pattern filter ───────────────────────────────────
        # Catches character-repetition ("IVVVVVVV") and number-loop ("40,40,40")
        # hallucinations that dedup can't catch (they're unique, just garbage).
        before_filter = len(segments)
        segments = [s for s in segments if not self._is_hallucinated_pattern(s.text)]
        pattern_dropped = before_filter - len(segments)
        if pattern_dropped:
            logger.info(f"Pattern filter removed {pattern_dropped} hallucinated segment(s)")

        # ── Deduplication ──────────────────────────────────────────────────
        # Whisper occasionally hallucinates repeated text over silence even
        # with condition_on_previous_text=False.  Strip obvious repeats.
        segments = self._deduplicate_segments(segments)

        result = TranscriptionResult(
            audio_path=audio_path,
            source=source,
            language=detected_language or info.language,
            was_translated=was_translated,
            duration_ms=duration_ms,
            segments=segments,
        )

        logger.info(
            f"Transcription complete — {len(segments)} segments, "
            f"{duration_ms / 1000:.1f}s, lang={result.language}, "
            f"translated={was_translated}"
        )
        self._log_low_confidence_segments(segments)
        return result

    def _deduplicate_segments(
        self,
        segments: list,
        window_s: float = 60.0,
        similarity_threshold: float = 0.85,
    ) -> list:
        """
        Remove hallucinated repeated segments.

        Whisper sometimes emits identical or near-identical text for silent
        regions.  This scans each segment against recent segments and drops
        it if the normalised text similarity exceeds `similarity_threshold`
        AND it occurs within `window_s` seconds of the original.

        Args:
            segments:             List of TranscriptSegment objects.
            window_s:             Time window to check for repeats (seconds).
            similarity_threshold: 0.0–1.0. 0.85 = 85% text overlap = duplicate.

        Returns:
            Deduplicated segment list (order preserved).
        """
        if not segments:
            return segments

        def _normalise(text: str) -> str:
            return " ".join(text.lower().split())

        kept   = []
        dropped = 0

        for seg in segments:
            norm = _normalise(seg.text)
            is_dup = False

            # Compare against recent kept segments within the time window
            seg_start_s = seg.start_ms / 1000
            for prev in reversed(kept):
                prev_start_s = prev.start_ms / 1000
                if seg_start_s - prev_start_s > window_s:
                    break  # outside window — stop looking back
                prev_norm = _normalise(prev.text)
                # Dice coefficient for overlap
                if prev_norm and norm:
                    prev_words = set(prev_norm.split())
                    curr_words = set(norm.split())
                    overlap = len(prev_words & curr_words)
                    dice = (2 * overlap) / (len(prev_words) + len(curr_words))
                    if dice >= similarity_threshold:
                        is_dup = True
                        break

            if is_dup:
                dropped += 1
                logger.debug(f"Dedup: dropped repeated segment at {seg.start_ms}ms: {seg.text[:60]}")
            else:
                kept.append(seg)

        if dropped:
            logger.info(f"Deduplication removed {dropped} hallucinated repeated segment(s)")
        return kept

    def _is_hallucinated_pattern(self, text: str) -> bool:
        """
        Detect obvious Whisper hallucination patterns:

        1. Character repetition: "IVVVVVVVVVVVVVVVV" — same char repeated 8+ times
        2. Number loop:         "40, 40, 40, 40, 40" — same number repeated 5+ times
        3. Token loop:          "start here. start here. start here." — phrase repeated 4+x
        4. Very short garbage:  single char or pure punctuation

        Returns True if the segment should be dropped.
        """
        import re
        if not text or not text.strip():
            return True

        stripped = text.strip()

        # 1. Single character repeated (e.g. "VVVVVVVVVVVVV")
        if re.search(r'(.)\1{7,}', stripped):
            logger.debug(f"Hallucination (char repeat): {stripped[:50]}")
            return True

        # 2. Same number/token repeated 5+ times (e.g. "40, 40, 40, 40, 40")
        tokens = re.findall(r'\b\w+\b', stripped.lower())
        if len(tokens) >= 5:
            from collections import Counter
            most_common_token, count = Counter(tokens).most_common(1)[0]
            if count / len(tokens) >= 0.6 and len(most_common_token) <= 4:
                logger.debug(f"Hallucination (token loop '{most_common_token}'x{count}): {stripped[:50]}")
                return True

        # 3. Repeated phrase (e.g. "start here. start here. start here.")
        # Split on punctuation and check for phrase repetition
        phrases = [p.strip().lower() for p in re.split(r'[.!?,;]', stripped) if p.strip()]
        if len(phrases) >= 4:
            from collections import Counter
            most_common_phrase, count = Counter(phrases).most_common(1)[0]
            if count >= 4 and len(most_common_phrase) > 3:
                logger.debug(f"Hallucination (phrase repeat '{most_common_phrase}'x{count}): {stripped[:50]}")
                return True

        return False

    def transcribe_session(
        self,
        lapel_path:   str,
        ceiling_path: str,
    ) -> dict[str, TranscriptionResult]:
        """
        Transcribe both lapel + ceiling mics with language detection.
        Processes sequentially to avoid VRAM pressure on RTX 2050.

        Returns:
            {"lapel": TranscriptionResult, "ceiling": TranscriptionResult}
        """
        logger.info("Transcribing lapel mic first (sequential for VRAM safety)...")
        lapel_result = self.transcribe_with_language_detection(lapel_path, source="lapel")

        logger.info("Transcribing ceiling mic...")
        ceiling_result = self.transcribe_with_language_detection(ceiling_path, source="ceiling")

        return {"lapel": lapel_result, "ceiling": ceiling_result}

    # ------------------------------------------------------------------
    # Language detection
    # ------------------------------------------------------------------

    def detect_language(self, audio_path: str) -> tuple[str, float]:
        """
        Run Whisper's built-in language detection on first LANG_DETECT_SECONDS.

        Returns:
            (language_code, confidence)  e.g. ("ta", 0.92) or ("en", 0.98)
        """
        audio_path = str(Path(audio_path).resolve())
        logger.info(f"Detecting language from first {self.LANG_DETECT_SECONDS}s of {audio_path}")

        # Trim to first N seconds using pydub (cheap, no GPU)
        audio        = AudioSegment.from_wav(audio_path)
        clip         = audio[:self.LANG_DETECT_SECONDS * 1000]
        clip_path    = str(Path(audio_path).parent / "_lang_detect_clip.wav")
        clip.export(clip_path, format="wav")

        # Whisper language detection via detect_language()
        import numpy as np
        from faster_whisper import decode_audio
        audio_array = decode_audio(clip_path)
        # faster-whisper v1.x: detect_language returns
        #   (language: str, probability: float, all_probs: list[tuple[str, float]])
        # Older versions returned a dict or list of tuples — handle all cases.
        result = self.model.detect_language(audio_array)

        if isinstance(result, tuple) and len(result) == 3:
            # v1.2.x: (language, probability, all_probs)
            best_lang, confidence, _ = result
        elif isinstance(result, tuple) and len(result) == 2:
            # older: (language, probability)
            best_lang, confidence = result
        elif isinstance(result, dict):
            best_lang  = max(result, key=result.get)
            confidence = result[best_lang]
        elif isinstance(result, list):
            # list of (lang, prob) tuples sorted by prob
            best_lang, confidence = result[0]
        else:
            logger.warning(f"Unexpected detect_language return type: {type(result)} — defaulting to 'en'")
            best_lang, confidence = "en", 0.0

        logger.info(f"Detected language: {best_lang} (confidence={confidence:.3f})")

        # Clean up clip
        try:
            Path(clip_path).unlink()
        except Exception:
            pass

        return best_lang, float(confidence)

    # ------------------------------------------------------------------
    # Audio preprocessing
    # ------------------------------------------------------------------

    def _preprocess(self, audio_path: str) -> str:
        """
        Convert any audio format to mono 16kHz 16-bit WAV.
        Saves alongside original with _preprocessed suffix.
        Skips if cached preprocessed file already exists.

        Strategy:
          - Plain WAV  → pydub (no ffmpeg needed, uses Python wave module)
          - All others → PyAV  (av package ships with compiled FFmpeg —
                                no system ffmpeg installation required)
        Supports: .wav, .mp3, .mp4, .m4a, .ogg, .flac, .aac, and more.
        """
        path        = Path(audio_path)
        output_path = path.parent / f"{path.stem}_preprocessed.wav"

        if output_path.exists():
            logger.debug(f"Using cached preprocessed file: {output_path}")
            return str(output_path)

        logger.info(f"Preprocessing audio → mono 16kHz WAV: {path.name}")

        if path.suffix.lower() == ".wav":
            # WAV: pydub reads natively (no ffmpeg needed)
            audio = AudioSegment.from_wav(str(path))
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            audio.export(str(output_path), format="wav")
        else:
            # All other formats (.m4a, .mp4, .mp3, etc.): use PyAV
            self._preprocess_with_av(str(path), str(output_path))

        logger.info(f"Preprocessed audio saved: {output_path}")
        return str(output_path)

    def _preprocess_with_av(self, audio_path: str, output_path: str) -> None:
        """
        Decode any audio format to mono 16kHz 16-bit WAV using PyAV.

        PyAV (package 'av') ships with FFmpeg compiled as a shared library —
        no system ffmpeg installation or PATH entry required.

        Args:
            audio_path:  Source audio file (any format supported by FFmpeg).
            output_path: Destination .wav path (mono 16kHz 16-bit PCM).
        """
        import wave
        try:
            import av as _av
        except ImportError:
            raise ImportError(
                "PyAV is required to decode non-WAV audio formats.\n"
                "Install with: pip install av"
            )

        logger.info(f"PyAV decoding: {Path(audio_path).name}")

        container = _av.open(audio_path)
        resampler = _av.AudioResampler(format="s16", layout="mono", rate=16000)

        pcm_chunks: list[bytes] = []

        def _collect(result) -> None:
            """Handles both single-frame and list returns from resampler."""
            if result is None:
                return
            frames = result if isinstance(result, list) else [result]
            for f in frames:
                pcm_chunks.append(bytes(f.planes[0]))

        for frame in container.decode(audio=0):
            _collect(resampler.resample(frame))

        _collect(resampler.resample(None))   # flush resampler
        container.close()

        if not pcm_chunks:
            raise ValueError(f"PyAV produced no audio from: {audio_path}")

        raw_pcm   = b"".join(pcm_chunks)
        n_seconds = len(raw_pcm) / (2 * 16000)  # 2 bytes per s16 sample
        logger.info(f"Decoded {n_seconds:.1f}s of audio via PyAV")

        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)    # 16-bit PCM
            wf.setframerate(16000)
            wf.writeframes(raw_pcm)


    # ------------------------------------------------------------------
    # Whisper prompt builder
    # ------------------------------------------------------------------

    def _build_initial_prompt(self, source: str) -> str:
        """
        Prime Whisper with expected vocabulary.
        Lapel → leader language; ceiling/room → team patterns.
        """
        base = (
            "This is a medical simulation recording of an ACLS cardiac arrest scenario. "
            "Medical terms include: " + ", ".join(self.MEDICAL_HOTWORDS[:14]) + ". "
        )
        if source == "lapel":
            return base + (
                "The speaker is the team leader giving orders. "
                "Expected phrases: 'start CPR', 'give one milligram epinephrine IV', "
                "'resume compressions', 'analyze rhythm', 'clear, shocking', "
                "'charge to 200 joules', 'terminate resuscitation'."
            )
        else:
            # ceiling or room
            return base + (
                "Multiple team members are speaking: compressor, airway, IV nurse, "
                "defibrillator operator, and recorder. "
                "Expected phrases: 'epinephrine given', 'compressions ongoing', "
                "'pulse check', 'clear', 'shock delivered', 'rhythm is VF', "
                "'no pulse', 'starting compressions', 'amiodarone administered'."
            )

    # ------------------------------------------------------------------
    # QA helpers
    # ------------------------------------------------------------------

    def _log_low_confidence_segments(
        self,
        segments:  list[TranscriptSegment],
        threshold: float = 0.4,
    ) -> None:
        """Log segments with high no_speech_prob for QA review."""
        low_conf = [s for s in segments if s.no_speech_prob > threshold]
        if low_conf:
            logger.warning(
                f"{len(low_conf)} low-confidence segments "
                f"(no_speech_prob > {threshold}):"
            )
            for s in low_conf:
                logger.warning(
                    f"  [{s.segment_id}] t={s.start_ms}ms "
                    f"no_speech_prob={s.no_speech_prob:.2f} "
                    f"text='{s.text[:60]}'"
                )

    def vram_info(self) -> dict:
        """Return VRAM usage info for monitoring (CUDA only)."""
        if self.device != "cuda":
            return {"device": self.device, "vram_available": False}
        try:
            import torch
            allocated = torch.cuda.memory_allocated() / 1e9
            reserved  = torch.cuda.memory_reserved() / 1e9
            total     = torch.cuda.get_device_properties(0).total_memory / 1e9
            return {
                "device":         self.device,
                "model":          self.model_size,
                "compute_type":   self.compute_type,
                "vram_allocated_gb": round(allocated, 2),
                "vram_reserved_gb":  round(reserved, 2),
                "vram_total_gb":     round(total, 2),
                "vram_free_gb":      round(total - reserved, 2),
            }
        except Exception as e:
            return {"device": self.device, "vram_error": str(e)}
