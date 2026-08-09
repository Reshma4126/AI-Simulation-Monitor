import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Award, ArrowLeft, Trophy, Shield, RefreshCw, Zap } from "lucide-react";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import "../components/dashboard/dashboard.css";

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function LeaderboardPage() {
  const navigate = useNavigate();
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  const currentTeam = sessionStorage.getItem("team_name") || "";
  const token = sessionStorage.getItem("token") || localStorage.getItem("token") || "";

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
    fetchLeaderboard();
  }, []);

  return (
    <div className="medsim-dashboard-page" style={{ backgroundColor: "#F8FAFC" }}>
      <Navbar
        searchQuery=""
        setSearchQuery={() => {}}
        showNotifications={false}
        setShowNotifications={() => {}}
        showProfileMenu={false}
        setShowProfileMenu={() => {}}
        handleStartSimulation={() => navigate("/cases")}
        handleLogout={() => {
          sessionStorage.clear();
          navigate("/");
        }}
        onOpenSettings={() => setActiveModal("settings")}
      />

      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          setSidebarExpanded={setSidebarExpanded}
          activeTab="dashboard"
          setActiveTab={() => {}}
          handleStartSimulation={() => navigate("/cases")}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content" style={{ flex: 1, padding: "32px 40px", overflowY: "auto" }}>
          
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <button
                onClick={() => navigate(-1)}
                style={{ backgroundColor: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 8, padding: 8, cursor: "pointer", color: "#64748B" }}
              >
                <ArrowLeft size={18} />
              </button>
              <div>
                <h1 style={{ fontSize: 22, fontWeight: 800, color: "#0F172A", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
                  <Trophy size={24} color="#D97706" /> Simulation Team Leaderboard
                </h1>
                <p style={{ fontSize: 12, color: "#64748B", margin: "2px 0 0 0" }}>
                  Ranked by total XP earned across completed clinical scenarios
                </p>
              </div>
            </div>

            <button
              onClick={fetchLeaderboard}
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #CBD5E1", borderRadius: 8, padding: "8px 14px", fontSize: 12, fontWeight: 600, color: "#334155", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>

          <div style={{ backgroundColor: "#FFFFFF", borderRadius: 16, border: "1px solid #E2E8F0", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", overflow: "hidden" }}>
            
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13 }}>
              <thead>
                <tr style={{ backgroundColor: "#F8FAFC", borderBottom: "1px solid #E2E8F0", color: "#64748B", fontSize: 11, textTransform: "uppercase", fontWeight: 700 }}>
                  <th style={{ padding: "14px 20px" }}>Rank</th>
                  <th style={{ padding: "14px 20px" }}>Team Name</th>
                  <th style={{ padding: "14px 20px" }}>Level</th>
                  <th style={{ padding: "14px 20px" }}>Sessions</th>
                  <th style={{ padding: "14px 20px" }}>Best Score</th>
                  <th style={{ padding: "14px 20px" }}>Total XP</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={6} style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>
                      Loading leaderboard rankings...
                    </td>
                  </tr>
                ) : leaderboard.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>
                      No leaderboard data yet. Complete simulation scenarios to earn XP!
                    </td>
                  </tr>
                ) : (
                  leaderboard.map((row) => {
                    const isCurrent = currentTeam && row.team_name.toLowerCase() === currentTeam.toLowerCase();
                    const rankMedal = row.rank === 1 ? "🥇" : row.rank === 2 ? "🥈" : row.rank === 3 ? "🥉" : `#${row.rank}`;
                    return (
                      <tr
                        key={row.rank}
                        style={{
                          borderBottom: "1px solid #F1F5F9",
                          backgroundColor: isCurrent ? "#F0FDFA" : "transparent"
                        }}
                      >
                        <td style={{ padding: "14px 20px", fontWeight: 800, color: row.rank <= 3 ? "#D97706" : "#64748B", fontSize: row.rank <= 3 ? 16 : 13 }}>
                          {rankMedal}
                        </td>
                        <td style={{ padding: "14px 20px", fontWeight: 700, color: "#0F172A", display: "flex", alignItems: "center", gap: 8 }}>
                          {row.team_name}
                          {isCurrent && (
                            <span style={{ fontSize: 10, backgroundColor: "#0F766E", color: "#FFF", padding: "2px 8px", borderRadius: 10, fontWeight: 600 }}>Your Team</span>
                          )}
                        </td>
                        <td style={{ padding: "14px 20px", color: "#475569" }}>
                          <span style={{ backgroundColor: "#F1F5F9", padding: "4px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600, color: "#0F766E", border: "1px solid #CCFBF1" }}>
                            {row.level}
                          </span>
                        </td>
                        <td style={{ padding: "14px 20px", color: "#475569", fontWeight: 600 }}>
                          {row.session_count}
                        </td>
                        <td style={{ padding: "14px 20px", fontWeight: 700, color: "#059669" }}>
                          {row.best_score}%
                        </td>
                        <td style={{ padding: "14px 20px", fontWeight: 800, color: "#D97706", fontSize: 14 }}>
                          ⚡ {row.total_xp.toLocaleString()} XP
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>

          </div>

        </main>
      </div>

      <DashboardModals activeModal={activeModal} onClose={() => setActiveModal(null)} />
    </div>
  );
}
