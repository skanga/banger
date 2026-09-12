import pytest

from banger.analysis import FlowAnalysis
from banger.index import CodeIndex


@pytest.mark.parametrize(
    "declaration,call,parameter,expected",
    [
        ("def target(left=0, *, right=0): pass", "target(right=value)", "left", []),
        ("def target(left, right): pass", "target(right=value, left=other)", "left", ["other"]),
        ("def target(flag): pass", "target(value == other)", "flag", ["value == other"]),
        ("def target(first, *rest): pass", "target(0, value, other)", "rest", ["value", "other"]),
        ("def target(first, /, **extras): pass", "target(value, first=other)", "first", ["value"]),
        ("def target(first, /, **extras): pass", "target(value, first=other)", "extras", ["other"]),
        ("def target(first, second): pass", "target(*values)", "first", []),
        ("def target(first): pass", "target(**values)", "first", []),
        ("def target(first, /): pass", "target(first=value)", "first", []),
    ],
)
def test_backflow_and_graph_agree_on_python_argument_binding(
    tmp_path, declaration, call, parameter, expected
):
    (tmp_path / "flow.py").write_text(
        declaration + "\ndef caller(value, other, values):\n " + call + "\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    result = FlowAnalysis(index).backflow("target", parameter)
    site = result["call_sites"][0]
    assert site["argument"] == (expected[0] if len(expected) == 1 else None)
    assert site["arguments"] == expected
    graph = result["graph"]
    expressions = {node["id"]: node.get("expression") for node in graph["nodes"]}
    incoming = [
        expressions[edge["source"]]
        for edge in graph["edges"]
        if edge.get("kind") == "call argument"
        and edge["target"] == index.get_definition("target")["id"] + "|value|" + parameter
    ]
    assert incoming == expected
    if "*values" in call:
        assert site["binding"] == "unresolved"
    if declaration == "def target(first, /): pass":
        assert site["binding"] == "invalid call"


def test_implicit_receiver_does_not_shift_explicit_argument(tmp_path):
    (tmp_path / "flow.py").write_text(
        "class Service:\n"
        " def target(this, value): return value\n"
        " def caller(this, original): return this.target(original)\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    result = FlowAnalysis(index).backflow("target", "value")
    assert result["call_sites"][0]["argument"] == "original"
    assert any(node.get("expression") == "original" for node in result["graph"]["nodes"])


def test_forward_flow_continues_through_variadic_parameter(tmp_path):
    (tmp_path / "flow.py").write_text(
        "def source(): return 3\n"
        "def target(*items): return items\n"
        "def caller():\n value = source()\n return target(0, value)\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).forwardflow("source")["graph"]
    assert any(
        node.get("symbol") == index.get_definition("target")["id"] and node.get("name") == "$return"
        for node in graph["nodes"]
    )
