import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from textual.widgets import Input, Select

from banger.agent import Agent
from banger.app import Approval, BangerApp
from banger.models import ModelClient, ModelConfig
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


def provider_response(provider, name=None, args=None, step=0):
    if provider == "anthropic":
        block = (
            {"type": "tool_use", "id": f"call{step}", "name": name, "input": args}
            if name
            else {"type": "text", "text": "Fixed addition; the reproduction passes."}
        )
        return httpx.Response(
            200, json={"content": [block], "stop_reason": "tool_use" if name else "end_turn"}
        )
    message = {
        "role": "assistant",
        "content": "" if name else "Fixed addition; the reproduction passes.",
    }
    if name:
        message["tool_calls"] = [
            {
                "id": f"call{step}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ]
    return httpx.Response(200, json={"choices": [{"message": message}]})


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_query_edit_execute_and_resume_through_provider_protocol(tmp_path, provider):
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a - b\n")
    steps = [
        ("profile", {"symbol": "add"}),
        ("replace_text", {"path": "calculator.py", "old": "a - b", "new": "a + b"}),
        (
            "execute_generated_testcase",
            {
                "content": "from calculator import add\nassert add(2, 3) == 5\nprint('PASS')\n",
                "python": sys.executable,
            },
        ),
    ]
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["tools"]
        step = len(requests) - 1
        return (
            provider_response(provider, *steps[step], step)
            if step < len(steps)
            else provider_response(provider)
        )

    approved = []

    async def approve(action, detail):
        approved.append(action.kind)
        return "allow"

    with StateStore(tmp_path / ".banger/state.db") as state:
        config = ModelConfig(
            provider, "fixture-model", "https://example.test/v1", "test-key", stream=False
        )
        async with ModelClient(config, httpx.MockTransport(respond)) as client:
            toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ASK), approve)
            agent = Agent(state, toolbox, client)
            result = await agent.run("Fix add and verify it")
            assert "passes" in result
            assert "a + b" in (tmp_path / "calculator.py").read_text()
            execution = state.artifact("execution", "last")
            assert execution["exit_code"] == 0
            assert "PASS" in execution["output"]
            assert approved == ["edit", "edit", "command"]
            assert state.artifact("trace", "last")["events"]
            resumed = Agent(state, toolbox, client, agent.session)
            assert resumed.messages == agent.messages
            assert len(requests) == 4


async def test_tui_approval_and_completed_edit(tmp_path):
    app = BangerApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.screen.query_one("#model", Input).value = "fixture-model"
        app.screen.query_one("#mode", Select).value = "ask"
        await pilot.click("#start")
        await pilot.pause()
        step = 0

        def respond(request):
            nonlocal step
            step += 1
            if step == 1:
                return provider_response(
                    "openai",
                    "write_file",
                    {"path": "hello.py", "content": "print('hello')\n"},
                    step,
                )
            return provider_response("openai")

        await app.client.client.aclose()
        app.client.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        app.client.config.stream = False
        prompt = app.query_one("#prompt", Input)
        prompt.value = "Create hello.py"
        prompt.focus()
        await pilot.press("enter")
        for _ in range(100):
            if isinstance(app.screen, Approval):
                break
            await pilot.pause(0.02)
        assert isinstance(app.screen, Approval)
        assert not (tmp_path / "hello.py").exists()
        await pilot.click("#allow")
        for _ in range(100):
            if not app.agent.running:
                break
            await pilot.pause(0.02)
        assert (tmp_path / "hello.py").read_text() == "print('hello')\n"
        assert not app.agent.running
        assert app.agent.messages[-1]["role"] == "assistant"
        if os.environ.get("BANGER_CAPTURE_UI"):
            await pilot.pause()
            Path(os.environ["BANGER_CAPTURE_UI"]).write_text(
                app.export_screenshot(), encoding="utf-8"
            )
