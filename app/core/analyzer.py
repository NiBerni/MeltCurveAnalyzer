from typing import Any

import numpy as np
from loguru import logger
from scipy.signal import find_peaks, savgol_filter
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve


class MeltCurveAnalyzer:
    """
    Orchestrates the signal processing pipeline strictly sequentially for a single, isolated channel.
    """

    def __init__(
        self,
        relative_height_threshold: float = 0.15,
        prominence_factor: float = 5.0,
        savgol_window: int = 15,
        savgol_polyorder: int = 3,
        als_lam: float = 1e4,
        als_p: float = 0.05,
        als_niter: int = 10,
    ) -> None:
        self.relative_height_threshold = relative_height_threshold
        self.prominence_factor = prominence_factor
        self.savgol_window = savgol_window
        self.savgol_polyorder = savgol_polyorder
        self.als_lam = als_lam
        self.als_p = als_p
        self.als_niter = als_niter

    def _als_baseline(self, y: np.ndarray) -> np.ndarray:
        """
        Applies Asymmetric Least Square (ALS) smoothing algorithm to remove background drift.
        Optimized with scipy.sparse matrix operations for millisecond performance.
        """
        L = len(y)
        D = diags([1, -2, 1], [0, 1, 2], shape=(L - 2, L))

        w = np.ones(L)
        z = np.copy(y)
        for _ in range(self.als_niter):
            W = diags(w, 0, shape=(L, L))
            Z = W + self.als_lam * D.transpose().dot(D)
            z = spsolve(Z, w * y)
            w = self.als_p * (y > z) + (1 - self.als_p) * (y < z)
        return z

    def analyze(
        self,
        temperatures: list[float],
        patient_rfu: list[float],
        ntc_rfu: list[float] | None,
    ) -> dict[str, Any]:
        """
        Executes the mathematical signal processing pipeline for a single channel.
        """
        requires_senior_validation = False
        processed_rfu = np.array(patient_rfu)
        temps_arr = np.array(temperatures)
        delta_t = temps_arr[1] - temps_arr[0] if len(temps_arr) > 1 else 0.1

        patient_max_signal = np.max(processed_rfu) - np.min(processed_rfu)

        # 1. NTC Validation & Blanking
        if ntc_rfu is None or len(ntc_rfu) == 0 or len(ntc_rfu) != len(patient_rfu):
            requires_senior_validation = True
            logger.warning(
                "NTC is None, empty, or length missmatch. Skipping blanking, triggering escalation."
            )
        else:
            ntc_arr = np.array(ntc_rfu)
            # Evaluate NTC contamination
            ntc_deriv = -savgol_filter(
                ntc_arr,
                window_length=self.savgol_window,
                polyorder=self.savgol_polyorder,
                deriv=1,
                delta=delta_t,
            )
            ntc_noise_floor = patient_max_signal * 0.025
            ntc_peaks, _ = find_peaks(
                ntc_deriv, height=ntc_noise_floor, prominence=self.prominence_factor
            )

            if len(ntc_peaks) > 0:
                requires_senior_validation = True
                logger.warning(
                    f"NTC contamination detected ({len(ntc_peaks)} peaks). Skipping blanking."
                )
            else:
                processed_rfu = processed_rfu - ntc_arr

        # 2. Baseline Correction
        baseline = self._als_baseline(processed_rfu)
        corrected_rfu = processed_rfu - baseline

        # 3. Savitzky-Golay Filter
        deriv = savgol_filter(
            corrected_rfu,
            window_length=self.savgol_window,
            polyorder=self.savgol_polyorder,
            deriv=1,
            delta=delta_t,
        )
        processed_curve = -deriv

        # 4. Peak Detection
        max_height = np.max(processed_curve)
        height_thresh = (
            max_height * self.relative_height_threshold if max_height > 0 else 0
        )
        peaks, _ = find_peaks(
            processed_curve,
            height=float(height_thresh),
            prominence=self.prominence_factor,
        )  # type:ignore
        tm_peaks = temps_arr[peaks].tolist()

        return {
            "tm_peaks": tm_peaks,
            "processed_curve": processed_curve.tolist(),
            "requires_senior_validation": requires_senior_validation,
        }
