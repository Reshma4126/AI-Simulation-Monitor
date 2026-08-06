import useMonitorStore from "../../store/monitorStore";

export default function AlarmBar() {
  const alarms = useMonitorStore((s) => s.alarms) || [];

  if (alarms.length === 0) return null;

  const getAlarmStyle = (alarm) => {
    if (alarm === "APNEA" || alarm === "DESAT") {
      return { backgroundColor: "#cc0000", color: "#fff" };
    }
    if (alarm === "ABPs High") {
      return { backgroundColor: "#ffcc00", color: "#000" };
    }
    return { backgroundColor: "#cc0000", color: "#fff" };
  };

  return (
    <div className="alarm-bar">
      {alarms.map((alarm, i) => (
        <div
          key={`${alarm}-${i}`}
          className="alarm-badge"
          style={getAlarmStyle(alarm)}
        >
          ⚠ {alarm}
        </div>
      ))}
    </div>
  );
}
