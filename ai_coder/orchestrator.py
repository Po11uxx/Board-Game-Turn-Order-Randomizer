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


class TestSyntaxError(ValueError):
    pass


def validate_tests(suite, spec):
    expected = {r.id for r in spec.requirements}
    if {c.requirement_id for c in suite.coverage} != expected:
        raise ValueError('Test mapping must cover every requirement')
    functions = set()
    for file in suite.files:
        try:
            tree = ast.parse(file.content, filename=file.path)
        except SyntaxError as exc:
            raise TestSyntaxError(f'{file.path}:{exc.lineno}: {exc.msg}') from None
        functions.update(n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_'))
        for node in ast.walk(tree):
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
    def __init__(self, runs, agents, runner, notify=None):
        self.runs, self.agents, self.runner = Path(runs), agents, runner
        self.notify = notify or (lambda state: None)
        self.trace = []

    async def call(self, role, tool, **payload):
        started = time.monotonic()
        event = dict(role=role, tool=tool, status='running', run_id=self.run_id)
        self.trace.append(event)
        self.workspace.save('trace.json', self.trace)
        try:
            result = await self.agents.call(role, tool, dict(run_id=self.run_id, **payload))
            event['status'] = 'ok'
            return result
        except Exception:
            event['status'] = 'error'
            raise
        finally:
            event['duration'] = round(time.monotonic() - started, 3)
            self.workspace.save('trace.json', self.trace)

    async def run(self, request):
        self.run_id = uuid4().hex
        self.workspace = ws = Workspace(self.runs / self.run_id)
        ws.save('request.json', request.model_dump())
        ws.save('rules.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (ROOT / 'agents').rglob('*.md')})
        reports, status, detail = [], 'ERROR', ''
        problem = await asyncio.to_thread(self.runner.check)
        try:
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
                    except TestSyntaxError as exc:
                        if test_attempt == 1:
                            raise
                        feedback = {'error': str(exc), 'previous_tests': suite.model_dump()}
                        ws.save('rejected_tests.json', feedback)
                        self.notify('Regenerating invalid test syntax (once, before execution)')
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
