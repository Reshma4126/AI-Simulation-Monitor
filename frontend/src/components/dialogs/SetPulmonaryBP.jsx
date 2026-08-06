IMSimport { useState } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

export default function SetPulmonaryBP({ isOpen, onClose, sessionCode }) {
  const curSys = useMonitorStore((s) => s.PAP_sys);
  const curDia = useMonitorStore((s) => s.PAP_dia);
  const curWedge = useMonitorStore((s) => s.PAP_wedge);
  const [sysTo, setSysTo] = useState(curSys);
  const [diaTo, setDiaTo] = useState(curDia);
  const [wedgeTo, setWedgeTo] = useState(curWedge);
  const [transferTime, setTransferTime] = useState(0);

  if (!isOpen) return null;

  const handleOk = () => {
    const store = useMonitorStore.getState();
    // Optimistic local update only for instant changes
    if (transferTime === 0) {
      store.updateParam("PAP_sys", sysTo);
      store.updateParam("PAP_dia", diaTo);
      store.updateParam("PAP_wedge", wedgeTo);
    }
    socket.emit("update_parameter", { field: "PAP_sys", value: sysTo, transfer_time_seconds: transferTime, transfer_function: "linear" });
    socket.emit("update_parameter", { field: "PAP_dia", value: diaTo, transfer_time_seconds: transferTime, transfer_function: "linear" });
    socket.emit("update_parameter", { field: "PAP_wedge", value: wedgeTo, transfer_time_seconds: transferTime, transfer_function: "linear" });
    onClose();
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-box" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">Set Pulmonary Artery Pressure</div>
        <div className="dialog-body">
          <div className="dialog-group">
            <div className="dialog-group-title">Systolic</div>
            <div className="dialog-row"><span className="dialog-label">Current:</span><span className="dialog-current">{curSys} mmHg</span></div>
            <input type="range" min={0} max={80} value={sysTo} onChange={(e) => setSysTo(Number(e.target.value))} className="dialog-slider" />
            <div className="dialog-row"><span className="dialog-label">Target:</span><input type="number" value={sysTo} onChange={(e) => setSysTo(Number(e.target.value))} className="dialog-input" /><span className="dialog-unit">mmHg</span></div>
          </div>
          <div className="dialog-group">
            <div className="dialog-group-title">Diastolic</div>
            <div className="dialog-row"><span className="dialog-label">Current:</span><span className="dialog-current">{curDia} mmHg</span></div>
            <input type="range" min={0} max={40} value={diaTo} onChange={(e) => setDiaTo(Number(e.target.value))} className="dialog-slider" />
            <div className="dialog-row"><span className="dialog-label">Target:</span><input type="number" value={diaTo} onChange={(e) => setDiaTo(Number(e.target.value))} className="dialog-input" /><span className="dialog-unit">mmHg</span></div>
          </div>
          <div className="dialog-group">
            <div className="dialog-group-title">Wedge (PCWP)</div>
            <div className="dialog-row"><span className="dialog-label">Current:</span><span className="dialog-current">{curWedge} mmHg</span></div>
            <input type="range" min={0} max={30} value={wedgeTo} onChange={(e) => setWedgeTo(Number(e.target.value))} className="dialog-slider" />
            <div className="dialog-row"><span className="dialog-label">Target:</span><input type="number" value={wedgeTo} onChange={(e) => setWedgeTo(Number(e.target.value))} className="dialog-input" /><span className="dialog-unit">mmHg</span></div>
          </div>
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
