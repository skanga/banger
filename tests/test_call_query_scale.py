import time

import pytest

from banger.index import CodeIndex


class CountedCalls(list):
    visits = 0

    def __iter__(self):
        for item in super().__iter__():
            self.visits += 1
            yield item


@pytest.mark.parametrize("query", ["forward", "reverse", "path"])
def test_call_queries_do_not_rescan_all_calls_for_each_reachable_symbol(tmp_path, query):
    count = 200
    (tmp_path / "chain.py").write_text(
        "".join(f"def node{i}(): return node{i + 1}()\n" for i in range(count - 1))
        + f"def node{count - 1}(): return 1\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    index.calls = CountedCalls(index.calls)
    start = time.perf_counter()
    if query == "path":
        result = index.trace_path_details("node0", f"node{count - 1}")
        assert len(result["symbols"]) == count
        assert len(result["steps"]) == count - 1
        assert all(len(step["call_sites"]) == 1 for step in result["steps"])
    else:
        result = index.call_tree(
            "node0" if query == "forward" else f"node{count - 1}", query == "reverse"
        )
        assert len(result["nodes"]) == count
        assert len(result["edges"]) == count - 1
    elapsed = time.perf_counter() - start
    print(f"{query}: {index.calls.visits} call visits, {elapsed:.6f}s")
    assert index.calls.visits <= 3 * len(index.calls)


def test_grouped_call_traversal_preserves_shortest_paths_cycles_and_module_sites(tmp_path):
    (tmp_path / "branch.py").write_text(
        "def root():\n a()\n b()\n"
        "def a(): middle()\n"
        "def middle(): leaf()\n"
        "def b(): leaf()\n"
        "def leaf(): root()\n"
        "leaf()\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    path = index.trace_path("root", "leaf")
    assert [index.symbols[identity]["name"] for identity in path] == ["root", "b", "leaf"]
    forward = index.call_tree("root")
    backward = index.call_tree("leaf", reverse=True)
    assert len(forward["nodes"]) == len(backward["nodes"]) == 5
    assert len(forward["edges"]) == 6
    assert len(backward["edges"]) == 7
    module_sites = [edge for edge in backward["edges"] if edge["source"] is None]
    assert module_sites == [
        {"source": None, "target": index.get_definition("leaf")["id"], "line": 8}
    ]
