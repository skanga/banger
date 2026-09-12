import subprocess

import pytest

from banger.discovery import discover_files
from banger.index import CodeIndex
from banger.markup import MarkupIndex
from banger.state import StateStore


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_git_discovery_honors_nested_ignores_and_retains_tracked_files(tmp_path):
    git(tmp_path, "init")
    write(tmp_path, ".gitignore", "vendor/\ngenerated.py\n")
    write(tmp_path, "vendor/ignored.py", "def ignored(): pass\n")
    write(tmp_path, "generated.py", "def tracked(): pass\n")
    git(tmp_path, "add", "-f", "generated.py")
    write(tmp_path, "src/.gitignore", "*.py\n!keep.py\n")
    write(tmp_path, "src/drop.py", "def drop(): pass\n")
    write(tmp_path, "src/keep.py", "def keep(): pass\n")
    write(tmp_path, "new space café.py", "def fresh(): pass\n")
    index = CodeIndex(tmp_path)
    index.refresh()
    assert set(index.files) == {"generated.py", "src/keep.py", "new space café.py"}


def test_git_ignore_changes_invalidate_cached_files_and_notice_new_sources(tmp_path):
    git(tmp_path, "init")
    write(tmp_path, "old.py", "def old(): pass\n")
    with StateStore(tmp_path / ".banger/state.db") as state:
        index = CodeIndex(tmp_path, state)
        index.refresh()
        assert "old.py" in index.files
        write(tmp_path, ".gitignore", "old.py\n")
        write(tmp_path, "new.py", "def fresh(): pass\n")
        index.refresh()
        assert set(index.files) == {"new.py"}
        restored = CodeIndex(tmp_path, state)
        restored.refresh()
        assert set(restored.files) == {"new.py"}


def test_subdirectory_workspace_uses_ancestor_git_rules_without_sibling_files(tmp_path):
    git(tmp_path, "init")
    write(tmp_path, ".gitignore", "src/hidden.py\n")
    write(tmp_path, "sibling.py", "def sibling(): pass\n")
    write(tmp_path, "src/hidden.py", "def hidden(): pass\n")
    write(tmp_path, "src/main.py", "def main(): pass\n")
    index = CodeIndex(tmp_path / "src")
    index.refresh()
    assert set(index.files) == {"main.py"}


def test_markup_ignores_documents_scripts_and_stylesheets(tmp_path):
    git(tmp_path, "init")
    write(tmp_path, ".gitignore", "private/\n")
    write(tmp_path, "private/secret.html", '<div id="hidden"></div>')
    write(tmp_path, "private/secret.js", 'document.querySelector("#shown")')
    write(tmp_path, "private/theme.css", "div { color: red; }")
    write(
        tmp_path,
        "index.html",
        '<link rel="stylesheet" href="private/theme.css"><div id="shown"></div>',
    )
    index = MarkupIndex(tmp_path)
    index.refresh()
    assert index.query("#hidden") == []
    assert index.dom_references("#shown") == []
    assert any("unresolved" in rule for rule in index.rules["index.html"])
    assert not any(
        "color" in str(rule.get("declarations", {})) for rule in index.rules["index.html"]
    )


def test_git_failure_does_not_silently_scan_ignored_sources(tmp_path, monkeypatch):
    git(tmp_path, "init")
    write(tmp_path, "secret.py", "def secret(): pass\n")

    def unavailable(*args, **kwargs):
        raise FileNotFoundError("Git is unavailable")

    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(RuntimeError, match="Git.*discovery"):
        CodeIndex(tmp_path).refresh()


def test_plain_directory_discovery_works_without_git(tmp_path, monkeypatch):
    write(tmp_path, "main.py", "def main(): pass\n")
    write(tmp_path, ".venv/hidden.py", "def hidden(): pass\n")

    def unexpected(*args, **kwargs):
        pytest.fail("A plain directory should not invoke Git")

    monkeypatch.setattr(subprocess, "run", unexpected)
    index = CodeIndex(tmp_path)
    index.refresh()
    assert set(index.files) == {"main.py"}


def test_git_discovery_uses_selected_workspace_despite_inherited_git_environment(
    tmp_path, monkeypatch
):
    git(tmp_path, "init")
    write(tmp_path, "main.py", "def main(): pass\n")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "wrong.git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "wrong-tree"))
    assert discover_files(tmp_path) == [tmp_path / "main.py"]


def test_git_discovery_disables_hooks_and_rejects_escaping_paths(tmp_path, monkeypatch):
    git(tmp_path, "init")
    write(tmp_path, "main.py", "def main(): pass\n")
    write(tmp_path, ".banger/hidden.py", "def hidden(): pass\n")

    def listing(argv, **kwargs):
        assert "core.fsmonitor=false" in argv
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        assert kwargs.get("shell", False) is False
        assert kwargs["timeout"] == 10
        return subprocess.CompletedProcess(
            argv, 0, b"main.py\0../outside.py\0.banger/hidden.py\0", b""
        )

    monkeypatch.setattr(subprocess, "run", listing)
    assert discover_files(tmp_path) == [tmp_path / "main.py"]


def test_git_ownership_rejection_is_reported_without_a_trust_override(tmp_path, monkeypatch):
    git(tmp_path, "init")

    def rejected(argv, **kwargs):
        assert not any("safe.directory" in arg for arg in argv)
        return subprocess.CompletedProcess(argv, 128, b"", b"fatal: dubious ownership")

    monkeypatch.setattr(subprocess, "run", rejected)
    with pytest.raises(RuntimeError, match="dubious ownership"):
        discover_files(tmp_path)
