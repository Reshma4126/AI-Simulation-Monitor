"""
scenarios/generator.py — ScenarioGenerator
===========================================
Generates structured clinical scenarios parameterized by:
  • level      : beginner | intermediate | advanced
  • location   : ER | ICU | Theatre | Ward_Medical | Ward_Surgical |
                  Ward_Ortho | Ward_Neuro | Ward_Cardio
  • discipline : list of doctor | nurse | physiotherapist | allied
  • speciality : ER | ICU | Anaesthesia | Cardio | Neuro | Trauma |
                  Ortho | Surgery | Medicine | Allied_Medical | Allied_Surgical

Output: ScenarioSpec dict — ready for OutcomePredictor, VoiceNarrator, and
        the frontend Scenario Studio panel.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE         = Path(__file__).parent
_LIBRARY_PATH = _HERE / "library.json"

# ── Difficulty multipliers for XP calculation ─────────────────────────────────
_XP_BASE = {
    "beginner":     200,
    "intermediate": 400,
    "advanced":     700,
}

# ── Location resource profiles ────────────────────────────────────────────────
_LOCATION_RESOURCES: Dict[str, dict] = {
    "ER": {
        "label":              "Emergency Room",
        "icon":               "🚨",
        "crash_cart":         True,
        "defibrillator":      True,
        "ventilator":         True,
        "advanced_airway":    True,
        "iv_access_ready":    True,
        "team_size_range":    (4, 6),
        "response_delay_sec": 0,
        "context_note":       "Full crash-cart available. No delay in resources.",
    },
    "ICU": {
        "label":              "Intensive Care Unit",
        "icon":               "💉",
        "crash_cart":         True,
        "defibrillator":      True,
        "ventilator":         True,
        "advanced_airway":    True,
        "iv_access_ready":    True,
        "team_size_range":    (3, 5),
        "response_delay_sec": 0,
        "context_note":       "Patient already on monitoring. Arterial line in situ.",
    },
    "Theatre": {
        "label":              "Operating Theatre",
        "icon":               "🏥",
        "crash_cart":         True,
        "defibrillator":      True,
        "ventilator":         True,
        "advanced_airway":    True,
        "iv_access_ready":    True,
        "team_size_range":    (4, 6),
        "response_delay_sec": 0,
        "context_note":       "Anaesthetic machine available. Intraoperative context.",
    },
    "Ward_Medical": {
        "label":              "Medical Ward",
        "icon":               "🛏️",
        "crash_cart":         False,
        "defibrillator":      False,
        "ventilator":         False,
        "advanced_airway":    False,
        "iv_access_ready":    False,
        "team_size_range":    (2, 4),
        "response_delay_sec": 120,
        "context_note":       "Basic crash bag only. Crash cart arrives in ~2 minutes.",
    },
    "Ward_Surgical": {
        "label":              "Surgical Ward",
        "icon":               "🔪",
        "crash_cart":         False,
        "defibrillator":      False,
        "ventilator":         False,
        "advanced_airway":    False,
        "iv_access_ready":    True,
        "team_size_range":    (2, 4),
        "response_delay_sec": 90,
        "context_note":       "Post-operative patient. IV access established. Crash cart ~90 s away.",
    },
    "Ward_Ortho": {
        "label":              "Orthopaedic Ward",
        "icon":               "🦴",
        "crash_cart":         False,
        "defibrillator":      False,
        "ventilator":         False,
        "advanced_airway":    False,
        "iv_access_ready":    True,
        "team_size_range":    (2, 3),
        "response_delay_sec": 120,
        "context_note":       "Post-ortho surgery. Fat embolism risk. Crash cart ~2 minutes.",
    },
    "Ward_Neuro": {
        "label":              "Neurology Ward",
        "icon":               "🧠",
        "crash_cart":         False,
        "defibrillator":      False,
        "ventilator":         False,
        "advanced_airway":    False,
        "iv_access_ready":    True,
        "team_size_range":    (2, 4),
        "response_delay_sec": 120,
        "context_note":       "Anticoagulation risk. Known seizure history possible. Crash cart ~2 minutes.",
    },
    "Ward_Cardio": {
        "label":              "Cardiology Ward",
        "icon":               "❤️",
        "crash_cart":         True,
        "defibrillator":      True,
        "ventilator":         False,
        "advanced_airway":    False,
        "iv_access_ready":    True,
        "team_size_range":    (3, 5),
        "response_delay_sec": 30,
        "context_note":       "Defibrillator immediately available. Telemetry monitoring in room.",
    },
}

# ── Speciality context modifiers ──────────────────────────────────────────────
_SPECIALITY_CONTEXT: Dict[str, dict] = {
    "ER":              {"label": "Emergency",       "patient_history": "Unknown — brought by ambulance"},
    "ICU":             {"label": "Intensive Care",  "patient_history": "Critically ill, multi-organ monitoring"},
    "Anaesthesia":     {"label": "Anaesthesia",     "patient_history": "Intraoperative, general anaesthesia"},
    "Cardio":          {"label": "Cardiology",      "patient_history": "Known CAD, previous MI, on antiplatelets"},
    "Neuro":           {"label": "Neurology",       "patient_history": "Recent stroke, on anticoagulants"},
    "Trauma":          {"label": "Trauma",          "patient_history": "Polytrauma, RTA mechanism"},
    "Ortho":           {"label": "Orthopaedics",    "patient_history": "Post-arthroplasty, DVT prophylaxis"},
    "Surgery":         {"label": "General Surgery", "patient_history": "Post-abdominal surgery, NGT in situ"},
    "Medicine":        {"label": "General Medicine","patient_history": "Sepsis workup, multiple comorbidities"},
    "Allied_Medical":  {"label": "Allied Medical",  "patient_history": "Rehab patient, physiotherapy session"},
    "Allied_Surgical": {"label": "Allied Surgical", "patient_history": "Post-surgical rehab, drain in situ"},
}

# ── Discipline role labels ────────────────────────────────────────────────────
_DISCIPLINE_LABELS = {
    "doctor":          "Physician / Registrar",
    "nurse":           "Staff Nurse / Charge Nurse",
    "physiotherapist": "Physiotherapist",
    "allied":          "Allied Health Professional",
}


class ScenarioGenerator:
    """
    Generate a clinical scenario specification.

    Example
    -------
    gen = ScenarioGenerator()
    spec = gen.generate(
        level="advanced",
        location="ICU",
        discipline=["doctor", "nurse"],
        speciality="Cardio",
    )
    """

    def __init__(self):
        self._library = self._load_library()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        level:      str,
        location:   str,
        discipline: List[str],
        speciality: str,
        seed:       Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate and return a ScenarioSpec dict.

        Parameters
        ----------
        level       : 'beginner' | 'intermediate' | 'advanced'
        location    : one of the keys in _LOCATION_RESOURCES
        discipline  : non-empty list of role strings
        speciality  : one of the keys in _SPECIALITY_CONTEXT
        seed        : optional random seed for reproducibility

        Returns
        -------
        ScenarioSpec dict — see _build_spec for structure.
        """
        if seed is not None:
            random.seed(seed)

        level      = level.lower()
        location   = location.strip()
        speciality = speciality.strip()

        if level not in _XP_BASE:
            level = "beginner"
        if location not in _LOCATION_RESOURCES:
            location = "ER"
        if speciality not in _SPECIALITY_CONTEXT:
            speciality = "ER"

        template = self._pick_template(level, location, speciality)
        spec     = self._build_spec(template, level, location, discipline, speciality)
        return spec

    def list_levels(self) -> List[str]:
        return ["beginner", "intermediate", "advanced"]

    def list_locations(self) -> Dict[str, dict]:
        return {k: {"label": v["label"], "icon": v["icon"]} for k, v in _LOCATION_RESOURCES.items()}

    def list_specialities(self) -> Dict[str, str]:
        return {k: v["label"] for k, v in _SPECIALITY_CONTEXT.items()}

    # ── Template selection ────────────────────────────────────────────────────

    def _load_library(self) -> List[dict]:
        if not _LIBRARY_PATH.exists():
            return []
        with open(_LIBRARY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("templates", [])

    def _pick_template(self, level: str, location: str, speciality: str) -> dict:
        """Pick best-matching template from library; fall back gracefully."""
        # Exact match first
        for t in self._library:
            tags = t.get("tags", {})
            if (tags.get("level") == level
                    and speciality in tags.get("specialities", [])
                    and (not tags.get("locations") or location in tags.get("locations", []))):
                return t

        # Relax location constraint
        for t in self._library:
            tags = t.get("tags", {})
            if tags.get("level") == level and speciality in tags.get("specialities", []):
                return t

        # Relax speciality — same level only
        candidates = [t for t in self._library if t.get("tags", {}).get("level") == level]
        if candidates:
            return random.choice(candidates)

        # Final fallback — any template
        if self._library:
            return random.choice(self._library)

        return self._default_template(level)

    def _default_template(self, level: str) -> dict:
        """Hard-coded fallback when library.json is empty."""
        rhythms = {
            "beginner":     {"type": "VF", "label": "Ventricular Fibrillation"},
            "intermediate": {"type": "PEA_to_VF", "label": "PEA transitioning to VF"},
            "advanced":     {"type": "megacode", "label": "Megacode — mixed rhythms"},
        }
        r = rhythms.get(level, rhythms["beginner"])
        return {
            "template_id": "DEFAULT",
            "title":       f"Default {r['label']} Scenario",
            "rhythm_type": r["type"],
            "tags":        {"level": level, "specialities": [], "locations": []},
            "patient": {
                "age_range":    [40, 70],
                "sex_options":  ["Male", "Female"],
                "weight_range": [60, 90],
                "presentation": "Sudden collapse",
            },
            "complications": [],
            "hints": ["Check pulse.", "Start CPR.", "Attach defibrillator."],
            "checklist": [
                {"action": "Recognise arrest",            "window_sec": 15,  "critical": True},
                {"action": "Start CPR",                   "window_sec": 30,  "critical": True},
                {"action": "Attach defibrillator",        "window_sec": 120, "critical": True},
                {"action": "Rhythm analysis",             "window_sec": 180, "critical": True},
                {"action": "First shock (if shockable)",  "window_sec": 180, "critical": True},
                {"action": "Resume CPR immediately",      "window_sec": 195, "critical": True},
                {"action": "Epinephrine 1 mg",            "window_sec": 300, "critical": False},
                {"action": "Consider reversible causes",  "window_sec": 360, "critical": False},
            ],
            "estimated_duration_min": {"beginner": 8, "intermediate": 12, "advanced": 18}.get(level, 10),
        }

    # ── Spec builder ──────────────────────────────────────────────────────────

    def _build_spec(
        self,
        template:   dict,
        level:      str,
        location:   str,
        discipline: List[str],
        speciality: str,
    ) -> Dict[str, Any]:
        loc    = _LOCATION_RESOURCES[location]
        spec_c = _SPECIALITY_CONTEXT[speciality]
        pt     = template.get("patient", {})

        # Patient demographics
        age    = random.randint(*pt.get("age_range", [40, 70]))
        sex    = random.choice(pt.get("sex_options", ["Male", "Female"]))
        weight = random.randint(*pt.get("weight_range", [60, 90]))

        # Complications — only Intermediate / Advanced
        complications = []
        if level in ("intermediate", "advanced") and template.get("complications"):
            n = 1 if level == "intermediate" else min(2, len(template["complications"]))
            complications = random.sample(template["complications"], n)

        # Hints — only Beginner
        hints = template.get("hints", []) if level == "beginner" else []

        # XP reward
        base_xp      = _XP_BASE[level]
        complication_bonus = len(complications) * 50
        xp_reward    = base_xp + complication_bonus

        # Difficulty score 1–10
        difficulty_score = {"beginner": 3, "intermediate": 6, "advanced": 9}[level]
        if loc["response_delay_sec"] > 0:
            difficulty_score = min(10, difficulty_score + 1)
        if complications:
            difficulty_score = min(10, difficulty_score + 1)

        # Team composition
        ts_min, ts_max  = loc["team_size_range"]
        team_size       = random.randint(ts_min, ts_max)
        discipline_roles = [_DISCIPLINE_LABELS.get(d, d) for d in discipline]

        # Narration intro text (spoken by AI voice narrator)
        intro_text = self._build_intro(
            template, level, location, speciality, age, sex, weight,
            spec_c, loc, complications,
        )

        return {
            "scenario_id":       f"SCN-{uuid.uuid4().hex[:8].upper()}",
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "level":             level,
            "location":          location,
            "location_label":    loc["label"],
            "location_icon":     loc["icon"],
            "speciality":        speciality,
            "speciality_label":  spec_c["label"],
            "discipline":        discipline,
            "discipline_labels": discipline_roles,

            # Patient
            "patient": {
                "age":           age,
                "sex":           sex,
                "weight_kg":     weight,
                "history":       spec_c["patient_history"],
                "presentation":  pt.get("presentation", "Sudden collapse"),
            },

            # Rhythm & clinical context
            "rhythm_type":    template.get("rhythm_type", "VF"),
            "title":          template.get("title", "Clinical Scenario"),
            "complications":  complications,

            # Resources
            "resources": {
                "crash_cart":         loc["crash_cart"],
                "defibrillator":      loc["defibrillator"],
                "ventilator":         loc["ventilator"],
                "advanced_airway":    loc["advanced_airway"],
                "iv_access_ready":    loc["iv_access_ready"],
                "response_delay_sec": loc["response_delay_sec"],
                "context_note":       loc["context_note"],
            },

            # Team
            "team_size":  team_size,
            "team_roles": discipline_roles,

            # Learning
            "checklist":  template.get("checklist", self._default_template(level)["checklist"]),
            "hints":      hints,

            # Gamification
            "difficulty_score": difficulty_score,
            "xp_reward":        xp_reward,

            # Timing
            "estimated_duration_min": template.get("estimated_duration_min", {}).get(level, 10)
                                       if isinstance(template.get("estimated_duration_min"), dict)
                                       else template.get("estimated_duration_min", 10),

            # Narration
            "narration_intro": intro_text,
        }

    def _build_intro(
        self,
        template:      dict,
        level:         str,
        location:      str,
        speciality:    str,
        age:           int,
        sex:           str,
        weight:        int,
        spec_c:        dict,
        loc:           dict,
        complications: list,
    ) -> str:
        level_labels = {
            "beginner":     "Beginner",
            "intermediate": "Intermediate",
            "advanced":     "Advanced",
        }
        comp_text = ""
        if complications:
            comp_text = " Be aware: there are additional complications in this case."

        intro = (
            f"Attention team. This is a {level_labels[level]}-level scenario "
            f"set in the {loc['label']}. "
            f"Your patient is a {age}-year-old {sex}, weighing {weight} kilograms. "
            f"History: {spec_c['patient_history']}. "
            f"Presentation: {template.get('patient', {}).get('presentation', 'sudden collapse')}. "
            f"{loc['context_note']}"
            f"{comp_text} "
            f"You may begin."
        )
        return intro
