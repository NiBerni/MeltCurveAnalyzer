"""
Database models for the Identity & Access Management (IAM) layer.
"""

import datetime
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Table,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Uuid, ForeignKey("roles.id"), primary_key=True),
)


role_permissions = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", Uuid, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Uuid, ForeignKey("permissions.id"), primary_key=True),
)


class User(Base):
    """
    User entity handling IAM / RBAC operations for the PCR LIMS application.
    """

    __tablename__ = "users"

    # Identity
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    # Core Attributes
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # One-to-Many: User as an operator of PCR Runs
    pcr_runs: Mapped[list["PcrRun"]] = relationship(
        "PcrRun", back_populates="imported_by"
    )

    # One-toMany: User as the technical validator of sample results
    sample_results: Mapped[list["SampleResult"]] = relationship(
        "SampleResult", back_populates="tech_validated_by"
    )

    # Many-to-Many: User's assigned roles (Admin, TA, AL, Arzt, ...) via user_roles
    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users"
    )

    def set_password(self, password: str) -> None:
        """
        Creates a hash out of a clear-text password
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """
        Checks if the pw fits the hash of the pw
        """
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        """Standard f-string implementation for debugging/logging purposes."""
        return f'<User(id={self.id}, username="{self.username}",  is_active={self.is_active})>'


class Role(Base):
    """
    Role entity defining specific privileges within the PCR LIMS application.
    Part of the Identity & Access Management (IAM) / RBAC architecture.
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    users: Mapped[list["User"]] = relationship(
        "User", secondary=user_roles, back_populates="roles"
    )

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )

    def __repr__(self) -> str:
        """
        Standard f-string implementation for debugging/logging purposes.
        """
        return f'<Role(id={self.id}, name="{self.name}")>'


class Permission(Base):
    """
    Permission entity defining specific granular access rights within the application.
    Part of the Identity & Access Management (IAM) / RBAC architecture.
    """

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )

    def __repr__(self) -> str:
        """
        Standard f-string implementation for debugging/logging purposes.
        """
        return f'<Permission(id={self.id}, name="{self.name}")>'


class PcrRun(Base):
    """
    PcrRun entity handling the ingestion state of a batch of PCR samples.
    """

    __tablename__ = "pcr_runs"

    # Identity
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    # Core Attributes
    run_identifier: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_operator: Mapped[str | None] = mapped_column(String, nullable=True)

    # Foreign Keys
    imported_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    # Relationships
    imported_by: Mapped["User"] = relationship("User", back_populates="pcr_runs")

    samples: Mapped[list["Sample"]] = relationship(
        "Sample", back_populates="pcr_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """
        Standard f-string implementation for debugging/logging purposes.
        Returns a human-readable representation of the PCR Run
        """
        return f'<PcrRun(id={self.id}, run_identifier="{self.run_identifier}")>'


class Sample(Base):
    """
    SQLAlchemy model representing a sample/well within a PCR run.
    """

    __tablename__ = "samples"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)
    pcr_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pcr_runs.id"), nullable=False
    )
    well_position: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    pcr_run: Mapped["PcrRun"] = relationship(back_populates="samples")
    melt_curves: Mapped[list["MeltCurve"]] = relationship(
        back_populates="sample", cascade="all, delete-orphan"
    )


class MeltCurve(Base):
    __tablename__ = "melt_curves"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)
    sample_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("samples.id"), nullable=False
    )
    target_channel: Mapped[str] = mapped_column(String, nullable=False)
    temperatures: Mapped[list[float]] = mapped_column(
        ARRAY(Float).with_variant(JSON, "sqlite"), nullable=False
    )
    raw_fluorescence: Mapped[list[float]] = mapped_column(
        ARRAY(Float).with_variant(JSON, "sqlite"), nullable=False
    )

    sample: Mapped["Sample"] = relationship("Sample", back_populates="melt_curves")


class SampleResult(Base):
    """
    SampleResult entity encapsulating the final analytical output of the MeltCurveAnalyzer and ClusterClassifier.
    Stores both the algorithmic clustering results and the manual technical validation (RBAC escalation).
    """

    __tablename__ = "sample_results"

    # Core Identity
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    # Foreign Keys & Core Data
    sample_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("samples.id"), nullable=False
    )
    target_name: Mapped[str] = mapped_column(String, nullable=False)

    # Algorithmic Results
    algo_is_positive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    algo_tm_peaks: Mapped[list[float]] = mapped_column(
        ARRAY(Float).with_variant(JSON, "sqlite"), nullable=False
    )
    cluster_label: Mapped[str] = mapped_column(String, nullable=False)

    # Technical Validation (Escalation / Override capabilities)
    tech_val_is_positive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tech_validated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    tech_validated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    override_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    # Export & LIS Status
    export_status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending"
    )
    exported_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Relationships
    tech_validated_by: Mapped["User"] = relationship(
        "User", back_populates="sample_results", uselist=False
    )

    def __repr__(self) -> str:
        """Standard f-string implementation for debugging/logging purposes."""
        return (
            f"<SampleResult(id={self.id}, target='{self.target_name}', "
            f"algo_positive={self.algo_is_positive}, cluster='{self.cluster_label}', "
            f"export_status='{self.export_status}')>"
        )


class AssayTemplate(Base):
    """
    AssayTemplate entity defining assay configuration parameters like
    target definitions, expected Tm values, and multiplex mappings.
    """

    __tablename__ = "assay_templates"

    # Core Identity
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    # Required Attributes
    template_identifier: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )
    multiplex_mapping: Mapped[dict[str, list[str]]] = mapped_column(
        JSON, nullable=False
    )

    # Optional Attributes
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        """Standard f-string implementation for debugging/logging purposes."""
        return f'<AssayTemplate(id={self.id}, template_identifier="{self.template_identifier}")>'
