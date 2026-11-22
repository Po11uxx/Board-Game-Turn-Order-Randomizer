# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import argparse
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from ai_coder.gemini import Gemini, ROLES
from ai_coder.models import Request, Spec, Application, TestSuite
from ai_coder.usage import Ledger


# Register only the MCP tools assigned to this role and route their model calls through the usage ledger.
# 只注册当前角色负责的 MCP 工具，并通过用量日志记录它们发起的模型调用。
def create_server(role, ledger_path):
    server = FastMCP(f'ai-coder-{role}', log_level='WARNING')
    adapter = Gemini(Ledger(ledger_path))

    if role == 'planner':
        # Turn the original request into a specification and check that it retains every requirement.
        # 将原始请求整理成规格，并检查是否保留了全部需求。
        @server.tool()
        async def plan_requirements(run_id: str, request: dict) -> dict:
            request = Request.model_validate(request)
            spec = await adapter.generate(run_id, role, 'plan', request.model_dump(), Spec)
            spec.check_request(request)
            return spec.model_dump()
    elif role == 'developer':
        # Generate the application files from the validated Planner specification.
        # 根据已验证的 Planner 规格生成应用文件。
        @server.tool()
        async def generate_application(run_id: str, spec: dict) -> dict:
            spec = Spec.model_validate(spec)
            result = await adapter.generate(run_id, role, 'generate', spec.model_dump(), Application)
            return result.model_dump()

        # Send the current application and execution report to Developer for a targeted repair.
        # 把当前应用和执行报告交给 Developer，针对报告中的问题修复。
        @server.tool()
        async def repair_application(run_id: str, spec: dict, application: dict, report: dict) -> dict:
            payload = {'spec': Spec.model_validate(spec).model_dump(),
                       'application': Application.model_validate(application).model_dump(), 'report': report}
            return (await adapter.generate(run_id, role, 'repair', payload, Application)).model_dump()
    elif role == 'tester':
        # Generate pytest files from the request, specification, and any pre-execution feedback.
        # 根据请求、规格和执行前的反馈生成 pytest 文件。
        @server.tool()
        async def generate_tests(run_id: str, request: dict, spec: dict, feedback: dict | None = None) -> dict:
            payload = {'request': Request.model_validate(request).model_dump(),
                       'spec': Spec.model_validate(spec).model_dump(),
                       'task': 'Generate only executable pytest files for the agreed logic and UI callback interfaces. No application source.',
                       'pre_execution_feedback': feedback}
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
