import asyncio
from types import SimpleNamespace
import pytest
from google.genai import errors
from ai_coder.gemini import Gemini
from ai_coder.models import Application
from ai_coder.usage import Ledger

VALID = '{"files":[{"path":"app.py","content":"pass"},{"path":"logic.py","content":"pass"},{"path":"README.md","content":"Run"}]}'

@pytest.mark.parametrize('recover', [True, False])
def test_provider_retry_is_bounded_and_tracked(tmp_path, monkeypatch, recover):
    waits=[]
    async def sleep(delay): waits.append(delay)
    monkeypatch.setattr('ai_coder.gemini.asyncio.sleep', sleep)
    class Models:
        attempts=0
        async def generate_content(self, **kwargs):
            self.attempts+=1
            if not recover or self.attempts < 4:
                raise errors.ServerError(503, {'error':{'message':'High demand'}})
            return SimpleNamespace(text=VALID, usage_metadata=None)
    model=Models()
    adapter=Gemini(Ledger(tmp_path/'usage.jsonl'), client=SimpleNamespace(aio=SimpleNamespace(models=model)))
    call=adapter.generate('r','planner','plan',{},Application)
    if recover: asyncio.run(call)
    else:
        with pytest.raises(RuntimeError, match='4 API attempts'): asyncio.run(call)
    assert model.attempts==4
    assert len(waits)==3
    assert all(base <= actual <= base+1 for base,actual in zip([5,10,20],waits))
    calls=adapter.ledger.calls()
    assert len(calls)==4
    assert calls[0]['error_code']==503
    assert adapter.ledger.summary()['failed_calls']==(3 if recover else 4)


def test_failed_ui_has_recovery_without_preview():
    import gradio as gr
    from ai_coder.ui import display_values
    result={'status':'FAILED','detail':'one failing test','reports':[], 'trace':[]}
    values=display_values(('FAILED', '', '', {}, [], {}, 'failure.zip',result,gr.update(interactive=True)))
    assert values[10]['value']=='Generate again'
    assert values[12]['visible'] is False
    assert values[8]['label']=='Download diagnostics'
    assert values[15]['visible'] is True
    assert 'What to do next' in values[11]


def test_running_ui_hides_unused_controls():
    import gradio as gr
    from ai_coder.ui import display_values
    values=display_values(('Starting','','',{},[],{},None,None,gr.update(interactive=False)))
    assert values[8]['visible'] is False
    assert values[12]['visible'] is False
    assert values[14]['visible'] is False
    assert values[16]['interactive'] is False
    assert 'Generation in progress' in values[11]
