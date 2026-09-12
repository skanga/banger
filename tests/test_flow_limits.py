import pytest

from banger.analysis import FlowAnalysis
from banger.index import CodeIndex


@pytest.mark.parametrize("call_count", [998, 999, 1000, 1100])
def test_backflow_node_limit_is_exact_and_reports_actual_omissions(tmp_path, call_count):
    (tmp_path / "flow.py").write_text(
        "def consume(value): return value\n"
        + "".join(f"consume({number})\n" for number in range(call_count))
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).backflow("consume", "value")["graph"]
    assert len(graph["nodes"]) == min(call_count + 1, 1000)
    assert graph["truncated"] == (call_count + 1 > 1000)
    identities = {node["id"] for node in graph["nodes"]}
    assert all(
        edge["source"] in identities and edge["target"] in identities for edge in graph["edges"]
    )
    assert len(graph["edges"]) == min(call_count, 999)


@pytest.mark.parametrize("call_count", [999, 1100])
def test_forward_flow_limit_preserves_edge_endpoints(tmp_path, call_count):
    (tmp_path / "flow.py").write_text(
        "def source(): return 3\n"
        + "".join(f"value_{number} = source()\n" for number in range(call_count))
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).forwardflow("source")["graph"]
    assert len(graph["nodes"]) == min(call_count + 1, 1000)
    assert graph["truncated"] == (call_count + 1 > 1000)
    identities = {node["id"] for node in graph["nodes"]}
    assert all(
        edge["source"] in identities and edge["target"] in identities for edge in graph["edges"]
    )
    assert len(graph["edges"]) == min(call_count, 999)
