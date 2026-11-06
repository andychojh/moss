import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('moss', ROOT / 'skills/moss/scripts/moss.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MossTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='moss-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config/config.json'
        self.vault = self.root / 'notes with spaces'
        self.agents = self.root / 'codex/AGENTS.md'
        self.agents.parent.mkdir()
        self.agents.write_text('Keep my existing project rules.\n', encoding='utf-8')
        self.project = self.root / 'source project'
        self.project.mkdir()
        self.data = json.loads((ROOT / 'skills/moss/references/record.example.json').read_text())

    def setup(self):
        return m.setup(self.config, self.vault, self.agents)

    def register(self, key='demo'):
        return m.register(self.config, self.project, key, 'Demo ' + key, 'Development')

    def test_setup_is_repeatable_and_preserves_edits(self):
        self.assertTrue(self.setup()['doctor']['ok'])
        home = self.vault / 'Home.md'
        home.write_text(home.read_text(encoding='utf-8') + '\nUser addition\n', encoding='utf-8')
        before = home.read_bytes()
        self.setup()
        self.assertEqual(before, home.read_bytes())
        text = self.agents.read_text()
        self.assertEqual(text.count(m.BEGIN), 1)
        self.assertTrue(text.startswith('Keep my existing project rules.\n'))
        self.assertEqual(len(list((self.config.parent / 'backups').glob('*.md'))), 1)

    def test_existing_vault_is_never_merged(self):
        self.vault.mkdir()
        (self.vault / 'private.md').write_text('private')
        before = self.agents.read_bytes()
        with self.assertRaises(ValueError):
            self.setup()
        self.assertEqual(before, self.agents.read_bytes())
        self.assertFalse(self.config.exists())
        self.assertEqual((self.vault / 'private.md').read_text(), 'private')

    def test_instructions_are_optional(self):
        before = self.agents.read_bytes()
        result = m.setup(self.config, self.vault)
        self.assertEqual(before, self.agents.read_bytes())
        self.assertTrue(result['doctor']['warnings'])

    def test_conflicting_or_malformed_instructions_stop_before_writes(self):
        for text in ('$obsidian-project-memory is configured', '<!-- BEGIN EXAMPLE OBSIDIAN PROJECT MEMORY -->', m.BEGIN):
            self.agents.write_text(text)
            with self.assertRaises(ValueError):
                self.setup()
            self.assertFalse(self.vault.exists())

    def test_standing_instructions_retain_custom_config(self):
        self.setup()
        self.assertIn('--config "' + self.config.resolve().as_posix() + '"', self.agents.read_text())

    def test_start_and_exact_root_selection(self):
        self.setup()
        self.register()
        before = self.config.read_bytes()
        self.assertEqual(m.start(self.config, self.project)['key'], 'demo')
        child = self.project / 'separate project'
        child.mkdir()
        self.assertEqual(m.start(self.config, child)['status'], 'registration_required')
        self.assertEqual(before, self.config.read_bytes())
        self.register('another')
        self.assertEqual(m.start(self.config, self.project)['status'], 'selection_required')
        with self.assertRaises(ValueError):
            m.record(self.config, self.project, self.data)

    def test_duplicate_revision_and_historical_body(self):
        self.setup()
        self.register()
        a = m.record(self.config, self.project, self.data)
        oldmeta, oldbody = m.parse_note(Path(a['note']))
        self.assertEqual(m.record(self.config, self.project, self.data)['status'], 'unchanged')
        self.data['facts'].append('A different result after a real rerun.')
        b = m.record(self.config, self.project, self.data)
        self.assertEqual(b['revision'], 2)
        meta, body = m.parse_note(Path(a['note']))
        self.assertEqual(oldbody, body)
        self.assertEqual(oldmeta['created_at'], meta['created_at'])
        self.assertFalse(meta['record_current'])
        self.assertIsNone(meta['reviewed'])
        self.assertEqual(m.doctor(self.config)['records'], 2)

    def test_task_cannot_silently_switch_projects(self):
        self.setup()
        self.register()
        self.register('other')
        m.record(self.config, self.project, self.data, 'demo')
        with self.assertRaises(ValueError):
            m.record(self.config, self.project, self.data, 'other')

    def test_safe_unicode_and_reserved_names(self):
        self.setup()
        m.register(self.config, self.project, 'unicode', '실험 Café', 'Research')
        self.data['title'] = 'CON'
        result = m.record(self.config, self.project, self.data)
        self.assertTrue(Path(result['note']).is_file())
        self.assertTrue(Path(result['note']).name.startswith('Note CON'))
        with self.assertRaises(ValueError):
            m.inside(self.vault, '../outside.md')

    def test_register_retry_repairs_missing_support(self):
        self.setup()
        with patch.object(m, 'support', side_effect=OSError('simulated support failure')):
            with self.assertRaises(OSError):
                self.register()
        self.register()
        self.assertTrue(m.doctor(self.config)['ok'])

    def test_retry_repairs_partial_revision_flag_write(self):
        self.setup()
        self.register()
        first = Path(m.record(self.config, self.project, self.data)['note'])
        self.data['facts'].append('Changed evidence')
        real_write = m.write
        def fail_old(path, text):
            if path == first:
                raise OSError('simulated flag write failure')
            real_write(path, text)
        with patch.object(m, 'write', side_effect=fail_old):
            with self.assertRaises(OSError):
                m.record(self.config, self.project, self.data)
        self.assertFalse(m.doctor(self.config)['ok'])
        self.assertEqual(m.record(self.config, self.project, self.data)['status'], 'unchanged')
        self.assertTrue(m.doctor(self.config)['ok'])
        self.assertEqual(m.doctor(self.config)['records'], 2)

    def test_lock_blocks_second_writer(self):
        self.setup()
        self.register()
        with m.lock(self.vault / 'System/.write-lock'):
            with self.assertRaises(ValueError):
                m.record(self.config, self.project, self.data)
        self.assertEqual(m.doctor(self.config)['records'], 0)

    def test_invalid_record_has_no_effect(self):
        self.setup()
        self.register()
        self.data['sources'] = []
        with self.assertRaises(ValueError):
            m.record(self.config, self.project, self.data)
        self.assertEqual(m.doctor(self.config)['records'], 0)

    def test_config_cannot_be_redirected_or_saved_inside_vault(self):
        with self.assertRaises(ValueError):
            m.setup(self.vault / 'config.json', self.vault)
        self.setup()
        with self.assertRaises(ValueError):
            m.setup(self.config, self.root / 'other vault')

    def test_template_has_no_projects_records_or_personal_paths(self):
        template = ROOT / 'skills/moss/assets/vault'
        self.assertEqual(m.read_json(template / 'System/projects.json')['projects'], {})
        self.assertFalse((template / 'Records').exists())
        for f in template.rglob('*'):
            if f.is_file():
                text = f.read_text(encoding='utf-8')
                self.assertNotRegex(text, r'[A-Za-z]:[\\/]Users[\\/]|/Users/|/home/[^/]+/')


if __name__ == '__main__':
    unittest.main()
