import json

import pytest

from banger.edits import Editor
from banger.index import CodeIndex
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


def test_coordinated_signature_change_and_group_undo_survive_restart(tmp_path):
    original = {
        "lib.py": "def leaf(value): return value\n",
        "app.py": "from lib import leaf\ndef root(): return leaf(1)\n",
    }
    for name, content in original.items():
        (tmp_path / name).write_text(content)
    changes = {
        "lib.py": "def leaf(value, extra): return value + extra\n",
        "app.py": "from lib import leaf\ndef root(): return leaf(1, 2)\n",
    }
    with StateStore(tmp_path / ".banger/state.db") as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path))
        with pytest.raises(ValueError, match="semantic"):
            editor.write("lib.py", changes["lib.py"])
        result = editor.apply_changes(changes)
        assert len(result["edits"]) == 2
        assert all((tmp_path / name).read_text() == content for name, content in changes.items())
    with StateStore(tmp_path / ".banger/state.db") as state:
        Editor(tmp_path, state, CodeIndex(tmp_path)).rollback()
        assert all((tmp_path / name).read_text() == content for name, content in original.items())
        assert state.latest_snapshot() is None


def test_invalid_batch_leaves_every_file_untouched(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    with StateStore(tmp_path / ".banger/state.db") as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path))
        with pytest.raises(ValueError, match="syntax"):
            editor.apply_changes({"a.py": "x = 2\n", "b.py": "def broken(:"})
        assert (tmp_path / "a.py").read_text() == "x = 1\n"
        assert not (tmp_path / "b.py").exists()
        assert state.latest_snapshot() is None


def test_semantically_invalid_batch_leaves_every_file_untouched(tmp_path):
    original = {
        "lib.py": "def leaf(value): return value\n",
        "app.py": "from lib import leaf\ndef root(): return leaf(1)\n",
    }
    for name, content in original.items():
        (tmp_path / name).write_bytes(content.encode())
    with StateStore(tmp_path / ".banger/state.db") as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path))
        with pytest.raises(ValueError, match="semantic"):
            editor.apply_changes(
                {
                    "lib.py": "def leaf(value, extra): return value + extra\n",
                    "app.py": "from lib import leaf\ndef root(): return leaf(2)\n",
                }
            )
        assert all(
            (tmp_path / name).read_bytes() == text.encode() for name, text in original.items()
        )
        assert state.latest_snapshot() is None


def test_batch_io_failure_restores_previously_written_files(tmp_path, monkeypatch):
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text("old")
    with StateStore(tmp_path / ".banger/state.db") as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path))
        atomic = editor._atomic

        def fail_second(path, content):
            if path.name == "b.txt" and content == b"new":
                raise OSError("injected write failure")
            atomic(path, content)

        monkeypatch.setattr(editor, "_atomic", fail_second)
        with pytest.raises(OSError, match="injected"):
            editor.apply_changes({"a.txt": "new", "b.txt": "new"})
        assert all((tmp_path / name).read_text() == "old" for name in ("a.txt", "b.txt"))
        assert state.latest_snapshot() is None


@pytest.mark.parametrize("external_change", [False, True])
def test_incomplete_batch_recovery_preserves_unrelated_changes(tmp_path, external_change):
    first, second = tmp_path / "a.txt", tmp_path / "b.txt"
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.snapshot_many([(str(first), b"old", b"new"), (str(second), b"old", b"new")])
    first.write_bytes(b"new")
    second.write_bytes(b"external" if external_change else b"old")
    with StateStore(tmp_path / ".banger/state.db") as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path))
        assert first.read_bytes() == b"new"
        assert second.read_bytes() == (b"external" if external_change else b"old")
        assert state.pending_snapshots() == []
        if external_change:
            assert state.latest_snapshot() is None
        else:
            assert state.latest_snapshot()["status"] == "incomplete"
            editor.rollback()
            assert first.read_bytes() == second.read_bytes() == b"old"


async def test_batch_approvals_finish_before_any_write(tmp_path):
    approved = []

    async def approve(action, detail):
        approved.append(action.path)
        assert not (tmp_path / "a.txt").exists()
        return "allow" if len(approved) == 1 else "deny"

    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ASK), approve)
        result = await toolbox.invoke(
            "apply_edits", {"edits_json": json.dumps({"a.txt": "one", "b.txt": "two"})}
        )
        assert len(approved) == 2
        assert "error" in result
        assert not (tmp_path / "a.txt").exists()
        assert not (tmp_path / "b.txt").exists()


async def test_grouped_create_delete_and_undo_authorize_every_path(tmp_path):
    (tmp_path / "old.txt").write_bytes(b"\xff\r\n")
    approved = []

    async def approve(action, detail):
        approved.append(action.path)
        return "allow"

    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ASK), approve)
        result = await toolbox.invoke(
            "apply_edits", {"edits_json": json.dumps({"old.txt": None, "new.txt": "created"})}
        )
        assert "batch" in result
        assert not (tmp_path / "old.txt").exists()
        assert (tmp_path / "new.txt").read_text() == "created"
        restored = await toolbox.invoke("rollback_edit", {})
        assert len(restored["restored"]) == 2
        assert len(approved) == 4
        assert (tmp_path / "old.txt").read_bytes() == b"\xff\r\n"
        assert not (tmp_path / "new.txt").exists()


async def test_denied_group_undo_leaves_all_applied_files(tmp_path):
    approved = []

    async def approve(action, detail):
        approved.append(action.path)
        assert (tmp_path / "a.txt").read_text() == "one"
        return "allow" if len(approved) == 1 else "deny"

    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ASK), approve)
        toolbox.editor.apply_changes({"a.txt": "one", "b.txt": "two"})
        result = await toolbox.invoke("rollback_edit", {})
        assert len(approved) == 2
        assert "error" in result
        assert (tmp_path / "a.txt").read_text() == "one"
        assert (tmp_path / "b.txt").read_text() == "two"
        assert state.latest_snapshot()["status"] == "applied"


def test_failed_group_undo_restores_the_applied_state(tmp_path, monkeypatch):
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text("old")
    with StateStore(tmp_path / ".banger/state.db") as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path))
        editor.apply_changes({"a.txt": "new", "b.txt": "new"})
        atomic = editor._atomic

        def fail_second(path, content):
            if path.name == "b.txt" and content == b"old":
                raise OSError("undo failed")
            atomic(path, content)

        monkeypatch.setattr(editor, "_atomic", fail_second)
        with pytest.raises(OSError, match="undo failed"):
            editor.rollback()
        assert all((tmp_path / name).read_text() == "new" for name in ("a.txt", "b.txt"))
        assert state.latest_snapshot()["status"] == "applied"
