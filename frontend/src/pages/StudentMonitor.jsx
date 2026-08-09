import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import socket from "../socket";
import useMonitorStore from "../store/monitorStore";
import { connect, disconnect } from "../engine/wsClient";
import AlarmBar from "../components/monitor/AlarmBar";
import VitalsPanel from "../components/monitor/VitalsPanel";
import WaveformStack from "../components/monitor/WaveformStack";
import {
  Activity,
  Clock,
  FileText,
  MessageSquare,
  ChevronRight,
  ChevronLeft,
  LogOut,
  UserCheck,
  AlertCircle
} from "lucide-react";
import "../styles/monitor.css";

export default function StudentMonitor() {
  const { sessionCode } = useParams();
  const navigate = useNavigate();
  const setFullState = useMonitorStore((s) => s.setFullState);
  
  const [comments, setComments] = useState([]);
  const [joinStatus, setJoinStatus] = useState("joining"); // "joining" | "joined" | "error"
  const [joinError, setJoinError] = useState("");
  const [scenario, setScenario] = useState(null);
  
  const [selectedLead, setSelectedLead] = useState("II");
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [activeTab, setActiveTab] = useState("case"); // "case" | "messages"

  // Timer for session duration
  const [elapsed, setElapsed] = useState(0);
  const sessionStartRef = useRef(Date.now());

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - sessionStartRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (s) => {
    const h = String(Math.floor(s / 3600)).padStart(2, "0");
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    const sec = String(s % 60).padStart(2, "0");
    return `${h}:${m}:${sec}`;
  };

  useEffect(() => {
    let token = sessionStorage.getItem("token");
    sessionStorage.setItem("session_code", sessionCode);

    const doJoin = () => {
      const currentToken = sessionStorage.getItem("token") || token || "student";
      console.log("[StudentMonitor] Emitting join_session for:", sessionCode);
      socket.emit("join_session", { session_code: sessionCode, token: currentToken });
    };

    const initConnection = async () => {
      if (!token) {
        try {
          const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
          const res = await fetch(`${API}/session/student-join`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_code: sessionCode })
          });
          if (res.ok) {
            const data = await res.json();
            token = data.token;
            sessionStorage.setItem("token", token);
          } else {
            const errData = await res.json().catch(() => ({}));
            setJoinStatus("error");
            setJoinError(errData.detail || "Session not available");
            return;
          }
        } catch (e) {
          console.error("[StudentMonitor] Auto-join failed:", e);
        }
      }

      if (!socket.connected) {
        socket.connect();
        socket.once("connect", doJoin);
      } else {
        doJoin();
      }
      
      connect(); // Connect to simman-ecg engine
    };

    initConnection();

    // ── Event handlers ──────────────────────────────────────
    const handleJoinConfirmed = (data) => {
      console.log("[StudentMonitor] join_confirmed:", data);
      setJoinStatus("joined");
    };

    const handleError = (data) => {
      console.error("[StudentMonitor] Socket error:", data.message);
      if (
        data.message?.includes("not found") ||
        data.message?.includes("has ended") ||
        data.message?.includes("Invalid token")
      ) {
        setJoinStatus("error");
        setJoinError(data.message);
        setTimeout(() => {
          sessionStorage.clear();
          navigate("/");
        }, 2000);
      }
    };

    const handleSessionEnded = () => {
      console.log("[StudentMonitor] session_ended — redirecting");
      setJoinStatus("error");
      setJoinError("Session has been finalized by the instructor.");
      setTimeout(() => {
        sessionStorage.clear();
        socket.disconnect();
        navigate("/");
      }, 2000);
    };

    const handleState = (state) => setFullState(state);
    const handleRhythm = (data) => setFullState(data);
    const handleAlarm = (data) => useMonitorStore.setState({ alarms: data.alarms });
    const handleFacultyComment = (msg) => {
      console.log("[StudentMonitor] faculty_comment received:", msg);
      setComments((prev) => [...prev, msg]);
    };
    const handleScenarioSelected = (data) => {
      console.log("[StudentMonitor] scenario_selected:", data);
      setScenario(data);
    };

    socket.on("join_confirmed", handleJoinConfirmed);
    socket.on("error", handleError);
    socket.on("session_ended", handleSessionEnded);
    socket.on("state_update", handleState);
    socket.on("rhythm_change", handleRhythm);
    socket.on("alarm_update", handleAlarm);
    socket.on("faculty_comment", handleFacultyComment);
    socket.on("scenario_selected", handleScenarioSelected);

    return () => {
      socket.off("join_confirmed", handleJoinConfirmed);
      socket.off("error", handleError);
      socket.off("session_ended", handleSessionEnded);
      socket.off("state_update", handleState);
      socket.off("rhythm_change", handleRhythm);
      socket.off("alarm_update", handleAlarm);
      socket.off("faculty_comment", handleFacultyComment);
      socket.off("scenario_selected", handleScenarioSelected);
      socket.off("connect", doJoin);
      disconnect(); // Disconnect from simman-ecg engine
    };
  }, [sessionCode, setFullState, navigate]);

  const handleExit = () => {
    sessionStorage.clear();
    socket.disconnect();
    navigate("/");
  };

  // Show redirect/error overlay
  if (joinStatus === "error") {
    return (
      <div style={{
        position: "fixed", inset: 0, background: "#0F172A",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        color: "white", fontFamily: "Inter, sans-serif", gap: 16
      }}>
        <AlertCircle size={54} color="#EF4444" />
        <div style={{ fontSize: 20, fontWeight: 700, color: "#F8FAFC" }}>{joinError || "Session Error"}</div>
        <div style={{ fontSize: 13, color: "#94A3B8" }}>Redirecting to login portal...</div>
      </div>
    );
  }

  // Parse scenario patient details cleanly
  const pd = scenario?.patient_details
    ? typeof scenario.patient_details === "string"
      ? JSON.parse(scenario.patient_details)
      : scenario.patient_details
    : null;

  const symp = scenario?.symptoms
    ? typeof scenario.symptoms === "string"
      ? JSON.parse(scenario.symptoms)
      : scenario.symptoms
    : null;

  const activeSymptoms = symp ? Object.entries(symp).filter(([, v]) => v === true) : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", backgroundColor: "#0F172A", color: "#F8FAFC", fontFamily: "Inter, sans-serif" }}>
      
      {/* TOP BAR - MATCHES INSTRUCTOR DASHBOARD DESIGN */}
      <div style={{
        height: 56,
        backgroundColor: "#1E293B",
        borderBottom: "1px solid #334155",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 16px",
        flexShrink: 0
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ backgroundColor: "#0F766E", padding: 6, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Activity size={20} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#F8FAFC", display: "flex", alignItems: "center", gap: 8 }}>
              MedSim AI
              <span style={{ fontSize: 10, fontWeight: 700, backgroundColor: "#0D9488", color: "#F0FDF4", padding: "2px 8px", borderRadius: 12, textTransform: "uppercase" }}>
                Student Monitor
              </span>
              <span style={{ fontSize: 11, fontWeight: 700, backgroundColor: "#334155", color: "#38BDF8", padding: "2px 8px", borderRadius: 4 }}>
                CODE: {sessionCode}
              </span>
            </div>
          </div>
        </div>

        {/* CENTER TIMING */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, backgroundColor: "#0F172A", padding: "4px 12px", borderRadius: 20, border: "1px solid #334155" }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: "#10B981", boxShadow: "0 0 8px #10B981" }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: "#10B981" }}>Live Simulation</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontFamily: "monospace", fontWeight: 700, color: "#94A3B8" }}>
            <Clock size={14} />
            {formatTime(elapsed)}
          </div>
        </div>

        {/* RIGHT ACTIONS */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
            title="Toggle Right Panel"
            style={{ backgroundColor: "#334155", color: "#F8FAFC", border: "1px solid #475569", padding: "6px 12px", borderRadius: 8, cursor: "pointer", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}
          >
            {rightPanelOpen ? <ChevronRight size={14} /> : <ChevronLeft size={14} />} Panel
          </button>
          <button
            onClick={handleExit}
            style={{ backgroundColor: "#EF4444", color: "#F8FAFC", border: "none", padding: "7px 16px", borderRadius: 8, cursor: "pointer", fontSize: 12, fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}
          >
            <LogOut size={14} /> Exit Portal
          </button>
        </div>
      </div>

      {/* MAIN 3-COLUMN LAYOUT */}
      <div style={{ display: "grid", gridTemplateColumns: rightPanelOpen ? "165px 1fr 285px" : "165px 1fr 0px", flex: 1, overflow: "hidden", transition: "all 0.25s ease" }}>
        
        {/* COLUMN 1: LIVE VITALS PANEL */}
        <div style={{ backgroundColor: "#0F172A", borderRight: "1px solid #1E293B", padding: "6px 8px", overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748B", textTransform: "uppercase", marginBottom: 4, letterSpacing: 0.5 }}>
            Live Vitals
          </div>
          <VitalsPanel onVitalClick={null} compact={true} isStudent={true} />
        </div>

        {/* COLUMN 2: CENTER WAVEFORMS & ALARMS */}
        <div style={{ backgroundColor: "#000000", display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
          
          {/* Collapsible Panel Toggle Arrow */}
          <button
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
            title={rightPanelOpen ? "Collapse Right Panel" : "Expand Right Panel"}
            style={{
              position: "absolute",
              top: 8,
              right: 8,
              zIndex: 50,
              backgroundColor: "#1E293B",
              color: "#10B981",
              border: "1px solid #334155",
              borderRadius: "50%",
              width: 28,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              boxShadow: "0 2px 8px rgba(0,0,0,0.6)",
              transition: "transform 0.2s ease"
            }}
          >
            {rightPanelOpen ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>

          <AlarmBar />
          <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
            <WaveformStack lead={selectedLead} onLeadSelect={setSelectedLead} />
          </div>
        </div>

        {/* COLUMN 3: RIGHT PANEL (CASE INFO & MESSAGES) */}
        <div style={{ backgroundColor: "#1E293B", borderLeft: rightPanelOpen ? "1px solid #334155" : "none", display: rightPanelOpen ? "flex" : "none", flexDirection: "column", overflow: "hidden" }}>
          
          {/* TAB HEADERS */}
          <div style={{ display: "flex", borderBottom: "1px solid #334155", backgroundColor: "#0F172A" }}>
            {[
              { id: "case", label: "Case Scenario", icon: FileText },
              { id: "messages", label: `Log (${comments.length})`, icon: MessageSquare }
            ].map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    flex: 1,
                    padding: "10px 4px",
                    backgroundColor: isActive ? "#1E293B" : "transparent",
                    color: isActive ? "#38BDF8" : "#94A3B8",
                    border: "none",
                    borderBottom: isActive ? "2px solid #38BDF8" : "2px solid transparent",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                    transition: "all 0.2s"
                  }}
                >
                  <Icon size={14} /> {tab.label}
                </button>
              );
            })}
          </div>

          {/* TAB CONTENT */}
          <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
            {activeTab === "case" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                
                {/* PATIENT PROFILE CARD */}
                <div style={{ backgroundColor: "#0F172A", border: "1px solid #334155", borderRadius: 10, padding: 14 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <div style={{ backgroundColor: "#1E293B", padding: 8, borderRadius: "50%" }}>
                      <UserCheck size={18} color="#38BDF8" />
                    </div>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: "#F8FAFC" }}>
                        {pd?.patientName || pd?.name || "Patient Record"}
                      </div>
                      <div style={{ fontSize: 11, color: "#94A3B8" }}>
                        {pd?.age ? `${pd.age} y/o` : ""} {pd?.gender ? `· ${pd.gender}` : ""} {pd?.bloodGroup ? `· ${pd.bloodGroup}` : ""}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 12, paddingTop: 6, borderTop: "1px solid #1E293B" }}>
                    <div>
                      <span style={{ color: "#64748B", display: "block", fontSize: 10, fontWeight: 600, textTransform: "uppercase" }}>Height / Weight</span>
                      <span style={{ color: "#CBD5E1", fontWeight: 600 }}>{pd?.heightCm ? `${pd.heightCm} cm` : "--"} / {pd?.weightKg ? `${pd.weightKg} kg` : "--"}</span>
                    </div>
                    <div>
                      <span style={{ color: "#64748B", display: "block", fontSize: 10, fontWeight: 600, textTransform: "uppercase" }}>Triage Level</span>
                      <span style={{ color: pd?.triageLevel === "Emergency" ? "#EF4444" : "#F59E0B", fontWeight: 700 }}>{pd?.triageLevel || "Standard"}</span>
                    </div>
                  </div>
                </div>

                {/* CLINICAL COMPLAINT */}
                <div style={{ backgroundColor: "#0F172A", border: "1px solid #334155", borderRadius: 10, padding: 14 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#64748B", textTransform: "uppercase", marginBottom: 6 }}>
                    Chief Complaint & Diagnosis
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#38BDF8", marginBottom: 6 }}>
                    {pd?.chiefComplaint || "No complaint reported."}
                  </div>
                  {pd?.diagnosis && (
                    <div style={{ fontSize: 12, color: "#94A3B8", backgroundColor: "#1E293B", padding: "6px 10px", borderRadius: 6 }}>
                      Diagnosis: <strong style={{ color: "#F1F5F9" }}>{pd.diagnosis}</strong>
                    </div>
                  )}
                </div>

                {/* ACTIVE SYMPTOMS */}
                {activeSymptoms.length > 0 && (
                  <div style={{ backgroundColor: "#0F172A", border: "1px solid #334155", borderRadius: 10, padding: 14 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#64748B", textTransform: "uppercase", marginBottom: 8 }}>
                      Presenting Symptoms
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {activeSymptoms.map(([key]) => (
                        <span key={key} style={{ fontSize: 11, backgroundColor: "#1E293B", color: "#F8FAFC", border: "1px solid #475569", padding: "3px 8px", borderRadius: 6, fontWeight: 600 }}>
                          {key.replace(/([A-Z])/g, " $1").trim()}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

              </div>
            )}

            {activeTab === "messages" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#64748B", textTransform: "uppercase", marginBottom: 4 }}>
                  Instructor Announcements & Feedback
                </div>
                {comments.length === 0 ? (
                  <div style={{ fontSize: 12, color: "#64748B", fontStyle: "italic", textAlign: "center", padding: "24px 0" }}>
                    No instructor messages received yet.
                  </div>
                ) : (
                  comments.map((c, i) => (
                    <div key={i} style={{ backgroundColor: "#0F172A", borderLeft: "3px solid #0D9488", border: "1px solid #334155", borderRadius: 8, padding: 10 }}>
                      <div style={{ fontSize: 10, color: "#64748B", marginBottom: 4, display: "flex", justifyContent: "space-between" }}>
                        <span>{c.from || "Instructor"}</span>
                        <span>{c.timestamp ? new Date(c.timestamp).toLocaleTimeString() : ""}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "#F8FAFC", fontWeight: 500 }}>
                        {c.comment}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
