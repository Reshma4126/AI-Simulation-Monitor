import React from "react";
import { useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Activity,
  ClipboardList,
  FileText,
  BookOpen,
  Settings,
} from "lucide-react";
import "./dashboard.css";

export default function Sidebar({
  sidebarExpanded,
  setSidebarExpanded,
  activeTab,
  setActiveTab,
  handleStartSimulation,
  onOpenModal,
}) {
  const navigate = useNavigate();

  const navItems = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
      onClick: () => {
        if (setActiveTab) setActiveTab("dashboard");
        navigate("/dashboard");
      },
    },
    {
      id: "simulation",
      label: "Simulation",
      icon: Activity,
      onClick: () => {
        if (handleStartSimulation) handleStartSimulation();
        else navigate("/initializing");
      },
    },
    {
      id: "sessions",
      label: "Sessions",
      icon: ClipboardList,
      onClick: () => {
        if (setActiveTab) setActiveTab("sessions");
        navigate("/sessions");
      },
    },
    {
      id: "reports",
      label: "Debrief Reports",
      icon: FileText,
      onClick: () => {
        if (setActiveTab) setActiveTab("reports");
        navigate("/reports");
      },
    },
    {
      id: "library",
      label: "Scenario Library",
      icon: BookOpen,
      onClick: () => {
        if (setActiveTab) setActiveTab("library");
        navigate("/cases");
      },
    },
    {
      id: "settings",
      label: "Settings",
      icon: Settings,
      onClick: () => {
        if (setActiveTab) setActiveTab("settings");
        navigate("/settings");
      },
    },
  ];

  return (
    <aside
      onMouseEnter={() => setSidebarExpanded(true)}
      onMouseLeave={() => setSidebarExpanded(false)}
      className={`medsim-sidebar ${sidebarExpanded ? "expanded" : "collapsed"}`}
    >
      <div style={{ padding: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={item.onClick}
              className={`medsim-nav-item ${isActive ? "active" : ""}`}
            >
              <Icon size={20} color={isActive ? "#0F766E" : "#64748B"} style={{ flexShrink: 0 }} />
              <span
                style={{
                  opacity: sidebarExpanded ? 1 : 0,
                  transition: "opacity 0.2s ease",
                }}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
