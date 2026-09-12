import sys

from banger.execution import Executor
from banger.index import CodeIndex
from banger.state import StateStore
from banger.tracing import trace_file


async def test_real_python_trace_records_arguments_return_and_exception(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "def twice(value):\n return value * 2\n"
        "assert twice(3) == 6\n"
        "try:\n raise ValueError('example')\nexcept ValueError:\n pass\n"
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = result["trace"]["events"]
    assert any(
        e["event"] == "call" and e["function"] == "twice" and e["arguments"]["value"] == 3
        for e in events
    )
    assert any(
        e["event"] == "return" and e["function"] == "twice" and e["value"] == 6 for e in events
    )
    assert any(e["event"] == "exception" and e["exception"] == "ValueError" for e in events)


async def test_trace_excludes_synthetic_filenames(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "exec(compile('def dynamic(): return 7\\ndynamic()', '<generated>', 'exec'))\n"
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    assert result["trace"]["events"]
    assert {event["path"] for event in result["trace"]["events"]} == {"sample.py"}
    assert set(result["trace"]["source_digests"]) == {"sample.py"}


async def test_traced_program_failure_is_preserved(tmp_path):
    target = tmp_path / "bad.py"
    target.write_text("raise RuntimeError('failure')\n")
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] != 0
    assert "RuntimeError" in result["execution"]["output"]
    assert result["trace"]["events"]


async def test_observed_dispatch_is_attached_to_symbol_profile(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("def leaf(): return 1\ndef root(f): return f()\nroot(leaf)\n")
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.put_artifact("trace", "last", result["trace"])
        index = CodeIndex(tmp_path, state)
        index.refresh()
        profile = index.profile("root")
        assert any(
            edge["target"] == index.get_definition("leaf")["id"]
            for edge in profile["runtime_calls"]
        )
        target.write_text("def leaf(): return 2\ndef root(f): return f()\nroot(leaf)\n")
        index.refresh()
        assert index.profile("root")["runtime_calls"] == []
