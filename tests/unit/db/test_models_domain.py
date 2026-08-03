import uuid
from typing import Any, TypedDict, cast

import pytest
from sqlalchemy import JSON, Column
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapper, class_mapper
from sqlalchemy.types import Float, String

from app.db.models import AssayTemplate, MeltCurve, PcrRun, Sample, SampleResult


# ==============================================================================
# Helper for Static Type Checkers (Ruff, PyCharm, Mypy)
# ==============================================================================
def get_col(mapper: Mapper[Any], col_name: str) -> Column[Any]:
    """Extracts a strictly typed Column to bypass dynamic attribute warnings (_COL_co)."""
    return cast(Column[Any], mapper.local_table.columns[col_name])


# ==============================================================================
# TypedDicts & Fixtures
# ==============================================================================
class PcrRunKwargs(TypedDict, total=False):
    id: uuid.UUID
    run_identifier: str
    device_id: str | None
    raw_operator: str | None
    imported_by_id: uuid.UUID


class SampleKwargs(TypedDict, total=False):
    id: uuid.UUID
    pcr_run_id: uuid.UUID
    well_position: str


class MeltCurveKwargs(TypedDict, total=False):
    id: uuid.UUID
    sample_id: uuid.UUID
    target_channel: str
    temperatures: list[float]
    raw_fluorescence: list[float]


class SampleResultKwargs(TypedDict, total=False):
    id: uuid.UUID
    sample_id: uuid.UUID
    target_name: str
    algo_is_positive: bool
    algo_tm_peaks: list[float]
    cluster_label: str


class AssayTemplateKwargs(TypedDict, total=False):
    id: uuid.UUID
    template_identifier: str
    multiplex_mapping: dict[str, list[str]]
    description: str | None


@pytest.fixture
def pcr_run_kwargs() -> PcrRunKwargs:
    return {
        "id": uuid.uuid7(),
        "run_identifier": "RUN-2026-ABC",
        "device_id": "CYCLER-01",
        "raw_operator": "Jane Doe",
        "imported_by_id": uuid.uuid7(),
    }


@pytest.fixture
def sample_kwargs() -> SampleKwargs:
    return {
        "id": uuid.uuid7(),
        "pcr_run_id": uuid.uuid7(),
        "well_position": "A01",
    }


@pytest.fixture
def melt_curve_kwargs() -> MeltCurveKwargs:
    return {
        "id": uuid.uuid7(),
        "sample_id": uuid.uuid7(),
        "target_channel": "FAM",
        "temperatures": [60.0, 60.5, 61.0, 61.5, 62.0],
        "raw_fluorescence": [100.5, 98.2, 85.1, 50.4, 10.0],
    }


@pytest.fixture
def sample_result_kwargs() -> SampleResultKwargs:
    return {
        "id": uuid.uuid7(),
        "sample_id": uuid.uuid7(),
        "target_name": "SARS-CoV-2",
        "algo_is_positive": True,
        "algo_tm_peaks": [82.5, 84.0],
        "cluster_label": "Wildtype",
    }


@pytest.fixture
def assay_template_kwargs() -> AssayTemplateKwargs:
    return {
        "id": uuid.uuid7(),
        "template_identifier": "RESP-MULTIPLEX-V1",
        "multiplex_mapping": {"FAM": ["SARS-CoV-2", "Flu A"], "HEX": ["RSV"]},
        "description": "Standard respiratory multiplex assay setup for Winter 2026.",
    }


# ==============================================================================
# Tests for PcrRun Model
# ==============================================================================
def test_pcr_run_instantiation(pcr_run_kwargs: PcrRunKwargs) -> None:
    run = PcrRun(**pcr_run_kwargs)

    assert run.id == pcr_run_kwargs["id"]
    assert run.run_identifier == pcr_run_kwargs["run_identifier"]
    assert run.device_id == pcr_run_kwargs["device_id"]
    assert run.raw_operator == pcr_run_kwargs["raw_operator"]
    assert run.imported_by_id == pcr_run_kwargs["imported_by_id"]


@pytest.mark.parametrize(
    "device_id, raw_operator",
    [
        ("CYCLER-02", "John Smith"),
        (None, "John Smith"),
        ("CYCLER-02", None),
        (None, None),
    ],
)
def test_pcr_run_instantiation_nullable_fields(
    device_id: str | None, raw_operator: str | None, pcr_run_kwargs: PcrRunKwargs
) -> None:
    kwargs = pcr_run_kwargs.copy()
    kwargs["device_id"] = device_id
    kwargs["raw_operator"] = raw_operator

    run = PcrRun(**kwargs)

    assert run.device_id == device_id
    assert run.raw_operator == raw_operator


def test_pcr_run_columns() -> None:
    mapper = class_mapper(PcrRun)

    assert get_col(mapper, "id").primary_key is True
    assert get_col(mapper, "run_identifier").nullable is False
    assert get_col(mapper, "run_identifier").unique is True
    assert get_col(mapper, "device_id").nullable is True
    assert get_col(mapper, "raw_operator").nullable is True
    assert get_col(mapper, "imported_by_id").nullable is False


def test_pcr_run_relationships() -> None:
    mapper = class_mapper(PcrRun)
    relationships = mapper.relationships

    assert "imported_by" in relationships
    assert relationships["imported_by"].uselist is False

    assert "samples" in relationships
    assert relationships["samples"].uselist is True
    assert relationships["samples"].cascade.delete is True
    assert relationships["samples"].cascade.delete_orphan is True


# ==============================================================================
# Tests for Sample Model
# ==============================================================================
def test_sample_instantiation(sample_kwargs: SampleKwargs) -> None:
    sample = Sample(**sample_kwargs)

    assert sample.id == sample_kwargs["id"]
    assert sample.pcr_run_id == sample_kwargs["pcr_run_id"]
    assert sample.well_position == sample_kwargs["well_position"]


def test_sample_columns() -> None:
    mapper = class_mapper(Sample)

    assert get_col(mapper, "id").primary_key is True
    assert get_col(mapper, "pcr_run_id").nullable is False
    assert get_col(mapper, "well_position").nullable is False


def test_sample_relationships() -> None:
    mapper = class_mapper(Sample)
    relationships = mapper.relationships

    assert "pcr_run" in relationships
    assert relationships["pcr_run"].uselist is False

    assert "melt_curves" in relationships
    assert relationships["melt_curves"].uselist is True
    assert relationships["melt_curves"].cascade.delete is True
    assert relationships["melt_curves"].cascade.delete_orphan is True


# ==============================================================================
# Tests for MeltCurve Model
# ==============================================================================
def test_melt_curve_instantiation(melt_curve_kwargs: MeltCurveKwargs) -> None:
    melt_curve = MeltCurve(**melt_curve_kwargs)

    assert melt_curve.id == melt_curve_kwargs["id"]
    assert melt_curve.sample_id == melt_curve_kwargs["sample_id"]
    assert melt_curve.target_channel == melt_curve_kwargs["target_channel"]
    assert melt_curve.temperatures == melt_curve_kwargs["temperatures"]
    assert melt_curve.raw_fluorescence == melt_curve_kwargs["raw_fluorescence"]


def test_melt_curve_columns() -> None:
    mapper = class_mapper(MeltCurve)

    assert get_col(mapper, "id").primary_key is True
    assert get_col(mapper, "sample_id").nullable is False
    assert get_col(mapper, "target_channel").nullable is False

    temp_col = get_col(mapper, "temperatures")
    assert temp_col.nullable is False
    assert isinstance(temp_col.type, ARRAY)
    assert isinstance(temp_col.type.item_type, Float)

    rfu_col = get_col(mapper, "raw_fluorescence")
    assert rfu_col.nullable is False
    assert isinstance(rfu_col.type, ARRAY)
    assert isinstance(rfu_col.type.item_type, Float)


def test_melt_curve_relationships() -> None:
    mapper = class_mapper(MeltCurve)
    relationships = mapper.relationships

    assert "sample" in relationships
    assert relationships["sample"].uselist is False


# ==============================================================================
# Tests for SampleResult Model
# ==============================================================================
def test_sample_result_instantiation_and_defaults(
    sample_result_kwargs: SampleResultKwargs,
) -> None:
    result = SampleResult(**sample_result_kwargs)

    # Core Data
    assert result.id == sample_result_kwargs["id"]
    assert result.sample_id == sample_result_kwargs["sample_id"]
    assert result.target_name == sample_result_kwargs["target_name"]
    assert result.algo_is_positive == sample_result_kwargs["algo_is_positive"]
    assert result.algo_tm_peaks == sample_result_kwargs["algo_tm_peaks"]
    assert result.cluster_label == sample_result_kwargs["cluster_label"]

    # Nullable Fields (in-memory state before flush)
    assert result.tech_val_is_positive is None
    assert result.tech_validated_by_id is None
    assert result.tech_validated_at is None
    assert result.override_reason is None
    assert result.exported_at is None


def test_sample_result_columns() -> None:
    mapper = class_mapper(SampleResult)

    # PK & Non-Nullable Fields
    assert get_col(mapper, "id").primary_key is True
    assert get_col(mapper, "sample_id").nullable is False
    assert get_col(mapper, "target_name").nullable is False
    assert get_col(mapper, "algo_is_positive").nullable is False
    assert get_col(mapper, "cluster_label").nullable is False
    assert get_col(mapper, "export_status").nullable is False

    export_col = get_col(mapper, "export_status")
    assert export_col.default is not None
    assert export_col.default.arg == "pending"

    # Array Validation
    algo_tm_peaks_col = get_col(mapper, "algo_tm_peaks")
    assert algo_tm_peaks_col.nullable is False
    assert isinstance(algo_tm_peaks_col.type, ARRAY)
    assert isinstance(algo_tm_peaks_col.type.item_type, Float)

    # Technical Validation (Escalation) - Must be Nullable
    assert get_col(mapper, "tech_val_is_positive").nullable is True
    assert get_col(mapper, "tech_validated_by_id").nullable is True
    assert get_col(mapper, "tech_validated_at").nullable is True
    assert get_col(mapper, "override_reason").nullable is True
    assert get_col(mapper, "exported_at").nullable is True


def test_sample_result_relationships() -> None:
    mapper = class_mapper(SampleResult)
    relationships = mapper.relationships

    assert "tech_validated_by" in relationships
    assert relationships["tech_validated_by"].uselist is False


# ==============================================================================
# Tests for AssayTemplate Model
# ==============================================================================
def test_assay_template_instantiation(
    assay_template_kwargs: AssayTemplateKwargs,
) -> None:
    template = AssayTemplate(**assay_template_kwargs)

    assert template.id == assay_template_kwargs["id"]
    assert template.template_identifier == assay_template_kwargs["template_identifier"]
    assert template.multiplex_mapping == assay_template_kwargs["multiplex_mapping"]
    assert template.description == assay_template_kwargs["description"]


def test_assay_template_columns() -> None:
    mapper = class_mapper(AssayTemplate)

    assert get_col(mapper, "id").primary_key is True

    template_identifier_col = get_col(mapper, "template_identifier")
    assert template_identifier_col.nullable is False
    assert template_identifier_col.unique is True

    multiplex_mapping_col = get_col(mapper, "multiplex_mapping")
    assert multiplex_mapping_col.nullable is False
    assert isinstance(multiplex_mapping_col.type, JSON)

    description_col = get_col(mapper, "description")
    assert description_col.nullable is True
