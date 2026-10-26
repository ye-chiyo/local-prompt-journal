"""Human-authored search facts; the external peer never executes these tools."""
from copy import deepcopy


def search_source():
    main = {"thread": {"id": "search-main", "name": "同名会话", "projectId": "project-a",
                       "cwd": "C:/搜索演示", "createdAt": 100, "updatedAt": 220},
            "turns": [{"id": "search-turn", "startedAt": 200, "status": "inProgress", "items": [
                {"id": "prompt-a", "type": "userMessage", "content": [{"type": "text", "text": "雨巷纸伞 SQLite 中文归档 100%_字面* <b>原文</b>"}]},
                {"id": "prompt-b", "type": "userMessage", "content": [{"type": "text", "text": "雨巷纸伞 SQLite 中文归档 100%_字面* <b>原文</b>"}]},
                {"id": "thinking", "type": "agentMessage", "phase": "commentary", "text": "青瓷回声，正在核对。"},
                {"id": "answer", "type": "agentMessage", "phase": "final_answer", "text": "晚霞书签，已经保存。"},
                {"id": "long-tool", "type": "commandExecution", "command": "never executed", "status": "completed", "exitCode": 0,
                 "aggregatedOutput": "长输出开头\n" + "长" * 8000 + "\n远山灯塔：仅取得这部分。", "truncated": True},
                {"id": "error-tool", "type": "mcpToolCall", "server": "fixture", "tool": "check", "arguments": {},
                 "status": "failed", "error": {"message": "校验雪松失败"}, "result": None},
                {"id": "changing-tool", "type": "dynamicToolCall", "tool": "observe", "arguments": {}, "status": "inProgress",
                 "contentItems": [{"type": "inputText", "text": "旧版沙洲"}]},
                {"id": "future", "type": "futureEvent", "payload": "未保存的星际菠萝"},
            ]}]}
    other = deepcopy(main)
    other["thread"].update(id="search-other", projectId="project-b", createdAt=110)
    other["turns"] = [{"id": "other-turn", "startedAt": 200, "status": "completed", "items": [
        {"id": "other-prompt", "type": "userMessage", "content": [{"type": "text", "text": "雨巷纸伞，另一个项目。"}]}]}]
    child = {"thread": {"id": "search-child", "name": "同名会话", "parentThreadId": "search-main", "cwd": "D:/子项目",
                        "createdAt": 120, "updatedAt": 220},
             "turns": [{"id": "child-turn", "startedAt": 200, "status": "completed", "items": [
                 {"id": "child-prompt", "type": "userMessage", "content": [{"type": "text", "text": "子会话独有梧桐"}]}]}]}
    return {"sessions": [main, other, child]}
