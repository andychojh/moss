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
        m.configure(self.config, {'domains': [{'id': 'Development', 'label': 'Development', 'color': '#35A38B'}]})
        return m.register(self.config, self.project, key, 'Demo ' + key, 'Development')

    def test_neutral_start_and_lazy_unsorted(self):
        self.setup()
        self.assertEqual(m.domains(self.config)['domains'], [])
        self.assertEqual(list((self.vault / 'Areas').glob('*.md')), [])
        m.register(self.config, self.project, 'first', 'First project')
        self.assertEqual(m.domains(self.config)['domains'][0]['id'], 'Unsorted')
        self.assertTrue(m.doctor(self.config)['ok'])

    def test_custom_taxonomy_has_no_eight_domain_limit(self):
        profile = {'domains': [{'id': 'Area' + str(i), 'label': '나의 분야 ' + str(i), 'color': '#123456'} for i in range(12)]}
        result = m.setup(self.config, self.vault, profile=profile)
        self.assertTrue(result['doctor']['ok'])
        self.assertEqual(result['doctor']['domains'], 12)
        m.register(self.config, self.project, 'client', 'Client website', 'Area11')
        result = m.record(self.config, self.project, self.data)
        self.assertIn('Area11', result['note'])
        self.assertEqual(len(m.read_json(self.vault / 'System/Domain Map.canvas')['nodes']), 12)

    def test_relabel_keeps_routes_and_preserves_unrelated_settings(self):
        self.setup(); self.register()
        recorded = Path(m.record(self.config, self.project, self.data)['note'])
        before = recorded.read_bytes()
        routes = (self.vault / 'System/projects.json').read_bytes()
        graph = m.read_json(self.vault / '.obsidian/graph.json')
        graph['search'] = 'my custom filter'
        graph['colorGroups'].insert(0, {'query':'tag:#important', 'color':{'a':1,'rgb':1}})
        m.save(self.vault / '.obsidian/graph.json', graph)
        m.configure(self.config, {'domains':[{'id':'Development','label':'고객 작업','color':'#112233'}, {'id':'Wellbeing','label':'웰빙','color':'#ABCDEF'}]})
        self.assertEqual(recorded.read_bytes(), before)
        self.assertEqual((self.vault / 'System/projects.json').read_bytes(), routes)
        self.assertIn('# 고객 작업', (self.vault / 'Areas/Development.md').read_text('utf-8'))
        graph = m.read_json(self.vault / '.obsidian/graph.json')
        self.assertEqual(graph['search'], 'my custom filter')
        self.assertEqual(graph['colorGroups'][0]['query'], 'tag:#important')
        self.assertTrue(m.doctor(self.config)['ok'])

    def test_invalid_profiles_never_write(self):
        for ident in ('../escape', 'CON', 'Shared', 'foo/bar'):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                m.setup(self.config, self.vault, profile={'domains':[{'id':ident,'label':'Example','color':'#123456'}]})
            self.assertFalse(self.vault.exists())
        self.setup()
        before = {str(p): p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):
            m.configure(self.config, {'domains':[{'id':'A','label':'One','color':'#123456'},{'id':'a','label':'Two','color':'#123456'}]})
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.vault.rglob('*') if p.is_file()})

    def test_edited_navigation_is_not_overwritten(self):
        self.setup(); self.register()
        area = self.vault / 'Areas/Development.md'
        area.write_text(area.read_text('utf-8') + '\nMy own text', encoding='utf-8')
        before = {str(p): p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'User-edited'):
            m.configure(self.config, {'domains':[{'id':'Development','label':'New label','color':'#123456'}]})
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.vault.rglob('*') if p.is_file()})

    def test_interrupted_configuration_can_retry(self):
        self.setup()
        profile = {'domains':[{'id':'Studio','label':'My studio','color':'#123456'}]}
        real_write = m.write
        def interrupted(path, content):
            if path.name == 'Studio.md':
                raise OSError('simulated interruption')
            return real_write(path, content)
        with patch.object(m, 'write', interrupted), self.assertRaises(OSError):
            m.configure(self.config, profile)
        self.assertFalse(m.doctor(self.config)['ok'])
        with self.assertRaisesRegex(ValueError, 'exact profile'):
            m.configure(self.config, {'domains':[]})
        m.configure(self.config, profile)
        self.assertTrue(m.doctor(self.config)['ok'])

    def test_legacy_domains_are_inferred_without_moving_records(self):
        self.setup(); self.register()
        record = Path(m.record(self.config, self.project, self.data)['note'])
        before = record.read_bytes()
        area = (self.vault / 'Areas/Development.md').read_bytes()
        canvas = (self.vault / 'Knowledge Map.canvas').read_bytes()
        for rel in ('System/domains.json','System/Areas.md','System/Domain Map.canvas'):
            (self.vault / rel).unlink()
        self.assertEqual(m.domains(self.config)['domains'][0]['id'], 'Development')
        m.configure(self.config, {'domains':[{'id':'Community','label':'Community','color':'#ABCDEF'}]})
        self.assertEqual(record.read_bytes(), before)
        self.assertEqual((self.vault / 'Areas/Development.md').read_bytes(), area)
        self.assertEqual((self.vault / 'Knowledge Map.canvas').read_bytes(), canvas)
        self.assertTrue(m.doctor(self.config)['ok'])

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
        m.configure(self.config, {'domains':[{'id':'Research','label':'Research','color':'#4879C4'}]})
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
