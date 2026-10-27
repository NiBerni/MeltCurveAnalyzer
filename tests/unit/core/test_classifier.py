from collections.abc import Generator

import pytest

from app.core.classifier import ClusterClassifier


@pytest.fixture
def classifier() -> Generator[ClusterClassifier, None, None]:
    """Provides a fresh instance of ClusterClassifier for each test."""
    yield ClusterClassifier()


def test_classify_all_targets_positive(classifier: ClusterClassifier) -> None:
    detected_peaks: list[float] = [70.2, 75.1]
    target_names: list[str] = ["Target A", "Target B"]
    expected_tms: list[float] = [70.0, 75.0]
    tolerance: float = 0.5

    result: dict[str, bool] = classifier.classify_channel_targets(
        detected_peaks=detected_peaks,
        target_names=target_names,
        expected_tms=expected_tms,
        tolerance=tolerance,
    )

    assert result == {"Target A": True, "Target B": True}


def test_classify_partial_match(classifier: ClusterClassifier) -> None:
    detected_peaks: list[float] = [70.1]
    target_names: list[str] = ["Target A", "Target B"]
    expected_tms: list[float] = [70.0, 75.0]

    result: dict[str, bool] = classifier.classify_channel_targets(
        detected_peaks=detected_peaks,
        target_names=target_names,
        expected_tms=expected_tms,
    )

    assert result == {"Target A": True, "Target B": False}


def test_classify_all_negative(classifier: ClusterClassifier) -> None:
    detected_peaks: list[float] = [60.0]
    target_names: list[str] = ["Target A", "Target B"]
    expected_tms: list[float] = [70.0, 75.0]

    result: dict[str, bool] = classifier.classify_channel_targets(
        detected_peaks=detected_peaks,
        target_names=target_names,
        expected_tms=expected_tms,
    )

    assert result == {"Target A": False, "Target B": False}


def test_classify_match_with_artefact(classifier: ClusterClassifier) -> None:
    detected_peaks: list[float] = [60.5, 75.1]
    target_names: list[str] = ["Target A", "Target B"]
    expected_tms: list[float] = [70.0, 75.0]

    result: dict[str, bool] = classifier.classify_channel_targets(
        detected_peaks=detected_peaks,
        target_names=target_names,
        expected_tms=expected_tms,
    )

    assert result == {"Target A": False, "Target B": True}


def test_classify_channel_targets_length_mismatch(
    classifier: ClusterClassifier,
) -> None:
    detected_peaks: list[float] = [70.0]
    target_names: list[str] = ["Target A", "Target B"]
    expected_tms: list[float] = [70.0]

    with pytest.raises(
        ValueError, match="Length of target_names and expected_tms must be equal."
    ):
        classifier.classify_channel_targets(
            detected_peaks=detected_peaks,
            target_names=target_names,
            expected_tms=expected_tms,
        )


@pytest.mark.parametrize(
    "detected, expected_result",
    [
        ([], {"Target A": False, "Target B": False}),
        ([70.5, 75.5], {"Target A": True, "Target B": True}),
        ([69.5, 74.5], {"Target A": True, "Target B": True}),
        ([70.51, 75.51], {"Target A": False, "Target B": False}),
        ([69.49, 74.49], {"Target A": False, "Target B": False}),
    ],
)
def test_classify_channel_targets_tolerance_boundaries(
    classifier: ClusterClassifier,
    detected: list[float],
    expected_result: dict[str, bool],
) -> None:
    target_names: list[str] = ["Target A", "Target B"]
    expected_tms: list[float] = [70.0, 75.0]
    tolerance: float = 0.5

    result: dict[str, bool] = classifier.classify_channel_targets(
        detected_peaks=detected,
        target_names=target_names,
        expected_tms=expected_tms,
        tolerance=tolerance,
    )

    assert result == expected_result


def test_classify_single_peak_between_overlapping_targets_assigns_closest_only(
    classifier: ClusterClassifier,
) -> None:
    """
    Verifies 1-to-1 distance-ordered peak assignment: a single detected peak at 70.3 °C
    lying within the 0.5 °C radius of both Target A (70.0 °C, dist=0.3) and Target B (70.7 °C, dist=0.4)
    must only activate the closest target (Target A).
    """
    result = classifier.classify_channel_targets(
        detected_peaks=[70.3],
        target_names=["Target A", "Target B"],
        expected_tms=[70.0, 70.7],
        tolerance=0.5,
    )
    assert result == {"Target A": True, "Target B": False}


def test_estimate_run_drift_dbscan_clustering_and_outliers(
    classifier: ClusterClassifier,
) -> None:
    """
    Verifies that DBSCAN groups plate-wide peaks into amplicon clusters, estimates
    systematic thermal matrix shift (+0.6 °C), and isolates primer-dimer noise outliers (62.1 °C).
    """
    pooled_peaks = [70.58, 70.62, 70.60, 75.59, 75.61, 62.1]
    expected_tms = [70.0, 75.0]

    drift_stats = classifier.estimate_run_drift(
        channel_peaks=pooled_peaks,
        expected_tms=expected_tms,
        base_tolerance=0.5,
    )

    assert drift_stats["thermal_shift"] == pytest.approx(0.6, abs=0.05)
    assert len(drift_stats["cluster_centers"]) == 2
    assert 62.1 in drift_stats["outlier_peaks"]
    assert 0.5 <= drift_stats["adaptive_tolerance"] <= 1.0


def test_estimate_run_drift_empty_inputs(classifier: ClusterClassifier) -> None:
    """Verifies safe fallback when no peaks or expected Tms are present."""
    stats = classifier.estimate_run_drift(channel_peaks=[], expected_tms=[70.0])
    assert stats["thermal_shift"] == 0.0
    assert stats["adaptive_tolerance"] == 0.5
    assert stats["cluster_centers"] == []
    assert stats["outlier_peaks"] == []


def test_classify_with_clustering_details_semantic_labels(
    classifier: ClusterClassifier,
) -> None:
    """
    Verifies that classify_with_clustering_details assigns accurate semantic cluster labels
    ('Wildtype', 'Drift_Compensated', 'Borderline_Escalated', 'Ambiguous_Outlier', 'Negative')
    and sets requires_senior_validation appropriately.
    """
    # 1. Wildtype match (minimal drift, close to expected Tm)
    wt_details = classifier.classify_with_clustering_details(
        detected_peaks=[70.1],
        target_names=["Target A", "Target B"],
        expected_tms=[70.0, 75.0],
        tolerance=0.5,
        thermal_shift=0.0,
    )
    assert wt_details["Target A"]["is_positive"] is True
    assert wt_details["Target A"]["cluster_label"] == "Wildtype"
    assert wt_details["Target A"]["requires_senior_validation"] is False

    # 2. Drift_Compensated match (systematic shift >= 0.25 °C)
    drift_details = classifier.classify_with_clustering_details(
        detected_peaks=[70.6],
        target_names=["Target A"],
        expected_tms=[70.0],
        tolerance=0.5,
        thermal_shift=0.6,
    )
    assert drift_details["Target A"]["is_positive"] is True
    assert drift_details["Target A"]["cluster_label"] == "Drift_Compensated"
    assert drift_details["Target A"]["requires_senior_validation"] is False

    # 3. Borderline_Escalated match (distance > 75% of tolerance)
    borderline_details = classifier.classify_with_clustering_details(
        detected_peaks=[70.45],
        target_names=["Target A"],
        expected_tms=[70.0],
        tolerance=0.5,
        thermal_shift=0.0,
    )
    assert borderline_details["Target A"]["is_positive"] is True
    assert borderline_details["Target A"]["cluster_label"] == "Borderline_Escalated"
    assert borderline_details["Target A"]["requires_senior_validation"] is True

    # 4. Ambiguous_Outlier (unmatched peak flagged as DBSCAN outlier)
    outlier_details = classifier.classify_with_clustering_details(
        detected_peaks=[62.1],
        target_names=["Target A"],
        expected_tms=[70.0],
        tolerance=0.5,
        thermal_shift=0.0,
        outlier_peaks=[62.1],
    )
    assert outlier_details["Target A"]["is_positive"] is False
    assert outlier_details["Target A"]["cluster_label"] == "Ambiguous_Outlier"
    assert outlier_details["Target A"]["requires_senior_validation"] is True
