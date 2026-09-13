import sys

import pytest

from banger.execution import Executor
from banger.tracing import trace_file


@pytest.mark.parametrize(
    "body", ["raise ValueError('bad value')", "return 1 / 0", "return missing()"]
)
async def test_failed_function_and_caller_unwind_without_return_values(tmp_path, body):
    target = tmp_path / "sample.py"
    target.write_text(
        f"def fail():\n {body}\n"
        "def caller():\n return fail()\n"
        "try:\n caller()\nexcept Exception:\n pass\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    for name in ("fail", "caller"):
        events = [e for e in result["trace"]["events"] if e["function"] == name]
        assert [e["event"] for e in events] == ["call", "exception", "unwind"]
        assert "value" not in events[-1]
        assert len({e["frame"] for e in events}) == 1


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("try:\n  raise ValueError()\n except ValueError:\n  return None", None),
        ("try:\n  raise ValueError()\n finally:\n  return 7", 7),
        ("try:\n  raise ValueError()\n except ValueError:\n  pass", None),
    ],
)
async def test_handled_exceptions_preserve_real_returns(tmp_path, body, expected):
    target = tmp_path / "sample.py"
    target.write_text(f"def recover():\n {body}\nrecover()\n", encoding="utf-8")
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "recover"]
    assert any(e["event"] == "exception" for e in events)
    assert events[-1]["event"] == "return"
    assert events[-1]["value"] == expected
    assert not any(e["event"] == "unwind" for e in events)
