import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import RecentSessions from "../components/dashboard/RecentSessions";
import SearchBar from "../components/cases/SearchBar";
import "../components/dashboard/dashboard.css";

export default function SessionsPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  const initialSessions = [
    { id: 1, name: "VF Cardiac Arrest", date: "06 Aug 2026", status: "Completed", duration: "12 Minutes", patient: "Robert Chen, 62M", score: "94%" },
    { id: 2, name: "Anaphylactic Shock", date: "06 Aug 2026", status: "Active", duration: "18 Minutes", patient: "Emma Watson, 28F", score: "In Progress" },
    { id: 3, name: "Acute STEMI", date: "05 Aug 2026", status: "Completed", duration: "15 Minutes", patient: "Arthur Pendelton, 55M", score: "88%" },
    { id: 4, name: "Pediatric Asthma Crisis", date: "05 Aug 2026", status: "Pending Debrief", duration: "22 Minutes", patient: "Leo Garcia, 8M", score: "Pending" },
    { id: 5, name: "Septic Shock Management", date: "04 Aug 2026", status: "Completed", duration: "25 Minutes", patient: "Eleanor Vance, 71F", score: "91%" },
    { id: 6, name: "Hypovolemic Shock Trauma", date: "03 Aug 2026", status: "Completed", duration: "30 Minutes", patient: "Arun Das, 45M", score: "89%" },
    { id: 7, name: "Symptomatic Bradycardia", date: "02 Aug 2026", status: "Completed", duration: "16 Minutes", patient: "Ramesh Kumar, 65M", score: "95%" },
  ];

  const filteredSessions = initialSessions.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.date.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.status.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleStartSimulation = () => {
    navigate("/initializing");
  };

  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  return (
    <div className="medsim-dashboard-page">
      <Navbar
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        showNotifications={showNotifications}
        setShowNotifications={setShowNotifications}
        showProfileMenu={showProfileMenu}
        setShowProfileMenu={setShowProfileMenu}
        handleStartSimulation={handleStartSimulation}
        handleLogout={handleLogout}
        onOpenSettings={() => setActiveModal("settings")}
      />

      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          setSidebarExpanded={setSidebarExpanded}
          activeTab="sessions"
          setActiveTab={(tab) => {
            if (tab === "dashboard") navigate("/dashboard");
          }}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Clinical Sessions History
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              View and audit all past and active simulation runs
            </p>
          </div>

          <SearchBar searchQuery={searchQuery} setSearchQuery={setSearchQuery} />

          <RecentSessions
            sessions={filteredSessions}
            searchQuery={searchQuery}
            handleStartSimulation={handleStartSimulation}
            onOpenModal={(modalType) => setActiveModal(modalType)}
          />
        </main>
      </div>

      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={handleStartSimulation}
        initialSessions={initialSessions}
      />
    </div>
  );
}
