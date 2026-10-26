"""Human-authored protocol facts. Commands here are evidence, never executed."""


def session(identity, text, **metadata):
    return {"thread": {"id": identity, "name": "受控关系样本 · " + identity,
                       "cwd": "C:/主项目", "createdAt": 100, "updatedAt": 210, **metadata},
            "turns": [{"id": "t1", "startedAt": 200, "status": "completed", "items": [
                {"id": "u1", "type": "userMessage", "content": [{"type": "text", "text": text}]}]}]}


def facts():
    main = session("main", "主会话原文")
    main["turns"][0]["items"].extend([
        {"id": "ok", "type": "commandExecution", "command": "sample identical", "cwd": "C:/主项目",
         "commandActions": [], "processId": "7", "status": "inProgress", "aggregatedOutput": "启动原文", "exitCode": None},
        {"id": "fail", "type": "commandExecution", "command": "sample identical", "cwd": "C:/主项目",
         "commandActions": [], "processId": "8", "status": "failed", "aggregatedOutput": "失败原文", "exitCode": 9},
        {"id": "activity", "type": "subAgentActivity", "agentThreadId": "child", "agentPath": "/root/child", "kind": "started"},
        {"id": "missing", "type": "subAgentActivity", "agentThreadId": "missing", "agentPath": "/root/missing", "kind": "interacted"},
        {"id": "blocked", "type": "subAgentActivity", "agentThreadId": "blocked", "agentPath": "/root/blocked", "kind": "interacted"},
        {"id": "incomplete", "type": "subAgentActivity", "agentPath": "/root/unknown", "kind": "started"},
        {"id": "untyped", "type": "collabAgentToolCall", "senderThreadId": "main", "receiverThreadIds": ["child"],
         "status": "completed", "agentsStates": {}},
    ])
    main["turns"].append({"id": "t2", "startedAt": 210, "status": "completed", "items": [
        {"id": "unknown", "type": "commandExecution", "command": "sample identical", "cwd": "C:/主项目",
         "commandActions": [], "processId": "7", "status": "completed", "aggregatedOutput": "只有启动回执", "exitCode": None},
        {"id": "running", "type": "commandExecution", "command": "sample running", "cwd": "C:/主项目",
         "commandActions": [], "processId": "11", "status": "inProgress", "aggregatedOutput": "仍在运行原文", "exitCode": None}]})
    child = session("child", "子会话原文", parentThreadId="main", cwd="D:/子项目")
    child["turns"][0]["items"].append({"id": "ok", "type": "commandExecution", "command": "sample identical", "cwd": "D:/子项目",
         "commandActions": [], "processId": "7", "status": "completed", "aggregatedOutput": "子执行原文", "exitCode": 4})
    old_child = session("old-child", "禁止补读的旧子会话正文", parentThreadId="main", updatedAt=100)
    old_fork = session("old-fork", "禁止补读的旧分叉正文", forkedFromId="main", updatedAt=100)
    old_child["turns"][0]["startedAt"] = old_fork["turns"][0]["startedAt"] = 100
    return {"forbidBodyBefore": 190, "sessions": [child, session("fork", "分叉原文", forkedFromId="main"),
                         session("grandchild", "孙会话原文", parentThreadId="child"), main,
                         {**session("blocked", "不可读取正文"), "fail": True}, old_child, old_fork]}
