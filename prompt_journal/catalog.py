"""Rebuildable metadata catalog; reading a directory never loads a snapshot."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from typing import Any
from .storage import decode_package


ORDER = "created IS NULL, created, instance, thread"


def project_identity(thread: dict[str, Any], instance: str) -> dict[str, Any]:
    project_id, cwd = thread.get("projectId"), thread.get("cwd")
    identity = [instance, "project", project_id] if project_id else [instance, "cwd", cwd] if cwd else [instance, "unknown"]
    return {"id": hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest(),
            "label": str(cwd or project_id or "项目未知"), "sourceInstance": instance,
            "sourceProjectId": project_id, "cwd": cwd, "basis": "projectId" if project_id else "cwd" if cwd else "unknown"}


def session_order(session: dict[str, Any]) -> tuple[Any, ...]:
    created = session.get("createdAt")
    known = isinstance(created, (int, float))
    return (not known, created if known else 0, session["source"]["instance"], session["id"])


def save_summary(db: sqlite3.Connection, session: dict[str, Any], number: int) -> None:
    source = session["source"]
    project = session.get("project") or project_identity(session["thread"], source["instance"])
    created = session.get("createdAt", session["thread"].get("createdAt"))
    created = created if isinstance(created, (int, float)) else None
    # Source contains protocol metadata only, never turns, messages or tool payloads.
    summary = {**{k: session[k] for k in ("id", "name", "savedAt", "source")},
               "createdAt": created, "project": project}
    db.execute("""INSERT INTO session_catalog(instance,thread,project_id,name,created,saved,number,summary)
        VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(instance,thread) DO UPDATE SET
        project_id=excluded.project_id,name=excluded.name,created=excluded.created,
        saved=excluded.saved,number=excluded.number,summary=excluded.summary""",
        (source["instance"], session["id"], project["id"], session["name"], created,
         session["savedAt"], number, json.dumps(summary, ensure_ascii=False)))


def initialize(db: sqlite3.Connection) -> None:
    db.execute("CREATE INDEX IF NOT EXISTS snapshots_identity ON snapshots(instance,thread,number)")
    db.execute("CREATE INDEX IF NOT EXISTS snapshots_version ON snapshots(thread,instance,saved,number)")
    db.execute("""CREATE TABLE IF NOT EXISTS session_catalog (
        instance TEXT NOT NULL, thread TEXT NOT NULL, project_id TEXT NOT NULL,
        name TEXT, created REAL, saved TEXT NOT NULL, number INTEGER NOT NULL,
        summary TEXT NOT NULL, PRIMARY KEY(instance,thread))""")
    db.execute("CREATE INDEX IF NOT EXISTS catalog_project_order ON session_catalog(project_id,created IS NULL,created,instance,thread)")
    # Inspect only snapshot identities on ordinary startup. Backfill incomplete
    # projections within the writer transaction, before the server is exposed.
    missing = db.execute("""SELECT s.number FROM snapshots s LEFT JOIN session_catalog c
        ON s.instance=c.instance AND s.thread=c.thread
        WHERE s.number IN (SELECT MAX(number) FROM snapshots GROUP BY instance,thread)
        AND (c.number IS NULL OR c.number!=s.number)""").fetchall()
    if missing:
        print(f'建立会话目录：0/{len(missing)}', file=sys.stderr, flush=True)
    for index, (number,) in enumerate(missing, 1):
        row = db.execute("SELECT package FROM snapshots WHERE number=?", (number,)).fetchone()
        save_summary(db, decode_package(row[0])["session"], number)
        if index % 20 == 0 or index == len(missing):
            print(f'建立会话目录：{index}/{len(missing)}', file=sys.stderr, flush=True)


def summaries(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return [json.loads(row[0]) for row in db.execute("SELECT summary FROM session_catalog ORDER BY " + ORDER)]


def projects(db: sqlite3.Connection) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for session in summaries(db):
        project = session["project"]
        result.setdefault(project["id"], {**project, "sessions": []})["sessions"].append(session)
    return sorted(result.values(), key=lambda p: (p["label"], p["id"]))


def project_choices(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute("SELECT summary,COUNT(*) FROM session_catalog GROUP BY project_id")
    result = [{**json.loads(row[0])["project"], "sessionCount": row[1]} for row in rows]
    return sorted(result, key=lambda p: (p["label"], p["id"]))


def session_summary(db: sqlite3.Connection, thread: str, instance: str) -> dict[str, Any]:
    row = db.execute("SELECT summary FROM session_catalog WHERE thread=? AND instance=?", (thread, instance)).fetchone()
    if row is None:
        raise KeyError("本机尚未保存这个会话。")
    return json.loads(row[0])


def directory(db: sqlite3.Connection, project_id: str | None = None, offset: int = 0,
              limit: int = 30, query: str = "") -> dict[str, Any]:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("目录页起点须非负，每页数量须为 1—100。")
    db.execute("BEGIN")
    where, values = [], []
    project = None
    if project_id is not None:
        row = db.execute("SELECT summary FROM session_catalog WHERE project_id=? LIMIT 1", (project_id,)).fetchone()
        if row is None:
            raise KeyError("项目尚未保存")
        project = json.loads(row[0])["project"]
        where.append("project_id=?")
        values.append(project_id)
    if query:
        where.append("(instr(COALESCE(name,''),?)>0 OR instr(thread,?)>0)")
        values.extend([query, query])
    clause = " WHERE " + " AND ".join(where) if where else ""
    total = db.execute("SELECT COUNT(*) FROM session_catalog" + clause, values).fetchone()[0]
    rows = db.execute("SELECT summary FROM session_catalog" + clause + " ORDER BY " + ORDER + " LIMIT ? OFFSET ?",
                      [*values, limit, offset])
    return {"project": project, "sessions": [json.loads(row[0]) for row in rows],
            "total": total, "offset": offset, "limit": limit,
            "nextOffset": offset + limit if offset + limit < total else None}
