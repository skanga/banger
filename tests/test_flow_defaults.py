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
        assert any(n.get("name") == "seed" for n in original["graph"]["nodes"])
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


@pytest.mark.parametrize("nested", [False, True])
def test_default_backflow_reaches_declaration_dependencies(tmp_path, nested):
    source = (
        "def outer(seed):\n"
        " derived = seed + 2\n"
        " def target(value=derived): return value\n"
        " return target() + target()\n"
        if nested
        else "seed = 7\nderived = seed + 2\ndef target(value=derived): return value\n"
    )
    (tmp_path / "lib.py").write_text(source)
    if not nested:
        (tmp_path / "app.py").write_text(
            "from lib import target\ndef caller():\n derived = 99\n return target() + target()\n"
        )
    index = CodeIndex(tmp_path)
    index.refresh()
    graph = FlowAnalysis(index).backflow("target", "value")["graph"]
    scope = index.get_definition("outer")["id"] if nested else None
    seed = next(n for n in graph["nodes"] if n.get("name") == "seed")
    assert seed["symbol"] == scope
    assert seed["path"] == "lib.py"
    assert not any(n.get("expression") == "99" for n in graph["nodes"])
    links = [e for e in graph["edges"] if e.get("kind") == "default expression"]
    assert len(links) == 1
    default = next(n for n in graph["nodes"] if n["id"] == links[0]["target"])
    assert default["expression"] == "derived"
    assert default["symbol"] == scope
