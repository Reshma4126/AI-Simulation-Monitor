"""
Root conftest.py — CPR Debriefing System
Ensures the project root is on sys.path for all test modules.
"""
import sys
import os
import pytest

# Make sure project root is importable
sys.path.insert(0, os.path.dirname(__file__))


def pytest_configure(config):
    """Register custom markers to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "integration: real audio hardware tests — requires TEST_WAV_PATH env var"
    )
