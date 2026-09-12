import pytest

from banger.index import CodeIndex

CASES = [
    (
        {
            "lib.ts": "export const leaf = (x: number) => x + 1;",
            "main.ts": "import { leaf } from './lib'; const root = () => leaf(2);",
        },
        "root",
        "leaf",
    ),
    (
        {
            "lib.ts": "export function leaf() { return 1; }",
            "main.ts": "import { leaf as chosen } from './lib'; function root() { return chosen(); }",
        },
        "root",
        "leaf",
    ),
    (
        {
            "lib.js": "export function leaf() { return 1; }",
            "main.js": "import * as utils from './lib'; function root() { return utils.leaf(); }",
        },
        "root",
        "leaf",
    ),
    (
        {
            "go.mod": "module example/app\n",
            "lib/lib.go": "package lib\nfunc Leaf() int { return 1 }",
            "main.go": 'package main\nimport alias "example/app/lib"\nfunc root() int { return alias.Leaf() }',
        },
        "root",
        "Leaf",
    ),
    (
        {
            "lib.rs": "pub fn leaf() -> i32 { 1 }",
            "main.rs": "mod lib; use crate::lib::leaf as chosen; fn root() -> i32 { chosen() }",
        },
        "root",
        "leaf",
    ),
    (
        {
            "app/lib/Tools.java": "package app.lib; public class Tools { public static int leaf() { return 1; } }",
            "app/Main.java": "package app; import app.lib.Tools; class Main { int root() { return Tools.leaf(); } }",
        },
        "root",
        "leaf",
    ),
    (
        {
            "Tools.cs": "namespace Lib { public class Tools { public static int Leaf() { return 1; } } }",
            "Main.cs": "using Lib; namespace App { class Main { int root() { return Tools.Leaf(); } } }",
        },
        "root",
        "Leaf",
    ),
]


@pytest.mark.parametrize("files,caller,target", CASES)
def test_imported_calls_resolve_to_the_correct_file(tmp_path, files, caller, target):
    for path, source in files.items():
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source)
    index = CodeIndex(tmp_path)
    index.refresh()
    calls = index.profile(caller)["calls"]
    definition = index.get_definition(target)
    assert calls[0]["targets"] == [definition["id"]]
    assert calls[0]["resolution"] == "resolved"


def test_javascript_bare_import_is_not_proven_external(tmp_path):
    (tmp_path / "main.ts").write_text(
        "import { leaf } from '@app/lib'; function root() { return leaf(); }"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    call = index.profile("root")["calls"][0]
    assert call["resolution"] == "unknown"
    assert "alias" in call["evidence"]
