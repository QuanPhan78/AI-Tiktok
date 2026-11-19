"""Setup checks must remain read-only and distinguish local use from publishing."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import check_setup


class SetupChecksTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='studio setup ')))
        (self.root / 'integrations/long-v2').mkdir(parents=True)
        self.enterContext(patch.object(check_setup, 'tool_path', return_value='synthetic-tool'))
        self.command = self.enterContext(patch.object(check_setup, 'command_ok', return_value=True))

    def write(self, relative, values):
        (self.root / relative).write_text(''.join(f'{k}={v}\n' for k, v in values.items()), encoding='utf-8')

    def automation(self):
        self.write('.env', {'GEMINI_API_KEY': 'synthetic-ai-value', 'WEBHOOK_V2_TOKEN': 'synthetic-shared-value'})
        values = {name: 'synthetic-value' for name in (
            'GEMINI_API_KEY', 'NOTION_TOKEN', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID',
            'TELEGRAM_WEBHOOK_SECRET', 'TELEGRAM_AUTHORIZED_USER_IDS')}
        values.update(WEBHOOK_V2_TOKEN='synthetic-shared-value', NOTION_DATABASE_ID='database-one',
                      NOTION_V2_DATABASE_ID='database-two')
        self.write('integrations/long-v2/.env', values)
        return values

    def test_studio_does_not_require_automation_or_docker(self):
        self.write('.env', {'GEMINI_API_KEY': 'synthetic-ai-value'})
        checks = check_setup.inspect_setup(self.root)
        self.assertTrue(all(row['ok'] for row in checks), checks)
        self.command.assert_not_called()

    def test_missing_files_are_reported_without_creating_them(self):
        checks = check_setup.inspect_setup(self.root, 'automation')
        self.assertFalse(all(row['ok'] for row in checks))
        self.assertFalse((self.root / '.env').exists())
        self.assertFalse((self.root / 'integrations/long-v2/.env').exists())

    def test_placeholder_and_inherited_keys_do_not_pass(self):
        self.write('.env', {'GEMINI_API_KEY': 'your_key_here'})
        with patch.dict('os.environ', GEMINI_API_KEY='synthetic-inherited-value'):
            checks = check_setup.inspect_setup(self.root)
        self.assertFalse(next(row for row in checks if row['label'] == '.env: GEMINI_API_KEY')['ok'])
        self.write('.env', {'GEMINI_API_KEY': '${GEMINI_API_KEY}'})
        with patch.dict('os.environ', GEMINI_API_KEY='synthetic-inherited-value'):
            checks = check_setup.inspect_setup(self.root)
        self.assertFalse(next(row for row in checks if row['label'] == '.env: GEMINI_API_KEY')['ok'])

    def test_automation_valid_settings_remain_unchanged_and_values_are_hidden(self):
        self.automation()
        before = {p: p.read_bytes() for p in self.root.rglob('.env')}
        checks = check_setup.inspect_setup(self.root, 'automation')
        self.assertTrue(all(row['ok'] for row in checks), checks)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertNotIn('synthetic-shared-value', str(checks))
        self.assertNotIn('synthetic-ai-value', str(checks))

    def test_mismatched_tokens_and_same_database_are_rejected(self):
        values = self.automation()
        values.update(WEBHOOK_V2_TOKEN='synthetic-different', NOTION_V2_DATABASE_ID='databaseone')
        self.write('integrations/long-v2/.env', values)
        checks = check_setup.inspect_setup(self.root, 'automation')
        failed = [row['label'] for row in checks if not row['ok']]
        self.assertIn('WEBHOOK_V2_TOKEN khớp hai file', failed)
        self.assertIn('Database thử v2 riêng', failed)

    def test_docker_not_started_is_separate_from_missing_compose(self):
        self.automation()
        self.command.side_effect = lambda cmd: cmd[-1] == 'version'
        checks = check_setup.inspect_setup(self.root, 'automation')
        self.assertTrue(next(row for row in checks if row['label'] == 'Docker Compose')['ok'])
        self.assertFalse(next(row for row in checks if row['label'] == 'Docker đang chạy')['ok'])

    def test_publishing_cannot_pass_with_only_automation_settings(self):
        self.automation()
        checks = check_setup.inspect_setup(self.root, 'publishing')
        self.assertFalse(all(row['ok'] for row in checks))
        self.assertTrue(any('lịch' in row['label'] and not row['ok'] for row in checks))

    def test_runtime_is_opt_in_and_only_probes_local_services(self):
        self.automation()
        with patch.object(check_setup, 'build_opener') as factory:
            check_setup.inspect_setup(self.root, 'automation')
            factory.assert_not_called()
            factory.return_value.open.return_value.__enter__.return_value.status = 200
            checks = check_setup.inspect_setup(self.root, 'automation', runtime=True)
        self.assertTrue(all(row['ok'] for row in checks), checks)
        urls = [call.args[0] for call in factory.return_value.open.call_args_list]
        self.assertEqual(len(urls), 4)
        self.assertTrue(all(url.startswith('http://127.0.0.1:') for url in urls))

    def test_cli_failure_does_not_print_credentials(self):
        self.write('.env', {'GEMINI_API_KEY': 'synthetic-confidential-value'})
        checks = check_setup.inspect_setup(self.root, 'automation')
        output = io.StringIO()
        with patch.object(check_setup, 'inspect_setup', return_value=checks), contextlib.redirect_stdout(output):
            self.assertEqual(check_setup.main(['--profile', 'automation']), 1)
        self.assertNotIn('synthetic-confidential-value', output.getvalue())


if __name__ == '__main__':
    unittest.main()
