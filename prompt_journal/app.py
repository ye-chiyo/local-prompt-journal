from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import hashlib
from typing import Any

from .source import CodexHistory, HistoryError, now
from .tool_evidence import TOOL_TYPES, tool_record, require_command_exit
from .topology import EXECUTION_GAPS, RELATION_GAPS, executions, relocate, relation_records
from .search import search_sessions


def default_data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "LocalPromptJournal" / "data"


def external_path(path: Path | str) -> Path:
    destination = Path(path).resolve()
    if destination.is_relative_to(Path(__file__).resolve().parent.parent):
        raise ValueError("运行时日志与导出必须位于项目源码以外。")
    return destination


class Journal:
    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        self.data_dir = external_path(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database = self.data_dir / "journal.sqlite3"
        with closing(self._connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS snapshots (number INTEGER PRIMARY KEY, instance TEXT NOT NULL, thread TEXT NOT NULL, saved TEXT NOT NULL, package TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS collection_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database, timeout=10)

    def import_session(self, thread_id: str, source: CodexHistory, page_size: int = 20) -> dict[str, Any]:
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
                "未复制附件；附件引用不等于附件已备份。",
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
                    reasons.append("非文本输入仅保留原始引用，附件尚未备份。")
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
            row = db.execute("SELECT package FROM snapshots WHERE instance=? AND thread=? ORDER BY number DESC LIMIT 1",
                             (session["source"]["instance"], thread_id)).fetchone()
            if row:
                previous_package = json.loads(row[0])
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
                    previous = json.loads(row[0])["session"]
                old_ids = {(m["turnId"], m["id"]) for group in ("messages", "tools", "unsupportedItems") for m in previous.get(group, [])}
                new_ids = {(m["turnId"], m["id"]) for group in ("messages", "tools", "unsupportedItems") for m in session.get(group, [])}
                if old_ids - new_ids:
                    raise HistoryError("来源本次缺少先前已保存条目；保留原快照与证据，缺失内容不能宣称已恢复。")
                old_evidence = evidence_payloads(json.loads(row[0])["evidence"])
                new_evidence = evidence_payloads(package["evidence"])
                if ({k: v for k, v in previous.items() if k != "savedAt"} == {k: v for k, v in session.items() if k != "savedAt"}
                        and old_evidence == new_evidence):
                    return previous
            db.execute("INSERT INTO snapshots(instance, thread, saved, package) VALUES (?, ?, ?, ?)",
                       (session["source"]["instance"], thread_id, session["savedAt"], json.dumps(package, ensure_ascii=False)))
        return session

    def _package(self, thread_id: str, instance: str | None = None, saved_at: str | None = None) -> dict[str, Any]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT instance, package FROM snapshots WHERE thread=? ORDER BY number DESC", (thread_id,)).fetchall()
        if instance is not None:
            rows = [r for r in rows if r[0] == instance]
        if saved_at is not None:
            rows = [r for r in rows if json.loads(r[1])["session"]["savedAt"] == saved_at]
        if not rows:
            raise KeyError("本机尚未保存这个会话。")
        if len({r[0] for r in rows}) > 1:
            raise ValueError("多个来源具有相同会话 ID；请指定来源实例。")
        return json.loads(rows[0][1])

    def session(self, thread_id: str, instance: str | None = None, saved_at: str | None = None) -> dict[str, Any]:
        return self._view_package(thread_id, instance, saved_at)["session"]

    def search(self, query: str, project: str | None = None, thread: str | None = None,
               instance: str | None = None, offset: int = 0, limit: int = 30) -> dict[str, Any]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT package FROM snapshots WHERE number IN (SELECT MAX(number) FROM snapshots GROUP BY instance, thread)").fetchall()
        sessions = [json.loads(row[0])["session"] for row in rows]
        for session in sessions:
            session.setdefault("project", project_identity(session["thread"], session["source"]["instance"]))
            session.setdefault("createdAt", session["thread"].get("createdAt"))
        return search_sessions(sorted(sessions, key=session_order), query, project, thread, instance, offset, limit)

    def evidence(self, thread_id: str, index: int, instance: str | None = None, saved_at: str | None = None) -> dict[str, Any]:
        return self._package(thread_id, instance, saved_at)["evidence"][index]

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
            rows = db.execute("SELECT package FROM snapshots WHERE number IN (SELECT MAX(number) FROM snapshots GROUP BY instance, thread) ORDER BY number DESC").fetchall()
        summaries = []
        for row in rows:
            session = json.loads(row[0])["session"]
            summaries.append({**{k: session[k] for k in ("id", "name", "savedAt", "source")},
                "createdAt": session.get("createdAt", session["thread"].get("createdAt")),
                "project": session.get("project", project_identity(session["thread"], session["source"]["instance"]))})
        return sorted(summaries, key=session_order)

    def projects(self) -> list[dict[str, Any]]:
        projects: dict[str, dict[str, Any]] = {}
        for session in self.sessions():
            project = session["project"]
            projects.setdefault(project["id"], {**project, "sessions": []})["sessions"].append(session)
        return sorted(projects.values(), key=lambda p: (p["label"], p["id"]))

    def collection_state(self) -> dict[str, Any]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT value FROM collection_state WHERE key='collector'").fetchone()
        return json.loads(row[0]) if row else {}

    def save_collection_state(self, state: dict[str, Any]) -> None:
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO collection_state(key,value) VALUES ('collector',?)", (json.dumps(state, ensure_ascii=False),))

    def _view_package(self, thread_id: str, instance: str | None = None, saved_at: str | None = None) -> dict[str, Any]:
        package = self._package(thread_id, instance, saved_at)
        with closing(self._connect()) as db:
            rows = db.execute("SELECT package FROM snapshots WHERE thread=? AND instance=? ORDER BY number",
                              (thread_id, package["session"]["source"]["instance"])).fetchall()
        if saved_at is not None:
            selected = next(i for i, row in enumerate(rows) if json.loads(row[0])["session"]["savedAt"] == saved_at)
            rows = rows[:selected + 1]
        # Use one coherent history; a search target stays at its selected version.
        package = json.loads(rows[-1][0])
        for tool in package["session"].get("tools", []):
            require_command_exit(tool)
        revisions = [json.loads(row[0]) for row in rows[:-1]]
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
            availability = "archived" if saved else "unavailable" if status.get("error") else "notArchived" if target else "unknown"
            reason = record["reason"]
            if not saved:
                detail = status.get("error") or ("目标不在已启用的正文采集范围内；仅保存已取得的关系元数据，不补读正文。"
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


def evidence_payloads(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Request IDs and collection clocks change on a reread; actual source
    # results (including unsupported payloads) are part of every saved revision.
    return [{"method": e["method"], "params": e["params"],
             "result": e["response"].get("result"), "error": e["response"].get("error")} for e in evidence]
