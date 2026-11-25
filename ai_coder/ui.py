# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import asyncio
import atexit
import json
import os
import re
import threading
from pathlib import Path
import gradio as gr
from dotenv import load_dotenv
from ai_coder.client import AgentClients
from ai_coder.gemini import ROOT
from ai_coder.models import Request, Requirement
from ai_coder.orchestrator import Pipeline
from ai_coder.runner import DockerRunner
from ai_coder.usage import Ledger
from ai_coder.ui_views import CSS, status_card, trace_chart, usage_chart, result_summary

load_dotenv(ROOT / '.env')
RUNS = ROOT / 'runs'
BUSY = threading.Lock()
RUNNER = DockerRunner()
PREVIEW = None
DESCRIPTION = 'Board Game Turn Order Randomizer: a simple browser application that randomizes the playing order for a group of board-game players.'
REQUIREMENTS = '''
R1: Accept an integer player count from 2 to 20 and exactly that many player names. Strictly enforce the inclusive 2–20 range in the player-count input: an out-of-range value must display a visible warning and prevent turn-order generation; do not silently clamp or replace the value. Show one name field per player. If the UI callback receives hidden fields too, only the first N fields count, including any blanks among those N.
R2: Trim names; reject blank names, invalid counts, mismatched counts and case-insensitive duplicate names with helpful errors.
R3: Use a standard uniform shuffle to produce a random permutation; do not use random sort comparisons.
R4: Display numbered positions 1 through N, include every player exactly once, and do not mutate the original input list.
R5: Support reshuffling the same players, editing players and resetting all input and output.
R6: Explain that repeated orders are valid and random ordering does not guarantee balanced game outcomes.
R7: Work without accounts or a database and do not persist player names by default.
R8: Deliver runnable source, dependency instructions, a README and executable tests. Test app.randomize_callback, the actual Randomize button callback, with four names and the hidden fields its Gradio event supplies. Verify that it returns four numbered names without an error.'''


# Parse the description and numbered requirement lines into the pipeline request model.
# 将描述和带编号的需求行转换成生成流程使用的请求对象。
def parse_request(description, lines):
    requirements = []
    for line in lines.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'\s*(R[1-9][0-9]*)\s*:\s*(.+)', line)
        if not match:
            raise ValueError('Use one requirement per line, such as R1: Accept player names')
        requirements.append(Requirement(id=match[1], text=match[2]))
    return Request(description=description, requirements=requirements)


# Combine source files for display and label each file with its path relative to the generated workspace.
# 拼接用于展示的源码，并标出每个文件相对于生成工作区的路径。
def source_view(root, paths):
    return '\n\n'.join(f'# --- {p.relative_to(root)} ---\n{p.read_text()}' for p in paths)


# Serialize UI-triggered runs and stream progress and results while releasing resources on exit.
# 让界面每次只执行一个生成任务，持续返回进度和结果，并在退出时释放资源。
async def generate(description, requirements):
    try:
        request = parse_request(description, requirements)
    except ValueError as exc:
        raise gr.Error(str(exc)) from None
    if not os.environ.get('GEMINI_API_KEY'):
        raise gr.Error('Set GEMINI_API_KEY in the backend environment before generating.')
    if not BUSY.acquire(blocking=False):
        raise gr.Error('Another generation is running. Please wait.')
    task = None
    try:
        stop_preview()
        yield ('Starting', '', '', {}, {}, {}, None, None, gr.update(interactive=False))
        queue = asyncio.Queue()
        # Keep the role sessions open for the pipeline and queue its progress and MCP trace snapshots.
        # 在流程中保持角色会话开启，把进度和 MCP 调用记录的副本放入队列。
        async def work():
            async with AgentClients(RUNS) as agents:
                return await Pipeline(
                    RUNS, agents, RUNNER,
                    notify=lambda state: queue.put_nowait((state, gr.skip())),
                    notify_trace=lambda trace: queue.put_nowait((gr.skip(), trace)),
                ).run(request)
        task = asyncio.create_task(work())
        active_run = None
        last_api_event = None
        while not task.done() or not queue.empty():
            try:
                state, trace = await asyncio.wait_for(queue.get(), timeout=0.5)
                if isinstance(trace, list) and trace:
                    active_run = trace[-1]['run_id']
                yield (state, gr.skip(), gr.skip(), gr.skip(), trace, gr.skip(), gr.skip(), gr.skip(), gr.update(interactive=False))
            except TimeoutError:
                if active_run:
                    calls = Ledger(RUNS / 'usage.jsonl').calls(active_run)
                    latest = calls[-1] if calls else {}
                    event = (latest.get('call_id'), latest.get('event'))
                    if event != last_api_event and latest.get('retry_delay') is not None:
                        last_api_event = event
                        state = (f"{latest['agent_id'].title()} · waiting to retry Gemini "
                                 f"(HTTP {latest['error_code']}, {latest['retry_delay']:.0f}s backoff; bounded retries)")
                        yield (state, *[gr.skip() for _ in range(7)], gr.update(interactive=False))
                    elif event != last_api_event and latest.get('event') == 'start':
                        last_api_event = event
                        yield (f"{latest['agent_id'].title()} · requesting Gemini", *[gr.skip() for _ in range(7)], gr.update(interactive=False))
        result = await task
        root = Path(result['generated'])
        source = source_view(root, sorted(root.glob('*.py')))
        tests = source_view(root, sorted((root / 'tests').glob('*.py')))
        evidence = {'execution':result['reports'], 'manual_ui_validation':'NOT RUN'}
        for name in ('spec', 'coverage'):
            path = root.parent / f'{name}.json'
            if path.exists():
                evidence[name] = json.loads(path.read_text())
        yield (f"{result['status']} · run {result['run_id']}\n{result['detail']}",
               source, tests, evidence, result['trace'], result['usage'], result['bundle'], result,
               gr.update(interactive=True))
    except Exception as exc:
        # Preserve a usable UI when MCP startup fails before a run is created.
        # 如果 MCP 在创建运行记录前启动失败，仍让界面保持可用。
        yield (f'ERROR: {str(exc)[:2000]}', '', '', {}, {}, {}, None, None, gr.update(interactive=True))
    finally:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        BUSY.release()


# Convert pipeline updates into the outputs expected by the graphical and raw-data views.
# 把流程更新转换成图形视图和原始数据视图需要的输出。
def display_values(values):
    status, source, tests, evidence, trace, usage, bundle, result, button = values
    # Pass through Gradio update instructions and format only new values for display.
    # 直接传递 Gradio 更新指令，只格式化新收到的值。
    def render(value, formatter):
        return value if isinstance(value, dict) and value.get('__type__') == 'update' else formatter(value)
    streaming = isinstance(result, dict) and result.get('__type__') == 'update'
    terminal = not streaming and (result is not None or str(status).startswith('ERROR'))
    passed = terminal and result is not None and result.get('status') == 'PASSED'
    failed = terminal and not passed
    overview_result = result if result else ({'status':'ERROR', 'detail':str(status)} if terminal else None)
    summary = gr.skip() if streaming else (
        result_summary(overview_result, evidence) if terminal else
        '<p>Generation in progress. Follow Run status and MCP activity. Temporary Gemini errors are retried automatically, at most four API attempts per agent call.</p>')
    return (render(status, status_card), source, tests, evidence, render(trace, trace_chart), trace,
            render(usage, usage_chart), usage,
            gr.skip() if streaming else gr.update(value=bundle, visible=bool(bundle), label='Download project' if passed else 'Download diagnostics'),
            result, gr.update(value='Generate again', interactive=True) if terminal else button,
            summary, gr.skip() if streaming else gr.update(visible=passed, interactive=passed),
            gr.skip() if streaming else gr.update(value='No preview running.', visible=passed),
            gr.skip() if streaming else gr.update(visible=False),
            gr.skip() if streaming else gr.update(visible=failed),
            gr.skip() if streaming else gr.update(interactive=terminal),
            gr.skip() if streaming else gr.update(interactive=terminal))



# Stream presentation-ready updates from the generation callback to the UI.
# 将格式化后的生成进度和结果逐步发送给界面。
async def generate_display(description, requirements):
    async for values in generate(description, requirements):
        yield display_values(values)


# Stop the active preview container and clear the tracked preview state.
# 停止当前的预览容器，并清除保存的预览状态。
def stop_preview():
    global PREVIEW
    if PREVIEW:
        RUNNER.stop_preview(PREVIEW)
        PREVIEW = None
    return 'Preview stopped.'


# Start a localhost preview for a generation that passed tests and its startup check.
# 为通过测试和启动检查的应用开启本机预览。
def start_preview(result):
    global PREVIEW
    if not result or result['status'] != 'PASSED':
        raise gr.Error('Preview requires passed tests and startup verification.')
    stop_preview()
    PREVIEW, url = RUNNER.preview(Path(result['generated']))
    return f'Open the generated app: [{url}]({url}). Manually verify shuffle, edit and reset; this is separate from automated tests.'


def preview_display(result):
    yield gr.update(value='Starting preview…', visible=True), gr.update(visible=True, interactive=False), gr.update(visible=False)
    try:
        message = start_preview(result)
    except Exception as exc:
        message = f'Preview could not start: {str(exc)[:2000]}\n\nThe generation result is unchanged. Check Docker, then select Open isolated preview again.'
        yield gr.update(value=message, visible=True), gr.update(interactive=True), gr.update(visible=False)
    else:
        yield gr.update(value=message, visible=True), gr.update(interactive=True), gr.update(visible=True)


def stop_preview_display():
    return stop_preview(), gr.update(visible=False)


# Resize the existing source viewer and update its button without replacing the displayed code.
# 调整现有源码视图的高度和按钮状态，保留正在展示的代码。
def toggle_code(expanded, label):
    expanded = not expanded
    return (gr.update(max_lines=100000 if expanded else 20),
            gr.update(value=f"Show less  ▴" if expanded else f"View full {label}  ▾"), expanded)



# Build the Gradio inputs, result tabs, and event bindings for generation and preview controls.
# 创建 Gradio 输入区和结果标签页，并为生成与预览控件绑定事件。
def build_ui():
    with gr.Blocks(title='AI Coder', analytics_enabled=False) as app:
        with gr.Row(elem_classes='page-header'):
            with gr.Column(scale=3, min_width=360):
                gr.Markdown('# AI Coder\nGenerate, test and inspect a small Python app with three Gemini-powered MCP agents.')
            with gr.Column(scale=2, min_width=300):
                gr.HTML('<div class="header-spacers" aria-hidden="true"><span></span><span></span><span></span></div>')
        with gr.Row(elem_classes='workspace-layout'):
            with gr.Column(scale=2, min_width=340, elem_classes='input-card'):
                description = gr.Textbox(label='Software description', value=DESCRIPTION, lines=4, elem_classes='request-field')
                requirements = gr.Textbox(elem_id='requirements-input', label='Requirements (one R-number per line)', value=REQUIREMENTS, lines=19, elem_classes='request-field')
                button = gr.Button('Generate application', variant='primary')
            with gr.Column(scale=3, min_width=420, elem_classes='output-column'):
                status = gr.HTML(status_card('Ready to generate\nDocker runner and Gemini credentials are required.'), elem_classes='status-panel')
                with gr.Column(elem_classes="results-card"):
                    with gr.Tabs():
                        with gr.Tab('Overview'):
                            summary = gr.HTML(result_summary(None, {}))
                            with gr.Row(elem_classes='preview-actions'):
                                preview = gr.Button('Open isolated preview', variant='primary', interactive=False, visible=False, scale=2, min_width=180)
                                close = gr.Button('Stop preview', visible=False, scale=1, min_width=120)
                            preview_link = gr.Markdown('No preview running.', visible=False)
                            edit = gr.Button('Edit inputs', visible=False)
                            edit.click(fn=None, js="() => {const field=document.querySelector('#requirements-input textarea'); field.scrollIntoView({behavior:'smooth', block:'center'}); field.focus();}", api_name=False)
                            download = gr.File(label='Download project · check run status before use', interactive=False, visible=False, elem_classes='project-download')
                        with gr.Tab('Application'):
                            with gr.Group(elem_classes='expandable-code'):
                                code = gr.Code(label='Application source', language='python', interactive=False, lines=1, max_lines=20)
                                source_toggle = gr.Button('View full source  ▾', elem_classes='code-toggle')
                            source_expanded = gr.State(False)
                            source_toggle.click(lambda expanded: toggle_code(expanded, 'source'), source_expanded,
                                                [code, source_toggle, source_expanded], api_name=False)
                        with gr.Tab('Tests'):
                            with gr.Group(elem_classes='expandable-code'):
                                tests = gr.Code(label='Test source', language='python', interactive=False, lines=1, max_lines=20)
                                tests_toggle = gr.Button('View full tests  ▾', elem_classes='code-toggle')
                            tests_expanded = gr.State(False)
                            tests_toggle.click(lambda expanded: toggle_code(expanded, 'tests'), tests_expanded,
                                               [tests, tests_toggle, tests_expanded], api_name=False)
                            with gr.Accordion('Execution evidence and requirement mapping', open=False):
                                evidence = gr.JSON(label='Execution, specification and requirement mapping')
                        with gr.Tab('MCP activity'):
                            with gr.Tabs(selected='graphical'):
                                with gr.Tab('Graphical', id='graphical'):
                                    trace_visual = gr.HTML(trace_chart({}))
                                with gr.Tab('JSON', id='json'):
                                    trace = gr.JSON(label='Actual MCP tool calls')
                        with gr.Tab('Usage'):
                            with gr.Tabs(selected='graphical'):
                                with gr.Tab('Graphical', id='graphical'):
                                    usage_visual = gr.HTML(usage_chart({}))
                                with gr.Tab('JSON', id='json'):
                                    usage = gr.JSON(label='Run and cumulative usage (unknown counts are explicit)')
        result = gr.State(None)
        button.click(generate_display, [description, requirements],
                     [status, code, tests, evidence, trace_visual, trace, usage_visual, usage, download, result, button, summary, preview, preview_link, close, edit, description, requirements],
                     api_name='generate', show_progress='hidden',
                     concurrency_limit=1, concurrency_id='generation', trigger_mode='once')
        preview.click(preview_display, result, [preview_link, preview, close], show_progress='hidden', concurrency_limit=1, concurrency_id='preview')
        close.click(stop_preview_display, outputs=[preview_link, close], show_progress='hidden', concurrency_limit=1, concurrency_id='preview')
    return app


if __name__ == '__main__':
    atexit.register(stop_preview)
    build_ui().queue(max_size=1).launch(server_name='127.0.0.1', share=False, run_history=False, footer_links=[],
        theme=gr.themes.Soft(primary_hue='emerald', neutral_hue='slate'), css=CSS,
        blocked_paths=[str(ROOT / '.env'), str(ROOT / '.git')])
