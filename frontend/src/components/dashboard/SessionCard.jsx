import React from "react";
import { Activity, Clock } from "lucide-react";
import "./dashboard.css";

export default function SessionCard({ session, onOpenSession }) {
  return (
    <div className="medsim-session-row">
      {/* Scenario Name & Patient */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", minWidth: "260px" }}>
        <div
          style={{
            width: "38px",
            height: "38px",
            borderRadius: "10px",
            backgroundColor: "#F0FDFA",
            color: "#0F766E",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Activity size={20} color="#0F766E" />
        </div>
        <div>
          <div style={{ fontWeight: "700", fontSize: "14px", color: "#0F172A", lineHeight: "1.3" }}>
            {session.name}
          </div>
          <div style={{ fontSize: "12px", color: "#64748B", marginTop: "2px", fontWeight: "500" }}>
            Patient: {session.patient}
          </div>
        </div>
      </div>

      {/* Date */}
      <div style={{ fontSize: "13px", color: "#475569", fontWeight: "500", minWidth: "110px" }}>
        {session.date}
      </div>

      {/* Duration */}
      <div
        style={{
          fontSize: "13px",
          color: "#64748B",
          minWidth: "110px",
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontWeight: "500",
        }}
      >
        <Clock size={14} color="#94A3B8" />
        <span>{session.duration}</span>
      </div>

      {/* Status Badge */}
      <div style={{ minWidth: "140px" }}>
        {session.status === "Completed" && (
          <span
            style={{
              backgroundColor: "#ECFDF5",
              color: "#047857",
              padding: "4px 12px",
              borderRadius: "16px",
              fontSize: "12px",
              fontWeight: "600",
              border: "1px solid #A7F3D0",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#10B981" }} />
            Completed
          </span>
        )}
        {session.status === "Active" && (
          <span
            style={{
              backgroundColor: "#F0FDFA",
              color: "#0F766E",
              padding: "4px 12px",
              borderRadius: "16px",
              fontSize: "12px",
              fontWeight: "600",
              border: "1px solid #CCFBF1",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#0F766E" }} />
            Active
          </span>
        )}
        {session.status === "Pending Debrief" && (
          <span
            style={{
              backgroundColor: "#FFFBEB",
              color: "#B45309",
              padding: "4px 12px",
              borderRadius: "16px",
              fontSize: "12px",
              fontWeight: "600",
              border: "1px solid #FDE68A",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#F59E0B" }} />
            Pending Debrief
          </span>
        )}
      </div>

      {/* Open Button (Reduced width) */}
      <div>
        <button onClick={onOpenSession} className="medsim-btn-open">
          Open →
        </button>
      </div>
    </div>
  );
}
