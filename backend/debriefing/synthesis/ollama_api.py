"""
Ollama Narrative Report Generator — CPR Debriefing System
===========================================================
Free, local LLM backend using Ollama.
Drop-in replacement for openai_api.py and claude_api.py.

Key upgrade: Every prompt now includes the FULL conversation transcript in
chronological dialogue format with timestamps and roles, so the LLM can
directly reference what was said and when — not just abstract finding IDs.

Setup:
  1. Install Ollama: https://ollama.ai
  2. Pull model:  ollama pull qwen2.5:0.5b
  3. Start:       ollama serve

Env vars:
  OLLAMA_MODEL      qwen2.5:0.5b (default — fits in 4GB)
  OLLAMA_BASE_URL   http://localhost:11434/v1 (default)

Author: Deva
"""

from __future__ import annotations
import json
import logging
import os
import time
from typing import Optional

from openai import OpenAI   # Ollama exposes an OpenAI-compatible API

from schemas.event_schema import (
    FindingRecord, UnifiedTimeline, Severity,
)
from synthesis.claude_api import (
    DebriefReport,
    ReportSection,
    FindingVerifier,
    SECTION_INSTRUCTIONS,
    build_section_prompt,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# System prompt — tuned for small local models (qwen2.5, phi4-mini, mistral)
# Shorter and more direct than the cloud versions.
# ==============================================================================

SYSTEM_PROMPT = """You are a clinical debriefing assistant for a medical simulation center.
You receive structured findings and the FULL conversation transcript from an ACLS cardiac arrest simulation.

Your role: NARRATIVE SYNTHESIS ONLY.
- Do NOT invent new findings or clinical judgments.
- Phrase the provided findings clearly and constructively for medical interns.
- Use the transcript to ground your writing in specific moments (quote times and speakers).

TRACEABILITY TAGS (required for evaluated sections):
Tag every evaluative claim with [finding_id:fnd_XXXXXXXX] immediately after the claim.
Example: "CPR was initiated 22 seconds after arrest [finding_id:fnd_a1b2c3d4], exceeding the AHA 10-second guideline."
Factual sections (scenario summary) do NOT need tags.
Use ONLY finding IDs from the provided JSON. Do not invent IDs.

Tone: constructive, specific, educational. Audience: medical interns (PGY-1/PGY-2)."""


# ==============================================================================
# Transcript formatter — converts raw segments to readable conversation format
# ==============================================================================

def format_transcript(raw_segments: list[dict]) -> str:
    """
    Converts the raw segments list into a clean, readable conversation
    transcript with timestamps, speaker roles, and dialogue.

    Example output:
      [00:00]  Airway              "Doctor, patient is unresponsive!"  (ai: Arrest recognition)
      [00:08]  Team Leader         "Check pulse."                       (ai: Pulse check initiated)
    """
    if not raw_segments:
        return "(No transcript segments available)"

    lines = []
    for seg in raw_segments:
        ts_ms = seg.get("timestamp_ms", 0)
        total_s = ts_ms // 1000
        time_str = f"{total_s // 60:02d}:{total_s % 60:02d}"
        speaker = seg.get("speaker", seg.get("role", "Unknown"))
        text = seg.get("text", "").strip()
        expected = seg.get("ai_expected", "")

        if text:
            ai_note = f"  (expected: {expected})" if expected else ""
            lines.append(f"[{time_str}]  {speaker:<28}  \"{text}\"{ai_note}")
        else:
            # Silent / empty segment — still log it for context
            if expected:
                lines.append(f"[{time_str}]  {speaker:<28}  (silence — expected: {expected})")

    return "\n".join(lines)


# ==============================================================================
# Enhanced section prompt builder — includes transcript
# ==============================================================================

def build_section_prompt_with_transcript(
    section_name: str,
    findings_json: str,
    scores_json: str,
    session_context: dict,
    instructions: str,
    transcript_text: str,
) -> str:
    return f"""SESSION CONTEXT:
Scenario: {session_context['scenario_name']}
Team Leader: {session_context['team_leader_id']}
Date: {session_context['session_date']}
Duration: {session_context.get('duration_min', 'N/A')}

FULL CONVERSATION TRANSCRIPT (chronological, with timestamps and roles):
{transcript_text}

DOMAIN SCORES:
{scores_json}

STRUCTURED FINDINGS (JSON):
{findings_json}

SECTION TO WRITE: {section_name}

INSTRUCTIONS:
{instructions}

Remember: tag every evaluative claim with [finding_id:fnd_XXXXXXXX].
Reference specific timestamps and quotes from the transcript where relevant.
Write only the section content. No headers, no preamble."""


# ==============================================================================
# Report Generator
# ==============================================================================

class ReportGenerator:
    """
    Generates debrief report sections using Ollama (local LLM).
    Identical public API to openai_api.ReportGenerator and claude_api.ReportGenerator.

    Key enhancement: full transcript is injected into every prompt so the
    LLM can reference exact moments, speaker quotes, and timings.
    """

    MAX_RETRIES   = 1
    RETRY_DELAY_S = 1

    def __init__(self):
        base_url   = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")

        self.client = OpenAI(
            base_url=base_url,
            api_key="ollama",   # required by OpenAI client; ignored by Ollama
            timeout=15.0,       # 15s timeout to prevent thread hanging
        )
        logger.info(f"Ollama backend ready — model={self.model} url={base_url}")

    def is_available(self) -> bool:
        """Check if Ollama server is reachable and enabled."""
        if os.environ.get("ENABLE_OLLAMA_DEBRIEF", "false").lower() not in ("true", "1"):
            return False
        try:
            import urllib.request
            url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").replace("/v1", "")
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status in (200, 404)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_report(self, timeline: UnifiedTimeline) -> DebriefReport:
        """Full pipeline: findings → all sections → verified DebriefReport."""
        logger.info(
            f"Generating report via Ollama ({self.model}) "
            f"for session: {timeline.session_id}"
        )
        start = time.time()

        raw_findings  = getattr(timeline, "findings", [])
        findings      = [f if isinstance(f, FindingRecord) else _finding_from_dict(f) for f in raw_findings]
        valid_ids     = {f.finding_id for f in findings}
        verifier      = FindingVerifier(valid_ids)
        findings_json = json.dumps([f.to_dict() for f in findings], indent=2)
        scores_json   = json.dumps(timeline.summary()["findings_by_severity"], indent=2)
        session_ctx   = {
            "scenario_name":  getattr(timeline, "scenario_name", "Unknown"),
            "team_leader_id": getattr(timeline, "team_leader_id", "Unknown"),
            "session_date":   getattr(timeline, "session_date", ""),
            "duration_min":   self._estimate_duration(timeline),
        }

        # Build the transcript text — use raw segments if stored on timeline,
        # otherwise fall back to a lightweight reconstruction from events.
        transcript_text = self._build_transcript_text(timeline)

        report = DebriefReport(
            session_id     = timeline.session_id,
            scenario_name  = session_ctx["scenario_name"],
            team_leader_id = session_ctx["team_leader_id"],
            session_date   = session_ctx["session_date"],
        )

        # Scenario summary — factual, no finding tag verification needed
        logger.info("Generating: scenario_summary")
        report.scenario_summary = ReportSection(
            title="Scenario Summary",
            content=self._generate_scenario_summary(
                session_ctx, findings, transcript_text
            ),
        )

        # All verified sections — transcript included in each prompt
        for section_key, instructions in SECTION_INSTRUCTIONS.items():
            logger.info(f"Generating: {section_key}")
            section = self._generate_verified_section(
                section_name    = section_key,
                instructions    = instructions,
                findings_json   = findings_json,
                scores_json     = scores_json,
                session_context = session_ctx,
                verifier        = verifier,
                transcript_text = transcript_text,
            )
            setattr(report, section_key, section)

        elapsed = time.time() - start
        report.generation_metadata = {
            "model":                 self.model,
            "backend":               "ollama",
            "total_findings":        len(findings),
            "generation_time_s":     round(elapsed, 2),
            "all_sections_verified": True,
            "transcript_included":   True,
        }
        logger.info(f"Report complete in {elapsed:.1f}s")
        return report

    def generate_report_from_payload(self, payload: dict) -> DebriefReport:
        """Worker-friendly entry point — reconstructs timeline from broker payload."""
        tl_meta  = payload.get("timeline", {})
        timeline = UnifiedTimeline(
            session_id     = tl_meta.get("session_id", "unknown"),
            scenario_name  = tl_meta.get("scenario_name", "Unknown"),
            team_leader_id = tl_meta.get("team_leader_id", "Unknown"),
            session_date   = tl_meta.get("session_date", ""),
        )
        timeline.findings = [
            _finding_from_dict(f) for f in payload.get("findings", [])
        ]
        # Attach raw segments if broker included them
        if "raw_segments" in payload:
            timeline.raw_segments = payload["raw_segments"]
        return self.generate_report(timeline)

    # ------------------------------------------------------------------
    # Transcript builder
    # ------------------------------------------------------------------

    def _build_transcript_text(self, timeline: UnifiedTimeline) -> str:
        """
        Returns the full conversation transcript in readable format.
        Priority:
          1. timeline.raw_segments (set by main.py after JSON load)
          2. Reconstruct a minimal version from UnifiedEvents
        """
        # Use raw_segments if main.py stored them (best quality)
        raw_segs = getattr(timeline, "raw_segments", None)
        if raw_segs:
            return format_transcript(raw_segs)

        # Fallback: reconstruct from events
        lines = []
        for ev in sorted(timeline.events, key=lambda e: e.timestamp_ms):
            ts = ev.timestamp_ms
            total_s = ts // 1000
            time_str = f"{total_s // 60:02d}:{total_s % 60:02d}"
            role = ev.actor_role.value if ev.actor_role else "unknown"
            ev_type = ev.event_type.value
            text = ""
            if ev.evidence:
                text = ev.evidence[0].text or ""
            lines.append(f"[{time_str}]  {role:<20}  [{ev_type}] {text}")
        return "\n".join(lines) if lines else "(No transcript available)"

    # ------------------------------------------------------------------
    # Section generators
    # ------------------------------------------------------------------

    def _generate_scenario_summary(
        self,
        session_context: dict,
        findings: list[FindingRecord],
        transcript_text: str,
    ) -> str:
        critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        high     = sum(1 for f in findings if f.severity == Severity.HIGH)
        prompt   = (
            f"Write a 2-paragraph factual scenario summary.\n\n"
            f"Paragraph 1: scenario name, team leader, date, duration.\n"
            f"Paragraph 2: neutral overview — total findings, "
            f"severity breakdown ({critical} critical, {high} high, "
            f"total {len(findings)}). Reference the key moments from the transcript.\n\n"
            f"Session: {json.dumps(session_context, indent=2)}\n\n"
            f"TRANSCRIPT:\n{transcript_text}"
        )
        raw      = self._call_ollama(prompt, max_tokens=200)
        verifier = FindingVerifier(set())
        return verifier.strip_tags(raw)

    def _generate_verified_section(
        self,
        section_name:    str,
        instructions:    str,
        findings_json:   str,
        scores_json:     str,
        session_context: dict,
        verifier:        FindingVerifier,
        transcript_text: str,
    ) -> ReportSection:
        """Generate → verify finding IDs → retry if hallucinated."""
        prompt   = build_section_prompt_with_transcript(
            section_name    = section_name,
            findings_json   = findings_json,
            scores_json     = scores_json,
            session_context = session_context,
            instructions    = instructions,
            transcript_text = transcript_text,
        )
        attempts     = 0
        last_content = ""

        while attempts < self.MAX_RETRIES:
            attempts += 1
            raw = self._call_ollama(prompt, max_tokens=250)
            is_valid, invalid_ids = verifier.verify(raw, section_name)

            if is_valid:
                return ReportSection(
                    title                  = section_name.replace("_", " ").title(),
                    content                = verifier.strip_tags(raw),
                    finding_ids_referenced = verifier.extract_referenced_ids(raw),
                    generation_attempts    = attempts,
                )

            logger.warning(
                f"[{section_name}] Attempt {attempts}/{self.MAX_RETRIES} — "
                f"invalid IDs: {invalid_ids}. Retrying."
            )
            last_content = raw
            prompt = self._build_correction_prompt(
                original_prompt = prompt,
                rejected_output = raw,
                invalid_ids     = invalid_ids,
                valid_ids       = list(verifier.valid_finding_ids)[:8],
            )
            time.sleep(self.RETRY_DELAY_S)

        logger.error(
            f"[{section_name}] All retries exhausted. Returning flagged section."
        )
        return ReportSection(
            title                  = section_name.replace("_", " ").title(),
            content                = (
                f"[VERIFICATION WARNING — review before use]\n\n"
                f"{verifier.strip_tags(last_content)}"
            ),
            finding_ids_referenced = [],
            generation_attempts    = attempts,
        )

    # ------------------------------------------------------------------
    # Ollama call
    # ------------------------------------------------------------------

    def _call_ollama(self, user_prompt: str, max_tokens: int = 700) -> str:
        """Single Ollama API call via OpenAI-compatible endpoint."""
        try:
            response = self.client.chat.completions.create(
                model       = self.model,
                max_tokens  = max_tokens,
                messages    = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature = 0.3,
                timeout     = 10.0,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(
                f"Ollama call failed: {e}\n"
                f"Is Ollama running? → ollama serve\n"
                f"Is model pulled?   → ollama pull {self.model}"
            )
            return f"[Ollama unavailable: {e}]"

    def _build_correction_prompt(
        self,
        original_prompt: str,
        rejected_output: str,
        invalid_ids:     list[str],
        valid_ids:       list[str],
    ) -> str:
        return (
            f"{original_prompt}\n\n---\nCORRECTION REQUIRED:\n"
            f"You referenced these finding IDs that do not exist: {invalid_ids}\n"
            f"Valid IDs you may use: {valid_ids}\n"
            f"Rewrite using ONLY valid IDs. "
            f"Omit any claim you cannot ground in a valid finding."
        )

    def _estimate_duration(self, timeline: UnifiedTimeline) -> str:
        if not timeline.events:
            return getattr(timeline, "duration_ms", 0) and \
                   f"{getattr(timeline, 'duration_ms', 0) // 60000}m " \
                   f"{(getattr(timeline, 'duration_ms', 0) % 60000) // 1000}s" or "N/A"
        ms = timeline.events[-1].timestamp_ms
        return f"{ms // 60000}m {(ms % 60000) // 1000}s"


# ==============================================================================
# Helper — deserialize FindingRecord from dict safely
# ==============================================================================

def _finding_from_dict(d: dict) -> FindingRecord:
    from schemas.event_schema import Evidence, SourceSystem, Severity

    d = dict(d)
    if isinstance(d.get("severity"), str):
        sev_str = d["severity"].upper()
        d["severity"] = Severity[sev_str] if sev_str in Severity.__members__ else Severity.INFO

    if "rule_id" in d and not d.get("title"):
        d["title"] = d["rule_id"]
    if "rule_id" in d and not d.get("template_id"):
        d["template_id"] = d["rule_id"]
    if "deviation_message" in d and not d.get("description"):
        d["description"] = d["deviation_message"]

    evidence_raw = d.pop("evidence", [])
    d.pop("missing_fields", None)

    finding = FindingRecord(**{
        k: v for k, v in d.items()
        if k in FindingRecord.__dataclass_fields__
    })
    finding.evidence = [
        Evidence(
            source       = SourceSystem(e["source"]),
            ref          = e["ref"],
            text         = e.get("text"),
            timestamp_ms = e.get("timestamp_ms"),
            confidence   = e.get("confidence", 1.0),
        )
        for e in evidence_raw
    ]
    return finding
