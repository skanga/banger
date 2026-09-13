import sys

import pytest

from banger.execution import Executor
from banger.tracing import trace_file


@pytest.mark.parametrize("hook", ["__hash__", "__eq__", "__getattribute__", "descriptor"])
async def test_custom_metaclass_hooks_are_not_called_by_capture(tmp_path, hook):
    methods = {
        "__hash__": " def __hash__(cls):\n  raise RuntimeError('capture called hash')\n",
        "__eq__": " def __hash__(cls):\n  return hash(str)\n def __eq__(cls, other):\n  raise RuntimeError('capture called equality')\n",
        "__getattribute__": " def __getattribute__(cls, name):\n  raise RuntimeError('capture read metadata')\n",
        "descriptor": " @property\n def __name__(cls):\n  raise RuntimeError('capture invoked descriptor')\n",
    }
    target = tmp_path / "sample.py"
    target.write_text(
        "class Guard(type):\n"
        + methods[hook]
        + "class Value(metaclass=Guard):\n pass\n"
        + "def identity(value):\n return value\n"
        + "value = Value()\nassert identity(value) is value\nprint('PROGRAM PASS')\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0, result["execution"]
    assert "PROGRAM PASS" in result["execution"]["output"]
    events = [e for e in result["trace"]["events"] if e["function"] == "identity"]
    assert events[0]["arguments"]["value"] == {"type": "Value"}
    assert events[1]["value"] == {"type": "Value"}


async def test_exception_name_capture_bypasses_metaclass_descriptor(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "class Guard(type):\n @property\n def __name__(cls):\n"
        "  raise RuntimeError('capture invoked descriptor')\n"
        "class Problem(Exception, metaclass=Guard):\n pass\n"
        "def fail():\n raise Problem()\n"
        "try:\n fail()\nexcept Problem:\n print('HANDLED')\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0, result["execution"]
    assert "HANDLED" in result["execution"]["output"]
    assert any(e.get("exception") == "Problem" for e in result["trace"]["events"])
