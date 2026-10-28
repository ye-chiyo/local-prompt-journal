"""Versioned turn projections: directories read metadata, readers load one body."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .catalog import project_identity
from .storage import decode_package, encode_package
from .attachments import archive_attachments
from .search import item_anchor


GROUPS = ('messages', 'tools', 'unsupportedItems', 'attachments')


def readable_count(body: dict[str, Any]) -> int:
    return sum(len(body.get(group, [])) for group in ('messages', 'tools', 'unsupportedItems'))


def save(db: sqlite3.Connection, number: int, package: dict[str, Any]) -> None:
    session = package['session']
    if 'attachments' not in session:
        # acquire=False only derives original references; it never reads files.
        archive_attachments(package, Path('.'), acquire=False)
    metadata = {k: v for k, v in session.items() if k not in (*GROUPS, 'turns', 'executions', 'relations')}
    metadata['thread'] = {k: v for k, v in session['thread'].items() if k in ('id', 'cwd', 'createdAt', 'projectId')}
    metadata['_turnProjectionVersion'] = 2
    metadata.setdefault('project', project_identity(session['thread'], session['source']['instance']))
    db.execute('INSERT INTO turn_snapshots(number,metadata) VALUES (?,?)', (number, json.dumps(metadata, ensure_ascii=False)))
    for index, turn in enumerate(session['turns']):
        body = {'turns': [turn], **{group: [entry for entry in session.get(group, []) if entry['turnId'] == turn['id']] for group in GROUPS}}
        serialized = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        digest = hashlib.sha256(serialized).hexdigest()
        db.execute('INSERT OR IGNORE INTO turn_payloads(digest,body) VALUES (?,?)', (digest, encode_package(body)))
        started = turn.get('startedAt')
        db.execute('INSERT INTO turn_entries(number,turn,ordinal,started,status,payload,content_count) VALUES (?,?,?,?,?,?,?)',
                   (number, turn['id'], index + 1, started if isinstance(started, (int, float)) else None, turn.get('status'), digest, readable_count(body)))
        for group, kind in (('messages', 'message'), ('tools', 'tool')):
            for entry in body[group]:
                anchor = item_anchor(session['source']['instance'], session['id'], turn['id'], entry['id'], kind)
                db.execute('INSERT INTO turn_items(number,anchor,turn) VALUES (?,?,?)', (number, anchor, turn['id']))


def initialize(db: sqlite3.Connection) -> None:
    db.execute('CREATE TABLE IF NOT EXISTS turn_snapshots(number INTEGER PRIMARY KEY,metadata TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS turn_payloads(digest TEXT PRIMARY KEY,body BLOB NOT NULL)')
    db.execute('''CREATE TABLE IF NOT EXISTS turn_entries(number INTEGER NOT NULL,turn TEXT NOT NULL,
        ordinal INTEGER NOT NULL,started REAL,status TEXT,payload TEXT NOT NULL,content_count INTEGER,PRIMARY KEY(number,turn))''')
    if 'content_count' not in {row[1] for row in db.execute('PRAGMA table_info(turn_entries)')}:
        db.execute('ALTER TABLE turn_entries ADD COLUMN content_count INTEGER')
    # Inspect each distinct payload only once during upgrade. Directories continue
    # to query metadata only, and full saved versions retain their source evidence.
    pending = db.execute('SELECT digest,body FROM turn_payloads WHERE digest IN (SELECT payload FROM turn_entries WHERE content_count IS NULL)').fetchall()
    for digest, value in pending:
        db.execute('UPDATE turn_entries SET content_count=? WHERE payload=?', (readable_count(decode_package(value)), digest))
    db.execute('CREATE INDEX IF NOT EXISTS turn_order ON turn_entries(number,ordinal)')
    db.execute('CREATE INDEX IF NOT EXISTS turn_payload_refs ON turn_entries(payload)')
    db.execute('CREATE TABLE IF NOT EXISTS turn_items(number INTEGER NOT NULL,anchor TEXT NOT NULL,turn TEXT NOT NULL,PRIMARY KEY(number,anchor))')
    missing = [row[0] for row in db.execute("SELECT s.number FROM snapshots s LEFT JOIN turn_snapshots t ON s.number=t.number WHERE t.number IS NULL OR json_extract(t.metadata,'$._turnProjectionVersion') IS NOT 2 ORDER BY s.number")]
    if missing:
        print(f'建立回合索引：0/{len(missing)} 个保存版本', file=sys.stderr, flush=True)
    for index, number in enumerate(missing, 1):
        value = db.execute('SELECT package FROM snapshots WHERE number=?', (number,)).fetchone()[0]
        db.execute('DELETE FROM turn_entries WHERE number=?', (number,))
        db.execute('DELETE FROM turn_snapshots WHERE number=?', (number,))
        db.execute('DELETE FROM turn_items WHERE number=?', (number,))
        save(db, number, decode_package(value))
        if index % 100 == 0 or index == len(missing):
            print(f'建立回合索引：{index}/{len(missing)} 个保存版本', file=sys.stderr, flush=True)
    if missing:
        db.execute('DELETE FROM turn_payloads WHERE digest NOT IN (SELECT payload FROM turn_entries)')


def directory(db: sqlite3.Connection, project: str, offset: int = 0, limit: int = 30,
              thread: str | None = None, instance: str | None = None) -> dict[str, Any]:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError('目录页起点须非负，每页数量须为 1—100。')
    db.execute('BEGIN')
    row = db.execute('SELECT summary FROM session_catalog WHERE project_id=? LIMIT 1', (project,)).fetchone()
    if row is None:
        raise KeyError('项目尚未保存')
    where, values = 'c.project_id=? AND t.content_count>0', [project]
    if thread is not None:
        where += ' AND c.thread=? AND c.instance=?'
        values.extend([thread, instance or ''])
    join = ' FROM session_catalog c JOIN turn_entries t ON c.number=t.number WHERE ' + where
    total = db.execute('SELECT COUNT(*)' + join, values).fetchone()[0]
    rows = db.execute('SELECT c.summary,t.turn,t.ordinal,t.started,t.status' + join +
                      ' ORDER BY c.created IS NULL,c.created,c.instance,c.thread,t.ordinal LIMIT ? OFFSET ?', [*values, limit, offset])
    return {'project': json.loads(row[0])['project'], 'turns': [
        {'session': json.loads(r[0]), 'id': r[1], 'ordinal': r[2], 'startedAt': r[3], 'status': r[4]} for r in rows],
        'total': total, 'offset': offset, 'limit': limit,
        'nextOffset': offset + limit if offset + limit < total else None}


def read(db: sqlite3.Connection, thread: str, turn: str, instance: str | None,
         saved: str | None) -> dict[str, Any]:
    db.execute('BEGIN')
    number, metadata = selected(db, thread, instance, saved)
    row = db.execute('SELECT t.ordinal,p.body FROM turn_entries t JOIN turn_payloads p ON p.digest=t.payload WHERE t.number=? AND t.turn=? AND t.content_count>0', (number, turn)).fetchone()
    if row is None:
        raise KeyError('本机未保存这个回合。')
    neighbors = db.execute('SELECT turn,ordinal FROM turn_entries WHERE number=? AND content_count>0 AND ordinal=(SELECT MAX(ordinal) FROM turn_entries WHERE number=? AND content_count>0 AND ordinal<?) UNION ALL SELECT turn,ordinal FROM turn_entries WHERE number=? AND content_count>0 AND ordinal=(SELECT MIN(ordinal) FROM turn_entries WHERE number=? AND content_count>0 AND ordinal>?)', (number, number, row[0], number, number, row[0])).fetchall()
    return {'session': {**metadata, **decode_package(row[1])}, 'ordinal': row[0],
            'previous': next((r[0] for r in neighbors if r[1] < row[0]), None),
            'next': next((r[0] for r in neighbors if r[1] > row[0]), None)}


def selected(db: sqlite3.Connection, thread: str, instance: str | None,
             saved: str | None) -> tuple[int, dict[str, Any]]:
    if instance is None:
        identities = db.execute('SELECT DISTINCT instance FROM snapshots WHERE thread=?', (thread,)).fetchall()
        if len(identities) > 1:
            raise ValueError('多个来源具有相同会话 ID；请指定来源实例。')
        instance = identities[0][0] if identities else None
    clause = ' AND s.saved=?' if saved is not None else ''
    values = [thread, instance] + ([saved] if saved is not None else [])
    version = db.execute('SELECT s.number,m.metadata FROM snapshots s JOIN turn_snapshots m ON s.number=m.number WHERE s.thread=? AND s.instance=?' + clause + ' ORDER BY s.number DESC LIMIT 1', values).fetchone()
    if version is None:
        raise KeyError('本机未保存这个会话版本。')
    return version[0], json.loads(version[1])


def session_directory(db: sqlite3.Connection, thread: str, instance: str | None, saved: str | None,
                      offset: int, limit: int, target: str | None = None) -> dict[str, Any]:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError('目录页起点须非负，每页数量须为 1—100。')
    db.execute('BEGIN')
    number, metadata = selected(db, thread, instance, saved)
    if target:
        row = db.execute('SELECT turn FROM turn_items WHERE number=? AND anchor=?', (number, target)).fetchone()
        if row is None:
            raise KeyError('此保存版本未包含命中条目。')
        return {'target': row[0], 'session': metadata}
    total = db.execute('SELECT COUNT(*) FROM turn_entries WHERE number=? AND content_count>0', (number,)).fetchone()[0]
    rows = db.execute('SELECT turn,ordinal,started,status FROM turn_entries WHERE number=? AND content_count>0 ORDER BY ordinal LIMIT ? OFFSET ?', (number, limit, offset))
    return {'project': metadata['project'], 'turns': [
        {'session': metadata, 'id': row[0], 'ordinal': row[1], 'startedAt': row[2], 'status': row[3]} for row in rows],
        'total': total, 'offset': offset, 'limit': limit, 'nextOffset': offset + limit if offset + limit < total else None}


def delete(db: sqlite3.Connection, thread: str, instance: str) -> None:
    db.execute('DELETE FROM turn_items WHERE number IN (SELECT number FROM snapshots WHERE thread=? AND instance=?)', (thread, instance))
    db.execute('DELETE FROM turn_entries WHERE number IN (SELECT number FROM snapshots WHERE thread=? AND instance=?)', (thread, instance))
    db.execute('DELETE FROM turn_snapshots WHERE number IN (SELECT number FROM snapshots WHERE thread=? AND instance=?)', (thread, instance))
    db.execute('DELETE FROM turn_payloads WHERE digest NOT IN (SELECT payload FROM turn_entries)')


def searchable(db: sqlite3.Connection, project: str | None, thread: str | None,
               instance: str | None) -> list[dict[str, Any]]:
    where, values = [], []
    for column, value in (('project_id', project), ('thread', thread), ('instance', instance)):
        if value is not None:
            where.append('c.' + column + '=?')
            values.append(value)
    clause = ' WHERE ' + ' AND '.join(where) if where else ''
    rows = db.execute('SELECT c.summary,p.body FROM session_catalog c JOIN turn_entries t ON c.number=t.number JOIN turn_payloads p ON p.digest=t.payload' + clause +
                      ' ORDER BY c.created IS NULL,c.created,c.instance,c.thread,t.ordinal', values)
    return [{**json.loads(row[0]), **decode_package(row[1])} for row in rows]
