import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from prompt_journal import Journal
from prompt_journal.source import HistoryError
from prompt_journal.web import create_server
from tests.fixtures.catalog_facts import catalog_capture


class ProjectDeletionAcceptance(unittest.TestCase):
    def test_home_confirmation_scope_change_and_same_name_project_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            capture = catalog_capture(text='待删除项目独有正文')
            first = app.save_capture(capture)
            app.save_capture(catalog_capture('catalog-2', text='同项目第二会话'))
            other = app.save_capture(catalog_capture(instance='other-source', text='另一个来源的同名项目'))
            server = create_server(app, port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            route = '/manage/delete-project/' + first['project']['id']
            def read(path):
                with urlopen(base + path) as response:
                    return response.read().decode()
            def fields(html):
                return {name: re.search(f'name="{name}" value="([^"]+)"', html)[1] for name in ('token', 'fingerprint')}
            def post(values, headers=None):
                return urlopen(Request(base + route, data=urlencode(values).encode(), headers=headers or {}))
            try:
                self.assertIn('href="' + route + '"', read('/'))
                review = read(route)
                self.assertIn('当前已归档的 2 个会话', review)
                self.assertIn('不改变 Codex 原会话', review)
                self.assertEqual(len(app.sessions()), 3)
                values = fields(review)
                for posted, headers in (({'fingerprint': values['fingerprint']}, {}), (values, {'Origin': 'http://evil.invalid'})):
                    with self.assertRaises(HTTPError) as error:
                        post(posted, headers)
                    self.assertEqual(error.exception.code, 403)
                app.save_capture(catalog_capture('new-session', text='确认之后新增的会话'))
                with self.assertRaises(HTTPError) as error:
                    post(values)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(len(app.sessions()), 4)
                with post(fields(read(route))) as response:
                    result = response.read().decode()
                self.assertIn('已删除项目归档', result)
                self.assertNotIn('href="/project/' + first['project']['id'] + '"', read('/'))
                self.assertEqual([p['id'] for p in app.projects()], [other['project']['id']])
                self.assertEqual(app.search('待删除项目独有正文')['total'], 0)
                self.assertEqual(app.session('catalog-1', 'other-source')['messages'][0]['text'], '另一个来源的同名项目')
                self.assertEqual(len(app.exclusions()), 3)
                with self.assertRaises(HistoryError):
                    app.save_capture(capture)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(2)

    def test_project_deletion_covers_sessions_beyond_a_directory_page(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            for i in range(105):
                saved = app.save_capture(catalog_capture(f'session-{i}', i))
            preview = app.project_deletion_preview(saved['project']['id'])
            self.assertEqual(len(preview['sessions']), 105)
            result = app.delete_project(saved['project']['id'], preview['fingerprint'])
            self.assertEqual(len(result['sessions']), 105)
            self.assertTrue(all(s['status'] == 'deleted' for s in result['sessions']))
            self.assertEqual(app.projects(), [])
            self.assertEqual(len(Journal(app.data_dir).exclusions()), 105)
