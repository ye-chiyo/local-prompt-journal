"""Durable exclusions and retryable removal of application-managed records."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from .attachments import managed_path
from .source import now


def excluded(db: sqlite3.Connection, instance: str, thread: str) -> bool:
    return db.execute('SELECT 1 FROM deletions WHERE instance=? AND thread=?', (instance, thread)).fetchone() is not None


def filter_state(db: sqlite3.Connection, state: dict[str, Any]) -> dict[str, Any]:
    identities = set(db.execute('SELECT instance, thread FROM deletions').fetchall())
    result = dict(state)
    result['relationMetadata'] = [entry for entry in state.get('relationMetadata', [])
        if (entry['sourceInstance'], entry['thread']['id']) not in identities]
    result['sessions'] = [entry for entry in state.get('sessions', [])
        if (entry.get('source'), entry['id']) not in identities]
    return result


class ManagedDeletion:
    def __init__(self, database: Path, data_dir: Path):
        self.database, self.data_dir = database, data_dir
        with closing(self.connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS deletions (instance TEXT NOT NULL, thread TEXT NOT NULL, deleted_at TEXT NOT NULL, pending TEXT NOT NULL, error TEXT, PRIMARY KEY(instance, thread))')
        self.retry()

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database, timeout=10)

    def entries(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as db:
            rows = db.execute('SELECT instance,thread,deleted_at,pending,error FROM deletions ORDER BY deleted_at,instance,thread').fetchall()
        return [{'sourceInstance': row[0], 'id': row[1], 'deletedAt': row[2],
                 'status': 'cleanupPending' if json.loads(row[3]) else 'deleted', 'error': row[4]} for row in rows]

    def identity(self, thread: str, instance: str | None, db: sqlite3.Connection) -> str:
        rows = db.execute('SELECT instance FROM snapshots WHERE thread=? UNION SELECT instance FROM deletions WHERE thread=?', (thread, thread)).fetchall()
        identities = {row[0] for row in rows if instance is None or row[0] == instance}
        if not identities:
            raise KeyError('本机没有此归档会话或删除排除。')
        if len(identities) != 1:
            raise ValueError('多个来源具有相同会话 ID；请指定来源实例。')
        return identities.pop()

    def delete(self, thread: str, instance: str | None) -> dict[str, Any]:
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            instance = self.identity(thread, instance, db)
            prior = db.execute('SELECT pending FROM deletions WHERE instance=? AND thread=?', (instance, thread)).fetchone()
            digests = set(json.loads(prior[0])) if prior else set()
            for (serialized,) in db.execute('SELECT package FROM snapshots WHERE instance=? AND thread=?', (instance, thread)):
                digests.update(a['sha256'] for a in json.loads(serialized)['session'].get('attachments', []) if a.get('status') == 'saved')
            db.execute('INSERT INTO deletions(instance,thread,deleted_at,pending,error) VALUES (?,?,?,?,NULL) ON CONFLICT(instance,thread) DO UPDATE SET pending=excluded.pending,error=NULL',
                       (instance, thread, now(), json.dumps(sorted(digests))))
            db.execute('DELETE FROM snapshots WHERE instance=? AND thread=?', (instance, thread))
            state = db.execute("SELECT value FROM collection_state WHERE key='collector'").fetchone()
            if state:
                db.execute("UPDATE collection_state SET value=? WHERE key='collector'", (json.dumps(filter_state(db, json.loads(state[0])), ensure_ascii=False),))
        self.retry(thread, instance)
        return next(entry for entry in self.entries() if entry['id'] == thread and entry['sourceInstance'] == instance)

    def retry(self, thread: str | None = None, instance: str | None = None) -> None:
        # The same SQLite writer lock serializes attachment acquisition, snapshot
        # persistence and cleanup across collectors, HTTP threads and processes.
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("SELECT instance,thread,pending FROM deletions WHERE pending != '[]'").fetchall()
            if not rows:
                return
            retained: set[str] = set()
            for (serialized,) in db.execute('SELECT package FROM snapshots'):
                retained.update(a['sha256'] for a in json.loads(serialized)['session'].get('attachments', []) if a.get('status') == 'saved')
            for source, identity, serialized in rows:
                if thread is not None and (thread != identity or instance != source):
                    continue
                pending = []
                errors = []
                for digest in json.loads(serialized):
                    if digest in retained:
                        continue
                    try:
                        managed_path(self.data_dir, digest).unlink(missing_ok=True)
                    except (OSError, ValueError) as exc:
                        pending.append(digest)
                        errors.append(str(exc))
                db.execute('UPDATE deletions SET pending=?,error=? WHERE instance=? AND thread=?',
                           (json.dumps(pending), '; '.join(errors) or None, source, identity))

    def restore(self, thread: str, instance: str | None) -> dict[str, Any]:
        with closing(self.connect()) as db:
            instance = self.identity(thread, instance, db)
        self.retry(thread, instance)
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT pending FROM deletions WHERE instance=? AND thread=?', (instance, thread)).fetchone()
            if row is None:
                raise KeyError('此会话没有删除排除。')
            if json.loads(row[0]):
                raise ValueError('附件清理尚未完成；请修复数据目录权限后重试删除，不能提前解除排除。')
            db.execute('DELETE FROM deletions WHERE instance=? AND thread=?', (instance, thread))
        return {'id': thread, 'sourceInstance': instance, 'status': 'restored',
                'note': '仅解除删除排除；后续自动采集仍遵守原启用时间，不恢复已删除历史副本。'}
