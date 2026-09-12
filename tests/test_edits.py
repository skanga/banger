import pytest

from banger.edits import Editor
from banger.index import CodeIndex
from banger.state import StateStore


@pytest.fixture
def editor(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        yield Editor(tmp_path, state, index)


def test_invalid_python_edit_preserves_original_bytes(editor, tmp_path):
    path = tmp_path / "a.py"
    original = b"def f():\r\n    return 1\r\n"
    path.write_bytes(original)
    with pytest.raises(ValueError, match="syntax"):
        editor.write("a.py", "def f(:")
    assert path.read_bytes() == original
    assert editor.state.latest_snapshot() is None


def test_edit_diff_and_rollback_survive_restart(editor, tmp_path):
    path = tmp_path / "a.py"
    path.write_text("def f(): return 1\n")
    result = editor.replace("a.py", "return 1", "return 2")
    assert "-def f(): return 1" in result["diff"]
    with StateStore(tmp_path / ".banger/state.db") as state:
        reopened = Editor(tmp_path, state, CodeIndex(tmp_path))
        reopened.rollback()
    assert path.read_text() == "def f(): return 1\n"


def test_rollback_refuses_to_overwrite_subsequent_user_changes(editor, tmp_path):
    editor.write("a.py", "x = 1\n")
    (tmp_path / "a.py").write_text("x = 99\n")
    with pytest.raises(ValueError, match="changed"):
        editor.rollback()
    assert (tmp_path / "a.py").read_text() == "x = 99\n"


def test_create_delete_and_repeated_text(editor, tmp_path):
    editor.write("new.py", "x = 1\n")
    editor.rollback()
    assert not (tmp_path / "new.py").exists()
    (tmp_path / "a.txt").write_text("twice twice")
    with pytest.raises(ValueError, match="exactly once"):
        editor.replace("a.txt", "twice", "once")
    editor.delete("a.txt")
    assert not (tmp_path / "a.txt").exists()
    editor.rollback()
    assert (tmp_path / "a.txt").read_text() == "twice twice"


def test_semantic_gate_reverts_removal_of_a_still_called_definition(editor, tmp_path):
    source = "def leaf(): return 1\ndef root(): return leaf()\n"
    (tmp_path / "a.py").write_text(source)
    with pytest.raises(ValueError, match="semantic"):
        editor.replace("a.py", "def leaf()", "def renamed()")
    assert (tmp_path / "a.py").read_text() == source
    assert editor.state.latest_snapshot() is None


def test_semantic_gate_allows_coordinated_rename(editor, tmp_path):
    (tmp_path / "a.py").write_text("def leaf(): return 1\ndef root(): return leaf()\n")
    editor.write("a.py", "def renamed(): return 1\ndef root(): return renamed()\n")
    assert "renamed" in (tmp_path / "a.py").read_text()


def test_semantic_gate_rejects_new_required_argument_for_existing_call(editor, tmp_path):
    original = "def leaf(value): return value\ndef root(): return leaf(1)\n"
    (tmp_path / "a.py").write_text(original)
    with pytest.raises(ValueError, match="semantic"):
        editor.replace("a.py", "leaf(value)", "leaf(value, extra)")
    assert (tmp_path / "a.py").read_text() == original


def test_semantic_gate_accepts_new_optional_argument(editor, tmp_path):
    (tmp_path / "a.py").write_text("def leaf(value): return value\ndef root(): return leaf(1)\n")
    editor.replace("a.py", "leaf(value)", "leaf(value, extra=0)")
    assert "extra=0" in (tmp_path / "a.py").read_text()


def test_edit_reports_consumers_and_relevant_tests_before_and_after(editor, tmp_path):
    (tmp_path / "lib.py").write_text("def leaf(value): return value - 1\n")
    (tmp_path / "app.py").write_text(
        "from lib import leaf\ndef calculate():\n result = leaf(3)\n return result\n"
    )
    (tmp_path / "test_app.py").write_text(
        "from app import calculate\ndef test_calculate():\n assert calculate() == 4\n"
        "def test_unrelated():\n assert True\n"
    )
    result = editor.write("lib.py", "# Fixed calculation\ndef leaf(value): return value + 1\n")
    for phase in ("impact_before", "impact_after"):
        report = result[phase][0]
        assert report["definition"]["name"] == "leaf"
        assert report["callers"][0]["name"] == "leaf"
        assert report["value_consumers"][0]["holder"] == "result"
        assert [test["name"] for test in report["relevant_tests"]] == ["test_calculate"]
    assert result["impact_before"][0]["definition"]["line"] == 1
    assert result["impact_after"][0]["definition"]["line"] == 2
    with StateStore(tmp_path / ".banger/state.db") as state:
        saved = state.artifact("edit-impact", str(result["snapshot"]))
        assert saved["before"] == result["impact_before"]
        assert saved["after"] == result["impact_after"]


def test_create_and_delete_have_explicit_empty_impact_sides(editor):
    created = editor.write("new.py", "def new_function(): pass\n")
    assert created["impact_before"] == []
    assert created["impact_after"][0]["definition"]["name"] == "new_function"
    deleted = editor.delete("new.py")
    assert deleted["impact_before"][0]["definition"]["name"] == "new_function"
    assert deleted["impact_after"] == []
