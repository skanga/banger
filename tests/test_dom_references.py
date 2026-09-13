import pytest

from banger.markup import MarkupIndex


@pytest.mark.parametrize("extension", ["js", "jsx", "ts", "tsx"])
def test_dom_calls_exclude_comments_strings_and_other_method_names(tmp_path, extension):
    path = tmp_path / f"app.{extension}"
    path.write_text(
        '// document.querySelector("#save")\n'
        'const example = `document.querySelector("#save")`;\n'
        '/* document.getElementById("save") */\n'
        'other.notquerySelector("#save");\n'
        'document.querySelector(/* selector */ "#save");\n'
        'root.querySelectorAll("#save");\n'
        'document.getElementById("save");\n',
        encoding="utf-8",
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert [r["line"] for r in index.dom_references("#save")] == [5, 6, 7]
    path.write_text('// document.querySelector("#save")', encoding="utf-8")
    index.refresh()
    assert index.dom_references("#save") == []


@pytest.mark.parametrize("python", [False, True])
def test_only_inline_javascript_is_scanned_in_markup(tmp_path, python):
    markup = (
        '<p>document.querySelector("#save")</p>\n'
        '<!-- document.querySelector("#save") -->\n'
        '<script type="application/json">"document.querySelector(\'#save\')"</script>\n'
        "<script>\n"
        '// document.querySelector("#save")\n'
        'document.querySelector("#save");\n'
        "</script>"
    )
    source = 'PAGE = """' + markup + '"""' if python else markup
    (tmp_path / ("page.py" if python else "page.html")).write_text(source, encoding="utf-8")
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert [r["line"] for r in index.dom_references("#save")] == [6]


def test_python_script_lines_follow_literal_source_mapping(tmp_path):
    (tmp_path / "page.py").write_text(
        "PAGE = (\n"
        "    '<script>const title = \"café\";\\n'\n"
        "    'document.querySelector(\"#save\");</script>'\n"
        ")\n",
        encoding="utf-8",
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.dom_references("#save") == [
        {"selector": "#save", "path": "page.py", "line": 3, "resolution": "syntactic candidate"}
    ]


def test_template_expression_calls_and_dynamic_selectors(tmp_path):
    (tmp_path / "app.tsx").write_text(
        'const view = <div>{`result: ${document.querySelector("#save")}`}</div>;\n'
        "document.querySelector(selector);\n"
        'document.querySelector("#" + name);\n'
        'document.querySelector("#save", extra);\n'
        'document?.querySelector("#save");\n',
        encoding="utf-8",
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert [r["line"] for r in index.dom_references("#save")] == [1, 5]


def test_external_script_body_is_ignored_and_module_script_is_scanned(tmp_path):
    (tmp_path / "page.html").write_text(
        '<script src="app.js">document.querySelector("#save")</script>\n'
        '<script type="module">document.querySelector("#save")</script>',
        encoding="utf-8",
    )
    (tmp_path / "app.js").write_text('document.querySelector("#save")', encoding="utf-8")
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert [(r["path"], r["line"]) for r in index.dom_references("#save")] == [
        ("app.js", 1),
        ("page.html", 2),
    ]
