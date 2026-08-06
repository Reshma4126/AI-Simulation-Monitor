import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import socket from "../socket";
import useMonitorStore from "../store/monitorStore";
import { connect, disconnect } from "../engine/wsClient";
import AlarmBar from "../components/monitor/AlarmBar";
import EyesPanel from "../components/monitor/EyesPanel";
import VitalsPanel from "../components/monitor/VitalsPanel";
import WaveformStack from "../components/monitor/WaveformStack";
import "../styles/monitor.css";

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

  // Helper to render patient details (no initial_readings for students)
  const renderScenarioCard = () => {
    if (!scenario) return null;
    const pd = typeof scenario.patient_details === "string"
      ? JSON.parse(scenario.patient_details)
      : scenario.patient_details;
    const symp = typeof scenario.symptoms === "string"
      ? JSON.parse(scenario.symptoms)
      : scenario.symptoms;

    const activeSymptoms = symp ? Object.entries(symp).filter(([, v]) => v === true) : [];

    return (
      <div className="student-scenario-card">
        <h4 className="student-scenario-title">📋 Case Scenario</h4>
        <div className="student-scenario-body">
          <div className="student-scenario-details">
            <div className="scenario-detail-row">
              <span className="scenario-detail-label">Patient</span>
              <span className="scenario-detail-value">{pd?.patientName}</span>
            </div>
            <div className="scenario-detail-row">
              <span className="scenario-detail-label">Age / Gender</span>
              <span className="scenario-detail-value">{pd?.age} / {pd?.gender}</span>
            </div>
            <div className="scenario-detail-row">
              <span className="scenario-detail-label">Blood Group</span>
              <span className="scenario-detail-value">{pd?.bloodGroup}</span>
            </div>
            <div className="scenario-detail-row">
              <span className="scenario-detail-label">Height / Weight</span>
              <span className="scenario-detail-value">{pd?.heightCm}cm / {pd?.weightKg}kg</span>
            </div>
            <div className="scenario-detail-row">
              <span className="scenario-detail-label">Complaint</span>
              <span className="scenario-detail-value">{pd?.chiefComplaint}</span>
            </div>
            <div className="scenario-detail-row">
              <span className="scenario-detail-label">Diagnosis</span>
              <span className="scenario-detail-value">{pd?.diagnosis}</span>
            </div>
            {pd?.medicalHistory && pd.medicalHistory.length > 0 && (
              <div className="scenario-detail-row">
                <span className="scenario-detail-label">History</span>
                <span className="scenario-detail-value">{pd.medicalHistory.join(", ")}</span>
              </div>
            )}
            <div className="scenario-detail-row">
              <span className="scenario-detail-label">Triage</span>
              <span className="scenario-detail-value" style={{
                color: pd?.triageLevel === "Emergency" ? "#ff4444" : "#ffaa00"
              }}>{pd?.triageLevel}</span>
            </div>
          </div>
          {activeSymptoms.length > 0 && (
            <div className="student-scenario-symptoms">
              <span className="scenario-detail-label" style={{ marginBottom: 4 }}>Symptoms</span>
              <div className="scenario-symptoms-list">
                {activeSymptoms.map(([key]) => (
                  <span key={key} className="scenario-symptom-tag">
                    {key.replace(/([A-Z])/g, " $1").trim()}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="student-monitor">
      <AlarmBar />
      <div className="monitor-main">
        {/* Left: readings values */}
        <div className="student-vitals-left">
          <VitalsPanel onVitalClick={null} compact={false} isStudent={true} />
        </div>

        {/* Center: waveforms */}
        <div className="student-waveforms-center waveform-container">
          <WaveformStack lead="II" />
        </div>

        {/* Right: scenario card */}
        <div className="student-monitor-right">
          {renderScenarioCard()}
        </div>
      </div>
      <EyesPanel editable={false} />

      {/* Faculty Comments Box — bottom right */}
      <div style={{
        position: "fixed",
        bottom: 20,
        right: 20,
        width: 320,
        maxHeight: 240,
        overflowY: "auto",
        backgroundColor: "rgba(10,10,20,0.92)",
        color: "white",
        padding: "12px 14px",
        borderRadius: "10px",
        border: "1px solid rgba(0,200,255,0.25)",
        boxShadow: "0 4px 16px rgba(0,0,0,0.6)",
        zIndex: 1000,
        fontFamily: "Inter, sans-serif",
      }}>
        <h4 style={{
          margin: "0 0 10px 0", fontSize: "11px",
          textTransform: "uppercase", letterSpacing: "1.5px", color: "#00ccff"
        }}>
          📢 Instructor Messages
        </h4>
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
  );
}
