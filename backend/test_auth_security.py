"""
Security & Authentication Validation Suite using FastAPI TestClient inside lifespan context.
Tests all core requirements for production-ready role authentication & authorization.
"""

from fastapi.testclient import TestClient
from main import api_app

def test_auth_security_suite():
    print("=" * 70)
    print("STARTING AUTHENTICATION & AUTHORIZATION SECURITY SUITE")
    print("=" * 70)

    with TestClient(api_app) as client:
        # 1. Valid instructor credentials + instructor role
        print("\n1. Testing valid instructor credentials + instructor role...")
        resp = client.post(
            "/auth/login",
            json={"username": "instructor", "password": "instructor123", "role": "instructor"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        instructor_token = data["access_token"]
        assert data["role"] == "instructor"
        assert "access_token" in data
        assert "access_token" in client.cookies
        print("   [PASS] Instructor login successful.")

        # 2. Valid student credentials + student role
        print("\n2. Testing valid student credentials + student role...")
        resp = client.post(
            "/auth/login",
            json={"username": "student", "password": "student123", "role": "student"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        student_token = data["access_token"]
        assert data["role"] == "student"
        assert "access_token" in data
        print("   [PASS] Student login successful.")

        # 3. Instructor credentials + Student role requested (REJECT)
        print("\n3. Testing instructor credentials with student role selected...")
        resp = client.post(
            "/auth/login",
            json={"username": "instructor", "password": "instructor123", "role": "student"}
        )
        assert resp.status_code == 401, f"Expected 401 rejection, got {resp.status_code}"
        print("   [PASS] Correctly rejected role mismatch.")

        # 4. Student credentials + Instructor role requested (REJECT)
        print("\n4. Testing student credentials with instructor role selected...")
        resp = client.post(
            "/auth/login",
            json={"username": "student", "password": "student123", "role": "instructor"}
        )
        assert resp.status_code == 401, f"Expected 401 rejection, got {resp.status_code}"
        print("   [PASS] Correctly rejected role mismatch.")

        # 5. Invalid credentials (REJECT)
        print("\n5. Testing invalid credentials...")
        resp = client.post(
            "/auth/login",
            json={"username": "instructor", "password": "wrongpassword", "role": "instructor"}
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        assert "Invalid username, password, or role." in resp.text
        print("   [PASS] Generic error returned on invalid credentials.")

        # 6. Unauthenticated request to protected endpoint (REJECT)
        print("\n6. Testing unauthenticated request to /auth/me and /session/create...")
        # Clear client cookies to simulate unauthenticated request
        client.cookies.clear()
        resp = client.get("/auth/me")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

        resp = client.post("/session/create")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("   [PASS] Unauthenticated access rejected with HTTP 401.")

        # 7. Demo token bypass test (REJECT)
        print("\n7. Testing demo-token bypass attempt...")
        headers = {"Authorization": "Bearer demo-token"}
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("   [PASS] demo-token bypass attempt correctly blocked.")

        # 8. Student attempting instructor-only API (REJECT 403)
        print("\n8. Testing student attempting instructor-only API (/session/create)...")
        headers = {"Authorization": f"Bearer {student_token}"}
        resp = client.post("/session/create", headers=headers)
        assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"
        print("   [PASS] Student request to instructor API returned HTTP 403 Forbidden.")

        # 9. Instructor access to instructor API (SUCCESS 200)
        print("\n9. Testing instructor access to instructor API (/session/create)...")
        headers = {"Authorization": f"Bearer {instructor_token}"}
        resp = client.post("/session/create", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        print("   [PASS] Instructor successfully accessed instructor endpoint.")

        # 10. Verify /auth/me with valid token
        print("\n10. Testing /auth/me session verification...")
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 200
        user_info = resp.json()
        assert user_info["username"] == "instructor"
        assert user_info["role"] == "instructor"
        print("   [PASS] /auth/me returned correct session user payload.")

        # 11. Logout test
        print("\n11. Testing /auth/logout endpoint...")
        client.cookies.clear()
        login_resp = client.post(
            "/auth/login",
            json={"username": "instructor", "password": "instructor123", "role": "instructor"}
        )
        assert login_resp.status_code == 200
        assert "access_token" in client.cookies
        logout_resp = client.post("/auth/logout")
        assert logout_resp.status_code == 200
        me_after_logout = client.get("/auth/me")
        assert me_after_logout.status_code == 401
        print("   [PASS] Logout successfully invalidated session cookies.")

        print("\n" + "=" * 70)
        print("ALL 11 AUTHENTICATION & AUTHORIZATION SECURITY SUITE TESTS PASSED PERFECTLY!")
        print("=" * 70)

if __name__ == "__main__":
    test_auth_security_suite()
