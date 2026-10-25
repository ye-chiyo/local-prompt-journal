"""Read-only App Server client. No resume, turn, tool, or model methods."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import shutil
import subprocess
import threading
from typing import Any


class HistoryError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CodexHistory:
    ALLOWED = frozenset({"initialize", "thread/read", "thread/turns/list", "thread/items/list"})

    def __init__(self, command: list[str] | None = None, timeout: float = 20):
        if command is None:
            exe = shutil.which("codex")
            if not exe:
                raise HistoryError("找不到 codex；请安装或将桌面捆绑的 codex.exe 加入 PATH。")
            command = [exe, "-c", "analytics.enabled=false", "-c", "feedback.enabled=false",
                       "-c", 'otel.exporter="none"', "-c", 'otel.trace_exporter="none"',
                       "app-server", "--stdio"]
        self.command = command
        self.timeout = timeout
        self.process: subprocess.Popen[str] | None = None
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.errors: deque[str] = deque(maxlen=20)
        self.evidence: list[dict[str, Any]] = []
        self.threads: list[threading.Thread] = []
        self.identity: dict[str, Any] = {}
        self.serial = 0

    def __enter__(self) -> CodexHistory:
        try:
            self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
            self.threads = [threading.Thread(target=self._read_stdout, daemon=True),
                            threading.Thread(target=self._read_stderr, daemon=True)]
            for thread in self.threads:
                thread.start()
            self.identity = self.request("initialize", {
                "clientInfo": {"name": "local_prompt_journal", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            })
            self._send({"method": "initialized"})
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            for thread in self.threads:
                thread.join(timeout=1)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                if stream:
                    stream.close()
            self.process = None

    def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        try:
            for line in self.process.stdout:
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def _read_stderr(self) -> None:
        assert self.process and self.process.stderr
        for line in self.process.stderr:
            self.errors.append(line)

    def _send(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise HistoryError("只读历史连接未打开。")
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method not in self.ALLOWED:
            raise HistoryError(f"只读历史客户端拒绝方法：{method}")
        self.serial += 1
        request_id = self.serial
        self._send({"id": request_id, "method": method, "params": params})
        while True:
            try:
                raw = self.lines.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise HistoryError(f"{method} 超时；未恢复原会话。") from exc
            if raw is None:
                raise HistoryError(f"{method} 连接关闭：{''.join(self.errors)}")
            try:
                response = json.loads(raw)
            except ValueError as exc:
                raise HistoryError("历史接口返回无法解析的 JSON。") from exc
            if "method" in response:
                if "id" in response:
                    self._send({"id": response["id"], "error": {
                        "code": -32601, "message": "Read-only history client cannot handle requests"}})
                continue
            if response.get("id") != request_id:
                continue
            self.evidence.append({"method": method, "params": params, "raw": raw,
                                  "response": response, "collectedAt": now(),
                                  "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()})
            if "error" in response:
                raise HistoryError(f"{method} 不可用：{json.dumps(response['error'], ensure_ascii=False)}")
            result = response.get("result")
            if not isinstance(result, dict):
                raise HistoryError(f"{method} 缺少有效结果。")
            return result

    def pages(self, method: str, params: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
        entries: list[tuple[dict[str, Any], str]] = []
        cursor = None
        seen = set()
        while True:
            page_params = dict(params)
            if cursor is not None:
                page_params["cursor"] = cursor
            response = self.request(method, page_params)
            evidence_index = len(self.evidence) - 1
            if not isinstance(response.get("data"), list) or "nextCursor" not in response:
                raise HistoryError(f"{method} 分页结果格式未知。")
            entries.extend((entry, f"#/evidence/{evidence_index}/response/result/data/{i}")
                           for i, entry in enumerate(response["data"]))
            cursor = response["nextCursor"]
            if cursor is None:
                return entries
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise HistoryError(f"{method} 返回重复或无效游标，不能宣称读取完整。")
            seen.add(cursor)

    def capture(self, thread_id: str, page_size: int) -> dict[str, Any]:
        if not 1 <= page_size <= 100:
            raise ValueError("分页大小必须在 1–100 之间。")
        metadata = self.request("thread/read", {"threadId": thread_id})
        thread = metadata.get("thread", {})
        if thread.get("id") != thread_id:
            raise HistoryError("历史接口返回的会话身份不匹配。")
        params = {"threadId": thread_id, "limit": page_size, "sortDirection": "asc"}
        turns = self.pages("thread/turns/list", {**params, "itemsView": "full"})
        if any(turn.get("itemsView") != "full" for turn, _ in turns):
            raise HistoryError("数据源返回摘要或未说明完整性；不能把摘要归档为原文。")
        items = self.pages("thread/items/list", params)
        home = self.identity.get("codexHome")
        if not home:
            raise HistoryError("数据源未提供来源实例身份 codexHome。")
        instance = hashlib.sha256(str(Path(home).resolve()).encode("utf-8")).hexdigest()
        return {"thread": thread, "turns": turns, "items": items,
                "source": {"instance": instance, "version": self.identity.get("userAgent"),
                           "transport": "app-server stdio", "identity": self.identity},
                "evidence": list(self.evidence)}
