import React from "react";
import { Activity, Calendar, CheckCircle2, AlertCircle } from "lucide-react";
import "./dashboard.css";

export default function Statistics() {
  const stats = [
    {
      id: "total",
      label: "Total Simulations",
      value: "128",
      icon: Activity,
      color: "#0F172A",
    },
    {
      id: "today",
      label: "Today's Sessions",
      value: "4",
      icon: Calendar,
      color: "#0F766E",
    },
    {
      id: "completed",
      label: "Completed Sessions",
      value: "114",
      icon: CheckCircle2,
      color: "#0F172A",
    },
    {
      id: "pending",
      label: "Pending Debriefs",
      value: "3",
      icon: AlertCircle,
      color: "#D97706",
    },
  ];

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
        Statistics
      </h2>

      <div className="medsim-stats-grid">
        {stats.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.id} className="medsim-stat-card">
              <div>
                <div style={{ fontSize: "12px", fontWeight: "500", color: "#64748B" }}>
                  {item.label}
                </div>
                <div
                  style={{
                    fontSize: "28px",
                    fontWeight: "800",
                    color: item.color,
                    marginTop: "4px",
                    letterSpacing: "-0.02em",
                  }}
                >
                  {item.value}
                </div>
              </div>
              <div
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "10px",
                  backgroundColor: "#F8FAFC",
                  border: "1px solid #F1F5F9",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon size={18} color="#94A3B8" />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
