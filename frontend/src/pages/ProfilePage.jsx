import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import { User, Mail, Shield, Award, Calendar } from "lucide-react";
import "../components/dashboard/dashboard.css";

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  const username = user?.username || "Instructor";
  const initials = username.substring(0, 2).toUpperCase();
  const displayName = username.charAt(0).toUpperCase() + username.slice(1);
  const displayRole = user?.role === "student" ? "Student" : "Verified Clinical Instructor";

  const handleStartSimulation = () => {
    navigate("/initializing");
  };

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
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
              User Profile
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Account details & clinical simulation credentials
            </p>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-8 max-w-2xl space-y-6">
            <div className="flex items-center gap-4 pb-6 border-b border-slate-100">
              <div className="w-16 h-16 rounded-full bg-teal-700 text-white text-2xl font-bold flex items-center justify-center">
                {initials}
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">{displayName}</h2>
                <div className="text-xs text-slate-500 font-medium">{displayRole}</div>
                <span className="inline-block mt-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 text-teal-700 border border-teal-200 uppercase">
                  {user?.role || "Active Account"}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-slate-400 font-medium block uppercase text-[10px]">Username</span>
                <span className="font-bold text-slate-900 text-sm">{user?.username || "N/A"}</span>
              </div>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-slate-400 font-medium block uppercase text-[10px]">Assigned Role</span>
                <span className="font-bold text-slate-900 text-sm capitalize">{user?.role || "Instructor"}</span>
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
