"""Atomic edits and persistent undo; invoked after tool authorization."""

import os
import tempfile
from pathlib import Path

from banger.analysis import FlowAnalysis
from banger.batches import BatchEdits
from banger.diffs import file_diff


class Editor:
    def __init__(self, root, state, index):
        self.root, self.state, self.index = Path(root).resolve(), state, index
        BatchEdits(self).recover()
        for snapshot in state.pending_snapshots():
            if snapshot.get("batch"):
                continue
            if snapshot["status"] == "pending-rollback":
                self._recover_rollback(snapshot)
                continue
            path = Path(snapshot["path"])
            current = path.read_bytes() if path.exists() else None
            status = (
                "applied"
                if current == snapshot["after"]
                else "abandoned"
                if current == snapshot["before"]
                else "conflict"
            )
            state.finish_snapshot(snapshot["id"], status)

    def _recover_rollback(self, snapshot):
        path = Path(snapshot["path"])
        current = path.read_bytes() if path.exists() else None
        status = (
            "rolled-back"
            if current == snapshot["before"]
            else "applied"
            if current == snapshot["after"]
            else "conflict"
        )
        self.state.finish_snapshot(snapshot["id"], status)

    def _path(self, path: str) -> Path:
        return (self.root / path).resolve()

    def _atomic(self, path: Path, content: bytes | None):
        if content is None:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = path.stat().st_mode if path.exists() else None
        fd, name = tempfile.mkstemp(prefix=".banger-edit-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if mode is not None:
                os.chmod(name, mode)
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)

    def write(self, path: str, content: str) -> dict:
        return self._apply(path, content.encode("utf-8"))

    def replace(self, path: str, old: str, new: str) -> dict:
        content = self._path(path).read_bytes().decode("utf-8")
        if not old or content.count(old) != 1:
            raise ValueError("The old text must occur exactly once")
        return self.write(path, content.replace(old, new, 1))

    def delete(self, path: str) -> dict:
        return self._apply(path, None)

    def apply_changes(self, changes):
        return BatchEdits(self).apply(changes)

    def _impact(self, target):
        flow = FlowAnalysis(self.index)
        return [
            {
                "definition": symbol,
                "callers": self.index.get_callers(symbol["id"]),
                "value_consumers": flow.return_uses(symbol["id"])["uses"],
                "relevant_tests": flow.relevant_tests(symbol["id"]),
                "scope": "Indexed callers and direct return holders; tests selected from resolved call paths",
            }
            for symbol in self.index.symbols.values()
            if self._path(symbol["path"]) == target
        ]

    def _check_syntax(self, path, after):
        if after is not None:
            errors = self.index.syntax_errors(path, after)
            if Path(path).suffix == ".py":
                try:
                    compile(after, path, "exec")
                except (SyntaxError, ValueError) as exc:
                    errors.append({"detail": str(exc)})
            if errors:
                raise ValueError(f"Edit rejected by syntax gate: {errors}")

    def _apply(self, path: str, after: bytes | None) -> dict:
        target = self._path(path)
        before = target.read_bytes() if target.exists() else None
        self._check_syntax(path, after)
        self.index.refresh()
        impact_before = self._impact(target)
        semantic = self.index.preview_change(target, after)
        if semantic["regressions"]:
            raise ValueError(f"Edit rejected by semantic gate: {semantic['regressions']}")
        snapshot = self.state.snapshot(str(target), before, after, status="pending")
        try:
            # Refuse a change made since the snapshot was captured.
            if (target.read_bytes() if target.exists() else None) != before:
                raise ValueError("File changed while preparing the edit")
            self._atomic(target, after)
            self.state.finish_snapshot(snapshot, "applied")
        except Exception:
            self.state.finish_snapshot(snapshot, "failed")
            raise
        self.index.refresh()
        impact_after = self._impact(target)
        self.state.put_artifact(
            "edit-impact", str(snapshot), {"before": impact_before, "after": impact_after}
        )
        diff = file_diff(path, before, after)
        return {
            "snapshot": snapshot,
            "diff": diff,
            "callers_before": {item["definition"]["id"]: item["callers"] for item in impact_before},
            "symbols_after": [item["definition"] for item in impact_after],
            "impact_before": impact_before,
            "impact_after": impact_after,
            "semantic_gate": semantic,
            "verification": "Syntax and known call-binding regressions checked; tests not yet executed",
        }

    def rollback(self) -> dict:
        snapshot = self.state.latest_snapshot()
        if not snapshot:
            raise ValueError("No edit to roll back")
        if snapshot.get("batch"):
            return BatchEdits(self).rollback(snapshot)
        path = Path(snapshot["path"])
        if (path.read_bytes() if path.exists() else None) != snapshot["after"]:
            raise ValueError("File changed after the edit; rollback would overwrite newer work")
        self.state.finish_snapshot(snapshot["id"], "pending-rollback")
        try:
            self._atomic(path, snapshot["before"])
        except Exception:
            self._recover_rollback(snapshot)
            raise
        self.state.finish_snapshot(snapshot["id"], "rolled-back")
        self.index.refresh()
        return {"restored": str(path), "snapshot": snapshot["id"]}
