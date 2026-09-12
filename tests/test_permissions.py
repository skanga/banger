"""Behavioral tests for the permission boundary, independent of the TUI."""

import tempfile
import unittest
from pathlib import Path

from banger.permissions import Action, Decision, Mode, PermissionPolicy


class PermissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_reads_are_allowed_inside_workspace_in_every_mode(self):
        for mode in Mode:
            policy = PermissionPolicy(self.root, mode)
            self.assertEqual(policy.decide(Action("read", path="src/main.py")), Decision.ALLOW)

    def test_read_only_denies_mutations_even_if_previously_approved(self):
        policy = PermissionPolicy(self.root, Mode.FULL_ACCESS)
        command = Action("command", command="python -m unittest", cwd=str(self.root))
        policy.remember(command)
        policy.mode = Mode.READ_ONLY
        self.assertEqual(policy.decide(command), Decision.DENY)
        self.assertEqual(policy.decide(Action("edit", path="main.py")), Decision.DENY)

    def test_accept_edits_still_asks_for_commands_and_outside_paths(self):
        policy = PermissionPolicy(self.root, Mode.ACCEPT_EDITS)
        self.assertEqual(policy.decide(Action("edit", path="main.py")), Decision.ALLOW)
        self.assertEqual(policy.decide(Action("edit", path="../outside.py")), Decision.ASK)
        self.assertEqual(policy.decide(Action("command", command="echo hello")), Decision.ASK)

    def test_escalation_always_requires_confirmation(self):
        for mode in Mode:
            policy = PermissionPolicy(self.root, mode)
            action = Action("escalate")
            policy.remember(action)
            self.assertEqual(policy.decide(action), Decision.ASK)

    def test_remembered_commands_match_exact_text_and_working_directory(self):
        policy = PermissionPolicy(self.root, Mode.ASK)
        action = Action("command", command="python -m unittest", cwd=str(self.root))
        policy.remember(action)
        self.assertEqual(policy.decide(action), Decision.ALLOW)
        self.assertEqual(
            policy.decide(Action("command", command="python -m unittest && echo extra")),
            Decision.ASK,
        )
        self.assertEqual(
            policy.decide(Action("command", command=action.command, cwd="subdir")), Decision.ASK
        )

    def test_invalid_and_unknown_actions_fail_closed(self):
        policy = PermissionPolicy(self.root, Mode.FULL_ACCESS)
        for action in [Action("unknown"), Action("read"), Action("command")]:
            self.assertEqual(policy.decide(action), Decision.DENY)

    def test_sibling_with_shared_prefix_is_outside_workspace(self):
        policy = PermissionPolicy(self.root, Mode.ASK)
        sibling = str(self.root) + "-other/file.py"
        self.assertEqual(policy.decide(Action("read", path=sibling)), Decision.ASK)

    def test_default_asks_for_writes_and_full_access_allows_outside(self):
        action = Action("edit", path="../outside.py")
        self.assertEqual(PermissionPolicy(self.root, Mode.ASK).decide(action), Decision.ASK)
        self.assertEqual(
            PermissionPolicy(self.root, Mode.FULL_ACCESS).decide(action), Decision.ALLOW
        )

    def test_reset_discards_session_approvals(self):
        policy = PermissionPolicy(self.root, Mode.ASK)
        action = Action("command", command="echo hello")
        policy.remember(action)
        policy.reset_approvals()
        self.assertEqual(policy.decide(action), Decision.ASK)


if __name__ == "__main__":
    unittest.main()
