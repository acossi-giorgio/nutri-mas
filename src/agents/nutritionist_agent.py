import asyncio
import json
import os
import spade.message
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade_bdi.bdi import BDIAgent
from src.utils.logger import get_logger
from src.utils.bdi import (
    add_belief_fact,
    add_typed_belief_fact,
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
from src.utils.messaging import send_later
from src.utils.nutrition_calculations import (
    calculate_profile_targets,
    calculate_rebalance_slot_target,
    calculate_rebalance_target,
    calculate_weight_change_percent,
)
from src.utils.time_utils import current_datetime, weekday_name
from src.utils.agent_format import (
    asl_string as _asl_string,
    int_value as _int,
    row_args as _row_args,
    text_value as _text,
)
import agentspeak
import agentspeak.stdlib

_logger = get_logger("NutritionistAgent")
logger = _logger
actions = agentspeak.Actions(agentspeak.stdlib.actions)
register_log_action(actions, _logger)
_agent_ref: dict = {}
_DATA_DIR = os.path.join("src", "data", "nutritionist")
_USER_CSV = "user.csv"
_USER_FIELDNAMES = [
    "username",
    "height",
    "weight",
    "age",
    "sex",
    "activity",
    "daily_calories",
    "target_weight",
    "allergens",
    "goal",
    "diet_type",
    "culinary_preferences",
]
_MEAL_LOG_CSV = "meal_log.csv"
_WEIGHT_LOG_CSV = "weight_log.csv"
_PLANNED_RECIPE_FIELDNAMES = [
    "username",
    "weekday",
    "meal_type",
    "dish",
    "template",
    "ingredients",
    "instructions",
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
]
_MEAL_LOG_FIELDNAMES = [
    "username",
    "date",
    "weekday",
    "meal_type",
    "planned_recipe",
    "actual_recipe",
    "status",
    "planned_calories",
    "planned_protein_g",
    "planned_carbs_g",
    "planned_fat_g",
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "source",
    "forecasted_at",
    "confirmation_requested_at",
    "updated_at",
]
_WEIGHT_LOG_FIELDNAMES = ["username", "date", "weight"]
_USER_SCHEMA = [
    ("username", _text),
    ("height", float),
    ("weight", float),
    ("age", _int),
    ("sex", _text),
    ("activity", _text),
    ("daily_calories", _int),
    ("target_weight", float),
    ("allergens", _text),
    ("goal", _text),
    ("diet_type", _text),
    ("culinary_preferences", _text),
]
_MEAL_LOG_SCHEMA = [
    ("username", _text),
    ("date", _text),
    ("weekday", _text),
    ("meal_type", _text),
    ("planned_recipe", _text),
    ("actual_recipe", _text),
    ("status", _text),
    ("planned_calories", _int),
    ("planned_protein_g", _int),
    ("planned_carbs_g", _int),
    ("planned_fat_g", _int),
    ("calories", _int),
    ("protein_g", _int),
    ("carbs_g", _int),
    ("fat_g", _int),
    ("source", _text),
    ("forecasted_at", _text),
    ("confirmation_requested_at", _text),
    ("updated_at", _text),
]
_WEIGHT_SCHEMA = [("username", _text), ("date", _text), ("weight", float)]


def _meal_label(value: object) -> str:
    """Return the display label for a meal slot."""
    labels = {
        "breakfast": "breakfast",
        "morning_snack": "morning snack",
        "lunch": "lunch",
        "afternoon_snack": "afternoon snack",
        "dinner": "dinner",
        "logged": "meal",
    }
    text = str(value or "").strip().lower()
    return labels.get(text, text.replace("_", " ") or "meal")


@actions.add(".calculate_profile_targets", 8)
def _calculate_profile_targets(asl_agent, term, intention):
    """Return Daily, Goal, and TargetWeight to ASL without mutating beliefs."""
    try:
        result = calculate_profile_targets(
            ground(term.args[0], intention.scope),
            ground(term.args[1], intention.scope),
            ground(term.args[2], intention.scope),
            ground(term.args[3], intention.scope),
            ground(term.args[4], intention.scope),
        )
    except (TypeError, ValueError) as exc:
        logger.warning("Could not calculate profile targets: %s", exc)
        return
    output = (
        result["daily_calories"],
        agentspeak.Literal(result["goal"]),
        result["target_weight"],
    )
    if agentspeak.unify(
        tuple(term.args[5:8]), output, intention.scope, intention.stack
    ):
        yield


@actions.add(".calculate_profile_targets_for_goal", 8)
def _calculate_profile_targets_for_goal(asl_agent, term, intention):
    """Recalculate calories for a new weight while preserving the current goal."""
    try:
        result = calculate_profile_targets(
            ground(term.args[0], intention.scope),
            ground(term.args[1], intention.scope),
            ground(term.args[2], intention.scope),
            ground(term.args[3], intention.scope),
            ground(term.args[4], intention.scope),
            goal_override=ground(term.args[5], intention.scope),
        )
    except (TypeError, ValueError) as exc:
        logger.warning("Could not recalculate profile targets: %s", exc)
        return
    output = (result["daily_calories"], result["target_weight"])
    if agentspeak.unify(
        tuple(term.args[6:8]), output, intention.scope, intention.stack
    ):
        yield


@actions.add(".calculate_weight_change_percent", 3)
def _calculate_weight_change_percent(asl_agent, term, intention):
    """Expose the consecutive-weigh-in heuristic to the BDI plans."""
    try:
        change_percent = calculate_weight_change_percent(
            ground(term.args[0], intention.scope),
            ground(term.args[1], intention.scope),
        )
    except (TypeError, ValueError) as exc:
        logger.warning("Could not calculate weight change: %s", exc)
        return
    if agentspeak.unify(
        tuple(term.args[2:3]), (change_percent,), intention.scope, intention.stack
    ):
        yield


@actions.add(".calculate_rebalance_target", 4)
def _calculate_rebalance_target(asl_agent, term, intention):
    """Calculate rebalance target."""
    try:
        daily_budget = float(ground(term.args[0], intention.scope))
        eaten_today = float(ground(term.args[1], intention.scope))
        slot = str(ground(term.args[2], intention.scope)).strip()
        target_calories = calculate_rebalance_target(daily_budget, eaten_today, slot)
    except (TypeError, ValueError) as exc:
        logger.warning("Could not calculate rebalance target: %s", exc)
        return
    output = (target_calories,)
    if agentspeak.unify(
        tuple(term.args[3:4]), output, intention.scope, intention.stack
    ):
        yield


@actions.add(".calculate_rebalance_slot_target", 5)
def _calculate_rebalance_slot_target(asl_agent, term, intention):
    """Calculate rebalance slot target."""
    try:
        daily_budget = float(ground(term.args[0], intention.scope))
        eaten_today = float(ground(term.args[1], intention.scope))
        origin_slot = str(ground(term.args[2], intention.scope)).strip()
        target_slot = str(ground(term.args[3], intention.scope)).strip()
        target_calories = calculate_rebalance_slot_target(
            daily_budget, eaten_today, origin_slot, target_slot
        )
    except (TypeError, ValueError) as exc:
        logger.warning("Could not calculate rebalance slot target: %s", exc)
        return
    if agentspeak.unify(
        term.args[4], target_calories, intention.scope, intention.stack
    ):
        yield


@actions.add(".calculate_eaten_today_from_log", 3)
def _calculate_eaten_today_from_log(asl_agent, term, intention):
    """Calculate eaten today from log."""
    nutritionist = _agent_ref.get("instance")
    if not nutritionist:
        return
    username = str(ground(term.args[0], intention.scope)).strip().lower()
    date = str(ground(term.args[1], intention.scope)).strip()
    total = 0
    for row in nutritionist._meal_log_beliefs_by_user().get(username, []):
        if str(row.get("date", "")).strip() != date:
            continue
        status = str(row.get("status", "")).strip().lower()
        actual = str(row.get("actual_recipe", "")).strip()
        if status in {"confirmed", "modified"} or actual:
            total += nutritionist._as_int(row.get("calories"))
    if agentspeak.unify(term.args[2], total, intention.scope, intention.stack):
        yield


@actions.add(".send_meal_logs", 1)
def _send_meal_logs(asl_agent, term, intention):
    """Send meal logs."""
    nutritionist = _agent_ref.get("instance")
    if not nutritionist:
        yield
        return
    username = str(ground(term.args[0], intention.scope)).strip().lower()
    logs: list[dict] = []
    rows = nutritionist._meal_log_beliefs_by_user().get(username, [])
    for row in rows:
        if row.get("date") and row.get("meal_type"):
            planned = row.get("planned_recipe", "")
            actual = row.get("actual_recipe", "")
            display_name = actual or planned
            logs.append(
                {
                    "date": row["date"],
                    "weekday": row.get("weekday", ""),
                    "meal_type": row["meal_type"],
                    "planned_recipe": planned,
                    "actual_recipe": actual,
                    "status": row.get("status", ""),
                    "dish": display_name,
                    "calories": nutritionist._as_int(row.get("calories")),
                    "protein_g": nutritionist._as_int(row.get("protein_g")),
                    "carbs_g": nutritionist._as_int(row.get("carbs_g")),
                    "fat_g": nutritionist._as_int(row.get("fat_g")),
                }
            )
    payload = json.dumps(logs, ensure_ascii=False)
    send_later(
        nutritionist,
        "gateway@localhost",
        "BDI",
        f"table_data({_asl_string('meal_logs')}, {_asl_string(payload)})",
        "tell",
    )
    logger.info("Sent meal logs to Gateway: user=%s rows=%d", username, len(logs))
    yield


@actions.add(".send_daily_recap_from_meal_log", 1)
def _send_daily_recap_from_meal_log(asl_agent, term, intention):
    """Send daily recap from meal log."""
    nutritionist = _agent_ref.get("instance")
    if not nutritionist:
        yield
        return
    username = str(ground(term.args[0], intention.scope)).strip().lower()
    today = current_datetime().date().isoformat()
    rows = [
        row
        for row in nutritionist._meal_log_beliefs_by_user().get(username, [])
        if str(row.get("date", "")).strip() == today
    ]
    slot_rank = {
        str(slot): int(index)
        for slot, index in belief_rows(nutritionist, "meal_slot_order", 2)
    }
    rows.sort(
        key=lambda item: slot_rank.get(
            str(item.get("meal_type", "")).strip().lower(), 99
        )
    )
    eaten_statuses = {"confirmed", "modified"}
    eaten_rows = [
        row
        for row in rows
        if str(row.get("status", "")).strip().lower() in eaten_statuses
        or str(row.get("actual_recipe", "")).strip()
    ]
    forecast_rows = [
        row
        for row in rows
        if str(row.get("status", "")).strip().lower() == "forecasted"
        and row not in eaten_rows
    ]
    total_calories = sum(
        nutritionist._as_int(row.get("calories")) for row in eaten_rows
    )
    budget = 0
    for row in belief_dicts(nutritionist, "user_profile_row", _USER_FIELDNAMES):
        if str(row.get("username", "")).strip().lower() == username:
            budget = nutritionist._as_int(row.get("daily_calories"))
            break
    meal_parts = []
    for row in eaten_rows:
        slot = _meal_label(row.get("meal_type"))
        recipe = str(
            row.get("actual_recipe") or row.get("planned_recipe") or ""
        ).strip()
        status = str(row.get("status", "")).strip().lower()
        if not recipe:
            continue
        suffix = " (modificato)" if status == "modified" else ""
        meal_parts.append(f"{slot}: {recipe}{suffix}")
    if not meal_parts and forecast_rows:
        planned = []
        for row in forecast_rows:
            recipe = str(row.get("planned_recipe") or "").strip()
            if recipe:
                planned.append(f"{_meal_label(row.get('meal_type'))}: {recipe}")
        if planned:
            meal_parts.append(
                "nessun pasto confermato; previsti: " + "; ".join(planned)
            )
    meals_text = " | ".join(meal_parts)
    body = f"daily_recap({total_calories}, {budget}, {_asl_string(meals_text)})"
    send_later(nutritionist, "gateway@localhost", "BDI", body, "tell")
    logger.info(
        "Sent daily recap from meal_log: user=%s date=%s eaten=%d forecast=%d calories=%d",
        username,
        today,
        len(eaten_rows),
        len(forecast_rows),
        total_calories,
    )
    yield


@actions.add(".send_weight_logs", 1)
def _send_weight_logs(asl_agent, term, intention):
    """Synchronize weight history and send it to the Gateway."""
    nutritionist = _agent_ref.get("instance")
    if not nutritionist:
        yield
        return
    username = str(ground(term.args[0], intention.scope)).strip().lower()
    logs: list[dict] = []
    for row in belief_dicts(nutritionist, "weight_log_entry", _WEIGHT_LOG_FIELDNAMES):
        if str(row.get("username", "")).strip().lower() != username:
            continue
        if row.get("date") and row.get("weight"):
            logs.append({"date": row["date"], "weight": float(row["weight"])})
    payload = json.dumps(logs, ensure_ascii=False)
    send_later(
        nutritionist,
        "gateway@localhost",
        "BDI",
        f"table_data({_asl_string('weight_logs')}, {_asl_string(payload)})",
        "tell",
    )
    logger.info("Sent weight logs to Gateway: user=%s rows=%d", username, len(logs))
    yield


@actions.add(".send_user_nutrition_context", 1)
def _send_user_nutrition_context(asl_agent, term, intention):
    """Send Cook the read-only nutrition context for a user."""
    nutritionist = _agent_ref.get("instance")
    if not nutritionist:
        yield
        return
    username = str(ground(term.args[0], intention.scope)).strip().lower()
    rows = {
        str(row.get("username", "")).strip().lower(): row
        for row in belief_dicts(nutritionist, "user_profile_row", _USER_FIELDNAMES)
    }
    row = rows.get(username, {})
    if row:
        logger.info(
            "Sending nutrition context to Cook: user=%s diet=%s allergens=%s culinary_preferences=%s daily_calories=%s",
            username,
            row.get("diet_type", "omnivore"),
            row.get("allergens", ""),
            row.get("culinary_preferences", ""),
            row.get("daily_calories", 0) or 0,
        )
    else:
        logger.warning(
            "Nutrition context requested for unknown user=%s; sending defaults",
            username,
        )
    body = (
        "user_nutrition_context("
        f"{_asl_string(username)}, "
        f'{_asl_string(row.get("diet_type", "omnivore"))}, '
        f'{_asl_string(row.get("allergens", ""))}, '
        f'{row.get("daily_calories", 0) or 0}, '
        f'{_asl_string(row.get("goal", ""))}, '
        f'{_asl_string(row.get("meal_distribution", "balanced"))}, '
        f'{_asl_string(row.get("culinary_preferences", ""))})'
    )
    send_later(nutritionist, "cook@localhost", "tell", body)
    yield


@actions.add(".send_free_meal_to_cook", 5)
def _send_free_meal_to_cook(asl_agent, term, intention):
    """Send free meal to cook."""
    nutritionist = _agent_ref.get("instance")
    if not nutritionist:
        yield
        return
    username = str(ground(term.args[0], intention.scope)).strip().lower()
    date = str(ground(term.args[1], intention.scope)).strip()
    slot = str(ground(term.args[2], intention.scope)).strip().lower()
    name = str(ground(term.args[3], intention.scope)).strip()
    calories = str(ground(term.args[4], intention.scope)).strip() or "unknown"
    body = (
        "evaluate_free_meal("
        f"{_asl_string(username)}, "
        f"{_asl_string(date)}, "
        f"{_asl_string(slot)}, "
        f"{_asl_string(name)}, "
        f"{_asl_string(calories)})"
    )

    class SendFreeMealBehaviour(OneShotBehaviour):
        async def run(self):
            """Execute one behaviour cycle."""
            msg = spade.message.Message(to="cook@localhost")
            msg.set_metadata("performative", "request")
            msg.set_metadata("message_type", "llm")
            msg.body = body
            await self.send(msg)

    nutritionist.add_behaviour(SendFreeMealBehaviour())
    logger.info("Free meal evaluation requested from Cook: %s", body)
    yield


def _serialize_daily_plan_payload(
    nutritionist: "NutritionistAgent", username: str, target_date: str
) -> str:
    """Serialize the daily log, enriched with the Planner's recipe details."""
    rows = nutritionist._meal_log_beliefs_by_user().get(username, [])
    daily_rows = [r for r in rows if r.get("date") == target_date]
    slot_order = {
        "breakfast": 0,
        "morning_snack": 1,
        "lunch": 2,
        "afternoon_snack": 3,
        "dinner": 4,
    }
    daily_rows.sort(key=lambda x: slot_order.get(x.get("meal_type", ""), 99))
    weekday = (
        str(daily_rows[0].get("weekday", "")).strip().lower() if daily_rows else ""
    )
    recipe_details = {
        str(row.get("meal_type", "")).strip().lower(): row
        for row in nutritionist._planned_recipe_rows_for(username, weekday)
    }

    def serialize_row(row: dict) -> dict:
        """Serialize one daily-plan row."""
        slot = str(row.get("meal_type", "")).strip().lower()
        planned_dish = str(row.get("planned_recipe") or "").strip()
        displayed_dish = str(row.get("actual_recipe") or planned_dish).strip()
        details = recipe_details.get(slot, {})
        details_match = not row.get("actual_recipe") or (
            displayed_dish.casefold() == str(details.get("dish", "")).strip().casefold()
        )
        if not details_match:
            details = {}
        return {
            "day": str(row.get("weekday", "")).lower(),
            "slot": slot,
            "dish": displayed_dish,
            "template": str(details.get("template", "")),
            "ingredients": str(details.get("ingredients", "")),
            "instructions": str(details.get("instructions", "")),
            "calories": nutritionist._as_int(row.get("calories")),
            "protein_g": nutritionist._as_int(row.get("protein_g")),
            "carbs_g": nutritionist._as_int(row.get("carbs_g")),
            "fat_g": nutritionist._as_int(row.get("fat_g")),
            "status": str(row.get("status", "")),
        }

    return json.dumps(
        [serialize_row(row) for row in daily_rows],
        ensure_ascii=False,
    )


@actions.add(".send_daily_plan_payload", 3)
def _send_daily_plan_payload(asl_agent, term, intention):
    """Send a daily plan with the JSON payload quoted as one ASL argument."""
    nutritionist = _agent_ref.get("instance")
    if not nutritionist:
        yield
        return

    username = str(ground(term.args[0], intention.scope)).strip().lower()
    target_date = str(ground(term.args[1], intention.scope)).strip()
    mode = str(ground(term.args[2], intention.scope)).strip().lower()
    payload = _serialize_daily_plan_payload(nutritionist, username, target_date)

    if mode == "rebalanced":
        body = f"rebalanced_plan_data({_asl_string(payload)})"
    else:
        body = f"plan_data({_asl_string('daily')}, {_asl_string(payload)})"
    send_later(nutritionist, "gateway@localhost", "BDI", body, "tell")
    logger.info(
        "Sent daily plan to Gateway: user=%s date=%s mode=%s rows=%d",
        username,
        target_date,
        mode,
        len(json.loads(payload)),
    )
    yield


class MealMonitorBehaviour(CyclicBehaviour):
    """Periodic agentic trigger driven by the shared, simulatable clock."""

    async def run(self):
        """Generate periodic time ticks for forecasts and meal confirmations."""
        self.agent.run_meal_time_triggers()
        await asyncio.sleep(self.agent.meal_monitor_interval_seconds)


class NutritionistAgent(BDIAgent):
    """BDI agent for profiles, nutrition state, persistence, and clock events."""

    def __init__(
        self,
        jid: str,
        password: str,
        asl: str,
        *,
        meal_monitor_interval_seconds: float = 30.0,
        data_dir: str = _DATA_DIR,
    ):
        """Initialize the instance."""
        super().__init__(jid, password, asl, actions=actions)
        self._data_dir = data_dir
        self.meal_monitor_interval_seconds = float(meal_monitor_interval_seconds)

    def _get_path(self, filename: str) -> str:
        """Return path."""
        return os.path.join(self._data_dir, filename)

    async def setup(self):
        """Load persisted beliefs and register runtime bridges."""
        logger.info("Starting Nutritionist Agent...")
        user_rows, meal_rows, weight_rows = self._load_csv_state()
        await super().setup()
        self._inject_csv_beliefs(user_rows, meal_rows, weight_rows)
        _agent_ref["instance"] = self
        add_achieve_bridge(self, _logger)
        add_tell_bridge(self, _logger)
        self.add_behaviour(MealMonitorBehaviour())
        logger.info("Nutritionist Agent ready.")

    def _meal_log_beliefs_by_user(self) -> dict[str, list[dict]]:
        """Return the current meal log grouped by username."""
        return group_rows_by_key(
            belief_dicts(self, "meal_log_row", _MEAL_LOG_FIELDNAMES), "username"
        )

    def _belief_csv_state(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Extract the persistent tables from the belief base."""
        return (
            belief_dicts(self, "user_profile_row", _USER_FIELDNAMES),
            belief_dicts(self, "meal_log_row", _MEAL_LOG_FIELDNAMES),
            belief_dicts(self, "weight_log_entry", _WEIGHT_LOG_FIELDNAMES),
        )

    @staticmethod
    def _as_int(value: object) -> int:
        """Convert a value to an integer."""
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return 0

    def _planned_recipe_rows_for(self, username: str, weekday: str) -> list[dict]:
        """Return recipe rows for."""
        by_slot: dict[str, dict] = {}
        for row in belief_dicts(self, "planned_recipe_row", _PLANNED_RECIPE_FIELDNAMES):
            if str(row.get("username", "")).strip().lower() != username:
                continue
            if str(row.get("weekday", "")).strip().lower() != weekday:
                continue
            slot = str(row.get("meal_type", "")).strip().lower()
            if slot:
                by_slot[slot] = row
        return list(by_slot.values())

    def run_meal_time_triggers(self) -> None:
        """Publish only the shared clock tick; AgentSpeak owns reminder state."""
        now = current_datetime()
        entry_date = now.date().isoformat()
        weekday = weekday_name(now)
        now_minutes = now.hour * 60 + now.minute
        logger.debug(
            "Meal monitor tick: date=%s weekday=%s time=%02d:%02d minutes=%s",
            entry_date,
            weekday,
            now.hour,
            now.minute,
            now_minutes,
        )
        self.bdi.set_belief("current_date", entry_date)
        self.bdi.set_belief(
            "clock_tick", entry_date, weekday, now.hour, now.minute, now_minutes
        )

    def _inject_csv_beliefs(
        self, user_rows: list[dict], meal_rows: list[dict], weight_rows: list[dict]
    ) -> None:
        """Inject CSV rows and runtime configuration into the belief base."""
        today = current_datetime().date().isoformat()
        add_belief_fact(self, "current_date", today)
        injected = 0
        for rows, belief_name, schema in (
            (user_rows, "user_profile_row", _USER_SCHEMA),
            (meal_rows, "meal_log_row", _MEAL_LOG_SCHEMA),
            (weight_rows, "weight_log_entry", _WEIGHT_SCHEMA),
        ):
            for row in rows:
                args = _row_args(row, schema)
                if belief_name == "meal_log_row":
                    args = [
                        value
                        if index in {6, 17}
                        else agentspeak.Literal(value)
                        if isinstance(value, str)
                        else value
                        for index, value in enumerate(args)
                    ]
                    add_typed_belief_fact(self, belief_name, *args)
                else:
                    add_belief_fact(self, belief_name, *args)
                injected += 1
        logger.info(
            "Injected %d CSV rows into Nutritionist BDI beliefs",
            injected,
        )

    def _load_csv_state(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Load the persistent agent state from CSV files."""
        user_rows = read_csv(self._get_path(_USER_CSV))
        meal_rows = read_csv(self._get_path(_MEAL_LOG_CSV))
        weight_rows = read_csv(self._get_path(_WEIGHT_LOG_CSV))
        logger.info(
            "Loaded CSV state into memory: users=%d meals=%d weights=%d",
            len(user_rows),
            len(meal_rows),
            len(weight_rows),
        )
        return user_rows, meal_rows, weight_rows

    def flush_state(self) -> None:
        """Persist the authoritative Nutritionist beliefs to CSV."""
        user_rows, meal_rows, weight_rows = self._belief_csv_state()
        write_csv(self._get_path(_USER_CSV), _USER_FIELDNAMES, user_rows)
        write_csv(self._get_path(_MEAL_LOG_CSV), _MEAL_LOG_FIELDNAMES, meal_rows)
        write_csv(self._get_path(_WEIGHT_LOG_CSV), _WEIGHT_LOG_FIELDNAMES, weight_rows)

    async def stop(self):
        """Persist state before stopping the agent."""
        self.flush_state()
        await super().stop()
