import { useLayoutEffect, useMemo, useRef, useState } from "react";
import useMonitorStore from "../../store/monitorStore";
import ECGTrack from "./ECGTrack";
import PlethTrack from "./PlethTrack";
import ABPTrack from "./ABPTrack";
import PAPTrack from "./PAPTrack";
import ETCO2Track from "./ETCO2Track";

const TRACK_GAP = 8;
const MAX_TRACK_HEIGHT = 250;

export default function WaveformStack({ lead = "II" }) {
  const stackRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const showEcg   = useMonitorStore((s) => s.show_ecg !== false);
  const showPleth = useMonitorStore((s) => s.show_pleth !== false);
  const showResp  = useMonitorStore((s) => s.show_resp !== false);
  const showIbp   = useMonitorStore((s) => s.show_ibp !== false);

  useLayoutEffect(() => {
    const element = stackRef.current;
    if (!element) return undefined;

    const readSize = () => {
      setSize({
        width: Math.floor(element.clientWidth),
        height: Math.floor(element.clientHeight),
      });
    };

    readSize();
    const observer = new ResizeObserver(readSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const activeTracks = useMemo(() => {
    const tracks = [];
    if (showEcg) tracks.push("ecg");
    if (showPleth) tracks.push("pleth");
    if (showIbp) {
      tracks.push("abp");
      tracks.push("pap");
    }
    if (showResp) tracks.push("etco2");
    return tracks;
  }, [showEcg, showPleth, showIbp, showResp]);

  const trackCount = activeTracks.length || 1;

  const trackSize = useMemo(() => {
    const width = Math.max(1, size.width);
    const availableHeight = Math.max(0, size.height - TRACK_GAP * (trackCount - 1));
    const height = Math.max(
      1,
      Math.min(MAX_TRACK_HEIGHT, Math.floor(availableHeight / trackCount))
    );
    return { width, height };
  }, [size, trackCount]);

  const plethGain = useMemo(
    () => Math.max(8, Math.min(42, (trackSize.height - 31) / 1.75)),
    [trackSize.height]
  );

  return (
    <div ref={stackRef} className="waveform-stack" style={{ display: "flex", flexDirection: "column", gap: `${TRACK_GAP}px`, height: "100%" }}>
      {size.width > 0 && size.height > 0 && (
        <>
          {showEcg && <ECGTrack lead={lead} width={trackSize.width} height={trackSize.height} />}
          {showPleth && <PlethTrack width={trackSize.width} height={trackSize.height} gain={plethGain} />}
          {showIbp && <ABPTrack width={trackSize.width} height={trackSize.height} />}
          {showIbp && <PAPTrack width={trackSize.width} height={trackSize.height} />}
          {showResp && <ETCO2Track width={trackSize.width} height={trackSize.height} />}
        </>
      )}
    </div>
  );
}
