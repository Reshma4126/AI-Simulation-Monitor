from __future__ import annotations
import math
import numpy as np

class Co2State:
    def __init__(
        self,
        etco2: float = 38.0,
        respiratory_rate: float = 14.0,
        baseline: float = 0.0,
        upstroke_fraction: float = 0.08,
        plateau_slope: float = 0.02
    ):
        self.etco2 = etco2
        self.respiratory_rate = respiratory_rate
        self.baseline = baseline
        self.upstroke_fraction = upstroke_fraction
        self.plateau_slope = plateau_slope

def _smoothstep(x: np.ndarray) -> np.ndarray:
    clamped = np.clip(x, 0.0, 1.0)
    return clamped * clamped * (3.0 - 2.0 * clamped)

def _sigmoid(x: np.ndarray, steepness: float = 14.0) -> np.ndarray:
    centered = (np.clip(x, 0.0, 1.0) - 0.5) * steepness
    raw = 1.0 / (1.0 + np.exp(-centered))
    low = 1.0 / (1.0 + math.exp(steepness / 2.0))
    high = 1.0 / (1.0 + math.exp(-steepness / 2.0))
    return (raw - low) / (high - low)

def _exp_decay(x: np.ndarray, steepness: float = 6.0) -> np.ndarray:
    progress = np.clip(x, 0.0, 1.0)
    raw = np.exp(-steepness * progress)
    floor = math.exp(-steepness)
    return (raw - floor) / (1.0 - floor)

def _co2_at_phase(phase: np.ndarray, state: Co2State) -> np.ndarray:
    baseline = state.baseline
    amplitude = max(state.etco2 - baseline, 0.0)
    upstroke_start = 0.30
    upstroke_end = upstroke_start + state.upstroke_fraction
    plateau_end = min(upstroke_end + 0.45, 0.88)
    downstroke_end = 0.96

    values = np.full_like(phase, baseline, dtype=float)

    upstroke_mask = (phase >= upstroke_start) & (phase < upstroke_end)
    upstroke_progress = (phase[upstroke_mask] - upstroke_start) / (upstroke_end - upstroke_start)
    plateau_entry = baseline + amplitude * (1.0 - state.plateau_slope)
    values[upstroke_mask] = baseline + (plateau_entry - baseline) * _sigmoid(upstroke_progress)

    plateau_mask = (phase >= upstroke_end) & (phase < plateau_end)
    plateau_progress = (phase[plateau_mask] - upstroke_end) / (plateau_end - upstroke_end)
    values[plateau_mask] = plateau_entry + amplitude * state.plateau_slope * plateau_progress

    downstroke_mask = (phase >= plateau_end) & (phase < downstroke_end)
    downstroke_progress = (phase[downstroke_mask] - plateau_end) / (downstroke_end - plateau_end)
    values[downstroke_mask] = baseline + amplitude * _exp_decay(downstroke_progress)

    inspiratory_mask = phase >= downstroke_end
    values[inspiratory_mask] = baseline

    return np.clip(values, baseline, state.etco2)
