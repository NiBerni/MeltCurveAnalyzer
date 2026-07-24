import uuid
from typing import TypedDict

import pytest
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Mapper

from app.db.models import PcrRun, Sample


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
    mapper: Mapper[PcrRun] = inspect(PcrRun)
    columns = mapper.columns

    assert columns.id.primary_key is True
    assert columns.run_identifier.nullable is False
    assert columns.run_identifier.unique is True
    assert columns.device_id.nullable is True
    assert columns.raw_operator.nullable is True
    assert columns.imported_by_id.nullable is False


def test_pcr_run_relationships() -> None:
    mapper: Mapper[PcrRun] = inspect(PcrRun)
    relationships = mapper.relationships

    assert "imported_by" in relationships
    assert relationships.imported_by.uselist is False

    assert "samples" in relationships
    assert relationships.samples.uselist is True
    assert relationships.samples.cascade.delete is True
    assert relationships.samples.cascade.delete_orphan is True


# ==============================================================================
# Tests for Sample Model
# ==============================================================================


def test_sample_instantiation(sample_kwargs: SampleKwargs) -> None:
    sample = Sample(**sample_kwargs)

    assert sample.id == sample_kwargs["id"]
    assert sample.pcr_run_id == sample_kwargs["pcr_run_id"]
    assert sample.wll_position == sample_kwargs["well_position"]


def test_sample_columns() -> None:
    mapper: Mapper[Sample] = inspect(Sample)
    columns = mapper.columns

    assert columns.id.primary_key is True
    assert columns.pcr_run_id.nullable is False
    assert columns.well_position.nullable is False


def test_sample_relationships() -> None:
    mapper: Mapper[Sample] = inspect(Sample)
    relationships = mapper.relationships

    assert "pcr_run" in relationships
    assert relationships.pcr_run.uselist is False

    assert "melt_curves" in relationships
    assert relationships.melt_curves.uselist is True
    assert relationships.melt_curves.cascade.delete is True
    assert relationships.melt_curves.cascade.delete_orphan is True
