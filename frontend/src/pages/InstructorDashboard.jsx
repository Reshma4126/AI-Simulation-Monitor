import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import socket from "../socket";
import useMonitorStore from "../store/monitorStore";
import { connect, disconnect } from "../engine/wsClient";
import "../styles/monitor.css";

import WaveformStack from "../components/monitor/WaveformStack";
import VitalsPanel from "../components/monitor/VitalsPanel";
import AlarmBar from "../components/monitor/AlarmBar";
import CommunicationPanel from "../components/instructor/CommunicationPanel";
import TrendsModal from "../components/instructor/TrendsModal";
import InstructorParameterModal from "../components/dialogs/InstructorParameterModal";
import LeaderboardModal from "../components/dialogs/LeaderboardModal";

import {
  Activity,
  Award,
  CheckCircle2,
  Clock,
  FileText,
  Sliders,
  AlertTriangle,
  Send,
  Zap,
  Users,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  XCircle,
  ChevronRight,
  ChevronLeft
} from "lucide-react";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function InstructorDashboard() {
  const [sessionCode, setSessionCode] = useState("");
  const [paramSpec, setParamSpec] = useState(null);
  const [openDialog, setOpenDialog] = useState(null);
  
  // Right panel collapsible state
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  
  const setFullState = useMonitorStore((s) => s.setFullState);
  const appendEvent = useMonitorStore((s) => s.appendEvent);
  const setSessionEnded = useMonitorStore((s) => s.setSessionEnded);
  const sessionEnded = useMonitorStore((s) => s.sessionEnded);
  const navigate = useNavigate();
  
  // Timer for top bar
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

  // Scenario state & conditions
  const [scenario, setScenario] = useState(null);
  const [checklist, setChecklist] = useState([]);
  const [activeConditionId, setActiveConditionId] = useState("initial");
  
  // Control Panel Active Tab: 'scenario' | 'conditions' | 'checklist' | 'interventions' | 'communication'
  const [activeTab, setActiveTab] = useState("conditions");

  // End Confirm Modal
  const [showEndConfirmModal, setShowEndConfirmModal] = useState(false);
  const [showTrendsModal, setShowTrendsModal] = useState(false);
  const [showLeaderboardModal, setShowLeaderboardModal] = useState(false);
  const [selectedLead, setSelectedLead] = useState("II");

  useEffect(() => {
    const token = sessionStorage.getItem("token");
    const role = sessionStorage.getItem("role");
    if (!token || role !== "instructor") {
      navigate("/");
      return;
    }

    // Fetch parameter spec once
    fetch(`${API}/meta/parameter-spec`)
      .then((r) => r.json())
      .then(setParamSpec)
      .catch(console.error);

    // Get active session code
    const code = sessionStorage.getItem("session_code");
    if (code) {
      setSessionCode(code);
      if (!socket.connected) socket.connect();
      socket.emit("join_session", { session_code: code, token });
      connect(); // Receive waveform engine telemetry
      sessionStartRef.current = Date.now();
    } else {
      navigate("/cases");
      return;
    }

    const handleStateUpdate = (state) => setFullState(state);
    const handleAlarmUpdate = (data) => {
      useMonitorStore.setState({ alarms: data.alarms });
    };
    
    const handleRhythmChange = (data) => setFullState(data);
    const handleSessionEvent = (entry) => appendEvent(entry);
    const handleSessionEnded = () => setSessionEnded();
    const handleScenarioSelected = (specData) => {
      setScenario(specData);
      if (specData.checklist) setChecklist(specData.checklist);
      if (specData.conditions && specData.conditions.length > 0) {
        setActiveConditionId(specData.conditions[0].id);
      }
    };
    const handleChecklistUpdated = (data) => {
      if (data && data.checklist) setChecklist(data.checklist);
    };
    const handleConditionChanged = (data) => {
      if (data && data.condition_id) setActiveConditionId(data.condition_id);
    };
    const handleError = (data) => console.error("[SIO Error]", data.message);

    socket.on("state_update", handleStateUpdate);
    socket.on("alarm_update", handleAlarmUpdate);
    socket.on("rhythm_change", handleRhythmChange);
    socket.on("session_event", handleSessionEvent);
    socket.on("session_ended", handleSessionEnded);
    socket.on("scenario_selected", handleScenarioSelected);
    socket.on("checklist_updated", handleChecklistUpdated);
    socket.on("condition_changed", handleConditionChanged);
    socket.on("error", handleError);

    return () => {
      socket.off("state_update", handleStateUpdate);
      socket.off("alarm_update", handleAlarmUpdate);
      socket.off("rhythm_change", handleRhythmChange);
      socket.off("session_event", handleSessionEvent);
      socket.off("session_ended", handleSessionEnded);
      socket.off("scenario_selected", handleScenarioSelected);
      socket.off("checklist_updated", handleChecklistUpdated);
      socket.off("condition_changed", handleConditionChanged);
      socket.off("error", handleError);
      disconnect();
    };
  }, [navigate, setFullState, appendEvent, setSessionEnded]);

  const handleConfirmEndSession = async () => {
    if (sessionCode) {
      const token = sessionStorage.getItem("token");
      try {
        await fetch(`${API}/session/${sessionCode}/end`, {
          method: "POST", headers: { Authorization: `Bearer ${token}` }
        });
      } catch (e) {
        console.error("Failed to end session on logout", e);
      }
    }
    sessionStorage.clear();
    socket.disconnect();
    setShowEndConfirmModal(false);
    navigate("/debrief/" + sessionCode);
  };

  const handleVitalClick = useCallback((key) => {
    setOpenDialog(key);
  }, []);

  const handleApplyCondition = (cond) => {
    setActiveConditionId(cond.id);
    socket.emit("apply_condition", {
      condition_id: cond.id,
      condition_name: cond.name,
      state: cond.state
    });
  };

  const handleMarkChecklistDone = (itemId) => {
    setChecklist(prev => prev.map(item => {
      if (item.id === itemId || item.action === itemId || String(item.id) === String(itemId)) {
        return { ...item, status: "completed" };
      }
      return item;
    }));
    socket.emit("mark_checklist_done", { session_code: sessionCode, item_id: itemId });
  };

  const completedChecklistCount = checklist.filter(c => c.status === "completed" || c.status === "completed_late").length;
  const checklistPct = checklist.length > 0 ? Math.round((completedChecklistCount / checklist.length) * 100) : 0;

  const currentConditionObj = scenario?.conditions?.find(c => c.id === activeConditionId);

  return (
    <div className="instructor-dashboard redesign" style={{ display: "flex", flexDirection: "column", height: "100vh", backgroundColor: "#0F172A", color: "#F8FAFC", fontFamily: "Inter, sans-serif" }}>
      

      {/* Session Ended Modal */}
      {sessionEnded && (
        <div className="dialog-overlay" style={{ zIndex: 9999, backgroundColor: "rgba(0,0,0,0.8)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="dialog-box" style={{ textAlign: "center", padding: 32, backgroundColor: "#1E293B", borderRadius: 16, border: "1px solid #334155" }}>
            <h2 style={{ color: "#EF4444", marginBottom: 16, fontSize: 22, fontWeight: 700 }}>Simulation Session Ended</h2>
            <p style={{ color: "#94A3B8", marginBottom: 24 }}>The instructor has finalized this simulation run.</p>
            <button className="btn-classic btn-ok" onClick={() => navigate("/debrief/" + sessionCode)} style={{ backgroundColor: "#10B981", color: "#FFF", padding: "10px 24px", borderRadius: 8, border: "none", cursor: "pointer" }}>Go to AI Debrief →</button>
          </div>
        </div>
      )}

      {/* End Confirm Modal */}
      {showEndConfirmModal && (
        <div className="dialog-overlay" style={{ zIndex: 10000, backgroundColor: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="dialog-box" style={{ textAlign: "center", padding: 28, maxWidth: 440, width: "100%", backgroundColor: "#1E293B", borderRadius: 16, border: "1px solid #334155" }}>
            <h2 style={{ color: "#F8FAFC", marginBottom: 8, fontSize: 20, fontWeight: 700 }}>End Simulation Session?</h2>
            <p style={{ color: "#94A3B8", fontSize: 13, marginBottom: 24, lineHeight: 1.5 }}>
              Are you sure you want to end active simulation session <strong>{sessionCode}</strong>? Control will be transferred to the AI debrief generator.
            </p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button onClick={() => setShowEndConfirmModal(false)} style={{ backgroundColor: "#334155", color: "#F8FAFC", padding: "8px 20px", borderRadius: 8, border: "none", cursor: "pointer" }}>
                Cancel
              </button>
              <button onClick={handleConfirmEndSession} style={{ backgroundColor: "#EF4444", color: "#F8FAFC", padding: "8px 20px", borderRadius: 8, border: "none", cursor: "pointer", fontWeight: 600 }}>
                Confirm & End Session →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TOP HEADER BAR */}
      <div style={{ height: 56, backgroundColor: "#1E293B", borderBottom: "1px solid #334155", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: "#10B98120", border: "1px solid #10B981", display: "flex", alignItems: "center", justifyContent: "center", color: "#10B981" }}>
            <Activity size={18} />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#F8FAFC", display: "flex", alignItems: "center", gap: 8 }}>
              {scenario?.title || "ACLS Cardiac Arrest Simulation"}
              <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 12, backgroundColor: "#3B82F620", color: "#60A5FA", border: "1px solid #3B82F640", textTransform: "uppercase" }}>
                {scenario?.level || "Intermediate"}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "#94A3B8", display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: "#10B981" }}></span>
              Instructor Connected • {scenario?.location_label || "Emergency Room"}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, color: "#94A3B8" }}>SESSION CODE</div>
            <div style={{ fontSize: 16, fontWeight: 800, color: "#10B981", letterSpacing: 1 }}>{sessionCode}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, color: "#94A3B8" }}>ELAPSED TIME</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#F8FAFC", fontFamily: "monospace" }}>{formatTime(elapsed)}</div>
          </div>
          <button onClick={() => setShowLeaderboardModal(true)} style={{ backgroundColor: "#334155", color: "#F8FAFC", border: "1px solid #475569", padding: "6px 14px", borderRadius: 8, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <Award size={14} color="#F59E0B" /> Leaderboard
          </button>
          <button onClick={() => setShowTrendsModal(true)} style={{ backgroundColor: "#334155", color: "#F8FAFC", border: "1px solid #475569", padding: "6px 14px", borderRadius: 8, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <TrendingUp size={14} color="#60A5FA" /> Trends
          </button>
          <button onClick={() => setShowEndConfirmModal(true)} style={{ backgroundColor: "#EF4444", color: "#F8FAFC", border: "none", padding: "7px 16px", borderRadius: 8, cursor: "pointer", fontSize: 12, fontWeight: 700 }}>
            End Session
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
          <VitalsPanel onVitalClick={handleVitalClick} compact={true} isStudent={false} />
        </div>

        {/* COLUMN 2: CENTER WAVEFORMS & ALARMS */}
        <div style={{ backgroundColor: "#000000", display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
          
          {/* Collapsible Control Panel Toggle Arrow */}
          <button
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
            title={rightPanelOpen ? "Collapse Right Control Panel" : "Expand Right Control Panel"}
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

        {/* COLUMN 3: RIGHT INSTRUCTOR CONTROL PANEL */}
        <div style={{ backgroundColor: "#1E293B", borderLeft: rightPanelOpen ? "1px solid #334155" : "none", display: rightPanelOpen ? "flex" : "none", flexDirection: "column", overflow: "hidden" }}>
          
          {/* TAB HEADERS */}
          <div style={{ display: "flex", borderBottom: "1px solid #334155", backgroundColor: "#0F172A" }}>
            {[
              { id: "conditions", label: "Conditions", icon: Zap },
              { id: "checklist", label: `Checklist`, icon: CheckCircle2 },
              { id: "scenario", label: "Patient", icon: FileText },
              { id: "interventions", label: "Manual", icon: Sliders },
              { id: "communication", label: "Log", icon: Users }
            ].map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    flex: 1,
                    padding: "8px 2px",
                    backgroundColor: isActive ? "#1E293B" : "transparent",
                    color: isActive ? "#10B981" : "#94A3B8",
                    border: "none",
                    borderBottom: isActive ? "2px solid #10B981" : "none",
                    cursor: "pointer",
                    fontSize: 11,
                    fontWeight: isActive ? 700 : 500,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 3
                  }}
                >
                  <Icon size={14} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* TAB CONTENT AREA */}
          <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
            
            {/* 1. CONDITIONS TAB */}
            {activeTab === "conditions" && (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 11, color: "#94A3B8", textTransform: "uppercase", fontWeight: 600 }}>Active Condition</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: "#10B981", marginTop: 2 }}>
                    {currentConditionObj?.name || "Initial Presentation"}
                  </div>
                  {currentConditionObj?.description && (
                    <div style={{ fontSize: 12, color: "#CBD5E1", marginTop: 4, backgroundColor: "#0F172A", padding: 8, borderRadius: 6, border: "1px solid #334155" }}>
                      {currentConditionObj.description}
                    </div>
                  )}
                </div>

                <div style={{ fontSize: 12, fontWeight: 700, color: "#F8FAFC", marginBottom: 10 }}>Scenario Progression States</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {(scenario?.conditions || [
                    { id: "initial", name: "Initial Presentation", description: "Baseline presentation" },
                    { id: "deteriorating", name: "Deterioration", description: "Vitals dropping" },
                    { id: "arrest_vf", name: "VF Cardiac Arrest", description: "Unresponsive, VF on ECG" },
                    { id: "post_shock", name: "Post-Shock CPR", description: "CPR in progress" },
                    { id: "rosc", name: "ROSC Achieved", description: "Pulse restored" }
                  ]).map((cond, idx) => {
                    const isActive = activeConditionId === cond.id;
                    return (
                      <div
                        key={cond.id || idx}
                        onClick={() => handleApplyCondition(cond)}
                        style={{
                          padding: "12px 14px",
                          borderRadius: 8,
                          backgroundColor: isActive ? "#10B98115" : "#0F172A",
                          border: isActive ? "1px solid #10B981" : "1px solid #334155",
                          cursor: "pointer",
                          transition: "all 0.15s ease"
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: isActive ? "#10B981" : "#F8FAFC" }}>
                            {idx + 1}. {cond.name}
                          </span>
                          {isActive && <span style={{ fontSize: 10, backgroundColor: "#10B981", color: "#FFF", padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>ACTIVE</span>}
                        </div>
                        {cond.description && (
                          <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>{cond.description}</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 2. CHECKLIST TAB */}
            {activeTab === "checklist" && (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 700, color: "#F8FAFC", marginBottom: 6 }}>
                    <span>Checklist Progress</span>
                    <span>{completedChecklistCount} / {checklist.length} ({checklistPct}%)</span>
                  </div>
                  <div style={{ width: "100%", height: 8, backgroundColor: "#0F172A", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ width: `${checklistPct}%`, height: "100%", backgroundColor: "#10B981", transition: "width 0.3s ease" }}></div>
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {checklist.map((item, idx) => {
                    const isDone = item.status === "completed" || item.status === "completed_late";
                    const isLate = item.status === "completed_late";
                    return (
                      <div
                        key={item.id || idx}
                        style={{
                          padding: "10px 12px",
                          borderRadius: 8,
                          backgroundColor: "#0F172A",
                          border: isDone ? "1px solid #10B98150" : "1px solid #334155",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between"
                        }}
                      >
                        <div style={{ flex: 1, paddingRight: 10 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: isDone ? "#94A3B8" : "#F8FAFC", textDecoration: isDone ? "line-through" : "none" }}>
                            {item.action}
                          </div>
                          <div style={{ fontSize: 10, color: "#64748B", marginTop: 2, display: "flex", gap: 8 }}>
                            <span>Target: {item.window_sec}s</span>
                            {item.critical && <span style={{ color: "#EF4444", fontWeight: 700 }}>CRITICAL</span>}
                            {isLate && <span style={{ color: "#F59E0B" }}>Late (+{item.delay_seconds}s)</span>}
                          </div>
                        </div>

                        {!isDone ? (
                          <button
                            onClick={() => handleMarkChecklistDone(item.id || item.action)}
                            style={{ backgroundColor: "#10B981", color: "#FFF", border: "none", padding: "5px 10px", borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                          >
                            Mark Done
                          </button>
                        ) : (
                          <CheckCircle2 size={18} color="#10B981" />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 3. PATIENT CASE DETAILS TAB */}
            {activeTab === "scenario" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ backgroundColor: "#0F172A", padding: 12, borderRadius: 8, border: "1px solid #334155" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#10B981", textTransform: "uppercase", marginBottom: 6 }}>Patient Profile</div>
                  <div style={{ fontSize: 13, color: "#F8FAFC", fontWeight: 600 }}>
                    {scenario?.patient?.age || 52}-year-old {scenario?.patient?.sex || "Male"} ({scenario?.patient?.weight_kg || 78} kg)
                  </div>
                  <div style={{ fontSize: 12, color: "#CBD5E1", marginTop: 4 }}>
                    <strong>Presentation:</strong> {scenario?.patient?.presentation || "Sudden collapse in ED."}
                  </div>
                  <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 4 }}>
                    <strong>History:</strong> {scenario?.patient?.history || "Known IHD, Hypertension."}
                  </div>
                </div>

                <div style={{ backgroundColor: "#0F172A", padding: 12, borderRadius: 8, border: "1px solid #334155" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#60A5FA", textTransform: "uppercase", marginBottom: 6 }}>Available Resources</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 11, color: "#CBD5E1" }}>
                    <div>🚨 Crash Cart: {scenario?.resources?.crash_cart ? "Available" : "No"}</div>
                    <div>⚡ Defibrillator: {scenario?.resources?.defibrillator ? "Available" : "No"}</div>
                    <div>🫁 Ventilator: {scenario?.resources?.ventilator ? "Available" : "No"}</div>
                    <div>💉 IV Access: {scenario?.resources?.iv_access_ready ? "Ready" : "Not set"}</div>
                  </div>
                </div>
              </div>
            )}

            {/* 4. MANUAL INTERVENTIONS TAB */}
            {activeTab === "interventions" && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#F8FAFC", marginBottom: 10 }}>Direct Vital Parameter Override</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {[
                    { key: "HR", label: "HR / Rhythm" },
                    { key: "abp", label: "Blood Pressure" },
                    { key: "SpO2", label: "SpO2 / Pleth" },
                    { key: "avRR", label: "Resp Rate" },
                    { key: "etCO2", label: "EtCO2" },
                    { key: "Tblood", label: "Temperature" },
                    { key: "toggles", label: "Display Toggles" }
                  ].map(item => (
                    <button
                      key={item.key}
                      onClick={() => setOpenDialog(item.key)}
                      style={{ backgroundColor: "#0F172A", border: "1px solid #334155", color: "#F8FAFC", padding: "10px", borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: "pointer", textAlign: "center" }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 5. COMMUNICATION & EVENT LOG TAB */}
            {activeTab === "communication" && (
              <CommunicationPanel />
            )}

          </div>
        </div>

      </div>

      {/* PARAMETER OVERRIDE MODAL */}
      {openDialog && (
        <InstructorParameterModal
          field={openDialog}
          paramSpec={paramSpec}
          onClose={() => setOpenDialog(null)}
          onApply={async (stagedValues) => {
            const token = sessionStorage.getItem("token");
            if (stagedValues.rhythm !== undefined || stagedValues.HR !== undefined) {
              const rhythmData = {
                rhythm: stagedValues.rhythm || useMonitorStore.getState().rhythm,
                HR: Number(stagedValues.HR ?? useMonitorStore.getState().HR),
                extrasystole: stagedValues.extrasystole || "None",
                ecg_lead: selectedLead
              };
              socket.emit("update_rhythm", rhythmData);
            }
            if (stagedValues.BP_sys !== undefined) {
              socket.emit("update_parameter", { field: "ABP_sys", value: Number(stagedValues.BP_sys) });
            }
            if (stagedValues.BP_dia !== undefined) {
              socket.emit("update_parameter", { field: "ABP_dia", value: Number(stagedValues.BP_dia) });
            }
            if (stagedValues.SpO2 !== undefined) {
              socket.emit("update_parameter", { field: "SpO2", value: Number(stagedValues.SpO2) });
            }
            if (stagedValues.RR !== undefined) {
              socket.emit("update_parameter", { field: "avRR", value: Number(stagedValues.RR) });
            }
            if (stagedValues.etCO2 !== undefined) {
              socket.emit("update_parameter", { field: "etCO2", value: Number(stagedValues.etCO2) });
            }
            setOpenDialog(null);
          }}
        />
      )}

      {/* TRENDS MODAL */}
      {showTrendsModal && (
        <TrendsModal sessionCode={sessionCode} onClose={() => setShowTrendsModal(false)} />
      )}

      {/* LEADERBOARD MODAL */}
      <LeaderboardModal isOpen={showLeaderboardModal} onClose={() => setShowLeaderboardModal(false)} />

    </div>
  );
}
