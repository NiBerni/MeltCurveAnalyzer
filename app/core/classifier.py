"""
Core ML classifier for PCR Melt Curve Analysis.
Handles unsupervised classification of extracted Tm-Peaks.
"""

import functools
from collections.abc import Callable
from typing import Any

import numpy as np
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
        tolerance: float = 1.5,
    ) -> dict[str, bool]:
        if len(target_names) != len(expected_tms):
            raise ValueError("Length of target_names and expected_tms must be equal.")
        return func(self, detected_peaks, target_names, expected_tms, tolerance)

    return wrapper


class ClusterClassifier:
    """
    Performs unsupervised machine learning to categorize extracted Tm-Peaks
    into defined target clusters based on relative density and expected Tms.
    """

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
        a Nearest Neighbors radius search.

        :param detected_peaks: List of Tm peaks identified by the Analyzer.
        :param target_names: List of target assay names.
        :param expected_tms: List of theoretical Tms for the given targets.
        :param tolerance: Maximum temperature deviation (radius) to count as a match.
        :return: Dictionary mapping target_names to a boolean match status.
        """
        # Initialize results to False
        results: dict[str, bool] = {name: False for name in target_names}

        # Early exit for empty peak arrays to prevent sklearn fitting errors
        if not detected_peaks:
            return results

        # Transform 1D lists into 2D numpy arrays for sklearn compatibility
        x_detected = np.array(detected_peaks).reshape(-1, 1)
        x_expected = np.array(expected_tms).reshape(-1, 1)

        # Initialize and fit NearestNeighbors
        nn_model = NearestNeighbors(radius=tolerance)
        nn_model.fit(x_detected)

        # Query the model: returns distances and indices of neighbors within the radius
        _, indices = nn_model.radius_neighbors(x_expected)

        # Map results back to the target names
        for i, target_name in enumerate(target_names):
            if len(indices[i]) > 0:
                results[target_name] = True

        return results
