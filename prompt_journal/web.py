from __future__ import annotations

from html import escape
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
import io
import zipfile
import sqlite3
import secrets
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlencode

from .app import Journal
from .sync import Collector
from .search import item_anchor, searchable_fields
from .attachments import content_type
from .presentation import STYLE, icon


LAZY_TEXT_LIMIT = 64 * 1024


def project_name(label: str) -> str:
    return label.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or label


def page(title: str, body: str, reading: bool = False, active: str = 'projects',
         projects: list[dict[str, Any]] | None = None, project_id: str | None = None) -> str:
    main_class = ' class="reader"' if reading else ''
    current_project = ' aria-current="true"' if active == 'projects' else ''
    search_current = ' aria-current="true"' if active == 'search' else ''
    status_current = ' aria-current="true"' if active == 'status' else ''
    manage_current = ' aria-current="true"' if active == 'manage' else ''
    project_links = ''
    names = [project_name(p['label']) for p in projects or []]
    for project in projects or []:
        selected = ' aria-current="page"' if project['id'] == project_id else ''
        label = project['label']
        short_name = project_name(label)
        name = f'{short_name} · {label}' if names.count(short_name) > 1 else short_name
        project_links += f'<a href="/project/{quote(project["id"], safe="")}" title="{escape(label, quote=True)}"{selected}>{icon("folder")}<span>{escape(name)}</span></a>'
    header = (f'<header class="app-header"><a class="brand" href="/">{icon("brand")}<strong>本机会话记录</strong></a>'
              f'<nav class="primary-nav" aria-label="主要导航"><a href="/"{current_project}>{icon("folder")}项目</a>'
              f'<a href="/search"{search_current}>{icon("search")}搜索</a><a href="/status"{status_current}>{icon("check")}采集状态</a>'
              f'<a href="/manage/exclusions"{manage_current}>{icon("trash")}删除管理</a></nav>'
              f'<div class="project-nav"><p>项目列表</p>{project_links}</div>'
              '<a class="capacity-card" href="/capacity"><strong>数据库容量</strong><span id="capacity-label">正在读取</span><span class="capacity-track"><span id="capacity-progress"></span></span></a>'
              '<span id="collection-indicator" class="collection-indicator" aria-live="polite">正在检查</span></header>')
    search = f'<form class="header-search" action="/search" method="get" aria-label="全局正文搜索">{icon("search")}<input type="search" name="q" aria-label="全局搜索正文" placeholder="搜索已保存正文"></form>'
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · 本机会话记录</title><style>{STYLE}</style><script src="/live.js" defer></script></head><body><a class="skip-link" href="#main">跳到正文</a>{header}<div class="app-content">{search}<main id="main" tabindex="-1"{main_class}>{body}</main></div></body></html>'


LIVE_SCRIPT = """
let version = null;
async function loadLazyContent(node) {
  if (!node?.dataset.lazyUrl || node.dataset.lazyLoaded === 'true') return;
  node.dataset.lazyLoaded = 'loading';
  try {
    const response = await fetch(node.dataset.lazyUrl);
    if (!response.ok) throw new Error();
    const payload = await response.json();
    node.textContent = payload.text;
    node.classList.remove('lazy-content');
    node.dataset.lazyLoaded = 'true';
  } catch {
    node.textContent = '原文加载失败；请重试或打开原始证据。';
    node.dataset.lazyLoaded = 'error';
  }
}
async function loadLazyInDetails(details) {
  if (!details) return;
  for (const node of details.querySelectorAll(':scope > [data-lazy-url]')) await loadLazyContent(node);
}
async function locateHit() {
  const params = new URLSearchParams(location.search);
  const target = document.getElementById(params.get('target'));
  if (!target) return;
  for (let node = target; node; node = node.parentElement) {
    if (node.tagName === 'DETAILS') node.open = true;
  }
  await loadLazyInDetails(target.closest('details'));
  const query = params.get('q');
  let focus = target;
  if (query) for (const pre of target.querySelectorAll('pre[data-search]')) {
    if (pre.dataset.search !== params.get('field')) continue;
    const text = pre.textContent, position = text.indexOf(query);
    if (position < 0) continue;
    const mark = document.createElement('mark');
    mark.textContent = query;
    pre.replaceChildren(document.createTextNode(text.slice(0, position)), mark, document.createTextNode(text.slice(position + query.length)));
    focus = mark;
    break;
  }
  focus.scrollIntoView({block:'center'});
}
document.addEventListener('toggle', event => {
  if (event.target instanceof HTMLDetailsElement && event.target.open) loadLazyInDetails(event.target);
}, true);
window.addEventListener('load', () => requestAnimationFrame(locateHit), {once:true});
window.addEventListener('load', async () => {
  if (!/^\\/session\\/[^/]+$/.test(location.pathname)) return;
  const old = /^#turn-(\\d+)$/.exec(location.hash);
  if (!old) return;
  const selector = '[data-turn-ordinal="' + (Number(old[1]) + 1) + '"]';
  let link = document.querySelector(selector);
  if (!link) {
    const url = new URL(location.href);
    url.searchParams.set('offset', old[1]);
    try {
      const response = await fetch(url.pathname + url.search);
      if (!response.ok) return;
      link = new DOMParser().parseFromString(await response.text(), 'text/html').querySelector(selector);
    } catch {return;}
  }
  if (link) location.replace(link.getAttribute('href'));
}, {once:true});
async function loadSessionOptions(form, more = false) {
  const select = form.querySelector('[data-session-options]');
  if (!select) return;
  form.sessionRequest?.abort();
  const request = new AbortController();
  form.sessionRequest = request;
  select.dataset.loading = 'true';
  const button = form.querySelector('[data-session-more]');
  try {
    const params = new URLSearchParams({limit:'100', offset:more ? select.dataset.next || '0' : '0'});
    const project = form.elements.project.value;
    const query = form.querySelector('[data-session-filter]').value;
    if (project) params.set('project', project);
    if (query) params.set('q', query);
    const response = await fetch('/api/catalog?' + params, {signal:request.signal});
    if (!response.ok) throw new Error();
    const result = await response.json();
    if (form.sessionRequest !== request || !select.isConnected) return;
    if (!more) for (const option of [...select.options]) if (option.value && !option.selected) option.remove();
    const normalize = value => {try {return JSON.stringify(JSON.parse(value));} catch {return value;}};
    const existing = new Set([...select.options].map(option => normalize(option.value)));
    for (const session of result.sessions) {
      const value = JSON.stringify([session.source.instance, session.id]);
      if (!existing.has(value)) {
        select.add(new Option((session.name || session.id) + ' · ' + session.id + ' · 来源 ' + session.source.instance.slice(0,8), value));
      }
    }
    select.dataset.loaded = 'true';
    select.dataset.next = result.nextOffset ?? '';
    button.hidden = result.nextOffset === null;
    button.textContent = '加载更多会话';
  } catch (error) {
    if (form.sessionRequest !== request || error.name === 'AbortError') return;
    button.hidden = false;
    button.textContent = '重试加载会话';
  } finally { if (form.sessionRequest === request) select.dataset.loading = 'false'; }
}
document.addEventListener('focusin', event => {
  if (event.target.matches('[data-session-options]') && event.target.dataset.loaded !== 'true') loadSessionOptions(event.target.form);
});
document.addEventListener('change', event => {
  if (!event.target.matches('.search-form select[name="project"]')) return;
  const select = event.target.form.querySelector('[data-session-options]');
  select.replaceChildren(new Option('所有已保存会话', ''));
  select.dataset.loaded = 'false';
  event.target.form.querySelector('[data-session-more]').hidden = true;
  loadSessionOptions(event.target.form);
});
document.addEventListener('input', event => {
  if (event.target.matches('[data-session-filter]')) {
    clearTimeout(event.target.sessionTimer);
    event.target.sessionTimer = setTimeout(() => loadSessionOptions(event.target.form), 200);
  }
});
function selectDirectoryGroup(group) {
  if (group) {
    const info = document.querySelector('.session-info');
    if (info) info.dataset.selected = group.dataset.key;
    for (const entry of document.querySelectorAll('.session-group')) entry.classList.toggle('selected', entry === group);
    if (info) for (const field of ['name', 'started', 'count', 'source', 'saved']) {
      const value = info.querySelector('[data-info="' + field + '"]');
      if (value) value.textContent = group.dataset[field] || '未知';
    }
  }
}
document.addEventListener('submit', event => {
  if (event.target.id !== 'session-selection') return;
  if (!document.querySelector('[data-session-choice]:checked')) {
    event.preventDefault();
    let notice = document.getElementById('selection-notice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'selection-notice';
      notice.className = 'selection-notice';
      notice.setAttribute('role', 'status');
      document.body.append(notice);
    }
    clearTimeout(notice.hideTimer);
    notice.textContent = '请选择会话';
    notice.classList.add('visible');
    notice.hideTimer = setTimeout(() => notice.classList.remove('visible'), 2000);
  }
});
let atlasRequest = 0;
let atlasController = null;
async function loadAtlasTurn(link) {
  const request = ++atlasRequest;
  atlasController?.abort();
  const controller = new AbortController();
  atlasController = controller;
  const timeout = setTimeout(() => controller.abort(), 20000);
  const content = document.querySelector('[data-reader-content]');
  const status = document.querySelector('[data-reader-status]');
  const open = document.querySelector('[data-reader-open]');
  for (const item of document.querySelectorAll('[data-atlas-turn]')) {
    item.classList.toggle('selected', item === link);
    if (item === link) item.setAttribute('aria-current', 'true');
    else item.removeAttribute('aria-current');
  }
  document.querySelector('[data-reader-title]').textContent = '回合 ' + link.dataset.turnOrdinal;
  content.replaceChildren();
  content.setAttribute('aria-busy', 'true');
  status.textContent = '正在加载回合正文…';
  open.href = link.href;
  open.hidden = false;
  try {
    const url = new URL(link.href);
    url.searchParams.set('view', 'reader');
    const response = await fetch(url, {signal:controller.signal});
    if (!response.ok) throw new Error();
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    const turn = doc.querySelector('.turn');
    if (!turn) throw new Error();
    if (request !== atlasRequest) return;
    const versionNote = doc.querySelector('[data-reader-version]');
    content.replaceChildren(...[versionNote, turn].filter(Boolean));
    status.textContent = '';
    content.closest('.atlas-reader').scrollTop = 0;
    for (const node of content.querySelectorAll('[data-lazy-url]')) {
      let visible = true;
      for (let parent = node.parentElement; parent && parent !== content; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS' && !parent.open) visible = false;
      }
      if (visible) loadLazyContent(node);
    }
  } catch {
    if (request !== atlasRequest) return;
    status.textContent = '正文加载失败，请重试或打开独立页面。';
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.dataset.readerRetry = '';
    retry.textContent = '重试加载';
    content.replaceChildren(retry);
  } finally {
    clearTimeout(timeout);
    if (request === atlasRequest) content.setAttribute('aria-busy', 'false');
  }
}
document.addEventListener('click', event => {
  const sessionButton = event.target.closest('[data-select-group]');
  if (sessionButton) {
    atlasRequest++;
    atlasController?.abort();
    const id = sessionButton.dataset.selectGroup;
    for (const row of document.querySelectorAll('.atlas-session-row')) row.classList.toggle('selected', row.dataset.group === id);
    for (const button of document.querySelectorAll('[data-select-group]')) button.setAttribute('aria-pressed', String(button === sessionButton));
    for (const link of document.querySelectorAll('[data-atlas-turn]')) {
      link.classList.remove('selected');
      link.removeAttribute('aria-current');
    }
    for (const group of document.querySelectorAll('[data-turn-group]')) group.hidden = group.dataset.turnGroup !== id;
    const group = document.querySelector('[data-turn-group="' + id + '"]');
    document.querySelector('[data-atlas-name]').textContent = group.dataset.name;
    document.querySelector('[data-atlas-meta]').textContent = group.dataset.meta;
    document.querySelector('[data-atlas-source]').textContent = group.dataset.source;
    document.querySelector('[data-reader-title]').textContent = '回合正文';
    const content = document.querySelector('[data-reader-content]');
    content.replaceChildren();
    content.setAttribute('aria-busy', 'false');
    document.querySelector('[data-reader-status]').textContent = '选择一个回合，正文将在这里显示。';
    document.querySelector('[data-reader-open]').hidden = true;
    return;
  }
  if (event.target.closest('[data-reader-retry]')) {
    const selected = document.querySelector('[data-atlas-turn][aria-current]');
    if (selected) loadAtlasTurn(selected);
    return;
  }
  const link = event.target.closest('[data-atlas-turn]');
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
  event.preventDefault();
  loadAtlasTurn(link);
});
document.addEventListener('focusin', event => selectDirectoryGroup(event.target.closest('.session-group')));
document.addEventListener('click', event => {
  if (event.target.matches('[data-session-more]')) loadSessionOptions(event.target.form, true);
  selectDirectoryGroup(event.target.closest('.session-group'));
});
async function update() {
  try {
    const response = await fetch('/api/version');
    if (!response.ok) throw new Error();
    const status = await response.json();
    const current = status.version;
    const capResponse = await fetch('/api/capacity');
    if (capResponse.ok) {
      const capacity = await capResponse.json();
      const label = document.getElementById('capacity-label');
      const bar = document.getElementById('capacity-progress');
      const format = bytes => bytes >= 1073741824 ? (bytes / 1073741824).toFixed(2) + ' GiB' : (bytes / 1048576).toFixed(1) + ' MiB';
      if (label && bar) {
        const ratio = capacity.limitBytes ? capacity.usedBytes / capacity.limitBytes : 0;
        label.textContent = format(capacity.usedBytes) + (capacity.limitBytes ? ' / ' + format(capacity.limitBytes) : ' · 未设上限') + (capacity.paused ? ' · 新会话暂停' : '');
        bar.style.width = Math.min(100, ratio * 100) + '%';
        bar.dataset.state = ratio >= 1 ? 'full' : ratio > .8 ? 'warning' : 'normal';
      }
    }
    const indicator = document.getElementById('collection-indicator');
    if (indicator) {
      indicator.textContent = status.error ? '采集异常' : status.running ? '自动采集中' : '采集未运行';
      indicator.classList.toggle('error', Boolean(status.error));
      indicator.dataset.state = status.error ? 'error' : status.running ? 'running' : 'stopped';
    }
    const canRefresh = !window.getSelection().toString() && !document.activeElement?.closest('form') && !document.querySelector('[data-session-choice]:checked') && !document.querySelector('[data-atlas-turn].selected') && !document.querySelector('.atlas-session-row.selected:not([data-group="0"])') && !document.querySelector('main.reader, .message-source[open], details[data-key="directory:info"][open]');
    if (version !== null && current !== version && canRefresh) {
      const html = await fetch(location.pathname + location.search);
      if (!html.ok) throw new Error();
      const next = new DOMParser().parseFromString(await html.text(), 'text/html');
      const states = new Map([...document.querySelectorAll('details[data-key]')].map(d => [d.dataset.key, d.open]));
      for (const detail of next.querySelectorAll('details[data-key]')) {
        if (states.has(detail.dataset.key)) detail.open = states.get(detail.dataset.key);
      }
      const position = window.scrollY;
      const selectedGroup = document.querySelector('.session-info')?.dataset.selected;
      const focused = document.activeElement?.closest('details[data-key]')?.dataset.key;
      const focusedHref = document.activeElement?.closest('a')?.getAttribute('href');
      const formValues = [...document.querySelectorAll('.search-form [name]')].map(el => [el.name, el.value, el.selectedOptions?.[0]?.textContent]);
      const sessionFilter = document.querySelector('[data-session-filter]')?.value || '';
      for (const form of document.querySelectorAll('.search-form')) form.sessionRequest?.abort();
      document.querySelector('main').replaceWith(next.querySelector('main'));
      document.getElementById('page-context')?.remove();
      document.querySelector('.project-nav')?.replaceWith(next.querySelector('.project-nav'));
      if (selectedGroup) {
        const group = [...document.querySelectorAll('.session-group')].find(el => el.dataset.key === selectedGroup);
        selectDirectoryGroup(group);
      }
      for (const [name, value, label] of formValues) {
        const el = [...document.querySelectorAll('.search-form [name]')].find(el => el.name === name);
        if (el?.matches('[data-session-options]') && value && ![...el.options].some(option => option.value === value)) el.add(new Option(label, value));
        if (el) el.value = value;
      }
      const filter = document.querySelector('[data-session-filter]');
      if (filter) filter.value = sessionFilter;
      locateHit();
      if (focused) {
        const detail = [...document.querySelectorAll('details[data-key]')].find(d => d.dataset.key === focused);
        const link = focusedHref && detail && [...detail.querySelectorAll('a[href]')].find(a => a.getAttribute('href') === focusedHref);
        (link || detail?.querySelector('summary'))?.focus({preventScroll:true});
      }
      window.scrollTo(0, position);
    }
    if (version === null || current === version || canRefresh) version = current;
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


def collection_html(status: dict[str, Any], database: str) -> str:
    running = "采集运行中" if status.get("running") else "此页面服务未运行采集器；其他进程的采集状态请在其页面核对"
    availability = "来源不可用" if status.get("sourceAvailable") is False else "来源可访问" if status.get("sourceAvailable") else "等待来源检查"
    if status.get("sourceAvailable") and status.get("discoveredCount") == 0:
        availability += " · 确实没有会话"
    rows = [f'<li>会话 {escape(s["id"])}：{escape(s["error"])}</li>' for s in status.get("sessions", []) if s.get("error")]
    saved = sum(s.get("status") == "saved" for s in status.get("sessions", []))
    error = escape(status.get("error") or "无来源级错误")
    return ('<section class="source" aria-label="本机数据库与采集状态"><strong>自动保存到本机数据库 · 无需手动下载</strong>'
            f'<dl><dt>数据库文件</dt><dd>{escape(database)}</dd></dl>'
            f'<p><strong>{running} · {availability}</strong></p>'
            f'<p>最近成功归档检查：{saved_time(status.get("lastSuccessAt"))} · 最近来源成功检查：{saved_time(status.get("lastSourceSuccessAt"))}</p>'
            f'<p>上次完整检查发现 {status.get("discoveredCount", 0)} 个会话；范围内保存成功 {saved} 个，失败 {len(rows)} 个。最近检查：{saved_time(status.get("lastCheckedAt"))}。当前来源错误：{error}</p>'
            f'<ul>{"".join(rows)}</ul></section>')


def display_value(value: Any) -> str:
    if value is None:
        return "未知／未取得"
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)


def lazy_pre(url: str, field: str, label: str) -> str:
    return (f'<pre class="lazy-content" data-search="{escape(field, quote=True)}" '
            f'data-lazy-url="{escape(url, quote=True)}">{escape(label)}</pre>')


def value_pre(value: Any, url: str, field: str = "") -> str:
    text = display_value(value)
    if len(text) > LAZY_TEXT_LIMIT:
        return lazy_pre(url, field, "原文较大，展开后加载完整内容。")
    attribute = f' data-search="{escape(field, quote=True)}"' if field else ''
    return f'<pre{attribute}>{escape(text)}</pre>'


def build_lazy_url(thread: str, item: str, instance: str, kind: str, field: str,
                   saved_at: str | None = None, text_index: int | None = None,
                   turn_id: str | None = None) -> str:
    query = {"source": instance, "kind": kind, "field": field}
    if saved_at:
        query["saved"] = saved_at
    if text_index is not None:
        query["textIndex"] = str(text_index)
    if turn_id is not None:
        query['turn'] = turn_id
    return f'/api/session/{quote(thread, safe="")}/item/{quote(item, safe="")}?{urlencode(query)}'


def tool_html(tool: dict[str, Any], thread: str, instance: str, query: str, saved_at: str | None = None) -> str:
    statuses = {"completed": "执行已完成（不代表业务成功）", "failed": "执行失败", "inProgress": "进行中（未取得最终结果）", "declined": "已拒绝", "unknown": "状态未知"}
    name = ".".join(str(v) for v in (tool["namespace"], tool["name"]) if v is not None)
    body = f'<details class="message tool" data-key="{thread}:{escape(tool["turnId"], quote=True)}:tool:{escape(tool["id"], quote=True)}" data-tool-id="{escape(tool["id"], quote=True)}"><summary><span class="label">工具执行 · {escape(name or "名称未知")}</span><span class="phase">{statuses[tool["status"]]} · {"部分内容" if tool["completeness"] == "partial" else "完整性未知"}</span></summary>'
    for label, value in (("退出码", tool["exitCode"]),
                         ("参数（来源已提供）", "null" if tool.get("argumentsAvailable") and tool["arguments"] is None else tool["arguments"]), ("结果原文（已取得的全部内容）", tool["result"]),
                         ("错误信息", tool["error"])):
        if value is None and label != '结果原文（已取得的全部内容）':
            continue
        field = ('result' if label == '结果原文（已取得的全部内容）' else
                 'error' if label == '错误信息' else
                 'arguments' if label == '参数（来源已提供）' else '')
        lazy_url = build_lazy_url(thread, tool["id"], instance, "tool", field or "value", saved_at, turn_id=tool['turnId'])
        body += f'<h3>{label}</h3>{value_pre(value, lazy_url, field if field in ("result", "error") else "")}'
    text_indices = {"result": 0, "error": 0}
    for field, text in searchable_fields(tool, "tool"):
        if not isinstance(tool.get(field), str):
            label = '结果' if field == 'result' else '错误'
            text_index = text_indices[field]
            text_indices[field] += 1
            lazy_url = build_lazy_url(thread, tool["id"], instance, "tool", field + "Text", saved_at, text_index, tool['turnId'])
            body += f'<h3>{label}中的文本原文</h3>{value_pre(text, lazy_url, field)}'
    body += '<p class="gap">业务／任务成功：未知。嵌套调用未独立返回时，不从文本推造调用树。</p>'
    body += ''.join(f'<p class="gap">{escape(r)}</p>' for r in tool["reasons"])
    index = tool["evidenceRef"].split("/")[2]
    return body + f'<footer><a href="/evidence/{thread}/{index}{query}" target="_blank" rel="noopener">查看工具原始证据 ↗</a><code>来源身份：{escape(tool["id"])}<br>关联依据：{escape(tool["association"])}<br>导出位置：{escape(tool["evidenceRef"])}</code></footer></details>'


def evidence_link(owner: str, instance: str, saved_at: str, ref: str, label: str) -> str:
    query = '?source=' + quote(instance, safe='') + '&amp;saved=' + quote(saved_at, safe='')
    parts = ref.split('/')
    route = f'/evidence/{quote(owner, safe="")}/{parts[parts.index("evidence") + 1]}' if 'evidence' in parts else f'/metadata/{quote(owner, safe="")}'
    return f'<a href="{route}{query}" target="_blank" rel="noopener">{escape(label)} ↗</a>'


def relations_html(session: dict[str, Any]) -> str:
    records = session.get("relations", [])
    labels = {"subAgent": "子 agent", "fork": "分叉", "agentInteraction": "agent 交互", "unknown": "关系类型未知"}
    body = f'<details class="source" data-key="{escape(session["id"], quote=True)}:relations"><summary>关联会话 · {len(records)} 条关系证据</summary>'
    for gap in session.get("relationGaps", []):
        body += f'<p class="gap">{escape(gap)}</p>'
    if not records:
        body += '<p>尚未取得关系身份；不能据此认定没有子 agent 或分叉。</p>'
    for relation in records:
        target = relation["targetId"]
        label = labels.get(relation["type"], "关系类型未知")
        direction = "指向关联目标" if relation["direction"] == "outgoing" else "来自关联来源"
        body += f'<section class="source"><strong>{label} · {direction} · {escape(target or "目标未知")}</strong>'
        body += f'<p>来源关系：{escape(relation["fromId"] or "未知")} → {escape(relation["toId"] or "未知")}；依据：{escape(relation["basis"])}；活动：{escape(relation["activity"] or "未知／不适用")}</p>'
        if relation["availability"] == "archived":
            href = '/session/' + quote(target, safe='') + '?source=' + quote(relation['sourceInstance'], safe='')
            body += f'<p><a href="{href}">查看已归档会话 · {escape(target)}</a></p>'
        else:
            unavailable = {"deleted": "受管理归档已删除并排除", "unavailable": "来源不可访问／未保存", "notArchived": "尚未归档", "unknown": "目标未知"}
            body += f'<p>{unavailable.get(relation["availability"], "不可取得")}；没有可打开的归档正文。</p>'
        if relation["reason"]:
            body += f'<p class="gap">{escape(relation["reason"])}</p>'
        if relation.get("metadataEvidenceId"):
            href = '/relation-evidence/' + quote(relation['metadataEvidenceId'], safe='') + '?source=' + quote(relation['sourceInstance'], safe='')
            body += f'<a href="{href}" target="_blank" rel="noopener">查看关系来源证据 ↗</a>'
        else:
            body += evidence_link(relation["ownerId"], relation["sourceInstance"], relation["savedAt"], relation["ownerEvidenceRef"], "查看关系来源证据")
        if relation.get("metadataEvidenceId") or relation["ownerEvidenceRef"].startswith("#/session/thread"):
            body += '<p class="count">会话元数据字段投影；原始列表预览按首次范围规则丢弃，不冒充完整原始响应。</p>'
        body += '</section>'
    return body + '</details>'


def execution_html(execution: dict[str, Any]) -> str:
    state = {"exited": "已有退出结果", "running": "仍在运行（来源最后记录；退出结果未知）",
             "started": "已启动／退出结果未知", "unknown": "退出结果未知"}[execution["state"]]
    outcome = {"success": "执行成功（退出码 0；业务成功未知）", "failed": "执行失败", "unknown": "执行结果未知"}[execution["outcome"]]
    key = escape(f'{execution["threadId"]}:{execution["turnId"]}:execution:{execution["id"]}', quote=True)
    body = f'<details class="message" data-key="{key}"><summary>后台执行证据 · {escape(execution["id"])} · {state}</summary><p>{outcome}；退出码：{escape(display_value(execution["exitCode"]))}</p>'
    body += '<p class="gap">原子命令条目的保存观察；句柄不证明后台启动，未取得独立轮询记录。每次输出是该次取得的完整累计快照，不拼接为增量输出。业务／任务成功未知。</p>'
    for index, observation in enumerate(execution["observations"]):
        body += f'<details class="source" data-key="{key}:observation:{index}"><summary>保存观察 {index + 1} · 来源状态 {escape(str(observation["sourceStatus"]))} · 退出码 {escape(display_value(observation["exitCode"]))}</summary>'
        body += f'<p class="count">保存时间 {escape(observation["savedAt"])}；观察顺序不代表执行因果。</p>'
        for field, label, value in (("processId", "来源 PTY 句柄", observation["processId"]), ("command", "命令", observation["command"]),
                                    ("cwd", "工作目录", observation["cwd"]), ("output", "输出原文（来源合并 stdout / stderr）", observation["output"]),
                                    ("error", "错误信息（如来源提供）", observation["error"])):
            lazy = build_lazy_url(execution["threadId"], execution["id"], execution["sourceInstance"], "execution", field, observation["savedAt"])
            lazy += "&observation=" + quote(str(index), safe="")
            body += f'<h3>{label}</h3>{value_pre(value, lazy, field if isinstance(value, str) else "")}'
        body += evidence_link(execution["threadId"], execution["sourceInstance"], observation["savedAt"], observation["evidenceRef"], "查看本次执行原始证据") + '</details>'
    return body + '</details>'


def attachments_html(session: dict[str, Any], entry: dict[str, Any]) -> str:
    body = ''
    for attachment in session.get('attachments', []):
        if (attachment['turnId'], attachment['itemId']) != (entry['turnId'], entry['id']):
            continue
        name = escape(attachment['name'])
        if attachment['status'] == 'saved':
            body += f'<p>已归档附件：<a href="{escape(attachment["url"], quote=True)}" target="_blank" rel="noopener">打开本机副本 · {name} ↗</a>（{attachment["size"]} 字节）</p>'
            body += f'<p class="count">{escape(attachment.get("versionNote", ""))}</p>'
        else:
            body += f'<p class="gap">附件未取得 · {name}：{escape(attachment["reason"])}</p>'
        body += evidence_link(session['id'], session['source']['instance'], session['savedAt'], attachment['evidenceRef'], '查看附件原始证据')
    return body


def session_body(session: dict[str, Any], return_to: str | None = None, turn_number: int | None = None) -> str:
    source = session["source"]
    thread = quote(session["id"], safe="")
    query = "?source=" + quote(source["instance"], safe="")
    evidence_query = query + "&amp;saved=" + quote(session["savedAt"], safe="")
    links = "".join(f'<a href="#turn-{i}">回合 {i + 1}</a>' for i, _ in enumerate(session["turns"]))
    back = return_to or ('/project/' + session['project']['id'] if session.get('project') else '/')
    back_label = '返回搜索结果' if urlsplit(back).path == '/search' else '返回会话目录'
    body = f'<div class="heading"><div><a href="{escape(back, quote=True)}">← {back_label}</a> · <a href="/">项目列表</a><h1>{escape(session["name"] or session["id"])}</h1><p>来源会话开始：{source_time(session.get("createdAt", session["thread"].get("createdAt")))}</p><p class="count">{len(session["turns"])} 个回合 · {len(session["messages"])} 条用户与 AI 消息 · {len(session.get("tools", []))} 次工具记录 · 自动归档 · 关联执行证据</p><p class="count">本会话已入库 · 最近保存：{saved_time(session["savedAt"])}。历史证据与修订保留在本机数据库；首次范围前的回合未回补。</p></div></div>'
    if turn_number is not None:
        body = f'<h1>{escape(session["name"] or session["id"])}</h1><p class="count">回合 {turn_number} · {source_time(session["turns"][0].get("startedAt"))}</p><div>'
    if source.get('retention'):
        body += '<p class="count">仅保留对话与消息附件 · 工具记录已移除</p>'
    if turn_number is None:
        body += f'<p class="count">所属项目：{escape(session.get("project", {}).get("label") or session["thread"].get("cwd") or "项目未知")}</p>'
        body += f'<div class="layout"><aside class="sidebar"><span class="eyebrow">回合索引</span><nav aria-label="回合索引">{links}</nav><p class="muted">按来源顺序阅读各回合。</p></aside><div>'
        body += relations_html(session)
    summary = session.get('attachmentSummary')
    if summary and turn_number is None:
        body += f'<p class="source">附件：已归档 {summary["saved"]} 个引用 · 未取得 {summary["missing"]} 个引用。{escape(summary["note"])}</p>'
    gaps = "".join(f'<li>{escape(gap)}</li>' for gap in source["gaps"])
    if turn_number is None:
        body += f'<details class="source" data-key="{thread}:source"><summary>数据源版本与已知缺口</summary><p>{escape(str(source["version"]))} · {escape(session["savedAt"])}</p><ul>{gaps}</ul></details>'
    labels = {"commentary": "AI 过程消息", "final_answer": "AI 最终回答"}
    statuses = {"completed": "已完成", "interrupted": "已中断", "inProgress": "进行中", "failed": "失败"}
    for index, turn in enumerate(session["turns"]):
        index = turn_number - 1 if turn_number is not None else index
        status = statuses.get(turn.get("status"), "状态未知")
        body += f'<section class="turn" id="turn-{index}"><h2>回合 {index + 1}<span class="turn-status">{status}</span></h2>'
        entries = session["messages"] + session.get("tools", []) + session.get("unsupportedItems", [])
        execution_body = ""
        execution_count = 0
        for message in sorted((m for m in entries if m["turnId"] == turn["id"]), key=lambda m: m["order"]):
            if "association" in message:
                anchor = item_anchor(source["instance"], session["id"], turn["id"], message["id"], "tool")
                execution_body += tool_html(message, thread, source["instance"], evidence_query, session.get("savedAt")).replace('</footer>', '</footer>' + attachments_html(session, message)).replace('<details ', f'<details id="{anchor}" ', 1)
                execution_count += 1
                continue
            if message["type"] not in ("userMessage", "agentMessage"):
                evidence_index = message["evidenceRef"].split("/")[2]
                relation_item = message["type"] in ("subAgentActivity", "collabAgentToolCall")
                item_label = "会话关系来源" if relation_item else "不支持的条目"
                reason = "关系见上方关联会话；完整原始载荷仍保留。" if relation_item else message["reasons"][0]
                execution_body += f'<details class="message" data-key="{thread}:{escape(turn["id"], quote=True)}:unsupported:{escape(message["id"], quote=True)}"><summary>{item_label} · {escape(message["type"])} · 完整性未知</summary><p>{escape(reason)}</p><a href="/evidence/{thread}/{evidence_index}{evidence_query}" target="_blank" rel="noopener">查看条目原始证据 ↗</a><footer><code>{escape(message["id"])}<br>导出位置：{escape(message["evidenceRef"])}</code></footer></details>'
                execution_body += attachments_html(session, message)
                execution_count += 1
                continue
            user = message["type"] == "userMessage"
            label = "用户原文" if user else labels.get(message["phase"], "AI 消息 · 阶段未知")
            evidence_index = message["evidenceRef"].split("/")[2]
            completeness = {"complete": "已取得文本", "partial": "部分内容", "unknown": "完整性未知"}[message["completeness"]]
            anchor = item_anchor(source["instance"], session["id"], turn["id"], message["id"], "message")
            lazy_url = build_lazy_url(thread, message["id"], source["instance"], "message", "text", session.get("savedAt"), turn_id=turn['id'])
            open_attribute = '' if len(message["text"]) > LAZY_TEXT_LIMIT else ' open'
            message_text = value_pre(message["text"], lazy_url, 'text')
            message_time = source_time(message["startedAtMs"] / 1000 if message["startedAtMs"] is not None else None)
            warning = f'<span class="phase">{completeness}</span>' if message["completeness"] != 'complete' else ''
            body += f'<details id="{anchor}"{open_attribute} data-key="{thread}:{escape(turn["id"], quote=True)}:message:{escape(message["id"], quote=True)}" class="message {"user" if user else "agent"}"><summary><span class="message-heading"><span class="label">{label}</span><span class="message-time">{escape(message_time)}</span></span>{warning}</summary>{message_text}'
            for reason in message["reasons"]:
                body += f'<p class="gap">{escape(reason)}</p>'
            body += attachments_html(session, message)
            body += f'<footer><details class="message-source" data-key="{thread}:{escape(turn["id"], quote=True)}:source:{escape(message["id"], quote=True)}"><summary>来源信息</summary><p>{completeness} · 来源时间：{escape(message_time)}</p><a href="/evidence/{thread}/{evidence_index}{evidence_query}" target="_blank" rel="noopener">查看消息来源证据 ↗</a><code>{escape(message["id"])}<br>导出位置：{escape(message["evidenceRef"])}<br>保存版本：{escape(session["savedAt"])}</code></details></footer></details>'
        if execution_count:
            gaps = ''.join(f'<p class="gap">{escape(gap)}</p>' for gap in session.get("executionGaps", []))
            body += f'<details class="source execution" data-key="{thread}:{escape(turn["id"], quote=True)}:execution"><summary>工具调用与最终结果 · {execution_count} 条记录</summary><p class="muted">每次工具调用展示最后保存的状态与完整结果；进行中的调用如实标明。历史保存观察可从原始证据与导出核对。</p>{execution_body}</details>'
        body += '</section>'
    return body + ('</div>' if turn_number is not None else '</div></div>')


def session_page(session: dict[str, Any]) -> str:
    return page("原文时间线", session_body(session))


def turn_url(session: dict[str, Any], turn: str, return_to: str = '', saved: bool = True) -> str:
    values = {'source': session['source']['instance']}
    if saved:
        values['saved'] = session['savedAt']
    if return_to:
        values['return'] = return_to
    return '/session/' + quote(session['id'], safe='') + '/turn/' + quote(turn, safe='') + '?' + urlencode(values)


def selection_toolbar(return_to: str) -> str:
    return (f'<form id="session-selection" action="/selection" method="get" class="selection-toolbar">'
            f'<input type="hidden" name="return" value="{escape(return_to, quote=True)}">'
            '<span>选择本页会话</span><button type="submit" name="action" value="export">导出所选</button>'
            '<button type="submit" name="action" value="delete">删除所选</button></form>')


def selection_checkbox(instance: str, thread: str, label: str) -> str:
    value = json.dumps([instance, thread], ensure_ascii=False)
    return (f'<label class="session-choice"><input type="checkbox" form="session-selection" name="session" '
            f'data-session-choice value="{escape(value, quote=True)}" aria-label="选择会话 {escape(label, quote=True)}">选择会话</label>')


def turn_directory(result: dict[str, Any], path: str, options: dict[str, list[str]]) -> str:
    preserved = {k: v[0] for k, v in options.items() if k in ('source', 'saved')}
    back = path + '?' + urlencode({**preserved, 'offset': result['offset'], 'limit': result['limit']})
    groups: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for entry in result['turns']:
        session = entry['session']
        identity = (session['source']['instance'], session['id'])
        if not groups or (groups[-1][0]['source']['instance'], groups[-1][0]['id']) != identity:
            groups.append((session, []))
        groups[-1][1].append(entry)
    states = {'completed': '已完成', 'inProgress': '进行中', 'interrupted': '已中断', 'failed': '失败'}
    body = '<div class="directory-layout atlas-layout"><section class="atlas-sessions"><header class="atlas-list-heading"><h1>会话目录</h1><span>本页 ' + str(len(groups)) + ' 个会话 · 共 ' + str(result['total']) + ' 个回合</span></header>'
    body += selection_toolbar(back) + '<div class="atlas-session-list">'
    for index, (session, entries) in enumerate(groups):
        label = session['name'] or session['id']
        choice = selection_checkbox(session['source']['instance'], session['id'], label)
        body += f'<div class="atlas-session-row{(" selected" if index == 0 else "")}" data-group="{index}">{choice}<button class="atlas-session-button" type="button" aria-pressed="{str(index == 0).lower()}" aria-controls="session-turns-{index}" data-select-group="{index}"><span class="atlas-session-icon">{icon("folder")}</span><span class="atlas-session-copy"><strong>{escape(label)}</strong><small>{source_time(session.get("createdAt"))} · 本页 {len(entries)} 个回合</small></span></button></div>'
    if not groups:
        body += f'<p class="empty">这一页没有回合。<a href="{escape(path, quote=True)}">返回第一页</a></p>'
    body += '</div><nav class="turn-navigation pagination" aria-label="回合目录分页">'
    for label, offset in (('上一页', max(0, result['offset'] - result['limit']) if result['offset'] else None), ('下一页', result['nextOffset'])):
        if label == '下一页':
            body += f'<span class="page-number" aria-current="page">{result["offset"] // result["limit"] + 1}</span>'
        if offset is None:
            body += f'<span class="disabled">{label}</span>'
        else:
            href = path + '?' + urlencode({**preserved, 'offset': offset, 'limit': result['limit']})
            body += f'<a href="{escape(href, quote=True)}">{label}</a>'
    body += '</nav></section><section class="atlas-detail"><header class="atlas-detail-heading"><div><h2 data-atlas-name>'
    body += escape((groups[0][0]['name'] or groups[0][0]['id']) if groups else '暂无会话')
    body += '</h2><p data-atlas-meta>' + (f'开始时间 {source_time(groups[0][0].get("createdAt"))} · 本页 {len(groups[0][1])} 个回合' if groups else '') + '</p><details data-key="directory:info"><summary>来源信息</summary><p data-atlas-source>' + escape(groups[0][0]['source']['instance'] if groups else '未知') + '</p></details></div></header><div class="atlas-detail-columns"><section class="atlas-turns"><h2>回合目录</h2>'
    for index, (session, entries) in enumerate(groups):
        label = escape(session['name'] or session['id'], quote=True)
        meta = escape(f'开始时间 {source_time(session.get("createdAt"))} · 本页 {len(entries)} 个回合', quote=True)
        body += f'<div class="atlas-turn-group" id="session-turns-{index}" data-turn-group="{index}" data-name="{label}" data-meta="{meta}" data-source="{escape(session["source"]["instance"], quote=True)}"{(" hidden" if index else "")}><ul class="turn-links">'
        for entry in entries:
            href = turn_url(session, entry['id'], back, saved=bool(options.get('saved')))
            state = entry['status'] if entry['status'] in states else 'unknown'
            body += f'<li><a data-atlas-turn data-turn-ordinal="{entry["ordinal"]}" href="{escape(href, quote=True)}"><strong>回合 {entry["ordinal"]}</strong><span class="status" data-state="{state}">{states.get(entry["status"], "状态未知")}</span></a></li>'
        body += '</ul></div>'
    body += '</section><section class="atlas-reader" aria-label="回合正文"><div class="atlas-reader-header"><h2 data-reader-title>回合正文</h2><a data-reader-open hidden>打开独立页面 ↗</a></div><p data-reader-status role="status" class="atlas-placeholder">选择一个回合，正文将在这里显示。</p><div data-reader-content aria-busy="false"></div></section></div></section></div>'
    return body


def turn_navigation(result: dict[str, Any], return_to: str) -> str:
    session = result['session']
    body = '<nav class="turn-navigation" aria-label="回合导航">'
    for label, key in (('上一回合', 'previous'), ('下一回合', 'next')):
        if key == 'next':
            label_back = '返回搜索结果' if urlsplit(return_to).path == '/search' else '返回目录'
            body += f'<a href="{escape(return_to, quote=True)}">{label_back}</a>'
        if result[key] is not None:
            body += f'<a href="{escape(turn_url(session, result[key], return_to, saved=result.get("pinned", False)), quote=True)}">{label}</a>'
        else:
            body += f'<span class="count">{label}：无</span>'
    return body + '</nav>'


def search_form(app: Journal, query: str = "", project_id: str | None = None,
                scope: str = "") -> str:
    projects = app.project_choices()
    project_options = '<option value="">所有已保存项目</option>'
    session_options = '<option value="">所有已保存会话</option>'
    for project in projects:
        selected = ' selected' if project["id"] == project_id else ''
        label = f'{project["label"]} · {project.get("sourceProjectId") or project["basis"]} · {project["id"][:8]}'
        project_options += f'<option value="{project["id"]}"{selected}>{escape(label)}</option>'
    if scope:
        instance, thread = json.loads(scope)
        session = app.session_summary(thread, instance)
        label = f'{session["name"] or session["id"]} · {session["id"]} · 来源 {instance[:8]}'
        session_options += f'<option value="{escape(scope, quote=True)}" selected>{escape(label)}</option>'
    return ('<section class="source" aria-label="搜索已保存正文"><h2>搜索已保存正文</h2>'
        '<form class="search-form" action="/search" method="get">'
        f'<label>中文或混合文本<input name="q" value="{escape(query, quote=True)}" type="search"></label>'
        f'<label>项目范围<select name="project">{project_options}</select></label>'
        '<label>筛选会话名称<input type="search" data-session-filter placeholder="按需查找会话"></label>'
        f'<label>会话范围<select name="scope" data-session-options>{session_options}</select></label>'
        '<button type="button" data-session-more hidden>加载更多会话</button>'
        '<button type="submit">搜索</button></form></section>')


def search_results(result: dict[str, Any], options: dict[str, str]) -> str:
    if result["emptyQuery"]:
        return '<p role="status">请输入搜索关键词。</p>'
    if not result["total"]:
        return ('<section class="source" role="status"><h2>未找到相关内容</h2>'
                f'<p>当前范围内没有匹配“{escape(result["query"])}”的已保存正文。请尝试其他关键词，或扩大搜索范围。</p></section>')
    body = f'<p role="status">共 {result["total"]} 条记录；当前第 {result["offset"] + 1}—{min(result["total"], result["offset"] + result["limit"])} 条，每页最多 {result["limit"]} 条。按会话开始时间排列。</p>'
    body += selection_toolbar('/search?' + urlencode(options))
    seen_sessions: set[tuple[str, str]] = set()
    labels = {"text": "消息正文", "result": "工具返回文本", "error": "工具错误文本"}
    for hit in result["results"]:
        kind = "用户提示" if hit["type"] == "userMessage" else "AI 过程消息" if hit["phase"] == "commentary" else "AI 最终回答" if hit["phase"] == "final_answer" else "AI 消息（阶段未知）" if hit["kind"] == "message" else labels[hit["field"]]
        completeness = {"complete": "已取得文本", "partial": "部分内容", "unknown": "完整性未知"}[hit["completeness"]]
        target = urlsplit(hit["url"])
        back = '/search?' + urlencode(options)
        href = target._replace(query=target.query + '&' + urlencode({'return': back})).geturl()
        identity = (hit['sourceInstance'], hit['threadId'])
        choice = ''
        if identity not in seen_sessions:
            seen_sessions.add(identity)
            choice = selection_checkbox(*identity, hit['sessionName'] or hit['threadId'])
        body += f'<article class="message search-result">{choice}<h2><a href="{escape(href, quote=True)}">{kind} · {escape(hit["sessionName"] or "未命名会话")}</a></h2>'
        state = f' · {completeness}' if hit["completeness"] != "complete" else ''
        body += f'<p class="count">项目：{escape(hit["project"]["label"])}{state}</p>'
        body += f'<pre>{escape(hit["snippet"])}</pre>'
        body += ''.join(f'<p class="gap">{escape(reason)}</p>' for reason in hit["reasons"])
        body += f'<footer><a href="{escape(hit["evidenceUrl"], quote=True)}" target="_blank" rel="noopener">查看来源证据 ↗</a> · 点击标题查看完整原文。</footer></article>'
    for label, offset in (("上一页", max(0, result["offset"] - result["limit"]) if result["offset"] else None), ("下一页", result["nextOffset"])):
        if offset is not None:
            href = '/search?' + urlencode({**options, "offset": offset, "limit": result["limit"]})
            body += f'<a class="action" href="{escape(href, quote=True)}">{label}</a> '
    return body


def create_server(app: Journal, port: int = 8765, collector: Collector | None = None) -> ThreadingHTTPServer:
    token = secrets.token_urlsafe(32)

    def management_form(action: str, identity: str, instance: str, label: str) -> str:
        return (f'<form method="post" action="/manage/{action}/{quote(identity, safe="")}">'
                f'<input type="hidden" name="token" value="{token}">'
                f'<input type="hidden" name="source" value="{escape(instance, quote=True)}">'
                f'<button type="submit" class="action">{escape(label)}</button></form>')

    def deletion_scope() -> str:
        return ('<p>删除范围仅限本应用管理的该来源会话：正文、工具、历史修订、原始证据、搜索内容和附件引用。'
                '其他会话仍引用的共享附件继续保留。</p><p>不改变 Codex 原会话；不擦除另存的导出副本。'
                '已删除会话将排除自动归档，只有显式解除排除后才重新采集，仍遵守原启用时间。</p>')

    def selected_sessions(values: dict[str, list[str]]) -> list[tuple[str, str]]:
        selected: list[tuple[str, str]] = []
        for value in values.get('session', []):
            item = json.loads(value)
            if not isinstance(item, list) or len(item) != 2 or not all(isinstance(x, str) and x for x in item):
                raise ValueError('会话选择无效。')
            identity = (item[0], item[1])
            if identity not in selected:
                selected.append(identity)
        if not selected or len(selected) > 100:
            raise ValueError('请选择 1 至 100 个会话。')
        return selected

    def safe_return(value: str) -> str:
        parsed = urlsplit(value)
        return value if not parsed.scheme and not parsed.netloc and (parsed.path == '/search' or parsed.path.startswith('/project/') or parsed.path.startswith('/session/')) else '/'

    def status() -> dict[str, Any]:
        return collector.status() if collector else {**app.collection_state(), 'exclusions': app.exclusions(), "running": False}

    class Handler(BaseHTTPRequestHandler):
        server: ThreadingHTTPServer

        def local_request(self, allow_opaque_form: bool = False) -> bool:
            local_port = self.server.server_port
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin')
            valid_origin = origin in (None, 'http://' + host) or (
                allow_opaque_form and origin == 'null' and self.headers.get('Sec-Fetch-Site') == 'same-origin')
            return host in {f'127.0.0.1:{local_port}', f'localhost:{local_port}'} and valid_origin

        def do_POST(self) -> None:
            if not self.local_request(allow_opaque_form=True):
                self.respond(403, 'text/plain', '仅允许本机同源访问。')
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 65536 or self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    raise ValueError('请求格式无效。')
                values = parse_qs(self.rfile.read(size).decode('utf-8'))
                if not secrets.compare_digest(values.get('token', [''])[0].encode('utf-8'), token.encode('ascii')):
                    self.respond(403, 'text/plain', '确认凭据无效，请重新打开管理页面。')
                    return
                if urlsplit(self.path).path == '/capacity':
                    amount = values.get('amount', [''])[0].strip()
                    unit = values.get('unit', ['MiB'])[0]
                    if unit not in ('MiB', 'GiB'):
                        raise ValueError('容量单位无效。')
                    if amount:
                        from decimal import Decimal, InvalidOperation
                        try:
                            value = Decimal(amount)
                            if not value.is_finite() or value < 0 or value > 1048576:
                                raise ValueError('容量无效。')
                            limit = int(value * (1024 ** (2 if unit == 'MiB' else 3)))
                        except (InvalidOperation, OverflowError):
                            raise ValueError('请输入有效容量。')
                    else:
                        limit = None
                    app.set_capacity(limit)
                    self.send_response(303)
                    self.send_header('Location', '/capacity?saved=1')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                if urlsplit(self.path).path == '/selection':
                    selected = selected_sessions(values)
                    action = values.get('action', [''])[0]
                    if action == 'export':
                        output = io.BytesIO()
                        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                            for index, (source, thread) in enumerate(selected, 1):
                                archive.writestr(f'session-{index:03d}.zip', app.export_bundle(thread, source))
                        self.respond(200, 'application/zip', output.getvalue(), filename='selected-sessions.zip')
                        return
                    if action == 'delete':
                        # Validate all identities before making any deletion.
                        for source, thread in selected:
                            app.session_summary(thread, source)
                        outcomes = []
                        for source, thread in selected:
                            try:
                                result = app.delete_session(thread, source)
                                outcomes.append((thread, result['status']))
                            except (KeyError, ValueError, OSError, sqlite3.Error):
                                outcomes.append((thread, 'failed'))
                        details = ''.join(f'<li>{escape(thread)}：{escape({"deleted": "已删除", "cleanupPending": "已删除，附件待清理", "failed": "删除失败，请在删除管理中核对"}.get(state, state))}</li>' for thread, state in outcomes)
                        self.respond(200, 'text/html', page('删除结果', '<h1>删除结果</h1><ul>' + details + '</ul><p><a href="/manage/exclusions">查看删除管理</a></p><p><a href="' + escape(safe_return(values.get('return', ['/'])[0]), quote=True) + '">返回</a></p>', active='manage', projects=app.project_choices()))
                        return
                    raise ValueError('操作无效。')
                segments = [unquote(p) for p in urlsplit(self.path).path.strip('/').split('/')]
                if len(segments) != 3 or segments[0] != 'manage' or segments[1] not in ('delete', 'restore', 'retry'):
                    self.respond(404, 'text/plain', '找不到这个操作。')
                    return
                instance = values.get('source', [None])[0]
                if not instance:
                    raise ValueError('必须明确来源实例。')
                result = app.restore_session(segments[2], instance) if segments[1] == 'restore' else app.delete_session(segments[2], instance)
                self.send_response(303)
                self.send_header('Location', '/manage/exclusions?' + urlencode({'notice': result['status']}))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', '0')
                self.end_headers()
            except (ValueError, UnicodeError) as exc:
                self.respond(400, 'text/plain', str(exc))
            except KeyError as exc:
                self.respond(404, 'text/plain', str(exc))
            except (OSError, sqlite3.Error):
                self.respond(500, 'text/plain', '本机存储操作失败；未确认完成。请检查数据目录后在管理页核对并重试。')

        def do_GET(self) -> None:
            if not self.local_request():
                self.respond(403, "text/plain", "仅允许本机同源访问。")
                return
            url = urlsplit(self.path)
            segments = [unquote(p) for p in url.path.strip("/").split("/")]
            options = parse_qs(url.query)
            instance = options.get("source", [None])[0]
            try:
                if url.path == '/api/capacity':
                    self.respond(200, 'application/json', json.dumps(app.capacity()))
                elif url.path == '/capacity':
                    capacity = app.capacity()
                    used = capacity['usedBytes'] / 1048576
                    cap_limit = capacity['limitBytes']
                    limit_label = f'{cap_limit / 1048576:.1f} MiB' if cap_limit else '未设置'
                    cap_state = '已达到上限，新会话暂停保存。' if capacity['paused'] else '当前可以保存新会话。' if cap_limit else '未设置上限。'
                    cap_notice = '<p role="status">容量设置已保存。</p>' if options.get('saved') else ''
                    body = f'<h1>数据库容量</h1>{cap_notice}<section class="source capacity-settings"><h2>使用情况</h2><p>已使用：<strong>{used:.1f} MiB</strong> · 设置上限：<strong>{limit_label}</strong></p><p>{cap_state}</p><p>统计数据库中已使用的数据页；删除后可重用的空间不计入。附件文件单独存储，不计入数据库容量。</p><p>达到上限后暂停保存新会话，已有会话仍会更新，因此使用量可能超过上限。容量降至上限以下后自动恢复。</p></section>'
                    body += f'<section class="source capacity-settings"><h2>设置容量上限</h2><form method="post" action="/capacity"><input type="hidden" name="token" value="{token}"><label>容量（留空表示不限制）<input name="amount" type="number" min="0.001" max="1048576" step="any" value="{cap_limit / 1048576 if cap_limit else ""}"></label><label>单位<select name="unit"><option value="MiB">MiB</option><option value="GiB">GiB</option></select></label><button type="submit">保存设置</button></form></section>'
                    self.respond(200, 'text/html', page('数据库容量', body, projects=app.project_choices()))
                elif url.path == '/selection':
                    selected = selected_sessions(options)
                    action = options.get('action', [''])[0]
                    if action not in ('export', 'delete'):
                        raise ValueError('操作无效。')
                    summaries = [app.session_summary(thread, source) for source, thread in selected]
                    back = safe_return(options.get('return', ['/'])[0])
                    heading = '确认导出会话' if action == 'export' else '确认删除会话'
                    body = f'<h1>{heading}</h1><p>已选择 {len(selected)} 个会话：</p><ul>'
                    for summary in summaries:
                        body += f'<li>{escape(summary["name"] or summary["id"])} <small>（{escape(summary["id"])} · 来源 {escape(summary["source"]["instance"][:8])}）</small></li>'
                    body += '</ul>' + (deletion_scope() if action == 'delete' else '<p>下载 ZIP 文件，每个会话包含独立的离线归档及附件。</p>')
                    body += f'<form method="post" action="/selection"><input type="hidden" name="token" value="{token}"><input type="hidden" name="action" value="{action}"><input type="hidden" name="return" value="{escape(back, quote=True)}">'
                    for selected_source, selected_thread in selected:
                        body += f'<input type="hidden" name="session" value="{escape(json.dumps([selected_source, selected_thread], ensure_ascii=False), quote=True)}">'
                    body += f'<button type="submit">{heading}</button></form><p><a href="{escape(back, quote=True)}">取消，返回</a></p>'
                    self.respond(200, 'text/html', page(heading, body, projects=app.project_choices()))
                elif url.path == '/api/exclusions':
                    self.respond(200, 'application/json', json.dumps(app.exclusions(), ensure_ascii=False))
                elif url.path == '/manage/exclusions':
                    body = '<a href="/">← 项目列表</a><h1>删除排除管理</h1>' + deletion_scope()
                    body += '<h2>已归档会话</h2><ul class="manage-list">'
                    for summary in app.sessions():
                        href = '/manage/delete/' + quote(summary['id'], safe='') + '?' + urlencode({'source': summary['source']['instance']})
                        body += f'<li><span>{escape(summary["name"] or summary["id"])}</span><a href="{escape(href, quote=True)}">查看删除选项</a></li>'
                    body += '</ul><h2>删除排除</h2>'
                    notices = {'deleted': '已删除受管理日志，并保留删除排除。', 'cleanupPending': '正文与证据已删除；附件清理未完成，请修复文件占用或权限后重试。重启也会重试。',
                               'restored': '已解除删除排除，等待原范围内自动归档；已删除的历史副本不会恢复。'}
                    notice = notices.get(options.get('notice', [''])[0])
                    if notice:
                        body += f'<p class="source" role="status">{notice}</p>'
                    entries = app.exclusions()
                    if not entries:
                        body += '<p class="empty">没有删除排除。</p>'
                    for entry in entries:
                        pending = entry['status'] == 'cleanupPending'
                        body += f'<section class="source"><h2>{escape(entry["id"])}</h2><p>来源实例：<code>{escape(entry["sourceInstance"])}</code></p><p>{"附件清理未完成，保持删除排除" if pending else "受管理日志已删除，保持删除排除"}</p>'
                        if pending:
                            body += f'<p class="gap">{escape(entry["error"] or "等待清理")}</p>'
                            body += management_form('retry', entry['id'], entry['sourceInstance'], '重试附件清理')
                        else:
                            body += management_form('restore', entry['id'], entry['sourceInstance'], '解除删除排除')
                        body += '</section>'
                    self.respond(200, 'text/html', page('删除排除管理', body, active='manage', projects=app.project_choices()))
                elif len(segments) == 3 and segments[:2] == ['manage', 'delete']:
                    session = app.session(segments[2], instance)
                    href = '/session/' + quote(session['id'], safe='') + '?' + urlencode({'source': session['source']['instance']})
                    body = f'<h1>确认删除受管理日志</h1><h2>{escape(session["name"] or session["id"])}</h2><p>会话：<code>{escape(session["id"])}</code> · 来源：<code>{escape(session["source"]["instance"])}</code></p>'
                    body += deletion_scope() + management_form('delete', session['id'], session['source']['instance'], '确认删除此会话的受管理日志')
                    body += f'<p><a href="{escape(href, quote=True)}">取消，返回会话</a></p>'
                    self.respond(200, 'text/html', page('确认删除', body, active='manage', projects=app.project_choices(), project_id=session['project']['id']))
                elif url.path == "/":
                    projects = app.project_choices()
                    items = ''.join(f'<li><h2><a href="/project/{quote(p["id"], safe="")}">{escape(project_name(p["label"]))}</a></h2><p class="project-path">{escape(p["label"])}</p><p>{p["sessionCount"]} 个已保存会话</p></li>' for p in projects)
                    empty = '<div class="empty"><h2>尚无范围内已保存的会话</h2><p>采集服务启动后会自动发现所有项目的新回合，无需手动导入或同步。来源运行情况见采集状态。</p></div>' if not items else ""
                    archive = '<h1>项目归档</h1><ul class="session-list">' + items + '</ul>' + empty
                    content = archive
                    self.respond(200, "text/html", page("项目归档", content, projects=projects))
                elif url.path in ("/search", "/api/search"):
                    values = {key: value[0] for key, value in options.items()}
                    scope = values.get("scope", "")
                    thread = values.get("session")
                    if scope:
                        selected_scope = json.loads(scope)
                        if not isinstance(selected_scope, list) or len(selected_scope) != 2 or not all(isinstance(s, str) for s in selected_scope):
                            raise ValueError("会话范围无效。")
                        instance, thread = selected_scope
                    result = app.search(values.get("q", ""), values.get("project") or None, thread or None, instance,
                                        int(values.get("offset", "0")), int(values.get("limit", "30")))
                    if url.path == "/api/search":
                        self.respond(200, "application/json", json.dumps(result, ensure_ascii=False))
                    else:
                        content = '<a href="/">← 项目列表</a><h1>正文搜索</h1>'
                        content += search_form(app, result["query"], result["scope"]["project"], scope)
                        content += search_results(result, values)
                        self.respond(200, "text/html", page("正文搜索", content, active='search', projects=app.project_choices()))
                elif url.path == "/live.js":
                    self.respond(200, "text/javascript", LIVE_SCRIPT)
                elif url.path == "/api/status":
                    self.respond(200, "application/json", json.dumps(status(), ensure_ascii=False))
                elif url.path == '/status':
                    self.respond(200, 'text/html', page('采集状态', '<h1>采集状态</h1>' + collection_html(status(), str(app.database)), active='status', projects=app.project_choices()))
                elif url.path == "/api/projects":
                    self.respond(200, "application/json", json.dumps(app.projects(), ensure_ascii=False))
                elif url.path == "/api/version":
                    state = status()
                    content = json.dumps([app.sessions(), state], ensure_ascii=False)
                    self.respond(200, "application/json", json.dumps({'version': hashlib.sha256(content.encode()).hexdigest(), 'running': state.get('running', False), 'error': bool(state.get('error')) or state.get('sourceAvailable') is False}))
                elif url.path == "/api/catalog":
                    result = app.project_sessions(options.get('project', [None])[0],
                        int(options.get('offset', ['0'])[0]), int(options.get('limit', ['100'])[0]), options.get('q', [''])[0])
                    result['sessions'] = [{k: s[k] for k in ('id', 'name', 'source')} for s in result['sessions']]
                    for summary in result['sessions']:
                        summary['source'] = {'instance': summary['source']['instance']}
                    self.respond(200, 'application/json', json.dumps(result, ensure_ascii=False))
                elif len(segments) == 2 and segments[0] == "project":
                    result = app.project_turns(segments[1], int(options.get('offset', ['0'])[0]), int(options.get('limit', ['30'])[0]))
                    project = result['project']
                    self.respond(200, 'text/html', page(project['label'], turn_directory(result, url.path, options), projects=app.project_choices(), project_id=project['id']))
                elif url.path == "/api/sessions":
                    self.respond(200, "application/json", json.dumps(app.sessions(), ensure_ascii=False))
                elif len(segments) == 3 and segments[:2] == ["api", "session"]:
                    self.respond(200, "application/json", json.dumps(app.session(segments[2], instance), ensure_ascii=False))
                elif len(segments) == 5 and segments[:2] == ["api", "session"] and segments[3] == "item":
                    identity, kind, field = segments[4], options.get("kind", [""])[0], options.get("field", [""])[0]
                    selected_turn = options.get('turn', [None])[0]
                    session = (app.turn(segments[2], selected_turn, instance, options.get('saved', [None])[0])['session'] if selected_turn is not None
                               else app.session(segments[2], instance, options.get("saved", [None])[0], include_history=kind == 'execution'))
                    entries = session.get("messages", []) if kind == "message" else session.get("tools", []) if kind == "tool" else []
                    entry = next((item for item in entries if item["id"] == identity), {})
                    if kind == "execution":
                        execution: dict[str, Any] = next((item for item in session.get("executions", []) if item["id"] == identity), {})
                        observation_index = int(options.get("observation", ["-1"])[0])
                        observations = execution.get("observations", [])
                        entry = observations[observation_index] if 0 <= observation_index < len(observations) else {}
                    if not entry:
                        raise KeyError("本机未保存这个条目。")
                    if kind == "message" and field == "text":
                        value = entry["text"]
                    elif kind in ("tool", "execution") and field in (("arguments", "result", "error") if kind == "tool" else ("processId", "command", "cwd", "output", "error")):
                        value = display_value(entry[field])
                    elif kind == "tool" and field in ("resultText", "errorText"):
                        source_field = field.removesuffix("Text")
                        text_index = int(options.get("textIndex", ["-1"])[0])
                        text_values = [text for actual_field, text in searchable_fields(entry, "tool") if actual_field == source_field]
                        if not 0 <= text_index < len(text_values):
                            raise KeyError("本机未保存这个文本字段。")
                        value = text_values[text_index]
                    else:
                        raise KeyError("不支持的原文字段。")
                    self.respond(200, "application/json", json.dumps({"text": value}, ensure_ascii=False))
                elif len(segments) == 4 and segments[0] == 'session' and segments[2] == 'turn':
                    result = app.turn(segments[1], segments[3], instance, options.get('saved', [None])[0])
                    result['pinned'] = bool(options.get('saved'))
                    session = result['session']
                    back = options.get('return', [''])[0]
                    destination = urlsplit(back)
                    if destination.scheme or destination.netloc or not (destination.path.startswith('/project/') or destination.path == '/search' or (destination.path.startswith('/session/') and destination.path.count('/') == 2)):
                        back = '/project/' + session['project']['id']
                    navigation = turn_navigation(result, back)
                    version_note = '<p class="count" data-reader-version>正在查看命中时的保存版本；原文与证据固定在该版本。</p>' if options.get('saved') else ''
                    content = version_note + session_body(session, back, result['ordinal'])
                    if options.get('view') == ['reader']:
                        self.respond(200, 'text/html', content)
                    else:
                        body = navigation + content + navigation
                        self.respond(200, 'text/html', page(f'回合 {result["ordinal"]}', body, reading=True, projects=app.project_choices(), project_id=session['project']['id']))
                elif len(segments) == 2 and segments[0] == "session":
                    result = app.session_turns(segments[1], instance, options.get('saved', [None])[0],
                        int(options.get('offset', ['0'])[0]), int(options.get('limit', ['30'])[0]), options.get('target', [None])[0])
                    if 'target' in result:
                        values = {k: v[0] for k, v in options.items() if k in ('saved', 'target', 'q', 'field', 'return')}
                        values['source'] = result['session']['source']['instance']
                        href = '/session/' + quote(segments[1], safe='') + '/turn/' + quote(result['target'], safe='') + '?' + urlencode(values)
                        self.send_response(303)
                        self.send_header('Location', href)
                        self.send_header('Content-Length', '0')
                        self.end_headers()
                    else:
                        source = result['turns'][0]['session']['source']['instance'] if result['turns'] else instance
                        href = '/manage/delete/' + quote(segments[1], safe='') + '?' + urlencode({'source': source or ''})
                        content = turn_directory(result, url.path, options) + f'<p class="count"><a href="{escape(href, quote=True)}">删除此会话的受管理日志</a></p>'
                        self.respond(200, 'text/html', page('回合目录', content, projects=app.project_choices(), project_id=result['project']['id']))
                elif len(segments) == 2 and segments[0] == "export":
                    self.respond(200, "application/json", app.export_session(segments[1], instance, options.get("related") == ["1"]), download=True)
                elif len(segments) == 2 and segments[0] == "bundle":
                    self.respond(200, "application/zip", app.export_bundle(segments[1], instance, options.get("related") == ["1"]), filename="session-bundle.zip")
                elif len(segments) == 3 and segments[0] == "attachment":
                    attachment, data = app.attachment(segments[1], segments[2], instance, options.get("saved", [None])[0], options.get('turn', [None])[0])
                    media = content_type(data)
                    self.respond(200, media, data, filename=None if media.startswith("image/") else attachment["name"])
                elif len(segments) == 2 and segments[0] == "metadata":
                    self.respond(200, "application/json", json.dumps(app.metadata(segments[1], instance,
                        options.get("saved", [None])[0]), ensure_ascii=False, indent=2))
                elif len(segments) == 2 and segments[0] == "relation-evidence":
                    self.respond(200, "application/json", json.dumps(app.relation_evidence(segments[1], instance), ensure_ascii=False, indent=2))
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

        def respond(self, status: int, content_type: str, body: str | bytes, download: bool = False, filename: str | None = None) -> None:
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type + ("; charset=utf-8" if isinstance(body, str) else ""))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="session.json"')
            elif filename:
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(filename, safe=''))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            # No prompts or evidence paths in server access logs.
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
