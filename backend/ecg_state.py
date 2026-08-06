"""
backend/models/ecg_state.py
============================
Central ECG state — the single source of truth for the entire simulation.
Every engine reads from this object. The instructor console writes to it.
"""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


# ─── Enumerations ─────────────────────────────────────────────────────────────

class RhythmType(str, Enum):
    NSR              = "NSR"
    SINUS_BRADY      = "SINUS_BRADY"
    SINUS_TACHY      = "SINUS_TACHY"
    AFIB             = "AFIB"
    AFLUTTER         = "AFLUTTER"
    JUNCTIONAL       = "JUNCTIONAL"
    AVB1             = "AVB1"
    AVB2_I           = "AVB2_I"        # Mobitz I / Wenckebach
    AVB2_II          = "AVB2_II"       # Mobitz II
    AVB3             = "AVB3"          # Complete heart block
    PAC              = "PAC"
    PVC              = "PVC"
    SVT              = "SVT"
    VT               = "VT"
    VF               = "VF"
    TORSADES         = "TORSADES"
    ASYSTOLE         = "ASYSTOLE"
    PEA              = "PEA"
    LBBB             = "LBBB"
    RBBB             = "RBBB"
    ANT_STEMI        = "ANT_STEMI"
    INF_STEMI        = "INF_STEMI"
    LAT_STEMI        = "LAT_STEMI"


class IschemiaZone(str, Enum):
    NONE      = "NONE"
    ANTERIOR  = "ANTERIOR"
    INFERIOR  = "INFERIOR"
    LATERAL   = "LATERAL"


class ConductionState(str, Enum):
    NORMAL = "NORMAL"
    LBBB   = "LBBB"
    RBBB   = "RBBB"
    AVB1   = "AVB1"
    AVB2   = "AVB2"
    AVB3   = "AVB3"


class ArtifactType(str, Enum):
    NONE          = "NONE"
    BASELINE      = "BASELINE"
    POWERLINE_50  = "POWERLINE_50"
    POWERLINE_60  = "POWERLINE_60"
    MOTION        = "MOTION"
    EMG           = "EMG"


class TransferFn(str, Enum):
    IMMEDIATE    = "IMMEDIATE"
    LINEAR       = "LINEAR"
    EXPONENTIAL  = "EXPONENTIAL"
    SIGMOID      = "SIGMOID"


class LeadName(str, Enum):
    I    = "I"
    II   = "II"
    III  = "III"
    aVR  = "aVR"
    aVL  = "aVL"
    aVF  = "aVF"
    V1   = "V1"
    V2   = "V2"
    V3   = "V3"
    V4   = "V4"
    V5   = "V5"
    V6   = "V6"
    PLETH = "PLETH"
    ABP   = "ABP"
    PAP   = "PAP"
    ETCO2 = "ETCO2"

ALL_LEADS = list(LeadName)


# ─── Severity helper ──────────────────────────────────────────────────────────

RHYTHM_SEVERITY: dict[RhythmType, str] = {
    RhythmType.NSR:         "normal",
    RhythmType.SINUS_BRADY: "warning",
    RhythmType.SINUS_TACHY: "warning",
    RhythmType.AFIB:        "warning",
    RhythmType.AFLUTTER:    "warning",
    RhythmType.JUNCTIONAL:  "warning",
    RhythmType.AVB1:        "warning",
    RhythmType.AVB2_I:      "warning",
    RhythmType.AVB2_II:     "critical",
    RhythmType.AVB3:        "critical",
    RhythmType.PAC:         "warning",
    RhythmType.PVC:         "warning",
    RhythmType.SVT:         "critical",
    RhythmType.VT:          "critical",
    RhythmType.VF:          "critical",
    RhythmType.TORSADES:    "critical",
    RhythmType.ASYSTOLE:    "critical",
    RhythmType.PEA:         "critical",
    RhythmType.LBBB:        "warning",
    RhythmType.RBBB:        "warning",
    RhythmType.ANT_STEMI:   "critical",
    RhythmType.INF_STEMI:   "critical",
    RhythmType.LAT_STEMI:   "critical",
}


# ─── Central ECG State ─────────────────────────────────────────────────────────

class ECGState(BaseModel):
    """
    The single source of truth for the simulation engine.
    All engines (rhythm, waveform, lead, noise) read from this.
    The instructor console writes to this via WebSocket commands.
    """

    # Identity
    session_id: str = "default"

    # Rhythm
    rhythm: RhythmType    = RhythmType.NSR
    heart_rate: float     = Field(80.0, ge=0, le=300)    # bpm
    hrv_std: float        = Field(0.03, ge=0, le=0.5)    # RR stddev (fraction)

    # Conduction intervals (ms)
    pr_interval:   float  = Field(160.0, ge=80,  le=400)
    qrs_duration:  float  = Field(80.0,  ge=40,  le=200)
    qt_interval:   float  = Field(400.0, ge=200, le=700)

    # Pulse Oximetry
    spo2:          float  = Field(98.0, ge=0, le=100)

    # Arterial Blood Pressure
    sys_bp:        float  = Field(120.0, ge=0, le=300)
    dia_bp:        float  = Field(80.0, ge=0, le=200)

    # Pulmonary Artery Pressure
    pap_sys:       float  = Field(25.0, ge=0, le=120)
    pap_dia:       float  = Field(10.0, ge=0, le=80)

    # Capnography / ventilation
    etco2:         float  = Field(38.0, ge=0, le=100)
    resp_rate:     float  = Field(12.0, ge=0, le=80)

    # ST segment (mV)
    st_elevation:  float  = Field(0.0, ge=-2.0, le=5.0)
    st_depression: float  = Field(0.0, ge=-2.0, le=5.0)
    st_slope:      float  = Field(0.0)          # 0 = flat, + = upsloping, - = down

    # Ischemia & Conduction
    ischemia_zone:    IschemiaZone    = IschemiaZone.NONE
    conduction_state: ConductionState = ConductionState.NORMAL

    # Ectopy
    ectopy_rate: float = Field(0.0, ge=0, le=60)   # beats/min extra (PVC/PAC)

    # Artifacts
    artifact_level: float        = Field(0.0, ge=0, le=1.0)
    artifact_type:  ArtifactType = ArtifactType.NONE

    # Transfer
    transfer_time: float       = Field(5.0, ge=0, le=300)   # seconds
    transfer_fn:   TransferFn  = TransferFn.SIGMOID

    # Display
    lead_selection: LeadName = LeadName.II
    gain:           float    = Field(10.0)     # mm/mV
    paper_speed:    float    = Field(25.0)     # mm/s


class ECGStateUpdate(BaseModel):
    """Partial update sent from the instructor console."""
    rhythm:         RhythmType   | None = None
    heart_rate:     float        | None = Field(None, ge=0, le=300)
    spo2:           float        | None = Field(None, ge=0, le=100)
    sys_bp:         float        | None = Field(None, ge=0, le=300)
    dia_bp:         float        | None = Field(None, ge=0, le=200)
    pap_sys:        float        | None = Field(None, ge=0, le=120)
    pap_dia:        float        | None = Field(None, ge=0, le=80)
    etco2:          float        | None = Field(None, ge=0, le=100)
    resp_rate:      float        | None = Field(None, ge=0, le=80)
    pr_interval:    float        | None = None
    qrs_duration:   float        | None = None
    qt_interval:    float        | None = None
    st_elevation:   float        | None = None
    st_depression:  float        | None = None
    ischemia_zone:  IschemiaZone | None = None
    ectopy_rate:    float        | None = None
    artifact_level: float        | None = None
    artifact_type:  ArtifactType | None = None
    transfer_time:  float        | None = Field(None, ge=0, le=300)
    transfer_fn:    TransferFn   | None = None
    lead_selection: LeadName     | None = None
