import { useState } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

/**
 * Set Arterial BP dialog — matches image 2.
 * Shows Systolic + Diastolic sliders with From/To layout.
 * Optional "Coupled" checkbox keeps pulse pressure constant.
 */
export default function SetArterialBP({ onClose }) {
  const storeABP_sys = useMonitorStore((s) => s.ABP_sys);
  const storeABP_dia = useMonitorStore((s) => s.ABP_dia);

  const [sys, setSys] = useState(Math.round(storeABP_sys));
  const [dia, setDia] = useState(Math.round(storeABP_dia));
  const [coupled, setCoupled] = useState(false);
  const [transferTime, setTransferTime] = useState(0);
  const [transferFn, setTransferFn] = useState("immediate");

  const PULSE_PRESSURE = Math.round(storeABP_sys - storeABP_dia);

  const handleSysChange = (val) => {
    setSys(val);
    if (coupled) setDia(Math.max(0, val - PULSE_PRESSURE));
  };

  const handleDiaChange = (val) => {
    setDia(val);
  };

  const handleApply = () => {
    const store = useMonitorStore.getState();
    // Optimistic local update only for instant changes
    if (transferTime === 0) {
      store.updateParam("ABP_sys", sys);
      store.updateParam("ABP_dia", dia);
    }
    socket.emit("update_parameter", {
      field: "ABP_sys",
      value: sys,
      transfer_time_seconds: transferTime,
      transfer_function: transferFn,
    });
    socket.emit("update_parameter", {
      field: "ABP_dia",
      value: dia,
      transfer_time_seconds: transferTime,
      transfer_function: transferFn,
    });
  };

  const handleOK = () => {
    handleApply();
    onClose();
  };

  return (
    <div className="sim-dialog-overlay" onClick={onClose}>
      <div className="sim-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Title bar */}
        <div className="sim-dialog-titlebar">
          <span>Set Arterial BP</span>
          <button className="sim-dialog-close" onClick={onClose}>✕</button>
        </div>

        <div className="sim-dialog-body">
          {/* Systolic */}
          <fieldset className="sim-fieldset">
            <legend>Systolic</legend>
            <div className="sim-from-to">
              <div className="sim-from">
                <div className="sim-from-label">From</div>
                <div className="sim-from-sub">(current value):</div>
                <div className="sim-from-value">{Math.round(storeABP_sys)}</div>
              </div>
              <div className="sim-slider-wrap">
                <input
                  type="range"
                  min={0} max={300} step={1}
                  value={sys}
                  onChange={(e) => handleSysChange(Number(e.target.value))}
                  className="sim-slider"
                />
              </div>
              <div className="sim-to">
                <div className="sim-to-label">To</div>
                <div className="sim-from-sub">(new value):</div>
                <div className="sim-to-input-row">
                  <input
                    type="number"
                    min={0} max={300}
                    value={sys}
                    onChange={(e) => handleSysChange(Number(e.target.value))}
                    className="sim-number-input"
                  />
                  <span className="sim-unit">mmHg</span>
                </div>
              </div>
            </div>
          </fieldset>

          {/* Diastolic */}
          <fieldset className="sim-fieldset">
            <legend>Diastolic</legend>
            <div className="sim-from-to">
              <div className="sim-from">
                <div className="sim-from-label">From</div>
                <div className="sim-from-sub">(current value):</div>
                <div className="sim-from-value">{Math.round(storeABP_dia)}</div>
              </div>
              <div className="sim-slider-wrap">
                <input
                  type="range"
                  min={0} max={200} step={1}
                  value={dia}
                  onChange={(e) => handleDiaChange(Number(e.target.value))}
                  className="sim-slider"
                />
              </div>
              <div className="sim-to">
                <div className="sim-to-label">To</div>
                <div className="sim-from-sub">(new value):</div>
                <div className="sim-to-input-row">
                  <input
                    type="number"
                    min={0} max={200}
                    value={dia}
                    onChange={(e) => handleDiaChange(Number(e.target.value))}
                    className="sim-number-input"
                  />
                  <span className="sim-unit">mmHg</span>
                </div>
              </div>
            </div>
          </fieldset>

          {/* Coupled checkbox */}
          <label className="sim-coupled-row">
            <input
              type="checkbox"
              checked={coupled}
              onChange={(e) => setCoupled(e.target.checked)}
            />
            <span>Coupled</span>
          </label>

          {/* Transfer time */}
          <div className="sim-transfer-group">
            <div className="sim-transfer-label">Transfer time:</div>
            <select
              value={transferTime}
              onChange={(e) => setTransferTime(Number(e.target.value))}
              className="sim-select"
            >
              <option value={0}>0 min</option>
              <option value={30}>0.5 min</option>
              <option value={60}>1 min</option>
              <option value={120}>2 min</option>
              <option value={300}>5 min</option>
            </select>
          </div>

          {/* Transfer function */}
          <div className="sim-transfer-group">
            <div className="sim-transfer-label">Transfer function:</div>
            <select
              value={transferFn}
              onChange={(e) => setTransferFn(e.target.value)}
              className="sim-select sim-select-fn"
            >
              <option value="immediate">— Immediate</option>
              <option value="linear">/ Linear</option>
              <option value="smooth">~ Smooth</option>
            </select>
          </div>
        </div>

        <div className="sim-dialog-footer">
          <button className="sim-btn" onClick={handleOK}>OK</button>
          <button className="sim-btn" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
