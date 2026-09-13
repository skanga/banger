import sys

from banger.execution import Executor
from banger.index import CodeIndex
from banger.state import StateStore
from banger.tracing import trace_file


async def test_immediately_completed_await_does_not_add_suspension(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "async def ready():\n return 7\n"
        "async def work():\n return await ready()\n"
        "assert asyncio.run(work()) == 7\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "work"]
    assert [e["event"] for e in events if e["event"] != "exception"] == ["call", "return"]
    assert events[-1]["value"] == 7


async def test_coroutine_can_suppress_cancellation_and_suspend_again(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "async def work():\n"
        " try:\n  await asyncio.sleep(30)\n"
        " except asyncio.CancelledError:\n  await asyncio.sleep(0)\n"
        " return 8\n"
        "async def main():\n"
        " task = asyncio.create_task(work())\n"
        " await asyncio.sleep(0)\n"
        " task.cancel()\n"
        " assert await task == 8\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "work"]
    assert [e["event"] for e in events if e["event"] != "exception"] == [
        "call",
        "suspend",
        "resume",
        "suspend",
        "resume",
        "return",
    ]
    assert events[-1]["value"] == 8
    assert len({e["frame"] for e in events}) == 1


async def test_coroutine_awaits_preserve_invocation_and_final_value(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "async def work(value):\n"
        " await asyncio.sleep(0)\n"
        " await asyncio.sleep(0)\n"
        " return value * 2\n"
        "assert asyncio.run(work(3)) == 6\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "work"]
    lifecycle = [e["event"] for e in events if e["event"] != "exception"]
    assert lifecycle == ["call", "suspend", "resume", "suspend", "resume", "return"]
    assert len({e["frame"] for e in events}) == 1
    assert events[-1]["value"] == 6
    assert events[0]["arguments"] == {"value": 3}


async def test_cancelled_coroutine_unwinds_without_a_successful_return(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "async def work():\n await asyncio.sleep(30)\n"
        "async def main():\n"
        " task = asyncio.create_task(work())\n"
        " await asyncio.sleep(0)\n"
        " task.cancel()\n"
        " try:\n  await task\n"
        " except asyncio.CancelledError:\n  pass\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "work"]
    assert [e["event"] for e in events] == ["call", "suspend", "resume", "exception", "unwind"]
    assert events[-2]["exception"] == "CancelledError"
    assert "value" not in events[-1]
    assert len({e["frame"] for e in events}) == 1


async def test_concurrent_coroutines_keep_separate_runtime_child_links(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import asyncio\n"
        "def leaf(value):\n return value\n"
        "async def work(value):\n await asyncio.sleep(0)\n return leaf(value)\n"
        "async def main():\n assert await asyncio.gather(work(3), work(7)) == [3, 7]\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )
    result = await trace_file(Executor(tmp_path), target, [], sys.executable)
    assert result["execution"]["exit_code"] == 0
    events = [e for e in result["trace"]["events"] if e["function"] == "work"]
    calls = [e for e in events if e["event"] == "call"]
    assert len(calls) == 2
    assert len({e["frame"] for e in calls}) == 2
    for call in calls:
        invocation = [e for e in events if e["frame"] == call["frame"]]
        assert invocation[-1]["event"] == "return"
        assert invocation[-1]["value"] == call["arguments"]["value"]
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.put_artifact("trace", "last", result["trace"])
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        edges = index.profile("work")["runtime_calls"]
        assert sorted(e["arguments"]["value"] for e in edges) == [3, 7]
