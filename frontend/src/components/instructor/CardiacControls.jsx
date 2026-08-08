import { useState } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

const RHYTHMS = [
  "Sinus Rhythm",
  "Sinus Bradycardia",
  "Sinus Tachycardia",
  "Atrial Fibrillation",
  "Atrial Flutter",
  "SVT",
  "Ventricular Tachycardia",
  "Ventricular Fibrillation",
  "Asystole",
  "Junctional Rhythm",
  "1st Degree AV Block",
  "2nd Degree AV Block",
  "3rd Degree AV Block",
  "Paced Rhythm",
];

const EXTRASYSTOLES = ["None", "PVC", "PAC", "Coupled PVC", "R-on-T"];
const ECG_LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"];
const ARTIFACT_ELEC = ["Off", "50Hz", "60Hz"];
const ARTIFACT_MUSC = ["Off", "Low", "Medium", "High"];

export default function CardiacControls({ sessionCode, onClose }) {
  // Read LIVE values from the store (not props)
  const storeRhythm = useMonitorStore((s) => s.rhythm);
  const storeExtra = useMonitorStore((s) => s.extrasystole);
  const storeHR = useMonitorStore((s) => s.HR);
  const storeLead = useMonitorStore((s) => s.ecg_lead);
  const storeArtElec = useMonitorStore((s) => s.artifact_electrical);
  const storeArtMusc = useMonitorStore((s) => s.artifact_muscular);
  const storeEmd = useMonitorStore((s) => s.emd_pea);

  const [selectedRhythm, setSelectedRhythm] = useState(storeRhythm);
  const [selectedExtrasystole, setSelectedExtrasystole] = useState(storeExtra);
  const [hr, setHr] = useState(storeHR);
  const [ecgLead, setEcgLead] = useState(storeLead || "II");
  const [artifactElec, setArtifactElec] = useState(storeArtElec || "Off");
  const [artifactMusc, setArtifactMusc] = useState(storeArtMusc || "Off");
  const [emdPea, setEmdPea] = useState(storeEmd || false);

  const handleApply = () => {
    socket.emit("update_rhythm", {
      rhythm: selectedRhythm,
      extrasystole: selectedExtrasystole,
      HR: hr,
      ecg_lead: ecgLead,
      artifact_electrical: artifactElec,
      artifact_muscular: artifactMusc,
      emd_pea: emdPea,
    });
  };

  const handleOk = () => {
    handleApply();
    if (onClose) onClose();
  };

  const handleQuickAction = (actionLabel, eventMessage) => {
    socket.emit("add_event_log", {
      session_code: sessionCode,
      event: eventMessage,
    });
  };

  return (
    <div className="cardiac-controls">
      <div className="cardiac-header">Cardiac / Rhythm Controls</div>

      <div className="cardiac-body">
        {/* Resuscitation Actions */}
        <div className="cardiac-section" style={{ marginBottom: 12 }}>
          <div className="cardiac-section-title">Resuscitation Actions</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn-classic btn-sm" onClick={() => handleQuickAction("Shock 200J", "Defibrillator Shock Delivered (200J Biphasic)")} style={{ backgroundColor: "#7f1d1d", color: "#fef2f2", border: "1px solid #991b1b" }}>⚡ Shock 200J</button>
            <button type="button" className="btn-classic btn-sm" onClick={() => handleQuickAction("Start CPR", "Chest Compressions / CPR Initiated")} style={{ backgroundColor: "#854d0e", color: "#fefce8", border: "1px solid #a16207" }}>🫀 Start CPR</button>
            <button type="button" className="btn-classic btn-sm" onClick={() => handleQuickAction("Pulse Check", "Pulse & Rhythm Check Performed")} style={{ backgroundColor: "#1e293b", color: "#f8fafc", border: "1px solid #334155" }}>🔍 Pulse Check</button>
          </div>
        </div>

        {/* Rhythm List */}
        <div className="cardiac-section">
          <div className="cardiac-section-title">Rhythm</div>
          <div className="rhythm-list">
            {RHYTHMS.map((r) => (
              <div
                key={r}
                className={`rhythm-item ${selectedRhythm === r ? "rhythm-selected" : ""}`}
                onClick={() => setSelectedRhythm(r)}
              >
                {r}
              </div>
            ))}
          </div>
        </div>

        {/* Extrasystole */}
        <div className="cardiac-section">
          <div className="cardiac-section-title">Extrasystole</div>
          <div className="rhythm-list small-list">
            {EXTRASYSTOLES.map((e) => (
              <div
                key={e}
                className={`rhythm-item ${selectedExtrasystole === e ? "rhythm-selected" : ""}`}
                onClick={() => setSelectedExtrasystole(e)}
              >
                {e}
              </div>
            ))}
          </div>
        </div>

        {/* Heart Rate */}
        <div className="cardiac-section">
          <div className="cardiac-section-title">Heart Rate</div>
          <div className="hr-control">
            <input
              type="range"
              min={0} max={300}
              value={hr}
              onChange={(e) => setHr(Number(e.target.value))}
              className="hr-slider"
            />
            <input
              type="number"
              min={0} max={300}
              value={hr}
              onChange={(e) => setHr(Number(e.target.value))}
              className="hr-input"
            />
            <span className="hr-unit">bpm</span>
          </div>
        </div>

        {/* ECG Lead */}
        <div className="cardiac-section">
          <div className="cardiac-section-title">ECG Lead</div>
          <select
            value={ecgLead}
            onChange={(e) => setEcgLead(e.target.value)}
            className="dialog-select"
            style={{ width: "100%" }}
          >
            {ECG_LEADS.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>

        {/* Artifacts */}
        <div className="cardiac-section">
          <div className="cardiac-section-title">Artifacts</div>
          <div className="dialog-row">
            <span className="dialog-label">Electrical:</span>
            <select
              value={artifactElec}
              onChange={(e) => setArtifactElec(e.target.value)}
              className="dialog-select"
            >
              {ARTIFACT_ELEC.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
          <div className="dialog-row">
            <span className="dialog-label">Muscular:</span>
            <select
              value={artifactMusc}
              onChange={(e) => setArtifactMusc(e.target.value)}
              className="dialog-select"
            >
              {ARTIFACT_MUSC.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
        </div>

        {/* EMD/PEA */}
        <div className="cardiac-section">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={emdPea}
              onChange={(e) => setEmdPea(e.target.checked)}
            />
            EMD / PEA (Pulseless Electrical Activity)
          </label>
        </div>
      </div>

      <div className="cardiac-footer">
        <button className="btn-classic btn-apply" onClick={handleApply}>Apply</button>
        <button className="btn-classic btn-ok" onClick={handleOk}>OK</button>
        <button className="btn-classic btn-cancel" onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}
