import json
import sqlite3
import re
from html import unescape
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from prompt_journal import Journal, CodexHistory
from prompt_journal.web import create_server
from tests.fixtures.catalog_facts import catalog_capture


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
        with urlopen(self.url + "/session/sample-session/turn/turn-1") as response:
            html = response.read().decode()
            self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
        for text in ("请记录原文。", "AI 过程消息", "AI 最终回答", 'href="/status"'):
            self.assertIn(text, html)
        self.assertNotIn("应用自带 SQLite 数据库", html)
        self.assertNotIn("首次启用：", html)
        self.assertNotIn("选择导出范围", html)
        self.assertNotIn('href="/export/', html)
        self.assertNotIn("<script>不会执行历史代码</script>", html)
        with urlopen(self.url + '/session/sample-session/turn/turn-2') as response:
            second_html = response.read().decode()
        for text in ('&lt;script&gt;不会执行历史代码&lt;/script&gt;', '阶段未知', '附件未取得'):
            self.assertIn(text, second_html)
        self.assertNotIn('<script>不会执行历史代码</script>', second_html)
        self.assertNotIn('数据库文件', html)
        self.assertNotIn('aria-label="回合索引"', html)
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

    def test_project_page_lists_sessions_without_rendering_each_full_timeline(self):
        project_id = self.app.projects()[0]["id"]
        with urlopen(self.url + "/project/" + project_id) as response:
            html = response.read().decode()
        self.assertIn("中文验收样本", html)
        self.assertIn('/session/sample-session/turn/turn-1?source=', html)
        self.assertNotIn("请记录原文。", html)
        self.assertNotIn("正在核对中文。", html)
        self.assertNotIn('数据库文件', html)
        self.assertNotIn('aria-label="搜索已保存正文"', html)
        self.assertNotIn("来源实例：", html)
        self.assertNotIn("以下按来源会话开始时间升序排列", html)

    def test_project_directory_and_automatic_polling_work_without_reading_snapshot_bodies(self):
        project_id = self.app.projects()[0]["id"]
        connect = sqlite3.connect

        def metadata_only(*args, **kwargs):
            db = connect(*args, **kwargs)
            db.set_authorizer(lambda action, table, column, database, trigger:
                sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "snapshots" and column == "package"
                else sqlite3.SQLITE_OK)
            return db

        with patch("sqlite3.connect", side_effect=metadata_only):
            for route in ("/project/" + project_id, "/api/version", "/"):
                with self.subTest(route=route), urlopen(self.url + route) as response:
                    self.assertEqual(response.status, 200)

    def test_project_directory_pages_in_start_order_and_returns_from_detail_to_same_page(self):
        for i, created in enumerate((None, 100, 100, 200, 300, 400, 500)):
            saved = self.app.save_capture(catalog_capture("catalog-" + str(i), created))
        project_id = saved["project"]["id"]
        route = "/project/" + project_id + "?offset=0&limit=2"
        with urlopen(self.url + route) as response:
            html = response.read().decode()
        self.assertIn("共 7 个回合", html)
        self.assertIn("目录会话-catalog-1", html)
        self.assertIn("目录会话-catalog-2", html)
        for hidden in ("目录会话-catalog-0", "目录会话-catalog-3", "目录不应加载的正文", "工具最终结果"):
            self.assertNotIn(hidden, html)
        self.assertIn("offset=2&amp;limit=2", html)
        href = unescape(re.search(r'href="([^"]*/session/catalog-1[^\"]*)"', html).group(1))
        with urlopen(self.url + href) as response:
            detail = response.read().decode()
        self.assertIn("目录不应加载的正文", detail)
        self.assertIn("工具最终结果", detail)
        self.assertIn('href="' + route.replace("&", "&amp;") + '">返回目录', detail)
        with urlopen(self.url + "/project/" + project_id + "?offset=6&limit=2") as response:
            self.assertIn("目录会话-catalog-0", response.read().decode())
        for params in ("offset=-1", "limit=0", "limit=101", "offset=oops"):
            with self.subTest(params=params), self.assertRaises(HTTPError) as error:
                urlopen(self.url + "/project/" + project_id + "?" + params)
            self.assertEqual(error.exception.code, 400)

    def test_detail_shows_final_tool_result_once_without_intermediate_observations(self):
        capture = catalog_capture()
        capture['turns'][0][0]['items'][1].update(status='inProgress', exitCode=None, aggregatedOutput='中间轮询输出')
        capture['items'][1][0]['item'].update(status='inProgress', exitCode=None, aggregatedOutput='中间轮询输出')
        self.app.save_capture(capture)
        self.app.save_capture(catalog_capture())
        with urlopen(self.url + '/session/catalog-1/turn/turn?source=catalog-fixture') as response:
            html = response.read().decode()
        self.assertNotIn('中间轮询输出', html)
        self.assertEqual(html.count('工具最终结果'), 1)
        self.assertIn('fixture-command', html)
        exported = json.loads(self.app.export_session('catalog-1', 'catalog-fixture'))
        self.assertEqual(exported['revisions'][0]['session']['tools'][0]['result'], '中间轮询输出')

    def test_search_page_keeps_status_separate_from_search_results(self):
        with urlopen(self.url + "/search?q=%E8%AF%B7%E8%AE%B0%E5%BD%95") as response:
            html = response.read().decode()
        self.assertIn('href="/status"', html)
        self.assertNotIn('数据库文件', html)
        self.assertIn('请记录原文。', html)

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
        with urlopen(self.url + "/session/large-session/turn/large-turn?source=large-fixture") as response:
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
