"""Self-contained ZIP packaging of the existing scoped JSON export."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
import zipfile

from .attachments import read_copy


INSTRUCTIONS = """离线会话包 v1

解压整个 ZIP 到任意新目录。无需日志服务、原数据库、原附件或网络。

session.json：既有结构化导出（schemaVersion 保持兼容），包含原始 evidence、
消息、工具状态、保存修订、关系及 exportScope。一层范围不会递归。
如果 session.source.retention 为 dialogue-only-v1，仅包含消息及其来源摘录、
消息附件与保存版本；工具及不支持条目已按用户要求移除，不包含完整协议响应。
manifest.json：包格式版本、各保存版本的附件与来源关系、实际文件校验及缺失。
attachments/：取得的原始字节。名字为校验身份，显示名在附件 name 中。

从 session.attachments 或 revisions/related 内的 attachments 找到条目，
bundlePath 相对于此目录；evidenceRef 是 session.json 内 JSON Pointer。
原始证据中的绝对路径／URL 仅为来源信息，不是离线文件位置。
manifest.missing 中未取得内容不在此包；文本取得不代表完整原生备份。
旧快照没有归档的附件不会被当前文件冒充。内容相同不合并来源记录。
附件打开不需要执行；普通文件按原字节保存，使用适当本机查看器核对。

PowerShell 中进入解压目录，核对实际文件与 manifest.files：
$manifest = Get-Content -LiteralPath ./manifest.json -Raw -Encoding utf8 | ConvertFrom-Json
$manifest.files | ForEach-Object {
    $file = Get-Item -LiteralPath $_.path
    $hash = (Get-FileHash -LiteralPath $_.path -Algorithm SHA256).Hash.ToLower()
    [pscustomobject]@{Path=$_.path; Bytes=$file.Length; Valid=($hash -eq $_.sha256 -and $file.Length -eq $_.size)}
}

校验表只能检测包内一致性；需要证明原字节时还应对照归档前独立保存的校验清单。
"""


def build_bundle(package: dict[str, Any], data_dir: Path) -> bytes:
    output = io.BytesIO()
    manifest: dict[str, Any] = {"bundleVersion": 1, "record": "session.json",
        "representation": "规范化会话及来源证据；实际保留范围见各版本 session.source.retention，不是底层原生数据库的完整备份。",
        "exportScope": package["exportScope"], "attachments": [], "missing": [], "files": []}
    files: dict[str, bytes] = {}

    def visit(document: dict[str, Any], prefix: str) -> None:
        session = document["session"]
        for index, attachment in enumerate(session.get("attachments", [])):
            attachment.pop("url", None)
            path = None
            if attachment["status"] == "saved":
                try:
                    data = read_copy(data_dir, attachment)
                    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}.get(attachment["mediaType"], ".bin")
                    path = f'attachments/{attachment["sha256"]}{suffix}'
                    if path not in files:
                        files[path] = data
                        manifest["files"].append({"path": path, "sha256": attachment["sha256"], "size": len(data)})
                except (OSError, ValueError) as exc:
                    attachment.update(status="missing", reason="导出时受管理副本不可取得：" + str(exc))
            attachment["bundlePath"] = path
            record = {**attachment, "savedAt": session["savedAt"], "project": session["project"],
                      "recordRef": f"session.json{prefix}/session/attachments/{index}"}
            manifest["attachments"].append(record)
            if path is None:
                manifest["missing"].append(record)
        session["attachmentSummary"] = {"saved": sum(a["status"] == "saved" for a in session["attachments"]),
            "missing": sum(a["status"] != "saved" for a in session["attachments"]),
            "note": "原字节与缺失分别列出；不宣称完整原生备份。"}
        for index, revision in enumerate(document.get("revisions", [])):
            visit(revision, f"{prefix}/revisions/{index}")
        for index, related in enumerate(document.get("related", [])):
            visit(related, f"{prefix}/related/{index}")

    visit(package, "#")
    package["offlineBundle"] = {"version": 1, "manifest": "manifest.json", "pathBase": "."}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("session.json", json.dumps(package, ensure_ascii=False, indent=2))
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("README.txt", INSTRUCTIONS)
        for path, data in files.items():
            archive.writestr(path, data)
    return output.getvalue()
