import datetime
import io
import uuid
from collections.abc import Generator
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
    mock_user.is_active = True
    mock_user.check_password.return_value = True

    mock_role = MagicMock()
    mock_role.name = "Operator"
    mock_user.roles = [mock_role]

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
def test_auth_login_deactivated_user_rejected(
    mock_get_session: MagicMock, client: FlaskClient
) -> None:
    """Verifies that a soft-deleted user (is_active=False) cannot log in."""
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    mock_user = MagicMock(spec=User)
    mock_user.id = uuid.uuid7()
    mock_user.is_active = False
    mock_user.check_password.return_value = True
    mock_session.execute.return_value.scalars.return_value.first.return_value = (
        mock_user
    )

    response = client.post(
        "/api/auth/login",
        json={"username": "deactivated_user", "password": "correct_password"},
    )
    assert response.status_code == 401


@patch("app.api.routes.get_session")
def test_auth_login_failure(mock_get_session: MagicMock, client: FlaskClient) -> None:
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
    mock_repo_instance.create.assert_called_once_with(
        username="tech1",
        email="tech1@lab.com",
        password="SuperSecretPassword!",
        roles=["Operator"],
    )


def test_create_user_invalid_payload_bad_request(
    client: FlaskClient, admin_token: str
) -> None:
    payload = {"username": "tech1"}
    response = client.post(
        "/api/users", json=payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400


@patch("app.api.routes.UserRepository")
@patch("app.api.routes.get_session")
def test_update_user_admin_success_and_not_found(
    mock_get_session: MagicMock,
    mock_user_repo: MagicMock,
    client: FlaskClient,
    admin_token: str,
) -> None:
    """Verifies PUT /api/users/<uuid:user_id> for 200 OK and 404 Not Found."""
    mock_repo_instance = MagicMock()
    mock_user_repo.return_value = mock_repo_instance

    target_uuid = uuid.uuid7()
    mock_updated_user = MagicMock()
    mock_updated_user.id = target_uuid
    mock_updated_user.username = "tech1_updated"
    mock_updated_user.email = "tech1_new@lab.com"
    mock_updated_user.is_active = True
    mock_repo_instance.update.return_value = mock_updated_user

    response = client.put(
        f"/api/users/{target_uuid}",
        json={"username": "tech1_updated", "email": "tech1_new@lab.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.get_json()["username"] == "tech1_updated"

    # Simulate user not found
    mock_repo_instance.update.return_value = None
    not_found_res = client.put(
        f"/api/users/{target_uuid}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert not_found_res.status_code == 404


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
def test_get_templates_list_and_single_detail(
    mock_get_session: MagicMock,
    mock_template_repo: MagicMock,
    client: FlaskClient,
    operator_token: str,
) -> None:
    """Verifies GET /api/templates and GET /api/templates/<uuid:template_id>."""
    mock_repo_instance = MagicMock()
    mock_template_repo.return_value = mock_repo_instance

    tpl_id = uuid.uuid7()
    mock_tpl = MagicMock()
    mock_tpl.id = tpl_id
    mock_tpl.template_identifier = "RESP_V1"
    mock_tpl.multiplex_mapping = {"FAM": ["FluA"]}
    mock_tpl.description = "Resp panel"
    mock_tpl.is_active = True

    mock_repo_instance.get_all_active.return_value = [mock_tpl]
    mock_repo_instance.get_by_id.return_value = mock_tpl

    list_res = client.get(
        "/api/templates", headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert list_res.status_code == 200
    assert len(list_res.get_json()) == 1

    detail_res = client.get(
        f"/api/templates/{tpl_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert detail_res.status_code == 200
    assert detail_res.get_json()["name"] == "RESP_V1"


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


@patch("app.api.routes.TemplateRepository")
@patch("app.api.routes.get_session")
def test_update_template_full_mapping_success(
    mock_get_session: MagicMock,
    mock_template_repo: MagicMock,
    client: FlaskClient,
    senior_token: str,
) -> None:
    """Verifies PUT /api/templates/<uuid:template_id> delegates to repo.update when mapping is provided."""
    mock_repo_instance = MagicMock()
    mock_template_repo.return_value = mock_repo_instance

    mock_template = MagicMock()
    mock_template.id = uuid.uuid7()
    mock_template.is_active = True
    mock_repo_instance.update.return_value = mock_template

    target_uuid = str(uuid.uuid7())
    response = client.put(
        f"/api/templates/{target_uuid}",
        json={"multiplex_mapping": {"FAM": ["SARS-CoV-2"]}, "description": "Updated"},
        headers={"Authorization": f"Bearer {senior_token}"},
    )
    assert response.status_code == 200
    mock_repo_instance.update.assert_called_once()


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


@patch("app.api.routes.PcrRunRepository")
@patch("app.api.routes.get_session")
def test_get_runs_and_run_details_success(
    mock_get_session: MagicMock,
    mock_run_repo: MagicMock,
    client: FlaskClient,
    operator_token: str,
) -> None:
    """Verifies GET /api/runs and GET /api/runs/<uuid:run_id> with full nested hierarchy."""
    mock_repo_instance = MagicMock()
    mock_run_repo.return_value = mock_repo_instance

    run_id = uuid.uuid7()
    mock_curve = MagicMock()
    mock_curve.id = uuid.uuid7()
    mock_curve.target_channel = "FAM"
    mock_curve.temperatures = [60.0, 61.0]
    mock_curve.raw_fluorescence = [100.0, 95.0]

    mock_result = MagicMock()
    mock_result.id = uuid.uuid7()
    mock_result.target_name = "SARS-CoV-2"
    mock_result.algo_is_positive = True
    mock_result.algo_tm_peaks = [82.5]
    mock_result.cluster_label = "Wildtype"
    mock_result.tech_val_is_positive = True
    mock_result.tech_validated_by_id = uuid.uuid7()
    mock_result.tech_validated_at = datetime.datetime.now(datetime.UTC)
    mock_result.override_reason = "Confirmed"
    mock_result.export_status = "pending"

    mock_sample = MagicMock()
    mock_sample.id = uuid.uuid7()
    mock_sample.well_position = "a01"
    mock_sample.melt_curves = [mock_curve]
    mock_sample.sample_results = [mock_result]

    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.run_identifier = "RUN_2026_01"
    mock_run.device_id = "LC480"
    mock_run.raw_operator = "Op1"
    mock_run.imported_by_id = uuid.uuid7()
    mock_run.samples = [mock_sample]

    mock_repo_instance.get_all.return_value = [mock_run]
    mock_repo_instance.get_by_id.return_value = mock_run

    list_res = client.get(
        "/api/runs", headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert list_res.status_code == 200
    assert len(list_res.get_json()) == 1

    detail_res = client.get(
        f"/api/runs/{run_id}", headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert detail_res.status_code == 200
    payload = detail_res.get_json()
    assert payload["run_id"] == str(run_id)
    assert len(payload["samples"]) == 1
    assert payload["samples"][0]["results"][0]["cluster_label"] == "Wildtype"


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
    mock_repo_instance.update_tech_validation.return_value = MagicMock()

    result_uuid = str(uuid.uuid7())
    response = client.post(
        f"/api/results/{result_uuid}/validate",
        headers={"Authorization": f"Bearer {senior_token}"},
        json={"is_positive": True, "override_reason": "Clinical sign-off"},
    )
    assert response.status_code == 200
    mock_repo_instance.update_tech_validation.assert_called_once()


@patch("app.api.routes.SampleResultRepository")
@patch("app.api.routes.get_session")
def test_results_validate_not_found_and_invalid_body(
    mock_get_session: MagicMock,
    mock_result_repo: MagicMock,
    client: FlaskClient,
    senior_token: str,
) -> None:
    """Verifies 404 when SampleResult is missing and 400 when override_reason is empty."""
    mock_repo_instance = MagicMock()
    mock_result_repo.return_value = mock_repo_instance
    mock_repo_instance.update_tech_validation.return_value = None

    result_uuid = str(uuid.uuid7())
    not_found_res = client.post(
        f"/api/results/{result_uuid}/validate",
        headers={"Authorization": f"Bearer {senior_token}"},
        json={"is_positive": False, "override_reason": "Valid reason"},
    )
    assert not_found_res.status_code == 404

    bad_req_res = client.post(
        f"/api/results/{result_uuid}/validate",
        headers={"Authorization": f"Bearer {senior_token}"},
        json={"is_positive": False, "override_reason": "   "},
    )
    assert bad_req_res.status_code == 400
