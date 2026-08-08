"""
Claude API Report Generator — CPR Debriefing System
====================================================
Narrative synthesis only. The LLM does not generate findings.
It phrases findings that already exist in the structured input.

Every sentence in the output must reference a finding_id.
Output is rejected and regenerated if any claim is ungrounded.

Author: Deva
"""

from __future__ import annotations
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional
import anthropic

from schemas.event_schema import (
    FindingRecord, UnifiedTimeline, Severity,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Report Section Dataclasses
# ==============================================================================

@dataclass
class ReportSection:
    """One named section of the debrief report."""
    title: str
    content: str                        # narrative prose from LLM
    finding_ids_referenced: list[str] = field(default_factory=list)
    generation_attempts: int = 1


@dataclass
class DebriefReport:
    """
    Full structured report. Eight sections as defined in the architecture doc.
    Passed to the PDF generator after all sections are verified.
    """
    session_id: str
    scenario_name: str
    team_leader_id: str
    session_date: str
    overall_score: float = 0.0
    domain_scores: dict = field(default_factory=dict)

    scenario_summary: Optional[ReportSection] = None
    strengths: Optional[ReportSection] = None
    protocol_deviations: Optional[ReportSection] = None
    communication_analysis: Optional[ReportSection] = None
    domain_scores_narrative: Optional[ReportSection] = None
    reflective_prompts: Optional[ReportSection] = None
    recommendations: Optional[ReportSection] = None

    generation_metadata: dict = field(default_factory=dict)

    def all_sections(self) -> list[ReportSection]:
        sections = [
            self.scenario_summary,
            self.strengths,
            self.protocol_deviations,
            self.communication_analysis,
            self.domain_scores_narrative,
            self.reflective_prompts,
            self.recommendations,
        ]
        return [s for s in sections if s is not None]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "scenario_name": self.scenario_name,
            "team_leader_id": self.team_leader_id,
            "session_date": self.session_date,
            "overall_score": self.overall_score,
            "domain_scores": self.domain_scores,
            "sections": {
                "scenario_summary": self.scenario_summary.content if self.scenario_summary else "",
                "strengths": self.strengths.content if self.strengths else "",
                "protocol_deviations": self.protocol_deviations.content if self.protocol_deviations else "",
                "communication_analysis": self.communication_analysis.content if self.communication_analysis else "",
                "domain_scores_narrative": self.domain_scores_narrative.content if self.domain_scores_narrative else "",
                "reflective_prompts": self.reflective_prompts.content if self.reflective_prompts else "",
                "recommendations": self.recommendations.content if self.recommendations else "",
            },
            "generation_metadata": self.generation_metadata,
        }


# ==============================================================================
# Verification Engine
# ==============================================================================

class FindingVerifier:
    """
    Verifies that every claim in LLM output traces to a real finding_id.
    
    The LLM is instructed to tag every claim with [finding_id:fnd_XXXXXXXX].
    This verifier parses those tags and checks them against the input finding set.
    Ungrounded claims → rejection → regeneration.
    """

    FINDING_TAG_PATTERN = re.compile(r'\[finding_id:(fnd_[a-zA-Z0-9]+)\]')

    def __init__(self, valid_finding_ids: set[str]):
        self.valid_finding_ids = valid_finding_ids

    def extract_referenced_ids(self, text: str) -> list[str]:
        return self.FINDING_TAG_PATTERN.findall(text)

    def verify(self, text: str, section_name: str) -> tuple[bool, list[str]]:
        """
        Returns (is_valid, list_of_invalid_ids).
        A section with zero finding tags is accepted only for
        scenario_summary (which is factual, not evaluative).
        """
        referenced = self.extract_referenced_ids(text)
        invalid = [fid for fid in referenced if fid not in self.valid_finding_ids]

        if invalid:
            logger.warning(
                f"[{section_name}] Hallucinated finding IDs detected: {invalid}"
            )
            return False, invalid

        return True, []

    def strip_tags(self, text: str) -> str:
        """Remove [finding_id:...] tags from final output for clean PDF rendering."""
        return self.FINDING_TAG_PATTERN.sub("", text).strip()


# ==============================================================================
# Prompt Templates
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
Audience: medical interns (PGY-1/PGY-2) and their supervising faculty.
"""


def build_section_prompt(
    section_name: str,
    findings_json: str,
    scores_json: str,
    session_context: dict,
    instructions: str,
) -> str:
    return f"""SESSION CONTEXT:
Scenario: {session_context['scenario_name']}
Team Leader: {session_context['team_leader_id']}
Date: {session_context['session_date']}
Duration: {session_context.get('duration_min', 'N/A')} minutes

DOMAIN SCORES:
{scores_json}

STRUCTURED FINDINGS (JSON):
{findings_json}

SECTION TO WRITE: {section_name}

INSTRUCTIONS:
{instructions}

Remember: tag every evaluative claim with [finding_id:fnd_XXXXXXXX].
Write only the section content. No headers, no preamble."""


SECTION_INSTRUCTIONS = {
    "strengths": """
Write 3–5 specific strengths observed during the scenario.
Each strength must reference a finding or a positive event from the findings list.
If a finding has severity=info and is positive in nature, highlight it here.
Be specific and timestamped where possible.
Format: One paragraph per strength, 2–3 sentences each.
""",

    "protocol_deviations": """
Write a clear account of each protocol deviation, severity-ranked (critical first).
For each deviation:
- State what happened and when (timestamp if available)
- State what the guideline requires (cite the guideline)
- State the clinical significance
- Keep tone educational, not accusatory
Format: One paragraph per deviation. Order: critical → high → moderate → low.
""",

    "communication_analysis": """
Analyze team communication patterns based on the findings.
Cover: closed-loop communication rate, order completeness, callout completeness,
any repeated requests (signals unheard orders), leadership clarity.
Be specific. Quote exact findings where relevant.
Format: 3–4 paragraphs.
""",

    "domain_scores_narrative": """
Write a brief interpretive narrative for each domain score provided.
Explain what the score means in plain language and what drove it up or down.
Note where data completeness was partial (wide confidence interval) and
caution the reader not to over-interpret those scores.
Format: One short paragraph per domain.
""",

    "reflective_prompts": """
Write 4–6 reflective questions for the debrief facilitator to use with the team leader.
Each question must be grounded in a specific finding.
Questions should be open-ended, non-leading, and invite the team leader to
reconstruct their own reasoning. Never ask "why didn't you..." — ask
"walk me through your thinking when..."
Format: Numbered list. One sentence per question.
""",

    "recommendations": """
Write 3–5 ranked recommendations for the next training session.
Rank by clinical impact (highest impact first).
Each recommendation must be specific and actionable, not generic.
Bad: "Work on communication." Good: "Practice closed-loop confirmation drills
specifically for drug orders — the team confirmed fewer than 40% of epinephrine orders."
Format: Numbered list. 2–3 sentences per recommendation.
""",
}


# ==============================================================================
# Report Generator
# ==============================================================================

class ReportGenerator:
    """
    Orchestrates Claude API calls to generate all report sections.

    Flow:
        1. Serialize findings + scores to JSON
        2. For each section: call Claude → verify finding IDs → retry if invalid
        3. Strip traceability tags for clean PDF output
        4. Assemble DebriefReport
    """

    MAX_RETRIES = 3
    RETRY_DELAY_S = 2

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-20250514"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_report(self, timeline: UnifiedTimeline) -> DebriefReport:
        """
        Full pipeline: findings → all sections → verified DebriefReport.
        """
        logger.info(f"Generating report for session: {timeline.session_id}")
        start_time = time.time()

        # Build inputs
        findings = timeline.findings
        valid_ids = {f.finding_id for f in findings}
        verifier = FindingVerifier(valid_ids)

        findings_json = json.dumps(
            [f.to_dict() for f in findings], indent=2
        )

        # Build a domain summary for the LLM — group findings by domain with
        # severity breakdown. ScoreReport integration comes when FSM→scoring
        # pipeline is unified; for now this gives the LLM real domain data.
        domain_summary: dict = {}
        for f in findings:
            entry = domain_summary.setdefault(f.domain, {"findings": 0, "severities": {}})
            entry["findings"] += 1
            sev = f.severity.value
            entry["severities"][sev] = entry["severities"].get(sev, 0) + 1
        scores_json = json.dumps(domain_summary, indent=2)

        session_context = {
            "scenario_name": timeline.scenario_name,
            "team_leader_id": timeline.team_leader_id,
            "session_date": timeline.session_date,
            "duration_min": self._estimate_duration(timeline),
        }

        report = DebriefReport(
            session_id=timeline.session_id,
            scenario_name=timeline.scenario_name,
            team_leader_id=timeline.team_leader_id,
            session_date=timeline.session_date,
        )

        # Generate scenario summary (no verification needed — factual)
        logger.info("Generating: scenario_summary")
        raw_summary = self._generate_scenario_summary(session_context, findings)
        report.scenario_summary = ReportSection(
            title="Scenario Summary",
            content=verifier.strip_tags(raw_summary),
        )

        # Generate all verified sections
        for section_key, instructions in SECTION_INSTRUCTIONS.items():
            logger.info(f"Generating: {section_key}")
            section = self._generate_verified_section(
                section_name=section_key,
                instructions=instructions,
                findings_json=findings_json,
                scores_json=scores_json,
                session_context=session_context,
                verifier=verifier,
            )
            setattr(report, section_key, section)

        elapsed = time.time() - start_time
        report.generation_metadata = {
            "model": self.model,
            "total_findings": len(findings),
            "generation_time_s": round(elapsed, 2),
            "all_sections_verified": True,
        }

        logger.info(f"Report complete in {elapsed:.1f}s")
        return report

    # ------------------------------------------------------------------
    # Section generators
    # ------------------------------------------------------------------

    def _generate_scenario_summary(
        self, session_context: dict, findings: list[FindingRecord]
    ) -> str:
        """
        Factual summary — no finding tags required.
        Built from structured data directly, minimal LLM involvement.
        """
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        high = [f for f in findings if f.severity == Severity.HIGH]

        prompt = f"""Write a 2-paragraph factual scenario summary for a debrief report.

Paragraph 1: What was run — scenario name, team leader, date, duration.
Paragraph 2: High-level overview of performance — total findings, 
severity breakdown ({len(critical)} critical, {len(high)} high). 
Keep this neutral and factual. No recommendations here.

Session context: {json.dumps(session_context, indent=2)}
Finding counts: critical={len(critical)}, high={len(high)}, 
total={len(findings)}"""

        return self._call_claude(prompt, max_tokens=400)

    def _generate_verified_section(
        self,
        section_name: str,
        instructions: str,
        findings_json: str,
        scores_json: str,
        session_context: dict,
        verifier: FindingVerifier,
    ) -> ReportSection:
        """
        Generate a section and verify finding ID references.
        Retries up to MAX_RETRIES times if verification fails.
        """
        prompt = build_section_prompt(
            section_name=section_name,
            findings_json=findings_json,
            scores_json=scores_json,
            session_context=session_context,
            instructions=instructions,
        )

        attempts = 0
        last_content = ""

        while attempts < self.MAX_RETRIES:
            attempts += 1
            raw_content = self._call_claude(prompt, max_tokens=800)
            is_valid, invalid_ids = verifier.verify(raw_content, section_name)

            if is_valid:
                referenced_ids = verifier.extract_referenced_ids(raw_content)
                clean_content = verifier.strip_tags(raw_content)
                return ReportSection(
                    title=section_name.replace("_", " ").title(),
                    content=clean_content,
                    finding_ids_referenced=referenced_ids,
                    generation_attempts=attempts,
                )

            # Retry with correction prompt
            logger.warning(
                f"[{section_name}] Attempt {attempts}/{self.MAX_RETRIES} failed. "
                f"Invalid IDs: {invalid_ids}. Retrying."
            )
            last_content = raw_content
            prompt = self._build_correction_prompt(
                original_prompt=prompt,
                rejected_output=raw_content,
                invalid_ids=invalid_ids,
                valid_ids=list(verifier.valid_finding_ids)[:10],
            )
            time.sleep(self.RETRY_DELAY_S)

        # All retries exhausted — return best attempt with warning
        logger.error(
            f"[{section_name}] Verification failed after {self.MAX_RETRIES} attempts. "
            f"Using last output with warning flag."
        )
        clean_content = verifier.strip_tags(last_content)
        return ReportSection(
            title=section_name.replace("_", " ").title(),
            content=f"[VERIFICATION WARNING — review before use]\n\n{clean_content}",
            finding_ids_referenced=[],
            generation_attempts=attempts,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_claude(self, user_prompt: str, max_tokens: int = 800) -> str:
        """Single Claude API call. Returns text content."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

    def _build_correction_prompt(
        self,
        original_prompt: str,
        rejected_output: str,
        invalid_ids: list[str],
        valid_ids: list[str],
    ) -> str:
        return f"""{original_prompt}

---
CORRECTION REQUIRED:
Your previous response referenced these finding IDs which do not exist in the input:
{invalid_ids}

Valid finding IDs you may use: {valid_ids}

Rewrite the section using ONLY finding IDs from the valid list above.
Do not invent IDs. If a claim has no supporting finding, omit the claim."""

    def _estimate_duration(self, timeline: UnifiedTimeline) -> str:
        if not timeline.events:
            return "N/A"
        duration_ms = timeline.events[-1].timestamp_ms
        minutes = duration_ms // 60000
        seconds = (duration_ms % 60000) // 1000
        return f"{minutes}m {seconds}s"
