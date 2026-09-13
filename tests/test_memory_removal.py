import pytest

from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


async def test_forget_fact_is_exact_and_survives_restart(tmp_path):
    database = tmp_path / ".banger/state.db"
    key = "stale'; DELETE FROM memory; --"
    with StateStore(database) as state:
        state.set_memory(key, "old guidance")
        state.set_memory("keep", "current guidance")
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.ACCEPT_EDITS))
        result = await tools.invoke("forget_fact", {"key": key})
        assert result == {"key": key, "removed": True}
        assert await tools.recall_memory() == {"keep": "current guidance"}
        assert await tools.invoke("forget_fact", {"key": key}) == {"key": key, "removed": False}
    with StateStore(database) as state:
        assert state.memories() == {"keep": "current guidance"}


@pytest.mark.parametrize(
    "mode,answer,removed",
    [(Mode.READ_ONLY, "allow", False), (Mode.ASK, "deny", False), (Mode.ASK, "allow", True)],
)
async def test_forget_fact_obeys_memory_edit_permissions(tmp_path, mode, answer, removed):
    requests = []
    with StateStore(tmp_path / ".banger/state.db") as state:
        state.set_memory("convention", "stale convention")

        async def approve(action, detail):
            assert state.memories() == {"convention": "stale convention"}
            requests.append((action, detail))
            return answer

        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, mode), approve)
        result = await tools.invoke("forget_fact", {"key": "convention"})
        if removed:
            assert result == {"key": "convention", "removed": True}
            assert state.memories() == {}
        else:
            assert "error" in result
            assert state.memories() == {"convention": "stale convention"}
        assert len(requests) == (0 if mode == Mode.READ_ONLY else 1)
        if requests:
            assert requests[0][0].kind == "edit"
            assert requests[0][0].path == ".banger/memory"
            assert "convention" in requests[0][1]
