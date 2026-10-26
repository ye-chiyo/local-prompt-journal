import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from prompt_journal import Journal, CodexHistory
from prompt_journal.web import create_server


class LocalInterfaceAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Journal(Path(self.temp.name) / "data")
        with CodexHistory([sys.executable, str(Path(__file__).parent / "fixtures" / "codex_server.py"), "complex"]) as source:
            self.app.import_session("sample-session", source, page_size=1)
        self.server = create_server(self.app, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_timeline_shows_local_database_saved_state_and_safe_evidence_links(self):
        with urlopen(self.url + "/session/sample-session") as response:
            html = response.read().decode()
            self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
        for text in ("请记录原文。", "AI 过程消息", "AI 最终回答", "阶段未知", "附件未取得", "fixture-1", "自动保存到本机数据库", "本会话已入库", str(self.app.database)):
            self.assertIn(text, html)
        self.assertNotIn("选择导出范围", html)
        self.assertNotIn('href="/export/', html)
        self.assertNotIn("<script>不会执行历史代码</script>", html)
        self.assertIn("&lt;script&gt;不会执行历史代码&lt;/script&gt;", html)
        with urlopen(self.url + "/api/session/sample-session") as response:
            view = json.load(response)
        with urlopen(self.url + "/export/sample-session") as response:
            exported = json.load(response)
            self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(view, exported["session"])
        self.assertEqual(len(view["messages"]), 5)
        with urlopen(self.url + "/evidence/sample-session/0") as response:
            self.assertEqual(json.load(response)["method"], "initialize")

    def test_browser_access_is_limited_to_local_origin_and_unknown_routes_are_errors(self):
        for headers in ({"Host": "untrusted.example"}, {"Origin": "https://remote.example"}):
            with self.subTest(headers=headers), self.assertRaises(HTTPError) as error:
                urlopen(Request(self.url + "/api/sessions", headers=headers))
            self.assertEqual(error.exception.code, 403)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + "/session/missing")
        self.assertEqual(error.exception.code, 404)

    def test_large_message_is_loaded_on_expand_without_initial_html(self):
        large = "大文本原文-" + ("x" * 70_000)
        tool_large = "工具结果原文-" + ("y" * 70_000)
        structured_large = "结构化结果-" + ("z" * 70_000)
        items = [
            {"type": "userMessage", "id": "large-user", "content": [{"type": "text", "text": large}]},
            {"type": "agentMessage", "id": "small-answer", "phase": "final_answer", "text": "小消息仍直接显示。"},
            {"type": "commandExecution", "id": "large-tool", "command": "dump", "cwd": "C:/fixture", "status": "completed", "exitCode": 0, "aggregatedOutput": tool_large},
            {"type": "mcpToolCall", "id": "structured-tool", "server": "fixture", "tool": "structured", "arguments": {}, "status": "completed", "result": {"content": [{"type": "text", "text": structured_large}]}, "error": None},
        ]
        evidence_items = [{"turnId": "large-turn", "item": item, "startedAtMs": 100_000, "completedAtMs": 101_000} for item in items]
        capture = {
            "thread": {"id": "large-session", "name": "大文本样本", "createdAt": 100},
            "turns": [({"id": "large-turn", "status": "completed", "startedAt": 100, "items": items}, "#/evidence/0/response/result/data/0")],
            "items": [(entry, f"#/evidence/0/response/result/data/{index}") for index, entry in enumerate(evidence_items)],
            "evidence": [{"method": "thread/items/list", "params": {}, "response": {"result": {"data": evidence_items}}}],
            "source": {"instance": "large-fixture", "version": "fixture", "gaps": [], "pagination": {"turnPages": 1, "itemPages": 1}, "notDisplayedTypes": []},
        }
        first_saved = self.app.save_capture(capture)
        with urlopen(self.url + "/session/large-session?source=large-fixture") as response:
            html = response.read().decode()
        self.assertIn("原文较大，展开后加载完整内容。", html)
        self.assertNotIn(large, html)
        self.assertNotIn(tool_large, html)
        self.assertNotIn(structured_large, html)
        with urlopen(self.url + "/api/session/large-session/item/large-user?source=large-fixture&kind=message&field=text") as response:
            payload = json.load(response)
        self.assertEqual(payload["text"], large)
        with urlopen(self.url + "/api/session/large-session/item/large-tool?source=large-fixture&kind=tool&field=result") as response:
            tool_payload = json.load(response)
        self.assertEqual(tool_payload["text"], tool_large)
        with urlopen(self.url + "/api/session/large-session/item/large-tool?source=large-fixture&kind=execution&field=output&observation=0") as response:
            execution_payload = json.load(response)
        self.assertEqual(execution_payload["text"], tool_large)
        with urlopen(self.url + "/api/session/large-session/item/structured-tool?source=large-fixture&kind=tool&field=resultText&textIndex=0") as response:
            structured_payload = json.load(response)
        self.assertEqual(structured_payload["text"], structured_large)
        newer_large = "新版本原文-" + ("n" * 70_000)
        items[0]["content"][0]["text"] = newer_large
        self.app.save_capture(capture)
        with urlopen(self.url + "/api/session/large-session/item/large-user?source=large-fixture&kind=message&field=text&saved=" + quote(first_saved["savedAt"], safe="")) as response:
            old_payload = json.load(response)
        self.assertEqual(old_payload["text"], large)
        self.assertIn("小消息仍直接显示。", html)
