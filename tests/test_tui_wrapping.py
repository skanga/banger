import pytest
from textual.widgets import Button, Input, ListView, RichLog, Select

from banger.app import AgentEvent, BangerApp


@pytest.mark.parametrize("kind", ["user", "restored_user", "assistant", "tool"])
@pytest.mark.parametrize("resized", [False, True])
async def test_compact_terminal_wraps_full_messages_into_visible_pane(
    tmp_path, click_ready, kind, resized
):
    app = BangerApp(tmp_path)
    words = [f"word{i:02}" for i in range(20)]
    content = " ".join(words)
    async with app.run_test(size=(120, 40) if resized else (80, 24)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "read-only"
        app.screen.query_one("#start", Button).focus()
        await click_ready(pilot, "#start")
        await pilot.pause()
        if kind == "tool":
            app.render_tool_result({"name": "read_file", "result": content})
            await click_ready(pilot, "#--content-tab-tools-tab")
            log = app.query_one("#tool-log", RichLog)
        elif kind == "assistant":
            app.on_agent_event(AgentEvent("done", content))
            log = app.query_one("#chat-log", RichLog)
        elif kind == "user":

            async def finish(prompt):
                assert prompt == content

            app.agent.run = finish
            prompt = app.query_one("#prompt", Input)
            prompt.value = content
            prompt.focus()
            await pilot.press("enter")
            await app.worker.wait()
            log = app.query_one("#chat-log", RichLog)
        else:
            session = app.agent.session
            app.state.append(session, {"role": "user", "content": content})
            await app.refresh_sessions()
            await click_ready(pilot, "#--content-tab-sessions-tab")
            listing = app.query_one("#sessions", ListView)
            listing.index = app.session_ids.index(session)
            listing.focus()
            await pilot.press("enter")
            log = app.query_one("#chat-log", RichLog)
        await pilot.pause()
        if resized:
            await pilot.resize_terminal(80, 24)
            await pilot.pause()
        visible = " ".join(log.render_line(y).text for y in range(log.size.height))
        for word in words:
            assert word in visible, (word, visible)
        assert log.max_scroll_x == 0
