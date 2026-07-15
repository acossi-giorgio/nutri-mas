from __future__ import annotations
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_DEFAULT_TZ = "Europe/Rome"
_TZ = ZoneInfo(_DEFAULT_TZ)


def _parse_speed(value: str | float | int | None) -> float:
    """Handle parse speed."""
    if value in (None, ""):
        return 1.0
    try:
        parsed = float(str(value).strip().lower().removesuffix("x"))
    except ValueError:
        return 1.0
    return parsed if parsed > 0 else 1.0


def _env_clock_speed() -> float:
    """Handle env clock speed."""
    return _parse_speed(os.getenv("NUTRIMAS_CLOCK_SPEED") or os.getenv("CLOCK_SPEED"))


def _mode_for_speed(speed: float) -> str:
    """Handle mode for speed."""
    return "simulated" if speed != 1.0 else "real"


_INITIAL_SPEED = _env_clock_speed()
_MODE = _mode_for_speed(_INITIAL_SPEED)
_SPEED = _INITIAL_SPEED
_REAL_ANCHOR = datetime.now(_TZ)


def _parse_datetime(value: str | None, fallback: datetime) -> datetime:
    """Parse an optional ISO datetime in the project timezone."""
    if not value:
        return fallback
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_TZ)
    return parsed.astimezone(_TZ)


_SIM_ANCHOR = _REAL_ANCHOR


def configure_clock(
    *,
    mode: str | None = None,
    timezone: str | None = None,
    simulated_start: str | None = None,
    speed: float | str | None = None,
) -> None:
    """Configure the clock used by both the runtime and simulations."""
    global _TZ, _MODE, _SPEED, _REAL_ANCHOR, _SIM_ANCHOR
    if timezone:
        _TZ = ZoneInfo(timezone)
    _MODE = (mode or _MODE or "real").strip().lower()
    _SPEED = _parse_speed(speed if speed not in (None, "") else _SPEED)
    _REAL_ANCHOR = datetime.now(_TZ)
    _SIM_ANCHOR = _parse_datetime(simulated_start, _REAL_ANCHOR)


def current_datetime() -> datetime:
    """Return the real or simulated time shared by all agents."""
    now = datetime.now(_TZ)
    if _MODE != "simulated":
        return now
    elapsed = now - _REAL_ANCHOR
    return _SIM_ANCHOR + timedelta(seconds=elapsed.total_seconds() * _SPEED)


def weekday_name(dt: datetime | None = None) -> str:
    """Return the lowercase weekday name used by ASL plans."""
    return (dt or current_datetime()).strftime("%A").lower()
