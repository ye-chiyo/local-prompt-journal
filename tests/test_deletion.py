import json
import http.client
from pathlib import Path
import sys
import tempfile
import time
import unittest
import re
import subprocess
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from prompt_journal import Journal, CodexHistory
from prompt_journal.source import HistoryError
from prompt_journal.sync import Collector
from prompt_journal.web import create_server
from tests.fixtures.attachment_facts import PNG, DOCUMENT, OTHER, facts


class ManagedDeletionAcceptance(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'sample.png').write_bytes(PNG)
        (self.root / 'sample.bin').write_bytes(DOCUMENT)
        (self.root / 'other').mkdir()
        (self.root / 'other' / 'sample.bin').write_bytes(OTHER)
        self.state = facts(self.root)
        self.path = self.root / 'source.json'
        self.publish()
        self.app = Journal(self.root / 'data')

    def publish(self):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.path)

    def source(self):
        return CodexHistory([sys.executable, str(Path(__file__).parent / 'fixtures' / 'automatic_source.py'), str(self.path)])

    def test_delete_removes_all_saved_versions_and_keeps_other_session_evidence_and_shared_bytes(self):
        with self.source() as source:
            for identity in ('main', 'child', 'empty'):
                self.app.import_session(identity, source)
            before = self.app.session('main')
            child = json.loads(self.app.export_session('child'))
            self.state['sessions'][0]['turns'][0]['items'][-2]['text'] = '第二版独有中文'
            self.publish()
            self.app.import_session('main', source)
        result = self.app.delete_session('main')
        self.assertEqual(result['status'], 'deleted')
        restarted = Journal(self.root / 'data')
        for read in (lambda: restarted.session('main'), lambda: restarted.session('main', saved_at=before['savedAt']),
                     lambda: restarted.evidence('main', 0), lambda: restarted.export_session('main'),
                     lambda: restarted.export_bundle('main')):
            with self.assertRaises(KeyError):
                read()
        self.assertEqual([s['id'] for s in restarted.sessions()], ['child', 'empty'])
        self.assertEqual(restarted.search('第二版独有中文')['total'], 0)
        remaining = json.loads(restarted.export_session('child'))
        self.assertEqual(remaining['evidence'], child['evidence'])
        self.assertEqual(remaining['session']['messages'], child['session']['messages'])
        self.assertEqual(remaining['session']['relations'][0]['availability'], 'deleted')
        attachment = restarted.session('child')['attachments'][0]
        self.assertEqual(restarted.attachment('child', attachment['id'])[1], PNG)
        # Managed byte identity is public export data; use its retained digest to
        # check the filesystem boundary, never inspect private SQLite tables.
        for attachment in before['attachments']:
            if attachment.get('status') == 'saved':
                exists = (self.root / 'data' / 'attachments' / attachment['sha256']).exists()
                self.assertEqual(exists, attachment['itemId'] in ('picture', 'shared'))
        self.assertTrue((self.root / 'sample.bin').exists())
        self.assertEqual(restarted.exclusions()[0]['id'], 'main')

    def await_view(self, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.03)
        self.fail('公开状态未取得预期结果')

    def test_exclusion_survives_collector_restart_and_restore_uses_original_scope(self):
        self.state['sessions'][0]['turns'].insert(0, {'id': 'old', 'startedAt': 180, 'status': 'completed', 'items': [
            {'id': 'old-message', 'type': 'userMessage', 'content': [{'type': 'text', 'text': '启用前不得恢复'}]}]})
        self.state['forbidBodyBefore'] = 190
        self.publish()
        collector = Collector(self.app, self.source, interval=.08, enabled_at=190)
        collector.start()
        self.addCleanup(collector.stop)
        self.await_view(lambda: len(self.app.sessions()) == 4)
        self.app.delete_session('main')
        previous = collector.status().get('lastCheckedAt')
        self.await_view(lambda: collector.status().get('lastCheckedAt') != previous)
        self.assertFalse(any(s['id'] == 'main' for s in self.app.sessions()))
        # Exclusion is checked before body retrieval, not only at persistence.
        self.state['sessions'][0]['fail'] = True
        self.publish()
        previous = collector.status().get('lastCheckedAt')
        self.await_view(lambda: collector.status().get('lastCheckedAt') != previous)
        self.assertFalse(any(s['id'] == 'main' and s.get('error') for s in collector.status()['sessions']))
        collector.stop()
        reopened = Journal(self.app.data_dir)
        with self.source() as source, self.assertRaisesRegex(HistoryError, '删除排除'):
            reopened.import_session('main', source)
        self.state['sessions'][0]['fail'] = False
        self.publish()
        self.assertEqual(reopened.restore_session('main')['status'], 'restored')
        self.assertEqual(reopened.collection_state()['enabledAt'], 190)
        restarted = Collector(reopened, self.source, interval=.08)
        restarted.start()
        self.addCleanup(restarted.stop)
        self.await_view(lambda: len(reopened.sessions()) == 4)
        self.assertEqual([t['id'] for t in reopened.session('main')['turns']], ['turn'])
        self.assertEqual(reopened.search('启用前不得恢复')['total'], 0)

    def test_same_id_from_another_source_and_late_capture_cannot_cross_deletion(self):
        with self.source() as source:
            first = source.instance()
            self.app.import_session('main', source)
            late = source.capture('main', 20)
        self.state['codexHome'] = 'other-source'
        self.publish()
        with self.source() as source:
            second = source.instance()
            self.app.import_session('main', source)
        with self.assertRaises(ValueError):
            self.app.delete_session('main')
        self.app.delete_session('main', first)
        with self.assertRaisesRegex(HistoryError, '删除排除'):
            Journal(self.app.data_dir).save_capture(late)
        self.assertEqual(self.app.session('main', second)['messages'][0]['id'], 'picture')
        with self.assertRaises(KeyError):
            self.app.session('main', first)

    def test_locked_managed_file_keeps_pending_deletion_and_restart_retries(self):
        import os
        from unittest.mock import patch
        with self.source() as source:
            saved = self.app.import_session('main', source)
        digest = next(a['sha256'] for a in saved['attachments'] if a['itemId'] == 'documents')
        real_unlink = os.unlink
        def locked(path, *args, **kwargs):
            if Path(path).name == digest:
                raise PermissionError('受控文件正被占用')
            return real_unlink(path, *args, **kwargs)
        # Filesystem is the external fault boundary; no internal module is mocked.
        with patch('os.unlink', side_effect=locked):
            result = self.app.delete_session('main')
            self.assertEqual(result['status'], 'cleanupPending')
            self.assertIn('受控文件正被占用', result['error'])
            with self.assertRaisesRegex(ValueError, '清理尚未完成'):
                self.app.restore_session('main')
            reopened = Journal(self.app.data_dir)
            self.assertEqual(reopened.exclusions()[0]['status'], 'cleanupPending')
            with self.assertRaises(KeyError):
                reopened.export_session('main')
        reopened = Journal(self.app.data_dir)
        self.assertEqual(reopened.exclusions()[0]['status'], 'deleted')
        self.assertFalse((self.app.data_dir / 'attachments' / digest).exists())

    def test_http_confirmation_and_cli_restore_operate_only_on_managed_archive(self):
        with self.source() as source:
            self.app.import_session('main', source)
        server = create_server(self.app, 0)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'
        session = urlopen(base + '/session/main').read().decode('utf-8')
        self.assertIn('删除此会话的受管理日志', session)
        html = urlopen(base + '/manage/delete/main').read().decode('utf-8')
        self.assertIn('不改变 Codex 原会话', html)
        self.assertIn('另存的导出副本', html)
        token = re.search(r'name="token" value="([^"]+)"', html).group(1)
        instance = self.app.session('main')['source']['instance']
        valid = {'source': instance, 'token': token}
        for values, headers in (({'source': instance}, {}), ({'source': instance, 'token': '中文无效'}, {}),
                (valid, {'Origin': 'null', 'Sec-Fetch-Site': 'cross-site'}),
                (valid, {'Origin': 'http://evil.invalid', 'Sec-Fetch-Site': 'same-origin'})):
            with self.assertRaises(HTTPError) as failure:
                urlopen(Request(base + '/manage/delete/main', data=urlencode(values).encode(), headers=headers))
            self.assertEqual(failure.exception.code, 403)
        self.assertEqual(self.app.session('main')['id'], 'main')
        # The app's sandboxed browser submits a same-origin form with an opaque
        # Origin. Reproduce the observed headers at the actual HTTP seam.
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
        self.addCleanup(connection.close)
        connection.request('POST', '/manage/delete/main', body=urlencode(valid).encode(), headers={
            'Origin': 'null', 'Sec-Fetch-Site': 'same-origin', 'Content-Type': 'application/x-www-form-urlencoded'})
        response = connection.getresponse()
        self.assertEqual(response.status, 303)
        result = urlopen(base + response.getheader('Location')).read().decode('utf-8')
        self.assertIn('已删除受管理日志', result)
        self.assertIn('解除删除排除', urlopen(base + '/manage/exclusions').read().decode('utf-8'))
        with self.assertRaises(HTTPError) as missing:
            urlopen(base + '/evidence/main/0')
        self.assertEqual(missing.exception.code, 404)
        args = [sys.executable, '-m', 'prompt_journal', '--data-dir', str(self.app.data_dir)]
        restored = subprocess.run(args + ['restore', 'main', '--source-instance', instance], capture_output=True, encoding='utf-8')
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(json.loads(restored.stdout)['status'], 'restored')
        self.assertEqual(self.app.exclusions(), [])
        with self.assertRaises(KeyError):
            self.app.session('main')
        with self.source() as source:
            self.app.import_session('main', source)
        deleted = subprocess.run(args + ['delete', 'main', '--yes'], capture_output=True, encoding='utf-8')
        self.assertEqual(deleted.returncode, 0, deleted.stderr)
        self.assertEqual(json.loads(deleted.stdout)['status'], 'deleted')
