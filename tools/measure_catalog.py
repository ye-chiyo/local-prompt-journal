"""Measure local HTTP catalog responses without recording conversation bodies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import threading
import time
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prompt_journal import Journal
from prompt_journal.web import create_server
from release_paths import external_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()
    output = external_output(args.output, Path(__file__).resolve().parent.parent)
    started = time.perf_counter()
    app = Journal(args.data_dir)
    startup = (time.perf_counter() - started) * 1000
    project = max(app.projects(), key=lambda p: len(p["sessions"]))
    server = create_server(app, port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    reports = {}
    try:
        for route in ("/project/" + project["id"], "/api/version"):
            samples = []
            for index in range(1 + 3 + args.repeats):
                begin = time.perf_counter()
                with urlopen(f"http://127.0.0.1:{server.server_port}" + route, timeout=120) as response:
                    first_byte = time.perf_counter()
                    body = response.read()
                samples.append({"ttfbMs": (first_byte - begin) * 1000,
                                "totalMs": (time.perf_counter() - begin) * 1000,
                                "bytes": len(body)})
                if index == 0:
                    print(json.dumps({"route": route, "first": samples[-1]}), flush=True)
            warm = samples[4:]
            elapsed = sorted(s["totalMs"] for s in warm)
            reports[route] = {"firstRequest": samples[0], "warmup": 3, "samples": warm,
                              "medianMs": statistics.median(elapsed),
                              "p95Ms": elapsed[max(0, (95 * len(elapsed) + 99) // 100 - 1)]}
        result = {"startupMs": startup, "databaseBytes": app.database.stat().st_size,
                  "projectSessionCount": len(project["sessions"]), "collectorRunning": False,
                  "cache": "Process first request and warm OS cache; OS cache not flushed", "routes": reports}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(output), flush=True)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


if __name__ == "__main__":
    main()
