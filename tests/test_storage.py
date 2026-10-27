import json
from contextlib import closing
import sqlite3
from pathlib import Path
import tempfile
import unittest

from prompt_journal import Journal
from tests.fixtures.catalog_facts import catalog_capture


class LosslessStorageAcceptance(unittest.TestCase):
    def test_compaction_reduces_files_and_preserves_every_saved_version_and_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = Journal(root / 'data')
            captures = [catalog_capture(text=prefix + '重复工具输出' * 40000) for prefix in ('首版完整原文', '新版完整原文')]
            saved = [app.save_capture(capture) for capture in captures]
            first = saved[0]
            # Seed the previous TEXT storage format at the database boundary.
            with closing(sqlite3.connect(app.database)) as db, db:
                for session, capture in zip(saved, captures):
                    package = {'schemaVersion': 1, 'session': session, 'evidence': capture['evidence']}
                    db.execute('UPDATE snapshots SET package=? WHERE saved=?', (json.dumps(package, ensure_ascii=False), session['savedAt']))
            expected = json.loads(app.export_session('catalog-1'))
            backup = root / 'backup' / 'journal.sqlite3'
            report = app.compact(backup)
            reopened = Journal(app.data_dir)
            self.assertEqual(json.loads(reopened.export_session('catalog-1')), expected)
            self.assertEqual(reopened.session('catalog-1', saved_at=first['savedAt'])['messages'][0]['text'],
                             '首版完整原文' + '重复工具输出' * 40000)
            self.assertEqual(report['snapshots'], 2)
            self.assertTrue(report['verified'])
            self.assertLess(report['bytesAfter'], report['bytesBefore'] / 3)
            self.assertEqual(json.loads(Journal(backup.parent).export_session('catalog-1')), expected)
            reopened.save_capture(catalog_capture('new-session', instance='other-source'))
            self.assertEqual(len(reopened.sessions()), 2)
            reopened.delete_session('catalog-1', 'catalog-fixture')
            self.assertEqual([s['id'] for s in reopened.sessions()], ['new-session'])
            self.assertEqual(len(Journal(backup.parent).sessions()), 1)

    def test_compaction_refuses_existing_backup_and_the_database_itself(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            app.save_capture(catalog_capture())
            for backup in (app.database, Path(temp) / 'existing.sqlite3'):
                if backup != app.database:
                    backup.write_bytes(b'keep-existing')
                with self.subTest(backup=backup), self.assertRaises(ValueError):
                    app.compact(backup)
            self.assertEqual(app.session('catalog-1')['messages'][0]['text'], '目录不应加载的正文')
