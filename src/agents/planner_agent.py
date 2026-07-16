import os
import json
import agentspeak
import agentspeak.stdlib
import spade.behaviour
import spade.message
from spade_bdi.bdi import BDIAgent
from src.utils.logger import get_logger
from src.utils.bdi import (
    add_belief_fact,
    belief_dicts,
    belief_rows,
    group_rows_by_key,
    ground,
)
from src.utils.bdi_bridge import (
    add_achieve_bridge,
    add_tell_bridge,
    register_log_action,
)
from src.utils.csv_store import read_csv, write_csv
from src.utils.messaging import send_later, send_many_later
from src.utils.nutrition_calculations import (
    calculate_slot_macro_targets,
    check_macro_tolerance,
)
from src.utils.agent_format import (
    asl_string as _asl_string,
    int_value as _int,
    row_args as _row_args,
    text_value as _text,
)

_logger = get_logger("PlannerAgent")
actions = agentspeak.Actions(agentspeak.stdlib.actions)
register_log_action(actions, _logger)
_agent_ref: dict = {}
_DATA_DIR = os.path.join("src", "data", "planner")
_WEEK_PLAN_CSV = "week_plan.csv"
_WEEK_PLAN_TEMPLATE_CSV = "week_plan_template.csv"
_NUTRITION_RULES_CSV = "nutrition_rules.csv"
_WEEK_PLAN_FIELDNAMES = [
    "username",
    "day",
    "slot",
    "dish",
    "template",
    "ingredients",
    "instructions",
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
]
_WEEK_PLAN_TEMPLATE_FIELDNAMES = [
    "username",
    "day",
    "slot",
    "template",
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "category",
]
_PLANNED_RECIPE_ROW_SCHEMA = [
    ("username", _text),
    ("day", _text),
    ("slot", _text),
    ("dish", _text),
    ("template", _text),
    ("ingredients", _text),
    ("instructions", _text),
    ("calories", _int),
    ("protein_g", _int),
    ("carbs_g", _int),
    ("fat_g", _int),
]
_PLANNED_TEMPLATE_ROW_SCHEMA = [
    ("username", _text),
    ("day", _text),
    ("slot", _text),
    ("template", _text),
    ("calories", _int),
    ("protein_g", _int),
    ("carbs_g", _int),
    ("fat_g", _int),
    ("category", _text),
]
_NUTRITION_RULE_SCHEMA = [
    ("diet_type", _text),
    ("category", _text),
    ("meal_slots", _text),
    ("min_per_week", _int),
    ("max_per_week", _int),
]


def _ordered_belief_values(agent, name: str) -> tuple[str, ...]:
    """Read values ordered by their numeric index from the BDI belief base."""
    rows = sorted(belief_rows(agent, name, 2), key=lambda row: int(row[1]))
    return tuple(str(value) for value, _ in rows)


def _minimums_reachable_after(
    planner,
    username: str,
    index: int,
    day: str,
    slot: str,
    name: str,
    category: str,
    diet_type: str,
) -> bool:
    """Check whether a hypothetical assignment leaves enough compatible slots."""
    username = username.strip().lower()
    diet_type = diet_type.strip().lower()
    counts = {
        str(cat): int(count) for cat, count in belief_rows(planner, "category_count", 2)
    }
    rules = [
        (str(cat), str(slots).split("|"), int(minimum))
        for diet, cat, slots, minimum, _ in belief_rows(planner, "nutrition_rule", 5)
        if str(diet) == diet_type
    ]
    rule_slots = {
        (str(cat), str(rule_slot))
        for diet, cat, rule_slot, _, _ in belief_rows(planner, "nutrition_rule_slot", 5)
        if str(diet) == diet_type
    }
    if (category, slot) in rule_slots:
        counts[category] = counts.get(category, 0) + 1
    counts[slot] = counts.get(slot, 0) + 1

    used_by_day: dict[str, set[str]] = {}
    for row in belief_rows(planner, "template_assignment", 10):
        row_username, _, assigned_day, _, assigned_name, *_ = row
        if str(row_username).strip().lower() == username:
            used_by_day.setdefault(str(assigned_day), set()).add(str(assigned_name))
    used_by_day.setdefault(day, set()).add(name)

    remaining_positions = [
        (int(position), str(position_day), str(position_slot))
        for position, position_day, position_slot in belief_rows(
            planner, "plan_position", 3
        )
        if int(position) > index
    ]
    domains: dict[tuple[str, str], list[str]] = {}
    for row in belief_rows(planner, "template_domain_candidate", 8):
        row_username, candidate_slot, candidate_name, *_, candidate_category = row
        if str(row_username).strip().lower() == username:
            domains.setdefault(
                (str(candidate_slot), str(candidate_category)), []
            ).append(str(candidate_name))

    # Slot rules describe the fixed weekly skeleton (seven breakfasts, snacks,
    # etc.). Every plan position is always assigned, so only recipe-category
    # rules need domain-based reachability checks here.
    deficits_by_slots: dict[tuple[str, ...], dict[str, int]] = {}
    meal_slots = set(_ordered_belief_values(planner, "meal_slot_order"))
    for rule_category, allowed_slots, minimum in rules:
        if rule_category in meal_slots:
            continue
        deficit = max(0, minimum - counts.get(rule_category, 0))
        if deficit == 0:
            continue
        capacity = 0
        for _, position_day, position_slot in remaining_positions:
            if position_slot not in allowed_slots:
                continue
            candidate_names = domains.get((position_slot, rule_category), [])
            if any(
                candidate_name not in used_by_day.get(position_day, set())
                for candidate_name in candidate_names
            ):
                capacity += 1
        if capacity < deficit:
            return False
        slot_group = tuple(sorted(allowed_slots))
        deficits_by_slots.setdefault(slot_group, {})[rule_category] = deficit

    for allowed_slots, deficits in deficits_by_slots.items():
        useful_positions = 0
        for _, position_day, position_slot in remaining_positions:
            if position_slot not in allowed_slots:
                continue
            for rule_category in deficits:
                candidate_names = domains.get((position_slot, rule_category), [])
                if any(
                    candidate_name not in used_by_day.get(position_day, set())
                    for candidate_name in candidate_names
                ):
                    useful_positions += 1
                    break
        if useful_positions < sum(deficits.values()):
            return False
    return True


def _reachability_args(term, intention) -> tuple[str, int, str, str, str, str, str]:
    """Extract args."""
    return (
        _text(ground(term.args[0], intention.scope)).strip().lower(),
        _int(ground(term.args[1], intention.scope)),
        _text(ground(term.args[2], intention.scope)).strip().lower(),
        _text(ground(term.args[3], intention.scope)).strip().lower(),
        _text(ground(term.args[4], intention.scope)),
        _text(ground(term.args[5], intention.scope)).strip().lower(),
        _text(ground(term.args[6], intention.scope)).strip().lower(),
    )


@actions.add(".minimums_reachable_after", 7)
def _minimums_reachable_after_action(asl_agent, term, intention):
    """Check whether minimums are reachable after action."""
    planner = _agent_ref.get("instance")
    if planner and _minimums_reachable_after(
        planner, *_reachability_args(term, intention)
    ):
        yield


@actions.add(".minimums_unreachable_after", 7)
def _minimums_unreachable_after_action(asl_agent, term, intention):
    """Check whether minimums are unreachable after action."""
    planner = _agent_ref.get("instance")
    if planner and not _minimums_reachable_after(
        planner, *_reachability_args(term, intention)
    ):
        yield


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


@actions.add(".send_plan", 2)
def _send_plan(asl_agent, term, intention):
    """Send plan."""
    planner = _agent_ref.get("instance")
    if not planner:
        yield
        return
    username = str(ground(term.args[0], intention.scope))
    message_type = str(ground(term.args[1], intention.scope))
    if message_type not in {"weekly_plan", "current_plan"}:
        _logger.warning("Unsupported plan message type: %s", message_type)
        yield
        return
    rows_by_user = planner._plan_rows_from_beliefs()
    rows = rows_by_user.get(username.strip().lower(), [])
    if not rows:
        _logger.warning("No week plan found in beliefs for %s", username)
        send_later(
            planner,
            "gateway@localhost",
            "BDI",
            f"no_plan_found({_asl_string(username)})",
            "tell",
        )
        yield
        return
    scope = "weekly" if message_type == "weekly_plan" else "current"
    payload = json.dumps(rows, ensure_ascii=False)
    send_later(
        planner,
        "gateway@localhost",
        "BDI",
        f"plan_data({_asl_string(scope)}, {_asl_string(payload)})",
        "tell",
    )
    _logger.info("Plan sent to Gateway (user=%s, type=%s)", username, message_type)
    yield


@actions.add(".calculate_slot_macro_targets", 7)
def _calculate_slot_macro_targets(asl_agent, term, intention):
    """Return Protein, Carbs, and Fat targets to ASL without mutating beliefs."""
    try:
        result = calculate_slot_macro_targets(
            ground(term.args[0], intention.scope),
            ground(term.args[1], intention.scope),
            ground(term.args[2], intention.scope),
            ground(term.args[3], intention.scope),
        )
    except (TypeError, ValueError) as exc:
        _logger.warning("Could not calculate slot macro targets: %s", exc)
        return
    output = (
        result["protein_g"],
        result["carbs_g"],
        result["fat_g"],
    )
    if agentspeak.unify(
        tuple(term.args[4:7]), output, intention.scope, intention.stack
    ):
        yield


@actions.add(".scale_runtime_macro_targets", 8)
def _scale_runtime_macro_targets(asl_agent, term, intention):
    """Scale an existing slot's macros to a new runtime calorie target."""
    try:
        target_calories = float(ground(term.args[0], intention.scope))
        base_calories = float(ground(term.args[1], intention.scope))
        base_protein = float(ground(term.args[2], intention.scope))
        base_carbs = float(ground(term.args[3], intention.scope))
        base_fat = float(ground(term.args[4], intention.scope))
    except (TypeError, ValueError) as exc:
        _logger.warning("Could not scale runtime macro targets: %s", exc)
        return
    if base_calories <= 0:
        return
    ratio = max(0.0, target_calories) / base_calories
    output = (
        int(round(base_protein * ratio)),
        int(round(base_carbs * ratio)),
        int(round(base_fat * ratio)),
    )
    if agentspeak.unify(
        tuple(term.args[5:8]), output, intention.scope, intention.stack
    ):
        yield


@actions.add(".request_recipe", 8)
def _request_recipe(asl_agent, term, intention):
    """Request recipe."""
    planner = _agent_ref.get("instance")
    if not planner:
        yield
        return
    username = _text(ground(term.args[0], intention.scope)).strip().lower()
    day = _text(ground(term.args[1], intention.scope)).strip().lower()
    slot = _text(ground(term.args[2], intention.scope)).strip().lower()
    template = _text(ground(term.args[3], intention.scope))
    calories = _int(ground(term.args[4], intention.scope))
    protein = _int(ground(term.args[5], intention.scope))
    carbs = _int(ground(term.args[6], intention.scope))
    fat = _int(ground(term.args[7], intention.scope))
    body = (
        "prepare_plan_slot("
        f"{_asl_string(username)}, {_asl_string(day)}, {_asl_string(slot)}, {_asl_string(template)}, "
        f"{calories}, {protein}, {carbs}, {fat})"
    )
    msg = spade.message.Message(to="cook@localhost")
    msg.set_metadata("message_type", "llm")
    msg.set_metadata("performative", "request")
    msg.body = body

    class SendLLMBehaviour(spade.behaviour.OneShotBehaviour):
        async def run(self):
            """Execute one behaviour cycle."""
            await self.send(msg)
            _logger.debug(
                "Prepared recipe request sent to Cook: user=%s day=%s slot=%s",
                username,
                day,
                slot,
            )

    planner.add_behaviour(SendLLMBehaviour())
    _logger.info("Prepared recipe requested from Cook: %s", body)
    yield


@actions.add(".same_text", 2)
def _same_text(asl_agent, term, intention):
    """Compare two ASL values as normalized text."""
    left = _text(ground(term.args[0], intention.scope)).strip().lower()
    right = _text(ground(term.args[1], intention.scope)).strip().lower()
    if left == right:
        yield


@actions.add(".get_next_slot", 4)
def _get_next_slot(asl_agent, term, intention):
    """Return next slot."""
    planner = _agent_ref.get("instance")
    if not planner:
        return
    days = _ordered_belief_values(planner, "weekday_order")
    slots = _ordered_belief_values(planner, "meal_slot_order")
    day = _text(ground(term.args[0], intention.scope)).strip().lower()
    slot = _text(ground(term.args[1], intention.scope)).strip().lower()
    try:
        day_index = days.index(day)
        slot_index = slots.index(slot)
    except ValueError:
        return
    if slot_index < len(slots) - 1:
        next_day = day
        next_slot = slots[slot_index + 1]
    elif day_index < len(days) - 1:
        next_day = days[day_index + 1]
        next_slot = slots[0]
    else:
        return
    output = (
        agentspeak.Literal(next_day),
        agentspeak.Literal(next_slot),
    )
    if agentspeak.unify(
        tuple(term.args[2:4]), output, intention.scope, intention.stack
    ):
        yield


@actions.add(".send_plan_day_context", 2)
def _send_plan_day_context(asl_agent, term, intention):
    """Send plan day context."""
    planner = _agent_ref.get("instance")
    if not planner:
        yield
        return
    username = _text(ground(term.args[0], intention.scope)).strip().lower()
    day = _text(ground(term.args[1], intention.scope)).strip().lower()
    rows = planner._plan_rows_from_beliefs().get(username, [])
    day_recipes = [
        str(row.get("dish", ""))
        for row in rows
        if str(row.get("day", "")).strip().lower() == day and row.get("dish")
    ]
    payload = "|".join(day_recipes)
    _logger.info(
        "Sending day plan context to Cook: user=%s day=%s recipes=%d",
        username,
        day,
        len(day_recipes),
    )
    send_later(
        planner,
        "cook@localhost",
        "tell",
        (
            "plan_day_context("
            f"{_asl_string(username)}, {_asl_string(day)}, {_asl_string(payload)}, {_asl_string(payload)})"
        ),
    )
    yield


class PlannerAgent(BDIAgent):
    def __init__(self, jid: str, password: str, asl: str, data_dir: str = _DATA_DIR):
        """Initialize the instance."""
        super().__init__(jid, password, asl, actions=actions)
        self._data_dir = data_dir

    def _get_path(self, filename: str) -> str:
        """Return path."""
        return os.path.join(self._data_dir, filename)

    async def setup(self):
        """Initialize the agent and its behaviours."""
        _logger.info("Starting Planner Agent...")
        week_rows, template_rows, nutrition_rules = self._load_week_history()
        await super().setup()
        self._inject_plan_positions()
        self._inject_week_plan_beliefs(week_rows, template_rows)
        self._inject_nutrition_rule_beliefs(nutrition_rules)
        self._send_plan_beliefs_to_nutritionist(week_rows)
        _agent_ref["instance"] = self
        add_achieve_bridge(self, _logger)
        add_tell_bridge(self, _logger)
        _logger.info("Planner Agent ready.")

    def _load_week_history(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Load week history."""
        week_rows = read_csv(self._get_path(_WEEK_PLAN_CSV))
        template_rows = read_csv(self._get_path(_WEEK_PLAN_TEMPLATE_CSV))
        nutrition_rules = read_csv(self._get_path(_NUTRITION_RULES_CSV))
        _logger.info(
            "Loaded planner history: recipes=%d templates=%d nutrition_rules=%d",
            len(week_rows),
            len(template_rows),
            len(nutrition_rules),
        )
        return week_rows, template_rows, nutrition_rules

    def _inject_plan_positions(self) -> None:
        """Derive plan positions from ordered BDI beliefs."""
        days = _ordered_belief_values(self, "weekday_order")
        slots = _ordered_belief_values(self, "meal_slot_order")
        index = 0
        for day in days:
            for slot in slots:
                add_belief_fact(self, "plan_position", index, day, slot)
                index += 1
        _logger.info("Injected %d ordered weekly plan positions", index)

    def _inject_week_plan_beliefs(
        self, week_rows: list[dict], template_rows: list[dict]
    ) -> None:
        """Inject week plan beliefs."""
        for row in week_rows:
            add_belief_fact(
                self, "planned_recipe_row", *_row_args(row, _PLANNED_RECIPE_ROW_SCHEMA)
            )
        for row in template_rows:
            add_belief_fact(
                self,
                "planned_template_row",
                *_row_args(row, _PLANNED_TEMPLATE_ROW_SCHEMA),
            )
        _logger.info(
            "Injected persisted Planner beliefs: recipes=%d templates=%d",
            len(week_rows),
            len(template_rows),
        )

    def _inject_nutrition_rule_beliefs(self, nutrition_rules: list[dict]) -> None:
        """Inject nutrition rule beliefs."""
        for row in nutrition_rules:
            add_belief_fact(
                self, "nutrition_rule", *_row_args(row, _NUTRITION_RULE_SCHEMA)
            )
            for slot in str(row.get("meal_slots") or "").split("|"):
                normalized_slot = slot.strip().lower()
                if normalized_slot:
                    add_belief_fact(
                        self,
                        "nutrition_rule_slot",
                        _text(row.get("diet_type")),
                        _text(row.get("category")),
                        normalized_slot,
                        _int(row.get("min_per_week")),
                        _int(row.get("max_per_week")),
                    )
        _logger.info(
            "Injected %d nutrition rules and their slot expansions into Planner beliefs",
            len(nutrition_rules),
        )

    def _send_plan_beliefs_to_nutritionist(self, week_rows: list[dict]) -> None:
        """Send plan beliefs to nutritionist."""
        bodies: list[str] = []
        for row in week_rows:
            recipe_args = [
                _asl_string(row.get("username")),
                _asl_string(str(row.get("day") or "").strip().lower()),
                _asl_string(str(row.get("slot") or "").strip().lower()),
                _asl_string(row.get("dish")),
                _asl_string(row.get("template")),
                _asl_string(row.get("ingredients")),
                _asl_string(row.get("instructions")),
                row.get("calories", ""),
                row.get("protein_g", ""),
                row.get("carbs_g", ""),
                row.get("fat_g", ""),
            ]
            bodies.append(f"planned_recipe_row({', '.join(map(str, recipe_args))})")
        send_many_later(
            self,
            "nutritionist@localhost",
            "tell",
            bodies,
        )
        if week_rows:
            _logger.info(
                "Sent %d persisted plan rows to Nutritionist as one ordered batch",
                len(week_rows),
            )

    def _plan_rows_from_beliefs(self) -> dict[str, list[dict]]:
        """Handle plan rows from beliefs."""
        rows = belief_dicts(self, "planned_recipe_row", _WEEK_PLAN_FIELDNAMES)
        return group_rows_by_key(rows, "username")

    def _template_rows_from_beliefs(self) -> list[dict]:
        """Handle template rows from beliefs."""
        return belief_dicts(
            self, "planned_template_row", _WEEK_PLAN_TEMPLATE_FIELDNAMES
        )

    def flush_state(self) -> None:
        """Persist state."""
        rows_by_user = self._plan_rows_from_beliefs()
        rows = [row for user_rows in rows_by_user.values() for row in user_rows]
        template_rows = self._template_rows_from_beliefs()
        write_csv(self._get_path(_WEEK_PLAN_CSV), _WEEK_PLAN_FIELDNAMES, rows)
        write_csv(
            self._get_path(_WEEK_PLAN_TEMPLATE_CSV),
            _WEEK_PLAN_TEMPLATE_FIELDNAMES,
            template_rows,
        )
        _logger.info(
            "Flushed Planner state: recipes=%d templates=%d",
            len(rows),
            len(template_rows),
        )

    async def stop(self):
        """Stop the agent and persist its state."""
        self.flush_state()
        await super().stop()
