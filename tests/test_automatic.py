import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from prompt_journal import Journal, CodexHistory
from prompt_journal.sync import Collector


def sample(identity, cwd, created, text):
    return {"thread": {"id": identity, "name": "同名会话", "cwd": cwd, "createdAt": created, "updatedAt": 200},
            "turns": [{"id": "t1", "startedAt": 200, "status": "inProgress", "items": [
                {"id": "u1", "type": "userMessage", "content": [{"type": "text", "text": text}]}]}]}


class AutomaticArchiveAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state_path = Path(self.temp.name) / "source.json"
        self.state = {"sessions": [sample("A", "C:/甲", 100, "相同提示"), sample("B", "C:/甲", 160, "乙会话原文"), sample("C", "D:/乙", 100, "跨项目原文")]}
        self.publish()
        self.app = Journal(Path(self.temp.name) / "archive")

    def publish(self):
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.state_path)

    def start(self):
        collector = Collector(self.app, source_factory=lambda: CodexHistory([
            sys.executable, str(Path(__file__).parent / "fixtures" / "automatic_source.py"), str(self.state_path)]),
            interval=0.08, enabled_at=190, page_size=1)
        collector.start()
        self.addCleanup(collector.stop)
        return collector

    def await_view(self, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.03)
        self.fail("公开归档视图未在期限内取得预期结果")

    def test_multiple_projects_discovered_and_updates_keep_whole_sessions_in_start_order(self):
        collector = self.start()
        self.await_view(lambda: len(self.app.sessions()) == 3)
        projects = self.app.projects()
        self.assertEqual([s["id"] for s in projects[0]["sessions"]], ["A", "B"])
        self.assertEqual([s["id"] for s in projects[1]["sessions"]], ["C"])
        self.assertEqual(self.app.session("C")["messages"][0]["text"], "跨项目原文")
        self.state["sessions"].append(sample("D", "E:/丙", 170, "新项目原文"))
        self.state["sessions"][0]["turns"][0]["items"].append({"id": "u2", "type": "userMessage", "content": [{"type": "text", "text": "相同提示"}]})
        self.publish()
        self.await_view(lambda: len(self.app.sessions()) == 4 and len(self.app.session("A")["messages"]) == 2)
        self.assertEqual([m["id"] for m in self.app.session("A")["messages"]], ["u1", "u2"])
        self.assertEqual([s["id"] for s in self.app.projects()[0]["sessions"]], ["A", "B"])
        self.state["sessions"].extend([sample("E", "C:/甲", 100, "同时间原文"), sample("F", "C:/甲", None, "未知开始时间原文")])
        self.publish()
        self.await_view(lambda: len(self.app.sessions()) == 6)
        self.assertEqual([s["id"] for s in self.app.projects()[0]["sessions"]], ["A", "E", "B", "F"])
        self.assertIsNone(self.app.session("F")["createdAt"])
        collector.stop()
        self.assertEqual(len(Journal(self.app.data_dir).session("A")["messages"]), 2)

    def test_tool_revisions_failures_and_restart_recover_without_losing_original_evidence(self):
        tool = {"id": "k", "type": "commandExecution", "command": "sample only", "cwd": "C:/甲",
                "commandActions": [], "status": "inProgress", "aggregatedOutput": None, "exitCode": None}
        self.state["sessions"][0]["turns"][0]["items"].append(tool)
        self.state["sessions"][0]["turns"][0]["items"].append({"id": "future", "type": "futureEvent", "payload": "原始前缀"})
        self.publish()
        collector = self.start()
        self.await_view(lambda: len(self.app.sessions()) == 3)
        self.assertEqual(self.app.session("A")["tools"][0]["status"], "inProgress")
        tool.update(status="completed", aggregatedOutput="完成原文", exitCode=0)
        self.state["sessions"][1]["fail"] = True
        self.publish()
        self.await_view(lambda: self.app.session("A")["tools"][0]["status"] == "completed" and any(s.get("error") for s in collector.status()["sessions"]))
        package = json.loads(self.app.export_session("A"))
        self.assertEqual(package["session"]["tools"][0]["result"], "完成原文")
        self.assertEqual(package["revisions"][0]["session"]["tools"][0]["status"], "inProgress")
        node = package
        for part in package["revisions"][0]["session"]["tools"][0]["evidenceRef"].removeprefix("#/").split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        self.assertEqual(node["status"], "inProgress")
        self.state["sessions"][0]["turns"][0]["items"][-1]["payload"] = "补全后的原始载荷"
        self.state["sessions"][2]["turns"] = []
        self.publish()
        def payload_completed():
            package = json.loads(self.app.export_session("A"))
            return any(e.get("response", {}).get("result", {}).get("data", [{}])[-1].get("item", {}).get("payload") == "补全后的原始载荷" for e in package["evidence"] if e.get("response", {}).get("result", {}).get("data"))
        self.await_view(lambda: payload_completed() and any(s["id"] == "C" and s.get("error") for s in collector.status()["sessions"]))
        self.assertEqual(self.app.session("C")["messages"][0]["text"], "跨项目原文")
        self.state["sessions"][2]["turns"] = sample("C", "D:/乙", 100, "跨项目原文")["turns"]
        self.state["unavailable"] = True
        self.publish()
        self.await_view(lambda: collector.status().get("sourceAvailable") is False)
        self.assertTrue(collector.status()["error"])
        self.assertEqual(self.app.session("C")["messages"][0]["text"], "跨项目原文")
        collector.stop()
        self.state["unavailable"] = False
        self.state["sessions"][1]["fail"] = False
        self.state["sessions"][0]["turns"].append({"id": "t2", "startedAt": 210, "status": "completed", "items": [
            {"id": "recovered", "type": "agentMessage", "phase": "final_answer", "text": "停机期间原文"}]})
        self.publish()
        restarted = self.start()
        self.await_view(lambda: len(self.app.session("A")["messages"]) == 2 and all(not s.get("error") for s in restarted.status()["sessions"]))
        self.assertEqual([m["text"] for m in Journal(self.app.data_dir).session("A")["messages"]], ["相同提示", "停机期间原文"])

    def test_first_scope_skips_old_bodies_and_preserves_previously_saved_authorized_history(self):
        self.state["sessions"] = [sample("A", "C:/甲", 100, "已有授权原文")]
        del self.state["sessions"][0]["turns"][0]["startedAt"]
        self.publish()
        # Previously authorized save is a fact separate from the new automatic cutoff.
        with CodexHistory([sys.executable, str(Path(__file__).parent / "fixtures" / "automatic_source.py"), str(self.state_path)]) as source:
            self.app.import_session("A", source)
        self.state["forbidBodyBefore"] = 190
        self.state["sessions"][0]["turns"][0]["startedAt"] = 180
        self.publish()
        collector = self.start()
        self.await_view(lambda: collector.status().get("sourceAvailable") is True)
        self.assertEqual(collector.status()["sessions"][0]["status"], "outsideScope")
        self.state["sessions"][0]["turns"].append({"id": "new-turn", "startedAt": 210, "status": "completed", "items": [
            {"id": "new", "type": "userMessage", "content": [{"type": "text", "text": "启用后原文"}]}]})
        self.publish()
        self.await_view(lambda: any(m["text"] == "启用后原文" for s in self.app.sessions() for m in self.app.session(s["id"], s["source"]["instance"])["messages"]))
        self.assertEqual([m["text"] for m in self.app.session("A")["messages"]], ["已有授权原文", "启用后原文"])
        self.state["sessions"][0]["turns"].append({"id": "next-turn", "startedAt": 220, "status": "completed", "items": [
            {"id": "next", "type": "userMessage", "content": [{"type": "text", "text": "再次更新原文"}]}]})
        self.publish()
        self.await_view(lambda: len(self.app.session("A")["messages"]) == 3)
        self.assertEqual([m["text"] for m in self.app.session("A")["messages"]], ["已有授权原文", "启用后原文", "再次更新原文"])
