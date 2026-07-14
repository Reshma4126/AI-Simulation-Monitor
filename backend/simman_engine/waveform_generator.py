"""
backend/engine/waveform_generator.py
=====================================
Gaussian PQRST ECG synthesis engine.

Architecture:
  ECG(t) = P(t) + Q(t) + R(t) + S(t) + T(t) + ST_offset(t)

Each wave: W(t) = A * exp(-(t - μ)² / (2·σ²))
  t is normalised to [0, 1] within one RR interval.

The generator maintains phase state across calls so the signal is
perfectly continuous even when parameters change mid-stream.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from ecg_state import ECGState, RhythmType, TransferFn
from simman_engine.rhythm_intelligence import get_wave_visibility
from simman_engine.co2_generator import _co2_at_phase, Co2State
from simman_engine.abp_generator import abp_equation


# ─── Wave descriptor ──────────────────────────────────────────────────────────

@dataclass
class Wave:
    amp:    float   # mV amplitude  (negative = downward)
    center: float   # position in beat [0, 1]
    sigma:  float   # Gaussian width (fraction of RR)


@dataclass
class BeatParams:
    """All Gaussian parameters for one beat."""
    p:  Wave | None   # None → no P wave (AFib, VT, etc.)
    q:  Wave
    r:  Wave
    s:  Wave
    t:  Wave
    rr_jitter:   float = 0.0    # RR variability fraction (σ of multiplicative noise)
    st_slope:    float = 0.0    # baseline ST offset (mV) — overridden by ECGState
    qrs_extra_width: float = 0.0  # extra Gaussian width for wide QRS rhythms (LBBB, RBBB, VT)


@dataclass
class RhythmTransition:
    source: RhythmType
    target: RhythmType
    duration_s: float
    fn: TransferFn
    elapsed_s: float = 0.0

    @property
    def done(self) -> bool:
        return self.elapsed_s >= self.duration_s


# ─── Default NSR parameters ───────────────────────────────────────────────────
#   (t in [0,1] is fraction of RR interval)
#   Normal: PR≈160ms, QRS≈80ms, QT≈400ms at 70 bpm → RR≈857ms
#   Fractions: P@0.13, QRS@0.38-0.48, T@0.60

def _nsr() -> BeatParams:
    return BeatParams(
        p = Wave( 0.12,  0.12, 0.024),
        q = Wave(-0.05,  0.38, 0.012),
        r = Wave( 1.00,  0.41, 0.015),
        s = Wave(-0.15,  0.44, 0.012),
        t = Wave( 0.26,  0.65, 0.050),
    )


# ─── Rhythm → BeatParams factory ─────────────────────────────────────────────

def get_beat_params(state: ECGState, rhythm: RhythmType | None = None) -> BeatParams:
    # Coerce rhythm to enum if it's a raw string (can happen after state updates)
    try:
        source_rhythm = state.rhythm if rhythm is None else rhythm
        r = RhythmType(source_rhythm) if not isinstance(source_rhythm, RhythmType) else source_rhythm
    except ValueError:
        r = RhythmType.NSR

    # ── Pure morphology rhythms ──────────────────────────────────────────────
    if r in (RhythmType.NSR, RhythmType.PAC):
        return _nsr()

    if r == RhythmType.SINUS_BRADY:
        # Slower sinus activation makes the atrial and repolarisation waves more distinct.
        bp = _nsr()
        bp.p = Wave(0.17, 0.12, 0.026)
        bp.t = Wave(0.34, 0.62, 0.055)
        return bp

    if r == RhythmType.SINUS_TACHY:
        # Rate compression brings the P wave closer to the preceding T wave.
        bp = _nsr()
        bp.p = Wave(0.12, 0.11, 0.025)
        bp.t = Wave(0.24, 0.61, 0.050)
        return bp

    if r == RhythmType.AVB1:
        # First-degree block keeps sinus morphology but with slightly reduced P-wave amplitude (0.11)
        bp = _nsr()
        bp.p = Wave(0.11, 0.12, 0.024)
        return bp

    if r == RhythmType.PEA:
        # PEA retains organised electrical activity; low-voltage morphology
        # distinguishes the teaching trace while the absent pulse is clinical.
        bp = _nsr()
        bp.p = Wave(0.10, 0.13, 0.030)
        bp.r = Wave(0.65, 0.41, 0.018)
        bp.s = Wave(-0.12, 0.45, 0.014)
        bp.t = Wave(0.18, 0.66, 0.065)
        return bp

    if r == RhythmType.AFIB:
        # No P wave, irregular baseline flutter added in noise engine
        bp = _nsr()
        bp.p = None
        bp.rr_jitter = 0.20   # irregular RR
        return bp

    if r == RhythmType.AFLUTTER:
        bp = _nsr()
        bp.p = None
        return bp

    if r == RhythmType.JUNCTIONAL:
        # Retrograde P (inverted, immediately before QRS)
        bp = _nsr()
        bp.p = Wave(-0.12, 0.12, 0.015)
        return bp


    if r in (RhythmType.AVB2_I, RhythmType.AVB2_II):
        # Handled beat-level in rhythm_engine; morphology same as NSR
        return _nsr()

    if r == RhythmType.AVB3:
        # P waves dissociated — drawn separately; QRS is ventricular escape
        bp = _nsr()
        bp.r.amp = 0.60   # slightly smaller escape QRS
        bp.qrs_extra_width = 0.010
        return bp

    if r == RhythmType.PVC:
        # Wide bizarre QRS, no P, compensatory pause handled in rhythm_engine
        return BeatParams(
            p = None,
            q = Wave(-0.20,  0.35, 0.025),
            r = Wave( 1.20,  0.42, 0.030),
            s = Wave(-0.40,  0.50, 0.025),
            t = Wave(-0.25,  0.70, 0.080),  # T discordant with QRS
            qrs_extra_width=0.020,
        )

    if r == RhythmType.SVT:
        # Clinically accurate AVNRT: sharp narrow QRS, shortened ST segment, smaller/narrower T wave closer to QRS, no P wave
        return BeatParams(
            p = None,
            q = Wave(-0.06,  0.385, 0.008),
            r = Wave( 1.20,  0.41,  0.012),
            s = Wave(-0.18,  0.43,  0.008),
            t = Wave( 0.18,  0.58,  0.035),
        )

    if r == RhythmType.VT:
        # Clinically accurate Monomorphic VT: wide bizarre QRS (>140 ms), steep upstroke, secondary ST-T discordance, no P
        return BeatParams(
            p = None,
            q = Wave(-0.15,  0.38,  0.015),
            r = Wave( 1.30,  0.44,  0.035),
            s = Wave(-0.35,  0.52,  0.020),
            t = Wave(-0.25,  0.72,  0.055),
            qrs_extra_width=0.025,
        )

    if r == RhythmType.VF:
        # Handled entirely in rhythm_engine as chaotic oscillation
        return _nsr()   # placeholder, not used

    if r == RhythmType.TORSADES:
        return BeatParams(
            p = None,
            q = Wave(-0.20,  0.35, 0.020),
            r = Wave( 1.50,  0.43, 0.035),
            s = Wave(-0.60,  0.52, 0.025),
            t = Wave(-0.40,  0.72, 0.055),
            qrs_extra_width=0.030,
            rr_jitter=0.08,
        )

    if r == RhythmType.ASYSTOLE:
        return BeatParams(
            p=None,
            q=Wave(0, 0.38, 0.01),
            r=Wave(0, 0.41, 0.01),
            s=Wave(0, 0.44, 0.01),
            t=Wave(0, 0.65, 0.01),
        )

    if r == RhythmType.LBBB:
        # Notched R in lateral leads, wide QRS
        return BeatParams(
            p = Wave( 0.15,  0.13, 0.030),
            q = Wave(-0.03,  0.36, 0.010),
            r = Wave( 0.90,  0.42, 0.035),   # broad R
            s = Wave(-0.05,  0.50, 0.010),
            t = Wave(-0.20,  0.72, 0.070),   # discordant T
            qrs_extra_width=0.025,
        )

    if r == RhythmType.RBBB:
        # RSR' in V1, wide S in I/V5/V6; discordant inverted T wave
        return BeatParams(
            p = Wave( 0.15,  0.13, 0.030),
            q = Wave(-0.05,  0.38, 0.012),
            r = Wave( 1.00,  0.41, 0.020),
            s = Wave(-0.30,  0.52, 0.018),   # deep wide S
            t = Wave(-0.18,  0.72, 0.055),
            qrs_extra_width=0.018,
        )

    if r in (RhythmType.ANT_STEMI, RhythmType.INF_STEMI, RhythmType.LAT_STEMI):
        # Acute STEMI: broad, tall hyperacute T wave
        bp = _nsr()
        bp.t = Wave(0.40, 0.65, 0.080)
        return bp

    # fallback
    return _nsr()


# ─── Generator ────────────────────────────────────────────────────────────────

class WaveformGenerator:
    """
    Maintains continuous phase state and generates ECG samples on demand.
    Thread-safe assumption: called only from the simulation loop.
    """

    def __init__(self, fs: int = 512):
        self.fs = fs
        self._phase: float = 0.0         # [0, 1) within one RR interval
        self._rr_history: list[float] = []
        self._beat_count: int = 0
        self._rr_factor: float = 1.0
        self._avb2_counter: int = 0      # for Wenckebach pattern
        self._torsades_axis: float = 0.0 # twisting axis angle
        self._vf_clock: float = 0.0
        self._atrial_clock: float = 0.0
        self._rhythm_transition: RhythmTransition | None = None
        self._last_phases: np.ndarray | None = None
        self._last_beat_indices: np.ndarray | None = None
        self._last_rr_factors: np.ndarray | None = None
        self._running_pleth_val: float = 0.0
        self._resp_phase: float = 0.0
        self._resp_wander_phase: float = 0.0
        self._r_amp_factor: float = 1.0
        self._t_amp_factor: float = 1.0
        self._abp_sys_var: float = 0.0
        self._abp_dia_var: float = 0.0
        self._last_resp_phases: np.ndarray | None = None
        self._pleth_amp_var: float = 1.0
        self._pap_sys_var: float = 0.0
        self._pap_dia_var: float = 0.0
        self._qrs_amp_var: float = 1.0
        self._pac_state: int = 0
        self._normal_beat_count_pac: int = 0
        self._pvc_state: int = 0
        self._normal_beat_count_pvc: int = 0

    def begin_rhythm_transition(
        self,
        source: RhythmType,
        target: RhythmType,
        duration_s: float,
        fn: TransferFn,
    ) -> None:
        source_rhythm = self._coerce_rhythm(source)
        target_rhythm = self._coerce_rhythm(target)
        if target_rhythm == RhythmType.VF:
            self._vf_duration_samples = 0
            self._vf_phase_perturbation = 0.0
            self._vf_amp_modulator = 1.0
        if source_rhythm == target_rhythm or fn == TransferFn.IMMEDIATE or duration_s <= 0.0:
            self._rhythm_transition = None
            return
        self._rhythm_transition = RhythmTransition(source_rhythm, target_rhythm, duration_s, fn)

    def clear_rhythm_transition(self) -> None:
        self._rhythm_transition = None

    def generate(self, state: ECGState, n_samples: int) -> np.ndarray:
        """
        Generate `n_samples` of ECG signal (Lead II reference).
        Returns float32 array normalised to approximately ±1.0 mV.
        """
        signal = np.zeros(n_samples, dtype=np.float32)
        target_rhythm = self._coerce_rhythm(state.rhythm)
        transition = self._rhythm_transition

        # A zero intrinsic rate is electrical standstill regardless of the
        # selected morphology. The engine loop continues emitting flat packets.
        if state.heart_rate <= 0.0:
            self._last_phases = np.zeros(n_samples, dtype=np.float32)
            self._last_beat_indices = np.zeros(n_samples, dtype=np.int64)
            self._last_rr_factors = np.ones(n_samples, dtype=np.float32)
            return (signal + np.random.normal(0.0, 0.003, n_samples)).astype(np.float32)
        if transition is not None and transition.done:
            self._rhythm_transition = None
            transition = None

        if transition is None and target_rhythm == RhythmType.VF:
            self._last_phases = np.zeros(n_samples, dtype=np.float32)
            self._last_beat_indices = np.zeros(n_samples, dtype=np.int64)
            self._last_rr_factors = np.ones(n_samples, dtype=np.float32)
            return (self._vf(n_samples) + np.random.normal(0.0, 0.003, n_samples)).astype(np.float32)
        if transition is None and target_rhythm == RhythmType.ASYSTOLE:
            self._last_phases = np.zeros(n_samples, dtype=np.float32)
            self._last_beat_indices = np.zeros(n_samples, dtype=np.int64)
            self._last_rr_factors = np.ones(n_samples, dtype=np.float32)
            return (signal + np.random.normal(0.0, 0.003, n_samples)).astype(np.float32)

        params_target = get_beat_params(state, target_rhythm)
        params_source = get_beat_params(state, transition.source) if transition is not None else params_target
        beat_start_pending = self._phase == 0.0

        phases = np.zeros(n_samples, dtype=np.float32)
        beat_indices = np.zeros(n_samples, dtype=np.int64)
        rr_factors = np.ones(n_samples, dtype=np.float32)

        for i in range(n_samples):
            phases[i] = self._phase
            beat_indices[i] = self._beat_count
            rr_factors[i] = self._rr_factor
            if transition is not None:
                mix = self._transition_mix(transition)
                source_sample = self._sample_for_rhythm_or_special(
                    self._phase, params_source, state, transition.source
                )
                target_sample = self._sample_for_rhythm_or_special(
                    self._phase, params_target, state, transition.target
                )
                signal[i] = (1.0 - mix) * source_sample + mix * target_sample
                transition.elapsed_s = min(transition.elapsed_s + (1.0 / self.fs), transition.duration_s)
                if transition.done:
                    self._rhythm_transition = None
                    transition = None
            else:
                signal[i] = self._sample_for_rhythm_or_special(
                    self._phase, params_target, state, target_rhythm
                )

            rr_sec = self._rr(state, target_rhythm)
            if beat_start_pending:
                self._on_beat_start(state, params_target, target_rhythm)
                beat_start_pending = False

            self._phase += 1.0 / (rr_sec * self.fs)
            if self._phase >= 1.0:
                self._phase -= 1.0
                self._beat_count += 1
                self._rr_factor = self._choose_rr_factor(state, target_rhythm)
                beat_start_pending = True

        self._last_phases = phases
        self._last_beat_indices = beat_indices
        self._last_rr_factors = rr_factors

        # Pre-calculate continuous respiratory phase array for synchronization across all waveforms
        resp_freq = state.resp_rate / 60.0 if state.resp_rate > 0.0 else 0.20
        resp_phases = np.zeros(n_samples, dtype=np.float32)
        for i in range(n_samples):
            resp_phases[i] = self._resp_wander_phase
            self._resp_wander_phase += resp_freq / self.fs
            if self._resp_wander_phase >= 1.0:
                self._resp_wander_phase -= 1.0
        self._last_resp_phases = resp_phases

        # Inject subtle respiratory baseline wander and monitor noise
        for i in range(n_samples):
            wander = 0.02 * np.sin(2 * np.pi * self._last_resp_phases[i])
            noise = float(np.random.normal(0.0, 0.003))
            signal[i] += wander + noise

        return signal

    def generate_pleth(self, state: ECGState, n_samples: int) -> np.ndarray:
        """
        Generate a continuous SpO2 plethysmography waveform.

        The shape is the two-component Gaussian model supplied for the
        simulator: a main systolic peak plus a lower, later reflected/dicrotic
        wave.  It is evaluated from the delayed hemodynamic phase so the pleth
        pulse follows the ECG R wave, and a running value smooths beat-to-beat
        or control changes without stopping the monitor stream.
        """
        signal = np.zeros(n_samples, dtype=np.float32)
        if (
            self._last_phases is None
            or self._last_beat_indices is None
            or self._last_rr_factors is None
            or len(self._last_phases) != n_samples
        ):
            return signal

        rhythm = self._coerce_rhythm(state.rhythm)
        if state.heart_rate <= 0.0 or rhythm in (
            RhythmType.ASYSTOLE, RhythmType.VF, RhythmType.PEA
        ):
            self._running_pleth_val = 0.0
            return signal

        hr = state.heart_rate
        beat_period = 60.0 / hr
        r_phase = 0.41
        delay_phase = min(0.65, 0.320 / beat_period)
        pulse_pressure = max(0.0, float(state.sys_bp - state.dia_bp))

        # The pleth is not a blood-pressure trace, but pulse pressure and
        # rhythm-dependent stroke volume are reasonable simulation proxies for
        # peripheral pulse amplitude/perfusion.
        pressure_scale = float(np.clip(pulse_pressure / 40.0, 0.25, 1.60))
        rate_scale = 1.0
        if hr > 160.0:
            rate_scale = max(0.65, 1.0 - (hr - 160.0) / 500.0)
        elif hr < 40.0:
            rate_scale = max(0.75, hr / 40.0)

        # Very low SpO2 may still have pulsatility, so saturation only lightly
        # attenuates amplitude. Numeric alarm handling remains separate.
        saturation_scale = float(np.clip(state.spo2 / 98.0, 0.70, 1.05))
        cardiac_output_scale = pressure_scale * rate_scale * saturation_scale
        hemodynamic_smoothing = 0.14

        for i in range(n_samples):
            cardiac_phase = float(self._last_phases[i])
            hemo_phase = (cardiac_phase - r_phase - delay_phase) % 1.0
            pleth_shape = self._pleth_shape(hemo_phase)
            current_pulse_scale = self._abp_pulse_factor(
                rhythm,
                int(self._last_beat_indices[i]),
                float(self._last_rr_factors[i]),
                hr,
            )
            resp_mod = 1.0 + 0.02 * np.sin(2 * np.pi * self._last_resp_phases[i])
            target_pleth = pleth_shape * cardiac_output_scale * current_pulse_scale * self._pleth_amp_var * resp_mod
            self._running_pleth_val += (
                target_pleth - self._running_pleth_val
            ) * hemodynamic_smoothing
            signal[i] = float(np.clip(self._running_pleth_val, 0.0, 2.0))

        return signal

    @staticmethod
    def _pleth_shape(t: float) -> float:
        """
        Two-component Gaussian pleth model.

        The constants intentionally match the provided JavaScript reference:
        A1/t1/g1 for the systolic peak and A2/t2/g2 for the dicrotic/reflection
        wave, using periodic distance over one cardiac cycle.
        """
        a1, t1, g1 = 1.0, 0.2, 0.08
        a2, t2, g2 = 0.35, 0.45, 0.15

        def periodic_diff(val: float, target: float) -> float:
            diff = val - target
            while diff < -0.5:
                diff += 1.0
            while diff > 0.5:
                diff -= 1.0
            return diff

        dt1 = periodic_diff(t, t1)
        dt2 = periodic_diff(t, t2)
        systolic_peak = a1 * np.exp(-(dt1 * dt1) / (2.0 * g1 * g1))
        dicrotic_wave = a2 * np.exp(-(dt2 * dt2) / (2.0 * g2 * g2))
        return float(systolic_peak + dicrotic_wave)

    def generate_abp(self, state: ECGState, n_samples: int) -> np.ndarray:
        """
        Generate a continuous invasive arterial-pressure trace using the clinically accurate abp_equation.
        """
        signal = np.zeros(n_samples, dtype=np.float32)
        if (
            self._last_phases is None
            or self._last_beat_indices is None
            or self._last_rr_factors is None
            or len(self._last_phases) != n_samples
        ):
            return signal

        rhythm = self._coerce_rhythm(state.rhythm)
        # No effective mechanical output in cardiac arrest or PEA.
        if state.heart_rate <= 0.0 or rhythm in (
            RhythmType.ASYSTOLE, RhythmType.VF, RhythmType.PEA
        ):
            return signal

        hr = state.heart_rate
        beat_period = 60.0 / hr
        
        # Clinical parameters from the validated ABP generator config
        rise_fraction = 0.28
        notch_depth_base = 15.0
        notch_timing_fraction = 0.42
        notch_sigma_fraction = 0.05

        rise_time = rise_fraction * beat_period
        notch_time = notch_timing_fraction * beat_period
        notch_sigma = notch_sigma_fraction * beat_period

        # Arterial pulse foot follows the electrical R wave by about 120 ms.
        r_phase = 0.41
        delay_phase = min(0.65, 0.120 / beat_period)

        for i in range(n_samples):
            cardiac_phase = float(self._last_phases[i])
            hemo_phase = (cardiac_phase - r_phase - delay_phase) % 1.0
            t_sample = hemo_phase * beat_period

            # Continuous respiratory modulation
            resp_mod = 2.5 * np.sin(2 * np.pi * self._last_resp_phases[i])

            # Apply beat-to-beat pressure variability
            sys_val = state.sys_bp + self._abp_sys_var + resp_mod
            dia_val = state.dia_bp + self._abp_dia_var + resp_mod

            pulse_factor = self._abp_pulse_factor(
                rhythm,
                int(self._last_beat_indices[i]),
                float(self._last_rr_factors[i]),
                hr,
            )

            # scale pulse pressure by the rhythm-dependent pulse factor
            effective_sys = dia_val + max(0.0, sys_val - dia_val) * pulse_factor
            effective_dia = dia_val
            effective_notch_depth = notch_depth_base * pulse_factor

            val = abp_equation(
                t_sample,
                effective_sys,
                effective_dia,
                rise_time,
                effective_notch_depth,
                notch_time,
                notch_sigma
            )
            signal[i] = max(0.0, float(val))

        return signal

    def generate_pap(self, state: ECGState, n_samples: int) -> np.ndarray:
        """
        Generate a pulmonary artery pressure trace.

        PAP is a mechanical pressure waveform like ABP, but with lower pressure,
        a gentler upstroke, and a softer dicrotic notch. It stays synchronized
        to the cardiac cycle and therefore follows HR/rhythm changes instantly.
        """
        signal = np.zeros(n_samples, dtype=np.float32)
        if (
            self._last_phases is None
            or self._last_beat_indices is None
            or self._last_rr_factors is None
            or len(self._last_phases) != n_samples
        ):
            return signal

        rhythm = self._coerce_rhythm(state.rhythm)
        if state.heart_rate <= 0.0 or rhythm in (
            RhythmType.ASYSTOLE, RhythmType.VF, RhythmType.PEA
        ):
            return signal

        pap_sys = max(float(state.pap_sys), float(state.pap_dia) + 0.5)
        pap_dia = max(0.0, float(state.pap_dia))
        pulse_pressure = max(0.0, pap_sys - pap_dia)
        if pulse_pressure <= 0.0:
            signal.fill(pap_dia)
            return signal

        hr = state.heart_rate
        beat_period = 60.0 / hr
        r_phase = 0.41
        delay_phase = min(0.65, 0.150 / beat_period)
        rise_fraction = 0.30
        notch_fraction = float(np.clip(0.46 - ((hr - 60.0) * 0.0007), 0.34, 0.52))
        notch_sigma_fraction = float(np.clip(0.060 * (70.0 / hr), 0.040, 0.075))

        for i in range(n_samples):
            cardiac_phase = float(self._last_phases[i])
            hemo_phase = (cardiac_phase - r_phase - delay_phase) % 1.0
            
            # Continuous respiratory modulation (±1.0 mmHg)
            resp_mod = 1.0 * np.sin(2 * np.pi * self._last_resp_phases[i])
            
            # Apply beat-to-beat pressure variability
            sys_val = pap_sys + self._pap_sys_var + resp_mod
            dia_val = pap_dia + self._pap_dia_var + resp_mod

            pulse_factor = self._abp_pulse_factor(
                rhythm,
                int(self._last_beat_indices[i]),
                float(self._last_rr_factors[i]),
                hr,
            )
            effective_pp = max(0.0, sys_val - dia_val) * pulse_factor
            pressure = self._abp_pressure(
                hemo_phase,
                dia_val,
                effective_pp,
                rise_fraction,
                notch_fraction,
                notch_sigma_fraction,
                notch_depth_fraction=0.07,
            )
            signal[i] = max(0.0, float(pressure))
        return signal

    def generate_etco2(self, state: ECGState, n_samples: int) -> np.ndarray:
        """
        Generate a capnography waveform using the integrated clinical CO2 generator module.
        """
        signal = np.zeros(n_samples, dtype=np.float32)
        if state.resp_rate <= 0.0 or state.etco2 <= 0.0:
            self._resp_phase = 0.0
            return signal

        rr_sec = 60.0 / state.resp_rate
        step = 1.0 / (rr_sec * self.fs)
        
        phases = np.zeros(n_samples, dtype=np.float32)
        for i in range(n_samples):
            phases[i] = self._resp_phase
            self._resp_phase += step
            if self._resp_phase >= 1.0:
                self._resp_phase -= 1.0

        co2_state = Co2State(
            etco2=float(state.etco2),
            respiratory_rate=float(state.resp_rate)
        )
        
        co2_vals = _co2_at_phase(phases, co2_state)
        return co2_vals.astype(np.float32)


    @staticmethod
    def _abp_pressure(
        phase: float,
        diastolic: float,
        pulse_pressure: float,
        rise_fraction: float,
        notch_fraction: float,
        notch_sigma_fraction: float,
        notch_depth_fraction: float = 0.10,
    ) -> float:
        """Reference-style ABP pressure sample for one normalised beat phase."""
        x = phase / max(rise_fraction, 1e-6)
        systolic_term = x * np.exp(1.0 - x)
        notch_term = np.exp(
            -((phase - notch_fraction) ** 2)
            / (2.0 * max(notch_sigma_fraction, 1e-6) ** 2)
        )
        notch_depth = pulse_pressure * notch_depth_fraction
        return float(diastolic + pulse_pressure * systolic_term - notch_depth * notch_term)


    @staticmethod
    def _abp_pulse_factor(
        rhythm: RhythmType, beat_index: int, rr_factor: float, heart_rate: float
    ) -> float:
        """Model rhythm-dependent effective stroke volume."""
        if rhythm == RhythmType.AFIB:
            # Irregular filling produces irregular pulse pressure.
            return float(np.clip(0.72 + 0.45 * (rr_factor - 0.8), 0.55, 1.0))
        if rhythm == RhythmType.PVC:
            cycle = beat_index % 4
            if cycle == 2:
                return 0.42  # premature beat: poor ventricular filling
            if cycle == 3:
                return 1.08  # post-PVC potentiation after compensatory pause
        if rhythm in (RhythmType.VT, RhythmType.TORSADES):
            return 0.48
        if rhythm == RhythmType.SVT:
            return 0.68

        # Very fast rates shorten filling even in organised rhythms.
        if heart_rate > 160:
            return max(0.65, 1.0 - (heart_rate - 160.0) / 500.0)
        return 1.0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _coerce_rhythm(self, rhythm: RhythmType | str | None) -> RhythmType:
        try:
            if rhythm is None:
                return RhythmType.NSR
            return RhythmType(rhythm) if not isinstance(rhythm, RhythmType) else rhythm
        except ValueError:
            return RhythmType.NSR

    def _get_rhythm(self, state: ECGState) -> RhythmType:
        """Safely coerce state.rhythm to RhythmType enum."""
        return self._coerce_rhythm(state.rhythm)

    def _rr(self, state: ECGState, rhythm: RhythmType | None = None) -> float:
        """Compute RR interval with HRV jitter."""
        if state.heart_rate <= 0.0:
            return float("inf")
        hr = state.heart_rate
        rr_mean = 60.0 / hr
        params = get_beat_params(state, rhythm)
        if rhythm in (RhythmType.AVB2_I, RhythmType.AVB2_II):
            # Dynamic block conduction ratio C based on heart rate
            if hr >= 70:
                C = 4
            elif hr >= 58:
                C = 3
            else:
                C = 2
            # Atrial rate is hr * C / (C - 1)
            effective_hr = hr * float(C) / float(C - 1)
            rr_mean = 60.0 / effective_hr
        elif rhythm == RhythmType.AFLUTTER:
            if hr > 120:
                effective_hr = 150.0
            elif hr > 85:
                effective_hr = 100.0
            else:
                effective_hr = 75.0
            rr_mean = 60.0 / effective_hr
        elif rhythm == RhythmType.PVC:
            if self._pvc_state == 1:
                return rr_mean * 0.60
            elif self._pvc_state == 2:
                return rr_mean * 1.40
        elif rhythm == RhythmType.PAC:
            if self._pac_state == 1:
                return rr_mean * 0.60
            elif self._pac_state == 2:
                return rr_mean * 1.20

        # General HRV
        return max(rr_mean * self._rr_factor, 0.20)  # floor at 0.2s (300 bpm)

    def _choose_rr_factor(self, state: ECGState, rhythm: RhythmType) -> float:
        """Choose variability once per beat so each RR interval is stable."""
        rhythm = self._coerce_rhythm(rhythm)
        if rhythm == RhythmType.AFIB:
            # Irregularly irregular ventricular rate
            return float(np.random.uniform(0.70, 1.30))
        if rhythm == RhythmType.AFLUTTER:
            # Fixed 2:1 conduction has very small variability (±1%)
            return float(np.random.uniform(0.99, 1.01))
        params = get_beat_params(state, rhythm)
        sigma = params.rr_jitter + state.hrv_std
        return float(max(np.random.normal(1.0, sigma), 0.65))

    def _on_beat_start(self, state: ECGState, params: BeatParams, rhythm: RhythmType | None = None) -> None:
        """Actions at the start of each new beat."""
        rhythm = self._coerce_rhythm(rhythm if rhythm is not None else state.rhythm)
        
        # Beat-to-beat amplitude variability
        if rhythm in (RhythmType.AFIB, RhythmType.AFLUTTER):
            self._r_amp_factor = float(np.random.uniform(0.98, 1.02))
            self._t_amp_factor = float(np.random.uniform(0.98, 1.02))
        else:
            self._r_amp_factor = 1.0
            self._t_amp_factor = 1.0

        # Beat-to-beat ABP pressure variability: systolic ±2 mmHg, diastolic ±1 mmHg
        self._abp_sys_var = float(np.random.uniform(-2.0, 2.0))
        self._abp_dia_var = float(np.random.uniform(-1.0, 1.0))

        # Beat-to-beat Pleth variability: amplitude ±3%
        self._pleth_amp_var = float(np.random.uniform(0.97, 1.03))

        # Beat-to-beat PAP variability: systolic ±1 mmHg, diastolic ±0.5 mmHg
        self._pap_sys_var = float(np.random.uniform(-1.0, 1.0))
        self._pap_dia_var = float(np.random.uniform(-0.5, 0.5))

        # Beat-to-beat QRS amplitude variability: ±5%
        self._qrs_amp_var = float(np.random.uniform(0.95, 1.05))

        # Wenckebach / Mobitz II: track dropped beats with dynamic cycle length C
        if rhythm in (RhythmType.AVB2_I, RhythmType.AVB2_II):
            hr = state.heart_rate
            if hr >= 70:
                C = 4
            elif hr >= 58:
                C = 3
            else:
                C = 2
            self._avb2_counter = (self._avb2_counter + 1) % C
        # Torsades: rotate QRS axis slowly
        if rhythm == RhythmType.TORSADES:
            self._torsades_axis += 0.15
        
        # PAC: track state machine transitions
        if rhythm == RhythmType.PAC:
            if self._pac_state == 1:
                self._pac_state = 2
            elif self._pac_state == 2:
                self._pac_state = 0
            else:
                self._normal_beat_count_pac += 1
                if self._normal_beat_count_pac >= 2 and np.random.random() < 0.20:
                    self._pac_state = 1
                    self._normal_beat_count_pac = 0
        else:
            self._pac_state = 0

        # PVC: track state machine transitions
        if rhythm == RhythmType.PVC:
            if self._pvc_state == 1:
                self._pvc_state = 2
            elif self._pvc_state == 2:
                rate = state.ectopy_rate
                if rate > 30.0:  # Bigeminy
                    self._pvc_state = 1
                else:
                    self._pvc_state = 0
                    self._normal_beat_count_pvc = 0
            else:  # self._pvc_state == 0
                rate = state.ectopy_rate
                if rate > 30.0:  # Bigeminy
                    self._pvc_state = 1
                elif rate > 15.0:  # Trigeminy
                    self._normal_beat_count_pvc += 1
                    if self._normal_beat_count_pvc >= 1:
                        self._pvc_state = 1
                elif rate > 0.0:  # Quadrigeminy
                    self._normal_beat_count_pvc += 1
                    if self._normal_beat_count_pvc >= 2:
                        self._pvc_state = 1
                else:  # Isolated/Occasional
                    self._normal_beat_count_pvc += 1
                    if self._normal_beat_count_pvc >= 3 and np.random.random() < 0.15:
                        self._pvc_state = 1
                        self._normal_beat_count_pvc = 0
        else:
            self._pvc_state = 0
            self._normal_beat_count_pvc = 0

    def _sample_for_rhythm(self, t: float, params: BeatParams, state: ECGState, rhythm: RhythmType) -> float:
        """Evaluate the sum of Gaussian waves at normalised position t ∈ [0,1]."""
        rhythm = self._coerce_rhythm(rhythm)

        # PVC is an ectopic event, not a continuous all-PVC waveform.
        if rhythm == RhythmType.PVC:
            if self._pvc_state != 1:
                params = _nsr()

        if rhythm == RhythmType.PAC:
            if self._pac_state != 1:
                params = _nsr()
            else:
                params = _nsr()
                # Altered P-wave morphology: inverted, slightly wider
                params.p = Wave(-0.15, 0.12, 0.030)

        # Wenckebach / Mobitz II: check if current beat in cycle is dropped
        if rhythm in (RhythmType.AVB2_I, RhythmType.AVB2_II):
            hr = state.heart_rate
            if hr >= 70:
                C = 4
            elif hr >= 58:
                C = 3
            else:
                C = 2
            if self._avb2_counter == C - 1:
                # Only P wave (if beat = dropped)
                rr_sec = self._rr(state, rhythm)
                # The P wave should be positioned regularly at the default PR (160 ms for Mobitz I, 180 ms for Mobitz II)
                pr_sec = 0.160 if rhythm == RhythmType.AVB2_I else 0.180
                c_r = params.r.center
                qrs_duration_scale = state.qrs_duration / 80.0
                q_offset_sec = (params.q.center - c_r) * qrs_duration_scale
                q_sigma_sec = params.q.sigma * qrs_duration_scale
                qrs_onset_sec = q_offset_sec - 2 * q_sigma_sec
                p_offset_sec = qrs_onset_sec - pr_sec + 2 * (params.p.sigma if params.p else 0.024)
                p_center = c_r + p_offset_sec / rr_sec
                p_sigma = params.p.sigma / rr_sec if params.p else 0.030 / rr_sec
                val = 0.0
                if params.p:
                    val += _gauss(t, Wave(params.p.amp, p_center, p_sigma))
                return val

        # Get current RR interval in seconds for scaling
        rr_sec = self._rr(state, rhythm)

        # Scale QRS (Q, R, S) to have constant width in seconds
        c_r = params.r.center
        if (rhythm == RhythmType.PVC and self._pvc_state == 1) or rhythm == RhythmType.TORSADES:
            qrs_duration_scale = 1.75  # Force wide QRS (>120 ms)
        else:
            qrs_duration_scale = state.qrs_duration / 80.0
        
        q_offset_sec = (params.q.center - c_r) * qrs_duration_scale
        s_offset_sec = (params.s.center - c_r) * qrs_duration_scale
        
        q_center = c_r + q_offset_sec / rr_sec
        s_center = c_r + s_offset_sec / rr_sec
        
        q_sigma = (params.q.sigma * qrs_duration_scale) / rr_sec
        r_sigma = (params.r.sigma * qrs_duration_scale) / rr_sec
        s_sigma = (params.s.sigma * qrs_duration_scale) / rr_sec

        # Scale P wave to honor state.pr_interval and have constant width in seconds
        if rhythm == RhythmType.AVB2_I:
            # Progressive PR interval: 160ms -> 210ms -> 260ms -> dropped
            pr_ms = 160.0 + 50.0 * self._avb2_counter
        elif rhythm == RhythmType.AVB2_II:
            # Constant PR interval: 180ms
            pr_ms = 180.0
        elif rhythm == RhythmType.JUNCTIONAL:
            pr_ms = 40.0
        elif rhythm == RhythmType.AVB1:
            pr_ms = max(230.0, state.pr_interval)
        elif rhythm in (RhythmType.NSR, RhythmType.SINUS_BRADY, RhythmType.SINUS_TACHY):
            pr_ms = 160.0 + (75.0 - state.heart_rate) / 3.0
            pr_ms = max(120.0, min(200.0, pr_ms))
        else:
            pr_ms = state.pr_interval
        pr_sec = pr_ms / 1000.0


        p_sigma_sec = params.p.sigma if params.p else 0.024
        p_sigma = p_sigma_sec / rr_sec

        q_sigma_sec = params.q.sigma * qrs_duration_scale
        qrs_onset_sec = q_offset_sec - 2 * q_sigma_sec
        if rhythm == RhythmType.AVB2_I:
            # Keep P wave at a fixed PR interval of 160ms
            p_offset_sec = qrs_onset_sec - 0.160 + 2 * p_sigma_sec
            p_center = c_r + p_offset_sec / rr_sec
            # Shift QRS and T waves to the right by the prolongation
            delay_sec = (pr_ms - 160.0) / 1000.0
            delay_phase = delay_sec / rr_sec
            c_r += delay_phase
            q_center += delay_phase
            s_center += delay_phase
        elif rhythm == RhythmType.AVB2_II:
            # Keep P wave at a fixed PR interval of 180ms
            p_offset_sec = qrs_onset_sec - 0.180 + 2 * p_sigma_sec
            p_center = c_r + p_offset_sec / rr_sec
            # No shift for QRS/T because PR is constant
        else:
            p_offset_sec = qrs_onset_sec - pr_sec + 2 * p_sigma_sec
            p_center = c_r + p_offset_sec / rr_sec

        # Scale T wave to scale with sqrt(rr_sec) (Bazett's formula) and honor state.qt_interval
        if rhythm in (RhythmType.NSR, RhythmType.SINUS_BRADY, RhythmType.SINUS_TACHY):
            qt_ms = state.qt_interval * np.sqrt(rr_sec)
        else:
            qt_ms = state.qt_interval
        qt_sec = qt_ms / 1000.0
        qt_scale = qt_sec / 0.400

        t_offset_sec = (params.t.center - c_r) * qt_scale
        t_center = c_r + t_offset_sec / rr_sec
        t_sigma = (params.t.sigma * qt_scale) / rr_sec

        # Adaptive wave visibility: scale P and T amplitudes by rhythm + rate factors
        p_factor, t_factor = get_wave_visibility(rhythm, state.heart_rate)

        # AVB3: dissociated P waves
        if rhythm == RhythmType.AVB3:
            t_ac = self._atrial_clock
            p_phase = (1.25 * t_ac) % 1.0
            p_val = _gauss(p_phase, Wave(0.12 * p_factor, 0.15, 0.025))
        else:
            p_amp = (params.p.amp * p_factor) if params.p else 0.0
            p_val = _gauss(t, Wave(p_amp, p_center, p_sigma)) if params.p else 0.0

        # Torsades: rotate QRS amplitude with beat
        r_amp_mod = 1.0
        if rhythm == RhythmType.TORSADES:
            r_amp_mod = np.sin(self._torsades_axis)

        # Scale secondary deflections for LBBB / RBBB QRS complexes to match QRS scaling
        extra_r_val = 0.0
        if rhythm == RhythmType.LBBB:
            extra_center = c_r + (0.08 * qrs_duration_scale) / rr_sec
            extra_sigma = (0.024 * qrs_duration_scale) / rr_sec
            extra_r_val = _gauss(t, Wave(0.80, extra_center, extra_sigma))
        elif rhythm == RhythmType.RBBB:
            extra_center = c_r + (0.08 * qrs_duration_scale) / rr_sec
            extra_sigma = (0.018 * qrs_duration_scale) / rr_sec
            extra_r_val = _gauss(t, Wave(0.75, extra_center, extra_sigma))

        # Modulate entire complex by r_amp_mod for Torsades to rotate around baseline symmetrically
        q_amp = params.q.amp * r_amp_mod if rhythm == RhythmType.TORSADES else params.q.amp
        r_amp = params.r.amp * r_amp_mod * self._r_amp_factor * self._qrs_amp_var
        s_amp = params.s.amp * r_amp_mod if rhythm == RhythmType.TORSADES else params.s.amp
        t_amp = params.t.amp * r_amp_mod * t_factor * self._t_amp_factor if rhythm == RhythmType.TORSADES else params.t.amp * t_factor * self._t_amp_factor

        q_val = _gauss(t, Wave(q_amp, q_center, q_sigma))
        r_extra_width_scaled = params.qrs_extra_width / rr_sec
        r_val = _gauss(t, Wave(r_amp, c_r, r_sigma + r_extra_width_scaled)) + extra_r_val
        s_val = _gauss(t, Wave(s_amp, s_center, s_sigma))
        t_val = _gauss(t, Wave(t_amp, t_center, t_sigma))

        # Create scaled params for ST offset computation
        scaled_params = BeatParams(
            p=None,
            q=Wave(params.q.amp, q_center, q_sigma),
            r=Wave(params.r.amp, c_r, r_sigma),
            s=Wave(params.s.amp, s_center, s_sigma),
            t=Wave(params.t.amp, t_center, t_sigma)
        )
        st_offset = _st_offset(t, scaled_params, state, rr_sec)

        return p_val + q_val + r_val + s_val + t_val + st_offset

    def _sample_for_rhythm_or_special(
        self, t: float, params: BeatParams, state: ECGState, rhythm: RhythmType
    ) -> float:
        """Sample ordinary and non-PQRST rhythms through the same transition path."""
        rhythm = self._coerce_rhythm(rhythm)
        if rhythm == RhythmType.VF:
            return self._vf_sample()
        if rhythm == RhythmType.ASYSTOLE:
            # Generate subtle physiological monitor noise (under 0.05 mV)
            t_clk = self._vf_clock
            self._vf_clock += 1.0 / self.fs
            if not hasattr(self, '_asystole_drift'):
                self._asystole_drift = 0.0
            self._asystole_drift += np.random.normal(0, 0.001)
            self._asystole_drift = max(-0.015, min(0.015, self._asystole_drift))
            noise = (
                self._asystole_drift
                + 0.004 * np.sin(2 * np.pi * 50.0 * t_clk)
                + 0.005 * np.random.normal(0, 1.0)
            )
            return float(noise)
        sample = self._sample_for_rhythm(t, params, state, rhythm)
        if rhythm == RhythmType.AFIB:
            # Chaotic, non-periodic, continuously evolving fibrillatory waves (f-waves)
            t_ac = self._atrial_clock
            # Phase noise modulators to disrupt sine repetition
            phase_noise_1 = 0.25 * np.sin(2 * np.pi * 0.15 * t_ac) + np.random.normal(0, 0.04)
            phase_noise_2 = 0.20 * np.cos(2 * np.pi * 0.28 * t_ac) + np.random.normal(0, 0.04)
            # Low frequency amplitude modulator to drift the amplitude realistically
            amp_mod = 1.0 + 0.12 * np.sin(2 * np.pi * 0.12 * t_ac) + np.random.normal(0, 0.02)
            
            f_wave = amp_mod * (
                0.045 * np.sin(2 * np.pi * 6.2 * t_ac + phase_noise_1)
                + 0.035 * np.sin(2 * np.pi * 9.1 * t_ac + phase_noise_2)
                + 0.025 * np.sin(2 * np.pi * 12.8 * t_ac)
                + 0.015 * np.sin(2 * np.pi * 15.4 * t_ac)
            )
            sample += f_wave
            self._atrial_clock += 1.0 / self.fs
        elif rhythm == RhythmType.AFLUTTER:
            # Continuous Lead II sawtooth flutter waves at constant 300 bpm (5 Hz)
            t_ac = self._atrial_clock
            p_fl = (5.0 * t_ac) % 1.0
            amp_fl = 0.20
            if p_fl < 0.15:
                # Rapid upstroke
                fl_val = -amp_fl + 2.0 * amp_fl * (p_fl / 0.15)
            else:
                # Nearly linear descending limb
                fl_val = amp_fl - 2.0 * amp_fl * ((p_fl - 0.15) / 0.85)
            sample += fl_val
            self._atrial_clock += 1.0 / self.fs
        elif rhythm == RhythmType.AVB3:
            self._atrial_clock += 1.0 / self.fs
        return float(sample)

    def _transition_mix(self, transition: RhythmTransition) -> float:
        if transition.duration_s <= 0.0 or transition.fn == TransferFn.IMMEDIATE:
            return 1.0
        progress = min(max(transition.elapsed_s / transition.duration_s, 0.0), 1.0)
        match transition.fn:
            case TransferFn.LINEAR:
                return progress
            case TransferFn.EXPONENTIAL:
                return 1.0 - np.exp(-5.0 * progress)
            case TransferFn.SIGMOID:
                return 1.0 / (1.0 + np.exp(-10.0 * (progress - 0.5)))
            case _:
                return progress

    def _vf_sample(self) -> float:
        """Generate a chaotic, physiologically realistic VF waveform using dynamic noise."""
        t = self._vf_clock
        self._vf_clock += 1.0 / self.fs

        # Keep track of VF duration to automatically progress Coarse VF -> Fine VF -> Asystole
        if not hasattr(self, '_vf_duration_samples'):
            self._vf_duration_samples = 0
        self._vf_duration_samples += 1

        duration_s = self._vf_duration_samples / self.fs

        # Amplitude decay simulating cardiac arrest progression:
        # Coarse VF (first 60s): scale = 1.0
        # Fine VF (60s to 150s): scale decays to 0.15
        # Asystole (150s to 240s): scale decays to 0.0
        if duration_s < 60.0:
            amp_scale = 1.0
        elif duration_s < 150.0:
            amp_scale = 1.0 - 0.85 * ((duration_s - 60.0) / 90.0)
        elif duration_s < 240.0:
            amp_scale = 0.15 * (1.0 - (duration_s - 150.0) / 90.0)
        else:
            amp_scale = 0.0

        # Filtered random walk for phase/frequency perturbation (disrupts periodicity)
        if not hasattr(self, '_vf_phase_perturbation'):
            self._vf_phase_perturbation = 0.0
        self._vf_phase_perturbation += np.random.normal(0, 0.02)
        self._vf_phase_perturbation = max(-3.0, min(3.0, self._vf_phase_perturbation))

        # Dynamic amplitude modulator (disrupts amplitude uniformity)
        if not hasattr(self, '_vf_amp_modulator'):
            self._vf_amp_modulator = 1.0
        self._vf_amp_modulator += np.random.normal(0, 0.03)
        self._vf_amp_modulator = max(0.4, min(1.6, self._vf_amp_modulator))

        # Chaotic, non-periodic multi-frequency wave synthesis
        f_wave = amp_scale * self._vf_amp_modulator * (
            0.45 * np.sin(2 * np.pi * 4.6 * t + self._vf_phase_perturbation + 1.2 * np.sin(2 * np.pi * 0.7 * t))
            + 0.30 * np.sin(2 * np.pi * 6.8 * t + 0.8 * np.cos(2 * np.pi * 1.2 * t))
            + 0.15 * np.sin(2 * np.pi * 9.5 * t + np.random.normal(0, 0.05))
            + 0.08 * np.sin(2 * np.pi * 12.1 * t)
        )
        return float(f_wave)

    def _vf(self, n_samples: int) -> np.ndarray:
        """Ventricular fibrillation: chaotic oscillation."""
        return np.array([self._vf_sample() for _ in range(n_samples)], dtype=np.float32)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _gauss(t: float, wave: Wave | None) -> float:
    if wave is None or wave.amp == 0:
        return 0.0
    val = 0.0
    for offset in (-1.0, 0.0, 1.0):
        val += wave.amp * np.exp(-0.5 * ((t + offset - wave.center) / wave.sigma) ** 2)
    return val


def _st_offset(t: float, params: BeatParams, state: ECGState, rr_sec: float = 1.0) -> float:
    """Add a flat ST offset between S wave and T wave."""
    from ecg_state import RhythmType
    if state.rhythm in (RhythmType.ANT_STEMI, RhythmType.INF_STEMI, RhythmType.LAT_STEMI):
        elevation = state.st_elevation - state.st_depression
        if elevation == 0.0:
            elevation = 0.35
        mid = (params.s.center + params.t.center) / 2.0
        width = (params.t.center - params.s.center) * 0.45
        if (params.s.center - params.s.sigma) < t < (params.t.center + params.t.sigma):
            return elevation * np.exp(-0.5 * ((t - mid) / width) ** 2)
        return 0.0

    st_start = params.s.center + 2 * params.s.sigma
    t_end    = params.t.center + 2 * params.t.sigma
    if st_start < t < t_end:
        if state.rhythm in (RhythmType.AVB2_I, RhythmType.AVB2_II):
            elevation = 0.0
        elif state.rhythm == RhythmType.LBBB:
            elevation = -0.08 + (state.st_elevation - state.st_depression)
        elif state.rhythm == RhythmType.RBBB:
            elevation = -0.06 + (state.st_elevation - state.st_depression)
        else:
            elevation = state.st_elevation - state.st_depression
        width = 0.04 / rr_sec
        return elevation * np.exp(-0.5 * ((t - (st_start + t_end) / 2) / width) ** 2)
    return 0.0
