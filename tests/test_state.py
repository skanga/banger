import sqlite3

import pytest

from banger.state import StateStore


def test_sessions_memory_and_artifacts_survive_reopening(tmp_path):
    db = tmp_path / "state.db"
    store = StateStore(db)
    session = store.new_session("Fix parser")
    store.append(session, {"role": "user", "content": "Fix this"})
    store.set_memory("convention", "Use tabs")
    store.put_artifact("trace", "last", {"calls": ["parse"]})
    store.close()
    with StateStore(db) as reopened:
        assert reopened.sessions()[0]["id"] == session
        assert reopened.messages(session) == [{"role": "user", "content": "Fix this"}]
        assert reopened.memories() == {"convention": "Use tabs"}
        assert reopened.artifact("trace", "last") == {"calls": ["parse"]}


def test_messages_remain_ordered_and_sessions_are_isolated(tmp_path):
    with StateStore(tmp_path / "state.db") as store:
        first, second = store.new_session("one"), store.new_session("two")
        for n in range(12):
            store.append(first, {"n": n})
        store.append(second, {"other": True})
        assert store.messages(first) == [{"n": n} for n in range(12)]
        assert store.messages(second) == [{"other": True}]
        with pytest.raises(KeyError):
            store.append("missing", {"n": 1})


def test_snapshot_preserves_binary_content_and_creation(tmp_path):
    with StateStore(tmp_path / "state.db") as store:
        edit = store.snapshot("a.py", b"\xff\r\n", b"new")
        assert store.latest_snapshot()["before"] == b"\xff\r\n"
        store.finish_snapshot(edit, "rolled-back")
        assert store.latest_snapshot() is None
        store.snapshot("new.py", None, b"created")
        assert store.latest_snapshot()["before"] is None


def test_pending_snapshot_is_recovered_after_completed_atomic_write(tmp_path):
    from banger.edits import Editor
    from banger.index import CodeIndex

    db = tmp_path / "state.db"
    path = tmp_path / "file.txt"
    with StateStore(db) as state:
        state.snapshot(str(path), b"old", b"new", status="pending")
    path.write_bytes(b"new")
    with StateStore(db) as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path))
        editor.rollback()
        assert path.read_bytes() == b"old"


def test_existing_snapshot_schema_is_migrated_without_losing_undo(tmp_path):
    path = tmp_path / "state.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "path TEXT NOT NULL, before BLOB, after BLOB, status TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO snapshots(path,before,after,status) VALUES (?,?,?,?)",
            ("old.txt", b"original", b"changed", "applied"),
        )
    with StateStore(path) as state:
        snapshot = state.latest_snapshot()
        assert snapshot["before"] == b"original"
        assert snapshot["after"] == b"changed"
        assert snapshot["batch"] is None
