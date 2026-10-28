"""
Core ML classifier for PCR Melt Curve Analysis.
Handles unsupervised DBSCAN batch clustering, thermal drift compensation,
and Nearest-Neighbors classification of extracted Tm-Peaks.
"""

import functools
from collections.abc import Callable
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors


def validate_classification_inputs(
    func: Callable[..., dict[str, bool]],
) -> Callable[..., dict[str, bool]]:
    """
    Decorator to perform defensive input validation before executing the
    machine learning clustering logic.
    """

    @functools.wraps(func)
    def wrapper(
        self: Any,
        detected_peaks: list[float],
        target_names: list[str],
        expected_tms: list[float],
        tolerance: float = 0.5,
    ) -> dict[str, bool]:
        if len(target_names) != len(expected_tms):
            raise ValueError("Length of target_names and expected_tms must be equal.")
        return func(self, detected_peaks, target_names, expected_tms, tolerance)

    return wrapper


class ClusterClassifier:
    """
    Performs unsupervised machine learning (DBSCAN + NearestNeighbors) to categorize
    extracted Tm-Peaks into defined target clusters based on relative density,
    plate-wide thermal drift, and expected Tms.
    """

    def __init__(
        self,
        dbscan_eps: float = 0.6,
        dbscan_min_samples: int = 2,
        max_thermal_drift: float = 1.5,
    ) -> None:
        self.dbscan_eps = dbscan_eps
        self.dbscan_min_samples = dbscan_min_samples
        self.max_thermal_drift = max_thermal_drift

    def estimate_run_drift(
        self,
        channel_peaks: list[float],
        expected_tms: list[float],
        base_tolerance: float = 0.5,
    ) -> dict[str, Any]:
        """
        Executes unsupervised DBSCAN clustering across all detected Tm peaks of a channel
        in a PCR run to identify dense amplicon clusters, isolate noise/primer-dimer outliers,
        and estimate systematic matrix/buffer thermal drift.
        """
        if not channel_peaks or not expected_tms:
            return {
                "thermal_shift": 0.0,
                "adaptive_tolerance": base_tolerance,
                "cluster_centers": [],
                "outlier_peaks": [],
            }

        x_peaks = np.array(channel_peaks, dtype=float).reshape(-1, 1)
        eff_min_samples = self.dbscan_min_samples if len(channel_peaks) >= 4 else 1

        dbscan = DBSCAN(eps=self.dbscan_eps, min_samples=eff_min_samples)
        labels = dbscan.fit_predict(x_peaks)

        cluster_centers: list[float] = []
        cluster_spreads: list[float] = []
        shifts: list[float] = []
        weights: list[int] = []
        outlier_peaks: list[float] = [
            float(channel_peaks[i]) for i, lbl in enumerate(labels) if lbl == -1
        ]

        unique_labels = sorted(set(labels) - {-1})
        for lbl in unique_labels:
            members = x_peaks[labels == lbl].flatten()
            centroid = float(np.mean(members))
            spread = float(np.std(members))
            cluster_centers.append(centroid)
            cluster_spreads.append(spread)

            # Match cluster centroid to closest theoretical expected Tm
            diffs = [centroid - float(exp_tm) for exp_tm in expected_tms]
            closest_diff = min(diffs, key=abs)
            if abs(closest_diff) <= self.max_thermal_drift:
                shifts.append(float(closest_diff))
                weights.append(len(members))

        thermal_shift = float(np.average(shifts, weights=weights)) if shifts else 0.0
        max_spread = max(cluster_spreads) if cluster_spreads else 0.0
        adaptive_tolerance = float(
            np.clip(max(base_tolerance, 2.5 * max_spread), base_tolerance, 1.0)
        )

        return {
            "thermal_shift": thermal_shift,
            "adaptive_tolerance": adaptive_tolerance,
            "cluster_centers": cluster_centers,
            "outlier_peaks": outlier_peaks,
        }

    @validate_classification_inputs
    def classify_channel_targets(
        self,
        detected_peaks: list[float],
        target_names: list[str],
        expected_tms: list[float],
        tolerance: float = 1.5,
    ) -> dict[str, bool]:
        """
        Classifies detected PCR peaks against expected target temperatures using
        a Nearest Neighbors radius search with distance-ordered 1-to-1 peak assignment.

        :param detected_peaks: List of Tm peaks identified by the Analyzer.
        :param target_names: List of target assay names.
        :param expected_tms: List of theoretical Tms for the given targets.
        :param tolerance: Maximum temperature deviation (radius) to count as a match.
        :return: Dictionary mapping target_names to a boolean match status.
        """
        results: dict[str, bool] = {name: False for name in target_names}

        if not detected_peaks:
            return results

        x_detected = np.array(detected_peaks, dtype=float).reshape(-1, 1)
        x_expected = np.array(expected_tms, dtype=float).reshape(-1, 1)

        nn_model = NearestNeighbors(radius=tolerance)
        nn_model.fit(x_detected)

        distances, indices = nn_model.radius_neighbors(x_expected, return_distance=True)

        # Build candidate (distance, target_idx, peak_idx) pairs sorted by closest distance
        candidate_matches: list[tuple[float, int, int]] = []
        for target_idx, (dist_arr, idx_arr) in enumerate(zip(distances, indices)):
            for dist, peak_idx in zip(dist_arr, idx_arr):
                candidate_matches.append((float(dist), target_idx, int(peak_idx)))

        candidate_matches.sort(key=lambda item: item[0])

        assigned_targets: set[int] = set()
        assigned_peaks: set[int] = set()

        for _, target_idx, peak_idx in candidate_matches:
            if target_idx in assigned_targets or peak_idx in assigned_peaks:
                continue
            assigned_targets.add(target_idx)
            assigned_peaks.add(peak_idx)
            results[target_names[target_idx]] = True

        return results

    def classify_with_clustering_details(
        self,
        detected_peaks: list[float],
        target_names: list[str],
        expected_tms: list[float],
        tolerance: float = 0.5,
        thermal_shift: float = 0.0,
        outlier_peaks: list[float] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Performs drift-compensated classification and derives semantic cluster labels
        ('Wildtype', 'Drift_Compensated', 'Borderline_Escalated', 'Ambiguous_Outlier', 'Negative')
        along with escalation flags for senior validation.
        """
        shifted_peaks = [float(p - thermal_shift) for p in detected_peaks]
        matches = self.classify_channel_targets(
            detected_peaks=shifted_peaks,
            target_names=target_names,
            expected_tms=expected_tms,
            tolerance=tolerance,
        )

        outliers = set(outlier_peaks or [])
        has_unmatched_outliers = any(p in outliers for p in detected_peaks)
        details: dict[str, dict[str, Any]] = {}

        for target_name, exp_tm in zip(target_names, expected_tms):
            is_pos = matches.get(target_name, False)
            if is_pos and shifted_peaks:
                min_dist = min(abs(p - float(exp_tm)) for p in shifted_peaks)
                if min_dist > tolerance * 0.75:
                    label = "Borderline_Escalated"
                    needs_validation = True
                elif abs(thermal_shift) >= 0.25:
                    label = "Drift_Compensated"
                    needs_validation = abs(thermal_shift) >= 0.8
                else:
                    label = "Wildtype"
                    needs_validation = False
            else:
                if detected_peaks and has_unmatched_outliers:
                    label = "Ambiguous_Outlier"
                    needs_validation = True
                elif detected_peaks:
                    label = "Unassigned_Peak"
                    needs_validation = True
                else:
                    label = "Negative"
                    needs_validation = False

            details[target_name] = {
                "is_positive": is_pos,
                "cluster_label": label,
                "requires_senior_validation": needs_validation,
            }

        return details
