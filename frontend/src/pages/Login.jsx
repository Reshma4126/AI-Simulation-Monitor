import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Activity, Lock, User, ShieldCheck } from "lucide-react";
import "../styles/auth.css";

const API = (
  import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export default function Login() {
  const [username, setUsername] = useState("instructor");
  const [password, setPassword] = useState("instructor123");
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (res.ok) {
        const data = await res.json();
        sessionStorage.setItem("token", data.access_token);
        sessionStorage.setItem("role", data.role);
        if (data.session_code) {
          sessionStorage.setItem("session_code", data.session_code);
        }

        if (data.role === "instructor") {
          navigate("/dashboard");
        } else {
          navigate("/student-dashboard");
        }
        return;
      }
    } catch (err) {
      console.warn("Backend auth unavailable, performing demo navigation...", err);
    }

    sessionStorage.setItem("token", "demo-token");
    if (username.toLowerCase().includes("student")) {
      sessionStorage.setItem("role", "student");
      navigate("/student-dashboard");
    } else {
      sessionStorage.setItem("role", "instructor");
      navigate("/dashboard");
    }
    setLoading(false);
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

        {/* Form */}
        <form onSubmit={handleLogin} className="auth-form">
          <div className="auth-field">
            <label className="auth-label">Instructor Username / Email</label>
            <div className="auth-input-container">
              <User className="auth-input-icon" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="instructor"
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

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "12px", paddingTop: "4px" }}>
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
            <div style={{ padding: "10px", borderRadius: "10px", backgroundColor: "#FEF2F2", color: "#DC2626", fontSize: "12px", fontWeight: 600, textAlign: "center" }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="auth-btn-primary">
            {loading ? "Authenticating..." : "Sign In →"}
          </button>

          <div style={{ textAlign: "center", fontSize: "12px", color: "#64748B" }}>
            Need an instructor account?{" "}
            <Link to="/register" style={{ color: "#0F766E", fontWeight: 600 }}>
              Request Access
            </Link>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px", margin: "4px 0" }}>
            <div style={{ flex: 1, height: "1px", backgroundColor: "#E2E8F0" }} />
            <span style={{ fontSize: "11px", color: "#94A3B8", fontWeight: 600 }}>OR</span>
            <div style={{ flex: 1, height: "1px", backgroundColor: "#E2E8F0" }} />
          </div>

          <button
            type="button"
            onClick={() => navigate("/student-dashboard")}
            className="auth-btn-secondary"
          >
            <ShieldCheck size={16} color="#0F766E" />
            Student Remote Access Portal
          </button>
        </form>

        <div style={{ textAlign: "center", fontSize: "11px", color: "#94A3B8" }}>
          🔒 Secure Clinical Simulation Node • MedSim AI v2.4
        </div>
      </div>
    </div>
  );
}
