import { useEffect, useRef } from "react";
import { useECGStore } from "../../store/ecgStore";
import { SAMPLE_RATE } from "../../types/wsProtocol";
import "./PAPTrack.css";

interface Props {
  width?: number;
  height?: number;
  paperSpeed?: number;
}

const GRID_MM_PX = 4;
const TRACE_COLOR = "#ffd43b";
const TRACE_GLOW = "rgba(255, 212, 59, 0.4)";

export default function PAPTrack({ width = 900, height = 110, paperSpeed = 25 }: Props) {
  const bgCanvasRef = useRef<HTMLCanvasElement>(null);
  const fgCanvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef(0);
  const prevHead = useRef(-1);
  const xDrawRef = useRef(0);
  const bufferRef = useECGStore.getState().buffer;

  useEffect(() => {
    const bgCanvas = bgCanvasRef.current;
    const fgCanvas = fgCanvasRef.current;
    if (!bgCanvas || !fgCanvas) return;

    const bgCtx = bgCanvas.getContext("2d", { alpha: false })!;
    const fgCtx = fgCanvas.getContext("2d", { alpha: true })!;

    const pxPerSample = (paperSpeed * GRID_MM_PX) / SAMPLE_RATE;
    const bufSize = bufferRef.PAP.length;

    bgCtx.fillStyle = "#070b0f";
    bgCtx.fillRect(0, 0, width, height);
    bgCtx.beginPath();
    for (let x = 0; x <= width; x += GRID_MM_PX) {
      bgCtx.moveTo(x, 0);
      bgCtx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += GRID_MM_PX) {
      bgCtx.moveTo(0, y);
      bgCtx.lineTo(width, y);
    }
    bgCtx.strokeStyle = "rgba(180, 150, 0, 0.10)";
    bgCtx.lineWidth = 0.5;
    bgCtx.stroke();

    bgCtx.beginPath();
    for (let x = 0; x <= width; x += GRID_MM_PX * 5) {
      bgCtx.moveTo(x, 0);
      bgCtx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += GRID_MM_PX * 5) {
      bgCtx.moveTo(0, y);
      bgCtx.lineTo(width, y);
    }
    bgCtx.strokeStyle = "rgba(255, 212, 59, 0.22)";
    bgCtx.lineWidth = 0.8;
    bgCtx.stroke();

    function frame() {
      const state = useECGStore.getState();
      const writeHead = state.bufferHead;
      const buf = state.buffer.PAP;
      let available = (writeHead - prevHead.current + bufSize) % bufSize;

      if (prevHead.current === -1) {
        const visibleSamples = Math.round(width / pxPerSample);
        prevHead.current = (writeHead - visibleSamples + bufSize) % bufSize;
        available = visibleSamples;
      }

      const maxPerFrame = Math.ceil(width / pxPerSample);
      if (available > maxPerFrame) {
        prevHead.current = (writeHead - maxPerFrame + bufSize) % bufSize;
        available = maxPerFrame;
      }

      if (available > 0) {
        fgCtx.beginPath();
        fgCtx.strokeStyle = TRACE_COLOR;
        fgCtx.lineWidth = 2;
        fgCtx.lineJoin = "round";
        fgCtx.lineCap = "round";
        fgCtx.shadowColor = TRACE_GLOW;
        fgCtx.shadowBlur = 6;

        let xPos = xDrawRef.current;
        let firstPoint = true;
        const topPad = 16;
        const plotHeight = Math.max(20, height - 28);
        const papSys = Math.max(state.livePapSys, state.livePapDia + 0.5);
        const papDia = Math.min(state.livePapDia, papSys - 0.5);
        const pressurePad = Math.max(8, (papSys - papDia) * 0.5);
        const yMin = Math.max(0, papDia - pressurePad);
        const yMax = Math.max(papSys + pressurePad, yMin + 25);

        for (let i = 0; i < available; i++) {
          const index = (prevHead.current + i) % bufSize;
          const y = topPad + (1 - (buf[index] - yMin) / (yMax - yMin)) * plotHeight;
          const clampedY = Math.max(4, Math.min(height - 4, y));
          const eraseX = (xPos + 10) % width;
          const eraseWidth = 30;

          if (eraseX + eraseWidth > width) {
            fgCtx.clearRect(eraseX, 0, width - eraseX, height);
            fgCtx.clearRect(0, 0, (eraseX + eraseWidth) % width, height);
          } else {
            fgCtx.clearRect(eraseX, 0, eraseWidth, height);
          }

          if (firstPoint) {
            fgCtx.moveTo(xPos, clampedY);
            firstPoint = false;
          } else {
            fgCtx.lineTo(xPos, clampedY);
          }

          xPos += pxPerSample;
          if (xPos >= width) {
            fgCtx.stroke();
            fgCtx.beginPath();
            fgCtx.strokeStyle = TRACE_COLOR;
            fgCtx.lineWidth = 2;
            fgCtx.shadowColor = TRACE_GLOW;
            fgCtx.shadowBlur = 6;
            xPos -= width;
            firstPoint = true;
          }
        }

        fgCtx.stroke();
        fgCtx.shadowBlur = 0;
        xDrawRef.current = xPos;
        prevHead.current = (prevHead.current + available) % bufSize;
      }

      rafRef.current = requestAnimationFrame(frame);
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(rafRef.current);
      prevHead.current = -1;
    };
  }, [bufferRef, height, paperSpeed, width]);

  return (
    <div className="pap-track" style={{ width, height }}>
      <span className="pap-track__label">PAP</span>
      <canvas ref={bgCanvasRef} width={width} height={height} />
      <canvas ref={fgCanvasRef} width={width} height={height} />
      <span className="pap-track__speed">{paperSpeed} mm/s</span>
    </div>
  );
}
