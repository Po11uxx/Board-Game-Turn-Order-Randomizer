import json
import zipfile
from pathlib import Path
import pytest
from ai_coder.models import Request, File, Spec, Requirement, Acceptance
from ai_coder.artifacts import Workspace
from ai_coder.usage import Ledger


def test_request_rejects_blank_and_duplicate_ids():
    with pytest.raises(ValueError):
        Request(description=' ', requirements=[Requirement(id='R1', text='work')])
    with pytest.raises(ValueError):
        Request(description='app', requirements=[Requirement(id='R1', text='a'), Requirement(id='R1', text='b')])


def test_workspace_rejects_traversal_and_overwriting_tests(tmp_path):
    ws = Workspace(tmp_path)
    for name in ('../escape.py', '/tmp/x.py', 'tests/test_x.py'):
        with pytest.raises(ValueError):
            ws.write_files([File(path=name, content='pass')], 'developer')
    assert not (tmp_path / 'generated' / 'tests' / 'test_x.py').exists()


def test_export_contains_only_validated_artifacts(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_files([File(path='logic.py', content='x=1')], 'developer')
    (tmp_path / '.env').write_text('secret')
    bundle = ws.export('NOT RUN')
    with zipfile.ZipFile(bundle) as archive:
        assert 'logic.py' in archive.namelist()
        assert '.env' not in archive.namelist()
        assert json.loads(archive.read('manifest.json'))['status'] == 'NOT RUN'


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


def test_usage_can_be_aggregated_per_agent(tmp_path):
    ledger = Ledger(tmp_path / 'usage.jsonl')
    for agent in ('planner','developer','developer'):
        ledger.start('run', agent, 'generation', 'model')
    assert ledger.summary('run', 'developer')['api_calls'] == 2
    assert ledger.summary('run', 'tester')['api_calls'] == 0


def test_dependencies_exist_before_execution(tmp_path):
    ws = Workspace(tmp_path)
    assert (ws.generated / 'requirements.txt').exists()
    assert 'requirements.txt' in ws.hashes()


def test_tester_schema_rejects_application_files():
    from ai_coder.models import TestSuite
    with pytest.raises(ValueError):
        TestSuite(files=[{'path':'app.py', 'content':'pass'}], coverage=[])


def test_readme_includes_standalone_privacy_setup(tmp_path):
    ws=Workspace(tmp_path)
    ws.write_files([File(path='README.md', content='Generated notes')], 'developer')
    text=(ws.generated/'README.md').read_text()
    assert 'GRADIO_RUN_HISTORY=False' in text
    assert 'pip install -r requirements.txt' in text
    assert 'Generated notes' in text
