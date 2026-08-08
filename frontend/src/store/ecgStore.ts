// src/store/ecgStore.ts
// Zustand store — mirrors ECGState from backend + manages sample ring buffer.

import { create } from "zustand";
import type { ECGState, ECGStateUpdate, LeadName, Severity, TransferFn, RhythmProfile } from "../types/ecgState";
import type { DecodedPacket, ECGIntelligenceMsg } from "../types/wsProtocol";
import { SAMPLE_RATE } from "../types/wsProtocol";
import { RHYTHM_SEVERITY, RHYTHM_INTELLIGENCE } from "../types/ecgState";

/** Ring buffer holding 10 seconds of samples per lead */
const BUFFER_SECONDS = 10;
const BUFFER_SIZE    = SAMPLE_RATE * BUFFER_SECONDS;  // 5120

function makeLeadBuffer(): Record<LeadName, Float32Array> {
  const leads: Partial<Record<LeadName, Float32Array>> = {};
  for (const l of [
    "I","II","III","aVR","aVL","aVF","V1","V2","V3","V4","V5","V6",
    "PLETH","ABP","PAP","ETCO2",
  ] as LeadName[]) {
    leads[l] = new Float32Array(BUFFER_SIZE);
  }
  return leads as Record<LeadName, Float32Array>;
}

export interface ECGStore {
  // Live state
  ecgState:     ECGState | null;
  heartRate:    number; // instructor target
  liveHeartRate: number; // value currently emitted by the engine
  spo2:         number;
  liveSpo2:     number;
  sysBP:        number;
  liveSysBP:    number;
  diaBP:        number;
  liveDiaBP:    number;
  papSys:       number;
  livePapSys:   number;
  papDia:       number;
  livePapDia:   number;
  etco2:        number;
  liveEtco2:    number;
  respRate:     number;
  liveRespRate: number;
  severity:     Severity;
  rhythm:       string;
  transferTime: number;
  transferFn:   TransferFn;
  connected:    boolean;

  // Rhythm Intelligence
  rhythmIntelligence: RhythmProfile | null;

  // Sample ring buffers (written by WS, read by canvas renderer)
  buffer:       Record<LeadName, Float32Array>;
  bufferHead:   number;     // next write index (wraps at BUFFER_SIZE)

  // Trend data (last 60 HR points)
  hrTrend:      number[];

  // Actions
  onPacket:       (pkt: DecodedPacket) => void;
  onState:        (state: ECGState) => void;
  onIntelligence: (payload: ECGIntelligenceMsg["payload"]) => void;
  setConnected:   (v: boolean) => void;
  sendCommand:    (update: ECGStateUpdate) => void;   // set by wsClient

  // WS send reference (set by wsClient)
  _sendFn:      ((update: ECGStateUpdate) => void) | null;
  _setSendFn:   (fn: (update: ECGStateUpdate) => void) => void;
}

export const useECGStore = create<ECGStore>((set, get) => ({
  ecgState:   null,
  heartRate:  80,
  liveHeartRate: 80,
  spo2:       98,
  liveSpo2:   98,
  sysBP:      120,
  liveSysBP:  120,
  diaBP:      80,
  liveDiaBP:  80,
  papSys:     25,
  livePapSys: 25,
  papDia:     10,
  livePapDia: 10,
  etco2:      38,
  liveEtco2:  38,
  respRate:   12,
  liveRespRate: 12,
  severity:   "normal",
  rhythm:     "NSR",
  transferTime: 5,
  transferFn:   "SIGMOID",
  connected:  false,
  rhythmIntelligence: RHYTHM_INTELLIGENCE["NSR"] ?? null,
  buffer:     makeLeadBuffer(),
  bufferHead: 0,
  hrTrend:    [],
  _sendFn:    null,

  onPacket: (pkt) => {
    const store = get();
    const head  = store.bufferHead;
    const n     = pkt.nSamples;

    // Write samples into ring buffer
    for (const [lead, arr] of Object.entries(pkt.leads) as [LeadName, Float32Array][]) {
      const buf = store.buffer[lead];
      if (!buf) continue;
      const end = head + n;
      if (end <= BUFFER_SIZE) {
        buf.set(arr, head);
      } else {
        const first = BUFFER_SIZE - head;
        buf.set(arr.subarray(0, first), head);
        buf.set(arr.subarray(first), 0);
      }
    }

    const newHead = (head + n) % BUFFER_SIZE;
    const severityMap: Severity[] = ["normal", "warning", "critical"];

    set((s) => ({
      bufferHead: newHead,
      liveHeartRate: Math.round(pkt.heartRate),
      liveSpo2:   Math.round(pkt.spo2),
      liveSysBP:  Math.round(pkt.sysBP),
      liveDiaBP:  Math.round(pkt.diaBP),
      livePapSys: Math.round(pkt.papSys),
      livePapDia: Math.round(pkt.papDia),
      liveEtco2: Math.round(pkt.etco2),
      liveRespRate: Math.round(pkt.respRate),
      severity:   severityMap[pkt.severity] ?? "normal",
      rhythm:     pkt.rhythm,
      hrTrend:    [...s.hrTrend.slice(-59), Math.round(pkt.heartRate)],
    }));
  },

  onState: (state) => {
    console.log("[STORE] onState:", {
      heartRate: Math.round(state.heart_rate),
      rhythm: state.rhythm,
      transferTime: state.transfer_time,
      transferFn: state.transfer_fn,
    });
    set(() => ({
      ecgState: state,
      heartRate: Math.round(state.heart_rate ?? 80),
      liveHeartRate: Math.round(state.heart_rate ?? 80),
      spo2: Math.round(state.spo2 ?? 98),
      liveSpo2: Math.round(state.spo2 ?? 98),
      sysBP: Math.round(state.sys_bp ?? 120),
      liveSysBP: Math.round(state.sys_bp ?? 120),
      diaBP: Math.round(state.dia_bp ?? 80),
      liveDiaBP: Math.round(state.dia_bp ?? 80),
      papSys: Math.round(state.pap_sys ?? 25),
      livePapSys: Math.round(state.pap_sys ?? 25),
      papDia: Math.round(state.pap_dia ?? 10),
      livePapDia: Math.round(state.pap_dia ?? 10),
      etco2: Math.round(state.etco2 ?? 38),
      liveEtco2: Math.round(state.etco2 ?? 38),
      respRate: Math.round(state.resp_rate ?? 12),
      liveRespRate: Math.round(state.resp_rate ?? 12),
      severity: RHYTHM_SEVERITY[state.rhythm as keyof typeof RHYTHM_SEVERITY] ?? "normal",
      rhythm:   state.rhythm,
      transferTime: state.transfer_time ?? 0,
      transferFn: state.transfer_fn ?? "IMMEDIATE",
      rhythmIntelligence: RHYTHM_INTELLIGENCE[state.rhythm as keyof typeof RHYTHM_INTELLIGENCE] ?? null,
    }));
  },

  onIntelligence: (payload) => {
    // When backend sends ECG_INTELLIGENCE, update the local intelligence state
    // The frontend static table is the primary source; the backend payload confirms the rhythm.
    const profile = RHYTHM_INTELLIGENCE[payload.rhythm as keyof typeof RHYTHM_INTELLIGENCE];
    if (profile) {
      set({ rhythmIntelligence: profile });
    }
    console.log("[STORE] onIntelligence:", payload.rhythm, payload.p_wave, payload.t_wave);
  },

  setConnected: (v) => set({ connected: v }),

  sendCommand: (update) => {
    const fn = get()._sendFn;
    console.log("[STORE] sendCommand called. _sendFn is:", !!fn, update);
    if (fn) fn(update);

    const currentState = get().ecgState;
    set(() => ({
      heartRate: update.heart_rate !== undefined ? Math.round(update.heart_rate) : get().heartRate,
      spo2: update.spo2 !== undefined ? Math.round(update.spo2) : get().spo2,
      sysBP: update.sys_bp !== undefined ? Math.round(update.sys_bp) : get().sysBP,
      diaBP: update.dia_bp !== undefined ? Math.round(update.dia_bp) : get().diaBP,
      papSys: update.pap_sys !== undefined ? Math.round(update.pap_sys) : get().papSys,
      papDia: update.pap_dia !== undefined ? Math.round(update.pap_dia) : get().papDia,
      etco2: update.etco2 !== undefined ? Math.round(update.etco2) : get().etco2,
      respRate: update.resp_rate !== undefined ? Math.round(update.resp_rate) : get().respRate,
      rhythm: update.rhythm ?? get().rhythm,
      transferTime: update.transfer_time ?? get().transferTime,
      transferFn: update.transfer_fn ?? get().transferFn,
      severity: update.rhythm
        ? RHYTHM_SEVERITY[update.rhythm as keyof typeof RHYTHM_SEVERITY] ?? get().severity
        : get().severity,
      ecgState: currentState ? { ...currentState, ...update } : currentState,
      // Eagerly update rhythm intelligence when rhythm changes
      rhythmIntelligence: update.rhythm
        ? RHYTHM_INTELLIGENCE[update.rhythm as keyof typeof RHYTHM_INTELLIGENCE] ?? get().rhythmIntelligence
        : get().rhythmIntelligence,
    }));
  },

  sendCommand: (update) => {
    const fn = get()._sendFn;
    if (fn) fn(update);
  },
  _setSendFn: (fn) => set({ _sendFn: fn }),
}));

