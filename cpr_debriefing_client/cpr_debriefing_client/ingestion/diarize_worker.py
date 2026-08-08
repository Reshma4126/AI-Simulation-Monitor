"""
ingestion/diarize_worker.py — Standalone pyannote GPU Worker
=============================================================
Runs in a SEPARATE PROCESS from the main AudioPipeline so that
pyannote's PyTorch CUDA runtime and CTranslate2's bundled CUDA runtime
do not conflict (Windows DLL namespace isolation).

Called by diarization._mode_b_pyannote() via subprocess.Popen().

Usage (internal — not called directly):
    python diarize_worker.py <wav_path> <hf_token> [num_speakers]

Output:
    JSON array of speaker turns written to stdout, one JSON line:
    [{"speaker": "SPEAKER_00", "start_ms": 0, "end_ms": 1230}, ...]

Exit codes:
    0 — success, JSON on stdout
    1 — error, message on stderr
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: diarize_worker.py <wav_path> <hf_token> [num_speakers]", file=sys.stderr)
        sys.exit(1)

    wav_path    = sys.argv[1]
    hf_token    = sys.argv[2]
    num_speakers = int(sys.argv[3]) if len(sys.argv) > 3 else None

    if not os.path.exists(wav_path):
        print(f"[diarize_worker] File not found: {wav_path}", file=sys.stderr)
        sys.exit(1)

    # ── Device selection ───────────────────────────────────────────────────────
    # This runs in its own process → no CTranslate2 DLLs loaded → safe to use GPU
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ── Load pyannote ──────────────────────────────────────────────────────────
    from pyannote.audio import Pipeline
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )
    pipeline.to(torch.device(device))

    # ── Run diarization ────────────────────────────────────────────────────────
    kwargs: dict = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
    else:
        kwargs["min_speakers"] = 2
        kwargs["max_speakers"] = 6

    diarization = pipeline(wav_path, **kwargs)

    # ── Emit JSON turns to stdout ──────────────────────────────────────────────
    turns = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append({
            "speaker":  speaker,
            "start_ms": int(turn.start * 1000),
            "end_ms":   int(turn.end   * 1000),
        })

    print(json.dumps(turns))   # single JSON line on stdout
    sys.exit(0)


if __name__ == "__main__":
    main()
