import pytest

from banger.edits import Editor
from banger.index import CodeIndex
from banger.state import StateStore


def snapshot_status(state, identity):
    return state.db.execute("SELECT status FROM snapshots WHERE id=?", (identity,)).fetchone()[0]


@pytest.mark.parametrize("before,after", [(b"old\r\n", b"new\n"), (None, b"new"), (b"old", None)])
def test_interrupted_undo_recovers_and_exposes_older_history(tmp_path, monkeypatch, before, after):
    database = tmp_path / ".banger/state.db"
    path = tmp_path / "file.txt"
    with StateStore(database) as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path, state))
        older = editor.write("older.txt", "older")["snapshot"]
        if before is not None:
            path.write_bytes(before)
        result = (
            editor.delete("file.txt") if after is None else editor.write("file.txt", after.decode())
        )
        atomic = editor._atomic

        def interrupted(target, content):
            atomic(target, content)
            raise KeyboardInterrupt("simulated process interruption")

        monkeypatch.setattr(editor, "_atomic", interrupted)
        with pytest.raises(KeyboardInterrupt):
            editor.rollback()

    with StateStore(database) as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path, state))
        assert (path.read_bytes() if path.exists() else None) == before
        assert snapshot_status(state, result["snapshot"]) == "rolled-back"
        assert state.latest_snapshot()["id"] == older
        editor.rollback()
        assert not (tmp_path / "older.txt").exists()


@pytest.mark.parametrize(
    "current,status", [(b"old", "rolled-back"), (b"new", "applied"), (b"user", "conflict")]
)
def test_startup_classifies_pending_undo_without_writing(tmp_path, monkeypatch, current, status):
    path = tmp_path / "file.txt"
    path.write_bytes(current)
    with StateStore(tmp_path / ".banger/state.db") as state:
        identity = state.snapshot(str(path), b"old", b"new", status="pending-rollback")

        def forbidden(*args):
            pytest.fail("startup must not rewrite source")

        monkeypatch.setattr(Editor, "_atomic", forbidden)
        Editor(tmp_path, state, CodeIndex(tmp_path, state))
        assert snapshot_status(state, identity) == status
        assert path.read_bytes() == current
        assert (state.latest_snapshot() is not None) == (status == "applied")


@pytest.mark.parametrize("failure_stage", ["before", "after", "conflict"])
def test_undo_write_failure_classifies_actual_bytes(tmp_path, monkeypatch, failure_stage):
    path = tmp_path / "file.txt"
    path.write_bytes(b"old")
    with StateStore(tmp_path / ".banger/state.db") as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path, state))
        identity = editor.write("file.txt", "new")["snapshot"]
        atomic = editor._atomic

        def failed(target, content):
            if failure_stage == "after":
                atomic(target, content)
            elif failure_stage == "conflict":
                target.write_bytes(b"user")
            raise OSError("simulated write failure")

        monkeypatch.setattr(editor, "_atomic", failed)
        with pytest.raises(OSError, match="simulated"):
            editor.rollback()
        expected = {
            "before": ("applied", b"new"),
            "after": ("rolled-back", b"old"),
            "conflict": ("conflict", b"user"),
        }
        status, content = expected[failure_stage]
        assert snapshot_status(state, identity) == status
        assert path.read_bytes() == content
        if failure_stage == "before":
            monkeypatch.setattr(editor, "_atomic", atomic)
            editor.rollback()
            assert path.read_bytes() == b"old"
