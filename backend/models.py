"""Pydantic models, default state, and parameter-spec definition."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "student"


class TokenResponse(BaseModel):
    access_token: str
    role: str
    session_code: Optional[str] = None


# ── Session ───────────────────────────────────────────────────────
class EventLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event: str


class SessionCreate(BaseModel):
    pass


class SessionResponse(BaseModel):
    session_code: str
    is_active: bool
    started_at: datetime


class UpdateParameterRequest(BaseModel):
    field: str
    value: float | int | str | bool
    transfer_time_seconds: float = 0
    transfer_function: str = "immediate"  # immediate | linear | smooth


class UpdateRhythmRequest(BaseModel):
    rhythm: str
    extrasystole: str = "None"
    HR: float = 80.0
    ecg_lead: str = "II"
    artifact_electrical: str = "Off"
    artifact_muscular: str = "Off"
    emd_pea: bool = False


class UpdateEyesRequest(BaseModel):
    eyes_state: str
    eyes_look: str


# ── Monitor State ─────────────────────────────────────────────────
DEFAULT_MONITOR_STATE = {
    # Cardiac
    "HR": 80.0,
    "pulse_rate": 80.0,
    "rhythm": "Sinus Rhythm",
    "extrasystole": "None",
    "ecg_lead": "II",
    "artifact_electrical": "Off",
    "artifact_muscular": "Off",
    "emd_pea": False,

    # Blood Pressure
    "ABP_sys": 120.0,
    "ABP_dia": 80.0,
    "MAP": 93.0,
    "NBP_sys": 120.0,
    "NBP_dia": 80.0,
    "NBP_mean": 93.0,
    "coupled_bp": False,

    # Pulmonary
    "PAP_sys": 20.0,
    "PAP_dia": 10.0,
    "PAP_mean": 13.0,
    "PAP_wedge": 10.0,
    "CO": 5.0,

    # Respiratory
    "avRR": 14.0,
    "SpO2": 98.0,
    "etCO2": 35.0,
    "inCO2": 0.0,
    "etO2": 21.0,
    "inO2": 21.0,
    "etN2O": 0.0,
    "inN2O": 0.0,
    "cyanosis_start": 90.0,
    "cyanosis_severe": 70.0,

    # Temperature
    "Tperi": 37.0,
    "Tblood": 37.0,

    # Neuromuscular
    "TOF_pct": 100.0,
    "TOF_count": 4,

    # Eyes
    "eyes_state": "Closed",
    "eyes_look": "Normal",

    # Meta
    "alarms": [],
    "alarm_thresholds": {
        "HR": {"low": 50, "high": 120},
        "SpO2": {"low": 94, "high": 100},
        "ABP_sys": {"low": 90, "high": 160},
        "ABP_dia": {"low": 50, "high": 100},
        "etCO2": {"low": 30, "high": 50},
        "avRR": {"low": 8, "high": 30},
        "Tblood": {"low": 35, "high": 39},
    },
    # Visibility toggles
    "show_ecg": True,
    "show_hr": True,
    "show_spo2": True,
    "show_pleth": True,
    "show_resp": True,
    "show_rr": True,
    "show_nibp": True,
    "show_map": True,
    "show_temp": True,
    "show_etco2": True,
    "show_ibp": True,
    "show_cvp": True,

    # NIBP state
    "nibp_state": "IDLE",
    "nibp_interval": 0,
    "nibp_last_measured": "",

    "last_updated": None,
    "updated_by": "",
    "initial_readings_hidden": False,
}


# ── Parameter Spec ────────────────────────────────────────────────
# Drives all frontend controls dynamically: ranges, enums, types.
PARAMETER_SPEC = {
    # Cardiac
    "HR": {"type": "float", "min": 0, "max": 300, "step": 1, "unit": "bpm", "category": "Cardiac"},
    "pulse_rate": {"type": "float", "min": 0, "max": 300, "step": 1, "unit": "bpm", "category": "Cardiac"},
    "rhythm": {
        "type": "enum",
        "enum": [
            "Sinus Rhythm", "Sinus Tachycardia", "Sinus Bradycardia",
            "Atrial Fibrillation", "Atrial Flutter", "SVT",
            "Ventricular Tachycardia", "Ventricular Fibrillation",
            "Asystole", "Junctional Rhythm",
            "1st Degree AV Block", "2nd Degree AV Block", "3rd Degree AV Block",
            "Paced Rhythm",
        ],
        "category": "Cardiac",
    },
    "extrasystole": {
        "type": "enum",
        "enum": ["None", "PVC", "PAC", "Coupled PVC", "R-on-T"],
        "category": "Cardiac",
    },
    "ecg_lead": {
        "type": "enum",
        "enum": ["I", "II", "III", "aVR", "aVL", "aVF",
                 "V1", "V2", "V3", "V4", "V5", "V6"],
        "category": "Cardiac",
    },
    "artifact_electrical": {
        "type": "enum", "enum": ["Off", "50Hz", "60Hz"], "category": "Cardiac",
    },
    "artifact_muscular": {
        "type": "enum", "enum": ["Off", "Low", "Medium", "High"], "category": "Cardiac",
    },
    "emd_pea": {"type": "bool", "category": "Cardiac"},

    # Blood Pressure
    "ABP_sys": {"type": "float", "min": 0, "max": 300, "step": 1, "unit": "mmHg", "category": "Blood Pressure"},
    "ABP_dia": {"type": "float", "min": 0, "max": 200, "step": 1, "unit": "mmHg", "category": "Blood Pressure"},
    "MAP": {"type": "float", "min": 0, "max": 250, "step": 1, "unit": "mmHg", "category": "Blood Pressure"},
    "NBP_sys": {"type": "float", "min": 0, "max": 300, "step": 1, "unit": "mmHg", "category": "Blood Pressure"},
    "NBP_dia": {"type": "float", "min": 0, "max": 200, "step": 1, "unit": "mmHg", "category": "Blood Pressure"},
    "NBP_mean": {"type": "float", "min": 0, "max": 250, "step": 1, "unit": "mmHg", "category": "Blood Pressure"},
    "coupled_bp": {"type": "bool", "category": "Blood Pressure"},

    # Pulmonary
    "PAP_sys": {"type": "float", "min": 0, "max": 120, "step": 1, "unit": "mmHg", "category": "Pulmonary"},
    "PAP_dia": {"type": "float", "min": 0, "max": 80, "step": 1, "unit": "mmHg", "category": "Pulmonary"},
    "PAP_mean": {"type": "float", "min": 0, "max": 100, "step": 1, "unit": "mmHg", "category": "Pulmonary"},
    "PAP_wedge": {"type": "float", "min": 0, "max": 50, "step": 1, "unit": "mmHg", "category": "Pulmonary"},
    "CO": {"type": "float", "min": 0, "max": 20, "step": 0.1, "unit": "L/min", "category": "Pulmonary"},

    # Respiratory
    "avRR": {"type": "float", "min": 0, "max": 80, "step": 1, "unit": "/min", "category": "Respiratory"},
    "SpO2": {"type": "float", "min": 0, "max": 100, "step": 1, "unit": "%", "category": "Respiratory"},
    "etCO2": {"type": "float", "min": 0, "max": 150, "step": 1, "unit": "mmHg", "category": "Respiratory"},
    "inCO2": {"type": "float", "min": 0, "max": 50, "step": 1, "unit": "mmHg", "category": "Respiratory"},
    "etO2": {"type": "float", "min": 0, "max": 100, "step": 1, "unit": "%", "category": "Respiratory"},
    "inO2": {"type": "float", "min": 0, "max": 100, "step": 1, "unit": "%", "category": "Respiratory"},
    "etN2O": {"type": "float", "min": 0, "max": 100, "step": 1, "unit": "%", "category": "Respiratory"},
    "inN2O": {"type": "float", "min": 0, "max": 100, "step": 1, "unit": "%", "category": "Respiratory"},
    "cyanosis_start": {"type": "float", "min": 70, "max": 100, "step": 1, "unit": "%", "category": "Respiratory"},
    "cyanosis_severe": {"type": "float", "min": 40, "max": 90, "step": 1, "unit": "%", "category": "Respiratory"},

    # Temperature
    "Tperi": {"type": "float", "min": 15, "max": 45, "step": 0.1, "unit": "C", "category": "Temperature"},
    "Tblood": {"type": "float", "min": 20, "max": 43, "step": 0.1, "unit": "C", "category": "Temperature"},

    # Neuromuscular
    "TOF_pct": {"type": "float", "min": 0, "max": 100, "step": 1, "unit": "%", "category": "Neuromuscular"},
    "TOF_count": {"type": "int", "min": 0, "max": 4, "step": 1, "unit": "", "category": "Neuromuscular"},

    # Eyes
    "eyes_state": {
        "type": "enum",
        "enum": ["Open", "Closed", "Squinting", "Dilated"],
        "category": "Eyes",
    },
    "eyes_look": {
        "type": "enum",
        "enum": ["Normal", "Left", "Right", "Up", "Down", "Crossed", "Deviated"],
        "category": "Eyes",
    },
}
