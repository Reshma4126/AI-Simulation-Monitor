// src/components/monitor/VitalsPanel.tsx
// Displays HR, rhythm, severity badge, and alarm indicator.

import { useECGStore } from "../../store/ecgStore";
import { RHYTHM_LABELS } from "../../types/ecgState";
import type { RhythmType } from "../../types/ecgState";
import "./VitalsPanel.css";

export default function VitalsPanel() {
  const heartRate = useECGStore((s) => s.liveHeartRate);
  const severity  = useECGStore((s) => s.severity);
  const rhythm    = useECGStore((s) => s.rhythm);
  const connected = useECGStore((s) => s.connected);
  const spo2      = useECGStore((s) => s.liveSpo2);
  const sysBP     = useECGStore((s) => s.liveSysBP);
  const diaBP     = useECGStore((s) => s.liveDiaBP);
  const papSys    = useECGStore((s) => s.livePapSys);
  const papDia    = useECGStore((s) => s.livePapDia);
  const etco2     = useECGStore((s) => s.liveEtco2);
  const respRate  = useECGStore((s) => s.liveRespRate);

  const label = RHYTHM_LABELS[rhythm as RhythmType] ?? rhythm;
  const hasPerfusingPulse = heartRate > 0 && !["ASYSTOLE", "VF", "PEA"].includes(rhythm);
  const spo2Alarm = !hasPerfusingPulse || spo2 < 90
    ? "critical"
    : spo2 < 95
      ? "warning"
      : "normal";

  return (
    <div className="vitals-panel">
      <div className="vitals-panel__status">
        <span className={`conn-dot conn-dot--${connected ? "on" : "off"}`} />
        <span className="conn-label">{connected ? "LIVE" : "OFFLINE"}</span>
      </div>

      <div className="vitals-panel__hr">
        <div className="vitals-panel__hr-label">HR</div>
        <div className={`vitals-panel__hr-value vitals-panel__hr-value--${severity}`}>
          {heartRate}
        </div>
        <div className="vitals-panel__hr-unit">bpm</div>
      </div>

      <div className="vitals-panel__rhythm">
        <span className={`badge badge--${severity}`}>
          {severity.toUpperCase()}
        </span>
        <span className="vitals-panel__rhythm-name">{label}</span>
      </div>

      <div className="vitals-panel__spo2">
        <div className="vitals-panel__hr-label" style={{color: "rgba(0, 255, 255, 0.8)"}}>SpO2</div>
        <div className={`vitals-panel__hr-value vitals-panel__hr-value--${spo2Alarm}`} style={{color: spo2Alarm === "normal" ? "#00ffff" : undefined}}>
          {hasPerfusingPulse ? spo2 : "---"}
        </div>
        <div className="vitals-panel__hr-unit" style={{color: "rgba(0, 255, 255, 0.5)"}}>{hasPerfusingPulse ? "%" : "NO PULSE"}</div>
      </div>

      <div className="vitals-panel__abp">
        <div className="vitals-panel__hr-label" style={{color: "rgba(255, 0, 0, 0.8)"}}>ABP</div>
        <div className="vitals-panel__hr-value" style={{color: "#ff0000", fontSize: '28px', whiteSpace: 'nowrap'}}>
          {sysBP} / {diaBP}
        </div>
        <div className="vitals-panel__hr-unit" style={{color: "rgba(255, 0, 0, 0.5)"}}>mmHg</div>
      </div>

      <div className="vitals-panel__pap">
        <div className="vitals-panel__hr-label vitals-panel__label--pap">PAP</div>
        <div className="vitals-panel__pressure vitals-panel__pressure--pap">
          {papSys} / {papDia}
        </div>
        <div className="vitals-panel__hr-unit">mmHg</div>
      </div>

      <div className="vitals-panel__etco2">
        <div className="vitals-panel__hr-label">EtCO2 / RR</div>
        <div className="vitals-panel__pressure">{etco2} / {respRate}</div>
        <div className="vitals-panel__hr-unit">mmHg / min</div>
      </div>
    </div>
  );
}
