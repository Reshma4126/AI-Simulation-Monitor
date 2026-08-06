import React from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, FileText, LayoutDashboard, Award, Clock } from "lucide-react";
import "../styles/simulation.css";

export default function SimulationCompletedPage() {
  const navigate = useNavigate();

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
            <span style={{ fontWeight: 700, color: "#0F172A" }}>VF Cardiac Arrest</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", paddingTop: "4px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Clock size={18} color="#94A3B8" />
              <div>
                <span style={{ fontSize: "10px", color: "#94A3B8", display: "block", textTransform: "uppercase" }}>Duration</span>
                <span style={{ fontWeight: 700, color: "#1E293B" }}>14 Mins 22 Sec</span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Award size={18} color="#0F766E" />
              <div>
                <span style={{ fontSize: "10px", color: "#94A3B8", display: "block", textTransform: "uppercase" }}>Performance Score</span>
                <span style={{ fontWeight: 800, color: "#0F766E", fontSize: "15px" }}>94 / 100</span>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px", paddingTop: "8px" }}>
          <button
            onClick={() => navigate("/debrief")}
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
