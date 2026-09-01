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
    assert getattr(template, "is_active", True) is True


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


def test_repository_update_template(
    db_session: Session, sample_template_data: dict[str, Any]
) -> None:
    repo = TemplateRepository(db_session)
    template = repo.create(**sample_template_data)

    new_mapping = {
        "FAM": ["SARS-CoV-2"],
        "HEX": ["Flu A", "Flu B", "RSV"],
        "CY5": ["Internal Extraction Control"],
    }

    updated_template = repo.update(
        template_id=template.id,
        multiplex_mapping=new_mapping,
        description="Updated viral multiplex mapping.",
    )

    assert updated_template is not None
    assert updated_template.id == template.id
    assert updated_template.multiplex_mapping == new_mapping
    assert updated_template.description == "Updated viral multiplex mapping."
    assert (
        updated_template.template_identifier
        == sample_template_data["template_identifier"]
    )


def test_repository_delete_template_soft_deactivates(
    db_session: Session, sample_template_data: dict[str, Any]
) -> None:
    # Delete should only deactivate(is_active = False) an AssayTemplate
    repo = TemplateRepository(db_session)
    template = repo.create(**sample_template_data)

    repo.delete(template.id)

    # Assert template still exists but is marked as inactive
    fetched_template = repo.get_by_identifier(
        sample_template_data["template_identifier"]
    )
    assert fetched_template is not None
    assert getattr(fetched_template, "is_active", None) is False
