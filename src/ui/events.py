from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, ClassVar


class EventValidationError(ValueError):
    """Raised when a UI transport payload does not match the contract."""


@dataclass(frozen=True, slots=True)
class UICommand:
    """A user command submitted by the single-user Streamlit interface."""

    version: int = 1
    type: str = "user_text"
    text: str = ""
    question_context: str | None = None

    _ALLOWED_TYPES: ClassVar[frozenset[str]] = frozenset({"user_text"})

    def __post_init__(self) -> None:
        """Validate the initialized value."""
        if self.version != 1:
            raise EventValidationError(f"Unsupported command version: {self.version}")
        if self.type not in self._ALLOWED_TYPES:
            raise EventValidationError(f"Unsupported command type: {self.type}")
        if not isinstance(self.text, str) or not self.text.strip():
            raise EventValidationError("Command text must be a non-empty string.")
        if self.question_context is not None and not isinstance(
            self.question_context, str
        ):
            raise EventValidationError("Question context must be a string or null.")

    def to_json(self) -> str:
        """Serialize the value to JSON."""
        return json.dumps(
            {
                "version": self.version,
                "type": self.type,
                "text": self.text.strip(),
                "question_context": self.question_context or None,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str) -> "UICommand":
        """Deserialize and validate a JSON value."""
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise EventValidationError("Command is not valid JSON.") from exc
        if not isinstance(value, dict):
            raise EventValidationError("Command must be a JSON object.")
        expected = {"version", "type", "text", "question_context"}
        if set(value) != expected:
            raise EventValidationError("Command fields do not match the contract.")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class UIEvent:
    """A structured event emitted by Gateway and consumed by Streamlit."""

    version: int = 1
    type: str = "message"
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    _ALLOWED_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "message",
            "question",
            "plan",
            "meal_confirmation",
            "status",
            "error",
            "session_closed",
        }
    )

    def __post_init__(self) -> None:
        """Validate the initialized value."""
        if self.version != 1:
            raise EventValidationError(f"Unsupported event version: {self.version}")
        if self.type not in self._ALLOWED_TYPES:
            raise EventValidationError(f"Unsupported event type: {self.type}")
        if not isinstance(self.message, str):
            raise EventValidationError("Event message must be a string.")
        if not isinstance(self.payload, dict):
            raise EventValidationError("Event payload must be an object.")
        self._validate_payload()

    def _validate_payload(self) -> None:
        """Validate the event payload."""
        if self.type == "question" and not isinstance(
            self.payload.get("question_context"), str
        ):
            raise EventValidationError("Question events require question_context.")
        if self.type == "plan":
            if self.payload.get("scope") not in {"weekly", "daily", "current"}:
                raise EventValidationError("Plan events require a valid scope.")
            rows = self.payload.get("rows")
            if not isinstance(rows, list) or not all(
                isinstance(row, dict) for row in rows
            ):
                raise EventValidationError("Plan events require a list of rows.")
        if self.type == "error":
            if not isinstance(self.payload.get("code"), str):
                raise EventValidationError("Error events require a code.")
            if not isinstance(self.payload.get("retryable"), bool):
                raise EventValidationError("Error events require retryable.")

    def to_json(self) -> str:
        """Serialize the value to JSON."""
        return json.dumps(
            {
                "version": self.version,
                "type": self.type,
                "message": self.message,
                "payload": self.payload,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str) -> "UIEvent":
        """Deserialize and validate a JSON value."""
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise EventValidationError("Event is not valid JSON.") from exc
        if not isinstance(value, dict):
            raise EventValidationError("Event must be a JSON object.")
        expected = {"version", "type", "message", "payload"}
        if set(value) != expected:
            raise EventValidationError("Event fields do not match the contract.")
        return cls(**value)
