import pytest

from banger.index import CodeIndex
from banger.state import StateStore


def make_index(tmp_path, sources, state=None):
    for name, source in sources.items():
        (tmp_path / name).write_text(source)
    index = CodeIndex(tmp_path, state)
    index.refresh()
    return index


def test_cpp_bases_preserve_qualified_names_and_ignore_access_modifiers(tmp_path):
    index = make_index(
        tmp_path,
        {
            "types.cpp": "namespace library {\nstruct Base {};\nstruct Face {};\n}\n"
            "class Child : public virtual library::Base, private ::library::Face {};\n",
        },
    )
    hierarchy = index.get_hierarchy("Child")
    assert hierarchy["bases"] == ["library::Base", "::library::Face"]
    assert [link["targets"] for link in hierarchy["base_links"]] == [
        ["types.cpp:2:Base"],
        ["types.cpp:3:Face"],
    ]
    assert all(link["resolution"] == "resolved" for link in hierarchy["base_links"])


def test_cpp_nearest_namespace_and_nested_class_scope(tmp_path):
    index = make_index(
        tmp_path,
        {
            "types.cpp": "struct Base {};\nnamespace outer::inner {\nstruct Base {};\n"
            "struct Child : Base {};\nclass Container {\nstruct Base {};\n"
            "struct Nested : Base {};\n};\n}\n"
            "struct Global : ::Base {};\n",
        },
    )
    for name, target in (
        ("Child", "types.cpp:3:Base"),
        ("Nested", "types.cpp:6:Base"),
        ("Global", "types.cpp:1:Base"),
    ):
        link = index.get_hierarchy(name)["base_links"][0]
        assert link["resolution"] == "resolved"
        assert link["targets"] == [target]
        assert [s["name"] for s in index.get_hierarchy(target)["subclasses"]] == [name]


def test_cpp_template_base_remains_one_unresolved_expression(tmp_path):
    index = make_index(
        tmp_path,
        {"types.cpp": "template<class T> struct Box {};\nstruct Child : public Box<int> {};\n"},
    )
    hierarchy = index.get_hierarchy("Child")
    assert hierarchy["bases"] == ["Box<int>"]
    assert hierarchy["base_links"][0]["resolution"] == "unknown"
    assert hierarchy["base_links"][0]["targets"] == []


@pytest.mark.parametrize(
    "source",
    [
        "struct Base;\nstruct Child : Base {};\n",
        "#if FEATURE\nstruct Base {};\n#endif\nstruct Child : Base {};\n",
        "struct Base {};\ntemplate<class T> struct Child : Base {};\n",
        "struct Child : Base {};\nstruct Base {};\n",
    ],
)
def test_cpp_incomplete_conditional_template_and_late_bases_are_not_proven(tmp_path, source):
    index = make_index(tmp_path, {"types.cpp": source})
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] != "resolved"
    assert index.get_hierarchy("Base")["subclasses"] == []


@pytest.mark.parametrize(
    "binding",
    ["using Base = Other;", "typedef Other Base;", "using other::Base;", "using namespace other;"],
)
def test_cpp_unexpanded_type_binding_does_not_resolve_to_outer_base(tmp_path, binding):
    index = make_index(
        tmp_path,
        {
            "types.cpp": "struct Base {};\nnamespace local {\n"
            + binding
            + "\nstruct Child : Base {};\n}\n"
        },
    )
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "unknown"
    assert "binding" in link["evidence"]
    assert index.get_hierarchy("Base")["subclasses"] == []


def test_cpp_other_translation_units_are_candidates_not_visible_declarations(tmp_path):
    index = make_index(
        tmp_path,
        {
            "base.cpp": "namespace library {\nstruct Base {};\n}\n",
            "unrelated.cpp": "namespace other {\nstruct Base {};\n}\n",
            "child.cpp": "struct Child : library::Base {};\n",
        },
    )
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "ambiguous"
    assert link["targets"] == ["base.cpp:2:Base"]
    assert index.get_hierarchy("base.cpp:2:Base")["subclasses"] == []
    assert index.get_hierarchy("unrelated.cpp:2:Base")["candidate_subclasses"] == []


def test_cpp_relative_qualifier_does_not_skip_a_shadowing_namespace(tmp_path):
    index = make_index(
        tmp_path,
        {
            "types.cpp": "namespace library {\nstruct Base {};\n}\nnamespace local {\n"
            "namespace library {}\nstruct Child : library::Base {};\n}\n"
        },
    )
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "unknown"
    assert link["targets"] == []


def test_cpp_function_local_classes_do_not_leak_into_other_functions(tmp_path):
    index = make_index(
        tmp_path,
        {
            "types.cpp": "void left() {\nstruct Base {};\n}\nvoid right() {\nstruct Child : Base {};\n}\n"
        },
    )
    assert index.get_hierarchy("Child")["base_links"][0]["resolution"] == "unknown"


def test_cpp_scope_metadata_survives_cached_restart_and_refresh(tmp_path):
    with StateStore(tmp_path / ".banger/state.db") as state:
        make_index(
            tmp_path,
            {"types.cpp": "namespace library {\nstruct Base {};\nstruct Child : Base {};\n}\n"},
            state,
        )
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        assert index.refresh()["changed"] == 0
        assert index.get_hierarchy("Child")["base_links"][0]["resolution"] == "resolved"
        (tmp_path / "types.cpp").write_text(
            "namespace other {\nstruct Base {};\n}\nstruct Child : library::Base {};\n"
        )
        assert index.refresh()["changed"] == 1
        assert index.get_hierarchy("Child")["base_links"][0]["targets"] == []
