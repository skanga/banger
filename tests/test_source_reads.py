import pytest

from banger.edits import Editor
from banger.index import CodeIndex
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029", "\v", "\f"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
async def test_source_read_lines_match_index_with_unicode_string_content(
    tmp_path, separator, newline
):
    lines = [f"marker = 'left{separator}right'", "def target(): return marker"]
    (tmp_path / "sample.py").write_bytes((newline.join(lines) + newline).encode("utf-8"))
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        definition = await toolbox.invoke("get_definition", {"symbol": "target"})
        assert definition["line"] == 2
        selected = await toolbox.invoke(
            "read_file",
            {"path": "sample.py", "start": definition["line"], "end": definition["line"]},
        )
        assert selected["total_lines"] == 2
        assert selected["source"] == "2: " + lines[1]
        full = await toolbox.invoke("read_file", {"path": "sample.py"})
        assert full["source"] == "1: " + lines[0] + "\n2: " + lines[1]


@pytest.mark.parametrize(
    "content,count,expected",
    [
        (b"", 0, ""),
        (b"\n", 1, "1: "),
        (b"one\ntwo", 2, "1: one\n2: two"),
        (b"one\r\ntwo\r\n", 2, "1: one\n2: two"),
        (b"one\rtwo\r", 2, "1: one\n2: two"),
    ],
)
async def test_source_reads_keep_empty_and_terminal_line_semantics(
    tmp_path, content, count, expected
):
    (tmp_path / "sample.txt").write_bytes(content)
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await toolbox.invoke("read_file", {"path": "sample.txt"})
        assert result["total_lines"] == count
        assert result["source"] == expected
        assert (await toolbox.invoke("read_file", {"path": "sample.txt", "start": 50, "end": 51}))[
            "source"
        ] == ""


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_edit_diff_counts_physical_lines_with_unicode_content(tmp_path, batch, newline):
    before = f"marker = 'left\u2028right'{newline}VALUE = 1{newline}"
    after = before.replace("VALUE = 1", "VALUE = 2")
    (tmp_path / "sample.py").write_bytes(before.encode("utf-8"))
    with StateStore(tmp_path / ".banger/state.db") as state:
        editor = Editor(tmp_path, state, CodeIndex(tmp_path))
        result = (
            editor.apply_changes({"sample.py": after})
            if batch
            else editor.write("sample.py", after)
        )
        assert "@@ -1,2 +1,2 @@" in result["diff"]
        assert " marker = 'left\u2028right'" + newline in result["diff"]
        assert "-VALUE = 1" + newline in result["diff"]
        assert "+VALUE = 2" + newline in result["diff"]
        assert (tmp_path / "sample.py").read_bytes() == after.encode("utf-8")
        editor.rollback()
        assert (tmp_path / "sample.py").read_bytes() == before.encode("utf-8")
