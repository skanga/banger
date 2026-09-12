"""Static HTML attribute matching for CSS selectors without escape syntax."""

import re

ATTRIBUTE = re.compile(r"""\[(?:[^\]"'\\]|"[^"\\]*"|'[^'\\]*')*\]""")
ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
SELECTOR = re.compile(
    r"""\[\s*([\w-]+)\s*(?:([~|^$*]?=)\s*(?:"([^"]*)"|'([^']*)'|([-\w]+))\s*([iIsS])?\s*)?\]"""
)


def attribute_matches(selector, attributes):
    match = SELECTOR.fullmatch(selector)
    if not match:
        raise ValueError("Unsupported attribute selector: " + selector)
    name, operator, double, single, unquoted, flag = match.groups()
    name = name.translate(ASCII_LOWER)
    if name not in attributes:
        return False
    if operator is None:
        return True
    expected = next(value for value in (double, single, unquoted) if value is not None)
    actual = attributes[name] or ""
    if flag and flag.lower() == "i":
        actual, expected = actual.translate(ASCII_LOWER), expected.translate(ASCII_LOWER)
    if operator == "=":
        return actual == expected
    if operator == "|=":
        return actual == expected or actual.startswith(expected + "-")
    if not expected:
        return False
    if operator == "~=":
        return expected in re.split(r"[ \t\n\r\f]+", actual)
    if operator == "^=":
        return actual.startswith(expected)
    if operator == "$=":
        return actual.endswith(expected)
    return expected in actual
