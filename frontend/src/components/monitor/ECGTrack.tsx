// src/components/monitor/ECGTrack.tsx
// Real-time scrolling ECG canvas. Reads from Zustand ring buffer, renders at 60 FPS.

import { useRef, useEffect } from "react";
import { useECGStore } from "../../store/ecgStore";
import type { LeadName, Severity } from "../../types/ecgState";
import { SAMPLE_RATE } from "../../types/wsProtocol";
import "./ECGTrack.css";

interface Props {
  lead:       LeadName;
  width?:     number;
  height?:    number;
  paperSpeed?: number;  // mm/s (default 25)
  gain?:      number;   // mm/mV (default 10)
}

const GRID_MM_PX = 4;   // 1mm = 4px

const SEVERITY_COLOR: Record<Severity, string> = {
  normal:   "#00ff88",
  warning:  "#ffb700",
  critical: "#ff4444",
};

const SEVERITY_GLOW: Record<Severity, string> = {
  normal:   "rgba(0,255,136,0.3)",
  warning:  "rgba(255,183,0,0.35)",
  critical: "rgba(255,68,68,0.4)",
};

export default function ECGTrack({ lead, width = 900, height = 220, paperSpeed = 25, gain = 10 }: Props) {
  const bgCanvasRef = useRef<HTMLCanvasElement>(null);
  const fgCanvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef     = useRef<number>(0);
  const prevHead   = useRef<number>(-1);
  const xDrawRef   = useRef<number>(0);

  const bufferRef    = useECGStore.getState().buffer;
  const severityRef  = useRef<Severity>("normal");

  useEffect(() => {
    return useECGStore.subscribe((s) => {
      severityRef.current = s.severity;
    });
  }, []);

  useEffect(() => {
    const bgCanvas = bgCanvasRef.current!;
    const fgCanvas = fgCanvasRef.current!;
    const bgCtx    = bgCanvas.getContext("2d", { alpha: false })!;
    const fgCtx    = fgCanvas.getContext("2d", { alpha: true })!;

    const pxPerSample = (paperSpeed * GRID_MM_PX) / SAMPLE_RATE;
    const mVperPx     = 1.0 / (gain * GRID_MM_PX);
    const baseline    = height / 2;
    const bufSize     = bufferRef[lead]?.length || 0;

    // ── Draw static background grid ──────────────────────────────────────────
    bgCtx.fillStyle = "#070b0f";
    bgCtx.fillRect(0, 0, width, height);

    bgCtx.beginPath();
    for (let x = 0; x <= width; x += GRID_MM_PX) {
      bgCtx.moveTo(x, 0); bgCtx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += GRID_MM_PX) {
      bgCtx.moveTo(0, y); bgCtx.lineTo(width, y);
    }
    bgCtx.strokeStyle = "rgba(0,160,70,0.09)";
    bgCtx.lineWidth = 0.5;
    bgCtx.stroke();

    bgCtx.beginPath();
    for (let x = 0; x <= width; x += GRID_MM_PX * 5) {
      bgCtx.moveTo(x, 0); bgCtx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += GRID_MM_PX * 5) {
      bgCtx.moveTo(0, y); bgCtx.lineTo(width, y);
    }
    bgCtx.strokeStyle = "rgba(0,180,80,0.22)";
    bgCtx.lineWidth = 0.8;
    bgCtx.stroke();

    bgCtx.beginPath();
    bgCtx.moveTo(0, baseline); bgCtx.lineTo(width, baseline);
    bgCtx.strokeStyle = "rgba(0,180,80,0.28)";
    bgCtx.lineWidth = 0.8;
    bgCtx.stroke();

    // ── Animation frame loop ───────────────────────────────────────────────
    function frame() {
      const state     = useECGStore.getState();
      const writeHead = state.bufferHead;
      const buf       = state.buffer[lead];

      if (!buf || bufSize === 0) {
        rafRef.current = requestAnimationFrame(frame);
        return;
      }

      let available = (writeHead - prevHead.current + bufSize) % bufSize;

      if (prevHead.current === -1) {
        const maxInitial = Math.round(width / pxPerSample);
        prevHead.current = (writeHead - maxInitial + bufSize) % bufSize;
        available = maxInitial;
      }

      const maxPerFrame = Math.ceil(width / pxPerSample);
      if (available > maxPerFrame) {
        prevHead.current = (writeHead - maxPerFrame + bufSize) % bufSize;
        available = maxPerFrame;
      }

      if (available <= 0) {
        rafRef.current = requestAnimationFrame(frame);
        return;
      }

      const color = SEVERITY_COLOR[severityRef.current];
      const glow  = SEVERITY_GLOW[severityRef.current];

      fgCtx.beginPath();
      fgCtx.strokeStyle = color;
      fgCtx.lineWidth   = 1.6;
      fgCtx.lineJoin    = "round";
      fgCtx.lineCap     = "round";
      fgCtx.shadowColor = glow;
      fgCtx.shadowBlur  = 4;

      let xPos = xDrawRef.current;
      let firstPoint = true;

      for (let i = 0; i < available; i++) {
        const idx  = (prevHead.current + i) % bufSize;
        const mv   = buf[idx];
        const y    = baseline - mv / mVperPx;
        const clampY = Math.max(4, Math.min(height - 4, y));

        // Eraser sweep (clearRect on transparent foreground)
        const eraseX = (xPos + 10) % width;
        const eraseW = 30;
        if (eraseX + eraseW > width) {
          fgCtx.clearRect(eraseX, 0, width - eraseX, height);
          fgCtx.clearRect(0, 0, (eraseX + eraseW) % width, height);
        } else {
          fgCtx.clearRect(eraseX, 0, eraseW, height);
        }

        if (firstPoint) { fgCtx.moveTo(xPos, clampY); firstPoint = false; }
        else              fgCtx.lineTo(xPos, clampY);

        xPos += pxPerSample;
        if (xPos >= width) {
          fgCtx.stroke();
          fgCtx.beginPath();
          fgCtx.strokeStyle = color;
          fgCtx.lineWidth   = 1.6;
          fgCtx.shadowColor = glow;
          fgCtx.shadowBlur  = 4;
          xPos -= width;
          firstPoint = true;
          fgCtx.moveTo(xPos, clampY);
        }
      }

      fgCtx.stroke();
      fgCtx.shadowBlur = 0;

      xDrawRef.current = xPos;
      prevHead.current = (prevHead.current + available) % bufSize;

      rafRef.current = requestAnimationFrame(frame);
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(rafRef.current);
      prevHead.current = -1;
    };
  }, [bufferRef, lead, width, height, paperSpeed, gain]);

  return (
    <div className="ecg-track" style={{ width, height, position: 'relative' }}>
      <span className="ecg-track__label" style={{ zIndex: 10 }}>{lead}</span>
      <canvas ref={bgCanvasRef} width={width} height={height} style={{ position: 'absolute', top: 0, left: 0 }} />
      <canvas ref={fgCanvasRef} width={width} height={height} style={{ position: 'absolute', top: 0, left: 0, zIndex: 2 }} />
      <span className="ecg-track__speed" style={{ zIndex: 10 }}>{paperSpeed} mm/s · {gain} mm/mV</span>
    </div>
  );
}
