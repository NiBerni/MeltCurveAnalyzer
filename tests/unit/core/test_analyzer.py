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
    The computed derivative of these yields a Gaussian peak at Tm = 82.5 °C.
    """
    temps = np.array(temperatures)
    amplitude = 1000.0
    steepness = 1.5
    tm_peak = 82.5
    background = 50.0

    # Inverse logistic function simulating a raw PCR melt curve fluorescence drop
    rfu = amplitude / (1.0 + np.exp(steepness * (temps - tm_peak))) + background
    return rfu.tolist()


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


@pytest.fixture
def patient_rfu_overlapping(temperatures: list[float]) -> list[float]:
    """
    Generates a synthetic PCR melt curve with two heavily overlapping peaks.
    The main peak at 82.0 °C and a smaller shoulder peak at 84.5 °C.
    """
    temps = np.array(temperatures)

    # Peak 1 (Main)
    amp1, steep1, tm1 = 1000.0, 1.5, 82.0
    rfu1 = amp1 / (1.0 + np.exp(steep1 * (temps - tm1)))

    # Peak 2 (Shoulder)
    amp2, steep2, tm2 = 400.0, 1.8, 84.5
    rfu2 = amp2 / (1.0 + np.exp(steep2 * (temps - tm2)))

    background = 50.0
    return (rfu1 + rfu2 + background).tolist()


def test_analyzer_initialization_defaults(analyzer: MeltCurveAnalyzer) -> None:
    """Verifies that the MeltCurveAnalyzer initializes with the correct default configuration."""
    assert analyzer.relative_height_threshold == 0.15
    assert analyzer.prominence_factor == 5.0
    assert analyzer.savgol_window == 15
    assert analyzer.savgol_polyorder == 3
    assert analyzer.als_lam == 1e4
    assert analyzer.als_p == 0.05
    assert analyzer.als_niter == 10


def test_analyzer_initialization_custom_values() -> None:
    """Verifies that the MeltCurveAnalyzer correctly assigns custom configuration parameters."""
    custom_analyzer = MeltCurveAnalyzer(
        relative_height_threshold=0.25,
        prominence_factor=6.0,
        savgol_window=11,
        savgol_polyorder=2,
        als_lam=1e5,
        als_p=0.01,
        als_niter=20,
    )

    assert custom_analyzer.relative_height_threshold == 0.25
    assert custom_analyzer.prominence_factor == 6.0
    assert custom_analyzer.savgol_window == 11
    assert custom_analyzer.savgol_polyorder == 2
    assert custom_analyzer.als_lam == 1e5
    assert custom_analyzer.als_p == 0.01
    assert custom_analyzer.als_niter == 20


@pytest.mark.parametrize(
    "invalid_kwargs, expected_exception",
    [
        ({"relative_height_threshold": "high"}, TypeError),
        ({"relative_height_threshold": -0.1}, ValueError),
        ({"savgol_window": 14}, ValueError),  # SavGol window must typically be odd
        ({"savgol_window": "fifteen"}, TypeError),
        ({"savgol_polyorder": "three"}, TypeError),
        ({"als_niter": -5}, ValueError),
        ({"als_niter": 5.5}, TypeError),
    ],
)
def test_analyzer_initialization_type_enforcement(
    invalid_kwargs: dict[str, str | float | int], expected_exception: type[Exception]
) -> None:
    """Validates that initialization enforces correct types and boundary constraints."""
    with pytest.raises(expected_exception):
        MeltCurveAnalyzer(**invalid_kwargs)


def test_analyzer_complete_pipeline_success(
    analyzer: MeltCurveAnalyzer,
    temperatures: list[float],
    patient_rfu_valid: list[float],
    ntc_rfu: list[float],
) -> None:
    """Validates successful end-to-end execution strictly sequentially isolated.
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


@pytest.mark.parametrize("missing_kwargs", [{"temperatures": []}, {"patient_rfu": []}])
def test_analyzer_missing_arrays_raises_error(
    analyzer: MeltCurveAnalyzer,
    temperatures: list[float],
    patient_rfu_valid: list[float],
    missing_kwargs: dict[str, list[float]],
) -> None:
    """Validates that empty input arrays raise the appropriate ValueErrors during processing."""
    kwargs = {
        "temperatures": temperatures,
        "patient_rfu": patient_rfu_valid,
        "ntc_rfu": None,
    }
    kwargs.update(missing_kwargs)

    with pytest.raises(ValueError):
        analyzer.analyze(**kwargs)


def test_analyzer_deconvolutes_overlapping_peaks(
    analyzer: MeltCurveAnalyzer,
    temperatures: list[float],
    patient_rfu_overlapping: list[float],
) -> None:
    """
    This test forces the implementation of Gaussian Deconvolution.
    A simple threshold approach will fail to separate the shoulder peak.
    """
    result = analyzer.analyze(
        temperatures=temperatures, patient_rfu=patient_rfu_overlapping, ntc_rfu=None
    )

    peaks = result["tm_peaks"]

    assert len(peaks) == 2, f"Expected 2 peaks, but found {len(peaks)}"

    assert any(81.8 <= peak <= 82.2 for peak in peaks), (
        "Main peak (82.0) not found or inaccurate"
    )
    assert any(84.3 <= peak <= 84.7 for peak in peaks), (
        "Shoulder peak (84.5) not found or inaccurate"
    )
