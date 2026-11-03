from contextlib import closing
from copy import deepcopy
import html as html_module
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import unittest
from urllib.request import urlopen
from unittest.mock import patch

from prompt_journal import Journal
from prompt_journal.web import create_server
from tests.fixtures.catalog_facts import catalog_capture


def long_session():
    capture = catalog_capture('session-00', 0, text='会话零的独立正文')
    template = deepcopy(capture['turns'][0][0])
    capture['turns'] = []
    capture['items'] = []
    data = capture['evidence'][0]['response']['result']['data'] = []
    for i in range(65):
        turn = deepcopy(template)
        turn['id'] = f'turn-{i + 1}'
        capture['turns'].append((turn, '#/evidence/0'))
        for item in turn['items']:
            entry = {'turnId': turn['id'], 'item': item}
            capture['items'].append((entry, f'#/evidence/0/response/result/data/{len(data)}'))
            data.append(entry)
    return capture


class SessionPaginationAcceptance(unittest.TestCase):
    def test_pages_hold_ten_sessions_and_long_session_loads_more_without_bodies(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            first = app.save_capture(long_session())
            for i in range(1, 23):
                app.save_capture(catalog_capture(f'session-{i:02}', i))
            server = create_server(app, port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            connect = sqlite3.connect
            def metadata_only(*args, **kwargs):
                db = connect(*args, **kwargs)
                db.set_authorizer(lambda action, table, column, database, trigger:
                    sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and
                    ((table == 'snapshots' and column == 'package') or (table == 'turn_payloads' and column == 'body')) else sqlite3.SQLITE_OK)
                return db
            def read(path):
                with urlopen(base + path) as response:
                    return response.read().decode()
            try:
                with patch('sqlite3.connect', side_effect=metadata_only):
                    pages = [app.project_directory(first['project']['id'], offset=o) for o in (0, 10, 20)]
                    self.assertEqual([len(p['sessionGroups']) for p in pages], [10, 10, 3])
                    identities = [g['session']['id'] for p in pages for g in p['sessionGroups']]
                    self.assertEqual(identities, [f'session-{i:02}' for i in range(23)])
                    self.assertEqual(pages[0]['sessionGroups'][0]['total'], 65)
                    self.assertEqual(len(pages[0]['sessionGroups'][0]['turns']), 30)
                    page = read('/project/' + first['project']['id'])
                    self.assertIn('每页 10 个会话 · 共 23 个会话', page)
                    self.assertIn('1 / 3', page)
                    self.assertNotIn('会话零的独立正文', page)
                    self.assertNotIn('目录会话-session-10', page)
                    href = html_module.unescape(re.search(r'data-turn-more="([^"]+)"', page)[1])
                    more = read(href)
                    self.assertIn('回合 31', more)
                    self.assertNotIn('data-turn-ordinal="30"', more)
                    last = read(html_module.unescape(re.search(r'data-turn-more="([^"]+)"', more)[1]))
                    self.assertIn('回合 65', last)
                    self.assertNotIn('data-turn-more', last)
                    self.assertIn('3 / 3', read('/project/' + first['project']['id'] + '?offset=20&limit=10'))
                    legacy = read('/project/' + first['project']['id'] + '?offset=0&limit=30')
                    self.assertIn('每页 10 个会话', legacy)
                    self.assertNotIn('目录会话-session-10', legacy)
                reader = read('/session/session-00/turn/turn-65?source=catalog-fixture')
                self.assertIn('会话零的独立正文', reader)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(2)
