"""
ingestion/role_assigner.py — Keyword Voting Engine
====================================================
Maps diarized speaker labels (SPEAKER_00, SPEAKER_01, …) to clinical roles
using keyword voting derived from all 7 synthetic ACLS scenarios.

Two modes:
  1. With diarization  — segments already have speaker_label field set
  2. Without diarization (keyword-only fallback) — all text treated as one pool;
     role assigned per segment individually based on utterance content alone

No external dependencies beyond the standard library.

Author: Deva
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Role keyword vocabulary
# Derived directly from all 7 synthetic scenario dialogues.
# Each keyword is a lowercase substring match — no regex needed.
# Order within each list does not matter; all matches score +1.
# =============================================================================

ROLE_KEYWORDS: dict[str, list[str]] = {
    "team_leader": [
        # ── Original synthetic scenario keywords ────────────────────────
        "start cpr",
        "give epinephrine",
        "charge to",
        "charge again",
        "shock now",
        "shock him",
        "shock once more",
        "resume cpr",
        "continue cpr",
        "stop compressions",
        "terminate resuscitation",
        "reversible causes",
        "hs and ts",
        "think about reversible",
        "prepare amiodarone",
        "give amiodarone",
        "advanced airway",
        "rosc achieved",
        "no shock",
        "give another",
        # ── Real audio — delegation commands ────────────────────────────
        "take over chest compression",      # Dr. Satish, take over chest compression
        "take over the airway",             # Dr. Anita, take over the airway
        "take care of monitor",             # Dr. Vijay, take care of monitor
        "take care of defibrillation",
        "get ready for defibrillation",     # Dr. Vijay, get ready for defibrillation
        "documents all the events",         # delegation to recorder
        "work as time keeper",
        # ── Real audio — rhythm check sequence ──────────────────────────
        "stop cpr",                         # Stop CPR, switch over, assess the rhythm
        "switch over",
        "assess the rhythm",
        # ── Real audio — drug ordering ──────────────────────────────────
        "load adrenaline",
        "load 1mg adrenaline",
        "give injection adrenaline",        # Sister, give injection adrenaline 1mg
        "next dose of adrenaline",          # Continue CPR, load next dose of adrenaline
        "secure iv",                        # Sister, secure IV cannula
        "secure iv canola",
        "iv canola",
        # ── Real audio — assessment orders ──────────────────────────────
        "check the lead",
        "check lead placement",
        "check carotid pulse",              # Dr. Vijay, check carotid pulse
        "check coveted pulse",              # Whisper mishears "carotid" as "coveted"
        "can you check the blood pressure",
        "check blood pressure",
        "check for the consciousness",
        "check consciousness",
        # ── Real audio — airway/ventilation orders ───────────────────────
        "one respiration every six seconds",
        "compression at 100",
        "prepare for advance airway",
        "prepare for advanced airway",
        # ── Real audio — post-ROSC ───────────────────────────────────────
        "return of spontaneous circulation",
        "shift the patient",
        "planning to shift",
        "inform code blue deactivation",
        "ventilator bed",
        "medical icu",
        "planning to shift the patient to medical icu",
    ],
    "compressor": [
        # ── Original synthetic scenario keywords ────────────────────────
        "starting compressions",
        "resuming compressions",
        "resuming cpr",
        "restarting compressions",
        "resume compressions",
        "resume cpr",
        "no pulse",
        "still no pulse",
        "stopping compressions",
        "switching compressor",
        "pulse present",
        "i can feel a pulse",
        "i can feel pulse",
        "continue compressions",
        # ── Real audio ──────────────────────────────────────────────────
        "checking carotid pulse",           # Checking carotid pulse, patient unresponsive
        "carotid pulse palpable",           # Carotid pulse palpable, volume is good
        "pulse palpable",
        "volume is good",
        "patient unresponsive",
        "activate the code blue",           # Sister, activate the code blue
    ],
    "defib_coach": [
        # ── Original synthetic scenario keywords ────────────────────────
        "charging",
        "charging to",
        "charging complete",
        "charge complete",
        "shock delivered",
        "clear",
        "looks like vf",
        "still vf",
        "rhythm still vf",
        "rhythm is vf",
        "pea",
        "asystole",
        "pulseless vt",
        "rhythm now",
        "rhythm looks like",
        "defibrillator connected",
        "defibrillator attached",
        "monitor connected",
        "pads not connected",
        "compression pause",
        "organized rhythm",
        "rhythm is",
        "what rhythm",
        "rhythm check",
        "rhythm unchanged",
        "resume compressions immediately",
        "resume cpr immediately",
        # ── Real audio ──────────────────────────────────────────────────
        "checking the rhythm",              # Stop CPR. Checking the rhythm
        "looks like ac",                    # Whisper: "looks like AC stool/stroll" = asystole
        "ac stool",                         # Whisper mishear of "asystole"
        "ac stroll",
        "looks like ventricular fibrillation",
        "ventricular fibrillation",
        "cardiac monitor is applied",       # Cardiac monitor is applied, sir
        "monitor is applied",
        "monitor applied",
        "lead checked",                     # Lead checked, sensitivity checked
        "sensitivity checked",
        "lead placement",
        "normal sinus rhythm",              # It is normal sinus rhythm
        "sinus rhythm",
        "nsr",
        "rate of 109",
        "200 joules selected",              # 200 joules selected, I am ready to give shock
        "ready to give shock",
        "i am clear",                       # I am clear, you are clear, everybody clear
        "everybody clear",
        "shock given",
    ],
    "iv_member": [
        # ── Original synthetic scenario keywords ────────────────────────
        "epinephrine given",
        "epinephrine administered",
        "epinephrine 1 mg given",
        "epinephrine 1 mg administered",
        "amiodarone given",
        "amiodarone administered",
        "amiodarone 300 mg given",
        "amiodarone 300 mg administered",
        "amiodarone 150 mg given",
        "saline flush",
        "flush given",
        "10 ml saline",
        "iv access",
        "iv fluids",
        "drug given",
        "medication given",
        # NOTE: "ready" removed — was causing defib phrases to mis-assign to iv_member
        # ── Real audio — drug administration reports ─────────────────────
        "adrenaline given",                 # Injection adrenaline, 1mg, IV given
        "adrenaline 1mg",
        "injection adrenaline",
        "iv given",                         # IV given
        "iv push",                          # 20ml NS IV push given
        "iv push given",
        "ns flush",
        "ns iv push",
        "20ml ns",
        "20cc",
        "cannula",
        "canola",                           # Whisper mishear of "cannula"
        "should we give adrenaline",
    ],
    "airway": [
        # ── Original synthetic scenario keywords ────────────────────────
        "bag mask",
        "bag-mask",
        "ventilation ongoing",
        "ventilation continuing",
        "airway looks patent",
        "airway",
        "intubation",
        "advanced airway secured",
        "no advanced airway",
        "possible hypoxia",
        "possible acidosis",
        "spo2",
        "etco2",
        "patient collapsed",
        "patient is unresponsive",
        "unresponsive",
        # ── Real audio ──────────────────────────────────────────────────
        "rescue breathing",                 # two rescue breathing after every 30 compressions
        "endotracheal intubation",
        "intubation done",
        "placement confirmed",              # Endotracheal intubation done and placement confirmed
        "tube placement",
        "take over the airway",             # Dr. Anita, take over the airway
    ],
    "recorder": [
        # ── Original synthetic scenario keywords ────────────────────────
        "documenting",
        "first shock at",
        "noted",
        "recorded",
        "multiple interruptions",
        "multiple prolonged interruptions",
        "bp not recordable",
        "spo2 not picking up",
        "transition from",
        "documented",
        "shock not delivered",
        "persistent pea despite",
        "ongoing vf",
        # ── Real audio ──────────────────────────────────────────────────
        "two minutes over",                 # Two minutes over, sir (time keeper)
        "2 minutes over",
        "time keeper",
        "timekeeper",
        "code blue was activated",          # The code blue was activated and CPR was initiated
        "cpr was initiated",
        "code blue deactivated",            # Code blue deactivated
        "code blue deactivation",
        "activated in",                     # Activated in A block, first floor...
        "bed number",                       # bed number 15
        "first floor",
        "male surgeon ward",
        "documents all the events",         # shared with team_leader — recorder says this
        "bp 130",                           # BP 130, 80 sir (vital sign reporting)
        "blood pressure",
        "four shocks delivered",
        "persistent pvt after",
    ],
}

# Display names for report output
ROLE_DISPLAY_NAMES: dict[str, str] = {
    "team_leader": "Team Leader",
    "compressor":  "Compressor",
    "defib_coach": "Defibrillator/CPR Coach",
    "iv_member":   "IV Member",
    "airway":      "Airway",
    "recorder":    "Recorder",
    "unknown":     "Unknown",
}

# Lapel overlap boost — added to team_leader score for the dominant lapel speaker
LAPEL_BOOST = 50

# Dual-role threshold — assign second role if score >= this fraction of top score
DUAL_ROLE_THRESHOLD = 0.60


# =============================================================================
# RoleAssigner
# =============================================================================

class RoleAssigner:
    """
    Assigns clinical roles to speaker labels using keyword voting.

    Usage — with diarization labels:
        assigner = RoleAssigner()
        role_map = assigner.assign(segments, lapel_timestamps=None)
        # role_map: {"SPEAKER_00": "team_leader", "SPEAKER_01": "compressor", ...}

    Usage — keyword-only fallback (no diarization):
        attributed = assigner.assign_per_segment(segments)
        # Returns same list with "role" field added to each segment dict.
    """

    def __init__(self):
        # Pre-compile all keywords as lowercase for fast matching
        self._keywords = {
            role: [kw.lower() for kw in kws]
            for role, kws in ROLE_KEYWORDS.items()
        }

    # ------------------------------------------------------------------
    # Public — diarized mode
    # ------------------------------------------------------------------

    def assign(
        self,
        segments: list[dict],
        lapel_timestamps: Optional[list[dict]] = None,
    ) -> dict[str, str]:
        """
        Given diarized segments (each with a "speaker_label" field),
        return a mapping of speaker_label → role string.

        Args:
            segments: List of segment dicts, each must have:
                      - "speaker_label": "SPEAKER_00" etc.
                      - "text": transcript text
                      - "timestamp_ms": int (used for tie-breaking by duration)
                      - "end_ms": int (used for tie-breaking by duration)
            lapel_timestamps: Optional list of lapel segment dicts with same format.
                              Speaker with most lapel overlap → +50 team_leader score.

        Returns:
            dict mapping speaker_label → role string, e.g.:
            {"SPEAKER_00": "team_leader", "SPEAKER_01": "compressor+defib_coach"}
        """
        if not segments:
            logger.warning("RoleAssigner.assign() called with empty segments list")
            return {}

        # Step 1 — Accumulate keyword scores per speaker
        scores = self._score_speakers(segments)

        # Step 2 — Apply lapel boost if lapel timestamps available
        if lapel_timestamps:
            dominant_lapel_speaker = self._find_lapel_dominant_speaker(
                segments, lapel_timestamps
            )
            if dominant_lapel_speaker and dominant_lapel_speaker in scores:
                scores[dominant_lapel_speaker]["team_leader"] = (
                    scores[dominant_lapel_speaker].get("team_leader", 0) + LAPEL_BOOST
                )
                logger.info(
                    f"Lapel boost +{LAPEL_BOOST} → {dominant_lapel_speaker} team_leader score"
                )

        # Step 3 — Compute speaking duration per speaker (for tie-breaking)
        durations = self._compute_durations(segments)

        # Step 4 — Winner-takes-all assignment
        role_map = self._assign_winners(scores, durations)

        # Step 5 — Detect and merge dual roles
        role_map = self._detect_dual_roles(scores, role_map)

        logger.info(f"Role assignment complete: {role_map}")
        return role_map

    def apply_role_map(
        self,
        segments: list[dict],
        role_map: dict[str, str],
    ) -> list[dict]:
        """
        Apply a role_map to a list of segments.
        Adds "role" and "speaker" (display name) fields to each segment.
        Segments without a matching speaker_label get role="unknown".
        """
        result = []
        for seg in segments:
            label = seg.get("speaker_label", "keyword_assigned")
            role = role_map.get(label, "unknown")
            result.append({
                **seg,
                "role": role,
                "speaker": self._display_name(role),
            })
        return result

    # ------------------------------------------------------------------
    # Public — keyword-only fallback (no diarization)
    # ------------------------------------------------------------------

    def assign_per_segment(self, segments: list[dict]) -> list[dict]:
        """
        Fallback mode: no speaker diarization available.
        Each segment is scored individually; the highest-scoring role
        for that segment's text is assigned.

        Returns same list with "role" and "speaker" fields added.
        Used when pyannote is unavailable and there is only one audio stream.
        """
        result = []
        for seg in segments:
            text = seg.get("text", "")
            seg_scores = self._score_text(text)
            if not seg_scores or max(seg_scores.values()) == 0:
                role = "unknown"
            else:
                role = max(seg_scores, key=lambda r: seg_scores[r])
            result.append({
                **seg,
                "role": role,
                "speaker": self._display_name(role),
                "speaker_label": seg.get("speaker_label", "keyword_assigned"),
            })
        logger.info(
            f"Per-segment keyword assignment complete — {len(result)} segments"
        )
        return result

    # ------------------------------------------------------------------
    # Internal — scoring
    # ------------------------------------------------------------------

    def _score_speakers(self, segments: list[dict]) -> dict[str, dict[str, int]]:
        """
        Returns scores[speaker_label][role] = total keyword hit count.
        """
        scores: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for seg in segments:
            label = seg.get("speaker_label", "UNKNOWN")
            text = seg.get("text", "")
            seg_scores = self._score_text(text)
            for role, count in seg_scores.items():
                scores[label][role] += count
        return {k: dict(v) for k, v in scores.items()}

    def _score_text(self, text: str) -> dict[str, int]:
        """
        Score a single text string against all role keyword lists.
        Returns {role: count} for all roles.
        """
        text_lower = text.lower()
        return {
            role: sum(1 for kw in kws if kw in text_lower)
            for role, kws in self._keywords.items()
        }

    def _compute_durations(self, segments: list[dict]) -> dict[str, int]:
        """
        Total speaking duration in ms per speaker.
        Used for tie-breaking: longest speaker → compressor, shortest → recorder.
        """
        durations: dict[str, int] = defaultdict(int)
        for seg in segments:
            label = seg.get("speaker_label", "UNKNOWN")
            start = seg.get("timestamp_ms", seg.get("start_ms", 0))
            end = seg.get("end_ms", start)
            durations[label] += max(0, end - start)
        return dict(durations)

    def _find_lapel_dominant_speaker(
        self,
        room_segments: list[dict],
        lapel_timestamps: list[dict],
    ) -> Optional[str]:
        """
        Find which room speaker has the most temporal overlap with lapel segments.
        Returns the speaker_label string of the dominant lapel speaker.
        """
        lapel_intervals = [
            (s.get("timestamp_ms", 0), s.get("end_ms", 0))
            for s in lapel_timestamps
        ]

        overlap_by_speaker: dict[str, int] = defaultdict(int)
        for seg in room_segments:
            label = seg.get("speaker_label", "UNKNOWN")
            seg_start = seg.get("timestamp_ms", 0)
            seg_end = seg.get("end_ms", seg_start)
            for lap_start, lap_end in lapel_intervals:
                overlap = max(
                    0,
                    min(seg_end, lap_end) - max(seg_start, lap_start)
                )
                overlap_by_speaker[label] += overlap

        if not overlap_by_speaker:
            return None
        return max(overlap_by_speaker, key=lambda k: overlap_by_speaker[k])

    # ------------------------------------------------------------------
    # Internal — winner assignment
    # ------------------------------------------------------------------

    def _assign_winners(
        self,
        scores: dict[str, dict[str, int]],
        durations: dict[str, int],
    ) -> dict[str, str]:
        """
        Winner-takes-all: for each role, the speaker with highest score wins.
        No two speakers assigned the same primary role.
        Tie-breaking:
          - "compressor" → longest-speaking speaker
          - "recorder"   → shortest-speaking speaker
          - others       → highest total keyword score
        """
        speakers = list(scores.keys())
        role_map: dict[str, str] = {s: "unknown" for s in speakers}
        assigned_speakers: set[str] = set()

        # Sort roles by priority (team_leader first — most critical)
        role_priority = [
            "team_leader", "defib_coach", "compressor",
            "iv_member", "airway", "recorder",
        ]

        for role in role_priority:
            # Candidates: speakers not yet assigned a role
            candidates = [
                s for s in speakers
                if s not in assigned_speakers
            ]
            if not candidates:
                break

            # Score for this role
            role_scores = {
                s: scores[s].get(role, 0) for s in candidates
            }
            max_score = max(role_scores.values(), default=0)

            if max_score == 0:
                # No keyword evidence for this role — use tie-breaking only for
                # positional roles where we can infer from speaking time
                if role == "compressor":
                    winner = max(candidates, key=lambda s: durations.get(s, 0))
                elif role == "recorder":
                    winner = min(candidates, key=lambda s: durations.get(s, 0))
                else:
                    continue  # leave as unknown if no evidence at all
            else:
                # Among tied highest scorers, apply tie-breaking
                tied = [s for s in candidates if role_scores[s] == max_score]
                if len(tied) == 1:
                    winner = tied[0]
                elif role == "compressor":
                    winner = max(tied, key=lambda s: durations.get(s, 0))
                elif role == "recorder":
                    winner = min(tied, key=lambda s: durations.get(s, 0))
                else:
                    # Highest total keyword score across all roles
                    winner = max(
                        tied,
                        key=lambda s: sum(scores[s].values())
                    )

            role_map[winner] = role
            assigned_speakers.add(winner)

        return role_map

    def _detect_dual_roles(
        self,
        scores: dict[str, dict[str, int]],
        role_map: dict[str, str],
    ) -> dict[str, str]:
        """
        If a speaker's second-highest role score is >= DUAL_ROLE_THRESHOLD
        fraction of their top score, AND that role is currently unassigned,
        merge both roles: "compressor+defib_coach".

        This handles real sessions where one person covers two roles.
        """
        assigned_roles = set(role_map.values()) - {"unknown"}
        result = dict(role_map)

        for speaker, primary_role in role_map.items():
            if primary_role == "unknown":
                continue

            spk_scores = scores.get(speaker, {})
            top_score = spk_scores.get(primary_role, 0)
            if top_score == 0:
                continue

            # Find second-best role for this speaker (excluding primary)
            other_roles = {
                r: s for r, s in spk_scores.items()
                if r != primary_role and s > 0
            }
            if not other_roles:
                continue

            second_role = max(other_roles, key=lambda r: other_roles[r])
            second_score = other_roles[second_role]

            if (
                second_score >= DUAL_ROLE_THRESHOLD * top_score
                and second_role not in assigned_roles
            ):
                merged = f"{primary_role}+{second_role}"
                result[speaker] = merged
                assigned_roles.add(second_role)
                logger.info(
                    f"Dual-role detected: {speaker} → {merged} "
                    f"(scores: {primary_role}={top_score}, {second_role}={second_score})"
                )

        return result

    # ------------------------------------------------------------------
    # Internal — formatting
    # ------------------------------------------------------------------

    def _display_name(self, role: str) -> str:
        """
        Convert role key to display name.
        Handles dual-role strings like "compressor+defib_coach".
        """
        if "+" in role:
            parts = role.split("+")
            return " + ".join(
                ROLE_DISPLAY_NAMES.get(p, p.replace("_", " ").title())
                for p in parts
            )
        return ROLE_DISPLAY_NAMES.get(role, role.replace("_", " ").title())
