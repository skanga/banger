from banger.analysis import FlowAnalysis
from banger.index import CodeIndex


def test_module_return_holder_references_stay_in_the_callers_file(tmp_path):
    (tmp_path / "lib.py").write_text("def leaf(): return 1\n")
    (tmp_path / "left.py").write_text("from lib import leaf\nx = leaf()\nprint(x)\n")
    (tmp_path / "right.py").write_text("x = 99\nprint(x)\nprint(x)\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    uses = FlowAnalysis(index).return_uses("leaf")["uses"]
    assert uses[0]["references"]
    assert {reference["path"] for reference in uses[0]["references"]} == {"left.py"}


def test_parameter_backflow_and_return_holders(tmp_path):
    (tmp_path / "a.py").write_text(
        "def twice(value):\n return value * 2\n"
        "def root():\n original = 3\n result = twice(original)\n return result\n"
        "def test_twice():\n assert twice(2) == 4\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    flow = FlowAnalysis(index)
    back = flow.backflow("twice", "value")
    site = next(s for s in back["call_sites"] if s["argument"] == "original")
    assert site["definitions"][0]["expression"] == "3"
    forward = flow.forwardflow("twice")
    assert any(s["holder"] == "result" for s in forward["uses"])
    assert flow.relevant_tests("twice")[0]["name"] == "test_twice"


def test_shadowed_callable_is_not_a_proven_edge(tmp_path):
    (tmp_path / "a.py").write_text("def target(): pass\ndef caller(target): target()\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    calls = index.profile("caller")["calls"]
    assert calls[0]["resolution"] != "resolved"


def test_reference_query_includes_read_and_write_sites(tmp_path):
    (tmp_path / "a.py").write_text("def f(value):\n result = value + 1\n return result\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    references = FlowAnalysis(index).references("result")
    assert {r["line"] for r in references} == {2, 3}


def test_dataflow_traverses_return_holder_and_next_call(tmp_path):
    (tmp_path / "a.py").write_text(
        "def source(): return 3\ndef consume(value): return value + 1\n"
        "def root():\n item = source()\n output = consume(item)\n return output\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    analysis = FlowAnalysis(index)
    forward = analysis.forwardflow("source")["graph"]
    assert any(
        n.get("symbol") == index.get_definition("consume")["id"] and n.get("name") == "value"
        for n in forward["nodes"]
    )
    backward = analysis.backflow("consume", "value")["graph"]
    assert any(n.get("expression") == "3" for n in backward["nodes"])
