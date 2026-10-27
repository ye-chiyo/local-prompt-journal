"""Literal search over saved, supported text. No source access or derived index."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterator
from urllib.parse import quote, urlencode


def item_anchor(instance: str, thread: str, turn: str, identity: str, kind: str) -> str:
    return "item-" + hashlib.sha256(json.dumps([instance, thread, turn, identity, kind]).encode()).hexdigest()


def string_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_values(child)


def content_text(value: Any) -> Iterator[str]:
    if isinstance(value, list):
        for block in value:
            if isinstance(block, dict) and block.get("type") in ("text", "inputText") and isinstance(block.get("text"), str):
                yield block["text"]


def searchable_fields(item: dict[str, Any], kind: str) -> Iterator[tuple[str, str]]:
    if kind == "message":
        yield "text", item["text"]
        return
    result = item.get("result")
    if isinstance(result, str):
        yield "result", result
    elif item["type"] == "mcpToolCall" and isinstance(result, dict):
        for text in content_text(result.get("content")):
            yield "result", text
        for text in string_values(result.get("structuredContent")):
            yield "result", text
    elif item["type"] == "dynamicToolCall":
        for text in content_text(result):
            yield "result", text
    error = item.get("error")
    if isinstance(error, str):
        yield "error", error
    elif isinstance(error, dict) and isinstance(error.get("message"), str):
        yield "error", error["message"]


def search_sessions(sessions: list[dict[str, Any]], query: str, project: str | None,
                    thread: str | None, instance: str | None, offset: int, limit: int) -> dict[str, Any]:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("搜索页起点须非负，每页数量须为 1—100。")
    matches = []
    total = 0
    for session in sessions:
        source = session["source"]["instance"]
        if ((project is not None and session["project"]["id"] != project)
                or (thread is not None and session["id"] != thread)
                or (instance is not None and source != instance) or not query.strip()):
            continue
        entries = [(item, "message") for item in session["messages"]]
        entries += [(item, "tool") for item in session.get("tools", [])]
        for item, kind in sorted(entries, key=lambda pair: pair[0]["order"]):
            for field, text in searchable_fields(item, kind):
                position = text.find(query)
                if position < 0:
                    continue
                total += 1
                if offset < total <= offset + limit:
                    start, end = max(0, position - 70), min(len(text), position + len(query) + 100)
                    anchor = item_anchor(source, session["id"], item["turnId"], item["id"], kind)
                    options = {"source": source, "saved": session["savedAt"], "target": anchor, "q": query, "field": field}
                    route = "/session/" + quote(session["id"], safe="") + '/turn/' + quote(item['turnId'], safe='')
                    evidence_index = item["evidenceRef"].split("/")[2]
                    evidence_url = "/evidence/" + quote(session["id"], safe="") + "/" + evidence_index
                    evidence_url += "?" + urlencode({"source": source, "saved": session["savedAt"]})
                    matches.append({"sourceInstance": source, "project": session["project"], "threadId": session["id"],
                        "sessionName": session["name"], "savedAt": session["savedAt"], "turnId": item["turnId"],
                        "id": item["id"], "type": item["type"], "phase": item.get("phase"), "kind": kind, "field": field,
                        "snippet": ("…" if start else "") + text[start:end] + ("…" if end < len(text) else ""),
                        "completeness": item["completeness"], "reasons": item["reasons"], "evidenceRef": item["evidenceRef"],
                        "url": route + "?" + urlencode(options) + "#" + anchor, "evidenceUrl": evidence_url})
                break  # One result per actual item, even when several fields match.
    return {"query": query, "total": total, "offset": offset, "limit": limit, "results": matches,
            "nextOffset": offset + limit if offset + limit < total else None,
            "scope": {"project": project, "session": thread, "source": instance}, "emptyQuery": not query.strip()}
