from collections.abc import Callable
import logging
import agentspeak
from spade.behaviour import CyclicBehaviour
from spade.template import Template
from src.utils.asl_message import parse_asl_message
from src.utils.bdi import add_belief_fact, ground

BeforeDispatch = Callable[[object, list], None]
APPEND_BELIEF_FUNCTORS = {
    "planned_recipe_row",
}


class BDIBridge(CyclicBehaviour):
    def __init__(
        self,
        label: str,
        logger: logging.Logger,
        before_dispatch: BeforeDispatch | None = None,
    ):
        """Initialize the instance."""
        super().__init__()
        self.label = label
        self.logger = logger
        self.before_dispatch = before_dispatch

    async def run(self):
        """Execute one behaviour cycle."""
        msg = await self.receive(timeout=1)
        if msg is None:
            return
        body = (msg.body or "").strip()
        parsed = parse_asl_message(body)
        if parsed is None:
            self.logger.warning("%s: unparseable message: %s", self.label, body)
            return
        functor, args = parsed
        if self.before_dispatch is not None:
            self.before_dispatch(self.agent, args)
        self.dispatch(functor, args, msg)

    def dispatch(self, functor: str, args: list, msg) -> None:
        """Handle dispatch."""
        raise NotImplementedError


class TellBridge(BDIBridge):
    """Convert an application-level ``tell`` message into a BDI belief event."""

    def dispatch(self, functor: str, args: list, msg) -> None:
        """Handle dispatch."""
        if functor in APPEND_BELIEF_FUNCTORS:
            add_belief_fact(self.agent, functor, *args)
        else:
            self.agent.bdi.set_belief(functor, *args)
        self.logger.debug("%s -> BDI belief: %s%s", self.label, functor, args)


class AchieveBridge(BDIBridge):
    """Convert an application-level ``achieve`` message into a BDI goal event."""

    def dispatch(self, functor: str, args: list, msg) -> None:
        """Handle dispatch."""
        source = agentspeak.Literal("source", (agentspeak.Literal(str(msg.sender)),))
        goal = agentspeak.Literal(functor, tuple(args)).with_annotation(source)
        self.agent.bdi_intention_buffer.append(
            (
                agentspeak.Trigger.addition,
                agentspeak.GoalType.achievement,
                goal,
                agentspeak.runtime.Intention(),
            )
        )
        self.logger.debug("%s -> BDI goal: %s%s", self.label, functor, args)


def _add_bridge(
    agent,
    performative: str,
    bridge: BDIBridge,
) -> None:
    """Attach a message bridge to an agent."""
    template = Template()
    template.set_metadata("performative", performative)
    agent.add_behaviour(bridge, template)


def add_tell_bridge(
    agent,
    logger: logging.Logger,
    before_dispatch: BeforeDispatch | None = None,
) -> None:
    """Attach the tell-message bridge."""
    _add_bridge(agent, "tell", TellBridge("TellBridge", logger, before_dispatch))


def add_achieve_bridge(
    agent,
    logger: logging.Logger,
    before_dispatch: BeforeDispatch | None = None,
) -> None:
    """Attach the achievement-message bridge."""
    _add_bridge(
        agent,
        "achieve",
        AchieveBridge("AchieveBridge", logger, before_dispatch),
    )


def register_log_action(actions: agentspeak.Actions, logger: logging.Logger) -> None:
    """Register the AgentSpeak logging action."""
    @actions.add(".log", 1)
    def _log(asl_agent, term, intention):
        """Write an AgentSpeak log message."""
        msg = ground(term.args[0], intention.scope)
        logger.info("%s", msg)
        yield
