import pytest

from banger.markup import MarkupIndex


@pytest.mark.parametrize(
    "source,rule_line,element_line",
    [
        ('PAGE = "<style>\\np {color:red}</style>\\n<p id=target></p>"\n', 1, 1),
        ('PAGE = (\n "<style>"\n "p {color:red}"\n "</style><p id=target></p>"\n)\n', 3, 4),
        ('PAGE = "\\x3cstyle>p {color:red}</style>\\u003cp id=target></p>"\n', 1, 1),
        ('PAGE = """<style>\\\np {color:red}</style>\\\n<p id=target></p>"""\n', 2, 3),
        ('PAGE = ("<style>/*é*/"\n "p {color:red}</style><p id=target></p>")\n', 2, 2),
        ('PAGE = r"""<style>\np {color:red}</style>\n<p id=target></p>"""\n', 2, 3),
        ('PAGE = ("<style>"\n    "p {color:red}" # note\n  "</style><p id=target></p>")\n', 2, 3),
        ('PAGE = "<style>p {color:red}</style>\\074p id=target></p>"\n', 1, 1),
        ('PAGE = "<style>p {color:red}</style>\\N{LESS-THAN SIGN}p id=target></p>"\n', 1, 1),
    ],
)
def test_decoded_markup_maps_to_literal_source_lines(tmp_path, source, rule_line, element_line):
    (tmp_path / "web.py").write_text(source, encoding="utf-8")
    index = MarkupIndex(tmp_path)
    index.refresh()
    node = index.query("#target")[0]
    assert node["line"] == element_line
    assert node["source_mapping"] == "exact literal"
    color = index.styles(node["id"])["computed"]["color"]
    assert color["path"] == "web.py"
    assert color["line"] == rule_line


def test_two_markup_literals_on_one_line_remain_distinct_documents(tmp_path):
    (tmp_path / "web.py").write_text('FIRST = "<p id=first></p>"; SECOND = "<p id=second></p>"\n')
    index = MarkupIndex(tmp_path)
    assert index.refresh()["documents"] == 2
    first, second = index.query("p")
    assert {first["attributes"]["id"], second["attributes"]["id"]} == {"first", "second"}
    assert first["document"] != second["document"]
    assert first["line"] == second["line"] == 1
