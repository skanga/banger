import pytest

from banger.markup import MarkupIndex


@pytest.mark.parametrize(
    "source,line",
    [
        ("<style>\np {color:red}\n\n</style><p></p>", 2),
        ('<style\n type="text/css">\np {color:red}\n</style><p></p>', 3),
        ("<style>p {color:red}</style><p></p>", 1),
    ],
)
def test_inline_stylesheet_rule_location_uses_content_start(tmp_path, source, line):
    (tmp_path / "page.html").write_text(source)
    index = MarkupIndex(tmp_path)
    index.refresh()
    rule = index.rules["page.html"][0]
    assert rule["line"] == line
    winner = index.styles(index.query("p")[0]["id"])["computed"]["color"]
    assert winner["path"] == "page.html"
    assert winner["line"] == line


def test_linked_stylesheet_line_is_relative_to_css_file(tmp_path):
    (tmp_path / "page.html").write_text('\n\n\n<link rel="stylesheet" href="site.css"><p></p>')
    (tmp_path / "site.css").write_text("/* comment */\np {color:red}\n")
    index = MarkupIndex(tmp_path)
    index.refresh()
    rule = index.rules["page.html"][0]
    assert rule["path"] == "site.css" and rule["line"] == 2
    winner = index.styles(index.query("p")[0]["id"])["computed"]["color"]
    assert winner["path"] == "site.css" and winner["line"] == 2


def test_style_provenance_survives_inheritance_and_reports_unsupported_selector(tmp_path):
    (tmp_path / "page.html").write_text(
        "<style>\nmain {color:red}\np:hover {color:blue}\n</style>\n"
        '<main><p style="padding:2px"></p></main>'
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["computed"]["color"]["line"] == 2
    assert styles["computed"]["padding"]["line"] == 5
    unsupported = next(r for r in styles["unresolved"] if r.get("selector") == "p:hover")
    assert unsupported["path"] == "page.html" and unsupported["line"] == 3


def test_literal_multiline_python_markup_keeps_file_offset(tmp_path):
    (tmp_path / "web.py").write_text(
        '# page\nPAGE = """\n<style>\np {color:red}\n</style><p></p>\n"""\n'
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    winner = index.styles(index.query("p")[0]["id"])["computed"]["color"]
    assert winner["path"] == "web.py" and winner["line"] == 4


def test_element_lines_do_not_include_html_column_offsets(tmp_path):
    (tmp_path / "page.html").write_text('<main><p id="first"></p>\n <p id="second"></p></main>')
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.query("#first")[0]["line"] == 1
    assert index.query("#second")[0]["line"] == 2
