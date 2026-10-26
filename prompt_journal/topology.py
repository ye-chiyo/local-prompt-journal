"""Relations from formal history fields only; projections never read the source."""
from __future__ import annotations

import json
from copy import deepcopy
import hashlib
from typing import Any

from .source import now


EXECUTION_GAPS = [
    "命令以来源实例、会话、回合、条目 ID 关联保存修订；processId 仅为来源提供的 PTY 句柄，不跨条目合并，也不单凭句柄认定后台运行。",
    "当前历史协议未独立提供后台启动／轮询调用记录；下列是已保存的命令条目观察，不伪造轮询或嵌套调用。",
    "仍在运行指来源最后一次记录；保存／到达顺序不是执行因果顺序。未取得退出码时退出结果未知，执行成功也不代表业务成功。",
]

RELATION_GAPS = [
    "只展示已保存的正式关系元数据与活动条目。未取得关系不等于没有发生；未知类型与缺失目标如实保留。",
    "子 agent 活动说明存在交互，不单凭 interacted/completed 活动断言直接父子。关系身份不授权读取目标正文。",
    "链接只打开同一来源实例中已保存的会话；未归档、来源不可访问或范围外的正文不会因查看／导出而读取。没有实现任务 10 的受管理删除。",
]


def pointer(document: dict[str, Any], ref: str) -> Any:
    node: Any = document
    for part in ref.removeprefix("#/").split("/"):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def relocate(package: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Relocate our index pointers, leaving all source payloads and raw lines intact."""
    result = deepcopy(package)

    def entries(document: dict[str, Any]) -> None:
        session = document["session"]
        for group in ("messages", "tools", "unsupportedItems", "relations"):
            for entry in session.get(group, []):
                ref = entry.get("evidenceRef")
                if ref:
                    entry["evidenceRef"] = prefix + ref[1:]
        for execution in session.get("executions", []):
            for observation in execution["observations"]:
                observation["evidenceRef"] = prefix + observation["evidenceRef"][1:]
        for revision in document.get("revisions", []):
            entries(revision)

    entries(result)
    return result


def executions(packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tracks: dict[tuple[str, str], dict[str, Any]] = {}
    last_payloads: dict[tuple[str, str], str] = {}
    for index, package in enumerate(packages):
        session = package["session"]
        prefix = "#" if index == len(packages) - 1 else f"#/revisions/{index}"
        for tool in session.get("tools", []):
            if tool["type"] != "commandExecution":
                continue
            item = pointer(package, tool["evidenceRef"])
            key = (tool["turnId"], tool["id"])
            track = tracks.setdefault(key, {"id": tool["id"], "turnId": tool["turnId"],
                "sourceInstance": session["source"]["instance"], "threadId": session["id"],
                "observations": [], "businessOutcome": "unknown"})
            payload = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if last_payloads.get(key) == payload:
                # The current location may have changed even if the fact did not.
                track["observations"][-1]["evidenceRef"] = prefix + tool["evidenceRef"][1:]
                track["observations"][-1]["savedAt"] = session["savedAt"]
                continue
            last_payloads[key] = payload
            exit_code = item.get("exitCode")
            has_exit = isinstance(exit_code, int) and not isinstance(exit_code, bool)
            source_status = item.get("status")
            state = "exited" if has_exit else "running" if source_status == "inProgress" else "started" if item.get("processId") else "unknown"
            outcome = ("failed" if exit_code != 0 else "success" if source_status == "completed" else "unknown") if has_exit else "unknown"
            observation = {"sourceStatus": source_status, "processId": item.get("processId"),
                "command": item.get("command"), "cwd": item.get("cwd"), "output": item.get("aggregatedOutput"),
                "error": item.get("error"), "exitCode": exit_code, "state": state, "outcome": outcome,
                "savedAt": session["savedAt"], "evidenceRef": prefix + tool["evidenceRef"][1:]}
            track["observations"].append(observation)
            track.update({k: observation[k] for k in ("state", "outcome", "exitCode", "processId")})
    return list(tracks.values())


def relation_records(package: dict[str, Any]) -> list[dict[str, Any]]:
    session = package["session"]
    thread = session["thread"]
    records = []

    def add(kind: str, origin: str | None, target: str | None, basis: str, ref: str,
            reason: str = "", turn_id: str | None = None, activity: str | None = None) -> None:
        records.append({"type": kind, "fromId": origin, "toId": target, "basis": basis,
            "reason": reason, "turnId": turn_id, "activity": activity,
            "ownerId": session["id"], "sourceInstance": session["source"]["instance"],
            "savedAt": session["savedAt"], "evidenceRef": ref})

    metadata_ref = "#/session/thread"
    for index, evidence in enumerate(package["evidence"]):
        if evidence["method"] == "thread/read" and evidence["response"].get("result", {}).get("thread", {}).get("id") == session["id"]:
            metadata_ref = f"#/evidence/{index}/response/result/thread"
            break
    parent = thread.get("parentThreadId")
    source = thread.get("source")
    subagent = source.get("subAgent") if isinstance(source, dict) else None
    spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else None
    if parent:
        add("subAgent", parent, session["id"], "parentThreadId", metadata_ref)
    elif isinstance(spawn, dict) and spawn.get("parent_thread_id"):
        add("subAgent", spawn["parent_thread_id"], session["id"], "source.subAgent.thread_spawn.parent_thread_id", metadata_ref)
    elif subagent is not None:
        add("subAgent", None, session["id"], "source.subAgent", metadata_ref, "来源标记子 agent，但未提供父会话身份。")
    if thread.get("forkedFromId"):
        add("fork", thread["forkedFromId"], session["id"], "forkedFromId", metadata_ref)
    for entry in session.get("unsupportedItems", []):
        if entry["type"] not in ("subAgentActivity", "collabAgentToolCall"):
            continue
        item = pointer(package, entry["evidenceRef"])
        if entry["type"] == "subAgentActivity":
            add("subAgent", session["id"], item.get("agentThreadId"), "subAgentActivity.agentThreadId", entry["evidenceRef"],
                "子 agent 活动关联；不据此推造直接父子。" if item.get("agentThreadId") else "来源缺少 agentThreadId，目标会话未知。",
                entry["turnId"], item.get("kind"))
        else:
            tool = item.get("tool")
            kind = "subAgent" if tool == "spawnAgent" else "agentInteraction" if tool in {
                "sendInput", "resumeAgent", "wait", "closeAgent", "sendMessage", "followupTask", "interruptAgent", "listAgents"} else "unknown"
            for target in item.get("receiverThreadIds") or [None]:
                missing = [name for name, value in (("senderThreadId", item.get("senderThreadId")), ("receiverThreadIds", target), ("tool", tool)) if not value]
                add(kind, item.get("senderThreadId"), target, "collabAgentToolCall", entry["evidenceRef"],
                    "来源缺少 " + ", ".join(missing) if missing else "协作操作不等于任务成功，也不自动建立父子关系。",
                    entry["turnId"], tool)
    return records


def remember_relation_metadata(threads: list[dict[str, Any]], instance: str,
                               previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations = list(previous)
    known = {entry["id"] for entry in observations}
    for thread in threads:
        fields = {k: thread[k] for k in ("id", "parentThreadId", "forkedFromId", "source") if k in thread}
        source = fields.get("source")
        if not (fields.get("parentThreadId") or fields.get("forkedFromId") or isinstance(source, dict) and "subAgent" in source):
            continue
        projection = json.dumps({"sourceInstance": instance, "thread": fields}, ensure_ascii=False, sort_keys=True)
        identity = hashlib.sha256(projection.encode("utf-8")).hexdigest()
        if identity not in known:
            observations.append({"id": identity, "sourceInstance": instance, "thread": fields,
                "observedAt": now(), "method": "thread/list", "projection": projection, "sha256": identity,
                "representation": "正式关系字段投影；preview 与正文未保存，不是完整原始列表响应。"})
            known.add(identity)
    return observations
