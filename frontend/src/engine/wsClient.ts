// src/engine/wsClient.ts
// WebSocket client with automatic reconnection and message queuing.
// Decodes binary ECG packets and routes JSON messages to the Zustand store.

import { decodePacket } from "../types/wsProtocol";
import type { ECGStateUpdate } from "../types/ecgState";
import type { ServerMsg } from "../types/wsProtocol";
import { useECGStore } from "../store/ecgStore";

function getWsUrl(): string {
  const envUrl = import.meta.env.VITE_WS_URL || import.meta.env.VITE_BACKEND_URL || "https://imsr2-a3xs.onrender.com";
  const base = envUrl.replace(/\/$/, "");
  if (base.startsWith("ws://") || base.startsWith("wss://")) {
    return `${base}/ws/ecg`;
  }
  if (base.startsWith("https://")) {
    return `${base.replace(/^https:\/\//, "wss://")}/ws/ecg`;
  }
  if (base.startsWith("http://")) {
    return `${base.replace(/^http:\/\//, "ws://")}/ws/ecg`;
  }
  return `ws://${base}/ws/ecg`;
}

const WS_URL = getWsUrl();
const RECONNECT_DELAY_MS = 2000;

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

// Message queue — accumulates messages while socket is not yet OPEN
const pendingQueue: string[] = [];

function flushQueue(): void {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  while (pendingQueue.length > 0) {
    const msg = pendingQueue.shift()!;
    ws.send(msg);
    console.log("[WS] Flushed queued msg:", msg.substring(0, 120));
  }
}

function send(msg: object): void {
  const payload = JSON.stringify(msg);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(payload);
    console.log("[WS] Sent:", payload.substring(0, 120));
  } else {
    // Queue for delivery once socket opens
    pendingQueue.push(payload);
    console.log("[WS] Queued (not open yet):", payload.substring(0, 120));
  }
}

export function sendCommand(update: ECGStateUpdate): void {
  send({ type: "SET_STATE", payload: update });
}

export function connect(): void {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  console.log("[WS] Connecting to", WS_URL);
  // Expose the send function immediately so UI commands can queue before OPEN.
  useECGStore.getState()._setSendFn(sendCommand);
  const socket = new WebSocket(WS_URL);
  ws = socket;
  socket.binaryType = "arraybuffer";

  socket.onopen = () => {
    if (ws !== socket) {
      socket.close();
      return;
    }
    console.log("[WS] Connected");
    useECGStore.getState().setConnected(true);
    // Flush any commands that were queued before the connection was ready
    flushQueue();
    // Request current state after flush so it arrives last
    send({ type: "GET_STATE" });
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  };

  socket.onmessage = (event) => {
    if (ws !== socket) return;
    if (event.data instanceof ArrayBuffer) {
      // Binary packet → ECG samples
      const pkt = decodePacket(event.data);
      if (pkt) useECGStore.getState().onPacket(pkt);
    } else {
      // JSON message
      try {
        const msg = JSON.parse(event.data as string) as ServerMsg;
        if (msg.type === "STATE_SNAPSHOT") {
          useECGStore.getState().onState(msg.payload);
        } else if (msg.type === "ECG_INTELLIGENCE") {
          useECGStore.getState().onIntelligence(msg.payload);
        }
      } catch (e) {
        console.warn("[WS] Failed to parse message", e);
      }
    }
  };

  socket.onerror = (err) => {
    if (ws !== socket) return;
    console.error("[WS] Error:", err);
  };

  socket.onclose = () => {
    // StrictMode may close an old socket after its replacement is live.
    if (ws !== socket) return;
    console.warn("[WS] Disconnected — reconnecting in", RECONNECT_DELAY_MS, "ms");
    useECGStore.getState().setConnected(false);
    ws = null;
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
  };
}

export function disconnect(): void {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  ws?.close();
  ws = null;
  pendingQueue.length = 0;
}
