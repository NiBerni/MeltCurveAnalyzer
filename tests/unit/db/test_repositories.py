import uuid

from sqlalchemy.orm import Session

from app.db.models import PcrRun, User
from app.db.repositories import PcrRunRepository


def test_repository_create_pcr_run(db_session: Session, user_instance: User) -> None:
    repo = PcrRunRepository(db_session)

    created_run = repo.create(
        run_identifier="RUN-2026-TEST01",
        device_id="CYCLER-9000",
        raw_operator="Jane Doe",
        imported_by_id=user_instance.id,
    )

    assert isinstance(created_run, PcrRun)
    assert created_run.id is not None
    assert isinstance(created_run.id, uuid.UUID)

    assert created_run.run_identifier == "RUN-2026-TEST01"
    assert created_run.device_id == "CYCLER-9000"
    assert created_run.raw_operator == "Jane Doe"
    assert created_run.imported_by_id == user_instance.id


def test_repository_get_run_by_identifier(
    db_session: Session, user_instance: User
) -> None:
    repo = PcrRunRepository(db_session)

    created_run = repo.create(
        run_identifier="RUN-2026-TEST02",
        device_id="CYCLER-9001",
        raw_operator=" John Doe",
        imported_by_id=user_instance.id,
    )
    fetched_run = repo.get_by_identifier("RUN-2026-TEST02")

    assert fetched_run is not None
    assert isinstance(fetched_run, PcrRun)
    assert fetched_run.id == created_run.id
    assert fetched_run.run_identifier == "RUN-2026-TEST02"


def test_repository_get_run_not_found(db_session: Session) -> None:
    repo = PcrRunRepository(db_session)

    fetched_run = repo.get_by_identifier("RUN-UNKNOWN-999")

    assert fetched_run is None
