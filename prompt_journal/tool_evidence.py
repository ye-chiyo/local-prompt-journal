"""Tool facts from atomic App Server items; never infer calls from output text."""
from __future__ import annotations

import json
from typing import Any


TOOL_TYPES = frozenset({"commandExecution", "mcpToolCall", "dynamicToolCall", "functionCallOutput"})


def tool_record(entry: dict[str, Any], ref: str, order: int) -> dict[str, Any]:
    item = entry["item"]
    kind = item["type"]
    arguments = item.get("arguments")
    arguments_available = "arguments" in item
    name = item.get("tool", item.get("name"))
    if kind == "commandExecution":
        name = "命令"
        arguments = {k: item[k] for k in ("command", "cwd") if k in item}
        arguments_available = bool(arguments)
        result = item.get("aggregatedOutput")
    elif kind == "mcpToolCall":
        result = item.get("result")
    elif kind == "dynamicToolCall":
        result = item.get("contentItems")
    else:
        result = item.get("output")
    reasons = []
    completeness = "unknown"
    error = item.get("error")
    if not arguments_available:
        reasons.append("来源未提供请求参数。")
    if result is None and error is None:
        completeness = "partial"
        reasons.append("未取得结果或错误；请求已记录不代表执行完成。")
    if kind == "functionCallOutput":
        reasons.append("独立函数输出：来源未提供对应请求身份，不与其他条目猜测配对。")
    # Output can quote warning text. Only structured metadata proves truncation.
    output_text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    if item.get("truncated") is True:
        completeness = "partial"
        reasons.append("来源标记输出截断；仅保存并展示已取得的原文，缺失部分不可恢复。")
    elif "Warning: truncated output" in output_text:
        reasons.append("结果包含截断提示文本；来源未提供结构化截断标记，是否实际截断未知。")
    reasons.append("来源未提供完整性保证；已取得内容全文保留，完整性未知。")
    status = item.get("status")
    if error is not None or item.get("success") is False or item.get("exitCode") not in (None, 0):
        status = "failed"
    elif status not in ("completed", "failed", "inProgress", "declined"):
        status = "unknown"
    if status == "completed" and result is None and error is None:
        status = "unknown"
        reasons.append("来源声称完成但未取得结果；展示状态未知，原状态另行保留。")
    return {"id": item["id"], "turnId": entry["turnId"], "type": kind, "order": order,
            "name": name, "namespace": item.get("server", item.get("namespace")),
            "arguments": arguments, "argumentsAvailable": arguments_available, "result": result, "error": error,
            "status": status, "sourceStatus": item.get("status"), "sourceSuccess": item.get("success"),
            "exitCode": item.get("exitCode"), "durationMs": item.get("durationMs"),
            "startedAtMs": entry.get("startedAtMs"), "completedAtMs": entry.get("completedAtMs"),
            "businessOutcome": "unknown", "completeness": completeness, "reasons": reasons,
            "association": "standaloneOutput" if kind == "functionCallOutput" else "sourceItemIdentity",
            "evidenceRef": ref + "/item"}
