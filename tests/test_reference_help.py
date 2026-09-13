from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


async def test_language_reference_reports_extensions_and_python_only_tracing(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await tools.invoke("read_reference", {"topic": "languages"})
        assert "error" not in result, result
        languages = {item["language"]: item for item in result["languages"]}
        assert languages["python"]["extensions"] == [".py"]
        assert ".go" in languages["go"]["extensions"]
        assert ".rs" in languages["rust"]["extensions"]
        assert ".html" in languages["html"]["extensions"]
        assert [name for name, value in languages.items() if value["runtime_tracing"]] == ["python"]
        assert result["resolution_levels"] == ["resolved", "ambiguous", "external", "unknown"]


async def test_reference_tool_contracts_and_artifact_recovery_are_callable(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        overview = await tools.invoke("read_reference", {})
        assert {"languages", "artifact", "tools"} <= set(overview["topics"])
        contracts = await tools.invoke("read_reference", {"topic": "tools"})
        assert contracts["tools"] == tools.schemas()
        reference = await tools.invoke("read_reference", {"topic": "artifact"})
        assert {"read_tool_output", "read_history", "get_runtime_trace", "get_plan"} <= set(
            reference["recovery_tools"]
        )
        assert all(name in tools.registry for name in reference["recovery_tools"])
        assert "error" in await tools.invoke("read_reference", {"topic": "missing"})
