"""Small independent captures for catalog and storage acceptance tests."""
from copy import deepcopy


def catalog_capture(identity="catalog-1", created=100, instance="catalog-fixture", text="目录不应加载的正文"):
    items = [
        {"id": "user", "type": "userMessage", "content": [{"type": "text", "text": text}]},
        {"id": "tool", "type": "commandExecution", "command": "fixture-command",
         "cwd": "C:/目录项目", "status": "completed", "exitCode": 0, "aggregatedOutput": "工具最终结果"},
    ]
    entries = [{"turnId": "turn", "item": deepcopy(item)} for item in items]
    return {"thread": {"id": identity, "name": "目录会话-" + identity, "createdAt": created, "cwd": "C:/目录项目"},
            "turns": [({"id": "turn", "startedAt": 100, "status": "completed", "items": items}, "#/evidence/0")],
            "items": [(entry, f"#/evidence/0/response/result/data/{i}") for i, entry in enumerate(entries)],
            "evidence": [{"method": "thread/items/list", "params": {}, "response": {"result": {"data": entries}}}],
            "source": {"instance": instance, "version": "fixture", "gaps": [], "pagination": {}, "notDisplayedTypes": []}}
