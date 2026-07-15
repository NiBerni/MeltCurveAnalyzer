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


class User(Base):
    """
    User entity handling IAM / RBAC operations for the PCR LIMS application.
    """

    __tablename__ = "users"

    # Identity[cite: 1, 2]
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    # Core Attributes[cite: 1, 2]
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships[cite: 1]

    # One-to-Many: User as an operator of PCR Runs[cite: 1, 2]
    pcr_runs: Mapped[list["PcrRun"]] = relationship("PcrRun", back_populates="operator")

    # One-toMany: User as the technical validator of sample results[cite: 1, 2]
    sample_results: Mapped[list["SampleResult"]] = relationship(
        "SampleResult", back_populates="tech_validated_by"
    )

    # Many-to-Many: User's assigned roles (Admin, TA, AL, Arzt, ...) via user_roles[cite: 1, 2]
    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users"
    )


def __repr__(self) -> str:
    """Standard f-string implementation for debugging/logging purposes."""
    return (
        f'<User(id={self.id}, username="{self.username}",  is_active={self.is_active})>'
    )


# --- TDD Stubs  ---


class PcrRun(Base):
    __tablename__ = "pcr_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    operator: Mapped["User"] = relationship(back_populates="pcr_runs")


class SampleResult(Base):
    __tablename__ = "sample_results"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    tech_validated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    tech_validated_by: Mapped["User"] = relationship(back_populates="sample_results")


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)

    users: Mapped[list["User"]] = relationship(
        secondary=user_roles, back_populates="roles"
    )
