// src/types/ecgState.ts
// Central TypeScript types mirroring the Python ECGState model.

export type RhythmType =
  | "NSR" | "SINUS_BRADY" | "SINUS_TACHY"
  | "AFIB" | "AFLUTTER" | "JUNCTIONAL"
  | "AVB1" | "AVB2_I" | "AVB2_II" | "AVB3"
  | "PAC" | "PVC" | "SVT"
  | "VT" | "VF" | "TORSADES"
  | "ASYSTOLE" | "PEA"
  | "LBBB" | "RBBB"
  | "ANT_STEMI" | "INF_STEMI" | "LAT_STEMI";

export type IschemiaZone   = "NONE" | "ANTERIOR" | "INFERIOR" | "LATERAL";
export type ArtifactType   = "NONE" | "BASELINE" | "POWERLINE_50" | "POWERLINE_60" | "MOTION" | "EMG";
export type TransferFn     = "IMMEDIATE" | "LINEAR" | "EXPONENTIAL" | "SIGMOID";
export type LeadName       = "I" | "II" | "III" | "aVR" | "aVL" | "aVF" | "V1" | "V2" | "V3" | "V4" | "V5" | "V6" | "PLETH" | "ABP" | "PAP" | "ETCO2";
export type Severity       = "normal" | "warning" | "critical";

export interface ECGState {
  session_id:       string;
  rhythm:           RhythmType;
  heart_rate:       number;
  spo2:             number;
  sys_bp:           number;
  dia_bp:           number;
  pap_sys:          number;
  pap_dia:          number;
  etco2:            number;
  resp_rate:        number;
  hrv_std:          number;
  pr_interval:      number;
  qrs_duration:     number;
  qt_interval:      number;
  st_elevation:     number;
  st_depression:    number;
  st_slope:         number;
  ischemia_zone:    IschemiaZone;
  conduction_state: string;
  ectopy_rate:      number;
  artifact_level:   number;
  artifact_type:    ArtifactType;
  transfer_time:    number;
  transfer_fn:      TransferFn;
  lead_selection:   LeadName;
  gain:             number;
  paper_speed:      number;
}

export type ECGStateUpdate = Partial<Omit<ECGState, "session_id">>;

// ─── Rhythm metadata ──────────────────────────────────────────────────────────

export const RHYTHM_LABELS: Record<RhythmType, string> = {
  NSR:         "Normal Sinus Rhythm",
  SINUS_BRADY: "Sinus Bradycardia",
  SINUS_TACHY: "Sinus Tachycardia",
  AFIB:        "Atrial Fibrillation",
  AFLUTTER:    "Atrial Flutter",
  JUNCTIONAL:  "Junctional Rhythm",
  AVB1:        "1st Degree AV Block",
  AVB2_I:      "2nd Degree AV Block – Mobitz I",
  AVB2_II:     "2nd Degree AV Block – Mobitz II",
  AVB3:        "3rd Degree AV Block (Complete)",
  PAC:         "Premature Atrial Contractions",
  PVC:         "Premature Ventricular Contractions",
  SVT:         "Supraventricular Tachycardia",
  VT:          "Ventricular Tachycardia",
  VF:          "Ventricular Fibrillation",
  TORSADES:    "Torsades de Pointes",
  ASYSTOLE:    "Asystole",
  PEA:         "Pulseless Electrical Activity",
  LBBB:        "Left Bundle Branch Block",
  RBBB:        "Right Bundle Branch Block",
  ANT_STEMI:   "Anterior STEMI",
  INF_STEMI:   "Inferior STEMI",
  LAT_STEMI:   "Lateral STEMI",
};

export const RHYTHM_SEVERITY: Record<RhythmType, Severity> = {
  NSR: "normal", SINUS_BRADY: "warning", SINUS_TACHY: "warning",
  AFIB: "warning", AFLUTTER: "warning", JUNCTIONAL: "warning",
  AVB1: "warning", AVB2_I: "warning", AVB2_II: "critical", AVB3: "critical",
  PAC: "warning", PVC: "warning", SVT: "critical",
  VT: "critical", VF: "critical", TORSADES: "critical",
  ASYSTOLE: "critical", PEA: "critical",
  LBBB: "warning", RBBB: "warning",
  ANT_STEMI: "critical", INF_STEMI: "critical", LAT_STEMI: "critical",
};

export const RHYTHM_GROUPS: { label: string; rhythms: RhythmType[] }[] = [
  { label: "Sinus Rhythms",     rhythms: ["NSR", "SINUS_BRADY", "SINUS_TACHY"] },
  { label: "Atrial",            rhythms: ["AFIB", "AFLUTTER", "JUNCTIONAL", "PAC", "SVT"] },
  { label: "AV Conduction",     rhythms: ["AVB1", "AVB2_I", "AVB2_II", "AVB3"] },
  { label: "Ventricular",       rhythms: ["PVC", "VT", "VF", "TORSADES"] },
  { label: "Arrest / PEA",      rhythms: ["ASYSTOLE", "PEA"] },
  { label: "Bundle Branch",     rhythms: ["LBBB", "RBBB"] },
  { label: "ST Elevation / MI", rhythms: ["ANT_STEMI", "INF_STEMI", "LAT_STEMI"] },
];

export const ALL_LEADS: LeadName[] = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6", "PLETH", "ABP", "PAP", "ETCO2"];

// ─── Rhythm Intelligence ───────────────────────────────────────────────────────

export interface RhythmProfile {
  hrMin:          number;
  hrMax:          number;
  defaultHr:      number;
  pWave:          "present" | "absent" | "retrograde" | "fibrillatory" | "flutter" | "dissociated";
  tWave:          "present" | "suppressed" | "discordant" | "absent";
  qrsType:        "narrow" | "wide" | "bizarre" | "sinusoidal" | "chaotic" | "escape";
  morphologyDesc: string;
  conditionDesc:  string;
}

export const RHYTHM_INTELLIGENCE: Record<RhythmType, RhythmProfile> = {
  NSR:         { hrMin:60,  hrMax:100, defaultHr:75,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"Normal P-QRS-T morphology, regular rhythm",                                 conditionDesc:"Normal Sinus Rhythm — physiologically normal conduction" },
  SINUS_BRADY: { hrMin:20,  hrMax:59,  defaultHr:50,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"Tall distinct P waves, pronounced T waves, slow regular rhythm",              conditionDesc:"Sinus Bradycardia — slow SA node discharge; may cause hemodynamic compromise" },
  SINUS_TACHY: { hrMin:101, hrMax:180, defaultHr:120, pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"P waves may merge with preceding T at very high rates",                       conditionDesc:"Sinus Tachycardia — physiologic response to stress, pain, fever, hypovolemia" },
  AFIB:        { hrMin:30,  hrMax:180, defaultHr:70,  pWave:"fibrillatory", tWave:"present",    qrsType:"narrow",   morphologyDesc:"No organised P waves; irregular baseline flutter; irregularly irregular RR",   conditionDesc:"Atrial Fibrillation — chaotic atrial activity, irregularly irregular ventricular response" },
  AFLUTTER:    { hrMin:70,  hrMax:180, defaultHr:150, pWave:"flutter",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"Sawtooth flutter waves ~300 bpm; ventricular rate typically 150 (2:1 block)",   conditionDesc:"Atrial Flutter — organised atrial tachycardia with characteristic flutter waves" },
  JUNCTIONAL:  { hrMin:40,  hrMax:60,  defaultHr:50,  pWave:"retrograde",   tWave:"present",    qrsType:"narrow",   morphologyDesc:"Retrograde inverted P wave immediately preceding QRS complex",                 conditionDesc:"Junctional Rhythm — AV node pacemaker; SA node suppressed" },
  AVB1:        { hrMin:40,  hrMax:100, defaultHr:60,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"Prolonged PR interval (>200ms); all P waves conduct",                        conditionDesc:"1st Degree AV Block — delayed conduction through AV node; benign" },
  AVB2_I:      { hrMin:40,  hrMax:90,  defaultHr:50,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"Progressive PR lengthening then dropped QRS (Wenckebach pattern)",             conditionDesc:"2nd Degree AV Block (Mobitz I) — Wenckebach pattern; usually benign" },
  AVB2_II:     { hrMin:30,  hrMax:80,  defaultHr:50,  pWave:"present",      tWave:"present",    qrsType:"wide",     morphologyDesc:"Fixed PR with intermittent non-conducted P waves; may have wide QRS",          conditionDesc:"2nd Degree AV Block (Mobitz II) — high risk of progression to complete block" },
  AVB3:        { hrMin:20,  hrMax:50,  defaultHr:35,  pWave:"dissociated",  tWave:"present",    qrsType:"escape",   morphologyDesc:"P waves completely dissociated from ventricular escape rhythm",                conditionDesc:"3rd Degree (Complete) AV Block — no atrial-ventricular conduction; requires pacing" },
  PAC:         { hrMin:50,  hrMax:110, defaultHr:95,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"Premature ectopic P waves with brief compensatory pause",                     conditionDesc:"Premature Atrial Contractions — early atrial depolarisations; usually benign" },
  PVC:         { hrMin:50,  hrMax:100, defaultHr:75,  pWave:"present",      tWave:"discordant", qrsType:"bizarre",  morphologyDesc:"Every 4th beat: wide bizarre QRS, no P, discordant T; compensatory pause",    conditionDesc:"Premature Ventricular Contractions — ectopic ventricular depolarisation" },
  SVT:         { hrMin:150, hrMax:250, defaultHr:156, pWave:"absent",       tWave:"suppressed", qrsType:"narrow",   morphologyDesc:"Very rapid narrow complexes; P waves buried in T or absent",                  conditionDesc:"Supraventricular Tachycardia — re-entrant circuit above His bundle" },
  VT:          { hrMin:120, hrMax:280, defaultHr:180, pWave:"absent",       tWave:"discordant", qrsType:"wide",     morphologyDesc:"Wide bizarre repetitive QRS; no P waves; discordant T waves",                  conditionDesc:"Ventricular Tachycardia — sustained ventricular origin; hemodynamically unstable" },
  VF:          { hrMin:0,   hrMax:0,   defaultHr:0,   pWave:"absent",       tWave:"absent",     qrsType:"chaotic",  morphologyDesc:"Chaotic irregular oscillations; no recognisable waveforms",                   conditionDesc:"Ventricular Fibrillation — cardiac arrest; immediate defibrillation required" },
  TORSADES:    { hrMin:150, hrMax:280, defaultHr:220, pWave:"absent",       tWave:"absent",     qrsType:"bizarre",  morphologyDesc:"Twisting QRS axis (sinusoidal envelope); no P or T waves",                   conditionDesc:"Torsades de Pointes — polymorphic VT associated with long QT interval" },
  ASYSTOLE:    { hrMin:0,   hrMax:0,   defaultHr:0,   pWave:"absent",       tWave:"absent",     qrsType:"chaotic",  morphologyDesc:"Flat isoelectric line; no cardiac electrical activity",                      conditionDesc:"Asystole — cardiac arrest; CPR + epinephrine immediately" },
  PEA:         { hrMin:20,  hrMax:80,  defaultHr:60,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"Low-voltage organised electrical activity; no mechanical output",              conditionDesc:"Pulseless Electrical Activity — organised ECG with no effective cardiac output" },
  LBBB:        { hrMin:50,  hrMax:100, defaultHr:60,  pWave:"present",      tWave:"discordant", qrsType:"wide",     morphologyDesc:"Broad notched R in lateral leads; discordant T waves; QRS >120ms",            conditionDesc:"Left Bundle Branch Block — delayed left ventricular activation" },
  RBBB:        { hrMin:50,  hrMax:100, defaultHr:60,  pWave:"present",      tWave:"present",    qrsType:"wide",     morphologyDesc:"RSR' pattern in V1; wide S wave in lateral leads; QRS >120ms",               conditionDesc:"Right Bundle Branch Block — delayed right ventricular activation" },
  ANT_STEMI:   { hrMin:50,  hrMax:110, defaultHr:60,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"ST elevation V1–V4; reciprocal depression II/III/aVF; hyperacute T waves",    conditionDesc:"Anterior STEMI — left anterior descending (LAD) artery occlusion" },
  INF_STEMI:   { hrMin:40,  hrMax:100, defaultHr:60,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"ST elevation II/III/aVF; reciprocal ST depression I/aVL",                    conditionDesc:"Inferior STEMI — right coronary artery (RCA) or circumflex occlusion" },
  LAT_STEMI:   { hrMin:50,  hrMax:100, defaultHr:60,  pWave:"present",      tWave:"present",    qrsType:"narrow",   morphologyDesc:"ST elevation I/aVL/V5–V6; reciprocal depression V1/III",                    conditionDesc:"Lateral STEMI — circumflex or diagonal branch occlusion" },
};

/** Compute effective P-wave and T-wave visibility factors based on rhythm + HR (mirrors backend logic) */
export function getWaveVisibility(rhythm: RhythmType, heartRate: number): { pFactor: number; tFactor: number } {
  const profile = RHYTHM_INTELLIGENCE[rhythm];
  if (!profile) return { pFactor: 1, tFactor: 1 };

  let pBase = profile.pWave === "absent" || profile.pWave === "fibrillatory" ? 0 : 1;
  let tBase = profile.tWave === "absent" ? 0 : 1;
  if (profile.qrsType === "chaotic") return { pFactor: 0, tFactor: 0 };

  let pRate = 1, tRate = 1;
  const hr = heartRate;
  if (hr < 150)       { pRate = 1;                              tRate = 1; }
  else if (hr < 180)  { pRate = 1;                              tRate = Math.max(0, 1 - (hr - 150) / 30); }
  else if (hr < 220)  { pRate = Math.max(0, 1 - (hr - 180) / 40); tRate = 0; }
  else                { pRate = 0;                              tRate = 0; }

  return { pFactor: pBase * pRate, tFactor: tBase * tRate };
}

/** Get a human-readable wave status string */
export function getWaveStatusLabel(factor: number, baseStatus: string): string {
  if (factor <= 0)    return "Absent";
  if (factor < 0.4)   return "Suppressed";
  if (factor < 0.85)  return "Reduced";
  return baseStatus === "present" ? "Present" : baseStatus.charAt(0).toUpperCase() + baseStatus.slice(1);
}

