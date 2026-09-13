"""Exercise the actual interactive launcher through native Linux/macOS PTYs."""

import errno
import os
import re
import select
import signal
import struct
import subprocess
import sys
import time

import pytest

from banger.state import StateStore

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX PTY; Windows console checked separately"
)


class Terminal:
    def __init__(self, root, columns, rows):
        import fcntl
        import termios

        self.master, self.slave = os.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
        self.original_mode = termios.tcgetattr(self.slave)
        env = os.environ.copy()
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TEXTUAL_DRIVER"):
            env.pop(key, None)
        env["TERM"] = "xterm-256color"
        env["NO_COLOR"] = "1"
        self.output = b""
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "banger", str(root)],
                stdin=self.slave,
                stdout=self.slave,
                stderr=self.slave,
                env=env,
                start_new_session=True,
            )
        except BaseException:
            os.close(self.master)
            os.close(self.slave)
            raise

    def read(self, timeout):
        if select.select([self.master], [], [], timeout)[0]:
            try:
                data = os.read(self.master, 65536)
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                return False
            self.output += data
            return bool(data)
        return False

    def plain(self, start=0):
        value = self.output[start:].decode("utf-8", errors="replace")
        value = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", value)
        return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)

    def expect(self, text, start=0):
        deadline = time.monotonic() + 20
        while text not in self.plain(start):
            assert self.process.poll() is None, self.plain()[-3000:]
            assert time.monotonic() < deadline, (text, self.plain()[-3000:])
            self.read(0.1)

    def send(self, keys):
        start = len(self.output)
        os.write(self.master, keys.encode())
        # Drain the resulting terminal updates before issuing the next key.
        # This is bounded I/O, not a fixed sleep or a headless pilot action.
        deadline = time.monotonic() + 1
        while self.read(0.15) and time.monotonic() < deadline:
            pass
        return start

    def click(self, x, y):
        return self.send(f"\x1b[<0;{x};{y}M\x1b[<0;{x};{y}m")

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=5)
        os.close(self.master)
        os.close(self.slave)


@pytest.mark.parametrize("columns,rows", [(80, 24), (120, 40)])
def test_native_terminal_setup_mouse_navigation_and_clean_exit(tmp_path, columns, rows):
    import termios

    root = tmp_path / "project"
    root.mkdir()
    source = "def answer():\n    return 42\n"
    (root / "sample.py").write_text(source, encoding="utf-8")
    with StateStore(root / ".banger/state.db") as state:
        state.put_artifact(
            "config",
            "last",
            {
                "provider": "openai",
                "model": "fixture-model",
                "base_url": "http://127.0.0.1:1/v1",
                "shell": "bash",
            },
        )
    terminal = Terminal(root, columns, rows)
    try:
        terminal.expect("Session setup")
        assert b"\x1b[?1049h" in terminal.output
        # Previous focus from the first setup control selects the last button.
        terminal.send("\x1b[Z")
        start = terminal.send("\r")
        terminal.expect("Enter a model, an HTTP(S) endpoint, and select permissions.", start)
        terminal.send("\x1b[Z")
        terminal.send("\x1b[Z")
        start = terminal.send("\r")
        terminal.expect("accept-edits", start)
        terminal.send("\x1b[B")
        terminal.send("\r")
        terminal.send("\t")
        terminal.send("\t")
        start = terminal.send("\r")
        terminal.expect("read-only | Ready", start)
        with StateStore(root / ".banger/state.db") as state:
            assert state.artifact("config", "last")["mode"] == "read-only"
            assert len(state.sessions()) == 1
        start = terminal.click(12, 3)
        terminal.expect("def answer():", start)
        terminal.expect("return 42", start)
        start = terminal.send("\x10")
        terminal.expect("Changes apply to subsequent actions.", start)
        terminal.send("\x1b")
        start = terminal.click(60, 2)
        terminal.expect("New session", start)
        terminal.send("\x11")
        assert terminal.process.wait(timeout=10) == 0
        while terminal.read(0.05):
            pass
        assert b"\x1b[?1049l" in terminal.output
        assert termios.tcgetattr(terminal.slave) == terminal.original_mode
        assert (root / "sample.py").read_text(encoding="utf-8") == source
    finally:
        terminal.close()
