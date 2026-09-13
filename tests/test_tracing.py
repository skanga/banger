import sys

import pytest

from banger.execution import Executor
from banger.index import CodeIndex
from banger.state import StateStore
from banger.tracing import trace_file


@pytest.mark.parametrize(
    ("signature", "invocation", "expected"),
    [
        ("*items", "1, 2, 3", {"items": [1, 2, 3]}),
        ("**options", "first=1, second=2", {"options": {"first": 1, "second": 2}}),
        (
            "first, /, second=2, *items, enabled=True, **options",
            "1, 3, 4, 5, enabled=False, label='demo'",
            {
                "first": 1,
                "second": 3,
                "items": [4, 5],
                "enabled": False,
                "options": {"label": "demo"},
            },
        ),
        ("*items, enabled=True, **options", "", {"items": [], "enabled": True, "options": {}}),
    ],
)
async def test_trace_records_all_python_argument_kinds(tmp_path, signature, invocation, expected):
    target = tmp_path / "sample.py"
    target.write_text(
        f"def capture({signature}):\n local_only = 99\n return local_only\ncapture({invocation})\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    calls = [
        e for e in result["trace"]["events"] if e["event"] == "call" and e["function"] == "capture"
    ]
    assert len(calls) == 1
    assert calls[0]["arguments"] == expected
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.put_artifact("trace", "last", result["trace"])
    with StateStore(tmp_path / ".banger/state.db") as state:
        assert state.artifact("trace", "last") == result["trace"]


async def test_variadic_trace_values_stay_bounded_without_calling_repr(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "class Value:\n"
        " def __repr__(self):\n  raise RuntimeError('repr must not run')\n"
        "class Receiver:\n"
        " def capture(self, *items, **options):\n  return len(items)\n"
        "assert Receiver().capture(Value(), *range(20), label=Value()) == 21\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    calls = [
        e for e in result["trace"]["events"] if e["event"] == "call" and e["function"] == "capture"
    ]
    assert calls[0]["arguments"] == {
        "self": {"type": "Receiver"},
        "items": [{"type": "Value"}, *range(9)],
        "options": {"label": {"type": "Value"}},
    }


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
