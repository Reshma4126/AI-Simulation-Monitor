"""
End-to-End Automated Validation Test for AI Simulation Debriefing.
"""

import time
import json
import os
import requests
import asyncio
import aiomysql

BASE_URL = "http://localhost:8000"

async def update_session_event_log(session_code, event_log):
    """Directly populate realistic simulation event log in DB for E2E testing."""
    from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
    conn = await aiomysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=DB_NAME,
        autocommit=True,
        ssl=ssl_ctx
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE sessions SET event_log = %s WHERE session_code = %s",
                (json.dumps(event_log), session_code)
            )
            print(f"[E2E] Updated event log in MySQL for session: {session_code} ({len(event_log)} events)")
    finally:
        conn.close()

def main():
    print("=" * 70)
    print("STARTING FULL END-TO-END VALIDATION SUITE")
    print("=" * 70)

    # 1. Login
    print("\n[STEP 1] Login as instructor...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "instructor", "password": "instructor123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[OK] Login successful. Token acquired.")

    # 2. Create Simulation
    print("\n[STEP 2] Create simulation session...")
    resp = requests.post(f"{BASE_URL}/session/create", headers=headers)
    assert resp.status_code == 200, f"Create session failed: {resp.text}"
    session_code = resp.json()["session_code"]
    print(f"[OK] Session created successfully. Code: {session_code}")

    # 3. Run Session (Simulate Active Resuscitation Event Log)
    print("\n[STEP 3] Populated simulated resuscitation event log...")
    now_iso = "2026-08-07T14:00:00.000Z"
    sim_events = [
        {"timestamp": "2026-08-07T14:00:05.000Z", "event": "Pulse check performed - No pulse. VF rhythm identified on monitor."},
        {"timestamp": "2026-08-07T14:00:35.000Z", "event": "Chest compressions initiated at rate 110 bpm with 2 inch depth."},
        {"timestamp": "2026-08-07T14:01:10.000Z", "event": "Defibrillator charged to 200J. Clear team alert issued."},
        {"timestamp": "2026-08-07T14:01:15.000Z", "event": "First Biphasic Defibrillation shock 200J delivered cleanly."},
        {"timestamp": "2026-08-07T14:01:20.000Z", "event": "Compressions immediately resumed post-shock."},
        {"timestamp": "2026-08-07T14:02:30.000Z", "event": "Epinephrine 1mg IV push administered per ACLS guidelines."},
        {"timestamp": "2026-08-07T14:03:15.000Z", "event": "Second shock 200J delivered for persistent VF."},
        {"timestamp": "2026-08-07T14:04:00.000Z", "event": "Amiodarone 300mg IV push administered."},
        {"timestamp": "2026-08-07T14:05:30.000Z", "event": "ROSC achieved! Organizing Sinus Rhythm at 88 bpm with BP 115/75."}
    ]
    asyncio.run(update_session_event_log(session_code, sim_events))

    # 4. End Session
    print("\n[STEP 4] End simulation session...")
    t0 = time.time()
    resp = requests.post(f"{BASE_URL}/session/{session_code}/end", headers=headers)
    elapsed_end = time.time() - t0
    assert resp.status_code == 200, f"End session failed: {resp.text}"
    end_json = resp.json()
    print(f"[OK] End session API response ({elapsed_end:.3f}s): {end_json}")
    assert elapsed_end < 5.0, "Session end endpoint blocked!"

    # 5. Verify Background Debrief Generation
    print("\n[STEP 5] Poll debrief status until completion...")
    completed = False
    for i in range(20):
        resp = requests.get(f"{BASE_URL}/api/debrief/status/{session_code}", headers=headers)
        assert resp.status_code == 200, f"Status check failed: {resp.text}"
        st = resp.json().get("status")
        print(f"   [{i*2}s] Debrief Status: {st}")
        if st == "completed":
            completed = True
            break
        elif st == "failed":
            raise RuntimeError("Debrief background generation failed!")
        time.sleep(2)

    assert completed, "Debrief generation timed out!"
    print("[OK] Background debrief pipeline completed successfully.")

    # 6. Verify Database Insertion in MySQL
    print("\n[STEP 6] Querying MySQL database 'debrief_reports' table...")
    from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
    async def query_db():
        conn = await aiomysql.connect(
            host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD, db=DB_NAME, autocommit=True, ssl=ssl_ctx
        )
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM debrief_reports WHERE session_code = %s", (session_code,))
                return await cur.fetchone()
        finally:
            conn.close()

    db_row = asyncio.run(query_db())
    assert db_row is not None, "Record missing in MySQL debrief_reports table!"
    print(f"[OK] DB Record Found! ID={db_row['id']}, Score={db_row['overall_score']}, Grade={db_row['grade']}, Status={db_row['status']}")
    assert db_row["status"] == "COMPLETED"

    # 7. Verify JSON Report API Endpoint
    print("\n[STEP 7] Fetching full JSON debrief report (GET /api/debrief/{session_code})...")
    resp = requests.get(f"{BASE_URL}/api/debrief/{session_code}", headers=headers)
    assert resp.status_code == 200, f"GET /api/debrief failed: {resp.text}"
    report = resp.json()
    print(f"[OK] JSON Report retrieved successfully. Overall Score: {report.get('overall_score')}, Grade: {report.get('grade')}")

    # 8. Verify PDF File Generation on Disk
    print("\n[STEP 8] Verifying PDF file generation on disk...")
    pdf_path = db_row["pdf_path"]
    print(f"   PDF File Path: {pdf_path}")
    assert os.path.exists(pdf_path), f"PDF file does not exist at {pdf_path}"
    pdf_size = os.path.getsize(pdf_path)
    print(f"[OK] PDF File exists on disk ({pdf_size} bytes).")
    assert pdf_size > 1000, "PDF file is empty or corrupted!"

    # 9. Verify PDF Streaming / Download Endpoint
    print("\n[STEP 9] Testing PDF streaming endpoint (GET /api/reports/{session_code})...")
    resp = requests.get(f"{BASE_URL}/api/reports/{session_code}", headers=headers)
    assert resp.status_code == 200, f"PDF download failed: {resp.text}"
    assert resp.headers.get("content-type") == "application/pdf"
    downloaded_bytes = len(resp.content)
    print(f"[OK] PDF stream successful! Downloaded {downloaded_bytes} bytes.")
    assert downloaded_bytes == pdf_size, "Downloaded PDF byte count mismatch!"

    print("\n" + "=" * 70)
    print("FULL E2E VALIDATION SUITE PASSED SUCCESSFULLY! ALL STEPS VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    main()
