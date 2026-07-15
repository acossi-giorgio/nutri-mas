import spade.behaviour
import spade.message
from src.utils.logger import get_logger

logger = get_logger("Messaging")


def send_later(
    agent, to: str, performative: str, body: str, ilf_type: str | None = None
) -> None:
    """Schedule asynchronous delivery of a SPADE message."""

    class SendBehaviour(spade.behaviour.OneShotBehaviour):
        async def run(self):
            """Execute one behaviour cycle."""
            msg = spade.message.Message(to=to)
            msg.set_metadata("performative", performative)
            if ilf_type:
                msg.set_metadata("ilf_type", ilf_type)
            msg.body = body
            logger.debug(
                "send_later: from=%s to=%s performative=%s ilf_type=%s body=%s",
                str(self.agent.jid).split("@", 1)[0],
                to,
                performative,
                ilf_type,
                body,
            )
            await self.send(msg)

    agent.add_behaviour(SendBehaviour())


def send_many_later(
    agent,
    to: str,
    performative: str,
    bodies: list[str],
    ilf_type: str | None = None,
) -> None:
    """Send an ordered batch from one behaviour so messages cannot overtake."""
    ordered_bodies = tuple(bodies)
    if not ordered_bodies:
        return

    class SendManyBehaviour(spade.behaviour.OneShotBehaviour):
        async def run(self):
            """Execute one behaviour cycle."""
            for body in ordered_bodies:
                msg = spade.message.Message(to=to)
                msg.set_metadata("performative", performative)
                if ilf_type:
                    msg.set_metadata("ilf_type", ilf_type)
                msg.body = body
                logger.debug(
                    "send_many_later: from=%s to=%s performative=%s ilf_type=%s body=%s",
                    str(self.agent.jid).split("@", 1)[0],
                    to,
                    performative,
                    ilf_type,
                    body,
                )
                await self.send(msg)

    agent.add_behaviour(SendManyBehaviour())
