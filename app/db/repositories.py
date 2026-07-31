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

from app.db.models import PcrRun, SampleResult

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
        self.session.commit()
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
        self.session.commit()
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

        self.session.commit()
        self.session.refresh(result)

        logger.info(
            f"Successfully updated technical validation for SampleResult ID: {result.id}"
        )

        return result
