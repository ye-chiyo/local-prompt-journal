"""Controlled external Codex protocol peer; never runs recorded commands."""
import json
import sys
from urllib.request import urlopen

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

THREAD = "sample-session"
TURNS = [
    {"id": "turn-1", "status": "completed", "itemsView": "full", "startedAt": 100,
     "items": [
         {"type": "userMessage", "id": "user-1", "content": [{"type": "text", "text": "请记录原文。"}]},
         {"type": "agentMessage", "id": "ai-1", "text": "正在核对中文。", "phase": "commentary"},
         {"type": "agentMessage", "id": "ai-2", "text": "原文已保留。", "phase": "final_answer"},
     ]},
]
MODE = sys.argv[1] if len(sys.argv) > 1 else "normal"
if MODE == "tools":
    TURNS[0]["items"].insert(2, {
        "type": "commandExecution", "id": "cmd-ok", "command": "echo 样本", "cwd": "C:/sample",
        "commandActions": [], "status": "completed", "aggregatedOutput": "命令原文\n", "exitCode": 0, "durationMs": 12,
    })
    TURNS[0]["items"][3:3] = [
        {"type": "mcpToolCall", "id": "parallel-b", "server": "sample", "tool": "lookup", "arguments": {"key": "相同"},
         "status": "failed", "result": None, "error": {"message": "乙失败"}},
        {"type": "mcpToolCall", "id": "parallel-a", "server": "sample", "tool": "lookup", "arguments": {"key": "相同"},
         "status": "completed", "result": {"content": [{"type": "text", "text": "甲结果"}]}, "error": None},
        {"type": "dynamicToolCall", "id": "dynamic-long", "namespace": "sample", "tool": "long", "arguments": {"limit": 9000},
         "status": "completed", "success": True, "contentItems": [{"type": "inputText", "text": "长" * 8000 + "末尾原文"}]},
        {"type": "commandExecution", "id": "cmd-cut", "command": "echo 截断", "cwd": "C:/sample", "commandActions": [],
         "status": "completed", "exitCode": 0, "aggregatedOutput": "已取得前缀\nWarning: truncated output"},
    ]
    TURNS.append({"id": "turn-2", "status": "interrupted", "itemsView": "full", "items": [
        {"type": "dynamicToolCall", "id": "missing", "namespace": "sample", "tool": "pending", "arguments": None,
         "status": "inProgress", "contentItems": None, "success": None},
        {"type": "functionCallOutput", "id": "output-only", "name": "standalone", "output": "独立原文"},
        {"type": "futureEvent", "id": "future", "payload": "未来原文"},
    ]})
if MODE == "complex":
    TURNS.append({"id": "turn-2", "status": "interrupted", "itemsView": "full", "items": [
        {"type": "userMessage", "id": "user-2", "content": [{"type": "text", "text": "请记录原文。"}, {"type": "localImage", "path": "missing.png"}]},
        {"type": "agentMessage", "id": "ai-3", "text": "<script>不会执行历史代码</script>"},
        {"type": "futureEvent", "id": "future-1", "payload": "不支持的原始事件"},
    ]})

for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    method, params = request["method"], request.get("params", {})
    if MODE == "invalid-utf8":
        sys.stdout.buffer.write(b"\xff\n")
        sys.stdout.buffer.flush()
        continue
    history = json.loads(json.dumps(TURNS))
    if MODE == "multi":
        history[0]["items"][0]["content"][0]["text"] = "会话 " + params.get("threadId", "") + " 原文"
    if method == "initialize":
        result = {"userAgent": "Controlled Codex/fixture-1", "platformOs": "windows", "codexHome": "fixture-only"}
        if MODE == "network":
            try:
                with urlopen("http://journal-isolation.invalid/probe", timeout=1) as response:
                    result["networkProbe"] = response.read().decode()
            except OSError:
                result["networkProbe"] = "blocked"
    elif method == "thread/read":
        result = {"thread": {"id": params["threadId"] if MODE == "multi" else THREAD, "name": "中文验收样本", "status": {"type": "notLoaded"}, "turns": []}}
    elif method == "thread/turns/list":
        start = int(params.get("cursor", "0"))
        limit = params.get("limit", 1)
        result = {"data": history[start:start + limit], "nextCursor": str(start + limit) if start + limit < len(history) else None}
        if MODE == "summary":
            result["data"][0]["itemsView"] = "summary"
        if MODE == "loop":
            result["nextCursor"] = "0"
    elif method == "thread/items/list":
        items = [{"turnId": t["id"], "item": i, "startedAtMs": 100000, "completedAtMs": 101000} for t in history for i in t["items"]]
        if MODE == "tools":
            for entry in items:
                if entry["item"]["id"] == "missing":
                    entry["completedAtMs"] = None
        if MODE == "conflicting":
            stale = json.loads(json.dumps(items[-1]))
            stale["item"]["text"] = "旧内容"
            stale["item"]["phase"] = "commentary"
            items.insert(len(items) - 1, stale)
        start = int(params.get("cursor", "0"))
        limit = params.get("limit", 1)
        result = {"data": items[start:start + limit], "nextCursor": str(start + limit) if start + limit < len(items) else None}
        if MODE == "overlap" and start:
            result["data"] = items[max(0, start - 1):start + limit]
    else:
        print(json.dumps({"id": request["id"], "error": {"code": -32601, "message": "Read-only fixture rejected method"}}), flush=True)
        continue
    print(json.dumps({"id": request["id"], "result": result}, ensure_ascii=False), flush=True)
