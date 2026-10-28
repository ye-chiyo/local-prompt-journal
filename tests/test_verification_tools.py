"""Exercise acceptance CLIs against independent source facts, including failures."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prompt_journal import CodexHistory, Journal
from tests.fixtures.catalog_facts import catalog_capture


class VerificationToolsAcceptance(unittest.TestCase):
    def run_tool(self, root, data, script, expected, label, code=0):
        manifest = root / (label + '-expected.json')
        report = root / (label + '-report.json')
        manifest.write_text(json.dumps(expected, ensure_ascii=False), encoding='utf-8')
        result = subprocess.run([sys.executable, '-X', 'utf8', 'tools/' + script,
            '--expected', str(manifest), '--data-dir', str(data), '--report', str(report),
            '--export', str(root / (label + '-export.json'))], capture_output=True, text=True,
            encoding='utf-8', timeout=40)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(report.read_text(encoding='utf-8'))

    def test_message_cli_reads_turns_and_checks_raw_or_original_message_excerpts(self):
        expected = {'thread': {'id': 'sample-session'}, 'turns': [{'id': 'turn-1', 'messages': [
            {'type': 'userMessage', 'id': 'user-1', 'content': [{'type': 'text', 'text': '请记录原文。'}]},
            {'type': 'agentMessage', 'id': 'ai-1', 'text': '正在核对中文。', 'phase': 'commentary'},
            {'type': 'agentMessage', 'id': 'ai-2', 'text': '原文已保留。', 'phase': 'final_answer'},
        ]}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / 'data'
            with CodexHistory([sys.executable, 'tests/fixtures/codex_server.py']) as source:
                Journal(data).import_session('sample-session', source)
            raw = self.run_tool(root, data, 'verify_saved_session.py', expected, 'raw')
            self.assertTrue(raw['passed'])
            self.assertTrue(raw['allMessageEvidenceLinksVisibleAndReadable'])
            Journal(data).prune_tools(root / 'before-prune.sqlite3')
            excerpt = self.run_tool(root, data, 'verify_saved_session.py', expected, 'excerpt')
            self.assertTrue(excerpt['passed'])
            self.assertGreater(excerpt['sourceExcerptCount'], 0)
            self.assertIsNone(excerpt['allRawHashesMatch'])
            expected['turns'][0]['messages'][2]['text'] = '独立清单与保存文本不符'
            mismatch = self.run_tool(root, data, 'verify_saved_session.py', expected, 'mismatch', 1)
            self.assertFalse(mismatch['allEvidenceReferencesResolve'])
            self.assertFalse(mismatch['passed'])

    def test_tool_cli_checks_turn_body_and_reports_removed_tools_without_crashing(self):
        capture = catalog_capture()
        evidence = capture['evidence'][0]
        evidence['raw'] = json.dumps(evidence['response'], ensure_ascii=False)
        evidence['sha256'] = hashlib.sha256(evidence['raw'].encode('utf-8')).hexdigest()
        entry = {**capture['items'][1][0], 'startedAtMs': None, 'completedAtMs': None}
        expected = {'definedBeforeImplementation': True, 'threadId': 'catalog-1', 'tools': [entry]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / 'data'
            app = Journal(data)
            app.save_capture(capture)
            report = self.run_tool(root, data, 'verify_tool_evidence.py', expected, 'tools')
            self.assertTrue(report['selfVerified'])
            app.prune_tools(root / 'before-prune.sqlite3')
            removed = self.run_tool(root, data, 'verify_tool_evidence.py', expected, 'removed', 1)
            self.assertEqual(removed['retention'], 'dialogue-only-v1')
            self.assertFalse(removed['sameCallIdentitiesAndTurns'])
            self.assertFalse(removed['selfVerified'])
