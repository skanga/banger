from banger.markup import MarkupIndex
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


def test_fstring_is_one_template_with_static_structure_and_explicit_uncertainty(tmp_path):
    (tmp_path / "web.py").write_text(
        'PAGE = f"<main><p id=first>{message}</p><p id=last>End</p></main>"\n'
    )
    index = MarkupIndex(tmp_path)
    assert index.refresh()["documents"] == 1
    elements = index.query("main > p")
    assert [n["attributes"]["id"] for n in elements] == ["first", "last"]
    assert all(n["dynamic"] for n in elements)
    assert len({n["document"] for n in elements}) == 1
    assert index.unresolved[0]["expressions"] == ["message"]
    assert index.unresolved[0]["path"] == "web.py"


def test_dynamic_styles_keep_static_candidates_and_do_not_execute_interpolation(tmp_path):
    (tmp_path / "web.py").write_text(
        'def danger(): raise RuntimeError("must not execute")\n'
        'PAGE = f"<style>p {{color:red}}</style><main>{danger()}<p id=target></p></main>"\n'
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    node = index.query("main > p")[0]
    styles = index.styles(node["id"])
    assert styles["computed"]["color"]["value"] == "red"
    assert styles["unresolved"][0]["expressions"] == ["danger()"]
    assert "template" in styles["scope"]


async def test_markup_tool_reports_unknown_dynamic_attribute_even_without_match(tmp_path):
    (tmp_path / "web.py").write_text('PAGE = f"<p class={kind}>Text</p>"\n')
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await toolbox.invoke("query_markup", {"selector": ".warning"})
        assert result["elements"] == []
        assert result["unresolved"][0]["expressions"] == ["kind"]


def test_plain_literal_keeps_exact_mapping_without_dynamic_warning(tmp_path):
    (tmp_path / "web.py").write_text('PAGE = "<p>Text</p>"\n')
    index = MarkupIndex(tmp_path)
    index.refresh()
    node = index.query("p")[0]
    assert node["source_mapping"] == "exact literal"
    assert node["dynamic"] is False
    assert index.unresolved == []


def test_dynamic_tag_names_remain_visible_as_unresolved_templates(tmp_path):
    (tmp_path / "web.py").write_text('PAGE = f"<{tag}>Text</{tag}>"\n')
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.query("p") == []
    assert index.unresolved[0]["expressions"] == ["tag", "tag"]


def test_nested_format_expression_is_reported_without_extra_documents(tmp_path):
    (tmp_path / "web.py").write_text('PAGE = f"<p>{number:{width}}</p>"\n')
    index = MarkupIndex(tmp_path)
    assert index.refresh()["documents"] == 1
    assert index.unresolved[0]["expressions"] == ["number", "width"]
