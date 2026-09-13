import pytest

from banger.index import CodeIndex
from banger.state import StateStore


@pytest.mark.parametrize(
    "sources,expressions,targets",
    [
        (
            {
                "Base.java": "package lib;\nclass Base<T> {}\ninterface Face<T> {}\n",
                "Child.java": "package app; import lib.Base; import lib.Face;\nclass Child extends Base<java.util.List<String>> implements Face<Integer> {}\n",
            },
            ["Base<java.util.List<String>>", "Face<Integer>"],
            ["Base.java:2:Base", "Base.java:3:Face"],
        ),
        (
            {
                "Base.cs": "namespace Lib {\nclass Base {}\nclass Base<T> {}\nclass Base<T,U> {}\ninterface Face<T> {}\n}\n",
                "Child.cs": "using Lib;\nclass Child : Base<System.Collections.Generic.List<string>>, Lib.Face<int> {}\n",
            },
            ["Base<System.Collections.Generic.List<string>>", "Lib.Face<int>"],
            ["Base.cs:3:Base", "Base.cs:5:Face"],
        ),
        (
            {
                "base.ts": "export class Base<T> {}\nexport interface Face<T> {}\n",
                "child.ts": "import {Base as Parent, Face} from './base';\nclass Child extends Parent<Array<string>> implements Face<number> {}\n",
            },
            ["Parent<Array<string>>", "Face<number>"],
            ["base.ts:1:Base", "base.ts:2:Face"],
        ),
        (
            {
                "base.ts": "export interface Face<T> {}\n",
                "child.ts": "import * as lib from './base';\ninterface Child extends lib.Face<Array<string>> {}\n",
            },
            ["lib.Face<Array<string>>"],
            ["base.ts:1:Face"],
        ),
    ],
)
def test_parameterized_bases_link_nominal_declarations_and_persist(
    tmp_path, sources, expressions, targets
):
    for filename, source in sources.items():
        (tmp_path / filename).write_text(source, encoding="utf-8")
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        result = index.get_hierarchy("Child")
        assert result["bases"] == expressions
        for link, expression, target in zip(
            result["base_links"], expressions, targets, strict=True
        ):
            assert link["expression"] == expression
            assert link["resolution"] == "resolved"
            assert link["targets"] == [target]
            assert [s["name"] for s in index.get_hierarchy(target)["subclasses"]] == ["Child"]
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        assert index.get_hierarchy("Child") == result


def test_csharp_nongeneric_base_does_not_bind_same_name_generic_type(tmp_path):
    (tmp_path / "types.cs").write_text(
        "class Base {}\nclass Base<T> {}\nclass Child : Base {}\n", encoding="utf-8"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "resolved"
    assert link["targets"] == ["types.cs:1:Base"]
    assert index.get_hierarchy("types.cs:2:Base")["subclasses"] == []


def test_computed_typescript_superclass_is_not_reduced_to_argument_type(tmp_path):
    (tmp_path / "types.ts").write_text(
        "class Base<T> {}\nclass Child extends factory<Base<string>>() {}\n", encoding="utf-8"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    result = index.get_hierarchy("Child")
    assert result["bases"] == ["factory<Base<string>>()"]
    assert result["base_links"][0]["resolution"] == "unknown"
    assert result["base_links"][0]["targets"] == []


def test_csharp_generic_argument_count_selects_type_and_refreshes(tmp_path):
    target = tmp_path / "types.cs"
    target.write_text(
        "class Base<T> {}\nclass Base<T,U> {}\nclass Child : Base<int, string> {}\n",
        encoding="utf-8",
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    assert index.get_hierarchy("Child")["base_links"][0]["targets"] == ["types.cs:2:Base"]
    target.write_text("class Base<T> {}\nclass Child : Base<int, string> {}\n", encoding="utf-8")
    index.refresh()
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "unknown"
    assert link["targets"] == []


def test_java_raw_base_can_reference_generic_declaration(tmp_path):
    (tmp_path / "types.java").write_text(
        "class Base<T> {}\nclass Child extends Base {}\n", encoding="utf-8"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "resolved"
    assert link["targets"] == ["types.java:1:Base"]


def test_csharp_generic_import_ambiguity_is_retained(tmp_path):
    (tmp_path / "types.cs").write_text(
        "namespace A { class Base<T> {} }\nnamespace B { class Base<T> {} }\n",
        encoding="utf-8",
    )
    (tmp_path / "child.cs").write_text(
        "using A; using B;\nclass Child : Base<int> {}\n", encoding="utf-8"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "ambiguous"
    assert link["targets"] == ["types.cs:1:Base", "types.cs:2:Base"]


@pytest.mark.parametrize(
    "extension,child",
    [("java", "class Child<Base> extends Base {}"), ("cs", "class Child<Base> : Base {}")],
)
def test_type_parameter_is_not_mistaken_for_global_class(tmp_path, extension, child):
    (tmp_path / f"types.{extension}").write_text("class Base {}\n" + child, encoding="utf-8")
    index = CodeIndex(tmp_path)
    index.refresh()
    assert index.get_hierarchy("Child")["base_links"][0]["resolution"] != "resolved"
