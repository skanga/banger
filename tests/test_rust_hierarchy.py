import pytest

from banger.index import CodeIndex
from banger.state import StateStore


@pytest.mark.parametrize(
    "source,expressions,targets",
    [
        ("trait Child: Parent {}\ntrait Parent {}\n", ["Parent"], ["lib.rs:2:Parent"]),
        (
            "trait Parent<T> {}\ntrait Face {}\ntrait Child<T>: Parent<T> + 'static where Self: Face {}\n",
            ["Parent<T>", "Face"],
            ["lib.rs:1:Parent", "lib.rs:2:Face"],
        ),
        (
            "trait Parent {}\nmod inner {\n trait Parent {}\n trait Child: Parent {}\n}\n",
            ["Parent"],
            ["lib.rs:3:Parent"],
        ),
        (
            "trait Parent {}\nmod inner {\n trait Child: super::Parent {}\n}\n",
            ["super::Parent"],
            ["lib.rs:1:Parent"],
        ),
        (
            "mod types { pub trait Parent {} }\ntrait Child: crate::types::Parent {}\n",
            ["crate::types::Parent"],
            ["lib.rs:1:Parent"],
        ),
        (
            "mod types { pub trait Parent {} }\nuse self::types::Parent as Alias;\ntrait Child: Alias {}\n",
            ["Alias"],
            ["lib.rs:1:Parent"],
        ),
    ],
)
def test_rust_declared_supertraits_and_reverse_links(tmp_path, source, expressions, targets):
    (tmp_path / "lib.rs").write_text(source, encoding="utf-8")
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        result = index.get_hierarchy("Child")
        assert result["bases"] == expressions
        assert [link["targets"] for link in result["base_links"]] == [[t] for t in targets]
        assert all(link["resolution"] == "resolved" for link in result["base_links"])
        for target in targets:
            assert [s["name"] for s in index.get_hierarchy(target)["subclasses"]] == ["Child"]
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        assert index.get_hierarchy("Child") == result


@pytest.mark.parametrize(
    "source",
    [
        "trait Parent {}\nmod inner { trait Child: Parent {} }\n",
        '#[cfg(feature="optional")]\ntrait Parent {}\ntrait Child: Parent {}\n',
        "trait Parent {}\ntrait Parent {}\ntrait Child: Parent {}\n",
        "struct Parent;\ntrait Child: Parent {}\n",
    ],
)
def test_rust_uncertain_or_invalid_supertraits_do_not_create_resolved_links(tmp_path, source):
    (tmp_path / "lib.rs").write_text(source, encoding="utf-8")
    index = CodeIndex(tmp_path)
    index.refresh()
    result = index.get_hierarchy("Child")
    assert result["bases"] == ["Parent"]
    assert result["base_links"][0]["resolution"] != "resolved"


def test_rust_generic_parameter_bound_is_not_a_supertrait(tmp_path):
    (tmp_path / "lib.rs").write_text(
        "trait Parent {}\ntrait Child<T: Parent> {}\n", encoding="utf-8"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    assert index.get_hierarchy("Child")["bases"] == []


def test_rust_type_parameter_does_not_resolve_to_same_name_trait(tmp_path):
    (tmp_path / "lib.rs").write_text(
        "trait Parent {}\ntrait Child<Parent>: Parent {}\n", encoding="utf-8"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    assert index.get_hierarchy("Child")["base_links"][0]["resolution"] == "unknown"


def test_rust_external_module_candidates_and_refresh(tmp_path):
    (tmp_path / "types.rs").write_text("pub trait Parent {}\n", encoding="utf-8")
    target = tmp_path / "lib.rs"
    target.write_text("mod types;\ntrait Child: crate::types::Parent {}\n", encoding="utf-8")
    index = CodeIndex(tmp_path)
    index.refresh()
    link = index.get_hierarchy("Child")["base_links"][0]
    assert link["resolution"] == "ambiguous"
    assert link["targets"] == ["types.rs:1:Parent"]
    target.write_text("trait Local {}\ntrait Child: Local {}\n", encoding="utf-8")
    index.refresh()
    assert index.get_hierarchy("Child")["base_links"][0]["targets"] == ["lib.rs:1:Local"]
    assert index.get_hierarchy("Child")["base_links"][0]["resolution"] == "resolved"
