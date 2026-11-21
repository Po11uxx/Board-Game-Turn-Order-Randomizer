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
from ai_coder.ui_views import CSS, status_card, trace_chart, usage_chart

load_dotenv(ROOT / '.env')
RUNS = ROOT / 'runs'
BUSY = threading.Lock()
RUNNER = DockerRunner()
PREVIEW = None
DESCRIPTION = 'Board Game Turn Order Randomizer: a simple browser application that randomizes the playing order for a group of board-game players.'
REQUIREMENTS = '''R1: Accept an integer player count from 2 to 20 and exactly that many player names. Show one name field per player. If the UI callback receives hidden fields too, only the first N fields count, including any blanks among those N.
R2: Trim names; reject blank names, invalid counts, mismatched counts and case-insensitive duplicate names with helpful errors.
R3: Use a standard uniform shuffle to produce a random permutation; do not use random sort comparisons.
R4: Display numbered positions 1 through N, include every player exactly once, and do not mutate the original input list.
R5: Support reshuffling the same players, editing players and resetting all input and output.
R6: Explain that repeated orders are valid and random ordering does not guarantee balanced game outcomes.
R7: Work without accounts or a database and do not persist player names by default.
R8: Deliver runnable source, dependency instructions, a README and executable tests. Test app.randomize_callback, the actual Randomize button callback, with four names and the hidden fields its Gradio event supplies. Verify that it returns four numbered names without an error.'''


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


def source_view(root, paths):
    return '\n\n'.join(f'# --- {p.relative_to(root)} ---\n{p.read_text()}' for p in paths)


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
        async def work():
            async with AgentClients(RUNS) as agents:
                return await Pipeline(
                    RUNS, agents, RUNNER,
                    notify=lambda state: queue.put_nowait((state, gr.skip())),
                    notify_trace=lambda trace: queue.put_nowait((gr.skip(), trace)),
                ).run(request)
        task = asyncio.create_task(work())
        while not task.done() or not queue.empty():
            try:
                state, trace = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield (state, gr.skip(), gr.skip(), gr.skip(), trace, gr.skip(), gr.skip(), gr.skip(), gr.update(interactive=False))
            except TimeoutError:
                pass
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
        yield (f'ERROR: {str(exc)[:2000]}', '', '', {}, {}, {}, None, None, gr.update(interactive=True))
    finally:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        BUSY.release()


def display_values(values):
    status, source, tests, evidence, trace, usage, bundle, result, button = values
    def render(value, formatter):
        return value if isinstance(value, dict) and value.get('__type__') == 'update' else formatter(value)
    return (render(status, status_card), source, tests, evidence, render(trace, trace_chart), trace,
            render(usage, usage_chart), usage, bundle, result, button)


async def generate_display(description, requirements):
    async for values in generate(description, requirements):
        yield display_values(values)


def stop_preview():
    global PREVIEW
    if PREVIEW:
        RUNNER.stop_preview(PREVIEW)
        PREVIEW = None
    return 'Preview stopped.'


def start_preview(result):
    global PREVIEW
    if not result or result['status'] != 'PASSED':
        raise gr.Error('Preview requires passed tests and startup verification.')
    stop_preview()
    PREVIEW, url = RUNNER.preview(Path(result['generated']))
    return f'Open the generated app: [{url}]({url}). Manually verify shuffle, edit and reset; this is separate from automated tests.'


def toggle_code(expanded, label):
    expanded = not expanded
    return (gr.update(max_lines=100000 if expanded else 20),
            gr.update(value=f"Show less  ▴" if expanded else f"View full {label}  ▾"), expanded)



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
                requirements = gr.Textbox(label='Requirements (one R-number per line)', value=REQUIREMENTS, lines=19, elem_classes='request-field')
                button = gr.Button('Generate application', variant='primary')
            with gr.Column(scale=3, min_width=420, elem_classes='output-column'):
                status = gr.HTML(status_card('Ready to generate\nDocker runner and Gemini credentials are required.'), elem_classes='status-panel')
                with gr.Column(elem_classes="results-card"):
                    with gr.Tabs():
                        with gr.Tab('Application'):
                            with gr.Group(elem_classes='expandable-code'):
                                code = gr.Code(label='Application source', language='python', interactive=False, lines=1, max_lines=20)
                                source_toggle = gr.Button('View full source  ▾', elem_classes='code-toggle')
                            source_expanded = gr.State(False)
                            source_toggle.click(lambda expanded: toggle_code(expanded, 'source'), source_expanded,
                                                [code, source_toggle, source_expanded], api_name=False)
                            with gr.Row(elem_classes='preview-actions'):
                                preview = gr.Button('Open isolated preview', variant='primary', scale=2, min_width=180)
                                close = gr.Button('Stop preview', scale=1, min_width=120)
                            preview_link = gr.Markdown('No preview running.')
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
                    download = gr.File(label='Download project · check run status before use', interactive=False, elem_classes='project-download')
        result = gr.State(None)
        button.click(generate_display, [description, requirements],
                     [status, code, tests, evidence, trace_visual, trace, usage_visual, usage, download, result, button],
                     api_name='generate',
                     concurrency_limit=1, concurrency_id='generation', trigger_mode='once')
        preview.click(start_preview, result, preview_link, concurrency_limit=1, concurrency_id='preview')
        close.click(stop_preview, outputs=preview_link, concurrency_limit=1, concurrency_id='preview')
    return app


if __name__ == '__main__':
    atexit.register(stop_preview)
    build_ui().queue(max_size=1).launch(server_name='127.0.0.1', share=False, run_history=False, footer_links=[],
        theme=gr.themes.Soft(primary_hue='emerald', neutral_hue='slate'), css=CSS,
        blocked_paths=[str(ROOT / '.env'), str(ROOT / '.git')])
