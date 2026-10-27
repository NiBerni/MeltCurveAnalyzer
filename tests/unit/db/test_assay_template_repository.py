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
        is_active=False,
    )
    assert updated_template is not None
    assert updated_template.id == template.id
    assert updated_template.multiplex_mapping == new_mapping
    assert updated_template.description == "Updated viral multiplex mapping."
    assert updated_template.is_active is False
    assert (
        updated_template.template_identifier
        == sample_template_data["template_identifier"]
    )


def test_repository_get_all_active_templates(
    db_session: Session, sample_template_data: dict[str, Any]
) -> None:
    """Verifies that get_all_active() returns only active templates."""
    repo = TemplateRepository(db_session)
    active_tpl = repo.create(**sample_template_data)
    inactive_tpl = repo.create(
        template_identifier="DEPRECATED_PANEL_V0",
        multiplex_mapping={"FAM": ["OldTarget"]},
        description="Deprecated panel",
    )
    repo.delete(inactive_tpl.id)

    active_list = repo.get_all_active()
    active_ids = {t.id for t in active_list}
    assert active_tpl.id in active_ids
    assert inactive_tpl.id not in active_ids


def test_repository_delete_template_soft_deactivates(
    db_session: Session, sample_template_data: dict[str, Any]
) -> None:
    repo = TemplateRepository(db_session)
    template = repo.create(**sample_template_data)
    repo.delete(template.id)

    fetched_template = repo.get_by_identifier(
        sample_template_data["template_identifier"]
    )

    assert fetched_template is not None
    assert getattr(fetched_template, "is_active", None) is False
