import React from "react";
import SessionCard from "./SessionCard";
import "./dashboard.css";

export default function RecentSessions({
  sessions,
  searchQuery,
  handleStartSimulation,
  onOpenModal,
}) {
  return (
    <section>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
        }}
      >
        <h2
          style={{
            fontSize: "16px",
            fontWeight: "700",
            color: "#0F172A",
            letterSpacing: "-0.01em",
            margin: 0,
          }}
        >
          Recent Sessions
        </h2>

        {searchQuery && (
          <div style={{ fontSize: "12px", color: "#64748B" }}>
            Showing matches for "<strong>{searchQuery}</strong>"
          </div>
        )}
      </div>

      <div className="medsim-card" style={{ overflow: "hidden" }}>
        {sessions.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {sessions.map((session) => (
              <SessionCard
                key={session.id}
                session={session}
                onOpenSession={handleStartSimulation}
              />
            ))}
          </div>
        ) : (
          <div style={{ padding: "32px", textAlign: "center", color: "#64748B", fontSize: "13px" }}>
            No sessions match your search filter.
          </div>
        )}

        {/* View All Sessions Footer */}
        <div
          style={{
            padding: "12px 24px",
            backgroundColor: "#F8FAFC",
            borderTop: "1px solid #F1F5F9",
            textAlign: "center",
          }}
        >
          <button
            onClick={() => onOpenModal("sessions")}
            style={{
              backgroundColor: "transparent",
              color: "#0F766E",
              border: "none",
              fontWeight: "600",
              fontSize: "13px",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            View All Sessions →
          </button>
        </div>
      </div>
    </section>
  );
}
