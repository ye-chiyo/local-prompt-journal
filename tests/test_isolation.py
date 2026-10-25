from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from prompt_journal import CodexHistory, Journal


class IsolationAcceptance(unittest.TestCase):
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
