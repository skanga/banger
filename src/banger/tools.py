"""Typed model tools, with authorization before any project side effect."""

import asyncio
import inspect
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from banger.analysis import FlowAnalysis
from banger.discovery import EXCLUDED
from banger.edits import Editor
from banger.execution import Executor
from banger.index import CodeIndex
from banger.markup import MarkupIndex
from banger.permissions import Action, Decision
from banger.tracing import trace_file


def tool(function):
    function.model_tool = True
    return function


class Toolbox:
    def __init__(self, root, state, policy, approve=None):
        self.root, self.state, self.policy, self.approve = root, state, policy, approve
        self.root = Path(root).resolve()
        self.index = CodeIndex(self.root, state)
        self.editor = Editor(self.root, state, self.index)
        self.executor = Executor(self.root)
        self.markup = MarkupIndex(self.root)
        self.shell = "cmd" if os.name == "nt" else "bash"
        self.escalate = None
        self.session = None
        self.active_execution = False
        self.registry = {
            name: getattr(self, name)
            for name in dir(type(self))
            if getattr(getattr(type(self), name), "model_tool", False)
        }

    async def blocking(self, function, *args):
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Atomic edits/index refresh must finish before shutdown closes their database.
            await task
            raise

    async def refresh(self):
        return await self.blocking(self.index.refresh)

    async def record_execution(self, request, run):
        record = {
            **request,
            "id": uuid.uuid4().hex,
            "started_at": datetime.now(UTC).isoformat(),
            "status": "running",
        }
        self.state.put_artifact("execution", "last", record)
        self.active_execution = True
        try:
            result = await run()
            execution = result.get("execution", result)
            record.update(execution)
            record["status"] = "timed-out" if execution.get("timed_out") else "completed"
            return {**result, "execution": record} if "execution" in result else record
        except asyncio.CancelledError:
            record.update(
                status="interrupted", outcome="Interrupted; partial side effects may remain"
            )
            raise
        except Exception as exc:
            record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            record["finished_at"] = datetime.now(UTC).isoformat()
            self.state.put_artifact("execution", "last", record)
            self.active_execution = False

    def schemas(self):
        result = []
        kinds = {str: "string", int: "integer", bool: "boolean", float: "number"}
        for name, function in self.registry.items():
            properties, required = {}, []
            for key, param in inspect.signature(function).parameters.items():
                properties[key] = {"type": kinds[param.annotation]}
                if param.default is inspect.Parameter.empty:
                    required.append(key)
            result.append(
                {
                    "name": name,
                    "description": inspect.getdoc(function) or name,
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                        "additionalProperties": False,
                    },
                }
            )
        return result

    async def authorize(self, action, detail):
        decision = self.policy.decide(action)
        if decision == Decision.DENY:
            raise PermissionError("Action denied by the selected permission mode")
        if decision == Decision.ASK:
            answer = await self.approve(action, detail) if self.approve else "deny"
            if answer not in {"allow", "remember"}:
                raise PermissionError("Action denied by user")
            if self.policy.decide(action) == Decision.DENY:
                raise PermissionError("Action denied by the updated permission mode")
            if answer == "remember" and action.kind != "escalate":
                self.policy.remember(action)

    async def invoke(self, name, arguments):
        try:
            if name not in self.registry or not isinstance(arguments, dict):
                raise ValueError("Unknown tool or invalid argument object")
            function = self.registry[name]
            bound = inspect.signature(function).bind(**arguments)
            for key, value in bound.arguments.items():
                expected = inspect.signature(function).parameters[key].annotation
                if type(value) is not expected:
                    raise ValueError(f"{key} must be {expected.__name__}")
            return await function(**arguments)
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            return {"error": str(exc)}

    @tool
    async def list_files(self, directory: str = "."):
        """List immediate directory entries; excluded build/dependency folders are omitted."""
        await self.authorize(Action("read", path=directory), directory)
        path = self.policy.resolve(directory)
        return [
            {"name": p.name, "directory": p.is_dir()}
            for p in sorted(path.iterdir())
            if p.name not in EXCLUDED
        ][:1000]

    @tool
    async def read_file(self, path: str, start: int = 1, end: int = 200):
        """Read a bounded line range with line numbers. Prefer symbol queries before broad reads."""
        await self.authorize(Action("read", path=path), path)
        if start < 1 or end < start or end - start > 1000:
            raise ValueError("Select 1-based lines, at most 1001 per read")
        selected, total = [], 0
        with self.policy.resolve(path).open(encoding="utf-8", errors="replace") as source:
            for total, line in enumerate(source, start=1):
                if start <= total <= end:
                    selected.append(f"{total}: " + line.removesuffix("\n"))
        return {
            "path": path,
            "total_lines": total,
            "source": "\n".join(selected),
        }

    @tool
    async def search_symbols(self, query: str):
        """Search indexed declarations by case-insensitive substring; returns stable location IDs."""
        await self.refresh()
        return self.index.search_symbols(query)[:200]

    @tool
    async def get_definition(self, symbol: str):
        """Get a symbol's signature, language, parent and source location."""
        await self.refresh()
        return self.index.get_definition(symbol)

    @tool
    async def profile(self, symbol: str):
        """Get definition, incoming/outgoing calls and hierarchy with resolution evidence."""
        await self.refresh()
        return self.index.profile(symbol)

    @tool
    async def get_callers(self, symbol: str):
        """Find call sites, including explicitly marked ambiguous candidates."""
        await self.refresh()
        return self.index.get_callers(symbol)

    @tool
    async def call_tree(self, symbol: str, reverse: bool = False):
        """Get cycle-safe transitive call relationships over resolved edges."""
        await self.refresh()
        return self.index.call_tree(symbol, reverse)

    @tool
    async def trace_path(self, source: str, target: str):
        """Find a resolved call chain with call sites, argument expressions and return holders."""
        await self.refresh()
        return self.index.trace_path_details(source, target)

    @tool
    async def get_hierarchy(self, symbol: str):
        """Get declared bases and candidate subclasses, with static limitations."""
        await self.refresh()
        return self.index.get_hierarchy(symbol)

    @tool
    async def external_calls(self, symbol: str):
        """List imported external library calls and unresolved calls separately."""
        await self.refresh()
        calls = self.index.profile(symbol)["calls"]
        return {
            "external": [c for c in calls if c["resolution"] == "external"],
            "unresolved": [c for c in calls if c["resolution"] in {"unknown", "ambiguous"}],
        }

    @tool
    async def backflow(self, symbol: str, parameter: str):
        """Trace a parameter to call-site arguments and their preceding assignments, with limitations."""
        await self.refresh()
        return FlowAnalysis(self.index).backflow(symbol, parameter)

    @tool
    async def forwardflow(self, symbol: str):
        """Find holders of a function's return value and later references in each caller."""
        await self.refresh()
        return FlowAnalysis(self.index).forwardflow(symbol)

    @tool
    async def get_references(self, name: str):
        """Find syntactic name references and their enclosing scopes across languages."""
        await self.refresh()
        return FlowAnalysis(self.index).references(name)

    @tool
    async def relevant_tests(self, symbol: str):
        """Find test declarations that reach a symbol through resolved call paths."""
        await self.refresh()
        return FlowAnalysis(self.index).relevant_tests(symbol)

    @tool
    async def skim_source(self, symbol: str):
        """Return a one-level parsed body outline with source ranges and nested declaration cards."""
        await self.refresh()
        definition = self.index.get_definition(symbol)
        return {
            **self.index.files[definition["path"]]["outlines"][definition["id"]],
            "children": [s for s in self.index.symbols.values() if s["parent"] == definition["id"]],
        }

    @tool
    async def write_file(self, path: str, content: str):
        """Create or replace UTF-8 source after syntax checks, with durable undo and impact report."""
        await self.authorize(
            Action("edit", path=path), json.dumps({"path": path, "content": content})
        )
        return await self.blocking(self.editor.write, path, content)

    @tool
    async def replace_text(self, path: str, old: str, new: str):
        """Replace exactly one matching text occurrence, preserving all other content."""
        await self.authorize(
            Action("edit", path=path), json.dumps({"path": path, "old": old, "new": new})
        )
        return await self.blocking(self.editor.replace, path, old, new)

    @tool
    async def delete_file(self, path: str):
        """Delete one file with a durable snapshot for undo."""
        await self.authorize(Action("edit", path=path), "Delete " + path)
        return await self.blocking(self.editor.delete, path)

    @tool
    async def apply_edits(self, edits_json: str):
        """Apply coordinated edits: JSON object mapping paths to full text or null for deletion; combined gates and grouped undo."""
        changes = json.loads(edits_json)
        if not isinstance(changes, dict) or not changes or len(changes) > 100:
            raise ValueError("Provide a JSON object with 1 to 100 file edits")
        if any(
            not path.strip() or not (content is None or isinstance(content, str))
            for path, content in changes.items()
        ):
            raise ValueError("Each path must map to text or null")
        for path, content in changes.items():
            await self.authorize(
                Action("edit", path=path), json.dumps({"path": path, "content": content})
            )
        return await self.blocking(self.editor.apply_changes, changes)

    @tool
    async def rollback_edit(self):
        """Undo the last applied edit, refusing to overwrite subsequent user changes."""
        snapshot = self.state.latest_snapshot()
        if not snapshot:
            raise ValueError("No edit to roll back")
        snapshots = (
            self.state.snapshot_group(snapshot["batch"]) if snapshot.get("batch") else [snapshot]
        )
        for item in snapshots:
            await self.authorize(
                Action("edit", path=item["path"]), "Undo last edit: " + item["path"]
            )
        return await self.blocking(self.editor.rollback)

    @tool
    async def run_command(self, command: str, cwd: str = ".", timeout: int = 120):
        """Run a local cmd/bash command. Approved commands have host filesystem and network access."""
        if not 1 <= timeout <= 3600:
            raise ValueError("Timeout must be between 1 and 3600 seconds")
        await self.authorize(
            Action("command", command=command, cwd=cwd),
            f"Shell: {self.shell}\nDirectory: {self.policy.resolve(cwd)}\n{command}",
        )
        result = await self.record_execution(
            {
                "command": command,
                "cwd": str(self.policy.resolve(cwd)),
                "shell": self.shell,
                "timeout_seconds": timeout,
            },
            lambda: self.executor.run(command, self.shell, cwd, timeout),
        )
        await self.refresh()
        return result

    @tool
    async def check_last_execution(self):
        """Read the last captured command result without executing again."""
        record = self.state.artifact("execution", "last") or {"status": "No recorded execution"}
        if record.get("status") == "running" and not self.active_execution:
            return {
                **record,
                "status": "unknown",
                "recorded_status": "running",
                "outcome": "No completion was saved for this earlier run; inspect effects before retrying",
            }
        return record

    @tool
    async def execute_from(self, path: str, arguments_json: str = "[]", python: str = ""):
        """Execute a Python file under the runtime tracer. Optional interpreter and JSON argv list."""
        arguments = json.loads(arguments_json)
        if not isinstance(arguments, list) or any(not isinstance(a, str) for a in arguments):
            raise ValueError("arguments_json must be a JSON list of strings")
        target = self.policy.resolve(path)
        if target.suffix != ".py":
            raise ValueError("Runtime tracing currently supports Python files")
        argv = [python or sys.executable, str(target), *arguments]
        await self.authorize(
            Action("command", command=json.dumps(argv)),
            "Execute with Python call tracing: " + json.dumps(argv),
        )
        self.state.put_artifact(
            "trace",
            "last",
            {
                "events": [],
                "incomplete": True,
                "reason": "New trace attempt has no saved result yet",
            },
        )
        result = await self.record_execution(
            {"command": json.dumps(argv), "cwd": str(self.root), "kind": "python-trace"},
            lambda: trace_file(self.executor, target, arguments, python or sys.executable),
        )
        self.state.put_artifact("trace", "last", result["trace"])
        return result

    @tool
    async def get_runtime_trace(self, function: str = ""):
        """Read recorded Python arguments, returns, generator yields/resumes and exceptions without rerunning."""
        trace = self.state.artifact("trace", "last") or {"events": []}
        return {
            **trace,
            "events": [e for e in trace["events"] if not function or e["function"] == function],
        }

    @tool
    async def query_markup(self, selector: str):
        """Find HTML and Python template candidates by CSS selector; reports unevaluated interpolations."""
        await self.blocking(self.markup.refresh)
        return {
            "elements": self.markup.query(selector),
            "dom_references": self.markup.dom_references(selector),
            "unresolved": self.markup.unresolved,
        }

    @tool
    async def get_styles(self, element: str):
        """Resolve author CSS declarations by specificity, importance and order; reports unsupported rules."""
        await self.blocking(self.markup.refresh)
        if element not in self.markup.nodes:
            raise ValueError("Unknown element ID; query_markup first")
        return self.markup.styles(element)

    @tool
    async def execute_generated_testcase(self, content: str, python: str = ""):
        """Write a standalone Python reproduction under .banger/repros and run it under tracing."""
        path = ".banger/repros/" + uuid.uuid4().hex + ".py"
        await self.authorize(Action("edit", path=path), "Write generated reproduction:\n" + content)
        await self.blocking(self.editor.write, path, content)
        return await self.execute_from(path, python=python)

    @tool
    async def remember_fact(self, key: str, value: str):
        """Store a durable project convention or fact, never a credential."""
        await self.authorize(Action("edit", path=".banger/memory"), f"Remember {key}: {value}")
        self.state.set_memory(key, value)
        return {"saved": key}

    @tool
    async def recall_memory(self):
        """Read durable project facts."""
        return self.state.memories()

    @tool
    async def read_history(self, start: int = 0, count: int = 5):
        """Recover exact persisted conversation messages omitted from the model context."""
        if start < 0 or not 1 <= count <= 20:
            raise ValueError("Use a nonnegative start and count from 1 to 20")
        messages = self.state.messages(self.session) if self.session else []
        return {
            "total": len(messages),
            "messages": [
                {"index": i, "message": messages[i]}
                for i in range(start, min(start + count, len(messages)))
            ],
        }

    @tool
    async def read_tool_output(self, artifact: str, start: int = 0, length: int = 10000):
        """Read a bounded character range from a saved large tool result."""
        if start < 0 or not 1 <= length <= 50000:
            raise ValueError("Invalid output range")
        value = self.state.artifact("tool-output", artifact)
        if value is None:
            raise ValueError("No such tool output")
        content = json.dumps(value, ensure_ascii=False)
        return {"total_characters": len(content), "content": content[start : start + length]}

    @tool
    async def upgrade_to_pro(self):
        """Request user confirmation to switch to the configured stronger model."""
        if not self.escalate:
            raise ValueError("No model escalation configured")
        return await self.escalate()
