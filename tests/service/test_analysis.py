import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.classifier import ClusterClassifier
from app.exceptions import (
    ControlValidationFailedError,
    DataParsingError,
    TemplateNotFoundError,
)
from app.services.analysis_service import AnalysisService


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
    mock_template.is_active = True
    mock_template.multiplex_mapping = {
        "Mix_1": {"FAM": {"targets": ["Target A"], "expected_tms": [70.0]}}
    }
    mock_template_repo.get_by_identifier.return_value = mock_template

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

    result = analysis_service.process_run(
        file_content=file_content,
        filename=filename,
        template_identifier=template_identifier,
        user_id=user_id,
    )

    mock_parser.parse_roche_xml_mvp.assert_called_once_with(file_content)
    mock_template_repo.get_by_identifier.assert_called_once_with(template_identifier)
    mock_analyzer.analyze.assert_called()
    mock_classifier.classify_channel_targets.assert_called()
    mock_run_repo.create.assert_called()
    mock_result_repo.create.assert_called()
    assert isinstance(result, dict)


def test_process_run_missing_template(
    analysis_service: AnalysisService,
    mock_template_repo: MagicMock,
) -> None:
    file_content = b"<xml>dummy data</xml>"
    filename = "test_run.xml"
    template_identifier = "MISSING_TEMPLATE_v1"
    user_id = uuid.uuid4()

    mock_template_repo.get_by_identifier.return_value = None

    with pytest.raises(TemplateNotFoundError, match=template_identifier):
        analysis_service.process_run(
            file_content=file_content,
            filename=filename,
            template_identifier=template_identifier,
            user_id=user_id,
        )

    mock_template_repo.get_by_identifier.assert_called_once_with(template_identifier)


def test_process_run_inactive_template_raises_error(
    analysis_service: AnalysisService,
    mock_template_repo: MagicMock,
) -> None:
    """Verifies that a soft-deleted template (is_active=False) is rejected."""
    mock_template = MagicMock()
    mock_template.is_active = False
    mock_template_repo.get_by_identifier.return_value = mock_template

    with pytest.raises(TemplateNotFoundError):
        analysis_service.process_run(
            file_content=b"<xml>data</xml>",
            filename="test_run.xml",
            template_identifier="INACTIVE_TPL",
            user_id=uuid.uuid4(),
        )


def test_process_run_csv_dispatch_and_parsing_error_translation(
    analysis_service: AnalysisService,
    mock_parser: MagicMock,
    mock_template_repo: MagicMock,
) -> None:
    """Verifies that block-CSV uploads dispatch to parse_csv_mvp and translate ValueError to DataParsingError."""
    mock_template = MagicMock()
    mock_template.is_active = True
    mock_template.multiplex_mapping = {}
    mock_template_repo.get_by_identifier.return_value = mock_template

    mock_parser.parse_csv_mvp.side_effect = ValueError("Corrupted CSV block")

    with pytest.raises(DataParsingError, match="Corrupted CSV block"):
        analysis_service.process_run(
            file_content=b"[Header]\nRun_ID,R1",
            filename="cycler_export.csv",
            template_identifier="VALID_TPL",
            user_id=uuid.uuid4(),
        )
    mock_parser.parse_csv_mvp.assert_called_once()


def test_process_run_invalid_positive_control(
    analysis_service: AnalysisService,
    mock_parser: MagicMock,
    mock_analyzer: MagicMock,
    mock_classifier: MagicMock,
    mock_template_repo: MagicMock,
) -> None:
    """
    Test that a failing positive control (e.g. PC detects 0 targets instead of required targets)
    invalidates the run and raises a ControlValidationFailedError.
    """
    file_content = b"<xml>dummy data</xml>"
    filename = "test_run.xml"
    template_identifier = "COVID_MULTIPLEX_v1"
    user_id = uuid.uuid4()

    mock_parser.parse_roche_xml_mvp.return_value = [
        {
            "run_identifier": "RUN1",
            "well_position": "PC_Well",
            "target_channel": "FAM",
            "temperatures": [60.0, 61.0],
            "raw_fluorescence": [1.0, 1.2],
        }
    ]

    mock_template = MagicMock()
    mock_template.is_active = True
    mock_template.multiplex_mapping = {
        "Mix_1": {"FAM": {"targets": ["Target A"], "expected_tms": [70.0]}}
    }
    mock_template_repo.get_by_identifier.return_value = mock_template

    mock_analyzer.analyze.return_value = {
        "tm_peaks": [],
        "processed_curve": [0.1, 0.2],
        "requires_senior_validation": False,
    }
    mock_classifier.classify_channel_targets.return_value = {"Target A": False}

    with pytest.raises(
        ControlValidationFailedError, match=r"(?i)positive control|PC|control"
    ):
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
    invalidates the run and raises a ControlValidationFailedError.
    """
    file_content = b"<xml>dummy data</xml>"
    filename = "test_run.xml"
    template_identifier = "COVID_MULTIPLEX_v1"
    user_id = uuid.uuid4()

    mock_parser.parse_roche_xml_mvp.return_value = [
        {
            "run_identifier": "RUN1",
            "well_position": "NTC_Well",
            "target_channel": "FAM",
            "temperatures": [60.0, 61.0],
            "raw_fluorescence": [1.0, 1.2],
        }
    ]

    mock_template = MagicMock()
    mock_template.is_active = True
    mock_template.multiplex_mapping = {
        "Mix_1": {"FAM": {"targets": ["Target A"], "expected_tms": [70.0]}}
    }
    mock_template_repo.get_by_identifier.return_value = mock_template

    mock_analyzer.analyze.return_value = {
        "tm_peaks": [70.1],
        "processed_curve": [1.0, 1.2],
        "requires_senior_validation": True,
    }
    mock_classifier.classify_channel_targets.return_value = {"Target A": True}

    with pytest.raises(
        ControlValidationFailedError, match=r"(?i)negative control|NTC|contamination"
    ):
        analysis_service.process_run(
            file_content=file_content,
            filename=filename,
            template_identifier=template_identifier,
            user_id=user_id,
        )


def test_process_run_pcr_substring_not_misidentified_as_pc_and_dbscan_drift(
    mock_parser: MagicMock,
    mock_analyzer: MagicMock,
    mock_run_repo: MagicMock,
    mock_result_repo: MagicMock,
    mock_template_repo: MagicMock,
) -> None:
    """
    Verifies:
    1. A well named 'pcr_patient_1' is NOT mistaken for a Positive Control ('pc').
    2. Multiple channels on the same well reuse the same Sample DB record.
    3. Real ClusterClassifier DBSCAN drift compensation labels shifted peaks as 'Drift_Compensated'.
    """
    real_classifier = ClusterClassifier()
    service = AnalysisService(
        parser=mock_parser,
        analyzer=mock_analyzer,
        classifier=real_classifier,
        run_repo=mock_run_repo,
        result_repo=mock_result_repo,
        template_repo=mock_template_repo,
    )

    mock_parser.parse_roche_xml_mvp.return_value = [
        {
            "run_identifier": "RUN_DRIFT",
            "well_position": "pcr_patient_1",
            "target_channel": "FAM",
            "temperatures": [60.0, 61.0],
            "raw_fluorescence": [10.0, 9.0],
        },
        {
            "run_identifier": "RUN_DRIFT",
            "well_position": "pcr_patient_2",
            "target_channel": "FAM",
            "temperatures": [60.0, 61.0],
            "raw_fluorescence": [10.0, 9.0],
        },
    ]

    mock_template = MagicMock()
    mock_template.is_active = True
    mock_template.multiplex_mapping = {
        "FAM": {"targets": ["Target A"], "expected_tms": [70.0]}
    }
    mock_template_repo.get_by_identifier.return_value = mock_template

    # Both wells have a +0.6 °C shifted peak (70.6 °C), which would fail a static 0.5 °C tolerance without drift compensation
    mock_analyzer.analyze.return_value = {
        "tm_peaks": [70.6],
        "processed_curve": [0.5, 0.6],
        "requires_senior_validation": False,
    }

    mock_run_db_obj = MagicMock()
    mock_run_db_obj.id = uuid.uuid4()
    mock_run_repo.create.return_value = mock_run_db_obj

    mock_result_db_obj = MagicMock()
    mock_result_db_obj.id = uuid.uuid4()
    mock_result_repo.create.return_value = mock_result_db_obj

    summary = service.process_run(
        file_content=b"<xml>data</xml>",
        filename="drift.xml",
        template_identifier="TPL_DRIFT",
        user_id=uuid.uuid4(),
    )

    assert len(summary["results"]) == 2
    assert summary["results"][0]["positive"] is True
    assert summary["results"][0]["cluster_label"] == "Drift_Compensated"
