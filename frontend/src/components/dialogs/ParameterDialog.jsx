import { useState, useEffect } from "react";
import socket from "../../socket";
import useMonitorStore from "../../store/monitorStore";

/**
 * Universal parameter editor dialog.
 * Reads the parameter spec to render the right control type:
 *   float/int → slider + number input
 *   enum → dropdown
 *   bool → toggle
 * Includes transfer_time_seconds + transfer_function selector.
 */
export default function ParameterDialog({ field, spec, sessionCode, onClose }) {
  const fieldSpec = spec[field];
  const currentValue = useMonitorStore((s) => s[field]);

  // Determine related fields (e.g. ABP_sys + ABP_dia)
  const relatedFields = getRelatedFields(field, spec);
  const allFields = [field, ...relatedFields.filter((f) => f !== field)];

  // Local state for each field being edited
  const [values, setValues] = useState({});
  const [transferTime, setTransferTime] = useState(0);
  const [transferFn, setTransferFn] = useState("linear");

  // Initialize local values from store
  useEffect(() => {
    const store = useMonitorStore.getState();
    const init = {};
    allFields.forEach((f) => {
      init[f] = store[f] ?? 0;
    });
    setValues(init);
  }, [field]);

  if (!fieldSpec) return null;

  const setVal = (f, v) => setValues((prev) => ({ ...prev, [f]: v }));

  const handleApply = () => {
    allFields.forEach((f) => {
      // Optimistic local update only for instant changes
      // For timed transfers let the server interpolation drive the graph
      if (transferTime === 0) {
        useMonitorStore.getState().updateParam(f, values[f]);
      }
      socket.emit("update_parameter", {
        field: f,
        value: values[f],
        transfer_time_seconds: transferTime,
        transfer_function: transferFn,
      });
    });
  };

  const handleOk = () => {
    handleApply();
    onClose();
  };

  const renderField = (f) => {
    const s = spec[f];
    if (!s) return null;
    const storeVal = useMonitorStore.getState()[f];

    if (s.type === "float" || s.type === "int") {
      return (
        <div key={f} className="dialog-group">
          <div className="dialog-group-title">
            {f} {s.unit ? `(${s.unit})` : ""}
          </div>
          <div className="dialog-row">
            <span className="dialog-label">Current:</span>
            <span className="dialog-current">
              {typeof storeVal === "number" ? Math.round(storeVal * 10) / 10 : storeVal}
            </span>
          </div>
          <input
            type="range"
            min={s.min ?? 0}
            max={s.max ?? 300}
            step={s.step ?? 1}
            value={values[f] ?? 0}
            onChange={(e) => setVal(f, Number(e.target.value))}
            className="dialog-slider"
          />
          <div className="dialog-row">
            <span className="dialog-label">New value:</span>
            <input
              type="number"
              min={s.min}
              max={s.max}
              step={s.step}
              value={values[f] ?? 0}
              onChange={(e) => setVal(f, Number(e.target.value))}
              className="dialog-input"
            />
            <span className="dialog-unit">{s.unit || ""}</span>
          </div>
        </div>
      );
    }

    if (s.type === "enum") {
      return (
        <div key={f} className="dialog-group">
          <div className="dialog-group-title">{f}</div>
          <select
            value={values[f] ?? ""}
            onChange={(e) => setVal(f, e.target.value)}
            className="dialog-select"
            style={{ width: "100%", padding: "8px" }}
          >
            {(s.enum || []).map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      );
    }

    if (s.type === "bool") {
      return (
        <div key={f} className="dialog-group">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={!!values[f]}
              onChange={(e) => setVal(f, e.target.checked)}
            />
            {f}
          </label>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-box" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          Set {fieldSpec.category || field}
        </div>
        <div className="dialog-body">
          {allFields.map(renderField)}

          {/* Transfer controls — only for numeric fields */}
          {(fieldSpec.type === "float" || fieldSpec.type === "int") && (
            <div className="dialog-group">
              <div className="dialog-group-title">Transfer</div>
              <div className="dialog-row">
                <span className="dialog-label">Time:</span>
                <select
                  value={transferTime}
                  onChange={(e) => setTransferTime(Number(e.target.value))}
                  className="dialog-select"
                >
                  <option value={0}>Instant</option>
                  <option value={10}>10 sec</option>
                  <option value={30}>30 sec</option>
                  <option value={60}>1 min</option>
                  <option value={120}>2 min</option>
                  <option value={300}>5 min</option>
                </select>
              </div>
              {transferTime > 0 && (
                <div className="dialog-row">
                  <span className="dialog-label">Function:</span>
                  <select
                    value={transferFn}
                    onChange={(e) => setTransferFn(e.target.value)}
                    className="dialog-select"
                  >
                    <option value="linear">Linear</option>
                    <option value="smooth">Smooth (ease)</option>
                  </select>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="dialog-footer">
          <button className="btn-classic btn-apply" onClick={handleApply}>
            Apply
          </button>
          <button className="btn-classic btn-ok" onClick={handleOk}>
            OK
          </button>
          <button className="btn-classic btn-cancel" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Given a field, return the group of related fields to edit together.
 * E.g., clicking ABP_sys also shows ABP_dia.
 */
function getRelatedFields(field, spec) {
  const groups = {
    ABP_sys: ["ABP_sys", "ABP_dia"],
    ABP_dia: ["ABP_sys", "ABP_dia"],
    NBP_sys: ["NBP_sys", "NBP_dia"],
    NBP_dia: ["NBP_sys", "NBP_dia"],
    PAP_sys: ["PAP_sys", "PAP_dia", "PAP_wedge"],
    PAP_dia: ["PAP_sys", "PAP_dia", "PAP_wedge"],
    PAP_wedge: ["PAP_sys", "PAP_dia", "PAP_wedge"],
    Tperi: ["Tperi", "Tblood"],
    Tblood: ["Tperi", "Tblood"],
    etCO2: ["etCO2", "inCO2"],
    inCO2: ["etCO2", "inCO2"],
    etO2: ["etO2", "inO2"],
    inO2: ["etO2", "inO2"],
    etN2O: ["etN2O", "inN2O"],
    inN2O: ["etN2O", "inN2O"],
  };
  return groups[field] || [field];
}
