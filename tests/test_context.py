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
