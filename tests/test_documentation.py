import pytest

from banger.index import CodeIndex
from banger.state import StateStore


@pytest.mark.parametrize(
    "filename,source",
    [
        ("a.py", 'def leaf():\n    """Return the answer."""\n    return 42\n'),
        ("a.js", "/** Return the answer. */\nexport function leaf() { return 42; }"),
        ("a.ts", "/** Return the answer. */\nexport const leaf = () => 42;"),
        ("A.java", "class A {\n/** Return the answer. */\nstatic int leaf() { return 42; }\n}"),
        ("A.cs", "class A {\n/// Return the answer.\nstatic int leaf() { return 42; }\n}"),
        ("a.cpp", "/** Return the answer. */\nint leaf() { return 42; }"),
        ("a.c", "/* Return the answer. */\nint leaf() { return 42; }"),
        ("a.go", "package a\n// Return the answer.\nfunc leaf() int { return 42 }"),
        ("a.rs", "/// Return the answer.\nfn leaf() -> i32 { 42 }"),
        ("a.rb", "# Return the answer.\ndef leaf\n 42\nend"),
    ],
)
def test_declaration_documentation_in_each_language(tmp_path, filename, source):
    (tmp_path / filename).write_text(source)
    index = CodeIndex(tmp_path)
    index.refresh()
    definition = index.get_definition("leaf")
    assert "Return the answer." in definition["documentation"]
    assert "Return the answer." in index.profile("leaf")["definition"]["documentation"]


def test_python_decorated_class_and_async_docs_survive_restart(tmp_path):
    path = tmp_path / "a.py"
    path.write_text(
        'class A:\n    """A documented class."""\n'
        '    @staticmethod\n    async def leaf():\n        """A documented method."""\n'
    )
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        assert index.refresh()["changed"] == 0
        assert index.get_definition("A")["documentation"] == "A documented class."
        assert index.get_definition("leaf")["documentation"] == "A documented method."


def test_comments_are_attached_only_to_adjacent_declarations(tmp_path):
    (tmp_path / "a.js").write_text(
        "// Detached comment\n\nfunction first() {}\n"
        "const value = 1; // About value\nfunction second() {}\n"
        "// Summary\n// Details\nfunction third() {}\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    assert index.get_definition("first")["documentation"] == ""
    assert index.get_definition("second")["documentation"] == ""
    assert "Summary" in index.get_definition("third")["documentation"]
    assert "Details" in index.get_definition("third")["documentation"]
