"""Recognize unconditional CSS imports with unescaped local URLs."""

import re
from urllib.parse import unquote, urlsplit


def import_path(statement):
    match = re.fullmatch(
        r"""@import\s+(?:"([^"\\]*)"|'([^'\\]*)'|url\(\s*(?:"([^"\\]*)"|'([^'\\]*)'|([^'"\\()\s]+))\s*\))\s*(?:all\s*)?;\s*""",
        statement,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Conditional, layered or unsupported CSS import")
    url = urlsplit(next((value for value in match.groups() if value), ""))
    path = unquote(url.path)
    if url.scheme or url.netloc or not path or path.startswith("/") or "\\" in path:
        raise ValueError("CSS import requires an available relative local URL")
    return path
