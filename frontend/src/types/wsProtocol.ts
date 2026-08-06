// src/types/wsProtocol.ts
// WebSocket message types for the SimMan ECG stream.

import type { ECGState, ECGStateUpdate, LeadName } from "./ecgState";

export const LEAD_ORDER: LeadName[] = [
  "I","II","III","aVR","aVL","aVF","V1","V2","V3","V4","V5","V6",
  "PLETH","ABP","PAP","ETCO2",
];

export const SAMPLE_RATE = 512;   // Hz — must match backend
export const PACKET_MS   = 50;    // ms per WebSocket packet

/** Number of samples per packet sent by the server */
export const SAMPLES_PER_PKT = Math.round(SAMPLE_RATE * PACKET_MS / 1000); // 26

// ─── Binary packet layout (big-endian) ──────────────────────────────────────
//
//  [0–1]  Uint16  magic = 0xECEC
//  [2–5]  Float32 heart_rate
//  [6–9]  Float32 spo2
//  [10–13] Float32 sys_bp
//  [14–17] Float32 dia_bp
//  [18–21] Float32 pap_sys
//  [22–25] Float32 pap_dia
//  [26–29] Float32 etco2
//  [30–33] Float32 resp_rate
//  [34–35] Uint16  n_samples
//  [36–37] Uint16  n_leads (= 16)
//  For each of 16 leads (in LEAD_ORDER):
//    [n_samples × 4 bytes]  Float32 array
//  [header_end + 0]  Uint8 severity (0=normal,1=warning,2=critical)
//  [header_end + 1]  Uint8 rhythm_len
//  [header_end + 2 … ]  ASCII rhythm string

export interface DecodedPacket {
  heartRate:  number;
  spo2:       number;
  sysBP:      number;
  diaBP:      number;
  papSys:     number;
  papDia:     number;
  etco2:      number;
  respRate:   number;
  nSamples:   number;
  leads:      Record<LeadName, Float32Array>;
  severity:   0 | 1 | 2;
  rhythm:     string;
}

export function decodePacket(buffer: ArrayBuffer): DecodedPacket | null {
  const headerBytes = 38;
  if (buffer.byteLength < headerBytes + 2) return null;

  const view = new DataView(buffer);
  let offset = 0;

  const magic = view.getUint16(offset, false); offset += 2;
  if (magic !== 0xECEC) return null;

  const heartRate = view.getFloat32(offset, false); offset += 4;
  const spo2      = view.getFloat32(offset, false); offset += 4;
  const sysBP     = view.getFloat32(offset, false); offset += 4;
  const diaBP     = view.getFloat32(offset, false); offset += 4;
  const papSys    = view.getFloat32(offset, false); offset += 4;
  const papDia    = view.getFloat32(offset, false); offset += 4;
  const etco2     = view.getFloat32(offset, false); offset += 4;
  const respRate  = view.getFloat32(offset, false); offset += 4;
  const nSamples  = view.getUint16(offset, false);  offset += 2;
  const nLeads    = view.getUint16(offset, false);  offset += 2;
  const waveformBytes = nSamples * nLeads * 4;

  if (
    nSamples === 0
    || nLeads !== LEAD_ORDER.length
    || buffer.byteLength < headerBytes + waveformBytes + 2
  ) {
    return null;
  }

  const leads: Partial<Record<LeadName, Float32Array>> = {};
  for (let i = 0; i < nLeads; i++) {
    const samples = new Float32Array(nSamples);
    for (let sample = 0; sample < nSamples; sample++) {
      samples[sample] = view.getFloat32(offset, false);
      offset += 4;
    }
    leads[LEAD_ORDER[i]] = samples;
  }

  const severity  = view.getUint8(offset) as 0 | 1 | 2; offset += 1;
  const rhytLen   = view.getUint8(offset);               offset += 1;
  if (offset + rhytLen > buffer.byteLength) return null;
  const bytes     = new Uint8Array(buffer, offset, rhytLen);
  const rhythm    = new TextDecoder().decode(bytes);

  return {
    heartRate,
    spo2,
    sysBP,
    diaBP,
    papSys,
    papDia,
    etco2,
    respRate,
    nSamples,
    leads: leads as Record<LeadName, Float32Array>,
    severity,
    rhythm,
  };
}

// ─── JSON message types ───────────────────────────────────────────────────────

export interface StateSnapshotMsg {
  type:    "STATE_SNAPSHOT";
  payload: ECGState;
}

export interface SetStateMsg {
  type:    "SET_STATE";
  payload: ECGStateUpdate;
}

export interface ECGIntelligenceMsg {
  type: "ECG_INTELLIGENCE";
  payload: {
    rhythm:          string;
    p_wave:          string;
    t_wave:          string;
    qrs_type:        string;
    morphology_desc: string;
    condition_desc:  string;
    hr_min:          number;
    hr_max:          number;
    default_hr:      number;
  };
}

export interface PingMsg  { type: "PING"; }
export interface PongMsg  { type: "PONG"; }

export type ServerMsg = StateSnapshotMsg | PongMsg | ECGIntelligenceMsg;
export type ClientMsg = SetStateMsg | { type: "GET_STATE" } | PingMsg;

