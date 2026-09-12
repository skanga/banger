import asyncio

import pytest

from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


async def test_interrupted_command_replaces_old_success_and_survives_restart(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        state.put_artifact("execution", "last", {"exit_code": 0, "output": "OLD SUCCESS"})
        started = asyncio.Event()

        async def slow(*args):
            started.set()
            await asyncio.Event().wait()

        toolbox.executor.run = slow
        task = asyncio.create_task(toolbox.run_command("slow-command"))
        await asyncio.wait_for(started.wait(), 2)
        running = await toolbox.check_last_execution()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert running["status"] == "running"
        assert running["command"] == "slow-command"
    with StateStore(tmp_path / ".banger/state.db") as state:
        saved = state.artifact("execution", "last")
        assert saved["status"] == "interrupted"
        assert saved["command"] == "slow-command"
        assert saved["cwd"] == str(tmp_path.resolve())
        assert "OLD SUCCESS" not in str(saved)


async def test_failed_launch_records_attempt_instead_of_previous_result(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        state.put_artifact("execution", "last", {"exit_code": 0, "output": "OLD SUCCESS"})

        async def fail(*args):
            raise FileNotFoundError("missing shell")

        toolbox.executor.run = fail
        result = await toolbox.invoke("run_command", {"command": "new-command"})
        assert "error" in result
        saved = await toolbox.check_last_execution()
        assert saved["status"] == "failed"
        assert saved["command"] == "new-command"
        assert "missing shell" in saved["error"]


async def test_interrupted_trace_does_not_return_an_older_trace(tmp_path, monkeypatch):
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        state.put_artifact("trace", "last", {"events": [{"function": "OLD"}]})
        started = asyncio.Event()

        async def slow(*args):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr("banger.tools.trace_file", slow)
        task = asyncio.create_task(toolbox.execute_from("sample.py"))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await toolbox.get_runtime_trace())["events"] == []
        assert (await toolbox.check_last_execution())["status"] == "interrupted"


async def test_unfinished_record_after_restart_is_not_claimed_as_live(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.put_artifact("execution", "last", {"status": "running", "command": "earlier"})
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await toolbox.check_last_execution()
        assert result["status"] == "unknown"
        assert result["recorded_status"] == "running"


async def test_completed_command_has_durable_invocation_and_timestamps(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        result = await toolbox.run_command("echo history-check")
        assert result["status"] == "completed"
        assert result["exit_code"] == 0
        assert "history-check" in result["output"]
        assert result["command"] == "echo history-check"
        assert result["finished_at"] >= result["started_at"]
        assert await toolbox.check_last_execution() == result
