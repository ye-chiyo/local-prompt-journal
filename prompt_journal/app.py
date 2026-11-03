from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import quote

from .source import CodexHistory, HistoryError, now
from .tool_evidence import TOOL_TYPES, tool_record, require_command_exit
from .topology import EXECUTION_GAPS, RELATION_GAPS, executions, relocate, relation_records
from .search import search_sessions
from .attachments import archive_attachments, attachment_view, read_copy
from .deletion import ManagedDeletion, excluded, filter_state
from . import catalog
from . import turns as turn_store
from .catalog import project_identity, session_order
from .storage import decode_package, encode_package, compact
from . import retention


def default_data_dir() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    ordinary = local / "LocalPromptJournal" / "data"
    candidates = [ordinary]
    if os.name == "nt":
        candidates.append(local / "Packages" / "OpenAI.Codex_2p2nqsd0c76g0" /
                          "LocalCache" / "Local" / "LocalPromptJournal" / "data")
    existing = {path.resolve() for path in candidates if (path / "journal.sqlite3").is_file()}
    if len(existing) > 1:
        raise ValueError("发现多个不同的默认数据库，请使用 --data-dir 明确指定现有数据目录。")
    return next(iter(existing)) if existing else ordinary.resolve()


def external_path(path: Path | str) -> Path:
    destination = Path(path).resolve()
    if destination.is_relative_to(Path(__file__).resolve().parent.parent):
        raise ValueError("运行时日志与导出必须位于项目源码以外。")
    return destination


class CapacityReached(HistoryError):
    pass


class Journal:
    def __init__(self, data_dir: Path | str | None = None, *, read_only: bool = False):
        self.read_only = read_only
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        self.data_dir = external_path(self.data_dir)
        self.database = self.data_dir / "journal.sqlite3"
        if read_only:
            if not self.database.is_file():
                raise FileNotFoundError("本机归档数据库不存在；请先使用本机会话记录应用完成初始化。")
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("CREATE TABLE IF NOT EXISTS snapshots (number INTEGER PRIMARY KEY, instance TEXT NOT NULL, thread TEXT NOT NULL, saved TEXT NOT NULL, package TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS collection_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            catalog.initialize(db)
            turn_store.initialize(db)
        self._deletion = ManagedDeletion(self.database, self.data_dir)

    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            return sqlite3.connect(self.database.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
        return sqlite3.connect(self.database, timeout=10)

    def capacity(self, db: sqlite3.Connection | None = None) -> dict[str, Any]:
        if db is None:
            with closing(self._connect()) as connection:
                return self.capacity(connection)
        page_size = db.execute('PRAGMA page_size').fetchone()[0]
        page_count = db.execute('PRAGMA page_count').fetchone()[0]
        free_pages = db.execute('PRAGMA freelist_count').fetchone()[0]
        row = db.execute("SELECT value FROM collection_state WHERE key='capacity_limit_bytes'").fetchone()
        limit = int(row[0]) if row else None
        used = (page_count - free_pages) * page_size
        return {'usedBytes': used, 'limitBytes': limit, 'paused': bool(limit and used >= limit)}

    def set_capacity(self, limit: int | None) -> None:
        if limit is not None and not 1024 * 1024 <= limit <= 1024 ** 4:
            raise ValueError('容量须在 1 MiB 至 1 TiB 之间。')
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if limit is None:
                db.execute("DELETE FROM collection_state WHERE key='capacity_limit_bytes'")
            else:
                db.execute("INSERT OR REPLACE INTO collection_state(key,value) VALUES ('capacity_limit_bytes',?)", (str(limit),))

    def compact(self, backup: Path | str) -> dict[str, Any]:
        return compact(self.database, external_path(backup))

    def prune_tools(self, backup: Path | str) -> dict[str, Any]:
        return retention.prune_tools(self.database, external_path(backup))

    def delete_session(self, thread_id: str, instance: str | None = None) -> dict[str, Any]:
        return self._deletion.delete(thread_id, instance)

    def project_deletion_preview(self, project_id: str) -> dict[str, Any]:
        with closing(self._connect()) as db:
            rows = db.execute('SELECT summary FROM session_catalog WHERE project_id=? ORDER BY instance,thread', (project_id,)).fetchall()
        if not rows:
            raise KeyError('项目尚未保存或已删除。')
        sessions = [json.loads(row[0]) for row in rows]
        identities = [(s['source']['instance'], s['id']) for s in sessions]
        fingerprint = hashlib.sha256(json.dumps(identities).encode('utf-8')).hexdigest()
        return {'project': sessions[0]['project'], 'sessions': sessions, 'fingerprint': fingerprint}

    def delete_project(self, project_id: str, fingerprint: str) -> dict[str, Any]:
        preview = self.project_deletion_preview(project_id)
        if preview['fingerprint'] != fingerprint:
            raise ValueError('项目内的归档会话已变化，请重新打开项目删除确认页。')
        outcomes = []
        for session in preview['sessions']:
            try:
                result = self.delete_session(session['id'], session['source']['instance'])
                state = result['status']
            except (KeyError, ValueError, OSError, sqlite3.Error):
                state = 'failed'
            outcomes.append({'id': session['id'], 'name': session['name'], 'source': session['source']['instance'], 'status': state})
        return {'project': preview['project'], 'sessions': outcomes}

    def restore_session(self, thread_id: str, instance: str | None = None) -> dict[str, Any]:
        return self._deletion.restore(thread_id, instance)

    def exclusions(self) -> list[dict[str, Any]]:
        return self._deletion.entries()

    def is_excluded(self, thread_id: str, instance: str) -> bool:
        with closing(self._connect()) as db:
            return excluded(db, instance, thread_id)

    def import_session(self, thread_id: str, source: CodexHistory, page_size: int = 20) -> dict[str, Any]:
        if self.is_excluded(thread_id, source.instance()):
            raise HistoryError('会话已删除排除；只有显式解除排除后才允许重新归档。')
        capture = source.capture(thread_id, page_size)
        return self.save_capture(capture)

    def save_capture(self, capture: dict[str, Any]) -> dict[str, Any]:
        thread_id = capture["thread"]["id"]
        turns = {turn["id"]: turn for turn, _ in capture["turns"]}
        expected = {(t["id"], i["id"]): i for t in turns.values() for i in t["items"]}
        actual = {(entry["turnId"], entry["item"]["id"]): entry["item"] for entry, _ in capture["items"]}
        if expected != actual:
            raise HistoryError("完整回合与分页条目不一致；源可能正在变化或缺失关键记录，请稍后重试。")
        messages: list[dict[str, Any]] = []
        tools: list[dict[str, Any]] = []
        unsupported: list[dict[str, Any]] = []
        seen = set()
        gaps = ["仅保存接口当前可取得的历史；不承诺恢复隐藏信息或已丢弃内容。",
                "按来源条目身份保留工具参数与结果；嵌套调用未独立返回时不生成调用树。",
                "只展示正式历史接口实际返回的条目；不能保证底层包装函数或独立函数输出均已返回。",
                "工具执行状态不等于任务或业务成功；业务结果未知。",
                "只归档明确类型和字段中的本机可取得附件；远端、失效及不支持引用说明缺失。附件状态不代表完整原生备份。",
                "持续采集只在采集服务运行时检查；来源已丢弃的内容无法恢复。"]
        if "scope" in capture["source"]:
            gaps.append("首次范围从启用时开始：只读取启用后开始的回合；更早及跨启用时刻的回合未回补。来源只提供整秒时，启用同秒无法区分先后的回合也不读取；时间未知时报告错误。枚举接口附带的预览不保存。")
        for order, (entry, ref) in enumerate(capture["items"]):
            item = entry["item"]
            key = (entry["turnId"], item["id"])
            if key in seen:
                continue
            seen.add(key)
            if item["type"] in TOOL_TYPES:
                tools.append(tool_record(entry, ref, order))
                continue
            if item["type"] not in ("userMessage", "agentMessage"):
                unsupported.append({"id": item["id"], "turnId": entry["turnId"], "type": item["type"],
                                    "order": order, "completeness": "unknown",
                                    "reasons": ["不支持此类型的语义展示；完整来源载荷保留在原始证据中。"],
                                    "evidenceRef": ref + "/item"})
                continue
            phase = item.get("phase")
            completeness = "complete"
            reasons = []
            if item["type"] == "userMessage":
                text = "\n".join(c["text"] for c in item["content"] if c.get("type") == "text")
                if any(c.get("type") != "text" for c in item["content"]):
                    completeness = "partial"
                    reasons.append("含非文本输入；原始引用保留在证据中，附件取得状态见本条目附件。")
            else:
                text = item["text"]
                if phase not in ("commentary", "final_answer"):
                    completeness = "unknown"
                    reasons.append("数据源未提供可识别的 AI 消息阶段。")
            messages.append({"id": item["id"], "turnId": entry["turnId"], "type": item["type"],
                             "phase": phase, "text": text, "order": order,
                             "startedAtMs": entry.get("startedAtMs"), "completedAtMs": entry.get("completedAtMs"),
                             "completeness": completeness, "reasons": reasons, "evidenceRef": ref + "/item"})
        session = {"id": thread_id, "name": capture["thread"].get("name"), "savedAt": now(),
                   "createdAt": capture["thread"].get("createdAt"), "project": project_identity(capture["thread"], capture["source"]["instance"]),
                   "source": {**capture["source"], "gaps": gaps,
                              "notDisplayedTypes": sorted({i["type"] for i in actual.values() if i["type"] not in TOOL_TYPES | {"userMessage", "agentMessage"}}),
                              "pagination": {"turnPages": sum(e["method"] == "thread/turns/list" for e in capture["evidence"]),
                                             "itemPages": sum(e["method"] == "thread/items/list" for e in capture["evidence"])},
                              "itemsView": "full"},
                   "turns": [{k: v for k, v in t.items() if k != "items"} for t in turns.values()],
                   "messages": messages, "tools": tools, "unsupportedItems": unsupported, "sourceItemCount": len(actual),
                   "thread": capture["thread"]}
        package = {"schemaVersion": 1, "session": session, "evidence": capture["evidence"]}
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if excluded(db, session['source']['instance'], thread_id):
                raise HistoryError('会话已删除排除；读取期间的删除不会被迟到快照覆盖。')
            dialogue_only = retention.enabled(db)
            if dialogue_only:
                package = retention.dialogue_package(package)
                session = package['session']
            row = db.execute("SELECT package FROM snapshots WHERE instance=? AND thread=? ORDER BY number DESC LIMIT 1",
                             (session["source"]["instance"], thread_id)).fetchone()
            if not row and self.capacity(db)['paused']:
                raise CapacityReached('数据库已达到设置容量，暂停保存新会话。')
            if row:
                previous_package = decode_package(row[0])
                previous = previous_package["session"]
                scope = session["source"].get("scope")
                if scope:
                    # Previously authorized snapshots stay readable when the new
                    # automatic scope deliberately excludes their earlier turns.
                    kept_turns = [t for t in previous["turns"] if
                        (isinstance(t.get("startedAt"), (int, float)) and t["startedAt"] < scope["enabledAt"])
                        or t.get("startedAt") is None]
                    kept_ids = {t["id"] for t in kept_turns}
                    kept_entries = [e for group in ("messages", "tools", "unsupportedItems")
                                    for e in previous.get(group, []) if e["turnId"] in kept_ids]
                    indices = sorted({int(e["evidenceRef"].split("/")[2]) for e in kept_entries})
                    offset = len(indices)
                    order_offset = max((e["order"] for e in kept_entries), default=-1) + 1
                    index_map = {old: new for new, old in enumerate(indices)}
                    for group in ("messages", "tools", "unsupportedItems"):
                        for entry in session[group]:
                            parts = entry["evidenceRef"].split("/")
                            parts[2] = str(int(parts[2]) + offset)
                            entry["evidenceRef"] = "/".join(parts)
                            entry["order"] += order_offset
                        retained = [e for e in previous.get(group, []) if e["turnId"] in kept_ids]
                        for entry in retained:
                            parts = entry["evidenceRef"].split("/")
                            parts[2] = str(index_map[int(parts[2])])
                            entry["evidenceRef"] = "/".join(parts)
                        session[group] = retained + session[group]
                    session["turns"] = kept_turns + session["turns"]
                    session["sourceItemCount"] += len(kept_entries)
                    session["source"]["notDisplayedTypes"] = sorted(set(session["source"]["notDisplayedTypes"]) |
                        {e["type"] for e in kept_entries if e["type"] not in TOOL_TYPES | {"userMessage", "agentMessage"}})
                    package["evidence"] = [previous_package["evidence"][i] for i in indices] + package["evidence"]
                    # Compare against the original, unmodified saved document.
                    previous = decode_package(row[0])["session"]
                old_ids = {(m["turnId"], m["id"]) for group in ("messages", "tools", "unsupportedItems") for m in previous.get(group, [])}
                new_ids = {(m["turnId"], m["id"]) for group in ("messages", "tools", "unsupportedItems") for m in session.get(group, [])}
                if old_ids - new_ids:
                    raise HistoryError("来源本次缺少先前已保存条目；保留原快照与证据，缺失内容不能宣称已恢复。")
                archive_attachments(package, self.data_dir, decode_package(row[0]))
                if dialogue_only:
                    same_content = retention.unchanged(decode_package(row[0]), package)
                else:
                    old_evidence = evidence_payloads(decode_package(row[0])["evidence"])
                    new_evidence = evidence_payloads(package["evidence"])
                    same_content = ({k: v for k, v in previous.items() if k != "savedAt"} == {k: v for k, v in session.items() if k != "savedAt"}
                                    and old_evidence == new_evidence)
                if same_content:
                    return previous
            else:
                archive_attachments(package, self.data_dir)
            cursor = db.execute("INSERT INTO snapshots(instance, thread, saved, package) VALUES (?, ?, ?, ?)",
                       (session["source"]["instance"], thread_id, session["savedAt"], encode_package(package)))
            assert cursor.lastrowid is not None
            catalog.save_summary(db, session, cursor.lastrowid)
            turn_store.save(db, cursor.lastrowid, package)
        return session

    def _package(self, thread_id: str, instance: str | None = None, saved_at: str | None = None) -> dict[str, Any]:
        with closing(self._connect()) as db:
            if instance is None:
                identities = db.execute("SELECT DISTINCT instance FROM snapshots WHERE thread=?", (thread_id,)).fetchall()
                if len(identities) > 1:
                    raise ValueError("多个来源具有相同会话 ID；请指定来源实例。")
                instance = identities[0][0] if identities else None
            clause = " AND saved=?" if saved_at is not None else ""
            values = [thread_id, instance] + ([saved_at] if saved_at is not None else [])
            row = db.execute("SELECT package FROM snapshots WHERE thread=? AND instance=?" + clause + " ORDER BY number DESC LIMIT 1", values).fetchone()
        if row is None:
            raise KeyError("本机尚未保存这个会话。")
        return decode_package(row[0])

    def session(self, thread_id: str, instance: str | None = None, saved_at: str | None = None,
                include_history: bool = True) -> dict[str, Any]:
        return self._view_package(thread_id, instance, saved_at, include_history)["session"]

    def search(self, query: str, project: str | None = None, thread: str | None = None,
               instance: str | None = None, offset: int = 0, limit: int = 30) -> dict[str, Any]:
        with closing(self._connect()) as db:
            sessions = turn_store.searchable(db, project, thread, instance) if query.strip() else []
        return search_sessions(sessions, query, project, thread, instance, offset, limit)

    def evidence(self, thread_id: str, index: int, instance: str | None = None, saved_at: str | None = None) -> dict[str, Any]:
        return self._package(thread_id, instance, saved_at)["evidence"][index]

    def attachment(self, thread_id: str, identity: str, instance: str | None = None,
                   saved_at: str | None = None, turn_id: str | None = None) -> tuple[dict[str, Any], bytes]:
        session = self.turn(thread_id, turn_id, instance, saved_at)['session'] if turn_id is not None else self.session(thread_id, instance, saved_at)
        attachment = next((a for a in session["attachments"] if a["id"] == identity), None)
        if attachment is None:
            raise KeyError("没有此附件引用。")
        return attachment, read_copy(self.data_dir, attachment)

    def export_bundle(self, thread_id: str, instance: str | None = None, include_related: bool = False) -> bytes:
        from .offline import build_bundle
        return build_bundle(json.loads(self.export_session(thread_id, instance, include_related)), self.data_dir)

    def metadata(self, thread_id: str, instance: str | None = None, saved_at: str | None = None) -> dict[str, Any]:
        session = self._package(thread_id, instance, saved_at)["session"]
        return {"thread": session["thread"], "provenance": session["source"].get("metadataProvenance",
            "已保存的来源会话元数据；完整 thread/read 原始响应如已取得，可从导出 evidence 核对。")}

    def relation_evidence(self, identity: str, instance: str | None = None) -> dict[str, Any]:
        for entry in self.collection_state().get("relationMetadata", []):
            if entry["id"] == identity and (instance is None or entry["sourceInstance"] == instance):
                return entry
        raise KeyError("未保存此关系元数据投影。")

    def sessions(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            return catalog.summaries(db)

    def projects(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            return catalog.projects(db)

    def project_sessions(self, project_id: str | None = None, offset: int = 0,
                         limit: int = 30, query: str = "") -> dict[str, Any]:
        with closing(self._connect()) as db:
            return catalog.directory(db, project_id, offset, limit, query)

    def project_choices(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            return catalog.project_choices(db)

    def session_summary(self, thread_id: str, instance: str) -> dict[str, Any]:
        with closing(self._connect()) as db:
            return catalog.session_summary(db, thread_id, instance)

    def project_turns(self, project_id: str, offset: int = 0, limit: int = 30,
                      thread: str | None = None, instance: str | None = None) -> dict[str, Any]:
        with closing(self._connect()) as db:
            return turn_store.directory(db, project_id, offset, limit, thread, instance)

    def project_directory(self, project_id: str, offset: int = 0, limit: int = 10) -> dict[str, Any]:
        with closing(self._connect()) as db:
            return turn_store.project_page(db, project_id, offset, limit)

    def turn(self, thread_id: str, turn_id: str, instance: str | None = None,
             saved_at: str | None = None) -> dict[str, Any]:
        with closing(self._connect()) as db:
            result = turn_store.read(db, thread_id, turn_id, instance, saved_at)
        attachment_view({'session': result['session']}, self.data_dir)
        for attachment in result['session'].get('attachments', []):
            if attachment.get('url'):
                attachment['url'] += '&turn=' + quote(turn_id, safe='')
        for tool in result['session'].get('tools', []):
            require_command_exit(tool)
        return result

    def session_turns(self, thread_id: str, instance: str | None = None, saved_at: str | None = None,
                      offset: int = 0, limit: int = 30, target: str | None = None) -> dict[str, Any]:
        with closing(self._connect()) as db:
            return turn_store.session_directory(db, thread_id, instance, saved_at, offset, limit, target)

    def collection_state(self) -> dict[str, Any]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT value FROM collection_state WHERE key='collector'").fetchone()
        return json.loads(row[0]) if row else {}

    def save_collection_state(self, state: dict[str, Any]) -> None:
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("INSERT OR REPLACE INTO collection_state(key,value) VALUES ('collector',?)", (json.dumps(filter_state(db, state), ensure_ascii=False),))

    def _view_package(self, thread_id: str, instance: str | None = None, saved_at: str | None = None,
                      include_history: bool = True) -> dict[str, Any]:
        package = self._package(thread_id, instance, saved_at)
        revisions = []
        if include_history:
            with closing(self._connect()) as db:
                # Pin history to the package selected above, even if a collector
                # saves another version while this request is being rendered.
                selected = db.execute("SELECT number FROM snapshots WHERE thread=? AND instance=? AND saved=? ORDER BY number DESC LIMIT 1",
                                      (thread_id, package['session']['source']['instance'], package['session']['savedAt'])).fetchone()
                if selected is None:
                    raise KeyError("本机尚未保存这个会话。")
                rows = db.execute("SELECT package FROM snapshots WHERE thread=? AND instance=? AND number<? ORDER BY number",
                                  (thread_id, package['session']['source']['instance'], selected[0]))
                revisions = [decode_package(row[0]) for row in rows]
        attachment_view(package, self.data_dir)
        for tool in package["session"].get("tools", []):
            require_command_exit(tool)
        for revision in revisions:
            attachment_view(revision, self.data_dir)
        package["session"]["executions"] = executions(revisions + [package])
        package["session"]["executionGaps"] = EXECUTION_GAPS
        package["session"]["relations"] = self._relations(package)
        metadata_ids = {r["metadataEvidenceId"] for r in package["session"]["relations"] if r.get("metadataEvidenceId")}
        if metadata_ids:
            package["relationEvidence"] = {identity: self.relation_evidence(identity, package["session"]["source"]["instance"])
                                           for identity in metadata_ids}
        package["session"]["relationGaps"] = RELATION_GAPS
        if revisions:
            package["revisions"] = [relocate(revision, f"#/revisions/{index}") for index, revision in enumerate(revisions)]
        return package

    def _relations(self, package: dict[str, Any]) -> list[dict[str, Any]]:
        current = package["session"]
        instance, thread_id = current["source"]["instance"], current["id"]
        summaries = {(s["source"]["instance"], s["id"]): s for s in self.sessions()}
        state = self.collection_state()
        statuses = {s["id"]: s for s in state.get("sessions", []) if s.get("source") == instance}
        candidates = []
        for (source_instance, identity), _ in summaries.items():
            if source_instance != instance:
                continue
            owner = package if identity == thread_id else self._package(identity, instance)
            candidates.extend(relation_records(owner))
        known_relations = {(r["ownerId"], r["type"], r["fromId"], r["toId"], r["basis"]) for r in candidates}
        for evidence in state.get("relationMetadata", []):
            if evidence["sourceInstance"] != instance:
                continue
            owner = {"session": {"id": evidence["thread"]["id"], "thread": evidence["thread"],
                     "source": {"instance": instance}, "savedAt": evidence["observedAt"]}, "evidence": []}
            for record in relation_records(owner):
                identity_key = (record["ownerId"], record["type"], record["fromId"], record["toId"], record["basis"])
                if identity_key in known_relations:
                    continue
                known_relations.add(identity_key)
                record["metadataEvidenceId"] = evidence["id"]
                record["evidenceRef"] = f'#/relationEvidence/{evidence["id"]}/thread'
                candidates.append(record)
        records = []
        for record in candidates:
            if thread_id not in (record["fromId"], record["toId"], record["ownerId"]):
                continue
            outgoing = record["fromId"] == thread_id
            target = record["toId"] if outgoing else record["fromId"]
            saved = summaries.get((instance, target))
            status = statuses.get(target, {})
            deleted = bool(target and self.is_excluded(target, instance))
            availability = "deleted" if deleted else "archived" if saved else "unavailable" if status.get("error") else "notArchived" if target else "unknown"
            reason = record["reason"]
            if not saved:
                detail = "目标受管理归档已删除并排除；此关系仍来自本会话实际保存的来源证据，不表示目标正文仍可取得。" if deleted else status.get("error") or ("目标不在已启用的正文采集范围内；仅保存已取得的关系元数据，不补读正文。"
                    if status.get("status") == "outsideScope" else "目标尚未获授权归档，可能在启用范围外、不可见或来源未提供；不读取正文。")
                reason += " " + (detail if target else "目标身份未知。")
            elif status.get("error"):
                reason += " 来源当前不可访问；只能查看已保存快照：" + status["error"]
            evidence_included = record["ownerId"] == thread_id or bool(record.get("metadataEvidenceId"))
            records.append({**record, "ownerEvidenceRef": record["evidenceRef"],
                            "evidenceRef": record["evidenceRef"] if evidence_included else None,
                            "evidenceUnavailableReason": None if evidence_included else "关系证据位于另一归档会话；当前单会话文档未包含。",
                            "targetId": target, "direction": "outgoing" if outgoing else "incoming",
                            "availability": availability, "reason": reason.strip()})
        return records

    def export_session(self, thread_id: str, instance: str | None = None, include_related: bool = False) -> str:
        package = self._view_package(thread_id, instance)
        instance = package["session"]["source"]["instance"]
        included = {thread_id: "#"}
        if include_related:
            identities = sorted({r["targetId"] for r in package["session"]["relations"]
                                 if r["availability"] == "archived" and r["targetId"] != thread_id})
            package["related"] = []
            for identity in identities:
                prefix = f'#/related/{len(package["related"])}'
                included[identity] = prefix
                package["related"].append(relocate(self._view_package(identity, instance), prefix))
        omitted = []
        documents = {p["session"]["id"]: p for p in [package] + package.get("related", [])}
        for document in documents.values():
            for relation in document["session"]["relations"]:
                if not relation.get("metadataEvidenceId"):
                    owner_prefix = included.get(relation["ownerId"])
                    owner = documents.get(relation["ownerId"])
                    if owner and owner["session"]["savedAt"] != relation["savedAt"]:
                        revision_index = next((i for i, r in enumerate(owner.get("revisions", []))
                                               if r["session"]["savedAt"] == relation["savedAt"]), None)
                        owner_prefix = f'{owner_prefix}/revisions/{revision_index}' if revision_index is not None else None
                    relation["evidenceRef"] = owner_prefix + relation["ownerEvidenceRef"][1:] if owner_prefix else None
                    relation["evidenceUnavailableReason"] = (None if owner_prefix else
                        "该关系的所有者保存版本未包含；不能使用另一版本的证据位置。" if owner else
                        "关系证据位于另一归档会话；当前单会话文档未包含。")
                if relation["targetId"] not in included:
                    reason = relation["availability"] if relation["availability"] != "archived" else "beyondOneHop" if include_related else "notSelected"
                    omitted.append({"fromSession": document["session"]["id"], "targetId": relation["targetId"],
                                    "type": relation["type"], "reason": reason, "detail": relation["reason"]})
        package["exportScope"] = {"mode": "oneHopArchived" if include_related else "single", "sourceInstance": instance,
            "included": list(included), "omitted": omitted,
            "note": "仅包含此会话及显式选择的一层已归档关联会话（含父／子／分叉／交互）；不递归、不连接来源，不读取未归档目标。外部会话的证据未包含时 evidenceRef=null，ownerEvidenceRef 仅定位该所有者自己的保存文档。"}
        return json.dumps(package, ensure_ascii=False, indent=2)


def evidence_payloads(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Request IDs and collection clocks change on a reread; actual source
    # results (including unsupported payloads) are part of every saved revision.
    return [{"method": e["method"], "params": e["params"],
             "result": e["response"].get("result"), "error": e["response"].get("error")} for e in evidence]
