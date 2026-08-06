import React from "react";
import { Activity, Search, Bell, ChevronDown, LogOut, Settings, Play } from "lucide-react";
import "./dashboard.css";

export default function Navbar({
  searchQuery,
  setSearchQuery,
  showNotifications,
  setShowNotifications,
  showProfileMenu,
  setShowProfileMenu,
  handleStartSimulation,
  handleLogout,
  onOpenSettings,
}) {
  return (
    <header className="medsim-navbar">
      {/* Left: Logo & Title */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div className="medsim-logo-badge">
          <Activity size={22} strokeWidth={2.2} />
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="medsim-app-title">MedSim AI</span>
            <span className="medsim-app-subtitle">Simulation & Debrief Platform</span>
          </div>
        </div>
      </div>

      {/* Center: Search Bar */}
      <div className="medsim-search-container">
        <Search className="medsim-search-icon" size={18} />
        <input
          type="text"
          placeholder="Search sessions..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="medsim-search-input"
        />
      </div>

      {/* Right: Notifications & Profile */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", position: "relative" }}>
        {/* Notifications Button */}
        <button
          onClick={() => {
            setShowNotifications(!showNotifications);
            setShowProfileMenu(false);
          }}
          className="medsim-icon-btn"
          title="Notifications"
        >
          <Bell size={20} color="#475569" />
          <span className="medsim-unread-dot" />
        </button>

        {/* Notifications Popup */}
        {showNotifications && (
          <div
            style={{
              position: "absolute",
              top: "52px",
              right: "60px",
              width: "320px",
              backgroundColor: "#FFFFFF",
              borderRadius: "16px",
              border: "1px solid #E2E8F0",
              boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
              zIndex: 50,
              padding: "16px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                paddingBottom: "12px",
                borderBottom: "1px solid #F1F5F9",
              }}
            >
              <span style={{ fontWeight: "600", fontSize: "14px", color: "#0F172A" }}>
                Notifications
              </span>
              <button
                style={{
                  fontSize: "11px",
                  color: "#0F766E",
                  fontWeight: "600",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Mark all as read
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
              <div
                style={{
                  padding: "10px",
                  borderRadius: "10px",
                  backgroundColor: "#F0FDFA",
                  border: "1px solid #CCFBF1",
                  fontSize: "13px",
                }}
              >
                <div style={{ fontWeight: "600", color: "#0F766E" }}>
                  Session #8943 Completed
                </div>
                <div style={{ color: "#475569", marginTop: "2px" }}>
                  Automated debrief report is ready for VF Cardiac Arrest.
                </div>
                <div style={{ fontSize: "11px", color: "#94A3B8", marginTop: "4px" }}>
                  10 mins ago
                </div>
              </div>
              <div
                style={{
                  padding: "10px",
                  borderRadius: "10px",
                  backgroundColor: "#F8FAFC",
                  border: "1px solid #E2E8F0",
                  fontSize: "13px",
                }}
              >
                <div style={{ fontWeight: "600", color: "#0F172A" }}>
                  Scenario Library Updated
                </div>
                <div style={{ color: "#475569", marginTop: "2px" }}>
                  Added "Anaphylactic Shock - Grade III" scenario.
                </div>
                <div style={{ fontSize: "11px", color: "#94A3B8", marginTop: "4px" }}>
                  1 hour ago
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Profile Avatar & Trigger */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => {
              setShowProfileMenu(!showProfileMenu);
              setShowNotifications(false);
            }}
            className="medsim-profile-trigger"
          >
            <div className="medsim-avatar">JD</div>
            <div style={{ textAlign: "left", paddingRight: "4px" }}>
              <div style={{ fontSize: "13px", fontWeight: "600", color: "#0F172A", lineHeight: 1.2 }}>
                Dr. John Doe
              </div>
              <div style={{ fontSize: "11px", color: "#64748B", lineHeight: 1.2 }}>
                Clinical Instructor
              </div>
            </div>
            <ChevronDown size={14} color="#64748B" />
          </button>

          {/* Profile Dropdown */}
          {showProfileMenu && (
            <div
              style={{
                position: "absolute",
                top: "52px",
                right: "0",
                width: "220px",
                backgroundColor: "#FFFFFF",
                borderRadius: "16px",
                border: "1px solid #E2E8F0",
                boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
                zIndex: 50,
                padding: "8px 0",
                overflow: "hidden",
              }}
            >
              <div style={{ padding: "12px 16px", borderBottom: "1px solid #F1F5F9" }}>
                <div style={{ fontWeight: "600", fontSize: "14px", color: "#0F172A" }}>
                  Dr. John Doe
                </div>
                <div style={{ fontSize: "12px", color: "#64748B" }}>
                  john.doe@hospital.org
                </div>
              </div>

              <div style={{ padding: "4px 0" }}>
                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    handleStartSimulation();
                  }}
                  style={{
                    width: "100%",
                    padding: "10px 16px",
                    textAlign: "left",
                    backgroundColor: "transparent",
                    border: "none",
                    fontSize: "13px",
                    color: "#0F766E",
                    fontWeight: "600",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <Play size={16} color="#0F766E" />
                  Simulation Monitor
                </button>

                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    onOpenSettings();
                  }}
                  style={{
                    width: "100%",
                    padding: "10px 16px",
                    textAlign: "left",
                    backgroundColor: "transparent",
                    border: "none",
                    fontSize: "13px",
                    color: "#334155",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <Settings size={16} color="#64748B" />
                  Account Settings
                </button>
              </div>

              <div style={{ borderTop: "1px solid #F1F5F9", paddingTop: "4px" }}>
                <button
                  onClick={handleLogout}
                  style={{
                    width: "100%",
                    padding: "10px 16px",
                    textAlign: "left",
                    backgroundColor: "transparent",
                    border: "none",
                    fontSize: "13px",
                    color: "#EF4444",
                    fontWeight: "600",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <LogOut size={16} color="#EF4444" />
                  Log Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
