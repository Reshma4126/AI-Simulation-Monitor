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
    <div className="alarm-bar" style={{ display: "flex", gap: "6px", padding: "4px 8px", backgroundColor: "#1E0000", borderBottom: "1px solid #380000", alignItems: "center", zIndex: 10 }}>
      {alarms.map((alarm, i) => (
        <div
          key={`${alarm}-${i}`}
          className="alarm-badge"
          style={{
            ...getAlarmStyle(alarm),
            fontSize: "11px",
            fontWeight: "700",
            padding: "2px 8px",
            borderRadius: "4px",
            display: "flex",
            alignItems: "center",
            gap: "4px"
          }}
        >
          <span>⚠️</span> {alarm.replace("_sys", " sys").replace("_dia", " dia")}
        </div>
      ))}
    </div>
  );
}
