import argparse
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from ai_coder.gemini import Gemini, ROLES
from ai_coder.models import Request, Spec, Application, TestSuite
from ai_coder.usage import Ledger


def create_server(role, ledger_path):
    server = FastMCP(f'ai-coder-{role}', log_level='WARNING')
    adapter = Gemini(Ledger(ledger_path))

    if role == 'planner':
        @server.tool()
        async def plan_requirements(run_id: str, request: dict) -> dict:
            request = Request.model_validate(request)
            spec = await adapter.generate(run_id, role, 'plan', request.model_dump(), Spec)
            spec.check_request(request)
            return spec.model_dump()
    elif role == 'developer':
        @server.tool()
        async def generate_application(run_id: str, spec: dict) -> dict:
            spec = Spec.model_validate(spec)
            result = await adapter.generate(run_id, role, 'generate', spec.model_dump(), Application)
            return result.model_dump()

        @server.tool()
        async def repair_application(run_id: str, spec: dict, application: dict, report: dict) -> dict:
            payload = {'spec': Spec.model_validate(spec).model_dump(),
                       'application': Application.model_validate(application).model_dump(), 'report': report}
            return (await adapter.generate(run_id, role, 'repair', payload, Application)).model_dump()
    elif role == 'tester':
        @server.tool()
        async def generate_tests(run_id: str, request: dict, spec: dict, feedback: dict | None = None) -> dict:
            payload = {'request': Request.model_validate(request).model_dump(),
                       'spec': Spec.model_validate(spec).model_dump(),
                       'task': 'Generate only executable pytest files importing from logic. No application source.',
                       'syntax_feedback': feedback}
            return (await adapter.generate(run_id, role, 'generate_tests', payload, TestSuite)).model_dump()
    else:
        raise ValueError('Unknown role')
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--role', choices=ROLES, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    create_server(args.role, args.ledger).run(transport='stdio')
