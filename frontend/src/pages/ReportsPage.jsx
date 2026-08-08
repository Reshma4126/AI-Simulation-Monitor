import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import { FileText, Download, Filter, Search, Loader2, AlertCircle } from "lucide-react";
import "../components/dashboard/dashboard.css";

const API_BASE = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function ReportsPage() {
  const navigate = useNavigate();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const token = sessionStorage.getItem("token") || localStorage.getItem("token") || "";

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/debrief/list?limit=50`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setReports(data.reports || []);
        } else {
          throw new Error(`Failed to load reports (${res.status})`);
        }
      } catch (err) {
        console.error("Error fetching reports:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchReports();
  }, []);

  const handleStartSimulation = () => navigate("/initializing");
  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return "—";
    try {
      return new Date(isoStr).toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
    } catch {
      return isoStr;
    }
  };

  const filteredReports = reports.filter((r) =>
    r.session_code?.toLowerCase().includes(searchQuery.toLowerCase())
  );

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

        <main className="medsim-main-content space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Clinical Performance Reports
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Archived AI debrief reports and student evaluation transcripts
            </p>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by session code..."
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
              {loading && (
                <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-400">
                  <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
                  <span className="text-sm">Loading reports...</span>
                </div>
              )}

              {!loading && error && (
                <div className="py-8 flex flex-col items-center gap-2 text-red-500">
                  <AlertCircle className="w-6 h-6" />
                  <p className="text-sm font-medium">{error}</p>
                </div>
              )}

              {!loading && !error && filteredReports.length === 0 && (
                <div className="py-12 text-center text-slate-400 text-sm">
                  <FileText className="w-10 h-10 mx-auto mb-3 opacity-40" />
                  <p className="font-medium">No completed debrief reports found</p>
                  <p className="text-xs mt-1">Reports appear here after a simulation session ends and the AI debrief is generated.</p>
                </div>
              )}

              {!loading && filteredReports.map((rep) => (
                <div key={rep.session_code} className="py-4 flex items-center justify-between hover:bg-slate-50 px-3 rounded-xl transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-bold text-sm text-slate-900">
                        Session <span className="font-mono">{rep.session_code}</span>
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatDate(rep.updated_at || rep.created_at)} •
                        Grade <span className="font-semibold text-teal-700">{rep.grade || "N/A"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-sm font-extrabold text-teal-700">
                        {rep.overall_score != null ? `${Math.round(rep.overall_score)}%` : "—"}
                      </div>
                      <div className="text-[10px] text-emerald-600 font-semibold uppercase">
                        {rep.status}
                      </div>
                    </div>

                    <button
                      onClick={() => navigate(`/debrief?sessionCode=${rep.session_code}`)}
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
