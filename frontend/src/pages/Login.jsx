import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Activity, Lock, User, UserCheck, GraduationCap } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import "../styles/auth.css";

export default function Login() {
  const [role, setRole] = useState("instructor"); // "instructor" | "student"
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
  const { login, user, isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!authLoading && isAuthenticated && user) {
      if (user.role === "instructor") {
        navigate("/dashboard", { replace: true });
      } else if (user.role === "student") {
        navigate("/student-dashboard", { replace: true });
      }
    }
  }, [authLoading, isAuthenticated, user, navigate]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await login(username, password, role, rememberMe);
      if (res.role === "instructor") {
        navigate("/dashboard", { replace: true });
      } else {
        navigate("/student-dashboard", { replace: true });
      }
    } catch (err) {
      setError(err.message || "Invalid username, password, or role.");
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
            <h1 className="auth-title">MedSim AI</h1>
            <span className="auth-badge">Simulation & Debrief Platform</span>
          </div>
        </div>

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

        {/* Form */}
        <form onSubmit={handleLogin} className="auth-form">
          <div className="auth-field">
            <label className="auth-label">
              {role === "instructor" ? "Instructor Username / Email" : "Student Username / Email"}
            </label>
            <div className="auth-input-container">
              <User className="auth-input-icon" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={role === "instructor" ? "Enter instructor username" : "Enter student username"}
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

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "12px", marginBottom: "16px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "6px", color: "#475569", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                style={{ accentColor: "#0F766E" }}
              />
              Remember Me
            </label>
            <Link to="/forgot-password" style={{ color: "#0F766E", fontWeight: 600 }}>
              Forgot Password?
            </Link>
          </div>

          {error && (
            <div style={{ padding: "10px", borderRadius: "10px", backgroundColor: "#FEF2F2", color: "#DC2626", fontSize: "12px", fontWeight: 600, textAlign: "center", marginBottom: "16px" }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="auth-btn-primary">
            {loading ? "Authenticating..." : `Sign In as ${role === "instructor" ? "Instructor" : "Student"} →`}
          </button>

          {role === "instructor" && (
            <div style={{ textAlign: "center", fontSize: "12px", color: "#64748B", marginTop: "16px" }}>
              Need an instructor account?{" "}
              <Link to="/register" style={{ color: "#0F766E", fontWeight: 600 }}>
                Request Access
              </Link>
            </div>
          )}
        </form>

        <div style={{ textAlign: "center", fontSize: "11px", color: "#94A3B8", marginTop: "24px" }}>
          🔒 Secure Clinical Simulation Node • MedSim AI v2.4
        </div>
      </div>
    </div>
  );
}
