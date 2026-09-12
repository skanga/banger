import asyncio
import json
import time

from banger.agent import Agent
from banger.models import ModelConfig
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


class FakeModel:
    config = ModelConfig("openai", "fake", "http://localhost/v1")

    def __init__(self, replies):
        self.replies = iter(replies)

    async def generate(self, system, messages, tools, on_text=None):
        return next(self.replies)


def call(name, args, identity="one"):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": identity,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


async def test_agent_edits_then_finishes_and_persists(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        model = FakeModel(
            [
                call("write_file", {"path": "a.py", "content": "x = 1\n"}),
                {"role": "assistant", "content": "Created a.py"},
            ]
        )
        agent = Agent(state, tools, model)
        result = await agent.run("Create a.py")
        assert result == "Created a.py"
        assert (tmp_path / "a.py").read_text() == "x = 1\n"
        assert [m["role"] for m in state.messages(agent.session)] == [
            "user",
            "assistant",
            "tool",
            "assistant",
        ]


async def test_denied_tool_never_writes(tmp_path):
    approvals = []

    async def deny(action, detail):
        approvals.append(action)
        return "deny"

    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ASK), deny)
        result = await tools.invoke("write_file", {"path": "a.py", "content": "x=1"})
        assert "denied" in result["error"].lower()
        assert len(approvals) == 1
        assert not (tmp_path / "a.py").exists()


async def test_resume_closes_unfinished_tools_without_executing_them(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        session = state.new_session("interrupted")
        state.append(session, {"role": "user", "content": "edit"})
        state.append(session, call("write_file", {"path": "a.py", "content": "bad"}))
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        agent = Agent(state, tools, FakeModel([]), session=session)
        assert agent.messages[-1]["role"] == "tool"
        assert "interrupted" in agent.messages[-1]["content"].lower()
        assert not (tmp_path / "a.py").exists()


async def test_tool_argument_validation_precedes_side_effects(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        assert "error" in await tools.invoke("write_file", {"path": "a.py", "content": 42})
        assert "error" in await tools.invoke(
            "write_file", {"path": "a.py", "content": "ok", "extra": True}
        )
        assert "error" in await tools.invoke("__getattribute__", {"name": "state"})
        assert not (tmp_path / "a.py").exists()


async def test_escalation_denial_keeps_original_model(tmp_path):
    async def deny(action, detail):
        assert action.kind == "escalate"
        return "deny"

    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS), deny)
        model = FakeModel([call("upgrade_to_pro", {}), {"role": "assistant", "content": "Staying"}])
        agent = Agent(state, tools, model, stronger_model="stronger")
        await agent.run("Work")
        assert model.config.model == "fake"


async def test_indexing_does_not_block_terminal_event_loop(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ASK))
        tools.index.refresh = lambda: time.sleep(0.15)
        beats = 0

        async def heartbeat():
            nonlocal beats
            for _ in range(4):
                await asyncio.sleep(0.02)
                beats += 1

        task = asyncio.create_task(heartbeat())
        await tools.invoke("search_symbols", {"query": "name"})
        assert beats >= 3
        await task
