import datetime
import uuid

from sqlalchemy.orm import Session

from app.db.models import SampleResult, User
from app.db.repositories import SampleResultRepository


def test_repository_create_sample_result(
    db_session: Session, sample_instance: uuid.UUID
) -> None:
    repo = SampleResultRepository(db_session)

    peaks: list[float] = [85.5, 88.2]
    created_result = repo.create(
        sample_id=sample_instance,
        target_name="FAM",
        algo_is_positive=True,
        algo_tm_peaks=peaks,
        cluster_label="Wildtype",
        tech_val_is_positive=None,
    )

    assert isinstance(created_result, SampleResult)
    assert created_result.id is not None
    assert isinstance(created_result.id, uuid.UUID)

    assert created_result.sample_id == sample_instance
    assert created_result.target_name == "FAM"
    assert created_result.algo_is_positive is True
    assert created_result.algo_tm_peaks == peaks
    assert created_result.cluster_label == "Wildtype"
    assert created_result.tech_val_is_positive is None


def test_repository_resolve_escalation(
    db_session: Session, sample_instance: uuid.UUID, user_instance: User
) -> None:
    repo = SampleResultRepository(db_session)

    created_result = repo.create(
        sample_id=sample_instance,
        target_name="HEX",
        algo_is_positive=True,
        algo_tm_peaks=[78.4],
        cluster_label="Mutation",
        tech_val_is_positive=True,
    )

    assert created_result.tech_validated_at is None

    updated_result = repo.update_tech_validation(
        result_id=created_result.id,
        is_positive=False,
        validated_by_id=user_instance.id,
        override_reason="False positive caused by artifact in baseline",
    )

    assert updated_result is not None
    assert updated_result.tech_val_is_positive is False
    assert updated_result.tech_validated_by_id == user_instance.id
    assert (
        updated_result.override_reason
        == "False positive caused by artifact in baseline"
    )
    assert updated_result.tech_validated_at is not None
    assert isinstance(updated_result.tech_validated_at, datetime.datetime)


def test_repository_get_result_not_found(db_session: Session) -> None:
    repo = SampleResultRepository(db_session)
    random_uuid = uuid.uuid4()

    fetched_result = repo.get_by_id(random_uuid)

    assert fetched_result is None
