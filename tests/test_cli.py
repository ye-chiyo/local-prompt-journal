import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CommandLineAcceptance(unittest.TestCase):
    def test_release_tools_reject_source_output_before_creating_any_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = Path(__file__).resolve().parent.parent
            tool_repo, selected_repo = root / 'tool-repo', root / 'selected-repo'
            shutil.copytree(repository / 'tools', tool_repo / 'tools', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(repository / 'prompt_journal', selected_repo / 'prompt_journal', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(repository / 'tests' / 'fixtures', selected_repo / 'tests' / 'fixtures', ignore=shutil.ignore_patterns('__pycache__'))
            entries = [('verify_release_flow.py', []), ('measure_release_performance.py', ['--repeats', '0']),
                       ('measure_release_performance.py', ['--condition', 'disabled', '--turns', '1'])]
            for index, (script, flags) in enumerate(entries):
                for output_repo in (selected_repo, tool_repo):
                    destination = output_repo / ('must-not-be-created-' + str(index))
                    with self.subTest(script=script, flags=flags, output_repo=output_repo.name):
                        result = subprocess.run([sys.executable, '-X', 'utf8', str(tool_repo / 'tools' / script),
                            '--repo', str(selected_repo), '--output', str(destination), *flags],
                            capture_output=True, encoding='utf-8')
                        self.assertFalse(destination.exists(), 'Rejected output must never be created')
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('outside', result.stderr)

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
