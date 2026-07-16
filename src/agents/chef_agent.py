import os
import random
from spade_bdi.bdi import BDIAgent
from src.utils.logger import get_logger
from src.utils.bdi import add_belief_fact
from src.utils.bdi_bridge import add_achieve_bridge, register_log_action
from src.utils.csv_store import read_csv
from src.utils.agent_format import (
    int_value as _int,
    row_args as _row_args,
    text_value as _text,
)
from src.utils.bdi import ground
from src.utils.nutrition_calculations import check_macro_tolerance
import agentspeak
import agentspeak.stdlib

logger = get_logger("ChefAgent")
_CSV_PATH = os.path.join("src", "data", "chef", "templates.csv")
_RANDOM = random.SystemRandom()
_TEMPLATE_FOR_PLAN_SCHEMA = [
    ("name", _text),
    ("calories", _int),
    ("protein_g", _int),
    ("carbs_g", _int),
    ("fat_g", _int),
    ("slot", _text),
    ("category", _text),
]
actions = agentspeak.Actions(agentspeak.stdlib.actions)
register_log_action(actions, logger)


@actions.add(".check_macro_tolerance", 10)
def _check_macro_tolerance(asl_agent, term, intention):
    """Check macro tolerance."""
    try:
        if check_macro_tolerance(
            int(ground(term.args[0], intention.scope)),
            int(ground(term.args[1], intention.scope)),
            int(ground(term.args[2], intention.scope)),
            int(ground(term.args[3], intention.scope)),
            float(ground(term.args[4], intention.scope)),
            float(ground(term.args[5], intention.scope)),
            float(ground(term.args[6], intention.scope)),
            float(ground(term.args[7], intention.scope)),
            float(ground(term.args[8], intention.scope)),
            float(ground(term.args[9], intention.scope)),
        ):
            yield
    except (TypeError, ValueError):
        pass


@actions.add(".random_candidate", 2)
def _random_candidate(asl_agent, term, intention):
    """Select candidate."""
    logger.debug("Selecting random candidate from %s", term.args[0])
    candidates = agentspeak.grounded(term.args[0], intention.scope)
    if not candidates:
        logger.warning("No candidates found for %s", term.args[0])
        return
    selected = _RANDOM.choice(candidates)
    logger.debug("Selected random candidate %s", selected)
    if agentspeak.unify(term.args[1], selected, intention.scope, intention.stack):
        yield


class ChefAgent(BDIAgent):
    def __init__(self, jid: str, password: str, asl: str):
        """Initialize the instance."""
        super().__init__(jid, password, asl, actions=actions)

    async def setup(self):
        """Initialize the agent and its behaviours."""
        logger.info("Starting Chef Agent...")
        await super().setup()
        self._load_template_beliefs()
        add_achieve_bridge(self, logger)
        logger.info("Chef Agent ready.")

    def _load_template_beliefs(self) -> None:
        """Load CSV templates directly into the BDI belief base."""
        rows = read_csv(_CSV_PATH, encoding="utf-8-sig")
        for row in rows:
            add_belief_fact(
                self, "template_for_plan", *_row_args(row, _TEMPLATE_FOR_PLAN_SCHEMA)
            )
        logger.info("Loaded %d recipe templates into Chef BDI beliefs", len(rows))

    def flush_state(self) -> None:
        """Persist state."""
        return

    async def stop(self):
        """Stop the agent and persist its state."""
        self.flush_state()
        await super().stop()
