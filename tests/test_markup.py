import pytest

from banger.markup import MarkupIndex


def test_html_css_specificity_important_and_dom_references(tmp_path):
    (tmp_path / "index.html").write_text(
        '<link rel="stylesheet" href="site.css"><main><button id="save" class="primary" '
        'style="padding: 2px">Save</button></main><script>document.querySelector("#save")</script>'
    )
    (tmp_path / "site.css").write_text(
        "button { color: black; padding: 1px; } .primary { color: blue; } "
        "#save { color: red; } main > button.primary { padding: 8px !important; }"
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    matches = index.query("#save")
    assert len(matches) == 1
    cascade = index.styles(matches[0]["id"])
    assert cascade["computed"]["color"]["value"] == "red"
    assert cascade["computed"]["padding"]["value"] == "8px"
    assert index.dom_references("#save")[0]["path"] == "index.html"


def test_css_is_scoped_to_linked_document_and_embedded_python_markup(tmp_path):
    (tmp_path / "a.html").write_text('<style>p { color: green; }</style><p id="a">A</p>')
    (tmp_path / "b.html").write_text('<p id="b">B</p>')
    (tmp_path / "web.py").write_text('PAGE = """<div id="embedded">Hi</div>"""\n')
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.query("#embedded")[0]["path"] == "web.py"
    assert index.styles(index.query("#a")[0]["id"])["computed"]["color"]["value"] == "green"
    assert index.styles(index.query("#b")[0]["id"])["computed"] == {}


def test_unsupported_dynamic_css_is_declared(tmp_path):
    (tmp_path / "a.html").write_text(
        "<style>@media (max-width: 500px) { p { color: red; } } "
        "p:hover { color: blue; }</style><p>Hi</p>"
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["unresolved"]
    assert "color" not in styles["computed"]


def test_inherited_properties_and_css_variables(tmp_path):
    (tmp_path / "a.html").write_text(
        "<html><head><style>:root { --accent: teal; color: black; } "
        "main { color: var(--accent); } button { padding: var(--space, 4px); }</style></head>"
        '<body><main><button id="button">Save</button></main></body></html>'
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    values = index.styles(index.query("#button")[0]["id"])["computed"]
    assert values["color"]["value"] == "teal"
    assert values["color"]["inherited_from"]
    assert values["padding"]["value"] == "4px"


def test_custom_properties_are_resolved_before_inheritance(tmp_path):
    (tmp_path / "a.html").write_text(
        "<style>main { --base: red; --accent: var(--base); }"
        "p { --base: blue; color: var(--accent); COLOR: var(--accent); }</style>"
        "<main><p>Text</p></main>"
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    values = index.styles(index.query("p")[0]["id"])["computed"]
    assert values["color"]["value"] == "red"
    assert "COLOR" not in values
    assert values["--accent"]["value"] == "red"


def test_cyclic_variables_are_invalid_but_consumers_can_use_fallback(tmp_path):
    (tmp_path / "a.html").write_text(
        "<style>p { --a: var(--b); --b: var(--a); color: var(--a, green); }</style><p>Text</p>"
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    result = index.styles(index.query("p")[0]["id"])
    assert result["computed"]["color"]["value"] == "green"
    assert "--a" not in result["computed"] and "--b" not in result["computed"]
    assert result["unresolved"]


@pytest.mark.parametrize("selector", ['[data-value^="x"]', '[data-value=""]'])
def test_attribute_selectors_do_not_silently_match_every_element(tmp_path, selector):
    (tmp_path / "a.html").write_text('<p data-value="x">Text</p><p>Other</p>')
    index = MarkupIndex(tmp_path)
    index.refresh()
    if "^=" in selector:
        with pytest.raises(ValueError, match="Unsupported"):
            index.query(selector)
    else:
        assert index.query(selector) == []
