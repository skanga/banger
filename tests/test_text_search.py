import asyncio
import subprocess

import pytest

from banger.permissions import PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


async def test_text_search_read_only_literals_and_physical_lines(tmp_path):
    (tmp_path / "notes.txt").write_bytes(b"First\r\nERROR [x]\rerror [x]\nlast\n")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, "read-only"))
        result = await tools.invoke("search_text", {"query": "error [x]", "case_sensitive": False})
        assert "error" not in result, result
        assert [(m["path"], m["line"], m["text"]) for m in result["matches"]] == [
            ("notes.txt", 2, "ERROR [x]"),
            ("notes.txt", 3, "error [x]"),
        ]
        assert result["truncated"] is False
        assert any(s["name"] == "search_text" for s in tools.schemas())


async def test_text_search_honors_git_ignore_and_directory_scope(tmp_path):
    await asyncio.to_thread(subprocess.run, ["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "ignored.txt").write_text("needle")
    (tmp_path / "other.txt").write_text("needle")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/guide.md").write_text("needle")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, "read-only"))
        result = await tools.invoke("search_text", {"query": "needle", "path": "docs"})
        assert [m["path"] for m in result["matches"]] == ["docs/guide.md"]
        result = await tools.invoke("search_text", {"query": "needle"})
        assert {m["path"] for m in result["matches"]} == {"docs/guide.md", "other.txt"}


async def test_text_search_limits_binary_and_invalid_requests(tmp_path):
    (tmp_path / "a.txt").write_text("needle\nneedle\nneedle\n")
    (tmp_path / "binary.dat").write_bytes(b"needle\x00")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, "read-only"))
        result = await tools.invoke("search_text", {"query": "needle", "max_results": 2})
        assert len(result["matches"]) == 2
        assert result["truncated"] is True
        result = await tools.invoke("search_text", {"query": "needle", "path": "binary.dat"})
        assert result["matches"] == []
        assert result["skipped"][0]["reason"] == "binary or non-UTF-8"
        for arguments in (
            {"query": ""},
            {"query": "x", "max_results": 0},
            {"query": "x", "path": "../"},
        ):
            assert "error" in await tools.invoke("search_text", arguments)


async def test_text_search_unicode_and_exact_limit(tmp_path):
    (tmp_path / "notes.txt").write_text("Straße\u2028still same physical line\n", encoding="utf-8")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, "read-only"))
        result = await tools.search_text("STRASSE", case_sensitive=False, max_results=1)
        assert result["matches"][0]["line"] == 1
        assert result["matches"][0]["text"] == "Straße\u2028still same physical line"
        assert result["truncated"] is False
        assert (await tools.search_text("STRASSE"))["matches"] == []


async def test_text_search_reports_oversized_files_and_long_previews(tmp_path):
    (tmp_path / "large.txt").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    (tmp_path / "line.txt").write_text("x" * 3000 + "needle")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, "read-only"))
        result = await tools.search_text("needle")
        assert result["skipped_count"] == 1
        assert result["skipped"] == [{"path": "large.txt", "reason": "file or search byte limit"}]
        assert result["matches"][0]["text_truncated"] is True
        assert len(result["matches"][0]["text"]) == 2000


@pytest.mark.parametrize(
    "prefix,query,case_sensitive,regex",
    [
        ("x" * 3000, "needle", True, False),
        ("ß" * 2500, "NEEDLE", False, False),
        ("x" * 3000, "n[e]+dle", True, True),
    ],
    ids=["literal", "unicode-casefold", "regex"],
)
async def test_search_preview_contains_match_and_source_columns(
    tmp_path, prefix, query, case_sensitive, regex
):
    line = prefix + "needle" + " tail"
    (tmp_path / "notes.txt").write_text(line, encoding="utf-8")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, "read-only"))
        result = await tools.search_text(query, case_sensitive=case_sensitive, regex=regex)
        match = result["matches"][0]
        assert "needle" in match["text"]
        assert match["column"] == len(prefix) + 1
        assert match["end_column"] == len(prefix) + 7
        start = match["preview_start_column"] - 1
        assert match["text"] == line[start : start + 2000]
        assert len(match["text"]) <= 2000
