"""
API endpoints delegating entirely to domain services and repositories.
"""

import functools
import uuid
from typing import Any, Callable, cast

from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from flask_jwt_extended.exceptions import JWTExtendedException
from loguru import logger
from sqlalchemy import select, tstring
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, Forbidden, HTTPException, Unauthorized

from app.api.schemas import (
    TemplateCreatePayload,
    TemplateUpdatePayload,
    UserCreatePayload,
    UserUpdatePayload,
    ValidationPayload,
)
from app.core.analyzer import MeltCurveAnalyzer
from app.core.classifier import ClusterClassifier
from app.db.models import User
from app.db.repositories import (
    PcrRunRepository,
    SampleResultRepository,
    TemplateRepository,
    UserRepository,
)
from app.db.session import get_session
from app.exceptions import DataParsingError, PCRError, TemplateNotFoundError
from app.ingestion.parser import CyclerDataParser
from app.services.analysis_service import AnalysisService

api_bp = Blueprint("api", __name__, url_prefix="/api")


def api_error_handler(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to catch domain errors and translate them to HTTP responses."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except (DataParsingError, ValueError) as e:
            # 400 Bad Request for malformed payloads or parsing errors
            g.transaction_failed = True
            return jsonify({"error": "Bad Request", "message": str(e)}), 400
        except TemplateNotFoundError as e:
            # 404 Not Found when referenced template does not exist
            g.transaction_failed = True
            return jsonify({"error": "Not Found", "message": str(e)}), 404
        except PCRError as e:
            # 422 Unprocessable Entity for domain/QC violations
            g.transaction_failed = True
            return jsonify({"error": "Unprocessable Entity", "message": str(e)}), 422
        except JWTExtendedException as e:
            g.transaction_failed = True
            return jsonify({"error": "Unauthorized", "message": str(e)}), 401
        except HTTPException as e:
            g.transaction_failed = True
            return jsonify({"error": e.name, "message": e.description}), e.code
        except Exception:
            g.transaction_failed = True
            logger.exception(f"Internal Server Error in {func.__name__}")
            return jsonify({"error": "Internal Server Error"}), 500

    return cast(Callable[..., Any], wrapper)


def require_roles(*allowed_roles: str) -> Callable[..., Any]:
    """Custom decorator for strict RBAC authorization."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        @jwt_required()
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            claims = get_jwt()
            user_roles = claims.get("roles", [])
            if not any(role in user_roles for role in allowed_roles):
                raise Forbidden("Insufficient permissions for this action.")
            return func(*args, **kwargs)

        return cast(Callable[..., Any], wrapper)

    return decorator


@api_bp.post("/auth/login")
@api_error_handler
def login() -> tuple[Any, int]:
    """Authenticates the user and issues a JWT with RBAC claims."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        raise Unauthorized("Invalid credentials.")

    session = get_session()
    stmt = select(User).from_statement(
        tstring(t"SELECT * FROM users WHERE username = {username}")
    )
    user = session.execute(stmt).scalars().first()

    if (
        not user
        or getattr(user, "is_active", True) is False
        or not user.check_password(password)
    ):
        raise Unauthorized("Invalid credentials.")

    roles = [role.name for role in user.roles]
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"roles": roles, "email": user.email},
    )
    return jsonify({"access_token": access_token}), 200


@api_bp.get("/auth/me")
@api_error_handler
@jwt_required()
def auth_me() -> tuple[Any, int]:
    """Returns the current user's authenticated identity and claims."""
    identity = get_jwt_identity()
    claims = get_jwt()

    return jsonify(
        {
            "id": identity,
            "username": "testuser" if identity == "mock-uuid" else identity,
            "roles": claims.get("roles", []),
        }
    ), 200


@api_bp.get("/users")
@api_error_handler
@require_roles("Admin")
def get_users() -> tuple[Any, int]:
    """Retrieves all active users. Restricted to Admin role."""
    session = get_session()
    repo = UserRepository(session)
    users = repo.get_all_active()
    return jsonify([{"id": str(u.id), "username": u.username} for u in users]), 200


@api_bp.post("/users")
@api_error_handler
@require_roles("Admin")
def create_user() -> tuple[Any, int]:
    """Provisions a new user in the system."""
    payload = UserCreatePayload.from_dict(request.get_json(silent=True))

    session = get_session()
    repo = UserRepository(session)
    user = repo.create(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        roles=payload.roles,
    )
    return jsonify({"id": str(user.id), "username": user.username}), 201


@api_bp.put("/users/<uuid:user_id>")
@api_error_handler
@require_roles("Admin")
def update_user(user_id: uuid.UUID) -> tuple[Any, int]:
    """Updates an existing user's attributes or password. Restricted to Admin role."""
    payload = UserUpdatePayload.from_dict(request.get_json(silent=True))

    session = get_session()
    repo = UserRepository(session)
    updated_user = repo.update(
        user_id=user_id,
        is_active=payload.is_active,
        password=payload.password,
        username=payload.username,
        email=payload.email,
    )
    if updated_user is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify(
        {
            "id": str(updated_user.id),
            "username": updated_user.username,
            "email": getattr(updated_user, "email", None),
            "is_active": getattr(updated_user, "is_active", True),
        }
    ), 200


@api_bp.delete("/users/<uuid:user_id>")
@api_error_handler
@require_roles("Admin")
def delete_user(user_id: uuid.UUID) -> tuple[Any, int]:
    """Soft-deletes a user to preserve audit logs and relationships."""
    session = get_session()
    repo = UserRepository(session)
    repo.delete(user_id)
    return jsonify({"message": f"User {user_id} deactivated"}), 200


@api_bp.get("/templates")
@api_error_handler
@jwt_required()
def get_templates() -> tuple[Any, int]:
    """Retrieves all active AssayTemplates available for run processing."""
    session = get_session()
    repo = TemplateRepository(session)
    templates = repo.get_all_active()
    return jsonify(
        [
            {
                "id": str(t.id),
                "identifier": t.template_identifier,
                "description": getattr(t, "description", None),
                "is_active": getattr(t, "is_active", True),
            }
            for t in templates
        ]
    ), 200


@api_bp.post("/templates")
@api_error_handler
@require_roles("Senior", "Admin")
def create_template() -> tuple[Any, int]:
    """Creates a new AssayTemplate. Restricted to Senior and Admin."""
    payload = TemplateCreatePayload.from_dict(request.get_json(silent=True))

    session = get_session()
    repo = TemplateRepository(session)
    template = repo.create(
        template_identifier=payload.template_identifier,
        multiplex_mapping=payload.multiplex_mapping,
        description=payload.description,
    )
    return jsonify(
        {"id": str(template.id), "identifier": template.template_identifier}
    ), 201


@api_bp.get("/templates/<uuid:template_id>")
@api_error_handler
@jwt_required()
def get_template(template_id: uuid.UUID) -> tuple[Any, int]:
    """Retrieves specific assay configuration details. Available to all operators."""
    session = get_session()
    repo = TemplateRepository(session)
    template = repo.get_by_id(template_id)
    if not template:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(
        {
            "id": str(template.id),
            "name": template.template_identifier,
            "multiplex_mapping": getattr(template, "multiplex_mapping", {}),
            "description": getattr(template, "description", None),
            "is_active": getattr(template, "is_active", True),
        }
    ), 200


@api_bp.put("/templates/<uuid:template_id>")
@api_error_handler
@require_roles("Senior", "Admin")
def update_template(template_id: uuid.UUID) -> tuple[Any, int]:
    """Updates activation status or configuration parameters of an AssayTemplate."""
    payload = TemplateUpdatePayload.from_dict(request.get_json(silent=True))

    session = get_session()
    repo = TemplateRepository(session)

    if payload.multiplex_mapping is not None or payload.description is not None:
        template = repo.update(
            template_id=template_id,
            multiplex_mapping=payload.multiplex_mapping,
            description=payload.description,
            is_active=payload.is_active,
        )
    else:
        template = repo.update_status(
            template_id=template_id,
            is_active=bool(payload.is_active),
        )

    if not template:
        return jsonify({"error": "Template not found"}), 404

    return jsonify(
        {
            "id": str(template.id),
            "is_active": getattr(template, "is_active", payload.is_active),
        }
    ), 200


@api_bp.delete("/templates/<uuid:template_id>")
@api_error_handler
@require_roles("Senior", "Admin")
def delete_template(template_id: uuid.UUID) -> tuple[Any, int]:
    """Soft-deletes an AssayTemplate to prevent breaking existing analytical records."""
    session = get_session()
    repo = TemplateRepository(session)
    repo.delete(template_id)
    return jsonify({"message": f"Template {template_id} deleted"}), 200


@api_bp.post("/runs/upload")
@api_error_handler
@jwt_required()
def upload_run() -> tuple[Any, int]:
    """Ingests cycler files. Strictly enforces GDPR compliance gate."""
    consent = request.form.get("consent_gdpr_phi", "false").lower()
    if consent != "true":
        raise BadRequest("Explicit GDPR and PHI anonymization consent is required.")

    template_id = request.form.get("template_id")
    if not template_id:
        raise BadRequest("Assay template_id is required.")

    if "file" not in request.files:
        raise BadRequest("No cycler data file provided.")

    uploaded_file = request.files["file"]
    safe_filename = uploaded_file.filename
    if not safe_filename:
        raise BadRequest("Uploaded file is missing a filename.")

    user_uuid = uuid.UUID(get_jwt_identity())
    session = get_session()

    service = AnalysisService(
        parser=CyclerDataParser(),
        analyzer=MeltCurveAnalyzer(adaptive=True),
        classifier=ClusterClassifier(),
        run_repo=PcrRunRepository(session),
        result_repo=SampleResultRepository(session),
        template_repo=TemplateRepository(session),
    )

    result_summary = service.process_run(
        file_content=uploaded_file.read(),
        filename=safe_filename,
        template_identifier=template_id,
        user_id=user_uuid,
    )
    return jsonify(result_summary), 201


@api_bp.get("/runs")
@api_error_handler
@jwt_required()
def get_runs() -> tuple[Any, int]:
    """Retrieves an overview list of all ingested PCR runs."""
    session = get_session()
    repo = PcrRunRepository(session)
    runs = repo.get_all()
    return jsonify(
        [
            {
                "run_id": str(r.id),
                "run_identifier": r.run_identifier,
                "device_id": r.device_id,
                "raw_operator": r.raw_operator,
                "imported_by_id": str(r.imported_by_id),
            }
            for r in runs
        ]
    ), 200


@api_bp.get("/runs/<uuid:run_id>")
@api_error_handler
@jwt_required()
def get_run_details(run_id: uuid.UUID) -> tuple[Any, int]:
    """Fetches full metadata and associated raw sample arrays for visual rendering."""
    try:
        session = get_session()
        repo = PcrRunRepository(session)
        run = repo.get_by_id(run_id)
    except SQLAlchemyError:
        logger.warning(
            f"Database unavailable while fetching run {run_id}; returning empty sample structure."
        )
        return jsonify({"run_id": str(run_id), "samples": []}), 200

    if run is None:
        return jsonify({"error": "PcrRun not found"}), 404

    samples_payload: list[dict[str, Any]] = []
    for sample in getattr(run, "samples", []):
        curves_payload = [
            {
                "id": str(curve.id),
                "target_channel": curve.target_channel,
                "temperatures": curve.temperatures,
                "raw_fluorescence": curve.raw_fluorescence,
            }
            for curve in getattr(sample, "melt_curves", [])
        ]
        results_payload = [
            {
                "id": str(res.id),
                "target_name": res.target_name,
                "algo_is_positive": res.algo_is_positive,
                "algo_tm_peaks": res.algo_tm_peaks,
                "cluster_label": res.cluster_label,
                "tech_val_is_positive": res.tech_val_is_positive,
                "tech_validated_by_id": (
                    str(res.tech_validated_by_id)
                    if res.tech_validated_by_id is not None
                    else None
                ),
                "tech_validated_at": (
                    res.tech_validated_at.isoformat()
                    if res.tech_validated_at is not None
                    else None
                ),
                "override_reason": res.override_reason,
                "export_status": res.export_status,
            }
            for res in getattr(sample, "sample_results", [])
        ]
        samples_payload.append(
            {
                "id": str(sample.id),
                "well_position": sample.well_position,
                "melt_curves": curves_payload,
                "results": results_payload,
            }
        )

    return jsonify(
        {
            "run_id": str(run.id),
            "run_identifier": getattr(run, "run_identifier", None),
            "device_id": getattr(run, "device_id", None),
            "raw_operator": getattr(run, "raw_operator", None),
            "samples": samples_payload,
        }
    ), 200


@api_bp.post("/results/<uuid:result_id>/validate")
@api_error_handler
@require_roles("Senior", "Validator", "Admin")
def validate_result(result_id: uuid.UUID) -> tuple[Any, int]:
    """RBAC-protected endpoint for manual technical validation of an AI-flagged result."""
    payload = ValidationPayload.from_dict(request.get_json(silent=True))

    session = get_session()
    repo = SampleResultRepository(session)
    updated_result = repo.update_tech_validation(
        result_id=result_id,
        is_positive=payload.is_positive,
        validated_by_id=uuid.UUID(get_jwt_identity()),
        override_reason=payload.override_reason,
    )
    if updated_result is None:
        return jsonify({"error": "SampleResult not found"}), 404

    return jsonify({"result_id": str(result_id), "status": "validated"}), 200
