import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.repositories import UserRepository


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Fixture providing standard user data for creation."""
    return {
        "username": "lab_tech_01",
        "email": "lab_tech_01@lims.local",
        "password": "SecureTestPassword123!",
    }


@pytest.fixture
def user_repo(db_session: Session) -> UserRepository:
    """Fixture initializing the UserRepository with the database session."""
    return UserRepository(db_session)


def test_repository_create_user(
    user_repo: UserRepository, sample_user_data: dict[str, Any]
) -> None:
    user = user_repo.create(
        username=sample_user_data["username"],
        email=sample_user_data["email"],
        password=sample_user_data["password"],
    )

    assert isinstance(user, User)
    assert isinstance(user.id, uuid.UUID)
    assert user.username == sample_user_data["username"]
    assert user.email == sample_user_data["email"]
    assert user.is_active is True
    # Verify password hash integration[cite: 2]
    assert user.check_password(sample_user_data["password"]) is True
    assert user.password_hash != sample_user_data["password"]


def test_repository_get_user_by_id(
    user_repo: UserRepository, sample_user_data: dict[str, Any]
) -> None:
    created_user = user_repo.create(**sample_user_data)
    fetched_user = user_repo.get_by_id(created_user.id)

    assert fetched_user is not None
    assert isinstance(fetched_user, User)
    assert fetched_user.id == created_user.id
    assert fetched_user.username == sample_user_data["username"]


def test_repository_get_user_by_username(
    user_repo: UserRepository, sample_user_data: dict[str, Any]
) -> None:
    created_user = user_repo.create(**sample_user_data)
    fetched_user = user_repo.get_by_username(sample_user_data["username"])

    assert fetched_user is not None
    assert fetched_user.id == created_user.id
    assert fetched_user.email == sample_user_data["email"]


def test_repository_get_user_not_found(user_repo: UserRepository) -> None:
    invalid_id = uuid.uuid7()
    fetched_user = user_repo.get_by_id(invalid_id)
    assert fetched_user is None


def test_repository_update_user(
    user_repo: UserRepository, sample_user_data: dict[str, Any]
) -> None:
    user = user_repo.create(**sample_user_data)

    updated_email = "updated_tech@lims.local"
    updated_user = user_repo.update(
        user_id=user.id, email=updated_email, is_active=True
    )

    assert updated_user is not None
    assert updated_user.id == user.id
    assert updated_user.email == updated_email
    assert updated_user.username == sample_user_data["username"]


def test_repository_delete_user_soft_deactivates(
    user_repo: UserRepository, sample_user_data: dict[str, Any]
) -> None:
    # Delete should only deactivate(is_active = False) a User
    user = user_repo.create(**sample_user_data)
    assert user.is_active is True

    user_repo.delete(user.id)

    fetched_user = user_repo.get_by_id(user.id)
    assert fetched_user is not None
    assert fetched_user.is_active is False
