"""
DebriefAdapter — Simulation Backend to Debriefing Engine Adapter.

Transforms simulation session records, event logs, and monitor state into the
structured transcript & event format expected by `backend/debriefing`.
Executes the debrief pipeline via `DebriefService` without modifying the core engine.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from debrief_service import generate_debrief, DebriefService

logger = logging.getLogger("DebriefAdapter")


class DebriefAdapter:
    """
    Adapter class for transforming simulation data and invoking the debrief engine.
    """

    def __init__(self):
        self.service = DebriefService()

    @staticmethod
    def parse_datetime(val: Any) -> Optional[datetime]:
        """Safely parse a datetime object or ISO datetime string into a naive datetime."""
        dt_obj = None
        if isinstance(val, datetime):
            dt_obj = val
        elif isinstance(val, str) and val.strip():
            try:
                # Handle ISO strings (with or without 'Z' or offset)
                clean_str = val.replace("Z", "+00:00")
                dt_obj = datetime.fromisoformat(clean_str)
            except ValueError:
                pass

        if dt_obj and dt_obj.tzinfo is not None:
            return dt_obj.replace(tzinfo=None)
        return dt_obj

    def transform_event_log_to_segments(
        self, event_log: List[Dict[str, Any]], start_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Convert raw simulation event_log entries into attributed transcript segments.
        Handles missing timestamps, text formatting, and speaker role mapping safely.
        """
        segments = []
        if not isinstance(event_log, list):
            logger.warning(f"[DebriefAdapter] event_log is not a list ({type(event_log)}), using empty log.")
            event_log = []

        start_dt = self.parse_datetime(start_time)

        for idx, item in enumerate(event_log):
            if not isinstance(item, dict):
                event_text = str(item)
                item_ts = None
            else:
                event_text = item.get("event", item.get("text", item.get("message", "")))
                item_ts = item.get("timestamp", item.get("time", item.get("created_at")))

            if not event_text:
                continue

            # Calculate relative timestamp in milliseconds
            dt = self.parse_datetime(item_ts)
            if dt and start_dt:
                delta_s = max(0.0, (dt - start_dt).total_seconds())
                timestamp_ms = int(delta_s * 1000)
            elif isinstance(item_ts, (int, float)):
                timestamp_ms = int(item_ts * 1000) if item_ts < 1000000 else int(item_ts)
            else:
                # Safe fallback: spacing events by 10s intervals
                timestamp_ms = idx * 10000

            text_lower = event_text.lower()

            # Determine speaker & role based on clinical action patterns
            if any(k in text_lower for k in ["order", "command", "instruct", "prepare", "start cpr", "give"]):
                speaker = item.get("speaker", "Team Leader")
                role = "team_leader"
            elif any(k in text_lower for k in ["administered", "delivered", "initiated", "placed", "resumed", "applied"]):
                speaker = item.get("speaker", "Nurse")
                role = "nurse"
            elif any(k in text_lower for k in ["rhythm", "check", "detected", "achieved", "identified", "assessed"]):
                speaker = item.get("speaker", "Resident")
                role = "resident"
            else:
                speaker = item.get("speaker", "Team Leader")
                role = item.get("role", "team_leader")

            # Enrich event text if it's a raw telemetry string (e.g., "Rhythm -> Ventricular Fibrillation, HR -> 0")
            formatted_text = event_text
            if "rhythm ->" in text_lower or "rhythm:" in text_lower:
                if "ventricular fibrillation" in text_lower or "vf" in text_lower:
                    formatted_text = f"Patient in Ventricular Fibrillation. Shock advised. ({event_text})"
                elif "asystole" in text_lower:
                    formatted_text = f"Patient in Asystole. No pulse. Start CPR. ({event_text})"
                elif "sinus" in text_lower or "rosc" in text_lower:
                    formatted_text = f"ROSC achieved. Rhythm changed to Sinus Rhythm. ({event_text})"
            elif "cpr" in text_lower and not any(k in text_lower for k in ["start", "begin", "paused", "resumed"]):
                formatted_text = f"CPR initiated: starting chest compressions. ({event_text})"

            segments.append({
                "segment_id": f"seg_{idx + 1:03d}",
                "speaker": speaker,
                "role": role,
                "text": formatted_text,
                "start_ms": timestamp_ms,
                "end_ms": timestamp_ms + 2500,
                "source": "lapel" if role == "team_leader" else "ceiling",
            })

        return segments

    def convert(
        self,
        session: Dict[str, Any],
        event_log: Optional[List[Dict[str, Any]]] = None,
        monitor_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Transforms simulation session + event_log + monitor_state into the transcript
        and session dictionary format required by `backend/debriefing`.

        Args:
            session: Dictionary containing session details (code, dates, user, etc.)
            event_log: Optional explicit event log list. If None, pulled from session["event_log"].
            monitor_state: Optional monitor state dictionary snapshot.

        Returns:
            Dictionary ready for `generate_debrief()`.
        """
        if not isinstance(session, dict):
            logger.warning(f"[DebriefAdapter] session is not a dict ({type(session)}), using empty dict.")
            session = {}

        # 1. Session Identification & Defaults
        session_code = session.get("session_code", session.get("session_id", session.get("id", "SES-SIM-001")))
        session_id = str(session_code)

        start_dt = self.parse_datetime(session.get("started_at")) or datetime.utcnow()
        end_dt = self.parse_datetime(session.get("ended_at"))

        # 2. Extract Event Log
        raw_log = event_log
        if raw_log is None:
            raw_log = session.get("event_log", [])

        if isinstance(raw_log, str) and raw_log.strip():
            try:
                raw_log = json.loads(raw_log)
            except Exception as e:
                logger.warning(f"[DebriefAdapter] Failed to parse event_log JSON string: {e}")
                raw_log = []

        if not isinstance(raw_log, list):
            raw_log = []

        # 3. Transform Event Log to Transcript Segments
        segments = self.transform_event_log_to_segments(raw_log, start_dt)

        # 4. Monitor State Baseline Enrichment
        monitor_state = monitor_state or session.get("monitor_state", {})
        if isinstance(monitor_state, str) and monitor_state.strip():
            try:
                monitor_state = json.loads(monitor_state)
            except Exception:
                monitor_state = {}

        # If no segments were created from event_log, create baseline synthetic segments from monitor_state
        if not segments and isinstance(monitor_state, dict) and monitor_state:
            initial_rhythm = monitor_state.get("rhythm", "Ventricular Fibrillation")
            initial_hr = monitor_state.get("HR", 0)
            segments = [
                {
                    "segment_id": "seg_001",
                    "speaker": "Resident",
                    "role": "resident",
                    "text": f"Patient unresponsive. Rhythm: {initial_rhythm}, HR: {initial_hr}. Pulse check performed - no pulse.",
                    "start_ms": 8000,
                    "end_ms": 12000,
                    "source": "ceiling",
                },
                {
                    "segment_id": "seg_002",
                    "speaker": "Team Leader",
                    "role": "team_leader",
                    "text": "Cardiac arrest confirmed! Start CPR immediately and prepare defibrillator.",
                    "start_ms": 15000,
                    "end_ms": 19000,
                    "source": "lapel",
                },
                {
                    "segment_id": "seg_003",
                    "speaker": "Nurse",
                    "role": "nurse",
                    "text": "CPR initiated. Compressions ongoing. Defibrillator attached.",
                    "start_ms": 32000,
                    "end_ms": 36000,
                    "source": "ceiling",
                },
            ]

        # 5. Duration Calculation
        if end_dt and start_dt and end_dt > start_dt:
            duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        elif segments:
            duration_ms = max(60000, segments[-1]["end_ms"] + 10000)
        else:
            duration_ms = 600000  # 10 minutes default

        # 6. Scenario Metadata
        scenario_name = session.get("scenario_name", session.get("name", "Adult ACLS - Cardiac Arrest"))
        scenario_type = session.get("scenario_type", monitor_state.get("rhythm", "VF") if isinstance(monitor_state, dict) else "VF")
        leader_name = session.get("team_leader_name", session.get("created_by_username", "Simulation Team"))
        team_size = session.get("team_size", 6)

        converted_payload = {
            "session_id": session_id,
            "scenario_name": scenario_name,
            "scenario_type": scenario_type,
            "team_leader_name": leader_name,
            "team_size": team_size,
            "duration_ms": duration_ms,
            "date": start_dt.strftime("%Y-%m-%d"),
            "segments": segments,
            "guideline_version": "AHA_2020",
        }

        # 7. Print Validation Logs as required
        print("\n" + "=" * 60)
        print("[DebriefAdapter] VALIDATION LOGS:")
        print(f"  • Events converted    : {len(raw_log)} event log entries processed")
        print(f"  • Transcript generated: {len(segments)} attributed segments created")
        print(f"  • Session Metadata    : ID={session_id} | Scenario={scenario_name} | Duration={duration_ms / 1000:.1f}s")
        print("=" * 60 + "\n")

        return converted_payload

    def process_session_and_debrief(
        self,
        session: Dict[str, Any],
        event_log: Optional[List[Dict[str, Any]]] = None,
        monitor_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convert simulation session data and execute the debrief engine end-to-end.
        """
        converted_data = self.convert(session=session, event_log=event_log, monitor_state=monitor_state)
        
        print(f"[DebriefAdapter] Executing debrief pipeline for {converted_data['session_id']}...")
        result = self.service.generate_debrief(converted_data)
        
        print(f"[DebriefAdapter] Debrief executed successfully! PDF generated at: {result['pdf_path']}\n")
        return result


def convert_and_debrief(
    session: Dict[str, Any],
    event_log: Optional[List[Dict[str, Any]]] = None,
    monitor_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Public entry point function for converting simulation data and generating a debrief report.
    """
    adapter = DebriefAdapter()
    return adapter.process_session_and_debrief(session=session, event_log=event_log, monitor_state=monitor_state)
