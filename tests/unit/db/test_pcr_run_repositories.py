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
        raw_operator="John Doe",
        imported_by_id=user_instance.id,
    )

    fetched_run = repo.get_by_identifier("RUN-2026-TEST02")

    assert fetched_run is not None
    assert isinstance(fetched_run, PcrRun)
    assert fetched_run.id == created_run.id
    assert fetched_run.run_identifier == "RUN-2026-TEST02"


def test_repository_get_run_by_id_and_get_all(
    db_session: Session, user_instance: User
) -> None:
    """Verifies get_by_id() and get_all() on PcrRunRepository."""
    repo = PcrRunRepository(db_session)
    run_1 = repo.create(
        run_identifier="RUN-2026-LIST-01",
        device_id="CYCLER-01",
        raw_operator="Op1",
        imported_by_id=user_instance.id,
    )
    run_2 = repo.create(
        run_identifier="RUN-2026-LIST-02",
        device_id="CYCLER-02",
        raw_operator="Op2",
        imported_by_id=user_instance.id,
    )

    fetched = repo.get_by_id(run_1.id)
    assert fetched is not None
    assert fetched.id == run_1.id

    all_runs = repo.get_all()
    all_ids = {r.id for r in all_runs}
    assert run_1.id in all_ids
    assert run_2.id in all_ids


def test_repository_get_run_not_found(db_session: Session) -> None:
    repo = PcrRunRepository(db_session)
    fetched_run = repo.get_by_identifier("RUN-UNKNOWN-999")
    assert fetched_run is None
