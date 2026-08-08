"""
Event Extractor — CPR Debriefing System
========================================
Maps raw transcript segments → structured UnifiedEvents.
v1: Rule-based regex patterns derived from synthetic dataset.
v2: Fine-tuned classifier trained on real session transcripts.

Designed to be protocol-agnostic — patterns loaded from config.
Audio transcript is the PRIMARY data source. SimMan is optional enrichment.

Author: Deva
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass
from typing import Optional
from schemas.event_schema import (
    UnifiedEvent, EventType, SourceSystem,
    ActorRole, DrugPayload, Evidence,
    DataCompletenessFlag,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Speaker → Role mapping
# Derived from synthetic dataset: Consultant=leader, Resident=assessor, Nurse=executor
# ==============================================================================

SPEAKER_ROLE_MAP: dict[str, ActorRole] = {
    "consultant": ActorRole.TEAM_LEADER,
    "resident":   ActorRole.AIRWAY,        # typically announces rhythm
    "nurse":      ActorRole.MEDICATION,    # typically gives drugs + shocks
    "team":       ActorRole.UNKNOWN,
    "unknown":    ActorRole.UNKNOWN,
}


# ==============================================================================
# Drug NER — name aliases → canonical name + route/dose parsing
# ==============================================================================

DRUG_ALIASES: dict[str, str] = {
    "epinephrine": "epinephrine",
    "epi":         "epinephrine",
    "adrenaline":  "epinephrine",
    "amiodarone":  "amiodarone",
    "cordarone":   "amiodarone",
    "atropine":    "atropine",
    "adenosine":   "adenosine",
    "lidocaine":   "lidocaine",
    "vasopressin": "vasopressin",
    "bicarb":      "sodium bicarbonate",
    "sodium bicarbonate": "sodium bicarbonate",
    "calcium":     "calcium",
}

DOSE_PATTERN   = re.compile(r'(\d+(?:\.\d+)?)\s*(mg|mcg|ml|g|meq)', re.IGNORECASE)
ROUTE_PATTERN  = re.compile(r'\b(iv|io|im|sc|tracheal|oral)\b', re.IGNORECASE)


# ==============================================================================
# Event Pattern Rules
# Each rule: (EventType, [trigger_patterns], confidence)
# Patterns are matched against lowercased transcript text.
# First match wins within a segment.
# ==============================================================================

@dataclass
class EventPattern:
    event_type: EventType
    patterns:   list[re.Pattern]
    confidence: float          # base confidence when matched by rule alone
    requires_context: bool = False  # True = needs surrounding events for disambiguation


EVENT_PATTERNS: list[EventPattern] = [

    # --- Arrest / Session lifecycle ---
    EventPattern(EventType.ARREST_RECOGNIZED, [
        re.compile(r'patient collapsed', re.I),
        re.compile(r'no response', re.I),
        re.compile(r'cardiac arrest', re.I),
        re.compile(r'found unresponsive', re.I),
    ], confidence=0.90),

    EventPattern(EventType.PULSE_CHECK, [
        re.compile(r'check pulse', re.I),
        re.compile(r'feel.*pulse', re.I),
        re.compile(r'pulse check', re.I),
        re.compile(r'any pulse', re.I),
    ], confidence=0.85),

    EventPattern(EventType.CPR_INITIATED, [
        re.compile(r'start cpr', re.I),
        re.compile(r'begin(?: compressions)?', re.I),
        re.compile(r'starting compressions', re.I),
        re.compile(r'pump(ing)?', re.I),
        re.compile(r'do(ing)? cpr', re.I),
    ], confidence=0.85),

    EventPattern(EventType.CPR_PAUSED, [
        re.compile(r'stop compressions', re.I),
        re.compile(r'hold(?: cpr)?', re.I),
        re.compile(r'pause(?: cpr)?', re.I),
        re.compile(r'no compressions', re.I),
    ], confidence=0.80),

    EventPattern(EventType.CPR_RESUMED, [
        re.compile(r'resume(?: cpr| compressions)?', re.I),
        re.compile(r'continue(?: cpr| compressions)?', re.I),
        re.compile(r'restart(?: cpr| compressions)?', re.I),
        re.compile(r'back on(?: compressions)?', re.I),
    ], confidence=0.85),

    # --- Rhythm ---
    EventPattern(EventType.RHYTHM_CHECK, [
        re.compile(r'rhythm check', re.I),
        re.compile(r'check(?: the)? rhythm', re.I),
        re.compile(r'analyze(?: rhythm)?', re.I),
        re.compile(r'stop.*check.*rhythm', re.I),
    ], confidence=0.88),

    EventPattern(EventType.RHYTHM_CHANGE, [
        re.compile(r'rhythm (?:is|looks like|now|shows?)\s+(\w+)', re.I),
        re.compile(r'(?:now it\'s|it\'s)\s+(vf|pea|asystole|pvt|sinus)', re.I),
        re.compile(r'(vf|ventricular fibrillation|pea|asystole|pvt|pulseless vt|sinus rhythm)\s+(?:recognized|detected|present|confirmed)', re.I),
        re.compile(r'still\s+(vf|pea|asystole)', re.I),
        re.compile(r'transition(?:ed|ing)? to\s+(\w+)', re.I),
        re.compile(r'looks like\s+(vf|pea|asystole|pvt)', re.I),
        re.compile(r'this is\s+(vf|pea|asystole|pvt)', re.I),
        re.compile(r'rhythm now looks like\s+(\w+)', re.I),
    ], confidence=0.85),

    # --- Shock ---
    EventPattern(EventType.SHOCK_ADVISED, [
        re.compile(r'shock(?:able)?(?: rhythm)?', re.I),
        re.compile(r'shock (?:him|her|now|indicated)', re.I),
        re.compile(r'charging(?: to \d+ joules?)?', re.I),
        re.compile(r'charge(?: to \d+ joules?)?', re.I),
        re.compile(r'defibrillat(?:e|ion|or)', re.I),
        re.compile(r'clear(?:\s*!)?$', re.I),
    ], confidence=0.80),

    EventPattern(EventType.SHOCK_DELIVERED, [
        re.compile(r'shock delivered', re.I),
        re.compile(r'shocked', re.I),
        re.compile(r'defibrillation delivered', re.I),
        re.compile(r'shock (?:given|done)', re.I),
    ], confidence=0.92),

    # --- Drugs ---
    EventPattern(EventType.DRUG_ORDERED, [
        re.compile(r'give\s+(?:\d+\s*mg\s+)?(\w+)', re.I),
        re.compile(r'prepare\s+(\w+)', re.I),
        re.compile(r'administer\s+(\w+)', re.I),
        re.compile(r'push\s+(\w+)', re.I),
    ], confidence=0.80),

    EventPattern(EventType.DRUG_ADMINISTERED, [
        re.compile(r'(\w+)\s+(?:\d+\s*mg\s+)?(?:given|administered|pushed|done)', re.I),
        re.compile(r'(\w+)\s+in', re.I),    # e.g. "epi in"
        re.compile(r'flush given', re.I),
    ], confidence=0.88),

    # --- Airway ---
    EventPattern(EventType.AIRWAY_SECURED, [
        re.compile(r'intubat(?:ed|ion|ing)', re.I),
        re.compile(r'advanced airway(?: placed| secured| in)?', re.I),
        re.compile(r'ett(?: placed| confirmed)?', re.I),
        re.compile(r'tube (?:placed|confirmed|in)', re.I),
        re.compile(r'laryngoscop(?:e|y|ing)', re.I),
    ], confidence=0.90),

    # --- ROSC ---
    EventPattern(EventType.ROSC_ACHIEVED, [
        re.compile(r'rosc', re.I),
        re.compile(r'return of spontaneous circulation', re.I),
        re.compile(r'(?:i )?can feel a pulse', re.I),
        re.compile(r'pulse (?:present|back|detected|felt)', re.I),
        re.compile(r'got a pulse', re.I),
    ], confidence=0.95),

    # --- Communication ---
    EventPattern(EventType.ORDER_CONFIRMED, [
        re.compile(r'(?:epi|epinephrine|amiodarone|atropine)\s+(?:in|confirmed|done)', re.I),
        re.compile(r'confirmed', re.I),
        re.compile(r'copy', re.I),
    ], confidence=0.75),

    EventPattern(EventType.CALLOUT_MADE, [
        re.compile(r'calling out', re.I),
        re.compile(r'(?:bp|spo2|etco2|heart rate)\s+(?:is\s+)?[\d/]+', re.I),
        re.compile(r'reversible causes?', re.I),
        re.compile(r'hs?\s+and\s+ts?', re.I),
    ], confidence=0.75),
]


# ==============================================================================
# Rhythm value extractor
# ==============================================================================

RHYTHM_LABELS: dict[str, str] = {
    "vf":                    "VF",
    "ventricular fibrillation": "VF",
    "pvt":                   "pVT",
    "pulseless vt":          "pVT",
    "pulseless ventricular tachycardia": "pVT",
    "pea":                   "PEA",
    "pulseless electrical activity": "PEA",
    "asystole":              "asystole",
    "sinus":                 "sinus",
    "sinus rhythm":          "sinus",
    "organized":             "organized",
}

def extract_rhythm_value(text: str) -> Optional[str]:
    text_lower = text.lower()
    for alias, label in RHYTHM_LABELS.items():
        if alias in text_lower:
            return label
    return None


# ==============================================================================
# Drug payload extractor
# ==============================================================================

def extract_drug_payload(text: str) -> Optional[DrugPayload]:
    text_lower = text.lower()
    found_drug = None
    for alias, canonical in DRUG_ALIASES.items():
        if alias in text_lower:
            found_drug = canonical
            break
    if not found_drug:
        return None

    dose_match  = DOSE_PATTERN.search(text)
    route_match = ROUTE_PATTERN.search(text)

    dose_mg   = float(dose_match.group(1)) if dose_match else None
    dose_unit = dose_match.group(2).lower() if dose_match else None
    route     = route_match.group(1).upper() if route_match else None

    return DrugPayload(
        drug_name=found_drug,
        dose_mg=dose_mg,
        dose_unit=dose_unit,
        route=route,
        is_complete=bool(found_drug and dose_mg and route),
    )


# ==============================================================================
# Main Event Extractor
# ==============================================================================

class EventExtractor:
    """
    Converts speaker-attributed transcript segments into UnifiedEvents.

    v1 strategy:
        - Rule-based regex matching
        - Drug NER via alias lookup + regex
        - Rhythm extraction via label map
        - Speaker → ActorRole mapping

    v2 upgrade path:
        - Replace _match_patterns() with classifier inference
        - Keep all other methods unchanged
        - Single method swap, zero architectural change
    """

    def __init__(self, source: SourceSystem = SourceSystem.LAPEL):
        self.source = source

    def extract(self, segments: list[dict]) -> list[UnifiedEvent]:
        """
        Process all transcript segments and return UnifiedEvents.

        Args:
            segments: list of dicts with keys:
                timestamp_ms, end_ms, text, speaker_label, segment_id, confidence
        Returns:
            list of UnifiedEvent sorted by timestamp_ms
        """
        events = []
        for seg in segments:
            extracted = self._process_segment(seg)
            events.extend(extracted)

        events.sort(key=lambda e: e.timestamp_ms)
        logger.info(f"Extracted {len(events)} events from {len(segments)} segments")
        return events

    def _process_segment(self, seg: dict) -> list[UnifiedEvent]:
        """One segment can produce multiple events (e.g. drug order + confirmation)."""
        text       = seg.get("text", "").strip()
        ts_ms      = seg.get("timestamp_ms", 0)
        seg_id     = seg.get("segment_id", "unknown")
        speaker    = seg.get("speaker_label", "unknown")
        base_conf  = seg.get("confidence", 0.8)

        if not text:
            return []

        role    = self._resolve_role(speaker)
        matched = self._match_patterns(text)
        events  = []

        for event_type, match_confidence in matched:
            event = UnifiedEvent(
                timestamp_ms=ts_ms,
                event_type=event_type,
                source_systems=[self.source],
                actor_role=role,
                confidence=round(min(1.0, base_conf * match_confidence), 3),
                data_completeness=DataCompletenessFlag.INFERRED,
                evidence=[Evidence(
                    source=self.source,
                    ref=seg_id,
                    text=text,
                    timestamp_ms=ts_ms,
                    confidence=base_conf,
                )],
            )

            # Enrich with payload
            if event_type in (EventType.DRUG_ORDERED, EventType.DRUG_ADMINISTERED):
                event.drug_payload = extract_drug_payload(text)

            if event_type == EventType.RHYTHM_CHANGE:
                rhythm_val = extract_rhythm_value(text)
                if rhythm_val:
                    event.value = {"rhythm": rhythm_val}

            events.append(event)
            logger.debug(
                f"[{ts_ms}ms] {event_type.value} ← '{text[:60]}' "
                f"(speaker={speaker}, conf={event.confidence:.2f})"
            )

        # If no pattern matched but segment is meaningful, log for v2 training
        if not events and len(text.split()) > 3:
            logger.debug(f"[UNMATCHED] t={ts_ms}ms '{text[:80]}'")

        return events

    def _match_patterns(self, text: str) -> list[tuple[EventType, float]]:
        """
        Returns list of (EventType, confidence) for all matching patterns.
        Multiple matches allowed — one segment can contain multiple events.
        Priority: higher-confidence patterns shadow lower ones of the same type.
        """
        matched: dict[EventType, float] = {}

        for rule in EVENT_PATTERNS:
            for pattern in rule.patterns:
                if pattern.search(text):
                    existing = matched.get(rule.event_type, 0.0)
                    if rule.confidence > existing:
                        matched[rule.event_type] = rule.confidence
                    break   # first pattern match per rule is enough

        return list(matched.items())

    def _resolve_role(self, speaker_label: str) -> ActorRole:
        key = speaker_label.lower().strip()
        return SPEAKER_ROLE_MAP.get(key, ActorRole.UNKNOWN)
