import asyncio
import json

import pytest
from textual.widgets import Input, Select, TextArea

from banger.app import Approval, BangerApp


@pytest.mark.parametrize("operation", ["write_file", "replace_text", "apply_edits", "delete_batch"])
async def test_edit_approval_shows_readable_proposal_before_changes(
    tmp_path, click_ready, operation
):
    original = "def value():\n    return 1\n"
    proposed = "def value():\n    return 2\n"
    target = tmp_path / "sample.py"
    target.write_text(original, encoding="utf-8")
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "ask"
        await click_ready(pilot, "#start")
        await pilot.pause()
        name = "apply_edits" if operation == "delete_batch" else operation
        args = (
            {"path": "sample.py", "old": original, "new": proposed}
            if operation == "replace_text"
            else {
                "edits_json": json.dumps(
                    {"sample.py": None if operation == "delete_batch" else proposed}
                )
            }
            if name == "apply_edits"
            else {"path": "sample.py", "content": proposed}
        )
        pending = asyncio.create_task(app.agent.tools.invoke(name, args))
        try:
            async with asyncio.timeout(5):
                while not isinstance(app.screen, Approval):
                    await pilot.pause(0.01)
            detail = app.screen.query_one("#approval-detail", TextArea).text
            assert "sample.py" in detail
            if operation == "delete_batch":
                assert "Delete file" in detail
            else:
                assert proposed in detail
                if operation == "replace_text":
                    assert original in detail
            assert target.read_text() == original
            assert app.screen.query_one("#approval-detail", TextArea).read_only
        finally:
            if isinstance(app.screen, Approval):
                await click_ready(pilot, "#deny")
            result = await asyncio.wait_for(pending, timeout=5)
        assert "error" in result
        assert target.read_text() == original
