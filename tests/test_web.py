import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
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
