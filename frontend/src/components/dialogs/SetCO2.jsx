import { useState } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

export default function SetCO2({ isOpen, onClose, sessionCode }) {
  const etCO2 = useMonitorStore((s) => s.etCO2);
  const inCO2 = useMonitorStore((s) => s.inCO2);
  const [etTarget, setEtTarget] = useState(etCO2);
  const [inTarget, setInTarget] = useState(inCO2);
  const [transferTime, setTransferTime] = useState(0);

  if (!isOpen) return null;

  const handleOk = () => {
    socket.emit("update_parameter", { session_code: sessionCode, field: "etCO2", value: etTarget, transfer_time: transferTime });
    socket.emit("update_parameter", { session_code: sessionCode, field: "inCO2", value: inTarget, transfer_time: transferTime });
    onClose();
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-box" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">Set CO₂ Parameters</div>
        <div className="dialog-body">
          <div className="dialog-group">
            <div className="dialog-group-title">End-tidal CO₂ (etCO₂)</div>
            <div className="dialog-row"><span className="dialog-label">Current:</span><span className="dialog-current">{etCO2} mmHg</span></div>
            <input type="range" min={0} max={80} value={etTarget} onChange={(e) => setEtTarget(Number(e.target.value))} className="dialog-slider" />
            <div className="dialog-row"><span className="dialog-label">Target:</span><input type="number" value={etTarget} onChange={(e) => setEtTarget(Number(e.target.value))} className="dialog-input" /><span className="dialog-unit">mmHg</span></div>
          </div>
          <div className="dialog-group">
            <div className="dialog-group-title">Inspired CO₂ (inCO₂)</div>
            <div className="dialog-row"><span className="dialog-label">Current:</span><span className="dialog-current">{inCO2} mmHg</span></div>
            <input type="range" min={0} max={20} value={inTarget} onChange={(e) => setInTarget(Number(e.target.value))} className="dialog-slider" />
            <div className="dialog-row"><span className="dialog-label">Target:</span><input type="number" value={inTarget} onChange={(e) => setInTarget(Number(e.target.value))} className="dialog-input" /><span className="dialog-unit">mmHg</span></div>
          </div>
          <div className="dialog-row">
            <span className="dialog-label">Transfer time:</span>
            <select value={transferTime} onChange={(e) => setTransferTime(Number(e.target.value))} className="dialog-select">
              <option value={0}>0 min</option><option value={1}>1 min</option><option value={2}>2 min</option><option value={5}>5 min</option>
            </select>
          </div>
        </div>
        <div className="dialog-footer">
          <button className="btn-classic btn-ok" onClick={handleOk}>OK</button>
          <button className="btn-classic btn-cancel" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
