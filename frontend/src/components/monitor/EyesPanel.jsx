import useMonitorStore from "../../store/monitorStore";
import socket from "../../socket";

const EYES_STATES = ["Open", "Closed", "Half Open", "Blinking"];
const EYES_LOOKS = ["Normal", "Left", "Right", "Up", "Down", "Divergent"];

export default function EyesPanel({ editable = false, sessionCode }) {
  const eyesState = useMonitorStore((s) => s.eyes_state);
  const eyesLook = useMonitorStore((s) => s.eyes_look);

  const handleChange = (field, value) => {
    if (!editable) return;
    socket.emit("update_eyes", {
      session_code: sessionCode,
      eyes_state: field === "eyes_state" ? value : eyesState,
      eyes_look: field === "eyes_look" ? value : eyesLook,
    });
  };

  return (
    <div className="eyes-panel">
      <div className="eyes-panel-title">EYES</div>
      <div className="eyes-controls">
        <div className="eyes-group">
          <label className="eyes-label">State</label>
          {editable ? (
            <select
              className="eyes-select"
              value={eyesState}
              onChange={(e) => handleChange("eyes_state", e.target.value)}
            >
              {EYES_STATES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          ) : (
            <span className="eyes-value">{eyesState}</span>
          )}
        </div>
        <div className="eyes-group">
          <label className="eyes-label">Look</label>
          {editable ? (
            <select
              className="eyes-select"
              value={eyesLook}
              onChange={(e) => handleChange("eyes_look", e.target.value)}
            >
              {EYES_LOOKS.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          ) : (
            <span className="eyes-value">{eyesLook}</span>
          )}
        </div>
      </div>
    </div>
  );
}
