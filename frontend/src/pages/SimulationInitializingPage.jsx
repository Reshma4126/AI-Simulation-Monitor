import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, CheckCircle2 } from "lucide-react";
import "../styles/simulation.css";

export default function SimulationInitializingPage() {
  const navigate = useNavigate();
  const [stepIndex, setStepIndex] = useState(0);

  const steps = [
    "Preparing Patient Clinical Baseline...",
    "Loading Selected Scenario Metadata...",
    "Initializing High-Fidelity ECG Engine...",
    "Connecting Telemetry & Vital Waveforms...",
    "Launching Instructor Monitor Console...",
  ];

  useEffect(() => {
    const timer = setInterval(() => {
      setStepIndex((prev) => {
        if (prev < steps.length - 1) {
          return prev + 1;
        } else {
          clearInterval(timer);
          setTimeout(() => {
            navigate("/instructor");
          }, 600);
          return prev;
        }
      });
    }, 700);

    return () => clearInterval(timer);
  }, [navigate, steps.length]);

  const progressPercent = Math.round(((stepIndex + 1) / steps.length) * 100);

  return (
    <div className="simulation-page">
      <div className="sim-card">
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
          <div style={{ width: 56, height: 56, borderRadius: 16, backgroundColor: "#F0FDFA", border: "1px solid #CCFBF1", display: "flex", alignItems: "center", justifyContent: "center", color: "#0F766E" }}>
            <Activity size={30} className="animate-pulse" />
          </div>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: "#0F172A", letterSpacing: "-0.02em" }}>
              Initializing Simulation
            </h1>
            <p style={{ fontSize: 12, color: "#64748B", marginTop: 4 }}>
              Configuring patient telemetry and vital parameters
            </p>
          </div>
        </div>

        <div className="sim-progress-bar">
          <div className="sim-progress-fill" style={{ width: `${progressPercent}%` }} />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {steps.map((stepText, idx) => {
            const isDone = idx < stepIndex;
            const isCurrent = idx === stepIndex;
            return (
              <div
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 14px",
                  borderRadius: 12,
                  backgroundColor: isCurrent ? "#F0FDFA" : "#F8FAFC",
                  border: isCurrent ? "1px solid #CCFBF1" : "1px solid #F1F5F9",
                  fontSize: 13,
                  fontWeight: isCurrent ? 600 : 500,
                  color: isCurrent ? "#0F766E" : isDone ? "#059669" : "#94A3B8",
                  transition: "all 0.2s ease",
                }}
              >
                {isDone ? (
                  <CheckCircle2 size={16} color="#059669" />
                ) : isCurrent ? (
                  <Activity size={16} color="#0F766E" />
                ) : (
                  <div style={{ width: 16, height: 16, borderRadius: "50%", border: "2px solid #CBD5E1" }} />
                )}
                <span>{stepText}</span>
              </div>
            );
          })}
        </div>

        <div style={{ textAlign: "center", fontSize: 11, color: "#94A3B8" }}>
          MedSim AI Clinical Engine v2.4 • High-Fidelity Simulation
        </div>
      </div>
    </div>
  );
}
