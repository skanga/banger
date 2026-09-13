import pytest

from banger.analysis import FlowAnalysis
from banger.index import CodeIndex
from banger.state import StateStore


@pytest.mark.parametrize(
    "declaration,expression,parameter,reaches",
    [
        ("import settings", "settings.VALUE", "", True),
        ("import settings as config", "config.VALUE + 1", "", True),
        ("import pkg.settings", "pkg.settings.VALUE", "", True),
        ("import pkg.settings as config", "config.VALUE", "", True),
        ("import settings", "settings.VALUE", "settings", False),
        ("import settings", "'settings.VALUE'", "", False),
        ("import settings", "lambda settings: settings.VALUE", "", False),
        ("import settings", "[settings.VALUE for settings in []]", "", False),
        ("import settings", "lambda captured=settings.VALUE: captured", "", True),
    ],
)
def test_module_attribute_flow_respects_import_and_expression_scope(
    tmp_path, declaration, expression, parameter, reaches
):
    library = "pkg/settings.py" if "pkg.settings" in declaration else "settings.py"
    target = tmp_path / library
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def source(): return 7\nVALUE = source()\n")
    (tmp_path / "app.py").write_text(
        f"{declaration}\ndef consume(item): return item\ndef caller({parameter}):\n return consume({expression})\n"
    )
    database = tmp_path / ".banger/state.db"
    with StateStore(database) as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        graph = FlowAnalysis(index).backflow("consume", "item")["graph"]
        source = index.get_definition("source")["id"]
        assert any(n.get("symbol") == source for n in graph["nodes"]) == reaches
        consumer = index.get_definition("consume")["id"]
        forward = FlowAnalysis(index).forwardflow("source")["graph"]
        assert any(n.get("symbol") == consumer for n in forward["nodes"]) == reaches
        if reaches:
            edges = [e for e in graph["edges"] if e.get("kind") == "module attribute"]
            assert edges and all(e["resolution"] == "resolved" for e in edges)
    with StateStore(database) as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        assert FlowAnalysis(index).backflow("consume", "item")["graph"] == graph


@pytest.mark.parametrize("case", ["local", "closure", "default", "shadow", "ambiguous"])
def test_module_attribute_scope_defaults_and_candidate_layouts(tmp_path, case):
    (tmp_path / "settings.py").write_text("VALUE = 7\n")
    if case == "ambiguous":
        (tmp_path / "src").mkdir()
        (tmp_path / "src/settings.py").write_text("VALUE = 9\n")
    source = "def consume(item): return item\n"
    if case == "local":
        source += "def caller():\n import settings\n return consume(settings.VALUE)\n"
    elif case == "closure":
        source += "def outer():\n import settings\n def inner(): return consume(settings.VALUE)\n return inner()\n"
    elif case == "default":
        source = "import settings\ndef consume(item=settings.VALUE): return item\nconsume()\n"
    else:
        source += "import settings\ndef caller():\n"
        if case == "shadow":
            source += " settings = object()\n"
        source += " return consume(settings.VALUE)\n"
    (tmp_path / "app.py").write_text(source)
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).backflow("consume", "item")["graph"]
    values = {n["expression"] for n in graph["nodes"] if n.get("expression") in {"7", "9"}}
    assert values == (set() if case == "shadow" else {"7", "9"} if case == "ambiguous" else {"7"})
    if case == "ambiguous":
        edges = [e for e in graph["edges"] if e.get("kind") == "module attribute"]
        assert len(edges) == 2 and all(e["resolution"] == "ambiguous" for e in edges)
