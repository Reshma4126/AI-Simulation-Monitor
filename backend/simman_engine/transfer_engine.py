"""
backend/engine/transfer_engine.py
===================================
Smooth interpolation between ECG parameter values (SimMan transfer time).

Supported functions:
  IMMEDIATE   → instantaneous jump
  LINEAR      → y = y0 + (y1-y0) * t/T
  EXPONENTIAL → y = y1 + (y0-y1) * exp(-k*t),  k = 5/T
  SIGMOID     → y = y0 + (y1-y0) * σ((t-T/2)*10/T)

Usage:
  engine = TransferEngine()
  engine.begin("heart_rate", from_val=80, to_val=140, duration_s=30, fn=TransferFn.SIGMOID)

  # Called once per simulation tick (every 50ms = 0.05s)
  current_hr = engine.tick("heart_rate", dt=0.05)
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from ecg_state import TransferFn


@dataclass
class _Transfer:
    y0:    float
    y1:    float
    T:     float       # duration in seconds
    fn:    TransferFn
    elapsed: float = 0.0
    done:    bool  = False


class TransferEngine:
    """
    Manages simultaneous parameter transitions.
    Each ECG parameter can have an independent ongoing transfer.
    """

    def __init__(self):
        self._transfers: dict[str, _Transfer] = {}

    def begin(
        self,
        param: str,
        from_val: float,
        to_val: float,
        duration_s: float,
        fn: TransferFn,
    ) -> None:
        if fn == TransferFn.IMMEDIATE or duration_s <= 0.0:
            # Store as a "done" transfer so .current() returns to_val
            self._transfers[param] = _Transfer(from_val, to_val, 1.0, fn, elapsed=1.0, done=True)
            return
        self._transfers[param] = _Transfer(from_val, to_val, duration_s, fn)

    def tick(self, param: str, dt: float) -> float | None:
        """
        Advance the transfer for `param` by `dt` seconds.
        Returns the interpolated value, or None if no transfer is active.
        """
        tr = self._transfers.get(param)
        if tr is None:
            return None
        if tr.done:
            return tr.y1

        tr.elapsed += dt
        if tr.elapsed >= tr.T:
            tr.done = True
            return tr.y1

        return _interpolate(tr.y0, tr.y1, tr.elapsed, tr.T, tr.fn)

    def is_active(self, param: str) -> bool:
        tr = self._transfers.get(param)
        return tr is not None and not tr.done

    def current(self, param: str, fallback: float) -> float:
        tr = self._transfers.get(param)
        if tr is None:
            return fallback
        if tr.done:
            return tr.y1
        return _interpolate(tr.y0, tr.y1, tr.elapsed, tr.T, tr.fn)

    def all_done(self) -> bool:
        return all(t.done for t in self._transfers.values())


# ─── Interpolation functions ──────────────────────────────────────────────────

def _interpolate(y0: float, y1: float, t: float, T: float, fn: TransferFn) -> float:
    p = t / T   # progress [0, 1]
    match fn:
        case TransferFn.LINEAR:
            return y0 + (y1 - y0) * p
        case TransferFn.EXPONENTIAL:
            k = 5.0 / T
            return y1 + (y0 - y1) * math.exp(-k * t)
        case TransferFn.SIGMOID:
            k  = 10.0 / T
            t0 = T / 2.0
            sig = 1.0 / (1.0 + math.exp(-k * (t - t0)))
            return y0 + (y1 - y0) * sig
        case _:
            return y1
