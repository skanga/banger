import pytest

from banger.index import CodeIndex
from banger.state import StateStore


def build(tmp_path, source):
    (tmp_path / "types.rb").write_text(source, encoding="utf-8")
    index = CodeIndex(tmp_path)
    index.refresh()
    return index


@pytest.mark.parametrize(
    "source,child,expression,target",
    [
        ("class Base; end\nclass Child < Base; end\n", "Child", "Base", "types.rb:1:Base"),
        (
            "class Base; end\nmodule A\n class Base; end\n class Child < Base; end\nend\n",
            "Child",
            "Base",
            "types.rb:3:Base",
        ),
        (
            "module A\n class Base; end\nend\nclass Child < A::Base; end\n",
            "Child",
            "A::Base",
            "types.rb:2:Base",
        ),
        (
            "class Base; end\nmodule A\n class Base; end\n class Child < ::Base; end\nend\n",
            "Child",
            "::Base",
            "types.rb:1:Base",
        ),
        (
            "module A\n class Base; end\n module B\n  class Child < Base; end\n end\nend\n",
            "Child",
            "Base",
            "types.rb:2:Base",
        ),
        (
            "class Base; end\nmodule A\n class Base; end\nend\nclass A::Child < Base; end\n",
            "A::Child",
            "Base",
            "types.rb:1:Base",
        ),
    ],
)
def test_ruby_constant_superclass_binding(tmp_path, source, child, expression, target):
    index = build(tmp_path, source)
    hierarchy = index.get_hierarchy(child)
    assert hierarchy["bases"] == [expression]
    link = hierarchy["base_links"][0]
    assert link["resolution"] == "resolved"
    assert link["targets"] == [target]
    assert [s["name"] for s in index.get_hierarchy(target)["subclasses"]] == [child]


@pytest.mark.parametrize(
    "source,expression",
    [
        ("class Base; end\nclass Child < factory(Base); end\n", "factory(Base)"),
        ("class Base; end\nBase = factory()\nclass Child < Base; end\n", "Base"),
        ("if flag\n class Base; end\nend\nclass Child < Base; end\n", "Base"),
        ("class Child < Base; end\nclass Base; end\n", "Base"),
        ("class Base; end\nclass Base; end\nclass Child < Base; end\n", "Base"),
        ("class Base; end\nif flag\n class Child < Base; end\nend\n", "Base"),
        (
            (
                "class Base; end\nmodule M\n class Base; end\nend\n"
                "class Outer\n include M\n class Child < Base; end\nend\n"
            ),
            "Base",
        ),
        (
            "module A\n class Base; end\nend\nA = factory()\nclass Child < A::Base; end\n",
            "A::Base",
        ),
        (
            "module A\n class Base; end\nend\nmodule B\n module A; end\n class Child < A::Base; end\nend\n",
            "A::Base",
        ),
    ],
)
def test_ruby_unproven_bases_do_not_create_resolved_subclasses(tmp_path, source, expression):
    index = build(tmp_path, source)
    hierarchy = index.get_hierarchy("Child")
    assert hierarchy["bases"] == [expression]
    assert hierarchy["base_links"][0]["resolution"] != "resolved"
    for symbol in index.symbols.values():
        assert index.get_hierarchy(symbol["id"])["subclasses"] == []


def test_ruby_cross_file_candidates_and_persisted_refresh(tmp_path):
    (tmp_path / "base.rb").write_text("class Base; end\n", encoding="utf-8")
    target = tmp_path / "child.rb"
    target.write_text("class Child < Base; end\n", encoding="utf-8")
    state_path = tmp_path / ".banger/state.db"
    with StateStore(state_path) as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        link = index.get_hierarchy("Child")["base_links"][0]
        assert link["resolution"] == "ambiguous"
        assert link["targets"] == ["base.rb:1:Base"]
    with StateStore(state_path) as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        assert index.get_hierarchy("Child")["base_links"][0] == link
        target.write_text("class Local; end\nclass Child < Local; end\n", encoding="utf-8")
        index.refresh()
        assert index.get_hierarchy("Child")["base_links"][0]["targets"] == ["child.rb:1:Local"]
        assert index.get_hierarchy("Child")["base_links"][0]["resolution"] == "resolved"


def test_ruby_inherited_constants_are_not_replaced_by_global_names(tmp_path):
    index = build(
        tmp_path,
        "class Base; end\nclass Parent\n class Base; end\nend\n"
        "class Outer < Parent\n class Child < Base; end\nend\n",
    )
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] != "resolved"
    assert index.get_hierarchy("types.rb:1:Base")["subclasses"] == []


def test_ruby_qualified_cross_file_base_retains_candidates(tmp_path):
    (tmp_path / "base.rb").write_text("module A\n class Base; end\nend\n", encoding="utf-8")
    index = build(tmp_path, "module A; end\nclass Child < A::Base; end\n")
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "ambiguous"
    assert link["targets"] == ["base.rb:2:Base"]
