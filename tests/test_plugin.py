"""Acceptance through packaged MCP stdio using independent archive facts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prompt_journal import Journal
from tests.fixtures.catalog_facts import catalog_capture
from tools.build_plugin import build


class LocalPluginAcceptance(unittest.TestCase):
    def test_packaged_manifest_exposes_website_entry_without_service_control(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = build(root / 'package')
            self.assertEqual(archive.name, 'local-journal.zip')

            plugin_root = root / 'package' / 'plugins' / 'local-journal'
            portable = json.loads((plugin_root / 'plugin.json').read_text(encoding='utf-8'))
            codex = json.loads((plugin_root / '.codex-plugin' / 'plugin.json').read_text(encoding='utf-8'))
            website = 'http://127.0.0.1:8766/'

            self.assertEqual(portable['version'], '0.1.1')
            self.assertEqual(codex['version'], '0.1.1')
            self.assertEqual(portable['extensions']['com.openai']['interface']['websiteURL'], website)
            self.assertEqual(codex['interface']['websiteURL'], website)
            self.assertEqual(portable['extensions']['com.openai']['interface']['capabilities'], ['Read'])

    def test_packaged_stdio_search_read_pagination_and_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = Journal(root / 'data')
            text = '独立事实：中文归档' + '长原文' * 2500
            session = app.save_capture(catalog_capture(text=text))
            app.save_capture(catalog_capture(identity='deleted', text='已删除独有正文'))
            app.delete_session('deleted', 'catalog-fixture')
            before = hashlib.sha256(app.database.read_bytes()).hexdigest()
            build(root / 'package')
            env = {**os.environ, 'LOCAL_JOURNAL_DATA_DIR': str(root / 'data')}
            process = subprocess.Popen([sys.executable, '-u', str(root / 'package/plugins/local-journal/server/main.py')],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, encoding='utf-8', env=env)
            def request(method, params=None):
                process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}) + '\n')
                process.stdin.flush()
                return json.loads(process.stdout.readline())['result']
            def call(name, **arguments):
                result = request('tools/call', {'name': name, 'arguments': arguments})
                self.assertFalse(result['isError'], result)
                return json.loads(result['content'][0]['text'])
            try:
                server_info = request('initialize', {'protocolVersion': '2025-11-25'})['serverInfo']
                self.assertEqual(server_info['name'], 'local-journal')
                self.assertEqual(server_info['version'], '0.1.1')
                self.assertEqual(len(request('tools/list')['tools']), 6)
                self.assertEqual(call('archive_status')['liveCollectorState'], 'unknown')
                projects = call('list_projects')['projects']
                self.assertEqual(len(projects), 1)
                self.assertEqual(call('list_sessions', project=projects[0]['id'])['sessions'][0]['id'], 'catalog-1')
                self.assertEqual(call('list_turns', session='catalog-1', source='catalog-fixture')['turns'][0]['id'], 'turn')
                hits = call('search_dialogue', query='独立事实')['results']
                self.assertEqual(len(hits), 1)
                self.assertIn('/turn/turn?', hits[0]['url'])
                self.assertEqual(call('search_dialogue', query='已删除独有正文')['results'], [])
                args = {'session': 'catalog-1', 'source': 'catalog-fixture', 'turn': 'turn', 'limit': 1, 'saved': session['savedAt']}
                first = call('read_turn', **args)['messages'][0]
                second = call('read_turn', **args, text_offset=first['nextTextOffset'])['messages'][0]
                self.assertEqual(first['text'] + second['text'], text)
                self.assertIsNone(second['nextTextOffset'])
                invalid = request('tools/call', {'name': 'list_projects', 'arguments': {'limit': 101}})
                self.assertTrue(invalid['isError'])
                missing = request('tools/call', {'name': 'read_turn', 'arguments': {'session': 'deleted', 'source': 'catalog-fixture', 'turn': 'turn'}})
                self.assertTrue(missing['isError'])
            finally:
                process.stdin.close()
                process.wait(timeout=10)
                errors = process.stderr.read()
                process.stdout.close()
                process.stderr.close()
            self.assertEqual(process.returncode, 0, errors)
            self.assertEqual(before, hashlib.sha256(app.database.read_bytes()).hexdigest())

    def test_readonly_missing_database_does_not_create_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / 'missing'
            with self.assertRaises(FileNotFoundError):
                Journal(missing, read_only=True)
            self.assertFalse(missing.exists())

    def test_readonly_connections_reject_writes(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as temp:
            app = Journal(temp)
            readonly = Journal(temp, read_only=True)
            with self.assertRaises(sqlite3.OperationalError):
                readonly.set_capacity(1024 * 1024)
            self.assertIsNone(app.capacity()['limitBytes'])
