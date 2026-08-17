import uuid
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest

try:
    from app.services.analysis_service import AnalysisService
except ImportError:

    class AnalysisService:
        def __init__(
            self,
            parser: Any,
            analyzer: Any,
            classifier: Any,
            run_repo: Any,
            result_repo: Any,
            template_repo: Any,
        ) -> None:
            self.parser = parser
            self.analyzer = analyzer
            self.classifier = classifier
            self.run_repo = run_repo
            self.result_repo = result_repo
            self.template_repo = template_repo

        def process_run(
            self,
            file_content: str | bytes,
            filename: str,
            template_identifier: str,
            user_id: uuid.UUID,
        ) -> dict[str, Any]:
            pass


@pytest.fixture
def mock_parser() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_analyzer() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_classifier() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_run_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_result_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_template_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def analysis_service(
    mock_parser: MagicMock,
    mock_analyzer: MagicMock,
    mock_classifier: MagicMock,
    mock_run_repo: MagicMock,
    mock_result_repo: MagicMock,
    mock_template_repo: MagicMock,
) -> Generator[AnalysisService, None, None]:
    service = AnalysisService(
        parser=mock_parser,
        analyzer=mock_analyzer,
        classifier=mock_classifier,
        run_repo=mock_run_repo,
        result_repo=mock_result_repo,
        template_repo=mock_template_repo,
    )
    yield service


def test_process_run_success(
    analysis_service: AnalysisService,
    mock_parser: MagicMock,
    mock_analyzer: MagicMock,
    mock_classifier: MagicMock,
    mock_run_repo: MagicMock,
    mock_result_repo: MagicMock,
    mock_template_repo: MagicMock,
) -> None:
    # Arrange
    file_content = b"<xml>dummy data</xml>"
    filename = "test_run.xml"
    template_identifier = "COVID_MULTIPLEX_v1"
    user_id = uuid.uuid4()

    mock_parser.parse_roche_xml_mvp.return_value = [
        {
            "run_identifier": "RUN1",
            "well_position": "Sample_1",
            "target_channel": "FAM",
            "temperatures": [60.0, 61.0],
            "raw_fluorescence": [1.0, 1.2],
        }
    ]

    mock_template = MagicMock()
    mock_template.multiplex_mapping = {
        "Mix_1": {"FAM": {"targets": ["Target A"], "expected_tms": [70.0]}}
    }
    mock_template_repo.get_by_identifier.return_value = mock_template

    # MOCK AKTUALISIERT: 'analyze' statt 'analyze_curve' verwenden
    mock_analyzer.analyze.return_value = {
        "tm_peaks": [70.1],
        "processed_curve": [0.1, 0.2],
        "requires_senior_validation": False,
    }

    mock_classifier.classify_channel_targets.return_value = {"Target A": True}

    mock_run_db_obj = MagicMock()
    mock_run_db_obj.id = uuid.uuid4()
    mock_run_repo.create.return_value = mock_run_db_obj

    mock_result_db_obj = MagicMock()
    mock_result_db_obj.id = uuid.uuid4()
    mock_result_repo.create.return_value = mock_result_db_obj

    # Act
    result = analysis_service.process_run(
        file_content=file_content,
        filename=filename,
        template_identifier=template_identifier,
        user_id=user_id,
    )

    # Assert
    mock_parser.parse_roche_xml_mvp.assert_called_once_with(file_content)
    mock_template_repo.get_by_identifier.assert_called_once_with(template_identifier)

    mock_analyzer.analyze.assert_called()

    # Verify classifier is called at least once
    mock_classifier.classify_channel_targets.assert_called()

    # Verify DB persistence calls
    mock_run_repo.create.assert_called()
    mock_result_repo.create.assert_called()

    # Assuming a dictionary structure for success response
    assert isinstance(result, dict)


def test_process_run_missing_template(
    analysis_service: AnalysisService,
    mock_template_repo: MagicMock,
) -> None:
    # Arrange
    file_content = b"<xml>dummy data</xml>"
    filename = "test_run.xml"
    template_identifier = "MISSING_TEMPLATE_v1"
    user_id = uuid.uuid4()

    mock_template_repo.get_by_identifier.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match=template_identifier):
        analysis_service.process_run(
            file_content=file_content,
            filename=filename,
            template_identifier=template_identifier,
            user_id=user_id,
        )

    mock_template_repo.get_by_identifier.assert_called_once_with(template_identifier)


def test_process_run_invalid_positive_control(
    analysis_service: AnalysisService,
    mock_parser: MagicMock,
    mock_analyzer: MagicMock,
    mock_classifier: MagicMock,
    mock_template_repo: MagicMock,
) -> None:
    """
    Test that a failing positive control (e.g. PC detects 0 targets instead of required targets)
    invalidates the run and raises a ValueError.
    """
    # Arrange
    file_content = b"<xml>dummy data</xml>"
    filename = "test_run.xml"
    template_identifier = "COVID_MULTIPLEX_v1"
    user_id = uuid.uuid4()

    # We simulate a well designated as Positive Control ("PC")
    mock_parser.parse_roche_xml_mvp.return_value = [
        {
            "run_identifier": "RUN1",
            "well_position": "PC_Well",  # Contains control keyword
            "target_channel": "FAM",
            "temperatures": [60.0, 61.0],
            "raw_fluorescence": [1.0, 1.2],
        }
    ]

    mock_template = MagicMock()
    mock_template.multiplex_mapping = {
        "Mix_1": {"FAM": {"targets": ["Target A"], "expected_tms": [70.0]}}
    }
    mock_template_repo.get_by_identifier.return_value = mock_template

    # Analyzer returns empty peaks for PC (amplification failed)
    mock_analyzer.analyze.return_value = {
        "tm_peaks": [],
        "processed_curve": [0.1, 0.2],
        "requires_senior_validation": False,
    }

    # Positive control fails: Target A is NOT detected (False)
    mock_classifier.classify_channel_targets.return_value = {"Target A": False}

    # Act & Assert
    with pytest.raises(ValueError, match=r"(?i)positive control|PC|control"):
        analysis_service.process_run(
            file_content=file_content,
            filename=filename,
            template_identifier=template_identifier,
            user_id=user_id,
        )


def test_process_run_invalid_negative_control(
    analysis_service: AnalysisService,
    mock_parser: MagicMock,
    mock_analyzer: MagicMock,
    mock_classifier: MagicMock,
    mock_template_repo: MagicMock,
) -> None:
    """
    Test that a contaminated negative control (NTC detects peaks / triggers analyzer escalation)
    invalidates the run and raises a ValueError.
    """
    # Arrange
    file_content = b"<xml>dummy data</xml>"
    filename = "test_run.xml"
    template_identifier = "COVID_MULTIPLEX_v1"
    user_id = uuid.uuid4()

    # We simulate a well designated as Negative Control ("NTC")
    mock_parser.parse_roche_xml_mvp.return_value = [
        {
            "run_identifier": "RUN1",
            "well_position": "NTC_Well",  # Contains control keyword
            "target_channel": "FAM",
            "temperatures": [60.0, 61.0],
            "raw_fluorescence": [1.0, 1.2],
        }
    ]

    mock_template = MagicMock()
    mock_template.multiplex_mapping = {
        "Mix_1": {"FAM": {"targets": ["Target A"], "expected_tms": [70.0]}}
    }
    mock_template_repo.get_by_identifier.return_value = mock_template

    # Analyzer detects contamination peaks in NTC and flags it for escalation
    mock_analyzer.analyze.return_value = {
        "tm_peaks": [70.1],
        "processed_curve": [1.0, 1.2],
        "requires_senior_validation": True,
    }

    mock_classifier.classify_channel_targets.return_value = {"Target A": True}

    # Act & Assert
    with pytest.raises(ValueError, match=r"(?i)negative control|NTC|contamination"):
        analysis_service.process_run(
            file_content=file_content,
            filename=filename,
            template_identifier=template_identifier,
            user_id=user_id,
        )
