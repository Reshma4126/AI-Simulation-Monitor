"""
backend/engine/rhythm_intelligence.py
=======================================
Rhythm Intelligence Layer — clinical metadata and wave visibility rules.

Provides:
  - Per-rhythm HR constraints (min, max, default)
  - Per-rhythm morphology metadata (P-wave, T-wave, QRS characteristics)
  - Adaptive wave visibility factors based on HR and rhythm
  - No changes to the mathematical generator — only amplitude scaling

Usage:
  from simman_engine.rhythm_intelligence import (
      get_wave_visibility,
      get_rhythm_hr_limits,
      get_rhythm_default_hr,
      get_rhythm_profile,
      RHYTHM_INTELLIGENCE,
  )
"""

from __future__ import annotations
from dataclasses import dataclass
from ecg_state import RhythmType


# ─── Rhythm Profile dataclass ─────────────────────────────────────────────────

@dataclass(frozen=True)
class RhythmProfile:
    """Clinical metadata for a rhythm type."""
    hr_min:          int     # minimum physiologically realistic HR (bpm)
    hr_max:          int     # maximum physiologically realistic HR (bpm)
    default_hr:      int     # recommended starting HR for this rhythm
    p_wave:          str     # "present" | "absent" | "retrograde" | "fibrillatory" | "flutter" | "dissociated"
    t_wave:          str     # "present" | "suppressed" | "discordant" | "absent"
    qrs_type:        str     # "narrow" | "wide" | "bizarre" | "sinusoidal" | "chaotic" | "escape"
    morphology_desc: str     # brief waveform description for instructor panel
    condition_desc:  str     # clinical teaching description


# ─── Per-rhythm Intelligence Table ────────────────────────────────────────────

RHYTHM_INTELLIGENCE: dict[RhythmType, RhythmProfile] = {
    RhythmType.NSR: RhythmProfile(
        hr_min=60, hr_max=100, default_hr=75,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="Normal P-QRS-T morphology, regular rhythm",
        condition_desc="Normal Sinus Rhythm — physiologically normal conduction",
    ),
    RhythmType.SINUS_BRADY: RhythmProfile(
        hr_min=20, hr_max=59, default_hr=50,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="Tall distinct P waves, pronounced T waves, slow regular rhythm",
        condition_desc="Sinus Bradycardia — slow SA node discharge; may cause hemodynamic compromise",
    ),
    RhythmType.SINUS_TACHY: RhythmProfile(
        hr_min=101, hr_max=180, default_hr=120,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="P waves may merge with preceding T at very high rates",
        condition_desc="Sinus Tachycardia — physiologic response to stress, pain, fever, hypovolemia",
    ),
    RhythmType.AFIB: RhythmProfile(
        hr_min=30, hr_max=180, default_hr=70,
        p_wave="fibrillatory", t_wave="present", qrs_type="narrow",
        morphology_desc="No organised P waves; irregular baseline flutter; irregularly irregular RR",
        condition_desc="Atrial Fibrillation — chaotic atrial activity, irregularly irregular ventricular response",
    ),
    RhythmType.AFLUTTER: RhythmProfile(
        hr_min=70, hr_max=180, default_hr=150,
        p_wave="flutter", t_wave="present", qrs_type="narrow",
        morphology_desc="Sawtooth flutter waves at ~300 bpm; ventricular rate typically 150 (2:1 block)",
        condition_desc="Atrial Flutter — organised atrial tachycardia with characteristic flutter waves",
    ),
    RhythmType.JUNCTIONAL: RhythmProfile(
        hr_min=40, hr_max=60, default_hr=50,
        p_wave="retrograde", t_wave="present", qrs_type="narrow",
        morphology_desc="Retrograde inverted P wave after QRS complex",
        condition_desc="Junctional Rhythm — AV node pacemaker; SA node suppressed",
    ),
    RhythmType.AVB1: RhythmProfile(
        hr_min=40, hr_max=100, default_hr=60,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="Prolonged PR interval (>200ms); all P waves conduct",
        condition_desc="1st Degree AV Block — delayed conduction through AV node; benign",
    ),
    RhythmType.AVB2_I: RhythmProfile(
        hr_min=40, hr_max=90, default_hr=50,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="Progressive PR lengthening then dropped QRS (Wenckebach pattern)",
        condition_desc="2nd Degree AV Block (Mobitz I) — Wenckebach pattern; usually benign",
    ),
    RhythmType.AVB2_II: RhythmProfile(
        hr_min=30, hr_max=80, default_hr=50,
        p_wave="present", t_wave="present", qrs_type="wide",
        morphology_desc="Fixed PR with intermittent non-conducted P waves; may have wide QRS",
        condition_desc="2nd Degree AV Block (Mobitz II) — high risk of progression to complete block",
    ),
    RhythmType.AVB3: RhythmProfile(
        hr_min=20, hr_max=50, default_hr=35,
        p_wave="dissociated", t_wave="present", qrs_type="escape",
        morphology_desc="P waves completely dissociated from ventricular escape rhythm",
        condition_desc="3rd Degree (Complete) AV Block — no atrial-ventricular conduction; requires pacing",
    ),
    RhythmType.PAC: RhythmProfile(
        hr_min=50, hr_max=110, default_hr=95,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="Premature ectopic P waves with brief compensatory pause",
        condition_desc="Premature Atrial Contractions — early atrial depolarisations; usually benign",
    ),
    RhythmType.PVC: RhythmProfile(
        hr_min=50, hr_max=100, default_hr=75,
        p_wave="present", t_wave="discordant", qrs_type="bizarre",
        morphology_desc="Every 4th beat: wide bizarre QRS, no P, discordant T; compensatory pause follows",
        condition_desc="Premature Ventricular Contractions — ectopic ventricular depolarisation",
    ),
    RhythmType.SVT: RhythmProfile(
        hr_min=150, hr_max=250, default_hr=156,
        p_wave="absent", t_wave="suppressed", qrs_type="narrow",
        morphology_desc="Very rapid narrow complexes; P waves buried in T waves or absent",
        condition_desc="Supraventricular Tachycardia — re-entrant circuit above His bundle",
    ),
    RhythmType.VT: RhythmProfile(
        hr_min=120, hr_max=280, default_hr=180,
        p_wave="absent", t_wave="discordant", qrs_type="wide",
        morphology_desc="Wide bizarre repetitive QRS complexes; no P waves; discordant T waves",
        condition_desc="Ventricular Tachycardia — sustained ventricular origin; hemodynamically unstable",
    ),
    RhythmType.VF: RhythmProfile(
        hr_min=0, hr_max=0, default_hr=0,
        p_wave="absent", t_wave="absent", qrs_type="chaotic",
        morphology_desc="Chaotic irregular oscillations; no recognisable waveforms",
        condition_desc="Ventricular Fibrillation — cardiac arrest; immediate defibrillation required",
    ),
    RhythmType.TORSADES: RhythmProfile(
        hr_min=150, hr_max=280, default_hr=220,
        p_wave="absent", t_wave="absent", qrs_type="bizarre",
        morphology_desc="Twisting QRS axis (sinusoidal envelope); no P or T waves",
        condition_desc="Torsades de Pointes — polymorphic VT associated with long QT interval",
    ),
    RhythmType.ASYSTOLE: RhythmProfile(
        hr_min=0, hr_max=0, default_hr=0,
        p_wave="absent", t_wave="absent", qrs_type="chaotic",
        morphology_desc="Flat isoelectric line; no cardiac electrical activity",
        condition_desc="Asystole — cardiac arrest; no electrical activity; CPR + epinephrine",
    ),
    RhythmType.PEA: RhythmProfile(
        hr_min=20, hr_max=80, default_hr=60,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="Low-voltage organised electrical activity; no mechanical output",
        condition_desc="Pulseless Electrical Activity — organised ECG with no effective cardiac output",
    ),
    RhythmType.LBBB: RhythmProfile(
        hr_min=50, hr_max=100, default_hr=60,
        p_wave="present", t_wave="discordant", qrs_type="wide",
        morphology_desc="Broad notched R in lateral leads (I, aVL, V5-V6); discordant T waves; QRS >120ms",
        condition_desc="Left Bundle Branch Block — delayed left ventricular activation",
    ),
    RhythmType.RBBB: RhythmProfile(
        hr_min=50, hr_max=100, default_hr=60,
        p_wave="present", t_wave="present", qrs_type="wide",
        morphology_desc="RSR' pattern in V1; wide S wave in lateral leads; QRS >120ms",
        condition_desc="Right Bundle Branch Block — delayed right ventricular activation",
    ),
    RhythmType.ANT_STEMI: RhythmProfile(
        hr_min=50, hr_max=110, default_hr=60,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="ST elevation V1–V4; reciprocal ST depression II/III/aVF; hyperacute T waves",
        condition_desc="Anterior STEMI — left anterior descending (LAD) artery occlusion",
    ),
    RhythmType.INF_STEMI: RhythmProfile(
        hr_min=40, hr_max=100, default_hr=60,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="ST elevation II/III/aVF; reciprocal ST depression I/aVL",
        condition_desc="Inferior STEMI — right coronary artery (RCA) or circumflex occlusion",
    ),
    RhythmType.LAT_STEMI: RhythmProfile(
        hr_min=50, hr_max=100, default_hr=60,
        p_wave="present", t_wave="present", qrs_type="narrow",
        morphology_desc="ST elevation I/aVL/V5–V6; reciprocal depression V1/III",
        condition_desc="Lateral STEMI — circumflex or diagonal branch occlusion",
    ),
}


# ─── Public API ───────────────────────────────────────────────────────────────

def get_rhythm_profile(rhythm: RhythmType) -> RhythmProfile:
    """Return the clinical profile for a rhythm. Fallback to NSR if unknown."""
    return RHYTHM_INTELLIGENCE.get(rhythm, RHYTHM_INTELLIGENCE[RhythmType.NSR])


def get_rhythm_hr_limits(rhythm: RhythmType) -> tuple[int, int]:
    """Return (min_hr, max_hr) for a rhythm."""
    p = get_rhythm_profile(rhythm)
    return (p.hr_min, p.hr_max)


def get_rhythm_default_hr(rhythm: RhythmType) -> int:
    """Return the recommended default HR for a rhythm."""
    return get_rhythm_profile(rhythm).default_hr


def get_wave_visibility(rhythm: RhythmType, heart_rate: float) -> tuple[float, float]:
    """
    Return (p_factor, t_factor) in [0.0, 1.0] — amplitude scaling for P and T waves.

    Rules applied in priority order:
      1. Rhythm-specific suppression (ventricular rhythms never show P)
      2. Rate-based progressive suppression:
         HR < 150       : full visibility
         HR 150–180     : T wave begins to reduce
         HR 180–220     : P partially hidden, T partially hidden
         HR 220–250     : P suppressed, T suppressed
         HR > 250       : ventricular-only waveform (both = 0)

    Returns amplitude scale factors (not boolean): the generator multiplies
    the Gaussian amplitude by this factor.
    """
    profile = get_rhythm_profile(rhythm)

    # Rhythm-level baseline visibility
    p_base: float = 0.0 if profile.p_wave in ("absent", "chaotic") else 1.0
    t_base: float = 0.0 if profile.t_wave == "absent" else 1.0

    # Fibrillatory baseline — P amplitude already 0 (no P drawn), keep as 0
    if profile.p_wave == "fibrillatory":
        p_base = 0.0

    # Flutter: inverted P already modelled in BeatParams, keep visibility=1.0
    if profile.p_wave == "flutter":
        p_base = 1.0

    # Chaotic (VF/Asystole): nothing to scale — both zero
    if profile.qrs_type == "chaotic":
        return (0.0, 0.0)

    # Rate-based suppression (applied on top of rhythm baseline)
    hr = heart_rate
    if hr < 150:
        p_rate = 1.0
        t_rate = 1.0
    elif hr < 180:
        # T wave gently reduces, P still visible
        t_rate = max(0.0, 1.0 - (hr - 150) / 30.0)   # 1.0 → 0.0
        p_rate = 1.0
    elif hr < 220:
        # Both P and T suppressing
        t_rate = 0.0
        p_rate = max(0.0, 1.0 - (hr - 180) / 40.0)   # 1.0 → 0.0
    elif hr < 250:
        # P fully gone, T fully gone
        t_rate = 0.0
        p_rate = 0.0
    else:
        # Pure ventricular waveform — no P or T
        t_rate = 0.0
        p_rate = 0.0

    return (p_base * p_rate, t_base * t_rate)


def intelligence_payload(rhythm: RhythmType) -> dict:
    """
    Build the ECG_INTELLIGENCE JSON payload for a given rhythm.
    Sent once per rhythm change over the WebSocket.
    """
    p = get_rhythm_profile(rhythm)
    return {
        "rhythm":          rhythm.value,
        "p_wave":          p.p_wave,
        "t_wave":          p.t_wave,
        "qrs_type":        p.qrs_type,
        "morphology_desc": p.morphology_desc,
        "condition_desc":  p.condition_desc,
        "hr_min":          p.hr_min,
        "hr_max":          p.hr_max,
        "default_hr":      p.default_hr,
    }
