from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from .source import CodexHistory, HistoryError, now


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

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database, timeout=10)

    def import_session(self, thread_id: str, source: CodexHistory, page_size: int = 20) -> dict[str, Any]:
        capture = source.capture(thread_id, page_size)
        turns = {turn["id"]: turn for turn, _ in capture["turns"]}
        expected = {(t["id"], i["id"]): i for t in turns.values() for i in t["items"]}
        actual = {(entry["turnId"], entry["item"]["id"]): entry["item"] for entry, _ in capture["items"]}
        if expected != actual:
            raise HistoryError("完整回合与分页条目不一致；源可能正在变化或缺失关键记录，请稍后重试。")
        messages: list[dict[str, Any]] = []
        seen = set()
        gaps = ["仅保存接口当前可取得的历史；不承诺恢复隐藏信息或已丢弃内容。",
                "任务 01 仅展示用户与 AI 消息；其他条目保留在原始证据中，工具语义尚未验收。",
                "未复制附件；附件引用不等于附件已备份。",
                "单次手动快照；未实现自动持续同步。"]
        for entry, ref in capture["items"]:
            item = entry["item"]
            key = (entry["turnId"], item["id"])
            if key in seen:
                continue
            seen.add(key)
            if item["type"] not in ("userMessage", "agentMessage"):
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
                             "phase": phase, "text": text, "order": len(messages),
                             "startedAtMs": entry.get("startedAtMs"), "completedAtMs": entry.get("completedAtMs"),
                             "completeness": completeness, "reasons": reasons, "evidenceRef": ref + "/item"})
        session = {"id": thread_id, "name": capture["thread"].get("name"), "savedAt": now(),
                   "source": {**capture["source"], "gaps": gaps,
                              "notDisplayedTypes": sorted({i["type"] for i in actual.values() if i["type"] not in ("userMessage", "agentMessage")}),
                              "pagination": {"turnPages": sum(e["method"] == "thread/turns/list" for e in capture["evidence"]),
                                             "itemPages": sum(e["method"] == "thread/items/list" for e in capture["evidence"])},
                              "itemsView": "full"},
                   "turns": [{k: v for k, v in t.items() if k != "items"} for t in turns.values()],
                   "messages": messages, "sourceItemCount": len(actual),
                   "thread": capture["thread"]}
        package = {"schemaVersion": 1, "session": session, "evidence": capture["evidence"]}
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO snapshots(instance, thread, saved, package) VALUES (?, ?, ?, ?)",
                       (session["source"]["instance"], thread_id, session["savedAt"], json.dumps(package, ensure_ascii=False)))
        return session

    def _package(self, thread_id: str, instance: str | None = None) -> dict[str, Any]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT instance, package FROM snapshots WHERE thread=? ORDER BY number DESC", (thread_id,)).fetchall()
        if instance is not None:
            rows = [r for r in rows if r[0] == instance]
        if not rows:
            raise KeyError("本机尚未保存这个会话。")
        if len({r[0] for r in rows}) > 1:
            raise ValueError("多个来源具有相同会话 ID；请指定来源实例。")
        return json.loads(rows[0][1])

    def session(self, thread_id: str, instance: str | None = None) -> dict[str, Any]:
        return self._package(thread_id, instance)["session"]

    def sessions(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT package FROM snapshots WHERE number IN (SELECT MAX(number) FROM snapshots GROUP BY instance, thread) ORDER BY number DESC").fetchall()
        return [{k: json.loads(row[0])["session"][k] for k in ("id", "name", "savedAt", "source")} for row in rows]

    def export_session(self, thread_id: str, instance: str | None = None) -> str:
        return json.dumps(self._package(thread_id, instance), ensure_ascii=False, indent=2)
