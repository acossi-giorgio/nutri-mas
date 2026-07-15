import re
import ast
from typing import TypeAlias
import agentspeak
import spade.message
import spade_bdi.bdi

ASLArgument: TypeAlias = int | float | str
ParsedASLMessage: TypeAlias = tuple[str, list[ASLArgument]]


def parse_asl_message(body: str) -> ParsedASLMessage | None:
    """Parse a simple ASL body into a functor and arguments."""
    body = body.strip()
    if not body:
        return None
    match = re.match(r"^(\w+)\((.*)\)\s*$", body, re.DOTALL)
    if match:
        functor = match.group(1)
        args = split_args(match.group(2).strip())
        return functor, args
    if re.match(r"^\w+$", body):
        return body, []
    return None


def split_args(args_str: str) -> list[ASLArgument]:
    """Split arguments while respecting strings and nested parentheses."""
    args: list[ASLArgument] = []
    depth = 0
    in_string = False
    escaped = False
    buffer: list[str] = []
    for char in args_str:
        if in_string and char == "\\" and not escaped:
            escaped = True
            buffer.append(char)
            continue
        if char == '"' and not escaped:
            in_string = not in_string
            buffer.append(char)
        elif char == "(" and not in_string:
            depth += 1
            buffer.append(char)
        elif char == ")" and not in_string:
            depth -= 1
            buffer.append(char)
        elif char == "," and depth == 0 and not in_string:
            args.append(coerce("".join(buffer).strip()))
            buffer = []
        else:
            buffer.append(char)
        escaped = False
    tail = "".join(buffer).strip()
    if tail:
        args.append(coerce(tail))
    return args


def coerce(token: str) -> ASLArgument:
    """Convert an ASL token into an int, float, or string."""
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        try:
            return ast.literal_eval(token)
        except (SyntaxError, ValueError):
            return token[1:-1]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return agentspeak.Literal(token)


_orig_parse = spade_bdi.bdi.parse_literal
if not hasattr(spade.message.MessageBase, "metadata"):
    spade.message.MessageBase.metadata = property(lambda self: self._metadata)


def _safe_parse_literal(body: str) -> tuple[str, list]:
    """Parse BDI messages while preserving spade-bdi compatibility."""
    parsed = parse_asl_message(body)
    if parsed:
        return parsed
    return _orig_parse(body)


spade_bdi.bdi.parse_literal = _safe_parse_literal
