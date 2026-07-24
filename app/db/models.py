"""
Database models for the Identity & Access Management (IAM) layer.
"""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Table, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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

    __tablename__ = "pcr_run"

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


class SampleResult(Base):
    __tablename__ = "sample_results"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    tech_validated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    tech_validated_by: Mapped["User"] = relationship(back_populates="sample_results")
