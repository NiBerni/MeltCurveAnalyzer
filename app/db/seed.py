"""
Automated Database Bootstrap, Alembic Migration Runner & Initial Data Seeder.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

from loguru import logger
from sqlalchemy import select, text, tstring
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AssayTemplate, Base, Permission, Role, User
from app.db.repositories import TemplateRepository, UserRepository
from app.db.session import SessionLocal, engine

ADMIN_USERNAME = os.environ.get("SEED_ADMIN_USERNAME", "admin_master")
ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin_master@lims.local")
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "AdminMasterPassword2026!")

SENIOR_USERNAME = os.environ.get("SEED_SENIOR_USERNAME", "senior_validator")
SENIOR_EMAIL = os.environ.get("SEED_SENIOR_EMAIL", "senior@lims.local")
SENIOR_PASSWORD = os.environ.get("SEED_SENIOR_PASSWORD", "SeniorPass2026!")

OPERATOR_USERNAME = os.environ.get("SEED_OPERATOR_USERNAME", "lab_operator")
OPERATOR_EMAIL = os.environ.get("SEED_OPERATOR_EMAIL", "operator@lims.local")
OPERATOR_PASSWORD = os.environ.get("SEED_OPERATOR_PASSWORD", "OperatorPass2026!")

COMPREHENSIVE_TEMPLATE_ID = "COMPREHENSIVE_MULTIPLEX_V1"

COMPREHENSIVE_6_CHANNEL_MAPPING: dict[str, dict[str, Any]] = {
    "FAM": {
        "targets": ["SARS-CoV-2_N_Gene", "SARS-CoV-2_E_Gene"],
        "expected_tms": [78.5, 83.2],
    },
    "HEX": {
        "targets": ["Influenza_A_M1", "Influenza_B_NS1"],
        "expected_tms": [76.0, 81.5],
    },
    "TexasRed": {
        "targets": ["RSV_A_Polymerase", "RSV_B_Nucleocapsid"],
        "expected_tms": [74.8, 80.4],
    },
    "ROX": {
        "targets": ["Adenovirus_Hexon", "hMPV_Fusion_Gene"],
        "expected_tms": [77.2, 84.0],
    },
    "Cy5": {
        "targets": ["Rhinovirus_5UTR", "Parainfluenza_Type3"],
        "expected_tms": [75.5, 82.0],
    },
    "Cy5.5": {
        "targets": ["Mycoplasma_pneumoniae", "IC_Human_RNaseP"],
        "expected_tms": [79.0, 85.5],
    },
}


def wait_for_database(max_retries: int = 30, delay_seconds: float = 2.0) -> None:
    """Blocks until PostgreSQL 18 accepts connections."""
    logger.info("Checking PostgreSQL database connectivity...")
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("PostgreSQL database connection established.")
            return
        except OperationalError as exc:
            logger.warning(
                f"Database not ready yet (attempt {attempt}/{max_retries}): {exc}"
            )
            time.sleep(delay_seconds)

    raise RuntimeError(
        f"CRITICAL: Could not connect to PostgreSQL after {max_retries} attempts."
    )


def run_migrations_and_schema_sync() -> None:
    """
    Executes `alembic upgrade head` if migrations folder and alembic.ini exist,
    and guarantees all SQLAlchemy 2.1 tables are created.
    """
    alembic_cfg_path = Path("alembic.ini")
    migrations_dir = Path("migrations")
    if alembic_cfg_path.is_file() and migrations_dir.is_dir():
        logger.info(
            "Found alembic.ini & migrations/ -> Running 'alembic upgrade head'..."
        )
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            logger.info("Alembic migrations applied successfully.")
        else:
            logger.warning(
                f"Alembic upgrade returned non-zero exit code ({result.returncode}): "
                f"{result.stderr.strip()}. Falling back to metadata.create_all()."
            )
    else:
        logger.info(
            "Alembic setup not fully present -> Using SQLAlchemy 2.1 Base.metadata.create_all()."
        )

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema verified and synchronized.")


def seed_rbac_roles_and_permissions(session: Session) -> dict[str, Role]:
    """Seeds standard LIMS permissions and roles idempotently using PEP 750 t-strings."""
    permissions_spec = {
        "manage_users": "Create, update, and deactivate LIMS user accounts.",
        "manage_templates": "Create, update, and deactivate multiplex assay templates.",
        "upload_runs": "Ingest cycler CSV/XML files and trigger AI melt curve analysis.",
        "view_runs": "Inspect PCR run metadata, raw melt curves, and target results.",
        "validate_results": "Perform technical validation and override escalated results.",
    }

    perm_objects: dict[str, Permission] = {}
    for perm_name, perm_desc in permissions_spec.items():
        stmt = select(Permission).from_statement(
            tstring(t"SELECT * FROM permissions WHERE name = {perm_name}")
        )
        perm = session.execute(stmt).scalars().first()
        if perm is None:
            perm = Permission(name=perm_name, description=perm_desc)
            session.add(perm)
            session.flush()
            logger.info(f"Seeded Permission: '{perm_name}'")
        perm_objects[perm_name] = perm

    roles_spec: dict[str, tuple[str, list[str]]] = {
        "Admin": (
            "Full system administrator with unrestricted IAM, template, and validation rights.",
            list(permissions_spec.keys()),
        ),
        "Senior": (
            "Senior Technical Assistant / Lab Scientist authorized for assay setup and escalation sign-off.",
            ["manage_templates", "upload_runs", "view_runs", "validate_results"],
        ),
        "Validator": (
            "Technical Validator authorized to review and sign off escalated PCR results.",
            ["view_runs", "validate_results"],
        ),
        "Operator": (
            "Standard laboratory operator authorized to upload runs and inspect results.",
            ["upload_runs", "view_runs"],
        ),
    }

    role_objects: dict[str, Role] = {}
    for role_name, (role_desc, assigned_perms) in roles_spec.items():
        stmt = select(Role).from_statement(
            tstring(t"SELECT * FROM roles WHERE name = {role_name}")
        )
        role = session.execute(stmt).scalars().first()
        if role is None:
            role = Role(name=role_name, description=role_desc)
            session.add(role)
            session.flush()
            logger.info(f"Seeded Role: '{role_name}'")

        role_permissions = getattr(role, "permissions")
        existing_perm_names = {p.name for p in role_permissions}
        for p_name in assigned_perms:
            if p_name not in existing_perm_names:
                role_permissions.append(perm_objects[p_name])

        role_objects[role_name] = role

    session.flush()
    return role_objects


def seed_default_users(session: Session) -> None:
    """Seeds `admin_master` (all rights) plus `senior_validator` and `lab_operator` accounts."""
    user_repo = UserRepository(session)

    users_to_seed: list[dict[str, Any]] = [
        {
            "username": ADMIN_USERNAME,
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "roles": ["Admin", "Senior", "Validator", "Operator"],
        },
        {
            "username": SENIOR_USERNAME,
            "email": SENIOR_EMAIL,
            "password": SENIOR_PASSWORD,
            "roles": ["Senior", "Validator"],
        },
        {
            "username": OPERATOR_USERNAME,
            "email": OPERATOR_EMAIL,
            "password": OPERATOR_PASSWORD,
            "roles": ["Operator"],
        },
    ]

    for spec in users_to_seed:
        uname = cast(str, spec["username"])
        mail = cast(str, spec["email"])
        pwd = cast(str, spec["password"])
        r_list = cast(list[str], spec["roles"])

        existing_user: User | None = user_repo.get_by_username(uname)
        if existing_user is None:
            created = user_repo.create(
                username=uname,
                email=mail,
                password=pwd,
                roles=r_list,
            )
            logger.info(
                f"Seeded User '{created.username}' (ID: {created.id}) with roles: {r_list}"
            )
        else:
            logger.info(
                f"User '{existing_user.username}' already exists (ID: {existing_user.id}). Skipping."
            )


def seed_comprehensive_template(session: Session) -> AssayTemplate:
    """
    Seeds the 6-channel, 12-target dummy assay template (`COMPREHENSIVE_MULTIPLEX_V1`).
    """
    template_repo = TemplateRepository(session)
    existing_tpl = template_repo.get_by_identifier(COMPREHENSIVE_TEMPLATE_ID)

    description = (
        "6-Channel / 12-Target Respiratory Multiplex Panel (2 expected Tm peaks per channel: "
        "FAM, HEX, TexasRed, ROX, Cy5, Cy5.5)."
    )

    if existing_tpl is None:
        tpl = template_repo.create(
            template_identifier=COMPREHENSIVE_TEMPLATE_ID,
            multiplex_mapping=COMPREHENSIVE_6_CHANNEL_MAPPING,
            description=description,
        )
        logger.info(
            f"Seeded 6-Channel / 12-Target AssayTemplate '{tpl.template_identifier}' (ID: {tpl.id})"
        )
        return tpl

    logger.info(
        f"AssayTemplate '{existing_tpl.template_identifier}' already exists (ID: {existing_tpl.id})."
    )
    return existing_tpl


def bootstrap() -> None:
    """Main entrypoint for database initialization and seeding."""
    wait_for_database()
    run_migrations_and_schema_sync()

    session = SessionLocal()
    try:
        seed_rbac_roles_and_permissions(session)
        seed_default_users(session)
        seed_comprehensive_template(session)
        session.commit()
        logger.info("Database bootstrap and seeding completed successfully.")
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error(f"Database seeding failed, transaction rolled back: {exc}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    bootstrap()
