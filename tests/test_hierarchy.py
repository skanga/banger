import pytest

from banger.index import CodeIndex


def build(tmp_path, sources):
    for filename, source in sources.items():
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    index = CodeIndex(tmp_path)
    index.refresh()
    return index


def test_import_alias_selects_base_without_same_name_false_subclasses(tmp_path):
    index = build(
        tmp_path,
        {
            "left.py": "class Base: pass\n",
            "right.py": "class Base: pass\n",
            "child.py": "from left import Base as Parent\nclass Child(Parent): pass\n",
        },
    )
    child = index.get_hierarchy("Child")
    assert child["bases"] == ["Parent"]
    assert child["base_links"][0]["targets"] == ["left.py:1:Base"]
    assert child["base_links"][0]["resolution"] == "resolved"
    assert [s["name"] for s in index.get_hierarchy("left.py:1:Base")["subclasses"]] == ["Child"]
    assert index.get_hierarchy("right.py:1:Base")["subclasses"] == []


def test_dotted_base_expression_and_src_layout(tmp_path):
    index = build(
        tmp_path,
        {
            "src/pkg/types.py": "class Base: pass\n",
            "child.py": "import pkg.types as types\nclass Child(types.Base): pass\n",
        },
    )
    result = index.get_hierarchy("Child")
    assert result["bases"] == ["types.Base"]
    assert result["base_links"][0]["targets"] == ["src/pkg/types.py:1:Base"]


def test_unknown_base_candidates_are_not_reported_as_resolved_subclasses(tmp_path):
    index = build(
        tmp_path,
        {
            "left.py": "class Base: pass\n",
            "right.py": "class Base: pass\n",
            "child.py": "class Child(Base): pass\nclass Dynamic(factory(Base)): pass\n",
        },
    )
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "ambiguous"
    assert len(link["targets"]) == 2
    assert index.get_hierarchy("left.py:1:Base")["subclasses"] == []
    assert len(index.get_hierarchy("left.py:1:Base")["candidate_subclasses"]) == 1
    dynamic = index.get_hierarchy("Dynamic")
    assert dynamic["bases"] == ["factory(Base)"]
    assert dynamic["base_links"][0]["resolution"] == "unknown"


def test_nearest_enclosing_scope_and_refresh_invalidate_hierarchy(tmp_path):
    index = build(
        tmp_path,
        {
            "a.py": "class Base: pass\ndef scope():\n class Base: pass\n class Child(Base): pass\n",
        },
    )
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["targets"] == ["a.py:3:Base"]
    (tmp_path / "a.py").write_text("class Other: pass\nclass Child(Other): pass\n")
    index.refresh()
    assert index.get_hierarchy("Child")["base_links"][0]["targets"] == ["a.py:1:Other"]


def test_rebound_or_parameter_base_is_not_proven(tmp_path):
    index = build(
        tmp_path,
        {
            "a.py": "class Base: pass\nBase = factory()\nclass Child(Base): pass\n"
            "def scope(Base):\n class Nested(Base): pass\n",
        },
    )
    for name in ("Child", "Nested"):
        link = index.get_hierarchy(name)["base_links"][0]
        assert link["resolution"] != "resolved"
        assert "binding" in link["evidence"]
    assert index.get_hierarchy("Base")["subclasses"] == []


@pytest.mark.parametrize(
    "sources,expected",
    [
        (
            {
                "Base.java": "package lib; class Base {} interface Face {}",
                "Child.java": "package app; import lib.Base; import lib.Face; class Child extends Base implements Face {}",
            },
            ["Base", "Face"],
        ),
        (
            {
                "Base.java": "package lib; class Base {}",
                "Child.java": "package app; class Child extends lib.Base {}",
            },
            ["lib.Base"],
        ),
        (
            {
                "Base.cs": "namespace Lib { class Base {} interface Face {} }",
                "Child.cs": "using Lib; namespace App { class Child : Base, Face {} }",
            },
            ["Base", "Face"],
        ),
        (
            {
                "base.js": "export default class Base {}",
                "child.js": "import Parent from './base'; class Child extends Parent {}",
            },
            ["Parent"],
        ),
        (
            {
                "base.ts": "export class Base {} export interface Face {}",
                "child.ts": "import * as lib from './base'; class Child extends lib.Base implements lib.Face {}",
            },
            ["lib.Base", "lib.Face"],
        ),
        ({"child.ts": "class Base {} class Child extends Base {}"}, ["Base"]),
    ],
)
def test_language_specific_base_bindings(tmp_path, sources, expected):
    index = build(tmp_path, sources)
    hierarchy = index.get_hierarchy("Child")
    assert hierarchy["bases"] == expected
    assert len(hierarchy["base_links"]) == len(expected)
    for link in hierarchy["base_links"]:
        assert link["resolution"] == "resolved"
        assert len(link["targets"]) == 1
        assert index.get_hierarchy(link["targets"][0])["subclasses"][0]["name"] == "Child"


def test_csharp_imported_namespace_ambiguity_is_preserved(tmp_path):
    index = build(
        tmp_path,
        {
            "A.cs": "namespace A { class Base {} }",
            "B.cs": "namespace B { class Base {} }",
            "Child.cs": "using A; using B; class Child : Base {}",
        },
    )
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "ambiguous"
    assert len(link["targets"]) == 2


def test_csharp_multiple_namespaces_use_each_declarations_namespace(tmp_path):
    index = build(
        tmp_path,
        {
            "types.cs": "namespace A { class Base {} }\nnamespace B { class Base {} }\n",
            "child.cs": "class Child : A.Base {}",
        },
    )
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "resolved"
    assert link["targets"] == ["types.cs:1:Base"]
