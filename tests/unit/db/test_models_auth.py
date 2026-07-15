import uuid
from typing import Any

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Mapper
from sqlalchemy.sql.sqltypes import Boolean, String, Uuid

from app.db.models import User


@pytest.fixture
def user_kwargs() -> dict[str, Any]:
    """Fixture providing valid keyword arguments for User model instantiation."""
    return {
        "id": uuid.uuid7(),  # Primary keys must use native PostgreSQL UUIDs generated via UUIDv7[cite: 1]
        "username": "jdoe_senior",  # Expected String[cite: 1]
        "email": "jdoe@example.com",  # Expected String[cite: 1]
        "password_hash": "secure_hash_string",  # Expected String[cite: 1]
        "is_active": True,  # Expected Boolean[cite: 1]
    }


@pytest.fixture
def user_instance(user_kwargs: dict[str, Any]) -> User:
    """Fixture returning an instantiated User model."""
    return User(**user_kwargs)


def test_user_model_instantiation(
    user_instance: User, user_kwargs: dict[str, Any]
) -> None:
    """
    Test that the User model instantiates correctly and attribute mapping
    behaves as expected without a database connection.
    """
    assert (
        user_instance.id == user_kwargs["id"]
    )  # Evaluates UUIDv7 id assignment[cite: 1]
    assert (
        user_instance.username == user_kwargs["username"]
    )  # Evaluates username assignment[cite: 1]
    assert (
        user_instance.email == user_kwargs["email"]
    )  # Evaluates email assignment[cite: 1]
    assert (
        user_instance.password_hash == user_kwargs["password_hash"]
    )  # Evaluates password_hash assignment[cite: 1]
    assert (
        user_instance.is_active is user_kwargs["is_active"]
    )  # Evaluates is_active assignment[cite: 1]


def test_user_model_columns() -> None:
    """
    Inspect the User model to ensure SQLAlchemy 2.1 mapped_column configs
    match domain constraints.[cite: 4]
    """
    mapper: Mapper = inspect(User)
    columns = mapper.columns

    # Test 'id' column constraints
    assert "id" in columns
    assert columns["id"].primary_key is True  # id is the Primary Key[cite: 1]
    assert isinstance(
        columns["id"].type, Uuid
    )  # Must be native PostgreSQL UUID[cite: 1, 4]

    # Test 'username' column constraints
    assert "username" in columns
    assert columns["username"].unique is True  # username must be unique[cite: 1]
    assert isinstance(columns["username"].type, String)  # username is a String[cite: 1]
    assert (
        columns["username"].nullable is False
    )  # Implicit constraint for Mapped[str][cite: 4]

    # Test 'email' column constraints
    assert "email" in columns
    assert columns["email"].unique is True  # email must be unique[cite: 1]
    assert isinstance(columns["email"].type, String)  # email is a String[cite: 1]
    assert (
        columns["email"].nullable is False
    )  # Implicit constraint for Mapped[str][cite: 4]

    # Test 'password_hash' column constraints
    assert "password_hash" in columns
    assert isinstance(
        columns["password_hash"].type, String
    )  # password_hash is a String[cite: 1]
    assert (
        columns["password_hash"].nullable is False
    )  # Implicit constraint for Mapped[str][cite: 4]

    # Test 'is_active' column constraints
    assert "is_active" in columns
    assert isinstance(
        columns["is_active"].type, Boolean
    )  # is_active is a Boolean[cite: 1]


@pytest.mark.parametrize(
    "relationship_name, expected_target_type",
    [
        ("pcr_runs", "One-to-Many"),  # Relationship to PcrRun as operator[cite: 1]
        (
            "sample_results",
            "One-to-Many",
        ),  # Relationship to SampleResult as tech_validated_by[cite: 1]
        (
            "roles",
            "Many-to-Many",
        ),  # Relationship to Role via association table user_roles[cite: 1]
    ],
)
def test_user_model_relationships(
    relationship_name: str, expected_target_type: str
) -> None:
    """
    Inspect the User model to ensure SQLAlchemy relationships are accurately defined.
    """
    mapper: Mapper = inspect(User)
    relationships = mapper.relationships

    assert relationship_name in relationships

    rel = relationships[relationship_name]
    if expected_target_type == "One-to-Many":
        assert rel.uselist is True
        assert rel.secondary is None
    elif expected_target_type == "Many-to-Many":
        assert rel.uselist is True
        assert (
            rel.secondary is not None
        )  # Requires an association table linking user_id and role_id[cite: 1]
