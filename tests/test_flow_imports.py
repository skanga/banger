import pytest

from banger.analysis import FlowAnalysis
from banger.index import CodeIndex
from banger.state import StateStore


@pytest.mark.parametrize(
    "case", ["module", "src", "relative", "reexport", "local", "shadow", "parameter"]
)
def test_imported_value_flow_and_restart(tmp_path, case):
    library = "src/lib.py" if case == "src" else "pkg/lib.py" if case == "relative" else "lib.py"
    app = "pkg/app.py" if case == "relative" else "app.py"
    path = tmp_path / library
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def source(): return 7\nvalue = source()\n")
    imported = ".lib" if case == "relative" else "bridge" if case == "reexport" else "lib"
    if case == "relative":
        (tmp_path / "pkg/__init__.py").write_text("")
    if case == "reexport":
        (tmp_path / "bridge.py").write_text("from lib import value\n")
    declaration = f"from {imported} import value as chosen\n"
    body = "def consume(item): return item\n"
    if case == "local":
        body += "def caller():\n " + declaration + " return consume(chosen)\n"
    else:
        body += declaration + (
            "def caller(chosen):\n" if case == "parameter" else "def caller():\n"
        )
        body += " chosen = 99\n" if case == "shadow" else ""
        body += " return consume(chosen)\n"
    (tmp_path / app).write_text(body)
    database = tmp_path / ".banger/state.db"
    with StateStore(database) as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        flow = FlowAnalysis(index)
        graph = flow.backflow("consume", "item")["graph"]
        source = index.get_definition("source")["id"]
        reaches = case not in {"shadow", "parameter"}
        assert any(n.get("symbol") == source for n in graph["nodes"]) == reaches
        target = index.get_definition("consume")["id"]
        assert (
            any(n.get("symbol") == target for n in flow.forwardflow("source")["graph"]["nodes"])
            == reaches
        )
        if reaches:
            edges = [e for e in graph["edges"] if e.get("kind") == "import binding"]
            assert edges and all(e["resolution"] == "resolved" for e in edges)
    with StateStore(database) as state:
        reopened = CodeIndex(tmp_path, state)
        reopened.refresh()
        assert FlowAnalysis(reopened).backflow("consume", "item")["graph"] == graph


def test_ambiguous_import_layout_retains_both_value_origins(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "lib.py").write_text("value = 7\n")
    (tmp_path / "src/lib.py").write_text("value = 9\n")
    (tmp_path / "app.py").write_text(
        "from lib import value\ndef consume(item): return item\ndef caller(): return consume(value)\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).backflow("consume", "item")["graph"]
    assert {n["expression"] for n in graph["nodes"] if n.get("expression") in {"7", "9"}} == {
        "7",
        "9",
    }
    imports = [e for e in graph["edges"] if e.get("kind") == "import binding"]
    assert len(imports) == 2 and all(e["resolution"] == "ambiguous" for e in imports)


def test_package_reexport_default_origin_refreshes_after_source_edit(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/__init__.py").write_text("from .constants import value\n")
    source = tmp_path / "pkg/constants.py"
    source.write_text("value = 7\n")
    (tmp_path / "app.py").write_text(
        "from pkg import value\ndef consume(item=value): return item\nconsume()\n"
    )
    index = CodeIndex(tmp_path)
    for expected in ("7", "9"):
        source.write_text(f"value = {expected}\n")
        index.refresh()
        graph = FlowAnalysis(index).backflow("consume", "item")["graph"]
        assert {n["expression"] for n in graph["nodes"] if n.get("expression") in {"7", "9"}} == {
            expected
        }
        assert any(e.get("kind") == "default argument" for e in graph["edges"])


def test_cyclic_reexports_keep_origins_without_unbounded_traversal(tmp_path):
    (tmp_path / "a.py").write_text("from b import value\nvalue = 7\n")
    (tmp_path / "b.py").write_text("from a import value\n")
    (tmp_path / "app.py").write_text(
        "from b import value\ndef consume(item): return item\nconsume(value)\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).backflow("consume", "item")["graph"]
    assert any(n.get("expression") == "7" for n in graph["nodes"])
    assert len([e for e in graph["edges"] if e.get("kind") == "import binding"]) == 3
    assert not graph["truncated"]
