from __future__ import annotations

import asyncio
import json
from queue import Empty, Queue
from collections.abc import Callable

import spade.message
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour

from src.ui.events import EventValidationError, UICommand, UIEvent
from src.utils.asl_message import parse_asl_message
from src.utils.logger import get_logger

logger = get_logger("GatewayAgent")

_SUPPORTED_SENDERS = {"nutritionist", "planner", "chef", "cook", "nlp"}
_NLP_RECIPIENTS = {"nutritionist", "planner", "chef", "cook"}
_NLP_PERFORMATIVES = {"tell", "achieve"}


def _sender_name(sender: object) -> str:
    """Normalize an XMPP sender JID to its local logical name."""
    return str(sender or "").split("/", 1)[0].split("@", 1)[0].lower()


def _recipient_jid(name: str) -> str:
    """Build the local JID for an agent."""
    return name if "@" in name else f"{name}@localhost"


def _asl_string(value: object) -> str:
    """Quote a value for AgentSpeak."""
    return json.dumps(str(value), ensure_ascii=True)


def _error(code: str, detail: str, *, retryable: bool = False) -> UIEvent:
    """Build a UI error event."""
    return UIEvent(
        type="error",
        message=detail,
        payload={"code": code, "detail": detail, "retryable": retryable},
    )


class GatewayAgent(Agent):
    """Route local single-user commands and internal SPADE messages."""

    def __init__(
        self,
        jid: str,
        password: str,
        command_queue: Queue[str],
        event_queue: Queue[str],
        session_close_handlers: dict[str, Callable[[], None]] | None = None,
        **kwargs: object,
    ) -> None:
        """Initialize the instance."""
        super().__init__(jid, password, **kwargs)
        self.command_queue = command_queue
        self.event_queue = event_queue
        self.session_close_handlers = (
            session_close_handlers if session_close_handlers is not None else {}
        )
        self.username = ""
        self._ui_active = False
        self._deferred_events: list[UIEvent] = []

    def emit(self, event: UIEvent) -> None:
        """Publish one validated event to Streamlit without crossing event loops."""
        if not self._ui_active:
            self._deferred_events.append(event)
            logger.debug(
                "Deferred UI event until initialization: type=%s code=%s",
                event.type,
                event.payload.get("code", ""),
            )
            return
        self.event_queue.put(event.to_json())
        logger.debug(
            "Queued UI event for Streamlit: type=%s code=%s",
            event.type,
            event.payload.get("code", ""),
        )

    def activate_ui(self) -> None:
        """Release events only after the configured user has been initialized."""
        self._ui_active = True
        for event in self._deferred_events:
            self.event_queue.put(event.to_json())
        self._deferred_events.clear()

    async def _send_message(self, message: spade.message.Message) -> None:

        """Send message."""
        class OutboundBehaviour(OneShotBehaviour):
            async def run(inner_self) -> None:
                """Execute one behaviour cycle."""
                await inner_self.send(message)

        behaviour = OutboundBehaviour()
        self.add_behaviour(behaviour)
        await behaviour.join()

    async def submit_init(self, username: str) -> None:
        """Initialize the configured user after all runtime services are ready."""
        self.username = username
        message = spade.message.Message(to=_recipient_jid("nutritionist"))
        message.set_metadata("performative", "tell")
        message.body = f"init({_asl_string(username)})"

        await self._send_message(message)

    async def notify_weekly_plan_displayed(self) -> None:
        """Tell the Nutritionist that the newly generated plan is visible."""
        if not self.username:
            return
        message = spade.message.Message(to=_recipient_jid("nutritionist"))
        message.set_metadata("performative", "tell")
        message.body = f"weekly_plan_displayed({_asl_string(self.username)})"
        await self._send_message(message)

    def flush_session(self) -> None:
        """Persist session."""
        for name, handler in self.session_close_handlers.items():
            try:
                handler()
            except Exception:
                logger.exception("State flush failed for %s", name)

    async def route_command(self, command: UICommand) -> None:
        """Handle route command."""
        if not self.username:
            self.emit(
                _error(
                    "runtime_not_ready",
                    "The configured user is not initialized.",
                    retryable=True,
                )
            )
            return
        message = spade.message.Message(to=_recipient_jid("nlp"))
        message.set_metadata("performative", "request")
        message.set_metadata("message_type", "llm")
        message.set_metadata("username", self.username)
        if command.question_context:
            message.set_metadata("question_context", command.question_context)
            message.body = f"username: {self.username}\nquestion: {command.question_context}\nanswer: {command.text}"
        else:
            message.body = f"username: {self.username}\nmessage: {command.text}"
        await self._send_message(message)

    async def route_nlp(self, body: str) -> None:
        """Validate and route a command produced by the NLP LLM behaviour."""
        parsed = parse_asl_message(body)
        if parsed is None:
            self.emit(
                _error(
                    "invalid_nlp_message",
                    "The NLP response is invalid.",
                    retryable=True,
                )
            )
            return
        functor, args = parsed
        if functor != "translated_user_command" or len(args) < 4:
            self.emit(
                _error(
                    "invalid_nlp_message",
                    "The NLP response uses an unsupported command.",
                )
            )
            return
        _, recipient, performative, command = (str(value).strip() for value in args[:4])
        recipient = recipient.lower()
        performative = performative.lower()
        if recipient not in _NLP_RECIPIENTS or performative not in _NLP_PERFORMATIVES:
            self.emit(
                _error(
                    "invalid_nlp_route",
                    "The NLP response selected an unsupported route.",
                )
            )
            return
        if parse_asl_message(command) is None:
            self.emit(
                _error("invalid_nlp_command", "The NLP response is not valid ASL.")
            )
            return
        message = spade.message.Message(to=_recipient_jid(recipient))
        message.set_metadata("performative", performative)
        message.body = command
        await self._send_message(message)

    async def present_agent_response(self, message: spade.message.Message) -> None:
        """Render deterministic agent output directly into the UI event queue."""
        from src.agents.nlp_agent import render_asl_response

        event = render_asl_response((message.body or "").strip())
        logger.debug(
            "Rendered internal response directly: source=%s type=%s",
            _sender_name(message.sender),
            event.type,
        )
        await self.publish_ui_event(event)

    async def publish_ui_event(self, event: UIEvent) -> None:
        """Publish an event and run the side effects tied to visible output."""
        if event.type == "session_closed":
            self.flush_session()
        self.emit(event)
        if event.type == "plan" and event.payload.get("scope") == "weekly":
            await self.notify_weekly_plan_displayed()

    async def route_ui_event(self, body: str) -> None:
        """Validate a rendered NLP event before publishing it to Streamlit."""
        try:
            event = UIEvent.from_json(body)
        except EventValidationError as exc:
            self.emit(_error("invalid_ui_event", str(exc), retryable=True))
            return
        await self.publish_ui_event(event)

    class LocalCommandBehaviour(CyclicBehaviour):
        async def run(self) -> None:
            """Execute one behaviour cycle."""
            try:
                raw = self.agent.command_queue.get_nowait()
            except Empty:
                await asyncio.sleep(0.05)
                return
            try:
                command = UICommand.from_json(raw)
            except EventValidationError as exc:
                self.agent.emit(_error("invalid_command", str(exc)))
                return
            await self.agent.route_command(command)

    class GatewayBehaviour(CyclicBehaviour):
        async def run(self) -> None:
            """Execute one behaviour cycle."""
            message = await self.receive(timeout=1)
            if message is None:
                return
            sender = _sender_name(message.sender)
            body = (message.body or "").strip()
            if sender == "nlp":
                if message.get_metadata("message_type") == "ui_event":
                    await self.agent.route_ui_event(body)
                else:
                    await self.agent.route_nlp(body)
                return
            if sender not in _SUPPORTED_SENDERS:
                logger.warning("Ignoring unsupported Gateway sender: %s", sender)
                return
            await self.agent.present_agent_response(message)

    async def setup(self) -> None:
        """Initialize the agent and its behaviours."""
        self.add_behaviour(self.GatewayBehaviour())
        self.add_behaviour(self.LocalCommandBehaviour())
        logger.info("Gateway agent ready.")
