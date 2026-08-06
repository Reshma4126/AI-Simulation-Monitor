import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import { FileText, Download, Filter, Search } from "lucide-react";
import "../components/dashboard/dashboard.css";

export default function ReportsPage() {
  const navigate = useNavigate();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  const reports = [
    { id: 1, title: "VF Cardiac Arrest - Batch A", date: "06 Aug 2026", score: "94%", author: "Dr. John Doe", status: "Verified" },
    { id: 2, title: "Anaphylaxis Crisis Evaluation", date: "05 Aug 2026", score: "88%", author: "Dr. John Doe", status: "Verified" },
    { id: 3, title: "Pediatric Status Asthmaticus Audit", date: "05 Aug 2026", score: "91%", author: "Dr. Jane Smith", status: "Verified" },
    { id: 4, title: "STEMI Interventional Response", date: "04 Aug 2026", score: "85%", author: "Dr. John Doe", status: "Draft" },
  ];

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
          activeTab="reports"
          setActiveTab={(tab) => {
            if (tab === "dashboard") navigate("/dashboard");
          }}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Clinical Performance Reports
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Archived debrief reports and student evaluation transcripts
            </p>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search reports by title or instructor..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full h-10 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:border-teal-700"
                />
              </div>

              <button className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-100 flex items-center gap-2">
                <Filter className="w-3.5 h-3.5" />
                Filter Date
              </button>
            </div>

            <div className="divide-y divide-slate-100">
              {reports.map((rep) => (
                <div key={rep.id} className="py-4 flex items-center justify-between hover:bg-slate-50 px-3 rounded-xl transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-bold text-sm text-slate-900">{rep.title}</div>
                      <div className="text-xs text-slate-500">{rep.date} • Evaluator: {rep.author}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-sm font-extrabold text-teal-700">{rep.score}</div>
                      <div className="text-[10px] text-emerald-600 font-semibold">{rep.status}</div>
                    </div>

                    <button
                      onClick={() => navigate("/debrief")}
                      className="px-3.5 py-1.5 bg-white border border-teal-200 hover:bg-teal-700 hover:text-white rounded-lg text-xs font-semibold text-teal-700 transition-all flex items-center gap-1.5"
                    >
                      <Download className="w-3.5 h-3.5" />
                      View Report
                    </button>
                  </div>
                </div>
              ))}
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
