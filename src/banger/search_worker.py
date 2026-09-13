"""Isolated worker for potentially expensive regular-expression searches."""

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from banger.text_search import search_text


def regex_search(root, selected, query, case_sensitive, max_results):
    request = json.dumps([str(root), str(selected), query, case_sensitive, max_results])
    options = (
        {"creationflags": subprocess.CREATE_NO_WINDOW}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with subprocess.Popen(
        [sys.executable, "-I", str(Path(__file__).resolve())],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        **options,
    ) as process:
        try:
            output, error = process.communicate(request, timeout=10)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.communicate()
            return {
                "error": "Regex search exceeded its 10-second time limit; simplify or narrow the query"
            }
        if process.returncode:
            raise RuntimeError("Regex worker failed: " + error[:500])
        return json.loads(output)


def main():
    if os.name == "nt":
        from banger.windows_job import WindowsJob

        job = WindowsJob()
        assert job.handle
    try:
        root, selected, query, case_sensitive, max_results = json.load(sys.stdin)
        result = search_text(
            Path(root), Path(selected), query, case_sensitive, max_results, regex=True
        )
    except (ValueError, OSError, RuntimeError, re.error) as exc:
        result = {"error": str(exc)}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
