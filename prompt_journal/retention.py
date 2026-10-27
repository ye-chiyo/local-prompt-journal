"""Explicit, backed-up removal of execution records from every saved version."""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterator

from . import catalog, turns
from .attachments import archive_attachments
from .storage import decode_package, encode_package
from .topology import pointer


POLICY = 'dialogue-only-v1'
NOTE = '仅保留用户与 AI 消息及消息附件；工具、不支持条目和完整协议响应已按用户要求移除。来源证据为原始消息对象摘录。'


def enabled(db: sqlite3.Connection) -> bool:
    return db.execute("SELECT value FROM collection_state WHERE key='retention'").fetchone() == (POLICY,)


def dialogue_package(package: dict[str, Any]) -> dict[str, Any]:
    """Keep source message objects verbatim, explicitly extracting from responses."""
    original = package['session']
    if original['source'].get('retention') == POLICY:
        return package
    if 'attachments' not in original:
        archive_attachments(package, Path('.'), acquire=False)
    session = {k: v for k, v in original.items() if k not in
               ('tools', 'unsupportedItems', 'executions', 'executionGaps', 'relations', 'relationGaps', 'attachmentSummary')}
    evidence: list[dict[str, Any]] = [
        {'method': source['method'], 'params': source['params'],
         'response': {'result': {'retainedItems': []}},
         'representation': 'sourceMessageExcerpt', 'note': NOTE,
         'sourceResponseSha256': source.get('sha256')}
        for source in package['evidence']]
    messages: list[dict[str, Any]] = []
    locations: dict[tuple[str, str], tuple[str, str]] = {}
    for entry in original['messages']:
        old_ref = entry['evidenceRef']
        item = pointer(package, old_ref)
        if item.get('type') not in ('userMessage', 'agentMessage') or item.get('id') != entry['id']:
            raise ValueError('消息来源身份不匹配；未清理数据库。')
        index = int(old_ref.split('/')[2])
        retained = evidence[index]['response']['result']['retainedItems']
        new_ref = f'#/evidence/{index}/response/result/retainedItems/{len(retained)}'
        # Drop raw and the surrounding response: both can repeat tool payloads.
        # Keep each source page's evidence index: old page URLs must never be
        # reassigned to an unrelated response after removing execution entries.
        retained.append({'originalEvidenceRef': old_ref, 'item': item})
        new_ref += '/item'
        messages.append({**entry, 'evidenceRef': new_ref})
        locations[(entry['turnId'], entry['id'])] = (old_ref, new_ref)
    attachments = []
    for attachment in original['attachments']:
        location = locations.get((attachment['turnId'], attachment['itemId']))
        if location is None:
            continue
        old_ref, new_ref = location
        if not attachment['evidenceRef'].startswith(old_ref + '/'):
            raise ValueError('附件来源位置不匹配；未清理数据库。')
        attachments.append({**attachment, 'evidenceRef': new_ref + attachment['evidenceRef'][len(old_ref):]})
    session.update(messages=messages, tools=[], unsupportedItems=[], attachments=attachments,
                   sourceItemCount=len(messages))
    session['turns'] = [{k: v for k, v in turn.items() if k != 'items'} for turn in original['turns']]
    session['thread'] = {k: v for k, v in original['thread'].items() if k not in ('turns', 'items', 'preview')}
    session['source'] = {**original['source'], 'retention': POLICY, 'retentionNote': NOTE,
                         'notDisplayedTypes': [], 'itemsView': 'dialogueOnly',
                         'gaps': [NOTE, '首次采集范围与来源缺失限制仍适用；消息中的工具名称、代码及过程说明按原文保留。']}
    return {'schemaVersion': package['schemaVersion'], 'session': session, 'evidence': evidence}


def dialogue_facts(package: dict[str, Any]) -> dict[str, Any]:
    """Identities, text, source message objects and message attachment facts."""
    session = package['session']
    if 'attachments' not in session:
        archive_attachments(package, Path('.'), acquire=False)
    identities = {(m['turnId'], m['id']) for m in session['messages']}
    facts = {k: session.get(k) for k in ('id', 'name', 'savedAt', 'createdAt', 'project', 'turns')}
    facts['messages'] = [{k: v for k, v in m.items() if k != 'evidenceRef'} for m in session['messages']]
    facts['sourceItems'] = [pointer(package, m['evidenceRef']) for m in session['messages']]
    facts['attachments'] = [{k: v for k, v in a.items() if k not in ('evidenceRef', 'url')}
                            for a in session['attachments'] if (a['turnId'], a['itemId']) in identities]
    facts['attachmentReferences'] = [pointer(package, a['evidenceRef'])
                                     for a in session['attachments'] if (a['turnId'], a['itemId']) in identities]
    return facts


def dialogue_digest(package: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(dialogue_facts(package), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def unchanged(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    def comparable(package: dict[str, Any]) -> dict[str, Any]:
        facts = dialogue_facts(package)
        facts.pop('savedAt')
        # Source absolute positions can shift when tools are added between the
        # same messages. List order still records the dialogue's relative order.
        facts['messages'] = [{k: v for k, v in m.items() if k != 'order'} for m in facts['messages']]
        facts['turns'] = [{k: v for k, v in t.items() if k not in ('durationMs', 'itemsView')} for t in facts['turns']]
        facts['thread'] = {k: v for k, v in package['session']['thread'].items() if k not in ('updatedAt', 'status')}
        facts['source'] = {k: v for k, v in package['session']['source'].items() if k != 'pagination'}
        return facts
    return comparable(previous) == comparable(current)


@contextmanager
def offline(data_dir: Path) -> Iterator[None]:
    """Use the collector's OS lock so a running collector cannot repopulate data."""
    with (data_dir / 'collector.lock').open('a+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('请先停止此数据目录的自动采集服务，再执行工具清理。') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == 'win32':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def prune_tools(database: Path, backup: Path) -> dict[str, Any]:
    if backup.resolve() == database.resolve() or backup.exists():
        raise ValueError('备份须使用新的独立文件，不能覆盖数据库或既有备份。')
    with offline(database.parent), closing(sqlite3.connect(database, timeout=10)) as db:
        before = database.stat().st_size
        removed_tools, removed_unsupported, count = 0, 0, 0
        expected: dict[int, str] = {}
        with db:
            db.execute('BEGIN IMMEDIATE')
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open('xb'):
                pass
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(backup)) as target:
                source.backup(target, pages=2048)
                if target.execute('PRAGMA quick_check').fetchone() != ('ok',):
                    raise ValueError('备份校验失败；未开始清理。')
            numbers = [row[0] for row in db.execute('SELECT number FROM snapshots ORDER BY number')]
            db.execute('DELETE FROM turn_items')
            db.execute('DELETE FROM turn_entries')
            db.execute('DELETE FROM turn_snapshots')
            db.execute('DELETE FROM turn_payloads')
            db.execute('DELETE FROM session_catalog')
            for number in numbers:
                package = decode_package(db.execute('SELECT package FROM snapshots WHERE number=?', (number,)).fetchone()[0])
                expected[number] = dialogue_digest(package)
                removed_tools += len(package['session'].get('tools', []))
                removed_unsupported += len(package['session'].get('unsupportedItems', []))
                reduced = dialogue_package(package)
                if dialogue_digest(reduced) != expected[number]:
                    raise ValueError('消息或附件校验失败；清理已回滚。')
                db.execute('UPDATE snapshots SET package=? WHERE number=?', (encode_package(reduced), number))
                catalog.save_summary(db, reduced['session'], number)
                turns.save(db, number, reduced)
                count += 1
                if count % 100 == 0 or count == len(numbers):
                    print(f'清理工具记录：{count}/{len(numbers)} 个保存版本', file=sys.stderr, flush=True)
            for number, value in db.execute('SELECT number,package FROM snapshots'):
                if dialogue_digest(decode_package(value)) != expected[number]:
                    raise ValueError('持久化消息校验失败；清理已回滚。')
            db.execute("INSERT OR REPLACE INTO collection_state(key,value) VALUES ('retention',?)", (POLICY,))
        db.execute('VACUUM')
        if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('清理后数据库检查失败，请使用独立备份恢复。')
        digest = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
        return {'verified': True, 'policy': POLICY, 'snapshots': count, 'deletedSnapshots': 0,
                'removedToolEntriesAcrossVersions': removed_tools, 'removedUnsupportedEntriesAcrossVersions': removed_unsupported,
                'dialogueDigest': digest, 'bytesBefore': before, 'bytesAfter': database.stat().st_size,
                'backup': str(backup), 'attachmentFilesRetainedForRecovery': True}
