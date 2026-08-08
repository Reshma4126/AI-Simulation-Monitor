"""
Database persistence test for debrief_reports table in MySQL.
"""

import asyncio
import json
from datetime import datetime, timedelta
from database import init_db, get_db_pool, save_debrief_report_async
from debrief_adapter import convert_and_debrief

async def test_persistence():
    print("1. Initializing database tables...")
    await init_db()
    pool = await get_db_pool()

    session_code = "SIM-PERSIST-TEST-001"
    start_time = datetime.utcnow() - timedelta(minutes=10)

    dummy_session = {
        "session_code": session_code,
        "started_at": start_time.isoformat(),
        "ended_at": datetime.utcnow().isoformat(),
        "scenario_name": "Ventricular Fibrillation Test",
        "scenario_type": "VF",
        "team_size": 4,
        "event_log": [
            {"timestamp": (start_time + timedelta(seconds=5)).isoformat(), "event": "Pulse check performed"},
            {"timestamp": (start_time + timedelta(seconds=15)).isoformat(), "event": "CPR initiated - compressions starting"},
            {"timestamp": (start_time + timedelta(seconds=120)).isoformat(), "event": "Defibrillation 200J delivered"},
            {"timestamp": (start_time + timedelta(seconds=300)).isoformat(), "event": "ROSC achieved"}
        ]
    }

    print("\n2. Executing convert_and_debrief()...")
    result1 = convert_and_debrief(dummy_session)
    print(f"Report generated: Score = {result1['overall_score']}, Grade = {result1['grade']}")

    print("\n3. Querying debrief_reports table in MySQL...")
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT session_code, overall_score, grade, status, pdf_path, created_at, updated_at FROM debrief_reports WHERE session_code = %s", (session_code,))
            row = await cur.fetchone()

            print("\n" + "=" * 60)
            print("MYSQL RECORD FOUND:")
            print("=" * 60)
            print(f"  Session Code  : {row[0]}")
            print(f"  Overall Score : {row[1]}")
            print(f"  Grade         : {row[2]}")
            print(f"  Status        : {row[3]}")
            print(f"  PDF Path      : {row[4]}")
            print(f"  Created At    : {row[5]}")
            print(f"  Updated At    : {row[6]}")
            print("=" * 60)

            assert row is not None, "Record not found in MySQL!"
            assert row[0] == session_code
            assert row[3] == "COMPLETED"

    print("\n4. Testing duplicate update (re-running debrief)...")
    result2 = convert_and_debrief(dummy_session)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM debrief_reports WHERE session_code = %s", (session_code,))
            count_res = await cur.fetchone()
            record_count = count_res[0]
            print(f"Total records in MySQL for session_code '{session_code}': {record_count}")

            assert record_count == 1, f"Expected 1 record (no duplicates), found {record_count}!"

    print("\nDATABASE PERSISTENCE TEST PASSED SUCCESSFULLY!")

def main():
    asyncio.run(test_persistence())

if __name__ == "__main__":
    main()
