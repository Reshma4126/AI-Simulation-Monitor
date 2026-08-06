import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import SearchBar from "../components/cases/SearchBar";
import CaseFilter from "../components/cases/CaseFilter";
import CaseCard from "../components/cases/CaseCard";
import CaseDetailsDrawer from "../components/cases/CaseDetailsDrawer";
import { CLINICAL_CASES } from "../data/casesData";
import "../components/dashboard/dashboard.css";

export default function CaseLibraryPage() {
  const navigate = useNavigate();

  // State
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("All");
  const [casesList, setCasesList] = useState(CLINICAL_CASES);
  const [selectedCase, setSelectedCase] = useState(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  // Toggle favorite
  const handleToggleFavorite = (caseId) => {
    setCasesList((prev) =>
      prev.map((c) => (c.id === caseId ? { ...c, isFavorite: !c.isFavorite } : c))
    );
  };

  // Filter & Search Logic
  const filteredCases = casesList.filter((item) => {
    // Search query match
    const query = searchQuery.toLowerCase();
    const matchesSearch =
      item.patientName.toLowerCase().includes(query) ||
      item.diagnosis.toLowerCase().includes(query) ||
      item.chiefComplaint.toLowerCase().includes(query) ||
      item.category.toLowerCase().includes(query);

    if (!matchesSearch) return false;

    // Filter chip match
    if (activeFilter === "All") return true;
    if (activeFilter === "Favorites") return item.isFavorite;
    return item.category === activeFilter;
  });

  const favoritesCount = casesList.filter((c) => c.isFavorite).length;

  const handleStartSimulation = (caseItem) => {
    if (caseItem) {
      sessionStorage.setItem("selected_case", JSON.stringify(caseItem));
    }
    navigate("/initializing");
  };

  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  return (
    <div className="medsim-dashboard-page">
      {/* Navbar (Same as DashboardPage) */}
      <Navbar
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        showNotifications={showNotifications}
        setShowNotifications={setShowNotifications}
        showProfileMenu={showProfileMenu}
        setShowProfileMenu={setShowProfileMenu}
        handleStartSimulation={() => handleStartSimulation(null)}
        handleLogout={handleLogout}
        onOpenSettings={() => setActiveModal("settings")}
      />

      {/* Main Body */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        {/* Sidebar (Same as DashboardPage) */}
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          setSidebarExpanded={setSidebarExpanded}
          activeTab="library"
          setActiveTab={(tab) => {
            if (tab === "dashboard") navigate("/dashboard");
          }}
          handleStartSimulation={() => handleStartSimulation(null)}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        {/* Scrollable Main Content */}
        <main className="medsim-main-content">
          {/* Top Section */}
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Case Library
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Select a clinical case to begin a simulation.
            </p>
          </div>

          {/* Search Bar */}
          <SearchBar searchQuery={searchQuery} setSearchQuery={setSearchQuery} />

          {/* Filter Chips */}
          <CaseFilter
            activeFilter={activeFilter}
            setActiveFilter={setActiveFilter}
            favoritesCount={favoritesCount}
          />

          {/* Case Grid */}
          <section>
            {filteredCases.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                {filteredCases.map((caseItem) => (
                  <CaseCard
                    key={caseItem.id}
                    caseItem={caseItem}
                    onSelectCase={(c) => setSelectedCase(c)}
                    onToggleFavorite={handleToggleFavorite}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-500 text-sm">
                No clinical cases found matching your search and filter criteria.
              </div>
            )}
          </section>
        </main>
      </div>

      {/* Case Details Sliding Drawer */}
      <CaseDetailsDrawer
        selectedCase={selectedCase}
        onClose={() => setSelectedCase(null)}
        onStartSimulation={handleStartSimulation}
      />

      {/* Dashboard Modals */}
      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={() => handleStartSimulation(null)}
        initialSessions={[]}
      />
    </div>
  );
}
