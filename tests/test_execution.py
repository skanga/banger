import asyncio
import os
import sys

import pytest

from banger.execution import Executor


async def test_concurrent_command_is_rejected_while_first_process_is_starting(
    tmp_path, monkeypatch
):
    executor = Executor(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    original = asyncio.create_subprocess_exec
    attempts = 0

    async def delayed(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            entered.set()
            await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed)
    first = asyncio.create_task(executor.run_argv([sys.executable, "-c", "print('first')"]))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        with pytest.raises(RuntimeError, match="already running"):
            await executor.run_argv([sys.executable, "-c", "print('second')"])
        assert attempts == 1
    finally:
        release.set()
        result = await asyncio.wait_for(first, timeout=10)
    assert "first" in result["output"]
    assert executor.process is None


@pytest.mark.parametrize("cancel", [False, True])
async def test_failed_or_cancelled_launch_allows_next_command(tmp_path, monkeypatch, cancel):
    executor = Executor(tmp_path)
    entered = asyncio.Event()
    original = asyncio.create_subprocess_exec

    async def fail_launch(*args, **kwargs):
        entered.set()
        if cancel:
            await asyncio.Event().wait()
        raise FileNotFoundError("launch failed")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail_launch)
    task = asyncio.create_task(executor.run_argv([sys.executable, "-c", "pass"]))
    await asyncio.wait_for(entered.wait(), timeout=5)
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else FileNotFoundError):
        await task
    monkeypatch.setattr(asyncio, "create_subprocess_exec", original)
    result = await executor.run_argv([sys.executable, "-c", "print('recovered')"])
    assert result["exit_code"] == 0 and "recovered" in result["output"]
    assert executor.process is None


@pytest.mark.asyncio
async def test_output_exit_and_cwd(tmp_path):
    executor = Executor(tmp_path)
    result = await executor.run_argv(
        [sys.executable, "-c", "import os; print(os.getcwd()); raise SystemExit(3)"]
    )
    assert result["exit_code"] == 3
    assert str(tmp_path) in result["output"]


@pytest.mark.asyncio
async def test_timeout_terminates_process(tmp_path):
    executor = Executor(tmp_path)
    result = await executor.run_argv(
        [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1
    )
    assert result["timed_out"]
    assert executor.process is None


@pytest.mark.asyncio
async def test_cancellation_waits_for_termination(tmp_path):
    executor = Executor(tmp_path)
    task = asyncio.create_task(
        executor.run_argv([sys.executable, "-c", "import time; time.sleep(30)"])
    )
    for _ in range(100):
        if executor.process:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert executor.process is None


@pytest.mark.asyncio
async def test_output_is_bounded(tmp_path):
    result = await Executor(tmp_path).run_argv(
        [sys.executable, "-c", "print('a' * 100000)"], max_output=1000
    )
    assert len(result["output"]) < 1100
    assert result["truncated"]


async def test_shell_executes_in_selected_directory(tmp_path):
    shell = "cmd" if os.name == "nt" else "bash"
    result = await Executor(tmp_path).run("echo banger-shell-check", shell)
    assert result["exit_code"] == 0
    assert "banger-shell-check" in result["output"]


async def test_parent_exit_with_inherited_output_pipe_does_not_hang(tmp_path):
    script = (
        "import subprocess, sys; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print('parent finished')"
    )
    result = await asyncio.wait_for(
        # Allow the parent/interpreter wrapper to finish even on a loaded runner.
        # The inherited pipe still outlives both deadlines without tree cleanup.
        Executor(tmp_path).run_argv([sys.executable, "-c", script], timeout=5),
        timeout=10,
    )
    assert "parent finished" in result["output"]
    assert result["exit_code"] == 0
    # Windows job ownership closes descendants at normal parent exit. POSIX
    # keeps the pipe open until the command deadline terminates the group.
    assert result["timed_out"] is (os.name != "nt")
