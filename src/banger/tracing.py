"""Run a Python file in a separate interpreter under a bounded call tracer."""

import json
import uuid
from pathlib import Path


async def trace_file(executor, path, args, python):
    output = executor.root / ".banger" / "traces" / (uuid.uuid4().hex + ".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    runner = Path(__file__).with_name("trace_runner.py")
    result = await executor.run_argv(
        [python, str(runner), str(executor.root), str(path), str(output), *args]
    )
    trace = (
        json.loads(output.read_text(encoding="utf-8"))
        if output.exists()
        else {"events": [], "incomplete": True, "reason": "Trace process did not save a result"}
    )
    return {"execution": result, "trace": trace}
