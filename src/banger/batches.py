"""Coordinated gated edits with grouped snapshots and compensating recovery."""

from pathlib import Path

from banger.diffs import file_diff


class BatchEdits:
    def __init__(self, editor):
        self.editor = editor
        self.state = editor.state

    @staticmethod
    def read(path):
        return path.read_bytes() if path.exists() else None

    def recover(self):
        groups = {s["batch"] for s in self.state.pending_snapshots() if s.get("batch")}
        for group in groups:
            snapshots = self.state.snapshot_group(group)
            current = [self.read(Path(s["path"])) for s in snapshots]
            if all(value == s["after"] for value, s in zip(current, snapshots)):
                status = "applied"
            elif all(value == s["before"] for value, s in zip(current, snapshots)):
                status = (
                    "rolled-back" if snapshots[0]["status"] == "pending-rollback" else "abandoned"
                )
            elif all(value in (s["before"], s["after"]) for value, s in zip(current, snapshots)):
                status = "incomplete"
            else:
                status = "conflict"
            self.state.finish_group(group, status)

    def _commit(self, snapshots, expected, column, success, failure):
        group = snapshots[0]["batch"]
        desired = {Path(s["path"]): s[column] for s in snapshots}
        try:
            for path, content in desired.items():
                if self.read(path) != expected[path]:
                    raise ValueError("File changed while preparing grouped edit: " + str(path))
                if content != expected[path]:
                    self.editor._atomic(path, content)
            self.state.finish_group(group, success)
        except Exception:
            # Restore only bytes still owned by this operation. A crash leaves
            # pending snapshots for classification at the next startup.
            if any(self.read(p) not in (expected[p], desired[p]) for p in desired):
                self.state.finish_group(group, "conflict")
                raise
            try:
                for path in reversed(desired):
                    if self.read(path) != expected[path]:
                        self.editor._atomic(path, expected[path])
                self.state.finish_group(group, failure)
            except Exception as restore_error:
                self.state.finish_group(group, "incomplete")
                raise RuntimeError(
                    "Grouped edit restoration failed; inspect snapshots before retrying"
                ) from restore_error
            raise

    def apply(self, changes):
        if not isinstance(changes, dict) or not changes or len(changes) > 100:
            raise ValueError("Provide from 1 to 100 file edits")
        proposed, labels = {}, {}
        for path, content in changes.items():
            if (
                not isinstance(path, str)
                or not path.strip()
                or not (content is None or isinstance(content, str))
            ):
                raise ValueError("Edits must map file paths to UTF-8 strings or null for deletion")
            target = self.editor._path(path)
            if target in proposed:
                raise ValueError("Duplicate resolved edit path: " + path)
            after = content.encode("utf-8") if content is not None else None
            self.editor._check_syntax(path, after)
            proposed[target], labels[target] = after, path
        before = {p: self.read(p) for p in proposed}
        self.editor.index.refresh()
        impacts = {p: self.editor._impact(p) for p in proposed}
        semantic = self.editor.index.preview_changes(proposed)
        if semantic["regressions"]:
            raise ValueError(f"Edit rejected by semantic gate: {semantic['regressions']}")
        snapshots = self.state.snapshot_many(
            [(str(p), before[p], after) for p, after in proposed.items()]
        )
        self._commit(snapshots, before, "after", "applied", "abandoned")
        self.editor.index.refresh()
        edits = []
        for snapshot in snapshots:
            path = Path(snapshot["path"])
            after_impact = self.editor._impact(path)
            self.state.put_artifact(
                "edit-impact", str(snapshot["id"]), {"before": impacts[path], "after": after_impact}
            )
            diff = file_diff(labels[path], before[path], proposed[path])
            edits.append(
                {
                    "path": labels[path],
                    "snapshot": snapshot["id"],
                    "diff": diff,
                    "impact_before": impacts[path],
                    "impact_after": after_impact,
                }
            )
        return {
            "batch": snapshots[0]["batch"],
            "edits": edits,
            "diff": "".join(edit["diff"] for edit in edits),
            "semantic_gate": semantic,
            "verification": "Combined syntax and known semantic gates passed; tests not yet executed",
        }

    def rollback(self, snapshot):
        snapshots = self.state.snapshot_group(snapshot["batch"])
        expected = {Path(s["path"]): self.read(Path(s["path"])) for s in snapshots}
        for item in snapshots:
            allowed = (
                (item["before"], item["after"])
                if snapshot["status"] == "incomplete"
                else (item["after"],)
            )
            if expected[Path(item["path"])] not in allowed:
                raise ValueError(
                    "File changed after the grouped edit; rollback would overwrite newer work"
                )
        self.state.finish_group(snapshot["batch"], "pending-rollback")
        self._commit(snapshots, expected, "before", "rolled-back", snapshot["status"])
        self.editor.index.refresh()
        return {"restored": [s["path"] for s in snapshots], "batch": snapshot["batch"]}
