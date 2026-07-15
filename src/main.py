from __future__ import annotations

import streamlit as st

from src.runtime.agent_runtime import AgentRuntime, RuntimeStatus
from src.ui.rendering import render_message
from src.ui.state import (
    append_local_error,
    append_user_message,
    apply_event,
    begin_user_turn,
    cancel_user_turn,
    initialize_state,
    ordered_messages,
)

_APP_TITLE = "Nutri-MAS"
_APP_STYLES = """
<style>
.nutrimas-chat-row {
    display: flex;
    width: 100%;
    margin: 0.45rem 0 0.9rem;
}
.nutrimas-chat-row.assistant { justify-content: flex-start; }
.nutrimas-chat-row.user { justify-content: flex-end; }
.nutrimas-chat-bubble {
    max-width: min(76%, 52rem);
    padding: 0.8rem 1rem;
    border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
    border-radius: 0.9rem;
    overflow-wrap: anywhere;
}
.nutrimas-chat-row.assistant .nutrimas-chat-bubble {
    background: color-mix(in srgb, currentColor 7%, transparent);
    border-bottom-left-radius: 0.25rem;
}
.nutrimas-chat-row.user .nutrimas-chat-bubble {
    background: color-mix(
        in srgb,
        var(--primary-color, #ff4b4b) 22%,
        transparent
    );
    border-color: color-mix(
        in srgb,
        var(--primary-color, #ff4b4b) 55%,
        transparent
    );
    border-bottom-right-radius: 0.25rem;
}
.nutrimas-chat-author {
    margin-bottom: 0.25rem;
    font-size: 0.75rem;
    font-weight: 650;
    letter-spacing: 0.02em;
    opacity: 0.72;
}
.nutrimas-chat-content { line-height: 1.5; }
.nutrimas-chat-timestamp {
    display: block;
    margin-top: 0.35rem;
    font-size: 0.68rem;
    line-height: 1;
    opacity: 0.55;
    text-align: right;
}
.st-key-chat_input [data-testid="stChatInput"] {
    border-radius: 999px;
    overflow: hidden;
}
.st-key-chat_input [data-testid="stChatInput"],
.st-key-chat_input [data-testid="stChatInput"]:focus-within,
.st-key-chat_input [data-testid="stChatInput"] > div,
.st-key-chat_input [data-testid="stChatInput"] > div:focus-within {
    border-color: transparent !important;
    outline: none !important;
    box-shadow: none !important;
}
.st-key-chat_input [data-testid="stChatInput"] textarea {
    border-radius: 999px;
}
.st-key-chat_input [data-testid="stChatInput"] button {
    border-radius: 50%;
}
</style>
"""

st.set_page_config(
    page_title=_APP_TITLE,
    page_icon=":material/nutrition:",
    layout="wide",
)
st.html(_APP_STYLES)


@st.cache_resource
def get_runtime() -> AgentRuntime:
    """Create the process-wide runtime once and reuse it across reruns."""
    runtime = AgentRuntime()
    runtime.start()
    return runtime


def consume_events(runtime: AgentRuntime) -> int:
    """Replay unseen Gateway events into this Streamlit session."""
    cursor = int(st.session_state.get("runtime_event_cursor", 0))
    next_cursor, events = runtime.poll_events_since(cursor)
    for event in events:
        apply_event(event)
    st.session_state.runtime_event_cursor = next_cursor
    return len(events)


initialize_state()
runtime = get_runtime()

@st.fragment(run_every="500ms")
def poll_agent_events() -> None:
    """Poll cheaply; redraw the full chat only when state actually changes."""
    event_count = consume_events(runtime)
    current_status = runtime.status.value
    previous_status = st.session_state.get("last_runtime_status")
    st.session_state.last_runtime_status = current_status
    if event_count or current_status != previous_status:
        st.rerun()


poll_agent_events()

if runtime.status is RuntimeStatus.STARTING:
    st.info("Starting...")
elif runtime.status is RuntimeStatus.FAILED:
    st.error(runtime.agent_error or "The agent runtime could not start.")

for message in ordered_messages():
    sequence = int(message["sequence"])
    with st.container(key=f"chat_message_{sequence}", gap=None):
        render_message(message)

input_disabled = not runtime.accepting_commands
placeholder = "Starting the agent runtime…" if input_disabled else "Write a message…"
prompt = st.chat_input(
    placeholder,
    key="chat_input",
    disabled=input_disabled,
    submit_mode="submit",
)
if prompt:
    append_user_message(prompt)
    question_context = begin_user_turn()
    try:
        runtime.submit(prompt, question_context)
    except Exception as exc:
        cancel_user_turn(question_context)
        append_local_error(
            f"Communication error: {exc}",
            "runtime_submit_failed",
        )
    st.rerun()
