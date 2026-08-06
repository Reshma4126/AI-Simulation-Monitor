import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import { FileText, CheckCircle2, Award, Clock, Activity, Download, Share2 } from "lucide-react";
import "../components/dashboard/dashboard.css";

export default function DebriefPage() {
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
          activeTab="reports"
          setActiveTab={(tab) => {
            if (tab === "dashboard") navigate("/dashboard");
          }}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                AI Automated Debrief Report
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                Comprehensive performance analytics & event timeline
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 rounded-xl text-xs font-semibold text-slate-700 cursor-pointer flex items-center gap-2">
                <Share2 className="w-4 h-4 text-slate-500" />
                Share Report
              </button>
              <button className="px-4 py-2 bg-teal-700 hover:bg-teal-800 rounded-xl text-xs font-semibold text-white cursor-pointer flex items-center gap-2 shadow-xs">
                <Download className="w-4 h-4" />
                Download PDF
              </button>
            </div>
          </div>

          {/* Overview Score Card */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-400 uppercase">Scenario</span>
              <div className="text-lg font-bold text-slate-900">VF Cardiac Arrest</div>
              <div className="text-xs text-slate-500">Patient: Robert Chen (62M)</div>
            </div>

            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-400 uppercase">Overall Score</span>
              <div className="text-3xl font-extrabold text-teal-700">94 <span className="text-xs font-normal text-slate-400">/ 100</span></div>
              <div className="text-xs text-emerald-600 font-semibold">Exceeds Benchmark</div>
            </div>

            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-400 uppercase">CPR Latency</span>
              <div className="text-2xl font-bold text-slate-900">42 sec</div>
              <div className="text-xs text-emerald-600 font-semibold">Target: &lt;60s (Passed)</div>
            </div>

            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-400 uppercase">Defibrillation</span>
              <div className="text-2xl font-bold text-slate-900">1m 14s</div>
              <div className="text-xs text-emerald-600 font-semibold">Optimal timing</div>
            </div>
          </div>

          {/* Clinical Milestones Timeline */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
            <h3 className="text-base font-bold text-slate-900">Clinical Event Timeline</h3>

            <div className="space-y-3 text-xs">
              {[
                { time: "00:00", title: "Simulation Started", desc: "Patient presented with loss of consciousness and VF rhythm", status: "pass" },
                { time: "00:42", title: "Chest Compressions Initiated", desc: "High-quality CPR started at rate of 110 bpm", status: "pass" },
                { time: "01:14", title: "First Defibrillation Shock (200J)", desc: "Biphasic shock delivered cleanly with team clear alert", status: "pass" },
                { time: "03:00", title: "IV Epinephrine Administered", desc: "1mg Epinephrine IV push administered per ACLS protocol", status: "pass" },
                { time: "05:12", title: "ROSC Achieved", desc: "Return of spontaneous circulation noted; Sinus Rhythm at 92 bpm", status: "pass" },
              ].map((ev, i) => (
                <div key={i} className="flex items-start gap-4 p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <span className="font-mono font-bold text-teal-700 bg-teal-50 px-2.5 py-1 rounded-md border border-teal-200">
                    {ev.time}
                  </span>
                  <div className="flex-1">
                    <div className="font-bold text-slate-900">{ev.title}</div>
                    <div className="text-slate-500 mt-0.5">{ev.desc}</div>
                  </div>
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
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
