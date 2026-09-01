import uuid
from typing import TypedDict

import pytest
from sqlalchemy import Table
from sqlalchemy.orm import Mapper
from sqlalchemy.sql.sqltypes import Boolean, String, Uuid
from werkzeug.security import generate_password_hash

from app.db.models import Permission, Role, User, role_permissions, user_roles


class UserKwargs(TypedDict):
    id: uuid.UUID
    username: str
    email: str
    password_hash: str
    is_active: bool


@pytest.fixture
def user_kwargs() -> UserKwargs:
    """Fixture providing valid keyword arguments for User model instantiation."""
    return {
        "id": uuid.uuid7(),  # Primary keys must use native PostgreSQL UUIDs generated via UUIDv7
        "username": "jdoe_senior",  # Expected String
        "email": "jdoe@example.com",  # Expected String
        "password_hash": generate_password_hash(
            "secure_hash_string"
        ),  # Expected String
        "is_active": True,  # Expected Boolean
    }


@pytest.fixture
def user_instance(user_kwargs: UserKwargs) -> User:
    """Fixture returning an instantiated User model."""
    return User(**user_kwargs)


def test_user_model_instantiation(user_instance: User, user_kwargs: UserKwargs) -> None:
    """
    Test that the User model instantiates correctly and attribute mapping
    behaves as expected without a database connection.
    """
    assert user_instance.id == user_kwargs["id"]  # Evaluates UUIDv7 id assignment
    assert (
        user_instance.username == user_kwargs["username"]
    )  # Evaluates username assignment
    assert user_instance.email == user_kwargs["email"]  # Evaluates email assignment
    assert (
        user_instance.password_hash == user_kwargs["password_hash"]
    )  # Evaluates password_hash assignment
    assert (
        user_instance.is_active is user_kwargs["is_active"]
    )  # Evaluates is_active assignment


def test_user_model_columns() -> None:
    """
    Inspect the User model to ensure SQLAlchemy 2.1 mapped_column configs
    match domain constraints.
    """
    mapper: Mapper = User.__mapper__
    columns = mapper.columns

    # Test 'id' column constraints
    assert "id" in columns
    assert columns["id"].primary_key is True  # id is the Primary Key
    assert isinstance(columns["id"].type, Uuid)  # Must be native PostgreSQL UUID

    # Test 'username' column constraints
    assert "username" in columns
    assert columns["username"].unique is True  # username must be unique
    assert isinstance(columns["username"].type, String)  # username is a String
    assert columns["username"].nullable is False  # Implicit constraint for Mapped[str]

    # Test 'email' column constraints
    assert "email" in columns
    assert columns["email"].unique is True  # email must be unique
    assert isinstance(columns["email"].type, String)  # email is a String
    assert columns["email"].nullable is False  # Implicit constraint for Mapped[str]

    # Test 'password_hash' column constraints
    assert "password_hash" in columns
    assert isinstance(
        columns["password_hash"].type, String
    )  # password_hash is a String
    assert (
        columns["password_hash"].nullable is False
    )  # Implicit constraint for Mapped[str]

    # Test 'is_active' column constraints
    assert "is_active" in columns
    assert isinstance(columns["is_active"].type, Boolean)  # is_active is a Boolean


@pytest.mark.parametrize(
    "relationship_name, expected_target_type",
    [
        ("pcr_runs", "One-to-Many"),  # Relationship to PcrRun as operator
        ("sample_results", "One-to-Many"),
        ("roles", "Many-to-Many"),
    ],
)
def test_user_model_relationships(
    relationship_name: str, expected_target_type: str
) -> None:
    """
    Inspect the User model to ensure SQLAlchemy relationships are accurately defined.
    """
    mapper: Mapper = User.__mapper__
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
        )  # Requires an association table linking user_id and role_id


class RoleKwargs(TypedDict):
    id: uuid.UUID
    name: str
    description: str | None


@pytest.fixture
def role_kwargs() -> RoleKwargs:
    """Fixture providing valid keyword arguments for Role model instantiation."""
    return {
        "id": uuid.uuid7(),
        "name": "Senior",
        "description": "Can validate questionable melt curves.",
    }


@pytest.fixture
def role_instance(role_kwargs) -> Role:
    """Fixture returning an instantiated Role model."""
    return Role(**role_kwargs)


def test_role_model_instantiation(role_instance: Role, role_kwargs: RoleKwargs) -> None:
    """Test that the Role model instantiates correctly with provided kwargs."""
    assert role_instance.id == role_kwargs["id"]
    assert role_instance.name == role_kwargs["name"]
    assert role_instance.description == role_kwargs["description"]


def test_role_model_columns() -> None:
    """
    Inspect the Role model to ensure SQLAlchemy mapped_column configs match domain constraints.
    """
    mapper: Mapper = Role.__mapper__
    columns = mapper.columns

    # Test "id" constraints
    assert "id" in columns
    assert columns["id"].primary_key is True
    assert isinstance(columns["id"].type, Uuid)

    # Test 'name' column constraints
    assert "name" in columns
    assert columns["name"].unique is True
    assert isinstance(columns["name"].type, String)
    assert columns["name"].nullable is False  # Implicit constraint for Mapped[str]
    # Test "description" column constraints
    assert "description" in columns
    assert isinstance(columns["description"].type, String)  # description is a String
    assert (
        columns["description"].nullable is True
    )  # description is Nullable / Mapped[str | None]


@pytest.mark.parametrize(
    "relationship_name, expected_target_type",
    [
        (
            "users",
            "Many-to-Many",
        )
    ],
)
def test_role_model_relationships(
    relationship_name: str, expected_target_type: str
) -> None:
    """
    Inspect the Role model to ensure SQLAlchemy relationships are accurately defined.
    """
    mapper: Mapper = Role.__mapper__
    relationships = mapper.relationships

    assert relationship_name in relationships

    rel = relationships[relationship_name]
    if expected_target_type == "Many-to-Many":
        assert rel.uselist is True
        assert rel.secondary is not None


class PermissionKwargs(TypedDict):
    id: uuid.UUID
    name: str
    description: str | None


@pytest.fixture
def permission_kwargs() -> PermissionKwargs:
    """Fixture providing valid keyword arguments for Permission model instantiation."""
    return {
        "id": uuid.uuid7(),
        "name": "validate_results",
        "description": "Allows technical validation of standard PCR results",
    }


@pytest.fixture
def permission_instance(permission_kwargs: PermissionKwargs) -> Permission:
    return Permission(**permission_kwargs)


def test_permission_model_instantiation(
    permission_instance: Permission, permission_kwargs: PermissionKwargs
) -> None:
    """
    Test that the Permission model instantiates correctly and attribute mapping behaves as expected
    without a database connection.
    """
    assert permission_instance.id == permission_kwargs["id"]
    assert permission_instance.name == permission_kwargs["name"]
    assert permission_instance.description == permission_kwargs["description"]


def test_permission_model_columns() -> None:
    """
    Inspect the Permission model to ensure SQLAlchemy mapped_column configs match domain constraints.
    """
    mapper: Mapper = Permission.__mapper__
    columns = mapper.columns

    # Test "id" column constraints
    assert "id" in columns
    assert columns["id"].primary_key is True
    assert isinstance(columns["id"].type, Uuid)

    # Test "name" column constraints
    assert "name" in columns
    assert columns["name"].unique is True
    assert isinstance(columns["name"].type, String)
    assert columns["name"].nullable is False

    # Test "description" column constraints
    assert "description" in columns
    assert isinstance(columns["description"].type, String)
    assert columns["description"].nullable is True


def test_user_roles_association_table() -> None:
    """
    Inspect the user_roles association table to ensure SQLAlchemy configs match domain constraints.
    """
    assert isinstance(user_roles, Table)
    assert user_roles.name == "user_roles"

    columns = user_roles.columns
    assert "user_id" in columns
    assert columns["user_id"].primary_key is True
    assert len(columns["user_id"].foreign_keys) == 1

    assert "role_id" in columns
    assert columns["role_id"].primary_key is True
    assert len(columns["role_id"].foreign_keys) == 1


def test_role_permission_association_table() -> None:
    """
    Inspect the role_permissions association table to ensure SQLAlchemy configs match domain constraints.
    """
    assert isinstance(role_permissions, Table)
    assert role_permissions.name == "role_permission"

    columns = role_permissions.columns
    assert "role_id" in columns
    assert columns["role_id"].primary_key is True
    assert len(columns["role_id"].foreign_keys) == 1

    assert "permission_id" in columns
    assert columns["permission_id"].primary_key is True
    assert len(columns["permission_id"].foreign_keys) == 1
