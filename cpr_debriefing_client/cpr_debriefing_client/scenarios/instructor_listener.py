"""
scenarios/instructor_listener.py — Instructor Voice Scenario Input
===================================================================
Captures instructor's spoken scenario description and parses it into
a partial ScenarioSpec. Gaps are filled with generator defaults.

Two capture modes:
  1. Browser MediaRecorder → WebSocket → server Whisper transcription
     (primary mode — browser sends audio chunks to /api/scenario/voice_stream)
  2. Server microphone via sounddevice (if enabled)

The parsed ScenarioSpec is then passed to ScenarioGenerator.generate()
with the extracted parameters, overriding defaults.

This module is only active when the 'instructor_voice_input_enabled' flag is True.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Whisper availability ──────────────────────────────────────────────────────
_WHISPER_AVAILABLE = False
try:
    from faster_whisper import WhisperModel as _WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    logger.warning("[InstructorListener] faster-whisper not installed. Voice input will use text fallback.")


# ── Keyword maps for NLP entity extraction ─────────────────────────────────────
_LEVEL_KEYWORDS = {
    "beginner":     ["beginner", "basic", "simple", "novice", "level 1"],
    "intermediate": ["intermediate", "medium", "moderate", "level 2"],
    "advanced":     ["advanced", "complex", "difficult", "hard", "expert", "level 3", "megacode"],
}

_LOCATION_KEYWORDS = {
    "ER":           ["er", "emergency", "emergency room", "a&e", "accident", "casualty"],
    "ICU":          ["icu", "intensive care", "critical care", "itu", "intensive therapy"],
    "Theatre":      ["theatre", "theater", "operating", "or ", "operation room", "intraop", "intraoperative"],
    "Ward_Medical": ["medical ward", "medicine ward", "general ward", "gen ward"],
    "Ward_Surgical":["surgical ward", "surgery ward", "post-op ward", "post op"],
    "Ward_Ortho":   ["ortho ward", "orthopaedic ward", "orthopedic ward"],
    "Ward_Neuro":   ["neuro ward", "neurology ward", "neuroscience ward"],
    "Ward_Cardio":  ["cardio ward", "cardiology ward", "cardiac ward", "heart ward"],
}

_SPECIALITY_KEYWORDS = {
    "ER":           ["emergency", "trauma resus"],
    "ICU":          ["icu", "intensive care"],
    "Anaesthesia":  ["anaesthesia", "anesthesia", "anaesthetic", "anesthetic"],
    "Cardio":       ["cardiology", "cardiac", "cardio", "heart"],
    "Neuro":        ["neurology", "neuro", "stroke", "brain"],
    "Trauma":       ["trauma", "accident", "rta", "polytrauma"],
    "Ortho":        ["orthopaedic", "orthopedic", "ortho", "fracture", "joint"],
    "Surgery":      ["surgery", "surgical", "general surgery", "laparotomy"],
    "Medicine":     ["medicine", "medical", "internal medicine"],
    "Allied_Medical":  ["physiotherapy", "physio", "occupational therapy", "ot "],
    "Allied_Surgical": ["post-surgical rehab", "surgical rehab"],
}

_RHYTHM_KEYWORDS = {
    "VF":           ["vf", "ventricular fibrillation", "v fib", "vfib"],
    "PEA":          ["pea", "pulseless electrical", "pulseless ea"],
    "asystole":     ["asystole", "flat line", "flatline", "no rhythm"],
    "pVT":          ["pvt", "pulseless vt", "pulseless ventricular tachycardia"],
    "bradycardia_with_pulse": ["bradycardia", "brady", "slow heart", "third degree", "av block"],
    "tachyarrhythmia_with_pulse": ["svt", "vt with pulse", "tachycardia", "fast heart", "af ", "afib"],
    "megacode":     ["megacode", "mega code", "multi-rhythm", "mixed rhythm"],
}

_DISCIPLINE_KEYWORDS = {
    "doctor":          ["doctor", "physician", "registrar", "consultant", "medical officer", "intern"],
    "nurse":           ["nurse", "nursing", "staff nurse", "charge nurse", "sister"],
    "physiotherapist": ["physio", "physiotherapist", "physical therapist"],
    "allied":          ["allied", "allied health", "ot", "occupational", "dietitian", "pharmacist"],
}


class InstructorListener:
    """
    Parse a spoken (or typed) instructor scenario description into
    a partial parameter dict consumable by ScenarioGenerator.

    Example
    -------
    listener = InstructorListener()

    # From text (browser transcription or typed fallback)
    params = listener.parse_text(
        "Give me an advanced ICU scenario for doctors, "
        "a VF arrest in a cardiac patient."
    )
    # → {"level": "advanced", "location": "ICU", "speciality": "Cardio",
    #    "discipline": ["doctor"], "rhythm_hint": "VF"}
    """

    def __init__(self, whisper_model_size: str = "small"):
        self._model = None
        self._model_size = whisper_model_size

    # ── Primary public API ────────────────────────────────────────────────────

    def parse_text(self, text: str) -> Dict[str, Any]:
        """
        Extract scenario parameters from a plain-text instructor utterance.

        Returns a partial param dict:
        {
          "level":       str | None,
          "location":    str | None,
          "speciality":  str | None,
          "discipline":  list[str],
          "rhythm_hint": str | None,
          "raw_text":    str,
        }
        """
        text_lower = text.lower()

        return {
            "level":       self._extract_level(text_lower),
            "location":    self._extract_location(text_lower),
            "speciality":  self._extract_speciality(text_lower),
            "discipline":  self._extract_discipline(text_lower),
            "rhythm_hint": self._extract_rhythm(text_lower),
            "raw_text":    text,
        }

    def transcribe_audio_bytes(self, audio_bytes: bytes, language: str = "en") -> Optional[str]:
        """
        Transcribe raw audio bytes using faster-whisper.
        Used when browser sends audio chunk over WebSocket.

        Returns transcribed text or None if unavailable.
        """
        if not _WHISPER_AVAILABLE:
            logger.warning("[InstructorListener] faster-whisper not available; cannot transcribe.")
            return None

        import io
        import tempfile
        import os

        try:
            if self._model is None:
                logger.info(f"[InstructorListener] Loading Whisper model: {self._model_size}")
                self._model = _WhisperModel(self._model_size, device="cpu", compute_type="int8")

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            segments, _ = self._model.transcribe(
                tmp_path,
                language=language if language != "auto" else None,
                task="transcribe",
                beam_size=3,
            )
            text = " ".join(s.text.strip() for s in segments)
            logger.info(f"[InstructorListener] Transcribed: {text[:80]}...")
            return text
        except Exception as exc:
            logger.error(f"[InstructorListener] Transcription error: {exc}")
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # ── Entity extractors ─────────────────────────────────────────────────────

    def _extract_level(self, text: str) -> Optional[str]:
        for level, kws in _LEVEL_KEYWORDS.items():
            if any(kw in text for kw in kws):
                return level
        return None

    def _extract_location(self, text: str) -> Optional[str]:
        for loc, kws in _LOCATION_KEYWORDS.items():
            if any(kw in text for kw in kws):
                return loc
        return None

    def _extract_speciality(self, text: str) -> Optional[str]:
        for spec, kws in _SPECIALITY_KEYWORDS.items():
            if any(kw in text for kw in kws):
                return spec
        return None

    def _extract_discipline(self, text: str) -> list:
        found = []
        for disc, kws in _DISCIPLINE_KEYWORDS.items():
            if any(kw in text for kw in kws):
                found.append(disc)
        return found if found else ["doctor"]

    def _extract_rhythm(self, text: str) -> Optional[str]:
        for rhythm, kws in _RHYTHM_KEYWORDS.items():
            if any(kw in text for kw in kws):
                return rhythm
        return None
