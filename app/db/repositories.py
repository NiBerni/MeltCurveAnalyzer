"""
app/db/repositories.py
"""

import datetime
import functools
import uuid
from typing import Any, Callable, TypeVar, cast

from loguru import logger
from sqlalchemy import select, tstring
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AssayTemplate, PcrRun, SampleResult, User

F = TypeVar("F", bound=Callable[..., Any])


def log_repository_action(action_name: str) -> Callable[[F], F]:
    """
    Custom decorator for consistent error handling and execution logging within
    the Data Access Layer. Safely intercepts and logs SQLAlchemy exceptions.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except SQLAlchemyError as e:
                logger.error(f"Database error during {action_name}: {e}")
                raise

        return cast(F, wrapper)

    return decorator


class UserRepository:
    """
    Repository handling persistence and retrieval logic for User entities.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    @log_repository_action("create_user")
    def create(self, username: str, email: str, password: str) -> User:
        """Creates a new User, ensuring password hashing occurs before DB flush."""
        new_user = User(
            username=username,
            email=email,
        )
        new_user.set_password(password)

        self.session.add(new_user)
        self.session.flush()
        self.session.refresh(new_user)

        logger.info(f"Successfully created User '{username}' with ID: {new_user.id}")
        return new_user

    @log_repository_action("get_user_by_id")
    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Retrieves a User by their ID using PEP 750 t-strings."""
        stmt = select(User).from_statement(
            tstring(t"SELECT * FROM users WHERE id = {user_id}")
        )
        return self.session.execute(stmt).scalars().first()

    @log_repository_action("get_user_by_username")
    def get_by_username(self, username: str) -> User | None:
        """Retrieves a User by their username using PEP 750 t-strings."""
        stmt = select(User).from_statement(
            tstring(t"SELECT * FROM users WHERE username = {username}")
        )
        return self.session.execute(stmt).scalars().first()

    @log_repository_action("update_user")
    def update(self, user_id: uuid.UUID, **kwargs: Any) -> User | None:
        """Updates arbitrary attributes of a User entity dynamically."""
        user = self.get_by_id(user_id)
        if user is None:
            logger.warning(f"Failed to update User: ID '{user_id}' not found.")
            return None

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        self.session.flush()
        self.session.refresh(user)
        logger.info(f"Successfully updated User ID: {user.id}")
        return user

    @log_repository_action("delete_user")
    def delete(self, user_id: uuid.UUID) -> None:
        """Soft-deactivates a user to preserve database relationships and audit trails."""
        user = self.get_by_id(user_id)
        if user is not None:
            user.is_active = False
            self.session.flush()
            logger.info(f"Successfully soft-deleted User ID: {user_id}")


class PcrRunRepository:
    """
    Repository handling persistence and retrieval logic for PcrRun entities.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    @log_repository_action("create_pcr_run")
    def create(
        self,
        run_identifier: str,
        device_id: str | None,
        raw_operator: str | None,
        imported_by_id: uuid.UUID,
    ) -> PcrRun:
        """
        Creates, persists, and refreshes a new PcrRun record.
        """
        new_run = PcrRun(
            run_identifier=run_identifier,
            device_id=device_id,
            raw_operator=raw_operator,
            imported_by_id=imported_by_id,
        )

        self.session.add(new_run)
        self.session.flush()
        self.session.refresh(new_run)

        logger.info(f"Successfully created PcrRun with ID: {new_run.id}")

        return new_run

    @log_repository_action("get_pcr_run_by_identifier")
    def get_by_identifier(self, run_identifier: str) -> PcrRun | None:
        """
        Retrieves a PcrRun by its string identifier using PEP 750 t-strings for security.
        """
        stmt = select(PcrRun).from_statement(
            tstring(t"SELECT * FROM pcr_runs WHERE run_identifier = {run_identifier}")
        )

        result = self.session.execute(stmt).scalars().first()

        if result is None:
            logger.warning(f"PcrRun with identifier '{run_identifier}' not found.")
        else:
            logger.info(f"Successfully fetched PcrRun '{run_identifier}'.")

        return result


class SampleResultRepository:
    """
    Repository handling persistence, retrieval, and updating logic for SampleResult entities.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    @log_repository_action("create_sample_result")
    def create(
        self,
        sample_id: uuid.UUID,
        target_name: str,
        algo_is_positive: bool,
        algo_tm_peaks: list[float],
        cluster_label: str,
        tech_val_is_positive: bool | None = None,
    ) -> SampleResult:
        """
        Creates, persists, and refreshes a new SampleResult record.
        """
        new_result = SampleResult(
            sample_id=sample_id,
            target_name=target_name,
            algo_is_positive=algo_is_positive,
            algo_tm_peaks=algo_tm_peaks,
            cluster_label=cluster_label,
            tech_val_is_positive=tech_val_is_positive,
        )

        self.session.add(new_result)
        self.session.flush()
        self.session.refresh(new_result)

        logger.info(f"Successfully created SampleResult with ID: {new_result.id}")

        return new_result

    @log_repository_action("get_sample_result_by_id")
    def get_by_id(self, result_id: uuid.UUID) -> SampleResult | None:
        """
        Retrieves a SampleResult safely by its UUID.
        Must use PEP 750 template strings to prevent SQL injection.
        """
        stmt = select(SampleResult).from_statement(
            tstring(t"SELECT * FROM sample_results WHERE id = {result_id}")
        )

        result = self.session.execute(stmt).scalars().first()

        if result is None:
            logger.warning(f"SampleResult with ID '{result_id}' not found.")
        else:
            logger.info(f"Successfully fetched SampleResult '{result_id}'.")

        return result

    @log_repository_action("update_tech_validation")
    def update_tech_validation(
        self,
        result_id: uuid.UUID,
        is_positive: bool,
        validated_by_id: uuid.UUID,
        override_reason: str,
    ) -> SampleResult | None:
        """
        Updates the technical validation status of a SampleResult, simulating an escalation resolution.
        Automatically sets the validation timestamp to UTC now.
        """
        result = self.get_by_id(result_id)

        # Guard clause handling the "not found" state natively
        if result is None:
            logger.warning(
                f"Failed to update tech validation: SampleResult '{result_id}' does not exist."
            )
            return None

        # Update domain fields
        result.tech_val_is_positive = is_positive
        result.tech_validated_by_id = validated_by_id
        result.override_reason = override_reason
        result.tech_validated_at = datetime.datetime.now(datetime.UTC)

        self.session.flush()
        self.session.refresh(result)

        logger.info(
            f"Successfully updated technical validation for SampleResult ID: {result.id}"
        )

        return result


class TemplateRepository:
    """
    Repository handling persistence and retrieval logic for AssayTemplate entities.
    Manages CRUD operations for assay configuration parameters required by the processing pipeline.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    @log_repository_action("create_template")
    def create(
        self,
        template_identifier: str,
        multiplex_mapping: dict[str, list[str]],
        description: str | None = None,
    ) -> AssayTemplate:
        """
        Creates, persists, and refreshes a new AssayTemplate record.
        """
        new_template = AssayTemplate(
            template_identifier=template_identifier,
            multiplex_mapping=multiplex_mapping,
            description=description,
        )

        self.session.add(new_template)
        self.session.flush()
        self.session.refresh(new_template)

        logger.info(f"Successfully created AssayTemplate with ID: {new_template.id}")

        return new_template

    @log_repository_action("get_template_by_identifier")
    def get_by_identifier(self, template_identifier: str) -> AssayTemplate | None:
        """
        Retrieves an AssayTemplate safely by its string identifier.
        Exclusively uses PEP 750 template strings for strict SQL injection prevention.
        """
        stmt = select(AssayTemplate).from_statement(
            tstring(
                t"SELECT * FROM assay_templates WHERE template_identifier = {template_identifier}"
            )
        )

        result = self.session.execute(stmt).scalars().first()

        if result is None:
            logger.warning(
                f"AssayTemplate with identifier '{template_identifier}' not found."
            )
        else:
            logger.info(f"Successfully fetched AssayTemplate '{template_identifier}'.")

        return result

    @log_repository_action("update_template")
    def update(
        self,
        template_id: uuid.UUID,
        multiplex_mapping: dict[str, list[str]],
        description: str | None = None,
    ) -> AssayTemplate | None:
        """Updates a template's mapping and description natively."""
        stmt = select(AssayTemplate).from_statement(
            tstring(t"SELECT * FROM assay_templates WHERE id = {template_id}")
        )
        template = self.session.execute(stmt).scalars().first()

        if template is None:
            logger.warning(
                f"Failed to update AssayTemplate: ID '{template_id}' not found."
            )
            return None

        template.multiplex_mapping = multiplex_mapping
        if description is not None:
            template.description = description

        self.session.flush()
        self.session.refresh(template)
        logger.info(f"Successfully updated AssayTemplate ID: {template.id}")
        return template

    @log_repository_action("delete_template")
    def delete(self, template_id: uuid.UUID) -> None:
        """Soft-deactivates an AssayTemplate to prevent breaking existing analytical records."""
        stmt = select(AssayTemplate).from_statement(
            tstring(t"SELECT * FROM assay_templates WHERE id = {template_id}")
        )
        template = self.session.execute(stmt).scalars().first()

        if template is not None:
            template.is_active = False
            self.session.flush()
            logger.info(f"Successfully soft-deleted AssayTemplate ID: {template_id}")
