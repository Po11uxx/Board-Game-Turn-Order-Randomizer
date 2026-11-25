# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import asyncio
import pytest
from ai_coder import ui
from ai_coder.ui import parse_request, build_ui


# Verify that numbered requirements parse and unnumbered entries are rejected.
# 验证带编号的需求可以解析，未编号的需求会被拒绝。
def test_requirements_are_explicit_numbered_inputs():
    request = parse_request('App', 'R1: Count players\nR2: Shuffle')
    assert [r.id for r in request.requirements] == ['R1','R2']
    with pytest.raises(ValueError):
        parse_request('App', 'Shuffle somehow')


# Verify that the interface can be constructed before a Gemini key is configured.
# 验证没有配置 Gemini 密钥时也能构建界面。
def test_ui_builds_without_credentials(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    app = build_ui()
    assert app is not None


# Verify that both MCP views report running and failed calls before receiving the final result.
# 验证两种 MCP 视图会在收到最终结果前显示调用进行中和失败的状态。
def test_mcp_activity_streams_before_final_result(monkeypatch, tmp_path):
    # Drive the asynchronous generation callback and inspect its updates while the fake call is paused.
    # 驱动异步生成回调，并在模拟调用暂停时检查界面更新。
    async def scenario():
        release_call = asyncio.Event()

        class Agents:
            # Accept the same workspace argument as the real MCP client without opening a subprocess.
            # 接收与真实 MCP 客户端相同的工作区参数，但不启动子进程。
            def __init__(self, runs):
                pass

            # Return the fake client from its asynchronous context manager.
            # 进入异步上下文时返回模拟客户端。
            async def __aenter__(self):
                return self

            # Allow the fake client context to close without transport cleanup.
            # 退出模拟客户端的异步上下文，无需关闭真实传输连接。
            async def __aexit__(self, *args):
                pass

            # Wait until the running state is observed and then simulate a model error.
            # 等到界面读到进行中状态，再模拟模型调用失败。
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
