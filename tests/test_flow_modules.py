from banger.analysis import FlowAnalysis
from banger.index import CodeIndex


def test_module_flow_connects_assignments_and_calls_without_crossing_files(tmp_path):
    (tmp_path / "lib.py").write_text(
        "def source(): return 3\n"
        "def consume(value): return value\n"
        "def unrelated(value): return value\n"
    )
    (tmp_path / "left.py").write_text(
        "from lib import source, consume\nvalue = source()\ncopy = value\nconsume(copy)\n"
    )
    (tmp_path / "right.py").write_text(
        "from lib import unrelated\nvalue = 99\ncopy = value\nunrelated(copy)\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    flow = FlowAnalysis(index)
    forward = flow.forwardflow("source")["graph"]
    assert any(n.get("symbol") == index.get_definition("consume")["id"] for n in forward["nodes"])
    assert not any(
        n.get("symbol") == index.get_definition("unrelated")["id"] for n in forward["nodes"]
    )
    backward = flow.backflow("consume", "value")["graph"]
    assert any(n.get("expression") == "3" for n in backward["nodes"])
    assert not any(n.get("path") == "right.py" for n in backward["nodes"])
    module_values = [
        n for n in backward["nodes"] if n.get("name") in {"value", "copy"} and n["symbol"] is None
    ]
    assert {n["path"] for n in module_values} == {"left.py"}


def test_identical_module_expressions_keep_their_own_source_location(tmp_path):
    (tmp_path / "lib.py").write_text("def consume(value): return value\n")
    for name in ("left.py", "right.py"):
        (tmp_path / name).write_text("from lib import consume\nconsume(42)\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).backflow("consume", "value")["graph"]
    origins = [n for n in graph["nodes"] if n.get("expression") == "42"]
    assert {n["path"] for n in origins} == {"left.py", "right.py"}
    assert len({n["id"] for n in origins}) == 2


def test_module_return_holder_does_not_merge_unrelated_assignment(tmp_path):
    (tmp_path / "lib.py").write_text("def source(): return 3\n")
    (tmp_path / "left.py").write_text("from lib import source\nvalue = source()\n")
    (tmp_path / "right.py").write_text("value = 99\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).forwardflow("source")["graph"]
    holder = next(n for n in graph["nodes"] if n.get("name") == "value")
    assert holder["path"] == "left.py"
