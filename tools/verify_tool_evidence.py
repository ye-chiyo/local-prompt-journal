"""Check saved tools via HTTP against raw protocol facts fixed before implementation."""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import quote

from verify_saved_session import EvidenceLinks, evidence_checks, read, reading_html, start, stop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    for path in (args.report, args.export):
        if path.resolve().is_relative_to(project):
            parser.error("报告与真实导出必须在源码外。")
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    assert expected["definedBeforeImplementation"] is True
    tid = quote(expected["threadId"], safe="")
    process, url = start(args.data_dir)
    try:
        first = read(url + "/api/session/" + tid)
        exported = read(url + "/export/" + tid)
    finally:
        stop(process)
    process, url = start(args.data_dir)
    try:
        second = read(url + "/api/session/" + tid)
        html = reading_html(url, json.loads(exported)['session'])
        links = EvidenceLinks()
        links.feed(html)
        for link in set(links.links):
            json.loads(read(url + link))
    finally:
        stop(process)
    package = json.loads(exported)
    view = package["session"]
    actual = {(t["turnId"], t["id"]): t for t in view["tools"]}
    wanted = {(e["turnId"], e["item"]["id"]) for e in expected["tools"]}
    checks = {"sameCallIdentitiesAndTurns": set(actual) == wanted,
              "newProcessRetainsTools": first == second,
              "publicQueryEqualsExport": json.loads(second) == view}
    matches = []
    for entry in expected["tools"]:
        item = entry["item"]
        tool = actual.get((entry["turnId"], item["id"]))
        if tool is None:
            matches.append(False)
            continue
        node = package
        for part in tool.get("evidenceRef", "#/")[2:].split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        # Expected fields come directly from fixed source records, never from Journal.
        if item["type"] == "commandExecution":
            fields_match = (tool["arguments"] == {"command": item["command"], "cwd": item["cwd"]}
                            and tool["result"] == item["aggregatedOutput"] and tool["exitCode"] == item["exitCode"])
        else:
            fields_match = (tool["arguments"] == item["arguments"] and tool["result"] == item.get("result")
                            and tool["error"] == item.get("error"))
        matches.append(fields_match and node == item and tool["sourceStatus"] == item.get("status")
                       and tool["durationMs"] == item.get("durationMs")
                       and tool["startedAtMs"] == entry["startedAtMs"]
                       and tool["completedAtMs"] == entry["completedAtMs"]
                       and f'data-tool-id="{item["id"]}"' in html)
    checks.update({"allFixedToolFactsAndEvidenceMatch": all(matches), "toolCount": len(actual),
                   "retention": view['source'].get('retention', 'full-protocol'), **evidence_checks(package)})
    checks["selfVerified"] = all(v for v in checks.values() if isinstance(v, bool))
    checks["userAccepted"] = False
    args.report.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    args.export.write_bytes(exported)
    print(json.dumps(checks, ensure_ascii=False))
    return 0 if checks["selfVerified"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
