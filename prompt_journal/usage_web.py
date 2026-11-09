"""Approved dashboard markup; behavior and scoped styles are served locally."""

BODY = """<div class="usage-dashboard"><h1>用量概览</h1><p class="usage-state" id="usage-state" role="status">正在读取用量…</p><button type="button" id="usage-retry" hidden>重新读取</button>
<div class="toolbar">
 <div class="filters">
  <div class="range" aria-label="统计时段"><button data-days="1" aria-pressed="false">今天</button><button data-days="7" aria-pressed="false">最近 7 天</button><button data-days="30" aria-pressed="false">最近 30 天</button><button data-days="90" aria-pressed="true">最近 90 天</button></div>
  <label class="field">项目 <select id="project"><option value="">全部项目</option></select></label>
  <label class="field">会话 <select id="source"><option value="main">主会话</option><option value="child">子 agent</option><option value="all">全部</option></select></label>
 </div>

</div>
<dl class="summary">
 <div><dt>完成回合</dt><dd id="rounds"></dd></div>
 <div><dt>总 token</dt><dd id="tokens"></dd><small>输入 <span id="input"></span> · 输出 <span id="output"></span></small></div>
 <div><dt>缓存输入 token</dt><dd id="cached"></dd></div>
 <div><dt>活跃天数</dt><dd id="active"></dd></div>
</dl>
<section class="surface timeline">
 <div class="section-head"><h2>时间趋势</h2><select id="metric" aria-label="趋势指标"><option value="tokens">token</option><option value="rounds">回合数</option></select></div>
 <div class="heatmap">
  <div class="months" id="months" aria-hidden="true"></div>
  <div class="calendar"><div class="weekdays" aria-hidden="true"><span>一</span><span></span><span>三</span><span></span><span>五</span><span></span><span>日</span></div><div class="heat-grid" id="trend" role="group" aria-label="每日用量热力图"></div></div>
  <div class="heat-legend" id="heat-legend" aria-label="热力图用量等级"></div>
 </div>
</section>
<div class="analysis">
 <section class="surface"><div class="section-head"><h2>活跃时间</h2></div><div class="hours" id="hours" aria-label="每小时回合数"></div><div class="axis"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:00</span></div></section>
 <section class="surface">
  <div class="section-head"><h2>模型用量分布</h2></div>
  <p class="chart-empty" id="model-empty" hidden>暂无已取得的模型用量</p><div class="ring-area"><div class="ring" id="ring"><svg viewBox="0 0 240 240" aria-label="模型用量环状图" role="group" id="ring-chart"></svg><div class="ring-center"><strong id="ring-total"></strong><small id="ring-label">总 token</small></div></div><ul class="legend" id="legend"></ul></div>
 </section>
</div>
<div class="details">
 <section class="surface"><table><caption>模型明细</caption><thead><tr><th>模型</th><th>token</th><th>占比</th></tr></thead><tbody id="models"></tbody></table></section>
 <section class="surface"><table><caption>项目用量</caption><thead><tr><th>项目</th><th>完成回合</th><th>token</th></tr></thead><tbody id="projects"></tbody></table></section>
</div>
<div class="chart-tooltip" id="chart-tooltip" role="tooltip"></div>

</div><link rel="stylesheet" href="/usage.css"><script src="/usage.js" defer></script>"""
