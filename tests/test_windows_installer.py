"""Exercise the real Windows installer without downloading packages or using credentials."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'win32', 'Windows PowerShell installer')
class WindowsInstallerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='Content Studio cài mới ')))
        (self.root / 'scripts').mkdir()
        (self.root / 'integrations/long-v2').mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/setup_windows.ps1', self.root / 'scripts/setup_windows.ps1')
        for name in ('.env.example', 'integrations/long-v2/.env.example',
                     'requirements.txt', 'requirements-test.txt'):
            shutil.copyfile(ROOT / name, self.root / name)
        # Intercept only pip in this disposable clone. The actual installer and Python run normally.
        (self.root / 'pip.py').write_text(
            "import json, os, sys\nfrom pathlib import Path\n"
            "Path('pip-request.json').write_text(json.dumps(sys.argv[1:]))\n"
            "raise SystemExit(int(os.getenv('TEST_INSTALLER_PIP_FAIL', '0')))\n", encoding='utf-8')
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(self.root / '.venv')],
                       check=True, capture_output=True, timeout=45)
        self.shell = shutil.which('powershell.exe') or shutil.which('pwsh.exe')
        if not self.shell:
            self.skipTest('PowerShell is unavailable')

    def run_installer(self, *args, fail_pip=False):
        return subprocess.run([self.shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                               str(self.root / 'scripts/setup_windows.ps1'), *args],
                              cwd=ROOT, env=dict(os.environ, TEST_INSTALLER_PIP_FAIL='1' if fail_pip else '0'),
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)

    def test_fresh_templates_and_second_run_preserve_settings_and_data(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ('.env', 'integrations/long-v2/.env'):
            self.assertEqual((self.root / name).read_bytes(), (self.root / (name + '.example')).read_bytes())
            (self.root / name).write_bytes(b'# synthetic existing settings\r\nKEEP_ME=local-only\r\n')
        (self.root / 'data').mkdir()
        data = self.root / 'data/keep.txt'
        data.write_bytes(b'synthetic session')
        before = {p: p.read_bytes() for p in [self.root / '.env', self.root / 'integrations/long-v2/.env', data]}
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        request = json.loads((self.root / 'pip-request.json').read_text())
        self.assertEqual(Path(request[-1]).name, 'requirements.txt')

    def test_with_tests_selects_test_dependencies(self):
        result = self.run_installer('-WithTests')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        request = json.loads((self.root / 'pip-request.json').read_text())
        self.assertEqual(Path(request[-1]).name, 'requirements-test.txt')

    def test_first_install_creates_a_python_environment(self):
        fresh = self.root / 'first installation'
        (fresh / 'scripts').mkdir(parents=True)
        (fresh / 'integrations/long-v2').mkdir(parents=True)
        for name in ('scripts/setup_windows.ps1', '.env.example', 'integrations/long-v2/.env.example',
                     'requirements.txt', 'pip.py'):
            shutil.copyfile(self.root / name, fresh / name)
        from unittest.mock import patch
        with patch.object(self, 'root', fresh):
            result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((fresh / '.venv/Scripts/python.exe').is_file())
        self.assertTrue((fresh / '.env').is_file())

    def test_installation_error_does_not_report_success_or_create_settings(self):
        result = self.run_installer(fail_pip=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Installation finished.', result.stdout)
        self.assertFalse((self.root / '.env').exists())


if __name__ == '__main__':
    unittest.main()
