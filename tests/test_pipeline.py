# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

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
    # Initialize a call log for the fake MCP roles.
    # 为模拟的 MCP 角色初始化调用记录。
    def __init__(self): self.calls = []
    # Record the tool name and return the canned response for that role.
    # 记录工具名称，并返回对应角色的预设结果。
    async def call(self, role, name, arguments):
        self.calls.append(name)
        return {'plan_requirements':SPEC, 'generate_application':APP, 'generate_tests':SUITE, 'repair_application':APP}[name]

class Runner:
    # Queue execution outcomes and create storage for snapshots of the locked tests.
    # 准备有序的执行结果，并创建存储以记录锁定测试的副本。
    def __init__(self, statuses): self.statuses = iter(statuses); self.test_snapshots = []
    # Report a ready runner so the test can exercise the generation pipeline.
    # 让模拟执行器报告已就绪，以便测试生成流程。
    def check(self): return None
    # Capture the test file bytes before returning the next configured execution outcome.
    # 保存测试文件的字节内容，再返回下一个预设的执行结果。
    def run(self, root):
        self.test_snapshots.append((root / 'tests/test_value.py').read_bytes())
        status = next(self.statuses)
        return Execution(status=status, detail='fixture', collected=1, passed=int(status=='PASSED'), startup_ok=status=='PASSED')


# Verify that two application repairs can succeed without changing the test files.
# 验证应用可以在两轮修复后通过，并且两轮都使用原有测试文件。
def test_repairs_twice_and_keeps_tests_unchanged(tmp_path):
    agents, runner = Agents(), Runner(['FAILED', 'FAILED', 'PASSED'])
    result = asyncio.run(Pipeline(tmp_path, agents, runner).run(REQ))
    assert result['status'] == 'PASSED'
    assert agents.calls.count('repair_application') == 2
    assert len(set(runner.test_snapshots)) == 1
    assert len(result['reports']) == 3
    assert Path(result['bundle']).exists()


# Verify that the run reports failure after exhausting its two repair attempts.
# 验证用完两轮修复后，流程会报告失败。
def test_repair_limit_reports_failure(tmp_path):
    agents = Agents()
    result = asyncio.run(Pipeline(tmp_path, agents, Runner(['FAILED']*3)).run(REQ))
    assert result['status'] == 'FAILED'
    assert agents.calls.count('repair_application') == 2


# Verify that a failed runner preflight stops the run before any agent calls.
# 验证执行器预检查失败时，流程会在调用角色前停止。
def test_unavailable_runner_does_not_spend_tokens(tmp_path):
    class Missing:
        # Simulate a runner that cannot connect to Docker.
        # 模拟无法连接到 Docker 的执行器。
        def check(self): return 'Docker is not running'
    agents = Agents()
    result = asyncio.run(Pipeline(tmp_path, agents, Missing()).run(REQ))
    assert result['status'] == 'NOT RUN'
    assert agents.calls == []


# Verify that a missing Docker CLI produces an explicit preflight error.
# 验证 Docker 命令行缺失时，预检查会明确报错。
def test_missing_docker_is_not_a_pass(monkeypatch):
    monkeypatch.setattr('ai_coder.runner.shutil.which', lambda name: None)
    assert DockerRunner().check() == 'Docker CLI is not installed'


# Verify that the Tester cannot change an automated acceptance criterion to a manual check.
# 验证 Tester 不能把自动化验收标准改成手动检查。
def test_tester_cannot_weaken_coverage():
    from ai_coder.orchestrator import validate_tests
    from ai_coder.models import TestSuite, Spec
    suite = TestSuite.model_validate(SUITE)
    suite.coverage[0].method = 'manual'
    with pytest.raises(ValueError, match='weakened'):
        validate_tests(suite, Spec.model_validate(SPEC))


# Verify that a suite with no executable tests does not trigger Developer repair.
# 验证没有可执行测试的测试套件不会触发 Developer 修复。
def test_bad_tests_do_not_enter_repair(tmp_path):
    class BadTests(Agents):
        # Return a file with no test functions for the Tester request.
        # 在 Tester 调用中返回一个不含测试函数的文件。
        async def call(self, role, name, arguments):
            if name == 'generate_tests':
                self.calls.append(name)
                return {'files':[{'path':'tests/test_value.py','content':'x = 1'}], 'coverage':SUITE['coverage']}
            return await super().call(role, name, arguments)
    agents = BadTests()
    result = asyncio.run(Pipeline(tmp_path, agents, Runner([])).run(REQ))
    assert result['status'] == 'ERROR'
    assert 'repair_application' not in agents.calls


# Verify that the exported run status includes the reason Docker was unavailable.
# 验证导出的结果会记录 Docker 不可用的原因。
def test_unavailable_runner_exports_failure_reason(tmp_path):
    import json
    import zipfile
    class Missing:
        # Provide a predictable preflight failure for the export assertion.
        # 返回确定的预检查错误，用于验证导出内容。
        def check(self): return 'Docker is not running'
    result = asyncio.run(Pipeline(tmp_path, Agents(), Missing()).run(REQ))
    with zipfile.ZipFile(result['bundle']) as archive:
        summary = json.loads(archive.read('result.json'))
        assert summary['detail'] == 'Docker is not running'
        assert summary['status'] == 'NOT RUN'


# Verify that failed runs preserve invalid generated test source in the ZIP.
# 验证失败运行的 ZIP 会保留无效的测试源码，供复查。
def test_invalid_test_source_is_retained_for_review(tmp_path):
    import zipfile
    class BadTests(Agents):
        # Return a test file containing a deliberate syntax error.
        # 返回一份故意包含语法错误的测试文件。
        async def call(self, role, name, arguments):
            if name == 'generate_tests':
                return {'files':[{'path':'tests/test_value.py','content':'def broken(:'}], 'coverage':SUITE['coverage']}
            return await super().call(role, name, arguments)
    result = asyncio.run(Pipeline(tmp_path, BadTests(), Runner([])).run(REQ))
    assert result['status'] == 'ERROR'
    assert 'tests/test_value.py' in result['detail']
    with zipfile.ZipFile(result['bundle']) as archive:
        assert archive.read('tests/test_value.py') == b'def broken(:'


# Verify that the Tester can replace a syntax-invalid suite once before execution.
# 验证 Tester 可以在执行前重新生成一次有语法错误的测试。
def test_test_syntax_can_regenerate_once_before_execution(tmp_path):
    class Recovering(Agents):
        count = 0
        # Return invalid syntax on the first Tester call and require feedback before returning valid tests.
        # 首次 Tester 调用返回语法错误，收到反馈后再返回有效测试。
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


# Verify that undeclared app imports are rejected and only the regenerated suite is executed.
# 验证系统拒绝导入未声明的应用回调，并且只执行重生成的测试。
def test_tests_using_undeclared_ui_callbacks_regenerate_before_execution(tmp_path):
    class CallbackAgents(Agents):
        # Declare one app callback, then simulate a test importing an unapproved callback to check the feedback.
        # 声明一个应用回调，再模拟测试导入未声明的回调，以检查反馈。
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


def test_runner_check_exception_exports_diagnostic_bundle(tmp_path):
    import json
    import zipfile

    class BrokenRunner:
        def check(self):
            raise OSError('Docker socket unavailable')

    agents = Agents()
    result = asyncio.run(Pipeline(tmp_path, agents, BrokenRunner()).run(REQ))
    assert result['status'] == 'ERROR'
    assert agents.calls == []
    with zipfile.ZipFile(result['bundle']) as archive:
        assert 'Docker socket unavailable' in json.loads(archive.read('result.json'))['detail']
