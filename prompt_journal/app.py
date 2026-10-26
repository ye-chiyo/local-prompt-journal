from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import hashlib
from typing import Any

from .source import CodexHistory, HistoryError, now
from .tool_evidence import TOOL_TYPES, tool_record


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

    def session(self, thread_id: str, instance: str | None = None) -> dict[str, Any]:
        return self._package(thread_id, instance)["session"]

    def evidence(self, thread_id: str, index: int, instance: str | None = None, saved_at: str | None = None) -> dict[str, Any]:
        return self._package(thread_id, instance, saved_at)["evidence"][index]

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

    def export_session(self, thread_id: str, instance: str | None = None) -> str:
        package = self._package(thread_id, instance)
        with closing(self._connect()) as db:
            rows = db.execute("SELECT package FROM snapshots WHERE thread=? AND instance=? ORDER BY number",
                              (thread_id, package["session"]["source"]["instance"])).fetchall()
        revisions = [json.loads(row[0]) for row in rows[:-1]]
        for index, revision in enumerate(revisions):
            for group in ("messages", "tools", "unsupportedItems"):
                for entry in revision["session"].get(group, []):
                    entry["evidenceRef"] = entry["evidenceRef"].replace("#/evidence/", f"#/revisions/{index}/evidence/", 1)
        if revisions:
            package["revisions"] = revisions
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
