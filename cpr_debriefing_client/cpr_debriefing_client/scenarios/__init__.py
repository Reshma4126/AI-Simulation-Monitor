"""
scenarios/__init__.py — Scenario Generation Package
=====================================================
Gamified clinical scenario engine for the CPR Debriefing System.

Exports:
  ScenarioGenerator   - builds scenarios from level × location × discipline × speciality
  OutcomePredictor    - predicts expected outcomes; scores actual vs predicted
  VoiceNarrator       - gTTS-based TTS narrator (server) + Web Speech API (browser)
  InstructorListener  - Whisper STT for instructor voice scenario input
  GamificationEngine  - XP, badges, leaderboard
  DebriefDetector     - detects human debrief in transcript; triggers AI debrief
"""

from .generator import ScenarioGenerator
from .outcome_predictor import OutcomePredictor
from .voice_narrator import VoiceNarrator
from .gamification import GamificationEngine
from .debrief_detector import DebriefDetector

__all__ = [
    "ScenarioGenerator",
    "OutcomePredictor",
    "VoiceNarrator",
    "GamificationEngine",
    "DebriefDetector",
]
