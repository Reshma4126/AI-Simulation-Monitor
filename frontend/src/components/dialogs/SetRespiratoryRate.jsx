import { useState } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

export default function SetRespiratoryRate({ isOpen, onClose, sessionCode }) {
  const current = useMonitorStore((s) => s.avRR);
  const [target, setTarget] = useState(current);
  const [transferTime, setTransferTime] = useState(0);

  if (!isOpen) return null;

  const handleOk = () => {
    // Optimistic local update only for instant changes
    if (transferTime === 0) {
      useMonitorStore.getState().updateParam("avRR", target);
    }
    socket.emit("update_parameter", { field: "avRR", value: target, transfer_time_seconds: transferTime, transfer_function: "linear" });
    onClose();
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-box" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">Set Respiratory Rate</div>
        <div className="dialog-body">
          <div className="dialog-row"><span className="dialog-label">Current:</span><span className="dialog-current">{current} /min</span></div>
          <input type="range" min={0} max={40} value={target} onChange={(e) => setTarget(Number(e.target.value))} className="dialog-slider" />
          <div className="dialog-row"><span className="dialog-label">Target:</span><input type="number" value={target} onChange={(e) => setTarget(Number(e.target.value))} className="dialog-input" /><span className="dialog-unit">/min</span></div>
          <div className="dialog-row">
            <span className="dialog-label">Transfer time:</span>
            <select value={transferTime} onChange={(e) => setTransferTime(Number(e.target.value))} className="dialog-select">
              <option value={0}>0 min (instant)</option><option value={60}>1 min</option><option value={120}>2 min</option><option value={300}>5 min</option>
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
