"""Prepare a reusable non-sensitive demo and verify public cross-feature paths.

No Codex real history is read. Expected identities, bytes, text and order are
defined in release_facts.py before application import.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import zipfile

from release_facts import DOCUMENT, image_bytes, initial, session
from release_paths import external_output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        root = external_output(args.output, args.repo)
    except ValueError as exc:
        parser.error(str(exc))
    args.repo = str(Path(args.repo).resolve())
    sys.path.insert(0, args.repo)
    from prompt_journal import Journal, CodexHistory
    from prompt_journal.sync import Collector
    root.mkdir(parents=True, exist_ok=False)
    (root / 'sample.png').write_bytes(image_bytes())
    (root / 'sample.bin').write_bytes(DOCUMENT)
    state = initial(root)
    state_path = root / 'source.json'
    (root / 'independent-expectations.json').write_text(json.dumps({
        'definedBeforeImport': True, 'initialSessions': ['A', 'B', 'C'], 'projectOneOrder': ['A', 'B'],
        'projectTwoOrder': ['C', 'D'], 'chineseQuery': '雨巷纸伞', 'expectedHit': ['A', 'user-1'],
        'originalDocumentHex': DOCUMENT.hex(), 'pngHex': image_bytes().hex(),
        'toolCompletedOutput': '中文工具错误：路径不存在', 'toolExitCode': 1,
        'offlineMessage': '中断后自动补回原文', 'oneHopRelated': ['C']}, ensure_ascii=False, indent=2), encoding='utf-8')
    def publish():
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        temporary.replace(state_path)
    publish()
    app = Journal(root / 'data')
    def source():
        return CodexHistory([sys.executable, str(Path(args.repo) / 'tests/fixtures/automatic_source.py'), str(state_path)])
    def start():
        collector = Collector(app, source_factory=source, interval=0.1, enabled_at=190, page_size=1)
        collector.start()
        return collector
    def await_(predicate):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        raise AssertionError('Public view did not reach pre-defined expectation')
    collector = start()
    try:
        await_(lambda: len(app.sessions()) == 3)
        assert [[s['id'] for s in p['sessions']] for p in app.projects()] == [['A', 'B'], ['C']]
        assert app.session('A')['tools'][0]['status'] == 'inProgress'
        command = state['sessions'][0]['turns'][0]['items'][1]
        command.update(status='completed', aggregatedOutput='中文工具错误：路径不存在', exitCode=1)
        state['sessions'].append(session('D', 'D:/演示乙', 180, '新会话被自动发现'))
        publish()
        await_(lambda: len(app.sessions()) == 4 and app.session('A')['tools'][0]['status'] == 'failed')
        assert [[s['id'] for s in p['sessions']] for p in app.projects()] == [['A', 'B'], ['C', 'D']]
        hits = app.search('雨巷纸伞')
        assert hits['total'] == 1
        assert app.search('中文工具错误')['total'] == 1
        state['unavailable'] = True
        publish()
        await_(lambda: collector.status().get('sourceAvailable') is False)
        assert app.search('雨巷纸伞')['total'] == 1
    finally:
        collector.stop()
    state['unavailable'] = False
    state['sessions'][0]['turns'].append({'id': 'turn-2', 'startedAt': 210, 'status': 'completed', 'items': [
        {'id': 'recovered', 'type': 'agentMessage', 'phase': 'final_answer', 'text': '中断后自动补回原文'}]})
    publish()
    collector = start()
    try:
        await_(lambda: app.session('A')['messages'][-1]['id'] == 'recovered')
    finally:
        collector.stop()
    app = Journal(root / 'data')
    assert app.session('A')['messages'][-1]['text'] == '中断后自动补回原文'
    assert app.collection_state()['enabledAt'] == 190
    # Delete the shared-image owner through the public API. Other owners and
    # their independent raw evidence remain unchanged throughout the cycle.
    before_a = json.loads(app.export_session('A'))
    before_b = json.loads(app.export_session('B'))
    shared = next(a for a in app.session('A')['attachments'] if a['itemId'] == 'user-1')
    assert app.delete_session('C')['status'] == 'deleted'
    assert app.search('另一项目中文原文：项目隔离')['total'] == 0
    try:
        app.export_session('C')
        raise AssertionError('Deleted session remained available')
    except KeyError:
        pass
    assert json.loads(app.export_session('A'))['evidence'] == before_a['evidence']
    assert json.loads(app.export_session('B'))['evidence'] == before_b['evidence']
    assert app.attachment('A', shared['id'])[1] == image_bytes()
    collector = start()
    try:
        checked = collector.status().get('lastCheckedAt')
        await_(lambda: collector.status().get('lastCheckedAt') != checked)
        assert [s['id'] for s in app.sessions()] == ['A', 'B', 'D']
    finally:
        collector.stop()
    app = Journal(root / 'data')
    assert [e['id'] for e in app.exclusions()] == ['C']
    collector = start()
    try:
        checked = collector.status().get('lastCheckedAt')
        await_(lambda: collector.status().get('lastCheckedAt') != checked)
        assert [s['id'] for s in app.sessions()] == ['A', 'B', 'D']
    finally:
        collector.stop()
    assert app.restore_session('C')['status'] == 'restored'
    assert app.collection_state()['enabledAt'] == 190
    collector = start()
    try:
        await_(lambda: len(app.sessions()) == 4)
    finally:
        collector.stop()
    assert app.exclusions() == []
    assert app.search('另一项目中文原文：项目隔离')['total'] == 1
    assert app.collection_state()['enabledAt'] == 190
    assert app.attachment('A', shared['id'])[1] == image_bytes()
    exported = json.loads(app.export_session('A', include_related=True))
    assert [p['session']['id'] for p in exported['related']] == ['C']
    assert any(p['session']['tools'][0]['status'] == 'inProgress' for p in exported['revisions'])
    evidence_count = 0
    for package in [exported] + exported['revisions'] + exported['related']:
        for evidence in package['evidence']:
            assert hashlib.sha256(evidence['raw'].encode('utf-8')).hexdigest() == evidence['sha256']
            assert json.loads(evidence['raw']) == evidence['response']
            evidence_count += 1
    (root / 'sample.png').rename(root / 'moved-original.png')
    (root / 'sample.bin').rename(root / 'moved-original.bin')
    png = next(a for a in app.session('A')['attachments'] if a['itemId'] == 'user-1')
    assert app.attachment('A', png['id'])[1] == image_bytes()
    bundle = app.export_bundle('A', include_related=True)
    (root / 'related-bundle.zip').write_bytes(bundle)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        archive.extractall(root / 'moved-offline-bundle')
        manifest = json.loads(archive.read('manifest.json'))
        session_json = json.loads(archive.read('session.json'))
        assert session_json['session']['id'] == 'A'
        assert [p['session']['id'] for p in session_json['related']] == ['C']
        attachment_files = [archive.read(n) for n in archive.namelist() if n.startswith('attachments/') and not n.endswith('/')]
        assert image_bytes() in attachment_files and DOCUMENT in attachment_files
    (root / 'public-export.json').write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {'passed': True, 'userAccepted': False, 'realCodexContract': 'not run; controlled protocol only',
              'sessions': 4, 'projects': 2, 'order': [['A', 'B'], ['C', 'D']], 'evidenceChecks': evidence_count,
              'sourceUnavailablePreservesSearch': True, 'restartRecovered': True, 'enabledAt': 190,
              'originalFilesMoved': True, 'bundleHasIndependentBytes': True,
              'deletionRestore': {'passed': True, 'target': 'C', 'sharedAttachmentPreserved': True,
                                  'otherSessionEvidenceUnchanged': True, 'excludedAfterCollectorRestart': True,
                                  'restoredAutomatically': True, 'enabledAtUnchanged': True},
              'dataDir': str(root / 'data'), 'sourceState': str(state_path)}
    (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
