from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


async def test_regex_search_runs_read_only_and_reports_invalid_patterns(tmp_path):
    (tmp_path / "notes.txt").write_text("ID=12\nid=345\nnot a match\n")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await tools.invoke(
            "search_text", {"query": r"^id=\d{2}$", "regex": True, "case_sensitive": False}
        )
        assert "error" not in result, result
        assert [(m["line"], m["text"]) for m in result["matches"]] == [(1, "ID=12")]
        assert "error" in await tools.invoke("search_text", {"query": "[", "regex": True})


async def test_pathological_regex_returns_a_bounded_error(tmp_path):
    (tmp_path / "notes.txt").write_text("a" * 20000 + "!")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        # The worker deadline, rather than a regex engine heuristic, bounds this.
        import asyncio

        async with asyncio.timeout(20):
            result = await tools.invoke("search_text", {"query": "(a+)+$", "regex": True})
        assert "time limit" in result.get("error", ""), result


async def test_regex_does_not_invent_a_line_after_final_newline(tmp_path):
    (tmp_path / "text.txt").write_text("text\n")
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / "blank.txt").write_text("\n")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await tools.invoke("search_text", {"query": "^$", "regex": True})
        assert [(m["path"], m["line"]) for m in result["matches"]] == [("blank.txt", 1)]
