from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import tempfile
import time
from typing import Any

from .app import Journal, external_path
from .source import CodexHistory, HistoryError
from .web import create_server
from .sync import Collector


def write_export(destination: Path, content: str | bytes) -> None:
    destination = external_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content.encode("utf-8") if isinstance(content, str) else content)
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


def main(argv: list[str] | None = None) -> int:
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
    compactor = commands.add_parser('compact', help='停服后无损压缩快照并回收空间；保留全部原文和版本')
    compactor.add_argument('--backup', type=Path, required=True, help='新的源码外备份文件；不会覆盖已有文件')
    pruner = commands.add_parser('prune-tools', help='停服并备份后，删除全部版本的工具与不支持条目；后续只保存对话')
    pruner.add_argument('--backup', type=Path, required=True, help='新的源码外备份文件；附件原字节保留以支持恢复')
    commands.add_parser('exclusions', help='查看删除排除及未完成的附件清理')
    for name in ('delete', 'restore'):
        management = commands.add_parser(name, help='删除受管理日志并排除自动归档' if name == 'delete' else '显式解除删除排除；沿用原自动采集范围')
        management.add_argument('thread_id')
        management.add_argument('--source-instance')
        if name == 'delete':
            management.add_argument('--yes', action='store_true', required=True, help='确认仅删除本应用归档；不改 Codex 原会话或另存导出')
    for name in ("show", "export", "bundle"):
        command = commands.add_parser(name)
        command.add_argument("thread_id")
        command.add_argument("--source-instance")
        if name in ("export", "bundle"):
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--include-related", action="store_true", help="显式包含一层已保存关联会话；不递归读取来源")
    server = commands.add_parser("serve", help="在 127.0.0.1 打开不采集的本机阅读与管理服务；Ctrl+C 关闭")
    server.add_argument("--port", type=int, default=8765)
    runner = commands.add_parser("run", help="启动自动发现、持续采集与本机页面；Ctrl+C 停止")
    runner.add_argument("--port", type=int, default=8766)
    runner.add_argument("--interval", type=float, default=3)
    runner.add_argument("--start-from-now", action="store_true", help="仅首次启用：从下一新回合开始，不回补旧正文")
    runner.add_argument("--stop-file", type=Path, help=argparse.SUPPRESS)
    commands.add_parser("monitor", help=argparse.SUPPRESS)
    commands.add_parser("install-autostart", help="安装当前用户的隐藏 ChatGPT 桌面联动监视器")
    commands.add_parser("uninstall-autostart", help="移除当前用户的 ChatGPT 桌面联动监视器")
    commands.add_parser("install-shortcuts", help="在 Windows 桌面和开始菜单创建 Codex 日志网站入口")
    args = parser.parse_args(argv)
    try:
        if args.command == "install-shortcuts":
            from .desktop import install_website_shortcuts
            print(json.dumps({"installed": True, "shortcuts": install_website_shortcuts()}, ensure_ascii=False))
            return 0
        if args.command == "monitor":
            from .desktop import run_monitor
            from .app import default_data_dir
            run_monitor(Path(__file__).resolve().parent.parent, args.data_dir or default_data_dir())
            return 0
        if args.command == "install-autostart":
            from .desktop import install_startup_task
            task = install_startup_task(Path(__file__).resolve().parent.parent, data_dir=args.data_dir)
            print(json.dumps({"installed": True, "task": task}, ensure_ascii=False))
            return 0
        if args.command == "uninstall-autostart":
            from .desktop import uninstall_startup_task
            removed = uninstall_startup_task(data_dir=args.data_dir)
            print(json.dumps({"removed": removed}, ensure_ascii=False))
            return 0
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
        elif args.command == 'compact':
            print(json.dumps(app.compact(args.backup), ensure_ascii=False, indent=2))
        elif args.command == 'prune-tools':
            print(json.dumps(app.prune_tools(args.backup), ensure_ascii=False, indent=2))
        elif args.command == 'exclusions':
            print(json.dumps(app.exclusions(), ensure_ascii=False, indent=2))
        elif args.command in ('delete', 'restore'):
            outcome = app.delete_session(args.thread_id, args.source_instance) if args.command == 'delete' else app.restore_session(args.thread_id, args.source_instance)
            print(json.dumps(outcome, ensure_ascii=False, indent=2))
            return 1 if outcome['status'] == 'cleanupPending' else 0
        elif args.command == "show":
            print(json.dumps(app.session(args.thread_id, args.source_instance), ensure_ascii=False, indent=2))
        elif args.command == "export":
            write_export(args.output, app.export_session(args.thread_id, args.source_instance, args.include_related))
            print(json.dumps({"saved": str(args.output.resolve())}, ensure_ascii=False))
        elif args.command == "bundle":
            write_export(args.output, app.export_bundle(args.thread_id, args.source_instance, args.include_related))
            print(json.dumps({"saved": str(args.output.resolve()), "bundleVersion": 1}, ensure_ascii=False))
        elif args.command in ("serve", "run"):
            collector = Collector(app, interval=args.interval, enabled_at=time.time() if args.start_from_now else None) if args.command == "run" else None
            server_instance = create_server(app, args.port, collector)
            if collector:
                collector.start()
                if args.stop_file:
                    from .desktop import wait_for_stop_file
                    threading.Thread(target=wait_for_stop_file,
                        args=(args.stop_file, server_instance.shutdown), daemon=True).start()
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
    except (HistoryError, OSError, sqlite3.Error, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
