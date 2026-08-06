import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import { User, Mail, Shield, Award, Calendar } from "lucide-react";
import "../components/dashboard/dashboard.css";

export default function ProfilePage() {
  const navigate = useNavigate();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

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
          activeTab="profile"
          setActiveTab={(tab) => {
            if (tab === "dashboard") navigate("/dashboard");
          }}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Instructor Profile
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Account details & clinical simulation credentials
            </p>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-8 max-w-2xl space-y-6">
            <div className="flex items-center gap-4 pb-6 border-b border-slate-100">
              <div className="w-16 h-16 rounded-full bg-teal-700 text-white text-2xl font-bold flex items-center justify-center">
                JD
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">Dr. John Doe</h2>
                <div className="text-xs text-slate-500 font-medium">Senior Clinical Simulation Instructor</div>
                <span className="inline-block mt-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 text-teal-700 border border-teal-200 uppercase">
                  Verified Instructor
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-slate-400 font-medium block uppercase text-[10px]">Email Address</span>
                <span className="font-bold text-slate-900 text-sm">john.doe@hospital.org</span>
              </div>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-slate-400 font-medium block uppercase text-[10px]">Institution</span>
                <span className="font-bold text-slate-900 text-sm">St. Jude Simulation Center</span>
              </div>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-slate-400 font-medium block uppercase text-[10px]">Total Conducted Sessions</span>
                <span className="font-bold text-slate-900 text-sm">128 Sessions</span>
              </div>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-slate-400 font-medium block uppercase text-[10px]">Account Created</span>
                <span className="font-bold text-slate-900 text-sm">15 Jan 2025</span>
              </div>
            </div>
          </div>
        </main>
      </div>

      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={handleStartSimulation}
        initialSessions={[]}
      />
    </div>
  );
}
