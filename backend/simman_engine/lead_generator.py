"""
backend/engine/lead_generator.py
==================================
Generates all 12 ECG leads from a single Lead II reference waveform
using cardiac dipole projection mathematics.

Mathematical basis:
  Lead_i(t) = H(t) · l̂_i
  where H(t) is the cardiac electrical vector and l̂_i is the lead vector.

For a simplified 2D frontal plane model with mean QRS axis = +60°:
  Lead I   = 0.50 × base
  Lead II  = 1.00 × base   (reference)
  Lead III = 0.50 × base
  aVR      = -0.70 × base
  aVL      = 0.25 × base
  aVF      = 0.70 × base

Precordial leads are modelled with per-component scaling, reflecting the
transition from right-heart dominance (V1) to left-heart dominance (V6).

STEMI modulation:
  Anterior STEMI  → ST elevation in V1–V4, reciprocal depression II, III, aVF
  Inferior STEMI  → ST elevation in II, III, aVF, reciprocal depression I, aVL
  Lateral STEMI   → ST elevation in I, aVL, V5, V6
"""

from __future__ import annotations
import numpy as np
from ecg_state import ECGState, RhythmType, IschemiaZone


# ─── Lead scaling coefficients ─────────────────────────────────────────────────
# (p_scale, qrs_scale, t_scale)  —  applied to Lead II reference

_LIMB_LEAD_SCALE: dict[str, tuple[float, float, float]] = {
    "I":   ( 0.50,  0.50,  0.35),
    "II":  ( 1.00,  1.00,  1.00),
    "III": ( 0.50,  0.50,  0.55),
    "aVR": (-0.75, -0.75, -0.55),
    "aVL": ( 0.15,  0.15,  0.05),
    "aVF": ( 0.70,  0.70,  0.75),
}

# Precordial leads have different P, QRS, and T scaling reflecting rotation
_PRECORDIAL_SCALE: dict[str, tuple[float, float, float]] = {
    "V1": ( 0.10,  0.25, -0.30),   # rS pattern, inverted T
    "V2": ( 0.15,  0.50, -0.15),   # rS transitional
    "V3": ( 0.30,  0.80,  0.10),   # transition zone
    "V4": ( 0.40,  1.05,  0.40),   # dominant R starts
    "V5": ( 0.45,  0.95,  0.50),
    "V6": ( 0.50,  0.80,  0.60),
}

ALL_SCALES = {**_LIMB_LEAD_SCALE, **_PRECORDIAL_SCALE}

# ─── STEMI ST modulation (additive mV per lead) ────────────────────────────────

def _stemi_st_delta(state: ECGState) -> dict[str, float]:
    """
    Returns per-lead ST offset (mV) to add on top of the base signal.
    Positive = elevation, Negative = reciprocal depression.
    """
    if state.ischemia_zone == IschemiaZone.NONE:
        # Generic ST change (instructor-controlled elevation/depression)
        base = state.st_elevation - state.st_depression
        return {lead: base * s[1] for lead, s in ALL_SCALES.items()}

    elev  = state.st_elevation
    depr  = -state.st_depression

    if state.ischemia_zone == IschemiaZone.ANTERIOR:
        return {
            "I":   0.0,   "II":  depr,   "III": depr,
            "aVR": 0.0,   "aVL": 0.0,    "aVF": depr,
            "V1":  elev,  "V2":  elev,   "V3": elev,  "V4": elev,
            "V5":  0.0,   "V6":  0.0,
        }
    if state.ischemia_zone == IschemiaZone.INFERIOR:
        return {
            "I":   depr,  "II":  elev,   "III": elev,
            "aVR": 0.0,   "aVL": depr,   "aVF": elev,
            "V1":  0.0,   "V2":  0.0,    "V3": 0.0,  "V4": 0.0,
            "V5":  0.0,   "V6":  0.0,
        }
    if state.ischemia_zone == IschemiaZone.LATERAL:
        return {
            "I":   elev,  "II":  0.0,    "III": depr,
            "aVR": depr,  "aVL": elev,   "aVF": 0.0,
            "V1":  depr,  "V2":  0.0,    "V3": 0.0,  "V4": 0.0,
            "V5":  elev,  "V6":  elev,
        }
    return {lead: 0.0 for lead in ALL_SCALES}


def _lbbb_modulate(leads: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """LBBB-specific per-lead morphology adjustments."""
    out = dict(leads)
    # Lateral leads: broad notched R, discordant T
    for lead in ("I", "aVL", "V5", "V6"):
        if lead in out:
            out[lead] = out[lead] * 0.85  # slight amplitude reduction
    # V1: deep rS pattern
    if "V1" in out:
        out["V1"] = out["V1"] * 0.40
    return out


def _rbbb_modulate(leads: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """RBBB: add RSR' morphology heuristic to V1."""
    out = dict(leads)
    if "V1" in out:
        # Boost V1 to simulate the R' wave (second R peak)
        out["V1"] = out["V1"] * 1.5
    # Deep S wave in lateral leads
    for lead in ("I", "V5", "V6"):
        if lead in out:
            out[lead] = out[lead] * 0.70
    return out


# ─── Public API ────────────────────────────────────────────────────────────────

def generate_all_leads(
    lead2_signal: np.ndarray,
    state: ECGState,
    fs: int,
) -> dict[str, np.ndarray]:
    """
    Given a Lead II reference signal, project it onto all 12 leads.

    Returns: dict mapping lead name (str) → float32 numpy array.
    """
    st_delta = _stemi_st_delta(state)

    # Build ST envelope: a soft square wave aligned to QRS position
    # (approximate: elevate the signal in the ST region using a smoothed step)
    st_envelope = _build_st_envelope(lead2_signal, fs, state)

    leads: dict[str, np.ndarray] = {}
    for lead, (p_s, qrs_s, t_s) in ALL_SCALES.items():
        # Simplified projection: scale by QRS coefficient
        proj = lead2_signal * qrs_s

        # Add per-lead ST modulation
        proj = proj + st_delta.get(lead, 0.0) * st_envelope

        leads[lead] = proj.astype(np.float32)

    # Apply rhythm-specific morphology tweaks
    if state.rhythm == RhythmType.LBBB:
        leads = _lbbb_modulate(leads)
    elif state.rhythm == RhythmType.RBBB:
        leads = _rbbb_modulate(leads)

    return leads


def _build_st_envelope(
    lead2: np.ndarray, fs: int, state: ECGState
) -> np.ndarray:
    """
    Build a smoothed envelope that highlights the ST segment.
    Uses the derivative to locate QRS peaks and builds a shaped window.
    """
    from scipy.signal import find_peaks
    if len(lead2) == 0:
        return np.zeros_like(lead2)

    # Find R peaks
    r_peaks, _ = find_peaks(lead2, height=0.3, distance=int(fs * 0.3))

    envelope = np.zeros(len(lead2), dtype=np.float32)
    st_window_samples = int(0.12 * fs)   # ~120ms ST region

    for peak in r_peaks:
        st_start = peak + int(0.04 * fs)   # ~40ms after R peak = J point
        st_end   = st_start + st_window_samples
        st_end   = min(st_end, len(lead2))
        if st_start >= len(lead2):
            continue
        # Gaussian-shaped ST bump
        w = np.arange(st_end - st_start)
        center = (st_end - st_start) / 2
        sigma  = (st_end - st_start) / 4
        gauss  = np.exp(-0.5 * ((w - center) / sigma) ** 2)
        envelope[st_start:st_end] += gauss

    # Clip to [0, 1]
    if envelope.max() > 0:
        envelope /= envelope.max()

    return envelope
