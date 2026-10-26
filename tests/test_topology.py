import json
from pathlib import Path
import sys
import tempfile
import unittest

from prompt_journal import Journal, CodexHistory
from tests.fixtures.topology_facts import facts
from prompt_journal.sync import Collector
import time
import threading
from urllib.request import urlopen
from prompt_journal.web import create_server


class TopologyAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "archive"
        self.path = Path(self.temp.name) / "source.json"
        self.state = facts()
        self.app = Journal(self.data)

    def capture(self, *ids):
        self.path.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        with CodexHistory([sys.executable, str(Path(__file__).parent / "fixtures/automatic_source.py"), str(self.path)]) as source:
            for identity in ids:
                self.app.import_session(identity, source, page_size=2)

    def test_saved_executions_keep_identity_exit_unknown_and_old_running_evidence(self):
        self.capture("main", "child")
        view = self.app.session("main")
        executions = {e["id"]: e for e in view["executions"]}
        self.assertEqual(set(executions), {"ok", "fail", "unknown", "running"})
        self.assertEqual((executions["running"]["state"], executions["running"]["outcome"]), ("running", "unknown"))
        self.assertEqual((executions["ok"]["state"], executions["ok"]["outcome"]), ("running", "unknown"))
        self.assertEqual((executions["fail"]["state"], executions["fail"]["exitCode"]), ("exited", 9))
        self.assertEqual(executions["unknown"]["outcome"], "unknown")
        self.assertEqual(view["tools"][2]["status"], "unknown")
        self.assertEqual(executions["unknown"]["turnId"], "t2")
        main = next(s for s in self.state["sessions"] if s["thread"]["id"] == "main")
        main["turns"][0]["items"][1].update(status="completed", exitCode=0, aggregatedOutput="启动原文\n结束原文")
        self.capture("main")
        self.capture("main")  # Re-reading is not a new execution or output chunk.
        self.app = Journal(self.data)
        execution = self.app.session("main")["executions"][0]
        self.assertEqual((execution["state"], execution["outcome"], execution["exitCode"]), ("exited", "success", 0))
        self.assertEqual([o["output"] for o in execution["observations"]], ["启动原文", "启动原文\n结束原文"])
        self.assertEqual(self.app.session("child")["executions"][0]["exitCode"], 4)
        package = json.loads(self.app.export_session("main"))
        for observation in package["session"]["executions"][0]["observations"]:
            node = package
            for part in observation["evidenceRef"][2:].split("/"):
                node = node[int(part)] if isinstance(node, list) else node[part]
            self.assertEqual(node["aggregatedOutput"], observation["output"])

    def test_automatic_relations_keep_session_boundaries_and_do_not_fetch_missing_targets(self):
        self.path.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        collector = Collector(self.app, source_factory=lambda: CodexHistory([
            sys.executable, str(Path(__file__).parent / "fixtures/automatic_source.py"), str(self.path)]),
            enabled_at=190, interval=0.08)
        collector.start()
        self.addCleanup(collector.stop)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if len(self.app.sessions()) == 4 and any(s.get("error") for s in collector.status().get("sessions", [])):
                break
            time.sleep(0.03)
        collector.stop()
        self.app = Journal(self.data)
        main = self.app.session("main")
        relations = main["relations"]
        self.assertTrue(any(r["type"] == "subAgent" and r["targetId"] == "child" and r["availability"] == "archived" for r in relations))
        self.assertTrue(any(r["type"] == "fork" and r["targetId"] == "fork" for r in relations))
        self.assertTrue(any(r["targetId"] == "missing" and r["availability"] == "notArchived" for r in relations))
        self.assertTrue(any(r["targetId"] == "blocked" and r["availability"] == "unavailable" for r in relations))
        self.assertTrue(any(r["targetId"] is None and "agentThreadId" in r["reason"] for r in relations))
        self.assertTrue(any(r["type"] == "unknown" and "tool" in r["reason"] for r in relations))
        self.assertTrue(any(r["type"] == "subAgent" and r["targetId"] == "old-child" and r["availability"] == "notArchived" for r in relations))
        self.assertTrue(any(r["type"] == "fork" and r["targetId"] == "old-fork" and r["availability"] == "notArchived" for r in relations))
        exported = json.loads(self.app.export_session("main", include_related=True))
        metadata_relation = next(r for r in exported["session"]["relations"] if r["targetId"] == "old-child")
        node = exported
        for part in metadata_relation["evidenceRef"][2:].split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        self.assertEqual(node["parentThreadId"], "main")
        self.assertNotIn("禁止补读的旧子会话正文", json.dumps(exported, ensure_ascii=False))
        self.assertTrue(any(r["targetId"] == "old-fork" for r in exported["exportScope"]["omitted"]))
        self.assertEqual([m["text"] for m in main["messages"]], ["主会话原文"])
        child = self.app.session("child")
        self.assertEqual((child["project"]["label"], child["messages"][0]["text"]), ("D:/子项目", "子会话原文"))
        self.assertTrue(any(r["targetId"] == "main" and r["direction"] == "incoming" for r in child["relations"]))
        self.assertEqual(len(self.app.sessions()), 4)

    def test_public_export_explicitly_includes_one_hop_with_locatable_evidence(self):
        self.capture("child", "fork", "grandchild", "main")
        server = create_server(Journal(self.data), port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def read(path):
                with urlopen(f"http://127.0.0.1:{server.server_port}" + path) as response:
                    return json.load(response)
            single = read("/export/main")
            self.assertNotIn("related", single)
            self.assertEqual(single["exportScope"]["mode"], "single")
            included = read("/export/main?related=1")
            self.assertEqual({p["session"]["id"] for p in included["related"]}, {"child", "fork"})
            self.assertEqual([m["text"] for m in included["session"]["messages"]], ["主会话原文"])
            self.assertTrue(any(r["targetId"] == "grandchild" and r["reason"] == "beyondOneHop" for r in included["exportScope"]["omitted"]))
            self.assertTrue(any(r["targetId"] == "missing" and r["reason"] == "notArchived" for r in included["exportScope"]["omitted"]))
            for package in [included] + included["related"]:
                for relation in package["session"]["relations"]:
                    if relation["evidenceRef"] is not None:
                        node = included
                        for part in relation["evidenceRef"][2:].split("/"):
                            node = node[int(part)] if isinstance(node, list) else node[part]
                        self.assertIsInstance(node, dict)
            self.assertEqual(read("/api/session/main"), single["session"])
            self.assertEqual(len(self.app.sessions()), 4)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
