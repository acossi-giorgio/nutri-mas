from __future__ import annotations

from typing import Any

import streamlit as st

from src.ui.events import UIEvent
from src.utils.time_utils import current_datetime

_INTERACTIVE_EVENT_TYPES = frozenset({"question", "meal_confirmation"})
_STATE_SCHEMA_VERSION = 3


def initialize_state() -> None:
    """Create the chat state and discard state from incompatible queue versions."""
    if st.session_state.get("state_schema_version") != _STATE_SCHEMA_VERSION:
        st.session_state.state_schema_version = _STATE_SCHEMA_VERSION
        st.session_state.messages = []
        st.session_state.active_question_context = None
        st.session_state.active_interaction = None
        st.session_state.pending_events = []
        st.session_state.awaiting_agent_response = False
        st.session_state.message_sequence = 0
        st.session_state.runtime_event_cursor = 0
        return

    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("active_question_context", None)
    st.session_state.setdefault("active_interaction", None)
    st.session_state.setdefault("pending_events", [])
    st.session_state.setdefault("awaiting_agent_response", False)
    st.session_state.setdefault("runtime_event_cursor", 0)
    _ensure_message_sequences()


def _ensure_message_sequences() -> None:
    """Give existing messages stable, monotonic identities without losing history."""
    messages = st.session_state.messages
    used: set[int] = set()
    maximum = 0
    unsequenced: list[dict[str, Any]] = []
    for message in messages:
        sequence = message.get("sequence")
        if isinstance(sequence, int) and sequence > 0 and sequence not in used:
            used.add(sequence)
            maximum = max(maximum, sequence)
        else:
            unsequenced.append(message)
    for message in unsequenced:
        maximum += 1
        message["sequence"] = maximum
    st.session_state.message_sequence = maximum


def _next_message_sequence() -> int:
    """Return the next chat message sequence."""
    sequence = int(st.session_state.get("message_sequence", 0)) + 1
    st.session_state.message_sequence = sequence
    return sequence


def ordered_messages() -> list[dict[str, Any]]:
    """Return chat messages in their immutable creation order."""
    return sorted(
        st.session_state.messages,
        key=lambda message: int(message.get("sequence", 0)),
    )


def timestamp() -> str:
    """Create a compact timestamp for the visible chat history."""
    return current_datetime().strftime("%H:%M")


def append_user_message(text: str) -> None:
    """Append a user message to the chat."""
    st.session_state.messages.append(
        {
            "role": "user",
            "content": text,
            "timestamp": timestamp(),
            "payload": {},
            "sequence": _next_message_sequence(),
        }
    )


def append_local_error(message: str, code: str) -> None:
    """Append a locally generated assistant error with a stable identity."""
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": message,
            "timestamp": timestamp(),
            "event_type": "error",
            "payload": {"code": code},
            "sequence": _next_message_sequence(),
        }
    )


def _append_event(event: UIEvent) -> dict[str, Any]:
    """Append an agent event to the chat."""
    message = {
        "role": "assistant",
        "content": event.message,
        "timestamp": timestamp(),
        "event_type": event.type,
        "payload": event.payload,
        "sequence": _next_message_sequence(),
    }
    st.session_state.messages.append(message)
    return message


def _activate_interaction(event: UIEvent) -> dict[str, Any]:
    """Make exactly one question or confirmation available to the user."""
    st.session_state.active_interaction = event.type
    # Short replies need the visible question as translation context.
    st.session_state.active_question_context = event.message
    return _append_event(event)


def _deliver_event(event: UIEvent) -> dict[str, Any]:
    """Render one event, making it active when it requires a user reply."""
    if event.type in _INTERACTIVE_EVENT_TYPES:
        return _activate_interaction(event)
    return _append_event(event)


def _drain_pending_events() -> None:
    """Deliver queued information in order, stopping at the next interaction."""
    pending = st.session_state.pending_events
    while pending and not st.session_state.active_interaction:
        event = pending.pop(0)
        if event.type == "status":
            continue
        if event.type == "session_closed":
            st.session_state.active_question_context = None
            st.session_state.active_interaction = None
            pending.clear()
            _append_event(event)
            return
        _deliver_event(event)


def apply_event(event: UIEvent) -> dict[str, Any] | None:
    """Apply an event while keeping every later visible event in one FIFO queue."""
    if event.type == "status":
        return None
    # Discard a startup greeting if another event has already reached the chat.
    if event.payload.get("code") == "welcome_back" and st.session_state.messages:
        return None
    if event.type == "session_closed":
        st.session_state.active_question_context = None
        st.session_state.active_interaction = None
        st.session_state.pending_events.clear()
        st.session_state.awaiting_agent_response = False
        return _append_event(event)

    # Later events must not overtake a visible question.
    if st.session_state.active_interaction:
        st.session_state.pending_events.append(event)
        return None

    # Queue proactive reminders while a user answer is being translated.
    if st.session_state.awaiting_agent_response and event.type == "meal_confirmation":
        st.session_state.pending_events.append(event)
        return None

    if st.session_state.awaiting_agent_response:
        st.session_state.awaiting_agent_response = False
        message = _deliver_event(event)
        # Interactive responses own the next turn; other responses release the queue.
        if event.type not in _INTERACTIVE_EVENT_TYPES:
            _drain_pending_events()
        return message

    message = _deliver_event(event)
    return message


def begin_user_turn() -> str | None:
    """Track an outstanding reply without locking the chat input."""
    context = st.session_state.active_question_context
    st.session_state.active_question_context = None
    st.session_state.active_interaction = None
    st.session_state.awaiting_agent_response = True
    return context


def cancel_user_turn(context: str | None) -> None:
    """Restore the active question after a command could not be queued."""
    st.session_state.awaiting_agent_response = False
    st.session_state.active_question_context = context
    st.session_state.active_interaction = "question" if context else None
