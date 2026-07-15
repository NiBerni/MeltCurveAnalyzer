import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.sql.sqltypes import Boolean, String, Uuid

from app.db.models import PcrRun, Role, SampleResult, User


@pytest.fixture
def user_mapper() -> Any | None:
    """Fixture to provide the SQLAlchemy mapper for User model."""
    return inspect(User)


@pytest.fixture
def valid_user_data() -> dict[str, UUID | str | bool]:
    """Fixture providing a standard valid payload for User instantiation"""
    return {
        "id": uuid.uuid7(),
        "username": "johndoe_operator",
        "email": "johndoe@example.com",
        "password_hash": "$2b$12$eImiTXuWVxfM37uY4JANjO20XoU.1",
        "is_active": True,
    }
