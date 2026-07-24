import numpy as np
import pytest

from app.core.analyzer import MeltCurveAnalyzer


@pytest.fixture
def analyzer() -> MeltCurveAnalyzer:
    """Returns an instance of the Core MathCurveAnalyzer"""
    return MeltCurveAnalyzer()


@pytest.fixture
def temperatures() -> list[float]:
    """Generates a synthetic temperature array from 65.0 to 95.0 °C in 0.1 steps."""
    return np.arange(65.0, 95.1, 0.1).tolist()


@pytest.fixture
def ntc_rfu(temperatures: list[float]) -> list[float]:
    """Generates a mock No Template Control (NTC) RFU baseline with minor random noise"""
    return (
        np.linspace(100.0, 90.0, len(temperatures))
        + np.random.normal(0, 1.0, len(temperatures))
    ).tolist()


@pytest.fixture
def patient_rfu_valid(temperatures: list[float]) -> list[float]:
    """
    Generates a synthetic PCR melt curve (sigmoidal fluorescence drop).
    The computed derivative of this yields a Gaussian peak at Tm = 82.5 °C.
    """
    temps = np.array(temperatures)
    amplitude = 1000.0
    steepness = 1.5
    tm_peak = 82.5
    background = 50.0

    # Inverse logistic function simulating a raw PCR melt curve fluorescence drop
    rfu = amplitude / (1.0 + np.exp(steepness * (temps - tm_peak))) + background
    return rfu.tolist()


def test_analyzer_complete_pipeline_success(
    analyzer: MeltCurveAnalyzer,
    temperatures: list[float],
    patient_rfu_valid: list[float],
    ntc_rfu: list[float],
) -> None:
    """Validates successful ent-to-end execution strictly sequentially isolated.
    (Blanking -> ALS -> SavGol -> Gauss-Fit).
    """
    result = analyzer.analyze(
        temperatures=temperatures, patient_rfu=patient_rfu_valid, ntc_rfu=ntc_rfu
    )

    assert isinstance(result, dict)
    assert result["requires_senior_validation"] is False
    assert len(result["processed_curve"]) == len(temperatures)
    assert len(result["tm_peaks"]) > 0
    assert all(isinstance(peak, float) for peak in result["tm_peaks"])


@pytest.mark.parametrize(
    "invalid_ntc",
    [
        None,
        [],
        [10.0, 15.0],
    ],
)
def test_analyzer_invalid_ntc_triggers_escalation(
    analyzer: MeltCurveAnalyzer,
    temperatures: list[float],
    patient_rfu_valid: list[float],
    invalid_ntc: list[float],
) -> None:
    """
    Verifies that if NTC is missing or invalid, blanking is skipped, ALS handles the baseline directly,
    and requires_senior_validation is flagged as True.
    """
    result = analyzer.analyze(
        temperatures=temperatures, patient_rfu=patient_rfu_valid, ntc_rfu=invalid_ntc
    )

    assert result["requires_senior_validation"] is True
    assert len(result["processed_curve"]) == len(temperatures)
    assert isinstance(result["tm_peaks"], list)


@pytest.fixture
def ntc_rfu_contaminated(temperatures: list[float]) -> list[float]:
    """
    Generates a contaminated NTC with a distinct peak (Tm = 75.0°C).
    Simulates cross-contamination or primer-dimers in the water control.
    """
    temps = np.array(temperatures)
    amplitude = 400.0
    steepness = 1.5
    tm_peak = 75.0
    background = 50.0

    # Inverse logistic function simulating a contamination melt curve
    rfu = amplitude / (1.0 + np.exp(steepness * (temps - tm_peak))) + background
    return rfu.tolist()


def test_analyzer_contaminated_ntc_triggers_escalation(
    analyzer: MeltCurveAnalyzer,
    temperatures: list[float],
    patient_rfu_valid: list[float],
    ntc_rfu_contaminated: list[float],
) -> None:
    """
    Verifies that an NTC with a detectable peak (contamination) is actively rejected for blanking.
    The system must fall back to ALS baseline correction and trigger senior validation
    """
    result = analyzer.analyze(
        temperatures=temperatures,
        patient_rfu=patient_rfu_valid,
        ntc_rfu=ntc_rfu_contaminated,
    )
    assert result["requires_senior_validation"] is True
    peaks = result["tm_peaks"]
    assert len(peaks) >= 1
    assert any(82.0 <= peak <= 83.0 for peak in peaks)


def test_analyzer_sav_gol_derivate_shape(
    analyzer: MeltCurveAnalyzer,
    temperatures: list[float],
    patient_rfu_valid: list[float],
) -> None:
    """
    Ensures the computed derivative curve (-dRFU/dT) via Savitzky-Golay matches expected dimensions and smoothing
    properties.
    """
    result = analyzer.analyze(
        temperatures=temperatures, patient_rfu=patient_rfu_valid, ntc_rfu=None
    )

    processed: list[float] = result["processed_curve"]
    assert len(processed) == len(temperatures)

    max_peak_value = max(processed)
    min_value = min(processed)

    assert max_peak_value > 0.0
    assert max_peak_value > abs(min_value)


def test_analyzer_gaussian_peak_detection(
    analyzer: MeltCurveAnalyzer,
    temperatures: list[float],
    patient_rfu_valid: list[float],
) -> None:
    """
    Tests the correct extraction of known synthetic Tm peaks via Gaussian Deconvolution.
    Verifies a synthetic peak at 82.5°C is accurately detected.
    """
    result = analyzer.analyze(
        temperatures=temperatures, patient_rfu=patient_rfu_valid, ntc_rfu=None
    )

    peaks = result["tm_peaks"]
    assert len(peaks) >= 1

    detected_expected_peak = any(82.0 <= peak <= 83.0 for peak in peaks)
    assert detected_expected_peak is True
