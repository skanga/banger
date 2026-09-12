import pytest

from banger.analysis import FlowAnalysis
from banger.index import CodeIndex


@pytest.mark.parametrize(
    "expression,depends",
    [
        ("'value'", False),
        ("obj.value", False),
        ("dict(value=0)", False),
        ("{'value': 0}", False),
        ("lambda value: value + 1", False),
        ("[value for value in range(3)]", False),
        ("{value: value + 1 for value in range(3)}", False),
        ("(value for value in range(3))", False),
        ("lambda: ((value := 1), value)", False),
        ("lambda: (lambda value: value)", False),
        ("lambda: (lambda captured=value: captured)", True),
        ("value + 1", True),
        ("f'value={value}'", True),
        ("lambda captured=value: captured", True),
        ("[item for item in value]", True),
        ("[value for value in value]", True),
    ],
)
def test_expression_flow_tracks_reads_not_matching_text(tmp_path, expression, depends):
    (tmp_path / "flow.py").write_text(
        "def source(): return 3\n"
        "def consume(item): return item\n"
        "def caller(obj):\n value = source()\n result = "
        + expression
        + "\n return consume(result)\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).forwardflow("source")["graph"]
    assert (
        any(node.get("symbol") == index.get_definition("consume")["id"] for node in graph["nodes"])
        == depends
    )


def test_unicode_variable_read_is_preserved(tmp_path):
    (tmp_path / "flow.py").write_text(
        "def source(): return 3\ndef caller():\n café = source()\n return café + 1\n",
        encoding="utf-8",
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).forwardflow("source")["graph"]
    assert any(
        node.get("symbol") == index.get_definition("caller")["id"] and node.get("name") == "$return"
        for node in graph["nodes"]
    )
