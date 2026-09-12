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
