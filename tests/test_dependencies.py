import json

import pytest

from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


@pytest.mark.parametrize(
    "filename,content,section,expected",
    [
        (
            "pyproject.toml",
            '[project]\ndependencies=["httpx>=0.28"]\n',
            "project.dependencies",
            ["httpx>=0.28"],
        ),
        (
            "package.json",
            '{"devDependencies":{"typescript":"^5"}}',
            "devDependencies",
            {"typescript": "^5"},
        ),
        (
            "Cargo.toml",
            '[dependencies]\nserde={version="1", features=["derive"]}\n',
            "dependencies",
            {"serde": {"version": "1", "features": ["derive"]}},
        ),
        (
            "go.mod",
            "module example/app\nrequire (\n example/lib v1.2.3 // indirect\n)\n",
            "require",
            ["example/lib v1.2.3 // indirect"],
        ),
        (
            "requirements.txt",
            "httpx>=0.28\n-r other.txt\n",
            "requirements",
            ["httpx>=0.28", "-r other.txt"],
        ),
        (
            "pom.xml",
            '<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies><dependency><groupId>org.demo</groupId><artifactId>lib</artifactId><version>${lib.version}</version></dependency></dependencies></project>',
            "dependencies",
            [{"groupId": "org.demo", "artifactId": "lib", "version": "${lib.version}"}],
        ),
        (
            "app.csproj",
            '<Project><ItemGroup><PackageReference Include="Example" Version="1.2" /></ItemGroup></Project>',
            "PackageReference",
            [{"Include": "Example", "Version": "1.2"}],
        ),
    ],
)
async def test_dependencies_preserve_declared_requirements(
    tmp_path, filename, content, section, expected
):
    (tmp_path / filename).write_text(content, encoding="utf-8")
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await tools.invoke("list_dependencies", {})
        assert "error" not in result, result
        assert result["basis"] == "declared; not installed or resolved"
        assert result["manifests"][0]["path"] == filename
        assert result["manifests"][0]["sections"][section] == expected
        assert result["truncated"] is False


async def test_dependencies_report_bad_and_executable_manifests(tmp_path):
    (tmp_path / "package.json").write_text("{")
    (tmp_path / "Gemfile").write_text("raise 'must not execute'\n")
    (tmp_path / "pyproject.toml").write_text(
        '[dependency-groups]\ndev=["pytest", {include-group="lint"}]\n'
    )
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await tools.invoke("list_dependencies", {})
        assert {item["path"] for item in result["unresolved"]} == {"Gemfile", "package.json"}
        manifest = result["manifests"][0]
        assert manifest["sections"]["dependency-groups"] == {
            "dev": ["pytest", {"include-group": "lint"}]
        }
        json.dumps(result)


async def test_dependency_manifests_refresh_and_preserve_conditions(tmp_path):
    (tmp_path / "nested").mkdir()
    manifest = tmp_path / "nested/package.json"
    manifest.write_text('{"dependencies":{"old":"1"}}')
    (tmp_path / "app.csproj").write_text(
        '<Project><ItemGroup Condition="UseExtras"><PackageReference Include="Extra"><Version>$(Version)</Version></PackageReference></ItemGroup></Project>'
    )
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await tools.list_dependencies()
        projects = {m["path"]: m["sections"] for m in result["manifests"]}
        assert projects["nested/package.json"]["dependencies"] == {"old": "1"}
        assert projects["app.csproj"]["PackageReference"] == [
            {
                "Include": "Extra",
                "Version": "$(Version)",
                "ancestor_attributes": [{"Condition": "UseExtras"}],
            }
        ]
        manifest.write_text('{"dependencies":{"new":"2"}}')
        updated = {m["path"]: m["sections"] for m in (await tools.list_dependencies())["manifests"]}
        assert updated["nested/package.json"]["dependencies"] == {"new": "2"}


async def test_dependency_manifest_size_limit_is_explicit(tmp_path):
    (tmp_path / "package.json").write_bytes(b" " * (1024 * 1024 + 1))
    with StateStore(tmp_path / ".banger/state.db") as state:
        tools = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await tools.list_dependencies()
        assert result["manifests"] == []
        assert result["unresolved"] == [
            {"path": "package.json", "reason": "Manifest or query byte limit"}
        ]
