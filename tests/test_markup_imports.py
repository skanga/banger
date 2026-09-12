import pytest

from banger.markup import MarkupIndex


@pytest.mark.parametrize(
    "url",
    [
        '"base.css"',
        "'base.css'",
        "url(base.css)",
        'url("base.css")',
        'url("base%2Ecss?v=1#part")',
        '"base.css" all',
    ],
)
def test_local_css_imports_preserve_order_provenance_and_refresh(tmp_path, url):
    (tmp_path / "css").mkdir()
    (tmp_path / "page.html").write_text('<link rel="stylesheet" href="css/site.css"><p></p>')
    (tmp_path / "css/site.css").write_text(f"@import {url};\np {{color:blue}}\n")
    (tmp_path / "css/base.css").write_text('@import "../tokens.css";\np {color:red; padding:2px}\n')
    (tmp_path / "tokens.css").write_text("p {margin:3px}\n")
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["computed"]["color"]["value"] == "blue"
    assert styles["computed"]["padding"]["value"] == "2px"
    assert styles["computed"]["padding"]["path"] == "css/base.css"
    assert styles["computed"]["padding"]["line"] == 2
    assert styles["computed"]["margin"]["path"] == "tokens.css"
    assert not styles["unresolved"]
    (tmp_path / "tokens.css").write_text("p {margin:4px}\n")
    index.refresh()
    assert index.styles(index.query("p")[0]["id"])["computed"]["margin"]["value"] == "4px"


def test_repeated_imports_keep_cascade_order_and_cycles_terminate(tmp_path):
    (tmp_path / "page.html").write_text('<link rel="stylesheet" href="site.css"><p></p>')
    (tmp_path / "site.css").write_text(
        '@import "base.css"; @import "other.css"; @import "base.css";'
    )
    (tmp_path / "base.css").write_text('@import "site.css"; p {color:red}')
    (tmp_path / "other.css").write_text("p {color:blue}")
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["computed"]["color"]["value"] == "red"
    assert any("cycle" in str(r).lower() for r in styles["unresolved"])


@pytest.mark.parametrize(
    "rule",
    [
        '@import "base.css" screen;',
        '@import "base.css" layer(theme);',
        'p {margin:0} @import "base.css";',
        '@import "https://example.test/base.css";',
        '@import ".banger/base.css";',
        '@import "missing.css";',
    ],
)
def test_unsupported_or_unavailable_import_is_not_applied(tmp_path, rule):
    (tmp_path / "page.html").write_text(f"<style>{rule}</style><p></p>")
    (tmp_path / "base.css").write_text("p {color:red}")
    (tmp_path / ".banger").mkdir()
    (tmp_path / ".banger/base.css").write_text("p {color:red}")
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert "color" not in styles["computed"]
    assert styles["unresolved"]


def test_python_embedded_import_preserves_imported_and_unresolved_locations(tmp_path):
    (tmp_path / "web.py").write_text(
        'PAGE = """\n<style>\n@import "base.css";\n@import "missing.css";\n</style><p></p>"""\n'
    )
    (tmp_path / "base.css").write_text("/* base */\np {padding:2px}\n")
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["computed"]["padding"]["path"] == "base.css"
    assert styles["computed"]["padding"]["line"] == 2
    missing = next(r for r in styles["unresolved"] if "missing.css" in r.get("unresolved", ""))
    assert missing["path"] == "web.py" and missing["line"] == 4


def test_deep_import_chain_reports_limit_and_keeps_loaded_styles(tmp_path):
    (tmp_path / "page.html").write_text('<link rel="stylesheet" href="0.css"><p></p>')
    for level in range(35):
        style = "p {padding:2px}" if level == 10 else ""
        (tmp_path / f"{level}.css").write_text(f'@import "{level + 1}.css";\n' + style)
    index = MarkupIndex(tmp_path)
    index.refresh()
    styles = index.styles(index.query("p")[0]["id"])
    assert styles["computed"]["padding"]["path"] == "10.css"
    assert any("limit" in r.get("reason", "") for r in styles["unresolved"])
