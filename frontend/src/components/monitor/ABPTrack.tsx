// src/components/monitor/ABPTrack.tsx
// Real-time scrolling ABP canvas. Reads from Zustand ring buffer, renders at 60 FPS.

import { useRef, useEffect } from "react";
import { useECGStore } from "../../store/ecgStore";
import { SAMPLE_RATE } from "../../types/wsProtocol";
import "./ABPTrack.css";

interface Props {
  width?:     number;
  height?:    number;
  paperSpeed?: number;  // mm/s (default 25)
}

const GRID_MM_PX = 4;   // 1mm = 4px
const ABP_COLOR = "#ff0000";
const ABP_GLOW = "rgba(255, 0, 0, 0.4)";

export default function ABPTrack({ width = 900, height = 150, paperSpeed = 25 }: Props) {
  const bgCanvasRef = useRef<HTMLCanvasElement>(null);
  const fgCanvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef     = useRef<number>(0);
  const prevHead   = useRef<number>(-1);
  const xDrawRef   = useRef<number>(0);

  const bufferRef = useECGStore.getState().buffer;

  useEffect(() => {
    const bgCanvas = bgCanvasRef.current!;
    const fgCanvas = fgCanvasRef.current!;
    const bgCtx    = bgCanvas.getContext("2d", { alpha: false })!;
    const fgCtx    = fgCanvas.getContext("2d", { alpha: true })!;

    const pxPerSample = (paperSpeed * GRID_MM_PX) / SAMPLE_RATE;
    const bufSize     = bufferRef["ABP"]?.length || 0;

    // ── Draw static background grid ──────────────────────────────────────────
    bgCtx.fillStyle = "#160a0a";
    bgCtx.fillRect(0, 0, width, height);

    bgCtx.beginPath();
    for (let x = 0; x <= width; x += GRID_MM_PX) {
      bgCtx.moveTo(x, 0); bgCtx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += GRID_MM_PX) {
      bgCtx.moveTo(0, y); bgCtx.lineTo(width, y);
    }
    bgCtx.strokeStyle = "rgba(255, 0, 0, 0.18)";
    bgCtx.lineWidth = 0.5;
    bgCtx.stroke();

    bgCtx.beginPath();
    for (let x = 0; x <= width; x += GRID_MM_PX * 5) {
      bgCtx.moveTo(x, 0); bgCtx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += GRID_MM_PX * 5) {
      bgCtx.moveTo(0, y); bgCtx.lineTo(width, y);
    }
    bgCtx.strokeStyle = "rgba(255, 20, 20, 0.35)";
    bgCtx.lineWidth = 0.8;
    bgCtx.stroke();

    // ── Animation frame loop ───────────────────────────────────────────────
    function frame() {
      const state     = useECGStore.getState();
      const writeHead = state.bufferHead;
      const buf       = state.buffer["ABP"];

      if (!buf || bufSize === 0) {
        rafRef.current = requestAnimationFrame(frame);
        return;
      }

      let available = (writeHead - prevHead.current + bufSize) % bufSize;

      if (prevHead.current === -1) {
        prevHead.current = (writeHead - Math.round(width / pxPerSample) + bufSize) % bufSize;
        available = Math.round(width / pxPerSample);
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

      fgCtx.beginPath();
      fgCtx.strokeStyle = ABP_COLOR;
      fgCtx.lineWidth   = 2.0;
      fgCtx.lineJoin    = "round";
      fgCtx.lineCap     = "round";
      fgCtx.shadowColor = ABP_GLOW;
      fgCtx.shadowBlur  = 6;

      let xPos = xDrawRef.current;
      let firstPoint = true;
      const yPad = 18;
      const bottomMargin = 14;
      const plotH = Math.max(20, height - yPad - bottomMargin);
      const sys = Math.max(state.liveSysBP, state.liveDiaBP + 1);
      const dia = Math.min(state.liveDiaBP, sys - 1);
      const pressurePad = Math.max(18, (sys - dia) * 0.45);
      const yMin = Math.max(0, dia - pressurePad);
      const yMax = Math.min(300, Math.max(sys + pressurePad * 0.65, yMin + 50));
      const pressureRange = Math.max(1, yMax - yMin);

      for (let i = 0; i < available; i++) {
        const idx  = (prevHead.current + i) % bufSize;
        const val  = buf[idx];
        const y    = yPad + (1 - ((val - yMin) / pressureRange)) * plotH;
        const clampY = Math.max(4, Math.min(height - 4, y));

        // Eraser sweep
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
          fgCtx.strokeStyle = ABP_COLOR;
          fgCtx.lineWidth   = 2.0;
          fgCtx.shadowColor = ABP_GLOW;
          fgCtx.shadowBlur  = 6;
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
  }, [bufferRef, width, height, paperSpeed]);

  return (
    <div className="abp-track" style={{ width, height, position: 'relative' }}>
      <span className="abp-track__label" style={{ zIndex: 10 }}>ABP</span>
      <canvas ref={bgCanvasRef} width={width} height={height} style={{ position: 'absolute', top: 0, left: 0 }} />
      <canvas ref={fgCanvasRef} width={width} height={height} style={{ position: 'absolute', top: 0, left: 0, zIndex: 2 }} />
      <span className="abp-track__speed" style={{ zIndex: 10 }}>{paperSpeed} mm/s</span>
    </div>
  );
}
