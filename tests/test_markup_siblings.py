import pytest

from banger.markup import MarkupIndex
from banger.permissions import Mode, PermissionPolicy
from banger.state import StateStore
from banger.tools import Toolbox


@pytest.fixture
def markup(tmp_path):
    (tmp_path / "a.html").write_text(
        '<main><h2 id="heading">Title</h2>text<!-- comment -->'
        '<p id="first"><span id="inside"></span></p><hr><p id="later"></p>'
        '<section><p id="nested"></p></section></main><p id="outside"></p>'
    )
    (tmp_path / "b.html").write_text('<p id="separate"></p>')
    index = MarkupIndex(tmp_path)
    index.refresh()
    return index


@pytest.mark.parametrize(
    "selector,expected",
    [
        ("h2+p", ["first"]),
        ("h2 ~ p", ["first", "later"]),
        ("main > h2 + p span", ["inside"]),
        ("h2~p+section > p", ["nested"]),
        ("p + h2", []),
        ("main > h2 ~ section p", ["nested"]),
    ],
)
def test_sibling_combinators_follow_element_order_and_parent_scope(markup, selector, expected):
    assert [n["attributes"]["id"] for n in markup.query(selector)] == expected


def test_sibling_specificity_participates_in_cascade(tmp_path):
    (tmp_path / "a.html").write_text(
        "<style>p {color:black} h2+p {color:red} h2~p.note {color:green}</style>"
        '<h2></h2><p id="first"></p><p id="later" class="note"></p>'
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.specificity("h2+p") == (0, 0, 2)
    assert index.specificity("h2~p.note") == (0, 1, 2)
    assert index.styles(index.query("#first")[0]["id"])["computed"]["color"]["value"] == "red"
    assert index.styles(index.query("#later")[0]["id"])["computed"]["color"]["value"] == "green"


@pytest.mark.parametrize("selector", ["+p", "p+", "p++p", "p ~ > p"])
def test_incomplete_sibling_selectors_are_rejected(markup, selector):
    with pytest.raises(ValueError):
        markup.query(selector)


async def test_markup_tool_updates_siblings_in_embedded_python_after_edit(tmp_path):
    path = tmp_path / "web.py"
    path.write_text('PAGE = "<h2></h2><p id=first></p><p id=second></p>"\n')
    with StateStore(tmp_path / ".banger/state.db") as state:
        toolbox = Toolbox(tmp_path, state, PermissionPolicy(tmp_path, Mode.READ_ONLY))
        result = await toolbox.invoke("query_markup", {"selector": "h2+p"})
        assert [n["attributes"]["id"] for n in result["elements"]] == ["first"]
        path.write_text('PAGE = "<h2></h2><hr><p id=first></p><p id=second></p>"\n')
        result = await toolbox.invoke("query_markup", {"selector": "h2+p"})
        assert result["elements"] == []
        result = await toolbox.invoke("query_markup", {"selector": "h2~p"})
        assert [n["attributes"]["id"] for n in result["elements"]] == ["first", "second"]
