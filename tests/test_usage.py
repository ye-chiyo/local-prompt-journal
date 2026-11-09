"""Independent fixed numeric fixtures for metadata-only usage accounting."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError

from prompt_journal import Journal
from prompt_journal.usage import UsageMonitor, UsageReader, RETENTION_SECONDS, aggregate, expire
from prompt_journal.web import create_server


NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc).timestamp()


def record(kind, payload, at):
    return {'type': kind, 'timestamp': datetime.fromtimestamp(at, timezone.utc).isoformat(), 'payload': payload}


def event(kind, at, **payload):
    return record('event_msg', {'type': kind, **payload}, at)


def usage(total, last, at):
    def values(v):
        return dict(zip(('input_tokens', 'output_tokens', 'total_tokens', 'cached_input_tokens'), v))
    return event('token_count', at, info={'total_token_usage': values(total), 'last_token_usage': values(last)})


class UsageAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'codex'
        (self.home / 'sessions').mkdir(parents=True)
        self.path = self.home / 'sessions' / 'one.jsonl'
        self.app = Journal(Path(self.temp.name) / 'archive')
        self.instance = hashlib.sha256(str(self.home.resolve()).encode()).hexdigest()
        self.monitor = UsageMonitor(self.app.database, interval=.01)
        self.monitor.configure(self.instance, str(self.home), [
            {'id': 'one', 'cwd': 'C:/project'},
            {'id': 'child', 'cwd': 'C:/project', 'source': {'subagent': {}}, 'parentThreadId': 'one'},
            {'id': 'other', 'cwd': 'D:/project'}])
        self.reader = UsageReader(self.app.database, self.instance, self.home)

    def write(self, rows, path=None, append=False):
        with (path or self.path).open('a' if append else 'w', encoding='utf-8') as f:
            for r in rows:
                f.write(json.dumps(r) + '\n')

    def meta(self, identity='one', at=NOW-200):
        return record('session_meta', {'id': identity, 'timestamp': datetime.fromtimestamp(at, timezone.utc).isoformat(),
                                      'instructions': 'PRIVATE_DO_NOT_PERSIST'}, at)

    def start(self, turn='a', at=NOW-100, model='model-a'):
        return [event('task_started', at, turn_id=turn, started_at=at),
                record('turn_context', {'turn_id': turn, 'model': model, 'cwd': 'PRIVATE_DO_NOT_PERSIST'}, at+.1)]

    def result(self, **kw):
        return aggregate(self.app.database, current=NOW, **kw)

    def test_duplicate_cumulative_restart_model_switch_and_metadata_privacy(self):
        self.write([self.meta(), *self.start(),
                    usage([100, 10, 110, 40], [100, 10, 110, 40], NOW-90),
                    usage([100, 10, 110, 40], [100, 10, 110, 40], NOW-89),
                    record('turn_context', {'turn_id': 'a', 'model': 'model-b'}, NOW-88),
                    usage([300, 30, 330, 90], [200, 20, 220, 50], NOW-80),
                    event('task_complete', NOW-70, turn_id='a', last_agent_message='PRIVATE_DO_NOT_PERSIST')])
        self.reader.scan(NOW)
        self.reader.scan(NOW)
        UsageReader(self.app.database, self.instance, self.home).scan(NOW)
        result = self.result()
        self.assertEqual((result['summary']['rounds'], result['summary']['total'], result['summary']['cached']), (1, 330, 90))
        self.assertEqual({m['name']: m['total'] for m in result['models']}, {'model-a': 110, 'model-b': 220})
        for group in ('daily', 'hours', 'projects', 'models'):
            self.assertEqual(sum(r['total'] for r in result[group]), 330)
        with closing(sqlite3.connect(self.app.database)) as db:
            self.assertNotIn('PRIVATE_DO_NOT_PERSIST', '\n'.join(db.iterdump()))
        # Archived relocation replays the same source facts, without double charge.
        archive = self.home / 'archived_sessions'
        archive.mkdir()
        shutil.move(self.path, archive / 'one.jsonl')
        self.reader.scan(NOW)
        self.assertEqual(self.result()['summary']['total'], 330)

    def test_fork_baseline_reset_unknown_model_and_incomplete_records(self):
        self.write([self.meta('child'), *self.start(model=None),
                    usage([1000, 100, 1100, 500], [100, 10, 110, 50], NOW-99),
                    usage([1200, 120, 1320, 550], [200, 20, 220, 50], NOW-90),
                    usage([30, 3, 33, 10], [30, 3, 33, 10], NOW-80),
                    event('task_complete', NOW-70, turn_id='a')])
        self.reader.scan(NOW)
        self.assertEqual(self.result()['summary']['total'], 0)
        child = self.result(kind='child')
        self.assertEqual((child['summary']['total'], child['summary']['rounds'], child['gaps']), (253, 1, 1))
        self.assertEqual(child['models'][0]['name'], '模型未知')
        self.assertEqual(self.result(kind='all')['summary']['total'], 253)
        # Truncating and rewriting cannot revive inherited usage or duplicate facts.
        self.write([self.meta('child')])
        self.reader.scan(NOW)
        self.assertEqual(self.result(kind='child')['summary']['total'], 253)

    def test_inherited_turns_and_larger_same_inode_rewrite_are_not_charged_twice(self):
        old_start = NOW-300
        self.write([self.meta(at=NOW-200), *self.start(turn='inherited', at=old_start),
                    usage([100, 10, 110, 40], [100, 10, 110, 40], NOW-250),
                    event('task_complete', NOW-240, turn_id='inherited'),
                    *self.start(turn='local', at=NOW-100),
                    usage([300, 30, 330, 90], [200, 20, 220, 50], NOW-90),
                    event('task_complete', NOW-80, turn_id='local')])
        self.reader.scan(NOW)
        self.assertEqual((self.result()['summary']['rounds'], self.result()['summary']['total']), (1, 220))
        # Replace contents with more bytes, preserving the same file inode.
        self.write([self.meta(at=NOW-200), *self.start(turn='replacement', at=NOW-60),
                    usage([50, 5, 55, 20], [50, 5, 55, 20], NOW-50),
                    event('task_complete', NOW-40, turn_id='replacement'),
                    record('response_item', {'text': 'PRIVATE_DO_NOT_PERSIST'*100}, NOW-30)])
        self.reader.scan(NOW)
        self.assertEqual((self.result()['summary']['rounds'], self.result()['summary']['total']), (2, 275))

    def test_closed_child_with_explicit_known_parent_is_read_and_capacity_pauses(self):
        meta = self.meta('closed-child')
        meta['payload'].update(parent_thread_id='one', source={'subagent': {}}, cwd='C:/project')
        self.write([meta, *self.start(), usage([100, 10, 110, 40], [100, 10, 110, 40], NOW-90)])
        self.reader.scan(NOW)
        self.assertEqual(self.result(kind='child')['summary']['total'], 110)
        with closing(self.app._connect()) as db, db:
            db.execute("INSERT INTO collection_state VALUES ('capacity_limit_bytes','1')")
        self.assertTrue(self.reader.scan(NOW)['capacityPaused'])
        self.assertEqual(self.result()['status']['state'], 'paused')

    def test_midnight_uses_turn_start_and_token_event_time_independently(self):
        midnight = datetime(2026, 11, 8, 16, tzinfo=timezone.utc).timestamp()
        self.write([self.meta(at=midnight-300), *self.start(at=midnight-10),
                    usage([100, 10, 110, 40], [100, 10, 110, 40], midnight+5),
                    event('task_complete', midnight+10, turn_id='a')])
        self.reader.scan(midnight+20)
        result = aggregate(self.app.database, days=7, current=midnight+20)
        dates = {d['date']: d for d in result['daily']}
        self.assertEqual((dates['2026-11-08']['rounds'], dates['2026-11-08']['total']), (1, 0))
        self.assertEqual((dates['2026-11-09']['rounds'], dates['2026-11-09']['total']), (0, 110))
        self.assertEqual((result['hours'][23]['rounds'], result['hours'][0]['total']), (1, 110))

    def test_partial_append_retry_failures_missing_tokens_and_project_filter(self):
        self.write([self.meta(), *self.start(), event('task_complete', NOW-70, turn_id='a')])
        tail = json.dumps(event('task_started', NOW-50, turn_id='b', started_at=NOW-50))
        with self.path.open('a', encoding='utf-8') as f:
            f.write(tail[:30])
        self.reader.scan(NOW)
        self.assertEqual(self.result()['summary']['missingTokens'], 1)
        with self.path.open('a', encoding='utf-8') as f:
            f.write(tail[30:] + '\n')
        self.reader.scan(NOW)
        self.assertEqual(self.result()['summary']['running'], 1)
        self.write([event('turn_aborted', NOW-40, turn_id='b')], append=True)
        self.reader.scan(NOW)
        result = self.result()
        self.assertEqual(result['summary']['interrupted'], 1)
        project = next(p for p in result['projectChoices'] if p['label'] == 'C:/project')
        self.assertEqual(self.result(project=project['id'])['summary']['rounds'], 1)
        self.assertEqual(self.result(project='missing')['summary']['rounds'], 0)
        with self.path.open('a') as f:
            f.write('{bad json}\n')
        self.assertEqual(self.reader.scan(NOW)['failedFiles'], 1)
        self.assertEqual(self.result()['summary']['rounds'], 1)

    def test_retention_boundary_archive_is_preserved_and_old_data_not_reimported(self):
        cutoff = NOW-RETENTION_SECONDS
        self.write([self.meta(at=cutoff-200), *self.start(at=cutoff-100),
                    usage([100, 10, 110, 40], [100, 10, 110, 40], cutoff-90),
                    event('task_complete', cutoff-80, turn_id='a'),
                    *self.start(turn='b', at=cutoff),
                    usage([300, 30, 330, 90], [200, 20, 220, 50], cutoff),
                    event('task_complete', cutoff+1, turn_id='b')])
        with closing(self.app._connect()) as db, db:
            db.execute("INSERT INTO snapshots VALUES (1,'keep','keep','keep','KEEP_ARCHIVE')")
            db.execute("INSERT INTO collection_state VALUES ('enabledAt','42')")
        attachment = self.app.data_dir/'keep-attachment'
        attachment.write_bytes(b'KEEP_ATTACHMENT')
        self.reader.scan(NOW)
        with closing(self.app._connect()) as db, db:
            self.assertEqual(db.execute('SELECT SUM(total) FROM usage_events').fetchone()[0], 220)
            expire(db, NOW+2)
            self.assertEqual(db.execute('SELECT package FROM snapshots').fetchone()[0], 'KEEP_ARCHIVE')
            self.assertEqual(db.execute("SELECT value FROM collection_state WHERE key='enabledAt'").fetchone()[0], '42')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM usage_events').fetchone()[0], 0)
        self.assertEqual(attachment.read_bytes(), b'KEEP_ATTACHMENT')
        self.reader.scan(NOW+2)
        self.assertEqual(self.result()['summary']['total'], 0)

    def test_source_failure_can_recover_without_browser_and_invalid_api_range(self):
        self.write([self.meta(), *self.start(), usage([100, 10, 110, 40], [100, 10, 110, 40], NOW-90)])
        # Controlled clock data is read by the production worker, not browser polling.
        with patch('prompt_journal.usage.time.time', return_value=NOW):
            self.monitor.start()
            self.addCleanup(self.monitor.stop)
            import time
            deadline = time.monotonic()+5
            while time.monotonic()<deadline and self.result()['summary']['total'] != 110:
                time.sleep(.03)
            self.assertEqual(self.result()['summary']['total'], 110)
            with patch('prompt_journal.usage.UsageReader.scan', side_effect=OSError('controlled unavailable')):
                deadline = time.monotonic()+5
                while time.monotonic()<deadline and self.result()['status']['state'] != 'error':
                    time.sleep(.03)
                self.assertEqual(self.result()['status']['state'], 'error')
            self.write([usage([150, 15, 165, 60], [50, 5, 55, 20], NOW-60)], append=True)
            deadline = time.monotonic()+5
            while time.monotonic()<deadline and self.result()['summary']['total'] != 165:
                time.sleep(.03)
            self.monitor.stop()
        self.assertEqual(self.result()['summary']['total'], 165)
        server = create_server(self.app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with urlopen(base+'/usage') as response:
                html = response.read().decode()
                self.assertIn('/usage.js', html)
                self.assertNotIn('示例项目', html)
                self.assertNotIn('统计保存', html)
            with urlopen(base+'/api/usage') as response:
                self.assertEqual(json.load(response)['retentionDays'], 90)
            for suffix in ('usage.js', 'usage.css'):
                with urlopen(base+'/'+suffix) as response:
                    self.assertEqual(response.status, 200)
            with self.assertRaises(HTTPError) as error:
                urlopen(base+'/api/usage?days=999')
            self.assertEqual(error.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
