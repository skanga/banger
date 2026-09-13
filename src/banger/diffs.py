"""Unified edit diffs using physical lines, preserving original line endings."""

import difflib
import re


def file_diff(path, before, after):
    def lines(data):
        content = (data or b"").decode("utf-8", errors="replace")
        return re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", content)

    return "".join(
        difflib.unified_diff(lines(before), lines(after), fromfile=str(path), tofile=str(path))
    )
