import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/moss/scripts'
sys.path.insert(0, str(SCRIPTS))
import migrate as g


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'existing'
        self.vault.mkdir()
        self.plan = self.root / 'plan.json'
        self.output = self.root / 'prepared'

    def put(self, path, text):
        p = self.vault / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')

    def audit(self):
        g.audit(self.vault, self.plan)
        return g.moss.read_json(self.plan)

    def test_adoption_preserves_original_and_rewrites_links(self):
        self.put('old_0123456789abcdef.md', '# 읽기 쉬운 제목\nEvidence unchanged.\n![](photo.png)\n')
        self.put('index.md', '# index\n[[old_0123456789abcdef#Section|alias]]\n[read](old_0123456789abcdef.md)\n`[[old_0123456789abcdef]]`\n')
        self.put('photo.png', 'binary bytes')
        self.put('map.canvas', json.dumps({'nodes': [{'id':'a','type':'file','file':'old_0123456789abcdef.md'}], 'edges':[]}))
        plan = self.audit()
        plan['moves'][0]['to'] = 'Notes/읽기 쉬운 제목.md'
        g.moss.save(self.plan, plan)
        before = g.inventory(self.vault)
        g.prepare(self.plan, self.output)
        self.assertEqual(before, g.inventory(self.vault))
        stage = self.output / 'vault'
        self.assertIn('![](../photo.png)', (stage / 'Notes/읽기 쉬운 제목.md').read_text(encoding='utf-8'))
        index = (stage / 'index.md').read_text(encoding='utf-8')
        self.assertIn('[[Notes/읽기 쉬운 제목#Section|alias]]', index)
        self.assertIn('`[[old_0123456789abcdef]]`', index)
        result = g.activate(self.output, self.root / 'config.json')
        self.assertEqual(before, g.inventory(Path(result['backup'])))
        self.assertTrue(result['doctor']['ok'])
        self.assertEqual((self.vault / 'photo.png').read_bytes(), b'binary bytes')

    def test_stale_source_and_preview_refused(self):
        self.put('old.md', '# New\n')
        self.audit()
        self.put('extra.md', '# extra\n')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            g.prepare(self.plan, self.output)
        self.plan.unlink(); self.audit()
        g.prepare(self.plan, self.output)
        (self.output / 'vault/New.md').write_text('modified')
        with self.assertRaisesRegex(ValueError, 'Preview changed'):
            g.activate(self.output, self.root / 'config.json')

    def test_collision_and_escape(self):
        self.put('one.md', '# same\n'); self.put('two.md', '# same\n')
        plan = self.audit()
        with self.assertRaisesRegex(ValueError, 'collision'):
            g.mapping_for(plan)
        plan['moves'][0]['to'] = '../escape.md'
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            g.mapping_for(plan)

    def test_template_conflict_preserves_source(self):
        self.put('Home.md', '# Home\nPersonal source')
        self.audit()
        before = g.inventory(self.vault)
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            g.prepare(self.plan, self.output)
        self.assertEqual(before, g.inventory(self.vault))

    def test_ambiguous_links_and_reference_definition(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            g.rewrite('[[Note]]', 'root.md', {'a/Note.md':'a/Note.md','b/Note.md':'b/Note.md','root.md':'root.md'}, [])
        result = g.rewrite('[x]: old.md "Title"\n', 'i.md', {'old.md':'New name.md','i.md':'i.md'}, [])
        self.assertEqual(result, '[x]: New%20name.md "Title"\n')

    def test_activation_failure_restores_original(self):
        self.put('old.md', '# New\n')
        self.audit(); g.prepare(self.plan, self.output)
        before = g.inventory(self.vault)
        real = Path.rename
        def fail_stage(path, target):
            if path.name.startswith('.moss-ready-') and not path.name.endswith('-original'):
                raise OSError('simulated replacement failure')
            return real(path, target)
        with patch.object(Path, 'rename', fail_stage):
            with self.assertRaises(OSError):
                g.activate(self.output, self.root / 'config.json')
        self.assertEqual(before, g.inventory(self.vault))

    def test_plugin_paths_require_review(self):
        self.put('old.md', '# New\n')
        self.put('.obsidian/workspace.json', '{"file": "old.md"}')
        self.audit(); g.prepare(self.plan, self.output)
        with self.assertRaisesRegex(ValueError, 'manual_reference_review'):
            g.activate(self.output, self.root / 'config.json')
        self.assertTrue((self.vault / 'old.md').exists())

    def test_markdown_titles_and_embeds(self):
        mapping = {'old.md':'New name.md','i.md':'i.md'}
        result = g.rewrite('![image](old.md "Caption")\n![[old#^block|200]]', 'i.md', mapping, [])
        self.assertIn('![image](New%20name.md "Caption")', result)
        self.assertIn('![[New name#^block|200]]', result)


if __name__ == '__main__':
    unittest.main()
