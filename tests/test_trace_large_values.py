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
