from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.types import ARRAY

from app.db.models import Base, User


@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """Creates a completely isolated in-memory SQLite database for blazing fast tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Returns a clean database session for a single test and rolls back afterward."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def user_instance(db_session: Session) -> User:
    """Provides a committed User instance to satisfy database foreign key constraints."""
    user = User(
        username="test_importer", email="importer@local.test", password_hash="fake_hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
