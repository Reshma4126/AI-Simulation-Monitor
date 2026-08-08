"""
ingestion/schema.py — Compatibility shim
=========================================
Redirects all imports to the canonical schema in data/schemas/event_schema.py.
Do NOT add new code here.

This file exists so that any external code still importing from
`ingestion.schema` continues to work during the migration period.
Once all callers have been updated, this file will be deleted.
"""
from data.schemas.event_schema import (
    EventType,
    SourceSystem,
    ActorRole,
    Severity,
    DataCompletenessFlag,
    Evidence,
    UnifiedEvent,
    FindingRecord,
    UnifiedTimeline,
)

# Legacy alias — ingestion.schema used RhythmType which does not exist
# in the canonical schema (rhythms are stored as plain strings in event.value).
# Map to EventType as a temporary stand-in; remove after full migration.
RhythmType = EventType

# Legacy Pydantic-style classes that tests relied on — expose SessionMetadata
# as a plain dataclass wrapper so dict-construction still works.
from dataclasses import dataclass as _dataclass, field as _field
from typing import Optional as _Optional


@_dataclass
class SessionMetadata:
    """
    Thin wrapper used by test helpers that pass metadata as a dict.
    The canonical schema embeds session info directly in UnifiedTimeline.
    """
    session_id: str = ""
    date: str = ""
    scenario_name: str = ""
    scenario_type: str = ""
    team_leader_id: str = ""
    team_leader_name: str = ""
    team_size: int = 0
    duration_ms: int = 0
    guideline_version: str = "AHA_2020"
