import pytest

from banger.markup import MarkupIndex


@pytest.mark.parametrize("tag", ["style", "link"])
@pytest.mark.parametrize("media", ["print", "screen", "(min-width: 900px)"])
def test_conditional_stylesheet_is_not_an_unconditional_winner(tmp_path, tag, media):
    resource = (
        f'<style media="{media}">p {{color:red}}</style>'
        if tag == "style"
        else f'<link rel="stylesheet" href="sheet.css" media="{media}">'
    )
    (tmp_path / "page.html").write_text("<style>p {color:green}</style>\n" + resource + "<p></p>")
    (tmp_path / "sheet.css").write_text("p {color:red}")
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["computed"]["color"]["value"] == "green"
    warning = next(r for r in styles["unresolved"] if "media" in r.get("unresolved", ""))
    assert media in warning["unresolved"]
    assert warning["path"] == "page.html" and warning["line"] == 2


@pytest.mark.parametrize(
    "attributes",
    [
        'rel="stylesheet" disabled',
        'rel="stylesheet" disabled="false"',
        'rel="alternate stylesheet" title="Alternative"',
    ],
)
def test_disabled_or_alternate_link_is_not_applied(tmp_path, attributes):
    (tmp_path / "page.html").write_text(f'<link {attributes} href="sheet.css"><p></p>')
    (tmp_path / "sheet.css").write_text("p {color:red}")
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert "color" not in styles["computed"]
    assert styles["unresolved"]


@pytest.mark.parametrize(
    "attributes",
    [
        'rel="STYLESHEET"',
        'rel="preload stylesheet"',
        'rel="stylesheet stylesheet" media=" ALL "',
    ],
)
def test_stylesheet_rel_tokens_and_all_media_are_recognized(tmp_path, attributes):
    (tmp_path / "page.html").write_text(f'<link {attributes} href="sheet.css"><p></p>')
    (tmp_path / "sheet.css").write_text("p {color:red}")
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["computed"]["color"]["value"] == "red"
    assert not styles["unresolved"]


def test_embedded_media_restriction_location_and_refresh(tmp_path):
    path = tmp_path / "web.py"
    source = 'PAGE = """\n<style media="print">p {color:red}</style><p></p>"""\n'
    path.write_text(source)
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert "color" not in styles["computed"]
    warning = next(r for r in styles["unresolved"] if "media" in r.get("unresolved", ""))
    assert warning["path"] == "web.py" and warning["line"] == 2
    path.write_text(source.replace('media="print"', 'media="all"'))
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["computed"]["color"]["value"] == "red"
    assert not styles["unresolved"]
