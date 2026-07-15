from __future__ import annotations

from collections import defaultdict
import html
from typing import Any

import streamlit as st

from src.domain.constants import MEAL_LABELS, WEEKDAY_LABELS


def _render_bubble(role: str, content: str, timestamp: str = "") -> None:
    """Render one escaped message bubble with role-based alignment."""
    normalized_role = "user" if role == "user" else "assistant"
    author = "You" if normalized_role == "user" else "Nutri-MAS"
    safe_content = html.escape(content).replace("\n", "<br>")
    safe_timestamp = html.escape(timestamp.strip())
    timestamp_html = (
        f'<time class="nutrimas-chat-timestamp">{safe_timestamp}</time>'
        if safe_timestamp
        else ""
    )
    st.html(f"""
        <div class="nutrimas-chat-row {normalized_role}">
          <div class="nutrimas-chat-bubble">
            <div class="nutrimas-chat-author">{author}</div>
            <div class="nutrimas-chat-content">{safe_content}</div>
            {timestamp_html}
          </div>
        </div>
        """)


def render_message(message: dict[str, Any]) -> None:
    """Render one chat message without inspecting transport or ASL syntax."""
    role = str(message.get("role", "assistant"))
    content = str(message.get("content", ""))
    timestamp = str(message.get("timestamp", ""))
    if content:
        _render_bubble(role, content, timestamp)
    payload = message.get("payload") or {}
    if message.get("event_type") == "plan":
        render_plan(payload.get("rows", []))
    elif payload.get("rows"):
        st.dataframe(payload["rows"], hide_index=True)


def render_plan(rows: list[dict[str, Any]]) -> None:
    """Render a plan from structured payload rows."""
    ordered = sorted(
        rows,
        key=lambda row: (
            (
                list(WEEKDAY_LABELS).index(str(row.get("day", "")))
                if row.get("day") in WEEKDAY_LABELS
                else 99
            ),
            (
                list(MEAL_LABELS).index(str(row.get("slot", "")))
                if row.get("slot") in MEAL_LABELS
                else 99
            ),
        ),
    )
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        by_day[str(row.get("day", ""))].append(row)
    for day, day_rows in by_day.items():
        with st.expander(WEEKDAY_LABELS.get(day, day.title()), expanded=False):
            for row in day_rows:
                slot = str(row.get("slot", ""))
                dish = str(row.get("dish", "")).strip() or "Unnamed meal"
                with st.container(border=True, gap="small"):
                    st.markdown(
                        f"**{MEAL_LABELS.get(slot, slot.replace('_', ' ').title())}**"
                    )
                    st.write(dish)
                    st.caption(
                        " · ".join(
                            [
                                f"{row.get('calories', 0)} kcal",
                                f"Protein {row.get('protein_g', 0)} g",
                                f"Carbs {row.get('carbs_g', 0)} g",
                                f"Fat {row.get('fat_g', 0)} g",
                            ]
                        )
                    )
                    ingredients = str(row.get("ingredients", "")).strip()
                    instructions = str(row.get("instructions", "")).strip()
                    if ingredients:
                        st.markdown("**Ingredients**")
                        st.write(ingredients)
                    if instructions:
                        st.markdown("**Description and preparation**")
                        st.write(instructions)
