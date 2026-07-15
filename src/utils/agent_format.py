from typing import Any, Callable


def text_value(value: Any) -> str:
    """Convert a CSV, ASL, or LLM value into a plain string."""
    return str(value or "")


def stripped_text(value: Any) -> str:
    """Convert a value into stripped text."""
    return str(value or "").strip()


def int_value(value: Any) -> int:
    """Convert a numeric CSV/ASL value to int, accepting float-like strings."""
    return int(float(value))


def safe_int(value: Any, default: int = 0) -> int:
    """Convert a value into an integer with a defensive fallback."""
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


def row_args(row: dict, schema: list[tuple[str, Callable[[Any], Any]]]) -> list:
    """Apply a casting schema to a row and produce ordered belief arguments."""
    return [cast(row.get(name, "")) for name, cast in schema]


def asl_string(value: object) -> str:
    """Serialize a Python value as a quoted AgentSpeak string."""
    return '"' + str(value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'
