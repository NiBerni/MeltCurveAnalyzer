import io
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_jwt_extended import JWTManager, create_access_token

from app.api.routes import api_bp
from app.db.models import User


# ==============================================================================
# Fixtures & App Setup
# ==============================================================================
@pytest.fixture
def app() -> Generator[Flask, None, None]:
    """Creates the Flask app and registers the REAL blueprint."""
    app = Flask("pcr_analyzer_test")
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = "test-jwt-secret-key"

    JWTManager(app)
    app.register_blueprint(api_bp)

    yield app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


# --- Token Fixtures for RBAC ---
@pytest.fixture
def operator_token(app: Flask) -> str:
    with app.app_context():
        return create_access_token(
            identity=str(uuid.uuid7()),
            additional_claims={"roles": ["Operator"], "email": "operator@lab.com"},
        )


@pytest.fixture
def senior_token(app: Flask) -> str:
    with app.app_context():
        return create_access_token(
            identity=str(uuid.uuid7()),
            additional_claims={"roles": ["Senior"], "email": "senior@lab.com"},
        )


@pytest.fixture
def admin_token(app: Flask) -> str:
    with app.app_context():
        return create_access_token(
            identity=str(uuid.uuid7()),
            additional_claims={"roles": ["Admin"], "email": "admin@lab.com"},
        )


# ==============================================================================
# Tests: Auth Routes
# ==============================================================================
@patch("app.api.routes.get_session")
def test_auth_login_success(mock_get_session: MagicMock, client: FlaskClient) -> None:
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    mock_user = MagicMock(spec=User)
    mock_user.id = uuid.uuid7()
    mock_user.email = "test@lab.com"
    mock_user.check_password.return_value = True

    mock_role = MagicMock()
    mock_role.name = "Operator"
    mock_user.roles = [mock_role]

    # Mock the SQLAlchemy chain: session.execute(stmt).scalars().first()
    mock_session.execute.return_value.scalars.return_value.first.return_value = (
        mock_user
    )

    response = client.post(
        "/api/auth/login",
        json={"username": "valid_operator", "password": "correct_password"},
    )

    assert response.status_code == 200
    assert "access_token" in response.get_json()


@patch("app.api.routes.get_session")
def test_auth_login_failure(mock_get_session: MagicMock, client: FlaskClient) -> None:
    # Simulating user not found
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    mock_session.execute.return_value.scalars.return_value.first.return_value = None

    response = client.post(
        "/api/auth/login",
        json={"username": "invalid_user", "password": "wrong_password"},
    )
    assert response.status_code == 401


def test_auth_me_valid_token(client: FlaskClient, operator_token: str) -> None:
    headers = {"Authorization": f"Bearer {operator_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert "roles" in response.get_json()


def test_auth_me_missing_token(client: FlaskClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


# ==============================================================================
# Tests: User Routes (CRUD & RBAC)
# ==============================================================================
@patch("app.api.routes.UserRepository")
@patch("app.api.routes.get_session")
def test_get_users_admin_success(
    mock_get_session: MagicMock,
    mock_user_repo: MagicMock,
    client: FlaskClient,
    admin_token: str,
) -> None:
    mock_repo_instance = MagicMock()
    mock_user_repo.return_value = mock_repo_instance

    mock_user = MagicMock()
    mock_user.id = uuid.uuid7()
    mock_user.username = "admin_user"
    mock_repo_instance.get_all_active.return_value = [mock_user]

    response = client.get(
        "/api/users", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)


def test_get_users_operator_forbidden(client: FlaskClient, operator_token: str) -> None:
    response = client.get(
        "/api/users", headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert response.status_code == 403


@patch("app.api.routes.UserRepository")
@patch("app.api.routes.get_session")
def test_create_user_admin_success(
    mock_get_session: MagicMock,
    mock_user_repo: MagicMock,
    client: FlaskClient,
    admin_token: str,
) -> None:
    mock_repo_instance = MagicMock()
    mock_user_repo.return_value = mock_repo_instance

    mock_user = MagicMock()
    mock_user.id = uuid.uuid7()
    mock_user.username = "tech1"
    mock_repo_instance.create.return_value = mock_user

    payload = {
        "username": "tech1",
        "email": "tech1@lab.com",
        "password": "SuperSecretPassword!",
        "roles": ["Operator"],
    }
    response = client.post(
        "/api/users", json=payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 201
    assert response.get_json()["username"] == "tech1"


def test_create_user_invalid_payload_bad_request(
    client: FlaskClient, admin_token: str
) -> None:
    payload = {"username": "tech1"}  # Missing email and password
    response = client.post(
        "/api/users", json=payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400


@patch("app.api.routes.UserRepository")
@patch("app.api.routes.get_session")
def test_delete_user_admin_success(
    mock_get_session: MagicMock,
    mock_user_repo: MagicMock,
    client: FlaskClient,
    admin_token: str,
) -> None:
    mock_repo_instance = MagicMock()
    mock_user_repo.return_value = mock_repo_instance

    target_uuid = str(uuid.uuid7())
    response = client.delete(
        f"/api/users/{target_uuid}", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    mock_repo_instance.delete.assert_called_once()


# ==============================================================================
# Tests: Template Routes (CRUD & RBAC)
# ==============================================================================
@patch("app.api.routes.TemplateRepository")
@patch("app.api.routes.get_session")
def test_create_template_senior_success(
    mock_get_session: MagicMock,
    mock_template_repo: MagicMock,
    client: FlaskClient,
    senior_token: str,
) -> None:
    mock_repo_instance = MagicMock()
    mock_template_repo.return_value = mock_repo_instance

    mock_template = MagicMock()
    mock_template.id = uuid.uuid7()
    mock_template.template_identifier = "Flu-A-Assay"
    mock_repo_instance.create.return_value = mock_template

    payload = {
        "template_identifier": "Flu-A-Assay",
        "multiplex_mapping": {"ROX": ["FluA"]},
        "description": "Validation Assay",
    }
    response = client.post(
        "/api/templates",
        json=payload,
        headers={"Authorization": f"Bearer {senior_token}"},
    )
    assert response.status_code == 201


def test_create_template_operator_forbidden(
    client: FlaskClient, operator_token: str
) -> None:
    payload = {
        "template_identifier": "Flu-A-Assay",
        "multiplex_mapping": {"ROX": ["FluA"]},
    }
    response = client.post(
        "/api/templates",
        json=payload,
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 403


@patch("app.api.routes.TemplateRepository")
@patch("app.api.routes.get_session")
def test_update_template_admin_success(
    mock_get_session: MagicMock,
    mock_template_repo: MagicMock,
    client: FlaskClient,
    admin_token: str,
) -> None:
    mock_repo_instance = MagicMock()
    mock_template_repo.return_value = mock_repo_instance

    mock_template = MagicMock()
    mock_template.id = uuid.uuid7()
    mock_template.is_active = False
    mock_repo_instance.update_status.return_value = mock_template

    target_uuid = str(uuid.uuid7())
    response = client.put(
        f"/api/templates/{target_uuid}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.get_json()["is_active"] is False


# ==============================================================================
# Tests: Runs & Results
# ==============================================================================
def test_runs_upload_missing_gdpr_consent_fails(
    client: FlaskClient, operator_token: str
) -> None:
    response = client.post(
        "/api/runs/upload",
        headers={"Authorization": f"Bearer {operator_token}"},
        data={"consent_gdpr_phi": "false", "template_id": "template-uuid"},
    )
    assert response.status_code == 400


@patch("app.api.routes.AnalysisService")
@patch("app.api.routes.get_session")
def test_runs_upload_success_with_consent(
    mock_get_session: MagicMock,
    mock_analysis_service: MagicMock,
    client: FlaskClient,
    operator_token: str,
) -> None:
    mock_service_instance = MagicMock()
    mock_analysis_service.return_value = mock_service_instance
    mock_service_instance.process_run.return_value = {
        "run_id": "run-uuid",
        "status": "processed",
    }

    data = {
        "consent_gdpr_phi": "true",
        "template_id": "template-uuid",
        "file": (
            io.BytesIO(b"well,target,temperature,rfu\nA01,FAM,60.0,1000.0"),
            "test.csv",
        ),
    }
    response = client.post(
        "/api/runs/upload",
        data=data,
        headers={"Authorization": f"Bearer {operator_token}"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert "run_id" in response.get_json()


def test_results_validate_rbac_forbidden_for_operator(
    client: FlaskClient, operator_token: str
) -> None:
    result_uuid = str(uuid.uuid7())
    response = client.post(
        f"/api/results/{result_uuid}/validate",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"is_positive": True, "override_reason": "False alarm"},
    )
    assert response.status_code == 403


@patch("app.api.routes.SampleResultRepository")
@patch("app.api.routes.get_session")
def test_results_validate_success_for_authorized_role(
    mock_get_session: MagicMock,
    mock_result_repo: MagicMock,
    client: FlaskClient,
    senior_token: str,
) -> None:
    mock_repo_instance = MagicMock()
    mock_result_repo.return_value = mock_repo_instance

    result_uuid = str(uuid.uuid7())
    response = client.post(
        f"/api/results/{result_uuid}/validate",
        headers={"Authorization": f"Bearer {senior_token}"},
        json={"is_positive": True, "override_reason": "Clinical sign-off"},
    )

    assert response.status_code == 200
    mock_repo_instance.update_tech_validation.assert_called_once()
