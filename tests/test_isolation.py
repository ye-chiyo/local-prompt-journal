from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from prompt_journal import CodexHistory, Journal
from prompt_journal.source import resolve_codex_executable


class IsolationAcceptance(unittest.TestCase):
    def test_codex_resolution_falls_back_to_desktop_bundle_when_path_is_stale(self):
        with patch.dict(os.environ, {"PATH": "", "LOCALAPPDATA": r"C:\Users\614\AppData\Local"}, clear=False):
            with patch("prompt_journal.source.os.name", "nt"):
                with patch("prompt_journal.source.Path.glob") as glob:
                    candidate = Path(r"C:\Users\614\AppData\Local\OpenAI\Codex\bin\fixture\codex.exe")
                    glob.return_value = [candidate]
                    with patch.object(Path, "is_file", return_value=True), patch.object(Path, "stat") as stat:
                        stat.return_value.st_mtime = 1
                        self.assertEqual(resolve_codex_executable(), str(candidate))

    def test_external_history_process_cannot_use_inherited_forward_proxy(self):
        class Proxy(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"unexpected egress")

            def log_message(self, *args):
                pass

        proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        try:
            address = f"http://127.0.0.1:{proxy.server_port}"
            environment = {name: address for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")}
            environment.update({"NO_PROXY": "", "no_proxy": ""})
            with patch.dict(os.environ, environment), tempfile.TemporaryDirectory() as temp:
                with CodexHistory([sys.executable, str(Path(__file__).parent / "fixtures" / "codex_server.py"), "network"]) as source:
                    view = Journal(temp).import_session("sample-session", source, page_size=1)
                self.assertEqual(view["source"]["identity"]["networkProbe"], "blocked")
        finally:
            proxy.shutdown()
            proxy.server_close()
            thread.join(timeout=2)
