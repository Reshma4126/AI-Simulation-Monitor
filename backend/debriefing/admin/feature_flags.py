"""
admin/feature_flags.py — Feature Flag Store
============================================
File-backed JSON feature flag store with in-memory cache.
All flag mutations require an authenticated admin.

Flag schema (per entry in flags.json)
--------------------------------------
{
  "value":       bool,
  "description": str,
  "changed_by":  str,   # admin username
  "changed_at":  str    # ISO timestamp
}
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_HERE      = Path(__file__).parent
_FLAGS_PATH = _HERE / "flags.json"

# ── Default flag definitions ──────────────────────────────────────────────────
_DEFAULTS: Dict[str, dict] = {
    "scenario_generation_enabled": {
        "value":       True,
        "description": "Allow instructors to generate AI scenarios from the Scenario Studio.",
        "changed_by":  "system",
        "changed_at":  "",
    },
    "ai_scenario_narration_enabled": {
        "value":       True,
        "description": "System speaks the scenario introduction and hints aloud during a run.",
        "changed_by":  "system",
        "changed_at":  "",
    },
    "ai_debrief_speech_enabled": {
        "value":       True,
        "description": "When no human debrief is detected in the session transcript, the AI reads the debriefing report aloud.",
        "changed_by":  "system",
        "changed_at":  "",
    },
    "instructor_voice_input_enabled": {
        "value":       False,
        "description": "Allow instructors to speak their own scenario; system transcribes and parses it.",
        "changed_by":  "system",
        "changed_at":  "",
    },
    "outcome_prediction_enabled": {
        "value":       True,
        "description": "Before a scenario runs, system predicts expected outcomes and benchmarks actual performance.",
        "changed_by":  "system",
        "changed_at":  "",
    },
    "gamification_enabled": {
        "value":       True,
        "description": "Enable XP, badges, and leaderboard for scenario completions.",
        "changed_by":  "system",
        "changed_at":  "",
    },
    "server_side_tts_enabled": {
        "value":       False,
        "description": "Generate TTS audio on the server (gTTS) instead of browser Web Speech API. Requires internet access.",
        "changed_by":  "system",
        "changed_at":  "",
    },
    "video_role_recognition_enabled": {
        "value":       False,
        "description": "[Phase 2] Activate camera feed for per-person role recognition during live scenarios.",
        "changed_by":  "system",
        "changed_at":  "",
    },
}


class FeatureFlags:
    """
    Thread-safe feature flag store backed by admin/flags.json.

    Usage
    -----
    flags = FeatureFlags()
    flags.get("ai_debrief_speech_enabled")          → True/False
    flags.set("gamification_enabled", False, "admin_user")
    flags.all()                                      → {name: {...}, ...}
    """

    _lock  = threading.Lock()
    _cache: Dict[str, dict] | None = None

    def __init__(self):
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, name: str, default: bool = False) -> bool:
        """Return the boolean value of a flag, or `default` if unknown."""
        with self._lock:
            flags = self._ensure_loaded()
            return bool(flags.get(name, {}).get("value", default))

    def set(self, name: str, value: bool, by_username: str) -> tuple[bool, str]:
        """
        Update a flag value. Returns (success, message).
        Creating new flags is not allowed — only pre-defined flags may be toggled.
        """
        with self._lock:
            flags = self._ensure_loaded()
            if name not in flags:
                return False, f"Unknown flag '{name}'. Only predefined flags can be toggled."
            flags[name]["value"]      = bool(value)
            flags[name]["changed_by"] = by_username
            flags[name]["changed_at"] = datetime.now(timezone.utc).isoformat()
            self._save(flags)
            logger.info(f"[FeatureFlags] '{name}' → {value} (by {by_username})")
        return True, f"Flag '{name}' set to {value}."

    def all(self) -> Dict[str, dict]:
        """Return all flags with their full metadata (copy)."""
        with self._lock:
            return dict(self._ensure_loaded())

    def all_values(self) -> Dict[str, bool]:
        """Return a {name: bool} snapshot — convenient for template rendering."""
        with self._lock:
            flags = self._ensure_loaded()
            return {k: bool(v["value"]) for k, v in flags.items()}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> Dict[str, dict]:
        """Return the in-memory cache (must be called with lock held)."""
        if FeatureFlags._cache is None:
            FeatureFlags._cache = self._read_from_disk()
        return FeatureFlags._cache

    def _load(self):
        """Public eager load (called from __init__, lock not needed)."""
        with self._lock:
            FeatureFlags._cache = self._read_from_disk()

    def _read_from_disk(self) -> Dict[str, dict]:
        """Read flags.json, merge with defaults to ensure no missing entries."""
        if _FLAGS_PATH.exists():
            try:
                with open(_FLAGS_PATH, "r", encoding="utf-8") as f:
                    stored: dict = json.load(f)
            except Exception as exc:
                logger.warning(f"[FeatureFlags] Could not read flags.json: {exc} — using defaults.")
                stored = {}
        else:
            stored = {}

        # Merge stored values onto defaults (adds new flags, preserves saved values)
        merged = {}
        for name, default_meta in _DEFAULTS.items():
            merged[name] = dict(default_meta)
            if name in stored:
                # Preserve saved value + audit info, keep description from defaults
                merged[name]["value"]      = stored[name].get("value", default_meta["value"])
                merged[name]["changed_by"] = stored[name].get("changed_by", "system")
                merged[name]["changed_at"] = stored[name].get("changed_at", "")

        # Persist merged state (creates file on first run)
        self._save(merged)
        return merged

    def _save(self, flags: Dict[str, dict]) -> None:
        """Write flags to disk (must be called with lock held)."""
        try:
            _FLAGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_FLAGS_PATH, "w", encoding="utf-8") as f:
                json.dump(flags, f, indent=2)
        except Exception as exc:
            logger.error(f"[FeatureFlags] Could not write flags.json: {exc}")
