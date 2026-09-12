"""Map decoded Python string literals to physical source lines without execution."""

import ast
import io
import re
import tokenize

ESCAPE = re.compile(
    r"\\(?:\n|[\\'\"abfnrtv]|[0-7]{1,3}|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|N\{[^}]+\})"
)
OPENING = re.compile(r"(?i)([ru]*)(\"\"\"|'''|\"|')")


def literal_lines(source, node):
    segment = ast.get_source_segment(source, node)
    if segment is None:
        return None
    decoded, lines = [], []
    try:
        for token in tokenize.generate_tokens(io.StringIO("(" + segment + ")").readline):
            if token.type != tokenize.STRING:
                continue
            opening = OPENING.match(token.string)
            if not opening:
                return None
            prefix, quote = opening.groups()
            body = token.string[opening.end() : -len(quote)]
            line = node.lineno + token.start[0] - 1
            position = 0
            while position < len(body):
                escape = ESCAPE.match(body, position) if "r" not in prefix.lower() else None
                unit = escape.group() if escape else body[position]
                value = ast.literal_eval('"' + unit + '"') if escape else unit
                decoded.append(value)
                lines.extend([line] * len(value))
                line += unit.count("\n")
                position += len(unit)
    except (SyntaxError, ValueError, tokenize.TokenError, IndentationError):
        return None
    return lines if "".join(decoded) == node.value else None
