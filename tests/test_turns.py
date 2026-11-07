from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from prompt_journal import Journal
from prompt_journal.web import create_server
from prompt_journal.storage import encode_package
from tests.fixtures.catalog_facts import catalog_capture


def two_turns():
    capture = catalog_capture(text='第一回合原文')
    turn = deepcopy(capture['turns'][0][0])
    turn.update(id='turn-two', startedAt=200)
    turn['items'][0]['content'][0]['text'] = '第二回合独有正文'
    turn['items'][1]['aggregatedOutput'] = '第二回合最终工具结果'
    capture['turns'].append((turn, '#/evidence/0'))
    entries = capture['evidence'][0]['response']['result']['data']
    for item in turn['items']:
        entry = {'turnId': 'turn-two', 'item': deepcopy(item)}
        capture['items'].append((entry, f'#/evidence/0/response/result/data/{len(entries)}'))
        entries.append(entry)
    return capture


class IndependentTurnAcceptance(unittest.TestCase):
    def test_empty_turn_removed_from_directories_and_neighbors_after_upgrade_and_new_save(self):
        capture = two_turns()
        empty = {'id': 'empty', 'startedAt': 150, 'status': 'completed', 'items': []}
        capture['turns'].insert(1, (empty, '#/evidence/0'))
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            saved = app.save_capture(capture)
            # An existing archive created before the message-count projection.
            with closing(sqlite3.connect(app.database)) as db, db:
                db.execute('ALTER TABLE turn_entries DROP COLUMN content_count')
            app = Journal(app.data_dir)
            server = create_server(app, port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                for directory in (app.project_turns(saved['project']['id']), app.session_turns('catalog-1')):
                    self.assertEqual(directory['total'], 2)
                    self.assertEqual([t['ordinal'] for t in directory['turns']], [1, 3])
                self.assertEqual(app.turn('catalog-1', 'turn')['next'], 'turn-two')
                self.assertEqual(app.turn('catalog-1', 'turn-two')['previous'], 'turn')
                for path in ('/project/' + saved['project']['id'], '/session/catalog-1'):
                    with urlopen(base + path) as response:
                        html = response.read().decode()
                        self.assertIn('/turn/turn-two?', html)
                        self.assertNotIn('/turn/empty?', html)
                for suffix in ('', '&view=reader'):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(base + '/session/catalog-1/turn/empty?source=catalog-fixture' + suffix)
                    self.assertEqual(error.exception.code, 404)
                app.save_capture(capture)
                self.assertEqual(app.session_turns('catalog-1')['total'], 2)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)

    def test_directory_and_both_versions_read_only_the_selected_turn(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            first = app.save_capture(two_turns())
            old_hit = app.search('第一回合原文')['results'][0]
            changed = two_turns()
            changed['turns'][0][0]['items'][0]['content'][0]['text'] = '新版第一回合'
            changed['items'][0][0]['item']['content'][0]['text'] = '新版第一回合'
            app.save_capture(changed)
            server = create_server(app, port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            connect = sqlite3.connect
            def turn_only(*args, **kwargs):
                db = connect(*args, **kwargs)
                db.set_authorizer(lambda action, table, column, database, trigger:
                    sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == 'snapshots' and column == 'package'
                    else sqlite3.SQLITE_OK)
                return db
            base = f'http://127.0.0.1:{server.server_port}'
            def read(path):
                with urlopen(base + path) as response:
                    return response.read().decode()
            try:
                with patch('sqlite3.connect', side_effect=turn_only):
                    directory = read('/project/' + first['project']['id'])
                    self.assertIn('/session/catalog-1/turn/turn?', directory)
                    self.assertIn('/session/catalog-1/turn/turn-two?', directory)
                    self.assertNotIn('第一回合原文', directory)
                    self.assertNotIn('数据库文件', directory)
                    self.assertNotIn('search-form', directory.split('<main', 1)[1])
                    route = '/session/catalog-1/turn/turn?source=catalog-fixture'
                    html = read(route)
                    self.assertIn('新版第一回合', html)
                    self.assertNotIn('第二回合独有正文', html)
                    self.assertIn('下一回合', html)
                    old = read(route + '&' + urlencode({'saved': first['savedAt']}))
                    self.assertIn('第一回合原文', old)
                    self.assertNotIn('新版第一回合', old)
                    reader = read(route + '&' + urlencode({'saved': first['savedAt'], 'view': 'reader'}))
                    self.assertIn('第一回合原文', reader)
                    self.assertNotIn('第二回合独有正文', reader)
                    self.assertNotIn('新版第一回合', reader)
                    self.assertNotIn('<!doctype html>', reader)
                    self.assertNotIn('全局正文搜索', reader)
                    self.assertIn('<summary>版本</summary>', reader)
                    self.assertIn('saved=' + first['savedAt'].replace(':', '%3A').replace('+', '%2B'), reader)
                    legacy = read(old_hit['url'].replace('/turn/turn?', '?'))
                    self.assertIn('第一回合原文', legacy)
                    self.assertNotIn('新版第一回合', legacy)
                    item = json.loads(read('/api/session/catalog-1/item/user?' + urlencode(
                        {'source': 'catalog-fixture', 'turn': 'turn-two', 'kind': 'message', 'field': 'text'})))
                    self.assertEqual(item['text'], '第二回合独有正文')
                hit = app.search('第二回合独有正文')['results'][0]
                self.assertIn('/turn/turn-two?', hit['url'])
                self.assertIn('第二回合独有正文', read(hit['url']))
                self.assertIn('数据库文件', read('/status'))
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)

    def test_old_projection_rebuild_keeps_missing_attachment_references(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(Path(temp) / 'data')
            capture = catalog_capture()
            image = {'type': 'localImage', 'path': 'missing-old-image.png'}
            capture['turns'][0][0]['items'][0]['content'].append(image)
            capture['items'][0][0]['item']['content'].append(image)
            saved = app.save_capture(capture)
            legacy = {k: v for k, v in saved.items() if k != 'attachments'}
            groups = ('messages', 'tools', 'unsupportedItems', 'attachments')
            body = {'turns': legacy['turns'], **{k: legacy.get(k, []) for k in groups}}
            metadata = {k: v for k, v in legacy.items() if k not in (*groups, 'turns')}
            with closing(sqlite3.connect(app.database)) as db, db:
                db.execute('UPDATE snapshots SET package=?', (json.dumps({'session': legacy, 'evidence': capture['evidence']}),))
                db.execute('UPDATE turn_snapshots SET metadata=?', (json.dumps(metadata),))
                db.execute('UPDATE turn_payloads SET body=?', (encode_package(body),))
            reopened = Journal(app.data_dir)
            result = reopened.turn('catalog-1', 'turn')['session']
            self.assertEqual(len(result['attachments']), 1)
            self.assertEqual(result['attachments'][0]['status'], 'missing')
            self.assertIn('历史保存版本未归档附件', result['attachments'][0]['reason'])
