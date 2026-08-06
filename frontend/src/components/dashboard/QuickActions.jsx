import React from "react";
import { Play, ClipboardList, FileText, BookOpen } from "lucide-react";
import "./dashboard.css";

export default function QuickActions({ handleStartSimulation, onOpenModal }) {
  return (
    <section>
      <h2
        style={{
          fontSize: "16px",
          fontWeight: "700",
          color: "#0F172A",
          marginBottom: "16px",
          letterSpacing: "-0.01em",
          margin: "0 0 16px 0",
        }}
      >
        Quick Actions
      </h2>

      <div className="medsim-quick-grid">
        {/* Card 1: Start Simulation (Primary Card, badge removed) */}
        <div
          onClick={handleStartSimulation}
          className="medsim-quick-card primary-card"
        >
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "12px",
              backgroundColor: "#0F766E",
              color: "#FFFFFF",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "12px",
            }}
          >
            <Play size={20} fill="currentColor" color="#FFFFFF" />
          </div>

          <div>
            <div
              style={{
                fontSize: "16px",
                fontWeight: "700",
                color: "#0F172A",
                marginBottom: "4px",
              }}
            >
              Start Simulation
            </div>
            <div style={{ fontSize: "12px", color: "#64748B", fontWeight: "500" }}>
              Launch real-time monitor & instructor controls
            </div>
          </div>
        </div>

        {/* Card 2: Sessions */}
        <div
          onClick={() => onOpenModal("sessions")}
          className="medsim-quick-card"
        >
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "12px",
              backgroundColor: "#F1F5F9",
              color: "#334155",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "12px",
            }}
          >
            <ClipboardList size={20} color="#334155" />
          </div>

          <div>
            <div
              style={{
                fontSize: "16px",
                fontWeight: "700",
                color: "#0F172A",
                marginBottom: "4px",
              }}
            >
              Sessions
            </div>
            <div style={{ fontSize: "12px", color: "#64748B", fontWeight: "500" }}>
              View active & past clinical runs
            </div>
          </div>
        </div>

        {/* Card 3: Debrief Reports */}
        <div
          onClick={() => onOpenModal("reports")}
          className="medsim-quick-card"
        >
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "12px",
              backgroundColor: "#F1F5F9",
              color: "#334155",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "12px",
            }}
          >
            <FileText size={20} color="#334155" />
          </div>

          <div>
            <div
              style={{
                fontSize: "16px",
                fontWeight: "700",
                color: "#0F172A",
                marginBottom: "4px",
              }}
            >
              Debrief Reports
            </div>
            <div style={{ fontSize: "12px", color: "#64748B", fontWeight: "500" }}>
              Automated AI performance insights
            </div>
          </div>
        </div>

        {/* Card 4: Scenario Library */}
        <div
          onClick={() => onOpenModal("library")}
          className="medsim-quick-card"
        >
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "12px",
              backgroundColor: "#F1F5F9",
              color: "#334155",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "12px",
            }}
          >
            <BookOpen size={20} color="#334155" />
          </div>

          <div>
            <div
              style={{
                fontSize: "16px",
                fontWeight: "700",
                color: "#0F172A",
                marginBottom: "4px",
              }}
            >
              Scenario Library
            </div>
            <div style={{ fontSize: "12px", color: "#64748B", fontWeight: "500" }}>
              Browse 20 clinical scenarios
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
