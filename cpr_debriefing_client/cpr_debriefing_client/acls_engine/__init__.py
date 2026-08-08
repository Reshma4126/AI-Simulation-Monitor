"""
acls_engine — ACLS Rule Engine Package
=======================================
AI-powered CPR Training Analysis & Debriefing System
AHA 2025 Guidelines | Educational / Simulation Use Only

Supported algorithms:
  - cardiac_arrest  (VF | pVT | PEA | asystole)
  - tachyarrhythmia_with_pulse  (narrow/wide QRS, stable/unstable, WPW)
  - bradycardia_with_pulse  (nodal / infranodal / transplant)
  - megacode  (multi-rhythm scenario)

Usage:
    from acls_engine import ACLSEngine

    engine = ACLSEngine()
    findings = engine.evaluate(events_data)
    engine.print_report(events_data)
    engine.save_findings(events_data, output_path="findings_output.json")
"""

from .engine import ACLSEngine
from .scenario_classifier import ScenarioClassifier

__all__ = ["ACLSEngine", "ScenarioClassifier"]
__version__ = "1.0.0"
