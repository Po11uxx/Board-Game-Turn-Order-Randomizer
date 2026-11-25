# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

"""Small, escaped HTML views; raw evidence remains available in adjacent tabs."""
from html import escape

CSS = '''
.run-card {padding:12px 4px;background:var(--background-fill-secondary);border-radius:12px}
.run-card h3 {margin:4px 0!important}.run-card p {white-space:pre-wrap;overflow-wrap:anywhere}
.status-passed .status-value {color:#047857}.status-error .status-value,.status-failed .status-value {color:#be123c}.status-running .status-value {color:#0369a1}
.status-value {font-size:18px;font-weight:600;margin:8px 0!important}
.expandable-code {gap:0!important;overflow:hidden;background:white!important}
.expandable-code > div {gap:0!important}
.expandable-code .code-toggle {position:relative;margin:0!important;border:0!important;border-radius:0!important;background:var(--block-background-fill)!important;text-align:center!important;justify-content:center;min-height:44px!important}
.expandable-code .code-toggle::before {content:"";position:absolute;left:0;right:0;bottom:100%;height:36px;background:linear-gradient(transparent,var(--block-background-fill));pointer-events:none;z-index:2}
.expandable-code .block {border:0!important;border-radius:0!important;padding-bottom:0!important}
.view-label {font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--body-text-color-subdued)}
.metric-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:12px 0}
.metric {padding:14px;border:1px solid var(--border-color-primary);border-radius:10px}.metric strong {display:block;font-size:24px}
.activity-row {padding:14px 0;border-bottom:1px solid var(--border-color-primary);overflow-wrap:anywhere}
.activity-heading {display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.chart-track {height:8px;background:var(--background-fill-secondary);border-radius:6px;margin:8px 0;overflow:hidden}
.chart-bar {height:100%;background:#059669;border-radius:6px}.chart-note {font-size:12px;color:var(--body-text-color-subdued)}
.gradio-container {width:100%!important;max-width:1440px!important;margin:0 auto!important;padding:28px 32px!important;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important}
.page-header {align-items:center!important;gap:24px!important;margin-bottom:24px!important}
.page-header h1 {font-size:30px!important;font-weight:750!important;letter-spacing:-1px;line-height:1.2!important;margin-bottom:10px!important}
.page-header p {font-size:15px!important;line-height:1.5!important}
.workspace-layout {display:flex!important;flex-wrap:wrap!important;width:100%!important;gap:24px!important;align-items:flex-start!important}
.gradio-container .main {width:100%!important}
.header-spacers {display:flex;justify-content:flex-end;gap:8px;height:34px;visibility:hidden;pointer-events:none}
.header-spacers span {display:block;width:100px;height:30px}
.header-spacers span:nth-child(2) {width:176px}
.input-card,.results-card,.status-panel.block {background:var(--block-background-fill)!important;border:1px solid var(--border-color-primary)!important;border-radius:16px!important;box-shadow:0 3px 12px rgba(15,23,42,.04);padding:24px!important}
.input-card {gap:22px!important}.output-column {gap:20px!important}.results-card {gap:16px!important;min-width:0!important}
.input-card .form {background:transparent!important;border:0!important;box-shadow:none!important;gap:22px!important}
.request-field label.container {background:transparent!important;border:0!important;box-shadow:none!important}
.request-field .input-container {border:0!important;box-shadow:none!important}
.request-field {border:0!important;padding:0!important;background:transparent!important}
.request-field label > span {font-size:12px!important;font-weight:650!important;letter-spacing:.06em;text-transform:uppercase;background:transparent!important;padding:0 0 9px!important}
.request-field textarea {font-family:inherit!important;font-size:14px!important;line-height:1.55!important;border:1px solid var(--border-color-primary)!important;border-radius:12px!important;padding:14px 16px!important}
.input-card button,.preview-actions button {border-radius:12px!important;font-size:14px!important;font-weight:650!important;min-height:46px!important}
.status-panel.block {padding:20px 24px!important}.run-card {padding:0;background:transparent;border-radius:0}
.run-card h3 {font-size:14px!important;font-weight:650!important}.status-value {font-size:16px;line-height:1.5}
.run-card summary {font-size:13px}.run-card details p {font-size:13px;line-height:1.6}
.results-card .tab-nav {gap:12px!important;padding-bottom:0!important}
.results-card .tab-nav button {font-size:14px!important;font-weight:600!important;padding:10px 6px!important}
.results-card .tabitem {padding:16px 0 0!important;border:0!important}
.expandable-code {border-radius:12px!important;border:1px solid var(--border-color-primary)!important}
.expandable-code .cm-editor {font-family:"SFMono-Regular",Consolas,monospace!important;font-size:13px!important}
.expandable-code .cm-line {line-height:1.65!important}
.expandable-code .code-toggle {font-size:13px!important;font-weight:600!important}
.preview-actions {gap:12px!important;margin-top:2px!important}
.project-download {min-height:80px!important;border-radius:12px!important}
.project-download .empty {min-height:54px!important;height:54px!important}
@media(max-width:800px) {.gradio-container {padding:20px 16px!important}.workspace-layout {gap:18px!important}.input-card,.results-card,.status-panel.block {padding:18px!important}}

@media(max-width:700px) {.header-spacers {display:none}}
'''


# Return the first 20 lines of source for a compact preview.
# 取源码的前 20 行，用于简要预览。
def code_excerpt(text):
    return '\n'.join(text.splitlines()[:20])


# Render the run state and escaped details in an accessible HTML status card.
# 把运行状态和经过转义的详情渲染成支持辅助技术的 HTML 状态卡片。
def status_card(text):
    title, _, detail = text.partition('\n')
    state = next((s for s in ('PASSED', 'FAILED', 'ERROR', 'NOT RUN') if title.startswith(s)), None)
    kind = state.lower().replace(' ', '-') if state else ('ready' if title.startswith('Ready') else 'running')
    icon = {'passed':'✓', 'failed':'✕', 'error':'!', 'ready':'○', 'not-run':'○', 'running':'◷'}[kind]
    details = f'<details><summary>Run details</summary><p>{escape(detail)}</p></details>' if detail else ''
    return f'<section class="run-card status-{kind}" role="status"><h3>Run status</h3><p class="status-value">{icon} {escape(title)}</p>{details}</section>'


# Scale a chart bar against the largest recorded value.
# 以记录中的最大值为基准计算图表条形的宽度。
def bar(value, maximum):
    width = 100 * value / maximum if maximum else 0
    return f'<div class="chart-track"><div class="chart-bar" style="width:{width:.2f}%"></div></div>'


# Show MCP calls in execution order with their state and available durations.
# 按执行顺序展示 MCP 调用的状态和已记录的耗时。
def trace_chart(trace):
    if not trace:
        return '<p>No MCP activity yet. Start a generation to see agent tool calls.</p>'
    maximum = max((call.get('duration', 0) for call in trace), default=0)
    rows = []
    for number, call in enumerate(trace, 1):
        state = call['status']
        duration = f"{call['duration']:.2f} s" if 'duration' in call else ('In progress' if state == 'running' else 'Not reported')
        icon = {'ok':'✓', 'error':'✕', 'running':'◷'}.get(state, '○')
        rows.append(f'<div class="activity-row"><div class="activity-heading"><strong>{number}. {escape(call["role"].title())} · {escape(call["tool"])}</strong><span>{icon} {escape(state)} · {duration}</span></div>{bar(call.get("duration", 0), maximum)}</div>')
    return f'<p><strong>{len(trace)} MCP tool calls</strong> · in execution order</p>' + ''.join(rows) + '<p class="chart-note">Bars compare recorded call durations. MCP calls and model API attempts are counted separately.</p>'


# Render an escaped metric label, value, and optional note.
# 转义并展示指标名称、数值和可选说明。
def metric(label, value):
    main, _, note = str(value).partition(' · ')
    return f'<div class="metric"><span>{escape(label)}</span><strong>{escape(main)}</strong><span class="chart-note">{escape(note)}</span></div>'


# Format known token totals and show how many API attempts lack that measurement.
# 格式化已知 token 总量，并标出有多少次 API 请求缺少该项数据。
def token_value(summary, key):
    unknown = summary.get(key + '_unknown_calls', 0)
    value = summary.get(key, 0)
    label = 'Not reported' if unknown and unknown == summary.get('api_calls') else f'{value:,}'
    return label + (f' · Not reported by Gemini for {unknown} API attempts' if unknown else '')


# Render per-run, cumulative, and per-agent model usage from the recorded data.
# 展示单次运行、累计和按角色统计的模型用量。
def usage_chart(usage):
    if not usage:
        return '<p>No usage data yet. Recorded API attempts and token counts appear after a run.</p>'
    parts = []
    for scope, title in (('run', 'This run'), ('cumulative', 'All recorded runs')):
        summary = usage.get(scope, {})
        parts.append(f'<h3>{title}</h3><div class="metric-grid">' +
                     metric('API attempts', summary.get('api_calls', 0)) +
                     metric('Known provider tokens', token_value(summary, 'provider_total_tokens')) +
                     metric('Failed attempts', summary.get('failed_calls', 0)) + '</div>')
        parts.append(f'<p class="chart-note">{summary.get("unknown_usage_calls", 0)} attempts with unavailable usage metadata.</p>')
    summary = usage['run']
    parts.append('<h3>Token breakdown · this run</h3><div class="metric-grid">')
    for key, label in (('input_tokens', 'Input'), ('output_tokens', 'Output'), ('reasoning_tokens', 'Reasoning')):
        parts.append(metric(label, token_value(summary, key)))
    parts.append('</div><p class="chart-note">Reasoning is read from usage_metadata.thoughts_token_count when present. A missing field is not a measured zero. Provider totals already include any reported thinking tokens; do not add them again.</p>')
    agents = usage.get('per_agent', {})
    if agents:
        maximum = max(agent.get('provider_total_tokens', 0) for agent in agents.values())
        parts.append('<h3>Known provider tokens by agent</h3>')
        for role, agent in agents.items():
            parts.append(f'<div class="activity-row"><div class="activity-heading"><strong>{escape(role.title())}</strong><span>{token_value(agent, "provider_total_tokens")} tokens · {agent.get("api_calls", 0)} API attempts</span></div>{bar(agent.get("provider_total_tokens", 0), maximum)}</div>')
    return ''.join(parts)


def result_summary(result, evidence):
    if not result:
        return '<p>Generate an application to see test results and requirements needing review.</p>'
    reports = result.get('reports', [])
    latest = reports[-1] if reports else None
    repairs = sum(call.get('tool') == 'repair_application' for call in result.get('trace', []))
    parts = ['<h3>Verification summary</h3><div class="metric-grid">',
             metric('Tests passed', f"{latest['passed']} / {latest['collected']}" if latest else 'Not run'),
             metric('Startup check', 'Passed' if latest and latest.get('startup_ok') else 'Not verified'),
             metric('Repair rounds', repairs), '</div>']
    manual = [item for item in evidence.get('spec', {}).get('acceptance', []) if item['method'] == 'manual']
    parts.append('<p>Browser interactions require manual verification. Automated success does not prove every requirement.</p>')
    if manual:
        parts.append('<h3>Requirements needing manual review</h3><ul>')
        parts.extend(f"<li><strong>{escape(item['requirement_id'])}</strong>: {escape(item['criterion'])}</li>" for item in manual)
        parts.append('</ul>')
    return ''.join(parts)
