import asyncio
from unittest.mock import Mock

import pytest
from textual.widgets import Static

from banger.app import AgentEvent, BangerApp
from banger.permissions import Action


async def test_working_animates_and_stops_when_done(tmp_path):
    app = BangerApp(tmp_path)
    app._terminal_control = Mock()
    async with app.run_test() as pilot:
        app.pop_screen()
        await pilot.pause()
        app.on_agent_event(AgentEvent("status", "Working"))
        initial = app.title
        assert "Working" in initial
        app._terminal_control.assert_called_with(f"\033]2;{initial}\033\\")
        await pilot.pause(0.25)
        assert app.title != initial
        assert "Working" in str(app.query_one("#status", Static).render())
        app.on_agent_event(AgentEvent("tool_start", {"name": "read_file"}))
        assert "Working" in app.title
        assert "read_file" in str(app.query_one("#status", Static).render())
        app.on_agent_event(AgentEvent("done", "Finished"))
        assert app.title == "Banger"
        app._terminal_control.assert_called_with("\033]2;Banger\033\\")
        await pilot.pause(0.25)
        assert app.title == "Banger"
    assert app._terminal_control.call_args_list[0].args == ("\033[22;2t",)
    app._terminal_control.assert_called_with("\033[23;2t")


@pytest.mark.parametrize("answer", ["allow", "deny", "cancel"])
async def test_approval_bell_takes_priority_and_restores_working(tmp_path, answer):
    app = BangerApp(tmp_path)
    app.bell = Mock()
    async with app.run_test() as pilot:
        app.pop_screen()
        await pilot.pause()
        app.on_agent_event(AgentEvent("status", "Working"))
        pending = asyncio.create_task(app.approve(Action("edit", path="a.py"), "Write a.py"))
        await pilot.pause()
        assert "🔔 Action required" in app.title
        await pilot.pause(0.25)
        assert "Action required" in app.title
        app.bell.assert_called_once()
        if answer == "cancel":
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        else:
            app.screen.dismiss(answer)
            assert await pending == answer
        assert "Working" in app.title
        app.on_agent_event(AgentEvent("status", "Interrupted; session saved"))
        assert app.title == "Banger"


async def test_failed_run_stops_animation(tmp_path):
    app = BangerApp(tmp_path)
    async with app.run_test() as pilot:
        app.pop_screen()
        await pilot.pause()

        async def fail(prompt):
            app.on_agent_event(AgentEvent("status", "Working"))
            raise RuntimeError("Provider unavailable")

        app.agent = Mock()
        app.agent.run = fail
        await app._run("hello")
        assert app.title == "Banger"
        assert "Stopped with an error" in str(app.query_one("#status", Static).render())
