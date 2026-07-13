import React, { useState, useCallback } from "react";
import { createPortal } from "react-dom";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";
import { useECGStore } from "../../store/ecgStore";
import { getMonitorRhythmLabel } from "../../utils/rhythms";
import InstructorParameterModal from "../dialogs/InstructorParameterModal";

export default function ScenarioDrawer({ isOpen, onClose, scenario }) {
  // ── Pending edits shown in the Initial Readings cards ─────────────────────
  // Structure: { HR, BP_sys, BP_dia, SpO2, RR, etCO2, Tblood }  (numeric display values)
  const [pendingEdits, setPendingEdits] = useState({});

  // ── Additional pending state for HR-dialog extras (rhythm, ST, artifacts) ─
  const [pendingECG, setPendingECG] = useState(null);
  // pendingECG shape: { rhythm, stElev, stDepr, artifactLevel, artifactType, transferTime, transferFn }

  // ── Which parameter dialog is currently open ──────────────────────────────
  const [openDialogKey, setOpenDialogKey] = useState(null);

  // ── Live monitor store values ─────────────────────────────────────────────
  const liveHR      = useMonitorStore((s) => s.HR);
  const liveABP_sys = useMonitorStore((s) => s.ABP_sys);
  const liveABP_dia = useMonitorStore((s) => s.ABP_dia);
  const liveSpO2    = useMonitorStore((s) => s.SpO2);
  const liveRR      = useMonitorStore((s) => s.avRR);
  const liveEtCO2   = useMonitorStore((s) => s.etCO2);
  const liveTblood  = useMonitorStore((s) => s.Tblood);

  const updateParam = useMonitorStore((s) => s.updateParam);
  const sendCommand = useECGStore((s) => s.sendCommand);
  const ecgTransferTime = useECGStore((s) => s.transferTime);
  const ecgTransferFn   = useECGStore((s) => s.transferFn);

  // ── Reset on close ────────────────────────────────────────────────────────
  const handleClose = useCallback(() => {
    setPendingEdits({});
    setPendingECG(null);
    setOpenDialogKey(null);
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  // ── Helpers ───────────────────────────────────────────────────────────────
  const parseReadings = (readings) => {
    if (!readings) return null;
    return typeof readings === "string" ? JSON.parse(readings) : readings;
  };

  const hasPending = Object.keys(pendingEdits).length > 0 || pendingECG !== null;

  // ── Card dialog key mapping ───────────────────────────────────────────────
  // Maps an internal card key → the field prop expected by InstructorParameterModal
  const CARD_TO_DIALOG = {
    HR:     "HR",
    BP_sys: "abp",
    BP_dia: "abp",
    SpO2:   "SpO2",
    RR:     "avRR",
    etCO2:  "etCO2",
    Tblood: "Tblood",
  };

  // Build initialValues for each dialog from current pending state
  const buildInitialValues = (cardKey) => {
    const base = {};
    if (cardKey === "HR") {
      base.HR = "HR" in pendingEdits ? pendingEdits.HR : liveHR;
      if (pendingECG) {
        base.rhythm      = pendingECG.rhythm;
        base.stElev      = pendingECG.stElev;
        base.stDepr      = pendingECG.stDepr;
        base.artifactLevel = pendingECG.artifactLevel;
        base.artifactType  = pendingECG.artifactType;
      }
    } else if (cardKey === "BP_sys" || cardKey === "BP_dia") {
      base.BP_sys = "BP_sys" in pendingEdits ? pendingEdits.BP_sys : liveABP_sys;
      base.BP_dia = "BP_dia" in pendingEdits ? pendingEdits.BP_dia : liveABP_dia;
    } else if (cardKey === "SpO2") {
      base.SpO2 = "SpO2" in pendingEdits ? pendingEdits.SpO2 : liveSpO2;
    } else if (cardKey === "RR") {
      base.RR    = "RR"    in pendingEdits ? pendingEdits.RR    : liveRR;
      base.etCO2 = "etCO2" in pendingEdits ? pendingEdits.etCO2 : liveEtCO2;
    } else if (cardKey === "etCO2") {
      base.etCO2 = "etCO2" in pendingEdits ? pendingEdits.etCO2 : liveEtCO2;
      base.RR    = "RR"    in pendingEdits ? pendingEdits.RR    : liveRR;
    } else if (cardKey === "Tblood") {
      base.Tblood = "Tblood" in pendingEdits ? pendingEdits.Tblood : liveTblood;
    }
    return base;
  };

  // ── Stage 1: Dialog Apply callback ───────────────────────────────────────
  // Called when the instructor clicks Apply inside the parameter dialog.
  // Only updates pendingEdits / pendingECG — nothing reaches the monitor yet.
  const handleDialogApply = (staged) => {
    setPendingEdits((prev) => {
      const next = { ...prev };
      if ("HR"     in staged) next.HR     = staged.HR;
      if ("SpO2"   in staged) next.SpO2   = staged.SpO2;
      if ("BP_sys" in staged) next.BP_sys = staged.BP_sys;
      if ("BP_dia" in staged) next.BP_dia = staged.BP_dia;
      if ("PAP_sys" in staged) next.PAP_sys = staged.PAP_sys;
      if ("PAP_dia" in staged) next.PAP_dia = staged.PAP_dia;
      if ("etCO2"  in staged) next.etCO2  = staged.etCO2;
      if ("RR"     in staged) next.RR     = staged.RR;
      if ("Tblood" in staged) next.Tblood = staged.Tblood;
      return next;
    });

    // Capture HR-dialog extras (rhythm, ST, artifacts)
    if ("rhythm" in staged || "stElev" in staged) {
      setPendingECG((prev) => ({
        ...(prev || {}),
        rhythm:        staged.rhythm       ?? prev?.rhythm,
        stElev:        staged.stElev       ?? prev?.stElev       ?? 0,
        stDepr:        staged.stDepr       ?? prev?.stDepr       ?? 0,
        artifactLevel: staged.artifactLevel ?? prev?.artifactLevel ?? 0,
        artifactType:  staged.artifactType  ?? prev?.artifactType  ?? "NONE",
        transferTime:  staged.transferTime  ?? prev?.transferTime  ?? ecgTransferTime,
        transferFn:    staged.transferFn    ?? prev?.transferFn    ?? ecgTransferFn,
      }));
    }

    setOpenDialogKey(null);
  };

  // ── Stage 2: Apply Changes — commit everything simultaneously ─────────────
  const handleApplyChanges = () => {
    if (!hasPending) return;

    const mapped = {};
    if ("HR" in pendingEdits) mapped.HR = Number(pendingEdits.HR);
    if ("BP_sys" in pendingEdits) mapped.ABP_sys = Number(pendingEdits.BP_sys);
    if ("BP_dia" in pendingEdits) mapped.ABP_dia = Number(pendingEdits.BP_dia);
    if ("SpO2" in pendingEdits) mapped.SpO2 = Number(pendingEdits.SpO2);
    if ("RR" in pendingEdits) mapped.avRR = Number(pendingEdits.RR);
    if ("etCO2" in pendingEdits) mapped.etCO2 = Number(pendingEdits.etCO2);
    if ("Tblood" in pendingEdits) mapped.Tblood = Number(pendingEdits.Tblood);

    if (pendingECG) {
      if (pendingECG.rhythm) {
        const monitorRhythm = getMonitorRhythmLabel(pendingECG.rhythm);
        if (monitorRhythm) mapped.rhythm = monitorRhythm;
      }
    }

    // Emit atomic settings update
    socket.emit("apply_all_settings", mapped);

    // Commit ECG engine state (HR, SpO2, BP, RR, EtCO2, rhythm, ST, artifacts)
    const engineCmd = {
      transfer_time: pendingECG?.transferTime ?? ecgTransferTime,
      transfer_fn:   pendingECG?.transferFn   ?? ecgTransferFn,
    };
    if ("HR"     in pendingEdits) engineCmd.heart_rate = Number(pendingEdits.HR);
    if ("SpO2"   in pendingEdits) engineCmd.spo2       = Number(pendingEdits.SpO2);
    if ("BP_sys" in pendingEdits) engineCmd.sys_bp     = Number(pendingEdits.BP_sys);
    if ("BP_dia" in pendingEdits) engineCmd.dia_bp     = Number(pendingEdits.BP_dia);
    if ("RR"     in pendingEdits) engineCmd.resp_rate  = Number(pendingEdits.RR);
    if ("etCO2"  in pendingEdits) engineCmd.etco2      = Number(pendingEdits.etCO2);

    if (pendingECG) {
      if (pendingECG.rhythm)       engineCmd.rhythm        = pendingECG.rhythm;
      if (pendingECG.stElev != null) engineCmd.st_elevation = pendingECG.stElev;
      if (pendingECG.stDepr != null) engineCmd.st_depression = pendingECG.stDepr;
      if (pendingECG.artifactLevel != null) engineCmd.artifact_level = pendingECG.artifactLevel;
      if (pendingECG.artifactType)  engineCmd.artifact_type = pendingECG.artifactType;
    }

    if (Object.keys(engineCmd).length > 2) {
      sendCommand(engineCmd);
    }

    // Clear all pending state
    setPendingEdits({});
    setPendingECG(null);
  };

  // ── Render helpers ────────────────────────────────────────────────────────
  const renderPatientDetails = (details) => {
    if (!details) return null;
    const pd = typeof details === "string" ? JSON.parse(details) : details;
    return (
      <div className="scenario-patient-details">
        <div className="scenario-detail-row">
          <span className="scenario-detail-label">Name</span>
          <span className="scenario-detail-value">{pd.patientName}</span>
        </div>
        <div className="scenario-detail-row">
          <span className="scenario-detail-label">Age / Gender</span>
          <span className="scenario-detail-value">{pd.age} / {pd.gender}</span>
        </div>
        <div className="scenario-detail-row">
          <span className="scenario-detail-label">Blood Group</span>
          <span className="scenario-detail-value">{pd.bloodGroup}</span>
        </div>
        <div className="scenario-detail-row">
          <span className="scenario-detail-label">Height / Weight</span>
          <span className="scenario-detail-value">{pd.heightCm}cm / {pd.weightKg}kg</span>
        </div>
        <div className="scenario-detail-row">
          <span className="scenario-detail-label">Chief Complaint</span>
          <span className="scenario-detail-value">{pd.chiefComplaint}</span>
        </div>
        <div className="scenario-detail-row">
          <span className="scenario-detail-label">Diagnosis</span>
          <span className="scenario-detail-value">{pd.diagnosis}</span>
        </div>
        {pd.medicalHistory && pd.medicalHistory.length > 0 && (
          <div className="scenario-detail-row">
            <span className="scenario-detail-label">History</span>
            <span className="scenario-detail-value">{pd.medicalHistory.join(", ")}</span>
          </div>
        )}
        {pd.allergies && pd.allergies.filter((a) => a !== "None").length > 0 && (
          <div className="scenario-detail-row">
            <span className="scenario-detail-label">Allergies</span>
            <span className="scenario-detail-value">{pd.allergies.join(", ")}</span>
          </div>
        )}
        <div className="scenario-detail-row">
          <span className="scenario-detail-label">Triage</span>
          <span
            className="scenario-detail-value"
            style={{ color: pd.triageLevel === "Emergency" ? "var(--alarm-red)" : "var(--alarm-gold)" }}
          >
            {pd.triageLevel}
          </span>
        </div>
      </div>
    );
  };

  const renderSymptoms = (symptoms) => {
    if (!symptoms) return null;
    const symp = typeof symptoms === "string" ? JSON.parse(symptoms) : symptoms;
    const activeSymptoms = Object.entries(symp).filter(([, v]) => v === true);
    if (activeSymptoms.length === 0) return <span style={{ color: "#666" }}>None</span>;
    return (
      <div className="scenario-symptoms-list">
        {activeSymptoms.map(([key]) => (
          <span key={key} className="scenario-symptom-tag">
            {key.replace(/([A-Z])/g, " $1").trim()}
          </span>
        ))}
      </div>
    );
  };

  // A single clickable reading card
  const readingCard = (cardKey, liveVal, color, label, displayFn) => {
    const isPending = cardKey in pendingEdits;
    const displayValue = isPending ? pendingEdits[cardKey] : liveVal;
    const formatted = displayFn ? displayFn(displayValue) : displayValue;
    return (
      <div
        key={cardKey}
        className={`reading-item${isPending ? " reading-item--pending" : ""}`}
        style={{ color, cursor: "pointer" }}
        title={`Click to edit ${label}`}
        onClick={() => setOpenDialogKey(cardKey)}
      >
        <span className="reading-label">{label}</span>
        <span className="reading-value">{formatted}</span>
      </div>
    );
  };

  const renderInitialReadings = (readings) => {
    if (!readings) return null;
    const rd = parseReadings(readings);

    // BP card: show sys/dia together
    const bpPending = "BP_sys" in pendingEdits || "BP_dia" in pendingEdits;
    const bpSys = "BP_sys" in pendingEdits ? pendingEdits.BP_sys : liveABP_sys;
    const bpDia = "BP_dia" in pendingEdits ? pendingEdits.BP_dia : liveABP_dia;

    return (
      <div className="scenario-readings-grid">
        {rd.heartRate != null && readingCard("HR", liveHR, "#00FF00", "HR")}

        {rd.bloodPressure && (
          <div
            className={`reading-item reading-item--bp${bpPending ? " reading-item--pending" : ""}`}
            style={{ color: "#FF3333", cursor: "pointer" }}
            title="Click to edit Blood Pressure"
            onClick={() => setOpenDialogKey("BP_sys")}
          >
            <span className="reading-label">BP</span>
            <span className="reading-value">{bpSys}/{bpDia}</span>
          </div>
        )}

        {rd.spo2 != null && readingCard("SpO2", liveSpO2, "#FFFF00", "SpO₂ %")}

        {rd.respiratoryRate != null && readingCard("RR", liveRR, "#00CCFF", "RR")}

        {rd.etco2 != null && readingCard("etCO2", liveEtCO2, "#00CCFF", "etCO₂")}

        {rd.temperature && readingCard(
          "Tblood",
          liveTblood,
          "#CC99FF",
          "Temp °C",
          (v) => (typeof v === "number" ? v.toFixed(1) : v)
        )}
      </div>
    );
  };

  // ── Determine which dialog field to pass to InstructorParameterModal ──────
  const dialogField = openDialogKey ? (CARD_TO_DIALOG[openDialogKey] ?? openDialogKey) : null;
  const dialogInitialValues = openDialogKey ? buildInitialValues(openDialogKey) : {};

  return (
    <>
      <div className="scenario-drawer-overlay" onClick={handleClose}>
        <div className="scenario-drawer" onClick={(e) => e.stopPropagation()}>
          <div className="scenario-drawer-header">
            <h2>Case Details</h2>
            <button className="btn-classic btn-sm" onClick={handleClose}>✕</button>
          </div>
          <div className="scenario-drawer-body">
            {scenario ? (
              <div className="scenario-card-full">
                <div className="scenario-card-section">
                  <h4 className="scenario-card-section-title">Patient Details</h4>
                  {renderPatientDetails(scenario.patient_details)}
                </div>
                <div className="scenario-card-section">
                  <h4 className="scenario-card-section-title">Symptoms</h4>
                  {renderSymptoms(scenario.symptoms)}
                </div>
                {scenario.initial_readings && (
                  <div className="scenario-card-section">
                    <div className="scenario-readings-header">
                      <h4
                        className="scenario-card-section-title"
                        style={{ margin: 0, border: "none", paddingBottom: 0 }}
                      >
                        Initial Readings
                      </h4>
                      <button
                        className={`btn-apply-changes${hasPending ? " btn-apply-changes--active" : ""}`}
                        onClick={handleApplyChanges}
                        disabled={!hasPending}
                        title={hasPending ? "Apply all pending changes to the simulator" : "No changes to apply"}
                      >
                        Apply Changes
                      </button>
                    </div>
                    <div className="scenario-readings-divider" />
                    {renderInitialReadings(scenario.initial_readings)}
                  </div>
                )}
              </div>
            ) : (
              <div className="scenario-empty">
                <p>No scenario loaded. Use <strong>Choose Scenario</strong> from the top bar.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stage 1 dialog — portal-rendered into document.body so it always sits
          above the drawer's stacking context (z-index: 9999). */}
      {openDialogKey && dialogField && createPortal(
        <InstructorParameterModal
          field={dialogField}
          pendingMode={true}
          initialValues={dialogInitialValues}
          onApply={handleDialogApply}
          onClose={() => setOpenDialogKey(null)}
        />,
        document.body
      )}
    </>
  );
}
