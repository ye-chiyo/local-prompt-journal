"""Local presentation tokens and small, non-interactive SVG icons."""

STYLE = """
/* Shared tokens: one source for all desktop pages. */
:root {
  color-scheme: light;
  --paper: #fff;
  --ground: #f3f6fb;
  --ink: #15213b;
  --muted: #52617b;
  --accent: #0861ef;
  --accent-hover: #004bc1;
  --accent-soft: #e7f0ff;
  --line: #e0e7f1;
  --nav: #112747;
  --nav-text: #d9e7f7;
  --nav-hover: #223f68;
  --nav-active: #2369e8;
  --nav-width: 248px;
  --success: #006f55;
  --success-soft: #d9f7ee;
  --danger: #ba2548;
  --danger-soft: #fce8ee;
  --warning: #805100;
  --warning-soft: #fff0c9;
  --user-soft: #effaff;
  --agent-soft: #f3f0ff;
  --radius: 12px;
  --control-radius: 7px;
}
* { box-sizing: border-box; }
html { scroll-padding-top: 24px; }
body { margin: 0; background: var(--ground); color: var(--ink); font: 16px/1.65 'Segoe UI', 'Microsoft YaHei', sans-serif; }
::selection { background: #cddfff; color: #10254e; }
a { color: var(--accent); text-underline-offset: 3px; }
a:hover { color: var(--accent-hover); }
a:focus-visible, summary:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible { outline: 3px solid #7298d1; outline-offset: 3px; }
input, select, button { font: inherit; caret-color: var(--accent); }
button { cursor: pointer; }
button:disabled { cursor: wait; opacity: .6; }
[hidden] { display: none !important; }
.icon { display: inline-block; width: 20px; height: 20px; flex: none; vertical-align: middle; }
.skip-link { position: fixed; top: -90px; left: 24px; background: var(--ink); color: white; padding: 10px 18px; z-index: 1001; }
.skip-link:focus { top: 8px; }
h1, h2, h3 { overflow-wrap: anywhere; }
h1 { font-size: 28px; line-height: 1.35; margin: 0 0 24px; }
h2 { font-size: 22px; line-height: 1.4; margin: 0 0 12px; }
h3 { font-size: 18px; line-height: 1.5; }
p { margin: 8px 0 18px; }
.count, .muted { color: var(--muted); font-size: 14px; }
.count { font-variant-numeric: tabular-nums; }
code { font: 13px/1.7 Consolas, monospace; overflow-wrap: anywhere; }

/* Persistent project rail and compact global search. */
.app-header { position: fixed; inset: 0 auto 0 0; z-index: 2; width: var(--nav-width); padding: 24px 14px 18px; background: var(--nav); color: var(--nav-text); display: flex; flex-direction: column; overflow: hidden; }
.brand { display: flex; align-items: center; gap: 12px; padding: 0 10px 28px; color: white; text-decoration: none; font-size: 20px; line-height: 1.4; flex: none; }
.brand:hover { color: white; }
.brand .icon { width: 31px; height: 31px; }
.primary-nav { display: grid; gap: 5px; flex: none; }
.primary-nav a { display: flex; align-items: center; gap: 16px; min-height: 48px; padding: 11px 16px; border-radius: var(--control-radius); color: var(--nav-text); font-size: 16px; font-weight: 600; text-decoration: none; }
.primary-nav a:hover { background: var(--nav-hover); color: white; }
.primary-nav a[aria-current] { background: var(--nav-active); color: white; }
.primary-nav .icon, .project-nav .icon { width: 21px; height: 21px; }
.project-nav { display: grid; gap: 3px; align-content: start; flex: 1; min-height: 0; overflow-y: auto; border-top: 1px solid #35506e; margin: 24px 4px 0; padding-top: 12px; scrollbar-width: thin; scrollbar-color: #60799b transparent; }
.project-nav p { margin: 0 10px 6px; color: #adc1db; font-size: 13px; }
.project-nav a { display: flex; align-items: center; gap: 12px; min-width: 0; padding: 9px 10px; border-radius: var(--control-radius); color: var(--nav-text); font-size: 14px; text-decoration: none; }
.project-nav a span { min-width: 0; overflow-wrap: anywhere; line-height: 1.5; }
.project-nav a:hover { background: var(--nav-hover); color: white; }
.project-nav a[aria-current] { background: #315ab2; color: white; }
.collection-indicator { flex: none; margin: 0 10px; color: #c7d7ec; font-size: 13px; }
.collection-indicator::before { content: ''; display: inline-block; width: 9px; height: 9px; margin-right: 8px; border-radius: 50%; background: #8a98ad; }
.collection-indicator[data-state=running]::before { background: #26cba0; }
.collection-indicator.error { color: #ffb9c4; }
.collection-indicator.error::before { background: #ff596b; }
.app-content { margin-left: var(--nav-width); min-height: 100vh; }
.header-search { display: flex; align-items: center; gap: 12px; height: 64px; padding: 10px 22px; margin: 0; border-bottom: 1px solid var(--line); background: var(--paper); }
.header-search .icon { color: var(--muted); }
.header-search input { min-width: 0; width: 100%; height: 40px; border: 1px solid var(--line); border-radius: var(--control-radius); padding: 7px 12px; background: var(--ground); color: var(--ink); font-size: 14px; }
.header-search input::placeholder { color: #667590; }
main { padding: 0; margin: 0; min-width: 0; }
main:not(:has(.directory-layout)) { padding: 28px 32px; max-width: 1200px; margin: 0 auto 40px; }

/* Shared cards, forms and navigation. */
.action, button { display: inline-block; background: var(--accent); color: white; border: 1px solid transparent; border-radius: var(--control-radius); padding: 9px 18px; font-weight: 600; text-decoration: none; }
.action:hover, button:hover { background: var(--accent-hover); color: white; }
.source { border: 1px solid var(--line); background: var(--paper); border-radius: var(--radius); padding: 20px 24px; margin: 0 0 24px; font-size: 14px; overflow-wrap: anywhere; }
.source>h2:first-child { margin-top: 0; }
.source summary { cursor: pointer; font-weight: 600; }
.source dl { display: grid; grid-template-columns: 110px minmax(0,1fr); gap: 9px 18px; }
.source dt { color: var(--muted); }
.source dd { margin: 0; overflow-wrap: anywhere; }
.source ul { padding-left: 22px; }
.empty { padding: 24px; background: var(--paper); border: 1px dashed #b7c8e1; border-radius: var(--radius); color: var(--muted); }
.empty h2 { font-size: 20px; margin-top: 0; }
.session-list { list-style: none; padding: 0; margin: 18px 0; }
.session-list li { overflow: hidden; padding: 0; margin: 12px 0; border: 1px solid var(--line); border-radius: 10px; background: var(--paper); }
.session-list h2 { margin: 0; font-size: 18px; }
.session-list h2 a { display: block; padding: 16px 20px 3px; color: var(--ink); text-decoration: none; overflow-wrap: anywhere; }
.session-list h2 a:hover { color: var(--accent); }
.session-list p { margin: 0; padding: 0 20px 14px; color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
.session-list .project-path { padding-bottom: 5px; font-size: 12px; }
.turn-navigation { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 0 0 24px; font-size: 14px; }
.turn-navigation a { padding: 7px 13px; background: var(--paper); border: 1px solid var(--line); border-radius: var(--control-radius); text-decoration: none; }
.turn-navigation a:hover { background: var(--accent-soft); border-color: #bfd3f6; }
.turn-navigation .count { padding: 7px 0; }
.pagination { justify-content: center; margin: 24px 0; }
.pagination .page-number { background: var(--accent); border: 1px solid var(--accent); border-radius: var(--control-radius); color: white; min-width: 38px; padding: 7px; text-align: center; font-weight: 600; }
.pagination .disabled { color: #6c7c95; background: var(--ground); border: 1px solid var(--line); border-radius: var(--control-radius); padding: 7px 13px; }
.status { display: inline-block; justify-self: start; font-size: 12px; font-weight: 600; border-radius: 18px; padding: 3px 10px; color: var(--muted); background: #eef2f7; white-space: nowrap; }
.status[data-state=completed] { color: var(--success); background: var(--success-soft); }
.status[data-state=failed] { color: var(--danger); background: var(--danger-soft); }
.status[data-state=interrupted] { color: var(--warning); background: var(--warning-soft); }
.status[data-state=inProgress] { color: #393fae; background: #e5e9ff; }
.turn-links { list-style: none; margin: 0; padding: 0; }
.turn-links a { text-decoration: none; align-items: center; }
.turn-links a:hover, .turn-links a:focus-visible { background: var(--accent-soft); }
.turn-links strong { color: var(--ink); font-weight: 600; }

/* Independent reading and search. */
.reader { max-width: 1050px; }
.message { border: 1px solid var(--line); border-radius: var(--radius); margin: 16px 0 24px; padding: 22px 26px; background: var(--paper); }
.message.user { background: var(--user-soft); }
.message.agent { background: var(--agent-soft); }
.message summary { cursor: pointer; }
.message .label { font-size: 14px; font-weight: 650; }
.phase { color: var(--muted); font-size: 12px; margin-left: 14px; }
.message pre { white-space: pre-wrap; overflow-wrap: anywhere; font: 16px/1.85 'Segoe UI', 'Microsoft YaHei', sans-serif; margin: 20px 0; max-width: 75ch; }
.message footer { border-top: 1px solid var(--line); padding-top: 12px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
.message footer code { display: block; font-size: 11px; margin-top: 8px; }
.message-source { margin-top: 12px; }
.message-source summary { color: var(--accent); font-size: 13px; }
.message-source a { display: inline-block; margin-top: 8px; }
.gap { color: var(--warning); font-size: 13px; margin: 10px 0; }
.turn { margin-bottom: 32px; }
.turn>h2 { display: flex; align-items: center; justify-content: space-between; font-size: 20px; margin: 12px 0 20px; }
.turn-status { color: var(--muted); font-size: 13px; font-weight: 400; }
.search-form { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 18px 22px; align-items: end; }
.search-form label { display: grid; gap: 7px; min-width: 0; color: var(--muted); font-size: 14px; }
.search-form input, .search-form select { width: 100%; max-width: 100%; min-width: 0; height: 44px; padding: 9px 12px; border: 1px solid #b9c9df; border-radius: var(--control-radius); background: var(--paper); color: var(--ink); font-size: 14px; }
.search-form input::placeholder { color: #65758d; }
.search-form button { justify-self: start; }
.search-result h2 { font-size: 19px; margin: 0 0 10px; }
.search-result pre { font-size: 15px; line-height: 1.8; }
.search-result footer { padding-top: 14px; }
mark { background: #f6e3a8; color: #27364b; border-radius: 2px; }
.message:target { outline: 2px solid #7298d1; outline-offset: 3px; }
.lazy-content { color: var(--muted); font-style: italic; }
.layout { display: grid; grid-template-columns: 190px minmax(0,1fr); gap: 28px; }
.sidebar { font-size: 13px; }
.sidebar nav { display: grid; gap: 9px; margin: 12px 0 24px; }
.heading { display: flex; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.heading>div { min-width: 0; }

/* Session selection and management. */
.selection-notice { position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); z-index: 1000; background: #173da0; color: white; padding: 18px 28px; border: 2px solid #8db4ff; border-radius: var(--radius); box-shadow: 0 12px 36px rgba(13,37,94,.3); font-size: 18px; font-weight: 700; opacity: 0; visibility: hidden; pointer-events: none; transition: opacity .3s ease,visibility 0s linear .3s; }
.selection-notice.visible { opacity: 1; visibility: visible; transition: opacity .15s ease; }
.selection-toolbar { display: flex; align-items: center; gap: 12px; margin: 16px 24px; flex-wrap: wrap; }
.selection-toolbar span { color: var(--muted); font-size: 14px; margin-right: auto; }
.selection-toolbar button { padding: 8px 14px; font-size: 14px; }
.selection-toolbar button[value=delete] { background: var(--danger); }
.selection-toolbar button[value=delete]:hover { background: #901a36; }
.session-choice { display: flex; align-items: center; gap: 8px; padding: 10px 24px; color: var(--muted); font-size: 14px; }
.session-choice input { width: 17px; height: 17px; accent-color: var(--accent); }
.search-result .session-choice { padding: 0 0 12px; }
.manage-list { list-style: none; margin: 12px 0 32px; padding: 0; border-top: 1px solid var(--line); }
.manage-list li { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 14px 4px; border-bottom: 1px solid var(--line); }
.manage-list li span { min-width: 0; overflow-wrap: anywhere; }
.manage-list a { flex: none; font-size: 14px; text-decoration: none; }

/* Capacity remains visible beneath the independently scrolling project list. */
.capacity-card { flex: none; display: grid; gap: 5px; margin: 18px 4px 14px; padding: 14px; border: 1px solid #405c89; border-radius: 10px; background: #1c365d; color: white; text-decoration: none; font-size: 13px; }
.capacity-card:hover { color: white; background: #244777; }
.capacity-card strong { font-size: 15px; }
.capacity-card span { color: #dbe8ff; }
.capacity-track { height: 6px; background: #536b90; border-radius: 9px; overflow: hidden; }
.capacity-track span { display: block; height: 100%; width: 0; background: #3986ff; transition: width .2s; }
.capacity-track span[data-state=warning] { background: #ffcf37; }
.capacity-track span[data-state=full] { background: #ff596b; }
.capacity-settings { max-width: 780px; }
.capacity-settings form { display: flex; align-items: end; gap: 14px; flex-wrap: wrap; }
.capacity-settings label { display: grid; gap: 6px; }
.capacity-settings input, .capacity-settings select { border: 1px solid #b8c9df; border-radius: var(--control-radius); padding: 10px; min-height: 44px; }

/* Three-pane conversation workspace based on the approved desktop reference. */
.atlas-layout{display:grid;grid-template-columns:minmax(320px,37%) minmax(0,1fr);gap:10px;padding:12px;background:var(--ground);min-height:calc(100vh - 64px);align-items:start}
.atlas-sessions,.atlas-detail-heading,.atlas-turns,.atlas-reader{background:var(--paper);border:1px solid #e8edf5;border-radius:10px}
.atlas-sessions{min-width:0;overflow:hidden}.atlas-list-heading{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:16px 18px 0}.atlas-list-heading h1{font-size:23px;margin:0}.atlas-list-heading span,.atlas-session-copy small{font-size:12px;color:#64728b}.atlas-sessions .selection-toolbar{margin:12px 16px 14px}.atlas-sessions .selection-toolbar span{display:none}.atlas-sessions .selection-toolbar button{background:white;color:#1760dc;border:1px solid #2475f1}.atlas-sessions .selection-toolbar button[value=delete]{color:#d42f57;border-color:#ee5373}.atlas-sessions .selection-toolbar button:hover{background:#eef4ff}.atlas-session-list{border-top:1px solid #e8edf5}.atlas-session-row{display:flex;align-items:center;min-width:0;border-bottom:1px solid #e9edf4}.atlas-session-row.selected{background:#e4efff}.atlas-session-row .session-choice{padding:0 0 0 16px;font-size:0}.atlas-session-row .session-choice input{flex:none}.atlas-session-button{display:flex;align-items:center;gap:12px;min-width:0;flex:1;text-align:left;color:#17243c;background:transparent;border:0;padding:14px 14px 14px 12px;border-radius:0}.atlas-session-button:hover{background:#edf4ff;color:#17243c}.atlas-session-icon{display:grid;place-items:center;width:40px;height:40px;flex:none;border-radius:50%;background:#e6ddff;color:#7051df}.atlas-session-row:nth-child(4n+2) .atlas-session-icon{background:#d8f7f2;color:#00a695}.atlas-session-row:nth-child(4n+3) .atlas-session-icon{background:#fff1ce;color:#d48b00}.atlas-session-row:nth-child(4n) .atlas-session-icon{background:#dceaff;color:#1663e6}.atlas-session-copy{display:grid;gap:4px;min-width:0}.atlas-session-copy strong{font-size:15px;overflow-wrap:anywhere;line-height:1.45}.atlas-session-copy small{font-weight:400}.atlas-sessions .pagination{margin:16px 10px}
.atlas-detail{min-width:0}.atlas-detail-heading{padding:16px 22px;margin-bottom:10px}.atlas-detail-heading h2{font-size:22px}.atlas-detail-heading p{font-size:13px;color:#64728b;margin:6px 0 0}.atlas-detail-columns{display:grid;grid-template-columns:minmax(160px,26%) minmax(0,1fr);gap:10px;align-items:start}.atlas-turns,.atlas-reader{padding:16px;min-height:600px}.atlas-turns h2,.atlas-reader h2{font-size:18px;margin:0 0 16px}.atlas-turns .turn-links a{display:flex;justify-content:space-between;gap:8px;padding:10px 12px;min-height:46px;font-size:14px;border-radius:6px}.atlas-turns .turn-links li{border:0}.atlas-turns .turn-links a.selected{background:#deebff;color:#075be4}.atlas-turns .status{font-size:11px;padding:2px 6px}.atlas-reader-header{display:flex;align-items:baseline;justify-content:space-between;gap:12px;border-bottom:1px solid #e9edf5;margin-bottom:16px}.atlas-reader-header a{font-size:13px;white-space:nowrap}.atlas-placeholder{color:#65738b}.atlas-reader .turn>h2{display:none}.atlas-reader .message{padding:16px;margin:0 0 14px}.atlas-reader .message pre{font-size:15px;line-height:1.75;margin:12px 0}.atlas-reader .message.user{background:var(--user-soft)}.atlas-reader .message.agent{background:var(--agent-soft)}.atlas-reader [data-reader-content]{overflow-wrap:anywhere}
@media(max-width:1200px){.atlas-layout{grid-template-columns:minmax(260px,36%) minmax(0,1fr)}.atlas-detail-columns{grid-template-columns:minmax(130px,31%) minmax(0,1fr)}.atlas-turns,.atlas-reader{padding:12px}.atlas-turns .status{display:none}}

@media(max-width:1200px) {
  :root { --nav-width: 220px; }
  .app-header { padding-left: 10px; padding-right: 10px; }
  .brand { gap: 9px; padding-left: 8px; font-size: 18px; }
  .primary-nav a { padding-left: 14px; }
  main:not(:has(.directory-layout)) { padding: 24px; }
}
@media(prefers-reduced-motion:reduce) {
  .selection-notice, .selection-notice.visible, .capacity-track span { transition: none; }
}
"""


_PATHS = {
    'search': '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
    'folder': '<path d="M3 7V5a1 1 0 0 1 1-1h5l3 3h8a1 1 0 0 1 1 1v11H3V7Z"/><path d="M3 9h18"/>',
    'arrow': '<path d="M4 12h15m-5-5 5 5-5 5"/>',
    'chevron': '<path d="m6 9 6 6 6-6"/>',
    'trash': '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
    'check': '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
}


def icon(name: str) -> str:
    if name == 'brand':
        return '<svg class="icon" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><path fill="#7daaff" d="M3 10h21v15H9l-6 5V10Z"/><path fill="#0861ef" d="M9 2h21v21H15l-6 5V2Z"/><path stroke="white" stroke-width="1.7" stroke-linecap="round" d="M14 8h11M14 12h11M14 16h7"/></svg>'
    return '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + _PATHS[name] + '</svg>'
