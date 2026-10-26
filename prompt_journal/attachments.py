"""Archive only explicit, typed source attachments; never follow remote references."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import url2pathname

from .topology import pointer
from .source import now


def candidates(item: dict[str, Any]) -> list[tuple[str, str, Any, str]]:
    """Return (field pointer, representation, reference, readable name)."""
    result: list[tuple[str, str, Any, str]] = []

    def add(field: str, kind: str, value: Any, name: str = "附件") -> None:
        result.append((field, kind, value, name))

    kind = item.get("type")
    if kind == "userMessage":
        for index, content in enumerate(item.get("content", [])):
            prefix = f"/content/{index}"
            content_type = content.get("type")
            if content_type in ("localImage", "localAudio", "mention"):
                add(prefix + "/path", "path", content.get("path"), content.get("name") or "附件")
            elif content_type in ("image", "audio"):
                field = "fileId" if content.get("fileId") else "url"
                add(prefix + "/" + field, field, content.get(field))
    elif kind == "imageView":
        add("/path", "path", item.get("path"), "图片")
    elif kind == "imageGeneration":
        if item.get("result"):
            add("/result", "base64", item["result"], "生成图片")
        elif item.get("savedPath"):
            add("/savedPath", "path", item["savedPath"], "生成图片")
        elif item.get("fileId"):
            add("/fileId", "fileId", item["fileId"], "生成图片")
        for index, image in enumerate(item.get("inputImages") or []):
            add(f"/inputImages/{index}", "verifiedPath", image, "生成输入图片")
    elif kind == "dynamicToolCall":
        for index, content in enumerate(item.get("contentItems") or []):
            media_field = {"inputImage": "imageUrl", "inputAudio": "audioUrl"}.get(content.get("type"))
            if media_field:
                add(f"/contentItems/{index}/{media_field}", "url", content.get(media_field))
    elif kind == "mcpToolCall":
        for index, content in enumerate((item.get("result") or {}).get("content", [])):
            if not isinstance(content, dict):
                continue
            prefix = f"/result/content/{index}"
            content_type = content.get("type")
            if content_type in ("image", "audio"):
                add(prefix + "/data", "base64", content.get("data"), content_type)
            elif content_type == "resource_link":
                add(prefix + "/uri", "url", content.get("uri"), content.get("name") or "附件")
            elif content_type == "resource" and isinstance(content.get("resource"), dict):
                resource = content["resource"]
                if "blob" in resource:
                    add(prefix + "/resource/blob", "base64", resource["blob"], resource.get("uri") or "附件")
                else:
                    add(prefix + "/resource/uri", "textResource", resource.get("uri"))
    return result


def local_file(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or value.startswith(("\\\\", "//")):
        raise ValueError("不是受支持的本机绝对文件路径（不读取相对路径或网络共享）。")
    resolved = path.resolve()
    if str(resolved).startswith(("\\\\", "//")):
        raise ValueError("附件指向网络共享，不在当前本机读取边界内。")
    if not resolved.is_file():
        raise ValueError("本机原文件不存在或不是普通文件。")
    return resolved


def source_bytes(kind: str, value: Any) -> tuple[bytes, str | None]:
    if kind == "verifiedPath" and isinstance(value, dict):
        path = local_file(value.get("path", ""))
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != value.get("sha256"):
            raise ValueError("当前本机文件与来源当时提供的校验不符；未冒充历史附件。")
        return data, path.name
    if not isinstance(value, str) or not value:
        raise ValueError("来源没有提供可取得的附件引用或内容。")
    if kind == "fileId":
        raise ValueError("来源仅提供 fileId；当前只读接口不支持解析附件内容。")
    if kind == "textResource":
        raise ValueError("来源仅提供文本资源；不能当作原始附件字节备份。")
    if kind == "url":
        url = urlsplit(value)
        if url.scheme == "data":
            header, separator, payload = value.partition(",")
            if not separator or not header.endswith(";base64"):
                raise ValueError("不支持此内嵌附件编码；仅支持明确的 base64 原字节。")
            return base64.b64decode(payload, validate=True), None
        if url.scheme != "file":
            raise ValueError("仅有远端或不受支持的引用；未联网下载附件。")
        if url.netloc not in ("", "localhost") or url.query or url.fragment:
            raise ValueError("不是受支持的本机文件引用；不读取网络共享。")
        value = url2pathname(url.path)
        kind = "path"
    if kind == "base64":
        return base64.b64decode(value, validate=True), None
    path = local_file(value)
    return path.read_bytes(), path.name


def managed_path(data_dir: Path, digest: str) -> Path:
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("附件校验身份无效。")
    path = (data_dir / "attachments" / digest).resolve()
    if not path.is_relative_to(data_dir.resolve()):
        raise ValueError("受管理附件路径超出数据目录。")
    return path


def read_copy(data_dir: Path, attachment: dict[str, Any]) -> bytes:
    if attachment.get("status") != "saved":
        raise ValueError(attachment.get("reason") or "附件未归档。")
    data = managed_path(data_dir, attachment["sha256"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != attachment["sha256"] or len(data) != attachment["size"]:
        raise ValueError("受管理副本校验失败；不能宣称附件已取得。")
    return data


def content_type(data: bytes) -> str:
    # Only inert raster formats open inline. Never execute HTML/SVG or source files.
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def archive_attachments(package: dict[str, Any], data_dir: Path,
                        previous: dict[str, Any] | None = None, acquire: bool = True) -> None:
    session = package["session"]
    old = {a["id"]: a for a in (previous or {}).get("session", {}).get("attachments", [])}
    attachments = []
    for group in ("messages", "tools", "unsupportedItems"):
        for entry in session.get(group, []):
            item = pointer(package, entry["evidenceRef"])
            for field, kind, value, name in candidates(item):
                reference = value
                if kind == "base64" or kind == "url" and isinstance(value, str) and value.startswith("data:"):
                    reference = {"encoding": kind, "referenceSha256": hashlib.sha256(str(value).encode()).hexdigest()}
                identity = [session["source"]["instance"], session["id"], entry["turnId"], entry["id"], field, reference]
                identity_hash = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
                attachment = {"id": identity_hash, "sourceInstance": session["source"]["instance"],
                    "sessionId": session["id"], "turnId": entry["turnId"], "itemId": entry["id"],
                    "evidenceRef": entry["evidenceRef"] + field, "reference": reference,
                    "representation": kind, "name": str(name), "status": "missing", "reason": None}
                if acquire:
                    try:
                        data, filename = source_bytes(kind, value)
                        digest = hashlib.sha256(data).hexdigest()
                        path = managed_path(data_dir, digest)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        temporary = None
                        try:
                            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                                temporary = Path(stream.name)
                                stream.write(data)
                                stream.flush()
                                os.fsync(stream.fileno())
                            os.replace(temporary, path)
                        finally:
                            if temporary and temporary.exists():
                                temporary.unlink()
                        attachment.update(status="saved", sha256=digest, size=len(data),
                                          mediaType=content_type(data), name=filename or str(name))
                        preserved = old.get(identity_hash)
                        attachment["acquiredAt"] = preserved["acquiredAt"] if preserved and preserved.get("sha256") == digest else now()
                        attachment["byteBasis"] = "localFileAtArchiveTime" if filename and kind != "verifiedPath" else "sourceProvidedBytesOrChecksum"
                        attachment["versionNote"] = ("来源没有提供事件当时的文件校验；此副本为归档时读取的本机字节，不能证明消息发生时的版本。"
                            if attachment["byteBasis"] == "localFileAtArchiveTime" else "原字节来自本次来源内容，或已核对来源提供的原始校验。")
                    except (OSError, ValueError, binascii.Error) as exc:
                        attachment["reason"] = str(exc) if isinstance(exc, ValueError) else "附件读取或保存失败：" + str(exc)
                        preserved = old.get(identity_hash)
                        if preserved:
                            try:
                                read_copy(data_dir, preserved)
                                # The copy survives, but pagination and evidence positions
                                # belong to this capture, never to the previous response.
                                for key in ("sha256", "size", "mediaType", "name", "acquiredAt", "byteBasis", "versionNote"):
                                    attachment[key] = preserved[key]
                                attachment.update(status="saved", reason=None)
                            except (OSError, ValueError):
                                pass
                else:
                    attachment["reason"] = "此历史保存版本未归档附件；没有用当前原文件冒充历史字节。"
                attachments.append(attachment)
    # Restore global source order after collecting the existing display groups.
    order = {(e["turnId"], e["id"]): e["order"] for group in ("messages", "tools", "unsupportedItems") for e in session.get(group, [])}
    attachments.sort(key=lambda a: order[(a["turnId"], a["itemId"])])
    session["attachments"] = attachments


def attachment_view(package: dict[str, Any], data_dir: Path) -> None:
    session = package["session"]
    if "attachments" not in session:
        archive_attachments(package, data_dir, acquire=False)
    for attachment in session["attachments"]:
        if attachment["status"] == "saved":
            try:
                read_copy(data_dir, attachment)
            except (OSError, ValueError) as exc:
                attachment.update(status="missing", reason="受管理副本不可取得：" + str(exc))
        query = urlencode({"source": session["source"]["instance"], "saved": session["savedAt"]})
        attachment["url"] = f'/attachment/{quote(session["id"], safe="")}/{attachment["id"]}?{query}' if attachment["status"] == "saved" else None
    session["attachmentSummary"] = {"saved": sum(a["status"] == "saved" for a in session["attachments"]),
        "missing": sum(a["status"] != "saved" for a in session["attachments"]),
        "note": "附件状态只说明明确引用的原字节是否取得；对话文本与附件分别核对，不宣称完整原生备份。"}
