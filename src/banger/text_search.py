"""Bounded line search over the workspace's discoverable UTF-8 files."""

import re

from banger.discovery import discover_files


def literal_span(line, needle, case_sensitive):
    searched = line if case_sensitive else line.casefold()
    start = searched.find(needle)
    if start < 0:
        return None
    end = start + len(needle)
    if case_sensitive:
        return start, end
    # Case folding can expand characters (for example ß -> ss). Return source
    # character offsets rather than offsets into the folded search buffer.
    folded_offset = 0
    source_start = None
    for index, character in enumerate(line):
        folded_end = folded_offset + len(character.casefold())
        if source_start is None and folded_end > start:
            source_start = index
        if folded_end >= end:
            return source_start, index + 1
        folded_offset = folded_end
    return None


def search_text(root, selected, query, case_sensitive, max_results, regex=False):
    if not query or len(query) > 1000 or "\n" in query or "\r" in query:
        raise ValueError("Use a nonempty single-line literal of at most 1000 characters")
    if not 1 <= max_results <= 200:
        raise ValueError("max_results must be between 1 and 200")
    if not selected.is_relative_to(root):
        raise ValueError("Text search is limited to the selected workspace")
    if not selected.exists():
        raise ValueError("Search path does not exist")
    result = {"matches": [], "skipped": [], "skipped_count": 0, "truncated": False}
    needle = query if case_sensitive else query.casefold()
    pattern = re.compile(query, 0 if case_sensitive else re.IGNORECASE) if regex else None
    budget = 32 * 1024 * 1024

    def skip(path, reason):
        result["skipped_count"] += 1
        if len(result["skipped"]) < 200:
            result["skipped"].append({"path": path, "reason": reason})

    for number, path in enumerate(discover_files(root)):
        if number >= 10_000 or budget <= 0:
            result["truncated"] = True
            break
        if path != selected and not path.is_relative_to(selected):
            continue
        relative = path.relative_to(root).as_posix()
        try:
            with path.open("rb") as source:
                data = source.read(min(2 * 1024 * 1024 + 1, budget + 1))
            budget -= len(data)
            if len(data) > 2 * 1024 * 1024 or budget < 0:
                skip(relative, "file or search byte limit")
                continue
            if b"\0" in data:
                skip(relative, "binary or non-UTF-8")
                continue
            content = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            skip(relative, "binary or non-UTF-8")
            continue
        except OSError:
            skip(relative, "unreadable or changed during search")
            continue
        lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if lines[-1] == "":
            lines.pop()
        for line_number, line in enumerate(lines, 1):
            if pattern:
                matched = pattern.search(line)
                span = matched.span() if matched else None
            else:
                span = literal_span(line, needle, case_sensitive)
            if span is None:
                continue
            if len(result["matches"]) == max_results:
                result["truncated"] = True
                return result
            start, end = span
            preview_start = min(max(0, start - 200), max(0, len(line) - 2000))
            result["matches"].append(
                {
                    "path": relative,
                    "line": line_number,
                    "column": start + 1,
                    "end_column": end + 1,
                    "preview_start_column": preview_start + 1,
                    "text": line[preview_start : preview_start + 2000],
                    "text_truncated": len(line) > 2000,
                }
            )
    return result
