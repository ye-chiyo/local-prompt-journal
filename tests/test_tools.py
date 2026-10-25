import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen

from prompt_journal import CodexHistory, Journal
from prompt_journal.web import create_server


class ToolEvidenceAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "data"
        with CodexHistory([sys.executable, str(Path(__file__).parent / "fixtures/codex_server.py"), "tools"]) as source:
            Journal(self.data).import_session("sample-session", source, page_size=2)
        self.app = Journal(self.data)
        self.server = create_server(self.app, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def read(self, path):
        with urlopen(self.url + path) as response:
            return response.read().decode("utf-8")

    def test_saved_command_can_be_expanded_and_exported_with_its_original_evidence(self):
        package = json.loads(self.read("/export/sample-session"))
        view = json.loads(self.read("/api/session/sample-session"))
        self.assertEqual(view, package["session"])
        tool = view["tools"][0]
        self.assertEqual((tool["id"], tool["turnId"], tool["arguments"], tool["result"], tool["status"], tool["exitCode"], tool["durationMs"]),
                         ("cmd-ok", "turn-1", {"command": "echo 样本", "cwd": "C:/sample"}, "命令原文\n", "completed", 0, 12))
        node = package
        for part in tool["evidenceRef"][2:].split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        self.assertEqual(node["aggregatedOutput"], "命令原文\n")
        html = self.read("/session/sample-session")
        self.assertIn("工具执行", html)
        self.assertIn("echo 样本", html)
        self.assertIn("命令原文\n", html)
        self.assertLess(html.index("正在核对中文。"), html.index("echo 样本"))
        self.assertLess(html.index("原文已保留。"), html.index("执行过程 ·"))
        self.assertLess(html.index("执行过程 ·"), html.index("echo 样本"))

    def test_parallel_same_arguments_keep_separate_results_and_failure_after_reopen(self):
        view = json.loads(self.read("/api/session/sample-session"))
        calls = {t["id"]: t for t in view["tools"]}
        self.assertEqual(len(calls), 7)
        self.assertEqual(calls["parallel-a"]["arguments"], {"key": "相同"})
        self.assertEqual(calls["parallel-b"]["arguments"], {"key": "相同"})
        self.assertEqual(calls["parallel-a"]["result"], {"content": [{"type": "text", "text": "甲结果"}]})
        self.assertIsNone(calls["parallel-b"]["result"])
        self.assertEqual(calls["parallel-b"]["error"], {"message": "乙失败"})
        self.assertEqual(calls["parallel-b"]["status"], "failed")
        self.assertEqual(calls["parallel-a"]["status"], "completed")
        html = self.read("/session/sample-session")
        failed = html.split('data-tool-id="parallel-b"')[1].split('</details>')[0]
        self.assertIn("执行失败", failed)
        self.assertIn("乙失败", failed)
        self.assertNotIn("甲结果", failed)

    def test_long_truncated_and_missing_results_remain_honest_and_evidence_is_locatable(self):
        package = json.loads(self.read("/export/sample-session"))
        calls = {t["id"]: t for t in package["session"]["tools"]}
        html = self.read("/session/sample-session")
        self.assertEqual(calls["dynamic-long"]["result"], [{"type": "inputText", "text": "长" * 8000 + "末尾原文"}])
        self.assertIn("长" * 8000 + "末尾原文", html)
        self.assertEqual(calls["cmd-cut"]["result"], "已取得前缀\nWarning: truncated output")
        self.assertEqual(calls["cmd-cut"]["completeness"], "unknown")
        self.assertIn("是否实际截断未知", html)
        self.assertEqual((calls["missing"]["turnId"], calls["missing"]["status"], calls["missing"]["result"], calls["missing"]["completedAtMs"]),
                         ("turn-2", "inProgress", None, None))
        self.assertTrue(calls["missing"]["argumentsAvailable"])
        pending = html.split('data-tool-id="missing"')[1].split('</details>')[0]
        self.assertIn("<pre>null</pre>", pending)
        self.assertNotIn("来源未提供请求参数", pending)
        self.assertEqual((calls["output-only"]["arguments"], calls["output-only"]["status"], calls["output-only"]["result"], calls["output-only"]["association"]),
                         (None, "unknown", "独立原文", "standaloneOutput"))
        self.assertFalse(calls["output-only"]["argumentsAvailable"])
        self.assertLess(html.index('id="turn-1"'), html.index('data-tool-id="missing"'))
        self.assertIn("不支持的条目 · futureEvent", html)
        for call in calls.values():
            index = call["evidenceRef"].split("/")[2]
            evidence = json.loads(self.read("/evidence/sample-session/" + index))
            self.assertEqual(evidence["method"], "thread/items/list")
            node = package
            for part in call["evidenceRef"][2:].split("/"):
                node = node[int(part)] if isinstance(node, list) else node[part]
            self.assertEqual(node["id"], call["id"])
            self.assertEqual(call["businessOutcome"], "unknown")
