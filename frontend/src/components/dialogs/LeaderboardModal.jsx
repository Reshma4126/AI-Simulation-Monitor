import React, { useState, useEffect } from "react";
import { Award, Trophy, RefreshCw, X, Zap, Shield } from "lucide-react";

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function LeaderboardModal({ isOpen, onClose }) {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);

  const token = sessionStorage.getItem("token") || localStorage.getItem("token") || "";
  const currentTeam = sessionStorage.getItem("team_name") || "";

  const fetchLeaderboard = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/leaderboard`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.ok) {
        const data = await res.json();
        setLeaderboard(data.leaderboard || []);
      }
    } catch (err) {
      console.error("Error fetching leaderboard:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchLeaderboard();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(15, 23, 42, 0.75)",
        backdropFilter: "blur(6px)",
        zIndex: 999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: "#0F172A",
          border: "1px solid #334155",
          borderRadius: 16,
          width: "100%",
          maxWidth: 680,
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)",
          overflow: "hidden"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid #1E293B",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            backgroundColor: "#1E293B40"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                backgroundColor: "#F59E0B20",
                border: "1px solid #F59E0B40",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
            >
              <Trophy size={20} color="#F59E0B" />
            </div>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: "#F8FAFC", margin: 0 }}>
                Simulation Leaderboard
              </h2>
              <p style={{ fontSize: 11, color: "#94A3B8", margin: 0 }}>
                Team rankings & XP performance metrics
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={fetchLeaderboard}
              disabled={loading}
              style={{
                backgroundColor: "#1E293B",
                border: "1px solid #334155",
                color: "#94A3B8",
                padding: "6px 12px",
                borderRadius: 8,
                fontSize: 12,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6
              }}
            >
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
            <button
              onClick={onClose}
              style={{
                backgroundColor: "#1E293B",
                border: "1px solid #334155",
                color: "#94A3B8",
                width: 32,
                height: 32,
                borderRadius: 8,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer"
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Content Table */}
        <div style={{ flex: 1, overflowY: "auto", padding: 0 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13 }}>
            <thead>
              <tr
                style={{
                  backgroundColor: "#1E293B",
                  borderBottom: "1px solid #334155",
                  color: "#94A3B8",
                  fontSize: 11,
                  textTransform: "uppercase",
                  fontWeight: 700
                }}
              >
                <th style={{ padding: "12px 16px" }}>Rank</th>
                <th style={{ padding: "12px 16px" }}>Team Name</th>
                <th style={{ padding: "12px 16px" }}>Level</th>
                <th style={{ padding: "12px 16px" }}>Sessions</th>
                <th style={{ padding: "12px 16px" }}>Best Score</th>
                <th style={{ padding: "12px 16px" }}>Total XP</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ padding: 40, textAlign: "center", color: "#64748B" }}>
                    Loading leaderboard rankings...
                  </td>
                </tr>
              ) : leaderboard.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: 40, textAlign: "center", color: "#64748B" }}>
                    No leaderboard data available yet. Complete simulation scenarios to earn XP!
                  </td>
                </tr>
              ) : (
                leaderboard.map((row) => {
                  const isCurrent = currentTeam && row.team_name.toLowerCase() === currentTeam.toLowerCase();
                  const rankMedal =
                    row.rank === 1 ? "🥇" : row.rank === 2 ? "🥈" : row.rank === 3 ? "🥉" : `#${row.rank}`;
                  return (
                    <tr
                      key={row.rank}
                      style={{
                        borderBottom: "1px solid #1E293B",
                        backgroundColor: isCurrent ? "#0F766E20" : "transparent"
                      }}
                    >
                      <td
                        style={{
                          padding: "12px 16px",
                          fontWeight: 800,
                          color: row.rank <= 3 ? "#F59E0B" : "#94A3B8",
                          fontSize: row.rank <= 3 ? 15 : 12
                        }}
                      >
                        {rankMedal}
                      </td>
                      <td
                        style={{
                          padding: "12px 16px",
                          fontWeight: 700,
                          color: "#F8FAFC"
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          {row.team_name}
                          {isCurrent && (
                            <span
                              style={{
                                fontSize: 9,
                                backgroundColor: "#10B98120",
                                color: "#10B981",
                                border: "1px solid #10B98140",
                                padding: "1px 6px",
                                borderRadius: 8,
                                fontWeight: 600
                              }}
                            >
                              Your Team
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        <span
                          style={{
                            backgroundColor: "#1E293B",
                            padding: "3px 8px",
                            borderRadius: 10,
                            fontSize: 10,
                            fontWeight: 600,
                            color: "#60A5FA",
                            border: "1px solid #334155"
                          }}
                        >
                          {row.level}
                        </span>
                      </td>
                      <td style={{ padding: "12px 16px", color: "#CBD5E1", fontWeight: 600 }}>
                        {row.session_count}
                      </td>
                      <td style={{ padding: "12px 16px", color: "#10B981", fontWeight: 700 }}>
                        {Number(row.best_score || 0).toFixed(1)}%
                      </td>
                      <td style={{ padding: "12px 16px", color: "#F59E0B", fontWeight: 800 }}>
                        ⚡ {row.total_xp}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid #1E293B",
            backgroundColor: "#1E293B20",
            display: "flex",
            justify: "space-between",
            alignItems: "center"
          }}
        >
          <span style={{ fontSize: 11, color: "#64748B" }}>
            XP points are awarded upon completing ACLS debriefing.
          </span>
          <button
            onClick={onClose}
            style={{
              backgroundColor: "#334155",
              border: "none",
              color: "#F8FAFC",
              padding: "6px 16px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer"
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
