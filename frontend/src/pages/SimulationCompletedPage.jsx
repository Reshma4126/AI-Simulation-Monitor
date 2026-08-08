import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, FileText, LayoutDashboard, Award, Clock } from "lucide-react";
import "../styles/simulation.css";

export default function SimulationCompletedPage() {
  const navigate = useNavigate();
  const [score, setScore] = useState(null);
  const [durationStr, setDurationStr] = useState("Calculating...");
  const [scenarioName, setScenarioName] = useState("ACLS Scenario");
  const [loading, setLoading] = useState(true);

  const sessionCode = sessionStorage.getItem("session_code") || "";
  const API_BASE = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

  useEffect(() => {
    if (!sessionCode) {
      setLoading(false);
      return;
    }
    const token = sessionStorage.getItem("token") || "";

    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/debrief/status/${sessionCode}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const statusData = await res.json();
          if (statusData.status === "completed") {
            const reportRes = await fetch(`${API_BASE}/api/debrief/${sessionCode}`, {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (reportRes.ok) {
              const report = await reportRes.json();
              setScore(report.overall_score);
              
              // Format duration from ms
              const ms = report.debrief?.duration_ms || 0;
              const totalSecs = Math.floor(ms / 1000);
              const mins = Math.floor(totalSecs / 60);
              const secs = totalSecs % 60;
              setDurationStr(`${mins} Mins ${secs} Sec`);
              
              setScenarioName(report.debrief?.scenario_name || "ACLS Scenario");
              setLoading(false);
              return true; // Stop polling
            }
          } else if (statusData.status === "failed") {
            setDurationStr("Generation failed");
            setLoading(false);
            return true;
          }
        }
      } catch (err) {
        console.error("Error fetching completed metrics:", err);
      }
      return false;
    };

    let timer;
    const poll = async () => {
      const done = await checkStatus();
      if (!done) {
        timer = setTimeout(poll, 2000);
      }
    };
    poll();

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [sessionCode]);

  return (
    <div className="simulation-page">
      <div className="sim-card">
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
          <div style={{ width: 64, height: 64, borderRadius: "50%", backgroundColor: "#ECFDF5", border: "1px solid #A7F3D0", display: "flex", alignItems: "center", justifyContent: "center", color: "#059669" }}>
            <CheckCircle2 size={36} />
          </div>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0F172A", letterSpacing: "-0.02em" }}>
              Simulation Completed
            </h1>
            <p style={{ fontSize: 12, color: "#64748B", marginTop: 4 }}>
              Session data saved and AI Debrief report generated successfully
            </p>
          </div>
        </div>

        <div style={{ backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0", padding: "20px", display: "flex", flexDirection: "column", gap: "12px", fontSize: 13 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "12px", borderBottom: "1px solid #E2E8F0" }}>
            <span style={{ color: "#64748B", fontWeight: 500 }}>Scenario</span>
            <span style={{ fontWeight: 700, color: "#0F172A" }}>{scenarioName}</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", paddingTop: "4px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Clock size={18} color="#94A3B8" />
              <div>
                <span style={{ fontSize: "10px", color: "#94A3B8", display: "block", textTransform: "uppercase" }}>Duration</span>
                <span style={{ fontWeight: 700, color: "#1E293B" }}>{durationStr}</span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Award size={18} color="#0F766E" />
              <div>
                <span style={{ fontSize: "10px", color: "#94A3B8", display: "block", textTransform: "uppercase" }}>Performance Score</span>
                <span style={{ fontWeight: 800, color: "#0F766E", fontSize: "15px" }}>
                  {score !== null ? `${score} / 100` : "Calculating..."}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px", paddingTop: "8px" }}>
          <button
            onClick={() => navigate(`/debrief?sessionCode=${sessionCode}`)}
            style={{ width: "100%", height: 48, backgroundColor: "#0F766E", color: "#FFFFFF", fontWeight: 600, fontSize: 14, borderRadius: 12, border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            <FileText size={18} />
            View AI Debrief Report
          </button>

          <button
            onClick={() => navigate("/dashboard")}
            style={{ width: "100%", height: 48, backgroundColor: "#FFFFFF", color: "#334155", border: "1px solid #CBD5E1", fontWeight: 600, fontSize: 14, borderRadius: 12, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            <LayoutDashboard size={18} color="#64748B" />
            Return to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
