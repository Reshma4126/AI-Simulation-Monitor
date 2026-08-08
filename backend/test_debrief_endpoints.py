"""
Verification test for FastAPI Debrief Endpoints.
"""

import time
import requests

BASE_URL = "http://localhost:8000"

def main():
    print("1. Logging in as instructor...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "instructor", "password": "instructor123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   Login successful.")

    print("\n2. Creating a test session...")
    resp = requests.post(f"{BASE_URL}/session/create", headers=headers)
    assert resp.status_code == 200, f"Session create failed: {resp.text}"
    session_code = resp.json()["session_code"]
    print(f"   Session created: {session_code}")

    print("\n3. Testing GET /api/debrief/status/{session_code}...")
    resp = requests.get(f"{BASE_URL}/api/debrief/status/{session_code}", headers=headers)
    assert resp.status_code == 200, f"Status check failed: {resp.text}"
    status_data = resp.json()
    print(f"   Status response: {status_data}")
    assert status_data["session_code"] == session_code
    assert status_data["status"] in ("pending", "running", "completed")

    print("\n4. Testing POST /api/debrief/generate/{session_code}...")
    start_t = time.time()
    resp = requests.post(f"{BASE_URL}/api/debrief/generate/{session_code}", headers=headers)
    elapsed = time.time() - start_t
    print(f"   Response time: {elapsed:.3f}s (Non-blocking background launch, DB auth latency included)")
    assert resp.status_code == 200, f"Generate failed: {resp.text}"
    assert elapsed < 5.0, "Endpoint blocked execution!"
    gen_data = resp.json()
    print(f"   Generate response: {gen_data}")
    assert gen_data["status"] == "running"

    print("\n5. Waiting for background debrief execution...")
    for i in range(15):
        time.sleep(2)
        resp = requests.get(f"{BASE_URL}/api/debrief/status/{session_code}", headers=headers)
        current_status = resp.json().get("status")
        print(f"   [{i+1}s] Current status: {current_status}")
        if current_status == "completed":
            break

    assert current_status == "completed", f"Debrief did not complete in time, status: {current_status}"

    print("\n6. Testing GET /api/debrief/{session_code}...")
    resp = requests.get(f"{BASE_URL}/api/debrief/{session_code}", headers=headers)
    assert resp.status_code == 200, f"Get debrief failed: {resp.text}"
    report = resp.json()
    print(f"   Report retrieved! Score: {report.get('overall_score')}, Grade: {report.get('grade')}, Status: {report.get('status')}")
    assert report["session_code"] == session_code
    assert "debrief" in report

    print("\n7. Testing GET /api/reports/{session_code} (PDF Stream)...")
    resp = requests.get(f"{BASE_URL}/api/reports/{session_code}", headers=headers)
    assert resp.status_code == 200, f"PDF stream failed: {resp.text}"
    assert resp.headers.get("content-type") == "application/pdf"
    pdf_bytes_len = len(resp.content)
    print(f"   PDF stream successful! Received {pdf_bytes_len} bytes.")
    assert pdf_bytes_len > 1000, "PDF stream empty or invalid!"

    print("\n" + "=" * 50)
    print("ALL FASTAPI DEBRIEF ENDPOINTS TESTED AND PASSED!")
    print("=" * 50)

if __name__ == "__main__":
    main()
