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
    expected_tms: list[float] = [70.0]  # Missing expected Tm for Target B

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
