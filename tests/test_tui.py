import asyncio
import json

import pytest
from textual.widgets import Input, Label, ListView, RichLog, Select, TabbedContent, TextArea

from banger.app import AgentEvent, Approval, BangerApp, ModePicker
from banger.permissions import Action
from banger.state import StateStore


async def wait_until(pilot, condition):
    async with asyncio.timeout(5):
        while not condition():
            await pilot.pause(0.01)


async def test_compact_terminal_setup_and_approval_controls_remain_usable(tmp_path):
    app = BangerApp(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "ask"
        start = app.screen.query_one("#start")
        await pilot.pause()
        start.scroll_visible(immediate=True, animate=False)
        await pilot.pause()
        assert await pilot.click("#start")
        await pilot.pause()
        assert app.agent is not None
        pending = asyncio.create_task(
            app.approve(Action("edit", path="sample.py"), "Long proposal\n" * 100)
        )
        try:
            await pilot.pause()
            assert isinstance(app.screen, Approval)
            deny = app.screen.query_one("#deny")
            await wait_until(
                pilot,
                lambda: deny.region.width > 0 and app.get_widget_at(*deny.region.center)[0] is deny,
            )
            assert await pilot.click(deny, offset=(deny.size.width // 2, deny.size.height // 2))
            assert await asyncio.wait_for(pending, timeout=5) == "deny"
            assert not isinstance(app.screen, Approval)
        finally:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)


async def test_shutdown_ignores_late_agent_updates(tmp_path, monkeypatch):
    app = BangerApp(tmp_path)
    close_all = app._close_all
    checked = False

    async def close_with_late_updates():
        nonlocal checked
        await close_all()
        assert not app.is_running
        # Reproduce a worker's already-queued messages arriving after widgets
        # disappear, while the application's message pump is still draining.
        for kind, payload in (
            ("text", "late token"),
            ("status", "late status"),
            ("done", "late answer"),
            ("tool_start", {"name": "write_file"}),
            ("tool_result", {"name": "write_file", "result": {"diff": "late diff"}}),
        ):
            app.on_agent_event(AgentEvent(kind, payload))
        app.clear_draft()
        await app.refresh_sessions()
        checked = True

    monkeypatch.setattr(app, "_close_all", close_with_late_updates)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
    assert checked


async def test_shutdown_cancels_model_worker_and_preserves_session(tmp_path):
    app = BangerApp(tmp_path)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def generate(system, messages, tools, on_text):
        on_text("Partial response")
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "ask"
        await pilot.click("#start")
        await pilot.pause()
        app.client.generate = generate
        session = app.agent.session
        app.worker = app.run_worker(app._run("Inspect the project"), group="agent")
        await asyncio.wait_for(started.wait(), timeout=2)
    assert cancelled.is_set()
    assert not app.agent.running
    assert app.client.client.is_closed
    with StateStore(tmp_path / ".banger/state.db") as state:
        assert state.messages(session)[-1]["content"] == "Inspect the project"


async def test_setup_requires_explicit_mode_and_can_open_workspace(tmp_path):
    (tmp_path / "hello.py").write_text("print('hello')\n")
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.screen.id == "setup"
        app.screen.query_one("#model", Input).value = "local-model"
        app.screen.query_one("#endpoint", Input).value = "http://localhost:1234/v1"
        await pilot.click("#start")
        assert app.screen.id == "setup"
        app.screen.query_one("#mode", Select).value = "read-only"
        await pilot.pause(0.3)
        app.screen.query_one("#start").scroll_visible(immediate=True)
        await pilot.pause()
        await pilot.click("#start")
        await pilot.pause()
        assert app.agent is not None, (
            app.screen.query_one("#mode", Select).value,
            app.screen.query_one("#start").region,
            str(app.screen.query_one("#setup-error").render()),
        )
        assert app.agent.tools.policy.mode.value == "read-only"
        await app.show_source(tmp_path / "hello.py")
        assert app.query_one("#source", TextArea).text == "print('hello')\n"


async def test_configuration_never_persists_api_key(tmp_path):
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "model"
        app.screen.query_one("#api-key", Input).value = "secret-test-key"
        app.screen.query_one("#mode", Select).value = "ask"
        await pilot.click("#start")
        await pilot.pause()
        saved = app.state.artifact("config", "last")
        assert "api_key" not in saved
        assert "secret-test-key" not in str(saved)
        await pilot.press("ctrl+p")
        await pilot.pause()
        app.screen.query_one("#permission-mode", Select).value = "read-only"
        await pilot.click("#apply-mode")
        await pilot.pause()
        assert app.client.config.api_key == "secret-test-key"
        assert app.agent.tools.policy.mode.value == "read-only"


async def test_cancelled_approval_does_not_remain_beneath_mode_picker(tmp_path):
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "ask"
        await pilot.click("#start")
        await pilot.pause()
        pending = asyncio.create_task(app.approve(Action("edit", path="a.py"), "Write a.py"))
        await pilot.pause()
        assert isinstance(app.screen, Approval)
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert isinstance(app.screen, ModePicker)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        if isinstance(app.screen, ModePicker):
            await pilot.press("escape")
        await pilot.pause()
        assert not any(isinstance(screen, Approval) for screen in app.screen_stack)


async def test_interrupted_stream_does_not_leak_into_next_session(tmp_path):
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "ask"
        await pilot.click("#start")
        await pilot.pause()
        started = asyncio.Event()

        async def generate(system, messages, tools, on_text):
            on_text("Partial answer from old session")
            started.set()
            await asyncio.Event().wait()

        app.client.generate = generate
        prompt = app.query_one("#prompt", Input)
        prompt.value = "Start slow response"
        prompt.focus()
        await pilot.press("enter")
        await asyncio.wait_for(started.wait(), timeout=2)
        await pilot.pause()
        assert app.draft == "Partial answer from old session"
        await pilot.press("escape")
        for _ in range(100):
            if not app.agent.running:
                break
            await pilot.pause(0.01)
        assert not app.agent.running
        assert app.draft == ""
        previous = app.agent.session
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert app.agent.session != previous
        assert app.draft == ""


async def test_new_session_clears_tool_and_diff_views(tmp_path):
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "ask"
        await pilot.click("#start")
        await pilot.pause()
        app.on_agent_event(
            AgentEvent(
                "tool_result",
                {"name": "write_file", "result": {"diff": "--- old\n+++ new\n+content"}},
            )
        )
        await pilot.click("#--content-tab-tools-tab")
        await wait_until(
            pilot,
            lambda: (
                app.query_one("#tabs", TabbedContent).active == "tools-tab"
                and app.query_one("#tool-log", RichLog).lines
            ),
        )
        assert app.query_one("#tool-log", RichLog).lines
        await pilot.click("#--content-tab-diff-tab")
        await wait_until(
            pilot,
            lambda: (
                app.query_one("#tabs", TabbedContent).active == "diff-tab"
                and app.query_one("#diff-log", RichLog).lines
            ),
        )
        assert app.query_one("#diff-log", RichLog).lines
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert not app.query_one("#tool-log", RichLog).lines
        assert not app.query_one("#diff-log", RichLog).lines


@pytest.mark.parametrize("selection", ["keyboard", "mouse"])
async def test_resuming_session_restores_its_saved_tool_results(tmp_path, selection):
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "ask"
        await pilot.click("#start")
        await pilot.pause()
        session = app.agent.session
        app.state.append(session, {"role": "user", "content": "Earlier task"})
        app.state.append(
            session,
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "saved-call",
                        "type": "function",
                        "function": {"name": "write_file", "arguments": "{}"},
                    }
                ],
            },
        )
        app.state.append(
            session,
            {
                "role": "tool",
                "tool_call_id": "saved-call",
                "content": json.dumps({"diff": "--- before\n+++ after\n+saved change"}),
            },
        )
        await pilot.press("ctrl+n")
        await pilot.pause()
        await pilot.click("#--content-tab-sessions-tab")
        await pilot.pause(0.3)
        listing = app.query_one("#sessions", ListView)
        index = app.session_ids.index(session)
        if selection == "keyboard":
            listing.index = index
            listing.focus()
            await pilot.press("enter")
        else:
            item = listing.children[index].query_one(Label)
            clicked = await pilot.click(item)
            assert clicked, (
                item.region,
                listing.region,
                app.query_one("#tabs", TabbedContent).active,
                listing.parent.region,
                listing.display,
                listing.parent.display,
            )
        await pilot.pause()
        assert app.agent.session == session, (listing.index, index, listing.region)
        await pilot.click("#--content-tab-tools-tab")
        await pilot.pause(0.3)
        assert app.query_one("#tool-log", RichLog).lines
        await pilot.click("#--content-tab-diff-tab")
        await pilot.pause(0.3)
        assert app.query_one("#diff-log", RichLog).lines
