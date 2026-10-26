from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from typing import Any

from .app import Journal, external_path
from .source import CodexHistory, HistoryError
from .web import create_server
from .sync import Collector


def write_export(destination: Path, content: str) -> None:
    destination = external_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def probe(source: CodexHistory, thread_id: str, expected_path: Path | None, page_size: int) -> dict[str, Any]:
    capture = source.capture(thread_id, page_size)
    actual = {(e["turnId"], e["item"]["id"]): e["item"] for e, _ in capture["items"] if e["item"]["type"] in ("userMessage", "agentMessage")}
    result: dict[str, Any] = {"source": capture["source"], "threadId": thread_id,
        "turnCount": len(capture["turns"]), "sourceItemCount": len(capture["items"]),
        "messageCounts": dict(Counter(i["type"] for i in actual.values())),
        "phaseCounts": dict(Counter(str(i.get("phase")) for i in actual.values())),
        "turnPages": sum(e["method"] == "thread/turns/list" for e in capture["evidence"]),
        "itemPages": sum(e["method"] == "thread/items/list" for e in capture["evidence"]),
        "methods": sorted({e["method"] for e in capture["evidence"]}),
        "threadStatus": capture["thread"].get("status"), "passed": False,
        "note": "能力探测不等于真实样本验收；必须提供导入前独立定义的预期清单。"}
    if expected_path is not None:
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        if expected.get("thread", {}).get("id") != thread_id or expected.get("page", {}).get("hasMore") is not False or expected.get("definedBeforeImport") is not True:
            raise ValueError("预期清单身份不匹配、尚未读取完整或未声明在导入前定义。")
        def fields(item: dict[str, Any]) -> tuple[Any, ...]:
            text = item.get("text") if item["type"] == "agentMessage" else [c.get("text") for c in item["content"] if c.get("type") == "text"]
            return item["type"], item.get("phase"), text
        wanted = {(t["id"], i["id"]): fields(i) for t in expected["turns"] for i in t["messages"]}
        got = {k: fields(i) for k, i in actual.items()}
        wanted_turns = {t["id"]: t["status"] for t in expected["turns"]}
        got_turns = {t["id"]: t["status"] for t, _ in capture["turns"]}
        turn_messages = {(t["id"], i["id"]): fields(i) for t, _ in capture["turns"] for i in t["items"] if i["type"] in ("userMessage", "agentMessage")}
        result.update({"passed": wanted == got == turn_messages and wanted_turns == got_turns,
                       "expectedMessageCount": len(wanted), "messageEquality": wanted == got,
                       "turnPaginationEquality": turn_messages == got, "statusEquality": wanted_turns == got_turns,
                       "missingIds": [list(k) for k in wanted.keys() - got.keys()],
                       "differentIds": [list(k) for k in wanted.keys() & got.keys() if wanted[k] != got[k]],
                       "note": "仅验证此版本、此本机来源、此选定会话；不代表所有桌面格式或消息类型均已认证。"})
    return result


def main() -> int:
    # Explicit encoding also keeps Chinese JSON usable in Windows pipes.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="本机 Codex 会话记录：只读历史、保存、查看与导出")
    parser.add_argument("--data-dir", type=Path, help="源码之外的运行时目录；默认 LOCALAPPDATA/LocalPromptJournal/data")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="从本机正式接口导入一个明确选择的会话")
    importer.add_argument("thread_id")
    importer.add_argument("--page-size", type=int, default=20)
    prober = commands.add_parser("probe", help="薄真实只读契约检查，不保存会话")
    prober.add_argument("thread_id")
    prober.add_argument("--page-size", type=int, default=1)
    prober.add_argument("--expected", type=Path)
    prober.add_argument("--report", type=Path)
    commands.add_parser("list", help="查询已保存的本机会话")
    for name in ("show", "export"):
        command = commands.add_parser(name)
        command.add_argument("thread_id")
        command.add_argument("--source-instance")
        if name == "export":
            command.add_argument("--output", type=Path, required=True)
    server = commands.add_parser("serve", help="在 127.0.0.1 打开只读查看服务；Ctrl+C 关闭")
    server.add_argument("--port", type=int, default=8765)
    runner = commands.add_parser("run", help="启动自动发现、持续采集与本机页面；Ctrl+C 停止")
    runner.add_argument("--port", type=int, default=8766)
    runner.add_argument("--interval", type=float, default=3)
    runner.add_argument("--start-from-now", action="store_true", help="仅首次启用：从下一新回合开始，不回补旧正文")
    args = parser.parse_args()
    try:
        if args.command == "probe":
            with CodexHistory() as source:
                result = probe(source, args.thread_id, args.expected, args.page_size)
            serialized = json.dumps(result, ensure_ascii=False, indent=2)
            if args.report:
                write_export(args.report, serialized)
            print(serialized)
            return 0 if result["passed"] else 1
        app = Journal(args.data_dir)
        if args.command == "import":
            with CodexHistory() as source:
                view = app.import_session(args.thread_id, source, args.page_size)
            print(json.dumps({"saved": True, "threadId": view["id"], "messageCount": len(view["messages"]), "dataDir": str(app.data_dir)}, ensure_ascii=False))
        elif args.command == "list":
            print(json.dumps(app.sessions(), ensure_ascii=False, indent=2))
        elif args.command == "show":
            print(json.dumps(app.session(args.thread_id, args.source_instance), ensure_ascii=False, indent=2))
        elif args.command == "export":
            write_export(args.output, app.export_session(args.thread_id, args.source_instance))
            print(json.dumps({"saved": str(args.output.resolve())}, ensure_ascii=False))
        elif args.command in ("serve", "run"):
            collector = Collector(app, interval=args.interval, enabled_at=time.time() if args.start_from_now else None) if args.command == "run" else None
            server_instance = create_server(app, args.port, collector)
            if collector:
                collector.start()
            print(f"本机会话记录：http://127.0.0.1:{server_instance.server_port} · 数据：{app.data_dir}", flush=True)
            try:
                server_instance.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                if collector:
                    collector.stop()
                server_instance.server_close()
        return 0
    except (HistoryError, OSError, sqlite3.Error, ValueError, KeyError) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
