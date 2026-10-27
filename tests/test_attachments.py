import json
import io
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from urllib.request import urlopen

from prompt_journal import Journal, CodexHistory
from prompt_journal.sync import Collector
from prompt_journal.web import create_server
from tests.fixtures.attachment_facts import PNG, DOCUMENT, OTHER, facts


class AttachmentAcceptance(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'sample.png').write_bytes(PNG)
        (self.root / 'sample.bin').write_bytes(DOCUMENT)
        (self.root / 'other').mkdir()
        (self.root / 'other' / 'sample.bin').write_bytes(OTHER)
        self.state = facts(self.root)
        self.state_path = self.root / 'source.json'
        self.publish()
        self.app = Journal(self.root / 'data')

    def publish(self):
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')

    def source(self):
        return CodexHistory([sys.executable, str(Path(__file__).parent / 'fixtures' / 'automatic_source.py'), str(self.state_path)])

    def test_automatic_copies_survive_original_move_and_restart_with_honest_missing_states(self):
        collector = Collector(self.app, source_factory=self.source, interval=0.1, enabled_at=190, page_size=1)
        collector.start()
        self.addCleanup(collector.stop)
        deadline = time.monotonic() + 8
        while len(self.app.sessions()) < 4 and time.monotonic() < deadline:
            time.sleep(0.04)
        collector.stop()
        session = self.app.session('main')
        attachments = session['attachments']
        self.assertEqual([(a['itemId'], a['status']) for a in attachments], [
            ('picture', 'saved'), ('shared', 'saved'), ('documents', 'saved'),
            ('documents', 'saved'), ('missing', 'missing'), ('missing', 'missing')])
        self.assertEqual(self.app.attachment('main', attachments[0]['id'])[1], PNG)
        self.assertEqual(self.app.attachment('main', attachments[2]['id'])[1], DOCUMENT)
        self.assertEqual(self.app.attachment('main', attachments[3]['id'])[1], OTHER)
        self.assertIn('远端', attachments[-1]['reason'])
        self.assertIn('不存在', attachments[-2]['reason'])
        self.assertEqual(self.app.session('empty')['attachments'], [])
        (self.root / 'sample.png').rename(self.root / 'moved.png')
        (self.root / 'sample.bin').rename(self.root / 'moved.bin')
        with self.source() as source:
            self.app.import_session('main', source)
        restarted = Journal(self.root / 'data')
        self.assertEqual(restarted.attachment('main', attachments[0]['id'])[1], PNG)
        server = create_server(restarted, 0)
        self.addCleanup(server.server_close)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'
        html = urlopen(base + '/session/main/turn/turn').read().decode('utf-8')
        self.assertIn('已归档附件', html)
        self.assertIn('远端', html)
        self.assertEqual(urlopen(base + attachments[0]['url']).read(), PNG)
        evidence = json.loads(restarted.export_session('main'))
        self.assertTrue(evidence['evidence'])
        self.assertEqual(evidence['session']['messages'][-1]['text'], '已保留对话和工具证据。')
        shared = next(a for a in evidence['session']['attachments'] if a['itemId'] == 'shared')
        node = evidence
        for part in shared['evidenceRef'].removeprefix('#/').split('/'):
            node = node[int(part)] if isinstance(node, list) else node[part]
        self.assertEqual(node, str(self.root / 'sample.png'))

    def test_portable_bundle_preserves_bytes_revisions_and_only_selected_one_hop(self):
        with self.source() as source:
            for identity in ('main', 'child', 'grandchild', 'empty'):
                self.app.import_session(identity, source)
        # Same source reference changes bytes: old saved version must stay original.
        (self.root / 'sample.bin').write_bytes(b'New revision bytes.\n')
        with self.source() as source:
            self.app.import_session('main', source)
        (self.root / 'sample.png').rename(self.root / 'moved.png')
        (self.root / 'sample.bin').rename(self.root / 'moved.bin')
        single = self.app.export_bundle('main')
        related = self.app.export_bundle('main', include_related=True)
        for data, expected in ((single, ['main']), (related, ['main', 'child'])):
            relocated = self.root / ('relocated-' + str(len(expected)))
            relocated.mkdir()
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                archive.extractall(relocated)
            package = json.loads((relocated / 'session.json').read_text(encoding='utf-8'))
            manifest = json.loads((relocated / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(package['exportScope']['included'], expected)
            self.assertEqual(manifest['bundleVersion'], 1)
            main = package['session']['attachments']
            self.assertEqual((relocated / main[0]['bundlePath']).read_bytes(), PNG)
            self.assertEqual((relocated / main[2]['bundlePath']).read_bytes(), b'New revision bytes.\n')
            self.assertEqual((relocated / main[3]['bundlePath']).read_bytes(), OTHER)
            old = package['revisions'][0]['session']['attachments']
            self.assertEqual((relocated / old[2]['bundlePath']).read_bytes(), DOCUMENT)
            self.assertEqual({m['itemId'] for m in manifest['missing']}, {'missing'})
            self.assertEqual({a['sessionId'] for a in manifest['attachments']}, set(expected))
            if len(expected) == 2:
                child = package['related'][0]['session']['attachments'][0]
                self.assertEqual((relocated / child['bundlePath']).read_bytes(), PNG)
                self.assertIn('grandchild', [o['targetId'] for o in package['exportScope']['omitted']])
            # Follow actual exported pointers to independently declared source facts.
            expected_references = [str(self.root / 'sample.png'), str(self.root / 'sample.png'),
                (self.root / 'sample.bin').as_uri(), (self.root / 'other' / 'sample.bin').as_uri(),
                str(self.root / 'absent.png'), 'https://example.invalid/remote.png']
            self.assertEqual([a['itemId'] for a in main], ['picture', 'shared', 'documents', 'documents', 'missing', 'missing'])
            for attachment, expected_reference in zip(main, expected_references, strict=True):
                node = package
                for part in attachment['evidenceRef'].removeprefix('#/').split('/'):
                    node = node[int(part)] if isinstance(node, list) else node[part]
                self.assertEqual(node, expected_reference)
                self.assertEqual(attachment['reference'], expected_reference)
                self.assertEqual((attachment['sessionId'], attachment['turnId']), ('main', 'turn'))
        empty = self.app.export_bundle('empty')
        with zipfile.ZipFile(io.BytesIO(empty)) as archive:
            self.assertEqual(json.loads(archive.read('manifest.json'))['attachments'], [])
