import { useState, useEffect } from "react";
import { useECGStore } from "../../store/ecgStore";
import useMonitorStore from "../../store/monitorStore";
import socket from "../../socket";
import { RHYTHM_INTELLIGENCE } from "../../types/ecgState";
import { ENGINE_RHYTHM_OPTIONS, getEngineRhythm, getMonitorRhythmLabel } from "../../utils/rhythms";

/**
 * InstructorParameterModal
 *
 * Props:
 *   field        — which parameter to show controls for
 *   onClose      — called when dialog should close (Cancel or ✕)
 *
 * Optional (pending-mode) props:
 *   pendingMode    — when true, suppress all live emits; only commit on Apply
 *   initialValues  — seed local state with previously-staged values (re-open continuity)
 *   onApply        — (stagedValues: object) => void  — called on Apply in pending mode
 */
export default function InstructorParameterModal({
  field,
  onClose,
  pendingMode = false,
  initialValues = {},
  onApply,
}) {
  // ── Monitor Store ──────────────────────────────────────────────────────────
  const rhythm = useMonitorStore((s) => s.rhythm);
  const updateParam = useMonitorStore((s) => s.updateParam);

  // ── ECG Store ──────────────────────────────────────────────────────────────
  const ecgState    = useECGStore((s) => s.ecgState);
  const heartRate   = useECGStore((s) => s.heartRate);
  const targetSpO2  = useECGStore((s) => s.spo2);
  const sysBP       = useECGStore((s) => s.sysBP);
  const diaBP       = useECGStore((s) => s.diaBP);
  const papSys      = useECGStore((s) => s.papSys);
  const papDia      = useECGStore((s) => s.papDia);
  const targetEtco2 = useECGStore((s) => s.etco2);
  const respRate    = useECGStore((s) => s.respRate);
  const transferTime = useECGStore((s) => s.transferTime);
  const transferFn  = useECGStore((s) => s.transferFn);
  const sendCommand = useECGStore((s) => s.sendCommand);
  const ecgRhythm   = useECGStore((s) => s.rhythm);

  // ── Local working state (always used; in live-mode mirrors store) ──────────
  const [localHR, setLocalHR]           = useState(() => initialValues.HR   ?? heartRate);
  const [localSpO2, setLocalSpO2]       = useState(() => initialValues.SpO2 ?? targetSpO2);
  const [localSysBP, setLocalSysBP]     = useState(() => initialValues.BP_sys ?? sysBP);
  const [localDiaBP, setLocalDiaBP]     = useState(() => initialValues.BP_dia ?? diaBP);
  const [localPapSys, setLocalPapSys]   = useState(() => initialValues.PAP_sys ?? papSys);
  const [localPapDia, setLocalPapDia]   = useState(() => initialValues.PAP_dia ?? papDia);
  const [localEtco2, setLocalEtco2]     = useState(() => initialValues.etCO2 ?? targetEtco2);
  const [localRR, setLocalRR]           = useState(() => initialValues.RR    ?? respRate);
  const [localTblood, setLocalTblood]   = useState(() => initialValues.Tblood ?? useMonitorStore.getState().Tblood ?? 37.0);
  const [localRhythm, setLocalRhythm]   = useState(() => initialValues.rhythm ?? getEngineRhythm(rhythm || ecgRhythm));
  const [localTransferTime, setLocalTransferTime] = useState(transferTime);
  const [localTransferFn, setLocalTransferFn]     = useState(transferFn);

  const [stElev, setStElev]             = useState(0);
  const [stDepr, setStDepr]             = useState(0);
  const [artifactLevel, setArtifactLevel] = useState(0);
  const [artifactType, setArtifactType]   = useState("NONE");

  // NIBP state
  const [localNBPSys, setLocalNBPSys] = useState(() => useMonitorStore.getState().NBP_sys ?? 120);
  const [localNBPDia, setLocalNBPDia] = useState(() => useMonitorStore.getState().NBP_dia ?? 80);
  const [localNIBPInterval, setLocalNIBPInterval] = useState(() => useMonitorStore.getState().nibp_interval ?? 0);

  // Visibility toggles
  const [showEcg, setShowEcg] = useState(() => useMonitorStore.getState().show_ecg ?? true);
  const [showHr, setShowHr] = useState(() => useMonitorStore.getState().show_hr ?? true);
  const [showSpo2, setShowSpo2] = useState(() => useMonitorStore.getState().show_spo2 ?? true);
  const [showPleth, setShowPleth] = useState(() => useMonitorStore.getState().show_pleth ?? true);
  const [showResp, setShowResp] = useState(() => useMonitorStore.getState().show_resp ?? true);
  const [showRr, setShowRr] = useState(() => useMonitorStore.getState().show_rr ?? true);
  const [showNibp, setShowNibp] = useState(() => useMonitorStore.getState().show_nibp ?? true);
  const [showMap, setShowMap] = useState(() => useMonitorStore.getState().show_map ?? true);
  const [showTemp, setShowTemp] = useState(() => useMonitorStore.getState().show_temp ?? true);
  const [showEtco2, setShowEtco2] = useState(() => useMonitorStore.getState().show_etco2 ?? true);

  const [applying, setApplying] = useState(false);
  const [applyStatus, setApplyStatus] = useState(null);

  // Seed ST / artifact from ecgState once
  useEffect(() => {
    if (!ecgState) return;
    setStElev(ecgState.st_elevation ?? 0);
    setStDepr(ecgState.st_depression ?? 0);
    setArtifactLevel(ecgState.artifact_level ?? 0);
    setArtifactType(ecgState.artifact_type ?? "NONE");
  }, [ecgState]);

  // ── Rhythm profile for HR bounds ──────────────────────────────────────────
  const rhythmProfile = RHYTHM_INTELLIGENCE[localRhythm];
  const hrMin         = rhythmProfile?.hrMin ?? 0;
  const hrMax         = rhythmProfile?.hrMax ?? 300;
  const hrControlMax  = hrMax === 0 ? 1 : hrMax;

  // ── Helpers ───────────────────────────────────────────────────────────────
  const liveEmitMonitorParam = (f, value) => {
    if (pendingMode) return;
    updateParam(f, value);
    socket.emit("update_parameter", { field: f, value });
  };

  const liveSendVital = (update) => {
    if (pendingMode) return;
    sendCommand({ ...update, transfer_time: localTransferTime, transfer_fn: localTransferFn });
  };

  // ── Change handlers ───────────────────────────────────────────────────────
  const handleHRChange = (value) => {
    const next = Math.max(hrMin, Math.min(value, hrControlMax));
    setLocalHR(next);
    liveEmitMonitorParam("HR", next);
    liveSendVital({ heart_rate: next });
  };

  const handleRhythmSelect = (e) => {
    const engineRhythm  = e.target.value;
    const monitorRhythm = getMonitorRhythmLabel(engineRhythm);
    const profile       = RHYTHM_INTELLIGENCE[engineRhythm];
    let   nextHR        = localHR;

    if (profile?.hrMax === 0) {
      nextHR = 0;
    } else if (profile && (localHR < profile.hrMin || localHR > profile.hrMax)) {
      nextHR = profile.defaultHr;
    }

    setLocalRhythm(engineRhythm);
    if (nextHR !== localHR) setLocalHR(nextHR);

    if (!pendingMode) {
      updateParam("rhythm", monitorRhythm);
      socket.emit("update_rhythm", { rhythm: monitorRhythm });
      if (nextHR !== localHR) liveEmitMonitorParam("HR", nextHR);
    }
  };

  const handleSTChange = (elev, depr) => {
    setStElev(elev);
    setStDepr(depr);
    if (!pendingMode) {
      sendCommand({ st_elevation: elev, st_depression: depr, transfer_time: localTransferTime, transfer_fn: localTransferFn });
    }
  };

  const handleArtifactChange = (level, type) => {
    setArtifactLevel(level);
    setArtifactType(type);
    if (!pendingMode) {
      sendCommand({ artifact_level: level, artifact_type: type });
    }
  };

  const handleSpO2Change = (value) => {
    const next = Math.max(0, Math.min(value, 100));
    setLocalSpO2(next);
    liveEmitMonitorParam("SpO2", next);
    liveSendVital({ spo2: next });
  };

  const handleSysBPChange = (value) => {
    const next = Math.max(localDiaBP + 1, Math.min(value, 300));
    setLocalSysBP(next);
    liveEmitMonitorParam("ABP_sys", next);
    liveSendVital({ sys_bp: next });
  };

  const handleDiaBPChange = (value) => {
    const next = Math.max(0, Math.min(value, localSysBP - 1));
    setLocalDiaBP(next);
    liveEmitMonitorParam("ABP_dia", next);
    liveSendVital({ dia_bp: next });
  };

  const handlePapSysChange = (value) => {
    const next = Math.max(localPapDia + 0.5, Math.min(value, 100));
    setLocalPapSys(next);
    liveEmitMonitorParam("PAP_sys", next);
    liveSendVital({ pap_sys: next });
  };

  const handlePapDiaChange = (value) => {
    const next = Math.max(0, Math.min(value, localPapSys - 0.5));
    setLocalPapDia(next);
    liveEmitMonitorParam("PAP_dia", next);
    liveSendVital({ pap_dia: next });
  };

  const handleEtco2Change = (value) => {
    const next = Math.min(100, Math.max(0, value));
    setLocalEtco2(next);
    liveEmitMonitorParam("etCO2", next);
    liveSendVital({ etco2: next });
  };

  const handleRespRateChange = (value) => {
    const next = Math.min(80, Math.max(0, value));
    setLocalRR(next);
    liveEmitMonitorParam("avRR", next);
    liveSendVital({ resp_rate: next });
  };

  const handleTbloodChange = (value) => {
    const next = Math.min(45, Math.max(30, value));
    setLocalTblood(next);
    liveEmitMonitorParam("Tblood", next);
  };

  // ── Pending-mode Apply ────────────────────────────────────────────────────
  const handleApply = async () => {
    if (applying) return;
    setApplying(true);
    setApplyStatus(null);

    const staged = {};
    if (field === "HR" || field === "ecg" || field === "cardiac") {
      staged.HR            = localHR;
      staged.rhythm        = localRhythm;
      staged.stElev        = stElev;
      staged.stDepr        = stDepr;
      staged.artifactLevel = artifactLevel;
      staged.artifactType  = artifactType;
      staged.transferTime  = localTransferTime;
      staged.transferFn    = localTransferFn;
    } else if (field === "SpO2") {
      staged.SpO2 = localSpO2;
    } else if (field === "abp" || field === "ABP_sys" || field === "ABP_dia") {
      staged.BP_sys = localSysBP;
      staged.BP_dia = localDiaBP;
    } else if (field === "pap" || field === "PAP_sys" || field === "PAP_dia") {
      staged.PAP_sys = localPapSys;
      staged.PAP_dia = localPapDia;
    } else if (field === "etCO2" || field === "avRR") {
      staged.etCO2 = localEtco2;
      staged.RR    = localRR;
    } else if (field === "Tblood" || field === "Tperi") {
      staged.Tblood = localTblood;
    } else if (field === "NBP_sys" || field === "NBP_dia" || field === "nbp") {
      staged.NBP_sys = localNBPSys;
      staged.NBP_dia = localNBPDia;
      staged.nibp_interval = localNIBPInterval;
    } else if (field === "toggles") {
      staged.show_ecg   = showEcg;
      staged.show_hr    = showHr;
      staged.show_spo2  = showSpo2;
      staged.show_pleth = showPleth;
      staged.show_resp  = showResp;
      staged.show_rr    = showRr;
      staged.show_nibp  = showNibp;
      staged.show_map   = showMap;
      staged.show_temp  = showTemp;
      staged.show_etco2 = showEtco2;
    }

    try {
      if (onApply) {
        await onApply(staged);
      }
      setApplyStatus("success");
      setApplying(false);
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      console.error(err);
      setApplyStatus("error");
      setApplying(false);
    }
  };

  // ── Render helpers ────────────────────────────────────────────────────────
  const renderCardiacControls = () => {
    const rhythmProfile_ = RHYTHM_INTELLIGENCE[localRhythm];
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
        {/* Left Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <div className="control-card" style={{ padding: "6px 10px", margin: 0 }}>
            <h3 style={{ margin: "0 0 4px 0", fontSize: "13px" }}>Rhythm</h3>
            <select className="rhythm-select" value={localRhythm} onChange={handleRhythmSelect} style={{ width: "100%", padding: "3px", fontSize: "13px" }}>
              {ENGINE_RHYTHM_OPTIONS.map((group) => (
                <optgroup key={group.label} label={group.label}>
                  {group.rhythms.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <div className="control-card" style={{ padding: "6px 10px", margin: 0 }}>
            <h3 style={{ margin: "0 0 4px 0", fontSize: "13px" }}>Heart Rate</h3>
            <div className="control-row" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <input
                type="range"
                min={hrMin}
                max={hrControlMax}
                value={Math.min(Math.max(localHR, hrMin), hrControlMax)}
                onChange={(e) => handleHRChange(Number(e.target.value))}
                disabled={hrMax === 0}
                style={{ flex: 1, height: "4px" }}
              />
              <input
                type="number"
                min={hrMin}
                max={hrMax}
                value={localHR}
                onChange={(e) => handleHRChange(Number(e.target.value))}
                disabled={hrMax === 0}
                style={{ width: "52px", padding: "2px", fontSize: "13px" }}
              />
            </div>
          </div>

          <div className="control-card" style={{ padding: "6px 10px", margin: 0 }}>
            <h3 style={{ margin: "0 0 4px 0", fontSize: "13px" }}>ST Elevation / Ischemia</h3>
            <div className="control-row" style={{ marginBottom: "2px" }}>
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", fontSize: "12px" }}>
                <span>Elev (mm)</span>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flex: 1, marginLeft: "8px" }}>
                  <input type="range" min={-2} max={5} step={0.1} value={stElev} onChange={(e) => handleSTChange(Number(e.target.value), stDepr)} style={{ flex: 1, height: "4px" }} />
                  <span className="val-badge" style={{ fontSize: "11px", padding: "1px 4px" }}>+{stElev}</span>
                </div>
              </label>
            </div>
            <div className="control-row">
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", fontSize: "12px" }}>
                <span>Depr (mm)</span>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flex: 1, marginLeft: "8px" }}>
                  <input type="range" min={-2} max={5} step={0.1} value={stDepr} onChange={(e) => handleSTChange(stElev, Number(e.target.value))} style={{ flex: 1, height: "4px" }} />
                  <span className="val-badge" style={{ fontSize: "11px", padding: "1px 4px" }}>-{stDepr}</span>
                </div>
              </label>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <div className="control-card" style={{ padding: "6px 10px", margin: 0 }}>
            <h3 style={{ margin: "0 0 4px 0", fontSize: "13px" }}>Rhythm Metadata</h3>
            <div className="metadata-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2px 6px", fontSize: "11px" }}>
              <div className="metadata-item">
                <span className="meta-label" style={{ color: "#aaa" }}>P Wave: </span>
                <span className="meta-value" style={{ color: "#fff" }}>{rhythmProfile_?.pWave || "Normal"}</span>
              </div>
              <div className="metadata-item">
                <span className="meta-label" style={{ color: "#aaa" }}>T Wave: </span>
                <span className="meta-value" style={{ color: "#fff" }}>{rhythmProfile_?.tWave || "Normal"}</span>
              </div>
              <div className="metadata-item">
                <span className="meta-label" style={{ color: "#aaa" }}>QRS: </span>
                <span className="meta-value" style={{ color: "#fff" }}>{rhythmProfile_?.qrsType || "Normal"}</span>
              </div>
              <div className="metadata-item">
                <span className="meta-label" style={{ color: "#aaa" }}>Severity: </span>
                <span className="meta-value" style={{ color: "#fff" }}>{rhythmProfile_?.severity || "Normal"}</span>
              </div>
            </div>
          </div>

          <div className="control-card" style={{ padding: "6px 10px", margin: 0 }}>
            <h3 style={{ margin: "0 0 4px 0", fontSize: "13px" }}>Artifacts (Noise)</h3>
            <div className="control-row" style={{ marginBottom: "2px" }}>
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", fontSize: "12px" }}>
                <span>Intensity</span>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flex: 1, marginLeft: "8px" }}>
                  <input type="range" min={0} max={1} step={0.1} value={artifactLevel} onChange={(e) => handleArtifactChange(Number(e.target.value), artifactType)} style={{ flex: 1, height: "4px" }} />
                  <span className="val-badge" style={{ fontSize: "11px", padding: "1px 4px" }}>{Math.round(artifactLevel * 100)}%</span>
                </div>
              </label>
            </div>
            <div className="control-row">
              <select value={artifactType} onChange={(e) => handleArtifactChange(artifactLevel, e.target.value)} style={{ width: "100%", padding: "3px", fontSize: "13px" }}>
                <option value="NONE">None</option>
                <option value="POWERLINE_50">Electrical (50Hz)</option>
                <option value="POWERLINE_60">Electrical (60Hz)</option>
                <option value="EMG">Muscular</option>
                <option value="BASELINE">Baseline Wander</option>
                <option value="MOTION">Motion</option>
              </select>
            </div>
          </div>

          <div className="control-card" style={{ padding: "6px 10px", margin: 0 }}>
            <h3 style={{ margin: "0 0 4px 0", fontSize: "13px" }}>Transfer Behavior</h3>
            <div className="control-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2px", fontSize: "12px" }}>
              <span>Time (s)</span>
              <input
                type="number"
                min={0}
                max={300}
                value={localTransferTime}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setLocalTransferTime(v);
                  if (!pendingMode) sendCommand({ transfer_time: v, transfer_fn: localTransferFn });
                }}
                style={{ width: "52px", padding: "2px", fontSize: "13px" }}
              />
            </div>
            <div className="control-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "12px" }}>
              <span>Function</span>
              <select
                value={localTransferFn}
                onChange={(e) => {
                  const v = e.target.value;
                  setLocalTransferFn(v);
                  if (!pendingMode) sendCommand({ transfer_time: localTransferTime, transfer_fn: v });
                }}
                style={{ padding: "3px", fontSize: "13px", width: "100px" }}
              >
                <option value="IMMEDIATE">Immediate</option>
                <option value="LINEAR">Linear</option>
                <option value="SIGMOID">Sigmoid</option>
                <option value="EXPONENTIAL">Exponential</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderSpO2Controls = () => (
    <div className="control-card">
      <h3>Target SpO2</h3>
      <div className="control-row">
        <input type="range" min={0} max={100} value={localSpO2} onChange={(e) => handleSpO2Change(Number(e.target.value))} />
        <input type="number" min={0} max={100} value={localSpO2} onChange={(e) => handleSpO2Change(Number(e.target.value))} />
      </div>
    </div>
  );

  const renderABPControls = () => (
    <div className="control-card">
      <h3>ABP (Arterial BP)</h3>
      <div className="control-row">
        <label>
          <span>Systolic</span>
          <input type="range" min={40} max={240} value={localSysBP} onChange={(e) => handleSysBPChange(Number(e.target.value))} />
        </label>
        <label>
          <span>Diastolic</span>
          <input type="range" min={20} max={160} value={localDiaBP} onChange={(e) => handleDiaBPChange(Number(e.target.value))} />
        </label>
      </div>
    </div>
  );

  const renderPAPControls = () => (
    <div className="control-card">
      <h3>PAP (Pulmonary Artery Pressure)</h3>
      <div className="control-row">
        <label>
          <span>Systolic</span>
          <input type="range" min={10} max={80} value={localPapSys} onChange={(e) => handlePapSysChange(Number(e.target.value))} />
        </label>
        <label>
          <span>Diastolic</span>
          <input type="range" min={0} max={40} value={localPapDia} onChange={(e) => handlePapDiaChange(Number(e.target.value))} />
        </label>
      </div>
    </div>
  );

  const renderEtCO2Controls = () => (
    <div className="control-card">
      <h3>etCO2 & Respirations</h3>
      <div className="control-row">
        <label>
          <span>etCO2 (mmHg)</span>
          <input type="range" min={0} max={100} value={localEtco2} onChange={(e) => handleEtco2Change(Number(e.target.value))} />
        </label>
        <label>
          <span>awRR (/min)</span>
          <input type="range" min={0} max={80} value={localRR} onChange={(e) => handleRespRateChange(Number(e.target.value))} />
        </label>
      </div>
    </div>
  );

  const renderTempControls = () => (
    <div className="control-card">
      <h3>Blood Temperature (°C)</h3>
      <div className="control-row">
        <input type="range" min={30} max={45} step={0.1} value={localTblood} onChange={(e) => handleTbloodChange(Number(e.target.value))} />
        <input type="number" min={30} max={45} step={0.1} value={localTblood} onChange={(e) => handleTbloodChange(Number(e.target.value))} />
      </div>
    </div>
  );

  const renderNBPControls = () => (
    <div className="control-card">
      <h3>NIBP Controls</h3>
      <div className="control-row">
        <label>
          <span>Systolic</span>
          <input type="number" min={40} max={240} value={localNBPSys} onChange={(e) => setLocalNBPSys(Number(e.target.value))} />
        </label>
        <label>
          <span>Diastolic</span>
          <input type="number" min={20} max={160} value={localNBPDia} onChange={(e) => setLocalNBPDia(Number(e.target.value))} />
        </label>
      </div>
      <div className="control-row">
        <label>
          <span>Auto Interval</span>
          <select value={localNIBPInterval} onChange={(e) => setLocalNIBPInterval(Number(e.target.value))}>
            <option value={0}>STAT / Manual</option>
            <option value={1}>1 Min</option>
            <option value={5}>5 Mins</option>
            <option value={15}>15 Mins</option>
            <option value={30}>30 Mins</option>
          </select>
        </label>
      </div>
    </div>
  );

  const renderTogglesControls = () => (
    <div className="control-card">
      <h3>Display Toggles</h3>
      <div className="toggles-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
        <label><input type="checkbox" checked={showEcg} onChange={(e) => setShowEcg(e.target.checked)} /> Show ECG Wave</label>
        <label><input type="checkbox" checked={showHr} onChange={(e) => setShowHr(e.target.checked)} /> Show HR Value</label>
        <label><input type="checkbox" checked={showPleth} onChange={(e) => setShowPleth(e.target.checked)} /> Show Pleth Wave</label>
        <label><input type="checkbox" checked={showSpo2} onChange={(e) => setShowSpo2(e.target.checked)} /> Show SpO2 Value</label>
        <label><input type="checkbox" checked={showResp} onChange={(e) => setShowResp(e.target.checked)} /> Show Capno Wave</label>
        <label><input type="checkbox" checked={showRr} onChange={(e) => setShowRr(e.target.checked)} /> Show RR Value</label>
        <label><input type="checkbox" checked={showNibp} onChange={(e) => setShowNibp(e.target.checked)} /> Show NIBP Value</label>
        <label><input type="checkbox" checked={showMap} onChange={(e) => setShowMap(e.target.checked)} /> Show MAP Value</label>
        <label><input type="checkbox" checked={showTemp} onChange={(e) => setShowTemp(e.target.checked)} /> Show Temp Value</label>
        <label><input type="checkbox" checked={showEtco2} onChange={(e) => setShowEtco2(e.target.checked)} /> Show etCO2 Value</label>
      </div>
    </div>
  );

  const getTitle = () => {
    if (field === "HR" || field === "ecg" || field === "cardiac") return "ECG & Heart Rate Controls";
    if (field === "SpO2") return "SpO2 Controls";
    if (field === "abp" || field === "ABP_sys" || field === "ABP_dia") return "ABP Controls";
    if (field === "pap" || field === "PAP_sys" || field === "PAP_dia") return "PAP Controls";
    if (field === "etCO2" || field === "avRR") return "Respiratory & Capnography Controls";
    if (field === "Tblood" || field === "Tperi") return "Temperature Controls";
    if (field === "NBP_sys" || field === "NBP_dia" || field === "nbp") return "NIBP Controls";
    if (field === "toggles") return "Display Toggles";
    return "Parameter Controls";
  };

  return (
    <div className="dialog-overlay" style={{ zIndex: 10000 }}>
      <div className="dialog-box" style={{ maxWidth: field === "HR" || field === "ecg" || field === "cardiac" ? 640 : 440, width: "100%" }}>
        <div className="dialog-header">
          <h2>{getTitle()}</h2>
          <button className="btn-classic btn-sm" onClick={onClose}>✕</button>
        </div>

        <div className="dialog-body" style={{ padding: "12px 16px" }}>
          {(field === "HR" || field === "ecg" || field === "cardiac") && renderCardiacControls()}
          {field === "SpO2" && renderSpO2Controls()}
          {(field === "abp" || field === "ABP_sys" || field === "ABP_dia") && renderABPControls()}
          {(field === "pap" || field === "PAP_sys" || field === "PAP_dia") && renderPAPControls()}
          {(field === "etCO2" || field === "avRR") && renderEtCO2Controls()}
          {(field === "Tblood" || field === "Tperi") && renderTempControls()}
          {(field === "NBP_sys" || field === "NBP_dia" || field === "nbp") && renderNBPControls()}
          {field === "toggles" && renderTogglesControls()}

          {applyStatus === "success" && (
            <div style={{ color: "#3fb950", fontSize: "12px", marginTop: "8px", textAlign: "center" }}>
              ✓ Settings applied successfully
            </div>
          )}
          {applyStatus === "error" && (
            <div style={{ color: "#ff7b72", fontSize: "12px", marginTop: "8px", textAlign: "center" }}>
              ✕ Failed to apply settings
            </div>
          )}
        </div>

        <div className="dialog-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "8px", padding: "8px 16px" }}>
          <button className="btn-classic btn-cancel" onClick={onClose} disabled={applying}>Cancel</button>
          <button className="btn-classic btn-apply" onClick={handleApply} disabled={applying}>
            {applying ? "Applying..." : "Apply Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
