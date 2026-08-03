import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.db.models import AssayTemplate
from app.db.repositories import TemplateRepository


@pytest.fixture
def sample_template_data() -> dict[str, Any]:
    return {
        "template_identifier": "RESP_PANEL_V1",
        "multiplex_mapping": {
            "FAM": ["SARS-CoV-2", "Flu A"],
            "HEX": ["Flu B", "RSV"],
            "CY5": ["Internal Extraction Control"],
        },
        "description": "Comprehensive multiplex panel for winter respiratory viruses.",
    }


def test_repository_create_template(
    db_session: Session, sample_template_data: dict[str, Any]
) -> None:
    repo = TemplateRepository(db_session)
    template = repo.create(**sample_template_data)

    assert isinstance(template, AssayTemplate)
    assert isinstance(template.id, uuid.UUID)
    assert template.template_identifier == sample_template_data["template_identifier"]
    assert template.multiplex_mapping == sample_template_data["multiplex_mapping"]
    assert template.description == sample_template_data["description"]


def test_repository_get_template_by_identifier(
    db_session: Session, sample_template_data: dict[str, Any]
) -> None:
    repo = TemplateRepository(db_session)
    repo.create(**sample_template_data)

    fetched_template = repo.get_by_identifier(
        sample_template_data["template_identifier"]
    )

    assert isinstance(fetched_template, AssayTemplate)
    assert fetched_template is not None
    assert (
        fetched_template.template_identifier
        == sample_template_data["template_identifier"]
    )
    assert (
        fetched_template.multiplex_mapping == sample_template_data["multiplex_mapping"]
    )


def test_repository_get_template_not_found(db_session: Session) -> None:
    repo = TemplateRepository(db_session)

    fetched_template = repo.get_by_identifier("INVALID_OR_MISSING_ID_0000")

    assert fetched_template is None
