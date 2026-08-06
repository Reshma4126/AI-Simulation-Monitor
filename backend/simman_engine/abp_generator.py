from __future__ import annotations
import numpy as np

def abp_equation(
    t: np.ndarray,
    systolic_pressure: float,
    diastolic_pressure: float,
    rise_time: float,
    notch_depth: float,
    notch_time: float,
    notch_sigma: float,
) -> np.ndarray:
    safe_rise_time = max(rise_time, 1e-6)
    safe_sigma = max(notch_sigma, 1e-6)

    # Standard clinical ABP pulse equation from formulas.py
    systolic_term = (t / safe_rise_time) * np.exp(1.0 - (t / safe_rise_time))
    notch_term = notch_depth * np.exp(-((t - notch_time) ** 2) / (2.0 * safe_sigma**2))
    return diastolic_pressure + (systolic_pressure - diastolic_pressure) * systolic_term - notch_term
