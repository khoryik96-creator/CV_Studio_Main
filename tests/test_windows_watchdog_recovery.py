"""Regression contracts for Windows CV Studio watchdog recovery."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsWatchdogRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.watchdog = (ROOT / "WATCHDOG.vbs").read_text(encoding="utf-8")
        self.helper = (ROOT / "INSTANCE_PORT.ps1").read_text(encoding="utf-8")
        self.start = (ROOT / "START_HIDDEN.vbs").read_text(encoding="utf-8")
        self.stop = (ROOT / "STOP_CORE.ps1").read_text(encoding="utf-8")

    def test_watchdog_recovery_preserves_its_own_supervisor(self):
        self.assertIn(
            'If LCase(CStr(mode))="stop" Then cmd=cmd & " -PreserveWatchdog"',
            self.watchdog,
        )
        self.assertIn("[switch]$PreserveWatchdog", self.helper)

        stop_calls = list(
            re.finditer(
                r"(?m)^(?P<indent>\s*)Stop-CVStudioWatchdogs \$(?:record|again)\.Root\s*$",
                self.helper,
            )
        )
        self.assertEqual(len(stop_calls), 2)
        for call in stop_calls:
            prefix = self.helper[max(0, call.start() - 100) : call.start()]
            self.assertRegex(prefix, r"if \(-not \$PreserveWatchdog\) \{\s*$")

    def test_deliberate_stop_and_upgrade_still_remove_old_watchdogs(self):
        self.assertNotIn("PreserveWatchdog", self.start)
        self.assertNotIn("PreserveWatchdog", self.stop)
        self.assertIn("Stop-ExactWatchdog $Root", self.stop)
        self.assertIn('-Mode Stop -Root $Root -ExpectedPid $port.Pid', self.stop)

    def test_protected_build_rejects_the_old_self_terminating_contract(self):
        build_tool = (ROOT / "owner_build_tools" / "build_protected.py").read_text(
            encoding="utf-8"
        )
        self.assertGreaterEqual(build_tool.count('"-PreserveWatchdog"'), 2)
        self.assertGreaterEqual(build_tool.count('"[switch]$PreserveWatchdog"'), 2)


if __name__ == "__main__":
    unittest.main()
