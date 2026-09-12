import pytest

from banger.analysis import FlowAnalysis
from banger.index import CodeIndex
from banger.state import StateStore


@pytest.mark.parametrize(
    "body,reaches",
    [
        (
            "def writer():\n global value\n value = source()\ndef caller(): return consume(value)\n",
            True,
        ),
        (
            "value = source()\ndef outer():\n def inner(item=value): return consume(item)\n return inner()\n",
            True,
        ),
        ("value = source()\ndef caller(): return consume(value)\n", True),
        (
            "def outer():\n value = source()\n def inner(): return consume(value)\n return inner()\n",
            True,
        ),
        (
            "value = source()\nclass C:\n value = 99\n def method(self): return consume(value)\n",
            True,
        ),
        (
            "def outer():\n value = source()\n class C:\n  value = 99\n  def method(self): return consume(value)\n",
            True,
        ),
        ("value = source()\ndef caller():\n value = 99\n return consume(value)\n", False),
        (
            "value = source()\ndef caller():\n from elsewhere import value\n return consume(value)\n",
            False,
        ),
        ("value = source()\ndef caller():\n for value in [99]:\n  consume(value)\n", False),
        (
            "value = 0\ndef writer():\n global value\n value = source()\ndef caller(): return consume(value)\n",
            True,
        ),
        (
            "def outer():\n value = 0\n def writer():\n  nonlocal value\n  value = source()\n writer()\n return consume(value)\n",
            True,
        ),
    ],
)
def test_python_flow_obeys_binding_scope_and_restart(tmp_path, body, reaches):
    (tmp_path / "flow.py").write_text(
        "def source(): return 3\ndef consume(item): return item\n" + body
    )
    database = tmp_path / ".banger/state.db"
    with StateStore(database) as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        graph = FlowAnalysis(index).forwardflow("source")["graph"]
        target = index.get_definition("consume")["id"]
        assert any(n.get("symbol") == target for n in graph["nodes"]) == reaches
        backward = FlowAnalysis(index).backflow("consume", "item")["graph"]
        source = index.get_definition("source")["id"]
        assert any(n.get("symbol") == source for n in backward["nodes"]) == reaches
        if reaches:
            assert not any(n.get("expression") == "99" for n in graph["nodes"])
    with StateStore(database) as state:
        reopened = CodeIndex(tmp_path, state)
        reopened.refresh()
        assert FlowAnalysis(reopened).forwardflow("source")["graph"] == graph
