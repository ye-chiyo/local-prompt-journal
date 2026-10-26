import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode
from urllib.request import urlopen

from prompt_journal import Journal, CodexHistory
from prompt_journal.sync import Collector
from prompt_journal.web import create_server
from tests.fixtures.search_facts import search_source


class SavedSearchAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "source.json"
        self.state = search_source()
        self.publish()
        self.app = Journal(self.root / "data")
        self.command = [sys.executable, str(Path(__file__).parent / "fixtures" / "automatic_source.py"), str(self.path)]
        with CodexHistory(self.command) as source:
            for identity in ("search-main", "search-other", "search-child"):
                self.app.import_session(identity, source)
        self.server = create_server(self.app, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def publish(self):
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)

    def search(self, query, **scope):
        with urlopen(self.url + "/api/search?" + urlencode({"q": query, **scope})) as response:
            return json.load(response)

    def test_saved_bodies_scope_literal_matching_and_versioned_evidence(self):
        def identities(query, **scope):
            return [(r["threadId"], r["turnId"], r["id"], r["field"]) for r in self.search(query, **scope)["results"]]
        self.assertEqual(identities("雨巷纸伞"), [("search-main", "search-turn", "prompt-a", "text"),
            ("search-main", "search-turn", "prompt-b", "text"), ("search-other", "other-turn", "other-prompt", "text")])
        for query, identity, field in (("青瓷回声", "thinking", "text"), ("晚霞书签", "answer", "text"),
                                       ("远山灯塔", "long-tool", "result"), ("校验雪松失败", "error-tool", "error")):
            self.assertEqual(identities(query), [("search-main", "search-turn", identity, field)])
        self.assertEqual(len(identities("SQLite 中文归档")), 2)
        for query in ("sqlite 中文归档", "SQLite  中文归档", "未保存的星际菠萝", "100%任意字面", "   "):
            self.assertEqual(identities(query), [])
        self.assertEqual(len(identities("100%_字面*")), 2)
        project = self.app.session("search-main")["project"]["id"]
        self.assertEqual(len(identities("雨巷纸伞", project=project)), 2)
        self.assertEqual(identities("雨巷纸伞", session="search-other"), [("search-other", "other-turn", "other-prompt", "text")])
        self.assertEqual(identities("子会话独有梧桐", session="search-main"), [])
        long = self.search("远山灯塔")["results"][0]
        self.assertIn("远山灯塔", long["snippet"])
        self.assertEqual(long["completeness"], "partial")
        self.assertIn("截断", "".join(long["reasons"]))
        with urlopen(self.url + long["evidenceUrl"]) as response:
            raw = json.load(response)
        self.assertEqual(raw["response"]["result"]["data"][4]["item"]["id"], "long-tool")
        self.assertEqual(raw["response"]["result"]["data"][4]["turnId"], "search-turn")
        self.state["codexHome"] = "second-source"
        self.publish()
        with CodexHistory(self.command) as source:
            self.app.import_session("search-main", source)
            second_instance = source.instance()
        self.assertEqual(len(identities("雨巷纸伞", session="search-main", source=second_instance)), 2)
        page = self.search("雨巷纸伞", limit=2)
        self.assertEqual(page["total"], 5)
        self.assertEqual(page["nextOffset"], 2)
        self.assertEqual(len(self.search("雨巷纸伞", limit=2, offset=2)["results"]), 2)
        self.assertEqual(len(Journal(self.root / "data").search("远山灯塔")["results"]), 2)

    def test_automatic_new_text_and_tool_revision_replace_search_view_but_keep_old_hit(self):
        old_hit = self.search("旧版沙洲")["results"][0]
        collector = Collector(self.app, source_factory=lambda: CodexHistory(self.command), interval=0.08, enabled_at=190)
        collector.start()
        self.addCleanup(collector.stop)
        items = self.state["sessions"][0]["turns"][0]["items"]
        items[6].update(status="completed", contentItems=[{"type": "inputText", "text": "新版渡口"}])
        items.append({"id": "auto-prompt", "type": "userMessage", "content": [{"type": "text", "text": "自动入库竹影"}]})
        self.publish()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not self.search("自动入库竹影")["results"]:
            time.sleep(0.04)
        self.assertEqual([(r["threadId"], r["id"]) for r in self.search("自动入库竹影")["results"]], [("search-main", "auto-prompt")])
        self.assertEqual([r["id"] for r in self.search("新版渡口")["results"]], ["changing-tool"])
        self.assertEqual(self.search("旧版沙洲")["results"], [])
        with urlopen(self.url + old_hit["url"]) as response:
            html = response.read().decode()
        self.assertIn("旧版沙洲", html)
        self.assertNotIn("新版渡口", html)
        self.assertIn("命中时的保存版本", html)
        with urlopen(self.url + old_hit["evidenceUrl"]) as response:
            evidence = json.load(response)
        raw = evidence["response"]["result"]["data"][6]
        self.assertEqual((raw["turnId"], raw["item"]["id"]), ("search-turn", "changing-tool"))
        self.assertEqual(raw["item"]["contentItems"], [{"type": "inputText", "text": "旧版沙洲"}])
        collector.stop()
        reopened = Journal(self.root / "data")
        self.assertEqual([r["id"] for r in reopened.search("新版渡口")["results"]], ["changing-tool"])
