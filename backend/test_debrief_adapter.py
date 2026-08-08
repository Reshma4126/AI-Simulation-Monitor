"""
Verification script for DebriefAdapter and backend integration.
"""

from datetime import datetime, timedelta
from pathlib import Path
from debrief_adapter import convert_and_debrief, DebriefAdapter

def main():
    print("Preparing dummy completed simulation session data...")

    start_time = datetime.utcnow() - timedelta(minutes=12)
    end_time = datetime.utcnow()

    dummy_session = {
        "id": 101,
        "session_code": "SIM-ACLS-TEST-001",
        "started_at": start_time.isoformat(),
        "ended_at": end_time.isoformat(),
        "is_active": False,
        "created_by_username": "Dr. Sarah Chen",
        "scenario_name": "Adult ACLS - Ventricular Fibrillation",
        "scenario_type": "VF",
        "team_size": 6,
        "event_log": [
            {
                "timestamp": (start_time + timedelta(seconds=8)).isoformat(),
                "event": "Pulse check performed - no pulse felt. Rhythm: Ventricular Fibrillation"
            },
            {
                "timestamp": (start_time + timedelta(seconds=20)).isoformat(),
                "event": "Cardiac arrest confirmed. Call for help and start CPR."
            },
            {
                "timestamp": (start_time + timedelta(seconds=32)).isoformat(),
                "event": "CPR initiated: high quality chest compressions starting."
            },
            {
                "timestamp": (start_time + timedelta(seconds=110)).isoformat(),
                "event": "Rhythm check performed. Ventricular Fibrillation detected. Shock advised."
            },
            {
                "timestamp": (start_time + timedelta(seconds=168)).isoformat(),
                "event": "Defibrillator charged to 200J. Shock delivered!"
            },
            {
                "timestamp": (start_time + timedelta(seconds=190)).isoformat(),
                "event": "Pulse check performed post-shock."
            },
            {
                "timestamp": (start_time + timedelta(seconds=220)).isoformat(),
                "event": "CPR resumed immediately."
            },
            {
                "timestamp": (start_time + timedelta(seconds=270)).isoformat(),
                "event": "Epinephrine 1mg IV ordered by Team Leader."
            },
            {
                "timestamp": (start_time + timedelta(seconds=330)).isoformat(),
                "event": "Epinephrine 1mg IV administered by Nurse."
            },
            {
                "timestamp": (start_time + timedelta(seconds=562)).isoformat(),
                "event": "Advanced airway Endotracheal Tube 7.5mm placed."
            },
            {
                "timestamp": (start_time + timedelta(seconds=650)).isoformat(),
                "event": "Rhythm check shows Sinus Rhythm. Pulse present! ROSC achieved."
            }
        ]
    }

    dummy_monitor_state = {
        "HR": 0.0,
        "rhythm": "Ventricular Fibrillation",
        "ABP_sys": 0.0,
        "ABP_dia": 0.0,
        "SpO2": 0.0,
        "etCO2": 12.0,
        "avRR": 0.0,
        "Tblood": 37.0,
        "eyes_state": "Closed"
    }

    print("Running convert_and_debrief()...")
    result = convert_and_debrief(
        session=dummy_session,
        event_log=dummy_session["event_log"],
        monitor_state=dummy_monitor_state
    )

    print("\n" + "=" * 50)
    print("VERIFICATION RESULTS:")
    print("=" * 50)
    print(f"Overall Score    : {result['overall_score']}")
    print(f"Grade            : {result['grade']}")
    print(f"Findings Count   : {len(result['findings'])}")
    print(f"Timeline Events  : {len(result['timeline']['events'])}")
    print(f"Domain Scores    : {len(result['domain_scores'])} domains")
    print(f"PDF Path         : {result['pdf_path']}")
    print(f"PDF Report Exists: {Path(result['pdf_path']).exists()}")
    print("=" * 50)

    assert result["overall_score"] is not None
    assert result["grade"] is not None
    assert isinstance(result["findings"], list)
    assert isinstance(result["timeline"], dict)
    assert isinstance(result["domain_scores"], list)
    assert Path(result["pdf_path"]).exists()

    print("\nSUCCESS: DebriefAdapter verification completed without exceptions!")

if __name__ == "__main__":
    main()
