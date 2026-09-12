import pytest

from banger.edits import Editor
from banger.index import CodeIndex
from banger.state import StateStore


@pytest.fixture
def editor(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        yield Editor(tmp_path, state, CodeIndex(tmp_path, state))


def test_unrelated_name_candidate_does_not_hide_removed_call_target(editor, tmp_path):
    source = "def leaf(): return 1\ndef root(): return leaf()\n"
    (tmp_path / "main.py").write_text(source)
    (tmp_path / "unrelated.py").write_text("def leaf(): return 99\n")
    with pytest.raises(ValueError, match="semantic"):
        editor.replace("main.py", "def leaf()", "def renamed()")
    assert (tmp_path / "main.py").read_text() == source
    assert editor.state.latest_snapshot() is None


def test_deleting_imported_project_module_is_not_treated_as_external_library(editor, tmp_path):
    source = "def leaf(): return 1\n"
    (tmp_path / "lib.py").write_text(source)
    (tmp_path / "main.py").write_text("from lib import leaf\ndef root(): return leaf()\n")
    with pytest.raises(ValueError, match="semantic"):
        editor.delete("lib.py")
    assert (tmp_path / "lib.py").read_text() == source
    assert editor.state.latest_snapshot() is None


def test_existing_unknown_in_same_named_nested_caller_does_not_block_unrelated_edit(
    editor, tmp_path
):
    (tmp_path / "lib.py").write_text("def leaf(): return 1\n")
    (tmp_path / "main.py").write_text(
        "def first():\n from lib import leaf as chosen\n def root(): return chosen()\n"
        "def second():\n def root(): return chosen()\n"
    )
    changed = editor.replace("lib.py", "return 1", "return 2")
    assert changed["semantic_gate"]["regressions"] == []


def test_existing_arity_error_does_not_mask_new_error_in_other_nested_caller(editor, tmp_path):
    source = (
        "def leaf(x): return x\n"
        "def first():\n def root(): return leaf()\n"
        "def second():\n def root(): return leaf(1)\n"
    )
    (tmp_path / "main.py").write_text(source)
    with pytest.raises(ValueError, match="semantic"):
        editor.replace("main.py", "leaf(1)", "leaf()")
    assert (tmp_path / "main.py").read_text() == source


def test_existing_arity_error_does_not_mask_an_additional_bad_call(editor, tmp_path):
    source = "def leaf(x): return x\ndef root():\n leaf()\n leaf(1)\n"
    (tmp_path / "main.py").write_text(source)
    with pytest.raises(ValueError, match="semantic"):
        editor.replace("main.py", "leaf(1)", "leaf()")
    assert (tmp_path / "main.py").read_text() == source


def test_new_ambiguity_with_original_target_still_present_is_not_a_known_break(editor, tmp_path):
    (tmp_path / "sample.cpp").write_text(
        "int leaf() { return 1; }\nint root() { return leaf(); }\n"
    )
    changed = editor.write(
        "sample.cpp",
        "int leaf() { return 1; }\nint leaf(int x) { return x; }\nint root() { return leaf(); }\n",
    )
    assert changed["semantic_gate"]["regressions"] == []


def test_explicit_switch_to_external_import_can_replace_project_module(editor, tmp_path):
    (tmp_path / "lib.py").write_text("def sqrt(x): return x\n")
    (tmp_path / "main.py").write_text("from lib import sqrt\ndef root(): return sqrt(4)\n")
    changed = editor.apply_changes(
        {"lib.py": None, "main.py": "from math import sqrt\ndef root(): return sqrt(4)\n"}
    )
    assert changed["semantic_gate"]["regressions"] == []
    assert not (tmp_path / "lib.py").exists()
