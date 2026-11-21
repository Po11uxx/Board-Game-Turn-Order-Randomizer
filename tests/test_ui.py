import asyncio
import pytest
from ai_coder import ui
from ai_coder.ui import parse_request, build_ui


def test_requirements_are_explicit_numbered_inputs():
    request = parse_request('App', 'R1: Count players\nR2: Shuffle')
    assert [r.id for r in request.requirements] == ['R1','R2']
    with pytest.raises(ValueError):
        parse_request('App', 'Shuffle somehow')


def test_ui_builds_without_credentials(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    app = build_ui()
    assert app is not None


def test_mcp_activity_streams_before_final_result(monkeypatch, tmp_path):
    async def scenario():
        release_call = asyncio.Event()

        class Agents:
            def __init__(self, runs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def call(self, role, name, arguments):
                await release_call.wait()
                raise RuntimeError('Gemini unavailable')

        monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
        monkeypatch.setattr(ui, 'RUNS', tmp_path)
        monkeypatch.setattr(ui, 'AgentClients', Agents)
        monkeypatch.setattr(ui.RUNNER, 'check', lambda: None)
        updates = ui.generate_display('App', 'R1: Count players')
        try:
            async with asyncio.timeout(5):
                async for update in updates:
                    chart, trace, result = update[4], update[5], update[9]
                    if isinstance(trace, list) and trace:
                        assert trace[0]['status'] == 'running'
                        assert 'plan_requirements' in chart and 'In progress' in chart
                        running = trace
                        assert result.get('__type__') == 'update'
                        break
                else:
                    pytest.fail('No running MCP call was streamed')

                release_call.set()
                error_streamed = False
                async for update in updates:
                    chart, trace, result = update[4], update[5], update[9]
                    if isinstance(trace, list):
                        assert trace[0]['status'] == 'error'
                        assert 'duration' in trace[0] and 'error' in chart
                        if result.get('__type__') == 'update':
                            error_streamed = True
                        else:
                            assert error_streamed
                            assert result['status'] == 'ERROR'
                            assert running[0]['status'] == 'running'
                            break
                else:
                    pytest.fail('No final MCP trace was returned')
        finally:
            await updates.aclose()

    asyncio.run(scenario())


def test_result_display_enables_preview_only_for_passed_runs():
    import gradio as gr
    from ai_coder.ui import display_values

    for status in ('PASSED', 'FAILED', 'ERROR', 'NOT RUN'):
        result = {'status': status, 'reports': [], 'trace': []}
        values = display_values((status, '', '', {}, [], {}, None, result, gr.update()))
        assert values[12]['interactive'] == (status == 'PASSED')
        assert 'Verification summary' in values[11]
    cleared = display_values(('Starting', '', '', {}, {}, {}, None, None, gr.update()))
    assert not cleared[12]['interactive']
    assert cleared[13] == 'No preview running.'
