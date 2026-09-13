import sys

from banger.execution import Executor
from banger.state import StateStore
from banger.tracing import trace_file


async def test_async_generator_await_and_yield_keep_values_and_identity(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "async def values(seed):\n"
        " await asyncio.sleep(0)\n"
        " received = yield seed\n"
        " yield {'received': received}\n"
        "async def main():\n"
        " stream = values(3)\n"
        " assert await anext(stream) == 3\n"
        " assert await stream.asend(7) == {'received': 7}\n"
        " try:\n  await anext(stream)\n"
        " except StopAsyncIteration:\n  pass\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "values"]
    assert [e["event"] for e in events if e["event"] != "exception"] == [
        "call",
        "suspend",
        "resume",
        "yield",
        "resume",
        "yield",
        "resume",
        "return",
    ]
    assert len({e["frame"] for e in events}) == 1
    assert [e["value"] for e in events if e["event"] == "yield"] == [3, {"received": 7}]
    assert events[-1]["value"] is None
    assert events[0]["arguments"] == {"seed": 3}
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.put_artifact("trace", "last", result["trace"])
    with StateStore(tmp_path / ".banger/state.db") as state:
        assert state.artifact("trace", "last") == result["trace"]


async def test_async_generator_throw_recovers_and_values_never_call_repr(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "class Value:\n"
        " def __repr__(self):\n  raise AssertionError('repr called')\n"
        "async def values():\n"
        " try:\n  yield None\n"
        " except ValueError:\n"
        "  await asyncio.sleep(0)\n"
        "  yield Value()\n"
        "async def main():\n"
        " stream = values()\n"
        " assert await anext(stream) is None\n"
        " assert isinstance(await stream.athrow(ValueError('recover')), Value)\n"
        " assert [item async for item in stream] == []\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "values"]
    assert len({e["frame"] for e in events}) == 1
    assert [e["value"] for e in events if e["event"] == "yield"] == [None, {"type": "Value"}]
    assert any(e["event"] == "suspend" for e in events)
    assert any(e.get("exception") == "ValueError" for e in events)
    assert events[-1]["event"] == "return"


async def test_async_generator_cancelled_await_unwinds_without_yield(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "async def values(ready):\n"
        " ready.set()\n"
        " await asyncio.Event().wait()\n"
        " yield 1\n"
        "async def main():\n"
        " ready = asyncio.Event()\n"
        " stream = values(ready)\n"
        " task = asyncio.create_task(anext(stream))\n"
        " await ready.wait()\n"
        " task.cancel()\n"
        " try:\n  await task\n"
        " except asyncio.CancelledError:\n  pass\n"
        " await stream.aclose()\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "values"]
    assert [e["event"] for e in events] == ["call", "suspend", "resume", "exception", "unwind"]
    assert events[-2]["exception"] == "CancelledError"
    assert all("value" not in e for e in events)
    assert len({e["frame"] for e in events}) == 1


async def test_async_generator_close_is_an_unwind_not_an_extra_yield(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "async def values():\n yield 1\n yield 2\n"
        "async def main():\n"
        " stream = values()\n"
        " assert await anext(stream) == 1\n"
        " await stream.aclose()\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "values"]
    assert [e["event"] for e in events] == ["call", "yield", "resume", "exception", "unwind"]
    assert events[1]["value"] == 1
    assert "value" not in events[-1]
    assert len({e["frame"] for e in events}) == 1
