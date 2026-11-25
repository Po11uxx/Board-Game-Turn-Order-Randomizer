# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

from ai_coder.ui_views import code_excerpt, status_card, trace_chart, usage_chart


# Verify that the excerpt is limited to 20 lines and short source is retained in full.
# 验证长源码的预览只显示前 20 行，短源码会完整保留。
def test_excerpt_preserves_full_source_separately():
    source='\n'.join(str(n) for n in range(35))
    assert code_excerpt(source).splitlines()==source.splitlines()[:20]
    assert code_excerpt('a\nb')=='a\nb'


# Verify that the status card escapes error text and exposes an accessible status role.
# 验证状态卡会转义错误文本，并向辅助技术提供状态角色。
def test_status_escapes_generated_error_text():
    html=status_card('ERROR · run abc\n<script>alert(1)</script>')
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert 'status-error' in html
    assert 'role="status"' in html


# Verify that the activity view preserves call order and indicates calls still running.
# 验证活动视图保留调用顺序，并标示仍在执行的调用。
def test_trace_keeps_order_and_missing_duration_unknown():
    html=trace_chart([{'role':'planner','tool':'plan_requirements','status':'ok','duration':1.2},
                      {'role':'tester','tool':'generate_tests','status':'running'}])
    assert html.index('plan_requirements')<html.index('generate_tests')
    assert '1.20 s' in html
    assert 'In progress' in html


# Verify that missing reasoning usage is distinguished from a known zero.
# 验证缺失的推理用量会与已知的零用量区分开。
def test_usage_does_not_display_missing_reasoning_as_known_zero():
    html=usage_chart({'run':{'api_calls':2,'provider_total_tokens':123,'unknown_usage_calls':1,
                             'reasoning_tokens':0,'reasoning_tokens_unknown_calls':2},
                      'cumulative':{'api_calls':4,'provider_total_tokens':500,'unknown_usage_calls':1}})
    assert '123' in html and '500' in html
    assert 'Not reported by Gemini for 2 API attempts' in html
    assert 'No usage data yet' in usage_chart({})


# Verify that expanding the code viewer changes its height without changing the source.
# 验证展开源码视图只改变显示高度，源码内容保持原样。
def test_code_toggle_keeps_one_component_and_does_not_replace_content():
    from ai_coder.ui import toggle_code, display_values
    import gradio as gr
    code, button, expanded = toggle_code(False, 'source')
    assert expanded and code['max_lines'] > 20 and 'value' not in code
    assert toggle_code(True, 'source')[0]['max_lines'] == 20
    source = '\n'.join(str(i) for i in range(50))
    values = display_values(('Starting', source, source, {}, {}, {}, None, None, gr.update()))
    assert values[1] == source and values[2] == source
    assert display_values(('Planning', *([gr.skip()] * 8)))[1] == gr.skip()


def test_overview_shows_final_revision_and_escapes_manual_criteria():
    from ai_coder.ui_views import result_summary
    result = {'reports': [{'passed': 2, 'collected': 3, 'startup_ok': False},
                          {'passed': 3, 'collected': 3, 'startup_ok': True}],
              'trace': [{'tool': 'repair_application'}]}
    evidence = {'spec': {'acceptance': [{'requirement_id': 'R1', 'method': 'manual',
                                        'criterion': '<script>bad</script>'}]}}
    html = result_summary(result, evidence)
    assert '3 / 3' in html and '2 / 3' not in html
    assert 'Repair rounds' in html and 'R1' in html
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'manual verification' in html


def test_not_run_status_is_not_shown_as_running():
    assert 'status-not-run' in status_card('NOT RUN · run abc\nDocker unavailable')
