import pytest

from banger.index import CodeIndex

SAMPLES = {
    "a.py": "def leaf(x):\n    return x\ndef root():\n    return leaf(1)\n",
    "a.js": "function leaf(x) { return x; } function root() { return leaf(1); }",
    "a.ts": "function leaf(x: number) { return x; } function root() { return leaf(1); }",
    "A.java": "class A { static int leaf(int x) { return x; } int root() { return leaf(1); } }",
    "A.cs": "class A { static int leaf(int x) { return x; } int root() { return leaf(1); } }",
    "a.cpp": "int leaf(int x) { return x; } int root() { return leaf(1); }",
    "a.c": "int leaf(int x) { return x; } int root() { return leaf(1); }",
    "a.go": "package main\nfunc leaf(x int) int { return x }; func root() int { return leaf(1) }",
    "a.rs": "fn leaf(x: i32) -> i32 { x } fn root() -> i32 { leaf(1) }",
    "a.rb": "def leaf(x)\n x\nend\ndef root\n leaf(1)\nend\n",
}


@pytest.mark.parametrize("filename,source", SAMPLES.items())
def test_each_language_indexes_definitions_and_local_calls(tmp_path, filename, source):
    (tmp_path / filename).write_text(source)
    index = CodeIndex(tmp_path)
    index.refresh()
    leaf = index.search_symbols("leaf")[0]
    root = index.search_symbols("root")[0]
    assert leaf["path"] == filename
    callers = index.get_callers(leaf["id"])
    assert any(c["caller"] == root["id"] and c["resolution"] == "resolved" for c in callers)
    assert index.trace_path(root["id"], leaf["id"]) == [root["id"], leaf["id"]]


def test_cross_file_ambiguity_and_import_resolution(tmp_path):
    (tmp_path / "a.py").write_text("def same():\n return 1\n")
    (tmp_path / "b.py").write_text("def same():\n return 2\n")
    (tmp_path / "main.py").write_text(
        "from a import same as selected\nimport json\n"
        "def root():\n selected()\n same()\n json.dumps({})\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    calls = index.profile(index.search_symbols("root")[0]["id"])["calls"]
    selected = next(c for c in calls if c["name"] == "selected")
    ambiguous = next(c for c in calls if c["name"] == "same")
    external = next(c for c in calls if c["name"] == "json.dumps")
    assert selected["resolution"] == "resolved"
    assert selected["targets"][0].startswith("a.py:")
    assert ambiguous["resolution"] == "ambiguous"
    assert len(ambiguous["targets"]) == 2
    assert external["resolution"] == "external"


def test_changes_deletions_exclusions_and_syntax_errors(tmp_path):
    path = tmp_path / "a.py"
    path.write_text(SAMPLES["a.py"])
    ignored = tmp_path / ".venv"
    ignored.mkdir()
    (ignored / "bad.py").write_text("def ignored(): pass")
    index = CodeIndex(tmp_path)
    index.refresh()
    assert len(index.search_symbols("")) == 2
    path.write_text("def replacement(): pass")
    index.refresh()
    assert not index.search_symbols("leaf")
    assert index.search_symbols("replacement")
    assert index.syntax_errors("a.py", b"def broken(:")
    path.unlink()
    index.refresh()
    assert index.search_symbols("") == []


def test_python_hierarchy_and_cycle_safe_call_tree(tmp_path):
    (tmp_path / "a.py").write_text(
        "class Base: pass\nclass Child(Base): pass\ndef a(): b()\ndef b(): a()\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    base = index.search_symbols("Base")[0]
    assert index.get_hierarchy(base["id"])["subclasses"][0]["name"] == "Child"
    a = index.search_symbols("a")
    a = next(s for s in a if s["name"] == "a")
    assert len(index.call_tree(a["id"])["edges"]) == 2


def test_python_method_name_is_not_a_lexical_global(tmp_path):
    (tmp_path / "a.py").write_text(
        "class A:\n def leaf(self): return 1\n def root(self): return leaf()\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    assert index.profile("root")["calls"][0]["resolution"] != "resolved"


def test_python_local_import_does_not_leak_to_other_functions(tmp_path):
    (tmp_path / "a.py").write_text("def leaf(): return 1\n")
    (tmp_path / "main.py").write_text(
        "def root():\n from a import leaf as local\n return local()\ndef other(): return local()\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    assert index.profile("root")["calls"][0]["resolution"] == "resolved"
    assert index.profile("other")["calls"][0]["resolution"] == "unknown"


def test_python_src_layout_import_and_missing_member(tmp_path):
    package = tmp_path / "src" / "package"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "lib.py").write_text("def leaf(): return 1\n")
    (tmp_path / "main.py").write_text(
        "from package.lib import leaf, missing\ndef root():\n leaf()\n missing()\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    calls = {c["name"]: c for c in index.profile("root")["calls"]}
    assert calls["leaf"]["targets"] == [index.get_definition("leaf")["id"]]
    assert calls["leaf"]["resolution"] == "resolved"
    assert calls["missing"]["resolution"] == "unknown"
    preview = index.preview_change(package / "lib.py", b"def renamed(): return 1\n")
    assert [c["name"] for c in preview["regressions"]] == ["leaf"]


def test_python_import_search_root_ambiguity(tmp_path):
    (tmp_path / "src").mkdir()
    for path in [tmp_path / "lib.py", tmp_path / "src/lib.py"]:
        path.write_text("def leaf(): return 1\n")
    (tmp_path / "main.py").write_text("from lib import leaf\ndef root(): leaf()\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    call = index.profile("root")["calls"][0]
    assert call["resolution"] == "ambiguous"
    assert len(call["targets"]) == 2


def test_python_missing_import_member_is_not_external_or_nested_method(tmp_path):
    (tmp_path / "lib.py").write_text("class Library:\n def missing(self): pass\n")
    (tmp_path / "main.py").write_text("from lib import missing\ndef root(): missing()\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    call = index.profile("root")["calls"][0]
    assert call["resolution"] == "unknown"
    assert call["targets"] == []
