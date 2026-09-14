import asyncio
from unittest.mock import Mock

import pytest
from textual.app import App

from banger.app import ProjectTree


class TreeApp(App):
    def __init__(self, path):
        super().__init__()
        self.path = path

    def compose(self):
        yield ProjectTree(self.path)


async def wait_for(pilot, condition):
    async with asyncio.timeout(4):
        while not condition():
            await pilot.pause(0.05)


def child(node, name):
    if node is None:
        return None
    return next((item for item in node.children if item.data.path.name == name), None)


async def test_external_file_and_folder_changes_refresh_tree(tmp_path):
    app = TreeApp(tmp_path)
    async with app.run_test() as pilot:
        tree = app.query_one(ProjectTree)
        await wait_for(pilot, lambda: tree.root.data.loaded)
        (tmp_path / "new.py").write_text("pass")
        (tmp_path / "folder").mkdir()
        await wait_for(pilot, lambda: child(tree.root, "new.py") and child(tree.root, "folder"))
        (tmp_path / "new.py").rename(tmp_path / "renamed.py")
        (tmp_path / "folder").rmdir()
        await wait_for(
            pilot,
            lambda: (
                child(tree.root, "renamed.py")
                and not child(tree.root, "new.py")
                and not child(tree.root, "folder")
            ),
        )


async def test_nested_changes_preserve_expansion_and_selection(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "keep.py").touch()
    app = TreeApp(tmp_path)
    async with app.run_test() as pilot:
        tree = app.query_one(ProjectTree)
        await wait_for(pilot, lambda: child(tree.root, "folder"))
        node = child(tree.root, "folder")
        node.expand()
        await wait_for(pilot, lambda: child(node, "keep.py"))
        tree.move_cursor(child(node, "keep.py"))
        (folder / "added.py").touch()
        await wait_for(pilot, lambda: child(child(tree.root, "folder"), "added.py"))
        assert child(tree.root, "folder").is_expanded
        assert tree.cursor_node.data.path == folder / "keep.py"


async def test_content_edits_and_excluded_directories_do_not_reload(tmp_path):
    source = tmp_path / "keep.py"
    source.touch()
    app = TreeApp(tmp_path)
    async with app.run_test() as pilot:
        tree = app.query_one(ProjectTree)
        await wait_for(pilot, lambda: child(tree.root, "keep.py"))
        tree.reload = Mock(wraps=tree.reload)
        source.write_text("changed content")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "hidden.js").touch()
        await pilot.pause(1.3)
        tree.reload.assert_not_called()
        assert not child(tree.root, "node_modules")


async def test_previously_loaded_collapsed_folder_updates_and_watcher_stops(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "old.py").touch()
    app = TreeApp(tmp_path)
    async with app.run_test() as pilot:
        tree = app.query_one(ProjectTree)
        await wait_for(pilot, lambda: child(tree.root, "folder"))
        node = child(tree.root, "folder")
        node.expand()
        await wait_for(pilot, lambda: child(node, "old.py"))
        node.collapse()
        (folder / "old.py").rename(folder / "new.py")
        await pilot.pause(1.3)
        node = child(tree.root, "folder")
        assert not node.is_expanded
        node.expand()
        await wait_for(pilot, lambda: child(node, "new.py") and not child(node, "old.py"))
        watcher = next(worker for worker in tree.workers if worker.group == "directory-changes")
    assert watcher.is_cancelled


@pytest.mark.parametrize("error", [PermissionError, FileNotFoundError])
def test_directory_scan_tolerates_filesystem_errors(tmp_path, monkeypatch, error):
    monkeypatch.setattr("banger.app.os.scandir", Mock(side_effect=error))
    changed = ProjectTree._directories_changed([(tmp_path, set())])
    assert changed is (error is FileNotFoundError)
