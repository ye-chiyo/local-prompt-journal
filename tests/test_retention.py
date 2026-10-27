import base64
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import threading
import unittest
from urllib.request import urlopen

from prompt_journal import Journal
from prompt_journal.storage import decode_package, encode_package
from prompt_journal.topology import pointer
from prompt_journal.web import create_server
from tests.fixtures.attachment_facts import PNG


def capture(text='保留的用户原文'):
    noise = random.Random(73).randbytes(100000).hex()
    items = [
        {'id': 'user', 'type': 'userMessage', 'content': [
            {'type': 'text', 'text': text},
            {'type': 'image', 'url': 'data:image/png;base64,' + base64.b64encode(PNG).decode()}]},
        {'id': 'tool', 'type': 'commandExecution', 'command': 'delete-tool-command',
         'status': 'completed', 'exitCode': 0, 'aggregatedOutput': 'delete-tool-result' + noise},
        {'id': 'unknown', 'type': 'futureUnsupported', 'payload': 'delete-unsupported-payload' + noise},
        {'id': 'ai', 'type': 'agentMessage', 'phase': 'final_answer', 'text': '保留 AI 原文与代码 tool()'}]
    entries = [{'turnId': 'turn', 'item': item} for item in items]
    return {'thread': {'id': 'dialogue', 'name': '保留对话', 'createdAt': 100, 'cwd': 'C:/Dialogue'},
            'turns': [({'id': 'turn', 'startedAt': 100, 'status': 'completed', 'items': deepcopy(items)}, '#/evidence/0')],
            'items': [(entry, f'#/evidence/1/response/result/data/{i}') for i, entry in enumerate(entries)],
            'evidence': [{'method': 'initialize', 'params': {}, 'response': {'result': {}}, 'raw': 'handshake'},
                         {'method': 'thread/items/list', 'params': {}, 'sha256': 'original-response-checksum',
                          'raw': json.dumps(entries), 'response': {'result': {'data': entries}}}],
            'source': {'instance': 'retention-fixture', 'version': 'fixture'}}


class DialogueRetentionAcceptance(unittest.TestCase):
    def test_all_versions_keep_dialogue_and_attachments_but_remove_execution_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = Journal(root / 'data')
            first = app.save_capture(capture())
            app.save_capture(capture('用户修改后的完整原文'))
            app.save_collection_state({'enabledAt': 90, 'sessions': [], 'error': None})
            backup = root / 'backup' / 'journal.sqlite3'
            report = app.prune_tools(backup)
            self.assertTrue(report['verified'])
            self.assertEqual((report['snapshots'], report['deletedSnapshots']), (2, 0))
            self.assertLess(report['bytesAfter'], report['bytesBefore'])
            app = Journal(app.data_dir)
            self.assertEqual(app.collection_state()['enabledAt'], 90)
            old = app.turn('dialogue', 'turn', saved_at=first['savedAt'])['session']
            self.assertEqual([m['text'] for m in old['messages']], ['保留的用户原文', '保留 AI 原文与代码 tool()'])
            self.assertEqual((old['tools'], old['unsupportedItems']), ([], []))
            self.assertEqual(app.attachment('dialogue', old['attachments'][0]['id'], saved_at=first['savedAt'], turn_id='turn')[1], PNG)
            exported = json.loads(app.export_session('dialogue'))
            self.assertEqual(exported['evidence'][0]['response']['result']['retainedItems'], [])
            self.assertEqual(exported['evidence'][1]['method'], 'thread/items/list')
            for document in (exported, *exported['revisions']):
                for message in document['session']['messages']:
                    self.assertEqual(pointer(exported, message['evidenceRef'])['id'], message['id'])
                attachment = document['session']['attachments'][0]
                self.assertTrue(pointer(exported, attachment['evidenceRef']).startswith('data:image/png;base64,'))
            serialized = json.dumps(exported)
            for removed in ('delete-tool-command', 'delete-tool-result', 'delete-unsupported-payload'):
                self.assertNotIn(removed, serialized)
            self.assertEqual(app.search('用户修改')['total'], 1)
            self.assertEqual(app.search('delete-tool-result')['total'], 0)
            server = create_server(app, 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                html = urlopen(f'http://127.0.0.1:{server.server_port}/session/dialogue/turn/turn').read().decode()
                self.assertNotIn('工具调用与最终结果', html)
                self.assertIn('用户修改后的完整原文', html)
                self.assertIn('已归档附件', html)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(2)
            recovered = Journal(backup.parent).turn('dialogue', 'turn')['session']
            self.assertEqual(recovered['tools'][0]['arguments']['command'], 'delete-tool-command')
            self.assertEqual(recovered['unsupportedItems'][0]['type'], 'futureUnsupported')

    def test_restart_and_new_captures_do_not_restore_tools_or_save_tool_only_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = Journal(root / 'data')
            app.save_capture(capture())
            app.prune_tools(root / 'backup.sqlite3')
            app = Journal(app.data_dir)
            updated = capture()
            updated['items'][1][0]['item']['aggregatedOutput'] = 'new tool result that must not be saved'
            updated['thread']['updatedAt'] = 999
            updated['source']['pagination'] = {'itemPages': 12}
            entries = [entry for entry, _ in updated['items']]
            entries.insert(3, {'turnId': 'turn', 'item': {'id': 'extra-tool', 'type': 'commandExecution',
                            'command': 'added-tool', 'status': 'completed', 'exitCode': 0, 'aggregatedOutput': 'extra'}})
            updated['items'] = [(entry, f'#/evidence/1/response/result/data/{i}') for i, entry in enumerate(entries)]
            updated['evidence'][1]['response']['result']['data'] = entries
            updated['evidence'][1]['raw'] = json.dumps(entries)
            updated['turns'][0][0]['items'] = [deepcopy(entry['item']) for entry in entries]
            updated['turns'][0][0]['durationMs'] = 500
            app.save_capture(updated)
            self.assertNotIn('revisions', json.loads(app.export_session('dialogue')))
            app.save_capture(capture('后续新消息'))
            result = json.loads(app.export_session('dialogue'))
            self.assertEqual(result['session']['messages'][0]['text'], '后续新消息')
            self.assertEqual(len(result['revisions']), 1)
            for document in (result, *result['revisions']):
                self.assertEqual(document['session']['tools'], [])
                self.assertEqual(document['session']['unsupportedItems'], [])
            self.assertNotIn('delete-tool-result', json.dumps(result))

    def test_existing_backup_and_invalid_source_evidence_never_destroy_saved_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = Journal(root / 'data')
            app.save_capture(capture())
            existing = root / 'existing.sqlite3'
            existing.write_bytes(b'keep-existing')
            with self.assertRaises(ValueError):
                app.prune_tools(existing)
            self.assertEqual(existing.read_bytes(), b'keep-existing')
            with closing(sqlite3.connect(app.database)) as db, db:
                package = decode_package(db.execute('SELECT package FROM snapshots').fetchone()[0])
                package['session']['messages'][0]['id'] = 'broken-source-identity'
                original = encode_package(package)
                db.execute('UPDATE snapshots SET package=?', (original,))
            with self.assertRaises(ValueError):
                app.prune_tools(root / 'failed-backup.sqlite3')
            with closing(sqlite3.connect(app.database)) as db:
                self.assertEqual(db.execute('SELECT package FROM snapshots').fetchone()[0], original)
            self.assertTrue(app.turn('dialogue', 'turn')['session']['tools'])
