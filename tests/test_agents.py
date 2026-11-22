# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import asyncio
from types import SimpleNamespace
import pytest
from ai_coder.gemini import Gemini, instructions
from ai_coder.models import Application
from ai_coder.usage import Ledger
from ai_coder.client import AgentClients


# Verify that each role has its expected rules and unknown role names are rejected.
# 验证各角色加载了预期规则，且未知角色名称会被拒绝。
def test_rules_are_role_specific():
    assert 'Do not repeat checks' in instructions('developer')
    assert 'Do not modify tests' in instructions('developer')
    assert 'Never require two random outcomes to differ' in instructions('tester')
    with pytest.raises(ValueError):
        instructions('../secret')


# Verify that API usage is recorded even when the model response fails JSON validation.
# 验证模型响应未通过 JSON 校验时，用量仍然会被记录。
def test_usage_survives_invalid_response(tmp_path):
    class Models:
        # Return malformed JSON with token metadata so the ledger can be checked after validation fails.
        # 返回带 token 数据的无效 JSON，用于检查校验失败后是否保留用量。
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text='not JSON', usage_metadata=SimpleNamespace(model_dump=lambda **kw: {'total_token_count': 19}))
    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    adapter = Gemini(Ledger(tmp_path / 'usage.jsonl'), client=client)
    with pytest.raises(ValueError):
        asyncio.run(adapter.generate('run', 'developer', 'generate', {}, Application))
    assert adapter.ledger.summary()['provider_total_tokens'] == 38
    assert adapter.ledger.summary()['api_calls'] == 2


# Verify that real MCP subprocesses expose only the tools assigned to their roles.
# 验证真实 MCP 子进程只公开各自角色负责的工具。
def test_real_stdio_role_discovery(tmp_path):
    # Start the role clients and query each server through its STDIO session.
    # 启动角色客户端，通过各自的 STDIO 会话查询服务端工具。
    async def scenario():
        async with AgentClients(tmp_path) as agents:
            assert await agents.tools('planner') == {'plan_requirements'}
            assert await agents.tools('developer') == {'generate_application', 'repair_application'}
            assert await agents.tools('tester') == {'generate_tests'}
    asyncio.run(scenario())


# Verify that one invalid response can be retried and both attempts are recorded.
# 验证无效响应可重试一次，而且两次请求都会被记录。
def test_malformed_output_has_one_tracked_retry(tmp_path):
    class Models:
        count = 0
        # Return malformed output once, followed by a valid three-file application.
        # 首次返回无效输出，第二次返回包含三个文件的有效应用。
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


# Verify that the API error includes useful context and redacts the configured key.
# 验证 API 错误包含有用信息，并隐藏配置的密钥。
def test_api_error_explains_failure_without_exposing_key(tmp_path, monkeypatch):
    from google.genai import errors
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret-value')
    class Models:
        # Raise a provider error that includes the fake key to exercise redaction.
        # 抛出包含模拟密钥的服务端错误，以检查脱敏过程。
        async def generate_content(self, **kwargs):
            raise errors.ClientError(400, {'error': {'message':'Unsupported schema; key test-secret-value'}})
    adapter = Gemini(Ledger(tmp_path / 'usage.jsonl'), client=SimpleNamespace(aio=SimpleNamespace(models=Models())))
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(adapter.generate('run', 'planner', 'plan', {}, Application))
    assert 'Unsupported schema' in str(caught.value)
    assert 'test-secret-value' not in str(caught.value)


# Verify that Gemini receives the full Pydantic JSON Schema through the expected SDK parameter.
# 验证 Gemini 通过指定的 SDK 参数接收完整的 Pydantic JSON Schema。
def test_full_json_schema_uses_json_schema_parameter(tmp_path):
    class Models:
        # Inspect the request configuration and return a valid application response.
        # 检查请求配置，并返回有效的应用响应。
        async def generate_content(self, **kwargs):
            config = kwargs['config']
            assert config.response_schema is None
            assert config.response_json_schema == Application.model_json_schema()
            return SimpleNamespace(text='{"files":[{"path":"app.py","content":"pass"},{"path":"logic.py","content":"pass"},{"path":"README.md","content":"Run"}]}', usage_metadata=None)
    adapter = Gemini(Ledger(tmp_path / 'usage.jsonl'), client=SimpleNamespace(aio=SimpleNamespace(models=Models())))
    asyncio.run(adapter.generate('run', 'developer', 'generate', {}, Application))
