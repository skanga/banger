"""Acceptance coverage for language gates through the model-facing tool interface."""

import pytest

from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox

SOURCES = {
    "sample.py": "def leaf(x):\n return x - 1\ndef root():\n return leaf(2)\n",
    "sample.js": "function leaf(x) { return x - 1; }\nfunction root() { return leaf(2); }\n",
    "sample.ts": "function leaf(x: number) { return x - 1; }\nfunction root() { return leaf(2); }\n",
    "Sample.java": "class Sample {\nstatic int leaf(int x) { return x - 1; }\nint root() { return leaf(2); }\n}\n",
    "Sample.cs": "class Sample {\nstatic int leaf(int x) { return x - 1; }\nint root() { return leaf(2); }\n}\n",
    "sample.cpp": "int leaf(int x) { return x - 1; }\nint root() { return leaf(2); }\n",
    "sample.c": "int leaf(int x) { return x - 1; }\nint root() { return leaf(2); }\n",
    "sample.go": "package sample\nfunc leaf(x int) int { return x - 1 }\nfunc root() int { return leaf(2) }\n",
    "sample.rs": "fn leaf(x: i32) -> i32 { x - 1 }\nfn root() -> i32 { leaf(2) }\n",
    "sample.rb": "def leaf(x)\n x - 1\nend\ndef root\n leaf(2)\nend\n",
}


@pytest.mark.parametrize("filename,source", SOURCES.items())
async def test_language_edit_gates_impact_and_restart_undo(tmp_path, filename, source):
    original = source.replace("\n", "\r\n").encode("utf-8")
    target = tmp_path / filename
    target.write_bytes(original)
    approvals = []

    async def approve(action, detail):
        approvals.append(action)
        return "allow"

    database = tmp_path / ".banger/state.db"
    with StateStore(database) as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ASK), approve)
        profile = await tools.invoke("profile", {"symbol": "leaf"})
        assert profile["callers"][0]["resolution"] == "resolved"

        rejected = await tools.invoke(
            "write_file", {"path": filename, "content": source + "\n@@@ {{\n"}
        )
        assert "syntax" in rejected["error"]
        assert target.read_bytes() == original
        assert state.latest_snapshot() is None

        rejected = await tools.invoke(
            "write_file", {"path": filename, "content": source.replace("leaf", "renamed", 1)}
        )
        assert "semantic" in rejected["error"]
        assert target.read_bytes() == original
        assert state.latest_snapshot() is None

        changed = await tools.invoke(
            "replace_text", {"path": filename, "old": "x - 1", "new": "x + 1"}
        )
        assert "error" not in changed
        assert target.read_bytes() == original.replace(b"x - 1", b"x + 1")
        for phase in ("impact_before", "impact_after"):
            leaf = next(
                report for report in changed[phase] if report["definition"]["name"] == "leaf"
            )
            assert leaf["callers"][0]["name"] == "leaf"
        assert "tests not yet executed" in changed["verification"]

    with StateStore(database) as state:
        reopened = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ASK), approve)
        undone = await reopened.invoke("rollback_edit", {})
        assert "error" not in undone
        assert target.read_bytes() == original
        assert state.latest_snapshot() is None
    assert len(approvals) == 4
    assert all(action.kind == "edit" for action in approvals)
