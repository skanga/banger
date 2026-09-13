import pytest

from banger.index import CodeIndex
from banger.state import StateStore


@pytest.mark.parametrize(
    "body,expression",
    [
        ("struct { Parent; named Parent }", "Parent"),
        ('struct { *Parent `json:"parent"` }', "*Parent"),
        ("struct { Parent[int] }", "Parent[int]"),
        ("interface { Parent; Read() error }", "Parent"),
    ],
)
def test_go_embedding_local_and_restart(tmp_path, body, expression):
    parent = "Parent[T any]" if "[int]" in body else "Parent"
    parent_body = "interface {}" if body.startswith("interface") else "struct {}"
    (tmp_path / "main.go").write_text(
        f"package sample\ntype {parent} {parent_body}\ntype Child {body}\n",
        encoding="utf-8",
    )
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        result = index.get_hierarchy("Child")
        assert result["bases"] == [expression]
        link = result["base_links"][0]
        assert link["relationship"] == "embedding"
        assert link["targets"] == ["main.go:2:Parent"]
        assert link["resolution"] == "resolved"
        assert [s["name"] for s in index.get_hierarchy("Parent")["subclasses"]] == ["Child"]
    with StateStore(tmp_path / ".banger/state.db") as state:
        restored = CodeIndex(tmp_path, state)
        restored.refresh()
        assert restored.get_hierarchy("Child") == result


def test_go_embedding_package_and_aliased_import(tmp_path):
    (tmp_path / "go.mod").write_text("module example/app\n", encoding="utf-8")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/base.go").write_text("package library\ntype Parent struct {}\n")
    (tmp_path / "local.go").write_text("package sample\ntype Local struct {}\n")
    (tmp_path / "main.go").write_text(
        'package sample\nimport alias "example/app/lib"\ntype Child struct { Local; *alias.Parent }\n'
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    links = index.get_hierarchy("Child")["base_links"]
    assert [link["targets"] for link in links] == [["local.go:2:Local"], ["lib/base.go:2:Parent"]]
    assert all(link["resolution"] == "resolved" for link in links)


@pytest.mark.parametrize(
    "other,body",
    [
        ("package other\ntype Parent struct {}\n", "struct { Parent }"),
        ("//go:build special\npackage sample\ntype Parent struct {}\n", "struct { Parent }"),
        ("package sample\ntype Parent struct {}\n", "struct { missing.Parent }"),
    ],
)
def test_go_embedding_uncertainty(tmp_path, other, body):
    (tmp_path / "other.go").write_text(other)
    (tmp_path / "main.go").write_text(f"package sample\ntype Child {body}\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    result = index.get_hierarchy("Child")
    assert result["bases"]
    assert result["base_links"][0]["resolution"] != "resolved"


def test_go_constraint_union_is_not_multiple_embedding_edges(tmp_path):
    (tmp_path / "main.go").write_text("package sample\ntype Number interface { ~int | ~float64 }\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    result = index.get_hierarchy("Number")
    assert result["bases"] == ["~int | ~float64"]
    assert result["base_links"][0]["resolution"] == "unknown"
    assert result["base_links"][0]["targets"] == []


def test_go_default_import_uses_declared_package_name(tmp_path):
    (tmp_path / "go.mod").write_text("module example/app\n")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/base.go").write_text("package library\ntype Parent struct {}\n")
    (tmp_path / "main.go").write_text(
        'package sample\nimport "example/app/lib"\ntype Child struct { library.Parent }\n'
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["targets"] == ["lib/base.go:2:Parent"]
    assert link["resolution"] == "resolved"


def test_go_duplicate_embedding_target_and_refresh(tmp_path):
    (tmp_path / "base.go").write_text("package sample\ntype Parent struct {}\n")
    (tmp_path / "main.go").write_text(
        "package sample\ntype Parent struct {}\ntype Child struct { Parent }\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "ambiguous"
    assert set(link["targets"]) == {"base.go:2:Parent", "main.go:2:Parent"}
    assert index.get_hierarchy("base.go:2:Parent")["subclasses"] == []
    (tmp_path / "base.go").write_text("package sample\n")
    index.refresh()
    assert index.get_hierarchy("Child")["base_links"][0]["resolution"] == "resolved"


@pytest.mark.parametrize(
    "source",
    [
        "package sample\ntype Parent struct {}\ntype Child[Parent any] struct { Parent }\n",
        "package sample\ntype Parent struct {}\nfunc f() { type Child struct { Parent } }\n",
        'package sample\nimport . "example/other"\ntype Parent struct {}\ntype Child struct { Parent }\n',
    ],
)
def test_go_unproven_embedding_scopes(tmp_path, source):
    (tmp_path / "main.go").write_text(source)
    index = CodeIndex(tmp_path)
    index.refresh()
    assert index.get_hierarchy("Child")["base_links"][0]["resolution"] == "unknown"
