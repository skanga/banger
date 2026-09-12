from banger.index import CodeIndex
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


async def test_path_tool_returns_callsite_arguments_and_return_holders(tmp_path):
    (tmp_path / "a.py").write_text(
        "def leaf(value): return value\n"
        "def middle(item):\n result = leaf(value=item + 1)\n return result\n"
        "def root():\n first = middle(2)\n second = middle(3)\n return first + second\n"
    )
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await toolbox.invoke("trace_path", {"source": "root", "target": "leaf"})
        assert result["found"] is True
        assert len(result["symbols"]) == 3
        first, second = result["steps"]
        assert [site["arguments"] for site in first["call_sites"]] == [["2"], ["3"]]
        assert [site["return_holder"] for site in first["call_sites"]] == ["first", "second"]
        assert first["target_parameters"] == ["item"]
        assert second["target_parameters"] == ["value"]
        assert second["call_sites"][0]["arguments"] == ["value=item + 1"]
        assert second["call_sites"][0]["path"] == "a.py"
        assert second["call_sites"][0]["line"] == 3
        assert second["call_sites"][0]["return_holder"] == "result"


def test_path_details_are_cycle_safe_and_distinguish_unreachable(tmp_path):
    (tmp_path / "a.py").write_text(
        "def leaf(): return 1\ndef a(): b()\ndef b():\n a()\n leaf()\ndef isolated(): pass\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    result = index.trace_path_details("a", "leaf")
    assert result["found"]
    assert len(result["steps"]) == 2
    assert index.trace_path_details("a", "isolated")["found"] is False
    same = index.trace_path_details("a", "a")
    assert same["found"] and same["steps"] == []


def test_path_details_do_not_claim_ambiguous_dispatch_is_resolved(tmp_path):
    (tmp_path / "a.py").write_text("def leaf(): pass\ndef root(leaf): leaf()\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    result = index.trace_path_details("root", "leaf")
    assert result["found"] is False
    assert result["steps"] == []
