"""Manual acceptance through public HTTP, with two fresh app processes.

No source/SQLite internals; expects an independently prepared desktop manifest.
Run from the project directory. All reports and exported history stay outside it.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
from urllib.parse import quote
from urllib.request import urlopen


class EvidenceLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.message_links = []
        self.in_message = False
        self.in_identity = False
        self.message_href = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        href = attributes.get("href", "")
        if tag == "details":
            self.in_message = attributes.get("class", "") in ("message user", "message agent")
            self.message_href = None
        if tag == "code" and self.in_message:
            self.in_identity = True
        if tag == "br":
            self.in_identity = False
        if tag == "a" and href.startswith("/evidence/"):
            self.links.append(href)
            if self.in_message:
                self.message_href = href

    def handle_endtag(self, tag):
        if tag == "code":
            self.in_identity = False
        if tag == "details":
            self.in_message = False

    def handle_data(self, data):
        if self.in_identity and self.message_href:
            self.message_links.append((data, self.message_href))


def start(data_dir):
    command = [sys.executable, "-m", "prompt_journal"]
    if data_dir:
        command += ["--data-dir", str(data_dir)]
    command += ["serve", "--port", "0"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8")
    lines = queue.Queue()
    reader = threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
    reader.start()
    try:
        line = lines.get(timeout=10)
        match = re.search(r"http://127\.0\.0\.1:\d+", line)
        if not match:
            raise RuntimeError("本机查看进程未成功启动。")
        return process, match.group()
    except Exception:
        stop(process)
        raise


def stop(process):
    process.terminate()
    process.wait(timeout=5)
    for stream in (process.stdout, process.stderr):
        stream.close()


def read(url):
    with urlopen(url, timeout=10) as response:
        return response.read()


def text(item):
    return item["text"] if item["type"] == "agentMessage" else "\n".join(c.get("text", "") for c in item["content"] if c.get("type") == "text")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    for path in (args.report, args.export):
        if path.resolve().is_relative_to(project):
            parser.error("报告和导出必须放在源码以外。")
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    tid = quote(expected["thread"]["id"], safe="")
    wanted = {(t["id"], i["id"]): (text(i), i.get("phase")) for t in expected["turns"] for i in t["messages"]}
    process, url = start(args.data_dir)
    try:
        first = read(url + "/api/session/" + tid)
        exported = read(url + "/export/" + tid)
    finally:
        stop(process)
    process, url = start(args.data_dir)
    try:
        second = read(url + "/api/session/" + tid)
        html = read(url + "/session/" + tid).decode("utf-8")
        links = EvidenceLinks()
        links.feed(html)
        for link in set(links.links):
            json.loads(read(url + link))
        visible_message_ids = [identity for identity, _ in links.message_links]
        expected_message_ids = [i["id"] for t in expected["turns"] for i in t["messages"]]
        message_links_match = sorted(visible_message_ids) == sorted(expected_message_ids)
        for identity, href in links.message_links:
            evidence = json.loads(read(url + href))
            entries = evidence["response"]["result"].get("data", [])
            message_links_match &= any(e.get("item", {}).get("id") == identity for e in entries)
    finally:
        stop(process)
    package = json.loads(exported)
    session = package["session"]
    got = {(m["turnId"], m["id"]): (m["text"], m["phase"]) for m in session["messages"]}
    references = []
    for message in session["messages"]:
        node = package
        for part in message["evidenceRef"][2:].split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        references.append(node["id"] == message["id"] and text(node) == message["text"])
    checks = {
        "publicExportMatchesIndependentManifest": wanted == got,
        "processRestartPreservesPublicQuery": first == second,
        "allEvidenceReferencesResolve": all(references) and len(references) == len(wanted),
        "allRawHashesMatch": all(hashlib.sha256(e["raw"].encode("utf-8")).hexdigest() == e["sha256"] for e in package["evidence"]),
        "allRawPayloadsMatch": all(json.loads(e["raw"]) == e["response"] for e in package["evidence"]),
        "allMessageEvidenceLinksVisibleAndReadable": message_links_match,
        "htmlHasPhaseLabels": all(s in html for s in ["AI 过程消息", "AI 最终回答", "用户原文"]),
        "messages": len(got), "sourceItemCount": session["sourceItemCount"],
        "schemaVersion": package["schemaVersion"], "exportBytes": len(exported),
    }
    checks["passed"] = all(v for v in checks.values() if isinstance(v, bool))
    for path, payload in ((args.report, json.dumps(checks, ensure_ascii=False, indent=2).encode("utf-8")), (args.export, exported)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    print(json.dumps(checks, ensure_ascii=False))
    return 0 if checks["passed"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
