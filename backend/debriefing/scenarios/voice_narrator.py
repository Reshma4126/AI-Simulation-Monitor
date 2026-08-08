"""
scenarios/voice_narrator.py — AI Voice Narrator
================================================
Two-mode TTS system:
  Server-side  : gTTS (Google TTS) → generates .mp3 → served as /api/tts/<file>
  Browser-side : returns text for Web Speech API (JS SpeechSynthesis)

Mode is controlled by the FeatureFlags 'server_side_tts_enabled' flag.
Both modes are available and the server always provides the text so the
browser can use Web Speech API as a fallback regardless.

gTTS requires internet access. Falls back to browser-mode if gTTS fails.

Usage (from server routes)
--------------------------
narrator = VoiceNarrator(output_dir=Path("output/tts"))

result = narrator.speak(
    text="Attention team. Scenario starting now.",
    use_server_tts=True,
)
# result = {"mode": "server", "audio_url": "/api/tts/abc123.mp3", "text": "..."}
# or      = {"mode": "browser", "text": "..."}
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_GTTS_AVAILABLE = False
try:
    from gtts import gTTS
    _GTTS_AVAILABLE = True
except ImportError:
    logger.warning("[VoiceNarrator] gTTS not installed. Install with: pip install gTTS. Browser TTS fallback will be used.")


class VoiceNarrator:
    """
    Server-side and browser-side TTS narrator.

    Parameters
    ----------
    output_dir  : directory where mp3 files are stored (default: output/tts)
    language    : gTTS language code (default: 'en')
    slow        : gTTS slow mode (default: False)
    """

    def __init__(
        self,
        output_dir: Path | str = Path("output/tts"),
        language:   str = "en",
        slow:       bool = False,
    ):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._language = language
        self._slow     = slow

    # ── Public API ────────────────────────────────────────────────────────────

    def speak(
        self,
        text:            str,
        use_server_tts:  bool = False,
        filename_hint:   Optional[str] = None,
    ) -> dict:
        """
        Generate TTS for the given text.

        Returns a dict:
          {"mode": "server", "audio_url": "/api/tts/<file>", "text": "..."}
          {"mode": "browser", "text": "..."}
        """
        text = text.strip()
        if not text:
            return {"mode": "browser", "text": ""}

        if use_server_tts and _GTTS_AVAILABLE:
            try:
                audio_url = self._gtts_speak(text, filename_hint)
                return {"mode": "server", "audio_url": audio_url, "text": text}
            except Exception as exc:
                logger.warning(f"[VoiceNarrator] gTTS failed: {exc}. Falling back to browser TTS.")

        return {"mode": "browser", "text": text}

    def speak_scenario_intro(self, spec: dict, use_server_tts: bool = False) -> dict:
        """Speak the scenario introduction text from a ScenarioSpec."""
        text = spec.get("narration_intro", "")
        if not text:
            text = self._build_intro_from_spec(spec)
        return self.speak(text, use_server_tts=use_server_tts, filename_hint="intro")

    def speak_hint(self, hint: str, use_server_tts: bool = False) -> dict:
        """Speak a beginner hint."""
        text = f"Hint: {hint}"
        return self.speak(text, use_server_tts=use_server_tts, filename_hint="hint")

    def speak_debrief_summary(
        self,
        narrative_text: str,
        score:          float,
        grade:          str,
        use_server_tts: bool = False,
    ) -> dict:
        """
        Speak the AI-generated debriefing summary aloud.
        Called when no human debrief is detected in the session transcript.
        """
        intro = (
            f"This is your AI-generated debriefing report. "
            f"Your overall score is {score:.0f} out of 100, grade {grade}. "
        )
        full_text = intro + self._clean_for_tts(narrative_text)
        return self.speak(full_text, use_server_tts=use_server_tts, filename_hint="debrief")

    def speak_outcome(
        self,
        prediction_result: dict,
        use_server_tts:    bool = False,
    ) -> dict:
        """Speak the post-scenario prediction accuracy summary."""
        accuracy = prediction_result.get("prediction_accuracy", 0)
        grade    = prediction_result.get("grade", "?")
        misses   = prediction_result.get("critical_misses", [])
        xp       = prediction_result.get("xp_earned", 0)

        miss_text = ""
        if misses:
            miss_text = (
                f"Critical steps that were missed: "
                + "; ".join(misses[:3])
                + ". "
            )

        text = (
            f"Scenario complete. "
            f"Prediction accuracy: {accuracy:.0f} percent, grade {grade}. "
            f"{miss_text}"
            f"You earned {xp} experience points."
        )
        return self.speak(text, use_server_tts=use_server_tts, filename_hint="outcome")

    def clean_old_files(self, max_files: int = 100) -> None:
        """Delete oldest TTS mp3 files if directory grows too large."""
        files = sorted(self._output_dir.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
        for f in files[:-max_files]:
            try:
                f.unlink()
            except Exception:
                pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _gtts_speak(self, text: str, filename_hint: Optional[str] = None) -> str:
        """Generate gTTS mp3. Returns relative URL path /api/tts/<filename>."""
        # Use content hash for cache-friendliness
        text_hash  = hashlib.md5(text.encode()).hexdigest()[:8]
        hint_slug  = (filename_hint or "tts").replace(" ", "_")[:20]
        filename   = f"{hint_slug}_{text_hash}.mp3"
        filepath   = self._output_dir / filename

        if not filepath.exists():
            tts = gTTS(text=text, lang=self._language, slow=self._slow)
            tts.save(str(filepath))
            logger.info(f"[VoiceNarrator] gTTS saved: {filepath}")

        return f"/api/tts/{filename}"

    def _build_intro_from_spec(self, spec: dict) -> str:
        """Fallback intro builder if narration_intro not set in spec."""
        level    = spec.get("level", "").title()
        loc      = spec.get("location_label", "hospital")
        pt       = spec.get("patient", {})
        rhythm   = spec.get("rhythm_type", "cardiac arrest")
        return (
            f"Attention team. {level}-level scenario in the {loc}. "
            f"Patient: {pt.get('age', 'unknown')}-year-old {pt.get('sex', 'patient')}. "
            f"Presenting with {pt.get('presentation', 'cardiac arrest')}. "
            f"You may begin."
        )

    def _clean_for_tts(self, text: str) -> str:
        """Strip markdown-like symbols that sound bad when spoken."""
        import re
        text = re.sub(r"\*+", "", text)
        text = re.sub(r"#{1,6}\s*", "", text)
        text = re.sub(r"\n+", " ", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()
