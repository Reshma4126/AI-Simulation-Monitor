"""
narrative_engine.py
-------------------
Final synthesis step of the CPR debriefing pipeline.

Takes the fully-scored ScoreReport (which contains FSM findings + NLP deductions)
and asks a local LLM to generate human-readable narrative sections suitable for
embedding in the PDF debrief report.

Output is a structured NarrativeOutput dataclass containing:
    - strengths        : List[str]   → bullet items for AI-Detected Strengths
    - deficiencies     : List[str]   → bullet items for AI-Detected Deficiencies
    - recommendations  : List[str]   → bullet items for AI Recommendations
    - reflective_qs    : List[str]   → bullet items for Reflective Debrief Questions
    - final_summary    : str         → paragraph for Final AI Summary

Design decisions:
    * Uses JSON-structured output (Ollama format_json) so we never need fragile
      keyword parsing; the LLM explicitly returns a typed object.
    * Falls back to deterministic rule-based text if the LLM is unavailable,
      ensuring the PDF pipeline never crashes during testing or offline runs.
    * The prompt is grounded in the quantitative ScoreReport data, so the narrative
      is always factually consistent with the scores (no hallucination risk).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Output model
# =============================================================================

@dataclass
class NarrativeOutput:
    """Structured narrative output consumed by pdf_adapter.py."""
    strengths: List[str] = field(default_factory=list)
    deficiencies: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    reflective_qs: List[str] = field(default_factory=list)
    final_summary: str = ""


# =============================================================================
# Prompt builder
# =============================================================================

def _build_prompt(report) -> str:
    """
    Convert a ScoreReport into a concise LLM prompt grounded in numbers.
    The LLM is instructed to return strict JSON — no markdown, no prose outside JSON.
    """
    # Summarise domain scores for the prompt context
    domain_lines = []
    for d in report.domain_scores:
        pct = (d.final_score / d.max_points * 100) if d.max_points > 0 else 0
        domain_lines.append(
            f"  - {d.domain_label}: {d.final_score:.1f}/{d.max_points:.0f} pts "
            f"({pct:.0f}%)"
        )

    # Gather sub-signal notes for context
    finding_notes = []
    for d in report.domain_scores:
        for ss in d.sub_signals:
            if ss.points_deducted > 0:
                finding_notes.append(f"  [{d.domain_label}] {ss.notes} (−{ss.points_deducted:.1f} pts)")

    grade_ctx = f"Overall Grade: {report.grade} ({report.overall_score:.1f}/100)"
    if report.hard_fail_override:
        grade_ctx += f" [HARD-FAIL: {report.hard_fail_reason}]"

    prompt = f"""You are a medical simulation debriefer AI assistant generating a structured written analysis.

Below is the quantitative scoring data from an ACLS simulation session.

{grade_ctx}

Domain Breakdown:
{chr(10).join(domain_lines) if domain_lines else "  (No domain data)"}

Key Findings (protocol deviations that caused point deductions):
{chr(10).join(finding_notes) if finding_notes else "  (No significant deviations)"}

---

Based ONLY on the data above, generate a debrief report narrative.

Respond with ONLY a valid JSON object — no markdown, no explanation, no extra text. Use this exact schema:

{{
  "strengths": ["<strength 1>", "<strength 2>", ...],
  "deficiencies": ["<deficiency 1>", "<deficiency 2>", ...],
  "recommendations": ["<recommendation 1>", "<recommendation 2>", ...],
  "reflective_qs": ["<question 1>", "<question 2>", ...],
  "final_summary": "<one paragraph summary>"
}}

Rules:
- strengths: 3–6 items, based on domains that scored > 70%
- deficiencies: 2–5 items, based on domains with deductions or hard-fail
- recommendations: 3–5 specific, actionable improvement items
- reflective_qs: 3–5 open-ended questions for team reflection
- final_summary: 2–4 sentences, clinically accurate, encouraging but honest
"""
    return prompt


# =============================================================================
# Fallback generator (deterministic, no LLM)
# =============================================================================

def _rule_based_narrative(report) -> NarrativeOutput:
    """
    Generates a safe deterministic narrative when the LLM is unavailable.
    This ensures the PDF pipeline always produces a valid document.
    """
    strengths = []
    deficiencies = []
    recommendations = []

    for d in report.domain_scores:
        pct = (d.final_score / d.max_points * 100) if d.max_points > 0 else 0
        if pct >= 80:
            strengths.append(f"Strong performance in {d.domain_label} ({pct:.0f}%).")
        elif pct < 60:
            deficiencies.append(
                f"{d.domain_label} needs improvement ({pct:.0f}% — target ≥ 80%)."
            )
            recommendations.append(
                f"Review {d.domain_label} protocol steps and practice focused drills."
            )

    if not strengths:
        strengths = ["Team demonstrated commitment to patient care throughout the scenario."]
    if not deficiencies:
        deficiencies = ["No critical deficiencies detected."]
    if not recommendations:
        recommendations = ["Continue practising regular ACLS simulation scenarios."]

    reflective_qs = [
        "What could have been done to improve CPR continuity?",
        "Were all team members' roles clearly defined?",
        "How could closed-loop communication be strengthened?",
        "At what point should reversible causes have been discussed?",
        "What would you do differently in the next scenario?",
    ]

    grade = report.grade
    score = report.overall_score
    hf = f" Note: A hard-fail rule was triggered ({report.hard_fail_reason})." if report.hard_fail_override else ""

    final_summary = (
        f"The team achieved a final grade of {grade} ({score:.1f}/100) on the ACLS simulation.{hf} "
        f"Key areas of strength were identified in domains scoring above 80%. "
        f"Targeted practice in the identified deficiency areas is recommended before the next scenario. "
        f"Continued simulation-based training will reinforce ACLS protocol adherence."
    )

    return NarrativeOutput(
        strengths=strengths,
        deficiencies=deficiencies,
        recommendations=recommendations,
        reflective_qs=reflective_qs,
        final_summary=final_summary,
    )


# =============================================================================
# NarrativeEngine
# =============================================================================

class NarrativeEngine:
    """
    Final synthesis step: ScoreReport → human-readable NarrativeOutput.

    Usage:
        engine = NarrativeEngine()
        narrative = engine.generate(score_report)
    """

    def __init__(self, llm=None):
        self._llm = llm
        self._use_llm = False

        if llm is not None:
            self._use_llm = True
            return

        # Auto-detect Ollama
        try:
            import urllib.request
            from langchain_ollama import ChatOllama  # noqa: F401

            # Prefer localhost — WSL2 port-forwards it automatically from Windows.
            base_url = "http://localhost:11434"
            try:
                urllib.request.urlopen(f"{base_url}/api/tags", timeout=2)
            except Exception:
                import subprocess
                try:
                    wsl_ip = subprocess.check_output(
                        ["wsl", "hostname", "-I"], text=True
                    ).strip().split()[0]
                    base_url = f"http://{wsl_ip}:11434"
                except Exception:
                    pass  # keep localhost

            model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
            self._llm = ChatOllama(
                model=model_name,
                temperature=0.3,
                base_url=base_url,
                format="json",   # Forces strict JSON output — no markdown wrapping
            )
            self._use_llm = True
            logger.info(
                f"NarrativeEngine: Ollama [{model_name}] at {base_url}"
            )
        except ImportError:
            logger.warning(
                "NarrativeEngine: langchain_ollama not installed. "
                "Using rule-based fallback."
            )
        except Exception as e:
            logger.warning(
                f"NarrativeEngine: Could not connect to Ollama ({e}). "
                "Using rule-based fallback."
            )

    def generate(self, report) -> NarrativeOutput:
        """
        Generate a NarrativeOutput from a ScoreReport.

        Tries the LLM first; falls back to rule-based generation on any failure.
        """
        if not self._use_llm:
            logger.info("NarrativeEngine: Using rule-based fallback (no LLM).")
            return _rule_based_narrative(report)

        prompt = _build_prompt(report)

        try:
            logger.info("NarrativeEngine: Invoking LLM for narrative generation...")
            response = self._llm.invoke(prompt)

            # LangChain returns an AIMessage; extract the string content
            raw_text = response.content if hasattr(response, "content") else str(response)

            # Parse JSON — with format="json" this should always be clean
            data = json.loads(raw_text)

            narrative = NarrativeOutput(
                strengths=data.get("strengths", []),
                deficiencies=data.get("deficiencies", []),
                recommendations=data.get("recommendations", []),
                reflective_qs=data.get("reflective_qs", []),
                final_summary=data.get("final_summary", ""),
            )

            # Safety net: if LLM returned empty sections, fill with fallback
            fallback = _rule_based_narrative(report)
            if not narrative.strengths:
                narrative.strengths = fallback.strengths
            if not narrative.deficiencies:
                narrative.deficiencies = fallback.deficiencies
            if not narrative.recommendations:
                narrative.recommendations = fallback.recommendations
            if not narrative.reflective_qs:
                narrative.reflective_qs = fallback.reflective_qs
            if not narrative.final_summary:
                narrative.final_summary = fallback.final_summary

            logger.info("NarrativeEngine: LLM narrative generated successfully.")
            return narrative

        except json.JSONDecodeError as e:
            logger.warning(
                f"NarrativeEngine: LLM returned malformed JSON ({e}). "
                "Falling back to rule-based narrative."
            )
            return _rule_based_narrative(report)

        except Exception as e:
            logger.warning(
                f"NarrativeEngine: LLM call failed ({e}). "
                "Falling back to rule-based narrative."
            )
            return _rule_based_narrative(report)
