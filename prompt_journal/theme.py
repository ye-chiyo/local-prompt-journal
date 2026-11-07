"""Shared visual system for the local conversation archive."""

STYLE = """
:root {
  color-scheme: light;
  --canvas: #e9ede6;
  --canvas-deep: #dfe5dc;
  --paper: #fffef9;
  --paper-soft: #f7f7f1;
  --paper-muted: #eff2eb;
  --ink: #1d2823;
  --ink-soft: #46534c;
  --muted: #5c6861;
  --quiet: #5c6861;
  --line: #d6ddd3;
  --line-strong: #b9c5b9;
  --moss: #2d5a49;
  --moss-strong: #1f4638;
  --moss-soft: #dce9df;
  --moss-faint: #eef4ef;
  --rust: #914638;
  --amber: #875617;
  --amber-soft: #f4e8d4;
  --success: #236147;
  --success-soft: #dcece3;
  --danger: #92364a;
  --danger-soft: #f5e3e7;
  --warning: #805100;
  --warning-soft: #f7edd4;
  --focus: #2f6853;
  --topbar-height: 58px;
  --rail-width: 232px;
  --sans: "Noto Sans SC", "Segoe UI", "Microsoft YaHei", sans-serif;
  --serif: "Noto Serif SC", "STSong", serif;
  --mono: "Cascadia Mono", "Consolas", monospace;
  --radius: 12px;
  --control-radius: 7px;
  --motion-fast: 160ms;
  --motion-base: 240ms;
  --motion-slow: 360ms;
  --ease-out: cubic-bezier(.22, 1, .36, 1);
  --ease-soft: cubic-bezier(.16, 1, .3, 1);
}
* { box-sizing: border-box; }
html {
  min-width: 1040px;
  scroll-padding-top: 76px;
  background: var(--canvas);
}
body {
  margin: 0;
  min-width: 1040px;
  min-height: 100vh;
  background: var(--canvas);
  color: var(--ink);
  font: 14px/1.65 var(--sans);
  letter-spacing: .006em;
  text-rendering: optimizeLegibility;
}
button, a, input, select, summary { touch-action: manipulation; }
input, textarea { caret-color: var(--moss); }
::selection { background: #cfe1d4; color: var(--moss-strong); }
a {
  color: var(--moss);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}
a:hover { color: var(--moss-strong); }
a:focus-visible,
summary:focus-visible,
button:focus-visible,
input:focus-visible,
select:focus-visible {
  outline: 3px solid var(--focus);
  outline-offset: 3px;
}
.brand:focus-visible,
.primary-nav a[aria-current]:focus-visible {
  outline-color: #f4d49b;
}
input, select, button { font: inherit; }
input[type=search]::-webkit-search-cancel-button { opacity: .72; filter: grayscale(1); }
button { cursor: pointer; }
button:disabled { cursor: wait; opacity: .62; }
[hidden] { display: none !important; }
h1, h2, h3 { overflow-wrap: anywhere; }
h1, h2 { text-wrap: balance; }
h1 {
  margin: 0 0 10px;
  font: 700 27px/1.35 var(--serif);
  letter-spacing: -.018em;
}
h2 {
  margin: 0 0 12px;
  font: 650 18px/1.45 var(--sans);
  letter-spacing: -.008em;
}
h3 { margin: 18px 0 8px; font-size: 15px; line-height: 1.5; }
p { margin: 8px 0 18px; }
code {
  font: 12px/1.65 var(--mono);
  overflow-wrap: anywhere;
  color: var(--ink-soft);
}
mark {
  padding: 1px 2px;
  border-radius: 2px;
  background: #f0dfad;
  color: #27332d;
}
.count, .muted { color: var(--muted); font-size: 12px; }
.count { font-variant-numeric: tabular-nums; }
.icon {
  display: inline-block;
  width: 18px;
  height: 18px;
  flex: none;
  vertical-align: middle;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.skip-link {
  position: fixed;
  top: -90px;
  left: 18px;
  z-index: 1002;
  padding: 10px 16px;
  border-radius: var(--control-radius);
  background: var(--moss-strong);
  color: white;
}
.skip-link:focus { top: 8px; color: white; }

@keyframes topbar-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes sidebar-in {
  from { opacity: 0; transform: translateX(-6px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes page-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes nav-in {
  from { opacity: 0; transform: translateX(-6px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes row-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes content-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes tab-in {
  from { opacity: 0; transform: scale(.9); }
  to { opacity: 1; transform: scale(1); }
}
@keyframes dialog-in {
  from { opacity: 0; transform: translateY(10px) scale(.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes backdrop-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Persistent navigation: a compact command bar and project index. */
.app-header {
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 20;
  height: var(--topbar-height);
  display: grid;
  grid-template-columns: var(--rail-width) max-content minmax(240px, 1fr) auto;
  align-items: stretch;
  border-bottom: 1px solid var(--line);
  background: var(--paper);
  animation: topbar-in var(--motion-slow) var(--ease-out) both;
}
.brand {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 18px;
  background: var(--moss-strong);
  color: #f9fbf7;
  text-decoration: none;
}
.brand:hover { color: white; }
.brand .icon { width: 25px; height: 25px; color: #dceade; }
.brand strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font: 700 16px/1.3 var(--serif);
  letter-spacing: .025em;
}
.primary-nav {
  height: 100%;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 0 12px;
}
.primary-nav a {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  border-radius: var(--control-radius);
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 650;
  text-decoration: none;
  white-space: nowrap;
  transition: background-color var(--motion-fast) var(--ease-out),
    color var(--motion-fast) var(--ease-out), transform var(--motion-fast) var(--ease-out);
}
.primary-nav a:hover { color: var(--ink); background: var(--paper-muted); }
.primary-nav a[aria-current] { color: var(--moss-strong); background: var(--moss-soft); }
.primary-nav a:active { transform: scale(.97); }
.primary-nav .icon { width: 16px; height: 16px; }
.global-search {
  align-self: center;
  min-width: 0;
  height: 38px;
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0 14px;
  padding: 0 10px 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--control-radius);
  background: var(--paper-soft);
  color: var(--muted);
}
.global-search:focus-within {
  border-color: var(--moss);
  outline: 3px solid var(--focus);
  outline-offset: 2px;
}
.global-search .icon { width: 16px; height: 16px; }
.global-search input {
  min-width: 0;
  width: 100%;
  height: 100%;
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ink);
  font-size: 13px;
}
.global-search input::placeholder { color: #59675f; opacity: 1; }
.top-status {
  align-self: center;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px 0 12px;
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.shortcut-help {
  width: 32px;
  height: 32px;
  display: inline-grid;
  place-items: center;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--paper-soft);
  color: var(--ink-soft);
}
.shortcut-help:hover { background: var(--moss-soft); color: var(--moss-strong); }
.shortcut-help .icon { width: 16px; height: 16px; }
.project-sidebar {
  position: fixed;
  inset: var(--topbar-height) auto 0 0;
  z-index: 10;
  width: var(--rail-width);
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #f3f5ee;
  animation: sidebar-in var(--motion-slow) var(--ease-out) both;
}
.project-nav {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 10px 8px 12px;
  scrollbar-width: thin;
  scrollbar-color: #a9b6ab transparent;
}
.project-nav a {
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 8px 10px;
  border-radius: 8px;
  color: var(--ink-soft);
  text-decoration: none;
  animation: nav-in var(--motion-slow) var(--ease-out) backwards;
  animation-delay: calc(var(--i, 0) * 20ms);
  transition: background-color var(--motion-fast) var(--ease-out),
    color var(--motion-fast) var(--ease-out), transform var(--motion-fast) var(--ease-out);
}
.project-nav a:hover { background: #e9eee5; color: var(--ink); }
.project-nav a[aria-current] { background: var(--moss-soft); color: var(--moss-strong); }
.project-nav a:active { transform: scale(.985); }
.project-nav a > span {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.project-nav a > span > span {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 12px;
  font-weight: 600;
}
.project-nav small {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: var(--muted);
  font: 11px/1.35 var(--mono);
}
.project-nav a[aria-current] small { color: #556159; }
.project-nav .icon { width: 17px; height: 17px; color: #738278; }
.project-nav a[aria-current] .icon { color: var(--moss); }
.rail-footer {
  flex: none;
  padding: 11px 12px 13px;
  background: #f7f8f2;
}
.capacity-card {
  display: grid;
  gap: 5px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--ink);
  text-decoration: none;
}
.capacity-card:hover { color: var(--ink); }
.capacity-card span { color: var(--muted); font-size: 12px; }
.capacity-track {
  height: 4px;
  border-radius: 4px;
  overflow: hidden;
  background: var(--canvas-deep);
}
.capacity-track span {
  display: block;
  width: 0;
  height: 100%;
  background: var(--moss);
  transition: width .2s ease-out, background-color .2s ease-out;
}
.capacity-track span[data-state=warning] { background: #b27a25; }
.capacity-track span[data-state=full] { background: var(--danger); }
.collection-indicator {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 10px;
  padding: 0 2px;
  color: var(--muted);
  font-size: 11px;
}
.collection-indicator::before {
  content: "";
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: #8b978e;
}
.collection-indicator[data-state=running]::before { background: #3a8a67; }
.collection-indicator.error { color: var(--danger); }
.collection-indicator.error::before { background: var(--danger); }
.app-content {
  min-height: 100vh;
  margin-left: var(--rail-width);
  padding-top: var(--topbar-height);
}
.app-content > main {
  width: min(1180px, calc(100% - 64px));
  margin: 0 auto;
  padding: 30px 0 44px;
  min-width: 0;
  animation: page-in var(--motion-slow) var(--ease-out) both;
}
.app-content > main.reader {
  width: min(1060px, calc(100% - 64px));
}
.app-content:has(.directory-layout) > main {
  width: 100%;
  margin: 0;
  padding: 0;
}

/* Shared actions, forms, notices and disclosure. */
.action, button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 8px 14px;
  border: 1px solid transparent;
  border-radius: var(--control-radius);
  background: var(--moss);
  color: white;
  font-size: 13px;
  font-weight: 650;
  text-decoration: none;
  transition: background-color var(--motion-fast) var(--ease-out),
    border-color var(--motion-fast) var(--ease-out),
    color var(--motion-fast) var(--ease-out),
    transform var(--motion-fast) var(--ease-out);
}
.action:hover, button:hover { background: var(--moss-strong); color: white; }
.action:active, button:active { transform: scale(.97); }
.outline-action {
  border-color: var(--moss);
  background: transparent;
  color: var(--moss-strong);
}
.outline-action:hover { background: var(--moss-soft); color: var(--moss-strong); }
.danger-action { background: var(--danger); }
.danger-action:hover { background: #752839; }
.source {
  margin: 0 0 24px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.source > h2:first-child { margin-top: 0; }
.source summary { cursor: pointer; font-weight: 600; }
.source dl {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 8px 16px;
}
.source dt { color: var(--muted); }
.source dd { margin: 0; overflow-wrap: anywhere; }
.source ul { padding-left: 20px; }
.empty {
  padding: 22px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  background: var(--paper-soft);
  color: var(--muted);
}
.empty h2 { margin-top: 0; color: var(--ink); }
.gap {
  color: var(--warning);
  font-size: 12px;
  line-height: 1.65;
}
.page-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 22px;
  margin-bottom: 20px;
}
.page-heading > div { min-width: 0; }
.page-heading h1 { margin-bottom: 3px; }
.page-heading p { margin: 0; color: var(--muted); font-size: 13px; }
.page-heading .page-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

/* Project archive: a compact index instead of a page of loose cards. */
.archive-filter {
  width: 260px;
  display: grid;
}
.archive-filter input {
  width: 100%;
  height: 38px;
  padding: 7px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--control-radius);
  background: var(--paper);
  color: var(--ink);
  outline: 0;
}
.archive-filter input:focus { border-color: var(--focus); }
.archive-filter input:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
.archive-filter input::placeholder { color: #59675f; opacity: 1; }
.archive-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.archive-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 54px;
  gap: 22px;
  align-items: center;
  min-height: 64px;
  padding: 13px 10px;
  animation: row-in var(--motion-slow) var(--ease-out) backwards;
  animation-delay: calc(var(--i, 0) * 24ms);
  transition: background-color var(--motion-fast) var(--ease-out),
    transform var(--motion-fast) var(--ease-out);
}
.archive-row:hover { background: var(--paper-soft); transform: translateY(-1px); }
.archive-row h2 { margin: 0; font-size: 15px; }
.archive-row h2 a { color: var(--ink); text-decoration: none; }
.archive-row h2 a:hover { color: var(--moss); text-decoration: underline; }
.project-context {
  margin: 3px 0 0;
  color: var(--muted);
  font: 12px/1.45 var(--mono);
  overflow-wrap: anywhere;
}
.project-path {
  margin: 4px 0 16px;
  color: var(--muted);
  font: 12px/1.5 var(--mono);
  overflow-wrap: anywhere;
}
.project-amount {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.project-delete-link {
  justify-self: end;
  padding: 6px 8px;
  border-radius: 5px;
  color: var(--rust);
  font-size: 12px;
  text-decoration: none;
  transition: background-color var(--motion-fast) var(--ease-out),
    color var(--motion-fast) var(--ease-out),
    transform var(--motion-fast) var(--ease-out);
}
.project-delete-link:hover { background: var(--danger-soft); color: var(--danger); }
.project-delete-link:active { transform: scale(.96); }

/* Project workspace: persistent context, session index, turn ruler, reader. */
.directory-layout {
  display: grid;
  grid-template-columns: 304px minmax(0, 1fr);
  grid-template-rows: 78px minmax(0, 1fr);
  grid-template-areas: "project project" "sessions detail";
  gap: 14px 16px;
  height: calc(100dvh - var(--topbar-height));
  padding: 16px 20px 20px;
  background: var(--canvas);
}
.project-directory-head {
  grid-area: project;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 0 2px;
}
.project-directory-head > div { min-width: 0; flex: 1; }
.project-directory-head h1 {
  margin: 1px 0 2px;
  font-size: 25px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.project-directory-head p {
  margin: 0;
  color: var(--muted);
  font: 12px/1.5 var(--mono);
  overflow-wrap: anywhere;
}
.project-directory-head .project-facts {
  display: flex;
  align-items: center;
  gap: 15px;
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.directory-back {
  display: inline-flex;
  align-items: center;
  color: var(--muted);
  font-size: 11px;
  text-decoration: none;
}
.directory-back:hover { color: var(--moss); }
.directory-back:active { transform: scale(.97); }
.atlas-sessions,
.atlas-detail {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.atlas-detail { background: var(--paper); }
.atlas-sessions {
  grid-area: sessions;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
}
.atlas-session-list {
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #aab8ae transparent;
}
.atlas-session-row {
  display: flex;
  align-items: stretch;
  min-height: 68px;
  border-radius: 8px;
  animation: row-in var(--motion-slow) var(--ease-out) backwards;
  animation-delay: calc(var(--i, 0) * 22ms);
  transition: background-color var(--motion-base) var(--ease-out),
    transform var(--motion-base) var(--ease-out);
}
.atlas-session-row:hover { transform: translateX(2px); }
.atlas-session-row.selected { background: var(--moss-faint); }
.session-choice {
  flex: none;
  width: 37px;
  min-height: 42px;
  display: grid;
  place-items: center;
  font-size: 0;
  cursor: pointer;
}
.session-choice input {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: var(--moss);
}
.atlas-session-button {
  min-width: 0;
  min-height: 0;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 12px 13px 12px 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--ink);
  text-align: left;
  transition: background-color var(--motion-fast) var(--ease-out),
    color var(--motion-fast) var(--ease-out),
    transform var(--motion-fast) var(--ease-out);
}
.atlas-session-button:hover { background: #f1f5ee; color: var(--ink); }
.atlas-session-button:active { transform: scale(.985); }
.atlas-session-button:focus-visible { outline-offset: -3px; }
.atlas-session-copy {
  width: 100%;
  min-width: 0;
  display: grid;
  justify-items: start;
  gap: 6px;
}
.atlas-session-copy strong {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.5;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.atlas-session-copy small {
  color: var(--muted);
  font: 11px/1.45 var(--mono);
  font-variant-numeric: tabular-nums;
}
.atlas-sessions .pagination {
  min-height: 45px;
  margin: 0;
  padding: 7px 0;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  margin-top: 18px;
}
.pagination a,
.pagination .disabled,
.pagination .page-number {
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 9px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--paper);
  color: var(--ink-soft);
  font-size: 11px;
  text-decoration: none;
}
.pagination a:hover { background: var(--moss-soft); border-color: var(--line-strong); color: var(--moss-strong); }
.pagination a:active { transform: scale(.96); }
.pagination .disabled { color: var(--quiet); background: var(--paper-soft); }
.pagination .page-number {
  border-color: var(--moss);
  background: var(--moss);
  color: white;
  font-family: var(--mono);
}
.atlas-detail {
  grid-area: detail;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
}
.atlas-detail-heading {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 20px 10px;
  background: var(--paper);
}
.atlas-detail-heading > div { min-width: 0; }
.atlas-detail-heading h2 {
  margin: 0 0 4px;
  font: 650 18px/1.45 var(--sans);
}
.session-context {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px 14px;
  color: var(--muted);
  font-size: 12px;
}
.session-context p { margin: 0; font: inherit; }
.selection-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0 0;
  flex-wrap: wrap;
}
.selection-toolbar span { margin-right: auto; color: var(--muted); font-size: 11px; }
.selection-toolbar button {
  min-height: 30px;
  padding: 5px 9px;
  border: 1px solid var(--line-strong);
  background: var(--paper);
  color: var(--moss);
  font-size: 11px;
}
.selection-toolbar button:hover { background: var(--moss-soft); color: var(--moss-strong); }
.selection-toolbar button[value=delete] { color: var(--danger); }
.selection-toolbar button[value=delete]:hover { background: var(--danger-soft); }
.selection-toolbar.selection-ready:not(.has-selection) { display: none; }
.atlas-turn-rail {
  min-width: 0;
  overflow: hidden;
}
.atlas-turn-group { min-width: 0; padding: 9px 12px; }
.turn-ruler {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  margin: 0;
  padding: 0 0 2px;
  list-style: none;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #b5c2b8 transparent;
}
.turn-links { margin: 0; padding: 0; list-style: none; }
.turn-ruler li { flex: none; }
.turn-tab {
  min-width: 40px;
  height: 36px;
  display: grid;
  place-items: center;
  gap: 2px;
  grid-template-columns: 1fr;
  grid-template-rows: auto;
  padding: 4px 5px 3px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--ink-soft);
  font: 11px/1 var(--mono);
  text-decoration: none;
  animation: tab-in var(--motion-base) var(--ease-soft) backwards;
  animation-delay: calc(var(--i, 0) * 22ms);
  transition: background-color var(--motion-fast) var(--ease-out),
    color var(--motion-fast) var(--ease-out),
    transform var(--motion-base) var(--ease-soft);
}
.turn-tab:has(.turn-state-label) {
  min-width: 62px;
  grid-template-columns: auto 1fr;
  column-gap: 4px;
}
.turn-state-label { color: inherit; font: 11px/1 var(--sans); letter-spacing: .01em; }
.turn-tab:hover {
  background: var(--moss-soft);
  color: var(--moss-strong);
  transform: scale(1.04);
}
.turn-tab.selected {
  background: var(--moss);
  color: white;
  font-weight: 700;
  transform: scale(1.03);
}
.turn-tab.selected:hover { color: white; background: var(--moss-strong); }
.turn-tab:active { transform: scale(.94); }
.atlas-turn-group [data-turn-more] {
  min-height: 34px;
  width: 100%;
  margin-top: 7px;
  border: 0;
  background: transparent;
  color: var(--moss);
  font-size: 11px;
}
.atlas-turn-group [data-turn-more]:hover { background: var(--moss-soft); }
.atlas-reader {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 24px 40px;
  scrollbar-width: thin;
  scrollbar-color: #b0beb3 transparent;
}
.atlas-reader-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 17px;
  padding-bottom: 0;
}
.atlas-reader-header h2 {
  margin: 0;
  font: 650 14px/1.4 var(--sans);
}
.atlas-reader-header a { font-size: 11px; text-decoration: none; }
.atlas-reader [data-reader-content] { max-width: 74ch; }
.atlas-reader .turn { margin: 0; }
.atlas-reader .turn > h2 { display: none; }
.atlas-reader .message { margin: 0; padding: 0 0 22px; }

/* Turn reading and message typography. */
.turn-navigation {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin: 0 0 18px;
  font-size: 12px;
}
.turn-navigation a {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--paper);
  text-decoration: none;
}
.turn-navigation a:hover { background: var(--moss-soft); border-color: var(--line-strong); }
.turn-navigation a { transition: background-color var(--motion-fast) var(--ease-out), border-color var(--motion-fast) var(--ease-out), color var(--motion-fast) var(--ease-out), transform var(--motion-fast) var(--ease-out); }
.turn-navigation a:active { transform: scale(.96); }
.reader-version { margin: 0 0 16px; color: var(--muted); font-size: 11px; }
.reader-version summary { width: fit-content; cursor: pointer; }
.heading { margin-bottom: 20px; }
.heading h1 { margin-top: 6px; }
.heading p { margin: 5px 0; }
.heading > div > a { font-size: 12px; text-decoration: none; }
.turn {
  margin: 0 0 28px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}
.turn > h2 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 16px;
  font: 650 17px/1.4 var(--sans);
}
.turn-status { color: var(--muted); font: 11px/1.4 var(--mono); }
.reader .turn { padding-bottom: 0; }
.message {
  margin: 0;
  padding: 17px 0 18px;
  border: 0;
  border-radius: 0;
  background: transparent;
  animation: content-in var(--motion-slow) var(--ease-out) backwards;
}
.message > summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px 14px;
  cursor: pointer;
  list-style-position: outside;
}
.message > summary::-webkit-details-marker { color: var(--muted); }
.message-heading {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
}
.message .label {
  display: inline-flex;
  align-items: center;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 650;
}
.message-time { color: var(--muted); font: 12px/1.45 var(--sans); white-space: nowrap; }
.phase { margin-left: 8px; color: var(--muted); font-size: 11px; }
.message > pre {
  max-width: 74ch;
  margin: 13px 0 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: #27352e;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 15px/1.85 var(--sans);
}
.message > p, .message > section, .message > footer, .message > h3 {
  max-width: 74ch;
  margin-left: 0;
}
.message > p { margin-top: 12px; margin-bottom: 9px; }
.message > h3 { font-size: 13px; }
.message > footer {
  margin-top: 12px;
  padding-top: 10px;
  color: var(--muted);
  font-size: 11px;
  overflow-wrap: anywhere;
}
.message > footer code { display: block; margin-top: 6px; font-size: 11px; }
.message-source { margin-top: 8px; }
.message-source summary { color: var(--moss); font-size: 12px; }
.message-source a { display: inline-block; margin-top: 7px; }
.message:target { outline: 2px solid var(--moss); outline-offset: 3px; }
.lazy-content { color: var(--muted); font-style: italic; }
.reader .heading { padding-bottom: 0; }
.reader .heading h1 { max-width: 850px; }
.reader .turn { border-radius: 0; }
.message.tool { padding: 0; }
.message.tool > summary,
.message.execution > summary {
  padding: 13px 0;
  color: var(--ink-soft);
  font-size: 12px;
}
.message.tool > h3,
.message.tool > pre,
.message.tool > footer,
.message.tool > p,
.message.execution > p,
.message.execution > details { margin-left: 0; max-width: 74ch; }

/* Search: filters stay compact, hits read as index entries. */
.search-query {
  margin: 0 0 20px;
  padding: 0;
}
.search-form { display: grid; gap: 11px; }
.search-query-row {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) auto;
  gap: 9px;
  align-items: end;
}
.search-query-row label {
  display: grid;
  gap: 5px;
  color: var(--muted);
  font-size: 11px;
}
.search-form input,
.search-form select {
  width: 100%;
  min-width: 0;
  height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--control-radius);
  background: var(--paper);
  color: var(--ink);
  font-size: 13px;
}
.search-form input::placeholder { color: #59675f; opacity: 1; }
.search-form input:focus, .search-form select:focus {
  border-color: var(--focus);
  outline: 3px solid var(--focus);
  outline-offset: 2px;
}
.search-advanced {
  padding-top: 8px;
}
.search-advanced > summary {
  width: fit-content;
  color: var(--muted);
  font-size: 12px;
}
.search-scope {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 30px;
  color: var(--muted);
  font-size: 12px;
}
.scope-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: min(420px, 100%);
  padding: 0;
  color: var(--ink-soft);
}
.scope-chip b { color: var(--muted); font-weight: 500; }
.search-scope a { margin-left: auto; font-size: 12px; text-decoration: none; }
.search-filter-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
  margin-top: 10px;
}
.search-filter-grid label {
  display: grid;
  gap: 5px;
  min-width: 0;
  color: var(--muted);
  font-size: 11px;
}
.search-filter-grid [data-session-more] {
  grid-column: 2;
  justify-self: end;
  min-height: 34px;
  border: 1px solid var(--line-strong);
  background: var(--paper);
  color: var(--moss);
  font-size: 11px;
}
.search-results-summary {
  width: 100%;
  max-width: 960px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 8px;
}
.search-results-summary p { margin: 0; color: var(--muted); font-size: 12px; }
.search-results-summary .selection-toolbar { margin: 0; }
.search-result-list { width: 100%; max-width: 960px; display: grid; gap: 0; }
.search-result {
  margin: 0;
  padding: 14px 0;
  font-size: 13px;
  animation: row-in var(--motion-slow) var(--ease-out) backwards;
  animation-delay: calc(var(--i, 0) * 28ms);
  transition: transform var(--motion-base) var(--ease-out);
}
.search-result:hover { transform: translateX(2px); }
.search-result .session-context { font-size: 12px; }
.search-result .session-choice {
  width: 18px;
  min-height: 22px;
  display: inline-flex;
  justify-content: flex-start;
  gap: 0;
  font-size: 0;
}
.search-result h2 {
  margin: 1px 0 4px;
  font-size: 14px;
  line-height: 1.45;
}
.search-result h2 a {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  overflow: hidden;
  text-decoration: none;
}
.search-result h2 a:hover { text-decoration: underline; }
.search-result p { margin: 3px 0; }
.search-result pre {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  margin: 7px 0;
  max-width: none;
  color: var(--ink-soft);
  white-space: pre-wrap;
  font: 13px/1.7 var(--sans);
}
.search-result footer {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
}
.search-pagination {
  width: 100%;
  max-width: 960px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin: 14px 0 0;
}
.search-pagination .pager-links { display: flex; gap: 7px; }
.search-pagination a {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid var(--line-strong);
  border-radius: 5px;
  background: var(--paper);
  text-decoration: none;
  font-size: 11px;
  transition: background-color var(--motion-fast) var(--ease-out),
    border-color var(--motion-fast) var(--ease-out),
    transform var(--motion-fast) var(--ease-out);
}
.search-pagination a:active { transform: scale(.96); }
.search-pagination span { color: var(--muted); font: 11px/1.4 var(--mono); }

/* Status: grouped diagnostics with actions instead of a wall of IDs. */
.status-overview {
  display: grid;
  grid-template-columns: minmax(240px, .75fr) minmax(360px, 1.25fr);
  gap: 30px;
  margin-bottom: 26px;
}
.status-state { display: grid; align-content: start; gap: 8px; }
.collection-state {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  margin: 0;
  padding: 0;
  color: var(--moss-strong);
  font: 650 22px/1.4 var(--serif);
}
.status-state.error .collection-state { color: var(--danger); }
.status-state.warning .collection-state { color: var(--warning); }
.status-state.stopped .collection-state { color: var(--ink-soft); }
.status-facts {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 7px 28px;
  max-width: 640px;
  margin: 0;
  font-size: 12px;
}
.status-facts dt { color: var(--muted); }
.status-facts dd { margin: 0; font-variant-numeric: tabular-nums; }
.diagnostic-card {
  padding: 0;
}
.diagnostic-card h2 { margin-bottom: 8px; font-size: 16px; }
.diagnostic-group {
  margin-top: 4px;
  border: 0;
  border-radius: 0;
  background: transparent;
}
.diagnostic-group > summary {
  padding: 10px 0;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 600;
}
.diagnostic-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.diagnostic-list li {
  display: grid;
  grid-template-columns: minmax(160px, 1.1fr) minmax(150px, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 8px 0;
  font-size: 12px;
}
.diagnostic-list code { font-size: 11px; color: var(--muted); }
.diagnostic-list a { text-decoration: none; }
.technical-details { margin-top: 11px; }
.technical-details summary { color: var(--muted); font-size: 12px; }
.technical-details dl { margin-top: 9px; }

/* Capacity and deletion management reuse the same calm surfaces. */
.capacity-settings { max-width: 800px; }
.capacity-settings h2 { margin-top: 26px; }
.capacity-settings dl {
  display: grid;
  grid-template-columns: 100px minmax(0, 1fr);
  gap: 8px 16px;
  margin: 10px 0 0;
}
.capacity-settings dt { color: var(--muted); }
.capacity-settings dd { margin: 0; overflow-wrap: anywhere; }
.capacity-settings form {
  display: flex;
  align-items: end;
  gap: 12px;
  flex-wrap: wrap;
}
.capacity-settings label {
  display: grid;
  gap: 5px;
  color: var(--muted);
  font-size: 12px;
}
.capacity-settings input, .capacity-settings select {
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--control-radius);
  background: var(--paper);
  color: var(--ink);
}
.capacity-settings input { width: 210px; max-width: 100%; }
.capacity-summary {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 20px;
}
.capacity-summary > strong { font: 600 27px/1.2 var(--serif); font-variant-numeric: tabular-nums; }
.capacity-summary small { color: var(--muted); font: 12px/1.4 var(--sans); }
.capacity-summary > span { color: var(--muted); font-size: 12px; }
.capacity-meter {
  width: 100%;
  height: 8px;
  margin: 14px 0;
  border: 0;
  border-radius: 8px;
  overflow: hidden;
  accent-color: var(--moss);
}
.capacity-meter::-webkit-progress-bar { background: var(--moss-soft); border-radius: 8px; }
.capacity-meter::-webkit-progress-value { background: var(--moss); border-radius: 8px; }
[data-capacity-state=warning] .capacity-meter::-webkit-progress-value { background: #b27a25; }
[data-capacity-state=full] .capacity-meter::-webkit-progress-value { background: var(--danger); }
.capacity-state { color: var(--moss); font-weight: 600; }
[data-capacity-state=warning] .capacity-state { color: var(--warning); }
[data-capacity-state=full] .capacity-state { color: var(--danger); }
.capacity-rules { margin: 14px 0 0; color: var(--muted); font-size: 12px; }
.capacity-rules summary { width: fit-content; cursor: pointer; }
.capacity-feedback {
  max-width: 800px;
  padding: 11px 13px;
  border-radius: var(--control-radius);
  background: var(--success-soft);
  color: var(--success);
}
.capacity-feedback[role=alert] { background: var(--danger-soft); color: var(--danger); }
.deletion-safety { margin: 0 0 28px; color: var(--ink-soft); }
.manage-list {
  list-style: none;
  margin: 8px 0 28px;
  padding: 0;
}
.manage-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 42px;
  padding: 7px 0;
}
.manage-list li span { min-width: 0; overflow-wrap: anywhere; }
.manage-list a { flex: none; font-size: 12px; text-decoration: none; }
.management-action { margin-top: 12px; }
.exclusion { margin: 0 0 20px; }
.exclusion h2 { margin-bottom: 2px; font-size: 15px; }

/* Keyboard help and selection feedback remain native and unobtrusive. */
.shortcut-dialog {
  width: min(520px, calc(100vw - 40px));
  padding: 0;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  background: var(--paper);
  color: var(--ink);
}
.shortcut-dialog[open] { animation: dialog-in var(--motion-slow) var(--ease-soft) both; }
.shortcut-dialog::backdrop {
  background: rgba(20, 31, 26, .35);
  animation: backdrop-in var(--motion-base) var(--ease-out) both;
}
.shortcut-dialog-inner { padding: 22px; }
.shortcut-dialog h2 { margin: 0 0 14px; font: 650 18px/1.4 var(--serif); }
.shortcut-dialog dl {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 10px 16px;
  margin: 0 0 18px;
}
.shortcut-dialog dt { color: var(--ink-soft); font: 11px/1.5 var(--mono); }
.shortcut-dialog dd { margin: 0; color: var(--muted); font-size: 12px; }
.shortcut-dialog kbd {
  display: inline-block;
  min-width: 26px;
  padding: 3px 6px;
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  background: var(--paper-soft);
  color: var(--ink-soft);
  font: 11px/1.2 var(--mono);
  text-align: center;
}
.selection-notice {
  position: fixed;
  top: 50%;
  left: 50%;
  z-index: 1000;
  transform: translate(-50%, -50%) scale(.94);
  padding: 15px 24px;
  border: 0;
  border-radius: 9px;
  background: var(--moss-strong);
  color: white;
  font-size: 15px;
  font-weight: 650;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity var(--motion-fast) var(--ease-out),
    transform var(--motion-base) var(--ease-soft),
    visibility 0s linear var(--motion-fast);
}
.selection-notice.visible {
  opacity: 1;
  visibility: visible;
  transform: translate(-50%, -50%) scale(1);
  transition: opacity var(--motion-fast) var(--ease-out),
    transform var(--motion-base) var(--ease-soft);
}

/* One responsive adjustment set for the two supported PC widths. */
@media (max-width: 1200px) {
  :root { --rail-width: 204px; }
  .app-header { grid-template-columns: var(--rail-width) max-content minmax(190px, 1fr) auto; }
  .brand { padding: 0 14px; gap: 8px; }
  .brand strong { font-size: 15px; }
  .brand .icon { width: 22px; height: 22px; }
  .primary-nav { padding: 0 7px; }
  .primary-nav a { padding: 0 7px; gap: 5px; }
  .global-search { margin: 0 9px; }
  .top-status { gap: 8px; padding-right: 10px; }
  .top-status > span:last-child { display: none; }
  .app-content > main { width: calc(100% - 44px); }
  .archive-row { grid-template-columns: minmax(0, 1fr) 80px 54px; gap: 14px; }
  .directory-layout {
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 10px 12px;
    padding: 12px 14px 16px;
  }
  .project-directory-head h1 { font-size: 23px; }
  .atlas-detail-heading { padding-left: 16px; padding-right: 16px; }
  .atlas-reader { padding-left: 22px; padding-right: 22px; }
  .message > pre { margin-left: 29px; }
  .message > p, .message > section, .message > footer, .message > h3 {
    max-width: calc(74ch + 29px);
    margin-left: 29px;
  }
  .status-overview { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: .01ms !important;
    animation-delay: 0s !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
    transition-delay: 0s !important;
  }
}
"""
