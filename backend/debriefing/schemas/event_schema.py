"""
Unified Event Schema — CPR Debriefing System
=============================================
The canonical data structure every component reads from and writes to.
All timestamps are milliseconds from session start (t=0).

Author: Deva
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid


# ==============================================================================
# Controlled Vocabulary — Event Types
# ==============================================================================

class EventType(str, Enum):
    """
    Every event in the unified timeline must be one of these types.
    Adding a new type here is the only place you need to change the vocabulary.
    """

    # --- Clinical / SimMan events ---
    ARREST_RECOGNIZED       = "arrest_recognized"
    CPR_INITIATED           = "cpr_initiated"
    CPR_PAUSED              = "cpr_paused"
    CPR_RESUMED             = "cpr_resumed"
    RHYTHM_CHECK            = "rhythm_check"
    SHOCK_DELIVERED         = "shock_delivered"
    SHOCK_ADVISED           = "shock_advised"
    SHOCK_NOT_ADVISED       = "shock_not_advised"
    DRUG_ORDERED            = "drug_ordered"
    DRUG_ADMINISTERED       = "drug_administered"
    VENTILATION_GIVEN       = "ventilation_given"
    AIRWAY_SECURED          = "airway_secured"
    ROSC_ACHIEVED           = "rosc_achieved"
    RHYTHM_CHANGE           = "rhythm_change"
    PULSE_CHECK             = "pulse_check"

    # --- Communication / Audio events ---
    SPEECH_SEGMENT          = "speech_segment"
    ORDER_GIVEN             = "order_given"           # parsed from lapel
    ORDER_CONFIRMED         = "order_confirmed"       # parsed from ceiling
    CALLOUT_MADE            = "callout_made"          # rhythm/vital announced
    ROLE_ASSIGNED           = "role_assigned"         # "you, do compressions"

    # --- Analysis / Derived events ---
    DEVIATION_DETECTED      = "deviation_detected"    # emitted by FSM
    FINDING_GENERATED       = "finding_generated"     # emitted by scoring engine
    CROSS_STREAM_CONFIRMED  = "cross_stream_confirmed"

    # --- Session lifecycle ---
    SESSION_START           = "session_start"
    SESSION_END             = "session_end"
    SCENARIO_MARKER         = "scenario_marker"       # instructor-triggered

    # --- Backward-compatibility aliases (from ingestion/schema.py) ---
    CALLOUT                 = "callout"               # alias for CALLOUT_MADE
    COMPRESSION_CYCLE       = "compression_cycle"     # per-compression event
    DRUG_ORDER              = "drug_order"             # alias for DRUG_ORDERED
    AIRWAY_SECURED_ALIAS    = "airway_secured"         # duplicate value guard
    ORDER_CONFIRMED_ALIAS   = "order_confirmed"        # already defined above
    INSTRUCTOR_TRIGGER      = "instructor_trigger"
    VENTILATION             = "ventilation"            # alias for VENTILATION_GIVEN
    SHOCK_ADVISED_ALIAS     = "shock_advised"          # already defined above


class SourceSystem(str, Enum):
    """Which data stream produced or confirmed this event."""
    SIMMAN      = "simman"
    LAPEL       = "lapel_audio"
    CEILING     = "ceiling_audio"
    VIDEO       = "video"
    FSM         = "fsm"           # derived by rule engine
    NLP         = "nlp"           # derived by NLP engine
    VERIFIER    = "cross_stream_verifier"
    MANUAL      = "manual"        # instructor override

    # Backward-compatibility aliases
    LAPEL_AUDIO     = "lapel_audio"    # same value as LAPEL — enum deduplication
    CEILING_AUDIO   = "ceiling_audio"  # same value as CEILING


class ActorRole(str, Enum):
    """Who performed the action. Unknown when audio attribution fails."""
    TEAM_LEADER     = "team_leader"
    COMPRESSOR      = "compressor"
    AIRWAY          = "airway_manager"
    MEDICATION      = "medication_nurse"
    RECORDER        = "recorder"
    INSTRUCTOR      = "instructor"
    UNKNOWN         = "unknown"


class Severity(str, Enum):
    """Severity of a deviation or finding."""
    CRITICAL    = "critical"   # directly impacts patient outcome in real scenario
    HIGH        = "high"       # significant guideline violation
    MODERATE    = "moderate"   # suboptimal but not dangerous
    LOW         = "low"        # minor, coaching opportunity
    INFO        = "info"       # neutral observation, not a deviation


class DataCompletenessFlag(str, Enum):
    """How complete is the evidence supporting this event."""
    FULL        = "full"        # all expected sources confirmed
    PARTIAL     = "partial"     # some sources missing, finding still valid
    INFERRED    = "inferred"    # single source, treat with caution
    UNCERTAIN   = "uncertain"   # low confidence across all sources

    # Scoring Engine aliases
    COMPLETE        = "full"
    PARTIAL_DATA    = "partial"
    LOW_DATA        = "uncertain"


# ==============================================================================
# Evidence — atomic unit of source traceability
# ==============================================================================

@dataclass
class Evidence:
    """
    Traces one event back to its raw source.
    Every finding shown to a clinician must have at least one Evidence object.
    """
    source: SourceSystem
    ref: str                        # e.g. "log_line_142", "transcript_seg_0028"
    text: Optional[str] = None      # verbatim text if from audio
    timestamp_ms: Optional[int] = None
    confidence: float = 1.0         # source-level confidence [0.0 – 1.0]

    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "ref": self.ref,
            "text": self.text,
            "timestamp_ms": self.timestamp_ms,
            "confidence": self.confidence,
        }


# ==============================================================================
# Drug payload — for DRUG_ORDERED / DRUG_ADMINISTERED events
# ==============================================================================

@dataclass
class DrugPayload:
    """
    Structured representation of a drug administration event.
    Parsed by NLP engine from lapel transcript.
    """
    drug_name: str                          # "epinephrine"
    dose_mg: Optional[float] = None         # 1.0
    dose_unit: Optional[str] = None         # "mg", "mcg"
    route: Optional[str] = None             # "IV", "IO"
    is_complete: bool = False               # True only if all three fields present

    def validate(self) -> list[str]:
        """Returns list of missing fields. Empty list = complete order."""
        missing = []
        if not self.dose_mg:
            missing.append("dose")
        if not self.route:
            missing.append("route")
        return missing

    def to_dict(self) -> dict:
        return {
            "drug_name": self.drug_name,
            "dose_mg": self.dose_mg,
            "dose_unit": self.dose_unit,
            "route": self.route,
            "is_complete": self.is_complete,
            "missing_fields": self.validate(),
        }


# ==============================================================================
# CPR Quality payload — for CPR_INITIATED / CPR_PAUSED / CPR_RESUMED
# ==============================================================================

@dataclass
class CPRQualityPayload:
    rate_per_min: Optional[float] = None        # compressions per minute
    depth_cm: Optional[float] = None            # compression depth in cm
    chest_compression_fraction: Optional[float] = None  # CCF [0–1]
    pause_duration_ms: Optional[int] = None     # duration of no-compression pause

    def to_dict(self) -> dict:
        return {
            "rate_per_min": self.rate_per_min,
            "depth_cm": self.depth_cm,
            "chest_compression_fraction": self.chest_compression_fraction,
            "pause_duration_ms": self.pause_duration_ms,
        }


# ==============================================================================
# Shock payload
# ==============================================================================

@dataclass
class ShockPayload:
    energy_joules: Optional[int] = None
    rhythm_pre: Optional[str] = None       # "VF", "pVT", "asystole"
    rhythm_post: Optional[str] = None
    shock_number: Optional[int] = None     # 1st, 2nd, 3rd shock in sequence

    def to_dict(self) -> dict:
        return {
            "energy_joules": self.energy_joules,
            "rhythm_pre": self.rhythm_pre,
            "rhythm_post": self.rhythm_post,
            "shock_number": self.shock_number,
        }


# ==============================================================================
# Core Unified Event Object
# ==============================================================================

@dataclass
class UnifiedEvent:
    """
    The canonical event object. Every downstream component reads from this.

    Construction:
        Event objects are created by parsers (SimMan, Whisper) and
        analysis engines (FSM, NLP). The synchronizer normalizes timestamps
        to a common clock before handing off to analysis.

    Immutability note:
        Once an event is on the unified timeline, its core fields
        (event_id, timestamp_ms, event_type, source_systems, evidence)
        should not be mutated. Enrichment (e.g. adding speaker_label,
        boosting confidence) creates a new event or updates mutable
        annotation fields only.
    """

    # --- Identity ---
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    timestamp_ms: int = 0                           # ms from session start

    # --- Classification ---
    event_type: EventType = EventType.SCENARIO_MARKER
    source_systems: list[SourceSystem] = field(default_factory=list)
    actor_role: ActorRole = ActorRole.UNKNOWN

    # --- Payload (one of these will be set depending on event_type) ---
    value: Optional[dict] = None                    # generic k/v for simple events
    drug_payload: Optional[DrugPayload] = None
    cpr_payload: Optional[CPRQualityPayload] = None
    shock_payload: Optional[ShockPayload] = None

    # --- Confidence & completeness ---
    confidence: float = 1.0                         # [0.0 – 1.0]
    data_completeness: DataCompletenessFlag = DataCompletenessFlag.FULL

    # --- Evidence chain ---
    evidence: list[Evidence] = field(default_factory=list)

    # --- Deviation linkage (set by FSM / NLP engine) ---
    deviation_id: Optional[str] = None              # links to FindingRecord
    severity: Optional[Severity] = None

    # --- Scenario context ---
    scenario_expected: bool = False                 # was this event expected at this time?
    expected_at_ms: Optional[int] = None            # when was it expected?
    delay_ms: Optional[int] = None                  # actual - expected (negative = early)

    def __post_init__(self):
        # Auto-compute delay if both timestamps available
        if self.expected_at_ms is not None and self.delay_ms is None:
            self.delay_ms = self.timestamp_ms - self.expected_at_ms

    def boost_confidence(self, additional_source: SourceSystem, evidence: Evidence):
        """
        Called by cross-stream verifier when a second source confirms this event.
        Multi-source confirmation boosts confidence toward 1.0.
        Formula: new = old + (1 - old) * 0.4 per additional confirming source.
        """
        self.source_systems.append(additional_source)
        self.evidence.append(evidence)
        self.confidence = min(1.0, self.confidence + (1.0 - self.confidence) * 0.4)
        self._update_completeness_flag()

    def _update_completeness_flag(self):
        n = len(self.source_systems)
        if n >= 3:
            self.data_completeness = DataCompletenessFlag.FULL
        elif n == 2:
            self.data_completeness = DataCompletenessFlag.PARTIAL
        elif self.confidence >= 0.7:
            self.data_completeness = DataCompletenessFlag.INFERRED
        else:
            self.data_completeness = DataCompletenessFlag.UNCERTAIN

    def to_dict(self) -> dict:
        """Serialize to plain dict for JSON export / LLM prompt injection."""
        d = {
            "event_id": self.event_id,
            "timestamp_ms": self.timestamp_ms,
            "event_type": self.event_type.value,
            "source_systems": [s.value for s in self.source_systems],
            "actor_role": self.actor_role.value,
            "confidence": round(self.confidence, 3),
            "data_completeness": self.data_completeness.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "severity": self.severity.value if self.severity else None,
            "deviation_id": self.deviation_id,
            "scenario_expected": self.scenario_expected,
            "expected_at_ms": self.expected_at_ms,
            "delay_ms": self.delay_ms,
        }
        if self.value:
            d["value"] = self.value
        if self.drug_payload:
            d["drug_payload"] = self.drug_payload.to_dict()
        if self.cpr_payload:
            d["cpr_payload"] = self.cpr_payload.to_dict()
        if self.shock_payload:
            d["shock_payload"] = self.shock_payload.to_dict()
        return d

    def __repr__(self):
        return (
            f"UnifiedEvent(id={self.event_id}, t={self.timestamp_ms}ms, "
            f"type={self.event_type.value}, confidence={self.confidence:.2f})"
        )


# ==============================================================================
# Finding Record — output of analysis engines, input to scoring + LLM
# ==============================================================================

@dataclass
class FindingRecord:
    """
    A structured finding emitted by the FSM, NLP, or cross-stream verifier.
    This is what the scoring engine aggregates and what the LLM narrates.

    The finding_id is the traceability anchor — every LLM output sentence
    must reference a finding_id that exists in this list.
    """
    finding_id: str = field(default_factory=lambda: f"fnd_{uuid.uuid4().hex[:8]}")
    template_id: str = ""                       # e.g. "delayed_first_shock"
    domain: str = ""                            # "cpr_quality", "drug_administration" …
    severity: Severity = Severity.INFO
    title: str = ""                             # short display title from template
    description: str = ""                       # human-readable, for the report
    guideline_citation: str = ""                # "AHA 2020 Adult Cardiac Arrest Algorithm, Step 5"
    recommendation: str = ""                    # actionable recommendation from template
    triggering_event_ids: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    timestamp_ms: int = 0                       # when the deviation occurred
    expected_at_ms: Optional[int] = None
    actual_value: Optional[Any] = None          # e.g. pause_duration_ms = 18000
    expected_value: Optional[Any] = None        # e.g. expected <= 10000
    reflective_prompt: Optional[str] = None     # fixed template prompt for debrief
    penalty_weight: float = 0.0                 # used by scoring engine

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "template_id": self.template_id,
            "domain": self.domain,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "guideline_citation": self.guideline_citation,
            "recommendation": self.recommendation,
            "triggering_event_ids": self.triggering_event_ids,
            "evidence": [e.to_dict() for e in self.evidence],
            "timestamp_ms": self.timestamp_ms,
            "expected_at_ms": self.expected_at_ms,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "reflective_prompt": self.reflective_prompt,
            "penalty_weight": self.penalty_weight,
        }


# ==============================================================================
# Unified Timeline — the full session record
# ==============================================================================

@dataclass
class UnifiedTimeline:
    """
    The complete session record. Passed between all pipeline stages.
    """
    session_id: str
    scenario_name: str
    team_leader_id: str
    session_date: str                           # ISO 8601
    events: list[UnifiedEvent] = field(default_factory=list)
    findings: list[FindingRecord] = field(default_factory=list)

    def add_event(self, event: UnifiedEvent):
        self.events.append(event)
        self.events.sort(key=lambda e: e.timestamp_ms)

    def get_events_by_type(self, event_type: EventType) -> list[UnifiedEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def get_events_in_window(self, start_ms: int, end_ms: int) -> list[UnifiedEvent]:
        return [e for e in self.events if start_ms <= e.timestamp_ms <= end_ms]

    def get_findings_by_domain(self, domain: str) -> list[FindingRecord]:
        return [f for f in self.findings if f.domain == domain]

    def get_findings_by_severity(self, severity: Severity) -> list[FindingRecord]:
        return [f for f in self.findings if f.severity == severity]

    @property
    def total_duration_ms(self) -> int:
        if hasattr(self, "duration_ms") and getattr(self, "duration_ms", None):
            return getattr(self, "duration_ms")
        if self.events:
            return self.events[-1].timestamp_ms
        return 600000

    @property
    def arrest_start_ms(self) -> Optional[int]:
        ev = next((e for e in self.events if e.event_type in [EventType.ARREST_RECOGNIZED, EventType.CPR_INITIATED, "arrest_recognized", "cpr_initiated"]), None)
        return ev.timestamp_ms if ev else 0

    @property
    def rosc_ms(self) -> Optional[int]:
        ev = next((e for e in self.events if e.event_type in [EventType.ROSC_ACHIEVED, "rosc_achieved"]), None)
        return ev.timestamp_ms if ev else None

    def summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "scenario_name": self.scenario_name,
            "team_leader_id": self.team_leader_id,
            "session_date": self.session_date,
            "total_events": len(self.events),
            "total_findings": len(self.findings),
            "findings_by_severity": {
                s.value: len(self.get_findings_by_severity(s))
                for s in Severity
            },
        }


@dataclass
class TranscriptSegment:
    segment_id: str = ""
    text: str = ""
    speaker_role: ActorRole = ActorRole.UNKNOWN
    start_ms: int = 0
    end_ms: int = 0
    source: str = "lapel"
    confidence: float = 1.0

