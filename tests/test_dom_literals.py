import pytest

from banger.markup import MarkupIndex


@pytest.mark.parametrize(
    ("literal", "selector"),
    [
        (r'"\x23save"', "#save"),
        (r'"\u0023save"', "#save"),
        (r'"\u{23}save"', "#save"),
        (r'"#caf\u00e9"', "#café"),
        (r'"#\uD83D\uDE80"', "#🚀"),
        (r'"#\u{1f680}"', "#🚀"),
        (r'"[data-name=\"save\"]"', '[data-name="save"]'),
        (r'"#some\\:id"', r"#some\:id"),
        (r'"#\save"', "#save"),
        ('"#sa\\\nve"', "#save"),
        ('"#sa\\\r\nve"', "#save"),
        (r"`#save`", "#save"),
        (r"`#\u{23}save`", "##save"),
        (r'"div\t>\nspan"', "div\t>\nspan"),
        (r'"\0name"', "\0name"),
        (r'"\b\f\r\v"', "\b\f\r\v"),
        (r'`[data-name="\`save\`"]`', '[data-name="`save`"]'),
        (r"`#\${name}`", "#${name}"),
        ('"#sa\\\u2028ve"', "#save"),
        ('"#sa\\\u2029ve"', "#save"),
        ("`div\r\nspan`", "div\nspan"),
    ],
)
def test_dom_literal_values_are_decoded_without_execution(tmp_path, literal, selector):
    (tmp_path / "app.js").write_text(
        f"document.querySelector({literal});", encoding="utf-8", newline=""
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.dom_references(selector) == [
        {"selector": selector, "path": "app.js", "line": 1, "resolution": "syntactic candidate"}
    ]


@pytest.mark.parametrize("extension", ["js", "jsx", "ts", "tsx"])
def test_literal_bracket_methods_and_optional_calls(tmp_path, extension):
    (tmp_path / f"app.{extension}").write_text(
        'document["querySelector"]("#save");\n'
        'root?.["querySelectorAll"]?.("#save");\n'
        r'document["getElementBy\u0049d"]("save");'
        "\n"
        'root[`querySelector`]("#save");\n'
        'root[method]("#save");\n'
        'root["query" + "Selector"]("#save");\n',
        encoding="utf-8",
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert [r["line"] for r in index.dom_references("#save")] == [1, 2, 3, 4]


def test_invalid_and_dynamic_literals_remain_unresolved(tmp_path):
    (tmp_path / "app.js").write_text(
        "document.querySelector(`#${name}`);\n"
        "document.querySelector(String.raw`#save`);\n"
        r'document.querySelector("\u{110000}");'
        "\n"
        r'document.querySelector("\xZZ");'
        "\n"
        r'document.querySelector("\043save");'
        "\n",
        encoding="utf-8",
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.references == []
