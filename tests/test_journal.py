import json
from pathlib import Path
import sys
import tempfile
import unittest

from prompt_journal import Journal, CodexHistory, HistoryError


class SingleSessionAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "journal"

    def source(self, mode="normal"):
        return CodexHistory([sys.executable, str(Path(__file__).parent / "fixtures" / "codex_server.py"), mode])

    def test_user_can_import_reopen_and_export_original_messages_with_evidence(self):
        with self.source() as source:
            Journal(self.data).import_session("sample-session", source, page_size=1)
        # New app instance reads persistent data with the external source closed.
        app = Journal(self.data)
        view = app.session("sample-session")
        self.assertEqual([m["text"] for m in view["messages"]], ["请记录原文。", "正在核对中文。", "原文已保留。"])
        self.assertEqual([m["phase"] for m in view["messages"]], [None, "commentary", "final_answer"])
        exported = json.loads(app.export_session("sample-session"))
        self.assertEqual(exported["session"]["source"]["version"], "Controlled Codex/fixture-1")
        for message in exported["session"]["messages"]:
            node = exported
            for part in message["evidenceRef"].removeprefix("#/").split("/"):
                node = node[int(part)] if isinstance(node, list) else node[part]
            self.assertEqual(node["id"], message["id"])
        self.assertEqual(exported["session"]["turns"][0]["status"], "completed")
        self.assertTrue(exported["session"]["source"]["gaps"])

    def test_repeated_prompts_unknown_phase_and_unbacked_attachment_remain_distinct(self):
        for _ in range(2):
            with self.source("complex") as source:
                Journal(self.data).import_session("sample-session", source, page_size=1)
        view = Journal(self.data).session("sample-session")
        self.assertEqual(len(view["messages"]), 5)
        self.assertEqual([m["id"] for m in view["messages"] if m["text"] == "请记录原文。"], ["user-1", "user-2"])
        self.assertEqual(view["messages"][3]["completeness"], "partial")
        self.assertEqual(view["messages"][4]["completeness"], "unknown")
        self.assertIsNone(view["messages"][4]["phase"])
        self.assertEqual(view["turns"][1]["status"], "interrupted")
        self.assertEqual(view["source"]["notDisplayedTypes"], ["futureEvent"])
        self.assertEqual(len(Journal(self.data).sessions()), 1)

    def test_rejects_summary_and_cursor_loop_without_publishing_an_archive(self):
        for mode in ("summary", "loop"):
            with self.subTest(mode=mode), self.source(mode) as source:
                with self.assertRaises(HistoryError):
                    Journal(self.data).import_session("sample-session", source, page_size=1)
                self.assertEqual(Journal(self.data).sessions(), [])

    def test_overlapping_pages_do_not_duplicate_messages(self):
        with self.source("overlap") as source:
            view = Journal(self.data).import_session("sample-session", source, page_size=1)
        self.assertEqual([m["id"] for m in view["messages"]], ["user-1", "ai-1", "ai-2"])


if __name__ == "__main__":
    unittest.main()
