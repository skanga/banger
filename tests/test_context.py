import json

import pytest

from banger.context import ContextWindow
from banger.state import StateStore


def test_compaction_keeps_tool_pairs_and_full_saved_history(tmp_path):
    with StateStore(tmp_path / "state.db") as state:
        session = state.new_session("long")
        history = []
        for n in range(10):
            history.extend(
                [
                    {"role": "user", "content": f"Task {n}"},
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": str(n),
                                "type": "function",
                                "function": {"name": "read_file", "arguments": "{}"},
                            }
                        ],
                    },
                    {"role": "tool", "tool_call_id": str(n), "content": "source" * 2000},
                    {"role": "assistant", "content": "Result " + str(n)},
                ]
            )
        for message in history:
            state.append(session, message)
        window = ContextWindow(state, session, max_chars=20000)
        compacted = window.prepare(history)
        assert len(str(compacted)) < 20000
        assert compacted[-1] == history[-1]
        assert "Task 0" in str(compacted)
        calls = {c["id"] for m in compacted for c in m.get("tool_calls", [])}
        results = {m["tool_call_id"] for m in compacted if m["role"] == "tool"}
        assert calls == results
        assert state.messages(session) == history
        assert ContextWindow(state, session, max_chars=20000).prepare(history) == compacted


def test_small_history_is_unchanged(tmp_path):
    with StateStore(tmp_path / "state.db") as state:
        history = [{"role": "user", "content": "hello"}]
        assert ContextWindow(state, state.new_session("s")).prepare(history) == history


@pytest.mark.parametrize("tool_batch", [False, True])
def test_latest_message_above_target_but_within_limit_is_retained(tmp_path, tool_batch):
    with StateStore(tmp_path / "state.db") as state:
        session = state.new_session("large latest")
        latest = [{"role": "user", "content": "latest " * 1000}]
        if tool_batch:
            latest = [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps({"content": "latest " * 1000}),
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call", "content": "saved"},
            ]
        history = [
            {"role": "user", "content": "earlier " * 1000},
            {"role": "assistant", "content": "acknowledged"},
            *latest,
        ]
        result = ContextWindow(state, session, max_chars=10000).prepare(history)
        assert result[-len(latest) :] == latest
        assert len(json.dumps(result)) <= 10000
        assert "read_history" in result[0]["content"]


def test_escaped_excerpt_obeys_serialized_limit_and_preserves_history(tmp_path):
    with StateStore(tmp_path / "state.db") as state:
        session = state.new_session("unicode")
        history = [{"role": "user", "content": "漢字" * 3000}]
        history.append({"role": "user", "content": "continue"})
        for message in history:
            state.append(session, message)
        result = ContextWindow(state, session, max_chars=10000).prepare(history)
        assert len(json.dumps(result)) <= 10000
        assert result[-1] == history[-1]
        assert "漢字" in result[0]["content"]
        assert state.messages(session) == history
        assert ContextWindow(state, session, max_chars=10000).prepare(history) == result


def test_oversized_latest_message_is_rejected_without_changing_history(tmp_path):
    with StateStore(tmp_path / "state.db") as state:
        session = state.new_session("oversized")
        history = [{"role": "user", "content": "large" * 3000}]
        state.append(session, history[0])
        with pytest.raises(ValueError, match="context limit"):
            ContextWindow(state, session, max_chars=10000).prepare(history)
        assert state.messages(session) == history


@pytest.mark.parametrize("count", [1, 2])
def test_latest_tool_result_is_delivered_intact_after_compaction(tmp_path, count):
    with StateStore(tmp_path / "state.db") as state:
        session = state.new_session("latest output")
        result = {"role": "tool", "tool_call_id": "read", "content": "x" * 3000 + "NEEDED"}
        call = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "read",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                }
            ],
        }
        call["tool_calls"] = [dict(call["tool_calls"][0], id=f"read{i}") for i in range(count)]
        results = [dict(result, tool_call_id=f"read{i}") for i in range(count)]
        history = [{"role": "user", "content": "old " * 4000}, call, *results]
        compacted = ContextWindow(state, session, max_chars=10000).prepare(history)
        assert compacted[-count - 1 :] == [call, *results]
        assert len(json.dumps(compacted)) <= 10000


async def test_compacted_artifact_can_be_retrieved_after_restart(tmp_path):
    from banger.permissions import Mode, PermissionPolicy
    from banger.tools import Toolbox

    database = tmp_path / ".banger/state.db"
    output = {"value": "x" * 61000 + "NEEDED"}
    with StateStore(database) as state:
        session = state.new_session("saved output")
        state.put_artifact("tool-output", "durable", output)
        history = [
            {"role": "user", "content": "inspect"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "read",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "read",
                "content": json.dumps(
                    {"preview": "x" * 58000, "truncated": True, "saved_artifact": "durable"}
                ),
            },
            {"role": "user", "content": "recover the tail"},
        ]
        for message in history:
            state.append(session, message)
    with StateStore(database) as state:
        compacted = ContextWindow(state, session, max_chars=10000).prepare(state.messages(session))
        excerpt = json.loads(next(m["content"] for m in compacted if m["role"] == "tool"))
        assert excerpt["saved_artifact"] == "durable"
        assert excerpt["retrieve_with"] == "read_tool_output"
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        toolbox.session = session
        recovered = await toolbox.invoke(
            "read_tool_output",
            {"artifact": excerpt["saved_artifact"], "start": 61000, "length": 1000},
        )
        assert recovered["content"] == json.dumps(output, ensure_ascii=False)[61000:62000]
        assert "NEEDED" in recovered["content"]
        assert state.messages(session) == history
