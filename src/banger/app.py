"""Textual terminal interface for Banger."""

import asyncio
import json
import os
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlsplit

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.worker import WorkerCancelled, WorkerFailed

from banger.agent import Agent
from banger.chat_markdown import ChatMarkdown
from banger.discovery import EXCLUDED
from banger.models import ModelClient, ModelConfig
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox
from banger.wrapped_log import WrappedLog


def requires_api_key(config):
    return bool(
        config.get("requires_api_key")
        or config.get("api_key")
        or config.get("provider") == "anthropic"
        or urlsplit(config.get("base_url", "")).hostname == "api.openai.com"
    )


class Setup(ModalScreen):
    def __init__(self, saved=None):
        super().__init__(id="setup")
        self.saved = saved or {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="setup-box"):
            yield Label("BANGER  /  Session setup", classes="heading")
            yield Label("Provider")
            yield Select(
                [("OpenAI-compatible / local", "openai"), ("Anthropic", "anthropic")],
                value=self.saved.get("provider", "openai"),
                allow_blank=False,
                id="provider",
            )
            yield Input(self.saved.get("model", ""), placeholder="Model ID", id="model")
            yield Input(
                self.saved.get("base_url", "https://api.openai.com/v1"),
                placeholder="API base URL, including /v1",
                id="endpoint",
            )
            yield Input(
                placeholder="API key (or use provider environment variable)",
                password=True,
                id="api-key",
            )
            yield Input(
                self.saved.get("stronger_model", ""),
                placeholder="Optional stronger model ID",
                id="stronger",
            )
            yield Label("Permission mode — remembered for this project")
            yield Select(
                [(m.value, m.value) for m in Mode],
                value=(
                    self.saved["mode"]
                    if self.saved.get("mode") in {m.value for m in Mode}
                    else Select.NULL
                ),
                prompt="Choose permissions",
                id="mode",
            )
            yield Select(
                [("cmd", "cmd"), ("bash", "bash")],
                value=self.saved.get("shell", "cmd" if os.name == "nt" else "bash"),
                allow_blank=False,
                id="shell",
            )
            yield Static(
                "Read-only: queries only. Ask: approve changes and commands. "
                "Accept-edits: approve commands. Full-access: run automatically. "
                "Commands run locally with your filesystem and network access."
            )
            yield Static("", id="setup-error")
            yield Button("Start session", id="start", variant="primary")

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "provider":
            endpoint = self.query_one("#endpoint", Input)
            if endpoint.value in {"https://api.openai.com/v1", "https://api.anthropic.com/v1"}:
                endpoint.value = (
                    "https://api.anthropic.com/v1"
                    if event.value == "anthropic"
                    else "https://api.openai.com/v1"
                )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id != "start":
            return
        model = self.query_one("#model", Input).value.strip()
        mode = self.query_one("#mode", Select).value
        endpoint = self.query_one("#endpoint", Input).value.strip().rstrip("/")
        if (
            not model
            or not isinstance(mode, str)
            or not endpoint.startswith(("http://", "https://"))
        ):
            self.query_one("#setup-error", Static).update(
                "Enter a model, an HTTP(S) endpoint, and select permissions."
            )
            return
        provider = self.query_one("#provider", Select).value
        key = self.query_one("#api-key", Input).value or os.environ.get(
            "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY", ""
        )
        if provider == "anthropic" and not key:
            self.query_one("#setup-error", Static).update("Anthropic requires an API key.")
            return
        self.dismiss(
            {
                "provider": provider,
                "model": model,
                "base_url": endpoint,
                "api_key": key,
                "mode": mode,
                "shell": self.query_one("#shell", Select).value,
                "stronger_model": self.query_one("#stronger", Input).value.strip(),
            }
        )


class Approval(ModalScreen):
    BINDINGS: ClassVar = [("escape", "deny", "Deny")]

    def __init__(self, action, detail):
        super().__init__()
        self.request, self.detail = action, detail

    def compose(self):
        with Vertical(id="approval-box"):
            yield Label(f"Approval required: {self.request.kind}", classes="heading")
            yield TextArea(self.detail, read_only=True, id="approval-detail")
            with Horizontal(classes="buttons"):
                yield Button("Allow once", id="allow", variant="primary")
                if self.request.kind in {"command", "read"}:
                    yield Button("Remember for session", id="remember")
                yield Button("Deny", id="deny", variant="error")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id)

    def action_deny(self):
        self.dismiss("deny")


class ProjectTree(DirectoryTree):
    def filter_paths(self, paths):
        return [p for p in paths if p.name not in EXCLUDED and not p.is_symlink()]

    def on_mount(self):
        # Widget-owned workers are cancelled automatically when the tree unmounts.
        self.run_worker(self._watch_directories(), group="directory-changes")

    @staticmethod
    def _directories_changed(snapshots):
        for path, previous in snapshots:
            try:
                with os.scandir(path) as entries:
                    current = {
                        (entry.name, entry.is_dir())
                        for entry in entries
                        if entry.name not in EXCLUDED and not entry.is_symlink()
                    }
            except (FileNotFoundError, NotADirectoryError):
                return True
            except OSError:
                # Inaccessible directories must not interrupt the interface.
                continue
            if current != previous:
                return True
        return False

    async def _watch_directories(self):
        while True:
            await asyncio.sleep(1)
            # Inspect only cached listings, including previously opened folders.
            # Unopened directories are read normally when the user expands them.
            snapshots = []
            pending = [self.root]
            while pending:
                node = pending.pop()
                if node.data and node.allow_expand and node.data.loaded:
                    snapshots.append(
                        (
                            node.data.path,
                            {(item.data.path.name, item.allow_expand) for item in node.children},
                        )
                    )
                    pending.extend(node.children)
            if await asyncio.to_thread(self._directories_changed, snapshots):
                # Textual's reload preserves expanded paths and the selected entry.
                await self.reload()


class ModePicker(ModalScreen):
    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]

    def __init__(self, mode):
        super().__init__()
        self.mode = mode

    def compose(self):
        with Vertical(id="mode-box"):
            yield Label("Permission mode", classes="heading")
            yield Select(
                [(m.value, m.value) for m in Mode],
                value=self.mode.value,
                allow_blank=False,
                id="permission-mode",
            )
            yield Static(
                "Changes apply to subsequent actions. Interrupt a running command with Escape."
            )
            yield Button("Apply", id="apply-mode", variant="primary")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(Mode(self.query_one("#permission-mode", Select).value))

    def action_cancel(self):
        self.dismiss(None)


class AgentEvent(Message):
    def __init__(self, kind, payload):
        super().__init__()
        self.kind, self.payload = kind, payload


class BangerApp(App):
    TITLE = "Banger"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: #111820; color: #d5e1e8; }
    Header { background: #193c43; }
    Footer { background: #193c43; }
    #workspace { height: 1fr; }
    #files { width: 26; border-right: solid #34545c; }
    TabbedContent { width: 1fr; }
    #chat-log, #tool-log, #diff-log { height: 1fr; }
    #draft { height: auto; max-height: 10; padding: 0 1; color: #b1d9cc; }
    #prompt { dock: bottom; }
    #status { height: 1; padding: 0 1; background: #193c43; }
    #source { height: 1fr; }
    Setup, Approval, ModePicker { align: center middle; background: #000000 65%; }
    #mode-box { width: 65; height: auto; padding: 1 2; background: #18262e; border: round #5fbaa4; }
    #setup-box { width: 78; max-height: 95%; padding: 1 2; background: #18262e; border: round #5fbaa4; }
    #approval-box { width: 90%; height: 80%; padding: 1 2; background: #18262e; border: round #d8af62; }
    #approval-detail { height: 1fr; }
    .heading { color: #81d8bd; text-style: bold; margin-bottom: 1; }
    .buttons { height: 3; }
    .buttons Button { margin-right: 1; }
    #setup-error { color: #ff887d; height: auto; }
    """
    BINDINGS: ClassVar = [
        ("ctrl+q", "quit", "Quit"),
        ("escape", "interrupt", "Interrupt"),
        ("ctrl+n", "new_session", "New session"),
        Binding("ctrl+p", "permissions", "Permissions", priority=True),
        ("ctrl+l", "focus_prompt", "Prompt"),
    ]

    def __init__(self, root, *, setup=False):
        super().__init__()
        self.show_setup = setup
        self.root = Path(root).resolve()
        self.state = StateStore(self.root / ".banger/state.db")
        self.agent = None
        self.client = None
        self.worker = None
        self.draft = ""
        self.session_ids = []
        self._status_text = "Choose a model and permission mode to begin"
        self._working = False
        self._awaiting_approval = False
        self._activity_frame = 0

    def compose(self):
        yield Header()
        with Horizontal(id="workspace"):
            yield ProjectTree(self.root, id="files")
            with TabbedContent(id="tabs"):
                with TabPane("Chat", id="chat-tab"):
                    yield WrappedLog(id="chat-log")
                    yield Static("", id="draft", markup=False)
                    yield Input(
                        placeholder="Ask Banger to inspect, change, or debug your project…",
                        id="prompt",
                    )
                with TabPane("Source", id="source-tab"):
                    yield TextArea(read_only=True, show_line_numbers=True, id="source")
                with TabPane("Diffs", id="diff-tab"):
                    yield RichLog(id="diff-log", wrap=False)
                with TabPane("Tools", id="tools-tab"):
                    yield WrappedLog(id="tool-log")
                with TabPane("Sessions", id="sessions-tab"):
                    yield ListView(id="sessions")
        yield Static("Choose a model and permission mode to begin", id="status", markup=False)
        yield Footer()

    def on_mount(self):
        self._status_widget = self.query_one("#status", Static)
        self._activity_timer = self.set_interval(0.15, self._animate_activity, pause=True)
        self._terminal_control("\033[22;2t")  # Save the terminal's existing window title.
        saved = self.state.artifact("config", "last") or {}
        key = os.environ.get(
            "ANTHROPIC_API_KEY" if saved.get("provider") == "anthropic" else "OPENAI_API_KEY",
            "",
        )
        if (
            not self.show_setup
            and saved.get("provider") in {"openai", "anthropic"}
            and saved.get("model", "").strip()
            and saved.get("base_url", "").startswith(("http://", "https://"))
            and saved.get("mode") in {m.value for m in Mode}
            and saved.get("shell") in {"cmd", "bash"}
            and (key or not requires_api_key(saved))
        ):
            self.call_after_refresh(self.configure, {"stronger_model": "", **saved, "api_key": key})
        else:
            self.push_screen(Setup(saved), self.configure)

    async def configure(self, config):
        if not config:
            return
        if self.client:
            await self.client.client.aclose()
        saved = {k: v for k, v in config.items() if k != "api_key"}
        saved["requires_api_key"] = requires_api_key(config)
        self.state.put_artifact("config", "last", saved)
        self.client = ModelClient(
            ModelConfig(config["provider"], config["model"], config["base_url"], config["api_key"])
        )
        tools = Toolbox(
            self.root, self.state, PermissionPolicy(self.root, Mode(config["mode"])), self.approve
        )
        tools.shell = config["shell"]
        session = self.agent.session if self.agent else None
        self.agent = Agent(
            self.state, tools, self.client, session, config["stronger_model"] or None
        )
        self.agent.on_event = lambda kind, payload: self.post_message(AgentEvent(kind, payload))
        self._status("Ready")
        await self.refresh_sessions()
        self.query_one("#prompt", Input).focus()

    def _status(self, text):
        self._status_text = text
        self._working = text == "Working" or text.startswith("Running ")
        self._render_status()

    def _terminal_control(self, sequence):
        if self._driver is not None and not self.is_headless:
            self._driver.write(sequence)

    def _animate_activity(self):
        self._activity_frame += 1
        self._render_status()

    def _render_status(self):
        if not self.is_running:
            return
        text = self._status_text
        title = "Banger"
        if self._awaiting_approval:
            text = "🔔 Action required" + "." * (self._activity_frame % 4)
            title = text + " | Banger"
        elif self._working:
            frame = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[self._activity_frame % 10]
            text = f"{frame} Working"
            if self._status_text.startswith("Running "):
                text += " · " + self._status_text
            title = f"{frame} Working | Banger"
        if self._working or self._awaiting_approval:
            self._activity_timer.resume()
        else:
            self._activity_timer.pause()
            self._activity_frame = 0
        if title != self.title:
            self.title = title
            self._terminal_control(f"\033]2;{title}\033\\")
        prefix = (
            f"{self.agent.model.config.model} | {self.agent.tools.policy.mode.value} | "
            if self.agent
            else ""
        )
        self._status_widget.update(prefix + text)

    async def approve(self, action, detail):
        future = asyncio.get_running_loop().create_future()
        screen = Approval(action, detail)

        def finish(answer):
            if not future.done():
                future.set_result(answer)

        self.push_screen(screen, finish)
        self._awaiting_approval = True
        self._render_status()
        self.bell()
        try:
            return await future
        finally:
            # A mode picker may cover this approval when its worker is cancelled.
            # Remove overlays as well so an expired request cannot reappear.
            while screen in self.screen_stack:
                self.pop_screen()
            self._awaiting_approval = False
            self._render_status()

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id != "prompt" or not event.value.strip() or not self.agent:
            return
        if self.agent.running:
            self.notify("Interrupt the current task before sending another", severity="warning")
            return
        prompt = event.value
        event.input.value = ""
        self.query_one("#chat-log", RichLog).write(Text("You › " + prompt, style="bold #81d8bd"))
        self.worker = self.run_worker(self._run(prompt), exclusive=True, group="agent")

    async def _run(self, prompt):
        self._status("Working")
        try:
            await self.agent.run(prompt)
        except asyncio.CancelledError:
            self.clear_draft()
            self._status("Interrupted; session saved")
            raise
        except Exception as exc:  # noqa: BLE001 -- keep provider/tool failures inside the TUI
            self.clear_draft()
            if self.is_running:
                self.query_one("#chat-log", RichLog).write(
                    Text(f"Error: {type(exc).__name__}: {exc}", style="red")
                )
                self._status("Stopped with an error; session saved")
        finally:
            self._working = False
            self._render_status()
            await self.refresh_sessions()

    def clear_draft(self):
        self.draft = ""
        if self.is_running:
            self.query_one("#draft", Static).update("")

    def clear_session_views(self):
        self.clear_draft()
        for name in ("chat-log", "tool-log", "diff-log"):
            self.query_one("#" + name, RichLog).clear()

    def render_tool_result(self, payload):
        self.query_one("#tool-log", RichLog).write(Text(json.dumps(payload, indent=2)[:60000]))
        result = payload["result"]
        if isinstance(result, dict) and result.get("diff"):
            self.query_one("#diff-log", RichLog).write(Syntax(result["diff"], "diff"))

    def on_agent_event(self, event: AgentEvent):
        if not self.is_running:
            return
        if event.kind == "text":
            self.draft += event.payload
            self.query_one("#draft", Static).update(self.draft)
        elif event.kind == "status":
            self._status(event.payload)
        elif event.kind == "done":
            self.query_one("#chat-log", RichLog).write(ChatMarkdown(event.payload))
            self.draft = ""
            self.query_one("#draft", Static).update("")
            self._status("Ready")
        elif event.kind == "tool_start":
            if self.draft:
                self.query_one("#chat-log", RichLog).write(ChatMarkdown(self.draft))
                self.draft = ""
                self.query_one("#draft", Static).update("")
            self._status("Running " + event.payload["name"])
            self.query_one("#tool-log", RichLog).write(Text(json.dumps(event.payload, indent=2)))
        elif event.kind == "tool_result":
            self.render_tool_result(event.payload)
            result = event.payload["result"]
            if isinstance(result, dict) and result.get("diff"):
                self.query_one("#files", ProjectTree).reload()

    async def show_source(self, path):
        source = path.read_text(encoding="utf-8", errors="replace")
        self.query_one("#source", TextArea).load_text(source)
        self.query_one("#tabs", TabbedContent).active = "source-tab"

    async def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        try:
            await self.show_source(event.path)
        except OSError as exc:
            self.notify(str(exc), severity="error")

    async def refresh_sessions(self):
        if not self.is_running:
            return
        rows = self.state.sessions()
        self.session_ids = [row["id"] for row in rows]
        listing = self.query_one("#sessions", ListView)
        await listing.clear()
        for row in rows:
            messages = self.state.messages(row["id"])
            title = next(
                (m["content"][:70] for m in messages if m["role"] == "user"), "New session"
            )
            await listing.append(ListItem(Label(title, markup=False)))

    async def on_list_view_selected(self, event: ListView.Selected):
        if event.list_view.id != "sessions" or not self.agent or self.agent.running:
            return
        session = self.session_ids[event.list_view.index]
        self.agent = Agent(
            self.state, self.agent.tools, self.client, session, self.agent.stronger_model
        )
        self.agent.on_event = lambda kind, payload: self.post_message(AgentEvent(kind, payload))
        self.clear_session_views()
        log = self.query_one("#chat-log", RichLog)
        calls = {
            call["id"]: call["function"]["name"]
            for message in self.agent.messages
            for call in message.get("tool_calls", [])
        }
        for message in self.agent.messages:
            if message["role"] in {"user", "assistant"} and message.get("content"):
                if message["role"] == "assistant":
                    log.write(ChatMarkdown(message["content"]))
                else:
                    log.write(Text("You › " + message["content"], style="bold #81d8bd"))
            elif message["role"] == "tool":
                try:
                    result = json.loads(message["content"])
                except (ValueError, TypeError):
                    result = message["content"]
                self.render_tool_result(
                    {"name": calls.get(message["tool_call_id"], "tool"), "result": result}
                )
        self.query_one("#tabs", TabbedContent).active = "chat-tab"
        self._status("Session resumed")

    def action_interrupt(self):
        if self.worker and self.agent and self.agent.running:
            self.worker.cancel()

    async def action_new_session(self):
        if not self.agent or self.agent.running:
            return
        self.agent = Agent(
            self.state, self.agent.tools, self.client, stronger_model=self.agent.stronger_model
        )
        self.agent.on_event = lambda kind, payload: self.post_message(AgentEvent(kind, payload))
        self.clear_session_views()
        await self.refresh_sessions()
        self._status("New session")

    def action_permissions(self):
        if self.agent and not isinstance(self.screen, ModePicker):
            self.push_screen(ModePicker(self.agent.tools.policy.mode), self.set_mode)

    def set_mode(self, mode):
        if mode is not None:
            self.agent.tools.policy.mode = mode
            saved = self.state.artifact("config", "last") or {}
            saved["mode"] = mode.value
            self.state.put_artifact("config", "last", saved)
            if self._working or self._awaiting_approval:
                self._render_status()
            else:
                self._status("Permission mode updated")

    def action_focus_prompt(self):
        self.query_one("#tabs", TabbedContent).active = "chat-tab"
        self.query_one("#prompt", Input).focus()

    async def on_unmount(self):
        self._activity_timer.stop()
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker.wait()
            except (WorkerCancelled, WorkerFailed):
                self.worker = None
        if self.client:
            await self.client.client.aclose()
        self.state.close()
        self._terminal_control("\033[23;2t")  # Restore the title saved on mount.


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Banger terminal coding agent")
    parser.add_argument("directory", nargs="?", default=".", help="Project directory")
    parser.add_argument("--setup", action="store_true", help="Edit the saved project settings")
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    if not root.is_dir():
        parser.error("Project directory does not exist")
    BangerApp(root, setup=args.setup).run()
