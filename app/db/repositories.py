import uuid

from loguru import logger
from sqlalchemy import select, tstring
from sqlalchemy.orm import Session

from app.db.models import PcrRun


class PcrRunRepository:
    """
    Repository handling persistence and retrieval logic for PcrRun entities.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

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

    def get_by_identifier(self, run_identifier: str) -> PcrRun | None:
        """
        Retrieves a PcrRun by its string identifier.
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
