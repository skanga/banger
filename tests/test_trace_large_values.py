import json
import subprocess
import sys

import pytest

from banger.execution import Executor
from banger.state import StateStore
from banger.tracing import trace_file


@pytest.mark.parametrize("expression", ["10 ** 5000", "-(10 ** 5000)"])
async def test_large_integer_arguments_and_returns_do_not_destroy_trace(tmp_path, expression):
    target = tmp_path / "sample.py"
    target.write_text(
        "def identity(value):\n return value\n"
        f"number = {expression}\n"
        "assert identity(number) == number\n"
        "assert identity(42) == 42\n"
        "print('PROGRAM PASS')\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0, result["execution"]
    assert "PROGRAM PASS" in result["execution"]["output"]
    events = [e for e in result["trace"]["events"] if e["function"] == "identity"]
    large = events[0]["arguments"]["value"]
    assert large["type"] == "int"
    assert large["bits"] == (10**5000).bit_length()
    assert large["truncated"] is True
    assert large["negative"] is expression.startswith("-")
    assert events[1]["value"] == large
    assert events[2]["arguments"]["value"] == 42
    assert events[3]["value"] == 42
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.put_artifact("trace", "last", result["trace"])
    with StateStore(tmp_path / ".banger/state.db") as state:
        assert state.artifact("trace", "last") == result["trace"]


async def test_nested_large_integers_are_bounded_and_smaller_values_stay_exact(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "def identity(value):\n return value\n"
        "identity({'values': [10 ** 5000, -(10 ** 5000)]})\n"
        "identity(2 ** 1023)\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0, result["execution"]
    events = [e for e in result["trace"]["events"] if e["function"] == "identity"]
    nested = events[0]["arguments"]["value"]["values"]
    assert [v["negative"] for v in nested] == [False, True]
    assert all(v["type"] == "int" and v["truncated"] for v in nested)
    assert events[1]["value"] == {"values": nested}
    assert events[2]["arguments"]["value"] == 2**1023
    assert events[3]["value"] == 2**1023


def test_dictionary_capture_allocation_is_bounded_by_sample_size():
    # Isolate tracemalloc from pytest and allocate the input before measuring.
    program = """
import json
import tracemalloc
from banger.trace_runner import safe_value
values = {str(i): i for i in range(300_000)}
tracemalloc.start()
sample = safe_value(values)
_, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(json.dumps({'sample': sample, 'peak': peak}))
"""
    process = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, timeout=30, check=True
    )
    result = json.loads(process.stdout)
    assert result["sample"] == {str(i): i for i in range(10)}
    assert result["peak"] < 200_000, result


def test_dictionary_sample_limit_includes_non_string_keys():
    from banger.trace_runner import safe_value

    values = {i: i for i in range(9)}
    values["included"] = [1, 2]
    values["beyond_limit"] = 3
    assert safe_value(values) == {"included": [1, 2]}


async def test_large_dictionary_capture_preserves_execution_and_restart(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "def identity(value):\n return value\n"
        "values = dict.fromkeys(map(str, range(100_000)), 1)\n"
        "assert identity(values) is values\n"
        "assert len(values) == 100_000\n"
        "print('PROGRAM PASS')\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0, result["execution"]
    assert "PROGRAM PASS" in result["execution"]["output"]
    events = [e for e in result["trace"]["events"] if e["function"] == "identity"]
    assert [e["event"] for e in events] == ["call", "return"]
    expected = {str(i): 1 for i in range(10)}
    assert events[0]["arguments"]["value"] == expected
    assert events[1]["value"] == expected
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.put_artifact("trace", "last", result["trace"])
    with StateStore(tmp_path / ".banger/state.db") as state:
        assert state.artifact("trace", "last") == result["trace"]
