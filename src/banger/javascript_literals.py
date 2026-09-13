"""Decode constant JavaScript strings without evaluating source expressions."""

import re

from banger.index import text


def string_value(node):
    if node is None or node.has_error or node.type not in {"string", "template_string"}:
        return None
    if any(child.type == "template_substitution" for child in node.named_children):
        return None
    source = text(node)[1:-1].replace("\r\n", "\n").replace("\r", "\n")
    result = []
    index = 0
    while index < len(source):
        char = source[index]
        index += 1
        if char != "\\":
            result.append(char)
            continue
        if index == len(source):
            return None
        char = source[index]
        index += 1
        if char in "\n\u2028\u2029":
            continue
        if char in "xu":
            pattern = r"[0-9a-fA-F]{2}" if char == "x" else r"(?:\{[0-9a-fA-F]+\}|[0-9a-fA-F]{4})"
            match = re.match(pattern, source[index:])
            if match is None:
                return None
            digits = match.group().strip("{}")
            # Avoid parsing arbitrarily large braced escape integers.
            digits = digits.lstrip("0") or "0"
            if len(digits) > 6 or int(digits, 16) > 0x10FFFF:
                return None
            result.append(chr(int(digits, 16)))
            index += match.end()
        elif char in "0123456789":
            # Legacy octal/non-octal decimal escapes depend on the source mode.
            if char != "0" or index < len(source) and source[index] in "0123456789":
                return None
            result.append("\0")
        else:
            result.append(
                {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}.get(char, char)
            )
    # ECMAScript stores UTF-16 code units; normalize paired surrogates for Python.
    return (
        "".join(result)
        .encode("utf-16-le", errors="surrogatepass")
        .decode("utf-16-le", errors="surrogatepass")
    )
