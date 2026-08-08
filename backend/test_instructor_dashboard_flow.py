"""
Verification script for Instructor Dashboard Communication & SimMan ECG Engine.
"""

import json
import requests
import asyncio
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/ecg"

async def test_instructor_flow():
    print("1. Logging in as instructor...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "instructor", "password": "instructor123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   [OK] Login successful.")

    print("\n2. Creating simulation session...")
    resp = requests.post(f"{BASE_URL}/session/create", headers=headers)
    assert resp.status_code == 200, f"Session create failed: {resp.text}"
    session_code = resp.json()["session_code"]
    print(f"   [OK] Session created: {session_code}")

    print("\n3. Fetching monitor state (GET /session/{session_code}/state)...")
    resp = requests.get(f"{BASE_URL}/session/{session_code}/state", headers=headers)
    assert resp.status_code == 200, f"Get state failed: {resp.text}"
    state = resp.json()
    print(f"   [OK] Initial Monitor State retrieved (HR={state.get('heartRate')}, SpO2={state.get('spo2')}, Rhythm={state.get('ecgRhythm')})")

    print("\n4. Connecting to SimMan ECG Engine WebSocket (ws://localhost:8000/ws/ecg)...")
    async with websockets.connect(WS_URL) as ws:
        # Receive initial state snapshot
        init_snapshot_raw = await ws.recv()
        init_snapshot = json.loads(init_snapshot_raw)
        print(f"   [OK] Received initial WebSocket state snapshot: type={init_snapshot.get('type')}")

        # Send SET_STATE command (Simulating instructor parameter update)
        command = {
            "type": "SET_STATE",
            "payload": {
                "rhythm": "VF",
                "hr": 0,
                "spo2": 0
            }
        }
        await ws.send(json.dumps(command))
        print("   [OK] Sent SET_STATE command to change rhythm to VF")

        # Receive snapshot response
        resp_raw = await ws.recv()
        resp_data = json.loads(resp_raw)
        print(f"   [OK] Received engine update snapshot: rhythm={resp_data.get('payload', {}).get('rhythm')}")

        # Receive intelligence payload
        intel_raw = await ws.recv()
        intel_data = json.loads(intel_raw)
        print(f"   [OK] Received rhythm intelligence payload: type={intel_data.get('type')}, label={intel_data.get('payload', {}).get('rhythm_label')}")

    print("\n" + "=" * 60)
    print("INSTRUCTOR DASHBOARD SIMULATOR FLOW VERIFIED SUCCESSFULLY!")
    print("=" * 60)

def main():
    asyncio.run(test_instructor_flow())

if __name__ == "__main__":
    main()
