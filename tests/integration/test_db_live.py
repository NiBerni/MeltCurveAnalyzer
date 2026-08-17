import os
import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select, tstring
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, PcrRun, Sample, SampleResult, User
from app.db.repositories import (
    PcrRunRepository,
    SampleResultRepository,
    TemplateRepository,
)


@pytest.fixture(scope="function")
def db_session_pg() -> Generator[Session, None, None]:
    """
    Create a live PostgreSQL session for integration testing.
    The default DBAPI driver is now psycopg (psycopg 3).
    """
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://pcr_admin:supersecretpassword@127.0.0.1:5432/pcr_analyzer",
    )
    engine = create_engine(db_url)

    # 1. Erstellt alle Tabellen in der Live-DB, falls sie noch nicht existieren
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    session.begin_nested()

    yield session

    session.rollback()
    session.close()
    engine.dispose()


@pytest.mark.parametrize(
    "base_username, is_active",
    [
        ("active_user", True),
        ("inactive_user", False),
    ],
)
def test_user_creation_and_query(
    db_session_pg: Session, base_username: str, is_active: bool
) -> None:
    """
    Test creating a User directly via SQLAlchemy 2.1 and querying it.
    Queries ALWAYS use select().
    """
    unique_tag = uuid.uuid4().hex[:8]
    username = f"{base_username}_{unique_tag}"
    email = f"{username}@example.com"

    test_id = uuid.uuid7()
    new_user = User(
        id=test_id,
        username=username,
        email=email,
        password_hash="hashed_secret_string",
        is_active=is_active,
    )
    db_session_pg.add(new_user)
    db_session_pg.flush()

    stmt = select(User).where(User.username == username)
    fetched_user = db_session_pg.execute(stmt).scalar_one_or_none()

    assert fetched_user is not None
    assert isinstance(fetched_user.id, uuid.UUID)
    assert fetched_user.email == email
    assert fetched_user.is_active is is_active


def test_template_repository_create_and_get(db_session_pg: Session) -> None:
    """Test TemplateRepository create() and get_by_identifier()."""
    repo = TemplateRepository(db_session_pg)

    unique_tag = uuid.uuid4().hex[:8]
    identifier = f"TPL-{unique_tag}"

    mapping: dict[str, list[str]] = {"FAM": ["TargetA"], "HEX": ["TargetB"]}
    desc = "Integration test assay template"

    template = repo.create(
        template_identifier=identifier, multiplex_mapping=mapping, description=desc
    )
    db_session_pg.flush()

    assert template is not None
    assert isinstance(template.id, uuid.UUID)
    assert template.template_identifier == identifier

    fetched_template = repo.get_by_identifier(identifier)
    assert fetched_template is not None
    assert fetched_template.template_identifier == identifier
    assert isinstance(fetched_template.multiplex_mapping, dict)

    assert fetched_template.multiplex_mapping["FAM"] == ["TargetA"]


def test_pcr_run_repository_create_and_get(db_session_pg: Session) -> None:
    """
    Test PcrRunRepository create() and get_by_identifier().
    Raw SQL Variable Injection: Python values become bound values automatically when
    embedded within the tstring() template.
    """
    unique_tag = uuid.uuid4().hex[:8]
    user_id = uuid.uuid7()
    new_user = User(
        id=user_id,
        username=f"importer_admin_{unique_tag}",
        email=f"importer_{unique_tag}@example.com",
        password_hash="hash",
        is_active=True,
    )
    db_session_pg.add(new_user)
    db_session_pg.flush()

    repo = PcrRunRepository(db_session_pg)
    run_id = f"RUN-{unique_tag}"
    dev_id = "DEV-ABC"

    pcr_run = repo.create(
        run_identifier=run_id,
        device_id=dev_id,
        raw_operator="Jane Doe",
        imported_by_id=user_id,
    )
    db_session_pg.flush()

    assert pcr_run is not None
    assert isinstance(pcr_run.id, uuid.UUID)
    assert pcr_run.imported_by_id == user_id

    fetched_run = repo.get_by_identifier(run_id)
    assert fetched_run is not None
    assert fetched_run.run_identifier == run_id
    assert fetched_run.device_id == dev_id

    # Verify using PEP 750 t-string directly to test native SQLAlchemy 2.1 support
    stmt = tstring(
        t"SELECT id, run_identifier FROM pcr_runs WHERE run_identifier = {run_id}"
    )
    raw_result = db_session_pg.execute(stmt).fetchone()
    assert raw_result is not None
    assert raw_result.run_identifier == run_id


def test_sample_result_repository_update_technical_validation(
    db_session_pg: Session,
) -> None:
    """Test SampleResultRepository technical validation updates."""

    unique_tag = uuid.uuid4().hex[:8]
    validator_id = uuid.uuid7()
    validator = User(
        id=validator_id,
        username=f"validator_senior_{unique_tag}",
        email=f"validator_{unique_tag}@example.com",
        password_hash="hash",
        is_active=True,
    )
    db_session_pg.add(validator)
    db_session_pg.flush()

    run_id = uuid.uuid7()
    run = PcrRun(
        id=run_id,
        run_identifier=f"RUN-VAL-{unique_tag}",
        imported_by_id=validator_id,
    )
    db_session_pg.add(run)
    db_session_pg.flush()

    sample_id = uuid.uuid7()
    sample = Sample(
        id=sample_id,
        pcr_run_id=run_id,
        well_position="A01",
    )
    db_session_pg.add(sample)
    db_session_pg.flush()

    result_id = uuid.uuid7()
    sample_result = SampleResult(
        id=result_id,
        sample_id=sample_id,
        target_name="TargetA",
        algo_is_positive=True,
        algo_tm_peaks=[65.5, 80.1],
        cluster_label="Wildtype",
        tech_val_is_positive=None,
    )
    db_session_pg.add(sample_result)
    db_session_pg.flush()

    repo = SampleResultRepository(db_session_pg)

    updated_result = repo.update_tech_validation(
        result_id=result_id,
        is_positive=False,
        validated_by_id=validator_id,
        override_reason="Artifact confirmed via manual inspection",
    )
    db_session_pg.flush()

    assert updated_result is not None
    assert updated_result.tech_val_is_positive is False
    assert updated_result.tech_validated_by_id == validator_id
    assert updated_result.override_reason == "Artifact confirmed via manual inspection"
    assert updated_result.tech_validated_at is not None
