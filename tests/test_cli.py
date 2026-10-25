import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CommandLineAcceptance(unittest.TestCase):
    def test_new_process_can_query_and_export_a_saved_session(self):
        from prompt_journal import Journal, CodexHistory
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            with CodexHistory([sys.executable, str(Path(__file__).parent / "fixtures" / "codex_server.py")]) as source:
                Journal(data).import_session("sample-session", source, page_size=1)
            command = [sys.executable, "-m", "prompt_journal", "--data-dir", str(data)]
            result = subprocess.run(command + ["show", "sample-session"], capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["messages"][0]["text"], "请记录原文。")
            destination = Path(temp) / "offline" / "sample.json"
            result = subprocess.run(command + ["export", "sample-session", "--output", str(destination)], capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["session"]["messages"][2]["text"], "原文已保留。")

    def test_unknown_session_produces_explicit_failure_instead_of_an_empty_success(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, "-m", "prompt_journal", "--data-dir", temp, "show", "missing"], capture_output=True, encoding="utf-8")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("未保存", result.stderr)
