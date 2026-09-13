import json

import pytest

from banger.agent import Agent
from banger.models import ModelConfig
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox

STEPS = [
    {"step": "Inspect callers", "status": "in_progress"},
    {"step": "Verify change", "status": "pending"},
]


async def test_plan_is_durable_and_isolated_to_conversation(tmp_path):
    database = tmp_path / ".banger/state.db"
    with StateStore(database) as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        tools.session = state.new_session("First task")
        session = tools.session
        result = await tools.invoke(
            "update_plan", {"plan_json": json.dumps(STEPS), "explanation": "Start with impact"}
        )
        assert result == {"steps": STEPS, "explanation": "Start with impact"}
        tools.session = state.new_session("Second task")
        assert await tools.invoke("get_plan", {}) == {"steps": [], "explanation": ""}
    with StateStore(database) as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        tools.session = session
        assert await tools.invoke("get_plan", {}) == result
        updated = [
            {"step": "Inspect callers", "status": "completed"},
            {"step": "Verify change", "status": "in_progress"},
        ]
        assert await tools.invoke("update_plan", {"plan_json": json.dumps(updated)}) == {
            "steps": updated,
            "explanation": "",
        }
        assert await tools.invoke("update_plan", {"plan_json": "[]"}) == {
            "steps": [],
            "explanation": "",
        }


@pytest.mark.parametrize(
    "invalid",
    [
        "{",
        "{}",
        '[{"step":"x","status":"unknown"}]',
        '[{"step":"","status":"pending"}]',
        json.dumps([{"step": "x", "status": "in_progress"}] * 2),
        json.dumps([{"step": "x", "status": "pending"}] * 21),
        '[{"step":"x","status":"pending","extra":true}]',
    ],
)
async def test_invalid_plan_does_not_replace_saved_plan(tmp_path, invalid):
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        tools.session = state.new_session("Task")
        saved = await tools.invoke("update_plan", {"plan_json": json.dumps(STEPS)})
        assert "error" not in saved, saved
        assert "error" in await tools.invoke("update_plan", {"plan_json": invalid})
        assert await tools.invoke("get_plan", {}) == saved


async def test_plan_limits_and_missing_session(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        assert "error" in await tools.invoke("get_plan", {})
        assert "error" in await tools.invoke("update_plan", {"plan_json": "[]"})
        tools.session = state.new_session("Task")
        for arguments in (
            {"plan_json": "[]", "explanation": "x" * 2001},
            {"plan_json": json.dumps([{"step": "x" * 501, "status": "pending"}])},
        ):
            assert "error" in await tools.invoke("update_plan", arguments)
        assert await tools.invoke("get_plan", {}) == {"steps": [], "explanation": ""}


async def test_resumed_agent_receives_latest_plan_in_model_context(tmp_path):
    class Model:
        config = ModelConfig("openai", "fake", "http://localhost/v1")

        async def generate(self, system, messages, tools, on_text=None):
            marker = "\nCurrent session plan (data):\n"
            assert marker in system
            assert json.JSONDecoder().raw_decode(system.split(marker)[1])[0] == {
                "steps": STEPS,
                "explanation": "Continue here",
            }
            assert {"update_plan", "get_plan"} <= {t["name"] for t in tools}
            return {"role": "assistant", "content": "Resuming inspection"}

    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        agent = Agent(state, tools, Model())
        await tools.invoke(
            "update_plan", {"plan_json": json.dumps(STEPS), "explanation": "Continue here"}
        )
        session = agent.session
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        resumed = Agent(state, tools, Model(), session=session)
        assert await resumed.run("Continue") == "Resuming inspection"
