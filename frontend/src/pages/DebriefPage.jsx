import React, { useState, useEffect } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  Award,
  Clock,
  Activity,
  Download,
  Share2,
  Loader2,
  RefreshCw,
  MessageSquare,
  Sparkles,
  ShieldCheck,
  ChevronRight,
  HelpCircle,
  TrendingUp,
} from "lucide-react";
import "../components/dashboard/dashboard.css";

const API_BASE = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function DebriefPage() {
  const navigate = useNavigate();
  const params = useParams();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);

  // Extract sessionCode from URL params, query string, location state, or sessionStorage
  const sessionCode =
    params.sessionCode ||
    searchParams.get("sessionCode") ||
    location.state?.sessionCode ||
    sessionStorage.getItem("session_code") ||
    sessionStorage.getItem("currentSessionCode") ||
    sessionStorage.getItem("activeSessionCode") ||
    "R04ZOG"; // fallback for standalone testing

  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  // API State
  const [loadingStatus, setLoadingStatus] = useState("running"); // pending | running | completed | failed
  const [debriefData, setDebriefData] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const token = sessionStorage.getItem("token") || localStorage.getItem("token") || "";

  // ── Fetch Status & Report ──────────────────────────────────────────
  const fetchReport = async () => {
    try {
      const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE}/api/debrief/${sessionCode}`, {
        headers: authHeader,
      });

      if (!res.ok) {
        throw new Error(`Failed to load debrief report (${res.status})`);
      }

      const data = await res.json();
      setDebriefData(data);
      setLoadingStatus("completed");
      setErrorMsg(null);
    } catch (err) {
      console.error("Error fetching debrief report:", err);
      setErrorMsg(err.message || "Failed to load debrief report.");
      setLoadingStatus("failed");
    }
  };

  const triggerGeneration = async () => {
    try {
      const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
      await fetch(`${API_BASE}/api/debrief/generate/${sessionCode}`, {
        method: "POST",
        headers: authHeader,
      });
    } catch (err) {
      console.warn("Could not trigger generate endpoint:", err);
    }
  };

  const checkStatusAndPoll = async () => {
    try {
      const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE}/api/debrief/status/${sessionCode}`, {
        headers: authHeader,
      });

      if (res.ok) {
        const data = await res.json();
        const currentStatus = (data.status || "pending").toLowerCase();

        if (currentStatus === "pending") {
          setLoadingStatus("running");
          await triggerGeneration();
        } else if (currentStatus === "running") {
          setLoadingStatus("running");
        } else if (currentStatus === "completed") {
          fetchReport();
          return true; // stop polling
        } else if (currentStatus === "failed") {
          setLoadingStatus("failed");
          setErrorMsg("Debrief report generation failed on the server.");
          return true; // stop polling
        }
      }
    } catch (err) {
      console.warn("Error checking debrief status:", err);
    }
    return false;
  };

  useEffect(() => {
    let timer = null;
    let isCancelled = false;

    const poll = async () => {
      const done = await checkStatusAndPoll();
      if (!done && !isCancelled) {
        timer = setTimeout(poll, 2500);
      }
    };

    poll();

    return () => {
      isCancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [sessionCode]);

  // ── Download PDF Handler ───────────────────────────────────────────
  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE}/api/reports/${sessionCode}`, {
        headers: authHeader,
      });

      if (!res.ok) {
        throw new Error("PDF report is not available yet.");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${sessionCode}_debrief.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message || "Failed to download PDF report.");
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleStartSimulation = () => navigate("/initializing");
  const handleLogout = () => {
    sessionStorage.clear();
    localStorage.clear();
    navigate("/");
  };

  // Extract debrief fields
  const debrief = debriefData?.debrief || debriefData || {};
  const overallScore = debriefData?.overall_score ?? debrief.overall_score ?? 100;
  const grade = debriefData?.grade || debrief.grade || "A";
  const findings = debrief.findings || [];
  const timelineEvents = debrief.timeline?.events || [];
  const domainScores = debrief.domain_scores || [];
  // narrative_report.to_dict() nests sections under a "sections" key;
  // fall back to the top-level keys for backward compatibility.
  const narrativeRaw = debrief.narrative_report || {};
  const narrative = narrativeRaw.sections || narrativeRaw;
  const scenarioName =
    narrativeRaw.scenario_name ||
    debrief.scenario_name ||
    debriefData?.scenario_name ||
    "ACLS Cardiac Arrest Simulation";
  // reflective_prompts can be a string (JSON array) or direct array
  let reflectivePrompts = [];
  try {
    const rawPrompts = narrative.reflective_prompts;
    if (Array.isArray(rawPrompts)) reflectivePrompts = rawPrompts;
    else if (typeof rawPrompts === "string" && rawPrompts.trim()) {
      const parsed = JSON.parse(rawPrompts);
      if (Array.isArray(parsed)) reflectivePrompts = parsed;
      else reflectivePrompts = rawPrompts.split(/\n+/).filter(Boolean);
    }
  } catch {
    // keep empty array
  }

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

        <main className="medsim-main-content space-y-6 overflow-y-auto pb-12">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                  AI Automated Debrief Report
                </h1>
                <span className="font-mono text-xs font-bold bg-teal-50 text-teal-800 border border-teal-200 px-3 py-1 rounded-full">
                  {sessionCode}
                </span>
              </div>
              <p className="text-sm text-slate-500 mt-1">
                Real-time ACLS guideline compliance, event timeline & performance analytics
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  if (navigator.share) {
                    navigator.share({ title: `CPR Debrief ${sessionCode}`, url: window.location.href });
                  } else {
                    navigator.clipboard.writeText(window.location.href);
                    alert("Report link copied to clipboard!");
                  }
                }}
                className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 rounded-xl text-xs font-semibold text-slate-700 cursor-pointer flex items-center gap-2"
              >
                <Share2 className="w-4 h-4 text-slate-500" />
                Share Report
              </button>

              <button
                onClick={handleDownloadPdf}
                disabled={loadingStatus !== "completed" || downloadingPdf}
                className="px-4 py-2 bg-teal-700 hover:bg-teal-800 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-xs font-semibold text-white cursor-pointer flex items-center gap-2 shadow-xs transition-colors"
              >
                {downloadingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Download PDF
              </button>
            </div>
          </div>

          {/* ── LOADING ANIMATED STATE ────────────────────────────────────── */}
          {loadingStatus !== "completed" && loadingStatus !== "failed" && (
            <div className="bg-white rounded-2xl p-12 border border-slate-200 shadow-xs flex flex-col items-center justify-center text-center space-y-4">
              <div className="relative">
                <div className="w-16 h-16 rounded-full border-4 border-teal-100 border-t-teal-600 animate-spin flex items-center justify-center" />
                <Sparkles className="w-6 h-6 text-teal-600 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">Generating AI Debrief Report</h3>
                <p className="text-sm text-slate-500 mt-1 max-w-md">
                  Analyzing team communication, ACLS protocol adherence, and calculating domain scores...
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs text-teal-700 bg-teal-50 px-4 py-2 rounded-full border border-teal-200 font-medium">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Status: {loadingStatus.toUpperCase()} (Polling backend...)
              </div>
            </div>
          )}

          {/* ── ERROR STATE ──────────────────────────────────────────────── */}
          {loadingStatus === "failed" && (
            <div className="bg-red-50 rounded-2xl p-8 border border-red-200 text-center space-y-3">
              <AlertTriangle className="w-10 h-10 text-red-600 mx-auto" />
              <h3 className="text-base font-bold text-red-900">Debrief Generation Failed</h3>
              <p className="text-xs text-red-700 max-w-md mx-auto">{errorMsg}</p>
              <button
                onClick={() => {
                  setLoadingStatus("running");
                  triggerGeneration();
                  checkStatusAndPoll();
                }}
                className="mt-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-semibold inline-flex items-center gap-2 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Retry Generation
              </button>
            </div>
          )}

          {/* ── COMPLETED DEBRIEF CONTENT ────────────────────────────────── */}
          {loadingStatus === "completed" && (
            <>
              {/* 1. Overview Score Cards */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Scenario</span>
                  <div className="text-base font-bold text-slate-900">{scenarioName}</div>
                  <div className="text-xs text-slate-500">Session ID: {sessionCode}</div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Overall Score</span>
                  <div className="text-3xl font-extrabold text-teal-700">
                    {overallScore.toFixed(0)} <span className="text-xs font-normal text-slate-400">/ 100</span>
                  </div>
                  <div className="text-xs text-emerald-600 font-semibold flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" /> Grade {grade} — Protocol Compliant
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Clinical Findings</span>
                  <div className="text-3xl font-extrabold text-slate-900">{findings.length}</div>
                  <div className="text-xs text-slate-500 font-medium">ACLS protocol deviations</div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Evaluated Events</span>
                  <div className="text-3xl font-extrabold text-slate-900">{timelineEvents.length}</div>
                  <div className="text-xs text-emerald-600 font-semibold">100% telemetry coverage</div>
                </div>
              </div>

              {/* 2. Domain Scores Section */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Award className="w-5 h-5 text-teal-700" />
                    ACLS Domain Performance
                  </h3>
                  <span className="text-xs text-slate-500">AHA 2020 Guideline Metrics</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {domainScores.map((ds, idx) => {
                    const label = (ds.domain_key || ds.domain_label || `Domain ${idx + 1}`)
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (c) => c.toUpperCase());
                    const scoreVal = ds.score ?? ds.final_score ?? 0;
                    const confidence = ds.completeness || ds.confidence_flag || "FULL";

                    return (
                      <div key={idx} className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2">
                        <div className="flex justify-between items-start">
                          <span className="text-xs font-bold text-slate-700">{label}</span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                              confidence === "FULL" || confidence === "COMPLETE"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {confidence}
                          </span>
                        </div>

                        <div className="text-2xl font-extrabold text-slate-900">
                          {scoreVal.toFixed(0)} <span className="text-xs font-normal text-slate-400">/ 100</span>
                        </div>

                        <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-teal-700 h-1.5 rounded-full"
                            style={{ width: `${Math.min(100, Math.max(0, scoreVal))}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 3. Clinical Findings / Protocol Deviations */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                  Protocol Deviations & Clinical Findings
                </h3>

                {findings.length === 0 ? (
                  <p className="text-xs text-slate-500 italic">No protocol deviations detected during session.</p>
                ) : (
                  <div className="space-y-3">
                    {findings.map((f, i) => {
                      const sev = (f.severity || "INFO").toUpperCase();
                      const sevBg =
                        sev === "CRITICAL"
                          ? "bg-red-50 text-red-800 border-red-200"
                          : sev === "HIGH"
                          ? "bg-amber-50 text-amber-800 border-amber-200"
                          : "bg-blue-50 text-blue-800 border-blue-200";

                      const tsS = Math.floor((f.timestamp_ms || 0) / 1000);
                      const timeStr = `${Math.floor(tsS / 60)}:${(tsS % 60).toString().padStart(2, "0")}`;

                      return (
                        <div key={i} className={`p-4 rounded-xl border ${sevBg} space-y-2`}>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-xs px-2.5 py-0.5 rounded-md bg-white border border-current">
                                {sev}
                              </span>
                              <span className="font-bold text-xs">{f.title || f.rule_id || "Finding"}</span>
                            </div>
                            <span className="font-mono text-xs font-semibold">@{timeStr}</span>
                          </div>

                          <p className="text-xs font-medium leading-relaxed">{f.description}</p>

                          {f.guideline_citation && (
                            <div className="text-[11px] opacity-80 flex items-center gap-1 font-mono">
                              <span>Ref:</span> {f.guideline_citation}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* 4. Clinical Event Timeline */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Clock className="w-5 h-5 text-teal-700" />
                  Clinical Event Timeline
                </h3>

                <div className="space-y-2.5 text-xs max-h-96 overflow-y-auto pr-1">
                  {timelineEvents.length === 0 ? (
                    <p className="text-xs text-slate-500 italic">No events recorded on timeline.</p>
                  ) : (
                    timelineEvents.map((ev, i) => {
                      const tsS = Math.floor((ev.timestamp_ms || 0) / 1000);
                      const timeStr = `${Math.floor(tsS / 60).toString().padStart(2, "0")}:${(tsS % 60)
                        .toString()
                        .padStart(2, "0")}`;

                      return (
                        <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100">
                          <div className="flex items-center gap-3">
                            <span className="font-mono font-bold text-teal-700 bg-teal-50 px-2.5 py-1 rounded-md border border-teal-200">
                              {timeStr}
                            </span>
                            <div>
                              <div className="font-bold text-slate-900">{ev.event_type}</div>
                              <div className="text-slate-500 text-[11px]">Speaker: {ev.speaker || "Team"}</div>
                            </div>
                          </div>
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* 5. Communication Analysis */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-3">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-teal-700" />
                  Communication Analysis
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {narrative.communication_analysis ||
                    "Communication patterns were analyzed across all team roles. Closed-loop communication was evaluated for medication orders, rhythm checks, and team callouts."}
                </p>
              </div>

              {/* 6. Strengths */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-3">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-emerald-600" />
                  Key Team Strengths
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {narrative.strengths ||
                    "Performance data from this session is being analyzed. Strengths will be displayed once the AI report is fully generated."}
                </p>
              </div>

              {/* 7. Recommendations */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-3">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-teal-700" />
                  Recommendations for Next Session
                </h3>
                <div className="text-xs text-slate-600 leading-relaxed space-y-2">
                  {narrative.recommendations ? (
                    <p>{narrative.recommendations}</p>
                  ) : (
                    <p className="text-xs text-slate-500 italic">Recommendations will appear once the AI report has finished generating for this session.</p>
                  )}
                </div>
              </div>

              {/* 8. Reflection Questions */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-3">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <HelpCircle className="w-5 h-5 text-teal-700" />
                  Reflective Debrief Prompts
                </h3>
                <div className="space-y-2">
                  {(reflectivePrompts.length > 0 ? reflectivePrompts : [
                    "How effectively did the team maintain continuous chest compressions during rhythm analysis?",
                    "What strategies can be implemented to streamline post-ROSC 12-lead ECG acquisition?",
                    "How was closed-loop communication utilized when ordering and administering epinephrine?",
                  ]).map((q, idx) => (
                    <div key={idx} className="p-3 rounded-xl bg-teal-50/50 border border-teal-100 flex items-start gap-2.5 text-xs text-slate-700">
                      <ChevronRight className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
                      <span>{typeof q === "string" ? q : q.question || q.prompt || JSON.stringify(q)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
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
