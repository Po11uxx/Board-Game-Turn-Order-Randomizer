# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import json
import zipfile
from pathlib import Path
import pytest
from ai_coder.models import Request, File, Spec, Requirement, Acceptance
from ai_coder.artifacts import Workspace
from ai_coder.usage import Ledger


# Verify that a blank description and duplicate requirement IDs are rejected.
# 验证系统会拒绝空描述和重复的需求编号。
def test_request_rejects_blank_and_duplicate_ids():
    with pytest.raises(ValueError):
        Request(description=' ', requirements=[Requirement(id='R1', text='work')])
    with pytest.raises(ValueError):
        Request(description='app', requirements=[Requirement(id='R1', text='a'), Requirement(id='R1', text='b')])


# Verify that Developer cannot use unsafe paths or overwrite Tester files.
# 验证 Developer 不能使用越界路径或覆盖 Tester 的文件。
def test_workspace_rejects_traversal_and_overwriting_tests(tmp_path):
    ws = Workspace(tmp_path)
    for name in ('../escape.py', '/tmp/x.py', 'tests/test_x.py'):
        with pytest.raises(ValueError):
            ws.write_files([File(path=name, content='pass')], 'developer')
    assert not (tmp_path / 'generated' / 'tests' / 'test_x.py').exists()


# Verify that the ZIP includes approved artifacts and excludes the local environment file.
# 验证 ZIP 包含允许导出的产物，并排除本地环境配置。
def test_export_contains_only_validated_artifacts(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_files([File(path='logic.py', content='x=1')], 'developer')
    (tmp_path / '.env').write_text('secret')
    bundle = ws.export('NOT RUN')
    with zipfile.ZipFile(bundle) as archive:
        assert 'logic.py' in archive.namelist()
        assert '.env' not in archive.namelist()
        assert json.loads(archive.read('manifest.json'))['status'] == 'NOT RUN'


# Verify that incomplete usage stays unknown and reported totals are counted once.
# 验证缺失用量被标为未知，服务端报告的总量只统计一次。
def test_ledger_preserves_unknown_and_does_not_double_count(tmp_path):
    ledger = Ledger(tmp_path / 'usage.jsonl')
    first = ledger.start('run', 'planner', 'generate', 'model')
    ledger.finish(first, 'ok', {'prompt_token_count': 10, 'candidates_token_count': 5, 'thoughts_token_count': 3, 'total_token_count': 18})
    ledger.start('run', 'developer', 'generate', 'model')
    result = ledger.summary('run')
    assert result['api_calls'] == 2
    assert result['provider_total_tokens'] == 18
    assert result['unknown_usage_calls'] == 1
    assert result['reasoning_tokens'] == 3


# Verify that usage totals include only attempts by the requested role.
# 验证按角色汇总的结果只包含指定角色的 API 请求。
def test_usage_can_be_aggregated_per_agent(tmp_path):
    ledger = Ledger(tmp_path / 'usage.jsonl')
    for agent in ('planner','developer','developer'):
        ledger.start('run', agent, 'generation', 'model')
    assert ledger.summary('run', 'developer')['api_calls'] == 2
    assert ledger.summary('run', 'tester')['api_calls'] == 0


# Verify that each workspace starts with pinned dependencies included in its artifact hashes.
# 验证工作区创建时就包含锁定版本的依赖文件，并将其纳入哈希清单。
def test_dependencies_exist_before_execution(tmp_path):
    ws = Workspace(tmp_path)
    assert (ws.generated / 'requirements.txt').exists()
    assert 'requirements.txt' in ws.hashes()


# Verify that a Tester response cannot contain an application file.
# 验证 Tester 的响应不能包含应用源码文件。
def test_tester_schema_rejects_application_files():
    from ai_coder.models import TestSuite
    with pytest.raises(ValueError):
        TestSuite(files=[{'path':'app.py', 'content':'pass'}], coverage=[])


# Verify that the generated README includes the host's install and privacy setup alongside the generated notes.
# 验证生成的 README 同时包含平台提供的安装和隐私说明，以及模型生成的说明。
def test_readme_includes_standalone_privacy_setup(tmp_path):
    ws=Workspace(tmp_path)
    ws.write_files([File(path='README.md', content='Generated notes')], 'developer')
    text=(ws.generated/'README.md').read_text()
    assert 'GRADIO_RUN_HISTORY=False' in text
    assert 'pip install -r requirements.txt' in text
    assert 'Generated notes' in text
