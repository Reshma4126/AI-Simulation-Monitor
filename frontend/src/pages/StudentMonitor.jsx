import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import socket from "../socket";
import useMonitorStore from "../store/monitorStore";
import { connect, disconnect } from "../engine/wsClient";
import AlarmBar from "../components/monitor/AlarmBar";
import EyesPanel from "../components/monitor/EyesPanel";
import MonitorParameters from "../components/monitor/MonitorParameters";
import WaveformStack from "../components/monitor/WaveformStack";
import audioEngine from "../engine/audioEngine";

// InlineReadings displays vitals horizontally above the canvas (retained as unused helper or clean up)
function InlineReadings() {
  const state = useMonitorStore();
  
  const hr = state.HR;
  const spo2 = state.SpO2;
  const abpSys = state.ABP_sys;
  const abpDia = state.ABP_dia;
  const papSys = state.PAP_sys;
  const papDia = state.PAP_dia;
  const etco2 = state.etCO2;
  const rr = state.avRR;
  const tperi = state.Tperi;
  const tblood = state.Tblood;
  const co = state.CO;

  const abpDisp = abpSys != null && abpDia != null ? `${Math.round(abpSys)}/${Math.round(abpDia)}` : "--";
  const papDisp = papSys != null && papDia != null ? `${Math.round(papSys)}/${Math.round(papDia)}` : "--";

  return (
    <div className="student-inline-readings">
      <div className="inline-reading-box" style={{ borderColor: "#00FF00" }}>
        <span className="inline-label" style={{ color: "#00FF00" }}>HR</span>
        <span className="inline-value" style={{ color: "#00FF00" }}>{hr ?? "--"}</span>
        <span className="inline-unit">bpm</span>
      </div>
      <div className="inline-reading-box" style={{ borderColor: "#FFFF00" }}>
        <span className="inline-label" style={{ color: "#FFFF00" }}>SpO₂</span>
        <span className="inline-value" style={{ color: "#FFFF00" }}>{spo2 ?? "--"}</span>
        <span className="inline-unit">%</span>
      </div>
      <div className="inline-reading-box" style={{ borderColor: "#FF3333" }}>
        <span className="inline-label" style={{ color: "#FF3333" }}>ABP</span>
        <span className="inline-value" style={{ color: "#FF3333" }}>{abpDisp}</span>
        <span className="inline-unit">mmHg</span>
      </div>
      <div className="inline-reading-box" style={{ borderColor: "#FF9900" }}>
        <span className="inline-label" style={{ color: "#FF9900" }}>PAP</span>
        <span className="inline-value" style={{ color: "#FF9900" }}>{papDisp}</span>
        <span className="inline-unit">mmHg</span>
      </div>
      <div className="inline-reading-box" style={{ borderColor: "#00CCFF" }}>
        <span className="inline-label" style={{ color: "#00CCFF" }}>CO₂/RR</span>
        <span className="inline-value" style={{ color: "#00CCFF" }}>{etco2 ?? "--"}/{rr ?? "--"}</span>
        <span className="inline-unit">mmHg</span>
      </div>
      <div className="inline-reading-box" style={{ borderColor: "#CC99FF" }}>
        <span className="inline-label" style={{ color: "#CC99FF" }}>Temp</span>
        <span className="inline-value" style={{ color: "#CC99FF" }}>
          {tperi != null ? tperi.toFixed(1) : "--"} / {tblood != null ? tblood.toFixed(1) : "--"}
        </span>
        <span className="inline-unit">°C</span>
      </div>
      <div className="inline-reading-box" style={{ borderColor: "#FF66CC" }}>
        <span className="inline-label" style={{ color: "#FF66CC" }}>CO</span>
        <span className="inline-value" style={{ color: "#FF66CC" }}>{co ?? "--"}</span>
        <span className="inline-unit">L/min</span>
      </div>
    </div>
  );
}

export default function StudentMonitor() {
  const { sessionCode } = useParams();
  const setFullState = useMonitorStore((s) => s.setFullState);
  const [comments, setComments] = useState([]);
  const [joinStatus, setJoinStatus] = useState("joining"); // "joining" | "joined" | "error"
  const [joinError, setJoinError] = useState("");
  const [scenario, setScenario] = useState(null);
  const [alarmMuted, setAlarmMuted] = useState(false);
  const [nibpRunning, setNibpRunning] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [audioEnabled, setAudioEnabled] = useState(false);

  const alarms = useMonitorStore((s) => s.alarms) || [];

  // Audio System Alarms hook
  useEffect(() => {
    if (alarmMuted) {
      audioEngine.setCritical(false);
      audioEngine.setWarning(false);
      return;
    }

    const safeAlarms = Array.isArray(alarms) ? alarms : [];
    const hasCritical = safeAlarms.some(a => a?.severity === 'critical' || a?.level === 'critical' || a?.message?.toLowerCase().includes('critical') || a?.message?.toLowerCase().includes('arrest') || a?.message?.toLowerCase().includes('fib'));
    const hasWarning = safeAlarms.length > 0 && !hasCritical;

    audioEngine.setCritical(hasCritical);
    audioEngine.setWarning(hasWarning);
  }, [alarms, alarmMuted]);

  useEffect(() => {
    const token = sessionStorage.getItem("token");
    if (!token) {
      console.warn("[StudentMonitor] No token — redirecting to login");
      window.location.href = "/";
      return;
    }

    // Store session_code for socket auto-rejoin on reconnect
    sessionStorage.setItem("session_code", sessionCode);

    const doJoin = () => {
      console.log("[StudentMonitor] Emitting join_session for:", sessionCode);
      socket.emit("join_session", { session_code: sessionCode, token });
    };

    if (!socket.connected) {
      socket.connect();
      // Wait for connect then join
      socket.once("connect", doJoin);
    } else {
      doJoin();
    }
    
    connect(); // Connect to simman-ecg engine

    // ── Event handlers ──────────────────────────────────────
    const handleJoinConfirmed = (data) => {
      console.log("[StudentMonitor] join_confirmed:", data);
      setJoinStatus("joined");
    };

    const handleError = (data) => {
      console.error("[StudentMonitor] Socket error:", data.message);
      // If session not found or ended, redirect to login
      if (
        data.message?.includes("not found") ||
        data.message?.includes("has ended") ||
        data.message?.includes("Invalid token")
      ) {
        setJoinStatus("error");
        setJoinError(data.message);
        setTimeout(() => {
          sessionStorage.clear();
          window.location.href = "/";
        }, 2000);
      }
    };

    const handleSessionEnded = () => {
      console.log("[StudentMonitor] session_ended — redirecting to login");
      setJoinStatus("error");
      setJoinError("Session has ended by the instructor.");
      setTimeout(() => {
        sessionStorage.clear();
        socket.disconnect();
        window.location.href = "/";
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
  }, [sessionCode, setFullState]);

  // Show redirect/error overlay
  if (joinStatus === "error") {
    return (
      <div style={{
        position: "fixed", inset: 0, background: "#0a0a0a",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        color: "white", fontFamily: "Inter, sans-serif", gap: 12
      }}>
        <div style={{ fontSize: 48 }}>⚠️</div>
        <div style={{ fontSize: 18, color: "#ff4444" }}>{joinError || "Session error"}</div>
        <div style={{ fontSize: 13, color: "#888" }}>Redirecting to login...</div>
      </div>
    );
  }

  const handleAlarmSilence = () => {
    audioEngine.init();
    if (!alarmMuted) {
      setAlarmMuted(true);
      audioEngine.muteAlarms(true);
      // 2 minute silence
      setTimeout(() => {
        setAlarmMuted(false);
        audioEngine.muteAlarms(false);
      }, 120000);
    } else {
      setAlarmMuted(false);
      audioEngine.muteAlarms(false);
    }
  };

  const handleMonitorClick = () => {
    if (!audioEnabled) {
      audioEngine.init();
      setAudioEnabled(true);
    }
  };

  const handleNIBPToggle = () => {
    if (!audioEnabled) {
      audioEngine.init();
      setAudioEnabled(true);
    }
    setNibpRunning(!nibpRunning);
  };

  return (
    <div className="student-monitor-layout" onClick={handleMonitorClick}>
      {!audioEnabled && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.8)', zIndex: 9999,
          display: 'flex', justifyContent: 'center', alignItems: 'center',
          flexDirection: 'column', color: '#00ccff', cursor: 'pointer'
        }}>
          <h1 style={{fontSize: '48px', marginBottom: '20px'}}>Click Anywhere to Start Monitor</h1>
          <p style={{fontSize: '24px'}}>Audio is disabled until interaction</p>
        </div>
      )}
      {/* Top Status Bar */}
      <div className="monitor-top-bar">
        <div>
          Adult
        </div>
        <div>
          {new Date().toLocaleDateString('en-US', { month: 'numeric', day: 'numeric', year: 'numeric'})} {new Date().toLocaleTimeString('en-US', {hour: '2-digit', minute:'2-digit'})}
        </div>
        <div>
          5wave
        </div>
      </div>
      
      {/* Alarm Bar (Absolute or integrated into top) */}
      <div style={{ position: 'relative', width: '100%', zIndex: 10 }}>
         <AlarmBar />
      </div>

      <div className="monitor-main-content">
        {/* Left: waveforms */}
        <div className="monitor-waveforms-section">
          <WaveformStack lead="II" />
        </div>

        {/* Right: parameters */}
        <div className="monitor-parameters-section">
          <MonitorParameters />
        </div>
      </div>

      {/* Bottom Control Bar */}
      <div className="monitor-bottom-bar">
        <button className={`monitor-btn ${alarmMuted ? 'active' : ''}`} onClick={handleAlarmSilence}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
             <path d="M11 5L6 9H2v6h4l5 4V5z"></path>
             {alarmMuted ? <line x1="23" y1="9" x2="17" y2="15"></line> : <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>}
             {alarmMuted && <line x1="17" y1="9" x2="23" y2="15"></line>}
          </svg>
          {alarmMuted ? "Alarm Muted" : "Silence Alarm"}
        </button>
        <button className="monitor-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          Start Stop
        </button>
        <button className={`monitor-btn ${nibpRunning ? 'active' : ''}`} onClick={handleNIBPToggle}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
          {nibpRunning ? "NBP Running..." : "NBP Start/Stop"}
        </button>
        <button className="monitor-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"></path>
            <path d="M2 12h20"></path>
          </svg>
          Zero Press
        </button>
        <button className="monitor-btn">
           Cardiac Output
        </button>
        <button className="monitor-btn">
           Wedge
        </button>
        <button className="monitor-btn">
           TOF
        </button>
        <button className="monitor-btn">
           Graph Trends
        </button>
        <button className="monitor-btn" onClick={() => { audioEngine.init(); setChatOpen(!chatOpen); }}>
           Messages {comments.length > 0 && `(${comments.length})`}
        </button>
        <button className="monitor-btn" style={{backgroundColor: '#0000FF', color: 'white'}} onClick={() => audioEngine.init()}>
           Main Screen
        </button>
      </div>

      <EyesPanel editable={false} />

      {/* Faculty Comments Drawer */}
      <div style={{
        position: "fixed",
        top: 24, // below top bar
        right: chatOpen ? 0 : -320,
        width: 320,
        height: "calc(100vh - 24px - 48px)", // above bottom bar
        backgroundColor: "#1f1f1f",
        color: "white",
        padding: "12px 14px",
        borderLeft: "2px solid #333",
        boxShadow: "-4px 0 16px rgba(0,0,0,0.5)",
        zIndex: 1000,
        fontFamily: "Inter, sans-serif",
        transition: "right 0.3s ease",
        display: "flex",
        flexDirection: "column"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
          <h4 style={{ margin: 0, fontSize: "11px", textTransform: "uppercase", letterSpacing: "1.5px", color: "#00ccff" }}>
            📢 Instructor Messages
          </h4>
          <button onClick={() => setChatOpen(false)} style={{ background: "transparent", border: "none", color: "white", cursor: "pointer", fontSize: "16px" }}>✕</button>
        </div>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {comments.length === 0 && (
            <div style={{ fontSize: "12px", color: "#555", fontStyle: "italic" }}>No messages yet</div>
          )}
          {comments.map((c, i) => (
            <div key={i} style={{
              marginBottom: "8px",
              fontSize: "13px",
              background: "rgba(0,200,255,0.07)",
              borderLeft: "3px solid #00ccff",
              padding: "6px 8px",
              borderRadius: "4px",
            }}>
              <div style={{ color: "#aaa", fontSize: "10px", marginBottom: "2px" }}>
                {c.from || "Instructor"} · {c.timestamp ? new Date(c.timestamp).toLocaleTimeString() : ""}
              </div>
              <div>{c.comment}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
