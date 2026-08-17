"""
Provides defensive data validation structures.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationPayload:
    is_positive: bool
    override_reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ValidationPayload":
        if not data:
            raise ValueError("Empty request body")

        is_positive = data.get("is_positive")
        override_reason = data.get("override_reason")

        if not isinstance(is_positive, bool):
            raise ValueError("'is_positive' must be a boolean.")
        if not isinstance(override_reason, str) or not override_reason.strip():
            raise ValueError("'override_reason' must be a non-empty string.")

        return cls(is_positive=is_positive, override_reason=override_reason.strip())
