import pytest

from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


async def test_outline_reports_one_body_level_and_source_ranges(tmp_path):
    (tmp_path / "a.py").write_text(
        "def root(value):\n"
        "    total = value\n"
        "    if value:\n"
        "        for item in range(3):\n"
        "            total += item\n"
        "    def inner():\n"
        "        return 99\n"
        "    return total\n"
    )
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await toolbox.invoke("skim_source", {"symbol": "root"})
        assert [item["line"] for item in result["outline"]] == [1, 2, 3, 6, 8]
        assert result["outline"][2]["end_line"] == 5
        assert [child["name"] for child in result["children"]] == ["inner"]
        assert result["truncated"] is False


@pytest.mark.parametrize(
    "filename,source",
    [
        ("a.js", "function root(x) {\n const value = x;\n return value;\n}"),
        ("a.ts", "function root(x: number) {\n const value = x;\n return value;\n}"),
        ("A.java", "class A { int root(int x) {\n int value = x;\n return value;\n} }"),
        ("A.cs", "class A { int root(int x) {\n int value = x;\n return value;\n} }"),
        ("a.cpp", "int root(int x) {\n int value = x;\n return value;\n}"),
        ("a.c", "int root(int x) {\n int value = x;\n return value;\n}"),
        ("a.go", "package main\nfunc root(x int) int {\n value := x\n return value\n}"),
        ("a.rs", "fn root(x: i32) -> i32 {\n let value = x;\n value\n}"),
        ("a.rb", "def root(x)\n value = x\n value\nend"),
    ],
)
async def test_outline_includes_assignments_in_each_language(tmp_path, filename, source):
    (tmp_path / filename).write_text(source)
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await toolbox.invoke("skim_source", {"symbol": "root"})
        assert len(result["outline"]) == 3
        assert "value" in result["outline"][1]["text"]
        assert result["outline"][1]["kind"]


async def test_large_outline_is_bounded_and_survives_restart(tmp_path):
    (tmp_path / "a.py").write_text(
        "def root():\n" + "\n".join(f" value{i} = {i}" for i in range(150))
    )
    for _ in range(2):
        with StateStore(tmp_path / ".banger/state.db") as state:
            toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
            result = await toolbox.invoke("skim_source", {"symbol": "root"})
            assert len(result["outline"]) == 100
            assert result["total_entries"] == 151
            assert result["truncated"] is True
