# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import json
import os
import sys
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ai_coder.gemini import ROOT, ROLES


class AgentClients:
    # Resolve the run directory and prepare to manage the lifecycle of all MCP sessions.
    # 解析运行目录的绝对路径，并准备管理所有 MCP 会话。
    def __init__(self, runs: Path):
        self.runs = runs.resolve()
        self.sessions = {}
        self.stack = AsyncExitStack()

    # Launch a STDIO MCP process for each role and close partial sessions if initialization fails.
    # 为每个角色启动 STDIO MCP 进程。初始化失败时关闭已启动的会话。
    async def __aenter__(self):
        try:
            for role in ROLES:
                env = {k: os.environ[k] for k in ('PATH', 'HOME', 'GEMINI_API_KEY', 'GEMINI_MODEL') if k in os.environ}
                env['PYTHONPATH'] = str(ROOT)
                params = StdioServerParameters(command=sys.executable,
                    args=['-m', 'ai_coder.server', '--role', role, '--ledger', str(self.runs / 'usage.jsonl')],
                    env=env, cwd=str(ROOT))
                read, write = await self.stack.enter_async_context(stdio_client(params))
                session = await self.stack.enter_async_context(ClientSession(read, write, read_timeout_seconds=timedelta(seconds=540)))
                await session.initialize()
                self.sessions[role] = session
        except BaseException:
            await self.stack.aclose()
            raise
        return self

    # Close the role sessions and their STDIO transports when generation finishes.
    # 生成结束后关闭各角色的会话和 STDIO 连接。
    async def __aexit__(self, *args):
        await self.stack.aclose()

    # List the tools exposed by an initialized role for capability discovery.
    # 列出已初始化角色提供的工具，供客户端发现其能力。
    async def tools(self, role):
        return {tool.name for tool in (await self.sessions[role].list_tools()).tools}

    # Invoke a role's MCP tool and return its structured response or a bounded error.
    # 调用指定角色的 MCP 工具，返回结构化结果或长度受限的错误信息。
    async def call(self, role, name, arguments):
        result = await self.sessions[role].call_tool(name, arguments)
        if result.isError:
            detail = '\n'.join(c.text for c in result.content if c.type == 'text')
            # Server errors are sanitized by the Gemini adapter.
            # Gemini 适配器会对服务端错误信息做脱敏处理。
            raise RuntimeError(f'{name}: {detail[:2000]}')
        if result.structuredContent is not None:
            return result.structuredContent
        return json.loads(next(c.text for c in result.content if c.type == 'text'))
