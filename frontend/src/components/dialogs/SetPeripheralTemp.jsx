import { useState } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

/**
 * Set Peripheral Temperature dialog — matches image 4.
 * Simple Tperi slider with From/To layout + OK/Cancel.
 */
export default function SetPeripheralTemp({ onClose }) {
  const storeTperi = useMonitorStore((s) => s.Tperi);

  const [tperi, setTperi] = useState(
    typeof storeTperi === "number" ? Math.round(storeTperi * 10) / 10 : 37.0
  );

  const handleApply = () => {
    // Optimistic local update
    useMonitorStore.getState().updateParam("Tperi", tperi);
    socket.emit("update_parameter", {
      field: "Tperi",
      value: tperi,
      transfer_time_seconds: 0,
      transfer_function: "immediate",
    });
  };

  const handleOK = () => {
    handleApply();
    onClose();
  };

  return (
    <div className="sim-dialog-overlay" onClick={onClose}>
      <div className="sim-dialog sim-dialog-narrow" onClick={(e) => e.stopPropagation()}>
        {/* Title bar */}
        <div className="sim-dialog-titlebar">
          <span>Set Peripheral Temperature</span>
          <button className="sim-dialog-close" onClick={onClose}>✕</button>
        </div>

        <div className="sim-dialog-body">
          {/* Tperi */}
          <fieldset className="sim-fieldset">
            <legend>Tperi</legend>
            <div className="sim-from-to">
              <div className="sim-from">
                <div className="sim-from-label">From</div>
                <div className="sim-from-sub">(current value):</div>
                <div className="sim-from-value">
                  {typeof storeTperi === "number" ? storeTperi.toFixed(1) : "37.0"}
                </div>
              </div>
              <div className="sim-slider-wrap">
                <input
                  type="range"
                  min={20} max={45} step={0.1}
                  value={tperi}
                  onChange={(e) => setTperi(Number(e.target.value))}
                  className="sim-slider"
                />
              </div>
              <div className="sim-to">
                <div className="sim-to-label">To</div>
                <div className="sim-from-sub">(new value):</div>
                <div className="sim-to-input-row">
                  <input
                    type="number"
                    min={20} max={45} step={0.1}
                    value={tperi}
                    onChange={(e) => setTperi(Number(e.target.value))}
                    className="sim-number-input"
                  />
                  <span className="sim-unit">C</span>
                </div>
              </div>
            </div>
          </fieldset>
        </div>

        <div className="sim-dialog-footer">
          <button className="sim-btn" onClick={handleOK}>OK</button>
          <button className="sim-btn" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
