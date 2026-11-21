import asyncio
from pathlib import Path
import pytest
from ai_coder.models import Request, Requirement, Execution
from ai_coder.orchestrator import Pipeline
from ai_coder.runner import DockerRunner

REQ = Request(description='Make a tiny app', requirements=[Requirement(id='R1', text='Return one')])
SPEC = {'requirements':[{'id':'R1','text':'Return one'}], 'interfaces':[{'signature':'value()','behavior':'Return one','returns':'int','errors':'none'}], 'ui_behavior':'Display one', 'acceptance':[{'requirement_id':'R1','criterion':'returns 1','method':'automated'}]}
APP = {'files':[{'path':'app.py','content':'print(1)'},{'path':'logic.py','content':'def value(): return 1'},{'path':'README.md','content':'Run app.py'}]}
SUITE = {'files':[{'path':'tests/test_value.py','content':'from logic import value\ndef test_value():\n    assert value() == 1\n'}], 'coverage':[{'requirement_id':'R1','method':'automated','test_names':['test_value'],'explanation':'value returns one'}]}

class Agents:
    def __init__(self): self.calls = []
    async def call(self, role, name, arguments):
        self.calls.append(name)
        return {'plan_requirements':SPEC, 'generate_application':APP, 'generate_tests':SUITE, 'repair_application':APP}[name]

class Runner:
    def __init__(self, statuses): self.statuses = iter(statuses); self.test_snapshots = []
    def check(self): return None
    def run(self, root):
        self.test_snapshots.append((root / 'tests/test_value.py').read_bytes())
        status = next(self.statuses)
        return Execution(status=status, detail='fixture', collected=1, passed=int(status=='PASSED'), startup_ok=status=='PASSED')


def test_repairs_twice_and_keeps_tests_unchanged(tmp_path):
    agents, runner = Agents(), Runner(['FAILED', 'FAILED', 'PASSED'])
    result = asyncio.run(Pipeline(tmp_path, agents, runner).run(REQ))
    assert result['status'] == 'PASSED'
    assert agents.calls.count('repair_application') == 2
    assert len(set(runner.test_snapshots)) == 1
    assert len(result['reports']) == 3
    assert Path(result['bundle']).exists()


def test_repair_limit_reports_failure(tmp_path):
    agents = Agents()
    result = asyncio.run(Pipeline(tmp_path, agents, Runner(['FAILED']*3)).run(REQ))
    assert result['status'] == 'FAILED'
    assert agents.calls.count('repair_application') == 2


def test_unavailable_runner_does_not_spend_tokens(tmp_path):
    class Missing:
        def check(self): return 'Docker is not running'
    agents = Agents()
    result = asyncio.run(Pipeline(tmp_path, agents, Missing()).run(REQ))
    assert result['status'] == 'NOT RUN'
    assert agents.calls == []


def test_missing_docker_is_not_a_pass(monkeypatch):
    monkeypatch.setattr('ai_coder.runner.shutil.which', lambda name: None)
    assert DockerRunner().check() == 'Docker CLI is not installed'


def test_tester_cannot_weaken_coverage():
    from ai_coder.orchestrator import validate_tests
    from ai_coder.models import TestSuite, Spec
    suite = TestSuite.model_validate(SUITE)
    suite.coverage[0].method = 'manual'
    with pytest.raises(ValueError, match='weakened'):
        validate_tests(suite, Spec.model_validate(SPEC))


def test_bad_tests_do_not_enter_repair(tmp_path):
    class BadTests(Agents):
        async def call(self, role, name, arguments):
            if name == 'generate_tests':
                self.calls.append(name)
                return {'files':[{'path':'tests/test_value.py','content':'x = 1'}], 'coverage':SUITE['coverage']}
            return await super().call(role, name, arguments)
    agents = BadTests()
    result = asyncio.run(Pipeline(tmp_path, agents, Runner([])).run(REQ))
    assert result['status'] == 'ERROR'
    assert 'repair_application' not in agents.calls


def test_unavailable_runner_exports_failure_reason(tmp_path):
    import json
    import zipfile
    class Missing:
        def check(self): return 'Docker is not running'
    result = asyncio.run(Pipeline(tmp_path, Agents(), Missing()).run(REQ))
    with zipfile.ZipFile(result['bundle']) as archive:
        summary = json.loads(archive.read('result.json'))
        assert summary['detail'] == 'Docker is not running'
        assert summary['status'] == 'NOT RUN'


def test_invalid_test_source_is_retained_for_review(tmp_path):
    import zipfile
    class BadTests(Agents):
        async def call(self, role, name, arguments):
            if name == 'generate_tests':
                return {'files':[{'path':'tests/test_value.py','content':'def broken(:'}], 'coverage':SUITE['coverage']}
            return await super().call(role, name, arguments)
    result = asyncio.run(Pipeline(tmp_path, BadTests(), Runner([])).run(REQ))
    assert result['status'] == 'ERROR'
    assert 'tests/test_value.py' in result['detail']
    with zipfile.ZipFile(result['bundle']) as archive:
        assert archive.read('tests/test_value.py') == b'def broken(:'


def test_test_syntax_can_regenerate_once_before_execution(tmp_path):
    class Recovering(Agents):
        count = 0
        async def call(self, role, name, arguments):
            if name == 'generate_tests':
                self.count += 1
                if self.count == 1:
                    self.calls.append(name)
                    return {'files':[{'path':'tests/test_bad.py','content':'def broken(:'}], 'coverage':SUITE['coverage']}
                assert 'syntax' in arguments['feedback']['error']
            return await super().call(role, name, arguments)
    agents = Recovering()
    result = asyncio.run(Pipeline(tmp_path, agents, Runner(['PASSED'])).run(REQ))
    assert result['status'] == 'PASSED'
    assert agents.calls.count('generate_tests') == 2
    assert not (Path(result['generated']) / 'tests/test_bad.py').exists()


def test_tests_using_undeclared_ui_callbacks_regenerate_before_execution(tmp_path):
    class CallbackAgents(Agents):
        async def call(self, role, name, arguments):
            if name == 'plan_requirements':
                return {**SPEC, 'ui_callbacks': ['randomize_callback']}
            if name == 'generate_tests' and arguments['feedback'] is None:
                return {
                    **SUITE,
                    'files': [{
                        'path': 'tests/test_value.py',
                        'content': 'from app import randomize_callback, reshuffle_callback\n'
                                   'def test_value():\n    assert randomize_callback()\n',
                    }],
                }
            if name == 'generate_tests':
                assert 'Undeclared app callbacks: reshuffle_callback' in arguments['feedback']['error']
            return await super().call(role, name, arguments)

    runner = Runner(['PASSED'])
    result = asyncio.run(Pipeline(tmp_path, CallbackAgents(), runner).run(REQ))
    assert result['status'] == 'PASSED'
    assert len(runner.test_snapshots) == 1
    assert b'reshuffle_callback' not in runner.test_snapshots[0]
    assert (Path(result['generated']).parent / 'rejected_tests.json').exists()
