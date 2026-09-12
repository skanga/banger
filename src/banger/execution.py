"""Local command execution with cancellation and bounded output."""

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path


class Executor:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.process = None

    async def run(self, command: str, shell: str, cwd: str = ".", timeout: float = 120):
        if shell == "cmd":
            if os.name != "nt":
                raise ValueError("cmd is available only on Windows")
            argv = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command]
        elif shell == "bash":
            argv = ["bash", "--noprofile", "--norc", "-c", command]
        else:
            raise ValueError("Select cmd or bash")
        return await self.run_argv(argv, cwd, timeout)

    async def _terminate(self, process):
        if os.name == "nt":
            if process.returncode is not None:
                return
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            await killer.wait()
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await process.wait()

    async def run_argv(
        self, argv: list[str], cwd: str = ".", timeout: float = 120, max_output: int = 50000
    ) -> dict:
        if self.process:
            raise RuntimeError("A command is already running")
        options = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        if os.name == "nt":
            argv = [sys.executable, str(Path(__file__).with_name("command_runner.py")), *argv]
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=self.root / cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            **options,
        )
        self.process = process
        output = bytearray()
        total = 0

        async def consume():
            nonlocal total
            while chunk := await process.stdout.read(8192):
                total += len(chunk)
                if len(output) < max_output:
                    output.extend(chunk[: max_output - len(output)])
            await process.wait()

        reader = asyncio.create_task(consume())
        timed_out = False
        try:
            await asyncio.wait_for(asyncio.shield(reader), timeout)
        except TimeoutError:
            timed_out = True
            await self._terminate(process)
            await reader
        except asyncio.CancelledError:
            await self._terminate(process)
            await reader
            raise
        finally:
            self.process = None
        return {
            "exit_code": process.returncode,
            "output": output.decode("utf-8", errors="replace"),
            "timed_out": timed_out,
            "truncated": total > max_output,
        }
