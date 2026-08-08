"""
analysis/reporting/__init__.py
-------------------------------
PDF report generation package.

Exports:
    NarrativeEngine   - LLM/rule-based narrative synthesis
    NarrativeOutput   - structured narrative dataclass
    build_pdf_input   - ScoreReport → pdf_engine JSON adapter
    generate_pdf      - pdf_engine renderer
"""

from .narrative_engine import NarrativeEngine, NarrativeOutput
from .pdf_adapter import build_pdf_input
from .pdf_engine import generate_pdf

__all__ = [
    "NarrativeEngine",
    "NarrativeOutput",
    "build_pdf_input",
    "generate_pdf",
]
