from __future__ import annotations
import json
import re
from collections.abc import Callable
from typing import Any
import spade.message
from spade.behaviour import CyclicBehaviour
from spade.template import Template
from spade_llm import LLMAgent, LLMProvider, LLMTool, RoutingResponse
from src.domain.constants import ONBOARDING_QUESTIONS
from src.ui.events import UIEvent
from src.utils.asl_message import parse_asl_message
from src.utils.agent_format import asl_string as _asl_string, stripped_text as _as_text
from src.utils.logger import get_logger
from src.utils.qdrant_db import (
    search_message_templates,
    get_translation_signatures,
    init_qdrant,
)
from src.utils.messages_registry import get_messages

logger = get_logger("NLPAgent")
_SUPPORTED_AGENTS = {"nutritionist", "planner"}
_SUPPORTED_PERFORMATIVES = {"tell", "achieve"}
_PLANNING_FAILURES = {
    "planning_in_progress": "A weekly plan is already being generated.",
    "cook_error": "I could not generate every recipe for the weekly plan.",
    "chef_strict_error": "I could not find templates matching the nutrition constraints.",
    "chef_error": "I could not find a valid meal template.",
    "nutrition_rules_violated": "The generated plan does not satisfy the configured nutrition rules.",
}


def _number(value: object) -> int | float | str:
    """Normalize a numeric value."""
    try:
        decimal = float(str(value))
    except (TypeError, ValueError):
        return str(value)
    return int(decimal) if decimal.is_integer() else decimal


def _sentence_start(value: object) -> str:
    """Capitalize the start of a sentence."""
    text = str(value).strip()
    return text[:1].upper() + text[1:]


def _message(code: str, message: str, **payload: object) -> UIEvent:
    """Build a UI message event."""
    return UIEvent(type="message", message=message, payload={"code": code, **payload})


def _error(code: str, detail: str, *, retryable: bool = False) -> UIEvent:
    """Build a UI error event."""
    return UIEvent(
        type="error",
        message=detail,
        payload={"code": code, "detail": detail, "retryable": retryable},
    )


def _present_ask(args: list[object]) -> UIEvent:
    """Format the ask response."""
    context = str(args[0]).strip() if args else "unknown"
    return UIEvent(
        type="question",
        message=ONBOARDING_QUESTIONS.get(
            context, "I need one more piece of information."
        ),
        payload={"question_context": context},
    )


def _present_plan_data(args: list[object]) -> UIEvent:
    """Format the plan data response."""
    if len(args) != 2:
        return _error("invalid_plan_data", "Plan data has an invalid shape.")
    scope = str(args[0]).strip().lower()
    try:
        rows = json.loads(str(args[1]))
    except json.JSONDecodeError:
        return _error("invalid_plan_data", "Plan data is not valid JSON.")
    if scope not in {"weekly", "daily", "current"} or not isinstance(rows, list):
        return _error("invalid_plan_data", "Plan data does not match the UI contract.")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            return _error("invalid_plan_data", "Plan rows must be objects.")
        normalized.append(
            {
                "day": str(row.get("day", "")).lower(),
                "slot": str(row.get("slot", row.get("meal_type", ""))).lower(),
                "dish": str(row.get("dish", row.get("planned_recipe", ""))),
                "template": str(row.get("template", "")),
                "ingredients": str(row.get("ingredients", "")),
                "instructions": str(row.get("instructions", "")),
                "calories": _number(
                    row.get("calories", row.get("planned_calories", 0))
                ),
                "protein_g": _number(
                    row.get("protein_g", row.get("planned_protein_g", 0))
                ),
                "carbs_g": _number(row.get("carbs_g", row.get("planned_carbs_g", 0))),
                "fat_g": _number(row.get("fat_g", row.get("planned_fat_g", 0))),
            }
        )
    title = {
        "weekly": "Your weekly meal plan",
        "daily": "Your daily meal plan",
        "current": "Your current meal plan",
    }[scope]
    return UIEvent(
        type="plan", message=title, payload={"scope": scope, "rows": normalized}
    )


def _present_rebalanced_plan_data(args: list[object]) -> UIEvent:
    """Format the rebalanced plan data response."""
    if len(args) != 1:
        return _error("invalid_plan_data", "Rebalanced plan data has an invalid shape.")
    event = _present_plan_data(["daily", args[0]])
    if event.type != "plan":
        return event
    return UIEvent(
        type="plan",
        message="Your daily rebalanced meal plan",
        payload=event.payload,
    )


def _present_table_data(args: list[object]) -> UIEvent:
    """Format the table data response."""
    if len(args) != 2:
        return _error("invalid_table_data", "Table data has an invalid shape.")
    try:
        rows = json.loads(str(args[1]))
    except json.JSONDecodeError:
        return _error("invalid_table_data", "Table data is not valid JSON.")
    if not isinstance(rows, list):
        return _error("invalid_table_data", "Table rows must be a list.")
    return _message(str(args[0]).strip().lower(), "Your requested data", rows=rows)


def _present_meal_confirmation(args: list[object]) -> UIEvent:
    """Format the meal confirmation response."""
    if len(args) < 5:
        return _error("invalid_confirmation", "Meal confirmation data is invalid.")
    _, date, _, meal_type, recipe = args[:5]
    return UIEvent(
        type="meal_confirmation",
        message=f"Did you eat the planned {str(meal_type).replace('_', ' ')} ({recipe})?",
        payload={
            "date": str(date),
            "meal_type": str(meal_type),
            "planned_recipe": str(recipe),
        },
    )


def _present_profile_complete(args: list[object]) -> UIEvent:
    """Format the profile complete response."""
    if len(args) < 3:
        return _error("invalid_profile", "Profile completion data is invalid.")
    return _message(
        "profile_complete",
        f"Profile completed. Your daily target is {_number(args[0])} kcal. Your goal is {args[1]}. The central healthy-range target weight is {args[2]} kg.",
    )


def _present_welcome(args: list[object]) -> UIEvent:
    """Format the welcome response."""
    if len(args) < 3:
        return _error("invalid_profile", "Welcome data is invalid.")
    return _message(
        "welcome_back",
        f"Welcome back. Your daily target is {_number(args[0])} kcal, with goal {args[1]} and central healthy-range target weight {args[2]} kg.",
    )


def _present_profile_updated(args: list[object]) -> UIEvent:
    """Format the profile updated response."""
    if len(args) < 3:
        return _error("invalid_profile", "Profile update data is invalid.")
    return _message(
        "profile_updated",
        f"Profile updated. Your daily target is {_number(args[0])} kcal. Your goal is {args[1]}. The central healthy-range target weight is {args[2]} kg.",
    )


def _present_weight_progress(args: list[object]) -> UIEvent:
    """Format the weight progress response."""
    if len(args) < 3:
        return _error("invalid_profile", "Weight update data is invalid.")
    weight, target, goal = args[:3]
    if str(goal) == "lose":
        detail = f"Your current plan will stay unchanged until you reach {_number(target)} kg."
    elif str(goal) == "gain":
        detail = f"Your current plan will stay unchanged until you reach {_number(target)} kg."
    else:
        detail = "Your current maintenance plan remains unchanged."
    return _message(
        "weight_progress_updated",
        f"Weight updated to {_number(weight)} kg. {detail}",
    )


def _present_weight_change_recorded(args: list[object]) -> UIEvent:
    """Format the weight change recorded response."""
    if len(args) < 2:
        return _error("invalid_profile", "Weight update data is invalid.")
    return _message(
        "weight_change_recorded",
        f"Weight updated to {_number(args[0])} kg. The {_number(args[1])}% change "
        "is below the 1% rebalance threshold, so your current plan stays unchanged.",
    )


def _present_weight_plan_rebalanced(args: list[object]) -> UIEvent:
    """Format the weight plan rebalanced response."""
    if len(args) < 4:
        return _error("invalid_profile", "Weight rebalance data is invalid.")
    goal_label = {
        "lose": "weight-loss",
        "gain": "weight-gain",
        "maintain": "maintenance",
    }.get(str(args[3]), str(args[3]))
    return _message(
        "weight_plan_rebalanced",
        f"Weight updated to {_number(args[0])} kg, a {_number(args[1])}% change from "
        f"your previous measurement. I’m rebuilding your weekly {goal_label} plan "
        f"at {_number(args[2])} kcal per day.",
    )


def _present_target_weight_reached(args: list[object]) -> UIEvent:
    """Format the target weight reached response."""
    if len(args) < 2:
        return _error("invalid_profile", "Target-weight data is invalid.")
    return _message(
        "target_weight_reached",
        f"You reached your target weight at {_number(args[0])} kg. I’m rebuilding your weekly plan for maintenance at {_number(args[1])} kcal per day.",
    )


def _present_preferences_updated(args: list[object]) -> UIEvent:
    """Format the preferences updated response."""
    diet = str(args[0]) if args else "unknown"
    return _message("preferences_updated", f"Preferences updated. Your diet is {diet}.")


def _present_culinary_preferences_updated(args: list[object]) -> UIEvent:
    """Format the culinary preferences updated response."""
    preferences = str(args[0]).strip() if args else ""
    return _message(
        "culinary_preferences_updated",
        f"Culinary preferences updated: {preferences or 'none'}.",
    )


def _present_planning_failed(args: list[object]) -> UIEvent:
    """Format the planning failed response."""
    reason = str(args[-1]) if args else "unknown"
    return _error(
        "planning_failed",
        _PLANNING_FAILURES.get(reason, "Meal planning failed."),
        retryable=True,
    )


def _present_meal_status(args: list[object]) -> UIEvent:
    """Format the meal status response."""
    if len(args) < 2:
        return _error("invalid_meal_status", "Meal status data is invalid.")
    return _message(
        "meal_status_updated",
        f"{str(args[0]).replace('_', ' ').capitalize()} is now marked as {args[1]}.",
    )


def _present_meal_missing(args: list[object]) -> UIEvent:
    """Format the meal missing response."""
    if len(args) < 2:
        return _error("invalid_meal_status", "Meal lookup data is invalid.")
    return _message(
        "meal_status_missing",
        f"No planned meal was found for {str(args[-1]).replace('_', ' ')} on {args[0]}.",
    )


def _present_simple(functor: str, args: list[object]) -> UIEvent:
    """Format the simple response."""
    messages = {
        "planning_started": (
            "planning_started",
            "Great, I am now preparing your weekly meal plan and recipes.",
        ),
        "meal_tracking_started": (
            "meal_tracking_started",
            "Your weekly plan is ready.",
        ),
        "no_plan_found": ("no_plan_found", "No meal plan was found for this profile."),
        "meal_logged_rebalancing": (
            "meal_logged_rebalancing",
            (
                f"{_sentence_start(args[0])} was logged with {_number(args[1])} kcal. I’ll rebalance the rest of your day now."
                if len(args) >= 2
                else "Your meal was logged. I’ll rebalance the rest of your day now."
            ),
        ),
        "daily_recap": (
            "daily_recap",
            (
                f"Today's total is {_number(args[0])}/{_number(args[1])} kcal."
                if len(args) >= 2
                else "Today's recap is unavailable."
            ),
        ),
        "weekly_budget_exceeded": (
            "weekly_budget_exceeded",
            (
                f"Your weekly calorie budget has been exceeded at {_number(args[0])}/{_number(args[1])} kcal."
                if len(args) >= 2
                else "Weekly budget exceeded."
            ),
        ),
    }
    code, message = messages[functor]
    return _message(code, message)


def _present_error(functor: str, args: list[object]) -> UIEvent:
    """Format the error response."""
    descriptions = {
        "translation_failed": "I could not understand that request.",
        "rebalance_failed": "I could not rebalance the remaining meals.",
    }
    if functor == "translation_failed" and len(args) > 1:
        detail = str(args[1]).strip()
        if detail:
            return _error(functor, detail, retryable=True)
    return _error(functor, descriptions[functor], retryable=True)


def _present_session_closed(args: list[object]) -> UIEvent:
    """Format the session closed response."""
    text = str(args[-1]).strip() if args else "Session closed."
    return UIEvent(type="session_closed", message=text or "Session closed.", payload={})


EVENT_PRESENTERS: dict[str, Callable[[list[object]], UIEvent]] = {
    "ask": _present_ask,
    "plan_data": _present_plan_data,
    "rebalanced_plan_data": _present_rebalanced_plan_data,
    "table_data": _present_table_data,
    "meal_confirmation_request": _present_meal_confirmation,
    "profile_complete": _present_profile_complete,
    "welcome_back": _present_welcome,
    "profile_updated": _present_profile_updated,
    "weight_updated": _present_profile_updated,
    "weight_progress_updated": _present_weight_progress,
    "weight_change_recorded": _present_weight_change_recorded,
    "weight_plan_rebalanced": _present_weight_plan_rebalanced,
    "target_weight_reached": _present_target_weight_reached,
    "preferences_updated": _present_preferences_updated,
    "culinary_preferences_updated": _present_culinary_preferences_updated,
    "planning_failed": _present_planning_failed,
    "meal_status_updated": _present_meal_status,
    "meal_status_missing": _present_meal_missing,
    "session_closed": _present_session_closed,
}
for _functor in {
    "planning_started",
    "no_plan_found",
    "daily_recap",
    "weekly_budget_exceeded",
    "meal_tracking_started",
    "meal_logged_rebalancing",
}:
    EVENT_PRESENTERS[_functor] = lambda args, functor=_functor: _present_simple(
        functor, args
    )
for _functor in {
    "translation_failed",
    "rebalance_failed",
}:
    EVENT_PRESENTERS[_functor] = lambda args, functor=_functor: _present_error(
        functor, args
    )


def render_asl_response(body: str) -> UIEvent:
    """Deterministically translate one internal ASL response into the UI contract."""
    parsed = parse_asl_message(body)
    if parsed is None:
        return _error("invalid_agent_message", "An agent returned an invalid message.")
    functor, args = parsed
    if functor == "system_notification":
        return _error(
            "deprecated_system_notification",
            "An agent emitted a deprecated UI notification.",
        )
    presenter = EVENT_PRESENTERS.get(functor)
    if presenter is None:
        return _error("unmapped_functor", f"No UI presenter exists for '{functor}'.")
    return presenter(args)


class ConversationAwareLLMTool(LLMTool):
    """Inject the current SPADE-LLM conversation into terminal tools."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the instance."""
        super().__init__(*args, **kwargs)
        self._conversation_id: str | None = None

    def set_conversation_id(self, conversation_id: str) -> None:
        """Set the active conversation identifier."""
        self._conversation_id = conversation_id

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the LLM tool request."""
        kwargs["_conversation_id"] = self._conversation_id
        return await super().execute(**kwargs)


def _body_lines(body: str) -> list[str]:
    """Extract lines."""
    return body.replace("\\n", "\n").splitlines()


def _has_unbound_asl_variables(command: str) -> bool:
    """Detect bare AgentSpeak variables that should not be sent as ground commands."""
    without_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', command)
    return bool(
        re.search(
            r"(?:\(|,)\s*[A-Z_][A-Za-z0-9_]*\s*(?=,|\))",
            without_strings,
        )
    )


def _registered_routes(command: str) -> set[tuple[str, str]]:
    """Return the registered routes matching a command's functor and arity."""
    parsed = parse_asl_message(command)
    if parsed is None:
        raise ValueError("command is not valid ASL")
    if _has_unbound_asl_variables(command):
        raise ValueError("command contains unbound variables")

    functor, args = parsed
    routes: set[tuple[str, str]] = set()
    for signature in get_translation_signatures(functor):
        template = parse_asl_message(_as_text(signature.get("prolog_template")))
        if template is None or len(template[1]) != len(args):
            continue
        target = _as_text(signature.get("target_agent")).lower()
        performative = _as_text(signature.get("performative")).lower()
        if target in _SUPPORTED_AGENTS and performative in _SUPPORTED_PERFORMATIVES:
            routes.add((target, performative))

    if not routes:
        raise ValueError(f"no registered route for {functor}/{len(args)}")
    return routes


def _translated_command_response(
    username: str,
    target_agent: str,
    performative: str,
    command: str,
) -> str:
    """Build command response."""
    return (
        f"translated_user_command({_asl_string(username)}, {_asl_string(target_agent)}, "
        f"{_asl_string(performative)}, {_asl_string(command)})"
    )


def _translation_failed_response(
    username: str, message: str = "Non ho capito, puoi ripetere"
) -> str:
    """Build failed response."""
    return f"translation_failed({_asl_string(username)}, {_asl_string(message)})"


def _message_context(original_msg: spade.message.Message) -> tuple[str, str]:
    """Extract context."""
    username = _as_text(original_msg.get_metadata("username")).lower() or "unknown"
    raw_user_message = original_msg.body or ""
    for line in _body_lines(raw_user_message):
        if line.lower().startswith("username:"):
            parsed_username = line.split(":", 1)[1].strip().lower()
            if parsed_username:
                username = parsed_username
            break
    parsed = parse_asl_message(original_msg.body or "")
    if parsed is not None and parsed[0] == "translate_user_message":
        args = parsed[1]
        if len(args) > 0 and username == "unknown":
            username = _as_text(args[0]).lower() or "unknown"
        if len(args) > 1:
            raw_user_message = _as_text(args[1])
    return username, raw_user_message


def _gateway_control_command(
    target_agent: str, performative: str, command: str
) -> bool:
    """Validate control command."""
    parsed = parse_asl_message(command)
    return (
        target_agent == "gateway"
        and performative == "tell"
        and parsed is not None
        and parsed[0] == "session_closed"
    )


def _validated_route(
    target_agent: str, performative: str, command: str
) -> tuple[str, str]:
    """Validate route."""
    target = target_agent.lower().strip()
    perf = performative.lower().strip()
    if target not in _SUPPORTED_AGENTS or perf not in _SUPPORTED_PERFORMATIVES:
        raise ValueError(f"unsupported route {target}/{perf}")
    routes = _registered_routes(command)
    if (target, perf) in routes:
        return target, perf
    if len(routes) == 1:
        corrected_target, corrected_performative = next(iter(routes))
        logger.warning(
            "NLP route corrected by signature validation: command=%s %s/%s -> %s/%s",
            command,
            target,
            perf,
            corrected_target,
            corrected_performative,
        )
        return corrected_target, corrected_performative
    allowed = ", ".join(
        f"{agent}/{performative}" for agent, performative in sorted(routes)
    )
    raise ValueError(
        f"route {target}/{perf} does not match registered routes: {allowed}"
    )


NLP_SYSTEM_PROMPT = """
You are NLPAgent. Translate each user request into one registered ASL command for the
SPADE nutrition app. Do not answer conversationally or perform the requested task yourself.

Incoming requests have one of these forms:
- User request:
  username: <name>
  message: <user text>
- User reply:
  username: <name>
  question: <question shown to the user>
  answer: <user reply>

Available tools:
- search_message_templates: retrieve candidate message IDs from language examples.
- get_message: retrieve the authoritative route, signature, and schema for those candidates.
- submit_translation: validate and send the terminal result to Gateway.

Workflow:
1. Call `search_message_templates` once with the complete request, including question-answer
   context and every value that may fill an argument.
2. Call `get_message` once with all returned candidate IDs.
3. Select exactly one candidate whose authoritative description and schema match the intent.
   Search rank alone does not determine the choice.
4. Build the command only from that definition. Copy its route, functor, argument order, types,
   and allowed values. Use the provided username for `Username`; use user values rather than
   example values from a retrieved template.
5. End with exactly one `submit_translation` call and no final text response.

Rules:
- Treat `question` and `answer` as one request: the question disambiguates the reply, while the
  answer supplies the value.
- When both `question` and `answer` are present, select the command that answers the current
  question. Do not reinterpret that reply as a standalone update to an existing profile.
- A successful command must be ground and valid ASL. Quote and escape string arguments; never
  leave variables or placeholders.
- Submit `status="error"` with a concise English explanation when the request is incomplete,
  ambiguous, or unsupported.
- Use `status="ok"` only for a complete, schema-compliant registered command.
""".strip()


class NLPAgent(LLMAgent):
    """Hybrid language agent: LLM for NL-to-ASL and static ASL-to-UI translation."""

    class StaticTranslationBehaviour(CyclicBehaviour):
        """Render internal ASL responses without involving the language model."""

        async def run(self) -> None:
            """Execute one behaviour cycle."""
            message = await self.receive(timeout=1)
            if message is None:
                return
            event = render_asl_response((message.body or "").strip())
            response = spade.message.Message(to="gateway@localhost")
            response.set_metadata("performative", "tell")
            response.set_metadata("message_type", "ui_event")
            response.thread = message.thread
            response.body = event.to_json()
            await self.send(response)
            logger.info(
                "NLP static translation produced UI event: source=%s type=%s",
                message.get_metadata("source_agent") or "nlp",
                event.type,
            )

    def __init__(
        self, jid: str, password: str, provider: LLMProvider, **kwargs: object
    ):
        """Initialize the instance."""
        self._submitted_conversations: set[str] = set()
        provider_name = getattr(provider, "model", provider.__class__.__name__)
        logger.info("Initializing NLP Agent with provider=%s", provider_name)
        super().__init__(
            jid,
            password,
            provider,
            tools=self._build_tools(),
            system_prompt=NLP_SYSTEM_PROMPT,
            max_interactions_per_conversation=6,
            routing_function=self._route_ack_response,
            **kwargs,
        )

    def _build_tools(self) -> list[LLMTool]:
        """Build the tools exposed to the language model."""
        return [
            LLMTool(
                name="search_message_templates",
                description=(
                    "Search Qdrant only over natural-language templates. Returns distinct "
                    "message IDs ordered by semantic similarity."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The complete user message or question-answer context; do not omit quantities or meal-slot details.",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 5,
                            "description": "Number of distinct message IDs to return.",
                        },
                    },
                    "required": ["query"],
                },
                func=self._tool_search_message_templates,
            ),
            LLMTool(
                name="get_message",
                description=(
                    "Fetch authoritative definitions for candidate message IDs. "
                    "The returned metadata contains the description, AgentSpeak signature, "
                    "parameter schema, target agent, and SPADE message performative."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "message_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Message IDs returned by search_message_templates.",
                        }
                    },
                    "required": ["message_ids"],
                    "additionalProperties": False,
                },
                func=self._tool_get_message,
            ),
            ConversationAwareLLMTool(
                name="submit_translation",
                description=(
                    "Validate and send the final translation to Gateway. Every request must end with "
                    "exactly one successful call to this tool. Use error status when "
                    "the request cannot produce a complete command."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["ok", "error"],
                        },
                        "target_agent": {"type": "string"},
                        "performative": {"type": "string"},
                        "command": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["status"],
                },
                func=self._tool_submit_translation,
            ),
        ]

    async def _tool_search_message_templates(
        self, query: str, limit: int = 5
    ) -> list[str]:
        """Search NL-only template vectors and return distinct message IDs."""
        limit = max(1, min(10, int(limit or 5)))
        logger.info(
            "NLP tool search_message_templates called with query=%s limit=%s",
            query,
            limit,
        )
        results = search_message_templates(query, limit=limit)
        return results

    async def _tool_get_message(self, message_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch complete message definitions after vector candidate selection."""
        definitions = get_messages(message_ids)
        logger.info(
            "NLP tool get_message called with ids=%s results=%s",
            message_ids,
            [definition["id"] for definition in definitions],
        )
        return definitions

    def _conversation_username(
        self, conversation_id: str, fallback: str = "unknown"
    ) -> str:
        """Read the trusted username from the original Gateway message."""
        for item in reversed(self.context.get_conversation_history(conversation_id)):
            if item.get("role") != "user":
                continue
            for line in _body_lines(_as_text(item.get("content"))):
                if line.lower().startswith("username:"):
                    username = line.split(":", 1)[1].strip().lower()
                    if username:
                        return username
        return fallback

    async def _send_to_gateway(self, body: str, conversation_id: str) -> None:
        """Send to gateway."""
        message = spade.message.Message(to="gateway@localhost")
        message.set_metadata("performative", "tell")
        message.set_metadata("message_type", "llm")
        message.thread = conversation_id
        message.body = body
        await self.llm_behaviour.send(message)

    async def _send_for_static_translation(
        self, body: str, conversation_id: str
    ) -> None:
        """Deliver an ASL response to this agent's deterministic behaviour."""
        message = spade.message.Message(to=str(self.jid))
        message.set_metadata("performative", "request")
        message.set_metadata("message_type", "static_translation")
        message.set_metadata("source_agent", "nlp")
        message.thread = conversation_id
        message.body = body
        await self.llm_behaviour.send(message)

    async def _tool_submit_translation(
        self,
        status: str,
        target_agent: str = "",
        performative: str = "",
        command: str = "",
        message: str = "",
        _conversation_id: str | None = None,
    ) -> dict[str, bool]:
        """Validate the terminal result and deliver it directly to Gateway."""
        conversation_id = _as_text(_conversation_id)
        if not conversation_id:
            raise ValueError("missing conversation id")
        if conversation_id in self._submitted_conversations:
            return {"submitted": True, "duplicate": True}

        username = self._conversation_username(conversation_id)
        normalized_status = _as_text(status).lower()
        if normalized_status not in {"ok", "error"}:
            raise ValueError(f"unsupported status {status}")

        target = _as_text(target_agent).lower()
        perf = _as_text(performative).lower()
        command = _as_text(command)
        if normalized_status != "ok":
            detail = (
                _as_text(message)
                or "I did not understand that request. Please try again."
            )
            body = _translation_failed_response(username, detail)
        elif _gateway_control_command(target, perf, command):
            parsed = parse_asl_message(command)
            if parsed is None or len(parsed[1]) != 2:
                raise ValueError("session_closed requires username and message")
            body = (
                f"session_closed({_asl_string(username)}, "
                f"{_asl_string(_as_text(parsed[1][1]))})"
            )
        else:
            target, perf = _validated_route(target, perf, command)
            body = _translated_command_response(username, target, perf, command)

        if normalized_status == "ok" and not _gateway_control_command(
            target, perf, command
        ):
            await self._send_to_gateway(body, conversation_id)
        else:
            await self._send_for_static_translation(body, conversation_id)
        self._submitted_conversations.add(conversation_id)
        logger.info(
            "NLP submitted translation: conversation=%s user=%s status=%s target=%s performative=%s command=%s",
            conversation_id,
            username,
            normalized_status,
            target,
            perf,
            command,
        )
        return {"submitted": True, "duplicate": False}

    def _route_ack_response(
        self,
        original_msg: spade.message.Message,
        response: str,
        context: dict[str, Any],
    ) -> RoutingResponse:
        """Consume the final LLM reply after the terminal tool delivered the result."""
        conversation_id = _as_text(context.get("conversation_id"))
        if conversation_id in self._submitted_conversations:
            self._submitted_conversations.discard(conversation_id)
            logger.info(
                "NLP consumed final LLM reply after submit tool delivered: %s",
                conversation_id,
            )
            return RoutingResponse(recipients=[], transform=lambda _: "", metadata={})

        username, raw_user_message = _message_context(original_msg)
        logger.error(
            "NLP ended without submit_translation: conversation=%s user=%s raw=%s response=%s",
            conversation_id,
            username,
            raw_user_message,
            response,
        )
        return RoutingResponse(
            recipients=str(self.jid),
            transform=lambda _: _translation_failed_response(username),
            metadata={
                "performative": "request",
                "message_type": "static_translation",
                "source_agent": "nlp",
            },
        )

    async def setup(self):
        """Start the NLP agent."""
        await super().setup()
        logger.info("Starting NLP Agent...")
        static_template = Template()
        static_template.set_metadata("message_type", "static_translation")
        self.add_behaviour(self.StaticTranslationBehaviour(), static_template)
        init_qdrant()
        logger.info(
            "NLP Agent ready with LLM translation and static response translation behaviours."
        )
