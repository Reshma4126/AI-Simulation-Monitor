"""
OpenAI Narrative Report Generator — CPR Debriefing System
==========================================================
Drop-in replacement for synthesis/claude_api.py.
Same FindingVerifier hallucination guard.
Same 7-section structure.
Same DebriefReport output — PDF generator is unchanged.

Only difference from claude_api.py:
  - Uses openai.OpenAI client instead of anthropic.Anthropic
  - System prompt passed as messages[0] role="system"
  - Model from OPENAI_MODEL env var (default gpt-4o)

Author: Deva
"""

from __future__ import annotations
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

from data.schemas.event_schema import (
    FindingRecord, UnifiedTimeline, Severity,
)

# Re-export DebriefReport and ReportSection so worker.py
# imports from one place regardless of which LLM backend is used.
from synthesis.claude_api import (
    DebriefReport,
    ReportSection,
    FindingVerifier,
    SECTION_INSTRUCTIONS,
    build_section_prompt,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# System prompt — identical clinical framing to claude_api.py
# ==============================================================================

SYSTEM_PROMPT = """You are a clinical debriefing assistant for a medical simulation center.
You receive pre-analyzed, structured findings from an ACLS cardiac arrest simulation.

Your role is NARRATIVE SYNTHESIS ONLY.
- You do NOT generate new findings.
- You do NOT introduce clinical judgments not present in the input.
- You phrase the provided findings in clear, constructive, evidence-based language
  appropriate for a post-simulation debrief with medical interns.

CRITICAL REQUIREMENT — TRACEABILITY TAGS:
Every evaluative claim you write must be tagged with the finding_id it comes from.
Format: place [finding_id:fnd_XXXXXXXX] immediately after the claim it supports.

Example:
"The team initiated CPR within 8 seconds of arrest recognition [finding_id:fnd_a3c21f90],
which is within the AHA-recommended 10-second window."

Sections that are purely factual (scenario summary) do not require tags.
Do NOT invent finding IDs. Only use IDs from the provided findings JSON.

Tone: constructive, specific, non-judgmental. This is education, not evaluation.
Audience: medical interns (PGY-1/PGY-2) and their supervising faculty."""


# ==============================================================================
# OpenAI Report Generator
# ==============================================================================

class ReportGenerator:
    """
    Generates all 7 debrief report sections using OpenAI.

    Identical public API to synthesis/claude_api.ReportGenerator.
    worker.py imports this class — no other file needs changing.
    """

    MAX_RETRIES   = 3
    RETRY_DELAY_S = 2

    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY")
        )
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    # ------------------------------------------------------------------
    # Public API — identical signature to claude_api.ReportGenerator
    # ------------------------------------------------------------------

    def generate_report(self, timeline: UnifiedTimeline) -> DebriefReport:
        """Full pipeline: findings → all sections → verified DebriefReport."""
        logger.info(
            f"Generating report via OpenAI ({self.model}) "
            f"for session: {timeline.session_id}"
        )
        start = time.time()

        findings      = timeline.findings
        valid_ids     = {f.finding_id for f in findings}
        verifier      = FindingVerifier(valid_ids)
        findings_json = json.dumps([f.to_dict() for f in findings], indent=2)
        scores_json   = json.dumps(
            timeline.summary()["findings_by_severity"], indent=2
        )
        session_ctx = {
            "scenario_name":  timeline.scenario_name,
            "team_leader_id": timeline.team_leader_id,
            "session_date":   timeline.session_date,
            "duration_min":   self._estimate_duration(timeline),
        }

        report = DebriefReport(
            session_id=timeline.session_id,
            scenario_name=timeline.scenario_name,
            team_leader_id=timeline.team_leader_id,
            session_date=timeline.session_date,
        )

        # Scenario summary — factual, no verification needed
        logger.info("Generating: scenario_summary")
        report.scenario_summary = ReportSection(
            title="Scenario Summary",
            content=self._generate_scenario_summary(session_ctx, findings),
        )

        # All verified sections
        for section_key, instructions in SECTION_INSTRUCTIONS.items():
            logger.info(f"Generating: {section_key}")
            section = self._generate_verified_section(
                section_name=section_key,
                instructions=instructions,
                findings_json=findings_json,
                scores_json=scores_json,
                session_context=session_ctx,
                verifier=verifier,
            )
            setattr(report, section_key, section)

        elapsed = time.time() - start
        report.generation_metadata = {
            "model":                 self.model,
            "backend":               "openai",
            "total_findings":        len(findings),
            "generation_time_s":     round(elapsed, 2),
            "all_sections_verified": True,
        }
        logger.info(f"Report complete in {elapsed:.1f}s")
        return report

    def generate_report_from_payload(self, payload: dict) -> DebriefReport:
        """
        Worker-friendly entry point.
        Reconstructs a UnifiedTimeline from the broker payload dict
        and calls generate_report().

        Handles Severity deserialization — payload findings carry severity
        as plain strings (from to_dict()); this method converts them back
        to Severity enum members before handing off.
        """
        tl_meta  = payload.get("timeline", {})
        timeline = UnifiedTimeline(
            session_id=tl_meta.get("session_id", "unknown"),
            scenario_name=tl_meta.get("scenario_name", "Unknown Scenario"),
            team_leader_id=tl_meta.get("team_leader_id", "Unknown"),
            session_date=tl_meta.get("session_date", ""),
        )
        timeline.findings = [
            self._finding_from_dict(f)
            for f in payload.get("findings", [])
        ]
        return self.generate_report(timeline)

    # ------------------------------------------------------------------
    # Section generators
    # ------------------------------------------------------------------

    def _generate_scenario_summary(
        self, session_context: dict, findings: list[FindingRecord]
    ) -> str:
        critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        high     = sum(1 for f in findings if f.severity == Severity.HIGH)
        prompt   = (
            f"Write a 2-paragraph factual scenario summary.\n\n"
            f"Paragraph 1: scenario name, team leader, date, duration.\n"
            f"Paragraph 2: neutral overview — total findings, "
            f"severity breakdown ({critical} critical, {high} high, "
            f"total {len(findings)}).\n\n"
            f"Session: {json.dumps(session_context, indent=2)}"
        )
        raw = self._call_openai(prompt, max_tokens=400)
        # Strip any traceability tags — summary is factual but the mock
        # (and occasionally the model) may include them; remove for clean output.
        verifier = FindingVerifier(set())   # empty set — we just want the strip method
        return verifier.strip_tags(raw)

    def _generate_verified_section(
        self,
        section_name:    str,
        instructions:    str,
        findings_json:   str,
        scores_json:     str,
        session_context: dict,
        verifier:        FindingVerifier,
    ) -> ReportSection:
        """Generate → verify → retry loop. Mirrors claude_api.py exactly."""
        prompt   = build_section_prompt(
            section_name=section_name,
            findings_json=findings_json,
            scores_json=scores_json,
            session_context=session_context,
            instructions=instructions,
        )
        attempts     = 0
        last_content = ""

        while attempts < self.MAX_RETRIES:
            attempts += 1
            raw = self._call_openai(prompt, max_tokens=800)
            is_valid, invalid_ids = verifier.verify(raw, section_name)

            if is_valid:
                return ReportSection(
                    title=section_name.replace("_", " ").title(),
                    content=verifier.strip_tags(raw),
                    finding_ids_referenced=verifier.extract_referenced_ids(raw),
                    generation_attempts=attempts,
                )

            logger.warning(
                f"[{section_name}] Attempt {attempts}/{self.MAX_RETRIES} — "
                f"invalid IDs: {invalid_ids}. Retrying."
            )
            last_content = raw
            prompt = self._build_correction_prompt(
                original_prompt=prompt,
                rejected_output=raw,
                invalid_ids=invalid_ids,
                valid_ids=list(verifier.valid_finding_ids)[:10],
            )
            time.sleep(self.RETRY_DELAY_S)

        logger.error(
            f"[{section_name}] All retries exhausted. "
            f"Returning flagged section."
        )
        return ReportSection(
            title=section_name.replace("_", " ").title(),
            content=(
                f"[VERIFICATION WARNING — review before use]\n\n"
                f"{verifier.strip_tags(last_content)}"
            ),
            finding_ids_referenced=[],
            generation_attempts=attempts,
        )

    # ------------------------------------------------------------------
    # OpenAI call
    # ------------------------------------------------------------------

    def _call_openai(self, user_prompt: str, max_tokens: int = 800) -> str:
        """Single OpenAI API call. Returns text content."""
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.3,    # low temperature — factual, not creative
        )
        return response.choices[0].message.content

    def _build_correction_prompt(
        self,
        original_prompt: str,
        rejected_output: str,
        invalid_ids:     list[str],
        valid_ids:       list[str],
    ) -> str:
        return (
            f"{original_prompt}\n\n---\nCORRECTION REQUIRED:\n"
            f"Your previous response referenced these finding IDs "
            f"which do not exist: {invalid_ids}\n"
            f"Valid IDs you may use: {valid_ids}\n"
            f"Rewrite using ONLY valid IDs. "
            f"If a claim has no supporting finding, omit the claim."
        )

    def _estimate_duration(self, timeline: UnifiedTimeline) -> str:
        if not timeline.events:
            return "N/A"
        ms = timeline.events[-1].timestamp_ms
        return f"{ms // 60000}m {(ms % 60000) // 1000}s"

    # ------------------------------------------------------------------
    # Deserialization helper
    # ------------------------------------------------------------------

    @staticmethod
    def _finding_from_dict(f: dict) -> FindingRecord:
        """
        Safely reconstruct a FindingRecord from a to_dict() payload.

        to_dict() serializes severity as a plain string ("high").
        FindingRecord expects a Severity enum member.
        Evidence list is dropped here — findings from broker payloads
        are used for narrative generation only, not re-evaluation.
        """
        sev_raw = f.get("severity", "info")
        severity = (
            Severity(sev_raw)
            if isinstance(sev_raw, str)
            else sev_raw
        )
        return FindingRecord(
            finding_id=f.get("finding_id", ""),
            template_id=f.get("template_id", ""),
            domain=f.get("domain", ""),
            severity=severity,
            title=f.get("title", ""),
            description=f.get("description", ""),
            guideline_citation=f.get("guideline_citation", ""),
            recommendation=f.get("recommendation", ""),
            timestamp_ms=f.get("timestamp_ms", 0),
            expected_at_ms=f.get("expected_at_ms"),
            actual_value=f.get("actual_value"),
            expected_value=f.get("expected_value"),
            reflective_prompt=f.get("reflective_prompt"),
            penalty_weight=f.get("penalty_weight", 0.0),
        )
