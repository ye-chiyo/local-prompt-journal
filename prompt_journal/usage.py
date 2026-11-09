"""Read-only runtime metadata projection, independent of dialogue snapshots.

No raw JSONL record is persisted. Checkpoints contain only parser state and
cumulative counters, never prompts, answers, instructions or tool payloads.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

from .catalog import project_identity

RETENTION_SECONDS = 90 * 86400
SHANGHAI = timezone(timedelta(hours=8), 'Asia/Shanghai')
COUNTERS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
            'output_tokens', 'reasoning_output_tokens', 'total_tokens')


class CapacityFull(RuntimeError):
    pass


def check_capacity(db: sqlite3.Connection) -> None:
    row = db.execute("SELECT value FROM collection_state WHERE key='capacity_limit_bytes'").fetchone()
    if row:
        used = (db.execute('PRAGMA page_count').fetchone()[0] - db.execute('PRAGMA freelist_count').fetchone()[0]) * db.execute('PRAGMA page_size').fetchone()[0]
        if used >= int(row[0]):
            raise CapacityFull('数据库容量已满，统计采集已暂停。')


def timestamp(value: Any) -> float | None:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result = float(value)
        elif isinstance(value, str):
            result = datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        else:
            return None
        return result if 0 < result < 32503680000 else None
    except (ValueError, OverflowError, OSError):
        return None


def initialize(db: sqlite3.Connection) -> None:
    db.executescript('''
        CREATE TABLE IF NOT EXISTS usage_sources (
            instance TEXT NOT NULL, thread TEXT NOT NULL, project TEXT NOT NULL,
            kind TEXT NOT NULL, parent TEXT, PRIMARY KEY(instance,thread));
        CREATE TABLE IF NOT EXISTS usage_turns (
            instance TEXT NOT NULL, thread TEXT NOT NULL, turn TEXT NOT NULL,
            started REAL NOT NULL, ended REAL, status TEXT NOT NULL,
            PRIMARY KEY(instance,thread,turn));
        CREATE INDEX IF NOT EXISTS usage_turn_time ON usage_turns(started);
        CREATE TABLE IF NOT EXISTS usage_events (
            instance TEXT NOT NULL, thread TEXT NOT NULL, event TEXT NOT NULL,
            turn TEXT NOT NULL, occurred REAL NOT NULL, model TEXT NOT NULL,
            input INTEGER NOT NULL, cached INTEGER NOT NULL, cache_write INTEGER NOT NULL,
            output INTEGER NOT NULL, reasoning INTEGER NOT NULL, total INTEGER NOT NULL,
            PRIMARY KEY(instance,thread,event));
        CREATE INDEX IF NOT EXISTS usage_event_time ON usage_events(occurred);
        CREATE TABLE IF NOT EXISTS usage_gaps (
            instance TEXT NOT NULL, thread TEXT NOT NULL, event TEXT NOT NULL,
            occurred REAL NOT NULL, PRIMARY KEY(instance,thread,event));
        CREATE TABLE IF NOT EXISTS usage_checkpoints (
            instance TEXT NOT NULL, path TEXT NOT NULL, inode TEXT NOT NULL,
            offset INTEGER NOT NULL, state TEXT NOT NULL, touched REAL NOT NULL,
            PRIMARY KEY(instance,path));
        CREATE TABLE IF NOT EXISTS usage_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')


def prepare_backup(db: sqlite3.Connection, data_dir: Path) -> None:
    """A one-time consistent backup before adding statistics to an existing archive."""
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'usage_settings' not in tables and 'snapshots' in tables and db.execute('SELECT 1 FROM snapshots LIMIT 1').fetchone():
        destination = data_dir / 'backups' / ('before-usage-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(destination)) as backup:
            db.backup(backup)


def set_setting(db: sqlite3.Connection, key: str, value: Any) -> None:
    db.execute('INSERT OR REPLACE INTO usage_settings VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))


def settings(db: sqlite3.Connection) -> dict[str, Any]:
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='usage_settings'").fetchone():
        return {}
    return {k: json.loads(v) for k, v in db.execute('SELECT key,value FROM usage_settings')}


def expire(db: sqlite3.Connection, current: float) -> None:
    cutoff = current - RETENTION_SECONDS
    db.execute('DELETE FROM usage_events WHERE occurred < ?', (cutoff,))
    db.execute('DELETE FROM usage_turns WHERE started < ?', (cutoff,))
    db.execute('DELETE FROM usage_gaps WHERE occurred < ?', (cutoff,))
    db.execute('DELETE FROM usage_checkpoints WHERE touched < ?', (cutoff,))
    # Identity-only source metadata must survive an empty first backfill; it
    # contains no timestamped usage facts and is also needed for attribution.


def counters(value: Any) -> list[int] | None:
    if not isinstance(value, dict):
        return None
    result = [value.get(k, 0) for k in COUNTERS]
    if not all(type(n) is int and 0 <= n <= 2**53 for n in result):
        return None
    if not all(k in value for k in ('input_tokens', 'output_tokens', 'total_tokens')):
        return None
    if result[1] > result[0] or result[4] > result[3] or result[0] + result[3] != result[5]:
        return None
    return result


class UsageReader:
    def __init__(self, database: Path, instance: str, home: Path):
        self.database, self.instance, self.home = database, instance, home

    def scan(self, current: float | None = None, stopping: threading.Event | None = None) -> dict[str, Any]:
        current = time.time() if current is None else current
        cutoff = current - RETENTION_SECONDS
        roots = [self.home / 'sessions', self.home / 'archived_sessions']
        if not any(p.is_dir() for p in roots):
            raise OSError('未找到本机 Codex 运行记录，请确认 Codex 已创建会话。')
        paths = [p for root in roots if root.is_dir() for p in root.rglob('*.jsonl')
                 if not p.is_symlink() and p.resolve().is_relative_to(root.resolve())]
        result: dict[str, Any] = {'files': 0, 'processed': 0, 'unmatchedFiles': 0, 'failedFiles': 0, 'capacityPaused': False}
        for path in paths:
            if stopping and stopping.is_set():
                return {**result, 'interrupted': True}
            try:
                stat = path.stat()
                if stat.st_mtime < cutoff:
                    continue
                result['files'] += 1
                matched, processed = self.read_file(path, current, stopping)
                result['processed'] += processed
                result['unmatchedFiles'] += int(not matched)
            except CapacityFull:
                result['capacityPaused'] = True
                break
            except (OSError, ValueError, sqlite3.Error):
                result['failedFiles'] += 1
        with closing(sqlite3.connect(self.database, timeout=10)) as db, db:
            expire(db, current)
            prior = settings(db).get('status', {})
            state = ('paused' if result.get('capacityPaused') else 'partial' if result['failedFiles']
                     else 'empty' if not result['files'] or result['unmatchedFiles'] == result['files'] else 'ready')
            set_setting(db, 'status', {**prior, **result, 'state': state,
                        'lastCheckedAt': current, 'lastSuccessAt': current if state == 'ready' else prior.get('lastSuccessAt'),
                        'error': '数据库容量已满，统计采集已暂停。' if state == 'paused' else '部分统计文件读取失败，将自动重试。' if result['failedFiles'] else None})
        return result

    def read_file(self, path: Path, current: float, stopping: threading.Event | None = None) -> tuple[bool, int]:
        cutoff = current - RETENTION_SECONDS
        stat = path.stat()
        inode = str(stat.st_ino)
        # Commit batches, so a long backfill does not lock archive writes.
        with closing(sqlite3.connect(self.database, timeout=10)) as db, path.open('rb') as stream:
            row = db.execute('SELECT inode,offset,state FROM usage_checkpoints WHERE instance=? AND path=?',
                             (self.instance, str(path))).fetchone()
            state: dict[str, Any] = {}
            if row and row[0] == inode and row[1] <= stat.st_size:
                stream.seek(row[1])
                state = json.loads(row[2])
            processed = 0
            check_capacity(db)
            with db:
                # Same-inode rewrites can grow past the old offset. Verify a
                # hash of the checkpoint boundary without retaining raw bytes.
                if state.get('tail') and stream.tell():
                    offset = stream.tell()
                    stream.seek(max(0, offset-128))
                    actual = hashlib.sha256(stream.read(offset-stream.tell())).hexdigest()
                    if actual != state['tail']:
                        stream.seek(0)
                        state = {}
                    else:
                        stream.seek(offset)
                while not (stopping and stopping.is_set()):
                    start = stream.tell()
                    line = stream.readline()
                    if not line:
                        break
                    if not line.endswith(b'\n'):
                        stream.seek(start)  # An append in progress is retried next cycle.
                        break
                    try:
                        record = json.loads(line)
                    except (ValueError, UnicodeError):
                        raise ValueError('统计文件有无效记录。') from None
                    if not isinstance(record, dict):
                        raise ValueError('统计记录格式未知。')
                    payload = record.get('payload')
                    if not isinstance(payload, dict):
                        continue
                    if record.get('type') == 'session_meta':
                        session = payload.get('id')
                        if not isinstance(session, str) or not 0 < len(session) <= 200:
                            raise ValueError('统计会话身份无效。')
                        match = db.execute('SELECT 1 FROM usage_sources WHERE instance=? AND thread=?', (self.instance, session)).fetchone()
                        if not match:
                            # Closed child agents can disappear from thread/list.
                            # An explicit runtime parent identity still proves
                            # their membership; no body/path heuristic is used.
                            parent = payload.get('parent_thread_id')
                            source = payload.get('source')
                            parent_row = db.execute('SELECT project FROM usage_sources WHERE instance=? AND thread=?',
                                                    (self.instance, parent if isinstance(parent, str) else None)).fetchone()
                            if parent_row and isinstance(source, dict) and 'subagent' in source:
                                parent_project = json.loads(parent_row[0])
                                cwd = payload.get('cwd')
                                project = parent_project
                                if isinstance(cwd, str) and cwd != parent_project.get('cwd'):
                                    project = project_identity({'cwd': cwd}, self.instance)
                                db.execute('INSERT OR IGNORE INTO usage_sources VALUES (?,?,?,?,?)',
                                           (self.instance, session, json.dumps(project, ensure_ascii=False), 'child', parent))
                                match = True
                        if not match:
                            # No guessing attribution from paths or dialogue content.
                            return False, processed
                        if state.get('session') != session:
                            state = {'session': session, 'created': timestamp(payload.get('timestamp')) or timestamp(record.get('timestamp')),
                                     'turn': None, 'model': None, 'baseline': None}
                    elif state.get('session'):
                        self.project_record(db, record, payload, state, cutoff, current)
                    processed += 1
                    if processed % 500 == 0:
                        self.checkpoint(db, path, inode, stream.tell(), state, current)
                        db.commit()
                        check_capacity(db)
                if state.get('session'):
                    self.checkpoint(db, path, inode, stream.tell(), state, current)
                return bool(state.get('session')), processed

    def checkpoint(self, db: sqlite3.Connection, path: Path, inode: str, offset: int, state: dict[str, Any], current: float) -> None:
        with path.open('rb') as stream:
            stream.seek(max(0, offset-128))
            state['tail'] = hashlib.sha256(stream.read(offset-stream.tell())).hexdigest()
        db.execute('INSERT OR REPLACE INTO usage_checkpoints VALUES (?,?,?,?,?,?)',
                   (self.instance, str(path), inode, offset, json.dumps(state), current))

    def project_record(self, db: sqlite3.Connection, record: dict[str, Any], payload: dict[str, Any],
                       state: dict[str, Any], cutoff: float, current: float) -> None:
        occurred = timestamp(record.get('timestamp'))
        if occurred is None or occurred > current + 300:
            return
        session, kind = state['session'], payload.get('type')
        created = state.get('created')
        inherited = created is not None and occurred < created
        if record.get('type') == 'turn_context':
            turn = payload.get('turn_id')
            if not inherited and isinstance(turn, str) and turn == state.get('turn'):
                model = payload.get('model')
                state['model'] = model if isinstance(model, str) and 0 < len(model) <= 200 else None
            return
        if record.get('type') != 'event_msg':
            return
        if kind == 'task_started':
            started, turn = timestamp(payload.get('started_at')) or occurred, payload.get('turn_id')
            if inherited or (created is not None and started < created - 1) or not isinstance(turn, str):
                state['turn'], state['model'] = None, None
                return
            if state.get('turn') != turn:
                state['model'] = None
            state['turn'] = turn
            if started >= cutoff:
                db.execute('''INSERT INTO usage_turns VALUES (?,?,?,?,NULL,'running')
                    ON CONFLICT(instance,thread,turn) DO NOTHING''', (self.instance, session, turn, started))
        elif kind in ('task_complete', 'turn_aborted', 'task_failed'):
            turn = payload.get('turn_id') or state.get('turn')
            ended = timestamp(payload.get('completed_at')) or occurred
            status = {'task_complete': 'completed', 'turn_aborted': 'interrupted', 'task_failed': 'failed'}[kind]
            if not inherited:
                db.execute('UPDATE usage_turns SET status=?,ended=? WHERE instance=? AND thread=? AND turn=?',
                           (status, ended, self.instance, session, turn))
            if turn == state.get('turn'):
                state['turn'], state['model'] = None, None
        elif kind == 'token_count':
            info = payload.get('info')
            if not isinstance(info, dict):
                return
            cumulative, last = counters(info.get('total_token_usage')), counters(info.get('last_token_usage'))
            baseline = state.get('baseline')
            state['baseline'] = cumulative
            if cumulative is None:
                self.gap(db, state, occurred, cutoff)
                return
            if cumulative == baseline:
                return
            delta = [a - b for a, b in zip(cumulative, baseline)] if baseline else None
            # First / reset counters must establish a known local increment. A
            # fork's inherited cumulative total is never charged to the child.
            if delta is None or any(n < 0 for n in delta):
                delta = last if cumulative == last else None
            if delta is None or last != delta:
                self.gap(db, state, occurred, cutoff)
                return
            if inherited or not state.get('turn') or occurred < cutoff:
                if not inherited and occurred >= cutoff and delta[-1]:
                    self.gap(db, state, occurred, cutoff)
                return
            if delta[-1] == 0:
                return
            model = state.get('model') or '模型未知'
            # Stable under restart, file relocation, rewrite and duplicate lines.
            identity = hashlib.sha256(json.dumps([state['turn'], occurred, model, cumulative], ensure_ascii=False).encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO usage_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (self.instance, session, identity, state['turn'], occurred, model, *delta))

    def gap(self, db: sqlite3.Connection, state: dict[str, Any], occurred: float, cutoff: float) -> None:
        if occurred >= cutoff:
            identity = hashlib.sha256(json.dumps([occurred, state.get('turn'), state.get('baseline')]).encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO usage_gaps VALUES (?,?,?,?)', (self.instance, state['session'], identity, occurred))


class UsageMonitor:
    """Separate worker: source/API or statistics failures cannot stop archiving."""
    def __init__(self, database: Path, interval: float = 10):
        self.database, self.interval = database, interval
        self.stopping = threading.Event()
        self.wake = threading.Event()
        self.thread: threading.Thread | None = None

    def configure(self, instance: str, home: Any, metadata: list[dict[str, Any]]) -> None:
        if not isinstance(home, str) or not Path(home).is_absolute():
            return
        if hashlib.sha256(str(Path(home).resolve()).encode('utf-8')).hexdigest() != instance:
            raise ValueError('统计来源身份不一致。')
        with closing(sqlite3.connect(self.database, timeout=10)) as db, db:
            for thread in metadata:
                source = thread.get('source')
                child = isinstance(source, dict) and any('sub' in str(k).lower() for k in source)
                child = child or isinstance(source, str) and source.lower().startswith('subagent')
                parent = thread.get('parentThreadId')
                db.execute('''INSERT INTO usage_sources VALUES (?,?,?,?,?) ON CONFLICT(instance,thread)
                    DO UPDATE SET project=excluded.project,kind=excluded.kind,parent=excluded.parent''',
                    (instance, thread['id'], json.dumps(project_identity(thread, instance), ensure_ascii=False),
                     'child' if child or parent else 'main', parent))
            set_setting(db, 'source', {'instance': instance, 'home': home})
        self.wake.set()

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, name='journal-usage', daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stopping.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=30)

    def run(self) -> None:
        while not self.stopping.is_set():
            try:
                with closing(sqlite3.connect(self.database, timeout=10)) as db, db:
                    config = settings(db).get('source')
                    expire(db, time.time())
                    if config:
                        previous = settings(db).get('status', {})
                        set_setting(db, 'status', {**previous, 'state': 'updating'})
                if config:
                    UsageReader(self.database, config['instance'], Path(config['home'])).scan(stopping=self.stopping)
            except Exception:
                try:
                    with closing(sqlite3.connect(self.database, timeout=10)) as db, db:
                        prior = settings(db).get('status', {})
                        set_setting(db, 'status', {**prior, 'state': 'error', 'error': '统计来源暂不可用，将自动重试。'})
                except sqlite3.Error:
                    pass
            self.wake.wait(self.interval)
            self.wake.clear()


def aggregate(database: Path, days: int = 90, project: str | None = None, kind: str = 'main',
              current: float | None = None) -> dict[str, Any]:
    if days not in (1, 7, 30, 90) or kind not in ('main', 'child', 'all'):
        raise ValueError('统计范围无效。')
    current = time.time() if current is None else current
    today = datetime.fromtimestamp(current, SHANGHAI).date()
    start_day = today - timedelta(days=days - 1)
    cutoff = max(current - RETENTION_SECONDS, datetime.combine(start_day, datetime.min.time(), SHANGHAI).timestamp())
    with closing(sqlite3.connect(database, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        config = settings(db)
        status = config.get('status', {'state': 'waiting', 'error': '等待统计来源连接。'})
        sources = {(r['instance'], r['thread']): dict(r) for r in db.execute('SELECT * FROM usage_sources')}
        turns = [dict(r) for r in db.execute('SELECT * FROM usage_turns WHERE started>=? AND started<=?', (cutoff, current))]
        events = [dict(r) for r in db.execute('SELECT * FROM usage_events WHERE occurred>=? AND occurred<=?', (cutoff, current))]
        gap_rows = [dict(r) for r in db.execute('SELECT * FROM usage_gaps WHERE occurred>=? AND occurred<=?', (cutoff, current))]
        identities = {(r[0], r[1]) for r in db.execute('''SELECT instance,thread FROM usage_turns WHERE started>=?
            UNION SELECT instance,thread FROM usage_events WHERE occurred>=?''', (current-RETENTION_SECONDS, current-RETENTION_SECONDS))}
    projects = {json.loads(s['project'])['id']: json.loads(s['project']) for identity, s in sources.items() if identity in identities}
    def selected(row: dict[str, Any]) -> bool:
        source = sources.get((row['instance'], row['thread']))
        return bool(source and (kind == 'all' or source['kind'] == kind) and
                    (not project or json.loads(source['project'])['id'] == project))
    turns, events = list(filter(selected, turns)), list(filter(selected, events))
    gaps = len(list(filter(selected, gap_rows)))
    def bucket() -> dict[str, Any]:
        return {'rounds': 0, 'total': 0, 'input': 0, 'output': 0, 'cached': 0, 'cacheWrite': 0, 'reasoning': 0, 'missingTokens': 0}
    summary = {**bucket(), 'running': 0, 'interrupted': 0, 'failed': 0, 'missingTokens': 0}
    daily = {str(start_day + timedelta(days=i)): bucket() for i in range(days)}
    hours = [bucket() for _ in range(24)]
    models: dict[str, dict[str, Any]] = {}
    project_rows: dict[str, dict[str, Any]] = {}
    event_turns = {(r['instance'], r['thread'], r['turn']) for r in events}
    model_turns: dict[str, set[tuple[str, str, str]]] = {}
    def project_bucket(row: dict[str, Any]) -> dict[str, Any]:
        p = json.loads(sources[(row['instance'], row['thread'])]['project'])
        return project_rows.setdefault(p['id'], {**p, **bucket()})
    for row in turns:
        moment = datetime.fromtimestamp(row['started'], SHANGHAI)
        if row['status'] == 'completed':
            summary['rounds'] += 1
            daily[str(moment.date())]['rounds'] += 1
            hours[moment.hour]['rounds'] += 1
            project_bucket(row)['rounds'] += 1
            missing = int((row['instance'], row['thread'], row['turn']) not in event_turns)
            summary['missingTokens'] += missing
            daily[str(moment.date())]['missingTokens'] += missing
            hours[moment.hour]['missingTokens'] += missing
            project_bucket(row)['missingTokens'] += missing
        elif row['status'] in summary:
            summary[row['status']] += 1
    keys = {'total': 'total', 'input': 'input', 'output': 'output', 'cached': 'cached', 'cacheWrite': 'cache_write', 'reasoning': 'reasoning'}
    for row in events:
        moment = datetime.fromtimestamp(row['occurred'], SHANGHAI)
        model = models.setdefault(row['model'], {'name': row['model'], **bucket()})
        model_turns.setdefault(row['model'], set()).add((row['instance'], row['thread'], row['turn']))
        for target in (summary, daily[str(moment.date())], hours[moment.hour], model, project_bucket(row)):
            for key, column in keys.items():
                target[key] += row[column]
    for name, model in models.items():
        model['rounds'] = len(model_turns[name])
    summary['active'] = sum(int(v['rounds'] > 0 or v['total'] > 0) for v in daily.values())
    return {'days': days, 'retentionDays': 90, 'timezone': 'Asia/Shanghai', 'status': status,
            'summary': summary, 'gaps': gaps,
            'daily': [{'date': k, **v} for k, v in daily.items()], 'hours': hours,
            'models': sorted(models.values(), key=lambda v: (-v['total'], v['name'])),
            'projects': sorted(project_rows.values(), key=lambda v: -v['total']),
            'projectChoices': sorted(projects.values(), key=lambda v: (v['label'], v['id']))}
