import { useState } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

/**
 * Set SpO2 dialog — matches image 3.
 * SpO2 slider + Transfer controls + Cyanosis section.
 */
export default function SetSpO2({ onClose }) {
  const storeSpo2 = useMonitorStore((s) => s.SpO2);
  const storeCyanosisStart = useMonitorStore((s) => s.cyanosis_start);
  const storeCyanosisSevere = useMonitorStore((s) => s.cyanosis_severe);

  const [spo2, setSpo2] = useState(Math.round(storeSpo2));
  const [cyanosisStart, setCyanosisStart] = useState(Math.round(storeCyanosisStart ?? 90));
  const [cyanosisSevere, setCyanosisSevere] = useState(Math.round(storeCyanosisSevere ?? 70));
  const [transferTime, setTransferTime] = useState(0);
  const [transferFn, setTransferFn] = useState("immediate");

  const handleApply = () => {
    const store = useMonitorStore.getState();
    // Optimistic local update only for instant changes
    if (transferTime === 0) {
      store.updateParam("SpO2", spo2);
    }
    // Cyanosis thresholds are always instant
    store.updateParam("cyanosis_start", cyanosisStart);
    store.updateParam("cyanosis_severe", cyanosisSevere);
    socket.emit("update_parameter", {
      field: "SpO2",
      value: spo2,
      transfer_time_seconds: transferTime,
      transfer_function: transferFn,
    });
    socket.emit("update_parameter", {
      field: "cyanosis_start",
      value: cyanosisStart,
      transfer_time_seconds: 0,
      transfer_function: "immediate",
    });
    socket.emit("update_parameter", {
      field: "cyanosis_severe",
      value: cyanosisSevere,
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
      <div className="sim-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Title bar */}
        <div className="sim-dialog-titlebar">
          <span>Set SpO2</span>
          <button className="sim-dialog-close" onClick={onClose}>✕</button>
        </div>

        <div className="sim-dialog-body">
          {/* SpO2 */}
          <fieldset className="sim-fieldset">
            <legend>SpO2</legend>
            <div className="sim-from-to">
              <div className="sim-from">
                <div className="sim-from-label">From</div>
                <div className="sim-from-sub">(current value):</div>
                <div className="sim-from-value">{Math.round(storeSpo2)}</div>
              </div>
              <div className="sim-slider-wrap">
                <input
                  type="range"
                  min={0} max={100} step={1}
                  value={spo2}
                  onChange={(e) => setSpo2(Number(e.target.value))}
                  className="sim-slider"
                />
              </div>
              <div className="sim-to">
                <div className="sim-to-label">To</div>
                <div className="sim-from-sub">(new value):</div>
                <div className="sim-to-input-row">
                  <input
                    type="number"
                    min={0} max={100}
                    value={spo2}
                    onChange={(e) => setSpo2(Number(e.target.value))}
                    className="sim-number-input"
                  />
                  <span className="sim-unit">%</span>
                </div>
              </div>
            </div>
          </fieldset>

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

          {/* Cyanosis section */}
          <fieldset className="sim-fieldset sim-fieldset-cyanosis">
            <legend>Cyanosis</legend>

            <div className="sim-sub-section-label">Cyanosis start</div>
            <div className="sim-from-to">
              <div className="sim-from">
                <div className="sim-from-label">From</div>
                <div className="sim-from-sub">(current value):</div>
                <div className="sim-from-value">{Math.round(storeCyanosisStart ?? 90)}</div>
              </div>
              <div className="sim-slider-wrap">
                <input
                  type="range"
                  min={50} max={100} step={1}
                  value={cyanosisStart}
                  onChange={(e) => setCyanosisStart(Number(e.target.value))}
                  className="sim-slider"
                />
              </div>
              <div className="sim-to">
                <div className="sim-to-label">To</div>
                <div className="sim-from-sub">(new value):</div>
                <div className="sim-to-input-row">
                  <input
                    type="number"
                    min={50} max={100}
                    value={cyanosisStart}
                    onChange={(e) => setCyanosisStart(Number(e.target.value))}
                    className="sim-number-input"
                  />
                  <span className="sim-unit">%</span>
                </div>
              </div>
            </div>

            <div className="sim-sub-section-label" style={{ marginTop: 8 }}>Cyanosis severe</div>
            <div className="sim-from-to">
              <div className="sim-from">
                <div className="sim-from-label">From</div>
                <div className="sim-from-sub">(current value):</div>
                <div className="sim-from-value">{Math.round(storeCyanosisSevere ?? 70)}</div>
              </div>
              <div className="sim-slider-wrap">
                <input
                  type="range"
                  min={40} max={100} step={1}
                  value={cyanosisSevere}
                  onChange={(e) => setCyanosisSevere(Number(e.target.value))}
                  className="sim-slider"
                />
              </div>
              <div className="sim-to">
                <div className="sim-to-label">To</div>
                <div className="sim-from-sub">(new value):</div>
                <div className="sim-to-input-row">
                  <input
                    type="number"
                    min={40} max={100}
                    value={cyanosisSevere}
                    onChange={(e) => setCyanosisSevere(Number(e.target.value))}
                    className="sim-number-input"
                  />
                  <span className="sim-unit">%</span>
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
