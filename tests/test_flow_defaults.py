import pytest

from banger.analysis import FlowAnalysis
from banger.index import CodeIndex
from banger.state import StateStore


@pytest.mark.parametrize(
    "call,uses_default",
    [
        ("target()", True),
        ("target(value=99)", False),
        ("target(**values)", False),
        ("target(1, 2)", False),
    ],
)
def test_default_origin_is_used_only_for_proven_omission(tmp_path, call, uses_default):
    (tmp_path / "lib.py").write_text("DEFAULT = 7\ndef target(value=DEFAULT): return value\n")
    (tmp_path / "app.py").write_text(
        "from lib import target\ndef caller(values):\n DEFAULT = 99\n return " + call + "\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    result = FlowAnalysis(index).backflow("target", "value")
    origin = result["call_sites"][0]["default"]
    if uses_default:
        assert origin == {"expression": "DEFAULT", "path": "lib.py", "line": 2, "scope": None}
        assert result["call_sites"][0]["definitions"] == []
    else:
        assert origin is None
    defaults = [edge for edge in result["graph"]["edges"] if edge.get("kind") == "default argument"]
    assert bool(defaults) == uses_default
    if uses_default:
        node = next(n for n in result["graph"]["nodes"] if n["id"] == defaults[0]["source"])
        assert node["expression"] == "DEFAULT"
        assert node["path"] == "lib.py"
        assert node["symbol"] is None


def test_nested_keyword_default_preserves_declaration_scope_and_restart(tmp_path):
    (tmp_path / "lib.py").write_text(
        "def outer(seed):\n"
        " def target(*, value=(seed +\n  2), missing=None): return value\n"
        " return target()\n",
        newline="\n",
    )
    database = tmp_path / ".banger/state.db"
    with StateStore(database) as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        original = FlowAnalysis(index).backflow("target", "value")
        origin = original["call_sites"][0]["default"]
        assert origin["expression"] == "seed +\n  2"
        assert origin["scope"] == index.get_definition("outer")["id"]
        assert origin["line"] == 2
        assert (
            FlowAnalysis(index).backflow("target", "missing")["call_sites"][0]["default"][
                "expression"
            ]
            == "None"
        )
    with StateStore(database) as state:
        reopened = CodeIndex(tmp_path, state)
        reopened.refresh()
        assert FlowAnalysis(reopened).backflow("target", "value") == original
