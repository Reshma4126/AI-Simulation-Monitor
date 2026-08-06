import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import WelcomeCard from "../components/dashboard/WelcomeCard";
import QuickActions from "../components/dashboard/QuickActions";
import Statistics from "../components/dashboard/Statistics";
import RecentSessions from "../components/dashboard/RecentSessions";
import DashboardModals from "../components/dashboard/DashboardModals";
import "../components/dashboard/dashboard.css";

export default function DashboardPage() {
  const navigate = useNavigate();

  // State
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [activeModal, setActiveModal] = useState(null); // 'library', 'reports', 'settings', 'sessions'

  // Sessions Data
  const initialSessions = [
    {
      id: 1,
      name: "VF Cardiac Arrest",
      date: "06 Aug 2026",
      status: "Completed",
      duration: "12 Minutes",
      patient: "Robert Chen, 62M",
      score: "94%",
    },
    {
      id: 2,
      name: "Anaphylactic Shock",
      date: "06 Aug 2026",
      status: "Active",
      duration: "18 Minutes",
      patient: "Emma Watson, 28F",
      score: "In Progress",
    },
    {
      id: 3,
      name: "Acute STEMI",
      date: "05 Aug 2026",
      status: "Completed",
      duration: "15 Minutes",
      patient: "Arthur Pendelton, 55M",
      score: "88%",
    },
    {
      id: 4,
      name: "Pediatric Asthma Crisis",
      date: "05 Aug 2026",
      status: "Pending Debrief",
      duration: "22 Minutes",
      patient: "Leo Garcia, 8M",
      score: "Pending",
    },
    {
      id: 5,
      name: "Septic Shock Management",
      date: "04 Aug 2026",
      status: "Completed",
      duration: "25 Minutes",
      patient: "Eleanor Vance, 71F",
      score: "91%",
    },
  ];

  // Filtered Sessions
  const filteredSessions = initialSessions.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.date.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.status.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  const handleStartSimulation = () => {
    navigate("/cases");
  };

  return (
    <div className="medsim-dashboard-page">
      {/* Fixed Top Navbar */}
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

      {/* Main Body: Sidebar + Scrollable Content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        {/* Left Sidebar */}
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          setSidebarExpanded={setSidebarExpanded}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        {/* Scrollable Main Dashboard Content */}
        <main className="medsim-main-content">
          {/* Section 1: Welcome Card (Refined User State) */}
          <WelcomeCard handleStartSimulation={handleStartSimulation} />

          {/* Section 2: Quick Actions */}
          <QuickActions
            handleStartSimulation={handleStartSimulation}
            onOpenModal={(modalType) => setActiveModal(modalType)}
          />

          {/* Section 3: Statistics */}
          <Statistics />

          {/* Section 4: Recent Sessions */}
          <RecentSessions
            sessions={filteredSessions}
            searchQuery={searchQuery}
            handleStartSimulation={handleStartSimulation}
            onOpenModal={(modalType) => setActiveModal(modalType)}
          />
        </main>
      </div>

      {/* Interactive Modals */}
      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={handleStartSimulation}
        initialSessions={initialSessions}
      />
    </div>
  );
}
