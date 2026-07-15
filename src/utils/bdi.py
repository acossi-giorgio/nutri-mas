import agentspeak


def ground(term_arg, scope):
    """Ground an AgentSpeak term into a Python value."""
    val = agentspeak.grounded(term_arg, scope)
    return val.functor if hasattr(val, "functor") else val


def add_belief_fact(agent, name: str, *args) -> None:
    """Add a BDI fact unless an identical belief already exists."""
    new_args = tuple(agentspeak.Literal(x) if isinstance(x, str) else x for x in args)
    source_self = agentspeak.Literal("source", (agentspeak.Literal("self"),))
    term = agentspeak.Literal(name, new_args, (source_self,))
    for belief in list(agent.bdi_agent.beliefs[term.literal_group()]):
        if agentspeak.unifies(term, belief):
            return
    agent.bdi_intention_buffer.append(
        (
            agentspeak.Trigger.addition,
            agentspeak.GoalType.belief,
            term,
            agentspeak.runtime.Intention(),
        )
    )


def belief_value(value):
    """Convert an AgentSpeak value into a serializable value."""
    return value.functor if hasattr(value, "functor") else value


def belief_rows(agent, name: str, arity: int) -> list[tuple]:
    """Read beliefs with the requested name and arity."""
    beliefs = getattr(agent.bdi_agent, "beliefs", {})
    return [
        tuple(belief_value(arg) for arg in belief.args)
        for belief in list(beliefs.get((name, arity), []))
    ]


def belief_dicts(agent, name: str, fieldnames: list[str]) -> list[dict]:
    """Convert positional beliefs into dictionary rows."""
    return [
        dict(zip(fieldnames, row)) for row in belief_rows(agent, name, len(fieldnames))
    ]


def group_rows_by_key(rows: list[dict], key: str) -> dict[str, list[dict]]:
    """Group rows by a normalized key."""
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]).strip().lower(), []).append(row)
    return grouped
