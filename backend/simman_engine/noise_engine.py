"""
backend/engine/noise_engine.py
================================
Mathematically injects physiological and electrical artifacts into ECG.
"""

from __future__ import annotations
import numpy as np
from ecg_state import ECGState, ArtifactType


def inject(signal: np.ndarray, fs: int, state: ECGState) -> np.ndarray:
    """Add artifacts to the signal based on ECG state. Returns a new array."""
    if state.artifact_level <= 0.0 or state.artifact_type == ArtifactType.NONE:
        return signal

    t   = np.arange(len(signal), dtype=np.float32) / fs
    lvl = state.artifact_level
    art = np.zeros_like(signal)

    match state.artifact_type:
        case ArtifactType.BASELINE:
            # Slow sine (0.15 Hz) — respiratory baseline wander
            art += lvl * 0.20 * np.sin(2 * np.pi * 0.15 * t).astype(np.float32)

        case ArtifactType.POWERLINE_50:
            art += lvl * 0.06 * np.sin(2 * np.pi * 50.0 * t).astype(np.float32)

        case ArtifactType.POWERLINE_60:
            art += lvl * 0.06 * np.sin(2 * np.pi * 60.0 * t).astype(np.float32)

        case ArtifactType.MOTION:
            # Broadband low-frequency noise burst
            rng  = np.random.default_rng()
            art += (lvl * 0.3 * rng.standard_normal(len(signal))).astype(np.float32)

        case ArtifactType.EMG:
            # High-frequency muscle artifact
            rng  = np.random.default_rng()
            art += (lvl * 0.05 * rng.standard_normal(len(signal))).astype(np.float32)

    return signal + art
