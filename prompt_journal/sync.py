"""Local periodic reconciliation. A successful saved snapshot is the progress record."""
from __future__ import annotations

from collections.abc import Callable
import threading
import time
import sys
from typing import Any, BinaryIO

from .app import CapacityReached, Journal
from .source import CodexHistory, HistoryError, now
from .topology import remember_relation_metadata
from .usage import UsageMonitor


class Collector:
    def __init__(self, journal: Journal, source_factory: Callable[[], CodexHistory] = CodexHistory,
                 interval: float = 3, enabled_at: float | None = None, page_size: int = 100):
        if interval <= 0 or not 1 <= page_size <= 100:
            raise ValueError("周期必须大于零，分页大小必须在 1–100 之间。")
        self.journal, self.source_factory = journal, source_factory
        self.interval, self.page_size = interval, page_size
        self.state = journal.collection_state()
        if not self.state:
            if enabled_at is None:
                raise ValueError("首次启用须明确 --start-from-now；不会默认回补旧历史。")
            self.state = {"enabledAt": enabled_at, "lastSuccessAt": None, "sessions": [], "error": None}
            journal.save_collection_state(self.state)
        self.stopping = threading.Event()
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.ownership: BinaryIO | None = None
        self.usage = UsageMonitor(journal.database)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            raise ValueError("采集器已经运行。")
        ownership = open(self.journal.data_dir / "collector.lock", "a+b")
        try:
            ownership.seek(0)
            if ownership.read(1) == b"":
                ownership.write(b"0")
                ownership.flush()
            ownership.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(ownership.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(ownership.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            ownership.close()
            raise ValueError("此数据目录已有采集器运行；请先停止原服务。") from exc
        self.ownership = ownership
        self.stopping.clear()
        self.usage.start()
        self.thread = threading.Thread(target=self._run, name="journal-collector", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stopping.set()
        self.usage.stop()
        if self.thread:
            self.thread.join(timeout=30)

    def status(self) -> dict[str, Any]:
        with self.lock:
            return {**self.state, **self.journal.collection_state(), 'exclusions': self.journal.exclusions(), "running": bool(self.thread and self.thread.is_alive() and not self.stopping.is_set()),
                    "intervalSeconds": self.interval}

    def _publish(self, state: dict[str, Any]) -> None:
        self.journal.save_collection_state(state)
        with self.lock:
            self.state = state

    def _run(self) -> None:
        try:
            self._reconcile()
        finally:
            self.usage.stop()
            if self.ownership:
                self.ownership.close()
                self.ownership = None

    def _reconcile(self) -> None:
        while not self.stopping.is_set():
            try:
                with self.source_factory() as source:
                    while not self.stopping.is_set():
                        started = time.monotonic()
                        metadata = source.discover(self.page_size)
                        try:
                            self.usage.configure(source.instance(), source.identity.get('codexHome'), metadata)
                        except Exception:
                            # Statistics never blocks saving dialogue snapshots.
                            pass
                        relation_metadata = remember_relation_metadata(metadata, source.instance(), self.state.get("relationMetadata", []))
                        saved_sessions = {s["id"]: s for s in self.journal.sessions() if s["source"]["instance"] == source.instance()}
                        results = []
                        last_success = self.state.get("lastSuccessAt")
                        for thread in metadata:
                            if self.stopping.is_set():
                                break
                            try:
                                if self.journal.is_excluded(thread['id'], source.instance()):
                                    continue
                                updated = thread.get("updatedAt")
                                created = thread.get("createdAt")
                                previously_in_scope = bool(saved_sessions.get(thread["id"], {}).get("source", {}).get("scope"))
                                if (isinstance(updated, (int, float)) and updated < self.state["enabledAt"]
                                        and (not isinstance(created, (int, float)) or created < self.state["enabledAt"])
                                        and not previously_in_scope):
                                    results.append({"id": thread["id"], "source": source.instance(), "status": "outsideScope", "error": None})
                                    continue
                                capture = source.capture_since(thread, self.state["enabledAt"], self.page_size)
                                if self.stopping.is_set():
                                    break
                                if capture["turns"]:
                                    saved = self.journal.save_capture(capture)
                                    last_success = now()
                                    results.append({"id": thread["id"], "source": source.instance(), "status": "saved", "savedAt": saved["savedAt"], "error": None})
                                else:
                                    if previously_in_scope:
                                        raise HistoryError("来源本次未返回先前已保存的范围内回合；保留已有记录，内容缺失或不可见，未宣称恢复。")
                                    results.append({"id": thread["id"], "source": source.instance(), "status": "outsideScope", "error": None})
                            except CapacityReached as exc:
                                results.append({"id": thread["id"], "source": source.instance(), "status": "capacityPaused", "error": str(exc)})
                            except Exception as exc:
                                results.append({"id": thread["id"], "source": source.instance(), "status": "error", "error": str(exc)})
                        if self.stopping.is_set():
                            break
                        visible_ids = {t["id"] for t in metadata}
                        for saved_session in saved_sessions.values():
                            if saved_session["id"] not in visible_ids:
                                results.append({"id": saved_session["id"], "source": source.instance(), "status": "missing",
                                    "error": "来源本轮枚举未返回此已保存会话；可能已丢弃或不可见。保留已有记录，未宣称恢复。"})
                        self._publish({**self.state, "sessions": results, "error": None, "sourceAvailable": True,
                            "relationMetadata": relation_metadata,
                            "discoveredCount": len(metadata), "lastCheckedAt": now(), "lastSuccessAt": last_success,
                            "lastSourceSuccessAt": now(),
                            "cycleSeconds": round(time.monotonic() - started, 3)})
                        self.stopping.wait(self.interval)
            except Exception as exc:
                try:
                    self._publish({**self.state, "sourceAvailable": False, "error": str(exc), "lastCheckedAt": now()})
                except Exception as storage_error:
                    with self.lock:
                        self.state = {**self.state, "error": f"{exc}；状态保存失败：{storage_error}"}
                self.stopping.wait(self.interval)
