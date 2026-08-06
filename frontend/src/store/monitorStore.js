import { create } from "zustand";

const useMonitorStore = create((set, get) => ({
  // Full state from server (replaced on every state_update)
  HR: 80,
  pulse_rate: 80,
  rhythm: "Sinus Rhythm",
  extrasystole: "None",
  ecg_lead: "II",
  artifact_electrical: "Off",
  artifact_muscular: "Off",
  emd_pea: false,

  ABP_sys: 120,
  ABP_dia: 80,
  MAP: 93,
  NBP_sys: 120,
  NBP_dia: 80,
  NBP_mean: 93,
  coupled_bp: false,

  PAP_sys: 20,
  PAP_dia: 10,
  PAP_mean: 13,
  PAP_wedge: 10,
  CO: 5.0,

  avRR: 14,
  SpO2: 98,
  etCO2: 35,
  inCO2: 0,
  etO2: 21,
  inO2: 21,
  etN2O: 0,
  inN2O: 0,
  cyanosis_start: 90,
  cyanosis_severe: 70,

  Tperi: 37.0,
  Tblood: 37.0,

  TOF_pct: 100,
  TOF_count: 4,

  eyes_state: "Closed",
  eyes_look: "Normal",

  // Meta
  alarms: [],
  alarm_thresholds: {},
  started_at: null,
  last_updated: null,
  updated_by: "",
  initial_readings_hidden: false,

  // Event log (appended via session_event)
  eventLog: [],

  // Session ended flag
  sessionEnded: false,

  // Actions
  setFullState: (state) => {
    // Filter out MongoDB internal fields
    const { _id, session_id, ...clean } = state;
    set(clean);
  },
  // Optimistic local update — called immediately when instructor changes a param
  updateParam: (field, value) => set({ [field]: value }),
  appendEvent: (entry) =>
    set((s) => ({ eventLog: [...s.eventLog, entry] })),
  setSessionEnded: () => set({ sessionEnded: true }),
  resetStore: () => set({ sessionEnded: false, eventLog: [] }),
}));

export default useMonitorStore;
