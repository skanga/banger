import pytest

from banger.markup import MarkupIndex


@pytest.fixture
def markup(tmp_path):
    (tmp_path / "page.html").write_text(
        '<p id="one" data-value="Alpha beta" lang="en-US" data-url="https://a,b/x?q=1+2" '
        'data-unicode="Ä" data-bracket="a]b"></p>'
        '<p id="two" data-value="alphabet" lang="en"></p>'
        '<p id="empty" data-value=""></p><p id="missing"></p>',
        encoding="utf-8",
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    return index


@pytest.mark.parametrize(
    "selector,expected",
    [
        ('[data-value^="Al"]', ["one"]),
        ('[data-value$="bet"]', ["two"]),
        ('[data-value*="pha"]', ["one", "two"]),
        ('[data-value~="beta"]', ["one"]),
        ('[lang|="en"]', ["one", "two"]),
        ('[data-value^="al" i]', ["one", "two"]),
        ('[DATA-VALUE="ALPHA BETA" I]', ["one"]),
        ('[data-value="ALPHA BETA" s]', []),
        ('[data-unicode="ä" i]', []),
        ('[data-url="https://a,b/x?q=1+2"]', ["one"]),
        ('[data-bracket="a]b"]', ["one"]),
        ('[data-value=""]', ["empty"]),
        ('[data-value~="Alpha beta"]', []),
        ('[data-value^=""]', []),
        ('[data-value$=""]', []),
        ('[data-value*=""]', []),
        ('[data-value~=""]', []),
    ],
)
def test_attribute_operator_and_case_semantics(markup, selector, expected):
    assert [n["attributes"]["id"] for n in markup.query(selector)] == expected


def test_attribute_operator_cascade_and_quoted_specificity(tmp_path):
    (tmp_path / "page.html").write_text(
        '<style>p {color:black} [data-url^="https:"] {color:red}</style>'
        '<p data-url="https://example.test"></p>'
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.styles(index.query("p")[0]["id"])["computed"]["color"]["value"] == "red"
    assert index.specificity('[data-value="[.#]"]') == (0, 1, 0)


@pytest.mark.parametrize(
    "selector",
    [
        '[data-value="x" q]',
        '[data-value!="x"]',
        "[data-value i]",
        "[data-value=]",
        '[data-value="x" i s]',
    ],
)
def test_invalid_attribute_operator_or_flag_is_rejected(markup, selector):
    with pytest.raises(ValueError):
        markup.query(selector)


def test_word_matching_uses_css_whitespace_and_presence_keeps_empty_values(tmp_path):
    (tmp_path / "page.html").write_text(
        '<p data-value="alpha\u00a0beta"></p><input disabled>', encoding="utf-8"
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.query('[data-value~="beta"]') == []
    assert len(index.query("[disabled]")) == 1
    assert len(index.query('[disabled=""]')) == 1
