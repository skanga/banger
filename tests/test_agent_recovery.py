import asyncio
import json

import pytest

from banger.agent import Agent
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


def tool_call(identity, path="file.txt"):
    return {
        "id": identity,
        "type": "function",
        "function": {
            "name": "write_file",
            "arguments": json.dumps({"path": path, "content": "new"}),
        },
    }


class Replies:
    def __init__(self, *replies):
        self.replies = iter(replies)

    async def generate(self, *args):
        return next(self.replies)


def test_resume_repairs_reused_call_id_at_its_latest_occurrence(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        session = state.new_session("Repeated IDs")
        state.append(session, {"role": "user", "content": "first"})
        state.append(session, {"role": "assistant", "tool_calls": [tool_call("reused")]})
        state.append(session, {"role": "tool", "tool_call_id": "reused", "content": "completed"})
        state.append(session, {"role": "user", "content": "second"})
        state.append(session, {"role": "assistant", "tool_calls": [tool_call("reused")]})
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        agent = Agent(state, toolbox, Replies(), session=session)
        assert agent.messages[-1]["role"] == "tool"
        assert "Interrupted" in agent.messages[-1]["content"]
        assert agent.messages[2]["content"] == "completed"
        count = len(agent.messages)
        agent._repair_pending()
        assert len(agent.messages) == count
        assert not (tmp_path / "file.txt").exists()


@pytest.mark.parametrize("identities", [("same", "same"), ("valid", 123), ("valid", " ")])
async def test_invalid_call_ids_are_rejected_before_any_tool_effect(tmp_path, identities):
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        response = {
            "role": "assistant",
            "tool_calls": [tool_call(i, f"file{n}.txt") for n, i in enumerate(identities)],
        }
        agent = Agent(state, toolbox, Replies(response, {"role": "assistant", "content": "done"}))
        with pytest.raises(ValueError, match="tool call"):
            await agent.run("write files")
        assert list(tmp_path.glob("file*.txt")) == []
        assert [m["role"] for m in agent.messages] == ["user"]
        assert agent.running is False
        assert await agent.run("retry") == "done"
        assert list(tmp_path.glob("file*.txt")) == []


async def test_large_outputs_survive_reused_model_call_ids(tmp_path, monkeypatch):
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        outputs = iter([{"value": "a" * 61000}, {"value": "b" * 61000}])

        async def invoke(*args):
            return next(outputs)

        monkeypatch.setattr(toolbox, "invoke", invoke)
        response = {"role": "assistant", "tool_calls": [tool_call("reused")]}
        agent = Agent(
            state, toolbox, Replies(response, response, {"role": "assistant", "content": "done"})
        )
        await agent.run("inspect")
        artifacts = [
            json.loads(m["content"])["saved_artifact"]
            for m in agent.messages
            if m["role"] == "tool"
        ]
        assert len(set(artifacts)) == 2
        assert state.artifact("tool-output", artifacts[0])["value"] == "a" * 61000
        assert state.artifact("tool-output", artifacts[1])["value"] == "b" * 61000


async def test_cancellation_repairs_the_current_reused_id_once(tmp_path, monkeypatch):
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.FULL_ACCESS))
        started = asyncio.Event()
        calls = 0

        async def invoke(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"completed": True}
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(toolbox, "invoke", invoke)
        response = {"role": "assistant", "tool_calls": [tool_call("reused")]}
        agent = Agent(state, toolbox, Replies(response, response))
        task = asyncio.create_task(agent.run("work"))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        results = [m for m in agent.messages if m["role"] == "tool"]
        assert len(results) == 2
        assert json.loads(results[0]["content"])["completed"] is True
        assert "Interrupted" in results[1]["content"]
        resumed = Agent(state, toolbox, Replies(), session=agent.session)
        assert resumed.messages == agent.messages
        assert calls == 2
