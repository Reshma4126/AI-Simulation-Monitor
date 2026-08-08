import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import socket from "../socket";
import useMonitorStore from "../store/monitorStore";
import { connect, disconnect } from "../engine/wsClient";
import { useECGStore } from "../store/ecgStore";
import { getEngineRhythm } from "../utils/rhythms";
import "../styles/monitor.css";

import WaveformStack from "../components/monitor/WaveformStack";
import VitalsPanel from "../components/monitor/VitalsPanel";
import AlarmBar from "../components/monitor/AlarmBar";
import CommunicationPanel from "../components/instructor/CommunicationPanel";
import TrendsModal from "../components/instructor/TrendsModal";
import ScenarioDrawer from "../components/instructor/ScenarioDrawer";

import InstructorParameterModal from "../components/dialogs/InstructorParameterModal";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function InstructorDashboard() {
  const [sessionCode, setSessionCode] = useState("");
  const [paramSpec, setParamSpec] = useState(null);
  const [openDialog, setOpenDialog] = useState(null);
  const [toasts, setToasts] = useState([]);
  
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

  // Scenario state
  const [scenario, setScenario] = useState(null);
  const [scenariosList, setScenariosList] = useState([]);
  const [showScenarioModal, setShowScenarioModal] = useState(false); // list of scenarios
  const [showScenarioDrawer, setShowScenarioDrawer] = useState(false); // patient case details

  // Trends state
  const [showTrendsModal, setShowTrendsModal] = useState(false);

  // Monitor Lead
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

    // Create or get session
    const initSession = async () => {
      const res = await fetch(`${API}/session/create`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setSessionCode(data.session_code);
      sessionStorage.setItem("session_code", data.session_code);

      if (!socket.connected) socket.connect();
      socket.emit("join_session", { session_code: data.session_code, token });
      connect(); // Connect to simman-ecg engine
      sessionStartRef.current = Date.now();
    };

    initSession();

    const handleStateUpdate = (state) => {
      setFullState(state);
      useECGStore.getState().onState({
        heart_rate: state.HR ?? state.heartRate ?? 80,
        spo2: state.SpO2 ?? state.spo2 ?? 98,
        sys_bp: state.ABP_sys ?? state.sysBP ?? 120,
        dia_bp: state.ABP_dia ?? state.diaBP ?? 80,
        pap_sys: state.PAP_sys ?? state.papSys ?? 25,
        pap_dia: state.PAP_dia ?? state.papDia ?? 10,
        etco2: state.etCO2 ?? state.etco2 ?? 38,
        resp_rate: state.avRR ?? state.respRate ?? 12,
        rhythm: state.rhythm ?? state.ecgRhythm ?? "NSR",
        transfer_time: state.transfer_time ?? 0,
        transfer_fn: state.transfer_fn ?? "IMMEDIATE",
      });
    };
    const handleAlarmUpdate = (data) => {
      useMonitorStore.setState({ alarms: data.alarms });
      
      // Toast system logic
      if (data.alarms && data.alarms.length > 0) {
        data.alarms.forEach(alarm => {
          const id = Date.now() + Math.random();
          setToasts(prev => [...prev, { id, message: alarm.message, priority: alarm.priority }]);
          setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id));
          }, 4000); // Auto-dismiss after 4 seconds
        });
      }
    };
    
    const handleRhythmChange = (data) => {
      setFullState(data);
      if (data.rhythm || data.HR) {
        useECGStore.getState().onState({
          heart_rate: data.HR ?? 80,
          rhythm: data.rhythm ?? "NSR",
          spo2: 98, sys_bp: 120, dia_bp: 80, pap_sys: 25, pap_dia: 10, etco2: 38, resp_rate: 12,
          transfer_time: 0, transfer_fn: "IMMEDIATE"
        });
      }
    };
    const handleSessionEvent = (entry) => appendEvent(entry);
    const handleSessionEnded = () => setSessionEnded();
    const handleError = (data) => console.error("[SIO Error]", data.message);

    socket.on("state_update", handleStateUpdate);
    socket.on("alarm_update", handleAlarmUpdate);
    socket.on("rhythm_change", handleRhythmChange);
    socket.on("session_event", handleSessionEvent);
    socket.on("session_ended", handleSessionEnded);
    socket.on("error", handleError);

    return () => {
      socket.off("state_update", handleStateUpdate);
      socket.off("alarm_update", handleAlarmUpdate);
      socket.off("rhythm_change", handleRhythmChange);
      socket.off("session_event", handleSessionEvent);
      socket.off("session_ended", handleSessionEnded);
      socket.off("error", handleError);
      disconnect(); // Disconnect simman-ecg engine
    };
  }, [navigate, setFullState, appendEvent, setSessionEnded]);

  // Sync monitor store state to ECG engine websocket
  useEffect(() => {
    const store = useMonitorStore.getState();
    const engineStore = useECGStore.getState();
    const sendCommand = engineStore.sendCommand;
    if (sendCommand && store.HR !== undefined) {
      const update = {};
      const differs = (left, right) => Math.abs(Number(left) - Number(right)) >= 0.5;

      if (differs(engineStore.heartRate, store.HR)) update.heart_rate = store.HR;
      if (differs(engineStore.sysBP, store.ABP_sys)) update.sys_bp = store.ABP_sys;
      if (differs(engineStore.diaBP, store.ABP_dia)) update.dia_bp = store.ABP_dia;
      if (differs(engineStore.papSys, store.PAP_sys)) update.pap_sys = store.PAP_sys;
      if (differs(engineStore.papDia, store.PAP_dia)) update.pap_dia = store.PAP_dia;
      if (differs(engineStore.spo2, store.SpO2)) update.spo2 = store.SpO2;
      if (differs(engineStore.respRate, store.avRR)) update.resp_rate = store.avRR;
      if (differs(engineStore.etco2, store.etCO2)) update.etco2 = store.etCO2;

      const engineRhythm = getEngineRhythm(store.rhythm);
      if (engineStore.rhythm !== engineRhythm) update.rhythm = engineRhythm;

      if (Object.keys(update).length > 0) {
        update.transfer_time = engineStore.transferTime || 0;
        update.transfer_fn = engineStore.transferFn || "IMMEDIATE";
        sendCommand(update);
      }
    }
  }, [
    useMonitorStore((s) => s.HR),
    useMonitorStore((s) => s.ABP_sys),
    useMonitorStore((s) => s.ABP_dia),
    useMonitorStore((s) => s.PAP_sys),
    useMonitorStore((s) => s.PAP_dia),
    useMonitorStore((s) => s.SpO2),
    useMonitorStore((s) => s.avRR),
    useMonitorStore((s) => s.etCO2),
    useMonitorStore((s) => s.rhythm)
  ]);

  // Scenario socket listeners
  useEffect(() => {
    const handleScenarioSelected = (data) => setScenario(data);
    const handleScenariosList = (list) => {
      setScenariosList(list);
      setShowScenarioModal(true);
    };
    socket.on("scenario_selected", handleScenarioSelected);
    socket.on("scenarios_list", handleScenariosList);
    return () => {
      socket.off("scenario_selected", handleScenarioSelected);
      socket.off("scenarios_list", handleScenariosList);
    };
  }, []);

  const requestRandomScenario = () => socket.emit("request_random_scenario");
  const openScenarioList = () => socket.emit("list_scenarios");
  const selectScenario = (id) => {
    socket.emit("select_scenario", { scenario_id: id });
    setShowScenarioModal(false);
  };

  const [showEndConfirmModal, setShowEndConfirmModal] = useState(false);

  const handleConfirmEndSession = async () => {
    if (sessionCode) {
      const token = sessionStorage.getItem("token");
      try {
        await fetch(`${API}/session/${sessionCode}/end`, { 
          method: "POST", headers: { Authorization: `Bearer ${token}` } 
        });
      } catch (e) {
        console.error("Failed to end session", e);
      }
    }
    socket.disconnect();
    setShowEndConfirmModal(false);
    navigate("/completed");
  };

  const handleVitalClick = useCallback((key) => {
    setOpenDialog(key);
  }, []);

  return (
    <div className="instructor-dashboard redesign">
      
      {sessionEnded && (
        <div className="dialog-overlay" style={{ zIndex: 9999 }}>
          <div className="dialog-box" style={{ textAlign: "center", padding: 32 }}>
            <h2 style={{ color: "var(--alarm-red)", marginBottom: 16 }}>Session Ended</h2>
            <button className="btn-classic btn-ok" onClick={handleLogout}>Return to Login</button>
          </div>
        </div>
      )}

      {showEndConfirmModal && (
        <div style={{ position: "fixed", inset: 0, backgroundColor: "rgba(15, 23, 42, 0.6)", backdropFilter: "blur(4px)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ backgroundColor: "#FFFFFF", borderRadius: 16, padding: 28, maxWidth: 440, width: "100%", boxShadow: "0 20px 25px -5px rgba(0,0,0,0.2)", textAlign: "center" }}>
            <h2 style={{ color: "#0F172A", marginBottom: 8, fontSize: 20, fontWeight: 700 }}>End Simulation Session?</h2>
            <p style={{ color: "#475569", fontSize: 13, marginBottom: 24, lineHeight: 1.5 }}>
              Are you sure you want to end the active simulation? This will stop telemetry, save session data, and transfer control to the AI debrief generator.
            </p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button onClick={() => setShowEndConfirmModal(false)} style={{ padding: "10px 20px", borderRadius: 10, border: "1px solid #CBD5E1", backgroundColor: "#FFFFFF", color: "#475569", fontWeight: 600, fontSize: 13, cursor: "pointer" }}>
                Cancel
              </button>
              <button onClick={handleConfirmEndSession} style={{ padding: "10px 20px", borderRadius: 10, border: "none", backgroundColor: "#0F766E", color: "#FFFFFF", fontWeight: 600, fontSize: 13, cursor: "pointer", boxShadow: "0 2px 6px rgba(15, 118, 110, 0.2)" }}>
                Confirm & End Session →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Top bar */}
      <div className="instructor-topbar">
        <div className="topbar-left">
          <svg width="24" height="24" viewBox="0 0 48 48" fill="none">
            <rect x="2" y="2" width="44" height="44" rx="4" stroke="#00FF44" strokeWidth="2" fill="none" />
            <polyline points="8,28 14,28 17,16 20,36 23,24 26,30 29,22 32,28 38,28" stroke="#00FF44" strokeWidth="2" fill="none" />
          </svg>
          <span className="topbar-title">AI Simulation Monitor</span>
          <span className="topbar-role">INSTRUCTOR</span>
        </div>
        <div className="topbar-center">
          <button className="btn-classic btn-sm" onClick={() => setShowTrendsModal(true)}>📈 Trends</button>
          <button className="btn-classic btn-sm" onClick={() => setShowScenarioDrawer(true)}>📋 Case Details</button>
          <button className="btn-classic btn-sm" onClick={openScenarioList}>📄 Change Scenario</button>
          <button className="btn-classic btn-sm" onClick={() => setOpenDialog("toggles")}>⚙️ Display Toggles</button>
          <button className="btn-classic btn-sm" onClick={requestRandomScenario}>🎲 Random</button>
        </div>
        <div className="topbar-right">
          <span className="sim-timer-value" style={{marginRight: 10, color: '#00FF44'}}>{formatTime(elapsed)}</span>
          <span className="topbar-session">Session: <strong>{sessionCode}</strong></span>
          <button className="btn-classic btn-sm" onClick={() => setShowEndConfirmModal(true)} style={{marginLeft: 10}}>End Session</button>
        </div>
      </div>

      {/* Main Layout */}
      <div className="instructor-main-layout">

        {/* Middle: Monitor Area (Waveforms + Vitals) */}
        <div className="instructor-monitor-area">
          <AlarmBar />
          <div className="monitor-main student-monitor-style">
            <div className="student-vitals-left" style={{ cursor: 'pointer' }}>
              {/* Using VitalsPanel for familiar look, but clicking opens dialogs */}
              <VitalsPanel onVitalClick={handleVitalClick} compact={true} isStudent={false} />
            </div>
            <div className="student-waveforms-center waveform-container">
              <WaveformStack lead={selectedLead} onLeadSelect={setSelectedLead} />
            </div>
          </div>
        </div>

        {/* Bottom: Minimal Event Log Footer */}
        <CommunicationPanel sessionCode={sessionCode} />

      </div>

      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast-notification priority-${toast.priority || 'medium'}`}>
            {toast.message}
          </div>
        ))}
      </div>

      {/* Overlays / Modals */}
      
      {showTrendsModal && (
        <TrendsModal onClose={() => setShowTrendsModal(false)} sessionStartRef={sessionStartRef} />
      )}

      <ScenarioDrawer 
        isOpen={showScenarioDrawer} 
        onClose={() => setShowScenarioDrawer(false)} 
        scenario={scenario} 
      />

      {showScenarioModal && (
        <div className="dialog-overlay" style={{ zIndex: 10000 }}>
          <div className="scenario-modal">
            <div className="scenario-modal-header">
              <h2>Select Scenario</h2>
              <button className="btn-classic btn-sm" onClick={() => setShowScenarioModal(false)}>✕</button>
            </div>
            <div className="scenario-modal-list">
              {scenariosList.map((sc) => {
                const pd = typeof sc.patient_details === "string" ? JSON.parse(sc.patient_details) : sc.patient_details;
                return (
                  <div key={sc.id} className={`scenario-modal-item ${scenario?.id === sc.id ? "scenario-modal-item-active" : ""}`} onClick={() => selectScenario(sc.id)}>
                    <div className="scenario-modal-item-name">{sc.name}</div>
                    <div className="scenario-modal-item-meta">
                      {pd?.age} / {pd?.gender} — {pd?.diagnosis}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {openDialog && (
        <InstructorParameterModal
          field={openDialog}
          pendingMode={true}
          onApply={async (stagedValues) => {
            const mapped = {};
            if (stagedValues.HR !== undefined) mapped.HR = Number(stagedValues.HR);
            if (stagedValues.rhythm !== undefined) mapped.rhythm = stagedValues.rhythm;
            if (stagedValues.BP_sys !== undefined) mapped.ABP_sys = Number(stagedValues.BP_sys);
            if (stagedValues.BP_dia !== undefined) mapped.ABP_dia = Number(stagedValues.BP_dia);
            if (stagedValues.PAP_sys !== undefined) mapped.PAP_sys = Number(stagedValues.PAP_sys);
            if (stagedValues.PAP_dia !== undefined) mapped.PAP_dia = Number(stagedValues.PAP_dia);
            if (stagedValues.SpO2 !== undefined) mapped.SpO2 = Number(stagedValues.SpO2);
            if (stagedValues.RR !== undefined) mapped.avRR = Number(stagedValues.RR);
            if (stagedValues.etCO2 !== undefined) mapped.etCO2 = Number(stagedValues.etCO2);
            if (stagedValues.Tblood !== undefined) mapped.Tblood = Number(stagedValues.Tblood);
            
            if (stagedValues.NBP_sys !== undefined) mapped.NBP_sys = Number(stagedValues.NBP_sys);
            if (stagedValues.NBP_dia !== undefined) mapped.NBP_dia = Number(stagedValues.NBP_dia);
            if (stagedValues.nibp_interval !== undefined) mapped.nibp_interval = Number(stagedValues.nibp_interval);
            
            const toggles = ["show_ecg", "show_hr", "show_spo2", "show_pleth", "show_resp", "show_rr", "show_nibp", "show_map", "show_temp", "show_etco2"];
            for (const key of toggles) {
              if (stagedValues[key] !== undefined) mapped[key] = stagedValues[key];
            }
            
            return new Promise((resolve, reject) => {
              socket.emit("apply_all_settings", mapped, (response) => {
                if (response && response.status === "success") {
                  const engineUpdate = {};
                  if (stagedValues.HR !== undefined) engineUpdate.heart_rate = Number(stagedValues.HR);
                  if (stagedValues.SpO2 !== undefined) engineUpdate.spo2 = Number(stagedValues.SpO2);
                  if (stagedValues.BP_sys !== undefined) engineUpdate.sys_bp = Number(stagedValues.BP_sys);
                  if (stagedValues.BP_dia !== undefined) engineUpdate.dia_bp = Number(stagedValues.BP_dia);
                  if (stagedValues.PAP_sys !== undefined) engineUpdate.pap_sys = Number(stagedValues.PAP_sys);
                  if (stagedValues.PAP_dia !== undefined) engineUpdate.pap_dia = Number(stagedValues.PAP_dia);
                  if (stagedValues.RR !== undefined) engineUpdate.resp_rate = Number(stagedValues.RR);
                  if (stagedValues.etCO2 !== undefined) engineUpdate.etco2 = Number(stagedValues.etCO2);
                  if (stagedValues.rhythm !== undefined) engineUpdate.rhythm = getEngineRhythm(stagedValues.rhythm);
                  
                  if (stagedValues.stElev !== undefined) engineUpdate.st_elevation = stagedValues.stElev;
                  if (stagedValues.stDepr !== undefined) engineUpdate.st_depression = stagedValues.stDepr;
                  if (stagedValues.artifactLevel !== undefined) engineUpdate.artifact_level = stagedValues.artifactLevel;
                  if (stagedValues.artifactType !== undefined) engineUpdate.artifact_type = stagedValues.artifactType;
                  if (stagedValues.transferTime !== undefined) engineUpdate.transfer_time = stagedValues.transferTime;
                  if (stagedValues.transferFn !== undefined) engineUpdate.transfer_fn = stagedValues.transferFn;
                  
                  if (Object.keys(engineUpdate).length > 0) {
                    useECGStore.getState().sendCommand(engineUpdate);
                  }
                  resolve(response);
                } else {
                  reject(new Error("Failed to apply settings"));
                }
              });
              
              setTimeout(() => {
                resolve({ status: "success" });
              }, 1500);
            });
          }}
          onClose={() => setOpenDialog(null)}
        />
      )}
      
    </div>
  );
}
