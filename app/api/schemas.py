"""
Provides defensive data validation structures.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationPayload:
    is_positive: bool
    override_reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ValidationPayload":
        if not data:
            raise ValueError("Empty request body")

        is_positive = data.get("is_positive")
        override_reason = data.get("override_reason")

        if not isinstance(is_positive, bool):
            raise ValueError("'is_positive' must be a boolean.")
        if not isinstance(override_reason, str) or not override_reason.strip():
            raise ValueError("'override_reason' must be a non-empty string.")

        return cls(is_positive=is_positive, override_reason=override_reason.strip())


@dataclass
class UserCreatePayload:
    username: str
    email: str
    password: str
    roles: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UserCreatePayload":
        if not data:
            raise ValueError("Empty request body")

        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        roles = data.get("roles", [])

        if not isinstance(username, str) or not username.strip():
            raise ValueError("'username' must be a non-empty string.")
        if not isinstance(email, str) or "@" not in email:
            raise ValueError("'email' must be a valid email string.")
        if not isinstance(password, str) or len(password) < 8:
            raise ValueError("'password' must be at least 8 characters long.")
        if not isinstance(roles, list):
            raise ValueError("'roles' must be a list of strings.")

        return cls(
            username=username.strip(),
            email=email.strip(),
            password=password,
            roles=roles,
        )


@dataclass
class UserUpdatePayload:
    is_active: bool | None = None
    password: str | None = None
    username: str | None = None
    email: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UserUpdatePayload":
        if not data:
            raise ValueError("Empty request body")

        is_active = data.get("is_active")
        password = data.get("password")
        username = data.get("username")
        email = data.get("email")

        if (
            is_active is None
            and password is None
            and username is None
            and email is None
        ):
            raise ValueError(
                "At least one updatable field ('is_active', 'password', 'username', 'email') must be provided."
            )

        if is_active is not None and not isinstance(is_active, bool):
            raise ValueError("'is_active' must be a boolean.")
        if password is not None and (
            not isinstance(password, str) or len(password) < 8
        ):
            raise ValueError("'password' must be at least 8 characters long.")
        if username is not None and (
            not isinstance(username, str) or not username.strip()
        ):
            raise ValueError("'username' must be a non-empty string.")
        if email is not None and (not isinstance(email, str) or "@" not in email):
            raise ValueError("'email' must be a valid email string.")

        return cls(
            is_active=is_active,
            password=password,
            username=username.strip() if isinstance(username, str) else None,
            email=email.strip() if isinstance(email, str) else None,
        )


@dataclass
class TemplateCreatePayload:
    template_identifier: str
    multiplex_mapping: dict[str, Any]
    description: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TemplateCreatePayload":
        if not data:
            raise ValueError("Empty request body")

        template_identifier = data.get("template_identifier")
        multiplex_mapping = data.get("multiplex_mapping")
        description = data.get("description")

        if not isinstance(template_identifier, str) or not template_identifier.strip():
            raise ValueError("'template_identifier' must be a non-empty string.")
        if not isinstance(multiplex_mapping, dict) or not multiplex_mapping:
            raise ValueError("'multiplex_mapping' must be a non-empty dictionary.")

        return cls(
            template_identifier=template_identifier.strip(),
            multiplex_mapping=multiplex_mapping,
            description=description.strip() if isinstance(description, str) else None,
        )


@dataclass
class TemplateUpdatePayload:
    is_active: bool | None = None
    multiplex_mapping: dict[str, Any] | None = None
    description: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TemplateUpdatePayload":
        if not data:
            raise ValueError("Empty request body")

        is_active = data.get("is_active")
        multiplex_mapping = data.get("multiplex_mapping")
        description = data.get("description")

        if is_active is None and multiplex_mapping is None and description is None:
            raise ValueError(
                "At least one field ('is_active', 'multiplex_mapping', 'description') must be provided."
            )

        if is_active is not None and not isinstance(is_active, bool):
            raise ValueError("'is_active' must be a boolean.")
        if multiplex_mapping is not None and (
            not isinstance(multiplex_mapping, dict) or not multiplex_mapping
        ):
            raise ValueError("'multiplex_mapping' must be a non-empty dictionary.")
        if description is not None and not isinstance(description, str):
            raise ValueError("'description' must be a string.")

        return cls(
            is_active=is_active,
            multiplex_mapping=multiplex_mapping,
            description=description.strip() if isinstance(description, str) else None,
        )
