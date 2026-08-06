import { useState, useEffect, useRef } from "react";
import useMonitorStore from "../../store/monitorStore";

export default function TrendsModal({ onClose, sessionStartRef }) {
  const [frozen, setFrozen] = useState(false);
  const [trendData, setTrendData] = useState([]);
  const trendCanvasRef = useRef(null);

  // Trend data sampling every 5s
  useEffect(() => {
    if (frozen) return;
    const interval = setInterval(() => {
      const s = useMonitorStore.getState();
      const startTime = sessionStartRef?.current || Date.now();
      
      setTrendData((prev) => {
        const next = [
          ...prev,
          {
            t: Math.floor((Date.now() - startTime) / 1000),
            HR: s.HR,
            RR: s.avRR,
            SpO2: s.SpO2,
            SAP: s.ABP_sys,
            DAP: s.ABP_dia,
          },
        ];
        // Keep last 240 samples (20 min) for the modal view
        return next.slice(-240);
      });
    }, 5000);
    return () => clearInterval(interval);
  }, [frozen, sessionStartRef]);

  // Mini trend chart using canvas
  useEffect(() => {
    const canvas = trendCanvasRef.current;
    if (!canvas || trendData.length < 2) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.offsetWidth;
    const H = canvas.offsetHeight;
    canvas.width = W;
    canvas.height = H;

    ctx.fillStyle = "#0e0e0e";
    ctx.fillRect(0, 0, W, H);

    const lines = [
      { key: "HR", color: "#FF3333", max: 200 },
      { key: "RR", color: "#00CCFF", max: 40 },
      { key: "SpO2", color: "#00FF00", max: 100 },
      { key: "SAP", color: "#FFFF00", max: 250 },
      { key: "DAP", color: "#FF9900", max: 200 },
    ];

    lines.forEach(({ key, color, max }) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      trendData.forEach((d, i) => {
        const x = (i / (trendData.length - 1)) * W;
        const y = H - (d[key] / max) * H * 0.9 - H * 0.05;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });

    // Legend
    ctx.font = "12px Inter, sans-serif";
    lines.forEach(({ key, color }, i) => {
      ctx.fillStyle = color;
      ctx.fillText(key, 10 + i * 55, 20);
    });
  }, [trendData]);

  return (
    <div className="dialog-overlay" style={{ zIndex: 10000 }}>
      <div className="dialog-box trends-modal">
        <div className="dialog-header">
          <h2>Patient Trends</h2>
          <div className="trends-actions">
            <button className="btn-classic btn-sm" onClick={() => setFrozen(!frozen)}>
              {frozen ? "▶ Resume" : "❚❚ Freeze"}
            </button>
            <button className="btn-classic btn-sm" onClick={onClose}>✕</button>
          </div>
        </div>
        <div className="dialog-body">
          <canvas ref={trendCanvasRef} className="trend-canvas-large" style={{ width: '100%', height: '300px', backgroundColor: '#0e0e0e', borderRadius: '4px' }} />
        </div>
      </div>
    </div>
  );
}
