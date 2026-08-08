"""
Local test script for backend/debrief_service.py
"""

import json
import logging
from pathlib import Path
from debrief_service import generate_debrief

logging.basicConfig(level=logging.INFO)

def main():
    transcript_path = Path(__file__).parent / "debriefing" / "dummy" / "ses_scn_001.json"
    print(f"Loading transcript from: {transcript_path}")
    with open(transcript_path, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    print("Calling generate_debrief(session_data)...")
    result = generate_debrief(session_data)

    print("\n" + "="*50)
    print("DEBRIEF SERVICE TEST RESULT:")
    print("="*50)
    print(f"Overall Score   : {result['overall_score']}")
    print(f"Grade           : {result['grade']}")
    print(f"Findings Count  : {len(result['findings'])}")
    print(f"Domain Scores   : {len(result['domain_scores'])} domains scored")
    print(f"Timeline Events : {len(result['timeline']['events'])} events")
    print(f"PDF Path        : {result['pdf_path']}")
    print(f"PDF Exists      : {Path(result['pdf_path']).exists()}")
    print("="*50)

    assert result["overall_score"] is not None
    assert result["grade"] is not None
    assert isinstance(result["findings"], list)
    assert isinstance(result["timeline"], dict)
    assert isinstance(result["domain_scores"], list)
    assert isinstance(result["narrative_report"], dict)
    assert Path(result["pdf_path"]).exists()
    print("TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
