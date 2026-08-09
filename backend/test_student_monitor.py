# backend/test_student_monitor.py
import asyncio
import requests
import socketio
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_student_monitor():
    print("=" * 70)
    print("STARTING STUDENT MONITOR REAL-TIME SYNCHRONIZATION TEST SUITE")
    print("=" * 70)

    # 1. Instructor Login
    print("\n1. Logging in as Instructor...")
    inst_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "instructor", "password": "instructor123", "role": "instructor"}
    )
    if inst_resp.status_code != 200:
        print(f"[FAIL] Instructor login failed with status {inst_resp.status_code}")
        sys.exit(1)

    inst_data = inst_resp.json()
    inst_token = inst_data["access_token"]
    print(f"   [PASS] Instructor authenticated. Token acquired.")

    # 2. Student Login
    print("\n2. Logging in as Student...")
    stud_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "student", "password": "student123", "role": "student"}
    )
    if stud_resp.status_code != 200:
        print(f"[FAIL] Student login failed with status {stud_resp.status_code}")
        sys.exit(1)

    stud_data = stud_resp.json()
    stud_token = stud_data["access_token"]
    print(f"   [PASS] Student authenticated. Token acquired.")

    # 3. Instructor creates simulation session with Case A vitals
    print("\n3. Instructor launching simulation session with Case spec...")
    spec_a = {
        "name": "Anaphylactic Shock Case",
        "patient_details": {
            "patientName": "Emma Watson",
            "age": "28",
            "gender": "Female",
            "bloodGroup": "O-",
            "chiefComplaint": "Severe dyspnea and facial swelling after peanut exposure",
            "diagnosis": "Anaphylactic Shock",
            "triageLevel": "Emergency"
        },
        "initial_readings": {
            "heartRate": 135,
            "spo2": 89,
            "bloodPressure": {"systolic": 85, "diastolic": 50},
            "respiratoryRate": 28,
            "etco2": 28,
            "ecgRhythm": "Sinus Tachycardia"
        }
    }
    
    sess_resp = requests.post(
        f"{BASE_URL}/session/create",
        headers={"Authorization": f"Bearer {inst_token}"},
        json={"force_new": True, "spec": spec_a}
    )
    if sess_resp.status_code != 200:
        print(f"[FAIL] Session creation failed with status {sess_resp.status_code}")
        sys.exit(1)

    session_code = sess_resp.json()["session_code"]
    print(f"   [PASS] Simulation session created with code: {session_code}")

    # 4. Verify initial monitor_state via REST API
    print("\n4. Verifying session state initialized with scenario vitals...")
    state_resp = requests.get(
        f"{BASE_URL}/session/{session_code}/state",
        headers={"Authorization": f"Bearer {inst_token}"}
    )
    if state_resp.status_code != 200:
        print(f"[FAIL] Fetching session state failed")
        sys.exit(1)

    initial_state = state_resp.json()
    assert initial_state["HR"] == 135, f"Expected HR 135, got {initial_state['HR']}"
    assert initial_state["SpO2"] == 89, f"Expected SpO2 89, got {initial_state['SpO2']}"
    assert initial_state["ABP_sys"] == 85, f"Expected ABP_sys 85, got {initial_state['ABP_sys']}"
    assert initial_state["initial_readings_hidden"] is False, "Expected initial_readings_hidden False"
    print(f"   [PASS] Initial state verified (HR: {initial_state['HR']}, SpO2: {initial_state['SpO2']}%, BP: {initial_state['ABP_sys']}/{initial_state['ABP_dia']}).")

    # 5. Socket.IO Synchronization Test
    print("\n5. Testing real-time Socket.IO synchronization with Student client...")
    
    sio_student = socketio.Client()
    received_events = []

    @sio_student.on("join_confirmed")
    def on_join_confirmed(data):
        received_events.append(("join_confirmed", data))
        print("   [Socket.IO Student] Join confirmed!")

    @sio_student.on("state_update")
    def on_state_update(data):
        received_events.append(("state_update", data))
        print(f"   [Socket.IO Student] Received state_update (HR: {data.get('HR')}, SpO2: {data.get('SpO2')})")

    @sio_student.on("faculty_comment")
    def on_faculty_comment(data):
        received_events.append(("faculty_comment", data))
        print(f"   [Socket.IO Student] Received faculty comment: '{data.get('comment')}' from {data.get('from')}")

    sio_student.connect(BASE_URL)
    sio_student.emit("join_session", {"session_code": session_code, "token": stud_token})
    sio_student.sleep(1)

    assert any(e[0] == "join_confirmed" for e in received_events), "Student failed to receive join_confirmed"
    print("   [PASS] Student joined session successfully via Socket.IO.")

    # 6. Instructor sends faculty comment & vitals update
    print("\n6. Instructor updating vitals and sending instructor message...")
    
    sio_instructor = socketio.Client()
    sio_instructor.connect(BASE_URL)
    sio_instructor.emit("join_session", {"session_code": session_code, "token": inst_token})
    sio_instructor.sleep(0.5)

    sio_instructor.emit("faculty_comment", {
        "session_code": session_code,
        "comment": "Administer 0.3mg Epinephrine IM immediately!",
        "from": "Instructor"
    })
    sio_instructor.sleep(0.5)

    sio_instructor.emit("update_rhythm", {
        "session_code": session_code,
        "HR": 110,
        "SpO2": 95,
        "ABP_sys": 110,
        "ABP_dia": 70
    })
    sio_instructor.sleep(1)

    sio_instructor.disconnect()
    sio_student.disconnect()

    # Validate received events
    comments = [e[1] for e in received_events if e[0] == "faculty_comment"]
    assert len(comments) > 0, "Student did not receive faculty comment"
    assert "Epinephrine" in comments[0]["comment"], "Comment content mismatch"
    print("   [PASS] Faculty comment received by Student client.")

    state_updates = [e[1] for e in received_events if e[0] == "state_update"]
    assert len(state_updates) > 0, "Student did not receive state_update"
    last_state = state_updates[-1]
    assert last_state["HR"] == 110, f"Expected updated HR 110, got {last_state.get('HR')}"
    print(f"   [PASS] Real-time state update verified on Student client (HR: {last_state['HR']}, SpO2: {last_state['SpO2']}%).")

    print("\n" + "=" * 70)
    print("ALL STUDENT MONITOR REAL-TIME SYNCHRONIZATION TESTS PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    test_student_monitor()
