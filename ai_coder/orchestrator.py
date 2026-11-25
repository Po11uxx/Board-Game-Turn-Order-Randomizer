# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import ast
import asyncio
import hashlib
import time
from pathlib import Path
from uuid import uuid4
from ai_coder.artifacts import Workspace
from ai_coder.gemini import ROOT
from ai_coder.models import Spec, Application, TestSuite
from ai_coder.usage import Ledger


class TestPreparationError(ValueError):
    pass


# Check test syntax, public callback imports, and coverage claims before allowing execution.
# 在执行前检查测试语法、公开回调的导入和需求覆盖声明。
def validate_tests(suite, spec):
    expected = {r.id for r in spec.requirements}
    callbacks = set(spec.ui_callbacks)
    if {c.requirement_id for c in suite.coverage} != expected:
        raise ValueError('Test mapping must cover every requirement')
    functions = set()
    for file in suite.files:
        try:
            tree = ast.parse(file.content, filename=file.path)
        except SyntaxError as exc:
            raise TestPreparationError(f'{file.path}:{exc.lineno}: {exc.msg}') from None
        functions.update(n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == 'app':
                unknown = {name.name for name in node.names} - callbacks
                if unknown:
                    raise TestPreparationError(
                        f'{file.path}:{node.lineno}: Undeclared app callbacks: '
                        f'{", ".join(sorted(unknown))}. Import only ui_callbacks declared '
                        f'by the Planner: {", ".join(sorted(callbacks)) or "none"}.')
            if isinstance(node, ast.Import) and any(name.name == 'app' for name in node.names):
                raise TestPreparationError(
                    f'{file.path}:{node.lineno}: Use explicit from app imports for declared UI callbacks.')
            if isinstance(node, ast.Attribute) and node.attr in {'skip', 'skipif', 'xfail'}:
                raise ValueError('Skipped/xfail tests are not accepted')
    if not functions:
        raise ValueError('No executable tests were generated')
    for item in suite.coverage:
        if item.method == 'automated' and (not item.test_names or not set(item.test_names) <= functions):
            raise ValueError('Automated mapping references missing tests')
    automated = {a.requirement_id for a in spec.acceptance if a.method == 'automated'}
    if not automated <= {c.requirement_id for c in suite.coverage if c.method == 'automated'}:
        raise ValueError('Tester weakened automated acceptance criteria')


class Pipeline:
    # Store the injected agents, runner, and optional callbacks for progress and trace updates.
    # 保存传入的角色客户端、执行器和可选的进度及调用记录回调。
    def __init__(self, runs, agents, runner, notify=None, *, notify_trace=None):
        self.runs, self.agents, self.runner = Path(runs), agents, runner
        self.notify = notify or (lambda state: None)
        self.notify_trace = notify_trace
        self.trace = []

    # Persist the trace and publish a snapshot so earlier UI updates are protected from later mutations.
    # 保存 MCP 调用记录并发布副本，避免后续修改影响已发出的界面更新。
    def record_trace(self):
        self.workspace.save('trace.json', self.trace)
        if self.notify_trace is not None:
            self.notify_trace([event.copy() for event in self.trace])

    # Route a tool call to its role and record its state and duration even when it fails.
    # 将工具调用交给对应角色，并记录状态和耗时，包括失败的调用。
    async def call(self, role, tool, **payload):
        started = time.monotonic()
        event = dict(role=role, tool=tool, status='running', run_id=self.run_id)
        self.trace.append(event)
        self.record_trace()
        try:
            result = await self.agents.call(role, tool, dict(run_id=self.run_id, **payload))
            event['status'] = 'ok'
            return result
        except Exception:
            event['status'] = 'error'
            raise
        finally:
            event['duration'] = round(time.monotonic() - started, 3)
            self.record_trace()

    # Plan the application, generate and lock its tests, then run bounded repair and export the evidence.
    # 规划应用、生成并锁定测试，再执行有限轮次的修复并导出验证记录。
    async def run(self, request):
        self.run_id = uuid4().hex
        self.workspace = ws = Workspace(self.runs / self.run_id)
        ws.save('request.json', request.model_dump())
        ws.save('rules.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (ROOT / 'agents').rglob('*.md')})
        reports, status, detail = [], 'ERROR', ''
        try:
            problem = await asyncio.to_thread(self.runner.check)
            if problem:
                status, detail = 'NOT RUN', problem
            else:
                self.notify('Planning')
                spec = Spec.model_validate(await self.call('planner', 'plan_requirements', request=request.model_dump()))
                spec.check_request(request)
                ws.save('spec.json', spec.model_dump())
                self.notify('Developing')
                application = Application.model_validate(await self.call('developer', 'generate_application', spec=spec.model_dump()))
                ws.write_files(application.files, 'developer')
                self.notify('Generating tests')
                feedback = None
                for test_attempt in range(2):
                    suite = TestSuite.model_validate(await self.call('tester', 'generate_tests',
                        request=request.model_dump(), spec=spec.model_dump(), feedback=feedback))
                    ws.write_files(suite.files, 'tester')
                    ws.save('coverage.json', suite.model_dump()['coverage'])
                    try:
                        validate_tests(suite, spec)
                        break
                    except TestPreparationError as exc:
                        if test_attempt == 1:
                            raise
                        feedback = {'error': str(exc), 'previous_tests': suite.model_dump()}
                        ws.save('rejected_tests.json', feedback)
                        self.notify('Regenerating invalid tests (once, before execution)')
                test_hashes = {p: h for p, h in ws.hashes().items() if p.startswith('tests/')}
                for round_index in range(3):
                    self.notify(f'Executing tests and startup check (revision {round_index})')
                    hashes = ws.hashes()
                    if {p: h for p, h in hashes.items() if p.startswith('tests/')} != test_hashes:
                        raise ValueError('Test files changed during repair')
                    report = await asyncio.to_thread(self.runner.run, ws.generated)
                    status, detail = report.status, report.detail
                    reports.append(dict(revision=round_index, files=hashes, **report.model_dump()))
                    ws.save('reports.json', reports)
                    if status != 'FAILED' or round_index == 2:
                        break
                    self.notify(f'Repairing application (round {round_index + 1}/2)')
                    application = Application.model_validate(await self.call('developer', 'repair_application',
                        spec=spec.model_dump(), application=application.model_dump(), report=report.model_dump()))
                    ws.write_files(application.files, 'developer')
        except Exception as exc:
            # Pipeline is the UI error boundary: retain evidence and mark ERROR.
            # 在流程层统一处理传给界面的错误，保留证据并标记为 ERROR。
            status, detail = 'ERROR', str(exc)[:4000]
        ledger = Ledger(self.runs / 'usage.jsonl')
        usage = {'run': ledger.summary(self.run_id), 'cumulative': ledger.summary(),
                 'calls': ledger.calls(self.run_id),
                 'per_agent': {role: ledger.summary(self.run_id, role) for role in ('planner', 'developer', 'tester')},
                 'mcp_tool_calls': len(self.trace), 'test_executions': len(reports)}
        ws.save('usage.json', usage)
        ws.save('trace.json', self.trace)
        ws.save('result.json', {'run_id': self.run_id, 'status': status, 'detail': detail,
                                'repair_rounds': sum(e['tool'] == 'repair_application' for e in self.trace),
                                'manual_ui_validation': 'NOT RUN'})
        bundle = ws.export(status)
        self.notify(status)
        return dict(run_id=self.run_id, status=status, detail=detail, reports=reports,
                    trace=self.trace, usage=usage, bundle=str(bundle), generated=str(ws.generated))
