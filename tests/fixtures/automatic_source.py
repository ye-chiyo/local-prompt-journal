"""Mutable external protocol fixture. The recorded tools are never executed."""
import json
from pathlib import Path
import sys
import time

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    method, params = request["method"], request.get("params", {})
    error = None
    if method == "initialize":
        result = {"userAgent": "controlled-auto/1", "codexHome": state.get("codexHome", "automatic-fixture")}
    elif state.get("unavailable"):
        error = "来源暂时不可用"
    elif method == "thread/list":
        data = [s["thread"] for s in state["sessions"] if s["thread"].get("archived", False) == params["archived"]]
        start = int(params.get("cursor", "0"))
        size = params["limit"]
        result = {"data": data[max(0, start - 1):start + size], "nextCursor": str(start + size) if start + size < len(data) else None}
    else:
        session = next(s for s in state["sessions"] if s["thread"]["id"] == params["threadId"])
        if session.get("fail"):
            error = "此会话暂时不可读取"
        elif method == "thread/read":
            result = {"thread": session["thread"]}
        elif method == "thread/turns/list":
            view = params.get("itemsView", "full")
            result = {"data": [{**t, "items": t["items"] if view == "full" else [], "itemsView": view} for t in session["turns"]], "nextCursor": None}
        elif method == "thread/items/list":
            if state.get("forbidBodyBefore") is not None and any(
                t["startedAt"] < state["forbidBodyBefore"] and params.get("turnId") in (None, t["id"])
                for t in session["turns"]
            ):
                print(json.dumps({"id": request["id"], "error": {"code": -1, "message": "不允许读取旧正文"}}), flush=True)
                continue
            time.sleep(session.get("delay", 0))
            data = [{"turnId": t["id"], "item": i, "startedAtMs": t.get("startedAt", 0) * 1000,
                     "completedAtMs": None} for t in session["turns"] if params.get("turnId") in (None, t["id"]) for i in t["items"]]
            start = int(params.get("cursor", "0"))
            size = params["limit"]
            result = {"data": data[max(0, start - 1):start + size], "nextCursor": str(start + size) if start + size < len(data) else None}
        else:
            error = "只读样本拒绝此方法"
    response = {"id": request["id"]}
    response.update({"error": {"code": -1, "message": error}} if error else {"result": result})
    print(json.dumps(response, ensure_ascii=False), flush=True)
