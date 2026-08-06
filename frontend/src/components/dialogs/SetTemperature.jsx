import { useState } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

export default function SetTemperature({ isOpen, onClose, sessionCode }) {
  const currentPeri = useMonitorStore((s) => s.Tperi);
  const currentBlood = useMonitorStore((s) => s.Tblood);
  const [periTo, setPeriTo] = useState(currentPeri);
  const [bloodTo, setBloodTo] = useState(currentBlood);
  const [transferTime, setTransferTime] = useState(0);

  if (!isOpen) return null;

  const handleOk = () => {
    socket.emit("update_parameter", { session_code: sessionCode, field: "Tperi", value: periTo, transfer_time: transferTime });
    socket.emit("update_parameter", { session_code: sessionCode, field: "Tblood", value: bloodTo, transfer_time: transferTime });
    onClose();
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-box" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">Set Temperature</div>
        <div className="dialog-body">
          <div className="dialog-group">
            <div className="dialog-group-title">Peripheral (Tperi)</div>
            <div className="dialog-row">
              <span className="dialog-label">Current:</span>
              <span className="dialog-current">{currentPeri} °C</span>
            </div>
            <input type="range" min={30} max={42} step={0.1} value={periTo}
              onChange={(e) => setPeriTo(Number(e.target.value))} className="dialog-slider" />
            <div className="dialog-row">
              <span className="dialog-label">Target:</span>
              <input type="number" step={0.1} value={periTo}
                onChange={(e) => setPeriTo(Number(e.target.value))} className="dialog-input" />
              <span className="dialog-unit">°C</span>
            </div>
          </div>
          <div className="dialog-group">
            <div className="dialog-group-title">Blood (Tblood)</div>
            <div className="dialog-row">
              <span className="dialog-label">Current:</span>
              <span className="dialog-current">{currentBlood} °C</span>
            </div>
            <input type="range" min={30} max={42} step={0.1} value={bloodTo}
              onChange={(e) => setBloodTo(Number(e.target.value))} className="dialog-slider" />
            <div className="dialog-row">
              <span className="dialog-label">Target:</span>
              <input type="number" step={0.1} value={bloodTo}
                onChange={(e) => setBloodTo(Number(e.target.value))} className="dialog-input" />
              <span className="dialog-unit">°C</span>
            </div>
          </div>
          <div className="dialog-row">
            <span className="dialog-label">Transfer time:</span>
            <select value={transferTime} onChange={(e) => setTransferTime(Number(e.target.value))} className="dialog-select">
              <option value={0}>0 min</option><option value={1}>1 min</option>
              <option value={2}>2 min</option><option value={5}>5 min</option>
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
