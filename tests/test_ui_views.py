from ai_coder.ui_views import code_excerpt, status_card, trace_chart, usage_chart


def test_excerpt_preserves_full_source_separately():
    source='\n'.join(str(n) for n in range(35))
    assert code_excerpt(source).splitlines()==source.splitlines()[:20]
    assert code_excerpt('a\nb')=='a\nb'


def test_status_escapes_generated_error_text():
    html=status_card('ERROR · run abc\n<script>alert(1)</script>')
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert 'status-error' in html
    assert 'role="status"' in html


def test_trace_keeps_order_and_missing_duration_unknown():
    html=trace_chart([{'role':'planner','tool':'plan_requirements','status':'ok','duration':1.2},
                      {'role':'tester','tool':'generate_tests','status':'running'}])
    assert html.index('plan_requirements')<html.index('generate_tests')
    assert '1.20 s' in html
    assert 'In progress' in html


def test_usage_does_not_display_missing_reasoning_as_known_zero():
    html=usage_chart({'run':{'api_calls':2,'provider_total_tokens':123,'unknown_usage_calls':1,
                             'reasoning_tokens':0,'reasoning_tokens_unknown_calls':2},
                      'cumulative':{'api_calls':4,'provider_total_tokens':500,'unknown_usage_calls':1}})
    assert '123' in html and '500' in html
    assert 'Not reported by Gemini for 2 API attempts' in html
    assert 'No usage data yet' in usage_chart({})


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
