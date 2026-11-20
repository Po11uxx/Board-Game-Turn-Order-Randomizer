import asyncio
from types import SimpleNamespace
import pytest
from ai_coder.gemini import Gemini, instructions
from ai_coder.models import Application
from ai_coder.usage import Ledger
from ai_coder.client import AgentClients


def test_rules_are_role_specific():
    assert 'Do not repeat checks' in instructions('developer')
    assert 'Do not modify tests' in instructions('developer')
    assert 'Never require two random outcomes to differ' in instructions('tester')
    with pytest.raises(ValueError):
        instructions('../secret')


def test_usage_survives_invalid_response(tmp_path):
    class Models:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text='not JSON', usage_metadata=SimpleNamespace(model_dump=lambda **kw: {'total_token_count': 19}))
    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    adapter = Gemini(Ledger(tmp_path / 'usage.jsonl'), client=client)
    with pytest.raises(ValueError):
        asyncio.run(adapter.generate('run', 'developer', 'generate', {}, Application))
    assert adapter.ledger.summary()['provider_total_tokens'] == 38
    assert adapter.ledger.summary()['api_calls'] == 2


def test_real_stdio_role_discovery(tmp_path):
    async def scenario():
        async with AgentClients(tmp_path) as agents:
            assert await agents.tools('planner') == {'plan_requirements'}
            assert await agents.tools('developer') == {'generate_application', 'repair_application'}
            assert await agents.tools('tester') == {'generate_tests'}
    asyncio.run(scenario())


def test_malformed_output_has_one_tracked_retry(tmp_path):
    class Models:
        count = 0
        async def generate_content(self, **kwargs):
            self.count += 1
            text = 'invalid' if self.count == 1 else '{"files":[{"path":"app.py","content":"pass"},{"path":"logic.py","content":"pass"},{"path":"README.md","content":"Run app.py"}]}'
            return SimpleNamespace(text=text, usage_metadata=SimpleNamespace(model_dump=lambda **kw: {'total_token_count': 7}))
    models = Models()
    adapter = Gemini(Ledger(tmp_path / 'usage.jsonl'), client=SimpleNamespace(aio=SimpleNamespace(models=models)))
    result = asyncio.run(adapter.generate('run', 'developer', 'generate', {}, Application))
    assert len(result.files) == 3
    assert adapter.ledger.summary()['api_calls'] == 2
    assert adapter.ledger.summary()['provider_total_tokens'] == 14


def test_api_error_explains_failure_without_exposing_key(tmp_path, monkeypatch):
    from google.genai import errors
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret-value')
    class Models:
        async def generate_content(self, **kwargs):
            raise errors.ClientError(400, {'error': {'message':'Unsupported schema; key test-secret-value'}})
    adapter = Gemini(Ledger(tmp_path / 'usage.jsonl'), client=SimpleNamespace(aio=SimpleNamespace(models=Models())))
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(adapter.generate('run', 'planner', 'plan', {}, Application))
    assert 'Unsupported schema' in str(caught.value)
    assert 'test-secret-value' not in str(caught.value)


def test_full_json_schema_uses_json_schema_parameter(tmp_path):
    class Models:
        async def generate_content(self, **kwargs):
            config = kwargs['config']
            assert config.response_schema is None
            assert config.response_json_schema == Application.model_json_schema()
            return SimpleNamespace(text='{"files":[{"path":"app.py","content":"pass"},{"path":"logic.py","content":"pass"},{"path":"README.md","content":"Run"}]}', usage_metadata=None)
    adapter = Gemini(Ledger(tmp_path / 'usage.jsonl'), client=SimpleNamespace(aio=SimpleNamespace(models=Models())))
    asyncio.run(adapter.generate('run', 'developer', 'generate', {}, Application))
