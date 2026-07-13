"""
backend/engine/state_machine.py
=================================
The central simulation loop.

Responsibilities:
  1. Hold the live ECGState
  2. Manage pending parameter transitions via TransferEngine
  3. Drive the WaveformGenerator to produce samples
  4. Project samples onto all 12 leads via LeadGenerator
  5. Inject artifacts via NoiseEngine
  6. Broadcast packets to all connected WebSocket clients
  7. Log events and HR trend to MongoDB

The loop runs as an asyncio task at ~50ms tick rate (configurable).
"""

from __future__ import annotations
import asyncio
import struct
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable

import numpy as np

from ecg_state import ECGState, ECGStateUpdate, RhythmType, IschemiaZone, TransferFn
from simman_engine.waveform_generator import WaveformGenerator
from simman_engine.lead_generator import generate_all_leads
from simman_engine.transfer_engine import TransferEngine
from simman_engine.noise_engine import inject
from simman_engine.rhythm_intelligence import (
    get_rhythm_hr_limits,
    get_rhythm_default_hr,
    intelligence_payload,
)

# ─── Config ───────────────────────────────────────────────────────────────────
SAMPLE_RATE     = 512          # Hz
PACKET_MS       = 50           # ms per WebSocket packet
SAMPLES_PER_PKT = round(SAMPLE_RATE * PACKET_MS / 1000)  # 25.6 -> 26

LEAD_ORDER = ["I", "II", "III", "aVR", "aVL", "aVF",
              "V1", "V2", "V3", "V4", "V5", "V6", "PLETH", "ABP", "PAP", "ETCO2"]

# ─── Broadcast type alias ─────────────────────────────────────────────────────
BroadcastFn = Callable[[bytes], Awaitable[None]]


class SimulationEngine:
    """
    Singleton-style engine that owns the ECG state and runs the real-time loop.
    WebSocket connections register callbacks to receive binary ECG packets.
    """

    def __init__(self):
        self.state       = ECGState()
        self._generator  = WaveformGenerator(fs=SAMPLE_RATE)
        self._transfer   = TransferEngine()
        self._clients:   set[BroadcastFn] = set()
        self._task:      asyncio.Task | None = None
        self._session_id: str = "default"
        self._hr_log_acc: float = 0.0   # accumulate time for HR trend logging
        # JSON broadcast callback — set by WS handler, called after rhythm change
        self._json_broadcast: Callable[[str], Awaitable[None]] | None = None

    # ─── Client management ────────────────────────────────────────────────────

    def add_client(self, send_fn: BroadcastFn) -> None:
        self._clients.add(send_fn)

    def remove_client(self, send_fn: BroadcastFn) -> None:
        self._clients.discard(send_fn)

    def set_json_broadcast(self, fn: Callable[[str], Awaitable[None]]) -> None:
        """Register a callback for JSON messages (ECG_INTELLIGENCE, etc.)."""
        self._json_broadcast = fn

    def clear_json_broadcast(self) -> None:
        self._json_broadcast = None

    def _coerce_rhythm(self, rhythm: RhythmType | str | None) -> RhythmType:
        try:
            if rhythm is None:
                return RhythmType.NSR
            return RhythmType(rhythm) if not isinstance(rhythm, RhythmType) else rhythm
        except ValueError:
            return RhythmType.NSR

    # ─── Instructor commands ──────────────────────────────────────────────────

    async def apply_command(self, update: ECGStateUpdate) -> None:
        """
        Apply an instructor update to the ECG state, using the configured
        transfer function and time for smooth transitions.
        """
        state = self.state
        print(f"[Engine] Incoming command: {update.model_dump(exclude_none=True)}")
        print(
            f"[Engine] Before apply: hr={state.heart_rate:.1f}, rhythm={state.rhythm}, "
            f"transfer_time={state.transfer_time}, transfer_fn={state.transfer_fn}"
        )

        # Update Transfer options first so they are immediately active for begin() calls
        if update.transfer_time is not None:
            state.transfer_time = update.transfer_time
        if update.transfer_fn is not None:
            state.transfer_fn = update.transfer_fn

        # Helper to begin a numeric transfer or set directly
        def begin(param: str, old: float, new: float | None) -> None:
            if new is None or new == old:
                return
            self._transfer.begin(
                param, old, new,
                state.transfer_time, state.transfer_fn
            )

        # Transfer-based params
        if update.heart_rate is not None:
            requested_hr = update.heart_rate
            # Snap HR for AFLUTTER
            active_rhythm = update.rhythm if update.rhythm is not None else state.rhythm
            if active_rhythm == RhythmType.AFLUTTER:
                if requested_hr > 120:
                    requested_hr = 150.0
                elif requested_hr > 85:
                    requested_hr = 100.0
                else:
                    requested_hr = 75.0

            old_hr = state.heart_rate
            print(f"[Engine] Begin HR transfer: {old_hr:.1f} -> {requested_hr:.1f}")
            await self._log_event("HR_CHANGE", old_hr, requested_hr)
            self._transfer.begin(
                "heart_rate",
                old_hr,
                requested_hr,
                state.transfer_time,
                state.transfer_fn,
            )
            if state.transfer_time <= 0.0 or state.transfer_fn == TransferFn.IMMEDIATE:
                state.heart_rate = requested_hr

        if update.pr_interval is not None:
            begin("pr_interval", state.pr_interval, update.pr_interval)
        if update.qrs_duration is not None:
            begin("qrs_duration", state.qrs_duration, update.qrs_duration)
        if update.qt_interval is not None:
            begin("qt_interval", state.qt_interval, update.qt_interval)
        if update.st_elevation is not None:
            begin("st_elevation", state.st_elevation, update.st_elevation)
        if update.st_depression is not None:
            begin("st_depression", state.st_depression, update.st_depression)
        if update.artifact_level is not None:
            begin("artifact_level", state.artifact_level, update.artifact_level)
        if update.ectopy_rate is not None:
            begin("ectopy_rate", state.ectopy_rate, update.ectopy_rate)
        if update.spo2 is not None:
            begin("spo2", state.spo2, update.spo2)
        if update.sys_bp is not None:
            requested_dia = update.dia_bp if update.dia_bp is not None else state.dia_bp
            target_sys = max(update.sys_bp, requested_dia + 1.0)
            begin("sys_bp", state.sys_bp, target_sys)
        if update.dia_bp is not None:
            requested_sys = update.sys_bp if update.sys_bp is not None else state.sys_bp
            target_dia = min(update.dia_bp, requested_sys - 1.0)
            begin("dia_bp", state.dia_bp, max(0.0, target_dia))
        if update.pap_sys is not None:
            requested_pap_dia = update.pap_dia if update.pap_dia is not None else state.pap_dia
            begin("pap_sys", state.pap_sys, max(update.pap_sys, requested_pap_dia + 0.5))
        if update.pap_dia is not None:
            requested_pap_sys = update.pap_sys if update.pap_sys is not None else state.pap_sys
            begin("pap_dia", state.pap_dia, max(0.0, min(update.pap_dia, requested_pap_sys - 0.5)))
        if update.etco2 is not None:
            begin("etco2", state.etco2, update.etco2)
        if update.resp_rate is not None:
            begin("resp_rate", state.resp_rate, update.resp_rate)

        # Instantaneous params
        if update.rhythm is not None:
            # Coerce to enum if it's a string
            try:
                new_rhythm = RhythmType(update.rhythm) if not isinstance(update.rhythm, RhythmType) else update.rhythm
            except ValueError:
                print(f"[Engine] Unknown rhythm: {update.rhythm!r} — ignoring")
                new_rhythm = None

            if new_rhythm is not None and new_rhythm != state.rhythm:
                old_rhythm = state.rhythm
                print(
                    f"[Engine] Begin rhythm transition: {old_rhythm} -> {new_rhythm}, "
                    f"transfer_time={state.transfer_time}, transfer_fn={state.transfer_fn}"
                )
                self._generator.begin_rhythm_transition(
                    old_rhythm,
                    new_rhythm,
                    state.transfer_time,
                    state.transfer_fn,
                )
                state.rhythm = new_rhythm
                print(f"[Engine] Rhythm changed: {old_rhythm} -> {new_rhythm}")

                # ── Auto-correct HR to the default rate for the new rhythm ──
                current_hr = state.heart_rate
                default_hr = get_rhythm_default_hr(new_rhythm)
                target_hr = float(default_hr)

                # Reset conduction and ischemia parameters to default if not explicitly updated or required by the rhythm
                if update.pr_interval is None and new_rhythm != RhythmType.AVB1:
                    state.pr_interval = 160.0
                if update.qrs_duration is None and new_rhythm not in (RhythmType.LBBB, RhythmType.RBBB):
                    state.qrs_duration = 80.0
                if update.st_elevation is None and new_rhythm not in (RhythmType.ANT_STEMI, RhythmType.INF_STEMI, RhythmType.LAT_STEMI):
                    state.st_elevation = 0.0
                if update.st_depression is None and new_rhythm not in (RhythmType.ANT_STEMI, RhythmType.INF_STEMI, RhythmType.LAT_STEMI):
                    state.st_depression = 0.0

                if new_rhythm == RhythmType.AVB1:
                    state.pr_interval = 230.0
                elif new_rhythm in (RhythmType.LBBB, RhythmType.RBBB):
                    state.qrs_duration = 140.0

                if target_hr is not None and target_hr != current_hr:
                    print(f"[Engine] Auto HR correction: {current_hr:.1f} -> {target_hr:.1f} for {new_rhythm}")
                    self._transfer.begin(
                        "heart_rate",
                        current_hr,
                        target_hr,
                        state.transfer_time,
                        state.transfer_fn,
                    )
                    if state.transfer_time <= 0.0 or state.transfer_fn == TransferFn.IMMEDIATE:
                        state.heart_rate = target_hr

                # Set ischemia zone for STEMI rhythms
                if new_rhythm == RhythmType.ANT_STEMI:
                    state.ischemia_zone = IschemiaZone.ANTERIOR
                    state.st_elevation  = max(state.st_elevation, 0.35)
                    target_hr = 60.0
                elif new_rhythm == RhythmType.INF_STEMI:
                    state.ischemia_zone = IschemiaZone.INFERIOR
                    state.st_elevation  = max(state.st_elevation, 0.35)
                    target_hr = 60.0
                elif new_rhythm == RhythmType.LAT_STEMI:
                    state.ischemia_zone = IschemiaZone.LATERAL
                    state.st_elevation  = max(state.st_elevation, 0.35)
                    target_hr = 60.0
                else:
                    state.ischemia_zone = IschemiaZone.NONE
                await self._log_event("RHYTHM_CHANGE", old_rhythm, new_rhythm)

        if update.ischemia_zone is not None:
            state.ischemia_zone = update.ischemia_zone
        if update.artifact_type is not None:
            state.artifact_type = update.artifact_type
        if update.lead_selection is not None:
            state.lead_selection = update.lead_selection

        print(
            f"[Engine] After apply: hr={state.heart_rate:.1f}, rhythm={state.rhythm}, "
            f"transfer_time={state.transfer_time}, transfer_fn={state.transfer_fn}"
        )

    # ─── Simulation loop ──────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        print("[Engine] Simulation loop started.")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            print("[Engine] Simulation loop stopped.")

    async def _loop(self) -> None:
        tick_s = PACKET_MS / 1000.0
        while True:
            t0 = asyncio.get_event_loop().time()
            try:
                # 1. Tick transfer engine → update state values smoothly
                self._tick_transfers()

                # 2. Generate ECG samples for all leads
                lead2 = self._generator.generate(self.state, SAMPLES_PER_PKT)
                all_leads = generate_all_leads(lead2, self.state, SAMPLE_RATE)
                # Inject artifacts
                all_leads = {
                    name: inject(sig, SAMPLE_RATE, self.state)
                    for name, sig in all_leads.items()
                }
                all_leads["PLETH"] = self._generator.generate_pleth(
                    self.state, SAMPLES_PER_PKT
                )
                all_leads["ABP"] = self._generator.generate_abp(
                    self.state, SAMPLES_PER_PKT
                )
                all_leads["PAP"] = self._generator.generate_pap(self.state, SAMPLES_PER_PKT)
                all_leads["ETCO2"] = self._generator.generate_etco2(self.state, SAMPLES_PER_PKT)

                # 3. Compute instantaneous HR
                hr_inst = round(self.state.heart_rate, 1)

                # 4. Build and broadcast binary packet
                packet = _encode_packet(all_leads, hr_inst, self.state)
                await self._broadcast(packet)

                # 5. HR trend logging (every ~1 second)
                self._hr_log_acc += tick_s
                if self._hr_log_acc >= 1.0:
                    self._hr_log_acc = 0.0
                    asyncio.create_task(self._log_hr(hr_inst))
            except Exception as e:
                import traceback
                print("[Engine] Error in simulation loop:")
                traceback.print_exc()

            # 6. Maintain tick rate
            elapsed = asyncio.get_event_loop().time() - t0
            await asyncio.sleep(max(0, tick_s - elapsed))

    def _tick_transfers(self) -> None:
        """Apply transfer engine ticks to update ECGState."""
        dt  = PACKET_MS / 1000.0
        state = self.state

        def apply(param: str) -> None:
            val = self._transfer.tick(param, dt)
            if val is not None:
                setattr(state, param, val)

        for p in ["heart_rate", "spo2", "sys_bp", "dia_bp", "pap_sys", "pap_dia", "etco2", "resp_rate", "pr_interval", "qrs_duration", "qt_interval",
                  "st_elevation", "st_depression", "artifact_level", "ectopy_rate"]:
            apply(p)

        # Physiological decay during cardiac arrest (PEA, VF, Asystole)
        rhythm = self._coerce_rhythm(state.rhythm)
        if rhythm in (RhythmType.ASYSTOLE, RhythmType.VF, RhythmType.PEA):
            state.sys_bp = max(0.0, state.sys_bp - 3.0)
            state.dia_bp = max(0.0, state.dia_bp - 2.0)
            state.pap_sys = max(0.0, state.pap_sys - 0.8)
            state.pap_dia = max(0.0, state.pap_dia - 0.5)
            state.spo2 = max(0.0, state.spo2 - 0.1)
            if state.etco2 > 10.0:
                state.etco2 = max(10.0, state.etco2 - 0.2)
            elif state.etco2 < 10.0:
                state.etco2 = min(10.0, state.etco2 + 0.2)

        # Independent transfers must never cross into an invalid pressure pair.
        if state.dia_bp >= state.sys_bp:
            state.dia_bp = max(0.0, state.sys_bp - 1.0)
        if state.pap_dia >= state.pap_sys:
            state.pap_dia = max(0.0, state.pap_sys - 0.5)

    async def _broadcast(self, data: bytes) -> None:
        dead = set()
        for send in list(self._clients):
            try:
                await send(data)
            except Exception:
                dead.add(send)
        self._clients -= dead

    async def _log_event(self, event_type: str, old: object, new: object) -> None:
        pass  # Handled by socket_manager.py directly

    async def _log_hr(self, hr: float) -> None:
        pass  # Handled by socket_manager.py directly


# ─── Binary packet encoding ───────────────────────────────────────────────────

def _encode_packet(
    leads: dict[str, np.ndarray],
    heart_rate: float,
    state: ECGState,
) -> bytes:
    """
    Binary packet layout:
      [2 bytes] magic  = 0xECEC
      [4 bytes] float  = heart_rate
      [4 bytes] float  = spo2
      [4 bytes] float  = sys_bp
      [4 bytes] float  = dia_bp
      [4 bytes] float  = pap_sys
      [4 bytes] float  = pap_dia
      [4 bytes] float  = etco2
      [4 bytes] float  = resp_rate
      [2 bytes] uint16 = n_samples
      [2 bytes] uint16 = n_leads  (always 16)
      For each lead (in LEAD_ORDER):
        [n_samples × 4 bytes] float32 array
      [1 byte]  severity  (0=normal, 1=warning, 2=critical)
      [1 byte]  rhythm_len
      [N bytes] rhythm string (ASCII)
    """
    from ecg_state import RHYTHM_SEVERITY
    severity_map = {"normal": 0, "warning": 1, "critical": 2}
    rhythm_key = state.rhythm if isinstance(state.rhythm, str) else state.rhythm.value
    sev = severity_map.get(RHYTHM_SEVERITY.get(state.rhythm, "normal"), 0)
    rhythm_bytes = rhythm_key.encode("ascii")

    n_samples = SAMPLES_PER_PKT
    parts = [
        struct.pack(
            ">HffffffffHH",
            0xECEC, heart_rate, state.spo2, state.sys_bp, state.dia_bp,
            state.pap_sys, state.pap_dia, state.etco2, state.resp_rate,
            n_samples, len(LEAD_ORDER)
        ),
    ]
    for lead_name in LEAD_ORDER:
        arr = leads.get(lead_name, np.zeros(n_samples, dtype=np.float32))
        parts.append(np.asarray(arr, dtype=">f4").tobytes())
    parts.append(struct.pack("BB", sev, len(rhythm_bytes)))
    parts.append(rhythm_bytes)
    return b"".join(parts)


# ─── Global singleton ─────────────────────────────────────────────────────────
engine = SimulationEngine()
