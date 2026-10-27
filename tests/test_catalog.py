from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from prompt_journal import Journal
from tests.fixtures.catalog_facts import catalog_capture


class CatalogAcceptance(unittest.TestCase):
    def test_legacy_backfill_reopen_update_and_deletion_keep_directory_consistent(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            capture = catalog_capture()
            first = app.save_capture(capture)
            app.save_capture(catalog_capture('catalog-2', 200))
            app.save_capture(catalog_capture(instance='other-source'))
            # A legacy database has snapshots, but no materialized catalog.
            with closing(sqlite3.connect(app.database)) as db, db:
                legacy = {**first}
                legacy.pop('project')
                legacy.pop('createdAt')
                db.execute('UPDATE snapshots SET package=? WHERE instance=? AND thread=?',
                           (json.dumps({'schemaVersion': 1, 'session': legacy, 'evidence': capture['evidence']}), 'catalog-fixture', 'catalog-1'))
                db.execute('DROP TABLE session_catalog')
            app = Journal(app.data_dir)
            project = next(p for p in app.project_choices() if p['sourceInstance'] == 'catalog-fixture')
            page = app.project_sessions(project['id'], limit=1)
            self.assertEqual((page['total'], page['nextOffset'], page['sessions'][0]['id']), (2, 1, 'catalog-1'))
            self.assertEqual(page['sessions'][0]['createdAt'], 100)
            self.assertEqual(app.project_sessions(project['id'], offset=1, limit=1)['sessions'][0]['id'], 'catalog-2')
            changed = catalog_capture(text='更新后正文')
            changed['thread']['name'] = '更新后会话名称'
            app.save_capture(changed)
            self.assertEqual(app.project_sessions(project['id'])['sessions'][0]['name'], '更新后会话名称')
            self.assertEqual(len(Journal(app.data_dir).sessions()), 3)
            app.delete_session('catalog-1', 'catalog-fixture')
            self.assertEqual(app.project_sessions(project['id'])['total'], 1)
            self.assertEqual(app.session_summary('catalog-1', 'other-source')['id'], 'catalog-1')
            app.restore_session('catalog-1', 'catalog-fixture')
            self.assertEqual(app.project_sessions(project['id'])['total'], 1)

    def test_catalog_search_is_bounded_and_does_not_need_bodies(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            for i in range(65):
                app.save_capture(catalog_capture(f'catalog-{i:02}', i))
            first = app.project_sessions(limit=30)
            second = app.project_sessions(offset=30, limit=30)
            third = app.project_sessions(offset=60, limit=30)
            identities = [s['id'] for page in (first, second, third) for s in page['sessions']]
            self.assertEqual(identities, [f'catalog-{i:02}' for i in range(65)])
            self.assertIsNone(third['nextOffset'])
            self.assertEqual(app.project_sessions(query='catalog-64')['total'], 1)
            self.assertEqual(app.project_sessions(offset=100)['sessions'], [])
            with self.assertRaises(KeyError):
                app.project_sessions('missing')
