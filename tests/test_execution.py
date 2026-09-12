import asyncio
import os
import sys

import pytest

from banger.execution import Executor


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
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3)']); "
        "print('parent finished')"
    )
    result = await asyncio.wait_for(
        Executor(tmp_path).run_argv([sys.executable, "-c", script], timeout=0.2), timeout=1.5
    )
    assert "parent finished" in result["output"]
    assert result["exit_code"] == 0
