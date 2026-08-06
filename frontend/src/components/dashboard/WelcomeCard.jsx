import React from "react";
import { Play, Clock } from "lucide-react";
import "./dashboard.css";

export default function WelcomeCard({ handleStartSimulation }) {
  return (
    <section className="medsim-welcome-card">
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <h1
            style={{
              fontSize: "20px",
              fontWeight: "700",
              color: "#0F172A",
              letterSpacing: "-0.01em",
              margin: 0,
            }}
          >
            Good Morning, Dr. John Doe
          </h1>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "3px 10px",
              borderRadius: "16px",
              fontSize: "12px",
              fontWeight: "600",
              backgroundColor: "#F1F5F9",
              color: "#64748B",
              border: "1px solid #E2E8F0",
            }}
          >
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: "#94A3B8",
              }}
            />
            No active simulation running
          </span>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "13px",
            color: "#64748B",
            fontWeight: "500",
          }}
        >
          <Clock size={14} color="#94A3B8" />
          <span>Last Login • Today • 09:15 AM</span>
        </div>
      </div>

      <div>
        <button onClick={handleStartSimulation} className="medsim-btn-primary">
          <Play size={16} fill="currentColor" color="#FFFFFF" />
          Start Simulation
        </button>
      </div>
    </section>
  );
}
