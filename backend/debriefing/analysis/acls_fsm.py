"""
ACLS Cardiac Arrest Finite State Machine
AHA 2020 Guidelines — Adult Cardiac Arrest Algorithm

Scope v1:
- VF / pVT branch
- Asystole / PEA branch
- ~12 critical state transitions

Every deviation emits a structured finding.
No ML. Pure rules. Fully auditable.
"""

import logging
from typing import List, Optional, Dict, Any
from transitions import Machine

from schemas.event_schema import (
    UnifiedTimeline, UnifiedEvent, EventType,
    Severity, FindingRecord, Evidence, SourceSystem,
)
from analysis.finding_templates import format_finding

logger = logging.getLogger(__name__)


# Severity → penalty_weight mapping for scoring engine
_SEVERITY_PENALTY: dict[str, float] = {
    "critical": 0.35,
    "high":     0.20,
    "moderate": 0.10,
    "low":      0.04,
    "info":     0.00,
}


def ms_to_readable(ms: int) -> str:
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}m {seconds:02d}s"


# ---------- FSM ----------

class ACLSFiniteStateMachine:
    """
    Walks a unified timeline and evaluates it against
    AHA 2020 ACLS cardiac arrest algorithm rules.
    Emits findings for every detected deviation.
    """

    # AHA timing constants (milliseconds)
    CPR_INITIATION_LIMIT_MS = 10_000        # 10 seconds
    RHYTHM_CHECK_INTERVAL_MS = 120_000      # 2 minutes
    CPR_PAUSE_LIMIT_MS = 10_000             # 10 seconds
    SHOCK_RESUME_LIMIT_MS = 10_000          # 10 seconds post-shock
    EPI_FIRST_WINDOW_MIN_MS = 180_000       # 3 minutes
    EPI_FIRST_WINDOW_MAX_MS = 300_000       # 5 minutes
    EPI_REPEAT_MIN_MS = 180_000             # 3 minutes
    EPI_REPEAT_MAX_MS = 300_000             # 5 minutes
    CCF_TARGET = 0.80                       # 80%
    COMPRESSION_RATE_MIN = 100
    COMPRESSION_RATE_MAX = 120
    COMPRESSION_DEPTH_MIN_CM = 5.0
    COMPRESSION_DEPTH_MAX_CM = 6.0
    RHYTHM_CALLOUT_WINDOW_MS = 10_000       # 10 seconds

    STATES = [
        "idle",
        "arrest_recognized",
        "cpr_active",
        "rhythm_check",
        "shock_delivered",
        "post_shock_cpr",
        "rosc",
        "terminated",
    ]

    def __init__(self):
        self.machine = Machine(
            model=self,
            states=self.STATES,
            initial="idle",
            ignore_invalid_triggers=True,
        )
        self._add_transitions()
        self._reset_state()

    def _add_transitions(self):
        self.machine.add_transition(
            "recognize_arrest", "idle", "arrest_recognized")
        self.machine.add_transition(
            "start_cpr", "arrest_recognized", "cpr_active")
        self.machine.add_transition(
            "do_rhythm_check", "cpr_active", "rhythm_check")
        self.machine.add_transition(
            "deliver_shock", "rhythm_check", "shock_delivered")
        self.machine.add_transition(
            "resume_cpr_post_shock", "shock_delivered", "post_shock_cpr")
        self.machine.add_transition(
            "continue_cpr_cycle", "post_shock_cpr", "cpr_active")
        self.machine.add_transition(
            "continue_no_shock", "rhythm_check", "cpr_active")
        self.machine.add_transition(
            "achieve_rosc", "*", "rosc")
        self.machine.add_transition(
            "end_session", "*", "terminated")

    def _reset_state(self):
        self.findings: List[FindingRecord] = []
        self.finding_counter = 0

        # Timing trackers
        self.arrest_time_ms: Optional[int] = None
        self.cpr_start_time_ms: Optional[int] = None
        self.last_rhythm_check_ms: Optional[int] = None
        self.last_shock_ms: Optional[int] = None
        self.last_epi_ms: Optional[int] = None
        self.epi_count = 0
        self.shock_count = 0
        self.current_rhythm: Optional[str] = None

        # CPR quality trackers
        self.cpr_active_ms = 0
        self.total_session_ms = 0
        self.cpr_pause_start_ms: Optional[int] = None
        self.cpr_resume_time_ms: Optional[int] = None   # tracks last CPR start/resume
        self.compression_rates: List[float] = []
        self.compression_depths: List[float] = []

        # Drug tracking
        self.amiodarone_given = False

        # Communication trackers
        self.rhythm_changes: List[dict] = []

    def _emit_finding(
        self,
        template_id: str,
        timestamp_ms: int,
        evidence_event_ids: List[str],
        **kwargs
    ) -> FindingRecord:
        self.finding_counter += 1
        finding_id = f"fnd_{self.finding_counter:08d}"
        raw = format_finding(template_id, **kwargs)

        finding = FindingRecord(
            finding_id=finding_id,
            template_id=template_id,
            title=raw["title"],
            severity=Severity(raw["severity"]),
            domain=raw["domain"],
            guideline_citation=raw["guideline_citation"],
            description=raw["description"],
            reflective_prompt=raw["reflective_prompt"],
            recommendation=raw["recommendation"],
            timestamp_ms=timestamp_ms,
            penalty_weight=_SEVERITY_PENALTY.get(raw["severity"], 0.10),
            evidence=[
                Evidence(
                    source=SourceSystem.SIMMAN,
                    ref=eid,
                    confidence=1.0,
                )
                for eid in evidence_event_ids
            ],
        )
        self.findings.append(finding)
        logger.info(
            f"Finding: {finding_id} | "
            f"{raw['severity'].upper()} | {raw['title']}"
        )
        return finding

    # ---------- Event processors ----------

    def _process_session_start(self, event: UnifiedEvent):
        self.total_session_ms = 0
        logger.info("Session started")

    def _process_arrest_recognized(self, event: UnifiedEvent):
        self.arrest_time_ms = event.timestamp_ms
        self.recognize_arrest()
        logger.info(
            f"Arrest recognized at {ms_to_readable(event.timestamp_ms)}")

    def _process_cpr_initiated(self, event: UnifiedEvent):
        if self.arrest_time_ms is None:
            logger.warning("CPR initiated before arrest recognized")
            self.arrest_time_ms = event.timestamp_ms

        delay_ms = event.timestamp_ms - self.arrest_time_ms
        self.cpr_start_time_ms = event.timestamp_ms
        self.cpr_resume_time_ms = event.timestamp_ms   # start accumulating CPR time

        if delay_ms > self.CPR_INITIATION_LIMIT_MS:
            self._emit_finding(
                "cpr_delayed",
                timestamp_ms=event.timestamp_ms,
                evidence_event_ids=[event.event_id],
                delay=round(delay_ms / 1000, 1)
            )

        # Collect compression quality data
        val = event.value or {}
        rate = val.get("compression_rate")
        depth = val.get("compression_depth_cm")
        if rate:
            self.compression_rates.append(rate)
            if rate < self.COMPRESSION_RATE_MIN:
                self._emit_finding(
                    "compression_rate_low",
                    timestamp_ms=event.timestamp_ms,
                    evidence_event_ids=[event.event_id],
                    rate=rate
                )
            elif rate > self.COMPRESSION_RATE_MAX:
                self._emit_finding(
                    "compression_rate_high",
                    timestamp_ms=event.timestamp_ms,
                    evidence_event_ids=[event.event_id],
                    rate=rate
                )
        if depth:
            self.compression_depths.append(depth)
            if depth < self.COMPRESSION_DEPTH_MIN_CM:
                self._emit_finding(
                    "compression_depth_low",
                    timestamp_ms=event.timestamp_ms,
                    evidence_event_ids=[event.event_id],
                    depth=depth
                )

        self.start_cpr()

    def _process_cpr_paused(self, event: UnifiedEvent):
        self.cpr_pause_start_ms = event.timestamp_ms
        pause_duration_ms = (event.value or {}).get("pause_duration_ms", 0)

        # Accumulate active CPR time up to this pause
        if self.cpr_resume_time_ms is not None:
            self.cpr_active_ms += event.timestamp_ms - self.cpr_resume_time_ms
            self.cpr_resume_time_ms = None

        if pause_duration_ms > self.CPR_PAUSE_LIMIT_MS:
            self._emit_finding(
                "cpr_pause_excessive",
                timestamp_ms=event.timestamp_ms,
                evidence_event_ids=[event.event_id],
                duration=round(pause_duration_ms / 1000, 1),
                timestamp=ms_to_readable(event.timestamp_ms)
            )

    def _process_cpr_resumed(self, event: UnifiedEvent):
        """Track CPR resume time for CCF accumulation and post-shock check."""
        self.cpr_resume_time_ms = event.timestamp_ms
        self.continue_cpr_cycle()

    def _process_rhythm_check(self, event: UnifiedEvent):
        rhythm = (event.value or {}).get("rhythm", "unknown")
        self.current_rhythm = rhythm

        if self.last_rhythm_check_ms is not None:
            interval_ms = event.timestamp_ms - self.last_rhythm_check_ms
            if interval_ms > self.RHYTHM_CHECK_INTERVAL_MS + 15_000:
                delay_ms = interval_ms - self.RHYTHM_CHECK_INTERVAL_MS
                self._emit_finding(
                    "rhythm_check_delayed",
                    timestamp_ms=event.timestamp_ms,
                    evidence_event_ids=[event.event_id],
                    timestamp=ms_to_readable(event.timestamp_ms),
                    delay=round(delay_ms / 1000, 1)
                )

        self.last_rhythm_check_ms = event.timestamp_ms
        self.do_rhythm_check()

    def _process_shock_delivered(self, event: UnifiedEvent):
        self.shock_count += 1
        self.last_shock_ms = event.timestamp_ms
        self.deliver_shock()
        logger.info(
            f"Shock #{self.shock_count} delivered at "
            f"{ms_to_readable(event.timestamp_ms)}"
        )

    def _process_drug_administered(self, event: UnifiedEvent):
        drug = (event.value or {}).get("drug", "").lower()
        timestamp = ms_to_readable(event.timestamp_ms)

        if "amiodarone" in drug:
            self.amiodarone_given = True

        if "epinephrine" in drug:
            self.epi_count += 1

            if self.epi_count == 1:
                if self.arrest_time_ms is not None:
                    delay_ms = event.timestamp_ms - self.arrest_time_ms
                    if delay_ms > self.EPI_FIRST_WINDOW_MAX_MS:
                        self._emit_finding(
                            "epinephrine_delayed_first",
                            timestamp_ms=event.timestamp_ms,
                            evidence_event_ids=[event.event_id],
                            timestamp=timestamp,
                            delay=round(
                                (delay_ms - self.EPI_FIRST_WINDOW_MAX_MS)
                                / 1000, 1
                            )
                        )

            elif self.epi_count > 1 and self.last_epi_ms is not None:
                interval_ms = event.timestamp_ms - self.last_epi_ms
                if interval_ms > self.EPI_REPEAT_MAX_MS:
                    self._emit_finding(
                        "epinephrine_interval_exceeded",
                        timestamp_ms=event.timestamp_ms,
                        evidence_event_ids=[event.event_id],
                        timestamp=timestamp,
                        interval=round(interval_ms / 1000, 1)
                    )

            self.last_epi_ms = event.timestamp_ms

            # Check order completeness
            if not (event.value or {}).get("order_complete", True):
                missing = (event.value or {}).get(
                    "missing_fields", "dose and route")
                self._emit_finding(
                    "drug_order_incomplete",
                    timestamp_ms=event.timestamp_ms,
                    evidence_event_ids=[event.event_id],
                    timestamp=timestamp,
                    drug=drug,
                    missing_fields=missing
                )

    def _process_rhythm_change(self, event: UnifiedEvent):
        from_rhythm = (event.value or {}).get("from_rhythm", "unknown")
        to_rhythm = (event.value or {}).get("to_rhythm", "unknown")
        self.rhythm_changes.append({
            "timestamp_ms": event.timestamp_ms,
            "from": from_rhythm,
            "to": to_rhythm,
            "event_id": event.event_id,
            "callout_detected": False
        })
        self.current_rhythm = to_rhythm

    def _process_callout(self, event: UnifiedEvent):
        callout_text = (event.value or {}).get("text", "").lower()
        rhythm_keywords = [
            "vf", "v-fib", "pea", "asystole",
            "rhythm", "sinus", "nsr", "shockable"
        ]
        is_rhythm_callout = any(
            kw in callout_text for kw in rhythm_keywords
        )
        if is_rhythm_callout:
            for change in self.rhythm_changes:
                time_diff = abs(
                    event.timestamp_ms - change["timestamp_ms"]
                )
                if (time_diff <= self.RHYTHM_CALLOUT_WINDOW_MS
                        and not change["callout_detected"]):
                    change["callout_detected"] = True
                    break

    def _process_rosc(self, event: UnifiedEvent):
        self.achieve_rosc()
        logger.info(
            f"ROSC at {ms_to_readable(event.timestamp_ms)}"
        )

    def _process_session_end(self, event: UnifiedEvent):
        self.total_session_ms = event.timestamp_ms
        self._run_end_of_session_checks()
        self.end_session()

    # ---------- End-of-session checks ----------

    def _run_end_of_session_checks(self):
        self._check_amiodarone()
        self._check_ccf()
        self._check_missed_rhythm_callouts()

    def _check_amiodarone(self):
        """Check amiodarone given after 3rd shock in VF/pVT."""
        if self.shock_count >= 3 and not self.amiodarone_given:
            self._emit_finding(
                "amiodarone_not_given",
                timestamp_ms=self.total_session_ms,
                evidence_event_ids=[],
            )

    def _check_ccf(self):
        """Check overall chest compression fraction."""
        # Flush any still-running CPR segment into the accumulator
        if self.cpr_resume_time_ms is not None:
            self.cpr_active_ms += self.total_session_ms - self.cpr_resume_time_ms

        if self.total_session_ms > 0 and self.cpr_active_ms > 0:
            ccf = self.cpr_active_ms / self.total_session_ms
            if ccf < self.CCF_TARGET:
                self._emit_finding(
                    "ccf_below_target",
                    timestamp_ms=self.total_session_ms,
                    evidence_event_ids=[],
                    ccf=round(ccf * 100, 1)
                )

    def _check_missed_rhythm_callouts(self):
        """Check for rhythm changes with no verbal announcement."""
        for change in self.rhythm_changes:
            if not change["callout_detected"]:
                self._emit_finding(
                    "rhythm_change_callout_missed",
                    timestamp_ms=change["timestamp_ms"],
                    evidence_event_ids=[change["event_id"]],
                    from_rhythm=change["from"],
                    to_rhythm=change["to"],
                    timestamp=ms_to_readable(change["timestamp_ms"])
                )

    # ---------- Main entry point ----------

    def evaluate(self, timeline: UnifiedTimeline) -> List[FindingRecord]:
        """
        Walk the timeline and evaluate against ACLS rules.
        Returns a list of FindingRecord objects ordered by timestamp.
        Compatible with ScoringEngine.compute() — pass timeline.findings
        after calling this method.
        """
        self._reset_state()
        logger.info(
            f"Evaluating session {timeline.session_id} "
            f"— {timeline.scenario_name}"
        )

        processors = {
            EventType.SESSION_START:    self._process_session_start,
            EventType.ARREST_RECOGNIZED: self._process_arrest_recognized,
            EventType.CPR_INITIATED:    self._process_cpr_initiated,
            EventType.CPR_PAUSED:       self._process_cpr_paused,
            EventType.CPR_RESUMED:      self._process_cpr_resumed,
            EventType.RHYTHM_CHECK:     self._process_rhythm_check,
            EventType.RHYTHM_CHANGE:    self._process_rhythm_change,
            EventType.SHOCK_DELIVERED:  self._process_shock_delivered,
            EventType.DRUG_ADMINISTERED: self._process_drug_administered,
            EventType.CALLOUT:          self._process_callout,
            EventType.ROSC_ACHIEVED:    self._process_rosc,
            EventType.SESSION_END:      self._process_session_end,
        }

        for event in sorted(
            timeline.events, key=lambda e: e.timestamp_ms
        ):
            processor = processors.get(event.event_type)
            if processor:
                processor(event)
            else:
                logger.debug(
                    f"No processor for event type: {event.event_type}"
                )

        self.findings.sort(key=lambda f: f.timestamp_ms)
        logger.info(
            f"Evaluation complete — {len(self.findings)} findings"
        )
        return self.findings
