from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from cvstudio_startup import StartupService, _managed_windows_startup_path


class _FakeWinreg(types.ModuleType):
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_QUERY_VALUE = 2
    KEY_SET_VALUE = 4
    REG_SZ = 1

    def __init__(self, value=None):
        super().__init__("winreg")
        self.value = value
        self.deleted = False
        self.closed = 0
        self.set_values = []

    def OpenKey(self, *_args):
        return object()

    def QueryValueEx(self, _key, _name):
        if self.value is None:
            raise FileNotFoundError
        return self.value, self.REG_SZ

    def SetValueEx(self, _key, name, _reserved, kind, value):
        self.set_values.append((name, kind, value))
        self.value = value

    def DeleteValue(self, _key, _name):
        if self.value is None:
            raise FileNotFoundError
        self.deleted = True
        self.value = None

    def CloseKey(self, _key):
        self.closed += 1


class CvStartupStaleRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.root = str(Path(tempfile.gettempdir()) / "CV Studio Current")
        self.service = StartupService(
            jsonify=lambda payload: payload,
            root_path=lambda: self.root,
            instance_id=lambda: "fixture",
        )

    @staticmethod
    def _windows(fake):
        return mock.patch.multiple(
            "cvstudio_startup.platform",
            system=mock.Mock(return_value="Windows"),
        ), mock.patch.dict(sys.modules, {"winreg": fake})

    def test_only_exact_absolute_cv_studio_launcher_is_managed(self):
        self.assertEqual(
            _managed_windows_startup_path(
                'wscript.exe "C:\\Old CV Studio\\START_HIDDEN.vbs"'
            ),
            "C:\\Old CV Studio\\START_HIDDEN.vbs",
        )
        self.assertEqual(
            _managed_windows_startup_path(
                '"C:\\Windows\\System32\\wscript.exe" '
                '"D:\\CV Studio\\START_HIDDEN.vbs"'
            ),
            "D:\\CV Studio\\START_HIDDEN.vbs",
        )
        for unsafe in (
            'powershell.exe "C:\\Old\\START_HIDDEN.vbs"',
            'wscript.exe "relative\\START_HIDDEN.vbs"',
            'wscript.exe "C:\\Old\\OTHER.vbs"',
            'wscript.exe "C:\\Old\\START_HIDDEN.vbs" /extra',
        ):
            self.assertEqual(_managed_windows_startup_path(unsafe), "")

    def test_status_marks_old_managed_path_for_repair_without_mutating_it(self):
        old = 'wscript.exe "C:\\Deleted CV Studio\\START_HIDDEN.vbs"'
        fake = _FakeWinreg(old)
        platform_patch, module_patch = self._windows(fake)
        with platform_patch, module_patch:
            payload = self.service.status()
        self.assertTrue(payload["enabled"])
        self.assertFalse(payload["configured"])
        self.assertTrue(payload["repair_required"])
        self.assertEqual(fake.value, old)
        self.assertFalse(fake.deleted)
        self.assertEqual(fake.closed, 1)

    def test_enable_rebinds_the_product_value_to_current_root(self):
        fake = _FakeWinreg('wscript.exe "C:\\Old\\START_HIDDEN.vbs"')
        platform_patch, module_patch = self._windows(fake)
        with platform_patch, module_patch:
            payload = self.service.enable()
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(len(fake.set_values), 1)
        expected = 'wscript.exe "{}"'.format(
            os.path.join(self.root, "START_HIDDEN.vbs")
        )
        self.assertEqual(fake.set_values[0][2], expected)

    def test_disable_removes_old_managed_path_but_not_an_unknown_command(self):
        managed = _FakeWinreg('wscript.exe "C:\\Old\\START_HIDDEN.vbs"')
        platform_patch, module_patch = self._windows(managed)
        with platform_patch, module_patch:
            self.assertEqual(self.service.disable(), {"ok": True})
        self.assertTrue(managed.deleted)

        unknown = _FakeWinreg('cmd.exe /c "C:\\Tools\\custom.bat"')
        platform_patch, module_patch = self._windows(unknown)
        with platform_patch, module_patch:
            self.assertEqual(self.service.disable(), {"ok": True})
        self.assertFalse(unknown.deleted)
        self.assertEqual(unknown.value, 'cmd.exe /c "C:\\Tools\\custom.bat"')


if __name__ == "__main__":
    unittest.main()
