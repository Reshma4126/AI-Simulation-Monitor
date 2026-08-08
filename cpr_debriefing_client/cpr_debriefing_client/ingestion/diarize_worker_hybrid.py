"""
ingestion/diarize_worker_hybrid.py — Hybrid Speaker Diarization Worker
=======================================================================
Option B: pyannote segmentation boundaries + Resemblyzer GE2E embeddings
         + SpectralClustering for global speaker assignment.

Why better than pure pyannote for Tanglish/noisy audio:
  - pyannote's WeSpeaker (VoxCeleb-trained) struggles with Tamil-accented voices
  - Resemblyzer's GE2E encoder handles accent/language variation better
  - We keep pyannote's VAD + temporal boundary detection (its strongest feature)
  - SpectralClustering with cosine distance handles speaker overlap gracefully

Usage (internal):
    python diarize_worker_hybrid.py <wav_path> <hf_token> [num_speakers]

Output (stdout):
    Single JSON line: [{"speaker": "SPEAKER_00", "start_ms": 0, "end_ms": 1230}, ...]

Exit codes:
    0 — success
    1 — error (message on stderr)
"""

from __future__ import annotations

import json
import os
import sys
import types
import warnings

warnings.filterwarnings("ignore")   # suppress torch/speechbrain warnings in subprocess

# ── webrtcvad mock ─────────────────────────────────────────────────────────────
# resemblyzer imports webrtcvad at module level in audio.py.
# We never call preprocess_wav (which uses it) — pyannote does our VAD.
# Install a minimal fake so the import succeeds without the C extension.
_fake_vad = types.ModuleType("webrtcvad")
_fake_vad.Vad = type("Vad", (), {"__init__": lambda s, m=3: None, "is_speech": lambda s, f, sr: True})
sys.modules.setdefault("webrtcvad", _fake_vad)


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: diarize_worker_hybrid.py <wav_path> <hf_token> [num_speakers]",
            file=sys.stderr,
        )
        sys.exit(1)

    wav_path     = sys.argv[1]
    hf_token     = sys.argv[2]
    num_speakers = int(sys.argv[3]) if len(sys.argv) > 3 else None

    if not os.path.exists(wav_path):
        print(f"[hybrid] File not found: {wav_path}", file=sys.stderr)
        sys.exit(1)

    import numpy as np
    import soundfile as sf
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ── Step 1 — pyannote segmentation (timing boundaries only) ───────────────
    # We use the full pipeline to extract turn boundaries, but we will
    # DISCARD its speaker labels and re-embed with Resemblyzer.
    from pyannote.audio import Pipeline as _Pipeline
    print("[hybrid] Loading pyannote segmentation pipeline …", file=sys.stderr)
    pyannote_pipeline = _Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )
    pyannote_pipeline.to(torch.device(device))

    kwargs: dict = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
    else:
        kwargs["min_speakers"] = 2
        kwargs["max_speakers"] = 8   # allow more clusters than pure pyannote default

    print("[hybrid] Running pyannote segmentation …", file=sys.stderr)
    diarization = pyannote_pipeline(wav_path, **kwargs)

    # Collect raw turn boundaries (ignore pyannote's speaker labels)
    raw_turns = [
        (turn.start, turn.end)
        for turn, _, _ in diarization.itertracks(yield_label=True)
    ]
    print(f"[hybrid] pyannote found {len(raw_turns)} turn boundaries", file=sys.stderr)

    if not raw_turns:
        print("[hybrid] No turns detected — empty output", file=sys.stderr)
        print(json.dumps([]))
        sys.exit(0)

    # ── Step 2 — Load full audio ───────────────────────────────────────────────
    audio_full, native_sr = sf.read(wav_path, dtype="float32", always_2d=False)
    # Ensure mono
    if audio_full.ndim == 2:
        audio_full = audio_full.mean(axis=1)

    # ── Step 3 — Resemblyzer embeddings ───────────────────────────────────────
    from resemblyzer import VoiceEncoder
    import librosa   # used for resampling; librosa doesn't need webrtcvad

    print("[hybrid] Loading Resemblyzer encoder …", file=sys.stderr)
    encoder = VoiceEncoder(device)   # GPU if available

    embeddings: list[np.ndarray] = []
    valid_turns: list[tuple[float, float]] = []
    MIN_DURATION = 0.4   # skip segments shorter than 400ms (too short for GE2E)
    TARGET_SR    = 16000  # Resemblyzer expects 16kHz mono float32

    print("[hybrid] Computing GE2E embeddings per turn …", file=sys.stderr)
    for start, end in raw_turns:
        duration = end - start
        if duration < MIN_DURATION:
            continue

        # Extract segment at native sample rate
        s = int(start * native_sr)
        e = int(end   * native_sr)
        clip = audio_full[s:e]

        try:
            # Resample to 16kHz (Resemblyzer's expected sample rate)
            if native_sr != TARGET_SR:
                clip = librosa.resample(clip, orig_sr=native_sr, target_sr=TARGET_SR)

            # Normalize to [-1, 1]
            peak = np.abs(clip).max()
            if peak > 0:
                clip = clip / peak

            if len(clip) < 1600:   # <0.1s at 16kHz — skip
                continue

            emb = encoder.embed_utterance(clip)
            embeddings.append(emb)
            valid_turns.append((start, end))
        except Exception as exc:
            print(f"[hybrid] Skipping turn {start:.2f}-{end:.2f}: {exc}", file=sys.stderr)

    print(f"[hybrid] Embedded {len(embeddings)} turns", file=sys.stderr)

    if len(embeddings) < 2:
        # Fall back to single-speaker labelling
        turns = [
            {"speaker": "SPEAKER_00", "start_ms": int(s * 1000), "end_ms": int(e * 1000)}
            for s, e in valid_turns
        ]
        print(json.dumps(turns))
        sys.exit(0)

    # ── Step 4 — Spectral Clustering with cosine affinity ─────────────────────
    from sklearn.cluster import SpectralClustering
    from sklearn.metrics import silhouette_score

    X = np.vstack(embeddings)

    if num_speakers is not None:
        n_sp = num_speakers
        print(f"[hybrid] Clustering with n_speakers={n_sp} (user hint)", file=sys.stderr)
    else:
        # Auto-select: try 2..8 and pick best silhouette score
        max_n = min(8, len(embeddings) - 1)
        best_score, best_n = -1.0, 2
        for n in range(2, max_n + 1):
            try:
                lbl = SpectralClustering(
                    n_clusters=n, affinity="cosine", random_state=42, n_init=10
                ).fit_predict(X)
                score = silhouette_score(X, lbl, metric="cosine")
                print(f"[hybrid]   n={n}  silhouette={score:.3f}", file=sys.stderr)
                if score > best_score:
                    best_score, best_n = score, n
            except Exception:
                break
        n_sp = best_n
        print(f"[hybrid] Selected n_speakers={n_sp} (silhouette={best_score:.3f})", file=sys.stderr)

    sc = SpectralClustering(
        n_clusters=n_sp, affinity="cosine", random_state=42, n_init=10
    )
    labels = sc.fit_predict(X)

    # ── Step 5 — Emit turns ────────────────────────────────────────────────────
    turns = []
    for (start, end), label in zip(valid_turns, labels):
        turns.append({
            "speaker":  f"SPEAKER_{int(label):02d}",
            "start_ms": int(start * 1000),
            "end_ms":   int(end   * 1000),
        })

    # Sort by start time
    turns.sort(key=lambda t: t["start_ms"])

    speakers_found = set(t["speaker"] for t in turns)
    print(
        f"[hybrid] Done — {len(turns)} turns, {len(speakers_found)} speakers: "
        f"{', '.join(sorted(speakers_found))}",
        file=sys.stderr,
    )

    print(json.dumps(turns))   # single JSON line on stdout
    sys.exit(0)


if __name__ == "__main__":
    main()
