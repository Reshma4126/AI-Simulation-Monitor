import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Activity, ArrowLeft, User, Lock, UserCheck, GraduationCap, CheckCircle } from "lucide-react";
import "../styles/auth.css";

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function RegistrationRequestPage() {
  const [role, setRole] = useState("instructor"); // "instructor" | "student"
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!username.trim()) {
      setError("Username / Email is required.");
      return;
    }

    if (password.length < 4) {
      setError("Password must be at least 4 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          password,
          role,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Registration failed. Please try again.");
      }

      setSubmitted(true);
    } catch (err) {
      setError(err.message || "Could not register user.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        {/* App Header */}
        <div className="auth-header">
          <div className="auth-logo">
            <Activity size={30} />
          </div>
          <div>
            <h1 className="auth-title">Create Account</h1>
            <span className="auth-badge">Register for MedSim AI</span>
          </div>
        </div>

        {!submitted ? (
          <>
            {/* Explicit Role Selection */}
            <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
              <button
                type="button"
                onClick={() => { setRole("instructor"); setError(""); }}
                style={{
                  flex: 1,
                  padding: "12px 8px",
                  borderRadius: "12px",
                  border: role === "instructor" ? "2px solid #0F766E" : "1px solid #E2E8F0",
                  backgroundColor: role === "instructor" ? "#F0FDFA" : "#F8FAFC",
                  color: role === "instructor" ? "#0F766E" : "#64748B",
                  fontWeight: 700,
                  fontSize: "13px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  transition: "all 0.2s ease"
                }}
              >
                <UserCheck size={18} color={role === "instructor" ? "#0F766E" : "#64748B"} />
                Instructor
              </button>
              <button
                type="button"
                onClick={() => { setRole("student"); setError(""); }}
                style={{
                  flex: 1,
                  padding: "12px 8px",
                  borderRadius: "12px",
                  border: role === "student" ? "2px solid #0F766E" : "1px solid #E2E8F0",
                  backgroundColor: role === "student" ? "#F0FDFA" : "#F8FAFC",
                  color: role === "student" ? "#0F766E" : "#64748B",
                  fontWeight: 700,
                  fontSize: "13px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  transition: "all 0.2s ease"
                }}
              >
                <GraduationCap size={18} color={role === "student" ? "#0F766E" : "#64748B"} />
                Student
              </button>
            </div>

            <form onSubmit={handleSubmit} className="auth-form">
              <div className="auth-field">
                <label className="auth-label">Username / Institutional Email</label>
                <div className="auth-input-container">
                  <User className="auth-input-icon" />
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. dr.smith or student1"
                    className="auth-input"
                  />
                </div>
              </div>

              <div className="auth-field">
                <label className="auth-label">Password</label>
                <div className="auth-input-container">
                  <Lock className="auth-input-icon" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="auth-input"
                  />
                </div>
              </div>

              <div className="auth-field">
                <label className="auth-label">Confirm Password</label>
                <div className="auth-input-container">
                  <Lock className="auth-input-icon" />
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    className="auth-input"
                  />
                </div>
              </div>

              {error && (
                <div style={{ padding: "10px", borderRadius: "10px", backgroundColor: "#FEF2F2", color: "#DC2626", fontSize: "12px", fontWeight: 600, textAlign: "center", marginBottom: "16px" }}>
                  {error}
                </div>
              )}

              <button type="submit" disabled={loading} className="auth-btn-primary">
                {loading ? "Creating Account..." : `Register as ${role === "instructor" ? "Instructor" : "Student"} →`}
              </button>
            </form>
          </>
        ) : (
          <div style={{ padding: "20px", borderRadius: "12px", backgroundColor: "#F0FDFA", border: "1px solid #CCFBF1", textAlign: "center" }}>
            <CheckCircle size={40} color="#0F766E" style={{ margin: "0 auto 12px" }} />
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#0F766E", marginBottom: "6px" }}>
              Account Created Successfully!
            </h3>
            <p style={{ fontSize: "12px", color: "#334155", marginBottom: "16px" }}>
              User <strong>{username}</strong> has been registered as an <strong>{role}</strong>. You can now sign in with your credentials.
            </p>
            <button
              onClick={() => navigate("/")}
              className="auth-btn-primary"
            >
              Proceed to Sign In →
            </button>
          </div>
        )}

        <div style={{ textAlign: "center", marginTop: "20px", paddingTop: "16px", borderTop: "1px solid #E2E8F0" }}>
          <Link
            to="/"
            style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: 600, color: "#64748B", textDecoration: "none" }}
          >
            <ArrowLeft size={14} />
            Back to Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}
