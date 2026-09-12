"""Workspace file discovery using Git's ignore rules when a repository is present."""

import os
import subprocess
from pathlib import Path

EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".banger",
    "target",
    "dist",
    "build",
    ".pytest_cache",
    ".ruff_cache",
}


def _safe_path(root, name):
    relative = Path(name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or any(p in EXCLUDED for p in relative.parts)
    ):
        return None
    path = root / relative
    try:
        # Also excludes directory symlinks and Windows junctions in ancestors.
        if path.resolve() != path:
            return None
    except (OSError, RuntimeError):
        return None
    return path


def discover_files(root):
    root = Path(root).resolve()
    repository = any((parent / ".git").exists() for parent in (root, *root.parents))
    if repository:
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env["GIT_OPTIONAL_LOCKS"] = "0"
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    "core.untrackedCache=false",
                    "ls-files",
                    "-z",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "--",
                    ".",
                ],
                capture_output=True,
                check=False,
                timeout=10,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Git file discovery failed: {exc}") from exc
        if result.returncode:
            raise RuntimeError(
                "Git file discovery failed: "
                + result.stderr.decode("utf-8", errors="replace")[:1000]
            )
        names = [os.fsdecode(name) for name in result.stdout.split(b"\0") if name]
    else:
        names = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if _safe_path(root, (Path(directory) / d).relative_to(root))]
            names.extend((Path(directory) / name).relative_to(root) for name in files)
    paths = {_safe_path(root, name) for name in names}
    return sorted(path for path in paths if path is not None and path.is_file())
