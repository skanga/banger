import sys

from banger.execution import Executor
from banger.index import CodeIndex
from banger.state import StateStore
from banger.tracing import trace_file


async def test_generator_yields_and_resumes_share_one_invocation(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "def values(seed):\n"
        " received = yield seed\n"
        " yield received\n"
        " return 99\n"
        "stream = values(3)\n"
        "assert next(stream) == 3\n"
        "assert stream.send(7) == 7\n"
        "try:\n next(stream)\n"
        "except StopIteration as done:\n assert done.value == 99\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "values"]
    assert [e["event"] for e in events] == ["call", "yield", "resume", "yield", "resume", "return"]
    assert len({e["frame"] for e in events}) == 1
    assert [e["value"] for e in events if e["event"] == "yield"] == [3, 7]
    assert events[-1]["value"] == 99
    assert events[0]["arguments"] == {"seed": 3}


async def test_generator_throw_can_recover_and_then_return(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "def values():\n"
        " try:\n  yield 1\n"
        " except ValueError:\n  yield 2\n"
        " return 3\n"
        "stream = values()\n"
        "assert next(stream) == 1\n"
        "assert stream.throw(ValueError('recover')) == 2\n"
        "try:\n next(stream)\n"
        "except StopIteration as done:\n assert done.value == 3\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "values"]
    assert [e["value"] for e in events if e["event"] == "yield"] == [1, 2]
    assert events[-1]["event"] == "return"
    assert events[-1]["value"] == 3
    assert len({e["frame"] for e in events}) == 1


async def test_resumed_generator_keeps_runtime_child_links_after_restart(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "def leaf(value):\n return value\n"
        "def values(seed):\n yield leaf(seed)\n yield leaf(seed + 1)\n"
        "assert list(values(3)) == [3, 4]\n"
        "assert list(values(8)) == [8, 9]\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    calls = [
        e for e in result["trace"]["events"] if e["function"] == "values" and e["event"] == "call"
    ]
    assert len(calls) == 2
    assert len({e["frame"] for e in calls}) == 2
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.put_artifact("trace", "last", result["trace"])
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        edges = index.profile("values")["runtime_calls"]
        assert [e["arguments"]["value"] for e in edges] == [3, 4, 8, 9]
        assert {e["target"] for e in edges} == {index.get_definition("leaf")["id"]}


async def test_yield_from_and_generator_close_do_not_fabricate_returns(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "def values():\n yield from [1, 2]\n"
        "stream = values()\n"
        "assert next(stream) == 1\n"
        "assert next(stream) == 2\n"
        "stream.close()\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "values"]
    assert [e["value"] for e in events if e["event"] == "yield"] == [1, 2]
    assert events[-1]["event"] == "unwind"
    assert not any(e["event"] == "return" for e in events)
    assert len({e["frame"] for e in events}) == 1
