from __future__ import annotations

from html import escape
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
import sqlite3
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from .app import Journal
from .sync import Collector


STYLE = """
:root{color-scheme:light;--paper:#fff;--ground:#eef2f6;--ink:#172b3a;--muted:#526676;--accent:#155c9c;--line:#d1dce5;--user:#edf4fc}
*{box-sizing:border-box}html{scroll-padding-top:24px}body{margin:0;background:var(--ground);color:var(--ink);font:16px/1.75 'Segoe UI','Microsoft YaHei',sans-serif}
a{color:var(--accent);text-underline-offset:3px}a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:4px}a:hover{text-decoration-thickness:2px}
header{background:var(--paper);border-top:5px solid var(--accent);border-bottom:1px solid var(--line);padding:18px max(24px,calc((100vw - 1240px)/2))}header strong{font-size:18px;letter-spacing:.06em}header span{margin-left:22px;color:var(--muted);font-size:14px}
main{max-width:1240px;margin:30px auto;padding:0 24px}h1{font-size:30px;line-height:1.4;margin:10px 0}h2{font-size:21px;line-height:1.6}h3{font-size:17px}p{margin:8px 0 16px}.muted{color:var(--muted)}.eyebrow{font:13px/1.6 Consolas,monospace;letter-spacing:.08em;color:var(--muted)}
.heading{display:flex;justify-content:space-between;align-items:start;gap:28px;margin-bottom:24px}.heading>div{min-width:0}.heading h1{overflow-wrap:anywhere}.action{display:inline-block;background:var(--accent);color:#fff;padding:10px 20px;border-radius:5px;text-decoration:none;white-space:nowrap;font-weight:600}
.layout{display:grid;grid-template-columns:215px minmax(0,1fr);gap:32px}.sidebar{position:sticky;top:20px;align-self:start;font-size:14px}.sidebar nav{display:grid;gap:3px;margin:12px 0 25px}.sidebar nav a{display:block;padding:8px 10px;text-decoration:none;border-left:2px solid var(--line)}.sidebar nav a:hover{background:var(--paper);border-color:var(--accent)}
.source{border:1px solid var(--line);background:var(--paper);border-radius:6px;padding:16px 20px;margin:0 0 24px;font-size:14px}.source summary{cursor:pointer;font-weight:600}.source dl{display:grid;grid-template-columns:100px minmax(0,1fr);gap:7px 16px}.source dt{color:var(--muted)}.source dd{margin:0;overflow-wrap:anywhere}.source ul{padding-left:22px}.source code{font-size:12px}
.turn{scroll-margin-top:24px;margin:0 0 38px}.turn>h2{display:flex;align-items:baseline;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line);padding-bottom:10px}.turn-status{font-size:13px;font-weight:400;color:var(--muted)}
.message{background:var(--paper);border:1px solid var(--line);border-radius:6px;margin:14px 0;padding:18px 22px}.message.user{background:var(--user);border-left:4px solid var(--accent)}.message summary{cursor:pointer;list-style-position:outside;margin-left:16px}.message .label{font-size:14px;font-weight:650}.phase{color:var(--muted);font-size:12px;margin-left:14px;font-weight:400}.message pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.9 'Segoe UI','Microsoft YaHei',sans-serif;margin:18px 0}.message footer{font-size:12px;line-height:1.7;border-top:1px solid var(--line);padding-top:12px;color:var(--muted);overflow-wrap:anywhere}.message footer code{display:block;font:11px/1.8 Consolas,monospace;margin-top:6px}.gap{font-size:13px;color:#80520d;margin:10px 0}.session-list{list-style:none;padding:0}.session-list li{background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:20px;margin:12px 0}.session-list h2{margin:0 0 8px}.empty{padding:40px;background:var(--paper);border:1px solid var(--line)}.empty code{overflow-wrap:anywhere}.count{font-size:13px;color:var(--muted)}
@media(max-width:760px){main{padding:0 16px;margin:20px auto}.layout{display:block}.sidebar{position:static;margin-bottom:24px}.sidebar nav{display:flex;overflow-x:auto}.sidebar nav a{white-space:nowrap;border-left:0;border-bottom:2px solid var(--line)}.heading{display:block}.heading .action{margin:10px 0}.message{padding:15px}h1{font-size:24px}header{padding:14px 16px}header span{display:block;margin:4px 0}.source dl{grid-template-columns:1fr;gap:2px}.source dd{margin-bottom:10px}}
"""


def page(title: str, body: str) -> str:
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · 本机会话记录</title><style>{STYLE}</style><script src="/live.js" defer></script></head><body><header><strong>本机会话记录</strong><span>多项目自动归档 · 任务 03 · 分组阅读</span></header><main>{body}</main></body></html>'


LIVE_SCRIPT = """
let version = null;
async function update() {
  try {
    const response = await fetch('/api/version');
    if (!response.ok) throw new Error();
    const current = (await response.json()).version;
    if (version !== null && current !== version && !window.getSelection().toString()) {
      const html = await fetch(location.pathname + location.search);
      if (!html.ok) throw new Error();
      const next = new DOMParser().parseFromString(await html.text(), 'text/html');
      const states = new Map([...document.querySelectorAll('details[data-key]')].map(d => [d.dataset.key, d.open]));
      for (const detail of next.querySelectorAll('details[data-key]')) {
        if (states.has(detail.dataset.key)) detail.open = states.get(detail.dataset.key);
      }
      const position = window.scrollY;
      const focused = document.activeElement?.closest('details[data-key]')?.dataset.key;
      document.querySelector('main').replaceWith(next.querySelector('main'));
      if (focused) {
        [...document.querySelectorAll('details[data-key]')].find(d => d.dataset.key === focused)?.querySelector('summary')?.focus({preventScroll:true});
      }
      window.scrollTo(0, position);
    }
    version = current;
    document.getElementById('connection-error')?.remove();
  } catch {
    if (!document.getElementById('connection-error')) {
      const warning = document.createElement('p');
      warning.id = 'connection-error'; warning.className = 'source gap';
      warning.textContent = '与本地服务失去连接，采集状态无法确认；当前保留的是已加载记录。重新启动服务后自动重连。';
      document.querySelector('main').prepend(warning);
    }
  }
  setTimeout(update, 1500);
}
update();
"""


def source_time(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "未知"
    return datetime.fromtimestamp(value, timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S +08:00")


def saved_time(value: Any) -> str:
    return source_time(datetime.fromisoformat(value).timestamp()) if value else "尚无"


def collection_html(status: dict[str, Any]) -> str:
    running = "采集运行中" if status.get("running") else "采集已停止／此页面服务未运行采集器"
    availability = "来源不可用" if status.get("sourceAvailable") is False else "来源可访问" if status.get("sourceAvailable") else "等待来源检查"
    if status.get("sourceAvailable") and status.get("discoveredCount") == 0:
        availability += " · 确实没有会话"
    rows = [f'<li>会话 {escape(s["id"])}：{escape(s["error"])}</li>' for s in status.get("sessions", []) if s.get("error")]
    saved = sum(s.get("status") == "saved" for s in status.get("sessions", []))
    error = escape(status.get("error") or "无来源级错误")
    return (f'<section class="source" aria-label="采集运行状态"><strong>{running} · {availability}</strong>'
            f'<p>最近成功归档检查：{saved_time(status.get("lastSuccessAt"))} · 最近来源成功检查：{saved_time(status.get("lastSourceSuccessAt"))}</p>'
            f'<p>上次完整检查发现 {status.get("discoveredCount", 0)} 个会话；范围内保存成功 {saved} 个，失败 {len(rows)} 个。最近检查：{saved_time(status.get("lastCheckedAt"))}。当前来源错误：{error}</p>'
            f'<ul>{"".join(rows)}</ul><p class="muted">首次启用：{source_time(status.get("enabledAt"))}。只读取启用后开始的回合；旧会话的新回合会自动采集，跨启用时刻的旧回合不回补。来源只提供整秒时，启用同秒无法区分先后的回合也不读取；开始时间未知会报告错误。页面关闭后，仍在运行的采集服务继续工作。</p></section>')


def display_value(value: Any) -> str:
    if value is None:
        return "未知／未取得"
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)


def tool_html(tool: dict[str, Any], thread: str, query: str) -> str:
    statuses = {"completed": "执行已完成（不代表业务成功）", "failed": "执行失败", "inProgress": "进行中（未取得最终结果）", "declined": "已拒绝", "unknown": "状态未知"}
    name = ".".join(str(v) for v in (tool["namespace"], tool["name"]) if v is not None)
    body = f'<details class="message tool" data-key="{thread}:{escape(tool["turnId"], quote=True)}:tool:{escape(tool["id"], quote=True)}" data-tool-id="{escape(tool["id"], quote=True)}"><summary><span class="label">工具执行 · {escape(name or "名称未知")}</span><span class="phase">{statuses[tool["status"]]} · {"部分内容" if tool["completeness"] == "partial" else "完整性未知"}</span></summary>'
    for label, value in (("来源类型", tool["type"]), ("来源执行状态", tool["sourceStatus"]),
                         ("退出码", tool["exitCode"]), ("耗时（毫秒）", tool["durationMs"]),
                         ("开始时间（来源 Unix 毫秒）", tool["startedAtMs"]), ("结束时间（来源 Unix 毫秒）", tool["completedAtMs"]),
                         ("参数（来源已提供）", "null" if tool.get("argumentsAvailable") and tool["arguments"] is None else tool["arguments"]), ("结果原文（已取得的全部内容）", tool["result"]),
                         ("错误信息", tool["error"]), ("来源 success 字段", tool["sourceSuccess"])):
        body += f'<h3>{label}</h3><pre>{escape(display_value(value))}</pre>'
    body += '<p class="gap">业务／任务成功：未知。嵌套调用未独立返回时，不从文本推造调用树。</p>'
    body += ''.join(f'<p class="gap">{escape(r)}</p>' for r in tool["reasons"])
    index = tool["evidenceRef"].split("/")[2]
    return body + f'<footer><a href="/evidence/{thread}/{index}{query}" target="_blank" rel="noopener">查看工具原始证据 ↗</a><code>来源身份：{escape(tool["id"])}<br>关联依据：{escape(tool["association"])}<br>导出位置：{escape(tool["evidenceRef"])}</code></footer></details>'


def session_body(session: dict[str, Any]) -> str:
    source = session["source"]
    thread = quote(session["id"], safe="")
    query = "?source=" + quote(source["instance"], safe="")
    evidence_query = query + "&amp;saved=" + quote(session["savedAt"], safe="")
    links = "".join(f'<a href="#turn-{i}">回合 {i + 1}</a>' for i, _ in enumerate(session["turns"]))
    body = f'<div class="heading"><div><a href="/">← 项目列表</a><h1>{escape(session["name"] or session["id"])}</h1><p>来源会话开始：{source_time(session.get("createdAt", session["thread"].get("createdAt")))}</p><p class="count">{len(session["turns"])} 个回合 · {len(session["messages"])} 条用户与 AI 消息 · {len(session.get("tools", []))} 次工具记录 · 任务 03 自动归档 · 分组阅读</p><p class="count">历史证据修订随完整结构化导出保留；首次范围前的回合未回补。</p></div><a class="action" href="/export/{thread}{query}">结构化导出 ↓</a></div>'
    body += f'<div class="layout"><aside class="sidebar"><span class="eyebrow">回合索引</span><nav aria-label="回合索引">{links}</nav><p class="muted">按对话与执行过程分组阅读，组内保留来源顺序。分组位置不代表所有事件的原始交错顺序；完整顺序可在导出和原始证据中核对。</p></aside><div>'
    gaps = "".join(f'<li>{escape(gap)}</li>' for gap in source["gaps"])
    body += f'<details class="source" data-key="{thread}:source"><summary>数据源版本与已知缺口</summary><dl><dt>数据源版本</dt><dd>{escape(str(source["version"]))}</dd><dt>保存时间</dt><dd>{escape(session["savedAt"])}</dd><dt>来源实例</dt><dd><code>{escape(source["instance"])}</code></dd><dt>会话身份</dt><dd><code>{escape(session["id"])}</code></dd><dt>已读取</dt><dd>{session["sourceItemCount"]} 条来源条目；完整视图；回合 {source["pagination"]["turnPages"]} 页、条目 {source["pagination"]["itemPages"]} 页</dd><dt>仅存原始证据</dt><dd>{escape(", ".join(source["notDisplayedTypes"]) or "无")}</dd></dl><ul>{gaps}</ul></details>'
    labels = {"commentary": "AI 过程消息", "final_answer": "AI 最终回答"}
    statuses = {"completed": "已完成", "interrupted": "已中断", "inProgress": "进行中", "failed": "失败"}
    for index, turn in enumerate(session["turns"]):
        status = statuses.get(turn.get("status"), "状态未知")
        body += f'<section class="turn" id="turn-{index}"><h2>回合 {index + 1}<span class="turn-status">{status}</span></h2>'
        entries = session["messages"] + session.get("tools", []) + session.get("unsupportedItems", [])
        execution_html = ""
        execution_count = 0
        for message in sorted((m for m in entries if m["turnId"] == turn["id"]), key=lambda m: m["order"]):
            if "association" in message:
                execution_html += tool_html(message, thread, evidence_query)
                execution_count += 1
                continue
            if message["type"] not in ("userMessage", "agentMessage"):
                evidence_index = message["evidenceRef"].split("/")[2]
                execution_html += f'<details class="message" data-key="{thread}:{escape(turn["id"], quote=True)}:unsupported:{escape(message["id"], quote=True)}"><summary>不支持的条目 · {escape(message["type"])} · 完整性未知</summary><p>{escape(message["reasons"][0])}</p><a href="/evidence/{thread}/{evidence_index}{evidence_query}" target="_blank" rel="noopener">查看未支持条目的原始证据 ↗</a><footer><code>{escape(message["id"])}<br>导出位置：{escape(message["evidenceRef"])}</code></footer></details>'
                execution_count += 1
                continue
            user = message["type"] == "userMessage"
            label = "用户原文" if user else labels.get(message["phase"], "AI 消息 · 阶段未知")
            evidence_index = message["evidenceRef"].split("/")[2]
            completeness = {"complete": "已取得文本", "partial": "部分内容", "unknown": "完整性未知"}[message["completeness"]]
            body += f'<details open data-key="{thread}:{escape(turn["id"], quote=True)}:message:{escape(message["id"], quote=True)}" class="message {"user" if user else "agent"}"><summary><span class="label">{label}</span><span class="phase">{completeness}</span></summary><pre>{escape(message["text"])}</pre>'
            for reason in message["reasons"]:
                body += f'<p class="gap">{escape(reason)}</p>'
            message_time = source_time(message["startedAtMs"] / 1000 if message["startedAtMs"] is not None else None)
            body += f'<footer><a href="/evidence/{thread}/{evidence_index}{evidence_query}" target="_blank" rel="noopener">查看原始证据 ↗</a> · 来源时间：{escape(message_time)}<code>{escape(message["id"])}<br>导出位置：{escape(message["evidenceRef"])}</code></footer></details>'
        if execution_count:
            body += f'<details class="source execution" data-key="{thread}:{escape(turn["id"], quote=True)}:execution"><summary>执行过程 · {execution_count} 条来源记录</summary><p class="muted">工具与其他非对话条目，按本回合的来源顺序排列；文档正文保留在读取它的工具结果中。</p>{execution_html}</details>'
        body += '</section>'
    return body + '</div></div>'


def session_page(session: dict[str, Any]) -> str:
    return page("原文时间线", session_body(session))


def create_server(app: Journal, port: int = 8765, collector: Collector | None = None) -> ThreadingHTTPServer:
    def status() -> dict[str, Any]:
        return collector.status() if collector else {**app.collection_state(), "running": False}

    class Handler(BaseHTTPRequestHandler):
        server: ThreadingHTTPServer

        def do_GET(self) -> None:
            local_port = self.server.server_port
            allowed_hosts = {f"127.0.0.1:{local_port}", f"localhost:{local_port}"}
            host = self.headers.get("Host", "")
            if host not in allowed_hosts or self.headers.get("Origin") not in (None, "http://" + host):
                self.respond(403, "text/plain", "仅允许本机同源访问。")
                return
            url = urlsplit(self.path)
            segments = [unquote(p) for p in url.path.strip("/").split("/")]
            instance = parse_qs(url.query).get("source", [None])[0]
            try:
                if url.path == "/":
                    projects = app.projects()
                    items = ''.join(f'<li><h2><a href="/project/{p["id"]}">{escape(p["label"])}</a></h2><p>{len(p["sessions"])} 个已保存会话 · 归属依据：{escape(p["basis"])}</p></li>' for p in projects)
                    empty = '<div class="empty"><h2>尚无范围内已保存的会话</h2><p>采集服务启动后会自动发现所有项目的新回合，无需手动导入或同步。来源运行情况见上方。</p></div>' if not items else ""
                    self.respond(200, "text/html", page("项目归档", collection_html(status()) + '<h1>项目归档</h1><p class="muted">同项目按会话开始时间升序，完整阅读每段会话。未知时间排在已知时间后；时间相同或未知时按来源实例、会话 ID 排序。较早会话更新不改变位置。</p><ul class="session-list">' + items + '</ul>' + empty))
                elif url.path == "/live.js":
                    self.respond(200, "text/javascript", LIVE_SCRIPT)
                elif url.path == "/api/status":
                    self.respond(200, "application/json", json.dumps(status(), ensure_ascii=False))
                elif url.path == "/api/projects":
                    self.respond(200, "application/json", json.dumps(app.projects(), ensure_ascii=False))
                elif url.path == "/api/version":
                    content = json.dumps([app.sessions(), status()], ensure_ascii=False)
                    self.respond(200, "application/json", json.dumps({"version": hashlib.sha256(content.encode()).hexdigest()}))
                elif len(segments) == 2 and segments[0] == "project":
                    project = next((p for p in app.projects() if p["id"] == segments[1]), None)
                    if project is None:
                        raise KeyError("项目尚未保存")
                    content = collection_html(status()) + f'<a href="/">← 项目列表</a><h1>{escape(project["label"])}</h1><p>以下按来源会话开始时间升序完整排列。未知时间在后，同时间以来源实例、会话 ID 排序。</p>'
                    for summary in project["sessions"]:
                        session = app.session(summary["id"], summary["source"]["instance"])
                        # Each session retains its own whole timeline and unique turn anchors.
                        fragment = session_body(session)
                        prefix = quote(summary["source"]["instance"] + '-' + summary["id"], safe="")
                        fragment = fragment.replace('href="#turn-', f'href="#{prefix}-turn-').replace('id="turn-', f'id="{prefix}-turn-')
                        content += f'<article data-session-id="{escape(summary["id"], quote=True)}">{fragment}</article>'
                    self.respond(200, "text/html", page(project["label"], content))
                elif url.path == "/api/sessions":
                    self.respond(200, "application/json", json.dumps(app.sessions(), ensure_ascii=False))
                elif len(segments) == 3 and segments[:2] == ["api", "session"]:
                    self.respond(200, "application/json", json.dumps(app.session(segments[2], instance), ensure_ascii=False))
                elif len(segments) == 2 and segments[0] == "session":
                    self.respond(200, "text/html", page("原文时间线", collection_html(status()) + session_body(app.session(segments[1], instance))))
                elif len(segments) == 2 and segments[0] == "export":
                    self.respond(200, "application/json", app.export_session(segments[1], instance), download=True)
                elif len(segments) == 3 and segments[0] == "evidence" and segments[2].isdigit():
                    saved_at = parse_qs(url.query).get("saved", [None])[0]
                    evidence = app.evidence(segments[1], int(segments[2]), instance, saved_at)
                    self.respond(200, "application/json", json.dumps(evidence, ensure_ascii=False, indent=2))
                else:
                    self.respond(404, "text/plain", "找不到这个页面。")
            except (KeyError, IndexError):
                self.respond(404, "text/plain", "本机未保存这个会话或证据。")
            except ValueError as exc:
                self.respond(400, "text/plain", str(exc))
            except (OSError, sqlite3.Error):
                self.respond(500, "text/plain", "本机存储读取失败，请检查数据目录。")

        def respond(self, status: int, content_type: str, body: str, download: bool = False) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="session.json"')
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            # No prompts or evidence paths in server access logs.
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
