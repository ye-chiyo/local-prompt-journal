"""Versioned, lossless snapshot encoding and explicit backed-up compaction."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any
import zlib


MAGIC = b"PJZ1"


def snapshot_bytes(value: str | bytes) -> bytes:
    if isinstance(value, str):
        return value.encode('utf-8')
    return zlib.decompress(value[len(MAGIC):]) if value.startswith(MAGIC) else value


def decode_package(value: str | bytes) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(snapshot_bytes(value))
    return result


def encode_package(package: dict[str, Any]) -> bytes:
    return MAGIC + zlib.compress(json.dumps(package, ensure_ascii=False).encode('utf-8'))


def compact(database: Path, backup: Path) -> dict[str, Any]:
    """Run with the service stopped. No snapshot, raw line or version is dropped."""
    if backup.resolve() == database.resolve() or backup.exists():
        raise ValueError('备份须使用新的独立文件，不能覆盖数据库或既有备份。')
    backup.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects existing files even if another process creates
    # the selected path after the existence check.
    with backup.open('xb'):
        pass
    before = database.stat().st_size
    count, logical_before, logical_after = 0, 0, 0
    expected = hashlib.sha256()
    with closing(sqlite3.connect(database, timeout=10)) as db:
        with db:
            db.execute('BEGIN IMMEDIATE')
            # The reserved writer lock keeps this consistent backup and the
            # following rewrite on the same generation while allowing reads.
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(backup)) as target:
                source.backup(target, pages=2048)
                if target.execute('PRAGMA quick_check').fetchone() != ('ok',):
                    raise ValueError('备份校验失败；未开始压缩。')
            numbers = [row[0] for row in db.execute('SELECT number FROM snapshots ORDER BY number')]
            for number in numbers:
                value = db.execute('SELECT package FROM snapshots WHERE number=?', (number,)).fetchone()[0]
                raw = snapshot_bytes(value)
                expected.update(str(number).encode() + b'\0' + hashlib.sha256(raw).digest())
                encoded = MAGIC + zlib.compress(raw)
                logical_before += len(value.encode('utf-8') if isinstance(value, str) else value)
                logical_after += len(encoded)
                if value != encoded:
                    db.execute('UPDATE snapshots SET package=? WHERE number=?', (encoded, number))
                count += 1
                if count % 100 == 0:
                    print(f'无损压缩：{count}/{len(numbers)} 个快照', file=sys.stderr, flush=True)
            actual = hashlib.sha256()
            for number, value in db.execute('SELECT number,package FROM snapshots ORDER BY number'):
                actual.update(str(number).encode() + b'\0' + hashlib.sha256(snapshot_bytes(value)).digest())
            if actual.digest() != expected.digest():
                raise ValueError('逐快照校验失败；本次压缩已回滚，备份保留。')
        db.execute('VACUUM')
        if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('压缩后数据库检查失败，请使用独立备份恢复。')
    return {'verified': True, 'snapshots': count, 'bytesBefore': before, 'bytesAfter': database.stat().st_size,
            'payloadBytesBefore': logical_before, 'payloadBytesAfter': logical_after,
            'snapshotDigest': expected.hexdigest(), 'backup': str(backup), 'deletedSnapshots': 0}
