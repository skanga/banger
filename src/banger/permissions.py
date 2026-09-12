"""Authorization policy. This does not sandbox an approved process."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Mode(StrEnum):
    READ_ONLY = "read-only"
    ASK = "ask"
    ACCEPT_EDITS = "accept-edits"
    FULL_ACCESS = "full-access"


class Decision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class Action:
    kind: str
    path: str | None = None
    command: str | None = None
    cwd: str | None = None


class PermissionPolicy:
    def __init__(self, root: Path, mode: Mode):
        self.root = root.resolve()
        self.mode = mode
        self._approvals: set[tuple[str, str, str]] = set()

    def resolve(self, path: str) -> Path:
        return (self.root / path).resolve()

    def _key(self, action: Action) -> tuple[str, str, str]:
        if action.kind == "command":
            return (action.kind, action.command or "", str(self.resolve(action.cwd or ".")))
        return (action.kind, str(self.resolve(action.path or ".")), "")

    def remember(self, action: Action) -> None:
        if action.kind in {"read", "edit", "command"}:
            self._approvals.add(self._key(action))

    def reset_approvals(self):
        self._approvals.clear()

    def decide(self, action: Action) -> Decision:
        if action.kind == "escalate":
            return Decision.ASK
        if action.kind not in {"read", "edit", "command"}:
            return Decision.DENY
        if action.kind in {"read", "edit"} and not action.path:
            return Decision.DENY
        if action.kind == "command" and not (action.command or "").strip():
            return Decision.DENY
        if self.mode == Mode.READ_ONLY and action.kind != "read":
            return Decision.DENY
        if self.mode == Mode.FULL_ACCESS:
            return Decision.ALLOW
        if self._key(action) in self._approvals:
            return Decision.ALLOW
        if action.kind == "command":
            return Decision.ASK
        inside = self.resolve(action.path).is_relative_to(self.root)
        if not inside:
            return Decision.ASK
        if action.kind == "read" or self.mode == Mode.ACCEPT_EDITS:
            return Decision.ALLOW
        return Decision.ASK
