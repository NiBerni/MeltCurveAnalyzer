import uuid
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

import pytest
from flask import Flask, jsonify, request
from flask.testing import FlaskClient

# ==============================================================================
# Mocked Schemas (Simulating app/api/schemas.py)
# ==============================================================================


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

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UserUpdatePayload":
        if not data:
            raise ValueError("Empty request body")
        is_active = data.get("is_active")
        password = data.get("password")

        if is_active is not None and not isinstance(is_active, bool):
            raise ValueError("'is_active' must be a boolean.")
        if password is not None and (
            not isinstance(password, str) or len(password) < 8
        ):
            raise ValueError("'password' must be at least 8 characters long.")

        return cls(is_active=is_active, password=password)


@dataclass
class TemplateCreatePayload:
    template_identifier: str
    multiplex_mapping: dict[str, list[str]]
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
    is_active: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TemplateUpdatePayload":
        if not data:
            raise ValueError("Empty request body")
        is_active = data.get("is_active")

        if not isinstance(is_active, bool):
            raise ValueError("'is_active' must be a boolean.")

        return cls(is_active=is_active)


# ==============================================================================
# Fixtures & App Setup (Simulating app setup & routing)
# ==============================================================================


def mock_jwt_required_and_roles(*allowed_roles: str) -> Any:
    """Helper to mock JWT role verification based on headers for tests."""

    def decorator(func: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Unauthorized"}), 401

            token = auth_header.split(" ")[1]
            # Simple token mock: "admin_token" -> Admin, "senior_token" -> Senior, etc.
            user_roles = []
            if "admin" in token:
                user_roles.append("Admin")
            if "senior" in token:
                user_roles.append("Senior")
            if "operator" in token:
                user_roles.append("Operator")

            if allowed_roles and not any(r in user_roles for r in allowed_roles):
                return jsonify({"error": "Forbidden"}), 403

            return func(*args, **kwargs)

        # Fix view function names for Flask routing
        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


@pytest.fixture
def app() -> Generator[Flask, None, None]:
    app = Flask("pcr_analyzer_test_extended")
    app.config["TESTING"] = True

    # -- User Routes --
    @app.get("/api/users")
    @mock_jwt_required_and_roles("Admin")
    def get_users() -> tuple[Any, int]:
        return jsonify([{"id": str(uuid.uuid7()), "username": "admin_user"}]), 200

    @app.post("/api/users")
    @mock_jwt_required_and_roles("Admin")
    def create_user() -> tuple[Any, int]:
        try:
            payload = UserCreatePayload.from_dict(request.get_json())
            return jsonify({"id": str(uuid.uuid7()), "username": payload.username}), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.delete("/api/users/<uuid:user_id>")
    @mock_jwt_required_and_roles("Admin")
    def delete_user(user_id: uuid.UUID) -> tuple[Any, int]:
        return jsonify({"message": f"User {user_id} deactivated"}), 200

    # -- Template Routes --
    @app.post("/api/templates")
    @mock_jwt_required_and_roles("Senior", "Admin")
    def create_template() -> tuple[Any, int]:
        try:
            payload = TemplateCreatePayload.from_dict(request.get_json())
            return jsonify(
                {"id": str(uuid.uuid7()), "identifier": payload.template_identifier}
            ), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.get("/api/templates/<uuid:template_id>")
    @mock_jwt_required_and_roles()  # Any valid JWT
    def get_template(template_id: uuid.UUID) -> tuple[Any, int]:
        return jsonify({"id": str(template_id), "name": "Assay B"}), 200

    @app.put("/api/templates/<uuid:template_id>")
    @mock_jwt_required_and_roles("Senior", "Admin")
    def update_template(template_id: uuid.UUID) -> tuple[Any, int]:
        try:
            payload = TemplateUpdatePayload.from_dict(request.get_json())
            return jsonify(
                {"id": str(template_id), "is_active": payload.is_active}
            ), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.delete("/api/templates/<uuid:template_id>")
    @mock_jwt_required_and_roles("Senior", "Admin")
    def delete_template(template_id: uuid.UUID) -> tuple[Any, int]:
        return jsonify({"message": f"Template {template_id} deleted"}), 200

    yield app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


# ==============================================================================
# Unit Tests: Validation Schemas
# ==============================================================================


def test_user_create_payload_valid() -> None:
    data = {
        "username": "new_user",
        "email": "test@example.com",
        "password": "securepassword123",
    }
    payload = UserCreatePayload.from_dict(data)
    assert payload.username == "new_user"
    assert payload.email == "test@example.com"
    assert payload.roles == []


@pytest.mark.parametrize(
    "invalid_data, expected_exception_match",
    [
        ({}, "Empty request body"),
        (
            {"email": "test@test.com", "password": "password123"},
            "'username' must be a non-empty string",
        ),
        (
            {"username": "user", "email": "invalid_email", "password": "password123"},
            "'email' must be a valid email",
        ),
        (
            {"username": "user", "email": "test@test.com", "password": "short"},
            "'password' must be at least 8 characters",
        ),
    ],
)
def test_user_create_payload_invalid(
    invalid_data: dict[str, Any], expected_exception_match: str
) -> None:
    with pytest.raises(ValueError, match=expected_exception_match):
        UserCreatePayload.from_dict(invalid_data)


def test_template_create_payload_valid() -> None:
    data = {
        "template_identifier": "Covid-19-Assay",
        "multiplex_mapping": {"FAM": ["Target_A"], "HEX": ["Target_B"]},
        "description": "Standard respiratory panel",
    }
    payload = TemplateCreatePayload.from_dict(data)
    assert payload.template_identifier == "Covid-19-Assay"
    assert payload.multiplex_mapping["FAM"] == ["Target_A"]


@pytest.mark.parametrize(
    "invalid_data, expected_exception_match",
    [
        (
            {"multiplex_mapping": {"FAM": ["A"]}},
            "'template_identifier' must be a non-empty string",
        ),
        (
            {"template_identifier": "Assay", "multiplex_mapping": {}},
            "'multiplex_mapping' must be a non-empty dictionary",
        ),
    ],
)
def test_template_create_payload_invalid(
    invalid_data: dict[str, Any], expected_exception_match: str
) -> None:
    with pytest.raises(ValueError, match=expected_exception_match):
        TemplateCreatePayload.from_dict(invalid_data)


# ==============================================================================
# Integration Tests: API Routing & RBAC
# ==============================================================================


def test_get_users_admin_success(client: FlaskClient) -> None:
    response = client.get("/api/users", headers={"Authorization": "Bearer admin_token"})
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)


def test_get_users_operator_forbidden(client: FlaskClient) -> None:
    response = client.get(
        "/api/users", headers={"Authorization": "Bearer operator_token"}
    )
    assert response.status_code == 403


def test_create_user_admin_success(client: FlaskClient) -> None:
    payload = {
        "username": "tech1",
        "email": "tech1@lab.com",
        "password": "SuperSecretPassword!",
    }
    response = client.post(
        "/api/users", json=payload, headers={"Authorization": "Bearer admin_token"}
    )
    assert response.status_code == 201
    assert response.get_json()["username"] == "tech1"


def test_create_user_invalid_payload_bad_request(client: FlaskClient) -> None:
    payload = {"username": "tech1"}  # Missing email and password
    response = client.post(
        "/api/users", json=payload, headers={"Authorization": "Bearer admin_token"}
    )
    assert response.status_code == 400


def test_delete_user_admin_success(client: FlaskClient) -> None:
    target_uuid = str(uuid.uuid7())
    response = client.delete(
        f"/api/users/{target_uuid}", headers={"Authorization": "Bearer admin_token"}
    )
    assert response.status_code == 200


def test_create_template_senior_success(client: FlaskClient) -> None:
    payload = {
        "template_identifier": "Flu-A-Assay",
        "multiplex_mapping": {"ROX": ["FluA"]},
    }
    response = client.post(
        "/api/templates", json=payload, headers={"Authorization": "Bearer senior_token"}
    )
    assert response.status_code == 201


def test_create_template_operator_forbidden(client: FlaskClient) -> None:
    payload = {
        "template_identifier": "Flu-A-Assay",
        "multiplex_mapping": {"ROX": ["FluA"]},
    }
    response = client.post(
        "/api/templates",
        json=payload,
        headers={"Authorization": "Bearer operator_token"},
    )
    assert response.status_code == 403


def test_get_template_by_id_operator_success(client: FlaskClient) -> None:
    target_uuid = str(uuid.uuid7())
    response = client.get(
        f"/api/templates/{target_uuid}",
        headers={"Authorization": "Bearer operator_token"},
    )
    assert response.status_code == 200
    assert response.get_json()["id"] == target_uuid


def test_update_template_admin_success(client: FlaskClient) -> None:
    target_uuid = str(uuid.uuid7())
    response = client.put(
        f"/api/templates/{target_uuid}",
        json={"is_active": False},
        headers={"Authorization": "Bearer admin_token"},
    )
    assert response.status_code == 200
    assert response.get_json()["is_active"] is False


def test_delete_template_senior_success(client: FlaskClient) -> None:
    target_uuid = str(uuid.uuid7())
    response = client.delete(
        f"/api/templates/{target_uuid}",
        headers={"Authorization": "Bearer senior_token"},
    )
    assert response.status_code == 200
