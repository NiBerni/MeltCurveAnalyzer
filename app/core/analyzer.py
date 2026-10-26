import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import numpy as np
from loguru import logger
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, savgol_filter
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve


def log_performance(func: Callable[..., Any]) -> Callable[..., Any]:
    """Custom decorator to monitor performance of computationally heavy matrix operations."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"Execution of {func.__name__} took {elapsed_ms:.2f} ms")
        return result

    return wrapper


class MeltCurveAnalyzer:
    """
    Orchestrates the signal processing pipeline strictly sequentially for a single, isolated channel.
    Executes Blanking -> Savitzky-Golay Derivative (-dRFU/dT) -> ALS Baseline -> Gaussian Deconvolution.
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

    @property
    def relative_height_threshold(self) -> float:
        return self._relative_height_threshold

    @relative_height_threshold.setter
    def relative_height_threshold(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("relative_height_threshold must be a float.")
        if value < 0:
            raise ValueError("relative_height_threshold must be positive.")
        self._relative_height_threshold = float(value)

    @property
    def savgol_window(self) -> int:
        return self._savgol_window

    @savgol_window.setter
    def savgol_window(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("savgol_window must be an integer.")
        if value % 2 == 0 or value < 3:
            raise ValueError("savgol_window must be an odd integer >= 3.")
        self._savgol_window = value

    @property
    def savgol_polyorder(self) -> int:
        return self._savgol_polyorder

    @savgol_polyorder.setter
    def savgol_polyorder(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("savgol_polyorder must be an integer.")
        if value < 1:
            raise ValueError("savgol_polyorder must be an integer >= 1.")
        self._savgol_polyorder = value

    @property
    def als_niter(self) -> int:
        return self._als_niter

    @als_niter.setter
    def als_niter(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("als_niter must be an integer.")
        if value <= 0:
            raise ValueError("als_niter must be strictly positive.")
        self._als_niter = value

    @property
    def prominence_factor(self) -> float:
        return self._prominence_factor

    @prominence_factor.setter
    def prominence_factor(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("prominence_factor must be a float.")
        self._prominence_factor = float(value)

    @property
    def als_lam(self) -> float:
        return self._als_lam

    @als_lam.setter
    def als_lam(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("als_lam must be a float.")
        self._als_lam = float(value)

    @property
    def als_p(self) -> float:
        return self._als_p

    @als_p.setter
    def als_p(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("als_p must be a float.")
        self._als_p = float(value)

    @staticmethod
    def _gaussian_sum(x: np.ndarray, *params: float) -> np.ndarray:
        """
        Evaluates a composite of n Gaussian curves to enable shoulder-peak separation.
        Params layout: [amp_1, mu_1, sigma_1, amp_2, mu_2, sigma_2, ...]
        """
        y = np.zeros_like(x)
        for i in range(0, len(params), 3):
            amp = params[i]
            mu = params[i + 1]
            sigma = params[i + 2]
            y += amp * np.exp(-((x - mu) ** 2) / (2 * sigma**2))
        return y

    @log_performance
    def _als_baseline(self, y: np.ndarray) -> np.ndarray:
        """
        Applies Asymmetric Least Square (ALS) smoothing algorithm to remove background drift
        from a positive peak spectrum (-dRFU/dT).
        Optimized with scipy.sparse matrix operations for millisecond performance.
        """
        L = len(y)
        if L < 3:
            return np.zeros_like(y)
        D = diags([1, -2, 1], [0, 1, 2], shape=(L - 2, L), dtype=float)
        D_csr = D.tocsr()
        w = np.ones(L)
        z = np.copy(y)

        for _ in range(self.als_niter):
            W = diags(w, 0, shape=(L, L))
            Z = W + self.als_lam * D_csr.transpose().dot(D)
            z = spsolve(Z, w * y)
            w = self.als_p * (y > z) + (1 - self.als_p) * (y < z)

        return z

    @log_performance
    def analyze(
        self,
        temperatures: list[float],
        patient_rfu: list[float],
        ntc_rfu: list[float] | None = None,
    ) -> dict[str, Any]:
        """
        Executes the mathematical signal processing pipeline for a single channel.
        """
        # Guard Clauses
        if not temperatures or not patient_rfu:
            raise ValueError(
                "Input arrays 'temperatures' and 'patient_rfu' cannot be empty."
            )
        if len(temperatures) != len(patient_rfu):
            raise ValueError(
                "Length mismatch between 'temperatures' and 'patient_rfu'."
            )

        requires_senior_validation = False
        processed_rfu = np.array(patient_rfu, dtype=float)
        temps_arr = np.array(temperatures, dtype=float)

        diffs = np.diff(temps_arr)
        raw_delta_t = float(np.median(diffs)) if len(diffs) > 0 else 0.1
        delta_t = raw_delta_t if raw_delta_t > 0 else 0.1

        # Adapt Savitzky-Golay window safely for short arrays
        n_points = len(temps_arr)
        eff_window = min(
            self.savgol_window, n_points if n_points % 2 == 1 else n_points - 1
        )
        eff_poly = min(self.savgol_polyorder, max(1, eff_window - 1))

        # 1. NTC Validation & Blanking
        if not ntc_rfu or len(ntc_rfu) != len(patient_rfu):
            requires_senior_validation = True
            logger.warning(
                "NTC is None, empty, or length mismatch. Skipping blanking, triggering escalation."
            )
        else:
            ntc_arr = np.array(ntc_rfu, dtype=float)
            if eff_window >= 3:
                ntc_deriv = -savgol_filter(
                    ntc_arr,
                    window_length=eff_window,
                    polyorder=eff_poly,
                    deriv=1,
                    delta=delta_t,
                )
            else:
                ntc_deriv = -np.gradient(ntc_arr, delta_t)

            # Intrinsic NTC noise threshold (independent of patient signal amplitude)
            median_deriv = float(np.median(ntc_deriv))
            mad_deriv = float(np.median(np.abs(ntc_deriv - median_deriv)))
            robust_sigma = 1.4826 * mad_deriv
            ntc_noise_floor = max(
                median_deriv + 6.0 * robust_sigma, self.prominence_factor * 5.0
            )
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

        # 2. Savitzky-Golay Filter (1st Derivative Extraction: -dRFU/dT)
        if eff_window >= 3:
            raw_deriv = -savgol_filter(
                processed_rfu,
                window_length=eff_window,
                polyorder=eff_poly,
                deriv=1,
                delta=delta_t,
            )
        else:
            raw_deriv = -np.gradient(processed_rfu, delta_t)

        # 3. ALS Baseline Correction on the positive derivative peak spectrum
        baseline = self._als_baseline(raw_deriv)
        processed_curve = raw_deriv - baseline

        # 4. Peak Detection & Gaussian Deconvolution
        max_height = float(np.max(processed_curve))
        height_thresh = (
            max_height * self.relative_height_threshold if max_height > 0 else 0.0
        )

        # Initial approximate peaks
        initial_peaks, _ = find_peaks(
            processed_curve,
            height=height_thresh,
            prominence=self.prominence_factor,
        )

        tm_peaks: list[float] = []

        if len(initial_peaks) > 0:
            guess = []
            lower_bounds = []
            upper_bounds = []
            # Seed the Gaussian optimizer with find_peaks output
            for p in initial_peaks:
                amp_guess = float(processed_curve[p])
                mu_guess = float(temps_arr[p])
                sigma_guess = 1.0
                guess.extend([amp_guess, mu_guess, sigma_guess])

                lower_bounds.extend([0.0, mu_guess - 2.0, 0.1])
                upper_bounds.extend([np.inf, mu_guess + 2.0, 5.0])

            try:
                # Deconvolute overlapping peaks
                popt, _ = curve_fit(
                    self._gaussian_sum,
                    temps_arr,
                    processed_curve,
                    p0=guess,
                    bounds=(lower_bounds, upper_bounds),
                    maxfev=2000,
                )
                # Extract optimized Tms (means of the fitted Gaussians)
                tm_peaks = sorted([float(popt[i + 1]) for i in range(0, len(popt), 3)])
            except (RuntimeError, ValueError) as e:
                logger.warning(f"Gaussian deconvolution failed to converge: {e}")
                # Fallback to simple indexed peaks on failure
                tm_peaks = temps_arr[initial_peaks].tolist()

        return {
            "tm_peaks": tm_peaks,
            "processed_curve": processed_curve.tolist(),
            "requires_senior_validation": requires_senior_validation,
        }
