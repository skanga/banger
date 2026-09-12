"""Standalone tracer subprocess: no Banger installation needed in the target interpreter."""

import hashlib
import json
import os
import runpy
import sys
import threading
from pathlib import Path


def safe_value(value, depth=0):
    # Never invoke user-defined repr/str from within a trace hook.
    if type(value) in {str, int, float, bool, type(None)}:
        return value[:500] if type(value) is str else value
    if depth < 2 and type(value) in {list, tuple}:
        return [safe_value(v, depth + 1) for v in value[:10]]
    if depth < 2 and type(value) is dict:
        return {k: safe_value(v, depth + 1) for k, v in list(value.items())[:10] if type(k) is str}
    return {"type": type(value).__name__}


def main():
    root, target, output = map(Path, sys.argv[1:4])
    arguments = sys.argv[4:]
    root = root.resolve()
    events = []
    truncated = False
    cache = {}
    source_digests = {}
    next_id = 0
    frames = {}

    def location(frame):
        filename = frame.f_code.co_filename
        if filename not in cache:
            # Interpreter and exec/compile labels are not paths, even when
            # resolving them against cwd would place them inside the project.
            if filename.startswith("<") and filename.endswith(">"):
                cache[filename] = None
                return None
            path = Path(filename).resolve()
            cache[filename] = (
                path.relative_to(root).as_posix() if path.is_relative_to(root) else None
            )
            if cache[filename] and path.is_file():
                source_digests[cache[filename]] = hashlib.sha256(path.read_bytes()).hexdigest()
        return cache[filename]

    def trace(frame, event, arg):
        nonlocal truncated, next_id
        path = location(frame)
        if not path or path.startswith((".venv/", "venv/")):
            return None
        if event not in {"call", "return", "exception"}:
            return trace
        if len(events) >= 10000:
            truncated = True
            return None
        key = id(frame)
        if event == "call":
            next_id += 1
            frames[key] = next_id
        record = {
            "event": event,
            "path": path,
            "line": frame.f_lineno,
            "definition_line": frame.f_code.co_firstlineno,
            "function": frame.f_code.co_name,
            "frame": frames.get(key),
            "parent_frame": frames.get(id(frame.f_back)),
        }
        if event == "call":
            count = frame.f_code.co_argcount + frame.f_code.co_kwonlyargcount
            record["arguments"] = {
                name: safe_value(frame.f_locals.get(name))
                for name in frame.f_code.co_varnames[:count]
            }
        elif event == "return":
            record["value"] = safe_value(arg)
            frames.pop(key, None)
        else:
            record["exception"] = arg[0].__name__
        events.append(record)
        return trace

    sys.argv = [str(target), *arguments]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(target.parent))
    os.chdir(root)
    sys.settrace(trace)
    threading.settrace(trace)
    try:
        runpy.run_path(str(target), run_name="__main__")
    finally:
        sys.settrace(None)
        threading.settrace(None)
        output.write_text(
            json.dumps(
                {"events": events, "truncated": truncated, "source_digests": source_digests}
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
