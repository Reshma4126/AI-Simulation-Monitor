// src/components/monitor/ECGAnalysisPanel.tsx
// ECG Intelligence Panel — shows live rhythm analysis, wave status, and clinical context.
// Reads from Zustand store; no props required for basic usage.

import { useECGStore } from "../../store/ecgStore";
import {
  RHYTHM_LABELS,
  RHYTHM_INTELLIGENCE,
  type RhythmType,
  type RhythmProfile,
} from "../../types/ecgState";
import "./ECGAnalysisPanel.css";

interface Props {
  compact?: boolean;  // compact mode for PatientMonitor overlay
}

// ── Severity colour tokens ───────────────────────────────────────────────────
const SEV_CLASS = { normal: "sev--normal", warning: "sev--warning", critical: "sev--critical" };
const SEV_LABEL = { normal: "NORMAL", warning: "WARNING", critical: "CRITICAL" };

// ── QRS badge colours ────────────────────────────────────────────────────────
const QRS_CLASS: Record<string, string> = {
  narrow:     "qrs--narrow",
  wide:       "qrs--wide",
  bizarre:    "qrs--bizarre",
  sinusoidal: "qrs--sinusoidal",
  chaotic:    "qrs--chaotic",
  escape:     "qrs--escape",
};

// ── Wave detail types ────────────────────────────────────────────────────────
interface WaveDetail {
  status:     string;
  statusCls:  string;
  rangeLabel: string;
  rangeValue: string;
}

/**
 * Compute rich wave visibility detail for P or T wave.
 *
 * Priority:
 *   1. Rhythm-level suppression → "Not Expected For Rhythm"
 *   2. Special labels (retrograde, fibrillatory, flutter, dissociated, discordant)
 *   3. Rate-based suppression ranges (mirrors backend get_wave_visibility logic)
 */
function getPWaveDetail(profile: RhythmProfile, hr: number): WaveDetail {
  // Rhythm-suppressed
  if (profile.pWave === "absent") {
    return { status: "Absent", statusCls: "wave--absent",
             rangeLabel: "Not Expected For Rhythm", rangeValue: "" };
  }
  if (profile.pWave === "fibrillatory") {
    return { status: "Fibrillatory", statusCls: "wave--suppressed",
             rangeLabel: "No Organised P Waves", rangeValue: "" };
  }
  if (profile.pWave === "retrograde") {
    return { status: "Retrograde", statusCls: "wave--reduced",
             rangeLabel: "Inverted · Post-QRS", rangeValue: "" };
  }
  if (profile.pWave === "flutter") {
    return { status: "Flutter Waves", statusCls: "wave--reduced",
             rangeLabel: "Sawtooth Pattern ~300 bpm", rangeValue: "" };
  }
  if (profile.pWave === "dissociated") {
    return { status: "Dissociated", statusCls: "wave--reduced",
             rangeLabel: "Independent Atrial Rate", rangeValue: "" };
  }

  // Rate-based suppression (P: present <180, transition 180-220, absent ≥220)
  if (hr < 180) {
    return { status: "Present", statusCls: "wave--present",
             rangeLabel: "Visible Range", rangeValue: "0–180 bpm" };
  }
  if (hr < 220) {
    return { status: "Partially Hidden", statusCls: "wave--reduced",
             rangeLabel: "Transition Range", rangeValue: "180–220 bpm" };
  }
  return { status: "Absent", statusCls: "wave--absent",
           rangeLabel: "Absent Above", rangeValue: "220 bpm" };
}

function getTWaveDetail(profile: RhythmProfile, hr: number): WaveDetail {
  // Rhythm-suppressed
  if (profile.tWave === "absent") {
    return { status: "Absent", statusCls: "wave--absent",
             rangeLabel: "Not Expected For Rhythm", rangeValue: "" };
  }
  if (profile.tWave === "discordant") {
    // Discordant T is always present but opposite polarity — rate rules still apply
    if (hr < 150) {
      return { status: "Discordant", statusCls: "wave--reduced",
               rangeLabel: "Opposite to QRS · Visible Range", rangeValue: "0–150 bpm" };
    }
    if (hr < 180) {
      return { status: "Discordant · Fading", statusCls: "wave--suppressed",
               rangeLabel: "Transition Range", rangeValue: "150–180 bpm" };
    }
    return { status: "Absent", statusCls: "wave--absent",
             rangeLabel: "Absent Above", rangeValue: "150 bpm" };
  }
  if (profile.tWave === "suppressed") {
    return { status: "Suppressed", statusCls: "wave--suppressed",
             rangeLabel: "Rate-Related Suppression", rangeValue: "" };
  }

  // Rate-based suppression (T: present <150, transition 150-180, absent ≥180)
  if (hr < 150) {
    return { status: "Present", statusCls: "wave--present",
             rangeLabel: "Visible Range", rangeValue: "0–150 bpm" };
  }
  if (hr < 180) {
    return { status: "Partially Hidden", statusCls: "wave--reduced",
             rangeLabel: "Transition Range", rangeValue: "150–180 bpm" };
  }
  return { status: "Absent", statusCls: "wave--absent",
           rangeLabel: "Absent Above", rangeValue: "150 bpm" };
}

// ── Full wave detail block ────────────────────────────────────────────────────
function WaveBlock({ title, detail }: { title: string; detail: WaveDetail }) {
  return (
    <div className="eap-wave-block">
      <div className="eap-wave-block__header">
        <span className="eap-wave-label">{title}</span>
        <span className={`eap-wave-badge ${detail.statusCls}`}>{detail.status}</span>
      </div>
      {detail.rangeLabel && (
        <div className="eap-wave-block__range">
          <span className="eap-range-label">{detail.rangeLabel}</span>
          {detail.rangeValue && (
            <span className="eap-range-value">{detail.rangeValue}</span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Compact wave row (no range detail) ────────────────────────────────────────
function CompactWaveRow({ title, detail }: { title: string; detail: WaveDetail }) {
  return (
    <div className="eap-compact-row">
      <span className="eap-label">{title}</span>
      <div className="eap-compact-wave">
        <span className={`eap-wave-badge ${detail.statusCls}`}>{detail.status}</span>
        {detail.rangeValue && (
          <span className="eap-compact-range">{detail.rangeValue}</span>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ECGAnalysisPanel({ compact = false }: Props) {
  const rhythm        = useECGStore((s) => s.rhythm) as RhythmType;
  const liveHeartRate = useECGStore((s) => s.liveHeartRate);
  const heartRate     = useECGStore((s) => s.heartRate);
  const severity      = useECGStore((s) => s.severity);
  const rhythmProfile = useECGStore((s) => s.rhythmIntelligence);

  const profile = rhythmProfile ?? RHYTHM_INTELLIGENCE[rhythm];
  if (!profile) return null;

  const hr           = liveHeartRate || heartRate;
  const pDetail      = getPWaveDetail(profile, hr);
  const tDetail      = getTWaveDetail(profile, hr);
  const rhythmLabel  = RHYTHM_LABELS[rhythm] ?? rhythm;
  const sevClass     = SEV_CLASS[severity];
  const sevLabel     = SEV_LABEL[severity];
  const qrsCls       = QRS_CLASS[profile.qrsType] ?? "qrs--narrow";
  const qrsLabel     = profile.qrsType.charAt(0).toUpperCase() + profile.qrsType.slice(1) + " Complex";
  const hrRangeStr   = profile.hrMax === 0 ? "0 bpm" : `${profile.hrMin}–${profile.hrMax} bpm`;

  // ── Compact mode ─────────────────────────────────────────────────────────
  if (compact) {
    return (
      <div className="eap eap--compact">
        <div className="eap-compact-row">
          <span className="eap-label">RHYTHM</span>
          <span className="eap-val">{rhythmLabel}</span>
        </div>
        <CompactWaveRow title="P WAVE" detail={pDetail} />
        <CompactWaveRow title="T WAVE" detail={tDetail} />
        <div className="eap-compact-row">
          <span className="eap-label">QRS</span>
          <span className={`eap-qrs-badge ${qrsCls}`}>{qrsLabel}</span>
        </div>
        <div className={`eap-alarm ${sevClass}`}>{sevLabel}</div>
      </div>
    );
  }

  // ── Full mode ─────────────────────────────────────────────────────────────
  return (
    <div className="eap">
      {/* Header */}
      <div className="eap-header">
        <span className="eap-header__icon">⚕</span>
        <span className="eap-header__title">ECG ANALYSIS</span>
        <span className={`eap-alarm ${sevClass}`}>{sevLabel}</span>
      </div>

      {/* Rhythm & HR */}
      <div className="eap-section">
        <div className="eap-row">
          <span className="eap-label">CURRENT RHYTHM</span>
          <span className="eap-val eap-val--rhythm">{rhythmLabel}</span>
        </div>
        <div className="eap-row">
          <span className="eap-label">HEART RATE</span>
          <span className={`eap-val eap-val--hr sev--${severity}`}>
            {liveHeartRate} <span className="eap-unit">bpm</span>
          </span>
        </div>
        <div className="eap-row">
          <span className="eap-label">TYPICAL HR</span>
          <span className="eap-val eap-val--dim">{hrRangeStr}</span>
        </div>
      </div>

      <div className="eap-divider" />

      {/* Waveform Status — full detail with ranges */}
      <div className="eap-section">
        <div className="eap-section-label">ECG MORPHOLOGY</div>

        <WaveBlock title="P Wave" detail={pDetail} />
        <WaveBlock title="T Wave" detail={tDetail} />

        {/* QRS */}
        <div className="eap-wave-block">
          <div className="eap-wave-block__header">
            <span className="eap-wave-label">QRS Complex</span>
            <span className={`eap-qrs-badge ${qrsCls}`}>{qrsLabel}</span>
          </div>
        </div>
      </div>

      <div className="eap-divider" />

      {/* Expected appearance */}
      <div className="eap-section">
        <div className="eap-section-label">EXPECTED APPEARANCE</div>
        <p className="eap-desc">{profile.morphologyDesc}</p>
      </div>

      <div className="eap-divider" />

      {/* Clinical context */}
      <div className="eap-section">
        <div className="eap-section-label">CLINICAL CONTEXT</div>
        <p className="eap-desc eap-desc--clinical">{profile.conditionDesc}</p>
      </div>
    </div>
  );
}
