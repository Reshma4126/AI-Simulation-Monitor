"""
scenarios/outcome_predictor.py — Outcome Predictor
===================================================
Takes a ScenarioSpec and predicts what a perfectly-performing team should do.
After a session, compares actual ACLS findings against the prediction and
returns a prediction accuracy score (0–100).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OutcomePredictor:
    """
    Pre-session: build ExpectedOutcome from ScenarioSpec.
    Post-session: score actual findings against ExpectedOutcome.

    Usage
    -----
    predictor = OutcomePredictor()

    # Before scenario runs
    expected = predictor.build_expected(scenario_spec)

    # After pipeline completes
    result = predictor.score_against_findings(expected, acls_findings, score_report)
    """

    # ── Pre-session ───────────────────────────────────────────────────────────

    def build_expected(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build an ExpectedOutcome dict from a ScenarioSpec.

        Fields
        ------
        checklist_items   : ordered list of {action, window_sec, critical}
        predicted_outcome : 'ROSC' | 'Termination' | 'Stabilised'
        danger_zones      : list of time windows where deviation is likely
        level             : difficulty level string
        """
        checklist = spec.get("checklist", [])
        level     = spec.get("level", "beginner")

        # Predict likely outcome based on level + rhythm
        rhythm = spec.get("rhythm_type", "VF")
        predicted_outcome = self._predict_outcome(rhythm, level)

        # Identify danger zones (times where teams commonly deviate)
        danger_zones = self._identify_danger_zones(checklist, level, rhythm)

        return {
            "scenario_id":       spec.get("scenario_id", ""),
            "level":             level,
            "rhythm_type":       rhythm,
            "checklist_items":   checklist,
            "predicted_outcome": predicted_outcome,
            "danger_zones":      danger_zones,
            "difficulty_score":  spec.get("difficulty_score", 5),
            "xp_reward":         spec.get("xp_reward", 400),
        }

    def _predict_outcome(self, rhythm: str, level: str) -> str:
        """Simple heuristic: beginner + VF → high ROSC chance."""
        shockable = rhythm in ("VF", "pVT", "PEA_to_VF", "asystole_to_pVT")
        if level == "beginner":
            return "ROSC" if shockable else "Termination"
        elif level == "intermediate":
            return "ROSC" if shockable else "Termination"
        else:
            return "Partial ROSC" if shockable else "Termination"

    def _identify_danger_zones(
        self,
        checklist: List[dict],
        level:     str,
        rhythm:    str,
    ) -> List[dict]:
        """Return time windows where deviation is historically common."""
        zones = []
        for item in checklist:
            if not item.get("critical"):
                continue
            ws = item.get("window_sec", 0)
            zones.append({
                "action":      item["action"],
                "at_sec":      ws,
                "risk_label":  self._risk_label(item["action"], level),
            })
        return zones[:5]  # top 5 danger zones

    def _risk_label(self, action: str, level: str) -> str:
        action_lower = action.lower()
        if "shock" in action_lower or "defib" in action_lower:
            return "Delayed or missed defibrillation" if level != "beginner" else "Ensure shock timing < 3 min"
        if "cpr" in action_lower or "compression" in action_lower:
            return "CPR quality degradation"
        if "epinephrine" in action_lower or "adrenaline" in action_lower:
            return "Medication timing error"
        if "airway" in action_lower:
            return "Airway management delay"
        return "Protocol deviation risk"

    # ── Post-session ──────────────────────────────────────────────────────────

    def score_against_findings(
        self,
        expected:     Dict[str, Any],
        acls_findings: List[dict],
        score_report:  Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Compare actual findings against the expected checklist.

        Parameters
        ----------
        expected      : output of build_expected()
        acls_findings : list of finding dicts from ACLSEngine.evaluate()
        score_report  : optional ScoringReport object for overall_score

        Returns
        -------
        {
          "prediction_accuracy": 0–100,
          "checklist_hit_rate":  0–100,
          "critical_misses":     [...],
          "performed_correctly": [...],
          "xp_earned":           int,
          "grade":               str,
        }
        """
        checklist     = expected.get("checklist_items", [])
        critical_items = [c for c in checklist if c.get("critical")]
        deviation_titles = {f.get("title", "").lower() for f in acls_findings}

        # Map checklist actions to deviation titles for matching
        critical_misses  = []
        performed_correctly = []

        for item in critical_items:
            action_lower = item["action"].lower()
            missed = self._action_was_missed(action_lower, deviation_titles)
            if missed:
                critical_misses.append(item["action"])
            else:
                performed_correctly.append(item["action"])

        total_critical = len(critical_items)
        hits           = total_critical - len(critical_misses)
        hit_rate       = round((hits / total_critical * 100) if total_critical else 100, 1)

        # Prediction accuracy = weighted combo of hit_rate + overall score
        overall = getattr(score_report, "overall_score", hit_rate) if score_report else hit_rate
        pred_accuracy = round((hit_rate * 0.6 + overall * 0.4), 1)

        # XP calculation
        base_xp = expected.get("xp_reward", 400)
        xp_earned = self._calc_xp(base_xp, pred_accuracy, len(acls_findings), expected.get("level"))

        # Grade
        grade = self._grade(pred_accuracy)

        return {
            "prediction_accuracy": pred_accuracy,
            "checklist_hit_rate":  hit_rate,
            "critical_misses":     critical_misses,
            "performed_correctly": performed_correctly,
            "xp_earned":           xp_earned,
            "grade":               grade,
            "total_deviations":    len(acls_findings),
        }

    def _action_was_missed(self, action_lower: str, deviation_titles: set) -> bool:
        """Heuristic: check if any deviation title implies this action was missed."""
        keywords = action_lower.split()
        for dev in deviation_titles:
            matches = sum(1 for kw in keywords if kw in dev)
            if matches >= min(2, len(keywords)):
                return True
        return False

    def _calc_xp(
        self, base_xp: int, accuracy: float, deviation_count: int, level: Optional[str]
    ) -> int:
        level_multiplier = {"beginner": 1.0, "intermediate": 1.5, "advanced": 2.0}.get(level or "", 1.0)
        deviation_penalty = min(deviation_count * 10, base_xp * 0.5)
        accuracy_bonus    = base_xp * (accuracy / 100) * 0.3
        xp = int((base_xp - deviation_penalty + accuracy_bonus) * level_multiplier)
        return max(0, xp)

    def _grade(self, score: float) -> str:
        if score >= 90: return "A"
        if score >= 80: return "B"
        if score >= 70: return "C"
        if score >= 60: return "D"
        return "F"
